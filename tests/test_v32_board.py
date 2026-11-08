"""V3.2 on-demand board: schedules remain distinct from fresh predictions."""
import unittest
from datetime import datetime, timedelta
from app import Tracker, TIMEZONE, OFF_ROUTE_THRESHOLD_M, route_proximity

class NearbyBoardTests(unittest.TestCase):
    def setUp(self):
        self.t = Tracker('victoria')
        self.when = datetime(2026, 11, 8, 10, 2, tzinfo=TIMEZONE)
        self.now = int(self.when.timestamp())
        today = self.when.strftime('%Y%m%d')
        self.t.update_index({
            'routes':{'r14':{'short':'14','long':'UVic'}},
            'trips':{
                't1':{'route_id':'r14','service_id':'ALL','headsign':'Downtown','shape_id':'sh'},
                't2':{'route_id':'r14','service_id':'ALL','headsign':'UVic','shape_id':'sh'}},
            'stops':{'s1':['Exchange',48.45,-123.49], 's2':['University',48.46,-123.48]},
            'trip_stops':{'t1':[[1,'s1',10*3600+10*60,10*3600+10*60]],
                          't2':[[1,'s1',10*3600+20*60,10*3600+20*60]]},
            'service_days':{'ALL':{'start':'20260101','end':'20270101','weekdays':[True]*7}},
            'exceptions':{},'shapes':{'sh':[[48.45,-123.49],[48.45,-123.48]]}
        },persist=False)

    def test_schedule_only_is_explicit(self):
        board=self.t.nearby_departures(['s1'],self.now)
        self.assertFalse(board['realtime_fresh'])
        arr=board['stops'][0]['arrivals']
        self.assertEqual([r['source'] for r in arr],['scheduled','scheduled'])
        self.assertEqual([r['route'] for r in arr],['14','14'])
        self.assertLess(arr[0]['arrival_at'],arr[1]['arrival_at'])

    def test_realtime_prediction_overrides_matching_schedule(self):
        self.t.trip_feed_timestamp=self.now
        self.t.trip_feed_fetched_at=self.now
        self.t.trip_updates={'t1':{'timestamp':self.now,'start_date':self.when.strftime('%Y%m%d'),
            'stops':[{'sequence':1,'id':'s1','predicted_at':self.now+5*60}]}}
        board=self.t.nearby_departures(['s1'],self.now)
        self.assertTrue(board['realtime_fresh'])
        arr=board['stops'][0]['arrivals']
        self.assertEqual(len(arr),2)
        self.assertEqual(arr[0]['source'],'live')
        self.assertEqual(arr[0]['arrival_at'],self.now+5*60)
        self.assertEqual(arr[0]['scheduled_at'],int(self.when.replace(hour=10,minute=10).timestamp()))
        self.assertEqual(arr[1]['source'],'scheduled')

    def test_expired_predictions_never_pass_as_live(self):
        self.t.trip_feed_timestamp=self.now-400
        self.t.trip_updates={'t1':{'timestamp':self.now-400,'start_date':self.when.strftime('%Y%m%d'),
            'stops':[{'sequence':1,'id':'s1','predicted_at':self.now+300}]}}
        board=self.t.nearby_departures(['s1'],self.now)
        self.assertFalse(board['realtime_fresh'])
        self.assertTrue(all(r['source']=='scheduled' for r in board['stops'][0]['arrivals']))

    def test_no_unpublished_scheduled_time(self):
        self.assertEqual(self.t.nearby_departures(['s2'],self.now)['stops'][0]['arrivals'],[])
        self.assertEqual(self.t.nearby_departures(['unknown'],self.now)['stops'][0]['status'],'unknown_stop')

    def test_100m_off_route_not_claimed_as_confirmed_nis(self):
        self.assertEqual(OFF_ROUTE_THRESHOLD_M,100)
        trip={'trip_id':'t1','route_id':'r14','timestamp':self.now,
              'lat':48.4515,'lon':-123.485}
        result=route_proximity(self.t.index,trip,self.now)
        self.assertEqual(result['state'],'far')
        self.assertEqual(result['threshold_m'],100)

if __name__=='__main__':unittest.main()
