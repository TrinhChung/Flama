from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class PaymentOrderItem(db.Model):
    __tablename__ = "payment_order_items"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    order_id = db.Column(
        db.String(36),
        db.ForeignKey("payment_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_type = db.Column(db.String(64), nullable=False)
    product_ref_id = db.Column(db.String(36), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    line_total_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    title_snapshot = db.Column(db.String(255), nullable=False)
    product_snapshot_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("PaymentOrder", back_populates="items")
    entitlement = db.relationship(
        "PaymentEntitlement",
        back_populates="order_item",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "order_id",
            "product_type",
            "product_ref_id",
            name="uq_payment_order_items_order_product",
        ),
        Index("ix_payment_order_items_product_ref", "product_type", "product_ref_id"),
    )
