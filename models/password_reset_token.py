"""One-time password reset token state.

Only the SHA-256 digest is persisted. The opaque token sent to the user is
never stored in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

from models import db

UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        db.Index(
            "ix_password_reset_tokens_user_active",
            "user_id",
            "used_at",
            "revoked_at",
        ),
        db.Index("ix_password_reset_tokens_expires_at", "expires_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User")

    @property
    def is_active(self) -> bool:
        now = _utcnow()
        return self.used_at is None and self.revoked_at is None and self.expires_at > now
