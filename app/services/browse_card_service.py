"""Application service for browse card detail updates."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from app.repositories import browse_card_repository
from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.validators import RequestValidationError, validate_browse_card_update_request


class BrowseCardUpdateError(ValueError):
    """Typed error for browse-card edit API responses."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        code: str = "BROWSE_CARD_UPDATE_ERROR",
        include_details: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.field = field
        self.code = code
        self.include_details = include_details


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def update_browse_card(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    card_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and persist browse editor mutations for a card."""
    from app.services import flashcards_share as share_ctrl

    card_obj = browse_card_repository.load_card_for_browse_update(card_id=card_id)
    if not card_obj:
        raise BrowseCardUpdateError("Card not found", status=404)

    note_obj = card_obj.note
    note_type_obj = note_obj.note_type if note_obj else None
    if note_obj is None or note_type_obj is None:
        raise BrowseCardUpdateError("Card note type not found", status=404)

    clone_scope = None
    if not admin_mode and note_obj.user_id != user_id:
        clone_scope = share_ctrl.resolve_clone_scope_for_card(
            user_id=user_id,
            card_obj=card_obj,
        )
        if clone_scope is None or not share_ctrl.is_card_visible_in_clone_scope(
            scope=clone_scope,
            card_obj=card_obj,
        ):
            raise BrowseCardUpdateError("Card not found", status=404)

    try:
        validated = validate_browse_card_update_request(
            note_type=note_type_obj,
            payload=payload,
            current_values=dict(note_obj.field_values or {}),
            note_media_ids=_collect_note_media_refs(note_obj),
        )
    except RequestValidationError as exc:
        raise BrowseCardUpdateError(
            str(exc),
            status=exc.status,
            field=exc.field,
            code=exc.code,
            include_details=True,
        ) from exc

    if clone_scope is not None and not admin_mode:
        return _update_clone_browse_card(
            user_id=user_id,
            timezone_name=timezone_name,
            card_obj=card_obj,
            note_obj=note_obj,
            clone_scope=clone_scope,
            validated=validated,
        )

    return _update_owned_browse_card(
        user_id=user_id,
        admin_mode=admin_mode,
        timezone_name=timezone_name,
        card_obj=card_obj,
        note_obj=note_obj,
        validated=validated,
    )


def _update_clone_browse_card(
    *,
    user_id: int,
    timezone_name: str,
    card_obj,
    note_obj,
    clone_scope,
    validated,
) -> dict[str, Any]:
    from app.services import flashcards_share as share_ctrl

    mapped_local_deck_id = (
        (clone_scope.source_to_local_deck_id or {}).get(int(note_obj.deck_id or 0))
        or clone_scope.install.local_deck_id
    )
    if validated.update_deck:
        selected_deck_id = validated.deck_id
        if selected_deck_id != (int(mapped_local_deck_id) if mapped_local_deck_id is not None else None):
            raise BrowseCardUpdateError(
                "Moving cloned cards across decks is not supported.",
                status=400,
            )

    if validated.update_tags:
        incoming_tags = validated.tags or []
        current_tags = _normalize_tags_payload(note_obj.tags or [])
        if incoming_tags != current_tags:
            raise BrowseCardUpdateError(
                "Editing tags for cloned cards is not supported.",
                status=400,
            )

    note_override_items = []
    for key_name, value in validated.field_updates.items():
        note_override_items.append(
            {
                "source_note_id": note_obj.id,
                "field_name": key_name,
                "operation": "set",
                "value": value,
            }
        )

    if note_override_items:
        _, validation_error = share_ctrl.upsert_clone_overlay(
            deck_install=clone_scope.install,
            payload={"note_field_overrides": note_override_items},
        )
        if validation_error:
            browse_card_repository.rollback_changes()
            raise BrowseCardUpdateError(validation_error, status=400)

    browse_card_repository.commit_changes()

    detail_payload = _build_browse_detail_payload(
        user_id=user_id,
        admin_mode=False,
        timezone_name=timezone_name,
        card_obj=card_obj,
    )
    detail_payload = _apply_clone_overlay_to_browse_payload(
        payload=detail_payload,
        card_obj=card_obj,
        clone_scope=clone_scope,
        deck_lookup=_clone_scope_deck_lookup(user_id=user_id, clone_scope=clone_scope),
    )
    return {
        "success": True,
        "row": detail_payload.get("card"),
        "detail": detail_payload,
    }


def _update_owned_browse_card(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    card_obj,
    note_obj,
    validated,
) -> dict[str, Any]:
    accessible_deck_ids: set[int] | None = None
    if validated.update_deck:
        selected_deck_id = validated.deck_id
        if selected_deck_id is None:
            note_obj.deck_id = None
        else:
            if browse_card_repository.get_deck(deck_id=selected_deck_id) is None:
                raise BrowseCardUpdateError("Deck not found", status=404)
            if not admin_mode:
                accessible_deck_ids = browse_card_repository.accessible_browse_deck_ids(
                    user_id=user_id,
                    admin_mode=admin_mode,
                )
                if selected_deck_id not in accessible_deck_ids:
                    raise BrowseCardUpdateError("Deck is not accessible", status=403)
            note_obj.deck_id = selected_deck_id

    if validated.update_tags:
        note_obj.tags = validated.tags

    if validated.field_updates:
        next_values = dict(note_obj.field_values or {})
        for key_name, value in validated.field_updates.items():
            next_values[key_name] = value
        note_obj.field_values = next_values

    browse_card_repository.commit_changes()

    now = _utcnow()
    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    progress = browse_card_repository.load_browse_progress(
        user_id=user_id,
        card_id=card_obj.id,
    )
    return {
        "success": True,
        "row": vocabulary_ctrl.build_browse_row(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress,
            timezone_name=timezone_name,
        ),
        "detail": vocabulary_ctrl.build_browse_card_detail(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress,
            timezone_name=timezone_name,
        ),
    }


def _build_browse_detail_payload(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    card_obj,
) -> dict[str, Any]:
    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    progress = browse_card_repository.load_browse_progress(
        user_id=user_id,
        card_id=card_obj.id,
    )
    now = _utcnow()
    return vocabulary_ctrl.build_browse_card_detail(
        card_obj,
        deck_lookup,
        now,
        progress_obj=progress,
        timezone_name=timezone_name,
    )


def _clone_scope_deck_lookup(*, user_id: int, clone_scope) -> dict[int, str]:
    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=False,
    )
    for source_deck_id, local_deck_id in (clone_scope.source_to_local_deck_id or {}).items():
        local_name = deck_lookup.get(int(local_deck_id))
        if local_name:
            deck_lookup.setdefault(int(source_deck_id), local_name)
    return deck_lookup


def _collect_note_media_refs(note_obj) -> set[str]:
    refs: set[str] = set()
    if note_obj is None:
        return refs
    for asset in note_obj.media_assets or []:
        asset_id = str(getattr(asset, "id", "") or "").strip()
        if asset_id:
            refs.add(asset_id)
            refs.add(f"/media/proxy/{asset_id}")
        filename = str(getattr(asset, "filename", "") or "").strip()
        if filename:
            refs.add(filename)
            refs.add(f"[sound:{filename}]")
    return refs


def _normalize_tags_payload(raw_tags: object) -> list[str]:
    if isinstance(raw_tags, list):
        return [str(item).strip() for item in raw_tags if str(item).strip()]
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def _apply_clone_overlay_to_browse_payload(
    *,
    payload: dict[str, Any],
    card_obj,
    clone_scope,
    deck_lookup: dict[int, str],
) -> dict[str, Any]:
    from app.services import flashcards_share as share_ctrl

    note_obj = card_obj.note
    if note_obj is None or note_obj.deck_id is None:
        return payload

    source_note_type_id = (clone_scope.install.source_note_type_id or note_obj.note_type_id or "").strip()
    if source_note_type_id:
        schema_view = share_ctrl.build_clone_schema_view(
            install=clone_scope.install,
            source_note_type_id=source_note_type_id,
        )
        overlay_field_defs = schema_view.field_defs or (note_obj.note_type.field_defs if note_obj.note_type else [])
        overlay_field_values = share_ctrl.apply_clone_note_field_overrides(
            install=clone_scope.install,
            source_note=note_obj,
            schema_view=schema_view,
        )
    else:
        overlay_field_defs = note_obj.note_type.field_defs if note_obj.note_type else []
        overlay_field_values = dict(note_obj.field_values or {})

    normalized_values = {
        str(key).strip(): "" if value is None else str(value)
        for key, value in dict(overlay_field_values or {}).items()
        if str(key).strip()
    }
    ordered_defs = sorted(
        overlay_field_defs or [],
        key=lambda item: (int(getattr(item, "position", 0) or 0), str(getattr(item, "name", "")).lower()),
    )

    local_deck_id = (
        (clone_scope.source_to_local_deck_id or {}).get(int(note_obj.deck_id))
        or clone_scope.install.local_deck_id
    )
    local_deck_name = deck_lookup.get(int(local_deck_id or 0), "")

    proxy_note = SimpleNamespace(
        field_values=normalized_values,
        note_type=SimpleNamespace(field_defs=ordered_defs),
    )
    display_triplet = vocabulary_ctrl.note_display_triplet(proxy_note)

    card_payload = payload.get("card")
    if isinstance(card_payload, dict):
        card_payload["word"] = display_triplet.get("word", "")
        card_payload["reading"] = display_triplet.get("reading", "")
        card_payload["meaning"] = display_triplet.get("meaning", "")
        if local_deck_id is not None:
            card_payload["deck_id"] = int(local_deck_id)
        if local_deck_name:
            card_payload["deck_name"] = local_deck_name

    note_payload = payload.get("note")
    if isinstance(note_payload, dict):
        note_payload["field_values"] = normalized_values
        if local_deck_id is not None:
            note_payload["deck_id"] = int(local_deck_id)
        note_payload["deck_name"] = local_deck_name

    note_type_fields_payload = []
    for field_def in ordered_defs:
        field_name = str(getattr(field_def, "name", "") or "").strip()
        if not field_name:
            continue
        try:
            field_position = int(getattr(field_def, "position", 0) or 0)
        except (TypeError, ValueError):
            field_position = 0
        note_type_fields_payload.append(
            {
                "name": field_name,
                "field_type": str(getattr(field_def, "field_type", "text") or "text"),
                "required": bool(getattr(field_def, "required", False)),
                "position": field_position,
            }
        )
    fields_payload = list(note_type_fields_payload)
    existing_names = {field_def["name"] for field_def in note_type_fields_payload}
    for key in normalized_values:
        if key in existing_names:
            continue
        fields_payload.append(
            {
                "name": key,
                "field_type": "text",
                "required": False,
                "position": 9999,
            }
        )
    fields_payload.sort(key=lambda item: (int(item["position"]), item["name"].lower()))
    payload["fields"] = fields_payload
    payload["note_type_fields"] = note_type_fields_payload
    return payload
