"""V51-4a: 6 source lineages / 4 domain summaries are read-only and never approve."""
from pathlib import Path
import subprocess, json, hashlib, re
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf8')
JS=ROOT/'docs/js/replan_pipeline_v514.js'

def node(script):
    p=subprocess.run(['node','-e',"const a=require('./docs/js/replan_pipeline_v514.js'); const assert=require('node:assert/strict');"+script],cwd=ROOT,text=True,capture_output=True,timeout=20)
    assert p.returncode==0,p.stderr
    return p.stdout.strip()

def test_anchor_and_review_cycle_boundary():
    node("""let c=a.reviewWindow('2026-11');assert.equal(c.firstReview,'2027-05');assert.equal(c.due,false);assert.equal(c.nextReview,'2027-05');
    c=a.reviewWindow('2027-05');assert.equal(c.due,true);assert.equal(c.latestDue,'2027-05');assert.equal(c.nextReview,'2027-11');assert.equal(c.reviewCompleted,false);
    c=a.reviewWindow('2028-05');assert.equal(c.latestDue,'2028-05');assert.equal(c.nextReview,'2028-11');""")

def test_invalid_month_rejected():
    node("""assert.throws(()=>a.reviewWindow('2026-13')); assert.throws(()=>a.reviewWindow('2026-00'));""")

def test_source_preference_no_old_rone_merging():
    node("""const s={id:'HOME_PRICE',ids:['new','old']};const e=a.lastObservation(s,[
      {id:'old',date:'2026-11',value:130},{id:'new',date:'2026-06',value:100},{id:'new',date:'2026-09',value:100.2}]);
      assert.equal(e.sourceId,'new');assert.equal(e.month,'2026-09');assert.equal(e.count,2);""")

def test_numeric_api_strings_are_read_as_numbers_but_blank_not_zero():
    node("""let e=a.lastObservation({id:'CPI_GENERAL'},[{id:'CPI_GENERAL',date:'2026-10',value:'120.73'},{id:'CPI_GENERAL',date:'2026-11',value:''}]);
       assert.equal(e.value,120.73);assert.equal(e.month,'2026-10');""")

def test_invalid_values_and_conflicting_month():
    node("""const s={id:'I',ids:['i']}; assert.equal(a.lastObservation(s,[{id:'i',date:'wrong',value:5},{id:'i',date:'2026-11',value:NaN}]),null);
    const e=a.lastObservation(s,[{id:'i',date:'2026-10',value:100},{id:'i',date:'2026-10',value:101}]);assert.equal(e.conflicting,true);""")

def test_successful_api_run_is_not_monthly_archive_proof():
    node("""const x=a.build({specs:[{id:'CPI_GENERAL',ids:['CPI_GENERAL']}],records:[],online:true,status:{latestRuns:[{id:'CPI_GENERAL',status:'ok',finishedAt:'2026-11-11T05:00:00Z'}]},nowMonth:'2026-11'});
    assert.equal(x.storedCount,0);assert.equal(x.sources[0].monthlyRunProven,false);assert.equal(x.monthlyHistory.runHistoryComplete,false);
    assert.equal(x.officialApplied,false);assert.equal(x.plan.appliedObservationMonthsVerified,false);""")

def test_failed_recent_run_not_erased_by_old_observation():
    node("""const x=a.build({specs:[{id:'MORTGAGE',ids:['MORTGAGE']}],records:[{id:'MORTGAGE',date:'2026-09',value:3.9}],online:true,
      status:{latestRuns:[{id:'MORTGAGE',status:'failed',finishedAt:'2026-11-11T01:00:00Z'}]},nowMonth:'2026-11'});
    assert.equal(x.storedCount,1);assert(x.sources[0].issues.includes('최근 API 점검 실패'));assert.equal(x.sources[0].verified,false);""")

def test_four_domains_and_fixed_retirement():
    node("""const x=a.build({specs:[{id:'HOME_PRICE',ids:['new']},{id:'DEPOSIT',ids:['DEPOSIT']},{id:'MORTGAGE',ids:['MORTGAGE']},{id:'CPI_GENERAL',ids:['CPI_GENERAL']},{id:'CPI_CAR',ids:['CPI_CAR']},{id:'CPI_TRAVEL',ids:['CPI_TRAVEL']}],records:[],nowMonth:'2026-11',asOf:'2027-05'});
    assert.deepEqual(x.domains.map(d=>d.id),['house','general','car','travel']);assert.equal(x.futureScenario,true);
    assert.equal(x.preparedForFullReplan,false);assert.equal(x.customerApproved,false);assert.equal(x.approvalButtonEnabled,false);
    assert(x.exclusions.some(t=>t.includes('승인')));""")

def test_domain_computation_from_existing_preview_not_fabricated():
    node("""const p={ready:true,asOf:'2027-05',cpi:{correction:1.01,source:'KOSIS'},environment:{homeBlocked:false,carBlocked:true,carWarning:'코드 불일치'},finance:{finance:{homePrice:600000000,homeMonthly:1675319,own:140000000,carPrice:50000000,tripPrice:6500000}},
     goals:{house:{newSaving:350000},car:{newSaving:200000},travel:{newSaving:30000}},monthlyResults:{'2027-05':{previewExpense:3222222,baselineCash:50,previewCash:45}}};
     const h=a.domainSteps('house',p),c=a.domainSteps('car',p),g=a.domainSteps('general',p);
     assert(h.values.some(x=>x.value===1675319));assert.equal(c.blocked,true);assert.equal(c.values.length,0);
     assert(g.values.some(x=>x.value===-5));""")

def test_reference_data_snapshots_untouched():
    from zipfile import ZipFile
    z=ZipFile('/mnt/data/IFPK_V51_3f_GitHub_upload(1).zip')
    for f in ['docs/data/v512k_authoritative_605.json','docs/data/v512k_reconciliation_605.csv','docs/data/v512k_audit_summary.json']:
        assert (ROOT/f).read_bytes()==z.read(f)

def test_html_keeps_existing_advanced_review_and_integrates_v514():
    for k in ['IFPK V51-4a','replan_pipeline_v514.js','function v514PipelinePanel(data)','v514PipelinePanel(pipeline)',
       'id="v513f-deep"','v512PreviewPanel()','v513DecisionPanel()','월별 자료 수집·저장과 6개월 공식 재설계',
       '고급 재설계 비교·고객 검토 기록']:
        assert k in HTML,k
    assert 'return {...packet,payload' in HTML
    assert 'rawPreview:data' in HTML
    assert 'V51-4a · 수집·재설계 준비 현황' in HTML
    assert '<script src="./js/replan_pipeline_v514.js"></script>' in HTML

def test_exports_are_read_only():
    source=JS.read_text('utf8')
    for k in ['officialApplied:false','customerApproved:false','runHistoryComplete:false','appliedObservationMonthsVerified:false']:
        assert k in source
    for bad in ['fetch(', 'localStorage.', 'supabase.from(', 'approvePlan(']:
        assert bad not in source
