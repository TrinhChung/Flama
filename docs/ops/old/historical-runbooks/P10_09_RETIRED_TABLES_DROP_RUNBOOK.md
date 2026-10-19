# P10-09 — Dump rồi drop năm bảng tiến độ NOTE đã nghỉ

> Bước **phá hủy có bản sao**: migration `20261003_000050` drop `study_progress_lineage_refs`, `study_progress_availability`, `study_progress_contributors`, `study_progress_states`, `study_authority_subject_tokens` và FK + index `study_progress_history_facts.contributor_id` (giữ cột). Chủ sản phẩm duyệt 2026-10-03 ("dump rồi xóa"). Cơ sở: [kế hoạch P10](../task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md) §P10-09, [ADR P10](../architecture/phase-10-consolidated-note-progress-adr-2026-10-03.md).

**Đã thực hiện 2026-10-04:** dump `/root/backups/flama-p10-09-retired-tables-20261003T152452Z.sql.gz` (sha256 `f10031f12d487880…`, khôi phục thử trùng số dòng và checksum), backup đầy đủ `flama-pre-p10-09-20261003T152452Z.sql.gz`; migration 50 chạy với release `d747a5f`; hậu kiểm §4 đạt (dữ liệu không đổi, audit 18/18 PASS). Lần deploy đầu fail vì runner GitHub hết giờ SSH tới VPS (mạng tạm thời); chạy lại job deploy là đủ.

Helper `flama_cli` như trong [P5 runbook](./P5_NOTE_AUTHORITY_RUNBOOK.md). Mọi lệnh MySQL dưới đây chạy bằng `--defaults-file=/etc/mysql/debian.cnf` trên VPS.

## 1. Điều kiện trước

1. Release đang chạy là PR-A (P10-09, #206) hoặc mới hơn: không còn code đọc/ghi năm bảng. Deploy chạy `flask db upgrade` trong khi release cũ còn phục vụ, nên PR-A phải chạy production **trước** PR-B.
2. `study_authority_storage_profile` = `CONSOLIDATED_V1` (migration từ chối profile cũ khi năm bảng còn dòng).
3. `flama_cli study-authority-learners --mode LEGACY` rỗng; `/root/p6/audit_all.sh` 18/18 PASS.
4. Ghi lại số dòng năm bảng (SELECT-only principal, như P10-08). Ngày 2026-10-03: 16.477 lineage ref, 40.795 dòng mỗi bảng còn lại.

## 2. Dump năm bảng và kiểm

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
dump=/root/backups/flama-p10-09-retired-tables-$ts.sql.gz
mysqldump --defaults-file=/etc/mysql/debian.cnf --single-transaction --skip-triggers --set-gtid-purged=OFF flama \
  study_progress_lineage_refs study_progress_availability study_progress_contributors \
  study_progress_states study_authority_subject_tokens | gzip > "$dump"
gzip -t "$dump" && zcat "$dump" | tail -1 | grep -q 'Dump completed' && sha256sum "$dump" | tee "$dump.sha256"
```

Khôi phục thử vào DB tạm rồi so số dòng và `CHECKSUM TABLE` với nguồn; xóa DB tạm:

```bash
mysql --defaults-file=/etc/mysql/debian.cnf -e "CREATE DATABASE flama_p10_09_verify"
zcat "$dump" | mysql --defaults-file=/etc/mysql/debian.cnf flama_p10_09_verify
for t in study_progress_lineage_refs study_progress_availability study_progress_contributors study_progress_states study_authority_subject_tokens; do
  mysql --defaults-file=/etc/mysql/debian.cnf -N -e "SELECT '$t', (SELECT COUNT(*) FROM flama.$t), (SELECT COUNT(*) FROM flama_p10_09_verify.$t)"
done
mysql --defaults-file=/etc/mysql/debian.cnf -N -e "CHECKSUM TABLE flama.study_progress_contributors, flama_p10_09_verify.study_progress_contributors, flama.study_progress_states, flama_p10_09_verify.study_progress_states"
mysql --defaults-file=/etc/mysql/debian.cnf -e "DROP DATABASE flama_p10_09_verify"
```

**Dừng** nếu số dòng hoặc checksum lệch. Dump này cùng backup đầy đủ thường lệ (`/root/backups/flama-pre-p10-09-<UTC>.sql.gz`, như P10-08) là đường phục hồi duy nhất.

## 3. Drop

Merge PR-B lên `master`; deploy chạy migration 50 (vài phần mười giây trên 40.000 subject: `scripts/probe_p10_drop_mysql.py`). Migration:

- từ chối nếu profile cũ và năm bảng còn dòng; DB cài mới (năm bảng rỗng) được nâng profile lên `CONSOLIDATED_V1`;
- drop FK + index `contributor_id` của `study_progress_history_facts`, rồi năm bảng theo thứ tự con trước;
- không đổi dòng nào khác (history fact giữ `contributor_id` cũ).

## 4. Hậu kiểm

1. `SELECT version_num FROM alembic_version` = `20261003_000050`; năm bảng không còn trong `SHOW TABLES`.
2. Số dòng và dấu vân tay `study_progress_subjects`, `study_progress_history_facts`, `study_authority_command_receipts`, `review_events`, `card_progress` không đổi so với trước deploy.
3. `flask --app wsgi_audit.py study-phase9-readiness` (SELECT-only) và `/root/p6/audit_all.sh` 18/18 PASS; smoke dashboard / study / browse như P10-08.

## 5. Phục hồi

- Code: rollback về release PR-A vẫn chạy được (không dùng năm bảng).
- Dữ liệu: `zcat "$dump" | mysql ... flama` dựng lại năm bảng cùng dòng, rồi `flask db downgrade 20261003_000049` thêm lại FK. Downgrade từ chối khi năm bảng chưa được khôi phục.
