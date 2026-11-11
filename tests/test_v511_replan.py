"""V52 uses the approved 677-month input as immutable reference."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'docs'/'js'/'replan_v51.js'
HTML=ROOT/'docs'/'index.html'

def node(script):
    p=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
    if p.returncode:
        raise AssertionError(f'node failure: {p.stderr[:2000]}')
    return p.stdout.strip()

JS_HEAD=f'''
const assert=require('node:assert/strict');
const fs=require('node:fs');
const v=require({str(JS)!r});
const html=fs.readFileSync({str(HTML)!r},'utf8');
const rows=JSON.parse(html.match(/const FULL_MONTHLY=Object.fromEntries\\((\\[.*?\\])\\);\\s*const RETIRE_SNAPSHOT=/s)[1]);
const snapshot=Object.fromEntries(rows);
const before={{monthlySaving:345345,monthlyLoanPayment:1675319,ownCashGoal:141486810,newHomeFuture:763747266,oldHomeFuture:362779952}};
const after={{monthlySaving:385888,monthlyLoanPayment:1675319,ownCashGoal:152989929,newHomeFuture:763812596,oldHomeFuture:362810984}};
const verified={{ready:true,verified:true,before,after,differences:{{monthlySaving:40543,monthlyLoanPayment:0,ownCashGoal:11503119}}}};
'''

class V511EngineTests(unittest.TestCase):
    def test_real_ledger_integrity(self):
        out=node(JS_HEAD+'''
const status=v.inspectLedger(snapshot);
assert.equal(status.ready,true);assert.equal(status.months,677);
assert.ok(status.maxCashMismatch<=2);assert.ok(status.maxNetMismatch<=2);
console.log('ledger ok');''')
        self.assertIn('ok',out)
    def test_partial_preview_math_and_immutability(self):
        out=node(JS_HEAD+'''
const old=JSON.stringify(snapshot);
const sim=v.simulateHousing(snapshot,verified);
assert.equal(sim.ready,true);assert.equal(sim.partial,true);
assert.equal(sim.months,677);assert.equal(sim.inputs.deltaSave,40543);
assert.equal(sim.inputs.deltaEvent,11503119);
assert.equal(sim.finalCashDelta,-40543*239);
// The base is the currently approved 677-month ledger, not the obsolete V51.1 fixture.
const baselineDeficits=Object.entries(snapshot).filter(([month,row])=>month<'2056-04' && row[16]<0).length;
assert.equal(sim.baseDeficitCount,baselineDeficits);
assert.ok(sim.deficitCount>=sim.baseDeficitCount);
assert.equal(snapshot['2026-11'][8],345345);assert.equal(old,JSON.stringify(snapshot));
assert.equal(sim.projected['2026-11'].houseSave,385888);
assert.equal(sim.projected['2046-10'].homeEvent,152989929);
assert.equal(sim.projected['2046-10'].eventTransfer-snapshot['2046-10'][14],11503119);
console.log('simulated only; original snapshot unchanged');''')
        self.assertIn('unchanged',out)
    def test_approval_always_locked_when_some_areas_pending(self):
        out=node(JS_HEAD+'''
const report=v.buildReview(snapshot,verified,[]);
assert.equal(report.approval.mayApprove,false);
assert.equal(report.approval.areas.length,6);
assert.equal(report.approval.areas.find(x=>x.id==='housing').status,'partial');
assert.equal(report.approval.areas.find(x=>x.id==='retirement').status,'pending');
console.log('locked');''')
        self.assertEqual(out,'locked')
    def test_mixed_index_bases_are_rejected(self):
        out=node(JS_HEAD+'''
const r=v.inspectIndexBases([{id:'CPI_GENERAL',value:100,unit:'2020=100'},{id:'CPI_GENERAL',value:105,unit:'2025=100'}],{CPI_GENERAL:['CPI_GENERAL']});
assert.equal(r[0].ready,false);
const status=v.buildReview(snapshot,verified,[{id:'CPI_GENERAL',value:100,unit:'2020=100'},{id:'CPI_GENERAL',value:105,unit:'2025=100'}]);
assert.equal(status.house.ready,false);
console.log('basis guarded');''')
        self.assertIn('guarded',out)
    def test_wrong_plan_basis_rejected(self):
        out=node(JS_HEAD+'''
const wrong={...verified,before:{...before,monthlySaving:999999}};
const x=v.simulateHousing(snapshot,wrong);assert.equal(x.ready,false);
console.log('basis guard');''')
        self.assertIn('guard',out)
    def test_missing_month_rejected(self):
        out=node(JS_HEAD+'''
delete snapshot['2027-03'];
assert.equal(v.inspectLedger(snapshot).ready,false);
console.log('missing');''')
        self.assertIn('missing',out)
    def test_site_includes_new_module_and_no_approval_write(self):
        html=HTML.read_text(encoding='utf-8')
        self.assertIn('src="./js/replan_v51.js"',html)
        self.assertIn('function v51ReviewPanel()',html)
        self.assertIn('새 계획 공식 적용 · 통합 검증 전',html)
        self.assertIn('현재 재무계획에 적용 중인 값',html)
        self.assertIn('새 경제지표로 계산한 예상값 (적용 전)',html)
        self.assertIn('6개월 재설계 · 6개 분야 변경 전후 검토',html)
        self.assertIn('2026년 6월 = 100',html)
        self.assertNotIn('data-v51-approve',html)
if __name__=='__main__': unittest.main()
