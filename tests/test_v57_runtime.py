"""CI-visible smoke tests for V57 pure rollover engine and deployable HTML."""
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

class V57RuntimeTest(unittest.TestCase):
    def test_node_rollover(self):
        r=subprocess.run(['node',str(ROOT/'tests'/'run_v57_tests.js')],cwd=ROOT,capture_output=True,text=True,timeout=35)
        self.assertEqual(r.returncode,0,msg=r.stdout+'\n'+r.stderr)
        self.assertIn('V57 PASS',r.stdout)

    def test_new_ux_present(self):
        s=(ROOT/'docs'/'index.html').read_text(encoding='utf8')
        self.assertIn('금은동 재무설계 플랫폼</div>',s)
        self.assertIn('data-v57-check',s)
        self.assertIn('IFPK_V57.closeMonth(',s)
        self.assertIn('${v57Roadmap()}',s)
        self.assertIn('data-v57-reopen',s)
