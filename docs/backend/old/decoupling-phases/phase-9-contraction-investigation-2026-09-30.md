# Phase 9 — điều tra phụ thuộc trước khi cắt tải

> Ngày: 2026-09-30. Chế độ: INVESTIGATE; phần lựa chọn thiết kế nằm trong [kế hoạch thực thi P9](../task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md). Kiểm tra mã nguồn trong workspace; không kết nối production hoặc chạy migration. Số liệu production được dẫn từ tài liệu có sẵn, chưa được đo lại trong lần lập kế hoạch này.

## 1. Kết luận có thể dùng để lập kế hoạch

Ưu tiên thực thi theo chỉ đạo chủ sản phẩm: xác nhận chuyển đầy đủ sang NOTE, backup có thể phục hồi, rồi ngừng ghi song song và cắt giảm tài nguyên. Inventory dưới đây dùng để tìm và sửa phần NOTE còn thiếu trước cutover. NOTE readers/writers hiện vẫn dùng `card_progress` để xác minh tính toàn vẹn, nên phải gỡ phụ thuộc đó khi hoàn thiện đường NOTE. Cửa sổ wire cũ là cổng riêng, không chặn ngừng projection khi đủ bằng chứng. Khi lỗi, bổ sung từ backup vào NOTE và giữ dữ liệu mới theo kế hoạch P9; không duy trì projection cập nhật chỉ để quay LEGACY tức thời. Ba phụ thuộc dễ bị bỏ sót khi cắt: fence Connect/Anki lưu revision CardProgress (F9-06), đường vào LEGACY phụ thuộc env (F9-07) và audit deploy so với projection (F9-08).

Runtime thực tế là `wsgi.py -> create_app() -> build_app_config() / run_startup_maintenance()`. Config và maintenance hiện nằm trong [settings](../../app/settings.py) và [startup](../../app/startup.py); không còn toàn bộ inline như một số hướng dẫn cũ. Production mặc định không chạy maintenance, nhưng env có thể bật; audit phải dùng bootstrap được kiểm chứng.

## 2. Hệ thống dữ liệu đang tồn tại

| Dữ liệu | Vai trò hiện tại | Phụ thuộc phải giữ hoặc thay thế |
|---|---|---|
| `study_progress_subjects`, `study_progress_states` | Identity learner/Note và current Algorithm State khi learner ở NOTE | Subject generation, Algorithm identity/schema/hash, progress sau reset/delete |
| `study_authority_subject_tokens`, enrollment | Fencing, authority revision/epoch | Chống ghi đè và worker/process dùng authority cũ |
| `card_progress` | NOTE → LEGACY projection; authority cho learner LEGACY | NOTE read validation, sibling write baseline, external/lifecycle paths, rollback |
| `study_progress_contributors` | Liên kết từng Card với subject và bằng chứng raw projection | `source_progress_id` NOT NULL; FK `live_card_progress_id -> card_progress.id` SET NULL; raw payload/revision/hash |
| `study_progress_availability` | Queue/due/burial/suspension phục vụ đọc và ordering | PK contributor; composite FK `(contributor_id, subject_id)` CASCADE; chưa độc lập với contributor |
| `review_events`, history facts, lineage/lifecycle | Lịch sử learner, provenance, Algorithm-switch input | History fact có FK nullable tới contributor SET NULL; lineage cần điều tra trước mọi purge |
| `study_session_cards`, authority pins | Snapshot và bằng chứng của lease | Pins cascade theo membership; active session/batch cần giữ |
| Session/command receipts, batches | Idempotency, accepted work, phục hồi sau mất ACK | Không thể coi là rác chỉ vì membership đã hết hạn |
| `study_applications`, Card, Connect refs | Presentation occurrence và external identity | Stable ordinal/binding, source-install/local context; không phải progress rác |

Nguồn: [migration applications 46](../../migrations/versions/20260930_000046_add_study_applications.py), [authority migration 40](../../migrations/versions/20260921_000040_add_study_authority_fence.py), [contributor](../../models/study_progress_contributor.py), [availability](../../models/study_progress_availability.py), [state](../../models/study_progress_state.py), [history fact](../../models/study_progress_history_fact.py), [session pin](../../models/study_session_authority_pin.py). DDL đang chạy phải được đối chiếu với migrations và schema thực trong P9-00; bảng trên không phải xác nhận schema production.

