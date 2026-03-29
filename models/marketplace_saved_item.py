from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class MarketplaceSavedItem(db.Model):
    __tablename__ = "marketplace_saved_items"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_type = db.Column(db.String(64), nullable=False, index=True)
    product_ref_id = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_type",
            "product_ref_id",
            name="uq_marketplace_saved_items_user_product",
        ),
    )
