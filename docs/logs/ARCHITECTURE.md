# Flama Logs & Observability Architecture

- **Domain**: Application Logging, Security Audit Trails, Health Probes & Monitoring
- **Architecture Standard**: 12-Factor Logging (Stdout/Stderr Streams) & Relational Audit Logging
- **Last Verified**: 2026-10-15
- **Status**: Production Reference

---

## 1. Executive Summary & Observability Philosophy

Flama strictly adheres to the **12-Factor App** logging philosophy: application processes do not manage their own log files, rotate logs, or write to local disk paths. Instead:
1. **Operational Logging (Stdout/Stderr)**: All application events, diagnostic traces, Gunicorn access logs, and unhandled exceptions are streamed directly to `stdout` and `stderr`.
2. **Journald Aggregation**: In production on Hostinger Ubuntu VPS, `systemd-journald` captures these streams from systemd units (`flama.service`, `flama-connect.service`, `flama-study-worker.service`).
3. **Relational Audit Trails (MySQL)**: High-value business and security mutations (Yomitan mining, deck imports, role privilege escalations, marketplace transactions, payment payouts) are recorded in dedicated, queryable MySQL tables (`audit_logs` and `user_permission_audit_logs`).
4. **Health & Readiness Probes**: Multi-tier HTTP endpoints (`/api/health`, `/healthz`) and CLI probes (`study_worker.py --check-ready`) provide active health reporting for automated deployment verification and rollback triggers.

### 1.1 Observability Data Flow

```text
       ┌────────────────────────┐
       │   Gunicorn / Flask     │
       │   logging.getLogger()  │
       └───────────┬────────────┘
                   │
         (stdout / stderr stream)
                   │
                   ▼
       ┌────────────────────────┐
       │    systemd-journald    │
       │ (/var/log/journal/)    │
       └───────────┬────────────┘
                   │
     (journalctl -u flama.service -f)
                   │
                   ▼
           [ DevOps Operator ]

─────────────────────────────────────────────────────────────

       ┌────────────────────────┐
       │ Business Actions /     │
       │ Admin Privilege Events │
       └───────────┬────────────┘
                   │
      (AuditLog / UserPermissionAuditLog)
                   │
                   ▼
       ┌────────────────────────┐
       │ MySQL InnoDB Database  │
       │ (`audit_logs` table)   │
       │ (`user_permission_     │
       │   audit_logs` table)   │
       └────────────────────────┘
```

---

## 2. Application Logging Architecture

### 2.1 Logger Lifecycle & Instantiation

Loggers are predominantly instantiated per Python module using the standard logging factory:

```python
import logging
logger = logging.getLogger(__name__)
```

This pattern is implemented across more than 60 service, route, and repository modules (including `app/services/flashcards_share_service.py`, `app/connect/__init__.py`, `app/services/payout_service.py`, and `app/services/study_service.py`). In select application contexts—specifically health endpoints (`app/api/v1/health.py`) and media service helpers (`app/services/flama_connect_media_service.py`)—Flask's application proxy `current_app.logger` is utilized for request-bound error and warning logging.

### 2.2 Gunicorn Stream Mapping

In production, Gunicorn explicitly disables file-based logging and redirects both access and error logs to standard streams:

- **`deploy/flama.service` (line 13)**:
  ```ini
  ExecStart=/opt/flama/venv/bin/gunicorn --workers 2 --threads 4 --worker-class gthread --timeout 120 --bind 0.0.0.0:4789 --access-logfile - --error-logfile - wsgi:app
  ```
  `--access-logfile -` routes HTTP request logs to `stdout`.  
  `--error-logfile -` routes operational errors and worker traces to `stderr`.
- **`deploy/flama-connect.service` (line 14)**:
  ```ini
  ExecStart=/opt/flama/venv/bin/gunicorn --workers 1 --timeout 30 --bind 127.0.0.1:4790 --error-logfile - connect_wsgi:app
  ```
  Connect runs with access logs disabled for URL-tokenized privacy, routing errors to `stderr`.

### 2.3 Production Stream Inspection with Journald

Operators query logs via `systemd-journald`:

```bash
# Follow live web application logs
journalctl -u flama.service -f

# Follow live Flama Connect bridge logs
journalctl -u flama-connect.service -f

# Follow live study session batch consumer logs
journalctl -u flama-study-worker.service -f

# Query error logs across the last 2 hours
journalctl -u flama.service --since "2 hours ago" -p err..emerg

# Export logs for a specific incident window
journalctl -u flama.service --since "2026-10-15 10:00:00" --until "2026-10-15 10:30:00" --no-pager > incident_logs.txt
```

