"""Common helpers, error classes, access/rating/activity checks for deck sharing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import os
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)

from app.repositories import (
    deck_change_request_repository,
    deck_release_repository,
    flashcards_share_repository,
    marketplace_taxonomy_repository,
    study_repository,
    vocabulary_repository,
)
from app.repositories.deck_tree_query import (
    collect_ancestor_ids,
    collect_subtree_ids,
)
from app.services import (
    deck_release_service,
    deck_working_tree_service,
    marketplace_query_service,
    marketplace_taxonomy_service,
    note_sync_service,
    study_service,
)
from app.services.share.constants import (
    DECK_ACTIVE_REVIEW_THRESHOLD,
    DEFAULT_VISIBLE_PUBLISH_STATUSES,
    FIELD_TYPES,
    MARKET_ACTIVITY_POLICY_VERSION,
    NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
    NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
    PUBLISH_STATUSES_VISIBLE,
    SHARED_DECK_INSTALL_DEADLOCK_MESSAGE,
    SHARED_DECK_INSTALL_MAX_RETRIES,
    UTC,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_review import DeckReview
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomySubject,
)
from models.user import User

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)



def _audit(user_id: int | None, action: str, payload: dict | None = None) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        payload=payload or {},
    )
    db.session.add(entry)



def _stage_initial_release_if_visible(
    deck_item: DeckMarketplaceItem,
) -> str | None:
    """Pin visible legacy/new listings to an immutable initial release.

    The release service deliberately leaves transaction ownership to its
    caller. This helper is used only by listing publish/seed mutations and the
    explicit bootstrap command; learner install paths must fail fast instead.
    """

    if deck_item.current_release_id is not None:
        return None
    status = str(deck_item.publish_status or "").strip().lower()
    if status not in PUBLISH_STATUSES_VISIBLE:
        return None

    from app.services import deck_release_service

    db.session.flush()
    try:
        deck_release_service.publish_release(
            deck_item_id=str(deck_item.id),
            user_id=int(deck_item.owner_user_id),
            version_label=str(deck_item.version or "1.0.0"),
            changelog=deck_item.changelog,
            expected_current_release_id=None,
            expected_working_revision=int(deck_item.working_revision or 0),
            idempotency_key=f"initial-listing:{deck_item.id}",
        )
    except deck_release_service.DeckReleaseError as exc:
        return exc.message
    return None



def ensure_visible_deck_item_initial_release(deck_item_id: str) -> dict[str, Any]:
    """Stage an initial immutable release for one visible legacy listing.

    This is used by the rollout CLI.  The caller owns commit/rollback so large
    catalogs can be processed one listing at a time without a long transaction.
    """

    deck_item = (
        DeckMarketplaceItem.query.filter_by(id=str(deck_item_id))
        .with_for_update()
        .first()
    )
    if deck_item is None:
        return {"deck_item_id": str(deck_item_id), "status": "missing"}
    if deck_item.current_release_id is not None:
        return {
            "deck_item_id": str(deck_item.id),
            "status": "already_versioned",
            "release_id": str(deck_item.current_release_id),
        }
    if str(deck_item.publish_status or "").strip().lower() not in PUBLISH_STATUSES_VISIBLE:
        return {"deck_item_id": str(deck_item.id), "status": "not_visible"}

    error = _stage_initial_release_if_visible(deck_item)
    if error:
        return {
            "deck_item_id": str(deck_item.id),
            "status": "failed",
            "error": error,
        }
    return {
        "deck_item_id": str(deck_item.id),
        "status": "created",
        "release_id": str(deck_item.current_release_id),
    }



def _is_mysql_deadlock(exc: Exception) -> bool:
    """Best-effort deadlock detection used by retry wrappers."""
    original = getattr(exc, "orig", None)
    if original is None:
        return False
    args = getattr(original, "args", ()) or ()
    if args:
        code_text = str(args[0]).strip()
        if code_text in {"1205", "1213"}:
            return True
    message = str(original).lower()
    return "deadlock" in message or "lock wait timeout" in message



def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)



def _log_shared_deck_install_performance(
    *,
    deck_item_id: str,
    release_id: str,
    attempt: int,
    created: bool,
    status: int,
    started_at: float,
    phase_metrics: dict[str, Any],
) -> None:
    logger.info(
        "shared_deck_install_perf deck_item_id=%s release_id=%s worker_pid=%s "
        "attempt=%s status=%s created=%s total_ms=%.2f readiness_ms=%.2f "
        "note_type_ms=%.2f tree_clone_ms=%.2f counter_ms=%.2f commit_ms=%.2f",
        deck_item_id,
        release_id,
        os.getpid(),
        attempt,
        status,
        created,
        _elapsed_ms(started_at),
        float(phase_metrics.get("readiness_ms") or 0),
        float(phase_metrics.get("note_type_ms") or 0),
        float(phase_metrics.get("tree_clone_ms") or 0),
        float(phase_metrics.get("counter_ms") or 0),
        float(phase_metrics.get("commit_ms") or 0),
    )


DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}


class ShareControllerError(Exception):
    """Domain error for flashcard share/deck flows."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        error: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.error = error


