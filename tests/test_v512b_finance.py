"""Read-only 6-month goal-funding and loan-cashflow replan scenarios."""
import subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'docs/js/rolling_projection_v512b.js'
HTML = ROOT / 'docs/index.html'


def node(source):
    out = subprocess.run(['node', '-e', source], cwd=ROOT, text=True, capture_output=True)
    assert out.returncode == 0, out.stderr[-3000:]
    return out.stdout.strip()

HEAD = f'''const assert=require('node:assert/strict');
const fs=require('fs');
const v=require({str(JS)!r});
const html=fs.readFileSync({str(HTML)!r},'utf8');
const match=html.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s);
assert.ok(match,'Workbook monthly ledger not found');
const book=Object.fromEntries(JSON.parse(match[1]));
'''


def test_base_ledger_is_immutable_and_financing_unchanged_when_no_new_records():
    out = node(HEAD + '''const before=JSON.stringify(book);
const res=v.compute(book,[],{asOf:'2027-05'});
assert.equal(res.ready,true);assert.equal(res.ledgerVerified,605);assert.equal(res.mayApprove,false);
assert.equal(res.finance.homePrice,763747266);assert.equal(res.finance.homeMonthly,1675319);
assert.equal(res.finance.carPrice,58885412);assert.equal(res.finance.carMonthly,532860);
assert.equal(res.finance.tripPrice,6724444);
assert.equal(res.environment.homeGrowth.updated,false);assert.equal(res.environment.deposit.updated,false);
assert.equal(res.retirementAfterExcluded,true);
assert.equal(JSON.stringify(book),before);
assert.equal(res.monthlyResults['2027-04'].previewCash,res.monthlyResults['2027-04'].baselineCash);
assert.equal(res.monthlyResults['2056-04'].previewCash,null);
assert.ok(res.eventAudit.every(x=>x.funded));console.log('ok');''')
    assert out == 'ok'


def test_car_cpi_reprices_auto_loan_from_nov_2034_not_before():
    out=node(HEAD+'''const res=v.compute(book,[],{asOf:'2027-05',scenarios:{carMA3:'121.5'}});
assert.equal(res.ready,true);assert.ok(res.finance.carPrice>58885412);
assert.equal(res.goals.car.goal,20000000);
assert.ok(res.finance.carLoan>28236648);
assert.ok(res.finance.carMonthly>532860);
assert.equal(res.monthlyResults['2034-10'].loanPaymentChange,0);
assert.equal(res.monthlyResults['2034-11'].loanPaymentChange,res.finance.carMonthly-532860);
assert.equal(res.monthlyResults['2027-04'].previewCash,res.monthlyResults['2027-04'].baselineCash);
assert.equal(res.environment.car.manual,true);
const event=res.eventAudit.find(x=>x.key==='car');assert.ok(event.funded);
assert.equal(event.transferred,20000000);console.log('ok');''')
    assert out=='ok'


def test_travel_index_updates_goal_month_savings_and_funds_full_event():
    out=node(HEAD+'''const res=v.compute(book,[],{asOf:'2027-05',scenarios:{travelMA12:132}});
assert.equal(res.ready,true);assert.equal(res.environment.travel.manual,true);
assert.ok(res.finance.tripPrice>6724444);
assert.ok(res.goals.travel.newSaving>res.goals.travel.oldSaving);
const evt=res.eventAudit.find(x=>x.key==='travel');
assert.equal(evt.required,res.finance.tripPrice);assert.equal(evt.transferred,evt.required);
assert.equal(evt.unfunded,0);
assert.equal(res.monthlyResults['2038-10'].directEventFundingGap,0);
console.log('ok');''')
    assert out=='ok'


def test_home_growth_and_mortgage_changes_loan_and_own_cash_without_new_ltv_claim():
    out=node(HEAD+'''const r=v.compute(book,[],{asOf:'2027-05',scenarios:{homeGrowth:1.0,mortgageRate:4.2}});
assert.equal(r.ready,true);assert.ok(r.finance.homePrice>763747266);
assert.ok(r.finance.own>141486810);
assert.ok(r.finance.loan<363598263);assert.equal(r.finance.loanConstraintRecomputed,true);
assert.equal(r.finance.own,r.finance.homePrice-r.finance.oldHomeNet-r.finance.loan);
assert.ok(r.finance.homeMonthly>0);
assert.equal(r.monthlyResults['2046-10'].loanPaymentChange,0);
assert.equal(r.monthlyResults['2046-11'].loanPaymentChange,r.finance.homeMonthly-1675319);
const e=r.eventAudit.find(x=>x.key==='house');assert.equal(e.required,r.finance.own);
assert.ok(e.funded);console.log('ok');''')
    assert out=='ok'


def test_customer_balance_saves_less_and_never_recategorizes_it_as_proven_history():
    out=node(HEAD+'''const before=v.compute(book,[],{asOf:'2027-05'});
const after=v.compute(book,[],{asOf:'2027-05',balances:{house:25000000,car:1800000,travel:1700000}});
assert.equal(after.ready,true);
for(const key of ['house','car','travel']){
 assert.equal(after.goals[key].confirmed,true);
 assert.ok(after.goals[key].newSaving<before.goals[key].newSaving);
 assert.match(after.goals[key].balanceStatus,/미증빙/);
}
assert.equal(after.monthlyResults['2027-04'].previewCash,before.monthlyResults['2027-04'].previewCash);
console.log('ok');''')
    assert out=='ok'


