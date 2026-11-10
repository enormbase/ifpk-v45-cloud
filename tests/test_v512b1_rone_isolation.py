"""V51-2b.1: R-ONE '지수' canonical unit is accepted only with verified 2026-06=100 anchor.
Incompatible home series block only housing, not unrelated CPI previews."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'docs/js/rolling_projection_v512b.js'
HTML=ROOT/'docs/index.html'
HEAD=f'''const assert=require('node:assert/strict');
const fs=require('fs');const v=require({str(JS)!r});const base=require('./docs/js/rolling_preview_v512a.js');
const html=fs.readFileSync({str(HTML)!r},'utf8');
const m=html.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s);
assert.ok(m,'605-month ledger');const book=Object.fromEntries(JSON.parse(m[1]));
'''
def run(code):
    p=subprocess.run(['node','-e',HEAD+code],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0, p.stderr

def test_official_collector_generic_index_unit_valid_with_verified_anchor():
    run('''const records=[];
for(let i=0;i<9;i++) records.push({id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:base.shift('2026-06',i),value:100+(i===0?0:.2*i),unit:'지수',provider:'R-ONE'});
const scenario=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(scenario.ready,true);assert.equal(scenario.environment.homeBlocked,false);
assert.equal(scenario.environment.homeActual.ready,true);
assert.ok(scenario.finance.homePrice>v.HOME_BASE.newPrice);
assert.ok(scenario.goals.house.active);
assert.ok(scenario.monthlyResults['2027-05'].previewGeneral>scenario.monthlyResults['2027-05'].baselineGeneral);
assert.equal(scenario.monthlyResults['2027-04'].baselineCash,scenario.monthlyResults['2027-04'].previewCash);
''')

def test_bad_rone_basis_does_not_stop_general_cpi_preview():
    run('''const records=[{id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:'2026-06',value:98,unit:'지수'}];
const s=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124,scenarios:{carMA3:121.5,travelMA12:132}});
assert.equal(s.ready,true);assert.equal(s.environment.homeBlocked,true);
assert.equal(s.goals.house.active,false);assert.equal(s.goals.house.blocked,true);
assert.equal(s.finance.homePrice,v.HOME_BASE.newPrice);
assert.equal(s.finance.homeMonthly,v.HOME_BASE.existingLoanMonthly);
assert.ok(s.finance.carPrice>v.CAR_BASE.price);
assert.ok(s.finance.tripPrice>v.TRIP_BASE.price);
assert.ok(s.monthlyResults['2027-05'].previewGeneral>s.monthlyResults['2027-05'].baselineGeneral);
assert.equal(s.monthlyResults['2027-04'].previewCash,s.monthlyResults['2027-04'].baselineCash);
assert.equal(s.mayApprove,false);
''')

def test_generic_index_without_anchor_freezes_only_house_and_keeps_no_false_actual():
    run('''const records=[{id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:'2026-09',value:101,unit:'지수'}];
const s=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(s.ready,true);assert.equal(s.environment.homeBlocked,true);
assert.equal(s.environment.homeActual.ready,false);
assert.equal(s.finance.homePrice,v.HOME_BASE.newPrice);
''')

def test_explicit_new_basis_series_without_anchor_supports_121_month_cagr():
    run('''const records=[];for(let i=0;i<121;i++)records.push({id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:base.shift('2027-01',i),value:100*Math.pow(1.001,i),unit:'2026-06=100'});
const r=v.homeGrowth(records,'2037-05');assert.equal(r.ready,true);assert.equal(r.invalid,undefined);
''')

def test_ui_discloses_house_only_hold_and_keeps_readonly():
    s=HTML.read_text(encoding='utf8')
    assert '주택 항목만 계산 보류' in s
    assert '전국 CPI·일반소비와 다른 정상 분야 미리보기는 계속 계산할 수 있어' in s
    assert 'V51-2k · 은퇴 전 롤링 검토 · 공식 계획 미변경' in s
