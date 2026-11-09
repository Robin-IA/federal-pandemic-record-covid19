#!/usr/bin/env python3
"""Build the explorer's data, corpus.js, from the pipeline's outputs.

Reads data/documents.jsonl (languages.py), data/dates.jsonl (dates.py),
data/titles-cache.jsonl (titles.py, if present) and data/pages-monthly.txt, and writes corpus.js beside index.html at the
repository root, where GitHub Pages serves it.

What goes in follows the corpus rule: every document opens as a document.
  - Agency file folders: PDFs and Office files only. Images, stylesheets,
    scripts and XML in the same folders are left out.
  - White House: the issuance pages themselves. Trump items take the first
    capture of their www.whitehouse.gov address from dates.py, and only those
    inside the period; Biden items carry their day in the URL.
  - PHE: only the COVID declarations. The same folder holds every emergency
    since 2010 (hurricanes, opioids, Zika). phe.gov moved to aspr.hhs.gov in
    2022, which re-hosted the earlier declarations, so each declaration is
    kept once, from whichever address was captured first.

Each Wayback link points at the capture the date came from, so the link
replays the document as it stood when it was first seen.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import harvest  # noqa: E402
import languages  # noqa: E402

FILE_TYPES = {
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word",
    "application/msword": "Word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel",
    "application/vnd.ms-excel": "Excel",
}
ISSUANCE_SOURCES = {"wht-actions", "wht-briefings", "whb-actions"}
# A declaration or renewal: covid19-21apr2020, covdi-15oct21, 2019-ncov. Not
# "letter-to-governors-on-the-covid-19-response", in the same folder.
PHE_COVID = re.compile(r"/pages/(covid|covdi|2019-ncov)[^/]*\.aspx$")
PHE_SOURCES = {"phe", "phe-aspr"}
# The archive mirrors were captured from January 2021, so a first capture there
# says nothing about when a file was issued. WordPress files each upload under
# the month it was made: /wp-content/uploads/2020/03/.
UPLOAD_SOURCES = {"wh-uploads-trump", "wh-uploads-biden"}
UPLOAD_MONTH = re.compile(r"/uploads/(20\d\d)/(\d\d)/")
# Named like a COVID renewal but not one: covid19-7april2021 renews the opioid
# crisis emergency (read on its 7 April 2021 capture). The COVID renewal that
# month is covid-15april2021.
PHE_NOT_COVID = {"covid19-7april2021.aspx"}

ACTION_TYPES = [("executive-order", "Executive order"), ("proclamation", "Proclamation"),
                ("memorandum", "Memorandum"), ("determination", "Determination"),
                ("notice", "Notice"), ("letter", "Letter"), ("message", "Message")]
BRIEFING_TYPES = [("remarks", "Remarks"), ("statement", "Statement"), ("press-briefing", "Press briefing"),
                  ("briefing", "Press briefing"), ("readout", "Readout"), ("fact-sheet", "Fact sheet"),
                  ("letter", "Letter"), ("message", "Message"), ("proclamation", "Proclamation"),
                  ("executive-order", "Executive order"), ("memorandum", "Memorandum")]


def title_from(key: str) -> str:
    slug = urllib.parse.unquote(key.rstrip("/").rsplit("/", 1)[-1])
    slug = re.sub(r"\.(pdf|docx?|xlsx?|html?|aspx)$", "", slug, flags=re.I)
    words = re.sub(r"[-_]+", " ", slug).strip()
    return words[:1].upper() + words[1:] if words else key


LANGUAGE_WORDS = set(languages.NAMES) | languages.QUALIFIERS | {"language", "version", "creole", "-", "/"}
URLISH = re.compile(r"^(https?://|www\.)|\.(gov|com|org)/", re.IGNORECASE)
MEDIA_ID = re.compile(r"/media/(\d+)/download$")
# Link text that names a format, not a document: GAO's report pages link every
# file as "Full Report (14 pages)", "Highlights Page (1 page)", "Accessible PDF".
FORMAT_ONLY = re.compile(
    r"^(full report|highlights( page)?|view (the )?report|view a summary|accessible (pdf|text|version)|"
    r"download print version)( \(\d+ pages?\))?$", re.IGNORECASE)


def one_per_file(documents: list[dict]) -> tuple[list[dict], int]:
    """One document per file across sources, the earliest capture kept.

    Sources overlap: Treasury's two hubs link the same files, hhs-files holds
    hhs-covid, cdc-ncov holds cdc-dl. A link text wins over none, since the
    keyword sources have none to give.
    """
    best: dict[str, dict] = {}
    for d in documents:
        held = best.get(d["key"])
        when = d.get("first_ts") or d["timestamp"]
        if held is None or (when, not d.get("link_text")) < \
                (held.get("first_ts") or held["timestamp"], not held.get("link_text")):
            best[d["key"]] = d
    kept = [d for d in documents if best[d["key"]] is d]
    return kept, len(documents) - len(kept)


def hub_title(d: dict) -> str:
    """A hub document's title: the words that linked to it, where they name it.

    A translation's link often says only its language ("French Creole"), and a
    few links are their own address; neither names the document. FDA's files
    are /media/<id>/download, so with no words the id is the most there is.
    """
    text = d.get("link_text", "")
    words = re.findall(r"[\w/-]+", text.lower())
    if text and not URLISH.search(text) and not FORMAT_ONLY.match(text) and not set(words) <= LANGUAGE_WORDS:
        return text
    m = MEDIA_ID.search(d["key"])
    return f"{d['agency']} document {m.group(1)}" if m else title_from(d["key"])


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SLUG_DATE = re.compile(r"(\d{1,2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(\d{2,4})")


def phe_title(slug: str) -> str:
    """phe.gov names each renewal by its date: covid19-21apr2020, covdi-15oct21."""
    m = SLUG_DATE.search(slug.lower())
    if not m:
        return "Determination that a public health emergency exists: 2019 novel coronavirus"
    day, mon, year = int(m.group(1)), m.group(2), m.group(3)
    year = int(year) + (2000 if len(year) == 2 else 0)
    return f"Renewal of the COVID-19 public health emergency, {day} {mon.title()} {year}"


def kind(slug: str, table: list[tuple[str, str]], default: str) -> str:
    return next((label for word, label in table if word in slug), default)


def wayback(ts: str, url: str) -> str:
    return f"https://web.archive.org/web/{ts}/{url}"


def month(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}"


def in_period(ts: str) -> bool:
    return harvest.FIRST_DAY <= ts[:8] <= harvest.LAST_DAY


def file_title(d: dict, titles: dict[str, dict]) -> dict:
    """The title fields for a file: the document's own title where titles.py found one.

    "fn" marks a title that is still the file name, so the page can say so.
    "date" is the date printed on the first page, kept only to tell apart a
    series whose issues share a title; one_title_each() uses it and drops it.
    """
    found = titles.get(d["key"], {})
    if found.get("status") == "found":
        return {"title": found["title"]} | ({"date": " ".join(found["date"].split())} if found.get("date") else {})
    title = hub_title(d)
    return {"title": title} | ({"fn": 1} if title == title_from(d["key"]) else {})


def one_title_each(docs: list[dict]) -> list[dict]:
    """Add the printed date to a title its agency uses more than once.

    SBA's "Disaster Assistance Update" and the White House's "COVID-19 Press
    Briefing" title every issue alike.
    """
    seen = Counter((d["agency"], d["title"]) for d in docs)
    for d in docs:
        when = d.pop("date", None)
        if when and seen[(d["agency"], d["title"])] > 1 and when not in d["title"]:
            d["title"] = f"{d['title']}, {when}"
    return docs


def entry(d: dict, dates: dict[str, dict], titles: dict[str, dict] | None = None) -> dict | None:
    """One document as the page shows it, or None if it is not in the corpus."""
    source, slug = d["source"], d["key"].rstrip("/").rsplit("/", 1)[-1]
    base = {"agency": d["agency"], "title": hub_title(d), "langs": d["languages"]}
    filed = base | file_title(d, titles or {})
    if source == "wht-actions" or source == "wht-briefings":
        found = dates.get(d["key"], {})
        if found.get("status") != "found" or not found.get("in_period"):
            return None
        table = ACTION_TYPES if source == "wht-actions" else BRIEFING_TYPES
        default = "Presidential action" if source == "wht-actions" else "Briefing room"
        return base | {"type": kind(slug, table, default), "month": month(found["first_ts"]),
                       "url": wayback(found["first_ts"], found["live_url"])}
    if source == "whb-actions":
        day = d["url_day"]
        if not day or not in_period(day):
            return None
        return base | {"type": kind(slug, ACTION_TYPES, "Presidential action"), "month": month(day),
                       "day": f"{day[:4]}-{day[4:6]}-{day[6:]}", "url": wayback(d["timestamp"], d["original"])}
    if source in UPLOAD_SOURCES:
        m = UPLOAD_MONTH.search(d["key"])
        if d["mimetype"] not in FILE_TYPES or not m or not in_period(m.group(1) + m.group(2) + "01"):
            return None
        return filed | {"type": FILE_TYPES[d["mimetype"]], "month": f"{m.group(1)}-{m.group(2)}",
                       "url": wayback(d["timestamp"], d["original"])}
    if source in PHE_SOURCES:
        if not PHE_COVID.search(d["key"]) or slug in PHE_NOT_COVID or not in_period(d["timestamp"]):
            return None
        return base | {"title": phe_title(slug), "type": "PHE declaration", "month": month(d["timestamp"]),
                       "url": wayback(d["timestamp"], d["original"])}
    if d["mimetype"] not in FILE_TYPES or not in_period(d["first_ts"]):
        return None
    return filed | {"type": FILE_TYPES[d["mimetype"]], "month": month(d["first_ts"]),
                   "url": wayback(d["timestamp"], d["original"])}


def pages(path: Path) -> list[dict]:
    out, lines = [], path.read_text().splitlines()
    for head, body in zip(lines[0::2], lines[1::2]):
        key, url, versions, first, last = head.lstrip("#").split("|")
        months = []
        for cell in body.split():
            ym, ts, v, kb = (cell.split(":") + [""])[:4]
            months.append({"m": f"{ym[:4]}-{ym[4:]}", "ts": ym + ts, "v": int(v),
                           "kb": float(kb) if kb else None})
        peak = max((x["kb"] for x in months if x["kb"]), default=0)
        for x in months:
            x["ph"] = bool(x["kb"] is not None and peak and x["kb"] < 0.15 * peak)
        out.append({"key": key, "url": url, "versions": int(versions),
                    "first": first, "last": last, "peak": peak, "months": months})
    return out


def one_per_declaration(docs: list[dict]) -> list[dict]:
    """Each PHE declaration once: the copy with the earliest capture."""
    first: dict[str, dict] = {}
    for d in docs:
        if d["type"] == "PHE declaration":
            seen = first.get(d["title"])
            # Wayback links differ first at the timestamp, so they sort by capture time.
            if seen is None or d["url"] < seen["url"]:
                first[d["title"]] = d
    return [d for d in docs if d["type"] != "PHE declaration" or first[d["title"]] is d]


def main() -> None:
    documents = [json.loads(line) for line in (ROOT / "data" / "documents.jsonl").read_text().splitlines()]
    dates = {json.loads(line)["key"]: json.loads(line)
             for line in (ROOT / "data" / "dates.jsonl").read_text().splitlines()}

    cache = ROOT / "data" / "titles-cache.jsonl"
    titles = {}
    if cache.exists():
        titles = {(r := json.loads(line))["key"]: r for line in cache.read_text(encoding="utf-8").splitlines() if line}

    docs, left_out = [], Counter()
    documents, repeats = one_per_file(documents)
    if repeats:
        left_out["same file in another source"] = repeats
    for d in documents:
        e = entry(d, dates, titles)
        if e:
            docs.append(e)
        else:
            left_out[d["source"]] += 1
    docs = one_title_each(one_per_declaration(docs))
    docs.sort(key=lambda d: (d["month"], d["agency"], d["title"]))

    fetched = max(json.loads(p.read_text())["fetched"] for p in (ROOT / "data" / "cdx-cache").glob("*.json"))
    harvested = time.strptime(fetched[:10], "%Y-%m-%d")
    cdc = [d for d in documents if d["source"] == "cdc-dl"]
    stats = {"built": time.strftime("%-d %B %Y"), "harvested": time.strftime("%-d %B %Y", harvested),
             "cdc_files": sum(len(d["members"]) for d in cdc), "cdc_docs": len(cdc),
             "by_agency": Counter(d["agency"] for d in docs)}
    data = {"docs": docs, "pages": pages(ROOT / "data" / "pages-monthly.txt"), "stats": stats}
    out = ROOT / "corpus.js"
    out.write_text("window.CORPUS=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n",
                   encoding="utf-8")

    named = sum(1 for d in docs if d["type"] in FILE_TYPES.values() and not d.get("fn"))
    print(f"  file titles: {named:,} named, {sum(1 for d in docs if d.get('fn')):,} still file names",
          file=sys.stderr)
    for agency, n in stats["by_agency"].most_common():
        print(f"  {agency:<22} {n:>6,}", file=sys.stderr)
    print(f"  {'left out':<22} " + ", ".join(f"{s} {n}" for s, n in left_out.most_common()), file=sys.stderr)
    print(f"wrote {len(docs):,} documents to {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
