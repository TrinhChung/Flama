from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class PaymentEntitlement(db.Model):
    __tablename__ = "payment_entitlements"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_order_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_order_item_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_order_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_attempt_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_attempts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entitlement_type = db.Column(db.String(64), nullable=False)
    resource_type = db.Column(db.String(64), nullable=False)
    resource_ref_id = db.Column(db.String(36), nullable=False)
    status = db.Column(
        db.Enum(
            "pending",
            "active",
            "revoked",
            "expired",
            "refunded",
            name="payment_entitlement_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    granted_at = db.Column(db.DateTime, nullable=True)
    effective_from = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    grant_data_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    order = db.relationship("PaymentOrder", back_populates="entitlements")
    order_item = db.relationship("PaymentOrderItem", back_populates="entitlement")
    payment_attempt = db.relationship("PaymentAttempt", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("payment_order_item_id", name="uq_payment_entitlements_order_item"),
        Index("ix_payment_entitlements_user_status", "user_id", "status"),
        Index("ix_payment_entitlements_resource_ref", "resource_type", "resource_ref_id"),
    )
