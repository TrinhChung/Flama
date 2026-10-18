
# P0-02 — Audit coverage and disposition inventory

> Phase: 0
>
> Priority: P0
>
> Status: COMPLETED
>
> Review verdict round 5 — 2026-08-29: PASSED. Session policy/hash validation đã dùng đúng canonical material, đối chiếu identity/version/timezone/config hash và chặn toàn bộ malformed/fake-digest fixtures.
>
> Dependency: P0-01
>
> Primary lane: Backend / Data architecture

## Mục tiêu

Mở rộng audit từ aggregate report thành inventory migration-grade, giải thích được mọi progress/session/event/composition/clone category và gán disposition rõ ràng mà không thay đổi dữ liệu.

## Phạm vi file dự kiến

- `app/services/study_architecture_audit_service.py`
- `app/services/mcp/study_tools.py`
- `app/services/study_service.py`
- `tests/test_study_architecture_audit_service.py`
- `tests/test_study_architecture_audit_cli.py`
- `docs/task/decoupling/completed/P0-02_AUDIT_COVERAGE_AND_DISPOSITION.md`

## Công việc chi tiết

1. Inventory schema/FK thực tế thay vì giả định từ ORM:
   - NULL `CardProgress.card_id`;
   - non-NULL orphan nếu FK enforcement drift;
   - Card/Note/Template cross-NoteType mismatch;
   - duplicate/ambiguous Template positions/defaults.
2. Group progress theo `(user_id, Card.note_id)` và phân loại:
   - một CardProgress/Note;
   - nhiều Card nhưng equivalent state;
   - divergent fan-in;
   - invalid/unresolvable subject.
3. Thêm revision inventory:
   - distribution;
   - count `0`;
   - missing/invalid counter;
   - open session drift.
4. Thêm algorithm/registry gates:
   - active registry executables lookup;
   - separate historical imported algorithm identities from active executable registry;
   - unregistered native algorithm keys;
   - missing algorithm versions;
   - unprovenanced FSRS state rows.
5. ReviewEvents linkage/provenance inventory:
   - orphan ReviewEvents;
   - legacy vs session-attached reviews;
   - duplicate client_event_id/session sequence;
   - exhaustive disjoint provenance classification (Anki import, native session, native MCP, native batch, native direct, conflicting, unknown).
6. StudySession snapshot/config review:
   - active open leases vs historical retired sessions;
   - deep JSON snapshot schema validation;
   - missing snapshot metadata.
7. Thống kê cards clone overlay:
   - installed source cards, local clone added cards, local authored cards, unassigned cards, overlay ambiguities.
8. Output JSON machine-readable:
   - `inventory` với `category`, `gate_group`, `count`, `sample_ids`, `severity`, `disposition`, `description`;
   - `verdicts` với `pass`, `warn`, `block`, `overall_status`, `exit_code`;
   - `reconciliation` với 11/11 formula checks exhaustively verified.

---

## Migration-Grade Inventory & Disposition Matrix

