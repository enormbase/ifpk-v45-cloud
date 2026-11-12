from pathlib import Path
S=(Path(__file__).resolve().parents[1]/'docs/index.html').read_text('utf8')

def test_future_month_input_unlocked_and_scenario_warning():
 assert "const allowed=dueActive;const isScenarioMonth=" in S
 assert "미래월 시뮬레이션" in S
 assert "실제 납입이 이루어진 것으로 간주하지 않으며" in S
 assert "allowed=dueActive&&date<=" not in S

def test_history_delta_and_preexisting_progress_preserved():
 assert "const V57_LOCAL_KEY='ifpk-v57-shared-monthly-close-v1'" in S
 assert "function v58HistoryPanel(" in S
 assert "nextRequiredBefore" in S
 assert "전체 월별 기록 펼쳐 보기" in S
 assert "data-v57-reopen" in S
