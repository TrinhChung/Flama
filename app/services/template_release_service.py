"""Immutable template publication and user-scoped marketplace inheritance.

Public writes own their transaction. Installation, deck publication and the
version event hook stage Core SQL in the caller's transaction without flushing.
"""

from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import event, insert, select, update
from sqlalchemy.orm import Session

from app.repositories import template_release_repository as repository
from app.repositories import template_version_repository
from app.services import release_core
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.model_uuid import uuid_str
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.study_application import StudyApplication
from models.field_def import FieldDef
from models.note_type_install import NoteTypeInstall
from models.note_type import NoteType

CONTENT_KEYS = ("front_html", "back_html", "shared_css", "input_schema")
APPLICATION_PIN_KEYS = ("note_type_id", "occurrence_key", "input_bindings", "is_default", "display_name", "position")
RESOLUTIONS = {"keep_mine", "keep_upstream", "manual"}


class TemplateReleaseError(ValueError):
    def __init__(self, code, message, *, status=400, field=None, details=None):
        super().__init__(message)
        self.code = self.error = code
        self.status = status
        self.field = field
        self.details = details


@event.listens_for(Session, "before_flush")
def _protect_immutable_releases(session, _context, _instances):
    immutable = (TemplateRelease, DeckReleaseTemplatePin)
    if any(isinstance(row, immutable) and session.is_modified(row, include_collections=False) for row in session.dirty) or any(isinstance(row, immutable) for row in session.deleted):
        raise TemplateReleaseError("IMMUTABLE_TEMPLATE_RELEASE", "Published template snapshots and deck pins cannot be modified.", status=409)


@event.listens_for(Session, "after_transaction_end")
def _clear_clone_provenance(session, transaction):
    if transaction.parent is None:
        session.info.pop("flama.template_clone_compat", None)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _body(payload, allowed):
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise TemplateReleaseError("VALIDATION_ERROR", "Request body contains unsupported properties.")
    return payload


def _commit(operation):
    try:
        result = operation()
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def _owned(session, *, user_id, template_id, lock=False):
    row = repository.template(session, template_id, lock=lock)
    if row is None or repository.template_owner(session, row) != int(user_id):
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
    return row


def _authored(row, *, allow_archived=False, session=None):
    from app.services.legacy_template_provenance_service import is_received_template
    if is_received_template(session if session is not None else db.session, row):
        raise TemplateReleaseError("MARKET_TEMPLATE_REPUBLISH_FORBIDDEN", "Received marketplace templates cannot be republished.", status=403)
    if row.get("archived_at") is not None and not allow_archived:
        raise TemplateReleaseError("TEMPLATE_ARCHIVED", "Archived templates cannot be published.", status=409)


def _snapshot(session, row, *, actor_user_id=None, origin="edit"):
    """Initialize/snapshot the actual flushed content before an explicit publish."""
    snapshot = template_version_repository.snapshots(session, [row["id"]])[row["id"]]
    version_id, _ = template_version_repository.append_snapshot(
        session, snapshot, origin=origin, actor_user_id=actor_user_id,
    )
    return repository.version(session, version_id, row["id"])


