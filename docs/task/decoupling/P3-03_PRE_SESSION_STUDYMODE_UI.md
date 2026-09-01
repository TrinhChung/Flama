# P3-03 — Pre-session StudyMode selection UI

> Phase: 3
>
> Priority: P0
>
> Status: TODO
>
> Dependency: P3-01 and P3-05
>
> Primary lane: Frontend Study

## Mục tiêu

Đảm bảo learner selection/default được resolve trước khi gọi open-session API; selector không còn chỉ lọc một session đã được tạo.

## Bối cảnh

`useStudySession.ts` hiện mở session chỉ với deck scope. `StudyPage` tạo selected composition state từ snapshot của session đã mở và lọc queue cục bộ.

## Phạm vi file dự kiến

- `frontend/src/features/study/api.ts`
- `frontend/src/features/study/hooks/useStudySession.ts`
- `frontend/src/features/study/pages/StudyPage.tsx`
- `frontend/src/features/study/components/StudyModeSelector.tsx`
- matching frontend tests

## Công việc chi tiết

1. Tách launch state machine:
   - discover options;
   - resolve one/default/multiple/empty;
   - learner selects;
   - open session với `composition_id`;
   - render active session.
2. Không gọi session open trước khi selection/default hợp lệ.
3. Một option: có thể auto-resolve theo approved policy nhưng request vẫn gửi explicit ID.
4. Nhiều options: hiển thị selector và chờ user.
5. Zero options: explicit recoverable empty/unavailable state; không mở empty session giả.
6. Handle loading/error/retry/stale selection từ API.
7. Remove client-only queue filtering như authority; view phải phản ánh frozen server session.
8. Sau khi session bắt đầu, bảo toàn Study UI/layout/controls hiện có.
9. Add tests cho one/multiple/zero options, selection request, open failure, retry và no-premature-open.

## Output đầu ra bắt buộc

- Pre-session launch state machine.
- API call gửi exactly-one composition ID.
- Selector/empty/error flows và tests.
- Proof không session request nào chạy trước selection resolution.
- Zero visual regression cho active Study screen.
- Handoff report.

## Acceptance criteria

- New session luôn mang explicit resolved composition.
- Multiple-options flow không auto-pick ngầm.
- Client không filter composition khác sau khi server đã tạo session.
- Active session UI hiện có giữ nguyên presentation.
- Error/retry không tạo duplicate sessions.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Feature flag có thể quay về legacy launch cho old API trong compatibility window. Không giữ hai concurrent session-open calls trong cùng flow.

## Không làm trong task này

- Không redesign toàn bộ Study page.
- Không implement backend clone resolution.
- Không tạo persistent StudyMode model.
- Không đổi scheduler behavior.
