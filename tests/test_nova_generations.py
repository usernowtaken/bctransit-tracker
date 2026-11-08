"""NovaBus production generation and separately chosen original artwork."""
import unittest
from pathlib import Path
from fleet_identity import identify_vehicle, series_for, nova_body_for

class NovaGenerations(unittest.TestCase):
    def test_boundary_cohorts(self):
        cases = {
            '9201': (2, 'Gen 2'), '9289': (2, 'Gen 2'),
            '9290': (2, 'Gen 2'), '9318': (2, 'Gen 2'),
            '9319': (3, 'Gen 3'), '9426': (3, 'Gen 3'), '9433': (3, 'Gen 3'),
            '9434': (3, 'Smart Bus'), '9435': (4, 'Gen 4'),
            '9446': (4, 'Gen 4'), '9447': (4, 'Gen 4'),
            '9486': (4, 'Gen 4'), '6000': (4, 'Gen 4'), '6029': (4, 'Gen 4'),
        }
        for fleet, (gen, label) in cases.items():
            with self.subTest(fleet=fleet):
                record=identify_vehicle('victoria', '313135'+fleet)
                self.assertEqual(record['nova_generation'], gen)
                self.assertIn(label, record['model'])
    def test_artwork_is_not_generation(self):
        # Gen 3, but can use the flat-body Gen 2 drawing as an illustration.
        flat = series_for('9350')
        self.assertEqual(flat['nova_generation'], 3)
        self.assertEqual(flat['model_key'], 'nova2')
        # Gen 4, but no user-supplied Gen 4 drawing exists.
        newer = series_for('9474')
        self.assertEqual(newer['nova_generation'], 4)
        self.assertEqual(newer['model_key'], 'nova3')
    def test_verified_raised_roof_not_overwritten(self):
        record = identify_vehicle('victoria','3131359426')
        self.assertEqual(record['nova_generation'],3)
        self.assertEqual(record['nova_body_variant'],'raised')
        self.assertEqual(nova_body_for('9303')['variant'],'flat')
    def test_smart_bus_not_called_hybrid(self):
        special=identify_vehicle('victoria','3131359434')
        self.assertEqual(special['nova_special'],'smart_lfs_9434')
        self.assertNotIn('hybrid',special['model'].lower())
        self.assertNotIn('hev',special['model'].lower())
    def test_no_inference_for_other_systems(self):
        for area in ('chilliwack','kelowna'):
            self.assertIsNone(identify_vehicle(area,'3131359434')['fleet_number'])
    def test_browser_generation_filter(self):
        text=(Path(__file__).resolve().parents[1]/'web/app.js').read_text()
        self.assertIn('NOVA_GENERATION_FILTERS',text)
        self.assertIn('Number(v.nova_generation)',text)

if __name__=='__main__': unittest.main()
