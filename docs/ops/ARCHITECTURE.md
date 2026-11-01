# Flama Operations & Infrastructure Architecture

- **Domain**: Infrastructure, Deployment, Edge Routing & Runtime Operations
- **Target Platform**: Hostinger Ubuntu VPS (Native Systemd) & Docker Containerization
- **Last Verified**: 2026-10-19 (deployment ownership and frontend hosting)
- **Status**: Production Reference

---

## 1. Executive Summary & Operational Topology

Flama is deployed in production on a Hostinger Ubuntu VPS using a systemd-managed native runtime, paired with an Nginx reverse proxy and Cloudflare edge SSL termination.

The frontend is deployed separately to Cloudflare Workers (`flama-frontend1001`,
`flama.vn`). Backend release activation runs under a durable VPS systemd coordinator;
SSH starts and observes it. See [Deployment and recovery](DEPLOY_RECOVERY.md) for
the current commands, status files and post-migration rollback constraints.

The production runtime is a multi-process architecture:
1. **Core Web & REST API (`flama.service`)**: Gunicorn running Flask application factory (`wsgi.py`) bound to `0.0.0.0:4789` (reverse-proxied locally via Nginx at `127.0.0.1:4789`) with 2 worker processes and 4 gthread threads.
2. **Flama Connect Bridge (`flama-connect.service`)**: Dedicated lightweight Gunicorn process (`connect_wsgi.py`) on `127.0.0.1:4790` providing Yomitan, asbplayer, and Model Context Protocol (MCP) tool integration.
3. **Durable Study Consumer (`flama-study-worker.service`)**: Continuous asynchronous worker (`study_worker.py`) consuming study sessions from Redis and persisting progress to MySQL.
4. **Scheduled Maintenance Timers**: Periodic systemd timer units executing analytics count rollups, review analytics event drains, temporary media eviction, and study session retention.
5. **Desktop Companion (`flama-audio/`)**: Local .NET 8 WPF desktop application running on port `4791` for end-user VoiceVox and Kokoro local TTS synthesis.

### 1.1 Architecture Topology Diagram

```text
[ Browser / Yomitan / asbplayer / AI Agents ]
                    │
                    ▼ (HTTPS 443)
       ┌───────────────────────────┐
       │     Cloudflare Edge       │
       └────────────┬──────────────┘
                    │
                    ▼ (HTTPS 443 with Origin Cert)
       ┌───────────────────────────┐
       │   Nginx Reverse Proxy     │
       │  (libnginx-mod-headers-   │
       │          more)            │
       └──────┬─────────────┬──────┘
              │             │
   (api.flama.vn)     (connect.flama.vn)
              │             │
              ▼             ▼
       ┌─────────────┐┌─────────────┐
       │flama.service││flama-connect│
       │  (Port 4789)││  (Port 4790)│
       └──────┬──────┘└──────┬──────┘
              │              │
              ├──────────────┴──────────────┬────────────────────────┐
              ▼                             ▼                        ▼
       ┌──────────────┐              ┌──────────────┐         ┌──────────────┐
       │ MySQL 8.0    │              │ Redis 7.x    │         │ /var/lib/    │
       │ (3306 Socket/│              │ (6379 Rate   │         │ flama/media/ │
       │  TCP)        │              │  Limit & Q)  │         │ (X-Accel)    │
       └──────────────┘              └──────┬───────┘         └──────────────┘
                                            │
                                            ▼
                                     ┌──────────────┐
                                     │ flama-study- │
                                     │ worker       │
                                     └──────────────┘
```

---

## 2. Hostinger VPS Production Deployment

### 2.1 Hostinger VPS Provisioning (`deploy/bootstrap_hostinger.sh`)

The script `deploy/bootstrap_hostinger.sh` bootstraps an Ubuntu Hostinger VPS for production execution:

