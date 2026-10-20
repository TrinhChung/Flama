# Flama Frontend Architecture Specification

- **Domain**: Frontend Single Page Application (SPA)
- **Root Path**: `frontend/src/`
- **Specification Status**: Active / Production Ground Truth
- **Framework Stack**: React 19.2.7, Vite 8.1.1, TypeScript ~6.0.2, TailwindCSS v4.3.3, React Router DOM ^7.18.3, TanStack Query v5.101.4

---

## 1. Architectural Overview & Design Philosophy

Flama is an enterprise-scale Japanese language spaced repetition system (SRS), vocabulary mining workstation, and educational content marketplace. The frontend is built as a fully decoupled Single Page Application (SPA) running React 19.

Server-rendered HTML templates (Jinja2) have been eliminated; Flask serves only the single static SPA entry shell (`app/spa.py`) and canonical JSON REST APIs under `/api`.

```
+--------------------------------------------------------------------------------------------------+
|                                  Flama Client System Architecture                                |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
         v                                       v                                       v
+------------------+                   +--------------------+                  +-------------------+
|  Flask REST API  |                   | Flama Audio Bridge |                  | Flama Connect MCP |
|  Port 4789       |                   | Port 4791 (Desktop)|                  | Port 4790 (Bridge)|
|  - Session / Auth|                   | - VoiceVox Engine  |                  | - Yomitan / Anki  |
|  - Flashcards    |                   | - Kokoro Engine    |                  | - asbplayer sync  |
|  - Decks & Notes |                   | - Local Synthesis  |                  | - OAuth2 Tokens   |
|  - Marketplace   |                   | - Pairing Protocol |                  | - Scheme CORS     |
+------------------+                   +--------------------+                  +-------------------+
```

### Architectural Guarantees
1. **Zero Server Rendering**: All UI components, state machines, and view routing execute entirely on the client.
2. **Pragmatic Feature-Sliced Design (FSD v2.1)**: Code is organized into strict functional layers (`app`, `pages`, `features`, `entities`, `shared`, `components`).
3. **Triple-Tier State Persistence**: Server state caching (TanStack Query) is decoupled from offline study execution (IndexedDB) and UI preferences (`localStorage`).
4. **Anti-AI-Slop & Zero Visual Regression**: Strict design system based on linear OKLCH color spaces ("Tone màu Hỏa ấm"), Geist typography, and ambient backdrops.
5. **Native Array Preservation**: Array fields are maintained as JSON lists; no Anki flat-string degeneration is permitted.

---

## 2. Technology Stack & Runtime Configuration

| Layer | Technology | Version | Location / Config |
|---|---|---|---|
| **Runtime / UI** | React | `19.2.7` | `frontend/package.json:44` |
| **Bundler & Dev Server**| Vite | `8.1.1` | `frontend/vite.config.ts` |
| **Type System** | TypeScript | `~6.0.2` | `frontend/package.json:67` |
| **Styling Engine** | TailwindCSS | `v4.3.3` | `frontend/src/index.css` via `@tailwindcss/vite` |
| **Client Routing** | React Router DOM | `^7.18.3` | `frontend/src/App.tsx:367` (`createBrowserRouter`) |
| **Server State** | TanStack Query | `v5.101.4` | `frontend/src/main.tsx:11` (`QueryClient`) |
| **Client Database** | IndexedDB | Database `flama-study` (v2/v3) | `frontend/src/features/study/session/sessionStore.ts` |
| **Internationalization**| i18next & react-i18next | `v26.4.2` / `v17.0.16` | `frontend/src/shared/config/i18n/` (26 namespaces) |
| **Icons & Primitives** | Lucide React & Radix UI | `^1.27.0` / Radix Primitives | `frontend/src/components/ui/` (30 primitives) |
| **Sanitization & AST** | DOMPurify & Mustache | `^3.4.15` / `v4.2.0` | `frontend/src/entities/flashcard/lib/clientRenderer.ts` |

### 2.1 Vite Proxy Configuration (`frontend/vite.config.ts`)
The development server binds to `127.0.0.1:5173`. Proxies route backend requests directly to the Flask server at `http://127.0.0.1:4789`:
- Proxied routes: `/api`, `/auth`, `/media`, `/static`, `/support-donation`.
- `changeOrigin: false`: Ensures original cookie domains, session headers, and host headers are preserved across Vite and Flask.
- Alias: `@` resolves directly to `frontend/src/`.

