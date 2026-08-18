"""Unit tests for deck naming analysis and next lesson naming generation."""

import unittest
from app.services import deck_naming_service


class DummyDeck:
    def __init__(self, id: int, name: str, parent_id: int | None = None):
        self.id = id
        self.name = name
        self.parent_id = parent_id


class DeckNamingServiceTests(unittest.TestCase):
    def test_natural_sort_key(self):
        files = ["bai_10.csv", "bai_1.csv", "bai_2.csv", "bai_20.csv", "bai_3.csv"]
        sorted_files = sorted(files, key=deck_naming_service.natural_sort_key)
        self.assertEqual(
            sorted_files,
            ["bai_1.csv", "bai_2.csv", "bai_3.csv", "bai_10.csv", "bai_20.csv"],
        )

    def test_sanitize_filename(self):
        self.assertEqual(
            deck_naming_service.sanitize_filename_to_deck_name("bai_01_tu_vung.csv"),
            "bai 01 tu vung",
        )
        self.assertEqual(
            deck_naming_service.sanitize_filename_to_deck_name("Lesson-05--Grammar.tsv"),
            "Lesson 05 Grammar",
        )

    def test_parse_deck_name_patterns(self):
        # Vietnamese
        p1 = deck_naming_service.parse_deck_name_pattern("Bài 01")
        self.assertIsNotNone(p1)
        self.assertEqual(p1["prefix"], "Bài ")
        self.assertEqual(p1["number"], 1)
        self.assertEqual(p1["zero_pad"], 2)

        p2 = deck_naming_service.parse_deck_name_pattern("Bài 10 - Từ vựng")
        self.assertIsNotNone(p2)
        self.assertEqual(p2["prefix"], "Bài ")
        self.assertEqual(p2["number"], 10)
        self.assertEqual(p2["suffix"], " - Từ vựng")

        # English
        p3 = deck_naming_service.parse_deck_name_pattern("Lesson 05")
        self.assertIsNotNone(p3)
        self.assertEqual(p3["prefix"], "Lesson ")
        self.assertEqual(p3["number"], 5)
        self.assertEqual(p3["zero_pad"], 2)

        # Japanese
        p4 = deck_naming_service.parse_deck_name_pattern("第3課")
        self.assertIsNotNone(p4)
        self.assertEqual(p4["prefix"], "第")
        self.assertEqual(p4["number"], 3)
        self.assertEqual(p4["suffix"], "課")

    def test_analyze_existing_child_decks_with_vietnamese_pattern(self):
        existing = [
            DummyDeck(1, "Bài 01"),
            DummyDeck(2, "Bài 02"),
            DummyDeck(3, "Bài 03"),
        ]
        analysis = deck_naming_service.analyze_existing_child_decks(existing)
        self.assertTrue(analysis["has_pattern"])
        self.assertEqual(analysis["dominant_prefix"], "Bài ")
        self.assertEqual(analysis["max_number"], 3)
        self.assertEqual(analysis["zero_pad"], 2)

    def test_generate_suggested_deck_names_incrementing(self):
        existing = [
            DummyDeck(1, "Bài 01"),
            DummyDeck(2, "Bài 02"),
        ]
        filenames = ["data_a.csv", "data_b.csv"]
        suggestions = deck_naming_service.generate_suggested_deck_names(
            child_decks=existing,
            filenames=filenames,
        )
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0]["suggested_deck_name"], "Bài 03")
        self.assertEqual(suggestions[1]["suggested_deck_name"], "Bài 04")
        self.assertFalse(suggestions[0]["is_existing_collision"])

    def test_generate_suggested_deck_names_with_filename_number(self):
        existing = [
            DummyDeck(1, "Lesson 01"),
            DummyDeck(2, "Lesson 02"),
        ]
        filenames = ["lesson_03.csv", "lesson_04.csv"]
        suggestions = deck_naming_service.generate_suggested_deck_names(
            child_decks=existing,
            filenames=filenames,
        )
        self.assertEqual(suggestions[0]["suggested_deck_name"], "Lesson 03")
        self.assertEqual(suggestions[1]["suggested_deck_name"], "Lesson 04")

    def test_collision_detection(self):
        existing = [
            DummyDeck(1, "Bài 01"),
            DummyDeck(2, "Bài 02"),
        ]
        filenames = ["bai_01.csv", "bai_03.csv"]
        suggestions = deck_naming_service.generate_suggested_deck_names(
            child_decks=existing,
            filenames=filenames,
        )
        self.assertTrue(suggestions[0]["is_existing_collision"])
        self.assertIsNotNone(suggestions[0]["existing_deck"])
        self.assertFalse(suggestions[1]["is_existing_collision"])


if __name__ == "__main__":
    unittest.main()
