/* IFPK V51-3a — customer review evidence; no official plan approval or mutation.
 * Static GitHub Pages cannot authenticate an approver or write to Google Sheets.
 * All decisions here are tentative local-browser records, exportable as JSON.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.IFPK_V513A=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const START='2026-11', END='2077-03', RETIRE='2056-04';
 const numeric=x=>typeof x==='number'&&Number.isFinite(x);
 const monthShift=(s,n)=>{const [y,m]=s.split('-').map(Number),v=y*12+m-1+n;return `${Math.floor(v/12)}-${String(v%12+1).padStart(2,'0')}`;};
 const integer=x=>Math.round(x);
 const expected=(snapshot)=>{
   if(!snapshot||typeof snapshot!=='object')return false;
   const keys=Object.keys(snapshot).sort();
   return keys.length===605&&keys[0]===START&&keys.at(-1)===END&&keys.every((k,i)=>k===monthShift(START,i)&&Array.isArray(snapshot[k])&&snapshot[k].length===19&&snapshot[k].every(numeric));
 };
 const stable=(x)=>{
   if(Array.isArray(x))return '['+x.map(stable).join(',')+']';
   if(x&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+stable(x[k])).join(',')+'}';
   return JSON.stringify(x);
 };
 // Consistency checksum only — NOT a digital signature, encryption or proof of identity.
 const checksum=(x)=>{const str=stable(x);let n=0x811c9dc5;for(let i=0;i<str.length;i++){n^=str.charCodeAt(i);n=Math.imul(n,0x01000193);}return (n>>>0).toString(16).padStart(8,'0');};
 function prepare(snapshot,checks,preview,afford,inputs={},audit=null,reference=null){
   if(!expected(snapshot)||!checks?.ready)return {ready:false,reason:'기준 605개월 원장의 정합성이 확인되지 않아 검토 기록을 만들 수 없습니다.'};
   if(!preview?.ready||!afford?.ready||afford.horizon!==6||!Array.isArray(afford.months)||afford.months.length!==6||!reference?.ready||reference.horizon!==6||reference.months?.length!==6)return {ready:false,reason:'6개월 롤링과 동일 엔진의 무변경 기준전망을 모두 계산해야 합니다.'};
   const asOf=preview.asOf;
   if(asOf!==afford.asOf||!/^\d{4}-(0[1-9]|1[0-2])$/.test(asOf)||asOf<START||monthShift(asOf,5)>=RETIRE)return {ready:false,reason:'재설계월 범위가 일치하지 않습니다.'};
   let baseSavings=0,baseNet=0,baseExpense=0,cashDelta=integer(afford.startingCash-reference.startingCash),trialSavingTotal=0,trialNetTotal=0;
   const comparison=[];
   for(let i=0;i<6;i++){
     const month=monthShift(asOf,i),row=snapshot[month],after=afford.months[i],neutral=reference.months[i];
     if(!row||!after||!neutral||after.month!==month||neutral.month!==month)return {ready:false,reason:`${month} 시나리오 6개월 연결 검증 실패`};
     const saving=row[7]+row[8]+row[9]+row[10];
     baseSavings+=saving;baseNet+=row[6]-saving;baseExpense+=row[2];
     const monthlyCashDelta=integer(after.monthlyAfterAll-neutral.monthlyAfterAll);
     const trialSaving=integer(saving+after.targetSaving-neutral.targetSaving);
     cashDelta+=monthlyCashDelta;
     const trialNet=integer(row[6]-saving+monthlyCashDelta);
     const testedCash=integer(row[16]+cashDelta);
     trialNetTotal+=trialNet;trialSavingTotal+=trialSaving;
     comparison.push({month,baselineCash:row[16],plannedNet:integer(row[6]-saving),testedCash,testedNet:trialNet,baseSaving:saving,trialSaving,unfunded:Math.max(0,trialSaving-(row[6]-saving+monthlyCashDelta+trialSaving))});
   }
   const end=monthShift(asOf,5),before=integer(snapshot[end][16]),after=integer(comparison.at(-1).testedCash),first=monthShift(asOf,-1);
   const historicalUnchanged=!!snapshot[first];
   const incomeInput=String(inputs.monthlyIncome??'').trim()!=='';
   const otherDebtInput=String(inputs.additionalDebt??'').trim()!=='';
   const extraRetirementInput=String(inputs.retirementAssets??'').trim()!=='';
   const changeFields=['hypotheticalCPI','actualSpending','house','car','travel','houseGoal','carMA3','travelMA12','depositRate','mortgageRate','homeGrowth','borrowingCase','monthlyIncome','additionalDebt','liquidCash','retirementAssets','mortgageOutstanding','fundsAggregate','retAssetOrigin','retAssetUsability'];
   const parameters=Object.fromEntries(changeFields.map(k=>[k,inputs[k]===undefined?'':String(inputs[k])]).filter(([k,v])=>v!==''&&v!=='unknown'&&(k!=='borrowingCase'||v!=='base')));
   const warnings=[];
   if(afford.unfundedMonths)warnings.push(`6개월 중 ${afford.unfundedMonths}개월에 월 소득만으로 목표저축을 충당할 수 없음`);
   const calibratedMaximumUnfunded=Math.max(0,...comparison.map(r=>-r.testedCash));
   if(calibratedMaximumUnfunded>0)warnings.push(`6개월 최대 누적 일반현금 미조달 ${integer(calibratedMaximumUnfunded)}원 (최신 시트 기준)`);
   if(checks.negativeCount)warnings.push(`기준계획 605개월 중 은퇴 전 일반현금 마이너스 ${checks.negativeCount}개월`);
   if(incomeInput||otherDebtInput)warnings.push('입력 소득·추가채무는 향후 6개월만 시험 적용, 장기 전체에는 미연결');
   if(extraRetirementInput)warnings.push('추가 은퇴자산은 별도성·세후 사용가능 증빙 전까지 공식 준비자산에 합산 금지');
   if(audit&&!audit.ready)warnings.push('장기 주담대·생활비 추가 검산 실패 또는 계산 보류');
   warnings.push('동일 롤링 엔진의 무변경 전망을 차감하여 시트 기준 605개월 원장에 6개월 순변화만 적용했습니다. 신 시나리오 공식 검산은 아닙니다.');
   warnings.push('은퇴설계는 임금·물가·수익률 고정 가정 유지, 국민연금·DC·IRP는 API로 자동 재추정하지 않음. 주담대 상환 변화의 은퇴 후 직접 영향은 별도 조건부 시험.');
   warnings.push('실제 거래·수입·고객 본인 확인·승인권한 및 구글시트 확정 기록은 검증되지 않음');
   const payload={schema:'ifpk-v51-3a-review',version:'V51-3a',asOf,horizonEnd:end,asOfBaselineCash:integer(snapshot[first][16]),lastBaselineCash:before,lastTrialCash:after,deltaCash:after-before,baselineSavings:baseSavings,trialSavings:trialSavingTotal,savingsDelta:trialSavingTotal-baseSavings,baseSixMonthNet:baseNet,trialSixMonthNet:trialNetTotal,baselineExpense:baseExpense,baselinePlanMonths:605,baselineNegativeMonths:checks.negativeCount,unfundedMonths:afford.unfundedMonths,trialMaximumUnfundedCash:calibratedMaximumUnfunded,parameters,comparison,warnings,calibratedToSheetBaseline:true,officialLedgerRecomputed:false,postRetirementRecomputed:false,customerIdentityVerified:false,officialApplied:false,historicalUnchanged};
   return {ready:true,payload,checksum:checksum(payload),reviewable:true,mayOfficiallyApply:false,reason:'변경안 일부 시험은 검토·의향 기록만 가능. 605개월 공식 적용 조건 미충족'};
 }
 const decisions={acknowledged:'검토 완료·공식 보류',revise:'보완 요청',defer:'판단 보류'};
 function decide(prepared,decision,ack={},note='',dateIso=''){
   if(!prepared?.ready||!prepared.payload||prepared.checksum!==checksum(prepared.payload))return {ok:false,reason:'검토 패킷이 없거나 계산 내용이 바뀌었습니다.'};
   if(!Object.hasOwn(decisions,decision))return {ok:false,reason:'선택한 검토 결과가 올바르지 않습니다.'};
   const cleaned=String(note||'').trim().slice(0,1000);
   if(decision==='acknowledged'&&!(ack.limits&&ack.funding&&ack.evidence))return {ok:false,reason:'공식 미적용·자금부족·증빙 미확인을 모두 확인해야 합니다.'};
   if(decision==='revise'&&!cleaned)return {ok:false,reason:'보완을 요청하는 이유를 입력해 주세요.'};
   const recordedAt=dateIso||new Date().toISOString();
   if(!/^\d{4}-\d{2}-\d{2}T/.test(recordedAt))return {ok:false,reason:'기록시각 확인 필요'};
   const record={schema:'ifpk-v51-3a-local-decision',id:`IFPK-${recordedAt.replace(/[^0-9]/g,'').slice(0,14)}-${prepared.checksum}`,recordedAt,decision,label:decisions[decision],note:cleaned,acknowledgements:{limits:!!ack.limits,funding:!!ack.funding,evidence:!!ack.evidence},reviewChecksum:prepared.checksum,review:JSON.parse(JSON.stringify(prepared.payload)),officialApproved:false,officialApplied:false,cloudSaved:false,authenticated:false,source:'이 브라우저의 검토 결정 기록 · 외부 검증 미완료'};
   return {ok:true,record:{...record,integrityCheck:checksum(record)}};
 }
 function verifyRecord(record){if(!record||record.schema!=='ifpk-v51-3a-local-decision'||record.officialApplied!==false||record.officialApproved!==false||record.cloudSaved!==false)return false;const {integrityCheck,...rest}=record;return typeof integrityCheck==='string'&&integrityCheck===checksum(rest)&&checksum(record.review)===record.reviewChecksum;}
 function exportArchive(records){if(!Array.isArray(records)||records.some(r=>!verifyRecord(r)))return {ok:false,reason:'기록 무결성이 확인되지 않았습니다. 파일 내보내기를 보류합니다.'};return {ok:true,data:JSON.stringify({schema:'ifpk-v51-3a-local-archive',exportedAt:new Date().toISOString(),warning:'사용자 브라우저 보관 이력입니다. 공식 고객 승인·전자서명·구글시트 변경이 아닙니다.',records},null,2)};}
 return Object.freeze({prepare,decide,verifyRecord,exportArchive,checksum,monthShift,decisions});
});
