# Phase 4 current-state preflight — 2026-09-10

> Scope: P4-01 repository implementation and evidence readiness
>
> Verdict: **BLOCKED for current-MySQL acceptance**
>
> Runtime/storage change: none; this work is read-only audit instrumentation

## 1. Outcome first

The repository side of P4-01 is implemented: audit schema `study-architecture-audit.v4` now embeds `study-phase4-preflight.v1`, verifies MySQL grants before reading application tables, inventories model/migration/database contracts, accounts for progress state and lineage independently, and emits the complete writer lifecycle inventory. A two-run bundle command freezes `observed_at`, records timings and exit codes, compares deterministic output, and writes checksums without putting a database URI in the command or artifacts.

P4-01 is not accepted yet. No dedicated current-MySQL `SELECT`-only URI was available in the process environment on 2026-09-10. The normal `.env` application principal was deliberately not used. Therefore all current database counts, actual Alembic head, table options and schema drift remain **Needs Verification**.

There is also an independent repository blocker: `StudySessionBatch` is registered and used at runtime, but no Alembic revision declares `study_session_batches`. This gap must be remediated as its own migration concern and must not be hidden inside the later Phase 4 shadow-schema migration.

## 2. Frozen repository evidence

| Evidence | Observation | Disposition |
|---|---|---|
| inspected branch / HEAD | `develop` / `a6dc9b392ee8095b4777542ec20169fd939b1a19` | HEAD advanced during the handoff through non-overlapping MCP/Study UI/worksheet commits. The audit records the actual run HEAD, dirty-worktree digest and per-file code manifest because P4 work is not committed yet. Regenerate the final bundle after the implementation commit is chosen. |
| repository Alembic head | `20260910_000036` | Compare against `alembic_version` in the current MySQL bundle. Mismatch blocks P4-05. |
| audit contract | `study-architecture-audit.v4` + `study-phase4-preflight.v1` | Versioned in [study architecture audit service](../../app/services/study_architecture_audit_service.py) and [Phase 4 preflight service](../../app/services/study_phase4_preflight_service.py). |
| audit entrypoint | `wsgi_audit.py -> create_audit_app()` | Startup DDL, compatibility repair, seeds and clone cutover stay disabled. Normal `wsgi.py` is prohibited for evidence collection. |
| current MySQL evidence | unavailable | Platform/operator must provide an ephemeral environment variable containing a dedicated `SELECT`-only URI. This is an external gate, not a reason to weaken the audit. |
| `study_session_batches` migration | no migration mention found | **BLOCK.** Database lane owns a dedicated migration-gap disposition before P4-05 approval; P4-06 must not silently absorb it. |

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

Current production values for all of the above are **Needs Verification** until the secured bundle is run.

## 4. Schema comparison contract

For each relevant table the report records ORM and inspected database columns, dialect-compiled types, nullability, primary key, foreign keys and delete actions, unique column sets, indexes, server/client/database defaults and table options. Server-default mismatches are structural drift; Python client defaults are preserved as separate observations rather than mistaken for database defaults. Database and repository Alembic heads are compared independently.

This covers the MySQL-sensitive facts needed by P4-05: JSON/date-time/float representation, charset/collation, index shape, FK action and server defaults. SQLite fixture output is labeled `repository-and-fixture-only`; it can prove accounting and contract stability but cannot satisfy the MySQL gate.

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

## 6. Independent blocker disposition

### `study_session_batches` migration gap

- **Observed:** [study_session_batch.py](../../models/study_session_batch.py) declares the table; [app factory](../../app/__init__.py) registers the model; session and worker services read/write it; no file under `migrations/versions/` contains `study_session_batches`.
- **Potential concern:** environments upgraded strictly through Alembic can lack a table that `db.create_all()` environments happen to possess.
- **Impact:** async admission or worker execution can fail by environment history; a Phase 4 migration that happens to create the table would make the provenance gap invisible.
- **Disposition:** remain a named P4-01 blocker. The Database lane must first inspect current MySQL presence and shape, then create/review a dedicated forward-migration strategy on disposable MySQL. It is not part of the shadow schema and no remediation DDL is authorized in P4-01.
- **Verification needed:** pre-upgrade schema without startup `create_all`, upgrade to the dedicated revision, model/migration parity, existing-table handling based on current MySQL evidence, and downgrade/forward-rollback policy.

## 7. Secured two-run procedure

Run against a database snapshot/read replica or a quiesced maintenance window so both processes observe the same data. The target output directory must be empty and should be outside the repository.

```powershell
$env:STUDY_AUDIT_DATABASE_URI = 'mysql+pymysql://SELECT_ONLY_USER:SECRET@HOST:3306/DB?charset=utf8mb4'
.\.venv\Scripts\python.exe scripts\run_phase4_preflight_bundle.py D:\secure-evidence\phase4-preflight-20260910 --observed-at 2026-09-10T03:04:05Z
Remove-Item Env:STUDY_AUDIT_DATABASE_URI
```

The bundle writes `run-1.json`, `run-2.json`, `comparison.json` and `SHA256SUMS`. `comparison.json` stores the credential-free command, per-run timing and exit code, report hashes, deterministic equality and bounded changed JSON paths. An audit exit code of `2` is expected while a named P4 blocker remains; bundle creation is still useful, but P4-01 acceptance remains blocked.

Do not place credentials in CLI arguments, check them into `.env`, or substitute the normal application principal. Do not run application tests against this database.

## 8. Gate table and owners

| Gate | State | Owner / next evidence |
|---|---|---|
| read-only entrypoint and grant fail-closed | PASS in tests | Study audit lane; retain v4 tests |
| deterministic fixed-time report and checksummed bundle | PASS in tests | Operator must execute against the same current snapshot |
| repository/model/migration inventory | PASS | Regenerate after final implementation commit |
| writer/delete/reset/rekey inventory | PASS for static code paths | P4-07/P4-08 consume this list; current active volume still comes from MySQL evidence |
| current MySQL identity/settings/schema/data | **BLOCKED / Needs Verification** | Platform/operator supplies dedicated `SELECT`-only URI and secured output location |
| `study_session_batches` migration provenance | **BLOCKED** | Database lane resolves independently before P4-05 approval |
| P4-05 physical schema approval | **BLOCKED** | Requires both blockers above plus accepted P4-02/P4-03/P4-04 decisions |

P4-02 through P4-04 may continue as explicitly provisional drafts using repository evidence, but they cannot be accepted where a decision depends on current MySQL distribution. P4-05 and every migration/backfill task remain closed.

## 9. Verification completed locally

- audit service/CLI and bundle suites: 36 tests passed;
- modular `study,database,cli --backend-only` gate: 358 tests across 41 files passed;
- fixed-time CLI option, grant rejection, redaction, deterministic output, independent fan-in dimensions and accounting partitions are covered;
- learner-FK orphan accounting and overlapping owned/install context membership are covered by focused fixtures;
- no production/current MySQL command was executed because a dedicated `SELECT`-only credential was unavailable.

The final modular command and diff/link checks are rerun after documentation updates; their result belongs in the P4-01 task handoff.
