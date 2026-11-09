"""V51.1c compatibility: old staged model survives only as comparison anchor."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=ROOT/'docs'/'index.html'

def test_legacy_is_retained_only_as_snapshot_anchor():
    script=r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const raw=fs.readFileSync(process.argv[1],'utf8');
const code=raw.slice(raw.indexOf('const SPENDING=['),raw.indexOf('let cashDeltaCache=null'));
const sandbox={persistent:{initialSpending:null,consumptionEvents:[]},console,assert};
vm.runInNewContext(code+`
 assert.equal(legacySheetGeneralBudget('2027-01'),2200000);
 assert.equal(legacySheetGeneralBudget('2030-01'),2300000);
 assert.equal(sheetGeneralBudget('2026-11'),2400000);
 assert.equal(monthSpendChange('2026-11',[]),0);
 assert.ok(sheetGeneralBudget('2027-01')>2400000);
 assert.ok(monthSpendChange('2027-01',[])>200000);
 console.log('compatibility baseline ok');`,sandbox);
'''
    result=subprocess.run(['node','-e',script,str(HTML)],text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert 'compatibility baseline ok' in result.stdout
