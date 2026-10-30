# Published Base: review corrections and evidence

Subsequent execution: exact script receipts reduced the draft proposal to six
Notes / 23 Fields, the owner approved it, and production cutover completed.
See the [production result](NOTE_PUBLISHED_BASE_PRODUCTION_CUTOVER_2026-10-30.md).
This document retains the earlier review/rehearsal record below.

The pre-cutover review corrections are verified locally. The owner requested
continued deployment and explicitly approved all six manual Notes / 31 Fields.
Production data conversion is not yet executed in this record; P6 follows
the production soak and its separate operational checks.

## Review disposition

| Item | Result and evidence |
|---|---|
| R1, quadratic draft reads/flushes | Transaction-local ID lookup with 500-ID batches, Draft lifecycle updates, current-row reconciliation and schema caches protected by the existing parent X lock. Rollback/savepoint clears caches and expires Core-updated ORM revision attributes. Final property benchmark is below. |
| R2, private drafts | Foreign/anonymous HTTP readers receive Base; foreign writes fail before replacing a draft. Trusted bearer identities survive the Connect transaction boundary. Non-HTTP author jobs can select `note_author_view(owner_id)`. |
| R3, study install scans | Filter installs by source owner/type and source-root ancestors before constructing scopes. The 1-versus-5-install MySQL query-count test passes. |
| R4, measurements | Sequential requests alternate legacy/Base order, with SQL/CPU/page counters and EXPLAIN. Added 10/1,000/10,000-Note publication and four independent worker processes. These are qualification samples, not sustained capacity results. |
| R5, owned search/sort | A materialized sparse key relation avoids a Draft PK miss per Base Note; values use one joined Draft with a no-draft branch. Carry explicit visibility into the ranked CTE, reuse it for total/page, and bind small owned field schemas once for word sorting. More than 200 field definitions uses the existing scoped fallback. Search page-read ratios meet the approximate 1.2x target. |
| R6, publication fences | Ordinary saves lock covering source-root heads through their existing unique index. Field schema changes retain the all-listing fence. Current Base/draft destinations get a late NOWAIT fence; tree reparenting also bumps affected heads. A validated head snapshot permits sparse PK publication with shared field locks, without a global NoteType X lock. Two-connection sibling-save and stale-move tests pass. |
| R7, edit timestamps | Author DTOs and secondary sort use max(Base time, Draft time). Learners retain Base time. Untouched content/metadata follows a concurrently published Base rather than becoming an unintended revert draft. |
| R8, retention scheduling | Daily timer, exclusive runner lock, bounded batches/time, atomic resumable cursor and JSON journal records. Disabled runs skip app/DB initialization. Enabled maintenance uses the audit factory, avoiding WSGI startup repair. Activation/rollback quiesces and restores the timer explicitly. Units are prepared locally, not installed on production. |
| R9, contraction | [P6 owner, entry/exit checks and removal inventory](NOTE_PUBLISHED_BASE_P6_CHECKLIST_2026-10-30.md). No historical table has been removed. |
| R10, SPA moves | 82 static routes/aliases, two viewports, 328 screenshots against `690933ab`. The audit caught and corrected 43 feature route loaders resolving a second `React.lazy` object. Build and subsequent route captures pass. |
| R11, owner review | The private list remains six Notes / 31 Fields from the fresh rehearsal, explicitly approved by the owner on 30 October. Fresh target content/classification must still match before apply. |

Additional retention protection checks the canonical logical Note key when the
advisory `live_note_id` FK is null. Publish and the 90-day purge retain that
identity; the MySQL regression covers both operations. Existing indexes are used;
no index declaration or DDL was added by these corrections.

## MySQL validation

The focused backend/deployment run passes **130 tests**, with one existing POSIX
symlink case skipped on Windows. This includes the original cutover suite,
ownership/privacy, pending/delete/detach/rollback cache lifecycle, concurrent
metadata, typed JSON booleans/numbers, arrays, escaped JSON keys, word ordering,
publication fences and retention cursor recovery. Study experiment env flags
were blanked for these processes; integration runs use disposable local MySQL.

A final **read-only** pass against the fresh production copy checks:

- All 41,874 author named-value reads: zero mismatches.
- All 31,080 converted published Note images against the reviewed working hashes:
  zero mismatches.
- All six current manual drafts read as a foreign actor: Base only, zero leaks.

The real `wsgi.py` entry point also passes under a MySQL read-only connection:
passive startup, `/api/session` 200, retention dry run and NoteType batch-publish
preview both exit 0. Production data/config remain unchanged.

## R1 final property benchmark

