# Security and accessibility checks

**Status: passing.** All three checks passed on 2026-11-07 at commit `4b28263c8a`. Nothing is open. Advisory items below are optional.

> The checkout had uncommitted changes when this ran, so it describes a working tree, not a commit.

| | |
|---|---|
| Explorer | https://github.com/Robin-IA/federal-pandemic-record-covid19 |
| Commit | `4b28263c8a` on `explorer-checks` |
| Date | 2026-11-07 |
| Pages checked | `./`, `./#documents`, `./#pages`, `./#archive`, `./#about` |
| Served from | repository root, served locally |
| Live site (headers) | https://internetarchivecanada.github.io/federal-pandemic-record-covid19/ |
| Standard | WCAG 2.2 Level AA |
| Security references | OWASP Top 10:2025 and ASVS 5.0.0 |
| Tools | axe-core 4.14.0, html5lib, ruff, bandit, pip-audit, headless Chromium |
| Reviewed by | Claude (claude-opus-5-5) via the explorer-checks skill |
| Skill version | 2026.11.05.9 |

## Summary

| Check | Result | Must fix | Needs review | Advisory |
|---|---|---:|---:|---:|
| Code validity | Pass | 0 | 0 | 0 |
| Code security | Pass | 0 | 0 | 3 |
| Accessibility (WCAG 2.2 AA) | Pass | 0 | 0 | 0 |

## Standards met

Checked 7 November 2026 at commit `4b28263c8a`, on the pages listed above:

- **WCAG 2.2 Level AA**: every Level A and AA success criterion, by automated tests and a manual review of each criterion (checklists under each check below).
- **WCAG 2.1 Level AA** and **WCAG 2.0 Level AA**, which WCAG 2.2 includes. 4.1.1 Parsing, dropped from 2.2 but still in 2.0 and 2.1, is covered by the code validity check (no HTML parse errors, no duplicate ids).
- These are the web content requirements of **Section 508** (US federal; WCAG 2.0 AA) and **EN 301 549** clause 9 (WCAG 2.1 AA).
- Security was checked against the OWASP Top 10:2025 risks and ASVS 5.0.0 chapters that apply to an explorer; each finding and checklist item names its category. That is not an ASVS verification at any level.

## What a pass means

Each check combines automated tools with a review of the code and pages against a written checklist. A pass means neither found anything open on the date and commit above. The standards are met as far as those checks can establish: it is a self-assessment, not third-party certification. Automated testing finds a minority of accessibility barriers. Testing with people who use assistive technology is still worth doing, and a change to the explorer needs a re-run.

## Code validity

No open items.

## Code security

No open items.

<details><summary>Manual checklist (4 pass, 0 fail, 5 n/a)</summary>

| Item | Result | Note |
|---|---|---|
| No secrets | pass | Scanner found none. No config or .env files; the build reads only public CDX and Wayback replay endpoints. |
| Untrusted data is escaped | pass | All eight sinks traced; app.js unchanged since 5 Nov. Hub link text from replayed pages reaches the page only as a title, through esc(). The meta CSP (script-src 'self') still limits what an escape miss could run. |
| URLs from data are safe | pass | Every data href is prefixed with https://web.archive.org/web/ or https:// and escaped. New static links (archive.org, democracys-library, wayback-labs, web.archive.org, mailto) are literals. |
| Third-party code is pinned | n/a | No third-party scripts. Google Fonts CSS only. |
| No mixed content | pass | Logos are served from the repository (img/), not loaded from archive.org. |
| Server input is validated | n/a | Static site on GitHub Pages; no server. |
| Dependencies have no known vulnerabilities | n/a | No requirements file; build scripts use the standard library only. |
| Errors do not leak | n/a | Static site. |
| Scope of writes | n/a | No uploads or contributions. |

</details>

<details><summary>Cleared on review (9)</summary>

