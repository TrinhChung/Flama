# P3-01 — Exactly-one composition session API

> Phase: 3
>
> Priority: P0
>
> Status: COMPLETED — 2026-09-09
>
> Dependency: Phase 1/2 correctness gates, P3-05 and P3-07
>
> Primary lane: Backend Study API

## Mục tiêu

Biến selected composition thành một authorized, explicit, exactly-one input của session creation thay vì optional list dùng để post-filter.

## Bối cảnh

`app/routes/flashcards/study.py` hiện nhận `composition_ids` dạng list tùy chọn. `study_session_service.py` lọc sau khi đã lấy candidate cards và không chứng minh selected composition thuộc scope hiện tại.

## Phạm vi file dự kiến

- `app/routes/flashcards/study.py`
- `app/services/study_session_service.py`
- `app/services/study_composition_service.py`
- validators/API error mapping liên quan
- `tests/test_study_session_api.py`
- `tests/test_study_composition_service.py`

## Công việc chi tiết

1. Chốt additive request contract với một `composition_id` canonical.
2. Từ chối:
   - nhiều IDs;
   - empty/blank malformed ID;
   - unauthorized composition;
   - out-of-scope composition;
   - composition không tương thích scope/NoteType đã chọn.
3. Old-client fallback phải explicit:
   - chỉ default khi có một unambiguous eligible option hoặc policy P3-05 cho phép;
   - feature flag/telemetry nếu cần;
   - không silently chọn phần tử đầu tiên từ nhiều options.
4. Authorization phải dùng current user's effective scope, không chỉ ownership của NoteType local.
5. API trả stable error codes cho stale/inaccessible/ambiguous selection.
6. Session service nhận typed resolved selection, không nhận raw arbitrary list.
7. Giữ API response fields cũ cần thiết cho old clients.
8. Tests cho owned deck/note type, unauthorized ID, cross-scope ID, multi-ID legacy input, zero/one/multiple options.

## Output đầu ra bắt buộc

- Exactly-one composition request/validation contract.
- Stable error code matrix.
- Explicit old-client fallback policy và telemetry nếu dùng.
- Backend tests cho authorization/scope/cardinality.
- API documentation update.
- Handoff report.

## Acceptance criteria

- Session không thể mở với unauthorized/out-of-scope selection.
- Multiple selections không được âm thầm chấp nhận.
- Ambiguous old client request không chọn ngẫu nhiên.
- Existing Template/Card relationships vẫn là compatibility authority.
- Không tạo composition table hoặc migration.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
```

## Rollback

Feature flag có thể quay về documented legacy default trong compatibility window; không quay lại accepting arbitrary list mà không authorization.

## Không làm trong task này

- Không implement frontend selector flow.
- Không giải quyết clone query chi tiết; thuộc P3-02.
- Không thêm FieldDef binding schema.
- Không thay Card IDs.

## Handoff — 2026-09-09

- Task ID: `P3-01`
- Primary outcome: session open now resolves exactly one authorized composition before any session row is created.
- Files changed: `app/routes/flashcards/study.py`, `app/services/study_session_service.py`, `app/services/study_composition_service.py`, `app/validators/study_composition.py`, and focused Study tests.
- Contract/API behavior changed: canonical `composition_id`; legacy `composition_ids` is accepted only when it contains exactly one value. Zero eligible cards, ambiguous omission, malformed/stale IDs, and out-of-scope IDs fail with stable typed errors.
- Tests added or updated: owned, zero/one/many cardinality, malformed legacy input, stale/out-of-scope selection, and no-session-on-failure cases.
- Rollback path: remove admission of the new launch flow while retaining the additive request reader and frozen-session reader.
- Known limitations: the compatibility identity remains derived from current `Template`/`Card` rows; no physical application entity exists in Phase 3.
- Follow-up task IDs: `P3-02`, `P3-04`, `P3-06`, `INT-01` — completed in the same integration closeout.
