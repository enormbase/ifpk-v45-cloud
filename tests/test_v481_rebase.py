"""V48.1 month-precision query and rebasing safe gates. No real API keys."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import rone_live as rl
import cloud_runner as cr


def raw(month, index):
    return {
        'STATBL_ID': rl.TABLE, 'DTACYCLE_CD': 'MM', 'CLS_ID': rl.REGION,
        'CLS_FULLNM': '대전광역시>서구', 'ITM_ID': rl.INDEX, 'ITM_NM': '지수',
        'UI_NM': '지수', 'WRTTIME_IDTFR_ID': month, 'DTA_VAL': str(index),
    }


class RebaseTests(unittest.TestCase):
    def fetch_factory(self, anchor=100., missing=None, wrong_region=False):
        calls=[]
        def fetch(endpoint, params):
            calls.append((endpoint,dict(params)))
            if endpoint == 'SttsApiTbl.do':
                return ([{'STATBL_ID':rl.TABLE,'STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}],1)
            if endpoint == 'SttsApiTblItm.do':
                return ([{'ITM_ID':rl.REGION,'ITM_FULLNM':'대전광역시>서구'}],1)
            if endpoint == 'SttsApiTblData.do':
                if params['pIndex'] != 1: raise AssertionError('unexpected page')
                rows=[]
                for y,m,v in [(2025,12,98.5),(2026,1,98.9),(2026,5,99.8),(2026,6,anchor),
                              (2026,7,100.1),(2026,8,100.2),(2026,9,100.35)]:
                    if f'{y:04d}{m:02d}' == missing: continue
                    rows.append(raw(f'{y:04d}{m:02d}',v))
                if wrong_region: rows[-1]['CLS_ID']='500001'
                return rows,len(rows)
            raise AssertionError(endpoint)
        return fetch,calls

    def test_yyyymm_instead_of_year_only(self):
        fetch,calls=self.fetch_factory()
        got=rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))
        period=next(p for endpoint,p in calls if endpoint=='SttsApiTblData.do')
        self.assertEqual(period['START_WRTTIME'],'201501')
        self.assertEqual(period['END_WRTTIME'],'202611')
        self.assertEqual(got[-1]['date'],'2026-09')
        self.assertEqual(got[-1]['id'],rl.REBASED_INDICATOR)
        self.assertEqual(got[0]['source_code'],rl.REBASED_SOURCE_CODE)

    def test_old_index_identity_never_reused(self):
        fetch,_=self.fetch_factory()
        got=rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))
        self.assertTrue(all(r['id']!=rl.INDICATOR for r in got))
        self.assertIn(rl.REBASED_INDICATOR,cr.ALL_INDICATORS)
        self.assertIn(rl.INDICATOR,cr.ALL_INDICATORS)

    def test_reject_unverified_anchor(self):
        fetch,_=self.fetch_factory(anchor=100.62)
        with self.assertRaisesRegex(ValueError,'기준지수=100'):
            rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))

    def test_reject_missing_anchor(self):
        fetch,_=self.fetch_factory(missing='202606')
        with self.assertRaisesRegex(ValueError,'월간 종료시점'):
            rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))

    def test_reject_foreign_region(self):
        fetch,_=self.fetch_factory(wrong_region=True)
        with self.assertRaisesRegex(ValueError,'다른 지역'):
            rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))

    def test_reject_abrupt_index_splice(self):
        fetch,_=self.fetch_factory()
        def strange(endpoint,params):
            rows,total=fetch(endpoint,params)
            if endpoint=='SttsApiTblData.do':
                rows[-3]['DTA_VAL']='82'
            return rows,total
        with self.assertRaisesRegex(ValueError,'비정상적 변동'):
            rl.collect_rone_202606_verified(strange,now=dt.date(2026,11,9))

    def test_isolated_estimates_stay_provisional(self):
        fetch,_=self.fetch_factory()
        records=rl.collect_rone_202606_verified(fetch,now=dt.date(2026,11,9))
        pub=[{'id':r['id'],'date':r['date'],'value':r['value'],
              'sourceCode':r['source_code'],'retrievedAt':'2026-11-09T00:00:00Z'} for r in records]
        est=next(x for x in cr.calculate_estimates(pub) if x['id']==rl.REBASED_INDICATOR)
        self.assertEqual(est['indexBaseMonth'],'2026-06')
        self.assertEqual(est['status'],'ready')
        self.assertEqual(est['lastMonth'],'2026-09')
        self.assertIsNone(est['rates']['60months'])
        self.assertIsNone(est['illustrative2046By5yrKrw'])
        self.assertFalse(est['approvedPlanChanged'])

    def test_ui_has_version_separation(self):
        html=(ROOT/'docs/index.html').read_text(encoding='utf-8')
        self.assertIn('_BASE202606',html)
        self.assertIn('기존 132개월과 새 기준 원장 분리',html)
        self.assertNotIn('sb_secret_',html)

if __name__=='__main__': unittest.main()