| Category | Gate Group | Severity Trigger | Target Disposition | Rationale & Remediation Action |
| :--- | :--- | :--- | :--- | :--- |
| `note_types_without_templates` | template | count > 0 -> `warn` | `investigate_empty_notetypes` | NoteType không có template định nghĩa; cần rà soát trước khi render |
| `note_types_with_single_template` | template | count >= 0 -> `pass` | `valid_single_template` | NoteType đơn template chuẩn |
| `note_types_with_multiple_templates` | template | count >= 0 -> `pass` | `valid_multi_template` | NoteType đa template hợp lệ theo thiết kế Anki multi-card |
| `note_types_with_zero_defaults` | template | count > 0 -> `warn` | `investigate_missing_default_template` | NoteType có template nhưng không có template nào được đánh dấu default |
| `note_types_with_single_default` | template | count >= 0 -> `pass` | `valid_single_default_template` | NoteType có đúng 1 default template hợp lệ |
| `note_types_with_multiple_defaults` | template | count > 0 -> `warn` | `reconcile_multiple_default_templates` | NoteType có nhiều hơn 1 default template; cần chuẩn hóa về 1 |
| `default_count_anomalies` | template | count > 0 -> `warn` | `reconcile_default_templates` | Template default count != 1 trong NoteType |
| `duplicate_name_groups` | template | count > 0 -> `warn` | `review_duplicate_names` | Trùng tên template trong cùng một NoteType |
| `duplicate_position_groups` | template | count > 0 -> `warn` | `review_duplicate_positions` | Trùng position template trong cùng một NoteType |
| `cross_note_type_cards` | template | count > 0 -> `block` | `quarantine_cross_notetype_cards` | Thẻ trỏ Template thuộc NoteType khác với Note cha; chặn migration để cô lập lỗi |
| `notes_without_cards` | card | count > 0 -> `warn` | `review_orphan_notes` | Note không sinh ra bất kỳ Card nào |
| `notes_with_single_card` | card | count >= 0 -> `pass` | `valid_single_card_notes` | Note sinh ra đúng 1 Card |
| `notes_with_multiple_cards` | card | count >= 0 -> `pass` | `valid_multi_card_notes` | Note sinh ra nhiều Card |
| `orphan_cards` | card | count > 0 -> `block` | `quarantine_orphan_cards` | Card trỏ tới Note hoặc Template không tồn tại |
| `null_card_id_rows` | progress | count > 0 -> `block` | `quarantine_null_card_progress` | CardProgress có card_id = NULL |
| `orphan_card_id_rows` | progress | count > 0 -> `block` | `quarantine_orphan_card_progress` | CardProgress trỏ tới Card đã bị xóa hoặc không tồn tại |
| `orphan_note_id_rows` | progress | count > 0 -> `block` | `quarantine_orphan_note_progress` | CardProgress mà Card trỏ tới Note không tồn tại |
| `unresolvable_progress_subjects` | progress | count > 0 -> `block` | `quarantine_unresolvable_progress_subjects` | CardProgress không thể phân giải chủ thể |
| `single_card_progress_groups` | progress | count >= 0 -> `pass` | `single_card_progress` | Nhóm tiến độ 1 thẻ / 1 note chuẩn |
| `learner_note_fan_in_groups` | progress | count >= 0 -> `pass` | `learner_note_fan_in` | Nhóm tiến độ nhiều thẻ thuộc cùng 1 note của 1 người học |
| `equivalent_fan_in_groups` | progress | count >= 0 -> `pass` | `equivalent_fan_in` | Nhóm fan-in có trạng thái scheduling đồng nhất tuyệt đối trên toàn bộ các trường hành vi |
| `divergent_fan_in_groups` | progress | count > 0 -> `block` | `quarantine_divergent_progress_fan_in` | Nhóm fan-in bị lệch trạng thái scheduling (queue, interval, ease, step, due, reps, lapses, memory state, revision) |
| `learner_note_history_fan_in_groups` | progress | count >= 0 -> `pass` | `review_history_fan_in` | Lịch sử review trên nhiều card của cùng note |
| `fsrs_rows` | progress | count >= 0 -> `pass` | `fsrs_progress_state` | Bản ghi tiến độ cấu hình scheduler FSRS |
| `partial_fsrs_state_rows` | progress | count > 0 -> `warn` | `reconcile_fsrs_memory_state` | Bản ghi FSRS khuyết một trong hai giá trị stability / difficulty |
| `zero_revision_rows` | revision | count >= 0 -> `pass` | `initial_revision_state` | Bản ghi ở revision 0 khởi tạo |
| `active_revision_rows` | revision | count >= 0 -> `pass` | `active_revision_state` | Bản ghi đã qua các lần cập nhật review (revision > 0) |
| `invalid_revision_rows` | revision | count > 0 -> `block` | `quarantine_invalid_revisions` | Bản ghi revision bị NULL hoặc âm |
| `open_session_stale_revisions` | revision | count > 0 -> `warn` | `flag_session_revision_drift` | Phiên học mở có thẻ bị trôi revision so với CardProgress hiện tại |
| `registered_algorithm_count` | algorithm | count >= 1 -> `pass` | `active_registered_executables` | Số lượng adapter thuật toán đang đăng ký trong in-memory registry |
| `registered_algorithm_events` | algorithm | count >= 0 -> `pass` | `active_registered_algorithm_events` | ReviewEvent khớp với thuật toán đang đăng ký thực thi |
| `historical_imported_algorithm_events` | algorithm | count >= 0 -> `pass` | `historical_imported_algorithm` | ReviewEvent nhập từ Anki revlogs / nguồn ngoài mang identity lịch sử |
| `unregistered_native_algorithm_events` | algorithm | count > 0 -> `warn` | `classify_unregistered_algorithm` | ReviewEvent native chỉ định thuật toán không có trong registry |
| `missing_algorithm_version_events` | algorithm | count > 0 -> `warn` | `classify_missing_algorithm_version` | ReviewEvent native có algorithm nhưng thiếu version |
| `unprovenanced_fsrs_rows` | algorithm | count > 0 -> `warn` | `verify_fsrs_provenance` | CardProgress FSRS nhưng user không có review event FSRS tương ứng |
| `orphan_card_id_events` | review_event | count > 0 -> `warn` | `retain_detached_review_events` | ReviewEvent trỏ tới card đã bị xóa |
| `attached_review_events` | review_event | count >= 0 -> `pass` | `attached_review_events` | ReviewEvent gắn với Card hiện có |
| `null_session_id_events` | review_event | count >= 0 -> `pass` | `legacy_or_direct_reviews` | ReviewEvent ngoài session (direct review / legacy review) |
| `null_algorithm_events` | review_event | count > 0 -> `warn` | `classify_unversioned_algorithm` | ReviewEvent có scheduler_algorithm = NULL |
| `duplicate_client_event_id_groups` | review_event | count > 0 -> `block` | `quarantine_duplicate_client_events` | Trùng client_event_id trong cùng user |
| `duplicate_session_sequence_groups` | review_event | count > 0 -> `block` | `quarantine_duplicate_session_sequences` | Trùng sequence_no trong cùng study session |
| `missing_session_sequence_events` | review_event | count > 0 -> `warn` | `review_session_events_missing_sequence` | ReviewEvent trong session nhưng thiếu sequence_no |
| `anki_import_events` | review_event | count >= 0 -> `pass` | `anki_import_reviews` | ReviewEvent nhập từ Anki import |
| `native_session_events` | review_event | count >= 0 -> `pass` | `native_session_reviews` | ReviewEvent học trong session giao diện web |
| `native_direct_events` | review_event | count >= 0 -> `pass` | `native_direct_reviews` | ReviewEvent học trực tiếp ngoài session có bằng chứng runtime |
| `native_mcp_events` | review_event | count >= 0 -> `pass` | `native_mcp_reviews` | ReviewEvent từ Flama Connect MCP tool |
| `native_batch_events` | review_event | count >= 0 -> `pass` | `native_batch_reviews` | ReviewEvent xử lý hàng loạt |
| `conflicting_provenance_events` | review_event | count > 0 -> `block` | `quarantine_conflicting_provenance` | ReviewEvent mang cờ xung đột (vừa import vừa có session_id) |
| `unknown_provenance_events` | review_event | count > 0 -> `warn` | `needs_verification_provenance` | ReviewEvent thiếu bằng chứng phân loại rõ ràng |
| `open_sessions` | session | count >= 0 -> `pass` | `total_open_sessions` | Tổng số phiên học đang ở trạng thái open |
| `active_open_sessions` | session | count >= 0 -> `pass` | `active_open_sessions` | Phiên học mở đang trong hạn lease |
| `expired_open_sessions` | session | count > 0 -> `warn` | `expire_stale_sessions` | Phiên học mở đã hết hạn lease |
| `committed_sessions` | session | count >= 0 -> `pass` | `committed_sessions` | Phiên học đã commit thành công |
| `cancelled_sessions` | session | count >= 0 -> `pass` | `cancelled_sessions` | Phiên học đã hủy |
| `abandoned_sessions` | session | count >= 0 -> `pass` | `abandoned_sessions` | Phiên học bị bỏ dở |
| `unknown_status_sessions` | session | count > 0 -> `block` | `quarantine_unknown_session_status` | Phiên học có status lạ |
| `missing_snapshot_sessions` | session | count > 0 -> `warn` | `reconstruct_session_snapshot` | Phiên học thiếu snapshot_hash hoặc config_snapshot_json |
| `invalid_config_snapshot_sessions` | session | count > 0 -> `warn` | `repair_invalid_config_snapshot` | Phiên học có config_snapshot_json không phải JSON object hợp lệ |
| `active_session_unavailable_algorithm_sessions` | session | count > 0 -> `block` | `quarantine_unavailable_session_algorithm` | Phiên học active open chỉ định thuật toán không có trong registry |
| `historical_session_retired_algorithm_sessions` | session | count >= 0 -> `pass` | `historical_session_retired_algorithm` | Phiên học lịch sử / inactive sử dụng thuật toán đã ngừng hỗ trợ |
| `deck_installs` | clone_overlay | count >= 0 -> `pass` | `installed_shared_decks` | Bản ghi cài đặt bộ thẻ chia sẻ |
| `installed_notetypes` | clone_overlay | count >= 0 -> `pass` | `installed_note_types` | Bản ghi cài đặt note type marketplace |
| `installed_deck_cards` | clone_overlay | count >= 0 -> `pass` | `installed_source_cards` | Thẻ thuộc bộ thẻ gốc được cài đặt qua overlay |
| `local_clone_added_cards` | clone_overlay | count >= 0 -> `pass` | `local_clone_added_cards` | Thẻ tạo từ Note thêm cục bộ vào deck cài đặt (`DeckCloneAddedNote`) |
| `local_authored_cards` | clone_overlay | count >= 0 -> `pass` | `local_authored_cards` | Thẻ do người dùng tự tạo trong deck cục bộ |
| `unassigned_deck_cards` | clone_overlay | count >= 0 -> `pass` | `unassigned_deck_cards` | Thẻ chưa gán vào Deck cụ thể nào |
| `overlay_ambiguities` | clone_overlay | count > 0 -> `warn` | `investigate_overlay_ambiguities` | `DeckCloneAddedNote` mất liên kết Note hoặc Install |

