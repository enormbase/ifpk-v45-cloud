#!/usr/bin/env python3
"""Official R-ONE Daejeon Seo-gu apartment sale-price index collector.

No credentials are ever emitted. All returned rows must match the previously
verified table, region and index field. Stale/partial input is NOT extrapolated.
R-ONE API provides regional indices, not individual property appraisals.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from typing import Callable

from rone_probe import (
    TABLE, fetch_xml_rows, choose_table, verified_region_item_ids,
    safe_target_observations,
)

INDICATOR = 'HOME_PRICE_APT_DAEJEON_SEOGU'
REGION = '510050'
INDEX = '100001'
SOURCE_CODE = f'{TABLE}/{REGION}/{INDEX}'
# A new R-ONE index base was officially introduced in July 2026.
# Keep all prior DB observations under the legacy ID, never silently overwrite.
REBASED_INDICATOR = INDICATOR + '_BASE202606'
REBASED_SOURCE_CODE = SOURCE_CODE + '/BASE202606'


def _validate_metadata(fetch: Callable):
    tables, _ = fetch('SttsApiTbl.do', {'pIndex': 1, 'pSize': 1000})
    choose_table(tables)
    items, _ = fetch('SttsApiTblItm.do', {'STATBL_ID': TABLE, 'pIndex': 1, 'pSize': 1000})
    confirmed = verified_region_item_ids(items)
    if confirmed != {REGION}:
        raise ValueError('R-ONE 대전 서구 공식 지역 메타데이터가 변경돼 수집을 중단했습니다')


def _parse_page(rows: list[dict], now: dt.date):
    if len(rows) > 0 and any(
        str(x.get('CLS_ID', '')).strip() != REGION or
        str(x.get('ITM_ID', '')).strip() != INDEX or
        (str(x.get('STATBL_ID', '')).strip() not in ('', TABLE))
        for x in rows
    ):
        raise ValueError('R-ONE 응답에 다른 지역/통계항목이 혼재되어 저장을 차단했습니다')
    validated = [safe_target_observations([r], REGION, INDEX) for r in rows]
    if any(len(v) != 1 for v in validated):
        # E.g., a missing index value or unexpected frequency should never be
        # silently treated as a continuous monthly index.
        raise ValueError('R-ONE 월별 관측값 형식 또는 단위 검증 실패')
    result = []
    for raw, candidates in zip(rows, validated):
        value = candidates[0]
        y, m = (int(x) for x in value['month'].split('-'))
        if (y, m) > (now.year, now.month):
            raise ValueError('R-ONE API 미래 통계월 발견')
        if y < 2000 or value['index'] > 10000:
            raise ValueError('R-ONE 주택가격지수 범위 오류')
        result.append({
            'id': INDICATOR, 'date': value['month'], 'value': value['index'],
            'unit': '지수', 'provider': 'R-ONE', 'source_code': SOURCE_CODE,
            'source_updated': str(raw.get('LST_CHN_DE') or raw.get('WRTTIME_DESC') or '')[:64],
        })
    return result


def _download_period(fetch, now: dt.date, start_year=2015, psize=240, max_pages=6):
    # R-ONE monthly dates are YYYYMM, NOT YYYY. The previous END_WRTTIME='2026'
    # caused months such as 202601 to sort beyond the end of the range. Filter both
    # CLS_ID (region) and ITM_ID (index) at the provider, and verify all rows.
    base = {'STATBL_ID': TABLE, 'DTACYCLE_CD': 'MM', 'CLS_ID': REGION,
            'ITM_ID': INDEX, 'START_WRTTIME': f'{start_year}01',
            'END_WRTTIME': f'{now.year}{now.month:02d}', 'pSize': psize}
    result = []
    for page in range(1, max_pages + 1):
        raw, total = fetch('SttsApiTblData.do', {**base, 'pIndex': page})
        if not raw:
            break
        result.extend(_parse_page(raw, now))
        if total is not None and len(result) >= total:
            break
        if len(raw) < psize:
            break
    else:
        raise ValueError('R-ONE 페이지 한도를 초과해 일부 월이 누락될 수 있어 저장을 보류했습니다')
    if total is not None and len(result) < total:
        raise ValueError('R-ONE 페이지 수보다 수집 건수가 적어 저장을 보류했습니다')
    return result


def collect_rone_monthly(fetch: Callable | None = None, now: dt.date | None = None):
    """Return provider-validated raw monthly rows; no DB access here.

    Fall back to the proven 2024-09 single-month query only when a period
    range returns no records. That yields a clearly *stale/insufficient*
    monitor entry, never an invented 5-year growth rate.
    """
    fetch = fetch or fetch_xml_rows
    now = now or dt.date.today()
    _validate_metadata(fetch)
    rows = _download_period(fetch, now)
    if not rows:
        # Diagnostic fallback. Avoid publishing if even the verified month
        # cannot be retrieved. No automatic fan-out of 100+ single-month calls.
        alt, _ = fetch('SttsApiTblData.do', {
            'STATBL_ID': TABLE, 'DTACYCLE_CD': 'MM', 'CLS_ID': REGION,
            'ITM_ID': INDEX, 'WRTTIME_IDTFR_ID': '202409', 'pIndex': 1, 'pSize': 20,
        })
        rows = _parse_page(alt, now)
    if not rows:
        raise ValueError('R-ONE 대전 서구 대상기간 관측값 없음 (기존 값 유지)')
    by_month = {}
    for item in rows:
        m = item['date']
        if m in by_month and not math.isclose(by_month[m]['value'], item['value'], abs_tol=1e-9, rel_tol=0):
            raise ValueError('R-ONE 동일 통계월 상충 값 발견')
        by_month[m] = item
    # No actual timestamp gets overwritten by a mocked or hardcoded value.
    return [by_month[k] for k in sorted(by_month)]


def collect_rone_202606_verified(fetch: Callable | None = None, now: dt.date | None = None):
    """Collect a new, separate official-base vintage without touching legacy rows.

    Safety gate: 2026-06 must be exactly the official 100-point anchor,
    2026-05..07 must exist with a plausible bridge, and at least one
    post-rebase month must be available. Do NOT concatenate stored legacy
    rows with newly retrieved values.
    """
    fetch = fetch or fetch_xml_rows
    now = now or dt.date.today()
    _validate_metadata(fetch)
    rows = _download_period(fetch, now)
    by_month = {}
    for row in rows:
        month = row['date']
        if month in by_month and not math.isclose(by_month[month]['value'], row['value'], abs_tol=1e-9, rel_tol=0):
            raise ValueError('R-ONE 같은 월에 서로 다른 지수가 있어 새 기준 저장을 보류합니다')
        by_month[month] = row
    if not {'2026-05','2026-06','2026-07'}.issubset(by_month):
        last = max(by_month, default='자료 없음')
        raise ValueError('R-ONE 월간 종료시점 또는 2026년 자료 확인 필요; 조회 최종월 '+last)
    anchor = by_month['2026-06']['value']
    if not math.isclose(anchor, 100.0, rel_tol=0, abs_tol=0.005):
        raise ValueError('R-ONE 2026-06 기준지수=100 검증 실패; 확인된 값 '+f'{anchor:.4f}')
    for a,b in [('2026-05','2026-06'),('2026-06','2026-07')]:
        step = by_month[b]['value']/by_month[a]['value'] - 1
        if not math.isfinite(step) or abs(step) > 0.10:
            raise ValueError('R-ONE 지수 기준연결 주변에서 비정상적 변동 발견; 재검토 필요')
    # All rows must originate from THIS single official API response, not
    # from a splice with old Supabase values of uncertain base/revision.
    result=[]
    for key in sorted(by_month):
        row=by_month[key].copy()
        row['id']=REBASED_INDICATOR
        row['source_code']=REBASED_SOURCE_CODE
        row['source_updated']=(row.get('source_updated') or '')[:64]
        result.append(row)
    return result


def calculate_home_reference(seq, *, current: dt.date | None = None,
                             indicator_id: str = INDICATOR):
    """CAGR from exactly 12/60/120 adjacent monthly intervals; no interpolation.

    Region price index != house appraisal. Only return comparable reference
    growth when the newest period is fresh and all months are continuous.
    """
    current = current or dt.date.today()
    seq = sorted(seq, key=lambda r: r['date'])
    if not seq:
        return {'status': 'empty', 'count': 0, 'basis': 'regional_sale_index'}
    latest = seq[-1]
    y, m = (int(x) for x in latest['date'].split('-'))
    age = (current.year - y) * 12 + current.month - m
    if age < 0:
        raise ValueError('R-ONE 최신월이 미래입니다')
    output = {
        'id': indicator_id, 'basis': 'regional_sale_index',
        'indexBaseMonth': '2026-06' if indicator_id == REBASED_INDICATOR else 'unverified_legacy',
        'lastMonth': latest['date'], 'latestObservedIndex': latest['value'],
        'value': latest['value'], 'count': len(seq),
        'sourceCode': latest.get('sourceCode', SOURCE_CODE),
        'lastRetrievedAt': latest.get('retrievedAt', ''),
        'latestAgeMonths': age, 'stale': age > 4,
        'status': 'stale' if age > 4 else 'ready',
        'rates': {}, 'approvedPlanChanged': False,
        'formula': '연환산 변동률 = (최신지수 / n개월 전 지수)^(12/n) − 1',
        'note': '지역지수는 개별 주택 시세가 아니며 미래 상승률을 보장하지 않음',
    }
    lookup = {r['date']: float(r['value']) for r in seq}
    end_year, end_month = y, m
    for n in (12, 60, 120):
        window = []
        for k in range(n + 1):
            zero = (end_year * 12 + end_month - 1) - k
            month = f'{(zero // 12):04d}-{(zero % 12) + 1:02d}'
            if month not in lookup:
                window = []
                break
            window.append(lookup[month])
        if not window or min(window) <= 0 or age > 4:
            output['rates'][f'{n}months'] = None
        else:
            pct = (pow(window[0] / window[-1], 12 / n) - 1) * 100
            output['rates'][f'{n}months'] = pct
    output['countContinuousRequired'] = {'1y': 13, '5y': 61, '10y': 121}
    # Anchor 4억원 to the *approved client example* only as a what-if; do not
    # treat it as the sale price of a specific property.
    output['illustrativeHomeCurrentKrw'] = 400000000
    output['illustrative2046By5yrKrw'] = (
        round(400000000 * (1 + output['rates']['60months'] / 100) ** 20)
        if output['rates']['60months'] is not None else None)
    output['illustrative2046By10yrKrw'] = (
        round(400000000 * (1 + output['rates']['120months'] / 100) ** 20)
        if output['rates']['120months'] is not None else None)
    return output
