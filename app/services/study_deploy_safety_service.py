"""Conservative, read-only guard for code rollback after writers are stopped."""

from sqlalchemy import select

from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session_batch import StudySessionBatch


def inspect_study_code_rollback(*, writers_quiesced: bool = False) -> dict:
    """Do not confuse code rollback with the explicit NOTE -> LEGACY command.

    The deploy runner must first stop HTTP/Connect writers and wait for their
    requests to finish. A continuous worker may drain existing admissions. Any
    NOTE enrollment or unfinished/unknown batch status blocks automatic code
    rollback, even if an older release happens to contain a worker binary.
    """
    result = {"schema_version": "study-code-rollback-check.v1", "status": "BLOCK", "reasons": []}
    if not writers_quiesced:
        return {**result, "reasons": ["WRITERS_NOT_QUIESCED"]}
    if db.session().in_transaction():
        raise RuntimeError("Code rollback inspection requires a transaction-neutral session.")
    try:
        unfinished = db.session.execute(select(StudySessionBatch.id).where(
            StudySessionBatch.status.notin_(("completed", "failed")),
        ).limit(1)).first() is not None
        note_enrollment = db.session.execute(select(StudyAuthorityEnrollment.learner_user_id).where(
            StudyAuthorityEnrollment.mode_code != "LEGACY",
        ).limit(1)).first() is not None
        if unfinished:
            result["reasons"].append("UNFINISHED_STUDY_BATCHES")
        if note_enrollment:
            result["reasons"].append("NOTE_AUTHORITY_REQUIRES_EXPLICIT_ROLLBACK")
        if not result["reasons"]:
            result["status"] = "PASS"
        return result
    except Exception:
        # Neither stale schema nor an unreachable DB proves rollback safety.
        # Driver messages may contain credentials/SQL; do not return them.
        return {**result, "reasons": ["STUDY_CODE_ROLLBACK_UNVERIFIED"]}
    finally:
        db.session.rollback()
