# Đường đọc của số đếm dashboard/heatmap — tạm hoãn

> Ngày 2026-10-24. Trạng thái: **tạm hoãn** theo quyết định của chủ sản phẩm. Đã làm xong trước đó: gỡ guard quét tiến độ (`7b73a2cb`) và quy tắc chọn Card của P11 (`ac6ee32a`).

Số đo trên bản dump production, user 1 (39.338 Note, 1.469 deck, đếm theo Note như production). Sau hai thay đổi trên: số đếm dashboard khoảng 0,6 s, phần tương lai của heatmap khoảng 0,8 s.

## Nguyên nhân gốc

Câu đếm đi từ **toàn bộ Note** của learner rồi tra tiến độ cho từng Note, trong khi thông tin cần gần như chỉ nằm ở các dòng tiến độ đã lên lịch và một bản đồ Note → deck nhỏ.

| # | Vấn đề | Số đo | Hướng sửa gốc |
|---|---|---|---|
| 1 | Đọc nguyên dòng `notes` (trung bình 2.786 byte, gồm nội dung field) chỉ để lấy `id`, `deck_id`, `note_type_id` | 39.338 dòng ≈ 105 MB mỗi request (+ khoảng 40 MB tiến độ), lớn hơn buffer pool production 128 MiB. Đếm Note qua index: 232 lượt đọc trang; lấy thêm deck/type: 129.791 lượt | Lấy bản đồ Note → deck mà không đọc dòng rộng: dùng `ix_notes_user_deck (user_id, deck_id)` (migration `000073` của session browse) hoặc index có `note_type_id`. Index mới phải trình bày và được duyệt theo AGENTS.md |
| 2 | Heatmap tra tiến độ mỗi Note hai lần (`live_note_id` trong `learner_note_scope`, rồi `logical_note_key` trong `note_rows`) | 93.914 lần tra khoá (dashboard 78.710); lần tra thừa khoảng 0,25 s | Bỏ lần tra theo `live_note_id`: bộ lọc "có ngày đến hạn" đã đủ, vì `ck_sp_subject_progress_group` bắt dòng không có trạng thái thì không có ngày đến hạn. Chỉ sửa code |
| 3 | Tra tiến độ cả Note đang "mới" | 23.897 / 39.338 (61%) là `new`; chỉ 15.441 đã lên lịch, đọc được qua `ix_sp_subject_note_due` | Đổi chiều: đi từ dòng tiến độ đã lên lịch; "mới" = tổng Note của deck − đã lên lịch. Giữ đúng quy tắc buried/suspended (`is_buried` không nằm trong index) |
| 4 | Dashboard và heatmap mỗi bên dựng scope riêng | Hai request độc lập | Xem lại sau khi xong 1–3 |

## Điều kiện quay lại

- Thời gian dashboard hoặc heatmap trên production vượt mức chấp nhận được, hoặc có learner vượt khoảng 40 nghìn Note.
- Hoặc có thay đổi khác cần chạm vào `note_analytics_scope_repository.py` / `note_analytics_read_repository.py` (làm luôn vấn đề 2 khi đó).

## Khi làm

1. Vấn đề 2 trước (nhỏ, chỉ sửa code). Kiểm tra parity JSON của dashboard/overview và probe `scripts/probe_dashboard_due_counts_mysql.py`.
2. Vấn đề 3 và 1 cùng nhau. Đo số lượt đọc trang (`Innodb_buffer_pool_read_requests`) chứ không chỉ thời gian, vì buffer pool local 2 GiB che mất chi phí đọc dòng rộng.
3. Chỉ đề xuất index khi cách không thêm index vẫn chưa đủ, kèm phân tích chi phí ghi (import, đổi deck, đổi note type, xoá Note).
