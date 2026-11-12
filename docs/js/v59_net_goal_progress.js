/* V59 patch: show progress only for NEW savings since 2026-11.
 * Original balances remain in the financial engine. This is a display-only
 * attribution ledger, not two separate financial accounts.
 * Deposits are booked after each month's accrual, as in v55_savings_engine.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V59_NET_GOAL=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const idx=d=>{const m=String(d||'').match(/^(\d{4})-(\d{2})$/);return m?Number(m[1])*12+Number(m[2])-1:NaN;};
const monthAt=i=>Math.floor(i/12)+'-'+String(i%12+1).padStart(2,'0');
const positive=n=>Math.max(0,Number(n)||0);
const rateFor=(goal,record)=>{
 if(goal.id==='ret')return Number(goal.monthlyRate)||0;
 const v=Number(record?.economicValues?.DEPOSIT);
 if(record&&record.economicValues&&Number.isFinite(v)&&v>=0&&v<100)return Math.pow(1+v/100,1/12)-1;
 return Number.isFinite(Number(goal.baseMonthlyRate))?Number(goal.baseMonthlyRate):(Number(goal.monthlyRate)||0);
};
function calculate(goal,activeMonth,history={},startMonth='2026-11'){
 const end=idx(goal.deadline),now=idx(activeMonth),start=idx(startMonth);
 if(!Number.isFinite(end)||!Number.isFinite(now)||!Number.isFinite(start))throw Error('유효한 목표월·진행월이 필요합니다');
 let seed=positive(goal.initial),newBalance=0,confirmedMonths=0,confirmedDeposits=0;
 for(let i=start;i<Math.min(now,end);i++){
  const date=monthAt(i),entry=history[date],rate=rateFor(goal,entry);
  // The original capital and later deposits earn the *same* monthly rate.
  seed*=1+rate;newBalance*=1+rate;
  if(entry?.confirmed===true&&Object.prototype.hasOwnProperty.call(entry.actuals||{},goal.id)){
   const cash=Number(entry.actuals[goal.id]);
   if(Number.isFinite(cash)&&cash>=0){newBalance+=cash;confirmedDeposits+=cash;confirmedMonths++;}
  }
 }
 const projectedRate=Number(goal.monthlyRate)||0;
 const futureFactor=Math.pow(1+projectedRate,Math.max(0,end-now));
 const seedAtGoal=seed*futureFactor;
 const newAtGoal=newBalance*futureFactor;
 const total=positive(goal.total);
 const netTarget=Math.max(0,total-seedAtGoal);
 const percent=netTarget>1?Math.max(0,Math.min(100,newAtGoal/netTarget*100)):100;
 return {percent,netTarget,seedAtGoal,newAtGoal,newBalance,seedBalance:seed,confirmedMonths,confirmedDeposits};
}
return {calculate};
});
