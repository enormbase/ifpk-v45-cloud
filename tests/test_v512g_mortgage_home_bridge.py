"""V51-2k: payoff-to-equity goal and savings bridge without modifying approved ledger."""
import re,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
JS=ROOT/'docs/js/home_bridge_v512g.js'
SNAP=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert SNAP

def run(code):
    pre=f'''const assert=require('node:assert/strict');
const snapshot=Object.fromEntries({SNAP.group(1)});
const frozen=JSON.stringify(snapshot);
const f=require({json.dumps(str(ROOT/'docs/js/rolling_projection_v512b.js'))});
const g=require({json.dumps(str(JS))});
const debt=require({json.dumps(str(ROOT/'docs/js/debt_retirement_v512f.js'))});
'''
    p=subprocess.run(['node','-e',pre+code],capture_output=True,text=True,cwd=ROOT)
    assert p.returncode==0,p.stderr[-4000:]
    return p.stdout.strip()

def test_baseline_balance_same_and_no_new_money_created():
    run('''const expected=debt.baselineSchedule()['2027-05'].begin;
const r=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:Math.round(expected)});
assert.equal(r.ready,true);assert.equal(r.applied,true);
assert.ok(Math.abs(r.delta.oldMortgageBalance)<=1);
assert.ok(Math.abs(r.delta.netSaleProceeds)<=1);
assert.equal(r.before.newMortgage,r.after.newMortgage);
assert.equal(r.safeguards.identityVerified,true);
assert.equal(JSON.stringify(snapshot),frozen);''')

def test_2027_250m_input_house_savings_equity_and_mortgage():
    run('''const r=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:250000000},'2026-11');
assert.equal(r.ready,true);assert.equal(r.applied,true);
assert.equal(r.after.oldMortgageBalance,100986389);
assert.equal(r.before.oldMortgageBalance,104117759);
assert.equal(r.delta.oldMortgageBalance,-3131370);
assert.equal(r.delta.netSaleProceeds,+3131370);
assert.equal(r.delta.requiredEquity,-3131370);
assert.equal(r.after.requiredEquity,138355440);
assert.equal(r.after.monthlySaving,334979);
assert.equal(r.delta.monthlySaving,-10348);
assert.equal(r.after.newMortgage,363598263);
assert.equal(r.safeguards.pastUntouched,true);
assert.equal(r.preview.monthlyResults['2027-04'].previewCash,r.preview.monthlyResults['2027-04'].baselineCash);
assert.equal(r.preview.goals.house.newSaving,r.after.monthlySaving);
assert.equal(r.preview.goals.car.newSaving, r.debt && f.compute(snapshot,[],{asOf:'2027-05'}).goals.car.newSaving);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_identity_and_upfront_new_loan_limit_scenarios():
    run('''for(const c of ['tight','base','loose']){
const opts={asOf:'2027-05',scenarios:{borrowingCase:c,mortgageRate:4.2}};
const x=g.link(snapshot,[],opts,{mortgageOutstanding:250000000});
assert.equal(x.ready,true);assert.equal(x.applied,true);
assert.equal(x.delta.netSaleProceeds+x.delta.newMortgage+x.delta.requiredEquity,0);
assert.equal(x.preview.finance.homePrice,x.after.netSaleProceeds+x.after.newMortgage+x.after.requiredEquity);
assert.equal(x.preview.finance.loan,x.preview.finance.borrowing.chosen.maxLoan);
assert.equal(x.preview.monthlyResults['2027-04'].previewCash,x.preview.monthlyResults['2027-04'].baselineCash);
}
''')

def test_blank_mortgage_does_not_manufacture_borrower_data():
    run('''const r=g.link(snapshot,[],{asOf:'2027-05'},{retirementAssets:30000000});
assert.equal(r.ready,true);assert.equal(r.applied,false);
assert.match(r.reason,/잔액/);
assert.equal(r.preview.finance.existingMortgageBridgeApplied,false);
assert.equal(r.debt.retirement.projected,true);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_customer_direct_house_equity_target_disables_override():
    run('''const base=f.compute(snapshot,[],{asOf:'2027-05'});
const r=g.link(snapshot,[],{asOf:'2027-05',houseGoal:base.finance.own+2000000},{mortgageOutstanding:250000000});
assert.equal(r.ready,true);assert.equal(r.applied,false);
assert.match(r.reason,/직접/);
assert.equal(r.preview.finance.own,base.finance.own+2000000);
''')

def test_bad_input_does_not_block_general_consumption():
    run('''const r=g.link(snapshot,[],{asOf:'2027-05',hypotheticalCPI:124},{mortgageOutstanding:'abc'});
assert.equal(r.ready,true);assert.equal(r.applied,false);
assert.match(r.reason,/원/);
assert.equal(r.preview.monthlyResults['2027-05'].previewGeneral,2465005);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_rebased_invalid_house_keeps_other_parts_working():
    run('''const records=[{id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:'2026-06',value:99.4,unit:'지수'}];
const r=g.link(snapshot,records,{asOf:'2027-05',hypotheticalCPI:124},{mortgageOutstanding:250000000});
assert.equal(r.ready,true);assert.equal(r.applied,false);
assert.match(r.reason,/보류/);
assert.equal(r.preview.monthlyResults['2027-05'].previewGeneral,2465005);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_post_move_does_not_rewrite_old_house_sale():
    run('''const r=g.link(snapshot,[],{asOf:'2046-11'},{mortgageOutstanding:250000000});
assert.equal(r.ready,true);assert.equal(r.applied,false);
assert.equal(r.debt.mortgage.eligible,false);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_zero_balance_respects_single_payoff():
    run('''const r=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:0});
assert.equal(r.ready,true);assert.equal(r.applied,true);
assert.equal(r.after.oldMortgageBalance,0);
assert.equal(r.after.netSaleProceeds-r.before.netSaleProceeds,104117759);
assert.equal(r.after.requiredEquity,Math.max(0,r.preview.finance.homePrice-r.after.netSaleProceeds-r.after.newMortgage));
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_version_page_and_client_friendly_collapsed_explanation():
    assert 'LIFE PLAN STUDIO · IFPK V51-3d' in HTML
    assert 'home_bridge_v512g.js' in HTML
    assert '⑩ 기존 대출이 달라지면, 이사 준비금은 얼마나 바뀔까요?' in HTML
    assert '<summary>기존 대출 → 집 매각대금 → 자기자금 계산 근거 보기</summary>' in HTML
    assert '공식 계획 적용은 잠금 상태' in HTML
    assert HTML.index('debt_retirement_v512f.js') < HTML.index('home_bridge_v512g.js')
