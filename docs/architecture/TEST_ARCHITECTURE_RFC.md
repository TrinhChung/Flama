# RFC-2026-TEST-01: Test architecture and CI improvements

Status: CI P0 committed on `fix/deploy-disconnect-cloudflare` (shared SPA build,
no separate SPA job); hosted Actions execution is not yet verified. The harness
prototype is parked on the local branch `experiment/test-harness-poc` and is not
included in the committed CI branch content. Reviewed: 2026-10-23 (Asia/Tokyo). Follow-up plan:
`docs/plans/TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md`.

Coordination review, 2026-10-23: the working tree now contains untracked prototype
files and in-progress archive/Worksheet changes from other sessions. Their
presence does not activate or qualify the parked harness. The implementation
plan's section 10 records the coverage findings and current acceptance gates;
[the task queue](../plans/MULTI_AGENT_TASK_QUEUE.md) records proposed ownership.
H1/H2/H3 remain parked. PR B was merged from Claude and hardened in commit
`11422541`; 156 focused tooling cases (one POSIX skip) matched across sequential
and seeded parallel runs, including a clean checkout. Full-suite/Linux hosted
acceptance is pending, and push/PR jobs stay at one worker. S2 keeps all 22 tests
at their original paths. This review did not execute MySQL integration/probes.

## Scope and repository policy

P0 covers trustworthy benchmark results, failure-safe prototype isolation, and
removing the duplicate SPA build in CI. The normal entry point remains
`scripts/run_tests.py`. CI does not activate the POC harness.

Follow `AGENTS.md`: local development, integration tests, JSON/dialect behavior,
concurrency, startup and migrations require local MySQL 8.0. Existing isolated
in-memory unit tests may remain; this RFC does not authorize new SQLite
integration tests. An SQLite auth benchmark cannot qualify MySQL behavior.

## Prototype review findings

Codex implemented these fixes in a hardened harness, which another agent then
overwrote in the working tree with the earlier draft. The parked draft still has
every defect below, so this column is the behavior a future harness must prove.

| Priority | Finding in the draft POC | Required behavior |
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

## Implemented CI topology

The separate SPA contract job repeated `npm ci` and `build:ci` on another runner.
Its assertions now run beside the existing frontend build, and the job is gone.
The private Free-plan repository has no branch protection (API 403), so no
required check name needs preserving; a pass-through job would still bill a
rounded runner minute.

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

## Parked prototype and limits

The local branch `experiment/test-harness-poc` holds the Antigravity draft as of
2026-10-23 00:34: `tests/test_harness_poc.py` (`FastTestHarness`), its re-export
`scripts/poc_harness.py`, `scripts/poc_test_runner.py` for eight auth test modules,
`scripts/test_repeatability_benchmark.py`, `scripts/stress_test_poc_adversarial.py`,
their two tooling tests and their `tooling` mapping in `scripts/run_tests.py`.
CI and the modular runner never activate it. Its own tooling tests pass there
(20 tests); no MySQL behavior was checked.

The hardened Codex harness is in no branch. Its patches remain in the local Codex
session log `~/.codex/sessions/2026/10/22/rollout-2026-10-22T23-50-19-01a16417-6dd1-7cc3-9137-1de6593730e4.jsonl`;
rebuilding it means replaying about 25 add, update and delete patches in order,
which has not been attempted.

Database/config restoration does not establish complete Flask object isolation:
extensions, registered callbacks, WSGI middleware and arbitrary process caches
can still require module-specific reset contracts. No expansion to other
modules, parallel workers, schema tests or MySQL is approved by this P0 result.

The initial draft's 39.46s/20.62s comparison and 48% speedup were historical
observations without a trustworthy cold-process comparison contract. They are
not acceptance criteria or verified performance claims. Timing while
`tracemalloc` is active includes instrumentation overhead and depends on host load.

## Local verification

Use the repository virtualenv in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_ci_workflow.py tests/test_deploy_workflow.py tests/test_modular_test_runner.py tests/test_test_mapping_coverage.py --backend-only

$env:FLAMA_REQUIRE_REAL_SPA_ARTIFACT = '1'
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_spa_artifact_contract.py --backend-only
Remove-Item Env:FLAMA_REQUIRE_REAL_SPA_ARTIFACT
```

The SPA command requires an existing `frontend/dist` produced by
`npm --prefix frontend run build:ci`; CI builds it in the same job. Keep this
test enabled with `FLAMA_REQUIRE_REAL_SPA_ARTIFACT=1` so absence is a failure.
A worktree without `.env` also needs the CI values `DB_USER=ci`, `DB_NAME=ci`
and `SECRET_KEY=ci-secret`; the test never connects to that database.

The prototype's committed opt-in commands are on `experiment/test-harness-poc`.
Untracked copies have reappeared in the current checkout; they remain unqualified
and are not approved for activation or inclusion in the CI rollout.

Local evidence for the CI commit, in a clean detached worktree (2026-10-23):

| Check | Result |
| --- | --- |
| `tests.test_ci_workflow`, `tests.test_deploy_workflow`, `tests.test_modular_test_runner`, `tests.test_test_mapping_coverage` | 57 tests passed |
| Fresh `npm ci` and `npm run build:ci` | Passed |
| Real SPA contract with `FLAMA_REQUIRE_REAL_SPA_ARTIFACT=1` and the CI env values | 2 tests passed |
| Workflow YAML parse, `needs` resolution, `Build` before the SPA step | Passed |
| `git diff --check` | Passed |
| Hosted GitHub Actions run | Not yet run |

No MySQL schema, data or production deployment was changed.

## Deferred changes and acceptance gates

Keep current PR and master MySQL/migration/Redis gates. The draft did not provide
an exact, reviewed list of 22 historical suites or sufficient evidence that those
suites have no active regression value. `tests.test_shared_state_services` is
the Redis contract actually used by CI; it must not be removed based on a claim
about another filename. Master still forces full validation before deploy.

Before moving any tests to nightly, inventory exact test IDs, active source
dependencies and trigger coverage. Migration changes must retain immediate
MySQL replay, and release checks must run against the exact candidate revision.

Future shared-harness/schema-reuse rollout requires the gates below. PR B instead
uses subprocess isolation under implementation-plan section 6.2; it does not
require introducing shared database fixtures merely to schedule workers.

- Separate pure unit logic from integration setup without losing assertions.
- Design and measure an owned disposable MySQL schema/session lifecycle.
- Prove isolation after setup/teardown/cleanup failures and committed writes,
  including reference mutations, multiple apps and environment changes.
- Compare executed case IDs and outcomes across baseline, repeated and shuffled
  runs; test all global/extension reset contracts for each enrolled module.
- Validate selection as well as discovery: explicit missing test files must fail,
  nested test edits must select their cases, and rename consumers/relative fixture
  paths must remain valid. Preserve ID multisets and outcomes after an explicit
  old-to-new rename map; equal counts alone do not establish coverage parity.
- Measure uninstrumented cold runs and CI costs before accepting latency targets.
- Consider fake timers and frontend setup changes separately, with relevant
  React/FSD guidance and focused tests of the actual production debounce,
  cancellation and stale-response paths. Do not bypass them with test-only
  application branches. No frontend source is changed in P0.

The user also requires preserving both runner-minute headroom and the account's
0.5 GB Actions storage allowance. Implementation-plan section 11 separates
shared artifact/Packages storage from cache, records the limits of available
billing evidence, and sets joint forecast/reserve gates. No build-artifact
transfer is introduced to buy a minute saving at the expense of storage.