def _require_legacy_overlay_install_route(*, user_id: int) -> None:
    """Fence install against NOTE enrollment until overlay subjects are canonical."""

    try:
        route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user_id),
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        raise ShareControllerError(str(exc), status=409, error=exc.code) from exc
    if route.mode_code == "NOTE":
        raise ShareControllerError(
            "Shared deck installation is unavailable for NOTE authority until overlay lifecycle is supported.",
            status=409,
            error="OVERLAY_AUTHORITY_NOT_READY",
        )


def make_unique_note_type_name(user_id: int, base_name: str) -> str:
    candidate = base_name.strip() or "Installed NoteType"
    if not flashcards_share_repository.get_note_type_by_name(user_id, candidate):
        return candidate
    counter = 2
    while True:
        candidate_with_counter = f"{candidate} ({counter})"
        if not flashcards_share_repository.get_note_type_by_name(user_id, candidate_with_counter):
            return candidate_with_counter
        counter += 1


def resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    deck_ids = collect_subtree_ids(deck_id)
    note_type_ids = flashcards_share_repository.get_note_type_ids_for_decks_notes(
        deck_ids,
        owner_user_id,
    )

    if not note_type_ids:
        return None, "Deck has no notes, cannot infer source_note_type_id."
    if len(note_type_ids) > 1:
        return None, "All notes in one deck must use the same template (note type)."

    resolved_note_type_id = note_type_ids[0]
    resolved_note_type = db.session.get(NoteType, resolved_note_type_id)
    if not resolved_note_type:
        return None, "Deck source note type not found."
    if not resolved_note_type.templates:
        return None, "Deck source note type has no templates."
    return resolved_note_type.id, None


def bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    if deck_item.source_deck_id is None:
        return "source_deck_id is required."

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id and deck_item.source_deck_id is not None:
        inferred_note_type_id, infer_error = resolve_single_note_type_for_deck(
            deck_id=deck_item.source_deck_id,
            owner_user_id=deck_item.owner_user_id,
        )
        if infer_error and require_source_note_type:
            return infer_error
        if inferred_note_type_id:
            deck_item.source_note_type_id = inferred_note_type_id
            source_note_type_id = inferred_note_type_id

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        if require_source_note_type:
            return "source_note_type_id is required."
        return None

    source_note_type = db.session.get(NoteType, source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found."
    provenance_error = validate_deck_source_note_type_provenance(
        deck_item=deck_item,
        source_note_type=source_note_type,
    )
    if provenance_error:
        return provenance_error
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type with at least one template."
    return None


def validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    if deck_id is None:
        return None

    marketplace_error = validate_marketplace_note_type_for_deck(
        deck_id=deck_id,
        note_type_id=note_type_id,
        user_id=user_id,
    )
    if marketplace_error:
        return marketplace_error

    existing_note_type_ids = flashcards_share_repository.get_note_type_ids_for_user_deck_notes(
        deck_id, user_id, exclude_note_id
    )

    if not existing_note_type_ids:
        return None
    if existing_note_type_ids == {note_type_id}:
        return None
    return "All notes in one deck must use the same template (note type)."



def validate_deck_source_note_type_provenance(
    *,
    deck_item: DeckMarketplaceItem,
    source_note_type: NoteType,
) -> str | None:
    if source_note_type.user_id != deck_item.owner_user_id:
        return "source_note_type_id not found."
    from app.services.share.note_types import is_installed_note_type_copy
    if is_installed_note_type_copy(source_note_type.id):
        return "Note Type được cài từ Marketplace không thể được đóng gói để chia sẻ lại."
    return None


def validate_marketplace_note_type_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int | None,
    publish_backstop: bool = False,
) -> str | None:
    """Enforce the persisted listing pointer at mutation/publish boundaries."""
    if deck_id is None or not str(note_type_id or "").strip():
        return None
    if publish_backstop:
        deck_ids = collect_subtree_ids(deck_id)
        query = Note.query.filter(
            Note.deck_id.in_(deck_ids),
            Note.note_type_id != str(note_type_id),
        )
        if user_id is not None:
            query = query.filter(Note.user_id == user_id)
        if query.first() is None:
            return None
        message = "Deck contains notes that do not match source_note_type_id."
    else:
        ancestor_ids = collect_ancestor_ids(deck_id)
        listings = (
            DeckMarketplaceItem.query.filter(
                DeckMarketplaceItem.source_deck_id.in_(ancestor_ids),
                DeckMarketplaceItem.publish_status.in_(PUBLISH_STATUSES_VISIBLE),
            ).all()
            if ancestor_ids
            else []
        )
        mismatch = next(
            (
                item
                for item in listings
                if str(item.source_note_type_id or "").strip()
                and str(item.source_note_type_id) != str(note_type_id)
            ),
            None,
        )
        if mismatch is None:
            return None
        message = "This shared deck requires its persisted source NoteType."

    mode = str(
        current_app.config.get("DECK_SOURCE_NOTETYPE_GUARD_MODE", "strict")
    ).strip().lower()
    if mode == "shadow" and not publish_backstop:
        logger.warning(
            "Deck source NoteType shadow mismatch deck_id=%s note_type_id=%s",
            deck_id,
            note_type_id,
        )
        return None
    return message



