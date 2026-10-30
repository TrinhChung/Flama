# P6 contract after the production soak

Owner: project owner for cutover/soak acceptance; implementation: Codex.
Schedule: the first separately reviewed implementation after the recorded soak
ends and its exit checks pass. There is no calendar date yet because production
cutover has not happened. Record the actual dates in the production receipt;
do not infer soak completion from elapsed local rehearsal time.

## Entry checks

- [ ] Owner reviewed the six manual Notes on the fresh production manifest;
  applied manifest/receipt and verified pre-cutover backup are retained privately.
- [ ] Production cutover and no-publish soak completed; owner accepted author,
  learner, Connect, render/media, progress and override smoke results.
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
