from datetime import datetime

from models import db


class UserRole(db.Model):
    """Role catalog used to classify user permissions."""

    __tablename__ = "user_roles"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    default_platform_fee_percent = db.Column(db.Float, nullable=False, default=10.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    users = db.relationship("User", back_populates="role")
