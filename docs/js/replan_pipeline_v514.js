/* IFPK V51-4 | Read-only monthly evidence / six-month replan preparation.
 * Customer-visible: observation month != retrieval/run month != plan basis != approval date.
 * Does not schedule collectors, run API ingestion, change an approved plan or create approval records.
 */
(function(root,factory){
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.IFPK_V514=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const BASIS='2026-11';
 const SOURCE={house:['HOME_PRICE','MORTGAGE','DEPOSIT'],general:['CPI_GENERAL'],car:['CPI_CAR','DEPOSIT'],travel:['CPI_TRAVEL','DEPOSIT']};
 const AREAS=[{id:'house',label:'주택',process:'지역 주택가격지수 → 동일 기준 검증·주담대/예금금리 추정 → 이사 자금·대출·목적저축 비교'},
 {id:'general',label:'일반소비',process:'전국 CPI 원지수 → 경과기간 물가보정·기존 연 2.5% 전망 → 은퇴 전 생활비·일반현금 비교'},
 {id:'car',label:'자동차',process:'차량 CPI → 3개월 이동평균·기존 차량잔가율 → 교체가격·목적저축·할부 비교'},
 {id:'travel',label:'해외여행',process:'여행 CPI → 12개월 이동평균·연 2.5% 미래가정 → 여행예산·목적저축 비교'}];
 const validMonth=x=>typeof x==='string'&&/^(?:19|20|21)\d\d-(?:0[1-9]|1[0-2])$/.test(x);
 const mindex=x=>{if(!validMonth(x))return null;const [y,m]=x.split('-').map(Number);return y*12+m-1;};
 const shifted=(m,n)=>{const z=mindex(m);if(z===null)throw Error('YYYY-MM 기준월 형식 오류');const v=z+n;return `${Math.floor(v/12)}-${String(v%12+1).padStart(2,'0')}`;};
 const number=x=>typeof x==='number'&&Number.isFinite(x);
 const numeric=x=>number(x)||(typeof x==='string'&&x.trim()!==''&&Number.isFinite(Number(x)));
 const fnumber=x=>numeric(x)?Number(x):null;
 function lastObservation(spec,records=[]){
  if(!Array.isArray(records))return null;
  const ids=Array.isArray(spec.ids)&&spec.ids.length?spec.ids:[spec.id];
  for(const id of ids){
   const found=records.filter(x=>x?.id===id&&validMonth(x.date)&&numeric(x.value)).sort((a,b)=>a.date.localeCompare(b.date));
   if(found.length){const newest=found.at(-1),collisions=found.filter(x=>x.date===newest.date&&Number(x.value)!==Number(newest.value));
    return {sourceId:id,month:newest.date,value:Number(newest.value),unit:newest.unit||spec.unit||'',sourceCode:newest.sourceCode||'',savedAt:newest.retrievedAt||null,provider:newest.provider||spec.source||'',count:found.length,conflicting:collisions.length>0};
   }
  }
  return null;
 }
 function evidence(specs,records,status,online){
  const runs=Array.isArray(status?.latestRuns)?status.latestRuns:[];
  const estimates=Array.isArray(status?.estimates)?status.estimates:[];
  return specs.map(sp=>{
   const last=lastObservation(sp,records);
   const ids=Array.isArray(sp.ids)&&sp.ids.length?sp.ids:[sp.id];
   const run=runs.find(x=>x.id===last?.sourceId)||runs.find(x=>ids.includes(x.id))||null;
   const estimate=estimates.find(x=>x.id===last?.sourceId)||estimates.find(x=>ids.includes(x.id))||null;
   const issues=[];
   if(!online)issues.push('공개 원장 연결 미확인');
   if(!last)issues.push('실측자료 없음');
   if(last?.conflicting)issues.push('동일 통계월의 값 불일치');
   if(estimate?.stale)issues.push('최신성 점검 필요');
   if(run?.status==='failed')issues.push('최근 API 점검 실패');
   // A changed observation may have been saved months after the source publication.
   // A successful latestRuns entry is not a history of every monthly scheduled run.
   return {id:sp.id,label:sp.label,source:sp.source||'',last,run:{status:run?.status||null,finishedAt:run?.finishedAt||null},
     estimate:{status:estimate?.status||null,month:estimate?.lastMonth||null,value:fnumber(estimate?.value),source:estimate?.source||estimate?.formula||null},
     issues,stored:!!last,verified:!!last&&online&&!issues.length,monthlyRunProven:false,officialApplied:false};
  });
 }
 function reviewWindow(today,anchor=BASIS){
  if(!validMonth(today)||!validMonth(anchor))throw Error('오늘·공식 계획 기준월 형식 오류');
  const delta=mindex(today)-mindex(anchor),n=delta<6?0:Math.floor(delta/6),due=n>0;
  return {basis:anchor,today,firstReview:shifted(anchor,6),due,latestDue:due?shifted(anchor,n*6):null,
    nextReview:shifted(anchor,(n+1)*6),reviewCompleted:false,customerEvidenceVerified:false,fullRecalculationCompleted:false,officialApprovalEnabled:false,
    label:due?'점검 대상 월 도래 · 완료 여부 별도 확인':'다음 정기 검토 전'};
 }
 function finiteDelta(after,before){return number(after)&&number(before)?Math.round(after-before):null;}
 function domainSteps(id,projection){
  const p=projection?.ready?projection:null,env=p?.environment||{},fin=p?.finance?.finance||{},goals=p?.goals||{},row=p?.monthlyResults?.[p.asOf]||{};
  // finance is the parent output of estimateFunds, goals may be overridden only in the tested projection.
  // Do not report a complete result if the engine is absent or the domain explicitly blocked.
  const blocked=id==='house'?!!env.homeBlocked:id==='car'?!!env.carBlocked:id==='travel'?!!env.travelBlocked:false;
  let values=[];
  const add=(label,value,unit='',basis='시험 추정치')=>{if(number(value))values.push({label,value,unit,basis});};
  if(id==='house'){
   add('신규 주택 예상가격',fin.homePrice,'원');add('이사 필요 자기자금',fin.own,'원');
   add('신규 주담대 예상 월 상환',fin.homeMonthly,'원');add('주택 목적저축 월액',goals.house?.newSaving,'원');
  } else if(id==='general'){
   add('물가 보정배율',p?.cpi?.correction,'배');
   add('검토월 생활비 시험액',row.previewExpense,'원');add('검토월 일반현금 변화',finiteDelta(row.previewCash,row.baselineCash),'원');
  }else if(id==='car'){
   add('차량 교체 예상가격',fin.carPrice,'원');add('자동차 할부 예상 월 상환',fin.carMonthly,'원');add('자동차 목적저축 월액',goals.car?.newSaving,'원');
  }else if(id==='travel'){
   add('해외여행 예상경비',fin.tripPrice,'원');add('해외여행 목적저축 월액',goals.travel?.newSaving,'원');
  }
  if(blocked)values=[]; // never show frozen fallback as a newly verified domain calculation.
  return {blocked,partial:!!p&&!blocked,values,reason:!p?(projection?.reason||'6개월 재계산 미리보기 준비 전'):blocked?(env[`${id==='house'?'home':id}Warning`]||'공식 지표 계열 검증 보류'):
    '조건부 6개월/은퇴 전 부분 계산이며 전생애 공식 갱신 아님',
    sourceDescription:id==='house'?`${env.homeGrowth?.source||'지역 지수 자료 없음'} · ${env.mortgage?.source||'주담대 기준 유지'}`:
      id==='general'?p?.cpi?.source||'고객 입력/기존 CPI 기준':id==='car'?env.car?.source||'차량 CPI 기준 유지':env.travel?.source||'여행 CPI 기준 유지'};
 }
 function build({specs=[],records=[],status={},online=false,nowMonth=BASIS,asOf=BASIS,projection=null,review=null,ledgerCheck=null}={}){
  if(!Array.isArray(specs)||!Array.isArray(records))throw Error('관측원장 배열 형식 오류');
  const sources=evidence(specs,records,status,online);
  const window=reviewWindow(nowMonth);
  const futureScenario=validMonth(asOf)&&asOf>nowMonth;
  const domains=AREAS.map(d=>{
    const needed=SOURCE[d.id].map(id=>sources.find(x=>x.id===id)).filter(Boolean);
    const missing=SOURCE[d.id].filter(id=>!sources.some(x=>x.id===id&&x.stored));
    const stages=domainSteps(d.id,projection);
    return {...d,sourceIds:[...SOURCE[d.id]],records:needed.map(x=>({id:x.id,label:x.label,month:x.last?.month||null,sourceId:x.last?.sourceId||null,runStatus:x.run.status,issues:x.issues})),
      missing,stages,status:stages.blocked?'해당 분야 계산 보류':!stages.partial?'계산 검토 대기':missing.length?'기존 가정 포함 · 부분 시험':'관측자료 보유 · 부분 시험',officialApplied:false};
  });
  return {version:'V51-4',plan:{basis:BASIS,appliedObservationMonthsVerified:false,appliedOn:null,approvedNewVersion:false},
    nowMonth,asOf,window,futureScenario,sources,storedCount:sources.filter(x=>x.stored).length,total:sources.length,
    monthlyHistory:{runHistoryComplete:false,lastRunDetailsAvailable:sources.some(x=>!!x.run.finishedAt),
      note:'관측값의 저장시각 및 최근 API 점검시각은 조회할 수 있으나, 모든 월의 예약 실행·성공 이력은 공개 스냅샷만으로 입증할 수 없음'},
    domains,steps:['공식 지표 월별 관측·이력 확인','6개월 검토 예정월·고객 실적 확인','분야별 부분 시험·605개월 정합성 대조','검증 완료 후 별도 고객 공식 승인 절차'],
    ledger:{checked:ledgerCheck?.ready===true,months:ledgerCheck?.months||0,unchanged:true},
    preparedForFullReplan:false,officialApplied:false,customerApproved:false,approvalButtonEnabled:false,
    previewReady:!!review?.ready,exclusions:['605개월 전면 자동 재설계 미구현','고객 본인확인·실적 증빙 미검증','새 공식 원장 승인/쓰기 미구현','Actions 월별 실행 일정 변경 미확인']};
 }
 return Object.freeze({BASIS,SOURCE,AREAS,shifted,lastObservation,evidence,reviewWindow,domainSteps,build});
});