def validate_deck_subtree_move_to_parent(
    *,
    deck_id: int,
    new_parent_id: int | None,
    user_id: int | None,
) -> str | None:
    """Validate existing notes before attaching a subtree to a listed tree."""
    if new_parent_id is None:
        return None
    subtree_ids = collect_subtree_ids(deck_id)
    note_type_ids = flashcards_share_repository.get_note_type_ids_for_decks_notes(
        subtree_ids,
        user_id,
    )
    for note_type_id in note_type_ids:
        error = validate_marketplace_note_type_for_deck(
            deck_id=new_parent_id,
            note_type_id=note_type_id,
            user_id=user_id,
        )
        if error:
            return error
    return None


def _next_deck_position(parent_deck_id: int | None) -> int:
    return flashcards_share_repository.get_next_deck_position(parent_deck_id)


def sync_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> tuple[str | None, bool]:
    original_note_type_id = deck_item.source_note_type_id
    bind_error = bind_deck_item_source_note_type(
        deck_item,
        require_source_note_type=require_source_note_type,
    )
    changed = deck_item.source_note_type_id != original_note_type_id
    return bind_error, changed



def sync_deck_item_source_note_type_and_commit(
    deck_item: DeckMarketplaceItem,
    require_source_note_type: bool
) -> tuple[str | None, bool]:
    bind_error, changed = flashcards_share.sync_deck_item_source_note_type(
        deck_item, 
        require_source_note_type=require_source_note_type
    )
    if changed:
        db.session.commit()
    return bind_error, changed




def is_card_visible_in_clone_scope(
    *,
    scope: CloneDeckScope,
    card_obj: Card | None,
) -> bool:
    if card_obj is None or card_obj.note is None:
        return False
    if (
        card_obj.note.user_id == scope.install.user_id
        and card_obj.note.deck_id is not None
        and int(card_obj.note.deck_id) in set(scope.local_deck_ids)
        and DeckCloneAddedNote.query.filter_by(
            deck_install_id=scope.install.id,
            note_id=card_obj.note.id,
        ).first()
        is not None
    ):
        return True
    if card_obj.note.deck_id is None or int(card_obj.note.deck_id) not in set(scope.source_deck_ids):
        return False
    if scope.source_owner_user_id is not None and card_obj.note.user_id != scope.source_owner_user_id:
        return False
    if _install_uses_release(scope.install):
        if not _note_is_member_of_applied_release(
            install=scope.install,
            note_id=card_obj.note.id,
        ):
            return False
    elif scope.base_snapshot_at is not None:
        note_created = card_obj.note.created_at or datetime.min
        card_created = card_obj.created_at or datetime.min
        if note_created > scope.base_snapshot_at or card_created > scope.base_snapshot_at:
            return False
    return True


