"""Reviewed, receipt-backed D6 cutover to the single Published Base.

Planning is read-only. Apply requires an exact approved manifest checksum,
operator confirmation that writers are stopped, and a backup reference. Private
manifests contain Note content and belong outside Git. Historical tables remain
untouched until the separate post-soak contract migration.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlalchemy as sa

from models.note import Note
from models.note_draft import NoteDraft
from models.field_def import FieldDef
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.deck_install import DeckInstall
from models.model_uuid import uuid_str

FORMAT = "flama.note-base-cutover.v1"
SCHEMA_KEYS = ("name", "field_type", "position", "required", "identity_role")


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    raise TypeError(type(value).__name__)


def checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), default=_json_default).encode()).hexdigest()


def _date(value):
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def manifest_checksum(manifest):
    return checksum({key: value for key, value in manifest.items() if key != "sha256"})


def manual_draft_review(manifest):
    """Content-bearing owner review, exported only to a private artifact."""
    if manifest.get("format") != FORMAT or manifest_checksum(manifest) != manifest.get("sha256"):
        raise RuntimeError("Invalid cutover manifest for review.")
    notes = []
    for plan in manifest["notes"]:
        if not plan["manual_fields"]:
            continue
        fields = []
        for field in plan["manual_fields"]:
            identity = field["field_id"]
            base = plan["base_fields_after"]
            author = plan["before"]["field_values_by_id"]
            fields.append({**field, "base_exists": identity in base, "published_base": base.get(identity),
                "author_exists": identity in author, "author_draft": author.get(identity)})
        notes.append({"note_id": plan["id"], "deck_item_id": plan["item_id"], "fields": fields})
    return {"database": manifest["database"], "manifest_sha256": manifest["sha256"],
        "manual_notes": len(notes), "notes": notes}


def _note_image(row):
    return {key: deepcopy(row[key]) for key in (
        "field_values_by_id", "field_values_extras", "tags", "deck_id", "content_revision", "deleted_at",
    )}


def _script_change(row, receipt_pairs):
    pair = (str(row["entity_id"]), str(row["field_def_id"] or ""))
    if pair in receipt_pairs:
        return "exact-script-receipt"
    when = row["updated_at"]
    if when is None:
        return None
    # Last-writer evidence only, matching the reviewed plan §2/§7.1. A manual
    # change subsequently overwritten by a script is necessarily treated as script.
    if datetime(2026, 10, 23, 12) <= when < datetime(2026, 10, 23, 12, 7):
        return "native-array-window-20261023"
    if when.date().isoformat() == "2026-10-11":
        return "cleanup-window-20261011"
    metadata = row["metadata_json"] or {}
    if when.date().isoformat() in {"2026-09-01", "2026-09-04"} and metadata.get("field_name") == "diagram":
        return "diagram-window-202609"
    return None


def _chunks(values, size=500):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def _locked_note_plans(connection, plans):
    for chunk in _chunks(plans):
        rows = {row["id"]: row for row in connection.execute(sa.select(Note.__table__).where(
            Note.id.in_([plan["id"] for plan in chunk])).order_by(Note.id).with_for_update()).mappings()}
        for plan in chunk:
            if plan["id"] not in rows:
                raise RuntimeError("A reviewed source Note no longer exists.")
            yield plan, rows[plan["id"]]


def _select_rows(session, model, *where):
    return session.connection().execute(sa.select(model.__table__).where(*where)).mappings().all()


def build_manifest(session, *, script_receipts=()):
    """Build a private review artifact without changing any database row.

    ``script_receipts`` is an iterable of exact ``(note_id, field_id)`` pairs
    normalized from the original script's private plan/receipt by the operator.
    Unknown last-writer evidence always becomes a manual draft.
    """
    from app.services.deck_release_service import _get_note_field_values_by_id_for_ids_at_release
    from app.services.template_release_service import deck_template_presentations
    if _select_rows(session, NoteDraft):
        raise RuntimeError("Cutover planning requires an empty note_drafts table.")
    pairs = {(str(note), str(field)) for note, field in script_receipts}
    items = _select_rows(session, DeckMarketplaceItem)
    releases = {row["id"]: row for row in _select_rows(session, DeckRelease)}
    memberships = _select_rows(session, DeckReleaseEntityMembership)
    fields = {row["id"]: row for row in _select_rows(session, FieldDef)}
    manifest = {"format": FORMAT, "database": session.get_bind().url.database,
                "created_at": datetime.utcnow().isoformat(timespec="microseconds"),
                "items": [], "notes": [], "installs": [],
                "classification": {"script_fields": 0, "manual_fields": 0}}
    dirty_by_item_note, classification_by_note = {}, {}
    # The legacy journal contains ~250k wide rows. Stream only the five columns
    # needed for classification and retain manual candidates, not script rows.
    dirty_query = sa.select(
        DeckWorkingDirtyEntity.deck_item_id, DeckWorkingDirtyEntity.entity_id,
        DeckWorkingDirtyEntity.field_def_id, DeckWorkingDirtyEntity.metadata_json,
        DeckWorkingDirtyEntity.updated_at,
    ).where(DeckWorkingDirtyEntity.entity_kind == "note_field")
    dirty_rows = session.connection().execute(dirty_query.execution_options(stream_results=True, yield_per=1000)).mappings()
    for row in dirty_rows:
        key = (row["deck_item_id"], row["entity_id"])
        reason = _script_change(row, pairs)
        counts = classification_by_note.setdefault(key, [0, 0])
        counts[0 if reason else 1] += 1
        if not reason:
            dirty_by_item_note.setdefault(key, []).append(dict(row))
    note_plans = {}
    for item in sorted(items, key=lambda value: value["id"]):
        release = releases.get(item["current_release_id"])
        schema = {identity: {**{key: field[key] for key in SCHEMA_KEYS},
                             "deleted_at": _json_default(field["deleted_at"]) if field["deleted_at"] else None}
                  for identity, field in fields.items() if field["note_type_id"] == item["source_note_type_id"]}
        item_plan = {"id": item["id"], "owner_user_id": item["owner_user_id"],
                     "current_release_id": item["current_release_id"],
                     "working_revision": item["working_revision"],
                     "published_schema_json": item["published_schema_json"],
                     "schema_after": schema,
                     "version": item["version"], "published_at": item["published_at"],
                     "auto_publish_enabled": item["auto_publish_enabled"],
                     "template_presentations_hash": checksum(deck_template_presentations(
                         session, note_type_id=item["source_note_type_id"])),
                     "release_sequence": release["sequence_no"] if release else None}
        manifest["items"].append(item_plan)
        if release is None:
            continue  # Notes in listings never published stay unpublished.
        if release["status"] != "published":
            raise RuntimeError("Listing head is not a published legacy release.")
        active_ids = sorted({row["entity_id"] for row in memberships
                             if row["deck_item_id"] == item["id"] and row["entity_kind"] == "note"
                             and row["introduced_sequence"] <= release["sequence_no"]
                             and (row["removed_sequence"] is None or row["removed_sequence"] > release["sequence_no"])})
        for chunk in _chunks(active_ids):
            rows = _select_rows(session, Note, Note.id.in_(chunk))
            if len(rows) != len(chunk):
                raise RuntimeError("An active legacy membership has no source Note.")
            manual_by_note = {}
            for row in rows:
                key = (item["id"], row["id"])
                counts = classification_by_note.get(key, [0, 0])
                manifest["classification"]["script_fields"] += counts[0]
                manifest["classification"]["manual_fields"] += counts[1]
                manual = dirty_by_item_note.get(key, [])
                if manual:
                    manual_by_note[row["id"]] = manual
            historical, _schema = _get_note_field_values_by_id_for_ids_at_release(
                release["id"], list(manual_by_note)) if manual_by_note else ({}, {})
            for row in rows:
                before = _note_image(row)
                if row["user_id"] != item["owner_user_id"]:
                    raise RuntimeError("Listing membership points to another author's Note.")
                base = deepcopy(row["field_values_by_id"])
                delta = {}
                manual_fields = []
                for change in manual_by_note.get(row["id"], []):
                    identity = change["field_def_id"]
                    if not identity:
                        raise RuntimeError("Manual dirty row has no stable Field ID; review its label disposition first.")
                    if row["id"] not in historical:
                        raise RuntimeError("Historical Base for a manual edit could not be reconstructed.")
                    old = historical[row["id"]]
                    current_present, old_present = identity in base, identity in old
                    current_value = deepcopy(base.get(identity))
                    if old_present:
                        base[identity] = deepcopy(old[identity])
                    else:
                        base.pop(identity, None)
                    if current_present != old_present or checksum(current_value) != checksum(old.get(identity)):
                        delta[identity] = {"op": "set", "value": current_value} if current_present else {"op": "remove"}
                        manual_fields.append({"field_id": identity, "field_name": (change["metadata_json"] or {}).get("field_name"),
                                              "last_written_at": change["updated_at"]})
                plan = {"id": row["id"], "item_id": item["id"], "before_hash": checksum(before),
                        "published_at_before": row["published_at"],
                        "published_at_after": row["published_at"] or release["published_at"],
                        "content_revision": row["content_revision"], "delta": delta,
                        "manual_fields": manual_fields}
                if delta:
                    plan["before"] = before
                    plan["base_fields_after"] = base
                prior = note_plans.get(row["id"])
                if prior and (prior["delta"] != delta or prior.get("base_fields_after") != plan.get("base_fields_after")):
                    raise RuntimeError("Overlapping listings disagree on a manual Note's Published Base.")
                note_plans[row["id"]] = plan
    manifest["notes"] = [note_plans[identity] for identity in sorted(note_plans)]
    manifest["installs"] = [{key: deepcopy(row[key]) for key in (
        "id", "deck_item_id", "applied_release_id", "seen_release_id", "version_mode", "auto_update_enabled",
    )} for row in _select_rows(session, DeckInstall)]
    manifest["sha256"] = manifest_checksum(manifest)
    return manifest


def _validate_manifest(session, manifest, approved_sha256):
    if manifest.get("format") != FORMAT or manifest_checksum(manifest) != approved_sha256 or manifest.get("sha256") != approved_sha256:
        raise RuntimeError("Manifest checksum does not match the explicitly approved artifact.")
    if manifest.get("database") != session.get_bind().url.database:
        raise RuntimeError("Manifest belongs to another database.")


def apply_manifest(session, manifest, *, approved_sha256, backup_reference, writers_stopped):
    """Stage one atomic cutover; caller persists the intent then commits once."""
    from app.services.template_release_service import capture_deck_release_template_pins, deck_template_presentations
    from models.audit_log import AuditLog
    if not writers_stopped or not str(backup_reference or "").strip():
        raise RuntimeError("Apply needs stopped writers and a verified backup reference.")
    _validate_manifest(session, manifest, approved_sha256)
    if _select_rows(session, NoteDraft):
        raise RuntimeError("Drafts already exist; inspect the cutover receipt before retrying.")
    connection = session.connection()
    now = datetime.utcnow()
    receipt = {"format": FORMAT, "manifest_sha256": approved_sha256,
               "database": manifest["database"], "backup_reference": backup_reference,
               "created_at": now.isoformat(timespec="microseconds"), "cutover_releases": {}, "base_note_updates": 0}
    for item in manifest["items"]:
        current = connection.execute(sa.select(DeckMarketplaceItem.__table__).where(
            DeckMarketplaceItem.id == item["id"]).with_for_update()).mappings().one()
        if current["current_release_id"] != item["current_release_id"] or current["working_revision"] != item["working_revision"]:
            raise RuntimeError("Listing changed since review; regenerate the cutover manifest.")
        from models.note_type import NoteType
        if current["source_note_type_id"]:
            connection.execute(sa.select(NoteType.id).where(NoteType.id == current["source_note_type_id"])
                .with_for_update()).first()
        fields = connection.execute(sa.select(FieldDef.__table__).where(
            FieldDef.note_type_id == current["source_note_type_id"]).order_by(FieldDef.id)
            .with_for_update()).mappings().all()
        schema = {row["id"]: {**{key: row[key] for key in SCHEMA_KEYS},
            "deleted_at": _json_default(row["deleted_at"]) if row["deleted_at"] else None} for row in fields}
        if checksum(schema) != checksum(item["schema_after"]):
            raise RuntimeError("Schema changed since review; regenerate the cutover manifest.")
        if checksum(deck_template_presentations(session, note_type_id=current["source_note_type_id"])) != item["template_presentations_hash"]:
            raise RuntimeError("Template changed since review; regenerate the cutover manifest.")
    for chunk in _chunks(manifest["notes"]):
        current_rows = {row["id"]: row for row in connection.execute(sa.select(Note.__table__).where(
            Note.id.in_([row["id"] for row in chunk])).order_by(Note.id).with_for_update()).mappings()}
        for plan in chunk:
            current = current_rows.get(plan["id"])
            if current is None or checksum(_note_image(current)) != plan["before_hash"] or current["published_at"] != _date(plan["published_at_before"]):
                raise RuntimeError("Note changed since review; regenerate the cutover manifest.")
            values = {}
            if current["published_at"] != _date(plan["published_at_after"]):
                values["published_at"] = _date(plan["published_at_after"])
            if plan["delta"]:
                values["field_values_by_id"] = plan["base_fields_after"]
                connection.execute(sa.insert(NoteDraft.__table__).values(
                    note_id=plan["id"], field_values_by_id=plan["delta"], op="edit", updated_at=now))
            if values:
                connection.execute(sa.update(Note.__table__).where(Note.id == plan["id"]).values(**values))
                receipt["base_note_updates"] += 1
    for item in manifest["items"]:
        values = {"published_schema_json": item["schema_after"], "auto_publish_enabled": False}
        if item["current_release_id"]:
            release = DeckRelease(id=uuid_str(), deck_item_id=item["id"],
                                  sequence_no=int(item["release_sequence"]) + 1,
                                  version_label=f"base-{approved_sha256[:12]}",
                                  parent_release_id=item["current_release_id"], status="published",
                                  publish_mode="base_cutover", source_working_revision=item["working_revision"],
                                  manifest_hash=approved_sha256, idempotency_key=f"base-cutover:{approved_sha256[:32]}",
                                  changelog="Single Published Base cutover; author drafts retained.",
                                  created_by_user_id=item["owner_user_id"], published_at=now)
            session.add(release)
            session.flush()
            capture_deck_release_template_pins(session, release, actor_user_id=item["owner_user_id"])
            values["current_release_id"] = release.id
            values["version"] = release.version_label
            values["published_at"] = now
            values["preview_samples_json"] = None
            values["preview_samples_release_id"] = None
            receipt["cutover_releases"][item["id"]] = release.id
        connection.execute(sa.update(DeckMarketplaceItem.__table__).where(DeckMarketplaceItem.id == item["id"]).values(**values))
    # One migration-only UPDATE; publication runtime never fans out to installs.
    for item_id, release_id in receipt["cutover_releases"].items():
        connection.execute(sa.update(DeckInstall.__table__).where(DeckInstall.deck_item_id == item_id).values(
            applied_release_id=release_id, seen_release_id=release_id, version_mode="published_base", auto_update_enabled=False))
    session.add(AuditLog(action="note_base_cutover", payload={"manifest_sha256": approved_sha256,
                    "backup_reference": backup_reference, "notes": len(manifest["notes"]),
                    "drafts": sum(bool(row["delta"]) for row in manifest["notes"])}))
    session.flush()
    receipt["sha256"] = checksum(receipt)
    return receipt


def rollback_manifest(session, manifest, receipt, *, backup_reference, writers_stopped):
    """Restore legacy heads before the first new publish, retaining new drafts.

    Historical rows were never deleted. Latest drafts are folded into the author
    working Notes and recreated in the dirty journal before legacy code resumes.
    """
    from app.services.note_draft_service import merge_draft_values
    from models.audit_log import AuditLog
    if not writers_stopped or not backup_reference:
        raise RuntimeError("Rollback requires stopped writers and backup reference.")
    _validate_manifest(session, manifest, receipt["manifest_sha256"])
    if receipt.get("database") != manifest["database"] or checksum({key: value for key, value in receipt.items() if key != "sha256"}) != receipt.get("sha256"):
        raise RuntimeError("Invalid cutover receipt.")
    connection = session.connection()
    for item in manifest["items"]:
        head = connection.execute(sa.select(DeckMarketplaceItem.current_release_id).where(
            DeckMarketplaceItem.id == item["id"]).with_for_update()).scalar_one()
        expected = receipt["cutover_releases"].get(item["id"], item["current_release_id"])
        if head != expected:
            raise RuntimeError("A publish occurred after cutover; restore the verified backup instead.")
    all_drafts = {row["note_id"]: row for row in _select_rows(session, NoteDraft)}
    now = datetime.utcnow()
    for plan, row in _locked_note_plans(connection, manifest["notes"]):
        if int(row["content_revision"]) != int(plan["content_revision"]):
            raise RuntimeError("Published Note revision changed; rollback requires the backup.")
        draft = all_drafts.get(row["id"])
        values = {}
        if row["published_at"] != _date(plan["published_at_before"]):
            values["published_at"] = _date(plan["published_at_before"])
        if draft:
            by_id, extras = merge_draft_values(row["field_values_by_id"], row["field_values_extras"], draft["field_values_by_id"])
            values.update(field_values_by_id=by_id, field_values_extras=extras,
                          tags=draft["tags"] if draft["tags"] is not None else row["tags"],
                          deck_id=draft["deck_id"] if draft["deck_id"] is not None else row["deck_id"])
            if draft["op"] == "delete":
                raise RuntimeError("A post-cutover delete draft cannot be represented by legacy code; use the backup.")
            for identity, change in draft["field_values_by_id"].items():
                if identity.startswith("meta:"):
                    if identity == "meta:deck_id":
                        values["deck_id"] = change.get("value")
                    continue
                if identity.startswith("extra:"):
                    raise RuntimeError("A draft with undeclared labels requires explicit legacy disposition.")
                field = connection.execute(sa.select(FieldDef.name).where(FieldDef.id == identity)).scalar_one_or_none()
                if field is None:
                    raise RuntimeError("A draft Field identity no longer exists.")
                property_key = f"field:{identity}"
                dirty = connection.execute(sa.select(DeckWorkingDirtyEntity.id).where(
                    DeckWorkingDirtyEntity.deck_item_id == plan["item_id"],
                    DeckWorkingDirtyEntity.entity_kind == "note_field", DeckWorkingDirtyEntity.entity_id == row["id"],
                    DeckWorkingDirtyEntity.property_key == property_key)).scalar_one_or_none()
                dirty_values = dict(operation="set" if identity in by_id else "remove", field_def_id=identity,
                                    current_hash=checksum(by_id[identity]) if identity in by_id else None,
                                    source_deck_id=values["deck_id"], metadata_json={"field_name": field}, updated_at=now)
                if dirty is None:
                    connection.execute(sa.insert(DeckWorkingDirtyEntity.__table__).values(
                        deck_item_id=plan["item_id"], entity_kind="note_field", entity_id=row["id"],
                        property_key=property_key, working_revision=0, created_at=now, **dirty_values))
                else:
                    connection.execute(sa.update(DeckWorkingDirtyEntity.__table__).where(DeckWorkingDirtyEntity.id == dirty).values(**dirty_values))
            connection.execute(sa.delete(NoteDraft.__table__).where(NoteDraft.note_id == row["id"]))
        if values:
            connection.execute(sa.update(Note.__table__).where(Note.id == row["id"]).values(**values))
    for item in manifest["items"]:
        connection.execute(sa.update(DeckMarketplaceItem.__table__).where(DeckMarketplaceItem.id == item["id"]).values(
            current_release_id=item["current_release_id"], published_schema_json=item["published_schema_json"],
            version=item["version"], published_at=_date(item["published_at"]), auto_publish_enabled=item["auto_publish_enabled"],
            dirty_tracking_revision=-1))  # Legacy publish must use its full-diff fallback.
        # Installs created during the no-publish soak retain their local content
        # and mapping, but need a valid legacy head before the cutover head is removed.
        connection.execute(sa.update(DeckInstall.__table__).where(
            DeckInstall.deck_item_id == item["id"], DeckInstall.version_mode == "published_base").values(
                applied_release_id=item["current_release_id"], seen_release_id=item["current_release_id"],
                version_mode="release" if item["current_release_id"] else "legacy_snapshot", auto_update_enabled=False))
    for install in manifest["installs"]:
        connection.execute(sa.update(DeckInstall.__table__).where(DeckInstall.id == install["id"]).values(
            **{key: value for key, value in install.items() if key not in {"id", "deck_item_id"}}))
    for release_id in receipt["cutover_releases"].values():
        connection.execute(sa.delete(DeckRelease.__table__).where(DeckRelease.id == release_id))
    session.add(AuditLog(action="note_base_cutover_rollback", payload={"manifest_sha256": receipt["manifest_sha256"],
                    "backup_reference": backup_reference}))
    session.flush()


def _write_private(path, value):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents and "output" not in path.parts:
        raise RuntimeError("Private cutover artifacts must be outside Git or under ignored output/.")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=_json_default)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "rollback"), nargs="?", default="plan")
    parser.add_argument("--database", required=True, help="Exact expected configured MySQL database name.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--script-pairs", help="Private JSON list of [note_id,field_id] from exact script receipts.")
    parser.add_argument("--review-drafts", help="Optional private JSON export of manual Notes and proposed Base/draft values.")
    parser.add_argument("--approved-sha256")
    parser.add_argument("--backup-reference")
    parser.add_argument("--writers-stopped", action="store_true")
    args = parser.parse_args(argv)
    from app import create_audit_app
    from models import db
    app = create_audit_app({"NOTE_PUBLISHED_BASE_ENABLED": False})
    with app.app_context():
        if db.engine.dialect.name != "mysql" or db.engine.url.database != args.database:
            raise RuntimeError("Explicit expected database does not match configured MySQL target.")
        session = db.session()
        if args.command == "plan":
            session.connection().exec_driver_sql("SET TRANSACTION READ ONLY")
            pairs = json.loads(Path(args.script_pairs).read_text(encoding="utf-8")) if args.script_pairs else []
            manifest = build_manifest(session, script_receipts=pairs)
            _write_private(args.manifest, manifest)
            if args.review_drafts:
                _write_private(args.review_drafts, manual_draft_review(manifest))
            session.rollback()
            print(json.dumps({"sha256": manifest["sha256"], "notes": len(manifest["notes"]),
                              "drafts": sum(bool(row["delta"]) for row in manifest["notes"]),
                              "classification": manifest["classification"]}))
            return
        if not args.receipt:
            parser.error("apply/rollback require --receipt")
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        if args.command == "apply":
            receipt = apply_manifest(session, manifest, approved_sha256=args.approved_sha256,
                                     backup_reference=args.backup_reference, writers_stopped=args.writers_stopped)
            # Persist intent before COMMIT: connection loss never implies rollback.
            _write_private(args.receipt + ".intent", receipt)
            session.commit()
            _write_private(args.receipt, receipt)
            print(json.dumps({"status": "applied", "manifest_sha256": manifest["sha256"]}))
        else:
            receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
            rollback_manifest(session, manifest, receipt, backup_reference=args.backup_reference, writers_stopped=args.writers_stopped)
            session.commit()
            print(json.dumps({"status": "rolled_back", "manifest_sha256": manifest["sha256"]}))


if __name__ == "__main__":
    main()
