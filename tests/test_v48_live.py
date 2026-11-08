"""V48 R-ONE integration tests: no external calls, no personal data."""
import datetime as dt
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import rone_live as r
import cloud_runner as cr


def fixture_rows(month, val=101.812228900096):
    return {'STATBL_ID':r.TABLE,'DTACYCLE_CD':'MM','CLS_ID':r.REGION,
            'CLS_FULLNM':'대전광역시>서구','CLS_NM':'서구','ITM_ID':r.INDEX,
            'ITM_NM':'지수','UI_NM':'지수',
            'WRTTIME_IDTFR_ID':month.replace('-',''),'DTA_VAL':str(val)}


def mocked_fetch(endpoint, params):
    if endpoint == 'SttsApiTbl.do':
        return ([{'STATBL_ID':r.TABLE,'STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}],1)
    if endpoint == 'SttsApiTblItm.do':
        return ([{'ITM_ID':r.REGION,'ITM_FULLNM':'대전광역시>서구'}],1)
    if endpoint == 'SttsApiTblData.do':
        if params['pIndex'] > 1: return ([],2)
        return ([fixture_rows('2024-09'),fixture_rows('2024-10',102.12)],2)
    raise AssertionError(endpoint)


def series(count, end='2026-09', pct_year=3.0):
    y,m=map(int,end.split('-'))
    last=y*12+m-1
    result=[]
    for i in range(count-1,-1,-1):
        x=last-i
        result.append({'id':r.INDICATOR,'date':f'{x//12:04d}-{x%12+1:02d}',
                       'value':100*(1+pct_year/100)**((count-1-i)/12),
                       'unit':'지수','provider':'R-ONE','sourceCode':r.SOURCE_CODE,
                       'retrievedAt':'2026-11-08T18:40:00Z'})
    return result


class RoneLiveTests(unittest.TestCase):
    def test_metadata_period_fetch_and_real_verified_codes(self):
        observed=[]
        def fetch(endpoint, params):
            observed.append((endpoint, dict(params)))
            return mocked_fetch(endpoint, params)
        got=r.collect_rone_monthly(fetch=fetch,now=dt.date(2026,11,9))
        self.assertEqual(len(got),2)
        self.assertEqual((got[0]['date'],got[0]['value']),('2024-09',101.812228900096))
        self.assertEqual(got[0]['source_code'],r.SOURCE_CODE)
        self.assertEqual([x for x in observed if x[0]=='SttsApiTblData.do'][0][1]['CLS_ID'],r.REGION)
        self.assertEqual([x for x in observed if x[0]=='SttsApiTblData.do'][0][1]['ITM_ID'],r.INDEX)

    def test_reject_mixed_regions_before_saving(self):
        def fetch(endpoint,params):
            rows, total=mocked_fetch(endpoint,params)
            if endpoint=='SttsApiTblData.do':rows[1]['CLS_ID']='500001'
            return rows,total
        with self.assertRaisesRegex(ValueError,'다른 지역'):
            r.collect_rone_monthly(fetch=fetch,now=dt.date(2026,11,9))

    def test_reject_metadata_region_mismatch(self):
        def fetch(endpoint,params):
            rows,total=mocked_fetch(endpoint,params)
            if endpoint=='SttsApiTblItm.do': rows[0]['ITM_FULLNM']='충북>청주'
            return rows,total
        with self.assertRaisesRegex(ValueError,'메타데이터'):
            r.collect_rone_monthly(fetch=fetch,now=dt.date(2026,11,9))

    def test_fallback_single_month_never_fabricates_history(self):
        def fetch(endpoint,params):
            if endpoint=='SttsApiTblData.do':
                if 'START_WRTTIME' in params:return [],0
                return [fixture_rows('2024-09')],1
            return mocked_fetch(endpoint,params)
        result=r.collect_rone_monthly(fetch=fetch,now=dt.date(2026,11,9))
        self.assertEqual(len(result),1)
        est=r.calculate_home_reference([{'date':x['date'],'value':x['value']} for x in result], current=dt.date(2026,11,9))
        self.assertTrue(est['stale'])
        self.assertIsNone(est['rates']['60months'])
        self.assertIsNone(est['illustrative2046By5yrKrw'])

    def test_5_and_10_year_cagr_with_complete_months(self):
        entry=r.calculate_home_reference(series(121),current=dt.date(2026,11,9))
        self.assertEqual(entry['status'],'ready')
        self.assertAlmostEqual(entry['rates']['12months'],3,places=8)
        self.assertAlmostEqual(entry['rates']['60months'],3,places=8)
        self.assertAlmostEqual(entry['rates']['120months'],3,places=8)
        self.assertEqual(entry['illustrative2046By5yrKrw'],round(400_000_000*1.03**20))
        self.assertFalse(entry['approvedPlanChanged'])

    def test_monthly_gap_blocks_cagr(self):
        rows=series(121)
        rows=[x for x in rows if x['date']!='2024-09']
        entry=r.calculate_home_reference(rows,current=dt.date(2026,11,9))
        self.assertIsNone(entry['rates']['60months'])
        self.assertIsNone(entry['rates']['120months'])

    def test_stale_last_month_blocks_projection(self):
        entry=r.calculate_home_reference(series(121,end='2024-09'),current=dt.date(2026,11,9))
        self.assertEqual(entry['status'],'stale')
        self.assertIsNone(entry['rates']['120months'])
        self.assertIsNone(entry['illustrative2046By10yrKrw'])

    def test_new_id_passes_cloud_normalization_and_uses_isolated_model(self):
        rows=[{'indicator_id':r.INDICATOR,'month':'2026-09','value':101.8,
               'unit':'지수','provider':'R-ONE','source_code':r.SOURCE_CODE,
               'source_updated':'','retrieved_at':'2026-11-08T13:00:00Z'}]
        public=cr.normalize_public_rows(rows)
        self.assertEqual(public[0]['id'],r.INDICATOR)
        est=next(x for x in cr.calculate_estimates(public) if x['id']==r.INDICATOR)
        self.assertEqual(est['latestObservedIndex'],101.8)
        self.assertIsNone(est['rates']['60months'])

    def test_failure_does_not_disrupt_existing_cloud_tasks(self):
        class Store:
            def __init__(self):self.rows={};self.events=[]
            def get_observations(self):return list(self.rows.values())
            def save_observations(self,x):
                for y in x:self.rows[y['indicator_id'],y['month']]=y
            def save_run(self,ind,status,**kw):self.events.append((ind,status))
            def get_runs(self):return []
        store=Store()
        cpi={'id':'CPI_GENERAL','date':'2026-10','value':120.73,'unit':'2020=100',
             'provider':'KOSIS','source_code':'101/DT_1J22003/T10/T','source_updated':''}
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch.object(cr,'DATA',Path(d)):
            result=cr.execute_cloud(store,[('CPI_GENERAL',[cpi]),(r.INDICATOR,{'error':'R-ONE 조회 실패'})])
            self.assertEqual([x['status'] for x in result],['ok','failed'])
            self.assertEqual(len(store.rows),1)
            self.assertTrue((Path(d)/'status.json').exists())

    def test_workflow_has_secret_and_html_does_not(self):
        workflow=(ROOT/'.github/workflows/ifpk-cloud-refresh.yml').read_text()
        self.assertIn('python collector/cloud_runner.py',workflow)
        html=(ROOT/'docs/index.html').read_text()
        self.assertIn('roneCardsV48(st)',html)
        self.assertNotIn('sb_secret_',html)

if __name__=='__main__':unittest.main()
