"""V3.4.5 fleet decoding: systematic candidate ID recognition, not guesses."""
import unittest
from fleet_identity import identify_vehicle, identify_feed_vehicle


class RegionalFleetImprovement(unittest.TestCase):
    def test_chilliwack_explicit_and_prefixed_numbers(self):
        self.assertEqual(identify_feed_vehicle('chilliwack', 'Bus #9217', None)['fleet_number'], '9217')
        self.assertEqual(identify_feed_vehicle('chilliwack', '', '3131359217')['fleet_number'], '9217')
        self.assertEqual(identify_vehicle('chilliwack', '3131369222')['fleet_number'], '9222')
        self.assertIn('Vicinity 35′', identify_vehicle('chilliwack', '3131354401')['model'])
        self.assertEqual(identify_vehicle('chilliwack', '3131354401')['model_key'], 'vicinity35')
        self.assertEqual(identify_vehicle('chilliwack', '4065')['model_key'], 'vicinity30')

    def test_kelowna_patterns_and_early_nova(self):
        self.assertEqual(identify_feed_vehicle('kelowna', '', '3131356017')['fleet_number'], '6017')
        self.assertEqual(identify_vehicle('kelowna', '3131386005')['model_key'], 'nova3')
        self.assertEqual(identify_feed_vehicle('kelowna', '9233', '3131356024')['fleet_number'], '9233')
        self.assertEqual(identify_vehicle('kelowna', '9205')['nova_generation'], 2)

    def test_victoria_not_broadened(self):
        self.assertIsNone(identify_vehicle('victoria', '3131389217')['fleet_number'])
        self.assertEqual(identify_feed_vehicle('victoria', '', '3131351248')['fleet_number'], '1248')

    def test_unsafe_or_unrecognized_sources_are_not_fleet_numbers(self):
        for system in ('kelowna', 'chilliwack'):
            for raw in ('some9217','9876549217','3131999999','trip-3131359217','313135-9217','no id'):
                self.assertIsNone(identify_feed_vehicle(system, raw, raw)['fleet_number'], (system, raw))
            self.assertIsNone(identify_feed_vehicle(system, None, None)['fleet_number'])
        self.assertIsNone(identify_feed_vehicle('kelowna', '', '3131354401')['fleet_number'])

    def test_id_and_label_priority_and_candidate_status(self):
        row = identify_feed_vehicle('chilliwack', '9217', '3131359206')
        self.assertEqual(row['fleet_number'], '9217')
        self.assertEqual(row['fleet_status'], 'candidate')
        self.assertIn('not independently verified', row['fleet_basis'])
        row = identify_feed_vehicle('chilliwack', None, '3131359206')
        self.assertEqual(row['fleet_number'], '9206')
        self.assertIn('descriptor/entity ID', row['fleet_basis'])


if __name__ == '__main__': unittest.main()
