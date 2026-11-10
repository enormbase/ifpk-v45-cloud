/* V51-3f | Customer-first monthly observation / six-month review hub.
 * Pure formatter/summary; does not request APIs or modify the approved 605-month ledger.
 * Explicitly differentiate actual stored observation and scheduled/approved changes.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V513F=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const formatMonth=x=>/^\d{4}-\d{2}$/.test(String(x||''))?String(x):'확인 대기';
 const stages=Object.freeze(['매월 수집·저장','6개월 재설계 검토','변경 결과 비교']);
 function summarize({specs=[],records=[],status={},online=false,schedule={},preview=null,asOf='' }={}){
  if(!Array.isArray(specs)||!Array.isArray(records))throw Error('지표 및 기록 형식 확인 필요');
  const runs=Array.isArray(status?.latestRuns)?status.latestRuns:[];
  const estimates=Array.isArray(status?.estimates)?status.estimates:[];
  const indicators=specs.map(sp=>{
    const ids=Array.isArray(sp.ids)&&sp.ids.length?sp.ids:[sp.id];
    // Preserve the selected R-ONE reference series: never merge index base years.
    let found=[];let sourceId=ids[0];
    for(const id of ids){const a=records.filter(x=>x.id===id && /^\d{4}-\d{2}$/.test(String(x.date||'')) && Number.isFinite(Number(x.value)));if(a.length){found=[...a].sort((a,b)=>String(a.date).localeCompare(String(b.date)));sourceId=id;break;}}
    const last=found.length?found.at(-1):null;
    const run=runs.find(x=>x.id===sourceId)||runs.find(x=>ids.includes(x.id));
    const estimate=estimates.find(x=>x.id===sourceId)||estimates.find(x=>ids.includes(x.id));
    const stale=!!estimate?.stale;
    const state=last?(stale?'기록 있음 · 최신성 점검':'관측자료 보관 중'):(run?.status==='failed'?'수집 오류 확인 필요':'공개자료 확인 대기');
    return {id:sp.id,label:sp.label,source:sp.source,purpose:sp.purpose,sourceId,month:last?.date||null,value:last?.value??null,unit:last?.unit||sp.unit||'',savedAt:last?.retrievedAt||null,runStatus:run?.status||null,hasObservation:!!last,stale,state,count:found.length};
  });
  const observed=indicators.filter(x=>x.hasObservation).length;
  const changed=preview?.ready && Number.isFinite(Number(preview?.payload?.deltaCash))?Number(preview.payload.deltaCash):null;
  return {
    stages, indicators, observed, total:indicators.length,
    schedule:{anchor:formatMonth(schedule.anchor),next:formatMonth(schedule.nextDue),last:schedule.lastDue?formatMonth(schedule.lastDue):null,reviewDue:!!schedule.due},
    review:{asOf:formatMonth(asOf),deltaCash:changed,hasPreview:changed!==null,officialApplied:false,forecastScope:'향후 6개월 부분 시험'},
    policy:{monthlyCollectionPlanned:true,collectionSuccessNotAssumed:true,sixMonthReviewPlanned:true,automaticApproval:false,retirementParametersFixed:true},
    cloudObservationStatus:online?'공개 원장 응답 확인':'공개 원장 확인 대기',
    releaseTime:status?.generatedAt||null,
  };
 }
 return Object.freeze({summarize});
});
