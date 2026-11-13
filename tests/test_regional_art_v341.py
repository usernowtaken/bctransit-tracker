"""V3.4.1 profile assets and regional fleet classifications (offline)."""
import hashlib
from pathlib import Path
import unittest
from fleet_identity import identify_vehicle, regional_series_for
ROOT=Path(__file__).resolve().parents[1]

class RegionalArtTests(unittest.TestCase):
    def test_smart_vehicle_is_victoria_only(self):
        v=identify_vehicle('victoria','3131359434')
        self.assertEqual(v['nova_special'],'smart_lfs_9434')
        self.assertEqual(v['model_key'],'nova3')
        self.assertIsNone(identify_vehicle('kelowna','9434')['model'])
    def test_electric_model_is_regional_and_provisional(self):
        for num in ('7010','7013','7020','7031'):
            with self.subTest(num=num):
                v=identify_vehicle('kelowna', num)
                self.assertEqual(v['fleet_number'],num)
                self.assertEqual(v['model_key'],'nova_lfse')
                self.assertIn('Provisional', v['model_basis'])
        self.assertIsNone(identify_vehicle('chilliwack','7010')['fleet_number'])
    def test_small_buses_not_misclassified_as_nova(self):
        for sys, num in [('kelowna','2875'),('kelowna','2922'),('chilliwack','2958')]:
            with self.subTest(sys=sys,num=num):
                self.assertEqual(identify_vehicle(sys,num)['model_key'],'light_duty')
    def test_regional_gen2_and_gen3(self):
        for sys in ('kelowna','chilliwack'):
            self.assertEqual(identify_vehicle(sys,'9303')['model_key'],'nova2')
            self.assertEqual(identify_vehicle(sys,'9426')['nova_generation'],3)
        self.assertEqual(identify_vehicle('kelowna','6012')['nova_generation'],4)
    def test_unknown_labels_and_models_are_left_unknown(self):
        for sys in ('kelowna','chilliwack'):
            for label in ('something7010','3131359999','x7010','701000',''):
                self.assertIsNone(identify_vehicle(sys,label)['fleet_number'])
    def test_exact_supplied_image_bytes(self):
        names={'nova_smart.png':'novabus 2012.png', 'nova_lfse.png':'novabus lfse.png'}
        for out,original in names.items():
            with self.subTest(out=out):
                self.assertEqual((ROOT/'web/buses'/out).read_bytes(), (Path('/mnt/data')/original).read_bytes())
    def test_placeholder_on_profile(self):
        html=(ROOT/'web/index.html').read_text()
        js=(ROOT/'web/app.js').read_text()
        self.assertIn('id="fleetNoImage"',html)
        self.assertIn("vehicle.model_key === 'light_duty'", js)
        self.assertIn('NO IMAGE', html)

if __name__=='__main__':unittest.main()
