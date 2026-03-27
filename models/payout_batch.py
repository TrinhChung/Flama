from datetime import datetime

from models import db


class PayoutBatch(db.Model):
    __tablename__ = "payout_batches"

    id = db.Column(db.Integer, primary_key=True)
    reference_id = db.Column(db.String(96), nullable=False, unique=True, index=True)
    client_reference_key = db.Column(db.String(96), nullable=False, index=True)
    request_fingerprint = db.Column(db.String(64), nullable=False, index=True)
    provider_payout_id = db.Column(db.String(128), nullable=True, unique=True, index=True)
    internal_status = db.Column(db.String(32), nullable=False, default="pending_submission", index=True)
    provider_approval_state = db.Column(db.String(32), nullable=True, index=True)
    validate_destination = db.Column(db.Boolean, nullable=False, default=False)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    category_json = db.Column(db.Text, nullable=False, default="[]")
    request_payload_json = db.Column(db.Text, nullable=False, default="{}")
    response_payload_json = db.Column(db.Text, nullable=True)
    error_payload_json = db.Column(db.Text, nullable=True)
    created_by_admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submitted_at = db.Column(db.DateTime, nullable=True, index=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items = db.relationship(
        "PayoutBatchItem",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="PayoutBatchItem.id.asc()",
    )
    created_by_admin = db.relationship("User", foreign_keys=[created_by_admin_id])
