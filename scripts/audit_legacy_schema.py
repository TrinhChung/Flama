"""Audit current deck/note/card schema health (legacy bridge removed)."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app  # noqa: E402
from models import db  # noqa: E402
from models.flashcard import Card, Note, ReviewEvent  # noqa: E402
from models.deck import Deck  # noqa: E402
from models.card_progress import CardProgress  # noqa: E402


def _count(model) -> int:
    return int(db.session.query(func.count(model.id)).scalar() or 0)


def _print_metric(label: str, value: int) -> None:
    print(f"{label:<48} {value}")


def main() -> int:
    app = create_app()
    with app.app_context():
        print("=== Current Schema Audit ===")
        print("")

        _print_metric("decks rows", _count(Deck))
        _print_metric("notes rows", _count(Note))
        _print_metric("cards rows", _count(Card))
        _print_metric("card_progress rows", _count(CardProgress))
        _print_metric("review_events rows", _count(ReviewEvent))

        print("")
        print("=== Integrity Checks ===")
        _print_metric(
            "decks missing owner_user_id",
            int(
                db.session.query(func.count(Deck.id))
                .filter(Deck.owner_user_id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "notes missing deck_id",
            int(
                db.session.query(func.count(Note.id))
                .filter(Note.deck_id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "progress rows missing card_id",
            int(
                db.session.query(func.count(CardProgress.id))
                .filter(CardProgress.card_id.is_(None))
                .scalar()
                or 0
            ),
        )
        _print_metric(
            "progress rows missing card reference",
            int(
                db.session.query(func.count(CardProgress.id))
                .outerjoin(Card, Card.id == CardProgress.card_id)
                .filter(Card.id.is_(None))
                .scalar()
                or 0
            ),
        )

        print("")
        print("Schema is now card-based only: no entry bridge columns are expected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
