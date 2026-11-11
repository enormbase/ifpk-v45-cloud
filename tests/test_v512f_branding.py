from pathlib import Path
import unittest

HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")

class VersionDisplayTest(unittest.TestCase):
    def test_topbar(self):
        self.assertIn("LIFE PLAN STUDIO · IFPK V56", HTML)
        self.assertNotIn("LIFE PLAN STUDIO · IFPK V51-2e", HTML)

    def test_title_and_footer(self):
        self.assertIn("대시보드 V56</title>", HTML)
        self.assertIn("V56 전체요약 타임라인 개편 · V55 월별 저축배분 유지", HTML)

    def test_module_present(self):
        self.assertIn("./js/debt_retirement_v512f.js", HTML)
        self.assertIn("⑨ 기존 대출과 은퇴자산", HTML)

if __name__ == "__main__":
    unittest.main()
