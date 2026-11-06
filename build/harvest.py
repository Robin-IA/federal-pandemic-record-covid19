#!/usr/bin/env python3
"""Ask Wayback's CDX index what each federal source published, per build/sources.tsv.

Modelled on Letters from Congress's harvest.py, and for the same reasons:

**The cache holds raw rows.** Everything CDX returns for a source is cached
verbatim in data/cdx-cache/, and cleaning runs on the way out. Querying is
minutes to hours; re-filtering is seconds, so a newly found kind of junk costs
an --export-only run instead of another pass at the server.

**A failure is recorded as a failure, never as a number.** A failed request and
an empty folder look the same in a spreadsheet. A source that errors is cached
with its error and retried on the next run; a source silently short stays wrong.
Hitting the row cap is a failure too: the resume key's presence says so.

**Narrow prefixes, no regex on big folders.** Measured in the Cowork survey,
22-25 Oct 2026: a domain-wide or regex-filtered query on cdc.gov or a large
/sites/default/files/ folder answers 503 or 504 after about a minute, and any
prefix query on www.whitehouse.gov answers 503 in five seconds, every time.
Keyword selection therefore runs here, locally, on the last path segment.
Large folders use mode `paged`, one cached file per CDX index page, so a run
of many hours can stop and resume. Expensive pages fail first, so a partial
paged run understates.

**Three ways in to an agency, measured 5 Nov 2026.** Where file names say
COVID (CMS, VA), the folder is read and selected by keyword. Where a Drupal
site files uploads by month (SBA; FEMA in 2020), mode `months` reads one
small folder per month. Where names are numbers or codes (FDA's
/media/<id>/download, OSHA3990.pdf) or COVID files sit among everything else
(Treasury, DOL, USDA), mode `hub` takes what the agency's own COVID page, and
the pages under it, linked to, with the link text as the title. See
collection-analysis docs/methodologies/03-wayback-search.md.

**https only.** Letters from Congress found the http endpoint answering
"Temporarily Offline" 503s that https did not.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import gzip
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CDX = "https://web.archive.org/cdx/search/cdx"
UA = {"User-Agent": "ia-federal-pandemic-record/0.1 "
                    "(Internet Archive; collections research)"}
FIELDS = ["original", "timestamp", "mimetype", "statuscode", "digest", "length"]

# The period: the first federal notices in December 2019 to the end of the
# Public Health Emergency. CDX takes months; URL dates are checked to the day.
FROM, TO = "201912", "202305"
FIRST_DAY, LAST_DAY = "20191201", "20230511"

TIMEOUT = 240
RETRIES = 3
ROW_CAP = 150_000
CACHE_METHOD = "v1"
MONTH = "{month}"
HUB_FLOOR = "20200101"
# CDX can answer an empty 200 for a query that has rows (seen by dates.py,
# 26 Oct 2026), so an empty answer is asked again, this long after, before it
# is believed.
EMPTY_PAUSE = 10.0
DEFAULT_STATUSES = {"harvested", "partial", "retry"}

# Tested in the Cowork survey. Word boundaries matter: without them "ppe"
# matched inside "copper". Slugs both over- and under-match, so the White House
# lists still need a read by hand.
KEYWORDS = re.compile(
    r"(covid|coronavirus|pandemic|vaccin|sars-cov|public-health-emergency|novel-corona|"
    r"(^|-)masks?(-|$)|mask-wearing|(^|-)testing(-|$)|reopen|cares-act|american-rescue|"
    r"paycheck|stimulus|quarantine|social-distanc|ventilator|(^|-)dpa(-|$)|"
    r"defense-production-act|(^|-)ppe(-|$)|personal-protective|long-covid|omicron|"
    r"delta-variant|suspension-of-entry|suspending-entry|immigrants-who-present-risk|"
    r"economic-relief|eviction|student-loan|task-force|opening-up-america|warp-speed|"
    r"hydroxychloroquine)")

URL_DATE = re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")

# Links mangled by whatever page cited them, and captured anyway: a bracket or
# quote from the surrounding markup, a trailing space or hyphen, an Outlook
# safelink tail, a JSON fragment, "-.5". Each is cut back to what it was meant
# to be, and dropped only where that address is in the source too: a mangled
# link with no well-formed twin is kept, since it may be the only trace.
EXTENSIONS = r"(?:aspx|html|htm|pdf|docx|doc|xlsx|xls|pptx|ppt)"
# A second real extension is not a tail: .pdf.pdf and .html.pdf are files of
# their own, with digests that differ from their single-extension namesakes.
EXTENSION_TAIL = re.compile(rf"(\.{EXTENSIONS})(?![A-Za-z0-9])(?!\.{EXTENSIONS}$)[^/]+$")
MARKUP_TAIL = re.compile(r"""[\[\]<>"&].*$|\.\*.*$|-\.\d+$""")

