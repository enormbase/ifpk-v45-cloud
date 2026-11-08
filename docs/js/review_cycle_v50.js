/* IFPK V50 | 반기 점검 일정·검증 범위·미승인 비교 (공식 월별 원장 미변경)
 * Browser & Node CommonJS — pure calculation functions.
 * 새 API 관측치는 '비교자료'이며, 공식 재무계획으로 확정하지 않는다.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V50_REVIEW=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const ANCHOR='2026-11';
  const INTERVAL=6;
  function monthIndex(s){
    if(typeof s!=='string'||!/^(\d{4})-(0[1-9]|1[0-2])$/.test(s))return null;
    const [year,month]=s.split('-').map(Number);return year*12+month-1;
  }
  function fmtMonth(n){return String(Math.floor(n/12)).padStart(4,'0')+'-'+String(n%12+1).padStart(2,'0');}
  function cycle(today=ANCHOR,anchor=ANCHOR){
    const now=monthIndex(today),origin=monthIndex(anchor);
    if(now===null||origin===null)throw Error('기준월 형식은 YYYY-MM이어야 합니다');
    const elapsed=now-origin;
    const dueCount=elapsed<INTERVAL?0:Math.floor(elapsed/INTERVAL);
    const lastDue=dueCount>0?fmtMonth(origin+dueCount*INTERVAL):null;
    const nextDue=fmtMonth(origin+(dueCount+1)*INTERVAL);
    return {anchor,lastDue,nextDue,due:dueCount>0&&now>=monthIndex(lastDue),period:lastDue||anchor,elapsedMonths:elapsed};
  }
  function seoulMonth(date=new Date()){
    const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit'}).formatToParts(date);
    return parts.find(x=>x.type==='year').value+'-'+parts.find(x=>x.type==='month').value;
  }
  const KEYS=['monthlySaving','monthlyLoanPayment','ownCashGoal','newHomeFuture','oldHomeFuture'];
  function extractHomePreview(status){
    if(!status||status.published!==true)return {ready:false,reason:'클라우드 공개·검증 상태가 확인되지 않았습니다.'};
    const impact=status.homeImpact;
    if(!impact||!impact.approved||!Array.isArray(impact.scenarios))return {ready:false,reason:'V49 주택 영향분석 데이터가 아직 준비되지 않았습니다.'};
    const pick=impact.scenarios.find(s=>s.id==='weighted')||impact.scenarios.find(s=>s.id==='rates_only');
    if(!pick)return {ready:false,reason:'계산에 필요한 시나리오가 없습니다.'};
    const old=impact.approved;
    if(!KEYS.every(key=>Number.isFinite(old[key])&&Number.isFinite(pick[key])))return {ready:false,reason:'변경 전후 금액이 일부 누락되거나 유효하지 않습니다.'};
    const vintage=impact.vintage||{};
    return {ready:true,partial:true,scope:'주택 부분 민감도',scenario:pick.id,
      verified:impact.status==='ready',vintage:{homePrice:String(vintage.homePrice||''),deposit:String(vintage.deposit||''),mortgage:String(vintage.mortgage||'')},
      before:Object.fromEntries(KEYS.map(k=>[k,old[k]])),
      after:Object.fromEntries(KEYS.map(k=>[k,pick[k]])),
      differences:Object.fromEntries(KEYS.map(k=>[k,pick[k]-old[k]]))};
  }
  function reviewReadiness(status){
    const preview=extractHomePreview(status);
    const checks=[
      {name:'공식 원장 공개',ready:status?.published===true,desc:'GitHub Pages의 실제 수집 스냅샷'},
      {name:'주택 영향분석',ready:preview.ready&&preview.verified,desc:'주택·금리 부분 비교만 가능'},
      {name:'은퇴·양육·일반소비 전체 재계산',ready:false,desc:'구글시트 수준 수식 연동·검증 필요'},
      {name:'605개월 통합 현금흐름 재검증',ready:false,desc:'모든 탭의 동일 계산 원천 검증 필요'},
      {name:'공식 새 계획 적용',ready:false,desc:'전체 검증 완료 전 승인 잠금'}
    ];
    return {checks,preview,mayApprove:checks.every(c=>c.ready)};
  }
  function makeReviewRecord(period,preview,nowISO){
    if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(period)||!preview?.ready)throw Error('검토 가능한 자료가 필요합니다');
    return {period,reviewedAt:nowISO||new Date().toISOString(),status:'자료 확인(공식 미승인)',scope:preview.scope,scenario:preview.scenario,vintage:{...preview.vintage},diffMonthlySaving:preview.differences.monthlySaving};
  }
  return Object.freeze({ANCHOR,INTERVAL,cycle,seoulMonth,extractHomePreview,reviewReadiness,makeReviewRecord});
});
