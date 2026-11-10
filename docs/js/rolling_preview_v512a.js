/* IFPK V51-2a: read-only rolling preview against the workbook's 605-month ledger.
   THIS IS NOT AN APPROVAL ENGINE. Observed CPI and explicit hypothetical values
   are kept separate; missing actual customer balances are labelled estimates.
   Retirement/pension/DC, policy rules and scenario financing are NOT recalculated.
*/
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V512A=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const START='2026-11',END='2077-03',RETIRE='2056-04';
 const PLAN_INFLATION=.025, SAVING_RATE=.02628945;
 const GOALS=Object.freeze({
   house:{label:'주택',date:'2046-10',goal:141486810,initial:20000000,initialMonthly:345345,colBalance:11,colSaving:8},
   car:{label:'자동차',date:'2034-10',goal:20000000,initial:0,initialMonthly:189847,colBalance:12,colSaving:9},
   travel:{label:'해외여행',date:'2038-10',goal:6724444,initial:1000000,initialMonthly:32032,colBalance:13,colSaving:10}
 });
 const AMOUNT_CAP=1e12;
 const monthValid=s=>typeof s==='string'&&/^\d{4}-(0[1-9]|1[0-2])$/.test(s);
 const number=n=>typeof n==='number'&&Number.isFinite(n);
 const shift=(s,n)=>{const [y,m]=s.split('-').map(Number),j=y*12+m-1+n;return `${Math.floor(j/12)}-${String(j%12+1).padStart(2,'0')}`;};
 const between=(a,b)=>{const [ay,am]=a.split('-').map(Number),[by,bm]=b.split('-').map(Number);return (by-ay)*12+bm-am;};
 const monthly=(annual)=>Math.pow(1+annual,1/12)-1;
 function legacyBudget(month){const y=Number(month.slice(0,4));if(y<=2026)return 2400000;if(y<=2029)return 2200000;if(y<=2033)return 2300000;return Math.round(2300000*Math.pow(1+PLAN_INFLATION,y-2033));}
 function currentBudget(month){return Math.round(2400000*Math.pow(1+PLAN_INFLATION,between(START,month)/12));}
 function neededMonthly(goal,balance,n,annual=SAVING_RATE){
   if(![goal,balance,annual].every(number)||goal<0||goal>AMOUNT_CAP||balance<0||balance>AMOUNT_CAP||annual<0||annual>1||!Number.isInteger(n)||n<0)return null;
   const r=monthly(annual);
   if(!n)return 0;
   const fv=Math.pow(1+r,n),remaining=goal-balance*fv;
   return Math.max(0,Math.round(Math.abs(r)<1e-12?remaining/n:remaining*r/(fv-1)));
 }
 function normalizeRecords(records,id,asOf,baseDate,expectedUnit){
   const found=(Array.isArray(records)?records:[]).filter(x=>x&&x.id===id&&monthValid(x.date)&&x.date>=baseDate&&x.date<=shift(asOf,-1));
   for(const r of found){if(!number(Number(r.value))||Number(r.value)<=0||String(r.unit||'').replace(/\s/g,'')!==expectedUnit.replace(/\s/g,''))return {ready:false,reason:`${id}: 동일한 기준(${expectedUnit})의 양수 지수만 사용할 수 있습니다.`};}
   return {ready:true,records:found.sort((a,b)=>a.date.localeCompare(b.date))};
 }
 function generalCpi(records,asOf,hypothetical){
   const checked=normalizeRecords(records,'CPI_GENERAL',asOf,'2026-10','2020=100');
   if(!checked.ready)return checked;
   const base=120.73,after=checked.records.filter(x=>x.date>'2026-10');
   let last=after.at(-1)||null,manual=false;
   if(hypothetical!==null&&hypothetical!==undefined&&String(hypothetical).trim()!==''){
     const value=Number(hypothetical);
     if(!number(value)||value<=0||value>10000||asOf<=START)return {ready:false,reason:'가상 CPI 값 또는 재설계 시점을 확인해 주세요.'};
     const target=shift(asOf,-1);
     if(last&&last.date>target)return {ready:false,reason:'실측월 이후를 가상 관측월로 사용할 수 없습니다.'};
     last={date:target,value,unit:'2020=100',provider:'사용자 가정'};manual=true;
   }
   const observedDate=last?.date||'2026-10',value=Number(last?.value??base);
   const months=between('2026-10',observedDate);
   const correction=value/base/Math.pow(1+PLAN_INFLATION,months/12);
   return {ready:true,source:manual?'가정 시나리오':last?'공식 관측값':'새 관측 없음',observedDate,value,base,months,correction,observed:!manual&&!!last,manual};
 }
 function movingAverage(records,id,asOf,count,baseValue,baseDate){
   const checked=normalizeRecords(records,id,asOf,shift(baseDate,-count+1),'2020=100');
   if(!checked.ready)return checked;
   const dict=new Map(checked.records.map(x=>[x.date,Number(x.value)]));
   const dates=[...dict.keys()].filter(x=>x>=baseDate).sort().reverse();
   let newest=null;
   for(const date of dates){const samples=Array.from({length:count},(_,i)=>dict.get(shift(date,-i)));
     if(samples.every(number)){newest={date,average:samples.reduce((a,b)=>a+b,0)/count};break;}
   }
   if(!newest||newest.date<=baseDate)return {ready:false,reason:`${id}의 기준월 이후 연속 ${count}개월 CPI가 부족합니다.`};
   const correction=newest.average/baseValue/Math.pow(1+PLAN_INFLATION,between(baseDate,newest.date)/12);
   return {ready:true, ...newest,correction,source:`공식 ${count}개월 이동평균`};
 }
 function readLedger(snapshot){
   if(!snapshot||typeof snapshot!=='object')return {ready:false,reason:'605개월 원장 없음'};
   const keys=Object.keys(snapshot).sort();if(keys.length!==605||keys[0]!==START||keys.at(-1)!==END)return {ready:false,reason:'605개월 공식 원장 길이·기준월 불일치'};
   let prevCash=0,maxNetDiff=0,maxCashDiff=0;
   for(let i=0;i<keys.length;i++){
     const month=keys[i],row=snapshot[month];
     if(month!==shift(START,i)||!Array.isArray(row)||row.length<19||!row.slice(0,19).every(number))return {ready:false,reason:`${month} 기준 원장 오류`};
     const diffNet=Math.abs(row[0]+row[1]-row[2]-row[3]-row[4]-row[5]-row[6]);
     const diffCash=Math.abs(prevCash+row[6]-row[7]-row[8]-row[9]-row[10]+row[14]+row[15]-row[16]);
     maxNetDiff=Math.max(maxNetDiff,diffNet);maxCashDiff=Math.max(maxCashDiff,diffCash);
     if(diffNet>2||diffCash>2)return {ready:false,reason:`${month}의 원본 수입·지출 또는 월말 잔액 검산 실패`};
     prevCash=row[16];
   }
   return {ready:true,months:605,maxNetDiff,maxCashDiff};
 }
 function estimateBalance(snapshot,key,asOf,explicit){
   if(explicit!==null&&explicit!==undefined&&String(explicit).trim()!==''){
     const n=Number(explicit);if(!number(n)||n<0||n>AMOUNT_CAP)return {ready:false,reason:`${GOALS[key].label} 목적잔액 입력 오류`};
     return {ready:true,balance:n,source:'입력된 실제 잔액(미증빙)',confirmed:true};
   }
   const def=GOALS[key],prior=shift(asOf,-1);
   const balance=asOf===START?def.initial:snapshot[prior]?.[def.colBalance];
   if(!number(balance))return {ready:false,reason:`${key}: 기존 원장 추정잔액을 찾지 못했습니다.`};
   return {ready:true,balance,source:'기존 계획 추정(실적 미확인)',confirmed:false};
 }
 function planGoals(snapshot,asOf,balances,travelIndex,houseGoal){
   const results={};const warnings=[];
   for(const [key,def] of Object.entries(GOALS)){
     const n=between(asOf,def.date);
     if(n<=0){results[key]={active:false,reason:'목표시점 경과 · 새 목표 및 실제 집행 확인 필요',label:def.label,date:def.date};continue;}
     const b=estimateBalance(snapshot,key,asOf,balances?.[key]);
     if(!b.ready)return {ready:false,reason:b.reason};
     let goal=def.goal,priceStatus='초기 계산값 유지';
     if(key==='travel'&&travelIndex?.ready){goal=Math.round(def.goal*travelIndex.correction);priceStatus=`해외단체여행비 MA12(${travelIndex.date}) 적용`;}
     if(key==='house'&&houseGoal!==null&&houseGoal!==undefined&&String(houseGoal).trim()!==''){
       goal=Number(houseGoal);if(!number(goal)||goal<0||goal>AMOUNT_CAP)return {ready:false,reason:'주택 자기자금 시나리오 입력 오류'};
       priceStatus='고객 입력 가정: 새 주택 필요 자기자금 (공식 지표 자동 추정 아님)';
     }
     const newSaving=neededMonthly(goal,b.balance,n);
     if(newSaving===null)return {ready:false,reason:`${def.label} 저축액 계산 오류`};
     const rate=monthly(SAVING_RATE),futureBal=b.balance*Math.pow(1+rate,n)+newSaving*(Math.pow(1+rate,n)-1)/rate;
     results[key]={active:true,label:def.label,date:def.date,months:n,goal,balance:b.balance,balanceStatus:b.source,confirmed:b.confirmed,baseSaving:def.initialMonthly,newSaving,deltaSaving:newSaving-def.initialMonthly,priceStatus,projectedGoalBalance:Math.round(futureBal),coverage:futureBal>=goal-2};
     if(!b.confirmed)warnings.push(`${def.label} 목적저축 잔액은 기존 계획 추정치입니다.`);
   }
   return {ready:true,results,warnings};
 }
 function compute(snapshot,records,opts={}){
   const ledger=readLedger(snapshot);if(!ledger.ready)return {ready:false,reason:ledger.reason};
   const asOf=opts.asOf||START;
   if(!monthValid(asOf)||asOf<START||asOf>=RETIRE||between(START,asOf)%6!==0)return {ready:false,reason:'재설계 기준월은 2026-11부터 6개월 단위여야 합니다.'};
   const cpi=generalCpi(records,asOf,opts.hypotheticalCPI??null);if(!cpi.ready)return {ready:false,reason:cpi.reason};
   const actualText=opts.actualSpending;
   const usesActual=actualText!==null&&actualText!==undefined&&String(actualText).trim()!=='';
   const actualSpending=usesActual?Number(actualText):null;
   if(usesActual&&(!number(actualSpending)||actualSpending<0||actualSpending>200000000))return {ready:false,reason:'확인된 현재 월 일반생활비는 0~2억원 범위여야 합니다.'};
   const travel= movingAverage(records,'CPI_TRAVEL',asOf,12,125.4608,'2026-09');
   const car= movingAverage(records,'CPI_CAR',asOf,3,115.83,'2026-09');
   const goal=planGoals(snapshot,asOf,opts.balances||{},travel,opts.houseGoal??null);
   if(!goal.ready)return goal;
   const carFuturePrice=car.ready?Math.round(58885412*car.correction):58885412;
   const carLoan=Math.max(0,carFuturePrice-10648764-20000000);
   const priorCarLoan=28236648,annualLoanRate=.05,loanMonths=60;
   const loanPmt=l=>Math.round(l*(annualLoanRate/12)/(1-Math.pow(1+annualLoanRate/12,-loanMonths)));
   let baseCash=0,newCash=0,baseDeficits=0,newDeficits=0,firstDeficit=null,changedMonths=0;
   const examples=[],monthlyResults={};
   const samples=new Set([START,shift(asOf,-1),asOf,shift(asOf,1),'2027-01','2034-10','2038-10','2046-10',END]);
   for(const month of Object.keys(snapshot).sort()){
     const row=snapshot[month],beforeRet=month<RETIRE;
     const rebase=beforeRet?currentBudget(month)-legacyBudget(month):0;
     const newGeneral=(beforeRet&&month>=asOf)?(usesActual?Math.round(actualSpending*Math.pow(1+PLAN_INFLATION,between(asOf,month)/12)):Math.round(currentBudget(month)*cpi.correction)):null;
     const cpiCost=newGeneral!==null?newGeneral-currentBudget(month):0;
     const expenseBase=row[2]+rebase,expenseNew=expenseBase+cpiCost;
     const savingsBase=row.slice(7,11);
     const savingsNew=savingsBase.slice();
     if(beforeRet&&month>=asOf){
       for(const [key,def] of Object.entries(GOALS)){
         const active=goal.results[key];if(active?.active&&month<def.date)savingsNew[def.colSaving-7]=active.newSaving;
       }
     }
     // General spending, purpose-saving transfers only; events and retirement inputs remain unchanged.
     const netBase=row[6]-rebase,netNew=row[6]-rebase-cpiCost;
     const common=row[14]+row[15];
     baseCash+=netBase-savingsBase.reduce((a,b)=>a+b,0)+common;
     newCash+=netNew-savingsNew.reduce((a,b)=>a+b,0)+common;
     baseCash=Math.round(baseCash);newCash=Math.round(newCash);
     if(beforeRet){if(baseCash<0)baseDeficits++;if(newCash<0){newDeficits++;firstDeficit ||= month;}}
     if((beforeRet&&month>=asOf)&&(cpiCost!==0||savingsNew.some((x,i)=>x!==savingsBase[i])))changedMonths++;
     monthlyResults[month]={month,baselineCash:baseCash,previewCash:newCash,monthlyExpenseBase:expenseBase,monthlyExpensePreview:expenseNew,cpiExtraExpense:cpiCost,baselineGeneralBudget:beforeRet?currentBudget(month):null,projectedGeneralBudget:beforeRet&&month>=asOf?currentBudget(month)+cpiCost:null,retirementSave:savingsNew[0],houseSave:savingsNew[1],carSave:savingsNew[2],travelSave:savingsNew[3]};
     if(samples.has(month))examples.push(monthlyResults[month]);
   }
   const final=monthlyResults[END],asOfRow=monthlyResults[asOf];
   return {ready:true,partial:true,mayApprove:false,scope:'일반소비 CPI 보정과 3개 목적저축의 월 현금흐름 검토용 재계산(은퇴·대출·자산 장부 미포함)',
     sourceCount:Array.isArray(records)?records.length:0,asOf,cpi,actualSpending,spendingMethod:usesActual?'고객 확인 생활비 우선·미래 2.5%':'CPI 보정·미래 2.5%',travel,car,goals:goal.results,warnings:goal.warnings,
     carFuturePrice,carLoan,carPaymentBefore:loanPmt(priorCarLoan),carPaymentAfter:loanPmt(carLoan),carLoanCashflowApplied:false,
     baseDeficits,newDeficits,firstDeficit,changedMonths,ledgerMonths:ledger.months,
     baselineCashAtReview:asOfRow.baselineCash,previewCashAtReview:asOfRow.previewCash,
     baselineFinalCash:final.baselineCash,previewFinalCash:final.previewCash,
     monthlyResults,examples,
     pending:['은퇴 후 필요자금·DC·국민연금 재계산','주택 신규대출·차량 할부 월별 재연결','목적계좌 실제 잔액 재산정 및 이벤트 지급 검증','전체 계획 승인과 과거 월별 공식 기록 고정']};
 }
 return Object.freeze({START,END,RETIRE,GOALS,between,shift,legacyBudget,currentBudget,neededMonthly,generalCpi,movingAverage,readLedger,estimateBalance,planGoals,compute});
});
