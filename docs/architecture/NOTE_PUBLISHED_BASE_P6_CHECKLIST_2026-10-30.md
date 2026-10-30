# P6 contract after the production soak

Owner: project owner for cutover/soak acceptance; implementation: Codex.
Schedule: the first separately reviewed implementation after the recorded soak
ends and its exit checks pass. Production cutover completed and soak started at
2026-10-30 13:01:18 UTC; its end has not been accepted or scheduled. See the
[production result](NOTE_PUBLISHED_BASE_PRODUCTION_CUTOVER_2026-10-30.md).
Do not infer soak completion from elapsed local rehearsal time or initial smoke.

## Working branch and cleanup batches — 2026-10-31

The owner's active branch `feat/flama-audio-edge-tts-20261027` now includes
`origin/master` through `123195ec`: Published Base implementation (#265) and
the production/soak record (#268). Integration was a fast-forward from `0eaef70f`.
The existing Connect/audio working edit was preserved byte-for-byte. The older
untracked plan differed only in its pre-deployment status; its original was
retained under the ignored `output/branch-merge-20261031-*` integration backup.
The route/retention integration smoke passed all six targeted tests; both
repository skill mirrors match. The local receipt and initial caller inventory
are recorded under `output/note-base-branch-integration-20261031.json` and that
integration backup directory.

Use this table as the cleanup queue. Each completed batch needs its commit and
validation evidence recorded here and its corresponding checkboxes updated below.
The paths identify candidates for inspection; their presence does not establish
that every function in a file is obsolete.

| Batch | State | Scope and acceptance evidence |
|---|---|---|
| I0 | Done: `123195ec` | Bring the deployed implementation and reports into the active branch; preserve local work and retain an integration backup. |
| C0 | Initial inventory captured; caller audit pending | Capture flag/history/rebase callers before each removal. Trace runtime, CLI, tests, dynamic imports and retained template consumers. |
| C1 | Pending entry checks | Remove obsolete Note reconstruction, atoms/checkpoints, dirty journals, automatic publication and subscriber fanout in `deck_release_service.py`, `deck_release_repository.py`, `deck_working_tree_service.py` and `deck_auto_publish_service.py`. Preserve active Base publication and template pins. |
| C2 | Pending entry checks | Retire install rebase/conflict paths in `deck_install_rebase_service.py`, marketplace installation routes and `frontend/src/features/deck-collaboration/` / `frontend/src/pages/installed-deck-update/`. Preserve personal overrides, local additions, comparison and authenticated compatibility responses. |
| C3 | After C1/C2 | Remove `NOTE_PUBLISHED_BASE_ENABLED` and its flag-off branches together across readers, codecs, settings, managed environment and deployment configuration. Verify every remaining runtime caller against the Base contract. |
| C4 | After runtime consumers and rollback disposition | Contract the six tables listed below, their ORM relationships/exports and dependent consumers. Verify fresh upgrade and production-copy migration on local MySQL, with retained backup and parity evidence. |
| C5 | With C4 | Update the code rollback capability guard and the cutover/rollback operator tools for the final schema. Keep historical migration chains executable and preserve their required historical definitions. |
| C6 | Final qualification | Run focused domain/MySQL checks, Study commit/process-concurrency qualification, desktop/mobile checks and before/after workload measurements; deploy and record the final result. |

Current scope evidence: Base guards remain in `deck_release_service.py`,
`deck_working_tree_service.py`, `deck_auto_publish_service.py`,
`deck_install_rebase_service.py` and `deck_release_repository.py`. The six legacy
models are still exported by `models/flashcard.py` and referenced by relationships
in `deck_release.py`, `deck_marketplace_item.py` and `deck_install.py`.
These references require coordinated removal rather than deleting the model files
alone. `deck_release_template_pin.py` belongs to the retained template contract.

The local uncommitted concurrency report is dated 2026-10-28, before the Base
cutover. It is useful prior-work evidence; it does not qualify the merged Base
runtime or close the entry checks below. Keep that stress work and the pending
Connect/audio change in their own commits. No runtime/schema removal was performed
by this branch-integration step.

## Entry checks

- [x] Owner approved six Notes / 23 manual Fields and eight receipt-backed script
  Fields retained in Base. Fresh production content/classification matched;
  applied manifest/receipt and verified pre-cutover backup are retained privately.
- [ ] Production cutover and no-publish soak completed; owner accepted author,
  learner, Connect, render/media, progress and override smoke results.
  Cutover and initial smoke passed; operational soak/owner acceptance remain open.
- [ ] Rollback disposition is explicit before removing historical storage.
- [ ] End-to-end study/review commits and a process-isolated concurrency matrix
  are qualified. Read-only page benchmarks do not satisfy this check.
- [ ] Runtime buffer pool/configured target and any approved measurement scope
  are recorded. Do not resize MySQL or introduce indexes for this checklist.

## Runtime removal

- [ ] Capture the current `published_base_enabled()`/flag inventory with `rg`
  immediately before editing. Inspect each caller; a text count is not proof
  that a path is unused. The pre-cutover inventory spans readers, Browse,
  author codecs, change requests, sharing, imports, media and MCP.
- [ ] Remove old Note content reconstruction/pinning, atom/checkpoint reads,
  working-tree dirty journals, automatic deck publication and subscriber fanout.
- [ ] Remove install rebase/conflict services, repository adapters and obsolete
  frontend update/conflict settings; preserve authorized local additions and
  sparse personal overrides. Keep intentional authenticated `410` responses
  for retired public APIs until their compatibility policy is reviewed.
- [ ] Remove the rollout switch and the flag-off backend branches together.
  Preserve template publication/version/pin storage: it remains active.
- [ ] Review legacy install/listing metadata column readers and writers before
  proposing their contraction. The approved expansion is not permission to
  add or change indexes.

## Historical storage contraction

Create and verify the separately reviewed Alembic contraction on local MySQL.
Check every FK, retention reference, CLI/report consumer and rollback guard:

- [ ] `deck_release_changes` (including the old template atoms).
- [ ] `deck_release_note_checkpoints`.
- [ ] `deck_release_entity_memberships`.
- [ ] `deck_working_dirty_entities`.
- [ ] `deck_install_rebases`.
- [ ] `deck_install_rebase_conflicts`.

## Exit evidence

- [ ] Narrow domain tests and MySQL migration/entry-point checks pass.
- [ ] All first-level SPA routes and affected author/installed flows are verified
  on desktop and mobile with before/after artifacts.
- [ ] Before/after latency, SQL counts, logical/disk page reads, write costs and
  lock behavior are published with the real measurement limits.
- [ ] Update the runbook, ADR, architecture portal and rollback guard for the
  final storage/runtime contract. Close this checklist only after deployment
  evidence exists; no historical tables are dropped by the current timer.