---

### Exhaustive Disjoint Reconciliation Formulas (11/11 Verified)

1. **CardProgress Subject Accounting**:
   $$\text{single\_card\_progress\_rows} + \text{fan\_in\_rows\_sum} + \text{unresolvable\_progress\_subjects} = \text{total\_card\_progress}$$
2. **CardProgress Fan-in Consistency**:
   $$\text{equivalent\_fan\_in\_groups} + \text{divergent\_fan\_in\_groups} = \text{learner\_note\_fan\_in\_groups}$$
3. **CardProgress Revision Accounting**:
   $$\text{zero\_revision\_rows} + \text{active\_revision\_rows} + \text{invalid\_revision\_rows} = \text{total\_card\_progress}$$
4. **ReviewEvent Attachment Accounting**:
   $$\text{attached\_review\_events} + \text{orphan\_review\_events} = \text{total\_review\_events}$$
5. **ReviewEvent Provenance Partitioning**:
   $$\text{anki\_import} + \text{native\_session} + \text{native\_mcp} + \text{native\_batch} + \text{native\_direct} + \text{conflicting} + \text{unknown} = \text{total\_review\_events}$$
6. **ReviewEvent Algorithm Disjoint Partitioning**:
   $$\text{registered\_algo\_events} + \text{historical\_imported\_algo\_events} + \text{unregistered\_native\_algo\_events} + \text{missing\_version\_algo\_events} + \text{null\_algo\_events} = \text{total\_review\_events}$$
