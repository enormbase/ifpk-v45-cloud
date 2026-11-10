/* IFPK V51-2g — verified scenario-only bridge: existing mortgage payoff ->
 * net old-home sale proceeds -> 2046 new-house equity -> remaining savings.
 * IMPORTANT: No mortgage balance is verified, official plan is NOT edited;
 * V51-2f payoff was already calculated at 2046-09, and must be counted ONCE.
 * New mortgage LTV/DSR still uses the conditional 2026 reference income budget.
 */
(function(root,factory){
 const f=root?.IFPK_V512B||(typeof module==='object'&&module.exports?require('./rolling_projection_v512b.js'):null);
 const m=root?.IFPK_V512F||(typeof module==='object'&&module.exports?require('./debt_retirement_v512f.js'):null);
 const api=factory(f,m);
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V512G=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(fin,mort){
 'use strict';
 if(!fin||!mort)throw Error('V51-2g requires V512B and V512F');
 function link(snapshot,records,options={},balances={},today='2026-11'){
   const first=fin.compute(snapshot,records,options);
   if(!first.ready)return {ready:false,preview:first,reason:first.reason};
   const debt=mort.project(snapshot,first,balances,today);
   if(!debt.ready)return {ready:true,preview:first,debt,applied:false,reason:debt.reason,previewOnly:true};
   const mortgage=debt.mortgage;
   const home=first.goals.house;
   const hasDirectHome=options.houseGoal!==undefined&&options.houseGoal!==null&&String(options.houseGoal).trim()!=='';
   if(!mortgage.projected||!home?.active||first.environment.homeBlocked||hasDirectHome){
     const reason=!mortgage.projected?'기존 주담대 잔액을 입력해야 이사자금에 연결할 수 있어요.':
       !home?.active?'이사 목표월이 지났거나 주택 저축 계산이 보류됐어요.':
       first.environment.homeBlocked?'주택가격·금리 기준이 검증되기 전에는 주택 연결을 보류해요.':
       '직접 지정한 이사 자기자금이 우선이므로 대출잔액 변화로 목표를 덮어쓰지 않아요.';
     return {ready:true,preview:first,debt,applied:false,reason,previewOnly:true};
   }
   const delta=mortgage.saleBalanceDelta;
   // A same-balance input is valid and produces a zero-change comparison.
   const next=fin.compute(snapshot,records,{...options,existingMortgageSaleDelta:delta});
   if(!next.ready)return {ready:true,preview:first,debt,applied:false,reason:'이사자금 연결 검증 보류: '+next.reason,previewOnly:true};
   const before=first.finance,after=next.finance;
   const beforeSaving=first.goals.house.newSaving,afterSaving=next.goals.house.newSaving;
   const oldHomeNetDelta=after.oldHomeNet-before.oldHomeNet;
   const loanDelta=after.loan-before.loan;
   const equityDelta=after.own-before.own;
   const identityDelta=oldHomeNetDelta+loanDelta+equityDelta;
   if(Math.abs(identityDelta)>1||Math.abs(oldHomeNetDelta+delta)>1)
     return {ready:true,preview:first,debt,applied:false,reason:'주택 매각대금·신규대출·자기자금 항등식 검증 실패',previewOnly:true};
   // Never move money from the separate goal account to cash at the sale twice:
   // fin.compute owns the single end-of-goal event. We only replace the home
   // savings and funding target in the read-only preview.
   return {ready:true,preview:next,debt,applied:true,previewOnly:true,mayApprove:false,asOf:next.asOf,
     status:'조건부 주택자금 연결 완료 · 공식 미적용',
     before:{oldMortgageBalance:mortgage.oldSaleBalance,netSaleProceeds:before.oldHomeNet,newMortgage:before.loan,requiredEquity:before.own,monthlySaving:beforeSaving},
     after:{oldMortgageBalance:mortgage.saleBalance,netSaleProceeds:after.oldHomeNet,newMortgage:after.loan,requiredEquity:after.own,monthlySaving:afterSaving},
     delta:{oldMortgageBalance:delta,netSaleProceeds:oldHomeNetDelta,newMortgage:loanDelta,requiredEquity:equityDelta,monthlySaving:afterSaving-beforeSaving},
     cashFlow:{beforeAtReview:first.monthlyResults[next.asOf].previewCash,afterAtReview:next.monthlyResults[next.asOf].previewCash,
       beforeAtSale:first.monthlyResults['2046-10'].previewCash,afterAtSale:next.monthlyResults['2046-10'].previewCash},
     safeguards:{identityVerified:true,pastUntouched:(()=>{const [yy,mm]=next.asOf.split('-').map(Number);const prev=mm===1?`${yy-1}-12`:`${yy}-${String(mm-1).padStart(2,'0')}`;return next.monthlyResults[prev].previewCash===first.monthlyResults[prev].previewCash;})(),
       oldMortgageMonthlyCashFlowFullRebuild:false,customerEvidenceVerified:false,full605OfficialRebuilt:false,
       bankEligibilityVerified:false,pastPaymentsUnchanged:true,retirementAssetsUnchanged:true},
     note:'이사 직전 기존 주담대 상환잔액의 변화는 기존 집 순매각대금에 한 번만 반영. 목표 자기자금·미래 주택저축·목표월 계좌전입을 시험 재계산. 기존 주담대 향후 모든 월의 상환액은 605개월 전체 현금흐름에 아직 미반영; 6개월 실행가능성 표에만 반영.'};
 }
 return Object.freeze({link});
});
