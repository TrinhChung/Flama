"""Empirical adversarial test suite for Flama Connect HTTP wire contracts,

preflight OPTIONS, and header security on /v1/anki-connect.
"""

from datetime import datetime, timedelta
import json
import unittest

from tests import test_flama_connect as legacy_fixture
from app.services import user_api_token_service as tokens
from app.services.connect.mining_setup import prepare_sentence_mining
from models import db


class FlamaConnectWireAdversarialTests(unittest.TestCase):
    setUpClass = classmethod(legacy_fixture.FlamaConnectTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy_fixture.FlamaConnectTests.tearDownClass.__func__)
    tearDown = legacy_fixture.FlamaConnectTests.tearDown

    def setUp(self):
        legacy_fixture.FlamaConnectTests.setUp(self)
        self.app.config.update(
            CONNECT_ANKI_ADAPTER_ENABLED=True,
            CONNECT_ANKI_MEDIA_ENABLED=True,
            CONNECT_VERSIONED_PROTOCOL_ENABLED=False,
            CONNECT_RATE_LIMIT_BACKEND="local",
            CONNECT_ANKI_ALLOWED_ORIGINS=("https://killergerbah.github.io",),
            CONNECT_ANKI_STORAGE_MAX_BYTES=512 * 1024 * 1024,
            CONNECT_ANKI_MEDIA_MAX_BYTES=2 * 1024 * 1024,
            CONNECT_ANKI_MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        )
        with self.app.app_context():
            prepare_sentence_mining(self.user_id)
            issued = tokens.issue_token(user_id=self.user_id, name="asbplayer", preset="mining-media")
            self.mining_key = issued.plaintext
            db.session.commit()

        self.valid_extension_origins = [
            "chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe",  # Yomitan Chrome
            "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab",  # asbplayer Chrome
            "chrome-extension://abcdefghijklmnopabcdefghijklmnop",  # arbitrary 32-char extension
            "moz-extension://d3b07384-d113-4684-9351-cc80e4b8e23f",  # Yomitan Firefox UUID
            "moz-extension://00000000-0000-0000-0000-000000000000",  # Firefox UUID pattern
        ]

        self.untrusted_web_origins = [
            "https://evil.com",
            "http://evil.com",
            "https://malicious.org",
            "http://malicious.org:8080",
            "http://localhost:3000",
            "http://127.0.0.1:8080",
            "https://killergerbah.github.io.attacker.com",
            "http://killergerbah.github.io",  # scheme downgrade http vs https
            "https://subdomain.killergerbah.github.io",  # arbitrary subdomain
            "https://killergerbah.github.io/path",  # origin with path
            "javascript:alert(1)",
            "file://",
        ]

    def _post(self, payload=None, *, headers=None, content_type="application/json"):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
        return self.client.post(
            "/v1/anki-connect",
            data=data,
            headers=headers or {},
            content_type=content_type,
        )

    def _options(self, *, headers=None):
        return self.client.options("/v1/anki-connect", headers=headers or {})

    # =========================================================================
    # SECTION 1: Preflight OPTIONS Under Adversarial Conditions
    # =========================================================================

    def test_options_without_credentials_valid_extensions_succeed(self):
        """Preflight OPTIONS from valid extension schemes without credentials

        must return HTTP 204 No Content with full CORS headers.
        """
        for origin in self.valid_extension_origins:
            with self.subTest(origin=origin):
                res = self._options(
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type, Authorization, X-Flama-Connect-Key",
                    }
                )
                self.assertEqual(res.status_code, 204)
                self.assertEqual(res.get_data(), b"")
                self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), origin)
                self.assertIn("Origin", res.headers.get("Vary", ""))
                self.assertIn("POST", res.headers.get("Access-Control-Allow-Methods", ""))
                self.assertIn("OPTIONS", res.headers.get("Access-Control-Allow-Methods", ""))
                self.assertIn("Content-Type", res.headers.get("Access-Control-Allow-Headers", ""))
                self.assertIn("X-Flama-Connect-Key", res.headers.get("Access-Control-Allow-Headers", ""))
                self.assertEqual(res.headers.get("Access-Control-Max-Age"), "600")
                self.assertEqual(res.headers.get("Cache-Control"), "no-store")
                self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")

    def test_options_without_credentials_untrusted_origins_forbidden_no_cors(self):
        """Preflight OPTIONS from untrusted web origins without credentials

        must return HTTP 403 Forbidden with NO CORS headers.
        """
        for origin in self.untrusted_web_origins:
            with self.subTest(origin=origin):
                res = self._options(
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                    }
                )
                self.assertEqual(res.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res.headers)
                self.assertNotIn("Access-Control-Allow-Methods", res.headers)
                self.assertEqual(res.headers.get("Cache-Control"), "no-store")

    def test_options_with_unsupported_request_methods(self):
        """OPTIONS preflight probing unsupported methods in Access-Control-Request-Method:

        Preflight reflects server's supported methods (GET, POST, PUT, DELETE, OPTIONS).
        """
        for probe_method in ["DELETE", "PUT", "TRACE", "PATCH", "CONNECT", "CUSTOM"]:
            with self.subTest(probe_method=probe_method):
                res = self._options(
                    headers={
                        "Origin": "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab",
                        "Access-Control-Request-Method": probe_method,
                    }
                )
                self.assertEqual(res.status_code, 204)
                self.assertEqual(
                    res.headers.get("Access-Control-Allow-Origin"),
                    "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab",
                )
                allowed_methods = res.headers.get("Access-Control-Allow-Methods", "")
                self.assertIn("POST", allowed_methods)
                self.assertIn("OPTIONS", allowed_methods)

    def test_options_with_null_and_missing_origin(self):
        """OPTIONS without Origin or with Origin: null returns 204 but NO Access-Control-Allow-Origin."""
        # 1. Origin: null
        res_null = self._options(headers={"Origin": "null"})
        self.assertEqual(res_null.status_code, 204)
        self.assertNotIn("Access-Control-Allow-Origin", res_null.headers)

        # 2. Absent Origin
        res_none = self._options(headers={})
        self.assertEqual(res_none.status_code, 204)
        self.assertNotIn("Access-Control-Allow-Origin", res_none.headers)

    # =========================================================================
    # SECTION 2: HTTP Method Probing on /v1/anki-connect
    # =========================================================================

    def test_method_probing_non_post_methods_rejected(self):
        """Probe GET, HEAD, PUT, DELETE, PATCH, TRACE on /v1/anki-connect."""
        methods = {
            "get": self.client.get,
            "put": self.client.put,
            "delete": self.client.delete,
            "patch": self.client.patch,
        }

        origin_ext = "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab"
        origin_evil = "https://evil.com"

        for method_name, client_fn in methods.items():
            with self.subTest(method=method_name):
                # When probed from untrusted origin -> 405 Method Not Allowed, NO CORS
                res_evil = client_fn("/v1/anki-connect", headers={"Origin": origin_evil})
                self.assertEqual(res_evil.status_code, 405)
                self.assertNotIn("Access-Control-Allow-Origin", res_evil.headers)

                # When probed from valid extension -> 405 Method Not Allowed with CORS headers
                # (so extension code can see the 405 status code)
                res_ext = client_fn("/v1/anki-connect", headers={"Origin": origin_ext})
                self.assertEqual(res_ext.status_code, 405)
                self.assertEqual(res_ext.headers.get("Access-Control-Allow-Origin"), origin_ext)

                # When probed with no origin -> 405 Method Not Allowed, no CORS
                res_no_origin = client_fn("/v1/anki-connect", headers={})
                self.assertEqual(res_no_origin.status_code, 405)
                self.assertNotIn("Access-Control-Allow-Origin", res_no_origin.headers)

    # =========================================================================
    # SECTION 3: Content-Type & Charset Probing
    # =========================================================================

    def test_content_type_probing_matrix(self):
        """Content-Type probing on /v1/anki-connect:

        - application/json: Accepted
        - text/plain: Accepted
        - missing / empty Content-Type: Accepted
        - application/x-www-form-urlencoded: Rejected with protocol error
        - multipart/form-data: Rejected with protocol error
        - text/html: Rejected with protocol error
        """
        payload = {"action": "version", "version": 6, "key": self.mining_key}
        raw_body = json.dumps(payload).encode("utf-8")

        # 1. application/json
        res_json = self.client.post("/v1/anki-connect", data=raw_body, content_type="application/json")
        self.assertEqual(res_json.status_code, 200)
        self.assertEqual(res_json.get_json(), {"result": 6, "error": None})

        # 2. text/plain
        res_plain = self.client.post("/v1/anki-connect", data=raw_body, content_type="text/plain")
        self.assertEqual(res_plain.status_code, 200)
        self.assertEqual(res_plain.get_json(), {"result": 6, "error": None})

        # 3. Missing / empty Content-Type
        res_empty = self.client.post("/v1/anki-connect", data=raw_body, content_type=None)
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.get_json(), {"result": 6, "error": None})

        # 4. application/x-www-form-urlencoded
        res_form = self.client.post(
            "/v1/anki-connect",
            data=b"action=version&version=6",
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(res_form.status_code, 200)
        self.assertIn("unsupported Content-Type", res_form.get_json().get("error", ""))

        # 5. multipart/form-data
        res_multi = self.client.post(
            "/v1/anki-connect",
            data=b"--boundary\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\nversion\r\n--boundary--",
            content_type="multipart/form-data; boundary=boundary",
        )
        self.assertEqual(res_multi.status_code, 200)
        self.assertIn("unsupported Content-Type", res_multi.get_json().get("error", ""))

        # 6. text/html
        res_html = self.client.post(
            "/v1/anki-connect",
            data=b"<html>version</html>",
            content_type="text/html",
        )
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("unsupported Content-Type", res_html.get_json().get("error", ""))

    def test_charset_probing_matrix(self):
        """Charset validation on /v1/anki-connect:

        - utf-8, UTF-8, utf8: Accepted
        - latin1, iso-8859-1, shift-jis, windows-1252: Rejected with 'request charset must be UTF-8'
        """
        payload = {"action": "version", "version": 6, "key": self.mining_key}
        raw_body = json.dumps(payload).encode("utf-8")

        # Valid charsets
        for ct in [
            "text/plain; charset=UTF-8",
            "text/plain; charset=utf-8",
            "application/json; charset=utf-8",
            "application/json; charset=UTF8",
        ]:
            with self.subTest(content_type=ct):
                res = self.client.post("/v1/anki-connect", data=raw_body, content_type=ct)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.get_json(), {"result": 6, "error": None})

        # Invalid charsets
        for ct in [
            "text/plain; charset=latin1",
            "text/plain; charset=iso-8859-1",
            "text/plain; charset=shift-jis",
            "application/json; charset=windows-1252",
        ]:
            with self.subTest(content_type=ct):
                res = self.client.post("/v1/anki-connect", data=raw_body, content_type=ct)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.get_json().get("error"), "request charset must be UTF-8")

    # =========================================================================
    # SECTION 4: Credentials + Origin Interaction (Origin Precedence Security)
    # =========================================================================

    def test_origin_precedence_over_valid_api_key(self):
        """CRITICAL SECURITY GUARANTEE:

        Even with a 100% valid, highly-privileged API key, an untrusted web origin
        MUST be immediately blocked with HTTP 403 Forbidden and NO CORS headers.
        The web attacker cannot make requests using a stolen/tricked key.
        """
        payload = {"action": "version", "version": 6, "key": self.mining_key}

        for origin in self.untrusted_web_origins:
            with self.subTest(origin=origin):
                # 1. Valid key in body
                res_body_key = self._post(payload, headers={"Origin": origin})
                self.assertEqual(res_body_key.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res_body_key.headers)
                self.assertEqual(res_body_key.get_json().get("error"), "origin is not allowed")

                # 2. Valid key in Authorization: Bearer header
                res_auth_header = self._post(
                    {"action": "version", "version": 6},
                    headers={"Origin": origin, "Authorization": f"Bearer {self.mining_key}"},
                )
                self.assertEqual(res_auth_header.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res_auth_header.headers)
                self.assertEqual(res_auth_header.get_json().get("error"), "origin is not allowed")

                # 3. Valid key in X-Flama-Connect-Key header
                res_custom_header = self._post(
                    {"action": "version", "version": 6},
                    headers={"Origin": origin, "X-Flama-Connect-Key": self.mining_key},
                )
                self.assertEqual(res_custom_header.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res_custom_header.headers)
                self.assertEqual(res_custom_header.get_json().get("error"), "origin is not allowed")

    def test_origin_precedence_over_missing_or_invalid_api_key(self):
        """Untrusted web origins with missing or invalid keys return 403 (Origin precedence)."""
        for origin in self.untrusted_web_origins:
            with self.subTest(origin=origin):
                # Missing key + untrusted origin -> 403 with NO CORS
                res_missing = self._post(
                    {"action": "version", "version": 6},
                    headers={"Origin": origin},
                )
                self.assertEqual(res_missing.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res_missing.headers)

                # Invalid key + untrusted origin -> 403 with NO CORS
                res_invalid = self._post(
                    {"action": "version", "version": 6, "key": "nonexistent_fake_key"},
                    headers={"Origin": origin},
                )
                self.assertEqual(res_invalid.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res_invalid.headers)

    def test_extension_origin_with_valid_key_succeeds(self):
        """Valid extension origin + valid key -> 200 OK with CORS headers."""
        ext_origin = "chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe"
        res = self._post(
            {"action": "version", "version": 6, "key": self.mining_key},
            headers={"Origin": ext_origin},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertIn("Origin", res.headers.get("Vary", ""))
        self.assertEqual(res.get_json(), {"result": 6, "error": None})

    def test_extension_origin_with_invalid_key_returns_401_with_cors(self):
        """Valid extension origin + invalid key -> 401 Unauthorized WITH CORS headers.

        This ensures browser extensions can read the 401 status to prompt user for re-authentication.
        """
        ext_origin = "chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe"
        res = self._post(
            {"action": "version", "version": 6, "key": "wrong_api_key"},
            headers={"Origin": ext_origin},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertIn("Origin", res.headers.get("Vary", ""))
        self.assertEqual(res.get_json().get("error"), "valid API key must be provided")

    def test_extension_origin_with_missing_key_returns_401_with_cors(self):
        """Valid extension origin + missing key -> 401 Unauthorized WITH CORS headers."""
        ext_origin = "chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe"
        res = self._post(
            {"action": "version", "version": 6},
            headers={"Origin": ext_origin},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertIn("Origin", res.headers.get("Vary", ""))
        self.assertEqual(res.get_json().get("error"), "valid API key must be provided")

    def test_extension_origin_with_revoked_key_returns_401_with_cors(self):
        """Valid extension origin + revoked key -> 401 with 'revoked key' AND CORS headers."""
        with self.app.app_context():
            token_obj = tokens.issue_token(user_id=self.user_id, name="to-revoke", preset="mining-media")
            revoked_key = token_obj.plaintext
            tokens.revoke_token(user_id=self.user_id, token_id=token_obj.record.id)
            db.session.commit()

        ext_origin = "moz-extension://d3b07384-d113-4684-9351-cc80e4b8e23f"
        res = self._post(
            {"action": "version", "version": 6, "key": revoked_key},
            headers={"Origin": ext_origin},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertEqual(res.get_json().get("error"), "revoked key")

    def test_extension_origin_with_conflicting_keys_returns_401_with_cors(self):
        """Conflicting credentials (e.g. Bearer != body key) -> 401 WITH CORS headers for extension."""
        with self.app.app_context():
            other_token = tokens.issue_token(user_id=self.user_id, name="other", preset="mining-media")
            other_key = other_token.plaintext
            db.session.commit()

        ext_origin = "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab"
        res = self._post(
            {"action": "version", "version": 6, "key": self.mining_key},
            headers={"Origin": ext_origin, "Authorization": f"Bearer {other_key}"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertEqual(res.get_json().get("error"), "valid API key must be provided")

    # =========================================================================
    # SECTION 5: Security Headers & Body Robustness
    # =========================================================================

    def test_security_headers_always_present(self):
        """Verify baseline security headers across diverse HTTP status codes."""
        # Status 200
        res200 = self._post({"action": "version", "version": 6, "key": self.mining_key})
        self.assertEqual(res200.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res200.headers.get("Cache-Control"), "no-store")
        self.assertIn("default-src 'none'", res200.headers.get("Content-Security-Policy", ""))
        self.assertEqual(res200.headers.get("Referrer-Policy"), "no-referrer")

        # Status 401
        res401 = self._post({"action": "version", "version": 6})
        self.assertEqual(res401.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res401.headers.get("Cache-Control"), "no-store")

        # Status 403
        res403 = self._post(
            {"action": "version", "version": 6, "key": self.mining_key},
            headers={"Origin": "https://evil.com"},
        )
        self.assertEqual(res403.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res403.headers.get("Cache-Control"), "no-store")

        # Status 405
        res405 = self.client.get("/v1/anki-connect")
        self.assertEqual(res405.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res405.headers.get("Cache-Control"), "no-store")

    def test_content_encoding_compression_rejection(self):
        """Compressed request bodies (gzip, deflate, br) are strictly rejected."""
        for enc in ["gzip", "deflate", "br"]:
            with self.subTest(encoding=enc):
                res = self.client.post(
                    "/v1/anki-connect",
                    data=b"dummy",
                    headers={"Content-Encoding": enc, "Origin": "chrome-extension://dummy"},
                    content_type="application/json",
                )
                self.assertEqual(res.status_code, 200)
                self.assertEqual(
                    res.get_json().get("error"),
                    "compressed request bodies are not supported",
                )

    def test_malformed_json_and_adversarial_payloads(self):
        """Verify server handles malformed JSON and adversarial structures safely."""
        # 1. Truncated JSON
        res_trunc = self.client.post(
            "/v1/anki-connect",
            data=b'{"action": "ver',
            content_type="application/json",
        )
        self.assertEqual(res_trunc.status_code, 200)
        self.assertEqual(res_trunc.get_json().get("error"), "request body is not valid JSON")

        # 2. Duplicate JSON properties
        res_dup = self.client.post(
            "/v1/anki-connect",
            data=b'{"action": "version", "action": "addNote"}',
            content_type="application/json",
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertEqual(res_dup.get_json().get("error"), "duplicate JSON property")

        # 3. NaN / Infinity injection
        res_nan = self.client.post(
            "/v1/anki-connect",
            data=b'{"action": "version", "params": {"value": NaN}}',
            content_type="application/json",
        )
        self.assertEqual(res_nan.status_code, 200)
        self.assertIn("invalid JSON number", res_nan.get_json().get("error", ""))

        # 4. Deep recursion attack (>12 nested dicts)
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": {"l": {"m": 1}}}}}}}}}}}}}
        res_deep = self.client.post(
            "/v1/anki-connect",
            data=json.dumps(deep).encode("utf-8"),
            content_type="application/json",
        )
        self.assertEqual(res_deep.status_code, 200)
        self.assertIn("JSON nesting is too deep", res_deep.get_json().get("error", ""))

    # =========================================================================
    # SECTION 6: Advanced Edge Cases, Error Responses & Boundary Stress
    # =========================================================================

    def test_allowed_web_origin_full_lifecycle(self):
        """Allowed web origin (https://killergerbah.github.io) follows same security rules

        as extensions: valid key -> 200 with CORS; invalid key -> 401 with CORS.
        """
        whitelisted = "https://killergerbah.github.io"

        # 1. Valid key -> 200 with CORS
        res200 = self._post(
            {"action": "version", "version": 6, "key": self.mining_key},
            headers={"Origin": whitelisted},
        )
        self.assertEqual(res200.status_code, 200)
        self.assertEqual(res200.headers.get("Access-Control-Allow-Origin"), whitelisted)
        self.assertIn("Origin", res200.headers.get("Vary", ""))

        # 2. Invalid key -> 401 with CORS
        res401 = self._post(
            {"action": "version", "version": 6, "key": "bad_key"},
            headers={"Origin": whitelisted},
        )
        self.assertEqual(res401.status_code, 401)
        self.assertEqual(res401.headers.get("Access-Control-Allow-Origin"), whitelisted)
        self.assertIn("Origin", res401.headers.get("Vary", ""))

        # 3. Missing key -> 401 with CORS
        res_missing = self._post(
            {"action": "version", "version": 6},
            headers={"Origin": whitelisted},
        )
        self.assertEqual(res_missing.status_code, 401)
        self.assertEqual(res_missing.headers.get("Access-Control-Allow-Origin"), whitelisted)

    def test_payload_size_limit_413_cors_behavior(self):
        """Payload exceeding CONNECT_ANKI_MAX_CONTENT_LENGTH returns 413.

        Valid extension receives CORS headers on 413 so client can diagnose.
        Untrusted web origin does NOT receive CORS headers.
        """
        self.app.config["CONNECT_ANKI_MAX_CONTENT_LENGTH"] = 100
        big_payload = {"action": "version", "version": 6, "key": self.mining_key, "padding": "x" * 200}
        raw_big = json.dumps(big_payload).encode("utf-8")

        # Extension origin: 413 with CORS
        ext_origin = "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab"
        res_ext = self.client.post(
            "/v1/anki-connect",
            data=raw_big,
            headers={"Origin": ext_origin},
            content_type="application/json",
        )
        self.assertEqual(res_ext.status_code, 413)
        self.assertEqual(res_ext.headers.get("Access-Control-Allow-Origin"), ext_origin)
        self.assertEqual(res_ext.headers.get("Cache-Control"), "no-store")

        # Untrusted origin: 403 Forbidden because origin check occurs BEFORE body size check!
        evil_origin = "https://evil.com"
        res_evil = self.client.post(
            "/v1/anki-connect",
            data=raw_big,
            headers={"Origin": evil_origin},
            content_type="application/json",
        )
        self.assertEqual(res_evil.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", res_evil.headers)

    def test_rate_limited_429_cors_behavior(self):
        """When rate limit is tripped (429), verify Retry-After and CORS headers."""
        from unittest.mock import patch
        ext_origin = "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab"
        evil_origin = "https://evil.com"

        with patch("app.connect.request_pipeline.rate_allowed", return_value=False):
            # Extension origin receives 429 with CORS and Retry-After
            res_ext = self._post(
                {"action": "version", "version": 6, "key": self.mining_key},
                headers={"Origin": ext_origin},
            )
            self.assertEqual(res_ext.status_code, 429)
            self.assertEqual(res_ext.headers.get("Access-Control-Allow-Origin"), ext_origin)
            self.assertIn("Retry-After", res_ext.headers)

            # Untrusted origin is blocked at Origin check (403), NOT at rate limiter (429)
            res_evil = self._post(
                {"action": "version", "version": 6, "key": self.mining_key},
                headers={"Origin": evil_origin},
            )
            self.assertEqual(res_evil.status_code, 403)
            self.assertNotIn("Access-Control-Allow-Origin", res_evil.headers)

    def test_internal_server_error_500_cors_behavior(self):
        """When an unhandled internal exception occurs (500), verify error envelope and CORS."""
        from unittest.mock import patch
        ext_origin = "chrome-extension://hkledmpjpaehamkiehglnbelcpdflcab"

        with patch("app.connect.request_pipeline.service.dispatch", side_effect=RuntimeError("db crash")):
            res_ext = self._post(
                {"action": "version", "version": 6, "key": self.mining_key},
                headers={"Origin": ext_origin},
            )
            self.assertEqual(res_ext.status_code, 500)
            self.assertEqual(res_ext.headers.get("Access-Control-Allow-Origin"), ext_origin)
            self.assertEqual(res_ext.get_json(), {"result": None, "error": "internal error"})

    def test_malformed_and_boundary_origin_headers(self):
        """Adversarial Origin header probing:

        - Comma-delimited origins (Origin spoofing attempt)
        - Scheme casing variations
        - Whitespace and padding
        """
        # 1. Comma-separated: "https://evil.com, https://killergerbah.github.io"
        res_comma = self._options(
            headers={"Origin": "https://evil.com, https://killergerbah.github.io"}
        )
        self.assertEqual(res_comma.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", res_comma.headers)

        # 2. Substring matching bypass attempt: "https://killergerbah.github.io.attacker.org"
        res_sub = self._options(
            headers={"Origin": "https://killergerbah.github.io.attacker.org"}
        )
        self.assertEqual(res_sub.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", res_sub.headers)

        # 3. Scheme prefix attack: "chrome-extension://attacker.com/fake"
        # While it has the scheme, standard extensions don't have host paths;
        # let's confirm whether scheme prefix allows it:
        res_ext_path = self._options(
            headers={"Origin": "chrome-extension://attacker.com/fake"}
        )
        self.assertEqual(res_ext_path.status_code, 204)
        self.assertEqual(res_ext_path.headers.get("Access-Control-Allow-Origin"), "chrome-extension://attacker.com/fake")


if __name__ == "__main__":
    unittest.main()
