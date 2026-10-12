"""Card membership and immutable base state for a study session."""

from datetime import datetime

from models import db


class StudySessionCard(db.Model):
    __tablename__ = "study_session_cards"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Presentation key of the dealt Card (ADR P11); Cards are derived, no FK.
    card_id = db.Column(db.String(80), nullable=False, index=True)
    source_deck_id = db.Column(db.Integer, nullable=True)
    local_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note_type_id = db.Column(db.String(36), nullable=True)
    scheduler_preset_id = db.Column(
        db.Integer,
        db.ForeignKey("scheduler_presets.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_progress_revision = db.Column(db.BigInteger, nullable=False, default=0)
    base_state_hash = db.Column(db.String(80), nullable=False)
    scheduler_config_hash = db.Column(db.String(80), nullable=False, index=True)
    initial_state_json = db.Column(db.Text, nullable=False)
    ordinal = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    session = db.relationship("StudySession", back_populates="cards")
    authority_pin = db.relationship(
        "StudySessionAuthorityPin",
        back_populates="session_card",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "card_id",
            name="uq_study_session_cards_session_card",
        ),
        db.Index(
            "ix_study_session_cards_session_ordinal",
            "session_id",
            "ordinal",
        ),
    )
