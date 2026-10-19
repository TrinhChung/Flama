"""Read-only guard: a contracted DB cannot run a name-storage binary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_field_code_rollback(engine, *, previous_release=None):
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if not inspector.has_table("notes"):
        return {"ok": True, "field_storage": "absent"}
    legacy = "field_values" in {column["name"] for column in inspector.get_columns("notes")}
    if legacy:
        return {"ok": True, "field_storage": "pre_contract"}
    if previous_release is None:
        return {"ok": False, "field_storage": "field-id.v1", "error": "FIELD_ID_CODE_ROLLBACK_UNSUPPORTED"}
    previous = Path(previous_release).resolve()
    model = previous / "models" / "note.py"
    # A declared capability accompanies the canonical getter. Do not execute
    # old application code against the current schema merely to discover it.
    compatible = model.is_file() and 'LIVE_FIELD_VALUE_CODEC = "field-id.v1"' in model.read_text(encoding="utf-8")
    compatible = compatible and (previous / "app" / "services" / "field_value_runtime_service.py").is_file()
    return {"ok": bool(compatible), "field_storage": "field-id.v1",
            "error": None if compatible else "FIELD_ID_CODE_ROLLBACK_UNSUPPORTED"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-release", type=Path)
    parser.add_argument("--writers-quiesced", action="store_true", required=True)
    args = parser.parse_args(argv)
    from app import create_audit_app
    from models import db
    app = create_audit_app({"REVIEW_ANALYTICS_WRITE_ENABLED": False, "DECK_COUNT_WRITE_ENABLED": False})
    with app.app_context():
        try:
            result = check_field_code_rollback(db.engine, previous_release=args.previous_release)
            print(json.dumps(result))
            return 0 if result["ok"] else 1
        finally:
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
