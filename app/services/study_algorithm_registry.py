"""Versioned study Algorithm adapters and retirement lifecycle policy.

The registry is storage-neutral. ``CardProgress`` remains authoritative; this
module owns exact executable resolution and exposes the support metadata needed
to decide whether a version may be issued to a new session or used by an
already-admitted lease/job. Historical readability is deliberately represented
separately from executable replay support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Protocol

from app.services.anki_scheduler import (
    Answer,
    CardState,
    DeckOptions,
    applyAnswer,
    computeAnswerPreview,
)
from app.services.study_progress_contract import HISTORY_SCHEMA_VERSION
from app.services.study_progress_shadow_codec import STATE_DECODERS, StateDecoderRegistry


LEGACY_ANKI_ALGORITHM_KEY = "legacy-anki"
LEGACY_ANKI_ALGORITHM_VERSION = "1.0.0"
LEGACY_ANKI_STATE_SCHEMA_VERSION = "anki-card-state.v1"


@dataclass(frozen=True)
class AlgorithmIdentity:
    key: str
    version: str
    state_schema_version: str


class AlgorithmLifecycleState(str, Enum):
    """Operational support state for one exact Algorithm version.

    ``deprecated`` remains executable and may still be explicitly issued while
    operators drain callers. ``lease-only`` is the hard issuance cutoff.
    ``retired`` retains only the declared read/inspection capabilities.
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    LEASE_ONLY = "lease-only"
    RETIRED = "retired"


class AlgorithmResolutionPurpose(str, Enum):
    NEW_SESSION = "new-session"
    EXISTING_LEASE = "existing-lease"
    ACCEPTED_JOB = "accepted-job"
    SWITCH_TARGET = "switch-target"


@dataclass(frozen=True)
class AlgorithmArtifactSupport:
    """Artifacts retained for an exact Algorithm version on the server."""

    state_decoder: bool = True
    config_decoder: bool = True
    event_history_decoder: bool = True
    interaction_contract_decoder: bool = True


@dataclass(frozen=True)
class AlgorithmSupport:
    identity: AlgorithmIdentity
    lifecycle_state: AlgorithmLifecycleState
    artifacts: AlgorithmArtifactSupport
    server_executable: bool
    switch_initializer_registered: bool = False

    @property
    def new_session_allowed(self) -> bool:
        return self.server_executable and self.lifecycle_state in {
            AlgorithmLifecycleState.ACTIVE,
            AlgorithmLifecycleState.DEPRECATED,
        }

    @property
    def existing_lease_allowed(self) -> bool:
        return self.server_executable and self.lifecycle_state in {
            AlgorithmLifecycleState.ACTIVE,
            AlgorithmLifecycleState.DEPRECATED,
            AlgorithmLifecycleState.LEASE_ONLY,
        }

    @property
    def accepted_job_allowed(self) -> bool:
        return self.existing_lease_allowed

    @property
    def history_read_allowed(self) -> bool:
        return self.artifacts.event_history_decoder

    @property
    def switch_target_allowed(self) -> bool:
        """Registry readiness only; history/CAS/rollback gates remain separate."""

        return (
            self.server_executable
            and self.lifecycle_state is AlgorithmLifecycleState.ACTIVE
            and self.switch_initializer_registered
            and self.artifacts.state_decoder
            and self.artifacts.config_decoder
            and self.artifacts.event_history_decoder
        )

    def allows(self, purpose: AlgorithmResolutionPurpose) -> bool:
        if purpose is AlgorithmResolutionPurpose.NEW_SESSION:
            return self.new_session_allowed
        if purpose is AlgorithmResolutionPurpose.EXISTING_LEASE:
            return self.existing_lease_allowed
        if purpose is AlgorithmResolutionPurpose.ACCEPTED_JOB:
            return self.accepted_job_allowed
        if purpose is AlgorithmResolutionPurpose.SWITCH_TARGET:
            return self.switch_target_allowed
        return False

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.identity.key,
            "version": self.identity.version,
            "state_schema_version": self.identity.state_schema_version,
            "lifecycle_state": self.lifecycle_state.value,
            "server_executable": self.server_executable,
            "new_session_allowed": self.new_session_allowed,
            "existing_lease_allowed": self.existing_lease_allowed,
            "accepted_job_allowed": self.accepted_job_allowed,
            "history_read_allowed": self.history_read_allowed,
            "switch_initializer_registered": self.switch_initializer_registered,
            "switch_target_allowed": self.switch_target_allowed,
            "artifacts": asdict(self.artifacts),
        }


