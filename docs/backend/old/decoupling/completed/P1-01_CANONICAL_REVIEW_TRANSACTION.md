# P1-01 — Canonical native review transaction

> Phase: 1
>
> Priority: P0
>
> Status: COMPLETED
>
> Dependency: P0-04
>
> Primary lane: Backend Study
>
> Completion status: P1-01.1 through P1-01.7 completed on 2026-08-29; next task is P1-02.1.

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

That historical gate was satisfied by the completed P0-03 evidence bundle before the runtime implementation below began.

## P1-01.2-P1-01.7 implementation handoff — 2026-08-29

### Primary outcome

REST, MCP and durable session review now share the same typed scheduler-transition and non-committing mutation core in `app/services/study_service.py`. The durable session service retains its lease, replay validation, ordered locks, idempotency receipt and one outer commit, but no longer builds native policy identity, `ReviewEvent`, progress fields or required review side effects independently.

### Typed core contract

| Contract | Responsibility | Transaction behavior |
|---|---|---|
| `NativeReviewTransitionInput` / `execute_native_review_transition` | Exact algorithm key/version transition for one state/action/policy | Pure scheduler execution; no persistence |
| `NativeReviewProvenance` | Optional session, client-event and sequence identity | Only session supplies all three fields; MCP supplies its server-owned client-event ID |
| `NativeReviewProgressInput` | Final `CardProgress` state and caller-approved revision | Applied by the core; no commit/rollback |
| `NativeReviewMutationInput` / `apply_native_review_mutation` | Progress application, canonical native `ReviewEvent`, duration/mode normalization, leech handling and install-usage touches | Never calls commit or rollback; outer wrapper owns the transaction |
| `NativeReviewMutationResult` | Created event and mutated progress/revision | Caller flushes, links `last_review_event_id` and commits or rolls back |

Session batches with multiple events for one card invoke the canonical mutation for every event and attach `NativeReviewProgressInput` only to that card's last replayed event. This preserves the existing one-revision-per-batch contract while using one event/side-effect authority.

### Post-change call graph

```text
REST answer
  -> execute_native_review_command [lock + direct transaction owner]
     -> execute_native_review_transition
     -> build_scheduler_policy
     -> apply_native_review_mutation
        -> apply CardProgress state/revision
        -> one native ReviewEvent builder
        -> leech + install-usage side effects
     -> flush + last_review_event_id + AuditLog
     -> commit / rollback

MCP submit_review
  -> execute_native_review_command
  -> same direct path, with MCP client_event_id provenance

Durable session commit
  -> validate lease/token/snapshot/sequence/idempotency
  -> execute_native_review_transition for replay + hash checks
  -> ordered CardProgress locks and frozen revision/scope checks
  -> apply_native_review_mutation for every event
  -> flush + last_review_event_id + receipt + AuditLog
  -> one outer commit / rollback
```

### Concurrency and rollback contract

- Direct first-progress insert maps `IntegrityError` to `StudyReviewError(code="CONCURRENT_REVIEW", status=409)`.
- Batch first-progress insert is explicitly flushed before event writes and maps the same race to `StudySessionError(code="CARD_PROGRESS_CONFLICT", status=409)`.
- Direct stale manifest remains `STALE_REVIEW_STATE`; durable-session stale base revision remains `CARD_PROGRESS_CONFLICT` because it reports a frozen session conflict.
- Suspended cards remain `CARD_SUSPENDED` in both wrappers.
- Failure injection after canonical progress/event/side-effect mutation proves rollback of `ReviewEvent`, `CardProgress`, note side effects, `AuditLog`, `StudySessionCommit` and session lifecycle state.

### Search proof

Repository search after migration shows:

- one native `record_review_event(...)` call, in `study_service.py`;
- one direct `execute_review_action(...)` call for native review, behind `execute_native_review_transition`;
- both direct and session policy creation call `build_scheduler_policy(...)`;
- `study_session_service.py` contains no native event builder, deck-option serializer, duration normalizer, days-late calculator, leech handler or direct progress-field application.

`anki_sync_service.py` remains a separate external/import producer by design and is owned by P1-02/P1-03; it is not a native user-action writer.

### Verification evidence

```text
py -3 -m py_compile app/services/study_service.py app/services/study_session_service.py app/routes/flashcards/study.py tests/test_study_behavior_acceptance_baseline.py
PASS

py -3 scripts/run_tests.py --module study --backend-only
PASS — 13 files, 98 tests, 80.46s

py -3 scripts/run_tests.py --module connect_mcp --backend-only
PASS — 13 files, 161 tests, 152.37s
```

The parity matrix now compares REST, MCP and durable session `CardProgress`, canonical `ReviewEvent` fields, runtime metadata and transport-specific provenance at the same fixed time and policy. Batch delegation, idempotent replay, stale conflict, first-insert races and rollback after canonical side effects are executable assertions.

### P0 duplicate-template-position warning disposition

The accepted P0-03 bundle found one legacy NoteType with nine Templates at `position=0`. Native review mutation does not select a Template by position: it reviews the stable Card/Template identity already selected by the query/session snapshot. No data repair or schema rewrite belongs in this no-storage-change task. Deterministic application/ordinal identity for this legacy condition is carried into P3-07's compatibility binding decision.

### Handoff report

```text
Task ID: P1-01
Primary outcome: One typed native transition/mutation authority for REST, MCP and durable session review.
Files changed: app/services/study_service.py; app/services/study_session_service.py; app/routes/flashcards/study.py; tests/test_study_behavior_acceptance_baseline.py; decoupling tracker/task Markdown.
Contract/API behavior changed: External REST/MCP/session response shapes are unchanged. Batch first-progress insert races now return typed CARD_PROGRESS_CONFLICT instead of leaking raw IntegrityError. Session ReviewEvent payload JSON uses the shared canonical serializer; semantic JSON fields are unchanged although insignificant whitespace may differ.
Tests added or updated: REST/MCP/session parity, canonical-core delegation, first-progress race mapping, idempotency, stale conflict and rollback after event/progress/note-side-effect mutation.
Commands run: py_compile; study backend module; connect_mcp backend module; search proof; git diff/check.
Test results: Study 98/98 PASS; Connect/MCP 161/161 PASS.
Rollback path: Revert the core and both call-site adaptations together; never leave native writers split across services.
Known limitations: External snapshot/revlog/import conflicts remain P1-02; bounded/versioned event provenance remains P1-03; executable/decoder retirement remains P1-04; MySQL driver-level deadlock/connection-loss fault injection was not added.
Follow-up task IDs: P1-02, P1-03, P1-04, P3-07.
```

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
