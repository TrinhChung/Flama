# Runbook Phase 7 — retention chi tiết phiên học

> Lập 2026-09-30. Nguồn: [P7 execution plan](../task/decoupling/P7_EXECUTION_PLAN_2026-09-30.md). Không bước nào tự chạy trong CI hay theo lịch. Lệnh `flama_cli` giống [runbook P5](./P5_NOTE_AUTHORITY_RUNBOOK.md).

## 1. Lệnh làm gì

`flask study-session-retention` (mặc định **dry-run**, `--apply` mới ghi):

1. Phiên `open` đã quá `expires_at` hơn `--grace-hours` (mặc định 24 h) và không có batch `enqueued` → `status = 'expired'`. Commit/batch muộn của phiên đó vẫn nhận `410 SESSION_EXPIRED` như trước; `GET /api/study/sessions/<id>` vẫn trả `expired`; audit kiến trúc đếm ở `session_gates.expired_sessions`.
2. Phiên ở trạng thái cuối (`committed`/`cancelled`/`expired`) mở và hết hạn trước mốc `--older-than-days` (mặc định 30, tối thiểu 2) → xóa `study_session_cards` và pin NOTE của chúng, `--batch-sessions` phiên (mặc định 200) mỗi transaction, khóa lại và kiểm lại điều kiện trong từng lô.

Không bao giờ xóa: `study_sessions`, `study_session_commits` (receipt: commit lặp lại của phiên đã dọn vẫn trả receipt cũ), `review_events`, history facts, `card_progress`, state/subject/token/contributor. Không số liệu nào (dashboard, overview, streak, heatmap, khởi tạo Algorithm) đọc membership, nên số liệu trước/sau giống hệt (`tests/test_study_session_retention.py`).

## 2. Chạy

1. Chỉ chạy khi release chứa Phase 7 đang chạy (`readlink -f /opt/flama/current`).
2. **Backup** như runbook P6 §3.1 (`/root/backups/flama-pre-p7-<UTC>.sql.gz`, kiểm `-- Dump completed`). Dọn membership không hoàn tác được ngoài backup.
3. Dry-run, ghi lại kết quả:
   ```bash
   flama_cli study-session-retention
   ```
   Kỳ vọng: `expired_sessions` = số phiên `open` quá hạn > 24 h; `purge_candidate_sessions`/`purged_session_cards` (ở dry-run là số sẽ xóa) khớp:
   ```sql
   SELECT COUNT(DISTINCT s.id), COUNT(c.id) FROM study_sessions s JOIN study_session_cards c ON c.session_id = s.id
    WHERE s.status IN ('committed','cancelled','expired')
      AND s.opened_at < UTC_TIMESTAMP() - INTERVAL 30 DAY AND s.expires_at < UTC_TIMESTAMP() - INTERVAL 30 DAY;
   ```
4. Ghi dấu vân tay trước (số dòng + checksum `review_events`, `card_progress`, `study_progress_states`, `study_sessions`, `study_session_commits`).
5. `flama_cli study-session-retention --apply`.
6. Kiểm: dấu vân tay các bảng ở bước 4 không đổi (trừ `study_sessions.status` của các phiên vừa `expired`); `study_session_cards` giảm đúng `purged_session_cards`; chạy lại `--apply` ra `expired_sessions=0`, `purged_sessions=0`; dashboard/overview một learner giống trước; `flama_cli study-architecture-audit` không có `unknown_status_sessions`.

## 3. Lịch định kỳ (tùy chọn, cần chủ sản phẩm duyệt)

Một timer systemd hằng ngày chạy `--apply` sau khi lần chạy tay đầu tiên đạt. Chưa cài.

## 4. Rollback

Code: deploy lại release trước (status `expired` với release cũ: commit trả `409 SESSION_NOT_OPEN` thay vì `410`, không mất dữ liệu). Membership đã xóa chỉ khôi phục từ backup bước 2.
