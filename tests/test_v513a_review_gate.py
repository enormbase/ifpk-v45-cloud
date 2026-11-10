"""V51-3a: strictly non-authoritative local customer review gate."""
import json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
SNAP=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert SNAP

def node(code):
    text='''
const assert=require('node:assert/strict');
const snap=Object.fromEntries(%s);
const frozen=JSON.stringify(snap);
const rev=require('./docs/js/review_decisions_v513a.js');
const m=require('./docs/js/rolling_projection_v512b.js');
const g=require('./docs/js/home_bridge_v512g.js');
const h=require('./docs/js/cashflow_audit_v512h.js');
const d=require('./docs/js/affordability_v512d.js');
const sheet=require('./docs/js/source_audit_v512k.js');
const dates={asOf:'2027-05',scenarios:{borrowingCase:'base'}};
const bridge=g.link(snap,[],dates,{});
const preview=bridge.preview;
const afford=d.analyze(snap,preview,{});
const check={ready:true,negativeCount:285};
const neutralAfford=d.analyze(snap,m.compute(snap,[],dates),{});
const trial=rev.prepare(snap,check,preview,afford,dates,h.audit(snap,bridge),neutralAfford);
''' % SNAP.group(1)
    r=subprocess.run(['node','-e',text+code],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0, r.stderr[-3000:]
    return r.stdout.strip()

def test_version_placement_and_local_only_disclaimers():
    for txt in ['LIFE PLAN STUDIO · IFPK V51-3b','review_decisions_v513a.js','v513DecisionPanel()',
                '공식 변경 미적용','검토 결정만 저장','공식 계획 잠금 유지','data-v513-export']:
        assert txt in HTML
    assert HTML.index('source_audit_v512k.js') < HTML.index('review_decisions_v513a.js')

def test_six_month_packet_carries_real_baseline_and_no_mutation():
    node('''assert.equal(trial.ready,true,JSON.stringify(trial));
assert.equal(trial.payload.asOf,'2027-05');
assert.equal(trial.payload.comparison.length,6);
assert.equal(trial.payload.baselinePlanMonths,605);
assert.equal(trial.payload.comparison[0].baselineCash,snap['2027-05'][16]);
assert.equal(trial.payload.comparison[5].baselineCash,snap['2027-10'][16]);
assert.equal(trial.payload.lastBaselineCash,snap['2027-10'][16]);
assert.equal(trial.payload.lastTrialCash,trial.payload.lastBaselineCash);
assert.equal(trial.payload.baselineNegativeMonths,285);
assert.equal(trial.payload.officialApplied,false);
assert.equal(trial.payload.customerIdentityVerified,false);
assert.equal(trial.payload.postRetirementRecomputed,false);
assert.equal(trial.mayOfficiallyApply,false);
assert.equal(JSON.stringify(snap),frozen);''')

def test_block_false_certification_and_require_all_risk_acknowledgements():
    node('''assert.equal(rev.decide(trial,'approve',{},'').ok,false);
assert.equal(rev.decide(trial,'acknowledged',{},'').ok,false);
assert.equal(rev.decide(trial,'acknowledged',{limits:true,funding:true},'').ok,false);
assert.equal(rev.decide(trial,'revise',{},'').ok,false);
assert.equal(rev.decide(trial,'revise',{},'추가 계좌 확인').ok,true);
assert.equal(rev.decide(trial,'defer',{},'').ok,true);
assert.equal(JSON.stringify(snap),frozen);''')

def test_review_record_is_not_authoritative_and_archive_export_verifies_tampering():
    node('''const a=rev.decide(trial,'acknowledged',{limits:true,funding:true,evidence:true},'가족과 상의', '2026-11-11T03:20:00.000Z');
assert.equal(a.ok,true);assert.equal(a.record.label,'검토 완료·공식 보류');
for(const k of ['officialApproved','officialApplied','cloudSaved','authenticated'])assert.equal(a.record[k],false);
assert.equal(rev.verifyRecord(a.record),true);
const out=rev.exportArchive([a.record]);assert.equal(out.ok,true);
const parsed=JSON.parse(out.data);assert.equal(parsed.records.length,1);
assert.equal(parsed.records[0].reviewChecksum,trial.checksum);
a.record.review.deltaCash+=5;assert.equal(rev.verifyRecord(a.record),false);
assert.equal(rev.exportArchive([a.record]).ok,false);
assert.equal(JSON.stringify(snap),frozen);''')

def test_invalid_input_or_incomplete_source_fails_closed():
    node('''const bad=rev.prepare(snap,{ready:false},preview,afford,dates,null,neutralAfford);assert.equal(bad.ready,false);
assert.equal(rev.decide(bad,'acknowledged',{limits:true,funding:true,evidence:true}).ok,false);
const other={...snap};delete other['2056-04'];
assert.equal(rev.prepare(other,check,preview,afford,dates,null,neutralAfford).ready,false);
const e=rev.prepare(snap,check,preview,{...afford,months:afford.months.slice(0,5)},dates,null,neutralAfford);
assert.equal(e.ready,false);assert.equal(JSON.stringify(snap),frozen);''')

def test_custom_data_is_only_trial_and_does_not_write_plan():
    node('''const options={asOf:'2027-05',scenarios:{borrowingCase:'base'},actualSpending:'2600000'};
const b=g.link(snap,[],options,{}),p=b.preview;
const six=d.analyze(snap,p,{monthlyIncome:'4500000',additionalDebt:'50000'});
const changed=rev.prepare(snap,check,p,six,{...options,monthlyIncome:'4500000',additionalDebt:'50000'},h.audit(snap,b),neutralAfford);
assert.equal(changed.ready,true);assert.equal(changed.payload.parameters.monthlyIncome,'4500000');
assert.ok(changed.payload.warnings.some(w=>w.includes('6개월만 시험 적용')));
assert.equal(changed.payload.postRetirementRecomputed,false);
assert.equal(JSON.stringify(snap),frozen);''')
