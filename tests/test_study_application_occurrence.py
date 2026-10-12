"""Phase 6 application occurrences: every Template has one and presents it (P6-04/P6-05, ADR P11).

Cards are derived from Note x occurrence; the stored pre-P11 Card rows live on
in the immutable alias registry; historical repair tools are retired.
"""

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import ArgumentError

from app import create_app
from models import db
from models.card import Card, PresentationAlias, card_key
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template

migration = importlib.import_module("migrations.versions.20260930_000046_add_study_applications")


class StudyApplicationOccurrenceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(username="occurrence", email="occurrence@example.test")
        db.session.add(self.user)
        db.session.flush()
        self.deck = Deck(name="Occurrence", owner_user_id=self.user.id)
        self.note_type = NoteType(name="Occurrence", user_id=self.user.id)
        db.session.add_all([self.deck, self.note_type])
        db.session.flush()
        db.session.add(FieldDef(note_type_id=self.note_type.id, name="Word", field_type="text", position=0))
        db.session.commit()

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _template(self, name="Front", position=0):
        template = attach_template(db.session, owner_user_id=self.user.id, note_type_id=self.note_type.id, name=name, front_html="{{Word}}",
                            back_html="{{Word}}", position=position, is_default=position == 0)
        db.session.add(template)
        db.session.commit()
        return template

    def _note(self):
        note = Note(user_id=self.user.id, note_type_id=self.note_type.id, deck_id=self.deck.id,
                    field_values={"Word": "w"})
        db.session.add(note)
        db.session.flush()
        return note

    def test_new_template_gets_its_compatibility_occurrence(self):
        template = self._template(position=3)
        rows = StudyApplication.query.filter_by(template_id=template.id).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].occurrence_key, COMPAT_OCCURRENCE_KEY)
        self.assertEqual(rows[0].note_type_id, self.note_type.id)
        self.assertEqual(rows[0].source_ord, 3)

    def test_a_note_presents_its_template_through_the_occurrence(self):
        template = self._template()
        note = self._note()
        db.session.commit()
        occurrence = StudyApplication.query.filter_by(template_id=template.id).one()
        card = Card.query.filter_by(note_id=note.id).one()
        self.assertEqual((card.id, card.application_id, card.template_id),
                         (card_key(note.id, occurrence.id), occurrence.id, template.id))

    def test_template_and_notes_created_in_one_flush_share_one_occurrence(self):
        template = attach_template(db.session, owner_user_id=self.user.id, note_type_id=self.note_type.id, name="Pending", front_html="", back_html="")
        notes = [self._note(), self._note()]
        db.session.add(template)
        db.session.commit()
        occurrences = StudyApplication.query.filter_by(template_id=template.id).all()
        self.assertEqual(len(occurrences), 1)
        self.assertEqual({card.application_id for card in Card.query.all()}, {occurrences[0].id})
        self.assertEqual({card.note_id for card in Card.query.all()}, {note.id for note in notes})

    def test_cards_are_derived_and_cannot_be_written(self):
        template = self._template()
        note = self._note()
        with self.assertRaises(TypeError):
            db.session.add(Card(note_id=note.id, template_id=template.id))
            db.session.flush()
        db.session.rollback()
        with self.assertRaises((TypeError, ArgumentError)):  # no table to write
            Card.query.filter_by(template_id=template.id).delete()
        db.session.rollback()

    def test_a_repeated_occurrence_presents_a_second_card(self):
        template = self._template()
        note = self._note()
        repeated = StudyApplication(note_type_id=self.note_type.id, template_id=template.id,
                                    occurrence_key="repeat-1", source_ord=None, status_code="ACTIVE")
        db.session.add(repeated)
        db.session.commit()
        cards = Card.query.filter_by(note_id=note.id).all()
        self.assertEqual(len(cards), 2)
        self.assertIn(card_key(note.id, repeated.id), {card.id for card in cards})

    def test_new_review_events_and_connect_refs_snapshot_their_note(self):
        from models.connect_source_card_ref import ConnectSourceCardRef

        template = self._template()
        notes = [self._note(), self._note()]
        db.session.commit()
        cards = [Card.query.filter_by(note_id=note.id).one() for note in notes]
        # A pre-P11 ID still names its Card through the registry.
        db.session.execute(PresentationAlias.__table__.insert().values(
            id="legacy-1", note_id=notes[1].id, template_id=template.id,
            application_id=cards[1].application_id, created_at=cards[1].created_at,
            updated_at=cards[1].updated_at))
        db.session.commit()
        db.session.add_all([
            ReviewEvent(user_id=self.user.id, card_id=cards[0].id, reviewed_at=cards[0].created_at,
                        rating="good", mode="review"),
            ReviewEvent(user_id=self.user.id, card_id="legacy-1", reviewed_at=cards[0].created_at,
                        rating="good", mode="review"),
            ReviewEvent(user_id=self.user.id, card_id="missing", reviewed_at=cards[0].created_at,
                        rating="good", mode="review"),
        ])
        ref = ConnectSourceCardRef(user_id=self.user.id, source_key="src", external_card_id="c1",
                                   external_note_id="n1", source_ord=0, card_id=cards[0].id)
        db.session.add(ref)
        db.session.commit()
        self.assertEqual(
            {row.card_id: row.note_id for row in ReviewEvent.query.all()},
            {cards[0].id: notes[0].id, "legacy-1": notes[1].id, "missing": None},
        )
        self.assertEqual(ref.note_id, notes[0].id)
        ref.card_id = cards[1].id  # a re-sync maps the ordinal to another Card
        db.session.commit()
        self.assertEqual(ref.note_id, notes[1].id)

    def test_anki_ordinal_follows_the_occurrence_not_the_template_position(self):
        from types import SimpleNamespace

        from app.services.anki_sync_service import AnkiSyncError, _card_for_ord

        front = self._template("Front", position=0)
        back = self._template("Back", position=1)
        note = self._note()
        db.session.commit()
        cards = {t.id: Card.query.filter_by(note_id=note.id, template_id=t.id).one() for t in (front, back)}
        ref = SimpleNamespace(note=note)
        self.assertEqual(_card_for_ord(ref, 0).id, cards[front.id].id)
        self.assertEqual(_card_for_ord(ref, 1).id, cards[back.id].id)

        # Reorder: positions swap, the Anki ordinals must not.
        front.position, back.position = 1, 0
        db.session.commit()
        db.session.expire_all()
        self.assertEqual(_card_for_ord(ref, 0).id, cards[front.id].id)
        self.assertEqual(_card_for_ord(ref, 1).id, cards[back.id].id)

        # Remove the "Back" Template: ordinal 1 is refused, not remapped to Front.
        db.session.delete(back)  # its occurrence, and so its Card, go with it
        db.session.commit()
        db.session.expire_all()
        with self.assertRaises(AnkiSyncError):
            _card_for_ord(ref, 1)
        self.assertEqual(_card_for_ord(ref, 0).id, cards[front.id].id)

    # The pre-P11 concurrent attribution repair command is retired. Historical
    # migration-chain and alias/backfill conservation are qualified in
    # test_retirement_fresh_migration_chain and test_derived_card_retirement_migration.


if __name__ == "__main__":
    unittest.main()
