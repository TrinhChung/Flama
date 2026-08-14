# Flama

React + Flask REST application for vocabulary learning, flashcards, marketplace installs, and payOS-based payment flows.

## Documentation

- Documentation Index: [`docs/README.md`](file:///d:/Project/nihongo/docs/README.md)
- Setup and basic commands: `README_SETUP.md`
- Flama Connect service (Yomitan/AnkiConnect bridge): `connect_wsgi.py` (port `4790`)
- Flama Audio Local TTS setup: [`flama-audio/README.md`](file:///d:/Project/nihongo/flama-audio/README.md) (port `4791`)
- System architecture overview: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](file:///d:/Project/nihongo/docs/architecture/SYSTEM_ARCHITECTURE.md)
- Payment architecture and operations: [`docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md`](file:///d:/Project/nihongo/docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md)
- Deck Change Request & collaboration: [`docs/plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`](file:///d:/Project/nihongo/docs/plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md)
- Flashcard V2 migration runbook: [`docs/runbooks/FLASHCARD_V2_RUNBOOK.md`](file:///d:/Project/nihongo/docs/runbooks/FLASHCARD_V2_RUNBOOK.md)
- One-command DB reseed script: `scripts/reseed_db.sh`

## Core Features

- Flask application factory pattern with SQLAlchemy models.
- React SPA owns all user-facing HTML; Flask serves REST and binary resources.
- Environment-based configuration via `.env` and `python-dotenv`.
- Secure password hashing and session management handled by Flask-Login.
- Vocabulary management and flashcard study flows with session undo/revert support.
- Marketplace sharing for note types and decks with logical-overlay clones.
- Deck Change Requests: collaborative contribution workflow with diff preview and conflict resolution.
- Flama Connect: Yomitan and AnkiConnect-compatible protocol server (`connect_wsgi.py` on port `4790`) for seamless browser word mining.
- Flama Audio: Local desktop TTS companion app (.NET 8 WPF on port `4791`) supporting VoiceVox and Kokoro engines.
- payOS-first payment domain centered on orders, payment attempts, webhook processing, and entitlements.
- Admin payment operations for order history, transaction history, and operational monitoring.
- User order history pages for clear order and payment visibility.

## Requirements

- Python 3.10+
- MySQL server with an empty schema (default name `flama`)
- Python dependencies listed in `requirements.txt`

## Project Structure

```text
wsgi.py                 # Flask entry point
app/
|-- __init__.py         # Application factory and configuration
|-- api/                # Canonical REST resources under /api
|-- extensions.py       # Shared Flask extensions
|-- routes/             # Protocol, binary and transition adapters
|-- services/           # Business logic and orchestration
|-- repositories/       # Query and persistence helpers
|-- validators/         # Request validation and normalization
models/                 # SQLAlchemy model definitions
frontend/               # React/Vite application
static/                 # Seed data, uploads and card-renderer host
docs/                   # Technical documentation
```

## Payment Direction

The repository is payOS-first.

- `PAYMENTS_PROVIDER=payos` is the intended configuration.
- User-facing payment UI is limited to order history and order detail.
- Admin-facing payment UI is operational and centered on orders, transactions, and dashboard monitoring.
- Older payment migration notes are not part of the active architecture direction.

See `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md` before changing the payment domain.
