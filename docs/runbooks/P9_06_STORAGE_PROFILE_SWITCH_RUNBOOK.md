# P9-06 — Chuyển NOTE storage profile sang `CANONICAL_V1`

> Bước **một chiều**: sau khi chuyển, `card_progress` đứng yên (chỉ còn bị xóa khi dọn nội dung) và không quay lại `PROJECTION_V1`. Chỉ chạy khi chủ sản phẩm đã duyệt. Cơ sở: [ADR P9-03](../architecture/phase-9-p9-03-projection-independent-note-adr-2026-09-30.md) §2.1, §2.6, §2.9.

Helper `flama_cli` như trong [P5 runbook](./P5_NOTE_AUTHORITY_RUNBOOK.md).

## 1. Điều kiện trước (ngày hôm trước)

1. Release đang chạy đã có P9-05a..d và lệnh `study-storage-profile-switch` (`SUPPORTED_STORAGE_PROFILES` gồm `CANONICAL_V1`). Release này phải chạy production ít nhất một lần deploy trước khi chuyển: rollback code chỉ được về release hỗ trợ `CANONICAL_V1`.
2. `flama_cli study-storage-profile-switch` (không `--apply`) trả `"blockers": []`. Ghi lại `connect_refs` (bao nhiêu ref sẽ `AUTHORITY` / `NEEDS_CONFIRMATION`).
3. `flama_cli study-phase9-readiness`: `legacy_projection_writes` = `ready`; `work_drain` không có batch chưa xong.
4. `flama_cli study-authority-read-audit --user-id <id>` PASS cho mọi learner có state.
5. `STUDY_ASYNC_BATCH_ENABLED=0` (đang là 0 trên production).

## 2. Cửa sổ chuyển (khung 17–21 UTC, ít review nhất theo H-01)

```bash
# 2.1 Đóng băng ghi: dừng mọi process ghi NOTE.
systemctl stop flama flama-connect flama-study-worker

# 2.2 Backup đã kiểm tra (≈15 s).
f=/root/backups/flama-pre-p906-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
mysqldump --defaults-file=/etc/mysql/debian.cnf --single-transaction --routines --triggers flama | gzip > "$f"
gzip -t "$f" && zcat "$f" | tail -1        # "-- Dump completed"

# 2.3 Kế hoạch lần cuối rồi chuyển (một transaction, khóa độc quyền dòng profile).
flama_cli study-storage-profile-switch
flama_cli study-storage-profile-switch --apply     # in switched_at_utc = T0, epoch, connect_refs

# 2.4 Mở lại.
systemctl start flama flama-connect flama-study-worker
```

Nếu `--apply` trả `SWITCH_BLOCKED` hoặc lỗi: không có gì thay đổi (transaction rollback); mở lại dịch vụ và điều tra.

## 3. Sau khi mở (cùng cửa sổ)

1. `flama_cli study-phase9-readiness --projection-since <T0>`: `projection_cutover.card_progress_rows_written_since` = 0. Kiểm lại sau vài giờ có review thật.
2. `study-authority-read-audit` cho các learner hoạt động (H-01: user 1, 2, 4, 16): PASS, `"compared_with_projection": false`.
3. Học thử vài thẻ, mở/commit một phiên v4; nginx không có 409/500 bất thường.
4. Một lần sync Anki của user có ref `AUTHORITY`: snapshot không đổi → `PROGRESS_UNCHANGED`, không conflict giả.

## 4. Sự cố

- **Không có rollback profile.** Lỗi code: sửa tiến (forward fix) hoặc deploy lại release trước đó *có* hỗ trợ `CANONICAL_V1`. Release cũ hơn sẽ từ chối mọi route NOTE (`STORAGE_PROFILE_UNSUPPORTED`) — đúng thiết kế fail-closed, không ghi sai.
- **Dữ liệu sai:** khôi phục backup 2.2 vào DB cách ly, đối chiếu, bổ sung phần thiếu theo D9-02; không ghi đè state mới hơn. Binlog ROW 30 ngày (H-03) dùng để replay sau T0 trong DB cách ly.
- Diễn tập restore (G9-BACKUP) làm trên DB cách ly sau khi đã mở ghi.

## 5. Sau đó (không thuộc cửa sổ)

P9-01, P9-07..P9-10 theo [kế hoạch P9](../task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md) §5: retention, giảm snapshot (nếu cần), gỡ wire cũ, dọn nhánh LEGACY-only, rồi mới archive/drop `card_progress` — mỗi bước cần backup + restore proof + duyệt riêng.
