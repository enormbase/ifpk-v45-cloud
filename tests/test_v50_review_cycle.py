"""V50 6개월 점검 · 실측 미리보기 vs 공식계획 불변 검증."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ReviewCycleTest(unittest.TestCase):
    def test_browser_script_and_preview_wiring(self):
        html=(ROOT/'docs/index.html').read_text(encoding='utf-8')
        self.assertIn('LIFE PLAN STUDIO · IFPK V51.1',html)
        self.assertIn('./js/review_cycle_v50.js',html)
        self.assertIn('v50ReviewPanel()',html)
        self.assertIn('v50ReviewBrief()',html)
        self.assertIn('data-v50-record',html)
        self.assertIn('변경안 공식 적용 · 검증 전',html)

    @unittest.skipUnless(shutil.which('node'),'Node.js unavailable')
    def test_pure_engine_and_safety_barriers(self):
        code=r'''const assert=require('node:assert/strict');
        const v=require('./docs/js/review_cycle_v50.js');
        assert.equal(v.cycle('2026-11').nextDue,'2027-05');
        assert.equal(v.cycle('2027-04').due,false);
        assert.equal(v.cycle('2027-05').due,true);
        assert.equal(v.cycle('2027-05').nextDue,'2027-11');
        assert.equal(v.cycle('2028-05').lastDue,'2028-05');
        assert.equal(v.cycle('2028-05').nextDue,'2028-11');
        assert.throws(()=>v.cycle('2027-13'));
        const approved={monthlySaving:345345,monthlyLoanPayment:1675319,ownCashGoal:141486810,newHomeFuture:763747266,oldHomeFuture:362779952};
        const after={...approved,id:'weighted',monthlySaving:370000,monthlyLoanPayment:1800000};
        const status={published:true,homeImpact:{status:'ready',approved,scenarios:[after],vintage:{homePrice:'2026-09',deposit:'2026-08',mortgage:'2026-08'}}};
        const x=v.reviewReadiness(status);
        assert.equal(x.preview.ready,true);assert.equal(x.preview.differences.monthlySaving,24655);
        assert.equal(x.mayApprove,false);
        assert.equal(x.checks.filter(c=>c.ready).length,2);
        assert.equal(v.reviewReadiness({...status,published:false}).preview.ready,false);
        const incomplete=v.reviewReadiness({published:true,homeImpact:{approved,scenarios:[{id:'weighted',monthlySaving:123}]}});
        assert.equal(incomplete.preview.ready,false);
        const record=v.makeReviewRecord('2027-05',x.preview,'2027-05-03T03:00:00Z');
        assert.equal(record.status,'자료 확인(공식 미승인)');assert.equal(record.diffMonthlySaving,24655);
        assert.deepEqual(status.homeImpact.approved,approved);
        assert.throws(()=>v.makeReviewRecord('2027-05',{ready:false}));
        console.log('V50 engine tests OK');'''
        output=subprocess.run(['node','-e',code],cwd=ROOT,capture_output=True,text=True,timeout=12)
        self.assertEqual(output.returncode,0,output.stderr)
        self.assertIn('tests OK',output.stdout)

if __name__=='__main__': unittest.main()
