"""Deterministic checks for V2.1 off-route / possible NIS classifications."""
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import app


class OffRouteTests(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.index = {
            "trips": {"trip14": {"shape_id": "route14shape", "route_id": "r14"},
                      "trip50": {"shape_id": "route50shape", "route_id": "r50"}},
            "routes": {"r14": {"short": "14"}, "r50": {"short": "50"}},
            "shapes": {
                "route14shape": [[48.450, -123.500], [48.450, -123.495], [48.450, -123.490]],
                "route50shape": [[48.470, -123.500], [48.470, -123.495], [48.470, -123.490]],
            },
            "updated_at": self.now,
            "stops": {}, "trip_stops": {}, "service_days": {}, "exceptions": {}, "blocks": {},
        }
        self.v = {"id": "bus1", "trip_id": "trip14", "route_id": "r14", "lat": 48.450,
                  "lon": -123.495, "timestamp": self.now, "timestamp_source": "vehicle"}

    def test_nearest_segment_not_just_nearest_vertex(self):
        d = app.route_distance_m(48.450, -123.497, self.index['shapes']['route14shape'])
        self.assertLess(d, 1)
        self.assertEqual(app.route_proximity(self.index, self.v, self.now)['state'], 'near')

    def test_outside_600m_and_two_distinct_observations(self):
        away = {**self.v, "lat": 48.461}
        first = app.update_proximity_observations(self.index, [away], {}, self.now)
        self.assertEqual(first['bus1']['state'], 'far')
        self.assertGreater(first['bus1']['distance_m'], 600)
        repeat = app.update_proximity_observations(self.index, [away], first, self.now)
        self.assertEqual(repeat['bus1']['state'], 'far')
        new = {**away, "timestamp": self.now+10}
        confirmed = app.update_proximity_observations(self.index, [new], repeat, self.now+10)
        self.assertEqual(confirmed['bus1']['state'], 'possible_nis')
        self.assertEqual(confirmed['bus1']['observations'], 2)
        returning = app.update_proximity_observations(self.index, [self.v], confirmed, self.now+15)
        self.assertEqual(returning['bus1']['state'], 'near')

    def test_feed_header_timestamps_are_not_new_gps_fixes(self):
        away = {**self.v, "lat":48.461, "timestamp_source": "feed"}
        once = app.update_proximity_observations(self.index, [away], {}, self.now)
        refreshed_header = {**away, "timestamp":self.now+15}
        twice = app.update_proximity_observations(self.index, [refreshed_header], once, self.now+15)
        self.assertEqual(twice['bus1']['state'], 'far')
        moving = {**refreshed_header, "lon":-123.494, "timestamp":self.now+20}
        third = app.update_proximity_observations(self.index, [moving], twice, self.now+20)
        self.assertEqual(third['bus1']['state'], 'possible_nis')

    def test_route_variants_avoid_false_nis(self):
        self.index['shapes']['variant14'] = [[48.461,-123.500],[48.461,-123.495],[48.461,-123.490]]
        self.index['route_shapes'] = app.build_route_shapes(self.index['trips'], self.index['shapes'])
        self.index['route_shapes']['r14'].append('variant14')
        off_trip_but_on_route_variant = {**self.v, 'lat':48.461}
        checked = app.route_proximity(self.index, off_trip_but_on_route_variant, self.now)
        self.assertEqual(checked['state'], 'near')
        self.assertIn('another published shape', checked['basis'])

    def test_no_false_nis_for_unmatchable_trips_and_stale_positions(self):
        for changed in ({"trip_id":None}, {"trip_id":"bogus"}, {"route_id":"r50"},
                        {"timestamp":self.now-1000}):
            with self.subTest(changed=changed):
                v = {**self.v, "lat":48.461, **changed}
                self.assertEqual(app.route_proximity(self.index, v, self.now)['state'], 'unknown')

    def test_switching_trips_resets_confirmation(self):
        away = {**self.v, "lat":48.461}
        prior = app.update_proximity_observations(self.index, [away], {}, self.now)
        changed = {**away, "trip_id":"trip50", "route_id":"r50", "timestamp":self.now+15}
        after = app.update_proximity_observations(self.index, [changed], prior, self.now+15)
        self.assertEqual(after['bus1']['state'], 'far')
        self.assertEqual(after['bus1']['observations'], 1)

    def test_stale_warning_expires_without_new_feed_revision(self):
        with TemporaryDirectory() as temp, patch.object(app,'INDEX_PATH',Path(temp)/'none.gz'):
            tracker = app.Tracker()
            tracker.update_index(self.index, persist=False)
            tracker.vehicles = [{**self.v, 'lat':48.461}]
            first = tracker.snapshot()
            self.assertEqual(first['vehicles'][0]['route_proximity']['state'], 'far')
            with patch.object(app.time, 'time', return_value=self.now + 400):
                refreshed = tracker.snapshot(first['revision'])
                self.assertFalse(refreshed.get('unchanged', False))
                self.assertEqual(refreshed['vehicles'][0]['route_proximity']['state'], 'unknown')

    def test_tracker_keeps_reported_route_and_status_is_separate(self):
        with TemporaryDirectory() as temp, patch.object(app,'INDEX_PATH',Path(temp)/'none.gz'):
            tracker = app.Tracker()
            tracker.update_index(self.index, persist=False)
            tracker.vehicles = [{**self.v, 'lat':48.461}]
            result = tracker.snapshot()
            v = result['vehicles'][0]
            self.assertEqual(v['route'], '14')
            self.assertEqual(v['route_proximity']['state'], 'far')
            self.assertGreater(v['route_proximity']['distance_m'], 600)


if __name__ == '__main__': unittest.main()
