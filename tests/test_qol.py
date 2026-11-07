"""V2.5 quality-of-life regression tests (requires normal setup.bat dependencies)."""
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import app


class QOLTests(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.index = {
            'routes': {'r14': {'short': '14'}},
            'trips': {'t14': {'route_id': 'r14', 'shape_id': 'shape14', 'service_id': 'S', 'first': 3600, 'last': 7200}},
            'shapes': {'shape14': [[48.450, -123.500], [48.450, -123.490]]},
            'stops': {'a': ['Stop A', 48.450, -123.500], 'b': ['Stop B', 48.450, -123.490]},
            'trip_stops': {'t14': [[1, 'a', 3600, 3600], [2, 'b', 7200, 7200]]},
            'service_days': {'S': {'start':'20260101', 'end':'20281231','weekdays':[True]*7}},
            'exceptions': {}, 'blocks': {}, 'updated_at': self.now,
        }
        self.index['route_shapes'] = app.build_route_shapes(self.index['trips'], self.index['shapes'])
        self.index['route_short_ids'] = app.build_route_short_ids(self.index['routes'])

    def test_unknown_trip_off_route_fallback_two_observations(self):
        v = {'id':'bus', 'trip_id':None, 'route_id':'r14', 'lat':48.465, 'lon':-123.495,
             'timestamp':self.now, 'timestamp_source':'vehicle'}
        first = app.update_proximity_observations(self.index, [v], {}, self.now)
        self.assertEqual(first['bus']['state'], 'far')
        new = {**v, 'timestamp':self.now+15}
        second = app.update_proximity_observations(self.index, [new], first, self.now+15)
        self.assertEqual(second['bus']['state'], 'possible_nis')
        self.assertGreater(second['bus']['distance_m'], 600)

    def test_arrival_event_absolute_time(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app,'INDEX_PATH',Path(tmp)/'none.gz'):
            tracker = app.Tracker()
            tracker.update_index(self.index, persist=False)
            tracker.trip_feed_fetched_at = self.now
            tracker.trip_updates = {'t14': {'timestamp':self.now, 'start_date':'20261106',
                'stops':[{'sequence':2,'id':'b','predicted_at':self.now+600,'delay_seconds':None}]}}
            result = tracker.arrivals_for_trip('t14')
            self.assertEqual(result['status'], 'live')
            self.assertEqual(result['stops'][0]['predicted_at'], self.now+600)
            tracker.trip_updates['t14']['timestamp'] = self.now-400
            self.assertEqual(tracker.arrivals_for_trip('t14')['status'], 'stale')

    def test_delays_without_absolute_time(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app,'INDEX_PATH',Path(tmp)/'none.gz'):
            tracker=app.Tracker()
            tracker.update_index(self.index,persist=False)
            tracker.trip_feed_fetched_at = self.now
            tracker.trip_updates = {'t14': {'timestamp':self.now, 'start_date':'20261106',
                'stops':[{'sequence':2,'id':'b','predicted_at':None,'delay_seconds':120}]}}
            result = tracker.arrivals_for_trip('t14')
            expected = datetime(2026,11,6,2,2,tzinfo=app.TIMEZONE).timestamp()
            self.assertEqual(result['stops'][0]['predicted_at'], int(expected))

if __name__ == '__main__':
    unittest.main()
