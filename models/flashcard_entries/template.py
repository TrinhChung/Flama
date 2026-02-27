from datetime import datetime

from models import db
from models.flashcard_entries.common import uuid_str


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    front_html = db.Column(db.Text, nullable=False, default="")
    back_html = db.Column(db.Text, nullable=False, default="")
    shared_css = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="templates")
    cards = db.relationship("Card", back_populates="template")

