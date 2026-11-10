/* V51-2k — Read-only audit of the exported authoritative Sheet snapshot. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V512K=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const START='2026-11', END='2077-03', RETIRE='2056-04', LAST='2076-10', ZERO='2076-11';
 const monthShift=(s,n)=>{const [y,m]=s.split('-').map(Number),v=y*12+m-1+n;return `${Math.floor(v/12)}-${String(v%12+1).padStart(2,'0')}`;};
 const okNum=x=>typeof x==='number'&&Number.isFinite(x);
 function audit(monthly,retire,annual,mortgage){
  const keys=Object.keys(monthly||{}).sort();let netMax=0,cashMax=0,purposeMax=0,deficitMax=0,drawMax=0,retireMax=0,mortgageMax=0;const problems=[];let prev=0,negativeCount=0,firstNegative=null,worst=0,worstMonth=null,preCount=0,retireMonths=0;
  if(keys.length!==605||keys[0]!==START||keys.at(-1)!==END)problems.push('전체 605개월 기간 누락');
  for(let i=0;i<keys.length;i++){
   const dt=keys[i],r=monthly[dt];if(dt!==monthShift(START,i)){problems.push(dt+' 달력 누락');break;}
   if(!Array.isArray(r)||r.length!==19||!r.every(okNum)){problems.push(dt+' 금액 형식 오류');break;}
   const net=r[0]+r[1]-r[2]-r[3]-r[4]-r[5],cash=prev+r[6]-r[7]-r[8]-r[9]-r[10]+r[14]+r[15];
   netMax=Math.max(netMax,Math.abs(net-r[6]));cashMax=Math.max(cashMax,Math.abs(cash-r[16]));
   purposeMax=Math.max(purposeMax,Math.abs(r[11]+r[12]+r[13]-r[17]));deficitMax=Math.max(deficitMax,Math.abs(Math.max(0,-r[16])-r[18]));
   if(dt<RETIRE){preCount++;if(r[16]<0){negativeCount++;firstNegative ||= dt;if(worstMonth===null||r[16]<worst){worst=r[16];worstMonth=dt;}}}
   else{
    retireMonths++;
    const v=retire?.[dt];if(!v){problems.push(dt+' 은퇴 인출 누락');break;}
    retireMax=Math.max(retireMax,Math.abs((v.living+v.insurance)-r[2]),Math.abs(v.pension-r[1]),Math.abs(v.withdraw-r[15]));
    if(r[0]!==0){problems.push(dt+' 국민연금이 근로소득에 중복 포함');break;}
   }
   if(mortgage){const due=mortgage[dt];if(!okNum(due)){problems.push(dt+' 주담대 납부월 증빙 누락');break;}if(dt==='2046-10'||dt==='2076-11')mortgageMax=Math.max(mortgageMax,Math.abs(due));}
   prev=r[16];
  }
  const m=mortgage||{};
  const installmentValid=m['2046-10']===0&&m['2046-11']===1675319&&m[LAST]===1675319&&m[ZERO]===0;
  if(!installmentValid)problems.push('신규 주담대 첫 납부/최종 납부월 불일치');
  if(!Array.isArray(annual)||annual.length!==52||annual[0]?.[0]!==2026||annual.at(-1)?.[0]!==2077)problems.push('연도별 52개 연말값 누락');
  if(netMax>2||cashMax>2||purposeMax>2||deficitMax>2||retireMax>2||mortgageMax>2)problems.push('월별 시트 산식과 자료의 오차가 2원을 넘습니다.');
  const checks=[['605개월·조회월·월별 재무원장',keys.length===605&&problems.filter(p=>/기간 누락|달력 누락|금액 형식/.test(p)).length===0],['수입·지출·저축·월말 일반현금',netMax<=2&&cashMax<=2],['주택·자동차·여행 목적잔액/누적 부족액',purposeMax<=2&&deficitMax<=2],['은퇴 252개월 연금·건보·실제 인출액',retireMonths===252&&retireMax<=2&&!problems.some(p=>/국민연금|인출 누락/.test(p))],['신규 주담대 실행·첫 납부·360회차·완납',installmentValid],['연도별 장기 자산 전망 52개년',annual?.length===52&&annual[0]?.[0]===2026&&annual.at(-1)?.[0]===2077]];
  return {ready:problems.length===0&&checks.every(x=>x[1]),months:keys.length,retirementMonths:retireMonths,checks,netMax,cashMax,purposeMax,deficitMax,retireMax,negativeCount,firstNegative,worst,worstMonth,problems,source:'2026-11-11 Google Sheets 내보내기',approved:false};
 }
 return {audit,monthShift};
});
