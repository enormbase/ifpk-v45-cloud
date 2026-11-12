"""V59: confirmation-gated four-goal month advance and separated source-of-truth views."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'docs'/'index.html').read_text('utf8')

def test_v59_bounded_dom_purpose():
 assert 'data-v59-advance' in S
 assert 'IFPK_V57.pendingReady(v57Progress,goals,date)' in S
 assert 'nextMonth=IFPK_V57.nextMonth(date)' in S
 assert 'function v59GoalDestination(' in S
 assert 'class="v59-goal-fill"' in S
 assert 'v59GoalDestination(date,sim,g)' in S
 assert '지난달 저축 실행 결과' not in S or '저축 실행 결과' in S
 assert 'v58HistoryPanel(date,sim,history)' in S
 assert 'function v59PlanBasisBanner()' in S
 assert 'function v59ConsumerComparison()' in S
 assert 'function v59FlowPanel()' in S
 assert 'function v59LatestSources()' in S
 assert '대시보드 V59</title>' in S

def test_v59_removed_semiannual_controls_only_in_data_page():
 data=S[S.index('function dataPage()'):S.index('function checkPage()')]
 for old in ['${v50ReviewBrief()}', '${v513fHubPanel()}', '${v51ReviewPanel()}', '${v512PreviewPanel()}']:
  assert old not in data
 assert '${v59LatestSources()}' in data
 assert '${v501Chart(rows,spec.unit)}' in data
 assert '과거 월별 데이터 확인' in data

def test_v59_numeric_source_and_cashflow():
 p=subprocess.run(['node',str(ROOT/'tests'/'run_v59_tests.js')],cwd=ROOT,capture_output=True,text=True,timeout=60)
 assert p.returncode==0,p.stdout+'\n'+p.stderr
 assert 'V59 PASS' in p.stdout
