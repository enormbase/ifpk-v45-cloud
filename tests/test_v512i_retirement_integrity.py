"""IFPK V51-2k: separate, source-aware read-only retirement reconciliation."""
import json,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
JS=str(ROOT/'docs/js/retirement_integrity_v512i.js')
DEBT=str(ROOT/'docs/js/debt_retirement_v512f.js')
F=str(ROOT/'docs/js/rolling_projection_v512b.js')

SNAP=re.search(r'const FULL_MONTHLY=Object.fromEntries\((\[.*?\])\);\s*const RETIRE_SNAPSHOT=',HTML,re.S)
assert SNAP

def run(js):
 setup=f'''const assert=require('node:assert/strict');const snap=Object.fromEntries({SNAP.group(1)});
 const serialized=JSON.stringify(snap),moduleI=require({json.dumps(JS)}),fin=require({json.dumps(F)}),debt=require({json.dumps(DEBT)});
 const prev=fin.compute(snap,[],{{asOf:'2027-05'}});assert.ok(prev.ready);
 const model={{neededRetirement:498798806,dcAfterTax:414925772,initialRetirement:666940773}};
 const full=debt.project(snap,prev,{{retirementAssets:30000000}},'2026-11');assert.ok(full.ready);
 '''
 p=subprocess.run(['node','-e',setup+js],capture_output=True,text=True,cwd=ROOT)
 assert p.returncode==0,p.stderr[-3500:]
 return p.stdout

def test_no_entry_never_pretends_proof():
 run('''const r=moduleI.audit({ready:true,retirement:{entered:false,projected:false}},model);
 assert.ok(r.ready);assert.equal(r.canCompare,false);assert.equal(r.scenarioPrepared,null);
 assert.equal(r.originalPrepared,r.dcAfterTax+r.originalPlannedRetirementSavingFV);
 assert.equal(r.baseAfterDcShortfall,83873034);
 assert.equal(r.baseSurplus,168141967);
 assert.equal(r.guards.pensionAlreadyNettedFromNeed,true);
 assert.equal(r.guards.official605MonthLedgerUnchanged,true);
 assert.equal(JSON.stringify(snap),serialized);
 ''')

def test_unknown_relation_blocks_extra():
 run('''const r=moduleI.audit(full,model,{},{});
 assert.ok(r.entered);assert.equal(r.startingFV,133559563);
 assert.equal(r.futureContributionFV,297761660);
 assert.equal(r.canCompare,false);assert.equal(r.excludedFV,0);
 assert.equal(r.scenarioDifference,null);assert.equal(JSON.stringify(snap),serialized);
 ''')

def test_within_dc_no_double_count_even_tax_confirmed():
 run('''const r=moduleI.audit(full,model,{retAssetOrigin:'within-plan',retAssetUsability:'net-confirmed'});
 assert.equal(r.canCompare,false);assert.equal(r.excludedFV,0);
 assert.equal(r.guards.dcNeverAddedTwice,true);
 assert.equal(r.guards.futureContributionsNeverAdded,true);
 ''')

def test_new_asset_but_tax_unknown_is_blocked():
 run('''const r=moduleI.audit(full,model,{retAssetOrigin:'new-independent',retAssetUsability:'tax-uncertain'});
 assert.equal(r.canCompare,false);assert.equal(r.scenarioPrepared,null);
 ''')

def test_conditional_separate_and_after_tax_only_adds_133m_once():
 run('''const r=moduleI.audit(full,model,{retAssetOrigin:'new-independent',retAssetUsability:'net-confirmed'},
 {ready:true,unfundedMonths:0,maximumUnfundedCash:0});
 assert.equal(r.canCompare,true);assert.equal(r.excludedFV,133559563);
 assert.equal(r.scenarioPrepared,800500336);assert.equal(r.scenarioDifference,301701530);
 // The same 297m of ongoing deposits is ALREADY covered by the old prepared plan.
 assert.notEqual(r.scenarioPrepared,666940773+133559563+297761660);
 assert.equal(r.guards.originalSavingAlreadyInPrepared,true);
 assert.equal(r.approved,false);assert.equal(JSON.stringify(snap),serialized);
 ''')

def test_affordability_risk_follows_without_declaring_retirement_success():
 run('''const r=moduleI.audit(full,model,{retAssetOrigin:'new-independent',retAssetUsability:'net-confirmed'},
 {ready:true,unfundedMonths:4,maximumUnfundedCash:1200000});
 assert.equal(r.canCompare,true);assert.equal(r.fundedSixMonths,false);
 assert.ok(r.liquidityStatus.includes('부족 위험'));
 assert.equal(r.guards.postRetirementCashflowRecomputed,false);
 ''')

def test_reject_stale_wrong_model_or_fake_select_value():
 run('''let r=moduleI.audit(full,{...model,initialRetirement:800000000});assert.equal(r.ready,false);
 r=moduleI.audit(full,model,{retAssetOrigin:'<script>',retAssetUsability:'net-confirmed'});
 assert.equal(r.ready,false);
 ''')

def test_web_wiring_and_minimal_customer_ui():
 assert 'V51-2k' in HTML
 assert 'LIFE PLAN STUDIO · IFPK V51-3f' in HTML
 assert HTML.index('cashflow_audit_v512h.js')<HTML.index('retirement_integrity_v512i.js')
 assert '⑫ 은퇴자산 중복 계산 확인' in HTML
 assert 'retAssetOrigin' in HTML and 'retAssetUsability' in HTML
 assert '⑫번에서 DC·IRP와 중복 여부를 점검합니다.' in HTML
 assert 'retirementIntegrityPanel' in HTML
 assert '공식 계획 적용은 잠금 상태' in HTML