# What a hub page links to that counts as a document: an Office or PDF file
# name, or FDA's /media/<id>/download, which serves PDFs under no file name.
ANCHOR = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*["']([^"'#\s]+)["'][^>]*>(.*?)</a\s*>""",
                    re.IGNORECASE | re.DOTALL)
TAG = re.compile(r"<[^>]+>")
# Link text that says nothing about the document: kept out of titles.
EMPTY_TEXT = re.compile(r"^(pdf|download|here|click here|english|espa[nñ]ol|spanish|view|read more|"
                        r"\W*|[\w.-]+\.(pdf|docx?|xlsx?))$", re.IGNORECASE)
DOC_LINK = re.compile(r"(\.(pdf|docx?|xlsx?)$|/media/\d+/download$)", re.IGNORECASE)


# ---------------------------------------------------------------- sources

def load_sources(path: Path) -> list[dict]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    sources = list(csv.DictReader(lines, delimiter="\t"))
    seen = set()
    for s in sources:
        if s["code"] in seen:
            raise ValueError(f"duplicate source code {s['code']!r} in {path.name}")
        seen.add(s["code"])
        if s["mode"] not in ("prefix", "paged", "months", "hub"):
            raise ValueError(f"{s['code']}: unknown mode {s['mode']!r}")
        if (s["mode"] == "months") != (MONTH in s["prefix"]):
            raise ValueError(f"{s['code']}: mode months and a {MONTH} prefix go together")
        if s["select"] not in ("all", "keywords"):
            raise ValueError(f"{s['code']}: unknown select {s['select']!r}")
    return sources


# ---------------------------------------------------------------- network

def fetch(url: str, *, timeout: int = TIMEOUT) -> str:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                # An id_ replay is the body as the site sent it, gzip and all.
                if body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
                text = body.decode("utf-8", "replace")
            # During an outage CDX answers 200 with its "Temporarily Offline"
            # HTML page (6 Nov 2026). Read as CDX text that is zero rows, and
            # it was cached as a finished, empty source. CDX text never
            # starts with "<"; a replay (id_) is HTML and is not checked.
            if url.startswith(CDX) and text.lstrip()[:1] == "<":
                raise RuntimeError("CDX answered an HTML page, not rows (Temporarily Offline?)")
            return text
        except urllib.error.HTTPError as exc:
            last = exc
            # 429 and 5xx are worth waiting out; other 4xx are not.
            if exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(8 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(6 * (attempt + 1))
    raise RuntimeError(f"{type(last).__name__}: {str(last)[:100]}")


def query(source: dict, **extra) -> str:
    params = [("url", source["prefix"]), ("matchType", "prefix"),
              ("collapse", "urlkey"), ("fl", ",".join(FIELDS))]
    if source["dated"] == "yes":
        params += [("from", FROM), ("to", TO)]
    params += [("filter", f) for f in source["filters"].split(";") if f]
    params += list(extra.items())
    return f"{CDX}?{urllib.parse.urlencode(params)}"


def parse_rows(body: str) -> list[dict]:
    """CDX text to rows. Raises if the body ends in a resume key.

    With showResumeKey, a response cut short by the limit ends with a blank
    line and a lone token. Anything else that is not a full row is ignored.
    """
    rows, lines = [], body.splitlines()
    for i, line in enumerate(lines):
        parts = line.split(" ")
        if len(parts) == len(FIELDS):
            rows.append(dict(zip(FIELDS, parts)))
        elif line.strip() and i >= len(lines) - 2:
            raise RuntimeError(f"hit the {ROW_CAP:,}-row cap; this source needs mode paged")
    return rows


def cdx_rows(url: str) -> list[dict]:
    """Rows for one CDX request, asking a second time before believing none."""
    rows = parse_rows(fetch(url))
    if not rows:
        time.sleep(EMPTY_PAUSE)
        rows = parse_rows(fetch(url))
    return rows


# ---------------------------------------------------------------- cache

def write_cache(path: Path, payload: dict) -> None:
    """Atomic: a run killed mid-write leaves the old entry or none, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(f".tmp{os.getpid()}")
    staged.write_text(json.dumps(payload), encoding="utf-8")
    staged.replace(path)


