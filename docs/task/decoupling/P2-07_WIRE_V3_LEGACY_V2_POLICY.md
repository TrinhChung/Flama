# P2-07 — Wire v3 and legacy v2 lease policy

> Phase: 2
>
> Priority: P1
>
> Status: TODO
>
> Dependency: P1-04, P2-03 and P2-06
>
> Primary lane: Backend + Frontend Contract

## Mục tiêu

Đưa semantic Action/Trigger identity thành required versioned wire contract cho session mới, đồng thời giữ valid `study-session.v2` leases hoạt động qua compatibility window đã đo và duyệt.

## Công việc chi tiết

1. Inventory v2 open/restore/commit request-response shapes.
2. Chốt v3 fields bắt buộc:
   - action identity/version;
   - trigger identity/version;
   - Algorithm/config identity;
   - session/client event identity và sequence;
   - không kéo Phase 4 state/schema vào wire.
3. Định nghĩa discriminated TypeScript/Python validation để không có independent unions tạo invalid combinations.
4. Server dispatch theo exact wire version; không heuristic parse v3 như v2.
5. Client mới tạo v3 session/events sau feature gate.
6. Server vẫn nhận valid v2 event trong active lease + safety margin.
7. Invalid partial semantic metadata trong v2 bị reject/quarantine theo P2-03.
8. Định nghĩa telemetry đo active v2 leases trước retirement.
9. Test deploy matrix:
   - old client → new server;
   - new client → new server;
   - restored v2 session;
   - unsupported v3 trigger/algorithm;
   - expired v2 lease;
   - rollback server trong compatibility window.
10. Cập nhật API contract và retirement runbook.

## Output đầu ra bắt buộc

- Versioned v3 wire schema và validators server/client.
- v2 compatibility handler + measured retirement rule.
- Feature flag/rollout order nếu implementation được duyệt.
- Cross-version contract tests.
- Telemetry/audit field cho active version counts, không log answer content.
- Handoff report.

## Acceptance criteria

- New v3 events không thể thiếu/mismatch action/trigger metadata.
- Unsupported wire/trigger/algorithm version fail closed.
- Valid active v2 lease vẫn restore/commit trong window.
- Không silently convert v3 sang latest behavior.
- Rollback an toàn trong window vì v2/new semantics còn losslessly representable.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Feature flag client creation về v2 trong compatibility window và giữ v3 reader nếu đã có v3 leases. Không xóa v3 handler khi còn active session.

## Không làm trong task này

- Không thêm learner/Note progress wire/state.
- Không contract v2 ngay sau deploy.
- Không thêm arbitrary Trigger payload.
- Không thay retention 30 ngày.
