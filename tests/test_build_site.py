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


if __name__ == "__main__":
    unittest.main()
