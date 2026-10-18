# Archived Operations & Infrastructure Documentation

This directory (`docs/ops/old/`) serves as the historical archive for retired deployment runbooks, superseded infrastructure specifications, and legacy migration procedures.

---

## Purpose & Archival Policy

1. **Preservation of Context**: Documents placed here provide historical context on past DevOps decisions, rollout phases, and migration milestones without cluttering the active documentation hierarchy.
2. **Read-Only Reference**: Files in this directory are preserved for archival and reference purposes only. They do not represent the current state of the Flama Hostinger VPS production deployment or CI/CD pipelines.
3. **Active Ground Truth**: For current infrastructure architecture, deployment topologies, and guidelines, refer to:
   - [**`docs/ops/ARCHITECTURE.md`**](../ARCHITECTURE.md) — Authoritative Hostinger systemd services, deploy workflows, quiesced migrations, Docker, and Nginx reverse proxy.
   - [**`docs/ops/README.md`**](../README.md) — Ops quickstart, directory layout, and operational procedures.
   - [**`docs/ops/tech-debt/README.md`**](../tech-debt/README.md) — Ops technical debt, Docker parity, and runner quota optimization.

---

## Archive Index

### Standalone Operational Runbooks

| Document | Original Location | Description |
|---|---|---|
| [**`FLAMA_AUDIO_WINDOWS_RELEASE.md`**](FLAMA_AUDIO_WINDOWS_RELEASE.md) | `docs/runbooks/FLAMA_AUDIO_WINDOWS_RELEASE.md` | Standard operating procedure for building, signing with Authenticode, and publishing `FlamaAudio-Portable.exe` releases. |
| [**`FLAMA_CONNECT_ASBPLAYER.md`**](FLAMA_CONNECT_ASBPLAYER.md) | `docs/runbooks/FLAMA_CONNECT_ASBPLAYER.md` | Configuration guide for Yomitan, asbplayer extension/web CORS origin handling, and Connect media cleanup. |
| [**`DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md`**](DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md) | `docs/runbooks/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md` | Operational rollout and rollback procedures for database progress scalability, field ID expansion, and shadow schema. |
| [**`ANALYTICS_COUNTS_RUNBOOK.md`**](ANALYTICS_COUNTS_RUNBOOK.md) | `docs/runbooks/ANALYTICS_COUNTS_RUNBOOK.md` | Prewarm and operational verification procedures for materialized analytics deck and review counts. |

### Historical Decoupling Runbooks (`historical-runbooks/`)

The [**`historical-runbooks/`**](historical-runbooks/) directory houses completed operational cutover and retirement runbooks from past engineering phases:

| Runbook File | Phase & Focus |
|---|---|
| [**`P5_NOTE_AUTHORITY_RUNBOOK.md`**](historical-runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md) | Phase 5 Note authority fence rollout and rollback verification |
| [**`P6_APPLICATION_OCCURRENCE_RUNBOOK.md`**](historical-runbooks/P6_APPLICATION_OCCURRENCE_RUNBOOK.md) | Phase 6 application occurrence transition runbook |
| [**`P7_SESSION_RETENTION_RUNBOOK.md`**](historical-runbooks/P7_SESSION_RETENTION_RUNBOOK.md) | Phase 7 study session retention and archive execution runbook |
| [**`P9_06_STORAGE_PROFILE_SWITCH_RUNBOOK.md`**](historical-runbooks/P9_06_STORAGE_PROFILE_SWITCH_RUNBOOK.md) | Phase 9 storage profile switch operational runbook |
| [**`P9_RETIREMENT_TELEMETRY_RUNBOOK.md`**](historical-runbooks/P9_RETIREMENT_TELEMETRY_RUNBOOK.md) | Phase 9 retirement telemetry and verification runbook |
| [**`P10_CONSOLIDATED_SWITCH_RUNBOOK.md`**](historical-runbooks/P10_CONSOLIDATED_SWITCH_RUNBOOK.md) | Phase 10 consolidated note progress switch runbook |
| [**`P10_09_RETIRED_TABLES_DROP_RUNBOOK.md`**](historical-runbooks/P10_09_RETIRED_TABLES_DROP_RUNBOOK.md) | Phase 10 drop retired legacy tables runbook |
