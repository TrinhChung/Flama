"""Browse list/deck-scope statement bounds for owned and logical-overlay decks."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import event, insert

from app import create_app
from app.repositories import vocabulary_repository
from app.services import browse_card_service
from app.services.anki_scheduler import CardState
from app.services.study_note_card_projection import NoteCardBurial, project_note_state
from app.services.study_progress_contract import ALGORITHM_KEY, ALGORITHM_VERSION, STORAGE_CODEC
from app.services.study_progress_shadow_codec import serialize_card_state
from models import db
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from tests.study_note_fixtures import attach_template


NOW = datetime(2026, 10, 12, 1, 30)
FIELD_NAMES = ("Word", "Reading", "Meaning")


def make_app():
    return create_app({
        'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'REDIS_URL': '', 'DECK_COUNT_WRITE_ENABLED': False,
        'REVIEW_ANALYTICS_WRITE_ENABLED': False, 'STUDY_NOTE_COUNT_ENABLED': False,
        'STARTUP_RUN_MAINTENANCE': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False,
        'WTF_CSRF_ENABLED': False,
    })


def seed_learner(username='bounds-learner'):
    """A NOTE learner plus the system storage profile; returns the user id."""
    user = User(username=username, email=f'{username}@example.test')
    db.session.add(user)
    db.session.flush()
    db.session.add(StudyAuthorityEnrollment(learner_user_id=user.id, mode_code='NOTE', epoch=1,
                                            created_at=NOW, updated_at=NOW))
    if db.session.get(StudyAuthorityStorageProfile, 1) is None:
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code='CONSOLIDATED_V1', epoch=3,
                                                    switched_at=NOW, created_at=NOW, updated_at=NOW))
    db.session.commit()
    return user.id


def _note_type(owner_id, name):
    note_type = NoteType(name=name, user_id=owner_id)
    db.session.add(note_type)
    db.session.flush()
    fields = [FieldDef(note_type_id=note_type.id, name=name_, field_type='text', position=index)
              for index, name_ in enumerate(FIELD_NAMES)]
    db.session.add_all(fields)
    attach_template(db.session, note_type_id=note_type.id, owner_user_id=owner_id,
                    name='Front', front_html='{{Word}}', back_html='{{Reading}}')
    db.session.flush()
    return note_type, {field.name: field.id for field in fields}


def _note_rows(*, prefix, owner_id, note_type_id, field_ids, deck_ids, count):
    return [{
        'id': f'{prefix}-0000-0000-0000-{index:012d}', 'user_id': owner_id,
        'note_type_id': note_type_id, 'deck_id': deck_ids[index % len(deck_ids)],
        'field_values_by_id': {field_ids['Word']: f'w{index:06d}', field_ids['Reading']: f'r{index:06d}',
                               field_ids['Meaning']: f'm{index:06d}'},
        'field_values_codec': 'field-id.v1', 'field_values_extras': {}, 'content_revision': 0,
        'tags': [], 'created_at': NOW - timedelta(days=2), 'updated_at': NOW,
    } for index in range(1, count + 1)]


def _stage_review_subjects(learner_id, note_ids):
    document = serialize_card_state(CardState(type='review', stepIndex=0, due=NOW, dueDay=1,
        intervalDays=1, ease=2.5, reps=1, lapses=0, lastReviewAt=None))
    projection = project_note_state(document.payload, burial=NoteCardBurial())
    states = [{
        'learner_user_id': learner_id, 'logical_note_key': note_id.encode(),
        'live_note_id': note_id, 'status_code': 'MIRRORED_SINGLE',
        'algorithm_key': ALGORITHM_KEY, 'algorithm_version': ALGORITHM_VERSION,
        'state_schema_version': projection.state_schema_version, 'storage_codec': STORAGE_CODEC,
        'state_payload': document.payload, 'state_payload_size': document.size,
        'algorithm_state_hash': projection.algorithm_state_hash,
        'semantic_state_hash': projection.semantic_state_hash,
        'projection_version': projection.projection_version, 'normalized_queue': 'review',
        'due_at': NOW, 'due_day': 1, 'is_suspended': False, 'is_buried': False,
        'history_completeness_code': 'HISTORY_NATIVE_COMPLETE', 'current_provenance_code': 'NATIVE_DIRECT',
        'created_at': NOW, 'updated_at': NOW,
    } for note_id in note_ids]
    if states:
        db.session.execute(insert(StudyProgressSubject), states)


def seed_owned_deck(learner_id, *, count, stateful_every=2):
    """An owned root deck with one subdeck; every ``stateful_every``-th Note is studied."""
    note_type, field_ids = _note_type(learner_id, 'Owned type')
    root = Deck(name='Owned', owner_user_id=learner_id)
    db.session.add(root)
    db.session.flush()
    child = Deck(name='Owned child', owner_user_id=learner_id, parent_id=root.id)
    db.session.add(child)
    db.session.flush()
    rows = _note_rows(prefix='20000000', owner_id=learner_id, note_type_id=note_type.id,
                      field_ids=field_ids, deck_ids=[root.id, child.id], count=count)
    db.session.connection().execute(Note.__table__.insert(), rows)
    _stage_review_subjects(learner_id, [row['id'] for row in rows[::stateful_every]])
    db.session.commit()
    return root.id


def seed_clone_install(learner_id, *, count, release, override_every=10, stateful_every=3,
                       prefix='30000000'):
    """A logical-overlay install of a two-deck source tree; returns ids for assertions."""
    publisher = User(username=f'publisher-{prefix}', email=f'publisher-{prefix}@example.test')
    db.session.add(publisher)
    db.session.flush()
    note_type, field_ids = _note_type(publisher.id, 'Shared type')
    source_root = Deck(name='Source', owner_user_id=publisher.id)
    local_root = Deck(name='Installed', owner_user_id=learner_id)
    db.session.add_all([source_root, local_root])
    db.session.flush()
    source_child = Deck(name='Source child', owner_user_id=publisher.id, parent_id=source_root.id)
    local_child = Deck(name='Installed child', owner_user_id=learner_id, parent_id=local_root.id)
    db.session.add_all([source_child, local_child])
    db.session.flush()
    rows = _note_rows(prefix=prefix, owner_id=publisher.id, note_type_id=note_type.id,
                      field_ids=field_ids, deck_ids=[source_root.id, source_child.id], count=count)
    db.session.connection().execute(Note.__table__.insert(), rows)
    item = DeckMarketplaceItem(owner_user_id=publisher.id, source_deck_id=source_root.id,
                               source_note_type_id=note_type.id, title='Shared',
                               publish_status='published', pricing_mode='free')
    db.session.add(item)
    db.session.flush()
    install_values = dict(deck_item_id=item.id, user_id=learner_id, local_deck_id=local_root.id,
                          clone_mode='logical_overlay', source_deck_id=source_root.id,
                          source_note_type_id=note_type.id, source_owner_user_id=publisher.id,
                          overlay_revision=0)
    release_row = None
    if release:
        release_row = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label='1.0.0',
                                  status='published', created_by_user_id=publisher.id)
        db.session.add(release_row)
        db.session.flush()
        for position, name in enumerate(FIELD_NAMES):
            field_id = field_ids[name]
            properties = {'name': name, 'field_type': 'text', 'position': position, 'required': False}
            for key, value in properties.items():
                db.session.add(DeckReleaseChange(
                    release_id=release_row.id, release_sequence_no=1,
                    change_key=f'field_def:{field_id}:{key}', entity_kind='field_def',
                    entity_id=field_id, field_def_id=field_id, property_key=key, operation='add',
                    after_value=value, source_deck_id=source_root.id,
                    sort_key=f'field:{position}:{field_id}:{key}'))
        db.session.execute(insert(DeckReleaseEntityMembership), [{
            'deck_item_id': item.id, 'entity_kind': 'note', 'entity_id': row['id'],
            'source_deck_id': row['deck_id'], 'introduced_sequence': 1,
            'metadata_json': {'note_type_id': note_type.id}, 'created_at': NOW, 'updated_at': NOW,
        } for row in rows])
        db.session.execute(insert(DeckReleaseNoteCheckpoint), [{
            'release_id': release_row.id, 'release_sequence_no': 1, 'source_note_id': row['id'],
            'source_deck_id': row['deck_id'], 'note_type_id': note_type.id,
            # Pinned values differ from the owner's live values.
            'field_values': {name: f'pinned-{name.lower()}-{row["id"][-6:]}' for name in FIELD_NAMES},
            'tags': [], 'content_hash': f'checkpoint-{row["id"][-6:]}', 'created_at': NOW,
        } for row in rows])
        item.current_release_id = release_row.id
        install_values.update(version_mode='release', applied_release_id=release_row.id,
                              seen_release_id=release_row.id)
    else:
        install_values.update(base_snapshot_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1))
    install = DeckInstall(**install_values)
    db.session.add(install)
    db.session.flush()
    db.session.add_all([
        DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_root.id, source_deck_id=source_root.id),
        DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_child.id, source_deck_id=source_child.id),
    ])
    overridden = [row['id'] for row in rows[::override_every]] if override_every else []
    for note_id in overridden:
        db.session.add(DeckCloneNoteFieldOverride(
            deck_install_id=install.id, source_note_id=note_id, source_field_def_id=field_ids['Word'],
            base_release_id=release_row.id if release_row is not None else None,
            field_name='Word', field_identity_key=field_ids['Word'], operation='set',
            value=f'override-{note_id[-6:]}'))
    _stage_review_subjects(learner_id, [row['id'] for row in rows[::stateful_every]])
    db.session.commit()
    return {
        'install_id': install.id, 'local_root_id': local_root.id, 'local_child_id': local_child.id,
        'source_root_id': source_root.id, 'source_child_id': source_child.id,
        'note_ids': [row['id'] for row in rows], 'overridden': set(overridden),
        'word_field_id': field_ids['Word'],
    }


class StatementCounter:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        event.listen(db.engine, 'before_cursor_execute', self._capture)
        return self

    def __exit__(self, *_exc):
        event.remove(db.engine, 'before_cursor_execute', self._capture)

    def _capture(self, _conn, _cursor, statement, *_args):
        self.statements.append(statement)


def legacy_full_scan_browse_decks(*, user_id):
    """The pre-2026-10-20 non-admin algorithm: scan every live deck, filter in Python."""
    from models.flashcard import DeckInstall as Install
    all_decks = (Deck.query.filter(Deck.deleted_at.is_(None))
                 .order_by(Deck.parent_id.isnot(None), Deck.position, Deck.created_at, Deck.id).all())
    deck_map = {deck.id: deck for deck in all_decks}
    children = {}
    for deck in all_decks:
        if deck.parent_id is not None:
            children.setdefault(deck.parent_id, []).append(deck.id)
    visible = {row[0] for row in db.session.query(Deck.id).filter(
        Deck.owner_user_id == user_id, Deck.deleted_at.is_(None))}
    visible |= {row[0] for row in db.session.query(Note.deck_id).filter(
        Note.user_id == user_id, Note.deck_id.isnot(None)).distinct()}
    roots = {row[0] for row in db.session.query(Install.local_deck_id).filter(
        Install.user_id == user_id, Install.local_deck_id.isnot(None)).distinct()}
    frontier = list(roots)
    while frontier:
        current = frontier.pop()
        visible.add(current)
        frontier.extend(child for child in children.get(current, []) if child not in visible)
    if not visible:
        return []
    stack = list(visible)
    while stack:
        deck = deck_map.get(stack.pop())
        if deck is None or deck.parent_id is None or deck.parent_id in visible:
            continue
        visible.add(deck.parent_id)
        stack.append(deck.parent_id)
    return [deck for deck in all_decks if deck.id in visible]


class BrowseQueryBoundsTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.session.remove)
        db.create_all()
        self.addCleanup(db.drop_all)
        self.learner_id = seed_learner()

    def _list(self, **args):
        db.session.remove()
        with StatementCounter() as counter:
            page = browse_card_service.list_browse_cards(
                user_id=self.learner_id, admin_mode=False, timezone_name='UTC', query_args=args)
        db.session.rollback()
        return page, len(counter.statements)

    def _assert_flat(self, deck_id, **args):
        small, small_count = self._list(deck_id=deck_id, per_page=10, **args)
        large, large_count = self._list(deck_id=deck_id, per_page=150, **args)
        self.assertEqual((len(small['items']), len(large['items'])), (10, 150))
        self.assertEqual(small['total'], large['total'])
        self.assertEqual([row['card_id'] for row in small['items']],
                         [row['card_id'] for row in large['items'][:10]])
        self.assertEqual(small_count, large_count, 'Browse statements grew with per_page')
        return large

    def test_owned_list_statement_count_does_not_grow_with_per_page(self):
        root_id = seed_owned_deck(self.learner_id, count=300)
        page = self._assert_flat(root_id)
        self.assertEqual(page['total'], 300)
        self.assertTrue({row['deck_name'] for row in page['items']} <= {'Owned', 'Owned child'})
        self.assertTrue(all(row['word'].startswith('w') for row in page['items']))

    def _assert_clone_rows(self, page, ids, *, pinned):
        rows_by_note = {row['note_id']: row for row in page['items']}
        self.assertTrue(set(rows_by_note) <= set(ids['note_ids']))
        self.assertEqual({row['deck_id'] for row in page['items']},
                         {ids['local_root_id'], ids['local_child_id']})
        self.assertEqual({row['deck_name'] for row in page['items']}, {'Installed', 'Installed child'})
        overridden = [note_id for note_id in rows_by_note if note_id in ids['overridden']]
        self.assertTrue(overridden, 'fixture page must include overridden Notes')
        for note_id, row in rows_by_note.items():
            suffix = note_id[-6:]
            if note_id in ids['overridden']:
                expected_word = f'override-{suffix}'
            elif pinned:
                expected_word = f'pinned-word-{suffix}'
            else:
                expected_word = f'w{int(suffix):06d}'
            self.assertEqual(row['word'], expected_word)
            self.assertEqual(row['reading'], f'pinned-reading-{suffix}' if pinned else f'r{int(suffix):06d}')

    def test_snapshot_clone_list_statement_count_does_not_grow_with_per_page(self):
        ids = seed_clone_install(self.learner_id, count=300, release=False)
        page = self._assert_flat(ids['local_root_id'])
        self.assertEqual(page['total'], 300)
        self._assert_clone_rows(page, ids, pinned=False)

    def test_release_clone_list_statement_count_does_not_grow_with_per_page(self):
        ids = seed_clone_install(self.learner_id, count=300, release=True)
        page = self._assert_flat(ids['local_root_id'])
        self.assertEqual(page['total'], 300)
        self._assert_clone_rows(page, ids, pinned=True)
        searched = self._assert_flat(ids['local_root_id'], q='pinned-word', sort_by='word')
        self.assertEqual(searched['total'], 300 - len(ids['overridden']))

    def test_mixed_owned_and_clone_list_without_deck_filter_is_flat(self):
        seed_owned_deck(self.learner_id, count=150)
        ids = seed_clone_install(self.learner_id, count=150, release=True)
        # Effective names: Owned child, Owned, Installed child, Installed (desc).
        # Both pages reach every deck, so only the row count differs between them.
        small, small_count = self._list(per_page=230, sort_by='deck', sort_dir='desc')
        large, large_count = self._list(per_page=300, sort_by='deck', sort_dir='desc')
        self.assertEqual((small['total'], len(small['items']), len(large['items'])), (300, 230, 300))
        self.assertEqual(small_count, large_count)
        clone_note_ids = set(ids['note_ids'])
        clone_rows = [row for row in large['items'] if row['note_id'] in clone_note_ids]
        owned_rows = [row for row in large['items'] if row['note_id'] not in clone_note_ids]
        self.assertEqual((len(clone_rows), len(owned_rows)), (150, 150))
        self.assertEqual({row['deck_name'] for row in clone_rows}, {'Installed', 'Installed child'})
        self.assertEqual({row['deck_name'] for row in owned_rows}, {'Owned', 'Owned child'})

    def test_accessible_browse_decks_match_full_scan_and_skip_unrelated_decks(self):
        learner_id = self.learner_id
        other = User(username='other-owner', email='other-owner@example.test')
        db.session.add(other)
        db.session.flush()
        other_id = other.id
        note_type, field_ids = _note_type(learner_id, 'Scope type')

        def deck(name, owner, parent=None, deleted=False, position=0):
            row = Deck(name=name, owner_user_id=owner, parent_id=parent.id if parent else None,
                       position=position, deleted_at=NOW if deleted else None)
            db.session.add(row)
            db.session.flush()
            return row

        owned_root = deck('Owned root', learner_id, position=2)
        deck('Owned child', learner_id, owned_root)
        # Another user's folder above an owned deck is an ancestor.
        foreign_folder = deck('Foreign folder', other.id, position=1)
        deck('Owned under foreign', learner_id, foreign_folder)
        # A foreign child of an owned deck is not visible (no install, no Note).
        deck('Foreign under owned', other.id, owned_root)
        # A foreign deck holding the learner's Note, plus its ancestors.
        holder_parent = deck('Holder parent', other.id)
        holder = deck('Holder', other.id, holder_parent)
        db.session.add(Note(user_id=learner_id, note_type_id=note_type.id, deck_id=holder.id,
                            field_values={'Word': 'x'}))
        # Install root subtree, including foreign and deleted descendants.
        install_root = deck('Install root', other.id, position=3)
        install_child = deck('Install child', other.id, install_root)
        deck('Install grandchild', other.id, install_child)
        deleted_child = deck('Deleted install child', other.id, install_root, deleted=True)
        deck('Child of deleted', other.id, deleted_child)
        # Descendants below an owned deck inside the install subtree are not expanded.
        owned_inside = deck('Owned inside install', learner_id, install_root)
        deck('Foreign below owned inside', other.id, owned_inside)
        # A deleted install root still exposes its live children.
        deleted_root = deck('Deleted install root', other.id, deleted=True)
        deck('Live child of deleted root', other.id, deleted_root)
        # A live owned deck under a deleted parent stops the ancestor walk.
        grand = deck('Grand of deleted parent', other.id)
        deleted_parent = deck('Deleted parent', other.id, grand, deleted=True)
        deck('Owned under deleted parent', learner_id, deleted_parent)
        for local_root in (install_root, deleted_root):
            item = DeckMarketplaceItem(owner_user_id=other.id, source_deck_id=local_root.id,
                                       source_note_type_id=note_type.id, title=f'Scope {local_root.id}',
                                       publish_status='published', pricing_mode='free')
            db.session.add(item)
            db.session.flush()
            db.session.add(DeckInstall(deck_item_id=item.id, user_id=learner_id, local_deck_id=local_root.id,
                                       clone_mode='logical_overlay', source_deck_id=owned_root.id))
        # Unrelated decks must not be loaded at all.
        unrelated_parent = deck('Unrelated', other.id)
        for index in range(20):
            deck(f'Unrelated {index}', other.id, unrelated_parent)
        db.session.commit()

        expected = [(row.id, row.name) for row in legacy_full_scan_browse_decks(user_id=learner_id)]
        db.session.remove()
        actual = vocabulary_repository.collect_accessible_browse_decks(user_id=learner_id, admin_mode=False)
        self.assertEqual([(row.id, row.name) for row in actual], expected)
        loaded_names = {obj.name for obj in db.session.identity_map.values() if isinstance(obj, Deck)}
        self.assertFalse({name for name in loaded_names if name.startswith('Unrelated')})
        self.assertIn('Owned under foreign', loaded_names)
        self.assertNotIn('Foreign under owned', loaded_names)
        self.assertNotIn('Foreign below owned inside', loaded_names)
        self.assertIn('Live child of deleted root', loaded_names)
        self.assertNotIn('Grand of deleted parent', loaded_names)
        for user_id in (other_id, other_id + 1000):
            expected = [(row.id, row.name) for row in legacy_full_scan_browse_decks(user_id=user_id)]
            db.session.remove()
            actual = vocabulary_repository.collect_accessible_browse_decks(user_id=user_id, admin_mode=False)
            self.assertEqual([(row.id, row.name) for row in actual], expected)


if __name__ == '__main__':
    unittest.main()
