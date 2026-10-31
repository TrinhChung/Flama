# Stress-test follow-up: install locks, worksheet SVG and media offload

Date: 2026-10-28. Scope: the three small follow-ups selected from the local report
`docs/architecture/CONCURRENCY_STRESS_TEST_REPORT.md` (a separate local artifact).
Application fixes are local; no application deployment or service restart was performed.

The source report and its original telemetry/harness were subsequently preserved
on the local archive branch `archive/local-pending-20261031`. Read the report with
`git show archive/local-pending-20261031:docs/architecture/CONCURRENCY_STRESS_TEST_REPORT.md`.
The archive's approval labels and old main-database stress scripts are retained
as historical material, not current qualification or a runnable P6 test suite.

## Install locking

- Deck NoteType installation and complete NoteType release receipts now acquire
  locks in the same order: installing user, source NoteType, install receipt.
- The source takes an exclusive lock before child foreign-key inserts or
  autoflush can acquire shared locks and cause the observed counter lock upgrade.
- After waiting, receipt and local-copy existence checks use current locking
  reads. This also prevents duplicate local copies when two requests from one
  user started with an older MySQL REPEATABLE READ snapshot.
- Counters stay synchronous in the existing transaction. Existing rollback/retry
  behavior and overlay-only source Note ownership are preserved.
- Installs sharing one source serialize until transaction completion. This fix
  addresses the observed upgrade cycle; it does not guarantee all possible
  cross-domain deadlocks are eliminated.

## Worksheet SVG

- Added a per-worker LRU of 256 SVG strings; files larger than 64 KiB bypass it.
  Cache keys include the absolute file path, size, mtime and ctime. Every lookup
  stats the file, so normal replacement/deletion is observed; misses are not cached.
- Static SVGs no longer resolve the upload directory for each character, either
  during the existence preflight or during content loading. Library fallback,
  locale/padded filenames and SVG bytes are preserved.
- XML parsing and output styling were not rewritten. The report's `kanji_stroke`
  workload resolves to `kanji_compact`, so XML decomposition was not established
  as the cause of its measured latency.

### Local paired measurement

Baseline functions were taken from Git `0c70cbba`; optimized functions came from
the working tree. Both ran on the same rollback-only MySQL fixture with 30 notes
containing 30 distinct characters whose SVGs already existed locally. The service
used the legacy `kanji_stroke` template alias, `first_n`, limit 30, five rows per
page and explicit Japanese locale. Four batches per variant alternated order;
each batch was warmed once and measured 15 times, for 60 measured calls each.
Every baseline/optimized response was compared for equality.

| Measurement | Baseline | Optimized |
|---|---:|---:|
| Median service time | 28.180 ms | 8.487 ms |
| Mean service time | 29.924 ms | 9.743 ms |
| GLOBAL `Innodb_buffer_pool_read_requests` delta | 6,985 | 6,918 |
| GLOBAL `Innodb_buffer_pool_reads` delta | 0 | 0 |

Median improved about 70%. This measures warm local service calls, including
querying/formatting, without HTTP queueing. It is not a repeat of the original
12-user burst or a production latency claim. GLOBAL counters can include other
connections; the small read-request difference does not establish a SQL gain.

Environment: Windows, MySQL 8.0.40; runtime buffer pool 1,073,741,824 bytes,
eight instances, 134,217,728-byte chunks; no persisted buffer-pool overrides.
`my.ini` targets 128M/eight instances. No resize, restart, index or DDL was used.

## Production media verification

Read-only SSH checks confirmed:

- `flama.service` was active, and its running process had
  `MEDIA_PROXY_USE_XACCEL=true` and media root `/var/lib/flama/media`.
- `nginx -T` succeeded. The active `/internal-media/` location was `internal`,
  aliased the same root and enabled `sendfile`.
- A HEAD request for an existing local asset directly to the running Flask
  upstream returned HTTP 200, the matching `X-Accel-Redirect`, and an empty body.

Media offload is already enabled; no production configuration change was needed.
This check did not benchmark Nginx/CDN transfer throughput.

## Verification

Run from the repository root in PowerShell:

```powershell
$env:FLAMA_MYSQL_TESTS='1'
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_note_type_install_locking_mysql.py tests/test_worksheet_stroke_cache.py tests/test_worksheet_preview_mysql.py tests/test_deck_release_performance_mysql.py tests/test_modular_test_runner.py tests/test_parallel_backend_runner.py --backend-only --jobs 1
```

Result: **135 cases, 134 passed, one platform skip** (POSIX signal forwarding on
Windows), zero failures/errors. The MySQL cases exercised concurrent distinct-user
and same-user installs, mixed entry points, rollback/counter integrity, deleted-copy
restoration, published schema pinning and full deck overlay installation. Worksheet
checks covered cache invalidation/fallbacks, native arrays, exact preview/print-HTML
parity for compact/step-by-step Japanese/Chinese options, access isolation and the
synchronous HTTP contract. SQL fixtures used the existing loopback schema without
DDL; synthetic committed account fixtures were removed after each test.

New regression files are registered with their test-runner domains.
`git diff --check` passed. The existing unrelated working-tree changes were preserved.
