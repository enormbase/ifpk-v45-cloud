/* IFPK V55 · unified four-goal allocation and monthly rolling preview.
 * Pure engine: actual records are user-entered, not certified bank transaction data.
 * The officially approved V52/V54 model remains distinct until verified approval.
 */
(function(root){'use strict';
const own=(x,k)=>Object.prototype.hasOwnProperty.call(x||{},k);
const finite=(x)=>typeof x==='number'&&Number.isFinite(x);
const money=(x)=>Math.round(Number(x)||0);
function periodIndex(d){const t=String(d||'').match(/^(\d{4})-(\d{2})$/);return t?Number(t[1])*12+Number(t[2])-1:NaN;}
function offset(d,n){const k=periodIndex(d)+n;return Math.floor(k/12)+'-'+String(k%12+1).padStart(2,'0');}
function months(d,end){return periodIndex(end)-periodIndex(d);}
function pmt(principal,annual,term){const r=annual/12;return r===0?principal/term:principal*r/(1-Math.pow(1+r,-term));}
function newGoalMoney(total,initial,rate,n){return Math.max(0,total-initial*Math.pow(1+rate,n));}
function requirement(goal,balance,date,annualPattern){
 const n=months(date,goal.deadline);if(n<=0)return 0;
 const rate=goal.monthlyRate, q=goal.method==='increase'?Math.pow(1+annualPattern,1/12):goal.method==='decrease'?Math.pow(1+annualPattern,-1/12):1;
 const need=newGoalMoney(goal.total,balance,rate,n);
 let den=0;for(let k=0;k<n;k++)den+=Math.pow(q,k)*Math.pow(1+rate,n-1-k);
 return den>0?need/den:0;
}
const BASELINE_ECON={CPI_GENERAL:120.73,CPI_CAR:115.83,CPI_TRAVEL:125.4608,DEPOSIT:2.6289,MORTGAGE:3.70845,HOME_PRICE:-0.233};
function economics(snapshot,options){
 const e=options.economics||{},asOf=options.asOf||snapshot.asOf||'2026-11';
 const values={},changes=[];
 for(const [id,base] of Object.entries(BASELINE_ECON)){
  const z=e[id];const x=Number(z?.value);
  const ref=String(z?.lastMonth||'');
  const baselineMonth=(id==='CPI_GENERAL')?'2026-10':'2026-09';
  if(z&&z.ready===true&&Number.isFinite(x)&&ref>=baselineMonth&&ref<=asOf){values[id]=x;if(Math.abs(x-base)>1e-8)changes.push({id,value:x,ref,base});}
  else values[id]=base;
 }
 return {values,changes,asOf};
}
function simulate(snapshot,options={}){
 if(!snapshot||!Array.isArray(snapshot.goals)||!Array.isArray(snapshot.incomeExpenseMonths))throw Error('V55 시트 입력 스냅샷 없음');
 const econ=economics(snapshot,options),e=econ.values,actuals=options.actuals||{},cashOverrides=options.cashOverrides||{},consumptionDeltas=options.consumptionDeltas||{},priority=options.priority||{},methods=options.methods||{};
 const goals=snapshot.goals.map(g=>({...g,priority:Number(priority[g.id]||g.priority),method:methods[g.id]||g.method,balance:Number(g.initial||0),originalTotal:Number(g.total||0)}));
 if(new Set(goals.map(g=>g.priority)).size!==goals.length || goals.some(g=>g.priority<1||g.priority>4))throw Error('우선순위는 1~4에서 중복 없이 지정해야 합니다');
 for(const g of goals){
  if(!['increase','flat','decrease'].includes(g.method))throw Error('지원하지 않는 저축방식');
  g.baseMonthlyRate=g.monthlyRate;
  if(g.id!=='ret'&&e.DEPOSIT!==BASELINE_ECON.DEPOSIT)g.monthlyRate=Math.pow(1+e.DEPOSIT/100,1/12)-1;
  if(g.id==='travel')g.total=g.originalTotal*e.CPI_TRAVEL/BASELINE_ECON.CPI_TRAVEL;
  if(g.id==='home'){
   // Constant-loan-size scenario for sensitivity; housing regulation and loan capacity need separate approval.
   const n=239/12;
   const orig=Math.pow(1+BASELINE_ECON.HOME_PRICE/100,n),next=Math.pow(1+e.HOME_PRICE/100,n);
   g.total=Math.max(0,g.originalTotal+(800000000-380000000)*(next-orig));
  }
  g.initialNewGoal=newGoalMoney(g.total,g.initial,g.monthlyRate,months(snapshot.asOf,g.deadline));
 }
 const sorted=[...goals].sort((a,b)=>a.priority-b.priority),byId=Object.fromEntries(goals.map(g=>[g.id,g]));
 const monthsOut=[],monthlyByKey={},actualCount={ret:0,home:0,car:0,travel:0},snapshotNow=options.asOf||snapshot.asOf,book={};
 const activeMonth=options.activeMonth||snapshot.asOf, historyEconomics=options.historyEconomics||{};
 let cumulativeFree=0,overbooked=0;
 const carDeltaLoan=((58885648*e.CPI_CAR/BASELINE_ECON.CPI_CAR)-10648764-20000000)/28236648;
 const newHousePay=pmt(363598263,e.MORTGAGE/100,360);
 const homeDelta=newHousePay-1675319;
 for(const [key,salary,spouse,gov,general,child,mortgage,auto,health,availableOriginal] of snapshot.incomeExpenseMonths){
  const t=key,scaleNew=t>=activeMonth;
  const generalAdj=scaleNew?general*(e.CPI_GENERAL/BASELINE_ECON.CPI_GENERAL):general;
  const childAdj=scaleNew?child*(e.CPI_GENERAL/BASELINE_ECON.CPI_GENERAL):child;
  const carAdj=scaleNew && t>='2034-11'&&t<='2039-10'?auto*Math.max(0,carDeltaLoan):auto;
  const mortAdj=scaleNew && t>='2046-11' && t<='2056-03'?mortgage+homeDelta:mortgage;
  // Customer itemized consumption adjustments apply from their effective month.
  // They alter only general consumption; childcare, mortgages, vehicle loans and
  // insurance remain separate and are never counted twice. A verified month's
  // explicit total-expense override takes precedence over this projected sum.
  const plannedConsumptionDelta=Number(consumptionDeltas[key]);
  const generalWithPlan=generalAdj+(Number.isFinite(plannedConsumptionDelta)?plannedConsumptionDelta:0);
  let income=salary+spouse+gov,expense=generalWithPlan+childAdj+mortAdj+carAdj+health;
  const changed=cashOverrides[key];
  if(changed&&finite(Number(changed.income))&&Number(changed.income)>=0)income=Number(changed.income);
  if(changed&&finite(Number(changed.expense))&&Number(changed.expense)>=0)expense=Number(changed.expense);
  const available=income-expense,budget=Math.max(0,available),given=actuals[key]||{};
  const required={},allocated={},balances={},entryStatus={};let reserved=0,used=0;
  for(const g of goals){required[g.id]=t<g.deadline?requirement(g,g.balance,t,snapshot.growthAnnual):0;
   if(t<g.deadline&&own(given,g.id)&&finite(Number(given[g.id]))&&Number(given[g.id])>=0){allocated[g.id]=Number(given[g.id]);reserved+=allocated[g.id];entryStatus[g.id]='user_entered';actualCount[g.id]++;}
  }
  let remaining=Math.max(0,budget-reserved);
  for(const g of sorted){if(!own(allocated,g.id)){allocated[g.id]=Math.min(required[g.id],remaining);remaining=Math.max(0,remaining-allocated[g.id]);entryStatus[g.id]='forecast';}}
  for(const g of goals){
   used+=allocated[g.id];
   if(t>=g.deadline){g.balance=0;balances[g.id]=0;continue;}
   // Confirmed historical balances accrue at the rate prevailing when that month was closed.
   // Unclosed future months use the latest verified deposit-rate assumption.
   const locked=historyEconomics[t],historicRate=locked&&Number.isFinite(Number(locked.DEPOSIT))?Math.pow(1+Number(locked.DEPOSIT)/100,1/12)-1:null;
   const accrual=g.id==='ret'?g.monthlyRate:(historicRate??(t<activeMonth?g.baseMonthlyRate:g.monthlyRate));
   g.balance=Math.max(0,g.balance*(1+accrual)+allocated[g.id]);balances[g.id]=g.balance;
  }
  const missing=Object.fromEntries(goals.map(g=>[g.id,Math.max(0,required[g.id]-allocated[g.id])]));
  const free=available-used;
  cumulativeFree+=free;
  if(free<-.01)overbooked++;
  const rec={month:t,income,expense,available,required,allocated,missing,balances,status:entryStatus,assigned:used,needed:Object.values(required).reduce((a,b)=>a+b,0),free,cumulativeFree,economicScenario:scaleNew&&econ.changes.length>0,
   expenseParts:{general:generalWithPlan,childcare:childAdj,mortgage:mortAdj,carLoan:carAdj,insurance:health},
   baselineParts:{general,childcare:child,mortgage,carLoan:auto,insurance:health},
   expenseOverride:!!(changed&&finite(Number(changed.expense))&&Number(changed.expense)>=0)};
  monthsOut.push(rec);monthlyByKey[t]=rec;
  for(const g of goals)if(offset(t,1)===g.deadline)book[g.id]={deadline:g.deadline,goal:g.total,expected:g.balance,shortfall:Math.max(0,g.total-g.balance),rate:g.monthlyRate};
 }
 for(const g of goals)if(!book[g.id])book[g.id]={deadline:g.deadline,goal:g.total,expected:g.balance,shortfall:Math.max(0,g.total-g.balance),rate:g.monthlyRate};
 // After retirement, 2056-04...2083-03. The required draw is pension-net expenditure.
 // V52 timing: draw at the start, earn on post-draw balance. Never equate a clamped-zero balance with success.
 let retirementBalance=Number(snapshot.dcRetirement||0)+(book.ret?.expected||0),firstUnmet=null,totalUnmet=0;
 const postRate=Math.pow(1+.04,1/12)-1,retirementProjection=[];
 for(const [date,draw,netMonth,expense,pension,insurance] of (snapshot.retirementMonths||[])){
  const baseExpense=Number(expense)||0,baseMortgage=date<='2076-10'?1675319:0;
  const livingBase=Math.max(0,baseExpense-baseMortgage);
  const cpiDelta=livingBase*(e.CPI_GENERAL/BASELINE_ECON.CPI_GENERAL-1);
  const houseDelta=date<='2076-10'?homeDelta:0;
  const raw=Math.max(0,(Number(draw)||0)+cpiDelta+houseDelta),surplus=Math.max(0,Number(netMonth)||0);
  const actual=Math.min(raw,retirementBalance),unmet=raw-actual;
  if(unmet>1&&!firstUnmet)firstUnmet=date;
  totalUnmet+=unmet;retirementBalance=Math.max(0,(retirementBalance-actual)*(1+postRate)+surplus);
  retirementProjection.push({month:date,balance:retirementBalance,needed:raw,paid:actual,unmet,expense:baseExpense+cpiDelta+houseDelta,pension,insurance});
 }
 const first=monthsOut[0],last=monthsOut[monthsOut.length-1];
 return {asOf:snapshotNow,activeMonth,source:snapshot.source,goals:goals.map(g=>({...g})),byId,months:monthsOut,byMonth:monthlyByKey,book,actualCount,economics:econ,overbooked,first,last,retirement:{initial:((snapshot.dcRetirement||0)+(book.ret?.expected||0)),lastBalance:retirementBalance,firstUnmet,totalUnmet,projection:retirementProjection},schema:snapshot.schema};
}
const api={months,offset,requirement,newGoalMoney,simulate,BASELINE_ECON};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.IFPK_V55=api;
})(typeof window!=='undefined'?window:globalThis);
