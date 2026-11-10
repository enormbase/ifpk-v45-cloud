/* IFPK V51-2e: read-only as-of account reconciliation and evidence gating.
 * Customer-entered amounts are NOT verified or persisted. Past-as-of entries
 * are unverified reports; future-as-of entries are scenarios, not observed data.
 * Existing mortgages and retirement balances are recorded only as review inputs.
 * They are not applied to debt underwriting or retirement FV calculations.
 */
(function(root,factory){
 const api=factory(root?.IFPK_V512A||(typeof module==='object'&&module.exports?require('./rolling_preview_v512a.js'):null));
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V512E=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(base){
 'use strict';
 if(!base)throw new Error('IFPK_V512A missing');
 const MAX=1e12;
 const FIELDS=Object.freeze([
  {key:'cash',label:'일반현금',source:'liquidCash',row:null},
  {key:'house',label:'주택 목적계좌',source:'house',row:11},
  {key:'car',label:'자동차 목적계좌',source:'car',row:12},
  {key:'travel',label:'여행 목적계좌',source:'travel',row:13}
 ]);
 const empty=x=>x===null||x===undefined||String(x).trim()==='';
 const validMoney=(raw,label)=>{
  if(empty(raw))return {entered:false,value:null};
  const v=Number(raw);
  if(!Number.isSafeInteger(v)||v<0||v>MAX)return {error:`${label}: 0원 이상 1조 원 이하의 정수로 입력해 주세요.`};
  return {entered:true,value:v};
 };
 const currentMonth=()=>new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'}).slice(0,7);
 function reconcile(snapshot,preview,input={},today){
  if(!snapshot||!preview?.ready||!preview?.monthlyResults)return {ready:false,reason:'먼저 6개월 재설계 계산을 실행해 주세요.'};
  const asOf=preview.asOf,prior=base.shift(asOf,-1);
  const previous=asOf===base.START?null:snapshot[prior];
  const previousResult=asOf===base.START?null:preview.monthlyResults[prior];
  if(asOf!==base.START&&(!Array.isArray(previous)||!previousResult||!Number.isFinite(previousResult.baselineCash)))
   return {ready:false,reason:'재설계 직전 월 원장 또는 현금기준값을 찾을 수 없습니다.'};
  const future=asOf>(today||currentMonth());
  const inputState={},accounts=[];
  for(const spec of FIELDS){
   const parsed=validMoney(input[spec.source],spec.label);if(parsed.error)return {ready:false,reason:parsed.error};
   inputState[spec.key]=parsed;
   const planned=spec.key==='cash'?(previousResult?.baselineCash??0):
     (previous?.[spec.row]??base.GOALS[spec.key].initial);
   if(!Number.isFinite(planned))return {ready:false,reason:`${spec.label} 계획상 잔액이 없습니다.`};
   const actual=parsed.entered?parsed.value:null;
   const delta=parsed.entered?actual-Math.round(planned):null;
   const goal=preview.goals?.[spec.key];
   accounts.push({key:spec.key,label:spec.label,plan:Math.round(planned),input:actual,difference:delta,
     status:parsed.entered?(future?'미래시점 가정':'고객 입력 · 증빙 미확인'):'계획 추정 · 실적 미확인',
     saving:goal?.active?goal.newSaving:null,
     isPurpose:spec.key!=='cash'});
  }
  const retirement=validMoney(input.retirementAssets,'은퇴준비 금융자산 평가액');
  const mortgage=validMoney(input.mortgageOutstanding,'기존 주담대 잔존원금');
  const statement=validMoney(input.fundsAggregate,'네 계좌의 합계 확인금액');
  for(const p of [retirement,mortgage,statement])if(p.error)return {ready:false,reason:p.error};
  // A four-account subtotal must never be called reconciled when any component
  // is inferred from the financial plan rather than user-entered.
  const fourEntered=accounts.every(a=>a.input!==null);
  const enteredSubtotal=fourEntered?accounts.reduce((s,a)=>s+a.input,0):null;
  const aggregateStatus=!statement.entered?'합계 대조 미요청':!fourEntered?'잔액 4개가 모두 입력되지 않아 대조 보류':
    Math.abs(enteredSubtotal-statement.value)<=1?'입력값끼리 일치 · 증빙 미확인':'입력된 4계좌 합계 불일치 · 중복/누락 확인';
  const aggregateDelta=statement.entered&&fourEntered?statement.value-enteredSubtotal:null;
  const enteredCount=accounts.filter(a=>a.input!==null).length+Number(retirement.entered)+Number(mortgage.entered);
  const differenceCount=accounts.filter(a=>a.difference!==null&&a.difference!==0).length;
  const cautions=[];
  if(future)cautions.push(`${asOf}는 아직 지나지 않은 기준월입니다. 입력한 잔액은 실제 실적이 아니라 미래 시나리오입니다.`);
  if(accounts.some(a=>a.input===null))cautions.push('입력하지 않은 계좌는 기존 계획상 추정값으로 남습니다. 고객의 실제 저축 실적으로 확정하지 않습니다.');
  if(accounts.some(a=>a.key==='cash'&&a.plan<0))cautions.push('계획상 일반현금이 음수이면 미조달 현금입니다. 별도 자산 또는 확정된 차입으로 취급하지 않습니다.');
  if(retirement.entered)cautions.push('은퇴 금융자산 평가액은 이번 미리보기 화면에만 입력·표시되며 공식 저장하지 않습니다. DC·IRP·필요 은퇴자금 및 은퇴자산 미래가치(FV)를 다시 계산하지 않습니다.');
  if(mortgage.entered)cautions.push('기존 주담대 잔액은 이번 미리보기 화면에만 입력·표시되며 공식 저장하지 않습니다. 기존 대출상환표·2046년 대출한도/LTV/DSR·이사 자기자금에는 아직 연결하지 않습니다.');
  if(aggregateDelta!==null&&Math.abs(aggregateDelta)>1)cautions.push('4개 계좌 합계가 일치하지 않습니다. 계좌 간 자금이동이나 중복 집계 여부를 확인해야 합니다.');
  cautions.push('일반현금·주택·자동차·여행 4계좌 합계는 은퇴계좌·부동산 가치·기존 대출잔액을 포함하지 않습니다.');
  cautions.push('고객 입력·계획 추정과 은행/증권사 명세서로 검증된 실적은 다릅니다. 이 결과는 공식 계획에 적용되지 않습니다.');
  return {ready:true,asOf,prior,future,previewOnly:true,mayApprove:false,accounts,
   enteredCount,requiredCount:6,differenceCount,
   retirement:{entered:retirement.entered,value:retirement.value,source:retirement.entered?(future?'미래시점 가정':'고객 입력 · 증빙 미확인'):'실제 평가액 미확인',recalculated:false},
   mortgage:{entered:mortgage.entered,value:mortgage.value,source:mortgage.entered?(future?'미래시점 가정':'고객 입력 · 증빙 미확인'):'실제 잔존원금 미확인',recalculated:false},
   fundsAggregate:{entered:statement.entered,value:statement.value,enteredSubtotal,delta:aggregateDelta,status:aggregateStatus,mathematicallyConsistent:aggregateDelta!==null&&Math.abs(aggregateDelta)<=1},
   purposeSavingsUnchangedByCash:true,mortgageAppliedToDSR:false,retirementRecomputed:false,
   cautions};
 }
 return Object.freeze({FIELDS,reconcile});
});
