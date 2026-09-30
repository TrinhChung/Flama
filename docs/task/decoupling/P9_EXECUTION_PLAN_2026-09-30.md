# Kế hoạch thực thi Phase 9 — cắt lớp tương thích, giảm tải hệ thống

> Lập 2026-09-30 theo yêu cầu chuẩn bị kế hoạch chi tiết, ưu tiên giảm tải sớm. **Trạng thái: kế hoạch; chưa triển khai code, migration hoặc thay đổi production.** Nguồn: [canonical Phase 9](../../architecture/study-interaction-trigger-algorithm-plan.md#phase-9--contract-old-storage-and-compatibility-code), [điều tra code hiện tại](../../architecture/phase-9-contraction-investigation-2026-09-30.md), [readiness P8/P9](./P8_P9_READINESS_2026-09-30.md).
>
> **Bổ sung sau review (2026-09-30):** thêm phát hiện [F9-06..F9-10](../../architecture/phase-9-contraction-investigation-2026-09-30.md#f9-06--fence-connectanki-lưu-revision-cardprogress) — fence Connect/Anki lưu revision CardProgress (nguy cơ ghi đè im lặng), đường vào LEGACY còn mở, audit deploy phụ thuộc projection, phân loại writer LEGACY-only, startup tái tạo bảng. Kéo theo: quyết định D9-08/D9-09, tách P9-02a/P9-02b, thêm P9-05b/P9-05c, gate và ma trận kiểm chứng tương ứng.

## 1. Hướng thực hiện

**Thứ tự đã được chủ sản phẩm chốt: chuyển đầy đủ sang NOTE → backup có thể phục hồi → cắt ghi song song → cắt giảm Phase 9.** Khi có lỗi, bổ sung phần dữ liệu cần sửa từ backup vào hệ NOTE hiện hành, bảo toàn dữ liệu mới đã ghi. Đây là nguyên tắc thực thi đã chốt; trạng thái hoàn tất từng bước vẫn phải có bằng chứng thực tế.

Phase 8 không phải điều kiện tiên quyết. Retention, tối ưu snapshot và dọn code được xếp sau việc bảo đảm NOTE đầy đủ và cắt ghi song song; không để các việc phụ này kéo dài thời gian duy trì hai đường ghi.

| Mốc | Kết quả cần đạt | Có phải đợi hết cửa sổ wire cũ? |
|---|---|---|
| **P9-A: hoàn tất NOTE không phụ thuộc projection, rồi xác nhận** | Mọi learner, dữ liệu, reader/writer, worker và luồng tạo mới có coverage NOTE đầy đủ, chạy được khi không có projection; không còn đường vào LEGACY; phần còn thiếu được bổ sung trước | Không |
| **P9-B: backup rồi ngừng ghi song song** | Backup trước cutover đã thử phục hồi; mọi ghi mới đầy đủ vào NOTE, ngừng tạo/cập nhật projection trên toàn hệ thống | Không đợi wire retirement; xử lý xong work phụ thuộc profile cũ trước khi chuyển |
| **P9-C: cắt giảm tài nguyên** | Dọn runtime/code/storage cũ, retention và snapshot theo ưu tiên đo được; lỗi thì bổ sung từ backup, giữ dữ liệu NOTE mới | Wire removal có gate riêng, không chặn cắt ghi song song |

Đường găng: **P9-00 → P9-02a → P9-03 → P9-04 → P9-05 + P9-05b + P9-05c → xác nhận FULL_NOTE_PASS → backup/restore proof → P9-06**. P9-02a là phần của P9-02 cần cho cutover (counters đọc/ghi projection, kiểm drain job/lease, invariant 0 learner LEGACY); P9-02b (telemetry wire/package/ordinal) phục vụ P9-08, không chặn cutover và không đợi cửa sổ 30 ngày. P9-01/P9-07/P9-08/P9-09/P9-10 tiếp sau, theo mức giảm tài nguyên và độ sẵn sàng.

P9-A **không chỉ là bước xác nhận**: G9-WRITE yêu cầu mọi luồng chạy đúng khi không có projection, nên P9-A bao gồm phần code lớn nhất (P9-03..P9-05c). Báo cáo tiến độ không coi P9-A là việc kiểm đếm.

### Bằng chứng bắt buộc trước khi cắt ghi song song

| Gate | Điều phải chứng minh | Không đủ để kết luận |
|---|---|---|
| **G9-FULL: FULL_NOTE_PASS** | Toàn bộ learner hiện tại + new-user default ở NOTE; **không còn đường tạo hoặc chuyển learner sang LEGACY** (F9-07); dữ liệu chuyển đủ theo identity/generation/state/history, mọi reader/writer và lifecycle có đường NOTE; binaries/worker đồng bộ; old jobs/leases có disposition | Chỉ thấy 18/18 enrollment NOTE hoặc số dòng hai bên bằng nhau; new-user NOTE chỉ đúng vì env đang bật cờ |
| **G9-WRITE: ghi NOTE đầy đủ** | Direct REST/MCP, session/batch/worker, import/sync, tạo Note/pristine, reset/switch/delete đều commit trọn bộ dữ liệu NOTE; fence Connect/Anki dùng revision NOTE (F9-06); lỗi/retry không mất hoặc nhân đôi dữ liệu; test không có projection vẫn chạy đúng | Chỉ lưu state nhưng thiếu availability, history, revision hoặc receipt; re-sync Anki không phát hiện học local |
| **G9-BACKUP: có bản phục hồi** | Backup nhất quán trước cutover, manifest/checksum/schema/identity mapping, thời điểm T0 và watermark; restore vào DB cách ly thành công; có cách giữ/khôi phục writes sau T0 | Có file dump nhưng chưa thử phục hồi hoặc không biết khoảng dữ liệu bị thiếu |
| **G9-CUT: đã cắt thật** | Sau cutover, mọi ghi mới chỉ cập nhật hệ NOTE; SQL counters không còn INSERT/UPDATE projection, receipts đối chiếu được với state/history đã commit; audit canonical thay thế (F9-08) PASS toàn bộ learner | Tắt một API nhưng MCP/worker/import vẫn ghi song song; audit cũ báo lệch vì projection đứng yên rồi bị bỏ qua |

“Ghi đầy đủ vào NOTE” là toàn bộ hệ progress theo Note: subject/state/token, availability/provenance cần thiết, ReviewEvent/history và receipt trong transaction tương ứng; không phải chép progress vào bảng nội dung `notes`. Kiểm cả ghi mới và cập nhật/reset/xóa, không chỉ answers.

Không lấy số dòng code xóa làm thước đo thành công. Đo SQL/answer, row writes/answer, thời gian transaction, p95, bộ nhớ và tăng trưởng membership/ngày.

## 2. Hiện trạng đã đối chiếu

| Hạng mục | Kết luận dùng cho kế hoạch |
|---|---|
| P5/P6/P7 | Tracker ghi đã chạy production; 18/18 learner NOTE, 0 user chưa enroll ở lần đo 30/09. Phải xác minh lại tại P9-00 |
| Projection | `study_authority_command_service.py` vẫn encode/ghi CardProgress; reader và analytics vẫn kiểm linkage/revision. Tắt ghi ngay sẽ phá invariant |
| Cờ shadow | `STUDY_PROGRESS_SHADOW_WRITE_ENABLED` không phải công tắc ngừng NOTE → CardProgress. Không dùng cờ này để thực hiện P9 |
| Snapshot | Mở phiên còn tải toàn scope, tối đa 5.000 Cards; pristine materialization đã được gom lô trong P5-11 |
| Rollover | NOTE batch đã tiếp tục cùng lease. Chỉ transport cũ có nhánh mở snapshot lại; giữ test hiện có, không lập task làm lại |
| Retention | Có CLI, đã dọn 15.072 membership theo runbook. Chưa có timer trong repo; default thực tế 200 phiên/lô, không phải 500 |
| Wire cũ | Report lịch sử có 363 phiên v2 trong 30 ngày, lần mở cuối 29/09 00:51. 29/10 là mốc dự kiến theo dữ liệu mở phiên, không phải giấy phép xóa |
| Ordinal | Stable occurrence có sẵn, positional fallback còn trong `anki_sync_service._card_for_ord`; gate hiện chưa đo actual fallback/package usage |
| Readiness | v1 chưa đủ gate cho contraction: thiếu runtime usage, jobs, observation coverage; báo `ready` ordinal chưa xét dangling refs; gate projection vẫn ghi blocker D6-02 dù D9-02 đã thay |
| Connect/Anki fence | `connect_source_card_refs.applied_local_revision` lưu `CardProgress.revision`; đường NOTE của Anki snapshot dựng input từ dòng CardProgress. Projection đứng yên thì re-sync ghi đè học local mà không báo (F9-06) |
| Đường vào LEGACY | Tài khoản mới rơi về LEGACY khi thiếu `STUDY_NEW_LEARNER_NOTE_ENABLED`/`STUDY_WIRE_V4_ENABLED` hoặc bật `STUDY_ASYNC_BATCH_ENABLED` (đều default `False`); CLI `--mode LEGACY` và runbook rollback P5 còn (F9-07) |
| Audit deploy | `study-authority-read-audit` và `study-architecture-audit` — nguồn “audit 18/18 PASS” — so NOTE với projection; sau cutover không còn gate deploy nếu chưa thay (F9-08) |
| Writer CardProgress | Nhiều constructor CardProgress nằm trong nhánh LEGACY (direct review, Connect import, session commit, worker, Anki); đường NOTE tập trung ở authority command/write/evidence, pristine, lifecycle mirror, Anki NOTE, delete/reset (F9-09) |
| Startup | `db.create_all()` tái tạo bảng đã drop nếu model còn import; `app/startup_schema.py` còn patch cột CardProgress (F9-10) |
| Backup | Runbook P5/P6 dùng `mysqldump --single-transaction` thủ công vào `/root`; chưa có bằng chứng binlog/PITR trong repo |

Các số production ở trên là số trong tài liệu, **không phải lần đo mới**. Điều tra F9-01..F9-10 ghi rõ code, ảnh hưởng và điểm chưa biết.

## 3. Invariants và phạm vi

1. Một current progress authoritative cho mỗi learner/Note; giữ exact Algorithm key/version/schema, generation, revision, hash và CAS.
2. Một accepted answer chỉ tạo một chuyển trạng thái và bộ history/receipt tương ứng; retry, mất ACK, worker crash không tạo review trùng.
3. Không purge `review_events`, `study_progress_history_facts`, current subjects/states/tokens, lifecycle/lineage evidence hoặc receipts trong đợt giảm tải này. Retention membership vẫn 30 ngày.
4. Template/Card/application là presentation; bỏ/reorder/nhân application không reset progress. Installed deck giữ logical overlay, không sửa source content.
5. Giữ timezone/day boundary, due counts theo Note, learning/relearning, new limit, suspension/burial và learn-ahead; dùng scheduler/repository hiện có.
6. Active lease và accepted job được xử lý theo contract đã cấp. Session/client cũ không được tự replay câu trả lời sang lease mới.
7. UI không redesign. Refactor transport/types giữ layout, rating built-in, accessibility và IndexedDB recovery.
8. Không drop bảng/cột chỉ vì tên có `legacy`, `shadow` hoặc `card`; mỗi removal có danh sách consumers bằng zero và replacement đã kiểm.
9. Từ P9-B, 0 learner LEGACY là invariant liên tục, không phải snapshot: không có đường tự động (signup, env lệch, cờ async) hay thủ công (CLI, runbook) đưa learner về LEGACY. Tính đúng không được phụ thuộc giá trị env sửa tay.
10. Fence đồng bộ ngoài (Connect/Anki) so với revision của hệ NOTE, không so với revision projection đã ngừng cập nhật.

Không mở rộng sang UUID PK migration, partitioning, đổi isolation level, thêm Algorithm/FSRS hay refactor toàn bộ Field/Template. Các việc đó không cần để cắt projection sớm.

## 4. Quyết định và thiết kế cần chốt trong triển khai

Chỉ đạo mới của chủ sản phẩm đã chốt thứ tự, việc bỏ ghi song song và cách phục hồi bằng bổ sung backup. Các thông số kỹ thuật còn lại được chọn theo bằng chứng; không hỏi lại quyết định đã chốt.

| ID | Đề xuất | Hệ quả và lúc cần chốt |
|---|---|---|
| D9-01 | **ĐÃ CHỐT:** full NOTE → backup → cắt ghi song song → giảm tài nguyên | Thay thứ tự ưu tiên retention trước trong bản kế hoạch đầu |
| D9-02 | **ĐÃ CHỐT:** NOTE giữ dữ liệu mới; có lỗi thì bổ sung từ backup vào NOTE | Thay yêu cầu D6-02 giữ projection luôn cập nhật để quay LEGACY tức thời; không đặt lại câu hỏi có bỏ rollback LEGACY hay không |
| D9-03 | Giữ quan sát wire tối thiểu 30 ngày; phân biệt executable retirement, receipt/history decoder và detail retention | Chốt trong P9-02b. Không giảm ngày chỉ để report xanh |
| D9-04 | Ưu tiên thay đổi ít schema ở P9-B, chưa gom mọi availability về một bảng mới | ADR P9-03 phải chứng minh writer cho cả Note mới không tạo CardProgress |
| D9-05 | Retention định kỳ, có row/time budget và một runner; giữ cửa sổ 30 ngày | Chốt lịch vận hành trước bật timer P9-01; đề xuất daily ngoài giờ cao điểm theo số liệu traffic |
| D9-06 | Snapshot giới hạn/refill là thay đổi contract riêng | Chốt offline coverage/learn-ahead trước P9-07; không tự giảm `MAX_SESSION_CARDS` |
| D9-07 | Mỗi destructive migration có manifest cụ thể, backup/restore proof và reconciliation | Chuẩn bị đầy đủ trước apply; chỉ đạo cắt giảm không cho phép đè dữ liệu NOTE mới bằng backup cũ |
| D9-08 | **Mặc định cắt một lần cho toàn hệ thống trong write freeze ngắn**, không xây cơ chế cohort/storage profile theo learner. Lý do: 18 learner; P5 plan ghi 29/09 production chưa có người dùng thật và đã bỏ canary vì vậy. Cờ/epoch cutover lưu trong DB, đọc dưới fence enrollment/epoch hiện có, không thêm authority mode mới nếu không cần | Xác minh lại quy mô và người dùng thật ở P9-00. Chỉ quay lại cohort nếu số liệu cho thấy freeze không chấp nhận được; khi đó ghi rõ lý do và thời hạn duy trì hai đường |
| D9-09 | Tài khoản mới vào NOTE **vô điều kiện**: không enroll được thì signup báo lỗi, không rơi về LEGACY; bỏ ràng buộc với `STUDY_ASYNC_BATCH_ENABLED`/cờ env. CLI `--mode LEGACY` và runbook rollback P5 bị gỡ/khóa | Phần signup làm sớm (P9-05c), không phụ thuộc P9-03. Gỡ CLI LEGACY chậm nhất tại P9-06; nhất quán với D9-02 (không quay LEGACY) |

### Hai phương án tách projection

| Phương án | Lợi ích | Chi phí/rủi ro | Đề xuất |
|---|---|---|---|
| **A. Giữ liên kết presentation/contributor và availability hiện có; tách evidence canonical khỏi snapshot legacy** | Ít đổi query shape, FK/history identity ổn định; cắt CardProgress writes sớm hơn | Cần evidence/storage profile mới, xử lý `source_progress_id NOT NULL`, raw legacy fields và reader validation; vẫn còn amplification availability theo Card | Ưu tiên ADR đánh giá để làm P9-B |
| **B. Availability theo subject, presentation mapping độc lập; contributor chỉ còn provenance lịch sử** | Có thể giảm thêm writes theo số sibling | Thay đổi rộng queue/order, topology, history/Connect và backfill; nhiều migration và compatibility hơn | Đợt sau nếu số đo chứng minh A chưa đủ |

Không nhét state mới vào JSON tùy ý để né constraint; giữ typed state codec/hash và relational identity. Không dùng ID giả để đáp ứng `source_progress_id`. ADR chọn physical schema sau inventory, xác định rõ dữ liệu cũ nào bất biến, dữ liệu mới nào cập nhật, và migration expand/backfill cần thiết.

**Cách rẻ nhất cho phương án A, ADR phải đánh giá trước:** giữ `encode legacy projection → map_card_progress` như hàm thuần trong bộ nhớ để tính availability/hash (đây chính là “adapter hiện hành” ở P9-03 §1), chỉ bỏ lock và INSERT/UPDATE bảng `card_progress`. Availability giữ nguyên ngữ nghĩa và code cũ trở thành oracle cho parity. Phần buộc đổi schema là các cột contributor chỉ có nghĩa khi có dòng CardProgress thật:

| Cột/ràng buộc | Hiện trạng | Việc ADR phải chốt |
|---|---|---|
| `source_progress_id` | NOT NULL, thuộc unique `uq_sp_contributor_generation_source (subject_id, subject_generation, source_progress_id)` | Cho phép NULL với contributor sinh sau cutover; MySQL cho nhiều NULL trong unique, nên phải có unique thay thế theo khóa logic (ví dụ subject/generation/`logical_card_key`) trước khi nới |
| `card_progress_revision`, `raw_schema_version`, `storage_codec`, `raw_payload*`, `raw_progress_hash` | NOT NULL, CHECK size/hash | NULL hoặc giữ giá trị lịch sử theo một cột phân loại evidence mới, có CHECK ràng buộc cặp. Không tái dùng `pointer_status` (mô tả con trỏ ReviewEvent) |
| `live_card_progress_id` | FK SET NULL, unique | Contributor mới để NULL; dòng cũ giữ đến P9-10 |

Contributor/availability cũ giữ nguyên giá trị lịch sử; chỉ dòng mới dùng evidence profile mới. Migration là expand (nới NOT NULL, thêm cột/unique) trước code cutover.

## 5. Backlog có thể thực thi

Ước lượng là ngày công tập trung gồm code/test/review, chưa tính thời gian quan sát và cửa sổ production. Owner là vai trò/file ownership, không phải yêu cầu tự mở nhiều agent.

| ID | Công việc và owner | Phụ thuộc | Ước lượng |
|---|---|---|---|
| P9-00 | Inventory và baseline hiện hành — Backend/Ops | Không | 0,5–1 ngày |
| P9-01 | Retention có giới hạn và vận hành định kỳ — Backend/Ops | P9-06; có thể chuẩn bị code sớm nhưng không chặn cutover | 1–2 ngày |
| P9-02a | Readiness v2 phần cutover: counters đọc/ghi projection, drain job/lease, invariant 0 learner LEGACY — Backend | P9-00 | 0,5–1 ngày |
| P9-02b | Readiness v2 phần retirement: wire/package/ordinal/restore telemetry — Backend/Connect/Frontend | P9-00; không chặn cutover | 1 ngày |
| P9-03 | ADR NOTE không phụ thuộc projection, expand schema nếu cần — Backend/Database | P9-00 + P9-02a | 1–2 ngày |
| P9-04 | Tách toàn bộ NOTE readers và audit canonical thay thế — Backend | P9-03 | 2–3 ngày |
| P9-05 | Tách toàn bộ NOTE writers/lifecycle, recovery — Backend/Database | P9-03, P9-04 | 3–5 ngày cho đường NOTE **sau khi** P9-00 tách nhánh LEGACY-only; lifecycle mirror và delete/reset có thể vượt ước lượng |
| P9-05b | Fence và codec Connect/Anki không qua CardProgress, xử lý `applied_local_revision` đã lưu — Backend/Connect/Database | P9-03 | 1–2 ngày |
| P9-05c | Đóng đường vào LEGACY: signup NOTE vô điều kiện, gỡ ràng buộc async/env, khóa CLI `--mode LEGACY`, sửa runbook P5 — Backend/Ops | P9-00; phần signup làm ngay được | 0,5 ngày |
| P9-06 | Backup/restore proof rồi ngừng projection toàn hệ thống — Ops/Backend | G9-FULL, G9-WRITE, G9-BACKUP; P9-03..05c | 1–2 ngày thao tác, tùy thời gian backup/restore và drain work thực tế |
| P9-07 | Giảm snapshot đầu phiên theo hợp đồng — Frontend/Backend | Baseline + D9-06 | 3–5 ngày, chỉ ưu tiên khi cần |
| P9-08 | Retire v2/v3 và positional Connect fallback theo từng gate — Backend/Frontend/Connect | P9-02b + đủ evidence từng nhóm | 1–2 ngày mỗi nhóm |
| P9-09 | Dọn generic rating/scheduler/renderer/name fallbacks — Backend/Frontend | Inventory + replacement từng mục | 1–3 ngày mỗi nhóm |
| P9-10 | Archive/drop storage cũ — Database/Ops | P9-06 ổn định + zero consumers + D9-07 | 1–2 ngày chuẩn bị mỗi migration, DDL tùy rehearsal |
| INT-06 | Tổng kết từng mốc P9-A/B/C, tracker và runbook | Các gate tương ứng | 0,5 ngày mỗi mốc |

Ước lượng trên dùng để chia việc, không phải thời gian chờ bắt buộc. Tái sử dụng bằng chứng và code đã có; tập trung xử lý khoảng trống NOTE thực sự còn lại. Không trì hoãn cắt ghi song song để hoàn thiện retention, telemetry wire 30 ngày hoặc chờ 72 giờ/7 ngày cố định do bản kế hoạch đầu đề xuất. Thực hiện cutover khi các gate kỹ thuật đã đạt.

### P9-00 — Inventory + baseline

**Output:** inventory CSV/Markdown và JSON benchmark gắn release SHA, schema revision, MySQL version, flags, hardware, giờ UTC. Mỗi callsite có entrypoint, reader/writer, transaction owner, bảng đọc/ghi, mode, replacement, test và evidence usage.

- Trace REST direct, MCP review/count/queue, session open/commit/batch/worker/status/retry, Anki snapshot/revlog/import, Algorithm switch, reset/suspend/bury, create Note/pristine, Template/application add/delete, admin/deck/NoteType delete, clone rekey và CLI seed/backfill.
- Trace reads dashboard/stats/Browse/admin/Connect export; phân biệt history-only reader với current progress reader.
- Chụp schema thực: FK vào CardProgress/contributor, constraints/indexes, Alembic head; đối chiếu ORM. Không sửa migration lịch sử.
- Đo đồng thời DB + Python CPU + payload: SQL count, rows written từng bảng, transaction/lock duration, p50/p95/p99, 5xx/409/429, pool wait, bytes, worker RSS, rows/ngày.
- Baseline sau P5-11 hiện hành; không dùng deadlock/22 giây của release cũ như tình trạng đang tồn tại.
- Phân loại mỗi callsite `CardProgress`/contributor theo một trong bốn nhóm: **đường NOTE** (phải chuyển ở P9-04/05/05b), **LEGACY-only** (chỉ cần chặn bằng P9-05c rồi xóa ở P9-09, không port), **cleanup lifecycle** (xóa projection lịch sử khi xóa nội dung, báo riêng như P9-05), **startup/schema** (xử lý ở P9-10). Điểm xuất phát đã thấy ở F9-09; danh sách cuối lấy từ trace, không từ grep.
- Chụp env thực tế liên quan authority (`/etc/flama/flama.env` và key do `deploy/sync_managed_env.py`/GitHub variables quản lý): `STUDY_WIRE_V4_ENABLED`, `STUDY_NEW_LEARNER_NOTE_ENABLED`, `STUDY_ASYNC_BATCH_ENABLED`, `STUDY_PROGRESS_SHADOW_*`, `STUDY_NOTE_COUNT_ENABLED`.
- Chụp hạ tầng backup thật: công cụ dump, nơi lưu, thời gian dump/restore với dữ liệu hiện tại, `log_bin`/`binlog_format`/`binlog_expire_logs_seconds`. Không giả định có PITR.
- Xác minh lại số learner và việc production đã có người dùng thật hay chưa để chốt D9-08.

**Gate:** không còn learner/dữ liệu/writer/read path chưa phân loại; lập danh sách thiếu hoặc lệch NOTE cụ thể và sửa/backfill có kiểm chứng trước G9-FULL. Nếu tải đang quá cao, tạm dừng job nền nặng theo §8 để hoàn tất việc chuyển NOTE; không biến tối ưu retention thành điều kiện chặn cutover.

### P9-01 — Retention không gây thêm quá tải

**Files:** `app/services/study_session_retention_service.py`, `app/cli.py`, tests/probe P7, runbook P7; timer/service mới dưới `deploy/` là output dự kiến.

1. Giữ đúng eligibility hiện hành: terminal session, opened và expires trước cutoff 30 ngày, không accepted/nonterminal batch. Kiểm mọi trạng thái queue/worker thật, không chỉ suy từ số batch bằng zero.
2. Thay việc lấy toàn bộ candidate IDs bằng keyset page. Expire stale sessions cũng chia lô.
3. Đặt giới hạn membership/pins thực tế mỗi transaction, không chỉ số session; đề xuất khởi điểm 1.000 membership/lô, tối đa 60 giây một lượt chạy, điều chỉnh bằng probe. Session lớn được chia membership, khóa và kiểm lại eligibility trước mỗi lô.
4. Resume/idempotent qua partial cleanup; receipts/history giữ nguyên; một runner, bounded pause giữa lô, dừng job khi chạm ngưỡng tải §8.
5. Dry-run đếm theo page, output counts + thời gian/row budget; timer chỉ chạy sau lần manual đạt và policy được chốt. Ghi ngày chạy thành công, backlog và lỗi.

**Gate:** ngắt tiến trình giữa hai lô rồi chạy lại không mất history/receipt; active lease/jobs nguyên vẹn; transaction p95 mục tiêu < 1 s trên workload nghiệm thu. Nếu một membership có payload lớn làm vượt budget, giảm lô.

**Giảm tải trong lúc chưa có code mới:** dùng dry-run hiện có để biết backlog và kích thước phiên; nếu chạy maintenance đã được cho phép, dùng lô nhỏ như runbook lần đầu. `--batch-sessions 1` vẫn có thể chứa 5.000 membership, không coi là hard row cap. Không rút retention xuống 2 ngày chỉ vì CLI cho phép.

**Rollback:** tắt timer/revert code; membership đã purge chỉ khôi phục từ backup. Không cần khôi phục để tính stats vì history được giữ.

### P9-02 — Readiness v2 (P9-02a cutover, P9-02b retirement)

**Files:** `study_phase9_readiness_service.py`, registration CLI, middleware/service counters cần thiết, restore/version telemetry frontend, Connect entrypoints và tests.

**P9-02a — nằm trên đường găng cutover:**

- Đưa command vào audit app surface, bắt buộc không chạy startup maintenance và dùng read-only transaction/credential cho production scan. Test SQL side effects qua entrypoint thật.
- Mỗi gate trả `status`, `blocking_reasons`, window start/end, last-use UTC, observation coverage, counts và samples không chứa answer/token/nội dung Note. Thêm `unknown` khi thiếu log/coverage; không biến unknown thành zero.
- Đếm legacy current reads, projection writes theo entrypoint và rollback commands; valid leases, enqueued/processing/recoverable jobs.
- Phân biệt expired-open với lease hợp lệ. Drain dựa expiry + processing deadline + safety margin, không chỉ status hoặc tuổi session.
- Gate `legacy_projection_writes` bỏ blocker D6-02/status `decision` hiện có; thay bằng điều kiện kỹ thuật theo D9-02: 0 learner LEGACY, 0 user chưa enroll, không đường vào LEGACY (F9-07), counters projection.

**P9-02b — phục vụ P9-08, không chặn cutover:**

- Old wire issuance/restore/commit/retry, package/client versions và positional fallback calls.
- Ordinal gate xét dangling refs có disposition rõ, chỉ yêu cầu source ordinal cho occurrence thuộc external mapping; kiểm duplicate/missing mapping và đường tạo dữ liệu mới.
- Cửa sổ tối thiểu 30 ngày cho wire theo D9-03; last-issued chỉ là proxy. Khi thiếu runtime telemetry cũ, không backdate observation. Bắt đầu tính từ khi có coverage hoặc chứng minh từ log đã giữ.

**Cơ chế ghi bằng chứng (cả a và b):** không ghi gì trên hot path. Chỉ ghi khi code đi vào nhánh legacy — một dòng log có cấu trúc (giữ qua logrotate/journald đủ cửa sổ) hoặc upsert DB theo `(gate, entrypoint, ngày)`. Nhánh này hiếm nên không tăng tải; nếu nó không hiếm thì chính điều đó là blocker. Counter trong process không dùng làm bằng chứng: Gunicorn nhiều worker và mất khi restart/deploy. Label giới hạn, không chứa answer/token/nội dung Note.

**Gate:** test cố ý tạo pending old job, expired-open, ref mất Card, native occurrence không ordinal, telemetry gap, late restore, learner LEGACY mới và signup khi cờ env lệch; report không báo xanh nhầm. Vẫn `destructive_steps_allowed=false`; quyết định migration nằm ngoài command.

### P9-03 — Hợp đồng canonical không phụ thuộc projection

**Output:** ADR + migration additive nếu cần + contract tests. Không tạo bảng mới trước khi giải quyết các mục sau:

1. Subject/state/token là current authority; availability được tính bằng adapter hiện hành, xác minh bằng generation/revision/hash mà không yêu cầu CardProgress. Đánh giá trước cách giữ `encode → map_card_progress` như hàm thuần trong bộ nhớ (§4, “Cách rẻ nhất cho phương án A”).
2. Tách historical contributor/raw provenance khỏi live evidence; giải quyết `source_progress_id` và unique `uq_sp_contributor_generation_source`, non-null raw fields, composite FK availability và history/lineage consumers. Note mới/overlay mới hoạt động mà không cần chèn CardProgress để lấy ID.
3. Freeze evidence/storage profile trong persisted state đọc dưới fence enrollment/epoch hiện có và trong session/job contract. Mọi process đọc cùng profile; request env flag riêng lẻ không đủ chống mixed-worker writes. Theo D9-08, mặc định là một cờ/epoch toàn hệ thống, không phải profile theo learner.
4. Cutover có fence/epoch hoặc contract version tương đương: không chuyển khi còn work của profile cũ. Nếu phải có wire mới, version rõ; không thay ngữ nghĩa v4 đã cấp.
5. Pre-cutover rehearsal bổ sung dữ liệu thiếu từ backup vào canonical NOTE; giữ identity mapping và metadata không suy ra được. Không giả định ReviewEvent/receipt riêng lẻ đủ tái tạo current state, không yêu cầu duy trì projection chỉ để rollback.
6. Registry `legacy-anki` và thuật toán đang dùng vẫn chạy; chỉ loại storage coupling/đường transaction trùng. CAS/history không phụ thuộc “bốn rating” của generic plumbing.
7. Fence Connect/Anki (F9-06): chọn revision NOTE thay cho `CardProgress.revision` trong `applied_local_revision` (ví dụ authority revision của subject hoặc cột mới có tên/ngữ nghĩa rõ), và cách xử lý giá trị đã lưu: migrate có ánh xạ chứng minh được, hoặc đánh dấu “cần xác nhận lại” để lần sync kế tiếp trả conflict thay vì ghi đè. Không để giá trị cũ được so với revision mới khác ngữ nghĩa. Codec Anki snapshot → NOTE state không dựng input từ dòng CardProgress.

**Gate:** reviewed design bao phủ tạo mới, sửa, delete/reset, switch, overlay, import, Anki/Connect re-sync, mất ACK và rollback. Có cách xử lý đúng cho Note không Card; không lờ validation hoặc tạo evidence giả để test xanh.

### P9-04 — Chuyển reader trước, còn giữ projection writer

**Files chính:** `study_authority_read_service.py`, `note_analytics_read_repository.py`, `study_repository.py`, session pins/snapshot, dashboard/Browse/stats/MCP và audit consumers đã tìm ở P9-00.

1. Reader mới theo persisted profile/epoch (D9-08: toàn hệ thống); code cũ chỉ giữ đến khi cutover xong, không duy trì song song theo cohort.
2. So cũ/mới trên cùng snapshot/timezone với projection còn cập nhật: state, due/new/relearn count, ordering, suspension/burial, scope authorization, overlay, admin và cardless Note.
3. Không chạy so sánh toàn bộ collection trên mỗi request production. Probe/offline audit hoặc sample có giới hạn; GET vẫn không materialize/khóa ghi cả scope.
4. **Audit canonical thay thế (F9-08)** cho `study-authority-read-audit` (`app/cli.py:391`) và `study-architecture-audit` (`study_architecture_audit_service.py`): kiểm invariant canonical (state/hash/token/generation, availability tính lại từ state bằng adapter so với dòng đã lưu, history/receipt) thay vì so với raw projection. Test corruption ở state/hash/availability/generation phải vẫn fail closed. Chạy được trên fixture không có projection.
5. Cập nhật runbook deploy dùng audit mới làm gate “N/N PASS” trước P9-06; audit cũ chỉ còn dùng cho so sánh parity trước cutover.

**Gate:** parity zero unexplained differences; SQL trace của reader profile mới không truy cập CardProgress; audit canonical PASS toàn bộ learner trên production (read-only) khi projection còn cập nhật, và PASS trên fixture không projection. Projection writer còn chạy nên có thể rollback reader an toàn.

### P9-05 — Chuyển writer và lifecycle đầy đủ

**Files chính:** authority command/write/evidence/repository, pristine materialization, lifecycle mirror, external/switch/content topology, delete/reset (`deck_management_service`, `flashcard_content_service`, `study_note_template_service`, `study_content_delete_service`), session/batch paths của NOTE; danh sách cuối từ P9-00. Nhánh LEGACY-only (F9-09) không port, chỉ chặn bằng P9-05c.

1. Một canonical transaction cập nhật state, token, availability cần thiết, ReviewEvent/history và receipt. Bỏ lock/encode/update CardProgress cùng raw-projection refresh khỏi profile mới.
2. Availability/provenance đang được dùng phải tiếp tục cập nhật đúng; không “giảm tải” bằng cách ngừng mọi contributor/lineage writes.
3. Bao phủ tất cả writers đường NOTE ở P9-00, nhất là first-state, Note mới, repeated application, admin delete nhiều learner và clone rekey. Anki/Connect tách sang P9-05b. Giữ typed conflict, zero source mutation.
4. Thử mixed versions: node/worker cũ không được ghi sau khi epoch cutover đã chuyển; fail closed khi không hiểu profile. Deploy hết binaries hỗ trợ trước khi enable.
5. Recovery sau lỗi không commit một nửa: inject lỗi sau state/history/receipt, process crash, lost COMMIT ACK, duplicate batch/direct retry, deadlock.
6. Cắt projection trên toàn hệ thống cùng lúc (D9-08), không theo một API riêng lẻ; không để direct/MCP/worker vẫn tạo projection trong khi batch đã dừng.

**Gate:** workload profile mới có **zero SELECT dùng cho quyết định/validation current progress và zero INSERT/UPDATE projection vào CardProgress**, kể cả create/import/reset. Reader canonical phải chạy được khi fixture không có projection. Nếu content deletion vẫn cascade dọn projection lịch sử còn giữ, khai báo riêng là cleanup, chứng minh không đổi canonical state/history ngoài lifecycle được yêu cầu và không tính nó thành projection writer. P9-10 mới yêu cầu bỏ toàn bộ SQL/FK phụ thuộc bảng. State/history/receipts khớp expected transitions, không chỉ khớp row count.

### P9-05b — Fence và codec Connect/Anki không qua CardProgress

**Files chính:** `app/services/anki_sync_service.py` (`_apply_note_authority_progress_snapshot`, các chỗ đọc/ghi `applied_local_revision`), `app/services/connect/import_cards.py`, `study_progress_reconciliation_service.py`, `models/connect_source_card_ref.py` + migration nếu ADR P9-03 §7 chọn cột mới.

1. Phát hiện học local so với revision của hệ NOTE theo ADR; không đọc `CardProgress.revision` trong đường NOTE.
2. Xử lý mọi `applied_local_revision` đã lưu theo cách ADR chốt, dưới fence, idempotent, có dry-run đếm; ghi lại số ref đã migrate/đánh dấu.
3. Dựng NOTE state từ snapshot Anki bằng codec trực tiếp (có thể dùng lại hàm map thuần), không cần dòng CardProgress của sibling; Note/Card chưa có CardProgress không lỗi.
4. Giữ external ID/provenance, typed conflict `LOCAL_PROGRESS_CHANGED`/`SOURCE_SNAPSHOT_CHANGED`, `force` như hiện hành.

**Gate:** học trên Flama sau cutover rồi re-sync cùng snapshot Anki phải trả `LOCAL_PROGRESS_CHANGED`, không ghi đè; snapshot mới không `force` cũng vậy; `force` ghi đúng và tạo history. Ref chưa từng sync, ref có giá trị cũ đã migrate và ref bị đánh dấu đều có test. Card mới tạo sau cutover (không CardProgress) import được.

### P9-05c — Đóng đường vào LEGACY

**Files chính:** `app/services/study_authority_enrollment_service.py` (`enroll_new_learner_note_authority`), `app/services/auth_service.py`, `app/services/google_auth_service.py`, `app/cli.py` (`study-authority-enrollment`), `docs/runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md` §4.5.

1. Signup (form và Google) enroll NOTE vô điều kiện; không enroll được thì transaction signup lỗi có mã rõ, không tạo tài khoản LEGACY. Bỏ phụ thuộc `STUDY_NEW_LEARNER_NOTE_ENABLED`/`STUDY_WIRE_V4_ENABLED`/`STUDY_ASYNC_BATCH_ENABLED` cho quyết định này. Wire v4 tắt hoặc async bật ảnh hưởng mọi learner NOTE như nhau, nên xử lý ở mức hệ thống (readiness/health báo lỗi cấu hình), không bằng cách âm thầm cho tài khoản mới vào LEGACY. Làm sớm được, trước P9-03.
2. Khóa `study-authority-enrollment --mode LEGACY` (từ chối có mã) chậm nhất khi P9-06 bắt đầu; `--mode NOTE` vẫn dùng được cho user chưa enroll nếu còn.
3. Sửa runbook P5 §4.5: rollback NOTE → LEGACY không còn là đường phục hồi (D9-02); dẫn sang §9 kế hoạch này.
4. Readiness P9-02a báo learner LEGACY/unenrolled mới là blocker, không chỉ đếm một lần.

**Gate:** test signup form/Google khi thiếu cờ env hoặc bật async vẫn cho learner NOTE hoặc báo lỗi, không bao giờ LEGACY; CLI `--mode LEGACY` bị từ chối; readiness phát hiện learner LEGACY được chèn cố ý trong test.

### P9-06 — Backup rồi ngừng ghi song song

**Prerequisites:** G9-FULL + G9-WRITE; P9-04/05/05b/05c và MySQL matrix §7 đã chứng minh toàn bộ luồng NOTE; audit canonical thay thế (P9-04 §4) là gate trong runbook deploy. D9-02 đã được chủ sản phẩm chốt. Backup phải có trước lần ngừng ghi projection đầu tiên.

1. Deploy đủ reader/writer/binaries/worker tương thích, projection còn cập nhật. Chạy đối chiếu toàn bộ learner và writer matrix, ghi `FULL_NOTE_PASS`; thiếu coverage thì sửa đúng phần thiếu.
2. Mặc định theo D9-08: **write freeze ngắn** — dừng admission session/batch/direct/import, drain accepted jobs/leases theo contract. Khi đó T0 của backup trùng điểm cutover, nên backup chứa mọi dữ liệu đến lúc cắt.
3. Tạo backup nhất quán dưới freeze: cả dữ liệu cũ và bộ NOTE hiện hành, history/receipt, external identity, schema/release và mapping. Ghi T0/checksum/watermark; restore vào DB cách ly, kiểm row/hash/quan hệ và thử bổ sung chọn lọc theo §9. Nếu thời gian dump/restore đo ở P9-00 làm freeze quá dài, restore thử có thể làm trên bản dump ngay sau khi mở lại, nhưng dump phải xong trước khi mở ghi.
4. Dưới fence, chụp watermark cuối và chuyển cờ/epoch cutover toàn hệ thống; khóa CLI `--mode LEGACY` (P9-05c) nếu chưa khóa; stale process không được ghi.
5. Mở ghi NOTE, xác nhận full canonical transaction và zero INSERT/UPDATE projection ở mọi entrypoint. Kiểm owned + overlay + new-user/create/import, Anki re-sync, lost-ACK replay và stats; chạy audit canonical toàn bộ learner.
6. Bảo toàn dữ liệu sau T0 cho giai đoạn sau: binlog/PITR hoặc backup định kỳ theo kết quả P9-00; ghi RPO thực tế, không báo RPO=0 nếu chưa có nguồn đã diễn tập. Đây là vận hành backup của hệ NOTE, không phải lý do giữ projection.
7. Giữ backup và mapping phục hồi. Tiến hành các phần cắt giảm đã đủ gate; không đặt thêm thời gian giữ projection cập nhật cố định. Bảng cũ tạm giữ không có nghĩa tiếp tục ghi nó.

Nếu D9-08 bị đổi sang cohort (P9-00 cho thấy freeze không chấp nhận được): chỉ bắt đầu chia nhóm sau khi toàn hệ thống đạt G9-FULL, mỗi nhóm có T0/watermark riêng, và không gọi “full NOTE-only” khi còn nhóm ghi song song.

**Gate P9-B:** 100% learners và new-user default dùng canonical profile, 0 learner LEGACY và không đường vào LEGACY, mọi writes mới đủ state/history/receipt, zero current-progress dependency/projection updates, zero split brain, audit canonical PASS; G9-BACKUP và G9-CUT có evidence. Cleanup dữ liệu legacy còn giữ phân loại riêng như P9-05.

**Khi lỗi:** giữ NOTE là nguồn dữ liệu hiện hành, sửa code hoặc dùng artifact vẫn hiểu NOTE; bổ sung dữ liệu thiếu từ backup theo §9. Không quay về LEGACY hay bật lại ghi song song như phản xạ mặc định.

### P9-07 — Giảm snapshot đầu phiên, nếu baseline yêu cầu

Đây là phần giảm tải bổ sung, không phải điều kiện để xóa code wire cũ.

- Đề xuất snapshot queue cần học + cửa sổ learning/learn-ahead đã định nghĩa, có refill/continuation và bounded pin/membership. Không âm thầm cắt danh sách rồi coi là học xong.
- Giữ frozen composition, scheduler config, Algorithm version, day boundary, new allowance và thứ tự queue; quy định rõ Card có thể đến hạn trong lúc offline.
- Profile/wire capability mới khi thay contract; legacy v4 lease đang sống vẫn xử lý đúng. Không sửa snapshot/hash đã cấp.
- Materialize/pin chỉ subjects được admit theo contract mới; lặp refill không cấp trùng, không reset lease TTL vô hạn, không làm history/receipt mất idempotency.
- Giữ NOTE batch rollover cùng lease hiện có. Không tăng limit 50 câu hoặc trì hoãn lưu offline để che chi phí server.

**Gate:** workload deck 20k/40k nhưng queue nhỏ phải có chi phí snapshot tỷ lệ với cửa sổ admitted, không cả deck; đủ tests online/offline/day rollover/refill retry/reset/template change. Mục tiêu giảm membership/payload ≥80% khi queue ≤20% scope, không áp dụng cho queue vốn bằng scope.

**Rollback:** ngừng cấp profile mới, tiếp tục xử lý lease đã cấp; client rollback chỉ khi đọc được IndexedDB/profile còn sống.

### P9-08 — Wire/Connect retirement tách PR

- Wire: dừng issuance cũ trước; chờ valid leases + accepted jobs + rollback window + D9-03, không suy từ 30 ngày detail retention. Gỡ executable/replay branch v2/v3 nhưng giữ decoder cần cho history/receipt và typed expiry/upgrade response.
- Frontend: pending data cũ được quarantine/hiển thị trạng thái rõ; không xóa IndexedDB hàng loạt hoặc replay tự động sang phiên mới. Test commit replay sau membership purge và double-submit cũ.
- Connect: bỏ riêng fallback positional khi replacement stable ordinal áp dụng cả import/reimport package mới/cũ. Test Template reorder/delete, repeated occurrence, native occurrence không source ordinal, ref detached, overlay. Giữ external ID/provenance.
- Hai nhóm độc lập; ordinal đủ gate có thể làm trước wire. Mỗi removal cần actual callsite usage, không chỉ null count.

**Gate:** old executable/fallback invocation bằng zero trong cửa sổ đã chốt, coverage đủ; retained history/receipt vẫn đọc được. 29/10/2026 là sớm nhất theo số liệu issuance đã ghi, có thể muộn hơn nếu có late use hoặc thiếu telemetry.

### P9-09 — Dọn phần generic và compatibility còn lại

Mỗi nhóm có inventory + replacement + test riêng:

| Nhóm | Được cắt khi | Phải giữ |
|---|---|---|
| Generic types giả định bốn rating | Action/evaluator adapter có contract tương đương | Bốn rating của built-in và đọc lịch sử rating |
| Gọi scheduler trực tiếp/transaction trùng | Mọi caller đã qua canonical orchestrator/adapter | Engine `anki_scheduler` còn được registry Algorithm dùng |
| Fixed Algorithm columns | Không phục vụ query/export/compatibility và thay thế đã đạt parity | Current state, availability fields còn query, config/preset còn dùng |
| Renderer/manifest cũ | Không lease/package/content nào cần decoder cũ | CSP, media proxy, versioned renderer active, custom content |
| Name-based Template/Field fallback, rename job | Stable binding thực sự tồn tại và toàn bộ content/import/export chuyển xong | Field-name JSON/placeholders/rename flow nếu vẫn là contract hiện hành |
| Backfill/mirror tools cũ | Cutover/restore/reconciliation không còn cần executable đó | Historical migration files và bằng chứng audit |
| Nhánh LEGACY-only (F9-09): tạo/cập nhật CardProgress trong direct review, session commit, worker, Connect import, Anki; `stage_legacy_authority_enrollment` | P9-05c đã chặn đường vào LEGACY, P9-02a xác nhận 0 learner LEGACY liên tục, không caller nào còn tới nhánh | Decoder cần để đọc history/receipt cũ; typed refusal nếu gặp route LEGACY bất ngờ |

Thiếu replacement thì ghi **deferred với blocker**, không tạo dự án stable Field IDs mới trong đợt giảm tải gấp. P9-C chỉ hoàn tất khi backlog còn lại được xử lý hoặc scope loại trừ được quyết định rõ.

### P9-10 — Archive và contract vật lý

1. Lập manifest chính xác từng table/column/index/FK, consumers=0, last use, row count/bytes, retention và nơi archive.
2. Archive giữ identity, schema/codec versions, hashes/provenance cần đọc. Kiểm restore trên DB cách ly cùng MySQL major/minor tương ứng và chạy invariant/replay matrix.
3. Migration additive đã có trước code cutover; contract là revision mới. Old binaries/startup maintenance/CLI cũ không được tái tạo hoặc ghi bảng đã nghỉ hưu. Cụ thể (F9-10): startup maintenance gọi `db.create_all()`, sẽ tạo lại bảng rỗng nếu model vẫn được import vào metadata; `app/startup_schema.py` còn patch cột CardProgress. Gỡ model khỏi metadata và gỡ patch trong release chạy trước DDL drop; test boot `wsgi.py` với maintenance bật trên schema đã contract không tạo lại bảng/cột.
4. Tháo FK/dependency đúng thứ tự. Không suy “SET NULL nên xóa an toàn”: nullable history link vẫn có thể mất khả năng truy vết; availability CASCADE có thể mất queue data.
5. Rehearse từng DDL, metadata-lock wait, duration, disk headroom, failure và forward recovery. Online DDL vẫn có metadata locks và hạn chế với FK; chọn `ALGORITHM`/`LOCK` theo operation đã chứng minh, không hứa `LOCK=NONE` cho mọi bảng. [MySQL 8.0](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-limitations.html).
6. Hoàn thiện manifest, backup/restore proof, reconciliation, RPO/RTO và exact migration trước apply; mỗi phần phải có cách bổ sung từ backup sang NOTE mà không đè dữ liệu mới.

**Gate:** boot/upgrade/restore trên schema đã contract; production current progress/history/receipts không đổi ngoài writes hợp lệ. Không coi Alembic downgrade tái tạo bảng rỗng là phục hồi dữ liệu.

Không chạy `OPTIMIZE TABLE` như cách “giảm tải nhanh”: đây là rebuild bảng, có chi phí riêng. Thu hồi dung lượng vật lý cần lịch/rehearsal riêng. [MySQL online DDL limitations](https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-limitations.html).

## 6. Thứ tự triển khai ưu tiên

| Bước | Hành động | Kết quả review được |
|---|---|---|
| 0 | Đóng đường vào LEGACY cho signup (P9-05c §1) — làm ngay, độc lập | Không learner LEGACY mới dù env lệch |
| 1 | Kiểm toàn bộ NOTE data/readers/writers; tách khỏi projection, gồm Connect/Anki fence và audit thay thế; sửa phần còn thiếu | G9-FULL + G9-WRITE; không kết luận từ enrollment count |
| 2 | Write freeze ngắn, backup nhất quán, thử restore và thử bổ sung dữ liệu | G9-BACKUP, T0 = điểm cutover, mapping + nguồn bảo vệ dữ liệu sau cutover |
| 3 | Drain work cũ, cắt projection toàn hệ thống, mở ghi NOTE đầy đủ | G9-CUT trên mọi entrypoint và mọi learner; audit canonical PASS |
| 4 | Retention có giới hạn, giảm snapshot khi cần, dọn compatibility | Đo SQL/CPU/I/O/memory/storage giảm thực tế |
| 5 | Archive/drop theo manifest từng nhóm đủ gate | Code/schema không còn consumer; backup vẫn phục hồi được |

Nếu phát hiện lỗi ở bất kỳ bước nào: khoanh phạm vi, giữ dữ liệu mới, sửa/bổ sung từ backup rồi tiếp tục. Không lấy việc chưa thể biết mọi lỗi tương lai làm lý do duy trì ghi song song vô thời hạn.

## 7. Ma trận kiểm chứng

| Trục | Ca bắt buộc |
|---|---|
| Ownership | Owned Note; installed source overlay; local-added Note; admin nhiều learner; Note mất Card; signup form/Google khi cờ env thiếu hoặc async bật (không bao giờ LEGACY) |
| Presentation | Một/nhiều Template; repeated application; add/delete/reorder; source/local edit |
| Study | New/learn/relearn/review; suspend/bury/reset; timezone/day rollover; Algorithm switch/history initialization |
| Transport | REST/MCP direct; NOTE sync batch; async nếu enabled; retry/duplicate/lost ACK; offline restore; empty finalization |
| External | Anki snapshot + revlog/import/reimport; Connect export/package; source ordinal delete/reorder; revision conflict; học trên Flama sau cutover rồi re-sync (phải `LOCAL_PROGRESS_CHANGED`); ref có `applied_local_revision` cũ; Card mới không có CardProgress |
| Concurrent | Cùng Note khác tab; khác Note cùng learner; khác learners; mixed code versions; cutover khi enqueue/commit đang diễn ra |
| Failure | Lỗi trước/sau commit; deadlock; process restart; partial retention/backfill; storage profile không hiểu; telemetry mất coverage |
| Retained data | History/stats/streak/receipt trước và sau retention; restore archive; source content fingerprints không đổi |

Commands hiện có, chạy theo phạm vi thay đổi khi triển khai:

```powershell
python scripts/run_tests.py --file tests/test_study_phase9_readiness.py tests/test_study_session_retention.py --backend-only
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module connect_mcp,flashcards,decks,marketplace --backend-only
python scripts/run_tests.py --module study --frontend-only
```

Chạy test hẹp trước; mở rộng module khi diff thực sự chạm domain, không chạy cả bốn lệnh sau mọi PR. Frontend đổi thì thêm production build và browser flow bằng isolated profile.

Probe có sẵn: `scripts/bench_p5_session_open_mysql.py`, `probe_p5_concurrency_mysql.py`, `probe_p5_direct_replay_mysql.py`, `probe_p5_study_batch_mysql.py`, `probe_p5_authority_schema_mysql.py`, `probe_p5_analytics_mysql.py`, `probe_p6_application_schema_mysql.py`, `probe_p7_session_retention_mysql.py`. Chỉ dùng DB tổng hợp cách ly; kiểm cấu hình endpoint trước khi chạy. Mở rộng probe cho canonical profile mới, không giả định probe cũ đã bao phủ P9.

Workload: 1/4/8 learner, 16 để tìm giới hạn; scope session 2.000 và tối đa 5.000 Card; 3.000 pristine Note; collection 20k/40k cho Browse/count (open >5k chỉ sau contract P9-07); 1/2/4 presentation occurrences/Note. Cùng SHA/hardware/flags/data/seed/timezone cho A/B, có warm-up và ít nhất 3 lượt đo.

## 8. Ngân sách tải và điều kiện dừng

Đây là **mục tiêu đề xuất**, chưa phải SLO đã được đo/chấp nhận. P9-00 phải ghi baseline và chốt ngưỡng trên host đại diện; không nới ngưỡng sau một benchmark xấu để báo pass.

| Chỉ số | Mục tiêu nghiệm thu / trigger |
|---|---|
| Correctness | 0 lost/duplicate accepted answers; 0 unexplained state/history/receipt/queue mismatch — vi phạm một lần là dừng |
| Projection | 0 current-progress read dependency, 0 INSERT/UPDATE projection sau cutover; 0 learner LEGACY mới; không tăng legacy writes theo answer/sibling count; cleanup lịch sử báo riêng |
| Commit workload 50 answers | Mục tiêu giảm ≥30% SQL/row-write cost so baseline cùng workload; p95 không xấu đi >10%; chưa hứa giảm latency 30% |
| Health/login bên cạnh load | Health p95 <500 ms, không 504; không làm starve login/commit |
| Open 2.000 Note đã materialize, 8 learners | Mục tiêu p95 <5 s; đo riêng pristine, payload, CPU và DB |
| Retention | Transaction p95 <1 s; lượt chạy ≤60 s trước khi nhường; không overdue eligible backlog tăng liên tục 3 ngày |
| Tăng trưởng | Rows/bytes membership mới, eligible backlog, purged rows/ngày và days-to-disk-full đều có báo cáo |
| Hạ tầng | Cảnh báo CPU >80% 5 phút, pool usage >80% hoặc pool timeout, disk free <20%; đo I/O và lock waits để phân biệt nguyên nhân |

Khi correctness lỗi: dừng rollout (hoặc chuyển cohort nếu D9-08 bị đổi), chặn writer ảnh hưởng, giữ local/queued work, theo recovery §9. Khi p95 xấu >20% baseline trong 10 phút với đủ mẫu hoặc có timeout/5xx tăng: dừng maintenance/rollout, thu trace, không tiếp tục.

Nếu đang quá tải trước khi hoàn tất P9-B: tạm dừng backfill/reconciliation/retention nặng, giảm concurrency job ngoài giờ học, thêm bounded admission cho session-open/import với typed 429/503 + Retry-After và client backoff nếu đo thấy cần. Đây là code/ops output phải thiết kế, chưa có flag P9 hiện hữu. Không trả receipt thành công khi chưa lưu, không bỏ accepted job, không tắt fencing hoặc bật async chưa đủ readiness. Commit/status/recovery được ưu tiên tài nguyên.

## 9. Bổ sung từ backup, bảo toàn dữ liệu NOTE mới

| Tình huống | Cách xử lý | Bảo vệ dữ liệu mới |
|---|---|---|
| Lỗi code đọc/ghi NOTE | Khoanh writer lỗi; sửa hoặc quay về artifact vẫn hiểu NOTE | Giữ canonical data, accepted jobs và client pending work |
| Thiếu dữ liệu lịch sử/metadata trước T0 | Restore backup vào DB cách ly; map và bổ sung đúng phần thiếu | Không overwrite state/revision mới, không tạo review/receipt trùng |
| Dữ liệu đã đổi/reset/delete sau T0 | Đối chiếu generation, revision, tombstone/lifecycle và operations sau T0 trước khi sửa | Không hồi sinh Note/progress đã xóa/reset, không dùng “backup có dòng” làm bằng chứng cần insert |
| Mất/hỏng dữ liệu sau T0 | Dùng nguồn phục hồi writes sau T0 đã thử, phục hồi cách ly rồi reconcile | Backup trước cutover không chứa các writes này; receipt riêng lẻ không mặc nhiên đủ dựng lại state |
| Đã archive/drop bảng cũ | Restore bảng cũ cách ly, chuyển phần cần thiết sang schema NOTE bằng mapping được giữ | Không restore toàn database cũ đè production |

Quy trình bổ sung:

1. Chụp backup/snapshot hiện trạng NOTE trước sửa; ghi phạm vi learner/subject/event và cutoff cần khôi phục.
2. Restore backup T0 vào DB cách ly. Lập manifest `insert_missing / repair_corrupt / skip_newer / skip_deleted_or_reset / conflict` theo stable identity và provenance; không chọn bản thắng chỉ dựa timestamp.
3. Với subject đã có dữ liệu mới, chỉ bổ sung phần thiếu độc lập. Current state bị hỏng phải được phục hồi có đủ chuỗi ghi/state mới đã xác minh; không chép state cũ rồi tự đoán lịch học tiếp theo.
4. Dry-run ra diff/count/hash, khóa/fence đúng phạm vi khi apply, kiểm lại revision để tránh ghi đè commit vừa tới. Apply theo lô idempotent, giữ unique operation/event/receipt identity.
5. Đối chiếu state/history/receipt/queue và tombstone. Test chạy lại không đổi, retry ACK không tạo duplicate; kiểm mọi write sau T0 vẫn còn.

**Bài thử phục hồi bắt buộc trước cutover:** tạo backup T0 → ghi thêm answers/import/reset/delete trên NOTE → làm thiếu một phần dữ liệu cũ có kiểm soát trong DB thử → bổ sung từ T0 → chứng minh dữ liệu cũ được sửa và tất cả thao tác sau T0 được giữ. Thêm ca hỏng state mới và phục hồi bằng nguồn sau T0; không báo RPO=0 nếu chưa có nguồn đó.

RPO=0 cần khả năng khôi phục mọi commit đã ACK sau backup bằng nguồn ghi đầy đủ đã diễn tập, chẳng hạn binlog/PITR nếu hạ tầng thực có. Backup/nhật ký sau cutover thuộc hệ NOTE, không phải tiếp tục projection legacy. Ghi RTO đo được và watermark trước mở lại writer bị ảnh hưởng.

Với write freeze theo D9-08, T0 trùng điểm cutover: backup T0 chứa toàn bộ dữ liệu legacy + NOTE đến lúc cắt, nên hàng “Thiếu dữ liệu lịch sử/metadata trước T0” không có khoảng trống giữa backup và cutover. Các hàng “sau T0” khi đó chỉ còn là dữ liệu phát sinh trên hệ NOTE sau cutover, được bảo vệ bằng nguồn ghi ở P9-06 §6.

## 10. Hồ sơ hoàn tất

Mỗi P9-A/B/C có report riêng: release/schema, quyết định áp dụng, learner coverage, inventory closed/deferred, benchmark trước/sau, SQL counters, MySQL failure/recovery evidence, backup/restore và trạng thái rollback.

- **P9-A đạt:** G9-FULL + G9-WRITE có bằng chứng toàn hệ thống; NOTE chứa đủ dữ liệu, chạy được khi không có projection, mọi luồng ghi mới (gồm Connect/Anki) đã được kiểm; không còn đường vào LEGACY; audit canonical thay thế sẵn sàng.
- **P9-B đạt:** backup/restore + bổ sung dữ liệu đã thử; toàn hệ thống ngừng projection, writes mới đầy đủ vào NOTE; 0 learner LEGACY; bảng cũ có thể vẫn giữ.
- **P9-C đạt:** từng nhóm cắt giảm có hiệu quả tài nguyên đo được, archive/schema contract được xác minh; recovery giữ cả dữ liệu trước và sau cutover.

Việc lập tài liệu này chỉ kiểm tra source, commands/paths và liên kết. Test, benchmark, production readiness và rollout trong kế hoạch vẫn là công việc triển khai, không phải kết quả đã thực hiện.
