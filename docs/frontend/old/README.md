# Archived Frontend Documentation

This directory (`docs/frontend/old/`) serves as the historical archive for retired frontend documentation, design token specifications, renderer architectures, and completed SPA migration plans.

---

## Purpose & Archival Policy

1. **Preservation of Context**: Documents placed here provide historical rationale and technical context on past frontend architectural decisions without cluttering the active documentation hierarchy.
2. **Read-Only Reference**: Files in this directory are preserved for archival and reference purposes only. They do not represent the current state of the Flama React 19 SPA.
3. **Active Ground Truth**: For current frontend architecture, design systems, and guidelines, refer to:
   - [**`docs/frontend/ARCHITECTURE.md`**](../ARCHITECTURE.md) — Authoritative React 19 SPA architecture, FSD slices, routing, and state management.
   - [**`docs/frontend/README.md`**](../README.md) — Developer quickstart, scripts, and component catalogs.
   - [**`docs/frontend/tech-debt/README.md`**](../tech-debt/README.md) — Frontend technical debt, oversized components, and pending refactors.

---

## Archive Index

### Architecture & Technical Research Documents

| Document | Original Location | Description |
|---|---|---|
| [**`TYPOGRAPHY_SYSTEM.md`**](TYPOGRAPHY_SYSTEM.md) | `docs/architecture/TYPOGRAPHY_SYSTEM.md` | Initial Design Token and Typography system specification for fonts, sizes, and layout primitives. |
| [**`CARD_TEMPLATE_SANDBOX_RENDERER.md`**](CARD_TEMPLATE_SANDBOX_RENDERER.md) | `docs/architecture/CARD_TEMPLATE_SANDBOX_RENDERER.md` | Security boundary and architecture for sandboxed iframe rendering of custom user card templates. |
| [**`FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md`**](FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md) | `docs/architecture/FRONTEND_ARCHITECTURE_SELECTION_RESEARCH.md` | Deep architectural trade-off analysis comparing SPA frameworks, bundlers, and styling approaches for Flama. |

### Migration & Task Workspaces

| Directory | Original Location | Description |
|---|---|---|
| [**`frontend-migration/`**](frontend-migration/) | `docs/task/frontend-migration/` | Complete history of the Jinja-to-React migration, G00 baseline mapping, and component extraction plans. |
| ↳ `FLAMA_FRONTEND_HIGH_ROI_SPECIFICATION_PLAN_2026-10-05.md` | `frontend-migration/` | High-ROI frontend modernization plan and feature delivery roadmap. |
| ↳ `FLASHCARD_EXTRACTION_CODEX_REVIEW_2026-10-05.md` | `frontend-migration/` | Code review and audit notes on flashcard renderer extraction. |
| ↳ `G00_BASELINE_AND_MAPPING.md` | `frontend-migration/` | Comprehensive inventory mapping Jinja server-rendered templates to React components. |
| ↳ `G00_CODEX_REVIEW_2026-10-04.md` | `frontend-migration/` | Independent review and acceptance record for the initial G00 migration slice. |
