"""Direct-upload metadata and deferred commit against disposable local MySQL."""
from unittest.mock import patch
from types import SimpleNamespace

from app.services import worker_media_service, flama_media_client, flashcard_content_service
from app.validators import RequestValidationError
from models import db
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user, attach_template

STAGE = "stg_" + "a" * 32
SHA = "b" * 64


class WorkerMediaMySQLTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"FLAMA_MEDIA_DIRECT_UPLOAD_ENABLED": True, "FLAMA_MEDIA_PUBLIC_URL": "https://media.example.test",
        "MEDIA_SHARED_SECRET": "test-media-upload-key", "INTERNAL_SECURITY_SECRET": "test-media-control-key"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from app.api.v1.flashcards.media import media_bp
        cls.app.register_blueprint(media_bp, url_prefix="/api")

    def setUp(self):
        super().setUp()
        self.owner = create_note_user(db.session, username="mediaowner", email="owner@example.invalid")
        self.other = create_note_user(db.session, username="mediaother", email="other@example.invalid")
        self.nt = NoteType(user_id=self.owner.id, name="Direct media")
        db.session.add(self.nt)
        db.session.flush()
        for position, (name, kind) in enumerate((("Word", "text"), ("Image", "image"), ("Audio", "audio"),
                                                ("Content", "markdown"), ("Examples", "array"))):
            db.session.add(FieldDef(note_type_id=self.nt.id, name=name, field_type=kind, position=position))
        attach_template(db.session, note_type_id=self.nt.id, owner_user_id=self.owner.id,
            name="Media card", front_html="{{Word}}", back_html="{{Image}}")
        self.note = Note(user_id=self.owner.id, note_type_id=self.nt.id,
            field_values={"Word": "猫", "Image": "", "Audio": "", "Content": "", "Examples": []})
        db.session.add(self.note)
        db.session.commit()
        self.calls = []

    def control(self, path, payload):
        self.calls.append((path, payload))
        if path == "/media/staged/inspect":
            return {"items": [{"stage_id": stage, "sha256": SHA, "content_type": "image/png", "size_bytes": 123,
                "relative_path": f"bb/bb/{SHA}.png", "filename": "cat.png"} for stage in payload["stage_ids"]]}
        if path == "/media/commit":
            return {"items": payload["items"]}
        self.fail(f"Unexpected worker call {path}")

    def login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
            session["_fresh"] = True

    def test_ticket_returns_only_direct_worker_capabilities_without_binary_request(self):
        self.login()
        with patch.object(flama_media_client, "internal_request") as network:
            response = self.client.post("/api/media/upload-ticket", json={"note_id": self.note.id, "field_name": "Image"})
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertEqual(data["upload_url"], "https://media.example.test/media/upload")
        self.assertEqual(data["staging_ttl_seconds"], 86400)
        network.assert_not_called()
        self.assertEqual(MediaAsset.query.count(), 0)

    def test_ticket_rejects_other_users_note(self):
        with self.assertRaises(RequestValidationError) as raised:
            worker_media_service.upload_ticket(user_id=self.other.id, payload={"note_id": self.note.id})
        self.assertEqual(raised.exception.status, 404)

    def test_save_attaches_verified_stage_and_preserves_uuid_media_identity(self):
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            result = worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                field_values={"Image": f"https://media.example.test/media/staged/{STAGE}", "Word": "猫"})
        asset = MediaAsset.query.one()
        self.assertEqual(len(asset.id), 36)
        self.assertEqual(asset.storage_path, f"worker:bb/bb/{SHA}.png")
        self.assertEqual(result, {"Image": f"/store/{asset.id}", "Word": "猫"})
        self.assertEqual(self.calls[-1], ("/media/commit", {"user_id": self.owner.id,
            "items": [{"stage_id": STAGE, "asset_id": asset.id}]}))

    def test_nested_array_and_markdown_remain_lists_and_markup(self):
        values = {"Examples": ["first", [f'<img src="/media/staged/{STAGE}">']],
                  "Content": f"![cat](/media/staged/{STAGE})"}
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            result = worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id, field_values=values)
        self.assertIsInstance(result["Examples"], list)
        self.assertIsInstance(result["Examples"][1], list)
        self.assertEqual(MediaAsset.query.count(), 2)
        self.assertNotIn("/media/staged/", str(result))
        self.assertTrue(result["Content"].startswith("![cat](/store/"))

    def test_wrong_kind_never_sends_commit(self):
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            with self.assertRaises(RequestValidationError):
                worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                    field_values={"Audio": f"/media/staged/{STAGE}"})
        self.assertEqual([call[0] for call in self.calls], ["/media/staged/inspect"])
        self.assertEqual(MediaAsset.query.count(), 0)

    def test_spoofed_origin_never_reaches_worker(self):
        with patch.object(flama_media_client, "internal_request") as network:
            with self.assertRaises(RequestValidationError):
                worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                    field_values={"Image": f"https://untrusted.example.test/media/staged/{STAGE}"})
        network.assert_not_called()

    def test_worker_failure_rolls_back_note_save_and_asset_row(self):
        note_id = self.note.id
        def fail_commit(path, payload):
            if path == "/media/commit":
                raise flama_media_client.FlamaMediaClientError("worker offline", 503)
            return self.control(path, payload)
        with patch.object(flama_media_client, "internal_request", side_effect=fail_commit):
            with self.assertRaises(flashcard_content_service.ContentApiError) as raised:
                flashcard_content_service.update_note(user_id=self.owner.id, note_id=note_id,
                    payload={"field_values": {"Image": f"/media/staged/{STAGE}"}})
        self.assertEqual(raised.exception.status, 503)
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(db.session.get(Note, note_id).field_values["Image"], "")

    def test_json_attach_endpoint_commits_no_file_bytes(self):
        self.login()
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            response = self.client.post(f"/api/notes/{self.note.id}/media", json={"field_name": "Image", "stage_id": STAGE})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(self.note.field_values["Image"], response.get_json()["url"])
        self.assertEqual(len(self.calls), 2)

    def test_no_reference_does_not_contact_worker(self):
        values = {"Word": "猫", "Examples": ["one", ["two"]]}
        with patch.object(flama_media_client, "internal_request") as network:
            self.assertEqual(worker_media_service.commit_field_values(user_id=self.owner.id,
                note_id=self.note.id, field_values=values), values)
        network.assert_not_called()

    def test_repeated_identical_upload_reuses_asset_uuid_and_quota(self):
        second = "stg_" + "c" * 32
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            first = worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                field_values={"Image": f"/media/staged/{STAGE}"})
            db.session.commit()
            with patch.object(worker_media_service.quota_service, "consume_media") as consume:
                again = worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                    field_values={"Image": f"/media/staged/{second}"})
        self.assertEqual(first, again)
        self.assertEqual(MediaAsset.query.count(), 1)
        consume.assert_not_called()
        self.assertEqual(self.calls[-1][1]["items"][0]["asset_id"], first["Image"].split("/")[-1])

    def test_worker_rejects_foreign_stage_before_note_save(self):
        note_id = self.note.id
        with patch.object(flama_media_client, "internal_request", side_effect=
            flama_media_client.FlamaMediaClientError("wrong stage owner", 403, "STAGE_FORBIDDEN")):
            with self.assertRaises(flashcard_content_service.ContentApiError) as raised:
                flashcard_content_service.update_note(user_id=self.owner.id, note_id=note_id,
                    payload={"field_values": {"Image": f"/media/staged/{STAGE}"}})
        self.assertEqual(raised.exception.status, 403)
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(db.session.get(Note, note_id).field_values["Image"], "")

    def test_batch_json_preserves_per_item_authorization_and_partial_results(self):
        self.login()
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            response = self.client.post("/api/notes/media/batch", json={"items": [
                {"item_id": "valid", "note_id": self.note.id, "field_name": "Image", "stage_id": STAGE},
                {"item_id": "missing", "note_id": "does-not-exist", "field_name": "Image", "stage_id": STAGE}]})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual((result["success_count"], result["failed_count"]), (1, 1))
        self.assertEqual(result["items"][1]["error"], "FIELD_NOT_FOUND")
        self.assertEqual(MediaAsset.query.count(), 1)

    def test_integrity_inspection_never_downloads_media_bytes(self):
        asset_id = "56945354-592b-4a4d-aa8b-847a927c7585"
        with patch.object(flama_media_client, "internal_request", return_value={"items": [
            {"asset_id": asset_id, "exists": True, "size_bytes": 123}]} ) as control:
            self.assertEqual(worker_media_service.inspect_assets([asset_id]), {asset_id: True})
        control.assert_called_once_with("/media/assets/inspect", {"asset_ids": [asset_id]})

    def test_note_creation_commits_staged_image(self):
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            result = flashcard_content_service.create_note(user_id=self.owner.id, payload={
                "note_type_id": self.nt.id, "field_values": {"Word": "犬", "Image": f"/media/staged/{STAGE}"}})
        created = db.session.get(Note, result["id"])
        self.assertTrue(created.field_values["Image"].startswith("/store/"))
        self.assertEqual(MediaAsset.query.one().note_id, created.id)

    def test_study_quick_edit_commits_staged_media_before_success(self):
        from app.services import study_card_editor_service
        card = SimpleNamespace(id="test-card", note=self.note, template=None)
        with patch.object(flama_media_client, "internal_request", side_effect=self.control), patch.object(
            study_card_editor_service.study_edit_repo, "load_owned_card_for_study_edit", return_value=card):
            result = study_card_editor_service.update_study_card_note(user_id=self.owner.id,
                card_id=card.id, payload={"field_values": {"Image": f"/media/staged/{STAGE}"}}, render_result=False)
        self.assertTrue(result["field_values"]["Image"].startswith("/store/"))
        self.assertEqual(self.calls[-1][0], "/media/commit")

    def test_owned_browse_save_commits_staged_media(self):
        from app.services import browse_card_service
        validated = SimpleNamespace(update_deck=False, update_tags=False,
            field_updates={"Image": f"/media/staged/{STAGE}"})
        with patch.object(flama_media_client, "internal_request", side_effect=self.control):
            result = browse_card_service._update_owned_browse_card(user_id=self.owner.id, admin_mode=False,
                timezone_name="UTC", card_obj=None, note_obj=self.note, validated=validated, include_response=False)
        self.assertEqual(result, {"success": True})
        self.assertTrue(self.note.field_values["Image"].startswith("/store/"))

    def test_clone_edit_never_promotes_upload_or_mutates_source_note(self):
        from app.services import browse_card_service
        validated = SimpleNamespace(field_updates={"Image": f"/media/staged/{STAGE}"})
        with patch.object(flama_media_client, "internal_request") as control:
            with self.assertRaises(browse_card_service.BrowseCardUpdateError):
                browse_card_service._update_clone_browse_card(user_id=self.other.id, timezone_name="UTC",
                    card_obj=None, note_obj=self.note, clone_scope=None, validated=validated)
        control.assert_not_called()
        self.assertEqual(self.note.field_values["Image"], "")
        self.assertEqual(MediaAsset.query.count(), 0)

    def test_malformed_stage_url_cannot_be_saved_without_promotion(self):
        with patch.object(flama_media_client, "internal_request") as control:
            with self.assertRaises(RequestValidationError):
                worker_media_service.commit_field_values(user_id=self.owner.id, note_id=self.note.id,
                    field_values={"Image": "https://media.example.test/media/staged/not-a-stage-id"})
        control.assert_not_called()
