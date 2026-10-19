# Flama Logs & Observability Technical Debt Catalog

- **Domain**: Application Logging, Telemetry, APM & Performance Observability
- **Last Audited**: 2026-10-15
- **Status**: Active Technical Debt Registry
- **Master Audit Report**: [Comprehensive Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md)

---

## 1. Executive Summary

Flama's current logging and observability architecture provides a solid baseline through 12-factor standard stream logging, systemd journal integration, and comprehensive MySQL business audit trails (`AuditLog`, `UserPermissionAuditLog`). However, modern cloud observability practices—specifically structured JSON logging, distributed correlation tracing, active application performance monitoring (APM), real-time exception alerting, and slow query profiling—are currently absent. This catalog details these technical debt items with concrete implementation designs. For cross-domain technical debt analysis and discrepancies catalog, see the master [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md).

---

## 2. Technical Debt Items

### [LOGS-DEBT-01] Structured JSON Logging

- **Category**: Log Ingestion & Machine Readability
- **Affected Files**: `app/__init__.py`, `deploy/flama.service`, `deploy/flama-connect.service`
- **Severity**: High
- **Current State**:
  Application log messages emitted via standard `logging.getLogger(__name__)` are plain text strings formatted using standard interpolation (e.g. `logger.info("Connect package authentication rejected status=%s", status)`). In multi-worker production Gunicorn setups, log lines from concurrent requests interleave without structured key-value metadata.
- **Operational Impact**:
  1. Automated log ingestion engines (Loki, Datadog, Elasticsearch, CloudWatch) must rely on fragile regex parsers to extract timestamps, log levels, request paths, and status codes.
  2. Contextual fields (such as `user_id`, `deck_id`, or `session_id`) cannot be indexed efficiently as structured dimensions for querying and filtering.
- **Remediation Plan**:
  1. Introduce a structured JSON logging formatter (using `python-json-logger` or standard library `json.dumps`) in `app/__init__.py`.
  2. Ensure each log event outputs standard JSON schema:
     ```json
     {
       "timestamp": "2026-10-15T15:00:00.123Z",
       "level": "INFO",
       "logger": "app.services.connect.actions",
       "message": "Connect package authentication rejected",
       "request_id": "req-9a8f3b2c",
       "user_id": 42,
       "path": "/v1/anki-connect",
       "status": "UNAUTHORIZED"
     }
     ```
  3. Keep plain text formatting enabled during local development via an environment toggle (`LOG_FORMAT=json` vs `LOG_FORMAT=text`).

---

### [LOGS-DEBT-02] Distributed Request Tracing / Correlation IDs

- **Category**: Distributed Tracing & End-to-End Request Tracking
- **Affected Files**: `deploy/flama.nginx.conf`, `app/__init__.py`, `app/connect/__init__.py`, `study_worker.py`
- **Severity**: High
- **Current State**:
  Requests traversing from Nginx -> Flask (:4789) -> Connect (:4790) or background workers (`study_worker.py`) have no shared correlation identifier.
- **Operational Impact**:
  1. When an end user experiences an error or study batch synchronization lag, operators cannot correlate the Nginx reverse proxy access log entry with the corresponding Flask route handler log or the background study consumer worker log.
  2. Investigating race conditions or multi-service transactions requires manual timestamp correlation across disjointed journald logs.
- **Remediation Plan**:
  1. In Nginx (`deploy/flama.nginx.conf`), generate an `X-Request-ID` header if not provided by Cloudflare:
     ```nginx
     proxy_set_header X-Request-ID $request_id;
     ```
  2. In Flask (`app/__init__.py`), attach `X-Request-ID` to Flask's request context `g.request_id` in a `before_request` hook, and return it in the client response header:
     ```python
     @app.before_request
     def set_request_id():
         g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

     @app.after_request
     def append_request_id(response):
         response.headers["X-Request-ID"] = getattr(g, "request_id", "")
         return response
     ```
  3. Include `request_id` automatically in all log records via a custom `logging.Filter`.
  4. Forward `request_id` into background study batch payloads consumed by `study_worker.py`.

---

### [LOGS-DEBT-03] Production Error Monitoring (Sentry Integration)

- **Category**: Incident Management & Real-Time Alerting
- **Affected Files**: `app/__init__.py` (lines 295–308), `requirements.txt`
- **Severity**: High
- **Current State**:
  When an unhandled exception occurs in `app/__init__.py`, it logs a stack trace to `stderr` and returns HTTP 500. There is no automated webhook, error aggregator, or alert notification dispatched.
