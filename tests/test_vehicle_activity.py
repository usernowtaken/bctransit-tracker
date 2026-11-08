"""Checks activity summarization, migration and conservative public status wording."""
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from gps_history import GPSHistory
from vehicle_activity import build_activity


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'history.sqlite3'
        self.now = int(time.time())
        self.db = GPSHistory(self.path)
        self.idx = {'routes': {'r14': {'short':'14'}, 'r50':{'short':'50'}}, 'trips': {}}

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def add(self, ts, route='r14', state='near', system='victoria', ident='bus1248'):
        v={'id':ident,'route_id':route,'lat':48.45+(ts%100)*.00001,'lon':-123.47,
           'timestamp':ts,'label':'3131351248'}
        return self.db.append(system,[v],self.idx,now=ts,
                              proximity={ident:{'state':state,'distance_m':900 if state=='likely_nis' else 3}})

    def test_reporting_route_change_is_observed_not_scheduled(self):
        self.add(self.now-160,'r14')
        self.add(self.now-120,'r14')
        self.add(self.now-70,'r50')
        self.add(self.now-25,'r50')
        data=self.db.activity('victoria','bus1248',60,now=self.now)
        self.assertEqual(data['reported_route_changes'],1)
        self.assertEqual(data['distinct_routes'],['14','50'])
        self.assertEqual([e['kind'] for e in data['events']],['reported','route_change','reported'])
        self.assertEqual(data['events'][1]['from_route'],'14')
        self.assertEqual(data['events'][1]['to_route'],'50')

    def test_possible_nis_never_claims_confirmed(self):
        self.add(self.now-120,state='near')
        self.add(self.now-60,state='likely_nis')
        self.add(self.now-25,state='likely_nis')
        data=self.db.activity('victoria','bus1248',60,now=self.now)
        self.assertEqual(data['off_route_observations'],2)
        self.assertEqual(data['events'][0]['kind'],'off_route')
        self.assertEqual(data['events'][0]['off_route_evidence'],'likely_nis')
        self.assertIn('not confirmed',data['disclaimer'].lower())

    def test_gap_does_not_invent_route_switch(self):
        self.add(self.now-1700,'r14')
        self.add(self.now-40,'r50')
        data=self.db.activity('victoria','bus1248',60,now=self.now)
        self.assertEqual(data['reported_route_changes'],0)
        self.assertIn('gap',[e['kind'] for e in data['events']])

    def test_deduplication_system_isolation_and_windows(self):
        self.add(self.now-40,'r14')
        self.assertEqual(self.add(self.now-40,'r14'),0)
        self.add(self.now-20,'r50',system='kelowna')
        result=self.db.activity('victoria','bus1248',60,now=self.now)
        self.assertEqual(result['recorded_fixes'],1)
        self.assertEqual(self.db.activity('kelowna','bus1248',60,now=self.now)['recorded_fixes'],1)
        for bad in ('invalid', '', 'outside'):
            with self.assertRaises(ValueError):self.db.activity(bad,'bus1248',60,now=self.now)
        with self.assertRaises(ValueError):self.db.activity('victoria','bus1248',99,now=self.now)
        with self.assertRaises(ValueError):self.db.activity('victoria','',60,now=self.now)

    def test_beta_schema_migration_preserves_data(self):
        self.db.close()
        self.db.db = sqlite3.connect(str(self.path))  # temporary handle for controlled legacy setup
        self.db.db.execute('DROP TABLE fixes')
        self.db.db.execute('''CREATE TABLE fixes (system TEXT NOT NULL, vehicle_id TEXT NOT NULL,
            gps_ts INTEGER NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, route TEXT,
            trip_id TEXT, label TEXT, recorded_at INTEGER NOT NULL,
            PRIMARY KEY(system,vehicle_id,gps_ts))''')
        self.db.db.execute('''INSERT INTO fixes VALUES (?,?,?,?,?,?,?,?,?)''',
            ('victoria','bus1248',self.now-40,48.5,-123.5,'14','t1','3131351248',self.now))
        self.db.db.commit();self.db.db.close()
        self.db=GPSHistory(self.path)
        result=self.db.activity('victoria','bus1248',60,now=self.now)
        self.assertEqual(result['recorded_fixes'],1)
        self.assertEqual(result['events'][0]['route'],'14')
        self.assertEqual(result['events'][0]['kind'],'reported')
        self.add(self.now-20,'r50')
        self.assertEqual(self.db.activity('victoria','bus1248',60,now=self.now)['reported_route_changes'],1)

    def test_only_observations_no_inferred_time(self):
        rows=[(1000,48.5,-123.4,'14','t1',None), (1090,48.5,-123.4,'14','t1',None)]
        data=build_activity(rows,'victoria','x',60,1120)
        self.assertEqual(data['recorded_fixes'],2)
        self.assertEqual(data['events'][0]['fixes'],2)
        self.assertEqual(data['reported_route_changes'],0)

if __name__ == '__main__': unittest.main()
