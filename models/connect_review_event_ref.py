from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class ConnectReviewEventRef(db.Model):
    """Idempotency/provenance record for an imported Anki revlog row."""

    __tablename__ = "connect_review_event_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_review_id = db.Column(db.String(128), nullable=False)
    external_card_id = db.Column(db.String(128), nullable=False)
    review_event_id = db.Column(
        db.Integer,
        db.ForeignKey("review_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="imported")
    ignored_reason = db.Column(db.String(64), nullable=True)
    last_session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    review_event = db.relationship("ReviewEvent", foreign_keys=[review_event_id])

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "source_key",
            "external_review_id",
            name="uq_connect_review_event_refs_source_review",
        ),
        db.Index(
            "ix_connect_review_event_refs_source_card",
            "user_id",
            "source_key",
            "external_card_id",
        ),
    )
