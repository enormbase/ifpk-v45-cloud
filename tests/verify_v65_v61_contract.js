'use strict';
// Preserve the formerly deployed V61 consumption-to-savings contract.
const assert=require('node:assert/strict');
const E=require('../docs/js/v55_savings_engine.js');
const snap=require('../docs/data/v55_monthly_savings_snapshot.json');
const near=(a,b,eps=1)=>assert.ok(Math.abs(a-b)<eps,`${a} vs ${b}`);
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

const actuals={'2026-11':{home:0,car:0,travel:0,ret:0}};
const actualBase=E.simulate(snap,{actuals});
const actualChanged=E.simulate(snap,{actuals,consumptionDeltas:{'2026-12':-100000}});
for(const id of ['home','car','travel','ret']){
 assert.equal(actualChanged.byMonth['2026-11'].allocated[id],0,id);
 near(actualChanged.byMonth['2026-12'].required[id],actualBase.byMonth['2026-12'].required[id],.01);
}
near(actualChanged.byMonth['2026-12'].available-actualBase.byMonth['2026-12'].available,100000,.01);
assert.ok(actualChanged.byMonth['2026-12'].allocated.ret>actualBase.byMonth['2026-12'].allocated.ret);

const initialChange=E.simulate(snap,{consumptionDeltas:{'2026-11':-100000,'2026-12':-100206}});
near(initialChange.byMonth['2026-11'].available-clean.byMonth['2026-11'].available,100000,.01);
assert.ok(initialChange.byMonth['2026-12'].required.ret<clean.byMonth['2026-12'].required.ret);

const scale=123/120.73;
const econChanged=E.simulate(snap,{asOf:'2026-12',activeMonth:'2026-12',
 economics:{CPI_GENERAL:{ready:true,value:123,lastMonth:'2026-11'}},
 consumptionDeltas:{'2026-12':-100000}});
near(econChanged.byMonth['2026-11'].expense,clean.byMonth['2026-11'].expense,.1);
near(econChanged.byMonth['2026-12'].expenseParts.general,(2404944-100000)*scale,.01);
near(econChanged.byMonth['2026-12'].expenseParts.childcare,379000,.01);

const override=E.simulate(snap,{consumptionDeltas:{'2026-12':-100000},cashOverrides:{'2026-12':{expense:3200000}}});
assert.equal(override.byMonth['2026-12'].expense,3200000);
assert.equal(override.byMonth['2026-12'].expenseOverride,true);
console.log('V61/V65 PASS: historic actuals, next-month inverse savings, one-time CPI, explicit override');
