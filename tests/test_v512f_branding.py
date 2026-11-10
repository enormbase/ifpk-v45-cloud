from pathlib import Path
import unittest

HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")

class VersionDisplayTest(unittest.TestCase):
    def test_topbar(self):
        self.assertIn("LIFE PLAN STUDIO · IFPK V51-3f", HTML)
        self.assertNotIn("LIFE PLAN STUDIO · IFPK V51-2e", HTML)

    def test_title_and_footer(self):
        self.assertIn("대시보드 V51-3f</title>", HTML)
        self.assertIn("V51-3f 고객용 재설계 현황", HTML)

    def test_module_present(self):
        self.assertIn("./js/debt_retirement_v512f.js", HTML)
        self.assertIn("⑨ 기존 대출과 은퇴자산", HTML)

if __name__ == "__main__":
    unittest.main()
