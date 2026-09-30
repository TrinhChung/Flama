from datetime import datetime

from sqlalchemy import event, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from models import db
from models.model_uuid import uuid_str


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
    # NULL once the Card is removed (Template deletion): the ref, its ordinal
    # and its sync cursors survive on the Note instead of cascading away
    # (Phase 6, D6-05). The next sync re-binds the ordinal or refuses it.
    card_id = db.Column(
        db.String(36),
        db.ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note_id = db.Column(db.String(36), nullable=True, index=True)
    snapshot_hash = db.Column(db.String(64), nullable=True)
    applied_local_revision = db.Column(db.BigInteger, nullable=True)
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

    card = db.relationship("Card", foreign_keys=[card_id])

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
    )


@event.listens_for(Session, "before_flush")
def _snapshot_source_card_notes(session: Session, _flush_context, _instances) -> None:
    """Keep ``note_id`` equal to the mapped Card's Note (Phase 6, D6-05).

    The Note survives Template and Card removal, so the external mapping and
    its sync cursors can be re-bound to the learning subject afterwards.
    """

    from models.card import Card

    changed = [
        item
        for item in list(session.new) + list(session.dirty)
        if isinstance(item, ConnectSourceCardRef)
        and item.card_id
        and (item.note_id is None or sa_inspect(item).attrs.card_id.history.has_changes())
    ]
    if not changed:
        return
    card_ids = sorted({str(item.card_id) for item in changed})
    with session.no_autoflush:
        note_by_card = {
            str(card_id): str(note_id)
            for card_id, note_id in session.execute(
                select(Card.id, Card.note_id).where(Card.id.in_(card_ids))
            )
        }
    for item in changed:
        note_id = note_by_card.get(str(item.card_id))
        if note_id:
            item.note_id = note_id
