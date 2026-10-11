# Array field cutover — 2026-10-11

> Follow-up for native JSON lists and template/data cleanup: use [NATIVE_ARRAY_CLEANUP_20261011.md](NATIVE_ARRAY_CLEANUP_20261011.md). This file documents the earlier line-string cutover; do not rerun its script to perform the native-list cleanup.

## Scope and storage

Based on Gemini's local production-dump analysis and the independent
[audit](../architecture/array-field-migration-review-2026-10-11.md). The original
long reports, unsafe chunk-commit script and generated test exports were archived
under ignored `output/typing-templates/array-source-archive/`; private dumps are
not release artifacts.

`scripts/migrations/array_manifest_20261011.json` identifies exactly 20 FieldDefs
across five NoteTypes, including the owners of the two installed types with own
notes. It does not match NoteTypes by name or change 50 empty installed schemas.
Release-pinned clone schema/content and learner overlays remain pinned.

At this cutover Flama's native `array` value was a **string with one item per
line**, not a JSON list. Later note writes store a JSON list instead (see
`models/field_types.py`); the strings written here stay until they are migrated
separately. Reading separators, `$` in short Vietnamese translations, semicolons in
English lists and commas in Kanji_N3 meanings follow the reviewed parsers.
Bracketed prose is preserved. Missing/null keys, non-target fields, media,
identity, tags, cards and review progress are retained. Already-array fields are
validated without splitting their punctuation again.

Initial production preflight: 41,199 scanned notes; 21,244 need content changes; 19,955
already have the same one-item result. 308 other notes remain out of scope.
139 repeated field values are preserved. Existing pair-length mismatches total
165 occurrences in **113 distinct notes** (Collocation 1, Synonym 64, Antonym 100);
the migration does not invent missing translations or deduplicate paired columns.

## Template and editor checks

- English pairs read rendered `<br>` boundaries in template JS. An item containing
  `;` remains one item; duplicate translations retain their index. Missing paired
  values render an empty cell rather than discarding the other column.
- Default reading/translation and English meanings use block text layout. Array
  lines have no added `<p>`/`<div>` wrapper, margin or padding. Existing grid row
  gap remains 3 px. Chrome checks covered 1280, 390 and 320 px plus natural wrapping.
- Prose fields not in the migration retain their existing formatting. The two
  customized template copies retain their image/audio markup and layout.
- Editor normalization and conversion validation preserve repeated array items.
  The server validates plain lines; it does not split template fields.
- Four reviewed typing definitions install into user 1's template library. Existing
  definitions update through ORM history; historical versions are not rewritten.

## Plan and apply

Run from the reviewed release with `/etc/flama/flama.env` supplied by systemd.
The factory runs in `audit_mode=True`; no startup schema repair executes.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py plan \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung
```

Before apply: stop HTTP, Connect and Study worker writers; verify they stopped;
take a fresh `mysqldump --single-transaction` backup and validate its gzip. Review
the plan summary/checksum. Plans contain original values and must stay mode 0600
outside git. Generate the final plan after writers stop.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py apply \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung --writers-stopped \
  --receipt /var/backups/flama/array-20261011/applied.json
```

Schema, content, template versions, audit and marketplace dirty atoms commit in
one transaction. Row locks plus whole-note hashes reject stale edits, including
notes whose preflight values did not require transformation. Note counts reject
membership changes. Chunked flushes do not commit partial data. Auto-publication
is suppressed for this cutover, including the presentation before-commit queue;
configured flags and historical releases/install pointers are retained. Dirty
atoms and revisions make a later normal release detect the backfill.

Verify every post-image hash, scoped field types, unchanged note/card/media counts,
new template heads, original historical versions/releases/install pointers,
working-tree atoms, renderer output, HTTP health and Study worker readiness.
An immediate new plan must report zero content/schema/template mutations.

## Restore

