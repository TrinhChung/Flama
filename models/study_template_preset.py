"""Personal composition selections and field bindings for one deck."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class StudyTemplatePreset(db.Model):
    __tablename__ = "study_template_presets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    selected_compositions = db.Column(db.JSON, nullable=False, default=list)
    input_bindings = db.Column(db.JSON, nullable=False, default=dict)
    ask_before_study = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "deck_id", name="uq_study_template_presets_user_deck"),
    )