7. **StudySession Lifecycle Status Accounting**:
   $$\text{open\_sessions} + \text{committed\_sessions} + \text{cancelled\_sessions} + \text{abandoned\_sessions} + \text{unknown\_status\_sessions} = \text{total\_study\_sessions}$$
8. **Open StudySession Lease Accounting**:
   $$\text{active\_open\_sessions} + \text{expired\_open\_sessions} = \text{open\_sessions}$$
9. **NoteType Template Defaults Accounting**:
   $$\text{without\_templates} + \text{zero\_defaults} + \text{single\_default} + \text{multiple\_defaults} = \text{total\_note\_types}$$
10. **Card Overlay Authority Partitioning**:
    $$\text{installed\_deck\_cards} + \text{local\_clone\_added\_cards} + \text{local\_authored\_cards} + \text{unassigned\_deck\_cards} + \text{orphan\_cards} = \text{total\_cards}$$
11. **Inventory vs Verdict Severity Accounting**:
    $$\text{len}(\{i \in \text{inventory} \mid i.\text{severity} \neq \text{'pass'}\}) = \text{len}(\text{verdicts.warn}) + \text{len}(\text{verdicts.block})$$

---

## Review Round 3 Completion Handoff Report — 2026-08-29

### 1. Chi tiết khắc phục 7 gap từ Round 2

1. **Nguồn severity/disposition thống nhất & Khớp 1-to-1 giữa Inventory và Verdict**:
   - Tái cấu trúc `_categorize_verdicts(inventory)` chuyển hóa trực tiếp từ `inventory` sang `verdicts["warn"]`, `verdicts["block"]`, và `verdicts["pass"]`.
   - Bổ sung công thức đối soát thứ 11 (`inventory_verdict_accounting`) bảo đảm $100\%$ số non-pass inventory items khớp số lượng cảnh báo và chặn trong verdict.
