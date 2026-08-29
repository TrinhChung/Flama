# P1-01 — Canonical native review transaction

> Phase: 1
>
> Priority: P0
>
> Status: TODO
>
> Dependency: P0-04
>
> Primary lane: Backend Study

## Mục tiêu

Đảm bảo REST, MCP và batch review dùng một authoritative command/core cho progress mutation, policy identity, ReviewEvent construction và required side effects, trong khi batch vẫn giữ outer lease/idempotency/atomic commit contract.

## Bối cảnh và evidence

- REST/MCP đã đi qua `execute_native_review_command` trong `app/services/study_service.py`.
- `app/services/study_session_service.py::commit_study_session` vẫn tự dựng authoritative ReviewEvent/side effects.
- `study_session_service.py` còn policy serialization/hash logic trùng với `app/services/study_policy_service.py`.

## Phạm vi file dự kiến

- `app/services/study_service.py`
- `app/services/study_session_service.py`
- `app/services/study_policy_service.py`
- `app/routes/flashcards/study.py`
- `app/services/mcp_tool_service.py`
- `tests/test_study_session_api.py`
- `tests/test_flama_connect_mcp.py`
- focused service tests mới nếu cần

## Công việc chi tiết

1. Trace mọi native review write entrypoint tới `CardProgress` và `ReviewEvent`.
2. Liệt kê chính xác phần đang trùng:
   - policy resolution/serialization/hash;
   - lock/revision/suspension validation;
   - Algorithm transition;
   - progress field application;
   - ReviewEvent payload/provenance;
   - audit/dirty tracking/secondary local side effects.
3. Thiết kế một command/core có input typed, không phụ thuộc HTTP/MCP route.
4. Giữ transaction ownership rõ:
   - direct/MCP command có thể commit atomic unit hiện tại;
   - batch gọi core trong outer transaction và không commit từng event.
5. Batch không được tự tạo canonical event hoặc policy identity.
6. Chuẩn hóa first-progress insert race:
   - existing row lock;
   - typed result/error cho concurrent insert;
   - không leak raw `IntegrityError`.
7. Đảm bảo stale/suspended/revision behavior tương đương giữa paths, ngoại trừ lease-specific validation được ghi rõ.
8. Giữ idempotency của batch và response shape hiện có.
9. Thêm parity tests so sánh direct/MCP/batch trên cùng initial state/action/policy.
10. Thêm rollback test chứng minh event/progress/side effects không partial khi một bước fail.

## Output đầu ra bắt buộc

- Một canonical transaction command/core được dùng bởi REST, MCP và batch.
- Không còn authoritative event/policy builder trùng trong batch.
- Typed concurrency contract cho first insert/stale revision.
- Parity test matrix và atomic rollback tests.
- Call graph trước/sau trong PR hoặc tài liệu ngắn.
- Handoff report theo format chung.

## Acceptance criteria

- REST, MCP và batch cùng input tạo equivalent progress state và canonical metadata.
- Chỉ batch mang StudySession/client-event/sequence metadata.
- Batch vẫn atomic và idempotent.
- Không service layer nào import helper từ route để hoàn thành command.
- `CardProgress` vẫn là authority duy nhất.
- Search/review xác nhận không còn second authoritative ReviewEvent builder cho native review.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --changed
```

## Rollback

Không đổi schema. Có thể route call sites về seam cũ nếu regression, nhưng phải revert đồng bộ command + call sites; không để hai paths cùng tồn tại lâu dài.

## Không làm trong task này

- Không xử lý Anki snapshot/revlog authority.
- Không thêm Trigger dispatcher.
- Không thêm Phase 4 mirror/new progress table.
- Không redesign API response ngoài phần cần để preserve typed errors hiện có.
