"""Batched persistence for direct-deck caches; callers own transactions."""

from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.deck_count_snapshot import (
    DeckCountContentRevision, DeckCountLearnerRevision, DeckStudyCountSnapshot,
)
from models.user import User
from models.user_role import UserRole


# Cache the common one-deck review invalidation instead of compiling a new
# dialect upsert on every command. Atomic increments keep concurrent commits
# and rollback semantics identical to the batched maintenance path.
_BUMP_CONTENT_MYSQL = text(
    "INSERT INTO deck_count_content_revisions (physical_deck_id,revision,updated_at) "
    "VALUES (:physical_deck_id,1,:updated_at) "
    "ON DUPLICATE KEY UPDATE revision=revision+1,updated_at=:updated_at"
)
_BUMP_LEARNER_MYSQL = text(
    "INSERT INTO deck_count_learner_revisions (user_id,effective_deck_id,revision,updated_at) "
    "VALUES (:user_id,:effective_deck_id,1,:updated_at) "
    "ON DUPLICATE KEY UPDATE revision=revision+1,updated_at=:updated_at"
)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def owned_scope_rows(session, *, user_id, deck_ids=None):
    statement = select(Deck.id, Deck.parent_id, Deck.owner_user_id).where(
        Deck.owner_user_id == int(user_id), Deck.deleted_at.is_(None),
    )
    if deck_ids is not None:
        ids = sorted({int(value) for value in deck_ids})
        if not ids:
            return []
        statement = statement.where(Deck.id.in_(ids))
    return session.execute(statement.order_by(Deck.id)).all()


def overlay_local_deck_ids(session, deck_ids):
    ids = sorted({int(value) for value in deck_ids})
    if not ids:
        return set()
    # Any mapped local deck is excluded, regardless of the install's owner or
    # clone mode. A root with missing mappings is also an unknown overlay scope.
    mapped = session.execute(select(DeckCloneDeckMap.local_deck_id).where(
        DeckCloneDeckMap.local_deck_id.in_(ids),
    )).scalars()
    installed = session.execute(select(DeckInstall.local_deck_id).where(
        DeckInstall.local_deck_id.in_(ids),
    )).scalars()
    return {int(value) for value in list(mapped) + list(installed) if value is not None}


def read_installed_scope_dependencies(session, *, deck_ids):
    """Small map/install/release vectors, with no Note or progress scan.

    Return every mapping, including malformed/foreign mappings: eligibility is
    the caller's decision. Missing release metadata is represented as NULL so
    legacy fallback never accidentally acquires an initialized-release stamp.
    """
    ids = sorted({int(value) for value in deck_ids})
    if not ids:
        return {}
    statement = select(
        DeckCloneDeckMap.local_deck_id.label("local_deck_id"),
        DeckCloneDeckMap.source_deck_id.label("map_source_deck_id"),
        DeckInstall.id.label("install_id"),
        DeckInstall.user_id.label("install_user_id"),
        DeckInstall.local_deck_id.label("install_local_deck_id"),
        DeckInstall.source_deck_id.label("install_source_deck_id"),
        DeckInstall.source_owner_user_id.label("source_owner_user_id"),
        DeckInstall.source_note_type_id.label("source_note_type_id"),
        DeckInstall.deck_item_id.label("deck_item_id"),
        DeckInstall.clone_mode.label("clone_mode"),
        DeckInstall.applied_release_id.label("applied_release_id"),
        DeckInstall.version_mode.label("version_mode"),
        DeckInstall.overlay_revision.label("overlay_revision"),
        DeckInstall.base_snapshot_at.label("base_snapshot_at"),
        DeckInstall.installed_at.label("installed_at"),
        DeckRelease.id.label("release_id"),
        DeckRelease.deck_item_id.label("release_deck_item_id"),
        DeckRelease.sequence_no.label("release_sequence_no"),
        DeckRelease.status.label("release_status"),
        DeckRelease.template_pins_initialized.label("template_pins_initialized"),
        DeckRelease.manifest_hash.label("release_manifest_hash"),
    ).select_from(DeckCloneDeckMap).join(
        DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id,
    ).outerjoin(DeckRelease, DeckRelease.id == DeckInstall.applied_release_id).where(
        DeckCloneDeckMap.local_deck_id.in_(ids),
    )
    return {int(row["local_deck_id"]): dict(row) for row in session.execute(statement).mappings()}


