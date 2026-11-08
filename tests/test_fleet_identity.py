"""Offline tests for fleet pattern + model lookup; no feed downloads."""
import unittest
from fleet_identity import identify_vehicle, series_for, VICTORIA_FLEET_SERIES

class FleetIdentityTests(unittest.TestCase):
    def test_recognized_suffixes(self):
        for number, model in [('7513','New Flyer XE40'), ('1248','New Flyer XN40'),
                              ('4237',"Vicinity 30′ CNG"), ('9532','Alexander Dennis Enviro500 MMC')]:
            v=identify_vehicle('victoria','313135'+number)
            self.assertEqual(v['fleet_number'],number)
            self.assertEqual(v['model'],model)
            self.assertEqual(v['fleet_status'],'candidate')
            self.assertIn('label',v['fleet_basis'])
    def test_model_boundaries(self):
        self.assertEqual(series_for('9529')['model_key'],'enviro500')
        self.assertEqual(series_for('9532')['model_key'],'enviro500mmc')
        self.assertEqual(series_for('9435')['model_key'],'nova3')
        self.assertEqual(series_for('9300')['model_key'],'nova2')
        self.assertEqual(series_for('9447')['model_key'],'nova3')
        self.assertEqual(series_for('9350')['model_key'],'nova2')
        self.assertIsNone(series_for('7075'))
        self.assertEqual(series_for('7525')['model_key'], 'xe40')
        self.assertEqual(series_for('7526')['model_key'], 'xe40')
        self.assertEqual(series_for('7527')['model_key'], 'generic')
        self.assertIsNone(series_for('7600'))
        provisional=identify_vehicle('victoria','3131357532')
        self.assertEqual(provisional['fleet_number'],'7532')
        self.assertEqual(provisional['model_key'],'generic')
    def test_unverified_patterns_are_not_claimed(self):
        for label in ['something7513','131357513','1234567513','3131357075','3131359658','313135-7513','000000','']:
            result=identify_vehicle('victoria',label)
            self.assertIsNone(result['fleet_number'],label)
            self.assertIsNone(result['model'],label)
    def test_no_other_region_assumption(self):
        for system in ['kelowna','chilliwack']:
            self.assertIsNone(identify_vehicle(system,'3131357513')['fleet_number'])
    def test_explicit_four_digit_label_candidate(self):
        self.assertEqual(identify_vehicle('victoria',' 1248 ')['fleet_number'],'1248')
    def test_snapshot_exposes_enriched_fleet_candidate(self):
        import app
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import time
        with tempfile.TemporaryDirectory() as temp, patch.object(app, 'CACHE_DIR', Path(temp)):
            tracker=app.Tracker('victoria')
            tracker.index={'routes':{'r14':{'short':'14','long':'Victoria'}},'trips':{},
                           'trip_stops':{},'shapes':{},'route_shapes':{},
                           'route_short_ids':{},'block_trips':{},'updated_at':None}
            tracker.vehicles=[{'id':'a', 'label':'3131351248', 'lat':48.45,'lon':-123.49,
                               'timestamp':int(time.time()), 'route_id':'r14'}]
            snap=tracker.snapshot()
            self.assertEqual(snap['vehicles'][0]['fleet_number'],'1248')
            self.assertEqual(snap['vehicles'][0]['model_key'],'xn40')
            self.assertEqual(snap['vehicles'][0]['label'],'3131351248')
            self.assertEqual(snap['vehicles'][0]['route'],'14')
    def test_model_illustrations_have_no_duplicated_series(self):
        for i,(lo,hi,*_) in enumerate(VICTORIA_FLEET_SERIES):
            for nextlo,nexthi,*_ in VICTORIA_FLEET_SERIES[i+1:]:
                self.assertFalse(max(lo,nextlo)<=min(hi,nexthi))
if __name__=='__main__':unittest.main()
