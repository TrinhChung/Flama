"""An immutable complete NoteType schema and presentation publication."""

from datetime import datetime

from sqlalchemy import event

from models import db
from models.model_uuid import uuid_str


class NoteTypeRelease(db.Model):
    __tablename__ = "note_type_releases"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    version_label = db.Column(db.String(50), nullable=False)
    sequence_no = db.Column(db.BigInteger, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    manifest_json = db.Column(db.JSON, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("note_type_id", "version_label", name="uq_note_type_releases_source_label"),
        db.UniqueConstraint("note_type_id", "sequence_no", name="uq_note_type_releases_source_sequence"),
        db.CheckConstraint("sequence_no > 0", name="ck_note_type_releases_sequence_positive"),
    )


@event.listens_for(NoteTypeRelease, "before_update")
@event.listens_for(NoteTypeRelease, "before_delete")
def _immutable_release(_mapper, _connection, _target):
    raise ValueError("Published NoteType releases are immutable; publish a new version.")
