/* IFPK V51.1: verified, read-only six-area re-planning preview.
 * This module deliberately NEVER commits changes to an official financial plan.
 * Inputs are the existing 605-month workbook snapshot, the verified partial
 * V49 housing impact and public-series basis metadata.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V51_REPLAN=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const START='2026-11', END='2077-03', MOVE='2046-10', RETIRE='2056-04', EXPECTED=605;
 const MONTH_RATE=0.026289/12; // existing fixed purpose-saving rate, not a new live-rate assumption
 const AREAS=Object.freeze([
   {id:'retirement',name:'은퇴설계',why:'국민연금·DC·IRP·인출·건강보험료를 포함한 은퇴자산 전체 재계산이 필요합니다.'},
   {id:'housing',name:'부동산설계',why:'검증된 주택 영향분석을 이용해 이사 전 저축·월별 일반현금 영향만 우선 시험합니다.'},
   {id:'consumption',name:'일반소비설계',why:'연 2.5% 소비물가 가정은 공식 고객계획에서 유지합니다. 새 CPI를 자동으로 2.5% 대신 쓰지 않습니다.'},
   {id:'childcare',name:'자녀양육설계',why:'성장단계·정부지원·교육비의 전체 월별 재계산 연결이 필요합니다.'},
   {id:'car',name:'자동차 교체설계',why:'자동차 CPI·매각 잔가율·차량 대출·적립액을 일관되게 재산출해야 합니다.'},
   {id:'travel',name:'해외여행설계',why:'해외여행 CPI 12개월 평균·미래 물가 가정·적립액을 연결해야 합니다.'}
 ]);
 const numeric=x=>typeof x==='number'&&Number.isFinite(x);
 const round=n=>Math.round(n);
 const nextMonth=s=>{const a=s.split('-').map(Number);return a[1]===12?`${a[0]+1}-01`:`${a[0]}-${String(a[1]+1).padStart(2,'0')}`;};
 function parseRow(x){
   if(!Array.isArray(x)||x.length<19||!x.slice(0,19).every(numeric))return null;
   return {income:x[0],pension:x[1],expense:x[2],homeEvent:x[3],carEvent:x[4],tripEvent:x[5],net:x[6],retSave:x[7],houseSave:x[8],carSave:x[9],travelSave:x[10],houseBal:x[11],carBal:x[12],travelBal:x[13],eventTransfer:x[14],retDraw:x[15],cash:x[16],purpose:x[17],shortfall:x[18]};
 }
 function inspectLedger(snapshot){
   if(!snapshot||typeof snapshot!=='object')return {ready:false,reason:'월별 원장이 없습니다.',months:0};
   const months=Object.keys(snapshot).sort();
   if(months.length!==EXPECTED||months[0]!==START||months.at(-1)!==END)return {ready:false,reason:`${EXPECTED}개월의 ${START}~${END} 원장이 필요합니다.`,months:months.length};
   let previous=null, expected=START, maxCashMismatch=0, maxNetMismatch=0, invalid=[];
   for(const month of months){
     if(month!==expected){invalid.push(month+' 월 누락/중복');break;}
     expected=nextMonth(month);
     const row=parseRow(snapshot[month]);if(!row){invalid.push(month+' 자료 오류');break;}
     const netExpected=row.income-row.expense-row.homeEvent-row.carEvent-row.tripEvent;
     maxNetMismatch=Math.max(maxNetMismatch,Math.abs(netExpected-row.net));
     const cashExpected=(previous===null?0:previous)+row.net-row.retSave-row.houseSave-row.carSave-row.travelSave+row.eventTransfer+row.retDraw;
     maxCashMismatch=Math.max(maxCashMismatch,Math.abs(cashExpected-row.cash));
     previous=row.cash;
   }
   if(invalid.length)return {ready:false,reason:invalid[0],months:months.length};
   // Workbook rounds different components to KRW. Permit <= 2 won/month of rounding.
   if(maxCashMismatch>2||maxNetMismatch>2)return {ready:false,reason:'기존 월별 현금흐름의 수입·지출 또는 누적 현금 검산이 일치하지 않습니다.',months:months.length,maxCashMismatch,maxNetMismatch};
   return {ready:true,months:months.length,firstMonth:months[0],lastMonth:months.at(-1),maxCashMismatch,maxNetMismatch};
 }
 function inspectIndexBases(records,ids){
   const all=Array.isArray(records)?records:[];
   const result=[];
   for(const [key,aliases] of Object.entries(ids||{})){
     const used=all.filter(r=>aliases.includes(r.id) && numeric(Number(r.value)));
     const units=[...new Set(used.map(r=>String(r.unit||'미표시').trim()))];
     const sourceIds=[...new Set(used.map(r=>String(r.id||'')))];
     const homogenous=units.length<=1&&sourceIds.length<=1;
     result.push({id:key,ready:used.length>0&&homogenous,available:used.length>0,unit:units[0]||null,units,sourceIds,count:used.length,reason:used.length===0?'공식 수집자료 없음':homogenous?'동일 기준 자료 확인':'기준년·계열 식별자가 섞여 있습니다. 동일 기준으로 환산 전에는 재계산하지 않습니다.'});
   }
   return result;
 }
 function simulateHousing(snapshot,preview,opts={}){
   const source=inspectLedger(snapshot);
   if(!source.ready)return {ready:false,reason:source.reason,ledgerCheck:source};
   if(!preview?.ready||!preview.verified)return {ready:false,reason:'검증된 주택설계 변경 전후 비교자료가 없습니다.',ledgerCheck:source};
   const before=preview.before||{},after=preview.after||{};
   for(const k of ['monthlySaving','monthlyLoanPayment','ownCashGoal']){
     if(!numeric(before[k])||!numeric(after[k]))return {ready:false,reason:`주택 비교자료 ${k}가 유효하지 않습니다.`,ledgerCheck:source};
   }
   const move=opts.move||MOVE;const rate=opts.monthlyRate===undefined?MONTH_RATE:Number(opts.monthlyRate);
   if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(move)||move<=START||move>=RETIRE||!numeric(rate)||rate<0||rate>.05)return {ready:false,reason:'주택 이사일 또는 적립금 수익률 조건이 올바르지 않습니다.',ledgerCheck:source};
   if(round(before.monthlySaving)!==parseRow(snapshot[START]).houseSave||round(before.ownCashGoal)!==parseRow(snapshot[move]).homeEvent){
     return {ready:false,reason:'주택 비교자료의 기준값이 월별 공식 원장과 다릅니다. 동일한 공식계획 기준으로만 시험할 수 있습니다.',ledgerCheck:source};
   }
   const deltaSave=round(after.monthlySaving-before.monthlySaving),deltaLoan=round(after.monthlyLoanPayment-before.monthlyLoanPayment),deltaEvent=round(after.ownCashGoal-before.ownCashGoal);
   let cashDelta=0,houseFundExtra=0,maxMonthlyNeed=0,firstCashDeficit=null,deficitCount=0,baseDeficitCount=0,impactedMonths=0;
   const projected={};const sampleKeys=new Set([START,'2027-05','2034-10','2038-10',nextMonth(MOVE),move,'2056-03','2056-04',END]);
   const samples=[];
   for(const month of Object.keys(snapshot).sort()){
     const base=parseRow(snapshot[month]);
     const preRetire=month<RETIRE;
     const extraSave=(month<move&&preRetire)?deltaSave:0;
     const extraLoan=(month>=move&&preRetire)?deltaLoan:0;
     const extraEvent=month===move?deltaEvent:0;
     // An externally funded housing event moves money from purpose savings to housing;
     // its event expense and event transfer cancel in the general-cash account.
     const extraHouseBalance=round(houseFundExtra*(1+rate)+extraSave-extraEvent);
     houseFundExtra=extraHouseBalance;
     cashDelta-=extraSave+extraLoan;
     const updated={...base,
       expense:base.expense+extraLoan,
       homeEvent:base.homeEvent+extraEvent,
       net:base.net-extraLoan-extraEvent,
       eventTransfer:base.eventTransfer+extraEvent,
       houseSave:base.houseSave+extraSave,
       houseBal:base.houseBal+houseFundExtra,
       purpose:base.purpose+houseFundExtra,
       cash:base.cash+cashDelta,
       shortfall:Math.max(0,-round(base.cash+cashDelta)),
     };
     if(updated.houseBal<0){return {ready:false,reason:`${month}의 주택목적 적립금이 부족합니다. 변경 저축액만으로 부족액을 충당할 수 없습니다.`,ledgerCheck:source};}
     const expCash=round(base.cash+cashDelta);
     if(Math.abs(updated.cash-expCash)>2)return {ready:false,reason:'일반현금 월별 누적값 불일치',ledgerCheck:source};
     projected[month]=updated;
     if(extraSave||extraLoan||extraEvent)impactedMonths++;
     if(preRetire){
       if(base.cash<0)baseDeficitCount++;
       if(updated.cash<0){deficitCount++;firstCashDeficit ||= month;}
       maxMonthlyNeed=Math.max(maxMonthlyNeed,-updated.cash);
     }
     if(sampleKeys.has(month))samples.push({month,beforeCash:base.cash,afterCash:updated.cash,beforeSaving:base.houseSave,afterSaving:updated.houseSave,beforeHouseBalance:base.houseBal,afterHouseBalance:updated.houseBal});
   }
   const final=projected[END],baseFinal=parseRow(snapshot[END]);
   return {ready:true,partial:true,scope:'주택 부분 변경 시 일반현금·주택목적 잔액에 한정한 시험 계산',ledgerCheck:source,months:source.months,
     inputs:{move,deltaSave,deltaLoan,deltaEvent,monthlyRate:rate},
     changedMonthCount:impactedMonths,firstCashDeficit,baseDeficitCount,deficitCount,maxDeficit:maxMonthlyNeed,
     finalCash:final.cash,baselineFinalCash:baseFinal.cash,finalCashDelta:final.cash-baseFinal.cash,
     residualHouseFundAtMove:projected[move].houseBal,
     projected,examples:samples};
 }
 function buildAreaReports(preview,house){
   return AREAS.map(area=>{
     if(area.id==='housing')return {...area,status:house?.ready?'partial':'pending',label:house?.ready?'월별 일반현금 영향 시험 완료':'주택 부분 비교 대기',details:house?.ready?`${house.months}개월 원장 무결성 확인 · ${house.changedMonthCount}개월에 저축·상환·이사 이벤트 변경 발생 · 은퇴자산 전체 재계산은 아직 미완료`:house?.reason||area.why};
     if(area.id==='consumption')return {...area,status:'fixed',label:'기존 연 2.5% 가정 유지',details:area.why};
     return {...area,status:'pending',label:'통합 계산 연결 전',details:area.why};
   });
 }
 function readiness(summary){
   const areas=buildAreaReports(summary?.preview,summary?.house);
   const blockers=[];
   if(!summary?.ledger?.ready)blockers.push('605개월 공식 기준 원장 검증 실패');
   if(!summary?.house?.ready)blockers.push('주택 월별 영향 시험 미완료');
   for(const a of areas){if(!['ready','verified'].includes(a.status))blockers.push(`${a.name}: ${a.label}`);}
   blockers.push('월별 은퇴자산·DC·연금·건보료 재계산 및 목표별 자금잔액 통합 대조 미완료');
   return {mayApprove:false,stage:'통합 미리보기 · 공식 적용 불가',blockers,areas};
 }
 function buildReview(snapshot,preview,records){
   const ledger=inspectLedger(snapshot);
   const indexBases=inspectIndexBases(records,{
     HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606:['HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606'],
     CPI_GENERAL:['CPI_GENERAL'],CPI_CAR:['CPI_CAR'],CPI_TRAVEL:['CPI_TRAVEL']
   });
   const mixed=indexBases.filter(x=>x.available&&!x.ready);
   const house=mixed.length?{ready:false,reason:'일부 지표에 서로 다른 기준시점이 혼합되었습니다. '+mixed.map(x=>x.id).join(', '),ledgerCheck:ledger}:simulateHousing(snapshot,preview);
   const report={ledger,indexBases,house,preview};
   return {...report,approval:readiness(report)};
 }
 return Object.freeze({START,END,EXPECTED,RETIRE,AREAS,MONTH_RATE,inspectLedger,inspectIndexBases,simulateHousing,buildAreaReports,readiness,buildReview});
});
