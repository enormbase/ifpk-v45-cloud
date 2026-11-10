"""V51-2k authoritative monthly, retirement, annual, and live-source safeguards."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
BOOK=json.loads((ROOT/'docs/data/v512k_authoritative_605.json').read_text(encoding='utf8'))
AUDIT=json.loads((ROOT/'docs/data/v512k_audit_summary.json').read_text(encoding='utf8'))
ledger=dict(json.loads(re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S).group(1)))
retire=json.loads(re.search(r'const RETIRE_SNAPSHOT=Object.fromEntries\(Object.entries\((\{.*?\})\)\.map\(',HTML,re.S).group(1))
model=json.loads(re.search(r'const MODEL=(\{.*?\});</script>',HTML,re.S).group(1))
mortgage=json.loads(re.search(r'const MORTGAGE_SHEET_605=(\{.*?\});',HTML,re.S).group(1))

def test_605_months_match_exported_sheet_every_integer():
    assert len(ledger)==605
    assert ledger==BOOK['monthly']
    assert AUDIT['changedMonthsAgainstV51_2j1']==605
    assert ledger['2026-11'][7]==120846
    assert ledger['2026-11'][16]==210017
    assert ledger['2077-03'][16]==37426215
    assert model['metrics']['finalRetirement']==386865490

def test_postretirement_wage_and_pension_are_separate():
    assert len(retire)==252 and retire==BOOK['retire']
    for date in retire:
        row=ledger[date];r=retire[date]
        assert row[0]==0, date
        assert row[1]==r[1],date
        assert abs(row[2]-r[0]-r[2])<=1,date
        assert row[15]==r[3],date
    assert ledger['2058-05'][1]==3235717
    assert ledger['2058-05'][0]==0

def test_annual_graph_data_comes_from_sheet():
    parsed=[[int(float(x)) if i==0 else float(x) for i,x in enumerate(y.split(','))] for y in model['annual'].split(';')]
    assert len(parsed)==52
    assert parsed==BOOK['annual']
    assert parsed[0][0]==2026 and parsed[-1][0]==2077
    assert parsed[-1][6]==37.4  # sheet's end-of-period general cash, million won

def test_loan_term_and_living_cash_requirements():
    assert mortgage==BOOK['mortgage']
    assert mortgage['2046-10']==0
    assert mortgage['2046-11']==1675319
    assert mortgage['2076-10']==1675319
    assert mortgage['2076-11']==0
    assert ledger['2046-10'][2]==4958562
    assert ledger['2046-11'][2]==6641965
    assert ledger['2076-11'][2]==6022604
    assert ledger['2076-11'][15]==1814061

def test_deficits_not_hidden_as_borrowing_or_return():
    pre={k:v for k,v in ledger.items() if k<'2056-04'}
    neg={k:v[16] for k,v in pre.items() if v[16]<0}
    assert len(neg)==285
    assert next(iter(neg))=='2027-02'
    assert min(neg,key=neg.get)=='2039-10'
    assert min(neg.values())==-32453069
    assert AUDIT['negativeCashMonthsBeforeRetirement']==285
    assert not any('자금조달 완료' in t for t in (ROOT/'docs/CHANGELOG_KO.md').read_text().splitlines()[:12])

def test_node_audit_pass_and_mutations_detected():
    script='''const d=require('./docs/data/v512k_authoritative_605.json');const a=require('./docs/js/source_audit_v512k.js');const r=Object.fromEntries(Object.entries(d.retire).map(([m,v])=>[m,{living:v[0],pension:v[1],insurance:v[2],withdraw:v[3],balance:v[4]}]));const base=a.audit(d.monthly,r,d.annual,d.mortgage);if(!base.ready||base.checks.some(x=>!x[1]))throw Error('base fail '+JSON.stringify(base));const mutated=JSON.parse(JSON.stringify(d.monthly));mutated['2058-05'][0]=mutated['2058-05'][1];if(a.audit(mutated,r,d.annual,d.mortgage).ready)throw Error('double pension not caught');const mortgage={...d.mortgage,'2076-11':1675319};if(a.audit(d.monthly,r,d.annual,mortgage).ready)throw Error('post payoff not caught');mutated['2058-05'][0]=0;mutated['2027-03'][16]+=500;if(a.audit(mutated,r,d.annual,d.mortgage).ready)throw Error('cash error not caught');console.log('6/6 passed; mutations detected');'''
    p=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    assert '6/6' in p.stdout

def test_all_six_tabs_and_client_accuracy_guards():
    assert 'LIFE PLAN STUDIO · IFPK V51-3d' in HTML
    assert 'function v512kBrief' in HTML
    assert 'function v512kAuditDetail' in HTML
    assert "app.tab==='checks'?v512kAuditDetail()+newLoanValidationPanel()" in HTML
    for tab in ['summary:summaryPage','customer:customerPage','plans:goalPage','flow:flowPage','data:dataPage','checks:checkPage']:
        assert tab in HTML
    for module in ['replan_v51.js','rolling_preview_v512a.js']:
        js=(ROOT/'docs/js'/module).read_text()
        assert ('row.income+row.pension-' in js or 'row[0]+row[1]-' in js)
    assert '실제 은행계좌 잔액 확인' in HTML
    assert '시트 원장 대사' in HTML
