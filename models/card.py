from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str
# Registered with the mapper before Card's relationship is configured.
from models.study_application import StudyApplication  # noqa: F401


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    # Phase 6 application occurrence this Card presents. Nullable only until
    # every Card creation path sets it; migration 46 backfills existing Cards.
    application_id = db.Column(
        db.String(36),
        db.ForeignKey("study_applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note = db.relationship("Note", back_populates="cards")
    template = db.relationship("Template", back_populates="cards")
    application = db.relationship("StudyApplication", back_populates="cards")
    progress_rows = db.relationship("CardProgress", back_populates="card", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("note_id", "template_id", name="uq_cards_note_template"),
        UniqueConstraint("note_id", "application_id", name="uq_cards_note_application"),
    )
