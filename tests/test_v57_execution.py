from pathlib import Path
S=(Path(__file__).resolve().parents[1]/'docs/index.html').read_text('utf8')
SUMMARY=S[S.index('function summaryPage()'):S.index('// 고객 입력 초안은 전체요약')]

def test_v57_four_goals_live_ui():
 assert '${v57Roadmap()}' in SUMMARY
 assert '${v54SavingsRoadmap(dt)}' not in SUMMARY
 for token in ('v57-goal','data-v57-input','data-v57-check','data-v57-lane','v57-person','v57-destination'):
  assert token in S

def test_v57_commit_and_replan():
 assert 'IFPK_V57.pendingReady(v57Progress,goals,date)' in S
 assert 'IFPK_V57.closeMonth(v57Progress,goals,date,snap)' in S
 assert 'v55Draft.actuals[date]' in S
 assert 'v55Save();v57Progress=result.state;v57Save();render()' in S
 assert 'v55State()' in S
 assert 'v57BindEvents();' in S

def test_v57_simplified_monthly_note():
 assert '표시된 미래 금액은 예상치이며 실제 저축 결과에 따라 달라질 수 있어요.' in S
 assert '새 자료가 없으면 기존 지표를 사용해요. 현재 결과는 미승인 시뮬레이션' not in SUMMARY
 assert '지표 기준월' in S
