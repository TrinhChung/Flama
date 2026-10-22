# RFC-2026-TEST-01: Test architecture and CI improvements

Status: CI P0 implemented locally (shared SPA build, no separate SPA job).
Harness P0 is parked: the hardened `scripts/poc_harness.py` described below was
replaced at 2026-10-23 00:32 by a shim over the earlier `tests/test_harness_poc.py`
draft, so the harness findings and evidence below no longer describe the checkout.
Reviewed: 2026-10-23 (Asia/Tokyo). Follow-up plan:
`docs/plans/TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md`.

## Scope and repository policy

P0 covers trustworthy benchmark results, failure-safe prototype isolation, and
removing the duplicate SPA build in CI. The normal entry point remains
`scripts/run_tests.py`. CI does not activate the POC harness.

Follow `AGENTS.md`: local development, integration tests, JSON/dialect behavior,
concurrency, startup and migrations require local MySQL 8.0. Existing isolated
in-memory unit tests may remain; this RFC does not authorize new SQLite
integration tests. An SQLite auth benchmark cannot qualify MySQL behavior.

## Review findings and implemented fixes

| Priority | Finding in the draft POC | Implemented behavior |
| --- | --- | --- |
| P0 | `--compare` could exit zero when either test run failed | Either failure or mismatched test IDs/counts/skips produces a nonzero exit. Empty suites and invalid repeat counts are rejected. |
| P0 | Cleanup and rate-limit reset exceptions were swallowed | Isolation errors fail the run. Raw connections close in `finally`; remaining apps are still cleaned when one fails. |
| P0 | Cleanup depended on `tearDown`, which unittest omits after failed `setUp` | The wrapper registers `addCleanup` before setup, so restoration also runs after setup failure and after all original test cleanups. |
| P0 | Lookup preservation used role codes/names and retained mutations to default rows | Restore a full database snapshot captured after app startup/first schema creation, including all seed rows, deleted/updated roles and generated IDs. |
| P0 | FK re-enablement could be ignored inside the cleanup transaction | No bulk-delete FK toggle is used. Restore and verify the profile's original FK setting; this preserves existing test semantics rather than silently changing them. |
| P0 | Every activation could wrap classes again; imported factory aliases and global hooks escaped a run | Wrapping is idempotent. Each run owns a harness and restores class methods, module aliases, factory and DDL hooks in `finally`. |
| P0 | Benchmark import changed environment globally; comparison reused warm imports and patched objects | Scoped test environment/media directories; baseline and POC comparisons run in independent Python subprocesses. JSON stdout is separate from diagnostics. |
| P0 | Destructive cleanup lacked a target contract | Require explicit `TESTING=True`, exactly `sqlite:///:memory:` and no binds. Only harness-owned apps can be restored. No MySQL cleanup adapter is inferred. |
| P0 | An intentionally crashing top-level test made normal discovery fail | Lifecycle regression tests nest expected failures and assert their results, using mocks without creating an integration database. |
| P1 | SPA contract repeated `npm ci` and `build:ci` on another runner | Execute Flask assertions beside the existing frontend build and remove the `spa-contract` job. The private Free-plan repository has no branch protection (API 403), so no required check name needs preserving; a pass-through job would still bill a rounded runner minute. |

## Implemented CI topology

`.github/workflows/ci.yml` now runs:

1. `changes`: existing event-range and deployed-release selection.
2. `frontend`: existing lint, typecheck, selected/full tests, one Vite build and
   deployment-config check. If `spa_contract=true`, install Python requirements
   and verify `tests.test_spa_artifact_contract` against that same build.
3. `backend`, `redis-contract`, `mysql-contract`: existing coverage and gates.
4. `deploy`: existing master-only runtime-change gate, now needing
   `[changes, frontend, backend, redis-contract, mysql-contract]`. A failed SPA
   contract fails `frontend`, which still blocks deployment.

The SPA test initializes Flask with startup maintenance and connectivity checks
disabled. Serving static bytes requires no database schema or connection. It
keeps the normal lazy MySQL configuration and disposes its engine afterward.
The contract guards `Engine.connect` so even a swallowed connection attempt
fails the test, independently of whether local MySQL happens to be available.

No Actions artifact transfer is used, so storage quota is not a prerequisite.
The workflow already cached pip and npm dependencies before this change; P0
also enables the pip cache on the frontend runner for its SPA assertions.

This removes one runner, one npm installation and one Vite build per selected
SPA contract run. Over the 30 days to 2026-10-23 the separate job billed about
41 rounded minutes; hosted savings after this change have not yet been measured.

## Prototype contract and limits

