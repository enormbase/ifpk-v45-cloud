"""V60 integration guard: live 6-indicator statuses and navy provenance."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
UI=(ROOT/'docs/js/v55_savings_ui.js').read_text(encoding='utf8')

def test_visible_navy_and_six_statuses():
 assert 'v59EconomicSource()' in HTML
 assert 'v60ImpactAudit' in HTML
 assert '${v60ImpactAudit()}' in HTML
 assert './js/v60_indicator_trace.js' in HTML
 assert '이 재무설계에 반영된 경제지표' in UI
 assert '지표별 적용 기준월' in UI
 assert '이번 전망의 계산 기준' not in UI
 assert '별도 집계된 보험·건보료' in (ROOT/'docs/js/v60_indicator_trace.js').read_text(encoding='utf8')

def test_model_adapters():
 r=subprocess.run(['node','tests/run_v60_tests.js'],cwd=ROOT,capture_output=True,text=True,timeout=60)
 assert r.returncode==0,r.stdout+'\n'+r.stderr
 assert 'V60 PASS' in r.stdout
