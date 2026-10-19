# Phase 4 current-state preflight — 2026-09-10

> Scope: P4-01 repository implementation and evidence readiness
>
> Verdict: **ACCEPTED — production upgraded and deterministic SELECT-only refresh passed on 2026-09-13**
>
> Runtime/storage change: none; this work is read-only audit instrumentation

## 1. Outcome first

The repository side of P4-01 is implemented: audit schema `study-architecture-audit.v4` embeds `study-phase4-preflight.v1`, verifies MySQL grants before reading application tables, inventories model/migration/database contracts, accounts for progress state and lineage independently, and emits the complete writer lifecycle inventory. A two-run bundle command freezes `observed_at`, records timings and exit codes, compares deterministic output, and writes checksums without putting a database URI in the command or artifacts.

P4-01 is accepted. After PR #162 deployed, the audit ran twice again against production MySQL with one frozen observation time and an ephemeral principal limited to `SELECT, SHOW VIEW`. The normal application principal was not used. The ephemeral principal was dropped and verified absent.

The two refreshed reports are deterministic and expose no credential or raw principal. They establish matching repository/database head `20260913_000038`, a valid `study_session_batches` contract and zero schema drift. The earlier bundle remains a labeled pre-remediation baseline that exposed 15 normalized actionable drift entries at head `20260910_000036`.

P4-01A resolved those findings through independent revisions `20260913_000037` and `20260913_000038`. Both local and production MySQL now report matching heads with zero drift. The [joint acceptance record](./phase-4-logical-contract-joint-acceptance-2026-09-13.md) carries the final checksums and closes P4-01.

### Accepted refresh — 2026-09-13

| Evidence | Observation | Disposition |
|---|---|---|
| deployed release | `11eefb15938cc8f4847df6d2d4014f40f41f3d13` | master deployment and services healthy |
| repository/database head | `20260913_000038` / `20260913_000038` | **PASS** |
| schema and batch contract | `drift_count=0`; batch issues `[]`; active/enqueued batches `0` | **PASS** |
| secured bundle | `/var/lib/flama-audit/phase4-preflight-20260912T225725Z-11eefb1` | root-owned `0700`; artifacts `0600` |
| deterministic result | canonical hash `59bdd8e680f09d0ed78a9164426abcf19ada81311d738dcf1947c15628aa1d63` twice; changed paths `[]` | **PASS** |
| file checksums | reports `fb45255ecd92f6bb7e10d99873bac0ef6db66e22ed6665a9b1b53be39a38d669`; comparison `ad4a8180c65ba4b907163d3ecf509f9d2bcd4b7890d69ffb9be895bd45db1026` | `sha256sum --check` passed |
| privilege/cleanup | only `SELECT, SHOW VIEW`; no disallowed privilege; temporary principals remaining `0` | **PASS** |
| P4 phase gate | both runs `PASS`; blockers `[]`; warnings `[]` | **ACCEPTED** |

The wider established audit exits `1` for seven historical warnings that remain visible and assigned; it has no overall blocker. This does not weaken the stricter P4 phase result.

## 2. Historical pre-remediation bundle

| Evidence | Observation | Disposition |
|---|---|---|
| inspected branch / HEAD | `develop` / `a6dc9b392ee8095b4777542ec20169fd939b1a19` | HEAD advanced during the handoff through non-overlapping MCP/Study UI/worksheet commits. The audit records the actual run HEAD, dirty-worktree digest and per-file code manifest because P4 work is not committed yet. Regenerate the final bundle after the implementation commit is chosen. |
| captured repository/Alembic head | `20260910_000036` | Historical production bundle baseline; current repository head is `20260913_000038` after P4-01A. A fresh bundle is required after deployment. |
| audit contract | `study-architecture-audit.v4` + `study-phase4-preflight.v1` | Versioned in [study architecture audit service](../../app/services/study_architecture_audit_service.py) and [Phase 4 preflight service](../../app/services/study_phase4_preflight_service.py). |
| audit entrypoint | `wsgi_audit.py -> create_audit_app()` | Startup DDL, compatibility repair, seeds and clone cutover stay disabled. Normal `wsgi.py` is prohibited for evidence collection. |
| deployed release source | `/opt/flama/releases/1ff3035826e3f370cba92639bc913640413bb148` | The release package has no `.git` metadata, so the report records `git_commit=null` and freezes a per-file code manifest instead. The run used a private copy of this release with only the reviewed audit portability patch applied; the serving release was not edited. |
| current MySQL evidence | observed `2026-09-12T11:16:29Z`; MySQL `8.0.46-0ubuntu0.22.04.4`; `utf8mb4` / `utf8mb4_unicode_ci`; timezone `SYSTEM` | **PASS for evidence availability and read-only safety.** `current_mysql_evidence=true`, two grant rows parsed, no disallowed privilege, and the temporary principal was removed. |
| deterministic bundle | `/var/lib/flama-audit/phase4-preflight-20260912T111629Z` on the VPS, mode `0700` directory / `0600` files | Both canonical report hashes are `307762278953f29ec88a31887f71af8c4b4a221f7d1e3ebf33c86db38a1e5704`; changed paths `[]`; durations `25,232 ms` and `25,281 ms`; both exits are expected blocker code `2`. |
| Alembic heads | repository `20260910_000036`; database `20260910_000036` | **PASS.** Repository and production database heads match. |
| `study_session_batches` migration/table | production table absent in captured evidence | **Historical finding.** `20260913_000037` later created/validated the table independently; the accepted refresh confirms it in production and P4-06 does not absorb it. |

