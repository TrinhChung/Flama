from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class DeckCloneAddedFieldDef(db.Model):
    __tablename__ = "deck_clone_added_field_defs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(
        db.Enum("text", "richtext", "image", "audio", "diagram", name="deck_clone_field_type_enum", native_enum=False),
        nullable=False,
        default="text",
    )
    position = db.Column(db.Integer, nullable=False, default=0)
    required = db.Column(db.Boolean, nullable=False, default=False)
    properties = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="clone_added_field_defs")
