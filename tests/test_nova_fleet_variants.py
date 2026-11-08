"""Focused offline regression tests for photo-backed NovaBus fleet details."""
import unittest
from pathlib import Path
from fleet_identity import identify_vehicle, nova_body_for

ROOT = Path(__file__).resolve().parents[1]

class NovaFleetVariantTests(unittest.TestCase):
    def test_photo_confirmed_rear_roofs(self):
        cases = {'9287':'flat', '9303':'flat', '9426':'raised', '9434':'smart'}
        for fleet, expected in cases.items():
            with self.subTest(fleet=fleet):
                data = identify_vehicle('victoria', '313135' + fleet)
                self.assertEqual(data.get('nova_body_variant'), expected)
                self.assertTrue(data.get('nova_body_basis'))
                self.assertIn(data['model_key'], {'nova2', 'nova3'})

    def test_9434_smart_prototype_identity(self):
        vehicle = identify_vehicle('victoria','3131359434')
        self.assertEqual(vehicle['nova_special'], 'smart_lfs_9434')
        self.assertIn('Smart Bus', vehicle['model'])
        self.assertEqual(vehicle['model_key'], 'nova3')

    def test_unknown_2009_roofs_are_not_assumed(self):
        for fleet in ['9319','9332','9354','9387','9418','9433']:
            with self.subTest(fleet=fleet):
                vehicle = identify_vehicle('victoria', '313135' + fleet)
                self.assertEqual(vehicle['model'], 'NovaBus LFS Gen 3 (2009)')
                self.assertNotIn('nova_body_variant', vehicle)
                self.assertIsNone(nova_body_for(fleet))
                self.assertNotIn('nova_special',vehicle)

    def test_no_cross_system_2009_assumptions(self):
        for system in ['chilliwack','kelowna']:
            self.assertIsNone(identify_vehicle(system,'3131359426')['fleet_number'])

    def test_all_original_drawings_preserved(self):
        self.assertTrue((ROOT/'web/buses/nova2.png').is_file())
        self.assertTrue((ROOT/'web/buses/nova3.png').is_file())
        self.assertTrue((ROOT/'web/buses/vicinity30.png').is_file())
        self.assertFalse((ROOT/'web/buses/nova_smart_new.png').exists())

    def test_ui_and_cache_versions_match(self):
        html=(ROOT/'web/index.html').read_text()
        js=(ROOT/'web/app.js').read_text()
        sw=(ROOT/'web/sw.js').read_text()
        for term in ('novaSmartSpecial','detailNovaBody'):
            self.assertIn(term,html)
            self.assertIn(term,js)
        self.assertIn('/app.js?v=3.2.0',html)
        self.assertIn('/app.js?v=3.2.0',sw)
        self.assertIn('/v30.css?v=3.0.5',html)
        self.assertIn('/v30.css?v=3.0.5',sw)
        self.assertIn('victoria-bus-radar-shell-v3.2.0',sw)

if __name__ == '__main__':
    unittest.main()
