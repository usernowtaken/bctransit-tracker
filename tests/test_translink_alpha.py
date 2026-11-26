import unittest, tempfile, time, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.error import HTTPError
from translink import RequestBudget, TransLink
from translink_fleet import identify
from fleet_identity import identify_feed_vehicle
from gps_history import GPSHistory

class BudgetTests(unittest.TestCase):
    def test_rolling_persistent_caps_and_concurrency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'budget.db'; budget=RequestBudget(path,100); now=100000.
            with ThreadPoolExecutor(max_workers=12) as pool:
                accepted=list(pool.map(lambda _:budget.reserve('vehicle',now),range(100)))
            self.assertEqual(sum(accepted),80)
            b=RequestBudget(path,100)
            self.assertFalse(b.reserve('vehicle',now+1))
            self.assertEqual(sum(b.reserve('trip',now) for _ in range(20)),15)
            self.assertEqual(sum(b.reserve('alerts',now) for _ in range(10)),5)
            self.assertFalse(b.reserve('alerts',now+86399))
            self.assertTrue(b.reserve('vehicle',now+86400))
    def test_no_key_no_requests_and_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=TransLink(Path(tmp)/'b.db',key='')
            self.assertFalse(p.active()); self.assertIsNone(p.fetch('vehicle',10)); self.assertEqual(p.status()['used'],0)
            p.touch();self.assertTrue(p.active());self.assertFalse(p.status()['configured'])
    def test_intervals_and_failed_request_accounting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ',{'TRANSLINK_GPS_SECONDS':'20'}):
            p=TransLink(Path(tmp)/'b.db',key='dummy-test-secret',limit=100)
            self.assertEqual(p.interval({'vehicle':0}),20);self.assertEqual(p.interval({'vehicle':40}),40);self.assertEqual(p.interval({'vehicle':64}),90)
            with patch.object(p.opener,'open',side_effect=HTTPError('https://example.com/?secret=dummy-test-secret',429,'rate limit',{},None)) as call:
                with self.assertRaisesRegex(RuntimeError,'TransLink HTTP 429'):p.fetch('vehicle',100)
                self.assertIsNone(p.fetch('trip',100)); self.assertEqual(call.call_count,1)
            self.assertEqual(p.status()['used'],1);self.assertNotIn('dummy-test-secret',json.dumps(p.status()))
    def test_fleet_formats_and_unknowns(self):
        for label,expected,key in [('V2138','2138','tl_e40'),('B18024','18024','tl_xde60'),('80701','701','tl_lfs'),('23201','23201','tl_lfse'),('55555','55555','generic')]:
            result=identify_feed_vehicle('vancouver',label,None); self.assertEqual((result['fleet_number'],result['model_key']),(expected,key))
        self.assertIsNone(identify(None,'3131359426')['fleet_number']);self.assertIsNone(identify(None,'55555')['fleet_number'])
        self.assertEqual(identify_feed_vehicle('victoria','3131359426',None)['fleet_number'],'9426')
    def test_history_isolation_and_5digit_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            history=GPSHistory(str(Path(tmp)/'h.db')); now=int(time.time())
            v={'id':'same','descriptor_id':'18024','label':'18024','timestamp':now,'lat':49.2,'lon':-123.1}
            history.append('vancouver',[v],now=now)
            self.assertTrue(history.last_known('vancouver',fleet='18024',now=now)['found']);self.assertFalse(history.last_known('victoria',vehicle_id='same',now=now)['found'])
            history.close()

if __name__=='__main__':unittest.main()
