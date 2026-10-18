# P10-08 — Production cutover sang `CONSOLIDATED_V1` (2026-10-03)

Chủ sản phẩm yêu cầu "xử lí full luôn" sau khi P10-02..07 xong. Bước switch một chiều đã chạy theo [runbook](../../runbooks/P10_CONSOLIDATED_SWITCH_RUNBOOK.md). Contraction (P10-09: gỡ code `CANONICAL_V1`, drop bảng cũ) **chưa** làm, cần duyệt phạm vi riêng.

## Release

| Release | Nội dung | Kiểm sau deploy |
|---|---|---|
| `09a34d1` (#203) | Migration 49 (expand) + toàn bộ reader/writer `CONSOLIDATED_V1` (chưa bật) | Alembic `20261003_000049`; dấu vân tay mọi bảng learner y hệt trước merge (chỉ alembic đổi); profile `CANONICAL_V1` epoch 2 |
| `d812f00` (#204) | `CONSOLIDATED_V1` vào `SUPPORTED_STORAGE_PROFILES`; `/api/study/next` không khóa cả scope | 3 service active, health 200 |

Backup trước merge #203: `/root/backups/flama-pre-p10-203-20261003T055911Z.sql.gz` (SHA-256 `04fbf7d3…010a`), cũng là bản dùng cho rehearsal.

## Trước switch

- Rehearsal trên chính bản backup đó (`probe_p10_consolidated_workload_mysql.py`): **PASS**. Kế hoạch 0 blocker/0 problem; `--apply` 40.851 subject; payload reader giống hệt giữa hai profile; read audit PASS; workload ghi 0 SQL chạm bảng cũ; integrity 0.
- Kế hoạch trên production: `blockers=[]`, `problems={}`, 40.795 state.
- Read audit: **18/18 learner PASS** (`/root/p10/pre-switch-audit.txt`).
- Readiness (principal SELECT-only): 0 learner LEGACY/chưa enroll; 4 lease v4 còn hạn, 0 batch. Lease qua switch giữ nguyên revision + hash (test `test_v4_lease_opened_before_the_switch_commits_after_it`).
- Lần ghi cuối trước cửa sổ: 2026-10-02 23:47Z (khung ít học nhất).

## Cửa sổ

- Script `/root/p10/p10_switch.sh`, log `/root/backups/p10-20261003T063808Z/window.log`.
- Freeze web, Connect, Study worker: **06:38:27Z → 06:39:34Z (67 giây)**.
- Backup trong freeze: `/root/backups/flama-pre-p10-switch-20261003T063808Z.sql.gz`, 120.830.646 byte, SHA-256 `ee77f1ffbcd8b537227003d15cf2778916d977805f4addb51cb7a3d5fa362d56`, gzip + completion marker hợp lệ, watermark **`binlog.000105` position `20243`**.
- T0 **`2026-10-03T06:38:52Z`**, `CONSOLIDATED_V1`, epoch **3**, 40.795 subject có state, 0 không state.

## Sau khi mở

- 3 service active, `/api/health` `{"status":"ok"}`.
- 40.795/40.795 dòng `study_progress_subjects` có state và availability. `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`, `card_progress` y hệt trước switch (đếm + CRC), `MAX(updated_at)` không vượt T0.
- Readiness: `storage_profile=CONSOLIDATED_V1`, `projection_cutover=ready`, `legacy_projection_writes=ready`; `work_drain=waiting` do 4 lease v4 còn hạn.
- Read audit: **18/18 learner PASS** dưới `CONSOLIDATED_V1` (`/root/p10/post-switch-audit.txt`); user 1 167 s → 128 s.
- Smoke chỉ đọc (principal SELECT-only, app không chạy startup maintenance), user 1 — 39.283 thẻ, median 3 lần:

| Màn | Sau switch |
|---|---|
| `/api/dashboard` | 1,023 s |
| `/api/statistics/overview` | 0,724 s |
| `/api/browse/decks/tree` | 0,788 s |

Trước đó (P9, production, `CANONICAL_V1`) dashboard của user 1 là 2,16 s.

## Phát hiện khi smoke và cách xử lý

Principal SELECT-only từ chối `SELECT … FOR UPDATE`, nên lộ ra hai reader GET vẫn khóa subject của cả phạm vi qua bộ đọc đầy đủ: `/api/statistics/today-future` (cả bộ sưu tập: ~39k subject của user 1) và MCP `get_deck_stats` (cả deck). Người dùng thật vẫn chạy được, nhưng chậm và giữ khóa. PR tiếp theo cho cả hai đọc thẳng `type`/`interval_days` + availability của dòng bằng một SELECT không khóa (cùng tập Card, cùng phép tính; test so khớp trước/sau switch). Cùng PR, `/vocabulary/study/deck/<id>` thôi dựng hàng đợi bằng đọc khóa cả deck chỉ để trả SPA shell: `serve_react_spa` vốn bỏ qua mọi tham số đó.

## Khôi phục

Không có rollback profile. Lỗi code: sửa tiến hoặc deploy lại release *có* hỗ trợ `CONSOLIDATED_V1` (`d812f00` trở về sau); release cũ hơn từ chối route NOTE (`STORAGE_PROFILE_UNSUPPORTED`). Dữ liệu sai: khôi phục backup trong freeze vào DB cách ly, replay binlog từ `binlog.000105:20243`, bổ sung theo D9-02. Các bảng cũ giữ nguyên bản chụp tại T0 cho tới contraction.
