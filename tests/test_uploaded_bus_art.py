"""Check the V3 artwork preserves the original user drawings (including revised Vicinity)."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / 'web' / 'buses'
NEW_ASSETS = {'nova_smart','nova_lfse'}
EXPECTED = {
  'xe40','enviro500mmc_classic','xn40_cng','enviro500mmc_green',
  'xn40_classic','xn40_greenrear','nova2','vicinity30','nova3','enviro500'
}

class UploadedBusArtworkTests(unittest.TestCase):
    def test_original_sheet_exact_bytes(self):
        data=json.loads((ROOT/'asset-map.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT/'full-original.png').read_bytes()).hexdigest(),data['sha256'])

    def test_only_user_drawings_and_no_svg_substitutes(self):
        self.assertFalse(list(ROOT.glob('*.svg')))
        data=json.loads((ROOT/'asset-map.json').read_text())
        self.assertEqual(set(data['assets']),EXPECTED)
        self.assertEqual({p.stem for p in ROOT.glob('*.png') if p.stem not in {'full-original','vicinity30-user-original'}},EXPECTED | NEW_ASSETS)

    def test_all_visible_pixels_identical_to_original(self):
        data=json.loads((ROOT/'asset-map.json').read_text())
        source=Image.open(ROOT/'full-original.png').convert('RGBA')
        for name,entry in data['assets'].items():
            with self.subTest(asset=name):
                rect=entry['source_rect']
                crop=np.array(Image.open(ROOT/entry['file']).convert('RGBA'))
                origin=Image.open(ROOT/entry.get('source','full-original.png')).convert('RGBA')
                original=np.array(origin.crop(tuple(rect)))
                self.assertEqual(crop.shape,original.shape)
                visible=crop[:,:,3]>0
                self.assertTrue(np.array_equal(crop[:,:,:3][visible],original[:,:,:3][visible]))
                self.assertTrue(np.count_nonzero(crop[:,:,3]==0)>0)
                self.assertEqual(int(crop[:,:,3].max()),255)

if __name__ == '__main__': unittest.main()
