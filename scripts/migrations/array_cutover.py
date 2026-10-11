#!/usr/bin/env python3
"""Plan/apply/restore the reviewed array cutover, with no startup repairs.

Plans contain private before/after values: keep outside git, mode 0600.
Apply requires stopped writers and an explicit database identity. Content,
schema, template history and marketplace journal writes commit together.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sqlalchemy as sa
from array_parsers import (split_reading, split_translation_vi,
    split_meaning_en4everyone, split_nghia_kanji_n3, split_paired_list)

PARSERS = {'reading': split_reading, 'translation_vi': split_translation_vi,
           'meaning': split_meaning_en4everyone, 'kanji_meaning': split_nghia_kanji_n3,
           'paired': split_paired_list}
CONTENT = ('front_html', 'back_html', 'shared_css', 'input_schema')
PAIRS = [('Collocation', 'Coollocation_VI'), ('Synonym', 'Synonym_VI'), ('Antonym', 'Antonym_VI')]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


def identity(session):
    if session.get_bind().dialect.name == 'mysql':
        return dict(session.execute(sa.text('SELECT DATABASE() AS database_name, @@hostname AS server')).mappings().one())
    return {'database_name': 'sqlite', 'server': 'test'}


def fields_for_manifest(session, manifest, *, lock=False):
    from models.field_def import FieldDef
    from models.note_type import NoteType
    fields = []
    for entry in manifest['fields']:
        query = sa.select(FieldDef).where(FieldDef.id == entry['id'])
        field = session.execute(query.with_for_update() if lock else query).scalar_one()
        owner = session.get(NoteType, field.note_type_id)
        if (field.note_type_id != entry['note_type_id'] or field.name != entry['name']
            or owner.user_id != entry['owner_user_id'] or field.identity_role == 'primary'
            or field.field_type not in ('text', 'richtext', 'markdown', 'array')):
            raise ValueError(f"Manifest scope/type mismatch: {entry['id']}")
        fields.append((entry, field))
    return fields


def converted_values(values, entries):
    """Preserve missing/null keys, non-target values, order and repeated items."""
    from app.validators.field_array_conversion import array_value_problem
    result = dict(values)
    for entry, field in entries:
        name = field.name
        if name not in values or values[name] is None:
            continue
        raw = values[name]
        if not isinstance(raw, str):
            raise ValueError(f'Non-string legacy value: {name}')
        if '[sound:' in raw.lower():
            raise ValueError(f'Media reference in array scope: {name}')
        value = raw if field.field_type == 'array' else '\n'.join(PARSERS[entry['parser']](raw))
        problem = array_value_problem(value)
        if problem:
            raise ValueError(f'Invalid result for {name}: {problem}')
        result[name] = value
    return result


def template_snapshot(template):
    return {key: getattr(template, key) for key in CONTENT}


def desired_back(entry, current, replacement):
    """Keep the two independently customized copies' original layout/media."""
    if entry.get('variant') == 'english-copy':
        return replacement.replace('  {{image}}\n', '  <div class="img-wrap">{{image}}</div>\n', 1)
    if entry.get('variant') == 'default-copy':
        if 'Only legacy prose fields still use $.' in current:
            return current
        result = current.replace("font-family: \"Arial\"; display: flex'>", "font-family: \"Arial\";'>", 1)
        result = result.replace("color: green; display: flex; padding-bottom: 10px' auto-split", "color: green; padding-bottom: 10px'", 1)
        start = result.rindex('(function() {')
        end = result.index('</script>', start)
        helper_start = replacement.rindex('(function() {')
        helper_end = replacement.index('</script>', helper_start)
        return result[:start] + replacement[helper_start:helper_end].replace('.flama-vocab-card', '.card-wrapper').replace("'flama-vocab-card'", "'card-wrapper'") + result[end:]
    return replacement


