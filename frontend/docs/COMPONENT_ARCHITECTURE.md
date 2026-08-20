# React Component Architecture Guide

## 1. Overview

Flama frontend is a Single Page Application (SPA) built with **React 18**, **Vite**, **TypeScript**, **Tailwind CSS**, and **Radix UI** primitives.
All user-facing HTML and interactions are managed by the React application in `frontend/src/`. Flask serves canonical JSON APIs under `/api` and the SPA entrypoint (`frontend/dist/index.html`).

---

## 2. Directory Structure

```text
frontend/src/
├── app/                  # Application routing, query client, root providers
│   ├── routes.tsx        # React Router routes definition
│   └── query-client.ts   # TanStack Query client configuration
├── assets/               # Static assets, SVG logos, brand illustrations
├── components/           # Global & UI Primitive Components
│   ├── ui/               # Reusable primitives (Radix UI + Tailwind CVA)
│   │   ├── alert.tsx
│   │   ├── avatar.tsx
│   │   ├── badge.tsx
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── drawer.tsx
│   │   ├── dropdown-menu.tsx
│   │   ├── input.tsx
│   │   ├── scroll-area.tsx
│   │   ├── select.tsx
│   │   ├── sheet.tsx
│   │   ├── sidebar.tsx
│   │   ├── skeleton.tsx
│   │   ├── sonner.tsx
│   │   ├── table.tsx
│   │   ├── tabs.tsx
│   │   ├── textarea.tsx
│   │   └── tooltip.tsx
│   ├── app-sidebar.tsx   # Main responsive navigation sidebar
│   ├── nav-main.tsx      # Sidebar navigation items
│   ├── nav-user.tsx      # User profile & logout controls
│   ├── site-footer.tsx   # Global footer
│   └── ambient-background.tsx
├── config/               # App configuration, constants, navigation items
├── features/             # Feature-sliced modules (Domain-driven)
│   ├── admin/            # Admin user management, roles, payments, TTS settings
│   ├── audio/            # Flama Audio local TTS integration & generation hooks
│   ├── auth/             # Authentication (Login, Register, Session context)
│   ├── browse/           # Card & deck browser, filters, card edit modals
│   ├── dashboard/        # Dashboard overview, deck tree, daily stats & heatmap
│   ├── import/           # CSV/Anki file import wizard & field mapping
│   ├── library/          # User decks, note types, and templates library
│   ├── marketplace/      # Shared deck marketplace, installs, change requests
│   ├── note-types/       # Note type builder, template editor, live sandbox preview
│   ├── orders/           # Orders, payOS checkout flow, donation support
│   ├── settings/         # User profile, scheduler presets, MCP access tokens
│   ├── statistics/       # Learning statistics, retention metrics, forecast
│   └── study/            # Active study session, card renderer, undo history
├── hooks/                # Custom React hooks (theme, media query, debounce)
├── layouts/              # Layout wrappers (AppLayout, AuthLayout, AdminLayout)
├── lib/                  # Utilities (cn helper, formatters, date helpers)
├── shared/               # Shared API client and common TypeScript definitions
│   ├── api/              # Canonical HTTP client with CSRF auto-injection
│   └── types/            # Shared DTOs, API error envelopes, entity interfaces
├── App.tsx               # Root component with providers
├── index.css             # Tailwind & CSS variable design tokens
└── main.tsx              # React DOM entrypoint
```

---

## 3. Core Design Principles

### 3.1 Feature-Sliced Architecture
- Code is organized by domain in `frontend/src/features/<feature_name>/`.
- Each feature encapsulates:
  - `components/`: UI components private to the feature.
  - `hooks/`: Domain hooks & data fetching.
  - `pages/`: Route page components.
  - `types.ts` / `utils/`: Domain-specific types and helpers.

### 3.2 UI Primitives with Tailwind CSS & Radix UI
- UI primitives in `frontend/src/components/ui/` leverage **Radix UI** for accessible unstyled primitives and **Tailwind CSS** with `class-variance-authority` (cva) for type-safe variants.
- Semantic colors use OKLCH color variables defined in `src/index.css` (e.g. `--primary`, `--secondary`, `--destructive`, `--muted`, `--accent`).

---

## 4. API Client & Security

### 4.1 Automated CSRF & Session Management
All API calls are routed through the shared client in `frontend/src/shared/api/`.
- Requests include `credentials: "same-origin"`.
- Mutation requests (`POST`, `PUT`, `PATCH`, `DELETE`) automatically inject the CSRF token retrieved from `GET /api/session`.
- Error responses adhere to the standard envelope `{ error: string, message: string, field?: string, details?: any[] }`.

```typescript
import { apiClient } from "@/shared/api"

// Fetching data
const decks = await apiClient.get<DeckListResponse>("/api/decks")

// Mutating data with CSRF
await apiClient.post("/api/decks", { name: "Japanese N1" })
```

---

## 5. Sandboxed Flashcard Renderer

To prevent XSS from custom card template scripts:
- Untrusted card HTML/CSS/JS is compiled and sanitized on the backend (`app/services/flashcard_renderer.py`).
- Card content is rendered inside an `iframe sandbox="allow-scripts"` managed by `static/js/card_renderer_host.js` and wrapped in React via `frontend/src/features/study/renderer/`.
- Communication uses a secure `postMessage` protocol with strictly allowlisted actions (flip, reveal, audio playback request).

---

## 6. Flama Audio Local Companion Integration

- The `features/audio/` module communicates with the local Flama Audio Windows desktop companion at `http://127.0.0.1:4791`.
- Provides offline VoiceVox and Kokoro TTS speech synthesis directly in the browser, uploading generated WAV blobs to `/api/notes/<note_id>/media`.
