"""Stroke control-plane tests; bare Flask, no database or upstream network."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

from app.services.strokes import worker_client
from app.services.strokes.stroke_service import StrokeServiceError, batch_generate_strokes, resolve_stroke_items


def receipt(char="一", *, available=True, locale="ja"):
    code = format(ord(char), "x")
    return {"char": char, "hex": code, "image_key": f"stroke_{locale.replace('-', '_')}_{code}",
            "url": f"/store/stroke_{locale.replace('-', '_')}_{code}.svg", "available": available,
            **({"sha256": hashlib.sha256(char.encode()).hexdigest(), "size_bytes": 100} if available
               else {"error": "STROKE_SOURCE_UNAVAILABLE"})}


class StrokeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(FLAMA_STROKE_WORKER_ENABLED=True,
                               FLAMA_MEDIA_WORKER_URL="http://wg-worker:4792",
                               INTERNAL_SECURITY_SECRET="test-internal-control-secret")
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

    def _response(self, items):
        response = MagicMock()
        response.read.return_value = json.dumps({"items": items}).encode()
        response.__enter__.return_value = response
        return response

    @patch("app.services.strokes.worker_client._open_internal")
    def test_control_request_has_no_svg_bytes_and_checks_receipt(self, request):
        request.return_value = self._response([receipt()])
        result = worker_client.generate_strokes(["一", "一"], "ja")
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, "http://wg-worker:4792/internal/strokes/generate")
        self.assertEqual(sent.get_header("X-internal-secret"), "test-internal-control-secret")
        self.assertEqual(json.loads(sent.data), {"characters": ["一"], "locale": "ja"})
        self.assertTrue(result["一"]["available"])

    @patch("app.services.strokes.worker_client._open_internal")
    def test_wrong_character_receipt_rejected(self, request):
        request.return_value = self._response([receipt("二")])
        with self.assertRaises(worker_client.StrokeWorkerError):
            worker_client.generate_strokes(["一"], "ja")

    @patch("app.services.strokes.worker_client._open_internal")
    def test_false_receipt_not_emitted_as_available_url(self, request):
        request.return_value = self._response([receipt(), receipt("二", available=False)])
        result = resolve_stroke_items("一二", output_format="raw")
        self.assertEqual(result["output"], "/store/stroke_ja_4e00.svg")
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["missing_characters"], ["二"])
        self.assertFalse(result["items"][1]["available"])

    @patch("app.services.strokes.worker_client._open_internal")
    def test_worker_cannot_inject_url_into_rendered_html(self, request):
        item = receipt()
        item["url"] = 'javascript:alert(1)'
        request.return_value = self._response([item])
        result = resolve_stroke_items("一", output_format="html")
        self.assertIn('/store/stroke_ja_4e00.svg', result["output"])
        self.assertNotIn("javascript", result["output"])

    @patch("app.services.strokes.worker_client.generate_strokes")
    def test_batch_preflight_failure_does_not_mutate_notes(self, generate):
        defs = [SimpleNamespace(name="Expression", field_type="text"),
                SimpleNamespace(name="Diagram", field_type="diagram")]
        notes = [SimpleNamespace(id="note1", note_type_id="type1", note_type=SimpleNamespace(field_defs=defs),
                                 field_values={"Expression": "一", "Diagram": "old"})]
        generate.side_effect = worker_client.StrokeWorkerError("unavailable")
        with patch("app.services.strokes.stroke_service._collect_notes", return_value=notes):
            with self.assertRaises(StrokeServiceError) as error:
                batch_generate_strokes(user_id=1, admin_mode=False, source_field="Expression",
                                       target_field="Diagram", overwrite=True, note_ids=["note1"])
        self.assertEqual(error.exception.status, 502)
        self.assertEqual(notes[0].field_values["Diagram"], "old")

    @patch("app.services.strokes.worker_client.generate_strokes")
    def test_no_cjk_does_not_request_worker(self, generate):
        result = resolve_stroke_items("abcひらがな", output_format="raw")
        self.assertEqual(result["output"], "")
        generate.assert_not_called()

    @patch("app.services.strokes.worker_client.generate_strokes")
    def test_resolve_reuses_batch_receipts(self, generate):
        cache = {"一": receipt()}
        result = resolve_stroke_items("一一", deduplicate=False, _worker_cache=cache)
        self.assertEqual(len(result["items"]), 2)
        generate.assert_not_called()

    @patch("app.services.strokes.worker_client._open_internal")
    def test_legacy_rollout_disabled_does_not_contact_worker(self, request):
        self.app.config["FLAMA_STROKE_WORKER_ENABLED"] = False
        result = resolve_stroke_items("一")
        self.assertTrue(result["items"][0]["available"])
        request.assert_not_called()

    @patch("app.services.strokes.worker_client.generate_strokes")
    def test_production_seeder_only_updates_metadata_and_preserves_force(self, generate):
        from app.services.strokes import production_seeder

        generate.return_value = {"一": receipt()}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.object(production_seeder, "_get_upload_root", return_value=root),
                  patch.object(production_seeder, "_get_static_root", return_value=root),
                  patch.object(production_seeder, "get_production_kanji_list", return_value=["一"]),
                  patch.object(production_seeder, "_sync_db_batch") as sync):
                result = production_seeder.seed_production_strokes_dataset(locales=("ja",), force=True)
            self.assertEqual(list(root.iterdir()), [])
        generate.assert_called_once_with(["一"], "ja", force=True)
        self.assertEqual(sync.call_args.args[0][0]["storage_path"], "strokes/stroke_ja_4e00.svg")
        self.assertEqual(result["db_updated"], 1)


class WorksheetStrokeSourceTests(unittest.TestCase):
    SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="flama-stroke-char"><path d="M1 1"/></svg>'

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(FLAMA_STROKE_WORKER_ENABLED=True, FLAMA_MEDIA_WORKER_URL="http://wg-worker:4792",
                               GATEWAY_SECRET="test-gateway-secret")
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        worker_client._SVG_CACHE.clear()
        self.addCleanup(worker_client._SVG_CACHE.clear)

    def _svg_response(self, body: str):
        response = MagicMock()
        response.read.return_value = body.encode()
        response.__enter__.return_value = response
        return response

    @patch("app.services.worksheets.worksheet_service.fetch_authentic_stroke_svg")
    @patch("app.services.strokes.worker_client._open_internal")
    def test_worksheet_reads_strokes_from_worker_without_github_or_disk(self, request, github):
        from app.services.worksheets import worksheet_service

        request.return_value = self._svg_response(self.SVG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.object(worksheet_service, "_get_static_root", return_value=root),
                  patch.object(worksheet_service, "_get_upload_root", return_value=root)):
                first = worksheet_service._get_stroke_svg_content("zh-hant", "6c34", char="水")
                second = worksheet_service._get_stroke_svg_content("zh-hant", "6c34", char="水")
            self.assertEqual(list(root.iterdir()), [])
        self.assertEqual((first, second), (self.SVG, self.SVG))
        github.assert_not_called()
        request.assert_called_once()  # the second read comes from the in-process cache
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, "http://wg-worker:4792/store/stroke_zh_hant_6c34.svg")
        self.assertEqual(sent.get_header("X-flama-gateway-secret"), "test-gateway-secret")

    @patch("app.services.strokes.worker_client._open_internal")
    def test_worker_failure_returns_none_and_is_not_cached(self, request):
        request.side_effect = OSError("down")
        self.assertIsNone(worker_client.fetch_stroke_svg("水", "ja"))
        request.side_effect = None
        request.return_value = self._svg_response(self.SVG)
        self.assertEqual(worker_client.fetch_stroke_svg("水", "ja"), self.SVG)


if __name__ == "__main__":
    unittest.main()
