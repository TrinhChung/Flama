"""Transactional template history and owner history/restore operations.

Flushes collect changes; the outer commit snapshots each Template once. This
covers normal ORM writers without publishing intermediate import/topology
flushes as separate versions. Raw/bulk SQL writers must opt in explicitly.
"""

from datetime import timezone

from sqlalchemy import delete, event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.repositories import template_version_repository as repository
from models import db
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion

_TRACKED = "flama.template_versions.tracked"
_MARKS = "flama.template_versions.marks"
_NESTED = "flama.template_versions.savepoints"
_FINALIZING = "flama.template_versions.finalizing"
_CONTENT = ("front_html", "back_html", "shared_css", "input_schema")
SCHEMA_VERSION = "template-versions.v2"


class TemplateVersionError(ValueError):
    def __init__(self, code, message, *, status=400, field=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field


def validate_change_note(payload):
    if not isinstance(payload, dict):
        raise TemplateVersionError("VALIDATION_ERROR", "Request body must be an object.")
    value = payload.get("change_note", "")
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > 1000:
        raise TemplateVersionError("VALIDATION_ERROR", "Change note must be at most 1000 characters.", field="change_note")
    return value.strip()


def mark_template_version(template, *, origin, actor_user_id=None, change_note=None, force=False):
    session = inspect(template).session
    if session is None:
        raise ValueError("Template must belong to a Session.")
    session.info.setdefault(_MARKS, {})[template] = {
        "origin": origin, "actor_user_id": actor_user_id, "change_note": change_note,
        "force": force,
    }


@event.listens_for(Session, "before_flush")
def _collect_changes(session, _context, _instances):
    if session.info.get(_FINALIZING):
        return
    for version in session.dirty:
        if isinstance(version, TemplateVersion) and session.is_modified(version, include_collections=False):
            raise TemplateVersionError("IMMUTABLE_TEMPLATE_VERSION", "Template versions cannot be modified.", status=409)
    if any(isinstance(item, TemplateVersion) for item in session.deleted):
        raise TemplateVersionError("IMMUTABLE_TEMPLATE_VERSION", "Template versions cannot be deleted directly.", status=409)

    deleted = [item.id for item in session.deleted if isinstance(item, Template) and item.id]
    if deleted:
        # Preserve MySQL CASCADE semantics in SQLite harnesses without FK checks.
        session.execute(delete(TemplateVersion.__table__).where(TemplateVersion.template_id.in_(deleted)))
    tracked = session.info.setdefault(_TRACKED, {})
    candidates = []
    for template in list(session.new) + list(session.dirty):
        if not isinstance(template, Template) or template in session.deleted:
            continue
        is_new = template in session.new
        if is_new or any(inspect(template).attrs[key].history.has_changes() for key in _CONTENT):
            if template not in tracked:
                tracked[template] = {"new": is_new, "baseline": None}
                if not is_new and template.id:
                    candidates.append(template)
    if candidates:
        before = repository.snapshots(session, [item.id for item in candidates])
        for template in candidates:
            row = before.get(template.id)
            # Normally migration already initializes this. Keep the original
            # database content if an unversioned row is edited before backfill.
            if row is not None and not row["current_version_id"]:
                tracked[template]["baseline"] = row


@event.listens_for(Session, "before_commit")
def _finalize_versions(session):
    if session.in_nested_transaction() or session.info.get(_FINALIZING):
        return
    session.flush()
    tracked = session.info.get(_TRACKED, {})
    marks = session.info.get(_MARKS, {})
    candidates = {**tracked}
    for template, mark in marks.items():
        if mark.get("force"):
            candidates.setdefault(template, {"new": False, "baseline": None})
    candidates = {
        template: state for template, state in candidates.items()
        if template.id and not inspect(template).deleted and template not in session.deleted
    }
    if not candidates:
        return
    session.info[_FINALIZING] = True
    try:
        current = repository.snapshots(session, [item.id for item in candidates])
        publication_events = []
        for template, state in sorted(candidates.items(), key=lambda pair: str(pair[0].id)):
            snapshot = current.get(template.id)
            if snapshot is None:
                continue
            baseline = state["baseline"]
            if baseline is not None and not snapshot["current_version_id"]:
                # Only content comes from the pre-edit baseline. History
                # metadata must preserve the live row's post-flush timestamp,
                # including an edit reverted within this transaction.
                baseline["updated_at"] = snapshot["updated_at"]
                base_id, _ = repository.append_snapshot(session, baseline, origin="backfill")
                snapshot["current_version_id"] = base_id
            mark = marks.get(template, {})
            version_id, appended = repository.append_snapshot(
                session, snapshot,
                origin=mark.get("origin", "create" if state["new"] else "edit"),
                actor_user_id=mark.get("actor_user_id"), change_note=mark.get("change_note"),
                force=bool(mark.get("force")),
            )
            set_committed_value(template, "current_version_id", version_id)
            set_committed_value(template, "owner_user_id", snapshot["owner_user_id"])
            if appended:
                publication_events.append((template.id, version_id, mark.get("actor_user_id"), mark.get("change_note")))
        # All authored and local edits must have a final history head before
        # automatic inheritance can modify local copies in this transaction.
        from app.services.template_release_service import on_version_appended
        for template_id, version_id, actor_user_id, change_note in publication_events:
            on_version_appended(session, template_id=template_id, version_id=version_id,
                                actor_user_id=actor_user_id, change_note=change_note)
    finally:
        session.info.pop(_FINALIZING, None)


@event.listens_for(Session, "after_transaction_create")
def _savepoint_started(session, transaction):
    if transaction.nested:
        session.info.setdefault(_NESTED, {})[transaction] = (
            {item: dict(state) for item, state in session.info.get(_TRACKED, {}).items()},
            {item: dict(mark) for item, mark in session.info.get(_MARKS, {}).items()},
        )


@event.listens_for(Session, "after_soft_rollback")
def _savepoint_rolled_back(session, transaction):
    checkpoint = session.info.get(_NESTED, {}).pop(transaction, None)
    if checkpoint is not None:
        session.info[_TRACKED], session.info[_MARKS] = checkpoint


@event.listens_for(Session, "after_transaction_end")
def _transaction_finished(session, transaction):
    if transaction.parent is None:
        for key in (_TRACKED, _MARKS, _NESTED, _FINALIZING):
            session.info.pop(key, None)


def _owned(*, user_id, template_id, note_type_id=None, lock=False):
    template = repository.owned_template(
        db.session, user_id=user_id, template_id=template_id, note_type_id=note_type_id, lock=lock,
    )
    if template is None:
        raise TemplateVersionError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
    return template


def _serialize(row, current_version_id, *, detail=False):
    version, actor_id, username = row
    created_at = version.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    payload = {
        "id": version.id, "template_id": version.template_id,
        "version_no": version.version_no, "content_hash": version.content_hash,
        "change_note": version.change_note or "", "origin": version.origin,
        "created_at": created_at.isoformat(),
        "created_by": {"id": actor_id, "username": username} if actor_id is not None else None,
        "is_current": version.id == current_version_id,
    }
    if detail:
        payload.update({
            "front_html": version.front_html, "back_html": version.back_html,
            "shared_css": version.shared_css, "input_schema": version.input_schema,
        })
    return payload


def list_versions(*, user_id, template_id, note_type_id=None):
    template = _owned(user_id=user_id, template_id=template_id, note_type_id=note_type_id)
    return {
        "schema_version": SCHEMA_VERSION, "template_id": template.id,
        "current_version_id": template.current_version_id,
        "items": [_serialize(row, template.current_version_id) for row in repository.versions_with_authors(
            db.session, template_id=template.id,
        )],
    }


def get_version(*, user_id, template_id, version_id, note_type_id=None):
    template = _owned(user_id=user_id, template_id=template_id, note_type_id=note_type_id)
    rows = repository.versions_with_authors(db.session, template_id=template.id, version_id=version_id)
    if not rows:
        raise TemplateVersionError("TEMPLATE_VERSION_NOT_FOUND", "Template version not found.", status=404)
    return _serialize(rows[0], template.current_version_id, detail=True)


def restore_version(*, user_id, template_id, version_id, payload, note_type_id=None):
    from app.services import flashcard_content_service, marketplace_query_service
    from app.services.flashcard_renderer import TemplateCompileError, render_template_pair

    change_note = validate_change_note(payload)
    if set(payload) - {"change_note"}:
        raise TemplateVersionError("VALIDATION_ERROR", "Only change_note may be supplied for restore.")
    template = _owned(user_id=user_id, template_id=template_id, note_type_id=note_type_id, lock=True)
    rows = repository.versions_with_authors(db.session, template_id=template.id, version_id=version_id)
    if not rows:
        raise TemplateVersionError("TEMPLATE_VERSION_NOT_FOUND", "Template version not found.", status=404)
    version = rows[0][0]
    # A content restore follows the existing #138 author hotfix rule. A schema
    # change remains closed until attachment/release support is implemented.
    same_schema = (template.input_schema or []) == version.input_schema
    from models.study_application import StudyApplication
    note_types = db.session.execute(select(NoteType).join(StudyApplication).where(
        StudyApplication.template_id == template.id, StudyApplication.status_code == "ACTIVE",
    ).distinct()).scalars().all()
    for attached_note_type in note_types:
        flashcard_content_service._ensure_version_safe_template_mutation(
            note_type=attached_note_type, owner_user_id=user_id,
            allow_released_template_content_hotfix=same_schema,
        )
    mark_template_version(template, origin="restore", actor_user_id=user_id, change_note=change_note, force=True)
    template.front_html = version.front_html
    template.back_html = version.back_html
    template.shared_css = version.shared_css
    template.input_schema = version.input_schema
    try:
        render_template_pair(
            template=template, field_defs=(),
            field_values={}, media_assets=[], preview_note_key="version-restore-validation",
        )
    except TemplateCompileError as exc:
        db.session.rollback()
        raise TemplateVersionError("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html") from exc
    flashcard_content_service._audit(user_id, "template.restore", {
        "template_id": template.id,
        "restored_version_id": version.id,
    })
    db.session.commit()
    return marketplace_query_service.serialize_template(template)


def backfill_versions(*, batch_size=500):
    """Stage missing initial snapshots without committing or touching content."""
    after = ""
    count = 0
    while True:
        ids = db.session.execute(select(Template.id).where(
            Template.current_version_id.is_(None), Template.id > after,
        ).order_by(Template.id).limit(batch_size)).scalars().all()
        if not ids:
            return count
        for row in repository.snapshots(db.session, ids).values():
            if row["current_version_id"] is None:
                repository.append_snapshot(db.session, row, origin="backfill")
                count += 1
        after = str(ids[-1])


def register_cli(app):
    import click

    @app.cli.command("template-versions-backfill")
    @click.option("--apply", is_flag=True, help="Commit initial history; default rolls back a dry run.")
    @click.option("--batch-size", type=click.IntRange(1, 2000), default=500)
    def backfill_command(apply, batch_size):
        try:
            count = backfill_versions(batch_size=batch_size)
            if apply:
                db.session.commit()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()
            raise
        click.echo(f"templates={count} applied={str(apply).lower()}")
