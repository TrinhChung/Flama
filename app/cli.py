"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import click
from flask import Flask

from app.services.flashcard_import import ImportValidationError, read_delimited_rows
from app.services.flashcard_legacy import ensure_legacy_note_type, ensure_quiz_note_type
from app.services.user_roles import ensure_default_user_roles
from app.services.tts_provider_service import (
    VOICEVOX_AUDIO_BASE_URL,
    VOICEVOX_POINTS_URL,
    VOICEVOX_SPEAKERS_URL,
    ensure_default_tts_providers,
)
from app.services import flashcards_share
from models import db
from models.flashcard import Card, DeckMarketplaceItem, Note
from models.user import User
from models.user_role import UserRole
from models.deck import Deck
from models.card_progress import CardProgress

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


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

    @app.cli.command("clone-cutover-overlay")
    @click.option(
        "--no-fail-on-mismatch",
        is_flag=True,
        default=False,
        help="Continue processing installs even when one legacy install cannot be migrated cleanly.",
    )
    def clone_cutover_overlay(no_fail_on_mismatch: bool) -> None:
        """One-shot cutover from legacy clone rows to logical overlay model."""
        summary = flashcards_share.cutover_clone_model_to_overlay_only(
            fail_on_mismatch=not no_fail_on_mismatch,
        )
        db.session.commit()
        click.echo(
            "Cutover done. "
            f"total={summary.get('total_installs', 0)}, "
            f"migrated={summary.get('migrated', 0)}, "
            f"failed={summary.get('failed', 0)}, "
            f"deck_map_rows={summary.get('deck_map_rows', 0)}, "
            f"note_pairs={summary.get('note_pairs', 0)}, "
            f"note_overrides={summary.get('note_overrides', 0)}, "
            f"progress_rows={summary.get('progress_rows', 0)}"
        )
        if summary.get("errors"):
            click.echo("Errors:")
            for error in summary.get("errors", []):
                click.echo(
                    f"- deck_install_id={error.get('deck_install_id')}: {error.get('message')}"
                )

    @app.cli.command("user-role-seed")
    def user_role_seed() -> None:
        """Seed default user roles and backfill users missing role mapping."""
        ensure_default_user_roles(db.session)
        db.session.commit()
        roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
        codes = ", ".join(role.code for role in roles)
        click.echo(f"Done. Seeded roles: {codes}")

    @app.cli.command("tts-provider-seed")
    def tts_provider_seed() -> None:
        """Seed default global TTS providers (currently VoiceVox)."""
        result = ensure_default_tts_providers(db.session)
        db.session.commit()
        click.echo(
            "Done. "
            f"created={result.get('created', 0)}, "
            f"updated={result.get('updated', 0)}. "
            f"VoiceVox endpoints: audio={VOICEVOX_AUDIO_BASE_URL}, "
            f"speakers={VOICEVOX_SPEAKERS_URL}, points={VOICEVOX_POINTS_URL}."
        )

    @app.cli.command("dev-purge-data")
    @click.option("--yes", is_flag=True, default=False, help="Confirm destructive purge.")
    def dev_purge_data(yes: bool) -> None:
        """Delete all application rows while keeping schema/migrations."""
        if not yes:
            raise click.ClickException("Refusing to purge data without --yes")

        bind = db.session.get_bind()
        dialect = bind.dialect.name if bind is not None else ""
        is_mysql = str(dialect).lower().startswith("mysql")

        try:
            if is_mysql:
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=0"))

            for table in reversed(db.metadata.sorted_tables):
                # Alembic migration tracking (if present in metadata) must be preserved.
                if table.name == "alembic_version":
                    continue
                db.session.execute(table.delete())

            db.session.commit()
            click.echo("Done. Purged all application data rows.")
        except Exception as exc:  # pragma: no cover - defensive rollback path
            db.session.rollback()
            raise click.ClickException(f"Failed to purge data: {exc}") from exc
        finally:
            if is_mysql:
                db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=1"))
                db.session.commit()

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
            return

        target_user = User.query.get(owner_user_id) if owner_user_id else User.query.order_by(User.id.asc()).first()
        if target_user is None:
            raise click.ClickException("No user found. Create at least one user before running vocab-seed.")

        note_type, template = ensure_legacy_note_type(db.session, target_user.id)
        quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, target_user.id)
        click.echo(f"Seeding from: {root}")
        click.echo(
            f"Using owner_user_id={target_user.id}, note_type={note_type.id}, template={template.id}"
        )
        click.echo(
            f"Also ensured quiz_note_type={quiz_note_type.id}, template={quiz_template.id}"
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
        )
        .order_by(Deck.id.asc())
        .first()
    )
    if deck:
        if deck.owner_user_id is None:
            deck.owner_user_id = owner_user_id
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
    leaf_name = file_path.stem.strip() or file_path.name
    leaf_deck, created = _get_or_create_deck(
        parent_deck_id=parent_deck_id,
        owner_user_id=owner_user_id,
        name=leaf_name,
        description=f"Seeded from {file_path.name}",
        stats=stats,
    )

    existing_count = (
        db.session.query(db.func.count(Note.id))
        .filter(
            Note.deck_id == leaf_deck.id,
            Note.user_id == owner_user_id,
            Note.note_type_id == note_type_id,
        )
        .scalar()
        or 0
    )
    if existing_count and not replace_existing:
        stats.skipped_files += 1
        click.echo(f"  Skip file (already seeded): {file_path.name}")
        return
    if existing_count and replace_existing:
        existing_notes = (
            Note.query.filter(
                Note.deck_id == leaf_deck.id,
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
        if existing_card_ids:
            CardProgress.query.filter(
                CardProgress.card_id.in_(existing_card_ids)
            ).delete(synchronize_session=False)
        if existing_note_ids:
            Card.query.filter(Card.note_id.in_(existing_note_ids)).delete(synchronize_session=False)
            Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)
        stats.replaced_files += 1
        click.echo(f"  Replace file deck: {file_path.name}")

    rows = _load_seed_rows(file_path)
    if not rows:
        stats.skipped_files += 1
        click.echo(f"  Skip empty file: {file_path.name}")
        return

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=owner_user_id,
                deck_id=leaf_deck.id,
                field_values=_seed_row_to_field_values(row),
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
            )
        )
    db.session.add_all(cards)
    db.session.flush()

    stats.created_notes += len(notes)
    stats.created_cards += len(cards)
    stats.seeded_files += 1
    deck_state = "Created" if created else "Updated"
    click.echo(f"  {deck_state} leaf deck: {leaf_name} ({len(rows)} rows)")


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


