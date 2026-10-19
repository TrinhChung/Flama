"""Standalone template marketplace queries; never flush or commit."""

from sqlalchemy import func, or_, select

from models.payment_entitlement import PaymentEntitlement
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.template_version import TemplateVersion
from models.user import User

PRODUCT_TYPE = "template"
LISTED = "published"
SORTS = {"newest", "popular", "price_asc", "price_desc", "name"}


def listed_conditions():
    # Received copies keep their provenance and can never be listed again.
    return (
        TemplatePublication.marketplace_status == LISTED,
        TemplatePublication.current_release_id.isnot(None),
        Template.archived_at.is_(None),
        Template.origin == "authored",
        Template.source_template_id.is_(None),
    )


def active_entitlement(session, *, user_id, template_id):
    statement = select(PaymentEntitlement.id).where(
        PaymentEntitlement.user_id == int(user_id),
        PaymentEntitlement.resource_type == PRODUCT_TYPE,
        PaymentEntitlement.resource_ref_id == str(template_id),
        PaymentEntitlement.status == "active",
    ).limit(1)
    return session.execute(statement).first() is not None


def marketplace_access(session, *, user_id, template_id):
    """A free listing or an active purchase grants receipt of the template."""
    listed_free = select(TemplatePublication.template_id).join(
        Template, Template.id == TemplatePublication.template_id,
    ).where(
        TemplatePublication.template_id == str(template_id),
        TemplatePublication.pricing_mode == "free",
        *listed_conditions(),
    ).limit(1)
    if session.execute(listed_free).first():
        return True
    return active_entitlement(session, user_id=user_id, template_id=template_id)


def _install_counts():
    return select(
        TemplateSubscription.source_template_id.label("template_id"),
        func.count(TemplateSubscription.id).label("install_count"),
    ).group_by(TemplateSubscription.source_template_id).subquery()


def _item_statement():
    counts = _install_counts()
    install_count = func.coalesce(counts.c.install_count, 0)
    statement = select(
        Template.id, Template.name, Template.description, Template.primary_category,
        Template.owner_user_id, Template.archived_at, Template.origin, Template.source_template_id,
        Template.current_version_id, Template.updated_at,
        TemplatePublication.marketplace_status, TemplatePublication.pricing_mode,
        TemplatePublication.price_amount_minor, TemplatePublication.marketplace_published_at,
        TemplatePublication.current_release_id,
        TemplateRelease.version_label, TemplateRelease.published_at.label("release_published_at"),
        TemplateRelease.change_note.label("release_change_note"), TemplateRelease.version_id.label("release_version_id"),
        TemplateVersion.input_schema.label("release_input_schema"),
        User.username.label("author_username"),
        install_count.label("install_count"),
    ).select_from(Template).join(
        TemplatePublication, TemplatePublication.template_id == Template.id,
    ).join(User, User.id == Template.owner_user_id).outerjoin(
        TemplateRelease, TemplateRelease.id == TemplatePublication.current_release_id,
    ).outerjoin(
        TemplateVersion, TemplateVersion.id == TemplateRelease.version_id,
    ).outerjoin(counts, counts.c.template_id == Template.id)
    return statement, install_count


def catalog(session, *, search=None, category=None, pricing_mode=None, sort="newest", page=1, page_size=24):
    statement, install_count = _item_statement()
    statement = statement.where(*listed_conditions())
    if category:
        statement = statement.where(Template.primary_category == category)
    if pricing_mode in {"free", "paid"}:
        statement = statement.where(TemplatePublication.pricing_mode == pricing_mode)
    if search:
        statement = statement.where(or_(
            Template.name.contains(search, autoescape=True),
            Template.description.contains(search, autoescape=True),
            Template.primary_category.contains(search, autoescape=True),
            User.username.contains(search, autoescape=True),
        ))
    total = session.scalar(select(func.count()).select_from(statement.subquery()))
    newest = TemplatePublication.marketplace_published_at.desc()
    order = {
        "newest": (newest, Template.id),
        "popular": (install_count.desc(), newest, Template.id),
        "price_asc": (TemplatePublication.price_amount_minor.asc(), newest, Template.id),
        "price_desc": (TemplatePublication.price_amount_minor.desc(), newest, Template.id),
        "name": (Template.name, Template.id),
    }[sort]
    rows = session.execute(statement.order_by(*order).offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return [dict(row) for row in rows], int(total or 0)


def categories(session):
    rows = session.execute(
        select(Template.primary_category, func.count(Template.id)).select_from(Template).join(
            TemplatePublication, TemplatePublication.template_id == Template.id,
        ).where(
            *listed_conditions(), Template.primary_category.isnot(None), Template.primary_category != "",
        ).group_by(Template.primary_category).order_by(func.count(Template.id).desc(), Template.primary_category)
    ).all()
    return [{"name": name, "count": int(count)} for name, count in rows]


def item(session, template_id):
    statement, _ = _item_statement()
    row = session.execute(statement.where(Template.id == str(template_id))).mappings().first()
    return dict(row) if row else None


def received(session, *, user_id, source_template_ids):
    if not source_template_ids:
        return {}
    rows = session.execute(select(TemplateSubscription.source_template_id, TemplateSubscription.local_template_id).where(
        TemplateSubscription.user_id == int(user_id),
        TemplateSubscription.source_template_id.in_([str(value) for value in source_template_ids]),
    )).all()
    return {source_id: local_id for source_id, local_id in rows}


def purchased(session, *, user_id, template_ids):
    if not template_ids:
        return set()
    return set(session.execute(select(PaymentEntitlement.resource_ref_id).where(
        PaymentEntitlement.user_id == int(user_id),
        PaymentEntitlement.resource_type == PRODUCT_TYPE,
        PaymentEntitlement.resource_ref_id.in_([str(value) for value in template_ids]),
        PaymentEntitlement.status == "active",
    )).scalars())


def recent_releases(session, template_id, *, limit=5):
    rows = session.execute(select(
        TemplateRelease.id, TemplateRelease.version_label, TemplateRelease.change_note, TemplateRelease.published_at,
    ).where(TemplateRelease.template_id == str(template_id)).order_by(TemplateRelease.sequence_no.desc()).limit(limit)).mappings()
    return [dict(row) for row in rows]
