# Nihongo Flask Starter

Lightweight Flask + MySQL application for vocabulary learning, flashcards, marketplace installs, and payOS-based payment flows.

## Documentation

- Setup and basic commands: `README_SETUP.md`
- Payment architecture and operations: `docs/FLAMA_PAYMENT_ARCHITECTURE.md`
- System architecture overview: `docs/SYSTEM_ARCHITECTURE.md`
- Flashcard V2 migration runbook: `docs/FLASHCARD_V2_RUNBOOK.md`
- One-command DB reseed script: `scripts/reseed_db.sh`

## Core Features

- Flask application factory pattern with SQLAlchemy models.
- Environment-based configuration via `.env` and `python-dotenv`.
- Secure password hashing and session management handled by Flask-Login.
- Vocabulary management and flashcard study flows.
- Marketplace sharing for note types and decks.
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
|-- extensions.py       # Shared Flask extensions
|-- routes/             # Blueprints and HTTP entrypoints
|-- services/           # Business logic and orchestration
|-- repositories/       # Query and persistence helpers
|-- validators/         # Request validation and normalization
models/                 # SQLAlchemy model definitions
templates/              # Jinja2 templates
static/                 # Static assets
docs/                   # Technical documentation
```

## Payment Direction

The repository is payOS-first.

- `PAYMENTS_PROVIDER=payos` is the intended configuration.
- User-facing payment UI is limited to order history and order detail.
- Admin-facing payment UI is operational and centered on orders, transactions, and dashboard monitoring.
- Older payment migration notes are not part of the active architecture direction.

See `docs/FLAMA_PAYMENT_ARCHITECTURE.md` before changing the payment domain.