def _serialize_release(row):
    if row is None:
        return None
    return {key: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


class _TemplatePublishAdapter:
    def __init__(self, session, row, version, actor_user_id):
        self.session = session
        self.row = row
        self.version = version
        self.actor_user_id = actor_user_id
        self.publication = repository.ensure_publication(session, row["id"])
        self.head_id = self.publication["current_release_id"]
        self.revision = version["id"]
        self.head = repository.release(session, self.head_id, row["id"]) if self.head_id else None
        if self.head_id and self.head is None:
            self.fail("RELEASE_HEAD_INVALID", "The published template head is invalid.")

    def fail(self, code, message, *, field=None):
        if field == "expected_working_revision":
            field = "expected_current_version_id"
        raise TemplateReleaseError(code, message, status=409, field=field)

    def find_replay(self, key):
        return repository.one(self.session, TemplateRelease, TemplateRelease.template_id == self.row["id"], TemplateRelease.idempotency_key == key)

    def matches_replay(self, existing, request):
        return (existing["version_label"] == request.version_label
                and existing["parent_release_id"] == request.expected_head_id
                and (existing["change_note"] or None) == (request.change_note or None)
                and (request.expected_revision is None or existing["version_id"] == request.expected_revision))

    def label_exists(self, label):
        return repository.one(self.session, TemplateRelease, TemplateRelease.template_id == self.row["id"], TemplateRelease.version_label == label) is not None

    def plan(self):
        return self.version

    def has_changes(self, plan):
        return self.head is None or self.head["version_id"] != plan["id"]

    def persist(self, plan, request):
        # Locking the Template serializes its publication sequence.
        row = dict(
            id=uuid_str(), template_id=self.row["id"], version_id=plan["id"],
            sequence_no=int(self.head["sequence_no"] if self.head else 0) + 1,
            version_label=request.version_label, parent_release_id=self.head_id,
            publish_mode=request.mode, idempotency_key=request.idempotency_key,
            change_note=request.change_note, created_by_user_id=self.actor_user_id, published_at=_now(),
        )
        self.session.execute(insert(TemplateRelease.__table__).values(**row))
        values = {"current_release_id": row["id"], "updated_at": _now()}
        if request.mode == "automatic":
            values.update(last_auto_published_at=row["published_at"], last_auto_publish_error=None)
        repository.update_row(self.session, TemplatePublication, [TemplatePublication.template_id == self.row["id"]], values)
        _process_auto_updates(self.session, self.row["id"], row["id"])
        return row


def _publish_version(session, row, version, *, actor_user_id, request, allow_archived=False):
    _authored(row, allow_archived=allow_archived, session=session)
    adapter = _TemplatePublishAdapter(session, row, version, actor_user_id)
    return release_core.publish(adapter, request)


def get_publication(*, user_id, template_id):
    row = _owned(db.session, user_id=user_id, template_id=template_id)
    publication = repository.publication(db.session, row["id"]) or {}
    head = repository.release(db.session, publication.get("current_release_id"), row["id"]) if publication.get("current_release_id") else None
    return {
        "template_id": row["id"], "auto_publish_enabled": bool(publication.get("auto_publish_enabled", False)),
        "current_release": _serialize_release(head), "current_version_id": row["current_version_id"],
        "has_unpublished_changes": head is None or head["version_id"] != row["current_version_id"],
        "last_auto_published_at": _serialize_release(publication).get("last_auto_published_at"),
        "last_auto_publish_error": publication.get("last_auto_publish_error"),
    }


def list_releases(*, user_id, template_id, limit=100, before_sequence=None):
    source_id = _read_release_source(user_id=user_id, template_id=template_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise TemplateReleaseError("VALIDATION_ERROR", "limit must be between 1 and 200.", field="limit")
    if before_sequence is not None and (isinstance(before_sequence, bool) or not isinstance(before_sequence, int) or before_sequence < 1):
        raise TemplateReleaseError("VALIDATION_ERROR", "before_sequence must be a positive integer.", field="before_sequence")
    rows = repository.releases(db.session, source_id, limit=limit + 1, before_sequence=before_sequence)
    return {"template_id": template_id, "source_template_id": source_id, "items": [_serialize_release(row) for row in rows[:limit]], "has_more": len(rows) > limit}


def get_release(*, user_id, template_id, release_id):
    source_id = _read_release_source(user_id=user_id, template_id=template_id)
    row = repository.release(db.session, release_id, source_id)
    if row is None:
        raise TemplateReleaseError("TEMPLATE_RELEASE_NOT_FOUND", "Template release not found.", status=404)
    return {**_serialize_release(row), "version": _serialize_release(repository.version(db.session, row["version_id"], source_id))}


def _read_release_source(*, user_id, template_id):
    """A recipient reads immutable upstream releases via their owned copy ID."""
    local = _owned(db.session, user_id=user_id, template_id=template_id)
    from app.services.legacy_template_provenance_service import legacy_reference
    legacy = legacy_reference(db.session, template_id)
    if legacy:
        if not legacy.get("source_template_id"):
            raise TemplateReleaseError("TEMPLATE_LEGACY_SOURCE_UNKNOWN", "The original legacy template cannot be identified safely.", status=409)
        return legacy["source_template_id"]
    if local.get("origin") != "market_copy":
        return template_id
    subscription, _ = _subscription(db.session, user_id=user_id, template_id=template_id)
    return subscription["source_template_id"]


def publish_release(*, user_id, template_id, payload, idempotency_key):
    _body(payload, {"version_label", "change_note", "expected_current_release_id", "expected_current_version_id"})
    label = payload.get("version_label")
    if not isinstance(label, str) or not label.strip() or len(label.strip()) > 50:
        raise TemplateReleaseError("VALIDATION_ERROR", "version_label must contain 1 to 50 characters.", field="version_label")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key.strip()) > 64:
        raise TemplateReleaseError("IDEMPOTENCY_KEY_REQUIRED", "A valid Idempotency-Key is required.", field="Idempotency-Key")
    for key in ("expected_current_release_id", "expected_current_version_id"):
        if key not in payload or (payload[key] is not None and not isinstance(payload[key], str)):
            raise TemplateReleaseError("VALIDATION_ERROR", f"{key} is required.", field=key)
    note = payload.get("change_note")
    if note is not None and (not isinstance(note, str) or len(note) > 1000):
        raise TemplateReleaseError("VALIDATION_ERROR", "change_note must be at most 1000 characters.", field="change_note")

    def operation():
        row = _owned(db.session, user_id=user_id, template_id=template_id, lock=True)
        _authored(row, session=db.session)
        version = _snapshot(db.session, row, actor_user_id=user_id)
        request = release_core.PublishRequest(label.strip(), idempotency_key.strip(), payload["expected_current_release_id"], payload["expected_current_version_id"], note.strip() if note else None)
        release, replayed = _publish_version(db.session, row, version, actor_user_id=user_id, request=request)
        return {"release": _serialize_release(release), "replayed": replayed}
    return _commit(operation)


def update_publication_settings(*, user_id, template_id, payload):
    _body(payload, {"auto_publish_enabled"})
    enabled = payload.get("auto_publish_enabled")
    if not isinstance(enabled, bool):
        raise TemplateReleaseError("VALIDATION_ERROR", "auto_publish_enabled must be boolean.", field="auto_publish_enabled")
    def operation():
        row = _owned(db.session, user_id=user_id, template_id=template_id, lock=True)
        _authored(row, session=db.session)
        repository.ensure_publication(db.session, row["id"])
        repository.update_row(db.session, TemplatePublication, [TemplatePublication.template_id == row["id"]], {"auto_publish_enabled": enabled, "updated_at": _now()})
        if enabled:
            version = _snapshot(db.session, row, actor_user_id=user_id)
            on_version_appended(db.session, template_id=row["id"], version_id=version["id"], actor_user_id=user_id)
        return get_publication(user_id=user_id, template_id=template_id)
    return _commit(operation)


def on_version_appended(session, template_id, version_id, actor_user_id=None, change_note=None):
    """Core-only hook called after an immutable history snapshot is appended."""
    with session.no_autoflush:
        return _on_version_appended(session, template_id, version_id, actor_user_id, change_note)


def _on_version_appended(session, template_id, version_id, actor_user_id=None, change_note=None):
    row = repository.template(session, template_id)
    publication = repository.publication(session, template_id)
    if row is None or row.get("archived_at") is not None or not publication or not publication["auto_publish_enabled"]:
        return None
    from app.services.legacy_template_provenance_service import is_received_template
    if is_received_template(session, row):
        return None
    _authored(row, session=session)
    version = repository.version(session, version_id, template_id)
    if version is None:
        raise TemplateReleaseError("TEMPLATE_VERSION_NOT_FOUND", "Template version not found.", status=409)
    head = repository.release(session, publication["current_release_id"], template_id) if publication["current_release_id"] else None
    head_version = repository.version(session, head["version_id"], template_id) if head else None
    if not release_core.should_auto_publish(enabled=True, eligible=True, revision=int(version["version_no"]), published_revision=int(head_version["version_no"]) if head_version else None):
        return None
    request = release_core.PublishRequest(
        release_core.next_auto_version(head["version_label"] if head else None),
        f"auto:{version_id}", publication["current_release_id"], version_id,
        change_note or "Tự động phát hành bản cập nhật.", "automatic",
    )
    return _publish_version(session, row, version, actor_user_id=actor_user_id or repository.template_owner(session, row), request=request)[0]


def _subscription(session, *, user_id, template_id, lock=False):
    local = _owned(session, user_id=user_id, template_id=template_id, lock=lock)
    subscription = repository.subscription(session, user_id=user_id, local_template_id=template_id, lock=lock)
    if subscription is None:
        from app.services.legacy_template_provenance_service import legacy_reference
        if legacy_reference(session, template_id):
            raise TemplateReleaseError("TEMPLATE_LEGACY_RELEASE_UNKNOWN",
                "This legacy copy has no known received release. Its content is preserved; receive the original separately to manage future updates.", status=409)
    if subscription is None or local.get("origin") != "market_copy":
        raise TemplateReleaseError("TEMPLATE_SUBSCRIPTION_NOT_FOUND", "Received template not found.", status=404)
    return subscription, local


def ensure_subscription(session, *, user_id, source_template_id, release_id=None, access_granted=False):
    """``access_granted`` is only for payment fulfillment, before its entitlement is active."""
    # Serialize first receipt across multiple deck installs for the same user.
    if repository.lock_user(session, int(user_id)) is None:
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "User not found.", status=404)
    # A current read is required after waiting for the user lock: a previous
    # request SELECT may already have established a REPEATABLE READ snapshot.
    existing = repository.subscription(session, user_id=user_id, source_template_id=source_template_id, lock=True)
    if existing:
        return existing  # another install must never downgrade or overwrite this copy
    source = repository.template(session, source_template_id)
    if source is None or repository.template_owner(session, source) == user_id or not (access_granted or repository.source_access(session, user_id=user_id, source_template_id=source_template_id)):
        raise TemplateReleaseError("TEMPLATE_ACCESS_DENIED", "An installed deck or NoteType is required to receive this template.", status=403)
    _authored(source, allow_archived=True, session=session)
    publication = repository.publication(session, source_template_id)
    target = repository.release(session, release_id or (publication or {}).get("current_release_id"), source_template_id)
    if target is None:
        raise TemplateReleaseError("TEMPLATE_RELEASE_NOT_READY", "This template has no published version available.", status=409)
    content = repository.version(session, target["version_id"], source_template_id)
    local_id = uuid_str()
    now = _now()
    session.execute(insert(Template.__table__).values(
        id=local_id, owner_user_id=int(user_id), name=source["name"],
        description=source.get("description") or "", primary_category=source.get("primary_category") or "",
        origin="market_copy", source_template_id=source_template_id, source_version_id=content["id"],
        **{key: deepcopy(content[key]) for key in CONTENT_KEYS}, position=0, is_default=False,
        created_at=now, updated_at=now,
    ))
    _snapshot(session, repository.template(session, local_id), actor_user_id=user_id, origin="market_copy")
    subscription = dict(
        id=uuid_str(), user_id=int(user_id), source_template_id=source_template_id, local_template_id=local_id,
        applied_release_id=target["id"], seen_release_id=target["id"], auto_update_enabled=False,
        pending_update_json=None, last_sync_status="synced", last_synced_at=now, created_at=now, updated_at=now,
    )
    session.execute(insert(TemplateSubscription.__table__).values(**subscription))
    return subscription


