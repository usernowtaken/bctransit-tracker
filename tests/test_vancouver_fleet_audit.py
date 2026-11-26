import json, unittest
from pathlib import Path
from PIL import Image
from translink_fleet import identify, SERIES, ROSTER, BLUE_BUS_ALIASES
from fleet_identity import identify_feed_vehicle

ROOT=Path(__file__).resolve().parents[1]
class VancouverAudit(unittest.TestCase):
    def test_art_per_unit(self):
        for n,art in [(2138,'tl_e40'),(2537,'tl_e60'),(8130,'tl_de60'),(14001,'tl_xn40'),(16101,'tl_xd40'),(1201,'tl_xd40_westvan'),(16605,'tl_xd40_westvan'),(9543,'tl_lfs_gen3'),(9583,'tl_lfs_gen3'),(9605,'tl_lfs_gen2'),(9799,'tl_lfs_gen2'),(701,'tl_lfs_westvan'),(901,'tl_lfs_westvan'),(18301,'tl_lfshev'),(18451,'tl_lfssub'),(18024,'tl_xde60_rapidbus'),(19047,'tl_xde60_rapidbus'),(22005,'tl_xde60'),(22006,'tl_xde60_rapidbus'),(22015,'tl_xde60_rapidbus'),(23201,'tl_lfse'),(25527,'tl_arboc'),(24548,'tl_arboc'),(26624,'tl_girardin'),(27001,'tl_solaris12'),(28201,'tl_solaris18')]:
            with self.subTest(n=n): self.assertEqual(identify(str(n))['fleet_art_id'],art)
    def test_all_cohorts_and_assets(self):
        manifest=json.loads((ROOT/'web/buses/asset-map.json').read_text())['uploaded_assets']
        self.assertEqual(len(ROSTER),sum(b-a+1 for a,b,*_ in SERIES))
        self.assertEqual(len([k for k in manifest if k.startswith('tl_')]),20)
        for n,(key,model,year,art,note) in ROSTER.items():
            r=identify(str(n)); self.assertEqual(r['model_key'],key);self.assertEqual(r['fleet_art_id'],art)
            if art:self.assertIn(art,manifest)
        for name,entry in manifest.items():
            if not name.startswith('tl_'): continue
            with Image.open(ROOT/'web/buses'/entry['file']) as image:
                self.assertEqual(image.mode,'RGBA'); self.assertEqual(image.getpixel((0,0))[3],0);self.assertEqual(image.getchannel('A').getextrema(),(0,255))
    def test_aliases_gaps_and_historical_models(self):
        for alias,n in BLUE_BUS_ALIASES.items():self.assertEqual(identify(str(alias))['fleet_number'],str(n))
        for n in ['9582','9792','9796','7500','27002','28202','81218','80000']:
            self.assertEqual(identify(n)['model_key'],'generic')
        for n in ['19301','19304','7504','9285','8117']:
            self.assertIsNone(identify(n)['fleet_art_id']);self.assertNotEqual(identify(n)['model_key'],'generic')
        self.assertEqual(identify_feed_vehicle('victoria','3131359426',None)['fleet_number'],'9426')
        self.assertIsNone(identify(None,'3131359426')['fleet_number'])
