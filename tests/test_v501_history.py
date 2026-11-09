import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
import cloud_runner as cr

class V501HistoryTest(unittest.TestCase):
    def test_revision_public_export_and_metadata(self):
        rows=[{'indicator_id':'CPI_GENERAL','month':'2026-10','previous_value':120.73,'new_value':120.83,
                'detected_at':'2026-11-09T13:00:00+00:00','source_updated':'2026-11-09'}]
        records=[{'id':'CPI_GENERAL','date':'2026-10','value':120.83,'provider':'KOSIS',
                  'unit':'지수','sourceCode':'cpi','sourceUpdated':'2026-11-09','retrievedAt':'2026-11-09T13:00:00+00:00'}]
        p,s=cr.prepare_snapshots(records,[],live=True,revisions=rows)
        self.assertTrue(p['revisionHistoryAvailable'])
        self.assertEqual(p['revisions'][0]['previousValue'],120.73)
        self.assertEqual(p['revisions'][0]['newValue'],120.83)
        self.assertEqual(s['revisionCount'],1)
        self.assertNotIn('SUPABASE_SECRET_KEY',json.dumps(p))
    def test_no_revision_export_is_unknown_not_empty(self):
        p,s=cr.prepare_snapshots([],[],live=False)
        self.assertFalse(p['revisionHistoryAvailable'])
        self.assertEqual(p['revisions'],[])
    def test_reject_nan_revisions(self):
        with self.assertRaises(ValueError):
            cr.normalize_public_revisions([{'indicator_id':'CPI_GENERAL','month':'2026-10',
                'previous_value':float('nan'),'new_value':120.7,'detected_at':'today'}])
    def test_ignore_unrecognized_indicator(self):
        x=cr.normalize_public_revisions([{'indicator_id':'NON_PUBLIC','month':'2026-10',
          'previous_value':1,'new_value':2,'detected_at':'today'}])
        self.assertEqual(x,[])
if __name__=='__main__':unittest.main()
