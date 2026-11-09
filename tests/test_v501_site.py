import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class V501SiteTest(unittest.TestCase):
    def test_customer_first_view_and_disclosure(self):
        html=(ROOT/'docs/index.html').read_text()
        for label in ['경제지표 변화 한눈에 보기','과거 월별 데이터 확인', '수집·수정 이력 확인',
                      '가공·추정 계산과 기준 계획값 확인','6개월 재설계 검토와 계획 변경 전후 비교',
                      '고급 자료·수동 등록·검증 기능']:
            self.assertIn(label,html)
        self.assertIn('function dataPageLegacy()',html)
        self.assertIn('function dataPage()',html)
        self.assertIn('v501Chart(rows,spec.unit)',html)
    def test_rone_alias_not_merged_with_previous_base(self):
        html=(ROOT/'docs/index.html').read_text()
        self.assertIn("'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606'",html)
        self.assertIn("'HOME_PRICE_APT_DAEJEON_SEOGU'",html)
        self.assertIn('const found=V44_LIVE.records.filter(r=>r.id===id',html)
        self.assertIn('est?.rates?.[\'60months\']',html)
        self.assertIn('est?.rates?.[\'120months\']',html)
    def test_revisions_only_from_public_snapshot(self):
        html=(ROOT/'docs/index.html').read_text()
        self.assertIn('V44_LIVE.revisionExported=json.revisionHistoryAvailable===true',html)
        self.assertIn('수정 이력이 없다는 의미는 아닙니다.',html)
        self.assertNotIn('sb_secret_',html)
if __name__=='__main__':unittest.main()
