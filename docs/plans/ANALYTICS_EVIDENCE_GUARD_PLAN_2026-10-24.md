# Kế hoạch: guard toàn vẹn tiến độ học nằm trong scope + chọn nhánh SQL theo múi giờ

> Ngày 2026-10-24. Trạng thái: **đã hoàn thành** (commit 1–6, xem mục 6). Chạy trên MySQL local (bản dump production), chưa deploy.

## 1. Bối cảnh

Heatmap (`GET /api/statistics/overview`) có hai nhánh tính "thẻ đến hạn tương lai". Nhánh Python báo lỗi 409 khi tiến độ học của note bị lệch/hỏng; nhánh MySQL (múi giờ offset cố định) không kiểm tra mà vẫn trả số. Lỗ hổng có từ `4c1d87fb` (2026-10-04). Không mất dữ liệu; hiện không user nào bị ảnh hưởng.

Số liệu bản dump: 33 user, 8 learner có tiến độ; múi giờ Asia/Tokyo 18, Asia/Saigon 8, Asia/Bangkok 3, UTC 3, Asia/Shanghai 1 — không ai dùng múi giờ DST. `Asia/Saigon` không có trong `MYSQL_FIXED_OFFSET_MINUTES` nên đi nhánh Python: overview của user 1 mất 4,55 s so với 1,54 s ở nhánh SQL (`Asia/Ho_Chi_Minh`), kết quả giống hệt.

### Nguyên nhân gốc và cách xử lý

| Nguyên nhân | Xử lý |
|---|---|
| Guard là việc từng nơi đọc tự nhớ (`note_rows()` trả cột `violation`, nơi đọc tự `max` → `violation_error` → `raise`; nhánh MySQL quên) | Guard chạy bên trong 3 hàm dựng scope dùng chung (`deck_note_scope`, `collection_note_scope`, `learner_note_scope`); gỡ code tự đọc `violation` ở các nơi đọc. |
| Chọn nhánh SQL theo danh sách tên múi giờ viết tay | Chọn theo tính chất: múi giờ có offset không đổi (kiểm tra bằng `zoneinfo`, có cache) → SQL; ngược lại → Python. |
| Không test nào canh sự tương đương; probe parity hỏng từ `cc657c25` mà không ai biết | Sửa probe, chạy trong job `mysql-contract` của CI, bổ sung `MYSQL_CONTRACT_SOURCE_PATTERNS`; thêm test hợp đồng fail-closed cho mọi nơi đọc. |

### Nơi đọc (8)

| # | Nơi đọc | Scope | Sau thay đổi |
|---|---|---|---|
| 1 | `deck_aggregation_service.aggregate_deck_study_counts` | `deck_note_scope` | guard trong scope |
| 2 | `stats_overview._canonical_future_due_day_counts` (Python) | `learner_note_scope` | guard trong scope |
| 3 | `stats_query_repository.query_canonical_future_due_day_counts_mysql` | `learner_note_scope` | guard trong scope (**từ đây fail closed**) |
| 4 | `stats_today_future._consolidated_due_rows_and_load` ← `query_consolidated_forecast_rows` | `collection_note_scope` | guard trong scope |
| 5 | `forecast_snapshot_service.prewarm_forecast_summary` ← cùng query | `collection_note_scope` | guard trong scope |
| 6 | `study_repository.query_study_queue_counts` | Card query | giữ kiểm tra trong aggregate (đường nóng) |
| 7 | `browse_card_service` ← `page_window_integrity` | note id của trang | giữ nguyên |
| 8 | `mcp/study_tools.get_deck_stats` | Card query | giữ nguyên (gián tiếp qua `get_due_card_counts`) |

## 2. Thiết kế guard

Một lần cho mỗi lần dựng scope, query riêng, cùng snapshot đọc (`analytics_read_transaction`, prewarm snapshot, hoặc một transaction `REPEATABLE READ`):

1. **Ứng viên theo learner** (rẻ, tập lớn hơn, thường rỗng): dòng có `live_note_id` khác khoá logic → ứng viên `live_note_id`; dòng `live_note_id IS NULL`, tombstone/rekey, hoặc `semantic_state_hash IS NULL` với trạng thái khác `NO_CURRENT_PROGRESS` **và note của khoá logic còn tồn tại** → ứng viên là note đó. (9 tombstone của note đã xoá trên bản dump không được tính.)
2. **Kiểm tra chính xác** nếu có ứng viên: dựng lại đúng scope đó chỉ cho các note ứng viên, tính `max(subject_integrity_violation)` (CASE giữ nguyên) và raise `StudyAuthorityReadError` như hiện nay. Tương đương chính xác cách cũ: cùng CASE, cùng phạm vi; dòng hỏng ngoài scope vẫn không báo lỗi.

Lệch hash vẫn không làm lúc đọc báo lỗi (audit offline phát hiện), như `test_overview_reads_note_availability_and_full_hash_audit_detects_drift` quy định.

Chi phí: ~100 ms cho learner lớn nhất (quét ~39 nghìn subject), vài ms cho learner nhỏ. Dashboard gần như không đổi (thay bước kiểm tra drift của `f9b0d860`); overview nhánh SQL thêm ~100 ms; nhánh Python/today-future/forecast bỏ được EXISTS cho từng note.

## 3. Commit

Làm tiếp trên nhánh hiện tại (checkout dùng chung với agent khác, không đổi nhánh); tách nhánh khi mở PR.

