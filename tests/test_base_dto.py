"""Unit tests for Pydantic v2 BaseDTO validator integration."""

import unittest
from pydantic import Field, HttpUrl
from app.validators.base import BaseDTO
from app.validators.flashcard_input import RequestValidationError


class SampleDonationDTO(BaseDTO):
    amount: int = Field(ge=1000, le=50_000_000)
    return_url: HttpUrl
    anonymous: bool = False


class TestBaseDTO(unittest.TestCase):
    def test_valid_payload_parsing(self):
        payload = {
            "amount": 50000,
            "return_url": "https://flama.app/success",
            "anonymous": True,
            "extra_field_to_ignore": "some_value",
        }
        dto = SampleDonationDTO.from_payload(payload)
        self.assertEqual(dto.amount, 50000)
        self.assertEqual(str(dto.return_url), "https://flama.app/success")
        self.assertTrue(dto.anonymous)

    def test_non_dict_payload_raises_request_validation_error(self):
        with self.assertRaises(RequestValidationError) as ctx:
            SampleDonationDTO.from_payload("not-a-dict")
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.field, "body")
        self.assertIn("JSON object", str(ctx.exception))

    def test_field_constraint_violation(self):
        payload = {
            "amount": 500,  # Below minimum 1000
            "return_url": "https://flama.app/success",
        }
        with self.assertRaises(RequestValidationError) as ctx:
            SampleDonationDTO.from_payload(payload)
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.field, "amount")

    def test_invalid_url_format(self):
        payload = {
            "amount": 10000,
            "return_url": "not-a-valid-url",
        }
        with self.assertRaises(RequestValidationError) as ctx:
            SampleDonationDTO.from_payload(payload)
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.field, "return_url")

    def test_field_prefix_support(self):
        payload = {
            "amount": -1,
            "return_url": "https://flama.app",
        }
        with self.assertRaises(RequestValidationError) as ctx:
            SampleDonationDTO.from_payload(payload, field_prefix="data")
        self.assertEqual(ctx.exception.field, "data.amount")


if __name__ == "__main__":
    unittest.main()
