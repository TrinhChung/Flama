"""Phase 6 application occurrences: every Template and Card has one (P6-04/P6-05)."""

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app import create_app
from app.services.study_note_attribution_service import backfill_phase6_attribution
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template
from models.user import User

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
        template = Template(note_type_id=self.note_type.id, name=name, front_html="{{Word}}",
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

    def test_new_card_is_bound_to_its_template_occurrence(self):
        template = self._template()
        card = Card(note_id=self._note().id, template_id=template.id)
        db.session.add(card)
        db.session.commit()
        occurrence = StudyApplication.query.filter_by(template_id=template.id).one()
        self.assertEqual(card.application_id, occurrence.id)

    def test_template_and_cards_created_in_one_flush_share_one_occurrence(self):
        template = Template(note_type_id=self.note_type.id, name="Pending", front_html="", back_html="")
        notes = [self._note(), self._note()]
        db.session.add(template)
        db.session.add_all(Card(note=note, template=template) for note in notes)
        db.session.commit()
        occurrences = StudyApplication.query.filter_by(template_id=template.id).all()
        self.assertEqual(len(occurrences), 1)
        self.assertEqual({card.application_id for card in Card.query.all()}, {occurrences[0].id})

    def test_card_for_template_created_before_the_seam_creates_the_missing_occurrence(self):
        template = self._template()
        db.session.execute(text("DELETE FROM study_applications"))
        db.session.commit()
        card = Card(note_id=self._note().id, template_id=template.id)
        db.session.add(card)
        db.session.commit()
        self.assertIsNotNone(card.application_id)
        self.assertEqual(StudyApplication.query.count(), 1)

    def test_explicit_occurrence_is_kept(self):
        template = self._template()
        repeated = StudyApplication(note_type_id=self.note_type.id, template_id=template.id,
                                    occurrence_key="repeat-1", source_ord=None, status_code="ACTIVE")
        db.session.add(repeated)
        db.session.flush()
        card = Card(note_id=self._note().id, template_id=template.id, application=repeated)
        db.session.add(card)
        db.session.commit()
        self.assertEqual(card.application_id, repeated.id)

    def test_new_review_events_and_connect_refs_snapshot_their_note(self):
        from models.connect_source_card_ref import ConnectSourceCardRef

        template = self._template()
        notes = [self._note(), self._note()]
        cards = [Card(note_id=note.id, template_id=template.id) for note in notes]
        db.session.add_all(cards)
        db.session.commit()
        db.session.add_all([
            ReviewEvent(user_id=self.user.id, card_id=cards[0].id, reviewed_at=cards[0].created_at,
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
            {cards[0].id: notes[0].id, "missing": None},
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
        cards = {t.id: Card(note_id=note.id, template_id=t.id) for t in (front, back)}
        db.session.add_all(cards.values())
        db.session.commit()
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
        Card.query.filter_by(template_id=back.id).delete()
        StudyApplication.query.filter_by(template_id=back.id).delete()
        db.session.delete(back)
        db.session.commit()
        db.session.expire_all()
        with self.assertRaises(AnkiSyncError):
            _card_for_ord(ref, 1)
        self.assertEqual(_card_for_ord(ref, 0).id, cards[front.id].id)

    def test_migration_backfills_occurrences_cards_and_note_snapshots(self):
        template = self._template()
        note = self._note()
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.commit()
        db.session.add(ReviewEvent(user_id=self.user.id, card_id=card.id, reviewed_at=card.created_at,
                                   rating="good", mode="review"))
        db.session.add(ReviewEvent(user_id=self.user.id, card_id="gone", reviewed_at=card.created_at,
                                   rating="good", mode="review"))
        db.session.commit()
        # Pretend the rows predate migration 46.
        db.session.execute(text("UPDATE cards SET application_id = NULL"))
        db.session.execute(text("UPDATE review_events SET note_id = NULL"))
        db.session.execute(text("DELETE FROM study_applications"))
        db.session.commit()
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            migration.upgrade()  # idempotent
        db.session.expire_all()
        occurrence = StudyApplication.query.one()
        self.assertEqual((occurrence.template_id, occurrence.occurrence_key), (template.id, "compat"))
        self.assertEqual(db.session.get(Card, card.id).application_id, occurrence.id)
        # The migration leaves old events alone; the batched backfill stamps them.
        self.assertEqual(ReviewEvent.query.filter(ReviewEvent.note_id.isnot(None)).count(), 0)
        dry_run = backfill_phase6_attribution(apply=False)
        self.assertEqual((dry_run.pending_events, dry_run.unresolved_events), (2, 1))
        self.assertEqual(ReviewEvent.query.filter(ReviewEvent.note_id.isnot(None)).count(), 0)
        report = backfill_phase6_attribution(apply=True, batch_size=1)
        self.assertEqual((report.attributed_events, report.unresolved_events, report.batches), (1, 1, 2))
        db.session.expire_all()
        self.assertEqual(
            {row.card_id: row.note_id for row in ReviewEvent.query.all()},
            {card.id: note.id, "gone": None},
        )
        rerun = backfill_phase6_attribution(apply=True)
        self.assertEqual((rerun.pending_events, rerun.attributed_events), (1, 0))

    def test_backfill_repairs_rows_written_by_the_previous_release(self):
        """The deploy migrates while the old release serves; its writes are repaired."""
        from models.connect_source_card_ref import ConnectSourceCardRef

        front = self._template()
        notes = [self._note(), self._note()]
        cards = [Card(note_id=note.id, template_id=front.id) for note in notes]
        db.session.add_all(cards)
        db.session.commit()
        ref = ConnectSourceCardRef(user_id=self.user.id, source_key="src", external_card_id="c1",
                                   external_note_id="n1", source_ord=0, card_id=cards[0].id)
        db.session.add(ref)
        db.session.commit()
        now = cards[0].created_at
        # Old code: a Template and Cards with no occurrence, a duplicate Card
        # (the unique (note, template) key is gone), a ref re-bound without its Note.
        db.session.execute(text(
            "INSERT INTO templates (id, note_type_id, name, front_html, back_html, shared_css, position, "
            "is_default, created_at, updated_at) VALUES ('t-old', :nt, 'Old', '', '', '', 1, 0, :now, :now)"
        ), {"nt": self.note_type.id, "now": now})
        for card_id, note_id, template_id in (
            ("c-old-0", notes[0].id, "t-old"), ("c-old-1", notes[1].id, "t-old"),
            ("c-dup", notes[0].id, front.id),
        ):
            db.session.execute(text(
                "INSERT INTO cards (id, note_id, template_id, created_at, updated_at) "
                "VALUES (:id, :note, :template, :now, :now)"
            ), {"id": card_id, "note": note_id, "template": template_id, "now": now})
        db.session.execute(text(
            "UPDATE connect_source_card_refs SET card_id = :card, note_id = NULL WHERE id = :id"
        ), {"card": "c-old-1", "id": ref.id})
        db.session.commit()

        dry_run = backfill_phase6_attribution(apply=False)
        self.assertEqual(
            (dry_run.templates_without_occurrence, dry_run.unbound_cards, dry_run.refs_pending),
            (1, 3, 1),
        )
        self.assertEqual(StudyApplication.query.filter_by(template_id="t-old").count(), 0)
        report = backfill_phase6_attribution(apply=True, batch_size=1)
        self.assertEqual(
            (report.occurrences_created, report.cards_bound, report.duplicate_cards, report.refs_attributed),
            (1, 2, ["c-dup"], 1),
        )
        db.session.expire_all()
        old = StudyApplication.query.filter_by(template_id="t-old").one()
        self.assertEqual((old.occurrence_key, old.source_ord), (COMPAT_OCCURRENCE_KEY, 1))
        self.assertEqual(
            {row.id: row.application_id for row in Card.query.filter(Card.template_id == "t-old")},
            {"c-old-0": old.id, "c-old-1": old.id},
        )
        self.assertIsNone(db.session.get(Card, "c-dup").application_id)  # reported, kept
        self.assertEqual(db.session.get(ConnectSourceCardRef, ref.id).note_id, notes[1].id)
        rerun = backfill_phase6_attribution(apply=True)
        self.assertEqual((rerun.occurrences_created, rerun.cards_bound, rerun.refs_attributed), (0, 0, 0))
        self.assertEqual(rerun.duplicate_cards, ["c-dup"])


if __name__ == "__main__":
    unittest.main()
