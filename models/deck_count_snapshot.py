"""Direct-deck count caches and durable, monotonic invalidation tokens."""

from datetime import datetime

from sqlalchemy import text

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, binary_hash, datetime6


DASHBOARD_CONTRACT = 1
CARD_UNIT = 1
NOTE_UNIT = 2


class DeckCountContentRevision(db.Model):
    __tablename__ = "deck_count_content_revisions"

    # Zero is the conservative global content epoch, so there is no Deck FK.
    physical_deck_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    revision = db.Column(db.BigInteger, nullable=False, default=0, server_default=text("0"))
    updated_at = db.Column(datetime6(), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("physical_deck_id >= 0", name="ck_deck_count_content_id"),
        db.CheckConstraint("revision >= 0", name="ck_deck_count_content_revision"),
        MYSQL_TABLE_OPTIONS,
    )


class DeckCountLearnerRevision(db.Model):
    __tablename__ = "deck_count_learner_revisions"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    # Zero invalidates every direct deck for this learner. Keep tombstone tokens.
    effective_deck_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    revision = db.Column(db.BigInteger, nullable=False, default=0, server_default=text("0"))
    updated_at = db.Column(datetime6(), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("effective_deck_id >= 0", name="ck_deck_count_learner_id"),
        db.CheckConstraint("revision >= 0", name="ck_deck_count_learner_revision"),
        MYSQL_TABLE_OPTIONS,
    )


class DeckStudyCountSnapshot(db.Model):
    __tablename__ = "deck_study_count_snapshots"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    effective_deck_id = db.Column(db.Integer, db.ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True, autoincrement=False)
    contract_code = db.Column(db.SmallInteger, primary_key=True, autoincrement=False)
    unit_code = db.Column(db.SmallInteger, primary_key=True, autoincrement=False)
    total_count = db.Column(db.BigInteger, nullable=False)
    new_count = db.Column(db.BigInteger, nullable=False)
    learn_count = db.Column(db.BigInteger, nullable=False)
    due_count = db.Column(db.BigInteger, nullable=False)
    study_day = db.Column(db.Date, nullable=False)
    valid_until_utc = db.Column(datetime6(), nullable=False)
    policy_hash = db.Column(binary_hash(), nullable=False)
    dependency_hash = db.Column(binary_hash(), nullable=False)
    computed_at = db.Column(datetime6(), nullable=False)

    __table_args__ = (
        db.Index("ix_deck_count_snapshot_deck", "effective_deck_id"),
        db.CheckConstraint("effective_deck_id > 0", name="ck_deck_count_snapshot_id"),
        db.CheckConstraint("contract_code = 1", name="ck_deck_count_snapshot_contract"),
        db.CheckConstraint("unit_code IN (1, 2)", name="ck_deck_count_snapshot_unit"),
        db.CheckConstraint("total_count >= 0", name="ck_deck_count_snapshot_total"),
        db.CheckConstraint("new_count >= 0 AND new_count <= total_count", name="ck_deck_count_snapshot_new"),
        db.CheckConstraint("learn_count >= 0 AND learn_count <= total_count", name="ck_deck_count_snapshot_learn"),
        db.CheckConstraint("due_count >= 0 AND due_count <= total_count", name="ck_deck_count_snapshot_due"),
        MYSQL_TABLE_OPTIONS,
    )
