"""Atomic NOTE topology updates for the MCP template-list API.

The caller owns authorization, shared-release guards, learner fences, preview
confirmation and commit/rollback. Add siblings before removing any: replacing
the entire presentation set must never reset the canonical Note state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.services import study_content_delete_service as content_topology
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.validators.flashcard_input import RequestValidationError
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.template import Template


def _invalid(message, code="INVALID_PARAMS"):
    return RequestValidationError(message, field="templates", status=400, code=code)


def _plan(current, changes):
    by_id = {row.id: row for row in current}
    by_name = {row.name: row for row in current}
    updates, additions, removed = [], [], set()
    seen_ids = set()

    def entry(value, *, add=False):
        if not isinstance(value, dict):
            raise _invalid("Each template must be an object.")
        data = dict(value)
        if data.get("id") is not None and not isinstance(data["id"], str):
            raise _invalid("Template ID must be a string.")
        if data.get("name") is not None and not isinstance(data["name"], str):
            raise _invalid("Template name must be a string.")
        row = None if add else (by_id.get(data["id"]) if data.get("id") else by_name.get(data.get("name")))
        if data.get("id") and (add or row is None):
            raise _invalid("Template ID does not identify an existing template of this NoteType.")
        if row is not None:
            if row.id in seen_ids:
                raise _invalid("A template may be updated only once per request.")
            seen_ids.add(row.id)
        if "name" in data or row is None:
            data["name"] = str(data.get("name") or "New Card").strip()
            if not data["name"] or len(data["name"]) > 255:
                raise _invalid("Template name must contain 1 to 255 characters.")
        if "position" in data:
            try:
                data["position"] = int(data["position"])
            except (TypeError, ValueError) as exc:
                raise _invalid("Template position must be an integer.") from exc
        if row is None:
            additions.append(data)
        else:
            updates.append((row, data))
        return row

    if isinstance(changes, list):
        for value in changes:
            entry(value)
        removed = set(by_id) - seen_ids
    elif isinstance(changes, dict):
        for key in ("added", "updated", "removed"):
            if not isinstance(changes.get(key, []), list):
                raise _invalid(f"templates.{key} must be a list.")
        for name in changes.get("removed", []):
            row = by_name.get(str(name))
            if row is None:
                raise _invalid("Removed template does not exist.")
            removed.add(row.id)
        for value in changes.get("updated", []):
            if entry(value) is None:
                raise _invalid("Updated template does not exist.")
        for value in changes.get("added", []):
            entry(value, add=True)
        if seen_ids & removed:
            raise _invalid("A template cannot be updated and removed in the same request.")
    else:
        raise _invalid("templates must be a list or an added/updated/removed object.")
    if len(current) - len(removed) + len(additions) < 1:
        raise _invalid("A NoteType requires at least one template.", "NOTE_TYPE_MUST_HAVE_TEMPLATES")
    update_by_id = {row.id: data for row, data in updates}
    final_names = [update_by_id.get(row.id, {}).get("name", row.name) for row in current if row.id not in removed]
    final_names.extend(data["name"] for data in additions)
    if len(set(final_names)) != len(final_names):
        raise _invalid("Template names must be unambiguous within the requested schema.")
    return updates, additions, removed


def stage_note_template_changes(session, *, routes, note_type, changes, operation_key):
    """Stage a complete delta/list update without committing any partial shape.

    ``routes`` hold every affected learner fence in ID order; other learners
    with state on these Notes keep one canonical state across the change.
    """
    route = next((row for row in routes if row.learner_user_id == note_type.user_id), None)
    if route is None or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", "NOTE template route is invalid.")
    current = tuple(session.execute(select(Template).where(Template.note_type_id == note_type.id)
        .order_by(Template.position, Template.id).with_for_update()
        .execution_options(populate_existing=True)).scalars())
    updates, additions, removed = _plan(current, changes)
    note_rows = tuple(session.execute(select(Note).where(Note.note_type_id == note_type.id)
        .order_by(Note.id).with_for_update().execution_options(populate_existing=True)).scalars())
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    # New Templates only generate Cards for the owner's Notes, as before.
    note_ids = tuple(str(note.id) for note in note_rows if note.user_id == route.learner_user_id)

    # Sequential expansions stay inside the SAME transaction, with one exact
    # copied projection per Note. A fault in any later step rolls back all.
    new_templates = []
    for index, data in enumerate(additions):
        expansion = content_topology.prepare_content_expansion(
            session, routes=routes, note_ids=note_ids, now_utc=now)
        content_topology.verify_content_expansion_scope(session, routes=routes, note_ids=note_ids)
        template = Template(note_type_id=note_type.id, name=data["name"],
            front_html=str(data.get("front_html") or ""), back_html=str(data.get("back_html") or ""),
            shared_css=str(data.get("shared_css") or ""), position=data.get("position", len(current) + index),
            is_default=False, created_at=now, updated_at=now)
        session.add(template)
        session.flush()
        cards = [Card(note_id=note_id, template_id=template.id, created_at=now, updated_at=now) for note_id in note_ids]
        session.add_all(cards)
        session.flush()
        content_topology.finalize_content_expansion(expansion, new_cards=cards,
            now_utc=now, provenance_code="NATIVE_MCP")
        new_templates.append(template)

    if removed:
        removed_card_ids = tuple(str(value) for value in session.execute(select(Card.id)
            .where(Card.template_id.in_(sorted(removed))).order_by(Card.note_id, Card.id).with_for_update()).scalars())
        removal = content_topology.prepare_content_delete(session, routes=routes,
            card_ids=removed_card_ids, note_ids=(), now_utc=now, cancel_legacy_sessions=False)
        content_topology.verify_content_delete_scope(session, routes=routes,
            card_ids=removed_card_ids, deleted_note_ids=())
        if removed_card_ids:
            session.query(CardProgress).filter(CardProgress.card_id.in_(removed_card_ids)).delete(synchronize_session=False)
        # Detach evidence while Card identities still exist, as in REST deletion.
        content_topology.finalize_content_delete(removal,
            source_path="mcp.note_type_template_update", operation_key=operation_key, now_utc=now)
        session.query(Card).filter(Card.template_id.in_(sorted(removed))).delete(synchronize_session=False)
        for template in current:
            if template.id in removed:
                session.delete(template)

    for template, data in updates:
        for key in ("name", "front_html", "back_html", "shared_css", "position"):
            if key in data:
                setattr(template, key, data[key] if key in {"name", "position"} else str(data[key] or ""))
    surviving = [row for row in current if row.id not in removed] + new_templates
    default = next((row for row in surviving if row.is_default), None)
    default = default or min(surviving, key=lambda row: (row.position, row.id))
    for template in surviving:
        template.is_default = template.id == default.id
    note_type.updated_at = now
    session.flush()
    session.expire(note_type, ["templates"])
