# Flama Operations & Infrastructure Hub

Welcome to the Flama Operations documentation hub. This directory covers the production deployment topology, systemd daemon management, Nginx edge proxying, database migrations, CI/CD automation, and operational technical debt.

---

## 1. Domain Navigation & Document Index

| Document | Purpose & Scope |
|---|---|
| [**`ARCHITECTURE.md`**](./ARCHITECTURE.md) | **Authoritative Operations Architecture Guide**: Production deployment topology on Hostinger Ubuntu VPS (`deploy/bootstrap_hostinger.sh`), systemd daemon units (`flama.service`, `flama-connect.service`, `flama-study-worker.service`), maintenance timers, Nginx reverse proxy with `X-Accel-Redirect` protected media streaming and edge WAF rules, environment configuration groups (`/etc/flama/flama.env`), 69 Alembic migration versions, quiesced runner (`deploy/migrate_database.py`), database seeding, and Docker containerization. |
| [**`tech-debt/README.md`**](./tech-debt/README.md) | **Operations Technical Debt Catalog**: Detailed documentation of [OPS-DEBT-01] Parity in Development Docker Compose, [OPS-DEBT-02] Flama Connect Containerization, [OPS-DEBT-03] `.dockerignore` Context Optimization, [OPS-DEBT-04] Reseed Script Platform Consistency, and [OPS-DEBT-05] Hostinger SSH Key Management & Healthcheck Retries. |
| [**`old/README.md`**](./old/README.md) | **Historical Archive**: Directory reserved for preserving retired rollout runbooks, legacy cutover plans, and historical infrastructure procedures. |

---

## 2. Quickstart for DevOps & Operators

### 2.1 Hostinger VPS Environment & Paths

- **Application Root**: `/opt/flama`
- **Active Release Symlink**: `/opt/flama/current`
- **Releases Directory**: `/opt/flama/releases/<sha>`
- **Python Virtualenv**: `/opt/flama/venv` → `/opt/flama/venv-<python>` (interpreter from `.python-version`, installed from the deadsnakes PPA; system `python3` stays untouched)
- **Configuration File**: `/etc/flama/flama.env` (permissions `0640`, owner `root:flama`)
- **Media Assets Storage**: `/var/lib/flama/media` (owner `flama:flama`)
- **System User**: `flama` (non-login system account)

### 2.2 Common Systemd Operational Commands

```bash
# Check status of application daemons
systemctl status flama.service
systemctl status flama-connect.service
systemctl status flama-study-worker.service

# View live streaming logs via journald
journalctl -u flama.service -f
journalctl -u flama-connect.service -f
journalctl -u flama-study-worker.service -f

# Check scheduled maintenance timers
systemctl list-timers 'flama-*'

# Restart application services after configuration update
systemctl restart flama.service
systemctl restart flama-connect.service
systemctl restart flama-study-worker.service
```

### 2.3 Database Migration & Seeding Commands

```bash
# Check current database migration version
flask --app wsgi.py db current

# Apply pending Alembic migrations in development
flask --app wsgi.py db upgrade

# Run production quiesced migration (writers MUST be stopped)
python deploy/migrate_database.py --writers-quiesced

# Run full database reseed in development
# On Linux/macOS:
bash scripts/reseed_db.sh

# On Windows PowerShell:
.\scripts\reseed_db.ps1
```

### 2.4 Nginx Edge Proxy Commands

```bash
# Test Nginx configuration syntax
sudo nginx -t

# Reload Nginx configuration without dropping connections
sudo systemctl reload nginx

# Check Nginx error and access logs
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

---

## 3. Directory Structure Overview (`deploy/`)

```text
nihongo/
├── deploy/
│   ├── bootstrap_hostinger.sh        # Hostinger VPS initial host provisioning script
│   ├── flama.service                 # Systemd unit for core Flask API (port 4789)
│   ├── flama-connect.service         # Systemd unit for Flama Connect daemon (port 4790)
│   ├── flama-study-worker.service    # Systemd unit for asynchronous study batch consumer
│   ├── flama-analytics-counts.*      # Systemd service & timer for count rollups
│   ├── flama-review-analytics-worker.* # Systemd service & timer for analytics event drain
│   ├── flama-connect-media-cleanup.* # Systemd service & timer for temporary media cleanup
│   ├── flama-study-retention.*       # Systemd service & timer for study session retention
│   ├── flama.nginx.conf              # Production Nginx config for api.flama.vn & X-Accel
│   ├── flama-connect.nginx.conf.example # Production Nginx config for connect.flama.vn
│   ├── check_field_code_rollback.py  # Guard blocking rollback to named-storage binaries after field contraction
│   ├── migrate_database.py           # Quiesced multi-step Alembic migration runner
│   ├── prune_releases.py             # Release retention manager (keeps last 2 releases)
│   └── sync_managed_env.py           # Remote /etc/flama/flama.env synchronization tool
├── .github/workflows/
│   ├── ci.yml                        # Matrix CI workflow with MySQL and Redis service containers
│   ├── deploy.yml                    # Automated SSH deployment and rollback workflow
│   ├── flama-audio-ci.yml            # CI for .NET 8 WPF companion
│   └── flama-audio-release.yml       # Release packager for FlamaAudio-Portable.exe
├── docker-compose.yml                # Local MySQL 8.0 database container service
├── Dockerfile                        # Multi-stage Docker image build
└── .dockerignore                     # Docker build context exclusions
```

---

## 4. Key Operational Guardrails

When operating or maintaining Flama infrastructure, strictly follow these guardrails:

1. **Quiescence Before Migration**: Never run schema contractions or `deploy/migrate_database.py` while HTTP or Connect writers are active. Writers must be completely stopped via systemd before running migrations.
2. **Never Commit Secrets in Repo**: Sensitive credentials (`SECRET_KEY`, `DB_PASSWORD`, `PAYOS_*`) belong exclusively in `/etc/flama/flama.env` and GitHub Secrets.
3. **Preserve X-Accel-Redirect Media Security**: Media files in `/var/lib/flama/media` must never be served directly without going through Flask authorization. Nginx `/internal-media/` must always retain the `internal;` directive and strict CSP sandboxing.
4. **Flama Connect Extension CORS**: Never add wildcard `Access-Control-Allow-Origin: *` to Flama Connect endpoints. Extensions (`chrome-extension://`, `moz-extension://`) are auto-approved, while web origins are strictly limited to allowlisted domains.
5. **Two-Release Retention**: Production deployments retain exactly the active release and the prior release in `/opt/flama/releases` for rapid automated rollback. Never manually purge releases without `deploy/prune_releases.py`.