def _load_seed_rows_from_legacy_rows(rows: List[List[str]], file_path: Path) -> List[Dict[str, str | None]]:
    items: List[Dict[str, str | None]] = []

    for row_index, row_values in enumerate(rows, start=1):
        if len(row_values) < 2:
            raise click.ClickException(
                f"Unsupported legacy seed row in {file_path} at data row {row_index}: expected at least 2 columns."
            )

        payload: Dict[str, str | None] = {
            field_name: _clean_seed_cell(row_values[index]) if index < len(row_values) else None
            for index, field_name in enumerate(SEED_LEGACY_POSITIONAL_FIELDS)
        }
        deck = payload.get("deck")
        word = payload.get("word")
        if not deck or not word:
            continue

        normalized_payload: Dict[str, str | None] = {"deck": deck, "word": word}
        for field in SEED_OPTIONAL_FIELDS:
            normalized_payload[field] = payload.get(field)
        items.append(normalized_payload)

    return items


def _load_seed_rows(file_path: Path) -> List[Dict[str, str | None]]:
    try:
        raw_rows, _ = read_delimited_rows(
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
    return _load_seed_rows_from_legacy_rows(raw_rows, file_path)


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
    root = Path(__file__).resolve().parent.parent / QUIZ_DUMP_DIR
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
    if existing_note_ids:
        existing_card_ids = [
            row[0]
            for row in db.session.query(Card.id)
            .filter(Card.note_id.in_(existing_note_ids))
            .all()
            if row and row[0]
        ]
        if existing_card_ids:
            CardProgress.query.filter(
                CardProgress.card_id.in_(existing_card_ids)
            ).delete(synchronize_session=False)
        Card.query.filter(Card.note_id.in_(existing_note_ids)).delete(synchronize_session=False)
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

    cards = [Card(note_id=note.id, template_id=template_id) for note in notes]
    db.session.add_all(cards)
    db.session.flush()

    stats.created_notes += len(notes)
    stats.created_cards += len(cards)
    stats.seeded_files += 1
    return quiz_deck, len(notes)
