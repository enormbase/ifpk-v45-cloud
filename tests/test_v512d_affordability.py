"""V51-2e: 6-month execution diagnostics; never auto-fund missing cash."""
from pathlib import Path
import json, re, subprocess
ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'docs/index.html'
MODULE=ROOT/'docs/js/affordability_v512d.js'
FIN=ROOT/'docs/js/rolling_projection_v512b.js'

def run(js):
    html=INDEX.read_text('utf-8')
    m=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',html,re.S)
    assert m,'Original 605-month ledger must be intact'
    head=f"""const assert=require('node:assert/strict');
    const raw=Object.fromEntries({m.group(1)});
    const finance=require({json.dumps(str(FIN))});
    const affordable=require({json.dumps(str(MODULE))});
    const before=JSON.stringify(raw);
    """
    p=subprocess.run(['node','-e',head+js],capture_output=True,text=True,cwd=ROOT)
    assert p.returncode==0,p.stderr[-4000:]
    return p.stdout

def test_baseline_separate_plan_and_cash_and_preserve_source():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05',hypotheticalCPI:124});
    assert.equal(p.ready,true);
    const d=affordable.analyze(raw,p);
    assert.equal(d.ready,true);assert.equal(d.months.length,6);
    assert.equal(d.months[0].month,'2027-05');assert.equal(d.months[5].month,'2027-10');
    assert.equal(d.actualInputs.income,false);
    assert.match(d.startingSource,/계획 추정/);
    for(const m of d.months){
      assert.equal(m.afterObligations-m.targetSaving,m.monthlyAfterAll);
      assert.equal(m.targetSaving,m.retirementSaving+m.houseSaving+m.carSaving+m.travelSaving);
      assert.ok(m.fundingGap>=0);assert.ok(m.essentialGap>=0);
      assert.ok(m.targetSaving>=0);
    }
    assert.equal(JSON.stringify(raw),before);assert.equal(p.mayApprove,false);assert.equal(d.mayApprove,false);
    assert.equal(p.monthlyResults['2027-04'].baselineCash,p.monthlyResults['2027-04'].previewCash);""")

def test_extra_debt_reduces_capacity_but_not_planned_saving():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05'});
    const a=affordable.analyze(raw,p),b=affordable.analyze(raw,p,{additionalDebt:'100000'});
    assert.equal(a.ready,true);assert.equal(b.ready,true);
    for(let i=0;i<6;i++){
      assert.equal(b.months[i].afterObligations,a.months[i].afterObligations-100000);
      assert.equal(b.months[i].targetSaving,a.months[i].targetSaving);
    }
    assert.equal(b.closingCash,a.closingCash-600000);
    assert.equal(JSON.stringify(raw),before);""")

def test_liquid_cash_is_separate_from_earmarked_accounts_and_is_only_scenario():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05',balances:{house:12000000,car:1000000,travel:300000}});
    const a=affordable.analyze(raw,p),b=affordable.analyze(raw,p,{liquidCash:'0'});
    assert.equal(b.ready,true);assert.equal(b.startingCash,0);assert.equal(b.actualInputs.liquidCash,true);
    assert.equal(b.closingCash,a.closingCash-a.startingCash);
    assert.equal(JSON.stringify(raw),before);""")

def test_monthly_income_6month_only_and_calculated_with_correct_ledger_inflows():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05'});
    const amount=Number(raw['2027-05'][0]+raw['2027-05'][1])+100000;
    const d=affordable.analyze(raw,p,{monthlyIncome:String(amount)});
    assert.equal(d.months[0].usedIncome,amount);
    assert.equal(d.months.at(-1).month,'2027-10');
    assert.equal(d.actualInputs.income,true);
    assert.match(d.incomeSource,/6개월 임시/);
    assert.equal(JSON.stringify(raw),before);""")

def test_zero_valid_and_invalid_inputs_rejected():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05'});
    assert.equal(affordable.analyze(raw,p,{liquidCash:'0',monthlyIncome:'0',additionalDebt:'0'}).ready,true);
    for(const opt of [{liquidCash:'-1'},{monthlyIncome:'abc'},{additionalDebt:'-1'},{liquidCash:'1e25'}]){
      const d=affordable.analyze(raw,p,opt);assert.equal(d.ready,false);assert.match(d.reason,/입력해/);
    }""")

def test_ltv_dsr_scenario_does_not_claim_customer_debt_underwriting():
    run("""const p=finance.compute(raw,[],{asOf:'2027-05',scenarios:{borrowingCase:'tight',mortgageRate:4.2}});
    const d=affordable.analyze(raw,p,{monthlyIncome:5000000,additionalDebt:200000,liquidCash:0});
    assert.equal(d.ready,true);
    assert.equal(p.finance.actualEligibilityVerified,false);
    assert.match(d.notes.join(' '),/DSR/);
    assert.equal(p.finance.borrowing.selected,'tight');
    assert.equal(JSON.stringify(raw),before);""")

def test_semantics_version_label_and_script_order():
    html=INDEX.read_text('utf-8')
    assert 'V51-2h' in html
    assert 'affordability_v512d.js' in html
    assert html.index('rolling_projection_v512b.js')<html.index('affordability_v512d.js')
    assert '고객 재무정보 확인·추가 입력' in html
    assert '향후 6개월 저축 실행가능성 점검' in html
    assert '고객 확인 월 순유입' in html
    assert '기존 모델에 빠진 추가 월 채무상환' in html
    assert '재설계월 월초 일반현금 잔액' in html
    assert '공식 계획 적용은 잠금 상태' in html
