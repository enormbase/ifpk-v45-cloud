"""Regression tests: the customer consumption budget and V55 savings use one monthly basis."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf8')

class ConsumptionBridgeTests(unittest.TestCase):
    def test_customer_budget_events_flow_to_v55_single_simulation(self):
        self.assertIn('function v55ConsumptionDeltas()', HTML)
        self.assertIn('const d=monthSpendChange(date);', HTML)
        self.assertIn('consumptionDeltas:v55ConsumptionDeltas()', HTML)
        self.assertIn('cashOverrides:v55CashOverrides()', HTML)
        self.assertIn('if(old&&Number(old.expense)===3300000)', HTML)
        self.assertIn('고객이 변경한 일반소비 계획 반영:', HTML)

    def test_11_12_month_plan_and_actual_roll_forward(self):
        out=subprocess.run(['node','tests/run_v61_consumption_rollover_tests.js'],cwd=ROOT,
                           capture_output=True,text=True,timeout=25,check=True)
        self.assertIn('V61 PASS:',out.stdout)

if __name__=='__main__':unittest.main()
