"""Run after setup: python -m unittest discover -s tests -v"""
import io
import time
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import tempfile

from google.transit import gtfs_realtime_pb2
import app


def sample_gtfs(include_block=True):
    files = {
      'routes.txt': 'route_id,route_short_name,route_long_name,route_color\nr95,95,Langford Express,04AC86\nr50,50,Langford/Downtown,0077EE\n',
      'trips.txt': 'route_id,service_id,trip_id,trip_headsign,block_id,shape_id\n' +
         f'r95,WKD,trip_95,Downtown,{"block_123" if include_block else ""},shape_1\n' +
         f'r50,WKD,trip_50,Langford,{"block_123" if include_block else ""},shape_2\n',
      'stops.txt': 'stop_id,stop_name,stop_lat,stop_lon\ns1,Langford Exchange,48.448,-123.496\ns2,Helmcken,48.465,-123.436\ns3,Downtown,48.425,-123.365\n',
      'stop_times.txt': 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n' +
        'trip_95,10:00:00,10:00:00,s1,1\ntrip_95,10:20:00,10:20:00,s2,2\ntrip_95,10:30:00,10:30:00,s3,3\n' +
        'trip_50,10:45:00,10:45:00,s3,1\ntrip_50,11:20:00,11:20:00,s1,2\n',
      'shapes.txt': 'shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n' +
        'shape_1,48.448,-123.496,1\nshape_1,48.465,-123.436,2\nshape_1,48.425,-123.365,3\n'+
        'shape_2,48.425,-123.365,1\nshape_2,48.448,-123.496,2\n',
      'calendar.txt': 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n'+
        'WKD,1,1,1,1,1,1,1,20260101,20280101\n',
      'calendar_dates.txt': 'service_id,date,exception_type\nWKD,20261107,2\n'
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        for name, content in files.items(): archive.writestr(name,content)
    return buffer.getvalue()


class TrackerTests(unittest.TestCase):
    def test_vehicle_feed_positions_and_optional_details(self):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = '2.0'
        feed.header.timestamp = int(time.time())
        entry = feed.entity.add()
        entry.id = 'entity'
        entry.vehicle.vehicle.id = 'BUS-8'
        entry.vehicle.trip.trip_id = 'trip_95'
        entry.vehicle.trip.route_id = 'r95'
        entry.vehicle.trip.start_date = '20261106'
        entry.vehicle.position.latitude = 48.45
        entry.vehicle.position.longitude = -123.49
        entry.vehicle.position.bearing = 85
        entry.vehicle.position.speed = 9.7
        entry.vehicle.current_stop_sequence = 2
        entry.vehicle.timestamp = int(time.time())
        invalid = feed.entity.add()
        invalid.id = 'faraway'
        invalid.vehicle.position.latitude = 20
        invalid.vehicle.position.longitude = 20
        vehicles,stamp = app.parse_vehicle_feed(feed.SerializeToString())
        self.assertEqual(len(vehicles), 1)
        self.assertEqual(vehicles[0]['stop_sequence'], 2)
        self.assertEqual(vehicles[0]['bearing'], 85)
        self.assertEqual(vehicles[0]['id'], 'BUS-8')
        self.assertEqual(stamp, feed.header.timestamp)

    def test_stop_context_and_route_geometry(self):
        index=app.parse_static_gtfs(sample_gtfs())
        self.assertEqual(index['routes']['r95']['color'], '#04AC86')
        self.assertEqual(index['trips']['trip_95']['block_id'],'block_123')
        self.assertEqual(index['shapes']['shape_1'][0], [48.448,-123.496])
        v={'trip_id':'trip_95','stop_sequence':2,'stop_status':2}
        context=app.stop_context(index,v,datetime(2026,11,6,10,20,tzinfo=app.TIMEZONE))
        self.assertEqual(context['previous']['name'], 'Langford Exchange')
        self.assertEqual(context['next']['name'],'Helmcken')
        v['stop_status']=1
        stopped=app.stop_context(index,v,datetime(2026,11,6,10,20,tzinfo=app.TIMEZONE))
        self.assertEqual(stopped['previous']['name'],'Helmcken')
        self.assertEqual(stopped['next']['name'],'Downtown')

    def test_next_route_block_prediction(self):
        index=app.parse_static_gtfs(sample_gtfs())
        now=datetime(2026,11,6,10,19,tzinfo=app.TIMEZONE)
        v={'trip_id':'trip_95','start_date':'20261106','timestamp':int(now.timestamp())}
        result=app.next_run(index,v,now)
        self.assertIsNotNone(result)
        self.assertEqual(result['route'],'50')
        self.assertEqual(result['starts_at'],'10:45')
        self.assertTrue(result['different_route'])
        self.assertIn('unconfirmed',result['basis'])
        self.assertIsNone(app.next_run(index,{**v,'timestamp':int(now.timestamp())-900},now))
        no_block=app.parse_static_gtfs(sample_gtfs(False))
        self.assertIsNone(app.next_run(no_block,v,now))
        not_active={**v,'start_date':'20261107'}
        next_day=datetime(2026,11,7,10,19,tzinfo=app.TIMEZONE)
        not_active['timestamp']=int(next_day.timestamp())
        self.assertIsNone(app.next_run(index,not_active,next_day))

    def test_details_and_revision_cache(self):
        index=app.parse_static_gtfs(sample_gtfs())
        with tempfile.TemporaryDirectory() as temp, patch.object(app,'INDEX_PATH',Path(temp)/'cache.gz'):
            tracker=app.Tracker()
            tracker.update_index(index,persist=False)
            tracker.vehicles=[{'id':'BUS-8','trip_id':'trip_95','route_id':None,'lat':48.45,'lon':-123.49,
                'bearing':None,'speed_mps':None,'timestamp':int(time.time()),'stop_sequence':2,'stop_status':2}]
            result=tracker.snapshot()
            self.assertEqual(result['vehicles'][0]['route'],'95')
            self.assertEqual(result['vehicles'][0]['headsign'],'Downtown')
            self.assertEqual(tracker.snapshot(result['revision'])['unchanged'],True)
            self.assertEqual(tracker.route_detail('trip_95')['stops'][1]['name'],'Helmcken')
            self.assertIsNone(tracker.route_detail('invalid'))

if __name__ == '__main__': unittest.main()
