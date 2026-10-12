"""Database and vocabulary seeding service.

Extracted from app/cli.py to keep CLI presentation distinct from seeding domain logic.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import joinedload

from app.repositories import template_library_repository
from app.repositories import (
    flashcards_share_repository,
    study_repository,
    vocabulary_repository,
)
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import (
    anki_scheduler,
    flashcard_content_service,
    flashcards_share,
    flashcards_share_service,
    study_service,
)
import click
from app.services.flashcard_import import ImportValidationError, read_delimited_rows
from app.services.flashcard_legacy import (
    LEGACY_NOTE_TYPE_NAME,
    QUIZ_NOTE_TYPE_NAME,
    ensure_legacy_note_type,
    ensure_quiz_note_type,
)
from models import db
from models.card import Card, forget_card_identities
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.taxonomy import TaxonomyDomain, TaxonomySubject
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc

SEED_REQUIRED_FIELDS = ("deck", "word")
SEED_OPTIONAL_FIELDS = (
    "hanviet",
    "reading",
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
    "image",
    "diagram",
    "word_audio",
    "example_audio",
)
SEED_LEGACY_POSITIONAL_FIELDS = (
    "deck",
    "word",
    "reading",
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
    "image",
    "word_audio",
    "example_audio",
)
SEED_FULL_POSITIONAL_FIELDS = (
    "deck",
    "word",
    *SEED_OPTIONAL_FIELDS,
)
SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK = (
    "word",
    *SEED_OPTIONAL_FIELDS,
)
SEED_ANKI_METADATA_COLUMN_DIRECTIVES = (
    "deck column",
    "guid column",
    "notetype column",
    "tags column",
)
SEED_ANKI_DECK_PATH_KEY = "_anki_deck_path"
SEED_SUPPORTED_SUFFIXES = {".tsv", ".csv", ".txt"}

QUIZ_DUMP_DIR = Path("static") / "deck_dumps" / "trac_nghiem_markdown"
QUIZ_DUMP_MANIFEST = "deck_manifest.json"
QUIZ_DUMP_DEFAULT_FILE = "trac_nghiem_markdown.tsv"
QUIZ_DUMP_REQUIRED_COLUMNS = (
    "question",
    "answer_1",
    "answer_2",
    "answer_3",
    "answer_4",
    "correct_answer",
)


@dataclass
class SeedStats:
    created_decks: int = 0
    seeded_files: int = 0
    created_notes: int = 0
    created_cards: int = 0
    replaced_files: int = 0
    skipped_files: int = 0
    shared_decks: int = 0




def _resolve_seed_data_owner(bootstrap_user: User) -> User:
    official_items = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.is_official.is_(True),
            DeckMarketplaceItem.owner_user_id.is_not(None),
        )
        .order_by(
            DeckMarketplaceItem.created_at.asc(),
            DeckMarketplaceItem.id.asc(),
        )
        .all()
    )
    seeded_item = next(
        (
            item
            for item in official_items
            if "seeded" in {str(tag).strip().lower() for tag in (item.tags or [])}
        ),
        None,
    )
    if seeded_item is not None:
        existing_owner = db.session.get(User, seeded_item.owner_user_id)
        if existing_owner is not None:
            return existing_owner

    return bootstrap_user


def _seed_vocabulary_data(
    *,
    seed_path: str,
    replace_lessons: bool,
    owner_user_id: int | None,
    share_seeded_decks: bool,
) -> SeedStats:
    root_input = _resolve_seed_path(seed_path)
    root = _resolve_seed_root(root_input)
    if not root.exists() or not root.is_dir():
        raise click.ClickException(f"Seed path not found: {root}")

    stats = SeedStats()
    start_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=_natural_sort_key)
    root_seed_files = sorted(
        (
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    if not start_dirs and not root_seed_files:
        click.echo(f"No subfolders or seed files found in {root}. Nothing to seed.")
        return stats

    target_user = (
        db.session.get(User, owner_user_id)
        if owner_user_id
        else User.query.order_by(User.id.asc()).first()
    )
    if target_user is None:
        raise click.ClickException(
            "No user found. Create at least one user before running vocab-seed."
        )

    # The seed package creates and replaces whole Note/Card subtrees. Keep the
    # learner fence through its one final commit; NOTE lifecycle materialization
    # is not implemented for this bulk import path yet.
    try:
        lock_study_authority_route(
            db.session,
            learner_user_id=int(target_user.id),
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise click.ClickException(f"{exc.code}: {exc}") from exc

    note_type, template = ensure_legacy_note_type(db.session, target_user.id)
    quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, target_user.id)
    click.echo(f"Seeding from: {root}")
    click.echo(
        f"Using owner_user_id={target_user.id}, "
        f"note_type={note_type.id}, template={template.id}"
    )
    click.echo(
        f"Also ensured quiz_note_type={quiz_note_type.id}, "
        f"template={quiz_template.id}"
    )
    top_level_seed_dirs = list(start_dirs)
    if not top_level_seed_dirs and root_seed_files:
        top_level_seed_dirs = [root]

    for start_dir in top_level_seed_dirs:
        top_deck = _seed_dir_to_deck(
            directory=start_dir,
            parent_deck_id=None,
            owner_user_id=target_user.id,
            note_type_id=note_type.id,
            template_id=template.id,
            replace_existing=replace_lessons,
            stats=stats,
        )
        if share_seeded_decks:
            subtree_entries = _count_entries_in_deck_subtree(top_deck.id)
            shared_created = _upsert_seeded_deck_marketplace_item(
                deck=top_deck,
                owner_user_id=target_user.id,
                note_type_id=note_type.id,
                sample_cards_count=min(max(subtree_entries, 0), 20),
            )
            stats.shared_decks += 1
            action = "Created" if shared_created else "Updated"
            click.echo(f"{action} shared top-level deck item: {top_deck.name}")

    quiz_deck, quiz_note_count = _seed_quiz_dump_for_user(
        owner_user_id=target_user.id,
        note_type_id=quiz_note_type.id,
        template_id=quiz_template.id,
        replace_existing=replace_lessons,
        stats=stats,
    )
    if quiz_deck is not None:
        click.echo(
            f"Seeded quiz dump deck: {quiz_deck.name} ({quiz_note_count} notes)"
        )

    db.session.commit()
    click.echo(
        "Done. "
        f"decks+{stats.created_decks}, files_seeded={stats.seeded_files}, "
        f"notes+{stats.created_notes}, cards+{stats.created_cards}, "
        f"replaced_files={stats.replaced_files}, "
        f"skipped_files={stats.skipped_files}, "
        f"shared_decks={stats.shared_decks}"
    )
    return stats


def _find_seed_data_gaps(
    *,
    root: Path,
    owner_user_id: int,
    share_seeded_decks: bool,
) -> list[str]:
    """Return missing production seed components without parsing large dumps."""
    if not root.exists() or not root.is_dir():
        return [f"seed path not found: {root}"]

    start_dirs = sorted((path for path in root.iterdir() if path.is_dir()), key=_natural_sort_key)
    root_seed_files = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    top_level_seed_dirs = list(start_dirs)
    if not top_level_seed_dirs and root_seed_files:
        top_level_seed_dirs = [root]
    if not top_level_seed_dirs:
        return [f"no seed bundles found in {root}"]

    gaps: list[str] = []
    legacy_note_type = (
        NoteType.query.filter_by(
            user_id=owner_user_id,
            name=LEGACY_NOTE_TYPE_NAME,
        )
        .order_by(NoteType.created_at.asc(), NoteType.id.asc())
        .first()
    )
    if legacy_note_type is None:
        gaps.append(f"note type missing: {LEGACY_NOTE_TYPE_NAME}")
    elif (
        next(iter(template_library_repository.attached_templates(db.session, legacy_note_type.id)), None)
        is None
    ):
        gaps.append(f"template missing for note type: {LEGACY_NOTE_TYPE_NAME}")

    for directory in top_level_seed_dirs:
        deck = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.parent_id.is_(None),
                Deck.name == directory.name,
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if deck is None:
            gaps.append(f"seed bundle missing: {directory.name}")
            continue
        if _count_entries_in_deck_subtree(deck.id) <= 0:
            gaps.append(f"seed bundle has no notes: {directory.name}")

        if share_seeded_decks:
            listing = (
                DeckMarketplaceItem.query.filter(
                    DeckMarketplaceItem.owner_user_id == owner_user_id,
                    DeckMarketplaceItem.source_deck_id == deck.id,
                    DeckMarketplaceItem.publish_status == "published",
                    DeckMarketplaceItem.archived_at.is_(None),
                )
                .order_by(
                    DeckMarketplaceItem.created_at.asc(),
                    DeckMarketplaceItem.id.asc(),
                )
                .first()
            )
            if listing is None:
                gaps.append(f"shared listing missing: {directory.name}")

    for source_file in sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    ):
        source_decks = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.description == f"Seeded from {source_file.name}",
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .all()
        )
        source_deck_ids = [deck.id for deck in source_decks]
        seeded_note_count = 0
        if source_deck_ids:
            seeded_note_count = int(
                db.session.query(db.func.count(Note.id))
                .filter(
                    Note.user_id == owner_user_id,
                    Note.deck_id.in_(source_deck_ids),
                )
                .scalar()
                or 0
            )
        if seeded_note_count <= 0:
            gaps.append(
                f"seed source missing: {source_file.relative_to(root).as_posix()}"
            )

    dump_root, manifest_path = _resolve_quiz_dump_paths()
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            gaps.append(f"quiz manifest invalid: {manifest_path}")
            return gaps

        quiz_note_type = (
            NoteType.query.filter_by(
                user_id=owner_user_id,
                name=QUIZ_NOTE_TYPE_NAME,
            )
            .order_by(NoteType.created_at.asc(), NoteType.id.asc())
            .first()
        )
        if quiz_note_type is None:
            gaps.append(f"note type missing: {QUIZ_NOTE_TYPE_NAME}")
        elif (
            next(iter(template_library_repository.attached_templates(db.session, quiz_note_type.id)), None)
            is None
        ):
            gaps.append(f"template missing for note type: {QUIZ_NOTE_TYPE_NAME}")

        quiz_deck_name = (
            str(manifest.get("deck_name") or "Trac Nghiem Co Ban").strip()
            or "Trac Nghiem Co Ban"
        )
        quiz_deck = (
            Deck.query.filter(
                Deck.owner_user_id == owner_user_id,
                Deck.parent_id.is_(None),
                Deck.name == quiz_deck_name,
                Deck.deleted_at.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if quiz_deck is None:
            gaps.append(f"quiz seed deck missing: {quiz_deck_name}")
        elif quiz_note_type is not None:
            quiz_notes = int(
                db.session.query(db.func.count(Note.id))
                .filter(
                    Note.user_id == owner_user_id,
                    Note.note_type_id == quiz_note_type.id,
                    Note.deck_id == quiz_deck.id,
                )
                .scalar()
                or 0
            )
            if quiz_notes <= 0:
                gaps.append(f"quiz seed deck has no notes: {quiz_deck_name}")

        dump_filename = (
            str(manifest.get("file") or QUIZ_DUMP_DEFAULT_FILE).strip()
            or QUIZ_DUMP_DEFAULT_FILE
        )
        if not (dump_root / dump_filename).is_file():
            gaps.append(f"quiz dump file missing: {dump_root / dump_filename}")

    return gaps


def _resolve_seed_path(seed_path: str) -> Path:
    candidate = Path(seed_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[2] / candidate


def _resolve_seed_root(root_input: Path) -> Path:
    # If user passes project/static, auto jump into static/seed_data.
    if root_input.name.lower() == "static":
        seed_data = root_input / "seed_data"
        if seed_data.exists():
            return seed_data
    # If user passes project root and it has static/seed_data.
    seed_data_under_root = root_input / "static" / "seed_data"
    if seed_data_under_root.exists():
        return seed_data_under_root
    # Default: use input directly (often already static/seed_data).
    return root_input


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_") if value else ""


def _natural_sort_key(path_obj: Path) -> List[tuple[int, object]]:
    text = path_obj.name.lower()
    key: List[tuple[int, object]] = []
    for part in re.split(r"(\d+)", text):
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return (max_pos or 0) + 1


def _get_or_create_deck(
    *,
    parent_deck_id: int | None,
    owner_user_id: int,
    name: str,
    description: str | None,
    stats: SeedStats,
) -> tuple[Deck, bool]:
    deck = (
        Deck.query.filter(
            Deck.parent_id == parent_deck_id,
            Deck.name == name,
            Deck.owner_user_id == owner_user_id,
        )
        .order_by(Deck.id.asc())
        .first()
    )
    if deck is None:
        deck = (
            Deck.query.filter(
                Deck.parent_id == parent_deck_id,
                Deck.name == name,
                Deck.owner_user_id.is_(None),
            )
            .order_by(Deck.id.asc())
            .first()
        )
    if deck:
        if deck.owner_user_id is None:
            deck.owner_user_id = owner_user_id
        deck.deleted_at = None
        return deck, False

    deck = Deck(
        parent_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=name,
        description=description,
        position=_next_deck_position(parent_deck_id),
    )
    db.session.add(deck)
    db.session.flush()
    stats.created_decks += 1
    return deck, True


def _seed_dir_to_deck(
    *,
    directory: Path,
    parent_deck_id: int | None,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> Deck:
    deck_name = directory.name.strip()
    if not deck_name:
        return

    deck_node, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=deck_name,
        description=None,
        stats=stats,
    )
    if created:
        click.echo(f"Created deck: {deck_node.name}")
    else:
        click.echo(f"Using deck: {deck_node.name}")

    # Files in a folder become leaf decks under this folder deck.
    seed_files = sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in SEED_SUPPORTED_SUFFIXES
        ),
        key=_natural_sort_key,
    )
    for seed_file in seed_files:
        _seed_file_to_leaf_deck(
            file_path=seed_file,
            parent_deck_id=deck_node.id,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            stats=stats,
        )

    # Recurse subfolders for nested deck hierarchy.
    subdirs = sorted((p for p in directory.iterdir() if p.is_dir()), key=_natural_sort_key)
    for child_dir in subdirs:
        _seed_dir_to_deck(
            directory=child_dir,
            parent_deck_id=deck_node.id,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            stats=stats,
        )
    return deck_node


def _seed_file_to_leaf_deck(
    *,
    file_path: Path,
    parent_deck_id: int,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> None:
    rows = _load_seed_rows(file_path)
    if not rows:
        stats.skipped_files += 1
        click.echo(f"  Skip empty file: {file_path.name}")
        return

    anki_deck_groups = _group_rows_by_anki_deck(rows, file_path)
    if not anki_deck_groups:
        leaf_name = file_path.stem.strip() or file_path.name
        leaf_deck, created = _get_or_create_deck(
            parent_deck_id=parent_deck_id,
            owner_user_id=owner_user_id,
            name=leaf_name,
            description=f"Seeded from {file_path.name}",
            stats=stats,
        )
        status = _seed_rows_to_deck(
            rows=rows,
            deck=leaf_deck,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            source_label=file_path.name,
            stats=stats,
        )
        if status == "skipped":
            stats.skipped_files += 1
            return
        if status == "replaced":
            stats.replaced_files += 1
        stats.seeded_files += 1
        deck_state = "Created" if created else "Updated"
        click.echo(f"  {deck_state} leaf deck: {leaf_name} ({len(rows)} rows)")
        return

    seeded_groups = 0
    replaced_groups = 0
    for deck_path, deck_rows in anki_deck_groups:
        leaf_deck, created = _get_or_create_seed_deck_path(
            parent_deck_id=parent_deck_id,
            owner_user_id=owner_user_id,
            path_parts=deck_path,
            source_file=file_path,
            stats=stats,
        )
        status = _seed_rows_to_deck(
            rows=deck_rows,
            deck=leaf_deck,
            owner_user_id=owner_user_id,
            note_type_id=note_type_id,
            template_id=template_id,
            replace_existing=replace_existing,
            source_label=f"{file_path.name}::{'::'.join(deck_path)}",
            stats=stats,
        )
        if status == "skipped":
            continue
        seeded_groups += 1
        if status == "replaced":
            replaced_groups += 1
        deck_state = "Created" if created else "Updated"
        click.echo(
            f"  {deck_state} Anki deck: {'::'.join(deck_path)} ({len(deck_rows)} rows)"
        )

    if seeded_groups:
        stats.seeded_files += 1
        if replaced_groups:
            stats.replaced_files += 1
        click.echo(
            f"  Split Anki export: {file_path.name} -> {len(anki_deck_groups)} deck(s)"
        )
    else:
        stats.skipped_files += 1


def _seed_rows_to_deck(
    *,
    rows: List[Dict[str, str | None]],
    deck: Deck,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    source_label: str,
    stats: SeedStats,
) -> str:
    existing_count = (
        db.session.query(db.func.count(Note.id))
        .filter(
            Note.deck_id == deck.id,
            Note.user_id == owner_user_id,
            Note.note_type_id == note_type_id,
        )
        .scalar()
        or 0
    )
    if existing_count and not replace_existing:
        click.echo(f"  Skip deck (already seeded): {source_label}")
        return "skipped"
    if existing_count and replace_existing:
        existing_notes = (
            Note.query.filter(
                Note.deck_id == deck.id,
                Note.user_id == owner_user_id,
                Note.note_type_id == note_type_id,
            )
            .all()
        )
        existing_note_ids = [note.id for note in existing_notes]
        existing_card_ids: list[str] = []
        if existing_note_ids:
            existing_card_ids = [
                row[0]
                for row in db.session.query(Card.id)
                .filter(Card.note_id.in_(existing_note_ids))
                .all()
                if row and row[0]
            ]
        # NOTE learners' rows are tombstoned like any content delete (ADR P10).
        _tombstone_replaced_notes(
            card_ids=existing_card_ids,
            note_ids=existing_note_ids,
            source_path="seed.deck_replace",
            operation_key=f"seed-deck-replace:{deck.id}:{source_label}",
        )
        if existing_note_ids:
            forget_card_identities(db.session, existing_note_ids)
            Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)
        click.echo(f"  Replace seeded deck: {source_label}")

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=deck.id,
                field_values=_seed_row_to_field_values(row),
                tags=[],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    # One Card per Note: derived from the seed NoteType's one occurrence (ADR P11).
    stats.created_notes += len(notes)
    stats.created_cards += len(notes)
    return "replaced" if existing_count else "seeded"


def _get_or_create_seed_deck_path(
    *,
    parent_deck_id: int,
    owner_user_id: int,
    path_parts: tuple[str, ...],
    source_file: Path,
    stats: SeedStats,
) -> tuple[Deck, bool]:
    current_parent_id = parent_deck_id
    leaf_deck: Deck | None = None
    leaf_created = False
    for index, part in enumerate(path_parts):
        is_leaf = index == len(path_parts) - 1
        leaf_deck, created = _get_or_create_deck(
            parent_deck_id=current_parent_id,
            owner_user_id=owner_user_id,
            name=part,
            description=f"Seeded from {source_file.name}" if is_leaf else None,
            stats=stats,
        )
        current_parent_id = leaf_deck.id
        if is_leaf:
            leaf_created = created
    if leaf_deck is None:
        raise click.ClickException(f"Anki deck path is empty in {source_file}")
    return leaf_deck, leaf_created


def _count_entries_in_deck_subtree(deck_id: int) -> int:
    total = 0
    stack = [deck_id]
    while stack:
        current = stack.pop()
        total += (
            db.session.query(db.func.count(Note.id))
            .filter(Note.deck_id == current)
            .scalar()
            or 0
        )
        child_ids = [
            row[0]
            for row in db.session.query(Deck.id)
            .filter(Deck.parent_id == current)
            .all()
        ]
        stack.extend(child_ids)
    return int(total)


def _upsert_seeded_deck_marketplace_item(
    *,
    deck: Deck,
    owner_user_id: int,
    note_type_id: str,
    sample_cards_count: int,
) -> bool:
    same_title_seeded_items = [
        item
        for item in (
            DeckMarketplaceItem.query.filter_by(
                owner_user_id=owner_user_id,
                title=deck.name,
            )
            .order_by(DeckMarketplaceItem.created_at.asc(), DeckMarketplaceItem.id.asc())
            .all()
        )
        if item.is_official and "seeded" in {str(tag).strip().lower() for tag in (item.tags or [])}
    ]
    deck_item = next(
        (
            item
            for item in same_title_seeded_items
            if item.source_deck_id == deck.id
        ),
        None,
    )
    if deck_item is None:
        deck_item = same_title_seeded_items[0] if same_title_seeded_items else None
    if deck_item:
        now = datetime.utcnow()
        for duplicate in same_title_seeded_items:
            if duplicate.id == deck_item.id:
                continue
            # Preserve historical installs/reviews while removing stale seed
            # listings from active marketplace and owner-library surfaces.
            duplicate.publish_status = "archived"
            duplicate.archived_at = duplicate.archived_at or now
            duplicate.is_official = False

        deck_item.source_deck_id = deck.id
        if not deck_item.title:
            deck_item.title = deck.name
        if not deck_item.description:
            deck_item.description = deck.description or f"Seeded deck: {deck.name}"
        deck_item.source_note_type_id = note_type_id
        deck_item.primary_category = deck_item.primary_category or "Japanese"
        deck_item.tags = deck_item.tags or ["seeded", "default"]
        deck_item.preview_text = deck_item.preview_text or f"Default seeded deck: {deck.name}"
        deck_item.sample_cards_count = max(int(deck_item.sample_cards_count or 0), sample_cards_count)
        deck_item.pricing_mode = "free"
        deck_item.price_amount_minor = 0
        deck_item.publish_status = "published"
        deck_item.is_official = True
        deck_item.published_at = deck_item.published_at or now
        deck_item.archived_at = None
        db.session.flush()
        release_error = flashcards_share_service._stage_initial_release_if_visible(deck_item)
        if release_error:
            raise click.ClickException(
                f"Could not publish initial release for seeded deck '{deck.name}': {release_error}"
            )
        return False

    new_item = DeckMarketplaceItem(
        owner_user_id=owner_user_id,
        source_deck_id=deck.id,
        source_note_type_id=note_type_id,
        title=deck.name,
        description=deck.description or f"Seeded deck: {deck.name}",
        primary_category="Japanese",
        tags=["seeded", "default"],
        preview_text=f"Default seeded deck: {deck.name}",
        sample_cards_count=sample_cards_count,
        pricing_mode="free",
        price_amount_minor=0,
        version="1.0.0",
        publish_status="published",
        is_official=True,
        published_at=datetime.utcnow(),
    )
    db.session.add(new_item)
    db.session.flush()
    release_error = flashcards_share_service._stage_initial_release_if_visible(new_item)
    if release_error:
        raise click.ClickException(
            f"Could not publish initial release for seeded deck '{deck.name}': {release_error}"
        )
    return True


def _build_header_mapping(fieldnames: Iterable[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for original in fieldnames:
        normalized = _normalize_header(original)
        if normalized in SEED_REQUIRED_FIELDS or normalized in SEED_OPTIONAL_FIELDS:
            mapping[normalized] = original
    missing = [field for field in SEED_REQUIRED_FIELDS if field not in mapping]
    if missing:
        raise click.ClickException(f"Missing required columns: {', '.join(missing)}")
    return mapping


def _default_seed_delimiter(file_path: Path) -> str:
    return "\t" if file_path.suffix.lower() in {".tsv", ".txt"} else ","


def _clean_seed_cell(value: str | None) -> str | None:
    cleaned = (value or "").replace("\r", "").strip()
    return cleaned or None


def _looks_like_seed_header_row(row: list[str]) -> bool:
    normalized = {_normalize_header(value) for value in row if _normalize_header(value)}
    return all(field in normalized for field in SEED_REQUIRED_FIELDS)


def _load_seed_rows_from_header_rows(rows: List[List[str]]) -> List[Dict[str, str | None]]:
    headers = rows[0]
    mapping = _build_header_mapping(headers)
    items: List[Dict[str, str | None]] = []

    for row_values in rows[1:]:
        raw = {
            headers[index]: row_values[index] if index < len(row_values) else ""
            for index in range(len(headers))
        }
        deck = _clean_seed_cell(raw.get(mapping["deck"]))
        word = _clean_seed_cell(raw.get(mapping["word"]))
        if not deck or not word:
            continue

        payload: Dict[str, str | None] = {"deck": deck, "word": word}
        for field in SEED_OPTIONAL_FIELDS:
            source_key = mapping.get(field)
            payload[field] = _clean_seed_cell(raw.get(source_key) if source_key else None)
        items.append(payload)

    return items


def _parse_anki_column_indexes(
    directives: Dict[str, str],
    file_path: Path,
) -> Dict[str, int]:
    indexes: Dict[str, int] = {}
    for directive in SEED_ANKI_METADATA_COLUMN_DIRECTIVES:
        raw_value = directives.get(directive)
        if raw_value is None:
            continue
        try:
            one_based_index = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise click.ClickException(
                f"Invalid Anki directive #{directive}:{raw_value} in {file_path}: "
                "column must be a positive integer."
            ) from exc
        if one_based_index < 1:
            raise click.ClickException(
                f"Invalid Anki directive #{directive}:{raw_value} in {file_path}: "
                "column numbering starts at 1."
            )
        indexes[directive] = one_based_index - 1
    return indexes


def _strip_anki_metadata_columns(
    row_values: List[str],
    *,
    column_indexes: Dict[str, int],
    file_path: Path,
    row_index: int,
) -> tuple[List[str], str | None]:
    for directive, column_index in column_indexes.items():
        if column_index >= len(row_values):
            raise click.ClickException(
                f"Invalid Anki row in {file_path} at data row {row_index}: "
                f"#{directive} points to column {column_index + 1}, "
                f"but the row has only {len(row_values)} columns."
            )

    deck_column_index = column_indexes.get("deck column")
    anki_deck_path = (
        _clean_seed_cell(row_values[deck_column_index])
        if deck_column_index is not None
        else None
    )
    metadata_indexes = set(column_indexes.values())
    field_values = [
        value for index, value in enumerate(row_values) if index not in metadata_indexes
    ]
    return field_values, anki_deck_path


def _select_seed_positional_fields(
    *,
    field_count: int,
    has_anki_deck_column: bool,
    file_path: Path,
    row_index: int,
) -> tuple[str, ...]:
    if field_count == len(SEED_FULL_POSITIONAL_FIELDS):
        return SEED_FULL_POSITIONAL_FIELDS
    if has_anki_deck_column and field_count == len(SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK):
        return SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK
    if field_count == len(SEED_LEGACY_POSITIONAL_FIELDS):
        return SEED_LEGACY_POSITIONAL_FIELDS
    if field_count == len(SEED_FULL_POSITIONAL_FIELDS) + 1:
        return SEED_FULL_POSITIONAL_FIELDS
    if not has_anki_deck_column and field_count == len(SEED_LEGACY_POSITIONAL_FIELDS) + 1:
        return SEED_LEGACY_POSITIONAL_FIELDS

    expected_counts = {
        len(SEED_LEGACY_POSITIONAL_FIELDS),
        len(SEED_LEGACY_POSITIONAL_FIELDS) + 1,
        len(SEED_FULL_POSITIONAL_FIELDS),
        len(SEED_FULL_POSITIONAL_FIELDS) + 1,
    }
    if has_anki_deck_column:
        expected_counts.add(len(SEED_FULL_POSITIONAL_FIELDS_WITHOUT_DECK))
    expected_label = ", ".join(str(value) for value in sorted(expected_counts))
    raise click.ClickException(
        f"Unsupported Anki seed row in {file_path} at data row {row_index}: "
        f"found {field_count} note-field columns after removing Anki metadata; "
        f"expected {expected_label}."
    )


def _load_seed_rows_from_positional_rows(
    rows: List[List[str]],
    file_path: Path,
    directives: Dict[str, str],
) -> List[Dict[str, str | None]]:
    column_indexes = _parse_anki_column_indexes(directives, file_path)
    has_anki_deck_column = "deck column" in column_indexes
    items: List[Dict[str, str | None]] = []

    for row_index, row_values in enumerate(rows, start=1):
        note_field_values, anki_deck_path = _strip_anki_metadata_columns(
            row_values,
            column_indexes=column_indexes,
            file_path=file_path,
            row_index=row_index,
        )
        positional_fields = _select_seed_positional_fields(
            field_count=len(note_field_values),
            has_anki_deck_column=has_anki_deck_column,
            file_path=file_path,
            row_index=row_index,
        )

        payload: Dict[str, str | None] = {
            field_name: _clean_seed_cell(note_field_values[index])
            for index, field_name in enumerate(positional_fields)
        }
        deck = payload.get("deck") or anki_deck_path
        word = payload.get("word")
        if not deck or not word:
            continue

        normalized_payload: Dict[str, str | None] = {"deck": deck, "word": word}
        for field in SEED_OPTIONAL_FIELDS:
            normalized_payload[field] = payload.get(field)
        if anki_deck_path:
            normalized_payload[SEED_ANKI_DECK_PATH_KEY] = anki_deck_path
        items.append(normalized_payload)

    return items


def _load_seed_rows(file_path: Path) -> List[Dict[str, str | None]]:
    try:
        raw_rows, metadata = read_delimited_rows(
            file_bytes=file_path.read_bytes(),
            delimiter=_default_seed_delimiter(file_path),
        )
    except OSError as exc:
        raise click.ClickException(f"Failed to read seed file {file_path}: {exc}") from exc
    except ImportValidationError as exc:
        raise click.ClickException(f"Failed to parse seed file {file_path}: {exc}") from exc

    if not raw_rows:
        return []
    if _looks_like_seed_header_row(raw_rows[0]):
        return _load_seed_rows_from_header_rows(raw_rows)
    directives = {
        str(key): str(value)
        for key, value in dict(metadata.get("preamble_directives") or {}).items()
    }
    return _load_seed_rows_from_positional_rows(raw_rows, file_path, directives)


def _split_anki_deck_path(raw_path: str, file_path: Path) -> tuple[str, ...]:
    parts = tuple(part.strip() for part in raw_path.split("::") if part.strip())
    if not parts:
        raise click.ClickException(f"Anki deck path is empty in {file_path}")
    return parts


def _common_anki_parent_prefix(paths: List[tuple[str, ...]]) -> tuple[str, ...]:
    if not paths:
        return ()
    parent_paths = [path[:-1] for path in paths]
    common: list[str] = []
    for parts_at_depth in zip(*parent_paths):
        if len(set(parts_at_depth)) != 1:
            break
        common.append(parts_at_depth[0])
    return tuple(common)


def _group_rows_by_anki_deck(
    rows: List[Dict[str, str | None]],
    file_path: Path,
) -> List[tuple[tuple[str, ...], List[Dict[str, str | None]]]]:
    routed_rows = [row for row in rows if row.get(SEED_ANKI_DECK_PATH_KEY)]
    if not routed_rows:
        return []
    if len(routed_rows) != len(rows):
        raise click.ClickException(
            f"Anki export {file_path} mixes rows with and without a deck path."
        )

    grouped_by_full_path: Dict[tuple[str, ...], List[Dict[str, str | None]]] = {}
    for row in rows:
        raw_path = str(row.get(SEED_ANKI_DECK_PATH_KEY) or "")
        full_path = _split_anki_deck_path(raw_path, file_path)
        grouped_by_full_path.setdefault(full_path, []).append(row)

    full_paths = list(grouped_by_full_path)
    common_parent = _common_anki_parent_prefix(full_paths)
    groups: List[tuple[tuple[str, ...], List[Dict[str, str | None]]]] = []
    for full_path in sorted(full_paths, key=lambda path: _natural_sort_key(Path("::".join(path)))):
        relative_path = full_path[len(common_parent):] or full_path[-1:]
        groups.append((relative_path, grouped_by_full_path[full_path]))
    return groups


def _seed_row_to_field_values(row: Dict[str, str | None]) -> Dict[str, str | None]:
    """Map seed CSV row columns into default Flama note field_values JSON."""
    return {
        "word": row.get("word") or "",
        "hanviet": row.get("hanviet"),
        "reading": row.get("reading"),
        "translation_vi": row.get("translation_vi"),
        "meaning_jp": row.get("meaning_jp"),
        "meaning_vi": row.get("meaning_vi"),
        "usage_jp": row.get("usage_jp"),
        "usage_vi": row.get("usage_vi"),
        "example_jp": row.get("example_jp"),
        "example_vi": row.get("example_vi"),
        "additional_note_jp": row.get("additional_note_jp"),
        "additional_note_vi": row.get("additional_note_vi"),
        "image": row.get("image"),
        "diagram": row.get("diagram"),
        "word_audio": row.get("word_audio"),
        "example_audio": row.get("example_audio"),
    }


def _resolve_quiz_dump_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2] / QUIZ_DUMP_DIR
    return root, root / QUIZ_DUMP_MANIFEST


def _normalize_quiz_correct_answer(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip()
    if candidate in {"1", "2", "3", "4"}:
        return candidate
    try:
        parsed = int(candidate)
    except (TypeError, ValueError):
        return "1"
    return str(parsed) if 1 <= parsed <= 4 else "1"


def _load_quiz_dump_rows(tsv_path: Path) -> list[dict[str, str]]:
    with tsv_path.open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile, delimiter="\t")
        if not reader.fieldnames:
            raise click.ClickException(f"Missing header row in quiz dump: {tsv_path}")

        normalized_columns = {_normalize_header(name): name for name in reader.fieldnames if name}
        missing_columns = [name for name in QUIZ_DUMP_REQUIRED_COLUMNS if name not in normalized_columns]
        if missing_columns:
            raise click.ClickException(
                "Quiz dump is missing required columns: " + ", ".join(missing_columns)
            )

        rows: list[dict[str, str]] = []
        for raw in reader:
            if not raw:
                continue
            question = str(raw.get(normalized_columns["question"]) or "").strip()
            if not question:
                continue
            rows.append(
                {
                    "question": question,
                    "answer_1": str(raw.get(normalized_columns["answer_1"]) or "").strip(),
                    "answer_2": str(raw.get(normalized_columns["answer_2"]) or "").strip(),
                    "answer_3": str(raw.get(normalized_columns["answer_3"]) or "").strip(),
                    "answer_4": str(raw.get(normalized_columns["answer_4"]) or "").strip(),
                    "correct_answer": _normalize_quiz_correct_answer(
                        str(raw.get(normalized_columns["correct_answer"]) or "").strip()
                    ),
                }
            )
        return rows


def _seed_quiz_dump_for_user(
    *,
    owner_user_id: int,
    note_type_id: str,
    template_id: str,
    replace_existing: bool,
    stats: SeedStats,
) -> tuple[Deck | None, int]:
    dump_root, manifest_path = _resolve_quiz_dump_paths()
    if not manifest_path.exists():
        click.echo(f"Quiz dump manifest not found: {manifest_path}. Skipping quiz deck seed.")
        return None, 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid quiz dump manifest JSON: {manifest_path}") from exc

    deck_name = str(manifest.get("deck_name") or "Trac Nghiem Co Ban").strip() or "Trac Nghiem Co Ban"
    dump_filename = str(manifest.get("file") or QUIZ_DUMP_DEFAULT_FILE).strip() or QUIZ_DUMP_DEFAULT_FILE
    dump_file = dump_root / dump_filename
    if not dump_file.exists():
        raise click.ClickException(f"Quiz dump file not found: {dump_file}")

    rows = _load_quiz_dump_rows(dump_file)
    if not rows:
        click.echo(f"Quiz dump has no valid rows: {dump_file}. Skipping quiz deck seed.")
        return None, 0

    deck_description = f"Seeded quiz dump from {dump_file.name}"
    quiz_deck, _created = _get_or_create_deck(
        parent_deck_id=None,
        owner_user_id=owner_user_id,
        name=deck_name,
        description=deck_description,
        stats=stats,
    )
    if not quiz_deck.note_type_id:
        quiz_deck.note_type_id = note_type_id

    existing_notes = (
        Note.query.filter(
            Note.deck_id == quiz_deck.id,
            Note.user_id == owner_user_id,
            Note.note_type_id == note_type_id,
        )
        .all()
    )
    existing_note_ids = [note.id for note in existing_notes]
    if existing_note_ids and not replace_existing:
        stats.skipped_files += 1
        click.echo(f"Skip quiz deck (already seeded): {quiz_deck.name}")
        return quiz_deck, len(existing_notes)

    if existing_note_ids:
        existing_card_ids = [
            row[0]
            for row in db.session.query(Card.id)
            .filter(Card.note_id.in_(existing_note_ids))
            .all()
            if row and row[0]
        ]
        # NOTE learners' rows are tombstoned like any content delete (ADR P10).
        _tombstone_replaced_notes(
            card_ids=existing_card_ids,
            note_ids=existing_note_ids,
            source_path="seed.quiz_replace",
            operation_key=f"seed-quiz-replace:{quiz_deck.id}:{dump_filename}",
        )
        forget_card_identities(db.session, existing_note_ids)
        Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)
        stats.replaced_files += 1

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=quiz_deck.id,
                field_values={
                    "question": row["question"],
                    "answer_1": row["answer_1"],
                    "answer_2": row["answer_2"],
                    "answer_3": row["answer_3"],
                    "answer_4": row["answer_4"],
                    "correct_answer": row["correct_answer"],
                },
                tags=["quiz", "seeded"],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    # One Card per Note: derived from the quiz NoteType's one occurrence (ADR P11).
    stats.created_notes += len(notes)
    stats.created_cards += len(notes)
    stats.seeded_files += 1
    return quiz_deck, len(notes)


def _tombstone_replaced_notes(*, card_ids, note_ids, source_path: str, operation_key: str) -> None:
    """Fence every learner of the replaced Notes and tombstone their progress."""

    from app.services import study_content_delete_service as content_delete

    card_ids = [str(value) for value in card_ids]
    note_ids = [str(value) for value in note_ids]
    routes = content_delete.lock_content_delete_routes(
        db.session, actor_user_ids=(), card_ids=card_ids, deleted_note_ids=note_ids
    )
    plan = content_delete.prepare_content_delete(
        db.session, routes=routes, card_ids=card_ids, note_ids=note_ids, cancel_legacy_sessions=False
    )
    content_delete.verify_content_delete_scope(
        db.session, routes=routes, card_ids=card_ids, deleted_note_ids=note_ids
    )
    if card_ids:
        pass  # NOTE lifecycle state is handled by the fenced deletion plan.
    content_delete.finalize_content_delete(plan, source_path=source_path, operation_key=operation_key)
