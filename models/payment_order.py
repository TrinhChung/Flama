from datetime import datetime

from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class PaymentOrder(db.Model):
    __tablename__ = "payment_orders"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merchant_order_code = db.Column(db.String(64), nullable=False, unique=True)
    status = db.Column(
        db.Enum(
            "pending_payment",
            "paid",
            "under_review",
            "expired",
            "canceled",
            "failed",
            "refunded",
            name="payment_order_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default="pending_payment",
        index=True,
    )
    grant_status = db.Column(
        db.Enum(
            "pending",
            "completed",
            "failed",
            name="payment_order_grant_status_enum",
            native_enum=False,
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    currency_code = db.Column(db.String(8), nullable=False, default="VND")
    subtotal_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    discount_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    total_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    paid_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    items = db.relationship(
        "PaymentOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PaymentOrderItem.created_at",
    )
    attempts = db.relationship(
        "PaymentAttempt",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PaymentAttempt.created_at",
    )
    entitlements = db.relationship(
        "PaymentEntitlement",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PaymentEntitlement.created_at",
    )

    __table_args__ = (
        Index("ix_payment_orders_user_created_at", "user_id", "created_at"),
        Index("ix_payment_orders_status_created_at", "status", "created_at"),
        Index("ix_payment_orders_grant_status_created_at", "grant_status", "created_at"),
    )
