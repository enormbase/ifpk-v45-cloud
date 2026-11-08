#!/usr/bin/env python3
"""IFPK V48 / 한국부동산원 R-ONE 지역별 아파트 매매가격지수 코드 검증.

- Read-only one-time metadata/probe. Never writes to Supabase or public site.
- API key is passed only in HTTPS request query, NEVER written to logs.
- Requires official STATBL_ID A_2024_00045 and dynamically confirms Daejeon Seo-gu
  CLS_ID / ITM_ID from returned monthly observation data.
"""
from __future__ import annotations

import json
import http.client
import time
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from typing import Any

BASE = 'https://www.reb.or.kr/r-one/openapi/'
TABLE = 'A_2024_00045'
TIMEOUT = 30
PAGE_SIZE = 1000
MAX_PAGES = 8   # limited pagination; read-only R-ONE verification


def request_json(endpoint: str, params: dict[str, str | int], opener=None) -> dict[str, Any]:
    """Fetch R-ONE JSON, protecting the KEY even in error messages."""
    if not re.fullmatch(r'SttsApiTbl(?:Itm|Data)?\.do', endpoint):
        raise ValueError('허용되지 않은 R-ONE 조회 서비스')
    key = os.environ.get('RONE_API_KEY', '').strip()
    if not key:
        raise ValueError('GitHub Repository Secrets에 RONE_API_KEY가 없습니다')
    query = {**params, 'Type':'json', 'KEY':key}
    url = BASE + endpoint + '?' + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={'User-Agent':'IFPK-RONE-Validation/1.0','Accept':'application/json'})
    try:
        transport = opener or urllib.request.urlopen
        with transport(req, timeout=TIMEOUT) as response:
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('R-ONE API 응답 크기 한도 초과')
        out = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(out, dict):
            raise ValueError('R-ONE JSON 최상위 형식 오류')
        if 'RESULT' in out and out['RESULT']:
            # Only print the provider's short CODE, never the raw response,
            # URL, message, or token (which may echo credentials).
            result = out['RESULT']
            raw_code = str(result.get('CODE', '')) if isinstance(result, dict) else ''
            code = raw_code if re.fullmatch(r'(?:INFO|ERROR)-\d{3}|\d{3}', raw_code) else 'UNKNOWN'
            explanations = {
                '290': '인증키 유효성 확인 필요',
                '300': '필수 조회조건 누락 확인 필요',
                '333': '페이지 번호 등 조회조건 형식 확인 필요',
                '336': '페이지당 조회건수 제한 초과',
                '337': '당일 호출 횟수 제한 초과',
            }
            raise ValueError('R-ONE API 오류코드 '+code+' / '+explanations.get(code, '공식 API 결과 확인 필요'))
        return out
    except urllib.error.HTTPError as exc:
        raise ValueError('R-ONE API HTTP 오류 '+str(exc.code)) from None
    except urllib.error.URLError:
        raise ValueError('R-ONE API 연결 실패') from None
    except (UnicodeError,json.JSONDecodeError):
        raise ValueError('R-ONE JSON 디코딩 실패') from None



