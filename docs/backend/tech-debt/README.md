# Flama Backend Technical Debt Catalog

> 2026-10-19 follow-up: use the [cleanup priorities and investigation plan](../LEGACY_CLEANUP_PLAN_2026-10-19.md)
> for the current scope. Retired shadow writer/backfill flags are removed there;
> the mapper/codec still support live NOTE authority. Historical model audits
> predate the Card, progress and Field ID contractions and are not a deletion list.

- **Domain**: Flask Modular Monolith & Persistence Layer
- **Last Audited**: 2026-10-15
- **Status**: Active Technical Debt Registry
- **Master Audit Report**: [Comprehensive Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md)

---

## 1. Executive Summary

The Flama backend exhibits high technical sophistication (derived virtual `Card` view ADR P11, decoupled `StudyProgressSubject` ADR P10, and logical overlay clone architecture). However, successive architectural refactoring phases have left several major technical debt hotspots where legacy patterns coexist with modern implementations. For cross-domain technical debt analysis and discrepancies catalog, see the master [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md).

---

## 2. Monolith 1: `app/services/flashcards_share_service.py` (3,685 LOC)

- **File Path**: `app/services/flashcards_share_service.py`
- **File Size**: **3,685 LOC / 147 KB**
- **Impact & Blast Radius**: Imported by **54 distinct files** across routes, repositories, CLI commands, and test suites (32 in `app/`, 1 in `scripts/`, 21 in `tests/`).

### Core Architectural Issues
1. **Divergent Implementation with `app/services/share/`**:
   An earlier refactoring created a modular package `app/services/share/` (containing `install.py`, `publish.py`, `overlay.py`, `cutover.py`, `helpers.py`, `constants.py`, `note_types.py`). However, `flashcards_share_service.py` was never decommissioned.
2. **Double-Fix Burden**:
   Any performance optimizations or bug fixes must be manually duplicated across both `flashcards_share_service.py` and `app/services/share/` to prevent divergence. For example, during the `DeckPublishBatchContext` optimization, logic had to be mirrored in both `app/services/flashcards_share_service.py:483-670` and `app/services/share/publish.py`.
3. **Bloated Responsibilities**:
   The file handles deck publishing, ratings, clone overlays, version releases, marketplace search filtering, and database transaction commits simultaneously.

### Remediation Plan
1. Phase 1: Re-export all symbols in `app/services/flashcards_share_service.py` from `app/services/share/`, turning the monolith into a thin compatibility facade.
2. Phase 2: Incrementally migrate all 54 calling files to import directly from `app/services/share/`.
3. Phase 3: Retire `app/services/flashcards_share_service.py`.

---

## 3. Monolith 2: `app/routes/vocabulary.py` (718 LOC)

- **File Path**: `app/routes/vocabulary.py`
- **File Size**: **718 LOC**

### Core Architectural Issues
1. **17 Dead 410 Gone Stubs**:
   Contains 17 legacy route functions that do nothing except return HTTP 410 (`create_level`, `create_topic`, `create_lesson`, `delete_lesson`, `delete_topic`, `open_topic`, `topic`, `study_topic`, `study_lesson`, `lesson`, `download_lesson_csv`, `save_column_width`, `create_entry`, `update_entry_field`, `update_entry_fields`, `bulk_update_entries`, `import_csv`) left over from the retired Level/Topic/Lesson structure.
2. **Endpoint Duplication**:
   Exposes `/vocabulary/api/browse/...` endpoints concurrently with canonical `/api/browse/...` (`app/api/v1/learning/browse.py`), causing routing ambiguity.
3. **HTML Form & Flash Postbacks**:
   Contains legacy HTML form POST handlers (`/decks/<id>/delete`, `/decks/<id>/reset`) that use `flask.flash()` and redirect to outdated URLs.

### Remediation Plan
1. Remove all 17 `410 Gone` stubs.
2. Deprecate `/vocabulary/api/browse/...` routes in favor of canonical `/api/browse/...`.
3. Migrate deck delete and progress reset operations to canonical JSON REST endpoints in `app/api/v1/decks/`.
4. Delete `app/routes/vocabulary.py`.

---

## 4. Transaction Boundary Leaks (`db.session.commit()` in Routes)

- **Architectural Violation**: According to `SYSTEM_ARCHITECTURE.md`, HTTP route handlers must never control transaction boundaries. Services are the sole owners of transactions.
- **Current State**: Exactly **45 direct `db.session.commit()` calls** exist across route handlers under `app/api/v1/`.

### Detailed Location Inventory
| Route File | Direct Commits | Operations Performed in Route Handler |
|---|---|---|
| `app/api/v1/admin/taxonomy.py` | **17 calls** | Category creation, ordering updates, and tag deletions directly committed in routes. |
| `app/api/v1/marketplace/installations.py` | **10 calls** | Deck installation records and local overlay mappings committed in HTTP routes. |
| `app/api/v1/flashcards/anki_imports.py` | **6 calls** | Chunk uploads and model mapping commits executed in route loop. |
| `app/api/v1/settings/integration_tokens.py` | **4 calls** | Yomitan and API token creation/revocation committed directly. |
| `app/api/v1/admin/mcp_tokens.py` | **2 calls** | Token revocation and issuance. |
| `app/api/v1/billing/support.py` | **2 calls** | Order checkout and donation status updates committed directly in routes. |
| `app/api/v1/marketplace/deck_releases.py` | **2 calls** | Release publishing and snapshot record commits executed in routes. |
| `app/api/v1/analytics/routes.py` | **1 call** | Analytics snapshot and review count rollups. |
| `app/api/v1/admin/security_alerts.py` | **1 call** | Alert dismissal committed in route. |

### Risks & Remediation Plan
- **Risks**: Partial commits leave database in inconsistent states if secondary steps fail; prevents composite transactions and complicates unit testing without full database fixtures.
- **Remediation**: Wrap multi-step mutations in application service methods (`TaxonomyService`, `InstallationService`, `TokenService`) and invoke `db.session.commit()` exclusively within service boundaries.

---

## 5. Dual Blueprint Exposure & Fragmented Study Routes

### Current State
REST APIs are fragmented across two separate blueprint hierarchies:
- **Canonical API (`app/api/v1/`)**: Registered under `/api` via `api_v1_bp`.
- **Legacy Route Blueprints (`app/routes/flashcards/`)**:
  - `app/routes/flashcards/study.py`: Houses all core flashcard study endpoints (`/api/study/sessions`, `/api/study/next`, `/api/study/cards/<id>/answer`, `/api/study/sessions/<id>/commit`).
  - `app/routes/flashcards/change_requests.py`: Houses `/api/deck-change-requests/...`.
  - `app/routes/flashcards/share.py`: Houses legacy `/api/shared/decks/...`.

### Documentation Discrepancy
Existing documentation (`AGENTS.md:48` and `SYSTEM_ARCHITECTURE.md`) erroneously claimed that study APIs were in `app/api/learning/study.py` (which does not exist).

### Remediation Plan
Migrate `app/routes/flashcards/study.py` into `app/api/v1/learning/study.py` and register it formally on `api_v1_bp`.

---

## 6. Query Bottlenecks & N+1 Performance Hotspots

1. **Deck Tree Subtree Rollup (`vocabulary_repository.py`)**:
   `build_browse_deck_tree_payload` calculates due/new/learn counts across recursive subtrees. While `DeckCloneDeckMap` batching was added, deep hierarchies still generate multiple database queries when `progress_counts=True`.
2. **Marketplace List Query Rollups**:
   Marketplace listing queries should be audited to ensure card count and sample card resolution use batch contexts identical to `DeckPublishBatchContext`.
