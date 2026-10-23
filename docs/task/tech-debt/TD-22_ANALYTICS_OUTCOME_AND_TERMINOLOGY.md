# TD-22 — Analytics theo outcome; tách thuật ngữ `StudyMode` và `ReviewKind`

> Mức: **P3** · Đợt: W6 · Trạng thái: `DECISION` (D-U6)
>
> Phụ thuộc: TD-20 · Lane: Backend Analytics + Frontend Statistics/Admin · Ước lượng: 3–4 ngày
>
> Nguồn: UX-E5, P8-UI-9 ở [điều tra UI/UX trước P8](../../backend/old/decoupling/UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); canonical plan §9.4.

## Mục tiêu

- Analytics không còn gắn cứng chuỗi rating để tính đúng/sai.
- Tên trường API không dùng "mode" cho ReviewKind, để dành `StudyMode` cho cách học.

## Bối cảnh

- "Đúng" = `good`/`easy`/`3`/`4` ở nhiều nơi: `app/repositories/stats_query_repository.py:684, 780`; `admin_analytics_repository.py:86, 338`; `StudyCompletionCard.tsx:65-67`.
- Admin API trả `modes_breakdown` nhưng dữ liệu là review/learn/relearn (`app/repositories/admin_analytics_repository.py:457`, `admin_analytics_service.py:188`; `frontend/src/features/admin/types/analytics.ts:107`).

## Phạm vi file dự kiến

Các repository/service analytics trên; `features/statistics/*`, `features/admin/*`; một hàm phân loại outcome dùng chung (backend + frontend).

## Công việc chi tiết

1. Hàm phân loại outcome theo Interaction:
   - bộ 4 nút ánh xạ theo D-U6 ("Khó" có tính đúng không);
   - Interaction sau này khai báo outcome của mình.
2. Thay mọi chỗ so chuỗi rating bằng hàm này (SQL: biểu thức dựng từ bảng ánh xạ).
3. Đổi `modes_breakdown` thành `review_kinds_breakdown`; giữ alias cũ một chu kỳ phát hành; cập nhật type frontend.
4. Màn hoàn thành và thống kê dùng cùng định nghĩa và hiển thị chú thích định nghĩa.

## Output đầu ra bắt buộc

Hàm dùng chung + thay thế + alias API + test số liệu không đổi (khi D-U6 giữ định nghĩa cũ); handoff.

## Acceptance criteria

- Grep không còn so chuỗi `good`/`easy` trong analytics ngoài bảng ánh xạ.
- Số liệu thống kê hiện tại không đổi nếu D-U6 giữ định nghĩa cũ; nếu đổi thì có ghi chú phát hành.
- Client cũ đọc `modes_breakdown` vẫn chạy trong thời gian alias.

## Verification

```text
python scripts/run_tests.py --module analytics,admin,study --backend-only
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Alias giữ tương thích; revert hàm phân loại.

## Không làm trong task này

Outbox/secondary consumer (XP, streak) của P8.
