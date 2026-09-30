# P9-00 — Kiểm kê `card_progress` theo trace (2026-09-30)

> Nguồn: `scripts/trace_card_progress_callsites.py` ghi mọi câu SQL chạm `card_progress` khi chạy test, kèm hàm phát lệnh (frame `app/` trong cùng) và điểm vào (frame `app/` ngoài cùng). Lần chạy: module `study`, `connect_mcp`, `flashcards`, `decks`, `marketplace`, `analytics`, `admin` — 121 file, 1.365 test, 0 lỗi, SQLite in-memory; master `5709b64`. **86 hàm phát lệnh**. Đây là danh sách runtime theo yêu cầu [P9 plan §5 P9-00](./P9_EXECUTION_PLAN_2026-09-30.md#p9-00--inventory--baseline); phân loại dưới đây do đọc code từng hàm, phải xác nhận lại khi P9-03/P9-05 tách nhánh.

Chạy lại:

```powershell
.\.venv\Scripts\python.exe scripts\trace_card_progress_callsites.py --module study --module connect_mcp --module flashcards --module decks --module marketplace --module analytics --module admin --json cp_trace.json
```

Giới hạn: trace chỉ thấy đường mà test đi qua; UPDATE gắn với một hàm có thể là autoflush của đối tượng CardProgress đã sửa ở nơi khác (ghi chú "autoflush"). Không có dữ liệu production nào được đọc.

## 1. Đường NOTE — phải chuyển ở P9-04 (reader) / P9-05 (writer) / P9-05b (Connect/Anki)

| Hàm | Thao tác | Việc Phase 9 |
|---|---|---|
| `study_authority_repository.lock_study_authority_siblings` | SELECT FOR UPDATE | Validation vector sibling bằng CardProgress → thay bằng contributor/availability canonical (P9-04/05) |
| `study_authority_read_service.load_study_authority_card_reads` | SELECT | Reader NOTE xác minh projection từng thẻ → xác minh canonical (P9-04) |
| `study_authority_read_service.load_study_authority_availability_snapshot`, `note_analytics_read_repository.note_card_rows`/`subject_vector_violation`, `deck_aggregation_service.aggregate_deck_study_counts` (NOTE) | SELECT | Kiểm linkage `contributor.live_card_progress_id`/revision với CardProgress → bỏ khi evidence không còn projection (P9-04) |
| `stats_overview._canonical_future_due_day_counts`, `stats_today_future._load_canonical_scope_reads` | SELECT | Phạm vi Card lấy qua CardProgress → lấy từ subject/contributor (P9-04) |
| `browse_card_service.list_browse_cards` | SELECT | Lọc/sắp xếp theo cột CardProgress kể cả khi NOTE → theo availability (P9-04) |
| `flashcards_share_repository.get_deck_reps_for_user_in_source_scope`, `get_note_type_reps_for_user` | SELECT | Thống kê `reps` marketplace đọc CardProgress mọi mode → sau cutover sẽ đứng yên; chuyển sang review_events/state (P9-04) |
| `mcp/note_tools.get_note`, `mcp/study_tools.get_deck_stats` (NOTE) | SELECT | Theo reader canonical (P9-04) |
| `study_note_pristine_service.classify_note_authority_keys` | SELECT FOR UPDATE | "Pristine" định nghĩa bằng việc không có CardProgress → định nghĩa bằng subject/state (P9-03/05) |
| `study_authority_evidence_service.finalize_study_authority_evidence`, `_lock_current_lineage_refs` | UPDATE (autoflush) | Writer NOTE vẫn cập nhật projection → bỏ (P9-05) |
| `study_progress_lifecycle_mirror_service`: `_materialize_note_authority`, `materialize_pristine_notes_bulk`, `finalize_note_authority_reset`, `finalize_note_authority_sibling_expansion`, `finalize_note_authority_delete`, `finalize_lifecycle_mirror`, `prepare_lifecycle_mirror`, `prepare_note_authority_reset`, `_detach_removed_contributors`, `prepare/finalize_clone_rekey_mirror` | INSERT/SELECT/UPDATE | Tạo/khóa CardProgress để lấy `source_progress_id` và raw evidence → evidence profile mới (P9-03 §2, P9-05) |
| `study_progress_shadow_mirror_service`: `finalize_native_mirror`, `prepare_native_mirror`, `prepare_mirror_scopes` | INSERT/SELECT/UPDATE | Mirror projection → canonical; `map_card_progress` giữ làm hàm thuần (P9-03 phương án A) |
| `study_content_delete_service`: `discover_content_learner_ids`, `_prepare_note_sibling_removal`, `prepare_content_expansion` | SELECT | Tìm learner bị ảnh hưởng qua CardProgress → qua subject/contributor (P9-05) |
| `study_authority_enrollment_service.stage_note_authority_enrollment` | SELECT | Seed NOTE từ projection. Sau P9-05c chỉ còn tài khoản mới (không có CardProgress) → giữ, không cần port (xác minh ở P9-05) |
| `anki_sync_service._apply_progress_snapshot` | INSERT/SELECT/UPDATE | Nhánh NOTE dựng input từ CardProgress; fence `applied_local_revision` = `CardProgress.revision` (F9-06) → P9-05b |
| `connect/import_cards._migrate_cards_progress`, `get_import_note_statuses` | INSERT/SELECT/UPDATE | Connect import ghi/đọc progress → P9-05b |

## 2. Hỗn hợp — cùng hàm có nhánh LEGACY và NOTE, tách ở P9-05

| Hàm | Thao tác | Ghi chú |
|---|---|---|
| `study_service.execute_native_review_command`, `_apply_review_side_effects` | INSERT/SELECT/UPDATE | Trả lời trực tiếp REST/MCP: nhánh LEGACY ghi CardProgress trực tiếp; nhánh NOTE đi qua authority command nhưng vẫn cập nhật projection |
| `study_session_service.commit_study_session` | INSERT/SELECT/UPDATE | Commit v2/v3 (LEGACY) ghi CardProgress; v4 qua authority command |
| `study_worker_service.process_single_study_batch` | INSERT/SELECT/UPDATE | Batch async (đang tắt trên production) cả hai mode |

## 3. Chỉ LEGACY — không port; chặn bằng P9-05c (đã xong, #181), xóa ở P9-09

`study_repository`: `query_next_due_card_id`, `query_study_queue_counts`, `query_pending_learning_summary`, `query_study_card_order`, `load_card_progress_map`, `card_state_from_progress`, `apply_card_state_to_progress`; `vocabulary_repository.build_browse_deck_tree_payload` (số đếm cây LEGACY, bị ghi đè ở NOTE); `browse_card_repository.load_browse_progress`; `stats_query_repository.query_due_progress_rows`, `query_interval_days_rows`; `study_authority_enrollment_service.stage_legacy_authority_enrollment` (CLI đã khóa ở #181).

Production 30/09: 18/18 learner NOTE và không còn đường vào LEGACY, nên các hàm này chỉ còn chạy khi route là LEGACY — hiện không có learner nào như vậy.

## 4. Dọn lifecycle — xóa projection khi xóa/đặt lại nội dung (báo riêng, không tính là writer)

`deck_management_service`: `_purge_deck_subtree`, `delete_deck_subtree`, `reset_deck_progress`, `collect_learner_ids`; `flashcard_content_service`: `delete_note`, `delete_note_type`, `delete_template`, `collect_learner_ids`; `browse_card_service`: `_stage_browse_card_removal`, `delete_browse_card`, `delete_browse_cards_batch`; `study_note_template_service.stage_note_template_changes`; `mcp/note_tools.batch_delete_notes`. Còn `collect_learner_ids` dùng CardProgress để biết learner bị ảnh hưởng → cần nguồn canonical trước khi projection đứng yên (P9-05).

Autoflush (không tự đọc/ghi CardProgress, chỉ là nơi flush chạy): `flashcards_share_service.touch_note_type_install_usage`, `deck_working_tree_service.note_has_shared_release_dependents`.

## 5. Startup/schema và công cụ — xử lý ở P9-10 hoặc giữ làm công cụ đối chiếu

`startup.run_startup_maintenance`, `startup_schema.*` (F9-10: `db.create_all()` và patch cột CardProgress); `study_phase4_preflight_service`, `study_progress_backfill_service`/`study_progress_backfill_repository` (backfill P4), `study_progress_reconciliation_service`, `study_architecture_audit_service`, `study_phase9_readiness_service`, `flashcards_share_repository.get_card_progress_rows_for_cutover` (cutover clone cũ).

## 6. Việc tiếp theo

1. P9-02a: counters projection reads/writes theo entrypoint dựa trên danh sách §1–§2 (ghi khi đi vào nhánh, không trên hot path).
2. P9-03 ADR: giải quyết `source_progress_id`, raw evidence, `pristine` không dựa CardProgress, fence Connect/Anki (H-05: 15.965 ref đều có `applied_local_revision`).
3. Chạy lại trace sau mỗi bước P9-04/P9-05; gate P9-05 = không còn hàng nào ở §1–§2 trên workload profile mới.
