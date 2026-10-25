# Bật bộ đếm dashboard/thống kê — rehearsal 2026-10-25

> Trạng thái: **đã rehearsal trên bản dump production 2026-10-25, chưa bật trên production.** Bật là thay đổi cấu hình production, cần chủ sản phẩm duyệt. Runbook gốc: `docs/ops/old/ANALYTICS_COUNTS_RUNBOOK.md`.

"Bộ đếm" gồm ba bản tóm tắt dựng sẵn thay cho câu đếm trực tiếp:

- tổng ôn theo ngày (`REVIEW_ANALYTICS_*`): heatmap, streak, study-time;
- số đếm theo deck (`DECK_COUNT_*`): dashboard;
- bucket dự báo (`FORECAST_SUMMARY_*`): phần tương lai của overview/today-future.

## Sửa trước khi bật (`a1610c8f`)

Mọi install trên production áp dụng release có `template_pins_initialized = 0` (release phát hành trước khi có pin template). Điều kiện kiểm tra install loại các release này, nên không deck cài đặt nào có snapshot. Kết quả: learner có install vẫn đọc câu đếm trực tiếp, ví dụ user 4 có 171 deck và dashboard mất 2,1 s.

Release chưa pin đọc các occurrence ACTIVE hiện hành. Khi một occurrence đổi trạng thái, global content epoch tăng, và epoch đó đã nằm trong dependency vector; snapshot dự báo cũng dựa vào điều này. Vì vậy chỉ cần bỏ điều kiện. Commit này cũng gộp hai lần đọc lặp: dòng deck, tổ tiên và clone map trước đây được đọc riêng cho bên owned và bên installed, giờ chỉ đọc một lần.

## Bằng chứng (DB `flama_prod_rehearsal_20261025_idx`, head `20261025_000074`)

Rehearsal dùng 5 learner có ôn trong 30 ngày (1, 2, 20, 19, 4). Với mỗi learner, so JSON giữa chế độ raw và summary trên 6 endpoint: dashboard, overview 2026, overview 2025, today-future 12m/30, today-future all/all và study-time 90d. Kết quả **30/30 giống hệt**. Mỗi request chạy trong app context mới, kết nối READ ONLY, lấy trung vị của 3 lần chạy sau 1 lần làm nóng.

| User (deck, install) | Dashboard raw → summary | Overview 2026 | Today-future 12m |
|---|---|---|---|
| 1 (1.534, 0) | 471 → 207 ms | 520 → 62 ms | 711 → 53 ms |
| 4 (1.852, 1) | 2.133 → 334 ms | 1.744 → 63 ms | 1.962 → 62 ms |
| 2 (209, 2) | 2.029 → 74 ms | 2.027 → 37 ms | 2.077 → 33 ms |
| 20 (290, 7) | 2.492 → 95 ms | 2.414 → 44 ms | 2.452 → 40 ms |
| 19 (171, 1) | 1.700 → 71 ms | 1.656 → 36 ms | 1.780 → 33 ms |

Overview của năm cũ và study-time vốn đã nhanh (12–60 ms) nên gần như không đổi.

- **Ngay sau khi học:** deck vừa ôn có learner revision mới nên snapshot của nó cũ cho tới lần prewarm kế tiếp (timer chạy mỗi phút). Khi đó dashboard chỉ đếm trực tiếp deck đó: user 1 tăng 203 → 209 ms, user 4 339 → 344 ms, user 2 74 → 107 ms.
- **Chi phí ghi** (`scripts/bench_review_projection_mysql.py`, 240 mẫu mỗi trường hợp): bật cả hai bộ ghi làm p95 của lệnh trả lời tăng 52,46 → 54,13 ms (+1,67 ms, +3,2%), trong ngưỡng ≤ 5 ms và ≤ 10%. Bộ ghi tổng ôn qua outbox có độ trễ p95 1,05 s ở local.
- **Global epoch** tăng khi sửa hoặc phát hành template, phát hành hoặc cài release, xoá deck/Note/note type hàng loạt, và khi cờ market-active của install đổi. Mỗi lần tăng làm cũ mọi snapshot. Trong 30 ngày trước bản dump có khoảng 125 sự kiện như vậy, rơi vào 6–10 ngày. Dựng lại toàn bộ snapshot của 5 learner mất khoảng 20 s ở local. Timer production dựng tối đa 100 deck mỗi learner mỗi phút, nên user 1 cần khoảng 16 phút. Trong lúc đó các deck cũ đọc trực tiếp, tức là không chậm hơn hiện nay quá vài phần trăm.
- **Kiểm thử:** `tests.test_deck_count_snapshots` có thêm test cho release chưa pin; test này fail trên quy tắc cũ. Module analytics và decks: 353 test pass. Các probe MySQL `probe_deck_counts_mysql` (15 kiểm tra), `probe_dashboard_due_counts_mysql` và `probe_forecast_snapshots_mysql` đều pass.