---

## 3. Application Entry Points & Startup Flow

The root bootstrap sequence guarantees that internationalization assets and synchronization listeners are fully hydrated before DOM attachment.

```typescript
// frontend/src/main.tsx:24-36
const root = createRoot(document.getElementById('root')!)
void i18nReady.then(() => {
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <TranslationLoadBoundary><App /></TranslationLoadBoundary>
          <Toaster position="bottom-right" richColors />
        </TooltipProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
}).catch(() => root.render(<TranslationLoadFailure />))
```

### 3.1 Startup Flow Lifecycle
1. **Card Content Synchronization Setup**: `frontend/src/App.tsx:2` imports `frontend/src/app/studyContentSync.ts`. This registers cross-entity card update listeners between `entities/flashcard` and `features/study/contentUpdates` before any route is evaluated.
2. **i18n Ready Gate**: `i18nReady` is resolved when primary namespaces (`common`, `shell`, `auth`) are loaded into memory, completely preventing Flash of Unlocalized Content (FOUC).
3. **QueryClient Configuration**:
   - `staleTime: 30_000` (30 seconds)
   - `retry: 1`
   - `refetchOnWindowFocus: false` (prevents unexpected background refetches during active study sessions)
4. **Backend Availability Guardian**: `App.tsx` subscribes to `subscribeBackendUnavailable` (`src/shared/api/backendAvailability.ts`). Any 502/503/504 gateway response from Flask automatically routes the browser to `/maintenance`.

---

## 4. Routing Hierarchy & View Layouts

Routing is declared in `frontend/src/App.tsx:367-689` using React Router v7 `createBrowserRouter`. All major pages use lazy-loaded dynamic imports wrapped in the `deferred(...)` utility (`Suspense` + `TranslationLoadBoundary` + loading spinner).

```
Routing Hierarchy (frontend/src/App.tsx)
│
├── /maintenance ──────────────────── MaintenancePage (standalone, gateway error fallback)
├── /oauth/consent ────────────────── OAuthConsentPage (standalone, MCP / ChatGPT consent)
│
└── <AppLayout /> (Root Shell Layout)
    │
    ├── [Public Layout: Header + Nav + Footer + Mascot]
    │   ├── / ─────────────────────── LandingPage
    │   ├── /login ────────────────── LoginPage
    │   ├── /register ─────────────── RegisterPage
    │   ├── /forgot-password, /reset-password, /verify-email
    │   ├── /support, /payments/result
    │   ├── /guide (with /:categorySlug/:articleSlug)
    │   └── /terms, /privacy, /cookies, /marketplace-guidelines, /community-guidelines
    │
    ├── [Distraction-Free Fullscreen Viewports (No Sidebar / No Header)]
    │   ├── /study ────────────────── StudyPage (h-screen h-[100dvh] overflow-hidden)
    │   └── /browse ───────────────── BrowsePage (h-screen h-[100dvh] overflow-hidden)
    │
    └── <RequireAuth /> (Authenticated Shell: AppSidebar + SidebarInset + Header)
        ├── /dashboard ────────────── DashboardPage (speculative route preloading enabled)
        ├── /statistics ───────────── StatisticsPage
        ├── /note-types, /note-types/:id, /note-types/:id/fields
        ├── /card-templates, /card-templates/:id
        ├── /installed-decks, /installed-decks/:id/templates, /installed-decks/:id/updates/:releaseId
        ├── /flashcards/shared-decks/:id/change-request, /flashcards/change-requests/incoming
        ├── /worksheets ───────────── WorksheetsPage
        ├── /audio/generate ───────── DeckAudioGeneratorPage
        ├── /sync, /import ────────── AnkiSyncPage, FileImportPage
        ├── /settings/goals, /settings/mcp-tokens, /settings/yomitan, /settings/asbplayer
        ├── /feedback, /tickets, /tickets/:id
        ├── /marketplace/decks, /marketplace/decks/publish, /marketplace/decks/:id
        ├── /marketplace/note-types, /marketplace/note-types/publish, /marketplace/note-types/:id
        ├── /orders, /profile, /wallet
        │
        ├── <RequireCreator />
        │   └── /creator/decks/:itemId/releases/new ── ReleaseBuilderPage
        │
        └── [Protected Admin Module]
            └── /admin/analytics, /admin/users, /admin/payments, /admin/fees,
                /admin/tts, /admin/image-library, /admin/permissions, /admin/mcp-tokens,
                /admin/support, /admin/tickets, /admin/taxonomy
```

