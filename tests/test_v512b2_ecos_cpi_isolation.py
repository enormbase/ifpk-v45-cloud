"""V51-2b.2: official ECOS item CPI generic unit anchoring and independent preview."""
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'docs/index.html'
JS=ROOT/'docs/js/rolling_projection_v512b.js'
HEAD=r'''const assert=require('node:assert/strict');
const fs=require('node:fs');
const v=require('__MODULE_PATH__');
const date=require('./docs/js/rolling_preview_v512a.js');
const html=fs.readFileSync('__HTML_PATH__','utf8');
const m=html.match(/const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=/s);
assert.ok(m);const book=Object.fromEntries(JSON.parse(m[1]));
const series=(id,item,val=125,start='2027-02',months=3)=>{
 const a=[];
 for(let i=0;i<12;i++)a.push({id,date:date.shift('2020-01',i),value:100,unit:'지수',provider:'ECOS',sourceCode:'901Y009/'+item});
 for(let i=0;i<months;i++)a.push({id,date:date.shift(start,i),value:val,unit:'지수',provider:'ECOS',sourceCode:'901Y009/'+item});
 return a;
};
'''.replace('__MODULE_PATH__',str(JS)).replace('__HTML_PATH__',str(HTML))


def run(js):
    res=subprocess.run(['node','-e',HEAD+js],cwd=ROOT,text=True,capture_output=True)
    assert res.returncode==0,res.stderr[-3500:]


def test_collector_car_generic_unit_with_verified_2020_anchor_calculates():
    run('''const records=series('CPI_CAR','C123',121.5,'2027-02',3);
const r=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.carBlocked,false);
assert.equal(r.environment.car.ready,true);
assert.match(r.environment.car.source,/2020=100 기준 확인/);
assert.ok(r.finance.carPrice>v.CAR_BASE.price);
assert.equal(r.monthlyResults['2027-04'].previewCash,r.monthlyResults['2027-04'].baselineCash);
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
''')


def test_collector_travel_generic_unit_with_verified_anchor_calculates():
    run('''const records=series('CPI_TRAVEL','T321',132,'2026-05',12);
const r=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.travelBlocked,false);
assert.equal(r.environment.travel.ready,true);assert.ok(r.finance.tripPrice>v.TRIP_BASE.price);
assert.ok(r.goals.travel.newSaving>r.goals.travel.oldSaving);
''')


def test_invalid_auto_cpi_unit_holds_only_auto_and_preserves_general_cpi_and_trip():
    run('''const records=[{id:'CPI_CAR',date:'2027-04',value:120,unit:'2025=100',provider:'ECOS',sourceCode:'901Y009/C123'}, ...series('CPI_TRAVEL','T321',132,'2026-05',12)];
const r=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.carBlocked,true);
assert.equal(r.environment.travelBlocked,false);
assert.equal(r.goals.car.active,false);assert.equal(r.finance.carPrice,v.CAR_BASE.price);
assert.equal(r.finance.carMonthly,v.CAR_BASE.monthlyPayment);
assert.ok(r.finance.tripPrice>v.TRIP_BASE.price);
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
assert.equal(r.monthlyResults['2027-04'].previewCash,r.monthlyResults['2027-04'].baselineCash);
assert.equal(r.mayApprove,false);assert.ok(r.partialModules.some(x=>x.includes('자동차')));
''')


def test_invalid_travel_holds_travel_only_and_keeps_general_and_car():
    run('''const records=[{id:'CPI_TRAVEL',date:'2027-04',value:120,unit:'2025=100'}, ...series('CPI_CAR','C123',121.5,'2027-02',3)];
const r=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.travelBlocked,true);
assert.equal(r.environment.carBlocked,false);assert.equal(r.goals.travel.active,false);
assert.equal(r.finance.tripPrice,v.TRIP_BASE.price);assert.ok(r.finance.carPrice>v.CAR_BASE.price);
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
''')


def test_missing_origin_or_missing_full_2020_anchor_fails_closed_locally():
    run('''for (const bad of [
 [{id:'CPI_CAR',date:'2027-04',value:123,unit:'지수'}],
 [{id:'CPI_CAR',date:'2027-04',value:123,unit:'지수',provider:'ECOS',sourceCode:'901Y009/C123'}],
 series('CPI_CAR','C123',123,'2027-02',3).map(x=>x.date.startsWith('2020-')?{...x,value:92}:x),
]) { const r=v.compute(book,bad,{asOf:'2027-05',hypotheticalCPI:124});
 assert.equal(r.ready,true);assert.equal(r.environment.carBlocked,true);assert.equal(r.finance.carPrice,v.CAR_BASE.price);
 assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
}
''')


def test_mixed_ecos_item_codes_same_id_and_duplicate_conflicts_block_module():
    run('''const good=series('CPI_CAR','C123',120,'2027-02',3);
for(const records of [
 good.map((x,i)=>i===1?{...x,sourceCode:'901Y009/OTHER'}:x),
 [...good,{...good.at(-1),value:140}],
]) {const r=v.compute(book,records,{asOf:'2027-05',hypotheticalCPI:124});
 assert.equal(r.ready,true);assert.equal(r.environment.carBlocked,true);
 assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
}
''')


def test_all_three_other_indices_bad_still_cpi_preview_runs_without_official_approval():
    run('''const rec=[
 {id:'HOME_PRICE_APT_DAEJEON_SEOGU_BASE202606',date:'2026-06',value:99,unit:'지수'},
 {id:'CPI_CAR',date:'2027-04',value:123,unit:'2025=100'},
 {id:'CPI_TRAVEL',date:'2027-04',value:121,unit:'2025=100'},
];
const r=v.compute(book,rec,{asOf:'2027-05',hypotheticalCPI:124});
assert.equal(r.ready,true);assert.equal(r.environment.homeBlocked,true);
assert.equal(r.environment.carBlocked,true);assert.equal(r.environment.travelBlocked,true);
assert.deepEqual(Object.keys(r.goals).filter(x=>r.goals[x].active),[]);
assert.equal(r.monthlyResults['2027-05'].previewGeneral,2465005);
assert.equal(r.monthlyResults['2027-04'].baselineCash,r.monthlyResults['2027-04'].previewCash);
assert.equal(r.partialModules.length,3);assert.equal(r.mayApprove,false);
''')


def test_invalid_manual_car_entry_remains_explicit_input_error():
    run('''const r=v.compute(book,[],{asOf:'2027-05',scenarios:{carMA3:'abc'}});
assert.equal(r.ready,false);assert.match(r.reason,/carMA3/);
''')


def test_site_independent_warnings_and_readonly_labels():
    html=HTML.read_text('utf8')
    assert 'V51-2g · 은퇴 전 롤링 검토 · 공식 계획 미변경' in html
    assert '자동차 지표만 검증 보류' in html
    assert '여행 지표만 검증 보류' in html
    assert '주택 항목만 계산 보류' in html
    assert '전국 CPI·일반소비와 다른 정상 분야 미리보기는 계속 계산할 수 있어' in html
    assert '공식 계획 적용은 잠금 상태' in html
