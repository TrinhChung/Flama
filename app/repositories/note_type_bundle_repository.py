"""Queries for canonical template prices and existing recipient licenses."""

from datetime import datetime

from sqlalchemy import or_, select

from models.payment_entitlement import PaymentEntitlement
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.user import User


def active_entitlement_conditions(*, user_id, now=None):
    now = now or datetime.utcnow()
    return (
        PaymentEntitlement.user_id == int(user_id),
        PaymentEntitlement.resource_type == "template",
        PaymentEntitlement.status == "active",
        or_(PaymentEntitlement.effective_from.is_(None), PaymentEntitlement.effective_from <= now),
        or_(PaymentEntitlement.expires_at.is_(None), PaymentEntitlement.expires_at > now),
    )


def template_rows(session, template_ids):
    if not template_ids:
        return {}
    rows = session.execute(select(
        Template.id, Template.name, Template.owner_user_id, Template.origin,
        Template.source_template_id, Template.archived_at,
        TemplatePublication.marketplace_status, TemplatePublication.pricing_mode,
        TemplatePublication.price_amount_minor, User.username,
    ).outerjoin(TemplatePublication, TemplatePublication.template_id == Template.id)
        .join(User, User.id == Template.owner_user_id)
        .where(Template.id.in_(template_ids))).mappings()
    return {row["id"]: dict(row) for row in rows}


def release_sources(session, release_ids):
    if not release_ids:
        return {}
    return dict(session.execute(select(TemplateRelease.id, TemplateRelease.template_id)
        .where(TemplateRelease.id.in_(release_ids))).all())


def licensed_template_ids(session, *, user_id, template_ids, current_read=False):
    """Server-issued receipts retain access unless a license was revoked.

    Free receipts predate template payment entitlements. Keeping these valid
    preserves licenses acquired before a template was put on sale.
    """
    if not template_ids:
        return set()
    now = datetime.utcnow()
    statement = select(
        PaymentEntitlement.resource_ref_id, PaymentEntitlement.status,
        PaymentEntitlement.effective_from, PaymentEntitlement.expires_at,
    ).where(PaymentEntitlement.user_id == user_id,
        PaymentEntitlement.resource_type == "template",
        PaymentEntitlement.resource_ref_id.in_(template_ids))
    rights = session.execute(statement.with_for_update() if current_read else statement).all()
    active, revoked = set(), set()
    for template_id, status, effective, expires in rights:
        if status == "active" and (effective is None or effective <= now) and (expires is None or expires > now):
            active.add(template_id)
        elif status in {"revoked", "refunded", "expired", "active"}:
            revoked.add(template_id)
    statement = (select(TemplateSubscription.source_template_id)
        .join(Template, Template.id == TemplateSubscription.local_template_id)
        .where(TemplateSubscription.user_id == user_id,
            TemplateSubscription.source_template_id.in_(template_ids),
            Template.origin == "market_copy",
            Template.source_template_id == TemplateSubscription.source_template_id))
    copies = set(session.execute(statement.with_for_update() if current_read else statement).scalars())
    statement = select(Template.id).where(Template.id.in_(template_ids), Template.owner_user_id == user_id)
    owned = set(session.execute(statement.with_for_update() if current_read else statement).scalars())
    from app.repositories.legacy_template_provenance_repository import legacy_license_source_ids
    legacy = legacy_license_source_ids(session, user_id=user_id, source_template_ids=template_ids,
        current_read=current_read)
    return owned | active | ((copies | legacy) - revoked)