def fetch_xml_rows(endpoint: str, params: dict[str, str | int], opener=None) -> tuple[list[dict],int|None]:
    """Read official XML (avoids known Korean JSON text corruption).

    Authentication stays in the HTTPS request only; URLs and response messages
    are never printed. INFO-200 is an empty result, not an invalid-key diagnosis.
    """
    if not re.fullmatch(r'SttsApiTbl(?:Itm|Data)?\.do', endpoint):
        raise ValueError('허용되지 않은 R-ONE 조회 서비스')
    key = os.environ.get('RONE_API_KEY', '').strip()
    if not key:
        raise ValueError('GitHub Repository Secrets에 RONE_API_KEY가 없습니다')
    query = {**params,'Type':'xml','KEY':key}
    url=BASE + endpoint + '?' + urllib.parse.urlencode(query)
    req=urllib.request.Request(url,headers={'User-Agent':'IFPK-RONE-Validation/1.2','Accept':'application/xml'})
    try:
        transport = opener or urllib.request.urlopen
        with transport(req,timeout=TIMEOUT) as response:
            raw=response.read(5_000_001)
        if len(raw)>5_000_000:
            raise ValueError('R-ONE XML 응답 크기 한도 초과')
        root=ET.fromstring(raw)
    except urllib.error.HTTPError as exc:
        raise ValueError('R-ONE HTTP 오류 '+str(exc.code)) from None
    except (http.client.RemoteDisconnected, ConnectionResetError, TimeoutError, BrokenPipeError):
        raise ValueError('R-ONE 서버 연결이 응답 없이 종료됨 (일시적 장애/요청제한 가능)') from None
    except urllib.error.URLError:
        raise ValueError('R-ONE API 연결 실패') from None
    except (ET.ParseError,UnicodeError):
        raise ValueError('R-ONE XML 응답 파싱 실패') from None
    # R-ONE may return a different XML root when there are no observations.
    # Inspect the short provider result code BEFORE checking the service root.
    # Never print provider error bodies or URLs: some responses may echo KEY.
    def tag_name(node):
        return node.tag.rsplit('}', 1)[-1] if isinstance(node.tag, str) else ''

    code = ''
    for node in root.iter():
        if tag_name(node).lower() in {'code', 'returnreasoncode'} and node.text:
            candidate = node.text.strip()
            if re.fullmatch(r'(?:INFO|ERROR)-\d{3}|\d{3}', candidate):
                code = candidate
                break
    if not code:
        # Some provider error envelopes put INFO-200 in direct text, not CODE.
        prefix = ' '.join((x or '').strip() for x in root.itertext())[:1000]
        match = re.search(r'\b(?:INFO|ERROR)-\d{3}\b', prefix)
        if match:
            code = match.group(0)
    if code == 'INFO-200':
        return [], 0
    if code and code not in {'INFO-000', '200'}:
        raise ValueError('R-ONE API 결과코드 '+code+' (요청조건/통계 제공시점 확인)')

    expected = endpoint.split('.')[0]
    if tag_name(root) != expected:
        safe_root = tag_name(root)[:48]
        safe_root = re.sub(r'[^a-zA-Z0-9_]', '', safe_root) or 'unknown'
        raise ValueError('R-ONE 응답형식 불일치 ('+safe_root+'); API 오류코드/조회조건 점검 필요')
    rows=[{tag_name(el):(el.text or '').strip() for el in row} for row in root.findall('row')]
    if not rows:
        rows=[{tag_name(el):(el.text or '').strip() for el in row} for row in root.findall('.//row')]
    total_txt=root.findtext('./head/list_total_count')
    total=int(total_txt) if (total_txt or '').isdigit() else None
    return rows,total


def locate_months():
    now=datetime.now()
    total=now.year*12+(now.month-1)
    return [f'{(total-i)//12:04d}{(total-i)%12+1:02d}' for i in (1,2,3,4,5,6)]


def choose_table(rows):
    matched=[r for r in rows if str(r.get('STATBL_ID'))==TABLE]
    if len(matched)!=1:
        candidates=[r for r in rows if '매매' in str(r.get('STATBL_NM','')) and '아파트' in str(r.get('STATBL_NM','')) and '지수' in str(r.get('STATBL_NM','')) and '월' in str(r.get('STATBL_NM',''))]
        print('지정 코드 미확인. 비슷한 공식 통계표 후보 (확정·저장 안 함):')
        for c in candidates[:12]:
            print('  ',c.get('STATBL_ID',''),c.get('STATBL_NM',''),c.get('DTACYCLE_CD',''))
        raise ValueError('공식 통계목록에서 지정 코드 '+TABLE+' 확인 불가')
    item=matched[0]
    name=str(item.get('STATBL_NM',''))
    cycle=str(item.get('DTACYCLE_CD',''))
    if not ('MM' in cycle.split(',') and '아파트' in name and '매매' in name and '지수' in name):
        raise ValueError('통계표명 또는 월별 주기가 불일치합니다. 저장 보류')
    return item