1. **`ci(analytics): repair due-count probe and run analytics MySQL probes in CI`**
   - `scripts/probe_dashboard_due_counts_mysql.py`: fixture "note không có thẻ" đang `Card.query...delete()` (không còn hợp lệ từ `cc657c25`) → dùng note type không có application ACTIVE.
   - `.github/workflows/ci.yml` (job `mysql-contract`, bước `run_mysql_probes.py`): thêm `probe_note_analytics_mysql.py`, `probe_dashboard_due_counts_mysql.py`.
   - `scripts/run_tests.py`: bổ sung `MYSQL_CONTRACT_SOURCE_PATTERNS` (`note_analytics_scope_repository.py`, `stats_query_repository.py`, `stats_today_future.py`, `browse_card_repository.py`).
2. **`test(analytics): fail-closed contract for every progress reader`** — bảng nơi đọc × kịch bản (sạch; con trỏ live lệch; tách khỏi note còn tồn tại; quarantine không có state; tombstone của note đã xoá; dòng hỏng ngoài scope). Nhánh MySQL chạy trên MySQL qua probe; kịch bản #3 trên MySQL là lỗi đã biết cho tới commit 3.
3. **`fix(analytics): guard progress evidence inside the shared scope builders`** — guard trong `note_analytics_scope_repository.py` / `note_analytics_read_repository.py`; gỡ đọc `violation` ở `deck_aggregation_service.py`, `stats_overview.py`, `stats_today_future.py`, `forecast_snapshot_service.py`; gỡ `learner_live_identity_drift` và các tham số tạm của `f9b0d860`.
4. **`perf(stats): pick the SQL path for any constant-offset time zone`** — thay `MYSQL_FIXED_OFFSET_MINUTES` bằng hàm `zoneinfo` (offset không đổi từ 2000 đến nay + vài năm tới, cache); `Asia/Saigon` và mọi tên gọi khác tự đi nhánh SQL.
5. **`feat(frontend): heatmap error state`** — `StudyHeatmap` nhận `error`, `DashboardPage`/`StatisticsPage` truyền lỗi; i18n vi/en.
6. **`docs(analytics): evidence guard contract`** — `docs/backend/ARCHITECTURE.md`; đo lại.

## 4. Kiểm chứng (mỗi commit)

- `scripts/run_tests.py --module analytics --backend-only`; commit 3–4 thêm `--module browse,study --backend-only --jobs auto` (để trống các cờ `STUDY_*` theo `skills/flama-local-dev`).
- Probe MySQL: `probe_note_analytics_mysql.py`, `probe_dashboard_due_counts_mysql.py`.
- Parity JSON trên bản dump: `output/analytics_json_snapshot_20261024.py` (user 1, 4, 2; dashboard + overview hai năm) giống hệt trước/sau; commit 4 thêm so sánh `Asia/Saigon` với `Asia/Ho_Chi_Minh` (`output/saigon_path_compare_20261024.py`).
- Đo lại: `output/dashboard_probe_local_20261024.py`, `output/heavy_query_explain_20261024.py`.
- Frontend: `npx tsc -b`, `npx vitest run --config vite.config.ts src/shared src/pages`.

## 6. Kết quả

| Commit | Nội dung |
|---|---|
| `9b44dd90` | Sửa probe due-count, chạy hai probe analytics trong CI, bổ sung `MYSQL_CONTRACT_SOURCE_PATTERNS` |
| `54f9a3fa` | Test hợp đồng fail-closed (5 nơi đọc × 6 kịch bản) |
| `cea69740` | Guard trong 3 hàm dựng scope; gỡ đọc `violation` ở các nơi đọc |
| `79c02a3a` | Chọn nhánh SQL bằng `fixed_utc_offset_minutes()` (`zoneinfo`) |
| `c5f4ccb1` | Heatmap hiện thông báo lỗi thay cho lưới trống |
| (commit này) | Tài liệu |

Kiểm chứng: test hợp đồng giữ nguyên kỳ vọng sau khi chuyển guard; probe MySQL 144 trường hợp parity (16 múi giờ nhánh SQL, gồm `Asia/Saigon`, +5:30, +5:45, −7:00) và cả hai nhánh cùng báo `DETACHED_AUTHORITY_SUBJECT` khi lệch danh tính; JSON của user 1, 2 (Asia/Tokyo) và 4 (Asia/Saigon, chuyển từ nhánh Python sang SQL) giống hệt trước thay đổi; module analytics 270 test, browse/study/MCP 1.405 test (1 lỗi có sẵn trên HEAD: `test_flama_connect_mcp` trường mảng).

Hiệu năng (user 1, bản dump): dashboard và overview không đổi so với `f9b0d860` (~1,6–1,8 s, nhanh hơn đầu ngày 25–34%); overview với `Asia/Saigon` 4,55 s → 2,03 s.

## 5. Tạm hoãn có điều kiện

| Việc | Làm lại khi |
|---|---|
| Hợp nhất mỗi chỉ số về một bản cài đặt cho mọi múi giờ (gom theo khung 15 phút UTC rồi quy ngày bằng `zoneinfo`) | Có learner dùng múi giờ DST thật, hoặc probe parity báo lệch giữa hai nhánh. |
| CHECK `live_note_id IS NULL OR logical_note_key = CAST(live_note_id AS BINARY)` ở tầng DB (cần audit chỉ-đọc production + migration riêng) | Có sự cố lệch danh tính, hoặc chi phí guard (~100 ms) trở thành vấn đề. |
| Xoá các hàm `query_*` không ai gọi trong `review_event_repository.py` | Lần tới sửa file đó. |
