"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import click
from flask import Flask

from app.services.flashcard_legacy import ensure_legacy_note_type
from app.services.user_roles import ensure_default_user_roles
from models import db
from models.flashcard import Card, DeckMarketplaceItem, LegacyMigrationMap, Note
from models.user import User
from models.user_role import UserRole
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_progress import VocabularyProgress

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
SEED_SUPPORTED_SUFFIXES = {".tsv", ".csv"}


@dataclass
class SeedStats:
    created_decks: int = 0
    seeded_files: int = 0
    created_entries: int = 0
    created_notes: int = 0
    created_cards: int = 0
    replaced_files: int = 0
    skipped_files: int = 0
    shared_decks: int = 0


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

    @app.cli.command("user-role-seed")
    def user_role_seed() -> None:
        """Seed default user roles and backfill users missing role mapping."""
        ensure_default_user_roles(db.session)
        db.session.commit()
        roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
        codes = ", ".join(role.code for role in roles)
        click.echo(f"Done. Seeded roles: {codes}")

    @app.cli.command("vocab-seed")
    @click.option(
        "--path",
        "seed_path",
        default="static/seed_data",
        show_default=True,
        help="Path to seed source. If path is 'static', command auto-uses 'static/seed_data'.",
    )
    @click.option(
        "--replace-lessons",
        is_flag=True,
        default=False,
        help="Replace entries in existing file-decks instead of skipping them.",
    )
    @click.option(
        "--owner-user-id",
        type=int,
        default=None,
        help="Owner user id for seeded decks/notes. Defaults to first available user.",
    )
    @click.option(
        "--share-seeded-decks/--no-share-seeded-decks",
        default=True,
        show_default=True,
        help="Auto publish only top-level seeded decks (with full subtree) to shared marketplace.",
    )
    def vocab_seed(
        seed_path: str,
        replace_lessons: bool,
        owner_user_id: int | None,
        share_seeded_decks: bool,
    ) -> None:
        """Seed deck tree from static folder structure.

        Rules:
        - `seed_data` is container only (not a deck node)
        - Subfolders under `seed_data` start hierarchy
        - Folder -> Deck node
        - File (.tsv/.csv) -> Leaf deck node containing vocabulary entries
        """

        root_input = _resolve_seed_path(seed_path)
        root = _resolve_seed_root(root_input)
        if not root.exists() or not root.is_dir():
            raise click.ClickException(f"Seed path not found: {root}")

        stats = SeedStats()
        start_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=_natural_sort_key)
        if not start_dirs:
            click.echo(f"No subfolders found in {root}. Nothing to seed.")
            return

        target_user = User.query.get(owner_user_id) if owner_user_id else User.query.order_by(User.id.asc()).first()
        if target_user is None:
            raise click.ClickException("No user found. Create at least one user before running vocab-seed.")

        note_type, template = ensure_legacy_note_type(db.session, target_user.id)
        click.echo(f"Seeding from: {root}")
        click.echo(
            f"Using owner_user_id={target_user.id}, note_type={note_type.id}, template={template.id}"
        )
        for start_dir in start_dirs:
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

        db.session.commit()
        click.echo(
            "Done. "
            f"decks+{stats.created_decks}, files_seeded={stats.seeded_files}, "
            f"entries+{stats.created_entries}, notes+{stats.created_notes}, cards+{stats.created_cards}, "
            f"replaced_files={stats.replaced_files}, "
            f"skipped_files={stats.skipped_files}, "
            f"shared_decks={stats.shared_decks}"
        )

    @app.cli.command("flashcard-migrate-legacy")
    @click.option("--user-id", type=int, default=None, help="Target owner user id for migrated notes.")
    @click.option("--sample-size", type=int, default=50, show_default=True, help="Sample size for data verification.")
    @click.option("--dry-run", is_flag=True, default=False, help="Run migration checks then rollback.")
    def flashcard_migrate_legacy(user_id: int | None, sample_size: int, dry_run: bool) -> None:
        """Backfill legacy vocabulary entries into flashcard v2 note/card model."""
        target_user = User.query.get(user_id) if user_id else User.query.order_by(User.id.asc()).first()
        if target_user is None:
            raise click.ClickException("No user found. Create at least one user before migration.")

        note_type, template = ensure_legacy_note_type(db.session, target_user.id)
        click.echo(f"Using user={target_user.id}, note_type={note_type.id}, template={template.id}")

        legacy_entries = VocabularyEntry.query.order_by(VocabularyEntry.id.asc()).all()
        existing_maps = {
            row.entry_id: row
            for row in LegacyMigrationMap.query.all()
        }
        created_notes = 0
        created_cards = 0

        for entry in legacy_entries:
            if entry.id in existing_maps:
                continue
            note = Note(
                note_type_id=note_type.id,
                user_id=target_user.id,
                deck_id=entry.deck_id,
                field_values=_legacy_entry_to_field_values(entry),
                tags=[],
            )
            db.session.add(note)
            db.session.flush()

            card = Card(
                note_id=note.id,
                template_id=template.id,
                queue="new",
            )
            db.session.add(card)
            db.session.flush()

            db.session.add(
                LegacyMigrationMap(entry_id=entry.id, note_id=note.id, card_id=card.id)
            )
            created_notes += 1
            created_cards += 1

        db.session.flush()

        migration_map = {row.entry_id: row.card_id for row in LegacyMigrationMap.query.all()}
        progress_rows = VocabularyProgress.query.filter(VocabularyProgress.entry_id.isnot(None)).all()
        mapped_progress = 0
        for progress in progress_rows:
            mapped_card_id = migration_map.get(progress.entry_id)
            if mapped_card_id and progress.new_card_id != mapped_card_id:
                progress.new_card_id = mapped_card_id
                mapped_progress += 1

        db.session.flush()

        total_entries = VocabularyEntry.query.count()
        total_notes = Note.query.filter_by(note_type_id=note_type.id, user_id=target_user.id).count()
        total_progress = VocabularyProgress.query.filter(VocabularyProgress.entry_id.isnot(None)).count()
        mapped_progress_total = (
            VocabularyProgress.query.filter(
                VocabularyProgress.entry_id.isnot(None),
                VocabularyProgress.new_card_id.isnot(None),
            ).count()
        )

        sample_rows = (
            VocabularyEntry.query.order_by(VocabularyEntry.id.asc()).limit(max(0, sample_size)).all()
        )
        mismatches = 0
        for entry in sample_rows:
            map_row = LegacyMigrationMap.query.filter_by(entry_id=entry.id).first()
            if map_row is None:
                mismatches += 1
                continue
            note = Note.query.get(map_row.note_id)
            if note is None:
                mismatches += 1
                continue
            expected = _legacy_entry_to_field_values(entry)
            for key, value in expected.items():
                if (note.field_values or {}).get(key, "") != (value or ""):
                    mismatches += 1
                    break

        click.echo(
            "Verification: "
            f"entries={total_entries}, notes={total_notes}, "
            f"progress={total_progress}, mapped_progress={mapped_progress_total}, "
            f"sample_mismatches={mismatches}"
        )
        click.echo(
            "Changes: "
            f"created_notes={created_notes}, created_cards={created_cards}, mapped_progress_updates={mapped_progress}"
        )

        if dry_run:
            db.session.rollback()
            click.echo("Dry-run complete. Rolled back all changes.")
        else:
            db.session.commit()
            click.echo("Legacy flashcard migration committed.")


