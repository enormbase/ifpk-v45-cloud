#!/usr/bin/env python3
"""IFPK V44 -- official data collection and an offline-first web UI.

Python standard library only. Source keys never sent to browser.
This is a data collection/observation database, NOT a financial-plan recalculator.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sqlite3
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean

BASE = Path(__file__).resolve().parent
DATABASE = BASE / 'ifpk_indicators.sqlite3'
HTML = BASE / 'IFPK_생애재무설계_웹사이트_V44.html'
PATTERN_MONTH = re.compile(r'^\d{4}-(?:0[1-9]|1[0-2])$')
INDICATORS = {
    'CPI_GENERAL': {'name': '전국 소비자물가지수', 'unit': '2020=100', 'source': 'KOSIS', 'source_code': '101/DT_1J22003/T10/T', 'calc': 'latest', 'minimum': 10, 'maximum': 1000},
    'CPI_CAR': {'name': '대형승용차 CPI 원지수', 'unit': '지수', 'source': 'ECOS', 'source_code': 'configured', 'calc': 'ma3', 'minimum': 10, 'maximum': 1000},
    'CPI_TRAVEL': {'name': '해외단체여행비 CPI 원지수', 'unit': '지수', 'source': 'ECOS', 'source_code': 'configured', 'calc': 'ma12', 'minimum': 10, 'maximum': 1000},
    'DEPOSIT': {'name': '예적금 세전금리 월별', 'unit': '%', 'source': 'ECOS', 'source_code': 'configured', 'calc': 'deposit60', 'minimum': -10, 'maximum': 50},
    'MORTGAGE': {'name': '신규 주택담보대출 금리 월별', 'unit': '%', 'source': 'ECOS', 'source_code': 'configured', 'calc': 'mortgage60_120', 'minimum': -10, 'maximum': 50},
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def month_delta(base: dt.date, diff: int) -> dt.date:
    year = base.year + (base.month - 1 + diff) // 12
    month = (base.month - 1 + diff) % 12 + 1
    return dt.date(year, month, 1)


def valid_month(raw: str) -> str:
    s = str(raw).strip().replace('-', '')
    if not re.fullmatch(r'\d{6}', s) or not (1 <= int(s[4:]) <= 12):
        raise ValueError('월별 통계시점 형식 오류')
    return s[:4] + '-' + s[4:]


def parse_number(v, lo: float, hi: float) -> float:
    if v is None or isinstance(v, bool):
        raise ValueError('통계값 없음')
    raw = str(v).strip().replace(',', '')
    if not re.fullmatch(r'-?\d+(?:\.\d+)?', raw):
        raise ValueError('숫자 아닌 통계값')
    x = float(raw)
    if not math.isfinite(x) or not (lo <= x <= hi):
        raise ValueError('범위를 벗어난 통계값')
    return x


def db_connect(path: Path = DATABASE):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=12)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=10000')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS observations(
      indicator_id TEXT NOT NULL,
      month TEXT NOT NULL,
      value REAL NOT NULL,
      unit TEXT NOT NULL,
      provider TEXT NOT NULL,
      source_code TEXT NOT NULL,
      source_updated TEXT,
      retrieved_at TEXT NOT NULL,
      PRIMARY KEY(indicator_id, month)
    );
    CREATE TABLE IF NOT EXISTS revisions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      indicator_id TEXT NOT NULL,
      month TEXT NOT NULL,
      previous_value REAL NOT NULL,
      new_value REAL NOT NULL,
      detected_at TEXT NOT NULL,
      source_updated TEXT
    );
    CREATE TABLE IF NOT EXISTS collection_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      indicator_id TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT NOT NULL,
      status TEXT NOT NULL,
      fetched INTEGER NOT NULL DEFAULT 0,
      inserted INTEGER NOT NULL DEFAULT 0,
      revised INTEGER NOT NULL DEFAULT 0,
      message TEXT NOT NULL DEFAULT ''
    );
    ''')
    db.commit()
    return db


def parse_kosis(response) -> list[dict]:
    """KOSIS 101/DT_1J22003: nationwide (=T10), total CPI (=T)."""
    if isinstance(response, dict):
        raise ValueError('KOSIS가 통계표 대신 오류 객체를 반환했습니다')
    if not isinstance(response, list):
        raise ValueError('KOSIS 응답 형식 오류')
    result = {}
    for raw in response:
        if not isinstance(raw, dict):
            raise ValueError('KOSIS 행 형식 오류')
        if str(raw.get('ORG_ID')) != '101' or str(raw.get('TBL_ID')) != 'DT_1J22003':
            raise ValueError('KOSIS 통계표 코드가 예상과 다릅니다')
        if str(raw.get('C1')) != 'T10' or str(raw.get('ITM_ID')) != 'T' or str(raw.get('PRD_SE')) != 'M':
            raise ValueError('KOSIS 지역/항목/주기가 전국 총지수와 다릅니다')
        unit = str(raw.get('UNIT_NM') or '')
        if unit and ('2020' not in unit or '100' not in unit):
            raise ValueError('소비자물가지수 기준연도 변경: 자동 혼합 금지 (' + unit[:80] + ')')
        month = valid_month(raw.get('PRD_DE'))
        val = parse_number(raw.get('DT'), 10, 1000)
        if month in result and result[month]['value'] != val:
            raise ValueError('같은 통계월의 상충된 전국 CPI')
        result[month] = {'id': 'CPI_GENERAL', 'date': month, 'value': val,
                         'unit': '2020=100', 'provider': 'KOSIS',
                         'source_code': '101/DT_1J22003/T10/T',
                         'source_updated': str(raw.get('LST_CHN_DE') or '')}
    if not result:
        raise ValueError('유효한 KOSIS 전국 CPI가 없습니다')
    return [result[k] for k in sorted(result)]


def parse_ecos(response, series: dict) -> list[dict]:
    """Requires explicit stat code and exact item-code filters; rejects mixed series."""
    box = response.get('StatisticSearch') if isinstance(response, dict) else None
    if not isinstance(box, dict) or not isinstance(box.get('row'), list):
        err = response.get('RESULT', response) if isinstance(response, dict) else response
        raise ValueError('ECOS 통계 조회 실패: ' + str(err)[:140])
    wanted = {str(k): str(v) for k, v in series['item_filters'].items()}
    if not wanted or 'ITEM_CODE1' not in wanted:
        raise ValueError('ECOS 통계항목 코드가 미설정되어 계열 혼합 위험')
    result = {}
    for raw in box['row']:
        if str(raw.get('STAT_CODE')) != series['stat_code']:
            raise ValueError('ECOS 통계표 코드 불일치')
        if str(raw.get('CYCLE')) != 'M':
            raise ValueError('ECOS 월별 계열 아님')
        if any(str(raw.get(k, '')) != v for k, v in wanted.items()):
            raise ValueError('ECOS 응답에 다른 품목 계열이 섞여 있습니다')
        month = valid_month(raw.get('TIME'))
        desc = INDICATORS[series['id']]
        val = parse_number(raw.get('DATA_VALUE'), desc['minimum'], desc['maximum'])
        if month in result and result[month]['value'] != val:
            raise ValueError('ECOS 동일 월 중복 수치 충돌')
        result[month] = {'id': series['id'], 'date': month, 'value': val,
                         'unit': desc['unit'], 'provider': 'ECOS',
                         'source_code': series['stat_code'] + '/' + '/'.join(wanted.values()),
                         'source_updated': ''}
    if not result:
        raise ValueError('ECOS 응답 데이터 없음')
    return [result[k] for k in sorted(result)]


def secure_get_json(url: str):
    # URLs contain provider keys: never log or return them to UI.
    req = urllib.request.Request(url, headers={'User-Agent': 'IFPK-V44-DataCollector/1.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=18) as response:
            if response.status != 200:
                raise RuntimeError('공식 API 응답 HTTP ' + str(response.status))
            data = response.read(4_000_001)
            if len(data) > 4_000_000:
                raise RuntimeError('공식 API 응답 크기 제한 초과')
            return json.loads(data.decode('utf-8-sig'))
    except urllib.error.HTTPError as ex:
        raise RuntimeError('공식 API 응답 HTTP ' + str(ex.code)) from None
    except urllib.error.URLError:
        raise RuntimeError('공식 API 네트워크 접근 실패 (DNS·TLS·네트워크 확인)') from None
    except (UnicodeError, json.JSONDecodeError):
        raise RuntimeError('공식 API JSON 변환 실패') from None


def get_kosis(key, start='202401', end=None):
    if not end:
        end = dt.date.today().strftime('%Y%m')
    # Nationwide C1=T10, total index ITM_ID=T verified with KOSIS table 101/DT_1J22003.
    params = {'method': 'getList', 'apiKey': key, 'orgId': '101', 'tblId': 'DT_1J22003',
              'objL1': 'T10', 'itmId': 'T', 'prdSe': 'M', 'startPrdDe': start,
              'endPrdDe': end, 'format': 'json', 'jsonVD': 'Y'}
    url = 'https://kosis.kr/openapi/Param/statisticsParameterData.do?' + urllib.parse.urlencode(params)
    return parse_kosis(secure_get_json(url))


def get_ecos(key, series: dict, start='201601', end=None):
    if not end:
        end = dt.date.today().strftime('%Y%m')
    stat = series['stat_code']
    if not re.fullmatch(r'\d{3}[A-Z]\d{3}', stat):
        raise ValueError('ECOS 통계표 코드 형식 오류')
    if not all(re.fullmatch(r'[0-9A-Za-z_]+', v) for v in series['item_filters'].values()):
        raise ValueError('ECOS 항목코드에 사용할 수 없는 문자')
    # ECOS StatisticSearch accepts optional item-code segments in fixed order.
    parts = ['https://ecos.bok.or.kr/api/StatisticSearch', urllib.parse.quote(key, safe=''),
             'json', 'kr', '1', '1000', stat, 'M', start, end]
    for col in ('ITEM_CODE1', 'ITEM_CODE2', 'ITEM_CODE3', 'ITEM_CODE4'):
        if col in series['item_filters']:
            parts.append(series['item_filters'][col])
        else:
            break
    return parse_ecos(secure_get_json('/'.join(parts)), series)


def store_observations(db, records: list[dict]):
    """Idempotent insert; revised official data retained in revisions audit table."""
    inserted = revised = 0
    now = utc_now()
    seen = set()
    with db:
        for row in records:
            indicator, month = row['id'], row['date']
            if indicator not in INDICATORS or not PATTERN_MONTH.fullmatch(month):
                raise ValueError('미등록 지표/통계월')
            if (indicator, month) in seen:
                raise ValueError('동일 배치에서 통계월 중복')
            seen.add((indicator, month))
            spec = INDICATORS[indicator]
            value = parse_number(row['value'], spec['minimum'], spec['maximum'])
            old = db.execute('SELECT value FROM observations WHERE indicator_id=? AND month=?',
                             (indicator, month)).fetchone()
            if old is None:
                db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)',
                           (indicator, month, value, row['unit'], row['provider'], row['source_code'],
                            row.get('source_updated', ''), now))
                inserted += 1
            elif not math.isclose(old['value'], value, rel_tol=0, abs_tol=1e-9):
                db.execute('INSERT INTO revisions(indicator_id, month, previous_value, new_value, detected_at, source_updated) VALUES (?,?,?,?,?,?)',
                           (indicator, month, old['value'], value, now, row.get('source_updated', '')))
                db.execute('UPDATE observations SET value=?,unit=?,provider=?,source_code=?,source_updated=?,retrieved_at=? WHERE indicator_id=? AND month=?',
                           (value, row['unit'], row['provider'], row['source_code'], row.get('source_updated', ''), now, indicator, month))
                revised += 1
    return inserted, revised


def log_run(db, indicator_id, start_at, status, fetched=0, inserted=0, revised=0, message=''):
    with db:
        db.execute('INSERT INTO collection_runs (indicator_id, started_at, finished_at, status, fetched, inserted, revised, message) VALUES (?,?,?,?,?,?,?,?)',
                   (indicator_id, start_at, utc_now(), status, fetched, inserted, revised, message[:240]))


def secrets_config():
    result = {}
    filepath = BASE / 'secrets.env'
    if filepath.exists():
        for line in filepath.read_text(encoding='utf-8-sig').splitlines():
            s = line.strip()
            if not s or s.startswith('#') or '=' not in s:
                continue
            k, v = s.split('=', 1)
            if k.strip() in ('KOSIS_API_KEY', 'ECOS_API_KEY'):
                result[k.strip()] = v.strip().strip('"').strip("'")
    for key in ('KOSIS_API_KEY', 'ECOS_API_KEY'):
        if os.getenv(key):
            result[key] = os.environ[key]
    return result


def load_ecos_series():
    p = BASE / 'ecos_series.json'
    if not p.exists():
        return []
    x = json.loads(p.read_text(encoding='utf-8'))
    result = []
    for entry in x.get('series', []):
        if not entry.get('enabled', False):
            continue
        if entry.get('id') not in INDICATORS or entry['id'] == 'CPI_GENERAL':
            raise ValueError('ECOS 지표 ID 설정 오류')
        if not isinstance(entry.get('item_filters'), dict):
            raise ValueError('ECOS item_filters 필요')
        result.append(entry)
    return result


def collect(db, only=None):
    key = secrets_config()
    tasks = []
    if only in (None, 'CPI_GENERAL'):
        tasks.append(('CPI_GENERAL', lambda: get_kosis(key['KOSIS_API_KEY']), bool(key.get('KOSIS_API_KEY'))))
    if only != 'CPI_GENERAL':
        for series in load_ecos_series():
            if only and only != series['id']:
                continue
            tasks.append((series['id'], lambda s=series: get_ecos(key['ECOS_API_KEY'], s), bool(key.get('ECOS_API_KEY'))))
    results = []
    if not tasks:
        return [{'indicator': only or 'none', 'status': 'not_configured', 'message': '수집 대상으로 설정한 계열이 없습니다'}]
    for indicator, fn, enabled in tasks:
        started = utc_now()
        if not enabled:
            msg = '공식 API 인증키 없음. secrets.env 또는 환경변수 설정 필요'
            log_run(db, indicator, started, 'missing_key', message=msg)
            results.append({'indicator': indicator, 'status': 'missing_key', 'message': msg})
            continue
        try:
            rows = fn()
            ins, rev = store_observations(db, rows)
            log_run(db, indicator, started, 'ok', len(rows), ins, rev, '공식 API 수집 및 저장 성공')
            results.append({'indicator': indicator, 'status': 'ok', 'fetched': len(rows), 'inserted': ins, 'revised': rev})
        except Exception as ex:
            # Never include provider URL, API key or traceback in persisted error messages.
            msg = str(ex).replace(key.get('KOSIS_API_KEY', '') or '\0', '[redacted]').replace(key.get('ECOS_API_KEY', '') or '\0', '[redacted]')[:230]
            log_run(db, indicator, started, 'failed', message=msg)
            results.append({'indicator': indicator, 'status': 'failed', 'message': msg})
    return results


def get_records(db, cap=5000):
    rows = db.execute('SELECT indicator_id AS id, month AS date, value, unit, provider, source_code AS sourceCode, source_updated AS sourceUpdated, retrieved_at AS retrievedAt FROM observations ORDER BY indicator_id, month LIMIT ?', (cap,)).fetchall()
    return [dict(x) for x in rows]


def contiguous_values(rows, size):
    if len(rows) < size:
        return None
    last = rows[-size:]
    initial = dt.date.fromisoformat(last[0]['date'] + '-01')
    for i, r in enumerate(last):
        if r['date'] != month_delta(initial, i).strftime('%Y-%m'):
            return None
    return [r['value'] for r in last]


def get_estimates(db):
    out = []
    for indicator, spec in INDICATORS.items():
        rs = [dict(x) for x in db.execute('SELECT month AS date,value FROM observations WHERE indicator_id=? ORDER BY month', (indicator,))]
        if not rs:
            out.append({'id': indicator, 'status': 'empty', 'count': 0, 'basis': None})
            continue
        latest = rs[-1]['date']
        kind = spec['calc']
        entry = {'id': indicator, 'count': len(rs), 'lastMonth': latest, 'basis': kind, 'status': 'ready', 'value': None}
        if kind == 'latest':
            entry['value'] = rs[-1]['value']
        elif kind in ('ma3', 'ma12', 'deposit60', 'mortgage60_120'):
            n = {'ma3': 3, 'ma12': 12, 'deposit60': 60, 'mortgage60_120': 120}[kind]
            seq = contiguous_values(rs, n)
            if seq is None:
                entry['status'] = 'insufficient_or_gapped'
                entry['neededMonths'] = n
            else:
                if kind == 'deposit60':
                    entry['value'] = mean(seq) * (1 - .154)
                elif kind == 'mortgage60_120':
                    entry['value'] = mean(seq[-60:]) * .7 + mean(seq) * .3
                else:
                    entry['value'] = mean(seq)
        out.append(entry)
    return out


def status_json(db):
    counts = [dict(x) for x in db.execute('''SELECT o.indicator_id AS id,COUNT(*) AS count,MIN(month) AS firstMonth,MAX(month) AS lastMonth,
     MAX(retrieved_at) AS lastRetrieved FROM observations o GROUP BY indicator_id ORDER BY indicator_id''')]
    last = [dict(x) for x in db.execute('''SELECT r.indicator_id AS id,r.status,r.finished_at AS finishedAt,
     r.fetched,r.inserted,r.revised,r.message FROM collection_runs r INNER JOIN
     (SELECT indicator_id,MAX(id) last_id FROM collection_runs GROUP BY indicator_id) mx ON r.id=mx.last_id ORDER BY r.id DESC''')]
    c = secrets_config()
    return {'format': 'ifpk-collector-v44', 'generatedAt': utc_now(), 'storage': 'SQLite (로컬 파일)',
            'credentialsConfigured': {'KOSIS': bool(c.get('KOSIS_API_KEY')), 'ECOS': bool(c.get('ECOS_API_KEY'))},
            'plannedFrequency': 'monthly (external scheduler must be configured)',
            'officialPlan': {'sourceSheetId': '1E7Sqmb4CeTTqpn8vDcl0FMjxSWWZ1qcgZyBQfOteJTM',
                             'basis': '2026-11', 'automaticUpdates': False, 'reviewCycleMonths': 6},
            'counts': counts, 'latestRuns': last, 'estimates': get_estimates(db)}


class LocalHandler(BaseHTTPRequestHandler):
    server_version = 'IFPK-V44/1.0'

    def _allowed(self):
        host = self.headers.get('Host', '').split(':')[0].strip('[]').lower()
        return host in ('127.0.0.1', 'localhost', '::1')

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self._allowed():
            self._json(403, {'error': 'local access only'})
            return
        path = urllib.parse.urlsplit(self.path).path
        if path in ('/', '/index.html', '/' + HTML.name):
            if not HTML.exists():
                self._json(404, {'error': 'V44 HTML 파일 없음'})
                return
            buf = HTML.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(buf)))
            self.end_headers()
            self.wfile.write(buf)
            return
        with db_connect(self.server.db_path) as db:
            if path == '/api/status':
                self._json(200, status_json(db))
            elif path == '/api/indicators':
                self._json(200, {'format': 'ifpk-public-indicators', 'generatedAt': utc_now(), 'records': get_records(db), 'estimates': get_estimates(db)})
            elif path == '/api/health':
                self._json(200, {'status': 'ok'})
            else:
                self._json(404, {'error': 'not found'})

    def do_POST(self):
        if not self._allowed():
            self._json(403, {'error': 'local access only'})
            return
        origin = self.headers.get('Origin', '')
        if origin and not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):\d+', origin):
            self._json(403, {'error': 'same-origin local UI only'})
            return
        if self.path != '/api/collect':
            self._json(404, {'error': 'not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self._json(415, {'error': 'application/json required'})
            return
        n = int(self.headers.get('Content-Length', '0'))
        if n < 0 or n > 2048:
            self._json(413, {'error': 'body too large'})
            return
        try:
            body = json.loads(self.rfile.read(n) if n else b'{}')
            only = body.get('indicator')
            if only is not None and only not in INDICATORS:
                raise ValueError('지원하지 않는 지표')
        except (ValueError, TypeError):
            self._json(400, {'error': '잘못된 요청'})
            return
        # A lock avoids concurrent collection attempts that waste provider quota.
        if not self.server.collect_lock.acquire(blocking=False):
            self._json(409, {'error': '수집 작업이 이미 실행 중'})
            return
        try:
            with db_connect(self.server.db_path) as db:
                self._json(200, {'results': collect(db, only=only), 'status': status_json(db)})
        finally:
            self.server.collect_lock.release()

    def log_message(self, fmt, *args):
        # Hide URLs/query strings; do not print provider credentials.
        if not self.path.startswith('/api/'):
            return
        print('[V44]', self.command, urllib.parse.urlsplit(self.path).path)


def main(argv=None):
    parser = argparse.ArgumentParser(description='IFPK V44 월별 경제지표 수집·SQLite 저장·웹뷰')
    parser.add_argument('command', choices=['serve', 'collect', 'status', 'export', 'selftest'])
    parser.add_argument('--db', default=str(DATABASE), help='SQLite database file')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--indicator', choices=list(INDICATORS))
    parser.add_argument('--output', help='export: JSON file path')
    a = parser.parse_args(argv)
    if a.command == 'selftest':
        import unittest
        from test_collector import CollectorTests
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(CollectorTests)
        ok = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
        return 0 if ok else 1
    with db_connect(Path(a.db)) as db:
        if a.command == 'collect':
            result = {'results': collect(db, only=a.indicator)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if all(x.get('status') == 'ok' for x in result['results']) else 2
        if a.command == 'status':
            print(json.dumps(status_json(db), ensure_ascii=False, indent=2))
            return 0
        if a.command == 'export':
            result = {'format': 'ifpk-public-indicators', 'generatedAt': utc_now(), 'records': get_records(db), 'estimates': get_estimates(db)}
            if a.output:
                Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                print('saved:', a.output)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    if a.command == 'serve':
        if not (1 <= a.port <= 65535):
            parser.error('port out of range')
        server = ThreadingHTTPServer(('127.0.0.1', a.port), LocalHandler)
        server.db_path = Path(a.db)
        server.collect_lock = threading.Lock()
        print(f'IFPK V44 local dashboard: http://127.0.0.1:{a.port}/', flush=True)
        print('V44 API keys stay on the Python process, not inside HTML.', flush=True)
        # Open the browser only after the socket is bound. The old BAT opened
        # Edge before the server had started, causing ERR_CONNECTION_REFUSED.
        if os.name == 'nt':
            def open_dashboard():
                try:
                    webbrowser.open(f'http://127.0.0.1:{a.port}/#data', new=2)
                except Exception:
                    print('Browser auto-open failed. Use the URL above.', flush=True)
            threading.Timer(0.7, open_dashboard).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
