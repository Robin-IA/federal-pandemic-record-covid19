import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import build_site  # noqa: E402


def phe(source, key, ts):
    host = "https://www.phe.gov/emergency/news/healthactions/phe/Pages/" if source == "phe" \
        else "https://aspr.hhs.gov/legal/PHE/Pages/"
    slug = key.rsplit("/", 1)[-1]
    return {"source": source, "agency": "HHS (ASPR)", "key": key, "languages": [],
            "timestamp": ts, "original": host + slug}


def keep(*records):
    docs = [e for e in (build_site.entry(r, {}) for r in records) if e]
    return build_site.one_per_declaration(docs)


class PublicHealthEmergency(unittest.TestCase):
    def test_declarations_and_renewals_count(self):
        for slug in ["2019-ncov.aspx", "covid19-21apr2020.aspx", "covdi-15oct21.aspx",
                     "covid19-14jan2022.aspx", "covid19-9feb2023.aspx"]:
            self.assertTrue(build_site.PHE_COVID.search("/pages/" + slug), slug)

    def test_other_pages_in_the_folder_do_not(self):
        for slug in ["letter-to-governors-on-the-covid-19-response.aspx", "mers-cov.aspx",
                     "opioids-7jan2021.aspx", "allitems.aspx"]:
            self.assertFalse(build_site.PHE_COVID.search("/pages/" + slug), slug)

    def test_opioid_renewal_named_like_covid_is_left_out(self):
        self.assertEqual(keep(phe("phe", "phe.gov/x/pages/covid19-7april2021.aspx", "20210407193309")), [])

    def test_renewal_titles_take_the_date_from_the_address(self):
        (d,) = keep(phe("phe-aspr", "aspr.hhs.gov/legal/phe/pages/covid19-11jan23.aspx", "20230111151419"))
        self.assertEqual(d["title"], "Renewal of the COVID-19 public health emergency, 11 Jan 2023")
        self.assertEqual(d["month"], "2023-01")

    def test_rehosted_copy_counts_once_from_the_first_capture(self):
        docs = keep(phe("phe-aspr", "aspr.hhs.gov/legal/phe/pages/covid-15oct21.aspx", "20220716093430"),
                    phe("phe", "phe.gov/x/pages/covdi-15oct21.aspx", "20211015183027"))
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["month"], "2021-10")
        self.assertIn("phe.gov", docs[0]["url"])

    def test_other_documents_are_untouched(self):
        a = {"type": "PDF", "title": "Same", "url": "u1", "month": "2020-01"}
        b = dict(a, url="u2")
        self.assertEqual(build_site.one_per_declaration([a, b]), [a, b])


def hub_doc(key, **kw):
    return {"source": "fda", "agency": "FDA", "key": key, "languages": [], "mimetype": "application/pdf",
            "timestamp": "20201219000000", "first_ts": "20201219000000",
            "original": "https://www." + key} | kw


class HubTitles(unittest.TestCase):
    def test_link_text_is_the_title(self):
        d = build_site.entry(hub_doc("fda.gov/media/144638/download", link_text="Moderna EUA letter"), {})
        self.assertEqual(d["title"], "Moderna EUA letter")

    def test_without_link_text_the_file_name_is_the_title(self):
        d = build_site.entry(hub_doc("osha.gov/sites/default/files/publications/osha4017.pdf"), {})
        self.assertEqual(d["title"], "Osha4017")

    def test_a_language_name_alone_is_not_a_title(self):
        for text in ["French Creole", "Spanish", "Chinese (Simplified)", "Haitian Creole version"]:
            d = build_site.entry(hub_doc("osha.gov/x/osha4007.pdf", link_text=text), {})
            self.assertEqual(d["title"], "Osha4007", text)

    def test_an_address_is_not_a_title(self):
        d = build_site.entry(hub_doc("aphis.usda.gov/import/covid-19-info.pdf",
                                     link_text="www.aphis.usda.gov/import/covid-19-info.pdf"), {})
        self.assertEqual(d["title"], "Covid 19 info")

    def test_untitled_fda_media_is_named_by_its_id(self):
        d = build_site.entry(hub_doc("fda.gov/media/142399/download"), {})
        self.assertEqual(d["title"], "FDA document 142399")

    def test_a_file_in_two_sources_is_listed_once_earliest_first(self):
        a = hub_doc("home.treasury.gov/system/files/136/plan.pdf", source="treasury",
                    first_ts="20210501000000", link_text="Plan")
        b = hub_doc("home.treasury.gov/system/files/136/plan.pdf", source="treasury-cares",
                    first_ts="20200601000000", link_text="Plan")
        c = hub_doc("home.treasury.gov/system/files/136/other.pdf")
        kept, repeats = build_site.one_per_file([a, b, c])
        self.assertEqual((kept, repeats), ([b, c], 1))

    def test_a_title_in_another_language_is_kept(self):
        d = build_site.entry(hub_doc("dol.gov/whd/pandemic/1422-spanish.pdf",
                                     link_text="Derechos del empleado sobre licencia laboral pagada"), {})
        self.assertEqual(d["title"], "Derechos del empleado sobre licencia laboral pagada")


def upload(path, ts="20210301000000"):
    key = "trumpwhitehouse.archives.gov/wp-content/uploads/" + path
    return {"source": "wh-uploads-trump", "agency": "White House (Trump)", "key": key, "languages": [],
            "timestamp": ts, "first_ts": ts, "mimetype": "application/pdf", "original": "https://" + key}


class WhiteHouseUploads(unittest.TestCase):
    def test_dated_by_the_upload_month_not_the_mirror_capture(self):
        d = build_site.entry(upload("2020/04/Guidelines-for-Opening-Up-America-Again.pdf"), {})
        self.assertEqual(d["month"], "2020-04")
        self.assertIn("/web/20210301000000/", d["url"])

    def test_uploads_outside_the_period_are_left_out(self):
        self.assertIsNone(build_site.entry(upload("2019/09/Vaccine-Order.pdf"), {}))
        self.assertIsNone(build_site.entry(upload("2023/06/Wind-Down.pdf"), {}))


if __name__ == "__main__":
    unittest.main()
