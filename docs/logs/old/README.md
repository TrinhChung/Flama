# Archived Logs, Reports & Observability Documentation

This directory (`docs/logs/old/`) serves as the historical archive for retired audit reports, performance benchmark measurements, incident reviews, and legacy code audit notes.

---

## Purpose & Archival Policy

1. **Preservation of Context**: Documents placed here provide historical context on past system audits, performance benchmarks, and diagnostic investigations without cluttering the active documentation hierarchy.
2. **Read-Only Reference**: Files in this directory are preserved for archival and reference purposes only. They do not represent the current state of the Flama logging architecture or monitoring setup.
3. **Active Ground Truth**: For current logging standards, audit trail specifications, and observability guidelines, refer to:
   - [**`docs/logs/ARCHITECTURE.md`**](../ARCHITECTURE.md) — Authoritative logging architecture, systemd journald streams, MySQL audit trails, and healthchecks.
   - [**`docs/logs/README.md`**](../README.md) — Logs quickstart, log query recipes, and audit trail tables.
   - [**`docs/logs/tech-debt/README.md`**](../tech-debt/README.md) — Observability technical debt (APM, Prometheus, structured JSON logs).

---

## Archive Index

### Audit Reports & Performance Benchmarks (`reports/`)

The [**`reports/`**](reports/) directory contains completed codebase health audits, security incident analyses, and migration benchmarks:

| Report File | Description |
|---|---|
| [**`CODE_HEALTH_AUDIT_REPORT.md`**](reports/CODE_HEALTH_AUDIT_REPORT.md) | Comprehensive codebase health review, modularity metrics, and refactoring inventory (October 2026). |
| [**`LEGACY_CODEBASE_AUDIT_REPORT.md`**](reports/LEGACY_CODEBASE_AUDIT_REPORT.md) | Architectural survey of legacy routes, schema dependencies, and technical debt. |
| [**`ARRAY_MIGRATION_AUDIT_REPORT.md`**](reports/ARRAY_MIGRATION_AUDIT_REPORT.md) | Verification audit of native JSON array storage rollout across note fields and cards. |
| [**`FRONTEND_DECOMPOSITION_PLAN.md`**](reports/FRONTEND_DECOMPOSITION_PLAN.md) | Detailed architectural breakdown for decomposing monolithic React components and layouts. |
| [**`LEGACY_PERFORMANCE_IMPLEMENTATION_2026-10-10.md`**](reports/LEGACY_PERFORMANCE_IMPLEMENTATION_2026-10-10.md) | Benchmark implementation and query latency measurements for study progress and scheduler queries. |
| [**`ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md`**](reports/ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md) | Implementation report for materialized analytics counts aggregation. |
| [**`ISSUE_BROWSE_DUPLICATE_CARDS_MULTI_TEMPLATE.md`**](reports/ISSUE_BROWSE_DUPLICATE_CARDS_MULTI_TEMPLATE.md) | Diagnostic report on duplicate card representations in browse under multi-template occurrences. |
| [**`SECURITY_INCIDENT_2026-10-04_CLOUDFLARE_CLICKFIX.md`**](reports/SECURITY_INCIDENT_2026-10-04_CLOUDFLARE_CLICKFIX.md) | Incident report and remediation analysis regarding external security warnings. |
| [**`legal_uiux_audit_report.md`**](reports/legal_uiux_audit_report.md) | Legal and UI/UX compliance assessment. |
| [**`INVESTIGATION_EVENT_TIME_INVALID_STUDY_SESSION.md`**](reports/INVESTIGATION_EVENT_TIME_INVALID_STUDY_SESSION.md) | Diagnostic investigation of study session expiration and EVENT_TIME_INVALID synchronization issue. |
| [**`FULL_TEST_FAILURE_REPORT_2026-09-01.md`**](reports/FULL_TEST_FAILURE_REPORT_2026-09-01.md) | Historical full test suite failure investigation, isolation analysis, and route snapshot audit (September 2026). |
| [**`analytics-counts-2026-10-06/`**](reports/analytics-counts-2026-10-06/) | Raw snapshot outputs and execution metrics for prewarmed analytics count benchmarks. |

### Architecture & Code Reviews (`reviews/`)

The [**`reviews/`**](reviews/) directory contains formal review records for major commits and bug fixes:

| Review File | Description |
|---|---|
| [**`code-review-c2c5902-decoupling-docs-2026-08-25.md`**](reviews/code-review-c2c5902-decoupling-docs-2026-08-25.md) | Code and architecture review of commit `c2c5902` (decoupling documentation and database skills). |
| [**`REVIEW_TASK_BROWSE_CANONICAL_CARD_FIX.md`**](reviews/REVIEW_TASK_BROWSE_CANONICAL_CARD_FIX.md) | Code review and verification record for the canonical card query fix in browse card service. |
