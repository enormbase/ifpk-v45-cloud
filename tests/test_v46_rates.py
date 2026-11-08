import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
from cloud_runner import calculate_estimates, prepare_snapshots


def months_from(y,m,n):
    out=[]
    for i in range(n):
        j=y*12+(m-1)+i
        out.append(f'{j//12:04d}-{j%12+1:02d}')
    return out

def records(series,months,values):
    return [{'id':series,'date':m,'value':v,'unit':'%', 'provider':'ECOS',
             'sourceCode':'test/verified','retrievedAt':'2026-11-08T13:10:00+00:00'}
             for m,v in zip(months,values)]

class V46RatesTests(unittest.TestCase):
    def test_rate_details_and_baseline(self):
        dates=months_from(2016,1,129)
        # 129 months: latest 60 / 120 exercise the entire window.
        d=records('DEPOSIT',dates,[3.035]*129)
        h=records('MORTGAGE',dates,[3.0]*69+[4.1525]*60)
        data=calculate_estimates(d+h)
        dep=next(x for x in data if x['id']=='DEPOSIT')
        mort=next(x for x in data if x['id']=='MORTGAGE')
        self.assertEqual(dep['status'],'ready')
        self.assertEqual(dep['observedMonths60'],60)
        self.assertAlmostEqual(dep['grossAverage60'],3.035)
        self.assertAlmostEqual(dep['value'],2.56761)
        self.assertGreater(dep['monthlyEquivalentRate'],0)
        self.assertEqual(mort['status'],'ready')
        self.assertEqual(mort['observedMonths120'],120)
        self.assertAlmostEqual(mort['grossAverage60'],4.1525)
        self.assertAlmostEqual(mort['grossAverage120'],(60*4.1525+60*3.0)/120)
        self.assertAlmostEqual(mort['value'], .7*4.1525+.3*((60*4.1525+60*3.0)/120))
        self.assertEqual(mort['sourceCode'],'test/verified')
        _,status=prepare_snapshots(d+h,[],live=True)
        self.assertTrue(status['credentialsConfigured']['ECOS'])

    def test_short_series_is_not_publishable_rate(self):
        dates=months_from(2026,1,9)
        rates=calculate_estimates(records('DEPOSIT',dates,[3.0]*9))
        dep=next(x for x in rates if x['id']=='DEPOSIT')
        self.assertEqual(dep['status'],'insufficient_or_gapped')
        self.assertIsNone(dep['value'])
        self.assertNotIn('grossAverage60',dep)

    def test_gap_in_last_120_blocks_mortgage_rate(self):
        dates=months_from(2016,1,129)
        dates[80]='2020-12' # create a missing/duplicate or wrong month inside the trailing window
        # calculate_estimates sorts; a gap invalidates its last 120 sequence.
        val=calculate_estimates(records('MORTGAGE',dates,[3.5]*129))
        mort=next(x for x in val if x['id']=='MORTGAGE')
        self.assertEqual(mort['status'],'insufficient_or_gapped')
        self.assertIsNone(mort['value'])

    def test_financial_plan_is_not_in_snapshot(self):
        months=months_from(2020,1,129)
        data=records('DEPOSIT',months,[3.1]*129)
        pub,st=prepare_snapshots(data,[],live=True)
        self.assertFalse(st['officialPlan']['automaticUpdates'])
        self.assertNotIn('customer',json.dumps(pub).lower())
        self.assertIn('grossAverage60',json.dumps(pub))

if __name__=='__main__': unittest.main()