The runtime report hashes the connected principal and database name, records server version, `sql_mode`, database charset/collation and timezone, but never returns the raw principal, URI, password or `SHOW GRANTS` text. For MySQL it queries identity/settings and `SHOW GRANTS` first, then refuses execution before application-table inspection when any write/admin privilege is present.

## 3. Data accounting contract

The preflight reads `CardProgress` as the current authority and reports:

- total source rows; valid learner→Card→Note subjects; NULL/missing learner, NULL/missing Card and NULL/missing Note rows as disjoint unresolvable reasons;
- an exact partition into preliminary mirror candidates, quarantine candidates and unresolvable rows;
- owned, installed-source, installed-local and unclassified progress contexts, plus independent context-membership counts so owned/install overlap is not hidden by the exclusive reporting precedence;
- canonical, compatibility-alias and unknown queues; due-at/due-day shapes; timestamp fractional precision; non-finite floats; suspension, burial and leech state; scheduler labels; complete/partial memory state;
- learner/Note fan-in with raw state equality kept separate from source/event lineage equality;
- NULL, valid, missing and mismatched `last_review_event_id`, plus matched Connect source-card, source-note and pointed-review references;
- current session evidence from the established audit and active `StudySessionBatch` / `ConnectImportSession` inputs when their tables exist.

Quarantine reasons are overlapping diagnostics, while the top-level migration disposition is mutually exclusive. Until P4-02 accepts the merge/fence rule, every fan-in group is a quarantine candidate; the audit never chooses a winner. Compatibility aliases are measured warnings, while unknown queues, partial memory state, invalid event pointers and unclassified identity are quarantine reasons.

Required formulas are emitted under `phase4_preflight.progress.accounting` and repeated in the top-level reconciliation gate. They include source, unresolvable-reason, migration-disposition, exclusive context, overlapping context-membership presence/cardinality, fan-in-state, fan-in-lineage, last-event-pointer, due-shape, queue and memory-state partitions.

Current production evidence is now available:

- 16,424 `CardProgress` rows are all valid learner→Card→Note subjects; unresolvable rows are `0`;
- 16,424 subject groups are single-contributor and fan-in groups are `0`; preliminary disposition is 16,424 mirror candidates, `0` quarantine candidates and `0` unresolvable;
- contexts partition into 16,107 owned and 317 installed-source rows, with no installed-local, overlapping or unclassified membership;
- all 16,424 queue labels are canonical: 432 new, 1,596 learning, 224 relearning and 14,172 review; no partial memory state, non-finite float, burial, suspension or leech rows were found;
- scheduler modes are 14,681 `anki` and 1,743 `legacy`; timestamp values have no fractional microseconds;
- 15,992 latest-event pointers are valid and 432 are null; no missing or cross-user/card pointer was found. All source-card/source-note/review-reference accounting partitions pass;
- four open sessions are active, 117 open sessions are expired, four session config snapshots are invalid, and no active Connect import exists. Batch volume is unavailable because `study_session_batches` is absent.

## 4. Schema comparison contract

For each relevant table the report records ORM and inspected database columns, dialect-compiled types, nullability, primary key, foreign keys and delete actions, unique column sets, indexes, server/client/database defaults and table options. Server-default mismatches are structural drift; Python client defaults are preserved as separate observations rather than mistaken for database defaults. Database and repository Alembic heads are compared independently.

This covers the MySQL-sensitive facts needed by P4-05: JSON/date-time/float representation, charset/collation, index shape, FK action and server defaults. SQLite fixture output is labeled `repository-and-fixture-only`; it can prove accounting and contract stability but cannot satisfy the MySQL gate.

The production comparison contains 15 normalized actionable entries:

| Drift kind | Count | Current observation |
|---|---:|---|
| server default | 12 | Database-only defaults on `card_progress.revision`, `connect_import_sessions.attempted_notes`, five `deck_installs` columns and five `deck_marketplace_items` columns |
| ordinary index | 1 | Model-only index on `deck_marketplace_items.student_offer_mode` |
| type/width | 1 | `deck_marketplace_items.student_offer_mode` is model `VARCHAR(16)` versus database `VARCHAR(32)` |
| table presence | 1 | `study_session_batches` is model-declared but absent in production |

