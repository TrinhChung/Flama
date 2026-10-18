# Flama Logs & Observability Hub

Welcome to the Flama Logs and Observability documentation hub. This directory covers the 12-factor application logging architecture, production journald streams, relational MySQL audit trails, multi-process healthchecks, and observability technical debt.

---

## 1. Domain Navigation & Document Index

| Document | Purpose & Scope |
|---|---|
| [**`ARCHITECTURE.md`**](./ARCHITECTURE.md) | **Authoritative Logs & Observability Architecture Guide**: 12-factor stdout/stderr logging streams, Gunicorn `--access-logfile - --error-logfile -` capture via `systemd-journald`, global exception handling in `app/__init__.py`, structured relational audit logs (`models/audit_log.py` 35+ checkpoints, `models/user_permission_audit_log.py`), and multi-tier healthchecks (`/api/health`, `/healthz`, `study_worker.py --check-ready`). |
| [**`tech-debt/README.md`**](./tech-debt/README.md) | **Observability Technical Debt Catalog**: Detailed documentation of [LOGS-DEBT-01] Structured JSON Logging, [LOGS-DEBT-02] Distributed Request Tracing / Correlation IDs, [LOGS-DEBT-03] Production Error Monitoring (Sentry Integration), [LOGS-DEBT-04] APM & Prometheus Metrics Exporter, and [LOGS-DEBT-05] Slow Query Logging. |
| [**`old/README.md`**](./old/README.md) | **Historical Archive**: Directory reserved for preserving retired performance audit probes, historical log analysis reports, and legacy incident postmortems. |

---

## 2. Quickstart for Site Reliability & Operators

### 2.1 Live Log Inspection (Journald)

```bash
# Follow live core web application logs (port 4789)
journalctl -u flama.service -f

# Follow live Flama Connect Yomitan bridge logs (port 4790)
journalctl -u flama-connect.service -f

# Follow live background study session batch worker
journalctl -u flama-study-worker.service -f

# Filter for errors and critical exceptions only
journalctl -u flama.service -p err..emerg -n 50 --no-pager

# Search logs for a specific user ID or exception string
journalctl -u flama.service --grep="Unhandled request exception"
```

### 2.2 Healthcheck & Readiness Probe Verification

```bash
# Verify Core Web & Database readiness (returns HTTP 200 {"status": "ok"})
curl -i http://127.0.0.1:4789/api/health

# Verify Flama Connect readiness (returns HTTP 200 {"status": "ok", "service": "flama-connect"})
curl -i http://127.0.0.1:4790/healthz

# Verify public edge health via Nginx
curl -i https://api.flama.vn/api/health
curl -i https://connect.flama.vn/healthz

# Run background worker readiness CLI probe (exits 0 if ready)
python study_worker.py --check-ready
echo "Worker check status: $?"
```

### 2.3 Querying MySQL Relational Audit Trails

```sql
-- Query the 10 most recent business audit actions
SELECT id, user_id, action, created_at, JSON_PRETTY(payload)
FROM audit_logs
ORDER BY created_at DESC
LIMIT 10;

-- Query recent Yomitan note mining actions
SELECT id, user_id, action, created_at, payload->'$.note_id' AS note_id
FROM audit_logs
WHERE action = 'connect.note.create'
ORDER BY created_at DESC
LIMIT 20;

-- Query recent administrative permission & role changes
SELECT id, actor_user_id, target_user_id, action, from_role_id, to_role_id,
       from_is_admin, to_is_admin, from_is_disabled, to_is_disabled, created_at
FROM user_permission_audit_logs
ORDER BY created_at DESC
LIMIT 15;
```

---

## 3. Directory Structure Overview (`models/` & `app/`)

```text
nihongo/
├── models/
│   ├── audit_log.py                  # AuditLog model (UUID, user_id, action, payload JSON)
│   └── user_permission_audit_log.py  # UserPermissionAuditLog model (actor, target, role delta)
├── app/
│   ├── __init__.py                   # Global exception handler & session rollback (lines 295–308)
│   ├── api/v1/health.py              # GET /api/health probe (MySQL SELECT 1 + Redis ping)
│   ├── connect/                      # GET /healthz probe for Flama Connect (port 4790)
│   └── services/                     # 35+ services emitting AuditLog records
├── deploy/
│   ├── flama.service                 # Gunicorn streaming to stdout/stderr via systemd
│   └── flama-connect.service         # Connect daemon error streaming
└── study_worker.py                   # Continuous study consumer with --check-ready CLI flag
```

---

## 4. Key Observability Guardrails

When working on logging, metrics, or auditing in Flama, you must adhere to these guardrails:

1. **12-Factor Logging (No File Handlers in App)**: Never configure `logging.FileHandler` or write log files inside `app/` or `wsgi.py`. Always emit to standard streams (`stdout` and `stderr`) and allow the runtime supervisor (`systemd-journald` or Docker daemon) to capture them.
2. **Never Log Plaintext Credentials or Tokens**: Never log passwords, API bearer tokens, Yomitan auth tokens, or payment checksum keys. URL-tokenized routes (`/v1/flama-connect/`, `/v1/mcp/`) must keep Nginx `access_log off;`.
3. **Always Roll Back Failed Sessions on Exception**: Unhandled HTTP exceptions must execute `_rollback_failed_session()` in `app/__init__.py` before returning HTTP 500 to prevent database connection pollution.
4. **Audit Trail Immutability**: Records in `audit_logs` and `user_permission_audit_logs` are write-only audit events. Never execute `UPDATE` or `DELETE` statements against these tables during routine operations.
5. **Mask Internal Details in 500 Responses**: Never return Python tracebacks, SQL queries, or internal error messages to client responses. Return sanitized JSON errors (`{"error": "INTERNAL_ERROR", "message": "Internal server error."}`).
