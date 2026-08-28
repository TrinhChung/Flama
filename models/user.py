from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from models import db


class User(UserMixin, db.Model):
    """Basic user model supporting authentication."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    role_id = db.Column(db.Integer, db.ForeignKey("user_roles.id"), nullable=True, index=True)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    balance_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    custom_platform_fee_percent = db.Column(db.Float, nullable=True)
    email_verified_at = db.Column(db.DateTime, nullable=True)
    email_verification_source = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    card_progress = db.relationship(
        "CardProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    scheduler_settings = db.relationship(
        "UserSchedulerSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    scheduler_presets = db.relationship(
        "SchedulerPreset",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    role = db.relationship("UserRole", back_populates="users")
    balance_transactions = db.relationship(
        "UserBalanceTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserBalanceTransaction.user_id",
        order_by="UserBalanceTransaction.created_at.desc()",
    )

    @property
    def is_active(self) -> bool:
        """Flask-Login hook: disabled users cannot authenticate."""
        return not bool(self.is_disabled)

    def set_password(self, password: str) -> None:
        """Hash and store the provided password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Validate a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)
