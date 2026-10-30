# Published Base production preflight — 2026-10-30

Status: no production schema, content or flag change has been made. PR #265
remains gated by CI. Production is running `cab65807` at Alembic
`20261025_000075`; the Base flag is unset and resolves to false.

## Backup and current-data rehearsal

A fresh single-transaction production backup was downloaded and checked for
complete gzip CRC, dump footer and SHA-256. It contains 1,467,124,716 SQL bytes;
SQL SHA-256 is `d731beb91610df7e84924b9aef0041f487649abca95d91b92c66a6a4a8f5dd4a`.
Restoring it into a new isolated local MySQL schema succeeded in 158.960 seconds.
Production was read only during backup; the local buffer pool was not changed.

The copy contains 41,874 Notes, 32 installs and four personal overrides. Alembic
76 and a cutover using the current classification succeeded. Apply took 4.644
seconds; all 41,874 author Note images matched their pre-cutover content after
merging Base and drafts. All four override postimages matched their intended hash
backfills. Study progress, review events, local additions and clone deck-map
checksums stayed equal. These are local rehearsal results, not production cutover.

Thirty-five authenticated in-process HTTP GETs passed on the restored copy:
author Browse/detail/search and installed Browse/comparison across 16 learner
accounts. A SQL listener rejected DML/DDL. The requests use normal transactions
because existing Study read fencing takes `FOR UPDATE` locks; they were not
MySQL `READ ONLY` transactions. Flask test-client sessions supplied authentication;
the routes and payloads were real. Public login and reverse-proxy verification
remain rollout checks. Separate browser/render evidence remains in the
[review response](NOTE_PUBLISHED_BASE_REVIEW_RESPONSE_2026-10-30.md).

## Classification changed with exact script evidence

The owner approved six Notes / 31 draft Fields from the earlier time-window
classification. Production still retains both native-array split plans and apply
receipts from 23 October. Their checksums and identities match. The operator
validated the plans and compared each proposed script Field's current typed JSON
value with the plan's exact applied value; mismatching values were not admitted
to the exact-script pair list.

Eight previously classified manual Fields match those exact script results.
Following the evidence priority in plan §7.1 changes the proposed draft set to
**six Notes / 23 Fields**. The retained 23 Fields have exactly the same Base and
author values as the approved list; there are no added manual Fields. All six
Notes still have drafts. The eight script Fields stay in Base with their current
values, so the author's combined content remains unchanged.

An updated private review lists all eight reclassifications and all 23 remaining
draft Fields. Renewed owner review of this changed classification is pending.
The old 31-Field approval is retained as evidence and is not treated as approval
of the updated classification. Earlier rehearsal reports describe their original
manifests and are not the fresh production apply artifact.

The final production plan must be regenerated while writers are stopped, compared
to the approved content/classification and applied with that exact target SHA.
See the [cutover runbook](../runbooks/NOTE_PUBLISHED_BASE_CUTOVER_20261029.md).

## Operational inventory and CI corrections

VPS inventory found the existing `flama-study-retention.timer` in addition to web,
Connect, Study consumer, analytics and the new Note retention job. Deployment now
stops its timer and oneshot before migration, refuses rollback if it cannot stop,
and resumes it only if it was previously enabled. The focused deployment suite
passed 27 tests with one pre-existing POSIX symlink skip on Windows.

No matching Flama cron entry or MySQL scheduled event was found. There were no
unfinished accepted Study batches at inspection. The operator must recheck both
at actual quiescence; the inspection is not a future-state guarantee.

Hosted CI run 41051500589 passed frontend and MySQL contracts. Its 2,617-case
backend selection found two NoteType purge errors and two static tooling failures.
The correction skips canonical payload validation for physically deleted Notes
while keeping Published Note deletion redirection, points the preview check at
the extracted hook/view, and maps the original benchmark script to its domain.
The three focused correction suites passed all 29 cases; the MySQL draft and
publication suites passed all 48 cases after the hook correction. A fresh hosted run must
pass before merge; this report does not convert the failed run into a pass.

P4 activation, no-publish soak and the
[P6 exit checks](NOTE_PUBLISHED_BASE_P6_CHECKLIST_2026-10-30.md) remain outstanding.
Historical tables and rollback code are retained.
