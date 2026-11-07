import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import harvest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def src(**kw):
    base = {"code": "t", "agency": "T", "prefix": "www.example.gov/files/",
            "mode": "prefix", "filters": "", "dated": "yes", "select": "all"}
    return base | kw


def row(url, ts="20200401000000"):
    return {"original": url, "timestamp": ts, "mimetype": "application/pdf",
            "statuscode": "200", "digest": "D", "length": "1"}


class Keywords(unittest.TestCase):
    def test_matches(self):
        for s in ["covid-19-guidance", "face-masks", "mask", "ppe-shortage",
                  "proclamation-on-the-suspension-of-entry", "invoking-the-dpa",
                  "testing", "opening-up-america-again"]:
            self.assertTrue(harvest.KEYWORDS.search(s), s)

    def test_word_boundaries(self):
        # "ppe" inside "copper" was the bug that made the boundaries necessary.
        for s in ["copper-mining", "maskell-report", "contesting-results",
                  "dpaa-accounting", "upper-basin"]:
            self.assertFalse(harvest.KEYWORDS.search(s), s)


class ParseRows(unittest.TestCase):
    def test_rows(self):
        body = "http://a/x.pdf 20200101000000 application/pdf 200 D 10\n"
        self.assertEqual(harvest.parse_rows(body)[0]["timestamp"], "20200101000000")

    def test_resume_key_is_a_failure(self):
        body = "http://a/x.pdf 20200101000000 application/pdf 200 D 10\n\ngov,a)/y.pdf+20200102\n"
        with self.assertRaises(RuntimeError):
            harvest.parse_rows(body)

    def test_empty_is_empty_not_a_failure(self):
        self.assertEqual(harvest.parse_rows(""), [])


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Network(unittest.TestCase):
    """An outage or a stray empty answer is a failure or a re-ask, never zero rows."""

    OFFLINE = (b'<html><head><meta charset="UTF-8"><title>Internet Archive: '
               b'Temporarily Offline</title></head><body>offline</body></html>')
    ROW = b"http://a/x.pdf 20200101000000 application/pdf 200 D 10\n"

    def setUp(self):
        self.saved = (harvest.urllib.request.urlopen, harvest.time.sleep, harvest.EMPTY_PAUSE)
        harvest.time.sleep = lambda s: None
        harvest.EMPTY_PAUSE = 0
        self.calls = 0

    def tearDown(self):
        harvest.urllib.request.urlopen, harvest.time.sleep, harvest.EMPTY_PAUSE = self.saved

    def answer(self, *bodies):
        def urlopen(request, timeout=None):
            body = bodies[min(self.calls, len(bodies) - 1)]
            self.calls += 1
            return Response(body)
        harvest.urllib.request.urlopen = urlopen

    def test_offline_page_from_cdx_is_a_failure(self):
        self.answer(self.OFFLINE)
        with self.assertRaises(RuntimeError):
            harvest.fetch(harvest.CDX + "?url=x")
        self.assertEqual(self.calls, harvest.RETRIES)

    def test_offline_then_rows_recovers(self):
        self.answer(self.OFFLINE, self.ROW)
        self.assertEqual(len(harvest.cdx_rows(harvest.CDX + "?url=x")), 1)

    def test_replay_html_is_not_checked(self):
        self.answer(b"<html>a page</html>")
        self.assertIn("a page", harvest.fetch("https://web.archive.org/web/2020id_/http://a/"))

    def test_empty_is_asked_twice(self):
        self.answer(b"", self.ROW)
        self.assertEqual(len(harvest.cdx_rows(harvest.CDX + "?url=x")), 1)
        self.assertEqual(self.calls, 2)

    def test_empty_twice_is_empty(self):
        self.answer(b"")
        self.assertEqual(harvest.cdx_rows(harvest.CDX + "?url=x"), [])
        self.assertEqual(self.calls, 2)

    def test_prefix_source_offline_is_cached_as_failure(self):
        import tempfile
        self.answer(self.OFFLINE)
        with tempfile.TemporaryDirectory() as tmp:
            entry = harvest.harvest_prefix(src(), Path(tmp))
            self.assertIn("error", entry)
            self.assertFalse(harvest.is_done(harvest.read_cache(Path(tmp) / "t.json")))


