# Rà soát model legacy và dữ liệu suy ra còn lưu riêng

> Ngày: 2026-10-12. Chế độ: INVESTIGATE. Baseline: `9b5db52e41ab94dcadbf68b5b58cc5ec6dc82b87`, branch `feat/typing-back-audio-usage`.
> Phạm vi: root checkout; không đánh giá các thay đổi chưa commit trong worktree P11 của Claude. Không thay đổi application code, migration hoặc database thật.

## Kết luận

Đã kiểm kê **110 model ORM / 110 bảng trong metadata runtime**. Có **4 model chỉ còn được đăng ký tại bootstrap, không tìm thấy reader/writer nghiệp vụ trong repo**: `VocabularyColumnPreference`, `StudyProgressBackfillRun`, `StudyProgressBackfillCheckpoint`, `StudyProgressBackfillDisposition`.

`CardProgress` là ứng viên retirement đáng xử lý cùng Card, nhưng vẫn có nhánh LEGACY hoạt động trong code. Các dấu vết origin của Template cũng cần tiếp tục cutover. Một phụ thuộc có chi phí tương tự tạo Card hàng loạt là lưu `Note.field_values` theo tên Field: rename hiện phải sửa tất cả Note. Đây là việc tách identity, không phải lý do xóa `FieldDef` hoặc `FieldRenameJob` ngay.

| Thành phần | Phân loại quan sát được | Mức sẵn sàng để dọn |
| --- | --- | --- |
| `VocabularyColumnPreference` | Model của UI vocabulary lesson đã nghỉ | Không tìm thấy consumer; cần kiểm tra dữ liệu còn lưu trước khi drop |
| `StudyProgressBackfillRun` | Accounting của backfill Phase 4 đã nghỉ | Không tìm thấy consumer runtime; migration 39 vẫn import model |
| `StudyProgressBackfillCheckpoint` | Checkpoint/lease của backfill cũ | Cùng nhóm trên; FK tới run |
| `StudyProgressBackfillDisposition` | Bằng chứng xử lý/quarantine của backfill cũ | Cùng nhóm trên; cần giữ được evidence lịch sử nếu có dữ liệu |
| `CardProgress` | Tiến độ LEGACY, projection cũ của NOTE | Còn reader/writer, startup patch, công cụ và dependency migration; chưa thể drop riêng lẻ |
| `Card` | Presentation vật chất hóa theo Note/application | P11 đang thay bằng presentation suy ra; session, Connect, clone và ID cũ còn phụ thuộc |
| `Template.note_type_id` / `NoteType.templates` | Quan hệ origin cũ, song song với attachment mới | Còn consumer đang coi origin là toàn bộ attachment; dọn consumer trước |
| `FieldRenameJob` / tên key của `field_values` | Rename đang ghi O(N), model job vẫn hoạt động | Cần điều tra/refactor identity riêng; không phải model chết |

Không có bằng chứng từ lần rà này để kết luận toàn bộ các model khác đều có thiết kế tối ưu. Kết quả xác định consumer còn tồn tại và các ứng viên retirement rõ nhất, không coi bảng ít consumer hoặc dữ liệu suy ra là mặc nhiên dư thừa.

## Phương pháp và hệ thống dữ liệu chính

- Parse AST các file `models/*.py` để lấy class có `__tablename__`; tìm class/table/module references trong `app/`, `models/`, `scripts/`, `tests/`, `migrations/` và frontend cho các ứng viên.
- Phân biệt import để đăng ký metadata với đọc/ghi thực tế; truy tiếp service/repository/API của các nhóm dễ bị nhận nhầm.
- Dùng `create_audit_app` với SQLite memory, tắt startup maintenance và connectivity; `configure_mappers()` PASS. Probe metadata không thực hiện database query.
- Kiểm tra migration 39, 50 và frozen metadata lịch sử; đọc các báo cáo cutover như bằng chứng lịch sử, không coi là trạng thái VPS được xác minh hôm nay.

