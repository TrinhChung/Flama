# Flama

React 19 SPA + Flask REST modular monolith for Japanese spaced repetition (SRS) vocabulary learning, flashcards, marketplace installs, Yomitan mining, and payOS payment flows.

## Documentation

- **Master Documentation Portal**: [`docs/README.md`](docs/README.md)
- **Documentation Audit & Reality Report**: [`docs/DOCUMENTATION_AUDIT_REPORT.md`](docs/DOCUMENTATION_AUDIT_REPORT.md)
- **Core Architecture Guides**:
  - Frontend SPA Architecture: [`docs/frontend/ARCHITECTURE.md`](docs/frontend/ARCHITECTURE.md)
  - Backend & Persistence Architecture: [`docs/backend/ARCHITECTURE.md`](docs/backend/ARCHITECTURE.md)
  - Operations & Deployment Topology: [`docs/ops/ARCHITECTURE.md`](docs/ops/ARCHITECTURE.md)
  - Logging & Observability Guide: [`docs/logs/ARCHITECTURE.md`](docs/logs/ARCHITECTURE.md)
- **Setup & Quickstart**: [`README_SETUP.md`](README_SETUP.md)
- **Companion Services**:
  - Flama Connect service (Yomitan/AnkiConnect protocol bridge): `connect_wsgi.py` (port `4790`)
  - Flama Audio Local TTS setup: [`flama-audio/README.md`](flama-audio/README.md) (port `4791`)
- **Key Domain Guides & Runbooks**:
  - Flashcard V2 operational runbook: [`docs/runbooks/FLASHCARD_V2_RUNBOOK.md`](docs/runbooks/FLASHCARD_V2_RUNBOOK.md)
  - Database seeding guide: [`docs/guides/SEEDING_GUIDE.md`](docs/guides/SEEDING_GUIDE.md)
  - Shared deck clone cutover report: [`docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md`](docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md)
  - Deck Change Request & collaboration: [`docs/backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`](docs/backend/old/completed-plans/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md)
  - Payment architecture (payOS): [`docs/backend/old/FLAMA_PAYMENT_ARCHITECTURE.md`](docs/backend/old/FLAMA_PAYMENT_ARCHITECTURE.md)
- **One-command DB reseed script**: `scripts/reseed_db.sh` (or `scripts/reseed_db.ps1` on Windows)

## Core Features

- Flask application factory pattern (`app/__init__.py`) with passive production startup.
- React 19 SPA owns all user-facing UI; server-rendered Jinja templates have been eliminated.
- Multi-tier state persistence: TanStack Query v5 cache + IndexedDB (`flama-study` v2/v3) for crash-resilient study sessions.
- Derived virtual `Card` view (ADR P11) and Note-level study progress (`StudyProgressSubject` ADR P10).
- Marketplace sharing for note types and decks with logical-overlay clones (`DeckInstall`), preserving original author notes.
- Deck Change Requests: collaborative contribution workflow with diff preview and conflict resolution.
- Flama Connect: Yomitan and AnkiConnect-compatible protocol bridge (`connect_wsgi.py` on port `4790`) with automatic extension CORS authorization.
- Flama Audio: Local desktop TTS companion app (.NET 8 WPF on port `4791`) supporting VoiceVox and Kokoro neural engines.
- payOS-first payment domain centered on orders, payment attempts, webhook processing, and entitlements.
- Admin management for user accounts, role-based access control, fee schedules, and operational monitoring.

## Requirements

- Python 3.12 (the version in `.python-version`, used by CI and production)
- MySQL 8.0 server (default database name `flama`)
- Node.js 20+ (for `frontend/`)
- Python dependencies listed in `requirements.txt`

## Project Structure

```text
wsgi.py                 # Flask WSGI entry point (port 4789)
connect_wsgi.py         # Flama Connect Yomitan bridge entry point (port 4790)
study_worker.py         # Asynchronous study progress consumer
app/
|-- __init__.py         # Application factory and configuration
|-- api/v1/             # Canonical REST resources under /api
|-- connect/            # Flama Connect protocol request pipeline
|-- extensions.py       # Shared Flask extensions (login_manager, migrate)
|-- routes/             # Binary proxy, study, and protocol adapters
|-- services/           # Business orchestration and transaction ownership
|-- repositories/       # Query and persistence helpers
|-- validators/         # Request validation and normalization
models/                 # SQLAlchemy 2.0 declarative model definitions (102 models)
frontend/               # React 19 SPA (Vite, TailwindCSS v4, FSD structure)
flama-audio/            # Flama Audio .NET 8 WPF desktop companion
deploy/                 # Hostinger VPS deployment scripts, systemd units, Nginx configs
docs/                   # Technical documentation structured into 4 domain hubs
static/                 # Seed data, uploads and card-renderer host
```

## Payment Direction

The repository is payOS-first.

- `PAYMENTS_PROVIDER=payos` is the intended configuration.
- User-facing payment UI is limited to order history and order detail.
- Admin-facing payment UI is operational and centered on orders, transactions, and dashboard monitoring.
- Older payment migration notes are preserved for historical reference in [`docs/backend/old/FLAMA_PAYMENT_ARCHITECTURE.md`](docs/backend/old/FLAMA_PAYMENT_ARCHITECTURE.md).