- **Operational Impact**:
  1. High-severity regressions or payment webhook failures in production go unnoticed until end users report them or an operator manually runs `journalctl -u flama.service -p err`.
  2. Spikes in 500 errors cannot trigger automated incident management workflows or notifications to developer channels.
- **Remediation Plan**:
  1. Integrate `sentry-sdk[flask]` into `requirements.txt` and `app/__init__.py`.
  2. Gate initialization behind the `SENTRY_DSN` environment variable:
     ```python
     sentry_dsn = app.config.get("SENTRY_DSN")
     if sentry_dsn:
         import sentry_sdk
         from sentry_sdk.integrations.flask import FlaskIntegration
         from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

         sentry_sdk.init(
             dsn=sentry_dsn,
             integrations=[FlaskIntegration(), SqlalchemyIntegration()],
             traces_sample_rate=float(app.config.get("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
             environment=app.config.get("FLASK_ENV", "production"),
         )
     ```
  3. Configure alert rules in Sentry to notify the development team via Discord or Slack when unhandled 500 errors occur.

---

### [LOGS-DEBT-04] APM & Prometheus Metrics Exporter

- **Category**: Telemetry, Capacity Planning & APM
- **Affected Files**: `app/api/v1/health.py`, `app/settings.py`
- **Severity**: Medium
- **Current State**:
  System observability relies entirely on host-level OS tools (`top`, `netdata`) and domain-level database rollups (`flask --app wsgi.py analytics-counts-prewarm`). There is zero visibility into:
  - SQLAlchemy connection pool saturation (`DB_POOL_SIZE=4`, `DB_MAX_OVERFLOW=1`).
  - Redis connection latency and command throughput.
  - HTTP request duration percentiles (p50, p95, p99) per endpoint.
  - Active study worker queue depths.
- **Operational Impact**:
  1. If connection pool timeout exceptions occur (`QueuePool limit of size 4 overflow 1 reached`), operators have no historical time-series graphs showing when pool checkout spikes occurred.
  2. Capacity planning and latency degradation cannot be tracked proactively before outages occur.
- **Remediation Plan**:
  1. Implement a protected endpoint `GET /api/metrics` (or `GET /api/v1/metrics`) using `prometheus-client` or a lightweight native exporter.
  2. Expose key operational gauges and counters:
     - `flama_db_pool_size`, `flama_db_pool_checked_out`, `flama_db_pool_overflow`.
     - `flama_http_requests_total{status, method, path}`.
     - `flama_http_request_duration_seconds{path}`.
     - `flama_study_queue_depth{namespace}`.
  3. Protect the endpoint with an internal token or restrict access to `127.0.0.1` in Nginx.

---

### [LOGS-DEBT-05] Slow Query Logging via SQLAlchemy Execution Hooks

- **Category**: Database Performance & Query Optimization
- **Affected Files**: `app/__init__.py`, `models/__init__.py`
- **Severity**: Medium
- **Current State**:
  MySQL slow query logging is dependent on VPS-level MySQL server configuration (`slow_query_log=1`, `long_query_time=2`). However, queries generated by complex SQLAlchemy ORM joins (such as recursive deck tree rollups, clone scope lookups, or study queue batching) are not timed or logged within the application context.
- **Operational Impact**:
  1. When a complex query takes 800ms, it is invisible in application logs unless it exceeds the server-wide MySQL timeout.
  2. Developers cannot identify which specific route handler or service triggered the slow query without manually running `EXPLAIN` on database logs.
- **Remediation Plan**:
  1. Attach SQLAlchemy event listeners (`before_cursor_execute` and `after_cursor_execute`) to `db.engine` in `app/__init__.py`:
     ```python
     import time
     from sqlalchemy import event

     @event.listens_for(db.engine, "before_cursor_execute")
     def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
         context._query_start_time = time.perf_counter()

     @event.listens_for(db.engine, "after_cursor_execute")
     def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
         total = time.perf_counter() - context._query_start_time
         threshold = current_app.config.get("SLOW_QUERY_THRESHOLD_SECONDS", 0.5)
         if total > threshold:
             logger.warning(
                 "Slow query detected (%.3fs): %s | Params: %s",
                 total,
                 statement[:500],
                 parameters,
             )
     ```
  2. Emit warnings to journald whenever query execution exceeds 500ms, enabling rapid identification of N+1 regressions.
