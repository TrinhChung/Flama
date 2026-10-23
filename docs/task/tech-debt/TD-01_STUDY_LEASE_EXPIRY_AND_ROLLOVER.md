# TD-01 — Phiên quá hạn lease vẫn cho trả lời; rollover chủ động trước hạn

> Mức: **P0** · Đợt: W1 · Trạng thái: `DECISION` (D-U1)
>
> Phụ thuộc: TD-02 (dùng chung hành động cách ly + phiên mới và bộ phân loại lỗi) · Lane: Frontend Study · Ước lượng: 2–3 ngày
>
> Nguồn: UX-A1 ở [điều tra UI/UX trước P8](../../backend/old/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md). Liên quan P7 (commit muộn trả `410 SESSION_EXPIRED`) và P9-08.

## Mục tiêu

Người học không bao giờ trả lời trên một phiên đã hết hạn mà không biết:
- Trước khi hết hạn, hệ thống tự đồng bộ và mở phiên mới (rollover chủ động).
- Nếu đã quá hạn (ví dụ mở lại tab sau một ngày), hệ thống báo rõ, giữ bản sao câu trả lời cũ và mở phiên mới.

## Bối cảnh

- Lease 24 giờ (`app/services/study_session_service.py:137`). Server từ chối commit/batch sau `expires_at` (dòng 1423-1427, 2256-2261).
- Client chỉ đọc `expires_at` lúc khởi động và chỉ để dọn phiên **không có** việc chưa xác nhận (`frontend/src/features/study/hooks/useStudySession.ts:321-331`).
- Không kiểm tra hạn trước khi trả lời; không có handler `visibilitychange` (chỉ có `online`, dòng 166-167).
- Rollover hiện chỉ theo số event (`DEFAULT_STUDY_BATCH_EVENT_LIMIT = 50`, `session/studySessionEngine.ts:50`) hoặc khi hết hàng đợi (`automaticCommitMode`, dòng 383-392).

## Phạm vi file dự kiến

- `hooks/useStudySession.ts`: kiểm tra hạn trước `answer`; handler `visibilitychange`/`focus`; timer rollover.
- `session/studySessionEngine.ts`: thêm lý do `lease_rollover` vào `automaticCommitMode`.
- `pages/StudyPage.tsx`: hiển thị thông báo khi phiên cũ đã hết hạn.
- `session/sessionStore.ts`: dùng lại cách ly từ TD-02.
- Test: `useStudySession.test.tsx`, `studySessionEngine.test.ts`.

## Công việc chi tiết

1. Tính thời gian còn lại của lease theo `snapshot.expires_at`. Nếu snapshot có thời điểm server thì bù lệch đồng hồ; nếu không thì dùng biên an toàn.
2. **Rollover chủ động:**
   - khi còn ít hơn ngưỡng (khuyến nghị 30 phút) và có event: commit với `reason: 'lease_rollover', resumeAfterCommit: true`;
   - khi không có event: mở phiên mới ở lần lấy thẻ kế tiếp;
   - giữ `accumulated_stats` như rollover hiện có.
3. **Kiểm tra trước khi trả lời:**
   - `answer` từ chối khi lease đã hết hạn (không ghi event);
   - chuyển sang luồng "phiên đã hết hạn" của TD-02.
4. **Khi tab hiện lại** (`visibilitychange` → `visible`, `focus`): kiểm tra hạn ngay, rồi xử lý như bước 2/3.
5. **Khôi phục lúc khởi động** khi phiên cũ đã hết hạn nhưng còn event:
   - hỏi server trạng thái;
   - nếu `expired` hoặc commit trả `410`: cách ly (không xóa), hiện "N câu trả lời của phiên trước chưa được ghi vì phiên đã hết hạn", mở phiên mới;
   - không replay sang phiên mới (P9-08, D-U1).
6. Log/telemetry nội bộ (không gửi dữ liệu cá nhân): số lần rollover theo lease, số lần gặp phiên hết hạn có event.

## Output đầu ra bắt buộc

Rollover theo lease; chặn trả lời khi hết hạn; xử lý khi tab hiện lại; luồng khôi phục phiên hết hạn; test; handoff.

## Acceptance criteria

- Tab mở liên tục quá 24 giờ vẫn học được: tự rollover trước hạn, không lần commit nào nhận `410` (test giả lập thời gian).
- Mở lại phiên đã hết hạn còn event: không có câu trả lời mới nào được ghi vào phiên cũ; event cũ nằm trong kho cách ly; phiên mới mở được.
- Không đổi hành vi rollover 50 event và auto-finish.
- Học liên tục với lease còn dài không phát sinh thêm request.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

Kèm luồng trình duyệt dùng đồng hồ giả hoặc lease ngắn ở môi trường dev (profile Chrome riêng).

## Rollback

Revert frontend. Không đổi wire hay server.

## Quyết định liên quan

D-U1: rollover chủ động + cách ly khi đã hết hạn (khuyến nghị) hay cho phép tiếp tục và chỉ cảnh báo.

## Không làm trong task này

Kéo dài lease phía server; replay event sang phiên mới.