The review's same-session benchmark was rerun after the corrections. The 5,000
Note case reads all properties, then edits/flushed 1,000 Notes:

| Mode | Read 5,000 | Read SQL | Write 1,000 | Write SQL |
|---|---:|---:|---:|---:|
| Flag off | 0.303 s | 3 | 8.634 s | 8,000 |
| Published Base | 0.440 s | 13 | 8.782 s | 7,006 |

Read time is 1.45x; write time is 1.02x. The extra page read queries are bounded
500-ID chunks, not one per Note. These timings are local warm-cache observations.

## Sequential request measurements

[Raw per-request metrics and EXPLAIN](NOTE_PUBLISHED_BASE_REVIEW_BENCHMARK_2026-10-30.json)
record 10,000 Notes, 100 installs, 1.8 KB synthetic padding, two alternating-order
samples per mode/scenario, and four process workers. Runtime MySQL buffer pool is
1 GiB, 8 x 128 MiB chunks; configured local target remains 128 MiB, with no
persisted pool setting. No resize or restart was performed.

Medians below are per request. “Pages” means `Innodb_buffer_pool_read_requests`
delta, not disk reads. All final request signatures match between modes.

| Author drafts | Search legacy / Base | Search pages legacy / Base | Word sort legacy / Base | Sort pages legacy / Base |
|---:|---:|---:|---:|---:|
| 0 | 289 / 296 ms | 84,703 / 80,384 | 852 / 277 ms | 50,059 / 50,227 |
| 200 | 294 / 417 ms | 79,091 / 81,574 | 778 / 268 ms | 50,065 / 51,107 |
| 2,000 | 293 / 512 ms | 82,852 / 92,466 | 696 / 360 ms | 50,069 / 56,347 |

Search logical reads are 0.95x / 1.03x / 1.12x respectively. Search latency still
increases at the nonzero draft densities. Author due-sort Browse also remains
more expensive: Base medians 188/247/270 ms and 50.3k/51.2k/56.7k logical reads,
versus legacy 112/115/113 ms and about 35.4k reads. The tombstone/metadata predicates
and plan choice still require more Base-row work. This is recorded as a tradeoff,
not hidden by the faster word sort; no index was added to mask it.

| Published Notes | Time | SQL statements | First lock query to return, upper bound |
|---:|---:|---:|---:|
| 10 | 166 ms | 56 | See raw record |
| 1,000 | 1.56 s | 1,038 | See raw record |
| 10,000 | 14.72 s | 10,074 | See raw record |

The SQL count grows with version-checked Note writes, not subscriber fanout.
The raw record separates DBAPI wall, process CPU and wall outside DBAPI. These
overlap and must not be added together as server CPU. The lock window includes
wait/planning/client work; zero global row-lock wait deltas do not prove zero
lock residency. A pre-existing older RR snapshot uses the conservative serialized
current-read publication path; normal matching-snapshot publication uses the
narrow fences tested above.

The original-order legacy zero-override query was also rerun at 1 VU with EXPLAIN:
Browse ~404 ms, search ~2.95 s and Study page ~511 ms **including EXPLAIN overhead**.
The previous 235–345 second concurrent outlier was not reproduced by that probe;
its precise cause remains unqualified. The old 10-thread table is withdrawn as
latency/capacity evidence. Full sustained 25/50/100 VU Study commits and the wider
matrix remain P6 work; the runtime pool must not be changed to obtain that table.

## Frontend evidence

[Route audit metadata](NOTE_PUBLISHED_BASE_ROUTE_QA_2026-10-30.json) records 82
static routes/aliases at 1440x1000 and 390x844. All 328 final captures settle with
no error boundary or JavaScript page error. Of 164 before/after pairs, 144 match
pixels exactly. The remaining regions were inspected: animated mascot/charts,
minor transient paint and the QA origin port shown in feedback fields; no
unintended layout/palette change was found. This is not an audit of every
parameterized detail/editor state. Earlier focused comparison/render evidence
remains relevant to those flows.

TypeScript, SPA and MCP builds pass. Vitest's expanded 66-file run passes 592 of
593 cases initially; the 400-row DeckTree browser-find case times out under the
parallel build. Its focused rerun passes all seven cases without a code change.
The initial timeout is retained in the evidence rather than reported as a clean
single-run pass.

## Operational disposition

Use the [updated runbook](../runbooks/NOTE_PUBLISHED_BASE_CUTOVER_20261029.md).
The owner approved the six private Notes. Preserve the verified backup/manifest and refresh
target state, comparing the manual export with that approval before production conversion. The explicit owner reply is recorded privately. CI/deployment and cutover receipts
will extend this record; no P6 history is removed before its operational gates.
