# Đề xuất gỡ index thừa — chờ duyệt

> Ngày 2026-10-25. Trạng thái: **đề xuất, chưa thay đổi gì** (theo quy định index trong `AGENTS.md`). Số liệu production đọc bằng root qua socket, chỉ SELECT; dữ liệu thô ở `output/index-audit-20261025/` (gitignored).

## Nguồn số liệu và giới hạn

- MySQL 8.0.46, `performance_schema.table_io_waits_summary_by_index_usage` tính từ lần khởi động cách đây **7,43 ngày** (khoảng 2026-10-17 → 2026-10-25). Dung lượng từng index lấy từ `mysql.innodb_index_stats` (ước tính theo trang).
- "Lượt đọc" = số lần một query tìm dòng qua index đó. `performance_schema` **không** quy INSERT cho từng index, nên không dùng được bảng này để đo chi phí cập nhật index; chi phí ghi được ước lượng theo tần suất ghi của bảng (mục cuối).
- Cửa sổ 7,4 ngày không chứa đợt import Anki hay xuất bản bản phát hành nào (các index chỉ dùng cho hai việc này đều 0 lượt đọc), nên "0 lượt đọc" một mình **không** đủ để gỡ. Mỗi index trong nhóm 1 có thêm một lý do cấu trúc: hoặc trùng tiền tố, hoặc không có query nào lọc theo nó.
- Toàn schema: 482 index phụ, 706,9 MiB.

## Nhóm 1 — Đề xuất gỡ (23 index, khoảng 105,9 MiB, 15% dung lượng index phụ)

"Trùng tiền tố" = có index khác (không bỏ) bắt đầu bằng đúng các cột này, nên mọi query dùng được index cũ thì dùng được index thay thế; khoá ngoại cũng được index thay thế đỡ.

