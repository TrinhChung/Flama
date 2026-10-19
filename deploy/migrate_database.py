"""Quiesced deployment migration: expand, archive Field values, then contract.

There is no application-startup backfill. Operators/deploy stop every writer
before invoking this entry point. Preparation resumes from committed archives.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def migrate_database(app, *, writers_quiesced=False, rename_job_dispositions=None):
    if not writers_quiesced:
        raise ValueError("Stop all web, Connect, Study, projection and CLI writers before migrating Field storage")
    from flask_migrate import upgrade
    from sqlalchemy import inspect, text
    from models import db
    from scripts.cutover_field_value_identity import prepare_cutover
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing = inspector.get_table_names()
            needs_cutover = "notes" in existing and "field_values" in {
                column["name"] for column in inspector.get_columns("notes")}
            cutover = None
            if needs_cutover:
                upgrade(directory=str(ROOT / "migrations"), revision="20261014_000066")
                db.session.remove()
                cutover = prepare_cutover(db.engine, apply=True, writers_quiesced=True,
                    batch_size=200, rename_job_dispositions=rename_job_dispositions)
            upgrade(directory=str(ROOT / "migrations"))
            head = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            return {"ok": True, "head": head, "field_cutover": cutover,
                    "writers_quiesced": True, "field_values_authority": "field-id.v1"}
        finally:
            db.session.remove()
            db.engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writers-quiesced", action="store_true", required=True)
    parser.add_argument("--rename-job-dispositions", type=Path)
    args = parser.parse_args(argv)
    from app import create_audit_app
    dispositions = json.loads(args.rename_job_dispositions.read_text(encoding="utf-8")) if args.rename_job_dispositions else None
    app = create_audit_app({"REVIEW_ANALYTICS_WRITE_ENABLED": False, "DECK_COUNT_WRITE_ENABLED": False})
    print(json.dumps(migrate_database(app, writers_quiesced=args.writers_quiesced,
        rename_job_dispositions=dispositions), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
