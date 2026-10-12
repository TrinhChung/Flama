"""The deployed template57 transformation remains independent of live models."""
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from migrations import template_modernization_20261012 as frozen


class FrozenTemplateModernizationTests(unittest.TestCase):
    def test_helpers_preserve_media_array_and_unicode_contract(self):
        fields = [SimpleNamespace(name='Image', field_type='image'),
                  SimpleNamespace(name='意味', field_type='richtext'),
                  SimpleNamespace(name='Words', field_type='array')]
        source = '<img src="{{Image}}"> {{Image}} {{意味}} {{#Words}}{{.}}{{/Words}}'
        front = frozen._upgrade_html_field_double_brace_tokens(
            frozen._rewrite_media_url_attribute_tokens(source, fields), fields)
        self.assertEqual(front, '<img src="{{Image_url}}"> {{{Image}}} {{{意味}}} {{#Words}}{{.}}{{/Words}}')
        self.assertEqual(frozen.infer_input_schema(front, '{{FrontSide}}', fields), [
            {'key':'Image','label':'Image','type':'image','required':False},
            {'key':'意味','label':'意味','type':'richtext','required':False},
            {'key':'Words','label':'Words','type':'text','required':False}])
        with self.assertRaises(frozen.TemplateLibraryError):
            frozen.infer_input_schema('{{=<% %>=}}', '', fields)
        self.assertEqual(len(frozen.template_content_hash(front, None, None)), 64)

    def test_deployed_revision_rewrites_versions_and_fills_only_missing_bindings(self):
        module = importlib.import_module('migrations.versions.20261012_000057_modernize_flashcard_templates')
        engine = sa.create_engine('sqlite:///:memory:')
        metadata = sa.MetaData()
        tables = {}
        specs = {
            'field_defs': ('id','note_type_id','name','field_type','required','position'),
            'templates': ('id','note_type_id','front_html','back_html','shared_css','input_schema'),
            'template_versions': ('id','template_id','front_html','back_html','shared_css','input_schema','content_hash'),
            'study_applications': ('id','template_id','note_type_id','input_bindings'),
        }
        for name,columns in specs.items():
            tables[name] = sa.Table(name, metadata, *[sa.Column(c,sa.Text,primary_key=c=='id') for c in columns])
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(tables['field_defs'].insert(), {'id':'field','note_type_id':'nt','name':'Image','field_type':'image','required':'0','position':'0'})
            connection.execute(tables['templates'].insert(), {'id':'template','note_type_id':'nt','front_html':'<img src="{{Image}}">','back_html':'{{Image}}','input_schema':'[]'})
            connection.execute(tables['template_versions'].insert(), {'id':'version','template_id':'template','front_html':'<img src="{{Image}}">','back_html':'{{Image}}','input_schema':'[]','content_hash':'old'})
            connection.execute(tables['study_applications'].insert(), [{'id':'app','template_id':'template','note_type_id':'nt','input_bindings':'{}'},
                {'id':'bound','template_id':'template','note_type_id':'nt','input_bindings':'{"Image":"explicit"}'}])
            with patch.object(module, 'op', Operations(MigrationContext.configure(connection))):
                module.upgrade()
                first = {name:connection.execute(table.select().order_by(table.c.id)).all() for name,table in tables.items()}
                module.upgrade()
                second = {name:connection.execute(table.select().order_by(table.c.id)).all() for name,table in tables.items()}
            self.assertEqual(first,second)
            template = connection.execute(tables['templates'].select()).mappings().one()
            version = connection.execute(tables['template_versions'].select()).mappings().one()
            self.assertEqual(template['front_html'],'<img src="{{Image_url}}">')
            self.assertEqual(version['content_hash'],frozen.template_content_hash(template['front_html'],'{{{Image}}}',''))
            bindings = dict(connection.execute(sa.select(tables['study_applications'].c.id,tables['study_applications'].c.input_bindings)).all())
            self.assertEqual(bindings, {'app':'{"Image": "field"}','bound':'{"Image":"explicit"}'})
        engine.dispose()

    def test_historical_helpers_never_import_live_application_or_models(self):
        import ast
        path = Path(frozen.__file__)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node,ast.ImportFrom):
                self.assertFalse((node.module or '').startswith(('app','models')))
        for name in ('bench_p6_migration_mysql.py','probe_p6_application_schema_mysql.py'):
            self.assertFalse((path.parents[1]/'scripts'/name).exists())


if __name__ == '__main__':
    unittest.main()
