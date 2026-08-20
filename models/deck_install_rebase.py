from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckInstallRebase(db.Model):
    __tablename__ = "deck_install_rebases"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_installs.id",
            name="fk_deck_install_rebases_install",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    from_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_install_rebases_from_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    to_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_install_rebases_to_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(32), nullable=False, default="prepared", index=True)
    expected_overlay_revision = db.Column(db.BigInteger, nullable=False)
    idempotency_key = db.Column(db.String(64), nullable=True)
    change_count = db.Column(db.Integer, nullable=False, default=0)
    conflict_count = db.Column(db.Integer, nullable=False, default=0)
    resolved_conflict_count = db.Column(db.Integer, nullable=False, default=0)
    applied_change_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    prepared_at = db.Column(db.DateTime, nullable=True)
    applied_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    deck_install = db.relationship("DeckInstall", back_populates="rebases")
    from_release = db.relationship("DeckRelease", foreign_keys=[from_release_id])
    to_release = db.relationship("DeckRelease", foreign_keys=[to_release_id])
    conflicts = db.relationship(
        "DeckInstallRebaseConflict",
        back_populates="rebase",
        cascade="all, delete-orphan",
        order_by="DeckInstallRebaseConflict.id",
    )

    __table_args__ = (
        UniqueConstraint(
            "deck_install_id",
            "idempotency_key",
            name="uq_deck_install_rebases_install_idempotency",
        ),
        Index(
            "ix_deck_install_rebases_install_status_updated",
            "deck_install_id",
            "status",
            "updated_at",
            "id",
        ),
        Index(
            "ix_deck_install_rebases_install_target_status",
            "deck_install_id",
            "to_release_id",
            "status",
            "id",
        ),
    )
