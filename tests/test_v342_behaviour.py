"""V3.4.2 deterministic NIS, heading and future *different route* tests.

Run normally after `pip install -r requirements.txt`.
"""
import unittest
from datetime import datetime
import app


class Version342Tests(unittest.TestCase):
    def test_generic_route_pair_is_likely_nis(self):
        self.assertEqual(app.infer_service_label(None,'Royal Oak Exch/Westhills Exch')['state'],'likely_nis')
        self.assertEqual(app.infer_service_label('Royal Oak Exch/Westhills Exch','Royal Oak Exch/Westhills Exch')['state'],'likely_nis')
        self.assertEqual(app.infer_service_label('to Royal Oak Exch','Royal Oak Exch/Westhills Exch')['state'],'regular')
        self.assertEqual(app.infer_service_label('Royal Oak Exch','Royal Oak Exch/Westhills Exch')['state'],'regular')
        self.assertEqual(app.infer_service_label(None,'Downtown')['state'],'unknown')
        self.assertEqual(app.infer_service_label('via Saanich','Royal Oak Exch/Westhills Exch')['state'],'regular')

    def test_route_aligned_heading_uses_assigned_trip_direction(self):
        timestamp = 1785000000
        shape = [[48.45,-123.5],[48.45,-123.495],[48.45,-123.49]]
        reverse=list(reversed(shape))
        index={'trips':{'e':{'route_id':'r38','shape_id':'east'},'w':{'route_id':'r38','shape_id':'west'}},
               'routes':{'r38':{'short':'38'}},'shapes':{'east':shape,'west':reverse}}
        base={'trip_id':'e','route_id':'r38','lat':48.45001,'lon':-123.496,
              'bearing':70.,'timestamp':timestamp,'speed_mps':8.0}
        result=app.route_aligned_bearing(index,base,timestamp)
        self.assertLess(abs(result['display_bearing']-90),3)
        self.assertIn('trip shape',result['bearing_basis'])
        result=app.route_aligned_bearing(index,{**base,'trip_id':'w','bearing':270.},timestamp)
        self.assertLess(abs(result['display_bearing']-270),3)
        # A stale GPS observation must not be forcibly turned to the route.
        self.assertEqual(app.route_aligned_bearing(index,base,timestamp+130)['display_bearing'],70.)
        # A real opposite-direction reading should not be overridden by a wrong trip assignment.
        self.assertEqual(app.route_aligned_bearing(index,{**base,'bearing':270.},timestamp)['display_bearing'],270.)
        self.assertEqual(app.route_aligned_bearing(index,{**base,'lat':48.454},timestamp)['display_bearing'],70.)
        self.assertEqual(app.route_aligned_bearing(index,{**base,'trip_id':None},timestamp)['display_bearing'],70.)

    def test_next_run_skips_same_public_route_even_when_trip_ids_differ(self):
        now=datetime(2026,11,22,8,35,tzinfo=app.TIMEZONE)
        def trip(route,first,last):
            return {'route_id':route,'block_id':'A','service_id':'daily','first':first,'last':last,'headsign':'Another direction' if route.startswith('r57') else 'Downtown'}
        index={'trips':{
              'first':trip('r57a',8*3600,9*3600),
              'return':trip('r57b',9*3600+15*60,10*3600),
              'another57':trip('r57a',10*3600+15*60,11*3600),
              'diff':trip('r61',11*3600+15*60,12*3600),
              'later':trip('r14',12*3600+15*60,13*3600)},
            'routes':{'r57a':{'short':'57'},'r57b':{'short':'57'},'r61':{'short':'61'},'r14':{'short':'14'}},
            'blocks':{'A':['first','return','another57','diff','later']},
            'service_days':{'daily':{'start':'20260101','end':'20281231','weekdays':[True]*7}},
            'exceptions':{}}
        vehicle={'trip_id':'first','timestamp':int(now.timestamp()),'start_date':'20261122'}
        nxt=app.next_run(index,vehicle,now)
        self.assertEqual(nxt['route'],'61')
        self.assertEqual(nxt['trip_id'],'diff')
        self.assertEqual(nxt['skipped_same_route'],2)
        self.assertTrue(nxt['different_route'])
        # No actually different number? Do not show the return trip.
        index['blocks']['A']=['first','return','another57']
        self.assertIsNone(app.next_run(index,vehicle,now))

if __name__=='__main__': unittest.main()
