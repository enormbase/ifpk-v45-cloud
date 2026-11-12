/* V60 · Read-only explanation of the same V55 simulation values displayed to customers.
   Browser records stay local; no external write/approval path. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V60_TRACE=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const NAMES={CPI_GENERAL:'일반 소비자물가',CPI_CAR:'자동차 물가',CPI_TRAVEL:'해외여행 물가',DEPOSIT:'목적저축 예금금리',MORTGAGE:'신규 주담대 금리',HOME_PRICE:'대전 서구 주택가격'};
const USES={CPI_GENERAL:'일반생활비·양육비·은퇴 후 일부 생활비',CPI_CAR:'차량 교체 후 오토론 상환 가정',CPI_TRAVEL:'여행 목표 경비',DEPOSIT:'주택·차량·여행 목적저축 수익률',MORTGAGE:'이사 후 신규 주담대 상환 가정',HOME_PRICE:'이사 시 주택 자기자금 민감도'};
const COSTS=[['general','일반생활비','CPI_GENERAL'],['childcare','양육비','CPI_GENERAL'],['mortgage','주택담보대출','MORTGAGE'],['carLoan','차량 할부상환','CPI_CAR'],['insurance','별도 집계된 보험·건보료',null]];
const isReal=(o)=>o&&Number.isFinite(Number(o.value));
function status(source,sim,id){
 const d=source.display.find(x=>x.id===id),published=source.values[id];
 const actual=sim.economics.values[id];
 const used=!!(published&&Number.isFinite(actual)&&Math.abs(actual-Number(published.value))<1e-7);
 return {id,name:NAMES[id],use:USES[id],month:d?.month||'—',value:actual,source:d?.source||'2026.11 최초 설계 가정',seriesId:d?.seriesId||'',validated:used,changed:used&&!!sim.economics.changes.find(z=>z.id===id)};
}
function trace(snapshot,sim,date,source){
 const row=sim.byMonth[date];
 const items=Object.keys(NAMES).map(id=>status(source,sim,id));
 if(!row)return {date,items,parts:[],expenseDiff:0,expenseOverride:false,appliedCount:items.filter(x=>x.validated).length};
 const parts=COSTS.map(([id,name,indicator])=>({id,name,indicator,appliedLabel:id==='mortgage'&&date<'2046-11'?'이사 전 기존대출 · 새 금리 자동연동 없음':id==='carLoan'&&date<'2034-11'?'차량 구매 전 · 할부 없음':null,value:row.expenseParts?.[id]||0,base:row.baselineParts?.[id]||0,delta:(row.expenseParts?.[id]||0)-(row.baselineParts?.[id]||0),linked:!!indicator&&items.find(x=>x.id===indicator)?.validated}));
 return {date,items,parts,expenseDiff:parts.reduce((a,b)=>a+b.delta,0),expenseOverride:row.expenseOverride,appliedCount:items.filter(x=>x.validated).length};
}
function impacts(snapshot,sim,source,engine,params){
 // Compare actual projection against an otherwise identical simulation with one economic input rolled back.
 // Only the selected indicator is removed each time; preserves actual deposits and other indicators.
 const base=Object.fromEntries(Object.entries(source.values).filter(([id,v])=>!!v&&isReal(v)));
 const impacts={};
 const samples={CPI_GENERAL:'2026-12',CPI_CAR:'2035-01',CPI_TRAVEL:'2026-12',DEPOSIT:'2026-12',MORTGAGE:'2047-01',HOME_PRICE:'2026-12'};
 for(const id of Object.keys(NAMES)){
  if(!base[id]||!sim.economics.changes.find(x=>x.id===id)){impacts[id]={status:'기준값과 같음 또는 새 자료 없음',delta:0};continue;}
  const without={...base};delete without[id];
  const baseline=engine.simulate(snapshot,{...params,economics:without});
  const d=samples[id],row=sim.byMonth[d],other=baseline.byMonth[d];
  let now=0,previous=0,label='';
  if(id==='CPI_GENERAL'){now=row.expenseParts.general+row.expenseParts.childcare;previous=other.expenseParts.general+other.expenseParts.childcare;label='2026.12 일반소비+양육비';}
  if(id==='CPI_CAR'){now=row.expenseParts.carLoan;previous=other.expenseParts.carLoan;label='2035.01 자동차 할부';}
  if(id==='CPI_TRAVEL'){now=sim.byId.travel.total;previous=baseline.byId.travel.total;label='여행 목표경비';}
  if(id==='DEPOSIT'){now=row.required.home+row.required.car+row.required.travel;previous=other.required.home+other.required.car+other.required.travel;label='2026.12 월 필요저축 합계(은퇴 제외)';}
  if(id==='MORTGAGE'){now=row.expenseParts.mortgage;previous=other.expenseParts.mortgage;label='2047.01 주담대 상환';}
  if(id==='HOME_PRICE'){now=sim.byId.home.total;previous=baseline.byId.home.total;label='2046년 주택 자기자금 가정';}
  impacts[id]={status:'재계산 검증',delta:now-previous,label,now,previous};
 }
 return impacts;
}
return {NAMES,USES,COSTS,trace,impacts};
});