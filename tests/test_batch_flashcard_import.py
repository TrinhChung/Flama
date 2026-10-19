"""Integration tests for multi-file batch import, naming detection, and content comparison."""

import io
import unittest
from app import create_app
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.flashcard import Note, NoteType, Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user



class BatchFlashcardImportTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            self.user_id = user.id

            # Create Parent Deck
            parent_deck = Deck(name="Tiếng Nhật N5", owner_user_id=self.user_id, position=0)
            db.session.add(parent_deck)
            db.session.flush()
            self.parent_deck_id = parent_deck.id

            # Create Child Decks
            child1 = Deck(name="Bài 01", parent_id=self.parent_deck_id, owner_user_id=self.user_id, position=0)
            child2 = Deck(name="Bài 02", parent_id=self.parent_deck_id, owner_user_id=self.user_id, position=1)
            db.session.add_all([child1, child2])
            db.session.flush()
            self.child1_id = child1.id
            self.child2_id = child2.id

            # Create NoteType with Word, Reading, Meaning
            note_type = NoteType(
                name="Basic Vocab",
                user_id=self.user_id,
            )
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            f1 = FieldDef(note_type_id=self.note_type_id, name="Word", required=True, field_type="text", position=0)
            f2 = FieldDef(note_type_id=self.note_type_id, name="Reading", required=False, field_type="text", position=1)
            f3 = FieldDef(note_type_id=self.note_type_id, name="Meaning", required=True, field_type="text", position=2)
            db.session.add_all([f1, f2, f3])
            db.session.flush()


            # Template
            template = attach_template(
                db.session,
                owner_user_id=self.user_id,
                note_type_id=self.note_type_id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{FrontSide}}<hr>{{Reading}}<br>{{Meaning}}",
                position=0,
            )

            # Add existing notes to child1 (Bài 01)
            n1 = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.child1_id,
                field_values={"Word": "私", "Reading": "わたし", "Meaning": "tôi"},
            )
            n2 = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.child1_id,
                field_values={"Word": "あなた", "Reading": "あなた", "Meaning": "bạn"},
            )
            db.session.add_all([n1, n2])
            db.session.commit()

        # Login
        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )


    def test_batch_parse_with_new_files_naming_increment(self):
        file1_content = "Word,Reading,Meaning\n先生,せんせい,thầy giáo\n学生,がくせい,học sinh\n"
        file2_content = "Word,Reading,Meaning\n会社員,かいしゃいん,nhân viên công ty\n銀行員,ぎんこういん,nhân viên ngân hàng\n"

        data = {
            "parent_deck_id": str(self.parent_deck_id),
            "note_type_id": self.note_type_id,
            "has_header": "1",
            "delimiter_mode": "csv",
            "naming_mode": "auto",
        }
        response = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                **data,
                "files": [
                    (io.BytesIO(file1_content.encode("utf-8")), "vocab_lesson_a.csv"),
                    (io.BytesIO(file2_content.encode("utf-8")), "vocab_lesson_b.csv"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        res = response.get_json()
        self.assertIn("token", res)
        self.assertEqual(len(res["files"]), 2)

        # Existing child decks are Bài 01, Bài 02 -> should suggest Bài 03, Bài 04
        self.assertEqual(res["files"][0]["suggested_deck_name"], "Bài 03")
        self.assertEqual(res["files"][1]["suggested_deck_name"], "Bài 04")
        self.assertFalse(res["files"][0]["collision"]["is_collision"])
        self.assertFalse(res["files"][1]["collision"]["is_collision"])

    def test_batch_parse_content_comparison_identical(self):
        # Exact same words as child1 (Bài 01)
        identical_content = "Word,Reading,Meaning\n私,わたし,tôi\nあなた,あなた,bạn\n"

        response = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": str(self.parent_deck_id),
                "note_type_id": self.note_type_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "auto",
                "files": [
                    (io.BytesIO(identical_content.encode("utf-8")), "Bài 01.csv"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        res = response.get_json()
        file_meta = res["files"][0]
        self.assertTrue(file_meta["collision"]["is_collision"])
        self.assertEqual(file_meta["collision"]["status"], "identical")
        self.assertEqual(file_meta["collision"]["suggested_action"], "skip")

    def test_batch_parse_content_comparison_different_content(self):
        # Collision with Bài 01 name, but completely different vocabulary (N3 vocab)
        different_content = "Word,Reading,Meaning\n経済,けいざい,kinh tế\n政治,せいじ,chính trị\n"

        response = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": str(self.parent_deck_id),
                "note_type_id": self.note_type_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "auto",
                "files": [
                    (io.BytesIO(different_content.encode("utf-8")), "Bài 01.csv"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        res = response.get_json()
        file_meta = res["files"][0]
        self.assertTrue(file_meta["collision"]["is_collision"])
        self.assertEqual(file_meta["collision"]["status"], "different")
        self.assertEqual(file_meta["collision"]["suggested_action"], "auto_rename")
        self.assertIn("0%", file_meta["collision"]["message"])

    def test_batch_estimate_and_execute(self):
        file1_content = "Word,Reading,Meaning\n車,くるま,xe hơi\n"
        file2_content = "Word,Reading,Meaning\n机,つくえ,cái bàn\n椅子,いす,cái ghế\n"

        parse_res = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": str(self.parent_deck_id),
                "note_type_id": self.note_type_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "auto",
                "files": [
                    (io.BytesIO(file1_content.encode("utf-8")), "lesson_03.csv"),
                    (io.BytesIO(file2_content.encode("utf-8")), "lesson_04.csv"),
                ],
            },
            content_type="multipart/form-data",
        ).get_json()

        token = parse_res["token"]

        # Estimate
        estimate_res = self.client.post(
            "/api/flashcards/import/batch/estimate",
            json={
                "token": token,
                "parent_deck_id": self.parent_deck_id,
                "note_type_id": self.note_type_id,
                "mapping": parse_res["suggested_mapping"],
                "file_configs": [
                    {"file_id": "f_0", "target_deck_name": "Bài 03", "action": "create_new"},
                    {"file_id": "f_1", "target_deck_name": "Bài 04", "action": "create_new"},
                ],
            },
        )
        self.assertEqual(estimate_res.status_code, 200, estimate_res.get_json())
        est = estimate_res.get_json()

        self.assertEqual(est["overall_summary"]["inserted"], 3)

        # Execute
        exec_res = self.client.post(
            "/api/flashcards/import/batch/execute",
            json={
                "token": token,
                "parent_deck_id": self.parent_deck_id,
                "note_type_id": self.note_type_id,
                "mapping": parse_res["suggested_mapping"],
                "file_configs": [
                    {"file_id": "f_0", "target_deck_name": "Bài 03", "action": "create_new"},
                    {"file_id": "f_1", "target_deck_name": "Bài 04", "action": "create_new"},
                ],
            },
        )
        self.assertEqual(exec_res.status_code, 200)
        ex = exec_res.get_json()
        self.assertEqual(ex["overall_summary"]["inserted"], 3)
        self.assertEqual(ex["overall_summary"]["created_decks"], 2)

        # Verify in DB that subdecks and notes are properly created
        with self.app.app_context():
            d3 = Deck.query.filter_by(parent_id=self.parent_deck_id, name="Bài 03").first()
            d4 = Deck.query.filter_by(parent_id=self.parent_deck_id, name="Bài 04").first()
            self.assertIsNotNone(d3)
            self.assertIsNotNone(d4)

            notes_d3 = Note.query.filter_by(deck_id=d3.id).all()
            notes_d4 = Note.query.filter_by(deck_id=d4.id).all()
            self.assertEqual(len(notes_d3), 1)
            self.assertEqual(len(notes_d4), 2)
            self.assertEqual(notes_d3[0].field_values["Word"], "車")

    def test_batch_estimate_edge_cases_no_parent_and_column_mismatch(self):
        # CSV with only 2 columns: Word and Meaning (NoteType has 3 fields: Word, Reading, Meaning)
        file1_content = "Word,Meaning\n猫,con mèo\n犬,con chó\n"
        file2_content = "Word,Meaning\n鳥,con chim\n"

        parse_res = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": "",  # Empty parent deck
                "note_type_id": self.note_type_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "filename",
                "files": [
                    (io.BytesIO(file1_content.encode("utf-8")), "animals_1.csv"),
                    (io.BytesIO(file2_content.encode("utf-8")), "animals_2.csv"),
                ],
            },
            content_type="multipart/form-data",
        ).get_json()

        token = parse_res["token"]
        self.assertIsNotNone(token)

        # Estimate with column mismatch, null parent_deck_id, empty uniqueness_fields
        estimate_res = self.client.post(
            "/api/flashcards/import/batch/estimate",
            json={
                "token": token,
                "parent_deck_id": None,
                "note_type_id": self.note_type_id,
                "uniqueness_fields": [],  # Empty, should fallback to default
                "mapping": {
                    "Word": {"source_type": "column", "column_index": 0, "constant_value": ""},
                    "Reading": {"source_type": "ignore", "column_index": None, "constant_value": ""},
                    "Meaning": {"source_type": "column", "column_index": 1, "constant_value": ""},
                },
                "file_configs": [
                    {"file_id": "f_0", "target_deck_name": "Động vật 1", "action": "create_new"},
                    {"file_id": "f_1", "target_deck_name": "Động vật 2", "action": "create_new"},
                ],
            },
        )
        self.assertEqual(estimate_res.status_code, 200, estimate_res.get_json())
        est = estimate_res.get_json()
        self.assertEqual(est["overall_summary"]["inserted"], 3)
        self.assertEqual(est["overall_summary"]["errors"], 0)

    def test_batch_import_with_array_field(self):
        with self.app.app_context():
            nt = NoteType(user_id=self.user_id, name="Array Import Model")
            db.session.add(nt)
            db.session.flush()
            db.session.add_all([
                FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0, required=True, identity_role="primary"),
                FieldDef(note_type_id=nt.id, name="Collocations", field_type="array", position=1, required=False),
            ])
            attach_template(
                db.session,
                note_type_id=nt.id,
                owner_user_id=self.user_id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{#Collocations}}{{.}}{{/Collocations}}",
            )
            db.session.commit()
            array_nt_id = nt.id

        csv_content = 'Word,Collocations\nTokyo,"Tokyo tower\ncentral Tokyo"\n'
        parse_res = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": str(self.parent_deck_id),
                "note_type_id": array_nt_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "auto",
                "files": [(io.BytesIO(csv_content.encode("utf-8")), "array_test.csv")],
            },
            content_type="multipart/form-data",
        ).get_json()

        token = parse_res["token"]
        mapping = {
            "Word": {"source_type": "column", "column_index": 0, "constant_value": ""},
            "Collocations": {"source_type": "column", "column_index": 1, "constant_value": ""},
        }

        # 1. Execute Insert
        exec_res = self.client.post(
            "/api/flashcards/import/batch/execute",
            json={
                "token": token,
                "parent_deck_id": self.parent_deck_id,
                "note_type_id": array_nt_id,
                "mapping": mapping,
                "file_configs": [{"file_id": "f_0", "target_deck_name": "Array Deck", "action": "create_new"}],
            },
        )
        self.assertEqual(exec_res.status_code, 200, exec_res.get_json())
        self.assertEqual(exec_res.get_json()["overall_summary"]["inserted"], 1)

        with self.app.app_context():
            imported_note = Note.query.filter_by(note_type_id=array_nt_id).first()
            self.assertIsNotNone(imported_note)
            self.assertEqual(imported_note.field_values.get("Collocations"), ["Tokyo tower", "central Tokyo"])
            target_deck_id = imported_note.deck_id

        # 2. Re-import same CSV into the existing deck -> must be detected as unchanged
        re_parse = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "parent_deck_id": str(self.parent_deck_id),
                "note_type_id": array_nt_id,
                "has_header": "1",
                "delimiter_mode": "csv",
                "naming_mode": "auto",
                "files": [(io.BytesIO(csv_content.encode("utf-8")), "array_test.csv")],
            },
            content_type="multipart/form-data",
        ).get_json()

        re_exec = self.client.post(
            "/api/flashcards/import/batch/execute",
            json={
                "token": re_parse["token"],
                "parent_deck_id": self.parent_deck_id,
                "note_type_id": array_nt_id,
                "mapping": mapping,
                "uniqueness_fields": ["Word"],
                "file_configs": [{"file_id": "f_0", "target_deck_id": target_deck_id, "action": "use_existing"}],
            },
        )
        self.assertEqual(re_exec.status_code, 200, re_exec.get_json())
        self.assertEqual(re_exec.get_json()["overall_summary"]["unchanged"], 1)
        self.assertEqual(re_exec.get_json()["overall_summary"]["updated"], 0)


if __name__ == "__main__":
    unittest.main()

