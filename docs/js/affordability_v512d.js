/* IFPK V51-2d: six-month execution-feasibility diagnostic, NOT an approval engine.
 * Plans and observed cash are not synonymous. No planned contribution is reduced,
 * no loan is created, and no source ledger is edited. Inputs are client-provided
 * hypothetical or unverified amounts for the selected review date ONLY.
 */
(function(root,factory){
  const api=factory(root?.IFPK_V512A || (typeof module==='object'&&module.exports?require('./rolling_preview_v512a.js'):null));
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V512D=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(base){
 'use strict';
 if(!base)throw new Error('IFPK_V512A missing');
 const missing=v=>v===null||v===undefined||String(v).trim()==='';
 const bounded=(raw,label,cap)=>{
   if(missing(raw))return {entered:false,value:null};
   const n=Number(raw);
   if(!Number.isFinite(n)||n<0||n>cap)return {error:`${label}: 0원부터 ${cap.toLocaleString('ko-KR')}원까지 입력해 주세요.`};
   return {entered:true,value:n};
 };
 function analyze(snapshot,preview,input={}){
   if(!preview||!preview.ready||!preview.monthlyResults||!snapshot)return {ready:false,reason:'월별 롤링 미리보기를 먼저 계산해 주세요.'};
   const asOf=preview.asOf;
   const income=bounded(input.monthlyIncome,'고객 확인 월 순유입',200000000);
   const extraDebt=bounded(input.additionalDebt,'모형에 없는 추가 월 채무상환',100000000);
   const liquid=bounded(input.liquidCash,'재설계월 월초 일반현금',1e12);
   const paymentAdjustments=input.mortgageMonthlyAdjustment||null;
   if(paymentAdjustments&&(typeof paymentAdjustments!=='object'||Object.values(paymentAdjustments).some(v=>typeof v!=='number'||!Number.isFinite(v)||Math.abs(v)>100000000)))return {ready:false,reason:'기존 주담대 상환변화 계산값 확인 필요'};
   for(const v of [income,extraDebt,liquid])if(v.error)return {ready:false,reason:v.error};
   const lastMonth=base.shift(asOf,-1), prior=preview.monthlyResults[lastMonth];
   if(!prior||!Number.isFinite(prior.baselineCash))return {ready:false,reason:'재설계월 직전 계획 현금잔액이 없습니다.'};
   const startingCash=liquid.entered?liquid.value:prior.baselineCash;
   const months=[];
   let plannedCash=startingCash,worstCash=startingCash,unfundedMonths=0,firstUnfunded=null;
   let sixMonthGoalTotal=0,sixMonthIncomeTotal=0,sixMonthNeed=0,negativeMonths=0;
   const n=Math.min(6,Math.max(0,base.between(asOf,base.RETIRE)));
   for(let i=0;i<n;i++){
     const month=base.shift(asOf,i),src=snapshot[month],p=preview.monthlyResults[month];
     if(!Array.isArray(src)||!p||!Number.isFinite(p.previewMonthlyCashflow)||!Array.isArray(p.previewPurposeSave))return {ready:false,reason:`${month} 월별 원장 연결 실패`};
     const incomePlan=src[0]+src[1];
     const usedIncome=income.entered?income.value:incomePlan;
     const goalRet=src[7],goalHouse=p.previewPurposeSave[0],goalCar=p.previewPurposeSave[1],goalTravel=p.previewPurposeSave[2];
     const goals=[goalRet,goalHouse,goalCar,goalTravel];
     if(![incomePlan,usedIncome,...goals].every(Number.isFinite)||goals.some(x=>x<0))return {ready:false,reason:`${month} 저축·소득 기록 오류`};
     const targetSaving=goals.reduce((a,b)=>a+b,0);
     // Preview monthly cashflow includes all expenses, net event transfers and target saving.
     // Reverse only saving transfers, then apply separately identified input deltas.
     const incomeDifference=usedIncome-incomePlan;
     const mortgageAdjustment=paymentAdjustments?.[month]??0;
     const afterObligations=p.previewMonthlyCashflow+targetSaving+incomeDifference-(extraDebt.entered?extraDebt.value:0)-mortgageAdjustment;
     const monthlyAfterAll=afterObligations-targetSaving;
     const fundingGap=Math.max(0,targetSaving-afterObligations);
     const essentialGap=Math.max(0,-afterObligations);
     plannedCash=Math.round(plannedCash+monthlyAfterAll);
     worstCash=Math.min(worstCash,plannedCash);
     if(fundingGap>0){unfundedMonths++;firstUnfunded??=month;}
     if(plannedCash<0)negativeMonths++;
     sixMonthGoalTotal+=targetSaving;sixMonthIncomeTotal+=usedIncome;sixMonthNeed+=fundingGap;
     months.push({month,expectedIncome:incomePlan,usedIncome,afterObligations:Math.round(afterObligations),retirementSaving:goalRet,houseSaving:goalHouse,carSaving:goalCar,travelSaving:goalTravel,
       mortgagePaymentDifference:Math.round(mortgageAdjustment),targetSaving:Math.round(targetSaving),fundingGap:Math.round(fundingGap),essentialGap:Math.round(essentialGap),monthlyAfterAll:Math.round(monthlyAfterAll),cashAfterAll:plannedCash,affordableFromMonthlyFlow:Math.max(0,Math.round(afterObligations))});
   }
   return {ready:true,previewOnly:true,mayApprove:false,asOf,lastMonth,startingCash:Math.round(startingCash),startingSource:liquid.entered?'고객 입력 일반현금 · 증빙 미확인':'기존 계획 추정 일반현금 · 음수이면 미조달액',
     incomeSource:income.entered?'고객 입력 순유입 · 향후 6개월 임시 가정':'기존 통합원장 예상 순유입',
     debtSource:extraDebt.entered?'추가 채무상환 입력 · 향후 6개월 임시 가정':'추가 채무 입력 없음 · 기존 모델의 주담대/오토론만 반영',
     actualInputs:{income:income.entered,extraDebt:extraDebt.entered,liquidCash:liquid.entered},
     months,horizon:months.length,unfundedMonths,negativeMonths,firstUnfunded,goalTotal:Math.round(sixMonthGoalTotal),incomeTotal:Math.round(sixMonthIncomeTotal),
     summedFundingGap:Math.round(sixMonthNeed),closingCash:plannedCash,maximumUnfundedCash:Math.round(Math.max(0,-worstCash)),
     status:unfundedMonths?'월 현금흐름만으로 목표저축 전액 납입 불가능한 달 있음':'월 현금흐름 기준 목표저축 전액 납입 가능',
     notes:['월 현금흐름 기준의 실행가능성 검사이며 기존 목적저축·은퇴저축 목표를 자동 삭감하지 않습니다.',
       '입력한 월 순유입·추가채무는 향후 6개월 임시 가정이며 2046년 대출한도(DSR) 산정에 쓰지 않습니다.',
       '일반현금은 목적계좌·은퇴자산과 별도입니다. 계획상 마이너스는 실제 대출·차입으로 확정하지 않습니다.',
       '고객이 입력한 실제값도 증빙 및 월별 과거 실적 확정이 완료된 데이터가 아닙니다.',
       '적립금의 실행 가능 여부를 검사할 뿐 실제 계좌입금이나 새로운 은퇴자산 FV를 계산하지 않습니다.']};
 }
 return Object.freeze({analyze});
});
