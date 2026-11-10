/* IFPK V51-2i — read-only retirement asset double-count audit.
 * Based on the frozen November-2026 source model. No public plan mutations.
 * The original integrated prepared total ALREADY INCLUDES future retirement
 * savings. Reprojecting those same deposits at 5.3% is a sensitivity check,
 * NEVER an extra asset. National pension is already netted from required funds.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V512I=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const CATEGORIES=Object.freeze(['unknown','within-plan','new-independent']);
const NET=Object.freeze(['unknown','net-confirmed','tax-uncertain']);
const asInteger=(x)=>Number.isSafeInteger(x)&&x>=0&&x<=1e12;
function audit(debt,model={},options={},liquidity={}){
 const needed=model.neededRetirement,dc=model.dcAfterTax,prepared=model.initialRetirement;
 if(![needed,dc,prepared].every(asInteger))return {ready:false,reason:'원본 필요 은퇴자금·DC·준비자산 기준값 검증 실패'};
 const planned=prepared-dc;
 if(planned<0||Math.abs(planned-252911768)>10000)return {ready:false,reason:'원본 준비자산과 세후 DC·기존 목적저축의 금액 연결이 일치하지 않아 보류합니다.'};
 const relation=options.retAssetOrigin||'unknown',tax=options.retAssetUsability||'unknown';
 if(!CATEGORIES.includes(relation)||!NET.includes(tax))return {ready:false,reason:'은퇴자산 구분·세후 사용가능 여부의 선택값 오류'};
 const entered=!!debt?.ready&&!!debt?.retirement?.entered&&!!debt?.retirement?.projected;
 const startingFV=entered?debt.retirement.startingFV:null;
 const futureContributionFV=entered?debt.retirement.futureContributionsFV:null;
 if(entered&&(!asInteger(startingFV)||!asInteger(futureContributionFV)))return {ready:false,reason:'은퇴자산 미래가치 계산값 검증 실패'};
 const missing=[];
 if(!entered)missing.push('현재 은퇴자산 평가액 미입력');
 if(relation==='unknown')missing.push('기존 DC·IRP·원본 준비자산과 중복 여부 미확인');
 if(relation==='within-plan')missing.push('입력 자산이 기존 준비자산에 포함됨 · 중복 합산 금지');
 if(tax!=='net-confirmed')missing.push(tax==='tax-uncertain'?'미래가치 세후 사용가능 금액 미확인':'세후 사용가능성 확인 전');
 // Allow a *conditional* extra-asset sensitivity only for a specifically
 // excluded, independently available, assumed-after-tax asset. No plan approval.
 const canCompare=entered&&relation==='new-independent'&&tax==='net-confirmed';
 const extra=canCompare?startingFV:0;
 const scenarioPrepared=canCompare?prepared+extra:null;
 const scenarioDifference=canCompare?scenarioPrepared-needed:null;
 const fundedSixMonths=liquidity?.ready&&liquidity.unfundedMonths===0&&liquidity.maximumUnfundedCash===0;
 const liquidityStatus=liquidity?.ready?(fundedSixMonths?'검토 6개월 중 저축 부족 미발견 (전체 기간 보장 아님)':'검토 6개월 중 현금·저축 부족 위험'):'향후 저축 납입가능성 미검증';
 return {
  ready:true,previewOnly:true,approved:false,
  source:'2026년 11월 최종 구글시트 고정 계획값',
  needed,dcAfterTax:dc,originalPlannedRetirementSavingFV:planned,originalPrepared:prepared,
  baseSurplus:prepared-needed,baseAfterDcShortfall:Math.max(0,needed-dc),
  entered,startingFV,futureContributionFV,
  relation,tax,canCompare,excludedFV:extra,
  scenarioPrepared,scenarioDifference,
  blockedReasons:missing,
  liquidityStatus, fundedSixMonths,
  guards:{pensionAlreadyNettedFromNeed:true,originalSavingAlreadyInPrepared:true,
   futureContributionsNeverAdded:true,dcNeverAddedTwice:true,
   unverifiedBalancesNeverApproved:true,postRetirementCashflowRecomputed:false,
   official605MonthLedgerUnchanged:true},
  summary:canCompare?'별도의 세후 사용가능 자금이라는 조건부 가정으로 비교':'중복·세후 여부 확인 전: 추가 합산 보류',
  explanation:'원본 준비자산에는 세후 DC와 기존 은퇴목적 저축의 미래가치가 이미 들어 있습니다. ⑨의 미래 은퇴월저축 FV는 같은 적립금에 다른 수익률을 적용한 참고값이므로 다시 더하지 않습니다. 국민연금은 필요 은퇴자금 계산에서 이미 차감했습니다.'
 };
}
return Object.freeze({audit});
});
