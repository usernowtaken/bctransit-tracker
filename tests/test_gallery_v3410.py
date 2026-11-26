from pathlib import Path
import unittest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
class FleetGalleryV3410(unittest.TestCase):
    def test_new_art_is_present_and_versioned(self):
        gallery=(ROOT/'web/fleet-gallery.html').read_text()
        for name in ('vicinity35','handydart_old','handydart_new','nova_lfse','vicinity30'):
            self.assertIn('/buses/'+name+'.png?v=4.0-alpha',gallery)
            img=Image.open(ROOT/'web/buses'/f'{name}.png').convert('RGBA')
            self.assertEqual(img.getpixel((0,0))[3],0)
        self.assertEqual(gallery.count('PLACEHOLDER / N/A'),1)
    def test_cache_invalidation(self):
        html=(ROOT/'web/index.html').read_text()
        py=(ROOT/'app.py').read_text()
        js=(ROOT/'web/app.js').read_text()
        sw=(ROOT/'web/sw.js').read_text()
        self.assertIn('href="/fleet-gallery.html?v=4.0-alpha"',html)
        self.assertIn('"/fleet-gallery.html", "/sw.js"',py)
        self.assertIn("'.png?v=4.0-alpha'",js)
        self.assertIn('victoria-bus-radar-shell-v4.0-alpha',sw)
