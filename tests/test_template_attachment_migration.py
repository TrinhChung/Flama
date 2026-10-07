"""Attachment expansion keeps identities and binds legacy inputs by FieldDef ID."""

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from models.template import Template
from models.study_application import StudyApplication

migration = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")


class TemplateAttachmentMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.original_op = getattr(op, "_proxy", None)
        op._proxy = Operations(MigrationContext.configure(self.connection))
        self.now = datetime(2026, 10, 7, 6, 7, 8)

    def tearDown(self):
        op._proxy = self.original_op
        self.connection.close()
        self.engine.dispose()

    def _schema(self, *, current=False):
        old_users, old_nt, old_templates, old_versions = migration.previous._tables()
        latest_templates, latest_apps, latest_fields = migration._tables()
        metadata = sa.MetaData()
        users = old_users.to_metadata(metadata)
        note_types = old_nt.to_metadata(metadata)
        templates = (latest_templates if current else old_templates).to_metadata(metadata)
        versions = old_versions.to_metadata(metadata)
        if current:
            applications = latest_apps.to_metadata(metadata)
        else:
            applications = sa.Table(
                "study_applications", metadata,
                *(column._copy() for column in latest_apps.c if column.name not in migration.APPLICATION_COLUMNS),
                sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
                sa.UniqueConstraint("template_id", "occurrence_key", name=migration.OLD_UNIQUE),
                sa.CheckConstraint("status_code IN ('ACTIVE')", name="ck_study_applications_status"),
                sa.Index("ix_study_applications_note_type_ord", "note_type_id", "source_ord"),
            )
        fields = latest_fields.to_metadata(metadata)
        cards = sa.Table(
            "cards", metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("application_id", sa.String(36), sa.ForeignKey("study_applications.id", ondelete="CASCADE"), nullable=False),
        )
        progress = sa.Table("probe_progress", metadata, sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True), sa.Column("revision", sa.Integer, nullable=False))
        metadata.create_all(self.connection)
        self.connection.execute(users.insert(), [{"id": 1}, {"id": 2}])
        self.connection.execute(note_types.insert(), [{"id": "nt-1", "user_id": 1}, {"id": "nt-2", "user_id": 2}])
        self.connection.execute(fields.insert(), [
            {"id": "word-1", "note_type_id": "nt-1", "name": "単語", "position": 0},
            {"id": "meaning-1", "note_type_id": "nt-1", "name": "Meaning", "position": 1},
            {"id": "word-2", "note_type_id": "nt-2", "name": "単語", "position": 0},
        ])
        self.connection.execute(templates.insert().values(id="template-1", note_type_id="nt-1", name="Original", front_html=" {{単語}}\r\n漢字 ", back_html="{{Meaning}}", shared_css="\n.card {}", position=2, is_default=True, created_at=self.now, updated_at=self.now))
        self.connection.execute(applications.insert().values(id="application-1", note_type_id="nt-1", template_id="template-1", occurrence_key="compat", source_ord=2, status_code="ACTIVE", created_at=self.now, updated_at=self.now))
        self.connection.execute(cards.insert().values(id="card-1", template_id="template-1", application_id="application-1"))
        self.connection.execute(progress.insert().values(card_id="card-1", revision=17))
        self.connection.commit()
        return templates, applications

    def _rows(self, name):
        table = sa.Table(name, sa.MetaData(), autoload_with=self.connection)
        return self.connection.execute(sa.select(table)).mappings().all()

    def test_legacy_upgrade_backfills_exact_ids_stable_bindings_and_layout(self):
        self._schema()
        source = dict(self._rows("templates")[0])
        migration.upgrade()
        migration.upgrade()
        template = self._rows("templates")[0]
        app = self._rows("study_applications")[0]
        for key, value in source.items():
            if key != "owner_user_id":
                self.assertEqual(template[key], value, key)
        self.assertEqual(template["owner_user_id"], 1)
        self.assertEqual(template["origin"], "authored")
        self.assertEqual(app["id"], "application-1")
        self.assertEqual(app["input_bindings"], {"単語": "word-1", "Meaning": "meaning-1"})
        self.assertEqual(app["position"], 2)
        self.assertTrue(app["is_default"])
        self.assertEqual(app["source_ord"], 2)
        self.assertEqual(app["updated_at"], self.now)
        self.assertEqual(self._rows("cards"), [{"id": "card-1", "template_id": "template-1", "application_id": "application-1"}])
        self.assertEqual(self._rows("probe_progress"), [{"card_id": "card-1", "revision": 17}])
        self.connection.commit()
        self.connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        self.assertEqual(self.connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])

    def test_current_precreated_schema_is_accepted_with_enforced_foreign_keys(self):
        self._schema(current=True)
        self.connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        migration.upgrade()
        migration.upgrade()
        self.assertEqual(self._rows("study_applications")[0]["input_bindings"]["単語"], "word-1")
        self.assertEqual(self.connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])

    def test_legacy_rebuild_refuses_enforced_foreign_keys_before_ddl(self):
        self._schema()
        self.connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        with self.assertRaisesRegex(RuntimeError, "requires foreign_keys=OFF"):
            migration.upgrade()
        self.assertNotIn("origin", {row["name"] for row in sa.inspect(self.connection).get_columns("templates")})
        self.assertEqual(self._rows("probe_progress")[0]["revision"], 17)

    def test_scoped_occurrences_support_same_template_on_another_note_type_and_retirement(self):
        self._schema()
        migration.upgrade()
        table = sa.Table("study_applications", sa.MetaData(), autoload_with=self.connection)
        self.connection.execute(table.insert().values(id="application-2", note_type_id="nt-2", template_id="template-1", occurrence_key="compat", source_ord=None, status_code="RETIRED", created_at=self.now, updated_at=self.now))
        self.assertEqual(len(self._rows("study_applications")), 2)
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(table.insert().values(id="duplicate", note_type_id="nt-2", template_id="template-1", occurrence_key="compat", status_code="ACTIVE", created_at=self.now, updated_at=self.now))
        self.assertEqual(self._rows("probe_progress")[0]["revision"], 17)

    def test_existing_explicit_bindings_and_attachment_metadata_are_not_overwritten(self):
        _, applications = self._schema(current=True)
        self.connection.execute(applications.update().values(input_bindings={"Answer": "word-1"}, position=9, is_default=False, display_name="Custom"))
        migration.upgrade()
        app = self._rows("study_applications")[0]
        self.assertEqual(app["input_bindings"], {"Answer": "word-1"})
        self.assertEqual(app["position"], 9)
        self.assertFalse(app["is_default"])
        self.assertEqual(app["display_name"], "Custom")

    def test_field_rename_keeps_backfilled_binding_keys_and_ids(self):
        self._schema()
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE field_defs SET name='New name' WHERE id='word-1'"))
        migration.upgrade()
        self.assertEqual(self._rows("study_applications")[0]["input_bindings"]["単語"], "word-1")

    def test_drift_fails_before_source_schema_mutation(self):
        self._schema()
        self.connection.exec_driver_sql("ALTER TABLE study_applications ADD COLUMN display_name INTEGER")
        with self.assertRaisesRegex(RuntimeError, "display_name type/nullability/default differs"):
            migration.upgrade()
        self.assertNotIn("origin", {row["name"] for row in sa.inspect(self.connection).get_columns("templates")})

    def test_downgrade_preserves_all_expanded_state(self):
        self._schema()
        migration.upgrade()
        with self.assertRaisesRegex(RuntimeError, "downgrade refuses"):
            migration.downgrade()
        self.assertEqual(self._rows("study_applications")[0]["input_bindings"]["単語"], "word-1")

    def test_mysql_schema_uses_nullable_origin_notetype_and_version_lineage_cycle(self):
        templates, applications, _ = migration._tables()
        sql = str(CreateTable(templates).compile(dialect=mysql.dialect()))
        app_sql = str(CreateTable(applications).compile(dialect=mysql.dialect()))
        self.assertIn("note_type_id VARCHAR(36),", sql)
        self.assertIn("REFERENCES note_types (id) ON DELETE SET NULL", sql)
        self.assertNotIn("FOREIGN KEY(source_version_id)", sql)
        self.assertIn("UNIQUE (note_type_id, template_id, occurrence_key)", app_sql)
        self.assertIn("'RETIRED'", app_sql)


class TemplateAttachmentCompatHookTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from models import db
        self.db = db
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "STARTUP_RUN_MAINTENANCE": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.db.drop_all()
        self.context.pop()

    def test_standalone_has_no_compat_and_cards_bind_by_note_type(self):
        from models.user import User
        from models.note_type import NoteType
        from models.note import Note
        from models.card import Card
        user = User(username="attachments", email="attachments@example.test")
        self.db.session.add(user)
        self.db.session.flush()
        first = NoteType(user_id=user.id, name="First")
        second = NoteType(user_id=user.id, name="Second")
        standalone = Template(owner_user_id=user.id, name="Standalone")
        self.db.session.add_all([first, second, standalone])
        self.db.session.commit()
        self.assertEqual(StudyApplication.query.count(), 0)
        note_a = Note(note_type_id=first.id, user_id=user.id)
        note_b = Note(note_type_id=second.id, user_id=user.id)
        card_a = Card(note=note_a, template=standalone)
        card_b = Card(note=note_b, template=standalone)
        self.db.session.add_all([note_a, note_b, card_a, card_b])
        self.db.session.commit()
        self.assertNotEqual(card_a.application_id, card_b.application_id)
        self.assertEqual(card_a.application.note_type_id, first.id)
        self.assertEqual(card_b.application.note_type_id, second.id)
        self.assertEqual(card_a.application.template_id, standalone.id)
        self.assertEqual(card_b.application.template_id, standalone.id)

    def test_notetype_delete_sets_origin_null_and_keeps_template_and_versions(self):
        from models.user import User
        from models.note_type import NoteType
        from models.template_version import TemplateVersion
        self.db.session.execute(sa.text("PRAGMA foreign_keys=ON"))
        user = User(username="detach", email="detach@example.test")
        self.db.session.add(user)
        self.db.session.flush()
        note_type = NoteType(user_id=user.id, name="Origin")
        template = Template(note_type=note_type, name="Reusable")
        self.db.session.add_all([note_type, template])
        self.db.session.commit()
        template_id = template.id
        self.db.session.delete(note_type)
        self.db.session.commit()
        self.db.session.expire_all()
        self.assertIsNone(self.db.session.get(Template, template_id).note_type_id)
        self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 1)