class StudyAlgorithmAdapter(Protocol):
    identity: AlgorithmIdentity

    def transition(
        self,
        state: CardState,
        options: DeckOptions,
        now: datetime,
        answer: Answer,
        *,
        timezone_name: str,
    ) -> CardState: ...

    def previews(
        self,
        state: CardState,
        options: DeckOptions,
        now: datetime,
        *,
        timezone_name: str,
    ) -> dict[Answer, dict[str, float | int | str | None]]: ...


class StudyAlgorithmSwitchInitializer(Protocol):
    """Target-owned initializer; invocation requires a separately frozen cut.

    Registration alone never authorizes a switch. The eventual command must
    verify the history cut, current-state CAS, idempotency and projection before
    invoking this target-specific implementation.
    """

    identity: AlgorithmIdentity
    state_storage_codec: str
    history_schema_version: str

    def decode_config(self, payload: object) -> object: ...

    def decode_history_fact(self, payload: object) -> object: ...

    def initialize(self, *, frozen_history_cut: object) -> object: ...


class StudyAlgorithmNotFoundError(LookupError):
    """Stable fail-closed error for an unavailable exact executable."""

    code = "ALGORITHM_UNAVAILABLE"

    def __init__(
        self,
        key: str,
        version: str,
        *,
        purpose: AlgorithmResolutionPurpose = AlgorithmResolutionPurpose.EXISTING_LEASE,
        lifecycle_state: AlgorithmLifecycleState | None = None,
        reason: str = "UNKNOWN_VERSION",
    ) -> None:
        display_key = key or "<missing>"
        display_version = version or "<missing>"
        super().__init__(
            f"Study Algorithm '{display_key}' version '{display_version}' "
            f"is unavailable for {purpose.value}."
        )
        self.key = key
        self.version = version
        self.purpose = purpose
        self.lifecycle_state = lifecycle_state
        self.reason = reason