def unpack(doc: dict, root: str):
    """Official schema: {Root:[{head:[...]},{row:[...]}]}.

    Support the fallback {Root:{row:[...]}} for related provider versions.
    """
    nodes = doc.get(root)
    if isinstance(nodes,dict):
        rows = nodes.get('row') or []
        head = nodes.get('head') or []
    elif isinstance(nodes,list):
        rows=[];head=[]
        for n in nodes:
            if isinstance(n,dict):
                rows.extend(n.get('row') or [])
                head.extend(n.get('head') or [])
    else:
        raise ValueError(f'R-ONE 응답에 {root} 데이터가 없습니다')
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):
        raise ValueError('R-ONE 관측행 형식 오류')
    total = None
    for h in head:
        if isinstance(h,dict) and 'list_total_count' in h:
            total = int(h['list_total_count']);break
    return rows,total


def norm_name(s):
    return re.sub(r'[\s\-·_()]+','',str(s or '')).replace('광역시','').replace('특별시','')


def is_daejeon_seogu(row: dict)->bool:
    fullname = norm_name(row.get('CLS_FULLNM'))
    group = norm_name(row.get('GRP_NM'))
    name = norm_name(row.get('CLS_NM'))
    item_full = norm_name(row.get('ITM_FULLNM'))
    # In this table, the REGION is an ITM_ID (e.g. 510050), not necessarily CLS_ID.
    # Reject ambiguous bare '서구'; match Daejeon from official metadata.
    return (('대전' in fullname and '서구' in fullname)
            or (name == '서구' and '대전' in group)
            or (name.startswith('대전') and '서구' in name)
            or ('대전' in item_full and '서구' in item_full))


def verified_region_item_ids(itemrows: list[dict]) -> set[str]:
    confirmed = set()
    for row in itemrows:
        full = norm_name(row.get('ITM_FULLNM'))
        item_id = str(row.get('ITM_ID', '')).strip()
        if '대전' in full and '서구' in full and item_id.isdigit():
            confirmed.add(item_id)
    return confirmed


def month_of(row:dict):
    for k in ('WRTTIME_IDTFR_ID','WRTTIME_DESC'):
        raw=str(row.get(k,'')).strip()
        m=re.search(r'((?:19|20)\d{2})\D{0,5}(1[0-2]|0?[1-9])(?:\D|$)',raw)
        if m:
            return f'{m.group(1)}-{int(m.group(2)):02d}'
        if re.fullmatch(r'(?:19|20)\d{2}(?:0[1-9]|1[0-2])',raw):
            return raw[:4]+'-'+raw[4:]
    return None


def candidate_rows(rows:list[dict], verified_itm_ids:set[str]|None=None)->list[dict]:
    valid=[]
    for row in rows:
        item_id=str(row.get('ITM_ID','')).strip()
        # Only trust an ITM_ID if it was established from the official metadata.
        # Region can also appear as a CLS hierarchy on other tables.
        proven_by_metadata=bool(verified_itm_ids and item_id in verified_itm_ids)
        if not (proven_by_metadata or is_daejeon_seogu(row)): continue
        table_id=str(row.get('STATBL_ID','')).strip()
        if table_id and table_id!=TABLE: continue
        month=month_of(row)
        if not month:continue
        try: value=float(str(row['DTA_VAL']).replace(',',''))
        except (TypeError,ValueError,KeyError):continue
        if not math.isfinite(value) or value <= 0:continue
        cls_id=str(row.get('CLS_ID','')).strip()
        if not item_id.isdigit():continue
        if cls_id and not cls_id.isdigit():continue
        valid.append({'month':month,'value':value,'cls_id':cls_id or '미확인', 'itm_id':item_id,
                      'region':'대전광역시 서구' if proven_by_metadata else str(row.get('CLS_FULLNM') or row.get('CLS_NM') or ''),
                      'item':str(row.get('CLS_NM') or row.get('ITM_NM') or ''),
                      'unit':str(row.get('UI_NM') or ''),
                      'group':str(row.get('GRP_NM') or '')})
    return valid


def summarize(rows:list[dict],verified_itm_ids:set[str]|None=None):
    groups=defaultdict(list)
    for row in candidate_rows(rows,verified_itm_ids):
        groups[(row['cls_id'],row['itm_id'])].append(row)
    summary=[]
    for (cls_id,itm_id),seq in sorted(groups.items()):
        by_month={x['month']:x for x in seq}
        seq=sorted(by_month.values(),key=lambda x:x['month'])
        summary.append({'table':TABLE,'cls_id':cls_id,'itm_id':itm_id,'region':seq[-1]['region'],
                        'item':seq[-1]['item'],'unit':seq[-1]['unit'],
                        'months':len(seq),'last_month':seq[-1]['month'],
                        'latest_value':seq[-1]['value'],
                        'recent':[(r['month'],r['value']) for r in seq[-3:]]})
    return summary


