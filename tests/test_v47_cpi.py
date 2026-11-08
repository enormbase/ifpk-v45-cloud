import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
from cpi_special import item_metadata,pick_verified_item,fetch_item_catalog,collect_special_cpis
from cloud_runner import calculate_estimates,prepare_snapshots


def _catalog(names=None):
    names=names or [('대형승용차','AUTOLARGE'),('해외단체여행비','TRIPOVERSEA'),('소형승용차','AUTOSMALL')]
    return {'StatisticItemList':{'list_total_count':len(names),'row':[
        {'GRP_CODE':'Group1','ITEM_NAME':name,'ITEM_CODE':code} for name,code in names]}}

def _months(start_y,start_m,n):
    idx=start_y*12+start_m-1
    return [f'{(idx+i)//12:04d}-{(idx+i)%12+1:02d}' for i in range(n)]

def _observations(ident,n,values=None):
    dates=_months(2024,1,n)
    vals=values if values is not None else [100+i*.5 for i in range(n)]
    return [{'id':ident,'date':m,'value':v,'unit':'지수','provider':'ECOS',
             'sourceCode':'901Y009/CODE','retrievedAt':'2026-11-09T00:00:00Z'} for m,v in zip(dates,vals)]

class V47CpiTests(unittest.TestCase):
    def test_exact_names_only(self):
        rows,total=item_metadata(_catalog())
        self.assertEqual(total,3)
        self.assertEqual(pick_verified_item(rows,'대형승용차'),'AUTOLARGE')
        self.assertEqual(pick_verified_item(rows,'해외단체여행비'),'TRIPOVERSEA')
        with self.assertRaises(ValueError): pick_verified_item(rows,'승용차')

    def test_group2_ignored_and_ambiguity_rejected(self):
        rows,_=item_metadata(_catalog())
        rows.append({'ITEM_NAME':'대형승용차','ITEM_CODE':'OTHER','GRP_CODE':'Group2'})
        self.assertEqual(pick_verified_item(rows,'대형승용차'),'AUTOLARGE')
        rows.append({'ITEM_NAME':'대형승용차','ITEM_CODE':'OTHER','GRP_CODE':'Group1'})
        with self.assertRaises(ValueError): pick_verified_item(rows,'대형승용차')

    def test_missing_or_bad_api_response_rejected(self):
        with self.assertRaises(ValueError):item_metadata({'RESULT':{'CODE':'ERROR-100'}})
        with self.assertRaises(ValueError):pick_verified_item([{'GRP_CODE':'Group1','ITEM_NAME':'해외단체여행비','ITEM_CODE':'이상한코드'}],'해외단체여행비')

    def test_pagination_requires_all(self):
        names=[(f'샘플{i}',f'X{i}') for i in range(500)]+[('대형승용차','L'),('해외단체여행비','T')]
        def fake_fetch(url):
            start=int(url.split('/json/kr/')[1].split('/')[0])-1
            return {'StatisticItemList':{'list_total_count':502,'row':[
               {'GRP_CODE':'Group1','ITEM_NAME':name,'ITEM_CODE':code} for name,code in names[start:start+500]]}}
        self.assertEqual(len(fetch_item_catalog('FAKE_KEY',fetch=fake_fetch)),502)

    def test_collect_pulls_only_verified_codes(self):
        requested=[]
        def mock_get_data(key,series,start):
            requested.append((series['id'],series['item_filters']['ITEM_CODE1'],start))
            n=13 if series['id']=='CPI_TRAVEL' else 4
            return [{'id':series['id'],'date':m,'value':100.0,'unit':'지수','provider':'ECOS',
                     'source_code':'901Y009/'+series['item_filters']['ITEM_CODE1'],'source_updated':''} for m in _months(2025,1,n)]
        tasks=collect_special_cpis('FAKE_KEY',fetch=lambda u:_catalog(),get_data=mock_get_data)
        self.assertEqual([x[0] for x in tasks],['CPI_CAR','CPI_TRAVEL'])
        self.assertEqual(requested,[('CPI_CAR','AUTOLARGE','201601'),('CPI_TRAVEL','TRIPOVERSEA','201601')])

    def test_rolling_and_source_metadata(self):
        car=_observations('CPI_CAR',3,[114.5,115.0,116.5])
        trip=_observations('CPI_TRAVEL',12,[100.0]*11+[124.0])
        est=calculate_estimates(car+trip)
        c=next(x for x in est if x['id']=='CPI_CAR')
        t=next(x for x in est if x['id']=='CPI_TRAVEL')
        self.assertEqual(c['rollingMonths'],3)
        self.assertEqual(t['rollingMonths'],12)
        self.assertAlmostEqual(c['value'],(114.5+115+116.5)/3)
        self.assertAlmostEqual(t['value'],102)
        self.assertEqual(c['windowStart'],'2024-01')
        self.assertEqual(t['windowStart'],'2024-01')
        self.assertEqual(t['sourceCode'],'901Y009/CODE')
        _,status=prepare_snapshots(car+trip,[],live=True)
        self.assertFalse(status['officialPlan']['automaticUpdates'])

    def test_optional_cpi_failure_keeps_existing_sources_running(self):
        from unittest.mock import patch
        from cloud_runner import gather_official_sources
        with patch('cloud_runner.get_kosis',return_value=[{'id':'CPI_GENERAL'}]), \
             patch('cloud_runner.load_ecos_series',return_value=[{'id':'DEPOSIT'}]), \
             patch('cloud_runner.get_ecos',return_value=[{'id':'DEPOSIT'}]), \
             patch('cloud_runner.collect_special_cpis',side_effect=ValueError('품목코드 미확인')), \
             patch('cloud_runner.os.getenv',side_effect=lambda name,default='': {'KOSIS_API_KEY':'KEY','ECOS_API_KEY':'ECOS'}.get(name,default)):
            result=gather_official_sources()
        self.assertEqual([x[0] for x in result],['CPI_GENERAL','DEPOSIT','CPI_CAR','CPI_TRAVEL'])
        self.assertEqual(result[-1][1]['error'].split(':')[0],'품목별 CPI 공식 코드 확인 보류')

    def test_gap_prevents_average(self):
        bad=_observations('CPI_TRAVEL',12)
        bad[-4]['date']='2023-04'
        item=next(x for x in calculate_estimates(bad) if x['id']=='CPI_TRAVEL')
        self.assertEqual(item['status'],'insufficient_or_gapped')
        self.assertIsNone(item['value'])

if __name__=='__main__':unittest.main()
