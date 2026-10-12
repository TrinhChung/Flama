"""Frozen pre-P11 Card and CardProgress DDL for historical migrations only.

These tables live on private metadata and never register application models.
Parent PK stubs exist only for foreign-key resolution. Nothing in this module
creates tables: individual historical revisions own their CREATE operations.
"""
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import text, UniqueConstraint
from sqlalchemy.orm import declarative_base

RETIRED_CARD_METADATA = sa.MetaData()
_CardBase = declarative_base(metadata=RETIRED_CARD_METADATA)
for name, column_type in (("users", sa.Integer()), ("notes", sa.String(36)),
                          ("templates", sa.String(36)), ("study_applications", sa.String(36)),
                          ("review_events", sa.Integer())):
    sa.Table(name, RETIRED_CARD_METADATA, sa.Column("id", column_type, primary_key=True))

class Card(_CardBase):
    __tablename__ = "cards"

    id = sa.Column(sa.String(36), primary_key=True)
    note_id = sa.Column(sa.String(36), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = sa.Column(sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    # Phase 6 application occurrence this Card presents. Nullable only until
    # every Card creation path sets it; migration 46 backfills existing Cards.
    application_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("study_applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


    # One Card per (Note, occurrence). A Template applied twice has two
    # occurrences, so (note_id, template_id) is no longer unique (D6-09).
    __table_args__ = (
        UniqueConstraint("note_id", "application_id", name="uq_cards_note_application"),
    )


class CardProgress(_CardBase):
    __tablename__ = "card_progress"

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    queue = sa.Column(sa.String(20), nullable=False, default="new", index=True)
    step_index = sa.Column(sa.Integer, nullable=False, default=0)
    due_at = sa.Column(sa.DateTime, nullable=True, index=True)
    due_day = sa.Column(sa.Integer, nullable=True, index=True)
    interval_days = sa.Column(sa.Integer, nullable=False, default=0)
    interval_days_raw = sa.Column(sa.Float, nullable=True)
    is_suspended = sa.Column(sa.Boolean, nullable=False, default=False, index=True)
    is_buried = sa.Column(sa.Boolean, nullable=False, default=False, index=True)
    buried_until_day = sa.Column(sa.Integer, nullable=True, index=True)
    review_kind = sa.Column(sa.String(20), nullable=False, default="review", index=True)
    scheduler_mode = sa.Column(sa.String(20), nullable=False, default="legacy", index=True)
    ease_factor = sa.Column(sa.Float, nullable=False, default=2.5)
    memory_stability = sa.Column(sa.Float, nullable=True)
    memory_difficulty = sa.Column(sa.Float, nullable=True)
    suspension_reason = sa.Column(sa.String(32), nullable=True)
    last_leech_at = sa.Column(sa.DateTime, nullable=True)
    last_leech_lapses = sa.Column(sa.Integer, nullable=False, default=0)
    last_review_event_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("review_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reps = sa.Column(sa.Integer, nullable=False, default=0)
    lapses = sa.Column(sa.Integer, nullable=False, default=0)
    last_reviewed_at = sa.Column(sa.DateTime, nullable=True)
    revision = sa.Column(
        sa.BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = sa.Column(
        sa.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "card_id", name="uq_card_progress_user_card"),
        sa.Index("ix_card_progress_user_queue_due_day", "user_id", "queue", "due_day"),
        sa.Index("ix_card_progress_user_queue_due_at", "user_id", "queue", "due_at"),
        sa.Index("ix_card_progress_user_hidden_flags", "user_id", "is_suspended", "is_buried"),
    )
