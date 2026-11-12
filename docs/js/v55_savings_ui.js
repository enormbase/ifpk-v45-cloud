/* IFPK V55 · present verified-versus-forecast four-goal execution without
 * touching the version-locked V52 reference/audit ledger. No external libraries.
 */
(function(root){'use strict';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>Number.isFinite(Number(n))?Math.round(Number(n)).toLocaleString('ko-KR')+'원':'—';
const compact=n=>Math.abs(Number(n))>=100000000?(Number(n)/1e8).toFixed(2)+'억원':(Number(n)/10000).toLocaleString('ko-KR',{maximumFractionDigits:1})+'만원';
const names={home:'부동산',car:'자동차',travel:'해외여행',ret:'은퇴'},icons={home:'🏠',car:'🚙',travel:'✈️',ret:'🌿'},colors={home:'#2f72b8',car:'#de9850',travel:'#258c6c',ret:'#6a75aa'};
const methodText={decrease:'감액형',flat:'정액형',increase:'증액형'};
const mon=(y,m)=>`${y}-${String(m).padStart(2,'0')}`;
function sectionStart(sim,date){const row=sim.byMonth[date],retired=date>='2056-04';return {row,retired};}
function actualOne(state,date,g){const z=state.actuals?.[date]||{};return Object.prototype.hasOwnProperty.call(z,g)&&Number.isFinite(Number(z[g]))?Number(z[g]):null;}
function infoSummary(snapshot,sim,date,source){const row=sim.byMonth[date],retired=date>='2056-04';
 if(!row)return `<section class="v55-summary-shade"><h3>월별 저축 배분 · 조회기간 밖</h3><p>2026년 11월~2056년 3월에 적용되는 월별 목적저축 실행계획입니다.</p></section>`;
 const gap=Math.max(0,row.needed-row.assigned),over=row.assigned>Math.max(0,row.available)+1;
 const basis=root.IFPK_V60_TRACE?.trace(snapshot,sim,date,source||{display:[],values:{}});
 const warn=basis?.expenseOverride?'해당 월 실제 총지출 입력값을 우선 적용했어요.':'표시된 지출은 아직 실지출 확인 전의 추정액이에요.';
 const summary=basis?`<div class="v60-basis-heading"><b>이번 전망의 계산 기준</b><span>조회월 ${esc(date)} · ${date<sim.activeMonth?'과거월 실적 보존 · ':'미래 전망 기준 · '}검증된 지표 ${basis.appliedCount}/6종</span></div><div class="v60-basis-source">${basis.items.map(x=>`<span>${esc(x.name)} <b>${esc(x.month)}</b> ${x.validated?'· 검증자료':'· 최초 가정'}</span>`).join('')}</div><details class="v60-basis-details"><summary>물가·금리 반영과 비용 구성 자세히 보기</summary><div class="v60-cost-list">${basis.parts.map(x=>`<div><span>${esc(x.name)} ${x.appliedLabel?`<small>· ${esc(x.appliedLabel)}</small>`:x.indicator?`<small>· ${esc(root.IFPK_V60_TRACE.NAMES[x.indicator])}</small>`:'<small>· 지표 자동연동 없음</small>'}</span><strong>${money(x.value)}${Math.abs(x.delta)>1?` <small>(${x.delta>0?'+':'−'}${money(Math.abs(x.delta))})</small>`:''}</strong></div>`).join('')}</div><p>${warn} 지표 영향은 신규 검증자료가 있는 미래 전망월에만 적용돼요. 별도 보험·건보료 금액이 0원이어도 실제 보험료가 0원이라는 의미는 아니며, 보험료의 최신 요율 자동 재계산은 아직 연결되지 않았습니다.</p></details>`:'';
 return `<section class="v55-summary-shade" aria-label="V55 우선순위 월별 배분 요약"><div class="v55-shade-heading"><div><small>V55 · 새 통합 저축 원장</small><h3>${esc(date)} · 우리 가족 월 저축가능액과 목적별 배분</h3></div><span class="v55-tag">${esc(date>sim.asOf?'미래 전망':'고객 실적 미확인월은 전망')}${sim.economics.changes.length?' · 갱신지표 시험':''}</span></div>
 ${summary}<div class="v55-shade-grid">
  <article><small>월 근로·지원 현금유입</small><strong>${money(row.income)}</strong></article>
  <article><small>일반소비·양육비·대출·보험</small><strong>${money(row.expense)}</strong></article>
  <article><small>월 저축가능액</small><strong>${money(row.available)}</strong></article>
  <article><small>4대 목적 배정저축액</small><strong>${money(row.assigned)}</strong></article>
  <article class="v55-alert"><small>필요 대비 미배정 저축액</small><strong>${money(gap)}</strong></article>
  <article><small>배정 후 남는 현금</small><strong>${money(row.free)}</strong></article>
 </div><p class="v55-shade-note">선택월 누적 일반현금(2026.11부터, 별도 일시거래 제외 기준) <b>${money(row.cumulativeFree)}</b> · ${over?'⚠ 실제 납입액이 가용액을 초과함':'예상 배정액은 계좌 입금 실적이 아닙니다'}. <b>주택구매·차량구매·여행은 목적계좌 전입과 분리해 중복 차감하지 않습니다.</b></p></section>`;
}
function miniLine(sim,id,date){const rows=sim.months.filter(x=>x.month<=date&&x.month<sim.byId[id].deadline).slice(-13);if(!rows.length)return '';
 const values=rows.flatMap(x=>[x.required[id],x.allocated[id]]),max=Math.max(1,...values),w=240,h=54;
 const poly=key=>rows.map((r,i)=>`${(i/(Math.max(1,rows.length-1))*w).toFixed(1)},${(h-r[key][id]/max*h).toFixed(1)}`).join(' ');
 return `<svg class="v55-mini-trend" viewBox="0 0 ${w} ${h}" role="img" aria-label="최근 최대 13개월 월 필요저축액과 배정저축액 비교"><polyline fill="none" stroke="#94a3b8" stroke-width="2.3" points="${poly('required')}"></polyline><polyline fill="none" stroke="#16a085" stroke-width="2.4" points="${poly('allocated')}"></polyline></svg>`;
}
function roadmap(snapshot,sim,date,state){
 const row=sim.byMonth[date],pct=goal=>Math.max(0,Math.min(100,(months('2026-11',date)/months('2026-11',goal.deadline))*100));
 const months=(a,b)=>root.IFPK_V55.months(a,b);
 const ordered=[...sim.goals].sort((a,b)=>a.priority-b.priority);
 const projected=ordered.map(g=>{const r=row||sim.last;const b=sim.book[g.id],newGoal=g.initialNewGoal,basicTarget=g.total;
 const first=r.month<g.deadline,needed=first?r.required[g.id]:0,assigned=first?r.allocated[g.id]:0,actual=actualOne(state,date,g.id);
 const currBal=r.balances[g.id],deficit=b.shortfall;
 const progPct=pct(g),goalX=Math.max(0,Math.min(100,root.IFPK_V55.months('2026-11',g.deadline)/root.IFPK_V55.months('2026-11','2056-04')*100));
 const entryDate=(date>='2026-11'&&date<g.deadline)?date:'2026-11';const fullX=Math.max(0,Math.min(100,root.IFPK_V55.months('2026-11',entryDate)/root.IFPK_V55.months('2026-11','2056-04')*100));
 const dots=sim.months.filter(x=>x.month<=date && x.month<g.deadline && x.status[g.id]==='user_entered').map(x=>`<i class="v55-real-dot" style="left:${(root.IFPK_V55.months('2026-11',x.month)/root.IFPK_V55.months('2026-11','2056-04')*100).toFixed(2)}%" title="${x.month} 고객 입력납입액"></i>`).join('');
 const funding=g.id==='ret'?`필요 은퇴일시금 ${compact(snapshot.retirementTotalNeed)} / DC 등 ${compact(snapshot.dcRetirement)}`:`기존 준비자금 예상 미래가치 ${compact(g.total-newGoal)}`;
 const status=deficit>1?`목표시점 예상 ${money(deficit)} 부족`:`목표 충족 전망`;
 return `<article class="v55-goal-row" style="--v55-goal:${colors[g.id]}"><div class="v55-goal-header"><b>${icons[g.id]} ${names[g.id]}</b><span>${g.priority}순위 · ${methodText[g.method]} · ${g.deadline.replace('-','.')} 목표</span><em class="${deficit>1?'v55-bad':'v55-ok'}">${status}</em></div>
 <div class="v55-goal-line" aria-label="선택월 ${date}, 목표월 ${g.deadline}; 점선은 전망, 점은 입력된 실제 내역"><span class="v55-progress-plan" style="width:${goalX}%"></span>${g.initial>0?'<span class="v55-hatch"></span>':''}<span class="v55-query-now" style="left:${fullX}%"></span><span class="v55-goal-end" style="left:${goalX}%"></span>${dots}</div>
 <div class="v55-goal-metrics"><div><small>목표시점 필요금액</small><strong>${money(basicTarget)}</strong><small class="v55-note">${funding}</small></div><div><small>새 저축으로 채울 미래금액</small><strong>${money(newGoal)}</strong></div><div><small>이번 달 필요저축액</small><strong>${first?money(needed):'목표기간 경과'}</strong></div><div><small>이번 달 배정저축액</small><strong class="v55-alloc">${first?money(assigned):'—'}</strong><small class="v55-note">${actual===null?'실제 납입 미확인':'고객 입력 '+money(actual)}</small></div></div>
 <div class="v55-goal-foot"><span>선택월 말 목적계좌 전망 ${money(currBal)} · 목표일까지 준비 전망 ${money(b.expected)}</span><span>필요 대비 당월 ${money(Math.max(0,needed-assigned))} 미배정</span></div>${miniLine(sim,g.id,date)}</article>`;
 }).join('');
 return `<section class="v55-roadmap" aria-labelledby="v55-road-title"><div class="v55-title"><div><small>FAMILY SAVINGS EXECUTION · V55</small><h2 id="v55-road-title">우리 가족 저축 실행 현황</h2><p>선택한 ${esc(date)} 기준. 최초 목표 대비 배정 차이를 다음 달부터 재역산하고, 새로운 공표지표가 검증되면 변경안에 반영합니다.</p></div><span class="v55-tag">${sim.economics.changes.length?'새 지표 '+sim.economics.changes.length+'건 · 변경안':'2026.11 시트 기준 · 전망'} / 공식 미승인</span></div>
 <div class="v55-legend"><span>— 회색 실선: 월 필요저축액</span><span>— 녹색 실선: 월 배정저축액</span><span>▧ 기초자금</span><span>● 실제 입력 월</span><span>⋯ 향후 계획</span></div>${projected}
 ${sim.retirement.firstUnmet?`<div class="v55-childcare" style="background:#fff1ef;border-color:#f0c1bd;color:#8d3026"><b>⚠ 은퇴 이후 인출 부족 경고</b> · 첫 미충당 ${esc(sim.retirement.firstUnmet)}. 만 90세 직전 종료잔액 0원은 목표 달성이 아니라 자산 고갈일 수 있습니다. 추가 미충당액 ${money(sim.retirement.totalUnmet)}.</div>`:''}
 <div class="v55-childcare"><b>👶 자녀 양육비는 목적계좌가 아닙니다.</b> 영유아·초등·중고등·대학 등 월 지출 및 정부지원금 변화로 저축가능액에 반영합니다.</div>
 <p class="v55-disclaimer">※ '총 필요금액'은 주택 갈아타기 자기자금, 차량 현금 자기자금, 여행 미래 경비, 은퇴일시금에서 각자의 기존 마련액과 조달액을 별도 차감한 값입니다. 금융시점과 용도가 다른 금액을 바로 합산하지 않습니다. 미래월 배정액은 실적이 아니며 입금이 확인된 월만 고객 입력으로 구분합니다.</p>
 ${entryEditor(sim,date,state)}</section>`;
}
function entryEditor(sim,date,state){const now=sim.asOf,valid=date>='2026-11'&&date<'2056-04',saveAllowed=valid&&date<=now;
 const rec=sim.byMonth[date];
 const inputs=sim.goals.map(g=>{let actual=actualOne(state,date,g.id);return `<label><span>${icons[g.id]} ${names[g.id]} 실제 납입(원)</span><input inputmode="numeric" type="number" min="0" step="1000" data-v55-actual="${g.id}" placeholder="미확인" value="${actual===null?'':esc(actual)}" ${saveAllowed?'':'disabled'}></label>`}).join('');
 const cash=state.cash?.[date]||{};
 return `<details class="v55-entry" ${saveAllowed?'':'data-readonly="true"'}><summary>✏️ 실제 월 소득·지출 및 목적저축 납입내역 입력 <small>${saveAllowed?'입력·삭제로 이후 월별 재계산':'과거월·현재월만 입력'}</small></summary><div class="v55-form"><p>선택월 ${esc(date)} · 시뮬레이션용 <b>고객 입력</b>입니다. 계좌 증빙이나 공식 계획 승인이 아닙니다. 입력하지 않은 목적은 전망으로 표시됩니다.</p>
 <div class="v55-form-grid"><label><span>당월 실제 총 현금유입(원)</span><input id="v55-income" type="number" min="0" step="1000" placeholder="기준 전망: ${money(rec?.income)}" value="${cash.income??''}" ${saveAllowed?'':'disabled'}></label><label><span>당월 실제 생활·의무지출(원)</span><input id="v55-expense" type="number" min="0" step="1000" placeholder="기준 전망: ${money(rec?.expense)}" value="${cash.expense??''}" ${saveAllowed?'':'disabled'}></label>${inputs}</div>
 <div class="v55-form-buttons"><button type="button" class="primary" data-v55-save="${date}" ${saveAllowed?'':'disabled'}>고객 입력값 저장·재계산</button><button type="button" class="secondary" data-v55-clear="${date}" ${saveAllowed?'':'disabled'}>선택월 입력 초기화</button></div>
 <p>⚠ 실제 입금 합계가 그달 저축가능액보다 커도 기록은 보존하지만, 초과 조달은 별도 경고합니다. 미래월은 고객 확인 전까지 계획에 따라 자동 배분합니다.</p></div></details>`;
}
function priorityControls(sim,state){return `<section class="v55-controls"><div class="v55-title"><div><small>고객정보 · CHAPTER 1-8</small><h2>목적저축 우선순위 · 저축방식</h2><p>기본값은 부동산 1순위 감액형, 자동차 2순위 정액형, 해외여행 3순위 정액형, 은퇴 4순위 증액형입니다.</p></div><span class="v55-tag">웹 시험 설정 · 공식 미승인</span></div><div class="v55-settings-grid">${sim.goals.map(g=>`<label><b>${icons[g.id]} ${names[g.id]}</b><span>우선순위<select data-v55-priority="${g.id}">${[1,2,3,4].map(n=>`<option value="${n}" ${g.priority===n?'selected':''}>${n}순위</option>`).join('')}</select></span><span>저축유형<select data-v55-method="${g.id}">${[['decrease','감액형'],['flat','정액형'],['increase','증액형']].map(([k,v])=>`<option value="${k}" ${g.method===k?'selected':''}>${v}</option>`).join('')}</select></span></label>`).join('')}</div><div class="v55-form-buttons"><button type="button" class="primary" data-v55-setting-save>우선순위·방식 재계산</button><button type="button" class="secondary" data-v55-setting-reset>기본값 복원</button></div><p class="v55-disclaimer">증액/감액은 현재 시트 기준 연 2.5%를 월 단위 복리비율로 환산합니다. 변경 계획은 이 브라우저에서만 시험하며 공식 재무설계 승인과 다릅니다.</p></section>`}
function flow(sim,year){const rows=sim.months.filter(x=>x.month.startsWith(String(year)));if(!rows.length)return '';
 const format=(d,g)=>money(d[g]);
 return `<section class="v55-flow"><div class="v55-title"><div><small>V55 · 단일 월별 배분원장</small><h2>${year}년 월별 4대 목적저축 실행표</h2><p>월 현금유입에서 일반소비·양육비·기존·신규 주담대·오토론을 차감한 후 저축가능액을 우선 배분합니다. 구매·여행 일시지출은 이 월별 저축가능액에서 다시 빼지 않습니다.</p></div></div><div class="v55-scroll-table"><table><thead><tr><th>월</th><th>현금유입</th><th>일반·의무지출</th><th>저축가능액</th><th>부동산 배정</th><th>자동차 배정</th><th>여행 배정</th><th>은퇴 배정</th><th>필요 대비 미배정</th><th>잔여현금</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.month}</td><td>${money(r.income)}</td><td>${money(r.expense)}</td><td>${money(r.available)}</td><td>${money(r.allocated.home)}</td><td>${money(r.allocated.car)}</td><td>${money(r.allocated.travel)}</td><td>${money(r.allocated.ret)}</td><td class="v55-short">${money(Math.max(0,r.needed-r.assigned))}</td><td>${money(r.free)}</td></tr>`).join('')}</tbody></table></div><p class="v55-disclaimer">사용한 전망 기준: ${esc(sim.schema)}. 아래 기존 원장·연간 금융자산 도표는 V52 이전 모델의 비교자료이며 새 월별 목적배분액과 완전히 일치하지 않을 수 있습니다.</p></section>`;
}
function plan(sim){const ordered=[...sim.goals].sort((a,b)=>a.priority-b.priority);
 return `<section class="v55-plans"><div class="v55-title"><div><small>분야별 설계 · V55 실행 연결</small><h2>목표금액과 월별 배정, 무엇이 다른가요?</h2><p>분야별 원래의 가격·연금 계산기는 유지하고, 실제 저축 실행은 통합 월별 배분원장으로 확인합니다.</p></div></div><div class="v55-plan-grid">${ordered.map(g=>{const b=sim.book[g.id];const m=sim.first;return `<article><b>${icons[g.id]} ${names[g.id]} · ${g.priority}순위 ${methodText[g.method]}</b><small>목표일 ${g.deadline}</small><p>전체 필요한 자기자금/일시금: <strong>${money(g.id==='ret'?Number(sim.retirement.initial-(sim.book.ret?.expected||0)+g.total):g.total)}</strong></p><p>기존 준비자금의 목표월 가치: <strong>${money(g.id==='ret'?Number(sim.retirement.initial-(sim.book.ret?.expected||0)):g.total-g.initialNewGoal)}</strong></p><p>신규 저축으로 채울 미래금액: <strong>${money(g.initialNewGoal)}</strong></p><p>이번 달 필요 / 배정: <strong>${money(m.required[g.id])} / ${money(m.allocated[g.id])}</strong></p><p class="${b.shortfall>1?'v55-short':''}">목표월 전망: <strong>${money(b.expected)}</strong> · ${b.shortfall>1?money(b.shortfall)+' 부족':'목표 충족'}</p></article>`}).join('')}</div><p class="v55-disclaimer">※ 고객이 목표시점·대출조건·가격 기준을 바꾸는 경우 필요한 자기자금 자체가 달라질 수 있으며 관련 분야 계산을 다시 검증해야 합니다.</p></section>`;}
function data(sim,source){const changes=sim.economics.changes,check=sim.economics;const sources=source?.display||[];const labels=root.IFPK_V60_TRACE?.NAMES||{};
 return `<section class="v55-update"><div class="v55-title"><div><small>V55 · 1개월 롤링 재설계 초안</small><h2>월별 현금흐름·경제지표 동시 재계산</h2><p>목표별 필요저축액→우선순위 배정→월말 목적계좌→다음 달 필요액 역산을 매월 반복합니다. 공식 API에서 신규 공표된 값만 해당 시점부터 반영하고, 그 외엔 기존 유효값을 유지합니다.</p></div><span class="v55-tag">${changes.length?changes.length+'건 최신 지표 변경안':'기준지표 유지 · 추가 발표 없음/미연결'}</span></div><div class="v55-cycle"><b>① 소득·의무지출·실제납입 확인</b><span>→</span><b>② 발표된 경제지표 검증</b><span>→</span><b>③ 4대 목표금액 갱신</b><span>→</span><b>④ 우선순위 재배정·잔여개월 역산</b><span>→</span><b>⑤ 고객 검토·승인 전후 비교</b></div><p class="v55-disclaimer">지표 기준월과 실제 공표·수집일은 다릅니다. 본 화면의 계산은 <b>변경안 미리보기</b>이며 공식 확정 기록이나 Google Sheets 자동 쓰기가 아닙니다. R-ONE 주택가격 변화는 LTV·DSR·순매각대금 재검증이 필요한 고정 조달조건 민감도 시나리오입니다.</p>${sources.length?`<div class="v55-source-list v60-source-chips">${sources.map(x=>`<span>${esc(labels[x.id]||x.id)} · ${esc(x.month)} · ${x.validated?'검증값 적용':'최초 가정 유지'}</span>`).join('')}</div>`:''}${changes.length?`<div class="v55-source-list">${changes.map(x=>`<span>${esc(x.id)} · ${esc(x.ref)}: ${x.value} (기준 ${x.base})</span>`).join('')}</div>`:''}<div class="v55-form-buttons"><button type="button" class="secondary" data-v55-refresh>클라우드 경제지표 새로 확인</button><a href="${esc(sim.sourceUrl||'https://docs.google.com/spreadsheets/d/1-_kJV7OkxJpyo4H5rUIeTwJyHB5-olhkZEj3ZRQz7Os/edit')}" target="_blank" rel="noopener">재무설계 근거 시트 ↗</a></div><p class="v55-disclaimer">자동 경제지표 연결은 공개 스냅샷이 검증되어 정상 로드될 때만 적용됩니다. 지표 연동에 실패하면 기준 가정을 고정하며, 고객의 1개월마다 실적 입력·공식 승인 자동 처리 기능은 아직 완전하지 않습니다.</p></section>`;
}
const api={money,compact,roadmap,infoSummary,priorityControls,flow,plan,data};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.IFPK_V55_UI=api;
})(typeof window!=='undefined'?window:globalThis);
