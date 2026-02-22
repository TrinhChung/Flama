"""CLI commands for data seeding and maintenance."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List

import click
from flask import Flask
from sqlalchemy import func

from models import db
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_structure import VocabularyLevel, VocabularyLesson, VocabularyTopic

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
SEED_MIN_PAGE_SIZE = 60


def register_cli_commands(app: Flask) -> None:
    """Register custom Flask CLI commands."""

    @app.cli.command("vocab-seed")
    @click.option(
        "--path",
        "seed_path",
        default="static/seed_data",
        show_default=True,
        help="Path to seed folder (relative to project root or absolute).",
    )
    @click.option(
        "--level",
        "level_name",
        default="Seed Data",
        show_default=True,
        help="Vocabulary level name used to store seeded topics.",
    )
    @click.option(
        "--replace-lessons",
        is_flag=True,
        default=False,
        help="Replace lessons with the same title in each topic if they already exist.",
    )
    def vocab_seed(seed_path: str, level_name: str, replace_lessons: bool) -> None:
        """Seed vocabulary from folder structure.

        - Folder name under seed path -> topic name
        - File name (.tsv/.csv) -> lesson title
        """

        root = _resolve_seed_path(seed_path)
        if not root.exists() or not root.is_dir():
            raise click.ClickException(f"Seed path not found: {root}")

        level_name_clean = level_name.strip()
        if not level_name_clean:
            raise click.ClickException("Level name cannot be empty.")

        level = VocabularyLevel.query.filter_by(name=level_name_clean).first()
        if not level:
            level = VocabularyLevel(
                name=level_name_clean,
                position=_next_level_position(),
            )
            db.session.add(level)
            db.session.flush()
            click.echo(f"Created level: {level.name}")
        else:
            click.echo(f"Using existing level: {level.name}")

        topic_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=_natural_sort_key)
        if not topic_dirs:
            click.echo("No topic folders found.")
            db.session.commit()
            return

        created_topics = 0
        created_lessons = 0
        created_entries = 0
        replaced_lessons = 0
        skipped_lessons = 0

        for topic_dir in topic_dirs:
            topic_name = topic_dir.name.strip()
            if not topic_name:
                continue

            topic = VocabularyTopic.query.filter_by(level_id=level.id, name=topic_name).first()
            if not topic:
                topic = VocabularyTopic(
                    level_id=level.id,
                    name=topic_name,
                    position=_next_topic_position(level.id),
                )
                db.session.add(topic)
                db.session.flush()
                created_topics += 1
                click.echo(f"Created topic: {topic.name}")
            else:
                click.echo(f"Using existing topic: {topic.name}")

            seed_files = sorted(
                (
                    p
                    for p in topic_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in SEED_SUPPORTED_SUFFIXES
                ),
                key=_natural_sort_key,
            )
            if not seed_files:
                click.echo(f"  No seed files in topic: {topic.name}")
                continue

            for seed_file in seed_files:
                lesson_title = seed_file.stem.strip() or seed_file.name
                existing_lesson = VocabularyLesson.query.filter_by(
                    topic_id=topic.id, title=lesson_title
                ).first()
                if existing_lesson and not replace_lessons:
                    skipped_lessons += 1
                    click.echo(f"  Skip existing lesson: {lesson_title}")
                    continue

                rows = _load_seed_rows(seed_file)
                if existing_lesson and replace_lessons:
                    db.session.delete(existing_lesson)
                    db.session.flush()
                    replaced_lessons += 1
                    click.echo(f"  Replacing lesson: {lesson_title}")

                lesson = VocabularyLesson(
                    topic_id=topic.id,
                    title=lesson_title,
                    position=_next_lesson_position(topic.id),
                    page_size=max(SEED_MIN_PAGE_SIZE, len(rows)),
                )
                db.session.add(lesson)
                db.session.flush()

                if rows:
                    entries = []
                    for row in rows:
                        entry = VocabularyEntry(
                            lesson_id=lesson.id,
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
                    created_entries += len(entries)

                created_lessons += 1
                click.echo(f"  Added lesson: {lesson_title} ({len(rows)} rows)")

        db.session.commit()
        click.echo(
            "Done. "
            f"topics+{created_topics}, lessons+{created_lessons}, "
            f"entries+{created_entries}, replaced_lessons={replaced_lessons}, "
            f"skipped_lessons={skipped_lessons}"
        )


def _resolve_seed_path(seed_path: str) -> Path:
    candidate = Path(seed_path)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parent.parent / candidate


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


def _next_level_position() -> int:
    max_pos = db.session.query(func.max(VocabularyLevel.position)).scalar()
    return (max_pos or 0) + 1


def _next_topic_position(level_id: int) -> int:
    max_pos = (
        db.session.query(func.max(VocabularyTopic.position))
        .filter(VocabularyTopic.level_id == level_id)
        .scalar()
    )
    return (max_pos or 0) + 1


def _next_lesson_position(topic_id: int) -> int:
    max_pos = (
        db.session.query(func.max(VocabularyLesson.position))
        .filter(VocabularyLesson.topic_id == topic_id)
        .scalar()
    )
    return (max_pos or 0) + 1


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
