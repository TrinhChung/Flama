"""Contract tests for bounded ReviewEvent payloads and legacy classification."""

import json
import unittest

from app.validators.review_event import (
    ReviewEventPayloadError,
    build_anki_revlog_review_event_payload,
    build_native_review_event_payload,
    classify_review_event_payload,
    validate_native_client_payload,
    validate_session_event_payload,
)


RUNTIME = {
    "action_key": "review.good",
    "trigger_key": "scheduler.review.good",
    "trigger_contract_version": "1",
    "algorithm_key": "legacy-anki",
    "algorithm_version": "1.0.0",
    "state_schema_version": "anki-card-state.v1",
}
CONFIG_HASH = "sha256:config"


class ReviewEventProvenanceContractTests(unittest.TestCase):
    def test_native_envelope_uses_trusted_source_and_bounded_context(self):
        encoded = build_native_review_event_payload(
            source_path="native.mcp",
            runtime=RUNTIME,
            scheduler_config_hash=CONFIG_HASH,
            client_payload={
                "duration_ms": 1200,
                "timezone": "UTC",
                "scope": "deck",
                "scope_id": 42,
            },
            client_event_id="mcp-review-id",
        )
        payload = json.loads(encoded)
        self.assertEqual(payload["schema_version"], "review-event-payload.v1")
        self.assertEqual(payload["provenance"]["source_path"], "native.mcp")
        self.assertEqual(payload["source"], "mcp")
        self.assertEqual(payload["client_context"], {"scope": "deck", "scope_id": 42})
        self.assertNotIn("duration_ms", payload)
        self.assertNotIn("timezone", payload)
        self.assertEqual(payload["_study_runtime"]["action_contract_version"], "1")

    def test_spoofed_malformed_and_oversized_payloads_are_typed(self):
        cases = (
            ({"source": "mcp"}, "REVIEW_EVENT_PAYLOAD_FIELD_NOT_ALLOWED", 422),
            ({"duration_ms": True}, "INVALID_REVIEW_DURATION", 422),
            (
                {"selection_id": "x" * 513},
                "REVIEW_EVENT_PAYLOAD_STRING_TOO_LONG",
                413,
            ),
        )
        for payload, code, status in cases:
            with self.subTest(code=code), self.assertRaises(ReviewEventPayloadError) as cm:
                validate_native_client_payload(payload, source_path="native.rest")
            self.assertEqual(cm.exception.code, code)
            self.assertEqual(cm.exception.status, status)

    def test_session_allowlist_rejects_provenance_claim_and_float_sequence(self):
        valid = {
            "event_id": "event-id",
            "sequence": 1,
            "card_id": "card-id",
            "rating": "good",
            "action_contract_version": "1",
            "algorithm_key": "legacy-anki",
            "algorithm_version": "1.0.0",
            "config_schema_version": "anki-scheduler-config.v1",
            "config_hash": "sha256:config",
            "study_session_id": "session-id",
            "scheduler_offset_ms": 100,
            "duration_ms": 500,
        }
        self.assertEqual(validate_session_event_payload(valid), valid)
        for mutation in (
            {"source_path": "native.mcp"},
            {"sequence": 1.0},
            {"action_contract_version": 1},
            {"algorithm_key": False},
            {"algorithm_version": 1},
            {"config_schema_version": []},
            {"config_hash": {}},
            {"study_session_id": 42},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(
                ReviewEventPayloadError
            ):
                validate_session_event_payload({**valid, **mutation})

    def test_external_revlog_envelope_has_no_native_action(self):
        encoded = build_anki_revlog_review_event_payload(
            source_key="anki-connect",
            import_session_id="session-id",
            external_review_id="1700000000000",
            external_card_id="card-1",
            record={
                "sourceReviewId": "1700000000000",
                "sourceCardId": "card-1",
                "ease": 3,
                "type": 1,
                "ivl": 10,
                "lastIvl": 5,
                "factor": 2500,
                "time": 1500,
            },
        )
        payload = json.loads(encoded)
        self.assertEqual(payload["provenance"]["kind"], "external")
        self.assertEqual(
            payload["provenance"]["source_path"],
            "external.anki.revlog",
        )
        self.assertNotIn("_study_runtime", payload)
        disposition = classify_review_event_payload(
            encoded,
            scheduler_algorithm="anki",
            algorithm_version="revlog-v1",
        )
        self.assertEqual(disposition.category, "complete")

    def test_classifier_distinguishes_missing_conflict_and_legacy(self):
        canonical = json.loads(
            build_native_review_event_payload(
                source_path="native.rest",
                runtime=RUNTIME,
                scheduler_config_hash=CONFIG_HASH,
            )
        )
        missing = dict(canonical)
        missing.pop("_study_runtime")
        conflicting = json.loads(json.dumps(canonical))
        conflicting["_study_runtime"]["algorithm_version"] = "9.9.9"

        self.assertEqual(
            classify_review_event_payload(json.dumps(missing)).category,
            "missing_expected_field",
        )
        self.assertEqual(
            classify_review_event_payload(
                json.dumps(conflicting),
                scheduler_algorithm="legacy-anki",
                algorithm_version="1.0.0",
                scheduler_config_hash=CONFIG_HASH,
            ).category,
            "conflicting",
        )
        self.assertEqual(
            classify_review_event_payload('{"source":"direct"}').category,
            "legacy_unknown",
        )


if __name__ == "__main__":
    unittest.main()
