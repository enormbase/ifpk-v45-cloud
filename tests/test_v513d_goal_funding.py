"""V51-3e goal-account buffer, monthly extra savings, and immutability tests."""
import subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
H=(ROOT/'docs/index.html').read_text(encoding='utf8')
MATCH=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',H,re.S)
assert MATCH

def node(code):
    js="const assert=require('node:assert/strict');const s=Object.fromEntries("+MATCH.group(1)+");const original=JSON.stringify(s);const p=require('./docs/js/goal_funding_v513d.js');\n"+code
    r=subprocess.run(['node','-e',js],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert r.returncode==0,r.stderr[-2400:]

PREFIX="const rev={ready:true,payload:{asOf:'2027-05',officialApplied:false,comparison:Array(6).fill({})}};\n"

def test_baseline_three_goal_events():
    node("""const a=p.goalBaseline(s);assert.equal(a.ready,true,JSON.stringify(a));assert.deepEqual(Object.keys(a.items).sort(),['car','house','travel']);assert.equal(a.items.car.date,'2034-10');assert.equal(a.items.car.required,20000000);assert.equal(a.items.travel.date,'2038-10');assert.equal(a.items.house.date,'2046-10');for(const k of Object.keys(a.items)){assert.equal(a.items[k].baseGap,0);assert.equal(a.items[k].baselineReady,true);assert.equal(a.items[k].available-a.items[k].required,a.items[k].baseSurplus);}assert.equal(JSON.stringify(s),original);""")

def test_zero_extra_saving_does_not_change_goal():
    node(PREFIX+"""const a=p.project(s,rev,{goal:'car',monthlyChange:'0',duration:'12'});assert.equal(a.ready,true,JSON.stringify(a));assert.equal(a.selected.fvDelta,0);assert.equal(a.selected.trialAvailable,a.selected.available);assert.equal(a.selected.trialGap,0);assert.equal(a.generalCashSensitivity.extraCashBeforeGoals,0);assert.equal(a.official,false);assert.equal(JSON.stringify(s),original);""")

def test_car_savings_reduction_increases_cash_but_creates_goal_gap():
    node(PREFIX+"""const a=p.project(s,rev,{goal:'car',monthlyChange:'-50000',duration:'12'});assert.equal(a.ready,true,JSON.stringify(a));assert.equal(a.selected.appliedMonths,12);assert.equal(a.generalCashSensitivity.extraCashBeforeGoals,600000);assert.ok(a.selected.trialGap>0);assert.ok(a.selected.trialAvailable<a.selected.available);assert.equal(a.generalCashSensitivity.doesNotSettleGoalShortfall,true);assert.equal(JSON.stringify(s),original);""")

def test_monthly_spending_cuts_do_not_enter_goal_account():
    node(PREFIX+"""const a=p.project(s,rev,{goal:'travel',monthlyChange:'0',duration:'goal'});assert.equal(a.ready,true);assert.equal(a.selected.trialAvailable,a.selected.available);assert.equal(a.selected.fvDelta,0);assert.equal(a.otherGoalBalancesChanged,false);assert.equal(a.retirementAssumptionsChanged,false);assert.equal(JSON.stringify(s),original);""")

def test_goal_months_and_reject_past_or_negative_monthly_savings():
    node(PREFIX+"""const a=p.project(s,rev,{goal:'house',monthlyChange:10000,duration:'goal'});assert.equal(a.ready,true);assert.ok(a.selected.appliedMonths>100);assert.equal(a.selected.trialGap,0);const b=p.project(s,rev,{goal:'travel',monthlyChange:-50000,duration:'12'});assert.equal(b.ready,false);rev.payload.asOf='2039-11';const c=p.project(s,rev,{goal:'car',monthlyChange:0,duration:'6'});assert.equal(c.ready,false);assert.equal(JSON.stringify(s),original);""")

def test_modified_event_month_rejects_source_inconsistency():
    node(PREFIX+"""s['2034-10'][14]-=100;const a=p.project(s,rev,{goal:'car'});assert.equal(a.ready,false);""")

def test_html_contains_functional_controls_and_review_json():
    for fragment in ['V51-3e','goal_funding_v513d.js','v513d-goal-audit','data-v513d-recalc','goalFundingPreview:goalImpact','goalImpact=IFPK_V513D.project']:
        assert fragment in H
    assert 'tests/test_v511_replan.py' not in H