---

## 5. Feature-Sliced Design (FSD) Structure & Component Map

The application follows Pragmatic Feature-Sliced Design (FSD v2.1):

```
frontend/src/
├── app/                  # Application initialization, API facade, content sync
├── assets/               # Brand SVGs, icons, illustrations
├── components/           # Global components & shadcn primitives
│   └── ui/               # 30 Radix UI primitives with Tailwind CVA
├── config/               # Endpoint declarations and environment constants
├── data/                 # Bilingual legal texts and static guide articles
├── entities/             # Core business domain entities
├── features/             # 25 independent functional domain slices
├── hooks/                # Global device and utility hooks
├── layouts/              # AppLayout shell
├── lib/                  # Foundational utilities (arrayField, audioClient, ankiSync)
├── pages/                # Top-level standalone page components
└── shared/               # Reusable infrastructure (API, UI primitives, i18n)
```

### 5.1 Domain Entities (`frontend/src/entities/`)
Entities encapsulate domain schemas, persistent data types, and isolated API query keys:
1. **`card-template`** (`frontend/src/entities/card-template/`):
   - Types: `TemplateInputSpec`, `TemplateBindings`, `TemplateLibraryItem`, `TemplateApplication`.
   - API: `cardTemplateApi.ts` managing `/api/card-templates` and `/api/note-types/:id/template-applications`.
   - Query Keys: `queryKeys.ts` with standardized tuples (`['card-template', 'library', ...]`).
2. **`flashcard`** (`frontend/src/entities/flashcard/`):
   - Client Renderer: `clientRenderer.ts` (in-memory Mustache compilation, safe DOMPurify sanitization, and native array preservation).
   - Event Hub: Cross-component flashcard content synchronization events (`studyContentSync.ts`).

### 5.2 The 25 Feature Slices (`frontend/src/features/`)