## Các bước trên production (chờ duyệt)

Các cờ là GitHub-managed variable. Nếu variable để trống, lần deploy giữ nguyên giá trị đang có trong `/etc/flama/flama.env`.

1. Deploy code có `a1610c8f` (cùng migration `000074`).
2. Bật hai bộ ghi, vẫn đọc raw: `REVIEW_ANALYTICS_WRITE_ENABLED=1`, `DECK_COUNT_WRITE_ENABLED=1`, `DECK_COUNT_READ_MODE=raw`, `DECK_COUNT_PREWARM_USER_IDS=1,2,20,19,4`. Restart app.
3. Chạy `review-analytics-backfill --user-id N --apply` cho từng learner, sau đó `review-analytics-reconcile` phải ra 0 mismatch. Tiếp theo chạy `deck-counts-invalidate --apply` và bật `flama-review-analytics-worker.timer` cùng `flama-analytics-counts.timer`. Chờ `deck-counts-status` và `forecast-summary-status` báo đã có snapshot.
4. Chuyển sang đọc summary: `REVIEW_ANALYTICS_READ_MODE=summary`, `REVIEW_ANALYTICS_READ_USER_IDS=1,2,20,19,4`, `DECK_COUNT_READ_MODE=summary`, `FORECAST_SUMMARY_READ_MODE=summary`, `FORECAST_SUMMARY_READ_USER_IDS=1,2,20,19,4`. Restart app.
5. Rollback: đặt các `*_READ_MODE` về `raw` rồi restart. Không cần đổi dữ liệu.

Ghi chú:

- `DECK_COUNT_READ_MODE` không có allowlist theo user. Learner ngoài danh sách prewarm vẫn tính dependency vector rồi đọc trực tiếp, nên tốn thêm một chút.
- Không đặt `ANALYTICS_REQUIRE_READY_USER_IDS`: cờ này biến mọi lần đọc trực tiếp thành lỗi 409.

## Còn lại

- **Đếm trực tiếp deck cài đặt chậm** (phát hiện ngày 2026-10-25). Theo đơn vị Note, nửa installed của scope (`_installed_presentations` + `clone_source_card_visibility`) vẫn tách mỗi Note thành các occurrence: với user 20, 14.835 Note thành 42.459 dòng. Truy vấn chạy `EXISTS` membership của release 114.598 lần, rồi đếm distinct application theo Note, tốn khoảng 2,4 trên 2,5 s. Nửa owned đã là một dòng mỗi Note, nối với số application theo note type. Khi bộ đếm đã bật, đường này chỉ chạy sau khi global epoch tăng và với deck vừa học, nhưng vẫn là nguyên nhân gốc khiến learner có install chậm gấp 4–5 lần user 1. Phần này thuộc vùng clone overlay, nên đọc `docs/backend/old/completed-plans/CLONE_CUTOVER_REPORT.md` trước khi sửa.
- Index composite nhóm 3 của `review_events` cần duyệt riêng theo AGENTS.md.
- Vấn đề 1, 3, 4 của `DASHBOARD_COUNT_READ_PATH_PARKED_2026-10-24.md` vẫn tạm hoãn.
