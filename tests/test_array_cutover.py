"""Production cutover invariants: atomic failure, stale writes, scope and restore."""
import importlib.util
from pathlib import Path
import unittest

from app import create_app
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.user import User

spec = importlib.util.spec_from_file_location('array_cutover', Path(__file__).resolve().parents[1] / 'scripts/migrations/array_cutover.py')
cutover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cutover)


class ArrayCutoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'STARTUP_RUN_MAINTENANCE': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False})

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        owner = User(username='owner', email='owner@example.com')
        other = User(username='other', email='other@example.com')
        db.session.add_all([owner, other])
        db.session.flush()
        nt = NoteType(user_id=owner.id, name='Example')
        other_nt = NoteType(user_id=other.id, name='Example')  # same name, different identity
        db.session.add_all([nt, other_nt])
        db.session.flush()
        self.field = FieldDef(note_type_id=nt.id, name='Meaning', field_type='text', position=0)
        self.foreign_field = FieldDef(note_type_id=other_nt.id, name='Meaning', field_type='text', position=0)
        self.note = Note(user_id=owner.id, note_type_id=nt.id, field_values={'Meaning': 'a; b; a', 'Usage': '<b>keep</b>'})
        self.null_note = Note(user_id=owner.id, note_type_id=nt.id, field_values={'Meaning': None})
        self.missing_note = Note(user_id=owner.id, note_type_id=nt.id, field_values={'Usage': 'missing'})
        self.foreign_note = Note(user_id=owner.id, note_type_id=other_nt.id, field_values={'Meaning': 'x; y'})
        db.session.add_all([self.field, self.foreign_field, self.note, self.null_note, self.missing_note, self.foreign_note])
        db.session.commit()
        self.manifest = {'fields': [{'id': self.field.id, 'note_type_id': nt.id, 'name': 'Meaning',
            'owner_user_id': owner.id, 'parser': 'paired'}]}

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def plan(self):
        plan = cutover.build_plan(db.session, self.manifest)
        plan['checksum'] = cutover.digest(plan)
        return plan

    def test_apply_restore_and_idempotent_native_punctuation(self):
        plan = self.plan()
        self.assertEqual(plan['summary']['changed_notes'], 1)
        cutover.apply_plan(db.session, plan)
        db.session.commit()
        self.assertEqual(self.note.field_values, {'Meaning': 'a\nb\na', 'Usage': '<b>keep</b>'})
        self.assertEqual(self.field.field_type, 'array')
        self.assertEqual(self.foreign_field.field_type, 'text')
        self.assertEqual(self.foreign_note.field_values, {'Meaning': 'x; y'})
        self.assertEqual(self.null_note.field_values, {'Meaning': None})
        self.assertEqual(self.missing_note.field_values, {'Usage': 'missing'})
        self.assertEqual(self.plan()['summary']['changed_notes'], 0)
        cutover.apply_plan(db.session, plan, restore=True)
        db.session.commit()
        self.assertEqual(self.note.field_values['Meaning'], 'a; b; a')
        self.assertEqual(self.field.field_type, 'text')
        self.field.field_type = 'array'
        self.note.field_values = {'Meaning': 'one; literal, slash/inside\ntwo'}
        db.session.commit()
        self.assertEqual(self.plan()['summary']['changed_notes'], 0)

    def test_injected_failure_rolls_back_type_content_and_audit(self):
        plan = self.plan()
        with self.assertRaisesRegex(RuntimeError, 'Injected failure'):
            cutover.apply_plan(db.session, plan, fail_after=1)
        db.session.rollback()
        self.assertEqual(self.field.field_type, 'text')
        self.assertEqual(self.note.field_values['Meaning'], 'a; b; a')
        self.assertEqual(AuditLog.query.count(), 0)

    def test_stale_non_target_edit_is_not_overwritten(self):
        plan = self.plan()
        self.note.field_values = {**self.note.field_values, 'Usage': 'edited after preview'}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Stale/missing note'):
            cutover.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertEqual(self.note.field_values['Usage'], 'edited after preview')
        self.assertEqual(self.field.field_type, 'text')

    def test_manifest_owner_and_checksum_reject_wrong_scope(self):
        manifest = {'fields': [{**self.manifest['fields'][0], 'owner_user_id': 999}]}
        with self.assertRaisesRegex(ValueError, 'Manifest scope'):
            cutover.build_plan(db.session, manifest)
        plan = self.plan()
        plan['notes'][0]['values']['Meaning']['after'] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            cutover.apply_plan(db.session, plan)

    def test_new_note_after_preflight_refuses_schema_cutover(self):
        plan = self.plan()
        db.session.add(Note(user_id=self.note.user_id, note_type_id=self.note.note_type_id, field_values={'Meaning': 'new; note'}))
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'membership changed'):
            cutover.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertEqual(self.field.field_type, 'text')

    def test_previously_unchanged_note_edit_is_checked(self):
        plan = self.plan()
        self.null_note.field_values = {'Meaning': 'new; content'}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Previously unchanged note'):
            cutover.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertEqual(self.null_note.field_values['Meaning'], 'new; content')
        self.assertEqual(self.field.field_type, 'text')


if __name__ == '__main__':
    unittest.main()
