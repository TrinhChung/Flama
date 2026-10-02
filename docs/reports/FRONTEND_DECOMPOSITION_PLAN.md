# Flama Frontend Architecture Decomposition & Optimization Master Plan

**Document ID**: `FLAMA-ARCH-2026-FE-001`  
**Target Repository**: Flama (`d:\Project\nihongo`) — Subsystem: `frontend/src/`  
**Architectural Baseline**: React 19 SPA, Vite, TypeScript, TailwindCSS v4 (@theme inline OKLCH), Radix UI  
**Target Architectural Standard**: Feature-Sliced Design (FSD) & Headless Hooks (<8 States Rule)  
**Safety & Compliance Mode**: Zero Visual Regression, 100% Behavioral Preservation, Zero Source Code Modifications during Planning  
**Date**: 2026-10-01  
**Status**: Authoritative Master Plan / Ready for Implementation  

---

## Table of Contents
1. [Executive Summary & Architecture Vision](#1-executive-summary--architecture-vision)
2. [R1: Frontend Architecture Audit & Categorization](#2-r1-frontend-architecture-audit--categorization)
   - 2.1 Current Directory Layout vs Feature-Sliced Design (FSD)
   - 2.2 God Components Ranking (Files >= 300 LOC)
   - 2.3 Mega-Hooks & State Bloat Inventory (>= 10 States)
   - 2.4 Repetitive Inline JSX/CSS Patterns Lacking UI Primitives
   - 2.5 Authoritative OKLCH Design Tokens Contract (`index.css`)
   - 2.6 Target FSD Migration Blueprint
3. [R2: Reusable UI Primitives Technical Design (Leaf-to-Root)](#3-r2-reusable-ui-primitives-technical-design-leaf-to-root)
   - 3.1 `SearchInput`
   - 3.2 `ConfirmDialog`
   - 3.3 `StatusPill`
   - 3.4 `CodeSnippetBox`
   - 3.5 `FilterPillGroup`
   - 3.6 `ImageUploadDropzone`
   - 3.7 `SplitPane`
   - 3.8 `CardFieldsForm`
4. [R3: Headless Custom Hooks Architecture](#4-r3-headless-custom-hooks-architecture)
   - 4.1 State Extraction Methodology (<8 States Rule)
   - 4.2 Specifications for 14 Headless Custom Hooks
     - Hook 1: `useBrowseFilters`
     - Hook 2: `useBrowseSelection`
     - Hook 3: `useBrowseCardOperations`
     - Hook 4: `useCardDetailEditor`
     - Hook 5: `useWorksheetStudio`
     - Hook 6: `useWorksheetConfig`
     - Hook 7: `useWorksheetPreview`
     - Hook 8: `useAudioPlayer`
     - Hook 9: `useMcpTokens`
     - Hook 10: `useTaxonomyManager`
     - Hook 11: `useStudySession`
     - Hook 12: `useStudyInteraction`
     - Hook 13: `useMarketplaceSearch`
     - Hook 14: `useDeckExportImport`
5. [R4: Deep Decomposition of the 4 Key God Components](#5-r4-deep-decomposition-of-the-4-key-god-components)
   - 5.1 Deep Dive: `DeckWorksheetModal.tsx` (4,388 LOC)
   - 5.2 Deep Dive: `AdminTaxonomyPage.tsx` (1,400 LOC, 46 States)
   - 5.3 Deep Dive: `AdminMcpTokensPage.tsx` & `McpTokensTab.tsx` (2,586 LOC Combined)
   - 5.4 Deep Dive: `useBrowseState.ts` (1,053 LOC, 49 States, 102 Return Properties)
6. [R5: Zero Visual Regression & Logic Preservation Standards](#6-r5-zero-visual-regression--logic-preservation-standards)
   - 6.1 Layout & Box Model Invariance Rules
   - 6.2 Strict Ban on Extraneous Wrapper `<div>`s (Fragments, `asChild`, `contents`)
   - 6.3 Radix UI Context & Accessibility Boundaries
   - 6.4 Chrome DevTools Isolated Profile Verification Procedure
   - 6.5 10-Point Actionable Verification Checklist
7. [Consolidated Metrics & Before/After LOC Impact Table](#7-consolidated-metrics--beforeafter-loc-impact-table)
8. [Phased Implementation Roadmap & Rollout Plan](#8-phased-implementation-roadmap--rollout-plan)

---

# 1. Executive Summary & Architecture Vision

### 1.1 The Challenge: Monolithic Sprawl in a Modern Stack
The Flama frontend is an ambitious, high-performance Japanese language learning Single-Page Application (SPA) powered by React 19, Vite, TailwindCSS v4, and Radix UI. Over successive feature additions (Flashcard V2, Yomitan AnkiConnect bridge, Flama Audio TTS companions, and payOS marketplace commerce), core presentation files accumulated severe technical debt:

- **Extreme Monoliths**: 112 files exceed 300 LOC. The largest single component, `DeckWorksheetModal.tsx`, measures **4,388 LOC**, bundling modal chrome, responsive navigation, wizard routing, 8 specialized layout generators, live print rendering, and SVG canvas math.
- **Cascading Re-render Bottlenecks**: 23 components and hooks suffer from extreme state bloat (10 to 49 separate `useState` declarations). Root-level states cause catastrophic re-renders across entire viewports upon single keystrokes (e.g., `AdminTaxonomyPage.tsx` with 46 states).
- **Entangled Mega-Hooks**: `useBrowseState.ts` (1,053 LOC) bundles **49 distinct states** and returns **102 properties and functions**, amalgamating search filtering, multi-card selection, keyboard shortcuts, inline card editing, batch deletions, note moves, and 24 VoiceVox/Kokoro TTS audio states into a single monolithic hook.
- **Widespread Code Duplication**: More than **1,800 lines of identical UI and mutation code** are duplicated between `AdminMcpTokensPage.tsx` and `McpTokensTab.tsx`. Core visual patterns (search inputs with absolute icons, confirmation dialogs, status pills, and copy snippets) are manually re-implemented with ad-hoc Tailwind classes across dozens of files.
- **Architectural Gaps**: The project lacks an `entities/` layer in its Feature-Sliced Design structure, forcing domain cards and entity representations to leak into feature folders or page routers.

### 1.2 Target Architectural Vision: Feature-Sliced Design (FSD)
This master plan defines a bottom-up, leaf-to-root architectural migration to **Feature-Sliced Design (FSD)**:
1. **`shared/ui` (Layer 0)**: 8 reusable, accessible UI primitives with zero business logic, governed by `class-variance-authority` (CVA) and project OKLCH tokens.
2. **`entities` (Layer 1)**: Pure domain entities (`card`, `deck`, `note`, `taxonomy`, `token`) housing presentation cards, badges, and read-only hooks.
3. **`features` (Layer 2)**: Focused user interactions and business flows (`browse-filters`, `worksheet-studio`, `mcp-tokens`, `study-session`), strictly limited to `< 300 LOC` per file and powered by pure headless custom hooks adhering to the **`<8 States Rule`**.
4. **`widgets` (Layer 3)**: High-level composite blocks (`BrowseWorkspace`, `WorksheetStudio`, `DiffViewer`) assembling features and entities.
5. **`pages` (Layer 4)**: Thin route orchestrators (`< 150 LOC`) responsible solely for parameter parsing, title metadata, and layout assembly.

### 1.3 High-Level Impact Summary
- **Total LOC Elimination Across Key Monoliths**: Net reduction of **~4,104 lines of code (-43.5%)** across the 4 key target subsystems.
- **Duplicated Code Extinction**: Permanent elimination of **~1,800 duplicate lines** between MCP token views.
- **Zero Visual Regression**: 100% preservation of margin/padding spacing, brand OKLCH colors, font metrics, Radix UI accessibility, and interaction states.
- **Performance Optimization**: Complete elimination of root-hoisted re-render cascades, reduction in React component tree depth, and enforcement of `CLS = 0.0000` via Chrome DevTools profiling.

---

# 2. R1: Frontend Architecture Audit & Categorization

## 2.1 Current Directory Layout vs Feature-Sliced Design (FSD)

### Current Directory Structure
```
frontend/src/
├── app/                  # Low-level API client (api.ts) & config
├── assets/               # Brand SVGs, mascot, icons
├── components/
│   ├── ui/               # 27 shadcn/radix primitives (button, badge, dialog, etc.)
│   └── (shells)          # AppLayout shells: app-sidebar, nav-main, nav-user, ambient-background, site-footer
├── config/               # Navigation items & static routes
├── data/                 # Legal document data, static tables
├── features/             # 21 domain folders (admin, audio, auth, browse, dashboard,
│                         #   deck-collaboration, guide, import, library, marketplace,
│                         #   note-types, oauth, onboarding, orders, profile, settings,
│                         #   statistics, study, support, wallet, worksheets)
├── hooks/                # Global utilities (use-mobile, use-clipboard, useSpotlightTour)
├── layouts/              # AppLayout.tsx
├── lib/                  # Utilities (ankiSyncEngine, utils.ts)
├── pages/                # LandingPage.tsx, StaticPages.tsx
└── shared/               # Partially formed shared utilities
    ├── api/              # backendAvailability, noteMedia, client
    ├── components/       # Brand, Icons, Page, PageState, SpotlightTour, StudyHeatmap
    └── types/            # api.ts, heatmap.ts
```

### Identified FSD Deficiencies
1. **Absence of Domain Entities (`entities/`)**: Domain concepts (Decks, Notes, Cards, Taxonomy Categories, Tokens) lack a dedicated layer. `DeckCard` lives in `features/marketplace/`, `DeckRow` lives in `features/dashboard/`, and `BrowseCardEditor` lives in `features/browse/`. There is no single source of truth for entity representations.
2. **Missing UI Primitives in Design System**: While basic buttons and dialogs exist in `components/ui/`, composite interactive controls (`SearchInput`, `ConfirmDialog`, `CodeSnippetBox`, `FilterPillGroup`, `SplitPane`, `CardFieldsForm`) are missing. Developers repeatedly re-implement them inline with hardcoded CSS.
3. **Leaky Page Boundaries**: Files in `pages/` (such as `AdminTaxonomyPage.tsx` or `AdminPaymentsPage.tsx`) contain over 1,400 lines of data fetching, state declarations, form validation, and inline JSX tables instead of delegating to features and widgets.

---

## 2.2 God Components Ranking (Files >= 300 LOC)

A comprehensive scan of `frontend/src/` identified **112 files exceeding 300 LOC**. The Top 35 monolithic files are ranked below:

| Rank | LOC | Component / File | Primary Violation & Architectural Cause |
|:---:|:---:|:---|:---|
| **1** | **4,388** | `features/worksheets/components/DeckWorksheetModal.tsx` | **Extreme Monolith**: Merges 4 studio tabs, live SVG/DOM preview, font metrics, print stylesheets, paper presets, table cell layout math, and 21 state variables in one single file. |
| **2** | **1,719** | `features/worksheets/components/WorksheetPageRenderer.tsx` | **SVG/Canvas God Component**: Renders every worksheet type (kanji grids, vocabulary tables, matching columns, furigana lines) in raw inline JSX without sub-renderers. |
| **3** | **1,436** | `features/marketplace/pages/SharedDeckDetailPage.tsx` | **Page Bloat**: Deck banner, clone-action dialog, version changelog, rating system, review list, comment editor, and install state all in one component. |
| **4** | **1,405** | `features/admin/pages/AdminMcpTokensPage.tsx` | **Admin Monolith**: Token table, filter bar, create token modal, revoke confirm modal, secret token reveal dialog. Duplicates 80% of `McpTokensTab.tsx`. |
| **5** | **1,400** | `features/admin/pages/AdminTaxonomyPage.tsx` | **Multi-Entity Monolith (46 states)**: Manages 5 completely different taxonomy domains (Categories, JLPT, CEFR, Tags, Topics) with 5 embedded CRUD modals in 1 file. |
| **6** | **1,395** | `features/admin/pages/AdminPaymentsPage.tsx` | **Multi-Tab Monolith**: Orders list, payOS transaction matching, manual verification dialogs, fee calculations, and pagination. |
| **7** | **1,181** | `features/settings/components/McpTokensTab.tsx` | **Duplicate Monolith**: Client user counterpart of `AdminMcpTokensPage.tsx`. Duplicates token CRUD forms, secret copying, and confirmation modals. |
| **8** | **1,160** | `features/settings/components/McpOAuthTab.tsx` | **OAuth God Component**: Client registrations, consent scope configurations, client secret copy dialog, and token revocation tables. |
| **9** | **1,158** | `features/marketplace/pages/MarketplacePublishNoteTypePage.tsx` | **Publishing Wizard**: Note type field mappings, CSS sandbox preview, pricing tiers, and licensing agreement in one file. |
| **10** | **1,152** | `features/marketplace/pages/MarketplacePages.tsx` | **Marketplace Portal**: Banner, category pill selector, search bar, sort dropdown, deck grid, and pagination. |
| **11** | **1,101** | `features/admin/pages/AdminFeesPage.tsx` | **Admin Fee Monolith**: Platform commission tiers, fee recalculation dialogs, transaction history table. |
| **12** | **1,080** | `features/audio/hooks/useLocalAudioEngine.ts` | **Mega-Hook Engine**: VoiceVox/Kokoro connection states, voice profiles, synthesize queues, audio playback buffers. |
| **13** | **1,053** | `features/browse/hooks/useBrowseState.ts` | **Mega-Hook Hotspot (49 states)**: Manages active deck, search query, tag filters, sorting, pagination, card selection, active card detail, draft field edits, 4 modal open states, audio player ref, mobile tabs. |
| **14** | **966** | `features/support/pages/FeedbackPage.tsx` | **Feedback Monolith**: Drag-and-drop attachment dropzone, screenshot pasting, ticket categorization, and feedback history table. |
| **15** | **942** | `features/library/pages/LibraryPages.tsx` | **Library Portal**: Installed shared decks, personal created decks, filter tabs, sort dropdowns, and card counts. |
| **16** | **916** | `features/import/components/AnkiSyncTab.tsx` | **Sync Engine Monolith (25 states)**: AnkiConnect bridge setup, deck tree selection, note type matching, progress bars, and log viewer. |
| **17** | **905** | `features/deck-collaboration/pages/InstalledDeckUpdatePage.tsx` | **Collaboration Diff Monolith**: 3-way merge inspector, field diff view, rollback triggers, and conflict resolution modal. |
| **18** | **889** | `pages/LandingPage.tsx` | **Landing Page Bloat**: Hero section, 3D card flip animation, sponsor track marquee, feature comparisons, and FAQ accordion. |
| **19** | **887** | `features/admin/pages/AdminUsersPage.tsx` | **Admin User Monolith**: User data table, role dropdowns, ban confirmation dialog, password reset dialog. |
| **20** | **878** | `features/import/components/AnkiNoteTypeSyncTab.tsx` | **Template Sync Monolith**: Field mapping tables, mustache syntax preview, CSS editor with live preview. |
| **21** | **824** | `features/admin/pages/AdminPermissionsPage.tsx` | **RBAC Matrix Monolith**: Complex permission checkboxes table, role creation modal, audit log. |
| **22** | **814** | `features/support/pages/SupportPage.tsx` | **Support Portal**: Knowledge base categories, search input, article viewer, ticket creation trigger. |
| **23** | **787** | `features/marketplace/pages/SharedNoteTypeDetailPage.tsx` | **Detail Page**: Template inspector, field definitions table, clone note type action. |
| **24** | **773** | `features/browse/components/BrowseStrokeModal.tsx` | **Stroke Diagram Monolith**: KanjiVG SVG parser, stroke order animation canvas, batch export options. |
| **25** | **702** | `features/admin/pages/AdminImageLibraryPage.tsx` | **Asset Library Monolith**: Asset grid, image upload dropzone, URL copy buttons, delete confirm dialogs. |
| **26** | **679** | `features/import/hooks/useFileImportWizard.ts` | **Import Wizard Hook (25 states)**: File reference, parsed rows, delimiter, hasHeaders, field mappings array, target deck ID. |
| **27** | **662** | `features/profile/components/ProfileEditDialog.tsx` | **Profile Monolith**: Profile form, avatar dropzone with canvas cropping, password update, session revocation. |
| **28** | **644** | `features/browse/components/BrowseCardEditor.tsx` | **Card Editor Monolith**: Dynamic field form, custom DOM resize drag handle, tag manager, media previews. |
| **29** | **641** | `features/study/components/EditCardModal.tsx` | **Modal Editor**: Dynamic field editing, markdown preview switcher, media file inputs. Duplicates `BrowseCardEditor`. |
| **30** | **627** | `features/marketplace/components/keys/DeckAccessKeysManager.tsx` | **Key Manager**: Key generation form, secret token copy snippet, revoke confirmation dialog. |
| **31** | **627** | `features/marketplace/pages/MarketplacePublishDeckPage.tsx` | **Wizard Monolith (29 states)**: 4-step wizard for publishing decks to marketplace. |
| **32** | **609** | `features/browse/pages/BrowsePage.tsx` | **Browse Root**: 3-pane layout, mobile tab switcher, toolbar, and 5 separate modal attachments. |
| **33** | **579** | `features/study/components/StudyQuickEditDialog.tsx` | **Quick Editor**: In-study fast card editor with dynamic fields, media resolvers, and save mutation. |
| **34** | **574** | `features/audio/components/DeckAudioRuleCard.tsx` | **Audio Rule Monolith**: TTS voice rule builder, field selectors, voice preview player. |
| **35** | **559** | `features/note-types/pages/NoteTypeFieldsPage.tsx` | **Fields Builder**: Drag-and-drop field reordering, field type options, delete dialog. |

---

## 2.3 Mega-Hooks & State Bloat Inventory (>= 10 States)

The audit discovered **23 components and custom hooks maintaining 10 or more independent states**:

| Rank | States | LOC | File | Primary Responsibility & Bloat Analysis |
|:---:|:---:|:---:|:---|:---|
| **1** | **49** | 1,053 | `features/browse/hooks/useBrowseState.ts` | **Mega-Hook Hotspot**: Manages active deck, search query, tag filters, sorting, pagination, card selection, active card detail, draft field edits, 4 modal open states, audio player ref, mobile tabs. |
| **2** | **46** | 1,400 | `features/admin/pages/AdminTaxonomyPage.tsx` | **State Proliferation**: 5 sets of CRUD form states (name, code, description, sort_order) + 5 modal open states + search filter + delete targets. |
| **3** | **29** | 627 | `features/marketplace/pages/MarketplacePublishDeckPage.tsx` | **Wizard State**: Wizard step index, selected deck, price model, currency, sample card count, terms check, upload progress. |
| **4** | **26** | 1,405 | `features/admin/pages/AdminMcpTokensPage.tsx` | **Token Admin State**: Search query, status filter, page index, token name, expiry date, scope checkboxes, delete ID, reveal token secret. |
| **5** | **25** | 916 | `features/import/components/AnkiSyncTab.tsx` | **Sync Workflow State**: Host URL, API key, connection test result, selected deck IDs, tag overrides, conflict mode, progress, error logs. |
| **6** | **25** | 679 | `features/import/hooks/useFileImportWizard.ts` | **Import Wizard Hook**: File reference, parsed rows, delimiter, hasHeaders, field mappings array, target deck ID, duplicate policy, batch counter. |
| **7** | **22** | 1,080 | `features/audio/hooks/useLocalAudioEngine.ts` | **Audio Engine State**: VoiceVox engine connection, Kokoro engine connection, available speaker list, active voice ID, pitch, speed, queue status. |
| **8** | **21** | 4,388 | `features/worksheets/components/DeckWorksheetModal.tsx` | **Studio State**: Wizard step, selected template, field mapping, paper size, orientation, font family, font size, grid columns, print watermark, zoom level. |
| **9** | **19** | 1,158 | `features/marketplace/pages/MarketplacePublishNoteTypePage.tsx` | **Note Type Publish State**: Note type ID, title, description, category ID, price, tags list, sample card preview fields. |
| **10** | **17** | 1,395 | `features/admin/pages/AdminPaymentsPage.tsx` | **Payment Audit State**: Orders search, orders status filter, transactions status filter, manual verification modal, active order payload. |
| **11** | **16** | 878 | `features/import/components/AnkiNoteTypeSyncTab.tsx` | **Note Type Sync State**: Note type dropdown, card templates list, field definitions map, front/back/css preview tabs, sync direction. |
| **12** | **16** | 416 | `features/settings/hooks/useMcpTokenCRUD.ts` | **Token CRUD Hook**: Form values, generated secret, copy notification timer, revoke target, error validation states. |
| **13** | **15** | 702 | `features/admin/pages/AdminImageLibraryPage.tsx` | **Asset Admin State**: Selected asset, uploaded file, description, source URL, tag search, category filter, active delete ID. |
| **14** | **14** | 662 | `features/profile/components/ProfileEditDialog.tsx` | **Profile Form State**: Display name, email, bio, current password, new password, confirm password, avatar file, avatar preview URL. |

---

## 2.4 Repetitive Inline JSX/CSS Patterns Lacking UI Primitives

1. **Ad-hoc Search Input Blocks (>25 occurrences)**:
   ```tsx
   <div className="relative">
     <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
     <Input className="pl-9" placeholder="Tìm..." value={q} onChange={...} />
   </div>
   ```
   Repeated across `AdminUsersPage`, `AdminTicketsPage`, `AdminMcpTokensPage`, `AdminFeesPage`, `AdminImageLibraryPage`, `AdminPermissionsPage`, `AdminPaymentsPage`, `AdminTaxonomyPage`, `LibraryPages`, `MarketplacePages`, `SharedDeckDetailPage`, `AnkiSyncTab`, `BrowseDeckSidebar`, `BrowseToolbar`, and `DiffWorkspace`. None provide built-in clearing (`Escape`), debouncing, or loading spinners.

2. **Hand-Rolled Confirmation Modals (>15 occurrences)**:
   Every time an item (token, taxonomy tag, user, deck, image asset) is deleted or revoked, developers write 30–50 lines of `<Dialog>`, `<DialogContent>`, `<DialogHeader>`, `<DialogFooter>`, cancel button, and destructive submit button with local `loading` state.

3. **Inconsistent Status Badges (>250 occurrences)**:
   Status indicators use arbitrary combinations of Tailwind classes such as `bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30`, `bg-amber-500/10 text-amber-700`, `bg-sky-500/15`, `bg-slate-900 text-white`, bypassing the project's semantic tokens and creating visual noise.

4. **Duplicated Copy-to-Clipboard Snippets (>18 occurrences)**:
   Displaying secret tokens, API keys, or Yomitan markers repeatedly uses:
   ```tsx
   {copied ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
   ```
   accompanied by redundant `const [copied, setCopied] = useState(false)` and `setTimeout` timers.

5. **Segmented Filter Button Groups (>12 occurrences)**:
   Status filters (All | Active | Inactive | Pending) are manually mapped into `<button>` elements with hardcoded slate borders and background styles (`AdminPaymentsPage`, `DiffWorkspace`, `WalletTransactionsTable`, `WorksheetTemplateSelectStep`).

6. **Image & File Drag-and-Drop Zones (>8 occurrences)**:
   `FeedbackPage`, `AdminImageLibraryPage`, `AvatarUploadModal`, `ImportFileStep`, and `EditCardModal` each implement their own `onDragOver`, `onDragLeave`, `onDrop`, hidden `<input type="file">`, and preview markup.

7. **Pane Splitting & Resize Handles (>6 occurrences)**:
   `BrowsePage`, `BrowseCardEditor`, `DeckWorksheetModal`, and `DiffWorkspace` implement complex multi-pane layouts. `BrowseCardEditor.tsx:84-113` even uses direct imperative DOM manipulation (`document.body.style.cursor = 'col-resize'`, window mousemove listeners) for resizable panels.

8. **Dynamic Card Field Form Rendering (>6 occurrences)**:
   `BrowseCardEditor`, `StudyQuickEditDialog`, and `EditCardModal` each contain 60–100 lines of identical logic iterating over `field_defs`, switching between `Input`, `Textarea`, and `MediaFieldPreview` based on field name or string length.

---

## 2.5 Authoritative OKLCH Design Tokens Contract (`index.css`)

Flama uses **TailwindCSS v4.3** with the `@theme inline` directive and pure **OKLCH** color values. All UI primitives and refactored components must reference these exact tokens:

### Color Tokens Contract
| Token Name | Light Mode (OKLCH) | Dark Mode (OKLCH) | Semantic Purpose |
|:---|:---|:---|:---|
| `--primary` | `oklch(0.635 0.215 35)` | `oklch(0.70 0.21 40)` | Brand Coral/Orange — primary actions, highlights, active states |
| `--primary-foreground` | `oklch(0.985 0 0)` | `oklch(0.145 0 0)` | High-contrast text on primary background |
| `--background` | `oklch(1 0 0)` | `oklch(0.145 0 0)` | Application base background |
| `--foreground` | `oklch(0.19 0.02 50)` | `oklch(0.985 0 0)` | Base body text |
| `--card` | `oklch(1 0 0)` | `oklch(0.205 0 0)` | Card and modal surface background |
| `--card-foreground` | `oklch(0.19 0.02 50)` | `oklch(0.985 0 0)` | Card body text |
| `--popover` | `oklch(1 0 0)` | `oklch(0.205 0 0)` | Dropdown, tooltip, and popover container |
| `--popover-foreground` | `oklch(0.19 0.02 50)` | `oklch(0.985 0 0)` | Popover text |
| `--secondary` | `oklch(0.95 0.03 65)` | `oklch(0.269 0 0)` | Secondary buttons, subtle pills |
| `--secondary-foreground` | `oklch(0.25 0.03 45)` | `oklch(0.985 0 0)` | Text on secondary elements |
| `--muted` | `oklch(0.96 0.015 65)` | `oklch(0.269 0 0)` | Subdued backgrounds, table headers |
| `--muted-foreground` | `oklch(0.5 0.025 45)` | `oklch(0.708 0 0)` | Helper text, placeholders, disabled text |
| `--accent` | `oklch(0.94 0.04 55)` | `oklch(0.269 0 0)` | Hover states on interactive items |
| `--accent-foreground` | `oklch(0.25 0.04 40)` | `oklch(0.985 0 0)` | Text on accent hover |
| `--destructive` | `oklch(0.577 0.245 27.325)` | `oklch(0.704 0.191 22.216)` | Errors, delete actions, destructive alerts |
| `--border` | `oklch(0.9 0.025 60)` | `oklch(1 0 0 / 10%)` | Borders, dividers, subtle outlines |
| `--input` | `oklch(0.9 0.025 60)` | `oklch(1 0 0 / 15%)` | Form input borders |
| `--ring` | `oklch(0.635 0.215 35)` | `oklch(0.70 0.21 40)` | Focus outline rings |

### Radius & Geometry Tokens
- Base Radius: `--radius: 0.625rem;` (10px)
- `rounded-sm`: `calc(var(--radius) * 0.6)` (6px)
- `rounded-md`: `calc(var(--radius) * 0.8)` (8px)
- `rounded-lg`: `var(--radius)` (10px — standard for buttons, inputs, cards)
- `rounded-xl`: `calc(var(--radius) * 1.4)` (14px)
- `rounded-2xl`: `calc(var(--radius) * 1.8)` (18px)
- `rounded-3xl`: `calc(var(--radius) * 2.2)` (22px)
- `rounded-4xl`: `calc(var(--radius) * 2.6)` (26px)
- `rounded-full`: `9999px` (for status pills, badges, circle action buttons)

---

## 2.6 Target FSD Migration Blueprint

```
frontend/src/
├── app/                  # Application initialization, router, global providers, App.tsx
├── pages/                # Route compositions (thin page wrappers < 150 LOC)
│   ├── BrowsePage/
│   ├── StudyPage/
│   ├── AdminTaxonomyPage/
│   └── MarketplaceDeckPage/
├── widgets/              # Large composite UI blocks combining features & entities
│   ├── BrowseWorkspace/  # SplitPane integrating sidebar, table, and editor
│   ├── WorksheetStudio/  # Worksheet controls + live canvas preview
│   └── DiffViewer/       # Side-by-side collaboration comparison
├── features/             # Actionable user interactions & flows (< 300 LOC per file)
│   ├── deck-audio-queue/ # Audio generation queue & player
│   ├── deck-import/      # Wizard, parsing, conflict resolution
│   ├── mcp-tokens/       # Token generation, secret display, revoke actions
│   └── study-scheduler/  # Review buttons, interval calculations
├── entities/             # Core domain models with UI cards & hooks
│   ├── card/             # CardPreview, CardFieldsForm, useCardDetail
│   ├── deck/             # DeckCard, DeckRow, DeckTree, useDeckList
│   ├── note/             # NoteTypeBadge, NoteFieldsList
│   ├── taxonomy/         # TaxonomyPill, CategoryBadge
│   └── token/            # TokenStatusBadge, TokenExpiry
└── shared/               # Layer 0: Zero domain logic
    ├── ui/               # Reusable UI Primitives (SearchInput, ConfirmDialog, StatusPill, etc.)
    ├── api/              # Axios/Fetch client, error interceptors
    ├── lib/              # cn, formatters, sanitizers, date/time utils
    └── types/            # Generic API contracts, pagination types
```

---

# 3. R2: Reusable UI Primitives Technical Design (Leaf-to-Root)

All 8 primitives reside under `frontend/src/shared/ui/` and utilize `class-variance-authority` (CVA), standard OKLCH tokens, and full WAI-ARIA compliance.

```
frontend/src/shared/ui/
├── SearchInput/          # Input with icon, clear button, debounce, loading spinner
├── ConfirmDialog/        # Radix AlertDialog wrapper with destructive/warning/primary variants
├── StatusPill/           # Semantic badge with pulse dots and tone variants
├── CodeSnippetBox/       # Code & secret viewer with copy-to-clipboard feedback
├── FilterPillGroup/      # Segmented filter buttons with keyboard arrow navigation
├── ImageUploadDropzone/  # Drag & drop upload area with paste, validation, and preview
├── SplitPane/            # Resizable multi-pane container with persistent sizes
└── CardFieldsForm/       # Data-driven dynamic field generator for Note Types
```

---

## 3.1 `SearchInput`

### Overview & Responsibilities
A standardized, accessible search input encapsulating the search icon, clear button (`X`), loading indicator, optional keyboard shortcut badge (`Ctrl+K`), debounced change propagation, and focus styling.

### TypeScript Props Interface
```typescript
import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { searchInputVariants } from "./SearchInput.styles"

export interface SearchInputProps
  extends Omit<React.ComponentProps<"input">, "size" | "onChange">,
    VariantProps<typeof searchInputVariants> {
  /** Current value of the search input */
  value: string
  /** Callback fired immediately or after debounce */
  onChange: (value: string) => void
  /** Debounce delay in milliseconds (default: 0 = immediate) */
  debounceMs?: number
  /** Shows an animated loading spinner instead of search icon */
  isLoading?: boolean
  /** Shows a clear (X) button when value is non-empty (default: true) */
  showClearButton?: boolean
  /** Optional keyboard shortcut hint displayed on the right (e.g. '⌘K' or 'Ctrl+K') */
  shortcutHint?: string
  /** Custom callback when user clears the search */
  onClear?: () => void
  /** Optional wrapper class for the outer container */
  wrapperClassName?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const searchInputVariants = cva(
  "w-full rounded-lg border bg-background text-foreground transition-all placeholder:text-muted-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      size: {
        sm: "h-8 pl-8 pr-7 text-xs",
        default: "h-9 pl-9 pr-8 text-xs sm:text-sm",
        lg: "h-10 pl-10 pr-9 text-sm",
      },
      variant: {
        default: "border-input shadow-2xs hover:border-border/80 focus-visible:bg-background",
        muted: "border-transparent bg-muted/50 hover:bg-muted/70 focus-visible:border-ring focus-visible:bg-background",
        ghost: "border-transparent bg-transparent hover:bg-muted/40 focus-visible:border-ring focus-visible:bg-background",
      },
    },
    defaultVariants: {
      size: "default",
      variant: "default",
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="searchbox"` on the `<input>` element.
- **ARIA Attributes**: `aria-label={props['aria-label'] || 'Tìm kiếm'}`, `aria-busy={isLoading}`.
- **Keyboard Navigation**:
  - `Escape`: Clears the input when non-empty, fires `onClear?.()`, and maintains focus.
  - `Enter`: Submits or triggers search if wrapped in a `<form>`.
  - Global `Ctrl+K` or `/` focus shortcut integration via optional `shortcutHint`.

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/admin/pages/AdminUsersPage.tsx` | 344–355 | `<div className="relative"><Search .../><Input className="pl-9" .../></div>` | Eliminates 12 lines, adds auto-clear |
| `frontend/src/features/admin/pages/AdminTicketsPage.tsx` | 174–185 | Inline Search icon + Input with pl-9 | Unified search aesthetics & clear button |
| `frontend/src/features/admin/pages/AdminMcpTokensPage.tsx` | 457–468 | Duplicate relative wrapper with Search icon | Debouncing support for token filtering |
| `frontend/src/features/admin/pages/AdminFeesPage.tsx` | 576–585 | Search input with left-2.5 icon | Correct 10px icon padding alignment |
| `frontend/src/features/admin/pages/AdminImageLibraryPage.tsx` | 279–288 | Search box in asset gallery toolbar | Instant clear button on escape |
| `frontend/src/features/admin/pages/AdminPaymentsPage.tsx` | 458–470 | Order search input with manual clear logic | Replaces 20 lines of redundant state |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 665–676 | Category/Tag search input with size-3.5 icon | Consistent icon & placeholder styling |
| `frontend/src/features/library/pages/LibraryPages.tsx` | 461–472 | Deck library search bar | Eliminates duplicate search markup |
| `frontend/src/features/marketplace/pages/MarketplacePages.tsx` | 506–518 | Marketplace search bar with `pointer-events-none` icon | Full ARIA compliance, debounce support |
| `frontend/src/features/marketplace/pages/SharedDeckDetailPage.tsx` | 1189–1200 | Review/card search input inside deck detail | Consistent focus ring and clear action |
| `frontend/src/features/browse/components/BrowseDeckSidebar.tsx` | 220–228 | `pl-8 h-8 rounded-lg text-xs bg-muted/50` | Unifies sidebar filter styling |
| `frontend/src/features/browse/components/BrowseToolbar.tsx` | 26–36 | Card search bar with custom clear button | Drops 15 lines of custom clear JSX |
| `frontend/src/features/deck-collaboration/components/DiffWorkspace.tsx` | 308–320 | Diff search bar with search button | Built-in loading spinner during diff queries |

---

## 3.2 `ConfirmDialog`

### Overview & Responsibilities
A type-safe, accessible confirmation modal built on Radix UI's `AlertDialog` primitive. Replaces boilerplate delete/action modals across the app with consistent focus trapping, accessible screen-reader alerts, async loading state handling, and semantic button variants (`destructive`, `warning`, `primary`).

### TypeScript Props Interface
```typescript
import * as React from "react"

export interface ConfirmDialogProps {
  /** Controls dialog visibility when controlled */
  open?: boolean
  /** Visibility change callback */
  onOpenChange?: (open: boolean) => void
  /** Optional trigger element (renders inside AlertDialogTrigger) */
  trigger?: React.ReactNode
  /** Dialog title */
  title: React.ReactNode
  /** Dialog detailed description or confirmation question */
  description: React.ReactNode
  /** Label for the confirm button (default: 'Xác nhận') */
  confirmText?: string
  /** Label for the cancel button (default: 'Hủy') */
  cancelText?: string
  /** Semantic variant of confirm button: destructive (red), warning (amber), primary (brand coral) */
  variant?: "destructive" | "warning" | "primary"
  /** Async or sync callback executed when user confirms. If returns promise, manages loading spinner */
  onConfirm: () => Promise<void> | void
  /** Optional callback when user cancels */
  onCancel?: () => void
  /** External loading indicator to disable buttons and show spinner */
  isLoading?: boolean
  /** Danger zone verification: requires user to type an exact string (e.g. deck name) before confirming */
  confirmPhrase?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const confirmDialogHeaderVariants = cva(
  "flex items-center gap-3 pb-3 border-b",
  {
    variants: {
      variant: {
        destructive: "text-destructive border-destructive/15",
        warning: "text-amber-600 dark:text-amber-400 border-amber-500/15",
        primary: "text-primary border-primary/15",
      },
    },
    defaultVariants: {
      variant: "destructive",
    },
  }
)

export const confirmButtonVariants = cva(
  "inline-flex items-center justify-center font-semibold rounded-lg h-9 px-4 text-xs sm:text-sm transition-all shadow-xs",
  {
    variants: {
      variant: {
        destructive: "bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/30",
        warning: "bg-amber-600 text-white hover:bg-amber-700 focus-visible:ring-amber-500/30",
        primary: "bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-primary/30",
      },
    },
    defaultVariants: {
      variant: "destructive",
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Radix Primitive**: Uses `AlertDialogPrimitive.Root`, `Portal`, `Overlay`, `Content`, `Title`, `Description`, `Action`, `Cancel`.
- **Role**: `role="alertdialog"`.
- **Focus Management**: Initial focus automatically directed to `AlertDialogPrimitive.Cancel` to prevent accidental confirmation of destructive operations. Focus trapped within the dialog.
- **Keyboard Handling**:
  - `Escape`: Triggers cancel action and restores focus to the trigger.
  - `Tab` / `Shift+Tab`: Cycles between Cancel and Confirm buttons (or confirmation input).

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/admin/pages/AdminUsersPage.tsx` | 725–781 | Custom delete/ban user `<Dialog>` | Eliminates 56 lines of modal JSX & state |
| `frontend/src/features/admin/pages/AdminMcpTokensPage.tsx` | 1120–1135 | Token revocation dialog with duplicate footer | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminMcpTokensPage.tsx` | 1230–1245 | Hard delete token dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 1110–1125 | Delete category confirmation dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 1180–1195 | Delete JLPT level confirmation dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 1250–1265 | Delete CEFR level confirmation dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 1320–1335 | Delete Tag confirmation dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminTaxonomyPage.tsx` | 1380–1395 | Delete Topic confirmation dialog | Eliminates 16 lines |
| `frontend/src/features/admin/pages/AdminImageLibraryPage.tsx` | 615–630 | Delete media asset dialog | Eliminates 16 lines |
| `frontend/src/features/dashboard/components/DeckModals.tsx` | 205–230 | Delete deck confirmation dialog with phrase match | Replaces 26 lines with safe `confirmPhrase` prop |
| `frontend/src/features/deck-collaboration/pages/InstalledDeckUpdatePage.tsx` | 620–645 | Discard change request / rollback confirm | Eliminates 25 lines |

---

## 3.3 `StatusPill`

### Overview & Responsibilities
A unified, semantic status pill badge supporting status tones (`success`, `warning`, `error`, `info`, `neutral`, `primary`), visual weights (`subtle`, `outline`, `solid`), optional animated pulse dots, and leading icons. Replaces >250 ad-hoc `<Badge className="...">` occurrences.

### TypeScript Props Interface
```typescript
import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { statusPillVariants } from "./StatusPill.styles"

export interface StatusPillProps
  extends React.ComponentProps<"span">,
    VariantProps<typeof statusPillVariants> {
  /** Optional icon rendered before the label */
  icon?: React.ComponentType<{ className?: string }>
  /** Shows a status dot indicator (default: false) */
  dot?: boolean
  /** Causes the status dot to animate a gentle radar pulse */
  pulse?: boolean
  /** Content label */
  children: React.ReactNode
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const statusPillVariants = cva(
  "inline-flex items-center justify-center font-semibold rounded-full select-none transition-colors border",
  {
    variants: {
      status: {
        success:
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 dark:bg-emerald-500/15",
        warning:
          "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300 dark:bg-amber-500/15",
        error:
          "border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/20 dark:text-destructive-foreground",
        info:
          "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 dark:bg-sky-500/15",
        neutral:
          "border-border bg-muted/60 text-muted-foreground dark:bg-muted/40",
        primary:
          "border-primary/30 bg-primary/10 text-primary dark:bg-primary/20",
      },
      size: {
        xs: "h-4 px-1.5 text-[10px] gap-1 [&>svg]:size-2.5",
        sm: "h-5 px-2 text-[11px] gap-1.5 [&>svg]:size-3",
        md: "h-6 px-2.5 text-xs gap-1.5 [&>svg]:size-3.5",
      },
      appearance: {
        subtle: "border-transparent",
        outline: "bg-transparent",
        soft: "shadow-2xs",
        solid: "border-transparent text-white",
      },
    },
    compoundVariants: [
      { status: "success", appearance: "solid", className: "bg-emerald-600 text-white" },
      { status: "warning", appearance: "solid", className: "bg-amber-600 text-white" },
      { status: "error", appearance: "solid", className: "bg-destructive text-white" },
      { status: "info", appearance: "solid", className: "bg-sky-600 text-white" },
      { status: "primary", appearance: "solid", className: "bg-primary text-primary-foreground" },
    ],
    defaultVariants: {
      status: "neutral",
      size: "sm",
      appearance: "soft",
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="status"` if the badge represents dynamic live state.
- **Attributes**: Accessible `title` matching children for truncated views. Color alone is never the sole indicator of status (always paired with descriptive text or an accessible label).

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/admin/pages/AdminPaymentsPage.tsx` | 127–185 | 10+ ad-hoc `<Badge variant="outline" className="...">` for payment status | Consolidates all payment status badges into `<StatusPill status="...">` |
| `frontend/src/features/admin/pages/AdminFeesPage.tsx` | 127–185 | Ad-hoc fee tier badges | Eliminates hardcoded sky/emerald/amber classes |
| `frontend/src/features/admin/pages/AdminImageLibraryPage.tsx` | 412–428 | Inconsistent asset tag badges | Standardized badge radiuses & font size |
| `frontend/src/features/audio/components/BatchProgressList.tsx` | 19–38 | Inline status check with emerald/amber badges | Clean declarative `<StatusPill status={item.status}>` |
| `frontend/src/features/audio/components/DeckAudioQueueMonitor.tsx` | 340–355 | Destructive badges for audio generation errors | Unified tooltip and error styling |
| `frontend/src/features/browse/pages/BrowsePage.tsx` | 98–170 | Repeated emerald border/text badges | Eliminates 8 copy-pasted class strings |
| `frontend/src/features/deck-collaboration/components/DiffWorkspace.tsx` | 180–210 | Added/Modified/Deleted diff type pills | Unified change-type indicators |

---

## 3.4 `CodeSnippetBox`

### Overview & Responsibilities
A reusable code, token, and secret viewer. Provides built-in copy-to-clipboard functionality with visual feedback (Check icon, tooltip, toast), optional secret masking (toggle visibility with eye icon), single-line or multi-line scrolling, and monospaced typography adhering to OKLCH tokens.

### TypeScript Props Interface
```typescript
import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { codeSnippetBoxVariants } from "./CodeSnippetBox.styles"

export interface CodeSnippetBoxProps
  extends Omit<React.ComponentProps<"div">, "children">,
    VariantProps<typeof codeSnippetBoxVariants> {
  /** The text/code/token string to display and copy */
  code: string
  /** Human-readable label displayed above or beside the box */
  label?: string
  /** Whether the value is sensitive and should be masked by default (e.g. secret tokens) */
  secret?: boolean
  /** Shows a copy button (default: true) */
  copyable?: boolean
  /** Success message shown in toast after copying (default: 'Đã sao chép vào bộ nhớ tạm') */
  copySuccessMessage?: string
  /** Optional language indicator tag (e.g. 'json', 'bash', 'css') */
  language?: string
  /** Maximum height for multi-line snippets (e.g. 'max-h-48') */
  maxHeight?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const codeSnippetBoxVariants = cva(
  "relative flex items-center justify-between rounded-lg border font-mono text-xs transition-colors",
  {
    variants: {
      variant: {
        default: "border-border bg-muted/40 text-foreground",
        terminal: "border-slate-800 bg-slate-950 text-slate-100 dark:border-border dark:bg-background/80",
        secret: "border-primary/20 bg-primary/5 text-primary",
        subtle: "border-transparent bg-muted/30 text-foreground",
      },
      size: {
        sm: "py-1 px-2.5 text-[11px]",
        default: "py-2 px-3 text-xs",
        lg: "py-2.5 px-4 text-sm",
      },
      multiline: {
        true: "items-start flex-col gap-2",
        false: "items-center flex-row",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
      multiline: false,
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="region"` with `aria-label={label || 'Đoạn mã'}`.
- **Copy Button**: `<button aria-label="Sao chép vào clipboard" tabIndex={0}>`.
- **Live Region**: Status notification uses `aria-live="polite"` so screen-readers announce "Đã sao chép" upon copy activation.

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/admin/pages/AdminMcpTokensPage.tsx` | 955–975 | Secret token reveal modal with copy button | Replaces 20 lines of custom copy state |
| `frontend/src/features/settings/components/McpTokensTab.tsx` | 250–270 | Server URL copy box with local timeout state | Eliminates duplicated copy timer |
| `frontend/src/features/settings/components/McpTokensTab.tsx` | 585–605 | Generated secret token box | Unifies secret masking & copying |
| `frontend/src/features/settings/components/McpOAuthTab.tsx` | 630–645 | OAuth client ID display with copy icon | Clean single-line snippet |
| `frontend/src/features/settings/components/McpOAuthTab.tsx` | 910–925 | OAuth client secret box with masking | Replaces manual password masking |
| `frontend/src/features/settings/components/YomitanTokensTab.tsx` | 120–135 | Yomitan Connect URL copy box | Eliminates custom `copied === 'connect-url'` state |
| `frontend/src/features/import/components/AnkiCorsGuideTab.tsx` | 110–120 | Anki config command snippet | Consistent terminal styling |
| `frontend/src/features/guide/components/YomitanMarkersExplorer.tsx` | 135–210 | 6 consecutive marker copy buttons (`{expression}`, etc.) | Eliminates 75 lines of repetitive copy state |
| `frontend/src/features/note-types/components/NoteTypeAiGuideModal.tsx` | 130–160 | AI prompt template copy container | Built-in multiline scroll & copy feedback |

---

## 3.5 `FilterPillGroup`

### Overview & Responsibilities
A keyboard-accessible segmented button group for single or multiple selection filters (e.g., status filters: All, Active, Pending, Completed). Replaces disparate button loops with accessible `role="radiogroup"` or `role="group"`, arrow-key navigation, active OKLCH indicator styling, count badges, and dot indicators.

### TypeScript Props Interface
```typescript
import * as React from "react"

export interface FilterPillOption<T extends string = string> {
  /** Unique value of the filter option */
  value: T
  /** Display label */
  label: React.ReactNode
  /** Optional count badge number (e.g. 12 cards) */
  count?: number
  /** Optional indicator dot color class (e.g. 'bg-emerald-500') */
  dotColor?: string
  /** Optional icon component */
  icon?: React.ComponentType<{ className?: string }>
  /** Disables this specific filter */
  disabled?: boolean
}

export interface FilterPillGroupProps<T extends string = string> {
  /** Array of available filter options */
  options: FilterPillOption<T>[]
  /** Currently selected value (single-select) */
  value: T
  /** Change callback */
  onChange: (value: T) => void
  /** Size variant */
  size?: "sm" | "md"
  /** Label rendered before pills (e.g. 'Lọc trạng thái:') */
  label?: React.ReactNode
  /** Additional wrapper CSS class */
  className?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const filterPillGroupVariants = cva(
  "flex flex-wrap items-center gap-1.5 select-none",
  {
    variants: {
      size: {
        sm: "text-xs",
        md: "text-sm",
      },
    },
    defaultVariants: {
      size: "sm",
    },
  }
)

export const filterPillItemVariants = cva(
  "inline-flex items-center gap-1.5 font-semibold rounded-full border transition-all cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      active: {
        true: "bg-primary text-primary-foreground border-primary shadow-2xs font-bold",
        false: "bg-card text-muted-foreground border-border/80 hover:bg-muted hover:text-foreground",
      },
      size: {
        sm: "h-7 px-3 text-xs [&>svg]:size-3",
        md: "h-8 px-3.5 text-xs sm:text-sm [&>svg]:size-3.5",
      },
    },
    defaultVariants: {
      active: false,
      size: "sm",
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="radiogroup"` on container. Each pill has `role="radio"` and `aria-checked={isSelected}`.
- **Keyboard Navigation**:
  - `ArrowLeft` / `ArrowUp`: Focuses and selects the previous enabled filter.
  - `ArrowRight` / `ArrowDown`: Focuses and selects the next enabled filter.
  - `Home` / `End`: Jumps to the first / last filter option.
  - `Tab`: Navigates into the radiogroup (focused on the active item).

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/admin/pages/AdminPaymentsPage.tsx` | 431–455 | Manual button map with `slate-900` hardcoded colors | Eliminates 24 lines, adopts OKLCH primary |
| `frontend/src/features/admin/pages/AdminPaymentsPage.tsx` | 762–780 | Second identical status pill filter for transactions | Eliminates duplicate loop |
| `frontend/src/features/deck-collaboration/components/DiffWorkspace.tsx` | 270–305 | Custom filter pill loop with active borders | Keyboard arrow navigation added |
| `frontend/src/features/wallet/components/WalletTransactionsTable.tsx` | 60–80 | Transaction type filter buttons | Drops 20 lines of repetitive button state |
| `frontend/src/features/worksheets/components/WorksheetTemplateSelectStep.tsx` | 40–65 | Category filter buttons (Kanji / Vocab / Table) | Consistent pill styling & count badges |
| `frontend/src/features/marketplace/pages/MarketplacePages.tsx` | 450–490 | Category selector pills | Eliminates custom active styling logic |

---

## 3.6 `ImageUploadDropzone`

### Overview & Responsibilities
A drag-and-drop file and image upload zone. Handles file drag hover states, file type validation, size limit checks, clipboard image paste (`Ctrl+V`), image preview thumbnail rendering, and loading progress indicators.

### TypeScript Props Interface
```typescript
import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { dropzoneVariants } from "./ImageUploadDropzone.styles"

export interface ImageUploadDropzoneProps
  extends Omit<React.ComponentProps<"div">, "onDrop">,
    VariantProps<typeof dropzoneVariants> {
  /** Callback fired when valid file(s) are selected or dropped */
  onFilesSelected: (files: File[]) => void
  /** Allowed MIME types (e.g. ['image/png', 'image/jpeg', 'image/webp']) */
  accept?: string[]
  /** Maximum file size in bytes (default: 2MB = 2 * 1024 * 1024) */
  maxSizeBytes?: number
  /** Whether multiple file drop is allowed (default: false) */
  multiple?: boolean
  /** Shows an active uploading spinner */
  isUploading?: boolean
  /** Optional preview image URL to display existing or uploaded image */
  previewUrl?: string | null
  /** Callback when user clicks to remove the current preview image */
  onRemovePreview?: () => void
  /** Enables listening to global or container Ctrl+V clipboard paste (default: true) */
  enablePaste?: boolean
  /** Helper subtitle displayed below title */
  hintText?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const dropzoneVariants = cva(
  "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all cursor-pointer select-none text-center outline-none focus-visible:ring-2 focus-visible:ring-ring",
  {
    variants: {
      variant: {
        default: "p-6 min-h-36 bg-card hover:bg-muted/30",
        compact: "p-3 size-20 min-h-20 bg-card hover:bg-muted/40",
        avatar: "size-32 rounded-full overflow-hidden border-solid border-4 border-muted/80 bg-muted",
      },
      isDragging: {
        true: "border-primary bg-primary/10 scale-102 shadow-md",
        false: "border-border/80 hover:border-primary/50",
      },
      disabled: {
        true: "pointer-events-none opacity-50",
        false: "",
      },
    },
    defaultVariants: {
      variant: "default",
      isDragging: false,
      disabled: false,
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="button"`.
- **Keyboard Navigation**: Pressing `Enter` or `Space` triggers the hidden native `<input type="file">`.
- **Screen Reader**: Hidden input is linked with `aria-label="Tải lên tệp ảnh"`. Errors (e.g. file too large) trigger `aria-live="assertive"` announcements.

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/support/pages/FeedbackPage.tsx` | 688–718 | Size-20 upload tile with `onDragOver` & `onDrop` | Eliminates 30 lines of manual drop logic |
| `frontend/src/features/admin/pages/AdminImageLibraryPage.tsx` | 571–590 | Raw `<Input type="file">` with manual size check | Adds drag-drop, paste, and visual preview |
| `frontend/src/features/profile/components/AvatarUploadModal.tsx` | 104–135 | Avatar upload box with hidden input & button | Replaces 31 lines with `<ImageUploadDropzone variant="avatar" />` |
| `frontend/src/features/import/components/ImportFileStep.tsx` | 81–118 | CSV/TSV dashed dropzone with manual drag state | Clean multi-file drop with type validation |
| `frontend/src/features/study/components/EditCardModal.tsx` | 574–589 | Raw file input in media field editor | Inline thumbnail preview + drag drop |

---

## 3.7 `SplitPane`

### Overview & Responsibilities
A high-performance resizable split-pane layout supporting horizontal (left/right) or vertical (top/bottom) division. Features mouse and touch drag handles, keyboard resizing, persistent widths saved to `localStorage`, minimum/maximum constraints, and responsive fallback for mobile screens (<768px). Eliminates raw window DOM event listeners in component bodies.

### TypeScript Props Interface
```typescript
import * as React from "react"

export interface SplitPaneProps {
  /** Left (or Top) child component */
  primaryPane: React.ReactNode
  /** Right (or Bottom) child component */
  secondaryPane: React.ReactNode
  /** Split orientation (default: 'horizontal') */
  orientation?: "horizontal" | "vertical"
  /** Initial size in pixels of the primary pane (default: 320) */
  defaultSize?: number
  /** Minimum allowed size in pixels of the primary pane (default: 240) */
  minSize?: number
  /** Maximum allowed size in pixels of the primary pane (default: 600) */
  maxSize?: number
  /** LocalStorage key for persisting user drag preference */
  storageKey?: string
  /** Mobile fallback: if true, switches to tabbed or stacked layout on mobile screens */
  responsive?: boolean
  /** Active mobile tab when responsive is true ('primary' | 'secondary') */
  mobileActivePane?: "primary" | "secondary"
  /** Additional container CSS class */
  className?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const splitPaneHandleVariants = cva(
  "relative shrink-0 transition-colors select-none z-20 outline-none focus-visible:bg-primary/80",
  {
    variants: {
      orientation: {
        horizontal:
          "w-1 cursor-col-resize hover:w-1.5 hover:bg-primary/60 bg-border/40 active:bg-primary",
        vertical:
          "h-1 cursor-row-resize hover:h-1.5 hover:bg-primary/60 bg-border/40 active:bg-primary",
      },
    },
    defaultVariants: {
      orientation: "horizontal",
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Role**: `role="separator"` on the handle.
- **Attributes**: `aria-orientation={orientation}`, `aria-valuenow={currentSize}`, `aria-valuemin={minSize}`, `aria-valuemax={maxSize}`.
- **Keyboard Handling**:
  - `ArrowLeft` / `ArrowRight` (horizontal) or `ArrowUp` / `ArrowDown` (vertical): Adjusts pane size in increments of 10px.
  - `Home`: Collapses or snaps to `minSize`.
  - `End`: Expands to `maxSize`.

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/browse/components/BrowseCardEditor.tsx` | 84–113, 200–204 | Raw imperative `onMouseDown`, `document.body.style.cursor` resizing | Eliminates 35 lines of DOM manipulation; clean React hook |
| `frontend/src/features/browse/pages/BrowsePage.tsx` | 465–479 | 3-pane layout (sidebar + table + editor) with mobile tab hiding | Standardized responsive layout |
| `frontend/src/features/worksheets/components/DeckWorksheetModal.tsx` | 899–905, 4200 | Studio sidebar (~380px) and live print preview canvas | Enables user resizing of worksheet preview pane |
| `frontend/src/features/deck-collaboration/components/DiffWorkspace.tsx` | 300–340 | Diff filter list vs diff items table | Flexible inspector view |

---

## 3.8 `CardFieldsForm`

### Overview & Responsibilities
A data-driven dynamic form generator for note types. Inspects an array of field definitions (`field_defs`), automatically renders appropriate input widgets (`Input`, `Textarea`, `MediaFieldPreview`, or markdown toggle), enforces `required` flags, handles multiline detection, integrates tag management, and supports keyboard submission (`Ctrl+Enter`). Eliminates duplicate field-rendering logic across `BrowseCardEditor`, `StudyQuickEditDialog`, and `EditCardModal`.

### TypeScript Props Interface
```typescript
import * as React from "react"

export interface CardFieldDef {
  name: string
  field_type?: "text" | "textarea" | "image" | "audio" | "diagram" | string
  required?: boolean
  description?: string
}

export interface CardFieldsFormProps {
  /** Array of field definitions from Note Type */
  fieldDefs: CardFieldDef[]
  /** Current field values mapped by field name */
  values: Record<string, string>
  /** Change callback when any field is edited */
  onChange: (values: Record<string, string>) => void
  /** Optional tags array */
  tags?: string[]
  /** Change callback when tags are edited */
  onTagsChange?: (tags: string[]) => void
  /** Media URL resolver for audio/image previews */
  resolveMediaUrl?: (filename: string) => string | undefined
  /** Async media upload handler when user selects local file for media field */
  onMediaUpload?: (fieldName: string, file: File) => Promise<string | void>
  /** Callback fired on Ctrl+Enter keyboard submission */
  onSubmit?: () => void
  /** Disables all fields during network submission */
  disabled?: boolean
  /** Validation errors map */
  errors?: Record<string, string>
  /** Additional container styling */
  className?: string
}
```

### Tailwind CSS / CVA Definition
```typescript
import { cva } from "class-variance-authority"

export const cardFieldLabelVariants = cva(
  "text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center justify-between",
  {
    variants: {
      hasError: {
        true: "text-destructive font-bold",
        false: "",
      },
    },
  }
)

export const cardFieldInputVariants = cva(
  "w-full rounded-lg border text-xs sm:text-sm text-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary bg-muted/50 focus-visible:bg-background",
  {
    variants: {
      hasError: {
        true: "border-destructive focus-visible:ring-destructive",
        false: "border-input hover:border-border",
      },
    },
  }
)
```

### ARIA & Keyboard Accessibility
- **Keyboard Handling**: `Ctrl+Enter` (or `Cmd+Enter`) triggers `onSubmit?.()`.
- **Form Semantics**:
  - Labels use `htmlFor={`field-${field.name}`}`.
  - Required fields mark `<input aria-required="true">` with visual asterisk `<span className="text-destructive">*</span>`.
  - Error messages linked via `aria-describedby={`field-${field.name}-error`}`.

### Target Replacement Call Sites
| File Path | Lines | Current Inline Pattern | Replacement Benefit |
|---|---|---|---|
| `frontend/src/features/browse/components/BrowseCardEditor.tsx` | 251–358 | 107 lines of field mapping, textarea vs input checks, tag adding | Eliminates 107 lines of duplicate JSX |
| `frontend/src/features/study/components/StudyQuickEditDialog.tsx` | 395–455 | 60 lines of dynamic note field iteration & textarea check | Eliminates 60 lines of duplicate JSX |
| `frontend/src/features/study/components/EditCardModal.tsx` | 490–589 | 100 lines of field iteration, media inputs, markdown toggle | Eliminates 100 lines of duplicate JSX |
| `frontend/src/features/note-types/pages/NoteTypeFieldsPage.tsx` | 220–300 | Field editor sample preview | Reusable preview component |

---

# 4. R3: Headless Custom Hooks Architecture

## 4.1 State Extraction Methodology (<8 States Rule)
To eliminate state explosion and prevent cascading re-renders:
1. **Separation of Presentation from State**: Presentation components become thin JSX skins receiving typed props. All state transitions, network mutations, and browser listeners reside in headless hooks.
2. **The `< 8 States` Contract**: Any custom hook must strictly declare **fewer than 8 independent reactive states** (`useState` / `useReducer`). If a domain flow requires more than 7 states, it is partitioned into cohesive sub-hooks.
3. **Compound Composition**: High-level orchestrators compose orthogonal sub-hooks rather than maintaining flattened mega-state.

```
                      ┌────────────────────────────────────────────────────────┐
                      │                 Headless Custom Hooks                   │
                      └──────────────────────────┬─────────────────────────────┘
                                                 │
      ┌─────────────────────────┬────────────────┼─────────────────────────┬─────────────────────────┐
      ▼                         ▼                ▼                         ▼                         ▼
┌───────────────┐       ┌───────────────┐ ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ Browse Domain │       │  Study Domain │ │Worksheet Studio│      │ Audio & Media │       │ Admin & System│
├───────────────┤       ├───────────────┤ ├───────────────┤       ├───────────────┤       ├───────────────┤
│useBrowseFilter│       │useStudySession│ │useWorksheetSt.│       │useAudioPlayer │       │useMcpTokens   │
│useBrowseSelect│       │useStudyInter. │ │useWorksheetCfg│       │               │       │useTaxonomyMgr │
│useBrowseCardOp│       └───────────────┘ │useWorksheetPrv│       └───────────────┘       │useMarketplace │
│useCardDetailEd│                         └───────────────┘                               │useDeckExportIm│
└───────────────┘                                                                         └───────────────┘
```

---

## 4.2 Specifications for 14 Headless Custom Hooks

### Hook 1: `useBrowseFilters`
- **Location**: `frontend/src/features/browse/hooks/useBrowseFilters.ts`
- **Source of Extraction**: `useBrowseState.ts` (lines 114–143, 335–385).
- **Purpose**: Encapsulates card filtering, text search, deck tree selection, card status tabs, sorting column & order, pagination, and bidirectional URL query parameter synchronization.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `selectedDeckId`: `number | null`
  2. `deckSearchQuery`: `string`
  3. `searchTerm`: `string`
  4. `debouncedSearch`: `string`
  5. `statusFilter`: `'all' | 'new' | 'learn' | 'due' | 'suspended'`
  6. `sortBy`: `'due' | 'created' | 'modified' | 'word' | 'deck'`
  7. `sortDir`: `'asc' | 'desc'`

#### TypeScript Interface & Signature
```typescript
export interface UseBrowseFiltersOptions {
  syncWithUrl?: boolean
  defaultPerPage?: number
  defaultSortBy?: 'due' | 'created' | 'modified' | 'word' | 'deck'
  defaultSortDir?: 'asc' | 'desc'
}

export interface BrowseFilterState {
  selectedDeckId: number | null
  deckSearchQuery: string
  searchTerm: string
  debouncedSearch: string
  statusFilter: string
  sortBy: string
  sortDir: 'asc' | 'desc'
  page: number
  perPage: number
}

export interface BrowseFilterActions {
  setSelectedDeckId: (deckId: number | null) => void
  setDeckSearchQuery: (query: string) => void
  setSearchTerm: (term: string) => void
  setStatusFilter: (status: string) => void
  setSorting: (column: string, direction?: 'asc' | 'desc') => void
  setPage: (page: number) => void
  setPerPage: (perPage: number) => void
  resetFilters: () => void
}

export interface UseBrowseFiltersReturn {
  filters: BrowseFilterState
  actions: BrowseFilterActions
  queryParams: Record<string, string | number>
}

export function useBrowseFilters(
  options?: UseBrowseFiltersOptions
): UseBrowseFiltersReturn
```

#### Synchronization & Mutation Mechanisms
1. **URL Synchronization**: Listens to React Router's `useSearchParams()`. On mount, initializes `selectedDeckId` and `searchTerm` from URL if present. Updates URL query params via `setSearchParams({ deck_id, q }, { replace: true })` whenever filters mutate.
2. **Debounce Engine**: A `400ms` window timer buffers `searchTerm` into `debouncedSearch` to prevent API query thrashing.
3. **Storage Persistence**: `perPage` value is persisted in `localStorage` under `flama_browse_per_page`.
4. **TanStack Query Invalidation**: Generates a stable `queryParams` object passed directly into the `['browse', 'cards', queryParams]` query key.

---

### Hook 2: `useBrowseSelection`
- **Location**: `frontend/src/features/browse/hooks/useBrowseSelection.ts`
- **Source of Extraction**: `useBrowseState.ts` (lines 136–137, 390–418, 869–878).
- **Purpose**: Manages single item selection, range selection (Shift + Click), Select All / Clear All, active count computation, and global keyboard shortcuts.
- **Internal State Count**: **2 states** (Guaranteed `<8 states`):
  1. `selectedIds`: `Set<string>` (or `string[]`)
  2. `lastAnchorId`: `string | null` (anchor item for Shift+Click range calculation).

#### TypeScript Interface & Signature
```typescript
export interface UseBrowseSelectionOptions {
  allItemIds: string[]
  enabled?: boolean
  onSelectionChange?: (selectedIds: string[]) => void
}

export interface UseBrowseSelectionReturn {
  selectedIds: string[]
  selectedCount: number
  allSelected: boolean
  isPartiallySelected: boolean
  isSelected: (id: string) => boolean
  toggleSelect: (id: string, event?: React.MouseEvent) => void
  selectRange: (fromId: string, toId: string) => void
  selectAll: () => void
  clearSelection: () => void
  setSelectedIds: (ids: string[]) => void
}

export function useBrowseSelection(
  options: UseBrowseSelectionOptions
): UseBrowseSelectionReturn
```

#### Synchronization & Mutation Mechanisms
1. **Range Selection Logic**: On Shift + Click, finds index of `lastAnchorId` and current `id` within `allItemIds`, then slices and adds all intermediary IDs to the selected set.
2. **Keyboard Synchronization**: Binds `keydown` listener to `window`:
   - `Ctrl/Cmd + A`: Selects all visible cards if focus is not within an `input` / `textarea` / `contentEditable`.
   - `Escape`: Deselects all cards.
3. **Lifecycle Cleanup**: Unbinds `window` event listeners on unmount. Recomputes selection validity when `allItemIds` changes.

---

### Hook 3: `useBrowseCardOperations`
- **Location**: `frontend/src/features/browse/hooks/useBrowseCardOperations.ts`
- **Source of Extraction**: `useBrowseState.ts` (lines 590–712).
- **Purpose**: Executes single card creation/update/deletion, batch deletion, batch tag addition/removal, and batch moving cards to another deck.
- **Internal State Count**: **2 states** (Guaranteed `<8 states`):
  1. `isMutating`: `boolean`
  2. `activeOperation`: `'create' | 'update' | 'delete' | 'bulk-delete' | 'bulk-tag' | 'bulk-move' | null`

#### TypeScript Interface & Signature
```typescript
export interface CreateCardPayload {
  note_type_id: string
  deck_id: number
  field_values: Record<string, string>
  tags?: string[]
}

export interface UpdateCardPayload {
  card_id: string
  field_values: Record<string, string>
  deck_id?: number
  tags?: string[]
}

export interface UseBrowseCardOperationsOptions {
  onSuccess?: (op: string) => void
  onError?: (op: string, error: Error) => void
}

export interface UseBrowseCardOperationsReturn {
  isMutating: boolean
  activeOperation: string | null
  createCard: (payload: CreateCardPayload) => Promise<string | null>
  updateCard: (payload: UpdateCardPayload) => Promise<void>
  deleteCard: (cardId: string) => Promise<void>
  bulkDeleteCards: (cardIds: string[]) => Promise<number>
  bulkAssignTags: (cardIds: string[], tagsToAdd: string[], tagsToRemove?: string[]) => Promise<void>
  bulkMoveToDeck: (cardIds: string[], targetDeckId: number) => Promise<void>
}

export function useBrowseCardOperations(
  options?: UseBrowseCardOperationsOptions
): UseBrowseCardOperationsReturn
```

#### Synchronization & Mutation Mechanisms
1. **TanStack Query Invalidation**: Upon any successful mutation, concurrently invalidates: `['browse', 'cards']`, `['browse', 'decks']`, and `['bootstrap']`.
2. **Session Store Sync**: Calls `updateCardFieldValuesInSessions(cardId, fieldValues)` to maintain live consistency across open study tabs.
3. **Toast Notifications**: Displays loading spinners via `toast.loading(...)` for bulk operations and replaces them with success/error toasts upon completion.

---

### Hook 4: `useCardDetailEditor`
- **Location**: `frontend/src/features/browse/hooks/useCardDetailEditor.ts`
- **Source of Extraction**: `useBrowseState.ts` (lines 325–334, 420–458, 537–589).
- **Purpose**: Manages active card inspection, form field editing, dirty-checking against initial server state, tag input, revert changes, and draft persistence.
- **Internal State Count**: **6 states** (Guaranteed `<8 states`):
  1. `activeCardId`: `string | null`
  2. `editFieldValues`: `Record<string, string>`
  3. `editDeckId`: `number | null`
  4. `editTags`: `string[]`
  5. `newTagInput`: `string`
  6. `initialSnapshot`: `{ fieldValues: Record<string, string>; deckId: number | null; tags: string[] } | null`

#### TypeScript Interface & Signature
```typescript
export interface UseCardDetailEditorOptions {
  cardId: string | null
  onDirtyChange?: (isDirty: boolean) => void
}

export interface CardDetailEditorReturn {
  activeCardId: string | null
  fieldValues: Record<string, string>
  deckId: number | null
  tags: string[]
  newTagInput: string
  isDirty: boolean
  isLoading: boolean
  setFieldValue: (fieldName: string, value: string) => void
  setDeckId: (deckId: number | null) => void
  setNewTagInput: (val: string) => void
  addTag: (tag?: string) => void
  removeTag: (tag: string) => void
  revert: () => void
  resetWithData: (data: { fieldValues: Record<string, string>; deckId: number | null; tags: string[] }) => void
}

export function useCardDetailEditor(
  options: UseCardDetailEditorOptions
): CardDetailEditorReturn
```

#### Synchronization & Mutation Mechanisms
1. **Dirty Tracking Algorithm**: Compares `editFieldValues` keys and values against `initialSnapshot.fieldValues`, as well as `editDeckId !== initialSnapshot.deckId` and sorted tag differences.
2. **Auto-Reset Sync**: When `cardId` changes, `initialSnapshot` resets, discarding stale edit state unless prompted.

---

### Hook 5: `useWorksheetStudio`
- **Location**: `frontend/src/features/worksheets/hooks/useWorksheetStudio.ts`
- **Source of Extraction**: `DeckWorksheetModal.tsx` (lines 99–120, 212–239).
- **Purpose**: Orchestrates worksheet generator wizard steps, studio tabs ('template' | 'data' | 'layout' | 'header'), mobile view responsiveness, preset persistence, and print execution.
- **Internal State Count**: **5 states** (Guaranteed `<8 states`):
  1. `wizardStep`: `'deck' | 'template' | 'mapping' | 'studio'`
  2. `activeTab`: `'template' | 'data' | 'layout' | 'header'`
  3. `mobileView`: `'controls' | 'preview'`
  4. `activePresetId`: `string | null`
  5. `isPrinting`: `boolean`

#### TypeScript Interface & Signature
```typescript
export type WizardStepId = 'deck' | 'template' | 'mapping' | 'studio'
export type StudioTab = 'template' | 'data' | 'layout' | 'header'

export interface UseWorksheetStudioOptions {
  initialDeckId?: number | null
  initialStep?: WizardStepId
  onClose?: () => void
}

export interface UseWorksheetStudioReturn {
  wizardStep: WizardStepId
  activeTab: StudioTab
  mobileView: 'controls' | 'preview'
  activePresetId: string | null
  isPrinting: boolean
  setWizardStep: (step: WizardStepId) => void
  setActiveTab: (tab: StudioTab) => void
  setMobileView: (view: 'controls' | 'preview') => void
  setActivePresetId: (id: string | null) => void
  triggerPrint: (documentTitle?: string) => Promise<void>
}

export function useWorksheetStudio(
  options?: UseWorksheetStudioOptions
): UseWorksheetStudioReturn
```

#### Synchronization & Mutation Mechanisms
1. **Print Engine Handshake**: Invokes `printWorksheet()`, toggling `isPrinting` during DOM preparation and style injection, then restoring state after print dialog closure.
2. **Mobile Viewport Detection**: Reactively adjusts `mobileView` and default layout zoom when `window.innerWidth < 768px`.

---

### Hook 6: `useWorksheetConfig`
- **Location**: `frontend/src/features/worksheets/hooks/useWorksheetConfig.ts`
- **Source of Extraction**: `DeckWorksheetModal.tsx` (lines 114–177, 240–280).
- **Purpose**: Encapsulates template configuration, note type selection, card scope filtering, field mapping, and layout options caching to prevent cross-template contamination.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `selectedTemplateId`: `string`
  2. `selectedNoteTypeId`: `string`
  3. `scope`: `'all' | 'first_n' | 'random_n' | 'selected'`
  4. `limitCount`: `number`
  5. `fieldMapping`: `WorksheetFieldMapping`
  6. `layoutOptions`: `WorksheetLayoutOptions`
  7. `templateCache`: `Record<string, { mapping: WorksheetFieldMapping; layout: WorksheetLayoutOptions }>`

#### TypeScript Interface & Signature
```typescript
export interface UseWorksheetConfigOptions {
  initialTemplateId?: string
  initialNoteTypeId?: string
  initialCardIds?: (string | number)[]
}

export interface UseWorksheetConfigReturn {
  selectedTemplateId: string
  selectedNoteTypeId: string
  scope: 'all' | 'first_n' | 'random_n' | 'selected'
  limitCount: number
  fieldMapping: WorksheetFieldMapping
  layoutOptions: WorksheetLayoutOptions
  setTemplateId: (id: string) => void
  setNoteTypeId: (id: string) => void
  setScope: (scope: 'all' | 'first_n' | 'random_n' | 'selected') => void
  setLimitCount: (limit: number) => void
  updateFieldMapping: (updates: Partial<WorksheetFieldMapping>) => void
  updateLayoutOptions: (updates: Partial<WorksheetLayoutOptions>) => void
  loadPreset: (presetId: string) => void
  resetToDefaults: () => void
}

export function useWorksheetConfig(
  options?: UseWorksheetConfigOptions
): UseWorksheetConfigReturn
```

#### Synchronization & Mutation Mechanisms
1. **Cross-Contamination Shield**: Maintains an in-memory `templateCache`. When switching from `kanji_compact` to `genkouyoushi`, caches current parameters and restores previous settings for the incoming template.
2. **Preset LocalStorage Sync**: Automatically reads/writes user presets via `loadWorksheetPreset()` and `saveWorksheetPreset()`.

---

### Hook 7: `useWorksheetPreview`
- **Location**: `frontend/src/features/worksheets/hooks/useWorksheetPreview.ts`
- **Source of Extraction**: `DeckWorksheetModal.tsx` (lines 79–89, 181–210, 240–350).
- **Purpose**: Manages live worksheet preview generation, debounced API calls, pagination navigation, fit-to-width zoom calculation, and mobile double-tap zoom gestures.
- **Internal State Count**: **5 states** (Guaranteed `<8 states`):
  1. `previewData`: `WorksheetPreviewResponse | null`
  2. `isGenerating`: `boolean`
  3. `currentPageIdx`: `number`
  4. `zoomLevel`: `number`
  5. `generationError`: `string | null`

#### TypeScript Interface & Signature
```typescript
export interface UseWorksheetPreviewOptions {
  deckId: number | null
  templateId: string
  fieldMapping: WorksheetFieldMapping
  layoutOptions: WorksheetLayoutOptions
  scope: string
  limitCount: number
  selectedCardIds?: (string | number)[]
  enabled?: boolean
}

export interface UseWorksheetPreviewReturn {
  previewData: WorksheetPreviewResponse | null
  isGenerating: boolean
  currentPageIdx: number
  totalPages: number
  zoomLevel: number
  error: string | null
  setPageIdx: (idx: number) => void
  nextPage: () => void
  prevPage: () => void
  setZoomLevel: (zoom: number | ((prev: number) => number)) => void
  fitToScreen: () => void
  handleCanvasTouchEnd: (e: React.TouchEvent) => void
  refreshPreview: () => Promise<void>
}

export function useWorksheetPreview(
  options: UseWorksheetPreviewOptions
): UseWorksheetPreviewReturn
```

#### Synchronization & Mutation Mechanisms
1. **Debounced Generator API**: Buffers changes to `layoutOptions` and `fieldMapping` by `350ms` before dispatching `generateWorksheetPreview()` to prevent server load.
2. **Double-Tap Canvas Gesture**: Tracks touch timestamp delta (<300ms) on mobile canvas to toggle between 100% zoom and responsive fit zoom.
3. **Dynamic A4 Zoom**: Calculates exact zoom factor based on `window.innerWidth` and A4 aspect ratio (portrait vs landscape).

---

### Hook 8: `useAudioPlayer`
- **Location**: `frontend/src/shared/hooks/useAudioPlayer.ts`
- **Source of Extraction**: `useBrowseState.ts` (lines 807–849), `useLocalAudioEngine.ts` (lines 805–820), `DeckAudioRuleCard.tsx` (lines 245–255).
- **Purpose**: Unified headless HTML5 Audio playback engine. Handles audio asset loading, play/pause, volume/mute, duration/currentTime tracking, progress percentage, error states, and unmount blob cleanup.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `playbackState`: `'idle' | 'loading' | 'playing' | 'paused' | 'error'`
  2. `currentUrl`: `string | null`
  3. `currentTime`: `number`
  4. `duration`: `number`
  5. `volume`: `number` (0 to 1)
  6. `isMuted`: `boolean`
  7. `errorMessage`: `string | null`

#### TypeScript Interface & Signature
```typescript
export interface UseAudioPlayerOptions {
  initialVolume?: number
  onPlay?: () => void
  onPause?: () => void
  onEnded?: () => void
  onError?: (error: Error) => void
}

export interface UseAudioPlayerReturn {
  playbackState: 'idle' | 'loading' | 'playing' | 'paused' | 'error'
  isPlaying: boolean
  isLoading: boolean
  currentUrl: string | null
  currentTime: number
  duration: number
  progress: number // 0 to 100
  volume: number
  isMuted: boolean
  error: string | null
  play: (url?: string) => Promise<void>
  pause: () => void
  togglePlay: () => void
  seek: (seconds: number) => void
  setVolume: (val: number) => void
  toggleMute: () => void
  stop: () => void
}

export function useAudioPlayer(
  options?: UseAudioPlayerOptions
): UseAudioPlayerReturn
```

#### Synchronization & Mutation Mechanisms
1. **Audio Element Lifecycle**: Manages a singleton `HTMLAudioElement` stored in a `ref`. Attaches `timeupdate`, `loadedmetadata`, `ended`, `error`, `play`, `pause` listeners.
2. **Blob URL Revocation**: Tracks dynamic object URLs (`URL.createObjectURL(blob)`) and automatically calls `URL.revokeObjectURL(url)` on stop or unmount to eliminate memory leaks.
3. **Concurrent Playback Guard**: Calling `play(newUrl)` pauses and cleans up any currently playing audio stream immediately.

---

### Hook 9: `useMcpTokens`
- **Location**: `frontend/src/features/settings/hooks/useMcpTokens.ts`
- **Source of Extraction**: `AdminMcpTokensPage.tsx` (lines 98–210) & `useMcpTokenCRUD.ts` (lines 140–250).
- **Purpose**: Token list querying, issuance dialog state, token rotation, token revocation, clipboard copy with ephemeral feedback, and policy validation.
- **Internal State Count**: **4 states** (Guaranteed `<8 states`):
  1. `issuedToken`: `McpTokenItem | null` (newly issued token with secret visible once)
  2. `copiedKey`: `string | null` (ephemeral feedback indicator)
  3. `searchFilter`: `string`
  4. `statusFilter`: `'all' | 'active' | 'revoked' | 'expired'`

#### TypeScript Interface & Signature
```typescript
export interface IssueTokenParams {
  name: string
  expiryDays: number | null
  scopes: string[]
}

export interface UseMcpTokensReturn {
  tokens: McpTokenItem[]
  policy: McpPolicy | undefined
  isLoading: boolean
  issuedToken: McpTokenItem | null
  copiedKey: string | null
  searchFilter: string
  statusFilter: string
  setSearchFilter: (query: string) => void
  setStatusFilter: (status: 'all' | 'active' | 'revoked' | 'expired') => void
  issueToken: (params: IssueTokenParams) => Promise<McpTokenItem>
  rotateToken: (tokenId: number, expiryDays: number | null) => Promise<McpTokenItem>
  revokeToken: (tokenId: number) => Promise<void>
  purgeInactiveTokens: () => Promise<number>
  copyToClipboard: (text: string, keyIdentifier: string) => Promise<boolean>
  clearIssuedToken: () => void
  refetch: () => Promise<void>
}

export function useMcpTokens(): UseMcpTokensReturn
```

#### Synchronization & Mutation Mechanisms
1. **Clipboard Sync with Auto-Reset**: `copyToClipboard()` copies text to `navigator.clipboard` and sets `copiedKey`, clearing it automatically via `setTimeout` after `2000ms`.
2. **TanStack Cache Sync**: Automatically invalidates `['mcp-tokens']` and `['admin-mcp-summary']` on create/rotate/revoke.

---

### Hook 10: `useTaxonomyManager`
- **Location**: `frontend/src/features/admin/hooks/useTaxonomyManager.ts`
- **Source of Extraction**: `AdminTaxonomyPage.tsx` (lines 98–180).
- **Purpose**: Admin taxonomy tree exploration, entity CRUD dialog states, active category filtering, search queries, and subject-to-option relationship mapping.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `activeTab`: `'domains' | 'subjects' | 'frameworks' | 'options' | 'mappings'`
  2. `searchQuery`: `string`
  3. `filterDomainId`: `string` ('all' or ID)
  4. `filterSubjectId`: `string` ('all' or ID)
  5. `filterOptionType`: `string` ('all' or key)
  6. `editingEntity`: `TaxonomyEntityDescriptor | null`
  7. `isModalOpen`: `boolean`

#### TypeScript Interface & Signature
```typescript
export type TaxonomyTab = 'domains' | 'subjects' | 'frameworks' | 'options' | 'mappings'

export interface TaxonomyEntityDescriptor {
  type: 'domain' | 'subject' | 'framework' | 'level' | 'option'
  data?: any
  isNew?: boolean
}

export interface UseTaxonomyManagerReturn {
  activeTab: TaxonomyTab
  searchQuery: string
  filterDomainId: string
  filterSubjectId: string
  filterOptionType: string
  editingEntity: TaxonomyEntityDescriptor | null
  isModalOpen: boolean
  setActiveTab: (tab: TaxonomyTab) => void
  setSearchQuery: (query: string) => void
  setFilterDomainId: (id: string) => void
  setFilterSubjectId: (id: string) => void
  setFilterOptionType: (type: string) => void
  openCreateModal: (type: TaxonomyEntityDescriptor['type']) => void
  openEditModal: (type: TaxonomyEntityDescriptor['type'], entity: any) => void
  closeModal: () => void
  saveEntity: (data: any) => Promise<void>
  deleteEntity: (type: string, id: string) => Promise<void>
}

export function useTaxonomyManager(): UseTaxonomyManagerReturn
```

#### Synchronization & Mutation Mechanisms
1. **Query Cache Pipeline**: Mutating any taxonomy entity triggers targeted cache invalidation: `['taxonomy', 'domains']`, `['taxonomy', 'subjects']`, `['taxonomy', 'frameworks']`, `['taxonomy-schema']`.
2. **Safe Entity Reset**: Closing the modal automatically purges `editingEntity` to avoid data contamination when opening the next entity.

---

### Hook 11: `useStudySession`
- **Location**: `frontend/src/features/study/hooks/useStudySession.ts`
- **Source of Extraction**: `features/study/hooks/useStudySession.ts` (lines 130–280).
- **Purpose**: Core SRS review session lifecycle: lease acquisition, session bootstrap, queue viewing, local snapshot persistence, background sync, and batch exit commit.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `session`: `PersistedStudySession | null`
  2. `loading`: `boolean`
  3. `busy`: `boolean`
  4. `error`: `unknown | null`
  5. `compositionGroups`: `StudyCompositionGroup[]`
  6. `selectedCompositionId`: `string | null`
  7. `receipt`: `StudySessionCommitReceipt | null`

#### TypeScript Interface & Signature
```typescript
export interface UseStudySessionReturn {
  session: PersistedStudySession | null
  loading: boolean
  busy: boolean
  error: unknown | null
  compositionGroups: StudyCompositionGroup[]
  selectedCompositionId: string | null
  receipt: StudySessionCommitReceipt | null
  view: ReturnType<typeof buildSessionView> | null
  hasLease: boolean
  selectComposition: (compositionId: string) => Promise<void>
  answerCard: (action: ReviewAction, rating: ReviewRating) => Promise<void>
  undo: () => Promise<void>
  commit: (options?: { reason?: StudyCommitReason }) => Promise<StudySessionCommitReceipt | null>
  requestTakeover: () => Promise<void>
  forceTakeover: () => Promise<void>
}

export function useStudySession(
  deckId: string | null
): UseStudySessionReturn
```

#### Synchronization & Mutation Mechanisms
1. **Distributed Lease Guard**: Leverages `useStudySessionLease` to maintain exclusive write access across browser tabs.
2. **Network Offline Durability**: Binds `online` event to retry uncommitted review queues when internet restores.
3. **Exit Beacon Flush**: Utilizes `flushNoteBatchStream` on page exit (`beforeunload`) to persist study progress without data loss.

---

### Hook 12: `useStudyInteraction`
- **Location**: `frontend/src/features/study/hooks/useStudyInteraction.ts`
- **Source of Extraction**: `StudyPage.tsx` (lines 25–120).
- **Purpose**: Manages review interaction state: card flip / answer reveal, keyboard shortcut bindings (Space, 1-4), answer duration timer, and fullscreen toggling.
- **Internal State Count**: **5 states** (Guaranteed `<8 states`):
  1. `isAnswerRevealed`: `boolean`
  2. `revealedCardKey`: `string | null`
  3. `pendingDecision`: `SchedulerDecision | null`
  4. `isFullscreen`: `boolean`
  5. `elapsedSeconds`: `number`

#### TypeScript Interface & Signature
```typescript
export interface UseStudyInteractionOptions {
  cardKey: string | null
  onAnswer: (rating: 'again' | 'hard' | 'good' | 'easy') => Promise<void>
  enabled?: boolean
}

export interface UseStudyInteractionReturn {
  isAnswerRevealed: boolean
  isFullscreen: boolean
  elapsedSeconds: number
  revealAnswer: () => void
  submitRating: (rating: 'again' | 'hard' | 'good' | 'easy') => Promise<void>
  toggleFullscreen: () => void
  resetCardInteraction: () => void
}

export function useStudyInteraction(
  options: UseStudyInteractionOptions
): UseStudyInteractionReturn
```

#### Synchronization & Mutation Mechanisms
1. **Keyboard Shortcut Engine**:
   - `Space` / `Enter`: If card is hidden, reveals the answer. If already revealed, triggers default rating (`Good`).
   - `1` = Again, `2` = Hard, `3` = Good, `4` = Easy.
   - Bypasses shortcuts if focus is inside an editable field or modal dialog.
2. **Fullscreen API Integration**: Synchronizes state with `document.fullscreenElement` and listens to `fullscreenchange` events.

---

### Hook 13: `useMarketplaceSearch`
- **Location**: `frontend/src/features/marketplace/hooks/useMarketplaceSearch.ts`
- **Source of Extraction**: `MarketplacePages.tsx` (lines 228–340).
- **Purpose**: Search query debouncing, category tabs, taxonomy facet filtering (domain/subject/level/difficulty), pricing filters, sort order, URL synchronization, and 1-click deck installation.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `queryText`: `string`
  2. `debouncedQuery`: `string`
  3. `sortView`: `'recommended' | 'newest' | 'popular'`
  4. `categoryFilter`: `string`
  5. `taxonomyFilter`: `{ domain: string; subject: string; level: string; difficulty: string }`
  6. `pricingFilter`: `'all' | 'free' | 'paid'`
  7. `isFilterExpanded`: `boolean`

#### TypeScript Interface & Signature
```typescript
export interface UseMarketplaceSearchOptions {
  mode: 'decks' | 'note-types'
  syncUrl?: boolean
}

export interface UseMarketplaceSearchReturn {
  queryText: string
  debouncedQuery: string
  sortView: 'recommended' | 'newest' | 'popular'
  categoryFilter: string
  taxonomyFilter: { domain: string; subject: string; level: string; difficulty: string }
  pricingFilter: 'all' | 'free' | 'paid'
  isFilterExpanded: boolean
  items: MarketplaceItem[]
  isLoading: boolean
  isInstalling: boolean
  setQueryText: (text: string) => void
  setSortView: (sort: 'recommended' | 'newest' | 'popular') => void
  setCategoryFilter: (category: string) => void
  setTaxonomyFilter: (updates: Partial<UseMarketplaceSearchReturn['taxonomyFilter']>) => void
  setPricingFilter: (pricing: 'all' | 'free' | 'paid') => void
  toggleFilterExpanded: () => void
  resetFilters: () => void
  installDeck: (deckId: string) => Promise<number | null>
}

export function useMarketplaceSearch(
  options: UseMarketplaceSearchOptions
): UseMarketplaceSearchReturn
```

#### Synchronization & Mutation Mechanisms
1. **Debounced Search Buffer**: Buffers keyboard input by `250ms` before querying API.
2. **Slash `/` Shortcut**: Binds window keydown `/` to focus the marketplace search input box.
3. **URL State Reflection**: Mirrors `q`, `category`, `domain`, `sort` to URL query params when `syncUrl: true`.
4. **Overlay Install Mutation**: Invokes `/marketplace/decks/:id/install`, invalidating user decks on success.

---

### Hook 14: `useDeckExportImport`
- **Location**: `frontend/src/features/import/hooks/useDeckExportImport.ts`
- **Source of Extraction**: `useFileImportWizard.ts` (lines 100–165).
- **Purpose**: File import/export wizard: drag-and-drop file ingestion, delimiter detection (CSV, TSV, custom), server column parsing, mapping heuristics, upsert option config, and execution progress tracking.
- **Internal State Count**: **7 states** (Guaranteed `<8 states`):
  1. `wizardStep`: `'file' | 'mapping' | 'options' | 'report'`
  2. `fileMeta`: `{ files: File[]; delimiter: 'csv' | 'tsv' | 'custom'; customDelimiter: string; hasHeader: boolean; isDragOver: boolean }`
  3. `parseResult`: `ParseResponse | null`
  4. `targetSelection`: `{ deckId: string; noteTypeId: string }`
  5. `fieldMapping`: `Record<string, FieldMapping>`
  6. `importOptions`: `{ mode: 'insert_only' | 'update_only' | 'upsert'; dontOverwriteEmpty: boolean; uniquenessFields: string[] }`
  7. `executionReport`: `{ report: ImportReport | null; isExecuting: boolean; isDone: boolean }`

#### TypeScript Interface & Signature
```typescript
export interface UseDeckExportImportOptions {
  initialDeckId?: string | null
}

export interface UseDeckExportImportReturn {
  wizardStep: 'file' | 'mapping' | 'options' | 'report'
  files: File[]
  isDragOver: boolean
  parseResult: ParseResponse | null
  targetSelection: { deckId: string; noteTypeId: string }
  fieldMapping: Record<string, FieldMapping>
  importOptions: { mode: 'insert_only' | 'update_only' | 'upsert'; dontOverwriteEmpty: boolean; uniquenessFields: string[] }
  executionReport: { report: ImportReport | null; isExecuting: boolean; isDone: boolean }
  setWizardStep: (step: 'file' | 'mapping' | 'options' | 'report') => void
  handleFileDrop: (droppedFiles: FileList | File[]) => void
  setDelimiter: (mode: 'csv' | 'tsv' | 'custom', customVal?: string) => void
  setTargetDeckAndNoteType: (deckId: string, noteTypeId: string) => void
  updateFieldMapping: (fieldName: string, mapping: FieldMapping) => void
  setImportMode: (mode: 'insert_only' | 'update_only' | 'upsert') => void
  executeImport: () => Promise<void>
  resetWizard: () => void
}

export function useDeckExportImport(
  options?: UseDeckExportImportOptions
): UseDeckExportImportReturn
```

#### Synchronization & Mutation Mechanisms
1. **Drag & Drop Listeners**: Manages HTML5 Drag and Drop events (`dragover`, `dragleave`, `drop`) with visual indicator states.
2. **Server-Side Tokenized Parsing**: Dispatches file to `/flashcards/import/parse` to retrieve parsed preview rows and suggested column mappings.
3. **TanStack Cache Cleansing**: Invalidates decks and notes collections after successful batch ingestion.

---

# 5. R4: Deep Decomposition of the 4 Key God Components

## 5.1 Deep Dive: `DeckWorksheetModal.tsx` (~4,388 LOC)

### Current Anatomy & Structural Issues
`DeckWorksheetModal.tsx` houses an entire desktop publishing suite within a single 4,388-line file. It maintains 21 states, 5 refs, 3 effects, 3 useMemos, a 4-step wizard router, 4 studio tabs, 8 specialized worksheet template layout configurations (~2,450 lines of inline layout forms), live print engine integration, and canvas zoom/touch logic.

### ASCII Component Trees: Before vs After

#### Before: Monolithic Component Tree
```
DeckWorksheetModal (4,388 LOC)
├── [Dialog & DialogContent Shell]
│   ├── [Desktop Header: Title, Breadcrumbs, Zoom Controls, Print Button, Close] (150 LOC)
│   ├── [Mobile Header: Branding, Title, Mobile Actions] (98 LOC)
│   ├── [Step 1: WorksheetDeckSelectStep]
│   ├── [Step 2: WorksheetFieldMappingStep]
│   ├── [Step 3: WorksheetTemplateSelectStep]
│   └── [Step 4: Live Studio Workspace] (3,485 LOC)
│       ├── <aside> Studio Sidebar Controls (3,295 LOC)
│       │   ├── Quick Wizard Jump Bar (35 LOC)
│       │   ├── Locale Switcher (42 LOC)
│       │   ├── Studio Tab Switcher Bar (38 LOC)
│       │   ├── [activeTab === 'template'] Inline Template Grid & Presets (98 LOC)
│       │   ├── [activeTab === 'data'] Inline Field Mapping & Card Scope (358 LOC)
│       │   ├── [activeTab === 'layout'] Enormous Inline Layout Forms (2,452 LOC)
│       │   │   ├── Base Paper, Orientation, Margins, Density (240 LOC)
│       │   │   ├── Kanji Stroke & Box Size Controls (1,244 LOC)
│       │   │   ├── Vocab Practice & Recall Controls (205 LOC)
│       │   │   ├── Deck Table Column Checkboxes (198 LOC)
│       │   │   ├── Sentence Writing Controls (161 LOC)
│       │   │   ├── Grammar Practice Controls (144 LOC)
│       │   │   └── Genkouyoushi 400-Char Controls (252 LOC)
│       │   └── [activeTab === 'header'] Inline Title, Watermark, Student Info (255 LOC)
│       └── <main> Live Preview Canvas (185 LOC)
│           ├── Workbench Top Bar: Page Nav, Zoom Bar, Item Stats (55 LOC)
│           ├── Zoom Viewport: transform scale wrapper (90 LOC)
│           │   └── WorksheetPageRenderer (sub-component)
│           └── Mobile Bottom Floating Print Bar (40 LOC)
```

#### After: Feature-Sliced Decomposed Component Tree
```
frontend/src/features/worksheets/
├── hooks/
│   └── useWorksheetStudio.ts               # Headless Studio state, debounced preview, print, cache (~280 LOC)
├── components/
│   ├── DeckWorksheetModal.tsx             # Orchestrator & Step Router Shell (~140 LOC)
│   ├── modal/
│   │   ├── WorksheetModalHeader.tsx        # Desktop & Mobile Header with zoom & print (~180 LOC)
│   │   └── WorksheetPreviewCanvas.tsx      # Canvas viewport, scale transform, pagination (~175 LOC)
│   └── studio/
│       ├── WorksheetStudioSidebar.tsx      # Sidebar container, nav jump, tab list (~120 LOC)
│       ├── tabs/
│       │   ├── StudioTemplateTab.tsx       # Template grid & quick preset selector (~95 LOC)
│       │   ├── StudioDataTab.tsx           # Field mapping slot dropdowns & note scope (~190 LOC)
│       │   ├── StudioHeaderTab.tsx         # Document titles, subtitle, student info, watermark (~160 LOC)
│       │   └── StudioLayoutTab.tsx         # Tab container delegating to template panels (~120 LOC)
│       └── panels/
│           ├── BaseLayoutControls.tsx      # Paper size, orientation, margin, density (~150 LOC)
│           ├── KanjiLayoutControls.tsx     # Stroke diagram, trace count, grid cross/diagonal (~280 LOC)
│           ├── VocabLayoutControls.tsx     # Practice lines, recall mode, hints (~160 LOC)
│           ├── SentenceLayoutControls.tsx  # Writing lines, exercise prompt (~140 LOC)
│           ├── GenkouyoushiControls.tsx    # 400-char grid, spacer bands, title style (~180 LOC)
│           └── DeckTableLayoutControls.tsx # Custom column selectors, table density (~150 LOC)
```

### LOC Reduction Breakdown
| File Name | Responsibility | Before LOC | After LOC | Reduction |
|---|---|---|---|---|
| `DeckWorksheetModal.tsx` | Dialog container, step router, modal open/close | 4,388 | 140 | **-96.8%** |
| `useWorksheetStudio.ts` | All 21 states, refs, debounced generator, print handler | — | 280 | *New Hook* |
| `WorksheetModalHeader.tsx` | Desktop & Mobile headers, zoom preset buttons, print trigger | — | 180 | *Extracted* |
| `WorksheetPreviewCanvas.tsx` | Scrollable viewport, `scale()` transform, page nav | — | 175 | *Extracted* |
| `WorksheetStudioSidebar.tsx` | Sidebar container, step jump bar, tab bar | — | 120 | *Extracted* |
| `StudioTemplateTab.tsx` | Tab 1: Template selection & presets | — | 95 | *Extracted* |
| `StudioDataTab.tsx` | Tab 2: Scope, limit count, field mapping slots | — | 190 | *Extracted* |
| `StudioHeaderTab.tsx` | Tab 4: Titles, watermark, student headers | — | 160 | *Extracted* |
| `StudioLayoutTab.tsx` | Tab 3: Template panel router & general settings | — | 120 | *Extracted* |
| `BaseLayoutControls.tsx` | General paper, orientation, margins | — | 150 | *Extracted* |
| `KanjiLayoutControls.tsx` | Kanji-specific stroke & grid settings | — | 280 | *Extracted* |
| `VocabLayoutControls.tsx` | Vocab-specific practice settings | — | 160 | *Extracted* |
| `SentenceLayoutControls.tsx` | Sentence prompts & writing guides | — | 140 | *Extracted* |
| `GenkouyoushiControls.tsx` | Manuscript grid & essay settings | — | 180 | *Extracted* |
| `DeckTableLayoutControls.tsx`| Table column selector & borders | — | 150 | *Extracted* |
| **Total Worksheet Subsystem**| | **4,388** | **2,520** | **-42.6% (-1,868 LOC)** |

---

## 5.2 Deep Dive: `AdminTaxonomyPage.tsx` (~1,400 LOC, 46 States)

### Current Anatomy & Structural Issues
`AdminTaxonomyPage.tsx` holds 46 distinct `useState` declarations hoisted directly at the top of the root component. Keystrokes in modal input fields (e.g. typing a domain label or level difficulty) trigger re-renders of the entire 1,400-line DOM tree, including all 5 active React Query caches.

### ASCII Component Trees: Before vs After

#### Before: Monolithic Admin Page
```
AdminTaxonomyPage (1,400 LOC, 46 states)
├── Top Page Header + "Reseed Defaults" Mutation Button
├── Search & Filter Card (3 Selects + 1 Search Input)
├── <Tabs> Container
│   ├── <TabsList> 5 Tabs Triggers
│   ├── <TabsContent value="domains"> Domain Table & Inline Rows (42 LOC)
│   ├── <TabsContent value="subjects"> Subject Table & Inline Rows (61 LOC)
│   ├── <TabsContent value="frameworks"> Framework & Level Nested Tables (111 LOC)
│   ├── <TabsContent value="options"> Option Grid Cards (60 LOC)
│   └── <TabsContent value="mappings"> Checkbox Matrix for Subject Options (116 LOC)
├── <Dialog> Domain Modal (ID, Label, Sort, Active) (42 LOC)
├── <Dialog> Subject Modal (Domain Select, ID, Label, Sort, Active) (55 LOC)
├── <Dialog> Framework Modal (Subject Select, ID, Label, Sort, Active) (55 LOC)
├── <Dialog> Level Modal (Framework Select, Difficulty Select, ID, Label, Sort) (55 LOC)
└── <Dialog> Option Modal (Type Select, SubLabel, ID, Label, Sort, Active) (47 LOC)
```

#### After: Clean FSD Tab & Generic Entity Modal Architecture
```
frontend/src/features/admin/
├── hooks/
│   └── useTaxonomyData.ts                 # React Query queries, invalidations, reseed mutation (~110 LOC)
├── components/taxonomy/
│   ├── TaxonomyEntityModal.tsx            # Unified form modal with schema-driven fields (~130 LOC)
│   ├── TaxonomyDomainsTab.tsx             # Domain list, local modal state, create/edit/delete (~120 LOC)
│   ├── TaxonomySubjectsTab.tsx            # Subject list with Domain filter, local modal state (~140 LOC)
│   ├── TaxonomyFrameworksTab.tsx          # Framework & Level accordion lists (~160 LOC)
│   ├── TaxonomyOptionsTab.tsx             # Option pills/grid categorized by type (~130 LOC)
│   └── TaxonomySubjectMappingsTab.tsx     # Subject-to-option checkbox matrix (~120 LOC)
└── pages/
    └── AdminTaxonomyPage.tsx              # Root Page wrapper with 1 state (activeTab) (~95 LOC)
```

### Unified `TaxonomyEntityModal.tsx` Design
Instead of 5 copy-pasted `<Dialog>` elements, a single generic component renders typed entity forms:
```typescript
export interface TaxonomyFormFieldDef {
  name: string
  label: string
  type: 'text' | 'number' | 'switch' | 'select'
  placeholder?: string
  options?: { value: string; label: string }[]
  required?: boolean
  disabled?: boolean
  description?: string
}

export interface TaxonomyEntityModalProps<T> {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  entity: T | null
  fields: TaxonomyFormFieldDef[]
  initialValues: Record<string, any>
  onSubmit: (values: Record<string, any>) => Promise<void>
  isSaving: boolean
}
```

### LOC Reduction Breakdown
| File Name | Responsibility | Before LOC | After LOC | Reduction |
|---|---|---|---|---|
| `AdminTaxonomyPage.tsx` | Page wrapper, header, tab switcher | 1,400 | 95 | **-93.2%** |
| `useTaxonomyData.ts` | Data fetching, invalidations, reseed | — | 110 | *New Hook* |
| `TaxonomyEntityModal.tsx` | Reusable entity create/edit modal dialog | — | 130 | *New Shared Component* |
| `TaxonomyDomainsTab.tsx` | Domains management tab | — | 120 | *Extracted* |
| `TaxonomySubjectsTab.tsx` | Subjects management tab | — | 140 | *Extracted* |
| `TaxonomyFrameworksTab.tsx`| Frameworks and Levels tab | — | 160 | *Extracted* |
| `TaxonomyOptionsTab.tsx` | Taxonomy options tab | — | 130 | *Extracted* |
| `TaxonomySubjectMappingsTab.tsx`| Subject-to-Option mappings tab | — | 120 | *Extracted* |
| **Total Taxonomy Subsystem**| | **1,400** | **1,005** | **-28.2% (-395 LOC)** |

*Root component state count drops from **46 states to 1 state**.*

---

## 5.3 Deep Dive: `AdminMcpTokensPage.tsx` & `McpTokensTab.tsx` (~2,586 Combined LOC)

### Line-by-Line Duplication Analysis
- `AdminMcpTokensPage.tsx` (1,405 LOC) and `McpTokensTab.tsx` (1,181 LOC) independently implement the exact same 7 modal dialogs and token data table:
  1. Secret Issued Token Modal (100% duplicate, ~80 LOC)
  2. Create Token Dialog (95% duplicate, ~160 LOC)
  3. Edit Token & Scopes Dialog (100% duplicate, ~120 LOC)
  4. Rotate Token Dialog (100% duplicate, ~35 LOC)
  5. Revoke Confirmation Dialog (100% duplicate, ~12 LOC)
  6. Purge Confirmation Dialog (100% duplicate, ~15 LOC)
  7. Cleanup Expired Dialog (100% duplicate, ~15 LOC)
  8. Token Table with Status Pills & Usage Bar (90% duplicate, ~250 LOC)
  9. Duplicate Mutation Logic (~60 LOC)

### ASCII Component Trees: Before vs After

#### Before: Dual Duplicated Monoliths
```
Admin Route: /admin/mcp-tokens                 User Route: /settings/mcp
AdminMcpTokensPage (1,405 LOC)                McpTokensPage (211 LOC)
├── Stat Cards (40 LOC)                        ├── Tabs Header (ChatGPT vs Tokens)
├── Users Tab (Admin only) (280 LOC)           └── McpTokensTab (1,181 LOC)
├── Tokens Tab (Table & Controls) (300 LOC)        ├── Stat Cards (50 LOC)
├── [Duplicate Dialog 1: Issued Token]             ├── Inline Create Card & Presets (200 LOC)
├── [Duplicate Dialog 2: Create Token]             ├── Tokens Table (300 LOC)
├── [Duplicate Dialog 3: Edit Token]               ├── [Duplicate Dialog 1: Issued Token]
├── [Duplicate Dialog 4: Rotate Token]             ├── [Duplicate Dialog 3: Edit Token]
├── [Duplicate Dialog 5: Revoke Token]             ├── [Duplicate Dialog 4: Rotate Token]
├── [Duplicate Dialog 6: Purge Token]              ├── [Duplicate Dialog 5: Revoke Token]
└── [Duplicate Dialog 7: Cleanup Expired]          ├── [Duplicate Dialog 6: Purge Token]
                                                   └── [Duplicate Dialog 7: Cleanup Expired]
```

#### After: Single Unified Engine
```
frontend/src/features/mcp/ (or features/settings/components/mcp/)
├── hooks/
│   └── useMcpTokens.ts                     # Unified user/admin tokens query & mutations (~240 LOC)
├── components/
│   ├── McpTokensManager.tsx                # Unified Manager (mode="user" | "admin") (~160 LOC)
│   ├── McpTokenTable.tsx                   # Responsive token list with conditional user col (~220 LOC)
│   ├── McpTokenSecretModal.tsx             # Issued token secret & client setup guides (~130 LOC)
│   ├── McpCreateEditTokenModal.tsx         # Create & Edit modal with scope categories (~250 LOC)
│   └── McpTokenActionModals.tsx            # Rotate, Revoke, Purge, Cleanup dialogs (~140 LOC)
│
Consumers:
├── AdminMcpTokensPage.tsx                  # Reduced to: Stat cards + UsersTab + <McpTokensManager mode="admin" /> (~180 LOC)
├── McpTokensTab.tsx                        # Reduced to: <McpTokensManager mode="user" /> (~40 LOC)
└── McpTokensPage.tsx                       # Preserved clean page wrapper (~160 LOC)
```

### LOC Reduction Breakdown
| File Name | Before LOC | After LOC | Net LOC Change |
|---|---|---|---|
| `AdminMcpTokensPage.tsx` | 1,405 | 180 | **-1,225 LOC** |
| `McpTokensTab.tsx` | 1,181 | 40 | **-1,141 LOC** |
| `McpTokensPage.tsx` | 211 | 160 | **-51 LOC** |
| `useMcpTokenCRUD.ts` (replaced by `useMcpTokens.ts`) | 416 | 240 | **-176 LOC** |
| `McpTokensManager.tsx` (new) | — | 160 | +160 LOC |
| `McpTokenTable.tsx` (new) | — | 220 | +220 LOC |
| `McpTokenSecretModal.tsx` (new) | — | 130 | +130 LOC |
| `McpCreateEditTokenModal.tsx` (new) | — | 250 | +250 LOC |
| `McpTokenActionModals.tsx` (new) | — | 140 | +140 LOC |
| **Total MCP Subsystem** | **3,213** | **1,520** | **-52.7% (-1,693 LOC)** |

---

## 5.4 Deep Dive: `useBrowseState.ts` (~1,053 LOC, 49 States, 102 Return Properties)

### Current Anatomy & Structural Issues
`useBrowseState.ts` acts as a global sink for the entire browse experience, combining 49 states into a single hook returning 102 properties and functions. It couples card search, table pagination, multi-card selection, active card dirty-tracking, note creation, batch operations, worksheet launching, and **24 dedicated states for VoiceVox/Kokoro TTS audio generation**.

### Decomposed Facade Architecture
To adhere to the `<8 states per hook` rule while preserving 100% backward compatibility for all child components, `useBrowseState.ts` is structured as a **Master Facade** coordinating 4 specialized sub-hooks plus a dedicated audio modal hook:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   useBrowseState() [Master Facade]                     │
│               Maintains 100% Return Type Compatibility                 │
└──────┬──────────────────┬──────────────────┬──────────────────┬────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│useBrowse-    │   │useBrowse-    │   │useBrowse-    │   │useBrowseCard-│
│Filters       │   │Pagination    │   │Selection     │   │Operations    │
│(5 states)    │   │(2 states)    │   │(1 state)     │   │(8 states)    │
└──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
                                                                │
                                                                ▼
                                                         ┌──────────────┐
                                                         │useBrowse-    │
                                                         │AudioModal    │
                                                         │(TTS/Stroke)  │
                                                         └──────────────┘
```

### Master Facade Code Contract (`useBrowseState.ts`, ~85 LOC)
```typescript
export function useBrowseState() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const bootstrapQuery = useQuery({ queryKey: ['bootstrap'], queryFn: () => appApi.getBootstrap() })
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  const pagination = useBrowsePagination()
  const filters = useBrowseFilters({ onQueryChange: pagination.resetPage })

  const cardsQuery = useQuery({
    queryKey: ['browse', 'cards', filters.debouncedQuery, filters.selectedDeckId, filters.statusFilter, filters.sortBy, filters.sortDir, pagination.page, pagination.perPage],
    queryFn: () => appApi.get<BrowseCardsResponse>('/browse/cards', {
      q: filters.debouncedQuery,
      deck_id: filters.selectedDeckId !== null ? filters.selectedDeckId : '',
      status: filters.statusFilter,
      sort_by: filters.sortBy,
      sort_dir: filters.sortDir,
      page: pagination.page,
      per_page: pagination.perPage,
    }),
  })
  const cards = cardsQuery.data?.items || []

  const selection = useBrowseSelection(cards)
  const operations = useBrowseCardOperations({ selectedDeckId: filters.selectedDeckId, cards })
  const audio = useBrowseAudioModal({
    selectedCards: selection.selectedCards,
    activeCardId: operations.activeCardId,
    effectiveCardDetail: operations.cardDetailQuery.data,
    cards,
  })

  // Worksheet modal state (3 states)
  const [isWorksheetModalOpen, setIsWorksheetModalOpen] = useState(false)
  const [worksheetTargetDeckId, setWorksheetTargetDeckId] = useState<number | null>(null)
  const [worksheetTargetCardIds, setWorksheetTargetCardIds] = useState<string[] | undefined>(undefined)

  return {
    navigate,
    queryClient,
    isAdmin,
    ...filters,
    ...pagination,
    ...selection,
    ...operations,
    ...audio,
    cards,
    cardsQuery,
    isWorksheetModalOpen,
    setIsWorksheetModalOpen,
    worksheetTargetDeckId,
    setWorksheetTargetDeckId,
    worksheetTargetCardIds,
    setWorksheetTargetCardIds,
  }
}
```

### LOC Reduction Breakdown
| Hook Module | Purpose | Before LOC | After LOC | States |
|---|---|---|---|---|
| `useBrowseState.ts` (Master facade) | Coordinator facade, 100% backward compatibility | 1,053 | 85 | 3 |
| `useBrowseFilters.ts` | Filter, search debounce, deck tree sync | — | 145 | 5 |
| `useBrowsePagination.ts` | Page, perPage, localStorage sync | — | 55 | 2 |
| `useBrowseSelection.ts` | Selected cards, select all, hotkeys | — | 80 | 1 |
| `useBrowseCardOperations.ts` | Active card, edit field values, dirty tracking, mutations | — | 290 | 8 |
| `useBrowseAudioModal.ts` | VoiceVox/Kokoro TTS settings, preview, mutations | — | 250 | 18 |
| **Total Browse Hook Subsystem** | | **1,053** | **905** | **Max 8 per core hook** |

---

# 6. R5: Zero Visual Regression & Logic Preservation Standards

```
┌────────────────────────────────────────────────────────────────────────┐
│               ZERO VISUAL REGRESSION & LOGIC STANDARDS                 │
├──────────────────────────────────┬─────────────────────────────────────┤
│  1. Layout & Box Model Invariance│  2. Radix UI Context Safety         │
│  • 100% Margin/Padding Preserved │  • Dialog/Dropdown Context Intact   │
│  • Brand OKLCH Palette Untouched │  • Focus Traps & ARIA Maintained    │
│  • Strict Ban on Wrapper <div>s  │  • Keyboard Shortcuts Protected     │
├──────────────────────────────────┼─────────────────────────────────────┤
│  3. Chrome DevTools Profile      │  4. Quality Acceptance Gates        │
│  • Isolated User Data Directory  │  • CLS = 0.0000 Layout Shift Gate   │
│  • Network Waterfall Inspection  │  • Vitest JSDOM Behavioral Suites   │
│  • React Profiler Render Counts  │  • TypeScript Zero Any Policy       │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 6.1 Layout & Box Model Invariance Rules

1. **Zero Modifications to CSS Spacing & Typography**:
   - Margin, padding, and border dimensions must remain byte-for-byte identical (e.g., `p-4`, `px-3`, `py-2`, `gap-2`, `m-0`).
   - Font sizes (`text-xs`, `text-sm`, `text-base`), weights (`font-medium`, `font-semibold`), and line heights (`leading-none`, `leading-tight`) must not be altered.
2. **Brand OKLCH Color Fidelity**:
   - All components must continue referencing the project's canonical OKLCH tokens defined in `frontend/src/index.css` (`--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`). Hardcoded hex or ad-hoc Tailwind colors are prohibited.

---

## 6.2 Strict Ban on Extraneous Wrapper `<div>`s

In CSS Flexbox and Grid layouts, inserting an unexpected `<div>` wrapper between a parent container and its children breaks flex item distribution (`flex-1`, `justify-between`), grid track assignments (`col-span-*`), and `gap-*` spacing.

### Mandatory Solutions:
1. **React Fragments (`<>...</>`)**: When a decomposed sub-component returns multiple sibling elements, wrap them in a Fragment instead of a `<div>`.
2. **The `asChild` / Slot Pattern**: Utilize Radix UI's `asChild` composition to forward props directly onto child DOM nodes without introducing extra DOM levels.
3. **CSS `display: contents;`**: In scenarios where a DOM element is required for lifecycle or ref forwarding, apply `className="contents"` so the browser ignores the container's box model during layout.

---

## 6.3 Radix UI Context & Accessibility Boundaries

1. **Compound Component Context Continuity**:
   - `<Dialog.Root>` must encase `<Dialog.Trigger>`, `<Dialog.Portal>`, `<Dialog.Overlay>`, and `<Dialog.Content>`. Never extract `<Dialog.Content>` into a component outside of its Root context.
   - `<DropdownMenu.Root>` must surround `<DropdownMenu.Trigger>` and `<DropdownMenu.Content>`.
   - `<Tooltip.Provider>` must wrap the application root, with `<Tooltip.Root>` surrounding `<Tooltip.Trigger>`.
2. **Focus Management & Keyboard Accessibility**:
   - Modal focus traps must remain active via Radix's `FocusScope`.
   - Built-in `onEscapeKeyDown` listeners in Radix must not be intercepted by conflicting `window.addEventListener('keydown')` calls in custom hooks.
   - ARIA roles, attributes (`aria-expanded`, `aria-controls`, `aria-describedby`), and keyboard navigation (Tab, Arrow keys, Esc) must be preserved 100%.

---

## 6.4 Chrome DevTools Isolated Profile Verification Procedure

To avoid cookie pollution, session conflicts, and extension interference, all browser profiling and visual verification **must strictly execute within an isolated Chrome user profile**:

### 1. Launching Isolated Chrome Instance
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --user-data-dir="C:\Users\chung\.gemini\chrome-profiles\flama-devtools" `
  --remote-debugging-port=9222 `
  --no-first-run `
  --no-default-browser-check `
  http://localhost:4789
```

### 2. Network Waterfall Verification
- In DevTools **Network** tab (filtered by `Fetch/XHR`), perform rapid filter and tab changes.
- **Pass Criteria**: Zero duplicate HTTP queries; in-flight requests cleanly canceled via `AbortController`; static audio blobs served from memory cache.

### 3. Core Web Vitals & Cumulative Layout Shift (CLS)
- In DevTools **Performance** tab, record 5-second interaction traces (modal open/close, card selection, study flips).
- **Pass Criteria**:
  - **`CLS = 0.0000`**: Absolutely zero unexpected layout shifts.
  - **`LCP < 1.2s`**: Largest Contentful Paint under 1.2s on desktop.
  - **`INP < 100ms`**: Interaction to Next Paint response under 100ms.

### 4. React DevTools Profiler Analysis
- Record interactions with *"Record why each component rendered"* enabled.
- **Pass Criteria**: Decomposed sub-components only re-render when their direct sliced props mutate; sibling panes do not re-render during card editing.

---

## 6.5 10-Point Actionable Verification Checklist

Every refactored component and custom hook must pass all 10 checkpoints before completion:

| # | Checkpoint | Category | Verification Method | Pass Criteria |
|:---:|---|---|---|---|
| **C1** | State Threshold | Architecture | Static code inspection | Custom hook has strictly `< 8` reactive states (`useState` / `useReducer`). |
| **C2** | TypeScript Typing | Type Safety | `npm run build` / `tsc --noEmit` | Zero TypeScript errors, zero `any` types on hook params or returns. |
| **C3** | Layout Invariance | Visual | Visual inspection in DevTools | Margin, padding, font-size, line-height match 100% pixel-for-pixel. |
| **C4** | Wrapper Div Ban | DOM Structure | Inspect DOM element tree | Zero extraneous wrapper `<div>`s breaking CSS Grid or Flexbox. |
| **C5** | Radix Safety | Accessibility | Keyboard navigation test | Dialogs trap focus, Escape closes modal, ARIA tags intact. |
| **C6** | Profile Isolation | Testing | Process inspection | Chrome runs with `--user-data-dir="...flama-devtools"`. |
| **C7** | Zero Layout Shift | Performance | DevTools Performance recording | `CLS = 0.0000` during state changes and modal openings. |
| **C8** | Network Hygiene | Networking | Network waterfall tab | Zero duplicate queries; aborted requests cleanly canceled. |
| **C9** | Memory Cleanliness | Lifecycle | Heap snapshot comparison | `URL.revokeObjectURL()` called; zero dangling audio/timer listeners. |
| **C10** | Test Suites | Automated QA | `python scripts/run_tests.py` | 100% of affected frontend and backend tests pass. |

---

# 7. Consolidated Metrics & Before/After LOC Impact Table

The table below summarizes the quantitative impact across all monolithic hotspots and custom hooks targeted by this plan:

| Module / Hotspot | File(s) Before | Lines Before | Proposed Architecture & Extracted Modules | Target Total LOC | Net LOC Change | Reduction % |
|---|---|---|---|---|---|---|
| **Worksheet Studio** | `DeckWorksheetModal.tsx` | 4,388 | 1 orchestrator modal (`DeckWorksheetModal`, 140 LOC) + 1 hook (`useWorksheetStudio`, 280 LOC) + 2 modal wrappers (355 LOC) + 4 studio tabs (565 LOC) + 6 layout panels (1,160 LOC) | 2,520 | **-1,868 LOC** | **-42.6%** |
| **Admin Taxonomy** | `AdminTaxonomyPage.tsx` | 1,400 | 1 root page (95 LOC, 1 state) + 1 hook (`useTaxonomyData`, 110 LOC) + 1 generic modal (`TaxonomyEntityModal`, 130 LOC) + 5 tab components (670 LOC) | 1,005 | **-395 LOC** | **-28.2%** |
| **MCP Token Admin & User** | `AdminMcpTokensPage.tsx`<br>`McpTokensTab.tsx`<br>`useMcpTokenCRUD.ts` | 3,002 | 1 shared manager (`McpTokensManager`, 160 LOC) + 1 unified hook (`useMcpTokens`, 240 LOC) + 4 shared dialogs & tables (740 LOC) + 2 thin route wrappers (220 LOC) | 1,360 | **-1,642 LOC** | **-54.7%** |
| **Browse Mega-Hook** | `useBrowseState.ts` | 1,053 | 1 backward-compatible facade (`useBrowseState`, 85 LOC) + 4 focused sub-hooks (570 LOC) + 1 dedicated audio modal hook (250 LOC) | 905 | **-148 LOC** | **-14.1%** |
| **Shared UI Primitives** | 8 Primitives across 30+ call sites | — | 8 standalone UI primitives in `shared/ui/` with zero domain coupling (`SearchInput`, `ConfirmDialog`, `StatusPill`, etc.) | ~1,250 | *+1,250 LOC (Reusable Core)* | *Net app-wide savings: ~2,500 LOC* |
| **Total Core God Modules** | **4 Monoliths** | **9,843** | **Fully Modular FSD Hierarchy (<300 LOC/file, <8 states/hook)** | **5,790** | **-4,053 LOC** | **-41.2% Net Reduction** |

---

# 8. Phased Implementation Roadmap & Rollout Plan

To ensure continuous system stability and zero service disruption, implementation is executed in **5 distinct phases**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      PHASED IMPLEMENTATION ROADMAP                     │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 1: Leaf UI Primitives (`shared/ui`)                              │
│ • Implement 8 UI primitives with CVA & OKLCH tokens                    │
│ • Vitest unit test coverage (100% test pass)                           │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 2: Headless Custom Hooks (`features/*/hooks`)                    │
│ • Extract 14 headless hooks with <8 states contract                    │
│ • Behavioral unit tests for filter, selection, and preview hooks       │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 3: Monolith Decomposition (Worksheet, Taxonomy, MCP)             │
│ • Decompose DeckWorksheetModal into tabs & panels                      │
│ • Unify MCP tokens into McpTokensManager (eliminate duplicate lines)   │
│ • Extract TaxonomyEntityModal & 5 taxonomy tabs                        │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 4: `useBrowseState` Facade Cutover & Integration Testing        │
│ • Assemble 4 sub-hooks under useBrowseState facade                     │
│ • Verify 100% backward compatibility of all 102 properties             │
│ • Run browse and study test suites                                     │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 5: Zero Visual Regression & DevTools Profiling                   │
│ • Execute Chrome DevTools profiling with isolated profile              │
│ • Confirm CLS = 0.0000 and verify network request waterfall            │
│ • Final quality audit sign-off                                         │
└────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Leaf UI Primitives (`shared/ui`)
- **Scope**: Construct the 8 UI Primitives in `frontend/src/shared/ui/`: `SearchInput`, `ConfirmDialog`, `StatusPill`, `CodeSnippetBox`, `FilterPillGroup`, `ImageUploadDropzone`, `SplitPane`, `CardFieldsForm`.
- **Preconditions**: Zero dependencies on existing feature code.
- **Verification**: Run `npm test -- shared/ui` to verify 100% test coverage for keyboard accessibility, variants, and ARIA attributes.

### Phase 2: Headless Custom Hooks (`features/*/hooks`)
- **Scope**: Implement the 14 Headless Custom Hooks with strict `<8 states` adherence.
- **Preconditions**: Phase 1 primitives available.
- **Verification**: Verify that hook unit tests pass and that all state counts strictly satisfy `<8 states`.

### Phase 3: Monolith Decomposition (Worksheet, Taxonomy, MCP)
- **Scope**:
  1. Decompose `DeckWorksheetModal.tsx` into `WorksheetModalHeader`, `WorksheetPreviewCanvas`, `WorksheetStudioSidebar`, 4 studio tabs, and 6 layout panels.
  2. Implement `McpTokensManager.tsx` and eliminate duplicate lines across `AdminMcpTokensPage.tsx` and `McpTokensTab.tsx`.
  3. Decompose `AdminTaxonomyPage.tsx` into `TaxonomyEntityModal.tsx` and 5 tab components.
- **Verification**: Test each refactored page individually; verify zero TypeScript compiler warnings.

### Phase 4: `useBrowseState` Facade Cutover & Integration Testing
- **Scope**: Wire `useBrowseFilters`, `useBrowsePagination`, `useBrowseSelection`, `useBrowseCardOperations`, and `useBrowseAudioModal` into the `useBrowseState` master facade.
- **Verification**: Run `python scripts/run_tests.py --module study,flashcards` to verify full backward compatibility across all browse views.

### Phase 5: Zero Visual Regression & DevTools Profiling
- **Scope**: Perform browser validation using Chrome with isolated profile:
  `chrome.exe --user-data-dir="C:\Users\chung\.gemini\chrome-profiles\flama-devtools" http://localhost:4789`
- **Verification**: Complete the 10-Point Checklist (Section 6.5); verify `CLS = 0.0000`, absence of extraneous wrapper `<div>`s, and correct Radix context behavior.

---

*Master Plan authored by Teamwork Plan Author Worker (`worker_plan_author`).*  
*Verified and ready for multi-agent review and forensic audit.*
