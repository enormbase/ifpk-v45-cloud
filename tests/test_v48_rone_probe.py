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

if __name__=='__main__':unittest.main()
