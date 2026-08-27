from datetime import datetime

from models import db


class CreatorFeaturePolicy(db.Model):
    """Platform policy and hidden monetization configuration for creator features."""

    __tablename__ = "creator_feature_policies"

    id = db.Column(db.Integer, primary_key=True)
    feature_code = db.Column(db.String(64), unique=True, nullable=False, default="deck_access_keys")
    is_monetized = db.Column(db.Boolean, nullable=False, default=False)
    free_quota_per_creator = db.Column(db.Integer, nullable=False, default=-1)
    price_per_key_minor = db.Column(db.Integer, nullable=False, default=0)
    requires_pro_role = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
