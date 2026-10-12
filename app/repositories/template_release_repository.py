"""Template publication/subscription persistence; never flush or commit.

Core SQL is intentional: these operations also run in before_commit after
history finalization, where adding dirty ORM rows would recursively flush.
"""

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import and_, exists, func, insert, or_, select, update
from sqlalchemy.orm.attributes import set_committed_value

from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.template_version import TemplateVersion
from models.user import User


def one(session, model, *conditions, lock=False):
    statement = select(model.__table__).where(*conditions)
    if lock:
        statement = statement.with_for_update()
    row = session.execute(statement).mappings().first()
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
        session.execute(insert(TemplatePublication.__table__).values(template_id=template_id, auto_publish_enabled=False))
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
    return [dict(row) for row in session.execute(statement.order_by(TemplateRelease.sequence_no.desc()).limit(limit)).mappings()]


def update_row(session, model, conditions, values):
    session.execute(update(model.__table__).where(*conditions).values(**values))
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
    """A received/purchased deck or NoteType grants initial template receipt."""
    app = StudyApplication.__table__
    template_row = template(session, source_template_id)
    if template_row is None:
        return False
    note_types = select(app.c.note_type_id).where(app.c.template_id == source_template_id)
    for model, column in ((DeckInstall, DeckInstall.source_note_type_id), (NoteTypeInstall, NoteTypeInstall.source_note_type_id)):
        statement = select(model.id).where(
            model.user_id == user_id,
            column.in_(note_types),
        ).limit(1)
        if session.execute(statement).first():
            return True
    free_published = select(NoteType.id).where(
        NoteType.id.in_(note_types),
        NoteType.publish_status.in_(["published", "unlisted"]),
        NoteType.pricing_mode == "free",
    ).limit(1)
    if session.execute(free_published).first():
        return True
    return False


def subscriptions_for_source(session, source_template_id, *, automatic_only=False):
    statement = select(TemplateSubscription.__table__).where(TemplateSubscription.source_template_id == source_template_id)
    if automatic_only:
        statement = statement.where(TemplateSubscription.auto_update_enabled.is_(True))
    return [dict(row) for row in session.execute(statement.order_by(TemplateSubscription.local_template_id)).mappings()]


def lock_user(session, user_id):
    return one(session, User, User.id == user_id, lock=True)


def install(session, *, user_id, install_id):
    return one(session, DeckInstall, DeckInstall.id == str(install_id), DeckInstall.user_id == int(user_id))


def source_applications(session, note_type_ids):
    statement = select(StudyApplication.__table__).where(
        StudyApplication.note_type_id.in_(sorted(set(note_type_ids))),
        StudyApplication.status_code == "ACTIVE",
    ).order_by(StudyApplication.template_id, StudyApplication.id)
    return [dict(row) for row in session.execute(statement).mappings()]


def active_templates(session, note_type_id):
    """Resolve reusable templates through active attachments, not legacy origin."""
    statement = select(Template.__table__).join(
        StudyApplication.__table__, StudyApplication.template_id == Template.id,
    ).where(
        StudyApplication.note_type_id == note_type_id,
        StudyApplication.status_code == "ACTIVE",
    ).distinct().order_by(Template.id)
    return [dict(row) for row in session.execute(statement).mappings()]


def deck_pins(session, deck_release_id):
    return {row["source_template_id"]: dict(row) for row in session.execute(
        select(DeckReleaseTemplatePin.__table__).where(DeckReleaseTemplatePin.deck_release_id == deck_release_id)
    ).mappings()}


def load_effective_template_overrides(session, *, user_id, source_template_ids, release_pins=None):
    """Batch source-ID-keyed effective templates, preserving artifact identity."""
    ids = sorted(set(str(value) for value in source_template_ids))
    pins = release_pins or {}
    rows = []
    for offset in range(0, len(ids), 500):
        rows.extend(session.execute(select(
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
    result = {}
    for row in rows:
        source_id = row["source_template_id"]
        pin = pins.get(source_id)
        apps = pin.get("applications_json", {}) if isinstance(pin, dict) else getattr(pin, "applications_json", {})
        result[source_id] = SimpleNamespace(
            id=source_id, market_template_id=row["local_template_id"],
            front_html=row["effective_front_html"], back_html=row["effective_back_html"],
            shared_css=row["effective_shared_css"], input_schema=row["effective_input_schema"] or [],
            effective_version_id=row["effective_version_id"], current_version_id=row["effective_version_id"],
            updated_at=row["effective_updated_at"], application_bindings=apps or {},
        )
    missing = [value for value in ids if value not in result and value in pins]
    release_ids = {
        pins[value].get("template_release_id") if isinstance(pins[value], dict) else pins[value].template_release_id
        for value in missing
    }
    releases_by_id = {}
    if release_ids:
        releases_by_id = {row["id"]: dict(row) for row in session.execute(select(
            TemplateRelease.__table__, TemplateVersion.front_html, TemplateVersion.back_html,
            TemplateVersion.shared_css, TemplateVersion.input_schema,
        ).join(TemplateVersion.__table__, TemplateVersion.id == TemplateRelease.version_id).where(TemplateRelease.id.in_(release_ids))).mappings()}
    for source_id in missing:
        pin = pins[source_id]
        release_id = pin.get("template_release_id") if isinstance(pin, dict) else pin.template_release_id
        row = releases_by_id.get(release_id)
        if row is None or row["template_id"] != source_id:
            raise ValueError("Invalid immutable deck template release pin.")
        apps = pin.get("applications_json", {}) if isinstance(pin, dict) else pin.applications_json
        result[source_id] = SimpleNamespace(
            id=source_id, market_template_id=None, front_html=row["front_html"], back_html=row["back_html"],
            shared_css=row["shared_css"], input_schema=row["input_schema"], effective_version_id=row["version_id"],
            current_version_id=row["version_id"], updated_at=row["published_at"], application_bindings=apps or {},
        )
    return result
