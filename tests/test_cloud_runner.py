import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'collector'))
import cloud_runner as cr
from ifpk_collector import parse_kosis


class InMemoryStore:
    def __init__(self):
        self.rows={};self.log=[];self.revisions=[]
    def get_observations(self):
        return list(self.rows.values())
    def save_observations(self,new):
        for r in new:
            old=self.rows.get((r['indicator_id'],r['month']))
            if old and float(old['value'])!=float(r['value']):
                self.revisions.append((r['indicator_id'],r['month'],old['value'],r['value']))
            self.rows[r['indicator_id'],r['month']]=r
    def save_run(self,indicator,status,fetched=0,inserted=0,revised=0,message='',started_at=None):
        self.log.insert(0,{'indicator_id':indicator,'status':status,'finished_at':'2026-11-08T10:00:00+00:00','fetched':fetched,'inserted':inserted,'revised':revised,'message':message})
    def get_runs(self):
        return self.log[:1]


def cpi(m,v):
    return parse_kosis([{'ORG_ID':'101','TBL_ID':'DT_1J22003','C1':'T10',
            'ITM_ID':'T','PRD_SE':'M','PRD_DE':m.replace('-',''),'DT':str(v),
            'UNIT_NM':'2020=100','LST_CHN_DE':'2026-11-03'}])[0]

class CloudCollectorTests(unittest.TestCase):
    def setUp(self):
        self.store=InMemoryStore()
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(cr,'DATA',Path(self.tmp.name))
        self.patch.start()
    def tearDown(self):
        self.patch.stop();self.tmp.cleanup()

    def test_first_collection_and_idempotence(self):
        rows=[cpi('2026-09',120.43),cpi('2026-10',120.73)]
        out=cr.execute_cloud(self.store,[('CPI_GENERAL',rows)],'2026-11-08T09:31:27+00:00')
        self.assertEqual(out[0]['inserted'],2)
        self.assertEqual(out[0]['revised'],0)
        out2=cr.execute_cloud(self.store,[('CPI_GENERAL',rows)],'2026-11-09T09:31:27+00:00')
        self.assertEqual((out2[0]['inserted'],out2[0]['revised']),(0,0))
        self.assertEqual(len(self.store.rows),2)
        self.assertEqual(len(self.store.revisions),0)

    def test_revised_data_logged_and_published(self):
        cr.execute_cloud(self.store,[('CPI_GENERAL',[cpi('2026-10',120.73)])])
        out=cr.execute_cloud(self.store,[('CPI_GENERAL',[cpi('2026-10',120.83)])])
        self.assertEqual(out[0]['revised'],1)
        self.assertEqual(len(self.store.revisions),1)
        status=json.loads((cr.DATA/'status.json').read_text())
        public=json.loads((cr.DATA/'public_indicators.json').read_text())
        self.assertTrue(status['published'])
        self.assertEqual(public['records'][0]['value'],120.83)
        self.assertNotIn('SUPABASE_SECRET_KEY',json.dumps(public))
        self.assertEqual(status['officialPlan']['sourceSheetId'],cr.SOURCE_SHEET_ID)
        self.assertFalse(status['officialPlan']['automaticUpdates'])

    def test_wrong_indicator_rejected(self):
        with self.assertRaises(ValueError):
            cr.execute_cloud(self.store,[('CPI_CAR',[cpi('2026-10',120.73)])])

    def test_ma3_and_gaps(self):
        records=[]
        for m,v in [('2026-01',100),('2026-02',105),('2026-03',110)]:
            records.append({'id':'CPI_CAR','date':m,'value':v,'retrievedAt':'2026-11-08'})
        x=next(e for e in cr.calculate_estimates(records) if e['id']=='CPI_CAR')
        self.assertEqual(x['value'],105)
        records[1]['date']='2026-04'
        x=next(e for e in cr.calculate_estimates(records) if e['id']=='CPI_CAR')
        self.assertEqual(x['status'],'insufficient_or_gapped')

    def test_initial_user_34month_snapshot(self):
        path=PROJECT/'docs/data/public_indicators.json'
        if not path.exists():
            self.skipTest('Optional bundled initial data not present')
        self.assertEqual(cr.dry_run(path),34)
        st=json.loads((cr.DATA/'status.json').read_text())
        p=json.loads((cr.DATA/'public_indicators.json').read_text())
        self.assertFalse(st['published'])
        self.assertEqual(p['estimates'][0]['lastMonth'],'2026-10')
        self.assertEqual(p['estimates'][0]['value'],120.73)

    def test_new_supabase_key_uses_apikey_not_jwt(self):
        captured=[]
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n=0):return b'[]'
        def fake_fetch(req,timeout=None):
            captured.append(req)
            return FakeResponse()
        st=cr.SupabaseStore('https://demo.supabase.co','sb_secret_testtesting1234',fetch=fake_fetch)
        self.assertEqual(st.request('GET','ifpk_observations'),[])
        headers={k.lower():v for k,v in captured[0].header_items()}
        self.assertIn('apikey',headers)
        self.assertNotIn('authorization',headers)

    def test_bad_supabase_url_rejected(self):
        for s in ['http://project.supabase.co','https://project.supabase.co/rest/v1','http://127.0.0.1:8000']:
            with self.assertRaises(ValueError):cr._validate_url(s)

    def test_public_snapshot_excludes_provider_keys(self):
        p,s=cr.prepare_snapshots([{'id':'CPI_GENERAL','date':'2026-10','value':120.73,'provider':'KOSIS',
         'unit':'2020=100','sourceCode':'101/DT_1J22003/T10/T','sourceUpdated':'2026-10-30',
         'retrievedAt':'2026-11-08T09:31:27Z'}],[],live=False)
        self.assertEqual(s['counts'][0]['count'],1)
        self.assertEqual(s['counts'][0]['firstMonth'],'2026-10')
        self.assertFalse(s['published'])
        self.assertIn('sourceUpdated',p['records'][0])

if __name__=='__main__':unittest.main()
