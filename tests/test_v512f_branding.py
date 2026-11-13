from pathlib import Path
import unittest

HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")

class VersionDisplayTest(unittest.TestCase):
    def test_topbar(self):
        self.assertIn("LIFE PLAN STUDIO · IFPK</small>", HTML)
        self.assertNotIn("LIFE PLAN STUDIO · IFPK V51-2e", HTML)

    def test_title_and_footer(self):
        self.assertIn("대시보드</title>", HTML)
        self.assertIn("4대 목적저축 · 최신 경제지표 · 월별 현금흐름", HTML)

    def test_module_present(self):
        self.assertIn("./js/debt_retirement_v512f.js", HTML)
        self.assertIn("⑨ 기존 대출과 은퇴자산", HTML)

if __name__ == "__main__":
    unittest.main()