def _subscription_dto(session, subscription, local):
    source_id = subscription["source_template_id"]
    publication = repository.publication(session, source_id) or {}
    head = repository.release(session, publication.get("current_release_id"), source_id) if publication.get("current_release_id") else None
    applied = repository.release(session, subscription["applied_release_id"], source_id)
    return {
        **_serialize_release(subscription), "template_id": local["id"], "current_version_id": local["current_version_id"],
        "current_release": _serialize_release(head), "applied_release": _serialize_release(applied),
        "update_available": bool(head and applied and head["sequence_no"] > applied["sequence_no"]),
        "template": _serialize_release(local),
    }


def get_subscription(*, user_id, template_id):
    from app.services.legacy_template_provenance_service import legacy_subscription
    legacy = legacy_subscription(db.session, user_id=user_id, template_id=template_id)
    if legacy is not None:
        legacy["current_release"] = _serialize_release(legacy["current_release"])
        legacy["template"] = _serialize_release(legacy["template"])
        return legacy
    subscription, local = _subscription(db.session, user_id=user_id, template_id=template_id)
    return _subscription_dto(db.session, subscription, local)


def _prepare(session, subscription, local, payload, *, automatic=False):
    target = repository.release(session, payload.get("release_id"), subscription["source_template_id"])
    applied = repository.release(session, subscription["applied_release_id"], subscription["source_template_id"])
    if target is None or applied is None:
        raise TemplateReleaseError("TEMPLATE_RELEASE_NOT_FOUND", "Template release not found.", status=404)
    if target["sequence_no"] <= applied["sequence_no"]:
        raise TemplateReleaseError("NO_TEMPLATE_UPDATE", "The target is not a newer release.", status=409)
    current = _snapshot(session, local, actor_user_id=subscription["user_id"])
    pending = subscription.get("pending_update_json")
    key = payload.get("idempotency_key")
    if key is not None and (not isinstance(key, str) or not key.strip() or len(key) > 64):
        raise TemplateReleaseError("VALIDATION_ERROR", "idempotency_key must contain 1 to 64 characters.", field="idempotency_key")
    if pending and key and pending.get("idempotency_key") == key:
        if pending["to_release_id"] != target["id"] or pending["expected_local_version_id"] != current["id"]:
            raise TemplateReleaseError("IDEMPOTENCY_KEY_REUSED", "The preparation key was used for another update.", status=409)
        return pending
    if "expected_applied_release_id" in payload and payload["expected_applied_release_id"] != applied["id"]:
        raise TemplateReleaseError("APPLIED_RELEASE_STALE", "The received release changed.", status=409)
    if "expected_current_version_id" in payload and payload["expected_current_version_id"] != current["id"]:
        raise TemplateReleaseError("LOCAL_VERSION_STALE", "Local template edits changed.", status=409)
    base = repository.version(session, applied["version_id"], subscription["source_template_id"])
    upstream = repository.version(session, target["version_id"], subscription["source_template_id"])
    conflicts = {name: {"base": base[name], "upstream": upstream[name], "local": current[name]} for name in CONTENT_KEYS if release_core.has_conflict(base[name], upstream[name], current[name])}
    pending = dict(
        id=uuid_str(), from_release_id=applied["id"], to_release_id=target["id"],
        expected_local_version_id=current["id"], status="has_conflict" if conflicts else "ready",
        conflicts=conflicts, idempotency_key=key, mode="automatic" if automatic else "manual",
    )
    repository.update_row(session, TemplateSubscription, [TemplateSubscription.id == subscription["id"]], {
        "pending_update_json": pending, "last_sync_status": "conflict" if conflicts else "ready", "updated_at": _now(),
    })
    return pending


