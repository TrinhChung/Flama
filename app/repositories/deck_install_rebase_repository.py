"""Persistence helpers for applying published deck releases to clone installs."""

from __future__ import annotations

from sqlalchemy import and_, false, func, or_

from models import db
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange


ACTIVE_REBASE_STATUSES = {"prepared", "has_conflict", "ready"}


def get_install_for_user(
    install_id: str,
    *,
    user_id: int,
    for_update: bool = False,
) -> DeckInstall | None:
    query = DeckInstall.query.filter_by(id=install_id, user_id=user_id)
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_release_for_install(
    install: DeckInstall,
    release_id: str,
) -> DeckRelease | None:
    return DeckRelease.query.filter_by(
        id=release_id,
        deck_item_id=install.deck_item_id,
        status="published",
    ).first()


def get_rebase_for_user(
    rebase_id: str,
    *,
    user_id: int,
    for_update: bool = False,
) -> DeckInstallRebase | None:
    query = (
        DeckInstallRebase.query.join(
            DeckInstall,
            DeckInstall.id == DeckInstallRebase.deck_install_id,
        )
        .filter(
            DeckInstallRebase.id == rebase_id,
            DeckInstall.user_id == user_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


def find_idempotent_rebase(
    *,
    install_id: str,
    idempotency_key: str,
) -> DeckInstallRebase | None:
    if not idempotency_key:
        return None
    return DeckInstallRebase.query.filter_by(
        deck_install_id=install_id,
        idempotency_key=idempotency_key,
    ).first()


def mark_other_active_rebases_stale(
    *,
    install_id: str,
    except_rebase_id: str | None = None,
) -> None:
    query = DeckInstallRebase.query.filter(
        DeckInstallRebase.deck_install_id == install_id,
        DeckInstallRebase.status.in_(ACTIVE_REBASE_STATUSES),
    )
    if except_rebase_id:
        query = query.filter(DeckInstallRebase.id != except_rebase_id)
    query.update(
        {DeckInstallRebase.status: "stale"},
        synchronize_session=False,
    )


def release_changes_query(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
):
    return (
        DeckReleaseChange.query.join(
            DeckRelease,
            DeckRelease.id == DeckReleaseChange.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no > int(after_sequence),
            DeckReleaseChange.release_sequence_no <= int(through_sequence),
        )
    )


def count_release_changes(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
) -> int:
    return int(
        release_changes_query(
            deck_item_id=deck_item_id,
            after_sequence=after_sequence,
            through_sequence=through_sequence,
        ).count()
    )


def list_release_changes_page(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
    cursor_sequence: int | None,
    cursor_id: int | None,
    limit: int,
    entity_kind: str | None = None,
    operation: str | None = None,
    query_text: str | None = None,
) -> list[DeckReleaseChange]:
    query = release_changes_query(
        deck_item_id=deck_item_id,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
    )
    if entity_kind:
        query = query.filter(DeckReleaseChange.entity_kind == entity_kind)
    if operation == "__conflict__":
        query = query.filter(false())
    elif operation:
        query = query.filter(DeckReleaseChange.operation == operation)
    normalized_query = str(query_text or "").strip().lower()
    if normalized_query:
        escaped = (
            normalized_query.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        like_value = f"%{escaped}%"
        query = query.filter(
            or_(
                func.lower(DeckReleaseChange.change_key).like(like_value, escape="\\"),
                func.lower(DeckReleaseChange.entity_id).like(like_value, escape="\\"),
                func.lower(DeckReleaseChange.property_key).like(like_value, escape="\\"),
                func.lower(DeckReleaseChange.sort_key).like(like_value, escape="\\"),
            )
        )
    if cursor_sequence is not None and cursor_id is not None:
        query = query.filter(
            or_(
                DeckReleaseChange.release_sequence_no > cursor_sequence,
                and_(
                    DeckReleaseChange.release_sequence_no == cursor_sequence,
                    DeckReleaseChange.id > cursor_id,
                ),
            )
        )
    return (
        query.order_by(
            DeckReleaseChange.release_sequence_no.asc(),
            DeckReleaseChange.id.asc(),
        )
        .limit(limit)
        .all()
    )


def list_overlapping_release_changes(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
    note_ids: set[str],
    field_def_ids: set[str],
    include_field_order: bool,
) -> list[DeckReleaseChange]:
    overlap_filters = []
    if note_ids:
        overlap_filters.append(
            and_(
                DeckReleaseChange.entity_kind == "note_field",
                DeckReleaseChange.entity_id.in_(sorted(note_ids)),
            )
        )
    if field_def_ids:
        overlap_filters.append(
            and_(
                DeckReleaseChange.entity_kind == "field_def",
                or_(
                    DeckReleaseChange.entity_id.in_(sorted(field_def_ids)),
                    DeckReleaseChange.field_def_id.in_(sorted(field_def_ids)),
                ),
            )
        )
    if include_field_order:
        overlap_filters.append(DeckReleaseChange.entity_kind == "field_order")
    if not overlap_filters:
        return []
    return (
        release_changes_query(
            deck_item_id=deck_item_id,
            after_sequence=after_sequence,
            through_sequence=through_sequence,
        )
        .filter(or_(*overlap_filters))
        .order_by(
            DeckReleaseChange.release_sequence_no.asc(),
            DeckReleaseChange.id.asc(),
        )
        .all()
    )
