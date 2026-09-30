# Phase 9 — điều tra phụ thuộc trước khi cắt tải

> Ngày: 2026-09-30. Chế độ: INVESTIGATE; phần lựa chọn thiết kế nằm trong [kế hoạch thực thi P9](../task/decoupling/P9_EXECUTION_PLAN_2026-09-30.md). Kiểm tra mã nguồn trong workspace; không kết nối production hoặc chạy migration. Số liệu production được dẫn từ tài liệu có sẵn, chưa được đo lại trong lần lập kế hoạch này.

## 1. Kết luận có thể dùng để lập kế hoạch

Ưu tiên thực thi theo chỉ đạo chủ sản phẩm: xác nhận chuyển đầy đủ sang NOTE, backup có thể phục hồi, rồi ngừng ghi song song và cắt giảm tài nguyên. Inventory dưới đây dùng để tìm và sửa phần NOTE còn thiếu trước cutover. NOTE readers/writers hiện vẫn dùng `card_progress` để xác minh tính toàn vẹn, nên phải gỡ phụ thuộc đó khi hoàn thiện đường NOTE. Cửa sổ wire cũ là cổng riêng, không chặn ngừng projection khi đủ bằng chứng. Khi lỗi, bổ sung từ backup vào NOTE và giữ dữ liệu mới theo kế hoạch P9; không duy trì projection cập nhật chỉ để quay LEGACY tức thời.

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

## 4. Những số đo được sử dụng và giới hạn

[P5-11](../task/decoupling/P5-11_NOTE_PRODUCTION_HARDENING.md) ghi các tối ưu đã có: open 1.000 Note còn 46 SQL, materialize 3.000 pristine Note còn 164 SQL, reader Browse/MCP đã gom truy vấn. [P7 runbook](../runbooks/P7_SESSION_RETENTION_RUNBOOK.md) ghi lần dọn đầu 15.072 membership. [Readiness](../task/decoupling/P8_P9_READINESS_2026-09-30.md) ghi 18/18 learner NOTE và 40.668 CardProgress.

Đây là **bằng chứng lịch sử**, khác môi trường và workload; không cộng các phần trăm cải thiện, không dùng làm SLO hiện tại. Báo cáo tải 29/09 mô tả nhiều lỗi đã được P5-11 sửa, nên P9-00 phải đo lại trên cùng release trước khi chọn ưu tiên.

## 5. Việc còn phải xác minh

1. Release/schema/env đang chạy, tài nguyên VPS, SQL/p95/locks/bytes trên workload hiện tại.
2. Toàn bộ reader/writer/callsite của projection, availability, contributors, history và old wire; mỗi mục có owner và replacement.
3. Readiness trong bootstrap read-only; telemetry không đếm thiếu khi deploy/restart hoặc log bị mất.
4. Bằng chứng phục hồi không mất commit mới sau thời điểm backup; backup cũ tự nó chưa đáp ứng RPO=0.
5. DDL từng bảng trên đúng MySQL production. Online DDL vẫn có metadata lock; FK CASCADE/SET NULL có thể hạn chế lựa chọn `LOCK`. Không khẳng định toàn bộ contraction chạy không downtime trước rehearsal. [MySQL 8.0 online DDL limitations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-limitations.html).
