# NOTE-only legacy retirement cutover

Status: populated and fresh isolated local MySQL rehearsals passed. Actual local
`nihongo` and VPS `flama` remain at revision 57; contraction is pending release
verification and integration of concurrent template changes. Never treat an
isolated rehearsal as an actual deployment.

## Release and evidence

Retirement must follow the deployed template modernization revision 57:

| Revision | Operation |
| --- | --- |
| 58 | Preserve original physical Card IDs/timestamps as immutable aliases and original entity sets; widen wire columns; drop physical Cards |
| 59 | Archive and drop column preferences and three historical backfill tables |
| 60 | Verify fresh NOTE coverage/current-state checksum; archive and drop CardProgress |
| 61 | Verify Template archive, explicit authorship and attachment coverage; remove origin NoteType |
| 62 | Add the NOTE due-selection index |

Current progress is already authoritative in NOTE. Do not import the frozen
CardProgress snapshot over it. Local and VPS state differ and must be audited
and backed up independently. Retain original event IDs, hashes, receipts,
session memberships and immutable release pins.

The [populated rehearsal evidence](../architecture/artifacts/legacy_progress_retirement_20261012/populated-local-rehearsal.json)
contains counts and checksums only. Full SQL backups and typed archives contain
private data and remain outside Git. Each archive must have a verified restore
marker from MySQL, using an isolated empty schema on the same dialect.

## Prepare each target

1. Build a committed release including the latest accepted template/frontend
   work. Run the relevant modular tests and release checks. Preserve unrelated
   working-tree edits. Verify one Alembic head, revision 62.
2. Take a full target backup and restore it to a newly created isolated schema.
   Record its SHA-256 and compare table counts. Do not reuse a stale backup or
   overwrite an existing rehearsal schema. Check views, routines, triggers and
   events for source-schema references before restoring.
3. Rehearse the six-table archive restore and actual `wsgi.py` migration entry
   point on that copy. Verify NOTE audit and protected-state conservation.
4. Inspect open sessions and unfinished batch inventory. Preserve sessions;
   drain admitted batches before stopping the worker. Expired/open sessions
   alone do not permit rewriting their hashes or IDs.

## Writer freeze and contraction

On local, identify the Flask listener and its parent before stopping only that
application. On VPS, stop HTTP and Connect writers, drain the current worker,
then stop `flama-study-worker.service` and the retention timer/service. Confirm
there are no other schedulers or deployments that can write or activate old
code during the window. Record the prior enabled/active service states.

With writers stopped, take the final full backup and restore proof, then create
the fresh audit, external archive and protected-state baseline. CLI commands
below run from the new release. Local credentials come from the private env
file; VPS may use root's MySQL socket for evidence commands. Do not print URIs,
environment contents or archive rows.

```text
python scripts/audit_legacy_progress_retirement.py --help
python scripts/archive_retired_tables.py [connection options] archive \
  --output <private-dir>/retirement-archive.json --tables \
  cards card_progress vocabulary_column_preferences \
  study_progress_backfill_runs study_progress_backfill_checkpoints \
  study_progress_backfill_dispositions
python scripts/archive_retired_tables.py [connection options] verify-restore \
  --bundle <private-dir>/retirement-archive.json \
  --restore-database <isolated-empty-archive-schema>
python scripts/verify_retirement_protected_state.py [connection options] \
  --output <private-dir>/protected-before.json --expected-revision 20261012_000057
```

The audit must return `DATA_READY`, no blockers, full old-progress coverage and
no current-state codec/hash/availability problems. Set both migration gate
paths to the **fresh target-specific** evidence:

```text
FLAMA_RETIREMENT_ARCHIVE=<private-dir>/retirement-archive.json
FLAMA_PROGRESS_RETIREMENT_AUDIT=<private-dir>/progress-before.json
STARTUP_RUN_MAINTENANCE=0
STARTUP_RUN_DB_CREATE_ALL=0
STARTUP_RUN_CLONE_CUTOVER=0
python -m flask --app wsgi.py db upgrade
```

Use the target database configuration explicitly. Inspect the result before
restarting writers. The MySQL DDL chain is not transactional: after a partial
failure, keep writers stopped, retain the compatible new code, inspect the
last revision/archive and resolve the failed gate. Do not restart the old
physical-Card runtime against a partially contracted schema.

```text
python scripts/verify_retirement_protected_state.py [connection options] \
  --output <private-dir>/protected-after.json \
  --baseline <private-dir>/protected-before.json \
  --expected-revision 20261012_000062 --require-retired
```

Require identical checksums for every protected table, no retired physical
table, no Template origin column, and alias count equal to the original Card
count. Run the read-only progress audit again using the verified external
archive as frozen-source evidence. Check its current Subject checksum matches
the baseline.

## Activate and verify

Activate the new release and restart the matching web, Connect and worker
processes. Restore the prior retention timer state. Verify actual entry-point
boot with maintenance enabled on the rehearsal first; it must not recreate
CardProgress, Cards or the retired backfill tables.

Check HTTP health, login, Browse, study queue/session issuance, old UUID session
status/retry, and owner versus installed clone scopes. Review service logs and
schema reflection. Inspect admission/worker health before permitting new
asynchronous work. Avoid synthetic production reviews that would change real
learner state; mutation smoke belongs on isolated rehearsal fixtures.

Only after actual local passes perform the same target-specific procedure on
VPS. Automatic rollback to a release expecting physical Cards is prohibited
after contraction. Restore a verified full backup into isolation for recovery
and reconcile any newer accepted work; frozen CardProgress never becomes
current NOTE authority again.
