# Kế hoạch thực thi P10 — gộp tiến độ NOTE về một dòng

> Lập 2026-10-03 theo yêu cầu chủ sản phẩm: tối ưu thiết kế và truy vấn trước, chưa dùng index/cache. Thiết kế: [ADR P10](../../architecture/phase-10-consolidated-note-progress-adr-2026-10-03.md). Bối cảnh đo: [tổng kết P9](./P9_CLOSEOUT_2026-10-03.md), [điều tra dashboard/study](../../architecture/LOCAL_PRODUCTION_STUDY_DASHBOARD_PERFORMANCE_2026-10-02.md).

## 1. Mục tiêu và phạm vi

Một dòng `study_progress_subjects` chứa định danh, state, revision CAS và availability của mỗi learner × Note. Mọi đọc/ghi NOTE ở profile `CONSOLIDATED_V1` không chạm `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`, `study_progress_lineage_refs` và `card_progress`.

Không thuộc P10: index/cache mới; đổi wire, receipt, ReviewEvent; đổi quyết định tiến độ chung theo Note; giao diện; Phase 8.

## 2. Đường đi

Theo cách đã chứng minh ở P9: code mới chạy song song với code cũ phía sau storage profile, chuyển production một chiều trong write freeze ngắn, rồi mới gỡ code và bảng cũ.

```text
P10-01 ADR + kế hoạch
P10-02 expand: migration 49, model, profile CONSOLIDATED_V1 (chưa bật)
P10-03 lõi: repository dòng tiến độ + chiếu availability + CAS
P10-04 reader CONSOLIDATED_V1 (+ parity với CANONICAL_V1)
P10-05 writer CONSOLIDATED_V1 (review, vòng đời, đổi thuật toán, Anki/Connect, overlay)
P10-06 gate: suite dưới CONSOLIDATED_V1 + guard bảng cũ, probe MySQL, A/B
P10-07 switch CLI + rehearsal trên bản khôi phục production + runbook
P10-08 production: deploy, backup, freeze, switch, postflight    [cần duyệt]
P10-09 contraction: gỡ code CANONICAL_V1/P4 tooling, drop bảng cũ [cần duyệt phạm vi]
```

Mỗi bước là một PR có test; P10-02..P10-07 không đổi hành vi production vì profile production vẫn là `CANONICAL_V1` cho tới P10-08.

## 3. Gói việc

### P10-02 — Expand (không đổi hành vi)

- Migration `20261003_000049`: thêm vào `study_progress_subjects` các cột ở ADR §2.1, đều NULL được (riêng `authority_revision` NOT NULL DEFAULT 0); CHECK “nhóm state/availability cùng có hoặc cùng NULL”, độ dài hash, queue chuẩn hóa. Expand thuần, chạy được khi release cũ còn phục vụ (cột mới không ai đọc).
- Model `StudyProgressSubject` thêm cột; `STORAGE_PROFILES` thêm `CONSOLIDATED_V1`; `SUPPORTED_STORAGE_PROFILES` của release chưa gồm nó (switch bị chặn bằng `RELEASE_DOES_NOT_SUPPORT_*`).
- Test: migration SQLite + MySQL (upgrade/downgrade, CHECK), model/migration parity, startup `create_all` không lệch.

### P10-03 — Lõi dòng tiến độ

- `app/repositories/note_progress_repository.py`: khóa dòng theo `(learner, logical_note_key)` hàng loạt; đọc không khóa; INSERT bulk dòng pristine; UPDATE state + revision + availability; reset generation; truy vấn tổng hợp cho analytics/hàng đợi.
- Chiếu availability theo Note: hàm thuần từ state + burial (tái dùng phần Note của `project_note_card`), cùng semantic hash như hiện tại để lease/receipt không đổi.
- `LockedStudyAuthoritySubject` ở profile mới dựng từ một dòng (state/token là view trên dòng) để pin, wire identity, receipt dùng lại không đổi.
- Test: CAS (revision/hash sai bị từ chối), non-material write bị từ chối, ràng buộc dòng, chiếu availability bằng hệt `project_note_card` trên mọi queue/suspend/bury/learning/relearning.

### P10-04 — Reader

| Entry point | File chính |
|---|---|
| Dashboard, overview, cây deck | `note_analytics_read_repository`, `deck_aggregation_service`, `stats_overview` |
| `/api/study/next`, MCP counts/queue/get_card | `study_authority_read_service`, `mcp/study_tools` |
| Browse danh sách/cây/lọc | `browse_card_service` |
| Thống kê hôm nay/tương lai | `stats_today_future` |
| Reps marketplace | `flashcards_share_repository` |
| Mở phiên (đọc state, ghim) | `study_session_authority_pin_service`, `study_session_service` |
| Audit/readiness | `cli.study-authority-read-audit`, `study_phase9_readiness_service` |

