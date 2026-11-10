"""V51-2f mortgage/retirement sensitivity: approved snapshot must remain unchanged."""
from pathlib import Path
import re,subprocess,json
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
JS=(ROOT/'docs/js/debt_retirement_v512f.js')

def execute(code):
    found=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
    assert found,'full monthly frozen snapshot missing'
    setup=f'''
const assert=require('node:assert/strict');
const snapshot=Object.fromEntries({found.group(1)});
const untouched=JSON.stringify(snapshot);
const fin=require({json.dumps(str(ROOT/'docs/js/rolling_projection_v512b.js'))});
const af=require({json.dumps(str(ROOT/'docs/js/affordability_v512d.js'))});
const f=require({json.dumps(str(JS))});
const preview=fin.compute(snapshot,[],{{asOf:'2027-05'}});
assert.equal(preview.ready,true);
'''
    p=subprocess.run(['node','-e',setup+code],capture_output=True,text=True,cwd=ROOT)
    assert p.returncode==0,p.stderr[-6000:]
    return p.stdout.strip()

def test_source_mortgage_exactly_matches_sheet_baseline():
    execute('''const m=f.baselineSchedule();
assert.ok(Math.abs(m['2027-05'].begin-257751960)<1);
assert.ok(Math.abs(m['2027-05'].payment-972344)<1);
assert.ok(Math.abs(m['2046-09'].end-104117759)<1);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_same_balance_means_zero_sensitivity_and_stable_old_schedule():
    execute('''const base=f.baselineSchedule();
const r=f.project(snapshot,preview,{mortgageOutstanding:String(Math.round(base['2027-05'].begin))},'2026-11');
assert.equal(r.ready,true);assert.equal(r.mortgage.projected,true);
assert.ok(Math.abs(r.mortgage.saleBalanceDelta)<2);
assert.ok(Math.abs(r.mortgage.monthlyDelta['2027-05'])<1);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_new_balance_changes_mortgage_payment_and_sale_balance_only_forward():
    execute('''const r=f.project(snapshot,preview,{mortgageOutstanding:'250000000'},'2026-11');
assert.equal(r.ready,true);assert.equal(r.future,true);
assert.equal(r.mortgage.firstPayment,943100);
assert.ok(r.mortgage.saleBalance<r.mortgage.oldSaleBalance);
assert.equal(r.mortgage.monthlyDelta['2027-04'],undefined);
assert.equal(r.mortgage.pastUntouched,true);
assert.equal(r.mortgage.mortgageAppliedToLtvDsr,false);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_six_month_affordability_changes_only_when_mortgage_entered():
    execute('''const base=af.analyze(snapshot,preview,{});
const r=f.project(snapshot,preview,{mortgageOutstanding:250000000},'2026-11');
const changed=af.analyze(snapshot,preview,{mortgageMonthlyAdjustment:r.mortgage.monthlyDelta});
assert.equal(base.ready,true);assert.equal(changed.ready,true);
assert.ok(changed.months[0].afterObligations>base.months[0].afterObligations);
assert.equal(changed.months[0].mortgagePaymentDifference,-29244);
assert.equal(changed.months[0].month,'2027-05');
assert.equal(base.months[0].mortgagePaymentDifference,0);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_retirement_fv_is_separate_from_dc_or_official_total():
    execute('''const r=f.project(snapshot,preview,{retirementAssets:30000000},'2026-11');
assert.equal(r.ready,true);assert.equal(r.retirement.projected,true);
assert.equal(r.retirement.assumedReturnPct,5.3);
assert.ok(r.retirement.startingFV>30000000);
assert.ok(r.retirement.futureContributionsFV>r.retirement.futureContributionsNominal);
assert.equal(r.retirement.notDCVerified,true);
assert.equal(r.retirement.notAppliedToOfficialRetirement,true);
assert.equal(r.mortgage.projected,false);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_zero_and_invalid_amounts_and_after_move_scenarios():
    execute('''let r=f.project(snapshot,preview,{mortgageOutstanding:0,retirementAssets:0},'2026-11');
assert.equal(r.ready,true);assert.equal(r.mortgage.saleBalance,0);
assert.equal(r.retirement.startingFV,0);
for(const bad of [{mortgageOutstanding:-1},{retirementAssets:'notMoney'},{mortgageOutstanding:1.5},{retirementAssets:2e12}]){
 assert.equal(f.project(snapshot,preview,bad,'2026-11').ready,false);
}
const later=fin.compute(snapshot,[],{asOf:'2046-11'});
assert.equal(later.ready,true);
r=f.project(snapshot,later,{mortgageOutstanding:30000000},'2026-11');
assert.equal(r.ready,true);assert.equal(r.mortgage.projected,false);
assert.equal(r.mortgage.eligible,false);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_inputs_blank_not_promoted_to_verified_assets():
    execute('''const r=f.project(snapshot,preview,{},'2026-11');
assert.equal(r.ready,true);
assert.equal(r.mortgage.projected,false);
assert.equal(r.retirement.projected,false);
assert.equal(r.mayApprove,false);
assert.equal(r.previewOnly,true);
assert.equal(JSON.stringify(snapshot),untouched);''')

def test_web_wiring_collapsed_details_and_approval_remains_locked():
    assert 'debt_retirement_v512f.js' in HTML
    assert HTML.index('reconciliation_v512e.js')<HTML.index('debt_retirement_v512f.js')
    assert '⑨ 기존 대출과 은퇴자산, 앞으로 어떻게 될까요?' in HTML
    assert '<summary>주담대 상환과 은퇴자산 예상 계산 자세히 보기</summary>' in HTML
    assert 'mortgageMonthlyAdjustment' in HTML
    assert 'V51-2j.1 · 은퇴 전 롤링 검토 · 공식 계획 미변경' in HTML
    assert '공식 계획 적용은 잠금 상태' in HTML
