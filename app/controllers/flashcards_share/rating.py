"""Extracted share submodule."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import OperationalError

from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import *

from app.controllers import flashcards_marketplace_controller as marketplace_ctrl
from app.controllers.deck_controller import collect_ancestor_ids, collect_subtree_ids

# We will let them import classes/constants from core
from .core import *
from .clone_install import (
    CloneSchemaView,
    build_clone_schema_view,
    deck_installs_covering_deck,
    resolve_clone_scope_for_local_deck,
    upsert_clone_overlay,
    _build_note_override_payload_for_cutover,
    _build_schema_overlay_payload_for_cutover,
    _ensure_clone_map_rows_for_cutover,
)

def touch_note_type_install_usage(
    *,
    user_id: int,
    installed_note_type_id: str,
    activity_at: datetime | None = None,
) -> None:
    install = NoteTypeInstall.query.filter_by(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    ).first()
    if not install:
        return
    now = activity_at or datetime.utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now

def note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    result = (
        db.session.query(db.func.coalesce(db.func.sum(CardProgress.reps), 0))
        .select_from(CardProgress)
        .join(Card, CardProgress.card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            Note.note_type_id == installed_note_type_id,
        )
        .scalar()
    )
    return int(result or 0)

def is_note_type_install_active(
    install: NoteTypeInstall,
    *,
    now: datetime,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if not install.installed_note_type_id:
        return False
    note_count = Note.query.filter_by(
        user_id=install.user_id,
        note_type_id=install.installed_note_type_id,
    ).count()
    review_reps = note_type_reps_for_user(
        user_id=install.user_id,
        installed_note_type_id=install.installed_note_type_id,
    )
    first_use = install.first_use_at
    used_days = bool(
        first_use
        and now - first_use >= timedelta(days=note_type_active_days_threshold)
    )
    return (
        note_count >= note_type_active_note_threshold
        or review_reps >= note_type_active_review_threshold
        or used_days
    )

def recompute_note_type_market_stats(
    note_type: NoteType,
    *,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> None:
    now = datetime.utcnow()
    installs = NoteTypeInstall.query.filter_by(source_note_type_id=note_type.id).all()
    note_type.install_count = len(installs)
    note_type.active_usage_count = sum(
        1
        for install in installs
        if is_note_type_install_active(
            install,
            now=now,
            note_type_active_note_threshold=note_type_active_note_threshold,
            note_type_active_review_threshold=note_type_active_review_threshold,
            note_type_active_days_threshold=note_type_active_days_threshold,
        )
    )

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(NoteTypeReview.rating), 0.0),
            db.func.count(NoteTypeReview.id),
        )
        .filter(NoteTypeReview.note_type_id == note_type.id)
        .first()
    )
    note_type.rating_avg = float(rating_avg or 0.0)
    note_type.rating_count = int(rating_count or 0)

def can_user_rate_note_type(
    note_type: NoteType,
    *,
    user_id: int,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if note_type.user_id == user_id:
        return False
    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=user_id,
    ).first()
    if not install:
        return False
    return is_note_type_install_active(
        install,
        now=datetime.utcnow(),
        note_type_active_note_threshold=note_type_active_note_threshold,
        note_type_active_review_threshold=note_type_active_review_threshold,
        note_type_active_days_threshold=note_type_active_days_threshold,
    )

def touch_deck_install_usage(
    *,
    user_id: int,
    local_deck_id: int,
    activity_at: datetime | None = None,
) -> None:
    installs = deck_installs_covering_deck(user_id=user_id, deck_id=local_deck_id)
    if not installs:
        return
    now = activity_at or datetime.utcnow()
    for install in installs:
        if install.first_use_at is None:
            install.first_use_at = now
        install.last_activity_at = now

def deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    clone_scope = resolve_clone_scope_for_local_deck(
        user_id=user_id,
        local_deck_id=local_deck_id,
    )
    if clone_scope is not None and clone_scope.source_deck_ids:
        query = (
            db.session.query(db.func.coalesce(db.func.sum(CardProgress.reps), 0))
            .select_from(CardProgress)
            .join(Card, CardProgress.card_id == Card.id)
            .join(Note, Card.note_id == Note.id)
            .filter(
                CardProgress.user_id == user_id,
                Note.deck_id.in_(clone_scope.source_deck_ids),
            )
        )
        if clone_scope.source_owner_user_id is not None:
            query = query.filter(Note.user_id == clone_scope.source_owner_user_id)
        if clone_scope.base_snapshot_at is not None:
            query = query.filter(
                Note.created_at <= clone_scope.base_snapshot_at,
                Card.created_at <= clone_scope.base_snapshot_at,
            )
        return int(query.scalar() or 0)

    subtree_deck_ids = collect_subtree_ids(local_deck_id)
    if not subtree_deck_ids:
        return 0

    flashcard_reps = (
        db.session.query(db.func.coalesce(db.func.sum(CardProgress.reps), 0))
        .select_from(CardProgress)
        .join(Card, CardProgress.card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            Note.deck_id.in_(subtree_deck_ids),
        )
        .scalar()
    ) or 0
    return int(flashcard_reps or 0)

def is_deck_install_active(
    install: DeckInstall,
    *,
    deck_active_review_threshold: int = 3,
) -> bool:
    if not install.local_deck_id:
        return False
    reps = deck_reps_for_user(user_id=install.user_id, local_deck_id=install.local_deck_id)
    return reps >= deck_active_review_threshold

def recompute_deck_item_market_stats(
    deck_item: DeckMarketplaceItem,
    *,
    deck_active_review_threshold: int = 3,
) -> None:
    installs = DeckInstall.query.filter_by(deck_item_id=deck_item.id).all()
    deck_item.install_count = len(installs)
    deck_item.active_usage_count = sum(
        1
        for install in installs
        if is_deck_install_active(
            install,
            deck_active_review_threshold=deck_active_review_threshold,
        )
    )

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(DeckReview.rating), 0.0),
            db.func.count(DeckReview.id),
        )
        .filter(DeckReview.deck_item_id == deck_item.id)
        .first()
    )
    deck_item.rating_avg = float(rating_avg or 0.0)
    deck_item.rating_count = int(rating_count or 0)

def can_user_rate_deck(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = 3,
) -> bool:
    if deck_item.owner_user_id == user_id:
        return False
    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if not install:
        return False
    return is_deck_install_active(
        install,
        deck_active_review_threshold=deck_active_review_threshold,
    )

def migrate_legacy_clone_install_to_overlay(
    install: DeckInstall,
) -> dict[str, int]:
    deck_item = DeckMarketplaceItem.query.get(install.deck_item_id)
    source_deck_id = install.source_deck_id or (deck_item.source_deck_id if deck_item else None)
    if source_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: source_deck_id is required for cutover.",
            status=409,
        )
    source_deck = Deck.query.get(source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: source deck not found ({source_deck_id}).",
            status=404,
        )
    if install.local_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: local_deck_id is required for cutover.",
            status=409,
        )
    local_deck = Deck.query.get(install.local_deck_id)
    if local_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: local deck not found ({install.local_deck_id}).",
            status=404,
        )

    source_owner_user_id = install.source_owner_user_id or (deck_item.owner_user_id if deck_item else None)
    source_note_type_id = (
        (install.source_note_type_id or "").strip()
        or ((deck_item.source_note_type_id or "").strip() if deck_item else "")
    )
    snapshot_at = install.base_snapshot_at or install.installed_at

    map_rows = _ensure_clone_map_rows_for_cutover(
        install=install,
        source_root_deck_id=source_deck.id,
        local_root_deck_id=local_deck.id,
    )
    source_to_local = {
        int(row.source_deck_id): int(row.local_deck_id)
        for row in map_rows
        if row.source_deck_id is not None and row.local_deck_id is not None
    }
    if not source_to_local:
        raise ShareControllerError(
            f"Install {install.id}: source/local deck map is empty for cutover.",
            status=409,
        )

    pairs = _pair_legacy_local_source_notes_for_cutover(
        install=install,
        source_to_local_deck_id=source_to_local,
        source_owner_user_id=source_owner_user_id,
        source_note_type_id=source_note_type_id or None,
        snapshot_at=snapshot_at,
    )

    local_note_type_ids = sorted(
        {
            str(local_note.note_type_id).strip()
            for local_note, _source_note in pairs
            if (local_note.note_type_id or "").strip()
        }
    )
    local_note_type_id = local_note_type_ids[0] if len(local_note_type_ids) == 1 else None
    if len(local_note_type_ids) > 1:
        raise ShareControllerError(
            f"Install {install.id}: local legacy clone has multiple note types; cutover is ambiguous.",
            status=409,
        )

    if not source_note_type_id:
        source_note_type_ids = sorted(
            {
                str(source_note.note_type_id).strip()
                for _local_note, source_note in pairs
                if (source_note.note_type_id or "").strip()
            }
        )
        if len(source_note_type_ids) == 1:
            source_note_type_id = source_note_type_ids[0]
        elif len(source_note_type_ids) > 1:
            raise ShareControllerError(
                f"Install {install.id}: source clone scope has multiple note types; source_note_type_id is required.",
                status=409,
            )

    install.clone_mode = "logical_overlay"
    DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    db.session.flush()

    if source_note_type_id:
        schema_payload = _build_schema_overlay_payload_for_cutover(
            source_note_type_id=source_note_type_id,
            local_note_type_id=local_note_type_id,
        )
        if schema_payload:
            _counters, validation_error = upsert_clone_overlay(
                deck_install=install,
                payload=schema_payload,
            )
            if validation_error:
                raise ShareControllerError(
                    f"Install {install.id}: schema cutover failed: {validation_error}",
                    status=409,
                )
    elif local_note_type_id:
        raise ShareControllerError(
            f"Install {install.id}: source_note_type_id is required for schema cutover.",
            status=409,
        )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    else:
        schema_view = CloneSchemaView(field_defs=[], removed_field_names=set(), renamed_field_names={})

    note_override_payload: list[dict[str, Any]] = []
    progress_migrated = 0
    local_note_ids: list[str] = []
    template_map_cache: dict[str, dict[str, str]] = {}

    for local_note, source_note in pairs:
        local_note_ids.append(local_note.id)
        note_override_payload.extend(
            _build_note_override_payload_for_cutover(
                install=install,
                source_note=source_note,
                local_note=local_note,
                schema_view=schema_view,
            )
        )

        local_note_type_key = str(local_note.note_type_id or "").strip()
        source_note_type_key = str(source_note.note_type_id or "").strip()
        template_key = f"{local_note_type_key}->{source_note_type_key}"
        template_map = template_map_cache.get(template_key)
        if template_map is None:
            local_templates = (
                Template.query.filter_by(note_type_id=local_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            source_templates = (
                Template.query.filter_by(note_type_id=source_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            if len(local_templates) != len(source_templates):
                raise ShareControllerError(
                    (
                        f"Install {install.id}: template count mismatch for note type pair "
                        f"({local_note_type_key} -> {source_note_type_key})."
                    ),
                    status=409,
                )
            template_map = {
                str(local_templates[idx].id): str(source_templates[idx].id)
                for idx in range(len(local_templates))
            }
            template_map_cache[template_key] = template_map

        source_cards_by_template = {
            str(card.template_id): card
            for card in Card.query.filter_by(note_id=source_note.id).all()
        }
        local_cards = Card.query.filter_by(note_id=local_note.id).all()
        for local_card in local_cards:
            source_template_id = template_map.get(str(local_card.template_id))
            if not source_template_id:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: cannot map local template_id={local_card.template_id} "
                        f"for local_note_id={local_note.id}."
                    ),
                    status=409,
                )
            source_card = source_cards_by_template.get(str(source_template_id))
            if source_card is None:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: source card not found for template_id={source_template_id} "
                        f"(source_note_id={source_note.id})."
                    ),
                    status=409,
                )
            progress_migrated += _merge_card_progress_rows_for_cutover(
                user_id=install.user_id,
                local_card_id=local_card.id,
                source_card_id=source_card.id,
            )

    if note_override_payload:
        _counters, validation_error = upsert_clone_overlay(
            deck_install=install,
            payload={"note_field_overrides": note_override_payload},
        )
        if validation_error:
            raise ShareControllerError(
                f"Install {install.id}: note cutover failed: {validation_error}",
                status=409,
            )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    _assert_cutover_note_equivalence(
        install=install,
        pairs=pairs,
        schema_view=schema_view,
    )

    if local_note_ids:
        Note.query.filter(Note.id.in_(local_note_ids)).delete(synchronize_session=False)

    install.clone_mode = "logical_overlay"
    install.source_deck_id = source_deck.id
    install.source_note_type_id = source_note_type_id or None
    install.source_owner_user_id = source_owner_user_id
    install.base_snapshot_at = snapshot_at

    return {
        "deck_map_rows": len(source_to_local),
        "note_pairs": len(pairs),
        "note_overrides": len(note_override_payload),
        "progress_rows": progress_migrated,
    }
