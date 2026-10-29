# Published Base local validation, 2026-10-29

Implementation: [ADR](NOTE_PUBLISHED_BASE_IMPLEMENTATION_2026-10-29.md).
Operations: [cutover runbook](../runbooks/NOTE_PUBLISHED_BASE_CUTOVER_20261029.md).
Production has not been changed. This report establishes local readiness and
records the remaining P4/P6 gates; it does not approve a production manifest.

## Environment and isolation

- Branch `feat/note-published-base-20261029`, isolated worktree
  `D:/Project/nihongo-note-base-20261029`, based on `86231d25`.
- Local MySQL 8.0.40. Running buffer pool: 1,073,741,824 bytes, eight instances,
  134,217,728-byte chunks. `my.ini` targets 128M; no persisted buffer pool variables.
  No resize, restart or new secondary index was performed.
- A 1.408 GB dump of local production-copy schema
  `flama_prod_rehearsal_20261025_idx` was restored to generated schema
  `flama_note_base_rehearsal_20261029_8c374786` (116 tables). The source schema and
  configured development DB were not modified. Restore took about 200 seconds.
- Integration tests and synthetic load use independently generated disposable
  MySQL schemas. The original checkout and its unrelated changes are preserved.
- Frontend dependencies were reused through a verified junction from this worktree
  to `D:/Project/nihongo/frontend/node_modules`. No dependencies were installed.
  A verified `.venv` junction reuses `D:/Project/nihongo/.venv` for the repository's
  commit hook, which otherwise selects the Windows Store `python3` stub.

## Expansion, cutover and rollback

Alembic 74 → 75 → 76 was exercised on the restored MySQL schema. The initial
expansion took 4.291 s, 387,870 logical page requests and 968 disk page reads.
Migration 76 introduces only the approved expansion; `note_drafts` has its PK
and no additional secondary index. Restart/retry coverage verifies interrupted
backfill completion and preservation of an already populated schema snapshot.

The optimized second rehearsal below ran on the already expanded copy. Its
0.156 s expansion probe was an idempotent rerun, not a fresh DDL measurement.

| Operation | Seconds | Δ logical page requests | Δ disk page reads |
|---|---:|---:|---:|
| Read-only manifest | 8.402 | 376,977 | 0 |
| Apply | 4.341 | 69,173 | 4 |
| Author parity check | 3.372 | 48,231 | 0 |
| Rollback | 2.475 | 65,446 | 7 |
| Reapply | 4.375 | 67,439 | 2 |

These are shared-server global counter deltas, not isolated per-query accounting.
They establish bounded local operation, not production latency predictions.

- 30,834 Notes received Published Base membership; all 29 install metadata rows
  were handled by the one-time cutover.
- 250,708 script-classified journal entries remained current Base content.
  Of 39 manual journal entries in current membership, 24 effective Field changes
  produced sparse drafts on seven Notes; unchanged values produced no draft delta.
- The original plan's count of 47 manual entries was not reproduced. A read-only
  source audit found 59 non-script entries overall, including 20 outside current
  membership. Fresh production classification and owner review are still required.
- All 41,623 author Notes matched before versus Base + draft, with zero mismatches.
  Rollback restored exact per-Note hashes.
- Checksums for progress subjects (`4239374805`), review events (`3894585596`),
  clone mappings (`1350227590`), overrides (`0`) and local additions (`0`) matched
  before/after rollback. This copy contains zero override/addition rows; nonempty
  preservation is covered separately by MySQL tests.
- Final active rehearsal manifest SHA-256:
  `7a303807cd2bf508221c7442385e350ae4ce84b51e3b6d80d045a24232c67df7`.
  The generated copy was left in the reapplied Base state for read-only inspection.

Private manifests, review values, receipts and database dumps stay under ignored
`output/`; they are excluded from Git. The seven-Note review export includes each
Field's proposed Base, author value, presence and last writer evidence. It is a
review of the local copy, not approval for a newer production database.

## Functional and browser evidence

The four new MySQL suites passed 53 tests, covering draft isolation and metadata reversion, arrays,
JSON null/presence, author versus public search, clone effective SQL before
pagination, current schema/template pins, publication rollback/idempotency,
nonzero personal edits, deletion/reference retention, retention pagination and
multi-listing schema publication. Concurrency cases explicitly establish an older
REPEATABLE READ snapshot before another connection commits source/schema/template
or override changes. The publisher must observe those commits after its locks.

Existing identity, template pin, release API, dirty tracking, rebase, automatic
publication and Study artifact suites passed 115 tests with the flag disabled.
Existing count projection/snapshot suites passed another 47 tests. Deployment
configuration/rollback selections passed 43 cases with one Windows-inapplicable
POSIX symlink case skipped. The MySQL cutover suite checks the active-Base code
rollback refusal and this branch's declared capability on the real database.
These established isolated tests retain their original test harness; new DB
integration/migration/concurrency cases run exclusively on real MySQL.

Frontend validation passed 83 tests across collaboration, comparison route
selection, Browse markers, marketplace, auth and Study content synchronization.
`npm run build` passed, including TypeScript and the MCP build.