| Dữ liệu | Nơi giữ dữ liệu chính hiện tại | Ý nghĩa với cleanup |
| --- | --- | --- |
| Content | `Note`, `FieldDef`, `NoteType` | Không thay bằng Card và không xóa để xử lý presentation |
| Attachment/binding | `StudyApplication` | Quan hệ Template với NoteType thực tế; origin trên Template không bao quát tất cả attachment |
| Tiến độ NOTE | `StudyProgressSubject` | Row theo learner/logical Note, không cần projection mới vào `CardProgress` |
| Tiến độ LEGACY | `CardProgress` | Vẫn là dữ liệu chính cho route LEGACY; không được coi tất cả row là cache |
| Lịch sử và replay | `ReviewEvent`, `StudyProgressHistoryFact`, `StudyAuthorityCommandReceipt` | Có consumer hiện tại, phải giữ lịch sử và idempotency |
| Phạm vi session | `StudySessionCard`, authority pins, commits/batches | Chỉ chứa membership/lease thực tế, khác với materialize Card cho mọi Note |
| Release/clone | Releases, template pins, memberships, checkpoint và overlay | Giữ phiên bản đã publish, không thể suy ra đầy đủ từ source live |
| Tổng hợp nhanh | Review analytics generations/daily counts, deck count snapshots/revisions | Dữ liệu suy ra có consumer và validation/invalidation contract hiện tại |

## Các phát hiện

### F1 — VocabularyColumnPreference không còn consumer nghiệp vụ

- **Observed:** Model giữ độ rộng cột vocabulary lessons, chỉ còn import tại app bootstrap. Route POST `/column-widths` đã trả response cấu trúc legacy bị loại bỏ (`410`); không đọc/ghi bảng.
- **Evidence:** [model](../../models/column_preference.py:6), [registration](../../app/__init__.py:149), [route](../../app/routes/vocabulary.py:684), [410 helper](../../app/routes/vocabulary.py:75). Tìm cả tên class, table, module và các biến thể column preference trong source không thấy persistence consumer. Worksheet `column_widths` là options riêng, không tham chiếu model này.
- **Potential concern:** Metadata vẫn chứa bảng nghỉ, nên `db.create_all()` còn có thể tạo lại khi bật maintenance hoặc dựng test DB.
- **Impact:** Đây là ứng viên dọn nhỏ và độc lập với P11, giảm schema/metadata dư; không có bằng chứng rằng bỏ nó cải thiện hot path học.
- **Unknowns:** Số row, giá trị người dùng muốn lưu lại, SQL/script bên ngoài repo và schema thật trên VPS chưa được kiểm tra.

### F2 — Ba model backfill Phase 4 đã hết consumer runtime, nhưng còn giữ migration chain

- **Observed:** Cả ba model chỉ được import trong `app/__init__.py` để đăng ký. Không tìm thấy service/repository/CLI/test hiện tại dùng class hoặc bảng. Migration 39 vẫn import cả ba và dùng `__table__` trong `TARGET_TABLES`.
- **Evidence:** [bootstrap](../../app/__init__.py:140), [run](../../models/study_progress_backfill_run.py:22), [checkpoint](../../models/study_progress_backfill_checkpoint.py:18), [disposition](../../models/study_progress_backfill_disposition.py:24), [migration 39 imports](../../migrations/versions/20260913_000039_add_study_progress_shadow_schema.py:24), [table list](../../migrations/versions/20260913_000039_add_study_progress_shadow_schema.py:39).
- **Potential concern:** Xóa file model trực tiếp sẽ làm import migration 39 hỏng. Dump/drop dữ liệu run còn có thể mất bằng chứng backfill/quarantine, dù không phải tiến độ NOTE hiện hành.
- **Impact:** Có thể loại khỏi runtime sau khi giải quyết dependency migration và lưu giữ evidence cần thiết. FK yêu cầu xử lý disposition/checkpoint trước run; `disposition.run_id` là `RESTRICT`, `checkpoint.run_id` là `CASCADE`.
- **Unknowns:** Số run chưa kết thúc, evidence lịch sử cần giữ và tác vụ vận hành ngoài repo. Không chứng minh các bảng rỗng bằng việc không còn consumer code.

### F3 — CardProgress là legacy thật, nhưng chưa bị loại khỏi runtime

