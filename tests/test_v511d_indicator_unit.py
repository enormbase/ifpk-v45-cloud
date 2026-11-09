"""V51.1d: headline number and index basis must not share oversized type."""
from pathlib import Path
import subprocess

HTML=Path(__file__).resolve().parents[1]/'docs'/'index.html'

def test_large_observation_shows_number_only_and_basis_below():
    html=HTML.read_text('utf-8')
    assert 'v501HeadlineUnit(spec,last)' in html
    assert 'V51.1d 지표값·기준연도 표기 수정' in html
    assert '<span class="v501-observation">${esc(v501Fmt(last.value))}</span>' in html
    assert '<span class="v501-headline-unit">${esc(v501HeadlineUnit(spec,last))}</span>' in html
    assert '기준: ${esc(v501IndexBasis(spec,last))}' in html
    assert "v501Fmt(last.value)+' '+(last.unit||spec.unit)" not in html

def test_index_unit_classifier_using_actual_page_javascript():
    script="""
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const a=html.indexOf('function v501HeadlineUnit(spec,last)');
const b=html.indexOf('function v501Data(spec)',a);
assert.ok(a>0&&b>a);
const js=html.slice(a,b);
const values=vm.runInNewContext(js+`[
 v501HeadlineUnit({unit:'지수'},{unit:'2020=100'}),
 v501HeadlineUnit({unit:'지수'},{unit:'2026-06=100'}),
 v501HeadlineUnit({unit:'지수'},{unit:'지수'}),
 v501HeadlineUnit({unit:'%'},{unit:'%'}),
 v501HeadlineUnit({unit:'%'}),
]`);
assert.deepEqual(Array.from(values),['','','','%','%']);
"""
    r=subprocess.run(['node','-e',script,str(HTML)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
