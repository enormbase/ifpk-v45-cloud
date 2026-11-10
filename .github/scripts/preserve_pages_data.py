#!/usr/bin/env python3
"""Preserve the last *verified* Pages snapshot on website-only deployments.

A temporary KOSIS/ECOS/R-ONE network failure must not block a frontend release,
but a website-only deploy must never masquerade an old sample as fresh official data.
Does not contact any API with keys. Does not change official plan or observation dates.
"""
from __future__ import annotations
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs' / 'data'
NAMES = ('status.json', 'public_indicators.json')


def get_bytes(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'IFPK-Pages-preserve/1.0', 'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=22) as response:
                if response.status != 200:
                    raise RuntimeError('HTTP ' + str(response.status))
                result = response.read(4_000_001)
                if len(result) > 4_000_000:
                    raise ValueError('공개 스냅샷 크기 초과')
                return result
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError('기존 Pages 경제지표 스냅샷 연결 실패; 오래된 샘플 배포를 중단합니다') from None
            time.sleep(2 + attempt * 2)
    raise AssertionError('unreachable')


def validate(status: dict, public: dict) -> None:
    if not isinstance(status, dict) or not isinstance(public, dict):
        raise ValueError('잘못된 자료 형식')
    if status.get('published') is not True:
        raise ValueError('이전 공개 자료가 정식 발표자료 스냅샷이 아님; 배포 보류')
    if public.get('format') != 'ifpk-public-indicators':
        raise ValueError('이전 공개 지표 자료의 형식 불일치')
    if not status.get('generatedAt') or status.get('generatedAt') != public.get('generatedAt'):
        raise ValueError('이전 공개 지표 상태·원장 시각 불일치')
    records = public.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('기존 공개 관측자료가 없어 배포 보류')
    for rec in records:
        if not isinstance(rec, dict) or not all(k in rec for k in ('id','date','value')):
            raise ValueError('기존 공개 관측자료 구조 오류')


def main() -> None:
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if '/' not in repo:
        raise ValueError('GITHUB_REPOSITORY 값이 없습니다')
    owner, name = repo.split('/', 1)
    # This project publishes from the repository's GitHub Pages project URL.
    base = f'https://{owner.lower()}.github.io/{name}/data'
    docs = {k: json.loads(get_bytes(f'{base}/{k}').decode('utf-8-sig')) for k in NAMES}
    validate(docs['status.json'], docs['public_indicators.json'])
    DEST.mkdir(parents=True, exist_ok=True)
    for filename in NAMES:
        (DEST / filename).write_text(json.dumps(docs[filename], ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    age = docs['status.json']['generatedAt']
    print(f'웹 배포용 최신 성공 경제지표 복원 완료. 이전 수집/발행 시각 유지: {age}')
    # Explicitly disclose that this deployment does not represent a new collection.
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f:
            f.write('## 웹사이트 배포 (경제지표 수집과 분리)\n'
                    f'- 마지막 정상 수집 스냅샷 보존: `{age}`\n'
                    '- 이번 작업에서 **새 공식 경제지표를 수집하지 않았습니다.**\n'
                    '- 공식 재무계획 및 승인 여부는 변경되지 않았습니다.\n')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print('::error::'+str(exc), file=sys.stderr)
        sys.exit(1)
