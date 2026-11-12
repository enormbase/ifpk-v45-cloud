from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class V55Test(unittest.TestCase):
    def test_v55_pure_engine(self):
        r=subprocess.run(['node',str(ROOT/'tests'/'run_v55_tests.js')],cwd=ROOT,text=True,capture_output=True,timeout=30)
        self.assertEqual(r.returncode,0,msg=r.stdout+'\n'+r.stderr)
        self.assertIn('V55 PASS',r.stdout)

    def test_html_links_runtime(self):
        s=(ROOT/'docs'/'index.html').read_text('utf-8')
        self.assertIn('IFPK V58',s)
        self.assertIn('대시보드 V58</title>',s)
        self.assertIn('v55_savings_engine.js',s)
        self.assertIn('v55_savings_ui.js',s)
        self.assertIn('v55_monthly_savings_snapshot.js',s)
