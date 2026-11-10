/* IFPK V51-2f | Read-only as-of mortgage and retirement projection.
 * Inputs are unverified client hypotheses, not account statements. This module
 * NEVER edits the approved ledger, pension/DC values, or loan eligibility.
 * Mortgage: original Jan-2026 loan, 12 months interest-only, Dec-2055 maturity;
 * original 1.9% for first 60 months, thereafter 2.65%; as-of principal is
 * beginning-of-month, and 2046 sale pays off September 2046 ending principal.
 * Retirement: input balance is an unspecified account; show separately from
 * future retirement deposits. Never add either to official DC without proving
 * what the customer balance already includes.
 */
(function(root, factory){
  const base=root?.IFPK_V512A || (typeof module==='object'&&module.exports?require('./rolling_preview_v512a.js'):null);
  const api=factory(base);
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V512F=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(base){
'use strict';
if(!base)throw Error('IFPK_V512A missing');
const LOAN_START='2026-01', GRACE_END='2026-12', RATE_RESET='2031-01';
const SALE='2046-10', SALE_PRIOR='2046-09', MATURITY='2055-12';
const RETIRE_PRIOR='2056-03', ORIGINAL=260000000, ORIGINAL_SALE_BAL=104117759;
const DEFAULT_RET_RATE=.053;
const parse=(raw,label)=>{
 if(raw===null||raw===undefined||String(raw).trim()==='')return {entered:false,value:null};
 const n=Number(raw);
 if(!Number.isSafeInteger(n)||n<0||n>1000000000000)return {error:label+'은(는) 0~1조 원의 정수만 입력할 수 있습니다.'};
 return {entered:true,value:n};
};
const pm=(b,r,n)=>{const m=r/12;return m===0?b/n:b*m/(1-Math.pow(1+m,-n));};
function baselineSchedule(){
 const map={};let b=ORIGINAL,scheduled=0;
 for(let k=0;k<360;k++){
  const month=base.shift(LOAN_START,k),r=k<60?.019:.0265;
  if(k===12)scheduled=pm(b,r,360-k);
  if(k===60)scheduled=pm(b,r,360-k);
  const interest=b*r/12;
  const pay=k<12?interest:Math.min(b+interest,scheduled);
  const end=Math.max(0,b+interest-pay);
  map[month]={month,begin:b,interest,payment:pay,end,rate:r};b=end;
 }
 return map;
}
const original=baselineSchedule();
function mortgageProjection(asOf,begin){
 let balance=begin,scheduled=0;const rows={};
 for(let m=asOf;m<SALE;m=base.shift(m,1)){
  const idx=base.between(LOAN_START,m);
  const rate=idx<60?.019:.0265;
  const isGrace=idx<12;
  if(!isGrace&&(m===asOf||m==='2027-01'||m===RATE_RESET))scheduled=pm(balance,rate,360-idx);
  const interest=balance*rate/12;
  const payment=isGrace?interest:Math.min(balance+interest,scheduled);
  const end=Math.max(0,balance+interest-payment);
  rows[m]={month:m,begin:balance,payment,interest,end,rate,
   baseline:original[m],deltaPayment:payment-original[m].payment};
  balance=end;
 }
 return {rows,saleBalance:balance};
}
function retirementProjection(snapshot,asOf,input,rate=DEFAULT_RET_RATE){
 if(!Number.isFinite(rate)||rate<0||rate>.2)return {ready:false,reason:'은퇴자산 가정수익률은 연 0~20% 범위여야 합니다.'};
 const monthly=(1+rate)**(1/12)-1;
 let current=input,contrib=0,count=0,contribNominal=0;
 for(let m=asOf;m<=RETIRE_PRIOR;m=base.shift(m,1)){
  const row=snapshot[m];if(!Array.isArray(row)||!Number.isFinite(row[7])||row[7]<0)return {ready:false,reason:'은퇴 목적저축 원장 누락 · '+m};
  current*=1+monthly;
  contrib=contrib*(1+monthly)+row[7];
  contribNominal+=row[7];count++;
 }
 return {ready:true,months:count,assumedReturnPct:rate*100,startingFV:Math.round(current),
  futureContributionsFV:Math.round(contrib),futureContributionsNominal:Math.round(contribNominal),
  nominalRetirementMonth:'2056-04',retirementValuation:'2056-03 말',
  separateAccountOnly:true,notOfficialAssets:true,notDCVerified:true};
}
function project(snapshot,preview,inputs={},today='2026-11'){
 if(!preview?.ready||!snapshot)return {ready:false,reason:'먼저 6개월 재설계 미리보기를 계산하세요.'};
 const asOf=preview.asOf,ret=parse(inputs.retirementAssets,'은퇴자산'),loan=parse(inputs.mortgageOutstanding,'기존 주담대 잔액');
 if(ret.error||loan.error)return {ready:false,reason:ret.error||loan.error};
 const future=asOf>today;
 const mortgage={entered:loan.entered,projected:false,eligible:asOf<SALE,
  reason:asOf>=SALE?'이사 예정월 이후에는 기존 집 대출잔액을 적용하지 않습니다.':!loan.entered?'기존 주담대 잔액 미입력 · 기존 계획 유지':'',
  oldBalanceAtReview:original[asOf]?.begin??null,oldSaleBalance:ORIGINAL_SALE_BAL,
  inputBalance:loan.value,deltaByMonth:{},pastUntouched:true};
 if(loan.entered&&asOf<SALE){
  const out=mortgageProjection(asOf,loan.value),monthDelta={};
  for(const [month,r] of Object.entries(out.rows))monthDelta[month]=r.deltaPayment;
  Object.assign(mortgage,{projected:true,monthOfMove:SALE,
   firstMonth:asOf,firstPayment:Math.round(out.rows[asOf].payment),
   firstBaselinePayment:Math.round(out.rows[asOf].baseline.payment),
   saleBalance:Math.round(out.saleBalance),oldSaleBalance:ORIGINAL_SALE_BAL,
   saleBalanceDelta:Math.round(out.saleBalance-ORIGINAL_SALE_BAL),
   monthlyDelta:monthDelta,rateChange:'2031-01',
   beforeMoveUsesOldMortgageOnly:true,mortgageAppliedToLtvDsr:false,
   homeSavingNotYetRecomputed:true});
 }
 const retirement={entered:ret.entered,projected:false,reason:ret.entered?'':'은퇴 금융자산 잔액을 입력하면 독립적인 미래가치를 계산합니다.',inputBalance:ret.value};
 if(ret.entered){const out=retirementProjection(snapshot,asOf,ret.value);
  if(!out.ready)return {ready:false,reason:out.reason};Object.assign(retirement,out,{projected:true,notAppliedToOfficialRetirement:true});}
 return {ready:true,previewOnly:true,mayApprove:false,asOf,future,mortgage,retirement,
  cautions:['금액은 고객 입력 · 증빙 미확인이며 미래 기준월 입력은 단순 가정입니다.',
  '기존 주담대 입력은 월초 잔액 기준입니다. 이후 원리금균등과 금리변경을 반영한 시험 계산입니다.',
  '주담대 상환액 변화는 V51-2h의 6개월 실행가능성 및 은퇴 전 장기 월별 미리보기에만 시험 반영합니다. 이사자금은 V51-2g 연결 계산으로 별도 시험하며, 605개월 공식 원장·대출규제 실심사는 변경되지 않습니다.',
  '은퇴 금융자산 FV는 연 5.3% 수익률 가정이며 DC·IRP 구분 및 중복 여부를 확인하기 전 공식 은퇴준비자산이나 국민연금에 합산하지 않습니다.']};
}
return Object.freeze({project,baselineSchedule,mortgageProjection,retirementProjection,ORIGINAL_SALE_BAL,DEFAULT_RET_RATE});
});
