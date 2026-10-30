# Published Base: owner-approved artifact cleanup — 2026-10-31

The owner requested removal of redundant code versions, migration backups and
rehearsal data, then explicitly answered **“Xoá cả dump production trước cutover”**.
Cleanup completed on the active branch `feat/flama-audio-edge-tts-20261027`.
Git history remains the record of code changes. No replacement data backup was
created. This closes artifact disposal batch B0, not the P6 runtime/schema contract.

## Removed

| Location | Result | Size evidence |
|---|---|---|
| Local MySQL | 27 inactive rehearsal/probe schemas dropped through MySQL | 22,327,574,528 bytes, estimated `DATA_LENGTH + INDEX_LENGTH` before deletion |
| Local project files | Two completed worktrees, their ignored dumps/caches and older migration backup artifacts | 4,196,093,978 regular-file bytes from the pre-deletion inventory; shared junction targets excluded |
| VPS backups | Eight completed migration backup directories, including both older SQL dumps and the final Published Base cutover dump | 2,222,497,025 regular-file bytes |
| VPS old releases | Five inactive release directories; current release retained | 173,679,001 regular-file bytes |

These are decimal bytes, not a claim that MySQL reclaimed exactly that physical
space. Local MySQL data-directory ACLs prevented direct allocation measurement.
The C: free-space observation increased from 19,278,028,800 to 36,772,491,264 bytes;
other processes can affect free-space deltas. No buffer-pool change, MySQL restart,
filesystem deletion of MySQL data, index change or production database DDL occurred.

Local disposable schemas removed:

```text
flama_browse_contract_10988_5f541d9f90f3
flama_browse_contract_70360_9d9ed8b55962
flama_note_base_fresh_20261029_fe2cefe0
flama_note_base_preexpand_20261030_cb058d06
flama_note_base_rehearsal_20261029_8c374786
flama_notetype_release_probe_14892_9f4ceb37cac2
flama_prod_rehearsal_20261021
flama_prod_rehearsal_20261022
flama_prod_rehearsal_20261025_idx
flama_prod_rehearsal_branch_20261021
flama_rehearsal_fresh_20261021
flama_rehearsal_fresh_branch_20261021
flama_rehearsal_fresh_pr239_20261022
flama_study_scaling_probe_21316_54dccc2c
nihongo_fresh_retirement_20261012
nihongo_fresh_retirement_20261012_live
nihongo_fresh_retirement_20261012_v2
nihongo_fresh_retirement_20261012_v3
nihongo_native_array_rehearsal_20261011
nihongo_retirement_archive_debug_20261012
nihongo_retirement_archive_debug_20261012_full
nihongo_retirement_archive_restore_20261012
nihongo_retirement_archive_restore_20261012_live
nihongo_retirement_archive_restore_20261012_v3
nihongo_retirement_rehearsal_20261012
nihongo_retirement_rehearsal_20261012_live
nihongo_retirement_rehearsal_20261012_v3
```

Configured application/system schemas, other applications and `nihongo_quota_dev`
were excluded. The local server UUID was checked against inventory, every target
was checked for active connections immediately before DROP, and cross-schema FK
references were checked. Main local `nihongo` retained 41,870 Notes; its existing
absence of `note_drafts` was unchanged. Cleanup did not upgrade that database.

The retired worktrees were `D:/Project/nihongo-note-base-20261029` and
`D:/Project/nihongo-note-ui-baseline-20261030`. Their three dependency junctions
were unlinked before `git worktree remove`; main `.venv` and
`frontend/node_modules` remain available. The original feature/docs branch trees
matched their squash merges. The temporary pre-merge backup ref was removed;
the ancestor commit remains in Git history.

The unique untracked `NOTE_PUBLISHED_BASE_REVIEW_2026-10-29.md` was moved to the
main checkout without changes and remains untracked. The Fulltext plan duplicate
matched the main copy's SHA-256. Existing Connect/audio edits retain SHA-256
`0d5f783337aa05030da0fab60e029dd356fe53153bce62ef4b50388e3d64d545`.
Other worktrees, stress-test work, user documents and active dependencies were
preserved.

Completed main-output directories removed: `native-array-rehearsal-20261021`,
`predeploy-pr239-20261022`, `native-array-cleanup`, `native-array-production` and
the temporary `branch-merge-20261031-8062c8f7`. Only the old SQL dumps were removed
from `index-audit-20261025`, `p9-restore` and `p10`; their other reports remain.

VPS directories removed under `/var/backups/flama/`: `array-20261011`,
`legacy-retirement-20261012-fb685882`, `native-array-20261011`,
`native-array-rehearsal-20261021`, `native-array-split-20261023`,
`note-published-base-20261030T125353Z-058c10`, `predeploy-pr239-20261022` and
`typing-back-audio-20261011`. Content-bearing manifests, raw reviews, old script
postimages and the cutover environment snapshot in these directories were also
discarded. These paths are no longer valid restore sources.

VPS cleanup acquired `/opt/flama/deploy.lock`, rechecked resolved paths and current
release, and found no process/file-descriptor or systemd/cron reference to its
targets. Five obsolete releases, including the old manual/Anki/media-origin
copies, were removed. `/opt/flama/current` remained on
`e824e8fa13ccf75da7b516d2dfeb1c331cca603e`; `/opt/flama/venv-3.12` and shared
`/var/lib/flama` storage were retained. Deployment activation in this branch now
uses `--keep 1` after successful health/readiness checks. This policy change has
not been pushed or deployed by this cleanup; the current VPS release was pruned
directly under the deployment lock.

## Verification and recovery disposition

Before/after read-only production checks matched exactly:

- Alembic `20261029_000076`, Published Base enabled.
- 41,874 Notes; six drafts / 23 Field deltas; 32 Base installs; four personal
  overrides; automatic publication disabled.
- Canonical Note content hash:
  `56dde35a193d2f1936fa5c4f947941f38019aae84252d7203558377c3a580ce2`.
- Draft content hash:
  `ac365414605103c9700076d1f65b216531a99794fa1a93dae329aab7826dd8e0`.
- Web, Connect, Study worker, Note retention and Study retention remained active.
  Public API health, session, Connect health and the SPA returned HTTP 200.

Checks completed at 2026-10-30 17:19 UTC (31 October in Asia/Tokyo).
The focused release-pruning suite ran through `scripts/run_tests.py`: three passed
and the symlink test skipped on Windows because the process lacks symlink
privileges. All four tests passed on VPS Linux using temporary directories,
including current-only retention and protection of linked shared assets.
The deployment workflow suite also passed (27 cases, one Windows/POSIX symlink
skip); `bash -n deploy/activate_release.sh`, Markdown links and `git diff --check`
passed. No frontend files or application behavior were changed by this cleanup.

Small inventory/deletion receipts and test results remain under ignored
`output/cleanup-note-base-20261031/`; they contain counts, hashes and paths rather
than Note payloads or credentials. No old SQL dump or content manifest was copied
into these receipts. The final local file-size sum was reconstructed from the
pre-deletion inventory after a PowerShell aggregation error; every reported
removed path was independently confirmed absent.

Pre-cutover database restore files and previous deployed release directories are
now unavailable. Git can rebuild code; it cannot recover discarded database rows.
The live six historical/rebase tables, active template versions/pins, personal
overlays, Study data and the rollout switch remain in place because their code
consumers still exist. Remove those consumers and storage together under the
[P6 checklist](NOTE_PUBLISHED_BASE_P6_CHECKLIST_2026-10-30.md); artifact deletion
does not establish soak acceptance or the remaining concurrency/UI qualification.
