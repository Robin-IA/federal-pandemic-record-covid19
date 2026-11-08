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

Hub documents keep their link text, which the agency wrote to name them.

Results are cached in data/titles-cache.jsonl, one line per attempt, last line
wins, so a run can stop at any point and resume. Statuses:
  found     a title, with "from": "meta" or "page"
  none      the PDF was read and names itself nowhere usable
  error     the request or the parse failed; retried on the next run
"""

from __future__ import annotations

import argparse
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
    r"fact ?sheet|memorandum|word document|pdf|cover page|draft|r graphics output)$", re.IGNORECASE)
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
    if GENERIC.match(t) or EDITOR.match(t) or FURNITURE.match(t) or GLYPH_IDS.search(t):
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
        parts = [t for s, _, t in sorted((r for r in runs if r[0] == size), key=lambda r: r[1])]
        lines = [tidy(x) for x in re.split(r"\n", "".join(parts)) if tidy(x)]
        lines = [x for x in lines if not FURNITURE.match(x)]
        text = tidy(" ".join(lines))
        if sum(c.isalpha() for c in text) >= 6:
            return text
    return ""


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
            found = {"status": "found", "from": "page", "title": heading}
    if not found or says_less(found["title"], key):
        return {"status": "none"}
    # A series titles every issue alike ("COVID-19 Press Briefing"); the date
    # printed on the first page is kept so build_site.py can tell them apart.
    return found | ({"date": when.group(0)} if when else {})


def fetch(d: dict) -> bytes:
    url = f"https://web.archive.org/web/{d['timestamp']}id_/{d['original']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=180) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("larger than 40 MB")
    if not data.startswith(b"%PDF"):
        raise ValueError("not a PDF: " + data[:40].decode("latin-1", "replace"))
    return data


def load_cache(path: Path = CACHE) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {(r := json.loads(line))["key"]: r for line in path.read_text(encoding="utf-8").splitlines() if line}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--limit", type=int, help="read at most this many documents")
    ap.add_argument("--pause", type=float, default=2.0, help="seconds between requests")
    args = ap.parse_args()

    documents = [json.loads(line) for line in (ROOT / "data" / "documents.jsonl").read_text().splitlines()]
    documents = [d for d in documents if needs_title(d) and build_site.entry(d, {})]
    cache = load_cache()
    todo = [d for d in documents if cache.get(d["key"], {}).get("status") in (None, "error")]
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
