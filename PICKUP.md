# The Federal Pandemic Record: pickup

Hand this file to Claude Code and say "start the work". It records what a
Cowork session found on 22–25 October 2026 before moving here, so nothing
below needs to be re-surveyed. `data/pages-monthly.txt` is the page-timeline
file it refers to.

## Where the code lives (since 6 November 2026)

Develop at **`Robin-IA/federal-pandemic-record-covid19`** (public). The
`internetarchivecanada` repository is its mirror: it gets `main` with
`git push canada main` after each merge, and serves the explorer on GitHub
Pages. All 18 branches were copied across on 6 Nov 2026. PRs #1–#43 and the
issues filed until then stay on the mirror, because GitHub cannot move issues
from an organization to a personal account. Never commit or open a pull
request on the mirror.

## Since the handoff (26 October 2026)

- Repository created: `internetarchivecanada/federal-pandemic-record-covid19`,
  **public** (Robin's decision). Steps 1 and 2 of "Start here" are done: CDX and
  `advancedsearch.php` both answer directly from Robin's Mac over https.
- Archive-It partner 593 is corrected below.
- **Step 3 is done.** `build/sources.tsv` holds the table below as data, and
  `build/harvest.py` re-ran the 11 sources marked harvested, partial or retry
  in about 3 minutes, 26 Oct 2026. Run it again with `python3 build/harvest.py`.
  Raw rows match the survey exactly wherever it gave a count: CDC 2,550, ED
  134, NIH 289, HHS `covid*` 97, DHS 15, CISA 6. CDC folds to exactly the
  survey's 1,990 distinct files, and Trump actions give exactly 65 COVID.
  PHE, which failed twice in the survey, returned 215 rows and 124 distinct
  files. HHS `coronavirus*` returned 4. After cleaning: **2,824 records** in
  `data/harvest.jsonl`. Differences, recorded but not resolved:
  - ED keeps 29 of 134 rows: most are the same PDF with `utm_` query strings.
  - Biden actions: 44, all dated in the URL from 20 Jan 2021 to 9 May 2023,
    inside the period. The survey said 42 in range, without saying which cutoff
    it used.
  - Trump briefings: 208 against the survey's 195. The keyword list catches
    false positives such as "reopening the Washington Monument", so the list
    needs a read by hand either way.
- **Step 4 is done.** `build/dates.py` looked up the first status-200 capture
  of each of the 273 Trump White House items (65 actions, 208 briefings) at its
  `www.whitehouse.gov` address, 26 Oct 2026: about 16 minutes on 2 workers, 9
  network failures, all recovered on a re-run. Two items checked by hand: the national-emergency
  proclamation is first captured 13 Mar 2020 and "15 Days to Slow the Spread"
  16 Mar 2020, their issue dates. Result: **231 in the period**, peaking at
  71 in March 2020. **35 outside the period**: keyword false positives,
  dropping out on date as intended. Examples: the 2019 influenza-vaccine order,
  2017-2019 Defense Production Act determinations, and unrelated task forces.
  Seven had no capture on that run; both causes are now fixed (next item).
- **Mangled links are dropped, and an empty CDX answer is asked twice**
  (26 Oct 2026). Of the 7 empty lookups, 4 were mirror URLs mangled by whatever
  cited them (a stray `]`, a trailing `-`, `-.5`). Looking across every source
  found 15 such records: those 4, plus 9 in PHE (trailing spaces, `&nbsp`,
  JSON fragments, an Outlook safelink carrying a reader's email address) and
  2 in HHS (`.pdf<`, `.pdf>`). `clean()` now cuts each back to the address it
  was meant to be and drops it **only where that address is also in the
  source**, so a mangled link that is the only trace of a file is kept. A
  second real extension is not a tail: CDC's `...-sp.pdf.pdf` and `...-sp.pdf`
  differ in digest and are 9 months apart, so both stay. Now **2,809
  records**: Trump actions 64, not 65, because the survey's 65 counted the `]`
  duplicate; Trump briefings 205; PHE 115; HHS `covid*` 65.
  The other 3 empty lookups were not empty at all. Asked again, CDX gave a
  capture for each, the same query three times out of three: CDX had answered
  an empty 200 during the run. `dates.py` now asks twice, a pause apart,
  before recording `none`, and re-asks any `none` from before that change.
  Result: **all 269 items dated, 232 in the period, 37 outside**. The 2
  added outside are Defense Production Act determinations first captured in
  July 2019; the one added inside is the Paycheck Protection Program remarks,
  29 Apr 2020.
- **Step 5 is done: `build/languages.py`** folds CDC's translations
  (26 Oct 2026). It follows the method in "Folding translations" below, made
  precise against all 1,990 cdc-dl filenames: a two-to-four-letter code counts
  only in the run of tags at the end of the name, so `my` in
  `how_do_i_set_up_my_classroom` stays a word. **1,990 files → 1,270
  documents, 303 with at least one language other than English**, against the
  survey's 1,294 and 336. That gap is not reconciled: the survey's code is not
  in the handoff. The rule here reads more spellings than the survey's list
  did, among them `haitian-creole`, `ps`/`psaf`, `mand`, `maylay`, `amet`,
  `cape-verdean-creole`, and Kurdish, Kunama, Serbian, Tamil, Telugu and
  Yiddish, which the first list lacked. Three facts worth knowing before using the numbers:
  - **181 of the 303 have no English file under the same name.** 58 of them
    have an untagged file of similar name in the same folder (difflib ratio
    0.8 or more), e.g. `covid19_keepbabyhealthy-arabic` beside
    `covid-19-keep-baby-healthy`. These are not merged: a fuzzy name is a
    false-merge risk. They need a hand read or a matching pass of their own.
  - 6 documents fold two English or untagged files that differ only by the
    handoff's noise tokens (`-print`, `_final_508`, `-508`, `-final`).
  - Two tokens are left unread on purpose, each in a single file: `_ch` and
    `-fi-`. Others not folded by design: sizes (`11x17`), `updated`, `v4`,
    trailing `-1`/`-2`.
  Output: `data/documents.jsonl`, one row per document with its members;
  non-CDC sources pass through one file per document.
- **The explorer is live** at
  <https://internetarchivecanada.github.io/federal-pandemic-record-covid19/>
  (27 Oct 2026), GitHub Pages from the root of `main`. `build/build_site.py`
  writes `corpus.js` from `documents.jsonl`, `dates.jsonl` and
  `pages-monthly.txt`; `corpus.js` is committed because Pages serves it.
  **1,839 documents**: CDC
  1,259, Trump White House 232, NIH 217, Biden White House 44, ED 29, HHS 28,
  DHS 15, PHE declarations 9, CISA 6. Left out by the corpus rule: images,
  stylesheets, scripts and XML in the file folders; 76 PHE HTML pages that
  are not COVID declarations (other emergencies and list pages) plus 30 PHE
  XML, JSON and image files; 37 Trump items first captured outside the period. PHE shows two April 2021 renewals
  (`covid19-7april2021`, `covid-15april2021`), not yet checked.
- Not run yet: the paged sources (`cdc-ncov`, `hhs-files`), which run only
  when named with `--source`.
- **White House uploads** (6 Nov 2026, #18, #19). One prefix query on a
  mirror's whole `wp-content/uploads/` answers 504, so `months` mode now also
  takes WordPress's `uploads/{yyyy}/{mm}/` layout and reads one month at a
  time. The mirrors were captured from January 2021, so each file is dated by
  the upload month in its path, not by its capture. Kept: Trump 17, Biden
  163. Trump 2020-08 and Biden 2020-04 are still missing after a retry
  (Robin-IA#2). The keyword filter over-matches four Trump files, left in on
  purpose rather than narrowing `KEYWORDS`: the budgetary impact analyses
  for EOs 13829, 13844 and 13882 (matched on `task-force` or
  `suspending-entry`) and a Native American children task-force report.
  They belong in the hand read (#34).
- **CDX outages are failures, not empty sources** (6 Nov 2026). During an
  outage CDX answered 200 with its "Temporarily Offline" HTML page, which
  `parse_rows()` read as zero rows and cached as finished (phe-aspr, which
  has 102). `fetch()` now treats an HTML body from CDX as a failure, and
  `cdx_rows()` asks an empty answer twice before believing it.
- **Rebuilt 6 Nov 2026: 4,185 documents** (from 1,839), 18 agencies. New
  since 27 Oct: Treasury 1,139, CMS 286, SBA 214, FDA 173, OSHA 171,
  FEMA 117, VA 45, USDA 10, DOL 6 (#20–#28); White House uploads, Trump
  +17 and Biden +163 (#18, #19); PHE declarations now 14 as HHS (ASPR),
  with the aspr.hhs.gov renewals (#17). 110 files linked from two sources
  are counted once. Against PR #43's test harvest, FDA has 173, not 224:
  2 of its 32 pages still fail, and they hold most of the gap. CMS has 286,
  not 306, with 4 of 65 pages missing. After one retry, still missing:
  CMS 4 pages; Treasury 1 page and 11 documents; Treasury CARES 3 pages;
  FDA 2 pages and 7 documents; OSHA and USDA 1 document each. Filed as
  issues on Robin-IA.
- **Rebuilt 9 Nov 2026: 6,534 documents.** `cdc-ncov` finished: CDC 2,275 →
  2,672, with 27 of 1,767 CDX pages still missing after one retry (#23; the 29
  pages the retry recovered were all empty). `hhs-files` complete (#9 closed).
  The ten hubs from #20 are in: GAO 487, IRS 25, Safer Federal Workforce 10,
  and combatcovid, Operation Warp Speed, covid.gov and covid19.nih.gov under
  HHS and NIH. GAO follows
  only GAO-20 to GAO-23 report pages: its hub also links 292 "prior work"
  pages from 2002-2019 (638 documents), which were left out. GAO's link text
  names a format ("Full Report (14 pages)"), so `build_site.py` treats it as
  no title and `titles.py --source gao-covid` read the PDFs: 468 titled, 14
  unreadable captures keep file names. Both SBA relief hubs are a JavaScript
  shell with no links (#21); coronavirus.gov links no files. Seven hub
  sub-pages are unread (#22). The full title run (about 4,100 PDFs) has not
  run yet.
- **Rebuilt 8 Nov 2026: 5,539 documents**, while `cdc-ncov` was still
  running. CDC 1,259 → 2,275 from the 785 of 1,767 `cdc-ncov` pages read so
  far. The DHS hub now follows /publication/ pages (#16, #17): DHS 15 → 20,
  CISA 15 → 25, FEMA 117 → 125, FLETC 1, with no gaps. Second gap retries:
  FDA 173 → 222; CMS, Treasury, OSHA, USDA and the CISA workforce hub
  complete. Titles from `titles.py` (#18) are not in yet: only a 29-PDF trial
  has run, and 3,730 file documents still carry file-name titles. Rebuild
  again when `cdc-ncov`, the `hhs-files` retry and the full title run finish.
- **Rebuilt 7 Nov 2026: 4,426 documents.** HHS 28 → 260 from `hhs-files`
  (#16), with 392 of its 425 CDX pages; the other 33 are queued for their
  retry after `cdc-ncov`. CISA 6 → 15 from the workforce-guidance hub (#30),
  1 of 37 pages still missing after a retry. The DHS hub (#29) added nothing:
  51 of its 54 captures read, and none yielded a document link, so the
  link extraction does not fit dhs.gov's pages. `cdc-ncov` (#14) is
  harvesting (1,767 pages, about 30 hours) and gets its own rebuild.
- Still open: whether HTML issuances (statements, press releases) belong in the
  corpus, and whether state material is in scope. The explorer assumes federal
  only and links Archive-It 15784 as a companion.

## What we are building

An explorer of the COVID-19 pandemic as the U.S. federal government told it
on its own websites, preserved by the Wayback Machine. It follows
**Letters from Congress** (`internetarchivecanada/congressional-letters`, branch
`harvest-member-letters`): one static page, a small index, data fetched on
demand, the URL holding the whole state, and every number on the page derived
from the data at build time.

Decisions already made with Robin:

| | |
| --- | --- |
| Views | **Both**: (1) a corpus of published documents, (2) "how the page changed" timelines for a short list of key pages |
| Dates | **December 2019 – 11 May 2023** (end of the federal Public Health Emergency) |
| First milestone | Survey + working prototype + written plan for the full pipeline |
| Sources | Wayback for CDC, HHS, DHS, White House and other federal agencies; then archive.org collections |

**Read first:** `congressional-letters` README.md, CLAUDE.md and PICKUP.md.
Its conventions apply here: branch and PR, never commit to `main`; merging is
Robin's call; repos are private by default; GitHub Pages allows 10 builds an
hour; bump `app.js?v=` whenever it changes; stamp everything a build rewrites.

## The corpus rule (proposed)

**Every document opens as a document.** A Wayback link in the corpus must
replay a PDF or an official issuance page (executive order, proclamation,
memorandum, declaration, statement), not a hub page, a search page, a 404 shell
or a redirect stub. Fold translations of one document into one record that
lists its languages. Check the rule on a random sample of replays before
quoting any count.

## Environment notes

- The Cowork sandbox could not reach archive.org (proxy 403), so the survey ran
  as `fetch()` calls in a Chrome tab. Claude Code on Robin's machine should
  reach `web.archive.org/cdx/search/cdx` and `archive.org/advancedsearch.php`
  directly. Confirm with one request first.
- **Use https.** Letters from Congress found the http CDX endpoint returns 503s.
- Long jobs run from a **terminal under `caffeinate -i`**, not from inside a
  Claude session. Two workers with a pause is the stable rate there. Expect the
  same here.

## CDX: what worked and what didn't (measured)

| Query shape | Result |
| --- | --- |
| Domain-wide `cdc.gov` + regex filter on urlkey | **504 after ~68 s** |
| Prefix `www.cdc.gov/coronavirus/2019-ncov/` + mimetype filter | **504 after ~60 s** |
| Same prefix, `showNumPages=true` | **1,767 pages** (~6,000 rows each, ~32 s per page ≈ 16 h) |
| Prefix `.../2019-ncov/downloads/`, `collapse=urlkey`, `filter=mimetype:application/pdf`, `from=201912&to=202305` | **200 in 70 s, 2,550 rows** |
| Any **prefix** query on `www.whitehouse.gov/...` | **503 "Temporarily Offline" in ~5 s**, every time, including monthly sub-prefixes |
| **Exact** URL on `whitehouse.gov` | 200, fast |
| Prefixes on `trumpwhitehouse.archives.gov` / `bidenwhitehouse.archives.gov` | 200 in 8–20 s |
| Exact-URL timelines (`collapse=digest`) for single pages | 200 in 0.3–6 s |
| Prefix + regex keyword filter on large folders (`hhs.gov/sites/default/files/`, `fema.gov/sites/default/files/` …) | 503 / 504 |
| Filename-prefix trick (`.../files/covid`, `.../files/coronavirus`) | Fast when it works, but 503/504 on about half the attempts |

So the rule is **narrow prefixes, no regex on big folders**. For large folders,
use paged queries (`page=N`) with a per-page on-disk cache, filter locally, and
resume. Expensive pages fail first, so a partial run understates. Record failures
as failures and retry only those, as `harvest.py` does in Letters from Congress.

`collapse=urlkey` with `from=201912` returns the **first capture in range**,
which is the document's "by" date, an upper bound. Show it as "by March 2020",
never as a day, unless a date is in the URL or the document.

## Sources: status per agency

| Code | Source | Prefix | Status |
| --- | --- | --- | --- |
| CDC | CDC COVID downloads | `www.cdc.gov/coronavirus/2019-ncov/downloads/` | **Harvested:** 2,550 rows → 1,990 distinct files after stripping query strings → **1,294 documents** after folding translations; 336 have ≥1 translation (one fact sheet in 32 languages). First seen per year: 2020 1,369 · 2021 822 · 2022 274 · 2023 85 (rows) |
| CDC | Rest of `2019-ncov/` (PDFs outside `downloads/`) | same, paged | **Not done.** Needs the paged harvest (1,767 pages) |
| CDC | MMWR COVID reports | `www.cdc.gov/mmwr/volumes/69…72/` | Not done. Filenames (`mm6912e2-H.pdf`) carry no subject, so titles have to come from the MMWR tables of contents |
| ED | Dept. of Education | `www2.ed.gov/documents/coronavirus/` | **Harvested:** 134 rows |
| NIH | COVID-19 Treatment Guidelines files | `files.covid19treatmentguidelines.nih.gov/` | **Harvested:** 289 rows |
| WH-T | Trump presidential actions | `trumpwhitehouse.archives.gov/presidential-actions/` | **Harvested:** 1,787 actions, **65 COVID** by slug keyword. Archive-site captures start Jan 2021; date each by an exact-URL first-capture lookup on `www.whitehouse.gov/presidential-actions/<slug>/` (not done yet). |
| WH-T | Trump briefings & statements | `trumpwhitehouse.archives.gov/briefings-statements/` | **Harvested** with the keyword filter: **195** COVID items. Date them the same way. |
| WH-B | Biden presidential actions | `bidenwhitehouse.archives.gov/briefing-room/presidential-actions/` | **Harvested:** 1,183 actions, 44 COVID by slug, **42 in range**. Date is in the URL (`/2021/01/21/`). Link to `www.whitehouse.gov/...` at that date. |
| WH | White House PDFs (`wp-content/uploads/2020…2023/`) | | **Blocked** by the whitehouse.gov prefix 503. Try the archives.gov mirrors' `wp-content/uploads/`. |
| HHS | `www.hhs.gov/sites/default/files/` | | Partial: `covid*` = 97 rows. Other prefixes 503. Needs paging (425 pages). |
| PHE | PHE declarations | `www.phe.gov/emergency/news/healthactions/phe/` | Harvested 5 Nov 2026: 215 rows, 115 kept. Declarations to October 2021. `covid19-7April2021` is the opioid crisis renewal, despite its name; left out. |
| PHE | PHE declarations after the move | `aspr.hhs.gov/legal/PHE/Pages/` | Harvested 5 Nov 2026: 102 rows, 55 kept. phe.gov moved here in 2022 and re-hosted the earlier pages; renewals from January 2022 to February 2023 are only here. The build keeps each declaration once, from its first capture: 14 in all (the determination and 13 renewals). |
| DHS | `www.dhs.gov/sites/default/files/publications/` | | Partial: `covid*` = 15 |
| CISA | `www.cisa.gov/sites/default/files/publications/` | | Partial: `covid*` = 6. The essential critical infrastructure workforce guidance PDFs are not named `covid*`; look at `cisa.gov/identifying-critical-infrastructure-during-covid-19` for their URLs. |
| Treasury | hubs `policy-issues/cares` (to April 2021) and `policy-issues/coronavirus` | mode `hub` | Test-harvested 6 Nov 2026: **1,141 documents** after the corpus rule, March 2020 to May 2023; 228 files linked from both hubs counted once. Relief-program files: CARES Act, ARP recovery plans, ERA, HAF. Many titles are bare ("Transaction Summary", "Term Sheet"); see #32. |
| CMS | `www.cms.gov/files/document/` | `paged`, keywords | Test-harvested 6 Nov 2026: 65 pages, 8,230 rows, **306 documents**. |
| FDA | hub `emergency-preparedness-and-response/coronavirus-disease-2019-covid-19` and the pages under it | mode `hub` | Test-harvested 6 Nov 2026: **224 documents**, titled from link text; untitled ones are "FDA document <id>". EUA letters, fact sheets in many languages. 1 of 32 pages still answered 503. |
| SBA | `www.sba.gov/sites/default/files/{month}/` | mode `months`, keywords | Test-harvested 6 Nov 2026: **214 documents** (EIDL, PPP). |
| OSHA | hub `www.osha.gov/coronavirus` and pages under it | mode `hub` | Test-harvested 6 Nov 2026: **172 documents**; publications are numbered (`osha4017.pdf`), so link text gives the titles. |
| FEMA | `www.fema.gov/sites/default/files/{month}/` | mode `months`, keywords | Test-harvested 6 Nov 2026: **117 documents**. Month folders hold files for 2020 only; later uploads are elsewhere and not reached yet. |
| VA | `www.publichealth.va.gov/n-coronavirus/` | prefix, all | Test-harvested 6 Nov 2026: **45 documents**: 9 PDFs and 36 weekly State Veterans Homes case spreadsheets. The rest of the folder is pages and images. |
| USDA | hub `www.usda.gov/coronavirus` | mode `hub` | Test-harvested 6 Nov 2026: **11 documents**, including rd.usda.gov and ams.usda.gov files. |
| DOL | hub `www.dol.gov/coronavirus` | mode `hub` | Test-harvested 6 Nov 2026: **6 documents**. The hub links mostly to wdr.doleta.gov (UIPLs) and osha.gov, which are other sites; UIPL 14-20 and the rest are not reached yet. |

Keyword regex used on slugs (tested; an earlier version matched "ppe" inside
"copper", so keep the word boundaries):

```
(covid|coronavirus|pandemic|vaccin|sars-cov|public-health-emergency|novel-corona|
(^|-)masks?(-|$)|mask-wearing|(^|-)testing(-|$)|reopen|cares-act|american-rescue|
paycheck|stimulus|quarantine|social-distanc|ventilator|(^|-)dpa(-|$)|
defense-production-act|(^|-)ppe(-|$)|personal-protective|long-covid|omicron|
delta-variant|suspension-of-entry|suspending-entry|immigrants-who-present-risk|
economic-relief|eviction|student-loan|task-force|opening-up-america|warp-speed|
hydroxychloroquine)
```

Slug keywords both over- and under-match. Review the Trump/Biden lists by hand
(65 + 195 + 42 items is a short read). For example, a 2019 influenza-vaccine
executive order matches and falls out only on date.

### Folding translations (CDC)

CDC names translations by suffix in many spellings: `-sp`, `-es`, `_ESP`,
`-spanish`, `_ZHCN_HR`, `-chinese`, `_KO_HR_Korean`, `_FAAF_Dari`, `-tigryna`,
`-tigrynia`, `-kinyardwanda`, `TempLog_IItalian`. Method that worked: split the
filename on `[-_ .]`, treat a known language token as the language when it is
not the first token (two- to four-letter codes only near the end), drop noise
tokens (`hr`, `p`, `508`, `print`, `plain`, `final`, `c`, `fs`), and group by
directory + remaining tokens. Keep the English or untagged file as the
representative and list the languages. Write this as `build/languages.py` with
unit tests, including cases that look like languages but aren't (`to` and `my`
are also ISO codes).

## View 2: key pages over time

`data/pages-monthly.txt` holds 27 pages already measured with
`collapse=digest`, `filter=statuscode:200`, Dec 2019–May 2023. Format:

```
#key|url|versions|first_ts|last_ts
YYYYMM:DDhhmmss(first capture that month):versions_that_month:median_KB ...
```

"Versions" means adjacent-digest changes. CDC pages carry dynamic markup, so
the CDC home page shows 14,968 versions. Digest change is **not** content
change. For "what changed", compare extracted text between monthly snapshots,
for example with the org's `compare` tool (wayback-labs.sf.archive.org/wayback-changes/compare/,
repo `internetarchivecanada/compare`), and link Wayback's own diff
(`web.archive.org/web/diff/<ts1>/<ts2>/<url>`).

**Finding: CDC's moved pages become 1 KB placeholders.** When CDC moved a page,
the old URL kept answering **200** with a ~1 KB redirect page, and Wayback kept
capturing it. Median size by month:

| Page | Real page | Then |
| --- | --- | --- |
| `prevent-getting-sick/cloth-face-cover.html` | 50–57 KB, Apr–Jun 2020 | ~1 KB from Jul 2020 |
| `if-you-are-sick/quarantine.html` | 53–77 KB to Aug 2021 | ~1 KB from Sep 2021 |
| `your-health/quarantine-isolation.html` (its successor) | 73–81 KB | ~1 KB from Sep 2022 |
| `cases-updates/cases-in-us.html` | 48–73 KB | ~1 KB from Sep 2020 |
| `schools-childcare/operation-strategy.html` | 94–107 KB | ~1 KB from Feb 2022 |
| `schools-childcare/k-12-guidance.html` | 92–94 KB | ~1 KB from Jun 2022 |
| `need-extra-precautions/people-at-increased-risk.html` | 52–71 KB | 1–2.4 KB from Oct 2020 |

The same trap shows up in the document corpus (Letters from Congress calls it
the "download wrapper"). The explorer should mark placeholder months and follow
the page to its successor. Flag a month when its median size is under ~15% of
that page's largest monthly median.

Other measured shapes worth showing: coronavirus.gov runs Mar 2020–Oct 2021 at
~5 KB (a portal to CDC); covid.gov first appears Mar 2022; covidtests.gov is
captured only Jan–Mar 2022 in range; the FDA COVID hub grows steadily from 28 KB
to 129 KB; the PHE declaration page has 590 versions, with a capture spike in
Jan 2023 (61 that month).

## archive.org: what is there (searched 25 Oct 2026)

Federal material worth linking. Verify partner names before publishing them:

- **Archive-It 13721** "Coronavirus (COVID-19)" and **19129** "COVID.gov", both
  Archive-It partner **593**, which is the **Federal Depository Library Program
  Web Archive** (title of `ArchiveIt-Partner-593`, checked 26 Oct 2026), not NLM.
- **Archive-It 18608** COVIDtests.gov.
- **Archive-It 16018** "David J. Sencer CDC Museum COVID-19 Collection Web
  Archive" and **20471** "David J. Sencer CDC Museum COVID-19 Timeline Links".
  The museum's own timeline is a strong backbone for the events track.
- **Archive-It 15784** "State Executive Actions Related to the COVID-19 Pandemic"
  (states, not federal, but a natural companion).
- **TV News Archive**: C-SPAN "White House Coronavirus Task Force Briefing"
  recordings, Mar–Jul 2020 (`collection:TV-CSPAN`). Get the full count.
- `cdc-youtube-channel`: CDC YouTube videos (`yt_*` items).
- `COVID-19_Apps`: archived apps, including `gov.cdc.general.apk`.
- `USGovernmentDocuments`: e.g. `presidenttrumpscoronavirusguidelinesforamerica`.
- More than 300 COVID Archive-It collections exist, mostly universities and
  localities. Searching `mediatype:collection` for COVID with "federal" in the
  title or description found only 7.

Leave out of the explorer: `opensource`/`community` uploads tagged `fringe` or
`deemphasize`, and `perma_cc` items.

## Events track (verify each before use)

Draft dates for markers on the timeline: HHS PHE declared 31 Jan 2020; national
emergency proclamation 13 Mar 2020; "15 Days to Slow the Spread" 16 Mar 2020;
CARES Act 27 Mar 2020; CDC cloth face-covering recommendation 3 Apr 2020;
Opening Up America Again 16 Apr 2020; first vaccine EUA 11 Dec 2020; Biden
national strategy 21 Jan 2021; American Rescue Plan 11 Mar 2021; CDC
fully-vaccinated mask guidance 13 May 2021 and its reversal 27 Jul 2021;
isolation shortened 27 Dec 2021; COVIDtests.gov opens Jan 2022; CDC streamlined
guidance 11 Aug 2022; national emergency ended 10 Apr 2023; PHE ended 11 May
2023. Prefer linking each to its own archived federal page in the corpus.

## Proposed pipeline (mirrors congressional-letters)

```
build/sources.tsv          agency, prefix, mode (prefix|paged|months|hub), filters
build/harvest.py           CDX per source → data/cdx-cache/ (raw rows, resumable, failures recorded)
build/dates.py             exact-URL first-capture lookups (Trump WH items), URL dates (Biden)
build/languages.py         translation folding + tests
build/titles.py            a PDF's own title (Title field, else first-page heading) + tests
build/pages.py             key-page timelines from build/pages.tsv → data/pages-monthly.txt + tests
build/classify.py          slug → title, doc type (EO, proclamation, memo, guidance, fact sheet,
                           poster, checklist, FAQ, toolkit, transcript, form), topics
build/pages.py             key-page monthly timelines → payload/pages/<key>.json
build/verify_sample.py     replay N random corpus links; record PDF/HTML/stub/404
build/thumbs.py            later: first-page renders, WebP q72, by digest (as in Letters)
build/build_site.py        index.json (counts, facets, histogram, stamp) + payload/
tests/
```

Prototype explorer, in this order:

1. **Overview.** Month histogram Dec 2019–May 2023 with event markers, the
   facets for agency and "translated", title search, and a button to browse
   the matching documents.
1. **Browse the Documents.** The facets (with document type as well) and
   search, sharing their state with the Overview, beside the list. Each row shows its date ("by Mar 2020"), agency,
   title from the slug, languages, and a Wayback link.
2. **Pages over time.** One row per key page: a sparkline of versions per
   month, a size line, placeholder months marked, and a link to the successor
   page. Expanding a row shows monthly snapshot links plus diff and compare
   links.
3. **Democracy's Library Collections.** COVID-19 material in the library's own
   collections (U.S. Agency for Global Media by tag; US Government Documents
   and FEDLINK by scope), then the collections above under "Elsewhere on
   archive.org", with counts derived from search.
4. **About.** The corpus rule, the traps, and caveats with their measured
   numbers.

## Start here

1. Confirm direct access: one CDX request and one advancedsearch request.
2. Create the repo (private, under internetarchivecanada, after asking Robin
   about the name) and copy this file in as `PICKUP.md`, with
   `data/pages-monthly.txt`.
3. Write `build/sources.tsv` from the table above and run `harvest.py` on the
   sources marked Harvested. That rebuilds what the browser held, in minutes.
4. Run `dates.py` for the 260 Trump White House items. Exact lookups are cheap.
   Keep it to 2 workers.
5. Build the prototype on that corpus and open a PR. Then start the long paged
   harvests (CDC `2019-ncov/`, HHS files) from a terminal.

Open questions for Robin: the repo name; whether the corpus should include HTML
issuances (statements, press releases) or only PDFs and formal actions; and
whether state-level material belongs in scope.
