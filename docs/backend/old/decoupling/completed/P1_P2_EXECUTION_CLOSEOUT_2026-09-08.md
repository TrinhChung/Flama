# P1/P2 decoupling execution closeout — 2026-09-08

> Status: COMPLETE for P1-03, P1-04 and P2-02 through P2-07
>
> Baseline: branch `develop`, implementation worktree based on `da52960`
>
> Scope boundary: no model, migration, progress store, overlay model or UI redesign

## Outcomes

| Task | Outcome |
|---|---|
| P1-03 | Versioned, bounded ReviewEvent provenance for native REST/MCP/session writers and external Anki revlog facts; legacy rows remain classified, not invented. |
| P1-04 | Exact Algorithm lifecycle and retained-decoder matrix on Python/TypeScript, with purpose-aware resolution and audit introspection. |
| P2-02 | One owner-token mutation mutex across Study bootstrap, answer, undo, commit/retry, exit, reload and persisted content/template updates. |
| P2-03 | Strict v2/v3 restore plus additive bounded IndexedDB quarantine, stable reasons and explicit evidence-preserving recovery. |
| P2-04 | One semantic `ReviewAction` callback; raw rating conversion exists only at the named compatibility boundary. |
| P2-05 | Accepted no-bridge keyboard boundary; parent shortcuts remain trusted and iframe focus cannot request progress actions. |
| P2-06 | Accepted and implemented minimal exact-version built-in Trigger dispatcher; no arbitrary automation runtime. |
| P2-07 | Paired v2/v3 session/commit/batch decoders, pinned-session validation, capability negotiation and metadata-only rollout telemetry. |

## G0 containment and rollout state

- `STUDY_ASYNC_BATCH_ENABLED=false` by default. New clients use synchronous
  rollover; async routes reject new admission unless operators explicitly opt in.
- Existing queue/worker code remains fail-closed for wire and Algorithm identity,
  but re-enablement requires the separate schema, Redis locking, consumer and
  durable receipt prerequisites documented in the execution plan.
- `STUDY_WIRE_V3_ENABLED=false` by default. The client advertises v3/v2 and the
  server issues v3 only when the flag is enabled. Disabling issuance never removes
  the v3 reader required by live leases.
- `CardProgress` remains authoritative, `ReviewEvent` remains history, and shared
  decks remain overlay-only.

## Verification evidence

Commands executed from the repository root with the project virtualenv:

```text
.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --module study --frontend-only
.venv\Scripts\python.exe scripts/run_tests.py --module connect_mcp --backend-only
.venv\Scripts\python.exe scripts/run_tests.py --module decks,flashcards --backend-only
.venv\Scripts\python.exe -m unittest tests.test_owner_note_dirty_tracking_services
npm --prefix frontend run typecheck
npm --prefix frontend run lint
git diff --check
```

Recorded results:

- Study backend: 144 tests / 17 files passed.
- Study frontend: 167 tests / 22 files passed.
- Connect/MCP backend: 161 tests / 13 files passed.
- Decks/Flashcards backend: 361 tests / 31 files passed.
- Owner-note focused regression: 12 tests passed.
- TypeScript typecheck: passed.
- Frontend lint: zero errors; existing unrelated warnings remain.
- Diff check: passed (line-ending conversion notices only).

P2-05 browser verification used the isolated Playwright session `flama-p205`.
Parent focus received the shortcut, iframe focus retained it locally, and a
forged `host_command` caused no parent action. The accepted ADR contains the
exact observations and ignored local evidence paths.

## API and contract changes

- Session open accepts `accepted_session_schema_versions`; omission preserves v2.
- V3-capable issuance is guarded by `STUDY_WIRE_V3_ENABLED`.
- Async batch admission is guarded by `STUDY_ASYNC_BATCH_ENABLED`.
- New ReviewEvent payloads use `review-event-payload.v1` with trusted producer,
  runtime and session/import provenance.
- Unknown/mismatched wire, Trigger and Algorithm versions fail closed rather than
  falling forward.

## Rollback and known limits

Rollback should stop new v3 issuance and keep all readers/exact artifacts for
live leases. ReviewEvent readers must continue accepting legacy and v1 payloads;
quarantine evidence must not be copied back into the active store automatically.

This closeout does not certify real Redis/MySQL async operation. The async path
is deliberately disabled by default, and pre-existing accepted batches require
operational reconciliation before it may be enabled. It also does not complete
Phase 3 or INT-01.

## Next work

Proceed with P3-05 and P3-07 decisions, then P3-01 through P3-06 in dependency
order. Run INT-01 only after those tasks and the real overlay composition exit
gate are complete.