- **Observed:** NOTE hiện dùng consolidated subject row. LEGACY vẫn query/update/create `CardProgress`; content-wide discovery còn đọc projection cũ để tìm learners liên quan. Enrollment mới có tiến độ LEGACY bị từ chối, không được tự migrate sang NOTE.
- **Evidence:** [authority repository](../../app/repositories/study_authority_repository.py:3), [projection_is_live](../../app/repositories/study_authority_repository.py:75), [direct review NOTE branch](../../app/services/study_service.py:900), [legacy create](../../app/services/study_service.py:953), [session legacy create](../../app/services/study_session_service.py:2658), [enrollment refusal](../../app/services/study_authority_enrollment_service.py:231), [startup compatibility patches](../../app/startup_schema.py:387), [frozen migration parent imports](../../migrations/retired_note_progress_tables.py:36).
- **Potential concern:** Có thể xóa nhầm dữ liệu chính của learner LEGACY. Xóa ORM file còn làm hỏng các import service/model/migration. Không phải chỉ bỏ FK `CardProgress.card_id` là hoàn tất retirement.
- **Impact:** Là ứng viên cleanup lớn cùng Card khi consumer LEGACY được giải quyết. Readiness hiện đã phân biệt `LEGACY_LEARNERS` và `UNENROLLED_USERS`; phải xác minh cohort và các session/consumer còn cần compatibility trên database đích.
- **Unknowns:** Báo cáo P9 ghi 0 learner LEGACY/unenrolled và 18/18 NOTE vào 2026-10-02, đồng thời chốt giữ v2/v3, ordinal fallback và `card_progress` trong phạm vi đó. Đây là lịch sử, không phải audit VPS ngày 2026-10-12. [P9 closeout](../task/decoupling/P9_CLOSEOUT_2026-10-03.md:21), [phạm vi cũ](../task/decoupling/P9_06_CUTOVER_REPORT_2026-10-02.md:5).

### F4 — Quan hệ origin của Template vẫn được dùng như attachment đầy đủ

- **Observed:** `Template.note_type_id` được ghi chú là legacy origin, nullable và FK `SET NULL`; attachment reusable thuộc `StudyApplication`. Tuy vậy MCP schema/list còn tính template bằng `nt.templates`; một số maintenance/update consumer còn query theo origin.
- **Evidence:** [Template](../../models/template.py:11), [NoteType relationship](../../models/note_type.py:53), [MCP count](../../app/services/mcp/note_type_tools.py:65), [MCP schema](../../app/services/mcp/note_type_tools.py:99), [MCP update](../../app/services/mcp/note_type_tools.py:960), [media scope](../../app/services/flashcard_media_normalizer.py:441). Probe trong [review trước](./CARD_TEMPLATE_DECOUPLING_REVIEW_2026-10-11.md) cho thấy REST có 2 attachment còn MCP báo 1.
- **Potential concern:** Hai quan hệ cùng tồn tại nhưng không cùng nghĩa; consumer origin có thể bỏ sót template được attach từ library/marketplace.
- **Impact:** Đây là cleanup consumer/relationship đáng ghép với P11/attachment cutover. Xóa `Template` hoặc `NoteType` không giải quyết vấn đề; drop origin column khi reader chưa chuyển sẽ làm lỗi runtime.
- **Unknowns:** Danh sách consumer còn cần origin như provenance thực sự; trạng thái cutover trong worktree P11 chưa được audit ở đây.

### F5 — Field rename là phụ thuộc ghi hàng loạt tương tự, nhưng FieldRenameJob vẫn hoạt động

