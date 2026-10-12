from datetime import datetime

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

from models import db
from models.model_uuid import uuid_str


APPLIED_STATES = ("LEGACY_CARD_PROGRESS", "AUTHORITY", "NEEDS_CONFIRMATION")
APPLIED_STATE_CHECK = (
    "applied_local_revision_state IS NULL OR "
    "(applied_local_revision_state IN ('LEGACY_CARD_PROGRESS', 'AUTHORITY', 'NEEDS_CONFIRMATION') "
    "AND (applied_local_revision_state <> 'AUTHORITY' OR applied_authority_revision IS NOT NULL))"
)


class ConnectSourceCardRef(db.Model):
    """Stable mapping and sync cursors for one external Anki card."""

    __tablename__ = "connect_source_card_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_card_id = db.Column(db.String(128), nullable=False)
    external_note_id = db.Column(db.String(128), nullable=False)
    source_ord = db.Column(db.Integer, nullable=False)
    # Presentation key of the mapped Card (ADR P11). A key whose application
    # is gone names no Card: the ref, its ordinal and its sync cursors survive
    # on the Note (Phase 6, D6-05) and the next sync re-binds the ordinal.
    card_id = db.Column(db.String(80), nullable=True, index=True)
    note_id = db.Column(db.String(36), nullable=True, index=True)
    snapshot_hash = db.Column(db.String(64), nullable=True)
    applied_local_revision = db.Column(db.BigInteger, nullable=True)
    # NOTE storage profile CANONICAL_V1 (ADR P9-03 §2.6, migration 48): the
    # Note authority revision this ref last applied or confirmed.
    # applied_local_revision keeps the projection-era CardProgress revision.
    applied_authority_revision = db.Column(db.BigInteger, nullable=True)
    applied_local_revision_state = db.Column(db.String(32), nullable=True)
    review_cursor = db.Column(db.BigInteger, nullable=True)
    last_session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "source_key",
            "external_card_id",
            name="uq_connect_source_card_refs_source_card",
        ),
        db.Index(
            "ix_connect_source_card_refs_source_note",
            "user_id",
            "source_key",
            "external_note_id",
        ),
        db.CheckConstraint(
            APPLIED_STATE_CHECK, name="ck_connect_source_card_refs_applied_state"
        ),
    )


@event.listens_for(Session, "before_flush")
def _snapshot_source_card_notes(session: Session, _flush_context, _instances) -> None:
    """Keep ``note_id`` equal to the mapped Card's Note (Phase 6, D6-05).

    The Note survives Template and Card removal, so the external mapping and
    its sync cursors can be re-bound to the learning subject afterwards.
    """

    from models.card import card_key_pairs

    changed = [
        item
        for item in list(session.new) + list(session.dirty)
        if isinstance(item, ConnectSourceCardRef)
        and item.card_id
        and (item.note_id is None or sa_inspect(item).attrs.card_id.history.has_changes())
    ]
    if not changed:
        return
    with session.no_autoflush:
        # A presentation key names its Note; a legacy ID resolves through the registry.
        note_by_card = {
            card_id: note_id
            for card_id, (note_id, _application_id) in card_key_pairs(
                session, {str(item.card_id) for item in changed}
            ).items()
        }
    for item in changed:
        note_id = note_by_card.get(str(item.card_id))
        if note_id:
            item.note_id = note_id
