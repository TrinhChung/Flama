# Đường đọc của số đếm dashboard/heatmap — tạm hoãn

> Ngày 2026-10-24. Trạng thái: **tạm hoãn** theo quyết định của chủ sản phẩm (vấn đề 1, 3, 4). Đã làm xong: gỡ guard quét tiến độ (`7b73a2cb`), quy tắc chọn Card của P11 (`ac6ee32a`), **vấn đề 2** ngày 2026-10-25 (`82afc733`, heatmap 535 → 307 ms) và bỏ câu đọc toàn bộ lịch sử ngày học khi streak nằm trong năm (`50016b6c`, −75 ms).

Số đo trên bản dump production, user 1 (39.338 Note, 1.469 deck, đếm theo Note như production). Sau hai thay đổi trên: số đếm dashboard khoảng 0,6 s, phần tương lai của heatmap khoảng 0,8 s.

## Nguyên nhân gốc

Câu đếm đi từ **toàn bộ Note** của learner rồi tra tiến độ cho từng Note, trong khi thông tin cần gần như chỉ nằm ở các dòng tiến độ đã lên lịch và một bản đồ Note → deck nhỏ.

| # | Vấn đề | Số đo | Hướng sửa gốc |
|---|---|---|---|
| 1 | Đọc nguyên dòng `notes` (trung bình 2.786 byte, gồm nội dung field) chỉ để lấy `id`, `deck_id`, `note_type_id` | 39.338 dòng ≈ 105 MB mỗi request (+ khoảng 40 MB tiến độ), lớn hơn buffer pool production 128 MiB. Đếm Note qua index: 232 lượt đọc trang; lấy thêm deck/type: 129.791 lượt | Lấy bản đồ Note → deck mà không đọc dòng rộng: dùng `ix_notes_user_deck (user_id, deck_id)` (migration `000073` của session browse) hoặc index có `note_type_id`. Index mới phải trình bày và được duyệt theo AGENTS.md |
| 2 | Heatmap tra tiến độ mỗi Note hai lần (`live_note_id` trong `learner_note_scope`, rồi `logical_note_key` trong `note_rows`) | 93.914 lần tra khoá (dashboard 78.710); lần tra thừa khoảng 0,25 s | Bỏ lần tra theo `live_note_id`: bộ lọc "có ngày đến hạn" đã đủ, vì `ck_sp_subject_progress_group` bắt dòng không có trạng thái thì không có ngày đến hạn. Chỉ sửa code |
| 3 | Tra tiến độ cả Note đang "mới" | 23.897 / 39.338 (61%) là `new`; chỉ 15.441 đã lên lịch, đọc được qua `ix_sp_subject_note_due` | Đổi chiều: đi từ dòng tiến độ đã lên lịch; "mới" = tổng Note của deck − đã lên lịch. Giữ đúng quy tắc buried/suspended (`is_buried` không nằm trong index) |
| 4 | Dashboard và heatmap mỗi bên dựng scope riêng | Hai request độc lập | Xem lại sau khi xong 1–3 |

## Bằng chứng bổ sung (2026-10-25)

- **Production (chỉ đọc, user SELECT-only):** buffer pool 134.217.728 byte. Trong 602.253 s (khoảng 7 ngày) có 8.762.354 lần đọc trang từ đĩa trên 517.716.255 lần truy cập trang (khoảng 134 GiB đọc đĩa).
  - Đếm Note của user 1 qua index: 28 ms, 113 trang đọc đĩa.
  - Lấy `deck_id`/`note_type_id` của user 1 (phải đọc dòng đầy đủ): 172 / 167 / 178 ms, mỗi lần 5.497–5.963 trang đọc đĩa (khoảng 86 MiB), kể cả ba lần chạy liền nhau. Dữ liệu Note không ở lại được trong buffer pool.
  - Đọc toàn bộ dòng tiến độ của user 1: 41 ms, 168 trang. Bảng tiến độ vẫn nằm trong cache.
- **Thành phần dòng `notes` (user 1):** `field_values_by_id` trung bình 1.849 byte trên tổng 2.786 byte. Ba cột cần cho số đếm khoảng 80 byte.
- **A/B vấn đề 2 trên dump:** bỏ lần tra theo `live_note_id` cho kết quả giống hệt (user 1/4/2: 25/1/59 ngày, tổng 15.203/1.064/543). Thời gian 587 → 322 ms, lượt đọc trang 549.199 → 339.404, lượt tra khoá 93.914 → 54.576.
- **Bury/suspend:** hiện 0 dòng tiến độ bị bury hoặc suspend. Trạng thái bury có thể đến từ import Anki (`anki_sync_service`) và trạng thái scheduler (`study_note_card_projection._burial_anchors`), nên không phải luôn bằng 0. Cách "trừ" ở vấn đề 3 vẫn phải xử lý Note mới bị bury; `is_buried` không nằm trong `ix_sp_subject_note_due`.
- **Ghi vào `notes`:** tạo mới theo tháng 2026-07: 68, 08: 18.374, 09: 21.818, 10: 1.364 (chủ yếu import hàng loạt). Sửa nội dung field không đổi `user_id`/`deck_id`/`note_type_id`.
- **Index có sẵn:** `ix_notes_user_id`, `ix_notes_deck_id`, `ix_notes_note_type_id`; `ix_notes_user_deck (user_id, deck_id)` mới có ở local (migration `000073` của session browse). Nếu đề xuất index cho vấn đề 1, nên cân nhắc mở rộng index đó thành `(user_id, deck_id, note_type_id)`: nó thay được `ix_notes_user_id` (tiền tố `user_id`), nên số index trên `notes` không tăng.

## Điều kiện quay lại

- Thời gian dashboard hoặc heatmap trên production vượt mức chấp nhận được, hoặc có learner vượt khoảng 40 nghìn Note.
- Hoặc có thay đổi khác cần chạm vào `note_analytics_scope_repository.py` / `note_analytics_read_repository.py` (làm luôn vấn đề 2 khi đó).

## Khi làm

1. Vấn đề 2 trước (nhỏ, chỉ sửa code). Kiểm tra parity JSON của dashboard/overview và probe `scripts/probe_dashboard_due_counts_mysql.py`.
2. Vấn đề 3 và 1 cùng nhau. Đo số lượt đọc trang (`Innodb_buffer_pool_read_requests`) chứ không chỉ thời gian, vì buffer pool local 2 GiB che mất chi phí đọc dòng rộng.
3. Chỉ đề xuất index khi cách không thêm index vẫn chưa đủ, kèm phân tích chi phí ghi (import, đổi deck, đổi note type, xoá Note).