def prepare_update(*, user_id, template_id, payload):
    _body(payload, {"release_id", "expected_applied_release_id", "expected_current_version_id", "idempotency_key"})
    def operation():
        subscription, local = _subscription(db.session, user_id=user_id, template_id=template_id, lock=True)
        return _prepare(db.session, subscription, local, payload)
    return _commit(operation)


def _validate_resolutions(resolutions, conflicts):
    if not isinstance(resolutions, dict) or set(resolutions) - set(conflicts):
        raise TemplateReleaseError("VALIDATION_ERROR", "Only conflicted content properties can be resolved.", field="resolutions")
    for name, resolution in resolutions.items():
        if not isinstance(resolution, dict) or set(resolution) - {"mode", "value"} or resolution.get("mode") not in RESOLUTIONS:
            raise TemplateReleaseError("VALIDATION_ERROR", "Invalid conflict resolution.", field="resolutions")
        if resolution["mode"] == "manual":
            value = resolution.get("value")
            if name == "input_schema":
                from app.services.template_library_service import validate_input_schema
                try:
                    validate_input_schema(value)
                except ValueError as exc:
                    raise TemplateReleaseError("VALIDATION_ERROR", str(exc), field="input_schema") from exc
            elif not isinstance(value, str):
                raise TemplateReleaseError("VALIDATION_ERROR", "Manual content must be a string.", field=name)
        elif "value" in resolution:
            raise TemplateReleaseError("VALIDATION_ERROR", "Only manual resolutions accept a value.", field=name)


def _write_local(session, subscription, local, content, target):
    from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
    from types import SimpleNamespace
    try:
        render_template_pair(template=SimpleNamespace(id=local["id"], **content), field_defs=[], field_values={}, media_assets=[], preview_note_key="template-update-validation")
    except TemplateCompileError as exc:
        raise TemplateReleaseError("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html") from exc
    repository.update_row(session, Template, [Template.id == local["id"]], {
        **content, "source_version_id": target["version_id"], "updated_at": _now(),
    })
    _snapshot(session, repository.template(session, local["id"]), actor_user_id=subscription["user_id"], origin="update")
    repository.update_row(session, TemplateSubscription, [TemplateSubscription.id == subscription["id"]], {
        "applied_release_id": target["id"], "seen_release_id": target["id"], "pending_update_json": None,
        "last_sync_status": "synced", "last_synced_at": _now(), "updated_at": _now(),
    })


