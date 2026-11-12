/* V59: validated latest-available public-indicator adapter. No fabricated observations.
   Published derived estimates are preferred. Rebuild from verified raw months only if complete.
   The official 2026-11 baseline remains the fallback, and each basis month is displayed. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V59_ECON=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const IDS=['CPI_GENERAL','CPI_CAR','CPI_TRAVEL','DEPOSIT','MORTGAGE','HOME_PRICE'];
const BASE={CPI_GENERAL:{value:120.73,ref:'2026-10'},CPI_CAR:{value:115.83,ref:'2026-09'},CPI_TRAVEL:{value:125.4608,ref:'2026-09'},DEPOSIT:{value:2.6289,ref:'2026-09'},MORTGAGE:{value:3.70845,ref:'2026-09'},HOME_PRICE:{value:-.233,ref:'2026-09'}};
const month=x=>/^\d{4}-(0[1-9]|1[0-2])$/.test(String(x||''));
const offset=(d,n)=>{const [y,m]=d.split('-').map(Number),v=y*12+m-1+n;return Math.floor(v/12)+'-'+String(v%12+1).padStart(2,'0');};
const isValid=(id,n)=>Number.isFinite(n) && (id==='DEPOSIT'||id==='MORTGAGE'?n>=0&&n<=30:id==='HOME_PRICE'?n>=-20&&n<=20:n>0&&n<5000);
function complete(series,n){if(series.length<n)return null;const last=series.at(-1),part=series.slice(-n);for(let i=1;i<n;i++)if(part[i].date!==offset(part[i-1].date,1))return null;return part;}
const RONE_NEW='HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606';
const RONE_OLD='HOME_PRICE_APT_DAEJEON_SEOGU';
function lastSeries(id,records,asOf){
 const rows=new Map();for(const r of records||[]){
  if(r.id!==id||!month(r.date)||r.date>asOf)continue;
  const val=Number(r.value);if(!Number.isFinite(val))continue;
  rows.set(r.date,{date:r.date,value:val,unit:String(r.unit||'')});
 }
 return [...rows.values()].sort((a,b)=>a.date.localeCompare(b.date));
}
function homeRaw(records,asOf,seriesId){
 const s=lastSeries(seriesId,records,asOf),used=complete(s,121);
 if(!used)return null;
 // Rebased index must have verifiable basis metadata: no old/new series splicing.
 if(seriesId===RONE_NEW){
  const anchor=s.find(x=>x.date==='2026-06');
  const explicit=used.some(x=>/2026\s*[-.]\s*0?6\s*=\s*100/.test(x.unit));
  if(!(anchor&&Math.abs(anchor.value-100)<0.15)&&!explicit)return null;
 }
 const now=used.at(-1).value,p60=used.at(-61).value,p120=used[0].value;
 if(!(now>0&&p60>0&&p120>0))return null;
 const v=(Math.pow(now/p60,1/5)-1)*50+(Math.pow(now/p120,1/10)-1)*50;
 return isValid('HOME_PRICE',v)?{ready:true,value:v,lastMonth:used.at(-1).date,source:'R-ONE 동일기준 5·10년 CAGR',seriesId}:null;
}
function derived(id,records,asOf){
 if(id==='HOME_PRICE')return homeRaw(records,asOf,RONE_NEW)||homeRaw(records,asOf,RONE_OLD);
 const s=lastSeries(id,records,asOf);if(!s.length)return null;
 let res=null,used=null;
 if(id==='CPI_GENERAL'){used=complete(s,1);if(used)res=used[0].value;}
 if(id==='CPI_CAR'||id==='CPI_TRAVEL'){const n=id==='CPI_CAR'?3:12;used=complete(s,n);if(used)res=used.reduce((a,b)=>a+b.value,0)/n;}
 if(id==='DEPOSIT'){used=complete(s,60);if(used)res=used.reduce((a,b)=>a+b.value,0)/60*.846;}
 if(id==='MORTGAGE'){used=complete(s,120);if(used)res=.7*used.slice(-60).reduce((a,b)=>a+b.value,0)/60+.3*used.reduce((a,b)=>a+b.value,0)/120;}
 return used&&isValid(id,res)?{ready:true,value:res,lastMonth:used.at(-1).date,source:'공식 원장 관측값 재계산'}:null;
}
function estimateCandidate(id,r,asOf){
 if(!r||r.status!=='ready'||!month(r.lastMonth)||r.lastMonth>asOf)return null;
 let value=Number(r.value),seriesId=r.id;
 if(id==='HOME_PRICE'){
  if(![RONE_NEW,RONE_OLD].includes(r.id))return null;
  const rates=r.rates||{};
  if(!Number.isFinite(rates['60months'])||!Number.isFinite(rates['120months']))return null;
  if(r.id===RONE_NEW&&r.indexBaseMonth&&r.indexBaseMonth!=='2026-06')return null;
  value=(rates['60months']+rates['120months'])/2;
 }else if(r.id!==id)return null;
 if(!isValid(id,value))return null;
 return {ready:true,value,lastMonth:r.lastMonth,source:'수집기 검증 가공값',seriesId};
}
function latest(status={},records=[],asOf='2026-11'){
 const data={},display=[];const estimates=Array.isArray(status?.estimates)?status.estimates:[];
 for(const id of IDS){
  let candidates=estimates.map(r=>estimateCandidate(id,r,asOf)).filter(Boolean);
  const raw=derived(id,records,asOf);if(raw)candidates.push(raw);
  candidates.sort((a,b)=>b.lastMonth.localeCompare(a.lastMonth)||Number(b.seriesId===RONE_NEW)-Number(a.seriesId===RONE_NEW));
  const best=candidates[0]||null,ref=BASE[id];
  if(best&&best.lastMonth>=ref.ref){data[id]=best;display.push({id,value:best.value,month:best.lastMonth,source:best.source,seriesId:best.seriesId,updated:best.lastMonth>ref.ref,validated:true});}
  else display.push({id,value:ref.value,month:ref.ref,source:'2026.11 최초 설계 기준값',updated:false,validated:false});
 }
 return {values:data,display,asOf};
}
return {IDS,BASE,derived,latest,offset};
});
