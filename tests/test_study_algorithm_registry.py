from __future__ import annotations

from datetime import datetime
import unittest

from app.services.anki_scheduler import Answer, CardState, DeckOptions
from app.services.study_algorithm_registry import (
    DEFAULT_ALGORITHM_IDENTITY,
    AlgorithmArtifactSupport,
    AlgorithmIdentity,
    AlgorithmLifecycleState,
    AlgorithmResolutionPurpose,
    StudyAlgorithmNotFoundError,
    StudyAlgorithmRegistry,
    get_study_algorithm_support,
    list_study_algorithm_support,
    resolve_study_algorithm_switch_target,
)
from app.services.study_progress_contract import HISTORY_SCHEMA_VERSION
from app.services.study_progress_shadow_codec import StateDecoderRegistry


class _FakeAlgorithm:
    def __init__(self, key: str, version: str) -> None:
        self.identity = AlgorithmIdentity(
            key=key,
            version=version,
            state_schema_version=f"{key}-state.v1",
        )

    def transition(
        self,
        state: CardState,
        options: DeckOptions,
        now: datetime,
        answer: Answer,
        *,
        timezone_name: str,
    ) -> CardState:
        return state

    def previews(
        self,
        state: CardState,
        options: DeckOptions,
        now: datetime,
        *,
        timezone_name: str,
    ) -> dict:
        return {}


class _FakeSwitchInitializer:
    state_storage_codec = "test-state-json.v1"
    history_schema_version = HISTORY_SCHEMA_VERSION

    def __init__(self, identity: AlgorithmIdentity) -> None:
        self.identity = identity

    def initialize(self, *, frozen_history_cut: object) -> object:
        return frozen_history_cut

    def decode_config(self, payload: object) -> object:
        return payload

    def decode_history_fact(self, payload: object) -> object:
        return payload