Gate: với cùng dữ liệu, hai profile trả kết quả giống hệt (test parity chuyển profile trong test). Câu đếm dashboard đọc `notes ⋈ subjects` (± `cards`), không kiểm tra chéo.

### P10-05 — Writer và vòng đời

| Entry point | File chính |
|---|---|
| Trả lời REST/MCP, commit phiên v4, batch NOTE | `study_service`, `study_authority_command_service`, `study_authority_receipt_service`, `study_session_service`, `study_note_batch_service` |
| Note mới, materialize pristine | `study_note_pristine_service`, `study_canonical_materialization_service`, `flashcard_content_service` |
| Thêm/xóa Template, xóa Card/Note/NoteType/deck, reset | `study_note_template_service`, `study_content_delete_service`, `deck_management_service`, `browse_card_service`, `mcp/note_tools` |
| Đổi thuật toán, history cut | `study_algorithm_switch_service`, `study_algorithm_history_cut_service` |
| Anki/Connect snapshot, revlog, import | `anki_sync_service`, `connect/import_cards` |
| Overlay, clone rekey | `flashcards_share_service`, `flashcards_share_repository` |
| Enrollment | `study_authority_enrollment_service` |

Gate: writer matrix ở ADR §5.3; mỗi câu trả lời một UPDATE tiến độ; history fact khớp theo `logical_card_key` + generation.

### P10-06 — Gate tích hợp

- `scripts/trace_card_progress_callsites.py --profile CONSOLIDATED_V1` mở rộng theo dõi bốn bảng cũ: không SQL nào ngoài DELETE dọn dẹp đã khai báo; lỗi còn lại chỉ thuộc test khẳng định nội tạng bảng cũ, liệt kê từng test.
- Probe MySQL đồng thời/replay/batch trên profile mới; `bench_p9_storage_profile_ab_mysql.py` thêm profile mới; workload probe trên bản khôi phục production.
- Mục tiêu đo (cùng máy, so với `CANONICAL_V1`): commit 50 câu ≤ 60% SQL và ≤ 60% dòng ghi; câu đếm dashboard user 1 ≤ 0,5 s trên dữ liệu production khôi phục; mở phiên không xấu đi.

### P10-07 — Switch

- `flask study-consolidated-switch` (dry-run mặc định, `--apply` để chuyển): blocker (batch chưa xong, learner không NOTE, release chưa hỗ trợ), một UPDATE JOIN chép state/token/availability/contributor sang dòng subject, kiểm đối chiếu 100% (đếm, hash, revision, availability tính lại từ state), tăng epoch, khóa độc quyền dòng profile.
- Rehearsal trên `pre-p906` dump khôi phục (sau switch P9-06 rồi switch P10), workload probe, read audit hai learner, lease v4 qua switch.
- Runbook `P10_CONSOLIDATED_SWITCH_RUNBOOK.md`.

### P10-08 — Production (cần chủ sản phẩm duyệt cửa sổ)

Deploy release hỗ trợ hai profile → backup có watermark → freeze → switch → mở lại → readiness, read audit, SQL trace, postflight như P9-06.

### P10-09 — Contraction (cần duyệt phạm vi)

Gỡ nhánh `CANONICAL_V1`, công cụ P4 (mirror, backfill, reconciliation), đổi profile mặc định của test, migration drop bốn bảng + lineage ref + bảng backfill sau archive, bỏ cột envelope cũ. `study_progress_lifecycle_events` được giữ (history cut đọc nó). Gỡ `card_progress`, LEGACY, `PROJECTION_V1` là quyết định riêng (phạm vi compatibility đã giữ ở P9).

Chủ sản phẩm duyệt 2026-10-03: dump rồi drop năm bảng `study_progress_states`, `study_authority_subject_tokens`, `study_progress_contributors`, `study_progress_availability`, `study_progress_lineage_refs`. `card_progress`/LEGACY giữ nguyên. Chia hai PR:

