"""UI/indicator compatibility checks updated for V63.

The retired advanced six-month review surface is no longer part of the
rendered economic-data page. Its replacement explains monthly rolling.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V501SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')

    def test_customer_first_view_and_disclosure(self):
        # Check the live data and monthly-execution UI, not the deleted
        # "6개월 재설계 · 6개 분야 변경 전후 검토" panel.
        for label in [
            '경제지표 변화 한눈에 보기',
            '과거 월별 데이터 확인',
            '수집·수정 이력 확인',
            '현재 계획과 새 계산값 비교',
            '우리 가족의 저축 실행 현황',
            '월별 롤링 계산 원칙 확인',
        ]:
            with self.subTest(label=label):
                self.assertIn(label, self.html)

        self.assertNotIn('6개월 재설계 · 6개 분야 변경 전후 검토', self.html)
        self.assertIn('function dataPageLegacy()', self.html)
        self.assertIn('function dataPage()', self.html)
        self.assertIn('v501Chart(rows,spec.unit)', self.html)
        self.assertIn("gdPatternPlan('home')", self.html)
        self.assertIn("gdPatternPlan('travel')", self.html)
        self.assertIn('data-gd-go-customer-spend', self.html)

    def test_rone_alias_not_merged_with_previous_base(self):
        html = self.html
        self.assertIn("const oldId='HOME_PRICE_APT_DAEJEON_SEOGU'", html)
        self.assertIn("const newId=oldId+'_BASE202606'", html)
        self.assertIn('function v501Data(spec)', html)
        self.assertIn('const found=V44_LIVE.records.filter(r=>r.id===id', html)
        self.assertIn("est?.rates?.['60months']", html)
        self.assertIn("est?.rates?.['120months']", html)

    def test_revisions_only_from_public_snapshot(self):
        html = self.html
        self.assertIn('V44_LIVE.revisionExported=json.revisionHistoryAvailable===true', html)
        self.assertIn('수정 이력이 없다는 의미는 아닙니다.', html)
        self.assertNotIn('sb_secret_', html)


if __name__ == '__main__':
    unittest.main()
