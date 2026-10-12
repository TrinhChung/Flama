"""Typed offline archives and fail-closed gates for retired tables.

This module never imports application models. Bundles live outside the active
database and include original CREATE TABLE statements for manual recovery.
Restore checks recreate source-shaped tables in an isolated database, without
external foreign keys, and prove exact row-content round trips. A full MySQL
backup rehearsal remains a deployment prerequisite; this check preserves the
retired evidence independently of live parents.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

import sqlalchemy as sa


FORMAT = "flama-retirement-archive-v1"
ARCHIVE_ENV = "FLAMA_RETIREMENT_ARCHIVE"
DEAD_MODEL_TABLES = (
    "vocabulary_column_preferences", "study_progress_backfill_runs",
    "study_progress_backfill_checkpoints", "study_progress_backfill_dispositions",
)


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _encode(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"kind": "bytes", "value": bytes(value).hex()}
    if isinstance(value, (datetime, date, time)):
        return {"kind": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"kind": "decimal", "value": str(value)}
    if isinstance(value, (dict, list)):
        return {"kind": "json", "value": value}
    return {"kind": "scalar", "value": value}


def _decode(value):
    kind, raw = value["kind"], value["value"]
    decoders = {"bytes": bytes.fromhex, "datetime": datetime.fromisoformat,
                "date": date.fromisoformat, "time": time.fromisoformat, "decimal": Decimal}
    if kind in ("json", "scalar"):
        return raw
    if kind not in decoders:
        raise RuntimeError(f"Unsupported archive value kind: {kind}")
    return decoders[kind](raw)


def _rows(connection, table):
    if not list(table.primary_key.columns):
        raise RuntimeError(f"Cannot archive {table.name}: no primary key for deterministic ordering")
    result = connection.execution_options(stream_results=True).execute(
        sa.select(table).order_by(*table.primary_key.columns))
    return [[_encode(value) for value in row] for row in result]


def _sha(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update((_canonical(row) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _bundle_hash(bundle):
    # Verification records do not change the source evidence identity.
    data = {key: value for key, value in bundle.items()
            if key not in ("bundle_sha256", "restore_verifications")}
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _column_descriptor(column, dialect):
    generic = column.type.as_generic()
    if isinstance(generic, sa.JSON):
        kind = "json"
    elif isinstance(generic, sa.LargeBinary):
        kind = "binary"
    elif isinstance(generic, sa.Boolean):
        kind = "boolean"
    elif isinstance(generic, sa.DateTime):
        kind = "datetime"
    elif isinstance(generic, sa.Date):
        kind = "date"
    elif isinstance(generic, sa.Time):
        kind = "time"
    elif isinstance(generic, sa.Integer):
        kind = "integer"
    elif isinstance(generic, sa.Float):
        kind = "float"
    elif isinstance(generic, sa.Numeric):
        kind = "numeric"
    elif isinstance(generic, sa.String):
        kind = "text"
    else:
        raise RuntimeError(f"Unsupported archive column type: {column.name}={column.type}")
    return {"name": column.name, "kind": kind, "nullable": bool(column.nullable),
            "primary_key": bool(column.primary_key), "source_type": str(column.type.compile(dialect=dialect)),
            "length": getattr(generic, "length", None), "precision": getattr(generic, "precision", None),
            "scale": getattr(generic, "scale", None)}


def write_bundle(connection, output: Path, table_names=DEAD_MODEL_TABLES):
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite archive: {output}")
    existing = set(sa.inspect(connection).get_table_names())
    missing = set(table_names) - existing
    if missing:
        raise RuntimeError(f"Cannot archive missing tables: {', '.join(sorted(missing))}")
    bundle = {"format": FORMAT, "source_dialect": connection.dialect.name,
              "source_database": connection.engine.url.database,
              "created_at": datetime.now(timezone.utc).isoformat(), "tables": [],
              "restore_verifications": []}
    for name in table_names:
        table = sa.Table(name, sa.MetaData(), autoload_with=connection, resolve_fks=False)
        rows = _rows(connection, table)
        if connection.dialect.name == "mysql":
            create_sql = connection.exec_driver_sql(
                f"SHOW CREATE TABLE {connection.dialect.identifier_preparer.quote(name)}").one()[1]
        elif connection.dialect.name == "sqlite":
            create_sql = connection.execute(sa.text(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :name"), {"name": name}).scalar_one()
        else:
            create_sql = str(sa.schema.CreateTable(table).compile(dialect=connection.dialect))
        bundle["tables"].append({"name": name, "columns": [_column_descriptor(c, connection.dialect) for c in table.columns],
                                 "create_sql": create_sql, "row_count": len(rows), "sha256": _sha(rows), "rows": rows})
    bundle["bundle_sha256"] = _bundle_hash(bundle)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_canonical(bundle) + "\n", encoding="utf-8")
    return bundle


def load_bundle(path: Path):
    bundle = json.loads(path.read_text(encoding="utf-8"))
    if bundle.get("format") != FORMAT or bundle.get("bundle_sha256") != _bundle_hash(bundle):
        raise RuntimeError("Retirement archive bundle format/checksum mismatch")
    names = [table["name"] for table in bundle["tables"]]
    if len(names) != len(set(names)):
        raise RuntimeError("Retirement archive contains duplicate tables")
    for table in bundle["tables"]:
        if table["row_count"] != len(table["rows"]) or table["sha256"] != _sha(table["rows"]):
            raise RuntimeError(f"Retirement archive table checksum mismatch: {table['name']}")
    return bundle


def _restore_type(column, dialect):
    kind = column["kind"]
    if kind == "float" and dialect.name == "mysql":
        # Preserve the reflected source type and result processor. Promoting
        # FLOAT to MySQL DOUBLE changes SQLAlchemy's default asdecimal=False
        # to True, turning archived floats into quantized Decimal values.
        from sqlalchemy.dialects.mysql import DOUBLE, FLOAT
        if str(column["source_type"]).upper().startswith("FLOAT"):
            return FLOAT(precision=column["precision"], asdecimal=False)
        return DOUBLE(asdecimal=True)
    if kind == "datetime" and dialect.name == "mysql":
        from sqlalchemy.dialects.mysql import DATETIME
        return DATETIME(fsp=6)
    if kind == "text":
        return sa.String(column["length"]) if column["length"] else sa.Text()
    if kind == "binary":
        return sa.LargeBinary(column["length"])
    if kind == "numeric":
        return sa.Numeric(column["precision"], column["scale"])
    return {"json": sa.JSON, "boolean": sa.Boolean, "datetime": sa.DateTime,
            "date": sa.Date, "time": sa.Time, "integer": sa.BigInteger,
            "float": sa.Float}[kind]()


def verify_restore(connection, bundle_path: Path):
    bundle = load_bundle(bundle_path)
    if (connection.dialect.name == bundle["source_dialect"]
            and connection.engine.url.database == bundle["source_database"]):
        raise RuntimeError("Restore destination must be an isolated database, different from the source")
    present = set(sa.inspect(connection).get_table_names())
    collision = present & {entry["name"] for entry in bundle["tables"]}
    if collision:
        raise RuntimeError(f"Restore destination already contains archive tables: {', '.join(sorted(collision))}")
    for entry in bundle["tables"]:
        table = sa.Table(entry["name"], sa.MetaData(), *[
            sa.Column(c["name"], _restore_type(c, connection.dialect), nullable=c["nullable"], primary_key=c["primary_key"])
            for c in entry["columns"]])
        table.create(connection)
        for offset in range(0, len(entry["rows"]), 500):
            rows = [dict(zip(table.columns.keys(), map(_decode, values)))
                    for values in entry["rows"][offset:offset + 500]]
            connection.execute(table.insert(), rows)
        rows = _rows(connection, table)
        if len(rows) != entry["row_count"] or _sha(rows) != entry["sha256"]:
            raise RuntimeError(f"Restore row checksum mismatch: {entry['name']}")
    # Persist restored rows before recording evidence. A caller rollback must
    # never leave a verification marker for data that did not survive.
    connection.commit()
    verification = {"bundle_sha256": bundle["bundle_sha256"], "dialect": connection.dialect.name,
                    "database": connection.engine.url.database,
                    "verified_at": datetime.now(timezone.utc).isoformat()}
    bundle["restore_verifications"].append(verification)
    bundle_path.write_text(_canonical(bundle) + "\n", encoding="utf-8")
    return verification


def assert_archive_matches(connection, table_names, *, archive_path=None):
    path = archive_path or os.environ.get(ARCHIVE_ENV)
    if not path:
        raise RuntimeError(f"Populated retirement requires a restore-verified archive; set {ARCHIVE_ENV}")
    bundle = load_bundle(Path(path))
    if not any(record.get("bundle_sha256") == bundle["bundle_sha256"]
               and record.get("dialect") == connection.dialect.name
               for record in bundle.get("restore_verifications", [])):
        raise RuntimeError(f"Retirement archive has no {connection.dialect.name} restore verification")
    archived = {entry["name"]: entry for entry in bundle["tables"]}
    for name in table_names:
        if name not in archived:
            raise RuntimeError(f"Retirement archive missing table: {name}")
        table = sa.Table(name, sa.MetaData(), autoload_with=connection, resolve_fks=False)
        columns = [_column_descriptor(c, connection.dialect) for c in table.columns]
        rows = _rows(connection, table)
        evidence = archived[name]
        if columns != evidence["columns"] or len(rows) != evidence["row_count"] or _sha(rows) != evidence["sha256"]:
            raise RuntimeError(f"Live table changed since retirement archive: {name}")
    return bundle["bundle_sha256"]
