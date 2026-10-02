"""P9-04a: NOTE readers verify canonical state and need no CardProgress under CANONICAL_V1."""

from datetime import datetime, timezone
import unittest
from unittest import mock

from sqlalchemy import select

from app.repositories import note_analytics_read_repository as note_reads
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    StudyAuthorityReadError,
    load_study_authority_availability_snapshot,
    load_study_authority_card_reads,
    summarize_study_authority_queue,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_availability import StudyProgressAvailability
from tests import test_study_direct_note_replay as fixtures

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
NOW = datetime(2026, 10, 1)


def _without_move_tokens(value):
    """Dashboard deck move tokens (and their MID- aliases) are time-signed."""
    if isinstance(value, dict):
        return {key: _without_move_tokens(item) for key, item in value.items() if "move" not in key}
    if isinstance(value, list):
        return [_without_move_tokens(item) for item in value]
    return value


class StudyCanonicalReadTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _add_pristine_note(self):
        template_card = db.session.get(Card, self.card_ids[0])
        note = Note(user_id=self.user_id, note_type_id=template_card.note.note_type_id,
                    deck_id=self.deck_id, field_values={"Word": "pristine"})
        db.session.add(note)
        db.session.flush()
        db.session.add(Card(note_id=note.id, template_id=template_card.template_id))
        db.session.commit()

    def _set_profile(self, profile_code):
        row = db.session.get(StudyAuthorityStorageProfile, 1)
        if row is None:
            row = StudyAuthorityStorageProfile(id=1, created_at=NOW, updated_at=NOW)
            db.session.add(row)
        row.profile_code = profile_code
        db.session.commit()

    def _scope_and_cards(self):
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == self.user_id, Note.deck_id == self.deck_id)
        scope = query.with_entities(
            Note.deck_id.label("deck_id"), Card.id.label("card_id"), Card.note_id.label("note_id"),
        ).order_by(None).subquery("scope")
        return scope, query.order_by(Card.id.asc()).all()

    def _read_everything(self, profile):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        scope, cards = self._scope_and_cards()
        options = {str(card.id): resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)
                   for card in cards}
        reads = load_study_authority_card_reads(
            db.session, learner_user_id=self.user_id, cards=tuple(cards), now_utc=now,
            timezone_name="UTC", deck_options_by_card_id=options)
        snapshot = load_study_authority_availability_snapshot(
            db.session, learner_user_id=self.user_id, cards=cards, scope=scope, now_utc=now)
        rows = note_reads.note_card_rows(
            note_reads.learner_note_scope(learner_user_id=self.user_id, storage_profile=profile),
            learner_user_id=self.user_id, storage_profile=profile,
        ).subquery("rows")
        analytics = sorted(tuple(row) for row in db.session.execute(select(
            rows.c.card_id, rows.c.queue, rows.c.due_day, rows.c.due_at, rows.c.is_suspended,
            rows.c.violation)).all())
        summary = summarize_study_authority_queue(
            cards=tuple(cards), reads_by_card_id=snapshot, learner_user_id=self.user_id,
            now_utc=now, timezone_name="UTC")
        result = {
            "reads": {key: (value.availability, value.authority_revision, value.state_version)
                      for key, value in reads.items()},
            "snapshot": {key: value.availability for key, value in snapshot.items()},
            "analytics": analytics,
            "summary": summary,
        }
        db.session.rollback()
        return result

    def test_canonical_profile_reads_the_same_without_any_card_progress(self):
        self._answer()
        with self.app.app_context():
            self._add_pristine_note()
            projected = self._read_everything("PROJECTION_V1")
            self.assertTrue(all(row[-1] == 0 for row in projected["analytics"]))

            self._set_profile("CANONICAL_V1")
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()
            with mock.patch(
                "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
            ):
                canonical = self._read_everything("CANONICAL_V1")
        self.assertEqual(canonical, projected)

    def _read_endpoints(self):
        paths = [
            "/api/dashboard",
            "/api/statistics/overview",
            "/api/statistics/today-future",
        ] + [
            f"/api/browse/cards?deck_id={self.deck_id}{query}"
            for query in ("", "&status=new", "&status=learn", "&status=due", "&sort_dir=desc")
        ]
        responses = {}
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, (path, response.get_json()))
            responses[path] = _without_move_tokens(response.get_json())
        with self.app.app_context():
            from app.repositories import flashcards_share_repository as share_reads

            responses["reps"] = (
                share_reads.get_deck_reps_for_user_in_subtree(self.user_id, [self.deck_id]),
                share_reads.get_deck_reps_for_user_in_source_scope(self.user_id, [self.deck_id]),
                share_reads.get_note_type_reps_for_user(
                    self.user_id, str(db.session.get(Card, self.card_ids[0]).note.note_type_id)),
            )
            db.session.rollback()
        return responses

    def test_endpoints_answer_the_same_under_canonical_without_card_progress(self):
        self._answer()
        with self.app.app_context():
            self._add_pristine_note()
        with mock.patch("app.services.browse_card_service._utcnow", return_value=NOW):
            projected = self._read_endpoints()
            self.assertGreater(projected["reps"][0], 0)
            with self.app.app_context():
                self._set_profile("CANONICAL_V1")
                db.session.execute(CardProgress.__table__.delete())
                db.session.commit()
            with mock.patch(
                "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
            ):
                canonical = self._read_endpoints()
        for path in projected:
            with self.subTest(path=path):
                self.assertEqual(canonical[path], projected[path])

    def test_projection_profile_still_requires_its_projection(self):
        self._answer()
        with self.app.app_context():
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()
            with self.assertRaises(StudyAuthorityReadError) as refused:
                self._read_everything("PROJECTION_V1")
        self.assertEqual(refused.exception.code, "INCOMPLETE_AUTHORITY_COMPATIBILITY")

    def test_divergent_availability_fails_closed_under_both_profiles(self):
        self._answer()
        for profile, tamper in (
            ("PROJECTION_V1", {"due_day": 1}),
            ("CANONICAL_V1", {"due_day": 1}),
            ("CANONICAL_V1", {"is_buried": True}),
        ):
            with self.subTest(profile=profile, tamper=tamper), self.app.app_context():
                self._set_profile(profile)
                row = StudyProgressAvailability.query.first()
                original = {name: getattr(row, name) for name in tamper}
                for name, value in tamper.items():
                    setattr(row, name, value)
                db.session.commit()
                with mock.patch(
                    "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES",
                    BOTH_PROFILES,
                ), self.assertRaises(StudyAuthorityReadError) as refused:
                    self._read_everything(profile)
                self.assertEqual(refused.exception.code, "AUTHORITY_READ_PARITY_DIVERGED")
                db.session.rollback()
                row = StudyProgressAvailability.query.first()
                for name, value in original.items():
                    setattr(row, name, value)
                db.session.commit()


if __name__ == "__main__":
    unittest.main()
