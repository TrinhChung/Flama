"""Queries for personal definitions and active NoteType applications."""

from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import defer, joinedload, undefer
from models.card import Card
from models.note import Note
from models.note_type import NoteType
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template


def owner_filter(user_id):
    return or_(Template.owner_user_id == int(user_id), and_(Template.owner_user_id.is_(None), Template.note_type.has(NoteType.user_id == int(user_id))))


def _library_statement(user_id, *, include_archived=False, category=None, search=None, group="all"):
    statement = select(Template).where(owner_filter(user_id))
    if not include_archived:
        statement = statement.where(Template.archived_at.is_(None))
    if category:
        statement = statement.where(Template.primary_category == category)
    if search:
        # Literal substring, including percent/underscore.
        statement = statement.where(Template.name.contains(search, autoescape=True))
    active_usage = select(StudyApplication.id).join(NoteType).where(
        StudyApplication.template_id == Template.id,
        StudyApplication.status_code == "ACTIVE", NoteType.user_id == int(user_id),
    ).exists()
    if group == "mine":
        statement = statement.where(Template.origin != "market_copy")
    elif group == "market":
        statement = statement.where(Template.origin == "market_copy")
    elif group == "standalone":
        statement = statement.where(~active_usage)
    elif group == "in_use":
        statement = statement.where(active_usage)
    return statement


def library_query(session, user_id, *, include_archived=False, category=None, search=None, group="all", compact=False, page=None, page_size=24):
    statement = _library_statement(user_id, include_archived=include_archived, category=category, search=search, group=group)
    total = None
    if page is not None:
        total = session.scalar(select(func.count()).select_from(statement.subquery()))
        statement = statement.offset((page - 1) * page_size).limit(page_size)
    statement = statement.options(joinedload(Template.note_type).selectinload(NoteType.field_defs))
    if compact:
        statement = statement.options(defer(Template.front_html), defer(Template.back_html), defer(Template.shared_css))
    items = session.execute(statement.order_by(Template.name, Template.id)).scalars().all()
    if compact:
        # Old definitions infer their inputs from source. Batch that compatibility
        # read for this page rather than triggering a deferred query per item.
        legacy_ids = [item.id for item in items if not item.input_schema]
        if legacy_ids:
            session.execute(select(Template).where(Template.id.in_(legacy_ids)).options(
                undefer(Template.front_html), undefer(Template.back_html),
                defer(Template.shared_css),
            )).scalars().all()
    return items, total


def template_usage(session, user_id, template_ids):
    """Load visible active usages once for an entire library page."""
    if not template_ids:
        return {}
    rows = session.execute(select(StudyApplication, NoteType.name).join(NoteType).where(
        StudyApplication.template_id.in_(template_ids),
        StudyApplication.status_code == "ACTIVE", NoteType.user_id == int(user_id),
    ).order_by(NoteType.name, StudyApplication.position, StudyApplication.id))
    result = {}
    for application, note_type_name in rows:
        result.setdefault(application.template_id, []).append({
            "id": application.id, "application_id": application.id,
            "note_type_id": application.note_type_id, "note_type_name": note_type_name,
            "occurrence_key": application.occurrence_key, "display_name": application.display_name,
            "position": application.position, "is_default": bool(application.is_default),
        })
    return result


def applications(session, note_type_id, *, include_retired=False):
    statement = select(StudyApplication).where(StudyApplication.note_type_id == str(note_type_id))
    if not include_retired:
        statement = statement.where(StudyApplication.status_code == "ACTIVE")
    return session.execute(statement.options(joinedload(StudyApplication.template)).order_by(StudyApplication.position, StudyApplication.id)).scalars().all()


def active_card_condition():
    # Legacy pre-cutover rows retain their old visibility until attributed.
    return or_(Card.application_id.is_(None), Card.application.has(StudyApplication.status_code == "ACTIVE"))


def legacy_fallback_templates(session, note_type_id):
    """Pre-attachment definitions of this NoteType that never had an occurrence."""
    note_type_id = str(note_type_id)
    return session.execute(select(Template).where(
        Template.note_type_id == note_type_id,
        ~select(StudyApplication.id).where(StudyApplication.template_id == Template.id, StudyApplication.note_type_id == note_type_id).exists(),
    ).order_by(Template.position, Template.id)).scalars().all()


