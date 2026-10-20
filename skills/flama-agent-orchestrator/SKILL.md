---
name: flama-agent-orchestrator
description: Coordinate authorized multi-agent work on complex Flama changes spanning database, backend, frontend or documentation with explicit contracts and file ownership.
---

# Flama Agent Orchestrator

Use `AGENTS.md` and `docs/architecture/MULTI_AGENT_COLLABORATION.md`. Skills describe workflows; they do not create agents or grant tool access. Use the current host's actual delegation API only when delegation is authorized and useful. Small tasks can be completed by one agent.

1. Inspect the current diff and define the requested outcome, invariants and affected layers. Preserve other contributors' changes.
2. Agree on the actual contract: schema/nullability where relevant, endpoint/method, request and response examples, status/error shapes, pagination, authorization, array values, cache and revision semantics. Preserve existing response envelopes rather than imposing a new one.
3. Assign non-overlapping files or isolated worktrees. Each worker receives its paths, dependencies, public interfaces, tests and stop conditions. Shared files and integration remain owned by the lead. Do not have a worker recursively delegate unless needed and authorized.
4. Order work by dependencies. Schema-dependent work waits for its MySQL-verified migration; independent reviews, frontend work against an agreed contract, and documentation can proceed in parallel. Do not dispatch DB work for changes with no schema impact.
5. Review each diff and integrate contracts. Run focused tests, real MySQL checks for DB integration, and visual verification for UI changes. Report unexecuted checks and missing tools honestly.

Use `$flama-database-architecture` for models/migrations, `$flama-backend-architecture` for APIs/services, `$flama-frontend-architecture` for React, `$docs-architect` for documentation, and `$nihongo-agent-architect` for agent guidance. Read canonical `skills/<name>/SKILL.md` directly if the catalog is stale. If a source or tool is missing, report the name and prerequisite; do not claim another platform's review occurred or sign on its behalf.

When using an external CLI worker, follow its local skill, preserve the configured model unless the user requests otherwise, and use read-only permissions for review. An expired login stops that worker, not independent work by the lead. Never switch another agent's account to work around authentication.
