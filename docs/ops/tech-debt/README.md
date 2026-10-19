# Flama Operations Technical Debt Catalog

- **Domain**: Infrastructure, DevOps, Containerization & Deployment
- **Last Audited**: 2026-10-15
- **Status**: Active Technical Debt Registry
- **Master Audit Report**: [Comprehensive Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md)

---

## 1. Executive Summary

While Flama's production deployment pipeline on Hostinger VPS is robust—featuring quiesced database migrations, multi-process systemd isolation, and automated healthcheck rollbacks—local containerization and operational scripts exhibit several parity gaps and optimizations backlogs. This catalog documents these technical debt items with concrete remediation plans. For cross-domain technical debt analysis and discrepancies catalog, see the master [Documentation Audit Report](../../DOCUMENTATION_AUDIT_REPORT.md).

---

## 2. Technical Debt Items

### [OPS-DEBT-01] Parity in Development Docker Compose

- **Category**: Local Developer Environment & Containerization
- **Affected File**: `docker-compose.yml` (lines 14–32)
- **Severity**: High
- **Current State**:
  In `docker-compose.yml`, the `db` service runs MySQL 8.0 on port `3306`. However, the `web` application service definition is completely commented out (lines 14–32), and no Redis service is defined.
  ```yaml
  # web:
  #   build: .
  #   container_name: flama_app
  #   restart: always
  #   depends_on:
  #     - db
  #   ports:
  #     - "4789:4789"
  ```
- **Operational Impact**:
  1. Developers running `docker compose up` only get a MySQL container, not a working application environment.
  2. Onboarding documentation (`README_SETUP.md:148` and `scripts/setup_new_device.sh:89`) claims `--mode docker` runs the full stack in containers, but attempting to execute commands against the `web` container fails immediately (`No such container: flama_app`).
  3. Redis dependencies (rate limiting, study batch queues, MCP preview caching) cannot run in Docker out of the box.
- **Remediation Plan**:
  1. Create a modern, working `docker-compose.yml` (or `docker-compose.dev.yml`) that defines:
     - `db`: MySQL 8.0 with healthcheck (`mysqladmin ping`).
     - `redis`: Redis 7-alpine with volume persistence.
     - `web`: Flask backend mounted to local source code for live hot-reloading (`FLASK_ENV=development`).
     - `frontend`: Optional Vite development server container running on port 5173.
  2. Update `README_SETUP.md` and `scripts/setup_new_device.sh` to match the validated compose setup.

---

### [OPS-DEBT-02] Flama Connect Containerization Disparity

- **Category**: Multi-Process Containerization
- **Affected Files**: `Dockerfile` (lines 25–28), `connect_wsgi.py`
- **Severity**: Medium
- **Current State**:
  In `Dockerfile`:
  ```dockerfile
  EXPOSE 4789 4790

  # Chạy ứng dụng bằng gunicorn
  CMD ["gunicorn", "--bind", "0.0.0.0:4789", "wsgi:app"]
  ```
  The container exposes port `4790` (Flama Connect), but its `CMD` only launches Gunicorn against `wsgi:app` on port `4789`. `connect_wsgi.py` is never executed.
- **Operational Impact**:
  1. If Flama is deployed via Docker, Yomitan browser extension synchronization and MCP tool integration cannot function because port 4790 is dead.
  2. A single container cannot run both `wsgi:app` and `connect_wsgi:app` simultaneously without a process supervisor (such as `supervisord`) or a multi-container Docker Compose setup.
- **Remediation Plan**:
  - *Option A (Recommended)*: Split into distinct services in Docker Compose:
    - Service `web`: runs `gunicorn wsgi:app` on port 4789.
    - Service `connect`: runs `gunicorn connect_wsgi:app` on port 4790.
  - *Option B*: Introduce a lightweight entrypoint script using `supervisord` or `honcho` to manage both Python processes inside a single container if monolithic packaging is preferred.