### 2.4 Unhandled Exception Handling (`app/__init__.py`)

Unhandled exceptions are intercepted by a global Flask error handler in `app/__init__.py` (lines 295–308):

```python
import logging
_rollback_failed_session()
logging.getLogger(__name__).error(
    "Unhandled request exception: %s",
    error,
    exc_info=True,
)
resp = jsonify({"error": "INTERNAL_ERROR", "message": "Internal server error."})
if request.path == "/media/proxy" or request.path.startswith("/media/proxy"):
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers.pop("Vary", None)
return resp, 500
```

**Key Safety Mechanics**:
1. **Transaction Isolation (`_rollback_failed_session()`)**: Automatically rolls back `db.session` to guarantee that uncommitted or corrupted database transactions do not leak into subsequent worker requests.
2. **Full Traceback (`exc_info=True`)**: Emits the complete Python exception traceback to `stderr` for capture by journald.
3. **Safe Error Masking**: Returns a generic JSON payload (`{"error": "INTERNAL_ERROR", "message": "Internal server error."}`) preventing internal database schemas, paths, or credentials from leaking to end users.
4. **Media Proxy Cache Invalidation**: Strips `Cache-Control` and `Vary` headers on `/media/proxy` error responses to prevent upstream CDNs (Cloudflare) from caching transient 500 errors.

---

## 3. Structured Relational Audit Trails (MySQL)

Flama records critical security and domain mutations in dedicated MySQL InnoDB audit tables.

### 3.1 Business Audit Trail: `models/audit_log.py` (`AuditLog`)

```python
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
```

#### Key Checkpoint Inventory (35+ Locations)

| Domain | Action Name | File & Line Reference | Payload Contents |
|---|---|---|---|
| **Yomitan Mining** | `connect.note.create` | `app/services/connect/actions.py:507` | `note_id`, `connect_note_id`, `deck_id`, `note_type_id`, `clone_install_id`, `media_count` |
| **Yomitan Import** | `connect.note.import` | `app/services/connect/import_cards.py:428` | `session_id`, `note_id`, `external_note_id`, `deck_id`, `note_type_id`, `created` |
| **Media Mining** | `connect.import_media.stage` | `app/services/flama_connect_media_service.py:227` | `session_id`, `media_id`, `sha256`, `size_bytes`, `mime_type` (also `.attach` at lines 590, 664) |
| **Deck Sharing** | `market.deck_item.create` & `market.deck_item.update` | `app/services/flashcards_share_service.py:785, 864` | `deck_item_id` (published marketplace item reference; also `.install` at line 1049) |
| **Deck Change Requests** | `market.deck_change_request.merge` | `app/services/change_request/merge.py:484` | `change_request_id`, `deck_item_id`, `deck_install_id`, `merge_status`, `dirty_change_count` |
| **Flashcard Import** | `note.import` & `note.batch_import` | `app/services/flashcard_import_api_service.py:240, 461` | `note_type_id`, `target_deck_id`, `mode`, `summary` |
| **Image Security** | `security.alert.triggered` | `app/services/image_security_service.py:111` | `threat_type`, `severity`, `message`, `source_url`, `details` |
| **Image Crawl** | `media.crawl.inline` or `media.crawl` | `app/services/image_crawl_service.py:345` | `note_id`, `asset_id`, `field_name`, `source_url` |
| **Payout Requests** | `payos.payout_batch.create_pending` & `payos.payout_batch.submitted` | `app/services/payout_service.py:112, 346` | `batch_id`, `reference_id`, `item_count` (also `.failed` at line 393) |
| **Token Management** | `integration_token.revoke` | `app/services/user_api_token_service.py:144` | `token_id` (also `integration_token.issue` at line 114, `integration_token.rotate` at line 164) |
| **Array Migration** | `field.convert_array` | `app/services/field_array_conversion_service.py:166` | `note_type_id`, `field_id`, `from_type`, `to_type`, `note_count`, `changed_note_count` |

### 3.2 Privilege & Administrative Audit Trail: `models/user_permission_audit_log.py`

