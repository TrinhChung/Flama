# Phase 4 reconciliation and rollout rehearsal — 2026-09-20

> Status: P4-10 locally complete; P4-11 and INT-02 are **not closed**.
>
> Authority: `CardProgress` only. Shadow write, backfill and compare flags remain default-off.
>
> Scope: disposable local and VPS MySQL databases/principals with synthetic rows. The production application database `flama` was read-only and unchanged.

## P4-10 comparison evidence

The versioned `study-progress-reconciliation.v1` comparator runs only through the
mutation-disabled audit application when `STUDY_PROGRESS_SHADOW_COMPARE_ENABLED`
is explicitly on. It checks source/contributor/state/availability accounting,
raw hashes, revision/generation, last-event pointers, Connect lineage, typed
quarantines, fixed-context due counts and complete Card ordering. Two runs at
one fixed observation time must produce identical reports and checksums. The
report names bounded representation tolerances separately from unexplained
differences. A Connect source Note whose content hash advances after the
captured progress lineage is tolerated only if identity still matches and the
source ref's update time is strictly later; source Card snapshot hash drift
remains a blocker.

The writer coverage matrix reports direct REST, MCP, session, async batch,
Connect snapshot, legacy progress, revlog, reset, content delete and clone
cutover separately. Each class has a real flag-on regression that backfills
and reconciles after the writer, or checks the matching retained lifecycle
evidence. `NOT_OBSERVED` in a single audit is not reported as a pass for an
absent writer. Installed-source and installed-local Note query scopes are
covered by the overlay integration and fixed-context comparator tests.

## Disposable MySQL evidence

Run from `D:\Project\nihongo` with the existing local `.env`:

```text
.\.venv\Scripts\python.exe scripts/probe_phase4_reconciliation_mysql.py --schema-snapshot-baseline --rollout-rehearsal --extra-rows 1000
```

The probe reads only table DDL and Alembic head from the configured local
database. It excludes ten shadow tables previously created outside Alembic,
restores 88 core tables at head `20260913_000038` into a new disposable
database, and copies **no application rows**. Migration 38→39 creates the ten
shadow tables; disposable downgrade and re-upgrade both passed. This is a
synthetic pre-Phase4 schema reconstruction, not a restored production backup.

| Check | Observed local result |
|---|---|
| Engine | MySQL 8.0.40; `utf8mb4_0900_ai_ci`; server timezone `SYSTEM` |
| Synthetic source rows | 1,002; one owned learner/deck context |
| Migration upgrade/downgrade/re-upgrade | pass; 1.689 s total |
| Backup/restore of synthetic pre-backfill snapshot | 98 tables; equal table-count/content checksums; 4.365 s |
| Flags-off `wsgi.py` restart before and after backfill | source progress unchanged; no startup backfill; derived rows retained after rollback |
| Bounded backfill | 11 batches, 21.839 s, 45.88 rows/s |
| SELECT-only audit principal | grant verified; `REPEATABLE-READ` snapshot |
| Two full reconciliation reports | identical, zero unexplained; 16.411 s total |
| Full architecture audit | embedded shadow reconciliation gate PASS |
| `EXPLAIN ANALYZE` | subject, current-contributor and disposition-resume lookups used indexes; no `ALL` table access |
| Cleanup | disposable database, restored database and SELECT-only principal removed |

The server's `sql_mode` was
`ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION`.
The source is the local head-38 schema, not the live production schema. The
known production preflight reported MySQL 8.0.46 and `utf8mb4_unicode_ci`;
this local run alone did **not** prove version/collation parity or production
`sql_mode`. The VPS-specific result below checks those separately.
The same probe also passed with **16,424 synthetic source rows** and the
P4-01 queue histogram (432 new, 1,596 learning, 224 relearning, 14,172
review). Its measured result was:

```text
.\.venv\Scripts\python.exe scripts/probe_phase4_reconciliation_mysql.py --schema-snapshot-baseline --rollout-rehearsal --extra-rows 16422
```

