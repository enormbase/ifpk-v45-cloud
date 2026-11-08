"""V47: fail-closed CPI item discovery for ECOS 901Y009.

Only exact, unambiguous official item-name matches are accepted. Never
store a total CPI or a different type of travel/car price by guessing codes.
"""
from __future__ import annotations

import re
import urllib.parse

from ifpk_collector import get_ecos, secure_get_json

TABLE = '901Y009'
TARGETS = {'CPI_CAR': '대형승용차', 'CPI_TRAVEL': '해외단체여행비'}
MAX_PAGE = 10
PAGE_SIZE = 500


def _clean(text):
    return re.sub(r'\s+', '', str(text or ''))


def _ascii_code(text):
    text = str(text or '')
    return bool(re.fullmatch(r'[0-9A-Za-z_]+', text))


def item_metadata(response):
    if not isinstance(response, dict) or not isinstance(response.get('StatisticItemList'), dict):
        raise ValueError('ECOS 901Y009 항목목록 조회 실패: 응답 형식을 확인해야 해요')
    data = response['StatisticItemList']
    rows = data.get('row')
    if not isinstance(rows, list):
        raise ValueError('ECOS 품목목록에 row 배열이 없어요')
    total = data.get('list_total_count') or data.get('total_count') or len(rows)
    try:
        total = int(total)
    except (TypeError, ValueError):
        raise ValueError('ECOS 품목목록 전체 건수 형식 오류') from None
    if total < 0 or total > PAGE_SIZE * MAX_PAGE:
        raise ValueError('ECOS 품목목록이 비정상적으로 커서 정확한 판별이 어려워요')
    return rows, total


def pick_verified_item(rows, expected):
    exact = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('ECOS 품목 메타데이터 행 형식 오류')
        name = row.get('ITEM_NAME')
        if _clean(name) != _clean(expected):
            continue
        grp = str(row.get('GRP_CODE') or '').strip().lower()
        # For a one-dimension CPI index, the item must belong to GROUP1.
        if grp not in ('group1', '1'):
            continue
        code = row.get('ITEM_CODE')
        if not _ascii_code(code):
            raise ValueError('ECOS ' + expected + ' 품목코드가 잘못된 형식이에요')
        exact.append(str(code))
    distinct = sorted(set(exact))
    if len(distinct) != 1:
        raise ValueError('ECOS ' + expected + ' 공식 품목코드 유일성 확인 실패 (' + str(len(distinct)) + '개). 추측 코드로 수집하지 않아요')
    return distinct[0]


def fetch_item_catalog(key, fetch=secure_get_json):
    all_rows = []
    expected_total = None
    for index in range(MAX_PAGE):
        start = index * PAGE_SIZE + 1
        end = start + PAGE_SIZE - 1
        parts = ['https://ecos.bok.or.kr/api/StatisticItemList', urllib.parse.quote(key, safe=''),
                 'json', 'kr', str(start), str(end), TABLE]
        rows, total = item_metadata(fetch('/'.join(parts)))
        if expected_total is None:
            expected_total = total
        elif expected_total != total:
            raise ValueError('ECOS 품목목록 페이지 간 전체 건수가 달라요')
        all_rows.extend(rows)
        if len(all_rows) >= total:
            if len(all_rows) > total:
                raise ValueError('ECOS 품목목록 페이지가 중복됐어요')
            return all_rows
        if not rows:
            break
    raise ValueError('ECOS 품목목록 일부만 조회돼 코드를 확정할 수 없어요')


def collect_special_cpis(ecos_key, fetch=secure_get_json, get_data=get_ecos):
    if not ecos_key:
        raise ValueError('ECOS_API_KEY 없이 품목별 CPI 수집 불가')
    metadata = fetch_item_catalog(ecos_key, fetch=fetch)
    output = []
    for indicator_id, expected_name in TARGETS.items():
        code = pick_verified_item(metadata, expected_name)
        series = {'id': indicator_id, 'stat_code': TABLE, 'item_filters': {'ITEM_CODE1': code}}
        rows = get_data(ecos_key, series, start='201601')
        if len(rows) < (12 if indicator_id == 'CPI_TRAVEL' else 3):
            raise ValueError(expected_name + ' 지수의 가공에 필요한 월별 데이터가 부족해요')
        if any(row['id'] != indicator_id or row['source_code'] != TABLE + '/' + code for row in rows):
            raise ValueError(expected_name + ' 관측계열 출처 검증 실패')
        output.append((indicator_id, rows))
    return output
