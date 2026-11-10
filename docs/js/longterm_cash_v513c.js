/* V51-3c — read-only, transparent cash-liquidity sensitivity through retirement.
 * Only six observed trial monthly deltas are carried, never guessed recurring.
 * Optional *additional* nominal monthly spending relief is user-assumed and explicit.
 * Purpose-fund balances, pension/DC/IRP, and official ledger are immutable.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V513C=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const FIRST='2026-11',RETIRE='2056-04',LAST='2056-03',END='2077-03';
 const shift=(s,n)=>{const z=s.split('-').map(Number),q=z[0]*12+z[1]-1+n;return Math.floor(q/12)+'-'+String(q%12+1).padStart(2,'0');};
 const num=x=>typeof x==='number'&&Number.isFinite(x);
 const checkLedger=s=>{const k=Object.keys(s||{}).sort();return k.length===605&&k[0]===FIRST&&k.at(-1)===END&&k.every((d,i)=>d===shift(FIRST,i)&&Array.isArray(s[d])&&s[d].length===19&&s[d].every(num));};
 const limit=(x)=>{if(x===undefined||x===null||x==='')return 0;const v=Number(x);return Number.isSafeInteger(v)&&v>=0&&v<=2000000?v:null;};
 function project(snapshot,review,opts={}){
  if(!checkLedger(snapshot))return {ready:false,reason:'기준 605개월 원장 검증 실패'};
  if(!review?.ready||!review.payload||review.payload.officialApplied!==false)return {ready:false,reason:'검증된 6개월 고객 검토 시험이 필요합니다.'};
  const r=review.payload,asOf=r.asOf,comparison=r.comparison;
  if(typeof asOf!=='string'||asOf<FIRST||shift(asOf,5)>=RETIRE||!Array.isArray(comparison)||comparison.length!==6)return {ready:false,reason:'6개월 시험기간 확인 실패'};
  const extraMonthlyRelief=limit(opts.additionalMonthlyRelief);
  const duration=String(opts.duration||'12');
  if(extraMonthlyRelief===null||!['6','12','36','retirement'].includes(duration))return {ready:false,reason:'추가 월 절감액은 0~200만원 정수, 적용기간은 6/12/36개월 또는 은퇴 전까지 선택'};
  // Six-month trial cash changes are the only *modelled* changes from the engine.
  // A manual cash relief is explicitly outside the six-month engine and never auto-CPI-escalated.
  const deltaByMonth=new Map();let lastOffset=null;
  for(let i=0;i<6;i++){
   const d=shift(asOf,i),line=comparison[i];
   if(!line||line.month!==d||![line.plannedNet,line.testedNet,line.baselineCash,line.testedCash].every(num))return {ready:false,reason:`${d} 시험 산식 데이터 불일치`};
   if(Math.abs(line.baselineCash-snapshot[d][16])>2)return {ready:false,reason:`${d} 기준원장과 6개월 비교의 현금잔액 불일치`};
   deltaByMonth.set(d,line.testedNet-line.plannedNet);
   const impliedOffset=line.testedCash-line.baselineCash;
   const sum=Array.from(deltaByMonth.values()).reduce((a,b)=>a+b,0);
   const start=impliedOffset-sum;
   if(lastOffset!==null&&Math.abs(start-lastOffset)>3)return {ready:false,reason:`${d} 6개월 누적현금 연결 오류`};
   lastOffset=start;
  }
  const openingOffset=lastOffset||0;
  let monthlyDelta=0,manualSum=0,affectedMonths=0;
  const baseline=[],trial=[],illustrations=[];
  const maxMonths=duration==='retirement'?Infinity:Number(duration);
  const sampleDates=new Set([asOf,shift(asOf,5),'2039-10','2046-10','2056-03']);
  for(let d=FIRST,i=0;d<RETIRE;d=shift(d,1),i++){
   const original=snapshot[d][16];
   if(d>=asOf){
    const byEngine=deltaByMonth.get(d)||0;
    monthlyDelta+=byEngine;
    const distance=(+d.slice(0,4)-+asOf.slice(0,4))*12+(+d.slice(5,7)-+asOf.slice(5,7));
    const saving=distance<maxMonths?extraMonthlyRelief:0;
    manualSum+=saving;if(saving)affectedMonths++;
   }
   const difference=d>=asOf?openingOffset+monthlyDelta+manualSum:0;
   const cash=Math.round(original+difference);
   baseline.push({month:d,cash:Math.round(original)});
   trial.push({month:d,cash,delta:Math.round(difference)});
   if(sampleDates.has(d))illustrations.push({month:d,baseline:Math.round(original),trial:cash,delta:Math.round(difference)});
  }
  function stats(arr){let firstDeficit=null,worst=Infinity,worstMonth=null,negativeMonths=0;
   for(const r of arr){if(r.cash<0){negativeMonths++;if(!firstDeficit)firstDeficit=r.month;}if(r.cash<worst){worst=r.cash;worstMonth=r.month;}}
   return {firstDeficit,negativeMonths,worst,worstMonth,last:arr.at(-1).cash};
  }
  const s=stats(trial),b=stats(baseline);
  const snapshot2039=illustrations.find(x=>x.month==='2039-10')||null;
  const engineCarry=Math.round(openingOffset+monthlyDelta);
  return {ready:true,official:false,asOf,until:LAST,sourceMonths:605,examinedMonths:baseline.length,sixMonthEngineDeltas:comparison.map(x=>({month:x.month,delta:Math.round(x.testedNet-x.plannedNet)})),sixMonthEngineCarry:engineCarry,manual:{amount:extraMonthlyRelief,duration,affectedMonths,total:manualSum,nominalFixed:true,assumptionOnly:true},baseline:b,trial:s,improvementAtWorstMonth:b.worstMonth?trial.find(x=>x.month===b.worstMonth).cash-b.worst:0,at2039:snapshot2039,samples:illustrations,retirementAssumptionsChanged:false,goalAccountBalancesRecomputed:false,postRetirementWithdrawalsRecomputed:false,officialLedgerUpdated:false,risks:['6개월 계산결과만 원장 현금차이로 반영하며 7개월차부터 6개월 재설계의 반복효과를 임의 외삽하지 않음','추가 월 절감액은 사용자가 직접 입력한 명목금액. 실적·물가지표·자동 절감/저축 실행 증빙 아님','목적저축이 변경되면 목표계좌 잔액 및 목표달성 가능성 별도 재검증 필요','은퇴 후 국민연금·DC·IRP·인출·건보 및 공식 원장 변경 없음']};
 }
 return Object.freeze({project,shift,FIRST,LAST,RETIRE,checkLedger});
});
