# Flama Backend Technical Debt Catalog

> 2026-10-19 follow-up: use the [cleanup priorities and investigation plan](../LEGACY_CLEANUP_PLAN_2026-10-19.md)
> for the current scope. Retired shadow writer/backfill flags are removed there;
> the mapper/codec still support live NOTE authority. Historical model audits
> predate the Card, progress and Field ID contractions and are not a deletion list.

- **Domain**: Flask Modular Monolith & Persistence Layer
- **Last Audited**: 2026-10-19
- **Status**: Active Technical Debt Registry (Significant Remediation Completed)
- **Master Audit Report**: [Comprehensive Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md)
- **Companion service review**: [Edge TTS reliability review — 2026-10-27](EDGE_TTS_RELIABILITY_REVIEW_2026-10-27.md), including WebSocket fault injection, live probes and prioritized improvements.

---

## 1. Executive Summary

The Flama backend exhibits high technical sophistication (derived virtual `Card` view ADR P11, decoupled `StudyProgressSubject` ADR P10, and logical overlay clone architecture). In October 2026, a major technical debt remediation initiative addressed the primary monoliths, transaction boundary leaks, and routing anomalies. For cross-domain technical debt analysis and discrepancies catalog, see the master [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md).

---

## 2. Monolith 1: `app/services/flashcards_share_service.py` (Facade Transformation)

- **File Path**: `app/services/flashcards_share_service.py`
- **File Size**: **26 LOC** (previously **3,685 LOC / 147 KB**, ~99% code elimination)
- **Status**: **Phase 1 Completed** (Zero divergence, 113/113 sharing tests passing)

### Architectural Transformation
1. **De-duplication via Facade**:
   `app/services/flashcards_share_service.py` has been converted into a lightweight re-export facade on top of modular `app/services/share/` (`install.py`, `publish.py`, `overlay.py`, `cutover.py`, `helpers.py`, `constants.py`, `note_types.py`).
2. **Double-Fix Burden Eliminated**:
   All core business logic now lives exclusively in `app/services/share/`. Optimizations (such as `DeckPublishBatchContext`) and fixes only need to be written once.
3. **Backward Compatibility Preserved**:
   All existing callers continue to resolve their imports without breaking changes while new code imports directly from `app/services/share/`.

---

## 3. Monolith 2: `app/routes/vocabulary.py` (Pruned to 117 LOC)

- **File Path**: `app/routes/vocabulary.py`
- **File Size**: **117 LOC** (pruned from **718 LOC**)
- **Status**: **Phase 1 & 2 Completed**

### Architectural Remediation
1. **Dead Stubs Consolidated**:
   All 17 dead `410 Gone` stubs (`create_level`, `create_topic`, `create_lesson`, etc.) were consolidated into a single unified `legacy_structure_removed` catch-all handler.
2. **Duplicate Routes Pruned**:
   Duplicate `/vocabulary/api/browse/...` endpoints were retired in favor of canonical `/api/browse/...` (`app/api/v1/learning/browse.py`).
3. **Legacy HTML Forms Retired**:
   HTML form postbacks (`/decks/<id>/delete`, `/decks/<id>/reset`) using flash messages were removed; clients use canonical JSON REST endpoints in `app/api/v1/decks/`.
4. **Current Responsibility**:
   Module now exclusively retains legacy browse deck-tree and deck-settings wrappers.

---

## 4. Transaction Boundary Leaks (`db.session.commit()` in Routes) - RESOLVED

- **Architectural Policy**: HTTP route handlers must never control transaction boundaries. Services are the sole owners of transactions.
- **Status**: **Completed** (Reduced from **45 direct calls** to **0 calls** across all `app/api/v1/` routes).

### Remediation Breakdown
All direct `db.session.commit()` calls in `app/api/v1/` have been removed and wrapped inside service methods:
- `admin/taxonomy.py` (17 calls): Extracted to `marketplace_taxonomy_service.py` transactions.
- `marketplace/installations.py` (10 calls): Extracted to `deck_install_rebase_service.py` transactional operations handling persisted rebase errors.
- `flashcards/anki_imports.py` (6 calls): Extracted to `anki_import_service.py` (with review analytics rollups).
- `settings/integration_tokens.py` (4 calls): Handled via token service transactions.
- `admin/mcp_tokens.py` (2 calls): Handled via `mcp_access_token_service.py`.
- `billing/support.py` (2 calls): Handled via `app/services/payment/orders.py`.
- `marketplace/deck_releases.py` (2 calls): Handled via `publish_release_and_commit` and `update_auto_publish_setting_and_commit`.
- `analytics/routes.py` (1 call): Handled via `stats_overview.py` rollups.
- `admin/security_alerts.py` (1 call): Handled via alert service dismiss methods.

---

## 5. Dual Blueprint Exposure & Fragmented Study Routes - CANONICALIZED

- **Status**: **Completed**
- **Implementation**:
  - Created canonical `app/api/v1/learning/study.py` registering `study_bp` on `api_v1_bp` with `/study` URL prefix.
  - 14 core study endpoints (`/api/study/sessions`, `/api/study/next`, `/api/study/cards/<id>/answer`, `/api/study/sessions/<id>/commit`, etc.) are now canonically part of `api_v1_bp`.
  - Added explicit rate-limit exemption for `/api/study/` in `app/api/v1/__init__.py` to ensure high-frequency flashcard reviews do not trip daily API rate limits.
  - Route snapshot updated to **300 canonical routes** (`tests/snapshots/api_v1_routes.json`).


---

## 6. Query Bottlenecks & N+1 Performance Hotspots

1. **Deck Tree Subtree Rollup (`vocabulary_repository.py`)**:
   `build_browse_deck_tree_payload` calculates due/new/learn counts across recursive subtrees. While `DeckCloneDeckMap` batching was added, deep hierarchies still generate multiple database queries when `progress_counts=True`.
2. **Marketplace List Query Rollups**:
   Marketplace listing queries should be audited to ensure card count and sample card resolution use batch contexts identical to `DeckPublishBatchContext`.
