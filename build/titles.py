#!/usr/bin/env python3
"""Give file-folder documents the title the document gives itself.

Documents found by folder carry no link text, so build_site.py titles them
from the file name: "Section 74", "Covid eidl targeted advance 4.29.2021 rev
5.5.2021 final 508". This step reads each such PDF from its Wayback capture
and takes, in order:

  1. the PDF's own Title field, when it names the document. It often does
     not: "Consolidated-Forecasts-Hosp-2023-03-13" is the file name again,
     "Microsoft Word - memo.docx" is the editor's, and CDC's fact sheets say
     only "Coronavirus disease 2019 (COVID-19) Factsheet";
  2. otherwise the largest type on the first page, its heading. A heading
     that is a page number, a form code or a date is passed over for the next
     size down.

Neither is a guess: a document where both fail keeps its file-name title,
and build_site.py marks it as one. Tried on 30 sampled PDFs, 8 Nov 2026:
about three in four of those Wayback served gave a real title.

Hub documents keep their link text, which the agency wrote to name them,
unless it names only a format: GAO links every report as "Full Report (14
pages)" or "Highlights Page", so those are read here too (--source gao-covid).

Results are cached in data/titles-cache.jsonl, one line per attempt, last line
wins (except that an error never replaces a result), so a run can stop at any point and resume. Statuses:
  found     a title, with "from": "meta" or "page"
  none      the PDF was read and names itself nowhere usable
  error     the request or the parse failed; retried on the next run
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import build_site  # noqa: E402

CACHE = ROOT / "data" / "titles-cache.jsonl"
AGENT = "federal-pandemic-record/1.0 (+https://github.com/internetarchivecanada/federal-pandemic-record-covid19)"
MAX_BYTES = 40 * 1024 * 1024

# Titles that name a template or a series, not the document.
GENERIC = re.compile(
    r"^(untitled|title|document\d*|slide \d+|powerpoint presentation|presentation|"
    r"coronavirus disease 2019 \(covid-19\)( factsheet| fact sheet)?|covid-19|"
    r"fact ?sheet|memorandum|word document|pdf|cover page|draft|r graphics output|see schedule|"
    # COVIDView's weekly issues carry the name of their first chart.
    r"pneumonia and influenza mortality)$", re.IGNORECASE)
# A heading that is a table's first column: CDC's county data run "National",
# "Alabama", "Autauga County, Alabama" together.
TABLE = re.compile(r"alabama\W*(autauga|alaska)|(county, [a-z ]+){3}|(new deaths.*){3}", re.IGNORECASE)
# A video transcript's subtitle cues: "00:00:08,189 --> 00:00:08,910".
CUES = re.compile(r"\d\d:\d\d:\d\d|-->")
EDITOR = re.compile(r"^(microsoft (word|powerpoint|excel) - |adobe |untitled)", re.IGNORECASE)
FILEISH = re.compile(r"\.(docx?|pdf|pptx?|xlsx?|indd|ai)\b|^[\w.-]+$", re.IGNORECASE)
# A heading made only of these is a page furniture, not a title.
FURNITURE = re.compile(
    r"^(page )?\d+( of \d+)?$|^[\d\s./:-]+$|^(cs|omb|cdc|form)\s*[\w-]*\d[\w-]*$|"
    r"^\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}|^www\.|^https?://", re.IGNORECASE)


def needs_title(d: dict) -> bool:
    """A PDF that build_site.py would title from its file name."""
    return (d["mimetype"] == "application/pdf"
            and build_site.hub_title(d) == build_site.title_from(d["key"]))


# A footer address run into the heading: "Examples of Triage Algorithmscdc.gov/coronavirus".
WEB_ADDRESS = re.compile(r"(https?://)?(www\.)?(cdc|hhs|fda|cms|medicare|sba|fema|osha|nih|dhs|cisa|"
                         r"treasury|va|ed|usda|dol|whitehouse|coronavirus|covid|vaccines)\.gov(/\S*)?",
                         re.IGNORECASE)
# File-name words that say nothing about the document: workflow, accessibility, dates.
NOISE = {"final", "draft", "rev", "revised", "public", "508", "for", "transcription", "add", "logo",
         "web", "print", "clean", "updated", "update", "v", "copy", "eng", "en", "fs", "and", "the", "of"}
MONTH_DAY_YEAR = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2},\s+20\d\d\b", re.IGNORECASE)


# CDC stamped retired files "This PDF is no longer being updated. Please go to ...".
RETIRED = re.compile(r"(this )?pdf ?is no longer being updated.*$", re.IGNORECASE)
# Text a font maps to no characters comes out as glyph ids: "/gid01088/gid01092".
GLYPH_IDS = re.compile(r"/gid\d+")


def tidy(text: str) -> str:
    text = WEB_ADDRESS.sub(" ", RETIRED.sub("", text.replace("\u00ad", "")))
    text = re.sub(r"\s+", " ", text).strip(" -\u2013\u2014|:;,")
    return text[:200].rsplit(" ", 1)[0] + "\u2026" if len(text) > 200 else text


def slug_words(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", build_site.title_from(key).lower())


def usable(title: str, key: str) -> bool:
    """A title that names the document: words, not its file name or a template's."""
    t = tidy(title)
    letters = sum(c.isalpha() for c in t)
    if letters < 6 or len(t.split()) < 2 or len(re.findall(r"[^\W\d_]{3,}", t)) < 2:
        return False
    if GENERIC.match(t) or EDITOR.match(t) or FURNITURE.match(t) or GLYPH_IDS.search(t) \
            or TABLE.search(t) or CUES.search(t):
        return False
    if " " not in t.strip() or (FILEISH.search(t) and not re.search(r"\s\w+\s", t)):
        return False
    return re.sub(r"[^a-z0-9]", "", t.lower()) != slug_words(key)


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 1} - NOISE


