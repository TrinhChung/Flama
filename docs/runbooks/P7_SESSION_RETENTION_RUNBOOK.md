# Runbook Phase 7 — retention chi tiết phiên học

> Lập 2026-09-30; cập nhật P9-01 ngày 2026-10-02. Nguồn: [P7 execution plan](../task/decoupling/P7_EXECUTION_PLAN_2026-09-30.md), [P9 plan](../task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md). Timer trong repo chưa được cài/bật trên production. Lệnh `flama_cli` giống [runbook P5](./P5_NOTE_AUTHORITY_RUNBOOK.md), thêm `Environment=STARTUP_RUN_MAINTENANCE=0` để chạy maintenance này mà không chạy các mutator startup khác.

## 1. Lệnh làm gì

`flask study-session-retention` (mặc định **dry-run**, `--apply` mới ghi):

1. Phiên `open` đã quá `expires_at` hơn `--grace-hours` (mặc định 24 h) và không có batch chưa terminal → `status = 'expired'`. Chỉ `completed`/`failed` là batch terminal; `enqueued`, `processing`, recoverable hoặc status chưa biết đều chặn. Expire chia page và tối đa `--max-expired-sessions` (1.000) một lượt.
2. Phiên terminal (`committed`/`cancelled`/`expired`) mở và hết hạn trước `--older-than-days` (mặc định và tối thiểu **30**) → xóa membership và pin. Discovery dùng keyset page `--batch-sessions` (200); mỗi transaction khóa lại đúng một phiên và xóa tối đa `--batch-memberships` (1.000) membership cùng tối đa 1.000 pin. Phiên lớn được chia lô.
3. Mỗi lượt tối đa `--max-memberships` (10.000) membership và `--max-seconds` (60) giữa các lô. Time budget là giới hạn mềm: không hủy transaction đang chạy. `scan_complete=false`, `stop_reason` cho biết còn backlog hoặc chưa scan hết; số candidate trong report là số đã xét, không phải toàn bộ backlog. Dry-run cũng dùng page/budget. Chạy tiếp để hoàn tất; không tăng budget để che transaction chậm.
4. MySQL `GET_LOCK` trên connection riêng giữ một runner qua các lần commit; runner thứ hai bị từ chối. CLI trực tiếp và timer dùng chung khóa theo database. Chỉ các chunk đã commit tồn tại sau khi tiến trình bị ngắt; chạy lại tiếp tục từ membership còn lại. Lease/status/receipt/history giữ đúng contract.

Không bao giờ xóa: `study_sessions`, `study_session_commits` (receipt: commit lặp lại của phiên đã dọn vẫn trả receipt cũ), `review_events`, history facts, `card_progress`, state/subject/token/contributor. Không số liệu nào (dashboard, overview, streak, heatmap, khởi tạo Algorithm) đọc membership, nên số liệu trước/sau giống hệt (`tests/test_study_session_retention.py`).

## 2. Chạy

1. Chỉ chạy khi release chứa Phase 7 đang chạy (`readlink -f /opt/flama/current`).
2. **Backup** như runbook P6 §3.1 (`/root/backups/flama-pre-p7-<UTC>.sql.gz`, kiểm `-- Dump completed`). Dọn membership không hoàn tác được ngoài backup.
3. Dry-run, ghi lại kết quả:
   ```bash
   flama_cli study-session-retention
   ```
   Khi `scan_complete=true`: `expired_sessions` = số phiên đủ điều kiện expire; counts membership khớp truy vấn dưới đây sau khi trừ các phiên có batch chưa terminal. Khi budget hết, report chỉ là phần đã scan. Open session được expire trong apply có thể bắt đầu đủ điều kiện purge trong cùng lượt; dry-run không đổi status nên chưa đếm membership của chúng.
   ```sql
   SELECT COUNT(DISTINCT s.id), COUNT(c.id) FROM study_sessions s JOIN study_session_cards c ON c.session_id = s.id
    WHERE s.status IN ('committed','cancelled','expired')
      AND s.opened_at < UTC_TIMESTAMP() - INTERVAL 30 DAY AND s.expires_at < UTC_TIMESTAMP() - INTERVAL 30 DAY;
   ```
4. Ghi dấu vân tay trước (số dòng + checksum `review_events`, `card_progress`, `study_progress_states`, `study_sessions`, `study_session_commits`).
5. `flama_cli study-session-retention --apply --batch-memberships 1000 --max-memberships 10000 --max-seconds 60`. Ghi elapsed/batches/stop_reason; tiếp tục nếu `scan_complete=false`.
6. Kiểm: dấu vân tay các bảng ở bước 4 không đổi (trừ `study_sessions.status` của các phiên vừa `expired`); `study_session_cards` giảm đúng `purged_session_cards`; chạy lại `--apply` ra `expired_sessions=0`, `purged_sessions=0`; dashboard/overview một learner giống trước; `flama_cli study-architecture-audit` không có `unknown_status_sessions`.

### Kết quả lần chạy đầu 2026-09-30

| Bước | Kết quả |
|---|---|
| Release | PR #175 `1e14106`, lên 09:52:46 UTC; health 200; 0 phản hồi 5xx |
| Backup | `/root/backups/flama-pre-p7-20260930T095337Z.sql.gz` (117 MB, `-- Dump completed`) |
| Dry-run | 0 phiên `open` quá hạn; 160 phiên, 15.072 dòng membership; khớp truy vấn SQL §2.3 |
| `--apply --batch-sessions 20` | 8 lô, 4,4 s cả khởi động app; xóa 15.072 dòng membership, 0 pin |
| Dấu vân tay trước/sau | chỉ `study_session_cards` đổi (41.160 → 26.088); notes, cards, review_events, card_progress, state/subject NOTE, ref Connect, sessions (id + status), commits giống hệt |
| Chạy lại `--apply` | 0 phiên, 0 dòng |

## 3. Lịch định kỳ P9-01 (sau cutover và lần manual được duyệt)

Repo có `deploy/flama-study-retention.service` và `.timer`: 18:30 UTC mỗi ngày, jitter tối đa 10 phút, không chạy bù khi máy bật lại. Thời gian tương ứng 03:30 JST ngày hôm sau. Service có `flock` và database lease, chạy ưu tiên thấp, không chạy startup maintenance. Không bật trong deploy tự động.

Sau P9-06, backup/restore proof và lần manual đạt: cài hai unit vào `/etc/systemd/system/`, tạo marker `/etc/flama/study-retention-approved` rồi `systemctl daemon-reload` và `systemctl enable --now flama-study-retention.timer`. Không có marker thì service bỏ qua. Xem kết quả qua `journalctl -u flama-study-retention.service`; lỗi hoặc SQL/transaction quá chậm thì tắt timer, giảm batch rồi probe lại. Giới hạn lô không thay thế đo p95 <1 s trên workload nghiệm thu.

## 4. Rollback

Code: deploy lại release trước (status `expired` với release cũ: commit trả `409 SESSION_NOT_OPEN` thay vì `410`, không mất dữ liệu). Membership đã xóa chỉ khôi phục từ backup bước 2.
