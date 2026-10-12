"""Atomic NOTE topology updates for the MCP template-list API.

The caller owns authorization, shared-release guards, learner fences, preview
confirmation and commit/rollback. Add siblings before removing any: replacing
the entire presentation set must never reset the canonical Note state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.services import study_content_delete_service as content_topology
from app.repositories import template_library_repository
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.validators.flashcard_input import RequestValidationError
from models.card import Card
from models.study_application import StudyApplication
from models.template import Template


def _invalid(message, code="INVALID_PARAMS"):
    return RequestValidationError(message, field="templates", status=400, code=code)


def _plan(current, changes):
    by_application = {row.application_id: row for row in current}
    updates, additions, removed, seen = [], [], set(), set()

    def resolve(value):
        if isinstance(value, dict):
            if value.get("application_id"):
                row = by_application.get(str(value["application_id"]))
                if row is None:
                    raise _invalid("Application does not belong to this NoteType.")
                return row
            candidates = [row for row in current if
                          (row.id == value.get("id") if value.get("id") else row.name == value.get("name"))]
        else:
            candidates = [row for row in current if str(value) in {row.application_id, row.id, row.name}]
        if len(candidates) > 1:
            raise _invalid("Repeated attachments require an explicit application_id.")
        return candidates[0] if candidates else None

    def entry(value, *, add=False):
        if not isinstance(value, dict):
            raise _invalid("Each template must be an object.")
        data = dict(value)
        row = None if add else resolve(data)
        if (data.get("id") or data.get("application_id")) and row is None:
            raise _invalid("Template/application ID does not identify an attachment of this NoteType.")
        if row is None:
            data["name"] = str(data.get("name") or "New Card").strip()
        if "name" in data and (not isinstance(data["name"], str) or not 1 <= len(data["name"]) <= 255):
            raise _invalid("Template name must contain 1 to 255 characters.")
        if "position" in data and (isinstance(data["position"], bool) or not isinstance(data["position"], int) or data["position"] < 0):
            raise _invalid("Template position must be a nonnegative integer.")
        if row is None:
            additions.append(data)
        else:
            if row.application_id in seen:
                raise _invalid("An attachment may be updated only once per request.")
            seen.add(row.application_id)
            updates.append((row, data))
        return row

    if isinstance(changes, list):
        for value in changes:
            entry(value)
        removed = set(by_application) - seen
    elif isinstance(changes, dict):
        for key in ("added", "updated", "removed"):
            if not isinstance(changes.get(key, []), list):
                raise _invalid(f"templates.{key} must be a list.")
        for value in changes.get("removed", []):
            row = resolve(value)
            if row is None:
                raise _invalid("Removed attachment does not exist.")
            removed.add(row.application_id)
        for value in changes.get("updated", []):
            if entry(value) is None:
                raise _invalid("Updated attachment does not exist.")
        for value in changes.get("added", []):
            entry(value, add=True)
        if seen & removed:
            raise _invalid("An attachment cannot be updated and removed in the same request.")
    else:
        raise _invalid("templates must be a list or an added/updated/removed object.")
    if len(current) - len(removed) + len(additions) < 1:
        raise _invalid("A NoteType requires at least one template.", "NOTE_TYPE_MUST_HAVE_TEMPLATES")
    return updates, additions, removed


def stage_note_template_changes(session, *, routes, note_type, changes, operation_key):
    """Change explicitly scoped applications without deleting reusable definitions."""
    route = next((row for row in routes if row.learner_user_id == note_type.user_id), None)
    if route is None or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", "NOTE template route is invalid.")
    # Caller holds the authoring NoteType/learner fences. Lock application rows
    # in deterministic order; definitions are independently owned.
    session.execute(select(StudyApplication).where(StudyApplication.note_type_id == note_type.id)
                    .order_by(StudyApplication.id).with_for_update()
                    .execution_options(populate_existing=True)).scalars().all()
    current = tuple(template_library_repository.attached_templates(session, note_type.id))
    updates, additions, removed = _plan(current, changes)
    for view, data in updates:
        if any(key in data for key in ("name", "front_html", "back_html", "shared_css")):
            from app.services.flashcard_content_service import _ensure_version_safe_template_mutation
            from models.note_type import NoteType
            attached_types = session.execute(select(NoteType).join(StudyApplication).where(
                StudyApplication.template_id == view.id,
            ).distinct()).scalars().all()
            for attached_type in attached_types:
                _ensure_version_safe_template_mutation(
                    note_type=attached_type, owner_user_id=note_type.user_id,
                    allow_released_template_content_hotfix=not ("name" in data),
                )
        for key in ("name", "front_html", "back_html", "shared_css"):
            if key in data:
                if view.template.owner_user_id != note_type.user_id:
                    raise _invalid("Attached definition belongs to another author.")
                setattr(view.template, key, str(data[key] or ""))
        if "position" in data:
            view.application.position = data["position"]
        if "is_default" in data:
            if not isinstance(data["is_default"], bool):
                raise _invalid("is_default must be boolean.")
            view.application.is_default = data["is_default"]
    for view in current:
        if view.application_id in removed:
            view.application.status_code = "RETIRED"
    for index, data in enumerate(additions):
        template_library_repository.create_attached_template(session, note_type=note_type,
            name=data["name"], front_html=str(data.get("front_html") or ""),
            back_html=str(data.get("back_html") or ""), shared_css=str(data.get("shared_css") or ""),
            position=data.get("position", len(current) + index), is_default=bool(data.get("is_default", False)))
    session.flush()
    active = template_library_repository.applications(session, note_type.id)
    default = next((row for row in active if row.is_default), None) or min(active, key=lambda row: (row.position, row.id))
    for application in active:
        application.is_default = application.id == default.id
    note_type.updated_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    session.flush()
