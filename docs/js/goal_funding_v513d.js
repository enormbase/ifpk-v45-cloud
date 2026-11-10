/* V51-3d — purpose account stress test and rollout scope validation.
 * Reference balances: authoritative 605-month sheet snapshot. Never assumes
 * general cash or user spending savings transfer into designated accounts.
 * Manual monthly purpose-saving changes are explicitly additional to the
 * already-computed six-month rolling test; not a silent permanent extension.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V513D=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const FIRST='2026-11',RETIRE='2056-04',END='2077-03',INTEREST=.02628945/12;
 const goals=Object.freeze({
  car:{label:'자동차 교체',date:'2034-10',expenseIndex:4,saveIndex:9,balanceIndex:12},
  travel:{label:'해외여행',date:'2038-10',expenseIndex:5,saveIndex:10,balanceIndex:13},
  house:{label:'주택 갈아타기',date:'2046-10',expenseIndex:3,saveIndex:8,balanceIndex:11}
 });
 const shift=(s,n)=>{const [y,m]=s.split('-').map(Number),j=y*12+m-1+n;return `${Math.floor(j/12)}-${String(j%12+1).padStart(2,'0')}`;};
 const distance=(a,b)=>{const [y,m]=a.split('-').map(Number),[Y,M]=b.split('-').map(Number);return (Y-y)*12+M-m;};
 const finite=v=>typeof v==='number'&&Number.isFinite(v);
 const ledgerOk=s=>{const k=Object.keys(s||{}).sort();return k.length===605&&k[0]===FIRST&&k.at(-1)===END&&k.every((d,i)=>d===shift(FIRST,i)&&Array.isArray(s[d])&&s[d].length===19&&s[d].every(finite));};
 const cleanInteger=(raw)=>{if(raw===null||raw===undefined||raw==='')return 0;const n=Number(raw);return Number.isSafeInteger(n)&&Math.abs(n)<=2000000?n:null;};
 function goalBaseline(snapshot){
  if(!ledgerOk(snapshot))return {ready:false,reason:'공식 기준 605개월 원장 검증 오류'};
  const items={};
  for(const [key,g] of Object.entries(goals)){
   const row=snapshot[g.date],required=row[g.expenseIndex],accountEnd=row[g.balanceIndex],eventTransfer=row[14];
   // These are separate goal event months: only one purpose-account withdrawal per event.
   if(![required,accountEnd,eventTransfer].every(finite)||required<=0||accountEnd<0||Math.abs(eventTransfer-required)>2)
    return {ready:false,reason:`${g.label} ${g.date} 목표금/계좌 전입 단일성 대사 실패`};
   const available=Math.round(accountEnd+eventTransfer);
   items[key]={key,label:g.label,date:g.date,required:Math.round(required),available,remaining:Math.round(accountEnd),baseSurplus:Math.round(available-required),baseGap:Math.max(0,Math.round(required-available)),baselineReady:available+2>=required,source:'605개월 구글시트 기준원장 · 해당 목적계좌 전용 자금',accountNotGeneralCash:true};
  }
  return {ready:true,items,sourceMonths:605};
 }
 function project(snapshot,review,opts={},rollingGoalAudit=null){
  const baseline=goalBaseline(snapshot);if(!baseline.ready)return baseline;
  if(!review?.ready||review.payload?.officialApplied!==false)return {ready:false,reason:'검증된 6개월 변경안 비교가 선행돼야 합니다.'};
  const asOf=review.payload.asOf;
  if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(asOf)||asOf<FIRST||asOf>=RETIRE||!Array.isArray(review.payload.comparison)||review.payload.comparison.length!==6)
   return {ready:false,reason:'6개월 재설계 기준월 검증 실패'};
  const key=String(opts.goal||'car'),g=goals[key],monthlyChange=cleanInteger(opts.monthlyChange),duration=String(opts.duration||'12');
  if(!g)return {ready:false,reason:'주택·자동차·해외여행 중 하나만 선택해 주세요.'};
  if(monthlyChange===null||!['6','12','36','goal'].includes(duration))return {ready:false,reason:'추가 저축 변경액은 ±200만원 정수, 기간은 6·12·36개월 또는 목표 전까지'};
  if(asOf>=g.date)return {ready:false,reason:`${g.label} 목표월(${g.date})이 재설계월(${asOf})보다 빠릅니다. 해당 목표의 과거 집행은 변경 불가.`};
  const monthsLeft=distance(asOf,g.date),months=Math.min(monthsLeft,duration==='goal'?monthsLeft:Number(duration));
  // A contribution made in month M is kept invested through the goal event month.
  let fvDelta=0,nominalDifference=0,deltaCash2039=0;
  for(let i=0;i<months;i++){
   const date=shift(asOf,i),r=snapshot[date];
   if(r[g.saveIndex]+monthlyChange<0)return {ready:false,reason:`${date} ${g.label} 월 적립액이 0원 미만이 됩니다. 감액 폭을 줄여주세요.`};
   fvDelta+=monthlyChange*Math.pow(1+INTEREST,distance(date,g.date));
   nominalDifference+=monthlyChange;
   if(date<='2039-10')deltaCash2039-=monthlyChange;
  }
  const b=baseline.items[key],newAvailable=Math.max(0,Math.round(b.available+fvDelta));
  const forecast={};
  for(const [k,entry] of Object.entries(goals)){
   const one=Array.isArray(rollingGoalAudit)?rollingGoalAudit.find(x=>x.key===k):null;
   forecast[k]=one&&one.month===entry.date&&[one.required,one.available,one.unfunded].every(finite)?
    {state:'projected',month:entry.date,required:Math.round(one.required),available:Math.round(one.available),unfunded:Math.round(one.unfunded),funded:one.unfunded<=0,conditional:true}:
    {state:'pending',month:entry.date,reason:'해당 분야 지표 확인 보류 또는 재설계 기준월에 이미 목표월 경과'};
  }
  const selected={...b,asOf,monthlyChange,duration,appliedMonths:months,baselineMonthlyContribution:snapshot[asOf][g.saveIndex],trialMonthlyContribution:snapshot[asOf][g.saveIndex]+monthlyChange,trialAvailable:newAvailable,fvDelta:Math.round(fvDelta),nominalContributionDelta:nominalDifference,trialSurplus:newAvailable-b.required,trialGap:Math.max(0,b.required-newAvailable),trialFunded:newAvailable>=b.required,unfundedNeverAutoTransferred:true};
  return {ready:true,official:false,asOf,selected,baseline:baseline.items,rolling:forecast,generalCashSensitivity:{extraContributionDelta:nominalDifference,extraCashBeforeGoals:nominalDifference===0?0:-nominalDifference,extraCashTo2039BeforeGoals:deltaCash2039,doesNotSettleGoalShortfall:true},nominalAnnualInterest:.02628945,old605Unchanged:true,retirementAssumptionsChanged:false,goalBalanceRecomputedFromUserAssumption:true,otherGoalBalancesChanged:false,otherGoalLiquidityUpdated:false,notes:[
  '목표월 필요자금은 각 목적계좌에서 부담하는 부분만 비교. 자동차 목표의 2,000만원은 차량 전체 가격이 아니라 기존 모델 자기자금 몫임',
  '소비절감 15만원은 일반현금 개선 가정이며 목적계좌로 자동 이체하지 않음',
  '수기 목적저축 조정은 6개월 엔진의 변경액에 더하는 별도 추가 가정. 같은 적립액 변화를 두 번 입력하면 중복 계산됨',
  '목표월에 부족액이 발생해도 일반현금에서 자동 충당하지 않음. 일반현금 개선액은 목표 부족액 조달 전 참고치',
  '해당 월 적립액 납입 성공·실제 목표 달성·고객 공식 승인·은퇴자산 변경은 확인되지 않음']};
 }
 return Object.freeze({project,goalBaseline,shift,goals});
});
