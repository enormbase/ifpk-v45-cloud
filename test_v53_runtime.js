const fs=require('fs');const vm=require('vm'),assert=require('assert');
const path=require('node:path').join(__dirname,'docs/index.html');const html=fs.readFileSync(path,'utf8');
function section(start,end){let i=html.indexOf(start),j=html.indexOf(end,i);assert(i>=0 && j>i,`missing ${start}`);return html.slice(i,j)}
const modelData=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'docs/data/v52_authoritative_677.json'),'utf8'));
console.log('JSON keys',Object.keys(modelData));
const keys=Object.keys(modelData.monthly||{}).sort();console.log('months',keys.length,keys[0],keys.at(-1));
const map=modelData.monthly;const annual=JSON.parse('['+JSON.stringify(modelData.annual||[])+']');
const originalTxt=html.match(/const MODEL=(\{.*?\});<\/script><script>/s);
assert(originalTxt,'MODEL found');
const MODEL=JSON.parse(originalTxt[1]);
const rows=MODEL.annual.split(';').map(s=>s.split(',').map(Number));
const date='2028-04';
const conversion=a=>Array.isArray(a)?{income:a[0],pension:a[1],expense:a[2],retSave:a[7],houseSave:a[8],carSave:a[9],travelSave:a[10],houseBal:a[11],carBal:a[12],travelBal:a[13],cash:a[16]}:a;
const getMonth=d=>conversion(map[d]||MODEL.monthly.find(x=>x[0]===d)?.[1]);
const ctx={Number,Math,app:{year:2028,month:4,flowExpandedYear:null},persistent:{retireMonths:{}},RETIRE_SNAPSHOT:{},ANNUAL:rows,MODEL,monthInfo:getMonth,computedGoalPlan:()=>({homeMonth:'2046-10',carMonth:'2034-10',travelMonth:'2038-10'}),goalPlanChanged:()=>false,esc:x=>String(x),KRW:x=>Math.round(+x).toLocaleString('ko-KR')+'원',COMPACT:x=>Math.abs(x)>1e8?(x/1e8).toFixed(2)+'억원':Math.abs(x)>10000?Math.round(x/1e4)+'만원':Math.round(x)+'원',MILL:x=>Number(x).toFixed(1)+'백만원',flowYearMonths:()=>'<div>month rows</div>'};
vm.createContext(ctx);
vm.runInContext(section('function v53GoalFundPanel(date){','function overviewHero(dt)'),ctx);
vm.runInContext(section('function v53FlowFundBalances(date){','function flowYearMonths(y){'),ctx);
const annualLine=html.match(/function annualTable\(\)\{return `.*?\}\s*\nfunction flowBrief/s);assert(annualLine,'annual fn');vm.runInContext(annualLine[0].replace(/\nfunction flowBrief$/,''),ctx);
const card=vm.runInContext(`v53GoalFundPanel('${date}')`,ctx);
console.log('card length',card.length,'goal cards', (card.match(/class="v53-goal-fund/g)||[]).length,'retire target', card.includes('640,166,067원'),'lifetime title', card.includes('우리 가족의 목표자금'));
assert((card.match(/class="v53-goal-fund/g)||[]).length===4);
assert(card.includes('2028년 말 은퇴자산 전망'));
assert(card.includes('월 335,598원')||card.includes('335,598원'));
const flow=vm.runInContext(`v53FlowFundBalances('${date}')`,ctx);assert(flow.includes('주택')&&flow.includes('자동차')&&flow.includes('해외여행'));
const a=vm.runInContext('annualTable()',ctx);assert(a.includes('주택 목적잔액')&&a.includes('여행 목적잔액')&&a.includes('자동차 목적잔액'));
console.log('flow sample',flow.slice(0,360));console.log('year table',a.slice(0,380));
console.log('passed!')
