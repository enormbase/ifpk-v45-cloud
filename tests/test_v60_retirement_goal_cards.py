"""V60 retirement goal screen must match 2026-11 canonical 4-goal baseline."""
from pathlib import Path
import json
import unittest
ROOT = Path(__file__).resolve().parents[1]
S = (ROOT/'docs/index.html').read_text(encoding='utf-8')
SNAP = json.loads((ROOT/'docs/data/v55_monthly_savings_snapshot.json').read_text('utf-8'))

class RetirementGoalCardsTest(unittest.TestCase):
    def test_retirement_target_identity(self):
        self.assertEqual(SNAP['retirementTotalNeed'],640166067)
        self.assertEqual(SNAP['dcRetirement'],414925772)
        self.assertEqual(next(g for g in SNAP['goals'] if g['id']=='ret')['total'],225240295)
        self.assertEqual(SNAP['retirementTotalNeed']-SNAP['dcRetirement'],225240295)

    def test_retirement_cards_use_new_goal_structure(self):
        section=S[S.index("if(goal==='은퇴'){",S.index('function gdGoalContent(goal)')):S.index("if(goal==='주택'){",S.index('function gdGoalContent(goal)'))]
        for expected in ["['필요 은퇴자금',needed", "['DC형 퇴직연금 예상자산',RV_DC_TAXED", "['추가 은퇴저축 목표',RV_PERSONAL_GOAL",'rvPersonalChart()','gdSegmentChart']:
            self.assertIn(expected,section)
        for stale in ['MODEL.metrics.initialRetirement','635553777','80984826','253327174']:
            self.assertNotIn(stale,section)

    def test_retirement_forecast_separate_from_target(self):
        for expected in ['const RV_SAVINGS_FV=218417648','const RV_TOTAL_EXPECTED=RV_DC_TAXED+RV_SAVINGS_FV','const RV_PROJECTED_GAP=RV_PERSONAL_GOAL-RV_SAVINGS_FV','2082년 9월','잔액 0원은 목표 달성이 아니라 자산 소진']:
            self.assertIn(expected,S)

if __name__=='__main__':unittest.main()
