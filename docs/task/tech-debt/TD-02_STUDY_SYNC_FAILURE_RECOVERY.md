# TD-02 — Phục hồi khi đồng bộ phiên học lỗi vĩnh viễn; thông điệp lỗi cho người học

> Mức: **P0** · Đợt: W1 · Trạng thái: `TODO`
>
> Phụ thuộc: không · Chặn: TD-01, TD-03 · Lane: Frontend Study · Ước lượng: 3–4 ngày
>
> Nguồn: UX-A2, UX-A5 ở [điều tra UI/UX trước P8](../decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); canonical plan §14.3 và Phụ lục B #3. Phối hợp P9-08 ("pending data cũ được quarantine/hiển thị trạng thái rõ").

## Mục tiêu

Khi commit hoặc batch bị server từ chối vĩnh viễn, người học thấy **một màn sự cố rõ ràng** với các lựa chọn an toàn: thử lại, giữ bản sao rồi mở phiên mới, hoặc gửi hỗ trợ. Không còn vòng quay chờ vô hạn, không mất dữ liệu, không lộ thông điệp kỹ thuật hay tiếng Anh.

## Bối cảnh

- Commit lỗi thì `setError` rồi `throw`, phiên giữ `pending_commit` (`frontend/src/features/study/hooks/useStudySession.ts:756-757`).
- `blockingCommit` hiện vòng quay "Đang đồng bộ phiên học…" cùng `PageError` (`pages/StudyPage.tsx:399-404, 451-455, 468-471`).
- "Tải lại phiên học" commit lại rồi dừng (`useStudySession.ts:1141-1142`).
- Lối cách ly `reloadSession(true)` chỉ có khi không có phiên (`StudyPage.tsx:386-397`).
- `PageError` luôn có tiêu đề "Không thể tải dữ liệu" và in nguyên `message` (`shared/components/PageState.tsx:13-21`).
- Frontend không xử lý riêng `SESSION_EXPIRED` hay `CARD_PROGRESS_CONFLICT` (server: `app/services/study_session_service.py:1423-1427, 2256-2261, 2389, 2494, 2608`).

## Phạm vi file dự kiến

- Mới:
  - `frontend/src/features/study/session/studyErrorClassification.ts` (mã lỗi → loại + thông điệp + hành động);
  - `components/StudySyncIssueCard.tsx`.
- Sửa:
  - `hooks/useStudySession.ts` (hành động `quarantineAndRestart`, trạng thái sự cố);
  - `pages/StudyPage.tsx` (render màn sự cố thay vòng quay khi lỗi vĩnh viễn);
  - `session/sessionStore.ts` (cách ly phiên đang chờ commit, giữ nguyên dữ liệu);
  - `components/StudyScopeErrorCard.tsx` (dùng chung bộ phân loại);
  - `shared/components/PageState.tsx` (cho phép truyền tiêu đề).
- Test: `useStudySession.test.tsx`, `StudyPage.test.tsx`, test mới cho bộ phân loại.

## Công việc chi tiết

1. Bảng phân loại mã lỗi (tối thiểu):

   | Loại | Mã lỗi |
   |---|---|
   | Tạm thời, tự thử lại | mạng, 5xx, `BACKEND_UNAVAILABLE`, `BATCH_PENDING` |
   | Hết hạn | `SESSION_EXPIRED` (410); dùng chung với TD-01 |
   | Xung đột | `CARD_PROGRESS_CONFLICT`, `AUTHORITY_STATE_CONFLICT`, `SESSION_AUTHORITY_SUBJECT_CONFLICT`, `BATCH_FAILED`, `BATCH_AFTER_FINAL`, `COMPOSITION_*_CONFLICT` |
   | Dữ liệu không hợp lệ | `FINAL_STATE_MISMATCH`, `INVALID_*_RECEIPT`, `COMMIT_TOO_LARGE`, `INVALID_FINAL_STATES` |
   | Lưu trữ máy | `STUDY_STORAGE_UNAVAILABLE` |
   | Phạm vi | `NO_STUDY_CARDS`, `SESSION_TOO_LARGE`, `ALGORITHM_UNAVAILABLE`, `DECK_ACCESS_DENIED` |

   Mỗi mã có thông điệp tiếng Việt cho người học và danh sách hành động.
2. Màn "Không thể đồng bộ N câu trả lời":
   - giải thích ngắn;
   - số câu trả lời đang giữ trên máy;
   - nút *Thử lại*;
   - nút *Giữ bản sao và bắt đầu phiên mới*: cách ly bản ghi phiên cũ trong IndexedDB (không xóa), rồi mở phiên mới;
   - nút *Sao chép thông tin hỗ trợ* (session id, commit id, mã lỗi, thời điểm);
   - liên kết trang khắc phục sự cố.
3. Lỗi tạm thời giữ vòng quay kèm trạng thái "Đang thử lại…" và thời gian thử lại; quá N lần thì chuyển sang màn sự cố.
4. Cách ly:
   - lưu trong kho cách ly hiện có (`loadStudySessionWithDurability` đã có khái niệm quarantine);
   - có giới hạn dung lượng như P2-03;
   - không replay tự động sang phiên mới (P9-08).
5. `PageError` trong phiên đổi tiêu đề theo ngữ cảnh ("Đồng bộ chưa hoàn tất" thay vì "Không thể tải dữ liệu").
6. Không hiện thông điệp tiếng Anh: mọi `Error` nội bộ (`'Study session lease is not held by this window.'`, `'Study renderer ABI mismatch.'`, `'Card is not part of the active session.'`…) được ánh xạ; mã gốc chỉ nằm trong phần "Chi tiết".
7. Trợ năng: màn sự cố dùng `role="alert"`, focus vào tiêu đề (như `StudySessionConflict`).

## Output đầu ra bắt buộc

Bộ phân loại + test bao phủ mọi mã ở bước 1; màn sự cố; hành động cách ly + phiên mới; ánh xạ thông điệp; handoff theo mẫu.

## Acceptance criteria

- Commit `409`/`410`/`422` hiện màn sự cố, không còn vòng quay vô hạn; người học mở được phiên mới trong 1 thao tác.
- Không có event nào bị xóa: kho cách ly chứa đủ event của phiên lỗi; test kiểm tra số event trước/sau.
- Lỗi tạm thời tự thử lại và hồi phục khi mạng trở lại (handler `online` hiện có vẫn chạy).
- Không còn chuỗi tiếng Anh hay mã kỹ thuật ở vùng chính của màn học (kiểm bằng test snapshot text).
- Giao diện phiên học bình thường không đổi (Zero Visual Regression).

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

Kèm luồng trình duyệt (profile Chrome riêng):
- chặn request commit trả `409`;
- trả `410`;
- mất mạng rồi có mạng lại.

## Rollback

Revert frontend. Dữ liệu cách ly tương thích ngược vì dùng định dạng quarantine hiện có.

## Không làm trong task này

Kiểm tra hạn lease chủ động (TD-01); chỉ báo lưu bền (TD-03); endpoint server mới.
