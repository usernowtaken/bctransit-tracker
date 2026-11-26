"""V4.0 Alpha: gallery is compact; each distinct supplied image appears once."""
import unittest
from pathlib import Path
from html.parser import HTMLParser
import json
ROOT=Path(__file__).resolve().parents[1]
NAMES=("vicinity30","vicinity35","handydart_old","handydart_new","nova2","nova3","nova_smart","nova_lfse","xn40_classic","xn40_greenrear","xn40_cng","xe40","enviro500","enviro500mmc_classic","enviro500mmc_green")
class Collector(HTMLParser):
    def __init__(self): super().__init__();self.images=[];self.cards=0;self.details=0
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='img' and d.get('src','').startswith('/buses/'):
            self.images.append(d['src'])
        if t=='article' and 'bus-card' in d.get('class','').split():self.cards+=1
        if t=='details':self.details+=1
class Gallery(unittest.TestCase):
    def test_one_card_per_supplied_image(self):
        source=(ROOT/'web/fleet-gallery.html').read_text()
        c=Collector();c.feed(source)
        self.assertEqual(c.cards,35)
        self.assertEqual(c.images[:15],[f'/buses/{name}.png?v=4.0-alpha3' for name in NAMES])
        manifest=json.loads((ROOT/'web/buses/asset-map.json').read_text())['uploaded_assets']
        self.assertEqual(set(c.images[15:]),{f'/buses/{k}.png?v=4.0-alpha3' for k in manifest if k.startswith('tl_')})
        self.assertEqual(len(set(c.images)),35)
        self.assertEqual(c.details,1)
    def test_simple_dark_theme_and_placeholder(self):
        src=(ROOT/'web/fleet-gallery.html').read_text()
        self.assertIn('--bg:#202124',src)
        self.assertIn('--panel:#25272a',src)
        self.assertIn('PLACEHOLDER / N/A',src)
        self.assertNotIn('art-tag',src)
        self.assertNotIn('missing-card',src)
        self.assertIn('grid-template-columns:repeat(2,minmax(0,1fr))',src)
