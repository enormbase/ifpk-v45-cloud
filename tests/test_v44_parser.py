import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collector"))

from ifpk_collector import (contiguous_values, db_connect, get_estimates, parse_ecos,
                             parse_kosis, status_json, store_observations)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = db_connect(Path(self.tmp.name) / 'test.sqlite3')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    @staticmethod
    def kosis_row(month, value, city='T10'):
        return {'ORG_ID': '101', 'TBL_ID': 'DT_1J22003', 'C1': city,
                'ITM_ID': 'T', 'PRD_SE': 'M', 'PRD_DE': month, 'DT': str(value),
                'UNIT_NM': '2020=100', 'LST_CHN_DE': '2026-11-03'}

    def test_kosis_schema_prevents_wrong_city(self):
        self.assertEqual(parse_kosis([self.kosis_row('202610', '120.73')])[0]['value'], 120.73)
        with self.assertRaises(ValueError):
            parse_kosis([self.kosis_row('202610', '121.00', city='T16')])

    def test_kosis_rejects_bad_year_base(self):
        wrong = self.kosis_row('202610', '120')
        wrong['UNIT_NM'] = '2025=100'
        with self.assertRaises(ValueError):
            parse_kosis([wrong])

    def test_saved_rows_idempotent_and_revision_tracked(self):
        r = parse_kosis([self.kosis_row('202610', '120.73')])
        self.assertEqual(store_observations(self.db, r), (1, 0))
        self.assertEqual(store_observations(self.db, r), (0, 0))
        r2 = parse_kosis([self.kosis_row('202610', '120.90')])
        self.assertEqual(store_observations(self.db, r2), (0, 1))
        self.assertEqual(self.db.execute('select count(*) from revisions').fetchone()[0], 1)
        self.assertEqual(status_json(self.db)['counts'][0]['lastMonth'], '2026-10')

    def test_atomic_rejects_non_numeric(self):
        good = parse_kosis([self.kosis_row('202609', 120)])
        good.append(dict(good[0], date='2026-10', value='abc'))
        with self.assertRaises(ValueError):
            store_observations(self.db, good)
        self.assertEqual(self.db.execute('select count(*) from observations').fetchone()[0], 0)

    def test_ecos_item_mixing_blocked(self):
        series = {'id': 'CPI_CAR', 'stat_code': '901Y009', 'item_filters': {'ITEM_CODE1': '777'}}
        original = {'STAT_CODE': '901Y009', 'CYCLE': 'M', 'TIME': '202610', 'ITEM_CODE1': '777', 'DATA_VALUE': '116.2'}
        self.assertEqual(parse_ecos({'StatisticSearch': {'row': [original]}}, series)[0]['value'], 116.2)
        with self.assertRaises(ValueError):
            parse_ecos({'StatisticSearch': {'row': [dict(original, ITEM_CODE1='888')]}}, series)

    def test_rolling_gap_does_not_publish_avg(self):
        self.assertIsNone(contiguous_values([{'date': '2026-01','value': 1},
                                              {'date': '2026-03','value': 2},
                                              {'date': '2026-04','value': 3}], 3))
        self.assertEqual(contiguous_values([{'date': '2026-01','value': 1},
                                             {'date': '2026-02','value': 2},
                                             {'date': '2026-03','value': 3}], 3), [1,2,3])

    def test_official_series_estimate(self):
        rows = [dict(id='CPI_CAR', date=f'2026-{m:02d}', value=100+m,unit='지수',
                     provider='ECOS',source_code='901Y009/example',source_updated='') for m in (1,2,3)]
        store_observations(self.db, rows)
        ma = next(x for x in get_estimates(self.db) if x['id'] == 'CPI_CAR')
        self.assertEqual(ma['value'],102)


if __name__ == '__main__':
    unittest.main()
