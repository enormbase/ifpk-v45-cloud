"""V51-2e account-reconciliation contract; read-only, evidence-aware."""
from pathlib import Path
import json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf-8')
NEW=ROOT/'docs/js/reconciliation_v512e.js'
FIN=ROOT/'docs/js/rolling_projection_v512b.js'

def run(js):
    m=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
    assert m,'ledger must be preserved'
    pre=f'''const assert=require('node:assert/strict');
const source=Object.fromEntries({m.group(1)}); const original=JSON.stringify(source);
const finance=require({json.dumps(str(FIN))});
const audit=require({json.dumps(str(NEW))});
const report=finance.compute(source,[],{{asOf:'2027-05'}});
assert.equal(report.ready,true);'''
    p=subprocess.run(['node','-e',pre+js],cwd=ROOT,capture_output=True,text=True)
    assert p.returncode==0,p.stderr[-5000:]
    return p.stdout.strip()

def test_empty_fields_must_not_be_verified():
    run('''const r=audit.reconcile(source,report,{},'2026-11');
assert.equal(r.ready,true);assert.equal(r.future,true);assert.equal(r.enteredCount,0);
assert.equal(r.fundsAggregate.mathematicallyConsistent,false);assert.equal(r.fundsAggregate.delta,null);
assert.equal(r.retirementRecomputed,false);assert.equal(r.mortgageAppliedToDSR,false);
assert.equal(r.mayApprove,false);assert.equal(JSON.stringify(source),original);''')

def test_future_balance_inputs_only_scenarios_and_plan_savings_recalculated():
    run('''const withBalances=finance.compute(source,[],{asOf:'2027-05',balances:{house:20000000,car:1000000,travel:500000}});
const inputs={liquidCash:0,house:20000000,car:1000000,travel:500000,retirementAssets:30000000,mortgageOutstanding:250000000,fundsAggregate:21500000};
const r=audit.reconcile(source,withBalances,inputs,'2026-11');
assert.equal(r.ready,true);assert.equal(r.enteredCount,6);assert.equal(r.fundsAggregate.delta,0);
assert.equal(r.fundsAggregate.mathematicallyConsistent,true);assert.equal(r.future,true);
assert.equal(r.accounts.find(x=>x.key==='house').input,20000000);
assert.match(r.accounts.find(x=>x.key==='house').status,/미래/);
assert.equal(r.accounts.find(x=>x.key==='house').saving,withBalances.goals.house.newSaving);
assert.equal(JSON.stringify(source),original);''')

def test_partial_balance_must_not_claim_match():
    run('''const r=audit.reconcile(source,report,{house:10000000,fundsAggregate:10000000},'2026-11');
assert.equal(r.ready,true);assert.equal(r.enteredCount,1);
assert.equal(r.fundsAggregate.delta,null);assert.equal(r.fundsAggregate.mathematicallyConsistent,false);
assert.match(r.fundsAggregate.status,/보류/);''')

def test_totals_mismatch_detects_not_silently_fund():
    run('''const input={liquidCash:'0',house:'20000000',car:'1000000',travel:'500000',fundsAggregate:'21599999'};
const r=audit.reconcile(source,report,input,'2026-11');
assert.equal(r.fundsAggregate.delta,99999);assert.equal(r.fundsAggregate.mathematicallyConsistent,false);
assert.match(r.fundsAggregate.status,/불일치/);
assert.equal(r.purposeSavingsUnchangedByCash,true);assert.equal(JSON.stringify(source),original);''')

def test_debt_and_retirement_values_only_record_not_change_loan_dsr_or_pensions():
    run('''const a=audit.reconcile(source,report,{},'2026-11');
const b=audit.reconcile(source,report,{mortgageOutstanding:'260000000',retirementAssets:'30000000'},'2026-11');
assert.equal(b.mortgage.value,260000000);assert.equal(b.retirement.value,30000000);
assert.equal(b.retirementRecomputed,false);assert.equal(b.mortgageAppliedToDSR,false);
assert.equal(report.finance.loan,finance.compute(source,[],{asOf:'2027-05'}).finance.loan);
assert.equal(b.accounts[0].plan,a.accounts[0].plan);assert.equal(JSON.stringify(source),original);''')

def test_invalid_values_rejected_and_zero_valid():
    run('''assert.equal(audit.reconcile(source,report,{liquidCash:0,house:0,car:0,travel:0,fundsAggregate:0},'2026-11').fundsAggregate.mathematicallyConsistent,true);
for(const q of [{house:-1},{car:'abc'},{travel:1e20},{retirementAssets:1.25},{mortgageOutstanding:'-5'},{fundsAggregate:'inf'}]){
  const r=audit.reconcile(source,report,q,'2026-11');assert.equal(r.ready,false);}
assert.equal(JSON.stringify(source),original);''')

def test_at_past_as_of_still_not_confirmed_without_evidence():
    run('''const r=audit.reconcile(source,report,{house:'15000000'},'2028-06');
assert.equal(r.future,false);assert.match(r.accounts.find(x=>x.key==='house').status,/증빙 미확인/);
assert.equal(r.mayApprove,false);''')

def test_html_exposes_simple_collapsed_panel_with_correct_script_order():
    assert 'V51-2g' in HTML
    assert '계좌별 자산·대출잔액 대사(선택)' in HTML
    assert '⑧ 내 돈이 계획대로 모였는지 확인' in HTML
    assert '<details class="v512-details"><summary>계좌별 예상 금액과 입력 금액 비교' in HTML
    assert HTML.index('affordability_v512d.js') < HTML.index('reconciliation_v512e.js')
    assert '공식 계획 적용은 잠금 상태' in HTML
