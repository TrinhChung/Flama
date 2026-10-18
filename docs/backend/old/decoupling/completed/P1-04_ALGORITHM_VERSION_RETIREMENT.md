# P1-04 — Algorithm executable and decoder retirement lifecycle

> Phase: 1
>
> Priority: P1
>
> Status: COMPLETED 2026-09-08
>
> Dependency: P1-01
>
> Primary lane: Backend + Frontend Architecture

## Mục tiêu

Định nghĩa và kiểm thử lifecycle giữ lại/retire Algorithm executable, client evaluator và persisted state/session decoder để exact-version dispatch không trở thành compatibility promise vô thời hạn.

## Bối cảnh

- Python và TypeScript đã dispatch exact `algorithm_key/version` và fail closed.
- Active StudySession lease hiện có thể kéo dài tới 24 giờ.
- Browser có IndexedDB persisted session; không được giả định mọi old session đã biến mất sau deploy.
- Detail retention 30 ngày không đồng nghĩa executable phải replay 30 ngày.

## Phạm vi file dự kiến

- `app/services/study_algorithm_registry.py`
- `frontend/src/features/study/scheduler/algorithmRegistry.ts`
- session restore/store modules
- StudySession lease constants/services
- registry/session tests
- architecture/runbook documentation

## Công việc chi tiết

1. Inventory versioned artifacts phải giữ:
   - server Algorithm adapter;
   - client evaluator/preview;
   - event/session payload decoder;
   - renderer/interaction contract decoder.
2. Chốt support states: active, deprecated, lease-only, retired/unavailable.
3. Định nghĩa minimum retention:
   - max active lease;
   - safety margin;
   - browser persisted session measurement;
   - deploy rollback window.
4. Định nghĩa behavior khi version unavailable:
   - open new session;
   - restore old session;
   - commit active lease;
   - inspect historical event.
5. Server và client phải fail cùng stable error family, không silently fallback sang latest.
6. Thêm registry introspection/support matrix dùng cho audit P0-02.
7. Test deploy/version scenarios với supported và retired versions.
8. Ghi procedure thêm version mới mà không sửa golden vectors cũ.

## Output đầu ra bắt buộc

- Algorithm/version/decoder support matrix.
- Retention and retirement ADR/runbook.
- Registry status/introspection seam nếu cần.
- Stable unavailable/deprecated behavior trên server và client.
- Tests cho old active lease, retired restore, new session và exact dispatch.
- Handoff report.

## Implementation evidence — 2026-09-08

Implemented within the registry ownership boundary:

- Python and TypeScript lifecycle states: `active`, `deprecated`,
  `lease-only`, `retired`.
- Purpose-aware exact resolution for `new-session`, `existing-lease` and
  `accepted-job`; all unavailable paths retain the
  `ALGORITHM_UNAVAILABLE` family and never fall forward.
- Deterministic support introspection with executable/evaluator, state decoder,
  config decoder, event-history decoder and interaction decoder capabilities.
- A history-only retired descriptor can remain readable without being
  executable.
- Current `legacy-anki/1.0.0` remains active; frozen Python/TypeScript golden
  vectors are unchanged.
- Session open resolves `new-session`; status/restore and commit resolve
  `existing-lease`; the async worker resolves `accepted-job` before replay.
- Architecture audit reports the support matrix and treats an active
  `lease-only` session as executable while blocking a retired/unknown one.
- Architecture decision and operator procedure:
  [STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md](../../../architecture/STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md).

Focused verification:

```text
.venv/Scripts/python.exe -m unittest tests.test_study_session_api tests.test_study_algorithm_registry tests.test_study_architecture_audit_service tests.test_study_batch_queue tests.test_study_algorithm_golden_vectors tests.test_study_action_runtime
Result: 64 passed

npm --prefix frontend test -- --run src/features/study/scheduler/algorithmRegistry.test.ts src/features/study/scheduler/legacyEngine.golden.test.ts src/features/study/session/studySessionEngine.test.ts
Result: 3 files, 32 tests passed

npm exec -- tsc --ignoreConfig --noEmit --target es2023 --module esnext --moduleResolution bundler --skipLibCheck --types vite/client src/features/study/scheduler/algorithmRegistry.ts src/features/study/scheduler/algorithmRegistry.test.ts
Result: passed
```

Focused coverage proves active/deprecated issuance, lease-only restore/job
execution, retired and unknown fail-closed behavior, history-only readability,
stable HTTP/worker errors, no ReviewEvent write on rejection and lifecycle-aware
audit classification.

Combined closeout passed on 2026-09-08: Study backend 144 tests, Study frontend
167 tests after the final restore/recovery additions, and full frontend
TypeScript typecheck. The runtime default remains `legacy-anki/1.0.0` in
`active`; no executable was retired by this task.

## Acceptance criteria

- Không path nào fallback sang version khác khi exact version thiếu.
- Active lease trong supported window vẫn commit/restore được.
- Retirement không xóa decoder/executable trước safety gate.
- Historical event readability được tách khỏi exact executable replay.
- Policy nêu rõ 30-day detail retention không kéo dài replay promise.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Re-add retained registry entry/version artifact nếu retire gây regression. Không rewrite session/event version IDs.

## Không làm trong task này

- Không thêm Algorithm mới.
- Không implement Algorithm switching.
- Không thay state storage.
- Không xóa `legacy-anki/1.0.0`.