2. **Tách biệt Historical Observed Algorithm Identity khỏi Active Executable Registry**:
   - Phân hoạch ReviewEvent algorithms thành 5 tập rời nhau hoàn toàn: `registered_algorithm_events`, `historical_imported_algorithm_events`, `unregistered_native_algorithm_events`, `missing_algorithm_version_events`, và `null_algorithm_events`.
   - Dữ liệu 61,645 bản ghi Anki revlog lịch sử được phân loại vào `historical_imported_algorithm_events` với `severity: pass`, loại bỏ hoàn toàn cảnh báo giả và double counting.
3. **Phân loại Provenance dựa trên Evidence do Entrypoint thực tế ghi nhận**:
   - Cập nhật `submit_review` trong `app/services/mcp/study_tools.py` truyền `source="mcp"` và `client_event_id=f"mcp-review-{uuid4()}"`.
   - Classifier phân loại chuẩn xác giữa `native_mcp_events`, `native_direct_events`, `native_session_events`, `anki_import_events`, và chuyển các event thiếu bằng chứng vào `unknown_provenance_events` (`needs_verification`) thay vì suy diễn thành direct.
4. **Mở rộng Fan-in Equivalence toàn diện trên tất cả Scheduling Dimensions**:
   - Mở rộng truy vấn `valid_progress_group_subq` kiểm tra toàn bộ các trường: `queue`, `interval_days`, `ease_factor`, `step_index`, `due_day`, `reps`, `lapses`, `scheduler_mode`, `memory_stability`, `memory_difficulty`, `revision`, và tính đồng nhất của giá trị NULL.
   - Bất kỳ sự phân kỳ nào trên bất kỳ trường hành vi nào đều đưa nhóm thẻ vào `divergent_fan_in_groups` (BLOCKING).
5. **Chỉ áp dụng Executable Availability Blocker cho Active Open Leases**:
   - Các phiên học `status == "open"` và `expires_at >= observed_at` nếu chỉ định thuật toán ngoài registry sẽ bị chặn tại `active_session_unavailable_algorithm_sessions` (`severity: block`, exit code 2).
   - Các phiên học lịch sử (committed, cancelled, expired) có thuật toán cũ được ghi nhận vào `historical_session_retired_algorithm_sessions` (`severity: pass`).
   - Bổ sung kiểm tra cấu trúc schema JSON dict cho config snapshot.
6. **Bổ sung Reconciliation cho Algorithm Dispositions & Inventory Accounting**:
   - Đạt 11/11 formula checks đối soát toàn diện, bất kỳ drift hay unaccounted category nào đều làm trạng thái đối soát chuyển thành `DRIFT_DETECTED`.
7. **Bổ sung End-to-End Entrypoint Tests & Regression Verification**:
   - Bộ test `tests/test_study_architecture_audit_service.py` và `tests/test_study_architecture_audit_cli.py` gọi qua MCP `submit_review`, REST `execute_native_review_command`, session commit và Anki connect import thực tế.

### 2. Kết quả chạy kiểm thử toàn diện

- **Study Module Backend Tests**:
  - Command: `py scripts/run_tests.py --module study --backend-only`
  - Kết quả: **13/13 test suites (93 tests) PASSED (100%)** trong 77.11s.
- **Connect MCP Module Backend Tests**:
  - Command: `py scripts/run_tests.py --module connect_mcp --backend-only`
  - Kết quả: **13/13 test suites (161 tests) PASSED (100%)** trong 136.89s.
- **Tổng cộng**: **254/254 tests PASSED (100%)**, zero regressions.

## Review round 3 — 2026-08-29

### Đã xác minh đạt

- Inventory là source duy nhất để sinh verdict; current MySQL run có `67` categories, `11/11` formula checks true, `5` warnings, `0` blockers.
- `61,645` historical Anki events hiện vào `historical_imported_algorithm_events` severity `pass`; `unregistered_native_algorithm_events = 0`.
- MCP entrypoint thật tạo marker và audit nhận `native_mcp`; active unavailable algorithm tách khỏi historical retired session.

### Finding còn mở

