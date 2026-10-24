"""Deck management services encapsulating transaction boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.repositories.deck_tree_query import (
    collect_ancestor_ids as _collect_deck_ancestor_ids,
    collect_subtree_ids as _collect_deck_subtree_ids,
)
from app.services import study_progress_lifecycle_mirror_service
from app.services.scheduler_config_service import resolve_deck_options
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from models import db
from models.deck import Deck
from models.card import card_key_pairs, forget_card_identities, legacy_card_ids, note_card_ids
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, DeckMarketplaceItem, Note
from models.study_progress_subject import StudyProgressSubject

UTC = timezone.utc

class DeckManagementError(Exception):
    pass


@dataclass(frozen=True)
class _DeckPurgeScope:
    deck_ids: tuple[int, ...]
    note_ids: tuple[str, ...]
    card_ids: tuple[str, ...]
    learner_user_ids: tuple[int, ...]


def _current_deck_subtree_ids(root_deck_id: int) -> tuple[int, ...]:
    """Rewalk the subtree with current InnoDB reads after locking its root."""
    seen: set[int] = set()
    frontier = {int(root_deck_id)}
    while frontier:
        current = frontier - seen
        if not current:
            break
        rows = (
            db.session.query(Deck.id)
            .filter(Deck.id.in_(sorted(current)))
            .order_by(Deck.id.asc())
            .with_for_update()
            .all()
        )
        present = {int(row.id) for row in rows}
        if present != current:
            raise StudyAuthorityFenceError(
                "PURGE_SCOPE_CHANGED", "Deck subtree changed during purge admission."
            )
        seen.update(current)
        frontier = {
            int(row.id)
            for row in db.session.query(Deck.id)
            .filter(Deck.parent_id.in_(sorted(current)))
            .order_by(Deck.id.asc())
            .with_for_update()
            .all()
        }
    return tuple(sorted(seen))


def _deck_purge_scope(
    deck_ids: tuple[int, ...], *, fallback_user_id: int, current_read: bool = False
) -> _DeckPurgeScope:
    """Discover study and install learners affected by an admin deck purge."""
    from models.review_event import ReviewEvent
    from models.study_session import StudySession
    from models.study_session_card import StudySessionCard

    def read(query):
        return query.with_for_update() if current_read else query

    learner_ids = {int(fallback_user_id)}

    def collect_learner_ids(query) -> None:
        learner_ids.update(int(row[0]) for row in read(query.distinct()).all())

    note_ids_found: list[str] = []
    for offset in range(0, len(deck_ids), 500):
        deck_chunk = deck_ids[offset : offset + 500]
        collect_learner_ids(
            db.session.query(Deck.owner_user_id).filter(
                Deck.id.in_(deck_chunk), Deck.owner_user_id.isnot(None)
            )
        )
        note_rows = read(
            db.session.query(Note.id, Note.user_id).filter(Note.deck_id.in_(deck_chunk))
        ).all()
        note_ids_found.extend(str(row.id) for row in note_rows)
        learner_ids.update(int(row.user_id) for row in note_rows)
        for install_query in (
            db.session.query(DeckInstall.user_id).filter(
                (DeckInstall.local_deck_id.in_(deck_chunk))
                | (DeckInstall.source_deck_id.in_(deck_chunk))
            ),
            db.session.query(DeckInstall.user_id)
            .join(DeckMarketplaceItem, DeckInstall.deck_item_id == DeckMarketplaceItem.id)
            .filter(DeckMarketplaceItem.source_deck_id.in_(deck_chunk)),
            db.session.query(DeckInstall.user_id)
            .join(DeckCloneDeckMap, DeckCloneDeckMap.deck_install_id == DeckInstall.id)
            .filter(
                (DeckCloneDeckMap.local_deck_id.in_(deck_chunk))
                | (DeckCloneDeckMap.source_deck_id.in_(deck_chunk))
            ),
        ):
            collect_learner_ids(install_query)
        collect_learner_ids(
            db.session.query(StudySession.user_id).filter(
                StudySession.local_deck_id.in_(deck_chunk)
            )
        )
        collect_learner_ids(
            db.session.query(StudySession.user_id)
            .join(StudySessionCard, StudySessionCard.session_id == StudySession.id)
            .filter(
                (StudySessionCard.local_deck_id.in_(deck_chunk))
                | (StudySessionCard.source_deck_id.in_(deck_chunk))
            )
        )
        collect_learner_ids(
            db.session.query(ReviewEvent.user_id).filter(
                ReviewEvent.deck_id.in_(deck_chunk)
            )
        )

    note_ids = tuple(sorted(note_ids_found))
    card_ids_found: list[str] = []
    for offset in range(0, len(note_ids), 500):
        note_chunk = note_ids[offset : offset + 500]
        card_rows = read(
            db.session.query(Card.id).filter(Card.note_id.in_(note_chunk))
        ).all()
        card_ids_found.extend(str(row.id) for row in card_rows)
        collect_learner_ids(
            db.session.query(StudyProgressSubject.learner_user_id).filter(
                (StudyProgressSubject.live_note_id.in_(note_chunk))
                | StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in note_chunk]
                )
            )
        )
    card_ids = tuple(sorted(card_ids_found))
    from app.repositories.study_authority_repository import projection_is_live

    projection_live = projection_is_live(db.session)
    for offset in range(0, len(card_ids), 500):
        card_chunk = card_ids[offset : offset + 500]
        pass
        collect_learner_ids(
            db.session.query(StudySession.user_id)
            .join(StudySessionCard, StudySessionCard.session_id == StudySession.id)
            .filter(StudySessionCard.card_id.in_(card_chunk))
        )
    return _DeckPurgeScope(
        deck_ids=deck_ids,
        note_ids=note_ids,
        card_ids=card_ids,
        learner_user_ids=tuple(sorted(learner_ids)),
    )

def create_decks_path(*, tokens: List[str], parent_id: Optional[int] = None) -> tuple[int, Optional[Deck]]:
    """Creates a path of decks under the given parent_id mapping tokens to deck names.
    Commits the transaction and returns the number of newly created decks and the deepest leaf Deck.
    """
    created_count = 0
    final_deck = None
    current_parent_id = parent_id

    for token in tokens:
        existing = (
            Deck.query.filter(
                Deck.parent_id == current_parent_id,
                Deck.name == token,
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if existing:
            final_deck = existing
            current_parent_id = existing.id
            continue

        position = vocabulary_ctrl.next_deck_position(current_parent_id)
        node = Deck(
            parent_id=current_parent_id,
            name=token,
            position=position,
        )
        db.session.add(node)
        db.session.flush()
        created_count += 1
        final_deck = node
        current_parent_id = node.id

    flush_review_analytics_deltas(db.session)
    db.session.commit()
    return created_count, final_deck

def rename_deck(*, deck_obj: Deck, new_name: str) -> None:
    """Renames a deck and commits the transaction."""
    deck_obj.name = new_name
    flush_review_analytics_deltas(db.session)
    db.session.commit()

def move_deck(*, deck_obj: Deck, new_parent_id: Optional[int]) -> None:
    """Moves a deck under a new parent and commits the transaction."""
    from app.services import flashcards_share_service

    guard_error = flashcards_share_service.validate_deck_subtree_move_to_parent(
        deck_id=deck_obj.id,
        new_parent_id=new_parent_id,
        user_id=deck_obj.owner_user_id,
    )
    if guard_error:
        raise ValueError(guard_error)
    deck_obj.parent_id = new_parent_id
    deck_obj.position = vocabulary_ctrl.next_deck_position(new_parent_id)
    flush_review_analytics_deltas(db.session)
    db.session.commit()

def _purge_deck_subtree(*, deck_obj: Deck, user_id: int, authority_learner_id: int) -> str:
    with db.session.no_autoflush:
        deck_ids_to_delete = _collect_deck_subtree_ids(deck_obj.id)
        scope = _deck_purge_scope(
            tuple(deck_ids_to_delete), fallback_user_id=authority_learner_id
        )
    # Purge spans owner content, installs and shared Card progress. Take all
    # learner fences in ID order before locking/deleting content or provenance.
    authority_routes = tuple(
        lock_study_authority_route(
            db.session,
            learner_user_id=learner_id,
            allow_note_authority=True,
        )
        for learner_id in scope.learner_user_ids
    )
    locked_deck = (
        db.session.query(Deck)
        .filter(Deck.id == deck_obj.id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if locked_deck is None:
        raise StudyAuthorityFenceError(
            "PURGE_SCOPE_CHANGED", "Deck changed during purge admission."
        )
    current_deck_ids = _current_deck_subtree_ids(int(locked_deck.id))
    if (
        current_deck_ids != scope.deck_ids
        or _deck_purge_scope(
            current_deck_ids,
            fallback_user_id=int(locked_deck.owner_user_id or user_id),
            current_read=True,
        ) != scope
    ):
        raise StudyAuthorityFenceError(
            "PURGE_SCOPE_CHANGED",
            "Deck purge scope changed while learner routes were locked.",
        )
    # A purged installed clone node keeps its learners' overlay source state,
    # exactly as LEGACY keeps their source CardProgress rows.

    from models.deck_change_request import DeckChangeRequest
    from models.review_event import ReviewEvent
    from models.study_session import StudySession
    from models.study_session_card import StudySessionCard
    from app.services.study_content_delete_service import (
        finalize_content_delete,
        prepare_content_delete,
    )

    # Validate and lock every NOTE/LEGACY learner plan before any row changes.
    lifecycle_plan = prepare_content_delete(
        db.session,
        routes=authority_routes,
        card_ids=scope.card_ids,
        note_ids=scope.note_ids,
    )

    # 1. Delete DeckChangeRequests referencing local_deck_id or source_deck_id in deck_ids_to_delete
    DeckChangeRequest.query.filter(
        (DeckChangeRequest.local_deck_id.in_(deck_ids_to_delete)) |
        (DeckChangeRequest.source_deck_id.in_(deck_ids_to_delete))
    ).delete(synchronize_session=False)

    # 2. Delete DeckInstalls referencing local_deck_id or source_deck_id in deck_ids_to_delete
    install_query = DeckInstall.query.filter(
        (DeckInstall.local_deck_id.in_(deck_ids_to_delete)) |
        (DeckInstall.source_deck_id.in_(deck_ids_to_delete))
    )
    install_rows = install_query.with_for_update().all()
    if install_rows:
        from app.services import flashcards_share_service

        flashcards_share_service.remove_deck_install_market_counters(
            install_rows
        )
    install_query.delete(synchronize_session=False)

    # 3. Delete DeckMarketplaceItems referencing source_deck_id in deck_ids_to_delete
    DeckMarketplaceItem.query.filter(
        DeckMarketplaceItem.source_deck_id.in_(deck_ids_to_delete)
    ).delete(synchronize_session=False)

    # 4. ReviewEvent is an immutable analytics fact. Detach the deleted
    # deck snapshot instead of erasing study history and breaking imported
    # Anki provenance links.
    from app.services.review_analytics_projection_service import invalidate_review_analytics

    invalidate_review_analytics(db.session, scope.learner_user_ids)
    ReviewEvent.query.filter(
        ReviewEvent.deck_id.in_(deck_ids_to_delete)
    ).update({ReviewEvent.deck_id: None}, synchronize_session=False)

    # 5. Delete StudySessionCards referencing local_deck_id in deck_ids_to_delete
    StudySessionCard.query.filter(
        StudySessionCard.local_deck_id.in_(deck_ids_to_delete)
    ).delete(synchronize_session=False)

    # 6. Delete StudySessions referencing local_deck_id in deck_ids_to_delete
    StudySession.query.filter(
        StudySession.local_deck_id.in_(deck_ids_to_delete)
    ).delete(synchronize_session=False)

    # 7. Delete compatibility progress, tombstone every learner's subject,
    # then delete all notes and cards inside the deck subtree.
    if scope.card_ids:
        pass  # NOTE lifecycle state is handled by the fenced deletion plan.
    finalize_content_delete(
        lifecycle_plan,
        source_path="deck.delete.purge",
        operation_key=f"deck-purge:{deck_obj.id}",
    )
    if scope.note_ids:
        # Their derived Cards go with the Notes (ADR P11).
        forget_card_identities(db.session, scope.note_ids)
        Note.query.filter(Note.id.in_(scope.note_ids)).delete(synchronize_session=False)

    # 8. Delete the deck object itself
    db.session.delete(deck_obj)
    flush_review_analytics_deltas(db.session)
    db.session.commit()
    return "purged"


def delete_deck_subtree(*, deck_obj: Deck, user_id: int, is_admin: bool, purge: bool = False) -> str:
    """Delete a local deck, or archive a shared source while preserving installs."""
    authority_learner_id = int(deck_obj.owner_user_id or user_id)

    if purge:
        if not is_admin:
            raise ValueError("Only administrators can purge decks.")
        try:
            return _purge_deck_subtree(
                deck_obj=deck_obj,
                user_id=user_id,
                authority_learner_id=authority_learner_id,
            )
        except Exception:
            # Never leave staged tombstones or bulk deletes in the session.
            db.session.rollback()
            raise

    deck_ids_to_delete = _collect_deck_subtree_ids(deck_obj.id)

    marketplace_source_ids = set(deck_ids_to_delete)
    marketplace_source_ids.update(_collect_deck_ancestor_ids(deck_obj.id))
    marketplace_items = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.source_deck_id.in_(marketplace_source_ids)
        ).all()
    )
    has_overlay_dependents = (
        db.session.query(DeckCloneDeckMap.id)
        .filter(DeckCloneDeckMap.source_deck_id.in_(deck_ids_to_delete))
        .first()
        is not None
    )
    has_source_installs = (
        db.session.query(DeckInstall.id)
        .filter(DeckInstall.source_deck_id.in_(deck_ids_to_delete))
        .first()
        is not None
    )

    if marketplace_items or has_overlay_dependents or has_source_installs:
        # Archival changes no progress or state in either authority mode;
        # installers keep studying the archived source through their overlay.
        lock_study_authority_route(
            db.session,
            learner_user_id=authority_learner_id,
            allow_note_authority=True,
        )
        deleted_at = datetime.now(UTC).replace(tzinfo=None)
        Deck.query.filter(Deck.id.in_(deck_ids_to_delete)).update(
            {Deck.deleted_at: deleted_at},
            synchronize_session=False,
        )
        for marketplace_item in marketplace_items:
            marketplace_item.publish_status = "archived"
            marketplace_item.archived_at = deleted_at
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        return "archived"

    from app.services import study_content_delete_service as content_delete

    note_rows = db.session.query(Note.id).filter(Note.deck_id.in_(deck_ids_to_delete)).all()
    note_ids = [str(row[0]) for row in note_rows if row and row[0]]
    card_rows = (
        db.session.query(Card.id).filter(Card.note_id.in_(note_ids)).all()
        if note_ids
        else []
    )
    card_ids = [str(row[0]) for row in card_rows if row and row[0]]
    # Notes owned by other users and other learners' progress on these Cards
    # are fenced in learner ID order together with the deck owner.
    authority_routes = content_delete.lock_content_delete_routes(
        db.session,
        actor_user_ids=(authority_learner_id,),
        card_ids=card_ids,
        deleted_note_ids=note_ids,
    )
    authority_route = next(
        route
        for route in authority_routes
        if route.learner_user_id == authority_learner_id
    )
    # Deleting an installed clone node removes the install/map rows and the
    # learner's local Notes; its overlay source state stays, as LEGACY keeps
    # source CardProgress rows, and is reused if the deck is installed again.
    install_query = DeckInstall.query.filter(DeckInstall.local_deck_id.in_(deck_ids_to_delete))
    if not is_admin:
        install_query = install_query.filter(DeckInstall.user_id == user_id)
    install_rows = install_query.all()
    if install_rows:
        from app.services import flashcards_share_service

        flashcards_share_service.remove_deck_install_market_counters(install_rows)
    install_query.delete(synchronize_session=False)

    if note_ids:
        lifecycle_plan = content_delete.prepare_content_delete(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            note_ids=note_ids,
            cancel_legacy_sessions=False,
        )
        content_delete.verify_content_delete_scope(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            deleted_note_ids=note_ids,
        )
        current_note_ids = {
            str(row[0])
            for row in db.session.query(Note.id)
            .filter(Note.deck_id.in_(deck_ids_to_delete))
            .with_for_update(read=True)
            .all()
        }
        if current_note_ids != set(note_ids):
            raise StudyAuthorityFenceError(
                "CONTENT_SCOPE_CHANGED",
                "Deck Notes changed while the deletion was admitted; retry.",
            )
        if card_ids:
            pass  # NOTE lifecycle state is handled by the fenced deletion plan.
        content_delete.finalize_content_delete(
            lifecycle_plan,
            source_path="deck.delete",
            operation_key=f"deck-delete:{deck_obj.id}",
        )
        # Their derived Cards go with the Notes (ADR P11).
        forget_card_identities(db.session, note_ids)
        Note.query.filter(Note.id.in_(note_ids)).delete(synchronize_session=False)

    db.session.delete(deck_obj)
    flush_review_analytics_deltas(db.session)
    db.session.commit()
    return "deleted"

def reset_deck_progress(*, deck_obj: Deck, user_id: int) -> int:
    """Reset current-user progress, including logical-overlay source cards."""
    authority_route = lock_study_authority_route(
        db.session,
        learner_user_id=int(user_id),
        allow_note_authority=True,
    )
    deck_ids = _collect_deck_subtree_ids(deck_obj.id)
    card_id_set = {
        str(row[0])
        for row in (
            db.session.query(Card.id)
            .join(Note, Card.note_id == Note.id)
            .filter(Note.deck_id.in_(deck_ids))
            .all()
        )
        if row and row[0]
    }

    from app.services import flashcards_share

    seen_scopes: set[tuple[str, int]] = set()
    overlay_local_deck_by_note_id: dict[str, int] = {}
    for local_deck_id in sorted(
        {int(item) for item in deck_ids if item is not None}
    ):
        clone_scope = flashcards_share.resolve_clone_scope_for_local_deck(
            user_id=user_id,
            local_deck_id=local_deck_id,
        )
        if clone_scope is None:
            continue
        scope_key = (
            str(clone_scope.install.id),
            int(clone_scope.local_scope_deck_id),
        )
        if scope_key in seen_scopes:
            continue
        seen_scopes.add(scope_key)
        clone_rows = (
            flashcards_share.query_clone_scope_cards(clone_scope)
            .with_entities(Card.id, Note.id, Note.deck_id, Note.user_id)
            .all()
        )
        for card_id, note_id, source_deck_id, note_owner_id in clone_rows:
            if not card_id:
                continue
            card_id_set.add(str(card_id))
            if note_owner_id is not None and int(note_owner_id) == int(user_id):
                continue  # Local-added Notes keep their own deck options.
            overlay_local_deck_by_note_id.setdefault(
                str(note_id),
                int(
                    (clone_scope.source_to_local_deck_id or {}).get(int(source_deck_id or 0))
                    or clone_scope.install.local_deck_id
                ),
            )

    starting_ease_by_note_id: dict[str, float] = {}
    if authority_route.mode_code == "NOTE" and card_id_set:
        # NOTE state is per Note, so a reset covers every sibling of each
        # affected Note (including an overlay sibling outside the install
        # snapshot). Overlay source Notes restart with the learner's mapped
        # local deck options, exactly as a LEGACY first review would.
        note_ids = {
            note_id for note_id, _application_id in card_key_pairs(db.session, card_id_set).values()
        }
        card_id_set.update(note_card_ids(db.session, note_ids))
        options_by_deck_id: dict[int, float] = {}
        for note_id, local_deck_id in overlay_local_deck_by_note_id.items():
            if local_deck_id not in options_by_deck_id:
                options_by_deck_id[local_deck_id] = float(
                    resolve_deck_options(user_id=int(user_id), deck_id=local_deck_id).startingEase
                )
            starting_ease_by_note_id[note_id] = options_by_deck_id[local_deck_id]

    deleted_count = 0
    if card_id_set:
        from models.study_session import StudySession
        from models.study_session_card import StudySessionCard

        session_wire_ids = card_id_set | set(legacy_card_ids(db.session, card_id_set))
        affected_session_ids = db.session.query(
            StudySessionCard.session_id
        ).filter(StudySessionCard.card_id.in_(sorted(session_wire_ids)))
        open_sessions = (
            StudySession.query.filter(
                StudySession.user_id == user_id,
                StudySession.status == "open",
                StudySession.id.in_(affected_session_ids),
            )
            .order_by(StudySession.id.asc())
            .with_for_update()
            .all()
        )
        for session in open_sessions:
            session.status = "cancelled"

        lifecycle_plan = study_progress_lifecycle_mirror_service.prepare_note_authority_reset(
            db.session,
            route=authority_route,
            removed_card_ids=card_id_set,
            starting_ease_by_note_id=starting_ease_by_note_id,
        )
        if lifecycle_plan is None:
            flush_review_analytics_deltas(db.session)
            db.session.commit()
            return 0
        deleted_count = len(lifecycle_plan.removed_card_ids)
        study_progress_lifecycle_mirror_service.finalize_note_authority_reset(
            lifecycle_plan,
            source_path="deck.progress_reset",
            operation_key=f"deck-reset:{deck_obj.id}:user:{user_id}",
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    return deleted_count
