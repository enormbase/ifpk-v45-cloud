"""V51-3b: only 4 dynamic domains; fixed retirement assumptions; conditional mortgage bridge."""
import re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf8')
MATCH=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert MATCH
RETIRE=re.search(r'const RETIRE_SNAPSHOT=Object.fromEntries\(Object.entries\((\{.*?\})\)\.map',HTML,re.S)
assert RETIRE

def node(js):
    code="""
const assert=require('node:assert/strict');
const ledger=Object.fromEntries(%s);
const rs=Object.fromEntries(Object.entries(%s).map(([k,v])=>[k,{living:v[0],pension:v[1],insurance:v[2],withdraw:v[3],balance:v[4]}]));
const saved=JSON.stringify(ledger),retSaved=JSON.stringify(rs);
const preview=require('./docs/js/rolling_projection_v512b.js');
const scope=require('./docs/js/review_scope_v513b.js');
const baseline=preview.compute(ledger,[],{asOf:'2027-05',scenarios:{borrowingCase:'base'}});
const fixed=scope.classification(baseline,{});
const metrics={initialRetirement:666940773,finalRetirement:386865490,neededRetirement:498798806};
""" % (MATCH.group(1),RETIRE.group(1))
    p=subprocess.run(['node','-e',code+js],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr[-3500:]
    return p.stdout

def test_version_and_policy_are_customer_facing():
    for s in ['V51-3b','review_decisions_v513a.js','review_scope_v513b.js',
              '경제지표는 4개 분야만 자동 갱신','국민연금·DC·IRP는 외부 경제지표 발표만으로 다시 추정하지 않습니다',
              '은퇴 후 인출액 영향 시험', '공식 변경 미적용', '검토 결정만 저장']:
        assert s in HTML

def test_only_four_external_domains_and_retirement_fixed():
    node('''assert.equal(fixed.ready,true);
assert.deepEqual(fixed.categories.map(x=>x.label),['주택','일반소비','자동차','해외여행']);
assert.equal(scope.fixed.wageAnnual,.025);assert.equal(scope.fixed.retirementInflationAnnual,.025);
assert.equal(scope.fixed.retirementReturnAnnual,.04);
assert.equal(fixed.retirement.apiReestimate,false);assert.equal(fixed.retirement.pensionReestimate,false);
assert.equal(fixed.retirement.dcReestimate,false);assert.equal(fixed.retirement.irpReestimate,false);
assert.deepEqual(scope.requiredChecks(fixed).mandatory.filter(x=>x.id==='mortgage').map(x=>x.required),[false]);
assert.equal(JSON.stringify(ledger),saved);assert.equal(JSON.stringify(rs),retSaved);''')

def test_no_mortgage_change_preserves_baseline_end_balance():
    node('''const impact=scope.mortgageRetirement(rs,metrics,fixed);
assert.equal(impact.ready,true);assert.equal(impact.changed,false);
assert.equal(impact.baselineFinal,386865490);assert.equal(impact.trialFinal,386865490);
assert.equal(impact.deltaFinal,0);assert.equal(impact.affectedMonths,0);
assert.equal(JSON.stringify(rs),retSaved);''')

def test_new_mortgage_rate_propagates_only_direct_postretirement_cash_impact():
    node('''const trial=preview.compute(ledger,[],{asOf:'2027-05',scenarios:{mortgageRate:'4.5',borrowingCase:'base'}});
assert.equal(trial.ready,true,JSON.stringify(trial));
const impactScope=scope.classification(trial,{mortgageRate:'4.5'});
assert.equal(impactScope.retirement.triggeredByMortgage,true);
assert.equal(impactScope.retirement.pensionReestimate,false);
assert.equal(impactScope.retirement.dcReestimate,false);
assert.equal(scope.requiredChecks(impactScope).mandatory.find(x=>x.id==='mortgage').required,true);
const res=scope.mortgageRetirement(rs,metrics,impactScope);
assert.equal(res.ready,true,JSON.stringify(res));assert.equal(res.changed,true);
assert.equal(res.affectedMonths,247);assert.notEqual(res.monthlyMortgageChange,0);
assert.equal(res.trialFirstWithdrawal,5625415+res.monthlyMortgageChange);
assert.equal(Math.sign(res.trialFinal-res.baselineFinal),-Math.sign(res.monthlyMortgageChange));
assert.ok(res.examples.some(x=>x.month==='2076-11'&&x.monthlyMortgageChange===0));
assert.equal(res.retirementAnnualReturn,.04);
assert.equal(JSON.stringify(ledger),saved);assert.equal(JSON.stringify(rs),retSaved);''')

def test_unrelated_cpi_and_car_inputs_do_not_recalculate_pension_dc_or_retirement():
    node('''const c=scope.classification(baseline,{hypotheticalCPI:'123',carMA3:'125'});
assert.equal(c.retirement.triggeredByMortgage,false);
assert.equal(c.retirement.pensionReestimate,false);assert.equal(c.retirement.dcReestimate,false);
assert.equal(c.categories.find(x=>x.id==='general').hasNewInput,true);
assert.equal(c.categories.find(x=>x.id==='car').hasNewInput,true);
assert.equal(scope.mortgageRetirement(rs,metrics,c).deltaFinal,0);''')

def test_unverified_retirement_asset_is_conditional_not_automatically_added():
    node('''const c=scope.classification(baseline,{retirementAssets:'30000000'});
assert.equal(c.retirement.accountEvidenceNeeded,true);
assert.equal(c.retirement.triggeredByVerifiedAccount,false);
assert.equal(c.officialApply,false);
assert.equal(scope.requiredChecks(c).mandatory.find(x=>x.id==='account').required,true);
const bad=scope.mortgageRetirement({},metrics,{...c,retirement:{...c.retirement,triggeredByMortgage:true}});
assert.equal(bad.ready,false);''')
