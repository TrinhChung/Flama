# Vì sao Analytics counts chưa được bật trên production

> Ngày: 2026-10-13 | Kiểm tra VPS: 20:21 JST | Mode: INVESTIGATE
> Release: `fb685882099d20d90479d234402ae3b098076f89` | Migration: `20261012_000062`
> Bằng chứng mới: [inventory đã lọc credentials](artifacts/analytics_counts_production_enablement_20261013.json)

## Kết luận

Code và sáu bảng count đã có trên production, nhưng phần kích hoạt vận hành chưa được thực hiện: cả hai writer dùng mặc định tắt, readers dùng raw, chưa có generation/snapshot và service/timer prewarm chưa được cài.

Lý do giữ tắt được ghi rõ trong báo cáo ngày 6/10 và nhắc lại ngày 10/10: benchmark local bật **cả history writer và deck invalidation** làm median một native review tăng từ **27,76 ms lên 49,60 ms**, thêm **21,84 ms / 78,7%**. Đây là kết quả LEGACY cũ; gate đề xuất là added commit **p95 ≤5 ms và ≤10%**. Median cũ không chứng minh p95 trên NOTE production hiện tại, cũng không xác định chi phí riêng của từng writer.

Pipeline hiện tại không tự rollout counts: không quản lý các biến `DECK_COUNT_*` / `REVIEW_ANALYTICS_*`, không cài timer, không chạy backfill/prewarm. Deploy thêm code hoặc chỉ đặt GitHub Environment variables sẽ không đủ với pipeline này.

## Nguồn dữ liệu và đường đọc

| Nguồn | Vai trò | Code |
|---|---|---|
| `review_events` | History gốc | `models/review_event.py` |
| `study_progress_subjects` | Progress canonical | `models/study_progress_subject.py` |
| `review_analytics_heads`, `review_analytics_generations`, `daily_review_counts` | History projection có verification | `models/review_analytics.py` |
| `deck_count_content_revisions`, `deck_count_learner_revisions`, `deck_study_count_snapshots` | Revision và snapshot count dẫn xuất | `models/deck_count_snapshot.py` |

Web, Connect và Study worker đọc `/etc/flama/flama.env`; release `.env` cũng không có flags count. `app/settings.py:151` đặt writers mặc định false và read modes raw. Dashboard resolver trả toàn bộ deck về raw tại `app/services/deck_count_snapshot_service.py:135`. History façade dùng raw tại `app/repositories/review_analytics_read_repository.py:106`. GET không tạo hoặc sửa derived counts.

## Findings

### F1 — Giữ raw/off là quyết định được ghi nhận do write overhead

