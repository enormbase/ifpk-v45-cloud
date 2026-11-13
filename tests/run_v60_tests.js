'use strict';
const assert=require('node:assert/strict');
const E=require('../docs/js/v55_savings_engine.js');
const A=require('../docs/js/v59_economic_adapter.js');
const T=require('../docs/js/v60_indicator_trace.js');
const snap=require('../docs/data/v55_monthly_savings_snapshot.json');
const next=(d,n)=>A.offset(d,n);
const asOf='2026-11';
const status={estimates:[
 {id:'CPI_GENERAL',status:'ready',lastMonth:'2026-11',value:122},
 {id:'CPI_CAR',status:'ready',lastMonth:'2026-11',value:120.1},
 {id:'CPI_TRAVEL',status:'ready',lastMonth:'2026-11',value:128.7},
 {id:'DEPOSIT',status:'ready',lastMonth:'2026-11',value:2.75},
 {id:'MORTGAGE',status:'ready',lastMonth:'2026-11',value:3.95},
 {id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',status:'ready',lastMonth:'2026-11',indexBaseMonth:'2026-06',rates:{'60months':1.2,'120months':0.4}},
]};
const data=A.latest(status,[],asOf);
assert.equal(data.display.length,6);
assert.equal(Object.keys(data.values).length,6);
assert.equal(data.values.HOME_PRICE.value,0.8);
assert.equal(data.values.HOME_PRICE.seriesId,'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606');
const opt={asOf,activeMonth:'2026-11',economics:data.values};
const base=E.simulate(snap),sim=E.simulate(snap,opt);
const trace=T.trace(snap,sim,'2026-12',data);
assert.equal(trace.appliedCount,6);
assert.equal(trace.parts.length,5);
assert.equal(trace.parts.reduce((a,b)=>a+b.value,0),sim.byMonth['2026-12'].expense);
assert.ok(trace.parts.find(x=>x.id==='general').delta>0);
assert.equal(trace.parts.find(x=>x.id==='childcare').delta,0,'Childcare follows stage-based costs and fixed 2.5% inflation, not live CPI');
assert.equal(trace.parts.find(x=>x.id==='insurance').delta,0);
const changes=T.impacts(snap,sim,data,E,{asOf,activeMonth:'2026-11'});
for(const k of ['CPI_GENERAL','CPI_CAR','CPI_TRAVEL','DEPOSIT','MORTGAGE','HOME_PRICE']){
 assert.equal(changes[k].status,'재계산 검증',k);
 assert.ok(Number.isFinite(changes[k].delta),k);
}
assert.ok(changes.CPI_GENERAL.delta>0);
assert.ok(changes.CPI_CAR.delta>0);
assert.ok(changes.CPI_TRAVEL.delta>0);
assert.ok(changes.MORTGAGE.delta>0);
assert.ok(changes.HOME_PRICE.delta>0);
assert.ok(Math.abs(changes.DEPOSIT.delta)>0.001);
const partial=A.latest({estimates:status.estimates.filter(x=>x.id==='CPI_GENERAL')},[],asOf);
assert.equal(partial.display.filter(x=>x.validated).length,1);
assert.equal(partial.display.filter(x=>!x.validated).length,5);
// Do not conflate raw index level with growth or splice different index bases.
const newId='HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',oldId='HOME_PRICE_APT_DAEJEON_SEOGU';
const old=Array.from({length:121},(_,i)=>({id:oldId,date:next('2016-11',i),value:100*Math.pow(1.002,i),unit:'지수'}));
const short=Array.from({length:6},(_,i)=>({id:newId,date:next('2026-06',i),value:100+i*.3,unit:'지수'}));
assert.equal(A.derived('HOME_PRICE',short,'2026-11'),null);
assert.equal(A.derived('HOME_PRICE',old.concat(short),'2026-11').seriesId,oldId);
const full=Array.from({length:121},(_,i)=>({id:newId,date:next('2016-11',i),value:100*Math.pow(1.003,i),unit:'2026-06=100'}));
assert.equal(A.derived('HOME_PRICE',old.concat(full),'2026-11').seriesId,newId);
// Historical rate in baseline reference month can be revised and must be accepted.
const sameMonth=E.simulate(snap,{asOf,activeMonth:'2026-11',economics:{DEPOSIT:{ready:true,lastMonth:'2026-09',value:3.1}}});
assert.ok(sameMonth.byId.home.monthlyRate>base.byId.home.monthlyRate);
// Verified CPI rolls forward while already confirmed month retains original expense.
const historical=E.simulate(snap,{asOf,activeMonth:'2026-12',actuals:{'2026-11':{home:200000,car:0,travel:50000,ret:0}},economics:data.values});
assert.equal(historical.byMonth['2026-11'].expense,base.byMonth['2026-11'].expense);
assert.ok(historical.byMonth['2026-12'].expense>base.byMonth['2026-12'].expense);
assert.equal(historical.byMonth['2026-11'].allocated.home,200000);
const overridden=E.simulate(snap,{...opt,cashOverrides:{'2026-12':{expense:500000}}});
assert.equal(overridden.byMonth['2026-12'].expense,500000);
assert.equal(T.trace(snap,overridden,'2026-12',data).expenseOverride,true);
console.log('V60 PASS: provenance, 6 independent impacts, health fixed, rate same-month, R-ONE rebasing, locked history, cost override');
