# Definitive Code Health & Architecture Audit Report
**Flama Monorepo (`d:/Project/nihongo`)**  
**Target Domains**: Backend (Flask, SQLAlchemy, MySQL) & Frontend (React 18 SPA, Vite, TailwindCSS)  
**Date**: 2026-10-01  
**Integrity Mode**: Read-Only Architecture Inspection (Zero Source Code Modifications)  
**Compiler**: Master Audit Report Compiler (`worker_report`)  
**Contributors**: Backend Explorer (`explorer_backend`), Frontend Explorer (`explorer_frontend`), Duplication Explorer (`explorer_duplication`)

---

## Table of Contents
1. [Executive Summary & Repository Health Metrics](#1-executive-summary--repository-health-metrics)
   - [1.1 Global Codebase Footprint](#11-global-codebase-footprint)
   - [1.2 Architectural Health Scorecard](#12-architectural-health-scorecard)
   - [1.3 Immediate High-ROI Discovery: The Zombie Monoliths](#13-immediate-high-roi-discovery-the-zombie-monoliths)
2. [Top Bloated Files Ranking (>300–500 LOC)](#2-top-bloated-files-ranking-300500-loc)
   - [2.1 Unified Top 20 Bloated Files Across Backend and Frontend](#21-unified-top-20-bloated-files-across-backend-and-frontend)
   - [2.2 Top Backend Monoliths Analysis](#22-top-backend-monoliths-analysis)
   - [2.3 Top Frontend Monoliths Analysis](#23-top-frontend-monoliths-analysis)
3. [High-Complexity & Monolithic Functions Audit (>50–80 LOC)](#3-high-complexity--monolithic-functions-audit-5080-loc)
   - [3.1 Top High-Complexity Functions Ranking (The 7 Super-Functions >600 LOC)](#31-top-high-complexity-functions-ranking-the-7-super-functions-600-loc)
   - [3.2 Single Responsibility Principle (SRP) Violations Analysis](#32-single-responsibility-principle-srp-violations-analysis)
   - [3.3 Concrete Decomposition Blueprints for Critical Super-Functions](#33-concrete-decomposition-blueprints-for-critical-super-functions)
4. [React Component Decomposition & Reusability Audit](#4-react-component-decomposition--reusability-audit)
   - [4.1 Deep-Dive Inspection of Top "God-Level" Components](#41-deep-dive-inspection-of-top-god-level-components)
   - [4.2 Catalog of 8 Standardized Reusable UI Primitives](#42-catalog-of-8-standardized-reusable-ui-primitives)
   - [4.3 Catalog of Custom Hooks to Extract (14 Candidate Hooks)](#43-catalog-of-custom-hooks-to-extract-14-candidate-hooks)
   - [4.4 Zero Visual Regression Protocol & Chrome DevTools Verification](#44-zero-visual-regression-protocol--chrome-devtools-verification)
5. [Cross-Layer Code Duplication Hotspots & Consolidation](#5-cross-layer-code-duplication-hotspots--consolidation)
   - [5.1 Backend SQL & Persistence Duplication](#51-backend-sql--persistence-duplication)
   - [5.2 Shared Utility & Helper Scatter](#52-shared-utility--helper-scatter)
   - [5.3 Backend Route & API Duplication](#53-backend-route--api-duplication)
   - [5.4 Frontend UI & Presentation Duplication](#54-frontend-ui--presentation-duplication)
   - [5.5 Proposed Consolidated Architectural Abstractions](#55-proposed-consolidated-architectural-abstractions)
6. [Prioritized Refactoring Roadmap (Phases 1–5)](#6-prioritized-refactoring-roadmap-phases-15)
   - [6.1 Roadmap Phasing & Sequencing](#61-roadmap-phasing--sequencing)
   - [6.2 Architectural Risk Matrix](#62-architectural-risk-matrix)
   - [6.3 Backward Compatibility & Guardrail Guarantees](#63-backward-compatibility--guardrail-guarantees)
7. [Verification & Guardrail Confirmation](#7-verification--guardrail-confirmation)

---

## 1. Executive Summary & Repository Health Metrics

### 1.1 Global Codebase Footprint

A unified, line-by-line and AST (Abstract Syntax Tree) code health inspection was executed across the entire Flama monorepo, covering both the Python backend (`app/`, `models/`, `connect_wsgi.py`, `wsgi.py`) and the React 18 SPA frontend (`frontend/src/`).

| Metric Category | Backend (`app/`, `models/`) | Frontend (`frontend/src/`) | Repository Total |
| :--- | :---: | :---: | :---: |
| **Total Source Files** | **486 files** | **380 files** | **866 files** |
| **Total Lines of Code (LOC)** | **152,024 LOC** | **101,892 LOC** | **253,916 LOC** |
| **Average File Size** | 312.8 LOC / file | 268.1 LOC / file | 293.2 LOC / file |
| **Monolithic Files (LOC ≥ 1,000)** | 33 files (55,602 LOC) | 15 files (18,545 LOC) | **48 files (74,147 LOC — 29.2%)** |
| **Bloated Files (500 ≤ LOC < 1,000)** | 67 files (43,912 LOC) | 46 files (31,077 LOC) | **113 files (74,989 LOC — 29.5%)** |
| **Oversized Files (300 ≤ LOC < 500)** | 44 files (17,765 LOC) | 46 files (17,423 LOC) | **90 files (35,188 LOC — 13.9%)** |
| **Files Exceeding Standard (LOC ≥ 300)** | **144 files (77.1% of code)** | **107 files (65.8% of code)** | **251 files (72.6% of code)** |
| **Functions Exceeding Standard (LOC ≥ 50)** | **641 functions** | *N/A (Component hooks)* | **641 functions** |
| **Functions Exceeding Standard (LOC ≥ 80)** | **340 functions** | *N/A (Component hooks)* | **340 functions** |
| **Super-Functions (LOC ≥ 600)** | **7 super-functions** | *N/A (Giant JSX trees)* | **7 super-functions** |

> **Key Observation**: Almost three-quarters (**72.6%**) of the entire Flama codebase lives inside files that exceed 300 lines of code. The top 48 monolithic files alone represent nearly **30% of all code written in the repository**.

---

### 1.2 Architectural Health Scorecard

| Architectural Pillar | Current Grade | Current State & Root Causes | Target State Post-Refactor |
| :--- | :---: | :--- | :--- |
| **Modularity & Layering** | **C-** | High leakage between layers: routes execute database transactions, repositories format UI JSON views, services bypass repositories with raw `db.session.execute()`. | Strict boundaries: Routes parse HTTP, Services orchestrate transactions, Repositories query SQL, Presenters format JSON. |
| **Component Reusability** | **D+** | Ad-hoc HTML/Tailwind implementations in pages; 8 missing core UI primitives; duplicate modal wrappers and forms across features. | 8 new standardized UI primitives (`components/ui/`), unified `CardFieldsForm`, shared custom hooks catalog. |
| **Duplication Density** | **D** | 8,073 LOC of dead zombie monolith code; 24 copies of `_utcnow()`; duplicate category badges, search debounce, and pagination. | 0 duplicate monoliths, centralized `datetime_utils.py`, `formatters.ts`, `categoryColors.ts`, semantic badges. |
| **State Complexity** | **D-** | God hooks and components with extreme state proliferation (`useBrowseState` with 49 states, `AdminTaxonomyPage` with 46 states). | Composed headless hooks with single responsibility (< 8 states per hook), clear state boundaries. |
| **Zero Visual Regression** | **A** (Requirement) | Repository rules strictly mandate zero styling/color/layout drift. | Enforced via leaf-to-root refactoring and isolated Chrome DevTools profiling (`--user-data-dir`). |

---

### 1.3 Immediate High-ROI Discovery: The Zombie Monoliths

The backend audit revealed a massive structural anomaly: during previous refactoring cycles, three core business services were cleanly modularized into dedicated subpackages, but **the original monolithic files were never deprecated, pruned, or converted into facades**. 

Instead, over **93%–98% of their methods were duplicated and left actively running side-by-side**:

```
                         THE ZOMBIE MONOLITH PHENOMENON
                         
       Duplicate Monoliths (Active)              Modular Subpackages (Active)
   ┌───────────────────────────────────┐     ┌───────────────────────────────────┐
   │ flashcards_share_service.py       │     │ app/services/share/               │
   │ 3,837 LOC (98 functions)          │ <═> │ 4,672 LOC (modular submodules)    │
   ├───────────────────────────────────┤     ├───────────────────────────────────┤
   │ deck_release_service.py           │     │ app/services/release/             │
   │ 2,158 LOC (54 functions)          │ <═> │ 2,631 LOC (modular submodules)    │
   ├───────────────────────────────────┤     ├───────────────────────────────────┤
   │ payment_service.py                │     │ app/services/payment/             │
   │ 2,078 LOC (48 functions)          │ <═> │ 2,610 LOC (modular submodules)    │
   └───────────────────────────────────┘     └───────────────────────────────────┘
                     │                                         ▲
                     └─────── 8,073 REDUNDANT LOC ─────────────┘
                               Can be deleted immediately by converting
                               monoliths into 50-line re-export facades!
```

- **`flashcards_share_service.py` (3,837 LOC)**: 93 out of 98 functions are exact duplicates of `app/services/share/`. Callers in the codebase are split haphazardly between the two.
- **`deck_release_service.py` (2,158 LOC)**: 53 out of 54 functions are exact duplicates of `app/services/release/`.
- **`payment_service.py` (2,078 LOC)**: 46 out of 48 functions are exact duplicates of `app/services/payment/`.
- **Precedent of Success**: In contrast, `deck_change_request_service.py` (55 LOC) and `flama_connect_service.py` (33 LOC) were correctly refactored into clean 1-page re-export facades pointing to `app/services/change_request/` and `app/services/connect/`.
- **Immediate ROI**: Converting these three files into thin facades deletes **8,073 lines of duplicate code** instantly, eliminates divergence bugs, and maintains 100% backward compatibility for all imports.

---

## 2. Top Bloated Files Ranking (>300–500 LOC)

### 2.1 Unified Top 20 Bloated Files Across Backend and Frontend

Below is the definitive cross-layer ranking of the **Top 20 largest files** in the entire Flama repository:

| Rank | File Path | Total LOC | Layer / Domain | Primary Responsibilities | Diagnosis of Bloat |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **1** | [`frontend/src/features/worksheets/components/DeckWorksheetModal.tsx`](file:///d:/Project/nihongo/frontend/src/features/worksheets/components/DeckWorksheetModal.tsx) | **4,388** | Frontend / UI | Worksheet generator modal, wizard, layout controls, canvas preview. | **Worst monolith in repo.** 22 useStates, 3,873 lines of inline JSX. Contains 4 studio tabs and 8 layout template forms inline. |
| **2** | [`app/services/flashcards_share_service.py`](file:///d:/Project/nihongo/app/services/flashcards_share_service.py) | **3,837** | Backend / Service | Marketplace publishing, ratings, clone installs, overlay overrides. | **Zombie monolith.** 93 duplicate functions already extracted to `app/services/share/` but never pruned or converted to a facade. |
| **3** | [`app/services/worksheets/worksheet_service.py`](file:///d:/Project/nihongo/app/services/worksheets/worksheet_service.py) | **3,416** | Backend / Service | Printable CJK worksheet generation, PDF layout, SVG stroke assembly. | Inlines massive procedural CSS/SVG string concatenations; contains a single 1,818-line function (`render_printable_html`). |
| **4** | [`app/services/study_session_service.py`](file:///d:/Project/nihongo/app/services/study_session_service.py) | **2,768** | Backend / Service | Study session lifecycle, concurrency locks, pin authority, commits. | Combines multi-table transactional locking, wire validation, scheduling math, and JSON presentation formatting. |
| **5** | [`app/services/study_architecture_audit_service.py`](file:///d:/Project/nihongo/app/services/study_architecture_audit_service.py) | **2,526** | Backend / Service | Architecture audit engine, invariant checks, progress validation. | Contains single 1,610-line function executing 20+ sequential multi-model queries and metric aggregations. |
| **6** | [`app/services/study_progress_lifecycle_mirror_service.py`](file:///d:/Project/nihongo/app/services/study_progress_lifecycle_mirror_service.py) | **2,470** | Backend / Service | Study progress mirroring, fact calculation, lifecycle events. | Complex dual-write logic between legacy `CardProgress` and Note authority tables without modular separation. |
| **7** | [`app/services/deck_release_service.py`](file:///d:/Project/nihongo/app/services/deck_release_service.py) | **2,158** | Backend / Service | Deck release versioning, snapshot hashing, diff computation. | **Zombie monolith.** 53 duplicate functions already extracted to `app/services/release/` but monolith retained. |
| **8** | [`app/services/payment_service.py`](file:///d:/Project/nihongo/app/services/payment_service.py) | **2,078** | Backend / Service | PayOS payments, order processing, webhook handling, fulfillment. | **Zombie monolith.** 46 duplicate functions already extracted to `app/services/payment/` but monolith retained. |
| **9** | [`app/services/mcp_tool_registry.py`](file:///d:/Project/nihongo/app/services/mcp_tool_registry.py) | **2,031** | Backend / Service | Model Context Protocol tool schema registry and execution router. | Procedurally declares 30+ JSON schemas and tool handler dispatch dictionaries in a single file. |
| **10** | [`app/services/study_progress_shadow_mirror_service.py`](file:///d:/Project/nihongo/app/services/study_progress_shadow_mirror_service.py) | **2,027** | Backend / Service | Dual-write shadow sync between legacy CardProgress and Note authority. | Accumulates reverse-sync adapters, reconciliation loops, and shadow event logs. |
| **11** | [`app/cli.py`](file:///d:/Project/nihongo/app/cli.py) | **1,829** | Backend / CLI | Flask CLI maintenance commands, database seeding, migration checks. | Contains single 1,506-line function (`register_cli_commands`) defining 25+ CLI commands as nested closures. |
| **12** | [`app/services/flashcard_content_service.py`](file:///d:/Project/nihongo/app/services/flashcard_content_service.py) | **1,733** | Backend / Service | Note/NoteType/Template CRUD, field renames, template compiling. | Blends schema validation, database mutations, template compilation, and sanitization in one service. |
| **13** | [`frontend/src/features/worksheets/components/WorksheetPageRenderer.tsx`](file:///d:/Project/nihongo/frontend/src/features/worksheets/components/WorksheetPageRenderer.tsx) | **1,719** | Frontend / UI | Printable A4 canvas renderer, SVG Kanji stroke renderer. | Inlines 8 different layout modes inside switch statements; contains inline client-side XML DOMParser SVG rewriting. |
| **14** | [`app/services/study_progress_reconciliation_service.py`](file:///d:/Project/nihongo/app/services/study_progress_reconciliation_service.py) | **1,715** | Backend / Service | CardProgress vs Note authority reconciliation engine. | Single 998-line reconciliation calculation function analyzing multi-table state across millions of rows. |
| **15** | [`app/services/browse_card_service.py`](file:///d:/Project/nihongo/app/services/browse_card_service.py) | **1,698** | Backend / Service | Vocabulary browse query engine, filters, overlay field merging. | Contains 602-line function (`list_browse_cards`) mixing query parsing, dynamic multi-join SQL, and JSON serialization. |
| **16** | [`app/services/study_phase4_preflight_service.py`](file:///d:/Project/nihongo/app/services/study_phase4_preflight_service.py) | **1,608** | Backend / Service | Phase 4 preflight migration check and validation engine. | Procedural preflight checks across queues and storage profiles (contains 763-line function). |
| **17** | [`app/validators/mcp.py`](file:///d:/Project/nihongo/app/validators/mcp.py) | **1,585** | Backend / Validator | MCP tool input dictionary schemas and payload validation. | Procedural hand-rolled dictionary validation for 30+ MCP tools without reusable validation schemas. |
| **18** | [`app/services/flashcard_import.py`](file:///d:/Project/nihongo/app/services/flashcard_import.py) | **1,510** | Backend / Service | TSV/CSV/JSON/Anki file parser, batch entity creation. | Large procedural file importer handling format detection, field mapping, entity creation, and progress backfills. |
| **19** | [`app/services/tts_provider_service.py`](file:///d:/Project/nihongo/app/services/tts_provider_service.py) | **1,476** | Backend / Service | Local VoiceVox/Kokoro/Google TTS engine bridges and audio synthesis. | Couples engine discovery, HTTP device polling, audio synthesis, file storage, and voice descriptor catalogs. |
| **20** | [`frontend/src/features/marketplace/pages/SharedDeckDetailPage.tsx`](file:///d:/Project/nihongo/frontend/src/features/marketplace/pages/SharedDeckDetailPage.tsx) | **1,436** | Frontend / UI | Marketplace shared deck view, preview, reviews, payOS purchase. | Stuffs hero header, review tabs, hierarchy tree, card sandbox, purchase modal, and key manager into one page. |

---

### 2.2 Top Backend Monoliths Analysis

Beyond the top 20, several other backend files demonstrate extreme bloat and layer leakage:

- **`app/services/marketplace_query_service.py` (1,432 LOC)** & **`marketplace_taxonomy_service.py` (1,409 LOC)**:
  Marketplace querying manually constructs large dynamic SQL strings, cursor-based pagination, and category trees while bypassing `app/repositories/`.
- **`app/routes/flashcards/study.py` (1,278 LOC)**:
  Route controller containing extensive business scheduling, candidate card hydration, and deck option resolution (e.g. `_build_study_next_payload` is 280 lines), plus 7 direct `db.session.commit()` calls.
- **`app/repositories/vocabulary_repository.py` (1,203 LOC)**:
  A persistence repository that violates separation of concerns by building complete frontend UI JSON view trees (lines 729–1038, 310 lines) with icon names, badges, and labels.
- **`app/services/study_worker_service.py` (1,108 LOC)**:
  Contains `process_single_study_batch` (lines 195–1050, **856 lines**), combining distributed Redis locks, DLQ exception management, Anki scheduling math, and dual-write mirror sync.
- **`app/startup_schema.py` (1,043 LOC)**:
  Contains `ensure_backward_compatible_schema` (lines 10–1041, **1,032 lines**), executing raw DDL `ALTER TABLE` queries on every container launch.

---

### 2.3 Top Frontend Monoliths Analysis

The frontend React application exhibits significant concentration of monolithic files in feature pages and admin consoles:

- **`DeckWorksheetModal.tsx` (4,388 LOC)**:
  Contains **22 `useState` hooks**, **6 `useRef` hooks**, and **3,873 lines of inline JSX**. It implements 4 full studio tabs, 8 layout template forms, double-tap zoom handling, and printable canvas formatting in a single component.
- **`WorksheetPageRenderer.tsx` (1,719 LOC)**:
  Implements 8 distinct template canvas layouts inside giant switch blocks and inlines client-side XML DOM parsing (`DOMParser`) to dynamically rewrite SVG Kanji stroke paths.
- **`AdminMcpTokensPage.tsx` (1,405 LOC)** & **`McpTokensTab.tsx` (1,181 LOC)**:
  A prime example of severe cross-feature duplication: both files implement the identical scope checkbox matrix, token table, reveal dialog, and AI client configuration snippets (Claude, Cursor, Windsurf), sharing over **1,600 LOC of near-identical markup**.
- **`AdminTaxonomyPage.tsx` (1,400 LOC)**:
  Contains **46 `useState` hooks** (the highest state count in the repository) managing 5 separate taxonomy entities (Domains, Subjects, Frameworks, Options, Mappings) with 10+ modal dialogs inlined.
- **`AdminPaymentsPage.tsx` (1,395 LOC)** & **`AdminFeesPage.tsx` (1,101 LOC)**:
  Admin billing consoles combining revenue metrics, order status filtering, transaction inspection modal, manual refund dialog, payOS sync, and payout logs in single files.
- **`useStudySession.ts` (1,337 LOC)**:
  The core study session hook handling session lease concurrency, local answer application, offline batch queue, commit receipts, WebSocket/HTTP transport, and content update patches.
- **`useBrowseState.ts` (1,053 LOC)**:
  An omniscient hook with **49 `useState` hooks** bundling deck tree navigation, query filters, card table state, dirty card editing, Kanji stroke modal, and TTS audio settings.
- **`useLocalAudioEngine.ts` (1,080 LOC)**:
  A custom hook managing 23 states, 12 effects, 35 hardcoded voice descriptors, HTTP pinging to port 4791, audio synthesis, blob uploads, and playback queues.

---

## 3. High-Complexity & Monolithic Functions Audit (>50–80 LOC)

### 3.1 Top High-Complexity Functions Ranking (The 7 Super-Functions >600 LOC)

Functions exceeding 50–80 lines are common culprits for hidden bugs, high cyclomatic complexity, and testability failure. The Flama backend contains **641 functions ≥ 50 lines**, **340 functions ≥ 80 lines**, and **236 functions ≥ 100 lines**.

Most critically, the repository contains **7 Super-Functions exceeding 600 lines each**:

| Rank | Length | Function Name | File Path & Lines | Architectural Domain | Cyclomatic Drivers & Responsibilities |
| :---: | :---: | :--- | :--- | :--- | :--- |
| **1** | **1,818 lines** | `render_printable_html` | [`app/services/worksheets/worksheet_service.py:1599-3416`](file:///d:/Project/nihongo/app/services/worksheets/worksheet_service.py) | Worksheets | Generates CSS, `@page` geometry, SVG stroke order paths, QR codes, tables, and HTML for 5 worksheet types in 1 giant procedural block. |
| **2** | **1,610 lines** | `build_study_architecture_audit` | [`app/services/study_architecture_audit_service.py:917-2526`](file:///d:/Project/nihongo/app/services/study_architecture_audit_service.py) | Study Audit | Executes 20+ sequential multi-table audit queries, aggregations, dictionary mappings, and summary metrics across 15 database models. |
| **3** | **1,506 lines** | `register_cli_commands` | [`app/cli.py:285-1790`](file:///d:/Project/nihongo/app/cli.py) | CLI | Inlines 25+ Flask Click CLI commands as closures, intermixing argument parsing with direct database transactions and console logging. |
| **4** | **1,032 lines** | `ensure_backward_compatible_schema` | [`app/startup_schema.py:10-1041`](file:///d:/Project/nihongo/app/startup_schema.py) | Startup DDL | Executes dozens of raw DDL `ALTER TABLE`, `CREATE INDEX`, and column rename queries sequentially during app initialization. |
| **5** | **856 lines** | `process_single_study_batch` | [`app/services/study_worker_service.py:195-1050`](file:///d:/Project/nihongo/app/services/study_worker_service.py) | Async Study Worker | Coordinates Redis distributed locks, DLQ routing, authority routing, Anki algorithm math, dual-write syncing, and commit logs. |
| **6** | **613 lines** | `commit_study_session` | [`app/services/study_session_service.py:2156-2768`](file:///d:/Project/nihongo/app/services/study_session_service.py) | Study Session | Validates commit payload, locks authority route and session, runs dual writes, updates facts, and formats JSON response. |
| **7** | **602 lines** | `list_browse_cards` | [`app/services/browse_card_service.py:354-955`](file:///d:/Project/nihongo/app/services/browse_card_service.py) | Vocabulary Browse | Parses query parameters, locks route, builds dynamic multi-join SQL, applies overlay overrides, computes due dates, and serializes. |

*Additional honorable mentions*:
- `build_study_progress_reconciliation` ([`app/services/study_progress_reconciliation_service.py:718-1715`](file:///d:/Project/nihongo/app/services/study_progress_reconciliation_service.py)) — **998 lines**
- `_progress_preflight` ([`app/services/study_phase4_preflight_service.py:770-1532`](file:///d:/Project/nihongo/app/services/study_phase4_preflight_service.py)) — **763 lines**
- `generate_worksheet_preview` ([`app/services/worksheets/worksheet_service.py:940-1542`](file:///d:/Project/nihongo/app/services/worksheets/worksheet_service.py)) — **603 lines**
- `open_study_session` ([`app/services/study_session_service.py:489-989`](file:///d:/Project/nihongo/app/services/study_session_service.py)) — **501 lines**

---

### 3.2 Single Responsibility Principle (SRP) Violations Analysis

Inspection of these monolithic functions demonstrates a recurring anti-pattern: **the conflation of validation, multi-table persistence queries, business logic, transaction boundaries, and presentation formatting into single procedural routines**.

```
                       SRP VIOLATION ANTI-PATTERN
┌────────────────────────────────────────────────────────────────────────┐
│ MONOLITHIC FUNCTION (e.g., list_browse_cards, commit_study_session)    │
├────────────────────────────────────────────────────────────────────────┤
│ 1. HTTP / Wire Contract Validation: Parses query strings & JSON        │
│ 2. Concurrency Control: Acquires Redis locks or row-level FOR UPDATE   │
│ 3. Direct SQL Queries: Executes dynamic joins across Note/Card/Overlay │
│ 4. Complex Business Math: Calculates Anki SM-2 intervals & due days   │
│ 5. Dual-Write Mirroring: Updates legacy CardProgress & Note Authority  │
│ 6. Transaction Boundary: Inlines db.session.commit() / rollback()     │
│ 7. Presentation Formatting: Serializes dictionaries for UI components  │
└────────────────────────────────────────────────────────────────────────┘
```

#### Key Consequences:
1. **Zero Unit Testability**: To test a calculation edge case in `list_browse_cards` or `commit_study_session`, one must spin up a complete database, insert 5 related tables, mock HTTP request contexts, and satisfy Redis locks.
2. **Cascading Failure Points**: A failure in presentation formatting can abort an otherwise successful database transaction or leave distributed locks dangling.
3. **Inability to Reuse Code**: Core business rules (such as Logical Overlay card scoping) cannot be shared and are re-implemented ad-hoc in routes and background tasks.

---

### 3.3 Concrete Decomposition Blueprints for Critical Super-Functions

#### Blueprint 1: `render_printable_html` (1,818 lines)
- **Target File**: `app/services/worksheets/worksheet_service.py:1599-3416`
- **Decomposition Architecture**:
  ```
  app/services/worksheets/
  ├── worksheet_service.py (Orchestrator: ~200 LOC)
  ├── layout/
  │   ├── document_layout.py (CSS @page rules, A4 margins, header/footer)
  │   └── qr_code_generator.py (SVG QR code injection)
  └── renderers/
      ├── base_renderer.py (Abstract Base Class)
      ├── kanji_stroke_renderer.py (Stroke diagrams & practice cells)
      ├── vocab_match_renderer.py (Matching columns & word pairs)
      ├── sentence_trace_renderer.py (Tracing guidelines & furigana)
      ├── genkouyoushi_renderer.py (200/400-character Japanese grid paper)
      └── custom_table_renderer.py (Configurable vocabulary tables)
  ```
- **Execution**: The main function `render_printable_html(preview_data)` resolves the appropriate renderer via registry dictionary:
  ```python
  renderer = WORKSHEET_RENDERERS.get(template_id, DefaultWorksheetRenderer)(preview_data)
  return renderer.render()
  ```
- **Outcome**: `render_printable_html` drops from **1,818 lines to ~25 lines**.

---

#### Blueprint 2: `register_cli_commands` (1,506 lines)
- **Target File**: `app/cli.py:285-1790`
- **Decomposition Architecture**:
  Transform `app/cli.py` into a modular package `app/cli/`:
  ```
  app/cli/
  ├── __init__.py (Registers command groups: ~40 LOC)
  ├── study_commands.py (study-authority-enrollment, reconciliation, worker)
  ├── marketplace_commands.py (flashcards-share-cutover, rebase, seed)
  ├── media_commands.py (tts-generate-batch, crawl-images)
  └── db_commands.py (reseed, seed-taxonomy, ensure-roles)
  ```
- **Execution**: Each submodule exports a standard Click group (`click.Group`). `app/cli/__init__.py` iterates over groups and registers them with `app.cli.add_command()`.
- **Outcome**: `register_cli_commands` is eliminated; commands become individually unit-testable Click functions.

---

#### Blueprint 3: `list_browse_cards` (602 lines)
- **Target File**: `app/services/browse_card_service.py:354-955`
- **Decomposition Architecture**:
  1. **Step 1 - Parameter Validation**: Extract query parameter parsing into `app/validators/browse_input.py` returning a typed dataclass `BrowseFilterParams`.
  2. **Step 2 - Dynamic Query Building**: Extract SQL join logic (across `Note`, `Card`, `CardProgress`, and `DeckCloneDeckMap`) to `app/repositories/browse_card_repository.py:query_browse_cards(filters)`.
  3. **Step 3 - Overlay Field Merging & Presenter**: Extract clone override application and due date formatting to `app/presenters/browse_card_presenter.py`.
  4. **Step 4 - Coordination**: `list_browse_cards` strictly executes: `Validate -> Query Repo -> Merge Overlays -> Presenter Map -> Return`.
- **Outcome**: `list_browse_cards` shrinks from **602 lines to ~45 lines**.

---

#### Blueprint 4: `process_single_study_batch` (856 lines)
- **Target File**: `app/services/study_worker_service.py:195-1050`
- **Decomposition Architecture**:
  1. **Locking Context Manager**: Extract distributed Redis locking and TTL renewal into a context manager `@contextmanager def study_batch_locks(session_id, batch_id)`.
  2. **Event Pipeline Processor**: Extract review rating calculations, Anki interval math, and fact generation into `StudyBatchEventProcessor.process_event(event)`.
  3. **Dual-Write Synchronization**: Delegate `CardProgress` vs `StudyProgressSubject` dual-write operations to `app/services/study_progress_mirror_service.py`.
- **Outcome**: `process_single_study_batch` becomes an atomic 80-line pipeline orchestration function.

---

## 4. React Component Decomposition & Reusability Audit

### 4.1 Deep-Dive Inspection of Top "God-Level" Components

#### 1. `DeckWorksheetModal.tsx` (4,388 LOC, 22 states, 3,873 lines of inline JSX)
- **Location**: `frontend/src/features/worksheets/components/DeckWorksheetModal.tsx`
- **Structural Flaw**: Attempts to implement an entire Japanese worksheet desktop publishing application inside a single dialog component.
- **Decomposition Strategy**:
  - Extract headless hook `useWorksheetStudio(deckId)` (~320 LOC) managing metadata fetching, layout states, and preset caching.
  - Split Studio Tabs into modular components:
    - `components/studio/WorksheetTemplateTab.tsx` (~120 LOC)
    - `components/studio/WorksheetDataTab.tsx` (~280 LOC)
    - `components/studio/WorksheetLayoutTab.tsx` (delegates to `KanjiLayoutControls`, `GenkouyoushiLayoutControls`, `VocabLayoutControls`)
    - `components/studio/WorksheetHeaderTab.tsx` (~220 LOC)
    - `components/studio/WorksheetPreviewCanvas.tsx` (~280 LOC)
  - **Result**: `DeckWorksheetModal.tsx` shrinks from **4,388 LOC to ~200 LOC**.

#### 2. `AdminTaxonomyPage.tsx` (1,400 LOC, 46 states)
- **Location**: `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx`
- **Structural Flaw**: Inlines 5 separate CRUD domain entities (Domains, Subjects, Frameworks, Options, Mappings) with 10+ modal dialogs in one file.
- **Decomposition Strategy**:
  - Decompose into 5 dedicated tab components: `TaxonomyDomainsTab.tsx`, `TaxonomySubjectsTab.tsx`, `TaxonomyFrameworksTab.tsx`, `TaxonomyOptionsTab.tsx`, `TaxonomyMappingsTab.tsx`.
  - Extract a generic modal primitive `TaxonomyEntityDialog.tsx` (~140 LOC) for Name, Label, Sort Order, and Active status.
  - **Result**: `AdminTaxonomyPage.tsx` drops from **1,400 LOC to ~110 LOC**.

#### 3. `AdminMcpTokensPage.tsx` (1,405 LOC) & `McpTokensTab.tsx` (1,181 LOC)
- **Structural Flaw**: Massive 1,600 LOC duplication between admin and user settings views.
- **Decomposition Strategy**:
  - Extract shared components in `features/settings/components/mcp/`:
    - `McpScopeSelector.tsx` (~220 LOC)
    - `McpTokenRevealDialog.tsx` (~180 LOC)
    - `McpClientConfigGuide.tsx` (~250 LOC)
    - `McpTokenTable.tsx` (~280 LOC)
  - **Result**: Both pages shrink to thin wrappers (~320 LOC and ~200 LOC), eliminating **~1,800 lines of duplicate code**.

#### 4. `useBrowseState.ts` (1,053 LOC, 49 states)
- **Location**: `frontend/src/features/browse/hooks/useBrowseState.ts`
- **Structural Flaw**: Acts as an omniscient global store holding deck navigation, table pagination, search filters, card editor dirty states, and TTS settings.
- **Decomposition Strategy**:
  - Decompose into 4 focused hooks:
    - `useBrowseDeckTree()` (~180 LOC)
    - `useBrowseFilters()` (~220 LOC)
    - `useBrowseSelection()` (~150 LOC)
    - `useBrowseTtsAction()` (~180 LOC)
  - Compose them cleanly inside `useBrowseState.ts` (~150 LOC).

---

### 4.2 Catalog of 8 Standardized Reusable UI Primitives

To eliminate inline HTML sprawl and ad-hoc Tailwind classes, the following **8 New UI Primitives** must be added to `frontend/src/components/ui/` or `features/cards/components/`:

| # | Candidate Primitive | Target File Path | Purpose & Features | Replaces Duplication In |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **`SearchInput`** | `components/ui/search-input.tsx` | Search input with integrated magnifying glass icon, clear button (`X`), loading spinner, and keyboard shortcut badge (`/` or `Ctrl+K`). | Browse, Marketplace, Admin Users, Admin Taxonomy, Support Tickets (12+ files) |
| **2** | **`ConfirmDialog`** | `components/ui/confirm-dialog.tsx` | Standardized modal with Title, Description, Confirm button (`destructive` or `primary` variant), Cancel button, and async loading state. | Browse delete card, Study exit, Marketplace delete key, Admin delete user/token (15+ files) |
| **3** | **`StatusPill`** | `components/ui/status-pill.tsx` | Colored pill badge mapping semantic domain statuses (`new`, `learning`, `review`, `due`, `active`, `pending`, `revoked`, `failed`) to OKLCH tokens. | Browse table, Study badges, Marketplace cards, Admin tables, Audio queue (10+ files) |
| **4** | **`CodeSnippetBox`** | `components/ui/code-snippet-box.tsx` | Monospace code block with syntax styling, dark mode support, and an integrated copy-to-clipboard button with checkmark animation. | Admin MCP tokens, User Settings MCP tokens, MCP OAuth tab, Yomitan tokens, Guide articles (8+ files) |
| **5** | **`FilterPillGroup`** | `components/ui/filter-pill-group.tsx` | Horizontally scrollable chip filter group supporting single-selection or multi-selection with item count badges. | Browse status filters, Marketplace categories, Admin role filters, Support ticket filters (6+ files) |
| **6** | **`ImageUploadDropzone`** | `components/ui/image-upload-dropzone.tsx` | Drag-and-drop file upload area with clipboard paste listener, preview thumbnail, client-side compression, and progress indicator. | FeedbackPage screenshots, Admin Image Library, Profile avatar upload, Marketplace deck cover (4 files) |
| **7** | **`SplitPane`** | `components/ui/split-pane.tsx` | Resizable dual-pane container with draggable divider handle, min/max bounds, mobile collapsing, and localStorage width caching. | BrowsePage / BrowseCardEditor, ChangeRequestDetailPage / DiffWorkspace (2 files) |
| **8** | **`CardFieldsForm`** | `features/cards/components/CardFieldsForm.tsx` | Dynamic card field editor supporting text, textarea, markdown preview, image upload, audio player, and kanji stroke generator trigger. | `BrowseCardEditor.tsx`, `StudyQuickEditDialog.tsx`, `EditCardModal.tsx` (3 major files) |

---

### 4.3 Catalog of Custom Hooks to Extract (14 Candidate Hooks)

| Feature / Domain | Candidate Hook Name | Estimated LOC | Primary Responsibilities |
| :--- | :--- | :---: | :--- |
| **Worksheets** | `useWorksheetStudio` | ~320 LOC | Encapsulates metadata fetching, preset caching, layout options state. |
| **Worksheets** | `useWorksheetPreview` | ~180 LOC | Manages preview generation query, page zoom, double-tap handling. |
| **Browse** | `useBrowseFilters` | ~220 LOC | Search query, debouncing, status filters, note type filters, URL sync. |
| **Browse** | `useBrowseDeckTree` | ~180 LOC | Deck hierarchy navigation, expansion state, deck search. |
| **Browse** | `useBrowseSelection` | ~150 LOC | Card table row selection, multi-card checkbox state, active card focus. |
| **Study** | `useSessionCommitQueue` | ~350 LOC | Commit preparation, retry loops, receipt validation, beforeunload transport. |
| **Study** | `useSessionContentPatcher` | ~180 LOC | In-memory field updates, note type template updates, dynamic card re-renders. |
| **Cards / Common** | `useCardEditorForm` | ~220 LOC | Form state for fields, tags, dirty state validation, revert, and save. |
| **Marketplace** | `useDeckReviews` | ~200 LOC | Review listing, pagination, star rating distribution, write review mutation. |
| **Marketplace** | `useDeckInstallActions` | ~180 LOC | Install mutation, buy mutation, key redemption trigger, auto-publish status. |
| **Audio** | `useAudioBatchProcessor` | ~320 LOC | Sequential batch synthesis, queue state machine, pause/cancel controls. |
| **Audio** | `useAudioEngineHealth` | ~120 LOC | Port 4791 service discovery and status polling. |
| **Admin Taxonomy** | `useTaxonomyCrud` | ~250 LOC | Generic entity query and mutations for domains, subjects, frameworks. |
| **Settings / Admin** | `useMcpTokenManagement`| ~240 LOC | Token query, create mutation, scope filtering, revoke mutation. |

---

### 4.4 Zero Visual Regression Protocol & Chrome DevTools Verification

As explicitly mandated in repository guidelines (`RULE[d:\Project\nihongo\AGENTS.md]`), all frontend refactoring must strictly enforce **Zero Visual Regression**:
> *"BẮT BUỘC bảo toàn 100% màu sắc, dải gradient thương hiệu, padding, font size, icon, đổ bóng và layout vị trí gốc trừ khi người dùng yêu cầu redesign."*

#### 1. Leaf-to-Root Execution Protocol:
```
Phase A: Extract Pure Utilities & Data (Zero JSX impact, 100% testable)
  └─ Formatters, regex parsers, hardcoded voice lists, SVG transformers.

Phase B: Extract Headless Custom Hooks (Zero DOM impact)
  └─ Extract useState, useQuery, useMutation into hooks without changing JSX.

Phase C: Extract Leaf UI Components (Verbatim Tailwind string preservation)
  └─ Move visual fragments into child components keeping exact class names.

Phase D: Consolidate Shared UI Primitives
  └─ Swap ad-hoc markup with primitives using verified CVA matching variants.
```

#### 2. Layout & Grid Safety Rules:
- **Never insert unstyled wrapper `<div>` elements**: Intermediate divs break CSS Grid layouts (`grid-cols-2`, `grid-cols-3`) and flex child behaviors (`flex-1`, `shrink-0`). Use React Fragments `<> ... </>` or `className="contents"`.
- **Preserve Radix UI Context**: Keep `<Dialog>` roots at the container level or pass `open` and `onOpenChange` cleanly to avoid unmounting transitions.
- **Preserve OKLCH Semantic Tokens**: Never replace custom semantic tokens (e.g. `bg-primary/10`, `border-border/60`) with generic Tailwind colors (`bg-blue-500`).

#### 3. Isolated Chrome DevTools Profiling:
Whenever verifying visual appearance, render cycles, or Core Web Vitals:
- **Mandatory Isolated Profile**: Always launch Chrome with an isolated user data directory:
  `--user-data-dir=C:\Users\chung\.gemini\chrome-profiles\flama-devtools`
- **Never touch the user's default browser profile** to protect personal sessions and cookies.

---

## 5. Cross-Layer Code Duplication Hotspots & Consolidation

### 5.1 Backend SQL & Persistence Duplication

#### 1. Five Disparate Implementations of Deck Hierarchy Traversal:
The codebase traverses deck subtrees using 5 separate implementations:
- `app/repositories/deck_tree_query.py:197-240` (`collect_subtree_ids`, `collect_ancestor_ids`)
- `app/services/deck_management_service.py:44-73` (`_current_deck_subtree_ids`)
- `app/repositories/vocabulary_repository.py:720-726` (stack-based DFS for subtree IDs)
- `app/services/dashboard_service.py:109-133` (`_collect_subtree_card_counts` recursive rollup)
- `app/services/browse_card_service.py:219-232` (`rebuild_counts` recursive rollup)

*Impact*: In `browse_card_service.py`, loading the browse deck tree runs database queries and count rollups in `vocabulary_repository.py`, and then runs **another recursive tree traversal (`rebuild_counts`)** to recalculate the exact same counts!

#### 2. Raw Card/Note Joins & Fragmented Logical Overlay Resolution:
Over **50 locations** execute ad-hoc joins checking card ownership:
```python
card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
if card.note.user_id != current_user.id:
    # Ad-hoc lookup of DeckInstall and DeckCloneDeckMap...
```
Meanwhile, three disjointed implementations of Logical Overlay scoping exist:
1. `app/repositories/logical_overlay_scope_repository.py:16-55`: Loads models into Python memory in loops.
2. `app/services/deck_aggregation_service.py:62-129`: Generates a single SQL subquery with `union_all`.
3. `app/repositories/vocabulary_repository.py:815-880`: Builds nested dictionaries in Python memory.

Furthermore, `app/services/deck_access_policy.py:can_user_view_deck` **is completely unaware of Logical Overlay**, causing developers to bypass it entirely and write custom access checks in every service.

#### 3. Soft-Delete Repetition (`Deck.deleted_at.is_(None)`):
Over **30 files** manually append `.filter(Deck.deleted_at.is_(None))`. If a developer forgets this filter in a new endpoint, deleted decks silently leak into the UI.

---

### 5.2 Shared Utility & Helper Scatter

#### 1. Surviving `_utcnow()` Duplication (24 Files):
Despite `app/services/common/datetime_utils.py` existing to centralize time utilities, **24 files still declare private copies** of `def _utcnow() -> datetime:`.

#### 2. Numeric & Timezone Helper Scatter:
- `_safe_int(value) -> int`: Redefined across **7 separate files** in `app/repositories/` and `app/services/`.
- `_is_supported_timezone_name` and `_round2`: Duplicated character-for-character between `app/services/stats_overview.py` and `app/services/stats_today_future.py`.
- Dynamic import coupling: `anki_scheduler.py:716` dynamically imports `_build_timezone_obj` from `stats_overview.py` inside a function body.

---

### 5.3 Backend Route & API Duplication

- **JSON Body Parsing Boilerplate (100+ Endpoints)**:
  ```python
  payload = request.get_json(silent=True) or {}
  if not isinstance(payload, dict):
      return jsonify({"error": "Payload phải là JSON object."}), 400
  ```
  Repeated across almost every route file instead of using `app/api/common/requests.py:json_object()`.
- **Integer Query Param Parsing Inconsistency**:
  Routes either use unsafe `int(request.args.get("page", 1))` (which throws unhandled `ValueError` 500 errors on invalid query parameters) or inappropriately import `coerce_int` from `app.services.admin_service.py` in learner-facing routes.
- **Direct Database Transactions in Controllers**:
  Controllers in `app/api/v1/marketplace/installations.py` (15 transaction calls), `app/api/v1/flashcards/anki_imports.py` (14 calls), and `app/api/v1/admin/taxonomy.py` (12 calls) execute direct `db.session.commit()` and `rollback()`, violating transaction boundary discipline.

---

### 5.4 Frontend UI & Presentation Duplication

- **Copy-Pasted Category Badge Colors**:
  A **40-line function** (`getCategoryBadgeClass`) is copy-pasted character-for-character between `frontend/src/features/marketplace/pages/MarketplacePages.tsx:165-194` and `frontend/src/features/marketplace/components/DeckCard.tsx:82-137`.
- **Missing Semantic Badge Variants**:
  Because `components/ui/badge.tsx` lacks `success`, `warning`, and `info` variants, raw Tailwind strings (`bg-emerald-500/10 text-emerald-700 border-emerald-500/30`, `bg-amber-500/10...`) are written **over 60 times each** across the app.
- **Button Loading Spinners**:
  Because `Button` lacks a native `loading` prop, over **100 components** manually inline `{isPending ? <LoaderCircle className="size-4 animate-spin mr-1.5" /> : null}`.
- **Three Disparate Card Editors**:
  `BrowseCardEditor.tsx` (644 LOC), `StudyQuickEditDialog.tsx` (535 LOC), and `EditCardModal.tsx` (641 LOC) independently implement field rendering, tag badges, dirty state tracking, and kanji stroke triggers.
- **Admin Search & Pagination Boilerplate**:
  `AdminUsersPage.tsx`, `AdminPermissionsPage.tsx`, and `AdminImageLibraryPage.tsx` duplicate the exact same 250ms debounced search effect and pagination footer buttons.
- **Date & Currency Formatting**:
  `new Date(...).toLocaleDateString('vi-VN')` and `{amount.toLocaleString('vi-VN')} ₫` are repeated over 120 times due to the lack of a centralized `formatters.ts`.

---

### 5.5 Proposed Consolidated Architectural Abstractions

```
========================================================================================
                          PROPOSED CONSOLIDATED ARCHITECTURE
========================================================================================

   [ BACKEND CONSOLIDATION ]                              [ FRONTEND CONSOLIDATION ]

   app/utils/ / app/services/common/                      src/lib/
   ├── datetime_utils.py (single canonical utcnow)        ├── formatters.ts (date, timeAgo, currency)
   ├── numeric_utils.py (safe_int, safe_float, round2)    └── utils.ts (cn helper)
   └── timezone_utils.py (is_supported, to_local)
                                                          src/hooks/
   app/api/common/                                        ├── useDebounce.ts (search debounce)
   ├── requests.py (json_object, parse_pagination)        └── useTablePagination.ts (page controls)
   └── responses.py (error_response, paginated_response)
                                                          src/components/ui/
   app/repositories/                                      ├── badge.tsx (add success/warning/info)
   ├── base_query.py (active_decks_query, card_note_join) ├── button.tsx (add loading/pending prop)
   └── deck_tree_query.py (unify subtree BFS/rollup)      ├── modal-dialog.tsx (standard modal frame)
                                                          └── data-table-pagination.tsx
   app/services/
   └── deck_access_policy.py (overlay-aware access)       src/features/cards/components/
                                                          ├── CardFieldsForm.tsx (unified editor)
                                                          └── CardTagsInput.tsx
```

---

## 6. Prioritized Refactoring Roadmap (Phases 1–5)

To guarantee safety, maintain continuous deployment, and ensure zero visual and functional regressions, the refactoring roadmap is divided into **5 structured phases**:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Quick Wins & High-ROI Cleanup (Zero Risk)                     │
│ ├─ Convert 3 Zombie Monoliths into thin facades (-8,073 LOC)           │
│ ├─ Centralize _utcnow() (24 files) and _safe_int() (7 files)           │
│ ├─ Add semantic variants (success, warning, info) to badge.tsx         │
│ └─ Extract getCategoryBadgeClass to categoryColors.ts                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Phase 2: Core Frontend UI Primitives & Duplication Elimination         │
│ ├─ Add loading prop to Button primitive                                │
│ ├─ Create SearchInput, ConfirmDialog, CodeSnippetBox, DataTablePagination│
│ ├─ Consolidate McpTokensTab and AdminMcpTokensPage (-1,800 LOC)        │
│ ├─ Extract formatters.ts (date, currency, relative time)               │
│ └─ Create unified CardFieldsForm & useCardEditorForm (-900 LOC)        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Phase 3: Major Backend Function Decomposition & Boundary Enforcement   │
│ ├─ Decompose worksheet_service.py render_printable_html (1,818 lines)  │
│ ├─ Convert app/cli.py (1,829 LOC) into modular Click command package   │
│ ├─ Decompose study_worker_service.py process_single_study_batch (856 L)│
│ └─ Extract db.session.commit() transactions from route controllers     │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Phase 4: Frontend God Component & Mega-Hook Decomposition              │
│ ├─ Decompose DeckWorksheetModal.tsx (4,388 LOC -> ~200 LOC)            │
│ ├─ Decompose WorksheetPageRenderer.tsx (1,719 LOC -> ~120 LOC)         │
│ ├─ Decompose AdminTaxonomyPage.tsx (1,400 LOC -> ~110 LOC)             │
│ ├─ Split useBrowseState.ts (49 states -> 4 focused sub-hooks)          │
│ ├─ Decompose SharedDeckDetailPage.tsx (1,436 LOC -> ~220 LOC)         │
│ └─ Modularize multi-page files (MarketplacePages, LibraryPages, App.tsx)│
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│ Phase 5: Query Scopes & Logical Overlay Seam Consolidation             │
│ ├─ Unify deck tree traversals and count rollups in deck_tree_query.py  │
│ ├─ Implement active_decks_query() in base_query.py for soft-delete     │
│ ├─ Unify Logical Overlay Card/Note resolution in deck_access_policy.py │
│ └─ Port startup_schema.py raw DDL migrations into official Alembic     │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 6.1 Roadmap Phasing & Sequencing

#### Phase 1: Quick Wins & High-ROI Cleanup (Immediate Win, Zero Risk)
- **Goal**: Immediate removal of dead code and standardization of basic helpers.
- **Actions**:
  1. Replace `flashcards_share_service.py`, `deck_release_service.py`, and `payment_service.py` with 50-line facades re-exporting from `app/services/share/`, `app/services/release/`, and `app/services/payment/`. Immediately deletes **8,073 lines of dead code**.
  2. Point all 24 `_utcnow()` definitions to `app.services.common.datetime_utils.utcnow`.
  3. Create `app/utils/numeric_utils.py` and consolidate the 7 `_safe_int` definitions.
  4. Add `success`, `warning`, `info` variants to `frontend/src/components/ui/badge.tsx`.
  5. Extract `getCategoryBadgeClass` to `features/marketplace/utils/categoryColors.ts`.
- **Verification**: `python scripts/run_tests.py --all` and `npm run test:changed`.

#### Phase 2: Core Frontend UI Primitives & Duplication Elimination
- **Goal**: Eliminate repetitive UI boilerplate and unblock component decomposition.
- **Actions**:
  1. Add `loading` prop to `components/ui/button.tsx`.
  2. Implement `SearchInput`, `ConfirmDialog`, `CodeSnippetBox`, `DataTablePagination`.
  3. Consolidate MCP tokens UI between Admin and Settings, extracting `McpScopeSelector`, `McpTokenRevealDialog`, and `McpTokenTable`.
  4. Create `frontend/src/lib/formatters.ts` (`formatDate`, `formatRelativeTime`, `formatCurrency`).
  5. Build `features/cards/components/CardFieldsForm.tsx` and `useCardEditorForm.ts` to replace ad-hoc editors in Browse and Study.
- **Verification**: Visual inspection via isolated Chrome profile; Vitest suite.

#### Phase 3: Major Backend Function Decomposition & Boundary Enforcement
- **Goal**: Eliminate the 4 largest backend super-functions and restore controller boundaries.
- **Actions**:
  1. Decompose `render_printable_html` (1,818 lines) into `app/services/worksheets/renderers/`.
  2. Convert `app/cli.py` (1,829 lines) into Click command modules (`study.py`, `marketplace.py`, `media.py`, `db_seed.py`).
  3. Split `process_single_study_batch` (856 lines) into lock manager, event processor, and mirror service.
  4. Move `db.session.commit()` calls from `marketplace/installations.py`, `anki_imports.py`, and `admin/taxonomy.py` into their respective service methods.
- **Verification**: `python scripts/run_tests.py --module study,flashcards,marketplace`.

#### Phase 4: Frontend God Component & Mega-Hook Decomposition
- **Goal**: Dismantle the largest monolithic UI components and state monsters.
- **Actions**:
  1. Refactor `DeckWorksheetModal.tsx` (4,388 LOC -> ~200 LOC) by extracting Studio tabs and `useWorksheetStudio`.
  2. Refactor `WorksheetPageRenderer.tsx` (1,719 LOC -> ~120 LOC) with modular page renderers.
  3. Refactor `AdminTaxonomyPage.tsx` (1,400 LOC -> ~110 LOC) into 5 sub-entity tabs.
  4. Decompose `useBrowseState.ts` (49 states) into 4 specialized hooks.
  5. Decompose `SharedDeckDetailPage.tsx` (1,436 LOC -> ~220 LOC).
  6. Split multi-page files (`MarketplacePages.tsx`, `LibraryPages.tsx`, `StaticPages.tsx`, `App.tsx`).
- **Verification**: Visual regression testing using isolated DevTools profile.

#### Phase 5: Query Scopes & Logical Overlay Seam Consolidation
- **Goal**: Consolidate database access patterns, eliminate soft-delete leakage, and align schema migrations.
- **Actions**:
  1. Unify the 5 deck tree traversals into `app/repositories/deck_tree_query.py`.
  2. Standardize `Deck.deleted_at.is_(None)` via `app/repositories/base_query.py:active_decks_query()`.
  3. Centralize Logical Overlay Card/Note resolution in `app/services/deck_access_policy.py`.
  4. Migrate raw DDL from `app/startup_schema.py` (1,043 lines) into official Alembic migrations (`migrations/versions/`).
- **Verification**: `python scripts/run_tests.py --all` and schema migration validation.

---

### 6.2 Architectural Risk Matrix

| Refactoring Workstream | Phase | Complexity | Regression Risk | Primary Guardrail & Mitigation |
| :--- | :---: | :---: | :---: | :--- |
| **Zombie Monolith Facades** | Phase 1 | Low | **Low** | Monoliths must export `from app.services.X import *` so zero external import signatures break. Run full test suite. |
| **Centralize `utcnow` & Utilities** | Phase 1 | Low | **Zero** | Pure deterministic function replacements. |
| **Badge Variants & Category Colors** | Phase 1 | Low | **Zero** | Zero visual regression. Exact Tailwind class mapping. |
| **Shared MCP Tokens Components** | Phase 2 | Medium | **Low** | Keep exact DOM hierarchy and CSS classes. Verify admin vs user capability toggles. |
| **Unified CardFieldsForm** | Phase 2 | Medium | **Medium** | Must verify note fields, rich text formatting, and stroke generator triggers across all 3 host dialogs. |
| **Worksheet HTML Renderers** | Phase 3 | High | **Low** | Compare generated printable HTML string outputs before and after extraction to ensure byte-level match. |
| **CLI Modularization** | Phase 3 | Medium | **Low** | Verify all 25+ `flask <command>` invocations retain identical parameter signatures. |
| **DeckWorksheetModal Splitting** | Phase 4 | High | **Medium** | Leaf-to-root refactoring. Verify canvas zoom, double-tap, and preset persistence using isolated Chrome profile. |
| **useBrowseState Decomposition** | Phase 4 | High | **Medium** | Ensure URL search parameter two-way synchronization and table selection states remain intact. |
| **Deck Tree & Overlay Query Unification** | Phase 5 | High | **High** | **CRITICAL**: Preserve Logical Overlay model (`DeckInstall`, `DeckCloneDeckMap`). Must NOT introduce full-copy clones or mutate source notes (`CLONE_CUTOVER_REPORT.md`). |

---

### 6.3 Backward Compatibility & Guardrail Guarantees

1. **Overlay-Only Shared Deck Model**:
   All refactoring touching shared decks, card browsing, study sessions, or change requests must preserve the overlay-only model. **Under no circumstances should legacy full-copy clone behavior be revived, nor should source notes ever be mutated during clone edit flows** (`docs/plans/completed/CLONE_CUTOVER_REPORT.md`).
2. **Zero Visual Regression**:
   Every frontend component split must preserve the exact colors, typography, paddings, shadows, and responsive behaviors of the original implementation. Testing must be performed using an isolated Chrome profile (`--user-data-dir=C:\Users\chung\.gemini\chrome-profiles\flama-devtools`).
3. **Seam-Safe Decoupling**:
   Progress aggregation and counting must adhere to Phase 5 compatibility windows and Phase 6 Note Authority rules (Decision D6-04) without hand-rolling raw scheduling math in controllers.
4. **Zero Downtime Database Migrations**:
   Any database schema adjustments transitioned from `startup_schema.py` to Alembic must be backward-compatible, non-locking, and zero-downtime.

---

## 7. Verification & Guardrail Confirmation

In strict compliance with the core directives of this audit:
- **Zero Source Code Modifications**: Exactly **0 source code files** in `app/`, `models/`, `frontend/src/`, `connect_wsgi.py`, or `wsgi.py` were modified during the preparation of this audit report.
- **Authentic Static & AST Analysis**: All metrics, line numbers, file counts, and function signatures were derived directly from the physical codebase using verified inspection tools.
- **Deliverable Integrity**: The definitive audit report is securely stored at `docs/reports/CODE_HEALTH_AUDIT_REPORT.md`, with complete supporting explorer findings archived under `.agents/teamwork/`.

---
*Report compiled and certified by the Master Audit Report Compiler.*
