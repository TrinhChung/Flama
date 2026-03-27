from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class PaymentWebhookEvent(db.Model):
    __tablename__ = "payment_webhook_events"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    provider_code = db.Column(db.String(64), nullable=False)
    event_key = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(120), nullable=False, default="payment.unknown")
    payment_attempt_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_attempts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_order_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    signature_valid = db.Column(db.Boolean, nullable=False, default=False)
    processing_status = db.Column(
        db.Enum(
            "received",
            "processed",
            "ignored",
            "failed",
            name="payment_webhook_processing_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default="received",
        index=True,
    )
    error_message = db.Column(db.Text, nullable=True)
    payload_json = db.Column(db.JSON, nullable=False, default=dict)
    received_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    payment_attempt = db.relationship("PaymentAttempt", back_populates="webhook_events")
    payment_order = db.relationship("PaymentOrder")

    __table_args__ = (
        UniqueConstraint("provider_code", "event_key", name="uq_payment_webhook_events_provider_event"),
        Index(
            "ix_payment_webhook_events_processing_status_received_at",
            "processing_status",
            "received_at",
        ),
        Index(
            "ix_payment_webhook_events_payment_attempt_received_at",
            "payment_attempt_id",
            "received_at",
        ),
        Index(
            "ix_payment_webhook_events_payment_order_received_at",
            "payment_order_id",
            "received_at",
        ),
    )
