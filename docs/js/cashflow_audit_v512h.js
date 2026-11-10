/* IFPK V51-2h: read-only whole-horizon mortgage-payment audit + change attribution.
 * Keeps original 605-month ledger and every source preview immutable.
 * Reprojects existing mortgage payments ONLY from review month until the month
 * BEFORE the Oct-2046 sale; net sale payoff is reflected separately exactly
 * once by V512G in home equity and required goal savings.
 * Post-retirement rows are held as unverified, never mislabelled as an updated
 * retirement plan. This is not an asset/liability double-entry reconciliation:
 * reduced principal needs evidence of the funds used to repay it.
 */
(function(root,factory){
 const base=root?.IFPK_V512A||(typeof module==='object'&&module.exports?require('./rolling_preview_v512a.js'):null);
 const fin=root?.IFPK_V512B||(typeof module==='object'&&module.exports?require('./rolling_projection_v512b.js'):null);
 const api=factory(base,fin);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V512H=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(base,fin){
 'use strict';
 if(!base||!fin)throw Error('V51-2h requires V512A and V512B');
 const SALE='2046-10', RETIRE='2056-04';
 const valid=n=>typeof n==='number'&&Number.isFinite(n);
 function audit(snapshot,bridge){
   if(!bridge?.ready||!bridge.preview?.ready)return {ready:false,reason:bridge?.reason||'월별 미리보기 계산을 먼저 완료하세요.'};
   const src=bridge.preview,asOf=src.asOf;
   const ledger=base.readLedger(snapshot);
   if(!ledger.ready)return {ready:false,reason:ledger.reason};
   const mortgage=bridge.debt?.ready?bridge.debt.mortgage:null;
   const canApply=!!mortgage?.projected;
   const keys=Object.keys(snapshot).sort();
   if(keys.length!==605||!keys.every((k,i)=>k===base.shift(base.START,i)))return {ready:false,reason:'605개월 기준 원장의 월 연속성 검증 실패'};
   const result={}, samples=[],sampleSet=new Set([base.shift(asOf,-1),asOf,base.shift(asOf,1),'2030-12','2031-01','2046-09','2046-10','2056-03']);
   let paidDifference=0,activeMonths=0,priorIntegrated=null,preRetDeficits=0,firstAdjusted=null;
   const asOfPrior=base.shift(asOf,-1);
   for(const month of keys){
     const old=src.monthlyResults[month];
     if(!old||!valid(old.baselineCash))return {ready:false,reason:`${month} 미리보기 현금흐름 누락`};
     const eligible=month<RETIRE;
     // Must not count October 2046 payoff twice; September ending balance
     // was already transferred to net old-home proceeds by V512G.
     const active=canApply&&month>=asOf&&month<SALE&&eligible;
     const monthlyDelta=active?(mortgage.monthlyDelta[month]??NaN):0;
     if(!valid(monthlyDelta))return {ready:false,reason:`${month} 기존 주담대 월 상환액 검증 실패`};
     paidDifference+=monthlyDelta;
     if(active){activeMonths++;firstAdjusted??=month;}
     const previewCash=eligible&&valid(old.previewCash)?Math.round(old.previewCash-paidDifference):null;
     const expense=eligible&&valid(old.previewExpense)?old.previewExpense+monthlyDelta:null;
     const cashFlow=eligible&&valid(old.previewMonthlyCashflow)?old.previewMonthlyCashflow-monthlyDelta:null;
     const x={month,baselineCash:old.baselineCash,otherConditionsCash:old.previewCash,
       integratedCash:previewCash,baselineExpense:old.baselineExpense,
       otherConditionsExpense:old.previewExpense,integratedExpense:expense,
       mortgagePaymentDelta:monthlyDelta,mortgageCumulativeDelta:paidDifference,
       integratedMonthlyCashflow:cashFlow,preRetirement:eligible,
       changedByMortgage:active&&Math.abs(monthlyDelta)>.0001};
     if(month<asOf&&eligible&&(x.integratedCash!==old.baselineCash||x.integratedCash!==old.previewCash))
       return {ready:false,reason:`${month} 과거 현금흐름 변경 방지 검산 실패`};
     if(eligible&&previewCash<0)preRetDeficits++;
     if(eligible&&priorIntegrated!==null&&month>=asOf&&valid(old.previewMonthlyCashflow)){
       // Preview and baseline monthly aggregation use integer rounding for
       // accumulated cash, so permit a small bounded per-month discrepancy.
       if(Math.abs(previewCash-(old.previewCash-Math.round(paidDifference)))>1)
         return {ready:false,reason:`${month} 대출상환 차이 누적 검산 실패`};
     }
     priorIntegrated=previewCash;
     result[month]=x;
     if(sampleSet.has(month))samples.push(x);
   }
   if(canApply&&activeMonths===0)return {ready:false,reason:'월 상환 적용개월 검증 실패'};
   const after=result['2046-10'],before=result['2046-09'],retirePrior=result['2056-03'];
   const debtSaving=bridge.applied?bridge.delta.requiredEquity:0;
   const initial=fin.HOME_BASE.own;
   const otherGoal=bridge.applied?bridge.before.requiredEquity:src.finance.own;
   const finalGoal=bridge.applied?bridge.after.requiredEquity:src.finance.own;
   const otherEffect=otherGoal-initial;
   const totalEffect=finalGoal-initial;
   if(Math.abs(otherEffect+debtSaving-totalEffect)>1)return {ready:false,reason:'자기자금 변경원인 합계 검산 실패'};
   // Loan repayment is booked in monthly obligations, while lower sale payoff
   // is booked in home equity once. They are never both treated as a cash gift.
   const pastUnchanged=result[asOfPrior]?.integratedCash===src.monthlyResults[asOfPrior]?.baselineCash;
   const noPostSaleRepayment=after.mortgagePaymentDelta===0&&result['2056-03'].mortgagePaymentDelta===0;
   if(!pastUnchanged||!noPostSaleRepayment)return {ready:false,reason:'과거 보존 또는 이사 이후 대출상환 중복 검산 실패'};
   return {ready:true,mayApprove:false,previewOnly:true,asOf,sourceMonths:keys.length,
     integratedMonths:keys.filter(m=>m>=asOf&&m<RETIRE).length,
     mortgageApplied:canApply,mortgageAppliedMonths:activeMonths,
     mortgageFirstMonth:firstAdjusted,
     mortgageFirstPaymentDelta:result[asOf]?.mortgagePaymentDelta??0,
     monthlyPaymentTotalDelta:Math.round(paidDifference),
     totalCashDeltaFromPayment:Math.round(-paidDifference)||0,
     preRetirementNegativeMonths:preRetDeficits,
     previewCashAtReview:result[asOf].integratedCash,
     preRetirementLink:{month:'2056-03',baselineCash:retirePrior.baselineCash,
       otherConditionsCash:retirePrior.otherConditionsCash,previewCash:retirePrior.integratedCash,
       change:retirePrior.integratedCash-retirePrior.baselineCash,
       mortgageCashEffect:retirePrior.integratedCash-retirePrior.otherConditionsCash,
       unfundedIfNegative:Math.max(0,-retirePrior.integratedCash),retirementAssetsRecalculated:false},
     fundingAttribution:{
       initialRequiredEquity:initial,otherConditionsRequiredEquity:otherGoal,
       finalRequiredEquity:finalGoal,otherConditionsEffect:otherEffect,
       mortgageBalanceEffect:debtSaving,totalEffect,
       mortgageInputEffectIsolated:bridge.applied,
       initialMonthlySaving:fin.HOME_BASE.saving??345345,
       otherConditionsMonthlySaving:bridge.applied?bridge.before.monthlySaving:src.goals.house?.newSaving??null,
       finalMonthlySaving:bridge.applied?bridge.after.monthlySaving:src.goals.house?.newSaving??null,
       otherConditionsInclude:'최신 경제지표·대출규제 선택·목적잔액 등 다른 시험조건을 함께 포함'},
     monthlyResults:result,samples,
     safeguards:{immutableSource:true,pastUnchanged,noPostSaleRepayment,
       officialLedgerRebuilt:false,retirementRecomputed:false,
       retirementPostMonthsUnverified:true,customerEvidenceVerified:false,
       customerMortgagePrincipalFundingSourceUnverified:true,
       noDoubleCountAtSale:true},
     note:'경제지표 및 다른 가정의 영향과 기존 주담대 잔액 변화의 영향을 순서대로 구분한 참고 계산입니다. 기존대출 원금 감소에 사용한 실제 자금은 확인되지 않았으므로 총자산 증가로 간주하지 않습니다.'};
 }
 return Object.freeze({audit});
});
