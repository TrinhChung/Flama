# Deck, Note Type and Template stability

Date: 2026-10-21. Mode: DESIGN. Engine: MySQL 8.0.

This implements the authorized fixes from [the investigation](deck-notetype-template-review-2026-10-20.md). The investigation remains a record of the previous behavior.

## Invariants and ownership

- Installing another deck must not advance an existing deck's template pin. Explicit personal edits to the canonical received template apply across that user's decks; clean upstream changes use each deck's own pin.
- A published Note Type release includes metadata, stable field IDs/types/roles, all active application occurrences, their mappings/order/defaults, and exact TemplateRelease IDs. Subsequent draft edits cannot change that release.
- Free and paid receipts use the same service. Checkout records the purchased release ID, so fulfillment does not substitute a newer release published during payment.
- A deleted local Note Type can be restored using its installation provenance without counting a second purchase/install. Existing local content is not overwritten on repeated receipt.
- Author publication stages one durable dispatcher in its transaction. Subscriber delivery runs in separate bounded transactions; one subscriber's lock or failure cannot roll back the author's publication.
- Source notes, overlays, learning progress and native array values keep their existing ownership and representation. Marketplace republishing restrictions remain enforced.

## Systems of record

| Store | Role | Writers and readers |
|---|---|---|
| `note_types`, `field_defs`, `study_applications` | Mutable author/local working copy | Existing content and mapping services |
| `note_type_releases` | Immutable complete published manifest and digest | Explicit author publish; marketplace detail and receipt |
| `note_types.current_release_id` | Author's current publication | Publish service |
| `note_type_installs.applied_release_id` | Received release provenance | Canonical free/paid receipt |
| `template_releases`, `template_versions` | Exact published template content | Existing release service; manifests and render resolver |
| `deck_release_template_pins` | Per-deck immutable presentation and occurrences | Deck publish; installed source-card resolver |
| `template_subscriptions` | One editable received definition per user/source | Template editor and opt-in subscriber sync |
| `template_sync_jobs` | Dispatcher cursor and independent recipient delivery/retry state | Publish outbox; study consumer or explicit drain CLI |

Release manifests reference exact template releases in JSON. The service validates source identity and availability when reading them. Mutable source and installation pointers have relational foreign keys; the manifest is a complete read snapshot, not a collection of mutable ORM relationships.

Standalone Note Type receipts use frozen received template definitions for their applications. A later deck receipt reuses its NoteTypeInstall without appending duplicate applications or rewriting the frozen schema. Source cards of that deck continue to use their own deck release pins. Local notes use the local Note Type's applications.

## Modeling alternatives

For Note Type releases, normalized snapshot tables for fields, applications and bindings were compared with one immutable JSON manifest. The manifest keeps a complete schema read atomic and avoids several snapshot joins and migrations for future schema attributes. The trade-off is validating embedded template references in the service rather than with one FK per JSON entry. Unique source/version-label and source/sequence constraints protect publication identity. The same label is accepted only when its complete digest matches; changing published metadata also requires a new version label.

For subscriber delivery, one JSON cursor plus all recipients on a shared row was compared with normalized dispatcher/delivery rows. Separate recipient rows permit `SKIP LOCKED`, independent retries and short transactions. This adds one row per eligible recipient/release and requires queue-history retention planning. It avoids serializing every subscriber's delivery state on the author's publication row.

## Query and transaction behavior

- `GET /api/note-types?summary=1` selects scalar manager metadata with indexed count subqueries in one SQL statement. It does not load fields or template HTML. Existing full-detail callers retain their response. The manager uses a distinct query key to avoid poisoning detail caches.
- The deck resolver batches subscriptions and release/version rows. Local content is compared with its applied upstream release; only changed properties are projected onto the deck pin.
- Applications retain `occurrence_key` and `source_ord`. Removing one occurrence retires that occurrence while preserving the remaining application identity.
- Queue dispatch pages through `(source_template_id, auto_update_enabled, id)`. Delivery locks its local template and subscription with `NOWAIT`, checks opt-out and release order again, and preserves manual/conflicting preparations.
- Each worker connection uses READ COMMITTED for queue processing, avoiding REPEATABLE READ next-key locks that could delay author outbox inserts. This does not change the application's global isolation level.
- Claim, apply and completion share one transaction. A crash rolls them back together. Failures retry with bounded backoff, then retain a safe error code after six attempts. No HTML, learner payload or SQL parameters are stored in diagnostics.

## Expand, cutover and rollback

