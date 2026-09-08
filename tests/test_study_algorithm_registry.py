from __future__ import annotations

from datetime import datetime
import unittest

from app.services.anki_scheduler import Answer, CardState, DeckOptions
from app.services.study_algorithm_registry import (
    AlgorithmArtifactSupport,
    AlgorithmIdentity,
    AlgorithmLifecycleState,
    AlgorithmResolutionPurpose,
    StudyAlgorithmNotFoundError,
    StudyAlgorithmRegistry,
    get_study_algorithm_support,
    list_study_algorithm_support,
    DEFAULT_ALGORITHM_IDENTITY,
)


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

if __name__ == "__main__":
    unittest.main()