class StudyAlgorithmRegistryLifecycleTests(unittest.TestCase):
    def _register(
        self,
        registry: StudyAlgorithmRegistry,
        version: str,
        state: AlgorithmLifecycleState,
    ) -> _FakeAlgorithm | None:
        adapter = None if state is AlgorithmLifecycleState.RETIRED else _FakeAlgorithm(
            "algorithm",
            version,
        )
        identity = (
            adapter.identity
            if adapter is not None
            else AlgorithmIdentity("algorithm", version, "algorithm-state.v1")
        )
        registry.register(
            identity=identity,
            lifecycle_state=state,
            adapter=adapter,
        )
        return adapter

    def test_new_session_accepts_active_and_deprecated_but_not_lease_only(self):
        registry = StudyAlgorithmRegistry()
        active = self._register(registry, "1", AlgorithmLifecycleState.ACTIVE)
        deprecated = self._register(
            registry,
            "2",
            AlgorithmLifecycleState.DEPRECATED,
        )
        self._register(registry, "3", AlgorithmLifecycleState.LEASE_ONLY)

        self.assertIs(
            registry.resolve(
                "algorithm",
                "1",
                purpose=AlgorithmResolutionPurpose.NEW_SESSION,
            ),
            active,
        )
        self.assertIs(
            registry.resolve(
                "algorithm",
                "2",
                purpose=AlgorithmResolutionPurpose.NEW_SESSION,
            ),
            deprecated,
        )
        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            registry.resolve(
                "algorithm",
                "3",
                purpose=AlgorithmResolutionPurpose.NEW_SESSION,
            )
        self.assertEqual(caught.exception.code, "ALGORITHM_UNAVAILABLE")
        self.assertEqual(caught.exception.reason, "PURPOSE_NOT_SUPPORTED")
        self.assertEqual(
            caught.exception.lifecycle_state,
            AlgorithmLifecycleState.LEASE_ONLY,
        )

    def test_lease_only_remains_available_for_existing_lease_and_accepted_job(self):
        registry = StudyAlgorithmRegistry()
        adapter = self._register(
            registry,
            "1",
            AlgorithmLifecycleState.LEASE_ONLY,
        )

        self.assertIs(
            registry.resolve(
                "algorithm",
                "1",
                purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
            ),
            adapter,
        )
        self.assertIs(
            registry.resolve(
                "algorithm",
                "1",
                purpose=AlgorithmResolutionPurpose.ACCEPTED_JOB,
            ),
            adapter,
        )

    def test_retired_version_cannot_execute_but_history_can_remain_readable(self):
        registry = StudyAlgorithmRegistry()
        self._register(registry, "1", AlgorithmLifecycleState.RETIRED)

        support = registry.support("algorithm", "1")
        self.assertIsNotNone(support)
        assert support is not None
        self.assertFalse(support.server_executable)
        self.assertFalse(support.existing_lease_allowed)
        self.assertTrue(support.history_read_allowed)

        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            registry.resolve(
                "algorithm",
                "1",
                purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
            )
        self.assertEqual(caught.exception.reason, "RETIRED")

    def test_history_readability_is_an_independent_retained_artifact(self):
        registry = StudyAlgorithmRegistry()
        identity = AlgorithmIdentity("algorithm", "1", "algorithm-state.v1")
        registry.register(
            identity=identity,
            lifecycle_state=AlgorithmLifecycleState.RETIRED,
            adapter=None,
            artifacts=AlgorithmArtifactSupport(event_history_decoder=False),
        )

        support = registry.support("algorithm", "1")
        self.assertIsNotNone(support)
        assert support is not None
        self.assertFalse(support.history_read_allowed)
        self.assertTrue(support.artifacts.state_decoder)

    def test_unknown_exact_version_never_falls_back(self):
        registry = StudyAlgorithmRegistry()
        self._register(registry, "2", AlgorithmLifecycleState.ACTIVE)

        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            registry.resolve(
                "algorithm",
                "1",
                purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
            )
        self.assertEqual(caught.exception.reason, "UNKNOWN_VERSION")
        self.assertIsNone(caught.exception.lifecycle_state)

    def test_support_introspection_is_deterministic_and_serializable(self):
        registry = StudyAlgorithmRegistry()
        self._register(registry, "2", AlgorithmLifecycleState.LEASE_ONLY)
        self._register(registry, "1", AlgorithmLifecycleState.ACTIVE)

        support = tuple(item.as_dict() for item in registry.list_support())

        self.assertEqual([item["version"] for item in support], ["1", "2"])
        self.assertEqual(support[0]["lifecycle_state"], "active")
        self.assertTrue(support[0]["new_session_allowed"])
        self.assertFalse(support[1]["new_session_allowed"])
        self.assertTrue(support[1]["existing_lease_allowed"])

    def test_production_default_is_active_and_new_session_eligible(self):
        support = get_study_algorithm_support(
            DEFAULT_ALGORITHM_IDENTITY.key,
            DEFAULT_ALGORITHM_IDENTITY.version,
        )

        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual(support.lifecycle_state, AlgorithmLifecycleState.ACTIVE)
        self.assertTrue(support.new_session_allowed)
        self.assertEqual(
            list_study_algorithm_support()[0]["state_schema_version"],
            DEFAULT_ALGORITHM_IDENTITY.state_schema_version,
        )

    def test_production_algorithm_has_no_implicit_switch_initializer(self):
        support = get_study_algorithm_support(
            DEFAULT_ALGORITHM_IDENTITY.key,
            DEFAULT_ALGORITHM_IDENTITY.version,
        )
        self.assertIsNotNone(support)
        assert support is not None
        self.assertFalse(support.switch_target_allowed)
        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            resolve_study_algorithm_switch_target(
                DEFAULT_ALGORITHM_IDENTITY.key,
                DEFAULT_ALGORITHM_IDENTITY.version,
            )
        self.assertEqual(caught.exception.reason, "INITIALIZER_UNAVAILABLE")

    def test_switch_requires_exact_active_executable_decoder_and_initializer(self):
        decoders = StateDecoderRegistry()
        registry = StudyAlgorithmRegistry(state_decoders=decoders)
        adapter = _FakeAlgorithm("algorithm", "2")
        registry.register(
            identity=adapter.identity,
            lifecycle_state=AlgorithmLifecycleState.ACTIVE,
            adapter=adapter,
        )
        initializer = _FakeSwitchInitializer(adapter.identity)

        with self.assertRaisesRegex(ValueError, "exact registered state decoder"):
            registry.register_switch_initializer(initializer)
        decoders.register(
            (
                adapter.identity.key,
                adapter.identity.version,
                adapter.identity.state_schema_version,
                initializer.state_storage_codec,
            ),
            lambda payload: payload,
        )
        registry.register_switch_initializer(initializer)
        target = registry.resolve_switch_target("algorithm", "2")
        self.assertIs(target.adapter, adapter)
        self.assertIs(target.initializer, initializer)
        support = registry.support("algorithm", "2")
        self.assertIsNotNone(support)
        assert support is not None
        self.assertTrue(support.switch_target_allowed)
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register_switch_initializer(initializer)
        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            registry.resolve_switch_target("algorithm", "1")
        self.assertEqual(caught.exception.reason, "UNKNOWN_VERSION")

    def test_switch_rejects_wrong_identity_incomplete_artifacts_and_draining_versions(
        self,
    ):
        decoders = StateDecoderRegistry()
        registry = StudyAlgorithmRegistry(state_decoders=decoders)
        active = _FakeAlgorithm("algorithm", "1")
        registry.register(
            identity=active.identity,
            lifecycle_state=AlgorithmLifecycleState.ACTIVE,
            adapter=active,
            artifacts=AlgorithmArtifactSupport(event_history_decoder=False),
        )
        with self.assertRaisesRegex(ValueError, "exact registered Algorithm identity"):
            registry.register_switch_initializer(
                _FakeSwitchInitializer(
                    AlgorithmIdentity("algorithm", "1", "wrong.v1")
                )
            )
        with self.assertRaisesRegex(ValueError, "state, config and history decoders"):
            registry.register_switch_initializer(_FakeSwitchInitializer(active.identity))

        draining = _FakeAlgorithm("algorithm", "2")
        registry.register(
            identity=draining.identity,
            lifecycle_state=AlgorithmLifecycleState.LEASE_ONLY,
            adapter=draining,
        )
        with self.assertRaisesRegex(ValueError, "Only an active executable"):
            registry.register_switch_initializer(
                _FakeSwitchInitializer(draining.identity)
            )
        with self.assertRaises(StudyAlgorithmNotFoundError) as caught:
            registry.resolve_switch_target("algorithm", "2")
        self.assertEqual(caught.exception.reason, "PURPOSE_NOT_SUPPORTED")

if __name__ == "__main__":
    unittest.main()
