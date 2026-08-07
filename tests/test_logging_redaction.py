import logging
import unittest
from io import StringIO

from app.utils.logging_redactor import RedactingFormatter, mask_key, redact_sensitive_text


class LoggingRedactionTests(unittest.TestCase):
    def test_mask_key_format(self):
        sample_key = "flama_yt_12345678_ABCDEF1234567890abcdef1234567890UXw"
        masked = mask_key(sample_key)
        self.assertTrue(masked.startswith("flama_yt"))
        self.assertTrue(masked.endswith("UXw"))
        self.assertNotIn("ABCDEF1234567890", masked)

    def test_redact_sensitive_text_standalone_key(self):
        raw = "Failed auth for token flama_yt_12345678_ABCDEF1234567890abcdef1234567890UXw in service"
        sanitized = redact_sensitive_text(raw)
        self.assertNotIn("ABCDEF1234567890", sanitized)
        self.assertIn("flama_yt", sanitized)
        self.assertIn("****", sanitized)

    def test_redact_authorization_header(self):
        raw = "Sending request with Authorization: Bearer flama_yt_12345678_ABCDEF1234567890abcdef1234567890UXw to host"
        sanitized = redact_sensitive_text(raw)
        self.assertNotIn("ABCDEF1234567890", sanitized)
        self.assertIn("Authorization: Bearer flama_yt", sanitized)

    def test_redact_x_flama_connect_key_header(self):
        raw = "X-Flama-Connect-Key: flama_yt_12345678_ABCDEF1234567890abcdef1234567890UXw"
        sanitized = redact_sensitive_text(raw)
        self.assertNotIn("ABCDEF1234567890", sanitized)
        self.assertIn("X-Flama-Connect-Key: flama_yt", sanitized)

    def test_redact_url_path_key(self):
        raw = "GET /v1/flama-connect/flama_yt_12345678_ABCDEF1234567890abcdef1234567890UXw HTTP/1.1"
        sanitized = redact_sensitive_text(raw)
        self.assertNotIn("ABCDEF1234567890", sanitized)
        self.assertIn("/v1/flama-connect/flama_yt", sanitized)

    def test_logging_formatter_integration(self):
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))

        test_logger = logging.getLogger("test_redactor")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)

        test_key = "flama_yt_99999999_secretkeyvalueabcdef12345678900000END"
        test_logger.info("Connecting using key=%s", test_key)

        output = stream.getvalue()
        self.assertNotIn("secretkeyvalue", output)
        self.assertIn("flama_yt", output)
        self.assertIn("END", output)


if __name__ == "__main__":
    unittest.main()
