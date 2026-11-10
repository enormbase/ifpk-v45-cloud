/* IFPK V51-2c — illustrative lending capacity, NOT underwriting approval.
 * The original model has no separately confirmed 2046 household gross income or
 * other-debt annual service at the target date. Therefore, the DSR cash-payment
 * budget is calibrated from the original 40%-DSR maximum mortgage of KRW
 * 363,598,263 at 3.708%, 360 months. DO NOT label that proxy as verified income.
 * All outputs are scenario estimates under fixed DSR budgets, not official Korean
 * LTV/DSR/Stress-DSR regulatory eligibility, and they require customer checking.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V512C_LOAN=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const BASE=Object.freeze({loan:363598263,annualPct:3.708,term:360,dsr:40,ltv:70});
 const CASES=Object.freeze({tight:Object.freeze({id:'tight',label:'강화 가정',ltv:60,dsr:35}),base:Object.freeze({id:'base',label:'기준 가정',ltv:70,dsr:40}),loose:Object.freeze({id:'loose',label:'완화 가정',ltv:80,dsr:45})});
 const valid=n=>typeof n==='number'&&Number.isFinite(n);
 function monthlyFactor(annualPct,term=360){
   if(!valid(annualPct)||annualPct<0||annualPct>30||!Number.isInteger(term)||term<1)return null;
   const r=annualPct/1200;
   return r<1e-12?1/term:r/(1-Math.pow(1+r,-term));
 }
 function payment(principal,annualPct,term=360){const factor=monthlyFactor(annualPct,term);return factor===null||!valid(principal)||principal<0?null:Math.round(principal*factor);}
 function assess(price,rate,oldNet,selected='base'){
   if(!valid(price)||price<0||price>1e12||!valid(oldNet)||oldNet<0||oldNet>1e12||!Object.hasOwn(CASES,selected))
     return {ready:false,reason:'주택가격·기존 주택 순매각대금 또는 LTV/DSR 시나리오 입력 오류'};
   const baseFactor=monthlyFactor(BASE.annualPct,BASE.term),factor=monthlyFactor(rate,BASE.term);
   if(factor===null)return {ready:false,reason:'신규 주담대 가정금리는 연 0~30% 범위로 입력해야 합니다.'};
   const referServiceMonthly=BASE.loan*baseFactor;
   const impliedAnnualDebtServiceBase=referServiceMonthly*12;
   const impliedAnnualIncomeEquivalent=impliedAnnualDebtServiceBase/(BASE.dsr/100);
   const loanNeed=Math.max(0,price-oldNet);
   const cases=Object.fromEntries(Object.entries(CASES).map(([id,c])=>{
     const ltvLimit=Math.floor(price*c.ltv/100);
     // Normalize by the original reference DSR cap. No inferred borrower income
     // or external debts are asserted as customer facts.
     const dsrLimit=Math.round(BASE.loan*(c.dsr/BASE.dsr)*(baseFactor/factor));
     const maxLoan=Math.max(0,Math.min(ltvLimit,dsrLimit,Math.floor(loanNeed)));
     const monthlyPayment=payment(maxLoan,rate,BASE.term);
     const requiredOwn=Math.max(0,Math.round(price-oldNet-maxLoan));
     return [id,{...c,ltvLimit,dsrLimit,maxLoan,monthlyPayment,requiredOwn,binding:maxLoan===Math.floor(loanNeed)?'자금필요 상한':maxLoan===ltvLimit?'LTV 제한':'DSR 환산 제한'}];
   }));
   const chosen=cases[selected];
   const identityResidual=price-oldNet-chosen.maxLoan-chosen.requiredOwn;
   if(Math.abs(identityResidual)>1)return {ready:false,reason:'주택 자금조달 항등식 불일치'};
   return {ready:true,selected,chosen,cases,rate,price,oldNet,
      baseEquivalentMonthlyService:referServiceMonthly,
      annualGrossEquivalent:impliedAnnualIncomeEquivalent,
      assumptions:'원본 기준 대출한도(DSR 40%, 3.708%, 360개월)로 환산한 상환여력 고정. 다른 부채·금융기관 심사·스트레스 DSR 미반영',
      actualEligibilityVerified:false};
 }
 return Object.freeze({BASE,CASES,monthlyFactor,payment,assess});
});
