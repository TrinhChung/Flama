from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class UserBalanceTransaction(db.Model):
    """Ledger table tracking changes to a user's wallet balance."""

    __tablename__ = "user_balance_transactions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    buyer_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_order_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_order_item_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_order_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type = db.Column(
        db.String(50),
        nullable=False,
        default="deck_sale",
        index=True,
    )
    gross_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    platform_fee_percent = db.Column(db.Float, nullable=False, default=0.0)
    platform_fee_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    net_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    balance_after_minor = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(255), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="balance_transactions")
    buyer = db.relationship("User", foreign_keys=[buyer_user_id])
    order = db.relationship("PaymentOrder", foreign_keys=[payment_order_id])
    order_item = db.relationship("PaymentOrderItem", foreign_keys=[payment_order_item_id])

    __table_args__ = (
        UniqueConstraint(
            "payment_order_item_id",
            "user_id",
            "transaction_type",
            name="uq_user_balance_tx_order_item_user_type",
        ),
        Index("ix_user_balance_tx_user_created", "user_id", "created_at"),
    )
