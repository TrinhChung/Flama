# Flama (Nihongo) System Architecture

## 1. Overview
Flama is a lightweight web application designed for vocabulary learning. It provides user authentication, vocabulary management (bulk import, inline editing), a spaced repetition flashcard system inspired by Anki, and a marketplace/payment domain for paid learning content.

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
  - `routes/`: Application blueprints covering different domains (`auth.py`, `main.py`, `vocabulary.py`, `flashcards/*`, `payments.py`, `admin.py`, `admin_payments.py`, `user_orders.py`).
  - `services/`: Encapsulated business logic including payment/order orchestration and admin query services.
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
- **Payment & Commerce**:
  - **Order / Checkout**: `PaymentOrder`, `PaymentOrderItem`
  - **Transaction-facing payment state**: `PaymentAttempt`
  - **Webhook / callback audit**: `PaymentWebhookEvent`
  - **Fulfillment ledger**: `PaymentEntitlement`
  - **Admin payout operations**: `PayoutBatch`, `PayoutBatchItem`

### 4.2 Payment Architecture Direction

- payOS is the primary and intended payment provider for the current repository.
- The payment domain is organized around order management, payment attempts, webhook processing, and entitlement fulfillment.
- User-facing payment surfaces are intentionally simple: order history and order detail.
- Admin-facing payment surfaces are operational: dashboard, global order management, and transaction management.
- Older provider-specific payment experiments are not an equal architecture track.

For payment-specific architecture details, use `docs/FLAMA_PAYMENT_ARCHITECTURE.md`.

## 5. Frontend Architecture
The frontend employs a custom component-based architecture built with Jinja2 macros and modular static assets. This provides a maintainable UI without the overhead of a heavy JavaScript framework.
- **Templates**: `base.html` serves as the root layout. UI elements are broken down into reusable pieces in `templates/components/` (e.g., forms, buttons, modals, deck rows).
- **Styling**: Component-specific styles are located in `static/css/components/`, while global resets and layouts are in `static/css/main.css`.
- **Interactivity**: Vanilla JavaScript modules reside in `static/js/components/`, providing encapsulated logic for their corresponding UI components.

*(For detailed frontend component usage, see `docs/COMPONENT_ARCHITECTURE.md`)*

## 6. Infrastructure & Deployment
- The environment is orchestrated using `docker-compose.yml`.
- **Services**:
  - `web`: The Flask application running via `wsgi.py` on port 4789.
  - `db`: MySQL 8.0 database container with persistent volume storage (`flama_db_data`).
- **Configuration**: Secrets and environment-specific settings are injected via a `.env` file (loaded by `python-dotenv`). Important keys include database connection parameters (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`), `SECRET_KEY`, feature flags like `USE_NEW_CARD_MODEL`, and payment settings such as `PAYMENTS_ENABLED`, `PAYMENTS_PROVIDER=payos`, `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, and `PAYOS_CHECKSUM_KEY`.

## 7. Key Workflows
- **Authentication Flow**: Secure password hashing with standard session-based login mechanisms.
- **Data Initialization (Seeding)**: Custom CLI commands allow seeding vocabulary from CSV/TSV files into isolated deck structures.
- **Vocabulary Import & Management**: Users can bulk import CSV data and utilize a spreadsheet-like grid for inline editing, which saves custom column width preferences per user.
- **Spaced Repetition (Flashcard V2)**: Advanced scheduling subsystem that tracks user reviews on individual `Card` records generated from `Note` data and associated `Template` definitions.
- **Marketplace Payment Flow**:
  - paid marketplace content creates a `PaymentOrder`
  - payOS checkout creates or reuses a `PaymentAttempt`
  - payOS webhook or explicit state sync confirms payment
  - fulfillment grants access through `PaymentEntitlement` and the existing install tables
  - admin payment screens monitor abnormal attempts, webhook failures, and order state

## 8. Layer Responsibility Rules (Agent Guardrails)
These rules are mandatory for all contributors and coding agents to prevent logic from being added to the wrong layer.

### 8.1 Route Layer (`app/routes/*`)
- **Must do**:
  - Parse HTTP input (`request.args`, `request.form`, `request.get_json`).
  - Perform HTTP-level auth checks and simple resource existence checks.
  - Call validator(s) and service(s).
  - Map result to HTTP response (`jsonify`, `render_template`, status code).
- **Must not do**:
  - Implement business rules/use-case orchestration.
  - Do deep data sanitization/security filtering directly in route.
  - Own transaction boundaries (`db.session.commit/rollback`) except explicitly documented emergency fallback.
  - Become a data-access hub with large ORM query logic.

### 8.2 Validator Layer (`app/validators/*`)
- **Must do**:
  - Validate schema, required/optional, type, enum, length, structure.
  - Normalize input data.
  - Apply input security checks (XSS, injection probes, file upload guards).
  - Return clean data object or structured validation error.
- **Must not do**:
  - Write to DB or mutate persistent state.
  - Call `db.session.commit/rollback`.
  - Depend on Flask route context side effects.

### 8.3 Service Layer (`app/services/*`)
- **Must do**:
  - Implement use-case/business orchestration.
  - Own transaction boundaries.
  - Coordinate repository/query modules and domain policies.
- **Must not do**:
  - Parse raw HTTP payload formats.
  - Return Flask response objects.
  - Re-validate raw request format that already belongs to validator layer.

### 8.4 Repository/Query Layer (`app/repositories/*`)
- **Must do**:
  - Encapsulate DB read/write/query operations.
  - Return entities/read-models needed by service layer.
- **Must not do**:
  - Implement business workflows/policies.
  - Parse or sanitize HTTP input.
  - Depend on `request`, `current_user`, or route modules.
  - Own transaction commit/rollback (except explicitly documented low-level migration scripts).

### 8.5 Mandatory Check Before Merge (for Agent and Human)
For every new logic block, confirm all 4 statements:
1. Input validation and security checks are in validator layer.
2. Business orchestration is in service layer.
3. DB access is in repository/query layer.
4. Route only maps HTTP <-> app flow and does not absorb business logic.

If any statement fails, refactor before merge.
