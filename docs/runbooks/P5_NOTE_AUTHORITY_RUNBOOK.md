# Runbook Phase 5 — phát hành R0 và chuyển toàn bộ learner sang NOTE (R1)

> Lập 2026-09-29; sửa cùng ngày: **bỏ canary**. Chủ sản phẩm quyết định chuyển mọi learner sang NOTE một lượt vì production chưa có người dùng thật (18 tài khoản, 6 learner có progress ở snapshot 2026-09-21). Nguồn: [P5 execution plan](../task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md) §1, §7. Không bước nào ở đây tự chạy trong CI.

Mọi lệnh `flask` dưới đây chạy trên VPS với quyền root, qua cùng cách `deploy.yml` chạy migration (user `flama`, thư mục release hiện tại, file env production):

```bash
flama_cli() {
  systemd-run --quiet --wait --collect --pipe \
    --property=User=flama --property=Group=flama \
    --property=WorkingDirectory=/opt/flama/current \
    --property=EnvironmentFile=/etc/flama/flama.env \
    /opt/flama/venv/bin/flask --app wsgi.py "$@"
}
```

File env production là `/etc/flama/flama.env` (dùng chung cho `flama.service`, `flama-connect.service`, `flama-study-worker.service`). Các cờ `STUDY_WIRE_V4_ENABLED`, `STUDY_NEW_LEARNER_NOTE_ENABLED`, `STUDY_PROGRESS_SHADOW_*` không nằm trong danh sách key do `deploy/sync_managed_env.py` quản lý, nên giá trị sửa tay được giữ qua các lần deploy. `STUDY_ASYNC_BATCH_ENABLED` **được** quản lý bởi GitHub variable (mặc định `0`).

## 1. Cờ theo từng bước

| Cờ | Sau R0 | Trong lúc backfill | Sau R1 |
|---|---|---|---|
| `STUDY_ASYNC_BATCH_ENABLED` | `0` | `0` | `0` (CLI từ chối enroll NOTE khi bật) |
| `STUDY_PROGRESS_SHADOW_WRITE_ENABLED` | `0` | `1` | `1` (giữ mirror cho learner nào còn LEGACY) |
| `STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED` | `0` | `1` | `0` |
| `STUDY_WIRE_V4_ENABLED` | `0` | `0` | `1` |
| `STUDY_NEW_LEARNER_NOTE_ENABLED` | `0` | `0` | `1` (tài khoản mới vào thẳng NOTE) |

Không có hàng `study_authority_enrollments` nghĩa là LEGACY, epoch 0.

## 2. Cổng trước R0 (bằng chứng trên release candidate)

1. Backend: `python scripts/run_tests.py --all --backend-only` xanh.
2. Frontend: `npm run test` và `npm run build` trong `frontend/` xanh.
3. MySQL disposable (không đụng DB cấu hình; mỗi script tự tạo và xoá DB tạm):
   - `python scripts/probe_p5_authority_schema_mysql.py` — upgrade 39→45, boot `wsgi.py` với cờ tắt, downgrade/re-upgrade rỗng, CAS/receipt/projection/rollback.
   - `python scripts/probe_p5_direct_replay_mysql.py` — direct replay + race, numeric, template topology + race, content delete/purge, overlay/first-state + race, Algorithm switch.
   - `python scripts/probe_p5_study_batch_mysql.py` — worker LEGACY/NOTE, recovery sau mất queue.
   - `python scripts/probe_p5_numeric_storage_mysql.py` — profile lưu số NOTE.
   - Chỉ khi định bật async: `python scripts/probe_p5_study_consumer.py --redis-url <redis cục bộ hoặc tunnel>`.

## 3. R0 — phát hành code

