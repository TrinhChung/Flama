# Flama Frontend Technical Debt Catalog

- **Domain**: Frontend Single Page Application (`frontend/src/`)
- **Last Audited**: 2026-10-15
- **Status**: Active Technical Debt Registry
- **Master Audit Report**: [Comprehensive Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md)

---

## 1. Executive Summary

While the Flama frontend compiles with **0 TypeScript errors** across **174 Vitest test files (1,424 tests total)** (with 173 passing cleanly and a known DOM mock state pollution issue in concurrent runs for `TemplateDetailPage.test.tsx` which passes 16/16 in isolation), rapid feature expansion has created concentrated technical debt hotspots. This catalog identifies and ranks all architectural bottlenecks, gargantuan components, mega-hooks, and legacy facades across the codebase. For cross-domain technical debt analysis and discrepancies catalog, see the master [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md).

---

## 2. Gargantuan Components (>800 Lines of Code)

The repository standard specifies that UI components should remain between **150 and 400 LOC**. Ten components significantly exceed this threshold:

| Component File Path | LOC | Size (KB) | Core Architectural Issues | Decomposition & Remediation Plan | Priority |
|---|---|---|---|---|---|
| `frontend/src/features/worksheets/components/studio/StudioLayoutTab.tsx` | **2,497** | **157.8 KB** | **Massive God Component**: Combines interactive SVG canvas drawing, drag-and-drop cell configuration, paper margin math, printable PDF layout settings, and stateful toolbars. | 1. Extract canvas rendering into `StudioCanvasPreview.tsx`.<br>2. Extract cell configuration into `StudioCellEditor.tsx`.<br>3. Extract print setup into `StudioPrintSettings.tsx`.<br>4. Extract state machine into custom hook `useStudioLayoutState.ts`. | **P1 (Highest)** |
| `frontend/src/features/worksheets/components/WorksheetPageRenderer.tsx` | **1,753** | **84.5 KB** | **Monolithic Drawing Engine**: Procedural SVG generation for 8 different Japanese practice sheet types (Kana, Kanji strokes, vocabulary grids). | Decompose into format-specific sub-renderers: `KanaGridRenderer.tsx`, `KanjiStrokeRenderer.tsx`, `VocabularyListRenderer.tsx`. | **P1** |
| `frontend/src/features/admin/pages/AdminPaymentsPage.tsx` | **1,394** | **62.8 KB** | Monolithic page file mixing transaction data tables, refund confirmation dialogs, payOS webhook logs, and filter states. | Extract `PaymentTransactionsTable.tsx`, `RefundDialog.tsx`, and state hook `usePaymentManagement.ts`. | **P2** |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | **1,399** | **61.2 KB** | Mixes hierarchical taxonomy tree rendering, category editing modal, and inline validation. | Extract `TaxonomyTree.tsx`, `CategoryEditModal.tsx`, and `useTaxonomyTree.ts`. | **P2** |
| `frontend/src/features/settings/components/McpOAuthTab.tsx` | **1,109** | **55.1 KB** | Combines OAuth client registration, token generation, cryptographic secret reveal modals, and scope matrices. | Extract `OAuthClientList.tsx`, `ScopeSelectorMatrix.tsx`, `TokenSecretModal.tsx`. | **P2** |
| `frontend/src/features/admin/pages/AdminFeesPage.tsx` | **1,100** | **46.8 KB** | Merges fee calculation formulas, tier overrides, and fee history tables into a single page file. | Split into `FeeScheduleTable.tsx`, `FeeRuleForm.tsx`, and `FeeHistoryLog.tsx`. | **P2** |
| `frontend/src/features/worksheets/components/DeckWorksheetModal.tsx` | **930** | **41.6 KB** | Modal wizard managing step progression, note type inspection, preset persistence, and print triggers. | Extract `WorksheetStepWizard.tsx` and `WorksheetPresetSelector.tsx`. | **P3** |
| `frontend/src/features/admin/pages/AdminUsersPage.tsx` | **886** | **35.0 KB** | Monolithic user table with inline role switches, ban actions, and password reset dialogs. | Extract `UserTable.tsx`, `UserRoleModal.tsx`, and `UserFiltersBar.tsx`. | **P3** |
| `frontend/src/pages/LandingPage.tsx` | **812** | **34.5 KB** | Combines 3D card tilt animation, feature showcase grids, user testimonials, pricing tables, and FAQ accordion. | Split into section components: `LandingHero.tsx`, `LandingFeatures.tsx`, `LandingTestimonials.tsx`, `LandingPricing.tsx`. | **P3** |
| `frontend/src/features/admin/pages/AdminPermissionsPage.tsx` | **823** | **32.6 KB** | Monolithic role permission matrix editor with granular checkbox toggles and unsaved-changes state. | Extract `PermissionMatrixTable.tsx` and `usePermissionMatrix.ts`. | **P3** |