def build_plan(session, manifest):
    from models.note import Note
    from models.template import Template
    entries = fields_for_manifest(session, manifest)
    by_type = defaultdict(list)
    plan = {'schema_version': 'flama-array-cutover.v1', 'identity': identity(session),
            'created_at': datetime.now(timezone.utc).isoformat(), 'manifest': manifest,
            'fields': [], 'notes': [], 'unchanged_notes': [], 'templates': [], 'library': []}
    for entry, field in entries:
        by_type[field.note_type_id].append((entry, field))
        if field.field_type != 'array':
            plan['fields'].append({'id': field.id, 'before': field.field_type, 'after': 'array'})
    counts, mismatches = {}, Counter()
    mismatch_ids = set()
    duplicate_values = 0
    for type_id, scoped in by_type.items():
        notes = session.execute(sa.select(Note).where(Note.note_type_id == type_id).order_by(Note.id)).scalars().all()
        counts[type_id] = len(notes)
        for note in notes:
            before = dict(note.field_values or {})
            after = converted_values(before, scoped)
            for left, right in PAIRS:
                if left in after and right in after:
                    lengths = [len(after[name].split('\n')) if after[name] else 0 for name in (left, right)]
                    if lengths[0] != lengths[1]:
                        mismatches[left] += 1
                        mismatch_ids.add(note.id)
            for entry, field in scoped:
                value = after.get(field.name)
                items = value.lower().split('\n') if isinstance(value, str) and value else []
                duplicate_values += int(len(set(items)) < len(items))
            if before != after:
                plan['notes'].append({'id': note.id, 'note_type_id': type_id,
                    'before_hash': digest(before), 'after_hash': digest(after),
                    'values': {name: {'before': before[name], 'after': after[name]}
                               for name in before if before[name] != after[name]}})
            else:
                plan['unchanged_notes'].append({'id': note.id, 'hash': digest(before)})
    for entry in manifest.get('templates', []):
        template = session.get(Template, entry['id'])
        if template is None:
            raise ValueError(f"Missing template: {entry['id']}")
        folder = ROOT / 'note-type-templates' / entry['slug']
        prototype = json.loads((folder / 'prototype.json').read_text(encoding='utf-8'))
        back = desired_back(entry, template.back_html, (folder / 'back.html').read_text(encoding='utf-8'))
        if template.back_html == back:
            continue
        expected = entry.get('expected_back_sha256', prototype['source']['sha256']['back.html'])
        if hashlib.sha256(template.back_html.encode()).hexdigest() != expected:
            raise ValueError(f"Template differs from reviewed dump: {template.id}")
        before = template_snapshot(template)
        plan['templates'].append({'id': template.id, 'owner_user_id': template.owner_user_id,
                                 'before': before, 'after': {**before, 'back_html': back}})
    for slug in manifest.get('library_slugs', []):
        folder = ROOT / 'note-type-templates' / slug
        prototype = json.loads((folder / 'prototype.json').read_text(encoding='utf-8'))
        definition = prototype['template']
        template_id = prototype['database_installation']['template_id']
        from app.validators.template_library import validate_input_schema
        content = dict(front_html=(folder/'front.html').read_text(encoding='utf-8'),
                       back_html=(folder/'back.html').read_text(encoding='utf-8'),
                       shared_css=(folder/'style.css').read_text(encoding='utf-8'),
                       input_schema=validate_input_schema(definition['input_schema']))
        existing = session.get(Template, template_id)
        if existing:
            if existing.owner_user_id != manifest['library_owner_user_id']:
                raise ValueError('Library template owner mismatch')
            if template_snapshot(existing) != content:
                raise ValueError('Existing library template differs; review separately')
        else:
            plan['library'].append({'id': template_id, 'owner_user_id': manifest['library_owner_user_id'],
                'name': definition['name'], 'description': definition.get('description', ''), 'content': content})
    plan['summary'] = {'notes_by_type': counts, 'scanned_notes': sum(counts.values()),
        'changed_notes': len(plan['notes']), 'changed_fields': len(plan['fields']),
        'updated_templates': len(plan['templates']), 'new_library_templates': len(plan['library']),
        'pair_mismatches': dict(mismatches), 'unique_mismatched_notes': len(mismatch_ids),
        'repeated_field_values': duplicate_values}
    return plan


def validate_plan(plan):
    if plan.get('schema_version') != 'flama-array-cutover.v1':
        raise ValueError('Unsupported plan')
    if digest({key: value for key, value in plan.items() if key != 'checksum'}) != plan['checksum']:
        raise ValueError('Plan checksum mismatch')


