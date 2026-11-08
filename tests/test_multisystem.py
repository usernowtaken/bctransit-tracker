"""Multi-region and service-state regression tests. Run with project dependencies installed."""
from pathlib import Path
from unittest.mock import patch
import time
import unittest
import tempfile
import app


class MultiSystemTests(unittest.TestCase):
    def test_verified_system_ids_and_separate_urls(self):
        self.assertEqual({key: value['operator'] for key,value in app.SYSTEMS.items()},
                         {'victoria':48,'chilliwack':13,'kelowna':47})
        self.assertIn('operatorIds=13',app.system_feed_url('chilliwack','vehicle'))
        self.assertIn('operatorIds=47',app.system_feed_url('kelowna','static'))
        self.assertIn('operatorIds=48',app.system_feed_url('victoria','trip'))

    def test_chilliwack_shares_feed_but_filters_abbotsford_routes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app,'CACHE_DIR',Path(temp)):
            tracker=app.Tracker('chilliwack')
            tracker.index={'routes':{'route51':{'short':'51','long':'Vedder'},
                                     'route66':{'short':'66','long':'Fraser Valley Express'},
                                     'route1':{'short':'1','long':'Highstreet'}},
                           'trips':{}, 'updated_at':int(time.time())}
            tracker.vehicles=[
                {'id':'a','route_id':'route51','lat':49.158,'lon':-121.955,'timestamp':int(time.time())},
                {'id':'b','route_id':'route1','lat':49.060,'lon':-122.3,'timestamp':int(time.time())},
                {'id':'c','route_id':'route66','lat':49.060,'lon':-122.3,'timestamp':int(time.time())},
                {'id':'d','route_id':None,'lat':49.16,'lon':-121.95,'timestamp':int(time.time())},
                {'id':'e','route_id':None,'lat':49.060,'lon':-122.3,'timestamp':int(time.time())},
            ]
            result=tracker.snapshot()
            self.assertEqual({v['id'] for v in result['vehicles']},{'a','c','d'})
            self.assertEqual(result['system'],'chilliwack')
            self.assertEqual(result['count'],3)

    def test_separate_tracker_cache_and_snapshot(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(app,'CACHE_DIR',Path(temp)):
            victoria=app.Tracker('victoria')
            kelowna=app.Tracker('kelowna')
            self.assertNotEqual(victoria.index_path,kelowna.index_path)
            self.assertNotEqual(victoria.urls['vehicle'],kelowna.urls['vehicle'])
            victoria.vehicles=[{'id':'same-id','route_id':None,'lat':48.44,'lon':-123.50,
                                'timestamp':int(time.time())}]
            kelowna.vehicles=[{'id':'same-id','route_id':None,'lat':49.89,'lon':-119.50,
                               'timestamp':int(time.time())}]
            self.assertEqual(victoria.snapshot()['vehicles'][0]['lat'],48.44)
            self.assertEqual(kelowna.snapshot()['vehicles'][0]['lat'],49.89)

    def test_offroute_confidence_grows_without_calling_it_confirmed(self):
        now=int(time.time())
        index={'routes':{'r':{'short':'14'}},'trips':{'t':{'route_id':'r','shape_id':'s'}},
               'shapes':{'s':[[48.450,-123.500],[48.450,-123.490]]}}
        index['route_shapes']=app.build_route_shapes(index['trips'],index['shapes'])
        readings=[{'id':'bus','route_id':'r','trip_id':'t','lat':48.465,'lon':-123.495,
                   'timestamp':now+i*20, 'timestamp_source':'vehicle'} for i in range(4)]
        states=[]; previous={}
        for reading in readings:
            previous=app.update_proximity_observations(index,[reading],previous,reading['timestamp'])
            states.append(previous['bus']['state'])
        self.assertEqual(states,['far','possible_nis','possible_nis','likely_nis'])
        previous=app.update_proximity_observations(index,[readings[-1]],previous,readings[-1]['timestamp'])
        self.assertEqual(previous['bus']['state'],'likely_nis')
        returned={**readings[-1],'lat':48.450,'lon':-123.495,'timestamp':now+85}
        previous=app.update_proximity_observations(index,[returned],previous,returned['timestamp'])
        self.assertEqual(previous['bus']['state'],'near')

if __name__=='__main__': unittest.main()