def says_less(title: str, key: str) -> bool:
    """The file name already holds every word of the title and two real words more.

    The White House's "Budgetary impact analysis for executive order entitled
    protecting the federal workforce and requiring mask wearing" carries the
    order's name as its Title field; the file name is the better title.
    """
    named, own = content_words(build_site.title_from(key)), content_words(title)
    return bool(own) and own <= named and len(named - own) >= 2 and not re.search(r"\d", build_site.title_from(key))


def page_heading(page) -> str:
    """The first page's largest type, top to bottom, skipping page furniture."""
    runs: list[tuple[float, float, str]] = []

    def visit(text, cm, tm, font, size):
        if text and text.strip():
            scale = (abs(tm[3]) or abs(tm[0]) or 1) * (abs(cm[3]) or abs(cm[0]) or 1)
            runs.append((round(size * scale, 1), -(tm[5] * (cm[3] or 1) + cm[5]), text))

    page.extract_text(visitor_text=visit)
    for size in sorted({s for s, _, _ in runs}, reverse=True)[:4]:
        text = tidy(" ".join(heading_lines([(y, t) for s, y, t in runs if s == size], size)))
        if sum(c.isalpha() for c in text) >= 6:
            return text
    return ""


def heading_lines(runs: list[tuple[float, str]], size: float) -> list[str]:
    """The first block of lines in one type size, top down.

    Runs at one height are one line, joined as they are; lines are joined with
    a space ("Coronavirus Disease 2019 (COVID-19)" / "Treatment Guidelines").
    A gap of more than twice the type size ends the title: below it, the same
    size is the next heading (COVIDView's "Virus", "Severe Disease").
    """
    rows: dict[float, list[str]] = {}
    for y, text in runs:
        rows.setdefault(round(y), []).append(text)
    lines, last = [], None
    for y in sorted(rows):
        if last is not None and y - last > 2 * size and lines:
            break
        for line in re.split(r"\n", "".join(rows[y])):
            if tidy(line) and not FURNITURE.match(tidy(line)):
                lines.append(tidy(line))
        last = y
    return lines


def title_of(data: bytes, key: str) -> dict:
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = pypdf.PdfReader(io.BytesIO(data))
    meta = tidy(str((reader.metadata or {}).get("/Title") or ""))
    first = reader.pages[0] if reader.pages else None
    text = (first.extract_text() or "") if first else ""
    when = MONTH_DAY_YEAR.search(text)
    found = None
    if usable(meta, key):
        found = {"status": "found", "from": "meta", "title": meta}
    elif first:
        heading = page_heading(first)
        # Longer than a heading: the largest type was the body, as on a PSA script.
        if usable(heading, key) and len(heading.split()) <= 20:
            found = {"status": "found", "from": "page", "title": heading, "v": 2}
    if not found or says_less(found["title"], key):
        return {"status": "none"}
    # A series titles every issue alike ("COVID-19 Press Briefing"); the date
    # printed on the first page is kept so build_site.py can tell them apart.
    return found | ({"date": " ".join(when.group(0).split())} if when else {})


def fetch(d: dict) -> bytes:
    url = f"https://web.archive.org/web/{d['timestamp']}id_/{d['original']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=180) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("larger than 40 MB")
    if data.startswith(b"\x1f\x8b"):  # a capture stored gzipped, as served
        data = gzip.decompress(data)
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF: " + data[:40].decode("latin-1", "replace"))
    return data


def load_cache(path: Path = CACHE) -> dict[str, dict]:
    return build_site.load_titles(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--limit", type=int, help="read at most this many documents")
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between requests")
    ap.add_argument("--source", action="append", default=[], help="read only this source (repeatable)")
    args = ap.parse_args()

    documents = [json.loads(line) for line in (ROOT / "data" / "documents.jsonl").read_text().splitlines()]
    # Only the copy build_site.py keeps: a file two sources found is read once.
    documents, _ = build_site.one_per_file(documents)
    documents = [d for d in documents if needs_title(d) and build_site.entry(d, {})
                 and (not args.source or d["source"] in args.source)]
    cache = load_cache()
    # A title found before a rule was added is read again if the rule now rejects it.
    todo = [d for d in documents if cache.get(d["key"], {}).get("status") in (None, "error")
            or (cache[d["key"]]["status"] == "found" and not usable(cache[d["key"]]["title"], d["key"]))
            # Headings read before heading_lines() ran their lines together.
            or (cache[d["key"]].get("from") == "page" and cache[d["key"]].get("v", 1) < 2)]
    print(f"{len(documents):,} PDFs in the corpus titled from file names, {len(todo):,} to read",
          file=sys.stderr)
    with CACHE.open("a", encoding="utf-8") as sink:
        for n, d in enumerate(todo[: args.limit], 1):
            try:
                rec = title_of(fetch(d), d["key"])
            except Exception as exc:  # noqa: BLE001
                rec = {"status": "error", "error": str(exc)[:160]}
            rec = {"key": d["key"]} | rec
            sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
            sink.flush()
            if n % 50 == 0:
                print(f"  {n:,} read", file=sys.stderr, flush=True)
            time.sleep(args.pause)
    counts: dict[str, int] = {}
    for r in load_cache().values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("  " + ", ".join(f"{k} {v:,}" for k, v in sorted(counts.items())), file=sys.stderr)


if __name__ == "__main__":
    main()