def is_note_type_visible_for_shared(
    note_type: NoteType,
    user_id: int | None = None,
    publish_statuses_visible: set[str] | None = None,
) -> bool:
    visible_statuses = publish_statuses_visible or PUBLISH_STATUSES_VISIBLE
    status = str(note_type.publish_status or "").strip().lower()
    if user_id is not None and note_type.user_id == user_id:
        return True
    return status in visible_statuses



def is_deck_item_visible_for_shared(
    deck_item: DeckMarketplaceItem,
    user_id: int | None = None,
    publish_statuses_visible: set[str] | None = None,
) -> bool:
    visible_statuses = publish_statuses_visible or PUBLISH_STATUSES_VISIBLE
    status = str(deck_item.publish_status or "").strip().lower()
    if user_id is not None and deck_item.owner_user_id == user_id:
        return True
    return status in visible_statuses




def touch_note_type_install_usage(
    *,
    user_id: int,
    installed_note_type_id: str,
    activity_at: datetime | None = None,
) -> None:
    install = (
        NoteTypeInstall.query.filter(
            NoteTypeInstall.user_id == user_id,
            or_(
                NoteTypeInstall.installed_note_type_id == installed_note_type_id,
                NoteTypeInstall.source_note_type_id == installed_note_type_id,
            ),
        )
        .order_by(
            (NoteTypeInstall.installed_note_type_id == installed_note_type_id).desc(),
            NoteTypeInstall.installed_at.asc(),
            NoteTypeInstall.id.asc(),
        )
        .with_for_update()
        .first()
    )
    if not install:
        return
    now = activity_at or _utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now
    _update_note_type_install_market_activity(install, now=now)


