"""Small fixtures for independent Templates and explicit NOTE attachments."""

from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template


def dashboard_totals(payload):
    """New/learning/due over the dashboard's root decks (each carries its subtree)."""
    roots = payload["items"]
    return {
        "new": sum(row["new_count"] for row in roots),
        "learning": sum(row["learn_count"] for row in roots),
        "due": sum(row["due_count"] for row in roots),
    }


def enroll_note_user(session, user):
    """Explicit signup fixture; never infer state for an old unenrolled user."""
    from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
    return enroll_new_learner_note_authority(session, user=user)


def create_note_user(session, **values):
    """Stage a new NOTE learner before staging any owned content; never commit."""
    from models.user import User

    user = User(**values)
    session.add(user)
    session.flush()
    enroll_note_user(session, user)
    return user


def mapper_state_input(**changes):
    """Pure scheduler-state input for codec fixtures, never an ORM entity."""
    from datetime import datetime
    from types import SimpleNamespace
    now = datetime(2026, 9, 21, 8)
    values = dict(id=1, user_id=1, card_id="fixture-state", queue="new", step_index=0,
        due_at=None, due_day=None, interval_days=0, interval_days_raw=None,
        is_suspended=False, is_buried=False, buried_until_day=None, review_kind="review",
        scheduler_mode="legacy", ease_factor=2.5, memory_stability=None, memory_difficulty=None,
        suspension_reason=None, last_leech_at=None, last_leech_lapses=0, last_review_event_id=None,
        reps=0, lapses=0, last_reviewed_at=None, revision=0, created_at=now, updated_at=now)
    values.update(changes)
    return SimpleNamespace(**values)


def assert_retired_progress_absent(test, session):
    """Assert structural retirement instead of querying a deleted table."""
    import sqlalchemy as sa
    from models import db
    test.assertNotIn("card_progress", db.metadata.tables)
    test.assertFalse(sa.inspect(session.get_bind()).has_table("card_progress"))


def archive_wire_alias(session, card, wire_id):
    """Stage immutable pre-cutover evidence using Core, preserving old wire ID."""
    import sqlalchemy as sa
    from models.card import PresentationAlias
    session.connection().execute(sa.insert(PresentationAlias.__table__).values(
        id=wire_id, note_id=card.note_id, template_id=card.template_id,
        application_id=card.application_id, created_at=card.created_at, updated_at=card.updated_at,
    ))


def attach_template(session, *, note_type_id, owner_user_id, occurrence_key=COMPAT_OCCURRENCE_KEY,
                    application_id=None, **template_values):
    """Create a definition and its application; return the definition.

    This is fixture persistence, not a runtime compatibility constructor.
    No NoteType origin lives on Template and no per-Note Card is inserted.
    """

    template = Template(owner_user_id=owner_user_id, **template_values)
    session.add(template)
    session.flush()
    application = StudyApplication(note_type_id=note_type_id, template_id=template.id,
        occurrence_key=occurrence_key, source_ord=template.position,
        position=template.position, is_default=template.is_default, status_code='ACTIVE')
    if application_id is not None:
        application.id = application_id
    session.add(application)
    session.flush()
    return template
