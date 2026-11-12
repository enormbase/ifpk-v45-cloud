"""V53 objective-financing UX: 677-month V52 ledger must remain intact."""
from pathlib import Path
import subprocess, json, re
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
DATA=json.loads((ROOT/'docs/data/v52_authoritative_677.json').read_text(encoding='utf8'))

def test_funding_replaces_lifetime_cards_without_deleting_calculation():
    assert '우리 가족의 전체 생애계획 결과' not in HTML
    assert '우리 가족 저축 실행 현황' in HTML
    assert '${v57Roadmap()}' in HTML
    assert 'function v54SavingsRoadmap(date)' in HTML
    assert '실제 납입액 미확인' in HTML
    assert 'data-goal="${g.goto}"' in HTML


def test_summary_distinguishes_plan_and_required_amount():
    assert '이달 계획' in HTML
    assert '개인 은퇴저축' in HTML
    assert '월15만원·2033년 이후 월48만원' in HTML
    assert '실제 납입 완료선' in HTML

def test_cashflow_has_goal_balances_month_and_year():
    assert '${v53FlowFundBalances(dt)}' in HTML
    for x in ['주택 목적잔액','자동차 목적잔액','여행 목적잔액']:
        assert f'<th>{x}</th>' in HTML
    assert '집 · 차 · 여행 잔액' in HTML
    assert 'colspan="13"' in HTML
    assert 'monthInfo(yearEnd)' in HTML

def test_v52_financial_data_unmodified_and_677_months():
    assert len(DATA['monthly'])==677
    assert DATA['monthly']['2028-04'][0]==4132837
    assert len(DATA['retirement'])==324
    assert DATA['retirement']['2083-03'][-1]==80984826

def test_dynamic_render_functions_execute_in_node():
    r=subprocess.run(['node',str(ROOT/'test_v53_runtime.js')],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert 'passed!' in r.stdout
