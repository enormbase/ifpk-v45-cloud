"""V51-2a real-sheet 605-month read-only rolling calculations and guards."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'docs/js/rolling_preview_v512a.js'
HTML=ROOT/'docs/index.html'

def node(source):
    p=subprocess.run(['node','-e',source],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr[-2400:]
    return p.stdout.strip()

HEAD=f'''const assert=require('node:assert/strict');
const fs=require('fs');
const f=require({str(JS)!r});
const html=fs.readFileSync({str(HTML)!r},'utf8');
const match=html.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s);
assert(match,'embedded 605-month workbook not found');
const book=Object.fromEntries(JSON.parse(match[1]));
'''

def test_real_ledger_and_original_goals():
    out=node(HEAD+'''const valid=f.readLedger(book);assert.equal(valid.ready,true);assert.equal(valid.months,605);
const base=f.compute(book,[],{asOf:'2026-11'});assert.equal(base.ready,true);
assert.equal(base.cpi.correction,1);
assert.equal(base.goals.house.newSaving,345345);
assert.equal(base.goals.car.newSaving,189847);
assert.equal(base.goals.travel.newSaving,32032);
assert.equal(base.previewCashAtReview,base.baselineCashAtReview);
assert.equal(base.mayApprove,false);console.log('ok');''')
    assert out=='ok'

def test_future_review_without_fresh_data_is_not_fabricated():
    out=node(HEAD+'''const r=f.compute(book,[],{asOf:'2027-05'});
assert.equal(r.ready,true);assert.equal(r.cpi.observed,false);
assert.equal(r.cpi.source,'새 관측 없음');assert.equal(r.cpi.observedDate,'2026-10');
assert.equal(r.monthlyResults['2027-05'].projectedGeneralBudget,2429815);
assert.equal(r.monthlyResults['2027-04'].projectedGeneralBudget,null);
assert.equal(r.goals.house.confirmed,false);
assert.ok(r.warnings.length>0);console.log('ok');''')
    assert out=='ok'

def test_hypothetical_cpi_and_past_months_unchanged():
    out=node(HEAD+'''const before=JSON.stringify(book);
const base=f.compute(book,[],{asOf:'2027-05'});
const changed=f.compute(book,[],{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(changed.cpi.manual,true);assert.equal(changed.cpi.observed,false);
assert.equal(changed.cpi.observedDate,'2027-04');assert.ok(changed.cpi.correction>1);
assert.equal(changed.monthlyResults['2027-04'].previewCash,base.monthlyResults['2027-04'].previewCash);
assert.ok(changed.monthlyResults['2027-05'].previewCash<base.monthlyResults['2027-05'].previewCash);
assert.equal(JSON.stringify(book),before);console.log('ok');''')
    assert out=='ok'

def test_actual_spending_replaces_cpi_instead_of_double_counting():
    out=node(HEAD+'''const actual=f.compute(book,[],{asOf:'2027-05',actualSpending:2450000,hypotheticalCPI:124});
assert.equal(actual.ready,true);assert.equal(actual.monthlyResults['2027-05'].projectedGeneralBudget,2450000);
const future=Math.round(2450000*Math.pow(1.025,1/12));
assert.equal(actual.monthlyResults['2027-06'].projectedGeneralBudget,future);
assert.equal(actual.spendingMethod,'고객 확인 생활비 우선·미래 2.5%');console.log('ok');''')
    assert out=='ok'

def test_goal_real_balances_change_future_savings():
    out=node(HEAD+'''const estimated=f.compute(book,[],{asOf:'2027-05'});
const actual=f.compute(book,[],{asOf:'2027-05',balances:{house:25000000,car:2000000,travel:1800000}});
for(const key of ['house','car','travel']){
 assert.equal(actual.goals[key].confirmed,true);
 assert.ok(actual.goals[key].newSaving<estimated.goals[key].newSaving);
 assert.ok(actual.goals[key].projectedGoalBalance>=actual.goals[key].goal-2);
}
assert.equal(actual.monthlyResults['2027-04'].previewCash,estimated.monthlyResults['2027-04'].previewCash);
console.log('ok');''')
    assert out=='ok'

def test_bad_basis_or_bad_month_blocks_preview():
    out=node(HEAD+'''const mixed=[{id:'CPI_GENERAL',date:'2027-04',value:124,unit:'2025=100'}];
const res=f.compute(book,mixed,{asOf:'2027-05'});assert.equal(res.ready,false);
assert.equal(f.compute(book,[],{asOf:'2027-04'}).ready,false);
assert.equal(f.compute(book,[],{asOf:'2027-05',actualSpending:'abc'}).ready,false);
assert.equal(f.compute(book,[],{asOf:'2027-05',balances:{car:-10}}).ready,false);
console.log('ok');''')
    assert out=='ok'

def test_travel_index_requires_contiguous_twelve_months():
    out=node(HEAD+'''const obs=[];
for(let i=0;i<13;i++){obs.push({id:'CPI_TRAVEL',date:f.shift('2026-03',i),value:125.5+i*1.1,unit:'2020=100'});}
const out=f.compute(book,obs,{asOf:'2027-05'});
assert.equal(out.ready,true);assert.equal(out.travel.ready,true);assert.equal(out.travel.date,'2027-03');
assert.notEqual(out.goals.travel.goal,6724444);
console.log('ok');''')
    assert out=='ok'

def test_website_wiring_and_readonly_contract():
    html=HTML.read_text(encoding='utf-8')
    assert 'src="./js/rolling_preview_v512a.js"' in html
    assert 'function v512PreviewPanel()' in html
    assert 'data-v512-calc' in html
    assert '공식 계획 적용은 잠금 상태' in html
    assert '2026년 11월 월 생활비 240만원' in html
    assert 'data-v51-approve' not in html
    assert 'V51-2a · 검토용 계산' in html
