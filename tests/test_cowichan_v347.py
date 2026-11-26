"""V4.0 Alpha Cowichan and Kelowna-only Gen 4 reference tests (offline)."""
import pathlib
import unittest
from fleet_identity import identify_vehicle, identify_feed_vehicle
from gps_history import GPSHistory
import tempfile
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]

class CowichanV347(unittest.TestCase):
    def test_fleet_models_are_bounded_and_regions_distinct(self):
        cases = {
            '2842': ('light_duty', 'ARBOC', None),
            '2844': ('light_duty', 'ARBOC', None),
            '2819': ('light_duty', 'unverified', None),
            '4013': ('vicinity30', '30′', None),
            '4017': ('vicinity30', '30′', None),
            '4019': ('vicinity30', '30′', None),
            '4020': ('vicinity30', '30′', None),
            '4025': ('vicinity30', '30′', None),
            '4432': ('vicinity35', '35′', None),
            '4471': ('vicinity35', '35′', None),
            '4474': ('vicinity35', '35′', None),
            '9294': ('nova2', 'Suburban', 2),
            '9295': ('nova2', 'Suburban', 2),
            '9297': ('nova2', 'Suburban', 2),
            '9300': ('nova2', 'Suburban', 2),
            '9388': ('nova3', 'Gen 3', 3),
            '9451': ('nova3', 'Gen 4', 4),
        }
        for num, (key, text, generation) in cases.items():
            with self.subTest(fleet=num):
                row=identify_vehicle('cowichan',num)
                self.assertEqual(row['fleet_number'],num)
                self.assertEqual(row['model_key'],key)
                self.assertIn(text,row['model'])
                if generation: self.assertEqual(row['nova_generation'],generation)
                self.assertEqual(row['fleet_status'], 'candidate')
        for num in ('3007','4232','6005','7005','9999'):
            self.assertIsNone(identify_vehicle('cowichan',num)['fleet_number'], num)

    def test_regional_descriptor_format_bounded(self):
        self.assertEqual(identify_feed_vehicle('cowichan',None,'3131354471')['fleet_number'], '4471')
        self.assertEqual(identify_feed_vehicle('cowichan','Bus #9300','non-id')['fleet_number'], '9300')
        self.assertEqual(identify_feed_vehicle('cowichan',None,'4474')['fleet_number'], '4474')
        self.assertIsNone(identify_feed_vehicle('cowichan',None,'9999994474')['fleet_number'])
        self.assertIsNone(identify_feed_vehicle('cowichan',None,'3131359999')['fleet_number'])

    def test_history_keeps_cowichan_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            store=GPSHistory(pathlib.Path(td)/'history.sqlite3')
            try:
                now=1795000000
                for system in ('cowichan','victoria'):
                    row={'id':'same-id','timestamp':now,'lat':48.45,'lon':-123.38,'label':'9300'}
                    self.assertEqual(store.append(system,[row],now=now),1)
                    self.assertEqual(store.get(system,'same-id',now=now)['count'],1)
                self.assertFalse(store.last_known('kelowna',vehicle_id='same-id',now=now)['found'])
                self.assertTrue(store.last_known('cowichan',fleet='9300',now=now)['found'])
            finally: store.close()

    def test_frontend_system_and_gen4_fallback(self):
        app_js=(ROOT/'web/app.js').read_text()
        html=(ROOT/'web/index.html').read_text()
        self.assertIn("cowichan: {name:'Cowichan Valley'",app_js)
        self.assertIn('<option value="cowichan">Cowichan Valley</option>',html)
        self.assertIn("state.system === 'kelowna'",app_js)
        self.assertIn("{id:'nova3', name:'Gen 3 reference drawing",app_js)
        self.assertIn('PLACEHOLDER / N/A',app_js)
        self.assertIn('NovaBus LFS Gen 4 (Kelowna / Chilliwack / Cowichan)', (ROOT/'web/fleet-gallery.html').read_text())
        self.assertIn('uses the Gen 3 reference drawing', (ROOT/'web/fleet-gallery.html').read_text())

    def test_dedicated_operator_and_all_commuter_bounds(self):
        # Run safely in unit environments lacking gtfs-realtime-bindings. The
        # configuration is literal Python data and import-free AST is sufficient.
        import ast
        source=(ROOT/'app.py').read_text()
        tree=ast.parse(source)
        assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEMS' for t in n.targets))
        systems=ast.literal_eval(assignment.value)
        self.assertEqual(systems['cowichan']['operator'],10)
        a,b,c,d=systems['cowichan']['bounds']
        for lat,lon in [(48.426,-123.370), (48.779,-123.705), (49.166,-123.94), (48.84,-124.06)]:
            self.assertLessEqual(a,lat)
            self.assertLessEqual(lat,b)
            self.assertLessEqual(c,lon)
            self.assertLessEqual(lon,d)
        self.assertNotEqual(systems['cowichan']['operator'],systems['victoria']['operator'])

if __name__=='__main__':unittest.main()