def _apply(session, subscription, local, payload):
    pending = subscription.get("pending_update_json")
    if not pending or payload.get("preparation_id") != pending["id"]:
        raise TemplateReleaseError("TEMPLATE_UPDATE_NOT_FOUND", "Update preparation not found.", status=404)
    current = _snapshot(session, local, actor_user_id=subscription["user_id"])
    if subscription["applied_release_id"] != pending["from_release_id"] or current["id"] != pending["expected_local_version_id"]:
        raise TemplateReleaseError("TEMPLATE_UPDATE_STALE", "The received release or local content changed. Prepare again.", status=409)
    resolutions = payload.get("resolutions", {})
    _validate_resolutions(resolutions, pending["conflicts"])
    if set(pending["conflicts"]) - set(resolutions):
        raise TemplateReleaseError("REBASE_CONFLICTS_UNRESOLVED", "Resolve all conflicts before applying this update.", status=409, details={"preparation": pending})
    target = repository.release(session, pending["to_release_id"], subscription["source_template_id"])
    applied = repository.release(session, pending["from_release_id"], subscription["source_template_id"])
    base = repository.version(session, applied["version_id"], subscription["source_template_id"])
    upstream = repository.version(session, target["version_id"], subscription["source_template_id"])
    content = {}
    for name in CONTENT_KEYS:
        resolution = resolutions.get(name, {})
        action, value = release_core.merge_unit(base[name], upstream[name], current[name], resolution=resolution.get("mode"), manual_value=resolution.get("value"))
        if action == "conflict":
            raise TemplateReleaseError("REBASE_CONFLICTS_UNRESOLVED", "Resolve all conflicts before applying.", status=409)
        content[name] = deepcopy(value)
    _write_local(session, subscription, local, content, target)
    return _subscription_dto(session, repository.subscription(session, user_id=subscription["user_id"], local_template_id=local["id"]), repository.template(session, local["id"]))


def apply_update(*, user_id, template_id, payload):
    _body(payload, {"preparation_id", "resolutions"})
    def operation():
        subscription, local = _subscription(db.session, user_id=user_id, template_id=template_id, lock=True)
        return _apply(db.session, subscription, local, payload)
    return _commit(operation)


def reset_to_upstream(*, user_id, template_id, payload=None):
    _body(payload or {}, set())
    def operation():
        subscription, local = _subscription(db.session, user_id=user_id, template_id=template_id, lock=True)
        target = repository.release(db.session, subscription["applied_release_id"], subscription["source_template_id"])
        upstream = repository.version(db.session, target["version_id"], subscription["source_template_id"])
        _write_local(db.session, subscription, local, {name: deepcopy(upstream[name]) for name in CONTENT_KEYS}, target)
        return get_subscription(user_id=user_id, template_id=template_id)
    return _commit(operation)


def _process_auto_updates(session, source_template_id, release_id):
    for subscription in repository.subscriptions_for_source(session, source_template_id, automatic_only=True):
        if subscription["applied_release_id"] == release_id:
            continue
        local = repository.template(session, subscription["local_template_id"], lock=True)
        pending = _prepare(session, subscription, local, {"release_id": release_id}, automatic=True)
        if pending["status"] == "ready":
            subscription["pending_update_json"] = pending
            _apply(session, subscription, local, {"preparation_id": pending["id"]})



def update_subscription_settings(*, user_id, template_id, payload):
    _body(payload, {"auto_update_enabled"})
    enabled = payload.get("auto_update_enabled")
    if not isinstance(enabled, bool):
        raise TemplateReleaseError("VALIDATION_ERROR", "auto_update_enabled must be boolean.", field="auto_update_enabled")
    def operation():
        subscription, local = _subscription(db.session, user_id=user_id, template_id=template_id, lock=True)
        repository.update_row(db.session, TemplateSubscription, [TemplateSubscription.id == subscription["id"]], {"auto_update_enabled": enabled, "updated_at": _now()})
        if enabled:
            publication = repository.publication(db.session, subscription["source_template_id"])
            if publication and publication["current_release_id"] != subscription["applied_release_id"]:
                pending = _prepare(db.session, subscription, local, {"release_id": publication["current_release_id"]}, automatic=True)
                if pending["status"] == "ready":
                    subscription["pending_update_json"] = pending
                    _apply(db.session, subscription, local, {"preparation_id": pending["id"]})
        return get_subscription(user_id=user_id, template_id=template_id)
    return _commit(operation)


