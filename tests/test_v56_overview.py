"""V56 summary IA: time navigation, legacy banner relocation and calculation guardrails."""
from pathlib import Path
SRC=(Path(__file__).resolve().parents[1]/'docs/index.html').read_text(encoding='utf8')
SUMMARY=SRC[SRC.index('function summaryPage()'):SRC.index('// 고객 입력 초안은 전체요약')]

def test_life_timeline_precedes_month_selector():
 assert 'function overviewLifeTimeline()' in SRC
 assert '${overviewLifeTimeline()}' in SUMMARY
 assert SUMMARY.index('${overviewLifeTimeline()}')<SUMMARY.index('id="ov-date-select"')<SUMMARY.index('${overviewMonthlyCycle()}')
 assert 'data-life-jump=' in SRC
 assert 'const span=monthsApart(PLAN_START,PLAN_LAST)+1' in SRC

def test_old_home_banners_removed_only_from_summary():
 for old in ('${hmSummaryAlert()}', '${v49SummarySignal()}', '${v50ReviewBrief()}', 'summary-top-grid', 'cycle-banner'):
  assert old not in SUMMARY
 assert 'v512kBrief()+v513StatusRibbon()+newLoanCalendarRibbon(app.tab)' not in SRC
 assert "(app.tab==='checks'?(v512kBrief()+v513StatusRibbon()):'')" in SRC

def test_housing_calendar_moved_to_plans_only():
 assert "${app.goal==='부동산'?newLoanCalendarRibbon('plans'):''}" in SRC
 assert 'function newLoanCalendarRibbon(' in SRC
 assert 'function newLoanValidationPanel(' in SRC

def test_monthly_recalculation_messaging_and_audit():
 assert '${overviewMonthlyCycle()}' in SUMMARY
 assert '${overviewVerification()}' in SUMMARY
 assert '매달, 우리 가족 저축계획을 다시 확인해요' in SRC
 assert '표시된 미래 금액은 예상치이며 실제 저축 결과에 따라 달라질 수 있어요.' in SRC
 assert "location.hash='#checks'" in SRC

def test_boundary_dates_and_v55_execution_retained():
 assert '(y!==2083||v<=3)' in SRC
 assert "'2056-04','◈','만 63세 은퇴'" in SRC
 assert "'2083-04','◇','만 90세 도달 가정'" in SRC
 assert 'IFPK_V55_UI.infoSummary' in SRC
 assert 'IFPK_V55_UI.roadmap' in SRC
 assert 'IFPK V58' in SRC
