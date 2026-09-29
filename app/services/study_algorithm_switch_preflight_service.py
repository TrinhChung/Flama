"""Fail-closed, read-only preflight for a future Algorithm switch command.

This does not invoke an initializer, mutate current state, write a receipt, or
authorize forward-only state. A future switch command must retain the same
transaction/locks and prove idempotency plus lossless legacy projection.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
)
from app.services.study_algorithm_history_cut_service import (
    FrozenStudyAlgorithmHistoryCut,
    freeze_study_algorithm_history_cut,
)
from app.services.study_algorithm_registry import (
    StudyAlgorithmSwitchTarget,
    resolve_study_algorithm_switch_target,
)
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation


class StudyAlgorithmSwitchPreflightError(ValueError):
    def __init__(
        self, code: str, message: str, *, blockers: tuple[str, ...] = ()
    ) -> None:
        super().__init__(message)
        self.code = code
        self.blockers = blockers


@dataclass(frozen=True)
class StudyAlgorithmSwitchPreflight:
    target: StudyAlgorithmSwitchTarget
    history_cut: FrozenStudyAlgorithmHistoryCut


def preflight_study_algorithm_switch(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    expected: StudyAuthorityCASExpectation,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
    target_key: str,
    target_version: str,
) -> StudyAlgorithmSwitchPreflight:
    """Resolve a fresh history cut and exact target under the caller's CAS locks."""

    history_cut = freeze_study_algorithm_history_cut(
        session,
        route=route,
        locked=locked,
        expected=expected,
        siblings=siblings,
        compatibility=compatibility,
    )
    if not history_cut.native_complete:
        raise StudyAlgorithmSwitchPreflightError(
            "INCOMPLETE_ALGORITHM_HISTORY",
            "Algorithm switch history is incomplete or its lineage is unproven.",
            blockers=history_cut.blocker_codes,
        )
    if history_cut.facts:
        # A contiguous native hash chain does not reconstruct the first state
        # or every historical scheduler config. No target-specific policy has
        # been approved to consume this evidence yet.
        raise StudyAlgorithmSwitchPreflightError(
            "ALGORITHM_HISTORY_POLICY_UNAPPROVED",
            "Reviewed Note history lacks an approved baseline/config policy.",
            blockers=("FIRST_STATE_BASELINE_UNPROVEN", "HISTORICAL_CONFIG_UNPROVEN"),
        )
    if locked.state is None:  # pragma: no cover - cut is incomplete without state
        raise StudyAlgorithmSwitchPreflightError(
            "AUTHORITY_STATE_REQUIRED", "Algorithm switch requires current state."
        )
    if (
        str(locked.state.algorithm_key) == str(target_key).strip()
        and str(locked.state.algorithm_version) == str(target_version).strip()
    ):
        raise StudyAlgorithmSwitchPreflightError(
            "ALGORITHM_ALREADY_ACTIVE",
            "Requested Algorithm identity is already current for this Note.",
        )
    target = resolve_study_algorithm_switch_target(target_key, target_version)
    return StudyAlgorithmSwitchPreflight(target=target, history_cut=history_cut)