def capture_deck_release_template_pins(session, release, *, actor_user_id=None):
    """Snapshot active attachment bindings and their published source version."""
    item = repository.one(session, DeckMarketplaceItem, DeckMarketplaceItem.id == release.deck_item_id)
    applications = repository.source_applications(session, [item["source_note_type_id"]] if item["source_note_type_id"] else [])
    grouped = {}
    for app in applications:
        grouped.setdefault(app["template_id"], {})[app["id"]] = {
            name: deepcopy(app.get(name)) for name in APPLICATION_PIN_KEYS
        }
    for template_id, apps in sorted(grouped.items()):
        row = repository.template(session, template_id, lock=True)
        _authored(row, allow_archived=True, session=session)
        version = _snapshot(session, row, actor_user_id=actor_user_id)
        template_release = repository.one(session, TemplateRelease, TemplateRelease.template_id == template_id, TemplateRelease.version_id == version["id"])
        if template_release is None:
            publication = repository.ensure_publication(session, template_id)
            head = repository.release(session, publication["current_release_id"], template_id) if publication["current_release_id"] else None
            request = release_core.PublishRequest(release_core.next_auto_version(head["version_label"] if head else None), f"deck:{release.id}", publication["current_release_id"], version["id"], "Published with deck release.")
            template_release, _ = _publish_version(session, row, version, actor_user_id=actor_user_id, request=request, allow_archived=True)
        session.execute(insert(DeckReleaseTemplatePin.__table__).values(
            deck_release_id=release.id, source_template_id=template_id,
            template_release_id=template_release["id"], applications_json=apps,
        ))
    repository.update_row(session, DeckRelease, [DeckRelease.id == release.id], {"template_pins_initialized": True})


def deck_template_presentations(session, *, note_type_id, release_id=None):
    """Compare immutable pins to a draft using hashes, without leaking code in diffs."""
    from app.services.template_tokens import template_content_hash
    if release_id is not None:
        result = {}
        for source_id, pin in repository.deck_pins(session, release_id).items():
            release = repository.release(session, pin["template_release_id"], source_id)
            version = repository.version(session, release["version_id"], source_id)
            apps = {
                app_id: {key: deepcopy(values.get(key, 0 if key == "position" else None)) for key in APPLICATION_PIN_KEYS}
                for app_id, values in (pin["applications_json"] or {}).items()
            }
            result[source_id] = {"content_hash": version["content_hash"], "input_schema": version["input_schema"] or [], "applications": apps}
        return result
    result = {}
    for app in repository.source_applications(session, [note_type_id] if note_type_id else []):
        template_id = app["template_id"]
        if template_id not in result:
            template = repository.template(session, template_id)
            result[template_id] = {
                "content_hash": template_content_hash(**{key: template[key] or "" for key in CONTENT_KEYS if key != "input_schema"}),
                "input_schema": template["input_schema"] or [], "applications": {},
            }
        result[template_id]["applications"][app["id"]] = {key: deepcopy(app.get(key)) for key in APPLICATION_PIN_KEYS}
    return result


def note_type_publication_error(session, note_type_id):
    """Every marketplace path must inspect the active attachment definitions."""
    templates = repository.active_templates(session, note_type_id)
    if any(row.get("origin") == "market_copy" or row.get("source_template_id") for row in templates):
        return "Received marketplace templates cannot be redistributed in a shared NoteType or deck."
    return None


def stage_note_type_publications(session, *, note_type_id, actor_user_id, initialize_only=False):
    """Pin original releases; only authored unlisted definitions may be staged.

    This low-level helper never creates a marketplace listing. The NoteType
    publish API stages those explicitly before assembling its release.
    """
    from app.services.note_type_bundle_publication_service import references
    releases = {}
    for item in references(session, note_type_id=note_type_id, actor_user_id=actor_user_id, lock=True):
        row = item["source"]
        if not item["requires_publication"]:
            releases[item["attached"]["id"]] = item["release"]
            continue
        _authored(row, allow_archived=True, session=session)
        publication = repository.publication(session, row["id"])
        head = repository.release(session, publication["current_release_id"], row["id"]) if publication and publication["current_release_id"] else None
        if not initialize_only or head is None:
            version = _snapshot(session, row, actor_user_id=actor_user_id)
            existing = repository.one(session, TemplateRelease, TemplateRelease.template_id == row["id"], TemplateRelease.version_id == version["id"])
            if existing:
                head = existing
            else:
                publication = repository.ensure_publication(session, row["id"])
                request = release_core.PublishRequest(
                    release_core.next_auto_version(head["version_label"] if head else None),
                    f"note-type:{version['id']}", publication["current_release_id"], version["id"],
                    "Published with shared NoteType.",
                )
                head, _ = _publish_version(session, row, version, actor_user_id=actor_user_id, request=request, allow_archived=True)
        releases[item["attached"]["id"]] = head
    return releases


def stage_marketplace_release(session, row, *, actor_user_id):
    """Listing publishes the current content so marketplace buyers get what is shown."""
    _authored(row, session=session)
    publication = repository.publication(session, row["id"])
    head = repository.release(session, publication["current_release_id"], row["id"]) if publication and publication["current_release_id"] else None
    version = _snapshot(session, row, actor_user_id=actor_user_id)
    existing = repository.one(session, TemplateRelease, TemplateRelease.template_id == row["id"], TemplateRelease.version_id == version["id"])
    if existing:
        repository.ensure_publication(session, row["id"])
        repository.update_row(session, TemplatePublication,
            [TemplatePublication.template_id == row["id"]], {"current_release_id": existing["id"]})
        return existing
    publication = repository.ensure_publication(session, row["id"])
    request = release_core.PublishRequest(
        release_core.next_auto_version(head["version_label"] if head else None),
        f"market:{version['id']}", publication["current_release_id"], version["id"],
        "Phát hành khi đăng lên chợ giao diện thẻ.",
    )
    return _publish_version(session, row, version, actor_user_id=actor_user_id, request=request)[0]


