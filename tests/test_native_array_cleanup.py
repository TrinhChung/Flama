"""Transaction and compatibility checks for the native array cleanup."""
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/migrations'))
import native_array_cleanup as cleanup
import native_array_audit as audit
from native_array_templates import modernize
from app import create_app
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_version import TemplateVersion
from models.user import User
from models.study_application import StudyApplication
from tests.study_note_fixtures import create_note_user, attach_template


class NativeArrayCleanupTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'STARTUP_RUN_MAINTENANCE': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False})

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = create_note_user(db.session, username='owner', email='owner@example.com')
        db.session.add(user)
        db.session.flush()
        nt = NoteType(user_id=user.id, name='Array')
        db.session.add(nt)
        db.session.flush()
        self.field = FieldDef(note_type_id=nt.id, name='Answer', field_type='array', position=0)
        self.note = Note(user_id=user.id, note_type_id=nt.id,
            field_values={'Answer': 'one; literal\ntwo\none; literal', 'Other': '<b>keep</b>'})
        self.native = Note(user_id=user.id, note_type_id=nt.id,
            field_values={'Answer': ['a,b', '', ['nested', 'items'], 'a,b']})
        db.session.add(self.field)
        db.session.flush()
        self.template = attach_template(db.session, owner_user_id=user.id, note_type_id=nt.id, name='Array',
            front_html='{{#Answer}}<div>{{Answer}}</div>{{/Answer}}', back_html='', shared_css='.card{color:red}')
        db.session.add_all([self.field, self.note, self.native, self.template])
        db.session.commit()
        self.publication = TemplatePublication(template_id=self.template.id, auto_publish_enabled=True)
        db.session.add(self.publication)
        db.session.commit()
        self.manifest = {'schema_version': cleanup.SCHEMA, 'fields': [{
            'id': self.field.id, 'note_type_id': nt.id, 'name': 'Answer', 'owner_user_id': user.id}],
            'templates': [{'id': self.template.id, 'note_type_id': nt.id, 'owner_user_id': user.id,
                'array_names': ['Answer'], 'allowed_before_hashes': [cleanup.digest(cleanup.template_snapshot(self.template))]}]}

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def plan(self):
        return cleanup.build_plan(db.session, self.manifest)

    def test_apply_restore_idempotent_history_and_no_publication(self):
        plan = self.plan()
        before_audit = audit.snapshot(db.session)
        old_versions = {v.id: (v.front_html, v.back_html) for v in TemplateVersion.query.all()}
        calls = []
        from app.services import template_release_service
        original = template_release_service.on_version_appended
        def observe(*args, **kwargs):
            calls.append(self.publication.auto_publish_enabled)
            return original(*args, **kwargs)
        with patch.object(template_release_service, 'on_version_appended', side_effect=observe):
            cleanup.apply_plan(db.session, plan)
            db.session.commit()
        self.assertEqual(calls, [False])
        self.assertTrue(self.publication.auto_publish_enabled)
        self.assertEqual(self.note.field_values['Answer'], ['one; literal', 'two', 'one; literal'])
        cleanup.verify_plan(db.session, plan)
        audit.compare(before_audit, audit.snapshot(db.session), plan)
        self.assertEqual(self.native.field_values['Answer'], ['a,b', '', ['nested', 'items'], 'a,b'])
        self.assertEqual(self.template.shared_css, '.card{color:red}')
        self.assertEqual(self.plan()['summary']['changed_notes'], 0)
        self.assertEqual(self.plan()['summary']['updated_templates'], 0)
        for version_id, value in old_versions.items():
            version = db.session.get(TemplateVersion, version_id)
            self.assertEqual((version.front_html, version.back_html), value)
        cleanup.apply_plan(db.session, plan, restore=True)
        db.session.commit()
        self.assertEqual(self.note.field_values['Answer'], 'one; literal\ntwo\none; literal')
        cleanup.verify_plan(db.session, plan, restored=True)
        audit.compare(before_audit, audit.snapshot(db.session), plan, restored=True)
        self.assertEqual(self.template.front_html, '{{#Answer}}<div>{{Answer}}</div>{{/Answer}}')
        self.assertEqual(TemplateVersion.query.count(), len(old_versions) + 2)
        self.assertTrue(self.publication.auto_publish_enabled)

    def test_changed_binding_or_application_scope_blocks_apply_before_any_write(self):
        plan = self.plan()
        application = StudyApplication.query.filter_by(template_id=self.template.id).one()
        application.input_bindings = {'Answer': None}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'attachment scope changed'):
            cleanup.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertIsInstance(self.note.field_values['Answer'], str)
        self.assertEqual(AuditLog.query.count(), 0)

    def test_reused_definition_requires_reviewed_array_fields_in_every_active_scope(self):
        original_application = StudyApplication.query.filter_by(template_id=self.template.id).one()
        second_type = NoteType(user_id=self.note.user_id, name='Second array scope')
        db.session.add(second_type)
        db.session.flush()
        second_field = FieldDef(note_type_id=second_type.id, name='Answer', field_type='array')
        second_note = Note(user_id=self.note.user_id, note_type_id=second_type.id, field_values={'Answer': 'two\nthree'})
        db.session.add_all([second_field, second_note])
        db.session.flush()
        db.session.add(StudyApplication(template_id=self.template.id, note_type_id=second_type.id,
            occurrence_key='second-scope', input_bindings={'Answer': second_field.id}))
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'outside the reviewed field scope'):
            self.plan()
        self.manifest['fields'].append({'id': second_field.id, 'note_type_id': second_type.id,
            'name': 'Answer', 'owner_user_id': self.note.user_id})
        plan = self.plan()
        self.assertEqual(len(plan['templates'][0]['application_scope']), 2)
        cleanup.apply_plan(db.session, plan)
        db.session.commit()
        cleanup.verify_plan(db.session, plan)
        self.assertEqual(second_note.field_values['Answer'], ['two', 'three'])
        self.assertEqual(original_application.status_code, 'ACTIVE')
        self.assertEqual(StudyApplication.query.count(), 2)

    def test_matching_definition_owner_cannot_substitute_unrelated_note_type_scope(self):
        other = NoteType(user_id=self.note.user_id, name='Unattached')
        db.session.add(other)
        db.session.commit()
        self.manifest['templates'][0]['note_type_id'] = other.id
        with self.assertRaisesRegex(ValueError, 'Template scope mismatch'):
            self.plan()

    def test_injected_failure_rollback(self):
        plan = self.plan()
        version_count = TemplateVersion.query.count()
        with self.assertRaisesRegex(RuntimeError, 'Injected failure'):
            cleanup.apply_plan(db.session, plan, fail_after=1)
        db.session.rollback()
        self.assertIsInstance(self.note.field_values['Answer'], str)
        self.assertTrue(self.publication.auto_publish_enabled)
        self.assertEqual(TemplateVersion.query.count(), version_count)
        self.assertEqual(AuditLog.query.count(), 0)
        # A rolled-back operation must not restore old flags on a later edit.
        self.publication.auto_publish_enabled = False
        db.session.commit()
        self.assertFalse(self.publication.auto_publish_enabled)

    def test_stale_note_and_template_prevent_all_writes(self):
        plan = self.plan()
        self.template.shared_css = 'edited'
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Stale/missing template'):
            cleanup.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertIsInstance(self.note.field_values['Answer'], str)
        self.manifest['templates'][0]['allowed_before_hashes'] = [cleanup.digest(cleanup.template_snapshot(self.template))]
        plan = self.plan()
        self.note.field_values = {**self.note.field_values, 'Other': 'edited'}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Stale/missing note'):
            cleanup.apply_plan(db.session, plan)
        db.session.rollback()

    def test_wrong_identity_tamper_and_scope(self):
        plan = self.plan()
        plan['identity']['server'] = 'wrong'
        plan['checksum'] = cleanup.digest({k: v for k, v in plan.items() if k != 'checksum'})
        with self.assertRaisesRegex(ValueError, 'identity'):
            cleanup.apply_plan(db.session, plan)
        plan = self.plan()
        plan['notes'][0]['values']['Answer']['after'] = ['tamper']
        with self.assertRaisesRegex(ValueError, 'tampered'):
            cleanup.apply_plan(db.session, plan)
        self.manifest['fields'][0]['owner_user_id'] = 999
        with self.assertRaisesRegex(ValueError, 'scope/type'):
            self.plan()

    def test_repair_requires_scope_and_preimage(self):
        self.manifest['repair_scope_ids'] = [self.note.id]
        self.manifest['repairs'] = [{'id': self.note.id, 'owner_user_id': self.note.user_id,
            'note_type_id': self.note.note_type_id, 'expected': {'Answer': ['one; literal', 'two', 'one; literal']},
            'values': {'Answer': ['reviewed']}}]
        plan = cleanup.build_plan(db.session, self.manifest, include_repairs=True)
        cleanup.apply_plan(db.session, plan)
        db.session.commit()
        self.assertEqual(self.note.field_values['Answer'], ['reviewed'])
        self.manifest['repair_scope_ids'] = []
        with self.assertRaisesRegex(ValueError, 'explicit note IDs'):
            cleanup.build_plan(db.session, self.manifest, include_repairs=True)

    def test_authored_loops_attributes_and_inverted_sections_fail_closed(self):
        for source in ('{{#Answer}}{{.}}{{/Answer}}', '<div title="{{Answer}}"></div>', '{{^Answer}}empty{{/Answer}}'):
            with self.assertRaises(ValueError):
                modernize(source, {'Answer'})

    def test_audit_rejects_unplanned_schema_changes(self):
        before = audit.snapshot(db.session)
        plan = self.plan()
        cleanup.apply_plan(db.session, plan)
        db.session.commit()
        self.field.position = 10
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Protected data changed'):
            audit.compare(before, audit.snapshot(db.session), plan)

    def test_audit_preserves_retired_field_values_outside_the_named_adapter(self):
        retired = FieldDef(note_type_id=self.note.note_type_id, name='Retired', field_type='text')
        db.session.add(retired)
        db.session.flush()
        self.note.field_values = {**self.note.field_values, 'Retired': 'keep tombstone'}
        db.session.commit()
        retired_id = retired.id
        db.session.delete(retired)
        db.session.commit()
        self.assertNotIn('Retired', self.note.field_values)
        before = audit.snapshot(db.session)
        plan = self.plan()
        cleanup.apply_plan(db.session, plan)
        db.session.commit()
        audit.compare(before, audit.snapshot(db.session), plan)
        self.assertEqual(self.note.field_values_by_id[retired_id], 'keep tombstone')
        self.note.field_values_by_id = {**self.note.field_values_by_id, retired_id: 'unexpected'}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Protected data changed: note_metadata'):
            audit.compare(before, audit.snapshot(db.session), plan)

    def test_legacy_backfill_keeps_empty_pair_positions_and_rejects_lossy_cleanup(self):
        self.assertEqual(cleanup.array_value('a; literal\r\n\r\na; literal'), ['a; literal', '', 'a; literal'])
        self.assertEqual(cleanup.array_value(''), [])
        self.assertIsNone(cleanup.array_value(None))
        with self.assertRaisesRegex(ValueError, 'review separately'):
            cleanup.array_value('  meaningful spaces  ')

    def test_vocabulary_presenter_includes_array_in_ordered_names_and_reexports(self):
        from app.presenters import vocabulary_presenter
        from app.repositories import vocabulary_repository
        self.assertIs(vocabulary_presenter.note_ordered_field_names, vocabulary_repository.note_ordered_field_names)
        self.assertIs(vocabulary_presenter.note_display_triplet, vocabulary_repository.note_display_triplet)
        names = vocabulary_presenter.note_ordered_field_names(self.note, text_only=True)
        self.assertIn("Answer", names)

    def test_update_field_blocks_direct_type_change_to_or_from_array(self):
        from app.services.flashcard_content_service import update_field, ContentApiError
        # Changing from array to text is blocked
        with self.assertRaises(ContentApiError) as cm:
            update_field(
                user_id=self.note.user_id,
                note_type_id=self.field.note_type_id,
                field_id=self.field.id,
                payload={"name": "Answer", "field_type": "text"},
            )
        self.assertEqual(cm.exception.status, 409)
        self.assertEqual(cm.exception.error, "FIELD_TYPE_REQUIRES_CONVERSION")

    def test_connect_normalized_identity_handles_list_without_repr(self):
        from app.services.connect.base import _normalized_identity
        self.assertEqual(_normalized_identity(["word1", "word2"]), "word1 word2")
        self.assertEqual(_normalized_identity("  simple   text  "), "simple text")
