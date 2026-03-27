from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class PaymentAttempt(db.Model):
    __tablename__ = "payment_attempts"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    order_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_code = db.Column(db.String(64), nullable=False)
    payment_method_code = db.Column(db.String(64), nullable=False)
    status = db.Column(
        db.Enum(
            "created",
            "pending",
            "confirmed",
            "manual_review",
            "expired",
            "canceled",
            "failed",
            "refunded",
            name="payment_attempt_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default="created",
        index=True,
    )
    amount_minor = db.Column(db.Integer, nullable=False, default=0)
    currency_code = db.Column(db.String(8), nullable=False, default="VND")
    provider_payment_id = db.Column(db.String(255), nullable=True)
    provider_order_code = db.Column(db.String(255), nullable=True)
    expected_payment_reference = db.Column(db.String(255), nullable=True, index=True)
    checkout_url = db.Column(db.Text, nullable=True)
    provider_metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    failure_code = db.Column(db.String(120), nullable=True)
    failure_message = db.Column(db.Text, nullable=True)
    manual_review_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    order = db.relationship("PaymentOrder", back_populates="attempts")
    webhook_events = db.relationship(
        "PaymentWebhookEvent",
        back_populates="payment_attempt",
        cascade="all, delete-orphan",
        order_by="PaymentWebhookEvent.received_at",
    )
    entitlements = db.relationship(
        "PaymentEntitlement",
        back_populates="payment_attempt",
        order_by="PaymentEntitlement.created_at",
    )

    __table_args__ = (
        Index("ix_payment_attempts_order_created_at", "order_id", "created_at"),
        Index("ix_payment_attempts_status_expires_at", "status", "expires_at"),
        UniqueConstraint(
            "provider_code",
            "provider_payment_id",
            name="uq_payment_attempts_provider_payment_id",
        ),
        UniqueConstraint(
            "provider_code",
            "provider_order_code",
            name="uq_payment_attempts_provider_order_code",
        ),
    )