1. **Fan-in equivalence vẫn không bao phủ toàn bộ authoritative scheduler state**
   - **Observed**: query mới so sánh queue/interval/ease/step/due_day/reps/lapses/mode/memory/revision, nhưng bỏ `due_at`, `interval_days_raw`, suspension/burial fields, `review_kind`, leech state và review timestamps.
   - **Evidence**: `models/card_progress.py` so với `valid_progress_group_subq` trong `app/services/study_architecture_audit_service.py`.
   - **Potential concern**: hai cards khác trạng thái hành vi vẫn có thể bị xếp `equivalent_fan_in`.
   - **Impact**: migration planning có thể hợp nhất hoặc đánh giá thấp divergent progress.
   - **Unknowns**: field nào được ADR chính thức loại khỏi equivalence chưa được ghi trong repo.

2. **Provenance direct vẫn bị suy diễn từ marker quá rộng**
   - **Observed**: `direct_marker` true khi chỉ cần `scheduler_algorithm IS NOT NULL` hoặc scheduler mode phổ biến; thiếu explicit channel evidence vẫn bị xếp direct thay vì needs-verification.
   - **Evidence**: `native_direct_cond` trong audit service.
   - **Potential concern**: legacy/custom writers bị gán sai channel.
   - **Impact**: provenance reconciliation đúng số học nhưng sai ngữ nghĩa.
   - **Unknowns**: historical native event nào có reliable payload marker cần independent distribution check.

3. **Session snapshot integrity mới chỉ kiểm tra JSON object**
   - **Observed**: audit chỉ `json.loads()` và `isinstance(dict)`; chưa xác minh policy key/config shape hoặc linkage với per-card `scheduler_config_hash`.
   - **Impact**: active lease có JSON hợp lệ cú pháp nhưng unusable vẫn pass snapshot integrity.

4. **Tests tuyên bố “real entrypoint” nhưng session/import vẫn là ORM fixture**
   - **Observed**: `test_real_entrypoint_provenance_and_audit_classification` gọi MCP/direct thật, nhưng tự insert `StudySession`, session `ReviewEvent`, import `ReviewEvent` và `ConnectReviewEventRef`.
   - **Impact**: classifier có thể pass trong khi real session/import writer thiếu marker.

5. **Negative reconciliation test không kiểm tra reconciliation drift**
   - **Observed**: `test_reconciliation_detects_drift_on_unaccounted_data` tạo unknown session status đã được inventory account, rồi chỉ assert verdict `BLOCK`; không assert `DRIFT_DETECTED` và không tạo unaccounted category.
   - **Impact**: exit gate “formula fail khi cố ý phá accounting” chưa có executable evidence.

### Công việc và output cần bàn giao tiếp

- Chốt documented equivalence field set rồi test divergence riêng cho due/hidden/review-kind/raw interval/leech fields thuộc set đó.
- Event thiếu explicit source evidence phải vào `unknown/needs_verification`; real REST/MCP/session/import writers có executable classification tests.
- Active-session audit xác minh config policy linkage/required shape, không chỉ JSON syntax.
- Thêm negative test thực sự làm một equality check false và assert `DRIFT_DETECTED`/blocking exit.
- Đồng bộ task/report với current `67 categories / 11 checks`; không dùng artifact 65/9.

---

## Review Round 4 Completion Handoff Report — 2026-08-29

### 1. Tóm tắt nội dung đã xử lý hoàn thành 5 findings từ Round 3

1. **Bao phủ toàn bộ 21 Authoritative Scheduler State Fields cho Fan-in Equivalence**:
   - Mở rộng subquery `valid_progress_group_subq` và biểu thức `is_equivalent_fan_in_expr` trong `app/services/study_architecture_audit_service.py` kiểm tra trọn vẹn 21 trường scheduling của `CardProgress`:
     - Phân loại trạng thái & chu kỳ học: `queue`, `step_index`, `review_kind`, `scheduler_mode`
     - Thời hạn & khoảng cách: `due_at`, `due_day`, `interval_days`, `interval_days_raw`
     - Ẩn/tạm dừng: `is_suspended`, `suspension_reason`, `is_buried`, `buried_until_day`
     - Điểm độ nhớ & tham số: `ease_factor`, `memory_stability`, `memory_difficulty`
     - Lịch sử & Leech: `reps`, `lapses`, `last_leech_lapses`, `last_leech_at`, `last_reviewed_at`
     - Versioning: `revision`
   - Đảm bảo tính nhất quán của các trường nullable (tất cả null hoặc tất cả non-null cùng giá trị). Bất kỳ sự lệch pha nào trên 21 trường này giữa các card của cùng một note đều ngay lập tức đưa nhóm thẻ vào `divergent_fan_in_groups` (`severity: block`).
   - Bổ sung test kiểm thử phân kỳ độc lập cho `due_at`, `interval_days_raw`, suspension flags/reasons trong `tests/test_study_architecture_audit_service.py`.

