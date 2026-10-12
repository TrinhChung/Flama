# Hoàn tất progress hiện hành và loại bỏ legacy

> Ngày: 2026-10-12 (Asia/Tokyo). Yêu cầu: kiểm tra/chuyển local trước, ổn mới thực hiện trên VPS; lập kế hoạch loại bỏ legacy.
> Baseline root: `9b5db52e`. VPS audit tại release `/opt/flama/releases/fde1cd882abe3cfc4158e473a8c53da2dd71de36`.
> Chế độ: DESIGN, dựa trên [review 110 model](../architecture/LEGACY_MODEL_CLEANUP_REVIEW_2026-10-12.md) và audit MySQL thực tế dưới đây. Đây là kế hoạch implementation/retirement; chưa xóa model hay bảng nào.

## 1. Kết quả hiện tại: không còn progress cần chuyển ở hai DB đã kiểm

Đã thực hiện audit local, kiểm tra công cụ bằng test, rồi chạy cùng audit qua SSH trên VPS. Toàn bộ truy vấn chạy trong transaction MySQL **READ ONLY / consistent snapshot**, không chạy app startup, không ghi state hoặc đổi enrollment/profile.

| Chỉ tiêu | Local `nihongo`, MySQL 8.0.40 | VPS `flama`, MySQL 8.0.46 |
| --- | ---: | ---: |
| Tài khoản NOTE | 32/32 | 32/32 |
| LEGACY / chưa enroll | 0 / 0 | 0 / 0 |
| Storage profile / epoch | `CONSOLIDATED_V1` / 3 | `CONSOLIDATED_V1` / 3 |
| Dòng `card_progress` cũ | 40.793 | 40.793 |
| Dòng cũ có subject + state mới đúng identity | 40.793 | 40.793 |
| Thiếu Card/Note/subject/state hoặc khác Note identity | 0 | 0 |
| Dòng cũ ghi sau cutover | 0 | 0 |
| Subject hiện hành | 42.793 | 42.839 |
| Lỗi codec/hash/availability state mới | 0 | 0 |
| State cũ và mới có cùng semantic hash | 40.349 | 40.310 |
| State hiện hành khác bản cũ, được giữ nguyên | 444 | 483 |
| Progress cũ không map được | 0 | 0 |
| Fan-in của progress cũ | 0 | 0 |
| Kết quả audit dữ liệu | `DATA_READY`, blockers rỗng | `DATA_READY`, blockers rỗng |

Profile được chuyển ngày `2026-10-03T06:38:52Z`. Hai bảng progress cũ có **cùng SHA-256 snapshot**: `f4af3cb924bbb099b1c6f565a0906af91f416ca5f506f65153d621d8af993b04`. State mới local/VPS khác nhau; không đồng bộ state local đè VPS.

State khác bản đóng băng không tự chứng minh mất dữ liệu: NOTE đã được review/reset/import hoặc đổi thuật toán sau khi projection cũ dừng ghi. Audit giữ nguyên state hiện hành và kiểm tra codec, size, algorithm hash, semantic hash, queue/due/suspension projection của nó. Audit này không thay cho chứng cứ lịch sử của từng review; [hồ sơ cutover P10](../task/decoupling/P10_08_CUTOVER_REPORT_2026-10-03.md) vẫn cần giữ.

**Không chạy lại migration progress:** các trường hợp thiếu dữ liệu trên local và VPS đều bằng 0. Chạy lại CardProgress -> NOTE sẽ có nguy cơ làm lùi 444/483 state hiện hành khác snapshot cũ. Việc cần làm tiếp là retirement code và archive/contraction dữ liệu cũ.

Chứng cứ đã lưu trong repo, chỉ gồm số lượng, checksum và trạng thái; không chứa password hay nội dung Note:

- [Local audit](../architecture/artifacts/legacy_progress_retirement_20261012/local-retirement-audit.json)
- [VPS audit](../architecture/artifacts/legacy_progress_retirement_20261012/vps-retirement-audit.json)
- [Công cụ audit](../../scripts/audit_legacy_progress_retirement.py), [12 test](../../tests/test_legacy_progress_retirement_audit.py)

## 2. Invariant khi dọn

