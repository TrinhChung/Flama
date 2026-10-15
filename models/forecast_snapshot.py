"""Rebuildable collection/scoped due buckets, never scheduler authority."""

from datetime import datetime

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, binary_hash, datetime6


class StudyForecastSnapshot(db.Model):
    __tablename__ = "study_forecast_snapshots"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        primary_key=True, autoincrement=False)
    scope_hash = db.Column(binary_hash(), primary_key=True)
    study_day = db.Column(db.Integer, nullable=False)
    policy_hash = db.Column(binary_hash(), nullable=False)
    dependency_hash = db.Column(binary_hash(), nullable=False)
    valid_until_utc = db.Column(datetime6(), nullable=False)
    daily_load = db.Column(db.Float(precision=53), nullable=False)
    bucket_count = db.Column(db.Integer, nullable=False)
    computed_at = db.Column(datetime6(), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("daily_load >= 0", name="ck_forecast_load"),
        db.CheckConstraint("bucket_count >= 0", name="ck_forecast_buckets"),
        MYSQL_TABLE_OPTIONS,
    )


class StudyForecastDueBucket(db.Model):
    __tablename__ = "study_forecast_due_buckets"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    scope_hash = db.Column(binary_hash(), primary_key=True)
    due_day = db.Column(db.Integer, primary_key=True, autoincrement=False)
    queue = db.Column(db.String(20), primary_key=True)
    card_count = db.Column(db.BigInteger, nullable=False)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["user_id", "scope_hash"],
            ["study_forecast_snapshots.user_id", "study_forecast_snapshots.scope_hash"],
            ondelete="CASCADE", name="fk_forecast_bucket_snapshot",
        ),
        db.CheckConstraint("due_day BETWEEN 1 AND 3652059", name="ck_forecast_due_day"),
        db.CheckConstraint("card_count > 0", name="ck_forecast_card_count"),
        MYSQL_TABLE_OPTIONS,
    )
