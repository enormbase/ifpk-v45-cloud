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
from collections import defaultdict
from datetime import datetime
from typing import Any

BASE = 'https://www.reb.or.kr/r-one/openapi/'
TABLE = 'A_2024_00045'
TIMEOUT = 30
PAGE_SIZE = 1000
MAX_PAGES = 8   # rate-limited on purpose; read only one calendar year


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
    # Reject ambiguous bare "서구"; there is also Gwangju, Incheon, Daegu, Busan.
    return ('대전' in fullname and '서구' in fullname) or (name == '서구' and '대전' in group) or (name.startswith('대전') and '서구' in name)


def month_of(row:dict):
    for k in ('WRTTIME_IDTFR_ID','WRTTIME_DESC'):
        raw=str(row.get(k,'')).strip()
        m=re.search(r'((?:19|20)\d{2})\D{0,5}(1[0-2]|0?[1-9])(?:\D|$)',raw)
        if m:
            return f'{m.group(1)}-{int(m.group(2)):02d}'
        if re.fullmatch(r'(?:19|20)\d{2}(?:0[1-9]|1[0-2])',raw):
            return raw[:4]+'-'+raw[4:]
    return None


def candidate_rows(rows:list[dict])->list[dict]:
    valid=[]
    for row in rows:
        if not is_daejeon_seogu(row): continue
        # A specific table & monthly period are verified in the API request.
        # Do NOT assume which item is the correct index based on just region.
        month=month_of(row)
        if not month:continue
        try: value=float(str(row['DTA_VAL']).replace(',',''))
        except (TypeError,ValueError,KeyError):continue
        if not math.isfinite(value):continue
        item_id=str(row.get('ITM_ID','')).strip()
        cls_id=str(row.get('CLS_ID','')).strip()
        if not (item_id.isdigit() and cls_id.isdigit()):continue
        valid.append({'month':month,'value':value,'cls_id':cls_id,'itm_id':item_id,
                      'region':str(row.get('CLS_FULLNM') or row.get('CLS_NM') or ''),
                      'item':str(row.get('ITM_NM') or ''),
                      'unit':str(row.get('UI_NM') or ''),
                      'group':str(row.get('GRP_NM') or '')})
    return valid


def summarize(rows:list[dict]):
    groups=defaultdict(list)
    for row in candidate_rows(rows):
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
    print('IFPK V48: R-ONE 공식 월간 지역별 아파트 매매가격지수 메타데이터 검증')
    print('검증 통계표: '+TABLE+' / 대전광역시 서구 / 월별 아파트 매매가격지수')
    print('1단계: 서비스 통계목록 조회 (STATBL_ID 및 월별 DTACYCLE_CD=MM)')
    meta=request_json('SttsApiTbl.do', {'STATBL_ID':TABLE,'DTACYCLE_CD':'MM','pIndex':1,'pSize':30})
    tables,_=unpack(meta,'SttsApiTbl')
    matched=[r for r in tables if str(r.get('STATBL_ID'))==TABLE]
    if not matched:
        raise ValueError('통계표ID가 공식 API 목록에 없습니다. 별도 확인 필요')
    item=matched[0]
    name=str(item.get('STATBL_NM',''))
    cycle=str(item.get('DTACYCLE_CD',''))
    print('통계표명:', name, '/ 주기:',cycle)
    if cycle not in ('MM','M') or not ('아파트' in name and '매매' in name and '지수' in name):
        raise ValueError('공식 통계표명·주기가 예상과 불일치: 저장·적용 보류')
    print('공식 자료 검증: 월별 아파트 매매가격지수 계열 확인')
    year=str(datetime.now().year)
    collected=[];last_total=None
    for page in range(1,MAX_PAGES+1):
        doc=request_json('SttsApiTblData.do', {'STATBL_ID':TABLE,'DTACYCLE_CD':'MM',
              'START_WRTTIME':year,'END_WRTTIME':year,'pIndex':page,'pSize':PAGE_SIZE})
        batch,total=unpack(doc,'SttsApiTblData')
        if last_total is None:last_total=total
        collected.extend(batch)
        print(f'해당 연도 메타데이터 검증: 페이지 {page}, 확인 {len(batch)}행 (누적 {len(collected)}행)')
        if not batch or len(batch)<PAGE_SIZE:break
        if total is not None and page*PAGE_SIZE>=total:break
    candidates=summarize(collected)
    print('\n--- 대전 서구 분류/항목 후보 (API 값 그대로, 인증키 비공개) ---')
    if not candidates:
        print('후보 없음: API 반환 범위·지역 분류를 추가 확인해야 합니다.')
        print('임의의 지역코드를 등록하지 않았으며, 기존 V47 자동수집에는 영향이 없습니다.')
        # Potential API's period range filters can use other formats: do not guess.
        print('응답 행수:',len(collected),' / 조회 연도:',year)
        return 2
    for c in candidates:
        print(json.dumps(c,ensure_ascii=False))
    if len(candidates)!=1:
        print('후보가 여러 개입니다. 항목명이 실제 매매가격지수인지 확인 후 확정해야 합니다.')
        return 3
    only=candidates[0]
    if not only['item'] or not ('지수' in only['item'] or '매매' in only['item']):
        print('단일 후보지만 항목명이 미확인. 확정 전 공식 항목 목록과 비교가 필요합니다.')
        return 3
    print('검증 후보 1개 확인. CLS_ID와 ITM_ID를 확인해 다음 단계에 연결하세요.')
    print('이 작업은 검증 전용이며 DB 저장 및 확정 재무계획 변경을 하지 않습니다.')
    return 0


if __name__=='__main__':
    try:sys.exit(run())
    except Exception as exc:
        # Never print URL, request or HTTP error body (could contain secrets).
        print('R-ONE 검증 실패:',str(exc)[:160],file=sys.stderr)
        sys.exit(1)
