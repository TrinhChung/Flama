"""Sparse author changes to one already-published Note.

Values use ``identity -> {op: set, value: ...} / {op: remove}`` envelopes.
JSON null remains a value and never means deletion. Retained undeclared labels
use the existing ``extra:<hash>`` identity and carry their original ``label``.
"""
from datetime import datetime

from models import db


class NoteDraft(db.Model):
    __tablename__ = "note_drafts"

    note_id = db.Column(
        db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True,
    )
    field_values_by_id = db.Column(db.JSON, nullable=False, default=dict)
    tags = db.Column(db.JSON, nullable=True)
    # Validated by the author service. A FK here would require an unapproved
    # secondary index; the table deliberately has only its note_id primary key.
    deck_id = db.Column(db.Integer, nullable=True)
    op = db.Column(db.String(16), nullable=False, default="edit", server_default="edit")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note = db.relationship("Note", foreign_keys=[note_id])
