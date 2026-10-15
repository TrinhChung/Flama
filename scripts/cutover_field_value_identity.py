"""Bounded offline Field-ID preparation; archive and verify before revision67.

The tool reflects legacy storage and never boots Flask or calls create_all.
Apply requires the operator to quiesce every web/Connect/CLI/worker writer.
Resume is automatic from immutable archive records, committed with each batch.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migrations.field_identity_contract import (
    ARCHIVE, CODEC, CUTOVERS, LEDGER, archive_root, json_text, raw_hash, reflected,
    schema_fingerprint, typed_hash, verify_prepared, extra_identity_key, cached_reflections,
)


def _object(value, label):
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object.")
    # Hash rejects nonfinite/scalar values; no normalization/default injection.
    typed_hash(value)
    return value


def _scratch(connection):
    return connection.info.get("field_identity_contract.reflections", {}).setdefault("_cutover_scratch", {})


def _known_tables(connection):
    scratch = _scratch(connection)
    if "known_tables" not in scratch:
        scratch["known_tables"] = set(sa.inspect(connection).get_table_names())
    return scratch["known_tables"]


def _prime_batch_scopes(connection, rows):
    """Resolve local scope in two bounded reads, rather than per-Note probes."""
    scratch, known = _scratch(connection), _known_tables(connection)
    scratch["note_links"] = {row["id"]: [] for row in rows}
    scratch["deck_links"] = {row["deck_id"]: [] for row in rows if row.get("deck_id") is not None}
    if "deck_clone_added_notes" in known and rows:
        added = reflected(connection, "deck_clone_added_notes")
        for row in connection.execute(sa.select(added.c.note_id, added.c.deck_install_id)
                .where(added.c.note_id.in_(list(scratch["note_links"])))).mappings():
            scratch["note_links"][row["note_id"]].append(row["deck_install_id"])
    if "deck_clone_deck_maps" in known and scratch["deck_links"]:
        maps = reflected(connection, "deck_clone_deck_maps")
        for row in connection.execute(sa.select(maps.c.local_deck_id, maps.c.deck_install_id)
                .where(maps.c.local_deck_id.in_(list(scratch["deck_links"])))).mappings():
            scratch["deck_links"][row["local_deck_id"]].append(row["deck_install_id"])


def _note_schema(connection, note):
    scratch, fields = _scratch(connection), reflected(connection, "field_defs")
    owned = scratch.setdefault("owned", {})
    if note["note_type_id"] not in owned:
        mapping, definitions = {}, []
        ages = scratch.setdefault("owned_created", {}).setdefault(note["note_type_id"], {})
        for field in connection.execute(sa.select(fields).where(fields.c.note_type_id == note["note_type_id"])
                .order_by(fields.c.id)).mappings():
            definition = {"identity_key": field["id"], "identity_kind": "owned", "field_id": field["id"],
                "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": field["name"],
                "label_history": [field["name"]], "is_retired": False}
            if field["name"] in mapping:
                raise RuntimeError("Ambiguous owned field label in captured schema.")
            mapping[field["name"]] = field["id"]
            ages[field["id"]] = field.get("created_at")
            definitions.append(definition)
        owned[note["note_type_id"]] = (mapping, definitions)
    mapping, definitions = owned[note["note_type_id"]]
    mapping, definitions = dict(mapping), list(definitions)
    known = _known_tables(connection)
    install_id = None
    if "deck_clone_added_notes" in known:
        added = reflected(connection, "deck_clone_added_notes")
        links = scratch.get("note_links", {}).get(note["id"])
        if links is None:
            links = connection.execute(sa.select(added.c.deck_install_id).where(added.c.note_id == note["id"])).scalars().all()
        if len(links) > 1:
            raise RuntimeError("One local Note cannot belong to multiple install scopes.")
        install_id = links[0] if links else None
    if "deck_clone_deck_maps" in known and note.get("deck_id") is not None:
        maps = reflected(connection, "deck_clone_deck_maps")
        links = scratch.get("deck_links", {}).get(note["deck_id"])
        if links is None:
            links = connection.execute(sa.select(maps.c.deck_install_id).where(maps.c.local_deck_id == note["deck_id"])).scalars().all()
        if len(set(links)) > 1 or (install_id and links and install_id not in links):
            raise RuntimeError("Conflicting local Note/install scope.")
        install_id = install_id or (links[0] if links else None)
    if install_id and "deck_clone_added_field_defs" in known:
        added_fields = reflected(connection, "deck_clone_added_field_defs")
        for field in connection.execute(sa.select(added_fields).where(added_fields.c.deck_install_id == install_id)
                .order_by(added_fields.c.id)).mappings():
            name = (field["properties"] or {}).get("name") or field["name"]
            if name in mapping:
                raise RuntimeError("Clone-added and owned labels collide; explicit schema correction is required.")
            key = f"added:{install_id}:{field['id']}"
            mapping[name] = key
            definitions.append({"identity_key": key, "identity_kind": "clone_added", "field_id": field["id"],
                "note_type_id": None, "deck_install_id": install_id, "retained_name": name,
                "label_history": [name], "is_retired": False})
    return {"note_type_id": note["note_type_id"], "deck_install_id": install_id,
            "names": mapping, "definitions": definitions}


def _store_definitions(connection, definitions):
    ledger = reflected(connection, LEDGER)
    stored = _scratch(connection).setdefault("stored_definitions", {})
    for definition in definitions:
        if definition["identity_key"] in stored:
            if any(stored[definition["identity_key"]][key] != definition[key]
                    for key in ("identity_kind", "field_id", "note_type_id", "deck_install_id")):
                raise RuntimeError("Stable field identity scope differs from retained provenance.")
            continue
        prior = connection.execute(sa.select(ledger).where(ledger.c.identity_key == definition["identity_key"])).mappings().first()
        if prior:
            if any(prior[key] != definition[key] for key in ("identity_kind", "field_id", "note_type_id", "deck_install_id")):
                raise RuntimeError("Stable field identity scope differs from retained provenance.")
        else:
            connection.execute(ledger.insert().values(**definition, created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        stored[definition["identity_key"]] = definition


def _historical_label_ids(connection, note_type_id, label):
    """Exact rename-job identity evidence, never a case/name approximation."""
    scratch = _scratch(connection)
    histories = scratch.setdefault("historical_labels", {})
    if note_type_id not in histories:
        histories[note_type_id] = {}
        if "field_rename_jobs" in _known_tables(connection):
            jobs = reflected(connection, "field_rename_jobs")
            if {"note_type_id", "field_def_id", "old_name", "new_name"} <= set(jobs.c.keys()):
                rows = connection.execute(sa.select(jobs).where(jobs.c.note_type_id == note_type_id)).mappings().all()
                field_ids = {job["field_def_id"] for job in rows if job["field_def_id"]}
                if field_ids:
                    fields = reflected(connection, "field_defs")
                    scopes = dict(connection.execute(sa.select(fields.c.id, fields.c.note_type_id).where(fields.c.id.in_(field_ids))).all())
                    if any(scope != note_type_id for scope in scopes.values()):
                        raise RuntimeError("Rename evidence belongs to another Field scope.")
                for job in rows:
                    if not job["field_def_id"]:
                        continue
                    for name in (job["old_name"], job["new_name"]):
                        histories[note_type_id].setdefault(name, set()).add(job["field_def_id"])
    return histories[note_type_id].get(label, set())


def _pinned_field_names(connection, release_id):
    """Decode immutable release field atoms; never rewrite a checkpoint/hash."""
    known = set(sa.inspect(connection).get_table_names())
    if not release_id:
        return {}
    if not {"deck_releases", "deck_release_changes"} <= known:
        raise RuntimeError("Explicit pinned release requires its retained Field history.")
    releases, changes = reflected(connection, "deck_releases"), reflected(connection, "deck_release_changes")
    target = connection.execute(sa.select(releases).where(releases.c.id == release_id)).mappings().one()
    if "status" in target and target["status"] != "published":
        raise RuntimeError("Explicit pinned release is not published historical evidence.")
    state = {}
    statement = sa.select(changes).join(releases, changes.c.release_id == releases.c.id).where(
        releases.c.deck_item_id == target["deck_item_id"], changes.c.release_sequence_no <= target["sequence_no"],
        changes.c.entity_kind == "field_def").order_by(changes.c.release_sequence_no, changes.c.id)
    for change in connection.execute(statement).mappings():
        identity = change["field_def_id"] or change["entity_id"]
        if change["operation"] in {"add", "set"}:
            state.setdefault(identity, {})[change["property_key"]] = change["after_value"]
        elif change["operation"] == "remove":
            state.setdefault(identity, {}).pop(change["property_key"], None)
    if "deck_release_entity_memberships" in known:
        members = reflected(connection, "deck_release_entity_memberships")
        rows = connection.execute(sa.select(members).where(members.c.deck_item_id == target["deck_item_id"],
            members.c.entity_kind == "field_def")).mappings().all()
        if rows:
            active = {row["entity_id"] for row in rows if row["introduced_sequence"] <= target["sequence_no"]
                and (row["removed_sequence"] is None or row["removed_sequence"] > target["sequence_no"])}
            state = {identity: payload for identity, payload in state.items() if identity in active}
    return {identity: payload["name"] for identity, payload in state.items() if isinstance(payload.get("name"), str)}


def _predates_override(created_at, item):
    # DATETIME without fractional seconds can make independent creations equal;
    # equality is not evidence that a definition existed before the override.
    return isinstance(created_at, datetime) and isinstance(item.get("created_at"), datetime) and created_at < item["created_at"]


def _override_identity(connection, item, notes):
    note = connection.execute(sa.select(notes).where(notes.c.id == item["source_note_id"])).mappings().one()
    schema = _note_schema(connection, note)
    installs = reflected(connection, "deck_installs")
    install = connection.execute(sa.select(installs).where(installs.c.id == item["deck_install_id"])).mappings().one()
    release_id = item.get("base_release_id") or install.get("applied_release_id")
    pinned = _pinned_field_names(connection, release_id)
    candidate_defs = []
    stable_key = item.get("field_identity_key")
    if stable_key and not item["source_field_def_id"]:
        if stable_key.startswith("extra:"):
            if stable_key != extra_identity_key(note["note_type_id"], item["field_name"]):
                raise RuntimeError("Preexisting extra override identity is outside captured scope.")
            candidate_defs = [{"identity_key": stable_key, "identity_kind": "extra", "field_id": None,
                "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": item["field_name"],
                "label_history": [item["field_name"]], "is_retired": False}]
        elif stable_key.startswith("added:"):
            parts = stable_key.split(":")
            if len(parts) != 3 or parts[1] != install["id"]:
                raise RuntimeError("Preexisting added override identity is outside its install.")
            added = reflected(connection, "deck_clone_added_field_defs")
            field = connection.execute(sa.select(added).where(added.c.id == parts[2], added.c.deck_install_id == install["id"])).mappings().first()
            if field:
                name = (field["properties"] or {}).get("name") or field["name"]
                candidate_defs = [{"identity_key": stable_key, "identity_kind": "clone_added", "field_id": field["id"],
                    "note_type_id": None, "deck_install_id": install["id"], "retained_name": name,
                    "label_history": [name], "is_retired": False}]
        else:
            candidate_defs = [definition for definition in schema["definitions"] if definition["identity_key"] == stable_key]
            if not candidate_defs and stable_key in pinned:
                candidate_defs = [{"identity_key": stable_key, "identity_kind": "owned", "field_id": stable_key,
                    "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": pinned[stable_key],
                    "label_history": [pinned[stable_key]], "is_retired": True}]
        if not candidate_defs:
            ledger = reflected(connection, LEDGER)
            retained = connection.execute(sa.select(ledger).where(ledger.c.identity_key == stable_key)).mappings().first()
            scoped = retained and retained["is_retired"] and (
                retained["identity_kind"] == "clone_added" and retained["deck_install_id"] == install["id"]
                or retained["identity_kind"] == "owned" and retained["note_type_id"] == note["note_type_id"])
            if not scoped:
                raise RuntimeError("Preexisting override identity has no exact scoped provenance.")
            candidate_defs = [{key: retained[key] for key in ("identity_key", "identity_kind", "field_id", "note_type_id",
                "deck_install_id", "retained_name", "label_history", "is_retired")}]
    elif item["source_field_def_id"]:
        field_id = item["source_field_def_id"]
        candidate_defs = [definition for definition in schema["definitions"] if definition["field_id"] == field_id]
        if not candidate_defs:
            fields = reflected(connection, "field_defs")
            scope = connection.execute(sa.select(fields.c.note_type_id).where(fields.c.id == field_id)).scalar_one_or_none()
            if scope is not None and scope != note["note_type_id"]:
                raise RuntimeError("Source override Field ID belongs to another NoteType.")
            candidate_defs = [{"identity_key": field_id, "identity_kind": "owned", "field_id": field_id,
                "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": pinned.get(field_id, item["field_name"]),
                "label_history": [pinned.get(field_id, item["field_name"])], "is_retired": True}]
    else:
        if release_id:
            for identity, name in pinned.items():
                if name == item["field_name"]:
                    candidate_defs.append({"identity_key": identity, "identity_kind": "owned", "field_id": identity,
                        "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": name,
                        "label_history": [name], "is_retired": identity not in schema["names"].values()})
        else:
            ages = _scratch(connection).get("owned_created", {}).get(note["note_type_id"], {})
            candidate_defs.extend(definition for definition in schema["definitions"]
                if definition["identity_kind"] == "owned" and definition["retained_name"] == item["field_name"]
                and _predates_override(ages.get(definition["field_id"]), item))
        added = reflected(connection, "deck_clone_added_field_defs")
        for field in connection.execute(sa.select(added).where(added.c.deck_install_id == item["deck_install_id"])).mappings():
            name = (field["properties"] or {}).get("name") or field["name"]
            if name == item["field_name"] and _predates_override(field.get("created_at"), item):
                candidate_defs.append({"identity_key": f"added:{install['id']}:{field['id']}", "identity_kind": "clone_added",
                    "field_id": field["id"], "note_type_id": None, "deck_install_id": install["id"],
                    "retained_name": name, "label_history": [name], "is_retired": False})
    if len(candidate_defs) > 1:
        raise RuntimeError("Clone override label has ambiguous source/added identity.")
    if not candidate_defs:
        candidate_defs = [{"identity_key": extra_identity_key(note["note_type_id"], item["field_name"]), "identity_kind": "extra",
            "field_id": None, "note_type_id": note["note_type_id"], "deck_install_id": None,
            "retained_name": item["field_name"], "label_history": [item["field_name"]], "is_retired": False}]
    schema = {"note_type_id": note["note_type_id"], "deck_install_id": install["id"], "definitions": candidate_defs,
              "base_release_id": item.get("base_release_id"), "applied_release_id": install.get("applied_release_id")}
    return candidate_defs[0]["identity_key"], schema


def _encoded_note(connection, note):
    named = _object(note["field_values"], "Named note values")
    schema = _note_schema(connection, note)
    by_id, extras = {}, {}
    for name, value in named.items():
        if name in schema["names"]:
            by_id[schema["names"][name]] = value
        else:
            extras[name] = value
    old = note["field_values_by_id"]
    if old is not None:
        old = _object(old, "Existing ID shadow")
        if note["field_values_codec"] != CODEC:
            raise RuntimeError("Existing ID shadow has an unsupported codec.")
        active_ids = set(schema["names"].values())
        for key in old:
            if key in active_ids:
                if key not in by_id or typed_hash(old[key]) != typed_hash(by_id[key]):
                    raise RuntimeError("Existing field-ID shadow differs from named values.")
            else:
                ledger = reflected(connection, LEDGER)
                definition = connection.execute(sa.select(ledger).where(ledger.c.identity_key == key)).mappings().first()
                if not definition or not definition["is_retired"] or (
                    definition["identity_kind"] == "clone_added" and definition["deck_install_id"] != schema["deck_install_id"]
                    or definition["identity_kind"] != "clone_added" and definition["note_type_id"] != note["note_type_id"]):
                    raise RuntimeError("Retired/out-of-scope shadow ID lacks explicit retained provenance.")
                reused = schema["names"].get(definition["retained_name"])
                if reused and reused not in old and definition["retained_name"] in named:
                    raise RuntimeError("Retired field label was reused without proven new-ID value provenance.")
                schema["definitions"].append({column: definition[column] for column in (
                    "identity_key", "identity_kind", "field_id", "note_type_id", "deck_install_id", "retained_name", "label_history", "is_retired")})
                by_id[key] = old[key]
        if typed_hash(note["field_values_extras"] or {}) != typed_hash(extras):
            raise RuntimeError("Existing retained extras differ from named values.")
    payload = {key: note[key] for key in ("id", "note_type_id", "user_id", "deck_id", "content_revision")}
    payload.update(field_values_by_id=by_id, field_values_codec=CODEC, field_values_extras=extras)
    return schema, payload


def _archive(connection, kind, identity, source_raw, schema, canonical):
    archive = reflected(connection, ARCHIVE)
    record = dict(object_kind=kind, object_id=str(identity), source_raw=source_raw, captured_schema=schema,
        canonical_payload=canonical, source_sha256=raw_hash(source_raw), canonical_sha256=typed_hash(canonical))
    existing = connection.execute(sa.select(archive).where(archive.c.object_kind == kind,
        archive.c.object_id == str(identity))).mappings().first()
    if existing:
        if any(existing[key] != record[key] for key in ("source_sha256", "canonical_sha256")):
            raise RuntimeError("Source changed after immutable cutover archive capture.")
    else:
        connection.execute(archive.insert().values(**record, created_at=datetime.utcnow()))


def prepare_cutover(engine, *, apply=False, writers_quiesced=False, batch_size=200, max_batches=None,
                    rename_job_dispositions=None):
    """Prepare all live scopes without ORM writes; each batch is atomic/resumable."""
    if not 1 <= batch_size <= 1000 or (max_batches is not None and max_batches < 1):
        raise ValueError("batch_size must be 1..1000 and max_batches positive.")
    if apply and not writers_quiesced:
        raise ValueError("Apply requires --writers-quiesced after every writer is stopped.")
    rename_job_dispositions = rename_job_dispositions or {}
    report = {"apply": apply, "notes": 0, "media": 0, "rename_jobs": 0, "overrides": 0, "batches": 0, "state": "dry_run"}
    with engine.connect() as connection, cached_reflections(connection):
        if "field_values" not in {column["name"] for column in sa.inspect(connection).get_columns("notes")}:
            return dict(report, state="already_contracted")
        schema_sha = schema_fingerprint(connection)
        manifest = reflected(connection, CUTOVERS)
        prior = connection.execute(sa.select(manifest).where(manifest.c.id == CODEC)).mappings().first()
        if prior and (prior["schema_sha256"] != schema_sha or prior["state"] == "contracted"):
            raise RuntimeError("Captured Field schema changed; immutable preparation cannot be silently restarted.")
        connection.rollback()
        if apply and not prior:
            with connection.begin():
                connection.execute(manifest.insert().values(id=CODEC, state="preparing", archive_count=0,
                    note_count=0, media_count=0, rename_job_count=0, override_count=0, archive_root_sha256="", schema_sha256=schema_sha,
                    definitions_sha256="", writers_quiesced=True, created_at=datetime.utcnow()))
        notes = reflected(connection, "notes")
        cursor = None
        connection.rollback()
        while True:
            with connection.begin():
                statement = sa.select(notes, sa.cast(notes.c.field_values, sa.Text).label("named_raw"),
                    sa.cast(notes.c.field_values_by_id, sa.Text).label("legacy_id_raw"),
                    sa.cast(notes.c.field_values_extras, sa.Text).label("legacy_extras_raw")).order_by(notes.c.id).limit(batch_size)
                if cursor:
                    statement = statement.where(notes.c.id > cursor)
                if apply:
                    archive = reflected(connection, ARCHIVE)
                    statement = statement.where(~sa.exists(sa.select(archive.c.object_id).where(
                        archive.c.object_kind == "note", archive.c.object_id == notes.c.id)))
                rows = connection.execute(statement).mappings().all()
                if not rows:
                    break
                _prime_batch_scopes(connection, rows)
                for note in rows:
                    schema, canonical = _encoded_note(connection, note)
                    if apply:
                        _store_definitions(connection, schema["definitions"])
                        captured = dict(schema, legacy_identity_state={key: note[key] for key in
                            ("field_values_by_id", "field_values_codec", "field_values_extras")},
                            legacy_identity_raw={"field_values_by_id": note["legacy_id_raw"], "field_values_extras": note["legacy_extras_raw"]},
                            legacy_note_row={key: value.isoformat() if isinstance(value, datetime) else value
                                for key, value in note.items() if key in notes.c})
                        _archive(connection, "note", note["id"], note["named_raw"], captured, canonical)
                        exact = sa.cast(notes.c.field_values, sa.Text) == note["named_raw"]
                        if connection.dialect.name == "mysql":
                            from sqlalchemy.dialects.mysql import BINARY
                            exact = sa.cast(notes.c.field_values, BINARY) == sa.cast(sa.literal(note["named_raw"], type_=sa.Text), BINARY)
                        changed = connection.execute(notes.update().where(notes.c.id == note["id"], exact,
                            notes.c.content_revision == note["content_revision"], notes.c.note_type_id == note["note_type_id"],
                            notes.c.user_id == note["user_id"]).values(
                            field_values_by_id=canonical["field_values_by_id"], field_values_codec=CODEC,
                            field_values_extras=canonical["field_values_extras"]))
                        if changed.rowcount != 1:
                            raise RuntimeError("Note changed during offline cutover; writers must remain quiesced.")
                    report["notes"] += 1
                cursor = rows[-1]["id"]
            report["batches"] += 1
            if max_batches and report["batches"] >= max_batches:
                return dict(report, state="preparing" if apply else "dry_run_bounded")
        # Media/job evidence is bounded by the same keyset/transaction budget.
        for kind, table_name in (("media", "media_assets"), ("override", "deck_clone_note_field_overrides"), ("rename_job", "field_rename_jobs")):
            if not sa.inspect(connection).has_table(table_name):
                connection.rollback()
                continue
            table = reflected(connection, table_name)
            connection.rollback()
            cursor = None
            while True:
                with connection.begin():
                    statement = sa.select(table).order_by(table.c.id).limit(batch_size)
                    if cursor:
                        statement = statement.where(table.c.id > cursor)
                    if apply:
                        archive = reflected(connection, ARCHIVE)
                        statement = statement.where(~sa.exists(sa.select(archive.c.object_id).where(
                            archive.c.object_kind == kind, archive.c.object_id == table.c.id)))
                    rows = connection.execute(statement).mappings().all()
                    if not rows:
                        break
                    for item in rows:
                        if kind == "media":
                            note = connection.execute(sa.select(notes).where(notes.c.id == item["note_id"])).mappings().one()
                            schema = _note_schema(connection, note)
                            key = schema["names"].get(item["field_name"])
                            if item["field_def_id"] is None:
                                candidates = set(_historical_label_ids(connection, note["note_type_id"], item["field_name"]))
                                if key:
                                    candidates.add(key)
                                if len(candidates) > 1:
                                    raise RuntimeError("Historical media label has ambiguous reused Field identities; explicit stable reference required.")
                                if candidates:
                                    key = next(iter(candidates))
                                    if key not in {definition["identity_key"] for definition in schema["definitions"]}:
                                        schema["definitions"].append({"identity_key": key, "identity_kind": "owned", "field_id": key,
                                            "note_type_id": note["note_type_id"], "deck_install_id": None, "retained_name": item["field_name"],
                                            "label_history": [item["field_name"]], "is_retired": True})
                            if item["field_def_id"] is not None:
                                candidates = [definition["identity_key"] for definition in schema["definitions"]
                                    if definition["field_id"] == item["field_def_id"]]
                                if len(candidates) == 1:
                                    key = candidates[0]
                                else:
                                    fields = reflected(connection, "field_defs")
                                    existing = connection.execute(sa.select(fields).where(fields.c.id == item["field_def_id"])).mappings().first()
                                    if existing and existing["note_type_id"] != note["note_type_id"]:
                                        raise RuntimeError("Media Field ID belongs to another NoteType; historical scope cannot be guessed.")
                                    key = item["field_identity_key"] or item["field_def_id"]
                                    schema["definitions"].append({"identity_key": key, "identity_kind": "owned",
                                        "field_id": item["field_def_id"], "note_type_id": note["note_type_id"], "deck_install_id": None,
                                        "retained_name": item["field_name"], "label_history": [item["field_name"]], "is_retired": True})
                            if not key:
                                if item["field_def_id"] is not None:
                                    raise RuntimeError("Historical media Field ID needs explicit retained provenance; it cannot become an extra label identity.")
                                key = extra_identity_key(note["note_type_id"], item["field_name"])
                                schema["definitions"].append({"identity_key": key, "identity_kind": "extra", "field_id": None,
                                    "note_type_id": note["note_type_id"], "deck_install_id": None,
                                    "retained_name": item["field_name"], "label_history": [item["field_name"]], "is_retired": False})
                            if item["field_identity_key"] and item["field_identity_key"] != key:
                                raise RuntimeError("Media stable identity conflicts with its captured scope.")
                            canonical = {column: item[column] for column in table.c.keys() if column != "created_at"}
                            canonical["field_identity_key"] = key
                            if apply:
                                _store_definitions(connection, schema["definitions"])
                                _archive(connection, kind, item["id"], json_text(dict(item)), schema, canonical)
                                connection.execute(table.update().where(table.c.id == item["id"]).values(field_identity_key=key))
                        elif kind == "override":
                            key, schema = _override_identity(connection, item, notes)
                            if item["field_identity_key"] and item["field_identity_key"] != key:
                                raise RuntimeError("Clone override stable identity differs from captured scope.")
                            canonical = {column: item[column] for column in table.c.keys() if column not in {"created_at", "updated_at"}}
                            canonical["field_identity_key"] = key
                            if apply:
                                _store_definitions(connection, schema["definitions"])
                                _archive(connection, kind, item["id"], json_text(dict(item)), schema, canonical)
                                connection.execute(table.update().where(table.c.id == item["id"]).values(field_identity_key=key))
                        else:
                            if item["status"] not in {"completed", "done", "succeeded"} and rename_job_dispositions.get(item["id"]) != "archive_as_abandoned":
                                raise RuntimeError("Unfinished rename job requires explicit archive_as_abandoned disposition.")
                            if apply:
                                if item.get("field_def_id") and item.get("note_type_id"):
                                    fields, ledger = reflected(connection, "field_defs"), reflected(connection, LEDGER)
                                    live = connection.execute(sa.select(fields).where(fields.c.id == item["field_def_id"])).mappings().first()
                                    if live and live["note_type_id"] != item["note_type_id"]:
                                        raise RuntimeError("Rename evidence belongs to another Field scope.")
                                    definition = {"identity_key": item["field_def_id"], "identity_kind": "owned", "field_id": item["field_def_id"],
                                        "note_type_id": item["note_type_id"], "deck_install_id": None,
                                        "retained_name": item["old_name"], "label_history": [item["old_name"], item["new_name"]],
                                        "is_retired": live is None}
                                    _store_definitions(connection, [definition])
                                    prior = connection.execute(sa.select(ledger).where(ledger.c.identity_key == item["field_def_id"])).mappings().one()
                                    names = list(dict.fromkeys([*(prior["label_history"] or []), item["old_name"], item["new_name"]]))
                                    connection.execute(ledger.update().where(ledger.c.identity_key == item["field_def_id"]).values(label_history=names))
                                _archive(connection, kind, item["id"], json_text(dict(item)),
                                    {"disposition": rename_job_dispositions.get(item["id"], "completed")}, {})
                        report[{"media": "media", "override": "overrides", "rename_job": "rename_jobs"}[kind]] += 1
                    cursor = rows[-1]["id"]
                report["batches"] += 1
                if max_batches and report["batches"] >= max_batches:
                    return dict(report, state="preparing" if apply else "dry_run_bounded")
        if apply:
            with connection.begin():
                if schema_fingerprint(connection) != schema_sha:
                    raise RuntimeError("Field scope/schema changed while preparing cutover.")
                root, counts = archive_root(connection)
                connection.execute(manifest.update().where(manifest.c.id == CODEC).values(state="verified",
                    archive_count=sum(counts.values()), note_count=counts["note"], media_count=counts["media"],
                    rename_job_count=counts["rename_job"], override_count=counts["override"], archive_root_sha256=root, verified_at=datetime.utcnow()))
                connection.execute(manifest.update().where(manifest.c.id == CODEC).values(
                    definitions_sha256=schema_fingerprint(connection, include_ledger=True)))
                verify_prepared(connection)
            report.update(state="verified", total_notes=counts["note"], total_media=counts["media"],
                total_rename_jobs=counts["rename_job"], total_overrides=counts["override"], archive_root_sha256=root)
        return report


def restore_archived_note_values(source_connection, isolated_target_connection):
    """Rehearse real legacy value restoration into a separate prepared database.