def test_rate_observation_must_be_contiguous_and_basis_consistent():
    out=node(HEAD+'''const months=require('./docs/js/rolling_preview_v512a.js');
let observations=[];for(let i=0;i<120;i++){
 observations.push({id:'MORTGAGE',date:months.shift('2017-05',i),value:4.2,unit:'%'});
}for(let i=0;i<60;i++){
 observations.push({id:'DEPOSIT',date:months.shift('2022-05',i),value:3.6,unit:'%'});
}
const res=v.compute(book,observations,{asOf:'2027-05'});
assert.equal(res.ready,true);
assert.ok(res.environment.deposit.updated);assert.ok(res.environment.mortgage.updated);
assert.ok(Math.abs(res.environment.mortgage.value-4.2)<1e-10);
assert.ok(Math.abs(res.environment.deposit.annualNet-3.6/100*.846)<1e-10);
assert.equal(res.environment.car.ready,false);
console.log('ok');''')
    assert out=='ok'


def test_rone_121_consecutive_months_required_and_old_basis_excluded():
    out=node(HEAD+'''const base=require('./docs/js/rolling_preview_v512a.js');
const oldId=[{id:'HOME_PRICE_APT_DAEJEON_SEOGU',date:'2037-02',value:128,unit:'2022=100'}];
const unusable=v.homeGrowth(oldId,'2037-05');assert.equal(unusable.ready,false);
const series=[];for(let i=0;i<121;i++)series.push({id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:base.shift('2027-01',i),value:100*Math.pow(1.001,i),unit:'2026-06=100'});
const observed=v.homeGrowth(series,'2037-05');assert.equal(observed.ready,true);
assert.ok(observed.annualPct>1 && observed.annualPct<2);
const env=v.buildEnvironment(series,'2037-05',{scenarios:{}});assert.equal(env.ready,true);
assert.equal(env.homeGrowth.updated,true);
console.log('ok');''')
    assert out=='ok'


def test_goals_past_date_not_repriced_and_future_retirement_risk_not_reported():
    out=node(HEAD+'''const r=v.compute(book,[],{asOf:'2047-05',scenarios:{homeGrowth:2,mortgageRate:4.2,carMA3:200,travelMA12:200}});
assert.equal(r.ready,true);assert.equal(r.goals.house.active,false);
assert.equal(r.goals.car.active,false);assert.equal(r.goals.travel.active,false);
assert.equal(r.monthlyResults['2047-05'].loanPaymentChange,0);
assert.equal(r.finance.carPrice,58885412);
assert.equal(r.finance.tripPrice,6724444);
assert.equal(r.monthlyResults['2056-04'].previewCash,null);
console.log('ok');''')
    assert out=='ok'


def test_invalid_inputs_stop_scenarios_safely():
    out=node(HEAD+'''assert.equal(v.compute(book,[],{asOf:'2027-04'}).ready,false);
assert.equal(v.compute(book,[],{asOf:'2027-05',scenarios:{mortgageRate:-1}}).ready,false);
assert.equal(v.compute(book,[],{asOf:'2027-05',scenarios:{carMA3:'hello'}}).ready,false);
assert.equal(v.compute(book,[],{asOf:'2027-05',balances:{house:-100}}).ready,false);
assert.equal(v.compute(book,[],{asOf:'2027-05',actualSpending:'-1'}).ready,false);
console.log('ok');''')
    assert out=='ok'


def test_web_wiring_and_official_lock():
    s=HTML.read_text(encoding='utf-8')
    assert 'src="./js/rolling_preview_v512a.js"' in s
    assert 'src="./js/rolling_projection_v512b.js"' in s
    assert 'IFPK_V512B.compute(INITIAL_MONTHLY' in s
    assert 'V51-2d · 은퇴 전 롤링 검토 · 공식 계획 미변경' in s
    assert '공식 계획 적용은 잠금 상태' in s
    assert '2026년 11월 월 생활비 240만원' in s
    assert 'data-v512-field="carMA3"' not in s  # field ids produced dynamically by makeInput
    assert "makeInput('carMA3'" in s
    assert 'data-v51-approve' not in s


def test_rone_actual_elapsed_index_is_applied_even_without_new_120_month_cagr():
    out=node(HEAD+'''const base=require('./docs/js/rolling_preview_v512a.js');
const records=[];for(let i=0;i<8;i++)records.push({id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:base.shift('2026-09',i),value:100*(1+0.002*i),unit:'2026-06=100'});
const changed=v.compute(book,records,{asOf:'2027-05'});
assert.equal(changed.ready,true);
assert.equal(changed.environment.homeActual.ready,true);
assert.equal(changed.environment.homeGrowth.updated,false);
assert.ok(changed.finance.homePrice>v.HOME_BASE.newPrice);
assert.ok(changed.goals.house.newSaving>345345);
console.log('ok');''')
    assert out=='ok'


def test_conflicting_index_or_interest_basis_is_rejected_not_passed_as_official():
    out=node(HEAD+'''const bad=v.compute(book,[{id:'CPI_CAR',date:'2027-04',value:120,unit:'2025=100'}],{asOf:'2027-05'});assert.equal(bad.ready,true);assert.equal(bad.environment.carBlocked,true);assert.equal(bad.goals.car.active,false);
const invalidRate=v.compute(book,[{id:'DEPOSIT',date:'2027-04',value:3.8,unit:'bp'}],{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(invalidRate.ready,true);assert.equal(invalidRate.environment.depositBlocked,true);assert.equal(invalidRate.goals.car.active,false);assert.equal(invalidRate.monthlyResults['2027-05'].previewGeneral,2465005);
const same=[{id:'CPI_CAR',date:'2027-04',value:120,unit:'2020=100'},{id:'CPI_CAR',date:'2027-04',value:122,unit:'2020=100'}];
const duplicate=v.compute(book,same,{asOf:'2027-05'});assert.equal(duplicate.ready,true);assert.equal(duplicate.environment.carBlocked,true);
console.log('ok');''')
    assert out=='ok'
