#!/usr/bin/env python3
"""Measure key pages month by month for the "Pages over time" view.

Reads build/pages.tsv (key, url) and writes data/pages-monthly.txt in the
format the 27 original pages were measured in (Cowork survey, 22-25 Oct 2026):

    #key|url|versions|first_ts|last_ts
    YYYYMM:DDhhmmss:versions_that_month:median_KB ...

From one exact-URL CDX request per page, statuscode 200, Dec 2019 - May 2023:
only the captures where the digest changed are counted, as collapse=digest
would give them (checked against covidtests.gov's original line, 8 Nov 2026):
  - the month's cell starts at its first changed capture, whose link replays it;
  - "versions" is how many changed captures fell in the month. Digest change
    is not content change: CDC pages carry dynamic markup;
  - median KB (1,000 bytes) is the median compressed length of those captures, which is
    what shows a moved page shrinking to a ~1 KB redirect.

A page already in the file is kept as measured unless --remeasure names it,
so the original 27 are not silently re-dated.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import harvest  # noqa: E402

LIST = ROOT / "build" / "pages.tsv"
OUT = ROOT / "data" / "pages-monthly.txt"


def load_list(path: Path = LIST) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            key, url = line.split("\t")[:2]
            rows.append((key, url))
    return rows


def load_measured(path: Path = OUT) -> dict[str, tuple[str, str]]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    return {head.lstrip("#").split("|", 1)[0]: (head, body) for head, body in zip(lines[0::2], lines[1::2])}


def measure(key: str, url: str, captures: list[tuple[str, str, int]]) -> tuple[str, str] | None:
    """The two lines for one page from its (timestamp, digest, length) captures, in time order."""
    if not captures:
        return None
    # As CDX's collapse=digest: only the captures where the page changed.
    changes = [c for i, c in enumerate(captures) if i == 0 or c[1] != captures[i - 1][1]]
    months: dict[str, dict] = {}
    for ts, _digest, length in changes:
        m = months.setdefault(ts[:6], {"first": ts, "v": 0, "kb": []})
        m["v"] += 1
        m["kb"].append(length / 1000)
    head = f"#{key}|{url}|{len(changes)}|{changes[0][0]}|{changes[-1][0]}"
    cells = []
    for ym, m in months.items():
        kb = round(statistics.median(m["kb"]), 1)
        cells.append(f"{ym}:{m['first'][6:]}:{m['v']}:{kb:g}")
    return head, " ".join(cells)


def captures_of(url: str) -> list[tuple[str, str, int]]:
    params = [("url", url), ("from", harvest.FROM), ("to", harvest.TO), ("filter", "statuscode:200"),
              ("fl", "timestamp,digest,length")]
    out = []
    for line in harvest.fetch(f"{harvest.CDX}?{urllib.parse.urlencode(params)}").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
            out.append((parts[0], parts[1], int(parts[2])))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--remeasure", nargs="*", default=[], help="keys to measure again")
    ap.add_argument("--print", dest="show", help="measure one key and print it, writing nothing")
    args = ap.parse_args()

    listed, measured = load_list(), load_measured()
    if args.show:
        url = dict(listed)[args.show]
        print("\n".join(measure(args.show, url, captures_of(url)) or ["no captures"]))
        return
    for key, url in listed:
        if key in measured and key not in args.remeasure:
            continue
        try:
            lines = measure(key, url, captures_of(url))
        except Exception as exc:  # noqa: BLE001
            print(f"  {key:<20} FAILED  {str(exc)[:80]}", file=sys.stderr)
            continue
        if lines:
            measured[key] = lines
            print(f"  {key:<20} {lines[0].split('|')[2]:>6} versions", file=sys.stderr)
        else:
            print(f"  {key:<20} no captures in the period", file=sys.stderr)
        time.sleep(3)
    order = [k for k, _ in listed if k in measured] + [k for k in measured if k not in dict(listed)]
    OUT.write_text("".join(f"{measured[k][0]}\n{measured[k][1]}\n" for k in order), encoding="utf-8")
    print(f"wrote {len(order)} pages to {OUT.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
