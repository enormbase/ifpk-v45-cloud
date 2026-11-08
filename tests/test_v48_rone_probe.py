import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collector'))
import rone_probe as rp

class V7RegionFilterTests(unittest.TestCase):
    def setUp(self):
        self.target={'STATBL_ID':rp.TABLE,'DTACYCLE_CD':'MM','CLS_ID':'510050','CLS_NM':'서구',
                     'CLS_FULLNM':'대전광역시>서구','ITM_ID':'100001','ITM_NM':'지수',
                     'WRTTIME_IDTFR_ID':'202409','DTA_VAL':'103.12','UI_NM':'지수'}

    def test_seogu_is_cls_and_index_is_itm(self):
        got=[]
        def fake(endpoint,p):
            got.append(p)
            return [self.target],1
        res=rp.read_region_index('510050','100001',fetch=fake,pause=lambda _:None)
        self.assertEqual(len(res),1)
        self.assertEqual(res[0]['index'],103.12)
        self.assertEqual(got[0]['CLS_ID'],'510050')
        self.assertEqual(got[0]['ITM_ID'],'100001')
        self.assertEqual(got[0]['WRTTIME_IDTFR_ID'],'202409')
        self.assertNotIn('ITM_ID',{'CLS_ID':got[0]['CLS_ID']})

    def test_wrong_region_and_item_rejected(self):
        self.assertEqual(rp.safe_target_observations([{**self.target,'CLS_ID':'500001'}],'510050','100001'),[])
        self.assertEqual(rp.safe_target_observations([{**self.target,'ITM_ID':'510050'}],'510050','100001'),[])
        self.assertEqual(rp.safe_target_observations([{**self.target,'ITM_NM':'변동률'}],'510050','100001'),[])
        self.assertEqual(rp.safe_target_observations([{**self.target,'DTACYCLE_CD':'YY'}],'510050','100001'),[])

    def test_bad_numbers_and_nonmonth_rejected(self):
        for v in ('nan','inf','-1','','not a number'):
            self.assertEqual(rp.safe_target_observations([{**self.target,'DTA_VAL':v}],'510050','100001'),[])
        self.assertEqual(rp.safe_target_observations([{**self.target,'WRTTIME_IDTFR_ID':'2024'}],'510050','100001'),[])

    def test_second_try_period_if_first_empty(self):
        calls=[]
        def fake(endpoint,p):
            calls.append(p)
            return ([],0) if len(calls)==1 else ([self.target],1)
        seq=rp.read_region_index('510050','100001',fetch=fake,pause=lambda _:None)
        self.assertEqual(len(seq),1)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[1]['START_WRTTIME'],'2024')

    def test_disconnect_does_not_retry(self):
        calls=[]
        def fake(endpoint,p):
            calls.append(p)
            raise ValueError('R-ONE 서버 연결이 응답 없이 종료됨')
        self.assertFalse(rp.read_region_index('510050','100001',fetch=fake,pause=lambda _:None))
        self.assertEqual(len(calls),1)

    def test_run_success_and_no_database_writes(self):
        calls=[]
        def fake(endpoint,p):
            calls.append((endpoint,p))
            if endpoint=='SttsApiTbl.do':
                return [{'STATBL_ID':rp.TABLE,'STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}],1
            if endpoint=='SttsApiTblItm.do':
                return [{'ITM_ID':'510050','ITM_FULLNM':'대전광역시 서구'}],1
            return [self.target],1
        with patch.dict('os.environ',{'RONE_API_KEY':'SECRET-XYZ'}):
            with patch.object(rp,'fetch_xml_rows',side_effect=fake):
                with patch.object(rp.time,'sleep'):
                    self.assertEqual(rp.run(),0)
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[2][1]['CLS_ID'],'510050')
        self.assertEqual(calls[2][1]['ITM_ID'],'100001')

    def test_run_no_match_safe_nonzero(self):
        def fake(endpoint,p):
            if endpoint=='SttsApiTbl.do':
                return [{'STATBL_ID':rp.TABLE,'STATBL_NM':'(월) 매매가격지수_아파트','DTACYCLE_CD':'MM'}],1
            if endpoint=='SttsApiTblItm.do':
                return [{'ITM_ID':'510050','ITM_FULLNM':'대전광역시 서구'}],1
            return [],0
        with patch.dict('os.environ',{'RONE_API_KEY':'SECRET-XYZ'}):
            with patch.object(rp,'fetch_xml_rows',side_effect=fake):
                with patch.object(rp.time,'sleep'):
                    self.assertEqual(rp.run(),2)

    def test_xml_provider_code_is_not_logged_with_key(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,*a):return b'<RESULT><CODE>INFO-200</CODE></RESULT>'
        with patch.dict('os.environ',{'RONE_API_KEY':'SECRET-XYZ'}):
            self.assertEqual(rp.fetch_xml_rows('SttsApiTblData.do',{},opener=lambda req,timeout:Response()),([],0))

    def test_region_metadata_must_name_daejeon(self):
        self.assertEqual(rp.verified_region_item_ids([{'ITM_ID':'510050','ITM_FULLNM':'대전광역시 서구'}]),{'510050'})
        self.assertEqual(rp.verified_region_item_ids([{'ITM_ID':'510050','ITM_FULLNM':'부산광역시 서구'}]),set())

if __name__=='__main__':unittest.main()
