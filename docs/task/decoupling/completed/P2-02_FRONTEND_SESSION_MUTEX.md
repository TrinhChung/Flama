# P2-02 — Frontend session mutation mutex

> Phase: 2
>
> Priority: P0
>
> Status: COMPLETED 2026-09-08
>
> Dependency: P2-01
>
> Primary lane: Frontend Study

## Mục tiêu

Đảm bảo tại mọi thời điểm chỉ một async session mutation có ownership, ngăn submit/undo/restore/commit cùng tick làm state hoặc IndexedDB diverge.

## Bối cảnh

`operationRef` trong `useStudySession.ts` hiện hoạt động như marker nhưng mutation paths chưa atomically test-and-acquire trước `await`.

## Phạm vi file dự kiến

- `frontend/src/features/study/hooks/useStudySession.ts`
- `frontend/src/features/study/hooks/useStudySession.test.tsx`
- session engine/store/lease modules nếu cần
- StudyPage/interaction call sites nếu cần typed busy result

## Công việc chi tiết

1. Inventory mọi mutating entrypoint: answer, undo, restore, retry, commit, auto-commit, conflict recovery.
2. Phân biệt read-only preview/reveal với persistent mutation.
3. Implement synchronous test-and-acquire trước async boundary:
   - compare current owner;
   - acquire token/operation kind;
   - reject/ignore duplicate theo documented UX;
   - release chỉ khi owner token khớp.
4. Mọi mutation phải đi qua cùng guard, không tự kiểm tra rời rạc.
5. Xử lý cleanup trên success, typed failure, thrown error, abort và unmount.
6. Không để stale `finally` của operation cũ release lock của operation mới.
7. Giữ local undo/offline recovery behavior.
8. Add same-tick tests:
   - submit + submit;
   - submit + undo;
   - restore + submit;
   - commit + submit;
   - retry + undo;
   - unmount/abort cleanup.
9. Tests phải chứng minh old implementation sẽ fail ít nhất một case.

## Output đầu ra bắt buộc

- Một operation ownership/mutex boundary duy nhất.
- Stable duplicate/busy result behavior.
- Same-tick concurrency test matrix.
- Không thay đổi visible UI/layout.
- Handoff report.

## Acceptance criteria

- Tối đa một mutating operation được acquire.
- Duplicate event không append hai session events hoặc gửi hai commit requests.
- Undo không chạy giữa transition chưa hoàn tất.
- Lock luôn release đúng owner sau failure/abort/unmount.
- Existing restore/offline/undo tests vẫn xanh.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Không đổi storage schema. Revert guard và tests cùng nhau nếu cần, nhưng không giữ marker cũ song song với mutex mới.

## Không làm trong task này

- Không sửa iframe keyboard.
- Không đổi backend event validation.
- Không redesign Study UI.
- Không thay Algorithm logic.

## Completion handoff — 2026-09-08

- Primary outcome: `useStudySession` now uses one synchronous owner-token mutex
  across bootstrap, answer, undo, commit/retry, page exit, selection persistence,
  reload and content/template mutations. A stale `finally` cannot release a
  newer owner.
- Contract/API behavior: same-tick duplicate actions are busy/no-op; automatic
  rollover uses the synchronous commit endpoint. New async batch admission is
  disabled by default by the G0 containment flag.
- Tests: deferred-promise matrices cover answer+answer, answer+undo,
  commit+answer, retry+undo, bootstrap+answer and pagehide using latest state.
- Verification: Study frontend module, typecheck and lint gates passed.
- Rollback: revert the hook and tests together; do not restore the boolean
  operation marker or automatic async rollover.
- Known limitation/follow-up: pre-existing accepted async batches remain
  durable evidence and require operational reconciliation before async can be
  re-enabled. Phase 3/INT-01 must continue using the same mutation boundary.