- **PR-A — gỡ code, không đổi schema.** Release chỉ phục vụ `CONSOLIDATED_V1` (`SUPPORTED_STORAGE_PROFILES = {CONSOLIDATED_V1}`; DB không có dòng profile = cài mới `CONSOLIDATED_V1`; DB còn `PROJECTION_V1`/`CANONICAL_V1` bị từ chối `STORAGE_PROFILE_UNSUPPORTED`). Không còn code đọc/ghi năm bảng. Hệ quả:
  - Learner LEGACY: tiến độ chỉ ở `card_progress`; không còn shadow mirror, history fact hay lifecycle event cho LEGACY.
  - Enroll NOTE từ chối learner còn `card_progress` (`LEGACY_PROGRESS_NOT_MIGRATABLE`); learner mới/chưa học enroll bình thường. Rollback NOTE → LEGACY bị gỡ (`LEGACY_ROLLBACK_RETIRED`).
  - Gỡ CLI `study-architecture-audit`, `study-progress-backfill`, `study-storage-profile-switch`, `study-consolidated-switch`; giữ `study-authority-learners`, `study-authority-read-audit`, `study-phase9-readiness` (postflight `/root/p6/audit_all.sh` chỉ dùng hai lệnh đầu).
  - Read audit không còn so thứ tự với SQL `card_progress` (chỉ có ý nghĩa ở `PROJECTION_V1`); vẫn kiểm từng dòng (availability dựng lại từ state).
  - `card_progress` đông cứng của learner NOTE không phải bằng chứng: xóa nội dung không bị chặn bởi nó (giống `CONSOLIDATED_V1` trên production từ P10-08).
  - Probe CI cập nhật: `probe_p5_concurrency_mysql` (revision trên dòng, mỗi câu trả lời đúng một history fact), `probe_p5_direct_replay_mysql`, `probe_p5_study_batch_mysql`, `probe_p9_backup_restore_mysql`; helper chung `scripts/mysql_probe_db.py`.
- **PR-B — dump + migration 50.** Dump năm bảng trên production (kiểm sha256 + khôi phục thử), migration 50 drop năm bảng và FK + index `study_progress_history_facts.contributor_id` (giữ cột), gỡ năm model. Migration 39/40 dựng bảng từ model nên định nghĩa được đông cứng ở `migrations/retired_note_progress_tables.py` (MetaData riêng, DDL MySQL/SQLite trùng khớp model cũ); chuỗi migration mới trên MySQL đi qua 39 → 50. Chuỗi mới luôn seed `PROJECTION_V1` (migration 47) với năm bảng rỗng: migration 50 nâng profile lên `CONSOLIDATED_V1` cho DB như vậy, còn từ chối khi profile cũ mà năm bảng có dòng. Probe `scripts/probe_p10_drop_mysql.py` (CI); bench migration 47 dựng bảng contributor đông cứng. [Runbook](../../runbooks/P10_09_RETIRED_TABLES_DROP_RUNBOOK.md).

## 4. Ước lượng và rủi ro

| Bước | Ước lượng tập trung |
|---|---|
| P10-02 | 0,5 ngày |
| P10-03 | 1–2 ngày |
| P10-04 | 2–3 ngày |
| P10-05 | 4–6 ngày |
| P10-06, P10-07 | 2–3 ngày |
| P10-09 | 3–5 ngày |

Rủi ro chính: số entry point lớn trong các file rủi ro cao (`study_session_service`, `flashcards_share_service`, lifecycle). Giảm bằng: code profile mới nằm ở module riêng, nhánh tại entry point; test parity hai profile; guard SQL trên toàn suite; rehearsal trên dữ liệu production thật trước switch.

## 5. Trạng thái

