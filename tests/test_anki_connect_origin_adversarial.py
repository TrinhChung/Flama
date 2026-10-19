"""Adversarial stress-testing suite for Flama Connect Origin validation (/v1/anki-connect)."""

import json
import unittest

from tests import test_flama_connect as legacy_fixture
from app.services import user_api_token_service as tokens
from app.services.connect.mining_setup import prepare_sentence_mining
from models import db


class AdversarialOriginValidationTests(unittest.TestCase):
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

    def rpc(self, action="version", params=None, *, version=6, key=None, headers=None, content_type="text/plain; charset=UTF-8"):
        payload = {"action": action, "key": self.mining_key if key is None else key}
        if version is not None:
            payload["version"] = version
        if params is not None:
            payload["params"] = params
        return self.client.post(
            "/v1/anki-connect",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type=content_type,
            headers=headers or {},
        )

    def preflight(self, origin, headers=None):
        req_headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Flama-Connect-Key",
        }
        if headers:
            req_headers.update(headers)
        return self.client.options("/v1/anki-connect", headers=req_headers)

    # -------------------------------------------------------------------------
    # 1. Prefix and Suffix Spoofing Vectors
    # -------------------------------------------------------------------------

    def test_prefix_and_suffix_spoofing_attacks(self):
        """Attacker crafts origins that mimic legitimate schemes or domains."""
        adversarial_origins = [
            # Scheme mimicry attacks
            "chrome-extension-evil://ogmnaimimemjmbakcfefmnngchbpflhe",
            "moz-extension-fake://d3b07384-d113-4684-9351-cc80e4b8e23f",
            "chrome-extension:",
            "moz-extension:",
            "not-chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe",
            "chrome-extension.evil.com",
            "moz-extension.evil.com",
            "https://chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe",
            "http://chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe",
            # Domain suffix / subdomain attacks
            "https://killergerbah.github.io.attacker.com",
            "https://killergerbah.github.io.evil.org",
            "https://killergerbah.github.io-attacker.com",
            "https://evil-killergerbah.github.io.com",
            "https://sub.killergerbah.github.io.attacker.com",
            # Prefix attacks
            "https://evil.killergerbah.github.io",
            "https://fake-killergerbah.github.io",
            # Protocol / Port spoofing
            "http://killergerbah.github.io",  # HTTP downgrade
            "https://killergerbah.github.io:8080",  # Custom port
            "https://killergerbah.github.io:443",  # Explicit standard port
            "https://killergerbah.github.io:8443",
            # Path and parameter injection attempts in Origin header
            "https://attacker.com/https://killergerbah.github.io",
            "https://attacker.com?origin=https://killergerbah.github.io",
            "https://attacker.com#https://killergerbah.github.io",
            "https://killergerbah.github.io@attacker.com",
            "https://user:pass@killergerbah.github.io",
            # Data / Javascript / File URIs
            "data:text/html,<html>evil</html>",
            "javascript:alert(1)",
            "file://",
            "file:///etc/passwd",
        ]

        for origin in adversarial_origins:
            with self.subTest(origin=origin):
                # 1. Preflight OPTIONS
                opt = self.preflight(origin)
                self.assertEqual(
                    opt.status_code,
                    403,
                    f"Preflight should be 403 Forbidden for '{origin}', got {opt.status_code}",
                )
                self.assertNotIn(
                    "Access-Control-Allow-Origin",
                    opt.headers,
                    f"CORS header must NOT be present on 403 preflight for '{origin}'",
                )

                # 2. POST execution
                post = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(
                    post.status_code,
                    403,
                    f"POST should be 403 Forbidden for '{origin}', got {post.status_code}",
                )
                self.assertNotIn(
                    "Access-Control-Allow-Origin",
                    post.headers,
                    f"CORS header must NOT be present on 403 POST for '{origin}'",
                )
                data = post.get_json()
                self.assertEqual(data.get("error"), "origin is not allowed")

    # -------------------------------------------------------------------------
    # 2. Case Sensitivity Attacks
    # -------------------------------------------------------------------------

    def test_case_sensitivity_attacks(self):
        """Case variations in scheme or domain should be rejected or handled strictly."""
        variations = [
            # Uppercase or mixed-case extension schemes
            "CHROME-EXTENSION://ogmnaimimemjmbakcfefmnngchbpflhe",
            "MOZ-EXTENSION://d3b07384-d113-4684-9351-cc80e4b8e23f",
            "Chrome-Extension://ogmnaimimemjmbakcfefmnngchbpflhe",
            "Moz-Extension://d3b07384-d113-4684-9351-cc80e4b8e23f",
            # Uppercase or mixed-case domain names
            "https://KILLERGERBAH.GITHUB.IO",
            "HTTPS://killergerbah.github.io",
            "Https://KillerGerbah.GitHub.io",
            "https://killergerbah.GITHUB.IO",
        ]

        for origin in variations:
            with self.subTest(origin=origin):
                # Must be rejected because allowlist and prefix match are case-sensitive
                post = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(post.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", post.headers)
                self.assertEqual(post.get_json().get("error"), "origin is not allowed")

    # -------------------------------------------------------------------------
    # 3. Trailing Slashes and Paths in Origin
    # -------------------------------------------------------------------------

    def test_trailing_slashes_and_paths(self):
        """Standard web origins with trailing slashes or paths are rejected."""
        invalid_web_origins = [
            "https://killergerbah.github.io/",
            "https://killergerbah.github.io/index.html",
            "https://killergerbah.github.io/app/",
            "https://killergerbah.github.io//",
        ]
        for origin in invalid_web_origins:
            with self.subTest(origin=origin):
                post = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(post.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", post.headers)

    # -------------------------------------------------------------------------
    # 4. Null Origin Representations
    # -------------------------------------------------------------------------

    def test_null_origin_and_empty_origin_handling(self):
        """Verify handling of null, empty, whitespace, and missing Origin headers."""
        # A. Origin: "null" (e.g. sandboxed iframe or file-based local desktop tool)
        # Permitted for requests with valid API key, but MUST NOT return CORS allow-origin header
        null_valid = self.rpc("version", headers={"Origin": "null"})
        self.assertEqual(null_valid.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", null_valid.headers)
        self.assertIsNone(null_valid.get_json().get("error"))

        # Preflight with Origin: "null" returns 204 but NO CORS allow-origin header
        null_opt = self.preflight("null")
        self.assertEqual(null_opt.status_code, 204)
        self.assertNotIn("Access-Control-Allow-Origin", null_opt.headers)

        # Origin: "null" with invalid key rejects with 401 and NO CORS header
        null_bad = self.rpc("version", key="bad-key", headers={"Origin": "null"})
        self.assertEqual(null_bad.status_code, 401)
        self.assertNotIn("Access-Control-Allow-Origin", null_bad.headers)

        # B. Origin: "" (empty string) - must be 403 Forbidden
        empty_opt = self.preflight("")
        self.assertEqual(empty_opt.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", empty_opt.headers)

        empty_post = self.rpc("version", headers={"Origin": ""})
        self.assertEqual(empty_post.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", empty_post.headers)
        self.assertEqual(empty_post.get_json().get("error"), "origin is not allowed")

        # C. Whitespace or deformed null strings
        deformed = [" null ", "NULL", "None", "undefined", "0", "false"]
        for origin in deformed:
            with self.subTest(origin=origin):
                res = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(res.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", res.headers)

        # D. Omitted Origin header (desktop apps, curl, python scripts)
        no_origin_valid = self.rpc("version", headers={})
        self.assertEqual(no_origin_valid.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", no_origin_valid.headers)

        no_origin_bad = self.rpc("version", key="bad-key", headers={})
        self.assertEqual(no_origin_bad.status_code, 401)
        self.assertNotIn("Access-Control-Allow-Origin", no_origin_bad.headers)

    # -------------------------------------------------------------------------
    # 5. Localhost and LAN Origins
    # -------------------------------------------------------------------------

    def test_localhost_and_lan_origins_rejected_by_default(self):
        """Localhost and private network IP origins are rejected unless in allowlist."""
        lan_origins = [
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:4789",
            "http://localhost:8080",
            "https://localhost:3000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
            "http://0.0.0.0:3000",
            "http://[::1]:3000",
            "http://192.168.1.1:3000",
            "http://192.168.1.100:8080",
            "http://10.0.0.1:3000",
            "http://172.16.0.1:3000",
            "http://10.254.254.254",
        ]

        for origin in lan_origins:
            with self.subTest(origin=origin):
                opt = self.preflight(origin)
                self.assertEqual(opt.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", opt.headers)

                post = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(post.status_code, 403)
                self.assertNotIn("Access-Control-Allow-Origin", post.headers)

    # -------------------------------------------------------------------------
    # 6. Wildcard and Config Invalidation Defenses
    # -------------------------------------------------------------------------

    def test_wildcard_and_null_in_allowlist_are_defensively_ignored(self):
        """Even if CONNECT_ANKI_ALLOWED_ORIGINS is misconfigured with '*' or 'null',

        these dangerous origins are stripped and never allowed or echoed.
        """
        # Inject dangerous configuration
        self.app.config["CONNECT_ANKI_ALLOWED_ORIGINS"] = (
            "*",
            "null",
            "https://killergerbah.github.io",
        )

        # Attacker tries to use '*' as origin
        wildcard_post = self.rpc("version", headers={"Origin": "*"})
        self.assertEqual(wildcard_post.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", wildcard_post.headers)

        # Attacker tries arbitrary domain
        evil_post = self.rpc("version", headers={"Origin": "https://evil.com"})
        self.assertEqual(evil_post.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", evil_post.headers)

        # Origin 'null' is handled by the 'null' desktop branch (allowed to compute with key, but NO CORS header)
        null_post = self.rpc("version", headers={"Origin": "null"})
        self.assertEqual(null_post.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", null_post.headers)

        # Legitimate whitelisted origin still works
        valid_post = self.rpc("version", headers={"Origin": "https://killergerbah.github.io"})
        self.assertEqual(valid_post.status_code, 200)
        self.assertEqual(
            valid_post.headers.get("Access-Control-Allow-Origin"),
            "https://killergerbah.github.io",
        )

    # -------------------------------------------------------------------------
    # 7. Preflight vs POST Method Consistency & Security Headers
    # -------------------------------------------------------------------------

    def test_preflight_and_post_security_headers_consistency(self):
        """Ensure security headers are present and CORS headers are strictly scoped."""
        whitelisted = "https://killergerbah.github.io"
        extension = "chrome-extension://ogmnaimimemjmbakcfefmnngchbpflhe"

        for origin in [whitelisted, extension]:
            with self.subTest(origin=origin):
                # OPTIONS preflight
                opt = self.preflight(origin)
                self.assertEqual(opt.status_code, 204)
                self.assertEqual(opt.headers.get("Access-Control-Allow-Origin"), origin)
                self.assertEqual(opt.headers.get("Vary"), "Origin")
                self.assertEqual(opt.headers.get("Access-Control-Max-Age"), "600")
                self.assertIn("POST", opt.headers.get("Access-Control-Allow-Methods", ""))
                self.assertIn("OPTIONS", opt.headers.get("Access-Control-Allow-Methods", ""))
                self.assertIn("Content-Type", opt.headers.get("Access-Control-Allow-Headers", ""))
                self.assertIn("X-Flama-Connect-Key", opt.headers.get("Access-Control-Allow-Headers", ""))
                self.assertEqual(opt.headers.get("X-Content-Type-Options"), "nosniff")

                # Successful POST
                post = self.rpc("version", headers={"Origin": origin})
                self.assertEqual(post.status_code, 200)
                self.assertEqual(post.headers.get("Access-Control-Allow-Origin"), origin)
                self.assertEqual(post.headers.get("Vary"), "Origin")
                self.assertEqual(post.headers.get("X-Content-Type-Options"), "nosniff")

                # Failed POST (e.g. invalid key) - CORS headers still present so client UI knows it's auth error
                post_bad_key = self.rpc("version", key="wrong-key", headers={"Origin": origin})
                self.assertEqual(post_bad_key.status_code, 401)
                self.assertEqual(post_bad_key.headers.get("Access-Control-Allow-Origin"), origin)
                self.assertEqual(post_bad_key.headers.get("Vary"), "Origin")

    # -------------------------------------------------------------------------
    # 8. Unauthenticated and Action Execution Protection Under Untrusted Origin
    # -------------------------------------------------------------------------

    def test_untrusted_origin_cannot_trigger_any_action_even_with_valid_key(self):
        """Untrusted web origins cannot execute write actions (e.g. addNote) even if they possess an API key."""
        malicious_origin = "https://malicious-website.com"
        note_payload = {
            "note": {
                "deckName": "Sentences",
                "modelName": "Sentence Card",
                "fields": {"Sentence": "攻撃テスト", "Definition": "Attack test"},
            }
        }
        res = self.rpc("addNote", note_payload, headers={"Origin": malicious_origin})
        self.assertEqual(res.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", res.headers)
        self.assertEqual(res.get_json().get("error"), "origin is not allowed")


if __name__ == "__main__":
    unittest.main()