def stage_note_type_template_subscriptions(session, *, note_type_install_id, user_id):
    """Standalone NoteType receipt uses the same per-user/source copies as decks."""
    install = repository.one(session, NoteTypeInstall, NoteTypeInstall.id == note_type_install_id, NoteTypeInstall.user_id == user_id)
    if install is None:
        raise TemplateReleaseError("INSTALL_NOT_FOUND", "Installation not found.", status=404)
    source_nt = repository.one(session, NoteType, NoteType.id == install["source_note_type_id"])
    releases = stage_note_type_publications(session, note_type_id=install["source_note_type_id"], actor_user_id=source_nt["user_id"], initialize_only=True)
    received = []
    for app in repository.source_applications(session, [install["source_note_type_id"]]):
        release = releases[app["template_id"]]
        subscription = ensure_subscription(session, user_id=user_id, source_template_id=app["template_id"], release_id=release["id"])
        received.append(subscription)
        _attach_received_template(session, subscription, app, user_id=user_id)
    return received


def _ensure_local_field_map(session, *, source_nt, local_nt):
    source_fields = session.execute(
        select(FieldDef.__table__)
        .where(FieldDef.note_type_id == source_nt)
        .order_by(FieldDef.position.asc(), FieldDef.id.asc())
    ).mappings().all()
    local_fields = session.execute(
        select(FieldDef.__table__).where(FieldDef.note_type_id == local_nt)
    ).mappings().all()
    local_by_name = {row["name"]: row["id"] for row in local_fields}
    for row in source_fields:
        if row["name"] not in local_by_name:
            new_field_id = uuid_str()
            from app.repositories.field_value_identity_repository import insert_field_definition
            insert_field_definition(session,
                id=new_field_id,
                note_type_id=local_nt,
                name=row["name"],
                field_type=row["field_type"],
                position=row["position"],
                required=bool(row["required"]),
                identity_role=row.get("identity_role"),
            )
            local_by_name[row["name"]] = new_field_id
    return {row["id"]: local_by_name.get(row["name"]) for row in source_fields}


def _mapped_bindings(source_app, field_map):
    if not source_app:
        return {}
    return {
        key: field_map.get(value)
        for key, value in (source_app.get("input_bindings") or {}).items()
    }


def _sync_subscription_to_pinned_release(session, subscription, *, target_release_id):
    if not target_release_id or subscription["applied_release_id"] == target_release_id:
        return subscription
    source_id = subscription["source_template_id"]
    target = repository.release(session, target_release_id, source_id)
    applied = repository.release(session, subscription["applied_release_id"], source_id)
    if target is None or applied is None or int(target["sequence_no"]) <= int(applied["sequence_no"]):
        return subscription
    local = repository.template(session, subscription["local_template_id"], lock=True)
    pending = _prepare(session, subscription, local, {"release_id": target["id"]}, automatic=True)
    if pending["status"] == "ready":
        subscription = dict(subscription, pending_update_json=pending)
        _apply(session, subscription, local, {"preparation_id": pending["id"]})
    return repository.subscription(session, user_id=subscription["user_id"], source_template_id=source_id)


def _attach_received_template(session, subscription, source_app, *, user_id, base_app=None, reactivate=False):
    source_nt = source_app["note_type_id"]
    nt_install = repository.one(session, NoteTypeInstall, NoteTypeInstall.user_id == user_id, NoteTypeInstall.source_note_type_id == source_nt)
    if not nt_install or not nt_install["installed_note_type_id"]:
        return
    if nt_install.get("applied_release_id"):
        return  # A separately received Note Type owns its frozen applications.
    local_nt = nt_install["installed_note_type_id"]
    field_map = _ensure_local_field_map(session, source_nt=source_nt, local_nt=local_nt)
    bindings = _mapped_bindings(source_app, field_map)
    existing = repository.one(session, StudyApplication, StudyApplication.note_type_id == local_nt, StudyApplication.template_id == subscription["local_template_id"])
    if existing:
        updates = {}
        if base_app is not None:
            base_bindings = _mapped_bindings(base_app, field_map)
            local_bindings = dict(existing.get("input_bindings") or {})
            merged_bindings = {}
            for key in set(base_bindings) | set(bindings) | set(local_bindings):
                b_val = base_bindings.get(key)
                u_val = bindings.get(key)
                l_val = local_bindings.get(key)
                if key in bindings:
                    merged_bindings[key] = u_val if l_val == b_val else l_val
                elif l_val != b_val and l_val is not None:
                    merged_bindings[key] = l_val
            if merged_bindings != local_bindings:
                updates["input_bindings"] = merged_bindings
            for prop, default in (("display_name", None), ("is_default", False), ("position", 0)):
                b_val = bool(base_app.get(prop)) if prop == "is_default" else base_app.get(prop, default)
                u_val = bool(source_app.get(prop)) if prop == "is_default" else source_app.get(prop, default)
                l_val = bool(existing.get(prop)) if prop == "is_default" else existing.get(prop, default)
                if l_val == b_val and u_val != l_val:
                    updates[prop] = u_val
        elif reactivate and existing.get("status_code") != "ACTIVE":
            updates.update(
                input_bindings=bindings,
                display_name=source_app.get("display_name"),
                is_default=bool(source_app.get("is_default")),
                position=source_app.get("position", 0),
            )
        if reactivate and existing.get("status_code") != "ACTIVE":
            updates["status_code"] = "ACTIVE"
        if updates:
            updates["updated_at"] = _now()
            repository.update_row(session, StudyApplication, [StudyApplication.id == existing["id"]], updates)
        return  # reinstall never overwrites a user's customized binding
    session.execute(insert(StudyApplication.__table__).values(
        id=uuid_str(), note_type_id=local_nt, template_id=subscription["local_template_id"],
        occurrence_key="compat", input_bindings=bindings, status_code="ACTIVE",
        display_name=source_app.get("display_name"), is_default=bool(source_app.get("is_default")), position=source_app.get("position", 0),
    ))
    # Retain compatibility IDs/history, but keep raw clone definitions out of
    # discovery and preserve provenance so they cannot become authored copies.
    raw_copies = session.info.get("flama.template_clone_compat", {}).pop(local_nt, [])
    raw_ids = [row.id for row in raw_copies if row.id]
    if raw_ids:
        session.execute(update(StudyApplication.__table__).where(
            StudyApplication.note_type_id == local_nt, StudyApplication.template_id.in_(raw_ids),
            StudyApplication.occurrence_key == "compat",
        ).values(status_code="RETIRED"))
        session.execute(update(Template.__table__).where(Template.id.in_(raw_ids)).values(archived_at=_now()))


