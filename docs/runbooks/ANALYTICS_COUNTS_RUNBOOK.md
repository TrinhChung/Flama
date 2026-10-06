# Analytics count rollout and recovery

Implementation: migrations `20261005_000051` and `20261006_000052`. ReviewEvents and canonical progress remain authoritative. GET never populates or repairs derived counts. Production flags remain raw/off by default.

## Initial rollout

All commands below are prefixed with `flask --app wsgi.py`.

1. Deploy the implementation to **every** HTTP, Study worker, Connect and import process with both writers disabled/read modes raw. Disable startup maintenance/schema mutation; apply `db upgrade` before enabling writers.
2. Enable `REVIEW_ANALYTICS_WRITE_ENABLED=1` on all writers, retaining `REVIEW_ANALYTICS_READ_MODE=raw`. Drain older processes before backfill. Audit maintenance jobs that bypass Session hooks.
3. Run `review-analytics-backfill --user-id 1 --apply --chunk-size 500`. Admission/chunks take short learner fences; full verification uses a read-only snapshot. `--max-chunks 20 --no-publish` bounds a run. Rerun to resume BUILDING; `--restart` admits a new generation for recovery/policy changes.
4. Check `review-analytics-status --user-id 1` and `review-analytics-reconcile --user-id 1`. Observe sampled `REVIEW_ANALYTICS_READ_MODE=shadow`, `REVIEW_ANALYTICS_READ_USER_IDS=1`, sample rate `0.01`. Shadow deliberately executes both readers. Switch the canary to summary only after correctness/latency gates.
5. Roll out Phase B separately: enable `DECK_COUNT_WRITE_ENABLED=1` everywhere with `DECK_COUNT_READ_MODE=raw`; run `deck-counts-invalidate --apply` to establish a new coverage epoch, then `deck-counts-prewarm --user-id 1 --apply`. Validate before switching reads to summary. Unsupported ownership/install scopes stay raw.

Backfill/prewarm default to dry run without `--apply`. The audit app exposes only status/read-only reconciliation, not write commands. Leaving `REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION` empty fingerprints installed TZif data; an explicit operator version must change with supplied timezone rules.

## Keeping Dashboard warm

`DECK_COUNT_PREWARM_USER_IDS=1` configures the first canary. The optional `deploy/flama-analytics-counts.service` / `.timer` invokes `deck-counts-prewarm --configured --apply` about once per minute. Review paths/environment before installing it; this change does not install or enable it.

The explicit configured scope is capped at 100 learners/invocation; it does **not** automatically discover all active learners. Valid keys skip raw aggregation; only dirty/missing direct decks are computed outside requests. `--force` refreshes valid keys too. `deck-counts-status` reports row count, not freshness.

After a review/import, raw fallback may serve that deck until prewarm runs. Worker failure loses performance, not correctness. Snapshots expire at the next study-day boundary even without new events. The job shifts `O(C_dirty)` work out of GET; it does not eliminate the computation. The timer uses `flock` and lower CPU/I/O priority.

## Rollback and coverage gaps

Switch reads to raw first, keeping covered writers enabled whenever possible. Do not drop/reset count tables to roll back the application. Revision tombstones must remain monotonic; resetting them can resurrect stale snapshots.

After disabled writers, an older binary, or SQL maintenance bypassed capture, old READY/hash evidence is insufficient. Before enabling summary again:

- History: enable covered writers with raw reads, drain older processes, run `review-analytics-backfill --user-id <id> --apply --restart` for every served learner; require successful verification/publication.
- Deck counts: enable covered writers/raw reads, run `deck-counts-invalidate --apply`, then prewarm canaries. This advances one global epoch without scanning Cards.

OFF/ON flag toggling alone does **not** prove continuity. Direct `Connection.execute`, `exec_driver_sql`, DB tools, legacy `Session.bulk_*` and external processes bypass Session capture. No current hot application writers using those bypasses were found; maintenance using them must follow recovery above. Session projected history bulk writes are guarded; text history DML is refused while history capture is enabled.

On drift, `review-analytics-reconcile --user-id <id> --invalidate-on-drift` marks only the same failed generation DIRTY and clears proof, returning nonzero. Rebuild with `--restart`. Plain reconcile is read only. Deck publication stores the **captured** dependency vector, so a late race cannot label old counts current.

## Local dump verification

Use the configured loopback MySQL DB and repository venv, without resetting the dump. Probes refuse remote/non-MySQL targets and delete only captured fixture IDs with exact generated email ownership.

```powershell
D:\Project\nihongo\.venv\Scripts\python.exe scripts/probe_review_analytics_mysql.py --env-file D:\Project\nihongo\.env
D:\Project\nihongo\.venv\Scripts\python.exe scripts/probe_deck_counts_mysql.py --env-file D:\Project\nihongo\.env
D:\Project\nihongo\.venv\Scripts\python.exe scripts/bench_analytics_counts_mysql.py --env-file D:\Project\nihongo\.env --apply --repetitions 7
D:\Project\nihongo\.venv\Scripts\python.exe scripts/run_tests.py --module analytics --backend-only
```

Run from the implementation checkout. Benchmark `--apply` builds only User 1 derived data and compares source fingerprints before/after; omit it to measure existing projections. Admission after READY creates another generation; avoid unnecessary rebuilds. RETIRED-generation cleanup is deferred, and raw events remain intact. The deck probe advances the global epoch, so rewarm User 1 afterward before measuring hits.

Timings exclude Flask JSON serialization, Internet transfer and browser rendering. Production p95, concurrent learner write latency and chunk fence duration need canary measurement. Local write overhead exceeds the proposed 5 ms / 10% gate; read improvements alone do not approve broad rollout. See [measurements and remaining linear costs](../reports/ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md).
