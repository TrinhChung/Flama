"""Frozen v1 cutover evidence contract shared by revision66/67 and offline tool.

This module deliberately reads reflected tables, never current ORM mappings.
Historical source JSON is archived verbatim; canonical hashes retain JSON types.
"""
from __future__ import annotations

from datetime import datetime
from contextlib import contextmanager
import hashlib
import json

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

CODEC = "field-id.v1"
LEDGER = "field_value_identity_definitions"
ARCHIVE = "field_value_identity_archive"
CUTOVERS = "field_value_identity_cutovers"


@contextmanager
def cached_reflections(connection):
    """Cache metadata only within a read/migration preparation operation."""
    key = "field_identity_contract.reflections"
    if key in connection.info:
        yield
        return
    connection.info[key] = {}
    try:
        yield
    finally:
        connection.info.pop(key, None)


@contextmanager
def bounded_mysql_ddl(connection):
    if connection.dialect.name != "mysql":
        yield
        return
    previous = int(connection.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    connection.execute(sa.text("SET SESSION lock_wait_timeout = 30"))
    try:
        yield
    finally:
        connection.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def tables(metadata):
    ledger = sa.Table(LEDGER, metadata,
        sa.Column("identity_key", sa.String(115), primary_key=True),
        sa.Column("identity_kind", sa.String(16), nullable=False),
        sa.Column("field_id", sa.String(36), nullable=True),
        sa.Column("note_type_id", sa.String(36), nullable=True),
        sa.Column("deck_install_id", sa.String(36), nullable=True),
        sa.Column("retained_name", sa.String(255), nullable=False),
        sa.Column("label_history", sa.JSON(), nullable=False),
        sa.Column("is_retired", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Index("ix_field_value_identity_definitions_note_type_id", "note_type_id"),
        sa.Index("ix_field_value_identity_definitions_deck_install_id", "deck_install_id"))
    archive = sa.Table(ARCHIVE, metadata,
        sa.Column("object_kind", sa.String(16), primary_key=True),
        sa.Column("object_id", sa.String(115), primary_key=True),
        sa.Column("source_raw", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=False),
        sa.Column("captured_schema", sa.JSON(), nullable=False),
        sa.Column("canonical_payload", sa.JSON(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("canonical_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    cutover = sa.Table(CUTOVERS, metadata,
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("archive_count", sa.Integer(), nullable=False),
        sa.Column("note_count", sa.Integer(), nullable=False),
        sa.Column("media_count", sa.Integer(), nullable=False),
        sa.Column("rename_job_count", sa.Integer(), nullable=False),
        sa.Column("override_count", sa.Integer(), nullable=False),
        sa.Column("archive_root_sha256", sa.String(64), nullable=False),
        sa.Column("schema_sha256", sa.String(64), nullable=False),
        sa.Column("definitions_sha256", sa.String(64), nullable=False),
        sa.Column("writers_quiesced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True))
    return ledger, archive, cutover


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item))


def typed_hash(value):
    return hashlib.sha256(json_text(value).encode("utf-8")).hexdigest()


def raw_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extra_identity_key(note_type_id, name):
    return "extra:" + raw_hash(str(note_type_id) + "\0" + name)


def reflected(connection, name):
    cache = connection.info.get("field_identity_contract.reflections")
    if cache is None:
        return sa.Table(name, sa.MetaData(), autoload_with=connection)
    if name not in cache:
        cache[name] = sa.Table(name, sa.MetaData(), autoload_with=connection)
    return cache[name]


def bounded_rows(connection, statement, identity, *, batch_size=200):
    """Keyset iteration permits nested reads without unbuffered cursor loss."""
    cursor = None
    while True:
        query = statement.order_by(identity).limit(batch_size)
        if cursor is not None:
            query = query.where(identity > cursor)
        rows = connection.execute(query).mappings().all()
        if not rows:
            break
        yield from rows
        cursor = rows[-1][identity.name]


def schema_fingerprint(connection, *, include_ledger=False):
    """Hash every identity/scope input; changes after preparation block DDL."""
    descriptors = {
        "field_defs": ("id", "note_type_id", "name", "created_at"),
        "note_types": ("id", "user_id", "field_schema_revision"),
        "deck_clone_added_field_defs": ("id", "deck_install_id", "name", "properties", "created_at"),
        "deck_clone_added_notes": ("id", "deck_install_id", "note_id"),
        "deck_clone_field_def_overrides": ("id", "deck_install_id", "source_field_def_id", "is_disabled", "properties"),
        "deck_clone_deck_maps": ("id", "deck_install_id", "local_deck_id"),
        "deck_installs": ("id", "user_id", "source_note_type_id", "overlay_revision", "applied_release_id"),
    }
    if include_ledger:
        descriptors[LEDGER] = ("identity_key", "identity_kind", "field_id", "note_type_id", "deck_install_id",
            "retained_name", "label_history", "is_retired")
    digest = hashlib.sha256()
    known = set(sa.inspect(connection).get_table_names())
    for name, columns in sorted(descriptors.items()):
        if name not in known:
            continue
        table = reflected(connection, name)
        selected = [table.c[column] for column in columns if column in table.c]
        digest.update((name + "\n").encode())
        identity = table.c.identity_key if name == LEDGER else table.c.id
        for row in bounded_rows(connection, sa.select(*selected), identity):
            digest.update((json_text(dict(row)) + "\n").encode("utf-8"))
    return digest.hexdigest()


def archive_root(connection):
    table = reflected(connection, ARCHIVE)
    digest, counts = hashlib.sha256(), {"note": 0, "media": 0, "rename_job": 0, "override": 0}
    # No nested statements inside this loop: server-side streaming bounds the
    # archive byte budget even when it contains many large raw payloads.
    for row in connection.execute(sa.select(table).order_by(table.c.object_kind, table.c.object_id)
            .execution_options(yield_per=200)).mappings():
        if raw_hash(row["source_raw"]) != row["source_sha256"] or typed_hash(row["canonical_payload"]) != row["canonical_sha256"]:
            raise RuntimeError("Field cutover archive checksum mismatch.")
        digest.update((json_text([row["object_kind"], row["object_id"], row["source_sha256"],
            row["canonical_sha256"], typed_hash(row["captured_schema"])]) + "\n").encode("utf-8"))
        if row["object_kind"] not in counts:
            raise RuntimeError("Unknown field cutover archive object kind.")
        counts[row["object_kind"]] += 1
    return digest.hexdigest(), counts


def verify_prepared(connection, *, allow_partial_contract=False):
    with cached_reflections(connection):
        return _verify_prepared(connection, allow_partial_contract=allow_partial_contract)


def _verify_prepared(connection, *, allow_partial_contract=False):
    """Read-only all-row gate before destructive contraction; no source repair."""
    inspector = sa.inspect(connection)
    notes, media = reflected(connection, "notes"), reflected(connection, "media_assets")
    archive, manifest = reflected(connection, ARCHIVE), reflected(connection, CUTOVERS)
    row = connection.execute(sa.select(manifest).where(manifest.c.id == CODEC)).mappings().first()
    totals = {"note": connection.execute(sa.select(sa.func.count()).select_from(notes)).scalar_one(),
              "media": connection.execute(sa.select(sa.func.count()).select_from(media)).scalar_one(),
              "override": connection.execute(sa.text("SELECT COUNT(*) FROM deck_clone_note_field_overrides")).scalar_one()
                  if inspector.has_table("deck_clone_note_field_overrides") else 0,
              "rename_job": connection.execute(sa.text("SELECT COUNT(*) FROM field_rename_jobs")).scalar_one()
                  if inspector.has_table("field_rename_jobs") else
                  (row["rename_job_count"] if row and allow_partial_contract else 0)}
    if not any(totals.values()) and row is None:
        return {"empty": True, "counts": totals}
    acceptable_states = {"verified", "contracted"} if allow_partial_contract else {"verified"}
    if row is None or row["state"] not in acceptable_states or not row["writers_quiesced"]:
        raise RuntimeError("Field contraction requires explicit quiesced-writer cutover preparation.")
    root, counts = archive_root(connection)
    if counts != totals or sum(counts.values()) != row["archive_count"] or root != row["archive_root_sha256"] \
            or any(row[key + "_count"] != totals[key] for key in totals):
        raise RuntimeError("Field cutover archive coverage/root differs from live rows.")
    if schema_fingerprint(connection) != row["schema_sha256"]:
        raise RuntimeError("Field scope/schema changed after cutover preparation.")
    if schema_fingerprint(connection, include_ledger=True) != row["definitions_sha256"]:
        raise RuntimeError("Retained Field identity provenance changed after cutover preparation.")
    has_names = "field_values" in notes.c
    if not has_names and not allow_partial_contract:
        raise RuntimeError("Named storage already contracted; verify immutable archive and canonical values separately.")
    query = sa.select(notes, sa.cast(notes.c.field_values, sa.Text).label("named_raw")) if has_names else sa.select(notes)
    query = query.add_columns(archive.c.canonical_payload.label("_canonical"), archive.c.source_raw.label("_raw"),
        archive.c.canonical_sha256.label("_hash")).outerjoin(archive, sa.and_(archive.c.object_kind == "note", archive.c.object_id == notes.c.id))
    for live in bounded_rows(connection, query, notes.c.id):
        expected = live["_canonical"]
        if expected is None:
            raise RuntimeError("Note has no immutable cutover archive record.")
        if (has_names and live["named_raw"] != live["_raw"]) or typed_hash({key: live[key] for key in expected}) != live["_hash"]:
            raise RuntimeError("Note changed after field cutover preparation.")
        if live["field_values_codec"] != CODEC or not isinstance(live["field_values_by_id"], dict) \
                or not isinstance(live["field_values_extras"], dict):
            raise RuntimeError("Every Note must have the canonical v1 codec before contraction.")
    media_query = sa.select(media, archive.c.canonical_payload.label("_canonical"), archive.c.canonical_sha256.label("_hash")) \
        .outerjoin(archive, sa.and_(archive.c.object_kind == "media", archive.c.object_id == media.c.id))
    for live in bounded_rows(connection, media_query, media.c.id):
        if live["_canonical"] is None or typed_hash({key: live[key] for key in live["_canonical"]}) != live["_hash"]:
            raise RuntimeError("Media changed after field cutover preparation.")
    if inspector.has_table("deck_clone_note_field_overrides"):
        overrides = reflected(connection, "deck_clone_note_field_overrides")
        query = sa.select(overrides, archive.c.canonical_payload.label("_canonical"), archive.c.canonical_sha256.label("_hash")) \
            .outerjoin(archive, sa.and_(archive.c.object_kind == "override", archive.c.object_id == overrides.c.id))
        for live in bounded_rows(connection, query, overrides.c.id):
            if live["_canonical"] is None or typed_hash({key: live[key] for key in live["_canonical"]}) != live["_hash"]:
                raise RuntimeError("Clone override changed after field cutover preparation.")
    if inspector.has_table("field_rename_jobs"):
        jobs = reflected(connection, "field_rename_jobs")
        query = sa.select(jobs, archive.c.source_raw.label("_raw")).outerjoin(archive,
            sa.and_(archive.c.object_kind == "rename_job", archive.c.object_id == jobs.c.id))
        for live in bounded_rows(connection, query, jobs.c.id):
            if json_text({key: value for key, value in live.items() if key != "_raw"}) != live["_raw"]:
                raise RuntimeError("Rename evidence changed after field cutover preparation.")
    return {"empty": False, "counts": counts, "archive_root_sha256": root}
