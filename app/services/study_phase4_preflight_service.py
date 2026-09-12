"""Read-only Phase 4 schema, lineage, and rollout preflight evidence."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

import sqlalchemy as sa
from sqlalchemy.orm import aliased

from app.services import study_artifact_service
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.note import Note
from models.review_event import ReviewEvent
from models.study_session_batch import StudySessionBatch
from models.user import User


PREFLIGHT_SCHEMA_VERSION = "study-phase4-preflight.v1"
CANONICAL_QUEUE_LABELS = frozenset({"new", "learning", "review", "relearning"})
COMPATIBILITY_QUEUE_ALIASES = frozenset({"learn", "relearn"})
ACTIVE_IMPORT_STATUSES = frozenset({"preflighting", "note_types_ready", "importing"})
RELEVANT_TABLES = (
    "alembic_version",
    "card_progress",
    "cards",
    "connect_import_sessions",
    "connect_review_event_refs",
    "connect_source_card_refs",
    "connect_source_note_refs",
    "deck_clone_added_notes",
    "deck_clone_deck_maps",
    "deck_installs",
    "deck_marketplace_items",
    "note_type_installs",
    "notes",
    "review_events",
    "study_session_batches",
    "study_session_cards",
    "study_session_commits",
    "study_sessions",
)
RAW_PROGRESS_STATE_FIELDS = (
    "queue",
    "step_index",
    "due_at",
    "due_day",
    "interval_days",
    "interval_days_raw",
    "is_suspended",
    "is_buried",
    "buried_until_day",
    "review_kind",
    "scheduler_mode",
    "ease_factor",
    "memory_stability",
    "memory_difficulty",
    "suspension_reason",
    "last_leech_at",
    "last_leech_lapses",
    "reps",
    "lapses",
    "last_reviewed_at",
    "revision",
)
_ALLOWED_READ_PRIVILEGES = frozenset({"SELECT", "SHOW VIEW", "USAGE"})

WRITER_INVENTORY = (
    {
        "id": "native_review_rest_and_mcp",
        "entrypoint": "app.services.study_service.execute_native_review_command",
        "writes": ["card_progress", "review_events"],
        "transaction_owner": "execute_native_review_command",
        "atomic_unit": "one native review command",
        "locking": "CardProgress row FOR UPDATE; create-on-miss race retry",
        "savepoint": "none",
    },
    {
        "id": "synchronous_session_commit",
        "entrypoint": "app.services.study_session_service.commit_study_session",
        "writes": [
            "card_progress",
            "review_events",
            "study_session_commits",
            "study_sessions",
        ],
        "transaction_owner": "commit_study_session",
        "atomic_unit": "one complete study-session commit",
        "locking": "StudySession and sorted touched CardProgress rows FOR UPDATE",
        "savepoint": "none",
    },
    {
        "id": "asynchronous_session_worker",
        "entrypoint": "app.services.study_worker_service.process_single_study_batch",
        "writes": [
            "card_progress",
            "review_events",
            "study_session_batches",
            "study_session_commits",
            "study_sessions",
        ],
        "transaction_owner": "process_single_study_batch",
        "atomic_unit": "one durable batch delivery or one recorded failure",
        "locking": "StudySessionBatch/StudySession and sorted CardProgress rows FOR UPDATE",
        "savepoint": "none",
    },
    {
        "id": "connect_card_import",
        "entrypoint": "app.services.connect.import_cards.import_cards",
        "writes": [
            "cards",
            "card_progress",
            "connect_source_card_refs",
            "connect_source_note_refs",
        ],
        "transaction_owner": "import_cards",
        "atomic_unit": "one package request with per-note partial success",
        "locking": "source identity rows guarded by uniqueness and lookup",
        "savepoint": "one nested transaction per imported note",
    },
    {
        "id": "connect_progress_snapshot",
        "entrypoint": "app.services.anki_sync_service.import_progress",
        "writes": ["card_progress", "connect_source_card_refs"],
        "transaction_owner": "app.api.v1.flashcards.anki_imports._upload_sync_package",
        "atomic_unit": "one package upload with per-record disposition",
        "locking": "CardProgress row FOR UPDATE",
        "savepoint": "one nested transaction per progress record",
    },
    {
        "id": "connect_review_history",
        "entrypoint": "app.services.anki_sync_service.import_reviews",
        "writes": ["review_events", "connect_review_event_refs"],
        "transaction_owner": "app.api.v1.flashcards.anki_imports._upload_sync_package",
        "atomic_unit": "one package upload with per-card atomic review history",
        "locking": "ConnectReviewEventRef and ReviewEvent identity rows FOR UPDATE",
        "savepoint": "one nested transaction per source card",
    },
    {
        "id": "deck_progress_reset",
        "entrypoint": "app.services.deck_management_service.reset_deck_progress",
        "writes": ["card_progress", "study_sessions"],
        "transaction_owner": "reset_deck_progress",
        "atomic_unit": "one learner/deck-subtree reset",
        "locking": "affected open sessions FOR UPDATE before bulk progress delete",
        "savepoint": "none",
    },
    {
        "id": "deck_subtree_delete",
        "entrypoint": "app.services.deck_management_service.delete_deck_subtree",
        "writes": ["notes", "cards", "card_progress", "review_events", "deck_installs"],
        "transaction_owner": "delete_deck_subtree",
        "atomic_unit": "one subtree delete or detach operation",
        "locking": "affected installs FOR UPDATE on destructive branches",
        "savepoint": "none",
    },
    {
        "id": "browse_card_delete",
        "entrypoint": "app.services.browse_card_service.delete_browse_card(s)_batch",
        "writes": ["cards", "notes", "card_progress_via_fk_cascade"],
        "transaction_owner": "browse-card delete service",
        "atomic_unit": "one card delete or one selected-card batch",
        "locking": "authorization-scoped entity reads; FK cascade for progress",
        "savepoint": "none",
    },
    {
        "id": "mcp_note_delete",
        "entrypoint": "app.services.mcp.note_tools.delete_note/batch_delete_notes",
        "writes": ["notes", "cards", "card_progress"],
        "transaction_owner": "MCP note delete tool",
        "atomic_unit": "one note or one requested note batch",
        "locking": "authorization-scoped reads; explicit bulk progress delete",
        "savepoint": "none",
    },
    {
        "id": "legacy_clone_cutover_rekey",
        "entrypoint": "app.services.share.cutover.cutover_clone_model_to_overlay_only",
        "writes": ["card_progress", "notes", "deck_installs", "clone_overlay_tables"],
        "transaction_owner": "startup maintenance or clone-cutover-overlay CLI caller",
        "atomic_unit": "outer startup/CLI transaction with per-install isolation",
        "locking": "progress merge/rekey resolves source and legacy-local contributors",
        "savepoint": "one nested transaction per DeckInstall",
    },
    {
        "id": "seed_replace",
        "entrypoint": "app.services.seeding_service seed commands",
        "writes": ["notes", "cards", "card_progress"],
        "transaction_owner": "registered seed CLI command",
        "atomic_unit": "one seed command transaction",
        "locking": "none; operator-only maintenance path",
        "savepoint": "none",
    },
    {
        "id": "standalone_template_seed_replace",
        "entrypoint": "scripts.seed_flama_template.seed_template",
        "writes": ["notes", "cards", "card_progress"],
        "transaction_owner": "seed_template script",
        "atomic_unit": "explicit script commit stages",
        "locking": "none; operator-only maintenance path",
        "savepoint": "none",
    },
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def analyze_mysql_grants(grants: Iterable[str]) -> dict[str, Any]:
    """Classify grants without returning principal names or raw grant text."""

    normalized = [str(item or "").strip().upper() for item in grants]
    privilege_tokens: set[str] = set()
    has_select = False
    has_grant_option = False
    unparsed_grant_rows = 0
    for grant in normalized:
        match = re.search(r"\bGRANT\s+(.+?)\s+ON\s+", grant)
        if match:
            privilege_tokens.update(
                token.strip() for token in match.group(1).split(",") if token.strip()
            )
        else:
            unparsed_grant_rows += 1
        has_select = has_select or "SELECT" in privilege_tokens
        has_grant_option = has_grant_option or "WITH GRANT OPTION" in grant

    disallowed = sorted(privilege_tokens - _ALLOWED_READ_PRIVILEGES)
    if has_grant_option and "GRANT OPTION" not in disallowed:
        disallowed.append("GRANT OPTION")
    if unparsed_grant_rows:
        disallowed.append("UNPARSED OR ROLE GRANT")
    disallowed = sorted(disallowed)
    return {
        "grant_row_count": len(normalized),
        "unparsed_grant_row_count": unparsed_grant_rows,
        "has_select": has_select,
        "disallowed_privileges": disallowed,
        "select_only_verified": bool(
            has_select and not disallowed and not unparsed_grant_rows
        ),
    }


def collect_connection_safety() -> dict[str, Any]:
    """Verify MySQL audit credentials before reading application tables."""

    dialect = str(db.engine.dialect.name or "").lower()
    if not dialect.startswith("mysql"):
        return {
            "dialect": dialect,
            "evidence_scope": "non-mysql-fixture",
            "select_only_verified": False,
            "current_mysql_evidence": False,
        }

    identity = db.session.execute(
        sa.text(
            "SELECT CURRENT_USER() AS connected_principal, DATABASE() AS database_name, "
            "@@version AS server_version, @@sql_mode AS sql_mode, "
            "@@character_set_database AS database_charset, "
            "@@collation_database AS database_collation, @@time_zone AS time_zone"
        )
    ).mappings().one()
    grant_rows = db.session.execute(sa.text("SHOW GRANTS FOR CURRENT_USER")).all()
    grants = [str(row[0]) for row in grant_rows]
    grant_analysis = analyze_mysql_grants(grants)
    if not grant_analysis["select_only_verified"]:
        raise RuntimeError(
            "Audit refused before application-table inspection: the MySQL principal "
            "is not verified SELECT-only."
        )

    principal = str(identity.get("connected_principal") or "")
    database_name = str(identity.get("database_name") or "")
    return {
        "dialect": dialect,
        "evidence_scope": "current-mysql-select-only",
        "select_only_verified": True,
        "current_mysql_evidence": True,
        "principal_sha256": _sha256_text(principal),
        "database_sha256": _sha256_text(database_name),
        "server_version": str(identity.get("server_version") or ""),
        "sql_mode": sorted(
            item.strip()
            for item in str(identity.get("sql_mode") or "").split(",")
            if item.strip()
        ),
        "database_charset": str(identity.get("database_charset") or ""),
        "database_collation": str(identity.get("database_collation") or ""),
        "time_zone": str(identity.get("time_zone") or ""),
        **grant_analysis,
    }


def _run_git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_inventory() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = repo_root / "migrations" / "versions"
    migration_paths = sorted(migrations_dir.glob("*.py"), key=lambda item: item.name)
    migration_text = {
        path.name: path.read_text(encoding="utf-8") for path in migration_paths
    }
    mentions = {
        table: sorted(
            name for name, body in migration_text.items() if table in body
        )
        for table in RELEVANT_TABLES
    }

    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(repo_root / "migrations" / "alembic.ini"))
        config.set_main_option("script_location", str(repo_root / "migrations"))
        repository_heads = sorted(ScriptDirectory.from_config(config).get_heads())
    except Exception as exc:  # pragma: no cover - defensive packaging fallback
        repository_heads = []
        head_error = type(exc).__name__
    else:
        head_error = None

    manifest_paths = [
        repo_root / "app" / "cli.py",
        repo_root / "app" / "settings.py",
        repo_root / "app" / "services" / "anki_sync_service.py",
        repo_root / "app" / "services" / "browse_card_service.py",
        repo_root / "app" / "services" / "deck_management_service.py",
        repo_root / "app" / "services" / "flama_connect_package_service.py",
        repo_root / "app" / "services" / "seeding_service.py",
        repo_root / "app" / "services" / "study_service.py",
        repo_root / "app" / "services" / "study_architecture_audit_service.py",
        repo_root / "app" / "services" / "study_phase4_preflight_service.py",
        repo_root / "app" / "services" / "study_session_config.py",
        repo_root / "app" / "services" / "study_session_service.py",
        repo_root / "app" / "services" / "study_worker_service.py",
        repo_root / "app" / "services" / "connect" / "import_cards.py",
        repo_root / "app" / "services" / "mcp" / "note_tools.py",
        repo_root / "app" / "services" / "share" / "cutover.py",
        repo_root / "models" / "card_progress.py",
        repo_root / "models" / "review_event.py",
        repo_root / "models" / "study_session_batch.py",
        repo_root / "scripts" / "run_phase4_preflight_bundle.py",
        repo_root / "scripts" / "seed_flama_template.py",
        repo_root / "wsgi_audit.py",
        *migration_paths,
    ]
    file_hashes = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "sha256": _file_sha256(path),
        }
        for path in manifest_paths
        if path.is_file()
    ]
    manifest_sha256 = _sha256_text(
        json.dumps(file_hashes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    status = _run_git(repo_root, "status", "--porcelain")
    status_lines = sorted(line for line in (status or "").splitlines() if line)
    return {
        "git_commit": os.getenv("FLAMA_BUILD_COMMIT")
        or _run_git(repo_root, "rev-parse", "HEAD"),
        "git_branch": _run_git(repo_root, "branch", "--show-current"),
        "worktree_dirty": bool(status_lines),
        "worktree_change_count": len(status_lines),
        "worktree_status_sha256": _sha256_text("\n".join(status_lines)),
        "repository_alembic_heads": repository_heads,
        "repository_alembic_head_error": head_error,
        "migration_file_count": len(migration_paths),
        "migration_mentions": mentions,
        "study_session_batches_migration_declared": bool(
            mentions.get("study_session_batches")
        ),
        "code_manifest": file_hashes,
        "code_manifest_sha256": manifest_sha256,
    }


def _default_description(default: Any) -> str | None:
    if default is None:
        return None
    argument = getattr(default, "arg", default)
    if callable(argument):
        module = getattr(argument, "__module__", "")
        name = getattr(argument, "__qualname__", getattr(argument, "__name__", "callable"))
        return f"python:{module}.{name}".strip(".")
    return str(argument)


def _model_table_contract(
    table: sa.Table,
    *,
    dialect: sa.engine.Dialect,
) -> dict[str, Any]:
    foreign_keys = sorted(
        {
            (
                tuple(constraint.column_keys),
                next(iter(constraint.elements)).column.table.name,
                tuple(element.column.name for element in constraint.elements),
                str(constraint.ondelete or "").upper(),
            )
            for constraint in table.foreign_key_constraints
        }
    )
    unique_sets = sorted(
        {
            tuple(constraint.columns.keys())
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        | {
            tuple(index.columns.keys())
            for index in table.indexes
            if bool(index.unique)
        }
    )
    indexes = sorted(
        {
            (tuple(index.columns.keys()), bool(index.unique))
            for index in table.indexes
            if not bool(index.unique)
        }
    )
    return {
        "columns": [
            {
                "name": column.name,
                "type": str(column.type.compile(dialect=dialect)),
                "nullable": bool(column.nullable),
                "client_default": _default_description(column.default),
                "server_default": _default_description(column.server_default),
            }
            for column in table.columns
        ],
        "primary_key": list(table.primary_key.columns.keys()),
        "foreign_keys": [list(item) for item in foreign_keys],
        "unique_column_sets": [list(item) for item in unique_sets],
        "indexes": [[list(columns), unique] for columns, unique in indexes],
    }


def _database_table_contract(inspector: sa.Inspector, table_name: str) -> dict[str, Any]:
    columns = inspector.get_columns(table_name)
    foreign_keys = sorted(
        {
            (
                tuple(item.get("constrained_columns") or ()),
                str(item.get("referred_table") or ""),
                tuple(item.get("referred_columns") or ()),
                str((item.get("options") or {}).get("ondelete") or "").upper(),
            )
            for item in inspector.get_foreign_keys(table_name)
        }
    )
    indexes_raw = inspector.get_indexes(table_name)
    unique_sets = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints(table_name)
    } | {
        tuple(item.get("column_names") or ())
        for item in indexes_raw
        if bool(item.get("unique"))
    }
    indexes = sorted(
        {
            (tuple(item.get("column_names") or ()), bool(item.get("unique")))
            for item in indexes_raw
            if not bool(item.get("unique"))
        }
    )
    try:
        table_options = inspector.get_table_options(table_name)
    except NotImplementedError:
        table_options = {}
    return {
        "columns": [
            {
                "name": str(column.get("name") or ""),
                "type": str(column.get("type") or ""),
                "nullable": bool(column.get("nullable")),
                "default": None
                if column.get("default") is None
                else str(column.get("default")),
            }
            for column in columns
        ],
        "primary_key": list(
            (inspector.get_pk_constraint(table_name) or {}).get("constrained_columns")
            or ()
        ),
        "foreign_keys": [list(item) for item in foreign_keys],
        "unique_column_sets": [list(item) for item in sorted(unique_sets)],
        "indexes": [[list(column_names), unique] for column_names, unique in indexes],
        "table_options": {
            str(key): str(value) for key, value in sorted(table_options.items())
        },
    }


def _normalized_type(value: str) -> str:
    normalized = str(value or "").strip().upper()
    normalized = re.sub(
        r"\s+COLLATE\s+(?:\"[^\"]+\"|'[^']+'|`[^`]+`|[A-Z0-9_]+)\s*$",
        "",
        normalized,
    )
    normalized = re.sub(r"\s+", "", normalized)
    if normalized in {"BOOL", "BOOLEAN", "TINYINT", "TINYINT(1)"}:
        return "BOOLEAN"
    return normalized


def _normalized_server_default(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    normalized = re.sub(r"\s+", "", normalized)
    if normalized.endswith("()"):
        normalized = normalized[:-2]
    return normalized


def _actionable_indexes(contract: dict[str, Any]) -> list[list[Any]]:
    """Exclude indexes MySQL must synthesize to support declared foreign keys."""

    foreign_key_columns = {
        tuple(item[0]) for item in contract.get("foreign_keys", []) if item
    }
    return [
        item
        for item in contract.get("indexes", [])
        if tuple(item[0]) not in foreign_key_columns
    ]


def _schema_inventory(repository: dict[str, Any]) -> dict[str, Any]:
    inspector = sa.inspect(db.engine)
    actual_tables = set(inspector.get_table_names())
    database_heads: list[str] = []
    if "alembic_version" in actual_tables:
        database_heads = sorted(
            str(row[0])
            for row in db.session.execute(
                sa.text("SELECT version_num FROM alembic_version ORDER BY version_num")
            ).all()
        )

    table_inventory: dict[str, Any] = {}
    drift: list[dict[str, Any]] = []
    default_observations: list[dict[str, Any]] = []
    for table_name in RELEVANT_TABLES:
        model_table = db.metadata.tables.get(table_name)
        model_contract = (
            _model_table_contract(model_table, dialect=db.engine.dialect)
            if model_table is not None
            else None
        )
        database_contract = (
            _database_table_contract(inspector, table_name)
            if table_name in actual_tables
            else None
        )
        table_inventory[table_name] = {
            "model_declared": model_contract is not None,
            "database_present": database_contract is not None,
            "migration_files": repository["migration_mentions"].get(table_name, []),
            "model": model_contract,
            "database": database_contract,
        }
        if model_contract is None or database_contract is None:
            if model_contract is not None or database_contract is not None:
                if table_name != "alembic_version":
                    drift.append(
                        {
                            "table": table_name,
                            "kind": "table_presence",
                            "model_declared": model_contract is not None,
                            "database_present": database_contract is not None,
                        }
                    )
            continue

        model_columns = {item["name"] for item in model_contract["columns"]}
        database_columns = {item["name"] for item in database_contract["columns"]}
        if model_columns != database_columns:
            drift.append(
                {
                    "table": table_name,
                    "kind": "column_set",
                    "missing_in_database": sorted(model_columns - database_columns),
                    "unexpected_in_database": sorted(database_columns - model_columns),
                }
            )
        model_columns_by_name = {
            item["name"]: item for item in model_contract["columns"]
        }
        database_columns_by_name = {
            item["name"]: item for item in database_contract["columns"]
        }
        for column_name in sorted(model_columns.intersection(database_columns)):
            model_column = model_columns_by_name[column_name]
            database_column = database_columns_by_name[column_name]
            if (
                _normalized_type(model_column["type"])
                != _normalized_type(database_column["type"])
                or model_column["nullable"] != database_column["nullable"]
            ):
                drift.append(
                    {
                        "table": table_name,
                        "column": column_name,
                        "kind": "column_type_or_nullability",
                        "model": {
                            "type": model_column["type"],
                            "nullable": model_column["nullable"],
                        },
                        "database": {
                            "type": database_column["type"],
                            "nullable": database_column["nullable"],
                        },
                    }
                )
            client_default = model_column["client_default"]
            model_server_default = model_column["server_default"]
            database_default = database_column["default"]
            if any(
                value is not None
                for value in (client_default, model_server_default, database_default)
            ):
                server_default_matches = (
                    _normalized_server_default(model_server_default)
                    == _normalized_server_default(database_default)
                )
                default_observations.append(
                    {
                        "table": table_name,
                        "column": column_name,
                        "client_default": client_default,
                        "model_server_default": model_server_default,
                        "database_default": database_default,
                        "server_default_matches_database": server_default_matches,
                    }
                )
                if not server_default_matches:
                    drift.append(
                        {
                            "table": table_name,
                            "column": column_name,
                            "kind": "server_default",
                            "model": model_server_default,
                            "database": database_default,
                        }
                    )
        for key in ("primary_key", "foreign_keys", "unique_column_sets"):
            if model_contract[key] != database_contract[key]:
                drift.append(
                    {
                        "table": table_name,
                        "kind": key,
                        "model": model_contract[key],
                        "database": database_contract[key],
                    }
                )
        model_indexes = _actionable_indexes(model_contract)
        database_indexes = _actionable_indexes(database_contract)
        if model_indexes != database_indexes:
            drift.append(
                {
                    "table": table_name,
                    "kind": "indexes",
                    "model": model_indexes,
                    "database": database_indexes,
                }
            )

    repository_heads = repository["repository_alembic_heads"]
    return {
        "dialect": str(db.engine.dialect.name or ""),
        "database_alembic_heads": database_heads,
        "repository_alembic_heads": repository_heads,
        "alembic_head_match": (
            database_heads == repository_heads if database_heads else None
        ),
        "study_session_batches_database_present": (
            "study_session_batches" in actual_tables
        ),
        "study_session_batches_migration_declared": repository[
            "study_session_batches_migration_declared"
        ],
        "drift_count": len(drift),
        "drift": drift,
        "default_observations": default_observations,
        "tables": table_inventory,
    }


def _status_distribution(model: type[Any]) -> dict[str, int]:
    return {
        str(status if status is not None else "<null>"): int(count or 0)
        for status, count in (
            db.session.query(model.status, db.func.count(model.id))
            .group_by(model.status)
            .order_by(model.status.asc())
            .all()
        )
    }


def _progress_preflight(*, observed_at: datetime, actual_tables: set[str]) -> dict[str, Any]:
    total_progress = int(CardProgress.query.count())
    valid_progress = int(
        db.session.query(db.func.count(CardProgress.id))
        .join(User, User.id == CardProgress.user_id)
        .join(Card, Card.id == CardProgress.card_id)
        .join(Note, Note.id == Card.note_id)
        .scalar()
        or 0
    )
    unresolvable_progress = total_progress - valid_progress
    null_learner_subjects = int(
        CardProgress.query.filter(CardProgress.user_id.is_(None)).count()
    )
    missing_learner_subjects = int(
        db.session.query(db.func.count(CardProgress.id))
        .outerjoin(User, User.id == CardProgress.user_id)
        .filter(CardProgress.user_id.isnot(None), User.id.is_(None))
        .scalar()
        or 0
    )
    null_card_subjects = int(
        CardProgress.query.join(User, User.id == CardProgress.user_id)
        .filter(CardProgress.card_id.is_(None))
        .count()
    )
    missing_card_subjects = int(
        db.session.query(db.func.count(CardProgress.id))
        .join(User, User.id == CardProgress.user_id)
        .outerjoin(Card, Card.id == CardProgress.card_id)
        .filter(CardProgress.card_id.isnot(None), Card.id.is_(None))
        .scalar()
        or 0
    )
    null_note_subjects = int(
        db.session.query(db.func.count(CardProgress.id))
        .join(User, User.id == CardProgress.user_id)
        .join(Card, Card.id == CardProgress.card_id)
        .filter(Card.note_id.is_(None))
        .scalar()
        or 0
    )
    missing_note_subjects = int(
        db.session.query(db.func.count(CardProgress.id))
        .join(User, User.id == CardProgress.user_id)
        .join(Card, Card.id == CardProgress.card_id)
        .outerjoin(Note, Note.id == Card.note_id)
        .filter(Card.note_id.isnot(None), Note.id.is_(None))
        .scalar()
        or 0
    )

    queue_distribution = {
        str(label if label is not None else "<null>"): int(count or 0)
        for label, count in (
            db.session.query(
                db.func.lower(CardProgress.queue), db.func.count(CardProgress.id)
            )
            .group_by(db.func.lower(CardProgress.queue))
            .order_by(db.func.lower(CardProgress.queue).asc())
            .all()
        )
    }
    canonical_queue_rows = sum(
        count for label, count in queue_distribution.items() if label in CANONICAL_QUEUE_LABELS
    )
    alias_queue_rows = sum(
        count
        for label, count in queue_distribution.items()
        if label in COMPATIBILITY_QUEUE_ALIASES
    )
    unknown_queue_rows = total_progress - canonical_queue_rows - alias_queue_rows

    scheduler_mode_distribution = {
        str(label if label is not None else "<null>"): int(count or 0)
        for label, count in (
            db.session.query(
                db.func.lower(CardProgress.scheduler_mode),
                db.func.count(CardProgress.id),
            )
            .group_by(db.func.lower(CardProgress.scheduler_mode))
            .order_by(db.func.lower(CardProgress.scheduler_mode).asc())
            .all()
        )
    }
    due_shape_rows = {
        "both_null": int(
            CardProgress.query.filter(
                CardProgress.due_at.is_(None), CardProgress.due_day.is_(None)
            ).count()
        ),
        "time_only": int(
            CardProgress.query.filter(
                CardProgress.due_at.isnot(None), CardProgress.due_day.is_(None)
            ).count()
        ),
        "day_only": int(
            CardProgress.query.filter(
                CardProgress.due_at.is_(None), CardProgress.due_day.isnot(None)
            ).count()
        ),
        "both_present": int(
            CardProgress.query.filter(
                CardProgress.due_at.isnot(None), CardProgress.due_day.isnot(None)
            ).count()
        ),
    }

    card_refs: dict[tuple[int, str], list[str]] = defaultdict(list)
    for row in (
        db.session.query(
            ConnectSourceCardRef.user_id,
            ConnectSourceCardRef.card_id,
            ConnectSourceCardRef.source_key,
            ConnectSourceCardRef.external_card_id,
            ConnectSourceCardRef.external_note_id,
            ConnectSourceCardRef.source_ord,
        )
        .order_by(
            ConnectSourceCardRef.user_id.asc(),
            ConnectSourceCardRef.card_id.asc(),
            ConnectSourceCardRef.source_key.asc(),
            ConnectSourceCardRef.external_card_id.asc(),
        )
        .yield_per(1000)
    ):
        key = (int(row.user_id), str(row.card_id))
        card_refs[key].append(
            study_artifact_service.canonical_digest(
                {
                    "source_key": row.source_key,
                    "external_card_id": row.external_card_id,
                    "external_note_id": row.external_note_id,
                    "source_ord": row.source_ord,
                }
            )
        )

    note_refs: dict[tuple[int, str], list[str]] = defaultdict(list)
    for row in (
        db.session.query(
            ConnectSourceNoteRef.user_id,
            ConnectSourceNoteRef.note_id,
            ConnectSourceNoteRef.source_key,
            ConnectSourceNoteRef.external_note_id,
            ConnectSourceNoteRef.content_hash,
        )
        .order_by(
            ConnectSourceNoteRef.user_id.asc(),
            ConnectSourceNoteRef.note_id.asc(),
            ConnectSourceNoteRef.source_key.asc(),
            ConnectSourceNoteRef.external_note_id.asc(),
        )
        .yield_per(1000)
    ):
        key = (int(row.user_id), str(row.note_id))
        note_refs[key].append(
            study_artifact_service.canonical_digest(
                {
                    "source_key": row.source_key,
                    "external_note_id": row.external_note_id,
                    "content_hash": row.content_hash,
                }
            )
        )

    review_refs: dict[int, list[str]] = defaultdict(list)
    for row in (
        db.session.query(
            ConnectReviewEventRef.review_event_id,
            ConnectReviewEventRef.source_key,
            ConnectReviewEventRef.external_review_id,
            ConnectReviewEventRef.external_card_id,
            ConnectReviewEventRef.payload_hash,
            ConnectReviewEventRef.status,
        )
        .filter(ConnectReviewEventRef.review_event_id.isnot(None))
        .order_by(
            ConnectReviewEventRef.review_event_id.asc(),
            ConnectReviewEventRef.source_key.asc(),
            ConnectReviewEventRef.external_review_id.asc(),
        )
        .yield_per(1000)
    ):
        review_refs[int(row.review_event_id)].append(
            study_artifact_service.canonical_digest(
                {
                    "source_key": row.source_key,
                    "external_review_id": row.external_review_id,
                    "external_card_id": row.external_card_id,
                    "payload_hash": row.payload_hash,
                    "status": row.status,
                }
            )
        )

    installed_sources = {
        (int(user_id), int(source_deck_id))
        for user_id, source_deck_id in db.session.query(
            DeckInstall.user_id, DeckInstall.source_deck_id
        ).filter(DeckInstall.source_deck_id.isnot(None))
    }
    installed_sources.update(
        {
            (int(user_id), int(source_deck_id))
            for user_id, source_deck_id in (
                db.session.query(
                    DeckInstall.user_id,
                    DeckCloneDeckMap.source_deck_id,
                )
                .join(
                    DeckCloneDeckMap,
                    DeckCloneDeckMap.deck_install_id == DeckInstall.id,
                )
                .filter(DeckCloneDeckMap.source_deck_id.isnot(None))
                .all()
            )
        }
    )
    installed_local_notes = {
        (int(user_id), str(note_id))
        for user_id, note_id in (
            db.session.query(DeckInstall.user_id, DeckCloneAddedNote.note_id)
            .join(
                DeckCloneAddedNote,
                DeckCloneAddedNote.deck_install_id == DeckInstall.id,
            )
            .all()
        )
    }
    pointed_events = {
        int(event_id): (int(user_id), str(card_id))
        for event_id, user_id, card_id in (
            db.session.query(ReviewEvent.id, ReviewEvent.user_id, ReviewEvent.card_id)
            .join(
                CardProgress,
                CardProgress.last_review_event_id == ReviewEvent.id,
            )
            .distinct()
            .all()
        )
    }

    fan_in = {
        "groups": 0,
        "rows": 0,
        "state_equivalent_groups": 0,
        "state_divergent_groups": 0,
        "lineage_uniform_groups": 0,
        "lineage_divergent_groups": 0,
        "state_equivalent_lineage_uniform_groups": 0,
        "state_equivalent_lineage_divergent_groups": 0,
        "state_divergent_lineage_uniform_groups": 0,
        "state_divergent_lineage_divergent_groups": 0,
    }
    subject_groups = {"total": 0, "single": 0, "fan_in": 0}
    context_rows = {
        "owned": 0,
        "installed_source": 0,
        "installed_local": 0,
        "unclassified": 0,
    }
    context_membership_rows = {
        "owned": 0,
        "installed_source": 0,
        "installed_local": 0,
        "with_any": 0,
        "single": 0,
        "multiple": 0,
        "none": 0,
    }
    state_samples: dict[str, list[str]] = {
        "state_divergent": [],
        "lineage_divergent": [],
    }

    current_group: tuple[int, str] | None = None
    state_signatures: set[str] = set()
    lineage_signatures: set[str] = set()
    group_count = 0
    progress_contributor_keys: set[tuple[int, str]] = set()
    progress_subject_keys: set[tuple[int, str]] = set()
    pointed_event_ids: set[int] = set()
    valid_pointer_rows_with_connect_ref = 0
    disposition_rows = {"mirror_candidate": 0, "quarantine_candidate": 0}
    quarantine_reason_rows: dict[str, int] = defaultdict(int)
    group_quarantine_reasons: set[str] = set()

    def flush_group() -> None:
        nonlocal group_count
        if current_group is None or group_count == 0:
            return
        subject_groups["total"] += 1
        if group_count > 1:
            subject_groups["fan_in"] += 1
            group_quarantine_reasons.add("fan_in_requires_p4_02_disposition")
        else:
            subject_groups["single"] += 1
        if group_quarantine_reasons:
            disposition_rows["quarantine_candidate"] += group_count
            for reason in group_quarantine_reasons:
                quarantine_reason_rows[reason] += group_count
        else:
            disposition_rows["mirror_candidate"] += group_count
        if group_count <= 1:
            return
        fan_in["groups"] += 1
        fan_in["rows"] += group_count
        state_equivalent = len(state_signatures) == 1
        lineage_uniform = len(lineage_signatures) == 1
        state_key = "state_equivalent" if state_equivalent else "state_divergent"
        lineage_key = "lineage_uniform" if lineage_uniform else "lineage_divergent"
        fan_in[f"{state_key}_groups"] += 1
        fan_in[f"{lineage_key}_groups"] += 1
        fan_in[f"{state_key}_{lineage_key}_groups"] += 1
        sample = study_artifact_service.canonical_digest(
            {"user_id": current_group[0], "note_id": current_group[1]}
        )[:16]
        if not state_equivalent and len(state_samples["state_divergent"]) < 10:
            state_samples["state_divergent"].append(sample)
        if not lineage_uniform and len(state_samples["lineage_divergent"]) < 10:
            state_samples["lineage_divergent"].append(sample)

    progress_rows = (
        db.session.query(
            CardProgress,
            Card.note_id.label("note_id"),
            Note.user_id.label("note_owner_user_id"),
            Note.deck_id.label("note_deck_id"),
        )
        .join(User, User.id == CardProgress.user_id)
        .join(Card, Card.id == CardProgress.card_id)
        .join(Note, Note.id == Card.note_id)
        .order_by(
            CardProgress.user_id.asc(),
            Card.note_id.asc(),
            CardProgress.id.asc(),
        )
        .yield_per(1000)
    )
    for progress, note_id, note_owner_user_id, note_deck_id in progress_rows:
        group_key = (int(progress.user_id), str(note_id))
        if current_group != group_key:
            flush_group()
            current_group = group_key
            state_signatures = set()
            lineage_signatures = set()
            group_count = 0
            group_quarantine_reasons = set()

        state_material = {
            field: getattr(progress, field) for field in RAW_PROGRESS_STATE_FIELDS
        }
        progress_contributor_keys.add((int(progress.user_id), str(progress.card_id)))
        progress_subject_keys.add((int(progress.user_id), str(note_id)))
        if progress.last_review_event_id is not None:
            pointed_event_ids.add(int(progress.last_review_event_id))
        state_signatures.add(study_artifact_service.canonical_digest(state_material))
        lineage_signatures.add(
            study_artifact_service.canonical_digest(
                {
                    "last_review_event_id": progress.last_review_event_id,
                    "source_card_refs": sorted(
                        card_refs.get((int(progress.user_id), str(progress.card_id)), [])
                    ),
                    "source_note_refs": sorted(
                        note_refs.get((int(progress.user_id), str(note_id)), [])
                    ),
                    "last_review_event_refs": sorted(
                        review_refs.get(int(progress.last_review_event_id), [])
                        if progress.last_review_event_id is not None
                        else []
                    ),
                }
            )
        )
        group_count += 1

        is_installed_local = (
            int(progress.user_id),
            str(note_id),
        ) in installed_local_notes
        is_installed_source = note_deck_id is not None and (
            int(progress.user_id),
            int(note_deck_id),
        ) in installed_sources
        is_owned = int(note_owner_user_id) == int(progress.user_id)
        memberships = {
            "owned": is_owned,
            "installed_source": is_installed_source,
            "installed_local": is_installed_local,
        }
        membership_count = sum(1 for present in memberships.values() if present)
        for context_name, present in memberships.items():
            if present:
                context_membership_rows[context_name] += 1
        if membership_count:
            context_membership_rows["with_any"] += 1
            if membership_count > 1:
                context_membership_rows["multiple"] += 1
            else:
                context_membership_rows["single"] += 1
        else:
            context_membership_rows["none"] += 1

        if is_installed_local:
            context_rows["installed_local"] += 1
        elif is_installed_source:
            context_rows["installed_source"] += 1
        elif is_owned:
            context_rows["owned"] += 1
        else:
            context_rows["unclassified"] += 1
            group_quarantine_reasons.add("unclassified_progress_context")

        queue_label = str(progress.queue or "").strip().lower()
        if queue_label not in CANONICAL_QUEUE_LABELS | COMPATIBILITY_QUEUE_ALIASES:
            group_quarantine_reasons.add("unknown_queue")
        has_stability = progress.memory_stability is not None
        has_difficulty = progress.memory_difficulty is not None
        if has_stability != has_difficulty:
            group_quarantine_reasons.add("partial_memory_state")
        if progress.last_review_event_id is not None:
            pointed_lineage = pointed_events.get(int(progress.last_review_event_id))
            if pointed_lineage is None:
                group_quarantine_reasons.add("missing_last_review_event")
            elif pointed_lineage != (int(progress.user_id), str(progress.card_id)):
                group_quarantine_reasons.add("mismatched_last_review_event")
            elif review_refs.get(int(progress.last_review_event_id)):
                valid_pointer_rows_with_connect_ref += 1
    flush_group()

    pointed_event = aliased(ReviewEvent)
    pointer_base = (
        db.session.query(CardProgress.id)
        .outerjoin(
            pointed_event,
            pointed_event.id == CardProgress.last_review_event_id,
        )
    )
    null_pointer_rows = int(
        pointer_base.filter(CardProgress.last_review_event_id.is_(None)).count()
    )
    missing_pointer_rows = int(
        pointer_base.filter(
            CardProgress.last_review_event_id.isnot(None), pointed_event.id.is_(None)
        ).count()
    )
    mismatched_pointer_rows = int(
        pointer_base.filter(
            CardProgress.last_review_event_id.isnot(None),
            pointed_event.id.isnot(None),
            db.or_(
                pointed_event.user_id != CardProgress.user_id,
                pointed_event.card_id != CardProgress.card_id,
            ),
        ).count()
    )
    valid_pointer_rows = (
        total_progress - null_pointer_rows - missing_pointer_rows - mismatched_pointer_rows
    )

    timestamp_precision = {
        "rows_with_fractional_microseconds": 0,
        "max_fractional_digits": 0,
    }
    float_anomalies = 0
    timestamp_fields = (
        CardProgress.due_at,
        CardProgress.last_leech_at,
        CardProgress.last_reviewed_at,
        CardProgress.created_at,
        CardProgress.updated_at,
    )
    for row in db.session.query(
        CardProgress.id,
        *timestamp_fields,
        CardProgress.interval_days_raw,
        CardProgress.ease_factor,
        CardProgress.memory_stability,
        CardProgress.memory_difficulty,
    ).order_by(CardProgress.id.asc()).yield_per(1000):
        row_has_fraction = False
        for value in row[1:6]:
            microsecond = int(getattr(value, "microsecond", 0) or 0)
            if microsecond:
                row_has_fraction = True
                digits = len(f"{microsecond:06d}".rstrip("0"))
                timestamp_precision["max_fractional_digits"] = max(
                    timestamp_precision["max_fractional_digits"], digits
                )
        if row_has_fraction:
            timestamp_precision["rows_with_fractional_microseconds"] += 1
        for value in row[6:10]:
            if value is not None and not math.isfinite(float(value)):
                float_anomalies += 1

    batch_present = "study_session_batches" in actual_tables
    batch_status = _status_distribution(StudySessionBatch) if batch_present else {}
    batch_total: int | None = int(StudySessionBatch.query.count()) if batch_present else None
    active_batches: int | None = (
        int(StudySessionBatch.query.filter(StudySessionBatch.status == "enqueued").count())
        if batch_present
        else None
    )
    import_present = "connect_import_sessions" in actual_tables
    import_status = _status_distribution(ConnectImportSession) if import_present else {}
    active_imports: int | None = (
        int(
            ConnectImportSession.query.filter(
                ConnectImportSession.status.in_(ACTIVE_IMPORT_STATUSES),
                ConnectImportSession.expires_at >= observed_at,
            ).count()
        )
        if import_present
        else None
    )

    source_card_ref_rows = sum(len(values) for values in card_refs.values())
    matched_source_card_ref_rows = sum(
        len(values)
        for key, values in card_refs.items()
        if key in progress_contributor_keys
    )
    source_note_ref_rows = sum(len(values) for values in note_refs.values())
    matched_source_note_ref_rows = sum(
        len(values) for key, values in note_refs.items() if key in progress_subject_keys
    )
    review_event_ref_rows = int(ConnectReviewEventRef.query.count())
    null_review_event_ref_rows = int(
        ConnectReviewEventRef.query.filter(
            ConnectReviewEventRef.review_event_id.is_(None)
        ).count()
    )
    missing_review_event_ref_rows = int(
        db.session.query(db.func.count(ConnectReviewEventRef.id))
        .outerjoin(
            ReviewEvent,
            ReviewEvent.id == ConnectReviewEventRef.review_event_id,
        )
        .filter(
            ConnectReviewEventRef.review_event_id.isnot(None),
            ReviewEvent.id.is_(None),
        )
        .scalar()
        or 0
    )
    existing_review_event_ref_rows = (
        review_event_ref_rows
        - null_review_event_ref_rows
        - missing_review_event_ref_rows
    )

    accounting = {
        "source_partition": total_progress == valid_progress + unresolvable_progress,
        "unresolvable_reason_partition": unresolvable_progress
        == (
            null_learner_subjects
            + missing_learner_subjects
            + null_card_subjects
            + missing_card_subjects
            + null_note_subjects
            + missing_note_subjects
        ),
        "migration_disposition_partition": total_progress
        == (
            disposition_rows["mirror_candidate"]
            + disposition_rows["quarantine_candidate"]
            + unresolvable_progress
        ),
        "subject_group_partition": subject_groups["total"]
        == subject_groups["single"] + subject_groups["fan_in"],
        "subject_group_row_partition": valid_progress
        == subject_groups["single"] + fan_in["rows"],
        "context_partition": valid_progress == sum(context_rows.values()),
        "context_membership_presence_partition": valid_progress
        == context_membership_rows["with_any"] + context_membership_rows["none"],
        "context_membership_cardinality_partition": valid_progress
        == (
            context_membership_rows["none"]
            + context_membership_rows["single"]
            + context_membership_rows["multiple"]
        )
        and context_membership_rows["with_any"]
        == context_membership_rows["single"] + context_membership_rows["multiple"],
        "fan_in_state_partition": fan_in["groups"]
        == fan_in["state_equivalent_groups"] + fan_in["state_divergent_groups"],
        "fan_in_lineage_partition": fan_in["groups"]
        == fan_in["lineage_uniform_groups"] + fan_in["lineage_divergent_groups"],
        "last_review_pointer_partition": total_progress
        == (
            null_pointer_rows
            + valid_pointer_rows
            + missing_pointer_rows
            + mismatched_pointer_rows
        ),
        "due_shape_partition": total_progress == sum(due_shape_rows.values()),
        "queue_partition": total_progress
        == canonical_queue_rows + alias_queue_rows + unknown_queue_rows,
        "memory_state_partition": total_progress
        == (
            int(
                CardProgress.query.filter(
                    CardProgress.memory_stability.is_(None),
                    CardProgress.memory_difficulty.is_(None),
                ).count()
            )
            + int(
                CardProgress.query.filter(
                    CardProgress.memory_stability.isnot(None),
                    CardProgress.memory_difficulty.isnot(None),
                ).count()
            )
            + int(
                CardProgress.query.filter(
                    db.or_(
                        db.and_(
                            CardProgress.memory_stability.is_(None),
                            CardProgress.memory_difficulty.isnot(None),
                        ),
                        db.and_(
                            CardProgress.memory_stability.isnot(None),
                            CardProgress.memory_difficulty.is_(None),
                        ),
                    )
                ).count()
            )
        ),
        "source_card_ref_partition": source_card_ref_rows
        == matched_source_card_ref_rows
        + (source_card_ref_rows - matched_source_card_ref_rows),
        "source_note_ref_partition": source_note_ref_rows
        == matched_source_note_ref_rows
        + (source_note_ref_rows - matched_source_note_ref_rows),
        "review_event_ref_partition": review_event_ref_rows
        == (
            null_review_event_ref_rows
            + missing_review_event_ref_rows
            + existing_review_event_ref_rows
        ),
        "valid_pointer_connect_ref_partition": valid_pointer_rows
        == valid_pointer_rows_with_connect_ref
        + (valid_pointer_rows - valid_pointer_rows_with_connect_ref),
    }
    return {
        "total_card_progress_rows": total_progress,
        "valid_note_subject_rows": valid_progress,
        "unresolvable_subject_rows": unresolvable_progress,
        "unresolvable_subject_reasons": {
            "null_learner_user_id": null_learner_subjects,
            "missing_learner_user": missing_learner_subjects,
            "null_card_id": null_card_subjects,
            "missing_card": missing_card_subjects,
            "null_note_id": null_note_subjects,
            "missing_note": missing_note_subjects,
        },
        "migration_disposition_rows": {
            **disposition_rows,
            "unresolvable": unresolvable_progress,
            "quarantine_reason_rows_overlap_allowed": dict(
                sorted(quarantine_reason_rows.items())
            ),
        },
        "raw_state_fields": list(RAW_PROGRESS_STATE_FIELDS),
        "queue_distribution": queue_distribution,
        "canonical_queue_rows": canonical_queue_rows,
        "compatibility_alias_queue_rows": alias_queue_rows,
        "unknown_queue_rows": unknown_queue_rows,
        "scheduler_mode_distribution": scheduler_mode_distribution,
        "due_shape_rows": due_shape_rows,
        "hidden_state_rows": {
            "suspended": int(
                CardProgress.query.filter(CardProgress.is_suspended.is_(True)).count()
            ),
            "buried": int(
                CardProgress.query.filter(CardProgress.is_buried.is_(True)).count()
            ),
            "leech_marked": int(
                CardProgress.query.filter(CardProgress.last_leech_lapses > 0).count()
            ),
        },
        "memory_state_rows": {
            "both_null": int(
                CardProgress.query.filter(
                    CardProgress.memory_stability.is_(None),
                    CardProgress.memory_difficulty.is_(None),
                ).count()
            ),
            "both_present": int(
                CardProgress.query.filter(
                    CardProgress.memory_stability.isnot(None),
                    CardProgress.memory_difficulty.isnot(None),
                ).count()
            ),
            "partial": int(
                CardProgress.query.filter(
                    db.or_(
                        db.and_(
                            CardProgress.memory_stability.is_(None),
                            CardProgress.memory_difficulty.isnot(None),
                        ),
                        db.and_(
                            CardProgress.memory_stability.isnot(None),
                            CardProgress.memory_difficulty.is_(None),
                        ),
                    )
                ).count()
            ),
        },
        "timestamp_precision": timestamp_precision,
        "nonfinite_float_values": float_anomalies,
        "subject_groups": subject_groups,
        "fan_in": {**fan_in, "samples": state_samples},
        "context_rows": context_rows,
        "context_membership_rows": context_membership_rows,
        "last_review_event_lineage": {
            "null_pointer_rows": null_pointer_rows,
            "valid_pointer_rows": valid_pointer_rows,
            "missing_pointer_rows": missing_pointer_rows,
            "mismatched_user_or_card_rows": mismatched_pointer_rows,
            "contributors_with_source_card_ref": sum(
                1 for key in progress_contributor_keys if card_refs.get(key)
            ),
            "subjects_with_source_note_ref": sum(
                1 for key in progress_subject_keys if note_refs.get(key)
            ),
            "pointed_review_events_with_connect_ref": sum(
                1 for event_id in pointed_event_ids if review_refs.get(event_id)
            ),
            "valid_pointer_rows_with_connect_ref": (
                valid_pointer_rows_with_connect_ref
            ),
            "valid_pointer_rows_without_connect_ref": (
                valid_pointer_rows - valid_pointer_rows_with_connect_ref
            ),
        },
        "connect_reference_inventory": {
            "source_card_ref_rows": source_card_ref_rows,
            "matched_source_card_ref_rows": matched_source_card_ref_rows,
            "unmatched_source_card_ref_rows": (
                source_card_ref_rows - matched_source_card_ref_rows
            ),
            "source_note_ref_rows": source_note_ref_rows,
            "matched_source_note_ref_rows": matched_source_note_ref_rows,
            "unmatched_source_note_ref_rows": (
                source_note_ref_rows - matched_source_note_ref_rows
            ),
            "review_event_ref_rows": review_event_ref_rows,
            "null_review_event_ref_rows": null_review_event_ref_rows,
            "missing_review_event_ref_rows": missing_review_event_ref_rows,
            "existing_review_event_ref_rows": existing_review_event_ref_rows,
        },
        "active_rollout_inputs": {
            "study_session_batches_table_present": batch_present,
            "study_session_batch_rows": batch_total,
            "study_session_batch_status_distribution": batch_status,
            "active_enqueued_batches": active_batches,
            "connect_import_sessions_table_present": import_present,
            "connect_import_status_distribution": import_status,
            "active_connect_imports": active_imports,
        },
        "accounting": accounting,
    }


def build_phase4_preflight(
    *,
    observed_at: datetime,
    connection_safety: dict[str, Any],
) -> dict[str, Any]:
    repository = _repository_inventory()
    schema = _schema_inventory(repository)
    actual_tables = {
        table_name
        for table_name, item in schema["tables"].items()
        if item["database_present"]
    }
    progress = _progress_preflight(
        observed_at=observed_at,
        actual_tables=actual_tables,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if not connection_safety.get("current_mysql_evidence"):
        blockers.append("current_mysql_select_only_evidence_missing")
    if connection_safety.get("current_mysql_evidence"):
        if schema["alembic_head_match"] is not True:
            blockers.append("database_alembic_head_mismatch_or_missing")
        if schema["drift_count"]:
            blockers.append("current_schema_model_drift")
    if not repository["study_session_batches_migration_declared"]:
        blockers.append("study_session_batches_missing_repository_migration")
    if not all(progress["accounting"].values()):
        blockers.append("progress_preflight_accounting_drift")
    if progress["context_rows"]["unclassified"]:
        blockers.append("unclassified_progress_contexts_require_disposition")
    if progress["context_membership_rows"]["multiple"]:
        warnings.append("multi_context_progress_requires_p4_02_review")
    if progress["unknown_queue_rows"]:
        blockers.append("unknown_queue_values_require_disposition")
    lineage = progress["last_review_event_lineage"]
    if lineage["missing_pointer_rows"] or lineage["mismatched_user_or_card_rows"]:
        blockers.append("invalid_last_review_event_lineage_requires_disposition")
    if progress["connect_reference_inventory"]["missing_review_event_ref_rows"]:
        blockers.append("orphan_connect_review_event_refs_require_disposition")
    if progress["compatibility_alias_queue_rows"]:
        warnings.append("compatibility_queue_aliases_present")
    if progress["fan_in"]["state_divergent_groups"]:
        warnings.append("state_divergent_fan_in_requires_p4_02_contract")
    if progress["fan_in"]["lineage_divergent_groups"]:
        warnings.append("lineage_divergent_fan_in_requires_p4_02_p4_04_contract")
    rollout = progress["active_rollout_inputs"]
    if (rollout["active_enqueued_batches"] or 0) > 0:
        warnings.append("active_study_batches_require_rollout_fence")
    if (rollout["active_connect_imports"] or 0) > 0:
        warnings.append("active_connect_imports_require_rollout_fence")

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "evidence_class": (
            "current-mysql"
            if connection_safety.get("current_mysql_evidence")
            else "repository-and-fixture-only"
        ),
        "connection_safety": connection_safety,
        "repository": repository,
        "writer_inventory": list(WRITER_INVENTORY),
        "schema": schema,
        "progress": progress,
        "gate": {
            "status": "PASS" if not blockers else "BLOCKED",
            "p4_05_data_gate_passed": not blockers,
            "blockers": blockers,
            "warnings": warnings,
        },
    }
