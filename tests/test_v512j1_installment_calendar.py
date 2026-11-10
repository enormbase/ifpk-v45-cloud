"""V51-2j.1 360-payment first/last month calendar and cross-tab ledger checks."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')

def loaded(pattern):
    m=re.search(pattern,HTML,re.S)
    assert m,pattern
    return json.loads(m.group(1))

MONTHLY=dict(loaded(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT='))
MODEL=loaded(r'const MODEL=(\{.*?\});</script>')
RETIRE=loaded(r'const RETIRE_SNAPSHOT=Object.fromEntries\(Object.entries\((\{.*?\})\)\.map\(')

def test_605_month_baseline_conservation():
    assert len(MONTHLY)==605
    assert next(iter(MONTHLY))=='2026-11'
    assert list(MONTHLY)[-1]=='2077-03'
    js='''const fs=require('fs');const s=fs.readFileSync('docs/index.html','utf8');const data=Object.fromEntries(JSON.parse(s.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s)[1]));const x=require('./docs/js/replan_v51.js').inspectLedger(data);if(!x.ready)throw Error(JSON.stringify(x));console.log(x.months,x.maxCashMismatch,x.maxNetMismatch)'''
    r=subprocess.run(['node','-e',js],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    assert r.stdout.startswith('605 ')

def test_house_move_month_is_zero_debt_repayment_and_next_month_first():
    oct=MONTHLY['2046-10'];nov=MONTHLY['2046-11'];sep=MONTHLY['2046-09']
    assert oct[2]==4204543
    assert nov[2]==5879862
    assert nov[2]-oct[2]==1675319
    assert oct[6]==oct[0]-oct[2]-oct[3]-oct[4]-oct[5]
    assert nov[6]==nov[0]-nov[2]-nov[3]-nov[4]-nov[5]
    assert oct[16]==120423634
    assert sep[16]==118826126
    assert nov[16]==120345824
    assert oct[3]==141486810 and oct[14]==oct[3] # no double cash deduction for home saving transfer
    assert next(r for r in MODEL['monthly'] if r[0]=='2046-10')[1]==oct

def test_new_loan_is_360_months_no_2p5_inflation_and_ends_nov_2076():
    assert 'first:\'2046-11\'' in HTML
    assert 'last:\'2076-10\'' in HTML
    assert 'zero:\'2076-11\'' in HTML
    assert 'months:360' in HTML
    assert 'function newLoanScheduledPayment(month)' in HTML
    assert RETIRE['2076-10'][0]-RETIRE['2076-11'][0] in (1675319,1675320)
    assert RETIRE['2076-10'][3]-RETIRE['2076-11'][3] in (1675319,1675320)
    assert RETIRE['2056-04'][3]==5625415
    assert MODEL['metrics']['neededRetirement']==498798806

def test_customer_goal_rollover_and_6_tab_visibility():
    assert 'date>plan.homeMonth?plan.homePay' in HTML
    assert "date>=NEW_LOAN_CAL.first?NEW_LOAN_CAL.payment" in HTML
    js=(ROOT/'docs/js/replan_v51.js').read_text(encoding='utf8')
    assert 'const extraLoan=(month>move&&preRetire)?deltaLoan:0;' in js
    assert "['summary','전체 요약']" in HTML
    assert "['customer','고객정보']" in HTML
    assert "['plans','분야별 설계']" in HTML
    assert "['flow','생애현금흐름']" in HTML
    assert "['data','경제지표·설계 갱신']" in HTML
    assert "['checks','AI 검증·갱신']" in HTML
    assert "newLoanCalendarRibbon(app.tab)+" in HTML
    assert "(app.tab==='checks'?newLoanValidationPanel():'')" in HTML


def test_after_only_cash_increase_without_artificial_retirement_growth():
    first=MONTHLY['2046-10'];last=MONTHLY['2077-03']
    assert first[16]-MONTHLY['2046-09'][16] == 1597508
    assert last[15]==RETIRE['2077-03'][3]
    assert last[7]==0
    assert RETIRE['2077-03'][4]==386865490
