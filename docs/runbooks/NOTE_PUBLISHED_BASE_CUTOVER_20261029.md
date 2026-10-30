# Published Base cutover and rollback

Status: local rehearsal verified; production not executed.
Contract and limits: [implementation ADR](../architecture/NOTE_PUBLISHED_BASE_IMPLEMENTATION_2026-10-29.md).

## Prepare and review

1. Restore a fresh production dump into an isolated MySQL 8 schema. Keep its server
   settings unchanged and record running/configured/persisted buffer pool values.
2. Install this code with `NOTE_PUBLISHED_BASE_ENABLED=false`; keep startup
   maintenance disabled. Apply Alembic through `20261029_000076` on the intended
   target. ORM code requires this expansion even with the runtime flag off.
3. Set `DB_*` for the exact target in the command's environment, without printing
   credentials. The `--database` argument checks that selection; it does not switch
   databases. Generate a private reviewed manifest:

```powershell
.\.venv\Scripts\python.exe scripts/note_base_cutover.py plan --database TARGET --manifest PRIVATE_MANIFEST.json --review-drafts PRIVATE_REVIEW.json
```

The plan command runs READ ONLY. If exact native-array/script receipts are available,
pass `--script-pairs PRIVATE_PAIRS.json` containing `[note_id, field_id]` pairs.
Exact receipt classification takes priority; otherwise the approved script windows
apply and remaining active field changes are treated as manual. Review every manual
Note/Field and its proposed Base/draft. Private manifests contain note content and
must stay outside Git and public reports. The tool refuses to overwrite an artifact.

The approved plan §7.1 explicitly requires: “Xuất danh sách note sẽ thành nháp để
chủ dự án duyệt.” Record the reviewed Note/Field content and classification together
with the manifest checksum. Before applying on the fresh target, compare its manual
draft export to that reviewed list. Request renewed owner review when Note/Field
values or classification change; database-name/timestamp-only manifest metadata
does not change a content approval. The operator must still pass the exact fresh
target checksum to `--approved-sha256` and retain both artifacts in the receipt.
Resolve any unexpected classification before apply.
Review the override census as well. A legacy override with a recorded original
release receives a hash of that release's value/presence; its personal value,
operation, identity and last-edit time are preserved. Unobserved legacy bases are
explicitly reported, never guessed from the author's current content.

## Apply

1. Stop all writers, including HTTP, MCP/Connect, workers, scheduled imports and
   scripts. Include the existing `flama-study-retention.timer` and
   `flama-study-retention.service`; deployment preserves its previous enablement.
   Stop **both** `flama-note-base-retention.timer` and
   `flama-note-base-retention.service`; verify the oneshot is inactive before
   acknowledging quiescence. Take a verified DB dump and retain its backup reference.
2. Regenerate/review the manifest if any Note, schema or template changed. Run:

```powershell
.\.venv\Scripts\python.exe scripts/note_base_cutover.py apply --database TARGET --manifest PRIVATE_MANIFEST.json --approved-sha256 APPROVED_HASH --writers-stopped --backup-reference VERIFIED_BACKUP --receipt PRIVATE_RECEIPT.json
```

The command validates target, checksum, listing heads/revisions, Note hashes,
schema and template state. It preserves manual edits in one sparse draft per Note,
and rejects a changed listing scope, install census or personal override since
review. Hash backfills are part of the same transaction; no learner value is
rewritten. It uses current script-normalized data as Base, captures current template pins, and
moves install metadata to the new Base once. It writes intent before COMMIT and
a receipt after COMMIT. If acknowledgment is lost, inspect intent and actual DB
state; never assume rollback or rerun blindly.

3. Deploy frontend/backend together with `NOTE_PUBLISHED_BASE_ENABLED=true`.
   The GitHub Environment variable of the same name is optional: when unset,
   managed-environment sync preserves the server's existing value. Set it only
   after applying the reviewed data conversion. An explicit `false` is not a
   data rollback. The code rollback guard rejects a pre-Base binary while a
   `base_cutover` release remains; complete the data rollback before that binary
   can be activated.
   Resume readers and smoke author Browse, installed Browse/search/Study, template
   rendering, local additions and comparison. Verify offline
   `study-authority-read-audit` after data conversion. Resume writers only after
   validation. Record that previously pinned installs now see the latest Base.
4. Keep a no-publish soak while old data/code remain available. Do not toggle the
   flag back and forth or enable dual writes. Automatic deck publication is retired.

## Rollback before the first new publish

Stop writers again, including the retention timer and active oneshot, and retain a fresh backup reference. Use the matching manifest
and active receipt:

```powershell
.\.venv\Scripts\python.exe scripts/note_base_cutover.py rollback --database TARGET --manifest PRIVATE_MANIFEST.json --receipt PRIVATE_RECEIPT.json --writers-stopped --backup-reference VERIFIED_BACKUP
```

The tool folds current author drafts back into the legacy working Notes, recreates
dirty fields, restores heads/install metadata and removes cutover releases. Installs
created during the soak keep local data/mappings and receive a valid legacy head.
It refuses rollback after a new publish or unsupported legacy draft disposition
(for example a post-cutover deletion draft); use the reviewed backup procedure in
that case. Do not bypass a refusal or overwrite new learner edits with an old dump.

After a successful rollback, deploy the legacy runtime with the flag off and run
the same smoke/audit checks. The expansion schema may remain in place.

## Contract and retention

After successful production soak and a retained operational backup, remove obsolete
runtime paths and the six history/rebase tables in a separately reviewed P6 change.
The current implementation keeps them for rollback and does not run destructive
history cleanup automatically.
The owner, operational entry checks and removal inventory are recorded in the
[P6 checklist](../architecture/NOTE_PUBLISHED_BASE_P6_CHECKLIST_2026-10-30.md).

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi.py note-base-retention --limit 200
.\.venv\Scripts\python.exe -m flask --app wsgi.py note-base-retention --limit 200 --apply
```

Resume a manual run with `--after NEXT_CURSOR` until `next_cursor` is null.
The daily systemd timer runs at 04:30 UTC with up to 15 minutes of jitter. It
skips flag-off releases before importing Flask or connecting to MySQL. Each
invocation uses `flock`, batches of 200, at most 200 batches and a 60-second
budget checked between batches. A batch commits before atomically advancing
`/var/lib/flama-note-base-retention/cursor.json`; interruption repeats a committed
batch safely if the cursor was not yet written. An incomplete daily run resumes
its cursor, and a completed sweep resets to the beginning for newly eligible
tombstones. Per-batch and total counts are JSON lines in
`journalctl -u flama-note-base-retention.service`. Activation installs the units,
stops the timer/oneshot with other writers before migration, and restores the
previous timer's enablement on safe code rollback. No unit has been installed
or activated on production as part of the local rehearsal.

The manual CLI defaults to dry run. Media asset/file GC is a separate future batch and
must account for Base, author drafts and learner overrides.

## Publish listings sharing a NoteType

The E6 convenience operation is explicit and defaults to preview:

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi.py note-base-publish-note-type --user-id OWNER_ID --note-type-id TYPE_UUID --version-label LABEL --batch-key UNIQUE_BATCH_KEY
```

Add `--apply` and optionally `--changelog TEXT` to publish. Each listing is its own
atomic transaction; a failed listing stops the batch with exit code 1 and a report
of the publications already committed. Reusing the same batch key replays completed
requests. Refresh the preview after a stale head/revision; use a new batch key when
changing the intended label or changelog. Listings with no changes are reported as
unchanged. This command never publishes subscribers individually.
