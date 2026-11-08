"""V2.8 opt-in stop catalogue/board tests. Uses current GTFS index; no GPS needed."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import time
import unittest
import app

class NearbyAndStopBoardTests(unittest.TestCase):
    def make_tracker(self):
        tracker=app.Tracker('victoria')
        tracker.index={
            'routes':{'r14':{'short':'14','long':'Victoria'}},
            'stops':{'a':['Langford Exchange',48.45,-123.50], 'b':['UVic',48.47,-123.30],
                     'bad':['Outside Region',60.0,-90.0]},
            'trips':{'t14':{'route_id':'r14','headsign':'UVic','service_id':'weekday'}},
            'trip_stops':{'t14':[[1,'a',3600,3600],[2,'b',4200,4200]]},
            'updated_at':12345,
        }
        return tracker

    def test_catalog_returns_stops_without_gps_parameter(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'CACHE_DIR',Path(temp)):
            tracker=self.make_tracker()
            result=tracker.all_stops()
            self.assertTrue(result['ready'])
            self.assertEqual(result['system'],'victoria')
            self.assertEqual({r[0] for r in result['stops']},{'a','b'})

    def test_only_fresh_predictions_are_shown(self):
        now=int(time.time())
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'CACHE_DIR',Path(temp)):
            tracker=self.make_tracker()
            tracker.trip_feed_timestamp=now
            tracker.trip_feed_fetched_at=now
            tracker.trip_updates={'t14':{'timestamp':now,'start_date':'20261107',
                'stops':[{'sequence':2,'id':'b','predicted_at':now+360,'delay_seconds':None}]}}
            board=tracker.stop_arrivals('b')
            self.assertEqual(board['status'],'live')
            self.assertEqual(board['arrivals'][0]['route'],'14')
            self.assertEqual(board['arrivals'][0]['arrival_at'],now+360)
            self.assertEqual(tracker.stop_arrivals('unknown')['status'],'unknown_stop')
            tracker.trip_feed_timestamp=now-500
            tracker.trip_feed_fetched_at=now-500
            self.assertEqual(tracker.stop_arrivals('b')['status'],'stale')

    def test_no_fabricated_etas(self):
        now=int(time.time())
        with tempfile.TemporaryDirectory() as temp,patch.object(app,'CACHE_DIR',Path(temp)):
            tracker=self.make_tracker()
            tracker.trip_feed_timestamp=now
            tracker.trip_feed_fetched_at=now
            tracker.trip_updates={'t14':{'timestamp':now,'start_date':'20261107',
                'stops':[{'sequence':1,'id':'a','predicted_at':None,'delay_seconds':None}]}}
            board=tracker.stop_arrivals('a')
            self.assertEqual(board['status'],'unavailable')
            self.assertEqual(board['arrivals'],[])

if __name__=='__main__':unittest.main()
