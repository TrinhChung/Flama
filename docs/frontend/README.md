# Flama Frontend Documentation Hub

Welcome to the Flama Frontend documentation directory. This hub covers the architecture, development workflows, component layouts, and technical debt of the Flama Single Page Application (`frontend/src/`).

---

## 1. Domain Navigation & Document Index

| Document | Purpose & Scope |
|---|---|
| [**`ARCHITECTURE.md`**](./ARCHITECTURE.md) | **Authoritative Technical Architecture Guide**: React 19 SPA lifecycle, Vite 8 build pipeline, FSD v2.1 structure, 25 feature slices, 2 entity slices, triple-tier persistence (TanStack Query + IndexedDB + localStorage), Flama Audio companion integration, and the Japanese Fire OKLCH design system. |
| [**`tech-debt/README.md`**](./tech-debt/README.md) | **Technical Debt & Refactoring Catalog**: Comprehensive index of 10 oversized components (>800 LOC, peak `StudioLayoutTab.tsx` at 2,497 LOC), 3 mega-hooks (>1,000 LOC), legacy `app/api.ts` facade, unlocalized admin modules, and pending FSD extractions. |
| [**`old/README.md`**](./old/README.md) | **Historical Archive**: Directory reserved for preserving retired frontend architecture notes, legacy planning documents, and superseded specifications. |

---

## 2. Quickstart for Frontend Developers

### 2.1 Environment & Prerequisites
- **Node.js**: `>= 20.x`
- **Package Manager**: `npm`
- **Working Directory**: `d:\Project\nihongo\frontend`
- **Backend Dependency**: Flask API running on port `4789` (or development proxy active).

### 2.2 Common Commands

```bash
# Install dependencies
npm --prefix frontend install

# Start Vite development server (http://127.0.0.1:5173)
npm --prefix frontend run dev

# Run TypeScript type check (strict, zero errors tolerated)
npm --prefix frontend run typecheck

# Run Vitest test suites (changed files only via repo test runner)
python scripts/run_tests.py --changed --frontend-only

# Run full Vitest test suite
npm --prefix frontend test

# Run Vitest for a specific domain module
npm --prefix frontend test -- src/entities/card-template

# Run Oxlint validation (oxlint src)
npm --prefix frontend run lint

# Build for production
npm --prefix frontend run build
```

---

## 3. Directory Structure Overview (`frontend/src/`)

```text
frontend/src/
├── app/                  # Application root bootstrap, API facade, study content sync
├── assets/               # Brand logos, icons, SVGs
├── components/           # Global components & 30 shadcn UI primitives
├── config/               # Environment constants (API_BASE_URL)
├── data/                 # Bilingual legal texts and static guide articles
├── entities/             # Core business domain entities (card-template, flashcard)
├── features/             # 25 independent functional domain slices
├── hooks/                # Global device and utility hooks (use-mobile, use-debounce)
├── layouts/              # Unified AppLayout shell
├── lib/                  # Helpers (arrayField, flamaAudioClient, ankiSyncEngine)
├── pages/                # Standalone top-level pages (LandingPage, MaintenancePage)
└── shared/               # Shared infrastructure (HTTP client, i18n, 10 UI primitives)
```

---

## 4. Key Engineering Guardrails

When developing on the Flama frontend, you must adhere to the following guardrails:

1. **Zero Visual Regression**: Always preserve exact colors, OKLCH linear gradients, padding, font size, icon alignment, and layout geometry. No visual drift is permitted during refactoring.
2. **Anti-AI-Slop Visual Constraints**: Purple/pink neon cosmic gradients, decorative magic wand icons, and generic placeholder text are strictly prohibited. Flama uses the warm Japanese Fire palette ("Tone màu Hỏa ấm") with Geist typography.
3. **Native Array Preservation**: Array fields in cards are stored as JSON lists. Never flatten them with `str()` or export them to Anki. Use `fieldValueEditorText()` in `src/lib/arrayField.ts` for text formatting.
4. **Bilingual i18n Parity**: All user-facing strings must use `useTranslation()`. Hardcoded English or Vietnamese text in JSX is forbidden. New translation keys must be added symmetrically to both `vi/*.json` and `en/*.json` with 100% leaf-key parity.
5. **Chrome DevTools Isolation**: When running automated profiling or browser tests, always use an isolated Chrome profile (`C:\Users\chung\.gemini\chrome-profiles\flama-devtools`) to protect personal cookies and data.
