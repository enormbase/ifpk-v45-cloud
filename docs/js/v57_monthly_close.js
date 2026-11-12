/* IFPK V57: customer-entered monthly actuals / manual completion / synchronized four-goal rollover.
 * Pure transactional helper. No bank verification, backend mutation, or official-plan approval.
 */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.IFPK_V57=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const IDS=['home','car','travel','ret'];
const monthOK=x=>/^\d{4}-(0[1-9]|1[0-2])$/.test(String(x||''));
function nextMonth(date){if(!monthOK(date))throw Error('월 형식이 올바르지 않습니다');const [y,m]=date.split('-').map(Number);return (m===12?y+1:y)+'-'+String(m===12?1:m+1).padStart(2,'0');}
function validAmount(v){return typeof v==='string'&&/^(0|[1-9]\d*)$/.test(v.trim())&&Number.isSafeInteger(Number(v))&&Number(v)<=1e12;}
function blank(){return {schema:1,active:'2026-11',pending:{},checks:{},history:{}};}
function clean(raw){let s=blank();if(!raw||typeof raw!=='object')return s;
 if(monthOK(raw.active)&&raw.active>='2026-11'&&raw.active<='2056-04')s.active=raw.active;
 if(raw.pending&&typeof raw.pending==='object')for(const id of IDS){const v=raw.pending[id];if(typeof v==='string'&&(/^\d*$/.test(v))&&v.length<=15)s.pending[id]=v;}
 if(raw.checks&&typeof raw.checks==='object')for(const id of IDS)s.checks[id]=!!raw.checks[id]&&validAmount(s.pending[id]||'');
 if(raw.history&&typeof raw.history==='object')for(const [month,rec] of Object.entries(raw.history)){
  if(!monthOK(month)||month>='2056-04'||!rec||typeof rec!=='object'||!rec.actuals)continue;
  const values={};let good=true;
  for(const [id,v] of Object.entries(rec.actuals))if(IDS.includes(id)){if(!Number.isSafeInteger(Number(v))||Number(v)<0){good=false;break;}values[id]=Number(v);}
  if(good&&Object.keys(values).length)s.history[month]={...rec,actuals:values};
 }
 return s;
}
function dueGoals(goals,date){return goals.filter(g=>date<g.deadline).map(g=>g.id);}
function pendingReady(state,goals,date){const due=dueGoals(goals,date);return due.every(id=>state.checks[id]===true&&validAmount(state.pending[id]));}
function closeMonth(state,goals,date,snapshot={}){
 if(date!==state.active)throw Error('진행 월이 일치하지 않습니다');
 if(!pendingReady(state,goals,date))throw Error('현재월 모든 저축실적 입력과 확인이 필요합니다');
 if(date>='2056-04')throw Error('은퇴 이후에는 목적저축 월마감이 없습니다');
 const actuals={};for(const id of dueGoals(goals,date))actuals[id]=Number(state.pending[id]);
 const past={...state.history,[date]:{...snapshot,actuals,confirmed:true}};
 return {state:{schema:1,active:nextMonth(date),history:past,pending:{},checks:{}},actuals};
}
function reopenLast(state){const dates=Object.keys(state.history).sort();const last=dates.at(-1);if(!last||nextMonth(last)!==state.active)throw Error('바로 이전에 확정한 월만 다시 열 수 있습니다');const history={...state.history};const rec=history[last];delete history[last];const pending={},checks={};for(const [id,amount] of Object.entries(rec.actuals)){pending[id]=String(amount);checks[id]=false;}
 return {state:{schema:1,active:last,history,pending,checks},reopened:last,actuals:rec.actuals};
}
const api={IDS,blank,clean,monthOK,nextMonth,validAmount,dueGoals,pendingReady,closeMonth,reopenLast};return api;
});
