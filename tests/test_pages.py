import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import pages  # noqa: E402


class Measure(unittest.TestCase):
    def test_counts_only_changed_captures(self):
        caps = [("20200301000000", "A", 5000), ("20200302000000", "A", 9000),
                ("20200315000000", "B", 6000), ("20200401000000", "B", 6000),
                ("20200402000000", "C", 1000)]
        head, body = pages.measure("k", "www.x.gov/", caps)
        self.assertEqual(head, "#k|www.x.gov/|3|20200301000000|20200402000000")
        # March: A then B, median of 5,000 and 6,000 bytes; April: C only.
        self.assertEqual(body, "202003:01000000:2:5.5 202004:02000000:1:1")

    def test_no_captures(self):
        self.assertIsNone(pages.measure("k", "www.x.gov/", []))

    def test_every_measured_page_is_listed(self):
        listed = dict(pages.load_list())
        self.assertTrue(set(pages.load_measured()) <= set(listed))


if __name__ == "__main__":
    unittest.main()
