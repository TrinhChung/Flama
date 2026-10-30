"""Template publication/subscription persistence; never flush or commit.

Core SQL is intentional: these operations also run in before_commit after
history finalization, where adding dirty ORM rows would recursively flush.
"""

from datetime import datetime
from copy import deepcopy
from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import and_, exists, func, insert, or_, select, update
from sqlalchemy.orm.attributes import set_committed_value

from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.payment_entitlement import PaymentEntitlement
from models.study_application import StudyApplication
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.template_version import TemplateVersion
from models.user import User


@contextmanager
def current_publication_reads(session):
    """Publication must not reconstruct sources from a pre-lock RR snapshot."""
    key = "flama.template.current_publication_reads"
    previous = session.info.get(key)
    session.info[key] = True
    try:
        yield
    finally:
        if previous is None:
            session.info.pop(key, None)
        else:
            session.info[key] = previous


def _execute(session, statement, *args, **kwargs):
    if session.info.get("flama.template.current_publication_reads") and getattr(statement, "is_select", False):
        statement = statement.with_for_update()
    return session.execute(statement, *args, **kwargs)


def one(session, model, *conditions, lock=False):
    statement = select(model.__table__).where(*conditions)
    if lock:
        statement = statement.with_for_update()
    row = _execute(session, statement).mappings().first()
    return dict(row) if row else None


def template(session, template_id, *, lock=False):
    return one(session, Template, Template.id == str(template_id), lock=lock)


def template_owner(session, row):
    return row.get("owner_user_id")


def publication(session, template_id, *, lock=False):
    return one(session, TemplatePublication, TemplatePublication.template_id == template_id, lock=lock)


def ensure_publication(session, template_id):
    row = publication(session, template_id, lock=True)
    if row is None:
        _execute(session, insert(TemplatePublication.__table__).values(template_id=template_id, auto_publish_enabled=False))
        row = publication(session, template_id, lock=True)
    return row


def release(session, release_id, source_template_id=None):
    filters = [TemplateRelease.id == str(release_id)]
    if source_template_id is not None:
        filters.append(TemplateRelease.template_id == source_template_id)
    return one(session, TemplateRelease, *filters)


def version(session, version_id, template_id=None):
    filters = [TemplateVersion.id == str(version_id)]
    if template_id is not None:
        filters.append(TemplateVersion.template_id == template_id)
    return one(session, TemplateVersion, *filters)


def releases(session, template_id, *, limit=100, before_sequence=None):
    statement = select(TemplateRelease.__table__).where(TemplateRelease.template_id == template_id)
    if before_sequence is not None:
        statement = statement.where(TemplateRelease.sequence_no < before_sequence)
    return [dict(row) for row in _execute(session, statement.order_by(TemplateRelease.sequence_no.desc()).limit(limit)).mappings()]


def update_row(session, model, conditions, values):
    _execute(session, update(model.__table__).where(*conditions).values(**values))
    # Keep already-loaded objects coherent without enrolling them in a flush.
    for obj in list(session.identity_map.values()):
        if isinstance(obj, model):
            key = "template_id" if model is TemplatePublication else "id"
            row = one(session, model, getattr(model, key) == getattr(obj, key))
            if row:
                for field in values:
                    set_committed_value(obj, field, row[field])


def subscription(session, *, user_id, source_template_id=None, local_template_id=None, lock=False):
    filters = [TemplateSubscription.user_id == int(user_id)]
    if source_template_id is not None:
        filters.append(TemplateSubscription.source_template_id == str(source_template_id))
    if local_template_id is not None:
        filters.append(TemplateSubscription.local_template_id == str(local_template_id))
    return one(session, TemplateSubscription, *filters, lock=lock)


def source_access(session, *, user_id, source_template_id):
    """Only a license, free original listing or valid deck grants receipt.

    A visible free NoteType may reference paid third-party definitions and is
    never itself proof of a template license. Bundle receipt issues canonical
    subscriptions/entitlements; legacy copy evidence is resolved centrally.
    """
    app = StudyApplication.__table__
    template_row = template(session, source_template_id)
    if template_row is None:
        return False
    from app.repositories.note_type_bundle_repository import licensed_template_ids
    if source_template_id in licensed_template_ids(session, user_id=user_id,
            template_ids=[source_template_id], current_read=True):
        return True
    now = datetime.utcnow()
    rights = _execute(session, select(PaymentEntitlement.status, PaymentEntitlement.effective_from,
        PaymentEntitlement.expires_at).where(PaymentEntitlement.user_id == user_id,
            PaymentEntitlement.resource_type == "template",
            PaymentEntitlement.resource_ref_id == source_template_id).with_for_update()).all()
    negative_right = any(status in {"revoked", "refunded", "expired"} or
        (status == "active" and ((effective is not None and effective > now)
            or (expires is not None and expires <= now))) for status, effective, expires in rights)
    note_types = select(app.c.note_type_id).where(app.c.template_id == source_template_id)
    installed_deck = select(DeckInstall.id).join(DeckMarketplaceItem,
        DeckMarketplaceItem.id == DeckInstall.deck_item_id).where(
        DeckInstall.user_id == user_id, DeckInstall.source_note_type_id.in_(note_types),
        DeckMarketplaceItem.owner_user_id == template_row["owner_user_id"],
    ).limit(1)
    if not negative_right and template_row.get("origin") == "authored" and not template_row.get("source_template_id") and _execute(session, installed_deck).first():
        return True
    from app.repositories import template_marketplace_repository
    return template_marketplace_repository.marketplace_access(session, user_id=user_id, template_id=source_template_id)


