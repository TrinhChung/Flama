"""Application service for browse card detail updates."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Mapping

from sqlalchemy import func
from sqlalchemy.orm import aliased, selectinload

UTC = timezone.utc

from app.repositories import browse_card_repository
from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    active_progress_expr,
    load_card_progress_map,
    normalized_queue_expr,
    review_due_expr,
)
from app.validators import (
    RequestValidationError,
    escape_like_pattern,
    sanitize_query_text,
    validate_browse_card_update_request,
    validate_legacy_browse_note_update_request,
)
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import Card, DeckInstall, Note


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


class BrowseApiError(ValueError):
    """Typed error shared by legacy and V1 Browse HTTP adapters."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.field = field
        self.code = code


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


def build_browse_deck_tree(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
) -> dict[str, Any]:
    return {
        "tree": vocabulary_ctrl.build_browse_deck_tree_payload(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
        )
    }


def build_browse_decks(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
) -> dict[str, Any]:
    tree = build_browse_deck_tree(
        user_id=user_id,
        admin_mode=admin_mode,
        timezone_name=timezone_name,
    )["tree"]
    flat_items: list[dict[str, Any]] = []

    def _flatten(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            flat_items.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "parent_id": node["parent_id"],
                    "counts": node.get("counts", {}),
                }
            )
            _flatten(node.get("children", []))

    _flatten(tree)
    return {"decks": flat_items, "tree": tree}


