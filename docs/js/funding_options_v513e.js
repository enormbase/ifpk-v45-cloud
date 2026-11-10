/* V51-3e — combined household cash / goal funding *sensitivity*.
 * Uses immutable baseline only; never moves money between accounts, borrows,
 * invents income, or silently postpones a goal. Nominal fixed manual inputs.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V513E=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const FIRST='2026-11',RETIRE='2056-04',LAST='2077-03',RATE=.02628945/12;
const GOALS=Object.freeze({
 car:{label:'자동차 교체',date:'2034-10',expense:4,saving:9,balance:12},
 travel:{label:'해외여행',date:'2038-10',expense:5,saving:10,balance:13},
 house:{label:'주택 갈아타기',date:'2046-10',expense:3,saving:8,balance:11}
});
const shift=(date,n)=>{const [y,m]=date.split('-').map(Number),a=y*12+m-1+n;return Math.floor(a/12)+'-'+String(a%12+1).padStart(2,'0');};
const distance=(a,b)=>{const [y,m]=a.split('-').map(Number),[Y,M]=b.split('-').map(Number);return (Y-y)*12+M-m;};
const good=v=>typeof v==='number'&&Number.isFinite(v);
const ledgerOk=s=>{const k=Object.keys(s||{}).sort();return k.length===605&&k[0]===FIRST&&k.at(-1)===LAST&&k.every((d,i)=>d===shift(FIRST,i)&&Array.isArray(s[d])&&s[d].length===19&&s[d].every(good));};
const nonnegative=(value,limit)=>{if(value===''||value==null)return 0;const v=Number(value);return Number.isSafeInteger(v)&&v>=0&&v<=limit?v:null;};
const signed=(value,limit)=>{if(value===''||value==null)return 0;const v=Number(value);return Number.isSafeInteger(v)&&Math.abs(v)<=limit?v:null;};
function evaluate(snapshot,review,options={}){
 if(!ledgerOk(snapshot))return {ready:false,reason:'기준 605개월 원장 검증 실패'};
 if(!review?.ready||review.payload?.officialApplied!==false)return {ready:false,reason:'6개월 검토 원장이 없습니다.'};
 const {asOf,comparison}=review.payload;
 if(!/^\d{4}-(0[1-9]|1[0-2])$/.test(asOf)||asOf<FIRST||shift(asOf,5)>=RETIRE||!Array.isArray(comparison)||comparison.length!==6)return {ready:false,reason:'재설계월 또는 6개월 원장 오류'};
 const goalKey=String(options.goal||'car'),goal=GOALS[goalKey],cut=nonnegative(options.monthlyRelief,2000000),savingChange=signed(options.monthlyContributionChange,2000000),budgetCut=nonnegative(options.goalBudgetReduction,1000000000);
 const cutDuration=String(options.reliefDuration||'12'),savingDuration=String(options.savingDuration||'12');
 if(!goal||cut===null||savingChange===null||budgetCut===null||!['6','12','36','retirement'].includes(cutDuration)||!['6','12','36','goal'].includes(savingDuration))return {ready:false,reason:'조정 대상/금액/기간을 다시 확인해 주세요. 소비절감은 0~200만원, 월 적립변경은 ±200만원 정수입니다.'};
 if(asOf>=goal.date)return {ready:false,reason:`${goal.date} 목표월이 이미 지나 해당 목표를 다시 설계할 수 없습니다.`};
 const event=snapshot[goal.date],required=Math.round(event[goal.expense]),available=Math.round(event[goal.balance]+event[14]);
 if(required<=0||event[goal.balance]<0||Math.abs(event[14]-event[goal.expense])>2||budgetCut>required)return {ready:false,reason:'목적계좌 목표금/전입 또는 목표 축소액 검증 오류'};
 const left=distance(asOf,goal.date),monthsSaving=Math.min(left,savingDuration==='goal'?left:Number(savingDuration));
 const monthsCut=cutDuration==='retirement'?distance(asOf,RETIRE):Math.min(distance(asOf,RETIRE),Number(cutDuration));
 for(let i=0;i<monthsSaving;i++){const date=shift(asOf,i);if(snapshot[date][goal.saving]+savingChange<0)return {ready:false,reason:`${date} 목적저축 납입액이 0원 미만입니다. 감액을 줄여 주세요.`};}
 const diffByMonth=new Map();let opening=null,monthlyCarry=0;
 for(let i=0;i<6;i++){
  const d=shift(asOf,i),line=comparison[i];if(!line||line.month!==d||![line.plannedNet,line.testedNet,line.baselineCash,line.testedCash].every(good)||Math.abs(line.baselineCash-snapshot[d][16])>2)return {ready:false,reason:`${d} 6개월 비교원장 오류`};
  const diff=line.testedNet-line.plannedNet;diffByMonth.set(d,diff);monthlyCarry+=diff;
  const startOffset=line.testedCash-line.baselineCash-monthlyCarry;
  if(opening!==null&&Math.abs(startOffset-opening)>3)return {ready:false,reason:`${d} 비교원장 누적 차이 불일치`};
  if(opening===null)opening=startOffset;
 }
 let runningEngine=0,manualCash=0,negative=0,monthUnfunded=0,firstDeficit=null,worst=Infinity,worstMonth=null,at2039=null,endCash=null,monthlyTrial=[],sample=[];
 let reliefTotal=0,nominalGoalSaving=0,goalFvDiff=0,cutCount=0;
 const months=distance(FIRST,RETIRE),asOfIdx=distance(FIRST,asOf),sampleDates=new Set([asOf,shift(asOf,5),'2039-10',goal.date,'2056-03']);
 for(let i=0;i<months;i++){
  const date=shift(FIRST,i),r=snapshot[date],offset=i-asOfIdx;
  if(offset>=0){
   runningEngine+=diffByMonth.get(date)||0;
   if(offset<monthsCut){manualCash+=cut;reliefTotal+=cut;cutCount++;}
   if(offset<monthsSaving){manualCash-=savingChange;nominalGoalSaving+=savingChange;goalFvDiff+=savingChange*Math.pow(1+RATE,distance(date,goal.date));}
  }
  // Do not fabricate a transfer to general cash when goal budget is reduced.
  const delta=offset>=0?(opening||0)+runningEngine+manualCash:0;
  const cash=Math.round(r[16]+delta),base=Math.round(r[16]);
  const net=Math.round(r[6]-r[7]-r[8]-r[9]-r[10]+(offset>=0?(diffByMonth.get(date)||0)+(offset<monthsCut?cut:0)-(offset<monthsSaving?savingChange:0):0));
  if(offset>=0){
   if(cash<0){negative++;if(firstDeficit===null)firstDeficit=date;}
   if(net<0)monthUnfunded++;
   if(cash<worst){worst=cash;worstMonth=date;}
  }
  if(date==='2039-10')at2039={month:date,baseline:base,trial:cash,delta:cash-base};
  if(sampleDates.has(date))sample.push({month:date,baseline:base,trial:cash,delta:cash-base,monthlyNet:net});
  if(date==='2056-03')endCash=cash;
 }
 const amount=Math.round(available+goalFvDiff),newRequired=required-budgetCut,gap=Math.max(0,newRequired-amount),surplus=amount-newRequired;
 let annuityFactor=0;
 for(let i=0;i<left;i++)annuityFactor+=Math.pow(1+RATE,distance(shift(asOf,i),goal.date));
 const topUp=gap>0?Math.ceil(gap/annuityFactor):0;
 const baselineGoalSurplus=available-required;
 const baseMonthsAfter=Array.from({length:months-asOfIdx},(_,i)=>snapshot[shift(asOf,i)][16]);
 const baselineNegativeMonths=baseMonthsAfter.filter(v=>v<0).length;
 const baselineWorst=Math.round(Math.min(...baseMonthsAfter));
 return {ready:true,official:false,asOf,until:'2056-03',goal:goalKey,goalLabel:goal.label,goalDate:goal.date,
  sourceMonths:605,baseline:{required,available,surplus:baselineGoalSurplus,negativeMonthsAfterAsOf:baselineNegativeMonths,worstCashAfterAsOf:baselineWorst},
  inputs:{monthlyRelief:cut,reliefDuration:cutDuration,reliefMonths:cutCount,monthlyContributionChange:savingChange,savingDuration,savingMonths:monthsSaving,goalBudgetReduction:budgetCut},
  goalFunding:{required:newRequired,available:amount,fvDelta:Math.round(goalFvDiff),shortfall:gap,surplus,funded:surplus>=0,replenishmentPerMonth:topUp,replenishmentMonths:left,needBasis:'모델상 해당 목적계좌 부담액만 축소; 실제 차량·주택 가격/대출·여행 물가 재추정은 미수행'},
  liquidity:{sixMonthEngineCarry:Math.round((opening||0)+monthlyCarry),reliefTotal,nominalContributionDelta:nominalGoalSaving,manualCashDelta:reliefTotal-nominalGoalSaving,negativeMonthsAfterAsOf:negative,unfundedMonthsAfterAsOf:monthUnfunded,firstDeficit,worstCashAfterAsOf:worst,worstMonth,at2039,endCash,samples:sample},
  gates:{goalFunded:surplus>=0,noNegativeMonths:negative===0,monthlyAffordable:monthUnfunded===0,actualEvidence:false,officialReady:false},
  immutableBaseline:true,existingGoalUnchanged:true,otherGoalsUnchanged:true,retirementFixed:true,goalDeferralComputed:false,scenarioOnly:true,
  caveats:['이 조합 시험은 이전 V51-3c 소비절감액 및 V51-3d 추가 목적저축 변경액과 별개입니다. 동일한 조정을 중복 입력하지 마세요.',
   '목표자금 예산 축소는 해당 목적계좌 부담액만 낮춰 비교합니다. 차량할부·부동산 취득·대출규제·목표일 연기·일반현금으로의 송금은 계산하지 않았습니다.',
   '일반현금의 음수는 미조달 금액이며 계획상 목적계좌 잔액은 전액 납입의 조건부 전망입니다. 절감액을 목적통장으로 자동 옮기거나 부족액을 빌리지 않았습니다.',
   '은퇴설계 고정 가정, 국민연금/DC/IRP, 은퇴 후 252개월 및 공식 605개월 원장은 변경하지 않았습니다.']
 };
}
return Object.freeze({evaluate,GOALS,shift,distance,ledgerOk});
});
