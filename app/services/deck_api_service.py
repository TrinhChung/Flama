"""Application service for versioned deck mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.repositories import flashcards_share_repository, vocabulary_repository
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services import deck_management_service, flashcards_share_service
from models import db
from models.deck import Deck


class DeckApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field


@dataclass(frozen=True)
class DeckCreateResult:
    created_count: int
    created_names: list[str]
    path_tokens: list[str]
    final_deck: Deck | None


@dataclass(frozen=True)
class DeckUpdateResult:
    changed: bool
    deck: Deck


def create_deck(
    *,
    payload: dict[str, Any],
    user_id: int,
    admin_mode: bool,
) -> DeckCreateResult:
    parent_id_raw = str(payload.get("parent_id") or "").strip()
    deck_path_raw = str(
        payload.get("path") or payload.get("deck_path") or ""
    ).strip()
    deck_name = str(payload.get("name") or "").strip() or "New Deck"

    parent_resolution = vocabulary_repository.resolve_create_deck_parent(
        parent_id_raw=parent_id_raw,
        user_id=user_id,
        admin_mode=admin_mode,
    )
    if parent_resolution.error:
        raise DeckApiError(
            "VALIDATION_ERROR",
            parent_resolution.error,
            status=400,
            field="parent_id",
        )

    path_tokens = vocabulary_repository.parse_create_deck_tokens(
        deck_path_raw=deck_path_raw,
        fallback_name=deck_name,
    )
    path_tokens = vocabulary_repository.normalize_create_deck_tokens_for_parent(
        path_tokens=path_tokens,
        parent_path_tokens=vocabulary_repository.deck_name_path_tokens(
            parent_resolution.parent_deck
        ),
        fallback_name=deck_name,
    )
    note_type_id_raw = payload.get("note_type_id")
    note_type_id: str | None = (
        str(note_type_id_raw).strip()
        if note_type_id_raw is not None and str(note_type_id_raw).strip()
        else None
    )

    if not note_type_id and parent_resolution.parent_deck:
        if parent_resolution.parent_deck.note_type_id:
            note_type_id = str(parent_resolution.parent_deck.note_type_id)
        else:
            existing_nt_ids = flashcards_share_repository.get_note_type_ids_for_user_deck_notes(
                parent_resolution.parent_deck.id, user_id
            )
            if existing_nt_ids and len(existing_nt_ids) == 1:
                note_type_id = next(iter(existing_nt_ids))

    if note_type_id:
        from models.note_type import NoteType
        from models.note_type_install import NoteTypeInstall

        nt_query = NoteType.query.filter(NoteType.id == note_type_id)
        if not admin_mode:
            installed_ids = [
                r[0]
                for r in db.session.query(
                    NoteTypeInstall.installed_note_type_id
                )
                .filter_by(user_id=user_id)
                .all()
                if r[0]
            ]
            nt_query = nt_query.filter(
                (NoteType.user_id == user_id)
                | (NoteType.id.in_(installed_ids))
            )
        if not nt_query.first():
            raise DeckApiError(
                "VALIDATION_ERROR",
                "Invalid note_type_id.",
                status=400,
                field="note_type_id",
            )

    try:
        result = vocabulary_repository.upsert_deck_path(
            parent_id=parent_resolution.parent_id,
            path_tokens=path_tokens,
            owner_user_id=user_id,
            admin_mode=admin_mode,
            note_type_id=note_type_id,
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise DeckApiError(
            "DB_ERROR",
            "Could not create the deck.",
            status=500,
        ) from exc
    return DeckCreateResult(
        created_count=int(result.created_count),
        created_names=list(result.created_names),
        path_tokens=list(result.path_tokens),
        final_deck=result.final_deck,
    )


def update_deck(
    *,
    deck_id: int,
    payload: dict[str, Any],
) -> DeckUpdateResult:
    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.deleted_at is not None:
        raise DeckApiError(
            "NOT_FOUND",
            "Deck not found.",
            status=404,
        )

    changed = False
    if "name" in payload:
        new_name = str(payload.get("name") or "").strip()
        if not new_name:
            raise DeckApiError(
                "VALIDATION_ERROR",
                "Deck name is required.",
                status=400,
                field="name",
            )
        if vocabulary_repository.deck_name_exists_under_parent(
            parent_id=deck.parent_id,
            name=new_name,
            exclude_deck_id=deck.id,
        ):
            raise DeckApiError(
                "CONFLICT",
                "A deck with this name already exists at the selected level.",
                status=409,
                field="name",
            )
        if new_name != deck.name:
            deck.name = new_name
            changed = True

    if "parent_id" in payload:
        new_parent_id = _parse_parent_id(payload.get("parent_id"))
        new_parent = (
            db.session.get(Deck, new_parent_id) if new_parent_id else None
        )
        if new_parent_id is not None and (
            new_parent is None or new_parent.deleted_at is not None
        ):
            raise DeckApiError(
                "NOT_FOUND",
                "Parent deck not found.",
                status=404,
            )

        cursor = new_parent
        while cursor is not None:
            if cursor.id == deck.id:
                raise DeckApiError(
                    "VALIDATION_ERROR",
                    "A deck cannot be moved into itself or its descendants.",
                    status=400,
                    field="parent_id",
                )
            cursor = cursor.parent

        if vocabulary_repository.deck_name_exists_under_parent(
            parent_id=new_parent_id,
            name=deck.name,
            exclude_deck_id=deck.id,
        ):
            raise DeckApiError(
                "CONFLICT",
                "The destination already contains a deck with this name.",
                status=409,
                field="parent_id",
            )
        if deck.parent_id != new_parent_id:
            guard_error = (
                flashcards_share_service.validate_deck_subtree_move_to_parent(
                    deck_id=deck.id,
                    new_parent_id=new_parent_id,
                    user_id=deck.owner_user_id,
                )
            )
            if guard_error:
                raise DeckApiError(
                    "CONFLICT",
                    guard_error,
                    status=409,
                    field="parent_id",
                )
            deck.parent_id = new_parent_id
            deck.position = vocabulary_repository.next_deck_position(
                new_parent_id
            )
            changed = True

    if not changed:
        return DeckUpdateResult(changed=False, deck=deck)
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise DeckApiError(
            "DB_ERROR",
            "Could not update the deck.",
            status=500,
        ) from exc
    return DeckUpdateResult(changed=True, deck=deck)


def delete_deck(
    *,
    deck_id: int,
    user_id: int,
    admin_mode: bool,
    purge: bool = False,
) -> str:
    deck = _owned_deck_or_error(
        deck_id=deck_id,
        user_id=user_id,
        admin_mode=admin_mode,
        action="delete",
    )
    try:
        return deck_management_service.delete_deck_subtree(
            deck_obj=deck,
            user_id=user_id,
            is_admin=admin_mode,
            purge=purge,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise DeckApiError(exc.code, str(exc), status=409) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise DeckApiError(
            "DB_ERROR",
            "Could not delete the deck.",
            status=500,
        ) from exc


def reset_deck_progress(
    *,
    deck_id: int,
    user_id: int,
    admin_mode: bool,
) -> int:
    deck = _owned_deck_or_error(
        deck_id=deck_id,
        user_id=user_id,
        admin_mode=admin_mode,
        action="reset",
    )
    try:
        return int(
            deck_management_service.reset_deck_progress(
                deck_obj=deck,
                user_id=user_id,
            )
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise DeckApiError(exc.code, str(exc), status=409) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise DeckApiError(
            "DB_ERROR",
            "Could not reset deck progress.",
            status=500,
        ) from exc


def default_note_type_id(*, deck_id: int, user_id: int, admin_mode: bool) -> str | None:
    """Note type a new sub-deck of ``deck_id`` inherits, as the dashboard chose it.

    The deck's own note type, else the type of its oldest owned Note, else its
    logical-overlay install's source type (not for admins). Read on demand by
    the create-deck dialog instead of for every deck on each dashboard load.
    """
    from app.repositories.deck_tree_query import collect_accessible_decks
    from app.services.deck_aggregation_service import deck_note_type_metadata

    deck = next((item for item in collect_accessible_decks(user_id=user_id, admin_mode=admin_mode)
                 if item.id == deck_id), None)
    if deck is None:
        raise DeckApiError("NOT_FOUND", "Deck not found.", status=404)
    if deck.note_type_id:
        return str(deck.note_type_id)
    return deck_note_type_metadata(
        db.session, learner_user_id=user_id, deck_ids=[deck_id], admin_mode=admin_mode,
    ).get(deck_id)


def _parse_parent_id(raw_parent_id: Any) -> int | None:
    if raw_parent_id in (None, ""):
        return None
    try:
        return int(raw_parent_id)
    except (TypeError, ValueError) as exc:
        raise DeckApiError(
            "VALIDATION_ERROR",
            "parent_id must be an integer or null.",
            status=400,
            field="parent_id",
        ) from exc


def _owned_deck_or_error(
    *,
    deck_id: int,
    user_id: int,
    admin_mode: bool,
    action: str,
) -> Deck:
    deck = db.session.get(Deck, deck_id)
    if deck is None or deck.deleted_at is not None:
        raise DeckApiError(
            "NOT_FOUND",
            "Deck not found.",
            status=404,
        )
    permitted = bool(
        admin_mode
        or deck.owner_user_id == user_id
        or vocabulary_repository.can_user_delete_cloned_deck(
            deck_obj=deck,
            user_id=user_id,
        )
    )
    if not permitted:
        raise DeckApiError(
            "FORBIDDEN",
            f"You cannot {action} this deck.",
            status=403,
        )
    return deck