The first production attempt also exposed audit noise: MySQL reflects collated strings with a `COLLATE` suffix and ORM `BOOL` as `TINYINT`, unique constraints may reappear through `get_indexes()`, and MySQL synthesizes indexes required by declared foreign keys. The audit now normalizes those dialect-managed representations and compares unique column sets independently from ordinary indexes. This reduced the raw 148 observations to the 15 entries above without suppressing the real width, default, application index or table mismatches.

## 5. Writer, delete, reset and rekey inventory

The same inventory is embedded in the machine report as `phase4_preflight.writer_inventory`.

| Path | Current mutation | Transaction/savepoint owner | Phase 4 handoff |
|---|---|---|---|
| `study_service.execute_native_review_command` | create/update `CardProgress`, append `ReviewEvent`, update latest pointer | service owns one-command commit; progress row uses `FOR UPDATE` | P4-07 native REST and MCP mirror point |
| `study_session_service.commit_study_session` | mutate all touched progress, append events, write receipt/session state | service owns one session commit; session and sorted progress rows use `FOR UPDATE` | P4-07 synchronous session mirror point |
| `study_worker_service.process_single_study_batch` | same progress/history effects plus durable batch/receipt status | worker owns one batch delivery or recorded-failure commit | P4-07 async retry/idempotency mirror point |
| `connect.import_cards.import_cards` | create/reconcile Cards, progress and source refs | service owns package commit; nested savepoint per Note | P4-08 card-import mirror stays inside Note savepoint |
| `anki_sync_service.import_progress` | apply external progress snapshot and revision/source-ref state | Anki upload route owns package commit; nested savepoint per record | P4-08 mirror only applied records, not conflict/no-op |
| `anki_sync_service.import_reviews` | append/repair ReviewEvent and Connect provenance | Anki upload route owns package commit; nested savepoint per source Card | history/provenance mirror only; no current-state replay |
| `deck_management_service.reset_deck_progress` | invalidate affected sessions and bulk-delete learner progress | service owns deck-subtree reset commit | P4-08 tombstone/generation event required |
| `deck_management_service.delete_deck_subtree` | detach/delete decks, Notes, Cards, progress, installs; preserve ReviewEvent facts by detaching deck | service owns subtree transaction | P4-08 explicit detach/delete disposition |
| browse card delete services | delete Card/possibly Note; progress follows FK cascade | browse service owns single/batch commit | P4-08 cascade must produce mirror lifecycle outcome |
| MCP note delete tools | explicit bulk-delete progress then Cards/Notes | tool owns single/batch commit | P4-08 explicit lifecycle mirror point |
| `share.cutover.cutover_clone_model_to_overlay_only` | merge/rekey progress from legacy local Cards to overlay source Cards, delete old local rows | startup/CLI caller owns outer transaction; nested savepoint per install | P4-08 preserve old→new contributor lineage |
| seed replacement paths | bulk-delete old progress with Cards/Notes then recreate content | registered seed command or standalone script owns commit | P4-08 maintenance rebuild/detach disposition |

Read-only repositories, dashboards, due queries and study selectors were inspected as consumers, not classified as writers. Overlay installation itself does not copy source Notes/Cards and must remain overlay-only.

## 6. Independent blocker disposition and closeout

### Remediation completion — 2026-09-13

[P4-01A](../task/decoupling/P4-01A_SCHEMA_DRIFT_REMEDIATION.md) implements two independent revisions. `20260913_000037` creates or validates `study_session_batches` and fails closed on an incompatible pre-existing shape. `20260913_000038` reconciles the 12 intentional server defaults, pins `student_offer_mode` to the migration-established width, adds its missing index, and safely converges nullable marketplace taxonomy metadata where required. Local MySQL was upgraded from `20260910_000036` to `20260913_000038`; the preflight schema comparator reports matching heads and zero drift. See the [design record](./phase-4-schema-drift-remediation-2026-09-13.md).

Production applied both revisions and the accepted refresh above closes the gate. The older captured bundle below remains evidence of the pre-remediation state rather than a current claim.

### `study_session_batches` migration gap

