from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import text

from app import create_app
from app.services import anki_sync_service, study_artifact_service
from app.services.mcp import study_tools as mcp_study_tools
from app.services.study_architecture_audit_service import (
    MAX_SAMPLE_IDS,
    build_study_architecture_audit,
)
from app.services.study_phase4_preflight_service import (
    _actionable_indexes,
    _database_table_contract,
    _model_table_contract,
    _normalized_type,
    analyze_mysql_grants,
    collect_connection_safety,
)
from app.services.study_service import execute_native_review_command
from app.services.study_session_service import commit_study_session, open_study_session
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.template import Template
from models.user import User


class StudyArchitectureAuditServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            db.create_all()
            user = User(username="audit-user", email="audit@example.com")
            user.password_hash = "mock_hash"
            db.session.add(user)
            db.session.flush()

            note_type_a = NoteType(user_id=user.id, name="A")
            note_type_b = NoteType(user_id=user.id, name="B")
            db.session.add_all([note_type_a, note_type_b])
            db.session.flush()

            template_a1 = Template(
                note_type_id=note_type_a.id,
                name="Basic",
                position=0,
                is_default=False,
            )
            template_a2 = Template(
                note_type_id=note_type_a.id,
                name="basic",
                position=0,
                is_default=False,
            )
            template_b = Template(
                note_type_id=note_type_b.id,
                name="Basic",
                position=0,
                is_default=True,
            )
            db.session.add_all([template_a1, template_a2, template_b])
            db.session.flush()

            note = Note(user_id=user.id, note_type_id=note_type_a.id, field_values={})
            db.session.add(note)
            db.session.flush()
            matching_card = Card(note_id=note.id, template_id=template_a1.id)
            mismatched_card = Card(note_id=note.id, template_id=template_b.id)
            db.session.add_all([matching_card, mismatched_card])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(user_id=user.id, card_id=matching_card.id),
                    CardProgress(user_id=user.id, card_id=mismatched_card.id),
                ]
            )
            now = datetime(2026, 8, 27, 12, 0, 0)
            db.session.add(
                StudySession(
                    user_id=user.id,
                    scope_type="deck",
                    scope_id="1",
                    status="open",
                    scheduler_algorithm="legacy-anki",
                    algorithm_version="1.0.0",
                    snapshot_hash="snapshot",
                    token_hash="token",
                    config_snapshot_json="{}",
                    opened_at=now - timedelta(days=2),
                    expires_at=now - timedelta(days=1),
                )
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_report_exposes_read_only_migration_gates_v4(self):
        with self.app.app_context():
            report = build_study_architecture_audit(
                now=datetime(2026, 8, 27, 12, 0, 0)
            )

        self.assertEqual(report["schema_version"], "study-architecture-audit.v4")
        self.assertEqual(report["template_gates"]["note_types_with_multiple_templates"], 1)
        self.assertIsInstance(report["template_gates"]["note_types_with_multiple_templates_samples"], list)
        self.assertEqual(report["template_gates"]["default_count_anomalies"], 1)
        self.assertEqual(report["template_gates"]["duplicate_name_groups"], 1)
        self.assertEqual(report["template_gates"]["duplicate_position_groups"], 1)
        self.assertEqual(report["template_gates"]["cross_note_type_cards"], 1)
        self.assertGreater(len(report["template_gates"]["cross_note_type_cards_samples"]), 0)
        self.assertEqual(report["card_gates"]["notes_with_multiple_cards"], 1)
        self.assertEqual(report["progress_gates"]["learner_note_fan_in_groups"], 1)
        self.assertEqual(
            report["algorithm_gates"]["algorithm_support"][0]["lifecycle_state"],
            "active",
        )
        self.assertTrue(
            report["algorithm_gates"]["algorithm_support"][0][
                "existing_lease_allowed"
            ]
        )
        self.assertEqual(report["progress_gates"]["equivalent_fan_in_groups"], 1)
        self.assertEqual(report["session_gates"]["expired_open_sessions"], 1)
        self.assertEqual(
            report["session_gates"]["wire_version_session_inventory"],
            [
                {
                    "wire_schema_version": "study-session.v2",
                    "status": "open",
                    "algorithm_key": "legacy-anki",
                    "algorithm_version": "1.0.0",
                    "count": 1,
                }
            ],
        )
        self.assertEqual(
            report["session_gates"]["active_wire_version_counts"],
            {},
        )

        preflight = report["phase4_preflight"]
        self.assertEqual(preflight["schema_version"], "study-phase4-preflight.v1")
        self.assertEqual(preflight["evidence_class"], "repository-and-fixture-only")
        self.assertEqual(preflight["schema"]["drift_count"], 0)
        self.assertTrue(
            preflight["repository"]["study_session_batches_migration_declared"]
        )
        self.assertIn(
            "current_mysql_select_only_evidence_missing",
            preflight["gate"]["blockers"],
        )
        self.assertNotIn(
            "study_session_batches_missing_repository_migration",
            preflight["gate"]["blockers"],
        )
        self.assertEqual(preflight["progress"]["total_card_progress_rows"], 2)
        self.assertEqual(preflight["progress"]["context_rows"]["owned"], 2)
        self.assertEqual(
            preflight["progress"]["context_membership_rows"],
            {
                "owned": 2,
                "installed_source": 0,
                "installed_local": 0,
                "with_any": 2,
                "single": 2,
                "multiple": 0,
                "none": 0,
            },
        )
        self.assertEqual(
            preflight["progress"]["subject_groups"],
            {"total": 1, "single": 0, "fan_in": 1},
        )
        self.assertEqual(
            preflight["progress"]["migration_disposition_rows"][
                "mirror_candidate"
            ],
            0,
        )
        self.assertEqual(
            preflight["progress"]["migration_disposition_rows"][
                "quarantine_candidate"
            ],
            2,
        )
        self.assertEqual(
            preflight["progress"]["unresolvable_subject_reasons"],
            {
                "null_learner_user_id": 0,
                "missing_learner_user": 0,
                "null_card_id": 0,
                "missing_card": 0,
                "null_note_id": 0,
                "missing_note": 0,
            },
        )
        self.assertTrue(all(preflight["progress"]["accounting"].values()))

        # v4 retains the established audit gates and adds Phase 4 preflight.
        self.assertIn("revision_gates", report)
        self.assertEqual(report["revision_gates"]["zero_revision_rows"], 2)
        self.assertEqual(report["revision_gates"]["active_revision_rows"], 0)
        self.assertEqual(report["revision_gates"]["invalid_revision_rows"], 0)

        # Established algorithm gates remain available.
        self.assertIn("algorithm_gates", report)
        self.assertIn("unregistered_algorithm_events", report["algorithm_gates"])
        self.assertIn("active_registry_executables", report["algorithm_gates"])
        self.assertIn("registered_algorithm_events", report["algorithm_gates"])
        self.assertIn("historical_imported_algorithm_events", report["algorithm_gates"])

        # Established review-event gates remain available.
        self.assertIn("review_event_gates", report)
        self.assertIn("orphan_card_id_events", report["review_event_gates"])
        self.assertIn("null_session_id_events", report["review_event_gates"])
        self.assertIn("null_algorithm_events", report["review_event_gates"])
        self.assertIn("duplicate_client_event_id_groups", report["review_event_gates"])

        # Established clone-overlay gates remain available.
        self.assertIn("clone_overlay_gates", report)
        self.assertIn("deck_installs_count", report["clone_overlay_gates"])
        self.assertIn("installed_deck_cards", report["clone_overlay_gates"])
        self.assertIn("local_authored_cards", report["clone_overlay_gates"])
        self.assertIn("local_clone_added_cards", report["clone_overlay_gates"])

        # Established inventory remains the operational audit verdict source.
        self.assertIn("inventory", report)
        self.assertIsInstance(report["inventory"], list)
        for item in report["inventory"]:
            self.assertIn("category", item)
            self.assertIn("gate_group", item)
            self.assertIn("count", item)
            self.assertIn("sample_ids", item)
            self.assertIn("severity", item)
            self.assertIn("disposition", item)
            self.assertIn("description", item)
            self.assertLessEqual(len(item["sample_ids"]), 10)

        # Established verdict categorization remains stable.
        self.assertIn("verdicts", report)
        verdicts = report["verdicts"]
        self.assertIsInstance(verdicts["pass"], list)
        self.assertIsInstance(verdicts["warn"], list)
        self.assertIsInstance(verdicts["block"], list)
        self.assertEqual(verdicts["overall_status"], "BLOCK")
        self.assertEqual(verdicts["exit_code"], 2)

        # Exact 1-to-1 consistency between inventory non-pass items and verdict warnings + blocks
        non_pass_inventory = [item for item in report["inventory"] if item["severity"] != "pass"]
        block_inventory = [item for item in report["inventory"] if item["severity"] == "block"]
        warn_inventory = [item for item in report["inventory"] if item["severity"] == "warn"]
        self.assertEqual(len(verdicts["block"]), len(block_inventory))
        self.assertEqual(len(verdicts["warn"]), len(warn_inventory))
        self.assertEqual(len(non_pass_inventory), len(verdicts["warn"]) + len(verdicts["block"]))

        # cross_note_type_cards > 0 should be a block
        block_texts = " ".join(verdicts["block"])
        self.assertIn("cross_note_type_cards", block_texts)

        # expired_open_sessions > 0 should be a warn
        warn_texts = " ".join(verdicts["warn"])
        self.assertIn("expired_open_sessions", warn_texts)

        # Reconciliation now includes the Phase 4 partitions.
        self.assertIn("reconciliation", report)
        self.assertEqual(report["reconciliation"]["status"], "VALID")
        checks = report["reconciliation"]["formula_checks"]
        self.assertTrue(checks["card_progress_accounting"])
        self.assertTrue(checks["card_progress_fan_in_consistency"])
        self.assertTrue(checks["card_progress_revision_accounting"])
        self.assertTrue(checks["review_events_attached_accounting"])
        self.assertTrue(checks["review_events_provenance_accounting"])
        self.assertTrue(checks["review_events_algorithm_accounting"])
        self.assertTrue(checks["study_sessions_status_accounting"])
        self.assertTrue(checks["study_sessions_open_accounting"])
        self.assertTrue(checks["note_types_template_accounting"])
        self.assertTrue(checks["cards_clone_overlay_accounting"])
        self.assertTrue(checks["inventory_verdict_accounting"])
        self.assertTrue(checks["phase4_source_partition"])
        self.assertTrue(checks["phase4_unresolvable_reason_partition"])
        self.assertTrue(checks["phase4_migration_disposition_partition"])
        self.assertTrue(checks["phase4_subject_group_partition"])
        self.assertTrue(checks["phase4_subject_group_row_partition"])
        self.assertTrue(checks["phase4_context_partition"])
        self.assertTrue(checks["phase4_context_membership_presence_partition"])
        self.assertTrue(checks["phase4_context_membership_cardinality_partition"])
        self.assertTrue(checks["phase4_fan_in_state_partition"])
        self.assertTrue(checks["phase4_fan_in_lineage_partition"])
        self.assertTrue(checks["phase4_last_review_pointer_partition"])
        self.assertTrue(checks["phase4_due_shape_partition"])
        self.assertTrue(checks["phase4_queue_partition"])
        self.assertTrue(checks["phase4_memory_state_partition"])
        self.assertTrue(checks["phase4_source_card_ref_partition"])
        self.assertTrue(checks["phase4_source_note_ref_partition"])
        self.assertTrue(checks["phase4_review_event_ref_partition"])
        self.assertTrue(checks["phase4_valid_pointer_connect_ref_partition"])

    def test_phase4_context_memberships_preserve_owned_installed_overlap(self):
        with self.app.app_context():
            user = User.query.first()
            note = Note.query.first()
            note_type = NoteType.query.filter_by(id=note.note_type_id).one()
            source_deck = Deck(
                owner_user_id=user.id,
                note_type_id=note_type.id,
                name="Owned source",
            )
            db.session.add(source_deck)
            db.session.flush()
            note.deck_id = source_deck.id
            item = DeckMarketplaceItem(
                owner_user_id=user.id,
                source_deck_id=source_deck.id,
                source_note_type_id=note_type.id,
                title="Owned listing",
            )
            db.session.add(item)
            db.session.flush()
            db.session.add(
                DeckInstall(
                    deck_item_id=item.id,
                    user_id=user.id,
                    source_deck_id=source_deck.id,
                    source_note_type_id=note_type.id,
                    source_owner_user_id=user.id,
                    clone_mode="logical_overlay",
                )
            )
            db.session.commit()

            report = build_study_architecture_audit(
                now=datetime(2026, 9, 10, 3, 4, 5)
            )

        progress = report["phase4_preflight"]["progress"]
        self.assertEqual(progress["context_rows"]["installed_source"], 2)
        self.assertEqual(progress["context_rows"]["owned"], 0)
        self.assertEqual(progress["context_membership_rows"]["owned"], 2)
        self.assertEqual(
            progress["context_membership_rows"]["installed_source"],
            2,
        )
        self.assertEqual(progress["context_membership_rows"]["with_any"], 2)
        self.assertEqual(progress["context_membership_rows"]["single"], 0)
        self.assertEqual(progress["context_membership_rows"]["multiple"], 2)
        self.assertEqual(progress["context_membership_rows"]["none"], 0)
        self.assertIn(
            "multi_context_progress_requires_p4_02_review",
            report["phase4_preflight"]["gate"]["warnings"],
        )
        self.assertTrue(all(progress["accounting"].values()))

    def test_phase4_missing_learner_is_an_unresolvable_subject_reason(self):
        with self.app.app_context():
            card = Card.query.first()
            db.session.commit()
            db.session.execute(text("PRAGMA foreign_keys = OFF"))
            db.session.commit()
            db.session.add(CardProgress(user_id=999_999, card_id=card.id))
            db.session.commit()

            report = build_study_architecture_audit(
                now=datetime(2026, 9, 10, 3, 4, 5)
            )

        progress = report["phase4_preflight"]["progress"]
        self.assertEqual(progress["total_card_progress_rows"], 3)
        self.assertEqual(progress["valid_note_subject_rows"], 2)
        self.assertEqual(progress["unresolvable_subject_rows"], 1)
        self.assertEqual(
            progress["unresolvable_subject_reasons"]["missing_learner_user"],
            1,
        )
        self.assertEqual(
            progress["migration_disposition_rows"]["unresolvable"],
            1,
        )
        self.assertTrue(all(progress["accounting"].values()))

    def test_mysql_grant_analysis_requires_select_without_write_or_admin_rights(self):
        safe = analyze_mysql_grants(
            [
                "GRANT USAGE ON *.* TO `audit`@`%`",
                "GRANT SELECT, SHOW VIEW ON `flama`.* TO `audit`@`%`",
            ]
        )
        self.assertTrue(safe["select_only_verified"])
        self.assertEqual(safe["disallowed_privileges"], [])

        unsafe = analyze_mysql_grants(
            ["GRANT SELECT, INSERT, UPDATE ON `flama`.* TO `app`@`%` WITH GRANT OPTION"]
        )
        self.assertFalse(unsafe["select_only_verified"])
        self.assertEqual(
            unsafe["disallowed_privileges"],
            ["GRANT OPTION", "INSERT", "UPDATE"],
        )

        role_grant = analyze_mysql_grants(
            [
                "GRANT SELECT ON `flama`.* TO `audit`@`%`",
                "GRANT `application_writer`@`%` TO `audit`@`%`",
            ]
        )
        self.assertFalse(role_grant["select_only_verified"])
        self.assertEqual(role_grant["unparsed_grant_row_count"], 1)
        self.assertEqual(
            role_grant["disallowed_privileges"],
            ["UNPARSED OR ROLE GRANT"],
        )

    def test_mysql_connection_safety_uses_non_reserved_principal_alias(self):
        fake_db = Mock()
        fake_db.engine.dialect.name = "mysql"

        identity_result = Mock()
        identity_result.mappings.return_value.one.return_value = {
            "connected_principal": "audit@127.0.0.1",
            "database_name": "flama",
            "server_version": "8.0",
            "sql_mode": "STRICT_TRANS_TABLES",
            "database_charset": "utf8mb4",
            "database_collation": "utf8mb4_unicode_ci",
            "time_zone": "+00:00",
        }
        grants_result = Mock()
        grants_result.all.return_value = [
            ("GRANT SELECT, SHOW VIEW ON `flama`.* TO `audit`@`127.0.0.1`",)
        ]
        fake_db.session.execute.side_effect = [identity_result, grants_result]

        with patch(
            "app.services.study_phase4_preflight_service.db",
            fake_db,
        ):
            result = collect_connection_safety()

        identity_sql = str(fake_db.session.execute.call_args_list[0].args[0])
        self.assertIn("AS connected_principal", identity_sql)
        self.assertNotIn("AS current_user", identity_sql)
        self.assertTrue(result["current_mysql_evidence"])
        self.assertTrue(result["select_only_verified"])

    def test_mysql_schema_comparison_normalizes_reflection_only_type_details(self):
        self.assertEqual(
            _normalized_type('VARCHAR(36) COLLATE "utf8mb4_unicode_ci"'),
            "VARCHAR(36)",
        )
        self.assertEqual(_normalized_type("BOOL"), _normalized_type("TINYINT"))
        self.assertNotEqual(
            _normalized_type("VARCHAR(16)"),
            _normalized_type('VARCHAR(32) COLLATE "utf8mb4_unicode_ci"'),
        )

    def test_schema_contract_compares_unique_sets_separately_from_indexes(self):
        metadata = sa.MetaData()
        table = sa.Table(
            "example",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("lookup", sa.String(36), nullable=False),
            sa.Column("scope", sa.String(36), nullable=False),
        )
        sa.Index("ix_example_lookup", table.c.lookup)
        sa.Index("uq_example_lookup_scope", table.c.lookup, table.c.scope, unique=True)

        model_contract = _model_table_contract(
            table,
            dialect=sa.engine.default.DefaultDialect(),
        )
        self.assertEqual(model_contract["indexes"], [[["lookup"], False]])
        self.assertEqual(
            model_contract["unique_column_sets"],
            [["lookup", "scope"]],
        )

        inspector = Mock()
        inspector.get_columns.return_value = [
            {
                "name": "id",
                "type": sa.Integer(),
                "nullable": False,
                "default": None,
            },
            {
                "name": "lookup",
                "type": sa.String(36),
                "nullable": False,
                "default": None,
            },
            {
                "name": "scope",
                "type": sa.String(36),
                "nullable": False,
                "default": None,
            },
        ]
        inspector.get_foreign_keys.return_value = []
        inspector.get_indexes.return_value = [
            {"column_names": ["lookup"], "unique": False},
            {"column_names": ["lookup", "scope"], "unique": True},
        ]
        inspector.get_unique_constraints.return_value = []
        inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
        inspector.get_table_options.return_value = {}

        database_contract = _database_table_contract(inspector, "example")
        self.assertEqual(database_contract["indexes"], [[["lookup"], False]])
        self.assertEqual(
            database_contract["unique_column_sets"],
            [["lookup", "scope"]],
        )

    def test_schema_comparison_excludes_mysql_foreign_key_support_indexes(self):
        contract = {
            "foreign_keys": [
                [["scheduler_preset_id"], "scheduler_presets", ["id"], "SET NULL"]
            ],
            "indexes": [
                [["scheduler_preset_id"], False],
                [["session_id", "ordinal"], False],
            ],
        }

        self.assertEqual(
            _actionable_indexes(contract),
            [[["session_id", "ordinal"], False]],
        )

    def test_current_mysql_phase4_blockers_flow_to_top_level_exit_code(self):
        verified_connection = {
            "dialect": "mysql",
            "evidence_scope": "current-mysql-select-only",
            "select_only_verified": True,
            "current_mysql_evidence": True,
        }
        with self.app.app_context(), patch(
            "app.services.study_architecture_audit_service.collect_connection_safety",
            return_value=verified_connection,
        ):
            report = build_study_architecture_audit(
                now=datetime(2026, 9, 10, 3, 4, 5)
            )

        self.assertEqual(report["verdicts"]["exit_code"], 2)
        self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
        self.assertNotIn(
            "study_session_batches_missing_repository_migration",
            report["phase4_preflight"]["gate"]["blockers"],
        )
        self.assertFalse(
            any(
                item["category"]
                == "phase4_study_session_batches_missing_repository_migration"
                for item in report["inventory"]
            )
        )

    def test_progress_fan_in_classification_equivalent_vs_divergent(self):
        """Test distinction between single-card progress, equivalent fan-in, and divergent fan-in across all 21 authoritative scheduling fields."""
        with self.app.app_context():
            user = User.query.first()
            nt = NoteType.query.first()
            tmpl1 = Template.query.filter_by(note_type_id=nt.id).first()
            tmpl2 = Template(note_type_id=nt.id, name="Back", position=1, is_default=False)
            db.session.add(tmpl2)
            db.session.flush()

            now = datetime(2026, 8, 29, 12, 0, 0)

            # Note 1: Single card progress
            note_single = Note(user_id=user.id, note_type_id=nt.id, field_values={})
            db.session.add(note_single)
            db.session.flush()
            card_single = Card(note_id=note_single.id, template_id=tmpl1.id)
            db.session.add(card_single)
            db.session.flush()
            db.session.add(
                CardProgress(
                    user_id=user.id,
                    card_id=card_single.id,
                    queue="review",
                    step_index=0,
                    due_at=now,
                    due_day=10,
                    interval_days=5,
                    interval_days_raw=5.2,
                    is_suspended=False,
                    is_buried=False,
                    buried_until_day=None,
                    suspension_reason=None,
                    review_kind="review",
                    scheduler_mode="legacy",
                    ease_factor=2.5,
                    memory_stability=None,
                    memory_difficulty=None,
                    last_leech_lapses=0,
                    last_leech_at=None,
                    reps=3,
                    lapses=0,
                    last_reviewed_at=now,
                    revision=1,
                )
            )

            # Note 2: Equivalent fan-in on 2 cards across all 21 fields
            note_equiv = Note(user_id=user.id, note_type_id=nt.id, field_values={})
            db.session.add(note_equiv)
            db.session.flush()
            c_eq1 = Card(note_id=note_equiv.id, template_id=tmpl1.id)
            c_eq2 = Card(note_id=note_equiv.id, template_id=tmpl2.id)
            db.session.add_all([c_eq1, c_eq2])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(
                        user_id=user.id,
                        card_id=c_eq1.id,
                        queue="review",
                        step_index=0,
                        due_at=now,
                        due_day=10,
                        interval_days=5,
                        interval_days_raw=5.0,
                        is_suspended=False,
                        is_buried=False,
                        buried_until_day=None,
                        suspension_reason=None,
                        review_kind="review",
                        scheduler_mode="legacy",
                        ease_factor=2.5,
                        memory_stability=None,
                        memory_difficulty=None,
                        last_leech_lapses=0,
                        last_leech_at=None,
                        reps=3,
                        lapses=0,
                        last_reviewed_at=now,
                        revision=1,
                    ),
                    CardProgress(
                        user_id=user.id,
                        card_id=c_eq2.id,
                        queue="review",
                        step_index=0,
                        due_at=now,
                        due_day=10,
                        interval_days=5,
                        interval_days_raw=5.0,
                        is_suspended=False,
                        is_buried=False,
                        buried_until_day=None,
                        suspension_reason=None,
                        review_kind="review",
                        scheduler_mode="legacy",
                        ease_factor=2.5,
                        memory_stability=None,
                        memory_difficulty=None,
                        last_leech_lapses=0,
                        last_leech_at=None,
                        reps=3,
                        lapses=0,
                        last_reviewed_at=now,
                        revision=1,
                    ),
                ]
            )

            # Note 3: Divergent fan-in on interval and queue
            note_div = Note(user_id=user.id, note_type_id=nt.id, field_values={})
            db.session.add(note_div)
            db.session.flush()
            card_div1 = Card(note_id=note_div.id, template_id=tmpl1.id)
            card_div2 = Card(note_id=note_div.id, template_id=tmpl2.id)
            db.session.add_all([card_div1, card_div2])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(user_id=user.id, card_id=card_div1.id, queue="learn", interval_days=1, ease_factor=2.5),
                    CardProgress(user_id=user.id, card_id=card_div2.id, queue="review", interval_days=10, ease_factor=2.1),
                ]
            )

            # Note 4: Divergent fan-in on subtle field due_at
            note_div_due = Note(user_id=user.id, note_type_id=nt.id, field_values={})
            db.session.add(note_div_due)
            db.session.flush()
            c_due1 = Card(note_id=note_div_due.id, template_id=tmpl1.id)
            c_due2 = Card(note_id=note_div_due.id, template_id=tmpl2.id)
            db.session.add_all([c_due1, c_due2])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(user_id=user.id, card_id=c_due1.id, queue="learn", due_at=now, interval_days=1, ease_factor=2.5),
                    CardProgress(user_id=user.id, card_id=c_due2.id, queue="learn", due_at=now + timedelta(minutes=10), interval_days=1, ease_factor=2.5),
                ]
            )

            # Note 5: Divergent fan-in on suspension / burial / leech
            note_div_susp = Note(user_id=user.id, note_type_id=nt.id, field_values={})
            db.session.add(note_div_susp)
            db.session.flush()
            c_susp1 = Card(note_id=note_div_susp.id, template_id=tmpl1.id)
            c_susp2 = Card(note_id=note_div_susp.id, template_id=tmpl2.id)
            db.session.add_all([c_susp1, c_susp2])
            db.session.flush()
            db.session.add_all(
                [
                    CardProgress(user_id=user.id, card_id=c_susp1.id, queue="review", interval_days=5, ease_factor=2.5, is_suspended=True, suspension_reason="manual"),
                    CardProgress(user_id=user.id, card_id=c_susp2.id, queue="review", interval_days=5, ease_factor=2.5, is_suspended=False, suspension_reason=None),
                ]
            )
            db.session.flush()

            # Keep raw state equal while giving the two contributors distinct,
            # valid event lineage. Phase 4 must report these dimensions
            # independently instead of silently choosing a winner.
            eq_event_1 = ReviewEvent(
                user_id=user.id,
                card_id=c_eq1.id,
                rating="good",
                mode="review",
                scheduler_mode="legacy",
                scheduler_algorithm="legacy-anki",
                algorithm_version="1.0.0",
                reviewed_at=now,
            )
            eq_event_2 = ReviewEvent(
                user_id=user.id,
                card_id=c_eq2.id,
                rating="good",
                mode="review",
                scheduler_mode="legacy",
                scheduler_algorithm="legacy-anki",
                algorithm_version="1.0.0",
                reviewed_at=now,
            )
            db.session.add_all([eq_event_1, eq_event_2])
            db.session.flush()
            CardProgress.query.filter_by(user_id=user.id, card_id=c_eq1.id).one().last_review_event_id = eq_event_1.id
            CardProgress.query.filter_by(user_id=user.id, card_id=c_eq2.id).one().last_review_event_id = eq_event_2.id
            db.session.commit()

            report = build_study_architecture_audit()
            pg = report["progress_gates"]
            self.assertEqual(pg["single_card_progress_groups"], 1)
            self.assertEqual(pg["equivalent_fan_in_groups"], 2)  # matching/mismatched from setUp + note_equiv
            self.assertGreaterEqual(pg["divergent_fan_in_groups"], 3)
            self.assertTrue(report["reconciliation"]["formula_checks"]["card_progress_fan_in_consistency"])
            phase4_fan_in = report["phase4_preflight"]["progress"]["fan_in"]
            self.assertGreaterEqual(phase4_fan_in["state_equivalent_groups"], 2)
            self.assertGreaterEqual(phase4_fan_in["lineage_divergent_groups"], 1)
            self.assertGreaterEqual(
                phase4_fan_in["state_equivalent_lineage_divergent_groups"],
                1,
            )

    def test_algorithm_gates_historical_import_vs_unregistered_native(self):
        """Test that historical Anki import algorithm events pass cleanly without false warnings, while unregistered native events warn."""
        with self.app.app_context():
            user = User.query.first()
            card = Card.query.first()

            # 1. Historical Anki import ReviewEvent (like production 61,645 rows)
            rev_anki = ReviewEvent(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                mode="import",
                scheduler_mode="anki",
                scheduler_algorithm="anki",
                algorithm_version=None,
                reviewed_at=datetime.utcnow(),
            )
            # 2. Registered active ReviewEvent
            rev_reg = ReviewEvent(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                mode="review",
                scheduler_mode="legacy",
                scheduler_algorithm="legacy-anki",
                algorithm_version="1.0.0",
                reviewed_at=datetime.utcnow(),
            )
            # 3. Native unregistered algorithm ReviewEvent
            rev_unreg = ReviewEvent(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                mode="review",
                scheduler_mode="custom",
                scheduler_algorithm="custom-experimental-model",
                algorithm_version="2.0.0",
                reviewed_at=datetime.utcnow(),
            )
            # 4. Native ReviewEvent with missing algorithm version
            rev_no_ver = ReviewEvent(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                mode="review",
                scheduler_mode="legacy",
                scheduler_algorithm="legacy-anki",
                algorithm_version=None,
                reviewed_at=datetime.utcnow(),
            )
            db.session.add_all([rev_anki, rev_reg, rev_unreg, rev_no_ver])
            db.session.commit()

            report = build_study_architecture_audit()
            ag = report["algorithm_gates"]
            self.assertEqual(ag["historical_imported_algorithm_events"], 1)
            self.assertEqual(ag["registered_algorithm_events"], 1)
            self.assertEqual(ag["unregistered_native_algorithm_events"], 1)
            self.assertEqual(ag["missing_algorithm_version_events"], 1)

            # Check inventory severity
            inventory_by_cat = {item["category"]: item for item in report["inventory"]}
            self.assertEqual(inventory_by_cat["historical_imported_algorithm_events"]["severity"], "pass")
            self.assertEqual(inventory_by_cat["registered_algorithm_events"]["severity"], "pass")
            self.assertEqual(inventory_by_cat["unregistered_native_algorithm_events"]["severity"], "warn")
            self.assertEqual(inventory_by_cat["missing_algorithm_version_events"]["severity"], "warn")

            # Algorithm reconciliation must be exactly valid
            self.assertTrue(report["reconciliation"]["formula_checks"]["review_events_algorithm_accounting"])

    def test_session_active_unavailable_vs_historical_retired_algorithm(self):
        """Test that active open leases with unavailable algorithms BLOCK, while historical retired sessions PASS."""
        with self.app.app_context():
            user = User.query.first()
            now = datetime(2026, 8, 29, 12, 0, 0)

            # 1. Historical committed session with retired algorithm -> PASS
            s_historical = StudySession(
                user_id=user.id,
                scope_type="deck",
                scope_id="1",
                status="committed",
                scheduler_algorithm="retired-v0-algo",
                algorithm_version="0.5.0",
                snapshot_hash="hash_ret",
                token_hash="tok_ret",
                config_snapshot_json='{"steps": [1]}',
                opened_at=now - timedelta(days=10),
                expires_at=now - timedelta(days=9),
                committed_at=now - timedelta(days=9),
            )
            # 2. Active open session with unavailable algorithm -> BLOCK
            s_active_bad = StudySession(
                user_id=user.id,
                scope_type="deck",
                scope_id="1",
                status="open",
                scheduler_algorithm="unregistered-live-algo",
                algorithm_version="3.0.0",
                snapshot_hash="hash_live_bad",
                token_hash="tok_live_bad",
                config_snapshot_json='{"steps": [1, 10]}',
                opened_at=now,
                expires_at=now + timedelta(hours=1),
            )
            db.session.add_all([s_historical, s_active_bad])
            db.session.commit()

            report = build_study_architecture_audit(now=now)
            sg = report["session_gates"]
            self.assertGreaterEqual(sg["active_session_unavailable_algorithm_sessions"], 1)
            self.assertGreaterEqual(sg["historical_session_retired_algorithm_sessions"], 1)

            # Active unavailable algorithm must be in verdicts["block"]
            block_texts = " ".join(report["verdicts"]["block"])
            self.assertIn("active_session_unavailable_algorithm_sessions", block_texts)
            self.assertEqual(report["verdicts"]["overall_status"], "BLOCK")
            self.assertEqual(report["verdicts"]["exit_code"], 2)

    def test_audit_uses_lifecycle_capability_for_active_lease(self):
        with self.app.app_context():
            user = User.query.first()
            now = datetime(2026, 8, 29, 12, 0, 0)
            lease_only = StudySession(
                user_id=user.id,
                scope_type="deck",
                scope_id="1",
                status="open",
                scheduler_algorithm="draining-algorithm",
                algorithm_version="1.0.0",
                snapshot_hash="lease-only",
                token_hash="lease-only",
                config_snapshot_json="{}",
                opened_at=now,
                expires_at=now + timedelta(hours=1),
            )
            retired = StudySession(
                user_id=user.id,
                scope_type="deck",
                scope_id="1",
                status="open",
                scheduler_algorithm="retired-algorithm",
                algorithm_version="1.0.0",
                snapshot_hash="retired",
                token_hash="retired",
                config_snapshot_json="{}",
                opened_at=now,
                expires_at=now + timedelta(hours=1),
            )
            db.session.add_all([lease_only, retired])
            db.session.commit()
            lease_only_id = lease_only.id
            retired_id = retired.id

            active = {
                "key": "legacy-anki",
                "version": "1.0.0",
                "state_schema_version": "anki-card-state.v1",
                "lifecycle_state": "active",
                "server_executable": True,
                "new_session_allowed": True,
                "existing_lease_allowed": True,
                "accepted_job_allowed": True,
                "history_read_allowed": True,
                "artifacts": {},
            }
            support = [
                active,
                {
                    **active,
                    "key": "draining-algorithm",
                    "lifecycle_state": "lease-only",
                    "new_session_allowed": False,
                },
                {
                    **active,
                    "key": "retired-algorithm",
                    "lifecycle_state": "retired",
                    "server_executable": False,
                    "new_session_allowed": False,
                    "existing_lease_allowed": False,
                    "accepted_job_allowed": False,
                },
            ]
            with patch(
                "app.services.study_architecture_audit_service."
                "list_study_algorithm_support",
                return_value=tuple(support),
            ):
                report = build_study_architecture_audit(now=now)

        unavailable = report["session_gates"][
            "active_session_unavailable_algo_samples"
        ]
        self.assertIn(retired_id, unavailable)
        self.assertNotIn(lease_only_id, unavailable)
        self.assertEqual(
            {
                item["lifecycle_state"]
                for item in report["algorithm_gates"]["algorithm_support"]
            },
            {"active", "lease-only", "retired"},
        )

    def test_real_entrypoint_provenance_and_audit_classification(self):
        """Invoke real review entrypoints (MCP, native direct command, session, import) and verify audit classification."""
        with self.app.app_context():
            user = User.query.first()
            card = Card.query.first()
            deck = Deck(name="Test Deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            card.note.deck_id = deck.id
            db.session.flush()

            # 1. Real MCP entrypoint via submit_review
            mcp_res = mcp_study_tools.submit_review(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                duration_ms=1500,
            )
            self.assertTrue(mcp_res["success"])

            # 2. Real native review command entrypoint
            cmd_res = execute_native_review_command(
                user=user,
                card=card,
                action="again",
                payload={"duration_ms": 2000, "timezone": "UTC"},
                clone_scope=None,
                requested_scope_id=deck.id,
                timezone_name="UTC",
            )
            self.assertIsNotNone(cmd_res)

            # 3. Real session review entrypoint via open_study_session and commit_study_session
            note_sess = Note(user_id=user.id, note_type_id=card.note.note_type_id, deck_id=deck.id, field_values={})
            db.session.add(note_sess)
            db.session.flush()
            card_sess = Card(note_id=note_sess.id, template_id=card.template_id)
            db.session.add(card_sess)
            db.session.flush()
            db.session.add(CardProgress(user_id=user.id, card_id=card_sess.id))
            db.session.commit()

            opened = open_study_session(
                user=user,
                query=Card.query.filter(Card.id == card_sess.id),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(deck.id),
                timezone_name="UTC",
            )
            commit_res = commit_study_session(
                user=user,
                session_id=opened["session_id"],
                payload={
                    "schema_version": "study-commit.v1",
                    "commit_id": f"commit-{uuid4()}",
                    "session_token": opened["session_token"],
                    "snapshot_hash": opened["snapshot_hash"],
                    "commit_reason": "manual_exit",
                    "events": [
                        {
                            "sequence": 1,
                            "event_id": str(uuid4()),
                            "card_id": card_sess.id,
                            "rating": "good",
                            "scheduler_offset_ms": 100,
                        }
                    ],
                    "final_states": [],
                },
            )
            self.assertIsNotNone(commit_res)

            # 4. Real Anki import entrypoint via anki_sync_service
            import_session = ConnectImportSession(
                user_id=user.id,
                source_key="anki_connect",
                status="active",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add(import_session)
            db.session.flush()

            note_ref = ConnectSourceNoteRef(
                user_id=user.id,
                source_key="anki_connect",
                external_note_id="ext_note_100",
                source_model_id="ext_model_100",
                source_deck_path="Default",
                note_id=card.note.id,
                content_hash="hash_note_100",
            )
            db.session.add(note_ref)
            db.session.flush()

            card_ref = ConnectSourceCardRef(
                user_id=user.id,
                source_key="anki_connect",
                external_card_id="ext_card_100",
                external_note_id="ext_note_100",
                card_id=card.id,
                source_ord=0,
            )
            db.session.add(card_ref)
            db.session.flush()

            status, ref = anki_sync_service._import_review(
                session=import_session,
                record={
                    "sourceReviewId": "1600000000000",
                    "sourceCardId": "ext_card_100",
                    "ease": 3,
                    "type": 1,
                    "ivl": 10,
                    "lastIvl": 5,
                    "factor": 2500,
                    "time": 3000,
                },
            )
            self.assertEqual(status, "imported")
            imported_payload = json.loads(ref.review_event.payload_json)
            self.assertEqual(
                imported_payload["provenance"]["source_path"],
                "external.anki.revlog",
            )
            self.assertNotIn("_study_runtime", imported_payload)

            # 5. Legacy unprovenanced review event without channel evidence -> unknown_provenance_events
            rev_legacy = ReviewEvent(
                user_id=user.id,
                card_id=card.id,
                rating="good",
                mode="review",
                reviewed_at=datetime.utcnow(),
            )
            db.session.add(rev_legacy)
            db.session.commit()

            report = build_study_architecture_audit()
            rg = report["review_event_gates"]
            self.assertGreaterEqual(rg["native_mcp_events"], 1)
            self.assertGreaterEqual(rg["native_direct_events"], 1)
            self.assertGreaterEqual(rg["native_session_events"], 1)
            self.assertGreaterEqual(rg["anki_import_events"], 1)
            self.assertGreaterEqual(rg["unknown_provenance_events"], 1)
            self.assertGreaterEqual(rg["canonical_payload_complete_events"], 4)
            self.assertGreaterEqual(rg["legacy_payload_unknown_events"], 1)
            self.assertEqual(rg["canonical_payload_missing_expected_field_events"], 0)
            self.assertEqual(rg["canonical_payload_conflicting_events"], 0)
            self.assertTrue(report["reconciliation"]["formula_checks"]["review_events_provenance_accounting"])
            self.assertTrue(
                report["reconciliation"]["formula_checks"][
                    "review_events_payload_provenance_accounting"
                ]
            )

    def test_session_config_snapshot_deep_validation(self):
        """Test deep schema validation and per-card scheduler_config_hash linkage for session config snapshots."""
        with self.app.app_context():
            user = User.query.first()
            card = Card.query.first()
            now = datetime(2026, 8, 29, 12, 0, 0)

            def policy_material(**overrides):
                material = {
                    "algorithm_key": "legacy-anki",
                    "algorithm_version": "1.0.0",
                    "config_schema_version": "scheduler-config.v1",
                    "timezone": "UTC",
                    "config": {"starting_ease": 2.5},
                }
                material.update(overrides)
                return material

            def frozen_policy(material, *, policy_key=None, config_hash=None):
                key = policy_key or study_artifact_service.canonical_digest(material)
                return key, {
                    **material,
                    "config_hash": config_hash if config_hash is not None else key,
                    "preset_id": None,
                }

            def add_session(label, snapshot, *, card_policy_key=None):
                session = StudySession(
                    user_id=user.id,
                    scope_type="deck",
                    scope_id="1",
                    status="open",
                    scheduler_algorithm="legacy-anki",
                    algorithm_version="1.0.0",
                    timezone="UTC",
                    snapshot_hash=f"snapshot-{label}",
                    token_hash=f"token-{label}",
                    config_snapshot_json=(
                        snapshot if isinstance(snapshot, str) else json.dumps(snapshot)
                    ),
                    opened_at=now,
                    expires_at=now + timedelta(hours=1),
                )
                db.session.add(session)
                db.session.flush()
                if card_policy_key is not None:
                    db.session.add(
                        StudySessionCard(
                            session_id=session.id,
                            card_id=card.id,
                            scheduler_config_hash=card_policy_key,
                            base_state_hash="base-state",
                            initial_state_json="{}",
                            ordinal=0,
                        )
                    )
                return session

            valid_key, valid_policy = frozen_policy(policy_material())
            valid_session = add_session(
                "valid",
                {valid_key: valid_policy},
                card_policy_key=valid_key,
            )

            invalid_sessions = []
            invalid_sessions.append(
                add_session(
                    "missing-card-hash",
                    {valid_key: valid_policy},
                    card_policy_key="missing-policy-key",
                )
            )
            invalid_sessions.append(add_session("array-root", "[1, 2, 3]"))

            missing_config_key = "not-a-canonical-policy-digest"
            invalid_sessions.append(
                add_session(
                    "missing-config",
                    {
                        missing_config_key: {
                            "algorithm_key": "legacy-anki",
                            "algorithm_version": "1.0.0",
                            "config_schema_version": "scheduler-config.v1",
                            "timezone": "UTC",
                            "config_hash": missing_config_key,
                        }
                    },
                    card_policy_key=missing_config_key,
                )
            )

            non_dict_material = policy_material(config="not-a-dict")
            non_dict_key, non_dict_policy = frozen_policy(non_dict_material)
            invalid_sessions.append(
                add_session(
                    "non-dict-config",
                    {non_dict_key: non_dict_policy},
                    card_policy_key=non_dict_key,
                )
            )

            wrong_version_material = policy_material(algorithm_version="2.0.0")
            wrong_version_key, wrong_version_policy = frozen_policy(wrong_version_material)
            invalid_sessions.append(
                add_session(
                    "wrong-version",
                    {wrong_version_key: wrong_version_policy},
                    card_policy_key=wrong_version_key,
                )
            )

            missing_version_material = policy_material()
            missing_version_material.pop("algorithm_version")
            missing_version_key, missing_version_policy = frozen_policy(
                missing_version_material
            )
            invalid_sessions.append(
                add_session(
                    "missing-version",
                    {missing_version_key: missing_version_policy},
                    card_policy_key=missing_version_key,
                )
            )

            wrong_schema_material = policy_material(
                config_schema_version="scheduler-config.v999"
            )
            wrong_schema_key, wrong_schema_policy = frozen_policy(
                wrong_schema_material
            )
            invalid_sessions.append(
                add_session(
                    "wrong-config-schema",
                    {wrong_schema_key: wrong_schema_policy},
                    card_policy_key=wrong_schema_key,
                )
            )

            wrong_hash_key, wrong_hash_policy = frozen_policy(
                policy_material(),
                config_hash="sha256-wrong-config-hash",
            )
            invalid_sessions.append(
                add_session(
                    "config-hash-mismatch",
                    {wrong_hash_key: wrong_hash_policy},
                    card_policy_key=wrong_hash_key,
                )
            )

            fake_digest = "sha256-" + ("0" * 64)
            _, fake_digest_policy = frozen_policy(
                policy_material(),
                policy_key=fake_digest,
            )
            invalid_sessions.append(
                add_session(
                    "fake-digest",
                    {fake_digest: fake_digest_policy},
                    card_policy_key=fake_digest,
                )
            )
            db.session.commit()

            report = build_study_architecture_audit(now=now)
            gates = report["session_gates"]
            # The fixture-level empty legacy snapshot is also invalid: a
            # genuine legacy policy map must contain at least one validated
            # canonical policy entry.
            self.assertEqual(gates["invalid_config_snapshot_sessions"], 10)
            self.assertNotIn(valid_session.id, gates["invalid_config_snapshot_samples"])
            self.assertTrue(
                {session.id for session in invalid_sessions}.issubset(
                    set(gates["invalid_config_snapshot_samples"])
                )
            )

    def test_reconciliation_detects_drift_when_formula_mismatches(self):
        """Verify that any formula check inequality triggers DRIFT_DETECTED status and blocking exit code 2."""
        with self.app.app_context():
            # Run audit on clean setup
            report = build_study_architecture_audit()
            self.assertEqual(report["reconciliation"]["status"], "VALID")

            # Patch formula check to simulate accounting drift / discrepancy
            with patch("app.services.study_architecture_audit_service.CardProgress.query") as mock_cp:
                # Force count mismatch
                mock_cp.count.return_value = 999999
                drift_report = build_study_architecture_audit()

            self.assertEqual(drift_report["reconciliation"]["status"], "DRIFT_DETECTED")
            self.assertFalse(drift_report["reconciliation"]["formula_checks"]["card_progress_accounting"])
            self.assertEqual(drift_report["verdicts"]["overall_status"], "BLOCK")
            self.assertEqual(drift_report["verdicts"]["exit_code"], 2)
            block_texts = " ".join(drift_report["verdicts"]["block"])
            self.assertIn("reconciliation_drift", block_texts)

    def test_privacy_and_sample_id_bounding_and_determinism(self):
        """Verify bounded sample size, privacy invariant, and deterministic fixed-timestamp runs."""
        with self.app.app_context():
            fixed_now = datetime(2026, 8, 29, 10, 0, 0)
            report1 = build_study_architecture_audit(now=fixed_now)
            report2 = build_study_architecture_audit(now=fixed_now)

            # Two runs with identical database and now must produce identical reports
            self.assertEqual(json.dumps(report1, sort_keys=True), json.dumps(report2, sort_keys=True))

            for item in report1["inventory"]:
                self.assertLessEqual(
                    len(item["sample_ids"]),
                    MAX_SAMPLE_IDS,
                    f"Category {item['category']} exceeded max sample ids",
                )
                # Verify that no sample ID contains raw answers or private PII
                for sample in item["sample_ids"]:
                    sample_str = str(sample)
                    self.assertNotIn("password", sample_str)
                    self.assertNotIn("email", sample_str)
                    self.assertNotIn("answer", sample_str)


if __name__ == "__main__":
    unittest.main()