def note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    return flashcards_share_repository.get_note_type_reps_for_user(user_id, installed_note_type_id)


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
    note_count = flashcards_share_repository.count_notes_by_note_type_for_user(
        install.user_id, install.installed_note_type_id
    )
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
    install_count, active_usage_count = (
        db.session.query(
            db.func.count(NoteTypeInstall.id),
            db.func.coalesce(
                db.func.sum(case((NoteTypeInstall.market_active.is_(True), 1), else_=0)),
                0,
            ),
        )
        .filter(NoteTypeInstall.source_note_type_id == note_type.id)
        .first()
    )
    note_type.install_count = int(install_count or 0)
    note_type.active_usage_count = int(active_usage_count or 0)

    rating_avg, rating_count = flashcards_share_repository.get_note_type_market_rating_stats(note_type.id)
    note_type.rating_avg = rating_avg
    note_type.rating_count = rating_count


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
    install = flashcards_share_repository.get_note_type_install_by_user_and_source(user_id, note_type.id)
    if not install:
        return False
    return is_note_type_install_active(
        install,
        now=_utcnow(),
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
    now = activity_at or _utcnow()
    for install in installs:
        install = (
            DeckInstall.query.filter_by(id=install.id)
            .with_for_update()
            .first()
        ) or install
        if install.first_use_at is None:
            install.first_use_at = now
        install.last_activity_at = now
        _update_deck_install_market_activity(install, now=now)


def deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    clone_scope = resolve_clone_scope_for_local_deck(
        user_id=user_id,
        local_deck_id=local_deck_id,
    )
    if clone_scope is not None and clone_scope.source_deck_ids:
        return flashcards_share_repository.get_deck_reps_for_user_in_source_scope(
            user_id, 
            clone_scope.source_deck_ids, 
            clone_scope.source_owner_user_id, 
            clone_scope.base_snapshot_at
        )

    subtree_deck_ids = collect_subtree_ids(local_deck_id)
    return flashcards_share_repository.get_deck_reps_for_user_in_subtree(user_id, subtree_deck_ids)


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
    install_count, active_usage_count = (
        db.session.query(
            db.func.count(DeckInstall.id),
            db.func.coalesce(
                db.func.sum(case((DeckInstall.market_active.is_(True), 1), else_=0)),
                0,
            ),
        )
        .filter(DeckInstall.deck_item_id == deck_item.id)
        .first()
    )
    deck_item.install_count = int(install_count or 0)
    deck_item.active_usage_count = int(active_usage_count or 0)

    rating_avg, rating_count = flashcards_share_repository.get_deck_market_rating_stats(deck_item.id)
    deck_item.rating_avg = rating_avg
    deck_item.rating_count = rating_count


def can_user_rate_deck(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = 3,
) -> bool:
    if deck_item.owner_user_id == user_id:
        return False
    install = flashcards_share_repository.get_deck_install_by_user_and_item(user_id, deck_item.id)
    if not install:
        return False
    return is_deck_install_active(
        install,
        deck_active_review_threshold=deck_active_review_threshold,
    )



def _increment_counter(model, row_id: str, column, delta: int) -> None:
    if not delta:
        return
    next_value = column + int(delta)
    db.session.query(model).filter(model.id == row_id).update(
        {column: case((next_value < 0, 0), else_=next_value)},
        synchronize_session=False,
    )



def _set_note_type_install_market_activity(
    install: NoteTypeInstall,
    *,
    active: bool,
    now: datetime,
) -> None:
    previous = bool(install.market_active)
    install.market_active = bool(active)
    install.market_active_evaluated_at = now
    install.market_active_policy_version = MARKET_ACTIVITY_POLICY_VERSION
    if previous != bool(active):
        _increment_counter(
            NoteType,
            str(install.source_note_type_id),
            NoteType.active_usage_count,
            1 if active else -1,
        )



def _update_note_type_install_market_activity(
    install: NoteTypeInstall,
    *,
    now: datetime,
) -> None:
    _set_note_type_install_market_activity(
        install,
        active=is_note_type_install_active(
            install,
            now=now,
            note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
            note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
            note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
        ),
        now=now,
    )



def _set_deck_install_market_activity(
    install: DeckInstall,
    *,
    active: bool,
    now: datetime,
) -> None:
    previous = bool(install.market_active)
    install.market_active = bool(active)
    install.market_active_evaluated_at = now
    install.market_active_policy_version = MARKET_ACTIVITY_POLICY_VERSION
    if previous != bool(active):
        _increment_counter(
            DeckMarketplaceItem,
            str(install.deck_item_id),
            DeckMarketplaceItem.active_usage_count,
            1 if active else -1,
        )



def _update_deck_install_market_activity(
    install: DeckInstall,
    *,
    now: datetime,
) -> None:
    _set_deck_install_market_activity(
        install,
        active=is_deck_install_active(
            install,
            deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
        ),
        now=now,
    )



def remove_deck_install_market_counters(installs: list[DeckInstall]) -> None:
    grouped: dict[str, tuple[int, int]] = {}
    for install in installs:
        total, active = grouped.get(str(install.deck_item_id), (0, 0))
        grouped[str(install.deck_item_id)] = (
            total + 1,
            active + (1 if bool(install.market_active) else 0),
        )
    for deck_item_id, (total, active) in grouped.items():
        _increment_counter(
            DeckMarketplaceItem,
            deck_item_id,
            DeckMarketplaceItem.install_count,
            -total,
        )
        _increment_counter(
            DeckMarketplaceItem,
            deck_item_id,
            DeckMarketplaceItem.active_usage_count,
            -active,
        )



def remove_note_type_install_market_counters(
    installs: list[NoteTypeInstall],
) -> None:
    grouped: dict[str, tuple[int, int]] = {}
    for install in installs:
        source_note_type_id = str(install.source_note_type_id or "").strip()
        if not source_note_type_id:
            continue
        total, active = grouped.get(source_note_type_id, (0, 0))
        grouped[source_note_type_id] = (
            total + 1,
            active + (1 if bool(install.market_active) else 0),
        )
    for source_note_type_id, (total, active) in grouped.items():
        _increment_counter(
            NoteType,
            source_note_type_id,
            NoteType.install_count,
            -total,
        )
        _increment_counter(
            NoteType,
            source_note_type_id,
            NoteType.active_usage_count,
            -active,
        )



def deactivate_note_type_installs_for_deleted_copy(
    *,
    user_id: int,
    installed_note_type_id: str,
) -> None:
    installs = (
        NoteTypeInstall.query.filter_by(
            user_id=user_id,
            installed_note_type_id=installed_note_type_id,
        )
        .with_for_update()
        .all()
    )
    now = _utcnow()
    for install in installs:
        _set_note_type_install_market_activity(install, active=False, now=now)



def can_user_rate_deck_item(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = DECK_ACTIVE_REVIEW_THRESHOLD,
) -> bool:
    return can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=deck_active_review_threshold,
    )


