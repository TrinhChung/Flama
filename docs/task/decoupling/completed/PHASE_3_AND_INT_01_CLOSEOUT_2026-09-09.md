# Phase 3 and INT-01 closeout — 2026-09-09

> Status: COMPLETED
>
> Scope: P3-01 through P3-07 and INT-01
>
> Baseline: `develop` at `bf3942a`
>
> Storage boundary: no model, migration, DDL, progress store, or physical clone behavior was added

## Outcome

Phase 3 now makes the selected compatibility composition an explicit server-authorized session input. The client discovers eligible options before opening a new session, auto-resolves only a single unambiguous option, waits for learner selection when multiple options exist, and does not create a fake empty session when none exist.

The backend derives discovery and session membership from the same effective card query. Owned cards, installed source-overlay cards, and installed local-added cards receive deterministic context-qualified identities. Selection filtering happens before the session limit, preserving the existing study query's scheduling, due-order, timezone, suspension, and burial behavior.

The selected composition and its effective compatibility binding are frozen in the existing session JSON. Restore uses that frozen material without rediscovery, while commit and batch admission reject contradictory selection data. Supported legacy flat session policies remain readable.

## Accepted decisions

- [Mixed-NoteType study-scope policy](../../../architecture/mixed-notetype-study-scope-policy-2026-09-09.md): group eligible choices by NoteType on one pre-session screen and authorize exactly one composition.
- [Applied composition and binding contract](../../../architecture/applied-composition-binding-contract-2026-09-09.md): keep current Template/Card identities as the Phase 3 compatibility projection, bind concrete fields by stable `FieldDef.id`, and defer physical definition/application/version storage.
- Compatibility owned ID: `comp:notetype:{note_type_id}:template:{template_id}`.
- Installed IDs: `comp:install:{install_id}:{source|local}:notetype:{note_type_id}:template:{template_id}`.
- Ambiguous omission fails with `COMPOSITION_SELECTION_REQUIRED`; malformed, stale, and out-of-scope cases use bounded typed errors.

## Exit-gate checklist

| Gate | Result | Evidence |
|---|---|---|
| P3-01 exactly-one authorization | PASS | canonical validator, typed resolved selection, route/service tests |
| P3-02 query-first effective scope | PASS | shared effective-card query, limit-fairness and mixed-scope tests |
| P3-03 pre-session selection | PASS | zero/one/many hook tests, no-premature-POST and retry deduplication |
| P3-04 frozen restore | PASS | versioned config wrapper, dual reader, restore quarantine, commit/batch mismatch tests |
| P3-05 mixed-NoteType decision | PASS | accepted ADR and deterministic group/order/cardinality contract |
| P3-06 real logical overlay | PASS | production publish/install service path with source and local-added Cards; zero ordinary source Card copies |
| P3-07 binding contract | PASS | accepted logical contract and explicit Phase 4+ deferrals |
| P2 security containment retained | PASS | full backend/frontend regression suite; no renderer command-boundary change |
| Progress authority unchanged | PASS | no `models/` or `migrations/` diff; `CardProgress` remains sole operational authority |

## Verification evidence

| Command/check | Result |
|---|---|
| `.venv\Scripts\python.exe -m unittest tests.test_study_composition_service tests.test_study_session_api tests.test_study_composition_exit_gate` | PASS — 46 tests |
| real `DeckInstall` overlay acceptance test | PASS |
| `.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only` | PASS — 151 tests |
| `.venv\Scripts\python.exe scripts/run_tests.py --module decks,flashcards --backend-only` | PASS — 361 tests |
| focused Study hook + restore frontend tests | PASS — 44 tests |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run lint` | PASS — no errors; 23 pre-existing unrelated warnings |
| `.venv\Scripts\python.exe scripts/run_tests.py --all` | PASS — 1,094 backend tests (2 skipped) and 384 frontend tests |
| `git diff --check` | PASS — line-ending notices only |

The full suite intentionally emits warnings/errors from negative-path tests such as disk-full, Redis-unavailable, SSRF, malformed media, and deprecated SQLAlchemy/Python APIs. They did not fail the suite.

## Integration search and boundary review

- No frontend `compositionFilter` remains as a session-authority mechanism.
- Legacy `composition_ids` remains only as a fail-closed request compatibility surface and test case.
- No “all compositions” choice remains in the pre-session selector.
- The overlay proof uses a real `DeckInstall`; the former physical-copy test is retained only as an owned legacy-projection scenario and is no longer described as clone proof.
- No source Note/Card mutation or copied source Card fallback was introduced.
- No secondary progress authority, model, or migration was introduced.
- REST, MCP, direct review, batch replay, Trigger/Interaction, and Algorithm compatibility boundaries from Phase 1/2 remain unchanged.

## MySQL evidence and confidence

INT-01 reuses the approved signed P0-03 SELECT-only evidence bundle dated 2026-08-29. No fresh production credential, startup path, DDL, DML, or write was used. The historical 2026-08-24 observation of a recursive scope containing two NoteTypes justifies the mixed-scope policy, but it is not presented as a fresh signed production distribution count.

## Rollback

If Phase 3 admission must be rolled back, stop opening new sessions through the new launch flow while retaining:

- additive request and session-config readers for already-issued leases;
- exact frozen-selection validation for those leases;
- logical-overlay invariants and the real-install regression test;
- historical compatibility composition IDs.

Any regression in the exit matrix requires the canonical tracker to return Phase 3 to `Partial`; tests or documentation must not be weakened to legitimize physical clone behavior.

## Remaining work and recommendation

Phase 4 may enter a separate architecture/planning review, but this closeout does **not** authorize SQL, Alembic, backfill, a new progress authority, physical reusable Template/application tables, or Algorithm State cutover. The deferred items are:

- physical reusable definition/version/application/binding storage;
- repeated application occurrence persistence;
- learner/Note progress envelope and availability projection;
- versioned Algorithm State, reconciliation, retention, and cutover;
- production rollout decisions for currently flag-off async admission and wire-v3 issuance.