## 3. Các phát hiện

### F9-01 — Projection còn là phụ thuộc runtime của NOTE

- **Observed:** `apply_existing_state_note_review` dựng baseline cho sibling Cards, encode legacy projection, ghi state/projection rồi refresh evidence và history trong cùng transaction. Locking reader yêu cầu đủ CardProgress/contributor/availability; analytics reader cũng join CardProgress và kiểm revision/linkage.
- **Evidence:** [command service](../../app/services/study_authority_command_service.py), [write service](../../app/services/study_authority_write_service.py), [authority repository](../../app/repositories/study_authority_repository.py), [read service](../../app/services/study_authority_read_service.py), [analytics repository](../../app/repositories/note_analytics_read_repository.py).
- **Potential concern:** Ngừng ghi projection làm evidence cũ, hoặc Note mới không thể materialize vì contributor cần source progress identity. Bỏ validator đơn thuần sẽ làm mất kiểm tra sai lệch.
- **Impact:** Commit/read có thể lỗi `INCOMPLETE_AUTHORITY_COMPATIBILITY`/`AUTHORITY_READ_PARITY_DIVERGED`, hoặc chấp nhận state không còn được xác minh.
- **Unknowns:** Chi phí projection còn lại trên release production hiện hành; inventory đầy đủ mọi writer và consumer chưa được hoàn tất.

### F9-02 — Snapshot lớn còn tồn tại; NOTE rollover đã tái sử dụng lease

- **Observed:** Mở phiên tải toàn phạm vi đến `MAX_SESSION_CARDS = 5000`, materialize pristine Notes, rồi tạo snapshot/membership/pins. Frontend có nhánh `usesNoteBatchTransport` trả về sau `flushNoteBatchStream`; nhánh mở lại snapshot nằm ở transport cũ.
- **Evidence:** [session service](../../app/services/study_session_service.py), [hook](../../frontend/src/features/study/hooks/useStudySession.ts), test `continues the same NOTE lease after rollover and preserves its stats through empty finalization` trong [hook tests](../../frontend/src/features/study/hooks/useStudySession.test.tsx).
- **Potential concern:** Câu “SPA mở lại mỗi 50 câu” trong tài liệu P5-11 không đúng cho nhánh NOTE batch hiện tại. Đặt backlog sửa lại rollover sẽ lặp việc đã làm.
- **Impact:** Cần đo và giảm snapshot lần mở đầu/reopen thật; không tăng batch 50 câu hoặc TTL chỉ để giảm tải.
- **Unknowns:** Tỷ lệ client production còn chạy transport cũ, kích thước snapshot và tần suất reopen thực tế.

### F9-03 — Retention đã có nhưng giới hạn theo phiên chưa giới hạn số dòng

- **Observed:** Service dùng `batch_sessions=200`, lấy toàn bộ candidate session IDs trước khi chia lô; đóng expired sessions bằng một UPDATE. Purge yêu cầu terminal status, cả `opened_at` và `expires_at` trước cutoff, không có batch `enqueued`. Runbook ghi timer hằng ngày chưa cài.
- **Evidence:** [retention service](../../app/services/study_session_retention_service.py), [CLI](../../app/cli.py), [runbook P7](../runbooks/P7_SESSION_RETENTION_RUNBOOK.md).
- **Potential concern:** 200 phiên × tối đa 5.000 membership có thể tới 1 triệu membership, chưa tính pins, trong một transaction. Lấy toàn bộ candidates cũng không có giới hạn bộ nhớ.
- **Impact:** Job “dọn tải” có thể tạo thêm tải lúc backlog lớn; chạy một lần không bảo đảm retention được duy trì.
- **Unknowns:** Backlog hiện hành, phân bố membership/phiên, thời gian từng transaction, lịch vận hành ngoài repo.

### F9-04 — Readiness v1 là tín hiệu sơ bộ, chưa chứng minh hết consumer cũ

