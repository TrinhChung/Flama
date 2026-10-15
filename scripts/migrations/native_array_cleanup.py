"""Plan/apply/restore native array templates and explicitly reviewed note repairs.

No schema changes or historical rewrites. Private plans use stable IDs, full
before/after hashes, stopped writers and one transaction with version/journal
tracking. The default plan only backfills current array strings and templates;
content repairs require a separately reviewed manifest and --include-repairs.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sqlalchemy as sa
from array_cutover import digest, identity, save_private, template_snapshot
from native_array_templates import modernize

SCHEMA = 'flama-native-array-cleanup.v1'


def template_application_scope(session, template, note_type_id, *, lock=False):
    """Read explicit attachment/render scope; no Template origin is inferred."""
    from models.field_def import FieldDef
    from models.study_application import StudyApplication

    query = sa.select(StudyApplication).where(
        StudyApplication.template_id == template.id).order_by(StudyApplication.id)
    applications = session.execute(query.with_for_update() if lock else query).scalars().all()
    if not any(application.note_type_id == note_type_id for application in applications):
        raise ValueError(f'Template scope mismatch: {template.id}')
    type_ids = {application.note_type_id for application in applications}
    fields_query = sa.select(FieldDef).where(FieldDef.note_type_id.in_(type_ids)).order_by(FieldDef.id)
    fields = session.execute(fields_query.with_for_update() if lock else fields_query).scalars().all()
    by_type = defaultdict(list)
    for field in fields:
        by_type[field.note_type_id].append({
            'id': field.id, 'name': field.name, 'field_type': field.field_type,
        })
    return [{
        'id': application.id, 'note_type_id': application.note_type_id,
        'occurrence_key': application.occurrence_key,
        'status_code': application.status_code, 'input_bindings': application.input_bindings,
        'field_defs': by_type[application.note_type_id],
    } for application in applications]


def verify_template_scope(session, template, entry, *, lock=False):
    scope = template_application_scope(session, template, entry['note_type_id'], lock=lock)
    if 'application_scope' in entry and scope != entry['application_scope']:
        raise ValueError(f'Template attachment scope changed after preflight: {template.id}')
    return scope


def validate_reviewed_array_contexts(scope, array_names, reviewed_field_ids):
    """Every active use affected by a definition edit needs reviewed array fields."""
    for application in scope:
        if application['status_code'] != 'ACTIVE':
            continue
        by_name = {field['name']: field for field in application['field_defs']}
        by_id = {field['id']: field for field in application['field_defs']}
        bindings = application['input_bindings']
        for name in array_names:
            if bindings is not None and name in bindings:
                if bindings[name] is None:
                    continue
                field = by_id.get(bindings[name])
            else:
                field = by_name.get(name)
            if field is None or field['field_type'] != 'array' or field['id'] not in reviewed_field_ids:
                raise ValueError('Template array context is outside the reviewed field scope: ' + application['id'])


def array_value(value):
    """Existing arrays retain structure/order; strings split only on line breaks."""
    from app.validators.flashcard_input import clean_array_fields
    from types import SimpleNamespace
    if value is None:
        return None
    if not isinstance(value, (str, list)):
        raise ValueError('Array field is neither a list nor legacy text')
    # Editors discard blank lines; a migration must retain positional gaps and
    # avoid silently sanitizing existing stored content.
    candidate = (value.replace('\r\n', '\n').replace('\r', '\n').split('\n') if value else []) if isinstance(value, str) else value
    cleaned = clean_array_fields({'value': candidate}, [SimpleNamespace(name='value', field_type='array')])['value']
    if cleaned != candidate:
        raise ValueError('Stored value would change on validation; review separately')
    return cleaned


def build_plan(session, manifest, *, include_repairs=False):
    from models.field_def import FieldDef
    from models.note import Note
    from models.note_type import NoteType
    from models.template import Template
    if manifest.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported manifest')
    for key in ('fields', 'templates', 'repairs'):
        ids = [entry['id'] for entry in manifest.get(key, [])]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate manifest IDs: '+key)
    plan = {'schema_version': SCHEMA, 'identity': identity(session), 'manifest': manifest,
            'notes': [], 'templates': [], 'note_counts': {}, 'absent_optional': [],
            'unresolved': manifest.get('unresolved', []), 'include_repairs': include_repairs}
    by_type = defaultdict(list)
    for entry in manifest['fields']:
        field = session.get(FieldDef, entry['id'])
        if field is None and entry.get('optional'):
            plan['absent_optional'].append(entry['id'])
            continue
        if (field is None or field.note_type_id != entry['note_type_id'] or field.name != entry['name']
                or session.get(NoteType, field.note_type_id).user_id != entry['owner_user_id']
                or field.field_type != 'array'):
            raise ValueError(f'Field scope/type differs from reviewed manifest: {entry["id"]}')
        by_type[field.note_type_id].append(field)
    repairs = {entry['id']: entry for entry in manifest.get('repairs', [])} if include_repairs else {}
    if include_repairs and (not repairs or not set(repairs).issubset(manifest.get('repair_scope_ids', []))):
        raise ValueError('Repairs require a reviewed private manifest within explicit note IDs')
    seen_repairs = set()
    for type_id, fields in by_type.items():
        notes = session.execute(sa.select(Note).where(Note.note_type_id == type_id).order_by(Note.id)).scalars().all()
        plan['note_counts'][type_id] = len(notes)
        for note in notes:
            before = dict(note.field_values or {})
            after = dict(before)
            for field in fields:
                if field.name in after:
                    after[field.name] = array_value(after[field.name])
            repair = repairs.get(note.id)
            if repair:
                if note.user_id != repair['owner_user_id'] or note.note_type_id != repair['note_type_id']:
                    raise ValueError('Repair owner/scope mismatch')
                expected = repair['expected']
                desired = repair['values']
                if all(before.get(key) == value for key, value in desired.items()):
                    seen_repairs.add(note.id)
                elif all(key in after and after[key] == value for key, value in expected.items()):
                    # A repair may only touch declared fields and their valid value types.
                    defs = {field.name: field for field in session.get(NoteType, type_id).field_defs}
                    from app.validators.flashcard_input import clean_note_field_values
                    clean_note_field_values(note_type=session.get(NoteType, type_id), raw_field_values=desired,
                                            partial=True, current_values=before)
                    if any(key not in defs for key in desired):
                        raise ValueError('Unknown repair field')
                    after.update(desired)
                    seen_repairs.add(note.id)
                else:
                    raise ValueError(f'Repair preimage differs; review again: {note.id}')
            if before != after:
                plan['notes'].append({'id': note.id, 'owner_user_id': note.user_id, 'note_type_id': type_id,
                    'before_hash': digest(before), 'after_hash': digest(after),
                    'values': {key: {'before': before[key], 'after': after[key]}
                               for key in before if before[key] != after[key]}})
    if seen_repairs != set(repairs):
        raise ValueError('Repair note missing from field scope')
    for entry in manifest['templates']:
        template = session.get(Template, entry['id'])
        if template is None and entry.get('optional'):
            plan['absent_optional'].append(entry['id'])
            continue
        if (template is None or template.owner_user_id != entry['owner_user_id']
                ):
            raise ValueError(f'Template scope mismatch: {entry["id"]}')
        application_scope = verify_template_scope(session, template, entry)
        validate_reviewed_array_contexts(application_scope, entry['array_names'],
            {field.id for fields in by_type.values() for field in fields})
        before = template_snapshot(template)
        after = {**before, **{key: modernize(before[key], set(entry['array_names']))
                             for key in ('front_html', 'back_html')}}
        if before != after:
            if digest(before) not in entry['allowed_before_hashes']:
                raise ValueError(f'Template differs from reviewed content: {template.id}')
            plan['templates'].append({'id': template.id, 'owner_user_id': template.owner_user_id,
                                     'note_type_id': entry['note_type_id'],
                                     'application_scope': application_scope, 'before': before, 'after': after})
    plan['summary'] = {'scanned_notes': sum(plan['note_counts'].values()), 'changed_notes': len(plan['notes']),
                       'updated_templates': len(plan['templates']), 'schema_changes': 0,
                       'reviewed_repairs': len(repairs), 'unresolved_notes': len(plan['unresolved']),
                       'absent_optional': len(plan['absent_optional'])}
    plan['checksum'] = digest(plan)
    return plan


def validate_plan(plan):
    if plan.get('schema_version') != SCHEMA or digest({key: value for key, value in plan.items() if key != 'checksum'}) != plan['checksum']:
        raise ValueError('Unsupported or tampered plan')


def verify_plan(session, plan, *, restored=False):
    """Verify every planned postimage without changing the database."""
    from models.note import Note
    from models.template import Template
    validate_plan(plan)
    if identity(session) != plan['identity']:
        raise ValueError('Unexpected database identity')
    target = 'before' if restored else 'after'
    for entry in plan['notes']:
        note = session.get(Note, entry['id'])
        if (note is None or note.user_id != entry['owner_user_id']
                or note.note_type_id != entry['note_type_id']
                or digest(dict(note.field_values or {})) != entry[target+'_hash']):
            raise ValueError(f'Verification failed for note: {entry["id"]}')
    for entry in plan['templates']:
        template = session.get(Template, entry['id'])
        if (template is None or template.owner_user_id != entry['owner_user_id']
                or template_snapshot(template) != entry[target]):
            raise ValueError(f'Verification failed for template: {entry["id"]}')
        verify_template_scope(session, template, entry)


def suppress_publication_until_commit(session):
    """Class history/journal hooks run before this session's final settings restore.

    Flags stay disabled during all publication hooks, then original settings are
    restored in the same transaction. Rollback discards everything. No global
    event, app setting or historical release is changed.
    """
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.template_publication import TemplatePublication
    flags = []
    for model in (DeckMarketplaceItem, TemplatePublication):
        for row in session.execute(sa.select(model).with_for_update()).scalars():
            # Deck journals legitimately advance updated_at; publication-only
            # settings retain theirs when the temporary flag is restored.
            flags.append((row, row.auto_publish_enabled,
                          row.updated_at if isinstance(row, TemplatePublication) else None))
            row.auto_publish_enabled = False
    session.flush()
    state = {'pending': True}
    def restore_settings(writer):
        if state['pending']:
            for row, enabled, updated_at in flags:
                row.auto_publish_enabled = enabled
                if updated_at is not None:
                    row.updated_at = updated_at
            writer.flush()
            state['pending'] = False
    sa.event.listen(session, 'before_commit', restore_settings)
    def discard_settings(writer):
        state['pending'] = False
    sa.event.listen(session, 'after_rollback', discard_settings)


def apply_plan(session, plan, *, restore=False, fail_after=None):
    from app.services import deck_working_tree_service, template_version_service
    from models.audit_log import AuditLog
    from models.field_def import FieldDef
    from models.note import Note
    from models.note_type import NoteType
    from models.template import Template
    validate_plan(plan)
    if identity(session) != plan['identity']:
        raise ValueError('Unexpected database identity')
    # db.session is a scoped proxy; event listeners require its actual Session.
    session = session() if callable(session) else session
    for entry in plan['manifest']['fields']:
        field = session.execute(sa.select(FieldDef).where(FieldDef.id == entry['id']).with_for_update()).scalar_one_or_none()
        if field is None and entry.get('optional') and entry['id'] in plan['absent_optional']:
            continue
        if (field is None or field.name != entry['name'] or field.note_type_id != entry['note_type_id']
                or field.field_type != 'array'
                or session.get(NoteType, field.note_type_id).user_id != entry['owner_user_id']):
            raise ValueError('Field changed after preflight')
    for type_id, count in plan['note_counts'].items():
        if session.execute(sa.select(sa.func.count()).select_from(Note).where(Note.note_type_id == type_id)).scalar_one() != count:
            raise ValueError('Note membership changed after preflight')
    source, target = ('after', 'before') if restore else ('before', 'after')
    # Validate all mutations before any write; row locks protect the preimages.
    locked_notes = []
    for entry in plan['notes']:
        note = session.execute(sa.select(Note).where(Note.id == entry['id']).with_for_update()).scalar_one_or_none()
        if (note is None or note.user_id != entry['owner_user_id'] or note.note_type_id != entry['note_type_id']
                or digest(dict(note.field_values or {})) != entry[source+'_hash']):
            raise ValueError(f'Stale/missing note: {entry["id"]}')
        locked_notes.append((entry, note))
    locked_templates = []
    for entry in plan['templates']:
        template = session.execute(sa.select(Template).where(Template.id == entry['id']).with_for_update()).scalar_one_or_none()
        if (template is None or template.owner_user_id != entry['owner_user_id']
                or template_snapshot(template) != entry[source]):
            raise ValueError(f'Stale/missing template: {entry["id"]}')
        scope = verify_template_scope(session, template, entry, lock=True)
        manifest_entry = next(item for item in plan['manifest']['templates'] if item['id'] == entry['id'])
        validate_reviewed_array_contexts(scope, manifest_entry['array_names'],
            {field['id'] for field in plan['manifest']['fields'] if field['id'] not in plan['absent_optional']})
        locked_templates.append((entry, template))
    suppress_publication_until_commit(session)
    mutations = []
    for index, (entry, note) in enumerate(locked_notes, 1):
        values = dict(note.field_values or {})
        for key, change in entry['values'].items():
            values[key] = change[target]
        if digest(values) != entry[target+'_hash']:
            raise ValueError('Post-image mismatch')
        note.field_values = values
        mutations.append({'note': note, 'field_names': list(entry['values']), 'operation': 'set'})
        if fail_after is not None and index >= fail_after:
            session.flush()
            raise RuntimeError('Injected failure before commit')
    deck_working_tree_service.mark_note_field_batches_changed(mutations=mutations)
    for entry, template in locked_templates:
        for key, value in entry[target].items():
            setattr(template, key, value)
        template_version_service.mark_template_version(template, origin='restore' if restore else 'edit',
            actor_user_id=template.owner_user_id, change_note='Native array cleanup restore' if restore else 'Native array template and data compatibility')
    session.add(AuditLog(action='field.native_array_cleanup.restore' if restore else 'field.native_array_cleanup',
                         payload={'plan_checksum': plan['checksum'], 'summary': plan['summary']}))
    session.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan', 'apply', 'restore', 'verify'])
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('native_array_manifest_20261011.json'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--expect-database', required=True)
    parser.add_argument('--expect-server', required=True)
    parser.add_argument('--include-repairs', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--restored', action='store_true', help='Verify original values after restore')
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    with app.app_context():
        try:
            if identity(db.session) != {'database_name': args.expect_database, 'server': args.expect_server}:
                raise ValueError('Unexpected database target')
            if args.mode == 'plan':
                # End the identity read, then force the entire planning snapshot read-only.
                db.session.rollback()
                db.session.execute(sa.text('SET TRANSACTION READ ONLY'))
                db.session.execute(sa.text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
                plan = build_plan(db.session, json.loads(args.manifest.read_text(encoding='utf-8')),
                                  include_repairs=args.include_repairs)
                save_private(args.plan, plan)
                db.session.rollback()
            elif args.mode == 'verify':
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                db.session.rollback()
                db.session.execute(sa.text('SET TRANSACTION READ ONLY'))
                db.session.execute(sa.text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
                verify_plan(db.session, plan, restored=args.restored)
                db.session.rollback()
            else:
                if not args.writers_stopped or not args.receipt or args.receipt.exists():
                    raise ValueError('Apply/restore requires stopped writers and a new receipt path')
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                validate_plan(plan)
                # Prove the receipt directory is writable before any mutation.
                # If the process dies after commit, this intent plus verify/audit
                # distinguishes a committed operation from a clean rollback.
                save_private(args.receipt.with_name(args.receipt.name+'.intent'),
                             {'mode':args.mode, 'identity':plan['identity'], 'checksum':plan['checksum']})
                apply_plan(db.session, plan, restore=args.mode == 'restore')
                db.session.commit()
                save_private(args.receipt, {'mode': args.mode, 'identity': plan['identity'],
                                           'checksum': plan['checksum'], 'summary': plan['summary']})
            print(json.dumps({'identity': plan['identity'], 'checksum': plan['checksum'], 'summary': plan['summary']}))
        except Exception:
            db.session.rollback()
            raise


if __name__ == '__main__':
    main()