def read_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing or corrupt is simply not an entry
        return None


def is_done(entry: dict | None) -> bool:
    return bool(entry) and "error" not in entry and entry.get("method") == CACHE_METHOD


# ---------------------------------------------------------------- harvest

def harvest_prefix(source: dict, cache: Path) -> dict:
    path = cache / f"{source['code']}.json"
    entry = read_cache(path)
    if is_done(entry):
        return entry
    started = time.time()
    try:
        rows = cdx_rows(query(source, limit=ROW_CAP, showResumeKey="true"))
        entry = {"code": source["code"], "method": CACHE_METHOD, "rows": rows,
                 "seconds": round(time.time() - started, 1),
                 "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    except Exception as exc:  # noqa: BLE001
        entry = {"code": source["code"], "error": str(exc)[:160],
                 "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}
    write_cache(path, entry)
    return entry


def harvest_paged(source: dict, cache: Path, pause: float) -> dict:
    """Walk CDX index pages, one cached file per page.

    showNumPages is asked without fl (with one it answers "- - - - -") and
    ignores filters, so it counts pages of the whole prefix; the filters still
    apply to each page. A page that fails is recorded and retried next run,
    and the source reports failed until every page is in.
    """
    folder = cache / source["code"]
    meta_path = folder / "_pages.json"
    meta = read_cache(meta_path)
    if not meta:
        count_params = [("url", source["prefix"]), ("matchType", "prefix"),
                        ("showNumPages", "true")]
        try:
            text = fetch(f"{CDX}?{urllib.parse.urlencode(count_params)}", timeout=120).strip()
            meta = {"pages": int(text)}
        except Exception as exc:  # noqa: BLE001
            return {"code": source["code"], "error": f"showNumPages: {str(exc)[:120]}"}
        write_cache(meta_path, meta)
    failed = 0
    for page in range(meta["pages"]):
        path = folder / f"page-{page:05d}.json"
        if is_done(read_cache(path)):
            continue
        try:
            rows = cdx_rows(query(source, page=page))
            write_cache(path, {"method": CACHE_METHOD, "rows": rows})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            write_cache(path, {"error": str(exc)[:160]})
        if pause:
            time.sleep(pause)
    return load_paged(source, cache) | ({"error": f"{failed} of {meta['pages']} pages failed"}
                                        if failed else {})


def load_paged(source: dict, cache: Path) -> dict:
    folder = cache / source["code"]
    meta = read_cache(folder / "_pages.json")
    if not meta:
        return {"code": source["code"], "error": "never started"}
    rows, missing = [], 0
    for page in range(meta["pages"]):
        entry = read_cache(folder / f"page-{page:05d}.json")
        if is_done(entry):
            rows += entry["rows"]
        else:
            missing += 1
    out = {"code": source["code"], "method": CACHE_METHOD, "rows": rows,
           "pages": meta["pages"]}
    if missing:
        out["error"] = f"{missing} of {meta['pages']} pages not in"
    return out


def months() -> list[str]:
    """Every YYYY-MM of the period, for Drupal's /sites/default/files/YYYY-MM/ upload folders."""
    out, year, mon = [], int(FROM[:4]), int(FROM[4:])
    while f"{year}{mon:02d}" <= TO:
        out.append(f"{year}-{mon:02d}")
        year, mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
    return out


def harvest_months(source: dict, cache: Path, pause: float) -> dict:
    """One prefix query per upload month, one cached file per month.

    Drupal sites file each upload under the month it was made, so a whole
    files folder (SBA's is 125 CDX index pages) can be read a month at a time
    in small requests. Only the months of the period are asked for: a file
    uploaded later is outside it, whenever it was captured.
    """
    folder = cache / source["code"]
    for m in months():
        path = folder / f"month-{m}.json"
        if is_done(read_cache(path)):
            continue
        one = source | {"prefix": source["prefix"].replace(MONTH, m)}
        try:
            rows = cdx_rows(query(one, limit=ROW_CAP, showResumeKey="true"))
            write_cache(path, {"method": CACHE_METHOD, "rows": rows})
        except Exception as exc:  # noqa: BLE001
            write_cache(path, {"error": str(exc)[:160]})
        if pause:
            time.sleep(pause)
    return load_months(source, cache)


def load_months(source: dict, cache: Path) -> dict:
    folder = cache / source["code"]
    rows, missing = [], 0
    for m in months():
        entry = read_cache(folder / f"month-{m}.json")
        if is_done(entry):
            rows += entry["rows"]
        else:
            missing += 1
    out = {"code": source["code"], "method": CACHE_METHOD, "rows": rows, "months": len(months())}
    if missing:
        out["error"] = f"{missing} of {len(months())} months not in"
    return out


def site(host: str) -> str:
    """The registrable part of a host, near enough for .gov: www.rd.usda.gov -> usda.gov."""
    return ".".join(host.lower().split(":")[0].split(".")[-2:])


def link_text(inner: str) -> str:
    """An anchor's words, or "" when they say nothing (PDF, Download, a bare file name)."""
    words = " ".join(html_lib.unescape(TAG.sub(" ", inner)).split())
    words = re.sub(r"\s*[(\[]\s*(pdf|docx?|xlsx?)[^)\]]*[)\]]\s*$", "", words, flags=re.IGNORECASE)
    return "" if EMPTY_TEXT.match(words) else words[:300]


def doc_links(html: str, page_url: str) -> dict[str, str]:
    """Document links on one replayed page, made absolute, on the hub's own site only,
    each with its link text. Where a document is linked twice the longer text wins.
    """
    out: dict[str, str] = {}
    for href, inner in ANCHOR.findall(html):
        url = urllib.parse.urljoin(page_url, html_lib.unescape(href))
        # A replayed page can still carry Wayback's own prefix on its links.
        url = re.sub(r"^https?://web\.archive\.org/web/\d+(id_|im_|if_)?/", "", url)
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or site(parts.netloc) != site(urllib.parse.urlsplit(page_url).netloc):
            continue
        if DOC_LINK.search(parts.path):
            url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            text = link_text(inner)
            if len(text) >= len(out.get(url, "")):
                out[url] = text
    return out


def merge_links(into: dict[str, str], links: dict[str, str]) -> None:
    for url, text in links.items():
        if len(text) > len(into.get(url, "")) or url not in into:
            into[url] = text


def page_done(entry: dict | None) -> bool:
    # Pages read before link text was kept cached a list; read those again.
    return is_done(entry) and isinstance(entry.get("links"), dict)


def _hashed(folder: Path, kind: str, key: str) -> Path:
    return folder / f"{kind}-{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"


def hub_pages(source: dict) -> list[tuple[str, str]]:
    """(timestamp, url) of every capture to read: the hub once a month, each sub-page once.

    A sub-page under the hub's path is read at the capture nearest the end of
    the period, when it had gathered the most links; the hub itself is read
    every month, since documents came and went from it.
    """
    hub = source["prefix"].rstrip("/")
    monthly = [("url", hub), ("from", FROM), ("to", TO), ("filter", "statuscode:200"),
               ("collapse", "timestamp:6"), ("fl", "timestamp,original")]
    under = [("url", hub + "/"), ("matchType", "prefix"), ("from", FROM), ("to", TO),
             ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
             ("collapse", "urlkey"), ("fl", "timestamp,original")]
    pages = [tuple(ln.split(" ", 1)) for ln in fetch(f"{CDX}?{urllib.parse.urlencode(monthly)}").splitlines()
             if ln.count(" ") == 1]
    seen = set()
    for ln in fetch(f"{CDX}?{urllib.parse.urlencode(under)}").splitlines():
        if ln.count(" ") != 1:
            continue
        url = ln.split(" ", 1)[1]
        key = canonical(url)
        if key not in seen and well_formed(key) == key:
            seen.add(key)
            # The capture nearest the end can be the page's own 404, captured
            # after it came down; the first good capture is the fallback.
            pages.append((LAST_DAY + "000000", url, ln.split(" ", 1)[0]))
    return pages


def harvest_hub(source: dict, cache: Path, pause: float) -> dict:
    """Documents linked from an agency's COVID hub page and the pages under it.

    For agencies whose files share a folder with everything else and carry
    numbers or form codes for names (FDA /media/136316/download, OSHA3990.pdf),
    the folder cannot be read by keyword. The hub is the agency's own list of
    what it published about COVID, so what it linked to is the selection.
    Each linked document is then looked up for its first capture in the period;
    a document never captured in it is left out, not guessed at.
    """
    folder = cache / source["code"]
    meta_path = folder / "_pages.json"
    meta = read_cache(meta_path)
    if not meta:
        try:
            meta = {"pages": hub_pages(source)}
        except Exception as exc:  # noqa: BLE001
            return {"code": source["code"], "error": f"hub pages: {str(exc)[:120]}"}
        write_cache(meta_path, meta)
    links: dict[str, str] = {}
    for ts, url, *fallback in meta["pages"]:
        path = _hashed(folder, "page", ts + url)
        entry = read_cache(path)
        if not page_done(entry):
            entry = None
            for when in [ts, *fallback]:
                try:
                    html = fetch(f"https://web.archive.org/web/{when}id_/{url}", timeout=120)
                    entry = {"method": CACHE_METHOD, "read": when,
                             "links": dict(sorted(doc_links(html, url).items()))}
                    break
                except Exception as exc:  # noqa: BLE001
                    entry = {"error": str(exc)[:160]}
                    if not re.search(r"HTTP Error 40[34]", str(exc)):
                        break
            write_cache(path, entry)
            if pause:
                time.sleep(pause)
        merge_links(links, entry.get("links") or {})
    for url in sorted(links):
        path = _hashed(folder, "doc", canonical(url))
        if is_done(read_cache(path)):
            continue
        params = [("url", url), ("from", FROM), ("to", TO), ("filter", "statuscode:200"),
                  ("limit", "1"), ("fl", ",".join(FIELDS))]
        try:
            rows = cdx_rows(f"{CDX}?{urllib.parse.urlencode(params)}")
            write_cache(path, {"method": CACHE_METHOD, "url": url, "rows": rows[:1]})
        except Exception as exc:  # noqa: BLE001
            write_cache(path, {"url": url, "error": str(exc)[:160]})
        if pause:
            time.sleep(pause)
    return load_hub(source, cache)


def load_hub(source: dict, cache: Path) -> dict:
    folder = cache / source["code"]
    meta = read_cache(folder / "_pages.json")
    if not meta:
        return {"code": source["code"], "error": "never started"}
    links: dict[str, str] = {}
    pages_missing = 0
    for ts, url, *_ in meta["pages"]:
        entry = read_cache(_hashed(folder, "page", ts + url))
        if page_done(entry):
            merge_links(links, entry["links"])
        else:
            pages_missing += 1
    # A document captured before 2020 was not published for COVID: DOL's weekly
    # claims report is linked from its hub and predates the pandemic. The hub's
    # own first capture is no floor: Treasury's dates from April 2021, after a
    # year of CARES Act files it went on to link.
    rows, docs_missing, never, before = [], 0, 0, 0
    for url in sorted(links):
        entry = read_cache(_hashed(folder, "doc", canonical(url)))
        if not is_done(entry):
            docs_missing += 1
        elif not entry["rows"]:
            never += 1
        elif entry["rows"][0]["timestamp"] < HUB_FLOOR:
            before += 1
        else:
            rows.append(entry["rows"][0] | ({"link_text": links[url]} if links[url] else {}))
    out = {"code": source["code"], "method": CACHE_METHOD, "rows": rows, "pages": len(meta["pages"]),
           "linked": len(links), "not_captured_in_period": never, "before_hub": before}
    problems = [f"{n} of {total} {what} not in" for n, total, what in
                ((pages_missing, len(meta["pages"]), "pages"), (docs_missing, len(links), "documents")) if n]
    if problems:
        out["error"] = "; ".join(problems)
    return out


def load(source: dict, cache: Path) -> dict | None:
    if source["mode"] == "hub":
        return load_hub(source, cache) if (cache / source["code"]).exists() else None
    if source["mode"] == "months":
        return load_months(source, cache) if (cache / source["code"]).exists() else None
    if source["mode"] == "paged":
        return load_paged(source, cache) if (cache / source["code"]).exists() else None
    return read_cache(cache / f"{source['code']}.json")


# ---------------------------------------------------------------- cleaning

def slug(url: str) -> str:
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return urllib.parse.unquote(path.rsplit("/", 1)[-1]).lower()


def url_day(url: str) -> str | None:
    m = URL_DATE.search(url)
    return "".join(m.groups()) if m else None


def canonical(url: str) -> str:
    """One key per file: scheme, www, port, query string and case do not count."""
    key = url.split("#", 1)[0].split("?", 1)[0]
    key = re.sub(r"^https?://", "", key)
    key = re.sub(r"^www\.", "", key)
    key = re.sub(r":80(/|$)", r"\1", key)
    return urllib.parse.unquote(key).rstrip("/").lower()


def well_formed(key: str) -> str:
    """The address a mangled key was meant to be; the key itself if it is not mangled."""
    head, _, last = MARKUP_TAIL.sub("", key).rpartition("/")
    last = EXTENSION_TAIL.sub(r"\1", last).rstrip(" -.:")
    return f"{head}/{last}" if head else last


def clean(source: dict, rows: list[dict]) -> list[dict]:
    """Raw rows to one record per file, earliest capture kept.

    A URL that carries a date outside the period is dropped; that is how a 2019
    influenza-vaccine order falls out of the keyword match. The prefix's own
    index page is dropped too: it is a listing, not a document. So is a
    mangled link whose well-formed twin is present, or is that index page
    (see MARKUP_TAIL).
    """
    # A hub's documents live anywhere on the agency's site, not under the hub.
    base = "" if source["mode"] == "hub" else canonical("https://" + source["prefix"].split(MONTH, 1)[0])
    seen: dict[str, dict] = {}
    for row in rows:
        key = canonical(row["original"])
        if base and (key == base or not key.startswith(base.rstrip("/"))):
            continue
        if source["select"] == "keywords" and not KEYWORDS.search(slug(row["original"])):
            continue
        day = url_day(row["original"])
        if day and not FIRST_DAY <= day <= LAST_DAY:
            continue
        if key not in seen or row["timestamp"] < seen[key]["timestamp"]:
            seen[key] = row
    for key in [k for k in seen if well_formed(k) != k and (well_formed(k) in seen or well_formed(k) == base)]:
        del seen[key]
    return [{"source": source["code"], "agency": source["agency"], "key": k,
             "url_day": url_day(r["original"]), **r} for k, r in sorted(seen.items())]


# ---------------------------------------------------------------- main

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", type=Path, default=root / "build" / "sources.tsv")
    ap.add_argument("--cache", type=Path, default=root / "data" / "cdx-cache")
    ap.add_argument("--out", type=Path, default=root / "data" / "harvest.jsonl")
    ap.add_argument("--source", action="append", default=[],
                    help="run only this code (repeatable); needed for queued, blocked and paged sources")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between paged requests")
    ap.add_argument("--export-only", action="store_true",
                    help="re-clean the cache without touching the network")
    args = ap.parse_args()

    sources = load_sources(args.sources)
    known = {s["code"] for s in sources}
    unknown = set(args.source) - known
    if unknown:
        sys.exit(f"unknown source code(s): {', '.join(sorted(unknown))}")
    chosen = ([s for s in sources if s["code"] in args.source] if args.source else
              [s for s in sources if s["status"] in DEFAULT_STATUSES and s["mode"] != "paged"])

    todo = [] if args.export_only else [
        s for s in chosen if s["mode"] != "prefix" or not is_done(load(s, args.cache))]
    print(f"{len(chosen)} sources chosen, {len(todo)} to query "
          f"({len(chosen) - len(todo)} cached)", file=sys.stderr)

    def run(s):
        if s["mode"] == "paged":
            return harvest_paged(s, args.cache, args.pause)
        if s["mode"] == "months":
            return harvest_months(s, args.cache, args.pause)
        if s["mode"] == "hub":
            return harvest_hub(s, args.cache, args.pause)
        return harvest_prefix(s, args.cache)

    failed = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, s): s for s in todo}
        for fut in cf.as_completed(futures):
            s, entry = futures[fut], fut.result()
            if "error" in entry:
                failed += 1
                print(f"  {s['code']:<18} FAILED  {entry['error']}", file=sys.stderr, flush=True)
            else:
                print(f"  {s['code']:<18} {len(entry['rows']):>7,} rows  "
                      f"{entry.get('seconds', '')}s", file=sys.stderr, flush=True)

    # Export everything cached, not only what was chosen, so a one-source run
    # never rewrites the dataset as that one source.
    total = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n{'source':<18} {'raw':>8} {'kept':>7}  handoff", file=sys.stderr)
    with args.out.open("w", encoding="utf-8") as sink:
        for s in sources:
            entry = load(s, args.cache)
            if not entry:
                continue
            if "error" in entry and not entry.get("rows"):
                print(f"{s['code']:<18} {'FAILED':>8}          {entry['error'][:60]}", file=sys.stderr)
                continue
            kept = clean(s, entry["rows"])
            flag = "  PARTIAL: " + entry["error"] if "error" in entry else ""
            print(f"{s['code']:<18} {len(entry['rows']):>8,} {len(kept):>7,}  {s['handoff']}{flag}",
                  file=sys.stderr)
            for rec in kept:
                sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += len(kept)
    print(f"\nwrote {total:,} records to {args.out}", file=sys.stderr)
    if failed:
        print(f"{failed} source(s) failed; re-run to retry only those", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