1. `StudyProgressSubject` là nguồn state, availability và CAS revision hiện hành cho toàn bộ learner ở hai DB đã kiểm. Không seed lại state pristine hay lấy max/latest của CardProgress để ghi đè row này.
2. Không xóa review history, command receipt, lifecycle evidence hoặc replay membership để giảm số model.
3. Source Note không bị copy/mutate trong clone; learner/source Note là identity progress. Release pins và overlay giữ nguyên phạm vi đã publish.
4. Fan-in tương lai chỉ migrate tự động khi các state có semantic hash tương đương. State khác nhau, orphan, tombstone/reset hoặc lịch sử không đủ cần disposition riêng; không tự chọn winner theo timestamp/reps/revision.
5. Xóa bảng không hoàn tất retirement nếu model còn trong metadata, startup patch hoặc migration chain còn import module bị xóa.
6. Thứ tự cho từng thay đổi: local rehearsal -> kiểm tra -> deploy code phù hợp -> chạy DDL/data operation trên VPS -> hậu kiểm. Migration ID phải chọn tại thời điểm implementation vì worktree P11 đã có revision 57 đang làm.

## 3. Hai phương án progress và lựa chọn theo audit

| Phương án | Khi áp dụng | Đánh giá trên dữ liệu hôm nay |
| --- | --- | --- |
| A — Import lại mọi CardProgress vào NOTE | Chỉ phù hợp restore/migration có source còn authoritative và target chưa được dùng | Không chọn: target đang authoritative, đã có state mới khác snapshot, coverage 100% |
| B — Xác minh coverage + state hiện hành, chỉ sửa gap chứng minh được | DB đã cutover; giữ state mới, audit từng source identity và archive snapshot | Đã chọn và thực hiện audit. Local/VPS đều không có gap để sửa |

Nếu audit ở DB khác trả `LEGACY_LEARNERS`, `NOTE_PROGRESS_COVERAGE_GAP` hoặc orphan, công cụ hiện tại trả BLOCK, không tự migrate. Khi đó mới cần adapter import có fence theo learner, dry-run/disposition cho từng group, bảo toàn lineage/Connect revision và transaction có thể retry. Hàm enrollment hiện từ chối learner có CardProgress; không tháo refusal để tự enroll pristine.

## 4. Các đợt implementation

### R0 — Kiểm chứng tiến độ mới: đã hoàn tất

- Local rồi VPS: 100% old progress coverage; 0 lỗi state hiện hành; 0 LEGACY/unenrolled; 0 old write sau cutover.
- Công cụ không có `--apply`; test kiểm SQL phát ra chỉ SELECT/PRAGMA và kiểm giữ nguyên state mới, gap, orphan, identity hỏng, hash sai, availability lệch, legacy learner, timestamp cutover thiếu và write sau cutover.
- Đã đăng ký script/test vào module `study` của [modular runner](../../scripts/run_tests.py).
- Chưa drop dữ liệu; các audit là baseline của các đợt sau, không phải trạng thái DDL đã hoàn tất.

### R1 — Retire bốn model không còn consumer runtime

**Model:** `VocabularyColumnPreference`, `StudyProgressBackfillRun`, `StudyProgressBackfillCheckpoint`, `StudyProgressBackfillDisposition`.

**Dữ liệu thực tế trên cả hai DB:** column preference 0 row; backfill 1 run, 1 checkpoint, **16.986 disposition**. Các disposition là bằng chứng migration cũ, không phải current progress và không được coi là dữ liệu rỗng.

**PR-A, code:** gỡ bootstrap imports và runtime ORM của bốn model. Giữ contract historical của migration 39 bằng frozen definitions trên metadata dành cho migration, theo cơ chế đang có cho các bảng P10 đã retire; không để import ngược đăng ký bảng vào runtime. Gỡ reference test matrix còn chỉ tới model cũ. Các route vocabulary lesson/column-widths `410` giữ hành vi.

**PR-B, contraction:** archive ba bảng backfill cùng schema/checksum/row counts; thử restore local và đọc được evidence. Migration drop disposition, checkpoint, rồi run (disposition FK `RESTRICT`). Drop column preferences sau khi xác nhận vẫn 0 hoặc đã archive. Tất cả thao tác drop là nhiệm vụ implementation sau kế hoạch này.

**Đạt khi:** fresh migration chain chạy được; import app/audit/Connect không đăng ký lại bốn bảng; `db.create_all()` trong rehearsal không tái tạo; MySQL local restore + migration + app boot PASS trước VPS.