def read_admin_mode(session, user_id):
    row = session.execute(select(User.is_admin, UserRole.is_admin).outerjoin(
        UserRole, UserRole.id == User.role_id,
    ).where(User.id == int(user_id))).one_or_none()
    if row is None:
        raise ValueError("Deck-count learner does not exist")
    return bool(row[1]) if row[1] is not None else bool(row[0])


def read_revision_vectors(session, *, user_id, deck_ids):
    ids = sorted({0, *(int(value) for value in deck_ids)})
    content = dict(session.execute(select(
        DeckCountContentRevision.physical_deck_id, DeckCountContentRevision.revision,
    ).where(DeckCountContentRevision.physical_deck_id.in_(ids))).all())
    learner = dict(session.execute(select(
        DeckCountLearnerRevision.effective_deck_id, DeckCountLearnerRevision.revision,
    ).where(DeckCountLearnerRevision.user_id == int(user_id),
            DeckCountLearnerRevision.effective_deck_id.in_(ids))).all())
    return {
        deck_id: (int(content.get(0, 0)), int(content.get(deck_id, 0)),
                  int(learner.get(0, 0)), int(learner.get(deck_id, 0)))
        for deck_id in ids if deck_id != 0
    }


def read_snapshots(session, *, user_id, deck_ids, contract_code, unit_code):
    ids = sorted({int(value) for value in deck_ids})
    if not ids:
        return {}
    table = DeckStudyCountSnapshot.__table__
    rows = session.execute(select(table).where(
        table.c.user_id == int(user_id), table.c.effective_deck_id.in_(ids),
        table.c.contract_code == contract_code, table.c.unit_code == unit_code,
    )).mappings()
    return {int(row["effective_deck_id"]): row for row in rows}


def _bump(session, table, rows, keys):
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "mysql" and len(rows) == 1:
        statement = (_BUMP_CONTENT_MYSQL if table is DeckCountContentRevision.__table__
                     else _BUMP_LEARNER_MYSQL)
        session.execute(statement, rows[0])
        return
    for offset in range(0, len(rows), 200):
        batch = rows[offset:offset + 200]
        if dialect == "mysql":
            statement = mysql_insert(table).values(batch)
            session.execute(statement.on_duplicate_key_update(
                revision=table.c.revision + 1, updated_at=statement.inserted.updated_at,
            ))
        elif dialect == "sqlite":
            statement = sqlite_insert(table).values(batch)
            session.execute(statement.on_conflict_do_update(
                index_elements=keys,
                set_={"revision": table.c.revision + 1, "updated_at": statement.excluded.updated_at},
            ))
        else:
            raise RuntimeError("Deck count snapshots support MySQL and SQLite only")


def bump_content_revisions(session, physical_deck_ids):
    ids = sorted({int(value) for value in physical_deck_ids})
    if any(value < 0 for value in ids):
        raise ValueError("Content revision keys must be nonnegative")
    now = _utcnow()
    _bump(session, DeckCountContentRevision.__table__, [
        {"physical_deck_id": value, "revision": 1, "updated_at": now} for value in ids
    ], ["physical_deck_id"])


def bump_learner_revisions(session, learner_deck_keys):
    keys = sorted({(int(user_id), int(deck_id)) for user_id, deck_id in learner_deck_keys})
    if any(user_id <= 0 or deck_id < 0 for user_id, deck_id in keys):
        raise ValueError("Learner revision keys require a positive user and nonnegative deck")
    now = _utcnow()
    _bump(session, DeckCountLearnerRevision.__table__, [
        {"user_id": user_id, "effective_deck_id": deck_id, "revision": 1, "updated_at": now}
        for user_id, deck_id in keys
    ], ["user_id", "effective_deck_id"])


def upsert_snapshots(session, rows):
    table = DeckStudyCountSnapshot.__table__
    dialect = session.get_bind().dialect.name
    mutable = [column.name for column in table.c if not column.primary_key]
    for offset in range(0, len(rows), 100):
        batch = rows[offset:offset + 100]
        if dialect == "mysql":
            statement = mysql_insert(table).values(batch)
            session.execute(statement.on_duplicate_key_update(**{
                name: getattr(statement.inserted, name) for name in mutable
            }))
        elif dialect == "sqlite":
            statement = sqlite_insert(table).values(batch)
            session.execute(statement.on_conflict_do_update(
                index_elements=[column.name for column in table.primary_key],
                set_={name: getattr(statement.excluded, name) for name in mutable},
            ))
        else:
            raise RuntimeError("Deck count snapshots support MySQL and SQLite only")
