"""Bounded template outbox SQL. Transaction ownership stays in the service."""

from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert

from models.template import Template
from models.template_subscription import TemplateSubscription
from models.template_sync_job import TemplateSyncJob


def insert_once(session, values):
    table = TemplateSyncJob.__table__
    if session.get_bind().dialect.name == "mysql":
        statement = mysql_insert(table).values(**values)
        statement = statement.on_duplicate_key_update(id=table.c.id)
    else:
        # Existing isolated unit suites use SQLite; production claims and
        # concurrency qualification run exclusively on MySQL.
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        statement = sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=["release_id", "recipient_key"])
    session.execute(statement)


def claim_next(session, now):
    row = session.execute(select(TemplateSyncJob.__table__).where(
        TemplateSyncJob.status == "pending", TemplateSyncJob.available_at <= now,
    ).order_by(TemplateSyncJob.available_at, TemplateSyncJob.id).limit(1).with_for_update(skip_locked=True)).mappings().first()
    return dict(row) if row else None


def lock_pending_job(session, job_id):
    row = session.execute(select(TemplateSyncJob.__table__).where(
        TemplateSyncJob.id == job_id, TemplateSyncJob.status == "pending",
    ).with_for_update(skip_locked=True)).mappings().first()
    return dict(row) if row else None


def update_job(session, job_id, **values):
    session.execute(update(TemplateSyncJob.__table__).where(TemplateSyncJob.id == job_id).values(**values))


def queue_summary(session, now):
    """Aggregate operational metadata without loading template/learner payloads."""
    counts = {status: 0 for status in ("pending", "done", "failed")}
    counts.update(dict(session.execute(select(TemplateSyncJob.status, func.count()).group_by(TemplateSyncJob.status)).all()))
    ready_count, oldest_pending = session.execute(select(
        func.count(), func.min(TemplateSyncJob.available_at),
    ).where(TemplateSyncJob.status == "pending", TemplateSyncJob.available_at <= now)).one()
    errors = dict(session.execute(select(TemplateSyncJob.last_error_code, func.count()).where(
        TemplateSyncJob.status == "failed",
    ).group_by(TemplateSyncJob.last_error_code)).all())
    return {"counts": counts, "ready_count": ready_count, "oldest_ready_at": oldest_pending,
            "failed_error_counts": errors}


def recipient_page(session, job, limit):
    statement = select(TemplateSubscription.id).where(
        TemplateSubscription.source_template_id == job["source_template_id"],
        TemplateSubscription.auto_update_enabled.is_(True),
    )
    if job["after_subscription_id"]:
        statement = statement.where(TemplateSubscription.id > job["after_subscription_id"])
    return list(session.execute(statement.order_by(TemplateSubscription.id).limit(limit)).scalars())


def lock_recipient(session, subscription_id):
    # Match the interactive service's local-template -> subscription lock order.
    local_id = session.execute(select(TemplateSubscription.local_template_id).where(
        TemplateSubscription.id == subscription_id,
    )).scalar_one_or_none()
    if local_id is None:
        return None, None
    local = session.execute(select(Template.__table__).where(
        Template.id == local_id,
    ).with_for_update(nowait=True)).mappings().first()
    subscription = session.execute(select(TemplateSubscription.__table__).where(
        TemplateSubscription.id == subscription_id,
    ).with_for_update(nowait=True)).mappings().first()
    return (dict(subscription) if subscription else None, dict(local) if local else None)
