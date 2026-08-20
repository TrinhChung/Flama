from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db


class DeckInstallRebaseConflict(db.Model):
    __tablename__ = "deck_install_rebase_conflicts"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    rebase_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_install_rebases.id",
            name="fk_deck_install_rebase_conflicts_rebase",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    release_change_id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        db.ForeignKey(
            "deck_release_changes.id",
            name="fk_deck_install_rebase_conflicts_release_change",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    conflict_key = db.Column(db.String(191), nullable=False)
    entity_kind = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    field_def_id = db.Column(db.String(36), nullable=True)
    property_key = db.Column(db.String(191), nullable=False)
    base_value = db.Column(db.JSON, nullable=True)
    upstream_value = db.Column(db.JSON, nullable=True)
    local_value = db.Column(db.JSON, nullable=True)
    resolution_mode = db.Column(db.String(32), nullable=True)
    resolved_value = db.Column(db.JSON, nullable=True)
    resolved_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            name="fk_deck_install_rebase_conflicts_resolved_by",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    rebase = db.relationship("DeckInstallRebase", back_populates="conflicts")
    release_change = db.relationship(
        "DeckReleaseChange",
        foreign_keys=[release_change_id],
    )
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id])

    __table_args__ = (
        UniqueConstraint(
            "rebase_id",
            "conflict_key",
            name="uq_deck_install_rebase_conflicts_rebase_key",
        ),
        Index(
            "ix_deck_install_rebase_conflicts_resolution",
            "rebase_id",
            "resolution_mode",
            "id",
        ),
        Index(
            "ix_deck_install_rebase_conflicts_entity",
            "rebase_id",
            "entity_kind",
            "entity_id",
            "property_key",
            "id",
        ),
    )
