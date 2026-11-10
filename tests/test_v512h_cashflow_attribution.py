"""V51-2k: old mortgage payments across all pre-sale months and clear attribution."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
SNAP=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert SNAP

def node(code):
 pre=f'''const assert=require('node:assert/strict');
const snapshot=Object.fromEntries({SNAP.group(1)});
const frozen=JSON.stringify(snapshot);
const f=require({json.dumps(str(ROOT/'docs/js/rolling_projection_v512b.js'))});
const g=require({json.dumps(str(ROOT/'docs/js/home_bridge_v512g.js'))});
const h=require({json.dumps(str(ROOT/'docs/js/cashflow_audit_v512h.js'))});
const base=require({json.dumps(str(ROOT/'docs/js/rolling_preview_v512a.js'))});
'''
 p=subprocess.run(['node','-e',pre+code],capture_output=True,text=True,cwd=ROOT)
 assert p.returncode==0,p.stderr[-6000:]
 return p.stdout.strip()

def test_consumer_page_version_and_script_dependency():
 assert 'LIFE PLAN STUDIO · IFPK V51-3f' in HTML
 assert 'V51-2g ·' not in HTML
 assert '⑪ 주택 준비금이 바뀐 이유와 장기 현금흐름' in HTML
 assert HTML.index('home_bridge_v512g.js')<HTML.index('cashflow_audit_v512h.js')
 assert '경제지표·다른 시험조건에 따른 자기자금 변화' in HTML
 assert '기존 대출상환까지 반영 후' in HTML
 assert 'fullAudit.ready?fullAudit.previewCashAtReview' in HTML
 assert 'fullAudit.preRetirementNegativeMonths' in HTML

def test_original_605_unchanged_and_monthly_payment_2027():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:250000000});
const r=h.audit(snapshot,b);
assert.equal(b.applied,true);assert.equal(r.ready,true);
assert.equal(r.sourceMonths,605);assert.equal(r.mortgageApplied,true);
assert.equal(r.mortgageAppliedMonths,233); // May 2027 to Sep 2046 inclusive
assert.equal(r.safeguards.pastUnchanged,true);
assert.equal(r.safeguards.pastUntouched,undefined);
assert.equal(r.safeguards.officialLedgerRebuilt,false);
assert.equal(Math.round(r.mortgageFirstPaymentDelta),-29244, 'rounded first-month difference');
assert.equal(r.monthlyResults['2027-04'].integratedCash,b.preview.monthlyResults['2027-04'].previewCash);
assert.ok(r.monthlyResults['2027-05'].integratedCash>b.preview.monthlyResults['2027-05'].previewCash);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_economic_vs_loan_attribution_adds_up():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:250000000});
const r=h.audit(snapshot,b);assert.equal(r.ready,true);
const x=r.fundingAttribution;
assert.equal(x.initialRequiredEquity,141486810);
assert.equal(x.mortgageBalanceEffect,-3131370);
assert.equal(x.finalRequiredEquity,138355440);
assert.equal(x.otherConditionsRequiredEquity,141486810);
assert.equal(x.otherConditionsEffect,0);
assert.equal(x.otherConditionsEffect+x.mortgageBalanceEffect,x.totalEffect);
assert.equal(x.mortgageInputEffectIsolated,true);
assert.equal(r.mortgageAppliedMonths,233);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_rate_scenario_decomposition_not_identical_to_mortgage_change():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05',scenarios:{borrowingCase:'base',mortgageRate:4.2}},{mortgageOutstanding:250000000});
const r=h.audit(snapshot,b);
assert.equal(r.ready,true);assert.equal(b.applied,true);
const a=r.fundingAttribution;
assert.ok(Math.abs(a.otherConditionsEffect)>1000000);
assert.equal(a.mortgageBalanceEffect,-3131370);
assert.equal(a.totalEffect,a.otherConditionsEffect+a.mortgageBalanceEffect);
assert.equal(r.monthlyResults['2027-04'].integratedCash,r.monthlyResults['2027-04'].baselineCash);
''')

def test_sale_payment_not_applied_twice():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:250000000});const r=h.audit(snapshot,b);
assert.equal(r.ready,true);
assert.ok(Math.abs(r.monthlyResults['2046-09'].mortgagePaymentDelta)>0);
assert.equal(r.monthlyResults['2046-10'].mortgagePaymentDelta,0);
assert.equal(r.monthlyResults['2046-11'].mortgagePaymentDelta,0);
assert.equal(r.monthlyResults['2056-03'].mortgagePaymentDelta,0);
assert.equal(r.monthlyResults['2046-09'].mortgageCumulativeDelta,r.monthlyResults['2046-10'].mortgageCumulativeDelta);
assert.equal(r.safeguards.noDoubleCountAtSale,true);
assert.ok(Math.abs(r.totalCashDeltaFromPayment)>1000000);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_without_loan_input_preserves_original_preview():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05'},{});const r=h.audit(snapshot,b);
assert.equal(r.ready,true);assert.equal(r.mortgageApplied,false);
assert.equal(r.mortgageAppliedMonths,0);assert.equal(r.totalCashDeltaFromPayment,0);
assert.equal(r.monthlyResults['2027-05'].integratedCash,b.preview.monthlyResults['2027-05'].previewCash);
assert.equal(JSON.stringify(snapshot),frozen);
''')

def test_manual_house_goal_still_applies_mortgage_monthly_not_sale_equity_override():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05',houseGoal:150000000},{mortgageOutstanding:250000000});
const r=h.audit(snapshot,b);assert.equal(r.ready,true);
assert.equal(b.applied,false);
assert.equal(r.fundingAttribution.mortgageInputEffectIsolated,false);
assert.equal(r.fundingAttribution.mortgageBalanceEffect,0);
assert.equal(r.mortgageApplied,true);
assert.equal(r.safeguards.noDoubleCountAtSale,true);
''')

def test_retirement_after_date_remains_unverified():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05',hypotheticalCPI:124},{mortgageOutstanding:250000000});const r=h.audit(snapshot,b);
assert.equal(r.ready,true);
assert.equal(r.monthlyResults['2056-03'].preRetirement,true);
assert.equal(r.monthlyResults['2056-04'].preRetirement,false);
assert.equal(r.monthlyResults['2056-04'].integratedCash,null);
assert.equal(r.monthlyResults['2077-03'].integratedCash,null);
assert.equal(r.safeguards.retirementRecomputed,false);
assert.equal(r.safeguards.customerEvidenceVerified,false);
''')

def test_zero_balance_no_fake_after_sale_payment():
 node('''const b=g.link(snapshot,[],{asOf:'2027-05'},{mortgageOutstanding:0});const r=h.audit(snapshot,b);
assert.equal(r.ready,true);assert.equal(r.mortgageApplied,true);
assert.equal(r.fundingAttribution.mortgageBalanceEffect,-104117759);
assert.equal(r.monthlyResults['2046-10'].mortgagePaymentDelta,0);
assert.equal(r.safeguards.customerMortgagePrincipalFundingSourceUnverified,true);
''')
