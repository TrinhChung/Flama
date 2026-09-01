"""Shared deck marketplace installation workflow for users."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

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
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)


from app.services.share.helpers import (
    ShareControllerError,
    _audit,
    _elapsed_ms,
    _increment_counter,
    _is_mysql_deadlock,
    _log_shared_deck_install_performance,
    _set_deck_install_market_activity,
    _utcnow,
    touch_deck_install_usage,
    validate_deck_source_note_type_provenance,
)
from app.services.share.note_types import ensure_note_type_install_for_user
from app.services.share.overlay import (
    clone_deck_subtree,
    get_user_deck_install_for_item,
    upsert_shared_deck_clone_overlay,
)

def _installed_local_deck_ids(*, user_id: int) -> set[int]:
    installs = DeckInstall.query.filter_by(user_id=user_id).all()
    if not installs:
        return set()

    install_ids = [row.id for row in installs if row.id]
    root_ids = {
        int(row.local_deck_id)
        for row in installs
        if row.local_deck_id is not None
    }
    mapped_ids = {
        int(row[0])
        for row in (
            db.session.query(DeckCloneDeckMap.local_deck_id)
            .filter(DeckCloneDeckMap.deck_install_id.in_(install_ids))
            .all()
        )
        if row and row[0] is not None
    } if install_ids else set()

    # Clone maps precisely distinguish copied Marketplace nodes from decks the
    # user later creates themselves (including Anki-synced decks).
    return root_ids | mapped_ids



def install_shared_deck_item(deck_item_id: str, user_id: int, publish_statuses_visible: set[str]) -> tuple[dict | None, str | None, str | None, int]:
    request_started = time.perf_counter()
    for attempt in range(1, SHARED_DECK_INSTALL_MAX_RETRIES + 1):
        deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
        if not deck_item:
            return None, "Deck item not found.", None, 404
        performance_deck_item_id = str(deck_item.id)
        performance_release_id = str(deck_item.current_release_id or "")

        if not str(deck_item.source_note_type_id or "").strip():
            return (
                None,
                "source_note_type_id is required for install.",
                "source_note_type_id",
                409,
            )

        try:
            install_result = flashcards_share.install_shared_deck_item_for_user(
                deck_item,
                user_id=user_id,
                publish_statuses_visible=publish_statuses_visible,
            )
        except flashcards_share.ShareControllerError as exc:
            db.session.rollback()
            _log_shared_deck_install_performance(
                deck_item_id=performance_deck_item_id,
                release_id=performance_release_id,
                attempt=attempt,
                created=False,
                status=exc.status,
                started_at=request_started,
                phase_metrics={},
            )
            return None, exc.message, exc.field, exc.status
        except IntegrityError:
            db.session.rollback()
            concurrent_install = DeckInstall.query.filter_by(
                deck_item_id=deck_item_id,
                user_id=user_id,
            ).first()
            if concurrent_install is not None:
                return {
                    "deck_item_id": deck_item_id,
                    "installed_deck_id": concurrent_install.local_deck_id,
                    "already_installed": True,
                }, None, None, 200
            if attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                continue
            raise
        except OperationalError as exc:
            db.session.rollback()
            if flashcards_share._is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while installing shared deck "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    user_id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if flashcards_share._is_mysql_deadlock(exc):
                return None, SHARED_DECK_INSTALL_DEADLOCK_MESSAGE, None, 409
            raise

        if not install_result.get("created"):
            _log_shared_deck_install_performance(
                deck_item_id=performance_deck_item_id,
                release_id=performance_release_id,
                attempt=attempt,
                created=False,
                status=200,
                started_at=request_started,
                phase_metrics=install_result.get("performance") or {},
            )
            return install_result.get("response") or {}, None, None, 200

        _audit(user_id, "market.deck_item.install", install_result.get("audit") or {})
        commit_started = time.perf_counter()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            concurrent_install = DeckInstall.query.filter_by(
                deck_item_id=deck_item_id,
                user_id=user_id,
            ).first()
            if concurrent_install is not None:
                return {
                    "deck_item_id": deck_item_id,
                    "installed_deck_id": concurrent_install.local_deck_id,
                    "already_installed": True,
                }, None, None, 200
            if attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                continue
            raise
        except OperationalError as exc:
            db.session.rollback()
            if flashcards_share._is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while committing shared deck install "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    user_id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if flashcards_share._is_mysql_deadlock(exc):
                return None, SHARED_DECK_INSTALL_DEADLOCK_MESSAGE, None, 409
            raise

        phase_metrics = dict(install_result.get("performance") or {})
        phase_metrics["commit_ms"] = _elapsed_ms(commit_started)
        _log_shared_deck_install_performance(
            deck_item_id=performance_deck_item_id,
            release_id=performance_release_id,
            attempt=attempt,
            created=True,
            status=201,
            started_at=request_started,
            phase_metrics=phase_metrics,
        )
        return install_result.get("response") or {}, None, None, 201

    return None, SHARED_DECK_INSTALL_DEADLOCK_MESSAGE, None, 409



def install_shared_deck_item_for_user(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> dict[str, Any]:
    readiness_started = time.perf_counter()
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in visible_statuses:
        raise ShareControllerError(
            "This deck is not available for install.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise ShareControllerError(
            "Owner cannot install own deck item.",
            status=409,
        )

    existing = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if existing:
        return {
            "created": False,
            "performance": {"readiness_ms": _elapsed_ms(readiness_started)},
            "response": {
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
                "already_installed": True,
            },
        }

    if deck_item.current_release_id is None:
        raise ShareControllerError(
            "Deck listing is preparing its initial release and cannot be installed yet.",
            status=503,
            error="DECK_RELEASE_NOT_READY",
        )

    source_note_type_id = str(deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        raise ShareControllerError(
            "source_note_type_id is required for install.",
            status=409,
            field="source_note_type_id",
        )

    now = _utcnow()
    source_deck_id = deck_item.source_deck_id
    if source_deck_id is None:
        raise ShareControllerError(
            "source_deck_id is required for install.",
            status=409,
            field="source_deck_id",
        )
    source_deck = db.session.get(Deck, source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            "Source deck not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )

    note_type_id_map: dict[str, str] = {}
    source_note_type = db.session.get(NoteType, source_note_type_id)
    if source_note_type is None:
        raise ShareControllerError(
            "source_note_type_id not found.",
            status=409,
            field="source_note_type_id",
        )
    provenance_error = validate_deck_source_note_type_provenance(
        deck_item=deck_item,
        source_note_type=source_note_type,
    )
    if provenance_error:
        raise ShareControllerError(
            provenance_error,
            status=404 if provenance_error == "source_note_type_id not found." else 409,
            field="source_note_type_id",
            error="FIELD_NOT_FOUND" if provenance_error == "source_note_type_id not found." else "CONFLICT",
        )
    readiness_ms = _elapsed_ms(readiness_started)
    note_type_started = time.perf_counter()
    note_type_install = ensure_note_type_install_for_user(
        source_note_type=source_note_type,
        user_id=user_id,
        installed_at=now,
    )
    installed_note_type_id = (note_type_install.installed_note_type_id or "").strip()
    if installed_note_type_id:
        note_type_id_map[source_note_type_id] = installed_note_type_id
    note_type_ms = _elapsed_ms(note_type_started)

    purchase_amount_minor = int(deck_item.price_amount_minor or 0) if deck_item.pricing_mode == "paid" else 0
    install = DeckInstall(
        deck_item_id=deck_item.id,
        user_id=user_id,
        local_deck_id=None,
        clone_mode="logical_overlay",
        source_deck_id=source_deck.id,
        source_note_type_id=(deck_item.source_note_type_id or "").strip() or None,
        source_owner_user_id=deck_item.owner_user_id,
        base_snapshot_at=now,
        applied_release_id=deck_item.current_release_id,
        seen_release_id=deck_item.current_release_id,
        version_mode=("release" if deck_item.current_release_id else "legacy_snapshot"),
        purchase_amount_minor=purchase_amount_minor,
        installed_at=now,
        purchased_at=now if deck_item.pricing_mode == "paid" else None,
        market_active=False,
        market_active_evaluated_at=now,
        market_active_policy_version=MARKET_ACTIVITY_POLICY_VERSION,
    )
    db.session.add(install)
    db.session.flush()

    local_deck_id = None
    tree_clone_started = time.perf_counter()
    cloned_root = clone_deck_subtree(
        source_deck_id=source_deck.id,
        parent_id=None,
        deck_install_id=install.id,
        owner_user_id=user_id,
        note_type_id_map=note_type_id_map,
    )
    if cloned_root.note_type_id is None and note_type_id_map:
        cloned_root.note_type_id = next(iter(note_type_id_map.values()))
    local_deck_id = cloned_root.id
    install.local_deck_id = local_deck_id

    counter_started = time.perf_counter()
    _increment_counter(
        DeckMarketplaceItem,
        deck_item.id,
        DeckMarketplaceItem.install_count,
        1,
    )
    return {
        "created": True,
        "performance": {
            "readiness_ms": readiness_ms,
            "note_type_ms": note_type_ms,
            "tree_clone_ms": _elapsed_ms(tree_clone_started),
            "counter_ms": _elapsed_ms(counter_started),
        },
        "response": {
            "deck_item_id": deck_item.id,
            "installed_deck_id": local_deck_id,
            "purchase_amount_minor": purchase_amount_minor,
            "purchase_price_cents": purchase_amount_minor,
        },
        "audit": {
            "deck_item_id": deck_item.id,
            "local_deck_id": local_deck_id,
            "price_amount_minor": purchase_amount_minor,
            "price_cents": purchase_amount_minor,
        },
    }