```python
class UserPermissionAuditLog(db.Model):
    __tablename__ = "user_permission_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    from_role_id = db.Column(db.Integer, db.ForeignKey("user_roles.id"), nullable=True, index=True)
    to_role_id = db.Column(db.Integer, db.ForeignKey("user_roles.id"), nullable=True, index=True)
    from_is_admin = db.Column(db.Boolean, nullable=False, default=False)
    to_is_admin = db.Column(db.Boolean, nullable=False, default=False)
    from_is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    to_is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
```

- **Usage Sites**:
  - `app/services/admin_service.py:162`: Administrative role updates, promoting users to `Admin` or `Creator`.
  - `app/api/v1/admin/mcp_tokens.py:230`: MCP token administrative revocation and re-issuance.
  - User suspension and deactivation operations.
- **Security Audit Guarantee**: Every role modification records both the actor (admin) and the target user, along with pre-change and post-change boolean states (`is_admin`, `is_disabled`), providing complete non-repudiation.

---

## 4. Healthchecks & Readiness Probes

The system provides three distinct healthcheck mechanisms spanning web, extension bridge, and background worker processes:

### 4.1 Main Web & REST API Healthcheck (`app/api/v1/health.py`)

- **Endpoint**: `GET /api/health` (Port 4789). *(Note: `/api/v1/health` does not exist; Flask routes `health_bp` mounted on `api_v1_bp` exclusively to `/api/health`).*
- **Handler Implementation**:
  ```python
  @health_bp.get("/health")
  def health():
      """Confirm that the application and its database connection are ready."""
      db.session.execute(text("SELECT 1")).scalar_one()
      redis_required = any(
          redis_state_service.backend_mode(config_name) == "redis"
          for config_name in ("RATE_LIMIT_BACKEND", "MCP_PREVIEW_BACKEND")
      )
      if redis_required:
          try:
              redis_state_service.redis_client().ping()
          except Exception as exc:
              current_app.logger.error("Redis readiness check failed: %s", exc)
              return jsonify({"status": "unavailable", "dependency": "redis"}), 503
      return jsonify({"status": "ok"})
  ```
- **Responses**:
  - `200 OK`: `{"status": "ok"}` when MySQL executes `SELECT 1` and Redis responds to `PING`.
  - `503 Service Unavailable`: `{"status": "unavailable", "dependency": "redis"}` if Redis is down while required.
  - `500 Internal Server Error`: If MySQL connection fails.

### 4.2 Flama Connect Healthcheck (`app/connect/__init__.py:91–93`)

- **Endpoint**: `GET /healthz` (Port 4790, and reverse-proxied at `connect.flama.vn/healthz`).
- **Handler Implementation**:
  ```python
  @connect_bp.get("/healthz")
  def healthz():
      return jsonify({"status": "ok", "service": "flama-connect"})
  ```
- **Responses**:
  - `200 OK`: `{"status": "ok", "service": "flama-connect"}`. Confirms Gunicorn process on port 4790 is alive and accepting connections.

### 4.3 Background Study Worker Readiness Probe (`study_worker.py:23, 38–42`)

- **CLI Probe**: `python study_worker.py --check-ready`.
- **Implementation**:
  ```python
  if args.check_ready:
      from app.services.study_worker_readiness_service import has_ready_study_worker
      with app.app_context():
          return 0 if has_ready_study_worker("study-session.v4") else 1
  ```
- **Execution**: Evaluated during deployment activation in `deploy.yml:521–528`. Verifies that the asynchronous study session consumer is registered, connected to the `flama-production` Redis queue namespace, and ready to process learning batches before the deployment is marked successful.

---

## 5. Production Observability Baseline & Monitoring

### 5.1 System vs Domain Metrics

Flama makes a clear architectural distinction between:
- **System Metrics**: Host CPU, memory, open file descriptors, MySQL connection pool checkout times, and HTTP request percentiles. (Currently captured at the VPS host level via Netdata/htop and journald).
- **Domain Metrics**: High-level learning analytics (daily study streaks, mature card retention rates, deck install counters) computed periodically via systemd timer `flama-analytics-counts.timer` and stored in MySQL.

### 5.2 Log Retention & Rotation

Systemd handles journal retention according to host configuration in `/etc/systemd/journald.conf` (recommended operator production settings for Hostinger VPS):
- `SystemMaxUse=2G`: Limits journal storage to 2GB on disk.
- `SystemKeepFree=1G`: Guarantees at least 1GB disk space remains available for media storage.
- `MaxRetentionSec=1month`: Automatically expires journal records older than 30 days.