def lock_user(session, user_id):
    return one(session, User, User.id == user_id, lock=True)


def install(session, *, user_id, install_id):
    return one(session, DeckInstall, DeckInstall.id == str(install_id), DeckInstall.user_id == int(user_id))


def source_applications(session, note_type_ids):
    statement = select(StudyApplication.__table__).where(
        StudyApplication.note_type_id.in_(sorted(set(note_type_ids))),
        StudyApplication.status_code == "ACTIVE",
    ).order_by(StudyApplication.template_id, StudyApplication.id)
    return [dict(row) for row in _execute(session, statement).mappings()]


def active_templates(session, note_type_id):
    """Resolve reusable templates through active attachments, not legacy origin."""
    statement = select(Template.__table__).join(
        StudyApplication.__table__, StudyApplication.template_id == Template.id,
    ).where(
        StudyApplication.note_type_id == note_type_id,
        StudyApplication.status_code == "ACTIVE",
    ).distinct().order_by(Template.id)
    return [dict(row) for row in _execute(session, statement).mappings()]


def deck_pins(session, deck_release_id):
    return {row["source_template_id"]: dict(row) for row in _execute(session,
        select(DeckReleaseTemplatePin.__table__).where(DeckReleaseTemplatePin.deck_release_id == deck_release_id)
    ).mappings()}


def load_effective_template_overrides(session, *, user_id, source_template_ids, release_pins=None):
    """Resolve deck pins plus personal edits, never another deck's upstream update.

    A canonical user copy is shared across installs. Its clean upstream content
    must not override a different deck's pin. Only changes relative to that
    copy's applied release are personal overrides of the deck's frozen content.
    """
    ids = sorted(set(str(value) for value in source_template_ids))
    pins = release_pins or {}
    rows = []
    for offset in range(0, len(ids), 500):
        rows.extend(_execute(session, select(
            TemplateSubscription.__table__,
            Template.__table__.c.front_html.label("effective_front_html"),
            Template.__table__.c.back_html.label("effective_back_html"),
            Template.__table__.c.shared_css.label("effective_shared_css"),
            Template.__table__.c.input_schema.label("effective_input_schema"),
            Template.__table__.c.current_version_id.label("effective_version_id"),
            Template.__table__.c.updated_at.label("effective_updated_at"),
        ).join(Template.__table__, Template.id == TemplateSubscription.local_template_id).where(
            TemplateSubscription.user_id == int(user_id),
            TemplateSubscription.source_template_id.in_(ids[offset:offset + 500]),
        )).mappings().all())
    subscriptions = {row["source_template_id"]: row for row in rows}
    release_ids = {
        pins[value].get("template_release_id") if isinstance(pins[value], dict) else pins[value].template_release_id
        for value in ids if value in pins
    }
    release_ids.update(row["applied_release_id"] for row in rows if row["source_template_id"] in pins)
    releases_by_id = {}
    release_ids = sorted(value for value in release_ids if value)
    for offset in range(0, len(release_ids), 500):
        releases_by_id.update({row["id"]: dict(row) for row in _execute(session, select(
            TemplateRelease.__table__, TemplateVersion.front_html, TemplateVersion.back_html,
            TemplateVersion.shared_css, TemplateVersion.input_schema,
        ).join(TemplateVersion.__table__, TemplateVersion.id == TemplateRelease.version_id).where(
            TemplateRelease.id.in_(release_ids[offset:offset + 500]))).mappings()})
    result = {}
    for source_id in ids:
        pin = pins.get(source_id)
        local = subscriptions.get(source_id)
        pinned = None
        apps = {}
        if pin is not None:
            release_id = pin.get("template_release_id") if isinstance(pin, dict) else pin.template_release_id
            pinned = releases_by_id.get(release_id)
            if pinned is None or pinned["template_id"] != source_id:
                raise ValueError("Invalid immutable deck template release pin.")
            apps = pin.get("applications_json", {}) if isinstance(pin, dict) else pin.applications_json
        if local is None and pinned is None:
            continue
        if local is None:
            content, customized = {key: deepcopy(pinned[key]) for key in _CONTENT_KEYS}, False
        elif pinned is None:
            content, customized = {key: deepcopy(local[f"effective_{key}"]) for key in _CONTENT_KEYS}, True
        else:
            base = releases_by_id.get(local["applied_release_id"])
            if base is None or base["template_id"] != source_id:
                raise ValueError("Invalid received template release.")
            content, customized = resolve_pinned_content(pinned, base, {
                key: local[f"effective_{key}"] for key in _CONTENT_KEYS
            })
        version_id = local["effective_version_id"] if local and (pinned is None or customized) else pinned["version_id"]
        result[source_id] = SimpleNamespace(
            id=source_id, market_template_id=local["local_template_id"] if local else None,
            **content, effective_version_id=version_id, current_version_id=version_id,
            updated_at=local["effective_updated_at"] if local and customized else pinned["published_at"],
            application_bindings=apps or {}, has_local_changes=customized,
        )
    return result


_CONTENT_KEYS = ("front_html", "back_html", "shared_css", "input_schema")


def resolve_pinned_content(pinned, applied, local):
    """Project explicit personal edits onto one deck's immutable presentation."""
    result = {}
    customized = False
    for key in _CONTENT_KEYS:
        mine = local.get(key) or ([] if key == "input_schema" else "")
        base = applied.get(key) or ([] if key == "input_schema" else "")
        changed = mine != base
        customized = customized or changed
        result[key] = deepcopy(mine if changed else pinned.get(key) or ([] if key == "input_schema" else ""))
    return result, customized
