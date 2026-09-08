from __future__ import annotations

import unittest

from app.validators.study_session_wire import (
    BATCH_SCHEMA_V1,
    BATCH_SCHEMA_V2,
    COMMIT_SCHEMA_V1,
    COMMIT_SCHEMA_V2,
    SESSION_SCHEMA_V2,
    SESSION_SCHEMA_V3,
    StudyWireContractError,
    resolve_wire_envelope_contract,
    select_session_schema,
    validate_envelope_schema,
    validate_review_event_wire_contract,
)


class StudySessionWireContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "algorithm_key": "legacy-anki",
            "algorithm_version": "1.0.0",
            "config_schema_version": "scheduler-config.v1",
            "config_hash": "config-1",
        }
        self.base_event = {
            "rating": "good",
            "action_key": "review.good",
            "trigger_key": "scheduler.review.good",
            "trigger_contract_version": "1",
        }

    def test_envelope_versions_are_mapped_independently(self) -> None:
        v2 = resolve_wire_envelope_contract(SESSION_SCHEMA_V2)
        v3 = resolve_wire_envelope_contract(SESSION_SCHEMA_V3)
        self.assertEqual(v2.commit_schema, COMMIT_SCHEMA_V1)
        self.assertEqual(v2.batch_schema, BATCH_SCHEMA_V1)
        self.assertEqual(v3.commit_schema, COMMIT_SCHEMA_V2)
        self.assertEqual(v3.batch_schema, BATCH_SCHEMA_V2)

    def test_negotiation_preserves_old_clients_and_gates_v3(self) -> None:
        self.assertEqual(select_session_schema(None, v3_enabled=True), SESSION_SCHEMA_V2)
        self.assertEqual(
            select_session_schema([SESSION_SCHEMA_V3, SESSION_SCHEMA_V2], v3_enabled=False),
            SESSION_SCHEMA_V2,
        )
        self.assertEqual(
            select_session_schema([SESSION_SCHEMA_V3, SESSION_SCHEMA_V2], v3_enabled=True),
            SESSION_SCHEMA_V3,
        )
        self.assertEqual(
            select_session_schema([SESSION_SCHEMA_V2, SESSION_SCHEMA_V3], v3_enabled=True),
            SESSION_SCHEMA_V2,
        )

    def test_envelope_decoder_is_selected_from_pinned_session(self) -> None:
        self.assertEqual(
            validate_envelope_schema(
                COMMIT_SCHEMA_V2,
                session_schema=SESSION_SCHEMA_V3,
                envelope_kind="commit",
            ).session_schema,
            SESSION_SCHEMA_V3,
        )
        with self.assertRaisesRegex(StudyWireContractError, "pinned session"):
            validate_envelope_schema(
                COMMIT_SCHEMA_V2,
                session_schema=SESSION_SCHEMA_V2,
                envelope_kind="commit",
            )
        with self.assertRaisesRegex(StudyWireContractError, "expected study-batch.v2"):
            validate_envelope_schema(
                BATCH_SCHEMA_V1,
                session_schema=SESSION_SCHEMA_V3,
                envelope_kind="batch",
            )

    def test_v2_accepts_absent_or_complete_legacy_semantics(self) -> None:
        legacy = {"rating": "good"}
        self.assertEqual(
            validate_review_event_wire_contract(
                legacy,
                session_schema=SESSION_SCHEMA_V2,
                session_id="session-1",
                algorithm_key="legacy-anki",
                algorithm_version="1.0.0",
                policy=self.policy,
                event_index=1,
            ).rating,
            "good",
        )
        self.assertEqual(
            validate_review_event_wire_contract(
                self.base_event,
                session_schema=SESSION_SCHEMA_V2,
                session_id="session-1",
                algorithm_key="legacy-anki",
                algorithm_version="1.0.0",
                policy=self.policy,
                event_index=1,
            ).rating,
            "good",
        )

    def test_v2_rejects_partial_or_v3_metadata(self) -> None:
        with self.assertRaisesRegex(StudyWireContractError, "partial v2"):
            validate_review_event_wire_contract(
                {"rating": "good", "action_key": "review.good"},
                session_schema=SESSION_SCHEMA_V2,
                session_id="session-1",
                algorithm_key="legacy-anki",
                algorithm_version="1.0.0",
                policy=self.policy,
                event_index=1,
            )
        with self.assertRaisesRegex(StudyWireContractError, "mixes v3"):
            validate_review_event_wire_contract(
                {**self.base_event, "action_contract_version": "1"},
                session_schema=SESSION_SCHEMA_V2,
                session_id="session-1",
                algorithm_key="legacy-anki",
                algorithm_version="1.0.0",
                policy=self.policy,
                event_index=1,
            )

    def test_v3_requires_exact_session_algorithm_config_and_action(self) -> None:
        event = {
            **self.base_event,
            "action_contract_version": "1",
            "algorithm_key": "legacy-anki",
            "algorithm_version": "1.0.0",
            "config_schema_version": "scheduler-config.v1",
            "config_hash": "config-1",
            "study_session_id": "session-1",
        }
        action = validate_review_event_wire_contract(
            event,
            session_schema=SESSION_SCHEMA_V3,
            session_id="session-1",
            algorithm_key="legacy-anki",
            algorithm_version="1.0.0",
            policy=self.policy,
            event_index=1,
        )
        self.assertEqual(action.action_key, "review.good")

        for field, bad_value in (
            ("action_contract_version", "2"),
            ("trigger_key", "scheduler.review.easy"),
            ("algorithm_version", "latest"),
            ("config_hash", "other"),
            ("study_session_id", "other-session"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(StudyWireContractError):
                    validate_review_event_wire_contract(
                        {**event, field: bad_value},
                        session_schema=SESSION_SCHEMA_V3,
                        session_id="session-1",
                        algorithm_key="legacy-anki",
                        algorithm_version="1.0.0",
                        policy=self.policy,
                        event_index=1,
                    )

    def test_v3_missing_required_metadata_fails_closed(self) -> None:
        with self.assertRaisesRegex(StudyWireContractError, "action_contract_version"):
            validate_review_event_wire_contract(
                self.base_event,
                session_schema=SESSION_SCHEMA_V3,
                session_id="session-1",
                algorithm_key="legacy-anki",
                algorithm_version="1.0.0",
                policy=self.policy,
                event_index=1,
            )


if __name__ == "__main__":
    unittest.main()