- **Prerequisites Check (lines 9–21)**: Verifies presence of `mysql`, `nginx`, `openssl`, `python3`, `redis-cli`, and `libnginx-mod-http-headers-more-filter` (`/etc/nginx/modules-enabled/50-mod-http-headers-more-filter.conf`).
- **Dedicated System User (lines 23–25)**: Creates non-login system user `flama` (`useradd --system --home-dir /opt/flama --shell /usr/sbin/nologin flama`).
- **Directory Hierarchy & Permissions (lines 27–30)**:
  - Base Directory: `/opt/flama` (owner: `flama:flama`, mode `0755`)
  - Release Storage: `/opt/flama/releases`
  - Active Symlink: `/opt/flama/current` (points to `/opt/flama/releases/<sha>`)
  - Configuration Directory: `/etc/flama` (owner: `root:flama`, mode `0750`)
  - Media & Download Storage: `/var/lib/flama/media` and `/var/lib/flama/downloads` (owner: `flama:flama`, mode `0755`)
  - Virtual Environment: `/opt/flama/venv`, a symlink to `/opt/flama/venv-<python>` for the interpreter in `.python-version`
- **Environment File Creation (lines 31–98)**: Seeds `/etc/flama/flama.env` (owner: `root:flama`, mode `0640`) with randomized cryptographically secure secrets (`openssl rand -hex 32`).
- **Database & User Initialization (lines 155–161)**:
  ```sql
  CREATE DATABASE IF NOT EXISTS `flama` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS 'flama'@'127.0.0.1' IDENTIFIED BY '<password>';
  ALTER USER 'flama'@'127.0.0.1' IDENTIFIED BY '<password>';
  GRANT ALL PRIVILEGES ON `flama`.* TO 'flama'@'127.0.0.1';
  FLUSH PRIVILEGES;
  ```

### 2.2 Systemd Service Units

Production daemon processes are managed via systemd units located in `deploy/`:

| Systemd Unit | Working Directory | Command Line & Parameters | Resource & Security Hardening |
|---|---|---|---|
| `deploy/flama.service` | `/opt/flama/current` | `/opt/flama/venv/bin/gunicorn --workers 2 --threads 4 --worker-class gthread --timeout 120 --bind 0.0.0.0:4789 --access-logfile - --error-logfile - wsgi:app` | `PrivateTmp=true`, `ProtectSystem=full`, `ProtectHome=true`, `ReadWritePaths=/var/lib/flama`, `Nice=5`, `CPUWeight=100`, `KillSignal=SIGQUIT` |
| `deploy/flama-connect.service` | `/opt/flama/current` | `/opt/flama/venv/bin/gunicorn --workers 1 --timeout 30 --bind 127.0.0.1:4790 --error-logfile - connect_wsgi:app` | `PrivateTmp=true`, `ProtectSystem=full`, `ProtectHome=true`, `Environment=CONNECT_TRUST_PROXY=1`, `TimeoutStopSec=30`, `KillSignal=SIGQUIT` |
| `deploy/flama-study-worker.service` | `/opt/flama/current` | `/opt/flama/venv/bin/python study_worker.py` | `PrivateTmp=true`, `ProtectSystem=full`, `ProtectHome=true`, `ReadWritePaths=/var/lib/flama`, `TimeoutStopSec=150`, `KillSignal=SIGTERM` |

### 2.3 Systemd Timers & Scheduled Workers

Maintenance jobs run on isolated schedules managed by systemd timers:

