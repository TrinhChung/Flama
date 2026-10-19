"""Qualify analytics on an isolated copy of the configured loopback MySQL DB.

Default is a dry run. --run explicitly creates a nonce-named fixture schema,
copies base tables without source locks, upgrades only that fixture, builds
derived projections and compares four read matrices. A successful fixture is
removed unless --keep-schema is requested; failed fixtures are retained.
Credentials are passed through MYSQL_PWD, never command lines or evidence.
This is a local read qualification, not the report's production load matrix.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_review_analytics_mysql import local_url

TARGET_PATTERN = re.compile(r"^flama_scalability_probe_[0-9]+_[a-f0-9]{16}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
HEAD = "20261014_000068"


def generated_target():
    return f"flama_scalability_probe_{os.getpid()}_{secrets.token_hex(8)}"


def assert_owned_target(*, target, source, created_target):
    if (not TARGET_PATTERN.fullmatch(target) or target == source
            or target != created_target):
        raise RuntimeError("Refusing a schema other than the fixture created by this run.")


def _identifier(name):
    if not IDENTIFIER_PATTERN.fullmatch(name):
        raise ValueError("Schema/table/column name is outside the probe identifier contract.")
    return f"`{name}`"


def canonical_copy_ddl(definition):
    """MySQL dumps spell an inherited charset explicitly beside its collation.

    The collation still determines the charset. Normalize only that redundant
    spelling for copy parity; source preservation retains the exact DDL hash.
    """
    return re.sub(r" CHARACTER SET [A-Za-z0-9_]+(?= COLLATE )", "", definition)


def copy_matches(source, fixture):
    if (source["mysql_version"] != fixture["mysql_version"]
            or source["alembic_revisions"] != fixture["alembic_revisions"]
            or set(source["tables"]) != set(fixture["tables"])):
        return False
    fields = ("rows", "checksum_sum", "checksum_xor", "copy_schema_sha256")
    return all(all(original[field] == fixture["tables"][table][field] for field in fields)
               for table, original in source["tables"].items())


def mysql_command(executable, url, *, dump=False, database=None):
    """Ignore user options files and never interpolate into a shell."""
    command = [str(executable), "--no-defaults", "--protocol=TCP",
               f"--host={url.host}", f"--port={url.port or 3306}",
               f"--user={url.username}", "--default-character-set=utf8mb4"]
    if dump:
        command.extend(["--single-transaction", "--skip-lock-tables", "--no-tablespaces",
                        "--set-gtid-purged=OFF", "--skip-triggers", "--skip-add-locks"])
    else:
        command.append("--local-infile=0")
    command.append(database or url.database)
    return command


def _client_environment(url):
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = url.password or ""
    return environment


def _clients(client_directory):
    directory = client_directory or Path("C:/Program Files/MySQL/MySQL Server 8.0/bin")
    clients = {}
    for name in ("mysqldump", "mysql"):
        candidate = directory / f"{name}.exe"
        resolved = candidate if candidate.is_file() else shutil.which(name)
        if not resolved:
            raise RuntimeError(f"Required MySQL client is unavailable: {name}.")
        clients[name] = resolved
    return clients


def fingerprint_source(engine, schema):
    """Bounded-result fingerprint of every base-table row and table definition.

    Count/sum/xor CRC32 cover all columns (HEX avoids binary encoding loss).
    This detects accidental writes but is not an adversarial integrity proof.
    No user content, URLs or credentials are retained in the report.
    """
    result = {}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        catalog = connection.execute(text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=:schema AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
        ), {"schema": schema}).scalars().all()
        for table in catalog:
            columns = connection.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=:schema AND TABLE_NAME=:table ORDER BY ORDINAL_POSITION"
            ), {"schema": schema, "table": table}).scalars().all()
            encoded = ",".join(
                f"IF({_identifier(column)} IS NULL,'N',CONCAT('V',HEX({_identifier(column)})))"
                for column in columns)
            checksum = f"CRC32(CONCAT_WS('|',{encoded}))"
            row = connection.exec_driver_sql(
                f"SELECT COUNT(*),COALESCE(SUM({checksum}),0),COALESCE(BIT_XOR({checksum}),0) "
                f"FROM {_identifier(schema)}.{_identifier(table)}"
            ).one()
            definition = connection.exec_driver_sql(
                f"SHOW CREATE TABLE {_identifier(schema)}.{_identifier(table)}"
            ).one()[1]
            result[table] = {"rows": int(row[0]), "checksum_sum": int(row[1]),
                             "checksum_xor": int(row[2]),
                             "schema_sha256": hashlib.sha256(definition.encode()).hexdigest(),
                             "copy_schema_sha256": hashlib.sha256(canonical_copy_ddl(definition).encode()).hexdigest()}
        version = connection.exec_driver_sql(
            f"SELECT version_num FROM {_identifier(schema)}.alembic_version").scalars().all()
        server = connection.exec_driver_sql("SELECT VERSION()").scalar_one()
    return {"mysql_version": server, "alembic_revisions": version, "tables": result,
            "contract": "all base-table columns: count + CRC32 sum/xor; table DDL SHA256"}


def _check_copyable(engine, schema):
    with engine.connect() as connection:
        for query in (
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=:schema AND TABLE_TYPE<>'BASE TABLE'",
            "SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=:schema",
            "SELECT COUNT(*) FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=:schema AND UNIQUE_CONSTRAINT_SCHEMA<>:schema",
        ):
            if connection.execute(text(query), {"schema": schema}).scalar_one():
                raise RuntimeError("Source has views, triggers or cross-schema references; safe copy is unsupported.")


def _run_client(command, *, environment, stdin=None, stdout=None):
    result = subprocess.run(command, env=environment, stdin=stdin, stdout=stdout,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        # Client stderr can contain usernames/URLs; keep it out of both logs and artifacts.
        raise RuntimeError(f"MySQL client failed with exit code {result.returncode}.")


def _private_env(path, target_url):
    # dotenv interpolates ${...}; percent-encoding those legal password characters
    # preserves URL semantics without looking up unrelated process variables.
    uri = target_url.render_as_string(hide_password=False)
    uri = uri.replace("$", "%24").replace("{", "%7B").replace("}", "%7D")
    from dotenv import set_key
    path.touch(mode=0o600)
    set_key(str(path), "SQLALCHEMY_DATABASE_URI", uri, quote_mode="always")


def _upgrade_target(target_url):
    from app import create_audit_app
    from flask_migrate import upgrade
    from models import db
    app = create_audit_app({"TESTING": True,
        "SQLALCHEMY_DATABASE_URI": target_url.render_as_string(hide_password=False),
        "REDIS_URL": "", "DECK_COUNT_WRITE_ENABLED": False,
        "REVIEW_ANALYTICS_WRITE_ENABLED": False})
    with app.app_context():
        try:
            before = db.session.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            db.session.remove()
            # Only this runner's nonce-owned, writer-free fixture is prepared.
            # Live deployment must perform the same stages while quiesced.
            with db.engine.connect() as connection:
                needs_cutover = "field_values" in {column["name"] for column in inspect(connection).get_columns("notes")}
            cutover = None
            if needs_cutover:
                from scripts.cutover_field_value_identity import prepare_cutover
                upgrade(directory=str(ROOT / "migrations"), revision="20261014_000066")
                cutover = prepare_cutover(db.engine, apply=True, writers_quiesced=True, batch_size=200)
            upgrade(directory=str(ROOT / "migrations"), revision=HEAD)
            after = db.session.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            if after != [HEAD]:
                raise RuntimeError("The fixture did not reach the required migration head.")
            return {"before": before, "after": after, "field_cutover": cutover}
        finally:
            db.session.remove()
            db.engine.dispose()


def _workload(engine):
    with engine.connect() as connection:
        result = {}
        for table, predicate in (("decks", "owner_user_id=1"), ("notes", "user_id=1"),
                ("review_events", "user_id=1"), ("study_progress_subjects", "learner_user_id=1"),
                ("deck_installs", "user_id=1")):
            if table in inspect(connection).get_table_names():
                result[table] = int(connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {_identifier(table)} WHERE {predicate}").scalar_one())
        result["authority"] = connection.exec_driver_sql(
            "SELECT mode_code,epoch FROM study_authority_enrollments WHERE learner_user_id=1").mappings().one()
        result["authority"] = dict(result["authority"])
        result["storage_profile"] = connection.exec_driver_sql(
            "SELECT profile_code FROM study_authority_storage_profile WHERE id=1").scalar_one()
    return result


def verify_canonical_field_snapshot(connection):
    """Check live v1 storage and immutable evidence after normal writes resume.

    The pre-DDL gate compares each live row with its archived cutover value.
    That equality is intentionally no longer an invariant after contraction:
    edits, new Notes, media and schema revisions must remain possible.
    """
    from migrations.field_identity_contract import (
        ARCHIVE, CODEC, CUTOVERS, archive_root, bounded_rows, cached_reflections, reflected,
    )
    with cached_reflections(connection):
        inspector = inspect(connection)
        columns = {item["name"]: item for item in inspector.get_columns("notes")}
        if "field_values" in columns or inspector.has_table("field_rename_jobs"):
            raise RuntimeError("Field snapshot still has live name-key storage or rename jobs.")
        if any(columns[key]["nullable"] for key in
                ("field_values_by_id", "field_values_codec", "field_values_extras")):
            raise RuntimeError("Canonical Field codec and value stores must be nonnullable.")
        root, counts = archive_root(connection)
        manifest = reflected(connection, CUTOVERS)
        captured = connection.execute(manifest.select().where(manifest.c.id == CODEC)).mappings().first()
        if captured is not None:
            if (captured["state"] != "contracted" or not captured["writers_quiesced"]
                    or captured["archive_root_sha256"] != root
                    or captured["archive_count"] != sum(counts.values())
                    or any(captured[kind + "_count"] != count for kind, count in counts.items())):
                raise RuntimeError("Immutable Field archive differs from its contracted manifest.")
        elif any(counts.values()):
            raise RuntimeError("Field archive is missing its cutover manifest.")
        notes = reflected(connection, "notes")
        live_notes = 0
        for note in bounded_rows(connection, notes.select().with_only_columns(
                notes.c.id, notes.c.field_values_codec, notes.c.field_values_by_id,
                notes.c.field_values_extras), notes.c.id):
            if (note["field_values_codec"] != CODEC or not isinstance(note["field_values_by_id"], dict)
                    or not isinstance(note["field_values_extras"], dict)):
                raise RuntimeError("Live Note is outside the canonical Field codec.")
            live_notes += 1
        live_counts = {"note": live_notes}
        for kind, name in (("media", "media_assets"), ("override", "deck_clone_note_field_overrides")):
            if not inspector.has_table(name):
                live_counts[kind] = 0
                continue
            table = reflected(connection, name)
            if "field_identity_key" not in table.c or table.c.field_identity_key.nullable:
                raise RuntimeError("Live Field references require nonnullable canonical identities.")
            if connection.execute(table.select().with_only_columns(table.c.id).where(
                    table.c.field_identity_key.is_(None) | (table.c.field_identity_key == "")).limit(1)).first():
                raise RuntimeError("Live Field reference has no canonical identity.")
            live_counts[kind] = connection.execute(text("SELECT COUNT(*) FROM " + name)).scalar_one()
        return {"counts": live_counts, "archived_counts": counts, "archive_root_sha256": root,
                "single_live_authority": True, "immutable_archive_verified": True,
                "post_cutover_edits_allowed": True}


def local_read_gates(benchmark, workload):
    """Record scope limits so passing a small/local sample cannot qualify rollout."""
    metrics = benchmark["metrics"]
    gates = {"source_preserved": benchmark["source_preserved"],
             "same_snapshot_payload_parity": all(row["exact_payload_parity"] for row in metrics.values()),
             "reads_without_dml_or_row_locks": all(
                 not value["dml_statements"] and not value["locking_selects"]
                 for row in metrics.values() for mode, value in row.items() if mode != "exact_payload_parity")}
    forecast_operations = [name for name in ("overview", "today_future") if name in metrics]
    if forecast_operations:
        gates["forecast_ready_hits"] = all(
                 metrics[name]["summary"]["forecast_cache_coverage"]
                 and all(item["outcome"] == "hit" for item in metrics[name]["summary"]["forecast_cache_coverage"])
                 for name in forecast_operations)
    history_operations = [name for name in ("overview", "today_future", "study_time_all") if name in metrics]
    if history_operations:
        gates["ready_history_without_raw_scan"] = all(
            metrics[name]["summary"]["raw_history_selects"] == 0 for name in history_operations)
    dashboard_name = next((name for name in metrics if name.startswith("dashboard_compact_owned_")), "dashboard_compact")
    coverage = metrics[dashboard_name]["summary"]["deck_cache_coverage"]
    gates["dashboard_ready_hits"] = bool(coverage) and all(item["misses"] == 0 for item in coverage)
    scope = benchmark.get("dashboard_scope", {})
    node_count = scope.get("bounded", {}).get("selected_nodes") if "owned_" in dashboard_name else scope.get("visible_nodes", workload["decks"])
    if "owned_" in dashboard_name:
        gates["bounded_dashboard_all_nodes_returned"] = metrics[dashboard_name]["summary"]["returned_dashboard_nodes"] == node_count
        gates["bounded_dashboard_requested_scope_filled"] = node_count == scope["bounded"]["requested_nodes"]
    slos = {"dashboard": {"operation": dashboard_name, "p95_ms": metrics[dashboard_name]["summary"]["p95_ms"],
                "limit_ms": 300, "scope_decks_limit": 100, "visible_nodes": node_count,
                "scope_applicable": node_count <= 100,
                "synthetic_benchmark_visibility": "owned_" in dashboard_name}}
    for name, label in (("overview", "overview_due_heatmap"), ("today_future", "today_future_30d")):
        if name in metrics:
            slos[label] = {"p95_ms": metrics[name]["summary"]["p95_ms"], "limit_ms": 500}
    for item in slos.values():
        item["observed_within_limit"] = item["p95_ms"] <= item["limit_ms"]
    return {"checked_operations": list(metrics), "checks": gates, "latency_slos": slos, "correctness_passed": all(gates.values()),
            "production_qualified": False,
            "unmeasured": ["controlled 10k/100k/1m history scale matrix", "multi-user concurrency",
                "review-write p95 overhead", "cold cache and pool wait", "worker crash/lag under load",
                "physical I/O, rows examined and production resource footprint"]}


def run(arguments):
    source_url = local_url(arguments.env_file.resolve())
    _identifier(source_url.database)
    target = generated_target()
    assert_owned_target(target=target, source=source_url.database, created_target=target)
    plan = {"status": "DRY_RUN", "source_host": source_url.host,
            "source_database": source_url.database, "generated_target": target,
            "migration_head": HEAD, "repetitions": arguments.repetitions,
            "benchmark_head": HEAD,
            "cutover_only": bool(arguments.cutover_only),
            "source_writes": 0, "production_qualified": False,
            "actions": ["copy base tables without source locks", "upgrade fixture only",
                        "build derived fixture projections", "compare four read matrices",
                        "verify source fingerprint", "remove successful owned fixture unless kept"]}
    if not arguments.run:
        print(json.dumps(plan))
        return True
    if arguments.repetitions < 10:
        raise ValueError("Qualification requires at least 10 measured repetitions.")
    clients = _clients(arguments.mysql_client_directory)
    source_engine = create_engine(source_url, pool_pre_ping=True)
    admin_engine = create_engine(source_url.set(database=None), pool_pre_ping=True)
    target_url = source_url.set(database=target)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    created_target = None
    report = {**plan, "status": "RUNNING", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "now_utc": arguments.now, "fixture_only_writes": True}
    started = time.monotonic()
    try:
        report["phase"] = "source fingerprint"
        _check_copyable(source_engine, source_url.database)
        report["source_before"] = fingerprint_source(source_engine, source_url.database)
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            collation = connection.execute(text(
                "SELECT DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:source"
            ), {"source": source_url.database}).scalar_one()
            _identifier(collation)
            if connection.execute(text(
                    "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=:target"
                    ), {"target": target}).first():
                raise RuntimeError("Generated target exists; never overwrite another schema.")
            connection.exec_driver_sql(f"CREATE DATABASE {_identifier(target)} CHARACTER SET utf8mb4 COLLATE {collation}")
            created_target = target
        report["phase"] = "copy local snapshot"
        with TemporaryDirectory(prefix="flama-scalability-private-") as temporary:
            private = Path(temporary)
            dump = private / "fixture.sql"
            environment = _client_environment(source_url)
            with dump.open("wb") as output:
                _run_client(mysql_command(clients["mysqldump"], source_url, dump=True),
                            environment=environment, stdout=output)
            with dump.open("rb") as source:
                _run_client(mysql_command(clients["mysql"], source_url, database=target),
                            environment=environment, stdin=source, stdout=subprocess.DEVNULL)
            clone_before = fingerprint_source(target_engine, target)
            report["copy_snapshot_matches_source"] = copy_matches(report["source_before"], clone_before)
            report["copy_schema_contract"] = "exact DDL except redundant column charset before explicit collation"
            if not report["copy_snapshot_matches_source"]:
                raise RuntimeError("Source changed during copy or clone differs; refusing qualification.")
            report["phase"] = "upgrade fixture"
            report["migration"] = _upgrade_target(target_url)
            report["workload_user_1"] = _workload(target_engine)
            if arguments.cutover_only:
                from migrations.field_identity_contract import verify_prepared
                report["phase"] = "verify Field snapshot"
                with target_engine.connect() as connection:
                    if report["migration"]["field_cutover"] is not None:
                        gate = verify_prepared(connection, allow_partial_contract=True)
                    else:
                        gate = verify_canonical_field_snapshot(connection)
                    columns = {column["name"] for column in inspect(connection).get_columns("notes")}
                    single_authority = "field_values" not in columns and not inspect(connection).has_table("field_rename_jobs")
                report["qualification"] = {"correctness_passed": single_authority,
                    "field_contract": gate, "production_qualified": False,
                    "latency_measured": False}
            else:
                from scripts import bench_analytics_counts_mysql as benchmark
                private_env = private / "fixture.env"
                _private_env(private_env, target_url)
                bench_output = private / "benchmark.json"
                bench_args = argparse.Namespace(env_file=private_env, output=bench_output,
                    apply=True, deck_only=False, history_only=False, now=arguments.now,
                    repetitions=arguments.repetitions, prewarm_max_decks=arguments.prewarm_max_decks,
                    prewarm_max_batches=arguments.prewarm_max_batches,
                    forecast_max_buckets=arguments.forecast_max_buckets,
                    dashboard_only=arguments.dashboard_only, dashboard_owned_limit=arguments.dashboard_owned_limit)
                report["phase"] = "benchmark read matrices"
                with redirect_stdout(io.StringIO()):
                    benchmark.run(bench_args)
                report["benchmark"] = json.loads(bench_output.read_text(encoding="utf-8"))
                report["qualification"] = local_read_gates(report["benchmark"], report["workload_user_1"])
        report["phase"] = "verify configured source unchanged"
        report["source_after"] = fingerprint_source(source_engine, source_url.database)
        report["configured_source_preserved"] = report["source_before"] == report["source_after"]
        report["passed"] = report["configured_source_preserved"] and report.get("benchmark", {"passed": True})["passed"] and report["qualification"]["correctness_passed"]
        report["status"] = "PASS" if report["passed"] else "FAIL"
        if report["passed"] and not arguments.keep_schema:
            target_engine.dispose()
            assert_owned_target(target=target, source=source_url.database, created_target=created_target)
            with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.exec_driver_sql(f"DROP DATABASE {_identifier(target)}")
            report["fixture_cleanup"] = "removed owned generated schema"
            created_target = None
        else:
            report["fixture_cleanup"] = "retained isolated schema"
        report["phase"] = "complete"
    except Exception as error:
        report.update({"status": "ERROR", "passed": False,
            "error_type": type(error).__name__, "error": "Qualification failed; credentials and driver details suppressed.",
            "fixture_cleanup": "retained isolated schema" if created_target else "no fixture created"})
        if "source_before" in report:
            try:
                report["source_after"] = fingerprint_source(source_engine, source_url.database)
                report["configured_source_preserved"] = report["source_before"] == report["source_after"]
            except Exception:
                report["configured_source_preserved"] = "verification unavailable"
    finally:
        source_engine.dispose()
        target_engine.dispose()
        admin_engine.dispose()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("status", "generated_target", "passed",
        "configured_source_preserved", "fixture_cleanup", "elapsed_seconds", "phase", "error_type")}))
    return report["passed"]


def bounded_integer(minimum, maximum):
    def parse(value):
        try:
            number = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError("expected an integer") from error
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"expected an integer between {minimum} and {maximum}")
        return number
    return parse


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--env-file", type=Path, default=ROOT / ".env")
    command.add_argument("--output", type=Path, default=ROOT / "docs/architecture/artifacts/progress_scalability_qualification_mysql_20261014.json")
    command.add_argument("--run", action="store_true", help="Explicitly authorize isolated fixture creation, derived writes and owned cleanup")
    command.add_argument("--keep-schema", action="store_true", help="Keep the generated fixture even on success")
    command.add_argument("--cutover-only", action="store_true", help="Qualify full-source Field contraction without timing analytics")
    command.add_argument("--mysql-client-directory", type=Path)
    command.add_argument("--now", default="2026-10-14T03:00:00")
    command.add_argument("--repetitions", type=bounded_integer(10, 50), metavar="10..50", default=10)
    command.add_argument("--prewarm-max-decks", type=bounded_integer(1, 1000), metavar="1..1000", default=100)
    command.add_argument("--prewarm-max-batches", type=bounded_integer(1, 100), metavar="1..100", default=20)
    command.add_argument("--forecast-max-buckets", type=bounded_integer(1, 65536), metavar="1..65536", default=4096)
    command.add_argument("--dashboard-owned-limit", type=bounded_integer(0, 100), metavar="0..100", default=0)
    command.add_argument("--dashboard-only", action="store_true", help="Qualify just the chosen dashboard fixture stage")
    return command


if __name__ == "__main__":
    try:
        raise SystemExit(0 if run(parser().parse_args()) else 1)
    except Exception as error:
        print(json.dumps({"status": "ERROR", "error_type": type(error).__name__,
                          "error": "Qualification refused; sensitive connection details suppressed."}), file=sys.stderr)
        raise SystemExit(1)
