"""V59 net new savings visualization: no changes to existing target engine."""
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'docs/index.html').read_text('utf-8')

def test_view_uses_net_target_not_total():
    assert './js/v59_net_goal_progress.js' in HTML
    section = HTML.split('function v59GoalDestination(date,sim,g){', 1)[1].split('\nfunction v58BeforeLastActual(', 1)[0]
    assert 'IFPK_V59_NET_GOAL.calculate(g,date,v57Progress.history)' in section
    assert 'COMPACT(p.netTarget)' in section
    assert '순필요저축 목표액' in section
    assert 'g.total' not in section
    assert 'p.newAtGoal' in section

def test_accounting_and_contribution_only_progress():
    run = subprocess.run(['node', str(ROOT / 'tests/run_v59_net_progress_tests.js')],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert run.returncode == 0, run.stdout + '\n' + run.stderr
