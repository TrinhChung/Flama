import unittest

from app.repositories.stats_query_repository import fixed_utc_offset_minutes


class FixedOffsetTimezoneTests(unittest.TestCase):
    """Which zones may group local days with SQL arithmetic."""

    def test_former_fixed_offset_table_keeps_its_offsets(self):
        expected = {
            "UTC": 0, "Etc/UTC": 0, "GMT": 0, "Asia/Ho_Chi_Minh": 420, "Asia/Bangkok": 420,
            "Asia/Jakarta": 420, "Asia/Tokyo": 540, "Asia/Seoul": 540, "Asia/Shanghai": 480,
            "Asia/Hong_Kong": 480, "Asia/Singapore": 480, "Asia/Taipei": 480,
        }
        self.assertEqual({name: fixed_utc_offset_minutes(name) for name in expected}, expected)

    def test_aliases_fractional_and_negative_constant_offsets_qualify(self):
        self.assertEqual(fixed_utc_offset_minutes("Asia/Saigon"), 420)
        self.assertEqual(fixed_utc_offset_minutes("Asia/Kolkata"), 330)
        self.assertEqual(fixed_utc_offset_minutes("Asia/Kathmandu"), 345)
        self.assertEqual(fixed_utc_offset_minutes("America/Phoenix"), -420)

    def test_names_match_case_insensitively(self):
        self.assertEqual(fixed_utc_offset_minutes("ASIA/TOKYO"), 540)
        self.assertEqual(fixed_utc_offset_minutes(" asia/saigon "), 420)

    def test_zones_whose_offset_changes_take_the_python_path(self):
        for name in ("America/New_York", "Europe/Berlin", "Australia/Sydney",
                     "Australia/Lord_Howe",  # 30-minute DST
                     "Africa/Casablanca"):  # offset suspended for Ramadan
            with self.subTest(name=name):
                self.assertIsNone(fixed_utc_offset_minutes(name))

    def test_unknown_or_empty_names_take_the_python_path(self):
        for name in ("", None, "Not/AZone", "../etc/passwd"):
            with self.subTest(name=name):
                self.assertIsNone(fixed_utc_offset_minutes(name))


if __name__ == "__main__":
    unittest.main()