1. **`flama-analytics-counts.service` & `.timer`**:
   - Schedule: Runs every 60 seconds (`OnUnitInactiveSec=60s`, `OnBootSec=30s`, `RandomizedDelaySec=5s`).
   - Command: `/usr/bin/flock --nonblock /run/flama-analytics-counts/runner.lock /opt/flama/venv/bin/flask --app wsgi.py analytics-counts-prewarm --configured --apply --max-decks 100 --max-buckets 4096` (prewarms learner deck counts and forecast buckets; each run finishes every 100-deck batch per learner through the keyset cursor, and each batch reads only its own decks' Notes).
   - Execution Condition: Guarded by `ExecCondition` verifying `DECK_COUNT_WRITE_ENABLED` is active and `DECK_COUNT_PREWARM_USER_IDS` is configured. With `DECK_COUNT_READ_MODE=summary`, only these learners read deck-count snapshots; others read raw counts.
2. **`flama-review-analytics-worker.service` & `.timer`**:
   - Schedule: Runs every 1 second (`OnUnitInactiveSec=1s`, `OnBootSec=5s`, `AccuracySec=100ms`).
   - Command: `/usr/bin/flock --nonblock /run/flama-review-analytics/runner.lock /opt/flama/venv/bin/flask --app wsgi.py review-analytics-drain --pending --apply --max-users 20 --max-revisions 100` (drains buffered review outbox projection events into analytics store in near real-time).
   - Execution Condition: Deploy (`sync_review_analytics_timer` in `deploy/activate_release.sh`) enables the timer only when the activated `/etc/flama/flama.env` turns `REVIEW_ANALYTICS_WRITE_ENABLED` on, and disables it otherwise; at a 1 s cadence the `ExecCondition` alone would start about 80k Python processes a day. The `ExecCondition` still skips runs if the flag is turned off without a deploy. After turning the flag on directly in `flama.env`, also run `systemctl enable --now flama-review-analytics-worker.timer`.
3. **`flama-connect-media-cleanup.service` & `.timer`**:
   - Schedule: Runs every 5 minutes (`OnBootSec=5min`, `OnUnitActiveSec=5min`, `Persistent=true`).
   - Command: `/opt/flama/venv/bin/flask --app connect_wsgi:app cleanup-connect-media` (purges orphaned Yomitan temporary audio/image uploads exceeding TTL).
4. **`flama-study-retention.service` & `.timer`**:
   - Schedule: Runs daily at 18:30:00 UTC (`OnCalendar=*-*-* 18:30:00 UTC` / 01:30 AM ICT, `RandomizedDelaySec=10m`).
   - Command: `/usr/bin/flock --nonblock /run/flama-study-retention/runner.lock /opt/flama/venv/bin/flask --app wsgi.py study-session-retention --apply --older-than-days 30 --batch-sessions 50 --batch-memberships 1000 --max-memberships 10000 --max-expired-sessions 1000 --max-seconds 60` (purges completed study sessions older than retention thresholds).
   - Execution Condition: Guarded by security approval gate `ConditionPathExists=/etc/flama/study-retention-approved` (execution is safely skipped unless operator creates the approval flag file).

### 2.4 Quiesced Deployment & Automated Rollback Contract (`deploy.yml`)

Production deployments are automated via GitHub Actions workflow `.github/workflows/deploy.yml`:

1. **Artifact Transfer**: Tarball release is unpacked into `/opt/flama/releases/<RELEASE_ID>`.
2. **Virtualenv Dependencies**: `/opt/flama/venv-<python>/bin/pip install -r requirements.txt`, using `python<version>` from `.python-version` (the version CI tests). A new interpreter gets a new venv while the old one still serves; `/opt/flama/venv` is relinked only after writers stop, and rollback relinks it back.
3. **Writers Quiescence (deploy.yml:461–469)**:
   All running service and timer units are strictly stopped before executing database migrations:
   ```bash
   for unit in flama.service flama-connect.service flama-study-worker.service \
     flama-analytics-counts.timer flama-analytics-counts.service \
     flama-review-analytics-worker.timer flama-review-analytics-worker.service; do
     if systemctl cat "$unit" >/dev/null 2>&1; then
       systemctl stop "$unit"
     fi
   done
   ```
4. **Quiesced Migration (`deploy/migrate_database.py --writers-quiesced`)**:
   Runs under a transient systemd unit (`flama-db-migrate-$RELEASE_ID`) with `STARTUP_RUN_MAINTENANCE=0 STARTUP_RUN_DB_CREATE_ALL=0 STARTUP_RUN_CLONE_CUTOVER=0`.
5. **Administrative Sync (`deploy.yml:478–484`)**:
   Runs `flask --app wsgi.py bootstrap-admin-sync` to ensure core admin users and system roles exist.
6. **Unit Installation & Symlink Switch (`deploy.yml:485–503`)**:
   Installs updated systemd unit files, moves managed environment file into place, and atomically switches the symlink:
   ```bash
   ln -sfn "$release_dir" "$PROJECT_DIR/current"
   ```
7. **Service Activation & Readiness Verification (`deploy.yml:516–541`)**:
   Polls for up to 20 attempts (3-second sleep intervals, 60s total) asserting that:
   - `http://127.0.0.1:4789/api/health` returns HTTP 200.
   - `http://127.0.0.1:4790/healthz` returns HTTP 200.
   - `flama-study-worker.service` is active in systemd.
   - `study_worker.py --check-ready` exits with code 0.
8. **Automated Rollback Trigger & Pre-Rollback Safety Gates (`deploy.yml:284–335`)**:
   If any healthcheck probe fails within 20 attempts, `deploy.yml` activates the `rollback_activation` subroutine. Rollback is not a naive symlink swap; it enforces **four mandatory pre-rollback safety gates** to prevent corrupting in-flight user data:
   - **Gate 1: HTTP/Connect Writer Quiescence**: Executes `systemctl stop flama.service flama-connect.service` and stops analytics timers. If incoming HTTP or extension writers fail to stop, automatic rollback is immediately halted (`"Automatic rollback blocked: HTTP/Connect writers did not stop"`).
   - **Gate 2: Study Progress Drain Gate**: Runs `study_worker.py --check-code-rollback --writers-quiesced`. Confirms that asynchronous study batches have safely drained to MySQL before restoring previous code. If uncommitted work remains, rollback is blocked to avoid discarding user review results.
   - **Gate 3: History Revision Drain Gate**: Stops `flama-study-worker.service` and executes `flask --app wsgi.py review-analytics-rollback-check --writers-quiesced`. Rejects rollback if pending review-history revisions remain in the durable outbox (`ASYNC_HISTORY_PENDING`).
   - **Gate 4: Field ID Contraction Guard (`deploy/check_field_code_rollback.py`)**: Runs `check_field_code_rollback.py --writers-quiesced --previous-release "$previous_release"`. If the database has already executed Phase 5 contraction (where `notes.field_values` was dropped in favor of `field-id.v1` storage), the guard inspects the previous release binary to ensure it declares `LIVE_FIELD_VALUE_CODEC = "field-id.v1"` and contains `field_value_runtime_service.py`. If the previous binary only understands legacy named storage, rollback is strictly blocked (`FIELD_ID_CODE_ROLLBACK_UNSUPPORTED`), requiring an isolated backup restore instead of corrupting field data.
   - **Restoration Sequence**: Only when all safety gates pass does the system restore `/etc/flama/flama.env.bak`, atomically point `/opt/flama/current` back to `$previous_release`, reinstall prior systemd units, restart services, and dump journal logs.
9. **Release Pruning (`deploy/prune_releases.py`)**:
   Upon success, cleans up older release directories, keeping the active release and the immediate prior release (retention = 2).

---

## 3. Nginx & Edge Routing Architecture

### 3.1 Domain & Virtual Host Routing

The production Nginx configuration separates public client traffic into two dedicated server blocks:

1. **`api.flama.vn` (`deploy/flama.nginx.conf`)**:
   - Serves the Single Page Application and canonical `/api/...` REST endpoints.
   - Forwards traffic to Gunicorn on `http://127.0.0.1:4789`.
   - Client body size: `client_max_body_size 20m;`.
2. **`connect.flama.vn` (`deploy/flama-connect.nginx.conf.example`)**:
   - Dedicated public host for Yomitan / Flama Connect browser extension syncing (`/v1/flama-connect`, `/v1/anki-connect`) and Model Context Protocol (MCP) tool integration (`/v1/mcp`, `/v1/mcp/`).
   - Forwards traffic to Gunicorn on `http://127.0.0.1:4790`.
   - Client body size: `client_max_body_size 2m;` (extended to `6m` for `/v1/anki-connect`).
   - Rate limit zone: `limit_req_zone $binary_remote_addr zone=flama_connect_ip:10m rate=2r/s; burst=60 nodelay;`.
   - MCP routes configure `proxy_read_timeout 60s` and disable access logging to protect bearer token privacy.

### 3.2 Protected Media Streaming via `X-Accel-Redirect`

To serve uploaded media (flashcard audio, images, vocabulary illustrations) efficiently without tying up Python worker threads, Flama utilizes Nginx `X-Accel-Redirect` (`deploy/flama.nginx.conf:30–58`):

```nginx
# Internal media serving (X-Accel-Redirect)
location /internal-media/ {
    internal;
    alias /var/lib/flama/media/;
    sendfile on;
    more_set_headers "Cache-Control: public, max-age=3600, s-maxage=86400";
    more_clear_headers "Vary" "Set-Cookie";
    add_header X-Content-Type-Options nosniff always;
    add_header Content-Security-Policy "default-src 'none'; sandbox" always;
}

location ^~ /media/proxy/ {
    proxy_pass http://127.0.0.1:4789;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_hide_header Vary;
    proxy_hide_header Set-Cookie;
    more_set_headers -s 400,403,404,405,410,500,502,503,504 "Cache-Control: no-cache, no-store, must-revalidate, max-age=0" "Pragma: no-cache";
}
```

**Data Flow**:
1. Client requests `GET /media/proxy/<asset_id>`.
2. Nginx proxies request to Flask (:4789).
3. Flask authenticates the request, verifies ownership/access, resolves storage path, and emits header:
   `X-Accel-Redirect: /internal-media/<subpath>` with `Content-Type`.
4. Nginx intercepts the header, cancels upstream pipe, and directly streams the file from `/var/lib/flama/media/<subpath>` via kernel `sendfile`.
5. Edge security headers (`Content-Security-Policy: default-src 'none'; sandbox`, `nosniff`) prevent SVG/HTML stored-XSS execution.

### 3.3 Edge WAF & Security Rules (`deploy/flama.nginx.conf:62–67`)

Nginx inspects query strings and rejects SQL injection signatures at the edge with HTTP 403 before requests reach Python:

```nginx
if ($query_string ~* "union.*select.*\(")        { return 403; }
if ($query_string ~* "select.+from")              { return 403; }
if ($query_string ~* "insert\s+into")            { return 403; }
if ($query_string ~* "drop\s+table")             { return 403; }
if ($query_string ~* "information_schema")        { return 403; }
if ($query_string ~* "sleep\((\s*)(\d*)(\s*)\)") { return 403; }
```

### 3.4 Flama Connect CORS & Extension Allowlist

Flama Connect validates request origins in both Nginx and Python:
- **Browser Extensions**: Any request with origin starting with `chrome-extension://` or `moz-extension://` is automatically permitted.
- **Trusted Web Applications**: Origin allowlist strictly limited to `https://killergerbah.github.io` and `https://asbplayer.dev`.
- **Non-browser Clients**: Requests without an `Origin` header (cURL, Python scripts) authenticate via Bearer token.
- **Unauthorized Web Origins**: Rejected with HTTP 403 without `Access-Control-Allow-Origin` headers.

---

## 4. Environment Configuration & Management

Configuration is loaded from environment variables in `app/settings.py` via `build_app_config()`. In production, variables reside in `/etc/flama/flama.env` (permissions `0640`, `root:flama`).

### 4.1 Configuration Groups

| Group | Key Variables | Default / Production Value | Description |
|---|---|---|---|
| **Database** | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | `127.0.0.1:3306`, user `flama` | Connection credentials for MySQL 8.0 InnoDB database. |
| **Pool Sizing** | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS` | `4`, `1`, `5`, `1800` | SQLAlchemy QueuePool configuration. Small pool size matches Gunicorn 2-worker / 4-thread architecture. |
| **Redis** | `REDIS_URL`, `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS`, `REDIS_SOCKET_TIMEOUT_SECONDS` | `redis://127.0.0.1:6379/0`, `1s`, `1s` | Redis instance for rate limiting and study batch queues. |
| **Study Workers** | `STUDY_QUEUE_NAMESPACE`, `STUDY_ASYNC_BATCH_ENABLED` | `flama-production`, `0` | Namespace prefix for study session queues; enables async background commit worker. |
| **Rate Limiting** | `RATE_LIMIT_BACKEND`, `RATE_LIMIT_DAILY_ENABLED`, `RATE_LIMIT_REGULAR_DAILY_MAX`, `RATE_LIMIT_CREATOR_DAILY_MAX`, `RATE_LIMIT_ENTERPRISE_DAILY_MAX` | `redis`, `true`, `300`, `2000`, `10000` | Redis-backed daily API quotas per user tier evaluated in `Asia/Ho_Chi_Minh` timezone. |
| **Auth Security** | `LOGIN_RATE_LIMIT_ENABLED`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `LOGIN_RATE_LIMIT_MAX_ATTEMPTS`, `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` | `true`, `60`, `5`, `300` | IP and account lockout rules for login attempts (5 failures in 60s locks for 5m). |
| **Connect / Yomitan** | `CONNECT_MAX_CONTENT_LENGTH`, `CONNECT_MEDIA_RATE_LIMIT`, `CONNECT_MEDIA_MAX_BYTES`, `CONNECT_PENDING_MEDIA_TTL_SECONDS` | `2097152` (2MB), `20/m`, `1048576` (1MB), `1800s` | Payloads, media size caps, and temporary asset retention for Yomitan mining. |
| **Media & Proxy** | `FLASHCARD_MEDIA_UPLOAD_ROOT`, `FLASHCARD_MEDIA_MAX_BYTES`, `MEDIA_PROXY_USE_XACCEL` | `/var/lib/flama/media`, `10485760` (10MB), `true` | Storage location and X-Accel offload toggle for flashcard assets. |
| **Payments** | `PAYMENTS_ENABLED`, `PAYMENTS_PROVIDER`, `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` | `0`, `payos` | payOS gateway integration for marketplace purchases and creator balances. |
| **Feature Flags** | `STARTUP_RUN_MAINTENANCE`, `REVIEW_ANALYTICS_WRITE_ENABLED`, `SHARED_DECK_TREE_CLONE_MODE` | `0`, `0`, `batched` | Startup mode (`0` = passive `SELECT 1`), review pipeline toggles, and deck tree cloning algorithm. |

---

## 5. Database Migrations & Versioning (Alembic)

Database schema evolution is managed via Flask-Migrate and Alembic (`migrations/`).

### 5.1 Migration Inventory (69 Versions & Lineage Topology)

The codebase contains exactly **69 migration files** in `migrations/versions/` (revisions spanning `000001` through `000068`).

**Lineage Branching & Merge Point**:
The migration graph is not purely linear; it contains a documented branch at revision 15 (`20260811_000015_enforce_marketplace_share_invariants.py`) where two parallel branches diverged:
- **Branch A (Deck Release Foundation)**: `20260812_000016_add_deck_release_foundation.py`
- **Branch B (Anki Sync & User Roles)**: `20260814_000016_add_anki_sync_provenance.py` ➔ `20260814_000017_add_anki_import_attempt_count.py` ➔ `20260820_000018_add_user_management_schema.py`
- **Merge Point**: Both branches merge cleanly at `20260820_000019_harden_deck_release_tracking.py` (`down_revision = ("20260812_000016", "20260820_000018")`).

**Key Architectural Migration Milestones**:
- Initial payment migrations: `20260327_000001_add_payment_domain_tables.py`
- Marketplace pricing refinement: `20260327_000002_rename_marketplace_price_columns.py`
- Decoupled progress (ADR P10): `20260913_000039_add_study_progress_shadow_schema.py`
- Template modernization: `20261012_000057_modernize_flashcard_templates.py`
- Field value identity cutover (Phase 1 Expansion through Phase 5 Contraction):
  - Phase 1 Expansion: `20261013_000063_expand_field_value_identity.py`
  - Phase 5 Contraction: `20261014_000067_contract_field_name_storage.py`
- Current Schema Head: `20261014_000068_add_review_outbox_fairness.py`

### 5.2 Zero-Downtime Multi-Phase Migration Pattern

To ensure zero data loss and avoid locking large tables in production, migrations follow a 5-phase expansion/contraction model:

```text
[ Phase 1: Expansion ]
  Add shadow columns/tables with nullable constraints.
        │
        ▼
[ Phase 2: Dual-Writing ]
  Application writes to both legacy and new structures. Reads remain on legacy.
        │
        ▼
[ Phase 3: Quiesced Runner & Backfill (`deploy/migrate_database.py`) ]
  Writers stopped. Backfill script migrates historical data in bounded batches.
        │
        ▼
[ Phase 4: Read Cutover ]
  Application switches reads to modern structure.
        │
        ▼
[ Phase 5: Contraction ]
  Drop legacy columns, constraints, and shadow tables.
```

### 5.3 Quiesced Migration Runner (`deploy/migrate_database.py`)

During deployment, migrations are executed exclusively via `deploy/migrate_database.py`:
- **Enforced Quiescence (lines 18–20)**: Checks `--writers-quiesced`. Raises `ValueError` if invoked while writers are active.
- **Two-Step Cutover (lines 32–37)**: If field values cutover is needed, upgrades to revision `20261014_000066`, executes `scripts.cutover_field_value_identity.prepare_cutover(apply=True, batch_size=200)`, and finally upgrades to migration head.
- **Dialect Safety (`migrations/env.py`)**: Uses `render_as_batch=True` on SQLite during unit tests, while using online DDL without table rebuilds on MySQL production.

---

## 6. Database Seeding & CLI Commands

### 6.1 Reseed Workflows Comparison

The repository provides automated database reseeding scripts for Linux/macOS and Windows:

| Step | Linux/macOS (`scripts/reseed_db.sh`) | Windows PowerShell (`scripts/reseed_db.ps1`) | Operation Performed |
|---|---|---|---|
| Step 1 | `flask --app wsgi.py db upgrade` | `flask --app wsgi.py db upgrade` | Applies all pending Alembic migrations to schema head. |
| Step 2 | `flask --app wsgi.py dev-purge-data --yes` | *(Skipped by default)* | Wipes user notes, cards, and custom decks. Omitted on Windows to avoid accidental developer data loss. |
| Step 3 | `python scripts/seed_flama_template.py` | `python scripts/seed_flama_template.py` | Seeds default Note Types, templates, and field definitions. |
| Step 4 | `flask --app wsgi.py user-role-seed` | `flask --app wsgi.py user-role-seed` | Seeds system roles: `Admin`, `Creator`, `Learner`. |
| Step 5 | `flask --app wsgi.py taxonomy-seed` | `flask --app wsgi.py taxonomy-seed` | Seeds Marketplace categories, tags, and JLPT levels. |
| Step 6 | `flask --app wsgi.py vocab-seed ...` | `flask --app wsgi.py vocab-seed ...` | Seeds sample decks from `static/seed_data/`. |

### 6.2 Seed Datasets (`static/seed_data/`)

- `ChungBech/`: `ChungBechN1__言葉__Bài 01.txt` (36KB TSV vocab deck).
- `徹底N1/`: `ChungBechN1__語彙徹底N1.txt` (9.1MB exhaustive JLPT N1 vocabulary collection).
- `strokes/`: Kanji/Hanzi stroke vector databases (`kanjivg_chars.json`, `makemeahanzi_chars.json`, `zh_production_hanzi.json`, `zh_hant_production_hanzi.json`).

### 6.3 Essential CLI Commands

```powershell
# Check database migration version
flask --app wsgi.py db current

# Upgrade database to latest revision
flask --app wsgi.py db upgrade

# Seed system roles (Admin, Creator, Learner)
flask --app wsgi.py user-role-seed

# Seed taxonomy (JLPT, grammar, vocabulary categories)
flask --app wsgi.py taxonomy-seed

# Bootstrap or synchronize admin credentials
flask --app wsgi.py bootstrap-admin-sync

# Inspect pending review analytics outbox status
flask --app wsgi.py review-analytics-outbox-status --max-users 20

# Drain review analytics outbox events to projection tables
flask --app wsgi.py review-analytics-drain --pending --apply --max-users 20 --max-revisions 100

# Prewarm learner deck counts and forecast buckets
flask --app wsgi.py analytics-counts-prewarm --configured --apply --max-decks 100 --max-buckets 4096

# Clean up expired Yomitan temporary media (registered on connect_wsgi:app)
flask --app connect_wsgi:app cleanup-connect-media
```

---

## 7. CI/CD Pipelines (`.github/workflows/`)

Flama implements a 4-tier GitHub Actions continuous integration and deployment pipeline:

```text
[.github/workflows/ci.yml]
  ├── minimal-matrix-planner (scripts/run_tests.py --ci-plan)
  ├── frontend (Oxlint, Typecheck, Vitest, Vite build, Flask SPA artifact contract)
  ├── backend (Modular Unittest/Pytest based on git diff)
  ├── redis-contract
  └── mysql-contract (MySQL 8 service container: probes & migrations)
          │
  (Master branch success)
          │
          ▼
[.github/workflows/deploy.yml]
  ├── tarball build & Hostinger SSH upload
  ├── venv pip install
  ├── writers quiescence (stop services & timers)
  ├── deploy/migrate_database.py --writers-quiesced
  ├── systemctl restart services & enable timers
  └── healthcheck probe loop (/api/health, /healthz, study_worker)
```

1. **`ci.yml` (428 lines)**:
   - Triggers on push/PR to `master` and `develop`.
   - Uses `scripts/run_tests.py --ci-plan` to compute minimal test execution requirements based on changed paths.
   - Spawns MySQL 8.0 and Redis services in CI for database contract tests (`mysql-contract` job runs 14 probe scripts validating field identity, concurrency, outbox fairness, and study session retention).
2. **`deploy.yml` (558 lines)**:
   - Triggered automatically via `workflow_call` upon successful `master` CI build, or manually via `workflow_dispatch`.
   - Executes remote SSH deployment to Hostinger VPS with automated rollback on failure.
3. **`flama-audio-ci.yml` & `flama-audio-release.yml`**:
   - Builds, tests, and packages the .NET 8 WPF Flama Audio desktop companion (`FlamaAudio-Portable.exe`).

---

## 8. Current Docker Containerization State

### 8.1 Docker Compose (`docker-compose.yml`)

The repository includes `docker-compose.yml`:

```yaml
services:
  db:
    image: mysql:8.0
    container_name: flama_db
    restart: always
    environment:
      MYSQL_DATABASE: flama
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD:-your-db-password}
    volumes:
      - flama_db_data:/var/lib/mysql
    ports:
      - "3306:3306"

  # web:
  #   build: .
  #   container_name: flama_app
  #   restart: always
  #   depends_on:
  #     - db
  #   ports:
  #     - "4789:4789"
  #   environment:
  #     - FLASK_APP=wsgi.py
  #     - FLASK_ENV=production
  #     - SECRET_KEY=${SECRET_KEY}
  #     - DB_HOST=db
  #     - DB_PORT=3306
  #     - DB_USER=root
  #     - DB_PASSWORD=${DB_PASSWORD:-your-db-password}
  #     - DB_NAME=flama
  #     - FLASHCARD_MEDIA_MAX_BYTES=10485760
```

- **Current Status**: Docker Compose is used **exclusively for hosting the local MySQL 8.0 database**.
- The `web` container definition (lines 14–32) is commented out.
- Redis is not defined in `docker-compose.yml`.

### 8.2 Dockerfile Multi-Stage Build

The root `Dockerfile` builds a production-ready image:
- **Stage 1 (`frontend-build`)**: `node:22-alpine` runs `npm ci` and `npm run build`.
- **Stage 2 (Runtime)**: `python:3.11-slim` installs `requirements.txt` and `gunicorn`, copies backend source and `frontend/dist`.
- **Exposed Ports**: `EXPOSE 4789 4790`.
- **CMD**: `CMD ["gunicorn", "--bind", "0.0.0.0:4789", "wsgi:app"]`.
- **Limitation**: While port `4790` is exposed, Gunicorn only executes `wsgi:app` on port `4789`. Flama Connect (`connect_wsgi:app`) is not launched within this container.

### 8.3 Context Optimization (`.dockerignore`)

`.dockerignore` contains basic exclusions:
- `.git`, `.github`, `.env`, `.venv`, `__pycache__`, `frontend/node_modules`, `frontend/dist`.
- **Optimization Needed**: Missing exclusions for `.agents/`, `flama-audio/`, `media/`, and `tests/`.
