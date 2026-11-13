'use strict';
const assert=require('node:assert/strict');
const E=require('../docs/js/v55_savings_engine.js');
const snap=require('../docs/data/v55_monthly_savings_snapshot.json');
const near=(actual,expect,eps=1)=>assert.ok(Math.abs(actual-expect)<eps,`${actual} vs ${expect}`);
const clean=E.simulate(snap);
near(clean.byMonth['2026-11'].expense,3190666.6667,.1);
near(clean.byMonth['2026-12'].expense,3195610.6667,.1);
near(clean.byMonth['2026-12'].available,893142.3333,.1);
const changed=E.simulate(snap,{consumptionDeltas:{'2026-12':-100000}});
near(changed.byMonth['2026-11'].expense,clean.byMonth['2026-11'].expense);
near(changed.byMonth['2026-12'].expense,3095610.6667,.1);
near(changed.byMonth['2026-12'].available,993142.3333,.1);
near(changed.byMonth['2026-12'].required.home,clean.byMonth['2026-12'].required.home);
near(changed.byMonth['2026-12'].required.ret,clean.byMonth['2026-12'].required.ret);
assert.ok(changed.byMonth['2026-12'].allocated.ret>clean.byMonth['2026-12'].allocated.ret);
near(changed.byMonth['2026-12'].assigned,changed.byMonth['2026-12'].needed,.01);
assert.equal(changed.byMonth['2026-12'].consumptionPlanChanged,true);
near(changed.byMonth['2026-12'].expenseParts.general,2304944,.01);
near(changed.byMonth['2026-12'].expenseParts.childcare,379000,.01);
assert.equal(changed.byMonth['2026-11'].consumptionPlanChanged,false);
// Carry a verified 11-month actual 0 even if a future consumption plan changes.
const actuals={'2026-11':{home:0,car:0,travel:0,ret:0}};
const actualBase=E.simulate(snap,{actuals});
const actualChanged=E.simulate(snap,{actuals,consumptionDeltas:{'2026-12':-100000}});
for(const id of ['home','car','travel','ret']){
 assert.equal(actualChanged.byMonth['2026-11'].allocated[id],0,id);
 near(actualChanged.byMonth['2026-12'].required[id],actualBase.byMonth['2026-12'].required[id],.01);
}
near(actualChanged.byMonth['2026-12'].available-actualBase.byMonth['2026-12'].available,100000,.01);
assert.ok(actualChanged.byMonth['2026-12'].allocated.ret>actualBase.byMonth['2026-12'].allocated.ret);
// Customer changes the INITIAL budget in November: November allocations and next month requirements roll together.
const initialChange=E.simulate(snap,{consumptionDeltas:{'2026-11':-100000,'2026-12':-100206}});
near(initialChange.byMonth['2026-11'].available-clean.byMonth['2026-11'].available,100000,.01);
assert.ok(initialChange.byMonth['2026-12'].required.ret<clean.byMonth['2026-12'].required.ret);
// Apply verified CPI to the changed general consumption once, but never to childcare.
const econ={CPI_GENERAL:{ready:true,value:123,lastMonth:'2026-11'}};
const scale=123/120.73;
const econChanged=E.simulate(snap,{asOf:'2026-12',activeMonth:'2026-12',economics:econ,consumptionDeltas:{'2026-12':-100000}});
near(econChanged.byMonth['2026-11'].expense,clean.byMonth['2026-11'].expense,.1);
near(econChanged.byMonth['2026-12'].expenseParts.general,(2404944-100000)*scale,.01);
near(econChanged.byMonth['2026-12'].expenseParts.childcare,379000,.01);
const override=E.simulate(snap,{consumptionDeltas:{'2026-12':-100000},cashOverrides:{'2026-12':{expense:3200000}}});
assert.equal(override.byMonth['2026-12'].expense,3200000);
assert.equal(override.byMonth['2026-12'].expenseOverride,true);
console.log('V61 PASS: 11월 3,190,667원, 12월 소비 -10만원, 실적 유지, 권장액 재배분, CPI 단일 적용, 실제 총지출 우선');
