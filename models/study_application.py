"""NoteType-scoped application occurrence of a presentation definition (Phase 6).

An application is where one definition (today a ``Template``) is applied to a
NoteType. A ``Card`` is that occurrence's presentation of one Note, derived and
never stored (ADR P11); learner progress stays on the learner/Note subject, so
applying the same Template twice adds an occurrence, never a second progress.

Attachments are created explicitly; independent Templates have no occurrence.
A compatibility occurrence (``occurrence_key = 'compat'``) retains the Phase 3 form
``comp:notetype:{note_type_id}:template:{template_id}`` for old Cards and
sessions. ``source_ord`` binds an imported Anki card ordinal to the occurrence
so a later Template reorder cannot retarget it.
"""

from datetime import datetime

from sqlalchemy import delete, event
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
    note_type = db.relationship("NoteType", back_populates="study_applications")
    cards = db.relationship(
        "Card", primaryjoin="foreign(Card.application_id) == StudyApplication.id", viewonly=True
    )

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



@event.listens_for(Session, "before_flush")
def _remove_template_applications(session: Session, _flush_context, _instances) -> None:
    """Match MySQL template removal cascades in SQLite test harnesses.

    Creation is always explicit through attachment services; a Template by
    itself never creates an application or any per-Note presentation row.
    """
    from models.template import Template
    removed = sorted(str(row.id) for row in session.deleted if isinstance(row, Template) and row.id)
    if removed:
        with session.no_autoflush:
            session.execute(delete(StudyApplication).where(StudyApplication.template_id.in_(removed))
                            .execution_options(synchronize_session=False))
