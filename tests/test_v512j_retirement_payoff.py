"""V51-2j: mortgage excluded from inflation, included only during its term.
The official Google Sheet backing formulas were updated separately; these tests
verify the bundled website has the same 252-month payoff reference and 605-month
cash conservation, without treating manual customer inputs as approvals.
"""
from pathlib import Path
import re,json,math,subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
def blob(pat):
    m=re.search(pat,HTML,re.S)
    assert m,pat
    return json.loads(m.group(1))
MODEL=blob(r'const MODEL=(\{.*?\});</script>')
RET=blob(r'const RETIRE_SNAPSHOT=Object.fromEntries\(Object.entries\((\{.*?\})\)\.map\(')
LEDGER=dict(blob(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT='))

def test_calendar_loan_term_and_first_month():
    assert len(RET)==252 and len(LEDGER)==605
    assert next(iter(RET))=='2056-04' and list(RET)[-1]=='2077-03'
    a=RET['2056-04']; assert a[:4]==[5243919,0,381496,5625415]
    assert round(a[0]-1675319)==3568600
    assert MODEL['metrics']['initialRetirement']==666940773

def test_payoff_october_to_november():
    x,y=RET['2076-10'],RET['2076-11']
    assert x[0]==7522885 and y[0]==5847566
    assert x[0]-y[0] in (1675319,1675320)
    assert x[3]-y[3] in (1675319,1675320)
    assert x[1]==y[1] and x[2]==y[2]
    assert round(3568599.7686961694*(1.025)**20)==y[0]

def test_no_double_count_monthly_sheet_columns():
    for key in ['2056-04','2057-01','2076-10','2076-11','2077-03']:
        r=RET[key];m=LEDGER[key]
        assert abs(m[2]-(r[0]+r[2]))<=1
        assert abs(m[6]-(m[0]-m[2]-m[3]-m[4]-m[5]))<=1
        assert m[15]==r[3]
        assert abs(m[1]+m[15]-m[2])<=1
        assert abs(r[4]-(MODEL['metrics']['finalRetirement'] if key=='2077-03' else r[4]))<=1

def test_pension_kept_as_inflow_only_once():
    d='2076-11';r=RET[d];m=LEDGER[d]
    assert m[1]==r[1]
    assert r[3]==round(r[0]+r[2]-r[1])
    assert m[0]==r[1]
    assert m[6]==-r[3]

def test_model_financial_totals_updated_without_dc_addition():
    m=MODEL['metrics'];assert m['neededRetirement']==498798806
    assert m['finalRetirement']==386865490 and m['retireYearEnd']==635553777
    assert m['initialRetirement']-m['dcAfterTax']==252015001
    assert '별도 건강보험료' in HTML and '2076년 10월' in HTML
    assert '⑬ 은퇴 후 대출 완납' in HTML
    assert 'retirement-payoff-breakdown' in HTML

def test_rolling_core_still_valid_after_restating_postretirement_months():
    js=f'''const h=require('fs').readFileSync('docs/index.html','utf8');
const m=h.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s);
const book=Object.fromEntries(JSON.parse(m[1]));
const r=require('./docs/js/rolling_preview_v512a.js').readLedger(book);
if(!r.ready)throw Error(r.reason);console.log(r.months,r.maxCashDiff);'''
    t=subprocess.run(['node','-e',js],capture_output=True,text=True,cwd=ROOT)
    assert t.returncode==0,t.stderr
    assert '605' in t.stdout
