# Kế hoạch thực thi Phase 7 — retention phiên học, không mất dữ liệu learner

> Lập 2026-09-30. Scope gốc: [canonical plan §15 Phase 7](../../architecture/study-interaction-trigger-algorithm-plan.md#phase-7--implement-retention-aggregation-and-replay-retirement), quyết định sản phẩm #20 (giữ chi tiết thực thi 30 ngày rồi dọn). Ràng buộc 30/09 của chủ sản phẩm: giữ hiệu năng, **không mất hoặc hỏng dữ liệu learner**.

## 1. Dữ liệu nào là "chi tiết thực thi"

Production 30/09 (SELECT-only):

| Bảng | Dòng | Vai trò | Phase 7 |
|---|---|---|---|
| `study_sessions` | 563 (430 committed, 132 cancelled, 1 open) | lease + provenance (`review_events.study_session_id` trỏ vào) | **giữ**; phiên `open` quá hạn chuyển `expired` |
| `study_session_cards` | 41.160 (15.612 thuộc phiên > 30 ngày) | snapshot membership + base state của lease | **dọn** khi phiên đã kết thúc > 30 ngày |
| `study_session_authority_pins` | 30 | pin NOTE của membership | dọn theo cascade của membership |
| `study_session_commits` | 430 | receipt idempotent của commit | giữ (nhỏ, dùng cho audit) |
| `study_session_batches` | 0 | outbox async | giữ (chỉ trạng thái cuối) |
| `review_events`, `study_progress_history_facts`, state/subject/token | — | **lịch sử và tiến độ learner** | **không bao giờ dọn** |

Mọi số thống kê (overview, dashboard, streak, heatmap) và khởi tạo Algorithm theo lịch sử đọc từ `review_events`/history facts, không đọc `study_session_cards`. Vì vậy dọn membership của phiên cũ không đổi số liệu nào và không cần bảng aggregate để "khớp số liệu trước/sau" (exit gate của canonical plan): đây là bằng chứng phải có test.

## 2. Work package

| ID | Nội dung | Output |
|---|---|---|
| P7-01 | Đóng phiên `open` đã quá `expires_at` + biên an toàn (mặc định 24 h) thành `expired`. Commit/batch của phiên hết hạn vốn đã bị từ chối (`SESSION_EXPIRED`); đổi trạng thái chỉ để không còn phiên `open` vĩnh viễn. | Service + CLI `study-session-retention` (dry-run mặc định) |
| P7-02 | Dọn `study_session_cards` (+ pin theo cascade) của phiên ở trạng thái cuối (`committed`/`cancelled`/`expired`) có `opened_at` cũ hơn 30 ngày; theo lô nhỏ (mặc định 500 phiên), từng lô một transaction, dừng/tiếp tục được, idempotent. Không đụng phiên `open`, phiên có batch `enqueued`, và mọi bảng lịch sử/tiến độ. | Cùng CLI `--apply` |
| P7-03 | Test chứng minh: số liệu overview/dashboard/lịch sử trước và sau dọn giống hệt; replay commit của phiên đã dọn trả receipt cũ (receipt giữ nguyên); phiên đang mở/đang có batch không bị đụng; chạy lại không đổi gì. | `tests/test_study_session_retention.py` |
| P7-04 | Probe MySQL: dọn theo lô trên DB tạm với phiên tổng hợp, đo thời gian khóa từng lô. | `scripts/probe_p7_session_retention_mysql.py` |
| P7-05 | Production: backup, dry-run (ghi số lượng), `--apply`, audit lại. Tùy chọn: timer systemd hằng ngày sau khi chủ sản phẩm duyệt. | Runbook |

## 3. Không làm trong Phase 7

- Không xóa `review_events`, history facts, receipt NOTE, state/subject/token, `card_progress`.
- Không xóa hàng `study_sessions` (giữ provenance cho `review_events`).
- Không bảng aggregate: không có số liệu nào đọc từ dữ liệu bị dọn.

## 4. Rollback

Dọn là xóa dữ liệu dẫn xuất của lease đã kết thúc; không có đường "hoàn tác" ngoài backup. Vì vậy mặc định dry-run, `--apply` chỉ chạy sau backup đã kiểm tra, và cột mốc 30 ngày lớn hơn lease tối đa (24 h) rất nhiều.