1. **Backup** (workflow deploy không tự backup DB): snapshot DB của nhà cung cấp hoặc `mysqldump --single-transaction --routines --triggers <db> | gzip > /root/flama-pre-r0-$(date -u +%Y%m%dT%H%M%SZ).sql.gz`; kiểm tra file giải nén đọc được (`zcat … | head`). Ghi lại đường dẫn và thời điểm. Không phát hành nếu chưa có backup.
2. Xác nhận `/etc/flama/flama.env` không bật `STUDY_WIRE_V4_ENABLED` và `STUDY_ASYNC_BATCH_ENABLED` (vắng mặt = `0`).
3. Merge PR `develop → master`. CI chạy test rồi `deploy.yml` (`flask db upgrade` tới head `20260925_000045`, cài service, kiểm tra `/api/health` và `:4790/healthz`). SPA do Cloudflare Pages tự build từ `master`, có thể lên trước backend vài phút.
4. Smoke (tài khoản thật, chưa enroll): đăng nhập, dashboard, mở phiên học, trả lời 1 thẻ, Browse list/detail, thống kê. Log không có mã `AUTHORITY_*`/`INCOMPLETE_*`.
5. Ghi nhận: SHA release, head migration, đường dẫn backup, kết quả smoke.

Rollback R0: deploy lại release trước theo workflow. Không downgrade schema; migrations 40–45 là additive.

## 4. R1 — chuyển toàn bộ learner sang NOTE

Làm liền một mạch trong giờ vắng. Enrollment đòi mọi Note đã học có subject Phase 4 ở trạng thái `MIRRORED_*`; production chưa từng chạy backfill nên bước 4.1 là bắt buộc.

### 4.1 Backfill shadow
1. Thêm `STUDY_PROGRESS_SHADOW_WRITE_ENABLED=1` và `STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED=1` vào `/etc/flama/flama.env`; `systemctl restart flama.service flama-connect.service`. Từ đây mọi writer LEGACY ghi mirror cùng transaction.
2. Thử khô: `flama_cli study-progress-backfill` → đọc `source_count`, `quarantined_count`, `unresolvable_count`.
3. Chạy thật: `flama_cli study-progress-backfill --apply` tới khi JSON có `"complete": true`. Nếu bị ngắt, chạy lại `flama_cli study-progress-backfill --apply --run-id <run_id>`.
4. **Dừng** nếu `quarantined_count` hoặc `unresolvable_count` khác 0: các learner đó sẽ không enroll được; ghi mẫu trong `samples` và xử lý riêng, không sửa dữ liệu bằng tay.

### 4.2 Bật v4 và enroll
1. Trong `/etc/flama/flama.env`: `STUDY_WIRE_V4_ENABLED=1`, `STUDY_NEW_LEARNER_NOTE_ENABLED=1`, `STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED=0` (giữ `SHADOW_WRITE=1`); `systemctl restart flama.service flama-connect.service`.
2. Thử khô toàn bộ, gom lỗi:
   ```bash
   for id in $(flama_cli study-authority-learners --mode LEGACY); do
     flama_cli study-authority-enrollment --user-id "$id" --mode NOTE >/dev/null || echo "DRY-RUN FAIL user=$id"
   done
   ```
3. Enroll thật:
   ```bash
   for id in $(flama_cli study-authority-learners --mode LEGACY); do
     flama_cli study-authority-enrollment --user-id "$id" --mode NOTE --apply || echo "ENROLL FAIL user=$id"
   done
   ```
4. Audit toàn bộ; mọi `BLOCK` (lệnh thoát khác 0) là hard stop:
   ```bash
   for id in $(flama_cli study-authority-learners --mode NOTE); do
     flama_cli study-authority-read-audit --user-id "$id" || echo "AUDIT BLOCK user=$id"
   done
   ```
5. `flama_cli study-authority-learners --mode LEGACY` phải rỗng (hoặc chỉ còn learner bị từ chối có lý do ở bảng 4.3).
6. Smoke lại bằng tài khoản thật: mở phiên học (phiên mới là `study-session.v4`), trả lời vài thẻ online và offline rồi reconnect, dashboard, Browse, thống kê. Đăng ký một tài khoản thử và kiểm tra nó xuất hiện trong `study-authority-learners --mode NOTE`.

### 4.3 Mã từ chối enroll