def apply_plan(session, plan, *, restore=False, fail_after=None):
    """Caller owns commit/rollback. Locks and hashes reject stale/concurrent edits."""
    from app.services import deck_working_tree_service, template_version_service
    from models.audit_log import AuditLog
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.field_rename_job import FieldRenameJob
    from models.note import Note
    from models.template import Template
    validate_plan(plan)
    if identity(session) != plan['identity']:
        raise ValueError('Database identity differs from the plan')
    scoped = fields_for_manifest(session, plan['manifest'], lock=True)
    field_map = {field.id: field for entry, field in scoped}
    if session.execute(sa.select(FieldRenameJob.id).where(
        FieldRenameJob.note_type_id.in_({field.note_type_id for field in field_map.values()}),
        FieldRenameJob.status.notin_(['completed', 'failed']))).first():
        raise ValueError('Field rename in progress')
    source_key, target_key = ('after', 'before') if restore else ('before', 'after')
    for type_id, expected_count in plan['summary']['notes_by_type'].items():
        count = session.execute(sa.select(sa.func.count()).select_from(Note).where(Note.note_type_id == type_id)).scalar_one()
        if count != expected_count:
            raise ValueError('Note membership changed after preflight')
    for offset in range(0, len(plan['unchanged_notes']), 1000):
        batch = plan['unchanged_notes'][offset:offset+1000]
        rows = session.execute(sa.select(Note).where(Note.id.in_([row['id'] for row in batch])).with_for_update()).scalars().all()
        hashes = {note.id: digest(dict(note.field_values or {})) for note in rows}
        if any(hashes.get(row['id']) != row['hash'] for row in batch):
            raise ValueError('Previously unchanged note changed after preflight')
    # Track atoms without auto-publishing partial content during the bulk cutover.
    listings = session.execute(sa.select(DeckMarketplaceItem).with_for_update()).scalars().all()
    publish_flags = [(item, item.auto_publish_enabled) for item in listings]
    for item, enabled in publish_flags:
        item.auto_publish_enabled = False
    try:
        for entry in plan['fields']:
            field = field_map[entry['id']]
            if field.field_type != entry[source_key]:
                raise ValueError(f"Stale field: {field.id}")
            field.field_type = entry[target_key]
            manifest_entry = next(row for row in plan['manifest']['fields'] if row['id'] == field.id)
            deck_working_tree_service.mark_field_def_changed(field_def=field,
                owner_user_id=manifest_entry['owner_user_id'], property_keys={'field_type'})
        for offset in range(0, len(plan['notes']), 1000):
            batch = plan['notes'][offset:offset+1000]
            rows = session.execute(sa.select(Note).where(Note.id.in_([row['id'] for row in batch])).order_by(Note.id).with_for_update()).scalars().all()
            by_id = {note.id: note for note in rows}
            mutations = []
            for row in batch:
                note = by_id.get(row['id'])
                if not note or note.note_type_id != row['note_type_id'] or digest(dict(note.field_values or {})) != row[source_key+'_hash']:
                    raise ValueError(f"Stale/missing note: {row['id']}")
                values = dict(note.field_values or {})
                for name, change in row['values'].items():
                    values[name] = change[target_key]
                if digest(values) != row[target_key+'_hash']:
                    raise ValueError('Post-image mismatch')
                note.field_values = values
                mutations.append({'note': note, 'field_names': list(row['values']), 'operation': 'set'})
            deck_working_tree_service.mark_note_field_batches_changed(mutations=mutations)
            session.flush()
            if fail_after is not None and offset + len(batch) >= fail_after:
                raise RuntimeError('Injected failure before commit')
        for row in plan['templates']:
            template = session.execute(sa.select(Template).where(Template.id == row['id']).with_for_update()).scalar_one()
            if template.owner_user_id != row['owner_user_id'] or template_snapshot(template) != row[source_key]:
                raise ValueError('Stale template')
            for key, value in row[target_key].items():
                setattr(template, key, value)
            template_version_service.mark_template_version(template, origin='edit', actor_user_id=template.owner_user_id,
                change_note='Array cutover restore' if restore else 'Read native array items in the template')
        for row in plan['library']:
            if restore:
                template = session.get(Template, row['id'])
                if not template or template_snapshot(template) != row['content']:
                    raise ValueError('Library template changed after cutover')
                template.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
            else:
                if session.get(Template, row['id']):
                    raise ValueError('Library template appeared after preflight')
                template = Template(id=row['id'], owner_user_id=row['owner_user_id'], name=row['name'],
                    description=row['description'], origin='authored', **row['content'])
                session.add(template)
                template_version_service.mark_template_version(template, origin='create', actor_user_id=row['owner_user_id'], change_note='Install reviewed typing templates')
        session.add(AuditLog(user_id=plan['manifest'].get('library_owner_user_id'),
            action='field.array_cutover.restore' if restore else 'field.array_cutover',
            payload={'plan_checksum': plan['checksum'], 'summary': plan['summary']}))
        session.flush()
    finally:
        for item, enabled in publish_flags:
            item.auto_publish_enabled = enabled
    # Template edits also enqueue a before_commit auto-publish. Keep the journal
    # revisions/atoms, but leave release publication and subscriber rebase explicit.
    session.info.pop(deck_working_tree_service._PRESENTATION_ITEMS, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan', 'apply', 'restore'])
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('array_manifest_20261011.json'))
    parser.add_argument('--expect-database', required=True)
    parser.add_argument('--expect-server', required=True)
    parser.add_argument('--writers-stopped', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    assert not app.config['STARTUP_RUN_MAINTENANCE']
    with app.app_context():
        actual = identity(db.session)
        if actual != {'database_name': args.expect_database, 'server': args.expect_server}:
            raise ValueError('Unexpected database target')
        try:
            if args.mode == 'plan':
                plan = build_plan(db.session, json.loads(args.manifest.read_text(encoding='utf-8')))
                plan['checksum'] = digest(plan)
                save_private(args.plan, plan)
                db.session.rollback()
            else:
                if not args.writers_stopped or not args.receipt:
                    raise ValueError('Apply/restore needs --writers-stopped and --receipt')
                if args.receipt.exists():
                    raise ValueError('Receipt already exists')
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                apply_plan(db.session, plan, restore=args.mode == 'restore')
                db.session.commit()
                save_private(args.receipt, {'mode': args.mode, 'identity': actual,
                    'plan_checksum': plan['checksum'], 'summary': plan['summary']})
            print(json.dumps({'identity': actual, 'checksum': plan['checksum'], 'summary': plan['summary']}, ensure_ascii=False))
        except Exception:
            db.session.rollback()
            raise


if __name__ == '__main__':
    main()
