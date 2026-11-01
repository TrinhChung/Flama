"""Real Flask tickets -> Go HTTP upload -> MySQL save -> permanent media read.

Opt in with FLAMA_MYSQL_TESTS=1 and FLAMA_MEDIA_TEST_BINARY pointing at a built
worker. The worker, files and database are all disposable; no production access.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
import zipfile

from PIL import Image

from app.services import flashcard_content_service, worker_media_service
from models import db
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user


class WorkerMediaEndToEndMySQLTests(NoteBaseMySQLTestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "linux":
            raise unittest.SkipTest("This contract targets the Linux worker filesystem (symlinks/flock).")
        binary = os.environ.get("FLAMA_MEDIA_TEST_BINARY", "")
        if not binary or not Path(binary).is_file():
            raise unittest.SkipTest("Build the worker and set FLAMA_MEDIA_TEST_BINARY.")
        super().setUpClass()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        cls.base = f"http://127.0.0.1:{port}"
        cls.gateway_secret = secrets.token_urlsafe(32)
        shared_secret, internal_secret = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        cls.storage_root = Path(cls.media_directory.name) / "worker"
        cls.app.config.update(
            FLAMA_MEDIA_DIRECT_UPLOAD_ENABLED=True, FLAMA_MEDIA_PUBLIC_URL=cls.base,
            FLAMA_MEDIA_WORKER_URL=cls.base, MEDIA_SHARED_SECRET=shared_secret,
            INTERNAL_SECURITY_SECRET=internal_secret,
        )
        from app.api.v1.flashcards.media import media_bp
        cls.app.register_blueprint(media_bp, url_prefix="/api")
        env = {
            **os.environ, "LISTEN_HOST": "127.0.0.1", "PORT": str(port),
            "MEDIA_STORAGE_ROOT": str(cls.storage_root),
            "MEDIA_TEMP_ROOT": str(cls.storage_root / "scratch"),
            "MEDIA_SHARED_SECRET": shared_secret, "GATEWAY_SECRET": cls.gateway_secret,
            "INTERNAL_SECURITY_SECRET": internal_secret, "SECURITY_CALLBACK_URL": "",
            "STROKE_ROLE": "disabled", "ALLOWED_ORIGINS": "https://frontend.example.test",
            "TRUSTED_PROXIES": "127.0.0.1", "MEDIA_STAGE_TTL_SECONDS": "86400",
        }
        cls.log = (Path(cls.media_directory.name) / "worker.log").open("wb")
        cls.addClassCleanup(cls.log.close)
        cls.worker = subprocess.Popen([str(Path(binary).resolve())], env=env,
            stdout=cls.log, stderr=subprocess.STDOUT)
        cls.addClassCleanup(cls._stop_worker)
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base + "/health", timeout=0.2) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            if cls.worker.poll() is not None:
                break
            time.sleep(0.05)
        raise RuntimeError("Disposable Go worker failed to start.")

    @classmethod
    def _stop_worker(cls):
        cls.worker.terminate()
        try:
            cls.worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.worker.kill()
            cls.worker.wait(timeout=5)

    def setUp(self):
        super().setUp()
        self.owner = create_note_user(db.session, username="e2emedia", email="e2e@example.invalid")
        note_type = NoteType(user_id=self.owner.id, name="Real Go media")
        db.session.add(note_type)
        db.session.flush()
        db.session.add_all([
            FieldDef(note_type_id=note_type.id, name="Image", field_type="image", position=0),
            FieldDef(note_type_id=note_type.id, name="Audio", field_type="audio", position=1),
        ])
        self.note = Note(user_id=self.owner.id, note_type_id=note_type.id,
            field_values={"Image": "", "Audio": ""})
        db.session.add(self.note)
        db.session.commit()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
            session["_fresh"] = True

    @staticmethod
    def _image():
        output = io.BytesIO()
        Image.new("RGB", (3200, 1600), "#f97316").save(output, "PNG")
        return output.getvalue()

    def _upload(self, data, filename, *, zipped=False):
        response = self.client.post("/api/media/upload-ticket", json={"note_id": self.note.id})
        self.assertEqual(response.status_code, 200, response.get_json())
        ticket = response.get_json()
        boundary = "flama-e2e-" + secrets.token_hex(16)
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"'
            '\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(ticket["upload_zip_url" if zipped else "upload_url"], data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": "Bearer " + ticket["ticket"],
                "X-Flama-Gateway-Secret": self.gateway_secret,
                "Origin": "https://frontend.example.test"})
        with urllib.request.urlopen(request, timeout=30) as uploaded:
            self.assertEqual(uploaded.headers.get("Access-Control-Allow-Origin"), "https://frontend.example.test")
            return json.load(uploaded)

    def _read_worker(self, path):
        request = urllib.request.Request(self.base + path,
            headers={"X-Flama-Gateway-Secret": self.gateway_secret})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read(), response.headers

    def test_image_is_temporary_until_note_save_then_survives_as_uuid_webp(self):
        stage = self._upload(self._image(), "camera.png")
        self.assertEqual(stage["content_type"], "image/webp")
        self.assertEqual((stage["width"], stage["height"]), (1600, 800))
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(self.note.field_values["Image"], "")
        preview, headers = self._read_worker(stage["url"])
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(Image.open(io.BytesIO(preview)).size, (1600, 800))
        flashcard_content_service.update_note(user_id=self.owner.id, note_id=self.note.id,
            payload={"field_values": {"Image": self.base + stage["url"]}})
        db.session.expire_all()
        asset = MediaAsset.query.one()
        self.assertEqual(db.session.get(Note, self.note.id).field_values["Image"], "/store/" + asset.id)
        self.assertTrue(asset.storage_path.startswith("worker:"))
        permanent, _ = self._read_worker("/store/" + asset.id)
        self.assertEqual(permanent, preview)
        self.assertTrue(worker_media_service.inspect_assets([asset.id])[asset.id])
        self.assertFalse(any((self.storage_root / "staging" / stage["stage_id"]).glob("payload.*")))

    def test_zip_extracts_to_stages_and_explicit_audio_attach_commits_only_audio(self):
        archive = io.BytesIO()
        audio = b"ID3" + bytes(40)
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("picture.png", self._image())
            output.writestr("sound.mp3", audio)
            output.writestr("../escape.png", self._image())
        result = self._upload(archive.getvalue(), "media.zip", zipped=True)
        self.assertEqual((result["accepted_count"], result["rejected_count"]), (2, 1))
        self.assertEqual(MediaAsset.query.count(), 0)
        sound = next(item for item in result["items"] if item.get("content_type") == "audio/mpeg")
        picture = next(item for item in result["items"] if item.get("content_type") == "image/webp")
        response = self.client.post(f"/api/notes/{self.note.id}/media", json={
            "field_name": "Audio", "stage_id": sound["stage_id"],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        asset = MediaAsset.query.one()
        self.assertEqual(self._read_worker("/store/" + asset.id)[0], audio)
        self.assertEqual(db.session.get(Note, self.note.id).field_values["Image"], "")
        self.assertTrue((self.storage_root / "staging" / picture["stage_id"]).is_dir())
        self.assertFalse((self.storage_root / "escape.png").exists())
