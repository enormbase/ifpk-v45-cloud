"""V51-3f customer-facing hub summaries, source boundaries, and approved ledger immutability."""
from pathlib import Path
import subprocess, json, re
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text('utf8')
JS=(ROOT/'docs/js/replan_hub_v513f.js').read_text('utf8')

def run(node):
 p=subprocess.run(['node','-e',"const a=require('./docs/js/replan_hub_v513f.js');const assert=require('node:assert/strict');"+node],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 return p.stdout.strip()

def test_all_six_source_descriptors_and_no_false_collector_success():
 run('''const specs=[{id:'H',label:'지수',ids:['new','old']},{id:'C',label:'물가',ids:['c']}];
 const records=[{id:'old',date:'2026-07',value:125},{id:'new',date:'2026-09',value:100.6},{id:'old',date:'2026-09',value:140}];
 const s=a.summarize({specs,records,online:false,schedule:{anchor:'2026-11',nextDue:'2027-05'},asOf:'2027-05'});
 assert.equal(s.observed,1);assert.equal(s.total,2);assert.equal(s.indicators[0].sourceId,'new');assert.equal(s.indicators[0].value,100.6);
 assert.equal(s.indicators[1].hasObservation,false);assert.equal(s.policy.collectionSuccessNotAssumed,true);assert.equal(s.policy.automaticApproval,false);''')

def test_failing_run_is_not_an_observation():
 run('''let s=a.summarize({specs:[{id:'CPI',ids:['c']}],records:[],status:{latestRuns:[{id:'c',status:'failed'}]},online:true});
 assert.equal(s.indicators[0].state,'수집 오류 확인 필요');assert.equal(s.observed,0);assert.equal(s.releaseTime,null);''')

def test_last_valid_and_stale_label():
 run('''let s=a.summarize({specs:[{id:'CPI',ids:['c']}],records:[{id:'c',date:'garbage',value:5},{id:'c',date:'2026-09',value:113},{id:'c',date:'2026-08',value:112}],status:{estimates:[{id:'c',stale:true}]}});
 assert.equal(s.indicators[0].month,'2026-09');assert.equal(s.indicators[0].state,'기록 있음 · 최신성 점검');''')

def test_approved_status_never_marked_applied_even_with_trial():
 run('''const s=a.summarize({specs:[],preview:{ready:true,payload:{deltaCash:-257364}},asOf:'2027-05'});
 assert.equal(s.review.deltaCash,-257364);assert.equal(s.review.officialApplied,false);assert.equal(s.policy.retirementParametersFixed,true);''')

def test_main_tab_and_developer_details_separated():
 for k in ['IFPK V51-3f','replan_hub_v513f.js','v513fHubPanel()','id="v513f-hub"','id="v513f-deep"','data-v513f-open-details','V513F_ADVANCED_OPEN','v512PreviewPanel()','v513DecisionPanel()']:
  assert k in HTML,k
 assert 'V51-3f · 수집·재설계 현황' in HTML
 assert 'v513fHubPanel()' in HTML[HTML.index('function dataPage(){'):HTML.index('function checkPage(){')]
 assert "const FULL_MONTHLY=Object.fromEntries(" in HTML
 assert '월별 자료 수집·저장과 6개월 공식 재설계' in HTML
