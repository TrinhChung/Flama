from datetime import datetime

from models import db


class PayoutBatchItem(db.Model):
    __tablename__ = "payout_batch_items"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("payout_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_id = db.Column(db.String(128), nullable=False, unique=True, index=True)
    client_reference_key = db.Column(db.String(96), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    to_bin = db.Column(db.String(12), nullable=False)
    to_account_number = db.Column(db.String(64), nullable=False)
    internal_status = db.Column(db.String(32), nullable=False, default="pending_submission", index=True)
    provider_transaction_id = db.Column(db.String(128), nullable=True, index=True)
    provider_reference = db.Column(db.String(128), nullable=True, index=True)
    provider_state = db.Column(db.String(32), nullable=True, index=True)
    response_payload_json = db.Column(db.Text, nullable=True)
    error_code = db.Column(db.String(64), nullable=True)
    error_message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    batch = db.relationship("PayoutBatch", back_populates="items")
