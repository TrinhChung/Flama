# Kế hoạch thực thi Phase 6 — tách Card/Template khỏi quyền sở hữu progress

> **Cập nhật 2026-09-30.** P5-T đã đạt trên production (R1 29/09: 18/18 learner NOTE, audit PASS, tài khoản mới vào NOTE). Theo chỉ đạo 30/09 của chủ sản phẩm ("hoàn thiện decoupling lần lượt từng phase, giữ hiệu năng, không mất/hỏng dữ liệu"), các quyết định D6 được chốt như bảng dưới — tất cả theo đề xuất, **trừ D6-05 chọn phương án B**:
>
> | ID | Chốt | Lý do khi khác đề xuất |
> |---|---|---|
> | D6-01..D6-04, D6-06..D6-09 | Theo đề xuất §4 | — |
> | D6-05 | **B**: giữ xóa cứng; lineage chuyển sang Note trước khi cascade (`connect_source_card_refs.note_id`, `card_id` NULL + `ON DELETE SET NULL`) | Phương án A cần lọc "application đang hoạt động" ở 182 chỗ truy vấn Card trong 49 file (chưa kể SQL thô); sót một chỗ là Card đã retire quay lại trong số đếm, phiên học hoặc kiểm tra vector sibling của NOTE. B giữ mọi dữ liệu learner (state Note, lịch sử qua `logical_note_key` và `review_events.note_id`, con trỏ Anki trên Note) mà không đổi gì reader đang thấy. ID Card đã xóa vẫn không còn địa chỉ, như hôm nay. |
>
> Trạng thái code: [P6-00 inventory](./P6-00_INVENTORY.md) xong; P6-04 (migration 46), P6-05 (seam `before_flush`), phần D6-04/D6-06/D6-07/D6-05B của P6-06/P6-08 đã có code + test + probe MySQL trên nhánh `phase6/p6-applications`. Còn: kiểm lại lifecycle hủy phiên khi xóa Template (P6-07), bỏ `uq_cards_note_template` cho áp dụng lặp (D6-09), INT-04, P6-10.

