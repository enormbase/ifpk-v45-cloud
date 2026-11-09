"""V51.1c: growing household budget replaces ungrounded staged 2.2/2.3m plan."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'docs'/'index.html'

def test_new_baseline_is_compounded_monthly_and_matches_snapshot_delta():
    script=r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const raw=fs.readFileSync(process.argv[1],'utf8');
const code=raw.slice(raw.indexOf('const SPENDING=['),raw.indexOf('let cashDeltaCache=null'));
const sandbox={persistent:{initialSpending:null,consumptionEvents:[]},console,assert};
vm.runInNewContext(code+`
 const expected = n=>Math.round(2400000*Math.pow(1.025,n/12));
 assert.equal(sheetGeneralBudget('2026-11'),expected(0));
 assert.equal(sheetGeneralBudget('2026-12'),expected(1));
 assert.equal(sheetGeneralBudget('2027-01'),expected(2));
 assert.equal(sheetGeneralBudget('2030-01'),expected(38));
 assert.equal(sheetGeneralBudget('2034-01'),expected(86));
 assert.ok(Math.abs(monthSpendChange('2027-01',[])-(expected(2)-2200000))<15);
 const date='2027-01';
 const newAmounts=Object.fromEntries(SPENDING.map(r=>[r.id,Math.round(r.value*2300000/2400000)]));
 const changed=monthSpendChange(date,[{date,amounts:newAmounts}]);
 assert.ok(Math.abs(changed-100000)<15,changed);
 assert.equal(monthSpendChange('2026-12',[{date,amounts:newAmounts}]),monthSpendChange('2026-12',[]));
 console.log('new baseline ok');`,sandbox);
'''
    r=subprocess.run(['node','-e',script,str(HTML)],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    assert 'new baseline ok' in r.stdout

def test_clear_disclosure_and_guardrails():
    html=HTML.read_text('utf8')
    assert '2026년 11월 월 240만원에서 매월 연 2.5% 복리 가정' in html
    assert '최신 CPI에 따른 6개월 공식 재설계' in html
    assert 'V51.1c' in html
    assert 'if(!raw||date<PLAN_START||date>PLAN_LAST)return raw;' in html
