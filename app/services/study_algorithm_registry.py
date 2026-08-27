"""Versioned study Algorithm adapters and runtime dispatch.

The registry is intentionally storage-neutral.  During the compatibility phases
``CardProgress`` remains authoritative; this module only makes the executable
Algorithm identity real instead of treating database labels as comments.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.services.anki_scheduler import (
    Answer,
    CardState,
    DeckOptions,
    applyAnswer,
    computeAnswerPreview,
)


LEGACY_ANKI_ALGORITHM_KEY = "legacy-anki"
LEGACY_ANKI_ALGORITHM_VERSION = "1.0.0"
LEGACY_ANKI_STATE_SCHEMA_VERSION = "anki-card-state.v1"


@dataclass(frozen=True)
class AlgorithmIdentity:
    key: str
    version: str
    state_schema_version: str


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


class StudyAlgorithmNotFoundError(LookupError):
    """Raised when a pinned session references an unavailable executable."""

    def __init__(self, key: str, version: str) -> None:
        super().__init__(f"Study Algorithm '{key}' version '{version}' is unavailable.")
        self.key = key
        self.version = version


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


_REGISTRY: dict[tuple[str, str], StudyAlgorithmAdapter] = {}


def register_study_algorithm(adapter: StudyAlgorithmAdapter) -> None:
    identity = adapter.identity
    registry_key = (str(identity.key), str(identity.version))
    existing = _REGISTRY.get(registry_key)
    if existing is not None and existing is not adapter:
        raise ValueError(
            f"Study Algorithm '{identity.key}' version '{identity.version}' is already registered."
        )
    _REGISTRY[registry_key] = adapter


def resolve_study_algorithm(key: str, version: str) -> StudyAlgorithmAdapter:
    normalized_key = str(key or "").strip()
    normalized_version = str(version or "").strip()
    adapter = _REGISTRY.get((normalized_key, normalized_version))
    if adapter is None:
        raise StudyAlgorithmNotFoundError(normalized_key, normalized_version)
    return adapter


LEGACY_ANKI_ALGORITHM = LegacyAnkiAlgorithmAdapter()
register_study_algorithm(LEGACY_ANKI_ALGORITHM)
DEFAULT_ALGORITHM_IDENTITY = LEGACY_ANKI_ALGORITHM.identity

