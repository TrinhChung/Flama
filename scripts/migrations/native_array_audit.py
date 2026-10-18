"""Read-only before/after evidence for native_array_cleanup; no private text output."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sqlalchemy as sa
from array_cutover import digest, identity, save_private
from native_array_cleanup import validate_plan, verify_plan

SCHEMA = 'flama-native-array-audit.v1'
WRITTEN = {'notes', 'templates', 'template_versions', 'deck_marketplace_items',
           'deck_working_dirty_entities', 'audit_logs'}


def row_hash(row):
    return hashlib.sha256(json.dumps(dict(row), ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def snapshot(session):
    from models.note import Note

    inspector = sa.inspect(session.get_bind())
    state = {'schema_version': SCHEMA, 'identity': identity(session), 'tables': {},
             'notes': {}, 'note_metadata': {}, 'old_versions': {}, 'template_settings': {}}
    for table in inspector.get_table_names():
        pk = inspector.get_pk_constraint(table)['constrained_columns']
        order = ','.join('`'+key+'`' for key in pk)
        query = sa.text('SELECT * FROM `'+table+'`'+(' ORDER BY '+order if order else ''))
        if table in WRITTEN and table not in ('notes', 'templates', 'template_versions', 'deck_marketplace_items'):
            continue
        hasher = hashlib.sha256(); count = 0
        for row in session.execute(query).mappings():
            count += 1
            if table == 'notes':
                note = None if 'field_values' in row else session.get(Note, row['id'])
                values = row['field_values'] if note is None else note.field_values
                state['notes'][row['id']] = digest(json.loads(values) if isinstance(values, str) else values)
                excluded = {'field_values', 'updated_at'}
                if note is not None:
                    excluded.update(('field_values_by_id', 'field_values_extras', 'content_revision'))
                metadata = {k:v for k,v in row.items() if k not in excluded}
                if note is not None:
                    # Removed definitions retain tombstones outside the named
                    # adapter; cleanup must preserve those values too.
                    from app.services.field_value_runtime_service import canonical_field_schema_for_note
                    schema = canonical_field_schema_for_note(note)
                    metadata['retired_values'] = {key:value for key,value in (note.field_values_by_id or {}).items()
                                                  if key not in schema.ids}
                state['note_metadata'][row['id']] = row_hash(metadata)
            elif table == 'template_versions':
                state['old_versions'][row['id']] = row_hash(row)
            elif table == 'templates':
                state['template_settings'][row['id']] = row_hash({k:v for k,v in row.items()
                    if k not in ('front_html','back_html','current_version_id','updated_at')})
            elif table == 'deck_marketplace_items':
                hasher.update(row_hash({k:v for k,v in row.items()
                    if k not in ('working_revision','dirty_tracking_revision','updated_at')}).encode())
            else:
                hasher.update(row_hash(row).encode())
        if table not in ('notes', 'templates', 'template_versions'):
            state['tables'][table] = {'count': count, 'sha256': hasher.hexdigest()}
    state['checksum'] = digest(state)
    return state


def compare(before, after, plan, *, restored=False):
    validate_plan(plan)
    if before.get('schema_version') != SCHEMA or digest({k:v for k,v in before.items() if k != 'checksum'}) != before['checksum']:
        raise ValueError('Unsupported or tampered audit snapshot')
    if before['identity'] != after['identity'] or before['identity'] != plan['identity']:
        raise ValueError('Audit identity mismatch')
    for key in ('tables', 'note_metadata', 'template_settings'):
        if before[key] != after[key]:
            raise ValueError('Protected data changed: '+key)
    if not all(after['old_versions'].get(key) == value for key,value in before['old_versions'].items()):
        raise ValueError('Historical template version changed')
    expected = dict(before['notes'])
    for entry in plan['notes']:
        if expected.get(entry['id']) != entry['before_hash']:
            raise ValueError('Audit snapshot differs from plan preimage')
        expected[entry['id']] = entry['before_hash' if restored else 'after_hash']
    if after['notes'] != expected:
        raise ValueError('Unexpected note changes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['snapshot', 'verify'])
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--restored', action='store_true')
    parser.add_argument('--expect-database', required=True)
    parser.add_argument('--expect-server', required=True)
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    with app.app_context():
        try:
            db.session.execute(sa.text('SET TRANSACTION READ ONLY'))
            db.session.execute(sa.text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
            if identity(db.session) != {'database_name':args.expect_database, 'server':args.expect_server}:
                raise ValueError('Unexpected database target')
            after = snapshot(db.session)
            if args.mode == 'snapshot':
                save_private(args.snapshot, after)
            else:
                if not args.plan:
                    raise ValueError('Audit verify requires the applied plan')
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                compare(json.loads(args.snapshot.read_text(encoding='utf-8')), after, plan, restored=args.restored)
                verify_plan(db.session, plan, restored=args.restored)
            print(json.dumps({'verified':args.mode == 'verify', 'identity':after['identity'],
                'tables':len(after['tables']), 'notes':len(after['notes']), 'checksum':after['checksum']}))
        finally:
            db.session.rollback()


if __name__ == '__main__':
    main()