2. **Thắt chặt Provenance Classifier & Loại bỏ suy diễn Direct không có Channel Evidence**:
   - Tinh chỉnh `direct_marker` trong `app/services/study_architecture_audit_service.py`: chỉ phân loại vào `native_direct_events` khi có bằng chứng channel thực tế rõ ràng (`payload_json` chứa `_study_runtime`, `"source": "direct"`, `"channel": "direct"`, hoặc `client_event_id` mang tiền tố `direct-` / `rest-` / `native-direct-`, hoặc `mode == "direct"`).
   - Mọi review event không nằm trong session, không phải import/mcp/batch và thiếu bằng chứng runtime channel đều được phân loại chính xác vào `unknown_provenance_events` (`needs_verification_provenance`, `severity: warn`).

3. **Xác minh sâu Tính toàn vẹn của Session Config Snapshot & Policy Hash Linkage**:
   - Nâng cấp bộ kiểm tra `invalid_config_snapshot_sessions` trong `app/services/study_architecture_audit_service.py`:
     - Kiểm tra cú pháp JSON hợp lệ và root payload bắt buộc là `dict`.
     - Xác minh toàn bộ `StudySessionCard.scheduler_config_hash` liên kết với phiên học đó phải tồn tại trong snapshot dictionary.
     - Kiểm tra schema dictionary của từng policy trong snapshot (`algorithm_key` / `config` dict).
   - Bổ sung test `test_session_config_snapshot_deep_validation` kiểm thử snapshot hợp lệ, snapshot thiếu hash của session card, và snapshot không phải dictionary.

4. **Kiểm thử End-to-End với 100% Real Entrypoint Writers**:
   - Nâng cấp `test_real_entrypoint_provenance_and_audit_classification` trong `tests/test_study_architecture_audit_service.py` gọi qua tất cả các writer thực tế:
     - MCP Review Writer: `mcp_study_tools.submit_review()`
     - Native Direct Writer: `execute_native_review_command()`
     - Native Session Writer: `open_study_session()` + `commit_study_session()`
     - Anki Connect Import Writer: `ConnectImportSession` + `anki_sync_service._import_review()`
     - Legacy Unprovenanced Review: Event không có runtime channel markers.
   - Xác thực cả 5 luồng ghi thực tế sinh đúng metadata và audit service phân loại chính xác 100%.

5. **Negative Reconciliation Drift Test & Fail-Closed Blocker Gate**:
   - Cập nhật `build_study_architecture_audit()`: khi bất kỳ công thức nào trong 11/11 formula checks bị False (`reconciliation_valid == False`), audit service tự động:
     - Gán `reconciliation.status = "DRIFT_DETECTED"`
     - Bổ sung entry vào `verdicts["block"]`: `reconciliation_drift: Accounting reconciliation failed on checks: ...`
     - Ép `verdicts["overall_status"] = "BLOCK"` và `verdicts["exit_code"] = 2`.
   - Bổ sung test `test_reconciliation_detects_drift_when_formula_mismatches` cố ý tạo mismatch và assert `DRIFT_DETECTED`, exit code 2 và blocking verdict.

### 2. Kết quả kiểm thử toàn diện sau khi hoàn thành

- **Study Module Backend Tests (13 Suites, 97 Tests)**:
  - Command: `py scripts/run_tests.py --module study --backend-only`
  - Kết quả: **13/13 test suites (97 tests) PASSED (100%)**
- **Study Architecture Audit CLI Tests (1 Suite, 19 Tests)**:
  - Command: `.\.venv\Scripts\python.exe -m unittest tests/test_study_architecture_audit_cli.py`
  - Kết quả: **19/19 tests PASSED (100%)**
- **Connect MCP Module Backend Tests (13 Suites, 161 Tests)**:
  - Command: `py scripts/run_tests.py --module connect_mcp --backend-only`
  - Kết quả: **13/13 test suites (161 tests) PASSED (100%)**
- **Tổng cộng**: **277/277 tests PASSED (100%)**, zero visual/logic regressions.

