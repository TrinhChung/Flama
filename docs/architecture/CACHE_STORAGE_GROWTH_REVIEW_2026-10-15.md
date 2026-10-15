# Dung lượng cache, snapshot và archive của Flama

Ngày kiểm tra: 2026-10-15 (Asia/Tokyo).

## Kết luận

Có phần tăng theo mức sử dụng và hiện chưa có retention tự động. Hai điểm đáng chú ý
là outbox đã xử lý vẫn được giữ và các generation thống kê cũ chỉ được đánh dấu
`RETIRED`. Cache đếm deck và forecast cho cùng một scope được ghi đè, không tạo
một bản mới mỗi lần người dùng mở trang.

Số lượng bảng không phản ánh trực tiếp dung lượng. Trong MySQL local vừa đo,
archive Field chiếm khoảng **1,28 GiB**, còn năm bảng cache/summary/outbox bên dưới
đều có **0 hàng**. Chưa có số đo production hoặc Redis để suy ra chi phí thực tế
khi toàn bộ người dùng bật các projection writer.

Đợt sửa Browse đi kèm báo cáo này không thêm bảng, migration hay cache DB.

## Số đo chỉ đọc trên MySQL local

Kết nối trực tiếp bằng SQLAlchemy, transaction `READ ONLY`; không khởi tạo app trên
database thật, không chạy migration/backfill/cleanup và không đọc nội dung ra báo cáo.

| Hạng mục | Quan sát |
|---|---:|
| `field_value_identity_archive`: `DATA_LENGTH` | 1.372.585.984 byte, khoảng 1,28 GiB |
| Archive Note, đếm chính xác | 41.533 hàng |
| Archive media, đếm chính xác | 33.934 hàng |
| Archive rename job, đếm chính xác | 1 hàng |
| Tổng archive | 75.468 hàng |
| `captured_schema`, tổng JSON dạng text | 528.998.827 byte, khoảng 504,5 MiB |
| `source_raw`, tổng độ dài | 74.696.285 byte, khoảng 71,2 MiB |
| `canonical_payload`, tổng JSON dạng text | 103.050.198 byte, khoảng 98,3 MiB |
| `deck_study_count_snapshots` | 0 hàng |
| `study_forecast_snapshots` / `study_forecast_due_buckets` | 0 / 0 hàng |
| `daily_review_counts` / `review_analytics_outbox` | 0 / 0 hàng |
| `review_analytics_generations` | 0 hàng |

`DATA_LENGTH` là dung lượng InnoDB báo qua `information_schema.TABLES`, không phải
độ dài JSON hay dung lượng có thể thu hồi ngay. Các tổng JSON dạng text không thể
cộng vào `DATA_LENGTH`; chúng giải thích loại payload đang được giữ. `TABLE_ROWS`
trong metadata là ước lượng nên bảng trên dùng `COUNT(*)` cho các số hàng chính xác.
Archive lặp schema theo từng object, vì vậy phần schema đã chiếm đáng kể dung lượng
logic. Các số này thuộc database local đang cấu hình, không phải bằng chứng production.

## Bảng nào tăng như thế nào

| Nhóm | Đơn vị tăng trưởng | Ghi đè / dọn dẹp hiện tại |
|---|---|---|
| `deck_study_count_snapshots` | `(user, deck, contract, unit)` | UPSERT cùng khóa; không lưu thêm một hàng mỗi ngày. FK xóa theo user/deck. Contract hiện chỉ có 1, unit có card/note. |
| `deck_count_content_revisions` / `deck_count_learner_revisions` | Deck đã từng bị thay đổi; cặp user/deck đã bị invalidation | Tăng số revision trên cùng hàng. Token deck đã xóa được giữ để tránh tái sử dụng revision; không thấy cleanup cho token này. |
| `study_forecast_snapshots` / `study_forecast_due_buckets` | User × scope khác nhau × nhóm ngày đến hạn/queue | Header UPSERT; xóa bucket cũ của cùng scope rồi thay mới trong một transaction. Không thấy eviction cho scope cũ. |
| `review_analytics_heads` | Một hàng/user | Cập nhật checkpoint cùng hàng. |
| `daily_review_counts` | User × generation × ngày học × scope collection/deck có sự kiện | Cộng dồn vào bucket; không một hàng/review. Bucket thuộc generation, có FK cascade khi generation bị xóa. |
| `review_analytics_generations` | Mỗi lần admit/restart/rebuild thống kê | Generation trước chuyển `RETIRED`; không thấy cơ chế xóa tự động. |
| `review_analytics_outbox` | Transaction review/dirty được capture thành revision | Worker đặt `applied_at`; không xóa hàng hay payload đã xử lý. |
| `field_value_identity_archive` | Object đã chụp trong cutover | Snapshot lịch sử giữ raw/schema/canonical/checksum. Không phải cache TTL; không có runtime writer append theo lượt học sau cutover. |
| `field_value_identity_definitions` | Identity Field được tạo/giữ lại | Ledger nhận diện dữ liệu, có cả identity đã retired. Đây là dữ liệu phục vụ đọc nội dung, không phải cache dùng xong có thể bỏ. |
| `review_events`, progress history/lifecycle, command receipts | Lịch sử học, thay đổi và operation đã xử lý | Bằng chứng/replay/idempotency, không phải cache. Cần chốt horizon retry/undo/restore trước retention. |
| Redis rate limit / MCP preview | Request/key đang trong cửa sổ hiệu lực | Rate limit có EXPIRE/PEXPIRE; MCP preview có TTL mặc định 600 giây. Tăng theo lưu lượng trong cửa sổ, chưa đo maxmemory/eviction thực tế. |