| Check | 16,424-row local result |
|---|---|
| Migration round-trip | pass; 1.724 s before fixture loading |
| Synthetic backup/restore | 98 tables, identical count/checksum digest; 7.332 s |
| Backfill | complete; 165 bounded batches in 413.002 s, 39.77 rows/s |
| Two reconciliation runs | identical checksums, zero unexplained; 313.468 s total |
| Full read-only architecture audit | embedded shadow reconciliation gate PASS |
| Query plans | subject `uq_sp_subject_user_note` (`const`, 1 estimated row); contributor `uq_sp_contributor_generation_source` (`ref`, 1); retry disposition `ix_sp_disposition_result` (`ref`, 1) |
| Flags-off restarts | before and after backfill both preserve source/shadow counts |
| Cleanup | disposable database, restored database and SELECT-only principal removed |

This proves the current local comparator at the **recorded production source
count**, not at production's exact version, schema contents, user/deck/overlay
mix or write load. Backfill and audit times are not production SLAs. The
probe uses one synthetic owned learner/deck scope; installed overlay parity
has separate integration coverage but not a production-shaped MySQL cohort.

## Isolated VPS MySQL rehearsal

After explicit approval, the same probe ran from the local worktree through an
SSH tunnel to the VPS MySQL Unix socket. It read only `SHOW CREATE TABLE`,
`alembic_version`, and schema collation metadata from the application database
`flama`; it copied **no application rows**. The observed application head was
`20260913_000039`, not the historical head-38 preflight snapshot. The probe
removed the ten Phase 4 shadow tables from a DDL-only copy of 98 source tables,
created 88 core tables in an isolated `utf8mb4_unicode_ci` database stamped at
head 38, then ran migration 38→39, downgrade and re-upgrade there. This is a
reconstructed pre-Phase4 schema, **not** a production data backup or a migration
on the application database.

| Check | Observed VPS result |
|---|---|
| Engine and schema default | MySQL 8.0.46; source/probe database `utf8mb4_unicode_ci`; server default `utf8mb4_0900_ai_ci`; timezone `SYSTEM` |
| SQL mode | `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION` |
| Synthetic cohort | 12 progress rows, one owned learner/deck scope |
| Migration upgrade/downgrade/re-upgrade | pass; 21.840 s across the tunnel |
| Synthetic backup/restore | 98 tables, equal content/count checksum digest; 82.127 s across the tunnel |
| Flags-off `wsgi.py` restart before and after backfill | pass; no startup backfill or source change; derived rows retained |
| Backfill | complete, one batch; 26.155 s across the tunnel (0.46 rows/s, **not** server-side capacity) |
| SELECT-only audit | `localhost` principal, `REPEATABLE-READ`, grant verified |
| Two reconciliation reports | identical, zero unexplained, 8.550 s total |
| Full architecture audit | embedded reconciliation gate PASS |
| `EXPLAIN ANALYZE` | subject `uq_sp_subject_user_note` (`const`); contributor `uq_sp_contributor_generation_source` (`ref`); retry `ix_sp_disposition_result` (`ref`); no full scan in these three lookups |
| Cleanup/post-check | both disposable databases and audit principal absent; `flama.alembic_version` remained head 39 |

The temporary audit principal used a random password and the server's
`mysql_native_password` plugin, restricted to `localhost` and SELECT on only
the disposable database; it was dropped. The server's default
`caching_sha2_password` authentication failed over this TCP-to-Unix-socket SSH
tunnel, while the native-password smoke check passed. This transport-specific
workaround is **not** a recommendation to change production application users.
The small VPS cohort proves the environment-matched migration/restart/audit
path, not the 16,424-row load, multi-user/overlay distribution, production
throughput or complete concurrency/fault matrix. Tunnel latency dominates its
measured timings, so none is a rollout batch-size or abort threshold.

Four additional isolated VPS probes passed on the same MySQL 8.0.46 server,
with each disposable database explicitly matching `flama`'s
`utf8mb4_unicode_ci` default. Unlike the DDL-copy rehearsal above, these
probes build synthetic core tables from current model metadata before stamping
head 38; they do **not** prove production core-schema migration equivalence.