def _retire_unpinned_received_applications(session, *, install, user_id, active_source_ids, base_source_ids):
    source_nt = install.get("source_note_type_id")
    if not source_nt:
        return
    nt_install = repository.one(session, NoteTypeInstall, NoteTypeInstall.user_id == user_id, NoteTypeInstall.source_note_type_id == source_nt)
    if not nt_install or not nt_install.get("installed_note_type_id"):
        return
    if nt_install.get("applied_release_id"):
        return  # A separately received Note Type owns its frozen applications.
    local_nt = nt_install["installed_note_type_id"]
    prior_source_ids = set(base_source_ids)
    if install.get("deck_item_id"):
        prior_source_ids.update(
            session.execute(
                select(DeckReleaseTemplatePin.source_template_id)
                .join(DeckRelease.__table__, DeckRelease.id == DeckReleaseTemplatePin.deck_release_id)
                .where(DeckRelease.deck_item_id == install["deck_item_id"])
            ).scalars().all()
        )
    for retired_source_id in sorted(prior_source_ids - set(active_source_ids)):
        sub = repository.subscription(session, user_id=user_id, source_template_id=retired_source_id)
        if not sub:
            continue
        existing = repository.one(
            session,
            StudyApplication,
            StudyApplication.note_type_id == local_nt,
            StudyApplication.template_id == sub["local_template_id"],
        )
        if existing and existing.get("status_code") == "ACTIVE":
            repository.update_row(
                session,
                StudyApplication,
                [StudyApplication.id == existing["id"]],
                {"status_code": "RETIRED", "updated_at": _now()},
            )


def list_install_templates(*, user_id, install_id):
    install = repository.install(db.session, user_id=user_id, install_id=install_id)
    if install is None:
        raise TemplateReleaseError("INSTALL_NOT_FOUND", "Installation not found.", status=404)
    release = repository.one(db.session, DeckRelease, DeckRelease.id == install["applied_release_id"]) if install["applied_release_id"] else None
    pins = repository.deck_pins(db.session, release["id"]) if release and release.get("template_pins_initialized") else {}
    source_ids = list(pins) if release and release.get("template_pins_initialized") else sorted({app["template_id"] for app in repository.source_applications(db.session, [install["source_note_type_id"]])})
    items = []
    for source_id in source_ids:
        subscription = repository.subscription(db.session, user_id=user_id, source_template_id=source_id)
        if subscription:
            local = repository.template(db.session, subscription["local_template_id"])
            items.append(_subscription_dto(db.session, subscription, local))
    return {"install_id": install_id, "items": items, "legacy_template_fallback": not bool(release and release.get("template_pins_initialized"))}


def stage_install_template_subscriptions(session, *, install_id, user_id, from_release_id=None):
    """Receive canonical user copies and attach them to the installed NoteType.

    Historical releases without a pin manifest retain explicit legacy behavior;
    this function never invents historical presentation from the author's draft.
    """
    install = repository.install(session, user_id=user_id, install_id=install_id)
    if install is None:
        raise TemplateReleaseError("INSTALL_NOT_FOUND", "Installation not found.", status=404)
    release = repository.one(session, DeckRelease, DeckRelease.id == install["applied_release_id"]) if install["applied_release_id"] else None
    if not release or not release.get("template_pins_initialized"):
        return []
    pins = repository.deck_pins(session, release["id"])
    base_release_id = from_release_id or release.get("parent_release_id")
    base_pins = repository.deck_pins(session, base_release_id) if base_release_id else {}
    received = []
    for source_id, pin in sorted(pins.items()):
        subscription = ensure_subscription(session, user_id=user_id, source_template_id=source_id, release_id=pin["template_release_id"])
        subscription = _sync_subscription_to_pinned_release(session, subscription, target_release_id=pin["template_release_id"])
        received.append(subscription)
        base_pin = base_pins.get(source_id)
        base_apps = list((base_pin.get("applications_json") or {}).values()) if base_pin else []
        base_app = base_apps[0] if base_apps else None
        for source_app in (pin["applications_json"] or {}).values():
            _attach_received_template(
                session,
                subscription,
                source_app,
                user_id=user_id,
                base_app=base_app,
                reactivate=bool(base_release_id is not None or source_id not in base_pins),
            )
    _retire_unpinned_received_applications(
        session,
        install=install,
        user_id=user_id,
        active_source_ids=set(pins),
        base_source_ids=set(base_pins),
    )
    return received