| Feature Slice | Directory | Primary Responsibilities & Components |
|---|---|---|
| **`admin`** | `features/admin/` | 11 administrative pages: `AdminUsersPage`, `AdminPaymentsPage`, `AdminFeesPage`, `AdminTtsPage`, `AdminPermissionsPage`, `AdminTaxonomyPage`, `AdminMcpTokensPage`. |
| **`audio`** | `features/audio/` | Flama Audio desktop companion integration, local audio dialog (`LocalAudioDialog.tsx`), connection gate (`FlamaAudioConnectionGate.tsx`), deck scan, batch audio queue monitor (`DeckAudioQueueMonitor.tsx`). |
| **`auth`** | `features/auth/` | Authentication forms (`LoginPage`, `RegisterPage`, `ForgotPasswordPage`, `ResetPasswordPage`), form hooks (`useLoginForm.ts`, `useRegisterForm.ts`), session auth gating via `useBootstrap()` in `RequireAuth.tsx`. |
| **`browse`** | `features/browse/` | Vocabulary browse table (`BrowsePage`), virtualized card list, multi-deck tree filter, tag search, bulk edit dialogs. |
| **`dashboard`** | `features/dashboard/` | Learner home (`DashboardPage`), deck tree hierarchy, daily review forecast heatmap, due counts rollup, speculative page preload. |
| **`deck-collaboration`** | `features/deck-collaboration/` | Community deck contribution: `ChangeRequestInboxPage`, `ChangeRequestDetailPage`, `ReleaseBuilderPage`, `InstalledDeckUpdatePage`. |
| **`guide`** | `features/guide/` | Interactive knowledge base (`GuidePage`, `GuideArticlePage`), Yomitan, asbplayer, and desktop companion tutorials. |
| **`import`** | `features/import/` | Import wizard (`FileImportPage`, `AnkiSyncPage`), AnkiConnect field mapping, progress streaming, zip extraction via zip.js. |
| **`library`** | `features/library/` | Installed community decks (`InstalledDecksPage`), overlay sync status, update checks against published releases. |
| **`marketplace`** | `features/marketplace/` | Public deck & note-type marketplace (`SharedDecksPage`, `SharedDeckDetailPage`, `MarketplacePublishDeckPage`), payOS payment results. |
| **`mcp`** | `features/mcp/` | Model Context Protocol API tokens, scope matrix, and authorization credentials for external AI agents. |
| **`note-types`** | `features/note-types/` | Note type builder (`NoteTypeManagerPage`, `NoteTypeFieldsPage`, `NoteTypeDetailPage`), field schema configuration. |
| **`oauth`** | `features/oauth/` | Standalone OAuth 2.0 authorization screen (`OAuthConsentPage`) for ChatGPT and external MCP clients. |
| **`onboarding`** | `features/onboarding/` | First-time user tour modal (`OnboardingModal.tsx`, `OnboardingHeroCard.tsx`), interactive steps. |
| **`orders`** | `features/orders/` | Transaction invoices, payment receipts, order ledger (`OrdersPage`). |
| **`profile`** | `features/profile/` | User profile management (`ProfilePage`), avatar upload, biography, account preferences. |
| **`settings`** | `features/settings/` | Study goals (`StudyGoalsPage`), Yomitan API tokens (`YomitanTokensPage`), asbplayer settings, scheduler parameters. |
| **`statistics`** | `features/statistics/` | Study analytics (`StatisticsPage`), retention rate charts, memory stability distribution, calendar heatmaps. |
| **`study`** | `features/study/` | Flashcard study engine (`StudyPage.tsx`, `useStudySession.ts` hook, `StudyCardRendererFrame.tsx`, `StudyHeaderToolbar.tsx`, `StudyBottomBar.tsx`), SRS rating buttons, answer reveal, quick card edit dialog. |
| **`support`** | `features/support/` | Support portal (`SupportPage`), feedback submission (`FeedbackPage`), user ticket status (`TicketDetailPage`). |
| **`template-distribution`**| `features/template-distribution/` | Card template publishing to marketplace, licensing options, pricing setup. |
| **`template-library`** | `features/template-library/` | Template exploration catalog (`TemplateLibraryPage`), preview host, template detail view. |
| **`template-versions`** | `features/template-versions/` | Template version history, visual diff comparison, rollback controls. |
| **`wallet`** | `features/wallet/` | Creator balance overview (`WalletPage`), transaction log, payout requests. |
| **`worksheets`** | `features/worksheets/` | Japanese practice sheet generator (`WorksheetsPage`), printable canvas studio (`StudioLayoutTab.tsx`), PDF generation. |

### 5.3 Shared Infrastructure & UI Primitives (`frontend/src/shared/`)
- **API Engine (`src/shared/api/`)**:
  - `client.ts`: Canonical HTTP client providing `apiRequest`, `apiJson`, `apiJsonKeepalive`, `setCsrfToken`, `getCsrfToken`.
  - Configures `credentials: "include"` for secure session cookies.
  - Automatically parses Flask-WTF CSRF tokens from cookies or response headers and injects `X-CSRFToken` on mutating requests (POST, PUT, PATCH, DELETE).
- **9 Domain-Level Tested UI Primitives (`src/shared/ui/`)**:
  1. `CodeSnippetBox`: Formatted code container with one-click copy feedback.
  2. `ConfirmDialog`: Standardized modal for destructive actions.
  3. `FilterPillGroup`: Multi-selection filter buttons with active counter badges.
  4. `ImageUploadDropzone`: Drag-and-drop image uploader with preview thumbnail.
  5. `LanguageSwitcher`: Bilingual selector supporting instant locale swap.
  6. `SearchInput`: Standardized debounced search input with clear icon.
  7. `SplitPane`: Resizable two-pane layout with persistent divider positions.
  8. `StatusPill`: Standardized colored state indicator for reviews and decks.
  9. `WorkspaceLayout`: Three-column responsive workspace drawer.
- **Note field editing** lives in `src/entities/flashcard/ui/NoteFieldEditor.tsx` (media preview, native array input or text; Input vs Textarea is fixed at mount from field type, name and stored value). Browse edit/create and the Study quick-edit dialog share it.

---

## 6. Triple-Tier State Persistence Architecture

Flama avoids monolithic global state stores (Redux, MobX, Zustand). State is stratified across three dedicated tiers:

```
+--------------------------------------------------------------------------------------------------+
|                                    State Management Triad                                        |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   1. Server State              2. Offline & Session Persistence          3. UI & Ephemeral       |
|   [@tanstack/react-query]      [IndexedDB + localStorage]                [React Hooks & Primitives]|
|   - Stale-while-revalidate     - 'flama-study' IndexedDB                 - useState / useReducer |
|   - Bootstrap session query    - Crash-safe study sessions               - Headless custom hooks |
|   - Domain queryKeys           - Event stream & checkpoints              - Context (Sidebar/Chart)
|   - Mutation invalidation      - User preferences & tokens               - SplitPane / Drawer states|
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

### 6.1 Tier 1: Server State (@tanstack/react-query)
- **Bootstrap Anchor**: `useBootstrap()` (`src/shared/api/bootstrap.ts`) is the primary source of truth for user authentication, role flags (`is_admin`, `is_creator`), server-rendered flash messages, and dynamic navigation badges.
- **Query Invalidation Policy**: Mutations explicitly invalidate domain-specific query keys. For example, logging out invalidates `['bootstrap']`; publishing a template invalidates `['card-template', 'library']`.

### 6.2 Tier 2: Study Engine Persistence (IndexedDB)
The study subsystem (`src/features/study/session/sessionStore.ts`) uses an IndexedDB database named `flama-study` (Version 2/3):
- **Object Stores**:
  - `sessions`: Active and committed study sessions with card state snapshots.
  - `session-quarantine`: Diverged or corrupted sessions isolated for inspection without crashing the client.
  - `session-artifacts`: Offloaded heavy review checkpoints (active when `SPLIT_STORAGE_ENABLED === '1'`).
- **Crash Resilience**: If a learner closes the tab or loses power mid-review, the session is recovered from IndexedDB upon relaunch.
- **Event Sourcing**: Every review rating (`again`, `hard`, `good`, `easy`) appends a `StudySessionEvent` with a monotonic timestamp, enabling instant client-side undo/redo without roundtrips to the server.
- **Private Browsing Fallback**: When IndexedDB access is denied by browser security policies, memory fallback `Map<string, PersistedStudySession>` instances maintain uninterrupted study.

### 6.3 Tier 3: LocalStorage Registry
Persistent client preferences stored in `localStorage`:
- `nihongo_language_preference`: Active language locale (`vi` or `en`).
- `flama_audio_pairing_token`: Cryptographic Bearer token for Flama Audio companion.
- `anki_nt_map_<modelName>`: Cached field mappings for AnkiConnect imports.
- `flama:workspace:split`: Persisted split-pane layout dimensions.
- `worksheet_preset_<noteTypeId>`: Custom field mappings for printable worksheets.
- `tour_completed_*`: Completed product walkthrough flags.

---

## 7. Audio & Speech Integration Architecture

Flama provides deep audio synthesis and playback support through a hybrid local/companion architecture:

### 7.1 Flama Audio Companion Bridge (`frontend/src/lib/flamaAudioClient.ts`)
To eliminate third-party cloud TTS costs and latency, Flama connects to the **Flama Audio** Windows desktop companion (.NET 8 WPF, port 4791).

```
+--------------------+        1. Start Pairing Challenge        +------------------------+
|                    | ---------------------------------------> |                        |
|  Flama Frontend    |                                          |  Flama Audio Companion |
|  Web Browser       | <--------------------------------------- |  (Local Port 4791)     |
|                    |        Returns pairing_id (HTTP 200)     |                        |
|                    |                                          |  - User clicks Approve |
|                    |        2. Poll Pairing Status            |    in Desktop Window   |
|                    | ---------------------------------------> |                        |
|                    | <--------------------------------------- |                        |
|                    |        Returns Bearer Token              +------------------------+
|                    |                                                      |
|                    |        3. POST /v1/tts with Token                    |
|                    | ---------------------------------------------------->|
|                    | <----------------------------------------------------+
|                    |        Returns Synthesized WAV Blob (VoiceVox/Kokoro)
+--------------------+
```

1. **Zero-Config Discovery**: Probes `http://127.0.0.1:4791/health` for local companion availability.
2. **Cryptographic Pairing**: Verifies `window.location.origin` and requires physical user confirmation in the desktop window before issuing a bearer token.
3. **Engine Support**: Provides both **VoiceVox** (neural Japanese vocoder) and **Kokoro TTS**.
4. **Batch Generation**: `DeckAudioGeneratorPage.tsx` scans decks for cards lacking audio, queues synthesis through `DeckAudioQueueMonitor.tsx`, and uploads the generated WAV audio to `/api/notes/<note_id>/media`.

