"""Audit legacy schema usage before dropping old vocabulary tables/columns."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app  # noqa: E402
from models import db  # noqa: E402
from models.flashcard import Card, LegacyMigrationMap, Note, ReviewEvent  # noqa: E402
from models.vocabulary_deck import VocabularyDeck  # noqa: E402
from models.vocabulary_entry import VocabularyEntry  # noqa: E402
from models.vocabulary_progress import VocabularyProgress  # noqa: E402


def _count(model) -> int:
    return int(db.session.query(func.count(model.id)).scalar() or 0)


def _print_metric(label: str, value: int) -> None:
    print(f"{label:<48} {value}")


def main() -> int:
    app = create_app()
    with app.app_context():
        print("=== Legacy Schema Audit ===")
        print("")

        _print_metric("vocabulary_entries rows", _count(VocabularyEntry))
        _print_metric("vocabulary_progress rows", _count(VocabularyProgress))
        _print_metric("legacy_migration_maps rows", _count(LegacyMigrationMap))
        _print_metric("notes rows", _count(Note))
        _print_metric("cards rows", _count(Card))
        _print_metric("review_events rows", _count(ReviewEvent))
        _print_metric(
            "vocabulary_decks rows missing owner_user_id",
            int(
                db.session.query(func.count(VocabularyDeck.id))
                .filter(VocabularyDeck.owner_user_id.is_(None))
                .scalar()
                or 0
            ),
        )

        print("")
        print("=== Bridging Columns ===")
        _print_metric(
            "progress rows with entry_id",
            int(
                db.session.query(func.count(VocabularyProgress.id))
                .filter(VocabularyProgress.entry_id.isnot(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "progress rows with new_card_id",
            int(
                db.session.query(func.count(VocabularyProgress.id))
                .filter(VocabularyProgress.new_card_id.isnot(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "progress rows with both entry_id + new_card_id",
            int(
                db.session.query(func.count(VocabularyProgress.id))
                .filter(
                    VocabularyProgress.entry_id.isnot(None),
                    VocabularyProgress.new_card_id.isnot(None),
                )
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "review_events rows with entry_id",
            int(
                db.session.query(func.count(ReviewEvent.id))
                .filter(ReviewEvent.entry_id.isnot(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "review_events card_id starting with 'entry:'",
            int(
                db.session.query(func.count(ReviewEvent.id))
                .filter(ReviewEvent.card_id.like("entry:%"))
                .scalar()
                or 0
            ),
        )

        print("")
        print("=== Mapping Health ===")
        _print_metric(
            "legacy entries missing migration map",
            int(
                db.session.query(func.count(VocabularyEntry.id))
                .outerjoin(LegacyMigrationMap, LegacyMigrationMap.entry_id == VocabularyEntry.id)
                .filter(LegacyMigrationMap.id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "migration maps missing source entry",
            int(
                db.session.query(func.count(LegacyMigrationMap.id))
                .outerjoin(VocabularyEntry, VocabularyEntry.id == LegacyMigrationMap.entry_id)
                .filter(VocabularyEntry.id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "migration maps missing note",
            int(
                db.session.query(func.count(LegacyMigrationMap.id))
                .outerjoin(Note, Note.id == LegacyMigrationMap.note_id)
                .filter(Note.id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "migration maps missing card",
            int(
                db.session.query(func.count(LegacyMigrationMap.id))
                .outerjoin(Card, Card.id == LegacyMigrationMap.card_id)
                .filter(Card.id.is_(None))
                .scalar()
                or 0
            ),
        )

        print("")
        print("Use this report before dropping: vocabulary_* tables,")
        print("VocabularyProgress.entry_id, ReviewEvent.entry_id, LegacyMigrationMap.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
