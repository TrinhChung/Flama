"""Persistence helpers for immutable shared-deck releases.

This module intentionally contains no transaction boundaries.  Callers may
flush while building a release, but the HTTP adapter owns commit/rollback.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import islice
from typing import Any

from sqlalchemy import and_, func, insert, or_, select
from sqlalchemy.orm import load_only

from app.repositories.deck_tree_query import collect_subtree_ids
from models import db
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note


def get_deck_item(
    deck_item_id: str,
    *,
    for_update: bool = False,
) -> DeckMarketplaceItem | None:
    query = DeckMarketplaceItem.query.filter_by(id=deck_item_id)
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_release(release_id: str) -> DeckRelease | None:
    return db.session.get(DeckRelease, release_id)


def get_release_for_item(
    *,
    deck_item_id: str,
    release_id: str,
) -> DeckRelease | None:
    return DeckRelease.query.filter_by(
        id=release_id,
        deck_item_id=deck_item_id,
    ).first()


def get_release_by_idempotency_key(
    *,
    deck_item_id: str,
    idempotency_key: str,
) -> DeckRelease | None:
    return DeckRelease.query.filter_by(
        deck_item_id=deck_item_id,
        idempotency_key=idempotency_key,
    ).first()


def get_release_by_version_label(
    *,
    deck_item_id: str,
    version_label: str,
) -> DeckRelease | None:
    return DeckRelease.query.filter_by(
        deck_item_id=deck_item_id,
        version_label=version_label,
    ).first()


def next_release_sequence(deck_item_id: str) -> int:
    current_max = (
        db.session.query(func.max(DeckRelease.sequence_no))
        .filter(DeckRelease.deck_item_id == deck_item_id)
        .scalar()
    )
    return int(current_max or 0) + 1


def list_releases(
    *,
    deck_item_id: str,
    before_sequence: int | None,
    limit: int,
    published_only: bool,
) -> tuple[list[DeckRelease], bool]:
    query = DeckRelease.query.filter(DeckRelease.deck_item_id == deck_item_id)
    if published_only:
        query = query.filter(DeckRelease.status == "published")
    if before_sequence is not None:
        query = query.filter(DeckRelease.sequence_no < before_sequence)
    rows = (
        query.order_by(DeckRelease.sequence_no.desc(), DeckRelease.id.desc())
        .limit(limit + 1)
        .all()
    )
    return rows[:limit], len(rows) > limit


def list_source_notes(deck_item: DeckMarketplaceItem) -> list[Note]:
    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids or not deck_item.source_note_type_id:
        return []
    return (
        Note.query.filter(
            Note.deck_id.in_(deck_ids),
            Note.note_type_id == deck_item.source_note_type_id,
            Note.user_id == deck_item.owner_user_id,
        )
        .order_by(Note.deck_id.asc(), Note.id.asc())
        .all()
    )


def list_source_field_defs(deck_item: DeckMarketplaceItem) -> list[FieldDef]:
    if not deck_item.source_note_type_id:
        return []
    return (
        FieldDef.query.filter_by(note_type_id=deck_item.source_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.id.asc())
        .all()
    )


def count_source_notes(deck_item: DeckMarketplaceItem) -> int:
    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids or not deck_item.source_note_type_id:
        return 0
    return int(
        Note.query.filter(
            Note.deck_id.in_(deck_ids),
            Note.note_type_id == deck_item.source_note_type_id,
            Note.user_id == deck_item.owner_user_id,
        ).count()
    )


def has_legacy_install_without_release(deck_item_id: str) -> bool:
    return (
        db.session.query(DeckInstall.id)
        .filter(
            DeckInstall.deck_item_id == deck_item_id,
            DeckInstall.applied_release_id.is_(None),
        )
        .limit(1)
        .first()
        is not None
    )


def list_notes_by_ids(note_ids: Iterable[str]) -> list[Note]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    return Note.query.filter(Note.id.in_(normalized_ids)).all()


def list_field_defs_by_ids(field_def_ids: Iterable[str]) -> list[FieldDef]:
    normalized_ids = sorted(
        {str(field_def_id) for field_def_id in field_def_ids if field_def_id}
    )
    if not normalized_ids:
        return []
    return FieldDef.query.filter(FieldDef.id.in_(normalized_ids)).all()


def list_working_dirty_entities(
    deck_item_id: str,
    *,
    entity_kind: str | None = None,
    content_only: bool = False,
) -> list[DeckWorkingDirtyEntity]:
    query = DeckWorkingDirtyEntity.query.filter_by(deck_item_id=deck_item_id)
    if entity_kind is not None:
        query = query.filter_by(entity_kind=entity_kind)
    if content_only:
        query = query.options(load_only(
            DeckWorkingDirtyEntity.id, DeckWorkingDirtyEntity.entity_kind,
            DeckWorkingDirtyEntity.entity_id, DeckWorkingDirtyEntity.field_def_id,
            DeckWorkingDirtyEntity.property_key, DeckWorkingDirtyEntity.operation,
            DeckWorkingDirtyEntity.current_hash, DeckWorkingDirtyEntity.source_deck_id,
            DeckWorkingDirtyEntity.working_revision,
        ))
    return query.order_by(DeckWorkingDirtyEntity.id.asc()).all()


def _latest_note_checkpoint_sequences(deck_item_id: str, through_sequence: int):
    return (
        select(
            DeckReleaseNoteCheckpoint.source_note_id.label("note_id"),
            func.max(DeckReleaseNoteCheckpoint.release_sequence_no).label("sequence_no"),
        )
        .join(DeckRelease, DeckRelease.id == DeckReleaseNoteCheckpoint.release_id)
        .where(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseNoteCheckpoint.release_sequence_no <= through_sequence,
        )
        .group_by(DeckReleaseNoteCheckpoint.source_note_id)
        .subquery()
    )


def list_release_history_changes(
    *,
    deck_item_id: str,
    through_sequence: int,
    entity_kinds: Iterable[str] | None = None,
    content_only: bool = False,
    after_checkpoints: bool = False,
) -> list[DeckReleaseChange]:
    query = (
        DeckReleaseChange.query.join(
            DeckRelease,
            DeckRelease.id == DeckReleaseChange.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no <= through_sequence,
        )
    )
    normalized_kinds = [str(value) for value in (entity_kinds or []) if value]
    if normalized_kinds:
        query = query.filter(DeckReleaseChange.entity_kind.in_(normalized_kinds))
    if after_checkpoints:
        # Reconstruction already starts from these snapshots. Keep all schema
        # atoms and history for notes without a checkpoint, including legacy
        # baselines; diff/history endpoints deliberately retain their atoms.
        latest = _latest_note_checkpoint_sequences(deck_item_id, through_sequence)
        query = query.outerjoin(latest, latest.c.note_id == DeckReleaseChange.entity_id).filter(
            or_(
                DeckReleaseChange.entity_kind != "note_field",
                DeckReleaseChange.release_sequence_no > func.coalesce(latest.c.sequence_no, 0),
            )
        )
    if content_only:
        query = query.options(load_only(
            DeckReleaseChange.id, DeckReleaseChange.release_sequence_no,
            DeckReleaseChange.entity_kind, DeckReleaseChange.entity_id,
            DeckReleaseChange.field_def_id, DeckReleaseChange.property_key,
            DeckReleaseChange.operation, DeckReleaseChange.after_value,
            DeckReleaseChange.source_deck_id,
        ))
    return query.order_by(
        DeckReleaseChange.release_sequence_no.asc(),
        DeckReleaseChange.id.asc(),
    ).all()


def list_release_changes_between(
    *,
    deck_item_id: str,
    after_sequence: int,
    through_sequence: int,
) -> list[DeckReleaseChange]:
    return (
        DeckReleaseChange.query.join(
            DeckRelease,
            DeckRelease.id == DeckReleaseChange.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no > after_sequence,
            DeckReleaseChange.release_sequence_no <= through_sequence,
        )
        .order_by(
            DeckReleaseChange.release_sequence_no.asc(),
            DeckReleaseChange.id.asc(),
        )
        .all()
    )


def list_note_checkpoints(
    *,
    deck_item_id: str,
    through_sequence: int,
) -> list[DeckReleaseNoteCheckpoint]:
    return (
        DeckReleaseNoteCheckpoint.query.join(
            DeckRelease,
            DeckRelease.id == DeckReleaseNoteCheckpoint.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseNoteCheckpoint.release_sequence_no <= through_sequence,
        )
        .order_by(
            DeckReleaseNoteCheckpoint.release_sequence_no.asc(),
            DeckReleaseNoteCheckpoint.id.asc(),
        )
        .all()
    )


def list_note_checkpoints_for_ids(
    *,
    deck_item_id: str,
    through_sequence: int,
    note_ids: Iterable[str],
    content_only: bool = False,
) -> list[DeckReleaseNoteCheckpoint]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    return (
        DeckReleaseNoteCheckpoint.query.options(*([load_only(
            DeckReleaseNoteCheckpoint.id, DeckReleaseNoteCheckpoint.source_note_id,
            DeckReleaseNoteCheckpoint.release_sequence_no, DeckReleaseNoteCheckpoint.field_values,
        )] if content_only else [])).join(
            DeckRelease,
            DeckRelease.id == DeckReleaseNoteCheckpoint.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseNoteCheckpoint.release_sequence_no <= through_sequence,
            DeckReleaseNoteCheckpoint.source_note_id.in_(normalized_ids),
        )
        .order_by(
            DeckReleaseNoteCheckpoint.release_sequence_no.asc(),
            DeckReleaseNoteCheckpoint.id.asc(),
        )
        .all()
    )


def list_note_field_history_for_ids(
    *,
    deck_item_id: str,
    through_sequence: int,
    note_ids: Iterable[str],
    content_only: bool = False,
    checkpoint_sequences: Mapping[str, int] | None = None,
) -> list[DeckReleaseChange]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    query = (
        DeckReleaseChange.query.options(*([load_only(
            DeckReleaseChange.id, DeckReleaseChange.release_sequence_no,
            DeckReleaseChange.entity_id, DeckReleaseChange.field_def_id,
            DeckReleaseChange.operation, DeckReleaseChange.after_value,
        )] if content_only else [])).join(
            DeckRelease,
            DeckRelease.id == DeckReleaseChange.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no <= through_sequence,
            DeckReleaseChange.entity_kind == "note_field",
            DeckReleaseChange.entity_id.in_(normalized_ids),
        )
    )
    if checkpoint_sequences is not None:
        groups: dict[int, list[str]] = {}
        for note_id in normalized_ids:
            groups.setdefault(checkpoint_sequences.get(note_id, 0), []).append(note_id)
        earliest = min(groups)
        # Release and atom sequences are written together by the publisher.
        # Bounding the release join avoids rescanning baseline atoms for each
        # 500-note chunk. Missing checkpoints retain the complete history.
        query = query.filter(
            DeckRelease.sequence_no > earliest,
            DeckReleaseChange.release_sequence_no > earliest,
        )
        if len(groups) > 1:
            query = query.filter(or_(*(
                and_(
                    DeckReleaseChange.entity_id.in_(ids),
                    DeckReleaseChange.release_sequence_no > sequence,
                )
                for sequence, ids in groups.items()
            )))
    return query.order_by(
        DeckReleaseChange.release_sequence_no.asc(),
        DeckReleaseChange.id.asc(),
    ).all()


def list_note_ids_at_release(
    *, deck_item_id: str, sequence_no: int, limit: int,
) -> list[str]:
    return [str(row[0]) for row in (
        db.session.query(DeckReleaseEntityMembership.entity_id)
        .filter(
            DeckReleaseEntityMembership.deck_item_id == deck_item_id,
            DeckReleaseEntityMembership.entity_kind == "note",
            DeckReleaseEntityMembership.introduced_sequence <= sequence_no,
            or_(DeckReleaseEntityMembership.removed_sequence.is_(None),
                DeckReleaseEntityMembership.removed_sequence > sequence_no),
        )
        .order_by(DeckReleaseEntityMembership.entity_id.asc())
        .limit(limit)
        .all()
    )]


def list_memberships(deck_item_id: str) -> list[DeckReleaseEntityMembership]:
    return (
        DeckReleaseEntityMembership.query.filter_by(deck_item_id=deck_item_id)
        .order_by(
            DeckReleaseEntityMembership.entity_kind.asc(),
            DeckReleaseEntityMembership.entity_id.asc(),
        )
        .all()
    )


def list_memberships_for_entities(
    *,
    deck_item_id: str,
    entity_kind: str,
    entity_ids: Iterable[str] | None = None,
) -> list[DeckReleaseEntityMembership]:
    query = DeckReleaseEntityMembership.query.filter_by(
        deck_item_id=deck_item_id,
        entity_kind=entity_kind,
    )
    if entity_ids is not None:
        normalized_ids = sorted(
            {str(entity_id) for entity_id in entity_ids if entity_id}
        )
        if not normalized_ids:
            return []
        query = query.filter(
            DeckReleaseEntityMembership.entity_id.in_(normalized_ids)
        )
    return query.order_by(DeckReleaseEntityMembership.entity_id.asc()).all()


def list_release_changes_page(
    *,
    release_id: str,
    after_id: int | None,
    limit: int,
    entity_kind: str | None,
    operation: str | None,
    source_deck_id: int | None,
    query_text: str | None,
) -> tuple[list[DeckReleaseChange], bool]:
    query = DeckReleaseChange.query.filter(
        DeckReleaseChange.release_id == release_id
    )
    if after_id is not None:
        query = query.filter(DeckReleaseChange.id > after_id)
    if entity_kind:
        query = query.filter(DeckReleaseChange.entity_kind == entity_kind)
    if operation:
        query = query.filter(DeckReleaseChange.operation == operation)
    if source_deck_id is not None:
        query = query.filter(DeckReleaseChange.source_deck_id == source_deck_id)
    normalized_query = (query_text or "").strip()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        query = query.filter(
            or_(
                DeckReleaseChange.change_key.ilike(pattern),
                DeckReleaseChange.entity_id.ilike(pattern),
                DeckReleaseChange.property_key.ilike(pattern),
            )
        )
    rows = query.order_by(DeckReleaseChange.id.asc()).limit(limit + 1).all()
    return rows[:limit], len(rows) > limit


def add_release(release: DeckRelease) -> None:
    db.session.add(release)


def add_release_changes(changes: Iterable[Mapping[str, Any]]) -> None:
    # Change IDs are not consumed while publishing. Core executemany avoids
    # one INSERT/lastrowid round trip per ORM object on MySQL. The caller still
    # owns the single release transaction, including all batches.
    rows = iter(changes)
    while batch := list(islice(rows, 500)):
        db.session.execute(insert(DeckReleaseChange.__table__), batch)


def add_note_checkpoints(
    checkpoints: Iterable[DeckReleaseNoteCheckpoint],
) -> None:
    db.session.add_all(list(checkpoints))


def add_membership(membership: DeckReleaseEntityMembership) -> None:
    db.session.add(membership)


def flush() -> None:
    db.session.flush()
