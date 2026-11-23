"""V3.4.11 fleet-year, regional, and placeholder regression checks."""
import pathlib
import unittest
from fleet_identity import identify_vehicle, identify_feed_vehicle

ROOT = pathlib.Path(__file__).resolve().parents[1]

class RegionalFleetModelsV346(unittest.TestCase):
    def assertModel(self, system, num, key, fragment, generation=None):
        row = identify_vehicle(system, num)
        self.assertEqual(row['fleet_number'], num)
        self.assertEqual(row['model_key'], key)
        self.assertIn(fragment, row['model'])
        if generation is not None:
            self.assertEqual(row['nova_generation'], generation)

    def test_kelowna_vicinities_and_small_buses(self):
        for num in ('3007', '3011', '3012'):
            self.assertModel('kelowna', num, 'vicinity_2013', '2013')
        for num in ('4400', '4403'):
            self.assertModel('kelowna', num, 'vicinity35', '35′')
        self.assertModel('kelowna', '2922', 'light_duty', 'ARBOC')
        self.assertModel('kelowna', '2876', 'light_duty', 'unverified')
        self.assertIsNone(identify_vehicle('kelowna', '4402')['fleet_number'])
        self.assertIsNone(identify_vehicle('kelowna', '3005')['fleet_number'])

    def test_chilliwack_vicinities(self):
        self.assertModel('chilliwack', '4034', 'vicinity30', '2017')
        self.assertModel('chilliwack', '4401', 'vicinity35', '2017')
        self.assertModel('chilliwack', '4402', 'vicinity35', '2017')
        for num in ('4439','4440','4441'):
            self.assertModel('chilliwack', num, 'vicinity35', '2018')
        self.assertModel('chilliwack', '3005', 'vicinity_2013', '2013')
        self.assertModel('chilliwack', '2958', 'light_duty', 'unverified')

    def test_fraser_valley_xn40_and_vicinity_cng(self):
        for num in ('1201','1214','1219'):
            self.assertModel('chilliwack', num, 'xn40', 'CNG')
        for num in ('4232','4233'):
            self.assertModel('chilliwack', num, 'vicinity30cng', 'CNG')
        self.assertIsNone(identify_vehicle('kelowna','4232')['fleet_number'])
        self.assertIsNone(identify_vehicle('kelowna','1214')['fleet_number'])

    def test_nova_year_boundaries(self):
        for sys in ('chilliwack','kelowna'):
            for num, gen, year in [('9201',2,'2006'),('9231',2,'2006'),
                ('9232',2,'2007'),('9267',2,'2007'),('9268',2,'2008'),
                ('9318',2,'2008'),('9319',3,'2009'),('9433',3,'2009'),
                ('9435',4,'2013'),('9446',4,'2013'),
                ('9447',4,'2015'),('9486',4,'2015')]:
                self.assertModel(sys,num,'nova2' if gen==2 else 'nova3',year,gen)
        self.assertModel('kelowna','6005','nova3','2017',4)
        self.assertModel('kelowna','7031','nova_lfse','provisional')

    def test_prefixed_feed_candidate_recognition(self):
        self.assertModel('chilliwack','4034','vicinity30','2017')
        self.assertEqual(identify_feed_vehicle('chilliwack', '', '3131354034')['fleet_number'],'4034')
        self.assertEqual(identify_feed_vehicle('kelowna', '', '3131353007')['fleet_number'],'3007')
        self.assertIsNone(identify_feed_vehicle('kelowna', '', '3131354402')['fleet_number'])
        self.assertIsNone(identify_feed_vehicle('victoria', '', '3131353007')['fleet_number'])

    def test_source_art_is_unchanged_and_missing_models_placeholder(self):
        js=(ROOT/'web/app.js').read_text()
        html=(ROOT/'web/index.html').read_text()
        gallery=(ROOT/'web/fleet-gallery.html').read_text()
        self.assertIn("Number(vehicle?.nova_generation) === 4) {", js)
        self.assertIn("vehicle?.model_key === 'xn40'", js)
        self.assertIn('PLACEHOLDER / N/A',js)
        self.assertIn('PLACEHOLDER / N/A',html)
        self.assertGreaterEqual(gallery.count('PLACEHOLDER / N/A'),1)
        self.assertIn('/buses/vicinity35.png', gallery)
        self.assertIn('/buses/handydart_old.png', gallery)
        self.assertIn('/buses/handydart_new.png', gallery)
        self.assertIn('V3.4.11',html)

if __name__=='__main__': unittest.main()
