'use strict';
const assert=require('assert');
const fs=require('fs');
const path=require('path');
const vm=require('vm');
const engine=require('../docs/js/v55_savings_engine.js');
const snapshot=require('../docs/data/v55_monthly_savings_snapshot.json');

const baseline=engine.simulate(snapshot,{activeMonth:'2027-01'});
const before=baseline.byMonth['2026-12'];
const january=baseline.byMonth['2027-01'];
const february=baseline.byMonth['2027-02'];
assert(january.available<before.available,'2027-01 must reflect the mortgage principal repayment start');

// A customer cuts January general spending by 100,000 won and keeps that plan
// into February with a small CPI rollover. Earlier periods must not change.
const revised=engine.simulate(snapshot,{
 activeMonth:'2027-01',
 consumptionDeltas:{'2027-01':-100000,'2027-02':-100200}
});
const round=n=>Math.round(n);
assert.strictEqual(round(revised.byMonth['2026-11'].expense),round(baseline.byMonth['2026-11'].expense));
assert.strictEqual(round(revised.byMonth['2026-12'].available),round(before.available));
assert.strictEqual(round(revised.byMonth['2027-01'].expense),round(january.expense)-100000);
assert.strictEqual(round(revised.byMonth['2027-01'].available),round(january.available)+100000);
assert.strictEqual(round(revised.byMonth['2027-02'].expense),round(february.expense)-100200);
assert.strictEqual(round(revised.byMonth['2027-02'].available),round(february.available)+100200);
assert.strictEqual(round(revised.byMonth['2027-01'].expenseParts.general),round(january.expenseParts.general)-100000);
assert.strictEqual(round(revised.byMonth['2027-01'].expenseParts.mortgage),round(january.expenseParts.mortgage));
assert.strictEqual(round(revised.byMonth['2027-01'].assigned),round(january.assigned)+100000);
assert(revised.byMonth['2027-02'].needed<february.needed,'later required goal savings must recalculate');

// Customer-verified actual expense of the month overrides its planning estimate.
const actual=engine.simulate(snapshot,{
 consumptionDeltas:{'2027-01':-100000},
 cashOverrides:{'2027-01':{expense:4000000}}
});
assert.strictEqual(actual.byMonth['2027-01'].expense,4000000);

const src=fs.readFileSync(path.resolve(__dirname,'../docs/index.html'),'utf8');
for(const token of [
 'data-v65-spend-from',
 'id="cp-monthly-spending"',
 '${v65CustomerMonthEditor()}',
 'v55State(plan).byMonth[start]',
 'function v55ConsumptionDeltas()',
 'const d=monthSpendChange(date);',
 'consumptionDeltas:v55ConsumptionDeltas()',
 'function v55ConsumptionDeltasFor(events)',
 'v65LastSavedMonth=spendDraftStart',
 'data-v65-review-flow',
 '소비를 바꾸지 않고 실제 납입액을 기록해 다음 달로 넘어가도 됩니다',
])assert(src.includes(token),`missing V65 connection: ${token}`);
assert(src.includes('rec&&diff>1?`<aside class="v65-shortfall-guide"'),'shortfall prompt must be conditional');
assert(!src.includes('class="hero-cash-jump"><button'),'legacy cash alert must not conflict with the new prompt');
// The browser adapter must compute a separate draft without replacing the
// cached saved events. Saving then invalidates the cache in the web handler.
const functionSrc=src.slice(src.indexOf('function v55ConsumptionDeltas('),src.indexOf('function cashDeltaMap('));
const savedEvents=[{date:'2027-01',amounts:{food:500000}}];
const draftEvents=[{date:'2027-01',amounts:{food:400000}}];
const context={
 spendEvents:()=>savedEvents,
 v55ConsumptionCache:null,
 IFPK_V55_DATA:{incomeExpenseMonths:[['2026-12'],['2027-01'],['2027-02']]},
 monthSpendChange:(date,events=savedEvents)=>date<'2027-01'?0:events===savedEvents?-100000:-200000
};
vm.createContext(context);
vm.runInContext(functionSrc,context);
assert.strictEqual(context.v55ConsumptionDeltas()['2027-01'],-100000);
assert.strictEqual(context.v55ConsumptionDeltasFor(draftEvents)['2027-01'],-200000);
assert.strictEqual(context.v55ConsumptionDeltas()['2027-02'],-100000);
assert.strictEqual(context.v55ConsumptionCache['2027-01'],-100000);
console.log('V65 PASS: exact-month expenses, forward-only savings rollover, untouched past and mortgage, verified expense override, conditional customer CTA');
