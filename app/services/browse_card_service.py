"""Application service for browse card detail updates."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Mapping

from sqlalchemy import case, false, func
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
from models.flashcard import Card, DeckInstall, Note, NoteType


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
                    "path": node.get("path") or node["name"],
                    "parent_id": node["parent_id"],
                    "note_type_id": node.get("note_type_id"),
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
        per_page = max(1, min(500, int(query_args.get("per_page") or "100")))
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
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            selectinload(Card.template),
        )
    )
    clone_scopes = []
    clone_scope_conditions: list[tuple[Any, Any]] = []
    owned_visibility_condition = None
    if admin_mode:
        if selected_ids:
            query = query.filter(Note.deck_id.in_(selected_ids))
        elif scoped_ids:
            query = query.filter(Note.deck_id.in_(scoped_ids))
        else:
            return _empty_result()
    else:
        local_scope_ids = set(selected_ids or scoped_ids)
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
            owned_visibility_condition = db.and_(
                Note.user_id == user_id,
                Note.deck_id.in_(local_scope_ids),
            )
            visibility_filters.append(owned_visibility_condition)
        for clone_scope in clone_scopes:
            scope_filters = [Note.deck_id.in_(clone_scope.source_deck_ids)]
            if clone_scope.source_owner_user_id is not None:
                scope_filters.append(Note.user_id == clone_scope.source_owner_user_id)
            release_membership = share_ctrl.release_note_membership_filter(
                clone_scope.install,
                Note.id,
            )
            if release_membership is not None:
                scope_filters.append(release_membership)
            elif clone_scope.base_snapshot_at is not None:
                scope_filters.extend(
                    [
                        Note.created_at <= clone_scope.base_snapshot_at,
                        Card.created_at <= clone_scope.base_snapshot_at,
                    ]
                )
            scope_condition = db.and_(*scope_filters)
            visibility_filters.append(scope_condition)
            clone_scope_conditions.append((clone_scope, scope_condition))

        if not visibility_filters:
            return _empty_result()
        query = query.filter(db.or_(*visibility_filters))

        for source_deck_id, local_deck_id in source_to_local_deck_id.items():
            local_name = deck_lookup.get(local_deck_id)
            if local_name:
                deck_lookup.setdefault(source_deck_id, local_name)

    clone_projections: list[dict[str, Any]] = []
    if (
        not admin_mode
        and clone_scope_conditions
        and (bool(keyword) or sort_by == "word")
    ):
        initial_field_names_cache: dict[tuple[str, int], dict[str, str]] = {}
        earlier_scope_condition = None
        for clone_scope, raw_scope_condition in clone_scope_conditions:
            exclusive_scope_condition = raw_scope_condition
            if earlier_scope_condition is not None:
                exclusive_scope_condition = db.and_(
                    raw_scope_condition,
                    ~earlier_scope_condition,
                )
                earlier_scope_condition = db.or_(
                    earlier_scope_condition,
                    raw_scope_condition,
                )
            else:
                earlier_scope_condition = raw_scope_condition

            install = clone_scope.install
            source_note_type_id = str(
                install.source_note_type_id or ""
            ).strip()
            if not source_note_type_id:
                clone_projections.append(
                    {
                        "condition": exclusive_scope_condition,
                        "all_fields": [],
                        "word": browse_card_repository.owned_note_word_expression(),
                    }
                )
                continue

            schema_view = share_ctrl.build_clone_schema_view(
                install=install,
                source_note_type_id=source_note_type_id,
            )
            release = (
                install.applied_release
                if install.version_mode == "release"
                and install.applied_release_id
                else None
            )
            target_sequence = int(release.sequence_no) if release is not None else None
            deck_item_id = str(release.deck_item_id) if release is not None else None
            initial_field_names: dict[str, str] = {}
            if release is not None:
                initial_cache_key = (deck_item_id, target_sequence)
                initial_field_names = initial_field_names_cache.get(
                    initial_cache_key,
                    {},
                )
                if initial_cache_key not in initial_field_names_cache:
                    initial_field_names = (
                        browse_card_repository.load_initial_release_field_names(
                            deck_item_id=deck_item_id,
                            through_sequence=target_sequence,
                        )
                    )
                    initial_field_names_cache[initial_cache_key] = initial_field_names

            added_field_names = browse_card_repository.load_clone_added_field_names(
                deck_install_id=str(install.id)
            )
            all_field_expressions = []
            word_field_expressions = []
            reverse_rename_map = {
                str(resolved_name): str(source_name)
                for source_name, resolved_name in (
                    schema_view.renamed_field_names or {}
                ).items()
            }
            for field_def in schema_view.field_defs or []:
                field_id = str(getattr(field_def, "id", "") or "").strip()
                field_name = str(
                    getattr(field_def, "name", "") or ""
                ).strip()
                if not field_id or not field_name:
                    continue
                is_added_field = field_id in added_field_names
                source_field_id = None if is_added_field else field_id
                checkpoint_field_name = None
                if not is_added_field:
                    checkpoint_field_name = (
                        initial_field_names.get(field_id)
                        if release is not None
                        else reverse_rename_map.get(field_name, field_name)
                    )
                if (
                    release is not None
                    and not is_added_field
                    and not checkpoint_field_name
                ):
                    # Compatibility for early release rows that predate stable
                    # field-name events. Current releases always have the map.
                    checkpoint_field_name = field_name
                override_names = [field_name]
                if checkpoint_field_name:
                    override_names.append(checkpoint_field_name)
                if is_added_field:
                    override_names.append(added_field_names[field_id])
                field_expression = (
                    browse_card_repository.clone_effective_field_text_expression(
                        deck_install_id=str(install.id),
                        deck_item_id=deck_item_id,
                        target_release_sequence=target_sequence,
                        source_field_def_id=source_field_id,
                        checkpoint_field_name=checkpoint_field_name,
                        override_field_names=override_names,
                    )
                )
                all_field_expressions.append(field_expression)
                if str(getattr(field_def, "field_type", "") or "").lower() in (
                    browse_card_repository.TEXT_FIELD_TYPES
                ):
                    word_field_expressions.append(field_expression)

            clone_projections.append(
                {
                    "condition": exclusive_scope_condition,
                    "all_fields": all_field_expressions,
                    "word": browse_card_repository.first_non_empty_text_expression(
                        word_field_expressions
                    ),
                }
            )

    if keyword:
        keyword_like = f"%{escape_like_pattern(keyword.lower())}%"
        if admin_mode:
            query = query.filter(
                func.lower(db.cast(Note.field_values, db.Text)).like(
                    keyword_like,
                    escape="\\",
                )
            )
        else:
            effective_search_conditions = []
            if owned_visibility_condition is not None:
                effective_search_conditions.append(
                    db.and_(
                        owned_visibility_condition,
                        func.lower(db.cast(Note.field_values, db.Text)).like(
                            keyword_like,
                            escape="\\",
                        ),
                    )
                )
            for projection in clone_projections:
                effective_search_conditions.append(
                    db.and_(
                        projection["condition"],
                        browse_card_repository.effective_fields_search_condition(
                            projection["all_fields"],
                            keyword_like=keyword_like,
                        ),
                    )
                )
            query = query.filter(
                db.or_(*effective_search_conditions)
                if effective_search_conditions
                else false()
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
        owned_word_expression = browse_card_repository.owned_note_word_expression()
        if admin_mode:
            sort_expr = func.lower(func.coalesce(owned_word_expression, ""))
        else:
            word_cases = []
            if owned_visibility_condition is not None:
                word_cases.append(
                    (owned_visibility_condition, owned_word_expression)
                )
            word_cases.extend(
                (projection["condition"], projection["word"])
                for projection in clone_projections
            )
            sort_expr = func.lower(
                func.coalesce(
                    case(*word_cases, else_=owned_word_expression)
                    if word_cases
                    else owned_word_expression,
                    "",
                )
            )
        query = query.order_by(
            sort_expr.desc() if sort_dir == "desc" else sort_expr.asc(),
            Card.updated_at.desc(),
            Card.id.asc(),
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
    clone_scope_by_card_id: dict[str, Any] = {}
    release_note_ids: dict[str, set[str]] = {}
    release_install_by_id: dict[str, Any] = {}
    clone_install_ids: set[str] = set()
    clone_source_note_ids: set[str] = set()
    if not admin_mode and clone_scopes:
        for card_obj in pagination.items:
            note_obj = card_obj.note
            if note_obj is None or note_obj.user_id == user_id or note_obj.deck_id is None:
                continue
            matching_scope = next(
                (
                    scope
                    for scope in clone_scopes
                    if int(note_obj.deck_id) in set(scope.source_deck_ids)
                    and (
                        scope.source_owner_user_id is None
                        or int(note_obj.user_id) == int(scope.source_owner_user_id)
                    )
                ),
                None,
            )
            if matching_scope is None:
                continue
            clone_scope_by_card_id[str(card_obj.id)] = matching_scope
            clone_install_ids.add(str(matching_scope.install.id))
            clone_source_note_ids.add(str(note_obj.id))
            release_id = str(matching_scope.install.applied_release_id or "")
            if matching_scope.install.version_mode == "release" and release_id:
                release_note_ids.setdefault(release_id, set()).add(str(note_obj.id))
                release_install_by_id[release_id] = matching_scope.install

    batch_overrides: dict[tuple[str, str], list] = {}
    if clone_install_ids and clone_source_note_ids:
        from app.repositories import flashcards_share_repository

        batch_overrides = flashcards_share_repository.get_clone_note_field_overrides_batch(
            list(clone_install_ids),
            list(clone_source_note_ids),
        )

    release_values_by_note: dict[tuple[str, str], dict[str, Any]] = {}
    if release_note_ids:
        from app.services import deck_release_service

        for release_id, note_ids in release_note_ids.items():
            resolved_values = deck_release_service.get_note_values_for_ids_at_release(
                release_install_by_id[release_id].applied_release,
                note_ids,
            )
            for note_id, values in resolved_values.items():
                release_values_by_note[(release_id, str(note_id))] = values

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
            clone_scope = clone_scope_by_card_id.get(str(card_obj.id))
            if clone_scope is not None:
                release_id = str(clone_scope.install.applied_release_id or "")
                override_key = (str(clone_scope.install.id), str(card_obj.note.id))
                adjusted_payload = _apply_clone_overlay_to_browse_payload(
                    payload={"card": row_payload, "note": {}, "fields": []},
                    card_obj=card_obj,
                    clone_scope=clone_scope,
                    deck_lookup=deck_lookup,
                    base_field_values=release_values_by_note.get(
                        (release_id, str(card_obj.note.id))
                    ),
                    note_override_rows=batch_overrides.get(override_key),
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
    clean_card_id = str(card_id).strip()
    query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == clean_card_id)
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    card_obj = query.first()
    if not card_obj:
        existing_card = Card.query.filter(Card.id == clean_card_id).first()
        if existing_card is not None and not admin_mode:
            raise BrowseApiError(
                "Không thể xóa thẻ thuộc bộ bài gốc được chia sẻ/clone. Bộ bài gốc được bảo vệ để không ảnh hưởng đến tác giả và những người học khác.",
                status=403,
                code="SHARED_SOURCE_CARD_PROTECTED",
            )
        raise BrowseApiError("Card not found", status=404)

    from app.services import deck_working_tree_service

    if card_obj.note is not None and deck_working_tree_service.note_has_shared_release_dependents(
        card_obj.note
    ):
        raise BrowseApiError(
            "Published shared cards cannot be hard-deleted because learner history must be preserved.",
            status=409,
            code="SHARED_ENTITY_RETIRE_REQUIRED",
        )

    note_id = card_obj.note_id
    db.session.delete(card_obj)
    db.session.flush()
    if Card.query.filter(Card.note_id == note_id).count() == 0:
        note_obj = db.session.get(Note, note_id)
        if note_obj:
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=[
                    {
                        "note": note_obj,
                        "field_names": (note_obj.field_values or {}).keys(),
                        "operation": "remove",
                    }
                ],
            )
            db.session.delete(note_obj)
    db.session.commit()
    return {"success": True}


def delete_browse_cards_batch(
    *,
    user_id: int,
    admin_mode: bool,
    card_ids: list[str],
) -> dict[str, Any]:
    if not card_ids:
        return {"success": True, "deleted_count": 0}

    from app.services import deck_working_tree_service

    clean_card_ids = [str(cid).strip() for cid in card_ids if str(cid).strip()]
    if not clean_card_ids:
        return {"success": True, "deleted_count": 0}

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id.in_(clean_card_ids))
    )
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)

    cards_to_delete = query.all()
    if not cards_to_delete:
        existing_cards = Card.query.filter(Card.id.in_(clean_card_ids)).all()
        if existing_cards and not admin_mode:
            raise BrowseApiError(
                "Không thể xóa các thẻ thuộc bộ bài gốc được chia sẻ/clone. Bộ bài gốc được bảo vệ để không ảnh hưởng đến tác giả và những người học khác.",
                status=403,
                code="SHARED_SOURCE_CARD_PROTECTED",
            )
        return {"success": True, "deleted_count": 0}

    # Verify none of the deleted cards have shared release dependents
    for card_obj in cards_to_delete:
        if card_obj.note is not None and deck_working_tree_service.note_has_shared_release_dependents(
            card_obj.note
        ):
            raise BrowseApiError(
                "Published shared cards cannot be hard-deleted because learner history must be preserved.",
                status=409,
                code="SHARED_ENTITY_RETIRE_REQUIRED",
            )

    note_ids = {card_obj.note_id for card_obj in cards_to_delete if card_obj.note_id}
    deleted_count = len(cards_to_delete)

    for card_obj in cards_to_delete:
        db.session.delete(card_obj)
    db.session.flush()

    for note_id in note_ids:
        remaining_cards_count = Card.query.filter(Card.note_id == note_id).count()
        if remaining_cards_count == 0:
            note_obj = db.session.get(Note, note_id)
            if note_obj:
                deck_working_tree_service.mark_note_field_batches_changed(
                    mutations=[
                        {
                            "note": note_obj,
                            "field_names": (note_obj.field_values or {}).keys(),
                            "operation": "remove",
                        }
                    ],
                )
                db.session.delete(note_obj)

    db.session.commit()
    return {"success": True, "deleted_count": deleted_count}


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

    changed_field_names = {
        key
        for key in set(note_obj.field_values or {}) | set(merged_values)
        if (note_obj.field_values or {}).get(key) != merged_values.get(key)
    }
    note_obj.field_values = merged_values
    if changed_field_names:
        from app.services import deck_working_tree_service

        deck_working_tree_service.mark_note_fields_changed(
            note=note_obj,
            field_names=changed_field_names,
        )
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
    from app.services import deck_working_tree_service

    original_deck_id = note_obj.deck_id
    accessible_deck_ids: set[int] | None = None
    if validated.update_deck:
        selected_deck_id = validated.deck_id
        if (
            original_deck_id != selected_deck_id
            and deck_working_tree_service.note_has_shared_release_dependents(
                note_obj
            )
        ):
            raise BrowseCardUpdateError(
                "A released shared note cannot move decks until release-aware membership moves are supported.",
                status=409,
                code="SHARED_ENTITY_RETIRE_REQUIRED",
            )
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
        if (
            list(note_obj.tags or []) != list(validated.tags or [])
            and deck_working_tree_service.note_has_shared_release_dependents(
                note_obj
            )
        ):
            raise BrowseCardUpdateError(
                "Tags on a released shared note cannot change until note metadata is versioned in deck releases.",
                status=409,
                code="SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
            )
        note_obj.tags = validated.tags

    if validated.field_updates:
        next_values = dict(note_obj.field_values or {})
        for key_name, value in validated.field_updates.items():
            next_values[key_name] = value
        note_obj.field_values = next_values

    deck_changed = validated.update_deck and original_deck_id != note_obj.deck_id
    if validated.field_updates and not deck_changed:
        deck_working_tree_service.mark_note_fields_changed(
            note=note_obj,
            field_names=validated.field_updates.keys(),
        )
    if deck_changed:
        all_field_names = list((note_obj.field_values or {}).keys())
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note_obj,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": original_deck_id,
                },
                {
                    "note": note_obj,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note_obj.deck_id,
                },
            ],
        )

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
    base_field_values: dict[str, Any] | None = None,
    note_override_rows: list[Any] | None = None,
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
            base_field_values=base_field_values,
            note_override_rows=note_override_rows,
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
    payload["can_upload_media"] = False
    payload["media_disabled_reason"] = "media_upload_not_supported_for_clone"
    return payload
