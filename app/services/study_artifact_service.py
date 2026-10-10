"""Versioned artifacts used by the React study renderer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from app.repositories.deck_tree_query import collect_subtree_ids
from app.services import flashcards_share_service
from app.services.effective_template_service import resolve_effective_template
from app.services.template_binding_service import apply_binding_projection, projection_metadata
from app.services.flashcard_renderer import (
    build_render_context,
    prepare_client_template_source,
    sanitize_css,
)
from models.deck_marketplace_item import DeckMarketplaceItem


RENDERER_ABI = "flama-client-mustache.v2"
TEMPLATE_SCHEMA = "study-template.v1"
CONTENT_SCHEMA = "study-content.v1"
MANIFEST_SCHEMA = "study-manifest.v1"
INTERVALS_SCHEMA = "study-intervals.v1"
TYPING_INPUT_SCHEMA = "study-typing-input.v1"


@dataclass(frozen=True)
class EffectiveStudyCard:
    card: Any
    note: Any
    template: Any
    field_defs: list[Any]
    field_values: dict[str, Any]
    clone_scope: flashcards_share_service.CloneDeckScope | None = None

    @property
    def install_id(self) -> str | None:
        if self.clone_scope is None:
            return None
        return str(self.clone_scope.install.id)


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return {
            str(key): _json_value(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256-{hashlib.sha256(encoded).hexdigest()}"


def serialize_field_defs(field_defs: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(getattr(item, "id", "") or ""),
            "name": str(getattr(item, "name", "") or ""),
            "field_type": str(getattr(item, "field_type", "text") or "text"),
            "required": bool(getattr(item, "required", False)),
            "position": int(getattr(item, "position", 0) or 0),
        }
        for item in sorted(
            field_defs,
            key=lambda row: (
                int(getattr(row, "position", 0) or 0),
                str(getattr(row, "name", "") or "").lower(),
            ),
        )
    ]


def build_effective_study_card(
    *,
    card: Any,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    clone_added_note_ids: frozenset[str] | None = None,
    note_override_rows_by_note_id: Mapping[str, list] | None = None,
    template_overrides: Mapping[str, Any] | None = None,
) -> EffectiveStudyCard:
    """Resolve a Card's effective content, owned or through a clone overlay.

    Callers building many Cards of one install may pass the install's added
    Note IDs, field-override rows, and resolved template sources loaded once.
    Without those contexts the existing clone content helpers resolve them.
    """
    note = card.note
    field_defs = list(note.note_type.field_defs)
    field_values = dict(note.field_values or {})
    if clone_scope is not None and (
        str(note.id) in clone_added_note_ids
        if clone_added_note_ids is not None
        else flashcards_share_service.is_clone_added_note(
            scope=clone_scope,
            note_id=note.id,
        )
    ):
        return apply_binding_projection(EffectiveStudyCard(
            card=card,
            note=note,
            template=resolve_effective_template(card, template_overrides=template_overrides),
            field_defs=field_defs,
            field_values=field_values,
            clone_scope=None,
        ))
    if clone_scope is not None:
        source_note_type_id = (
            clone_scope.install.source_note_type_id or note.note_type_id or ""
        ).strip()
        if source_note_type_id:
            schema_view = flashcards_share_service.build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            field_defs = list(schema_view.field_defs)
            field_values = flashcards_share_service.apply_clone_note_field_overrides(
                install=clone_scope.install,
                source_note=note,
                schema_view=schema_view,
                note_override_rows=(
                    list(note_override_rows_by_note_id.get(str(note.id), ()))
                    if note_override_rows_by_note_id is not None
                    else None
                ),
            )
    return apply_binding_projection(EffectiveStudyCard(
        card=card,
        note=note,
        template=resolve_effective_template(card, clone_scope, template_overrides=template_overrides),
        field_defs=field_defs,
        field_values=field_values,
        clone_scope=clone_scope,
    ))


def template_version(context: EffectiveStudyCard) -> str:
    context = apply_binding_projection(context)
    template = context.template
    material = {
        "schema_version": TEMPLATE_SCHEMA,
        "renderer_abi": RENDERER_ABI,
        "template_id": template.id,
        "front_source": template.front_html or "",
        "back_source": template.back_html or "",
        "shared_css": template.shared_css or "",
        "field_defs": serialize_field_defs(context.field_defs),
    }
    projection = _binding_projection_payload(context)
    if projection is not None:
        material["binding_projection"] = projection
    typing_input = typing_input_payload(template)
    if typing_input is not None:
        material["typing_input"] = typing_input
    return canonical_digest(material)


def typing_input_payload(template: Any) -> dict[str, Any] | None:
    """Expose the template's answers input so the host can run a typing mode.

    Only the key and display options travel; answers stay in the content
    artifact and the frontend alone compares them. Templates without an
    answers input keep their artifact (and version) unchanged.
    """
    for item in getattr(template, "input_schema", None) or []:
        if not isinstance(item, Mapping) or item.get("type") != "answers":
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            return None
        options = item.get("typing") if isinstance(item.get("typing"), Mapping) else {}
        return {
            "schema_version": TYPING_INPUT_SCHEMA,
            "key": key,
            "show_length": bool(options.get("show_length", True)),
            "hints": bool(options.get("hints", True)),
        }
    return None


def _binding_projection_payload(context):
    projection = projection_metadata(context)
    if projection is not None:
        projection["field_defs"] = serialize_field_defs(projection["field_defs"])
        projection["fingerprint"] = canonical_digest(projection)
    return projection


def _media_payload(context: EffectiveStudyCard) -> list[dict[str, Any]]:
    return [
        {
            "id": str(asset.id),
            "field_name": str(asset.field_name or ""),
            "filename": str(asset.filename or ""),
            "mime_type": str(asset.mime_type or "application/octet-stream"),
            "sha256": str(asset.sha256 or ""),
            "proxy_url": f"/media/proxy/{asset.id}",
        }
        for asset in sorted(
            context.note.media_assets or [],
            key=lambda item: (str(item.field_name or ""), str(item.id)),
        )
    ]


def content_version(context: EffectiveStudyCard) -> str:
    context = apply_binding_projection(context)
    return canonical_digest(
        {
            "schema_version": CONTENT_SCHEMA,
            "renderer_abi": RENDERER_ABI,
            "note_id": context.note.id,
            "field_defs": serialize_field_defs(context.field_defs),
            "field_values": context.field_values,
            "media": _media_payload(context),
        }
    )


def build_template_artifact(context: EffectiveStudyCard) -> dict[str, Any]:
    context = apply_binding_projection(context)
    front = prepare_client_template_source(
        context.template.front_html or "",
        context.field_defs,
    )
    back = prepare_client_template_source(
        context.template.back_html or "",
        context.field_defs,
    )
    artifact = {
        "schema_version": TEMPLATE_SCHEMA,
        "renderer_abi": RENDERER_ABI,
        "id": str(context.template.id),
        "version": template_version(context),
        "front_source": front["source"],
        "back_source": back["source"],
        "front_inline_scripts": front["inline_scripts"],
        "back_inline_scripts": back["inline_scripts"],
        "shared_css": sanitize_css(context.template.shared_css or ""),
        "field_defs": serialize_field_defs(context.field_defs),
    }
    projection = _binding_projection_payload(context)
    if projection is not None:
        artifact["binding_projection"] = projection
    typing_input = typing_input_payload(context.template)
    if typing_input is not None:
        artifact["typing_input"] = typing_input
    return artifact


def build_content_artifact(context: EffectiveStudyCard) -> dict[str, Any]:
    context = apply_binding_projection(context)
    template_sources = (
        str(context.template.front_html or ""),
        str(context.template.back_html or ""),
    )
    return {
        "schema_version": CONTENT_SCHEMA,
        "renderer_abi": RENDERER_ABI,
        "id": str(context.note.id),
        "note_id": str(context.note.id),
        "version": content_version(context),
        "field_values": _json_value(context.field_values),
        "render_context": build_render_context(
            context.field_defs,
            context.field_values,
            context.note.media_assets,
            template_sources=template_sources,
        ),
        "media": _media_payload(context),
    }


def review_state_version(
    *,
    progress: Any,
    deck_options: Any,
    timezone_name: str,
) -> str:
    progress_payload = None
    if progress is not None:
        progress_payload = {
            key: _json_value(getattr(progress, key, None))
            for key in (
                "queue",
                "step_index",
                "due_at",
                "due_day",
                "interval_days",
                "ease_factor",
                "reps",
                "lapses",
                "last_reviewed_at",
                "suspended_at",
            )
        }
    return canonical_digest(
        {
            "scheduler_contract": "anki-scheduler.v1",
            "timezone": timezone_name,
            "progress": progress_payload,
            "options": _json_value(deck_options),
        }
    )


def note_authority_review_state_version(
    *,
    enrollment_epoch: int,
    logical_note_key: str,
    subject_generation: int,
    authority_revision: int,
    semantic_state_hash: bytes,
    deck_options: Any,
    timezone_name: str,
) -> str:
    """Version one direct-read manifest from the canonical NOTE token."""

    if not isinstance(semantic_state_hash, bytes) or len(semantic_state_hash) != 32:
        raise ValueError("NOTE authority state hash must contain 32 bytes.")
    return canonical_digest(
        {
            "scheduler_contract": "anki-scheduler.v1",
            "authority_mode": "NOTE",
            "enrollment_epoch": int(enrollment_epoch),
            "logical_note_key": str(logical_note_key),
            "subject_generation": int(subject_generation),
            "authority_revision": int(authority_revision),
            "semantic_state_hash": semantic_state_hash.hex(),
            "timezone": timezone_name,
            "options": _json_value(deck_options),
        }
    )


PRISTINE_NOTE_STATE_MARKER = hashlib.sha256(b"flama.note-authority.pristine.v1").digest()


def pristine_note_review_state_version(
    *,
    enrollment_epoch: int,
    logical_note_key: str,
    deck_options: Any,
    timezone_name: str,
) -> str:
    """Version a never-studied NOTE read before its first-state materialization.

    Generation/revision 0 and the marker hash cannot collide with a
    materialized subject (generation >= 1 and a real semantic state hash).
    """

    return note_authority_review_state_version(
        enrollment_epoch=enrollment_epoch,
        logical_note_key=logical_note_key,
        subject_generation=0,
        authority_revision=0,
        semantic_state_hash=PRISTINE_NOTE_STATE_MARKER,
        deck_options=deck_options,
        timezone_name=timezone_name,
    )


def _same_effective_base(context: EffectiveStudyCard) -> bool:
    base_defs = serialize_field_defs(list(context.note.note_type.field_defs))
    return (
        serialize_field_defs(context.field_defs) == base_defs
        and context.field_values == dict(context.note.field_values or {})
    )


def _item_contains_note(item: DeckMarketplaceItem, note: Any) -> bool:
    if item.source_note_type_id and item.source_note_type_id != note.note_type_id:
        return False
    if item.source_deck_id is None:
        return bool(item.source_note_type_id)
    if note.deck_id is None:
        return False
    return int(note.deck_id) in set(collect_subtree_ids(int(item.source_deck_id)))


def public_deck_item(context: EffectiveStudyCard) -> DeckMarketplaceItem | None:
    """Return the public/free source item when the effective artifact is shareable."""
    if not _same_effective_base(context):
        return None

    if context.clone_scope is not None:
        item = context.clone_scope.install.deck_item
        if (
            item
            and item.publish_status == "published"
            and item.pricing_mode == "free"
            and _item_contains_note(item, context.note)
        ):
            return item
        return None

    candidates = (
        DeckMarketplaceItem.query.filter_by(
            owner_user_id=context.note.user_id,
            publish_status="published",
            pricing_mode="free",
        )
        .order_by(DeckMarketplaceItem.published_at.desc())
        .all()
    )
    return next(
        (item for item in candidates if _item_contains_note(item, context.note)),
        None,
    )


def public_item_allows_card(item: DeckMarketplaceItem, card: Any) -> bool:
    return bool(
        item.publish_status == "published"
        and item.pricing_mode == "free"
        and card is not None
        and card.note is not None
        and card.note.user_id == item.owner_user_id
        and _item_contains_note(item, card.note)
    )
