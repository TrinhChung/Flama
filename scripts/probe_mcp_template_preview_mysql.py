"""Guarded local-MySQL integration probe; owns disposable fixture rows only.

Run with --stage-browser to keep the owned fixture for a real Study browser
check, then --cleanup. Never runs DDL, migration, schema repair or create_all.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['STARTUP_RUN_MAINTENANCE'] = 'false'
os.environ['STARTUP_CHECK_DB_CONNECTIVITY'] = 'false'

from sqlalchemy import event
from app import create_app
from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User
from app.services import flashcard_content_service, template_library_service
from app.services.mcp_tool_registry import call_mcp_tool
from tests.study_note_fixtures import create_note_user

FOLDER = ROOT / 'output/playwright/mcp-study-smoke'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-browser', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    app = create_app({'WTF_CSRF_ENABLED': False, 'STARTUP_RUN_MAINTENANCE': False,
                      'STARTUP_RUN_DB_CREATE_ALL': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False})
    with app.app_context():
        assert db.engine.dialect.name == 'mysql', 'This probe requires MySQL.'
        assert db.engine.url.host in {'localhost', '127.0.0.1', '::1'}, 'Local DB required.'
        if args.cleanup:
            fixture = json.loads((FOLDER / 'fixture.json').read_text(encoding='utf-8'))
            cleanup(fixture)
            return
        fixture = {'username': f'mcp-preview-smoke-{secrets.token_hex(6)}'}
        try:
            recipe = json.loads((ROOT / 'app/services/mcp/recipes/quiz.json').read_text(encoding='utf-8'))
            user = create_note_user(db.session, username=fixture['username'], email=fixture['username'] + '@example.invalid')
            user.set_password(secrets.token_urlsafe(24))
            db.session.commit()
            fixture['user_id'] = user.id
            client = app.test_client()
            with client.session_transaction() as session:
                session['_user_id'] = str(user.id)
                session['_fresh'] = True

            def post(url, payload, statuses=(201,)):
                response = client.post(url, json=payload)
                assert response.status_code in statuses, (url, response.status_code, response.get_json())
                return response.get_json()

            template = post('/api/card-templates', {'name': 'MCP Quiz Smoke', **{
                key: recipe[key] for key in ('front_html', 'back_html', 'shared_css', 'input_schema')}})
            fixture['template_id'] = template['id']
            note_type = post('/api/note-types', {'name': 'MCP Quiz Smoke', 'field_defs': [
                {'name': item['key'], 'field_type': item['type'], 'required': item.get('required', False)}
                for item in recipe['input_schema']]})
            fixture['note_type_id'] = note_type['id']
            bindings = {field['name']: field['id'] for field in note_type['field_defs']}
            first = post(f"/api/note-types/{note_type['id']}/template-applications", {
                'template_id': template['id'], 'occurrence_key': 'smoke-first', 'is_default': True,
                'input_bindings': bindings}, (200, 201))
            # The web attachment flow deliberately deduplicates definitions.
            # Stage an imported-style second occurrence explicitly to exercise
            # preview's occurrence selector without changing that web policy.
            second_row = StudyApplication(note_type_id=note_type['id'], template_id=template['id'],
                occurrence_key='smoke-second', status_code='ACTIVE', is_default=False,
                input_bindings={**bindings, 'question': bindings['explanation']}, position=1)
            db.session.add(second_row)
            db.session.commit()
            second = {'id': second_row.id}
            fixture['application_id'] = first['id']
            fixture['second_application_id'] = second['id']
            deck = Deck(name='MCP Quiz Smoke', owner_user_id=user.id, note_type_id=note_type['id'])
            db.session.add(deck)
            db.session.commit()
            fixture['deck_id'] = deck.id
            note = post('/api/notes', {'note_type_id': note_type['id'], 'deck_id': deck.id,
                'field_values': recipe['sample_values']})
            fixture['note_id'] = note['id']
            snapshot = lambda: {'notes': Note.query.filter_by(user_id=user.id).count(),
                'templates': Template.query.filter_by(owner_user_id=user.id).count(),
                'versions': TemplateVersion.query.filter_by(template_id=template['id']).count()}
            before = snapshot()
            statements = []
            def reject_mutation(_conn, _cursor, statement, _params, _context, _executemany):
                statements.append(statement.split(None, 1)[0].upper())
                assert statement.lstrip().split(None, 1)[0].upper() not in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER', 'DROP'}, 'Preview attempted mutation.'
            event.listen(db.engine, 'before_cursor_execute', reject_mutation)
            try:
                raw = call_mcp_tool(tool_name='preview_note_type_template', user_id=user.id, arguments=recipe)
                assert not raw.get('isError'), raw
                attached = call_mcp_tool(tool_name='preview_note_type_template', user_id=user.id, arguments={
                    'note_type_id': note_type['id'], 'application_id': first['id'], 'sample_values': recipe['sample_values'], 'profile': 'quiz'})
                alternate = call_mcp_tool(tool_name='preview_note_type_template', user_id=user.id, arguments={
                    'note_type_id': note_type['id'], 'application_id': second['id'], 'sample_values': recipe['sample_values'], 'profile': 'quiz'})
                assert not attached.get('isError'), attached
                assert not alternate.get('isError'), alternate
                a, b = attached['structuredContent'], alternate['structuredContent']
                assert a['preview']['content_artifact']['render_context']['question'] != b['preview']['content_artifact']['render_context']['question']
                assert a['candidate_hash'] != b['candidate_hash']
                assert a['checks']['interaction'] == 'not_run'
                for invalid_arguments in ({'note_type_id': note_type['id'], 'template_id': template['id'], 'sample_values': recipe['sample_values']},
                    {'note_type_id': note_type['id'], 'application_id': 'wrong-occurrence', 'sample_values': recipe['sample_values']}):
                    try:
                        call_mcp_tool(tool_name='preview_note_type_template', user_id=user.id, arguments=invalid_arguments)
                    except Exception as error:
                        assert getattr(error, 'code', None) in {'INVALID_PARAMS', 'APPLICATION_NOT_FOUND'}, str(error)
                    else:
                        raise AssertionError('Invalid occurrence unexpectedly accepted.')
                try:
                    call_mcp_tool(tool_name='preview_note_type_template', user_id=-1, arguments={
                        'note_type_id': note_type['id'], 'application_id': first['id'], 'sample_values': recipe['sample_values']})
                except Exception as error:
                    assert getattr(error, 'status', None) in {403, 404}, str(error)
                else:
                    raise AssertionError('Foreign NoteType preview unexpectedly accepted.')
            finally:
                event.remove(db.engine, 'before_cursor_execute', reject_mutation)
            assert snapshot() == before
            report = {'database': 'local MySQL', 'read_only_preview': 'passed', 'occurrence_binding': 'passed',
                'ownership': 'passed', 'ambiguous_target_rejected': 'passed', 'before': before,
                'after': snapshot(), 'sql_statement_kinds': sorted(set(statements)), 'candidate_hash': a['candidate_hash']}
            FOLDER.mkdir(parents=True, exist_ok=True)
            (FOLDER / 'mysql-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
            if args.stage_browser:
                cookie = client.get_cookie(app.config.get('SESSION_COOKIE_NAME', 'session'))
                assert cookie
                (FOLDER / 'state.json').write_text(json.dumps({'cookies': [{'name': cookie.key, 'value': cookie.value,
                    'domain': '127.0.0.1', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}], 'origins': []}), encoding='utf-8')
                (FOLDER / 'fixture.json').write_text(json.dumps(fixture), encoding='utf-8')
                print(f"Study fixture ready: /study?deck_id={deck.id}")
            else:
                cleanup(fixture)
        except Exception:
            db.session.rollback()
            if fixture.get('user_id'):
                cleanup(fixture)
            raise


def cleanup(fixture):
    user = db.session.get(User, fixture['user_id'])
    assert user and user.username == fixture['username'] and user.username.startswith('mcp-preview-smoke-')
    assert user.email == fixture['username'] + '@example.invalid'
    for note in Note.query.filter_by(user_id=user.id).all():
        flashcard_content_service.delete_note(user_id=user.id, note_id=note.id)
    for note_type in NoteType.query.filter_by(user_id=user.id).all():
        flashcard_content_service.delete_note_type(user_id=user.id, note_type_id=note_type.id)
    for template in Template.query.filter_by(owner_user_id=user.id).all():
        template_library_service.delete_template(user_id=user.id, template_id=template.id)
    for deck in Deck.query.filter_by(owner_user_id=user.id).all():
        db.session.delete(deck)
    db.session.flush()
    db.session.delete(user)
    db.session.commit()
    (FOLDER / 'state.json').unlink(missing_ok=True)
    print('Removed the exact disposable fixture user and its owned content; session state deleted.')


if __name__ == '__main__':
    main()