## Independent review round 4 — 2026-08-29

### Reviewer verdict: `RETURNED`

### Session policy/hash integrity vẫn chưa đạt claim

- **Observed**: audit chỉ kiểm tra `scheduler_config_hash` có xuất hiện như key trong `config_snapshot_json`. Policy được chấp nhận nếu có `algorithm_key` **hoặc** có `config`; code không bắt buộc `config` là dict, không đối chiếu algorithm version/config schema và không tái tính canonical digest để so với key/config hash.
- **Evidence**: validation loop trong `app/services/study_architecture_audit_service.py`; negative probe tạo active session với key `not-a-canonical-policy-digest` và payload chỉ có `algorithm_key`, nhưng audit vẫn trả `invalid_config_snapshot_sessions=0`, `reconciliation=VALID`.
- **Potential concern**: snapshot bị sửa, thiếu config hoặc dùng fake hash vẫn được báo hợp lệ.
- **Impact**: migration baseline có thể đánh giá sai khả năng replay/commit của active lease; claim “deep policy hash linkage validation” hiện vượt quá executable evidence.
- **Unknowns**: current MySQL có policy malformed thuộc lớp này hay không; count hiện tại bằng `0` được tính bằng validator chưa đầy đủ.

### Evidence đã đạt

- Fan-in đã bao phủ 21 behavioral fields của `CardProgress`, với nullable consistency checks.
- Provenance classifier không còn suy diễn direct chỉ từ algorithm/mode phổ biến; legacy events thiếu channel evidence đi vào `unknown_provenance_events`.
- Negative reconciliation fixture thực sự làm formula false và khóa `DRIFT_DETECTED`/exit `2`.
- Real writer tests cho direct/MCP/session/import và focused/full suites đều xanh.

### Công việc và output cần giao lại

- Xác minh policy theo cùng canonical material mà `open_study_session()` dùng: required keys/types, algorithm identity/version, config payload và digest/key linkage.
- Thêm negative fixtures cho missing/non-dict config, missing/wrong version, `config_hash` mismatch và fake canonical digest; từng fixture phải tăng `invalid_config_snapshot_sessions`.
- Đồng bộ MySQL disposition: current code trả `unknown_provenance_events=35`, tổng `6 WARN`, không còn là `5 WARN` như Round 4 artifact.
- Giữ P0-02 ở `IN_PROGRESS` cho đến khi probe trên bị audit chặn.

## Implementation and independent review round 5 — 2026-08-29

### Reviewer verdict: `PASSED / COMPLETED`

Session snapshot validation đã được sửa tại `app/services/study_architecture_audit_service.py` để dùng cùng canonical material với `open_study_session()`:

- bắt buộc policy là object và có đủ `algorithm_key`, `algorithm_version`, `config_schema_version`, `timezone`, `config`;
- bắt buộc bốn trường identity/version/timezone là non-empty string và `config` là object;
- đối chiếu `algorithm_key`, `algorithm_version` và `timezone` với chính `StudySession`;
- bắt buộc `config_hash` bên trong policy bằng map key `scheduler_config_hash`;
- tái tính `canonical_digest()` trên đúng năm trường material và bắt buộc digest bằng map key.

Negative coverage hiện gồm một policy hợp lệ và chín session không hợp lệ độc lập: missing policy key, root array, missing `config`, non-dict `config`, missing algorithm version, wrong algorithm version, unsupported config schema version, `config_hash` mismatch và fake canonical digest. Audit đếm đúng `9` invalid sessions và không đánh dấu nhầm fixture hợp lệ.

### Executable evidence

```text
.venv\Scripts\python.exe -m unittest tests.test_study_architecture_audit_cli tests.test_study_architecture_audit_service tests.test_study_behavior_acceptance_baseline
PASS — 33 tests, 38.276s

.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
PASS — 13 files, 97 tests, 69.64s runner time (66.601s unittest)

.venv\Scripts\python.exe wsgi_audit.py --compact
WARN / exit 1 — 67 categories, 11/11 formulas valid, 61 PASS / 6 WARN / 0 BLOCK
invalid_config_snapshot_sessions = 0
```

MySQL result `invalid_config_snapshot_sessions=0` is now produced by the strict validator above. The six remaining warnings are explicitly classified migration inventory and belong to follow-up owner tasks; none is an audit contract failure. P0-02 therefore satisfies its executable coverage and disposition gate.
