"""Persistence helpers for immutable shared-deck releases.

This module intentionally contains no transaction boundaries.  Callers may
flush while building a release, but the HTTP adapter owns commit/rollback.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from itertools import islice
from typing import Any

from sqlalchemy import func, insert, or_, select, update

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
        from app.services.note_base_context import published_base_enabled
        if published_base_enabled():
            query = query.populate_existing()
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


def list_source_notes(
    deck_item: DeckMarketplaceItem,
    *,
    content_only: bool = False,
    include_tags: bool = True,
) -> list[Any]:
    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids or not deck_item.source_note_type_id:
        return []
    if content_only:
        columns = [
            Note.id,
            Note.user_id,
            Note.deck_id,
            Note.note_type_id,
            Note.field_values_by_id,
            Note.field_values_codec,
            Note.field_values_extras,
        ]
        if include_tags:
            columns.append(Note.tags)
        return (
            db.session.query(*columns)
            .filter(
                Note.deck_id.in_(deck_ids),
                Note.note_type_id == deck_item.source_note_type_id,
                Note.user_id == deck_item.owner_user_id,
            )
            .order_by(Note.deck_id.asc(), Note.id.asc())
            .all()
        )
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


def list_notes_by_ids(
    note_ids: Iterable[str],
    *,
    content_only: bool = False,
) -> list[Any]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    if content_only:
        return (
            db.session.query(
                Note.id,
                Note.user_id,
                Note.deck_id,
                Note.note_type_id,
                Note.field_values_by_id,
                Note.field_values_codec,
                Note.field_values_extras,
            )
            .filter(Note.id.in_(normalized_ids))
            .all()
        )
    return Note.query.filter(Note.id.in_(normalized_ids)).all()


def list_field_defs_by_ids(field_def_ids: Iterable[str]) -> list[FieldDef]:
    normalized_ids = sorted(
        {str(field_def_id) for field_def_id in field_def_ids if field_def_id}
    )
    if not normalized_ids:
        return []
    return FieldDef.query.filter(FieldDef.id.in_(normalized_ids)).all()


def count_working_dirty_entities(
    deck_item_id: str,
    *,
    after_revision: int | None = None,
) -> int:
    query = db.session.query(func.count(DeckWorkingDirtyEntity.id)).filter(
        DeckWorkingDirtyEntity.deck_item_id == deck_item_id
    )
    if after_revision is not None:
        query = query.filter(DeckWorkingDirtyEntity.working_revision > after_revision)
    return int(query.scalar() or 0)


def list_working_dirty_entities(
    deck_item_id: str,
    *,
    entity_kind: str | None = None,
    content_only: bool = False,
    after_revision: int | None = None,
) -> list[Any]:
    if content_only:
        query = db.session.query(
            DeckWorkingDirtyEntity.id,
            DeckWorkingDirtyEntity.entity_kind,
            DeckWorkingDirtyEntity.entity_id,
            DeckWorkingDirtyEntity.field_def_id,
            DeckWorkingDirtyEntity.property_key,
            DeckWorkingDirtyEntity.operation,
            DeckWorkingDirtyEntity.current_hash,
            DeckWorkingDirtyEntity.source_deck_id,
            DeckWorkingDirtyEntity.working_revision,
        ).filter(DeckWorkingDirtyEntity.deck_item_id == deck_item_id)
        if entity_kind is not None:
            query = query.filter(DeckWorkingDirtyEntity.entity_kind == entity_kind)
        if after_revision is not None:
            query = query.filter(
                DeckWorkingDirtyEntity.working_revision > after_revision
            )
        return query.order_by(DeckWorkingDirtyEntity.id.asc()).all()
    query = DeckWorkingDirtyEntity.query.filter_by(deck_item_id=deck_item_id)
    if entity_kind is not None:
        query = query.filter_by(entity_kind=entity_kind)
    if after_revision is not None:
        query = query.filter(
            DeckWorkingDirtyEntity.working_revision > after_revision
        )
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


def _build_history_changes_query(*, content_only: bool):
    if content_only:
        return db.session.query(
            DeckReleaseChange.id,
            DeckReleaseChange.release_sequence_no,
            DeckReleaseChange.entity_kind,
            DeckReleaseChange.entity_id,
            DeckReleaseChange.field_def_id,
            DeckReleaseChange.property_key,
            DeckReleaseChange.operation,
            DeckReleaseChange.after_value,
            DeckReleaseChange.source_deck_id,
        )
    return DeckReleaseChange.query


def list_note_field_atoms_for_ids(
    *,
    deck_item_id: str,
    note_ids: Iterable[str],
    after_sequence: int,
    through_sequence: int,
    content_only: bool = False,
) -> list[Any]:
    """Load note-field atoms of the given Notes without joining ``deck_releases``.

    A join driven from ``deck_releases`` reads every atom of each release via
    ``ix_deck_release_changes_diff_cursor`` before filtering the Note IDs
    (162k rows for a 500-Note chunk of N1). Filtering by the deck's published
    release IDs lets MySQL range-scan ``ix_deck_release_changes_entity_history``
    by Note ID instead.
    """
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids or through_sequence <= after_sequence:
        return []
    release_ids = [
        str(row[0])
        for row in db.session.query(DeckRelease.id).filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckRelease.sequence_no > after_sequence,
            DeckRelease.sequence_no <= through_sequence,
        )
    ]
    if not release_ids:
        return []
    rows: list[Any] = []
    ids = iter(normalized_ids)
    while chunk := list(islice(ids, 500)):
        rows.extend(
            _build_history_changes_query(content_only=content_only)
            .filter(
                DeckReleaseChange.release_id.in_(release_ids),
                DeckReleaseChange.release_sequence_no > after_sequence,
                DeckReleaseChange.release_sequence_no <= through_sequence,
                DeckReleaseChange.entity_kind == "note_field",
                DeckReleaseChange.entity_id.in_(chunk),
            )
            .all()
        )
    rows.sort(key=lambda row: (int(row.release_sequence_no), int(row.id)))
    return rows


def list_release_history_changes(
    *,
    deck_item_id: str,
    through_sequence: int,
    entity_kinds: Iterable[str] | None = None,
    content_only: bool = False,
    after_checkpoints: bool = False,
    min_note_field_sequence: int | None = None,
    full_history_note_ids: Iterable[str] = (),
) -> list[Any]:
    normalized_kinds = [str(value) for value in (entity_kinds or []) if value]
    if (
        after_checkpoints
        and min_note_field_sequence is not None
        and (not normalized_kinds or "note_field" in normalized_kinds)
    ):
        # Split reconstruction: schema atoms, note atoms from the earliest
        # checkpoint onward, and the complete history of Notes without a
        # checkpoint. The caller drops atoms covered by each Note's own
        # checkpoint, so no per-note checkpoint join is needed here.
        min_note_seq = int(min_note_field_sequence)
        other_kinds = [
            kind for kind in normalized_kinds if kind != "note_field"
        ]
        rows: list[Any] = []
        if other_kinds or not normalized_kinds:
            other_query = (
                _build_history_changes_query(content_only=content_only)
                .join(
                    DeckRelease,
                    DeckRelease.id == DeckReleaseChange.release_id,
                )
                .filter(
                    DeckRelease.deck_item_id == deck_item_id,
                    DeckRelease.status == "published",
                    DeckReleaseChange.release_sequence_no <= through_sequence,
                )
            )
            if other_kinds:
                other_query = other_query.filter(
                    DeckReleaseChange.entity_kind.in_(other_kinds)
                )
            else:
                other_query = other_query.filter(
                    DeckReleaseChange.entity_kind != "note_field"
                )
            rows.extend(other_query.all())
        if min_note_seq <= through_sequence:
            # Bounding the release side keeps this join on the newer releases.
            rows.extend(
                _build_history_changes_query(content_only=content_only)
                .join(
                    DeckRelease,
                    DeckRelease.id == DeckReleaseChange.release_id,
                )
                .filter(
                    DeckRelease.deck_item_id == deck_item_id,
                    DeckRelease.status == "published",
                    DeckRelease.sequence_no >= min_note_seq,
                    DeckReleaseChange.release_sequence_no >= min_note_seq,
                    DeckReleaseChange.release_sequence_no <= through_sequence,
                    DeckReleaseChange.entity_kind == "note_field",
                )
                .all()
            )
        # Atoms at or after min_note_seq are already loaded above.
        rows.extend(
            list_note_field_atoms_for_ids(
                deck_item_id=deck_item_id,
                note_ids=full_history_note_ids,
                after_sequence=0,
                through_sequence=min(min_note_seq - 1, through_sequence),
                content_only=content_only,
            )
        )
        rows.sort(key=lambda row: (int(row.release_sequence_no), int(row.id)))
        return rows

    query = (
        _build_history_changes_query(content_only=content_only)
        .join(
            DeckRelease,
            DeckRelease.id == DeckReleaseChange.release_id,
        )
        .filter(
            DeckRelease.deck_item_id == deck_item_id,
            DeckRelease.status == "published",
            DeckReleaseChange.release_sequence_no <= through_sequence,
        )
    )
    if normalized_kinds:
        query = query.filter(DeckReleaseChange.entity_kind.in_(normalized_kinds))
    if after_checkpoints:
        # Reconstruction already starts from these snapshots. Keep all schema
        # atoms and history for notes without a checkpoint, including legacy
        # baselines; diff/history endpoints deliberately retain their atoms.
        latest = _latest_note_checkpoint_sequences(deck_item_id, through_sequence)
        query = query.outerjoin(
            latest,
            latest.c.note_id == DeckReleaseChange.entity_id,
        ).filter(
            or_(
                DeckReleaseChange.entity_kind != "note_field",
                DeckReleaseChange.release_sequence_no
                > func.coalesce(latest.c.sequence_no, 0),
            )
        )
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
    content_only: bool = False,
) -> list[Any]:
    if content_only:
        return (
            db.session.query(
                DeckReleaseNoteCheckpoint.id,
                DeckReleaseNoteCheckpoint.source_note_id,
                DeckReleaseNoteCheckpoint.source_deck_id,
                DeckReleaseNoteCheckpoint.note_type_id,
                DeckReleaseNoteCheckpoint.release_sequence_no,
                DeckReleaseNoteCheckpoint.field_values,
            )
            .join(
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
) -> list[Any]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    if content_only:
        return (
            db.session.query(
                DeckReleaseNoteCheckpoint.id,
                DeckReleaseNoteCheckpoint.source_note_id,
                DeckReleaseNoteCheckpoint.release_sequence_no,
                DeckReleaseNoteCheckpoint.field_values,
            )
            .join(
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
    return (
        DeckReleaseNoteCheckpoint.query.join(
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


def _build_note_field_history_query(*, content_only: bool):
    if content_only:
        return db.session.query(
            DeckReleaseChange.id,
            DeckReleaseChange.release_sequence_no,
            DeckReleaseChange.entity_id,
            DeckReleaseChange.field_def_id,
            DeckReleaseChange.operation,
            DeckReleaseChange.after_value,
        )
    return DeckReleaseChange.query


def list_note_field_history_for_ids(
    *,
    deck_item_id: str,
    through_sequence: int,
    note_ids: Iterable[str],
    content_only: bool = False,
    checkpoint_sequences: Mapping[str, int] | None = None,
) -> list[Any]:
    normalized_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not normalized_ids:
        return []
    groups: dict[int, list[str]] = {}
    for note_id in normalized_ids:
        seq = int((checkpoint_sequences or {}).get(note_id, 0))
        if seq >= through_sequence:
            continue
        groups.setdefault(seq, []).append(note_id)
    rows: list[Any] = []
    for sequence, ids in sorted(groups.items()):
        if sequence == 0:
            # Without a checkpoint the whole history is needed; a join from
            # deck_releases would read every atom of every release here.
            rows.extend(
                list_note_field_atoms_for_ids(
                    deck_item_id=deck_item_id,
                    note_ids=ids,
                    after_sequence=0,
                    through_sequence=through_sequence,
                    content_only=content_only,
                )
            )
            continue
        group_query = (
            _build_note_field_history_query(content_only=content_only)
            .join(
                DeckRelease,
                DeckRelease.id == DeckReleaseChange.release_id,
            )
            .filter(
                DeckRelease.deck_item_id == deck_item_id,
                DeckRelease.status == "published",
                DeckRelease.sequence_no > sequence,
                DeckReleaseChange.release_sequence_no > sequence,
                DeckReleaseChange.release_sequence_no <= through_sequence,
                DeckReleaseChange.entity_kind == "note_field",
                DeckReleaseChange.entity_id.in_(ids),
            )
        )
        rows.extend(group_query.all())
    rows.sort(key=lambda row: (int(row.release_sequence_no), int(row.id)))
    return rows


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


def list_memberships(
    deck_item_id: str,
    *,
    active_at_sequence: int | None = None,
    open_only: bool = False,
    content_only: bool = False,
) -> list[Any]:
    if content_only:
        query = db.session.query(
            DeckReleaseEntityMembership.id,
            DeckReleaseEntityMembership.entity_kind,
            DeckReleaseEntityMembership.entity_id,
            DeckReleaseEntityMembership.source_deck_id,
            DeckReleaseEntityMembership.introduced_sequence,
            DeckReleaseEntityMembership.removed_sequence,
            DeckReleaseEntityMembership.metadata_json,
        ).filter(DeckReleaseEntityMembership.deck_item_id == deck_item_id)
    else:
        query = DeckReleaseEntityMembership.query.filter_by(
            deck_item_id=deck_item_id
        )
    if open_only:
        query = query.filter(
            DeckReleaseEntityMembership.removed_sequence.is_(None)
        )
    elif active_at_sequence is not None:
        query = query.filter(
            DeckReleaseEntityMembership.introduced_sequence
            <= active_at_sequence,
            or_(
                DeckReleaseEntityMembership.removed_sequence.is_(None),
                DeckReleaseEntityMembership.removed_sequence
                > active_at_sequence,
            ),
        )
    return query.order_by(
        DeckReleaseEntityMembership.entity_kind.asc(),
        DeckReleaseEntityMembership.entity_id.asc(),
    ).all()


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
    checkpoints: Iterable[DeckReleaseNoteCheckpoint | Mapping[str, Any]],
) -> None:
    now = datetime.utcnow()
    rows = (
        dict(row)
        if isinstance(row, Mapping)
        else {
            "release_id": row.release_id,
            "release_sequence_no": int(row.release_sequence_no),
            "source_note_id": row.source_note_id,
            "source_deck_id": row.source_deck_id,
            "note_type_id": row.note_type_id,
            "field_values": row.field_values,
            "tags": row.tags,
            "content_hash": row.content_hash,
            "created_at": getattr(row, "created_at", None) or now,
        }
        for row in checkpoints
    )
    while batch := list(islice(rows, 500)):
        db.session.execute(insert(DeckReleaseNoteCheckpoint.__table__), batch)


def add_membership(membership: DeckReleaseEntityMembership) -> None:
    db.session.add(membership)


def add_memberships(
    memberships: Iterable[DeckReleaseEntityMembership | Mapping[str, Any]],
) -> None:
    now = datetime.utcnow()
    rows = (
        dict(row)
        if isinstance(row, Mapping)
        else {
            "deck_item_id": row.deck_item_id,
            "entity_kind": row.entity_kind,
            "entity_id": row.entity_id,
            "source_deck_id": row.source_deck_id,
            "introduced_sequence": int(row.introduced_sequence),
            "removed_sequence": row.removed_sequence,
            "metadata_json": row.metadata_json,
            "created_at": getattr(row, "created_at", None) or now,
            "updated_at": getattr(row, "updated_at", None) or now,
        }
        for row in memberships
    )
    while batch := list(islice(rows, 500)):
        db.session.execute(
            insert(DeckReleaseEntityMembership.__table__),
            batch,
        )


def retire_memberships_by_ids(
    membership_ids: Iterable[int],
    removed_sequence: int,
) -> None:
    now = datetime.utcnow()
    ids = iter(int(mid) for mid in membership_ids)
    table = DeckReleaseEntityMembership.__table__
    while batch := list(islice(ids, 500)):
        db.session.execute(
            update(table)
            .where(table.c.id.in_(batch))
            .values(removed_sequence=int(removed_sequence), updated_at=now)
        )


def flush() -> None:
    db.session.flush()