Keep writers stopped, or stop them again before restoration. This checks the
post-image hashes before replacing target values and types. Unrelated later edits
cause a refusal rather than an overwrite. Template restore creates a new history
version; newly installed definitions archive rather than deleting attachments.

```sh
/opt/flama/venv/bin/python scripts/migrations/array_cutover.py restore \
  --plan /var/backups/flama/array-20261011/cutover.json \
  --expect-database flama --expect-server chung --writers-stopped \
  --receipt /var/backups/flama/array-20261011/restored.json
```

Use the full SQL backup only under a stopped-writer recovery procedure. It is not
a routine rollback after new user writes. Follow the Study code-rollback gate
before selecting an older application release.

## Validation evidence

51 focused backend tests and 46 frontend tests passed; frontend lint, typecheck
and production build passed. Isolated MySQL rehearsal uses a full production
backup, injects failure after the first batch, checks rollback, performs the full
apply, checks idempotency and release previews, then restores all target values.
Rehearsal passed injected rollback, full restore and idempotency; 22 historical
releases and all install pointers/overlay revisions stayed unchanged. It created
22,596 additional dirty atoms, and real release previews detected the backfill.

## Production result

Completed on 2026-10-11 after [PR #226](https://github.com/TrinhChung/Flama/pull/226)
merged as `40ca800c23e86e6c009c104e5971229baa67bfe5`.
[Master CI and backend deployment](https://github.com/TrinhChung/Flama/actions/runs/38115472515)
passed all backend, frontend, MySQL, Redis and SPA gates. The VPS selected that
release and Alembic reached `20261010_000056`.

The frontend is currently a Cloudflare **Workers Static Assets** deployment,
`flama-frontend1001`, rather than the Pages deployment described in older setup
notes. Its existing Git trigger built master commit `40ca800c…` successfully;
deployed Worker version `b0df415f-336c-46c6-8e9a-575ea40c2015`. Chrome loaded the
new `index-Djro7yp9.js` bundle without console errors.

HTTP, Connect, Study worker and the active retention timer were stopped before
the final backup and plan. The gzip-validated full stopped-writer backup is
`/var/backups/flama/array-20261011/before-stopped.sql.gz` (114,277,364 bytes,
mode 0600 inside a mode 0700 directory). Its SHA-256 is
`356c4db4801c15da98d46d0f0a640072743725dce2bf7da3d4589b052f63a5ce`.
The earlier rehearsal backup `before.sql.gz` is retained separately.

Private `cutover.json` and `applied.json` are beside the backups. Final plan
checksum: `5547220e30027a1a696a23109404a189bccae20bcf965addc3d721b766428f51`.
The apply committed 20 field-type changes, 21,244 note-content changes, four
existing template updates and four new typing library definitions atomically.

Stopped-writer verification checked whole-note hashes for all 41,199 scoped
notes, including 19,955 unchanged notes. A subsequent plan reported zero
mutations. One new out-of-scope note had been created after the initial census;
all **309** out-of-scope notes were retained, bringing the total to **41,508**.
Full row hashes stayed identical for 41,508 cards, 33,930 media assets, 22 deck
releases and 28 deck installs. All 30 previous template-version rows stayed
identical; eight new versions brought the total to 38. The template count is 34.
Auto-publication flags were unchanged. Dirty atoms rose from 674 to 23,270
(22,596 additions), leaving a later explicit release able to detect the migration.

The actual production note used in the audit rendered all six collocation pairs,
including repeated translations, at 1280, 390 and 320 px. Pair-item margin and
padding remain 0, with a 3 px row gap. The HTML fixture and screenshot remain in
ignored local `output/typing-templates/array-layout/`; private row data is not
committed. The known 113 notes with uneven source/translation counts remain
reported rather than filled with guessed translations.

After restart, HTTP and Connect health passed, Study worker readiness passed,
all 20 scoped fields remained arrays and all four typing definitions appeared
through the template-library service. The retention timer was resumed.
