# Flama Backend Documentation Hub

Welcome to the Flama Backend documentation directory. This hub covers the architecture, service topology, data models, and technical debt of the Flama Flask backend, persistence layer, and companion services.

---

## 1. Domain Navigation & Document Index

| Document | Purpose & Scope |
|---|---|
| [**`ARCHITECTURE.md`**](./ARCHITECTURE.md) | **Authoritative Technical Architecture Guide**: Flask Application Factory (`create_app()`, `MediaHardenedSessionInterface`, passive startup check), REST API layer (`app/api/v1/` alongside `app/routes/flashcards/study.py`), 102 SQLAlchemy models (Derived `Card` view ADR P11, `StudyProgressSubject` ADR P10, Overlay-only clone model `DeckInstall`), Anki SM-2 / FSRS scheduler, Flama Connect scheme CORS, and Flama Audio companion. |
| [**`tech-debt/README.md`**](./tech-debt/README.md) | **Technical Debt & Architectural Backlog**: Comprehensive catalog detailing `flashcards_share_service.py` (3,685 LOC monolith with 34 callers), `vocabulary.py` (718 LOC with 16 legacy 410 stubs), 40+ direct `db.session.commit()` calls in route handlers, and query bottlenecks. |
| [**`old/README.md`**](./old/README.md) | **Historical Archive**: Directory reserved for preserving retired backend architecture notes, historical ADRs, and completed migration plans. |

---

## 2. Quickstart for Backend Developers

### 2.1 Environment & Prerequisites
- **Python**: `3.12`
- **Virtual Environment**: `.venv`
- **Database**: MySQL 8.0 in production/local; in-memory SQLite used across automated test suites.

### 2.2 Common Commands

```powershell
# Activate Python virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Run modular test runner (preferred over running full suite)
python scripts/run_tests.py --changed
python scripts/run_tests.py --module study,flashcards
python scripts/run_tests.py --module auth --backend-only

# Run specific backend test file
python scripts/run_tests.py --file tests/test_oauth_mcp.py --backend-only

# Start Flama Core API server in development mode (port 4789)
python wsgi.py

# Start Flama Connect bridge in development mode (port 4790)
python connect_wsgi.py

# Run database migration (Alembic)
flask db upgrade

# Run administrative CLI commands
flask --help
flask deck-counts-status
flask review-analytics-status
```

---

## 3. Directory Structure Overview (`app/` and `models/`)

```text
nihongo/
├── app/
│   ├── __init__.py           # Flask application factory (create_app, create_audit_app)
│   ├── api/v1/               # Canonical REST API blueprints (/api/...)
│   ├── connect/              # Flama Connect Yomitan/AnkiConnect request pipeline
│   ├── extensions.py         # Extensions initialization (login_manager, migrate; db is in models)
│   ├── repositories/         # 46 data query repositories
│   ├── routes/               # Legacy route blueprints (study runtime, vocabulary)
│   ├── services/             # 167 business orchestration services
│   ├── settings.py           # Environment configuration loader
│   ├── spa.py                # Single-page app static delivery shell
│   ├── startup.py            # Startup maintenance and connectivity probes
│   ├── startup_schema.py     # Schema compatibility DDL inspection
│   └── validators/           # Request input validation logic
├── models/                   # 101 model files (111 SQLAlchemy models; db defined in models/__init__.py)
│   ├── card.py               # Derived presentation Card view (ADR P11)
│   ├── deck_install.py       # Logical overlay installation model
│   ├── note.py               # Note container with JSON array support
│   └── study_progress_subject.py # Decoupled study progress (ADR P10)
├── connect_wsgi.py           # Standalone entry point for Flama Connect (port 4790)
├── flama-audio/              # Local desktop TTS companion (.NET 8 WPF, port 4791)
├── study_worker.py           # Background CLI study session worker
└── wsgi.py                   # Primary application entry point (port 4789)
```

---

## 4. Key Engineering Guardrails

When developing on the Flama backend, you must adhere strictly to these rules:

1. **Preserve Overlay-Only Shared Deck Model**: Shared decks from Marketplace do not duplicate notes. Never reintroduce full-copy clone behavior or mutate source notes during clone editing.
2. **Native Array Preservation**: The `array` field type stores a JSON list in `notes.field_values`. Never flatten array values with `str()`. Flama does not export to Anki.
3. **Flama Connect Branding & Identity**: The application is **FLAMA**, and the extension bridge is **Flama Connect**. Never refer to the platform as "Anki" in documentation, logs, or error responses.
4. **Day-Boundary Scheduling**: Due counts and study intervals must use `_day_index()` in `anki_scheduler.py` based on the 04:00 AM local time boundary. Never invent custom date/time comparison math in route handlers.
5. **No Route Commits**: Route handlers must delegate transaction boundaries (`db.session.commit()`) to application services.
