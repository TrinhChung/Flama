# P10 — Chuyển NOTE storage profile sang `CONSOLIDATED_V1`

> Bước **một chiều**: sau khi chuyển, tiến độ mỗi learner × Note nằm trên một dòng `study_progress_subjects`; `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`, `study_progress_lineage_refs` và `card_progress` đứng yên (chỉ còn bị xóa khi dọn nội dung) cho tới contraction. Không quay lại `CANONICAL_V1`. **Chỉ chạy khi chủ sản phẩm đã duyệt cửa sổ (P10-08).** Cơ sở: [ADR P10](../architecture/phase-10-consolidated-note-progress-adr-2026-10-03.md) §2.6, §6; [kế hoạch P10](../task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md).

Helper `flama_cli` như trong [P5 runbook](./P5_NOTE_AUTHORITY_RUNBOOK.md).

## 1. Điều kiện trước (ngày hôm trước)

1. Migration `20261003_000049` đã chạy trên production (expand, không đổi hành vi).
2. Release đang chạy có `CONSOLIDATED_V1` trong `SUPPORTED_STORAGE_PROFILES` và lệnh `study-consolidated-switch`, đã chạy production ít nhất một lần deploy trước khi chuyển: rollback code chỉ được về release hỗ trợ `CONSOLIDATED_V1`.
3. Rehearsal trên bản khôi phục production mới nhất `PASS`: `scripts/probe_p10_consolidated_workload_mysql.py --backup <dump.sql.gz> --mysql-binary <mysql> --output <report.json>` (switch P10 sạch blocker, reader parity không lệch, 0 SQL bảng cũ ngoài DELETE dọn `card_progress`, read audit PASS, integrity 0).
4. `flama_cli study-consolidated-switch` (không `--apply`) trả `"blockers": []` và `problems: {}`; ghi lại `subjects_with_state`, `subjects_without_state`, `states`.
5. `flask --app wsgi_audit.py study-phase9-readiness` (credential SELECT-only): `work_drain` không có lease v4 còn hạn hoặc batch chưa xong ngay trước freeze.
6. `flama_cli study-authority-read-audit --user-id <id>` PASS cho các learner hoạt động (H-01: user 1, 2, 4, 16).

## 2. Cửa sổ chuyển (khung 17–21 UTC)

```bash
# 2.1 Đóng băng ghi: dừng mọi process ghi NOTE.
systemctl stop flama flama-connect flama-study-worker

# 2.2 Backup đã kiểm tra.
f=/root/backups/flama-pre-p10-$(date -u +%Y%m%dT%H%M%SZ).sql.gz
mysqldump --defaults-file=/etc/mysql/debian.cnf --single-transaction --routines --triggers flama | gzip > "$f"
gzip -t "$f" && zcat "$f" | tail -1        # "-- Dump completed"

# 2.3 Kế hoạch lần cuối rồi chuyển (một transaction, khóa độc quyền dòng profile).
flama_cli study-consolidated-switch
flama_cli study-consolidated-switch --apply     # in switched_at_utc = T0, epoch, subjects_with_state

# 2.4 Mở lại.
systemctl start flama flama-connect flama-study-worker
```

`--apply` kiểm từng subject trước khi ghi (token/state/subject cùng generation + hash; mọi Card cùng một availability và bằng availability tính lại từ state). Nếu trả `SWITCH_BLOCKED` (`SUBJECT_EVIDENCE_*`, `LEGACY_LEARNERS`, `UNENROLLED_USERS`, `UNFINISHED_BATCHES`, `RELEASE_DOES_NOT_SUPPORT_CONSOLIDATED_V1`) hoặc lỗi: không có gì thay đổi (transaction rollback); mở lại dịch vụ và điều tra theo `sample_subject_ids` của kế hoạch.

## 3. Sau khi mở (cùng cửa sổ)

1. `flask --app wsgi_audit.py study-phase9-readiness`: `storage_profile` = `CONSOLIDATED_V1`, `projection_cutover` = `ready`.
2. `study-authority-read-audit` cho user 1, 2, 4, 16: PASS, `"storage_profile":"CONSOLIDATED_V1"`.
3. Học thử vài thẻ, mở/commit một phiên v4; dashboard, Browse, thống kê hôm nay/tương lai trả 200; nginx không có 409/500 bất thường. Lease v4 cấp trước freeze vẫn commit đúng (revision và hash được chép nguyên).
4. Một lần sync Anki của user có ref `AUTHORITY`: snapshot không đổi → `PROGRESS_UNCHANGED`.
5. Kiểm bảng cũ đứng yên (SELECT-only): `MAX(updated_at)` của `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability` không vượt T0 sau vài giờ có review thật.

## 4. Sự cố

- **Không có rollback profile.** Lỗi code: sửa tiến hoặc deploy lại release trước đó *có* hỗ trợ `CONSOLIDATED_V1`. Release cũ hơn từ chối mọi route NOTE (`STORAGE_PROFILE_UNSUPPORTED`) — fail closed, không ghi sai.
- **Dữ liệu sai:** khôi phục backup 2.2 vào DB cách ly, đối chiếu, bổ sung phần thiếu theo D9-02; không ghi đè state mới hơn. Binlog ROW 30 ngày dùng để replay sau T0 trong DB cách ly. Các bảng cũ vẫn giữ nguyên bản chụp tại T0 cho tới contraction.

## 5. Sau đó (không thuộc cửa sổ)

P10-09 contraction theo kế hoạch: gỡ nhánh `CANONICAL_V1` và công cụ P4, rồi drop bảng cũ — mỗi bước cần backup + restore proof + duyệt phạm vi riêng. `study_progress_lifecycle_events` được giữ.
