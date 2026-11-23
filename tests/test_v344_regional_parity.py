"""V3.4.4 offline tests: Chilliwack operator scoping and regional parity."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import time
import unittest

import app
from fleet_identity import identify_feed_vehicle, identify_vehicle
from gps_history import GPSHistory


def index_for(now):
    return {
      'routes':{
        'cw51':{'short':'51','long':'Vedder'},
        'fvx66':{'short':'66','long':'Fraser Valley Express'},
        'ab1':{'short':'1','long':'Highstreet'},
      },
      'trips':{
        'cw-a':{'route_id':'cw51','service_id':'daily','headsign':'Downtown', 'block_id':'x', 'first':10*3600,'last':11*3600,'shape_id':'cws'},
        'cw-b':{'route_id':'fvx66','service_id':'daily','headsign':'Abbotsford', 'block_id':'x', 'first':12*3600,'last':13*3600,'shape_id':'fvxs'},
        'ab-a':{'route_id':'ab1','service_id':'daily','headsign':'Sevenoaks', 'block_id':'x', 'first':11*3600+60,'last':11*3600+55*60,'shape_id':'abs'},
      },
      'stops':{
        'common':['Shared interchange',49.158,-121.95],
        'cw':['Chilliwack local',49.17,-121.94],
        'ab':['Abbotsford local',49.15,-121.9],
      },
      'trip_stops':{
        'cw-a':[[1,'common',10*3600+10*60,10*3600+10*60],[2,'cw',10*3600+20*60,10*3600+20*60]],
        'cw-b':[[1,'common',12*3600+10*60,12*3600+10*60]],
        'ab-a':[[1,'common',11*3600+10*60,11*3600+10*60],[2,'ab',11*3600+30*60,11*3600+30*60]],
      },
      'service_days':{'daily':{'start':'20260101','end':'20281231','weekdays':[True]*7}},
      'exceptions':{},
      'shapes':{'cws':[[49.15,-121.96],[49.16,-121.95]],'fvxs':[[49.15,-121.95],[49.06,-122.3]],'abs':[[49.15,-121.9],[49.16,-121.91]]},
      'blocks':{'x':['cw-a','ab-a','cw-b']},
      'updated_at':now,
    }


class RegionalParity(unittest.TestCase):
    def test_operator_13_scoping_route_trip_and_stop(self):
        idx=index_for(int(time.time()))
        self.assertTrue(app.route_in_view('chilliwack',idx['routes']['cw51']))
        self.assertFalse(app.route_in_view('chilliwack',idx['routes']['ab1']))
        self.assertTrue(app.trip_in_view('chilliwack',idx,'cw-b'))
        self.assertFalse(app.trip_in_view('chilliwack',idx,'ab-a'))
        self.assertEqual(app.region_stop_ids('chilliwack',idx),{'common','cw'})
        self.assertIsNone(app.region_stop_ids('kelowna',idx))
        self.assertFalse(app.vehicle_in_view('chilliwack',idx,{'route_id':'ab1','lat':49.15,'lon':-121.95}))
        self.assertTrue(app.vehicle_in_view('chilliwack',idx,{'route_id':'fvx66','lat':49.05,'lon':-122.3}))
        self.assertTrue(app.vehicle_in_view('chilliwack',idx,{'route_id':None,'lat':49.16,'lon':-121.95}))
        self.assertFalse(app.vehicle_in_view('chilliwack',idx,{'route_id':None,'lat':49.05,'lon':-122.3}))
        self.assertTrue(app.vehicle_in_view('kelowna',idx,{'route_id':'ab1'}))

    def test_alerts_only_show_relevant_region(self):
        idx=index_for(int(time.time()))
        entries=[
          {'id':'c','selectors':[{'route_id':'cw51'}]},
          {'id':'f','selectors':[{'trip_id':'cw-b'}]},
          {'id':'s','selectors':[{'stop_id':'cw'}]},
          {'id':'a','selectors':[{'route_id':'ab1'}]},
          {'id':'aa','selectors':[{'stop_id':'ab'}]},
          {'id':'all','selectors':[]},
          {'id':'agency','selectors':[{'agency_id':'13'}]},
          {'id':'contradiction','selectors':[{'route_id':'cw51','stop_id':'ab'}]},
        ]
        self.assertEqual([a['id'] for a in app.region_alerts('chilliwack',entries,idx)],['c','f','s'])
        self.assertEqual(app.region_alerts('kelowna',entries,idx),entries)

    def test_chilliwack_departures_and_stops_exclude_abbotsford(self):
        now_time=datetime(2026,11,22,10,2,tzinfo=app.TIMEZONE)
        now=int(now_time.timestamp())
        with TemporaryDirectory() as tmp,patch.object(app,'CACHE_DIR',Path(tmp)):
            t=app.Tracker('chilliwack')
            t.update_index(index_for(now),persist=False)
            public=t.all_stops()
            self.assertEqual({row[0] for row in public['stops']},{'common','cw'})
            self.assertTrue(public['ready'])
            t.trip_feed_timestamp=now
            t.trip_feed_fetched_at=now
            t.trip_updates={
              'cw-a':{'timestamp':now,'start_date':'20261122','stops':[{'sequence':1,'id':'common','predicted_at':now+300}]},
              'ab-a':{'timestamp':now,'start_date':'20261122','stops':[{'sequence':1,'id':'common','predicted_at':now+350}]},
            }
            board=t.nearby_departures(['common','ab'],now)
            self.assertEqual(board['stops'][1]['status'],'unknown_stop')
            self.assertTrue(all(a['route'] in ('51','66') for a in board['stops'][0]['arrivals']))
            self.assertTrue(any(a['source']=='live' for a in board['stops'][0]['arrivals']))
            self.assertIsNone(t.route_detail('ab-a'))
            self.assertEqual(t.route_detail('cw-a')['route'],'51')
            arrival=t.stop_arrivals('ab')
            self.assertEqual(arrival['status'],'unknown_stop')

    def test_next_route_skip_foreign_and_same_route(self):
        now_dt=datetime(2026,11,22,10,2,tzinfo=app.TIMEZONE)
        idx=index_for(int(now_dt.timestamp()))
        v={'trip_id':'cw-a','timestamp':int(now_dt.timestamp()),'start_date':'20261122'}
        following=app.next_run(idx,v,now_dt,'chilliwack')
        self.assertEqual(following['route'],'66')
        self.assertNotEqual(following['trip_id'],'ab-a')

    def test_regional_fleet_label_and_id_fallback(self):
        self.assertEqual(identify_vehicle('kelowna','6007')['model_key'],'nova3')
        self.assertEqual(identify_feed_vehicle('kelowna','', '6007')['fleet_number'],'6007')
        self.assertIn('descriptor/entity ID',identify_feed_vehicle('kelowna','', '6007')['fleet_basis'])
        self.assertIsNone(identify_feed_vehicle('kelowna','', 'id-prefix-6007')['fleet_number'])
        self.assertEqual(identify_vehicle('chilliwack','9426')['nova_generation'],3)

    def test_fleet_history_for_all_systems_without_cross_data(self):
        now=int(time.time())
        with TemporaryDirectory() as tmp:
            db=GPSHistory(Path(tmp)/'history.sqlite')
            for system,num in [('victoria','9434'),('kelowna','6007'),('chilliwack','9426')]:
                db.append(system,[{'id':'id-'+num,'label':num,'lat':49.13,'lon':-121.90,
                                   'timestamp':now-20,'route_id':'cw51'}],now=now)
                payload=db.last_known(system,fleet=num,now=now)
                self.assertTrue(payload['found'],system)
                self.assertEqual(payload['vehicle']['id'],'id-'+num)
                other='victoria' if system!='victoria' else 'kelowna'
                self.assertFalse(db.last_known(other,fleet=num,now=now)['found'])
            db.close()

    def test_chilliwack_history_excludes_foreign_feed_vehicles(self):
        now=int(time.time())
        idx=index_for(now)
        with TemporaryDirectory() as tmp, patch.object(app,'CACHE_DIR',Path(tmp)):
            db=GPSHistory(Path(tmp)/'history.sqlite')
            tr=app.Tracker('chilliwack',db)
            tr.update_index(idx,persist=False)
            rows=[
              {'id':'local','label':'9426','route_id':'cw51','trip_id':'cw-a','lat':49.159,'lon':-121.95,'timestamp':now},
              {'id':'foreign','label':'9425','route_id':'ab1','trip_id':'ab-a','lat':49.15,'lon':-121.95,'timestamp':now},
            ]
            with patch.object(app,'parse_vehicle_feed',return_value=(rows,now)):
                tr.update_feed(b'fake')
            self.assertEqual({v['id'] for v in tr.snapshot()['vehicles']},{'local'})
            self.assertEqual(db.get('chilliwack','foreign',15,now)['count'],0)
            self.assertEqual(db.get('chilliwack','local',15,now)['count'],1)
            db.close()

if __name__=='__main__': unittest.main()
