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
 def test_table_discovery_uses_full_list_and_monthly_cycle(self):
  from rone_probe import choose_table
  self.assertEqual(choose_table([{'STATBL_ID':'A_2024_00045','STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}])['STATBL_ID'],'A_2024_00045')
  with self.assertRaises(ValueError):choose_table([{'STATBL_ID':'A_2024_00178','STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}])
 def test_xml_parsing_and_empty_result(self):
  from unittest.mock import patch
  from rone_probe import fetch_xml_rows
  class Reply:
   def __init__(self,p): self.p=p
   def __enter__(self):return self
   def __exit__(self,*a):return False
   def read(self,*args):return self.p
  payload=b'<SttsApiTbl><head><list_total_count>1</list_total_count><RESULT><CODE>INFO-000</CODE></RESULT></head><row><STATBL_ID>A_2024_00045</STATBL_ID></row></SttsApiTbl>'
  with patch.dict('os.environ',{'RONE_API_KEY':'SUPERSECRET'}):
   rows,n=fetch_xml_rows('SttsApiTbl.do',{},opener=lambda req,timeout:Reply(payload))
   self.assertEqual(n,1);self.assertEqual(rows[0]['STATBL_ID'],'A_2024_00045')
   empty=b'<SttsApiTbl><RESULT><CODE>INFO-200</CODE></RESULT></SttsApiTbl>'
   rows,n=fetch_xml_rows('SttsApiTbl.do',{},opener=lambda req,timeout:Reply(empty))
   self.assertEqual((rows,n),([],0))
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

class ROneProbeRunTests(unittest.TestCase):
 def test_run_probes_single_month_not_unspecified_annual(self):
  from unittest.mock import patch
  from rone_probe import run
  calls=[]
  def fake_request(endpoint,params):
   calls.append((endpoint,params))
   if endpoint=='SttsApiTbl.do':
    return [{'STATBL_ID':'A_2024_00045','STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}],1
   if endpoint=='SttsApiTblItm.do': return [{'ITM_ID':'510050','ITM_FULLNM':'대전광역시 서구', 'ITM_NM':'서구'}],1
   return [{'CLS_FULLNM':'','CLS_NM':'매매가격지수','CLS_ID':'510123','ITM_ID':'510050','ITM_NM':'서구', 'UI_NM':'2026.1=100', 'WRTTIME_IDTFR_ID':params['WRTTIME_IDTFR_ID'],'DTA_VAL':'100.23'}],1
  with patch.dict('os.environ',{'RONE_API_KEY':'not-for-logs'}):
   with patch('rone_probe.fetch_xml_rows',side_effect=fake_request):
    self.assertEqual(run(),0)
  self.assertEqual(calls[0][1],{'pIndex':1,'pSize':1000})
  self.assertEqual(calls[-1][1]['DTACYCLE_CD'],'MM')
  self.assertRegex(calls[-1][1]['WRTTIME_IDTFR_ID'],r'^\d{6}$')
  self.assertEqual(calls[-1][1]['ITM_ID'],'510050')


class V4ErrorEnvelopeTests(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  self.env=patch.dict('os.environ',{'RONE_API_KEY':'SPECIAL-SHARED-SECRET'})
  self.env.start()
 def tearDown(self): self.env.stop()
 def fetch(self,xml):
  from rone_probe import fetch_xml_rows
  class Response:
   def __enter__(self): return self
   def __exit__(self,*args): return False
   def read(self,*args): return xml.encode()
  return fetch_xml_rows('SttsApiTblData.do',{'STATBL_ID':'A_2024_00045','DTACYCLE_CD':'MM','WRTTIME_IDTFR_ID':'202610'},opener=lambda req,timeout:Response())
 def test_info200_separate_result_root(self):
  self.assertEqual(self.fetch('<RESULT><CODE>INFO-200</CODE><MESSAGE>no data</MESSAGE></RESULT>'),([],0))
 def test_error_result_root_strips_secrets(self):
  with self.assertRaisesRegex(ValueError,'ERROR-300') as context:
   self.fetch('<RESULT><CODE>ERROR-300</CODE><MESSAGE>SPECIAL-SHARED-SECRET</MESSAGE></RESULT>')
  self.assertNotIn('SPECIAL-SHARED-SECRET',str(context.exception))
 def test_unknown_root_name_reports_only_safe_tag(self):
  with self.assertRaisesRegex(ValueError,'UnexpectedService'):
   self.fetch('<UnexpectedService><status>not found</status></UnexpectedService>')
 def test_monthly_valid_response(self):
  rows,total=self.fetch('<SttsApiTblData><head><list_total_count>1</list_total_count></head><row><ITM_ID>510050</ITM_ID><WRTTIME_IDTFR_ID>202609</WRTTIME_IDTFR_ID><CLS_ID>10001</CLS_ID><DTA_VAL>96.58</DTA_VAL></row></SttsApiTblData>')
  self.assertEqual(rows[0]['DTA_VAL'],'96.58')
  self.assertEqual(total,1)
 def test_itm_id_validated_in_official_metadata(self):
  from rone_probe import verified_region_item_ids,candidate_rows
  metadata=[{'ITM_ID':'510050','ITM_FULLNM':'대전광역시 서구'}, {'ITM_ID':'510060','ITM_FULLNM':'부산광역시 서구'}]
  ids=verified_region_item_ids(metadata)
  self.assertEqual(ids,{'510050'})
  rows=[{'ITM_ID':'510050','CLS_NM':'매매가격지수','CLS_ID':'10000','WRTTIME_IDTFR_ID':'202609','DTA_VAL':'107.0'}, {'ITM_ID':'510060','CLS_NM':'매매가격지수','CLS_ID':'10000','WRTTIME_IDTFR_ID':'202609','DTA_VAL':'99.0'}]
  selected=candidate_rows(rows,ids)
  self.assertEqual(len(selected),1)
  self.assertEqual(selected[0]['region'],'대전광역시 서구')
