import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import build_site  # noqa: E402
import titles  # noqa: E402

KEY = "www.cdc.gov/coronavirus/2019-ncov/downloads/consolidated-forecasts-hosp-2023-03-13.pdf"


def pdf(title=None):
    import pypdf
    w = pypdf.PdfWriter()
    w.add_blank_page(612, 792)
    if title is not None:
        w.add_metadata({"/Title": title})
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


class Usable(unittest.TestCase):
    def test_a_real_title(self):
        self.assertTrue(titles.usable("COVID-19 Vaccines: What Older Adults Need to Know", KEY))

    def test_the_file_name_again(self):
        self.assertFalse(titles.usable("Consolidated-Forecasts-Hosp-2023-03-13", KEY))

    def test_templates_and_editors(self):
        for t in ["Coronavirus disease 2019 (COVID-19) Factsheet", "R Graphics Output",
                  "Microsoft Word - memo final.docx", "PowerPoint Presentation", "Untitled"]:
            self.assertFalse(titles.usable(t, KEY), t)

    def test_page_furniture_and_glyphs(self):
        for t in ["Page 3 of 12", "1-800-321-6742", "LI I fl LI", "04/23/2020"]:
            self.assertFalse(titles.usable(t, KEY), t)

    def test_other_scripts_count(self):
        self.assertTrue(titles.usable("等待COVID-19检测结果时需要采取的 3个关键步骤", KEY))


class Tidy(unittest.TestCase):
    def test_footer_address_run_in(self):
        self.assertEqual(titles.tidy("Examples of Triage Algorithmscdc.gov/coronavirus"),
                         "Examples of Triage Algorithms")

    def test_long_titles_cut_at_a_word(self):
        t = titles.tidy("word " * 60)
        self.assertLessEqual(len(t), 201)
        self.assertTrue(t.endswith("…"))


class SaysLess(unittest.TestCase):
    def test_the_file_name_holds_more(self):
        key = ("trumpwhitehouse.archives.gov/wp-content/uploads/2021/01/budgetary-impact-analysis-for-executive-"
               "order-entitled-protecting-the-federal-workforce-and-requiring-mask-wearing.pdf")
        self.assertTrue(titles.says_less("Protecting the Federal Workforce and Requiring Mask-Wearing", key))

    def test_workflow_words_do_not_count(self):
        key = "www.cdc.gov/coronavirus/2019-ncov/downloads/vaccinations-by-case-rate-final-07132021.pdf"
        self.assertFalse(titles.says_less("Vaccinations by Case Rate", key))


class TitleOf(unittest.TestCase):
    def test_metadata_title(self):
        self.assertEqual(titles.title_of(pdf("COVID-19 Healthcare Resource Roadmap"), KEY),
                         {"status": "found", "from": "meta", "title": "COVID-19 Healthcare Resource Roadmap"})

    def test_nothing_usable(self):
        self.assertEqual(titles.title_of(pdf("Consolidated-Forecasts-Hosp-2023-03-13"), KEY), {"status": "none"})


class BuildSite(unittest.TestCase):
    DOC = {"source": "cdc-ncov", "agency": "CDC", "key": KEY, "mimetype": "application/pdf",
           "languages": [], "first_ts": "20230313000000", "timestamp": "20230313000000",
           "original": "https://" + KEY}

    def test_found_title_is_used(self):
        found = {KEY: {"status": "found", "title": "Hospitalization forecasts"}}
        e = build_site.entry(self.DOC, {}, found)
        self.assertEqual(e["title"], "Hospitalization forecasts")
        self.assertNotIn("fn", e)

    def test_file_name_title_is_marked(self):
        e = build_site.entry(self.DOC, {}, {KEY: {"status": "none"}})
        self.assertEqual(e["title"], "Consolidated forecasts hosp 2023 03 13")
        self.assertEqual(e["fn"], 1)

    def test_a_format_label_is_not_a_title(self):
        d = self.DOC | {"source": "gao-covid", "key": "gao.gov/assets/gao-21-387.pdf",
                        "original": "https://www.gao.gov/assets/gao-21-387.pdf"}
        for text in ["Full Report (14 pages)", "Highlights Page (1 page)", "Accessible PDF (48 pages)", "View Report"]:
            self.assertEqual(build_site.hub_title(d | {"link_text": text}), "Gao 21 387", text)
            self.assertTrue(titles.needs_title(d | {"link_text": text}), text)
        self.assertEqual(build_site.hub_title(d | {"link_text": "Highlights of the CARES Act"}),
                         "Highlights of the CARES Act")

    def test_a_shared_title_takes_its_printed_date(self):
        docs = [{"agency": "White House (Biden)", "title": "COVID-19 Press Briefing", "date": "June 8, 2021"},
                {"agency": "White House (Biden)", "title": "COVID-19 Press Briefing", "date": "June 17, 2021"},
                {"agency": "FEMA", "title": "Roadmap", "date": "October 27, 2020"}]
        self.assertEqual([d["title"] for d in build_site.one_title_each(docs)],
                         ["COVID-19 Press Briefing, June 8, 2021", "COVID-19 Press Briefing, June 17, 2021",
                          "Roadmap"])
        self.assertTrue(all("date" not in d for d in docs))


if __name__ == "__main__":
    unittest.main()