class LegacyAnkiAlgorithmAdapter:
    """Compatibility adapter around the current production scheduler."""

    identity = AlgorithmIdentity(
        key=LEGACY_ANKI_ALGORITHM_KEY,
        version=LEGACY_ANKI_ALGORITHM_VERSION,
        state_schema_version=LEGACY_ANKI_STATE_SCHEMA_VERSION,
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
        return applyAnswer(
            state,
            options,
            now,
            answer,
            timezone_name=timezone_name,
        )

    def previews(
        self,
        state: CardState,
        options: DeckOptions,
        now: datetime,
        *,
        timezone_name: str,
    ) -> dict[Answer, dict[str, float | int | str | None]]:
        return computeAnswerPreview(
            state,
            options,
            now,
            timezone_name=timezone_name,
        )


@dataclass(frozen=True)
class _AlgorithmRegistration:
    support: AlgorithmSupport
    adapter: StudyAlgorithmAdapter | None
    switch_initializer: StudyAlgorithmSwitchInitializer | None = None


@dataclass(frozen=True)
class StudyAlgorithmSwitchTarget:
    adapter: StudyAlgorithmAdapter
    initializer: StudyAlgorithmSwitchInitializer


class StudyAlgorithmRegistry:
    """Exact-version registry with explicit issuance and drain semantics."""

    def __init__(self, *, state_decoders: StateDecoderRegistry | None = None) -> None:
        self._registrations: dict[tuple[str, str], _AlgorithmRegistration] = {}
        self._state_decoders = state_decoders or STATE_DECODERS

    @staticmethod
    def _key(key: str, version: str) -> tuple[str, str]:
        return (str(key or "").strip(), str(version or "").strip())

    def register(
        self,
        *,
        identity: AlgorithmIdentity,
        lifecycle_state: AlgorithmLifecycleState,
        adapter: StudyAlgorithmAdapter | None,
        artifacts: AlgorithmArtifactSupport | None = None,
    ) -> None:
        registry_key = self._key(identity.key, identity.version)
        if not all(registry_key):
            raise ValueError("Study Algorithm key and version must be non-empty.")
        if registry_key in self._registrations:
            raise ValueError(
                f"Study Algorithm '{identity.key}' version '{identity.version}' "
                "is already registered."
            )
        if adapter is not None and adapter.identity != identity:
            raise ValueError("Study Algorithm adapter identity does not match registration.")
        if lifecycle_state is not AlgorithmLifecycleState.RETIRED and adapter is None:
            raise ValueError("A supported Study Algorithm requires an executable adapter.")

        support = AlgorithmSupport(
            identity=identity,
            lifecycle_state=lifecycle_state,
            artifacts=artifacts or AlgorithmArtifactSupport(),
            server_executable=(
                adapter is not None
                and lifecycle_state is not AlgorithmLifecycleState.RETIRED
            ),
        )
        self._registrations[registry_key] = _AlgorithmRegistration(
            support=support,
            adapter=adapter,
        )

    def support(self, key: str, version: str) -> AlgorithmSupport | None:
        registration = self._registrations.get(self._key(key, version))
        return registration.support if registration is not None else None

    def register_switch_initializer(
        self, initializer: StudyAlgorithmSwitchInitializer
    ) -> None:
        identity = initializer.identity
        registry_key = self._key(identity.key, identity.version)
        registration = self._registrations.get(registry_key)
        if registration is None or registration.support.identity != identity:
            raise ValueError(
                "Switch initializer requires an exact registered Algorithm identity."
            )
        if registration.switch_initializer is not None:
            raise ValueError(
                "A switch initializer is already registered for this Algorithm."
            )
        if not callable(getattr(initializer, "initialize", None)):
            raise ValueError("Switch initializer must provide an initialize method.")
        if not callable(getattr(initializer, "decode_config", None)):
            raise ValueError("Switch initializer must provide a config decoder.")
        if not callable(getattr(initializer, "decode_history_fact", None)):
            raise ValueError("Switch initializer must provide a history decoder.")
        if initializer.history_schema_version != HISTORY_SCHEMA_VERSION:
            raise ValueError(
                "Switch initializer requires an exact history schema version."
            )
        if (
            registration.support.lifecycle_state is not AlgorithmLifecycleState.ACTIVE
            or registration.adapter is None
        ):
            raise ValueError(
                "Only an active executable Algorithm can receive a switch initializer."
            )
        if not all(
            (
                registration.support.artifacts.state_decoder,
                registration.support.artifacts.config_decoder,
                registration.support.artifacts.event_history_decoder,
            )
        ):
            raise ValueError(
                "Switch initializer requires state, config and history decoders."
            )
        codec = str(initializer.state_storage_codec or "").strip()
        if not codec or not self._state_decoders.has_decoder(
            (identity.key, identity.version, identity.state_schema_version, codec)
        ):
            raise ValueError(
                "Switch initializer requires an exact registered state decoder."
            )
        self._registrations[registry_key] = replace(
            registration,
            support=replace(registration.support, switch_initializer_registered=True),
            switch_initializer=initializer,
        )

    def resolve_switch_target(self, key: str, version: str) -> StudyAlgorithmSwitchTarget:
        adapter = self.resolve(
            key, version, purpose=AlgorithmResolutionPurpose.SWITCH_TARGET
        )
        registration = self._registrations[self._key(key, version)]
        initializer = registration.switch_initializer
        if initializer is None:  # pragma: no cover - guarded by switch_target_allowed
            raise StudyAlgorithmNotFoundError(
                key,
                version,
                purpose=AlgorithmResolutionPurpose.SWITCH_TARGET,
                reason="INITIALIZER_UNAVAILABLE",
            )
        return StudyAlgorithmSwitchTarget(adapter=adapter, initializer=initializer)

    def list_support(self) -> tuple[AlgorithmSupport, ...]:
        return tuple(
            registration.support
            for _, registration in sorted(self._registrations.items())
        )

    def resolve(
        self,
        key: str,
        version: str,
        *,
        purpose: AlgorithmResolutionPurpose = AlgorithmResolutionPurpose.EXISTING_LEASE,
    ) -> StudyAlgorithmAdapter:
        normalized_key, normalized_version = self._key(key, version)
        registration = self._registrations.get((normalized_key, normalized_version))
        if registration is None:
            raise StudyAlgorithmNotFoundError(
                normalized_key,
                normalized_version,
                purpose=purpose,
            )
        support = registration.support
        if not support.allows(purpose) or registration.adapter is None:
            if support.lifecycle_state is AlgorithmLifecycleState.RETIRED:
                reason = "RETIRED"
            elif (
                purpose is AlgorithmResolutionPurpose.SWITCH_TARGET
                and support.lifecycle_state is AlgorithmLifecycleState.ACTIVE
                and not support.switch_initializer_registered
            ):
                reason = "INITIALIZER_UNAVAILABLE"
            else:
                reason = "PURPOSE_NOT_SUPPORTED"
            raise StudyAlgorithmNotFoundError(
                normalized_key,
                normalized_version,
                purpose=purpose,
                lifecycle_state=support.lifecycle_state,
                reason=reason,
            )
        return registration.adapter


_ALGORITHM_REGISTRY = StudyAlgorithmRegistry()

# Compatibility view for callers that still inspect executable adapters
# directly. Retired history-only descriptors stay outside it.
_REGISTRY: dict[tuple[str, str], StudyAlgorithmAdapter] = {}


def register_study_algorithm(
    adapter: StudyAlgorithmAdapter,
    *,
    lifecycle_state: AlgorithmLifecycleState = AlgorithmLifecycleState.ACTIVE,
    artifacts: AlgorithmArtifactSupport | None = None,
) -> None:
    identity = adapter.identity
    _ALGORITHM_REGISTRY.register(
        identity=identity,
        lifecycle_state=lifecycle_state,
        adapter=adapter,
        artifacts=artifacts,
    )
    if lifecycle_state is not AlgorithmLifecycleState.RETIRED:
        _REGISTRY[(str(identity.key), str(identity.version))] = adapter


def register_retired_study_algorithm(
    identity: AlgorithmIdentity,
    *,
    artifacts: AlgorithmArtifactSupport | None = None,
) -> None:
    """Register retained history/decoder metadata after executable removal."""

    _ALGORITHM_REGISTRY.register(
        identity=identity,
        lifecycle_state=AlgorithmLifecycleState.RETIRED,
        adapter=None,
        artifacts=artifacts,
    )


def resolve_study_algorithm(
    key: str,
    version: str,
    *,
    purpose: AlgorithmResolutionPurpose = AlgorithmResolutionPurpose.EXISTING_LEASE,
) -> StudyAlgorithmAdapter:
    return _ALGORITHM_REGISTRY.resolve(key, version, purpose=purpose)


def register_study_algorithm_switch_initializer(
    initializer: StudyAlgorithmSwitchInitializer,
) -> None:
    """Register an exact target initializer; no production target is enabled yet."""

    _ALGORITHM_REGISTRY.register_switch_initializer(initializer)


def resolve_study_algorithm_switch_target(
    key: str, version: str
) -> StudyAlgorithmSwitchTarget:
    """Resolve only targets with executable and exact decoder/initializer support."""

    return _ALGORITHM_REGISTRY.resolve_switch_target(key, version)


def get_study_algorithm_support(key: str, version: str) -> AlgorithmSupport | None:
    return _ALGORITHM_REGISTRY.support(key, version)


def list_study_algorithm_support() -> tuple[dict[str, object], ...]:
    """Return deterministic, serialization-safe support introspection."""

    return tuple(item.as_dict() for item in _ALGORITHM_REGISTRY.list_support())


LEGACY_ANKI_ALGORITHM = LegacyAnkiAlgorithmAdapter()
register_study_algorithm(LEGACY_ANKI_ALGORITHM)
DEFAULT_ALGORITHM_IDENTITY = LEGACY_ANKI_ALGORITHM.identity

# A deprecated version may be issued only when explicitly pinned during its
# drain window. The implicit default must remain active.
_default_support = _ALGORITHM_REGISTRY.support(
    DEFAULT_ALGORITHM_IDENTITY.key,
    DEFAULT_ALGORITHM_IDENTITY.version,
)
if (
    _default_support is None
    or _default_support.lifecycle_state is not AlgorithmLifecycleState.ACTIVE
):
    raise RuntimeError("The default Study Algorithm must be active.")
_ALGORITHM_REGISTRY.resolve(
    DEFAULT_ALGORITHM_IDENTITY.key,
    DEFAULT_ALGORITHM_IDENTITY.version,
    purpose=AlgorithmResolutionPurpose.NEW_SESSION,
)
