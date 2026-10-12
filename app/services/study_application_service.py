"""Stage a repeated application of a Template to its NoteType (Phase 6, D6-09).

A repeated application is a new occurrence of an existing Template; its Cards
are derived (ADR P11). Learner progress stays on the Note (ADR P10 §2.3): the
new Cards share each Note's one row, so answering either occurrence schedules
the whole Note and nothing is copied. The caller owns authorization and
commit/rollback; there is no UI for this yet (storage and tests only).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.repositories.study_authority_repository import StudyAuthorityFenceError
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template


def stage_repeated_application(session, *, routes, template: Template, note_type, occurrence_key: str,
                               source_ord: int | None = None) -> StudyApplication:
    """Create one more occurrence of ``template``; its Cards are derived from the Notes."""

    key = str(occurrence_key or "").strip()
    if not key or key == COMPAT_OCCURRENCE_KEY or len(key) > 64:
        raise StudyAuthorityFenceError(
            "INVALID_APPLICATION_OCCURRENCE",
            "A repeated application needs its own occurrence key.",
        )
    route = next((row for row in routes if row.learner_user_id == note_type.user_id), None)
    if route is None or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "Repeated applications require the owner on NOTE authority."
        )
    if session.execute(
        select(StudyApplication.id).where(
            StudyApplication.template_id == template.id,
            StudyApplication.note_type_id == note_type.id,
            StudyApplication.occurrence_key == key,
        )
    ).first() is not None:
        raise StudyAuthorityFenceError(
            "APPLICATION_OCCURRENCE_EXISTS", "This Template already has that occurrence."
        )
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    application = StudyApplication(
        note_type_id=note_type.id,
        template_id=template.id,
        occurrence_key=key,
        source_ord=source_ord,
        status_code="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    session.add(application)
    # The occurrence presents the Template on every Note again (ADR P11).
    session.flush()
    return application
