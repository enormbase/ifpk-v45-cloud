"""V51-3d — benchmark 605-month sensitivity and strict immutability."""
import subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf8')
LEDGER=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert LEDGER
REV=(ROOT/'docs/js/longterm_cash_v513c.js')
assert REV.exists()

def run(js):
 c="const assert=require('node:assert/strict');const s=Object.fromEntries("+LEDGER.group(1)+");const old=JSON.stringify(s);const p=require('./docs/js/longterm_cash_v513c.js');\n"+js
 x=subprocess.run(['node','-e',c],cwd=ROOT,capture_output=True,text=True)
 assert x.returncode==0,x.stderr[-2000:]
 return x.stdout

BASE=r"""
let asOf='2027-05',comp=Array.from({length:6},(_,i)=>{let date=p.shift(asOf,i),r=s[date];return {month:date,plannedNet:r[6]-r[7]-r[8]-r[9]-r[10],testedNet:r[6]-r[7]-r[8]-r[9]-r[10],baselineCash:r[16],testedCash:r[16]}});
let review={ready:true,payload:{asOf,comparison:comp,officialApplied:false}};
"""

def test_policy_ui_and_version():
 for t in ['V51-3d','longterm_cash_v513c.js','장기 일반현금 부족 영향','장기 영향 시험 계산','공식 계획 미적용']:
  assert t in HTML

def test_zero_change_reproduces_authoritative_negative_months():
 run(BASE+"""const q=p.project(s,review,{additionalMonthlyRelief:0,duration:'12'});assert.equal(q.ready,true);assert.equal(q.baseline.negativeMonths,285);assert.equal(q.trial.negativeMonths,285);assert.equal(q.baseline.worst,-32453069);assert.equal(q.trial.worst,-32453069);assert.equal(q.baseline.worstMonth,'2039-10');assert.equal(q.at2039.delta,0);assert.equal(q.examinedMonths,353);assert.equal(q.official,false);assert.equal(JSON.stringify(s),old);""")

def test_six_month_one_time_delta_carries_without_repeat():
 run(BASE+"""for(let i=0;i<comp.length;i++){comp[i].testedNet+=100000;comp[i].testedCash+=100000*(i+1);}const q=p.project(s,review,{additionalMonthlyRelief:0});assert.equal(q.ready,true,JSON.stringify(q));assert.equal(q.sixMonthEngineCarry,600000);assert.equal(q.at2039.delta,600000);assert.equal(q.samples.at(-1).delta,600000);assert.equal(q.officialLedgerUpdated,false);assert.equal(q.postRetirementWithdrawalsRecomputed,false);assert.equal(JSON.stringify(s),old);""")

def test_manual_cut_is_nominal_and_duration_bound():
 run(BASE+"""const q=p.project(s,review,{additionalMonthlyRelief:200000,duration:'12'});assert.equal(q.ready,true);assert.equal(q.manual.total,2400000);assert.equal(q.manual.affectedMonths,12);assert.equal(q.at2039.delta,2400000);assert.equal(q.trial.worst<=0,true);assert.equal(q.manual.nominalFixed,true);assert.equal(q.goalAccountBalancesRecomputed,false);assert.equal(JSON.stringify(s),old);""")

def test_historical_months_immutable():
 run(BASE+"""review.payload.asOf='2039-10';review.payload.comparison=Array.from({length:6},(_,i)=>{const date=p.shift('2039-10',i),r=s[date],v=r[6]-r[7]-r[8]-r[9]-r[10];return {month:date,plannedNet:v,testedNet:v,baselineCash:r[16],testedCash:r[16]}});const q=p.project(s,review,{additionalMonthlyRelief:200000,duration:'retirement'});assert.equal(q.ready,true);assert.equal(q.baseline.worstMonth,'2039-10');assert.equal(q.at2039.delta,200000);assert.equal(q.samples.find(x=>x.month==='2056-03').delta,q.manual.total);assert.equal(JSON.stringify(s),old);""")

def test_rejects_invalid_and_inconsistent_reviews():
 run(BASE+"""assert.equal(p.project(s,review,{additionalMonthlyRelief:-1}).ready,false);assert.equal(p.project(s,review,{additionalMonthlyRelief:2000001}).ready,false);review.payload.comparison[4].testedCash+=999;assert.equal(p.project(s,review,{}).ready,false);assert.equal(JSON.stringify(s),old);""")

def test_old_stale_test_fixed_and_export_integrated():
 source=(ROOT/'tests/test_v511_replan.py').read_text('utf8')
 assert 'assert.equal(sim.baseDeficitCount,66)' not in source
 assert 'longTermCashflowPreview:longTerm' in HTML
 assert 'const longTerm=IFPK_V513C.project' in HTML
