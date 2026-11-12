'use strict';
const assert=require('assert');
const A=require('../docs/js/v59_economic_adapter.js');
const E=require('../docs/js/v55_savings_engine.js');
const snap=require('../docs/data/v55_monthly_savings_snapshot.json');
const ago=(base,n)=>A.offset(base,n);
const close=(a,b,tol=1e-6)=>assert.ok(Math.abs(a-b)<=tol,`${a} ≠ ${b}`);
const rows=[];
for(let i=0;i<125;i++){
 const d=ago('2016-07',i);
 for(const [id,base,k] of [ ['CPI_GENERAL',100,0.15], ['CPI_CAR',110,.12], ['CPI_TRAVEL',95,.21], ['DEPOSIT',2.1,.003], ['MORTGAGE',3.2,.002], ['HOME_PRICE_APT_DAEJEON_SEOGU',100,.3] ])rows.push({id,date:d,value:base+k*i});
}
const end=ago('2016-07',124);
// Given a verified computed estimate one month behind a newly available complete raw series, use newest observed month.
const statuses={estimates:[{id:'CPI_GENERAL',status:'ready',value:122,lastMonth:ago(end,-1)},{id:'CPI_CAR',status:'ready',value:122,lastMonth:end},{id:'MORTGAGE',status:'failed',value:50,lastMonth:end}]};
const latest=A.latest(statuses,rows,end);
assert.strictEqual(latest.display.length,6);
assert.ok(latest.display.every(v=>v.month===end),`vintages differ: ${JSON.stringify(latest.display)}`);
assert.ok(Object.keys(latest.values).length===6);
assert.ok(latest.values.CPI_GENERAL.value>100);
close(latest.values.CPI_CAR.value,122); // verified published estimate wins if its month matches raw
const travel=rows.filter(r=>r.id==='CPI_TRAVEL').slice(-12).reduce((a,b)=>a+b.value,0)/12;
close(latest.values.CPI_TRAVEL.value,travel);
assert.ok(latest.values.DEPOSIT.value>0&&latest.values.DEPOSIT.value<30);
assert.ok(latest.values.MORTGAGE.value>0&&latest.values.MORTGAGE.value<30);
assert.ok(latest.values.HOME_PRICE.value>=-20&&latest.values.HOME_PRICE.value<20);
const gaps=rows.filter(r=>!(r.id==='CPI_TRAVEL'&&r.date===ago(end,-5)));
const broken=A.latest({},gaps,end);
assert.ok(!('CPI_TRAVEL' in broken.values), 'Incomplete MA12 may not be accepted as verified');
assert.ok(broken.display.find(x=>x.id==='CPI_TRAVEL').source.includes('최초 설계'));
const fallback=A.latest({estimates:[{id:'CPI_GENERAL',status:'failed',value:99,lastMonth:end}]},[],end);
assert.deepStrictEqual(fallback.values,{});
assert.strictEqual(fallback.display.find(x=>x.id==='CPI_GENERAL').month,'2026-10');
// Because these fabricated raw dates precede the 2026 baseline, they are correctly not adopted.
const currentMonths=rows.map(x=>({...x,date:ago(x.date,124)}));
const currentEnd=ago(end,124);
const updated=A.latest({},currentMonths,currentEnd);
assert.ok(Object.keys(updated.values).length===6);
const stale=A.latest({},currentMonths,ago(currentEnd,-1));
assert.ok(stale.display.some(x=>x.month===ago(currentEnd,-1)||x.month==='2026-09'||x.month==='2026-10'));
const s=E.simulate(snap);
const sample=(id,value)=>({[id]:{ready:true,value,lastMonth:'2026-11'}});
const sim=(id,value)=>E.simulate(snap,{asOf:'2026-11',activeMonth:'2026-11',economics:sample(id,value)});
const common=sim('CPI_GENERAL',125);
assert.ok(common.byMonth['2026-11'].available<s.byMonth['2026-11'].available, 'CPI general must raise current expenses');
assert.ok(common.retirement.projection[0].needed>s.retirement.projection[0].needed, 'CPI general must reach retirement spending');
assert.ok(sim('CPI_TRAVEL',129).byId.travel.total>s.byId.travel.total);
assert.ok(sim('CPI_CAR',120).byMonth['2035-01'].expense>s.byMonth['2035-01'].expense);
assert.ok(sim('DEPOSIT',3.1).byId.home.monthlyRate>s.byId.home.monthlyRate);
assert.ok(sim('MORTGAGE',4.5).byMonth['2047-01'].expense>s.byMonth['2047-01'].expense);
assert.ok(sim('MORTGAGE',4.5).retirement.projection[0].needed>s.retirement.projection[0].needed);
assert.ok(sim('HOME_PRICE',0.5).byId.home.total>s.byId.home.total);
// Confirmed month expense must not be retroactively re-inflated after the active month moves.
const hist=E.simulate(snap,{activeMonth:'2026-12',asOf:'2026-11',economics:sample('CPI_GENERAL',125),actuals:{'2026-11':{home:450000,car:200000,travel:0,ret:100000}}});
assert.strictEqual(hist.byMonth['2026-11'].expense,s.byMonth['2026-11'].expense);
assert.ok(hist.byMonth['2026-12'].expense>s.byMonth['2026-12'].expense);
assert.strictEqual(hist.byMonth['2026-11'].allocated.ret,100000);
assert.ok(hist.byMonth['2026-12'].required.ret>s.byMonth['2026-12'].required.ret);
console.log('V59 PASS: 6 latest-source rollovers, stale fallback, continuous histories, effect on spending/loan/goals/retirement, confirmed past lock');
