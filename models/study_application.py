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

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from models import db
from models.model_uuid import uuid_str

COMPAT_OCCURRENCE_KEY = "compat"
APPLICATION_STATUSES = ("ACTIVE",)


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
            "template_id",
            "occurrence_key",
            name="uq_study_applications_template_occurrence",
        ),
        db.Index(
            "ix_study_applications_note_type_ord",
            "note_type_id",
            "source_ord",
        ),
        db.CheckConstraint(
            "status_code IN ('ACTIVE')",
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


def _new_compat_application(template) -> StudyApplication:
    application = StudyApplication(
        occurrence_key=COMPAT_OCCURRENCE_KEY,
        source_ord=template.position if template.position is not None else 0,
        status_code="ACTIVE",
    )
    # Relationships, not IDs: a Template or NoteType added in this same flush
    # has no primary key yet.
    application.template = template
    if template.note_type_id is not None:
        application.note_type_id = template.note_type_id
    else:
        application.note_type = template.note_type
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

    pending = list(session.new)
    new_templates = [item for item in pending if isinstance(item, Template)]
    new_cards = [
        item
        for item in pending
        if isinstance(item, Card) and item.application_id is None and item.application is None
    ]
    if not new_templates and not new_cards:
        return
    by_template: dict[int, StudyApplication] = {}
    for item in pending:
        if isinstance(item, StudyApplication) and item.occurrence_key == COMPAT_OCCURRENCE_KEY:
            template = item.__dict__.get("template")
            if template is not None:
                by_template[id(template)] = item
    with session.no_autoflush:
        for template in new_templates:
            if id(template) not in by_template:
                application = _new_compat_application(template)
                session.add(application)
                by_template[id(template)] = application
        for card in new_cards:
            template = _template_of(session, card)
            if template is None:
                continue  # the Card's own foreign key rejects it
            application = by_template.get(id(template))
            if application is None and template.id is not None:
                application = session.execute(
                    select(StudyApplication).where(
                        StudyApplication.template_id == template.id,
                        StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY,
                    )
                ).scalar_one_or_none()
            if application is None:
                application = _new_compat_application(template)
                session.add(application)
            by_template[id(template)] = application
            card.application = application
