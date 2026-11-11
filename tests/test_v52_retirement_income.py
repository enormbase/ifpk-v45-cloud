"""V52 acceptance checks for the 90-year / 2.7m A-case and decomposed inflows.
Assesses the authoritative exported Sheet snapshot and the deployed HTML payload.
"""
from pathlib import Path
import json,math,re,subprocess,zipfile,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')
DATA=json.loads((ROOT/'docs/data/v52_authoritative_677.json').read_text(encoding='utf8'))
META=json.loads((ROOT/'docs/data/v52_audit_677.json').read_text(encoding='utf8'))
MONTHLY=DATA['monthly'];RETIRE=DATA['retirement']; INCOME=DATA['incomes']; ANNUAL=DATA['annual']

def js_json(name):
    pos=HTML.index('const '+name+'=')+len('const '+name+'=')
    pos+=HTML[pos:].index('[[' if name=='FULL_MONTHLY' else '{')
    return json.JSONDecoder().raw_decode(HTML[pos:])[0]

def test_period_677_inclusive():
    assert len(MONTHLY)==677
    assert list(MONTHLY)[0]=='2026-11' and list(MONTHLY)[-1]=='2083-03'
    assert len(INCOME)==677 and list(INCOME)==list(MONTHLY)

def test_retirement_324_and_90_age():
    assert META['inputs']=={'endAge':90,'retireAge':63,'livingAt2026':2700000,'mortgageInclusive':True}
    assert len(RETIRE)==324 and list(RETIRE)[0]=='2056-04' and list(RETIRE)[-1]=='2083-03'

def test_A_case_includes_mortgage_once_and_health_separate():
    living,pension,health,withdraw,close=RETIRE['2056-04']
    assert living==5663432 and pension==0 and health==381496
    assert abs(withdraw-(living+health-pension))<=1
    assert living-1675319==3988113
    # The new mortgage expires 2076-10, so the following month must not pay it.
    assert RETIRE['2076-11'][0]<RETIRE['2076-10'][0]

def test_retire_ledger_end_and_annuity_close():
    assert RETIRE['2083-03'][-1]==META['balanceEnd']
    assert RETIRE['2083-03'][-1]>0
    assert META['balanceEnd']==80984826
    assert len(ANNUAL)==58 and ANNUAL[-1][0]==2083

def test_inflow_decomposition_and_child_support_cut():
    assert INCOME['2028-03']==[4027837,0,405000,0]
    assert INCOME['2028-04']==[4027837,0,105000,0]
    assert sum(INCOME['2028-03'])-sum(INCOME['2028-04'])==300000
    assert INCOME['2028-03'][0]==INCOME['2028-04'][0]

def test_income_decomposition_reconciles_677_months():
    assert all(abs(sum(INCOME[m])-MONTHLY[m][0]-MONTHLY[m][1])<=2 for m in MONTHLY)

def test_no_spouse_health_insurance_double_count():
    # Third row of MONTHLY is total mandatory spend; actual spouse 20%-net is already on inflow side.
    assert INCOME['2033-01'][1]==1200000
    assert MONTHLY['2033-01'][2] <= MONTHLY['2033-02'][2]+20000

def test_677_month_payload_matches_authoritative_sheet():
    inline=js_json('FULL_MONTHLY')
    assert len(inline)==677
    assert {m:r for m,r in inline}==MONTHLY
    assert js_json('INCOME_COMPONENTS_V52')==INCOME
    assert js_json('RETIRE_SNAPSHOT')==RETIRE

def test_all_months_present_in_mortgage_calendar():
    m=js_json('MORTGAGE_SHEET_605')
    assert list(m)==list(MONTHLY)
    assert m['2046-10']==0 and m['2046-11']==1675319
    assert m['2076-10']==1675319 and m['2076-11']==0 and m['2083-03']==0

def test_fv_is_conditional_and_not_marked_guaranteed():
    assert 'plan_contributions_not_guaranteed' in HTML
    assert '실적' in HTML and '계획' in HTML

def test_income_component_ui_in_summary_and_expanded_year():
    assert 'function v52IncomeHtml' in HTML
    assert '${v52IncomeHtml(dt,m)}' in HTML
    assert 'function flowYearMonths' in HTML
    assert '${esc(v52IncomeInline(date,m))}' in HTML
    assert '양육지원금 (추정)' in HTML

def test_audit_js_accepts_all_677_months():
    p=ROOT/'docs/js/source_audit_v512k.js'
    assert "END='2083-03'" in p.read_text()
    assert 'retireMonths===324' in p.read_text()
    assert 'annual.length!==58' in p.read_text()
    result=subprocess.run(['node','--check',str(ROOT/'_inline_main.js')],capture_output=True,text=True) if (ROOT/'_inline_main.js').exists() else None
    assert result is None or result.returncode==0,result.stderr if result else ''

def test_old_end_date_not_on_summary():
    assert '2026.11~2077.03' not in HTML
    assert '2077.04 예상 사망시점' not in HTML
    assert '250만 원' not in HTML

def test_summary_insurance_and_pension_after_2077():
    assert RETIRE['2078-05'][2]>0
    assert RETIRE['2083-03'][2]>0
    assert RETIRE['2083-03'][1]>0

def test_independent_annuity_pv_reconciles_new_need():
    monthly_effective=1.04**(1/12)-1
    total=sum((row[0]+row[2]-row[1])/(1+monthly_effective)**i for i,row in enumerate(RETIRE.values()))
    assert abs(total-META['needAtRetirement'])<100


def test_independent_month_start_withdrawal_reconciles_end():
    r=1.04**(1/12)-1
    wealth=float(META['preparedAtRetirement'])
    for living,pension,health,draw,recorded in RETIRE.values():
        wealth=max(0,wealth-min(draw,wealth))*(1+r)+max(0,pension-living-health)
        assert abs(wealth-recorded)<25  # independent, rounded export ledger
    assert abs(wealth-META['balanceEnd'])<25


def test_source_audit_module_reports_ready_677():
    script=r'''
const audit=require('./docs/js/source_audit_v512k.js');
const d=require('./docs/data/v52_authoritative_677.json');
const fs=require('fs');
const h=fs.readFileSync('./docs/index.html','utf8');
const mark='const MORTGAGE_SHEET_605=';
const pos=h.indexOf(mark)+mark.length;
const mort=JSON.parse(h.slice(pos,h.indexOf(';',pos)));
const retire=Object.fromEntries(Object.entries(d.retirement).map(([m,v])=>[m,{living:v[0],pension:v[1],insurance:v[2],withdraw:v[3],balance:v[4]}]));
const result=audit.audit(d.monthly,retire,d.annual,mort);
if(!result.ready)throw new Error(JSON.stringify(result));
if(result.retirementMonths!==324||result.months!==677)throw new Error('Unexpected duration');
'''
    run=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
