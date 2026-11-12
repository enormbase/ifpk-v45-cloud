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
function derived(id,records,asOf){const inputId=id==='HOME_PRICE'?'HOME_PRICE_APT_DAEJEON_SEOGU':id;const rows=new Map();for(const r of records||[]){if(r.id!==inputId||!month(r.date)||r.date>asOf)continue;const val=Number(r.value);if(!Number.isFinite(val))continue;rows.set(r.date,{date:r.date,value:val});}const s=[...rows.values()].sort((a,b)=>a.date.localeCompare(b.date));if(!s.length)return null;
 let res=null,used=null;
 if(id==='CPI_GENERAL'){used=complete(s,1);if(used)res=used[0].value;}
 if(id==='CPI_CAR'||id==='CPI_TRAVEL'){const n=id==='CPI_CAR'?3:12;used=complete(s,n);if(used)res=used.reduce((a,b)=>a+b.value,0)/n;}
 if(id==='DEPOSIT'){used=complete(s,60);if(used)res=used.reduce((a,b)=>a+b.value,0)/60*.846;}
 if(id==='MORTGAGE'){used=complete(s,120);if(used)res=.7*used.slice(-60).reduce((a,b)=>a+b.value,0)/60+.3*used.reduce((a,b)=>a+b.value,0)/120;}
 if(id==='HOME_PRICE'){used=complete(s,121);if(used){const now=used.at(-1).value,p60=used.at(-61).value,p120=used[0].value;if(now>0&&p60>0&&p120>0)res=.5*(Math.pow(now/p60,1/5)-1)*100+.5*(Math.pow(now/p120,1/10)-1)*100;}}
 return used&&isValid(id,res)?{ready:true,value:res,lastMonth:s.at(-1).date,source:'공식 원장 관측값 재계산'}:null;
}
function latest(status={},records=[],asOf='2026-11'){
 const data={},display=[];const estimates=Array.isArray(status?.estimates)?status.estimates:[];
 for(const id of IDS){let best=null;
 const item=estimates.find(r=>r.id===id&&r.status==='ready'&&month(r.lastMonth)&&r.lastMonth<=asOf&&isValid(id,Number(r.value)));
 if(item)best={ready:true,value:Number(item.value),lastMonth:item.lastMonth,source:'수집기 검증 가공값'};
 const raw=derived(id,records,asOf);if(raw&&(!best||raw.lastMonth>best.lastMonth))best=raw;
 const ref=BASE[id];if(best&&best.lastMonth>=ref.ref){data[id]=best;display.push({id,value:best.value,month:best.lastMonth,source:best.source,updated:best.lastMonth>ref.ref});}
 else{display.push({id,value:ref.value,month:ref.ref,source:'2026.11 최초 설계 기준값',updated:false});}
 }
 return {values:data,display,asOf};
}
return {IDS,BASE,derived,latest,offset};
});
