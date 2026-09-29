# Runbook Phase 5 — phát hành R0 (LEGACY) và canary R1 (NOTE)

> Lập 2026-09-29. Nguồn quyết định: [P5 execution plan](../task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md) §1, §7. Mọi lệnh `flask` chạy trong thư mục release với `--app wsgi.py` và `EnvironmentFile` production. Không bước nào ở đây tự chạy trong CI.

## 1. Trạng thái mặc định sau R0

| Cờ | Giá trị R0 | Ghi chú |
|---|---|---|
| `STUDY_WIRE_V4_ENABLED` | `0` | Bật trước khi enroll learner NOTE đầu tiên (R1). CLI từ chối `--apply` NOTE nếu cờ tắt. |
| `STUDY_ASYNC_BATCH_ENABLED` | `0` | Giữ tắt suốt canary R1; CLI từ chối enroll NOTE khi cờ bật. |
| `STUDY_PROGRESS_SHADOW_*` | tắt | Cờ Phase 4, **không** đảo authority của learner NOTE. |
| Enrollment | không learner nào ở NOTE | Route mặc định LEGACY/epoch 0. |

## 2. Cổng trước R0 (bằng chứng trên release candidate)

1. Backend: `python scripts/run_tests.py --all --backend-only` xanh.
2. Frontend: `npm run test` và `npm run build` trong `frontend/` xanh.
3. MySQL disposable (không đụng DB cấu hình; mỗi script tự tạo và xoá DB tạm):
   - `python scripts/probe_p5_authority_schema_mysql.py` — upgrade 39→45, boot `wsgi.py` với cờ tắt, downgrade/re-upgrade rỗng, CAS/receipt/projection/rollback.
   - `python scripts/probe_p5_direct_replay_mysql.py` — direct replay + race, numeric, template topology + race, content delete/purge, overlay/first-state + race, Algorithm switch.
   - `python scripts/probe_p5_study_batch_mysql.py` — worker LEGACY/NOTE, recovery sau mất queue.
   - `python scripts/probe_p5_numeric_storage_mysql.py` — profile lưu số NOTE.
   - Chỉ khi định bật async: `python scripts/probe_p5_study_consumer.py --redis-url <redis cục bộ hoặc tunnel>`.

## 3. R0 — phát hành code, LEGACY mặc định

1. **Backup**: snapshot DB của nhà cung cấp hoặc `mysqldump --single-transaction --routines --triggers <db>`; ghi lại ID/đường dẫn và thời điểm. Không phát hành nếu chưa có backup đọc lại được.
2. Xác nhận `/etc/flama/.flama.env` có `STUDY_WIRE_V4_ENABLED=0`, `STUDY_ASYNC_BATCH_ENABLED=0`.
3. Deploy bằng workflow hiện có (`.github/workflows/deploy.yml` chạy `flask db upgrade` tới head `20260925_000045`, cài `flama-study-worker.service`, kiểm tra `/api/health` và `:4790/healthz`).
4. Smoke LEGACY (tài khoản thật, không enroll): đăng nhập, dashboard, mở phiên học một deck, trả lời 1 thẻ, Browse list/detail, thống kê. Kiểm tra log không có mã `AUTHORITY_*`/`INCOMPLETE_*`.
5. Ghi nhận: SHA release, head migration, ID backup, kết quả smoke.

Rollback R0: deploy lại release trước theo workflow (nhánh rollback code đã có). Không downgrade schema; migrations 40–45 là additive.

## 4. R1 — canary NOTE (thủ công, từng learner)

### 4.1 Chọn và thử khô
```bash
flask --app wsgi.py study-authority-enrollment --user-id <ID> --mode NOTE        # dry-run, tự rollback
```
Kết quả PASS là JSON có `mode_code: "NOTE"`, `applied: false`. Các mã từ chối thường gặp và ý nghĩa:

| Mã | Ý nghĩa | Xử lý |
|---|---|---|
| `INCOMPLETE_AUTHORITY_COVERAGE` | Có Note đã học một phần sibling hoặc thiếu subject shadow | Chọn learner khác; không tự sửa dữ liệu |
| `AUTHORITY_SUBJECT_NOT_READY` | Subject quarantined/detached | Chọn learner khác |
| `CLONE_CUTOVER_PENDING` | Còn install `legacy_copy` chưa cutover | Chờ cutover khi boot rồi thử lại |
| `PENDING_DECK_ORDER` | Đơn mua deck đang treo | Chờ đơn hoàn tất |
| `AUTHORITY_BATCH_IN_FLIGHT` | Còn batch async đang chạy | Chờ worker xử lý xong |

### 4.2 Bật và enroll
1. Đặt `STUDY_WIRE_V4_ENABLED=1` trong `/etc/flama/.flama.env`, `systemctl restart flama.service`.
2. Audit trước: `flask --app wsgi.py study-authority-read-audit --user-id <ID>` → learner còn LEGACY nên `status: "SKIP"`.
3. Enroll: `flask --app wsgi.py study-authority-enrollment --user-id <ID> --mode NOTE --apply`.
4. Audit sau: `flask --app wsgi.py study-authority-read-audit --user-id <ID>` → phải `status: "PASS"`. Có thể cố định thời điểm/múi giờ: `--observed-at-utc 2026-10-01T00:00:00Z --timezone-name Asia/Tokyo`.

### 4.3 Theo dõi (tối thiểu hằng ngày, và sau mỗi lần learner học)
- Chạy lại read audit cho từng learner canary; mọi `BLOCK` là hard stop.
- Log ứng dụng: mã `AUTHORITY_READ_PARITY_DIVERGED`, `STALE_AUTHORITY_*`, `INCOMPLETE_AUTHORITY_*`, `ALGORITHM_IDENTITY_*`, `CONTENT_SCOPE_CHANGED` (mã cuối là xung đột đồng thời, người dùng thử lại được — chỉ đáng lo nếu lặp lại).
- MySQL: lock wait/deadlock tăng bất thường.

**Hard stop** (dừng enroll mới, xem xét rollback): transition được chấp nhận mà không chiếu được về legacy, split-brain/đua epoch, decoder sai, phiên cũ commit qua epoch, mất event/receipt, source clone bị sửa, hoặc audit `BLOCK` không giải thích được.

### 4.4 Rollback một learner (NOTE → LEGACY)
```bash
flask --app wsgi.py study-authority-enrollment --user-id <ID> --mode LEGACY          # dry-run
flask --app wsgi.py study-authority-enrollment --user-id <ID> --mode LEGACY --apply
```
Rollback chỉ commit khi mọi state NOTE còn sống chiếu **không mất mát** về `CardProgress` (subject đã tombstone do xoá nội dung được bỏ qua an toàn). Nếu bị từ chối với `LOSSY_LEGACY_PROJECTION`, `UNPROJECTABLE_LEGACY_STATE` hoặc `ROLLBACK_ALGORITHM_NOT_LEGACY`: **không** sửa cột legacy bằng tay, giữ learner ở NOTE và sửa tiến (forward repair) hoặc khôi phục backup theo quy trình đã duyệt. Không downgrade schema, không xoá dữ liệu trong sự cố. Tắt riêng `STUDY_PROGRESS_SHADOW_*` không đảo authority của learner NOTE.

## 5. Ngoài phạm vi R0/R1 (R2 hoặc Phase sau)
- Bật async batch trên production (cần diễn tập worker Linux + Redis thật).
- Diễn tập migration dữ liệu lớn, restore/downgrade đầy đủ, ma trận tải/fault MySQL 8.0.46.
- Đổi Algorithm cho người dùng (không có route/initializer production; Phase 8).
- Seed CLI (`vocab-seed`, `seed-data-ensure`, `seed_flama_template.py`) vẫn từ chối learner NOTE — là công cụ vận hành, không dùng cho learner canary.