- **Observed:** Report chỉ đếm enrollment, phiên mở trong cửa sổ, status `open`, Card/application binding và số CardProgress. Không đo actual legacy reads/writes, restore/retry, package/client versions hay accepted jobs. `connect_refs_without_card` có trong evidence nhưng chưa tham gia biểu thức quyết định ordinal `ready`.
- **Evidence:** [readiness service](../../app/services/study_phase9_readiness_service.py), [tests](../../tests/test_study_phase9_readiness.py). Lệnh được đăng ký trong `register_cli_commands`, chưa có trong `register_audit_cli_commands`.
- **Potential concern:** Không có request telemetry không có nghĩa là không còn sử dụng. CLI body chỉ đọc không bảo đảm bootstrap app không ghi. Status `open` quá hạn cũng khác lease còn hợp lệ.
- **Impact:** Cần readiness v2 trước cutover; không tự rút `--window-days` để tạo kết quả xanh. Mốc 29/10 chỉ là dự kiến theo thời điểm mở phiên cũ đã ghi nhận.
- **Unknowns:** Timestamp UTC chính xác lần sử dụng cũ cuối, độ phủ log, policy với client offline/quarantine và job đang xử lý.

### F9-05 — Ordinal đã ổn định cho dữ liệu có binding; tên “legacy” không chứng minh code thừa

- **Observed:** `anki_sync_service._card_for_ord` dùng `application.source_ord` nếu có, còn fallback vị trí nếu không có binding. Application lặp mới có thể nhận `source_ord=None`. Registry hiện còn adapter `legacy-anki` dùng hàm scheduler; đó là Algorithm có version, không đồng nghĩa LEGACY storage.
- **Evidence:** [Anki sync](../../app/services/anki_sync_service.py), [application service](../../app/services/study_application_service.py), [Algorithm registry](../../app/services/study_algorithm_registry.py).
- **Potential concern:** Đếm mọi application thiếu ordinal có thể chặn cả occurrence native hợp lệ; ngược lại zero null không chứng minh fallback không còn được gọi khi import package mới.
- **Impact:** Chỉ bỏ fallback sau khi trace import/reimport/template reorder/delete; giữ engine/decoder còn được Algorithm hiện hành dùng, bốn rating của built-in và Field name bindings còn sống.
- **Unknowns:** Adoption phiên bản Connect, package cũ còn chờ import; inventory name-based binding và renderer chưa hoàn tất.

> F9-06..F9-10 bổ sung sau review kế hoạch P9 cùng ngày; cùng chế độ INVESTIGATE, chỉ đọc source.

### F9-06 — Fence Connect/Anki lưu revision CardProgress

- **Observed:** `connect_source_card_refs.applied_local_revision` lưu giá trị `CardProgress.revision`. Đường NOTE của Anki snapshot so `progress.revision` của sibling với giá trị này để phát hiện learner đã học local (`local_diverged`), dựng candidate từ các cột của dòng CardProgress rồi mới `map_card_progress` sang NOTE state, và ghi lại `applied_local_revision = progress.revision`. Connect import và reconciliation cũng so cùng cặp giá trị.
- **Evidence:** [Anki sync](../../app/services/anki_sync_service.py) (`_apply_note_authority_progress_snapshot`, các chỗ gán/so `applied_local_revision`), [Connect import](../../app/services/connect/import_cards.py), [reconciliation](../../app/services/study_progress_reconciliation_service.py), [model ref](../../models/connect_source_card_ref.py).
- **Potential concern:** Khi projection ngừng cập nhật, `CardProgress.revision` đứng yên dù learner tiếp tục học trên NOTE. `local_diverged` vẫn false, nên re-sync Anki (không `force`) ghi đè tiến độ NOTE mới mà không báo conflict. Card/Note chưa có dòng CardProgress thì đường này không dựng được input.
- **Impact:** Mất tiến độ learner im lặng sau cutover — vi phạm ràng buộc không mất dữ liệu. Cần đổi fence sang revision NOTE, xử lý giá trị đã lưu (khác ngữ nghĩa), và codec snapshot → NOTE state không qua dòng CardProgress trước P9-06.
- **Unknowns:** Số ref có `applied_local_revision` khác NULL trên production; tần suất người dùng re-sync Anki; revision NOTE nào (authority revision của subject, token hay cột mới) phù hợp nhất với ngữ nghĩa per-Card hiện tại.