- **Observed:** [Báo cáo 6/10](../reports/ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md#L36) ghi benchmark LEGACY và quyết định chưa rollout rộng. [Báo cáo 10/10](../reports/LEGACY_PERFORMANCE_IMPLEMENTATION_2026-10-10.md#L14) tiếp tục ghi L4 raw/off.
- **Evidence:** `docs/reports/analytics-counts-2026-10-06/deck-mysql-contract.json`; [gate đề xuất](ANALYTICS_COUNT_TABLE_DESIGN_2026-10-05.md#L420).
- **Potential concern:** Dùng benchmark LEGACY cũ để kết luận chi phí NOTE hiện tại, hoặc quy toàn bộ overhead cho deck snapshot, sẽ vượt quá bằng chứng.
- **Impact:** Lợi ích đọc đã được đo local nhưng điều kiện về chi phí ghi chưa được chứng minh cho rollout hiện tại.
- **Unknowns:** Không tìm thấy report canary production mới chứng minh write p95 đạt gate sau retirement. Probe đã được đổi sang NOTE trong commit `95eb1c5f`; code probe và correctness qualification không thay thế số đo production.

### F2 — Production chưa đặt biến bật count

- **Observed:** Hai environment files và initial environment của ba main process không có các flags count. Defaults trong source release là false/raw; allowlists cũng chưa được đặt.
- **Evidence:** Artifact mới, các mục `environment_files`, `services`, `deployed_count_config_source`; `app/settings.py:151`.
- **Potential concern:** `STUDY_NOTE_COUNT_ENABLED=1` dễ bị hiểu nhầm là đã bật count cache. Biến này chọn đơn vị đếm Note; writer/read mode của cache là nhóm biến riêng.
- **Impact:** Dashboard và history vẫn chạy raw aggregates. Chỉ đổi read mode sang summary trong khi writer tắt vẫn fallback raw.
- **Unknowns:** `/proc/<pid>/environ` phản ánh environment ban đầu, không phải inspection trực tiếp Flask config trong worker. Kết luận kết hợp environment files, source defaults và [audit effective config trước đó cùng ngày](DASHBOARD_PRODUCTION_PERFORMANCE_INVESTIGATION_2026-10-13.md).

### F3 — Pipeline không quản lý flags hoặc cài prewarm job

- **Observed:** `deploy/sync_managed_env.py:29` không liệt kê các biến count. `.github/workflows/deploy.yml:403` chỉ cài Web, Connect và Study worker. Trên VPS, cả `flama-analytics-counts.service` và `.timer` có `LoadState=not-found`.
- **Evidence:** Kiểm tra cả workflow/helper trong release đang deploy và source local; các mục `deployed_managed_env_count_keys`, `deployed_workflow_count_references_present`, `services` trong artifact.
- **Potential concern:** Thêm GitHub variables hoặc deploy lại vẫn không truyền flags và không cài timer. Đây là phần rollout tùy chọn trong [runbook](../runbooks/ANALYTICS_COUNTS_RUNBOOK.md#L19), chưa được tích hợp pipeline.
- **Impact:** Không có job prewarm tạo mới snapshot thiếu/dirty hoặc làm ấm lại sau study-day boundary.
- **Unknowns:** Không suy đoán người chịu trách nhiệm hoặc nguyên nhân tổ chức khiến rollout chưa tiếp tục. Helper giữ nguyên keys không được quản lý tại `deploy/sync_managed_env.py:289`; không có bằng chứng nó đã xóa flags count từng tồn tại.

### F4 — Schema đã migrate, dữ liệu count chưa có

- **Observed:** Migration production là `20261012_000062`. Cả sáu bảng count đọc thành công và mỗi bảng có **0 row**. Source code count và hai unit files mẫu đều có trong release.
- **Evidence:** Các mục `database`, `release_has_count_files` trong artifact; kiểm tra trong transaction MySQL read-only.
- **Potential concern:** Có schema không đồng nghĩa projection đã được xây dựng và kiểm chứng.
- **Impact:** Không có READY history generation hoặc deck snapshot để summary reader sử dụng. Đây chưa phải trạng thái đã rollout thành công rồi reader tự tắt vì drift.
- **Unknowns:** Row count hiện tại không chứng minh toàn bộ lịch sử vận hành chưa từng chạy job hoặc chưa từng bị cleanup. Không audit lịch sử mọi thay đổi DB.

### F5 — NOTE retirement và rollout count là hai việc riêng

- **Observed:** Storage profile production là `CONSOLIDATED_V1`; 32 enrollment rows đều `NOTE`; `STUDY_NOTE_COUNT_ENABLED=1`. Count projections vẫn trống và writer flags vẫn thiếu.
- **Evidence:** Artifact mới; [retirement cutover report](../plans/completed/LEGACY_RETIREMENT_CUTOVER_REPORT_2026-10-12.md); reader/writer gates độc lập trong code.
- **Potential concern:** Không thể suy ra chuyển sang NOTE sẽ tự bật summary hoặc bỏ raw aggregation.
- **Impact:** Cần qualification/rollout count riêng trên runtime NOTE hiện tại.
- **Unknowns:** Chưa đo write overhead riêng history-only, deck-only và cả hai trên workload production đại diện.

## Điều kiện còn thiếu để kích hoạt

Đây là các bước đã có trong [runbook](../runbooks/ANALYTICS_COUNTS_RUNBOOK.md), chưa thực hiện trong cuộc điều tra:

1. Đo lại latency/contended writes của NOTE; tách history và deck phases để biết nguồn overhead, kiểm tra invalidation coverage của release đang deploy.
2. Đặt writer flags nhất quán trên Web, Connect, Study worker và các writer khác, giữ readers raw.
3. History: backfill và reconcile/verification. Deck: establish coverage epoch, prewarm và parity. Không chỉ bật read mode.
4. Canary readers có giới hạn; theo dõi correctness và read/write latency trước mở rộng. Cài timer prewarm với configured learner allowlist nếu rollout Phase B.

History rollup không thay trực tiếp phần future-due của heatmap; deck snapshot hiện giới hạn owned eligible scope. Vì vậy kích hoạt không đồng nghĩa mọi truy vấn Dashboard/overview sẽ biến mất.

## Phạm vi và validation

- Chỉ đọc VPS: release/source, whitelist environment, systemd metadata và MySQL SELECT trong read-only transaction.
- Không gọi serving app factory, không ghi DB/config, không restart hoặc bật service.
- Chỉ thêm báo cáo và JSON evidence local; không sửa application behavior hoặc các thay đổi có sẵn của workspace.
- Validate JSON, paths/link targets và whitespace của hai file mới. Không chạy suite ứng dụng vì không có thay đổi behavior.
