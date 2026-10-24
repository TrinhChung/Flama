"""Scalar dependency probes and atomic persistence for due projections."""

import hashlib
import json

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.repositories.deck_count_snapshot_repository import read_revision_vectors
from app.repositories.stats_query_repository import forecast_counts_notes
from app.repositories.study_authority_repository import read_study_authority_route
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.deck_count_snapshot import DeckCountContentRevision, DeckCountLearnerRevision
from models.forecast_snapshot import StudyForecastDueBucket, StudyForecastSnapshot


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).digest()


def scope_key(deck_ids):
    return _hash({"scope": "collection" if deck_ids is None else "decks",
                  "deck_ids": None if deck_ids is None else sorted(set(map(int, deck_ids)))})


def dependency_hash(session, *, user_id, deck_ids):
    """Probe O(deck/install metadata), without Notes, progress or history scans.

    Collection weights are a union, so their snapshots are computed separately
    rather than summing direct deck snapshots. Global epochs cover bulk writes,
    alias membership and Notes without a physical deck.
    """
    owned = session.execute(select(Deck.id, Deck.parent_id, Deck.owner_user_id).where(
        Deck.owner_user_id == user_id,
    ).order_by(Deck.id)).all()
    installs = session.execute(select(
        DeckInstall.id, DeckInstall.user_id, DeckInstall.local_deck_id,
        DeckInstall.clone_mode, DeckInstall.source_deck_id, DeckInstall.source_note_type_id,
        DeckInstall.source_owner_user_id, DeckInstall.base_snapshot_at, DeckInstall.installed_at,
        DeckInstall.applied_release_id, DeckInstall.version_mode, DeckInstall.overlay_revision,
        DeckInstall.deck_item_id, DeckRelease.id, DeckRelease.sequence_no,
        DeckRelease.status, DeckRelease.manifest_hash, DeckRelease.template_pins_initialized,
    ).outerjoin(DeckRelease, DeckRelease.id == DeckInstall.applied_release_id).where(
        DeckInstall.user_id == user_id,
    ).order_by(DeckInstall.id)).all()
    maps = session.execute(select(
        DeckCloneDeckMap.deck_install_id, DeckCloneDeckMap.source_deck_id,
        DeckCloneDeckMap.local_deck_id,
    ).join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id).where(
        DeckInstall.user_id == user_id,
    ).order_by(DeckCloneDeckMap.deck_install_id, DeckCloneDeckMap.source_deck_id,
               DeckCloneDeckMap.local_deck_id)).all()
    physical = {int(row[0]) for row in owned}
    physical.update(int(row[1]) for row in maps if row[1] is not None)
    physical.update(int(row[2]) for row in maps if row[2] is not None)
    if deck_ids is not None:
        physical.update(map(int, deck_ids))
    vectors = read_revision_vectors(session, user_id=user_id, deck_ids=physical)
    global_content = session.execute(select(DeckCountContentRevision.revision).where(
        DeckCountContentRevision.physical_deck_id == 0,
    )).scalar_one_or_none() or 0
    global_learner = session.execute(select(DeckCountLearnerRevision.revision).where(
        DeckCountLearnerRevision.user_id == user_id,
        DeckCountLearnerRevision.effective_deck_id == 0,
    )).scalar_one_or_none() or 0
    route = read_study_authority_route(session, learner_user_id=user_id)
    # Buckets hold the raw forecast's unit; flipping it invalidates them.
    unit = "note" if forecast_counts_notes() else "card"
    return _hash({"implementation": f"forecast-{unit}-buckets.v1", "scope": scope_key(deck_ids).hex(),
                  "owned_decks": [tuple(row) for row in owned],
                  "installs": [tuple(row) for row in installs], "maps": [tuple(row) for row in maps],
                  "revisions": vectors, "global_content": int(global_content),
                  "global_learner": int(global_learner), "mode": route.mode_code,
                  "epoch": route.epoch, "storage": route.storage_profile})


def read_header(session, *, user_id, scope_hash):
    table = StudyForecastSnapshot.__table__
    return session.execute(select(table).where(table.c.user_id == user_id,
        table.c.scope_hash == scope_hash)).mappings().one_or_none()


def read_buckets(session, *, user_id, scope_hash, start_day=None, end_day=None):
    table = StudyForecastDueBucket.__table__
    statement = select(table.c.due_day, table.c.queue, table.c.card_count).where(
        table.c.user_id == user_id, table.c.scope_hash == scope_hash,
    )
    if start_day is not None:
        statement = statement.where(table.c.due_day >= start_day)
    if end_day is not None:
        statement = statement.where(table.c.due_day <= end_day)
    return session.execute(statement.order_by(table.c.due_day, table.c.queue)).all()


def publish_snapshot(session, *, header, buckets):
    """Header and replacement buckets commit together in the caller's UoW."""
    table = StudyForecastSnapshot.__table__
    dialect = session.get_bind().dialect.name
    mutable = {name for name in header if name not in {"user_id", "scope_hash"}}
    if dialect == "mysql":
        statement = mysql_insert(table).values(header)
        statement = statement.on_duplicate_key_update(**{
            name: getattr(statement.inserted, name) for name in mutable})
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(header)
        statement = statement.on_conflict_do_update(index_elements=["user_id", "scope_hash"],
            set_={name: getattr(statement.excluded, name) for name in mutable})
    else:
        raise RuntimeError("Forecast snapshots support MySQL and SQLite only")
    session.execute(statement)
    table = StudyForecastDueBucket.__table__
    session.execute(delete(table).where(table.c.user_id == header["user_id"],
                                       table.c.scope_hash == header["scope_hash"]))
    for offset in range(0, len(buckets), 200):
        session.execute(table.insert(), [{"user_id": header["user_id"],
            "scope_hash": header["scope_hash"], "due_day": day, "queue": queue,
            "card_count": count} for (day, queue), count in buckets[offset:offset+200]])
