#!/usr/bin/env python3
"""IFPK V48 / 한국부동산원 R-ONE 지역별 아파트 매매가격지수 코드 검증.

- Read-only one-time metadata/probe. Never writes to Supabase or public site.
- API key is passed only in HTTPS request query, NEVER written to logs.
- Requires official STATBL_ID A_2024_00045 and dynamically confirms Daejeon Seo-gu
  CLS_ID / ITM_ID from returned monthly observation data.
"""
from __future__ import annotations

import json
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
MAX_PAGES = 8   # rate-limited on purpose; read only a single month per try


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


def run():
    if not os.getenv('RONE_API_KEY','').strip():
        raise ValueError('RONE_API_KEY GitHub Secret 설정을 확인해 주세요')
    print('IFPK V48: R-ONE 대전 서구 월별 아파트 매매가격지수 안전검증 V4')
    print('1단계: 서비스 통계표 전체목록 조회 (필터 없음, XML)')
    # SttsApiTbl supports STATBL_ID filter but does NOT accept DTACYCLE_CD
    # as a documented filter. Enumerating prevents INFO-200 on overfiltering.
    tables=[]
    for page in range(1,3):
        batch,total=fetch_xml_rows('SttsApiTbl.do',{'pIndex':page,'pSize':1000})
        tables+=batch
        if not batch or (total is not None and len(tables)>=total) or len(batch)<1000:
            break
    print('공식 통계표 목록:',len(tables),'건')
    item=choose_table(tables)
    print('검증 통계표:',TABLE,' / ',item.get('STATBL_NM',''),'/ 주기',item.get('DTACYCLE_CD',''))
    print('2단계: 통계항목 목록 조회 (대전 서구 ITM_ID 확인)')
    itemrows,_=fetch_xml_rows('SttsApiTblItm.do', {'STATBL_ID':TABLE,'pIndex':1,'pSize':1000})
    print('항목 목록:',len(itemrows),'건')
    valid_ids = verified_region_item_ids(itemrows)
    print('대전 서구 공식 항목 후보:', ', '.join(sorted(valid_ids)) if valid_ids else '없음')
    if not valid_ids:
        raise ValueError('공식 항목 목록에서 대전광역시 서구 ITM_ID 검증 실패')
    print('3단계: 최근 월별 데이터에서 대전 서구 관측행 식별 (DB 저장 없음)')
    for month in locate_months():
        collected=[]
        total=None
        for page in range(1,MAX_PAGES+1):
            params={'STATBL_ID':TABLE,'DTACYCLE_CD':'MM',
                    'WRTTIME_IDTFR_ID':month,'pIndex':page,'pSize':1000}
            if len(valid_ids)==1:
                params['ITM_ID']=next(iter(valid_ids))
            batch,all_count=fetch_xml_rows('SttsApiTblData.do',params)
            collected.extend(batch)
            if total is None:total=all_count
            if not batch or len(batch)<1000 or (total is not None and page*1000>=total):break
        print('통계월',month,'관측행:',len(collected),'건')
        if not collected:
            # INFO-200 may mean the monthly release is not yet available.
            print('  해당 통계월 미공표 또는 조회 결과 없음. 이전 월 확인')
            continue
        candidates=summarize(collected,valid_ids)
        if candidates:
            print('대전 서구 후보 - 공식 원문 분류코드/항목코드:')
            for c in candidates[:8]:print(json.dumps(c,ensure_ascii=False))
            if len(candidates)==1 and candidates[0]['itm_id'] in valid_ids and candidates[0]['cls_id']!='미확인':
                print('통계원장 조회 성공. 통계명·단위·기준년도와 장기 시계열은 별도 검증 후 수집 활성화.')
                return 0
            print('후보 조회됨: 분류 항목/단위를 추가 검증해야 하므로 적용 보류.')
            return 2
        print('해당 월에 지역 필터와 일치하는 수치 없음. 다음 월 조회')
    print('최근 6개 통계월에서 대전 서구 지수 미확인. 조회조건/분류 정보 추가검토 필요.')
    print('기존 CPI/금리·Supabase/웹사이트 값은 변경하지 않았습니다.')
    return 2


if __name__=='__main__':
    try:sys.exit(run())
    except Exception as exc:
        # Never print URL, request or HTTP error body (could contain secrets).
        print('R-ONE 검증 실패:',str(exc)[:160],file=sys.stderr)
        sys.exit(1)
