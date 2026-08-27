from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class DeckAccessKeyRedemption(db.Model):
    """Record of a student / learner redeeming an access key to install a shared deck."""

    __tablename__ = "deck_access_key_redemptions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    key_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_access_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    redeemed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    access_expires_at = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(
        db.Enum("active", "revoked", "expired", name="deck_key_redemption_status_enum", native_enum=False),
        nullable=False,
        default="active",
        index=True,
    )

    access_key = db.relationship("DeckAccessKey", back_populates="redemptions")
    user = db.relationship("User", foreign_keys=[user_id])
    deck_install = db.relationship("DeckInstall", foreign_keys=[deck_install_id])

    __table_args__ = (
        db.UniqueConstraint("key_id", "user_id", name="uq_deck_key_user_redemption"),
    )
