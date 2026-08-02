from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db


class ConnectNoteRef(db.Model):
    __tablename__ = "connect_note_refs"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    note_id = db.Column(
        db.String(36),
        db.ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False, default="yomitan")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    note = db.relationship("Note", foreign_keys=[note_id])
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "note_id", "provider", name="uq_connect_note_refs_user_note_provider"),
    )
