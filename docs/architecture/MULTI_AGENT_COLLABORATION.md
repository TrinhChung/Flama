# Flama Multi-Agent Collaboration Framework & Architecture

> Version: 1.0.0 | System Architecture Document | Project: Flama / Nihongo

This document defines the multi-agent collaboration architecture for Flama. It provides standard operational guidelines for coordinating specialized AI agents across Database, Backend, Frontend, and Documentation layers.

---

## 1. Multi-Agent Ecosystem Overview

```mermaid
flowchart TD
    User([User Prompt]) --> LeadAgent["$flama-agent-orchestrator\n(Lead Orchestrator)"]
    
    subgraph Plan Phase ["1. Planning & Contract Phase"]
        LeadAgent --> Contract["Inter-Layer Contract Spec\n(Schema DDL -> REST DTO -> TS Types)"]
    end

    subgraph Execution Phase ["2. Staged Subagent Execution"]
        Contract --> DBAgent["$flama-database-architecture\n(Database Agent)"]
        DBAgent -->|Schema & Migrations Ready| BEAgent["$flama-backend-architecture\n(Backend Agent)"]
        BEAgent -->|REST APIs & Services Ready| FEAgent["$flama-frontend-architecture\n(Frontend Agent)"]
    end

    subgraph Verification Phase ["3. Verification & Docs"]
        FEAgent --> DocsAgent["$docs-architect\n(Docs Agent)"]
        DocsAgent --> Audit["End-to-End Verification\n(Tests, Zero Visual Regression Check)"]
        Audit --> LeadAgent
    end

    LeadAgent --> FinalOutput([Complete Feature Solution])
```

---

## 2. Specialized Agent Roles & Boundaries

| Agent Persona | Skill Identifier | Target Workspace | Core Responsibility |
|---|---|---|---|
| **Lead Orchestrator** | `$flama-agent-orchestrator` | Entire Repository | Requirement analysis, task decomposition, API contract definition, agent dispatch, final verification. |
| **Database Architect** | `$flama-database-architecture` | `models/`, `migrations/` | Schema design, SQLAlchemy ORM mappings, zero-data-loss Alembic migrations, overlay clone modeling. |
| **Backend Architect** | `$flama-backend-architecture` | `app/api/`, `app/services/`, `app/repositories/`, `app/validators/`, `tests/` | Flask REST endpoints, service layer transaction management, Anki scheduling, payments, Yomitan bridge. |
| **Frontend Architect** | `$flama-frontend-architecture` | `frontend/src/` | React SPA components (FSD structure), custom hooks, state management, Tailwind styling, Zero Visual Regression. |
| **Docs Architect** | `$docs-architect` | `docs/`, `README.md`, `AGENTS.md` | Architecture docs, runbooks, setup guides, API specifications. |

---

## 3. Inter-Layer Contract Specification

To ensure seamless coordination between subagents working on separate layers, every full-stack feature must establish explicit contracts:

### A. Database -> Backend Contract
- **Schema Mapping**: Define SQLAlchemy model attributes, field types, nullability, foreign keys, and unique constraints.
- **Migration Guarantee**: Every schema update must include an Alembic migration script in `migrations/versions/`.

### B. Backend -> Frontend Contract (REST DTO)
- **JSON Payload Format**: Standardize request parameters and response JSON shapes.
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```
- **HTTP Status Codes**: `200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `404 Not Found`, `409 Conflict`, `422 Unprocessable Entity`.

### C. Frontend Interface Spec
- **TypeScript Types**: Declare interfaces matching Backend JSON payloads under `frontend/src/features/<feature>/types.ts` or `frontend/src/shared/types/`.
- **State Hooks**: Encapsulate API calls inside custom hooks (e.g., `useStudySession`, `useDeckMarketplace`).

---

## 4. Staged Execution Pipeline

1. **Step 1: Database Execution**:
   - DB Agent creates/modifies SQLAlchemy ORM models in `models/`.
   - DB Agent generates migration in `migrations/versions/`.
   - Verification: Run model tests or DB migration verification.

2. **Step 2: Backend Execution**:
   - BE Agent creates validators in `app/validators/`.
   - BE Agent creates repositories & services in `app/repositories/` and `app/services/`.
   - BE Agent exposes REST endpoints in `app/api/`.
   - Verification: Run backend tests under `tests/`.

3. **Step 3: Frontend Execution**:
   - FE Agent defines TypeScript types and API fetchers.
   - FE Agent extracts state management into custom hooks in `frontend/src/hooks/`.
   - FE Agent builds/updates React components in `frontend/src/` adhering to FSD layout and Zero Visual Regression.
   - Verification: Verify UI visual rendering and DevTools console clean state.

---

## 5. Non-Negotiable Quality Guardrails

1. **Zero Visual Regression**: Frontend modifications must preserve existing color palettes, brand gradients, typography, font sizes, padding, shadows, and responsive layout.
2. **Data Integrity First**: Database schema changes must be backward-compatible and zero-downtime (Expand -> Backfill -> Cutover -> Contract).
3. **Overlay-Only Shared Deck Integrity**: Shared decks use pointer overlay clones. Never mutate source notes when editing clone decks.
4. **Isolated Chrome DevTools**: All browser testing and DevTools profiling must use an isolated user profile directory.
