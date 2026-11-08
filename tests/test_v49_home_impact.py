"""V49: approved housing plan stays frozen while public-indicator previews move."""
from __future__ import annotations
import datetime as dt
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'collector'))
from home_impact import PLAN, payment, principal_from_payment, savings_monthly, scenario, calculate_home_impact
from cloud_runner import prepare_snapshots

TODAY=dt.date(2026,11,9)

def observed():
    return [
        {'id':'DEPOSIT','status':'ready','value':2.5676,'lastMonth':'2026-09'},
        {'id':'MORTGAGE','status':'ready','value':3.9714,'lastMonth':'2026-09'},
        {'id':'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606','status':'ready','indexBaseMonth':'2026-06',
         'lastMonth':'2026-09','rates':{'60months':-3.237,'120months':2.772}},
    ]

class HomeImpactTests(unittest.TestCase):
    def test_approved_snapshot_never_moves(self):
        r=calculate_home_impact(observed(),TODAY)
        self.assertEqual(r['status'],'ready')
        self.assertFalse(r['approvedPlanChanged'])
        old=r['approved']
        self.assertEqual([old[k] for k in ['newHomeFuture','oldHomeFuture','oldDebtAtMove','newMortgagePrincipal',
            'ownCashGoal','monthlySaving','monthlyLoanPayment']],
            [763747266,362779952,104117759,363598263,141486810,345345,1675319])

    def test_approved_savings_reproduce_original_unrounded(self):
        m,fv=savings_monthly(PLAN['approvedOwnCash'],PLAN['savedFundNow'],PLAN['baseNetDepositRatePct'],239)
        self.assertLess(abs(m-PLAN['approvedMonthlySave']),3)
        self.assertGreater(fv,PLAN['savedFundNow'])

    def test_rate_only_new_savings_and_cap(self):
        r=calculate_home_impact(observed(),TODAY)
        v=next(s for s in r['scenarios'] if s['id']=='rates_only')
        self.assertEqual(v['newHomeFuture'],PLAN['baseFutureNewPrice'])
        self.assertGreater(v['monthlySaving'],PLAN['approvedMonthlySave'])
        self.assertLess(v['newMortgagePrincipal'],PLAN['approvedLoanMax'])
        self.assertLessEqual(v['monthlyLoanPayment'],PLAN['approvedMonthlyLoan']+2)
        self.assertGreater(v['fixedPrincipalLoanPayment'],PLAN['approvedMonthlyLoan'])

    def test_weighted_cagr_not_overwritten(self):
        r=calculate_home_impact(observed(),TODAY)
        w=next(s for s in r['scenarios'] if s['id']=='weighted')
        self.assertAlmostEqual(w['growthPct'],(-3.237+2.772)/2)
        self.assertEqual(r['assumptions']['basePriceGrowthPct'],-0.233)
        self.assertEqual(r['approved']['growthPct'],-0.233)

    def test_loan_never_overfinances_purchase(self):
        r=calculate_home_impact(observed(),TODAY)
        for s in r['scenarios']:
            self.assertLessEqual(s['newMortgagePrincipal'],s['ltvLimit']+1)
            self.assertLessEqual(s['newMortgagePrincipal'],s['dsrProxyLimit']+1)
            self.assertLessEqual(s['newMortgagePrincipal'],max(0,s['newHomeFuture']-s['saleNet']))
            self.assertGreaterEqual(s['ownCashGoal'],0)
            self.assertGreaterEqual(s['monthlySaving'],0)

    def test_mortgage_principal_payment_inverse(self):
        for annual in (0,1.5,3.9714,12):
            p=principal_from_payment(1675319,annual,360)
            self.assertAlmostEqual(payment(p,annual,360),1675319,places=5)

    def test_stale_rate_yields_no_new_scenarios(self):
        x=observed();x[0]['lastMonth']='2025-10'
        r=calculate_home_impact(x,TODAY)
        self.assertEqual(r['status'],'pending');self.assertEqual(r['scenarios'],[])

    def test_stale_region_yields_rates_only(self):
        x=observed();x[2]['lastMonth']='2025-10'
        r=calculate_home_impact(x,TODAY)
        self.assertEqual(r['status'],'partial')
        self.assertEqual([c['id'] for c in r['scenarios']],['rates_only'])

    def test_insufficient_cagr_yields_no_price_scenario(self):
        x=observed();x[2]['rates']['120months']=None
        r=calculate_home_impact(x,TODAY)
        self.assertEqual(r['status'],'partial')
        self.assertEqual(len(r['scenarios']),1)

    def test_mortgage_payment_positive_normal(self):
        self.assertAlmostEqual(payment(363598263,3.70845,360),1675319.179,places=2)

    def test_cloud_snapshots_include_home_impact_not_writes(self):
        public,status=prepare_snapshots([],[],live=False)
        self.assertEqual(public['homeImpact']['status'],'pending')
        self.assertEqual(status['homeImpact']['approved']['monthlySaving'],345345)
        self.assertFalse(status['homeImpact']['approvedPlanChanged'])

    def test_invalid_growth_blocked(self):
        with self.assertRaises(ValueError):
            scenario('bad',-101,3,2)

if __name__=='__main__':unittest.main()