- **Observed:** `Note.field_values` dùng tên Field làm key. `_rename_field_values` tạo `FieldRenameJob`, count và `.all()` toàn bộ Note cùng user/NoteType, chuyển key cũ sang key mới rồi ghi lại JSON cho từng Note.
- **Evidence:** [rename entry](../../app/services/flashcard_content_service.py:647), [rename implementation](../../app/services/flashcard_content_service.py:1738), [full Note load](../../app/services/flashcard_content_service.py:1762), [array conversion guard](../../app/services/field_array_conversion_service.py:79), [job model](../../models/field_rename_job.py:7).
- **Potential concern:** Tên hiển thị đồng thời là khóa lưu trữ; thao tác đổi tên metadata kéo theo đọc/ghi O(N) và transaction lớn. Stable FieldDef-ID binding của template chưa tự loại bỏ key theo tên trong Note JSON.
- **Impact:** Đây là ứng viên điều tra tách identity tiếp theo nếu mục tiêu là giảm coupling và write amplification. Xóa model job riêng lẻ làm hỏng rename/guard hiện tại, còn nguyên nguyên nhân quét Note.
- **Unknowns:** Chi phí trên MySQL với các NoteType lớn, toàn bộ consumer field-name và dữ liệu legacy/overlay. Chưa thiết kế target schema hay migration trong review này.

### F6 — Nhóm NOTE progress cũ đã được contraction, không phải backlog mới

- **Observed:** `study_progress_states`, `study_progress_availability`, `study_progress_contributors`, `study_progress_lineage_refs`, `study_authority_subject_tokens` không còn runtime model. Migration 50 drop năm bảng; definition cũ được giữ trên private `MetaData` dành cho migration chain.
- **Evidence:** [migration 50](../../migrations/versions/20261003_000050_drop_retired_note_progress_tables.py:38), [frozen definitions](../../migrations/retired_note_progress_tables.py:1), [runbook ghi nhận thực hiện 2026-10-04](../runbooks/P10_09_RETIRED_TABLES_DROP_RUNBOOK.md:5), [tests](../../tests/test_study_retired_tables_migration.py:1).
- **Potential concern:** Nhìn thấy class cũ trong `migrations/` rồi xóa nhầm frozen definition sẽ làm hỏng dựng schema từ migration cũ; chúng không đăng ký lại bảng runtime.
- **Impact:** Không cần mở một đợt xóa model cho năm bảng này nữa. `HistoryFact.contributor_id` vẫn giữ provenance của fact cũ, còn được history-cut service đọc/serialize; cột mồ côi FK không đồng nghĩa cột không dùng.
- **Unknowns:** Schema database đích đã lên migration 50 hay chưa. Legacy vocabulary Level/Topic/Lesson/Entry/Progress/MigrationMap cũng không còn runtime model; tài liệu ghi đã dọn nhưng chưa kiểm schema VPS hôm nay.

## Các nhóm dễ bị nhận nhầm là legacy

| Nhóm | Consumer/lý do giữ hiện tại |
| --- | --- |
| `StudySessionCard`, `StudySessionAuthorityPin` | Membership thật, lease/CAS và replay; phải chuyển identity khi bỏ Card, không bỏ dữ liệu membership. [model](../../models/study_session_card.py:18), [session service](../../app/services/study_session_service.py:1616) |
| `ConnectSourceCardRef` | External card ID, `source_ord`, Note provenance và applied revision fence. Bỏ dependency Card không làm mất nhu cầu bảng ref. [model](../../models/connect_source_card_ref.py:31) |
| `ReviewEvent`, `StudyProgressHistoryFact`, receipts, lifecycle events | Review history, algorithm history cuts, reset/tombstone và idempotent command replay. [history cut](../../app/services/study_algorithm_history_cut_service.py:483), [receipt fingerprint](../../app/services/study_authority_receipt_service.py:163) |
| `StudyAuthorityEnrollment`, `StudyAuthorityStorageProfile` | Runtime vẫn đọc/lock enrollment và storage profile. Docstring của storage profile còn nói profile cũ nhưng code supported chỉ `CONSOLIDATED_V1`; đây là docstring stale, không phải bảng chết. [repository](../../app/repositories/study_authority_repository.py:48) |
| `NoteTypeInstall`, `NoteTypeReview` | Marketplace vẫn tạo install, subscription, rating và giữ linkage schema copy của clone. [install/rate](../../app/services/flashcards_share_service.py:899), [clone install](../../app/services/flashcards_share_service.py:2660) |
| `DeckClone*`, releases, checkpoints, template pins, rebase/change-request | Overlay/membership/version history riêng; không được thay bằng source live. [clone scope](../../app/services/flashcards_share_service.py:2982) |
| `ConnectNoteRef`, `ConnectNoteTypeRef`, `ConnectSourceNoteRef` | Ref đầu cấp numeric ID cho protocol mining; các ref còn lại giữ source model/note identity và hash phục vụ import/sync. [numeric ref](../../app/services/connect/actions.py:309), [import ref](../../app/services/connect/import_session.py:463), [source note](../../app/services/connect/import_cards.py:617) |
| `MediaFieldMigrationRun/Item` | CLI typed-media migration và rollback hiện còn ghi/đọc run/items. [writer](../../app/services/flashcard_media_normalizer.py:289), [rollback reader](../../app/services/flashcard_media_normalizer.py:501), [CLI](../../app/cli.py:803) |
| `ImageAsset`, `SharedImageAsset`, `MediaAsset` | Ingestion/processing record, reusable library key và Note media attachment là ba vai trò khác nhau. [ingestion](../../app/services/image_ingestion_service.py:125), [library](../../app/repositories/image_library_repository.py:33) |
| `DailyReviewCount`, analytics head/generation, deck snapshots/revisions | Cache/tổng hợp có phiên bản, kiểm chứng, invalidate và reader hiện tại; không giống materialize Card chỉ để giữ ID. [analytics reader](../../app/repositories/review_analytics_read_repository.py:75), [deck snapshots](../../app/repositories/deck_count_snapshot_repository.py:77) |
| `SchedulerPreset`, `UserSchedulerSettings` | `legacy` còn là mã thuật toán scheduler, không tự chỉ trạng thái model đã nghỉ. [config service](../../app/services/scheduler_config_service.py) |