An isolated Chrome profile exercised the built Flask-served SPA at desktop
1440 × 1000 and mobile 390 × 844. Both comparison actions worked: deleting an
override selected latest Base; keeping an override cleared the changed marker
after a browser reload while retaining its personal nested-array value. The final
comparison browser session had zero console errors/warnings. Screenshots are in
ignored `output/playwright/`. This is visual inspection of the new flow, not an
automated pixel comparison of every existing page.

Rendering sampled six distinct current author template/NoteType combinations
against their cutover-pinned equivalents, using 49 nonempty native array values.
All 12 front/back HTML comparisons and all 12 rendered text DOM comparisons
matched; no raw `$` face or empty face appeared. Manual-draft Notes were excluded
from that rendering sample because their author and learner values intentionally
differ. It does not establish every Note/template/media permutation: the static
render fixture did not serve every media/proxy asset and reported renderer CSP/
missing-asset diagnostics. Media availability and a complete deck DOM audit remain
production smoke checks. The sample does not independently prove every possible
accidental `String(array)` comma join is absent.

## Load qualification and delivery gates

The reproducible load harness is
[`scripts/bench_note_published_base_mysql.py`](../../scripts/bench_note_published_base_mysql.py).
It runs Browse, effective search and the Study page query on identical synthetic
10,000-Note content with 100/1,000 installs and 0/20/1,000 personal overrides per
active install. It compares response signatures and reports p50/p95, page reads,
CPU, sampled RSS, temporary tables and publish statements. See the accompanying
benchmark JSON and result table for the final 10-VU qualification run.

Final raw results: [synthetic benchmark JSON](NOTE_PUBLISHED_BASE_BENCHMARK_2026-10-29.json).
Every comparison had matching response signatures and no request errors. Each
cell below is legacy → Base p95 in milliseconds (only ten samples per operation,
so p95 equals the sampled maximum).

| Installs | Overrides / active install | Browse p95 ms | Search p95 ms | Study page p95 ms |
|---:|---:|---:|---:|---:|
| 100 | 0 | 345,478 → 1,029 | 2,557 → 2,254 | 792 → 1,226 |
| 100 | 20 | 1,272 → 1,153 | 4,318 → 2,844 | 1,042 → 925 |
| 100 | 1,000 | 1,434 → 1,065 | 4,394 → 3,423 | 1,000 → 1,478 |
| 1,000 | 0 | 262,107 → 1,126 | 2,711 → 2,397 | 873 → 1,368 |
| 1,000 | 20 | 1,259 → 964 | 5,019 → 2,795 | 1,259 → 1,280 |
| 1,000 | 1,000 | 1,201 → 888 | 4,938 → 3,217 | 1,371 → 1,039 |

| Installs | Overrides | Logical page requests, legacy → Base | Disk reads | SQL statements, legacy → Base |
|---:|---:|---:|---:|---:|
| 100 | 0 | 1,703,922,076 → 2,917,191 | 0 → 0 | 802 → 842 |
| 100 | 20 | 9,801,094 → 3,682,041 | 0 → 0 | 801 → 841 |
| 100 | 1,000 | 9,353,476 → 3,548,988 | 0 → 0 | 801 → 841 |
| 1,000 | 0 | 1,549,632,083 → 2,959,281 | 0 → 0 | 802 → 842 |
| 1,000 | 20 | 9,794,633 → 3,690,906 | 0 → 0 | 801 → 841 |
| 1,000 | 1,000 | 9,387,583 → 3,617,866 | 0 → 0 | 801 → 841 |

Page/SQL deltas cover the whole 30-request measurement, not one HTTP request.
Sampled Python RSS was approximately 175–187 MiB; CPU was 2.14–3.34 s per
measurement. Base used more SQL statements despite touching fewer logical pages.
Study page latency was mixed and regressed in four of the six short samples.

The zero-override legacy Browse path reproduced unusually expensive runs, with
262–345 s p95 and 1.55–1.70 billion logical page requests. The exact expensive SQL
plan was not captured with EXPLAIN in this run; this is an unresolved baseline
finding, not evidence for adding an index or a general speedup multiplier. The
harness always ran legacy before Base without cache flushing or randomized order,
which can bias timing and plan/cache warmup. No index or server setting was changed.

Publishing one changed Note executed **47 SQL statements and zero statements
against `deck_installs`** at both 100 and 1,000 installs. Measured time was 207 ms
and 103 ms respectively. This verifies subscriber independence for this fixture;
it does not measure publication of 10,000 changed Notes or concurrent write load.

P4 requires a fresh production-copy rehearsal, the exact reviewed manual-draft
manifest, stopped writers, a verified dump, coordinated deployment, smoke checks
and a no-publish soak. The rollback tool deliberately refuses unsupported
post-cutover dispositions or rollback after the first new publication.

P6 remains pending: remove obsolete historical runtime paths/tables after soak,
then run the full 25/50/100-VU and 128M/1G/2G matrix using isolated server instances
or coordinated operations. Current short 10-VU runs do not establish sustained
capacity, full Study session/review latency, cold-cache behavior or write-workload
cost. No production performance claim follows from this report.
