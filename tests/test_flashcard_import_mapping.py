"""Unit tests for flashcard import suggested mapping logic."""

import unittest
from types import SimpleNamespace
from app.services.flashcard_import import suggest_mapping


class FlashcardImportMappingTests(unittest.TestCase):
    def test_suggest_mapping_by_name(self):
        fields = [
            SimpleNamespace(name="Word", position=0),
            SimpleNamespace(name="Reading", position=1),
            SimpleNamespace(name="Meaning", position=2),
        ]
        header = ["Word", "Reading", "Meaning"]
        res = suggest_mapping(
            field_defs=fields,
            has_header=True,
            header=header,
            column_count=3,
        )
        self.assertEqual(res["Word"]["column_index"], 0)
        self.assertEqual(res["Reading"]["column_index"], 1)
        self.assertEqual(res["Meaning"]["column_index"], 2)

    def test_suggest_mapping_sequential_fallback_when_names_mismatch(self):
        fields = [
            SimpleNamespace(name="Front", position=0),
            SimpleNamespace(name="Back", position=1),
        ]
        header = ["Cột 1", "Cột 2", "Cột 3"]
        res = suggest_mapping(
            field_defs=fields,
            has_header=True,
            header=header,
            column_count=3,
        )
        # Should map sequentially: Front -> 0, Back -> 1
        self.assertEqual(res["Front"]["column_index"], 0)
        self.assertEqual(res["Back"]["column_index"], 1)

    def test_suggest_mapping_without_header(self):
        fields = [
            SimpleNamespace(name="Field1", position=0),
            SimpleNamespace(name="Field2", position=1),
        ]
        res = suggest_mapping(
            field_defs=fields,
            has_header=False,
            header=[],
            column_count=2,
        )
        self.assertEqual(res["Field1"]["column_index"], 0)
        self.assertEqual(res["Field2"]["column_index"], 1)

    def test_suggest_mapping_no_duplicate_collision(self):
        fields = [
            SimpleNamespace(name="Audio", position=0),
            SimpleNamespace(name="Front", position=1),
        ]
        header = ["Front", "AudioFile"]
        res = suggest_mapping(
            field_defs=fields,
            has_header=True,
            header=header,
            column_count=2,
        )
        # Front matches column 0
        # Audio doesn't match, position 0 is taken -> falls back to unused column 1
        self.assertEqual(res["Front"]["column_index"], 0)
        self.assertEqual(res["Audio"]["column_index"], 1)

    def test_suggest_mapping_excess_fields_ignored(self):
        fields = [
            SimpleNamespace(name="F1", position=0),
            SimpleNamespace(name="F2", position=1),
            SimpleNamespace(name="F3", position=2),
        ]
        header = ["Col A"]
        res = suggest_mapping(
            field_defs=fields,
            has_header=True,
            header=header,
            column_count=1,
        )
        self.assertEqual(res["F1"]["column_index"], 0)
        self.assertEqual(res["F2"]["source_type"], "ignore")
        self.assertIsNone(res["F2"]["column_index"])
        self.assertEqual(res["F3"]["source_type"], "ignore")
        self.assertIsNone(res["F3"]["column_index"])
