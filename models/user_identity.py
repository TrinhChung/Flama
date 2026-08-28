from datetime import datetime

from models import db


class UserIdentity(db.Model):
    """Stores external identity provider mappings (e.g. Google OIDC sub) for users."""

    __tablename__ = "user_identities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = db.Column(db.String(32), nullable=False, default="google")
    provider_sub = db.Column(db.String(255), nullable=False)
    provider_email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("provider", "provider_sub", name="uq_user_identity_provider_sub"),
    )

    user = db.relationship("User", back_populates="identities")
