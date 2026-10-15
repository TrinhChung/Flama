"""Bounded pending-feed reads; the caller owns head locks and transactions."""

from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm.attributes import set_committed_value

from models.review_analytics import ReviewAnalyticsHead
from models.review_analytics_outbox import ReviewAnalyticsOutbox

_ADVANCE_HEAD_MYSQL = text(
    "INSERT INTO review_analytics_heads (user_id,next_generation,source_revision,updated_at) "
    "VALUES (:user_id,1,LAST_INSERT_ID(1),:now_utc) "
    "ON DUPLICATE KEY UPDATE source_revision=LAST_INSERT_ID(source_revision+1),updated_at=:now_utc"
)
_INSERT_OUTBOX = ReviewAnalyticsOutbox.__table__.insert()


def advance_async_head(session, *, user_id):
    """Atomically allocate the learner's revision, keeping its lock until commit.

    MySQL returns LAST_INSERT_ID(expr) in this statement's OK packet, exposed
    by PyMySQL/SQLAlchemy as lastrowid. This is a locked counter on the learner
    head, not an AUTO_INCREMENT event watermark or a connection-global read.
    https://dev.mysql.com/doc/c-api/8.0/en/mysql-insert-id.html
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user_id = int(user_id)
    if session.get_bind().dialect.name != "mysql":
        from app.repositories.review_analytics_repository import lock_head
        head = lock_head(session, user_id)
        head.source_revision = int(head.source_revision) + 1
        head.updated_at = now
        return int(head.source_revision)
    result = session.execute(_ADVANCE_HEAD_MYSQL, {"user_id": user_id, "now_utc": now})
    revision = result.lastrowid
    if type(revision) is not int or revision <= 0:
        raise RuntimeError("MySQL did not return an authoritative async head revision.")
    loaded = session.identity_map.get(session.identity_key(ReviewAnalyticsHead, user_id))
    if loaded is not None:
        set_committed_value(loaded, "source_revision", revision)
        set_committed_value(loaded, "updated_at", now)
    return revision


def insert_outbox_revision(session, values):
    """Persist the feed directly without another ORM/domain-hook flush."""
    session.execute(_INSERT_OUTBOX, values)


def next_pending_revision(session, *, user_id, after_revision=0):
    return session.execute(select(ReviewAnalyticsOutbox).where(
        ReviewAnalyticsOutbox.user_id == int(user_id),
        ReviewAnalyticsOutbox.applied_at.is_(None),
        ReviewAnalyticsOutbox.source_revision > int(after_revision),
    ).order_by(ReviewAnalyticsOutbox.source_revision).limit(1).with_for_update()
        .execution_options(populate_existing=True)).scalar_one_or_none()


def pending_users_statement(*, limit=100):
    return select(ReviewAnalyticsOutbox.user_id).where(
        ReviewAnalyticsOutbox.applied_at.is_(None)
    ).group_by(ReviewAnalyticsOutbox.user_id).order_by(
        func.min(ReviewAnalyticsOutbox.created_at), ReviewAnalyticsOutbox.user_id,
    ).limit(int(limit))


def pending_user_ids(session, *, limit=100):
    return [int(value) for value in session.execute(pending_users_statement(limit=limit)).scalars()]


def has_pending(session, *, user_id):
    return session.execute(select(ReviewAnalyticsOutbox.source_revision).where(
        ReviewAnalyticsOutbox.user_id == int(user_id), ReviewAnalyticsOutbox.applied_at.is_(None)
    ).limit(1)).first() is not None
