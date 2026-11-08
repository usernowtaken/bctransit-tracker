"""Static regression checks for Nova 2009 roof choices and Vicinity art."""
import unittest
from pathlib import Path
from PIL import Image
from fleet_identity import series_for
ROOT = Path(__file__).resolve().parents[1]
class Nova2009RoofArt(unittest.TestCase):
    def test_nova_2009_remains_labeled_2009(self):
        for fid in (9319, 9345, 9387, 9433):
            result = series_for(str(fid))
            self.assertEqual(result['model'], 'NovaBus LFS Gen 3 (2009)')
            self.assertEqual(result['model_key'], 'nova2')
    def test_vicinity_preserves_uploaded_canvas(self):
        # Original bytes are retained; display copy only removes exterior bg.
        self.assertTrue((ROOT/'web/buses/vicinity30-user-original.png').exists())
        with Image.open(ROOT/'web/buses/vicinity30.png') as im:
            self.assertEqual(im.mode, 'RGBA')
            self.assertLess(im.getbbox()[2], 402)
    def test_frontend_controls_are_optional(self):
        js=(ROOT/'web/app.js').read_text()
        self.assertIn('VERIFIED_NOVA_2009_REAR_ROOFS',js)
        self.assertNotIn('id="novaRearDetails"',(ROOT/'web/index.html').read_text())
        self.assertIn('NOVA_UNKNOWN_CYCLE_MS = 1500',js)
if __name__=='__main__':unittest.main()