def diagnose_small_matrix(valid_ids: set[str], fetch=None, pause=None) -> list[dict]:
    """At most FOUR small, read-only calls; stop on early remote disconnect.

    The same table is tested with/without the region filter, on an older month
    and with a broad period. This is a DIAGNOSTIC, never an asserted official
    index; values are intentionally withheld until region+series are proven.
    """
    if fetch is None: fetch=fetch_xml_rows
    if pause is None: pause=time.sleep
    print('4단계: 최소 요청 필터 진단 (4개 이하, 읽기전용)')
    itm=sorted(valid_ids)[0]
    basic={'STATBL_ID':TABLE,'DTACYCLE_CD':'MM','pIndex':1,'pSize':10}
    cases=[
        ('A 과거 2024-09 + 대전서구 코드', {'WRTTIME_IDTFR_ID':'202409','ITM_ID':itm}),
        ('B 과거 2024-09 + 지역코드 없음', {'WRTTIME_IDTFR_ID':'202409'}),
        ('C 대전서구 코드만 / 시점 없음', {'ITM_ID':itm}),
        ('D 대전서구 코드 + 과거 기간', {'ITM_ID':itm,'START_WRTTIME':'202401','END_WRTTIME':'202412'}),
    ]
    results=[]
    for label, extra in cases:
        # Be polite to the official service; avoid many consecutive requests.
        pause(1.5)
        try:
            rows,total=fetch('SttsApiTblData.do',{**basic,**extra})
        except ValueError as exc:
            msg=str(exc)[:120]  # fetch_xml_rows sanitizes URLs/KEY
            print('진단',label,':',msg)
            results.append({'case':label,'error':msg})
            if '연결이 응답 없이 종료됨' in msg:
                print('연결이 갑자기 끊겼으므로 추가 호출은 중단합니다. 재시도 반복은 권장하지 않음.')
                break
            continue
        print('진단',label,':',len(rows),'건 / 전체',total if total is not None else '미제공')
        item_ids=sorted({str(row.get('ITM_ID','')) for row in rows if row.get('ITM_ID')})[:5]
        if rows:
            row=rows[0]
            # Metadata only: no financial index is reported until validated.
            print('  응답 예시 메타:',json.dumps({key:str(row.get(key,''))[:65] for key in (
                'WRTTIME_IDTFR_ID','CLS_ID','CLS_NM','ITM_ID','ITM_NM','ITM_FULLNM','UI_NM')},ensure_ascii=False))
        results.append({'case':label,'rows':len(rows),'total':total,'itm_ids':item_ids})
        # If B (without ITM_ID) has data but A does not, suspect item filter.
        # If C works, suspect month filter. No inferred series is saved.
    return results


def safe_target_observations(rows: list[dict], region_code: str, item_code: str) -> list[dict]:
    """Verify every field before showing a value; never trust returned rows blindly."""
    out=[]
    for row in rows:
        if str(row.get('CLS_ID','')).strip() != region_code:
            continue
        if str(row.get('ITM_ID','')).strip() != item_code:
            continue
        table_id = str(row.get('STATBL_ID','')).strip()
        if table_id and table_id != TABLE:
            continue
        freq = str(row.get('DTACYCLE_CD','')).strip()
        if freq and freq != 'MM':
            continue
        name = str(row.get('ITM_NM','')) + ' ' + str(row.get('ITM_FULLNM',''))
        if '지수' not in name:
            continue
        month = month_of(row)
        if not month:
            continue
        try:
            value=float(str(row.get('DTA_VAL','')).replace(',',''))
        except (TypeError,ValueError):
            continue
        if not math.isfinite(value) or value<=0:
            continue
        out.append({'month':month,'index':value,'cls_id':region_code,
                    'item_id':item_code, 'region_name':str(row.get('CLS_FULLNM') or row.get('CLS_NM') or ''),
                    'item_name':str(row.get('ITM_NM') or ''), 'unit':str(row.get('UI_NM') or '')})
    return sorted(out,key=lambda r:r['month'])


