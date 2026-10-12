"""Independent owned definitions and explicitly scoped attachment contracts."""

import unittest
from datetime import datetime
import sqlalchemy as sa

from app import create_audit_app
from app.repositories import template_library_repository as repository
from app.repositories.template_version_repository import owned_template
from app.services.mcp.note_type_tools import get_note_type_schema, list_note_types, update_note_type
from app.services.study_note_template_service import stage_note_template_changes
from app.repositories.study_authority_repository import StudyAuthorityRoute
from app.services.template_library_service import serialize_template
from app.services.flashcards_share_service import clone_note_type_for_user
from app.services.study_composition_service import resolve_compatibility_compositions_for_note_type, group_available_compositions
from models import db
from models.card import Card, PresentationAlias
from models.field_def import FieldDef
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User


class TemplateOriginRetirementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "REDIS_URL": ""})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.owner = User(username="origin-retirement", email="origin-retirement@example.test")
        db.session.add(self.owner)
        db.session.flush()
        self.first = NoteType(name="First", user_id=self.owner.id)
        self.second = NoteType(name="Second", user_id=self.owner.id)
        db.session.add_all([self.first, self.second])
        db.session.flush()
        db.session.add_all([FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0) for nt in (self.first, self.second)])
        db.session.add(StudyAuthorityEnrollment(learner_user_id=self.owner.id, mode_code="NOTE", epoch=3,
                                               created_at=datetime(2026, 10, 1), updated_at=datetime(2026, 10, 1)))
        db.session.commit()
        self.route = StudyAuthorityRoute(self.owner.id, "NOTE", 3, True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _template(self):
        row = repository.create_attached_template(db.session, note_type=self.first, name="Shared",
                                                 front_html="{{Word}}", back_html="{{Word}}", position=2, is_default=True)
        db.session.commit()
        return row

    def _attach_second(self, template, position=9):
        app = StudyApplication(note_type=self.second, template=template, occurrence_key="compat", source_ord=0,
                               position=position, is_default=True, status_code="ACTIVE")
        db.session.add(app)
        db.session.commit()
        return app

    def test_metadata_has_no_origin_column_or_relationship(self):
        self.assertNotIn("note_type_id", Template.__table__.c)
        self.assertNotIn("note_type", sa.inspect(Template).relationships)
        self.assertNotIn("templates", sa.inspect(NoteType).relationships)
        self.assertFalse(Template.__table__.c.owner_user_id.nullable)

    def test_independent_definition_creates_no_attachment_implicitly(self):
        row = Template(owner_user_id=self.owner.id, name="Standalone", front_html="{{Word}}", back_html="")
        db.session.add(row)
        db.session.commit()
        self.assertEqual(StudyApplication.query.filter_by(template_id=row.id).count(), 0)
        self.assertEqual(serialize_template(row)["owner_user_id"], self.owner.id)
        self.assertIs(owned_template(db.session, user_id=self.owner.id, template_id=row.id), row)

    def test_attached_creation_is_atomic_and_writes_no_cards_or_aliases(self):
        row = repository.create_attached_template(db.session, note_type=self.first, name="Pending",
                                                 front_html="{{Word}}", back_html="", position=7, is_default=True)
        db.session.flush()
        application = StudyApplication.query.filter_by(template_id=row.id).one()
        self.assertEqual((application.position, application.is_default, application.source_ord), (7, True, 7))
        self.assertEqual(application.input_bindings["Word"], self.first.field_defs[0].id)
        self.assertEqual(Card.query.count(), 0)
        self.assertEqual(PresentationAlias.query.count(), 0)
        identity = row.id
        db.session.rollback()
        self.assertIsNone(db.session.get(Template, identity))

    def test_mcp_reads_all_scoped_applications_instead_of_origin_definitions(self):
        row = self._template()
        app = self._attach_second(row)
        schema = get_note_type_schema(user_id=self.owner.id, note_type_id=self.second.id)
        self.assertEqual(len(schema["templates"]), 1)
        self.assertEqual(schema["templates"][0]["id"], row.id)
        self.assertEqual(schema["templates"][0]["application_id"], app.id)
        self.assertEqual(schema["templates"][0]["position"], 9)
        counts = {item["id"]: item["template_count"] for item in list_note_types(user_id=self.owner.id)}
        self.assertEqual(counts[self.first.id], 1)
        self.assertEqual(counts[self.second.id], 1)

    def test_order_and_default_are_independent_for_each_application_scope(self):
        row = self._template()
        self._attach_second(row)
        views = [repository.attached_templates(db.session, nt.id)[0] for nt in (self.first, self.second)]
        self.assertEqual([view.position for view in views], [2, 9])
        self.assertEqual([view.is_default for view in views], [True, True])
        self.assertEqual(row.position, 0)

    def test_deleting_origin_note_type_preserves_owned_definition_history_and_other_attachment(self):
        row = self._template()
        second_app = self._attach_second(row)
        versions = TemplateVersion.query.filter_by(template_id=row.id).count()
        db.session.delete(self.first)
        db.session.commit()
        self.assertIsNotNone(db.session.get(Template, row.id))
        self.assertEqual(TemplateVersion.query.filter_by(template_id=row.id).count(), versions)
        self.assertIsNotNone(db.session.get(StudyApplication, second_app.id))
        self.assertIsNotNone(owned_template(db.session, user_id=self.owner.id, template_id=row.id))

    def test_schema_removal_retires_attachment_without_deleting_independent_definition(self):
        shared = self._template()
        other = self._attach_second(shared)
        repository.create_attached_template(db.session, note_type=self.first, name="Keep", front_html="", back_html="", position=3)
        db.session.commit()
        old = repository.applications(db.session, self.first.id)[0]
        stage_note_template_changes(db.session, routes=[self.route], note_type=self.first,
                                    changes={"removed": [shared.name]}, operation_key="remove-one")
        db.session.commit()
        self.assertEqual(db.session.get(StudyApplication, old.id).status_code, "RETIRED")
        self.assertEqual(db.session.get(StudyApplication, other.id).status_code, "ACTIVE")
        self.assertIsNotNone(db.session.get(Template, shared.id))

    def test_repeated_application_update_requires_explicit_identity_and_changes_only_that_position(self):
        row = self._template()
        repeated = StudyApplication(note_type=self.first, template=row, occurrence_key="repeat", source_ord=None,
                                    position=11, is_default=False, status_code="ACTIVE")
        db.session.add(repeated)
        db.session.commit()
        with self.assertRaisesRegex(ValueError, "application_id"):
            stage_note_template_changes(db.session, routes=[self.route], note_type=self.first,
                                        changes={"updated": [{"id": row.id, "position": 18}]}, operation_key="ambiguous")
        db.session.rollback()
        stage_note_template_changes(db.session, routes=[self.route], note_type=self.first,
                                    changes={"updated": [{"application_id": repeated.id, "position": 18}]}, operation_key="explicit")
        db.session.commit()
        self.assertEqual(db.session.get(StudyApplication, repeated.id).position, 18)
        original = StudyApplication.query.filter_by(template_id=row.id, occurrence_key="compat").one()
        self.assertEqual(original.position, 2)

    def test_clone_repeated_applications_copy_one_definition_and_remap_field_bindings(self):
        row = self._template()
        field = self.first.field_defs[0]
        repeated = StudyApplication(note_type=self.first, template=row, occurrence_key="repeat", source_ord=None,
                                    position=11, is_default=False, status_code="ACTIVE", input_bindings={"Word": field.id})
        recipient = User(username="origin-recipient", email="origin-recipient@example.test")
        db.session.add_all([repeated, recipient])
        db.session.commit()
        clone = clone_note_type_for_user(self.first, recipient.id)
        db.session.commit()
        applications = repository.applications(db.session, clone.id)
        self.assertEqual(len(applications), 2)
        self.assertEqual(len({app.template_id for app in applications}), 1)
        cloned_field_id = clone.field_defs[0].id
        self.assertNotEqual(cloned_field_id, field.id)
        self.assertEqual({app.input_bindings["Word"] for app in applications}, {cloned_field_id})
        self.assertIsNone(next(app for app in applications if app.occurrence_key == "repeat").source_ord)

    def test_explicit_none_source_ordinal_is_not_assigned_from_position(self):
        row = repository.create_attached_template(db.session, note_type=self.first, name="No ordinal",
                                                 front_html="", back_html="", position=12, source_ord=None)
        db.session.commit()
        self.assertIsNone(StudyApplication.query.filter_by(template_id=row.id).one().source_ord)

    def test_mcp_update_locks_applications_and_changes_scoped_position_without_origin_lookup(self):
        row = self._template()
        second = self._attach_second(row)
        original = repository.applications(db.session, self.first.id)[0]
        result = update_note_type(user_id=self.owner.id, note_type_id=self.first.id,
                                  templates={"updated": [{"application_id": original.id, "position": 17}]})
        self.assertEqual(result["templates"][0]["position"], 17)
        self.assertEqual(db.session.get(StudyApplication, second.id).position, 9)
        self.assertEqual(db.session.get(Template, row.id).position, 0)

    def test_composition_group_order_uses_scoped_application_positions(self):
        first = self._template()
        second = repository.create_attached_template(db.session, note_type=self.first, name="Earlier",
                                                     front_html="", back_html="", position=1)
        first.position = -100  # Old definition metadata is not attachment order.
        db.session.commit()
        compositions = resolve_compatibility_compositions_for_note_type(self.first.id)
        groups = group_available_compositions(list(reversed(compositions)))
        self.assertEqual([item.template_id for item in groups[0].compositions], [second.id, first.id])


if __name__ == "__main__":
    unittest.main()
