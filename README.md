# Nihongo Flask Auth Starter

Lightweight Flask + MySQL starter project that focuses on user registration, login, and logout using Flask-Login.

## Documentation
- Setup and basic commands: `README_SETUP.md`
- One-command DB reseed script: `scripts/reseed_db.sh`
- Flashcard V2 migration runbook: `docs/FLASHCARD_V2_RUNBOOK.md`

## Core Features
- Flask application factory pattern with SQLAlchemy models.
- Environment-based configuration via `.env` and `python-dotenv`.
- Secure password hashing and session management handled by Flask-Login.
- Vocabulary management: duyệt danh sách bài chia tự động mỗi 60 từ, nhập liệu hàng loạt qua CSV và chỉnh sửa nhanh mọi trường dữ liệu ngay trong bảng.
- Giao diện bài học hỗ trợ kéo giãn cột và tự lưu kích thước cho từng tài khoản.
- Bootstrap 5 templates for a quick, responsive UI.

## Requirements
- Python 3.10+
- MySQL server with an empty schema (default name `flama`).
- Python dependencies listed in `requirements.txt` (includes `cryptography` for MySQL caching_sha2 auth and `Flask-Migrate` for database migrations).

## Project Structure
```
wsgi.py                 # Flask entry point
app/
├── __init__.py         # Application factory and configuration
├── extensions.py       # Shared Flask extensions (LoginManager)
├── routes/
│   ├── __init__.py     # Blueprint registration
│   ├── auth.py         # Authentication routes
│   ├── main.py         # Landing page and dashboard
│   └── vocabulary.py   # Vocabulary lessons, CSV import, deck editing
models/
├── __init__.py         # SQLAlchemy instance
├── user.py             # User model definition
└── vocabulary_entry.py # Vocabulary table schema
templates/              # Jinja2 templates
static/                 # Static assets
requirements.txt        # Python dependencies
.env                    # Environment configuration (never commit real secrets)
.venv/                  # Optional local virtual environment
```

## Flashcard V2 (Anki-like)
- New NoteType/FieldDef/Template/Note/Card/Media model is available.
- Management UI:
  - `/flashcards/note-types`
  - `/flashcards/note-types/<note_type_id>`
  - `/flashcards/notes/new`
  - `/flashcards/study`
- API root:
  - `/api/note-types`
  - `/api/notes`
  - `/api/study`

### Assumptions recorded for review
- Legacy data does not contain user ownership on `vocabulary_entries`; migration maps to one target user.
- Backward-compatible transition is preserved via `USE_NEW_CARD_MODEL=false` default.
- Field rename uses job-tracking record but executes synchronously in current version.
