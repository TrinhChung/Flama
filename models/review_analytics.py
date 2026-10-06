"""Rebuildable historical review counts; raw ReviewEvents remain authoritative."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, binary_hash, datetime6


BUILDING = 0
READY = 1
DIRTY = 2
FAILED = 3
RETIRED = 4
SCOPE_COLLECTION = 0
SCOPE_DECK = 1


def _unsigned_bigint():
    return sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")


def _unsigned_tinyint():
    return sa.SmallInteger().with_variant(mysql.TINYINT(unsigned=True), "mysql")


def _unsigned_smallint():
    return sa.SmallInteger().with_variant(mysql.SMALLINT(unsigned=True), "mysql")


class ReviewAnalyticsHead(db.Model):
    __tablename__ = "review_analytics_heads"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True, autoincrement=False,
    )
    next_generation = db.Column(
        _unsigned_bigint(), nullable=False, default=1, server_default=sa.text("1")
    )
    # Deliberately no reverse FKs: generation publication owns these pointers.
    active_generation = db.Column(_unsigned_bigint(), nullable=True)
    building_generation = db.Column(_unsigned_bigint(), nullable=True)
    source_revision = db.Column(
        _unsigned_bigint(), nullable=False, default=0, server_default=sa.text("0")
    )
    updated_at = db.Column(
        datetime6(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class ReviewAnalyticsGeneration(db.Model):
    __tablename__ = "review_analytics_generations"

    BUILDING = BUILDING
    READY = READY
    DIRTY = DIRTY
    FAILED = FAILED
    RETIRED = RETIRED

    user_id = db.Column(
        db.Integer, db.ForeignKey("review_analytics_heads.user_id", ondelete="CASCADE"),
        primary_key=True, autoincrement=False,
    )
    generation = db.Column(_unsigned_bigint(), primary_key=True, autoincrement=False)
    policy_hash = db.Column(binary_hash(), nullable=False)
    timezone_name = db.Column(ascii_string(64), nullable=False)
    day_boundary_hour = db.Column(_unsigned_tinyint(), nullable=False)
    grouping_version = db.Column(_unsigned_smallint(), nullable=False)
    timezone_rules_version = db.Column(db.String(64), nullable=False)
    status = db.Column(_unsigned_tinyint(), nullable=False)
    baseline_high_water_id = db.Column(
        _unsigned_bigint(), nullable=False, default=0, server_default=sa.text("0")
    )
    backfill_cursor_id = db.Column(
        _unsigned_bigint(), nullable=False, default=0, server_default=sa.text("0")
    )
    applied_source_revision = db.Column(_unsigned_bigint(), nullable=True)
    verified_source_revision = db.Column(_unsigned_bigint(), nullable=True)
    verification_contract_version = db.Column(_unsigned_smallint(), nullable=True)
    verified_at = db.Column(datetime6(), nullable=True)
    created_at = db.Column(datetime6(), nullable=False, default=datetime.utcnow)
    published_at = db.Column(datetime6(), nullable=True)
    last_error_code = db.Column(db.String(64), nullable=True)

    __table_args__ = (
        db.CheckConstraint("day_boundary_hour BETWEEN 0 AND 23", name="ck_review_analytics_day_boundary"),
        db.CheckConstraint("status BETWEEN 0 AND 4", name="ck_review_analytics_status"),
        db.CheckConstraint("backfill_cursor_id <= baseline_high_water_id", name="ck_review_analytics_cursor"),
        MYSQL_TABLE_OPTIONS,
    )


class DailyReviewCount(db.Model):
    __tablename__ = "daily_review_counts"

    SCOPE_COLLECTION = SCOPE_COLLECTION
    SCOPE_DECK = SCOPE_DECK

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    generation = db.Column(_unsigned_bigint(), primary_key=True, autoincrement=False)
    scope_kind = db.Column(_unsigned_tinyint(), primary_key=True, autoincrement=False)
    # Historical attribution is retained even after the live Deck is removed.
    scope_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    study_day = db.Column(db.Date, primary_key=True)
    review_event_count = db.Column(db.BigInteger, nullable=False)
    positive_duration_ms = db.Column(db.BigInteger, nullable=False)
    passed_review_count = db.Column(db.BigInteger, nullable=False)

    __table_args__ = (
        db.ForeignKeyConstraint(
            ("user_id", "generation"),
            ("review_analytics_generations.user_id", "review_analytics_generations.generation"),
            name="fk_daily_review_count_generation", ondelete="CASCADE",
        ),
        db.CheckConstraint(
            "(scope_kind = 0 AND scope_id = 0) OR (scope_kind = 1 AND scope_id > 0)",
            name="ck_daily_review_count_scope",
        ),
        db.CheckConstraint("review_event_count >= 0", name="ck_daily_review_count_events"),
        db.CheckConstraint("positive_duration_ms >= 0", name="ck_daily_review_count_duration"),
        db.CheckConstraint(
            "passed_review_count >= 0 AND passed_review_count <= review_event_count",
            name="ck_daily_review_count_passed",
        ),
        MYSQL_TABLE_OPTIONS,
    )
