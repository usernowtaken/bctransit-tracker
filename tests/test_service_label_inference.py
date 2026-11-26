import unittest
from app import infer_service_label

class ServiceInferenceTests(unittest.TestCase):
    def test_via_labels_not_generic_nis(self):
        for label in ("Bear Mountain / Via RRU", "Dockyard / Via Esquimalt", "UVic / Via McKenzie"):
            self.assertNotEqual(infer_service_label(label, None)['state'], 'likely_nis')
            self.assertNotEqual(infer_service_label(None, label)['state'], 'likely_nis')
    def test_plain_terminal_pairs_can_still_be_flagged(self):
        self.assertEqual(infer_service_label("Royal Oak Exch / Westhills Exch", None)['state'], 'likely_nis')

if __name__ == "__main__":
    unittest.main()