| ID | Trạng thái |
|---|---|
| P10-01 | DONE — ADR + kế hoạch |
| P10-02 | DONE — migration 49, model, profile (commit `6981312`) |
| P10-03 | DONE — view dòng (`ConsolidatedSubjectToken/State`), `project_note_state`, `study_consolidated_progress_service` |
| P10-04 | DONE — dashboard, overview, cây deck, `/api/study/next`, Browse, hôm nay/tương lai, reps marketplace, MCP, read audit |
| P10-05 | DONE — trả lời REST/MCP, phiên v4, batch async, Note mới/enrollment, Template thêm/xóa, reset, xóa Note/deck, đổi thuật toán, Anki/Connect + note-status, overlay |
| P10-06 | DONE — test SQLite có guard bảng cũ (`tests/test_study_consolidated_*`), A/B MySQL, workload probe trên bản khôi phục (§6) |
| P10-07 | DONE — CLI `study-consolidated-switch` + test, rehearsal trên bản khôi phục (§6), [runbook](../../runbooks/P10_CONSOLIDATED_SWITCH_RUNBOOK.md); release `d812f00` (#204) hỗ trợ `CONSOLIDATED_V1` |
| P10-08 | DONE — production 2026-10-03, T0 `06:38:52Z`, epoch 3, freeze 67 s, 18/18 audit PASS trước/sau ([báo cáo](./P10_08_CUTOVER_REPORT_2026-10-03.md)) |
| P10-09 | IN PROGRESS — duyệt 2026-10-03 (dump rồi drop năm bảng). PR-A (gỡ code): suite 1616 test xanh local, 10 probe MySQL CI PASS. PR-B (dump + migration 50): TODO |

Đo sơ bộ (SQLite, một câu trả lời REST dưới `CONSOLIDATED_V1`): 46 SQL, trong đó ghi đúng 1 UPDATE tiến độ + 4 INSERT (ReviewEvent, history fact, receipt, audit). 40 SELECT còn lại là đọc lặp ở route và phần xem trước thẻ kế (`cards` ×7, `decks` ×6, `study_progress_subjects` ×6, `users` ×5, enrollment/profile/scheduler settings ×3). Gom các đọc này là hạng mục tối ưu truy vấn tiếp theo, không thuộc gộp bảng.

Ghi chú gate trace: `--profile CONSOLIDATED_V1` ép profile mà không chạy switch, nên các test tự dựng `StudyAuthorityRoute`, ghi thẳng bảng cũ hoặc khẳng định nội tạng bảng cũ vẫn lỗi/được liệt kê (LEGACY, shadow mirror, backfill, reconciliation, startup DDL). Gate thực cho từng writer/reader là các test chạy switch thật và bắt mọi SQL chạm bảng cũ.

## 6. Bằng chứng gate (2026-10-03, MySQL 8 local)

**Rehearsal trên bản khôi phục production** (`pre-p906.sql.gz`, `scripts/probe_p10_consolidated_workload_mysql.py`, máy rảnh): migration 49 1,4 s; switch P9-06 rồi P10: kế hoạch 0 blocker/0 problem (12,9 s), `--apply` 40.849 subject trong 48,5 s; reader của user 1 (owned, 39.283 thẻ) và user 4 (installed) trả **payload giống hệt** giữa hai profile (trừ `move_alias` sinh từ token có dấu thời gian); read audit PASS cả hai; workload ghi (commit v4, REST, MCP, Note mới, reset deck) **0 SQL chạm bảng cũ**; integrity 0. Status `PASS`.

| Reader (median, s) | CANONICAL_V1 | CONSOLIDATED_V1 |
|---|---|---|
| user 1 dashboard | 4,605 | 1,632 (−65%) |
| user 1 overview | 3,022 | 1,870 (−38%) |
| user 1 cây Browse | 3,507 | 1,494 (−57%) |
| user 4 dashboard | 0,714 | 0,468 (−34%) |
| user 4 cây Browse | 0,805 | 0,578 (−28%) |

**A/B** (`bench_p9_storage_profile_ab_mysql.py --notes 2000 --runs 3 --overlay 200`, median):

| Bước | CANONICAL_V1 s / SQL / dòng ghi | CONSOLIDATED_V1 s / SQL / dòng ghi |
|---|---|---|
| commit 50 câu | 1,666 / 928 / 503 | 1,003 / 424 / 203 |
| overlay commit 50 | 1,433 / 999 / 508 | 0,788 / 495 / 208 |
| 20 câu REST | 30,8 / 1.780 / 220 | 21,0 / 1.200 / 100 |
| mở phiên lần đầu | 3,173 / 51 | 2,974 / 39 |
| dashboard | 0,131 / 17 | 0,069 / 16 |
| overview | 0,120 / 11 | 0,048 / 10 |
| `/api/study/next` | 1,494 / 48 | 0,977 / 34 |

Mục tiêu §P10-06 đạt: commit 50 câu còn 46% SQL và 40% dòng ghi. Switch 2.000 subject ≈ 2,4 s.

Bench đo đúng đường hôm nay/tương lai (`scope=collection`) lộ một N+1 có từ trước: 6.617 SQL / 9,1 s cho 2.000 Note (deck options và Note nạp theo từng Card). Đã sửa (Note nạp cùng Card, deck options một lần mỗi deck): CANONICAL_V1 32 SQL / 1,44 s, CONSOLIDATED_V1 18 SQL / 0,92 s.

Việc tối ưu truy vấn còn lại (không thuộc gộp bảng): `/api/study/next` và câu trả lời REST tính lại hàng đợi cả scope bằng Python (~1 s cho 2.000 thẻ một deck); đọc lặp trong route trả lời (§5).

