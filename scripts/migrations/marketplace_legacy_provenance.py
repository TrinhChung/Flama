"""Plan and tag proven legacy receipt copies, preserving all content and pins.

Only loopback MySQL is supported. Plan and verify are read-only. Apply/rollback
require a reviewed checksum-bound plan and a new execution receipt. --dry-run
rehearses all checks and changes in a transaction which is then rolled back.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import sqlalchemy as sa

SCHEMA = "flama-marketplace-legacy-provenance.v1"
CHANGED_KEYS = ("origin", "source_template_id", "source_version_id")


def canonical(value):
    def encode(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return {"binary_hex": obj.hex()}
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(type(obj).__name__)
    return json.loads(json.dumps(value, default=encode, ensure_ascii=False))


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def save(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(canonical(value), stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def identity(session):
    url = session.get_bind().url
    if url.get_backend_name() != "mysql" or url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("A configured loopback MySQL database is required.")
    return {"database": url.database,
        "server_uuid": session.execute(sa.text("SELECT @@server_uuid")).scalar_one()}


def rows(session, model, *conditions):
    statement = sa.select(model.__table__).where(*conditions).order_by(*model.__table__.primary_key.columns)
    return canonical([dict(row) for row in session.execute(statement).mappings()])


def footprint(session, reference):
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    from models.study_application import StudyApplication
    from models.template import Template
    from models.template_subscription import TemplateSubscription
    from models.template_version import TemplateVersion
    local_id, source_id = reference["template_id"], reference["source_template_id"]
    return {
        "template": rows(session, Template, Template.id == local_id),
        "install": rows(session, NoteTypeInstall, NoteTypeInstall.id == reference["install_id"]),
        "note_types": rows(session, NoteType, NoteType.id.in_([
            reference["source_note_type_id"], reference["installed_note_type_id"]])),
        "applications": rows(session, StudyApplication, StudyApplication.note_type_id.in_([
            reference["source_note_type_id"], reference["installed_note_type_id"]])),
        "source_template": rows(session, Template, Template.id == source_id),
        "local_versions": rows(session, TemplateVersion, TemplateVersion.template_id == local_id),
        "local_subscriptions": rows(session, TemplateSubscription, TemplateSubscription.local_template_id == local_id),
    }


def protected_state(session, reference):
    from models.field_def import FieldDef
    from models.note import Note
    from models.review_event import ReviewEvent
    from models.study_progress_subject import StudyProgressSubject
    local_id = reference["installed_note_type_id"]
    note_ids = sa.select(Note.id).where(Note.note_type_id == local_id)
    state = {
        "fields": rows(session, FieldDef, FieldDef.note_type_id == local_id),
        "notes": rows(session, Note, Note.note_type_id == local_id),
        "reviews": rows(session, ReviewEvent, ReviewEvent.note_type_id == local_id),
    }
    if sa.inspect(session.get_bind()).has_table(StudyProgressSubject.__tablename__):
        state["progress"] = rows(session, StudyProgressSubject, StudyProgressSubject.live_note_id.in_(note_ids))
    return digest(state)


def expected_after(entry):
    result = deepcopy(entry["before"])
    result["template"][0].update(origin="market_copy",
        source_template_id=entry["reference"]["source_template_id"], source_version_id=None)
    return result


def plan(session):
    from app.repositories.legacy_template_provenance_repository import candidate_template_ids
    from app.services.legacy_template_provenance_service import legacy_reference
    result = {"schema": SCHEMA, "identity": identity(session),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "meaning": "Provenance tags only; no historical release or received content is inferred.",
        "entries": [], "unresolved": []}
    for template_id in candidate_template_ids(session):
        reference = legacy_reference(session, template_id)
        if not reference or not reference.get("source_template_id"):
            result["unresolved"].append({"template_id": template_id, "reason": "Original source mapping is ambiguous."})
            continue
        before = footprint(session, reference)
        if before["template"][0].get("source_version_id") or before["local_subscriptions"]:
            result["unresolved"].append({"template_id": template_id, "reason": "Existing pinned lineage needs a separate review."})
            continue
        entry = {"reference": reference, "before": before,
            "before_digest": digest(before), "protected_digest": protected_state(session, reference)}
        entry["after_digest"] = digest(expected_after(entry))
        result["entries"].append(entry)
    result["checksum"] = digest(result)
    return result


def validate_plan(session, reviewed):
    body = {key: value for key, value in reviewed.items() if key != "checksum"}
    if reviewed.get("schema") != SCHEMA or digest(body) != reviewed.get("checksum"):
        raise ValueError("Reviewed plan checksum does not match.")
    if reviewed["identity"] != identity(session):
        raise ValueError("Reviewed plan belongs to a different database or server.")


def lock_entries(session, reviewed):
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    from models.study_application import StudyApplication
    from models.template import Template
    from models.user import User
    refs = [entry["reference"] for entry in reviewed["entries"]]
    note_ids = sorted({value for ref in refs for value in (ref["source_note_type_id"], ref["installed_note_type_id"])})
    template_ids = sorted({value for ref in refs for value in (ref["source_template_id"], ref["template_id"])})
    # Deterministic current reads validate preimages after waiting for writers.
    for model, condition in (
        (User, User.id.in_(sorted({ref["user_id"] for ref in refs}))),
        (NoteType, NoteType.id.in_(note_ids)),
        (Template, Template.id.in_(template_ids)),
        (NoteTypeInstall, NoteTypeInstall.id.in_([ref["install_id"] for ref in refs])),
        (StudyApplication, StudyApplication.note_type_id.in_(note_ids)),
    ):
        session.execute(sa.select(model).where(condition).order_by(*model.__table__.primary_key.columns)
            .with_for_update().execution_options(populate_existing=True)).all()


def verify(session, reviewed, *, applied=True):
    validate_plan(session, reviewed)
    for entry in reviewed["entries"]:
        if digest(footprint(session, entry["reference"])) != entry["after_digest" if applied else "before_digest"]:
            raise ValueError("A selected row or its mapping/history changed from the reviewed preimage.")
        if protected_state(session, entry["reference"]) != entry["protected_digest"]:
            raise ValueError("Protected fields, notes, progress or review history changed.")
    return {"verified_templates": len(reviewed["entries"]), "legacy_release_pins_unchanged": True,
        "content_mappings_notes_progress_unchanged": True}


def execute(session, reviewed, *, rollback=False):
    from models.audit_log import AuditLog
    from models.template import Template
    validate_plan(session, reviewed)
    lock_entries(session, reviewed)
    changed = 0
    for entry in reviewed["entries"]:
        actual = digest(footprint(session, entry["reference"]))
        wanted = entry["before_digest" if rollback else "after_digest"]
        if actual == wanted:
            continue
        if actual != entry["after_digest" if rollback else "before_digest"]:
            raise ValueError("A selected row changed; regenerate and review the plan.")
        if protected_state(session, entry["reference"]) != entry["protected_digest"]:
            raise ValueError("Protected local content changed; refusing provenance cutover.")
        before = entry["before"]["template"][0]
        values = {key: before[key] for key in CHANGED_KEYS} if rollback else {
            "origin": "market_copy", "source_template_id": entry["reference"]["source_template_id"], "source_version_id": None}
        # Preserve modification time: this operation changes lineage, not code.
        values["updated_at"] = datetime.fromisoformat(before["updated_at"])
        session.execute(sa.update(Template.__table__).where(Template.id == before["id"]).values(**values))
        session.add(AuditLog(user_id=None, action="marketplace.legacy_provenance.rollback" if rollback else "marketplace.legacy_provenance.apply",
            payload={"checksum": reviewed["checksum"], "template_id": before["id"],
                "source_template_id": entry["reference"]["source_template_id"],
                "install_id": entry["reference"]["install_id"], "historical_release_unknown": True}))
        changed += 1
    session.flush()
    session.expire_all()
    verified = verify(session, reviewed, applied=not rollback)
    return {"changed_templates": changed, "already_applied": changed == 0, **verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "apply", "verify", "rollback"))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--expect-database", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    from app import create_app
    from models import db
    app = create_app(audit_mode=True)
    with app.app_context():
        try:
            if identity(db.session)["database"] != args.expect_database:
                raise ValueError("Configured database does not match --expect-database.")
            if args.mode == "plan":
                reviewed = plan(db.session)
                save(args.plan, reviewed)
                db.session.rollback()
                result = {"templates": len(reviewed["entries"]), "unresolved": len(reviewed["unresolved"]), "checksum": reviewed["checksum"]}
            else:
                reviewed = json.loads(Path(args.plan).read_text(encoding="utf-8"))
                validate_plan(db.session, reviewed)
                if args.mode == "verify":
                    result = verify(db.session, reviewed)
                    db.session.rollback()
                else:
                    if not args.receipt:
                        raise ValueError("Apply/rollback needs a new execution --receipt path.")
                    result = execute(db.session, reviewed, rollback=args.mode == "rollback")
                    save(args.receipt, {"checksum": reviewed["checksum"], "identity": reviewed["identity"],
                        "mode": args.mode, "dry_run": args.dry_run, **result})
                    if args.dry_run:
                        db.session.rollback()
                    else:
                        db.session.commit()
            print(json.dumps({"mode": args.mode, "dry_run": args.dry_run, **result}, ensure_ascii=True))
        finally:
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()


if __name__ == "__main__":
    main()
