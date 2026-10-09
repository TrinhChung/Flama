"""NoteType-scoped application occurrence of a presentation definition (Phase 6).

An application is where one definition (today a ``Template``) is applied to a
NoteType. A ``Card`` is that occurrence's presentation instance for one Note;
learner progress stays on the learner/Note subject, so applying the same
Template twice creates a second occurrence and Cards, never a second progress.

Every Template has one compatibility occurrence (``occurrence_key = 'compat'``)
whose composition identity keeps the Phase 3 form
``comp:notetype:{note_type_id}:template:{template_id}`` for old Cards and
sessions. ``source_ord`` binds an imported Anki card ordinal to the occurrence
so a later Template reorder cannot retarget it.
"""

from datetime import datetime

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from models import db
from models.model_uuid import uuid_str

COMPAT_OCCURRENCE_KEY = "compat"
APPLICATION_STATUSES = ("ACTIVE", "RETIRED")


class StudyApplication(db.Model):
    __tablename__ = "study_applications"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id = db.Column(
        db.String(36),
        db.ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurrence_key = db.Column(db.String(64), nullable=False)
    source_ord = db.Column(db.Integer, nullable=True)
    input_bindings = db.Column(db.JSON, nullable=True)
    display_name = db.Column(db.String(255), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_default = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    status_code = db.Column(db.String(16), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    template = db.relationship("Template")
    note_type = db.relationship("NoteType")
    cards = db.relationship("Card", back_populates="application")

    __table_args__ = (
        db.UniqueConstraint(
            "note_type_id",
            "template_id",
            "occurrence_key",
            name="uq_study_applications_note_type_template_occurrence",
        ),
        db.Index(
            "ix_study_applications_note_type_ord",
            "note_type_id",
            "source_ord",
        ),
        db.CheckConstraint(
            "status_code IN ('ACTIVE', 'RETIRED')",
            name="ck_study_applications_status",
        ),
    )


def _template_of(session: Session, card):
    from models.template import Template

    template = card.__dict__.get("template")
    if template is not None:
        return template
    for pending in session.new:
        if isinstance(pending, Template) and pending.id == card.template_id:
            return pending
    if card.template_id is None:
        return None
    return session.get(Template, card.template_id)


def _note_of(session: Session, card):
    from models.note import Note

    note = card.__dict__.get("note")
    if note is not None:
        return note
    for pending in session.new:
        if isinstance(pending, Note) and pending.id == card.note_id:
            return pending
    return session.get(Note, card.note_id) if card.note_id is not None else None


def _note_type_of(template, note=None):
    if note is not None:
        return note.__dict__.get("note_type"), note.note_type_id
    return template.__dict__.get("note_type"), template.note_type_id


def _scope_key(template, note_type, note_type_id):
    return id(template), (str(note_type_id) if note_type_id is not None else id(note_type))


def _new_compat_application(template, *, note_type=None, note_type_id=None) -> StudyApplication:
    application = StudyApplication(
        occurrence_key=COMPAT_OCCURRENCE_KEY,
        source_ord=template.position if template.position is not None else 0,
        status_code="ACTIVE",
        position=template.position if template.position is not None else 0,
        is_default=bool(template.is_default),
    )
    # Relationships, not IDs: a Template or NoteType added in this same flush
    # has no primary key yet.
    application.template = template
    if note_type_id is not None:
        application.note_type_id = note_type_id
    else:
        application.note_type = note_type
    return application


@event.listens_for(Session, "before_flush")
def _assign_compat_applications(session: Session, _flush_context, _instances) -> None:
    """The single Card-creation seam: every Template and Card has an occurrence.

    A new Template gets its compatibility occurrence (``source_ord`` = its
    ``position``) in the same flush, so no later request races to create it.
    A new Card without an explicit ``application`` (every current creation
    path: REST, MCP, Connect, CSV, sharing, seed, NOTE sibling expansion) is
    bound to its Template's compatibility occurrence. A caller that applies a
    Template again sets ``application`` itself.
    """

    from models.card import Card
    from models.template import Template

    removed_template_ids = sorted(
        str(item.id)
        for item in session.deleted
        if isinstance(item, Template) and item.id is not None
    )
    if removed_template_ids:
        # The occurrence goes with its Template (the FK cascades on MySQL;
        # this also holds where foreign keys are not enforced).
        with session.no_autoflush:
            session.execute(
                delete(StudyApplication)
                .where(StudyApplication.template_id.in_(removed_template_ids))
                .execution_options(synchronize_session=False)
            )

    pending = list(session.new)
    new_templates = [item for item in pending if isinstance(item, Template)]
    new_cards = [
        item
        for item in pending
        if isinstance(item, Card) and item.application_id is None and item.application is None
    ]
    if not new_templates and not new_cards:
        return
    by_template: dict[tuple, StudyApplication] = {}
    for item in pending:
        if isinstance(item, StudyApplication) and item.occurrence_key == COMPAT_OCCURRENCE_KEY:
            template = item.__dict__.get("template")
            if template is not None:
                by_template[_scope_key(template, item.__dict__.get("note_type"), item.note_type_id)] = item
    with session.no_autoflush:
        for template in new_templates:
            note_type, note_type_id = _note_type_of(template)
            if note_type is None and note_type_id is None:
                continue  # An independent library Template has no occurrence.
            key = _scope_key(template, note_type, note_type_id)
            if key not in by_template:
                application = _new_compat_application(template, note_type=note_type, note_type_id=note_type_id)
                session.add(application)
                by_template[key] = application
        for card in new_cards:
            template = _template_of(session, card)
            if template is None:
                continue  # the Card's own foreign key rejects it
            note = _note_of(session, card)
            note_type, note_type_id = _note_type_of(template, note)
            if note_type is None and note_type_id is None:
                continue  # The Card's Note/attachment validation rejects this.
            key = _scope_key(template, note_type, note_type_id)
            application = by_template.get(key)
            if application is None and template.id is not None and note_type_id is not None:
                application = session.execute(
                    select(StudyApplication).where(
                        StudyApplication.template_id == template.id,
                        StudyApplication.note_type_id == note_type_id,
                        StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY,
                    )
                ).scalar_one_or_none()
            if application is None:
                application = _new_compat_application(template, note_type=note_type, note_type_id=note_type_id)
                session.add(application)
            by_template[key] = application
            card.application = application
