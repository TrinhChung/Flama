"""The "answers" field type is renamed to "array" in fields and template input schemas."""

from __future__ import annotations

import importlib
import json
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User


migration = importlib.import_module("migrations.versions.20261010_000056_rename_answers_field_type_to_array")


class ArrayFieldTypeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="owner", email="owner@example.test")
        db.session.add(user)
        db.session.flush()
        note_type = NoteType(user_id=user.id, name="Vocab")
        db.session.add(note_type)
        db.session.flush()
        schema = [
            {"key": "Prompt", "label": "Prompt", "type": "text", "required": True},
            {"key": "Answer", "label": "Answer", "type": "answers", "required": True, "typing": {"hints": True}},
        ]
        template = Template(owner_user_id=user.id, name="Typed", front_html="{{Prompt}}", back_html="{{Answer}}", input_schema=schema)
        plain = Template(owner_user_id=user.id, name="Plain", front_html="{{Prompt}}", input_schema=[schema[0]])
        db.session.add_all([template, plain])
        db.session.commit()
        self.note_type_id, self.template_id, self.plain_id = note_type.id, template.id, plain.id
        # Creating the template wrote its first version with the same input schema.
        self.version_id = db.session.execute(
            sa.select(TemplateVersion.id).where(TemplateVersion.template_id == template.id)
        ).scalar_one()
        # The model no longer knows "answers", so old field rows are written as raw SQL.
        for name, field_type in (("Prompt", "text"), ("Answer", "answers")):
            db.session.execute(
                sa.text(
                    "INSERT INTO field_defs (id, note_type_id, name, field_type, position, required, created_at, updated_at) "
                    "VALUES (:id, :note_type_id, :name, :field_type, 0, 0, '2026-10-10 00:00:00', '2026-10-10 00:00:00')"
                ),
                {"id": f"f-{name}", "note_type_id": note_type.id, "name": name, "field_type": field_type},
            )
        db.session.commit()

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _run(self, step):
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            step()

    def _field_types(self):
        rows = db.session.execute(sa.text("SELECT name, field_type FROM field_defs ORDER BY name")).all()
        return dict(rows)

    def _schema_types(self, table, row_id):
        raw = db.session.execute(sa.text(f"SELECT input_schema FROM {table} WHERE id = :id"), {"id": row_id}).scalar_one()
        schema = json.loads(raw) if isinstance(raw, str) else raw
        return [item["type"] for item in schema]

    def test_upgrade_renames_field_and_input_types_and_downgrade_restores_them(self):
        version_id = self.version_id
        self.assertEqual(self._schema_types("template_versions", version_id), ["text", "answers"])
        self._run(migration.upgrade)
        self._run(migration.upgrade)
        self.assertEqual(self._field_types(), {"Answer": "array", "Prompt": "text"})
        self.assertEqual(self._schema_types("templates", self.template_id), ["text", "array"])
        self.assertEqual(self._schema_types("template_versions", version_id), ["text", "array"])
        self.assertEqual(self._schema_types("templates", self.plain_id), ["text"])
        typed = db.session.execute(sa.text("SELECT input_schema FROM templates WHERE id = :id"), {"id": self.template_id}).scalar_one()
        self.assertEqual((json.loads(typed) if isinstance(typed, str) else typed)[1]["typing"], {"hints": True})

        self._run(migration.downgrade)
        self.assertEqual(self._field_types(), {"Answer": "answers", "Prompt": "text"})
        self.assertEqual(self._schema_types("templates", self.template_id), ["text", "answers"])
        self.assertEqual(self._schema_types("template_versions", version_id), ["text", "answers"])


if __name__ == "__main__":
    unittest.main()
