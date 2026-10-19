# Legacy retirement cutover, 2026-10-12

Code release: `fb685882099d20d90479d234402ae3b098076f89`.
GitHub: [PR #233](https://github.com/TrinhChung/Flama/pull/233),
branch `refactor/legacy-retirement-20261012`.

## Local result

Actual database `nihongo` migrated from `20261012_000057` to
`20261012_000062`. Full MySQL backup restored successfully into an isolated
schema; a separate seven-table archive also passed MySQL restore verification.

- All 20 protected table row counts and SHA-256 checksums remained identical.
- All 42,793 NOTE subjects retained their current state; the progress audit
  returned `DATA_READY` before and after migration.
- All 41,533 original Card identities have immutable presentation aliases.
- Physical `cards`, `card_progress`, and four retired auxiliary tables are
  absent. Template origin `note_type_id` is absent.
- Original working edits were preserved when integrating the release.
- The real local Flask entry point restarted; `/` and `/api/health` returned 200.

Private backup SHA-256:
`7973733515c5487fdbfbc9d01d41b56a25c3db319abc01f5eba09eef48caab31`.
Evidence is in ignored `output/legacy-retirement-20261012/local-cutover/`.
Backups and archives contain private application data and are not committed.

## VPS result

Actual database `flama` migrated from revision 57 to 62. Full backup restored
all 111 source tables into an isolated schema; all 20 protected checksums also
matched that restored copy. The seven-table external archive independently
passed MySQL restore verification before contraction.

- All 20 protected table counts and SHA-256 checksums remained identical.
- All 42,848 NOTE subjects retained their current state; both progress audits
  returned `DATA_READY`.
- All 111,743 original Card identities have immutable presentation aliases.
- All six retired physical tables and Template origin are absent.
- `/opt/flama/current` selects the exact code release above.
- Web, Connect and study worker are active, with zero restarts and no recent
  error-priority journal entries. The retention timer is active again.
- `/`, `/api/health`, and Connect `/healthz` returned 200.

Private backup SHA-256:
`d1d37c532c91fc42e13e4e7eae640cce7d6cb56c19c32638ccd0337da9080b9a`.
Private server evidence and backups:
`/var/backups/flama/legacy-retirement-20261012-fb685882/`.
Sanitized counts/checksums are recorded in
`docs/architecture/artifacts/legacy_progress_retirement_20261012/actual-cutover.json`.

The release archive SHA-256 was verified after transfer:
`835e924ae7ec8d8a9199febbc06edec3ccea049c6a3956d4870a2f75ea192b9c`.
The old release was replaced only after target-specific archive, audit,
migration, and protected-state verification passed. This deployment selected
the committed release directly; PR #233 remains open for integration into
`master`. Subsequent old releases must not be activated against schema 62.

## Qualification

Full backend: 2,320 tests passed, seven skipped. Focused frontend: 76 suites
passed; incoming guide/array fixtures: 15 tests passed. TypeScript and production
frontend build passed. MySQL migration, concurrency, Connect fence, retention,
NOTE analytics, due/count queries, and sibling scaling probes passed.
The preserved local template rebase edits passed their focused suite after merge.

## Remaining scope

R1–R4 implementation is complete. Field-name identity retirement (R5) has a
separate design in `docs/architecture/FIELD_VALUE_IDENTITY_DESIGN_2026-10-12.md`.
`FieldRenameJob` remains an active model until that storage migration is built;
removing it now would break the current rename flow.