> Lập ngày: 2026-09-29 | Trạng thái: **CHUẨN BỊ — chưa có code Phase 6.** Tài liệu này chốt baseline, các quyết định cần chủ sản phẩm và thứ tự work package. Không có migration, cờ hay thay đổi runtime nào đi kèm.
>
> Baseline code: `develop` tại `0ba1d69` (Phase 5 code + INT-03 local xanh, [P5 plan](./P5_EXECUTION_PLAN_2026-09-20.md) §2). Production vẫn ở head `20260913_000039`, chưa có R0 (PR #168 `develop → master` còn mở; `deploy.yml` chỉ chạy trên `master`).
>
> Scope gốc: [canonical plan §15 Phase 6](../../architecture/study-interaction-trigger-algorithm-plan.md#phase-6--remove-cardtemplate-from-progress-ownership). Hợp đồng nền: [applied composition/binding (P3-07)](../../architecture/applied-composition-binding-contract-2026-09-09.md), [history/lifecycle ADR (P4-04)](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md), [P5 runbook](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md). Issue liên quan: #137 (versioning Template cho shared deck).

## 1. Kết quả và ranh giới

Phase 6 hoàn tất khi `Card` và `Template` chỉ còn là presentation/compatibility identity:

1. Mọi thao tác Template (sửa, thay, gỡ/retire, xóa) và thao tác Card giữ nguyên 100% progress learner/Note.
2. Session mới chọn **Note + applied composition (application occurrence)**; progress lookup theo Note, không theo Card.
3. Card ID cũ được giữ qua mapping tường minh; REST/MCP/Connect/Anki địa chỉ theo Card đều resolve về cùng learner/Note subject.
4. Tham chiếu Anki ngoài, ordinal import, attribution lịch sử và clone lineage sống sót qua lifecycle của Card.
5. Một NoteType có nhiều application, kể cả **áp dụng lặp lại cùng một Template**, mà không tạo thêm progress row.

**Không thuộc Phase 6:** purge detail 30 ngày và aggregate (Phase 7); Interaction/binding kind/Algorithm mới (Phase 8); ngừng ghi `CardProgress`, xóa Card/Template/decoder cũ (Phase 9); bật async batch; đổi mô hình overlay-only (clone vẫn không copy/mutate source Note/Card).

## 2. Baseline: Phase 5 đã giao phần nào

Kiểm tra trực tiếp trên code `0ba1d69`. "NOTE" = learner đã enroll authority NOTE; "LEGACY" = mặc định.

| Yêu cầu Phase 6 | Hiện trạng | Còn thiếu |
|---|---|---|
| Template sửa/thay/xóa giữ progress | **NOTE: đã có.** Thêm sibling chép state trước khi gỡ (`study_note_template_service.stage_note_template_changes`), xóa Template là partial sibling removal giữ Note state (`study_content_delete_service.prepare_content_delete`, gọi từ `flashcard_content_service.delete_template:934`). | **LEGACY:** `CardProgress` là authority và cascade theo Card (`models/card.py:20`, `models/card_progress.py:17`), nên thay Template = mất progress của Card cũ. Template của shared deck đã release bị chặn `SHARED_SCHEMA_VERSIONING_REQUIRED` (`flashcard_content_service.py:1548`). |
| Card-addressed REST/MCP/Connect → Note subject | **NOTE: đã có** (P5-04/06/07: direct answer, MCP `submit_review`/`get_card`/`get_note`, Connect snapshot/revlog). | Anki `ord` map qua `Template.position` rồi fallback theo vị trí (`anki_sync_service._card_for_ord:122`). Không có application identity để bind ổn định. |
| Session chọn Note + composition | **Một phần.** Composition hiện là Template compatibility (`comp:notetype:{nt}:template:{t}`, `study_composition_service.py:94`), session lọc `Card.template_id` (`:361`), nên mỗi Note xuất hiện một lần trong một phiên. | Đếm dashboard/deck/stats duyệt **từng Card** kể cả với NOTE (`dashboard_service.py:296`, `study_authority_read_service.summarize_study_authority_queue:413`). NoteType nhiều Template sẽ đếm một Note nhiều lần. |
| Áp dụng lặp lại một Template | **Chưa có.** `uq_cards_note_template` (`models/card.py:23`) cấm hai Card cùng `(note_id, template_id)`; P3-07 ghi `application_id = composition_id` chỉ là compatibility. | Occurrence identity vật lý (P3-07 "Deferred physical design"). |
| Bỏ cascade Template/Card lên authority | **NOTE: state không cascade** (`study_progress_subjects.live_note_id` là `SET NULL`; state gắn subject). | `StudySessionCard.card_id` (`models/study_session_card.py:18`) và `ConnectSourceCardRef.card_id` (`models/connect_source_card_ref.py:23`) vẫn `CASCADE`: xóa Card làm mất membership phiên và cursor/mapping Anki. |
| Attribution lịch sử | `StudyProgressHistoryFact` có `logical_note_key`. | `ReviewEvent.card_id` là text, không có cột Note (`models/review_event.py:11`). Production 2026-09-21 có 595 event trỏ tới Card đã xóa ([P5-00](../../architecture/phase-5-p5-00-inventory-2026-09-21.md)). |
| Clone lineage | **Đã có:** subject overlay = (installer, source Note); install `legacy_copy` bị loại khi enroll (`CLONE_CUTOVER_PENDING`). Production 2026-09-21: 17 install, đều `logical_overlay`. | Structural Template change cho shared deck (#137). |
| Reader NOTE độc lập Card | **Chưa.** Reader NOTE yêu cầu đủ vector sibling: mỗi Card phải có `CardProgress` projection + contributor + availability (`study_authority_read_service.py:254-341`); availability khóa theo contributor/Card (`card_order_key`, `card_created_at`). | Cần quyết định có giữ vector Card-shaped (xem D6-03) hay chuyển availability lên mức Note. |
| Note không còn Card | Enrollment từ chối Note sở hữu không có Card (`study_authority_enrollment_service.py:317`); pristine read từ chối (`study_note_pristine_service.py:146`); NoteType bắt buộc ≥1 Template ở REST (`flashcard_content_service.py:955`) và MCP (`study_note_template_service.py:86`). | Giữ bất biến này hay không là quyết định D6-02. |

Nơi tạo Card: **14 callsite trong 11 file**, chưa có một service chung: `flashcard_content_service._create_cards`, `connect/actions.add_note`, `connect/import_cards._reconcile_note_cards` và `_reconcile_note_authority_cards`, `flashcard_import` (CSV), `flashcards_share_service.create_template`, `share/note_types.create_template`, `note_sync_service.execute_sync_notes`, `mcp/note_tools.create_note`, `mcp/note_type_tools.update_note_type` (2), `study_note_template_service`, `seeding_service` (2). Áp dụng lặp lại cần một seam tạo Card duy nhất.

## 3. Phát hiện ảnh hưởng thứ tự

1. **Phase 6 production phụ thuộc việc hết learner LEGACY.** Content dùng chung nhiều learner (owner, overlay subscriber). Chừng nào còn learner LEGACY trên cùng content, xóa/thay Template vẫn xóa progress của họ. Mốc này là P5-T (§5): từ quyết định 2026-09-29, R1 chuyển mọi learner sang NOTE một lượt và tài khoản mới vào thẳng NOTE. P5-T là điều kiện bật Phase 6 trên production, không phải điều kiện bắt đầu code.
2. **Rollback window.** [Runbook §4.4](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md) chỉ cho NOTE → LEGACY khi mọi state còn sống chiếu không mất mát về `CardProgress`. Bất kỳ trạng thái Phase 6 nào không có Card để chiếu (Note không Card, occurrence không Card) sẽ đóng rollback của learner đó. Vì vậy D6-02 và D6-03 phải quyết cùng nhau.
3. **Nguy cơ lẫn vào R0.** Code Phase 6 commit vào `develop` sẽ đi theo PR #168 lên `master` và vào R0. Cho tới khi R0 deploy xong, code Phase 6 ở nhánh `phase6/*` (giống `phase4/*`); chỉ tài liệu được vào `develop`.
4. **Mapping ordinal Anki mong manh.** Xóa Template cascade `ConnectSourceCardRef`; lần sync sau `_card_for_ord` có thể map `ord` sang Card sibling khác theo vị trí. Với NOTE, progress vẫn trúng cùng Note, nhưng `snapshot_hash`/`applied_local_revision`/`review_cursor` đã mất. **Chưa xác minh** quy tắc xung đột P1-02 xử lý snapshot "mới" này ra sao; P6-00 phải tái hiện bằng test.

## 4. Quyết định cần chủ sản phẩm

Đề xuất đứng đầu mỗi hàng. P6-01..P6-03 viết thành ADR đầy đủ; bảng này là bản tóm tắt để duyệt nhanh.

| ID | Câu hỏi | Đề xuất | Phương án còn lại / hệ quả |
|---|---|---|---|
| D6-01 | Khi nào bật hành vi Phase 6 trên production? | Code ngay sau cờ mặc định tắt và chứng minh trên MySQL disposable toàn NOTE; **bật production sau P5-T** (mọi learner hoạt động ở NOTE, learner mới mặc định NOTE). | Chạy song song LEGACY với refusal có mã: phải thêm nhánh fail-closed ở mọi writer Phase 6, content dùng chung giữa hai mode khó chứng minh. |
| D6-02 | Giữ rollback NOTE → LEGACY suốt Phase 6? | **Giữ.** Bất biến: mỗi Note có ≥1 Card, mỗi occurrence có Card, projection vẫn lossless. Đóng rollback chuyển sang preflight Phase 9. | Đóng rollback ngay khi vào Phase 6: cho phép Note không Card và occurrence không Card, nhưng rollback chỉ còn forward repair/backup restore. |
| D6-03 | Occurrence identity vật lý | **A — Card là occurrence.** Bảng application mới (NoteType-scoped: definition = Template, ordinal, binding fingerprint, trạng thái); `cards.application_id` backfill 1:1 cho Card hiện có; unique đổi từ `(note_id, template_id)` sang `(note_id, application_id)`. Wire v4 giữ nguyên, Card ID cũ giữ nguyên, projection vẫn lossless. Đúng dòng "Queue item → references an application" của P3-07. | B — occurrence không cần Card, membership phiên theo `(note, application)`: cần wire v5 + frontend dual reader, và occurrence mới không có projection (đóng rollback, xung đột D6-02). |
| D6-04 | Đếm new/learn/due theo gì? | **Theo Note** cho learner NOTE ở dashboard, deck tree, stats và count MCP; hàng đợi phiên giữ nguyên (một Card của application đã chọn cho mỗi Note). Production 2026-09-21 là 40.227 Note / 40.227 Card nên hôm nay không đổi số hiển thị. | Giữ theo Card: NoteType nhiều Template sẽ báo một Note đến hạn N lần dù trả lời một lần là hết hạn tất cả. |
| D6-05 | Xóa Template/application làm gì với Card? | **Retire (mềm):** application chuyển `RETIRED`, ngừng discovery; Card giữ làm compatibility identity ẩn, nên mapping Anki, membership phiên, attribution và projection còn nguyên. Đúng câu "Do not delete compatibility identities in this phase" của canonical plan. Purge vật lý để Phase 9. Tác dụng phụ: learner LEGACY cũng không mất progress. | Xóa cứng như hiện tại + chuyển lineage sang Note trước khi cascade (thêm `note_id` vào `ConnectSourceCardRef`, `card_id` nullable `SET NULL`). Ít bề mặt lọc hơn nhưng mất Card ID. **Chi phí của đề xuất:** mọi truy vấn Card (composition, Browse, count, map ordinal, reader vector) phải lọc application đang hoạt động qua một helper chung. |
| D6-06 | Anki `source_ord` bind vào đâu (Priority-1 #14)? | **Ordinal lưu trên application** lúc import; bỏ fallback theo vị trí cho NOTE, `ord` không map được trả mã lỗi. | Giữ `Template.position` + fallback: reorder/retire sẽ trỏ `ord` sang sibling khác. |
| D6-07 | Attribution `ReviewEvent` theo Note | **Thêm cột snapshot `note_id`** (additive, không FK), backfill những event resolve được, event đã detached ghi `UNRESOLVED`. Phase 7 aggregate cần chiều này. | Chỉ dựa vào `StudyProgressHistoryFact`: không có cho dữ liệu trước Phase 4 và cho learner chưa bật shadow. |
| D6-08 | #137 (versioning Template shared deck) thuộc Phase 6? | **Track riêng 6B**, bắt đầu sau khi schema P6-04 có application identity. Exit Phase 6 cho source-clone gồm: content-only hotfix (#138), install/uninstall, local-added, xóa source Note. Structural change cho shared Template vẫn trả `SHARED_SCHEMA_VERSIONING_REQUIRED`. | Gộp vào Phase 6: exit gate đầy đủ hơn nhưng kéo release/rebase/fork vào critical path. |
| D6-09 | Có mở UI áp dụng lặp lại Template? | **Chỉ storage + test** ở Phase 6. Hiện chỉ có `legacy-fielddef-direct` binding và một Interaction, nên áp dụng lặp lại chưa đem lại gì khác cho người dùng; UI đi cùng Phase 8. | Mở UI ngay: hai mode giống hệt nhau trong selector. |

## 5. Gate và thứ tự

| Gate | Điều kiện | Hiện tại |
|---|---|---|
| P5-T — Phase 5 tail | R0 deploy (merge #168); R1 chuyển mọi learner sang NOTE một lượt (quyết định 2026-09-29 bỏ canary, [runbook §4](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md)); tài khoản mới vào NOTE (`STUDY_NEW_LEARNER_NOTE_ENABLED`); audit `study-authority-read-audit` PASS toàn bộ | Code sẵn sàng; chờ backup + deploy + chạy runbook |
| G6-D — thiết kế | D6-01..D6-09 được duyệt; ADR P6-01..P6-03 accepted | Chưa |
| G6-S — schema additive | Migration 46+ qua SQLite + MySQL 8.0.40 disposable (upgrade/downgrade rỗng/re-upgrade, boot `wsgi.py` cờ tắt); backfill `application_id` 1:1 không đổi Card ID | Chưa |
| G6-W / G6-R — writer/reader | Mọi callsite tạo/xóa Card đi qua seam application; count/queue theo D6-04; reader NOTE không phụ thuộc Template sống | Chưa |
| G6-L — continuity | Ma trận §6 xanh trên SQLite và MySQL disposable | Chưa |
| INT-04 | Full backend/frontend suite, build, probe P5 + P6, audit, rollback NOTE → LEGACY vẫn pass (nếu D6-02 giữ rollback) | Chưa |
| G6-P — production | P5-T + INT-04; bật cờ Phase 6 theo runbook mới, theo dõi | Chưa |

| ID | Work package | Phụ thuộc | Output | Bắt đầu được ngay? |
|---|---|---|---|---|
| P6-00 | **Inventory + tái hiện rủi ro.** Liệt kê có callsite mọi reader/writer/cascade theo Card hoặc Template (gồm truy vấn thô, bulk delete, frontend/wire); test tái hiện phát hiện §3.4. Phần production (phân bố Card/Note, số Template/NoteType, Connect ref, event detached, install `legacy_copy`, learner theo mode) chạy SELECT-only khi chủ sản phẩm cho phép SSH. | — | Bảng disposition từng callsite; test tái hiện (được phép đỏ, đánh `expectedFailure` có ghi chú) | **Có** (phần code) |
| P6-01 | **ADR application occurrence + Card mapping** (D6-02, D6-03, D6-06, D6-09): bảng, khóa, thứ tự lock, backfill, compatibility ID `comp:*` cũ → application | P6-00 | ADR accepted | Có (bản nháp) |
| P6-02 | **ADR hàng đợi/đếm/availability mức Note** (D6-04): selector, thứ tự new theo Note, fixed-context parity, số đo query MySQL | P6-00 | ADR accepted | Có (bản nháp) |
| P6-03 | **ADR lifecycle + tham chiếu ngoài** (D6-05, D6-07, D6-08): ma trận cascade mới cho Card/Template/Note/NoteType/deck, `ConnectSourceCardRef`, `StudySessionCard`, `ReviewEvent` | P6-00 | ADR accepted | Có (bản nháp) |
| P6-04 | **Schema additive + backfill** (migration 46+), model, cờ mặc định tắt | G6-D + chủ sản phẩm cho phép schema | G6-S | Không |
| P6-05 | **Seam tạo Card theo application**: gom 14 callsite; composition resolver dùng application ID nhưng vẫn nhận `comp:*` cũ | P6-04 | Không còn `Card(...)` ngoài seam; test cũ xanh | Không |
| P6-06 | **Reader/count mức Note** cho dashboard, deck tree, stats, study, MCP, Browse, audit CLI | P6-04, P6-02 | So khớp số trước/sau trên dữ liệu 1:1; NoteType nhiều Template đếm theo D6-04 | Không |
| P6-07 | **Lifecycle**: retire/unretire Template, thay Template, xóa Card/Note, purge NoteType/deck, Browse delete, Connect import reconcile, clone install/uninstall | P6-05, P6-03 | Ma trận §6 phần lifecycle | Không |
| P6-08 | **Integration**: map ordinal Anki theo application, Connect ref bền qua retire, attribution `ReviewEvent`, REST/MCP theo Card vẫn resolve đúng subject | P6-05, P6-03 | Ma trận §6 phần integration | Không |
| P6-09 | **Probe MySQL** `scripts/probe_p6_*_mysql.py` (DB tạm tự tạo/xóa như probe P5): race retire vs answer, expansion vs answer, backfill idempotent, lock order | P6-05..P6-08 | Probe PASS | Không |
| INT-04 | Tích hợp Phase 6 | P6-00..P6-09 | Như gate INT-04 | Không |
| P6-10 | Production: runbook + bật cờ theo cohort sau P5-T | INT-04 + P5-T | G6-P | Không |
| 6B | Versioning Template shared deck (#137) | P6-04 + D6-08 | Theo issue #137 | Không |

**Thứ tự đề xuất:** P6-00 → P6-01/P6-02/P6-03 (song song) → duyệt D6 → P6-04 → P6-05 → P6-06/P6-07/P6-08 (song song, file ownership tách theo service) → P6-09 → INT-04 → (P5-T xong) → P6-10. Song song phía production: R0 → R1 → P5-T không chờ Phase 6.

## 6. Ma trận kiểm chứng Phase 6

| Nhóm | Tình huống bắt buộc |
|---|---|
| Continuity (exit gate) | Note owned, imported (CSV, Anki/Connect), source-clone overlay, local-added × {sửa Template, thay (thêm rồi retire/xóa), retire, unretire, xóa Card, xóa Note}: state, token revision và history không đổi ngoài các transition có chủ đích |
| Áp dụng lặp lại | Một Template áp dụng hai lần: hai Card, một subject, trả lời qua occurrence này làm occurrence kia hết hạn; retire một occurrence không đụng state |
| Integration | REST answer, MCP `submit_review`/`get_card`/`get_note`, Connect snapshot/revlog, Anki `ord` sau reorder/retire đều trúng cùng subject; ref ngoài và cursor còn nguyên |
| Session | Phiên v2/v3/v4 đang mở khi retire/xóa Template: bị hủy có mã hoặc commit qua handler đã pin, không có commit câm; restore IndexedDB |
| Count/queue | Parity trước/sau P6-06 trên dữ liệu 1:1 (UTC, Asia/Tokyo, day boundary, learn-ahead, suspend/bury); NoteType 2 Template đếm theo D6-04 |
| Rollback | Nếu D6-02 giữ rollback: NOTE → LEGACY vẫn lossless sau retire, áp dụng lặp lại và thay Template |
| Fault/MySQL | Race retire vs answer, expansion vs answer, backfill resume, lock timeout, unique violation; không split brain, không mất event/receipt |

Test module hẹp: `python scripts/run_tests.py --module study,flashcards,decks,connect_mcp,database --backend-only`; frontend `--module study --frontend-only`; INT-04 chạy `--all`. Python chạy qua `.venv\Scripts\python.exe`.

## 7. Rollback

- Cờ Phase 6 mặc định tắt; tắt cờ trả về selector/count theo Card và xóa cứng như Phase 5.
- Migration additive; backfill `application_id` giữ nguyên Card ID nên không cần downgrade khi sự cố.
- Retire đảo được (unretire) trong khi Card chưa bị purge; Phase 6 không purge.
- Với D6-02 giữ rollback: mọi learner NOTE vẫn rollback về LEGACY theo runbook §4.4. Nếu D6-02 chọn đóng rollback, runbook Phase 6 phải ghi rõ forward repair/backup restore thay thế.

## 8. Việc tiếp theo cho chủ sản phẩm

1. Duyệt hoặc sửa D6-01..D6-09 (§4).
2. Chạy song song Phase 5: backup → merge PR #168 (R0) → R1 chuyển toàn bộ learner sang NOTE theo [runbook §4](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md).
3. Cho phép chạy phần production SELECT-only của P6-00 khi thuận tiện.
4. Nếu muốn autopilot làm P6-00 (phần code) và bản nháp ADR P6-01..P6-03: prompt của scheduled task `decoupling-autopilot` hiện chỉ đọc P5 plan và bảng "Thứ tự" của nó, nên phải sửa prompt trỏ sang file này (giới hạn ở P6-00..P6-03, cấm P6-04 trở đi khi G6-D chưa đạt, và code chỉ ở nhánh `phase6/*` theo §3.3) rồi mới đổi `Trạng thái: RUN` trong [AUTOPILOT_LOG](./AUTOPILOT_LOG.md).