### F9-07 — Đường vào LEGACY còn mở

- **Observed:** `enroll_new_learner_note_authority` chỉ enroll NOTE khi `STUDY_NEW_LEARNER_NOTE_ENABLED` và `STUDY_WIRE_V4_ENABLED` bật và `STUDY_ASYNC_BATCH_ENABLED` tắt; ngược lại hoặc khi enrollment bị từ chối, nó trả `None` và tài khoản ở LEGACY (chỉ ghi warning). Cả ba cờ mặc định `False`. Theo runbook P5, hai cờ đầu được sửa tay trong `/etc/flama/flama.env`, không thuộc key do `deploy/sync_managed_env.py` quản lý; cờ async do GitHub variable quản lý. CLI `study-authority-enrollment --mode LEGACY` và runbook P5 §4.5 (rollback NOTE → LEGACY, đặt `STUDY_NEW_LEARNER_NOTE_ENABLED=0`) vẫn còn.
- **Evidence:** [enrollment service](../../app/services/study_authority_enrollment_service.py), [settings](../../app/settings.py), [auth](../../app/services/auth_service.py), [Google auth](../../app/services/google_auth_service.py), [CLI](../../app/cli.py), [runbook P5](../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md).
- **Potential concern:** Sau cutover, một lần lệch env (mất dòng khi sửa file, bật async) tạo learner LEGACY mới: CardProgress lại là authority của learner đó, counters “zero INSERT/UPDATE projection” sai, và dọn code LEGACY ở P9-09/P9-10 làm hỏng tài khoản đó. Rollback NOTE → LEGACY sau cutover tự từ chối nhờ `_verify_lossless_legacy_projection` (projection cũ/thiếu → `LOSSY_LEGACY_PROJECTION`/`INCOMPLETE_AUTHORITY_COVERAGE`), nhưng đó là fail-closed ngẫu nhiên, không phải chính sách.
- **Impact:** “100% learner ở NOTE” hiện là trạng thái phụ thuộc env, không phải invariant. Cần signup NOTE vô điều kiện, khóa CLI LEGACY và sửa runbook (P9-05c, D9-09).
- **Unknowns:** Giá trị env thực tế hiện hành trên production; có kế hoạch bật async batch trước khi Phase 9 hoàn tất hay không.

### F9-08 — Audit deploy dựa vào projection

- **Observed:** `study-authority-read-audit` (“Compare canonical NOTE queue semantics with the rollback projection”) và `study-architecture-audit` là nguồn kết quả “audit 18/18 PASS” trong runbook P5/P6 và sau mỗi deploy P5-11. `study_architecture_audit_service.py` có hơn 100 tham chiếu CardProgress. Readiness v1 vẫn ghi gate `legacy_projection_writes` là `decision` với blocker D6-02.
- **Evidence:** [CLI](../../app/cli.py), [architecture audit](../../app/services/study_architecture_audit_service.py), [readiness](../../app/services/study_phase9_readiness_service.py), [P5 runbook](../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md).
- **Potential concern:** Sau cutover, audit hiện tại hoặc báo lệch (projection đứng yên) hoặc bị bỏ qua, nên deploy mất gate an toàn chính đúng lúc hệ thống thay đổi nhiều nhất.
- **Impact:** Audit canonical thay thế phải có, được kiểm trên production khi projection còn cập nhật, và vào runbook trước P9-06 (P9-04 §4–5). Readiness cập nhật theo D9-02 (P9-02a).
- **Unknowns:** Những invariant nào của audit hiện tại chỉ có thể kiểm qua projection và cần công thức thay thế.

### F9-09 — Nhiều writer CardProgress là nhánh LEGACY-only

