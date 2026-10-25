"""Application service for browse card detail updates."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace
from typing import Any, Mapping

from flask import current_app
from sqlalchemy import LargeBinary, case, cast, false, func
from sqlalchemy.orm import aliased

UTC = timezone.utc

from app.repositories import browse_card_repository, note_analytics_read_repository
from app.repositories.field_value_query_repository import note_values_search_condition
from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.repositories import study_repository
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    active_progress_expr,
    review_due_expr,
)
from app.services.scheduler_config_service import (
    resolve_deck_options,
    resolve_scheduler_runtime_settings,
)
from app.services import study_progress_lifecycle_mirror_service
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.study_authority_read_service import (
    StudyAuthorityCardRead,
    StudyAuthorityReadError,
    load_study_authority_card_read,
    load_study_authority_card_reads,
)
from app.validators import (
    RequestValidationError,
    escape_like_pattern,
    sanitize_query_text,
    validate_browse_card_update_request,
    validate_legacy_browse_note_update_request,
)
from models import db
from models.study_progress_subject import StudyProgressSubject
from models.card import forget_card_identities, get_card, load_cards
from models.deck import Deck
from models.field_types import stored_field_value
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


@contextmanager
def _study_authority_conflict():
    """Turn a learner fence or authority-read refusal into a rolled-back 409."""
    try:
        yield
    except (StudyAuthorityFenceError, StudyAuthorityReadError) as exc:
        db.session.rollback()
        raise BrowseApiError(str(exc), status=409, code=str(exc.code)) from exc


def _visible_clone_scope(*, user_id: int, card_obj):
    """The learner's logical-overlay scope that presents this source Card, or None.

    ``resolve_clone_scope_for_card`` returns a scope only after running the
    same membership query as ``is_card_visible_in_clone_scope``.
    """
    from app.repositories.browse_note_repository import BrowseNoteReference
    if isinstance(card_obj, BrowseNoteReference):
        return card_obj.clone_scope
    from app.services import flashcards_share as share_ctrl

    return share_ctrl.resolve_clone_scope_for_card(user_id=user_id, card_obj=card_obj)


def _clone_local_deck_id(clone_scope, note_obj) -> int | None:
    """The learner's local deck for a source Note: its mapped deck, else the install root."""
    return (clone_scope.source_to_local_deck_id or {}).get(
        int(note_obj.deck_id or 0)
    ) or clone_scope.install.local_deck_id


def _with_clone_deck_names(
    deck_lookup: dict[int, str],
    source_to_local_deck_id: Mapping[int, int] | None,
) -> dict[int, str]:
    """Name each source deck after the local deck that presents it."""
    for source_deck_id, local_deck_id in (source_to_local_deck_id or {}).items():
        local_name = deck_lookup.get(int(local_deck_id))
        if local_name:
            deck_lookup.setdefault(int(source_deck_id), local_name)
    return deck_lookup