| Mã | Ý nghĩa | Xử lý |
|---|---|---|
| `INCOMPLETE_AUTHORITY_COVERAGE` | Note đã học một phần sibling, Card thiếu progress, hoặc thiếu subject (backfill chưa xong) | Kiểm tra backfill; nếu do dữ liệu, để learner đó ở LEGACY và ghi lại |
| `AUTHORITY_SUBJECT_NOT_READY` | Subject quarantined/detached/tombstoned | Để LEGACY, ghi lại |
| `CLONE_CUTOVER_PENDING` | Còn install `legacy_copy` | Chờ cutover khi boot rồi thử lại |
| `PENDING_DECK_ORDER` | Đơn mua deck đang treo | Chờ đơn hoàn tất |
| `AUTHORITY_BATCH_IN_FLIGHT` | Còn batch async đang chạy | Chờ worker xử lý xong |
| `NOTE_ENROLLMENT_DISABLED` | CLI chạy với `STUDY_WIRE_V4_ENABLED` tắt | Kiểm tra env ở bước 4.2.1 |

### 4.4 Theo dõi sau R1 (hằng ngày trong tuần đầu)
- Chạy lại vòng audit ở 4.2.4.
- Log ứng dụng: `AUTHORITY_READ_PARITY_DIVERGED`, `STALE_AUTHORITY_*`, `INCOMPLETE_AUTHORITY_*`, `ALGORITHM_IDENTITY_*`, `CONTENT_SCOPE_CHANGED` (mã cuối là xung đột đồng thời, người dùng thử lại được — chỉ đáng lo nếu lặp lại), `New learner … stays LEGACY` (tài khoản mới không vào được NOTE; enroll bằng CLI).
- MySQL: lock wait/deadlock tăng bất thường.

**Hard stop** (xem xét rollback): transition được chấp nhận mà không chiếu được về legacy, split-brain/đua epoch, decoder sai, phiên cũ commit qua epoch, mất event/receipt, source clone bị sửa, hoặc audit `BLOCK` không giải thích được.

### 4.5 Rollback một learner (NOTE → LEGACY)
```bash
flama_cli study-authority-enrollment --user-id <ID> --mode LEGACY          # dry-run
flama_cli study-authority-enrollment --user-id <ID> --mode LEGACY --apply
```
Rollback chỉ commit khi mọi state NOTE còn sống chiếu **không mất mát** về `CardProgress` (subject đã tombstone do xoá nội dung được bỏ qua an toàn). Nếu bị từ chối với `LOSSY_LEGACY_PROJECTION`, `UNPROJECTABLE_LEGACY_STATE` hoặc `ROLLBACK_ALGORITHM_NOT_LEGACY`: **không** sửa cột legacy bằng tay, giữ learner ở NOTE và sửa tiến (forward repair) hoặc khôi phục backup theo quy trình đã duyệt. Không downgrade schema, không xoá dữ liệu trong sự cố. Tắt `STUDY_PROGRESS_SHADOW_*` không đảo authority của learner NOTE. Khi rollback nhiều learner, đặt `STUDY_NEW_LEARNER_NOTE_ENABLED=0` trước để tài khoản mới không vào NOTE.

## 5. Giới hạn đã biết khi mọi learner ở NOTE
- Gói Connect/Anki kiểu cũ nhúng `cardsProgress` theo từng Card: nội dung vẫn import, còn progress trả `unsupported / NOTE_SNAPSHOT_REQUIRED`; progress phải đi qua gói snapshot.
- Seed CLI (`vocab-seed`, `seed-data-ensure`, `seed_flama_template.py`) từ chối learner NOTE — công cụ vận hành, chạy trên tài khoản LEGACY riêng nếu cần.
- Async batch vẫn tắt.

## 6. Ngoài phạm vi R0/R1 (R2 hoặc Phase sau)
- Bật async batch trên production (cần diễn tập worker Linux + Redis thật).
- Diễn tập migration dữ liệu lớn, restore/downgrade đầy đủ, ma trận tải/fault MySQL 8.0.46.
- Đổi Algorithm cho người dùng (không có route/initializer production; Phase 8).