- **Observed:** Các constructor `CardProgress(...)` trong direct review (`study_service.py`), session commit (`study_session_service.py`), worker (`study_worker_service.py`), Connect import (`connect/import_cards.py`) và Anki (`anki_sync_service.py`) nằm sau nhánh `authority_route.mode_code == "NOTE"` đã return/rẽ sang đường NOTE, tức chỉ chạy cho learner LEGACY. Đường NOTE ghi projection tập trung ở authority command/write/evidence, pristine materialization, lifecycle mirror, Anki NOTE snapshot và các đường delete/reset (`deck_management_service`, `flashcard_content_service`, `study_note_template_service`, `study_content_delete_service`). Discovery learner khi xóa nội dung hợp nhất CardProgress với subject/contributor/session, nên không bỏ sót learner NOTE khi projection không còn dòng mới.
- **Evidence:** các file trên; [content delete](../../app/services/study_content_delete_service.py) `discover_content_learner_ids`.
- **Potential concern:** Nếu P9-05 port mọi callsite CardProgress, phạm vi và ước lượng bị thổi phồng; nếu bỏ sót phân loại, một nhánh NOTE thật có thể bị coi là LEGACY.
- **Impact:** P9-00 phải phân loại callsite (đường NOTE / LEGACY-only / cleanup lifecycle / startup-schema). Nhánh LEGACY-only chỉ cần chặn (P9-05c) rồi xóa (P9-09).
- **Unknowns:** Danh sách cuối từ trace entrypoint thực, không từ grep.

### F9-10 — Startup có thể tái tạo storage đã drop

- **Observed:** Startup maintenance gọi `db.create_all()` sau khi import models; `app/startup_schema.py` còn nhiều patch liên quan `card_progress`.
- **Evidence:** [startup](../../app/startup.py), [startup schema](../../app/startup_schema.py).
- **Potential concern:** Drop bảng khi model còn trong metadata thì lần boot có maintenance bật tạo lại bảng rỗng; patch cột cũ có thể chạy trên schema đã contract.
- **Impact:** P9-10 phải gỡ model khỏi metadata và gỡ patch trong release chạy trước DDL, rồi boot `wsgi.py` với maintenance bật để chứng minh.
- **Unknowns:** Env production có bật maintenance ở lần boot nào không; thứ tự import models khi gỡ.

## 4. Những số đo được sử dụng và giới hạn

[P5-11](../task/decoupling/P5-11_NOTE_PRODUCTION_HARDENING.md) ghi các tối ưu đã có: open 1.000 Note còn 46 SQL, materialize 3.000 pristine Note còn 164 SQL, reader Browse/MCP đã gom truy vấn. [P7 runbook](../runbooks/P7_SESSION_RETENTION_RUNBOOK.md) ghi lần dọn đầu 15.072 membership. [Readiness](../task/decoupling/P8_P9_READINESS_2026-09-30.md) ghi 18/18 learner NOTE và 40.668 CardProgress.

Đây là **bằng chứng lịch sử**, khác môi trường và workload; không cộng các phần trăm cải thiện, không dùng làm SLO hiện tại. Báo cáo tải 29/09 mô tả nhiều lỗi đã được P5-11 sửa, nên P9-00 phải đo lại trên cùng release trước khi chọn ưu tiên.

## 5. Việc còn phải xác minh

1. Release/schema/env đang chạy, tài nguyên VPS, SQL/p95/locks/bytes trên workload hiện tại.
2. Toàn bộ reader/writer/callsite của projection, availability, contributors, history và old wire; mỗi mục có owner và replacement.
3. Readiness trong bootstrap read-only; telemetry không đếm thiếu khi deploy/restart hoặc log bị mất.
4. Bằng chứng phục hồi không mất commit mới sau thời điểm backup; backup cũ tự nó chưa đáp ứng RPO=0.
5. Env authority thực tế trên production (F9-07), số ref Connect có `applied_local_revision` (F9-06), hạ tầng backup/binlog và thời gian dump/restore với dữ liệu hiện tại.
6. DDL từng bảng trên đúng MySQL production. Online DDL vẫn có metadata lock; FK CASCADE/SET NULL có thể hạn chế lựa chọn `LOCK`. Không khẳng định toàn bộ contraction chạy không downtime trước rehearsal. [MySQL 8.0 online DDL limitations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-limitations.html).