### R2 — Loại bỏ CardProgress khỏi đường chạy

**PR-C, consumers:** chuyển code sang NOTE-only và loại nhánh scheduler persistence LEGACY. Phạm vi manifest phải bao gồm:

| Khu vực | Công việc cụ thể |
| --- | --- |
| Direct/session/worker review | Bỏ create/query/update CardProgress; giữ NOTE CAS, receipt/idempotency, algorithm decoder và transaction semantics |
| Browse, dashboard, tree, counts | Bỏ repository/join theo CardProgress; dùng subject availability và count contract hiện hành; cập nhật cache invalidation khi cần |
| Delete/reset/rekey và content fences | Learner discovery từ subjects + session/lease/context hiện hành, kể cả row không có current state; chứng minh không mất learner trước khi bỏ discovery từ projection cũ |
| Enrollment | NOTE-only bootstrap/enrollment invariant; row LEGACY ở DB ngoài rollout phải fail rõ ràng, không tự reset state |
| Connect import/snapshot/ref fence | Bỏ nhánh `LEGACY_CARD_PROGRESS` và dependency revision cũ theo disposition đã kiểm; giữ external ID, Note/source ordinal, `AUTHORITY` và `NEEDS_CONFIRMATION` |
| CLI, seed, audit, repair, maintenance | Bỏ mọi consumer/query tới CardProgress, gồm typed fixture/probe cần cập nhật; audit retirement này cũng phải được chuyển contract ở bước contraction |
| Models/startup/schema | Gỡ User/Card relationships tới CardProgress, re-export trong `models/flashcard.py`, bootstrap imports và mọi `startup_schema` patch `card_progress` |
| Historical migrations | Frozen parent/schema riêng cho migration 39 và `migrations/retired_note_progress_tables.py`; không xóa file mà bỏ qua import chain |

**Compatibility:** tách wire payload/history decoder khỏi thực thi scheduler LEGACY. V2/v3 và positional ordinal từng được chốt giữ ở P9; không coi chúng đã tự retire vì mọi learner đã NOTE. Kiểm inventory session/batch/retention/late retry và backend/frontend restore trước khi bỏ từng execution path. Historical receipts/events vẫn đọc được.

**PR-D, contraction:** archive `card_progress`, rehearsal restore vào DB cách ly; sau khi runtime consumer manifest = 0 và deployment phù hợp đã phục vụ, drop FK/model/table trong migration riêng. Không cần backfill lại 40.793 row vì R0 đã chứng minh target coverage hiện hành.

**Đạt khi:** SQL trace các luồng owner và installed clone không còn SELECT/INSERT/UPDATE/DELETE `card_progress`; progress/hash/CAS không đổi qua deployment; import/sync, reset/delete, queue/count parity, retry session PASS trên SQLite và MySQL.

### R3 — Card vật lý: nối với P11 đang làm

Không mở một implementation Card thứ hai cạnh worktree P11. Dùng [review P11](../architecture/P11_DERIVED_CARD_PLAN_REVIEW_2026-10-11.md) làm gate bổ sung:

- Presentation suy ra từ Note/application; gắn template không tạo N Card, tạo Note không tạo N presentation row.
- Owned ACTIVE applications và installed clone **release-pinned applications** là hai scope có nghĩa khác nhau; retired source app vẫn có thể nằm trong release cũ.
- Clone timestamp legacy: `application.created_at` backfill không thay được Card cutoff lịch sử.
- Session cũ giữ wire ID/snapshot/fingerprint; normalize internal identity không đổi ID của retry đã được nhận.
- Expand schema trước khi phát pair key 73 ký tự; `study_session_cards`, `review_events` và Connect ref phải có disposition rõ. Sau R2, FK CardProgress không còn là blocker, còn membership/ref dependencies phải chuyển.
- Đầu giai đoạn giữ Card cũ chỉ đọc làm alias. Physical purge là gate riêng khi toàn bộ lease/ref/history consumers đã có cách resolve phù hợp; readonly alias không tự tạo khả năng rollback release cũ cho presentation mới.

**Đạt khi:** owner + installed clone + local-added Note + pinned retired app đều parity; old session/retry giữ nguyên kết quả; attach/new Note không ghi Card; migration chain, MySQL DDL và backup restore PASS.

### R4 — Hoàn tất attachment cutover và dọn origin của Template