| # | Bảng.index (cột) | Dung lượng | Lượt đọc 7,4 ngày | Lý do | Index thay thế |
|---|---|---|---|---|---|
| 1 | `review_events.ix_review_events_study_session_id` (study_session_id) | 2,48 MiB | 0 | Trùng tiền tố | `uq_review_events_session_sequence` (study_session_id, sequence_no) |
| 2 | `review_events.ix_review_events_user_id` (user_id) | 2,52 MiB | 135.159 | Trùng tiền tố | 6 index khác bắt đầu bằng `user_id`, gần nhất `ix_review_events_user_reviewed_at` |
| 3 | `review_events.ix_review_events_review_kind` (review_kind) | 2,52 MiB | 0 | 4 giá trị; không query nào lọc theo cột này; tạo từ `startup_schema` | — |
| 4 | `review_events.ix_review_events_scheduler_mode` (scheduler_mode) | 2,52 MiB | 0 | Cột chỉ có 1 giá trị; code chỉ `GROUP BY` (admin) | — |
| 5 | `notes.ix_notes_user_id` (user_id) | 2,52 MiB | 39.338 | Trùng tiền tố | `ix_notes_user_deck` (user_id, deck_id), đã có trên production |
| 6 | `card_presentation_aliases.ix_card_presentation_aliases_note_id` (note_id) | 15,64 MiB | 1.536 | Trùng tiền tố; bảng đóng băng nên chỉ lợi dung lượng | `uq_presentation_alias_note_application` |
| 7 | `deck_working_dirty_entities.ix_deck_working_dirty_entities_deck_item_id` (deck_item_id) | 13,61 MiB | 1.186 | Trùng tiền tố (3 index khác) | `uq_deck_working_dirty_item_entity_property`, `ix_..._entity_scope`, `ix_..._publish` |
| 8 | `deck_release_changes.ix_deck_release_changes_release_id` (release_id) | 8,56 MiB | 0 | Trùng tiền tố | `uq_deck_release_changes_release_key`, `ix_..._diff_cursor` |
| 9 | `connect_review_event_refs.ix_connect_review_event_refs_user_id` (user_id) | 9,55 MiB | 0 | Trùng tiền tố | `ix_..._source_card`, `uq_..._source_review` |
| 10 | `connect_review_event_refs.ix_connect_review_event_refs_status` (status) | 9,55 MiB | 0 | Query duy nhất lọc `status` cũng lọc `user_id, source_key, external_card_id IN (…)` (`connect/import_cards.py:775`) | `ix_..._source_card` |
| 11 | `media_assets.ix_media_assets_note_id` (note_id) | 3,52 MiB | 34.092 | Trùng tiền tố | `uq_media_assets_note_sha_identity` |
| 12 | `connect_import_media.ix_connect_import_media_session_id` | 4,55 MiB | 0 | Trùng tiền tố | `uq_connect_import_media_session_filename` |
| 13 | `deck_release_entity_memberships.ix_deck_release_entity_memberships_deck_item_id` | 2,52 MiB | 0 | Trùng tiền tố | `ix_deck_release_memberships_deck_visibility` |
| 14 | `deck_release_note_checkpoints.ix_deck_release_note_checkpoints_release_id` | 2,52 MiB | 0 | Trùng tiền tố | `ix_deck_release_note_checkpoints_release_deck` |
| 15 | `study_session_cards.ix_study_session_cards_session_id` | 2,25 MiB | 3.580 | Trùng tiền tố | `ix_study_session_cards_session_ordinal` |
| 16 | `connect_source_card_refs.ix_connect_source_card_refs_user_id` | 1,52 MiB | 0 | Trùng tiền tố | `ix_connect_source_card_refs_source_note` |
| 17 | `connect_source_note_refs.ix_connect_source_note_refs_user_id` | 1,52 MiB | 2 | Trùng tiền tố | `uq_connect_source_note_refs_source_note` |
| 18–23 | `media_field_migration_items.ix_..._{action, entity_id, reason, deck_id, entity_type, user_id}` | 17,6 MiB tổng | 0 | Bảng nhật ký của công cụ chuẩn hoá media; không có query nào lọc theo 6 cột này (chỉ `run_id`, giữ) | — |

Tuỳ chọn: thêm 53 index trùng tiền tố nhỏ còn lại (tổng 1,77 MiB, mỗi cái ≤ 0,3 MiB; payment, token, template, change request…). An toàn theo định nghĩa nhưng lợi gần như bằng 0.

## Nhóm 2 — Giữ (0 lượt đọc nhưng phục vụ thao tác hiếm trên bảng lớn)

| Index | Vì sao giữ |
|---|---|
| `review_events.ix_review_events_user_card_reviewed_at`, `ix_review_events_user_note` | Đổi thuật toán (`study_algorithm_history_cut_service`), lịch sử theo Note |
| `review_events.ix_review_events_note_type_id` | Xoá note type cập nhật `review_events` theo cột này; không có index sẽ quét 124 nghìn dòng |
| `review_events.ix_review_events_card_id` (11,5 MiB) | Code app chỉ lọc kèm `user_id`, nhưng probe/script lọc `card_id` riêng; độ tin cậy trung bình, xem lại khi có số liệu dài hơn |
| `card_presentation_aliases.ix_..._application_id` | Xoá application (`study_content_delete_service`) |
| `connect_review_event_refs.ix_..._source_card`, các index khoá ngoại của Connect | Import Anki/Connect (không có đợt import nào trong cửa sổ đo) |
| `deck_working_dirty_entities.ix_deck_working_dirty_publish`, `deck_release_changes.ix_..._diff_cursor` | Xuất bản và xem diff bản phát hành |
| Mọi index unique và index là chỗ đỡ duy nhất của khoá ngoại (98 index, 81 MiB) | Bắt buộc về đúng đắn/InnoDB |

## Nhóm 3 — Cần tinh chỉnh plan, không gỡ thẳng