---

## 3. Mega-Hooks (>1,000 Lines of Code)

Three custom hooks encapsulate too many disparate concerns, creating cognitive overhead and potential re-render cascades:

### 3.1 `useStudySession.ts` (`frontend/src/features/study/hooks/useStudySession.ts`)
- **Lines of Code**: **1,482 LOC**
- **State Complexity**: Manages 30+ separate `useState` and `useRef` handles: session timers, card queue cursor, answer reveal status, audio trigger flags, keyboard shortcut bindings, quick edit dialogs, undo stacks, and offline IndexedDB sync.
- **Risks**: Any timer tick or audio status update causes re-evaluations across the entire study view.
- **Remediation Plan**: Decompose into focused sub-hooks:
  1. `useStudyKeyboardShortcuts.ts`: Space to reveal, 1-4 for rating, Z for undo.
  2. `useStudySessionTimer.ts`: Active review duration and idle detection.
  3. `useStudyReviewActions.ts`: Next card, submit answer, and rating calculations.
  4. `useStudyAudioPlayback.ts`: PostMessage listeners and host audio coordination.

### 3.2 `useBrowseState.ts` (`frontend/src/features/browse/hooks/useBrowseState.ts`)
- **Lines of Code**: **1,131 LOC**
- **State Complexity**: Manages 40+ states including deck tree selection, card table multi-selection, search debounce, tag filters, sorting criteria, and batch edit modals.
- **Risks**: Typing in the search input triggers recalculation of the entire deck tree selection and table state.
- **Remediation Plan**: Split into decoupled hooks:
  1. `useBrowseFilters.ts`: Search queries, tags, deck filters, and due status.
  2. `useBrowseTableSelection.ts`: Selected row IDs and select-all state.
  3. `useBrowseBatchActions.ts`: Batch deck repositioning, tag additions, and card suspensions.

### 3.3 `useLocalAudioEngine.ts` (`frontend/src/features/audio/hooks/useLocalAudioEngine.ts`)
- **Lines of Code**: **1,118 LOC**
- **State Complexity**: Integrates local service health polling, pairing challenges, engine download progress, voice catalog querying, and audio blob caching.
- **Remediation Plan**: Decompose into:
  1. `useFlamaAudioPairing.ts`: Pairing challenge, status polling, and bearer token storage.
  2. `useAudioEngineStatus.ts`: Engine installation, process launch, and healthchecks.
  3. `useVoiceCatalog.ts`: Speaker querying and voice preview playback.

---

## 4. Legacy API Facade (`frontend/src/app/api.ts`)

- **Current State**: 470 LOC file serving as a catch-all aggregator of legacy API calls across authentication, study, decks, browse, and dashboard.
- **Architectural Violation**: FSD prohibits monolithic app-level API files. Features and entities must own their private API modules.
- **Remediation**:
  - `card-template` and `audio` slices already use dedicated API clients (`cardTemplateApi.ts`, `flamaAudioClient.ts`).
  - Migrate remaining functions into slice-local modules:
    - Study APIs -> `features/study/api/`
    - Browse APIs -> `features/browse/api/`
    - Deck APIs -> `features/dashboard/api/` or `entities/deck/api/`
  - Deprecate `app/api.ts` once all callers have been redirected.

---

## 5. Unlocalized Admin Pages (`frontend/src/features/admin/`)

- **Context**: During previous internationalization sprints, the `features/admin/` module was intentionally excluded from i18n extraction to prevent accidental regressions on production operations.
- **Current State**: All 11 admin pages contain hardcoded Vietnamese text directly in JSX.
- **Remediation**:
  1. Create `admin.json` namespace for both `vi` and `en` locales.
  2. Extract all button labels, table headers, status badges, and error messages to `useTranslation('admin')`.
  3. Maintain 100% leaf-key parity in `i18n.stress.test.tsx`.

---

## 6. Missing FSD Layers & Pending Entity Extractions

1. **Entity Extractions Needed**:
   - `entities/deck`: Deck tree types and basic deck fetching are currently duplicated across `features/dashboard` and `features/browse`.
   - `entities/note`: Note field structures and tag types are shared implicitly.
   - `entities/user`: User profile DTOs and role checks are split between `shared/api/bootstrap.ts` and `features/profile`.
2. **Missing `widgets/` Layer**:
   - Composite multi-feature components currently reside in root components, layouts, or feature folders (e.g. `frontend/src/components/app-sidebar.tsx`, header navigation embedded directly inside `frontend/src/layouts/AppLayout.tsx`, and browse workspace logic embedded in `frontend/src/features/browse/pages/BrowsePage.tsx`), blurring the boundary between atomic features and composite view blocks.
