# P2-03 — Restore validation and quarantine

> Phase: 2
>
> Priority: P0
>
> Status: COMPLETED 2026-09-08
>
> Dependency: P2-01
>
> Primary lane: Frontend Session Storage

## Mục tiêu

Fail closed trước khi restored server/IndexedDB events được đưa vào live state hoặc commit calculation, trong khi vẫn normalize được valid legacy `study-session.v2` rows.

## Phạm vi file dự kiến

- `frontend/src/features/study/session/sessionRestore.ts`
- `frontend/src/features/study/session/sessionRestore.test.ts`
- `frontend/src/features/study/session/sessionStore.ts`
- `frontend/src/features/study/types.ts`
- hook restore integration tests

## Công việc chi tiết

1. Inventory persisted/server event shapes và legacy variants thực sự được support.
2. Validate trước live-state hydration:
   - event ID là UUID hợp lệ;
   - ID unique trong session;
   - sequence integer, bắt đầu đúng contract và contiguous;
   - sequence không reorder;
   - card thuộc frozen session card set;
   - event/session association khớp;
   - supported action/trigger identity/version;
   - rating/action/trigger canonical consistency;
   - elapsed/offset finite, non-negative, monotonic và không vượt lease bound;
   - Algorithm/config/policy identity khớp snapshot.
3. Chỉ normalize legacy row khi thiếu toàn bộ optional semantic metadata theo contract; partial mismatch phải reject.
4. Invalid row được atomically chuyển khỏi active store sang bounded quarantine.
5. Quarantine reason phải stable, diagnosable và không chứa answer content.
6. Invalid records không được recommit hoặc tự động bỏ qua để mở session như chưa có history.
7. Add fixtures cho từng invalid category và valid legacy/current cases.
8. Verify repeated restore không tạo duplicate quarantine rows.

## Output đầu ra bắt buộc

- Strict restore validator.
- Stable quarantine reason enum/table.
- Fixture matrix gồm valid current, valid legacy và mọi malformed case.
- Integration proof invalid history không ảnh hưởng commit.
- Handoff report.

## Acceptance criteria

- Duplicate ID, sequence gap/reorder, invalid UUID, overflow offset và mismatched card/session đều bị quarantine.
- Valid v2 legacy session vẫn restore.
- Quarantined data không vào active state/commit payload.
- Repeated failure giữ bounded one-row-per-scope behavior.
- Không silently repair ambiguous history.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

IndexedDB upgrade phải additive. Reader cũ không được ghi đè quarantine; nếu revert app, giữ raw quarantined evidence thay vì đưa trở lại active store tự động.

## Không làm trong task này

- Không đổi retention policy.
- Không đổi server schema.
- Không rewrite old event IDs.
- Không implement wire v3.

## Completion handoff — 2026-09-08

- Primary outcome: persisted v2/v3 session data is validated before hydration;
  UUIDs, exact identities, scope/card membership, numeric bounds, event/batch
  sequence and lease timing fail closed.
- Storage behavior: IndexedDB schema v2 adds an atomic active-to-quarantine
  store, bounded to 20 rows and 256,000 serialized characters per evidence
  record, with one row per scope. Repeated loads remain blocked.
- Recovery: “Thử lại” explicitly acknowledges the quarantine marker while
  retaining bounded evidence, then opens a new session. No invalid row is
  silently repaired or recommitted.
- Tests: valid legacy/current/v3, pending-batch round trip, malformed matrix,
  storage failure, repeated quarantine and explicit recovery are covered.
- Verification: Study frontend module and TypeScript typecheck passed.
- Rollback: preserve the additive quarantine store and evidence; do not copy a
  quarantined row back into the active store.
