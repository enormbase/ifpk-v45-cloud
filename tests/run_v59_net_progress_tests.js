'use strict';
const assert=require('assert');
const P=require('../docs/js/v59_net_goal_progress.js');
const E=require('../docs/js/v55_savings_engine.js');
const snapshot=require('../docs/data/v55_monthly_savings_snapshot.json');
const base=E.simulate(snapshot,{activeMonth:'2026-11',asOf:'2026-11'});
const near=(a,b,tol=1)=>assert.ok(Math.abs(a-b)<=tol,`${a} != ${b}`);
for(const g of base.goals){
 const p=P.calculate(g,'2026-11',{});
 near(p.percent,0);
 near(p.newAtGoal,0);
 near(p.netTarget,Math.max(0,g.total-g.initial*Math.pow(1+g.monthlyRate,E.months('2026-11',g.deadline))));
}
const m11={home:500000,car:100000,travel:0,ret:400000};
const h={'2026-11':{confirmed:true,actuals:m11,economicValues:{DEPOSIT:2.6289}}};
const sim=E.simulate(snapshot,{activeMonth:'2026-12',asOf:'2026-11',actuals:{'2026-11':m11},historyEconomics:{'2026-11':{DEPOSIT:2.6289}}});
for(const g of sim.goals){
 const p=P.calculate(g,'2026-12',h);
 near(p.confirmedDeposits,m11[g.id]);
 near(p.seedBalance+p.newBalance,sim.byMonth['2026-11'].balances[g.id],2);
 near(p.newBalance,m11[g.id]);
 near(p.newAtGoal,m11[g.id]*Math.pow(1+g.monthlyRate,E.months('2026-12',g.deadline)));
}
near(P.calculate(sim.byId.travel,'2026-12',h).percent,0);
assert.ok(P.calculate(sim.byId.home,'2026-12',h).percent>0);
const h2={...h,'2026-12':{confirmed:true,actuals:{home:0,car:100000,travel:25000,ret:0},economicValues:{DEPOSIT:3.1}}};
const sim2=E.simulate(snapshot,{activeMonth:'2027-01',asOf:'2026-11',actuals:{'2026-11':m11,'2026-12':h2['2026-12'].actuals},historyEconomics:{'2026-11':h['2026-11'].economicValues,'2026-12':h2['2026-12'].economicValues},economics:{DEPOSIT:{ready:true,lastMonth:'2026-12',value:3.1}}});
for(const g of sim2.goals){
 const p=P.calculate(g,'2027-01',h2);
 near(p.seedBalance+p.newBalance,sim2.byMonth['2026-12'].balances[g.id],2);
}
assert.ok(P.calculate(sim2.byId.travel,'2027-01',h2).percent>0);
const old=P.calculate(sim2.byId.home,'2027-01',h2);
const changed=P.calculate(sim2.byId.home,'2027-01',{'2026-11':{...h['2026-11'],actuals:{...m11,home:300000}},'2026-12':h2['2026-12']});
assert.ok(changed.percent<old.percent);
// Forecast allocations without an explicitly confirmed month must never create fake new savings.
const ghost=P.calculate(sim2.byId.home,'2027-01',{});
near(ghost.newBalance,0);
assert.strictEqual(ghost.confirmedMonths,0);
console.log('V59 NET PROGRESS PASS: 4 original 0% goals, month-close accounting, 0-yen, changing rates, history rewind, no fake projected deposits');