def card_slots(session, note_type_id, *, rows=None):
    """(template_id, application_id) per Card a new Note receives.

    ACTIVE occurrences decide membership, wherever the definition originated.
    Only a NoteType without any active occurrence falls back to old templates
    that never had one; a fully retired NoteType intentionally stays empty.
    """
    rows = applications(session, note_type_id) if rows is None else [row for row in rows if row.status_code == "ACTIVE"]
    if rows:
        return [(row.template_id, row.id) for row in rows]
    return [(row.id, None) for row in legacy_fallback_templates(session, note_type_id)]


def build_cards(note_ids, slots):
    """New Cards for Notes without any; a ``None`` application uses the compat seam."""
    from models.model_uuid import uuid_str
    return [Card(id=uuid_str(), note_id=note_id, template_id=template_id, application_id=application_id)
            for note_id in note_ids for template_id, application_id in slots]


def create_cards_for_note(session, note):
    """Materialize all active occurrences without creating learner progress."""
    existing = session.execute(select(Card.template_id, Card.application_id).where(Card.note_id == note.id)).all()
    applied = {application_id for _template_id, application_id in existing if application_id}
    templated = {template_id for template_id, _application_id in existing}
    slots = [(template_id, application_id) for template_id, application_id in card_slots(session, note.note_type_id)
             if (application_id not in applied if application_id else template_id not in templated)]
    session.add_all(build_cards([note.id], slots))


@dataclass(frozen=True)
class NoteCardPlan:
    missing: tuple
    removable: tuple
    has_slots: bool


def plan_note_cards(session, note_type_id, cards):
    """Reconcile an existing Note's Cards with its NoteType's occurrences.

    A Card is removable only when its occurrence (or, for an unattributed
    legacy Card, its definition) is not this NoteType's, for example after a
    NoteType change. Cards of retired occurrences stay with their progress.
    """
    note_type_id = str(note_type_id)
    rows = applications(session, note_type_id, include_retired=True)
    application_ids = {row.id for row in rows}
    compat = {row.template_id: row.id for row in rows if row.occurrence_key == COMPAT_OCCURRENCE_KEY}
    known_templates = {row.template_id for row in rows} | set(
        session.execute(select(Template.id).where(Template.note_type_id == note_type_id)).scalars())
    removable, applied, templated = [], set(), set()
    for card in cards:
        application_id = card.application_id or getattr(card.application, "id", None)
        if application_id is None:
            if card.template_id not in known_templates:
                removable.append(card)
                continue
            application_id = compat.get(card.template_id)
        elif application_id not in application_ids:
            removable.append(card)
            continue
        if application_id is not None:
            applied.add(application_id)
        templated.add(card.template_id)
    slots = card_slots(session, note_type_id, rows=rows)
    missing = tuple((template_id, application_id) for template_id, application_id in slots
                    if (application_id not in applied if application_id else template_id not in templated))
    return NoteCardPlan(missing=missing, removable=tuple(removable), has_slots=bool(slots))


def template_used_outside(session, template_id, note_type_id):
    """Whether removing a definition from one NoteType would touch another's Cards."""
    note_type_id = str(note_type_id)
    if session.execute(select(StudyApplication.id).where(
        StudyApplication.template_id == template_id, StudyApplication.note_type_id != note_type_id,
    ).limit(1)).first() is not None:
        return True
    return session.execute(select(Card.id).join(Note, Note.id == Card.note_id).where(
        Card.template_id == template_id, Note.note_type_id != note_type_id,
    ).limit(1)).first() is not None


def detach_template(session, note_type_id, template):
    """Retire this NoteType's occurrences; definition, Cards and progress stay."""
    note_type_id = str(note_type_id)
    rows = session.execute(select(StudyApplication).where(
        StudyApplication.note_type_id == note_type_id, StudyApplication.template_id == template.id,
    ).order_by(StudyApplication.id).with_for_update()).scalars().all()
    if not rows:
        # A never-attached legacy definition needs an explicit retired marker,
        # otherwise the compatibility fallback would keep presenting it.
        rows = [StudyApplication(note_type_id=note_type_id, template_id=template.id, occurrence_key=COMPAT_OCCURRENCE_KEY,
                                 source_ord=template.position or 0, position=template.position or 0, status_code="RETIRED")]
        session.add(rows[0])
    for row in rows:
        row.status_code = "RETIRED"
    return rows