def update_browse_card(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    card_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and persist browse editor mutations for a card."""
    card_obj = browse_card_repository.load_card_for_browse_update(card_id=card_id)
    if not card_obj:
        raise BrowseCardUpdateError("Card not found", status=404)

    note_obj = card_obj.note
    note_type_obj = note_obj.note_type if note_obj else None
    if note_obj is None or note_type_obj is None:
        raise BrowseCardUpdateError("Card note type not found", status=404)

    clone_scope = None
    if not admin_mode and note_obj.user_id != user_id:
        clone_scope = _visible_clone_scope(user_id=user_id, card_obj=card_obj)
        if clone_scope is None:
            raise BrowseCardUpdateError("Card not found", status=404)

    try:
        if clone_scope is None:
            from app.services.note_value_precondition_service import check_note_write_preconditions
            check_note_write_preconditions(note_obj, payload)
        else:
            from app.services.clone_field_identity_service import lock_clone_overlay_write
            clone_scope.install = lock_clone_overlay_write(clone_scope.install,
                expected_revision=payload.get("expected_overlay_revision") if isinstance(payload, dict) else None)
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
    with _study_authority_conflict():
        lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
        tree = vocabulary_ctrl.build_browse_deck_tree_payload(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
            # NOTE recounts every node below; skip the projection aggregate.
            progress_counts=False,
        )
        deck_ids: set[int] = set()

        def collect_deck_ids(nodes: list[dict[str, Any]]) -> None:
            for node in nodes:
                deck_ids.add(int(node["id"]))
                collect_deck_ids(node.get("children", []))

        collect_deck_ids(tree)
        # Admin-wide counts every Note in the
        # visible decks (with the admin's own state); a learner counts owned
        # Notes plus logical-overlay source Cards under their local deck.
        # Counted set-wise from canonical availability, like the dashboard,
        # instead of one locking authority read per Card (P5-11e).
        boundary_hour = int(resolve_scheduler_runtime_settings(user_id=user_id).day_boundary_hour_local)
        today_day_index = study_repository._today_day_index(
            now=_utcnow(),
            timezone_name=timezone_name,
            day_boundary_hour_local=boundary_hour,
        )
        direct_counts, _note_types = aggregate_deck_study_counts(
            db.session,
            learner_user_id=user_id,
            visible_deck_ids=sorted(deck_ids),
            today_day_index=today_day_index,
            day_cutoff_utc=_day_index_to_datetime(
                today_day_index + 1, boundary_hour, timezone_name=timezone_name,
            ),
            admin_mode=admin_mode,
            # D6-04: all Cards of a Note share one NOTE state.
            count_by_note=bool(current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False)),
            owned_by_any_user=admin_mode,
            include_note_types=False,
        )

        def rebuild_counts(node: dict[str, Any]) -> dict[str, int]:
            counts = dict(
                direct_counts.get(
                    int(node["id"]),
                    {"total": 0, "new": 0, "learn": 0, "due": 0},
                )
            )
            for child in node.get("children", []):
                child_counts = rebuild_counts(child)
                for key in ("total", "new", "learn", "due"):
                    counts[key] += int(child_counts[key])
            node["counts"] = counts
            return counts

        for root in tree:
            rebuild_counts(root)
    return {"tree": tree}


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
                    "note_type_name": node.get("note_type_name"),
                    "note_type_ids": node.get("note_type_ids", []),
                    "note_type_names": node.get("note_type_names", []),
                    "has_mixed_note_types": bool(node.get("has_mixed_note_types")),
                    "counts": node.get("counts", {}),
                }
            )
            _flatten(node.get("children", []))

    _flatten(tree)
    # Every caller reads only the flat list; the nested form stays on /decks/tree.
    return {"decks": flat_items}


def _authority_progress_view(authority_read: StudyAuthorityCardRead) -> SimpleNamespace:
    availability = authority_read.availability
    return SimpleNamespace(
        queue=availability.normalized_queue,
        due_at=availability.due_at,
        due_day=availability.due_day,
    )


def _load_mode_aware_browse_progress(
    *,
    user_id: int,
    timezone_name: str,
    card_obj: Card,
    now_utc: datetime,
    admin_mode: bool = False,
):
    with _study_authority_conflict():
        lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
        if card_obj.note is None:
            raise StudyAuthorityReadError(
                "NOTE_BROWSE_CONTEXT_UNAVAILABLE",
                "NOTE authority Browse cannot read a Card without a Note.",
            )
        options_deck_id = card_obj.note.deck_id
        if int(card_obj.note.user_id) != int(user_id) and not admin_mode:
            # Only a visible logical-overlay source Card may be read.
            clone_scope = _visible_clone_scope(user_id=user_id, card_obj=card_obj)
            if clone_scope is None:
                raise StudyAuthorityReadError(
                    "NOTE_BROWSE_CONTEXT_UNAVAILABLE",
                    "NOTE authority Browse cannot read a foreign source Card.",
                )
            options_deck_id = _clone_local_deck_id(clone_scope, card_obj.note)
        authority_read = load_study_authority_card_read(
            db.session,
            learner_user_id=user_id,
            card=card_obj,
            now_utc=now_utc,
            timezone_name=timezone_name,
            deck_options=resolve_deck_options(
                user_id=user_id,
                deck_id=options_deck_id,
            ),
        )
        return _authority_progress_view(authority_read)


def _join_note_availability(query, *, learner_user_id: int, note_id_column=None):
    """Outer-join each Card's canonical Note availability (ADR P10 §2.7).

    Integrity is checked on the returned page only (``page_window_integrity``).
    """

    subject = aliased(StudyProgressSubject)
    query = query.outerjoin(subject, db.and_(
        subject.learner_user_id == int(learner_user_id),
        subject.logical_note_key == cast(Card.note_id if note_id_column is None else note_id_column, LargeBinary),
    ))
    return query, SimpleNamespace(
        id=case((subject.semantic_state_hash.isnot(None), subject.id), else_=None),
        queue=subject.normalized_queue,
        due_at=subject.due_at,
        due_day=subject.due_day,
        is_suspended=subject.is_suspended,
        is_buried=subject.is_buried,
        buried_until_day=subject.buried_until_day,
    )


def _build_browse_query(*, user_id: int, admin_mode: bool, timezone_name: str, query_args, notes_only: bool = False, scope_only: bool = False, scope_note=None, scoped_deck_ids=None):
    """Share visibility and effective-value filters; Note reads never expand applications."""
    from app.services import flashcards_share as share_ctrl

    deck_id_raw = str(query_args.get("deck_id") or "").strip()
    include_subdecks_raw = str(query_args.get("include_subdecks") or "1").strip().lower()
    include_subdecks = include_subdecks_raw not in {"0", "false", "no"}
    include_all_templates_raw = str(
        query_args.get("all_templates")
        or query_args.get("include_all_templates")
        or ""
    ).strip().lower()
    include_all_templates = include_all_templates_raw in {"1", "true", "yes"}
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
    # The fence is held before any scope or Note-state read below.
    # load_study_authority_card_reads takes it again for its own contract.
    with _study_authority_conflict():
        lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )

    def _empty_result():
        return None

    selected_deck_id = None
    if deck_id_raw:
        try:
            selected_deck_id = int(deck_id_raw)
        except (TypeError, ValueError) as exc:
            raise BrowseApiError("Invalid deck_id") from exc
    requested_roots = None
    if scoped_deck_ids is not None:
        try:
            raw_roots = list(scoped_deck_ids)
            if not raw_roots or len(raw_roots) > 50 or any(
                isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0 for value in raw_roots
            ):
                raise ValueError
            requested_roots = set(map(int, raw_roots))
        except (TypeError, ValueError) as exc:
            raise BrowseApiError("Invalid scoped_deck_ids", field="deck_ids") from exc
    selection_roots = requested_roots if requested_roots is not None else (
        {selected_deck_id} if selected_deck_id is not None else None)
    expand_selection = True if requested_roots is not None else include_subdecks
    scoped_decks = None
    if notes_only and selection_roots is not None:
        from app.repositories.browse_note_repository import selected_browse_decks
        scoped_decks = selected_browse_decks(user_id=user_id, admin_mode=admin_mode,
            deck_ids=selection_roots, include_subdecks=expand_selection)
    if scoped_decks is None:
        scoped_decks = vocabulary_ctrl.collect_accessible_browse_decks(
            user_id=user_id, admin_mode=admin_mode)
    deck_by_id = {deck.id: deck for deck in scoped_decks}
    deck_lookup = {deck.id: deck.name for deck in scoped_decks}
    children_by_parent = vocabulary_ctrl.deck_children_map(scoped_decks)
    scoped_ids = set(deck_by_id)
    selected_ids: set[int] | None = None
    if selection_roots is not None:
        if not selection_roots.issubset(scoped_ids):
            raise BrowseApiError("Deck not found", status=404)
        if expand_selection:
            selected_ids = {deck_id for root in selection_roots
                for deck_id in vocabulary_ctrl.collect_subtree_ids(root, children_by_parent)}
        else:
            selected_ids = set(selection_roots)
        if requested_roots is not None:
            # Sidebar batches expose only the requested union, even when a
            # mixed learner subtree needed the full visibility resolver.
            deck_by_id = {deck_id: deck for deck_id, deck in deck_by_id.items() if deck_id in selected_ids}
            deck_lookup = {deck_id: deck.name for deck_id, deck in deck_by_id.items()}
            scoped_ids = set(deck_by_id)

    query = Note.query if notes_only else Card.query.join(Note, Card.note_id == Note.id)
    # Status and due order come from the learner's Note row (verified
    # on the returned page), NULL for pristine Notes.
    query, progress_alias = _join_note_availability(query, learner_user_id=user_id, note_id_column=Note.id if notes_only else Card.note_id)
    clone_scopes = []
    clone_scope_conditions: list[tuple[Any, Any]] = []
    owned_visibility_condition = None
    source_to_local_deck_id: dict[int, int] = {}
    if admin_mode:
        if selected_ids:
            query = query.filter(Note.deck_id.in_(selected_ids))
        elif scoped_ids:
            query = query.filter(Note.deck_id.in_(scoped_ids))
        else:
            return _empty_result()
    else:
        local_scope_ids = set(selected_ids or scoped_ids)

        if requested_roots is not None:
            from app.repositories.browse_note_repository import installed_batch_scope_roots
            scope_candidates = installed_batch_scope_roots(user_id=user_id, local_deck_ids=local_scope_ids)
        elif selected_ids is not None:
            if notes_only:
                from app.repositories.browse_note_repository import installed_scope_candidates
                scope_candidates = installed_scope_candidates(user_id=user_id, local_deck_ids=local_scope_ids)
            else:
                scope_candidates = sorted(local_scope_ids)
        elif notes_only and scope_note is not None:
            from app.repositories.browse_note_repository import clone_scope_roots_for_note
            scope_candidates = clone_scope_roots_for_note(user_id=user_id, source_deck_id=scope_note.deck_id)
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
            if requested_roots is None and selected_ids is not None and local_scope_deck_id in covered_local_ids:
                continue
            clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
                user_id=user_id,
                local_deck_id=int(local_scope_deck_id),
            )
            if clone_scope is None or not clone_scope.source_deck_ids:
                continue
            if requested_roots is not None:
                from dataclasses import replace
                mapping = {int(source): int(local) for source, local in
                    (clone_scope.source_to_local_deck_id or {}).items() if int(local) in local_scope_ids}
                clone_scope = replace(clone_scope,
                    local_deck_ids=[deck_id for deck_id in clone_scope.local_deck_ids if deck_id in local_scope_ids],
                    source_deck_ids=[deck_id for deck_id in clone_scope.source_deck_ids if deck_id in mapping],
                    source_to_local_deck_id=mapping)
                if not clone_scope.source_deck_ids:
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
                        *([] if notes_only else [Card.created_at <= clone_scope.base_snapshot_at]),
                    ]
                )
            scope_condition = db.and_(*scope_filters)
            visibility_filters.append(scope_condition)
            clone_scope_conditions.append((clone_scope, scope_condition))

        if not visibility_filters:
            return _empty_result()
        query = query.filter(db.or_(*visibility_filters))
        _with_clone_deck_names(deck_lookup, source_to_local_deck_id)

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
            field_specs = []
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
                from app.services.field_value_runtime_service import added_field_identity_key
                field_identity_key = added_field_identity_key(install.id, field_id) if is_added_field else field_id
                field_specs.append({'source_field_id': source_field_id,
                    'checkpoint_name': checkpoint_field_name, 'identity_key': field_identity_key})
                if notes_only and keyword and sort_by != 'word':
                    continue
                field_expression = (
                    browse_card_repository.clone_effective_field_text_expression(
                        deck_install_id=str(install.id),
                        deck_item_id=deck_item_id,
                        target_release_sequence=target_sequence,
                        source_field_def_id=source_field_id,
                        checkpoint_field_name=checkpoint_field_name,
                        field_identity_key=field_identity_key,
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
                    "field_specs": field_specs,
                    "install": install,
                    "deck_item_id": deck_item_id,
                    "target_sequence": target_sequence,
                    "word": browse_card_repository.first_non_empty_text_expression(
                        word_field_expressions
                    ),
                }
            )

    if keyword:
        keyword_like = f"%{escape_like_pattern(keyword.lower())}%"
        if admin_mode:
            query = query.filter(
                note_values_search_condition(keyword_like=keyword_like)
            )
        else:
            from sqlalchemy import select, union
            from app.repositories.browse_search_repository import clone_note_search_ids
            effective_search_conditions = []
            search_branches = []
            if owned_visibility_condition is not None:
                owned_search = db.and_(
                        owned_visibility_condition,
                        note_values_search_condition(keyword_like=keyword_like),
                    )
                effective_search_conditions.append(owned_search)
                if notes_only:
                    search_branches.append(select(Note.id.label('note_id')).where(owned_search))
            for projection in clone_projections:
                if notes_only and projection.get('field_specs'):
                    search_branches.append(clone_note_search_ids(
                        scope_condition=projection['condition'], field_specs=projection['field_specs'],
                        deck_install_id=projection['install'].id, deck_item_id=projection['deck_item_id'],
                        target_sequence=projection['target_sequence'], keyword_like=keyword_like))
                    continue
                effective_search_conditions.append(
                    db.and_(
                        projection["condition"],
                        browse_card_repository.effective_fields_search_condition(
                            projection["all_fields"],
                            keyword_like=keyword_like,
                        ),
                    )
                )
            if notes_only and search_branches:
                matches = (union(*search_branches) if len(search_branches) > 1 else search_branches[0]).subquery('browse_search_matches')
                query = query.join(matches, matches.c.note_id == Note.id)
            else:
                query = query.filter(db.or_(*effective_search_conditions) if effective_search_conditions else false())
    if tag:
        tag_like = f"%{escape_like_pattern(tag.lower())}%"
        query = query.filter(
            func.lower(db.cast(Note.tags, db.Text)).like(tag_like, escape="\\")
        )

    now = _utcnow()
    # One settings read serves the due filter and every deck's options.
    runtime_settings = resolve_scheduler_runtime_settings(user_id=user_id)
    # Consolidated availability is already a normalized, writer-owned enum.
    normalized_progress_queue = progress_alias.queue
    eligible = active_progress_expr(progress_alias)
    if status == NEW_QUEUE:
        eligible = db.and_(eligible,
            db.or_(
                progress_alias.id.is_(None),
                normalized_progress_queue == NEW_QUEUE,
            )
        )
    elif status == "learn":
        eligible = db.and_(eligible,
            normalized_progress_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE])
        )
    elif status in {"due", REVIEW_QUEUE}:
        eligible = db.and_(eligible,
            normalized_progress_queue == REVIEW_QUEUE,
            review_due_expr(progress_alias, now=now, timezone_name=timezone_name,
                            day_boundary_hour_local=int(runtime_settings.day_boundary_hour_local)),
        )

    if not scope_only:
        query = query.filter(eligible)
    return SimpleNamespace(
        include_all_templates=include_all_templates,
        keyword=keyword,
        sort_by=sort_by, sort_dir=sort_dir,
        query=query,
        progress_alias=progress_alias,
        source_to_local_deck_id=source_to_local_deck_id,
        deck_lookup=deck_lookup,
        clone_projections=clone_projections,
        owned_visibility_condition=owned_visibility_condition,
        normalized_progress_queue=normalized_progress_queue,
        page=page,
        per_page=per_page,
        now=now,
        runtime_settings=runtime_settings,
        deck_by_id=deck_by_id,
        clone_scopes=clone_scopes,
        clone_scope_conditions=clone_scope_conditions,
    )


def list_browse_cards(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str,
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    """Compatibility presentation list for existing Card-based consumers."""
    context = _build_browse_query(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args=query_args)
    if context is None:
        return {"items": [], "page": max(1, int(query_args.get("page") or 1)),
                "per_page": max(1, min(500, int(query_args.get("per_page") or 100))),
                "total": 0, "pages": 0, "has_next": False}
    include_all_templates = context.include_all_templates
    sort_by, sort_dir = context.sort_by, context.sort_dir
    query = context.query
    progress_alias = context.progress_alias
    source_to_local_deck_id = context.source_to_local_deck_id
    deck_lookup = context.deck_lookup
    clone_projections = context.clone_projections
    owned_visibility_condition = context.owned_visibility_condition
    normalized_progress_queue = context.normalized_progress_queue
    page = context.page
    per_page = context.per_page
    now = context.now
    runtime_settings = context.runtime_settings
    deck_by_id = context.deck_by_id
    clone_scopes = context.clone_scopes
    if not include_all_templates:
        query = browse_card_repository.one_visible_card_per_note(query)
    total = browse_card_repository.count_distinct_cards(query)
    query = query.options(*browse_card_repository.browse_page_load_options())

    if sort_by == "deck":
        query = browse_card_repository.order_browse_cards_by_deck(
            query,
            learner_user_id=user_id,
            sort_dir=sort_dir,
            source_to_local_deck_id=source_to_local_deck_id,
            deck_name_lookup=deck_lookup,
        )
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

    query = query.order_by(Card.id.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False, count=False)
    pagination.total = total
    if pagination.items:
        page_card_ids = [card_obj.id for card_obj in pagination.items]
        worst = browse_card_repository.page_window_integrity(
            db.session,
            learner_user_id=user_id,
            card_ids=page_card_ids,
            note_ids=[card_obj.note_id for card_obj in pagination.items],
        )
        violation = note_analytics_read_repository.violation_error(worst)
        if violation is not None:
            db.session.rollback()
            raise BrowseApiError(violation[1], status=409, code=violation[0])
    options_by_deck_id: dict[int | None, Any] = {}
    deck_options_by_card_id: dict[str, Any] = {}
    for card_obj in pagination.items:
        note_obj = card_obj.note
        # Overlay source Cards use the learner's mapped local deck options.
        effective_deck_id = int(note_obj.deck_id) if note_obj.deck_id is not None else None
        if effective_deck_id is not None and note_obj.user_id != user_id:
            effective_deck_id = source_to_local_deck_id.get(effective_deck_id, effective_deck_id)
        if effective_deck_id not in options_by_deck_id:
            options_by_deck_id[effective_deck_id] = resolve_deck_options(
                user_id=user_id,
                deck_id=effective_deck_id,
                deck_obj=deck_by_id.get(effective_deck_id),
                runtime_settings=runtime_settings,
            )
        deck_options_by_card_id[str(card_obj.id)] = options_by_deck_id[effective_deck_id]
    with _study_authority_conflict():
        authority_reads = load_study_authority_card_reads(
            db.session,
            learner_user_id=user_id,
            cards=tuple(pagination.items),
            now_utc=now,
            timezone_name=timezone_name,
            deck_options_by_card_id=deck_options_by_card_id,
        )
    clone_scope_by_card_id: dict[str, Any] = {}
    release_note_ids: dict[str, set[str]] = {}
    release_install_by_id: dict[str, Any] = {}
    clone_install_ids: set[str] = set()
    clone_source_note_ids: set[str] = set()
    if not admin_mode and clone_scopes:
        scope_source_deck_ids = [(scope, set(scope.source_deck_ids)) for scope in clone_scopes]
        for card_obj in pagination.items:
            note_obj = card_obj.note
            if note_obj is None or note_obj.user_id == user_id or note_obj.deck_id is None:
                continue
            matching_scope = next(
                (
                    scope
                    for scope, source_deck_ids in scope_source_deck_ids
                    if int(note_obj.deck_id) in source_deck_ids
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
    schema_views: dict[tuple[str, str], Any] = {}
    for card_obj in pagination.items:
        progress_view = _authority_progress_view(authority_reads[str(card_obj.id)])
        clone_scope = clone_scope_by_card_id.get(str(card_obj.id))
        if clone_scope is None:
            rows.append(vocabulary_ctrl.build_browse_row(
                card_obj,
                deck_lookup,
                now,
                progress_obj=progress_view,
                timezone_name=timezone_name,
            ))
            continue
        release_id = str(clone_scope.install.applied_release_id or "")
        override_key = (str(clone_scope.install.id), str(card_obj.note.id))
        overlay = _clone_overlay_fields(
            card_obj=card_obj,
            clone_scope=clone_scope,
            base_field_values=release_values_by_note.get((release_id, str(card_obj.note.id))),
            # The batch above holds every override of this page; none means none.
            note_override_rows=batch_overrides.get(override_key, []),
            schema_views=schema_views,
        )
        # The overlay supplies the displayed values, so the source Note's own
        # (owner working) values are never decoded for this row.
        row_payload = vocabulary_ctrl.build_browse_row(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress_view,
            timezone_name=timezone_name,
            display_triplet=overlay.display_triplet,
        )
        _apply_clone_card_fields(row_payload, overlay=overlay, deck_lookup=deck_lookup)
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
    with _study_authority_conflict():
        lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
    card_obj = browse_card_repository.load_card_for_browse_update(card_id=card_id)
    if not card_obj:
        raise BrowseApiError("Card not found", status=404)

    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    clone_scope = None
    if not admin_mode and card_obj.note and card_obj.note.user_id != user_id:
        clone_scope = _visible_clone_scope(user_id=user_id, card_obj=card_obj)
        if clone_scope is None:
            raise BrowseApiError("Card not found", status=404)
        _with_clone_deck_names(deck_lookup, clone_scope.source_to_local_deck_id)

    # Admin-wide detail reads the admin's own state on any Card.
    if not admin_mode and clone_scope is None and card_obj.note.user_id != user_id:
        raise BrowseApiError(
            "NOTE authority Browse detail is unavailable for this Card context.",
            status=409,
            code="NOTE_BROWSE_CONTEXT_UNAVAILABLE",
        )
    options_deck_id = card_obj.note.deck_id
    if clone_scope is not None:
        options_deck_id = _clone_local_deck_id(clone_scope, card_obj.note)
    with _study_authority_conflict():
        authority_read = load_study_authority_card_read(
            db.session,
            learner_user_id=user_id,
            card=card_obj,
            now_utc=_utcnow(),
            timezone_name=timezone_name,
            deck_options=resolve_deck_options(
                user_id=user_id,
                deck_id=options_deck_id,
            ),
        )
    progress = _authority_progress_view(authority_read)
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


def _stage_browse_card_removal(
    *,
    user_id: int,
    owner_user_ids,
    card_ids,
    deleted_note_ids,
    source_path: str,
    operation_key: str,
) -> None:
    """Fence every affected learner and retire their Card progress atomically.

    NOTE learners keep one canonical Note state across a partial sibling
    removal and are tombstoned when their Note loses its last Card.
    """
    from app.services import study_content_delete_service as content_delete

    actor_user_ids = {int(user_id), *(int(value) for value in owner_user_ids if value)}
    try:
        authority_routes = content_delete.lock_content_delete_routes(
            db.session,
            actor_user_ids=actor_user_ids,
            card_ids=card_ids,
            deleted_note_ids=deleted_note_ids,
        )
        lifecycle_plan = content_delete.prepare_content_delete(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            note_ids=deleted_note_ids,
            cancel_legacy_sessions=False,
        )
        content_delete.verify_content_delete_scope(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            deleted_note_ids=deleted_note_ids,
        )
        content_delete.finalize_content_delete(
            lifecycle_plan,
            source_path=source_path,
            operation_key=operation_key,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise BrowseApiError(str(exc), status=409, code=exc.code) from exc


def delete_browse_card(
    *,
    user_id: int,
    admin_mode: bool,
    card_id: str,
) -> dict[str, bool]:
    clean_card_id = str(card_id).strip()
    query = Card.query.join(Note, Card.note_id == Note.id)
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    card_obj = get_card(db.session, clean_card_id, query=query)
    if not card_obj:
        existing_card = get_card(db.session, clean_card_id)
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

    note_id = str(card_obj.note_id)
    _require_whole_notes({note_id: {str(card_obj.id)}})
    _stage_browse_card_removal(
        user_id=user_id,
        owner_user_ids=(card_obj.note.user_id,),
        card_ids=(str(card_obj.id),),
        deleted_note_ids=(note_id,),
        source_path="browse.card_delete",
        operation_key=f"browse-card-delete:{card_obj.id}",
    )
    _delete_browse_notes([note_id])
    db.session.commit()
    return {"success": True}


def _require_whole_notes(selected_by_note: dict[str, set[str]]) -> None:
    """A Card is a Note shown through one occurrence (ADR P11): it is removed
    with its Note, never alone. Selecting only some of a Note's Cards is
    refused; retire the Template on the NoteType to stop presenting it."""
    current: dict[str, set[str]] = {note_id: set() for note_id in selected_by_note}
    for card in Card.query.filter(Card.note_id.in_(sorted(selected_by_note))).all():
        current[str(card.note_id)].add(str(card.id))
    if any(selected != current.get(note_id, set()) for note_id, selected in selected_by_note.items()):
        raise BrowseApiError(
            "Thẻ này là một mặt của note có nhiều template. Hãy xóa cả note, hoặc gỡ template khỏi note type.",
            status=409,
            code="CARD_PARTIAL_DELETE_UNSUPPORTED",
        )


def _delete_browse_notes(note_ids) -> None:
    from app.services import deck_working_tree_service

    for note_id in sorted(set(note_ids)):
        note_obj = db.session.get(Note, note_id)
        if note_obj is None:
            continue
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note_obj,
                    "field_names": (note_obj.field_values or {}).keys(),
                    "operation": "remove",
                }
            ],
        )
        forget_card_identities(db.session, (note_id,))
        db.session.delete(note_obj)


def delete_browse_notes_batch(
    *, user_id: int, admin_mode: bool, note_ids: list[str],
) -> dict[str, Any]:
    """Delete selected Notes and all their presentations, preserving Templates.

    The card-delete compatibility APIs retain their explicit partial-selection
    guard. Note deletion is a separate intent and uses the same learner fences,
    lifecycle events and session cancellation as other content deletion paths.
    """
    from app.services import deck_working_tree_service

    ids = sorted(set(note_ids))
    if not ids:
        return {"success": True, "deleted_count": 0}
    notes = Note.query.filter(Note.id.in_(ids)).order_by(Note.id).all()
    if len(notes) != len(ids):
        raise BrowseApiError("Note not found", status=404)
    if not admin_mode and any(note.user_id != user_id for note in notes):
        raise BrowseApiError(
            "Không thể xóa note thuộc bộ bài gốc được chia sẻ/clone.",
            status=403, code="SHARED_SOURCE_NOTE_PROTECTED",
        )
    if any(deck_working_tree_service.note_has_shared_release_dependents(note) for note in notes):
        raise BrowseApiError(
            "Published shared notes cannot be hard-deleted because learner history must be preserved.",
            status=409, code="SHARED_ENTITY_RETIRE_REQUIRED",
        )
    _stage_browse_card_removal(
        user_id=user_id,
        owner_user_ids={note.user_id for note in notes},
        card_ids=(),
        deleted_note_ids=ids,
        source_path="browse.note_delete",
        operation_key="browse-note-delete:"
        + hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
    )
    _delete_browse_notes(ids)
    db.session.commit()
    return {"success": True, "deleted_count": len(ids)}


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

    query = Card.query.join(Note, Card.note_id == Note.id)
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)

    cards_to_delete = list({card.id: card for card in load_cards(db.session, clean_card_ids, query=query).values()}.values())
    if not cards_to_delete:
        existing_cards = load_cards(db.session, clean_card_ids)
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

    deleted_count = len(cards_to_delete)
    selected_by_note: dict[str, set[str]] = {}
    for card_obj in cards_to_delete:
        selected_by_note.setdefault(str(card_obj.note_id), set()).add(str(card_obj.id))
    _require_whole_notes(selected_by_note)
    deleted_card_ids = {str(card_obj.id) for card_obj in cards_to_delete}
    _stage_browse_card_removal(
        user_id=user_id,
        owner_user_ids={card_obj.note.user_id for card_obj in cards_to_delete if card_obj.note},
        card_ids=sorted(deleted_card_ids),
        deleted_note_ids=sorted(selected_by_note),
        source_path="browse.card_batch_delete",
        operation_key="browse-card-batch-delete:"
        + hashlib.sha256("\n".join(sorted(deleted_card_ids)).encode("utf-8")).hexdigest(),
    )
    _delete_browse_notes(selected_by_note)

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
        from app.services.note_value_precondition_service import check_note_write_preconditions
        check_note_write_preconditions(note_obj, payload)
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
    include_response: bool = True,
) -> dict[str, Any]:
    from app.services import flashcards_share as share_ctrl

    mapped_local_deck_id = _clone_local_deck_id(clone_scope, note_obj)
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

    if not include_response:
        return {"success": True}
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
        deck_lookup=_with_clone_deck_names(
            browse_card_repository.deck_lookup_for_browse(user_id=user_id, admin_mode=False),
            clone_scope.source_to_local_deck_id,
        ),
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
    include_response: bool = True,
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
        from app.services import media_staging_service
        next_values = media_staging_service.commit_all_staged_urls_in_field_values(
            user_id=user_id,
            note_id=note_obj.id,
            field_values=next_values,
        )
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

    if not include_response:
        return {"success": True}
    now = _utcnow()
    deck_lookup = browse_card_repository.deck_lookup_for_browse(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    progress = _load_mode_aware_browse_progress(
        user_id=user_id,
        timezone_name=timezone_name,
        card_obj=card_obj,
        now_utc=now,
        admin_mode=admin_mode,
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
    from app.repositories.browse_note_repository import BrowseNoteReference, detail_deck_lookup
    if isinstance(card_obj, BrowseNoteReference):
        deck_lookup = detail_deck_lookup(reference=card_obj)
    else:
        deck_lookup = browse_card_repository.deck_lookup_for_browse(user_id=user_id, admin_mode=admin_mode)
    now = _utcnow()
    progress = _load_mode_aware_browse_progress(
        user_id=user_id,
        timezone_name=timezone_name,
        card_obj=card_obj,
        now_utc=now,
        admin_mode=admin_mode,
    )
    return vocabulary_ctrl.build_browse_card_detail(
        card_obj,
        deck_lookup,
        now,
        progress_obj=progress,
        timezone_name=timezone_name,
    )


def _collect_note_media_refs(note_obj):
    from app.services.media_field_codec import build_media_reference_lookup

    if note_obj is None:
        return {}
    return build_media_reference_lookup(note_obj.media_assets or [])


def _normalize_tags_payload(raw_tags: object) -> list[str]:
    if isinstance(raw_tags, list):
        return [str(item).strip() for item in raw_tags if str(item).strip()]
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def _clone_overlay_fields(
    *,
    card_obj,
    clone_scope,
    base_field_values: dict[str, Any] | None = None,
    note_override_rows: list[Any] | None = None,
    schema_views: dict[tuple[str, str], Any] | None = None,
) -> SimpleNamespace:
    """A source Note's fields as this learner's install presents them.

    Values come from the install's pinned release (or snapshot) plus its
    overlay; the source Note is never mutated. ``schema_views`` memoizes the
    install schema across the rows of one page. The Note must have a deck.
    """
    from app.services import flashcards_share as share_ctrl

    note_obj = card_obj.note
    source_note_type_id = (clone_scope.install.source_note_type_id or note_obj.note_type_id or "").strip()
    if source_note_type_id:
        schema_key = (str(clone_scope.install.id), source_note_type_id)
        schema_view = (schema_views or {}).get(schema_key)
        if schema_view is None:
            schema_view = share_ctrl.build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            if schema_views is not None:
                schema_views[schema_key] = schema_view
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
        str(key).strip(): stored_field_value(value)
        for key, value in dict(overlay_field_values or {}).items()
        if str(key).strip()
    }
    ordered_defs = sorted(
        overlay_field_defs or [],
        key=lambda item: (int(getattr(item, "position", 0) or 0), str(getattr(item, "name", "")).lower()),
    )
    proxy_note = SimpleNamespace(
        field_values=normalized_values,
        note_type=SimpleNamespace(field_defs=ordered_defs),
    )
    return SimpleNamespace(
        field_defs=overlay_field_defs,
        ordered_defs=ordered_defs,
        values=normalized_values,
        display_triplet=vocabulary_ctrl.note_display_triplet(proxy_note),
        local_deck_id=_clone_local_deck_id(clone_scope, note_obj),
    )


def _apply_clone_card_fields(card_payload: dict[str, Any], *, overlay, deck_lookup: dict[int, str]) -> None:
    card_payload["word"] = overlay.display_triplet.get("word", "")
    card_payload["reading"] = overlay.display_triplet.get("reading", "")
    card_payload["meaning"] = overlay.display_triplet.get("meaning", "")
    if overlay.local_deck_id is not None:
        card_payload["deck_id"] = int(overlay.local_deck_id)
    local_deck_name = deck_lookup.get(int(overlay.local_deck_id or 0), "")
    if local_deck_name:
        card_payload["deck_name"] = local_deck_name


def _apply_clone_overlay_to_browse_payload(
    *,
    payload: dict[str, Any],
    card_obj,
    clone_scope,
    deck_lookup: dict[int, str],
) -> dict[str, Any]:
    note_obj = card_obj.note
    if note_obj is None or note_obj.deck_id is None:
        return payload

    overlay = _clone_overlay_fields(card_obj=card_obj, clone_scope=clone_scope)
    overlay_field_defs = overlay.field_defs
    normalized_values = overlay.values
    ordered_defs = overlay.ordered_defs
    local_deck_id = overlay.local_deck_id
    local_deck_name = deck_lookup.get(int(local_deck_id or 0), "")

    card_payload = payload.get("card")
    if isinstance(card_payload, dict):
        _apply_clone_card_fields(card_payload, overlay=overlay, deck_lookup=deck_lookup)

    note_payload = payload.get("note")
    if isinstance(note_payload, dict):
        note_payload["field_values"] = normalized_values
        note_payload.pop("content_revision", None)
        note_payload.pop("field_schema_revision", None)
        note_payload["deck_install_id"] = clone_scope.install.id
        note_payload["overlay_revision"] = int(clone_scope.install.overlay_revision or 0)
        if local_deck_id is not None:
            note_payload["deck_id"] = int(local_deck_id)
        note_payload["deck_name"] = local_deck_name

    media_payloads = payload.get("media_assets") or []
    if media_payloads:
        from app.services.media_field_codec import media_field_label_for_schema

        assets_by_id = {str(asset.id): asset for asset in note_obj.media_assets or []}
        for asset_payload in media_payloads:
            asset = assets_by_id.get(str(asset_payload.get("id")))
            if asset is not None:
                asset_payload["field_name"] = media_field_label_for_schema(asset, overlay_field_defs)

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
                "id": str(getattr(field_def, "id", "") or ""),
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
