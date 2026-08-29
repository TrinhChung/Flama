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
>
> Preparation status: P1-01.1 read-only investigation COMPLETED on 2026-08-29; runtime work remains gated by P0-03.

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

## P1-01.1 read-only producer and transaction investigation — 2026-08-29

This section is a non-authoritative implementation draft. It records the current runtime boundaries without changing code, starting Phase 1, or approving extraction before P0-03 closes.

### Current call graph

```text
REST POST /api/study[/cards]/<card_id>/answer
  -> app/routes/flashcards/study.py::study_answer
  -> app/services/study_service.py::execute_native_review_command
     -> resolve deck/options/policy and lock CardProgress
     -> execute_review_action
     -> record_native_review_transition
        -> stats_overview.record_review_event
           -> review_event_repository.create_review_event_record [session.add only]
        -> leech/owner-note and install-usage side effects
     -> flush, attach last_review_event_id, append AuditLog
     -> commit or rollback

MCP submit_review
  -> app/services/mcp/study_tools.py::submit_review
  -> app/services/study_service.py::execute_native_review_command
  -> same direct transaction path above

Session POST /api/study/sessions/<session_id>/commit
  -> app/routes/flashcards/study.py::study_session_commit
  -> app/services/study_session_service.py::commit_study_session
     -> lock/validate session, lease, snapshot, sequence and client events
     -> replay transitions and validate final states
     -> lock all CardProgress rows and validate frozen revisions/scope
     -> independently build ReviewEvent and repeat review side effects per event
     -> apply final progress, commit receipt, session status and AuditLog
     -> one outer commit or rollback
```

### Producer and transaction ownership matrix

| Producer | Progress/event writer | Commit/rollback owner | Finding |
|---|---|---|---|
| REST direct answer | `execute_native_review_command` | `study_service` | Route is an adapter; its pre-command progress/options reads are redundant and their local values are unused. |
| MCP `submit_review` | `execute_native_review_command` | `study_service` | MCP owns provenance input/error mapping only; it does not commit. |
| Session batch commit | `commit_study_session` | `study_session_service` | Required outer atomic transaction, but currently a second authoritative native event/side-effect writer. |
| `record_review_event` repository path | `create_review_event_record` | Calling service | Adds the event to the session only; it does not flush or commit. |
| Note-type/deck install usage helpers | Mutate locked install rows | Calling service | Both helper implementations mutate ORM state only; they do not flush or commit. |
| Audit append | Adds `AuditLog` | Calling service | Participates in the same direct or batch transaction. |

### Confirmed duplicated authoritative responsibilities

- Session commit replays the scheduler transition itself instead of invoking the direct native core.
- Session commit independently constructs the canonical `ReviewEvent` payload and attaches algorithm identity, state snapshots and session provenance.
- Session commit duplicates leech-tag and install-usage side effects already grouped by `record_native_review_transition`.
- Session open/commit retains policy serialization and digest logic that overlaps `study_policy_service.build_scheduler_policy` and `serialize_deck_options`.
- Both paths apply `CardProgress` fields and revision changes, so parity currently depends on duplicated behavior remaining synchronized.

### Boundaries that must remain outside the canonical non-committing core

- REST request parsing, visibility lookup, response mapping and HTTP status selection.
- MCP user/card lookup, server-created MCP event ID, transport provenance and MCP error mapping.
- Session lease/token/snapshot validation, contiguous sequence checks, client-event idempotency, bounded replay timing and ordered bulk locks.
- Session frozen base-revision and clone-scope revalidation, all-or-nothing transaction, `StudySessionCommit` receipt and session lifecycle.
- Direct/MCP outer commit and rollback remain in the command wrapper; batch keeps its single outer transaction.

### Proposed extraction slices after the P0-03 gate

1. Define typed transport-neutral transition input/result/error and a transaction mode that cannot commit inside the core.
2. Centralize scheduler policy serialization/identity in `study_policy_service`; session stores the same canonical output rather than rebuilding it.
3. Extract one non-committing native mutation core for transition execution, progress application, event construction and required local side effects.
4. Keep `execute_native_review_command` as the direct/MCP transaction wrapper around that core.
5. Adapt session commit to retain validation and bulk transaction ownership while delegating each authoritative transition/event mutation to the core.
6. Remove duplicated session builders only after direct/MCP/session parity, concurrency and rollback tests pass.

### Required proof for P1-01.2–P1-01.7

- Extend `tests/test_study_behavior_acceptance_baseline.py` direct/MCP parity to include session output on equivalent initial state and policy.
- Preserve its batch idempotency, validation rollback and mid-write rollback assertions.
- Cover first-progress concurrent insert, stale revision, suspension and clone overlay/source-owner cases with typed errors.
- Verify ReviewEvent, CardProgress, install usage, leech/dirty tracking, audit and session receipt roll back together after an injected failure.
- Search proof must show one canonical native event/policy builder after migration.

### Investigation verdict

P1-01.1 is complete as read-only preparation. The implementation boundary is sufficiently mapped for P1-01.2, but no runtime refactor is authorized until P0-03 produces accepted SELECT-only evidence and Phase 0 receives a GO verdict.

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
