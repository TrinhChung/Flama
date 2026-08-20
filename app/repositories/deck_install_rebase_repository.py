"""Persistence helpers for applying published deck releases to clone installs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, case, exists, false, func, or_

from models import db
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
from models.deck_install_rebase_conflict import DeckInstallRebaseConflict
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange


ACTIVE_REBASE_STATUSES = {"prepared", "has_conflict", "ready"}


@dataclass(frozen=True)
class CollapsedReleaseChange:
    """A range-level change projected from the first and last atomic events."""

    id: int
    release_id: str
    release_sequence_no: int
    change_key: str
    entity_kind: str
    entity_id: str
    field_def_id: str | None
    property_key: str
    operation: str
    before_value: Any
    after_value: Any
    before_hash: str | None
    after_hash: str | None
    source_deck_id: int | None
    sort_key: str


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


def list_rebase_conflicts_page(
    *,
    rebase_id: str,
    after_id: int | None,
    limit: int,
) -> list[DeckInstallRebaseConflict]:
    query = DeckInstallRebaseConflict.query.filter_by(rebase_id=rebase_id)
    if after_id is not None:
        query = query.filter(DeckInstallRebaseConflict.id > int(after_id))
    return query.order_by(DeckInstallRebaseConflict.id.asc()).limit(limit).all()


def has_unresolved_rebase_conflicts(*, rebase_id: str) -> bool:
    return (
        db.session.query(DeckInstallRebaseConflict.id)
        .filter(
            DeckInstallRebaseConflict.rebase_id == rebase_id,
            DeckInstallRebaseConflict.resolution_mode.is_(None),
        )
        .limit(1)
        .first()
        is not None
    )


def list_rebase_conflicts_for_keys(
    *,
    rebase_id: str,
    conflict_keys: set[str],
) -> list[DeckInstallRebaseConflict]:
    rows: list[DeckInstallRebaseConflict] = []
    normalized_keys = sorted({str(key) for key in conflict_keys if key})
    for offset in range(0, len(normalized_keys), 500):
        rows.extend(
            DeckInstallRebaseConflict.query.filter(
                DeckInstallRebaseConflict.rebase_id == rebase_id,
                DeckInstallRebaseConflict.conflict_key.in_(
                    normalized_keys[offset : offset + 500]
                ),
            ).all()
        )
    return rows


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


def _collapsed_release_changes_selectable(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
):
    """Return one effective row per ``change_key`` for a release range.

    Window functions keep the collapse inside the database: the first event
    provides the base value and the last event provides the upstream value.
    Keys whose final state equals their initial state are removed using the
    persisted content hashes, including the common add-then-remove case.
    """

    ranked = (
        db.session.query(
            DeckReleaseChange.id.label("id"),
            DeckReleaseChange.release_id.label("release_id"),
            DeckReleaseChange.release_sequence_no.label("release_sequence_no"),
            DeckReleaseChange.change_key.label("change_key"),
            DeckReleaseChange.entity_kind.label("entity_kind"),
            DeckReleaseChange.entity_id.label("entity_id"),
            DeckReleaseChange.field_def_id.label("field_def_id"),
            DeckReleaseChange.property_key.label("property_key"),
            DeckReleaseChange.operation.label("operation"),
            DeckReleaseChange.before_value.label("before_value"),
            DeckReleaseChange.after_value.label("after_value"),
            DeckReleaseChange.before_hash.label("before_hash"),
            DeckReleaseChange.after_hash.label("after_hash"),
            DeckReleaseChange.source_deck_id.label("source_deck_id"),
            DeckReleaseChange.sort_key.label("sort_key"),
            func.row_number()
            .over(
                partition_by=DeckReleaseChange.change_key,
                order_by=(
                    DeckReleaseChange.release_sequence_no.asc(),
                    DeckReleaseChange.id.asc(),
                ),
            )
            .label("first_rank"),
            func.row_number()
            .over(
                partition_by=DeckReleaseChange.change_key,
                order_by=(
                    DeckReleaseChange.release_sequence_no.desc(),
                    DeckReleaseChange.id.desc(),
                ),
            )
            .label("last_rank"),
        )
        .join(DeckRelease, DeckRelease.id == DeckReleaseChange.release_id)
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no > int(after_sequence),
            DeckReleaseChange.release_sequence_no <= int(through_sequence),
        )
        .cte("ranked_release_changes")
    )
    first = ranked.alias("first_change")
    last = ranked.alias("last_change")
    before_exists = first.c.operation != "add"
    after_exists = last.c.operation != "remove"
    hashes_differ_or_unknown = or_(
        first.c.before_hash.is_(None),
        last.c.after_hash.is_(None),
        first.c.before_hash != last.c.after_hash,
    )
    changed = or_(
        and_(~before_exists, after_exists),
        and_(before_exists, ~after_exists),
        and_(before_exists, after_exists, hashes_differ_or_unknown),
    )
    effective_operation = case(
        (and_(~before_exists, after_exists), "add"),
        (and_(before_exists, ~after_exists), "remove"),
        else_="set",
    )
    return (
        db.session.query(
            last.c.id.label("id"),
            last.c.release_id.label("release_id"),
            last.c.release_sequence_no.label("release_sequence_no"),
            last.c.change_key.label("change_key"),
            last.c.entity_kind.label("entity_kind"),
            last.c.entity_id.label("entity_id"),
            last.c.field_def_id.label("field_def_id"),
            last.c.property_key.label("property_key"),
            effective_operation.label("operation"),
            first.c.before_value.label("before_value"),
            last.c.after_value.label("after_value"),
            first.c.before_hash.label("before_hash"),
            last.c.after_hash.label("after_hash"),
            last.c.source_deck_id.label("source_deck_id"),
            last.c.sort_key.label("sort_key"),
        )
        .select_from(
            first.join(
                last,
                and_(
                    first.c.change_key == last.c.change_key,
                    first.c.first_rank == 1,
                    last.c.last_rank == 1,
                ),
            )
        )
        .filter(changed)
        .subquery("collapsed_release_changes")
    )


def summarize_effective_release_changes(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
) -> dict[str, int]:
    """Aggregate the exact final-state diff without loading range rows."""

    collapsed = _collapsed_release_changes_selectable(
        deck_item_id=deck_item_id,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
    )
    annotated = db.session.query(
        collapsed.c.id,
        collapsed.c.operation,
        func.row_number()
        .over(
            partition_by=(
                collapsed.c.entity_kind,
                collapsed.c.entity_id,
            ),
            order_by=(
                collapsed.c.release_sequence_no.asc(),
                collapsed.c.id.asc(),
            ),
        )
        .label("entity_rank"),
    ).subquery("annotated_collapsed_release_changes")
    totals = db.session.query(
        func.count(annotated.c.id),
        func.coalesce(
            func.sum(case((annotated.c.operation == "add", 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((annotated.c.operation == "set", 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((annotated.c.operation == "remove", 1), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((annotated.c.entity_rank == 1, 1), else_=0)),
            0,
        ),
    ).one()
    return {
        "change_count": int(totals[0] or 0),
        "entity_count": int(totals[4] or 0),
        "added_count": int(totals[1] or 0),
        "modified_count": int(totals[2] or 0),
        "removed_count": int(totals[3] or 0),
    }


def list_effective_release_changes_page(
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
) -> list[CollapsedReleaseChange]:
    """Page exact range-level changes using the last event as cursor anchor."""

    collapsed = _collapsed_release_changes_selectable(
        deck_item_id=deck_item_id,
        after_sequence=after_sequence,
        through_sequence=through_sequence,
    )
    query = db.session.query(collapsed)
    if entity_kind:
        query = query.filter(collapsed.c.entity_kind == entity_kind)
    if operation == "__conflict__":
        query = query.filter(false())
    elif operation:
        query = query.filter(collapsed.c.operation == operation)
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
                func.lower(collapsed.c.change_key).like(like_value, escape="\\"),
                func.lower(collapsed.c.entity_id).like(like_value, escape="\\"),
                func.lower(collapsed.c.property_key).like(like_value, escape="\\"),
                func.lower(collapsed.c.sort_key).like(like_value, escape="\\"),
            )
        )
    if cursor_sequence is not None and cursor_id is not None:
        query = query.filter(
            or_(
                collapsed.c.release_sequence_no > cursor_sequence,
                and_(
                    collapsed.c.release_sequence_no == cursor_sequence,
                    collapsed.c.id > cursor_id,
                ),
            )
        )
    rows = (
        query.order_by(
            collapsed.c.release_sequence_no.asc(),
            collapsed.c.id.asc(),
        )
        .limit(limit)
        .all()
    )
    return [CollapsedReleaseChange(**dict(row._mapping)) for row in rows]


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
    deck_install_id: str,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
    include_field_order: bool,
) -> list[DeckReleaseChange]:
    overlap_filters = [
        and_(
            DeckReleaseChange.entity_kind == "note_field",
            exists().where(
                DeckCloneNoteFieldOverride.deck_install_id == deck_install_id,
                DeckCloneNoteFieldOverride.source_note_id
                == DeckReleaseChange.entity_id,
            ),
        ),
        and_(
            DeckReleaseChange.entity_kind == "field_def",
            exists().where(
                DeckCloneFieldDefOverride.deck_install_id == deck_install_id,
                or_(
                    DeckCloneFieldDefOverride.source_field_def_id
                    == DeckReleaseChange.entity_id,
                    DeckCloneFieldDefOverride.source_field_def_id
                    == DeckReleaseChange.field_def_id,
                ),
            ),
        ),
    ]
    if include_field_order:
        overlap_filters.append(DeckReleaseChange.entity_kind == "field_order")
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
