import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collector'))
from rone_probe import unpack,is_daejeon_seogu,month_of,summarize,candidate_rows

class ROneProbeTests(unittest.TestCase):
 def test_provider_envelope(self):
  data={'SttsApiTblData':[{'head':[{'list_total_count':2}]},{'row':[{'x':1},{'x':2}]}]}
  self.assertEqual(unpack(data,'SttsApiTblData')[1],2)
  self.assertEqual(len(unpack(data,'SttsApiTblData')[0]),2)
 def test_daejeon_not_other_seogu(self):
  self.assertTrue(is_daejeon_seogu({'CLS_FULLNM':'대전>서구','CLS_NM':'서구'}))
  self.assertTrue(is_daejeon_seogu({'CLS_NM':'서구','GRP_NM':'대전광역시'}))
  self.assertFalse(is_daejeon_seogu({'CLS_FULLNM':'부산>서구','CLS_NM':'서구'}))
  self.assertFalse(is_daejeon_seogu({'CLS_NM':'서구'}))
  self.assertFalse(is_daejeon_seogu({'CLS_NM':'중구','GRP_NM':'대전광역시'}))
 def test_month_formats(self):
  self.assertEqual(month_of({'WRTTIME_IDTFR_ID':'202609'}),'2026-09')
  self.assertEqual(month_of({'WRTTIME_DESC':'2026년 9월'}),'2026-09')
  self.assertIsNone(month_of({'WRTTIME_DESC':'2026년'}))
 def test_candidates_and_aggregation(self):
  base={'CLS_FULLNM':'대전>서구','CLS_ID':'501123','ITM_ID':'10001','ITM_NM':'매매가격지수','UI_NM':'2021.6=100'}
  rows=[{**base,'WRTTIME_IDTFR_ID':'202608','DTA_VAL':'99.01'},
        {**base,'WRTTIME_IDTFR_ID':'202609','DTA_VAL':'100.5'},
        {'CLS_FULLNM':'부산>서구','CLS_ID':'501999','ITM_ID':'10001','WRTTIME_IDTFR_ID':'202609','DTA_VAL':'91.3'}]
  out=summarize(rows)
  self.assertEqual(len(out),1)
  self.assertEqual(out[0]['months'],2)
  self.assertEqual(out[0]['latest_value'],100.5)
  self.assertEqual(out[0]['cls_id'],'501123')
 def test_refuse_unverified_metadata(self):
  rows=[{'CLS_NM':'서구','ITM_ID':'1','CLS_ID':'2','DTA_VAL':'100','WRTTIME_IDTFR_ID':'202609'}]
  self.assertEqual(candidate_rows(rows),[])
  with self.assertRaises(ValueError):unpack({'RESULT':{'CODE':'ERROR'}},'SttsApiTblData')


class ROneResultDiagnosticsTests(unittest.TestCase):
 def test_monthly_cycle_in_metadata_request(self):
  from unittest.mock import patch
  from rone_probe import run
  with patch.dict('os.environ', {'RONE_API_KEY':'local-only-test'}):
   with patch('rone_probe.request_json') as mocked:
    mocked.return_value={'SttsApiTbl':[{'head':[{'list_total_count':1}]},{'row':[{'STATBL_ID':'A_2024_00045','STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}]}]}
    # Stop after metadata call, only inspect args.
    with patch('rone_probe.unpack', side_effect=ValueError('stop-after-request')):
     with self.assertRaisesRegex(ValueError, 'stop-after-request'):run()
    self.assertEqual(mocked.call_args.args[0], 'SttsApiTbl.do')
    self.assertEqual(mocked.call_args.args[1]['DTACYCLE_CD'], 'MM')
 def test_safe_result_code_diagnostics(self):
  import json,io
  from unittest.mock import patch
  from rone_probe import request_json
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*a):return False
   def read(self,*a):return json.dumps({'RESULT':{'CODE':'300','MESSAGE':'KEY=SUPERSECRET'}}).encode()
  with patch.dict('os.environ', {'RONE_API_KEY':'SUPERSECRET'}):
   with self.assertRaises(ValueError) as err:
    request_json('SttsApiTbl.do',{},opener=lambda request,timeout:Reply())
  self.assertIn('300', str(err.exception))
  self.assertNotIn('SUPERSECRET',str(err.exception))

if __name__=='__main__':unittest.main()
