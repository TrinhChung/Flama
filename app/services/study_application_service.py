"""Stage a repeated application of a Template to its NoteType (Phase 6, D6-09).

A repeated application is a new occurrence of an existing Template with its
own Cards. Learner progress stays on the Note: the new Cards join each Note's
sibling vector through the same NOTE expansion that adds a Template, so every
enrolled learner's state is copied to them and answering either occurrence
schedules the whole Note. The caller owns authorization, learner fences and
commit/rollback; there is no UI for this yet (storage and tests only).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services import study_content_delete_service as content_topology
from models.card import Card
from models.note import Note
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template


def stage_repeated_application(session, *, routes, template: Template, occurrence_key: str,
                               source_ord: int | None = None) -> StudyApplication:
    """Create one more occurrence of ``template`` and its Cards for the owner's Notes."""

    key = str(occurrence_key or "").strip()
    if not key or key == COMPAT_OCCURRENCE_KEY or len(key) > 64:
        raise StudyAuthorityFenceError(
            "INVALID_APPLICATION_OCCURRENCE",
            "A repeated application needs its own occurrence key.",
        )
    note_type = template.note_type
    route = next((row for row in routes if row.learner_user_id == note_type.user_id), None)
    if route is None or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "Repeated applications require the owner on NOTE authority."
        )
    if session.execute(
        select(StudyApplication.id).where(
            StudyApplication.template_id == template.id,
            StudyApplication.occurrence_key == key,
        )
    ).first() is not None:
        raise StudyAuthorityFenceError(
            "APPLICATION_OCCURRENCE_EXISTS", "This Template already has that occurrence."
        )
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    note_ids = tuple(
        str(value)
        for value in session.execute(
            select(Note.id)
            .where(Note.note_type_id == note_type.id, Note.user_id == route.learner_user_id)
            .order_by(Note.id)
            .with_for_update()
        ).scalars()
    )
    expansion = content_topology.prepare_content_expansion(
        session, routes=routes, note_ids=note_ids, now_utc=now
    )
    content_topology.verify_content_expansion_scope(session, routes=routes, note_ids=note_ids)
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
    session.flush()
    cards = [
        Card(note_id=note_id, template_id=template.id, application=application,
             created_at=now, updated_at=now)
        for note_id in note_ids
    ]
    session.add_all(cards)
    session.flush()
    content_topology.finalize_content_expansion(
        expansion, new_cards=cards, now_utc=now, provenance_code="NATIVE_DIRECT"
    )
    return application
