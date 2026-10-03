"""Result of one NOTE evidence step on the consolidated progress row (ADR P10).

Availability, provenance and history completeness are written onto the
subject row by ``study_consolidated_progress_service``; this module only
keeps the result shape receipts and callers read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class StudyAuthorityEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class StudyAuthorityEvidenceResult:
    mirror_revision: int
    subject_status: str
    contributor_count: int
    authority_vector_hash: bytes
    lineage_vector_hash: bytes
    # Cards carry no progress (ADR P10 §2.3): always empty.
    contributor_by_card_id: Mapping[str, object]