---

### [OPS-DEBT-03] `.dockerignore` Context Optimization

- **Category**: Build Performance & Storage Efficiency
- **Affected File**: `.dockerignore` (lines 1–11)
- **Severity**: Medium
- **Current State**:
  `.dockerignore` only lists 8 basic patterns:
  ```text
  .git
  .github
  .env
  .venv
  **/__pycache__
  **/*.pyc
  frontend/node_modules
  frontend/dist
  .playwright-cli
  output
  ```
- **Operational Impact**:
  When `docker build` runs, the entire repository context is transmitted to the Docker daemon. Crucially, the following heavy directories are NOT ignored:
  1. `.agents/`: Contains over 420 subdirectories, memory files, transcripts, and benchmarks amounting to several hundred megabytes.
  2. `flama-audio/`: .NET 8 WPF desktop solution with its own `bin/`, `obj/`, and NuGet packages.
  3. `media/` and local SQLite `.db` files: Unnecessary binary data transferred into build layers.
  4. `tests/`: 230+ backend test files and mocks not needed in the production image.
  This causes build context transfer times to inflate from < 2 seconds to > 30–60 seconds.
- **Remediation Plan**:
  Update `.dockerignore` to include:
  ```text
  .agents
  flama-audio
  media
  tests
  *.db
  *.sqlite
  *.log
  docs
  ```

---

### [OPS-DEBT-04] Reseed Script Platform Consistency

- **Category**: Tooling & Developer Experience
- **Affected Files**: `scripts/reseed_db.sh` (lines 15–16), `scripts/reseed_db.ps1` (lines 10–25)
- **Severity**: Low
- **Current State**:
  - `scripts/reseed_db.sh` includes 6 steps. Step 2 explicitly runs:
    ```bash
    flask --app wsgi.py dev-purge-data --yes
    ```
    This completely purges existing cards, notes, and user progress before seeding.
  - `scripts/reseed_db.ps1` includes 5 steps and skips `dev-purge-data` entirely, seeding data on top of existing database rows.
- **Operational Impact**:
  1. A Linux/macOS developer running `reseed_db.sh` gets a completely wiped, clean state.
  2. A Windows developer running `reseed_db.ps1` gets duplicated or stacked seed data without purging old test entries.
  3. Divergent behavior causes subtle "it works on my machine" test discrepancies.
- **Remediation Plan**:
  Standardize the CLI interface for reseed scripts:
  - Add an optional flag `-Purge` / `--purge` to both scripts.
  - Make both scripts exhibit identical behavior by default (e.g. prompt before purging, or require `--purge` to wipe).

---

### [OPS-DEBT-05] Hostinger SSH Deployment Key Management & Healthcheck Retry Backoff

- **Category**: CI/CD & Deployment Reliability
- **Affected File**: `.github/workflows/deploy.yml` (lines 450–550)
- **Severity**: Low
- **Current State**:
  - `deploy.yml` runs a sequential healthcheck polling loop:
    ```bash
    for attempt in $(seq 1 20); do
      if curl http://127.0.0.1:4789/api/health && ...; then
        ...
      fi
      sleep 3
    done
    ```
  - The healthcheck uses a fixed linear sleep of 3 seconds (max 60 seconds).
  - On slow VPS I/O during heavy background migrations or cache warmup, the Gunicorn worker boot can experience transient timeouts before stabilizing.
  - Furthermore, failed deployments execute `rollback_activation` immediately, but do not emit structured webhook alerts (e.g. to Discord/Slack) notifying the team of an automated rollback event.
- **Remediation Plan**:
  1. Implement exponential backoff or configurable retry timeout (e.g. initial 3s, expanding up to 5s, max 90s) to absorb cold-start cache latency.
  2. Add an automated deployment failure notification step in `deploy.yml` via Discord or Slack webhook when `rollback_activation` is triggered.
