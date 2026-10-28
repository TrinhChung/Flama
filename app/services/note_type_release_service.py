"""Publish and receive a complete NoteType without consulting mutable drafts.

Legacy publications intentionally have no invented historical snapshot. Their
author must publish once to establish a complete release before new receipts.
"""

from copy import deepcopy
from datetime import datetime
import hashlib
import json

from sqlalchemy import select

from app.repositories import note_type_release_repository as repository
from app.services import release_core
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_release import NoteTypeRelease
from models.study_application import StudyApplication

METADATA_KEYS = ("name", "description", "primary_category", "tags", "taxonomy_metadata",
    "preview_text", "preview_image_url", "changelog")
FIELD_KEYS = ("id", "name", "field_type", "position", "required", "identity_role")
APPLICATION_KEYS = ("id", "template_id", "note_type_id", "occurrence_key", "source_ord",
    "input_bindings", "display_name", "position", "is_default")


class NoteTypeReleaseError(Exception):
    def __init__(self, code, message, *, status=409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def stage_publication(session, *, note_type, actor_user_id):
    """Explicit author action only; caller owns commit/rollback."""
    from app.services.template_release_service import stage_note_type_publications
    if note_type.user_id != actor_user_id:
        raise NoteTypeReleaseError("NOTE_TYPE_ACCESS_DENIED", "Only the author can publish a Note Type release.", status=403)
    session.flush()
    repository.lock_source(session, note_type.id)
    if repository.is_received_note_type(session, note_type.id):
        raise NoteTypeReleaseError("NOTE_TYPE_REPUBLISH_FORBIDDEN", "Installed Note Types cannot be published again.", status=403)
    releases = stage_note_type_publications(session, note_type_id=note_type.id, actor_user_id=actor_user_id)
    from app.services.note_type_bundle_publication_service import references
    references_by_id = {item["attached"]["id"]: item for item in references(
        session, note_type_id=note_type.id, actor_user_id=actor_user_id)}
    fields = session.execute(select(FieldDef).where(FieldDef.note_type_id == note_type.id)
        .order_by(FieldDef.position, FieldDef.id)).scalars().all()
    applications = session.execute(select(StudyApplication).where(
        StudyApplication.note_type_id == note_type.id, StudyApplication.status_code == "ACTIVE")
        .order_by(StudyApplication.position, StudyApplication.id)).scalars().all()
    manifest = {
        "codec": "note-type-release.v1",
        "commerce_version": "note-type-bundle.v1",
        "metadata": {key: deepcopy(getattr(note_type, key)) for key in METADATA_KEYS},
        "field_schema_revision": int(note_type.field_schema_revision or 0),
        "fields": [{key: deepcopy(getattr(field, key)) for key in FIELD_KEYS} for field in fields],
        "applications": [{**{key: deepcopy(getattr(app, key)) for key in APPLICATION_KEYS},
            "template_id": references_by_id[app.template_id]["source"]["id"],
            "attached_template_id": app.template_id,
            "template_author_user_id": references_by_id[app.template_id]["source"]["owner_user_id"],
            "template_name": references_by_id[app.template_id]["source"]["name"],
            "template_release_id": releases[app.template_id]["id"]} for app in applications],
    }
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    label = str(note_type.version or "").strip()
    if not label or len(label) > 50:
        raise NoteTypeReleaseError("NOTE_TYPE_VERSION_INVALID", "Version must contain 1 to 50 characters.", status=400)
    existing = repository.by_label(session, note_type.id, label)
    if existing and existing.content_hash != digest:
        if existing.id != note_type.current_release_id:
            raise NoteTypeReleaseError("NOTE_TYPE_VERSION_CONFLICT",
                "This version already contains a different Note Type schema or template mapping. Choose a new version.")
        # Republishing edits under the current label continues its sequence;
        # only an explicitly chosen older label is a conflict.
        label = release_core.next_free_version(label, lambda value: repository.by_label(session, note_type.id, value) is not None)
        if len(label) > 50:
            raise NoteTypeReleaseError("NOTE_TYPE_VERSION_INVALID", "Version must contain 1 to 50 characters.", status=400)
        note_type.version = label
        existing = None
    if existing:
        note_type.current_release_id = existing.id
        return existing
    release = NoteTypeRelease(note_type_id=note_type.id, version_label=label,
        sequence_no=repository.next_sequence(session, note_type.id),
        content_hash=digest, manifest_json=manifest, created_by_user_id=actor_user_id)
    session.add(release)
    session.flush()
    note_type.current_release_id = release.id
    return release


def current_release(session, note_type):
    return repository.release(session, note_type.current_release_id, note_type.id)


def released_definition(session, note_type, *, include_definition=True):
    """Stable API definition, including exact template version content."""
    release = current_release(session, note_type)
    if not release:
        return {"current_release_id": None, "release_available": False,
            "requires_author_republish": True, "field_defs": [], "templates": []}
    manifest = release.manifest_json
    result = {**deepcopy(manifest["metadata"]), "title": manifest["metadata"]["name"],
        "current_release_id": release.id, "release_available": True, "requires_author_republish": False,
        "version": release.version_label, "published_at": release.published_at.isoformat(),
        "field_schema_revision": manifest["field_schema_revision"]}
    if not include_definition:
        return result
    contents = repository.template_contents(session, [app["template_release_id"] for app in manifest["applications"]])
    templates = []
    for app in manifest["applications"]:
        content = contents.get(app["template_release_id"])
        if not content or content["source_template_id"] != app["template_id"]:
            raise NoteTypeReleaseError("NOTE_TYPE_RELEASE_INCOMPLETE", "A published template version is unavailable.")
        templates.append({"id": app["template_id"], "note_type_id": note_type.id,
            "application_id": app["id"], "template_release_id": app["template_release_id"],
            "template_author_user_id": app.get("template_author_user_id"),
            "name": app.get("display_name") or app.get("template_name") or "Card",
            **{key: deepcopy(content[key]) for key in ("front_html", "back_html", "shared_css", "input_schema")},
            **{key: deepcopy(app.get(key)) for key in ("input_bindings", "position", "is_default", "occurrence_key", "source_ord")},
            "current_version_id": content["id"], "updated_at": release.published_at.isoformat()})
    return {**result,
        "field_defs": [{**deepcopy(field), "note_type_id": note_type.id} for field in manifest["fields"]],
        "templates": templates}


def stage_receipt(session, *, source_note_type, user_id, installed_at=None, purchase_amount_minor=0,
        purchased_at=None, access_granted=False, release_id=None):
    """Canonical free/paid receipt. Reinstall reuses provenance and its release."""
    from app.repositories.template_release_repository import lock_user
    from app.services.share.helpers import make_unique_note_type_name
    from app.services.share.constants import MARKET_ACTIVITY_POLICY_VERSION
    if source_note_type.user_id == user_id:
        raise NoteTypeReleaseError("NOTE_TYPE_ACCESS_DENIED", "Owner cannot install their own Note Type.")
    # Take the parent X lock before a receipt flush acquires its FK S lock.
    # Keep the same installer -> source -> receipt order as deck installs.
    with session.no_autoflush:
        lock_user(session, user_id)
        repository.lock_source(session, source_note_type.id)
        install = repository.install(session, source_note_type.id, user_id)
    if install and install.installed_note_type_id and session.get(
            NoteType, install.installed_note_type_id, with_for_update=True):
        return install, False
    if install and not install.applied_release_id and release_id is None:
        raise NoteTypeReleaseError("NOTE_TYPE_LEGACY_RELEASE_UNKNOWN",
            "This legacy installation has no recorded historical release to restore.")
    if source_note_type.pricing_mode == "paid" and not access_granted and install is None:
        raise NoteTypeReleaseError("PAYMENT_REQUIRED", "Payment is required before receiving this Note Type.", status=402)
    # A restored installation receives its original release, never the latest draft.
    target_id = install.applied_release_id if install and install.applied_release_id else release_id
    release = repository.release(session, target_id, source_note_type.id) if target_id else current_release(session, source_note_type)
    if release is None:
        raise NoteTypeReleaseError("NOTE_TYPE_RELEASE_NOT_READY",
            "The author must publish a complete Note Type release before it can be installed.")
    from app.services.note_type_bundle_pricing_service import require_receipt_access
    require_receipt_access(session, note_type=source_note_type, user_id=user_id,
        release=release, access_granted=(access_granted or install is not None))
    manifest = release.manifest_json
    metadata = deepcopy(manifest["metadata"])
    metadata["name"] = make_unique_note_type_name(user_id, metadata["name"])
    local = NoteType(user_id=user_id, **metadata, version=release.version_label, pricing_mode="free",
        price_amount_minor=0, publish_status="private", is_official=False)
    session.add(local)
    session.flush()
    field_map = {}
    for field in manifest["fields"]:
        copied = FieldDef(note_type_id=local.id, **{key: deepcopy(field.get(key)) for key in FIELD_KEYS if key != "id"})
        session.add(copied)
        session.flush()
        field_map[field["id"]] = copied.id
    now = installed_at or datetime.utcnow()
    created = install is None
    if created:
        install = NoteTypeInstall(source_note_type_id=source_note_type.id, user_id=user_id,
            purchase_amount_minor=int(purchase_amount_minor), purchased_at=purchased_at,
            installed_at=now, market_active=False, market_active_evaluated_at=now,
            market_active_policy_version=MARKET_ACTIVITY_POLICY_VERSION)
        session.add(install)
        from app.services.share.helpers import _increment_counter
        _increment_counter(NoteType, source_note_type.id, NoteType.install_count, 1)
    install.installed_note_type_id = local.id
    install.applied_release_id = release.id
    session.flush()
    for app in manifest["applications"]:
        stage_received_application(session, user_id=user_id, local_note_type_id=local.id,
            source_application=app, template_release_id=app["template_release_id"], field_map=field_map)
    return install, created


def stage_received_application(session, *, user_id, local_note_type_id, source_application,
        template_release_id, field_map):
    """A scoped snapshot keeps one NoteType receipt independent of subscriptions.

    Canonical subscriptions remain visible for update management. Applications
    use a hidden received definition per published release, so updating that
    subscription cannot silently rewrite this complete NoteType publication.
    """
    from app.services.template_release_service import ensure_subscription
    from models.template import Template
    from app.services.template_version_service import mark_template_version
    source_id = source_application["template_id"]
    content = repository.template_contents(session, [template_release_id]).get(template_release_id)
    if not content or content["source_template_id"] != source_id:
        raise NoteTypeReleaseError("NOTE_TYPE_RELEASE_INCOMPLETE", "A published template version is unavailable.")
    source_template = session.get(Template, source_id)
    if source_template is not None and source_template.owner_user_id == user_id:
        subscription = {"source_template_id": source_id, "local_template_id": source_id}
    else:
        subscription = ensure_subscription(session, user_id=user_id, source_template_id=source_id,
            release_id=template_release_id, access_granted=True)
    # Share a frozen definition among occurrences of the same release in this
    # receipt, while keeping canonical editable subscription definitions separate.
    local_template = session.execute(select(Template).join(StudyApplication).where(
        StudyApplication.note_type_id == local_note_type_id, Template.source_template_id == source_id,
        Template.source_version_id == content["id"], Template.archived_at.is_not(None),
    )).scalars().first()
    if local_template is None:
        local_template = Template(owner_user_id=user_id, name=source_application.get("template_name") or "Card",
            origin="market_copy", source_template_id=source_id, source_version_id=content["id"],
            archived_at=datetime.utcnow(), **{key: deepcopy(content[key]) for key in (
                "front_html", "back_html", "shared_css", "input_schema")})
        session.add(local_template)
        mark_template_version(local_template, origin="market_copy", actor_user_id=user_id)
        session.flush()
    bindings = {key: field_map.get(value) for key, value in (source_application.get("input_bindings") or {}).items()}
    session.add(StudyApplication(note_type_id=local_note_type_id, template_id=local_template.id,
        occurrence_key=source_application.get("occurrence_key") or source_application["id"],
        source_ord=source_application.get("source_ord"), input_bindings=bindings,
        display_name=source_application.get("display_name"), position=source_application.get("position", 0),
        is_default=bool(source_application.get("is_default")), status_code="ACTIVE"))
    session.flush()
    return subscription