| Id | Item | Where | Why cleared |
|---|---|---|---|
| `S-7da0cb` | String rendered as markup or code (innerHTML) | `app.js:49` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); Facet titles and data-k keys are literals; every facet value goes through esc() (app.js:15), and the checkbox id is esc(v) with \W stripped. |
| `S-86c03b` | String rendered as markup or code (innerHTML) | `app.js:50` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); Facet titles and data-k keys are literals; every facet value goes through esc() (app.js:15), and the checkbox id is esc(v) with \W stripped. |
| `S-e7be65` | String rendered as markup or code (innerHTML) | `app.js:88` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); Histogram markup is numbers computed in renderHist, month strings from the MONTHS loop, and EVENTS labels (a literal array) through esc(). |
| `S-0a0240` | String rendered as markup or code (innerHTML) | `app.js:93` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); The month select's options are built only from MONTHS, fmtM() of those, and fmtN() of computed counts. No corpus data reaches it. |
| `S-e56e10` | String rendered as markup or code (innerHTML) | `app.js:103` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); title, agency, type and langs go through esc(); month and day come from CDX timestamp digits (build_site.py); d.url goes through esc() and always starts https://web.archive.org/web/. New hub link text reaches the |
| `S-9a3420` | String rendered as markup or code (innerHTML) | `app.js:151` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); url is esc('https://' + p.url) and both timestamps in the Wayback and diff hrefs go through esc(); page name and URL text are escaped. |
| `S-3a1343` | String rendered as markup or code (innerHTML) | `app.js:180` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); Only literals reach it: card() renders the DL_CARDS and CARDS constants in app.js; titles through esc(), counts through fmtN(). |
| `S-b502a5` | String rendered as markup or code (innerHTML) | `app.js:181` | app.js is unchanged since the 5 Nov review (git diff 43a77b6..HEAD -- app.js is empty); Only literals reach it: card() renders the DL_CARDS and CARDS constants in app.js; titles through esc(), counts through fmtN(). |
| `S-d202c3` | Audit url open for permitted schemes. Allowing use of file:/ or custom schemes is often unexpected. | `build/harvest.py:143` | fetch() opens only URLs harvest.py builds: the CDX API base (https://web.archive.org/cdx/search/cdx) with sources.tsv prefixes, and https://web.archive.org/web/<timestamp>id_/<original> replays built from CDX rows for hub pages. Nothing from outside chooses the scheme. |

</details>

## Accessibility (WCAG 2.2 AA)

No open items.

<details><summary>Manual checklist (21 pass, 0 fail, 2 n/a)</summary>

| Item | Result | Note |
|---|---|---|
| 1.1.1 Non-text content | pass | New logo images have alt 'Internet Archive' and 'Democracy's Library', which name the link destinations. Month select still carries the histogram's data as text. |
| 1.3.1 Info and relationships | pass | Headings run h1 then h2 in every view, including the new About h2s (Why save government websites?, Who made this?) and Related explorers. Footer is a <footer> landmark. |
| 1.3.2 Meaningful sequence | pass | DOM order matches visual order; the accessibility statement and Feedback now follow main in the footer. |
| 1.4.1 Use of color | pass | Unchanged since 5 Nov; new links are underlined in body text. |
| 1.4.3 Contrast (minimum) | pass | Measured today: footer text and statement 5.30:1 light / 7.17:1 dark; footer and About links 6.60:1 / 8.14:1; new card title 7.09:1 / 7.28:1, card text 5.70:1 / 6.41:1. Histogram labels unchanged (5.38:1 lowest). |
| 1.4.11 Non-text contrast | pass | Unchanged controls; the DL logo sits on its own white tile on the dark band. |
| 1.4.4 Resize text / 1.4.12 Text spacing | pass | Reflow at 320px passes (automated). Statement is 12.25px, 0.875em of the footer's 14px. |
| 2.4.4 Link purpose | pass | Logo links are named by their alt text; 'Email us' follows 'Feedback?'; the new card link names the explorer. |
| 2.4.6 Headings and labels | pass |  |
| 3.1.1 Language of page | pass | lang="en". |
| 2.1.1 Keyboard | pass | New links (logos, card, About, footer) are native anchors in tab order. |
| 2.1.2 No keyboard trap | pass |  |
| 2.4.1 Bypass blocks | pass | The views are in <main id="main">. |
| 2.4.3 Focus order | pass | Logo links come first in the masthead, footer links last. |
| 2.4.7 Focus visible | pass | :focus-visible outline on a; masthead links use --mast-link for the outline. Automated focus check found no unstyled focus. |
| 2.4.11 Focus not obscured | pass | Unchanged since 5 Nov; new focusable elements are above the sticky nav (masthead) or at the end of the page. |
| 2.5.8 Target size | pass | Logo links are 40x40px; other new targets are inline text links. |
| 2.2.2 Pause, stop, hide | n/a | Nothing moves or auto-updates. |
| 3.2.2 On input | pass |  |
| 3.3.2 Labels or instructions | pass |  |
| 4.1.2 Name, role, value | pass | Checked in all five views. |
| 4.1.3 Status messages | pass | #count has role="status". |
| 1.2.x Media | n/a | No audio or video. |

</details>

<details><summary>Cleared on review (2)</summary>

| Id | Item | Where | Why cleared |
|---|---|---|---|
| `A-6c64c1` | Elements must meet minimum color contrast ratio thresholds | `/ color-contrast` | The same 23 SVG axis and event labels as on 5 Nov; histogram CSS and colours unchanged. Measured then: axis labels 5.70:1, event labels 5.38:1 on --surface. |
| `A-cae34d` | Elements must meet minimum color contrast ratio thresholds (dark mode) | `/ color-contrast (dark mode)` | Same labels in dark mode, unchanged since 5 Nov: axis 6.41:1, event 7.52:1. |

</details>

## Advisory (3)

Optional. These items never block a pass.

| Id | Check | Item | Where | Reference | Suggestion |
|---|---|---|---|---|---|
| `S-1baacc` | security | No x-content-type-options header | `https://internetarchivecanada.github.io/federal-pandemic-record-covid19/` | A02:2025 · ASVS V3 | Set it; it stops browsers guessing content types. It has no <meta> form, so on a host that cannot set headers (GitHub Pages) it stays open; the explorer's owners decide whether that matters enough to change host. |
| `S-36c938` | security | Page contacts a third party: fonts.googleapis.com | `/` | ASVS V3 | Every visitor's IP address and the page they are on go to this host. Serve the file from the explorer itself (fonts and libraries can be vendored), or keep it and say so in the review. |
| `S-21f485` | security | Page contacts a third party: fonts.gstatic.com | `/` | ASVS V3 | Every visitor's IP address and the page they are on go to this host. Serve the file from the explorer itself (fonts and libraries can be vendored), or keep it and say so in the review. |

<!-- explorer-checks:state {"passing": true, "date": "2026-11-07", "commit": "4b28263c8a5662d89d0225cc269d78c3dfe71ed8", "open": [], "titles": {}} -->
