"""Queries for personal definitions and active NoteType applications."""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload
from models.card import Card
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template


def owner_filter(user_id):
    return or_(Template.owner_user_id == int(user_id), and_(Template.owner_user_id.is_(None), Template.note_type.has(NoteType.user_id == int(user_id))))


def library_query(session, user_id, *, include_archived=False, category=None, search=None):
    statement = select(Template).where(owner_filter(user_id))
    if not include_archived:
        statement = statement.where(Template.archived_at.is_(None))
    if category:
        statement = statement.where(Template.primary_category == category)
    if search:
        # Literal substring, including percent/underscore.
        statement = statement.where(Template.name.contains(search, autoescape=True))
    return session.execute(statement.order_by(Template.name, Template.id)).scalars().all()


def applications(session, note_type_id, *, include_retired=False):
    statement = select(StudyApplication).where(StudyApplication.note_type_id == str(note_type_id))
    if not include_retired:
        statement = statement.where(StudyApplication.status_code == "ACTIVE")
    return session.execute(statement.options(joinedload(StudyApplication.template)).order_by(StudyApplication.position, StudyApplication.id)).scalars().all()


def active_card_condition():
    # Legacy pre-cutover rows retain their old visibility until attributed.
    return or_(Card.application_id.is_(None), Card.application.has(StudyApplication.status_code == "ACTIVE"))


def create_cards_for_note(session, note):
    """Materialize all active occurrences without creating learner progress."""
    from models.model_uuid import uuid_str
    rows = applications(session, note.note_type_id)
    if not rows:
        # Only old templates lacking occurrences use the compatibility seam.
        templates = session.execute(select(Template).where(Template.note_type_id == note.note_type_id, ~Template.cards.any(Card.note_id == note.id), ~select(StudyApplication.id).where(StudyApplication.template_id == Template.id, StudyApplication.note_type_id == note.note_type_id).exists())).scalars()
        for template in templates:
            session.add(Card(id=uuid_str(), note_id=note.id, template_id=template.id))
        return
    existing = set(session.execute(select(Card.application_id).where(Card.note_id == note.id)).scalars())
    for application in rows:
        if application.id not in existing:
            session.add(Card(id=uuid_str(), note_id=note.id, template_id=application.template_id, application_id=application.id))
