"""NOTE behavior acceptance across native, session, Connect and overlay boundaries."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.connect import connect_bp
from app.services import browse_card_service, flashcards_share_service, study_composition_service, study_service, study_session_service, user_api_token_service
from app.services.anki_scheduler import _day_index
from app.services.connect.actions import add_note
from app.services.mcp import study_tools as mcp_study_tools
from app.validators.review_event import classify_review_event_payload
from app.repositories.study_repository import query_next_due_card_id, query_study_queue_counts
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_clone_added_note import DeckCloneAddedNote
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.connect_note_ref import ConnectNoteRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_review_event_ref import ConnectReviewEventRef
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_commit import StudySessionCommit
from models.user import User
from tests.note_progress_fixtures import stage_note_state, decode_note_state, subject_for_card
from tests.study_note_fixtures import attach_template, enroll_note_user, assert_retired_progress_absent


def _review_event_provenance():
    counts = {}
    for row in ReviewEvent.query.all():
        disposition = classify_review_event_payload(row.payload_json,
            scheduler_algorithm=row.scheduler_algorithm, algorithm_version=row.algorithm_version,
            scheduler_config_hash=row.scheduler_config_hash, study_session_id=row.study_session_id,
            client_event_id=row.client_event_id, sequence_no=row.sequence_no)
        source = (json.loads(row.payload_json or "{}" ).get("provenance") or {}).get("source_path")
        key = (disposition.category, source)
        counts[key] = counts.get(key, 0) + 1
    return counts


class StudyBehaviorAcceptanceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
                "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
                "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": True, "CONNECT_RATE_LIMIT_BACKEND": "local",
            }
        )
        self.app.register_blueprint(connect_bp)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # User 1 (Source author)
            author = User(
                username="author",
                email="author@example.com",
                timezone="Asia/Ho_Chi_Minh",
                is_admin=True,
            )
            author.set_password("password")

            # User 2 (Learner / Subscriber)
            learner = User(
                username="learner",
                email="learner@example.com",
                timezone="Asia/Ho_Chi_Minh",
                is_admin=False,
            )
            learner.set_password("password")

            db.session.add_all([author, learner])
            db.session.flush()

            enroll_note_user(db.session, author)
            enroll_note_user(db.session, learner)
            self.author_id = author.id
            self.learner_id = learner.id

            # NoteType & Template
            note_type = NoteType(user_id=author.id, name="Vocabulary NoteType")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            field_word = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
                identity_role="primary",
            )
            field_meaning = FieldDef(
                note_type_id=note_type.id,
                name="Meaning",
                field_type="text",
                position=1,
                required=True,
            )
            template = attach_template(db.session, owner_user_id=author.id,
                note_type_id=note_type.id,
                name="Recognition",
                position=0,
                is_default=True,
                front_html="{{Word}}",
                back_html="{{Meaning}}",
            )
            db.session.add_all([field_word, field_meaning, template])
            db.session.flush()
            self.template_id = template.id

            # Source Deck & Note & Card A
            deck = Deck(owner_user_id=author.id, name="JLPT N5 Vocab")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            note_a = Note(
                user_id=author.id,
                note_type_id=note_type.id,
                deck_id=deck.id,
                field_values={"Word": "猫", "Meaning": "Cat"},
            )
            note_b = Note(
                user_id=author.id,
                note_type_id=note_type.id,
                deck_id=deck.id,
                field_values={"Word": "犬", "Meaning": "Dog"},
            )
            db.session.add_all([note_a, note_b])
            db.session.flush()
            self.note_a_id = note_a.id
            self.note_b_id = note_b.id

            card_a = Card.query.filter_by(note_id=note_a.id, template_id=template.id).one()
            card_b = Card.query.filter_by(note_id=note_b.id, template_id=template.id).one()
            db.session.commit()
            self.card_a_id = card_a.id
            self.card_b_id = card_b.id

        self._login(self.author_id)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


    def _login(self, user_id):
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(user_id), True

    def _open(self):
        response = self.client.post("/api/study/sessions", json={"scope": "deck", "scope_id": self.deck_id,
            "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _event(self, snapshot, card, sequence=1):
        policy = snapshot["policies"][card["policy_key"]]
        event_id = str(uuid4())
        self.assertEqual(len(card["card_id"]), 73)
        return dict(event_id=event_id, operation_key=event_id, sequence=sequence, card_id=card["card_id"],
            rating="good", action_key="review.good", action_contract_version="1",
            trigger_key="scheduler.review.good", trigger_contract_version="1", policy_key=card["policy_key"],
            scheduler_offset_ms=0, duration_ms=2500, algorithm_key=snapshot["scheduler_algorithm"],
            algorithm_version=snapshot["algorithm_version"], config_schema_version=policy["config_schema_version"],
            config_hash=policy["config_hash"], study_session_id=snapshot["session_id"],
            **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"})

    def _commit_payload(self, snapshot, events):
        return dict(schema_version="study-commit.v3", commit_id=str(uuid4()),
            session_token=snapshot["session_token"], snapshot_hash=snapshot["snapshot_hash"],
            commit_reason="manual_exit", events=events, final_states=[])

    def _commit(self, snapshot, payload, expected=200):
        response = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload)
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def test_direct_native_review_mcp_and_session_have_exact_note_state_and_provenance(self):
        fixed_now = datetime(2026, 8, 29, 10)
        today = _day_index(fixed_now, 4, timezone_name="Asia/Ho_Chi_Minh")
        with self.app.app_context():
            note = Note(user_id=self.author_id, note_type_id=self.note_type_id,
                        deck_id=self.deck_id, field_values={"Word": "bird", "Meaning": "Bird"})
            db.session.add(note)
            db.session.flush()
            card_c_id = Card.query.filter_by(note_id=note.id).one().id
            for card_id in (self.card_a_id, self.card_b_id, card_c_id):
                self.assertEqual(len(card_id), 73)
                stage_note_state(db.session, user_id=self.author_id, card_id=card_id, now=fixed_now,
                    queue="review", interval_days=5, ease_factor=2.5, reps=3, due_day=today)
            db.session.commit()
        with patch("app.routes.flashcards.study.datetime", wraps=datetime) as route_clock, \
             patch("app.services.study_service.datetime", wraps=datetime) as review_clock, \
             patch("app.services.study_session_service.datetime", wraps=datetime) as session_clock:
            route_clock.utcnow.return_value = fixed_now
            review_clock.utcnow.return_value = fixed_now
            session_clock.utcnow.return_value = fixed_now
            response = self.client.post(f"/api/study/{self.card_a_id}/answer", json={
                "rating": "good", "operation_key": str(uuid4()), "duration_ms": 2500,
                "scope": "deck", "scope_id": self.deck_id, "timezone": "Asia/Ho_Chi_Minh"})
            self.assertEqual(response.status_code, 200, response.get_json())
            # The server-render next link, not the client-render alias.
            self.assertTrue(response.get_json()["next_card_url"].startswith("/api/study/next?"),
                response.get_json()["next_card_url"])
            with self.app.app_context():
                result = mcp_study_tools.submit_review(user_id=self.author_id, card_id=self.card_b_id,
                    rating="good", duration_ms=2500, operation_key=str(uuid4()))
                self.assertTrue(result["success"])
            snapshot = self._open()
            card_c = next(card for card in snapshot["cards"] if card["card_id"] == card_c_id)
            payload = self._commit_payload(snapshot, [self._event(snapshot, card_c)])
            first = self._commit(snapshot, payload)
            replay = self._commit(snapshot, payload)
            self.assertEqual(replay, first)
        with self.app.app_context():
            subjects = [subject_for_card(db.session, user_id=self.author_id, card_id=card_id)
                        for card_id in (self.card_a_id, self.card_b_id, card_c_id)]
            self.assertTrue(all(subject.state_payload == subjects[0].state_payload for subject in subjects))
            self.assertTrue(all(subject.semantic_state_hash == subjects[0].semantic_state_hash for subject in subjects))
            state = decode_note_state(subjects[0])
            self.assertEqual((state.type, state.reps, state.intervalDays, state.dueDay), ("review", 4, 12.5, today+13))
            self.assertTrue(all(subject.authority_revision == 1 for subject in subjects))
            events = ReviewEvent.query.all()
            self.assertEqual(len(events), 3)
            self.assertTrue(all(len(event.card_id) == 73 for event in events))
            fields = ("rating", "duration_ms", "reviewed_at", "scheduler_algorithm", "algorithm_version",
                "queue_before", "queue_after", "interval_days_before", "interval_days_after", "due_day_after")
            for field in fields:
                self.assertEqual([getattr(event, field) for event in events], [getattr(events[0], field)]*3, field)
            self.assertEqual(_review_event_provenance(), {
                ("complete", "native.rest"): 1, ("complete", "native.mcp"): 1,
                ("complete", "native.session.commit"): 1})
            assert_retired_progress_absent(self, db.session)

    def test_atomic_commit_rolls_back_every_note_and_retry_is_idempotent(self):
        snapshot = self._open()
        events = [self._event(snapshot, card, sequence) for sequence, card in enumerate(snapshot["cards"], 1)]
        payload = self._commit_payload(snapshot, events)
        corrupt = {**payload, "events": [events[0], {**events[1], "algorithm_version": "invalid"}]}
        self._commit(snapshot, corrupt, expected=422)
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.filter(StudyProgressSubject.authority_revision > 0).count(), 0)
        first = self._commit(snapshot, payload)
        second = self._commit(snapshot, payload)
        self.assertEqual({k:v for k,v in first.items() if k != "replayed"}, {k:v for k,v in second.items() if k != "replayed"})
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(StudySessionCommit.query.count(), 1)
            self.assertTrue(all(subject.authority_revision == 1 for subject in StudyProgressSubject.query.all()))
            assert_retired_progress_absent(self, db.session)

    def test_second_session_cannot_overwrite_a_changed_note(self):
        first, stale = self._open(), self._open()
        self._commit(first, self._commit_payload(first, [self._event(first, first["cards"][0])]))
        result = self._commit(stale, self._commit_payload(stale, [self._event(stale, stale["cards"][0])]), expected=409)
        self.assertIn(result["error"], {"AUTHORITY_REVISION_CONFLICT", "AUTHORITY_STATE_CONFLICT", "STALE_AUTHORITY_PIN"})
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_later_note_command_fault_rolls_back_prior_state_history_and_receipt(self):
        snapshot = self._open()
        events = [self._event(snapshot, card, sequence)
                  for sequence, card in enumerate(snapshot["cards"], 1)]
        payload = self._commit_payload(snapshot, events)
        original = study_session_service.apply_idempotent_existing_state_note_review
        calls = 0

        def fault_after_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original(*args, **kwargs)
            if calls == 2:
                raise RuntimeError("injected fault after the second NOTE command")
            return result

        with patch.object(study_session_service, "apply_idempotent_existing_state_note_review",
                          side_effect=fault_after_second):
            self._commit(snapshot, payload, expected=500)
        self.assertEqual(calls, 2)
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(StudySessionCommit.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.filter(StudyProgressSubject.authority_revision > 0).count(), 0)
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "open")
        self._commit(snapshot, payload)
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 2)

    def _connect(self, action, params):
        response = self.client.post("/v1/flama-connect", json={
            "action": action, "version": 2, "key": self.connect_token, "params": params})
        self.assertEqual(response.status_code, 200, response.get_json())
        value = response.get_json()
        self.assertFalse(isinstance(value, dict) and value.get("error"), value)
        return value

    def _sync_package(self, session_id, kind, sequence, records):
        content = ("\n".join(json.dumps(record) for record in records)+"\n").encode()
        response = self.client.put(f"/api/flashcards/import/anki/sessions/{session_id}/packages/{kind}/{sequence}",
            data=content, content_type="application/x-ndjson", headers={"X-Package-SHA256": hashlib.sha256(content).hexdigest()})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_connect_http_import_and_snapshot_persist_complete_73_character_presentation_identity(self):
        with self.app.app_context():
            self.connect_token = user_api_token_service.issue_token(user_id=self.author_id, name="qualification").plaintext
            db.session.commit()
        imported = self._connect("createImportSession", dict(source="anki", sourceKey="qualification-profile",
            sourceRootPath="Inbox", targetRootPath="Inbox", selectedDecks=["Inbox"], totalNotes=1,
            totalMedia=0, mode="strict", planHash="a"*64, noteTypes=[dict(sourceModelId="1001",
                sourceModelName="Vocabulary", targetNoteTypeId=self.note_type_id,
                fields=[dict(name="Word",fieldType="text"),dict(name="Meaning",fieldType="text")],
                fieldMapping={"Word":"Word","Meaning":"Meaning"}, templates=[dict(name="Recognition",
                    frontHtml="{{Word}}",backHtml="{{Meaning}}",sharedCss="")])]))
        session_id = imported["importSessionId"]
        cards = self._connect("importCards", dict(importSessionId=session_id, cards=[dict(ankiNoteId=88001,
            sourceModelId="1001",sourceDeckId="1",sourceDeckPath="Inbox",contentHash="1"*64,
            note=dict(deckName="Inbox",modelName=self.note_type_id, fields={"Word":"qualification","Meaning":"complete identity"},tags=[]))]))
        self.assertTrue(cards["results"][0]["imported"], cards)
        with self.app.app_context():
            from app.repositories.field_value_query_repository import note_values_search_condition
            imported_note = Note.query.filter_by(user_id=self.author_id).filter(
                note_values_search_condition(keyword_like="qualification")).one()
            wire_card_id = Card.query.filter_by(note_id=imported_note.id).one().id
            self.assertEqual(len(wire_card_id), 73)
        # Source card identities are text in Connect. Feed the full UUID pair
        # through snapshot, revlog and status parsing too; no 36/64 truncation.
        snapshot = dict(externalNoteId=88001,sourceCardId=wire_card_id,ord=0,snapshotHash="2"*64,
            type=2,queue=2,due=50003,sourceToday=50000,interval=14,factor=2500,reps=2,lapses=1,left=0,mod=1)
        progress = self._sync_package(session_id, "progress", 0, [snapshot])
        self.assertEqual(progress["results"][0]["code"], "PROGRESS_APPLIED")
        replay = self._sync_package(session_id, "progress", 0, [snapshot])
        self.assertTrue(replay["replayed"])
        review_id = int(datetime(2026,8,20,12,tzinfo=timezone.utc).timestamp()*1000)
        reviews = self._sync_package(session_id, "reviews", 1, [dict(sourceReviewId=review_id,
            sourceCardId=wire_card_id,ease=3,type=1,ivl=10,lastIvl=5,factor=2500,time=2500)])
        self.assertEqual(reviews["status"], "processed")
        status = self.client.post(f"/api/flashcards/import/anki/sessions/{session_id}/note-status", json={
            "notes": [{"ankiNoteId": 88001, "contentHash": "1"*64,
                       "cards": [{"sourceCardId": wire_card_id, "snapshotHash": "2"*64}]}]})
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertEqual(status.get_json()["notes"][0]["cards"][0]["progressState"], "unchanged")
        with self.app.app_context():
            ref = ConnectSourceCardRef.query.filter_by(user_id=self.author_id, external_card_id=wire_card_id).one()
            self.assertEqual(len(ref.card_id), 73)
            self.assertEqual(ref.card_id, wire_card_id)
            note_id, application_id = ref.card_id.split(".")
            self.assertEqual((len(note_id),len(application_id)), (36,36))
            subject = subject_for_card(db.session, user_id=self.author_id, card_id=ref.card_id)
            self.assertEqual(subject.authority_revision, 1)
            self.assertEqual(decode_note_state(subject).reps, 2)
            event_ref = ConnectReviewEventRef.query.filter_by(external_review_id=str(review_id)).one()
            event = db.session.get(ReviewEvent, event_ref.review_event_id)
            self.assertEqual(event.card_id, ref.card_id)
            self.assertEqual(_review_event_provenance(), {("complete","external.anki.revlog"):1})
            assert_retired_progress_absent(self, db.session)

    def test_due_selection_queue_ordering_and_timezone_boundary(self):
        """Due selection respects queue ordering (learning -> review -> new), excludes suspended/buried, and enforces 4 AM local boundary."""
        with self.app.app_context():
            now = datetime(2026, 8, 29, 10, 0, 0)
            today_day = _day_index(now, boundary_hour=4, timezone_name="Asia/Ho_Chi_Minh")

            # 1. Queue Ordering Invariant: Learning (priority 0) > Review (priority 1) > New (priority 2)
            # Card A: Due Review Card
            p_rev = stage_note_state(db.session,
                user_id=self.author_id,
                card_id=self.card_a_id,
                queue="review",
                due_day=today_day - 1,
                interval_days=5,
                is_suspended=False,
                is_buried=False,
            )
            # Card B: Learning Card due right now
            p_learn = stage_note_state(db.session,
                user_id=self.author_id,
                card_id=self.card_b_id,
                queue="learning",
                due_at=now - timedelta(minutes=5),
                interval_days=0,
                is_suspended=False,
                is_buried=False,
            )
            # Card C: New Card
            note_c = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_c)
            db.session.flush()
            card_c = Card.query.filter_by(note_id=note_c.id, template_id=self.template_id).one()
            db.session.add_all([p_rev, p_learn])
            db.session.commit()

            # Query queue ordering: learning card must be selected first
            next_card_id = query_next_due_card_id(
                Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id, card_c.id])),
                user_id=self.author_id,
                now=now,
                timezone_name="Asia/Ho_Chi_Minh",
            )
            self.assertEqual(next_card_id, self.card_b_id)  # Learning card first

            # 2. Suspended and Buried Exclusion Invariant
            # Card D: Suspended
            note_d = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_d)
            db.session.flush()
            card_d = Card.query.filter_by(note_id=note_d.id, template_id=self.template_id).one()
            db.session.flush()
            p_susp = stage_note_state(db.session,
                user_id=self.author_id,
                card_id=card_d.id,
                queue="review",
                due_day=today_day - 1,
                is_suspended=True,
                is_buried=False,
            )
            # Card E: Buried
            note_e = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_e)
            db.session.flush()
            card_e = Card.query.filter_by(note_id=note_e.id, template_id=self.template_id).one()
            db.session.flush()
            p_buried = stage_note_state(db.session,
                user_id=self.author_id,
                card_id=card_e.id,
                queue="review",
                due_day=today_day - 1,
                is_suspended=False,
                is_buried=True,
                buried_until_day=today_day,
            )
            db.session.add_all([p_susp, p_buried])
            db.session.commit()

            new_cnt, learn_cnt, due_cnt = query_study_queue_counts(
                Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id, card_c.id, card_d.id, card_e.id])),
                user_id=self.author_id,
                now=now,
                timezone_name="Asia/Ho_Chi_Minh",
            )
            self.assertEqual(new_cnt, 1)    # card_c
            self.assertEqual(learn_cnt, 1)  # card_b
            self.assertEqual(due_cnt, 1)    # only card_a (card_d suspended and card_e buried are excluded)

            # 3. 4 AM Day Boundary Invariant across Multiple Timezones with Independent Expected Values
            tz_test_cases = [
                # (timezone_name, utc_datetime_for_03_59_59_local, utc_datetime_for_04_00_00_local, target_date)
                (
                    "Asia/Ho_Chi_Minh",  # UTC+7
                    datetime(2026, 8, 28, 20, 59, 59),  # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 28, 21, 0, 0),    # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "Asia/Tokyo",  # UTC+9
                    datetime(2026, 8, 28, 18, 59, 59),  # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 28, 19, 0, 0),    # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "UTC-4",  # UTC-4 (Fixed offset EDT)
                    datetime(2026, 8, 29, 7, 59, 59),   # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 29, 8, 0, 0),     # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "UTC+0",  # UTC+0 (Fixed offset GMT)
                    datetime(2026, 8, 29, 3, 59, 59),   # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 29, 4, 0, 0),     # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
            ]

            for tz_name, utc_before, utc_after, target_d in tz_test_cases:
                expected_before_ordinal = (target_d - timedelta(days=1)).toordinal()
                expected_after_ordinal = target_d.toordinal()

                actual_before = _day_index(utc_before, boundary_hour=4, timezone_name=tz_name)
                actual_after = _day_index(utc_after, boundary_hour=4, timezone_name=tz_name)

                self.assertEqual(
                    actual_before,
                    expected_before_ordinal,
                    f"Timezone {tz_name} at {utc_before} UTC should resolve to yesterday's day index",
                )
                self.assertEqual(
                    actual_after,
                    expected_after_ordinal,
                    f"Timezone {tz_name} at {utc_after} UTC should resolve to today's day index",
                )

    def test_installed_browse_due_filters_use_learner_nullable_review_state(self):
        now = datetime(2026, 8, 29, 10)
        with self.app.app_context():
            initial_notes, initial_cards = Note.query.count(), Card.query.count()
            source_fields = {note.id: dict(note.field_values) for note in Note.query.all()}
            item = DeckMarketplaceItem(
                source_deck_id=self.deck_id, source_note_type_id=self.note_type_id,
                owner_user_id=self.author_id, title='Nullable review anchors',
                publish_status='published', pricing_mode='free', price_amount_minor=0,
            )
            db.session.add(item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(item)
            db.session.commit()
            installed, error, _field, status = flashcards_share_service.install_shared_deck_item(
                deck_item_id=item.id, user_id=self.learner_id, publish_statuses_visible={'published'},
            )
            self.assertEqual(status, 201, error)
            local_deck_id = installed['installed_deck_id']
            scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
                user_id=self.learner_id, local_deck_id=local_deck_id,
            )
            learner_subject = stage_note_state(db.session, user_id=self.learner_id,
                card_id=self.card_a_id, now=now, queue='review', due_day=None,
                due_at=now + timedelta(hours=1), interval_days=1)
            stage_note_state(db.session, user_id=self.author_id,
                card_id=self.card_b_id, now=now, queue='review', due_day=None,
                due_at=now - timedelta(days=1), interval_days=1)
            db.session.commit()
            self.assertIsNone(learner_subject.due_day)
            counts = query_study_queue_counts(flashcards_share_service.query_clone_scope_cards(scope),
                user_id=self.learner_id, now=now, timezone_name='Asia/Ho_Chi_Minh')
            self.assertEqual(counts, (1, 0, 1))

        self._login(self.learner_id)
        with patch.object(browse_card_service, '_utcnow', return_value=now):
            for status in ('due', 'review'):
                response = self.client.get('/api/browse/cards', query_string={
                    'deck_id': local_deck_id, 'status': status,
                })
                self.assertEqual(response.status_code, 200, response.get_json())
                page = response.get_json()
                self.assertEqual(page['total'], counts[2])
                self.assertEqual([row['card_id'] for row in page['items']], [self.card_a_id])
        with self.app.app_context():
            self.assertEqual((Note.query.count(), Card.query.count()), (initial_notes, initial_cards))
            self.assertEqual({note.id: dict(note.field_values) for note in Note.query.all()}, source_fields)
            self.assertIsNone(StudyProgressSubject.query.filter_by(
                learner_user_id=self.author_id, live_note_id=self.note_a_id).first())

    def test_shared_deck_logical_overlay_via_real_service_path(self):
        """Real install/query/review path proves zero source card duplication, zero source note mutation, real local-added content, and isolated learner progress."""
        with self.app.app_context():
            initial_notes = Note.query.count()
            initial_cards = Card.query.count()

            # 1. Author publishes marketplace deck item
            deck_item = DeckMarketplaceItem(
                source_deck_id=self.deck_id,
                source_note_type_id=self.note_type_id,
                owner_user_id=self.author_id,
                title="Published JLPT N5 Master Deck",
                publish_status="published",
                pricing_mode="free",
                price_amount_minor=0,
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

            # 2. Learner installs via real flashcards_share_service entrypoint
            install_res, err, field, status_code = flashcards_share_service.install_shared_deck_item(
                deck_item_id=deck_item_id,
                user_id=self.learner_id,
                publish_statuses_visible={"published"},
            )
            self.assertEqual(status_code, 201)
            self.assertIsNotNone(install_res)
            local_deck_id = install_res["installed_deck_id"]

            # 3. Resolve clone scope and query cards via real query path
            scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
                user_id=self.learner_id,
                local_deck_id=local_deck_id,
            )
            self.assertIsNotNone(scope)
            installed_cards = flashcards_share_service.query_clone_scope_cards(scope).all()
            self.assertEqual(len(installed_cards), 2)

            # 4. Zero Physical Duplication Invariant
            self.assertEqual(Note.query.count(), initial_notes)
            self.assertEqual(Card.query.count(), initial_cards)

            # 5. Learner reviews source card A through clone scope
            now = datetime(2026, 8, 29, 10, 0, 0)
            learner_user = db.session.get(User, self.learner_id)
            source_card_a = db.session.get(Card, self.card_a_id)

            study_service.execute_native_review_command(
                user=learner_user,
                card=source_card_a,
                action="good",
                payload={"operation_key": str(uuid4()), "duration_ms": 2000},
                clone_scope=scope,
                requested_scope_id=local_deck_id,
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )

            # Learner progress is created on source card; author has no progress
            learner_prog = decode_note_state(subject_for_card(db.session, user_id=self.learner_id, card_id=self.card_a_id))
            self.assertEqual(learner_prog.reps, 1)
            author_prog = StudyProgressSubject.query.filter_by(learner_user_id=self.author_id, live_note_id=self.note_a_id).first()
            self.assertIsNone(author_prog)

            # Source Note field values remain completely untouched (Zero Mutation)
            source_note_a = db.session.get(Note, self.note_a_id)
            self.assertEqual(source_note_a.field_values, {"Word": "猫", "Meaning": "Cat"})
            self.assertEqual(source_note_a.user_id, self.author_id)

            # 6. Learner creates a local custom note via real service entrypoint (add_note)
            installed_deck = db.session.get(Deck, local_deck_id)
            note_type = db.session.get(NoteType, self.note_type_id)
            added_note_id = add_note(
                user_id=self.learner_id,
                raw_note={
                    "deckName": installed_deck.name,
                    "modelName": note_type.name,
                    "fields": {"Word": "鳥", "Meaning": "Bird"},
                },
            )
            self.assertIsNotNone(added_note_id)

            ref = db.session.get(ConnectNoteRef, added_note_id)
            self.assertIsNotNone(ref)
            actual_note_id = ref.note_id

            # Service entrypoint automatically created the DeckCloneAddedNote association
            added_record = DeckCloneAddedNote.query.filter_by(
                deck_install_id=scope.install.id,
                note_id=actual_note_id,
            ).first()
            self.assertIsNotNone(added_record)

            # Scope query now includes source cards + learner's added card (3 cards)
            all_scope_cards = flashcards_share_service.query_clone_scope_cards(scope).all()
            self.assertEqual(len(all_scope_cards), 3)

            # Composition discovery and session opening use this exact real
            # overlay query. Source and learner-local cards must remain
            # distinguishable without materializing a physical clone.
            effective_query = flashcards_share_service.query_clone_scope_cards(scope)
            compositions = study_composition_service.list_available_compositions_for_query(
                effective_query,
                clone_scope=scope,
            )
            self.assertEqual(
                {item.context_kind for item in compositions},
                {"installed_source", "installed_local"},
            )
            self.assertTrue(
                all(item.composition_id.startswith(f"comp:install:{scope.install.id}:") for item in compositions)
            )

            for composition in compositions:
                selection = study_composition_service.resolve_composition_selection(
                    effective_query,
                    clone_scope=scope,
                    requested_composition_id=composition.composition_id,
                    request_source="acceptance-real-overlay",
                )
                composition_snapshot = study_session_service.open_study_session(
                    user=learner_user,
                    query=effective_query,
                    clone_scope=scope,
                    scope_type="deck",
                    scope_id=str(local_deck_id),
                    timezone_name="Asia/Ho_Chi_Minh",
                    composition_selection=selection,
                    wire_schema_version="study-session.v4",
                    now=now,
                )
                self.assertEqual(
                    composition_snapshot["selected_composition_id"],
                    composition.composition_id,
                )
                self.assertTrue(composition_snapshot["cards"])
                self.assertEqual(
                    {card["composition_id"] for card in composition_snapshot["cards"]},
                    {composition.composition_id},
                )

            self.assertEqual(Note.query.count(), initial_notes + 1)
            self.assertEqual(Card.query.count(), initial_cards + 1)

            # 7. Learner reviews local-added card through clone scope
            custom_card = Card.query.filter_by(note_id=actual_note_id).first()
            self.assertIsNotNone(custom_card)

            study_service.execute_native_review_command(
                user=learner_user,
                card=custom_card,
                action="good",
                payload={"operation_key": str(uuid4()), "duration_ms": 1800},
                clone_scope=scope,
                requested_scope_id=local_deck_id,
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )

            # Progress created for learner on local added card
            custom_prog = decode_note_state(subject_for_card(db.session, user_id=self.learner_id, card_id=custom_card.id))
            self.assertEqual(custom_prog.reps, 1)

            # Author's notes query still only contains original author notes (2 notes)
            author_notes = Note.query.filter_by(deck_id=self.deck_id, user_id=self.author_id).all()
            self.assertEqual(len(author_notes), 2)

    def test_study_action_runtime_validates_and_rejects_unauthorized_actions(self):
        """Study action runtime validates semantic review actions and rejects unauthorized/forged actions without progress side effects."""
        with self.app.app_context():
            # Initial progress
            initial_progress = stage_note_state(db.session,
                user_id=self.author_id,
                card_id=self.card_a_id,
                queue="review",
                interval_days=1,
                reps=1,
            )
            db.session.add(initial_progress)
            db.session.commit()

            from app.services.study_action_runtime import (
                resolve_review_action,
                StudyActionValidationError,
            )

            # 1. Valid actions resolve to deterministic action & trigger keys
            for valid_rating in ["again", "hard", "good", "easy"]:
                action_contract = resolve_review_action(valid_rating)
                self.assertEqual(action_contract.rating, valid_rating)
                self.assertEqual(action_contract.action_key, f"review.{valid_rating}")
                self.assertEqual(action_contract.trigger_key, f"scheduler.review.{valid_rating}")

            # 2. Forged or arbitrary actions fail closed
            for invalid_action in ["untrusted_script_eval", "rate_10", "grant_admin", "", None]:
                with self.assertRaises(StudyActionValidationError):
                    resolve_review_action(invalid_action)  # type: ignore[arg-type]

            # 3. Ensure progress was NOT modified
            p = decode_note_state(subject_for_card(db.session, user_id=self.author_id, card_id=self.card_a_id))
            self.assertEqual(p.reps, 1)
            self.assertEqual(p.intervalDays, 1)


if __name__ == "__main__":
    unittest.main()