Nguồn: [snapshot models](../../models/deck_count_snapshot.py),
[snapshot UPSERT](../../app/repositories/deck_count_snapshot_repository.py),
[forecast publish](../../app/repositories/forecast_snapshot_repository.py),
[forecast budget](../../app/services/forecast_snapshot_service.py),
[analytics models](../../models/review_analytics.py),
[outbox worker](../../app/services/review_analytics_outbox_service.py),
[Field archive contract](../../migrations/field_identity_contract.py),
[MCP preview](../../app/services/mcp_preview_service.py).

## Các phần cần chốt retention

### 1. Outbox giữ payload sau khi xử lý

- **Observed:** `process_review_analytics_outbox()` cập nhật `applied_at` và giữ hàng.
- **Evidence:** [worker](../../app/services/review_analytics_outbox_service.py),
  [repository](../../app/repositories/review_analytics_outbox_repository.py),
  [runbook](../runbooks/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md) ghi rõ applied outbox chưa có retention tự động.
- **Potential concern:** Xử lý hết pending không làm giảm kích thước feed; khi worker
  chậm, pending còn tăng thêm. `max-revisions`, payload budget và timer chỉ giới hạn
  một lượt xử lý, không giới hạn tổng dữ liệu giữ lại.
- **Impact:** Tăng dung lượng disk, index và backup theo lịch sử ghi. Ví dụ giả định
  10.000 user hoạt động × 200 review/ngày × 1 outbox/review = 2 triệu hàng/ngày.
  Nếu payload trung bình 1 KiB, riêng payload đã khoảng 1,91 GiB/ngày, chưa tính
  row/index/backup. Đây là ví dụ tính toán, không phải benchmark hay lưu lượng đã đo.
- **Unknowns:** Chưa có kích thước payload trung bình, lưu lượng production, backlog,
  checkpoint và thời hạn cần giữ cho backfill/retry/rollback trên production.

### 2. Generation cũ và forecast scope cũ

- **Observed:** Backfill/publish chuyển generation trước sang `RETIRED`. Forecast ghi
  đè cùng scope, nhưng scope hash khác tạo thêm header/bucket.
- **Evidence:** [backfill](../../app/services/review_analytics_backfill_service.py),
  [forecast](../../app/repositories/forecast_snapshot_repository.py),
  [CLI prewarm](../../app/cli.py), [timer service](../../deploy/flama-analytics-counts.service).
- **Potential concern:** Rebuild nhiều lần giữ nhiều bộ bucket cũ; prewarm nhiều tổ
  hợp deck có thể giữ nhiều scope. `valid_until_utc` chỉ từ chối dữ liệu hết hạn
  khi đọc, không phải lịch xóa vật lý.
- **Impact:** Dung lượng phụ thuộc số generation/scope từng tạo. Worker hiện prewarm
  forecast collection với `deck_ids=None`; đọc UI không tự tạo một scope cache mới
  mỗi lần click. Budget mặc định 4.096 bucket giới hạn một scope/lần build, không
  giới hạn tổng scope/user.
- **Unknowns:** Chưa biết số rebuild, scope và tình trạng inactive của người dùng
  trên production. Cần policy giữ generation/scope trước khi bổ sung cleanup.

### 3. Archive cutover đã lớn, còn dữ liệu lịch sử cần bảo toàn

- **Observed:** Archive Field local có 75.468 object và khoảng 1,28 GiB được InnoDB
  cấp phát; mỗi object giữ raw, canonical và captured schema.
- **Evidence:** Số đo trên; [archive schema/gates](../../migrations/field_identity_contract.py),
  [contraction](../../migrations/versions/20261014_000067_contract_field_name_storage.py).
- **Potential concern:** Archive cùng primary DB làm tăng disk/backup dù runtime
  không dùng nó như cache. Các bảng history/receipt cũng tiếp tục tăng theo học tập.
- **Impact:** Đây đã là chi phí dung lượng thực trên local, khác với cache thống kê
  hiện trống. Retention session hiện chỉ dọn membership/pin cũ, không dọn các fact,
  receipt, review event hoặc archive.
- **Unknowns:** Chưa kiểm chứng vị trí archive/backup và full restore production.
  Cần chốt thời hạn giữ và quy trình restore/checksum trước quyết định di chuyển
  hoặc loại bỏ dữ liệu; báo cáo này không thực hiện các thao tác đó.

## Cách đánh giá khi số user tăng

Cache deck tăng theo số cặp user/deck thực sự cache. Ví dụ giả định 10.000 user ×
20 deck × một unit đang dùng là khoảng 200.000 snapshot rows; mở dashboard 100 lần
không nhân con số này lên 100 lần. Dung lượng byte cần đo thay vì suy từ số hàng.

Phần tăng liên tục theo thời gian đáng ưu tiên hơn là outbox đã applied, generations
retired và history/receipt. Cần đo theo bảng: data/index bytes, số hàng, tốc độ tăng
theo ngày, pending lag và số generation/scope không còn dùng; thêm thời hạn lưu và
cleanup có kiểm chứng là công việc còn thiếu trước khi khẳng định dung lượng được
khống chế khi mở rộng toàn bộ người dùng.

Subquery/window trong Browse là câu SQL thực thi theo request. MySQL có thể dùng
internal temporary table để thực thi rồi giải phóng; nó không tạo bảng cache bền
vững mới. Trong kiểm tra MySQL local chỉ đọc, 41.534 Note có presentation đang hoạt
động trả đúng 41.534 dòng Browse sau khi chọn một preview/Note; đây là kiểm tra
cardinality, không phải bằng chứng latency/concurrency production.
