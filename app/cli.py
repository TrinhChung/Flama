"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import click
from flask import Flask

from models import db
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry

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
    replaced_files: int = 0
    skipped_files: int = 0


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

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
    def vocab_seed(seed_path: str, replace_lessons: bool) -> None:
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

        click.echo(f"Seeding from: {root}")
        for start_dir in start_dirs:
            _seed_dir_to_deck(
                directory=start_dir,
                parent_deck_id=None,
                replace_existing=replace_lessons,
                stats=stats,
            )

        db.session.commit()
        click.echo(
            "Done. "
            f"decks+{stats.created_decks}, files_seeded={stats.seeded_files}, "
            f"entries+{stats.created_entries}, replaced_files={stats.replaced_files}, "
            f"skipped_files={stats.skipped_files}"
        )


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
        return deck, False

    deck = VocabularyDeck(
        parent_id=parent_deck_id,
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
    replace_existing: bool,
    stats: SeedStats,
) -> None:
    deck_name = directory.name.strip()
    if not deck_name:
        return

    deck_node, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
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
            replace_existing=replace_existing,
            stats=stats,
        )

    # Recurse subfolders for nested deck hierarchy.
    subdirs = sorted((p for p in directory.iterdir() if p.is_dir()), key=_natural_sort_key)
    for child_dir in subdirs:
        _seed_dir_to_deck(
            directory=child_dir,
            parent_deck_id=deck_node.id,
            replace_existing=replace_existing,
            stats=stats,
        )


def _seed_file_to_leaf_deck(
    *,
    file_path: Path,
    parent_deck_id: int,
    replace_existing: bool,
    stats: SeedStats,
) -> None:
    leaf_name = file_path.stem.strip() or file_path.name
    leaf_deck, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
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
    stats.created_entries += len(entries)
    stats.seeded_files += 1
    deck_state = "Created" if created else "Updated"
    click.echo(f"  {deck_state} leaf deck: {leaf_name} ({len(entries)} rows)")


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

