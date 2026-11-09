#!/usr/bin/env python3
"""IFPK V45: GitHub Actions -> official economic data -> Supabase -> public Pages snapshots.

Only anonymized PUBLIC indicators are exported. Nothing writes an approved financial plan.
No third-party Python dependencies. Secrets are read from environment, not site files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from pathlib import Path
from statistics import mean
from urllib.parse import urlsplit

from ifpk_collector import INDICATORS, get_kosis, get_ecos, load_ecos_series, contiguous_values, valid_month
from cpi_special import collect_special_cpis
from home_impact import calculate_home_impact
from rone_live import (
    INDICATOR as RONE_INDICATOR, REBASED_INDICATOR as RONE_REBASED,
    collect_rone_202606_verified, calculate_home_reference,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'docs' / 'data'
SOURCE_SHEET_ID = '1E7Sqmb4CeTTqpn8vDcl0FMjxSWWZ1qcgZyBQfOteJTM'
MAX_ROWS = 20000
ALL_INDICATORS = {**INDICATORS, RONE_INDICATOR: {'name':'대전 서구 아파트 매매가격지수 (기존)', 'calc':'regional_sale_index'}, RONE_REBASED: {'name':'대전 서구 아파트 매매가격지수 (2026-06 기준)', 'calc':'regional_sale_index'}}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def _validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('SUPABASE_URL은 HTTPS 프로젝트 URL이어야 합니다')
    if parsed.path.strip('/') or parsed.query or parsed.fragment:
        raise ValueError('SUPABASE_URL에는 프로젝트 주소만 입력하세요 (경로·쿼리 제외)')
    return url.rstrip('/')


class SupabaseStore:
    def __init__(self, url=None, key=None, fetch=None):
        self.url = _validate_url(url or os.getenv('SUPABASE_URL', ''))
        self.key = key or os.getenv('SUPABASE_SECRET_KEY', '')
        if not self.key or len(self.key) < 12:
            raise ValueError('SUPABASE_SECRET_KEY가 설정되지 않았습니다')
        self.fetch = fetch or urllib.request.urlopen

    def request(self, method, table, params=None, payload=None):
        if table not in ('ifpk_observations', 'ifpk_collection_runs', 'ifpk_revisions'):
            raise ValueError('허용되지 않은 DB 테이블')
        url = self.url + '/rest/v1/' + table
        if params:
            url += '?' + urllib.parse.urlencode(params, safe=',.*()')
        headers = {'apikey': self.key, 'Accept': 'application/json', 'User-Agent': 'IFPK-V45-CloudCollector/1.0'}
        # Supabase's 2026 sb_secret_ keys are opaque, NOT JWTs: do NOT send them as Bearer.
        if self.key.startswith('eyJ'):
            headers['Authorization'] = 'Bearer ' + self.key  # legacy service_role JWT only
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            headers['Prefer'] = 'resolution=merge-duplicates,return=minimal' if table == 'ifpk_observations' else 'return=minimal'
        data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.fetch(req, timeout=35) as response:
                content = response.read(4_000_001)
                if len(content) > 4_000_000:
                    raise RuntimeError('클라우드 응답 크기 제한 초과')
                if not content:
                    return []
                return json.loads(content)
        except urllib.error.HTTPError as exc:
            # Provider diagnostics only; never echo request URL or headers (may include API keys).
            raise RuntimeError('Supabase REST 요청 실패 HTTP ' + str(exc.code) + ' · SQL과 Secrets 설정 확인') from None
        except urllib.error.URLError:
            raise RuntimeError('Supabase 네트워크 연결 실패') from None

    def list_rows(self, table, order, select, page_size=600):
        rows = []
        for start in range(0, MAX_ROWS, page_size):
            part = self.request('GET', table, params={'select': select, 'order': order, 'limit': page_size, 'offset': start})
            if not isinstance(part, list):
                raise ValueError('Supabase 응답이 배열이 아닙니다')
            rows.extend(part)
            if len(part) < page_size:
                return rows
        raise RuntimeError('DB 조회 상한 초과: 결과 페이지 처리 확장 필요')

    def get_observations(self):
        return self.list_rows('ifpk_observations','indicator_id.asc,month.asc',
            'indicator_id,month,value,unit,provider,source_code,source_updated,retrieved_at')

    def get_runs(self):
        # Each indicator's latest run is enough for public status. Table grows, can be paged.
        x = self.request('GET', 'ifpk_collection_runs',
            {'select':'indicator_id,finished_at,status,fetched,inserted,revised,message',
             'order':'finished_at.desc', 'limit':100})
        if not isinstance(x,list):
            raise ValueError('수집 실행 기록 응답 형식 오류')
        seen = set(); latest=[]
        for row in x:
            if row['indicator_id'] not in seen:
                seen.add(row['indicator_id']); latest.append(row)
        return latest

    def get_revisions(self):
        # Server-side only. Never expose database keys or private client data.
        return self.list_rows('ifpk_revisions', 'detected_at.desc',
            'indicator_id,month,previous_value,new_value,detected_at,source_updated')

    def save_observations(self, records):
        if not records:
            return
        for begin in range(0, len(records), 200):
            self.request('POST','ifpk_observations',
                params={'on_conflict':'indicator_id,month'}, payload=records[begin:begin+200])

    def save_run(self, indicator, status, fetched=0, inserted=0, revised=0, message='', started_at=None):
        item = {'id':str(uuid.uuid4()), 'indicator_id':indicator,
                'started_at':started_at or utc_now(), 'finished_at':utc_now(),
                'status':status,'fetched':fetched,'inserted':inserted,'revised':revised,
                'message':str(message)[:160]}
        self.request('POST','ifpk_collection_runs',payload=[item])


def normalize_public_rows(db_rows):
    output=[]
    for r in db_rows:
        indicator=r['indicator_id']
        if indicator not in ALL_INDICATORS:
            continue
        month=valid_month(r['month'])
        val=float(r['value'])
        if not math.isfinite(val):
            raise ValueError('DB 숫자에 유한하지 않은 값이 있습니다')
        output.append({'id':indicator,'date':month,'value':val,'unit':r['unit'],
                       'provider':r['provider'],'sourceCode':r['source_code'],
                       'sourceUpdated':r.get('source_updated') or '',
                       'retrievedAt':r['retrieved_at']})
    output.sort(key=lambda x:(x['id'],x['date']))
    if len({(x['id'],x['date']) for x in output})!=len(output):
        raise ValueError('DB 통계월 중복')
    return output


def normalize_public_revisions(db_rows):
    """Export the official observation corrections, no private DB internals."""
    output = []
    for r in db_rows:
        indicator = r['indicator_id']
        if indicator not in ALL_INDICATORS:
            continue
        month = valid_month(r['month'])
        prev = float(r['previous_value'])
        new = float(r['new_value'])
        if not (math.isfinite(prev) and math.isfinite(new)):
            raise ValueError('수정 이력에 유한하지 않은 값이 있습니다')
        output.append({'id':indicator,'date':month,'previousValue':prev,
                       'newValue':new,'detectedAt':str(r['detected_at']),
                       'sourceUpdated':str(r.get('source_updated') or '')})
    output.sort(key=lambda x:(x['detectedAt'],x['id'],x['date']),reverse=True)
    return output


def calculate_estimates(records):
    lookup=defaultdict(list)
    for r in records:
        lookup[r['id']].append(r)
    output=[]
    for key,desc in ALL_INDICATORS.items():
        seq=sorted(lookup[key],key=lambda x:x['date'])
        if not seq:
            output.append({'id':key,'status':'empty','count':0,'basis':None})
            continue
        kind=desc['calc']
        entry={'id':key,'count':len(seq),'lastMonth':seq[-1]['date'], 'basis':kind,'status':'ready','value':None}
        if kind=='regional_sale_index':
            output.append(calculate_home_reference(seq,indicator_id=key)); continue
        if kind=='latest':
            entry['value']=seq[-1]['value']
        else:
            size={'ma3':3,'ma12':12,'deposit60':60,'mortgage60_120':120}.get(kind)
            values=contiguous_values(seq,size) if size else None
            if values is None:
                entry['status']='insufficient_or_gapped';entry['neededMonths']=size
            elif kind=='deposit60':
                avg_60=mean(values)
                entry['value']=avg_60*(1-.154)
                entry['latestObservedRate']=seq[-1]['value']
                entry['grossAverage60']=avg_60
                entry['taxFactor']=.846
                entry['monthlyEquivalentRate']=(pow(1+entry['value']/100,1/12)-1)*100
                entry['observedMonths60']=60
                entry['window60Start']=seq[-60]['date']
                entry['sourceCode']=seq[-1].get('sourceCode','')
                entry['lastRetrievedAt']=seq[-1].get('retrievedAt','')
                entry['formula']='60개월 세전 산술평균 × (1 − 0.154)'
            elif kind=='mortgage60_120':
                avg_60=mean(values[-60:]); avg_120=mean(values)
                entry['value']=avg_60*.7+avg_120*.3
                entry['latestObservedRate']=seq[-1]['value']
                entry['grossAverage60']=avg_60
                entry['grossAverage120']=avg_120
                entry['weights']={'60months':.7,'120months':.3}
                entry['observedMonths60']=60
                entry['observedMonths120']=120
                entry['window60Start']=seq[-60]['date']
                entry['window120Start']=seq[-120]['date']
                entry['sourceCode']=seq[-1].get('sourceCode','')
                entry['lastRetrievedAt']=seq[-1].get('retrievedAt','')
                entry['formula']='60개월 평균 × 0.70 + 120개월 평균 × 0.30'
            elif kind in ('ma3', 'ma12'):
                entry['value']=mean(values)
                entry['lastObservedIndex']=seq[-1]['value']
                entry['rollingMonths']=size
                entry['windowStart']=seq[-size]['date']
                entry['sourceCode']=seq[-1].get('sourceCode', '')
                entry['lastRetrievedAt']=seq[-1].get('retrievedAt', '')
                entry['formula']=f'최근 {size}개월의 월별 원지수 산술평균'
            else:
                entry['value']=mean(values)
        output.append(entry)
    return output


def prepare_snapshots(records, runs, live:bool, collected_at=None, revisions=None):
    records=sorted(records,key=lambda x:(x['id'],x['date']))
    estimates=calculate_estimates(records)
    home_impact=calculate_home_impact(estimates)
    counts=[];grouped=defaultdict(list)
    for r in records: grouped[r['id']].append(r)
    for k,v in grouped.items():
        counts.append({'id':k, 'count':len(v), 'firstMonth':v[0]['date'],
                       'lastMonth':v[-1]['date'], 'lastRetrieved':v[-1]['retrievedAt']})
    last=[{'id':x['indicator_id'],'status':x['status'], 'finishedAt':x['finished_at'],
           'fetched':x['fetched'],'inserted':x['inserted'],'revised':x['revised'],'message':x['message']} for x in runs]
    generated=collected_at or utc_now()
    sanitized_revisions = normalize_public_revisions(revisions) if revisions is not None else []
    public={'format':'ifpk-public-indicators','generatedAt':generated,'records':records,'estimates':estimates,'homeImpact':home_impact,
            'revisions':sanitized_revisions,'revisionHistoryAvailable':revisions is not None}
    status={'format':'ifpk-collector-v45','generatedAt':generated,'published':live,
            'storage':'Supabase PostgreSQL' if live else '로컬 수집자료: 클라우드 미배포 샘플',
            'credentialsConfigured':{'KOSIS':bool(live),'ECOS':bool(live and any(r['id'] in ('DEPOSIT','MORTGAGE') for r in records))},
            'plannedFrequency':'GitHub Actions: 매일 2회 점검 / GitHub 스케줄 실행은 지연될 수 있음',
            'officialPlan':{'sourceSheetId':SOURCE_SHEET_ID,'basis':'2026-11','automaticUpdates':False,'reviewCycleMonths':6},
            'counts':counts,'latestRuns':last,'estimates':estimates,'homeImpact':home_impact,
            'revisionHistoryAvailable':revisions is not None,'revisionCount':len(sanitized_revisions),
            'notes':'관측월/수집일/배포시각 별개, 수집자료는 6개월 공식계획에 자동반영하지 않음'}
    return public,status


def publish_snapshot(public,status):
    DATA.mkdir(parents=True,exist_ok=True)
    for name,doc in [('public_indicators.json',public),('status.json',status)]:
        p=DATA/name
        p.write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def gather_official_sources():
    api_key=os.getenv('KOSIS_API_KEY','')
    if not api_key:
        raise RuntimeError('GitHub Secrets에 KOSIS_API_KEY를 설정하세요')
    rows=get_kosis(api_key, start='202401')
    if not rows:
        raise ValueError('KOSIS에서 CPI 자료를 받지 못했습니다')
    tasks=[('CPI_GENERAL',rows)]
    ecos_key=os.getenv('ECOS_API_KEY','')
    selected=load_ecos_series()
    if selected and not ecos_key:
        raise RuntimeError('ECOS 수집계열이 활성화됐지만 ECOS_API_KEY가 없습니다')
    for series in selected:
        # CPI_CAR/TRAVEL are V47's dedicated, metadata-verified items.
        if series['id'] in ('CPI_CAR', 'CPI_TRAVEL'):
            raise ValueError('품목별 CPI는 ecos_series.json에서 켜지 말고 V47 공식 항목 조회로 수집하세요')
        tasks.append((series['id'],get_ecos(ecos_key,series,start='201601')))
    try:
        tasks.extend(collect_special_cpis(ecos_key))
    except (ValueError, RuntimeError) as exc:
        # Noncritical CPI indices are fail-closed, but must not break proven
        # general CPI and bank-rate publishing. Publish explicit failed runs.
        reason = '품목별 CPI 공식 코드 확인 보류: ' + str(exc)[:115]
        for indicator in ('CPI_CAR', 'CPI_TRAVEL'):
            tasks.append((indicator, {'error': reason}))
    # R-ONE is optional; a temporary provider failure must not break proven
    # KOSIS/ECOS collection or deployment. Failure is visible in DB runs.
    if os.getenv('RONE_API_KEY', '').strip():
        try:
            tasks.append((RONE_REBASED, collect_rone_202606_verified()))
        except (ValueError, RuntimeError) as exc:
            tasks.append((RONE_REBASED, {'error': 'R-ONE 새 기준 검증 보류: '+str(exc)[:115]}))
    return tasks


def execute_cloud(store, tasks, timestamp=None):
    existing=store.get_observations()
    old={(r['indicator_id'],r['month']):float(r['value']) for r in existing}
    outcome=[]
    for indicator, records in tasks:
        started=utc_now()
        if isinstance(records, dict) and 'error' in records:
            store.save_run(indicator,'failed',message=records['error'],started_at=started)
            outcome.append({'indicator':indicator,'status':'failed','reason':records['error']})
            continue
        seen=set();new=[];ins=rev=0
        for r in records:
            if r['id']!=indicator: raise ValueError('지표 ID 불일치')
            pair=(r['id'],r['date'])
            if pair in seen: raise ValueError('동일 배치에서 지표·통계월 중복')
            seen.add(pair)
            v=float(r['value']); prev=old.get(pair)
            if prev is not None and math.isclose(prev,v,abs_tol=1e-9,rel_tol=0):
                continue
            if prev is None: ins+=1
            else: rev+=1
            new.append({'indicator_id':r['id'],'month':r['date'],'value':v,
                        'unit':r['unit'],'provider':r['provider'], 'source_code':r['source_code'],
                        'source_updated':r.get('source_updated') or '', 'retrieved_at':timestamp or utc_now()})
        # DB trigger records changes atomically on updated rows; existing values untouched on repeat.
        store.save_observations(new)
        store.save_run(indicator,'ok',fetched=len(records),inserted=ins,revised=rev,
                       message='공식 API 점검 및 원장 저장 완료',started_at=started)
        outcome.append({'indicator':indicator,'status':'ok','fetched':len(records),'inserted':ins,'revised':rev})
    fresh=normalize_public_rows(store.get_observations())
    # In a real cloud run read Supabase's immutable audit table. Test stores
    # and legacy adapters that lack this method publish an explicit unknown flag.
    revision_reader=getattr(store,'get_revisions',None)
    revision_rows=revision_reader() if callable(revision_reader) else None
    public,status=prepare_snapshots(fresh,store.get_runs(),live=True,collected_at=timestamp,revisions=revision_rows)
    publish_snapshot(public,status)
    return outcome


def dry_run(sample_path):
    raw=json.loads(Path(sample_path).read_text(encoding='utf-8'))
    records=raw['records']
    if raw.get('format')!='ifpk-public-indicators':
        raise ValueError('수집 JSON 자료 형식 오류')
    for row in records:
        if row['id'] not in ALL_INDICATORS:raise ValueError('알 수 없는 지표')
        valid_month(row['date']);float(row['value'])
    public,status=prepare_snapshots(records,[],live=False,revisions=raw.get('revisions') if raw.get('revisionHistoryAvailable') is True else None)
    publish_snapshot(public,status)
    return len(records)


def main():
    parser=argparse.ArgumentParser(description='IFPK V45 cloud collector')
    parser.add_argument('--preview-json',help='기존 수집 JSON으로 배포 전 화면만 확인. Supabase 저장 아님')
    opts=parser.parse_args()
    if opts.preview_json:
        n=dry_run(opts.preview_json)
        print('미배포 샘플 스냅샷 구성 완료:',n,'개 월별 관측치')
        return 0
    tasks=gather_official_sources()  # no key or wrong stats: fail rather than publish stale "success"
    store=SupabaseStore()
    out=execute_cloud(store,tasks)
    print(json.dumps(out,ensure_ascii=False))
    return 0


if __name__=='__main__':
    try: sys.exit(main())
    except Exception as ex:
        # Do not print error URL or authentication key; exceptions from provider are sanitized.
        print('IFPK V45 수집 실패:',str(ex),file=sys.stderr)
        sys.exit(1)
