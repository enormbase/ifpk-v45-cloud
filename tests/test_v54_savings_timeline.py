"""V54 savings roadmap: visuals reflect V52's approved plan, not unconfirmed payments."""
from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf-8')
D=json.loads((ROOT/'docs/data/v52_authoritative_677.json').read_text(encoding='utf-8'))

def test_five_tracks_and_correct_scale():
    assert 'function v54SavingsRoadmap(date)' in HTML
    assert '${v54SavingsRoadmap(dt)}' in HTML
    for token in ['우리 가족 저축 실행 현황','2056-04','2046-10','2034-10','2038-10','2048-04']:
        assert token in HTML
    assert "const tickYears=[2030,2035,2040,2045,2050,2055]" in HTML
    assert 'v54AxisPercent(g.month)' in HTML

def test_no_fake_actual_savings():
    assert '실제 납입 실적 미연결' in HTML
    assert '실제 납입액 미확인' in HTML
    assert '실제 납입 완료선은 증빙 입력 후 표시 예정' in HTML
    assert "monthInfo(date)" in HTML
    assert 'v54RetirementPersonalForecast(date)' in HTML
    assert '개인 은퇴저축 누적 예상' in HTML

def test_childcare_is_expense_not_saving():
    assert '양육비는 저축 달성률로 표시하지 않습니다' in HTML
    assert '별도 목적저축 없음' in HTML

def test_no_change_to_source_data_and_operation_policy():
    assert len(D['monthly'])==677
    assert len(D['retirement'])==324
    assert D['retirement']['2083-03'][-1]==80984826
    assert '매달, 우리 가족 저축계획을 다시 확인해요' in HTML
    assert '종합 재설계 · 6개월마다' not in HTML[HTML.index('function summaryPage()'):HTML.index('// 고객 입력 초안은 전체요약')]
    assert '은행거래 자동확인·공식계획 자동승인은 연결 전' in HTML

def test_long_horizon_monthly_expansion():
    assert 'y>2083)return;' in HTML
    assert 'y>2077)return;' not in HTML
    assert 'function v53FlowFundBalances(date)' in HTML

def test_node_runtime_is_portable():
    js=(ROOT/'test_v53_runtime.js').read_text(encoding='utf-8')
    assert '/mnt/data/' not in js
    r=subprocess.run(['node',str(ROOT/'test_v53_runtime.js')],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    assert 'passed!' in r.stdout