1. Expand with migration `20261020_000070` (Note Type releases and nullable pointers), followed by `20261020_000071` (queue and subscriber cursor index). The previous head is `20261019_000069`.
2. There is deliberately no historical snapshot backfill. A published legacy Note Type without a complete manifest returns `requires_author_republish`; a new receipt/purchase returns `NOTE_TYPE_RELEASE_NOT_READY` until the author explicitly republishes. Existing installed content continues working. Audit outstanding pre-cutover Note Type payment orders: orders without a purchased release ID require operator recovery and return `PURCHASED_NOTE_TYPE_RELEASE_UNAVAILABLE` rather than silently granting a different release. Existing paid records are retained.
3. Deploy the release reader/writer and queue consumer together. Verify the continuous study consumer is running even when study async ingress is disabled, or operate the explicit bounded drain. Publication commits before subscriber delivery completes.
4. Keep legacy deck fallback for historical installs with uninitialized manifests or missing releases. The investigation found real local installs using it. Do not invent old deck presentation from today's draft or remove the fallback in this change.
5. For rollback, revert the application while retaining additive tables and columns. Downgrades refuse to drop nonempty release/queue history. There is no destructive contract phase in this change.

Run from the checkout root using the configured local MySQL environment:

```powershell
.\.venv\Scripts\python.exe -m flask --app wsgi.py db current
.\.venv\Scripts\python.exe -m flask --app wsgi.py db upgrade
.\.venv\Scripts\python.exe -m flask --app wsgi.py template-sync-status
.\.venv\Scripts\python.exe -m flask --app wsgi.py template-sync-drain --max-jobs 100 --batch-size 100
```

Inspect `failed_count`, queue age and safe error-code aggregates. A bounded drain is one pass, not a continuously running service. Use the existing study consumer for continuous processing. Exhausted deliveries remain inspectable; there is no automatic destructive purge or administrative retry reset in this change.

## UI and scoped legacy cleanup

The installed-template route now renders loading/error/retry/empty/legacy states, the deck's pinned release, and the editable personal copy. The dashboard's own-deck edit action opens application mapping. Manager and installed-template composition live in `pages/`; feature public APIs replace the touched facade/deep imports. Removed blank/duplicate page shims have their route, lazy import, re-export, alias and test callers checked.

The old synchronous publish fan-out function is removed. Broad share compatibility facades and historical clone readers remain because current installations still depend on them. This is scoped cleanup, not a claim that all repository legacy code has been eliminated.

## Verification

The tracked scripts below create unique generated schemas on loopback MySQL, reject the configured application database and existing schema names, inspect only its default collation, and clean up the generated schemas:

```powershell
.\.venv\Scripts\python.exe scripts/probe_note_type_releases_mysql.py
.\.venv\Scripts\python.exe scripts/probe_template_sync_mysql.py
.\.venv\Scripts\python.exe scripts/probe_template_pin_isolation_mysql.py
```

They cover release/receipt parity, checkout timing, actual SET NULL reinstall behavior, immutable mappings/occurrences, cross-deck pins, user scoping, compact manager query count, lock contention, retries, concurrent workers and additive migration repeatability. Frontend focused suites and isolated-browser checks cover routes and visible behavior. These checks do not establish production load capacity or replace production rollout monitoring.

## Verified local state (2026-10-21)

- Note Type release MySQL probe: PASS, including stale REPEATABLE READ receipt, REST preview/detail, exact paid release and parent-table collation.
- Template queue MySQL probe: 14/14 passed; publish completed in 0.047 seconds while a recipient row was locked. This is a local regression measurement, not a production latency guarantee.
- Template pin MySQL probe: 10/10 passed. Ten Note Type manager rows used one SQL statement and a 2,849-byte JSON payload.
- Frontend: 113 focused tests passed, TypeScript passed, touched-file Oxlint passed. Desktop and mobile browser checks used the real disposable MySQL backend; edit navigation and auto-update toggle worked, with no horizontal overflow. The existing editor preview emits its pre-existing CSP warnings; the manager emitted no console errors or warnings.
- Three pure pin-resolution unit tests passed. The complete backend suite was not rerun; its existing integration-style SQLite fixtures are not MySQL qualification.
- The main checkout's actual `wsgi.py` Alembic path upgraded local MySQL from `20261019_000069` to `20261020_000071`. Model-column smoke checks and session/unauthenticated-summary HTTP checks passed. Notes remained 41,534; there were zero outstanding legacy Note Type payment orders locally. Production order counts remain unverified.
- Disposable probe/browser schemas and owned dev servers were cleaned up. No production deployment or commit was performed.

## Remaining boundary

The new queue isolates TemplateRelease subscriber updates. Deck auto-publish still calls `deck_install_rebase_service.process_subscriber_auto_updates()` synchronously in `deck_auto_publish_service.py`. Its overlay rebase transaction requires a separate queue design; this change does not establish that deck auto-publish is isolated from every subscriber lock. Legacy reader removal and historical payment-order recovery also remain explicit operational work.
