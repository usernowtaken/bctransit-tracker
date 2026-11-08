"""Offline regression tests for SQLite persistence and GPS-recording bounds."""
import tempfile
from pathlib import Path
import time
import unittest

from gps_history import GPSHistory


class GPSHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'radar.sqlite3'
        self.store = GPSHistory(self.path)
        self.now = int(time.time())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def vehicle(self, ident, ts, lat=48.5, lon=-123.4, trip='trip1'):
        return {'id': ident, 'timestamp': ts, 'lat': lat, 'lon': lon,
                'trip_id': trip, 'route_id': 'a', 'label': '3131351248'}

    def test_deduplicates_same_timestamp(self):
        v = self.vehicle('v1', self.now)
        self.assertEqual(self.store.append('victoria', [v], now=self.now), 1)
        self.assertEqual(self.store.append('victoria', [v], now=self.now), 0)
        result = self.store.get('victoria', 'v1', 30, now=self.now)
        self.assertEqual(result['count'], 1)

    def test_isolates_systems_and_vehicle_ids(self):
        v = self.vehicle('v1', self.now)
        self.store.append('victoria', [v], now=self.now)
        self.store.append('kelowna', [v], now=self.now)
        self.store.append('victoria', [self.vehicle('v2', self.now)], now=self.now)
        self.assertEqual(self.store.get('victoria', 'v1', now=self.now)['count'], 1)
        self.assertEqual(self.store.get('kelowna', 'v1', now=self.now)['count'], 1)
        self.assertEqual(self.store.get('victoria', 'v2', now=self.now)['count'], 1)
        self.assertEqual(self.store.get('chilliwack', 'v1', now=self.now)['count'], 0)

    def test_no_stale_or_future_gps(self):
        batch=[self.vehicle('v', self.now-900), self.vehicle('old', self.now-301),
               self.vehicle('future', self.now+150), self.vehicle('good',self.now-50)]
        self.assertEqual(self.store.append('victoria', batch, now=self.now),1)
        self.assertEqual(self.store.get('victoria','good',now=self.now)['count'],1)

    def test_bounded_retention(self):
        # Insert a historical observation in the past, then simulate later time.
        self.store.append('victoria',[self.vehicle('v',self.now-200)],now=self.now)
        self.store.append('victoria',[self.vehicle('v',self.now-180)],now=self.now)
        self.assertEqual(self.store.get('victoria','v',30,now=self.now)['count'],2)
        # Periodic cleanup removes positions older than 24h.
        self.store.append('victoria',[],now=self.now+86401)
        self.assertEqual(self.store.get('victoria','v',60,now=self.now+86401)['count'],0)
        with self.store.lock:
            self.assertEqual(self.store.db.execute('SELECT count(*) FROM fixes').fetchone()[0],0)

    def test_persists_restart(self):
        self.store.append('victoria',[self.vehicle('v',self.now)],now=self.now)
        self.store.close()
        self.store=GPSHistory(self.path)
        self.assertEqual(self.store.get('victoria','v',30,now=self.now)['count'],1)

    def test_route_metadata_from_index(self):
        index={'routes':{'a':{'short':'95'}},'trips':{'trip1':{'route_id':'a'}}}
        self.store.append('victoria',[self.vehicle('v',self.now)],index,now=self.now)
        self.assertEqual(self.store.get('victoria','v',30,now=self.now)['points'][0][-1],'95')

    def test_invalid_arguments(self):
        for sys,vehicle,mins in (('fake','v',30),('victoria','',30),('victoria','v',1000)):
            with self.assertRaises(ValueError):self.store.get(sys,vehicle,mins,now=self.now)

    def test_ignores_nonfinite_and_invalid(self):
        self.assertEqual(self.store.append('victoria',[
            self.vehicle('v1', self.now,float('nan')),
            self.vehicle('v2', self.now,91),
            self.vehicle('', self.now),
            self.vehicle('v3', self.now),
        ],now=self.now),1)

    def test_window_boundaries_and_order(self):
        self.store.append('victoria',[self.vehicle('v',self.now-901),
            self.vehicle('v',self.now-900),self.vehicle('v',self.now-120),
            self.vehicle('v',self.now-15)],now=self.now)
        self.assertEqual([r[0] for r in self.store.get('victoria','v',15,now=self.now)['points']],
                         [self.now-120,self.now-15])
        self.assertEqual([r[0] for r in self.store.get('victoria','v',30,now=self.now)['points']],
                         [self.now-120,self.now-15])