### 7.2 Study Flashcard Audio Playback (`CardRendererHost`)
Card templates execute inside an isolated `iframe` sandbox to prevent arbitrary script execution.
- **Autoplay Restriction Workaround**: Modern browsers block audio autoplay inside cross-origin sandboxed iframes. The study host mounts a single shared `<audio aria-hidden="true">` element on `document.body`.
- **PostMessage Bridge**: When a card renders or when the user clicks an audio button, the iframe posts a message (`flama-play-audio`). The outer application intercepts the message, resolves the `/media/proxy/<asset_id>` URL, and triggers playback on the trusted host element.
- **Tag Normalization**: Automatically transforms Anki `[sound:filename.mp3]` tags, plain media URLs, and HTML5 `<audio>` tags into unified player controls.

---

## 8. Design System, Theming & Anti-AI-Slop Guardrails

### 8.1 Visual Theme Philosophy (`frontend/src/index.css`)
Flama's visual identity uses a warm fire palette ("Tone màu Hỏa ấm") expressed in linear **OKLCH**:
- **Primary Brand Color**:
  - Light Mode: `oklch(0.635 0.215 35)` (warm amber / vermilion fire)
  - Dark Mode: `oklch(0.70 0.21 40)` (illuminated ember)
  - Foreground: `oklch(0.985 0 0)` / `oklch(0.145 0 0)`
- **Typography**: `@fontsource-variable/geist` (`Geist Variable`, sans-serif).
- **Ambient Depth (`frontend/src/components/ambient-background.tsx`)**: Dynamic radial background gradients using OKLAB `color-mix` positioned at 20% and 80% bottom bounds, overlaid with a subtle repeating 36px grid pattern (`[size:36px_36px]`).
- **Cards & Toolbars**: Glassmorphic panels styled with `border-border/60`, `bg-background/80`, and `backdrop-blur-md`.

### 8.2 Anti-AI-Slop Visual Constraints
The repository enforces strict UI guardrails:
- **No Neon Cosmic Gradients**: Purple-to-pink gradient schemes are forbidden.
- **No Decorative Magic Icons**: Magic wand and starburst icons are prohibited.
- **Zero Visual Regression**: Any component refactoring must preserve exact pixel dimensions, padding, font weights, colors, and layout positioning.

---

## 9. Native Array Support & Client Renderer

### 9.1 Native Array Data Format
- In Flama, field values of type `array` are stored as **JSON lists** of text or rich-text items in `notes.field_values`.
- Flama **does not export to Anki**; flat string constraints of Anki do not apply.
- Values are read via `fieldValueEditorText()` and parsed via `parseArrayValue()` (`frontend/src/lib/arrayField.ts`) for editor representations, while backend normalization uses `stored_field_value()` (`models/field_types.py`).

### 9.2 Client Flashcard Renderer (`entities/flashcard/lib/clientRenderer.ts`)
- In-memory Mustache compiler processes card templates on the client.
- Passes array fields directly into Mustache templates without flat string conversions, enabling native `{{#field}}{{.}}{{/field}}` loop constructs.
- Output HTML is sanitized through DOMPurify before insertion into the sandboxed card frame.

---

## 10. Internationalization (i18n) Engine

The localization subsystem is built on `i18next` v26.4.2 and `react-i18next` v17.0.16.

### 10.1 Bilingual Namespaces
The system supports Vietnamese (`vi`) and English (`en`) across **26 namespaces**:
`audio`, `auth`, `browse`, `card_templates`, `collaboration`, `common`, `dashboard`, `guide`, `import`, `landing`, `legal`, `library`, `marketplace`, `mcp`, `note_types`, `onboarding`, `orders`, `profile`, `settings`, `shell`, `statistics`, `study`, `support`, `template_mapping`, `wallet`, `worksheets`.

### 10.2 Parity & Quality Gates
- **100% Leaf-Key Parity**: Automated stress test `frontend/src/shared/config/i18n/i18n.stress.test.tsx` validates that every key in `vi/*.json` exists in `en/*.json` with matching types and non-empty values.
- **Instant Locale Swap**: The `LanguageSwitcher` component updates `localStorage` and triggers immediate re-rendering via `i18n.changeLanguage()` with zero Cumulative Layout Shift (CLS = 0).