def list_browse_cards(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the Browse card page while preserving logical-clone visibility."""
    from app.services import flashcards_share as share_ctrl

    deck_id_raw = str(query_args.get("deck_id") or "").strip()
    include_subdecks_raw = str(query_args.get("include_subdecks") or "1").strip().lower()
    include_subdecks = include_subdecks_raw not in {"0", "false", "no"}
    try:
        keyword = sanitize_query_text(query_args.get("q"), field_name="q", max_length=120)
        tag = sanitize_query_text(query_args.get("tag"), field_name="tag", max_length=80)
    except RequestValidationError as exc:
        raise BrowseApiError(
            str(exc),
            status=exc.status,
            field=exc.field,
            code=exc.code,
        ) from exc

    status = str(query_args.get("status") or "all").strip().lower()
    sort_by = str(query_args.get("sort_by") or "due").strip().lower()
    sort_dir = str(query_args.get("sort_dir") or "asc").strip().lower()
    if status not in {"all", NEW_QUEUE, "learn", "due", REVIEW_QUEUE}:
        raise BrowseApiError("Invalid status filter.", field="status")
    if sort_by not in {"due", "deck", "word"}:
        raise BrowseApiError("Invalid sort_by.", field="sort_by")
    if sort_dir not in {"asc", "desc"}:
        raise BrowseApiError("Invalid sort_dir.", field="sort_dir")

    try:
        page = max(1, int(query_args.get("page") or "1"))
        per_page = max(20, min(200, int(query_args.get("per_page") or "100")))
    except (TypeError, ValueError) as exc:
        raise BrowseApiError("Invalid page/per_page") from exc

    def _empty_result() -> dict[str, Any]:
        return {
            "items": [],
            "page": page,
            "per_page": per_page,
            "total": 0,
            "pages": 0,
            "has_next": False,
        }

    scoped_decks = vocabulary_ctrl.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    deck_lookup = {deck.id: deck.name for deck in scoped_decks}
    children_by_parent = vocabulary_ctrl.deck_children_map(scoped_decks)
    scoped_ids = {deck.id for deck in scoped_decks}
    selected_ids: set[int] | None = None
    if deck_id_raw:
        try:
            selected_deck_id = int(deck_id_raw)
        except (TypeError, ValueError) as exc:
            raise BrowseApiError("Invalid deck_id") from exc
        if selected_deck_id not in scoped_ids:
            raise BrowseApiError("Deck not found", status=404)
        if include_subdecks:
            selected_ids = set(
                vocabulary_ctrl.collect_subtree_ids(selected_deck_id, children_by_parent)
            )
        else:
            selected_ids = {selected_deck_id}

    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .outerjoin(progress_alias, progress_join)
        .options(
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.template),
        )
    )
    if admin_mode:
        if selected_ids:
            query = query.filter(Note.deck_id.in_(selected_ids))
        elif scoped_ids:
            query = query.filter(Note.deck_id.in_(scoped_ids))
        else:
            return _empty_result()
    else:
        local_scope_ids = set(selected_ids or scoped_ids)
        clone_scopes = []
        source_to_local_deck_id: dict[int, int] = {}

        if selected_ids is not None:
            scope_candidates = sorted(local_scope_ids)
        else:
            install_root_rows = (
                db.session.query(DeckInstall.local_deck_id)
                .filter(
                    DeckInstall.user_id == user_id,
                    DeckInstall.clone_mode == "logical_overlay",
                    DeckInstall.local_deck_id.isnot(None),
                )
                .distinct()
                .all()
            )
            scope_candidates = [
                int(row[0])
                for row in install_root_rows
                if row and row[0] is not None
            ]

        covered_local_ids: set[int] = set()
        seen_scope_keys: set[tuple[str, int]] = set()
        for local_scope_deck_id in scope_candidates:
            if selected_ids is not None and local_scope_deck_id in covered_local_ids:
                continue
            clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
                user_id=user_id,
                local_deck_id=int(local_scope_deck_id),
            )
            if clone_scope is None or not clone_scope.source_deck_ids:
                continue
            scope_key = (clone_scope.install.id, int(clone_scope.local_scope_deck_id))
            if scope_key in seen_scope_keys:
                continue
            seen_scope_keys.add(scope_key)
            clone_scopes.append(clone_scope)
            covered_local_ids.update(
                int(deck_id)
                for deck_id in clone_scope.local_deck_ids
                if deck_id is not None
            )
            for source_deck_id, local_deck_id in (
                clone_scope.source_to_local_deck_id or {}
            ).items():
                source_to_local_deck_id.setdefault(
                    int(source_deck_id),
                    int(local_deck_id),
                )

        visibility_filters = []
        if local_scope_ids:
            visibility_filters.append(
                db.and_(
                    Note.user_id == user_id,
                    Note.deck_id.in_(local_scope_ids),
                )
            )
        for clone_scope in clone_scopes:
            scope_filters = [Note.deck_id.in_(clone_scope.source_deck_ids)]
            if clone_scope.source_owner_user_id is not None:
                scope_filters.append(Note.user_id == clone_scope.source_owner_user_id)
            if clone_scope.base_snapshot_at is not None:
                scope_filters.extend(
                    [
                        Note.created_at <= clone_scope.base_snapshot_at,
                        Card.created_at <= clone_scope.base_snapshot_at,
                    ]
                )
            visibility_filters.append(db.and_(*scope_filters))

        if not visibility_filters:
            return _empty_result()
        query = query.filter(db.or_(*visibility_filters))

        for source_deck_id, local_deck_id in source_to_local_deck_id.items():
            local_name = deck_lookup.get(local_deck_id)
            if local_name:
                deck_lookup.setdefault(source_deck_id, local_name)

    if keyword:
        keyword_like = f"%{escape_like_pattern(keyword.lower())}%"
        query = query.filter(
            func.lower(db.cast(Note.field_values, db.Text)).like(
                keyword_like,
                escape="\\",
            )
        )
    if tag:
        tag_like = f"%{escape_like_pattern(tag.lower())}%"
        query = query.filter(
            func.lower(db.cast(Note.tags, db.Text)).like(tag_like, escape="\\")
        )

    now = _utcnow()
    normalized_progress_queue = normalized_queue_expr(progress_alias)
    query = query.filter(active_progress_expr(progress_alias))
    if status == NEW_QUEUE:
        query = query.filter(
            db.or_(
                progress_alias.id.is_(None),
                normalized_progress_queue == NEW_QUEUE,
            )
        )
    elif status == "learn":
        query = query.filter(
            normalized_progress_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE])
        )
    elif status in {"due", REVIEW_QUEUE}:
        query = query.filter(
            normalized_progress_queue == REVIEW_QUEUE,
            review_due_expr(progress_alias, now=now),
        )

    if sort_by == "deck":
        query = query.outerjoin(Deck, Note.deck_id == Deck.id)
        if sort_dir == "desc":
            query = query.order_by(Deck.name.desc(), Card.updated_at.desc())
        else:
            query = query.order_by(Deck.name.asc(), Card.updated_at.desc())
    elif sort_by == "word":
        sort_expr = func.lower(db.cast(Note.field_values, db.Text))
        query = query.order_by(
            sort_expr.desc() if sort_dir == "desc" else sort_expr.asc(),
            Card.updated_at.desc(),
        )
    else:
        due_sort_day_expr = db.case(
            (normalized_progress_queue == REVIEW_QUEUE, progress_alias.due_day),
            else_=None,
        )
        due_sort_expr = progress_alias.due_at
        if sort_dir == "desc":
            query = query.order_by(
                due_sort_day_expr.is_(None),
                due_sort_day_expr.desc(),
                due_sort_expr.is_(None),
                due_sort_expr.desc(),
                Card.updated_at.desc(),
            )
        else:
            query = query.order_by(
                due_sort_day_expr.is_(None),
                due_sort_day_expr.asc(),
                due_sort_expr.is_(None),
                due_sort_expr.asc(),
                Card.updated_at.desc(),
            )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    progress_map = load_card_progress_map(
        user_id=user_id,
        card_ids=[card_obj.id for card_obj in pagination.items],
    )
    rows = []
    for card_obj in pagination.items:
        row_payload = vocabulary_ctrl.build_browse_row(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress_map.get(card_obj.id),
            timezone_name=timezone_name,
        )
        if not admin_mode and card_obj.note and card_obj.note.user_id != user_id:
            clone_scope = share_ctrl.resolve_clone_scope_for_card(
                user_id=user_id,
                card_obj=card_obj,
            )
            if clone_scope is not None and share_ctrl.is_card_visible_in_clone_scope(
                scope=clone_scope,
                card_obj=card_obj,
            ):
                adjusted_payload = _apply_clone_overlay_to_browse_payload(
                    payload={"card": row_payload, "note": {}, "fields": []},
                    card_obj=card_obj,
                    clone_scope=clone_scope,
                    deck_lookup=deck_lookup,
                )
                row_payload = adjusted_payload.get("card") or row_payload
        rows.append(row_payload)
    return {
        "items": rows,
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
    }


def get_browse_card_detail(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    card_id: str,
) -> dict[str, Any]:
    from app.services import flashcards_share as share_ctrl

    card_obj = browse_card_repository.load_card_for_browse_update(card_id=card_id)
    if not card_obj:
        raise BrowseApiError("Card not found", status=404)

    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    clone_scope = None
    if not admin_mode and card_obj.note and card_obj.note.user_id != user_id:
        clone_scope = share_ctrl.resolve_clone_scope_for_card(
            user_id=user_id,
            card_obj=card_obj,
        )
        if clone_scope is None or not share_ctrl.is_card_visible_in_clone_scope(
            scope=clone_scope,
            card_obj=card_obj,
        ):
            raise BrowseApiError("Card not found", status=404)
        for source_deck_id, local_deck_id in (
            clone_scope.source_to_local_deck_id or {}
        ).items():
            local_name = deck_lookup.get(int(local_deck_id))
            if local_name:
                deck_lookup.setdefault(int(source_deck_id), local_name)

    progress = browse_card_repository.load_browse_progress(
        user_id=user_id,
        card_id=card_obj.id,
    )
    payload = vocabulary_ctrl.build_browse_card_detail(
        card_obj,
        deck_lookup,
        _utcnow(),
        progress_obj=progress,
        timezone_name=timezone_name,
    )
    if clone_scope is not None:
        payload = _apply_clone_overlay_to_browse_payload(
            payload=payload,
            card_obj=card_obj,
            clone_scope=clone_scope,
            deck_lookup=deck_lookup,
        )
    return payload


def delete_browse_card(
    *,
    user_id: int,
    admin_mode: bool,
    card_id: str,
) -> dict[str, bool]:
    query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id)
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    card_obj = query.first()
    if not card_obj:
        raise BrowseApiError("Card not found", status=404)

    note_id = card_obj.note_id
    db.session.delete(card_obj)
    db.session.flush()
    if Card.query.filter(Card.note_id == note_id).count() == 0:
        note_obj = db.session.get(Note, note_id)
        if note_obj:
            db.session.delete(note_obj)
    db.session.commit()
    return {"success": True}


def build_legacy_notes_payload(cards_payload: dict[str, Any]) -> dict[str, Any]:
    notes = []
    for item in cards_payload.get("items", []):
        notes.append(
            {
                "id": item.get("note_id"),
                "sort_field": item.get("word", ""),
                "card_type": item.get("card_type", ""),
                "deck": item.get("deck_name", ""),
                "created_at": "",
                "fields": {
                    "Word": item.get("word", ""),
                    "Reading": item.get("reading", ""),
                    "Meaning": item.get("meaning", ""),
                },
            }
        )
    return {"notes": notes, "columns": ["Word", "Reading", "Meaning"]}


def update_legacy_browse_note(
    *,
    user_id: int,
    admin_mode: bool,
    note_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_obj = db.session.get(Note, note_id)
    if not note_obj:
        raise BrowseApiError("Note not found", status=404)
    if not admin_mode and note_obj.user_id != user_id:
        raise BrowseApiError("Unauthorized", status=403)
    note_type_obj = note_obj.note_type
    if note_type_obj is None:
        raise BrowseApiError("Note type not found", status=404)

    try:
        merged_values = validate_legacy_browse_note_update_request(
            note_type=note_type_obj,
            payload=payload,
            current_values=dict(note_obj.field_values or {}),
            note_media_ids=_collect_note_media_refs(note_obj),
        )
    except RequestValidationError as exc:
        raise BrowseApiError(
            str(exc),
            status=exc.status,
            field=exc.field,
            code=exc.code,
        ) from exc

    note_obj.field_values = merged_values
    db.session.commit()
    return {
        "success": True,
        "note": {"id": note_obj.id, "fields": note_obj.field_values},
    }


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