This restores field values/shadow state only. A full rollback starts from a
database backup preserving users, schemas, releases, media, sessions/history.
The target's existing rows and scope must match archived identities exactly.
"""
    if source_connection.engine is isolated_target_connection.engine:
        raise RuntimeError("Archive restoration requires a separate isolated database.")
    if isolated_target_connection.dialect.name == "mysql":
        target_name = str(isolated_target_connection.engine.url.database)
        if not target_name.startswith("flama_field_cutover_restore_") or target_name == source_connection.engine.url.database:
            raise RuntimeError("MySQL restore rehearsal requires a generated isolated restore schema.")
    archive_root(source_connection)
    target, archive = reflected(isolated_target_connection, "notes"), reflected(source_connection, ARCHIVE)
    if "field_values" not in target.c:
        raise RuntimeError("Restore target must use the pre-contraction legacy schema.")
    restored = 0
    for saved in source_connection.execute(sa.select(archive).where(archive.c.object_kind == "note").order_by(archive.c.object_id)).mappings():
        original = saved["captured_schema"]["legacy_note_row"]
        row = isolated_target_connection.execute(sa.select(target).where(target.c.id == saved["object_id"])).mappings().one()
        if any(row[key] != original[key] for key in ("note_type_id", "user_id", "deck_id", "content_revision")):
            raise RuntimeError("Isolated restore target Note scope/revision differs from archived source.")
        # Text binding preserves the original serialized JSON payload as held
        # by the engine. MySQL applies its canonical JSON binary encoding.
        isolated_target_connection.execute(sa.text("UPDATE notes SET field_values=:raw WHERE id=:identity"),
            {"raw": saved["source_raw"], "identity": saved["object_id"]})
        state = saved["captured_schema"]["legacy_identity_state"]
        isolated_target_connection.execute(target.update().where(target.c.id == saved["object_id"]).values(**{
            key: sa.null() if value is None else value for key, value in state.items()}))
        for key, raw_state in saved["captured_schema"].get("legacy_identity_raw", {}).items():
            if key not in {"field_values_by_id", "field_values_extras"}:
                raise RuntimeError("Unknown archived legacy identity column.")
            if raw_state is not None:
                isolated_target_connection.execute(sa.text(f"UPDATE notes SET {key}=:raw WHERE id=:identity"),
                    {"raw": raw_state, "identity": saved["object_id"]})
            actual = isolated_target_connection.execute(sa.select(sa.cast(target.c[key], sa.Text)).where(
                target.c.id == saved["object_id"])).scalar_one()
            if actual != raw_state:
                raise RuntimeError("Restored identity bytes/SQL-NULL presence differ from archived source.")
        raw = isolated_target_connection.execute(sa.select(sa.cast(target.c.field_values, sa.Text)).where(
            target.c.id == saved["object_id"])).scalar_one()
        if raw != saved["source_raw"]:
            raise RuntimeError("Restored legacy named bytes differ from archived source.")
        restored += 1
    if restored != isolated_target_connection.execute(sa.select(sa.func.count()).select_from(target)).scalar_one():
        raise RuntimeError("Isolated restore target has unarchived Note rows.")
    return {"restored_notes": restored, "raw_named_bytes_verified": True, "source_database_written": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url-env", default="DATABASE_URL", help="Environment variable holding target URL (never print credentials)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-quiesced", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--rename-job-dispositions", type=Path, help="JSON job_id to archive_as_abandoned decisions, archived with original evidence")
    parser.add_argument("--verify", action="store_true", help="Read-only full coverage/checksum/unchanged-source gate")
    args = parser.parse_args(argv)
    import os
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    target_url = os.getenv(args.database_url_env)
    if not target_url:
        if args.database_url_env != "DATABASE_URL":
            parser.error("Target database URL environment variable is unset")
        from scripts.mysql_probe_db import _connection_settings, _database_uri
        target_url = _database_uri(_connection_settings(), os.getenv("DB_NAME", ""))
    if args.apply and not args.writers_quiesced:
        parser.error("--apply requires --writers-quiesced after all writers are stopped")
    engine = sa.create_engine(target_url)
    try:
        if args.verify:
            if args.apply:
                parser.error("--verify is read-only and cannot combine with --apply")
            with engine.connect() as connection:
                result = verify_prepared(connection)
        else:
            dispositions = json.loads(args.rename_job_dispositions.read_text(encoding="utf-8")) if args.rename_job_dispositions else None
            result = prepare_cutover(engine, apply=args.apply, writers_quiesced=args.writers_quiesced,
                batch_size=args.batch_size, max_batches=args.max_batches, rename_job_dispositions=dispositions)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
