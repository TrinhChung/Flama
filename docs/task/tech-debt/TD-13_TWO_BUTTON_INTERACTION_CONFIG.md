# TD-13 — Chế độ 2 nút bằng cấu hình Interaction theo cách học

> Mức: **P2** · Đợt: W4b · Trạng thái: `DECISION` (D-C3)
>
> Phụ thuộc: TD-06 (metadata composition); nếu có TD-15 thì dùng engine để cấu hình này đi theo release/fork · Lane: Backend Study + Frontend Study/Note types · Ước lượng: 3–5 ngày
>
> Nguồn: tầng 2 ở [tùy chỉnh nút và thuật toán](../decoupling/STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) §2.2; canonical plan §6.2 ("A Template or mode may configure allowed visual properties while the host keeps the semantic contract").

## Mục tiêu

Một cách học có thể chỉ cho phép một tập Action của bộ 4 nút, ví dụ "Quên / Nhớ" = `review.again` + `review.good`. Cấu hình được đóng băng trong phiên và **server kiểm tra**, không chỉ ẩn ở UI.

## Bối cảnh

- Server nhận cả 4 Action (`app/services/study_action_runtime.py:22-23`).
- Composition có `interaction_key = 'review.four-rating'` cố định (`app/services/study_composition_service.py:25-27`).
- `study_applications` là chỗ tự nhiên để gắn cấu hình theo từng cách học (`models/study_application.py`).

## Phạm vi file dự kiến

- Model/migration: `interaction_config` (JSON có `schema_version`) trên application, hoặc bảng cấu hình riêng theo ADR TD-14.
- Backend:
  - `study_composition_service.py` (trả cấu hình);
  - `study_session_service.py` (snapshot ghim cấu hình; commit/batch từ chối Action ngoài tập, mã lỗi mới `ACTION_NOT_ALLOWED`);
  - `study_session_config.py` (kiểm tra khi khôi phục).
- Frontend:
  - `interactions/ReviewInteractionControls.tsx` (render theo tập Action);
  - `pages/StudyPage.tsx` (phím 1–4 ánh xạ theo tập);
  - `StudyCompletionCard.tsx` (thống kê theo Action hiện có);
  - trình soạn Template/cách học (TD-04) có mục "Nút đánh giá".

## Công việc chi tiết

1. Schema `interaction-config.four-rating.v1`: `allowed_actions` (tập con, bắt buộc có `review.again` và ít nhất một Action "nhớ"), nhãn hiển thị tùy chọn cho từng Action (chỉ trình bày), Action cho Space ở mặt sau.
2. Snapshot phiên chứa cấu hình + hash. Khôi phục phiên thiếu cấu hình thì dùng mặc định 4 nút (tương thích).
3. Server từ chối Action ngoài tập (REST, batch, MCP nếu gọi qua composition).
4. UI hiển thị 2 hoặc 3 nút theo cấu hình; phím tắt ánh xạ lại; khoảng thời gian xem trước chỉ cho Action hiện có.
5. Analytics: không cần đổi (Action vẫn thuộc bộ 4).

## Output đầu ra bắt buộc

Schema + migration + test server (từ chối Action); UI + test; handoff.

## Acceptance criteria

- Cách học 2 nút: người học chỉ thấy và chỉ gửi được 2 Action; server trả `ACTION_NOT_ALLOWED` với Action khác.
- Phiên cũ không có cấu hình vẫn chạy 4 nút.
- Golden vectors thuật toán không đổi.

## Verification

```text
python scripts/run_tests.py --module study,connect_mcp --backend-only
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Cấu hình trống thì dùng 4 nút; flag tắt kiểm tra server.

## Không làm trong task này

Action mới hoặc thang đánh giá khác (P8); thuật toán mới.
