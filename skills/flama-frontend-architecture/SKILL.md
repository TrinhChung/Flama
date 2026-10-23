---
name: flama-frontend-architecture
description: Build or refactor Flama React SPA components in frontend/src/, including FSD boundaries, hooks, slice APIs, and preservation of existing UI behavior.
---

# Flama Frontend Architecture

Read `AGENTS.md`, the relevant section of `docs/frontend/ARCHITECTURE.md`, and the touched code. Documentation describes both current legacy locations and migration targets; verify which is which.

## Ownership and imports

Target dependency direction: `app -> pages -> widgets (optional) -> features -> entities -> shared`. A layer imports lower layers; internal imports within a slice are allowed. Sibling slices at the same layer must not depend on each other, even through public barrels. Lift composition or extract a lower-layer dependency instead; a domain contract alone does not waive this rule.

- `app`: bootstrap, providers, router and global wiring.
- `pages`: route composition of features/entities; move integration out of `features/*/pages` when touching it.
- `widgets`: reusable composed blocks that may coordinate several features.
- `features`: user actions, workflows, API orchestration and their UI/hooks.
- `entities`: domain types, entity queries and display UI, independent of feature workflows.
- `shared/{ui,hooks,lib,api,config}`: business-independent infrastructure and primitives.

Root `components/`, `hooks/`, `lib/`, `config/`, `layouts/` contain migration debt. Add no new files there. Reuse a suitable existing primitive while migrating its callers; do not create a second implementation in `shared`.

Expose slice entry points through `index.ts`; outside consumers use `@/features/<slice>` or `@/entities/<slice>`. Keep same-slice imports local to avoid barrel cycles. Preserve lazy loading: a barrel must not eagerly import heavy worksheet/editor/audio bundles merely to export a lightweight type or button.

## Migration when touching a file

1. Identify the file's responsibility and move it to the appropriate layer as required by `AGENTS.md`; update affected callers rather than expanding into an unrelated repository rewrite.
2. Resolve sibling feature use by lifting composition to a page/widget or extracting an independent entity/primitive. Audio, worksheets and contextual help workflows must not become `shared` merely to silence a boundary check.
3. Extract complex state, effects, timers and requests into slice-local `hooks/`; simple local presentation state can remain in UI. Preserve cancellation, cleanup, error handling, optimistic updates and cache invalidation.
4. Replace legacy `app/api.ts` calls with slice-local `api/` using `shared/api/client.ts`. Preserve URLs, payloads, CSRF, cookies and error contracts. DTOs match API responses; ORM columns are not automatically public API fields.
5. Search alias/relative imports, re-exports, lazy imports, router, tests and configuration before deleting an old path. Remove a shim only after those consumers are migrated. Update Shadcn aliases in `frontend/components.json` when moving primitives.

Inspect consumer count and ownership before moving a shared module. A move spanning unrelated slices should be a coordinated, explicit migration step with its own verification, not an incidental expansion of a small fix. This keeps the on-touch rule scoped without adding new boundary violations or silently waiving it.

Choose feature boundaries by cohesive user workflows and ownership. Cycles justify investigation, not automatic merger of all `template-*` modules. Keep entity types independent of feature actions and auth effects outside the user entity model.

## Verification

Preserve colors, gradients, typography, spacing, icons, shadows, responsive layout, focus/keyboard behavior and loading/error states unless redesign was requested. Run focused Vitest coverage and typecheck for changed imports; compare affected screens at relevant viewports. Passing types or DOM snapshots alone does not establish visual equivalence. Use an isolated browser profile for all Chrome debugging.

Future boundary enforcement must resolve aliases, relative imports, re-exports, dynamic imports and type-only dependencies. Establish a reviewed baseline for existing violations, reject new ones, and reduce the baseline per migration; do not silently exempt changed files. Never claim this guard exists until it is implemented and wired into checks.
