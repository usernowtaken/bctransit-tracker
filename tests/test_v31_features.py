"""Offline V3.1 tests: historical last-known and service alert GTFS matching."""
from __future__ import annotations
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from gps_history import GPSHistory
from service_alerts import parse_alert_feed, alert_applies

class Scalar:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
    def HasField(self, key): return getattr(self, key, None) is not None

class FakeFeed(Scalar):
    def ParseFromString(self, body): pass

class V31Tests(unittest.TestCase):
    def test_last_known_victoria_by_fleet(self):
        now=int(time.time())
        with tempfile.TemporaryDirectory() as temp:
            db=GPSHistory(Path(temp)/'gps.sqlite')
            db.append('victoria',[{'id':'raw1','label':'3131359434','lat':48.42,'lon':-123.38,'timestamp':now-40,'route_id':'r14'}],
                      {'routes':{'r14':{'short':'14'}},'trips':{}},now=now)
            found=db.last_known('victoria',fleet='9434',now=now)
            self.assertTrue(found['found'])
            self.assertEqual(found['vehicle']['route'],'14')
            self.assertTrue(found['history_only'])
            self.assertEqual(found['vehicle']['id'],'raw1')
            self.assertFalse(db.last_known('victoria',fleet='9435',now=now)['found'])
            db.close()
    def test_last_known_system_separation_and_id(self):
        now=int(time.time())
        with tempfile.TemporaryDirectory() as temp:
            db=GPSHistory(Path(temp)/'gps.sqlite')
            db.append('kelowna',[{'id':'raw2','lat':49.9,'lon':-119.5,'timestamp':now-60}],now=now)
            self.assertTrue(db.last_known('kelowna',vehicle_id='raw2',now=now)['found'])
            self.assertFalse(db.last_known('victoria',vehicle_id='raw2',now=now)['found'])
            with self.assertRaises(ValueError): db.last_known('kelowna',fleet='9434',now=now)
            db.close()
    def test_last_known_expired(self):
        now=int(time.time())
        with tempfile.TemporaryDirectory() as temp:
            db=GPSHistory(Path(temp)/'gps.sqlite')
            db.append('victoria',[{'id':'raw1','label':'3131359434','lat':48.42,'lon':-123.38,'timestamp':now-60}],now=now)
            self.assertFalse(db.last_known('victoria',fleet='9434',now=now+86401)['found'])
            db.close()
    def test_selector_and_semantics(self):
        selectors=[{'route_id':'r14','trip_id':'t1','stop_id':'','agency_id':''}]
        self.assertTrue(alert_applies(selectors,route_id='r14',trip_id='t1'))
        self.assertFalse(alert_applies(selectors,route_id='r14',trip_id='t2'))
        self.assertFalse(alert_applies([{'route_id':'r14','stop_id':'s4'}],route_id='r14'))
        self.assertTrue(alert_applies([{'route_id':'r14','stop_id':'s4'}],route_id='r14',stop_id='s4'))
    def test_alert_parser(self):
        now=int(time.time())
        def translation(text): return Scalar(translation=[Scalar(text=text,language='en')])
        alert=Scalar(informed_entity=[Scalar(route_id='r14',agency_id=None,stop_id=None,trip=None)],
                     active_period=[Scalar(start=now-20,end=now+20)],
                     communication_period=[],header_text=translation('Construction detour'),
                     description_text=translation('Route 14 detoured'),url=translation('https://example.org/alert'),effect=4)
        entity=Scalar(id='A1',alert=alert,is_deleted=False)
        feed=FakeFeed(header=Scalar(timestamp=now),entity=[entity])
        parsed=parse_alert_feed(b'ignored',SimpleNamespace(FeedMessage=lambda: feed),now=now)
        self.assertEqual(parsed['alerts'][0]['effect'],'Detour')
        self.assertEqual(parsed['alerts'][0]['selectors'][0]['route_id'],'r14')
        self.assertTrue(parsed['alerts'][0]['url'].startswith('https://'))

if __name__=='__main__':unittest.main()
