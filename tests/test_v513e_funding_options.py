"""V51-3e combined liquidity and goal-stress scenarios; strict immutability."""
from pathlib import Path
import re, subprocess
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf8')
SNAP=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert SNAP
JS="const assert=require('node:assert/strict');const s=Object.fromEntries("+SNAP.group(1)+");const initial=JSON.stringify(s);const p=require('./docs/js/funding_options_v513e.js');\n"
BASE="""const asOf='2027-05';const comparison=Array.from({length:6},(_,i)=>{const month=p.shift(asOf,i),r=s[month],net=r[6]-r[7]-r[8]-r[9]-r[10];return {month,plannedNet:net,testedNet:net,baselineCash:r[16],testedCash:r[16]};});const review={ready:true,payload:{asOf,comparison,officialApplied:false}};\n"""
def check(code):
 r=subprocess.run(['node','-e',JS+code],cwd=ROOT,capture_output=True,text=True,timeout=20)
 assert r.returncode==0,r.stderr[-1800:]
 return r.stdout.strip()

def test_identity_keeps_baseline_and_goal():
 check(BASE+"""const x=p.evaluate(s,review,{});assert.equal(x.ready,true,JSON.stringify(x));assert.equal(x.goalFunding.available,20069086);assert.equal(x.goalFunding.required,20000000);assert.equal(x.goalFunding.shortfall,0);assert.equal(x.baseline.negativeMonthsAfterAsOf,x.liquidity.negativeMonthsAfterAsOf);assert.equal(x.baseline.worstCashAfterAsOf,x.liquidity.worstCashAfterAsOf);assert.equal(x.liquidity.sixMonthEngineCarry,0);assert.equal(x.liquidity.at2039.trial,-32453069);assert.equal(x.official,false);assert.equal(JSON.stringify(s),initial);""")

def test_goal_decrease_frees_cash_but_creates_funding_shortfall():
 check(BASE+"""const x=p.evaluate(s,review,{goal:'car',monthlyContributionChange:-50000,savingDuration:'12'});assert.equal(x.ready,true,JSON.stringify(x));assert.equal(x.goalFunding.available,19348771);assert.equal(x.goalFunding.shortfall,651229);assert.equal(x.liquidity.nominalContributionDelta,-600000);assert.equal(x.liquidity.manualCashDelta,600000);assert.equal(x.liquidity.at2039.trial,-31853069);assert.equal(x.gates.goalFunded,false);assert.equal(x.gates.noNegativeMonths,false);assert.equal(x.gates.officialReady,false);assert.equal(JSON.stringify(s),initial);""")

def test_target_reduction_fixes_goal_but_not_monthly_cash():
 check(BASE+"""const x=p.evaluate(s,review,{goal:'car',monthlyContributionChange:-50000,savingDuration:'12',goalBudgetReduction:700000});assert.equal(x.ready,true);assert.equal(x.goalFunding.required,19300000);assert.equal(x.goalFunding.shortfall,0);assert.equal(x.gates.goalFunded,true);assert.equal(x.gates.noNegativeMonths,false);assert.equal(x.liquidity.at2039.trial,-31853069);assert.equal(x.goalDeferralComputed,false);assert.equal(JSON.stringify(s),initial);""")

def test_spending_relief_is_separate_from_goal_account():
 check(BASE+"""const x=p.evaluate(s,review,{goal:'travel',monthlyRelief:150000,reliefDuration:'12'});assert.equal(x.ready,true);assert.equal(x.liquidity.reliefTotal,1800000);assert.equal(x.goalFunding.available,6754653);assert.equal(x.goalFunding.shortfall,0);assert.equal(x.liquidity.at2039.trial,-30653069);assert.equal(x.immutableBaseline,true);assert.equal(JSON.stringify(s),initial);""")

def test_consistent_six_month_engine_deltas_carried_once():
 check(BASE+"""comparison.forEach((r,i)=>{r.testedNet-=42894;r.testedCash-=42894*(i+1);});const x=p.evaluate(s,review,{goal:'car',monthlyContributionChange:-50000,savingDuration:'12',monthlyRelief:150000,reliefDuration:'12'});assert.equal(x.ready,true,JSON.stringify(x));assert.equal(x.liquidity.sixMonthEngineCarry,-257364);assert.equal(x.liquidity.reliefTotal,1800000);assert.equal(x.liquidity.nominalContributionDelta,-600000);assert.equal(x.liquidity.at2039.trial,-30310433);assert.equal(JSON.stringify(s),initial);""")

def test_negative_amount_rejected_if_savings_less_than_zero():
 check(BASE+"""assert.equal(p.evaluate(s,review,{goal:'travel',monthlyContributionChange:-50000}).ready,false);assert.equal(p.evaluate(s,review,{goal:'car',monthlyContributionChange:'-2000001'}).ready,false);assert.equal(p.evaluate(s,review,{goal:'car',monthlyRelief:-1}).ready,false);assert.equal(p.evaluate(s,review,{goal:'car',goalBudgetReduction:20000001}).ready,false);assert.equal(p.evaluate(s,review,{goal:'car',savingDuration:'wrong'}).ready,false);assert.equal(JSON.stringify(s),initial);""")

def test_goal_end_and_pre_replan_months_not_mutated():
 check(BASE+"""const x=p.evaluate(s,review,{goal:'house',monthlyRelief:200000,reliefDuration:'retirement',monthlyContributionChange:20000,savingDuration:'goal'});assert.equal(x.ready,true);assert.equal(x.goalDate,'2046-10');assert.equal(x.liquidity.reliefTotal,200000*p.distance('2027-05','2056-04'));assert.ok(x.goalFunding.available>x.baseline.available);assert.equal(JSON.stringify(s),initial);""")

def test_review_flags_and_invariant_boundaries():
 check(BASE+"""review.payload.officialApplied=true;assert.equal(p.evaluate(s,review,{}).ready,false);review.payload.officialApplied=false;comparison[1].testedCash+=123;assert.equal(p.evaluate(s,review,{}).ready,false);assert.equal(JSON.stringify(s),initial);""")

def test_ui_and_review_export():
 for x in ['V51-3e','funding_options_v513e.js','v513e-options','data-v513e-recalc','fundingOptionsPreview:optionsImpact','optionsImpact=IFPK_V513E.evaluate','goalFundingPreview:goalImpact','검토 기록 JSON 내보내기']:
  assert x in HTML,x