`scripts/poc_harness.py` remains an opt-in experiment for the eight existing
auth test modules selected in `scripts/poc_test_runner.py`. It is not a generic
replacement for the test lifecycle and is never activated by the modular runner.

The prototype caches apps by explicit config, environment and audit mode, restores deep
config copies, snapshots each owned in-memory database, resets the six existing
rate-limit services and limits the number of cached profiles. DDL calls for
unowned apps retain their normal behavior. Shutdown disposes engines and closes
snapshots rather than keeping a singleton cache alive across runs.

The earlier `tests/test_harness_poc.py` draft was being edited by another session
during this review. It is preserved separately and is not imported by the POC
runner or its safety tests. Use `scripts/poc_harness.py` for this implementation.

Database/config restoration does not establish complete Flask object isolation:
extensions, registered callbacks, WSGI middleware and arbitrary process caches
can still require module-specific reset contracts. No expansion to other
modules, parallel workers, schema tests or MySQL is approved by this P0 result.

The initial draft's 39.46s/20.62s comparison and 48% speedup were historical
observations without a trustworthy cold-process comparison contract. They are
not acceptance criteria or verified performance claims. Three successful runs
show no observed repeat failure; they do not prove zero flakiness. Timing while
`tracemalloc` is active includes instrumentation overhead and depends on host load.

## Local verification

Use the repository virtualenv in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_adversarial_poc_harness.py tests/test_poc_test_runner.py tests/test_ci_workflow.py tests/test_modular_test_runner.py tests/test_test_mapping_coverage.py --backend-only

$env:FLAMA_REQUIRE_REAL_SPA_ARTIFACT = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_spa_artifact_contract.py --backend-only
Remove-Item Env:FLAMA_REQUIRE_REAL_SPA_ARTIFACT
```

The SPA command requires an existing `frontend/dist` produced by
`npm --prefix frontend run build:ci`; CI builds it in the same job. Keep this
test enabled with `FLAMA_REQUIRE_REAL_SPA_ARTIFACT=1` so absence is a failure.

Opt-in checks of the existing auth prototype:

```powershell
.\.venv\Scripts\python.exe scripts/poc_test_runner.py --compare --json
.\.venv\Scripts\python.exe scripts/poc_test_runner.py --poc --repeat 2 --shuffle 42 --json
.\.venv\Scripts\python.exe scripts/test_repeatability_benchmark.py
.\.venv\Scripts\python.exe scripts/stress_test_poc_adversarial.py
```

`--compare` launches a fresh process for each side. `--repeat` repeats those
isolated runs; comparison timing includes process startup and shutdown, and
in-process timing includes harness imports on the POC side. The repeatability
script instead runs three complete lifecycle
activations in one process, shuffled with seed 42 by default, and writes
`output/poc-repeatability.json`; it derives
case identity from loaded tests rather than hardcoding 107. None of these
commands verifies live MySQL semantics or deployment.

Local review evidence (2026-10-23):

| Check | Result |
| --- | --- |
| Focused tooling, isolation, CI/deploy and real SPA contracts (7 files) | 80 tests passed |
| Fresh `npm --prefix frontend run build:ci` | Passed |
| Independent baseline and hardened POC executions | Both 107/107 passed; identical case IDs and outcomes |
| Same-process repeatability, shuffled seed 42 | Three runs of 107/107 passed after fixing first-import factory alias restoration |
| Workflow YAML parse, ordering and deploy dependencies | Passed locally; hosted Actions execution remains unverified |
| `git diff --check` | Passed |

Performance percentages are deliberately not accepted from these local runs:
host load varied and instrumentation is enabled. No MySQL schema, data or
production deployment was changed.

## Deferred changes and acceptance gates

Keep current PR and master MySQL/migration/Redis gates. The draft did not provide
an exact, reviewed list of 22 historical suites or sufficient evidence that those
suites have no active regression value. `tests.test_shared_state_services` is
the Redis contract actually used by CI; it must not be removed based on a claim
about another filename. Master still forces full validation before deploy.

Before moving any tests to nightly, inventory exact test IDs, active source
dependencies and trigger coverage. Migration changes must retain immediate
MySQL replay, and release checks must run against the exact candidate revision.

Future rollout requires:

- Separate pure unit logic from integration setup without losing assertions.
- Design and measure an owned disposable MySQL schema/session lifecycle.
- Prove isolation after setup/teardown/cleanup failures and committed writes,
  including reference mutations, multiple apps and environment changes.
- Compare executed case IDs and outcomes across baseline, repeated and shuffled
  runs; test all global/extension reset contracts for each enrolled module.
- Measure uninstrumented cold runs and CI costs before accepting latency targets.
- Consider fake timers and frontend setup changes separately, with relevant
  React/FSD guidance and focused tests. No frontend source is changed in P0.
