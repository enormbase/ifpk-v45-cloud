"""V51-2c: conditional LTV/DSR scenario math, status isolation, pre-retirement link."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'docs/index.html'
LOAN=ROOT/'docs/js/loan_scenarios_v512c.js'
FIN=ROOT/'docs/js/rolling_projection_v512b.js'
HEAD=f'''const assert=require('node:assert/strict');
const fs=require('node:fs');
const finance=require({str(FIN)!r});const lending=require({str(LOAN)!r});
const html=fs.readFileSync({str(HTML)!r},'utf8');
const match=html.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s);
assert.ok(match); const original=Object.fromEntries(JSON.parse(match[1]));
'''
def run(body):
    p=subprocess.run(['node','-e',HEAD+body],capture_output=True,text=True,cwd=ROOT)
    assert p.returncode==0,p.stderr[-3000:]

def test_reference_reproduces_sheet_three_scenario_loans_and_equity():
    run('''const r=lending.assess(763747266,3.708,258662193,'base');
assert.equal(r.ready,true);assert.equal(r.cases.tight.maxLoan,318148480);
assert.equal(r.cases.base.maxLoan,363598263);
assert.equal(r.cases.loose.maxLoan,409048046);
assert.equal(r.cases.base.requiredOwn,141486810);
for(const c of Object.values(r.cases))assert.equal(763747266,258662193+c.maxLoan+c.requiredOwn);
assert.equal(r.actualEligibilityVerified,false);
assert.match(r.assumptions,/스트레스 DSR/);
''')

def test_interest_rise_reduces_borrowing_capacity_and_increases_upfront_equity():
    run('''const base=finance.compute(original,[],{asOf:'2027-05'});
const higher=finance.compute(original,[],{asOf:'2027-05',scenarios:{mortgageRate:4.2}});
assert.equal(higher.ready,true);assert.equal(higher.finance.loanConstraintRecomputed,true);
assert.ok(higher.finance.loan<base.finance.loan);
assert.ok(higher.finance.own>base.finance.own);
assert.equal(higher.finance.homePrice,higher.finance.loan+higher.finance.oldHomeNet+higher.finance.own);
assert.ok(Math.abs(higher.finance.homeMonthly-base.finance.homeMonthly)<1500);
assert.equal(higher.monthlyResults['2027-04'].previewCash,higher.monthlyResults['2027-04'].baselineCash);
assert.equal(higher.monthlyResults['2046-10'].loanPaymentChange,0);
''')

def test_selecting_tight_and_loose_scenarios_changes_lending_and_savings():
    run('''const b=finance.compute(original,[],{asOf:'2027-05'});
const t=finance.compute(original,[],{asOf:'2027-05',scenarios:{borrowingCase:'tight'}});
const l=finance.compute(original,[],{asOf:'2027-05',scenarios:{borrowingCase:'loose'}});
assert.equal(t.ready,true);assert.equal(l.ready,true);
assert.ok(t.finance.loan<b.finance.loan&&b.finance.loan<l.finance.loan);
assert.ok(t.goals.house.newSaving>b.goals.house.newSaving&&b.goals.house.newSaving>l.goals.house.newSaving);
assert.equal(t.finance.borrowing.selected,'tight');assert.equal(l.finance.borrowing.selected,'loose');
assert.equal(t.monthlyResults['2027-04'].previewCash,b.monthlyResults['2027-04'].previewCash);
''')

def test_optional_customer_house_equity_cannot_exceed_mortgage_cap():
    run('''const b=finance.compute(original,[],{asOf:'2027-05'});
const bad=finance.compute(original,[],{asOf:'2027-05',houseGoal:b.finance.own-1000000});
assert.equal(bad.ready,false);assert.match(bad.reason,/자기자금/);
const good=finance.compute(original,[],{asOf:'2027-05',houseGoal:b.finance.own+1000000});
assert.equal(good.ready,true);assert.ok(good.finance.loan<b.finance.loan);
assert.equal(good.finance.own,good.finance.homePrice-good.finance.oldHomeNet-good.finance.loan);
''')

def test_dsr_or_ltv_ceiling_binds_as_conditions_change():
    run('''const hi=lending.assess(763747266,20,258662193,'base');
assert.equal(hi.ready,true);assert.equal(hi.chosen.binding,'DSR 환산 제한');
const low=lending.assess(763747266,0,0,'base');
assert.equal(low.ready,true);assert.equal(low.chosen.binding,'LTV 제한');
for(const r of [hi,low])assert.equal(r.chosen.maxLoan+r.oldNet+r.chosen.requiredOwn,r.price);
assert.equal(lending.assess(100000000,-1,0).ready,false);
assert.equal(lending.assess(100000000,2,0,'unknown').ready,false);
''')

def test_corrupted_mortgage_rate_freezes_house_only():
    run('''const records=[{id:'MORTGAGE',date:'2027-04',value:425,unit:'bp'}];
const r=finance.compute(original,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.mortgageBlocked,true);
assert.equal(r.environment.homeBlocked,true);
assert.equal(r.goals.house.active,false);
assert.equal(r.goals.car.active,true);assert.equal(r.goals.travel.active,true);
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
''')

def test_corrupted_deposit_rate_preserves_consumer_preview_and_freezes_goal_savings():
    run('''const records=[{id:'DEPOSIT',date:'2027-04',value:2.5,unit:'bp'}];
const r=finance.compute(original,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.depositBlocked,true);
assert.ok(Object.values(r.goals).every(x=>x.active===false));
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
assert.equal(r.monthlyResults['2027-04'].baselineCash,r.monthlyResults['2027-04'].previewCash);
''')

def test_retirement_link_is_just_pre_retirement_liquidity_not_asset_fv():
    run('''const before=JSON.stringify(original);
const r=finance.compute(original,[],{asOf:'2027-05',hypotheticalCPI:124,scenarios:{borrowingCase:'tight'}});
assert.equal(r.ready,true);assert.equal(r.mayApprove,false);
assert.equal(r.preRetirementLink.month,'2056-03');
assert.equal(r.preRetirementLink.retirementAssetsRecalculated,false);
assert.ok(Number.isFinite(r.preRetirementLink.change));
assert.equal(r.monthlyResults['2056-04'].previewCash,null);
assert.equal(JSON.stringify(original),before);
''')

def test_ui_displays_ltv_dsr_scenarios_and_disclaimers():
    html=HTML.read_text('utf8')
    assert 'V51-2h · 은퇴 전 롤링 검토 · 공식 계획 미변경' in html
    assert 'loan_scenarios_v512c.js' in html
    assert 'LTV·DSR 3가지 가정 비교' in html
    assert 'borrow.cases' in html
    assert "borrow.chosen.label" in html
    assert '스트레스 DSR' in html
    assert 'retirementAudit' in html
    assert '은퇴자산, 국민연금, DC·IRP' in html
    assert '공식 계획 적용은 잠금 상태' in html
