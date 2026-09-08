# P2-06 — Built-in Trigger Runtime design checkpoint

> Phase: 2
>
> Priority: P1
>
> Status: COMPLETED 2026-09-08 — ADR accepted and bounded runtime implemented
>
> Dependency: P1-03 and P2-04
>
> Primary lane: Architecture / Backend Study

## Mục tiêu

Chốt responsibility boundary nhỏ nhất cho built-in exact-version Trigger dispatcher thay cho coupling trực tiếp `Action -> Algorithm`, nhưng chưa mở arbitrary user Trigger/automation và chưa đổi storage.

## Mode

Design/documentation first. Runtime implementation chỉ được tách thành follow-up khi ADR được duyệt. Task này không được âm thầm biến `study_action_runtime.py` thành generic plugin engine.

## Công việc chi tiết

1. Trace compatibility flow hiện tại từ semantic Action tới Algorithm adapter.
2. Định nghĩa ownership:
   - Interaction tạo Action;
   - mapping cho phép Action nào gọi Trigger nào;
   - Trigger Runtime authorize/validate/idempotency/transaction orchestration;
   - Algorithm chỉ tính transition;
   - transaction owner persist state/event/required effects.
3. Chốt built-in Trigger identity/version/payload schema.
4. Chốt primary vs follow-up semantics:
   - phần nào bắt buộc cùng transaction;
   - secondary consumer khi nào được dispatch;
   - failure/retry/order/idempotency;
   - cycle prevention.
5. Chốt client-evaluates/server-verifies boundary.
6. Chốt authorization: StudyMode chỉ có allowlisted mappings, không arbitrary internal handler name.
7. Định nghĩa fail-closed behavior cho unknown version/payload/handler.
8. So sánh ít nhất:
   - giữ permanent four-rating adapter;
   - built-in exact-version dispatcher tối thiểu.
9. Xác định phần phải chờ Phase 3 bindings hoặc Phase 4 state.
10. Đề xuất smallest implementation slice riêng, không implement trong ADR nếu chưa duyệt.

## Output đầu ra bắt buộc

- ADR/design document trong `docs/architecture/`.
- Responsibility table và typed input/output contract.
- Sequence flow cho primary transaction và secondary handoff.
- Alternatives/trade-offs/security analysis.
- Error/idempotency/versioning matrix.
- Explicit list: implement now / defer to Phase 3 / defer to Phase 4+.

## Acceptance criteria

- Design không thêm progress authority hoặc schema.
- Không expose arbitrary Template/custom code trigger execution.
- Transaction ownership chỉ có một nơi.
- Unknown trigger/version fail closed.
- Primary/follow-up semantics và idempotency được duyệt rõ.
- Có implementation task nhỏ tiếp theo hoặc explicit defer decision.

## Verification

- Review design đối chiếu `study_action_runtime.py`, `study_service.py`, `study_session_service.py` và event contract P1-03.
- Không cần runtime tests nếu không đổi code; link toàn bộ evidence paths.

## Rollback

Không có runtime rollback. Nếu ADR bị bác bỏ, compatibility runtime giữ nguyên tên và Phase 2 tiếp tục `Partial`.

## Không làm trong task này

- Không tạo generic external automation.
- Không thêm multiple trigger chains runtime.
- Không tạo migration.
- Không implement new Algorithm/Interaction.

## Completion handoff — 2026-09-08

- Decision: use a minimal exact-version dispatcher for the four built-in
  scheduler Triggers; no generic plugin, arbitrary handler or Template
  automation runtime is introduced.
- Runtime slice: the action runtime exposes an introspectable allowlist, typed
  Trigger command and pure dispatcher. Sync commit and worker pass the exact
  validated Trigger identity before the Algorithm transition.
- Transaction authority: REST/MCP/session services remain the only owners of
  progress, ReviewEvent, required effects and commit/rollback.
- Tests: unknown version, mismatched Action/Trigger and four-action parity pass
  in the Study backend gate.
- Rollback: keep published Trigger identities stable even if calculation is
  temporarily routed through the compatibility adapter.