## Quan hệ FK đã kiểm bằng metadata runtime

| Cột | Đích | ON DELETE |
| --- | --- | --- |
| `card_progress.card_id` | `cards.id` | CASCADE |
| `connect_source_card_refs.card_id` | `cards.id` | SET NULL |
| `study_session_cards.card_id` | `cards.id` | CASCADE |
| `study_progress_backfill_checkpoints.run_id` | `study_progress_backfill_runs.id` | CASCADE |
| `study_progress_backfill_dispositions.run_id` | `study_progress_backfill_runs.id` | RESTRICT |

Không tìm thấy FK runtime từ bảng khác vào `vocabulary_column_preferences`, checkpoint hoặc disposition; hai FK vào run đều thuộc chính nhóm backfill. Các quan hệ trên là metadata ORM, chưa phải reflection MySQL production.

Bootstrap schema mutation được **gated** trong [app/startup.py](../../app/startup.py:42), không chạy mặc định trong mọi lần boot. Khi được bật, `db.create_all()` vẫn tạo mọi bảng còn đăng ký; drop table mà giữ model/import không hoàn tất contraction.

## Validation và phần chưa xác minh

- AST inventory: 110 model có `__tablename__`; audit-factory ORM metadata: 110 bảng, `configure_mappers()` PASS.
- Modular tests: `tests/test_study_retired_tables_migration.py` + `tests/test_study_authority_note_enrollment.py`: **10 tests PASS**, SQLite memory, 2 files, runner 6.16 giây.
- Probe SQLite memory: user có một `CardProgress` với `reps=17`, `revision=5`; enrollment NOTE bị từ chối bằng `LEGACY_PROGRESS_NOT_MIGRATABLE`, dữ liệu sau rollback giữ nguyên. Probe này không chứng minh có learner LEGACY trên VPS.
- Không query/drop/alter database production, không đọc hoặc xuất credential, không chỉnh source/migration, không chạy DDL MySQL.
- Cần xác minh trên database đích: row counts/evidence của 4 model nghỉ; cohort LEGACY/unenrolled và compatibility sessions; Alembic head và bảng dư thực tế. Bản audit code không thể kết luận bảng production rỗng hoặc tất cả old client đã hết hoạt động.

Danh sách review để đưa vào đợt cleanup là **4 model không còn consumer runtime + CardProgress + Card**, kèm consumer origin Template. Field-name identity là việc điều tra riêng. Hai review Card/P11 trước vẫn giữ nguyên các blocker release pin, snapshot cutoff, lease/retry ID và migration ordering.
