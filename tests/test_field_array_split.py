"""Converting reviewed text-like fields to native arrays: split, templates, transaction."""
import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/migrations'))
import field_array_split as split
from native_array_templates import INITIALIZER, MARKER, MARKER_V2, modernize, modernize_v2
from app import create_app
from app.services.flashcard_renderer import render_template_pair
from models import db
from models.audit_log import AuditLog
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template_publication import TemplatePublication
from models.template_version import TemplateVersion
from tests.study_note_fixtures import attach_template, create_note_user

SEPARATORS = ['br', 'newline', '$']
BACK = ('{{#Example}}<div class="ex" auto-split>{{{Example}}}</div>{{/Example}}'
        '<script>document.querySelectorAll("div[auto-split]").forEach(function(el) {'
        ' el.innerHTML = el.innerHTML.replace(/\\$/g, "<br>"); });</script>')


class SplitValueTests(TestCase):
    def test_visible_line_boundaries_only(self):
        self.assertEqual(split.split_value('a $ b<br>c\nd<BR/>e', SEPARATORS), ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(split.split_value('a;b, c', SEPARATORS), ['a;b, c'])
        self.assertEqual(split.split_value('one\\ntwo', SEPARATORS), ['one', 'two'])
        self.assertEqual(split.split_value('', SEPARATORS), [])
        self.assertEqual(split.split_value('$', SEPARATORS), ['', ''])
        self.assertEqual(split.split_value(['kept'], SEPARATORS), ['kept'])

    def test_elements_are_never_cut(self):
        self.assertEqual(split.split_value('<li><br></li>', SEPARATORS), ['<li><br></li>'])
        self.assertEqual(split.split_value('<b>x$y</b>$<i>z</i>', SEPARATORS), ['<b>x<br>y</b>', '<i>z</i>'])
        self.assertEqual(split.split_value('1 < 2$3', SEPARATORS), ['1 < 2', '3'])

    def test_semicolon_lists_keep_entities_and_money(self):
        separators = ['br', 'newline', ';']
        self.assertEqual(split.split_value('R&amp;D team; a&nbsp;b;<br>$25,000', separators),
                         ['R&amp;D team', 'a&nbsp;b', '', '$25,000'])
        self.assertEqual(split.split_value('<i>x; y</i>; z', separators), ['<i>x<br>y</i>', 'z'])

    def test_sentence_semicolon_keeps_one_sentence_together(self):
        separators = ['br', 'newline', ';sentence']
        self.assertEqual(split.split_value('The tool is reliable; moreover, it is cheap.', separators),
                         ['The tool is reliable; moreover, it is cheap.'])
        self.assertEqual(split.split_value('Phần mềm rẻ; hơn nữa, dễ cài.; Ký vào đây.', separators),
                         ['Phần mềm rẻ; hơn nữa, dễ cài.', 'Ký vào đây.'])
        with self.assertRaisesRegex(ValueError, 'one semicolon rule'):
            split.split_value('a', [';', ';sentence'])

    def test_blank_items_and_numbered_senses(self):
        self.assertEqual(split.drop_blank_items(['', 'a', '<li><br></li>', '&nbsp; ', '<img src="x">', ['']]),
                         ['a', '<img src="x">', ['']])
        self.assertEqual(split.split_numbered('① 色が薄い ② ぼんやり ③ 少し', 3), ['① 色が薄い', '② ぼんやり', '③ 少し'])
        self.assertEqual(split.split_numbered('(1) Dễ chịu. (2) Thẳng thắn, dứt khoát.', 2),
                         ['(1) Dễ chịu.', '(2) Thẳng thắn, dứt khoát.'])
        self.assertEqual(split.split_numbered('1. Năm 1999, 2. Tháng 2.5 lần', 2), ['1. Năm 1999', '2. Tháng 2.5 lần'])
        self.assertIsNone(split.split_numbered('① a ② b', 3))
        self.assertIsNone(split.split_numbered('Có 2 nghĩa: 1. a 2. b', 2))
        self.assertIsNone(split.split_numbered('<b>① a</b> ② b', 2))

    def test_unreviewed_separator_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed separators'):
            split.split_value('a,b', [','])

    def test_validator_escaping_is_the_only_accepted_change(self):
        self.assertEqual(split.clean_items(['R&D', 'a -> b'], 'Example'), ['R&amp;D', 'a -&gt; b'])
        with self.assertRaisesRegex(ValueError, 'would change'):
            split.clean_items(['<b>open'], 'Example')
        with self.assertRaisesRegex(ValueError, 'fail validation'):
            split.clean_items(['<script>x</script>'], 'Example')


class ModernizeV2Tests(TestCase):
    def test_fresh_template_keeps_item_markup_and_marks_legacy_delimiter(self):
        result = modernize_v2(BACK, {'Example': '$'})
        self.assertIn(MARKER_V2, result)
        self.assertIn('<span data-native-array-guard="Example" style="display:contents">', result)
        self.assertIn('<span data-native-array-value data-native-array-legacy="$">{{#Example}}'
                      '<span data-native-array-item>{{{.}}}</span>{{/Example}}</span>', result)
        self.assertIn('if (Array.isArray(el.__flamaArrayItems)) return;', result)
        with self.assertRaisesRegex(ValueError, 'Already authored item loop'):
            modernize_v2(result, {'Example': '$'})

    def test_v1_template_takes_more_fields_and_upgrades_its_initializer(self):
        v1 = modernize('<div>{{Reading}}</div><div auto-split>{{{Example}}}</div><script>var x;</script>', {'Reading'})
        self.assertIn(MARKER, v1)
        result = modernize_v2(v1, {'Example': '$'})
        self.assertNotIn(MARKER, result)
        self.assertEqual(result.count(MARKER_V2), 1)
        self.assertIn('{{#Reading}}<span data-native-array-item>{{.}}</span>{{/Reading}}', result)
        self.assertIn('{{#Example}}<span data-native-array-item>{{{.}}}</span>{{/Example}}', result)
        with self.assertRaisesRegex(ValueError, 'Customized v1'):
            modernize_v2(v1.replace("'use strict';", "'use strict'; var custom;"), {'Example': '$'})

    def test_attribute_and_inverted_placeholders_need_review(self):
        with self.assertRaisesRegex(ValueError, 'attribute'):
            modernize_v2('<div title="{{Example}}"></div>', {'Example': None})
        with self.assertRaisesRegex(ValueError, 'Inverted'):
            modernize_v2('{{^Example}}none{{/Example}}', {'Example': None})
        self.assertEqual(modernize_v2('<div>{{Other}}</div>', {'Example': None}), '<div>{{Other}}</div>')
        self.assertNotIn(INITIALIZER, modernize_v2('<p>{{Example}}</p>', {'Example': None}))


class FieldArraySplitTests(TestCase):
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
        self.user = user
        self.note_type = NoteType(user_id=user.id, name='Vocabulary')
        db.session.add(self.note_type)
        db.session.flush()
        self.word = FieldDef(note_type_id=self.note_type.id, name='Word', field_type='text', position=0,
                             identity_role='primary')
        self.field = FieldDef(note_type_id=self.note_type.id, name='Example', field_type='richtext', position=1)
        db.session.add_all([self.word, self.field])
        db.session.flush()
        self.note = Note(user_id=user.id, note_type_id=self.note_type.id,
                         field_values={'Word': 'w', 'Example': '<b>x$y</b>$R&D'})
        self.empty = Note(user_id=user.id, note_type_id=self.note_type.id, field_values={'Word': 'e', 'Example': ''})
        db.session.add_all([self.note, self.empty])
        self.template = attach_template(db.session, owner_user_id=user.id, note_type_id=self.note_type.id,
                                        name='Card', front_html='{{Word}}', back_html=BACK, shared_css='')
        db.session.commit()
        self.publication = TemplatePublication(template_id=self.template.id, auto_publish_enabled=True)
        db.session.add(self.publication)
        db.session.commit()
        self.manifest = {'schema_version': split.SCHEMA, 'fields': [{
            'id': self.field.id, 'note_type_id': self.note_type.id, 'name': 'Example', 'owner_user_id': user.id,
            'from_type': 'richtext', 'separators': SEPARATORS}],
            'templates': [{'id': self.template.id, 'note_type_id': self.note_type.id, 'owner_user_id': user.id,
                           'arrays': {'Example': '$'},
                           'allowed_before_hashes': [split.digest(split.template_snapshot(self.template))]}]}

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def plan(self):
        return split.build_plan(db.session, self.manifest)

    def test_apply_restore_and_render(self):
        plan = self.plan()
        self.assertEqual(plan['summary']['changed_notes'], 2)
        versions = TemplateVersion.query.count()
        split.apply_plan(db.session, plan)
        db.session.commit()
        split.verify_plan(db.session, plan)
        self.assertEqual(self.field.field_type, 'array')
        self.assertEqual(self.note.field_values['Example'], ['<b>x<br>y</b>', 'R&amp;D'])
        self.assertEqual(self.empty.field_values['Example'], [])
        self.assertIn(MARKER_V2, self.template.back_html)
        self.assertTrue(self.publication.auto_publish_enabled)
        rendered = render_template_pair(template=self.template, field_defs=list(self.note_type.field_defs),
                                        field_values=self.note.field_values)
        self.assertIn('<span data-native-array-value="" data-native-array-legacy="$">'
                      '<span data-native-array-item=""><b>x<br>y</b></span>'
                      '<span data-native-array-item="">R&amp;D</span></span>', rendered['back_html'])
        with self.assertRaisesRegex(ValueError, 'differs from the reviewed manifest'):
            self.plan()
        split.apply_plan(db.session, plan, restore=True)
        db.session.commit()
        split.verify_plan(db.session, plan, restored=True)
        self.assertEqual(self.field.field_type, 'richtext')
        self.assertEqual(self.note.field_values['Example'], '<b>x$y</b>$R&D')
        self.assertEqual(self.template.back_html, BACK)
        self.assertEqual(TemplateVersion.query.count(), versions + 2)
        self.assertEqual(AuditLog.query.filter(AuditLog.action.like('field.array_split%')).count(), 2)

    def test_injected_failure_rolls_back_everything(self):
        plan = self.plan()
        with self.assertRaisesRegex(RuntimeError, 'Injected failure'):
            split.apply_plan(db.session, plan, fail_after=1)
        db.session.rollback()
        self.assertEqual(db.session.get(FieldDef, self.field.id).field_type, 'richtext')
        self.assertEqual(db.session.get(Note, self.note.id).field_values['Example'], '<b>x$y</b>$R&D')
        self.assertEqual(AuditLog.query.count(), 0)
        self.assertTrue(self.publication.auto_publish_enabled)

    def test_stale_note_blocks_apply(self):
        plan = self.plan()
        self.note.field_values = {**self.note.field_values, 'Example': 'edited'}
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Stale/missing note'):
            split.apply_plan(db.session, plan)
        db.session.rollback()
        self.assertEqual(db.session.get(FieldDef, self.field.id).field_type, 'richtext')

    def test_scope_guards(self):
        other = create_note_user(db.session, username='learner', email='learner@example.com')
        db.session.add(other)
        db.session.flush()
        db.session.add(Note(user_id=other.id, note_type_id=self.note_type.id, field_values={'Word': 'o'}))
        db.session.commit()
        with self.assertRaisesRegex(ValueError, 'Other users hold notes'):
            self.plan()
        Note.query.filter_by(user_id=other.id).delete()
        db.session.commit()
        self.manifest['fields'][0]['from_type'] = 'image'
        with self.assertRaisesRegex(ValueError, 'Only text-like'):
            self.plan()
        self.manifest['fields'][0]['from_type'] = 'richtext'
        self.manifest['templates'][0]['arrays'] = {'Word': None}
        with self.assertRaisesRegex(ValueError, 'outside the reviewed field scope'):
            self.plan()

    def test_unconvertible_value_blocks_the_plan(self):
        self.note.field_values = {**self.note.field_values, 'Example': '<span>open$</span>x</em>'}
        db.session.commit()
        with self.assertRaises(split.PlanBlocked) as caught:
            self.plan()
        self.assertEqual(caught.exception.problems[0]['note_id'], self.note.id)

    def test_cleanup_rules_and_reviewed_repairs(self):
        self.note.field_values = {**self.note.field_values, 'Example': '$a$$b$'}
        db.session.commit()
        self.manifest['fields'][0]['drop_blank_items'] = True
        plan = self.plan()
        values = {note['id']: note['values'] for note in plan['notes']}
        self.assertEqual(values[self.note.id]['Example']['after'], ['a', 'b'])
        self.assertEqual(plan['field_stats']['Example@' + self.note_type.id]['blank_items_dropped'], 1)
        repairs = [{'note_id': self.note.id, 'field': 'Example', 'expected': ['a', 'b'],
                    'value': ['a', 'b (reviewed)'], 'reason': 'test'}]
        plan = split.build_plan(db.session, self.manifest, repairs)
        self.assertEqual(plan['summary']['reviewed_repairs'], 1)
        split.apply_plan(db.session, plan)
        db.session.commit()
        self.assertEqual(self.note.field_values['Example'], ['a', 'b (reviewed)'])
        split.apply_plan(db.session, plan, restore=True)
        db.session.commit()
        self.assertEqual(self.note.field_values['Example'], '$a$$b$')
        repairs[0]['expected'] = ['stale']
        with self.assertRaises(split.PlanBlocked) as caught:
            split.build_plan(db.session, self.manifest, repairs)
        self.assertIn('preimage differs', caught.exception.problems[0]['reason'])
        repairs[0].update({'expected': ['a', 'b'], 'value': ['<b>open']})
        with self.assertRaises(split.PlanBlocked):
            split.build_plan(db.session, self.manifest, repairs)

    def test_clone_field_type_override_needs_review(self):
        # SQLite does not enforce the install FK; only the override row matters here.
        db.session.add(DeckCloneFieldDefOverride(deck_install_id='install', source_field_def_id=self.field.id,
                                                 properties={'field_type': 'richtext'}))
        db.session.flush()
        with self.assertRaisesRegex(ValueError, 'overrides this field type'):
            self.plan()