| Probe | Observed VPS result |
|---|---|
| Shadow schema/codec | Ten migration table contracts clean; live Note/Card FK collations match; microsecond and raw codec round trips; duplicate subject key contained by savepoint; empty downgrade/re-upgrade and startup schema check pass |
| Resumable backfill | Dry run writes nothing; checkpoint failure rolls back; crash/resume and completed replay pass; sibling-Card-create, reset and Card-delete races each retry once and preserve correct generation/tombstone accounting |
| Native mirror | Direct/MCP/session fan-in and worker completion pass; injected mirror fault rolls back authority/event/shadow; forced InnoDB subject lock timeout rolls back the native review atomically |
| External lifecycle | External savepoint fault rolls back; revlog remains history-only; reset/delete lifecycle evidence passes; native/external two-connection race completes without deadlock and source content is unchanged |

After all five VPS probes, a read-only post-check found **zero** remaining
`flama_p4_shadow_probe_%` databases, **zero** `p4audit_%` principals and
`flama.alembic_version` still at head 39. These probes cover a useful subset,
not the missing rekey-versus-backfill, forced database deadlock/disconnect,
JSON/size and worker retry/DLQ matrix.

## Integration verification

```text
.\.venv\Scripts\python.exe scripts/run_tests.py --module study,connect_mcp,decks,flashcards,database,cli --backend-only
# 948 tests / 86 files passed

.\.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only
# 179 tests / 22 files passed

npm --prefix frontend run typecheck
# passed

npm --prefix frontend run lint
# exit 0, existing warnings
```

`git diff --check` and compilation of changed Phase 4 Python files passed.
Static searches found no product API/route shadow reads, no mirror-coordinator
commit/rollback, and no startup backfill call. The three Phase 4 flags are
configured `default=False`. These searches are supporting evidence, not a
substitute for the remaining MySQL fault matrix.

Four further local disposable MySQL probes were rerun successfully on
2026-09-20: `probe_phase4_shadow_schema_mysql.py` (ten table contracts,
microsecond/raw codec round trips, duplicate-subject-key savepoint isolation
and empty downgrade/re-upgrade),
`probe_phase4_shadow_mirror_mysql.py` (concurrent direct/MCP/session fan-in,
worker completion, mirror-fault rollback and a forced one-second InnoDB
subject-lock timeout with no partial authority/event/mirror commit),
`probe_phase4_resumable_backfill_mysql.py` (checkpoint fault, crash/resume,
idempotent replay, two-connection sibling-create, reset and Card-delete races), and
`probe_phase4_external_lifecycle_mysql.py` (external savepoint rollback,
revlog history-only, reset/delete lifecycle and native-vs-external race).
All ran on separate disposable databases; they are a **subset** of P4-11's
required fault matrix, not a full rehearsal pass.

## Open P4-11 / INT-02 gates

1. Extend the environment-matched **small** VPS rehearsal to a representative
   16,424-row, multi-user/overlay workload without treating SSH-tunnel timing
   as server capacity. The source-head-39 DDL reconstruction is not an actual
   head-38 backup. Production application data must not be copied to an
   unsecured local database.
2. Measure migration metadata locks under representative traffic, actual
   storage/row amplification, batch tail latency, retries and a safe quiet
   window. The local probe is not a production rollout limit.
3. Complete the two-connection/fault matrix on a production-matched disposable
   instance. Local probes cover first-create/native fan-in, sibling-create,
   reset and Card-delete versus backfill, and native/external overlap. A
   rekey-versus-backfill race and duplicate-key injection into a real writer,
   deadlock,
   JSON/size, disconnect and worker retry/DLQ failures remain unproven on
   MySQL. SQLite tests and generic fault rollback do not fill those gaps.
4. Re-run the full audit on that representative disposable cohort using a
   SELECT-only principal, then test immediate flags-off runtime rollback.
   The small VPS run passed this path; a reviewed representative
   backup/restore duration/checksum and release abort thresholds remain open.
5. Only after P4-11 passes, run INT-02 `--changed` and `--all`, review all
   uncommitted diffs and issue the Phase 5 go/no-go decision. No Phase 5
   authority cutover follows automatically.

The operational rollback remains: disable shadow write/compare/backfill,
continue serving from `CardProgress`, and retain additive evidence for forward
repair. Do not downgrade production schema as a routine incident response.
