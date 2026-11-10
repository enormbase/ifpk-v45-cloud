"""V51-4a regression: no phantom CPI charge against the official 605-month ledger."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'docs' / 'index.html'
LEDGER = ROOT / 'docs' / 'data' / 'v512k_authoritative_605.json'


def test_neutral_consumption_changes_zero_across_full_ledger():
    """Code-execute the ACTUAL inline browser functions, not a reimplementation."""
    js = f'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync({json.dumps(str(HTML))},'utf8');
const a=src.indexOf('const SPENDING=[');
const b=src.indexOf('// V21 local plan preview.', a);
assert(a>0 && b>a);
const extracted=src.slice(a,b);
assert(!extracted.includes('legacySheetGeneralBudget'));
const monthly=JSON.parse(fs.readFileSync({json.dumps(str(LEDGER))},'utf8')).monthly;
const ctx={{
    persistent:{{initialSpending:null,consumptionEvents:[],consumption:null,consumptionStart:null}},
    INITIAL_MONTHLY:monthly,
    app:{{year:2027,month:1}},
    dkey:(y,m)=>`${{y}}-${{String(m).padStart(2,'0')}}`,
    RETIRE_START:'2056-04', PLAN_START:'2026-11',
}};
vm.createContext(ctx);
vm.runInContext(extracted+`\n
const assertTest=(cond,msg)=>{{if(!cond)throw Error(msg)}};
assertTest(BASE_GENERAL===2400000,'240만원 기준액');
assertTest(sheetGeneralBudget('2026-11')===2400000,'2026.11');
assertTest(sheetGeneralBudget('2027-01')===2409897,'2027.01 CPI');
assertTest(sheetGeneralBudget('2030-01')===2595196,'2030.01 CPI');
for(const date of Object.keys(INITIAL_MONTHLY)){{
 assertTest(monthSpendChange(date)===0,'unexpected change: '+date);
 assertTest(totalCashDelta(date)===0,'unexpected cash carry: '+date);
}}
const x=INITIAL_MONTHLY['2027-01'];
assertTest(x[2]===3770716,'authoritative living costs');
assertTest(x[0]===4184597,'authoritative inflow');
assertTest(x[16]===111747,'official cumulative cash 2027-01');
assertTest(x[2]+monthSpendChange('2027-01')===3770716,'no duplicate CPI');
const z=INITIAL_MONTHLY['2033-01'];
assertTest(z[0]===5862128,'spouse income included');
assertTest(z[16]===-31221584,'do not hide unfunded balance');

// Customer increases the baseline food budget by KRW 100,000, without touching the official ledger.
const updated=originalSpend();updated.food+=100000;
persistent.initialSpending=updated;invalidateSpendingCache();
assertTest(monthSpendChange('2026-11')===100000,'customer adjustment 2026.11');
assertTest(Math.abs(monthSpendChange('2027-01')-100000*spendingFactor('2027-01'))<=2,'customer adjustment CPI');
assertTest(totalCashDelta('2027-01')>300000,'customer adjustment carried to future');
// Reset. A dated event must apply only from its effective month.
persistent.initialSpending=null;
persistent.consumptionEvents=[];
invalidateSpendingCache();
const custom=expensePlanAt('2027-01');custom.food+=50000;
persistent.consumptionEvents=[{{date:'2027-01',amounts:custom}}];invalidateSpendingCache();
assertTest(monthSpendChange('2026-12')===0,'no retroactive change');
assertTest(monthSpendChange('2027-01')===50000,'dated customer event');
assertTest(totalCashDelta('2026-12')===0,'no historical effect');
assertTest(totalCashDelta('2027-01')===50000,'current month cash delta');
assertTest(monthSpendChange('2027-02')>0,'future inflation of customer event');
assertTest(INITIAL_MONTHLY['2027-01'][2]===3770716,'official immutable');
`,ctx);
console.log('PASS baseline 605, 2027 CPI, spouse inflow, customer override, dated event');
'''
    run = subprocess.run(['node', '-e', js], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stderr[:3000]
    assert 'PASS baseline 605' in run.stdout


def test_v514a_correct_label_and_unchanged_frozen_source():
    h = HTML.read_text(encoding='utf-8')
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    assert 'LIFE PLAN STUDIO · IFPK V51-4a' in h
    assert 'legacySheetGeneralBudget' not in h
    assert 'const FULL_MONTHLY=Object.fromEntries(' in h
    assert ledger['meta']['months'] == 605
    assert ledger['meta']['negativeCashMonthsBeforeRetirement'] == 285
    assert ledger['meta']['firstNegativeMonth'] == '2027-02'


def test_both_replan_engines_use_authoritative_consumption_curve():
    """V512A and V512B must not rebase a sheet already on the CPI curve."""
    js = f'''
const assert=require('node:assert/strict');
const snapshot=require({json.dumps(str(LEDGER))}).monthly;
const original=require({json.dumps(str(ROOT/'docs/js/rolling_preview_v512a.js'))});
const plan=require({json.dumps(str(ROOT/'docs/js/rolling_projection_v512b.js'))});
const a=original.compute(snapshot,[],{{asOf:'2027-05'}});
const b=plan.compute(snapshot,[],{{asOf:'2027-05'}});
assert(a.ready&&b.ready);
for(const date of ['2026-11','2027-01','2027-12','2030-12','2033-01','2039-10','2044-12','2056-03']){{
  const row=snapshot[date];
  assert.equal(a.monthlyResults[date].monthlyExpenseBase,row[2],date+' A expense');
  assert.equal(b.monthlyResults[date].baselineExpense,row[2],date+' B expense');
  assert(Math.abs(a.monthlyResults[date].baselineCash-row[16])<=100,date+' A cash');
  assert(Math.abs(b.monthlyResults[date].baselineCash-row[16])<=100,date+' B cash');
}}
assert.equal(original.legacyBudget('2027-01'),original.currentBudget('2027-01'));
assert.equal(snapshot['2027-01'][2],3770716);
console.log('PASS both replan engine baselines aligned with authoritative ledger');
'''
    run = subprocess.run(['node', '-e', js], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert run.returncode == 0, run.stderr[:3000]
    assert 'PASS both replan' in run.stdout