def _resolve_seed_path(seed_path: str) -> Path:
    candidate = Path(seed_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parent.parent / candidate


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
    query = db.session.query(db.func.max(VocabularyDeck.position))
    if parent_deck_id is None:
        max_pos = query.filter(VocabularyDeck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(VocabularyDeck.parent_id == parent_deck_id).scalar()
    return (max_pos or 0) + 1


def _get_or_create_deck(
    *,
    parent_deck_id: int | None,
    owner_user_id: int,
    name: str,
    description: str | None,
    stats: SeedStats,
) -> tuple[VocabularyDeck, bool]:
    deck = (
        VocabularyDeck.query.filter(
            VocabularyDeck.parent_id == parent_deck_id,
            VocabularyDeck.name == name,
        )
        .order_by(VocabularyDeck.id.asc())
        .first()
    )
    if deck:
        if deck.owner_user_id is None:
            deck.owner_user_id = owner_user_id
        return deck, False

    deck = VocabularyDeck(
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
) -> VocabularyDeck:
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
    leaf_name = file_path.stem.strip() or file_path.name
    leaf_deck, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=leaf_name,
        description=f"Seeded from {file_path.name}",
        stats=stats,
    )

    existing_count = (
        db.session.query(db.func.count(VocabularyEntry.id))
        .filter(VocabularyEntry.deck_id == leaf_deck.id)
        .scalar()
        or 0
    )
    if existing_count and not replace_existing:
        stats.skipped_files += 1
        click.echo(f"  Skip file (already seeded): {file_path.name}")
        return
    if existing_count and replace_existing:
        existing_entry_ids = [
            row[0]
            for row in db.session.query(VocabularyEntry.id)
            .filter(VocabularyEntry.deck_id == leaf_deck.id)
            .all()
        ]
        if existing_entry_ids:
            LegacyMigrationMap.query.filter(
                LegacyMigrationMap.entry_id.in_(existing_entry_ids)
            ).delete(synchronize_session=False)
        existing_notes = (
            Note.query.filter(
                Note.deck_id == leaf_deck.id,
                Note.user_id == owner_user_id,
                Note.note_type_id == note_type_id,
            )
            .all()
        )
        for note in existing_notes:
            db.session.delete(note)
        VocabularyEntry.query.filter(VocabularyEntry.deck_id == leaf_deck.id).delete()
        stats.replaced_files += 1
        click.echo(f"  Replace file deck: {file_path.name}")

    rows = _load_seed_rows(file_path)
    if not rows:
        stats.skipped_files += 1
        click.echo(f"  Skip empty file: {file_path.name}")
        return

    entries = []
    for row in rows:
        entry = VocabularyEntry(
            deck_id=leaf_deck.id,
            lesson_id=None,
            deck=row.get("deck") or "",
            word=row.get("word") or "",
            hanviet=row.get("hanviet"),
            reading=row.get("reading"),
            translation_vi=row.get("translation_vi"),
            meaning_jp=row.get("meaning_jp"),
            meaning_vi=row.get("meaning_vi"),
            usage_jp=row.get("usage_jp"),
            usage_vi=row.get("usage_vi"),
            example_jp=row.get("example_jp"),
            example_vi=row.get("example_vi"),
            additional_note_jp=row.get("additional_note_jp"),
            additional_note_vi=row.get("additional_note_vi"),
            image=row.get("image"),
            diagram=row.get("diagram"),
            word_audio=row.get("word_audio"),
            example_audio=row.get("example_audio"),
        )
        entries.append(entry)

    db.session.add_all(entries)

    notes: list[Note] = []
    for entry in entries:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=leaf_deck.id,
                field_values=_legacy_entry_to_field_values(entry),
                tags=[],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    cards: list[Card] = []
    for note in notes:
        cards.append(
            Card(
                note_id=note.id,
                template_id=template_id,
                queue="new",
            )
        )
    db.session.add_all(cards)
    db.session.flush()

    migration_maps: list[LegacyMigrationMap] = []
    for entry, note, card in zip(entries, notes, cards):
        migration_maps.append(
            LegacyMigrationMap(
                entry_id=entry.id,
                note_id=note.id,
                card_id=card.id,
            )
        )
    db.session.add_all(migration_maps)

    stats.created_entries += len(entries)
    stats.created_notes += len(notes)
    stats.created_cards += len(cards)
    stats.seeded_files += 1
    deck_state = "Created" if created else "Updated"
    click.echo(f"  {deck_state} leaf deck: {leaf_name} ({len(entries)} rows)")


def _count_entries_in_deck_subtree(deck_id: int) -> int:
    total = 0
    stack = [deck_id]
    while stack:
        current = stack.pop()
        total += (
            db.session.query(db.func.count(VocabularyEntry.id))
            .filter(VocabularyEntry.deck_id == current)
            .scalar()
            or 0
        )
        child_ids = [
            row[0]
            for row in db.session.query(VocabularyDeck.id)
            .filter(VocabularyDeck.parent_id == current)
            .all()
        ]
        stack.extend(child_ids)
    return int(total)


def _upsert_seeded_deck_marketplace_item(
    *,
    deck: VocabularyDeck,
    owner_user_id: int,
    note_type_id: str,
    sample_cards_count: int,
) -> bool:
    deck_item = (
        DeckMarketplaceItem.query.filter_by(
            owner_user_id=owner_user_id,
            source_deck_id=deck.id,
        )
        .order_by(DeckMarketplaceItem.created_at.asc(), DeckMarketplaceItem.id.asc())
        .first()
    )
    if deck_item:
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
        deck_item.price_cents = 0
        deck_item.publish_status = "published"
        deck_item.is_official = True
        deck_item.published_at = deck_item.published_at or datetime.utcnow()
        return False

    db.session.add(
        DeckMarketplaceItem(
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
            price_cents=0,
            version="1.0.0",
            publish_status="published",
            is_official=True,
            published_at=datetime.utcnow(),
        )
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


def _load_seed_rows(file_path: Path) -> List[Dict[str, str | None]]:
    delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
    with file_path.open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile, delimiter=delimiter)
        if not reader.fieldnames:
            raise click.ClickException(f"Missing header row in file: {file_path}")
        mapping = _build_header_mapping(reader.fieldnames)
        rows: List[Dict[str, str | None]] = []
        for raw in reader:
            if not raw:
                continue
            deck = (raw.get(mapping["deck"]) or "").strip()
            word = (raw.get(mapping["word"]) or "").strip()
            if not deck or not word:
                continue
            payload: Dict[str, str | None] = {"deck": deck, "word": word}
            for field in SEED_OPTIONAL_FIELDS:
                source_key = mapping.get(field)
                if not source_key:
                    payload[field] = None
                    continue
                cleaned = (raw.get(source_key) or "").replace("\r", "").strip()
                payload[field] = cleaned or None
            rows.append(payload)
        return rows


def _legacy_entry_to_field_values(entry: VocabularyEntry) -> Dict[str, str]:
    """Map VocabularyEntry columns into default Flama note field_values JSON."""
    return {
        "word": entry.word or "",
        "hanviet": entry.hanviet or "",
        "reading": entry.reading or "",
        "translation_vi": entry.translation_vi or "",
        "meaning_jp": entry.meaning_jp or "",
        "meaning_vi": entry.meaning_vi or "",
        "usage_jp": entry.usage_jp or "",
        "usage_vi": entry.usage_vi or "",
        "example_jp": entry.example_jp or "",
        "example_vi": entry.example_vi or "",
        "additional_note_jp": entry.additional_note_jp or "",
        "additional_note_vi": entry.additional_note_vi or "",
        "image": entry.image or "",
        "diagram": entry.diagram or "",
        "word_audio": entry.word_audio or "",
        "example_audio": entry.example_audio or "",
    }