class Clean(unittest.TestCase):
    def test_query_strings_fold_and_earliest_wins(self):
        rows = [row("https://www.example.gov/files/a.pdf?v=2", "20200501000000"),
                row("http://www.example.gov/files/a.pdf", "20200301000000"),
                row("https://example.gov/files/A.pdf", "20200401000000")]
        out = harvest.clean(src(), rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["timestamp"], "20200301000000")

    def test_index_page_dropped(self):
        out = harvest.clean(src(), [row("https://www.example.gov/files/"),
                                    row("https://www.example.gov/files/b.pdf")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/b.pdf"])

    def test_keyword_select_reads_the_last_segment(self):
        s = src(select="keywords", prefix="www.example.gov/coronavirus-actions/")
        out = harvest.clean(s, [row("https://www.example.gov/coronavirus-actions/budget-memo/"),
                                row("https://www.example.gov/coronavirus-actions/covid-memo/")])
        self.assertEqual(len(out), 1)

    def test_url_date_outside_the_period_is_dropped(self):
        s = src(select="keywords", prefix="www.example.gov/actions/")
        out = harvest.clean(s, [
            row("https://www.example.gov/actions/2019/09/19/order-modernizing-influenza-vaccines/"),
            row("https://www.example.gov/actions/2021/01/21/order-covid-19-response/"),
            row("https://www.example.gov/actions/2023/05/12/memo-vaccine-requirements/")])
        self.assertEqual([r["url_day"] for r in out], ["20210121"])

    def test_filename_prefix_source_keeps_its_files(self):
        # A prefix like .../files/covid ends mid-filename; it is not a folder.
        s = src(prefix="www.example.gov/files/covid")
        out = harvest.clean(s, [row("https://www.example.gov/files/covid-guidance.pdf"),
                                row("https://www.example.gov/files/budget.pdf")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/covid-guidance.pdf"])

    def test_mangled_link_with_a_twin_is_dropped(self):
        s = src(prefix="www.example.gov/actions/")
        good = "https://www.example.gov/actions/proclamation-covid-19-outbreak/"
        out = harvest.clean(s, [row(good),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak]/"),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak-.5/"),
                                row("https://www.example.gov/actions/proclamation-covid-19-outbreak-"),
                                row("https://www.example.gov/actions/page.aspx%20"),
                                row("https://www.example.gov/actions/page.aspx&data=05|01|a@b.edu&reserved=0"),
                                row("https://www.example.gov/actions/page.aspx"),
                                row('https://www.example.gov/actions%22,%22contextTitle%22:%22X%22')])
        self.assertEqual([r["key"] for r in out],
                         ["example.gov/actions/page.aspx",
                          "example.gov/actions/proclamation-covid-19-outbreak"])

    def test_mangled_link_without_a_twin_is_kept(self):
        out = harvest.clean(src(), [row("https://www.example.gov/files/only-trace.pdf%3E")])
        self.assertEqual([r["key"] for r in out], ["example.gov/files/only-trace.pdf>"])

    def test_second_real_extension_is_not_a_tail(self):
        # Measured 26 Oct 2026: the cdc-dl .pdf.pdf and .pdf files differ in digest.
        for k in ["example.gov/files/a.pdf.pdf", "example.gov/files/a.html.pdf",
                  "example.gov/files/manual final_508.docx", "example.gov/files/data.xlsx"]:
            self.assertEqual(harvest.well_formed(k), k)


class Months(unittest.TestCase):
    def test_months_cover_the_period(self):
        m = harvest.months()
        self.assertEqual((m[0], m[-1], len(m)), ("2019-12", "2023-05", 42))

    def test_month_prefix_and_mode_go_together(self):
        import tempfile
        header = ["code", "agency", "prefix", "mode", "filters", "dated", "select", "status", "handoff", "note"]
        values = ["x", "X", "www.example.gov/files/{month}/", "prefix", "", "yes", "all", "harvested", "", ""]
        bad = "\t".join(header) + "\n" + "\t".join(values) + "\n"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.tsv"
            path.write_text(bad, encoding="utf-8")
            with self.assertRaises(ValueError):
                harvest.load_sources(path)

    def test_month_folders_clean_against_the_base(self):
        s = src(prefix="www.example.gov/files/{month}/", mode="months", select="keywords")
        kept = harvest.clean(s, [row("https://www.example.gov/files/2020-04/covid-loan-faq.pdf"),
                                 row("https://www.example.gov/files/2020-04/annual-report.pdf"),
                                 row("https://www.example.gov/other/2020-04/covid.pdf")])
        self.assertEqual([k["key"] for k in kept], ["example.gov/files/2020-04/covid-loan-faq.pdf"])

    def test_months_resume_and_report_missing(self):
        import tempfile
        s = src(prefix="www.example.gov/files/{month}/", mode="months")
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            harvest.write_cache(cache / "t" / "month-2020-04.json",
                                {"method": harvest.CACHE_METHOD, "rows": [row("https://www.example.gov/files/2020-04/a.pdf")]})
            entry = harvest.load(s, cache)
            self.assertEqual(len(entry["rows"]), 1)
            self.assertEqual(entry["error"], "41 of 42 months not in")


class Hub(unittest.TestCase):
    PAGE = "https://www.example.gov/coronavirus"

    def links(self, html):
        return sorted(harvest.doc_links(html, self.PAGE))

    def test_relative_links_made_absolute(self):
        self.assertEqual(self.links('<a href="/files/guide.pdf">Guide</a>'),
                         ["https://www.example.gov/files/guide.pdf"])

    def test_same_site_subdomain_counts_other_site_does_not(self):
        html = '<a href="https://www.rd.example.gov/a.pdf">A</a> <a href="https://www.other.gov/b.pdf">B</a>'
        self.assertEqual(self.links(html), ["https://www.rd.example.gov/a.pdf"])

    def test_pages_and_fragments_are_not_documents(self):
        html = '<a href="/coronavirus/faq">FAQ</a> <a href="#top">Top</a> <a href="mailto:x@example.gov">Mail</a>'
        self.assertEqual(self.links(html), [])

    def test_fda_media_download_is_a_document(self):
        self.assertEqual(self.links("<a class='x' href='/media/136316/download'>Letter</a>"),
                         ["https://www.example.gov/media/136316/download"])

    def test_wayback_prefix_and_query_stripped(self):
        html = '<a href="https://web.archive.org/web/20210101000000/https://www.example.gov/a.pdf?x=1&amp;y=2">A</a>'
        self.assertEqual(self.links(html), ["https://www.example.gov/a.pdf"])

    def test_link_text_becomes_the_title(self):
        html = ('<a href="/media/1/download"><span>Emergency Use Authorization</span>\n'
                ' letter &amp; fact sheet (PDF - 210KB)</a>')
        self.assertEqual(harvest.doc_links(html, self.PAGE),
                         {"https://www.example.gov/media/1/download": "Emergency Use Authorization letter & fact sheet"})

    def test_empty_link_text_is_dropped_and_longer_text_wins(self):
        html = ('<a href="/f/osha3990.pdf">PDF</a> <a href="/f/osha3990.pdf">osha3990.pdf</a>'
                ' <a href="/f/osha3990.pdf">Guidance on Preparing Workplaces for COVID-19</a>'
                ' <a href="/f/x.pdf">Download</a>')
        self.assertEqual(harvest.doc_links(html, self.PAGE),
                         {"https://www.example.gov/f/osha3990.pdf": "Guidance on Preparing Workplaces for COVID-19",
                          "https://www.example.gov/f/x.pdf": ""})

    def test_documents_from_before_2020_are_dropped_but_not_those_older_than_the_hub(self):
        import tempfile
        s = src(prefix="www.example.gov/coronavirus", mode="hub")
        hub = "https://www.example.gov/coronavirus"
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "t"
            harvest.write_cache(folder / "_pages.json", {"pages": [["20210414000000", hub]]})
            harvest.write_cache(harvest._hashed(folder, "page", "20210414000000" + hub),
                                {"method": harvest.CACHE_METHOD,
                                 "links": {"https://www.example.gov/old.pdf": "",
                                           "https://www.example.gov/new.pdf": "New guidance"}})
            for name, ts in (("old", "20191215000000"), ("new", "20200401000000")):
                url = f"https://www.example.gov/{name}.pdf"
                harvest.write_cache(harvest._hashed(folder, "doc", harvest.canonical(url)),
                                    {"method": harvest.CACHE_METHOD, "rows": [row(url, ts)]})
            entry = harvest.load(s, Path(d))
        self.assertEqual(entry["before_hub"], 1)
        self.assertEqual([(r["original"], r.get("link_text")) for r in entry["rows"]],
                         [("https://www.example.gov/new.pdf", "New guidance")])

    def test_hub_documents_need_not_sit_under_the_hub(self):
        s = src(prefix="www.example.gov/coronavirus", mode="hub")
        kept = harvest.clean(s, [row("https://www.example.gov/files/guide.pdf")])
        self.assertEqual([k["key"] for k in kept], ["example.gov/files/guide.pdf"])


class Sources(unittest.TestCase):
    def test_month_prefix_fills_either_layout(self):
        self.assertEqual(harvest.month_prefix("www.x.gov/sites/default/files/{month}/", "2020-03"),
                         "www.x.gov/sites/default/files/2020-03/")
        self.assertEqual(harvest.month_prefix("x.archives.gov/wp-content/uploads/{yyyy}/{mm}/", "2020-03"),
                         "x.archives.gov/wp-content/uploads/2020/03/")

    def test_sources_tsv_loads(self):
        sources = harvest.load_sources(ROOT / "build" / "sources.tsv")
        self.assertTrue(any(s["status"] == "harvested" for s in sources))
        for s in sources:
            self.assertNotIn("whitehouse.gov/", s["prefix"].replace("archives.gov", ""),
                             f"{s['code']}: whitehouse.gov prefix queries answer 503")


if __name__ == "__main__":
    unittest.main()
