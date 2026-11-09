/* IFPK V51-2b.1 — read-only, goal-aware rolling scenario projection.
 * This module DOES NOT mutate the 605-month source ledger, approve plans, or
 * claim debt-policy/retirement asset recalculation. Observed records and manual
 * hypotheses are reported separately. Unverified purpose balances are labelled.
 */
(function (root, factory) {
  const base = root?.IFPK_V512A || (typeof module === 'object' && module.exports ? require('./rolling_preview_v512a.js') : null);
  const api = factory(base);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.IFPK_V512B = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (old) {
  'use strict';
  if (!old) throw new Error('V51-2a calculation module must load first');
  const START = old.START, END = old.END, RETIRE = old.RETIRE, GOALS = old.GOALS;
  const HOME_MOVE = '2046-10', CAR_BUY = '2034-10', TRIP = '2038-10';
  const HOME_BASE = Object.freeze({
    newPrice:763747266, oldNet:258662193, own:141486810, loan:363598263,
    existingLoanMonthly:1675319, interest:3.708, growth:-0.233,
    currentNewPrice:800000000, currentOldPrice:380000000
  });
  const CAR_BASE = Object.freeze({ price:58885412, resale:10648764, own:20000000, loan:28236648, monthlyPayment:532860, interest:5, term:60 });
  const TRIP_BASE = Object.freeze({ price:6724444, index:125.4608, indexMonth:'2026-09' });
  const CAR_INDEX_BASE = Object.freeze({ index:115.83, indexMonth:'2026-09' });
  const DEPOSIT_ANNUAL_BASE = .02628945;
  const numeric = x => typeof x === 'number' && Number.isFinite(x);
  const sum = a => a.reduce((x,y)=>x+y,0);
  const monthValid = s => typeof s === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(s);
  const moneyMax = 1e12;
  const monthlyRate = a => Math.pow(1+a,1/12)-1;
  const validBounded = (v,lo,hi) => numeric(v) && v>=lo && v<=hi;
  const manual = (obj,name,lo,hi) => {
    const raw=obj?.[name];
    if(raw===null||raw===undefined||String(raw).trim()==='')return {entered:false};
    const value=Number(raw);
    return validBounded(value,lo,hi) ? {entered:true,value} : {entered:true,error:`${name} 시험입력은 ${lo}~${hi} 범위의 숫자여야 합니다.`};
  };
  function futurePayment(principal,annualPct,n){
    if(!validBounded(principal,0,moneyMax)||!validBounded(annualPct,0,30)||!Number.isInteger(n)||n<=0)return null;
    const r=annualPct/1200;
    return Math.round(r<1e-12?principal/n:principal*r/(1-Math.pow(1+r,-n)));
  }
  function savingsPerMonth(goal,balance,n,annual){
    if(!validBounded(goal,0,moneyMax)||!validBounded(balance,0,moneyMax)||!validBounded(annual,0,1)||!Number.isInteger(n)||n<=0)return null;
    const r=monthlyRate(annual), fv=Math.pow(1+r,n), gap=goal-balance*fv;
    if(gap<=0)return 0;
    return Math.ceil((r<1e-12?gap/n:gap*r/(fv-1))-1e-9);
  }
  function observedRollingMean(records,id,count,asOf,unit){
    const eligible=(Array.isArray(records)?records:[]).filter(x=>x && x.id===id && monthValid(x.date) && x.date<asOf);
    for(const r of eligible){
      if(String(r.unit||'').replace(/\s/g,'')!==unit || !validBounded(Number(r.value),0.00001,1e6))return {ready:false,invalid:true,source:'자료 기준 불일치',reason:`${id}의 기준단위 또는 수치가 달라 계산을 중단했습니다.`};
    }
    const dict=new Map();
    for(const r of eligible){
      const value=Number(r.value);
      if(dict.has(r.date)&&Math.abs(dict.get(r.date)-value)>1e-8)return {ready:false,invalid:true,reason:`${id} 동일 통계월 중복 관측값 불일치`};
      dict.set(r.date,value);
    }
    const sorted=[...dict.keys()].sort().reverse();
    for(const date of sorted){
      const values=Array.from({length:count},(_,i)=>dict.get(old.shift(date,-i)));
      if(values.every(numeric))return {ready:true,date,value:sum(values)/count,months:count,source:`연속 ${count}개월 관측`};
    }
    return {ready:false,source:'관측자료 부족',reason:`${id}의 동일 기준 연속 ${count}개월 공식 관측값이 필요합니다.`};
  }
  function observedRates(records,id,count,asOf){
    const obs=observedRollingMean(records,id,count,asOf,'%');
    if(!obs.ready)return obs;
    if(!validBounded(obs.value,0,30))return {ready:false,reason:`${id} 관측금리가 허용범위를 벗어났습니다.`};
    return obs;
  }
  // V51-2b.1: The official collector stores the rebased R-ONE unit as '지수'.
  // Verify the documented 2026-06=100 anchor before accepting that generic label.
  // An explicitly labelled 2026-06=100 series can be used independently of the anchor
  // for 5y/10y CAGR, provided it never mixes incompatible units or months.
  function rebasedHomeRecords(records,asOf){
    const id='HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606';
    const source=(Array.isArray(records)?records:[]).filter(x=>x&&x.id===id&&monthValid(x.date)&&x.date<asOf);
    if(!source.length)return {ready:false,invalid:false,records:[],reason:'새 기준 R-ONE 실측자료 없음'};
    const explicitUnit=x=>/^2026(?:-|\.|년)0?6(?:월)?=100$/.test(String(x.unit||'').replace(/\s/g,''));
    const simpleUnit=x=>String(x.unit||'').replace(/\s/g,'')==='지수';
    if(source.some(x=>!(explicitUnit(x)||simpleUnit(x))||!validBounded(Number(x.value),.00001,1e6)))
      return {ready:false,invalid:true,records:[],reason:'R-ONE 새 기준 계열에 다른 기준년 또는 비정상 지수가 섞여 있습니다.'};
    const dict=new Map();
    for(const x of source){
      const val=Number(x.value);
      if(dict.has(x.date)&&Math.abs(dict.get(x.date)-val)>1e-8)
        return {ready:false,invalid:true,records:[],reason:'R-ONE 같은 기준월의 관측값이 일치하지 않습니다.'};
      dict.set(x.date,val);
    }
    const hasSimple=source.some(simpleUnit),anchor=dict.get('2026-06');
    if(hasSimple&&(!numeric(anchor)||Math.abs(anchor-100)>0.005))
      return {ready:false,invalid:true,records:[],reason:'R-ONE 단위가 지수이지만 2026-06=100 기준월 관측값이 확인되지 않았습니다.'};
    if(numeric(anchor)&&Math.abs(anchor-100)>0.005)
      return {ready:false,invalid:true,records:[],reason:'R-ONE 2026-06 기준 지수가 100이 아니므로 동일 기준 검증을 보류합니다.'};
    for(const [a,b] of [['2026-05','2026-06'],['2026-06','2026-07']]){
      if(dict.has(a)&&dict.has(b)&&Math.abs(dict.get(b)/dict.get(a)-1)>.1)
        return {ready:false,invalid:true,records:[],reason:'R-ONE 기준변경 전후 월간 변화가 10%를 초과해 검증이 필요합니다.'};
    }
    return {ready:true,invalid:false,records:source,dictionary:dict,source:hasSimple?'수집기 단위 지수 · 2026-06=100 기준월 검증':'2026-06=100 기준이 명시된 지수'};
  }
  function homeGrowth(records,asOf){
    const valid=rebasedHomeRecords(records,asOf);
    if(!valid.ready)return {ready:false,invalid:valid.invalid,reason:valid.reason};
    const dictionary=valid.dictionary;
    for(const date of [...dictionary.keys()].sort().reverse()){
      const observations=Array.from({length:121},(_,i)=>dictionary.get(old.shift(date,-i)));
      if(observations.every(numeric)){
        const now=observations[0],g5=Math.pow(now/observations[60],12/60)-1,g10=Math.pow(now/observations[120],12/120)-1;
        const growth=(g5+g10)/2;
        if(!validBounded(growth,-.5,1))return {ready:false,invalid:true,reason:'R-ONE 5/10년 CAGR 계산 범위 점검 필요'};
        return {ready:true,date,annualPct:growth*100,g5:g5*100,g10:g10*100,source:'R-ONE 동일기준 연속 121개월 · 5년/10년 CAGR 50:50'};
      }
    }
    return {ready:false,invalid:false,reason:'R-ONE 동일 기준 연속 121개월 자료가 없어 5·10년 CAGR 갱신을 보류합니다.'};
  }
  function observedHomeMovement(records,asOf){
    const valid=rebasedHomeRecords(records,asOf);
    if(!valid.ready)return valid.invalid?{ready:false,error:valid.reason}:{ready:false,reason:valid.reason};
    const dict=valid.dictionary,base='2026-09',start=dict.get(base);
    if(!numeric(start))return {ready:false,reason:'R-ONE 2026-09 최초 기준월 지수가 없어 경과분 보정을 보류합니다.'};
    const newer=[...dict.keys()].filter(x=>x>base).sort();
    if(!newer.length)return {ready:false,reason:'R-ONE 최초 기준월 이후 신규 관측값 없음'};
    const last=newer.at(-1),elapsed=old.between(base,last);
    for(let i=1;i<=elapsed;i++)if(!numeric(dict.get(old.shift(base,i))))return {ready:false,reason:'R-ONE 월별 지표에 공백이 있어 경과분 보정 보류'};
    const actualRatio=dict.get(last)/start,correction=actualRatio/Math.pow(1+HOME_BASE.growth/100,elapsed/12);
    if(!validBounded(correction,.05,20))return {ready:false,error:'R-ONE 경과분 보정비율 검증 실패'};
    return {ready:true,date:last,ratio:actualRatio,correction,months:elapsed,source:`R-ONE 2026-09 → ${last} 실측 누적 변화 · ${valid.source}`};
  }
  function indexInfo(records,id,maMonths,baseValue,baseDate,asOf,scenarioValue){
    const official=observedRollingMean(records,id,maMonths,asOf,'2020=100');
    const override=manual({value:scenarioValue},'value',1,10000);
    if(override.error)return {ready:false,error:`${id}: ${override.error}`};
    const selected=override.entered?{ready:true,date:old.shift(asOf,-1),value:override.value,source:'고객 입력 가정 · MA 값 (공식 미확인)',manual:true}:official;
    if(official.invalid)return {ready:false,error:official.reason};
    if(!selected.ready||selected.date<=baseDate)return {ready:false,reason:selected.ready?'기존 기준월보다 새로운 지표가 없어 목표가격 유지':selected.reason,baseValue,officialReady:official.ready};
    const observedMonths=old.between(baseDate,selected.date);
    const correction=selected.value/baseValue/Math.pow(1.025,observedMonths/12);
    if(!validBounded(correction,.01,10))return {ready:false,error:`${id}: 누적 물가보정배율 검증 실패`};
    return {...selected,ready:true,correction,observedMonths,baseValue,officialReady:official.ready};
  }
  function buildEnvironment(records,asOf,opts){
    const scenarios=opts.scenarios||{}, out={};
    const optDeposit=manual(scenarios,'depositRate',0,30),optMort=manual(scenarios,'mortgageRate',0,30),optHousing=manual(scenarios,'homeGrowth',-40,40);
    for(const x of [optDeposit,optMort,optHousing])if(x.error)return {ready:false,reason:x.error};
    const depositObserved=observedRates(records,'DEPOSIT',60,asOf);
    if(depositObserved.invalid)return {ready:false,reason:depositObserved.reason};
    const depRate=optDeposit.entered?optDeposit.value:depositObserved.ready?depositObserved.value:3.1075;
    out.deposit={value:depRate,annualNet:depRate/100*.846,source:optDeposit.entered?'시험 입력 · 세전 연%':depositObserved.ready?`ECOS ${depositObserved.date} 최근 60개월 평균`:'기존 ECOS 저장 가정 유지 (새 60개월 자료 없음)',updated:optDeposit.entered||depositObserved.ready};
    const m60=observedRates(records,'MORTGAGE',60,asOf),m120=observedRates(records,'MORTGAGE',120,asOf);
    if(m60.invalid||m120.invalid)return {ready:false,reason:(m60.invalid?m60:m120).reason};
    const mortObserved=m60.ready&&m120.ready?(.7*m60.value+.3*m120.value):null;
    const mortRate=optMort.entered?optMort.value:mortObserved!==null?mortObserved:HOME_BASE.interest;
    out.mortgage={value:mortRate,source:optMort.entered?'시험 입력 · 연%':mortObserved!==null?`ECOS ${m120.date} 기준 5년 70%·10년 30%`:'기존 약정금리 추정 유지 (새 120개월 자료 없음)',updated:optMort.entered||mortObserved!==null};
    const hg=homeGrowth(records,asOf),homeRealized=observedHomeMovement(records,asOf);
    // Fault isolation: a disputed home-price series must not prevent a general CPI
    // or car/travel scenario. Freeze house amounts, monthly saving and mortgage
    // until the R-ONE vintage is repaired; never silently approve the old series.
    out.homeBlocked=Boolean(hg.invalid||homeRealized.error);
    out.homeWarning=out.homeBlocked?(homeRealized.error||hg.reason||'R-ONE 동일기준 검증 실패'):null;
    out.homeActual=out.homeBlocked?{ready:false,reason:out.homeWarning}:homeRealized;
    out.homeGrowth={value:out.homeBlocked?HOME_BASE.growth:optHousing.entered?optHousing.value:hg.ready?hg.annualPct:HOME_BASE.growth,source:out.homeBlocked?'R-ONE 기준 불일치 · 주택만 계산 보류':optHousing.entered?'시험 입력 · 연간 주택가격 변동률':hg.ready?hg.source:'기존 R-ONE 추정률 유지 (새 동일기준 121개월 자료 없음)',updated:!out.homeBlocked&&(optHousing.entered||hg.ready),observed:hg};
    out.car=indexInfo(records,'CPI_CAR',3,CAR_INDEX_BASE.index,CAR_INDEX_BASE.indexMonth,asOf,scenarios.carMA3);
    out.travel=indexInfo(records,'CPI_TRAVEL',12,TRIP_BASE.index,TRIP_BASE.indexMonth,asOf,scenarios.travelMA12);
    for(const x of [out.car,out.travel])if(x.error)return {ready:false,reason:x.error};
    return {ready:true,...out};
  }
  function estimateFunds(snapshot,asOf,opts,env){
    const overview={};const balanceInputs=opts.balances||{};
    const nHousing=old.between(asOf,HOME_MOVE);
    const forecastStart=env.homeActual.ready?env.homeActual.date:asOf;
    const remainingHome=old.between(forecastStart,HOME_MOVE);
    const growthFactor=Math.pow((1+env.homeGrowth.value/100)/(1+HOME_BASE.growth/100),Math.max(0,remainingHome)/12);
    const observedCorrection=env.homeActual.ready?env.homeActual.correction:1;
    const totalHomeFactor=env.homeBlocked||asOf>HOME_MOVE?1:growthFactor*observedCorrection;
    const newHousePrice=Math.round(HOME_BASE.newPrice*totalHomeFactor);
    const oldGross0=HOME_BASE.currentOldPrice*Math.pow(1+HOME_BASE.growth/100,240/12);
    const oldNet=Math.round(HOME_BASE.oldNet+oldGross0*(totalHomeFactor-1));
    const loan=HOME_BASE.loan;
    let homeOwn=Math.max(0,newHousePrice-oldNet-loan);
    const manualHome=manual(opts,'houseGoal',0,moneyMax);if(manualHome.error)return {ready:false,reason:manualHome.error};
    if(manualHome.entered&&!env.homeBlocked)homeOwn=manualHome.value;
    const carPrice=asOf<=CAR_BUY&&env.car.ready?Math.round(CAR_BASE.price*env.car.correction):CAR_BASE.price;
    const carLoan=Math.max(0,carPrice-CAR_BASE.resale-CAR_BASE.own);
    const carPay=futurePayment(carLoan,CAR_BASE.interest,CAR_BASE.term);
    const mortgagePay=env.homeBlocked || asOf>HOME_MOVE || !env.mortgage.updated || Math.abs(env.mortgage.value-HOME_BASE.interest)<1e-10 ? HOME_BASE.existingLoanMonthly : futurePayment(loan,env.mortgage.value,360);
    const tripPrice=asOf<=TRIP&&env.travel.ready?Math.round(TRIP_BASE.price*env.travel.correction):TRIP_BASE.price;
    if([homeOwn,newHousePrice,oldNet,carPrice,carLoan,carPay,mortgagePay,tripPrice].some(v=>!validBounded(v,0,moneyMax)))return {ready:false,reason:'목표가격 또는 대출 추정값 검증 실패'};
    const amounts={house:homeOwn,car:CAR_BASE.own,travel:tripPrice};
    for(const [key,def] of Object.entries(GOALS)){
      if(key==='house'&&env.homeBlocked){overview[key]={active:false,blocked:true,label:def.label,date:def.date,reason:'R-ONE 기준 검증 필요 · 주택 자기자금/월저축 재계산 보류(기존 계획 유지)'};continue;}
      const remain=old.between(asOf,def.date);
      if(remain<=0){overview[key]={active:false,label:def.label,date:def.date,reason:'목표월 경과 · 실집행 확인 필요'};continue;}
      const b=old.estimateBalance(snapshot,key,asOf,balanceInputs[key]);if(!b.ready)return {ready:false,reason:b.reason};
      const payment=savingsPerMonth(amounts[key],b.balance,remain,env.deposit.annualNet);
      if(!validBounded(payment,0,moneyMax))return {ready:false,reason:`${def.label} 저축액 계산 실패`};
      overview[key]={active:true,label:def.label,date:def.date,goal:amounts[key],n:remain,balance:b.balance,balanceStatus:b.source,confirmed:b.confirmed,
        oldSaving:def.initialMonthly,newSaving:payment,deltaSaving:payment-def.initialMonthly,annualNet:env.deposit.annualNet,accountingVerified:false};
    }
    return {ready:true,goals:overview,finance:{
       homePrice:newHousePrice,oldHomeNet:oldNet,loan,own:homeOwn,homeMonthly:mortgagePay,homeMonthlyBefore:HOME_BASE.existingLoanMonthly,
       homeBasis:env.homeBlocked?'R-ONE 새 기준 검증 실패 · 주택가격/주택저축/주택담보대출 변경 계산 보류 · 기존 기준만 표시':manualHome.entered?'주택 필요자기자금 시험 입력 · 시세/순매각·대출 일관성 검토 필요':env.homeActual.ready||env.homeGrowth.updated?'실측 경과분/미래 주택가격 변동률 반영 · 신규 대출한도는 기존 가정 유지':'기존 주택가격·대출원금 가정 유지',
       carPrice,carLoan,carMonthly:carPay,carMonthlyBefore:CAR_BASE.monthlyPayment,carResale:CAR_BASE.resale,
       tripPrice,depositNet:env.deposit.annualNet,
       loanConstraintRecomputed:false
    }};
  }
  function compute(snapshot,records,opts={}){
    const valid=old.readLedger(snapshot);if(!valid.ready)return {ready:false,reason:valid.reason};
    const asOf=opts.asOf||START;
    if(!monthValid(asOf)||asOf<START||asOf>=RETIRE||old.between(START,asOf)%6!==0)return {ready:false,reason:'재설계월은 2026-11 이후 6개월 간격(은퇴 전)만 선택할 수 있습니다.'};
    const cpi=old.generalCpi(records,asOf,opts.hypotheticalCPI??null);if(!cpi.ready)return cpi;
    const spendingRaw=opts.actualSpending;
    const actual=spendingRaw!==null&&spendingRaw!==undefined&&String(spendingRaw).trim()!=='';
    const spending=actual?Number(spendingRaw):null;
    if(actual&&!validBounded(spending,0,2e8))return {ready:false,reason:'실제 생활비 입력이 올바르지 않습니다.'};
    const env=buildEnvironment(records,asOf,opts);if(!env.ready)return env;
    const funds=estimateFunds(snapshot,asOf,opts,env);if(!funds.ready)return funds;
    const scenarioGoals=funds.goals,fin=funds.finance;
    const cash={baseline:0,preview:0};
    const account={};const eventAudit=[];const monthlyResults={};let deficitBase=0,deficitScenario=0;
    const targetEventName={house:3,car:4,travel:5},targetBalanceCol={house:11,car:12,travel:13};
    const sampleMonths=new Set([old.shift(asOf,-1),asOf,old.shift(asOf,1),HOME_MOVE,CAR_BUY,TRIP,old.shift(RETIRE,-1)]);
    const examples=[];
    for(const month of Object.keys(snapshot).sort()){
      const row=snapshot[month],preRet=month<RETIRE,after=month>=asOf;
      const legacyRebase=preRet?old.currentBudget(month)-old.legacyBudget(month):0;
      const baseBudget=preRet?old.currentBudget(month):null;
      const newBudget=preRet&&after?(actual?Math.round(spending*Math.pow(1.025,old.between(asOf,month)/12)):Math.round(baseBudget*cpi.correction)):baseBudget;
      const changeGeneral=preRet&&after?newBudget-baseBudget:0;
      // Existing current mortgage and child care obligations remain in the source expense.
      // New car and home loan effects only apply to their respective future 60/360 month terms.
      const hasCarLoan=month>CAR_BUY&&month<old.shift(CAR_BUY,CAR_BASE.term+1);
      const hasNewMortgage=month>HOME_MOVE&&month<old.shift(HOME_MOVE,361);
      const deltaCarPayment=after&&hasCarLoan?fin.carMonthly-fin.carMonthlyBefore:0;
      const deltaHomePayment=after&&asOf<=HOME_MOVE&&hasNewMortgage?fin.homeMonthly-fin.homeMonthlyBefore:0;
      const expenseChange=changeGeneral+deltaCarPayment+deltaHomePayment;
      const newSavings=[row[7],row[8],row[9],row[10]];
      for(const [key,def] of Object.entries(GOALS)){
        const g=scenarioGoals[key];if(after&&preRet&&g?.active&&month<g.date)newSavings[def.colSaving-7]=g.newSaving;
      }
      const savDelta=sum(newSavings)-sum(row.slice(7,11));
      let eventChange=0,transferChange=0;
      for(const [key,def] of Object.entries(GOALS)){
        const g=scenarioGoals[key];if(!after||!g?.active||month>g.date)continue;
        if(month===asOf)account[key]=g.balance;
        if(month<g.date){
          account[key]=account[key]*(1+monthlyRate(env.deposit.annualNet))+g.newSaving;
        }else if(month===g.date){
          const available=account[key];const draw=Math.min(g.goal,Math.max(0,Math.floor(available+0.0001)));
          const remaining=Math.max(0,g.goal-draw);
          const oldEvent=row[targetEventName[key]];
          const newEvent=g.goal;
          eventChange+=newEvent-oldEvent;
          transferChange+=draw-oldEvent;
          account[key]=Math.max(0,available-draw);
          const audited={key,label:g.label,month,required:newEvent,available:Math.round(available),transferred:draw,unfunded:remaining,funded:remaining===0};
          eventAudit.push(audited);
        }
      }
      const baseNet=row[6]-legacyRebase;
      const baseChange=baseNet-sum(row.slice(7,11))+row[14]+row[15];
      cash.baseline=Math.round(cash.baseline+baseChange);
      // Retirement withdrawal assumptions remain fixed: do not report post-retirement results as verified.
      cash.preview=Math.round(cash.preview+baseChange-(after?expenseChange+savDelta+eventChange-transferChange:0));
      if(preRet){if(cash.baseline<0)deficitBase++;if(cash.preview<0)deficitScenario++;}
      const x={month,previewEligible:preRet,baselineCash:cash.baseline,previewCash:preRet?cash.preview:null,
        baselineExpense:row[2]+legacyRebase,previewExpense:preRet?row[2]+legacyRebase+(after?expenseChange:0):null,
        baselineGeneral:baseBudget,previewGeneral:newBudget,
        basePurposeSave:[row[8],row[9],row[10]],previewPurposeSave:newSavings.slice(1),
        loanPaymentChange:after?deltaCarPayment+deltaHomePayment:0,
        houseBalance:account.house??null,carBalance:account.car??null,travelBalance:account.travel??null,
        directEventFundingGap:Math.max(0,eventChange-transferChange)
      };
      monthlyResults[month]=x;
      if(sampleMonths.has(month))examples.push(x);
    }
    const checks=eventAudit.filter(e=>e.unfunded>0);
    const changedPeriods=Object.values(monthlyResults).filter(r=>r.previewEligible&&r.month>=asOf&&((r.previewCash!==r.baselineCash)||(r.previewExpense!==r.baselineExpense))).length;
    const afterRet=monthlyResults[RETIRE];
    return {ready:true,partial:true,mayApprove:false,scope:'은퇴 전 월별 소비·목적저축·이벤트 계좌전입·차량할부·주택 신규대출 비용 시험',
      asOf,cpi,environment:env,finance:fin,goals:scenarioGoals,examples,monthlyResults,eventAudit,
      partialModules:env.homeBlocked?['주택: R-ONE 동일 기준 검증 대기']:[],
      expenseSource:'2026.11 일반생활비 240만원·연 2.5% 기준 재기준화',
      baselineCashAtReview:monthlyResults[asOf].baselineCash,previewCashAtReview:monthlyResults[asOf].previewCash,
      retirementEve:monthlyResults[old.shift(RETIRE,-1)],retirementAfterExcluded:afterRet.previewCash===null,
      changedPeriods,baselineDeficitMonths:deficitBase,previewDeficitMonths:deficitScenario,
      eventShortfalls:checks,ledgerVerified:valid.months,
      notices:[
        '주택 LTV·DSR 신규 한도 계산 및 기존 주담대 최신 잔액 재산정은 수행하지 않았습니다. 신규대출 원금은 기존 가정을 유지합니다.',
        '자동차 중고차 매각시세는 신규 검증자료가 없어 기존 추정값을 유지합니다.',
        '목적저축 실제 잔액을 입력하더라도 과거 일반계좌와의 자금 출처 대사는 하지 않았습니다.',
        '은퇴 후 현금흐름·필요 일시금·DC/국민연금/건보료·은퇴 투자자산은 재계산하지 않습니다.',
        '미래시점 지표의 수기 입력은 고객 가정이며 공식 발표자료로 저장되지 않습니다.',
        '고객 승인·과거 실적 확정 및 공식계획 저장은 지원하지 않습니다.'
      ]};
  }
  return Object.freeze({START,END,RETIRE,HOME_BASE,CAR_BASE,TRIP_BASE,monthlyRate,futurePayment,savingsPerMonth,observedRollingMean,observedRates,homeGrowth,observedHomeMovement,indexInfo,buildEnvironment,estimateFunds,compute});
});
