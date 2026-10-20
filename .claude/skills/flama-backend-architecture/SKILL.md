---
name: flama-backend-architecture
description: Design, build, refactor, and maintain Flask REST APIs, business services, repositories, validators, scheduling algorithms, and payment/sync integrations in app/. Use when working on Flask blueprints, services, repositories, validators, Anki scheduling, payOS payments, or Flama Connect protocol.
---

# Flama Backend Architecture

## Mission

Architect, build, maintain, and refactor Flama's Flask REST APIs and core domain services. Flama backend is a Flask application serving canonical REST APIs under `/api` for a React SPA, featuring Anki spaced-repetition scheduling, distributed deck overlay cloning, payOS payments, and Yomitan/AnkiConnect sync bridges.

---

## Architectural Layer Boundaries

Maintain clear separation across layers when introducing or refactoring code:

```
+-----------------------------------------------------------------------+
| app/api/*         -> HTTP handling, request parsing, JSON formatting  |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| app/validators/*  -> Input sanitization, payload schema validation     |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| app/services/*    -> Business logic orchestration, transactions       |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| app/repositories/*-> Database queries, persistence, SQLAlchemy CRUD   |
+-----------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------+
| models/*          -> SQLAlchemy ORM entities & schema definitions      |
+-----------------------------------------------------------------------+
```

> [!IMPORTANT]
> **Boundary Rule**: Keep HTTP logic out of repositories and keep direct database queries out of API route handlers. Keep transaction ownership inside service methods.

---

## Key Domain Modules

- **Auth & Identity**: `app/api/v1/identity/`, `models/user.py`, `app/services/identity_api_service.py`
- **Dashboard & Stats**: `app/api/v1/analytics/`, `app/services/dashboard_service.py`, `app/services/stats_overview.py`
- **Vocabulary & Study**: `app/api/v1/decks/`, `app/api/v1/learning/`, `app/repositories/vocabulary_repository.py`, `app/services/anki_scheduler.py`
- **Flashcard Engine**: `app/api/v1/flashcards/`, `app/services/flashcard_renderer.py`, `app/services/flashcard_content_service.py`
- **Marketplace & Clone Overlay**: `app/api/v1/marketplace/`, `app/services/flashcards_share_service.py`, `app/repositories/flashcards_share_repository.py`
- **Deck Change Requests**: `app/services/deck_change_request_service.py`, `models/deck_change_request.py`
- **Flama Connect (Sync Bridge)**: `connect_wsgi.py`, `app/services/flama_connect_service.py`
- **Payments (payOS)**: `app/services/payment_service.py`, `app/services/payment/provider/payos_provider.py`

---

## High-Risk Files & Hotspots

1. `app/routes/vocabulary.py`: Pruned legacy wrappers; retired Level/Topic/Lesson endpoints remain HTTP 410.
2. `app/services/share/`: Overlay share/install/cutover implementation; `flashcards_share_service.py` is a compatibility facade.
3. `app/services/deck_change_request_service.py`: Change request lifecycle & conflict resolution.
4. `app/__init__.py`: App factory, loading `app/settings.py` and gated `app/startup.py`. Production startup is passive by default; schema/data maintenance requires explicit flags.

---

## Preserved Guardrails

1. **Overlay-Only Shared Decks**: Do not reintroduce full-copy clone behavior or mutate source notes during clone edit operations.
2. **Anki Scheduler Integrity**: Use timezone-aware helpers in `app/services/anki_scheduler.py` and `app/repositories/study_repository.py`. Do not hand-roll new due-date calculation logic.
3. **Media Security**: All flashcard rendering and media access flow through `app/services/flashcard_renderer.py` and `/media/proxy/<asset_id>`. Preserve CSP rules and HTML sanitization.
4. **Canonical `/api` Endpoints**: All new functionality must expose JSON endpoints under `/api`. Server-rendered Jinja templates have been eliminated.
5. **Local MySQL First (Tránh SQLite khi phát triển)**: Bắt buộc ưu tiên dùng database MySQL cục bộ (local / docker container qua `.env`), tránh sử dụng SQLite khi phát triển hay sửa đổi logic backend để phòng ngừa sai lệch kiểu dữ liệu, hàm JSON, cơ chế lock transaction và migration DDL.

---

## Inter-Agent Collaboration Rules (Backend Agent)

1. **DB Alignment**: Coordinate schema changes with `$flama-database-architecture`. Ensure models in `models/` have matching Alembic migrations in `migrations/`.
2. **Frontend Alignment**: Provide clear REST JSON contracts (HTTP status codes, field names, data types) to `$flama-frontend-architecture`.
3. **Testing**: Use `python scripts/run_tests.py --module <domain> --backend-only`. MySQL is mandatory for integration, startup, JSON/locking behavior and migrations; retain SQLite only for existing isolated in-memory unit tests.
4. **Native arrays**: Preserve JSON lists in field values. Use `field_value_text()` for text and `stored_field_value()` for storage; no Anki export.
5. **Contracts**: Preserve endpoint-specific response shapes, authorization, CSRF and transaction semantics. Do not impose a universal envelope or expose ORM fields as DTOs without checking the API.
