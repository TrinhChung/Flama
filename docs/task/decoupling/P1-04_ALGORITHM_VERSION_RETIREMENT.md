# P1-04 — Algorithm executable and decoder retirement lifecycle

> Phase: 1
>
> Priority: P1
>
> Status: TODO
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