- Kiểm và chuyển toàn bộ consumer đang dùng `Template.note_type_id` / `NoteType.templates` như danh sách attachment sang `StudyApplication` đúng scope.
- Ưu tiên MCP schema/list/update, media maintenance, Connect writers và marketplace serialization. Regression hiện có: REST thấy 2 attachments nhưng MCP chỉ thấy 1.
- Phân biệt origin/provenance thực sự với ownership/attachment; chỉ drop origin relationship/column khi consumer còn lại = 0 và provenance cần giữ đã có vị trí phù hợp.
- Giữ Template, FieldDef, NoteType, version/release/subscription và release pins: đó là dữ liệu nghiệp vụ hiện tại.

**Đạt khi:** REST/MCP/Connect đồng nhất; attach standalone/market copy/repeated occurrence, rename binding và template retirement đúng; không còn consumer hiểu origin là toàn bộ attachment.

### R5 — Field-name identity: việc riêng sau retirement

Đổi tên Field hiện sửa JSON của mọi Note và tạo FieldRenameJob. Đây là coupling về identity, không phải model nghỉ.

- Điều tra đầy đủ key-by-name trong Note JSON, overlay, release atoms, media, search/TTS, import và rendering.
- Thiết kế lựa chọn dựa trên stable FieldDef ID và invariant array/list hiện hành; so sánh ít nhất hai phương án lưu trữ trước schema change.
- Chỉ retire FieldRenameJob sau khi rename mới không còn cần rewrite Note và toàn bộ readers/writers đã cutover. Không ghép thay identity Field vào cùng DDL xóa CardProgress/Card.

## 5. Validation và vận hành cho từng đợt

1. Rehearsal trên MySQL local cách ly/backup mới; snapshot subject state/hash/revision, ReviewEvent/history facts và receipt trước/sau. Không lấy state local làm source overwrite VPS.
2. Chạy modular test tối thiểu theo phạm vi đổi. Với clone: owner và installed clone, nhiều installs cùng source, source Note và local-added Note. Với session: lease cũ, duplicate/retry, failed commit rollback, expired membership và restore frontend.
3. Kiểm migration chain từ đầu và upgrade từ schema hiện hành; bật startup maintenance trong rehearsal để bắt việc tái tạo bảng nghỉ. Test downgrade không được giả vờ tái tạo dữ liệu đã purge: cần restore archive đã xác minh.
4. Deploy PR code bỏ consumer trước PR DDL drop. Trước DDL VPS, kiểm các process web/Connect/worker cùng contract, session/batch inventory và backup restore. Window dừng ghi nếu cần DDL/data cutover phải được ghi cụ thể trong runbook của PR.
5. Sau deploy/DDL: canonical state/read audit, smoke browse/study/import/clone, schema reflection và SQL trace; so checksum/counter các dữ liệu cần giữ. Rollback về release tương thích với schema đã contraction, hoặc restore/reconcile backup vào môi trường cách ly; không đưa bảng tiến độ đóng băng trở lại làm authority.

Các kiểm tra toàn bộ collection hiện chỉ phục vụ audit offline. Không thêm full scan/hash audit vào mỗi request Browse/study. Cũng không bỏ validation NOTE hiện hành hay semantics `due_day`/`due_at` chỉ vì có tên “legacy”: hai anchor còn có ý nghĩa scheduling và thuật toán `legacy-anki` vẫn là thuật toán được dùng.

## 6. Trạng thái và công việc kế tiếp

| Đợt | Trạng thái |
| --- | --- |
| R0 local -> VPS: audit progress hiện hành | **DONE**, cả hai DATA_READY, không có progress pending để chuyển |
| R1 bốn model không còn consumer | READY FOR IMPLEMENTATION; archive evidence + historical migration contract còn phải làm |
| R2 CardProgress consumers -> archive/drop | PLANNED; data gate đã qua, code/wire/Connect gates chưa thực hiện |
| R3 Card/P11 | IN PROGRESS ở worktree Claude; review này không chứng nhận diff chưa commit của worktree |
| R4 origin Template | PLANNED, còn consumer sai nghĩa |
| R5 Field-name identity | FOLLOW-UP DESIGN, không phải model có thể drop hiện tại |

Validation của công cụ: **12 test PASS**; modular runner sau khi cập nhật mapping: **25 test PASS**. Báo cáo không đánh dấu một bước retirement đã xong chỉ vì audit dữ liệu đã qua.
