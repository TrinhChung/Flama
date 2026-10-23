"""Plan/apply/restore converting reviewed text-like fields to native ``array``.

The disabled field array conversion API needs the browser to split values;
this operator tool splits only on the boundaries a learner already sees as
separate lines: ``<br>``, newlines (the renderer prints both as ``<br>``) and
a delimiter the bound templates' own formatter turns into ``<br>`` (``$`` in
the Flama vocabulary templates). Items keep their safe rich-text markup.

One transaction changes field types, owner notes, clone overlay values of
those fields and the reviewed templates (upgraded with native_array_templates
v2), with stopped writers, row locks, preimage hashes and template history.
Publishing a deck release and updating installed copies is the separate
``release`` step, so clones keep their pinned content until then.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sqlalchemy as sa
from array_cutover import digest, identity, save_private, template_snapshot
from native_array_cleanup import suppress_publication_until_commit, template_application_scope
from native_array_templates import modernize_v2

SCHEMA = 'flama-field-array-split.v1'
TEXT_LIKE = ('text', 'richtext', 'markdown')
# Regex fragments. The renderer prints a newline and a literal backslash-n as
# <br> in text; the vocabulary templates' auto-split turns '$' or ';\s*' into <br>.
# ';sentence' is ';' between sentences only: before a lowercase word ("reliable;
# moreover, ...") it is punctuation inside one sentence.
_SEPARATORS = {'br': (), 'newline': (r'\n', r'\\n'), '$': (r'\$',), ';': (r';\s*',), ';sentence': (r';\s*',)}
_INVISIBLE = re.compile(r'<[^>]*>|&nbsp;|&#160;|\s', re.I)
_MEDIA = re.compile(r'<\s*(?:img|audio|video|source)\b|\[sound:', re.I)
# Inline sense numbers at the start or after a space/sentence end: ① (1) 1. 1) 1、
_SENSE_MARK = re.compile(r'(?:^|(?<=[\s。．.;；,，、]))(?:([①-⑳])|\((\d{1,2})\)|(\d{1,2})[.)．、](?!\d))')
_TAG_RE = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9-]*)\b[^<>]*?(/?)>')
_VOID_TAGS = {'area', 'br', 'col', 'embed', 'hr', 'img', 'input', 'source', 'track', 'wbr'}
_ENTITY = r'&(?:[A-Za-z][A-Za-z0-9]{1,31}|#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6});'


class PlanBlocked(ValueError):
    """Values the plan cannot convert unchanged; each needs a reviewed decision."""

    def __init__(self, problems):
        super().__init__(f'{len(problems)} values need review before conversion')
        self.problems = problems


def split_value(value, separators):
    """Visible lines of a legacy value; positions (even empty ones) are kept.

    Line breaks are what the renderer prints as ``<br>``: the tag, a newline
    and a literal backslash-n. Only separators outside any element start a
    new item, so no element is cut in two. Inside an element a text separator
    becomes the ``<br>`` the old rendering showed there, and an inner ``<br>``
    stays in its item.
    """
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        raise ValueError('Field value is neither text nor a list')
    unknown = set(separators) - set(_SEPARATORS)
    if unknown:
        raise ValueError(f'Unreviewed separators: {sorted(unknown)}')
    if {';', ';sentence'} <= set(separators):
        raise ValueError('Choose one semicolon rule')
    sentence_semicolon = ';sentence' in separators
    text = value.replace('\r\n', '\n').replace('\r', '\n')
    text_separators = [sep for name in separators for sep in _SEPARATORS[name]]
    # An entity's own ';' (&nbsp; &amp;) is text, never a separator.
    text_pattern = re.compile(_ENTITY + '|' + '|'.join(text_separators)) if text_separators else None
    items, current, depth = [], [], 0

    def add_text(chunk):
        if text_pattern is None:
            current.append(chunk)
            return
        position = 0
        for match in text_pattern.finditer(chunk):
            if match.group(0).startswith('&'):
                continue
            if sentence_semicolon and match.group(0).startswith(';') and chunk[match.end():match.end() + 1].islower():
                continue
            current.append(chunk[position:match.start()])
            position = match.end()
            if depth:
                current.append('<br>')
            else:
                items.append(''.join(current))
                current[:] = []
        current.append(chunk[position:])

    position = 0
    for match in _TAG_RE.finditer(text):
        add_text(text[position:match.start()])
        position = match.end()
        closing, name, self_closing = match.group(1), match.group(2).lower(), match.group(3)
        if name == 'br' and not depth and 'br' in separators:
            items.append(''.join(current))
            current[:] = []
            continue
        current.append(match.group(0))
        if name not in _VOID_TAGS and not self_closing:
            depth = max(depth - 1, 0) if closing else depth + 1
    add_text(text[position:])
    items.append(''.join(current))
    return [item.strip() for item in items]


def clean_items(items, field_name):
    """Items exactly as note writes would store them, or a review error.

    The only accepted change is the validator escaping a bare ``&``/``<``/``>``
    as an entity: the item still renders the same text.
    """
    import html
    from types import SimpleNamespace
    from app.validators.flashcard_input import RequestValidationError, clean_array_fields
    try:
        cleaned = clean_array_fields({field_name: items}, [SimpleNamespace(name=field_name, field_type='array')])[field_name]
    except RequestValidationError as exc:
        raise ValueError(f'Items fail validation: {exc}') from exc
    changed = [(item, clean) for item, clean in zip(items, cleaned) if item != clean]
    if len(cleaned) != len(items) or any(html.unescape(item) != html.unescape(clean) for item, clean in changed):
        raise ValueError('Item would change on validation; review separately', changed[:3])
    return cleaned


def drop_blank_items(items):
    """Items that show something: no stray separator positions or empty markup."""
    return [item for item in items if not isinstance(item, str) or _MEDIA.search(item)
            or _INVISIBLE.sub('', item)]


def split_numbered(item, count):
    """``item`` split before each inline sense number when it holds exactly 1..count.

    None unless the plain item starts with sense 1 and numbers ``count`` senses
    in order, so ordinary digits never split a sentence.
    """
    if not isinstance(item, str) or '<' in item:
        return None
    marks = list(_SENSE_MARK.finditer(item))
    numbers = [ord(m.group(1)) - ord('①') + 1 if m.group(1) else int(m.group(2) or m.group(3)) for m in marks]
    if numbers != list(range(1, count + 1)) or marks[0].start() != 0:
        return None
    starts = [m.start() for m in marks] + [len(item)]
    parts = [item[starts[i]:starts[i + 1]].strip().rstrip(',，;；、').strip() for i in range(count)]
    return parts if all(parts) else None


def _field_entries(manifest):
    return {entry['id']: entry for entry in manifest['fields']}


def _check_field(session, field, entry, *, expected_type):
    from models.note_type import NoteType
    if (field is None or field.note_type_id != entry['note_type_id'] or field.name != entry['name']
            or session.get(NoteType, field.note_type_id).user_id != entry['owner_user_id']
            or field.field_type != expected_type or field.identity_role == 'primary'):
        raise ValueError(f'Field differs from the reviewed manifest: {entry["id"]}')


def _validate_template_contexts(scope, arrays, reviewed_field_ids):
    """Every active attachment must bind each converted input to a reviewed field."""
    for application in scope:
        if application['status_code'] != 'ACTIVE':
            continue
        by_name = {field['name']: field for field in application['field_defs']}
        by_id = {field['id']: field for field in application['field_defs']}
        bindings = application['input_bindings']
        for name in arrays:
            if bindings is not None and name in bindings:
                if bindings[name] is None:
                    continue
                field = by_id.get(bindings[name])
            else:
                field = by_name.get(name)
            if field is None or field['id'] not in reviewed_field_ids:
                raise ValueError('Template array input is outside the reviewed field scope: ' + application['id'])


def _clean_repair_value(field, value):
    """A reviewed repair value, unchanged by the validator for its field type."""
    from app.validators.flashcard_input import sanitize_plain_text, sanitize_rich_text
    if isinstance(value, list):
        return clean_items(value, field.name)
    if not isinstance(value, str):
        raise ValueError('Repair value must be text or a list')
    clean = {'richtext': sanitize_rich_text, 'text': sanitize_plain_text}.get(field.field_type)
    if clean is None or clean(value, field_name=field.name) != value:
        raise ValueError('Repair value would change on validation; review separately')
    return value


def build_plan(session, manifest, repairs=None):
    """``repairs``: private reviewed edits [{note_id, field, expected, value, reason}],
    applied after the split; ``expected`` is the value the split produces (or
    the stored value of a field outside the manifest)."""
    from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
    from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
    from models.field_def import FieldDef
    from models.note import Note
    from models.template import Template
    if manifest.get('schema_version') != SCHEMA:
        raise ValueError('Unsupported manifest')
    for key in ('fields', 'templates'):
        ids = [entry['id'] for entry in manifest.get(key, [])]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate manifest IDs: ' + key)
    plan = {'schema_version': SCHEMA, 'identity': identity(session), 'manifest': manifest,
            'fields': [], 'notes': [], 'overrides': [], 'templates': [], 'note_counts': {}, 'review': {}}
    entries = _field_entries(manifest)
    by_type = defaultdict(list)
    for field_id, entry in entries.items():
        if entry.get('from_type') not in TEXT_LIKE:
            raise ValueError(f'Only text-like fields convert to array: {field_id}')
        field = session.get(FieldDef, field_id)
        _check_field(session, field, entry, expected_type=entry['from_type'])
        typed = session.execute(sa.select(DeckCloneFieldDefOverride).where(
            DeckCloneFieldDefOverride.source_field_def_id == field_id)).scalars().all()
        if any(isinstance(row.properties, dict) and 'field_type' in row.properties for row in typed):
            raise ValueError(f'An installed copy overrides this field type; review first: {field_id}')
        by_type[field.note_type_id].append(field)
        plan['fields'].append({'id': field_id, 'before': entry['from_type'], 'after': 'array'})
    stats = {entry['name'] + '@' + entry['note_type_id']: Counter() for entry in entries.values()}
    problems = []
    repairs_by_note = defaultdict(list)
    for repair in repairs or []:
        repairs_by_note[repair['note_id']].append(repair)
    plan['repairs'] = [{key: repair[key] for key in ('note_id', 'field', 'reason')} for repair in repairs or []]
    seen_repairs = set()
    for type_id, fields in sorted(by_type.items()):
        owner = entries[fields[0].id]['owner_user_id']
        notes = session.execute(sa.select(Note).where(Note.note_type_id == type_id).order_by(Note.id)).scalars().all()
        if any(note.user_id != owner for note in notes):
            raise ValueError(f'Other users hold notes of this note type; review first: {type_id}')
        plan['note_counts'][type_id] = len(notes)
        type_fields = {field.name: field for field in fields[0].note_type.field_defs}
        for note in notes:
            before = dict(note.field_values or {})
            after = dict(before)
            for field in fields:
                if field.name not in before:
                    continue
                entry = entries[field.id]
                counter = stats[field.name + '@' + type_id]
                try:
                    items = split_value(before[field.name], entry['separators'])
                    cleaned = clean_items(items, field.name)
                except ValueError as exc:
                    problems.append({'note_id': note.id, 'field': field.name, 'reason': exc.args[0],
                                     'value': before[field.name], 'changed_items': exc.args[1] if len(exc.args) > 1 else None})
                    continue
                if cleaned != items:
                    counter['entity_escaped'] += 1
                if entry.get('drop_blank_items'):
                    kept = drop_blank_items(cleaned)
                    if kept != cleaned:
                        counter['blank_items_dropped'] += 1
                    cleaned = kept
                after[field.name] = cleaned
            for left, right in manifest.get('split_numbered_pairs', []):
                a, b = after.get(left), after.get(right)
                if not isinstance(a, list) or not isinstance(b, list):
                    continue
                for name, single, other in ((left, a, b), (right, b, a)):
                    if len(single) == 1 and len(other) > 1:
                        parts = split_numbered(single[0], len(other))
                        if parts:
                            after[name] = clean_items(parts, name)
                            stats[name + '@' + type_id]['numbered_split'] += 1
            for repair in repairs_by_note.get(note.id, []):
                field = type_fields.get(repair['field'])
                current = after.get(repair['field'])
                if field is None or repair['field'] not in after or current != repair['expected']:
                    problems.append({'note_id': note.id, 'field': repair['field'],
                                     'reason': 'Repair preimage differs; review again', 'value': current})
                    continue
                try:
                    after[repair['field']] = _clean_repair_value(field, repair['value'])
                except ValueError as exc:
                    problems.append({'note_id': note.id, 'field': repair['field'], 'reason': exc.args[0],
                                     'value': repair['value']})
                    continue
                seen_repairs.add((note.id, repair['field']))
            for field in fields:
                if isinstance(after.get(field.name), list):
                    counter = stats[field.name + '@' + type_id]
                    counter['items_%d' % len(after[field.name])] += 1
                    if any(item == '' for item in after[field.name]):
                        counter['with_empty_item'] += 1
            if before != after:
                plan['notes'].append({'id': note.id, 'owner_user_id': note.user_id, 'note_type_id': type_id,
                    'before_hash': digest(before), 'after_hash': digest(after),
                    'values': {key: {'before': before.get(key), 'after': after[key]}
                               for key in after if before.get(key) != after[key]}})
    for left, right in manifest.get('pairs', []):
        mismatched = []
        for note in plan['notes']:
            values = note['values']
            if left in values and right in values:
                a, b = values[left]['after'], values[right]['after']
                if a and b and len(a) != len(b):
                    mismatched.append(note['id'])
        plan['review'][f'{left}/{right} item counts differ'] = mismatched
    overrides = session.execute(sa.select(DeckCloneNoteFieldOverride).where(
        DeckCloneNoteFieldOverride.source_field_def_id.in_(list(entries))).order_by(DeckCloneNoteFieldOverride.id)).scalars().all()
    for row in overrides:
        if not isinstance(row.value, str):
            continue
        entry = entries[row.source_field_def_id]
        after = clean_items(split_value(row.value, entry['separators']), entry['name'])
        plan['overrides'].append({'id': row.id, 'deck_install_id': row.deck_install_id,
                                  'before': row.value, 'after': after})
    reviewed_ids = set(entries)
    for entry in manifest['templates']:
        template = session.get(Template, entry['id'])
        if template is None or template.owner_user_id != entry['owner_user_id']:
            raise ValueError(f'Template scope mismatch: {entry["id"]}')
        scope = template_application_scope(session, template, entry['note_type_id'])
        _validate_template_contexts(scope, entry['arrays'], reviewed_ids)
        before = template_snapshot(template)
        after = {**before, **{key: modernize_v2(before[key], entry['arrays']) for key in ('front_html', 'back_html')}}
        if digest(before) not in entry['allowed_before_hashes']:
            raise ValueError(f'Template differs from reviewed content: {template.id}')
        if before != after:
            plan['templates'].append({'id': template.id, 'owner_user_id': template.owner_user_id,
                                     'note_type_id': entry['note_type_id'], 'application_scope': scope,
                                     'before': before, 'after': after})
    reported = {(problem['note_id'], problem['field']) for problem in problems}
    problems.extend({'note_id': repair['note_id'], 'field': repair['field'],
                     'reason': 'Repair note is outside the plan scope', 'value': None}
                    for repair in repairs or []
                    if (repair['note_id'], repair['field']) not in seen_repairs | reported)
    if problems:
        raise PlanBlocked(problems)
    plan['field_stats'] = {key: dict(sorted(counter.items())) for key, counter in stats.items()}
    plan['summary'] = {'fields': len(plan['fields']), 'scanned_notes': sum(plan['note_counts'].values()),
                       'changed_notes': len(plan['notes']), 'clone_overrides': len(plan['overrides']),
                       'updated_templates': len(plan['templates']), 'schema_changes': 0,
                       'reviewed_repairs': len(plan['repairs']),
                       'review_notes': sum(len(ids) for ids in plan['review'].values())}
    plan['checksum'] = digest(plan)
    return plan


def validate_plan(plan):
    if plan.get('schema_version') != SCHEMA or digest({key: value for key, value in plan.items() if key != 'checksum'}) != plan['checksum']:
        raise ValueError('Unsupported or tampered plan')


def verify_plan(session, plan, *, restored=False):
    from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
    from models.field_def import FieldDef
    from models.note import Note
    from models.template import Template
    validate_plan(plan)
    if identity(session) != plan['identity']:
        raise ValueError('Unexpected database identity')
    target = 'before' if restored else 'after'
    entries = _field_entries(plan['manifest'])
    for change in plan['fields']:
        _check_field(session, session.get(FieldDef, change['id']), entries[change['id']], expected_type=change[target])
    for entry in plan['notes']:
        note = session.get(Note, entry['id'])
        if (note is None or note.user_id != entry['owner_user_id'] or note.note_type_id != entry['note_type_id']
                or digest(dict(note.field_values or {})) != entry[target + '_hash']):
            raise ValueError(f'Verification failed for note: {entry["id"]}')
    for entry in plan['overrides']:
        row = session.get(DeckCloneNoteFieldOverride, entry['id'])
        if row is None or row.value != entry[target]:
            raise ValueError(f'Verification failed for clone override: {entry["id"]}')
    for entry in plan['templates']:
        template = session.get(Template, entry['id'])
        if template is None or template.owner_user_id != entry['owner_user_id'] or template_snapshot(template) != entry[target]:
            raise ValueError(f'Verification failed for template: {entry["id"]}')


def _scope_with_field_types(scope, field_types):
    """The preflight attachment scope with converted fields in a given state."""
    return [{**application, 'field_defs': [
        {**field, 'field_type': field_types.get(field['id'], field['field_type'])}
        for field in application['field_defs']]} for application in scope]


def apply_plan(session, plan, *, restore=False, fail_after=None):
    from app.services import deck_working_tree_service, template_version_service
    from models.audit_log import AuditLog
    from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
    from models.field_def import FieldDef
    from models.note import Note
    from models.template import Template
    validate_plan(plan)
    if identity(session) != plan['identity']:
        raise ValueError('Unexpected database identity')
    session = session() if callable(session) else session
    source, target = ('after', 'before') if restore else ('before', 'after')
    entries = _field_entries(plan['manifest'])
    locked_fields = []
    for change in plan['fields']:
        field = session.execute(sa.select(FieldDef).where(FieldDef.id == change['id']).with_for_update()).scalar_one_or_none()
        _check_field(session, field, entries[change['id']], expected_type=change[source])
        locked_fields.append((change, field))
    for type_id, count in plan['note_counts'].items():
        if session.execute(sa.select(sa.func.count()).select_from(Note).where(Note.note_type_id == type_id)).scalar_one() != count:
            raise ValueError('Note membership changed after preflight')
    locked_notes = []
    for entry in plan['notes']:
        note = session.execute(sa.select(Note).where(Note.id == entry['id']).with_for_update()).scalar_one_or_none()
        if (note is None or note.user_id != entry['owner_user_id'] or note.note_type_id != entry['note_type_id']
                or digest(dict(note.field_values or {})) != entry[source + '_hash']):
            raise ValueError(f'Stale/missing note: {entry["id"]}')
        locked_notes.append((entry, note))
    locked_overrides = []
    for entry in plan['overrides']:
        row = session.execute(sa.select(DeckCloneNoteFieldOverride).where(
            DeckCloneNoteFieldOverride.id == entry['id']).with_for_update()).scalar_one_or_none()
        if row is None or row.value != entry[source]:
            raise ValueError(f'Stale/missing clone override: {entry["id"]}')
        locked_overrides.append((entry, row))
    locked_templates = []
    for entry in plan['templates']:
        template = session.execute(sa.select(Template).where(Template.id == entry['id']).with_for_update()).scalar_one_or_none()
        if template is None or template.owner_user_id != entry['owner_user_id'] or template_snapshot(template) != entry[source]:
            raise ValueError(f'Stale/missing template: {entry["id"]}')
        expected_scope = _scope_with_field_types(entry['application_scope'],
                                                 {change['id']: change[source] for change in plan['fields']})
        if template_application_scope(session, template, entry['note_type_id'], lock=True) != expected_scope:
            raise ValueError(f'Template attachment scope changed after preflight: {template.id}')
        locked_templates.append((entry, template))
    suppress_publication_until_commit(session)
    for change, field in locked_fields:
        field.field_type = change[target]
    session.flush()
    for change, field in locked_fields:
        deck_working_tree_service.mark_field_def_changed(
            field_def=field, owner_user_id=entries[change['id']]['owner_user_id'], property_keys={'field_type'})
    mutations = []
    for index, (entry, note) in enumerate(locked_notes, 1):
        values = dict(note.field_values or {})
        for key, change in entry['values'].items():
            values[key] = change[target]
        if digest(values) != entry[target + '_hash']:
            raise ValueError('Post-image mismatch')
        note.field_values = values
        mutations.append({'note': note, 'field_names': list(entry['values']), 'operation': 'set'})
        if fail_after is not None and index >= fail_after:
            session.flush()
            raise RuntimeError('Injected failure before commit')
    if mutations:
        deck_working_tree_service.mark_note_field_batches_changed(mutations=mutations)
    for entry, row in locked_overrides:
        row.value = entry[target]
    for entry, template in locked_templates:
        for key, value in entry[target].items():
            setattr(template, key, value)
        template_version_service.mark_template_version(template, origin='restore' if restore else 'edit',
            actor_user_id=template.owner_user_id,
            change_note='Native array field split restore' if restore else 'Native array field split')
    session.add(AuditLog(action='field.array_split.restore' if restore else 'field.array_split',
                         payload={'plan_checksum': plan['checksum'], 'summary': plan['summary']}))
    session.flush()


def release_and_update(session, manifest, *, update_installs):
    """Publish one release per affected deck item, then update installed copies.

    ``update_installs``: ``none``; ``at_head`` (copies already on the newest
    release, so only this change reaches them); ``all`` (every copy, which
    also brings them earlier releases they had not applied).
    """
    from app.services import deck_install_rebase_service, deck_release_service
    from app.services.release_core import next_auto_version
    from models.deck_install import DeckInstall
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.deck_release import DeckRelease
    note_type_ids = sorted({entry['note_type_id'] for entry in manifest['fields']})
    items = session.execute(sa.select(DeckMarketplaceItem).where(
        DeckMarketplaceItem.source_note_type_id.in_(note_type_ids)).order_by(DeckMarketplaceItem.id)).scalars().all()
    receipt = {'releases': [], 'updates': [], 'skipped_updates': []}
    for item in items:
        if item.publish_status != 'published':
            continue
        head = session.get(DeckRelease, item.current_release_id) if item.current_release_id else None
        result = deck_release_service.publish_release_and_commit(
            deck_item_id=item.id, user_id=item.owner_user_id,
            version_label=next_auto_version(head.version_label if head else None),
            changelog='Native array fields: example, meaning and usage items are stored as lists.',
            expected_current_release_id=item.current_release_id,
            expected_working_revision=item.working_revision,
            idempotency_key=f'array-split:{manifest.get("label", "v1")}:{item.id}'[:64])
        release = result.release
        receipt['releases'].append({'deck_item_id': item.id, 'from_release_id': head.id if head else None,
                                    'release_id': release.id, 'version_label': release.version_label,
                                    'replayed': result.replayed})
        if update_installs == 'none':
            continue
        installs = session.execute(sa.select(DeckInstall).where(DeckInstall.deck_item_id == item.id)
                                   .order_by(DeckInstall.id)).scalars().all()
        for install in installs:
            at_head = head is not None and install.applied_release_id == head.id
            if install.version_mode != 'release' or (update_installs == 'at_head' and not at_head):
                receipt['skipped_updates'].append({'install_id': install.id, 'version_mode': install.version_mode,
                                                   'applied_release_id': install.applied_release_id})
                continue
            rebase = deck_install_rebase_service.prepare_and_apply_update_and_commit(
                install_id=install.id, release_id=release.id, user_id=install.user_id,
                expected_applied_release_id=install.applied_release_id,
                idempotency_key=f'array-split:{release.id}'[:64])
            receipt['updates'].append({'install_id': install.id, 'user_id': install.user_id,
                                       'rebase_id': rebase.id, 'status': rebase.status,
                                       'changes': rebase.applied_change_count})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan', 'apply', 'restore', 'verify', 'release'])
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--repairs', type=Path, help='Private reviewed note repairs (never committed)')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--expect-database', required=True)
    parser.add_argument('--expect-server', required=True)
    parser.add_argument('--writers-stopped', action='store_true')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--restored', action='store_true', help='Verify original values after restore')
    parser.add_argument('--update-installs', choices=['none', 'at_head', 'all'], default='none')
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    with app.app_context():
        try:
            if identity(db.session) != {'database_name': args.expect_database, 'server': args.expect_server}:
                raise ValueError('Unexpected database target')
            if args.mode == 'plan':
                db.session.rollback()
                db.session.execute(sa.text('SET TRANSACTION READ ONLY'))
                db.session.execute(sa.text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
                try:
                    repairs = json.loads(args.repairs.read_text(encoding='utf-8')) if args.repairs else None
                    plan = build_plan(db.session, json.loads(args.manifest.read_text(encoding='utf-8')), repairs)
                except PlanBlocked as exc:
                    save_private(args.plan.with_name(args.plan.name + '.blocked.json'), exc.problems)
                    raise
                save_private(args.plan, plan)
                db.session.rollback()
                print(json.dumps({'checksum': plan['checksum'], 'summary': plan['summary'],
                                  'field_stats': plan['field_stats'],
                                  'review': {key: len(ids) for key, ids in plan['review'].items()}}, ensure_ascii=False))
                return
            if args.mode == 'verify':
                plan = json.loads(args.plan.read_text(encoding='utf-8'))
                db.session.rollback()
                db.session.execute(sa.text('SET TRANSACTION READ ONLY'))
                db.session.execute(sa.text('START TRANSACTION WITH CONSISTENT SNAPSHOT'))
                verify_plan(db.session, plan, restored=args.restored)
                db.session.rollback()
                print(json.dumps({'verified': 'before' if args.restored else 'after', 'checksum': plan['checksum']}))
                return
            if not args.writers_stopped or not args.receipt or args.receipt.exists():
                raise ValueError('Writes require stopped writers and a new receipt path')
            if args.mode == 'release':
                manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
                save_private(args.receipt.with_name(args.receipt.name + '.intent'),
                             {'mode': 'release', 'update_installs': args.update_installs})
                receipt = release_and_update(db.session, manifest, update_installs=args.update_installs)
                save_private(args.receipt, receipt)
                print(json.dumps({'releases': len(receipt['releases']), 'updates': len(receipt['updates']),
                                  'skipped_updates': len(receipt['skipped_updates'])}))
                return
            plan = json.loads(args.plan.read_text(encoding='utf-8'))
            validate_plan(plan)
            save_private(args.receipt.with_name(args.receipt.name + '.intent'),
                         {'mode': args.mode, 'identity': plan['identity'], 'checksum': plan['checksum']})
            apply_plan(db.session, plan, restore=args.mode == 'restore')
            db.session.commit()
            save_private(args.receipt, {'mode': args.mode, 'identity': plan['identity'],
                                       'checksum': plan['checksum'], 'summary': plan['summary']})
            print(json.dumps({'mode': args.mode, 'checksum': plan['checksum'], 'summary': plan['summary']}))
        except Exception:
            db.session.rollback()
            raise


if __name__ == '__main__':
    main()