- **Observed:** [study_session_batch.py](../../models/study_session_batch.py) declares the table; [app factory](../../app/__init__.py) registers the model; session and worker services read/write it; no file under `migrations/versions/` contains `study_session_batches`.
- **Repository provenance update (2026-09-12):** `git log --follow` traces the model to commit `6da743e` (`feat(study): add redis queue and async batch processing for study reviews`, 2026-09-07). That commit added the model, app registration, session/worker writers and tests but no Alembic revision. No later revision through repository head `20260910_000036` declares the table.
- **Potential impact:** a database bootstrapped only through `alembic upgrade` can lack the durable async idempotency table, while an environment that ran startup `db.create_all()` may contain an unversioned table. Enabling async admission therefore has environment-dependent schema behavior.
- **Potential concern:** environments upgraded strictly through Alembic can lack a table that `db.create_all()` environments happen to possess.
- **Impact:** async admission or worker execution can fail by environment history; a Phase 4 migration that happens to create the table would make the provenance gap invisible.
- **Production observation (2026-09-12):** the table is absent even though the deployed model is registered; active batch row/status counts are therefore unavailable.
- **Disposition:** closed outside the Phase 4 shadow migration by dedicated revision `20260913_000037`, which creates or validates the table and fails closed for an unexpected pre-existing shape. P4-01 itself created no migration/model.
- **Verification completed:** pre-upgrade schema without startup `create_all`, upgrade to the dedicated revision, model/migration parity, absent/exact/drifted existing-table handling, non-destructive downgrade policy and the accepted production refresh.

## 7. Secured two-run procedure and historical first bundle

Run against a database snapshot/read replica or a quiesced maintenance window so both processes observe the same data. The target output directory must be empty and should be outside the repository.

```powershell
$env:STUDY_AUDIT_DATABASE_URI = 'mysql+pymysql://SELECT_ONLY_USER:SECRET@HOST:3306/DB?charset=utf8mb4'
.\.venv\Scripts\python.exe scripts\run_phase4_preflight_bundle.py D:\secure-evidence\phase4-preflight-20260910 --observed-at 2026-09-10T03:04:05Z
Remove-Item Env:STUDY_AUDIT_DATABASE_URI
```

The bundle writes `run-1.json`, `run-2.json`, `comparison.json` and `SHA256SUMS`. `comparison.json` stores the credential-free command, per-run timing and exit code, report hashes, deterministic equality and bounded changed JSON paths. The first bundle's exit code `2` recorded the then-open schema blocker; the accepted refreshed bundle reports P4 `PASS` while the wider audit exits `1` only for retained historical warnings.

Do not place credentials in CLI arguments, check them into `.env`, or substitute the normal application principal. Do not run application tests against this database.

## 8. Gate table and owners

| Gate | State | Owner / next evidence |
|---|---|---|
| read-only entrypoint and grant fail-closed | PASS in tests | Study audit lane; retain v4 tests |
| deterministic fixed-time report and checksummed bundle | **PASS / ACCEPTED** | Retain both secured bundles; regenerate after relevant audit/schema/deployment changes |
| repository/model/migration inventory | PASS | Regenerate after final implementation commit |
| writer/delete/reset/rekey inventory | PASS for static code paths | P4-07/P4-08 consume this list; current active volume still comes from MySQL evidence |
| current MySQL identity/settings/schema/data | **PASS / ACCEPTED** | Refresh shows head `000038`, zero drift and complete accounting |
| `study_session_batches` migration provenance/table | **PASS / ACCEPTED** | Production table exists, contract issues none, active/enqueued rows zero |
| schema drift remediation | **PASS / ACCEPTED** | Production applied `000038`; fresh comparator reports zero drift |
| P4-05 physical schema approval | **PASS / COMPLETED** | Joint logical review and physical schema ADR accepted on 2026-09-13 |

P4-02 through P4-04 consumed the refreshed distribution and were accepted jointly. P4-05 is complete; P4-06 may implement the additive schema/codecs with all runtime flags default off. Mirror/backfill remain closed until their owning tasks.

## 9. Verification completed

- audit service/CLI and bundle suites: 40 tests passed;
- modular `study,database,cli --backend-only` gate: 362 tests across 41 files passed;
- changed-file gate: 163 Study tests across 17 backend files passed; no frontend tests were selected;
- fixed-time CLI option, grant rejection, redaction, deterministic output, independent fan-in dimensions and accounting partitions are covered;
- learner-FK orphan accounting and overlapping owned/install context membership are covered by focused fixtures;
- the reserved-alias, MySQL type-reflection and unique-index normalization regressions pass in the focused audit test slice;
- the historical pre-remediation production bundle ran twice through `wsgi_audit.py` on a copied deployed release with startup maintenance disabled; the application principal and serving release were not used for data inspection or modified;
- `SHA256SUMS` records `e7e09c97afa827e23e41b55032b40ea815c43feeba72c3b951123bf1c7c2096e` for each pretty report and `1223e706825134e72fef5ab840a423361046682a075c0e635a9d79b6137d72a5` for `comparison.json`;
- the ephemeral audit principal was verified absent after the historical run; the accepted refresh repeated the same cleanup guarantee and retained its own checksums above.

The final modular command and diff/link checks are rerun after documentation updates; their result belongs in the P4-01 task handoff.
