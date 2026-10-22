# Legacy marketplace template provenance cutover

Date: 2026-10-21; completion verified 2026-10-22 (Asia/Tokyo). Mode: IMPLEMENTED / LOCAL APPLIED. Engine: local MySQL 8.0.

## Evidence and scope

The completed [marketplace completeness review](marketplace-bundle-completeness-review-2026-10-21.md), finding 5, identified 21 old `NoteTypeInstall` rows with `applied_release_id=NULL`. Twenty local Note Types survive. Each has one template created in the same second as both the installed Note Type and receipt; each source currently has one active template. Those copied templates incorrectly retain `origin=authored`, without a source pointer. Four copies match a surviving original immutable content version, but this does not establish the actual release received at the earlier installation time. Other copies contain personal edits.

The private plan is `output/marketplace-legacy-provenance-plan-20261021.json`. It selects 20 templates, zero unresolved mappings. The missing local installation is not recreated. Its checksum is `d9f26471463380fba42e183ee451eafbf064ecdc417b5b092c58bac06385d90b`. The implementation worker only read the configured database. The lead subsequently reviewed the mappings, ran dry-run, applied and verified all 20 on local `nihongo` under the owner's instruction.

Receipts: `output/marketplace-legacy-provenance-dry-run-20261021.json`, `output/marketplace-legacy-provenance-applied-20261021.json`. A repeated apply saved as `output/marketplace-legacy-provenance-repeat-20261022.json` verified all 20 with zero changes and `already_applied=true`. Both historical release pins and protected content/mappings/notes/progress remained unchanged. No production database has been modified.

## Systems of record and invariants

| State | Authoritative evidence | Cutover behavior |
|---|---|---|
| Receipt and local ownership | `note_type_installs`, copied Note Type and template creation times | Preserve IDs, user ownership and timestamps |
| Original authorship | Unique source application and canonical source `Template.owner_user_id` | Store canonical `source_template_id`; expose original author separately |
| Local HTML, CSS and input schema | Existing local `Template` and `TemplateVersion` rows | Preserve byte-for-byte; no replacement or content snapshot appended |
| Application mapping and card identity | Existing `StudyApplication` IDs and bindings | Preserve all rows and mappings |
| Notes, field identities, reviews and scheduler state | Existing note/field/review/progress rows | Never write; checksum selected local state before and after |
| Historical release received | Unknown for legacy receipts | Keep Note Type `applied_release_id=NULL` and template `source_version_id=NULL` |
| A new current receipt | A new canonical `TemplateSubscription` explicitly requested now | Separate current copy; never relink or overwrite the old local application |

The local template remains editable by its recipient. Local ownership is not original authorship and never permits resale of received code. A local copy must remain blocked before tagging, after tagging, after personal edits, and after rollback.

## Alternatives considered

1. **Assign today's release to every old receipt.** This fits the existing non-null subscription pin, but invents history, changes the three-way merge base and can overwrite personal edits. Rejected.
2. **Introduce a dedicated legacy provenance table and nullable subscription mode.** This could record complex or detached receipt lineages durably, but requires schema expansion, new constraints and broader changes to update algorithms. Retained as a future option for populations with insufficient existing evidence.
3. **Provenance-only tags plus explicit unpinned runtime handling.** Selected for the verified local population. Set only `Template.origin=market_copy`, `source_template_id=<verified original>`, `source_version_id=NULL`; retain existing modification timestamps. Existing schema and indexes suffice, with no DDL, history mutation or subscription fabrication.

Ambiguous mappings are classified as received for publication safety, remain unresolved in the plan and receive no guessed source ID or license. Runtime evidence uses creation times, never `updated_at`, so later personal edits do not erase lineage. A genuinely authored template attached later to an installed Note Type remains authored and duplicable.

## Runtime boundaries

`legacy_received_condition()` provides a correlated SQL exclusion for standalone catalog counts and lists. `is_received_template(session, row_or_id)` protects standalone/manual/automatic publication and duplication. `legacy_reference()` resolves only uniquely supported source identity; explicit reviewed pointers survive later source mapping changes.

`legacy_license_source_ids()` preserves rights acquired through those receipts even if the original is now paid. The central license resolver subtracts explicit revoked, expired or not-yet-effective rights. Its `current_read=True` path locks the buyer first and performs current reads, avoiding stale `REPEATABLE READ` license decisions.

The template distribution read returns `legacy_unpinned=true`, no applied release, disabled automatic updates and a separate indication that a new canonical receipt can be requested. Prepare/apply/reset/update-settings return `TEMPLATE_LEGACY_RELEASE_UNKNOWN`; they cannot invent a merge base. Ordinary personal editing and rendering continue to use the existing local content and applications.

`source_access()` no longer treats a visible free Note Type or any generic Note Type installation as a license to every currently attached template. The retained deck fallback requires the canonical template's author to match the original deck author, and does not override explicit negative template rights. Adding a foreign paid template to a draft after an old deck release therefore does not license it to existing deck learners.

## Operator workflow and rollback

Use `scripts/migrations/marketplace_legacy_provenance.py` with the repository virtual environment. Every invocation requires `--expect-database`; the tool accepts loopback MySQL only and binds a plan to the exact database name and server UUID. Plan/receipt files are created exclusively, never overwritten.

1. `plan --plan <new-private-plan.json> --expect-database nihongo` reads candidates, records full row preimages and checksum digests, and rolls back its read transaction.
2. Review each original/local/receipt mapping, unresolved entries, source ownership and unchanged historical-null pins.
3. `apply --plan <reviewed-plan.json> --receipt <new-dry-run.json> --expect-database nihongo --dry-run` rehearses mutations and verification, then rolls back.
4. After reviewing the concrete plan and dry-run result within the authorized database scope, run `apply` with a new receipt path and without `--dry-run`.
5. `verify --plan <reviewed-plan.json> --expect-database nihongo` checks the expected postimages and protected local content. Reapplying the same plan is a no-op. Regenerating a plan after tagging also yields no tag changes.
6. `rollback --plan <reviewed-plan.json> --receipt <new-rollback.json> --expect-database nihongo` restores the three provenance fields from reviewed preimages, only while the postimages still match. Audit records remain. Runtime evidence continues to block resale after rollback.

Apply and rollback lock affected buyers in sorted order before Note Types, templates, receipts and applications. They compare current locked preimages, retain template timestamps explicitly, perform one transaction, and verify protected state before commit. Changed HTML, fields, mappings, progress, ownership, subscriptions or source structure cause a safe refusal; a stale plan must be regenerated and reviewed. No code path writes notes, applications, fields, progress, releases or subscriptions.

## Verification and limits

Six pure tests cover unique versus ambiguous evidence, original author identity, pointer stability, the low-level publication guard and provenance-only postimages. The disposable MySQL probe `scripts/probe_legacy_template_provenance_mysql.py` rehearses publication and duplication guards before/after cutover, exact rollback, idempotence, dry-run rollback, stale-plan refusal, continued personal editing, a separate new canonical receipt, and legitimate versus foreign/revoked deck access.

All probe writes use a generated `flama_legacy_provenance_probe_*` schema, dropped in `finally`. The configured database supplies collation metadata only. No live payment provider is used.

Production needs its own inventory and reviewed plan. Templates detached before any surviving receipt/application evidence, ambiguous multi-template histories and deleted legacy installations cannot be reconstructed automatically. These remain explicitly unknown; matching current HTML alone is not proof of a historical release.