def read_region_index(region_code: str, item_code: str, fetch=None, pause=None) -> list[dict]:
    """R-ONE: region belongs in CLS_ID; index name belongs in ITM_ID.

    Calls at most two targeted API requests. If one disconnects, do not flood
    the provider with automatic retries. No Supabase writes are performed.
    """
    if fetch is None:fetch=fetch_xml_rows
    if pause is None:pause=time.sleep
    base={'STATBL_ID':TABLE,'DTACYCLE_CD':'MM','CLS_ID':region_code,'ITM_ID':item_code,
          'pIndex':1,'pSize':24}
    cases=[('2024년 9월 단일시점',{'WRTTIME_IDTFR_ID':'202409'}),
           ('2024년 이후 기간',{'START_WRTTIME':'2024','END_WRTTIME':'2026'})]
    for label,when in cases:
        pause(1.0)
        try:
            rows,total=fetch('SttsApiTblData.do',{**base,**when})
        except ValueError as exc:
            print('데이터 요청 오류:',str(exc)[:140])
            # Stop rather than retry on server-side disconnects.
            return []
        verified=safe_target_observations(rows,region_code,item_code)
        print('대전 서구 관측값:',label,'전체',total if total is not None else '?',
              '수신',len(rows),'검증 통과',len(verified))
        if rows and not verified:
            sample=rows[0]
            print('참고: 응답 코드 불일치 (CLS_ID / ITM_ID / ITM_NM):',
                  str(sample.get('CLS_ID',''))[:20],str(sample.get('ITM_ID',''))[:20],
                  str(sample.get('ITM_NM',''))[:30])
            # Reject unexpected mixed series; don't switch codes blindly.
            return []
        if verified:
            return verified
    return []


def run():
    if not os.getenv('RONE_API_KEY','').strip():
        raise ValueError('RONE_API_KEY GitHub Secret 설정을 확인해 주세요')
    print('IFPK V48 대전 서구 아파트 매매가격지수 검증 V7: 필터 필드 교정')
    print('공식 개발가이드: 지역=CLS_ID, 지수=ITM_ID (V6의 반대 지정 오류 수정)')
    print('1단계: 대상 표·항목 메타데이터 확인')
    tables,_=fetch_xml_rows('SttsApiTbl.do',{'pIndex':1,'pSize':1000})
    table=choose_table(tables)
    print('통계표:',TABLE,str(table.get('STATBL_NM',''))[:100])
    items,_=fetch_xml_rows('SttsApiTblItm.do',{'STATBL_ID':TABLE,'pIndex':1,'pSize':1000})
    region_candidates=verified_region_item_ids(items)
    if len(region_candidates)!=1:
        print('대전 서구 후보가 1개가 아님:',len(region_candidates))
        return 2
    region_code=next(iter(region_candidates))
    # In V6 the real nationwide observation established ITM_ID=100001
    # as the index item, while CLS_ID=500001 represented nationwide.
    index_code='100001'
    print('지역 분류코드(CLS_ID) 후보:',region_code)
    print('지수 항목코드(ITM_ID) 후보:',index_code)
    print('2단계: 올바른 필드로 최소 관측값 조회 (Supabase 저장하지 않음)')
    series=read_region_index(region_code,index_code)
    if not series:
        print('R-ONE 대전 서구 지수 미검증: 정확한 지역/품목 조합 또는 자료 기간 추가 확인 필요')
        return 2
    print('확인된 관측값 (최대 5건):')
    for row in series[-5:]:
        print('  ',row['month'],'지수',row['index'],
              '지역',row['region_name'],'코드',row['cls_id'],'항목',row['item_id'],'단위',row['unit'])
    print('※ 읽기 전용 확인 성공. 지수 기준연도·연속성·최근월은 본연동 전에 별도 검증')
    return 0

if __name__ == '__main__':
    try:sys.exit(run())
    except Exception as exc:
        # Never log URL, response body, or private API key.
        print('R-ONE 검증 중단:',str(exc)[:150],file=sys.stderr)
        sys.exit(1)
