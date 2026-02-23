# Flama (Nihongo) System Architecture

## 1. Overview
Flama is a lightweight web application designed for vocabulary learning. It provides user authentication, vocabulary management (bulk import, inline editing), and a spaced repetition flashcard system inspired by Anki.

## 2. Technology Stack
- **Backend Framework**: Python 3.10+, Flask
- **Database**: MySQL 8.0
- **ORM & Migrations**: SQLAlchemy with Flask-Migrate (Alembic)
- **Frontend**: HTML5, Vanilla JavaScript, CSS (Bootstrap 5 & Custom Component Architecture)
- **Containerization**: Docker & Docker Compose
- **Authentication**: Flask-Login (session-based)

## 3. Application Structure
The backend follows the Flask Application Factory pattern to ensure clean configuration and testing.

### 3.1 Directory Layout
- `app/`: Main application package
  - `__init__.py`: Application factory (`create_app`), initializes extensions, and registers blueprints.
  - `extensions.py`: Shared Flask extensions (e.g., `login_manager`, `migrate`).
  - `routes/`: Application controllers/blueprints covering different domains (`auth.py`, `main.py`, `vocabulary.py`, `flashcards.py`, `admin.py`).
  - `services/`: Encapsulated business logic (e.g., role management).
  - `cli.py`: Custom Flask CLI commands for administrative tasks (like data seeding).
- `models/`: SQLAlchemy data model definitions.
- `templates/`: Jinja2 templates, highly structured to promote reusability (`templates/components/`).
- `static/`: Static assets including styling, client-side scripts, images, and user-uploaded media.
- `docs/`: Technical documentation (Runbooks, Architecture guides).

## 4. Data Architecture
The application connects to a MySQL database, with the schema fully defined and managed by SQLAlchemy.

### 4.1 Core Domains
- **Identity & Access Management**: 
  - `User`, `UserRole` (Handles authentication and authorization)
- **Legacy Vocabulary System**: 
  - `VocabularyDeck`, `VocabularyEntry`, `VocabularyProgress`, `VocabularyColumnPreference` (Supports table-based inline editing and basic vocabulary tracking).
- **Flashcard V2 (Anki-like System)**:
  - **Schema Definition**: `NoteType`, `FieldDef`, `Template`
  - **Content & Scheduling**: `Note`, `Card`
  - **Media**: `MediaAsset`
  - **Marketplace & Sharing**: `DeckMarketplaceItem`, `DeckInstall`, `NoteTypeInstall`, `DeckReview`, `NoteTypeReview`
  - **Background Jobs**: `FieldRenameJob`

## 5. Frontend Architecture
The frontend employs a custom component-based architecture built with Jinja2 macros and modular static assets. This provides a maintainable UI without the overhead of a heavy JavaScript framework.
- **Templates**: `base.html` serves as the root layout. UI elements are broken down into reusable pieces in `templates/components/` (e.g., forms, buttons, modals, deck rows).
- **Styling**: Component-specific styles are located in `static/css/components/`, while global resets and layouts are in `static/css/main.css`.
- **Interactivity**: Vanilla JavaScript modules reside in `static/js/components/`, providing encapsulated logic for their corresponding UI components.

*(For detailed frontend component usage, see `docs/COMPONENT_ARCHITECTURE.md`)*

## 6. Infrastructure & Deployment
- The environment is orchestrated using `docker-compose.yml`.
- **Services**:
  - `web`: The Flask application running via `wsgi.py` on port 5000.
  - `db`: MySQL 8.0 database container with persistent volume storage (`flama_db_data`).
- **Configuration**: Secrets and environment-specific settings are injected via a `.env` file (loaded by `python-dotenv`). Important keys include database connection parameters (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`), `SECRET_KEY`, and feature flags like `USE_NEW_CARD_MODEL`.

## 7. Key Workflows
- **Authentication Flow**: Secure password hashing with standard session-based login mechanisms.
- **Data Initialization (Seeding)**: Custom CLI commands allow seeding vocabulary from CSV/TSV files into isolated deck structures.
- **Vocabulary Import & Management**: Users can bulk import CSV data and utilize a spreadsheet-like grid for inline editing, which saves custom column width preferences per user.
- **Spaced Repetition (Flashcard V2)**: Advanced scheduling subsystem that tracks user reviews on individual `Card` records generated from `Note` data and associated `Template` definitions.