`review_events.ix_review_events_user_scheduler_reviewed_at` (7.258.279 lượt đọc) và `ix_review_events_user_kind_reviewed_at` (1.334.177 lượt đọc): MySQL đang dùng hai index này cho các query theo user + ngày, vì chúng bắt đầu bằng `user_id`. Với `scheduler_mode` chỉ một giá trị và `review_kind` gần như cố định, chúng là bản to hơn của `ix_review_events_user_reviewed_at`. Gỡ sẽ đổi plan của mọi query `review_events` theo user, nên phải `EXPLAIN` từng query trước, cùng lúc với lỗi chọn sai index của heatmap quá khứ (`uq_review_events_user_client_event`, 8.459.852 lượt đọc).

## Lợi và hại

**Tần suất ghi trên production:** `review_events` 25–635 dòng/ngày (tháng 10: 4.054; tháng 5–6: 10–14 nghìn/tháng); dòng tiến độ 22–1.768 cập nhật/ngày; `deck_working_dirty_entities` nhận 250.780 dòng một lượt trong tháng 10; `deck_release_changes` 162.953 dòng trong tháng 8; `connect_review_event_refs` ghi khi import.

**Lợi:**
- Mỗi dòng ghi cập nhật ít index hơn: `review_events` 16 → 12, `connect_review_event_refs` 6 → 4, `deck_working_dirty_entities` 5 → 4, `deck_release_changes` 6 → 5, `media_field_migration_items` 7 → 1. Ghi thường ngày hiện đã rẻ nên khác biệt chủ yếu thấy ở thao tác hàng loạt (import, đánh dấu dirty, xuất bản). Chưa đo thời gian của các thao tác đó.
- Bớt khoảng 105,9 MiB index trên đĩa và bớt trang index phải nạp vào buffer pool khi ghi.

**Hại:**
- Các query đang đọc qua index trùng tiền tố (`review_events.user_id` 135 nghìn lượt, `notes.user_id` 39 nghìn, `media_assets.note_id` 34 nghìn, `study_session_cards.session_id` 3,6 nghìn…) sẽ chuyển sang index dài hơn có cùng cột đầu: tìm đúng các dòng như cũ, nhưng mục index to hơn nên có thể chậm hơn một chút, và MySQL có thể chọn index khác với dự tính. Phải `EXPLAIN` các query nóng trước/sau trên bản dump.
- Index nhóm 1 phục vụ một query hiếm mà đọc code không thấy: rủi ro thấp vì mỗi index đều có lý do cấu trúc ngoài số liệu 7,4 ngày.

**DDL, triển khai, rollback:**
- `DROP INDEX` trên InnoDB 8.0 chạy `ALGORITHM=INPLACE, LOCK=NONE`, chỉ đổi metadata, không dựng lại bảng; cần khoá metadata ngắn, nên chạy lúc không có transaction dài.
- Rollback: tạo lại index online (`ADD INDEX … ALGORITHM=INPLACE, LOCK=NONE`); thời gian tỉ lệ với bảng (bảng lớn nhất ở đây khoảng 250 nghìn dòng).
- Phải sửa đồng thời: một migration Alembic (có downgrade tạo lại), bỏ `index=True`/`db.Index` tương ứng trong `models/` (để autogenerate không tạo lại), bỏ các dòng `CREATE INDEX` tương ứng trong `app/startup_schema.py` (để chế độ bảo trì lúc dev không tạo lại), và cập nhật test kiểm tra tên index nếu có.

## Các bước sau khi được duyệt

1. Viết migration và sửa model/`startup_schema`; chạy `--module` test liên quan và các probe MySQL.
2. Rehearsal trên bản dump production mới: `EXPLAIN` các query nóng (dashboard, heatmap, Statistics, study, import Connect, đánh dấu dirty, xuất bản) trước/sau; ghi lại thời gian.
3. Mở PR riêng; deploy lúc ít người dùng.
