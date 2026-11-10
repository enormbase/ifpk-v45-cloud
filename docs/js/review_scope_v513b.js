/* IFPK V51-3b — explicit API-update scope and conditional retirement cashflow bridge.
 * Original plan assumptions are NOT re-estimated by incoming public API data.
 * No user approval, no online identity, no official spreadsheet or asset mutation.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V513B=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const START='2056-04',END='2077-03',FIRST='2046-11',LAST='2076-10';
 const RATE=.04,INFLATION=.025,WAGE=.025;
 const DEPARTMENTS=Object.freeze([
  {id:'house',label:'주택',sources:'R-ONE 주택가격지수 · ECOS 주담대·예적금 금리',uses:'주택 미래가격·목적저축·신규대출 원리금'},
  {id:'general',label:'일반소비',sources:'KOSIS 일반 소비자물가지수',uses:'은퇴 전 일반생활비·일반현금'},
  {id:'car',label:'자동차',sources:'품목 CPI (차량 잔가율표는 저장된 기준값 참고)',uses:'교체가격·목적저축·자동차할부'},
  {id:'travel',label:'해외여행',sources:'KOSIS 해외단체여행비 CPI',uses:'여행예산·목적저축'}
 ]);
 const fixed=Object.freeze({wageAnnual:WAGE,retirementInflationAnnual:INFLATION,retirementReturnAnnual:RATE,pensionApiRoll:false,dcApiRoll:false,irpApiRoll:false,postRetirementTdfRoll:false});
 const month=(s,n)=>{const z=s.split('-').map(Number),i=z[0]*12+z[1]-1+n;return `${Math.floor(i/12)}-${String(i%12+1).padStart(2,'0')}`};
 const val=x=>typeof x==='number'&&Number.isFinite(x);
 const finite=x=>Number.isFinite(Number(x))&&x!==null&&x!=='';
 const has=x=>x!==undefined&&x!==null&&String(x).trim()!=='';
 function classification(preview,inputs={}){
  if(!preview?.ready||!preview.finance)return {ready:false,reason:'4개 분야의 경제지표 및 주택 상환모형 계산을 확인해야 합니다.'};
  const env=preview.environment||{},finance=preview.finance;
  const whole={house:Boolean((env.homeGrowth?.updated||env.mortgage?.updated||env.homeActual?.ready||env.deposit?.updated||has(inputs.mortgageRate)||has(inputs.homeGrowth)||has(inputs.houseGoal)||has(inputs.house)||inputs.borrowingCase&&inputs.borrowingCase!=='base')&&!env.homeBlocked),
  general:Boolean(preview.cpi?.correction&&Math.abs(preview.cpi.correction-1)>1e-9||has(inputs.hypotheticalCPI)||has(inputs.actualSpending)),
  car:Boolean(env.car?.ready||has(inputs.carMA3)||has(inputs.car)),
  travel:Boolean(env.travel?.ready||has(inputs.travelMA12)||has(inputs.travel))};
  const categories=DEPARTMENTS.map(d=>({...d,hasNewInput:!!whole[d.id],blocked:d.id==='house'?!!env.homeBlocked:d.id==='car'?!!env.carBlocked:d.id==='travel'?!!env.travelBlocked:false}));
  const asOf=preview.asOf||'';
  const activeHome=asOf&&asOf<'2046-10'&&!env.homeBlocked;
  const before=Number(finance.homeMonthlyBefore),after=Number(finance.homeMonthly),monthlyDelta=Math.round(after-before);
  const mortgageImpact=!!activeHome&&val(before)&&val(after)&&Math.abs(monthlyDelta)>=1;
  const accountInput=has(inputs.retirementAssets)||has(inputs.mortgageOutstanding)||has(inputs.fundsAggregate);
  const customerChange=Object.freeze({retirementAssetsEntered:has(inputs.retirementAssets),mortgageOutstandingEntered:has(inputs.mortgageOutstanding),incomeEntered:has(inputs.monthlyIncome),additionalDebtEntered:has(inputs.additionalDebt),any:accountInput||has(inputs.monthlyIncome)||has(inputs.additionalDebt)||has(inputs.liquidCash)});
  const triggers=[];
  if(mortgageImpact)triggers.push('신규 주담대 상환액 변화 → 은퇴 후 월 인출·잔액에 직접 영향');
  if(customerChange.retirementAssetsEntered)triggers.push('은퇴 금융자산 실잔액 입력 → DC·IRP 포함/세후여부 확인 후 별도 검증');
  return {ready:true,categories,staticRetirement:fixed,retirement:{model:'fixed-by-design',apiReestimate:false,pensionReestimate:false,dcReestimate:false,irpReestimate:false,retirementCpiReestimate:false,triggeredByMortgage:mortgageImpact,triggeredByVerifiedAccount:false,accountEvidenceNeeded:customerChange.retirementAssetsEntered,deltaMortgage:monthlyDelta,baselineMortgage:Math.round(before),trialMortgage:Math.round(after),triggers},customerChange,officialApply:false,comments:['API 연동은 주택·일반소비·자동차·해외여행 4개 분야에만 적용','임금 2.5%·은퇴생활비 물가 2.5%·은퇴 후 운용수익률 4%는 모델 고정 가정','국민연금·DC·IRP는 공개 API 발표만으로 재산정하지 않음','주택 신규 상환액이 바뀌면 은퇴 후 인출 현금흐름에 직접 영향분만 분리하여 참고 계산']};
 }
 function mortgageRetirement(snapshot,metrics,scope){
  if(!scope?.ready||!scope.retirement)return {ready:false,reason:'갱신 대상 분류가 필요합니다.'};
  const r=scope.retirement;
  if(!r.triggeredByMortgage)return {ready:true,changed:false,reason:'신규 주담대 월 원리금 변동 없음 — 은퇴계획 기준값 유지',baselineFinal:Number(metrics?.finalRetirement),trialFinal:Number(metrics?.finalRetirement),deltaFinal:0,affectedMonths:0,retirementAnnualInflation:INFLATION,retirementAnnualReturn:RATE,official:false};
  const keys=Object.keys(snapshot||{}).sort();
  if(keys.length!==252||keys[0]!==START||keys.at(-1)!==END||keys.some((k,i)=>k!==month(START,i)))return {ready:false,reason:'은퇴 후 252개월 자료 누락·순서 오류'};
  if(!val(metrics?.finalRetirement)||!val(r.deltaMortgage)||Math.abs(r.deltaMortgage)>1e8)return {ready:false,reason:'새 상환액 또는 기준 은퇴자산값 검증 실패'};
  const rate=Math.pow(1+RATE,1/12)-1;
  let growthEffect=0,deltaNeededPV=0,affected=0,extraRequired=0;
  const examples=[];
  for(let i=0;i<252;i++){
   const date=keys[i],base=snapshot[date];
   if(!base||![base.living,base.pension,base.insurance,base.withdraw,base.balance].every(val))return {ready:false,reason:`${date} 은퇴 월별 지출·잔액 오류`};
   const active=date>=START&&date<=LAST;
   const delta=active?r.deltaMortgage:0;
   const baselineNeed=Math.max(0,base.living+base.insurance-base.pension);
   const trialNeed=Math.max(0,base.living+delta+base.insurance-base.pension);
   // Preserve pension/insurance and only add the mortgage change to the living-cost component.
   const deltaDraw=trialNeed-baselineNeed;
   deltaNeededPV+=deltaDraw/Math.pow(1+rate,i);
   growthEffect=growthEffect*(1+rate)+deltaDraw;
   if(delta!==0)affected++;
   const rawBalance=base.balance-growthEffect;
   if(rawBalance<0)extraRequired=Math.max(extraRequired,-rawBalance);
   if(i===0||date==='2076-10'||date==='2076-11'||date===END)examples.push({month:date,baseWithdrawal:Math.round(base.withdraw),trialWithdrawal:Math.round(trialNeed),baseBalance:Math.round(base.balance),trialBalance:Math.max(0,Math.round(rawBalance)),monthlyMortgageChange:delta});
  }
  const originalEnd=Math.round(metrics.finalRetirement),proposedEnd=Math.max(0,Math.round(snapshot[END].balance-growthEffect));
  return {ready:true,changed:true,official:false,scope:'신규 주담대 상환 차이만 은퇴 후 인출액에 적용한 조건부 영향 시험',affectedMonths:affected,start:START,lastMortgagePayment:LAST,noPaymentFrom:'2076-11',monthlyMortgageChange:r.deltaMortgage,baselineFirstWithdrawal:Math.round(snapshot[START].withdraw),trialFirstWithdrawal:examples[0].trialWithdrawal,baselineFinal:originalEnd,trialFinal:proposedEnd,deltaFinal:proposedEnd-originalEnd,additionalRequiredCapitalAtRetirement:Math.round(deltaNeededPV),unfundedAlert:extraRequired>0,unfundedAtWorst:Math.round(extraRequired),retirementAnnualInflation:INFLATION,retirementAnnualReturn:RATE,examples};
 }
 // Review gate: selectively recalculate affected domains, never re-estimate fixed assumptions via API.
 function requiredChecks(scope){
  if(!scope?.ready)return {ready:false,reason:'분야별 변경 조건을 검증하지 못했습니다.'};
  return {ready:true,mandatory:[
    {id:'source',title:'변경된 4개 분야의 관측자료·가정 검증',required:true},
    {id:'linkedCash',title:'변경분의 소득·지출·월 목적저축·일반현금 연결 검증',required:true},
    {id:'mortgage',title:'은퇴 후 주담대 영향분만 추가 검증',required:scope.retirement.triggeredByMortgage},
    {id:'account',title:'고객 은퇴자산 변경·DC/IRP 포함 여부 및 세후 검증',required:scope.retirement.accountEvidenceNeeded},
    {id:'evidence',title:'월 부족액의 조달 가능성과 고객 입력 근거 확인',required:true},
    {id:'version',title:'고객 승인권한·공식 버전 기록/서버 저장',required:true}
  ],neverAutomatic:['국민연금 임의 재산정','DC·IRP 추정수익률 자동 변경','은퇴 후 생활비 CPI 실측치로 자동 교체'],officialApply:false};
 }
 return Object.freeze({classification,mortgageRetirement,requiredChecks,DEPARTMENTS,fixed,month});
});
