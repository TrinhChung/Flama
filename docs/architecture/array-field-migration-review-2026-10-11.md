# Review migration trường array trên bản dump production local

> Ngày: 2026-10-11 (Asia/Tokyo) | Chế độ: INVESTIGATE
> Code được review: HEAD `e5d8872d` và script migration chưa commit.
> Database kiểm tra: MySQL `localhost:3306/nihongo`.

> Đây là audit trước rollout của script Gemini ban đầu. Script đó đã được lưu ngoài git; triển khai tiếp theo dùng manifest ID và `scripts/migrations/array_cutover.py`. Trạng thái khắc phục và kết quả vận hành nằm trong [runbook cutover](../runbooks/ARRAY_FIELD_CUTOVER_20261011.md).

## Kết luận

**Chưa đủ điều kiện nghiệm thu toàn bộ tính năng hoặc đưa migration lên production.**

Migration đã thực thi trên local trước khi bắt đầu review này. Đối soát trực tiếp với `static/tmp/flama_dump.sql.gz` xác nhận dữ liệu ngoài phạm vi chuyển đổi giữ nguyên và dữ liệu đích khớp parser. Tuy nhiên, có lỗi hiển thị đã tái hiện, xung đột quy tắc loại trùng khi chỉnh sửa, và thiếu ghi nhận thay đổi cho marketplace release. Kết luận `APPROVED & CLEAN (100% Pass, 0 Regressions)` trong báo cáo kết quả đang rộng hơn bằng chứng kiểm thử.

Review này chỉ đọc MySQL bằng transaction `READ ONLY`, kiểm tra parser/renderer trên bộ nhớ và chạy test SQLite/frontend riêng. Không chạy `--apply`, không khởi động `wsgi.py`, không sửa application code hay dữ liệu local/production.

## Phạm vi thực tế và nguồn dữ liệu

| Thành phần | Vai trò | Migration đang xử lý |
|---|---|---|
| `field_defs` | Schema field đang làm việc; thuộc một NoteType, có ID ổn định | SQL trực tiếp đổi `field_type` |
| `notes.field_values` | Nội dung Note đang làm việc; JSON dùng tên field làm key | SQL trực tiếp chuyển delimiter thành chuỗi xuống dòng |
| `deck_working_dirty_entities`, revision của listing | Journal giúp phát hiện thay đổi để phát hành | Không được script cập nhật |
| `deck_release_changes`, `deck_release_note_checkpoints` | Dữ liệu đã phát hành; hệ thống clone đọc theo release | Giữ dữ liệu cũ; chưa có release chứa migration |
| `DeckInstall.applied_release_id` và clone overrides | Release đã cài và thay đổi riêng của người học | Không có xử lý chuyển đổi/rebase riêng |
| `templates`, renderer backend/frontend | Consumer quyết định cách hiển thị dữ liệu | Template cũ chưa được cập nhật đồng bộ |

Luồng đang chạy là `field_defs + notes` → renderer/template đối với nội dung làm việc. Deck đã cài đọc release đã pin → overlay → binding → renderer. Hai luồng phải được kiểm chứng riêng; số row SQL cập nhật không chứng minh cả hai hoạt động đúng.

## Kết quả kiểm tra độc lập

| Kiểm tra | Kết quả |
|---|---|
| Note trong dump và MySQL hiện tại | 41.507; không mất/thêm Note |
| Note trong phạm vi migrate | 41.199, thuộc 5 NoteType có dữ liệu |
| Note ngoài phạm vi | 308; field values, tags, identity và timestamp khớp dump |
| Thay đổi field ngoài phạm vi, key JSON, identity, tags | 0 sai khác |
| Giá trị đích so với parser chạy trên dữ liệu gốc | 0 sai khác |
| FieldDef đổi kiểu so với dump | 70; nằm trong 20 NoteType, không chỉ 5 NoteType có dữ liệu |
| Source HTML/CSS của 30 template có trong dump | 0 thay đổi; MySQL hiện có thêm một template standalone |
| Revision và release pointer của 22 listing có trong dump | 0 thay đổi |
| Giá trị bị `array_value_problem()` từ chối | 139 giá trị, thuộc 134 Note, đều do `duplicate_item` |
| Cặp lệch Collocation / Synonym / Antonym | 1 / 64 / 100; tổng 165 lần lệch, thuộc **113 Note khác nhau** |
| Test backend tập trung | 11 test trong 2 file pass |
| Test frontend tập trung | 12 test trong 2 file pass |

Đối soát dùng giá trị JSON đã decode, không so sánh thứ tự key hoặc byte của bản serialize MySQL. Việc giá trị mới khớp parser chứng minh migration chạy đúng parser đó; ý nghĩa của việc tách và hành vi hiển thị cần kiểm tra riêng.

Các artifact đầy đủ được giữ tại `.agents/reviews/array-migration-20261011/`, gồm `array_review_dump_comparison_20261011.json`, `array_review_20261011.json`, fixture DOM và `invalid_array_values.json` chứa toàn bộ Note ID/field không khớp validator. Thư mục này được git ignore; khi chia sẻ review cần gửi kèm artifact cần thiết.

## Findings

### F1 — [P1] Dữ liệu đã đổi nhưng template En4Everyone ghép các cặp thành một mục

- **Observed:** Script lưu các mục bằng `\n`. Renderer đổi xuống dòng trong text HTML thành `<br>`. Template En4Everyone hiện lấy `.textContent` từ `coll-raw` / `collvi-raw`, rồi mới `.split(";")`. DOM `textContent` nối text hai bên `<br>`; delimiter mới không còn để tách.
- **Evidence:** `scripts/migrations/migrate_db_to_arrays.py:233,503`; `app/services/flashcard_renderer.py:470,484,1105`. Template DB `f6d63262-7ad8-4694-af0c-4bd8b0519c61`, `back_html` dòng 107–126; template `0ff348a2-4896-4ba7-a7f6-99708e3e33de` cũng giữ hàm cũ.
- **Reproduction:** Note `0cfcd2d6-8e4c-42c0-8b3b-a05ce7b9aa1b` có 6 mục EN và 6 mục VI. Gọi renderer thực tế rồi đọc DOM bằng jsdom cho thấy mỗi cột có 5 `<br>`, nhưng `splitBySemicolon(element.textContent)` trả **1 mục**. Đây là lỗi hiển thị đã tái hiện sau migrate.
- **Potential concern:** Kế hoạch cắt template sang Mustache loop cũng chưa khả dụng: `build_render_context()` trả chuỗi cho array; `patchRenderContext()` frontend cũng trả chuỗi. `{{#Meaning}}<li>{{.}}</li>{{/Meaning}}` với hai mục hiện render một `<li>`.
- **Impact:** Mất cấu trúc các hàng song ngữ khi hiển thị; mục tiêu bỏ JS split chưa hoàn thành.
- **Unknowns:** Chưa chạy UI trình duyệt của phiên study đang mở hoặc mọi template/version đã pin. Việc thay renderer cần bảo toàn cách dùng field như chuỗi trong template hiện có, không đổi toàn bộ context sang list một cách mặc định.

### F2 — [P1] Giữ duplicate trong migration nhưng editor tự loại duplicate khi lưu

- **Observed:** `split_paired_list(..., preserve_duplicates=True)` giữ đúng các bản dịch lặp. `normalizeArrayValue()` lại loại dòng trùng không phân biệt hoa thường. Validator của endpoint conversion cũng từ chối dòng trùng.
- **Evidence:** `scripts/migrations/migrate_db_to_arrays.py:207,345`; `frontend/src/lib/arrayField.ts:47`; `app/validators/field_array_conversion.py:83`; `app/services/field_array_conversion_service.py:103`. Browse edit gọi normalizer ở `frontend/src/features/browse/components/BrowseCardEditForm.tsx:71`; quick edit gọi ở `frontend/src/features/study/hooks/useStudyQuickEditForm.ts:298`.
- **Reproduction:** Dùng chính normalizer TypeScript trên `Coollocation_VI` của Note mẫu F1 biến **6 mục thành 5**, vì hai cụm EN khác nhau cùng dịch thành `xử lý đồng thời`. Việc lưu chỉnh sửa có thể làm lệch các hàng còn lại, kể cả khi người dùng sửa field khác.
- **Potential concern:** Có 139 giá trị thuộc 134 Note không khớp conversion validator hiện hành. Phân bố: `Coollocation_VI` 36, `Synonym_VI` 60, `Antonym_VI` 36, `Synonym` 1, `reading` 3, `translation_vi` 2, `Nghĩa` 1. Endpoint không nhận option `deduplicate`/`preserveDuplicates`; thêm option đó theo kế hoạch hiện sẽ nhận `VALIDATION_ERROR`.
- **Impact:** Backfill giữ dữ liệu nhưng luồng chỉnh sửa phá đối ứng song ngữ. Không được sửa bằng cách deduplicate độc lập các cột để làm validator pass.
- **Unknowns:** Đã chứng minh normalizer đổi nội dung; chưa thực hiện save trên dữ liệu MySQL thật để tránh ghi dữ liệu trong lượt review.

### F3 — [P1] SQL trực tiếp bỏ qua journal phát hành marketplace

- **Observed:** Script chỉ cập nhật `field_defs` và `notes`. Service conversion chuẩn còn gọi `mark_field_def_changed()`, `mark_note_field_batches_changed()` và ghi audit trong cùng transaction.
- **Evidence:** Script dòng 414–424,591–597; `app/services/field_array_conversion_service.py:170,176`; `app/services/deck_working_tree_service.py:247,291`. `app/services/deck_release_service.py:975` có đường sparse diff trả `changes=[]` khi working revision bằng base revision và không có dirty row.
- **Database evidence:** Revision/release pointer của toàn bộ 22 listing trong dump không đổi sau migrate; không có dirty atom đổi `field_type` cho array. Có 48 historical schema change atom cho field hiện đã thành array vẫn chứa kiểu `text`/`richtext`, và không có schema atom release kiểu array. Local có 28 deck installs, gồm 27 install theo release và 1 legacy snapshot.
- **Potential concern:** Thay đổi thật không được phản ánh vào điều kiện chọn sparse diff. Phát hành sau đó có thể bỏ sót backfill. Việc giữ release cũ bất biến là đúng; thiếu phần ghi nhận nội dung làm việc để tạo release mới mới là vấn đề.
- **Impact:** Owner và clone có thể tiếp tục dùng các phiên bản schema/content khác nhau mà luồng publish không phát hiện đủ thay đổi.
- **Unknowns:** Chưa publish hoặc rebase trên bản local. Cần chứng minh source → release mới → install update giữ nguyên overlay của người học; không sửa trực tiếp historical release/checkpoint để đồng bộ.

### F4 — [P1] Commit schema trước khi xác thực toàn bộ dữ liệu tạo trạng thái chuyển đổi dở dang

- **Observed:** `execute_migration()` commit kiểu field trước, sau đó mới parse Note và commit từng chunk. Nếu parsing, assertion key-set hoặc SQL gặp lỗi, schema và các chunk đã commit không được rollback cùng nhau.
- **Evidence:** `scripts/migrations/migrate_db_to_arrays.py:643–663,588–602`. Với Note thiếu một field đích, script tự thêm key ở dòng 508 rồi assertion dòng 574 thất bại. Metrics chỉ được lưu khi toàn bộ quá trình đã chạy xong ở dòng 680.
- **Potential concern:** Transaction theo chunk chỉ bảo vệ chunk hiện tại, không bảo vệ toàn bộ cutover type/content. Không có checkpoint phục hồi hoặc cơ chế rollback riêng cho phần đã commit.
- **Impact:** Lần chạy lỗi có thể để field khai báo array nhưng còn dữ liệu delimiter cũ, cùng các Note đã đổi/ chưa đổi xen kẽ.
- **Unknowns:** Lần local đã hoàn thành không có sai khác với parser. Chưa có kiểm thử cố tình fail giữa các chunk và chứng minh phục hồi/cutover.

### F5 — [P1] Ghi toàn bộ JSON không kiểm tra thay đổi đồng thời

- **Observed:** Script `SELECT id, field_values`, dựng bản sao trên bộ nhớ, rồi `UPDATE notes SET field_values=:fv ... WHERE id=:id`. Không lock row khi đọc hoặc kiểm tra expected value/revision khi ghi.
- **Evidence:** `scripts/migrations/migrate_db_to_arrays.py:467–478,500,577–581,591–597`. Assertion field ngoài phạm vi chỉ so hai dict trên bộ nhớ lấy từ cùng snapshot. Endpoint chuẩn khóa dữ liệu và kiểm tra giá trị expected trong `field_array_conversion_service.py:134–153`.
- **Potential concern:** Nếu app/Connect/TTS sửa field khác giữa SELECT và UPDATE, script có thể ghi đè thay đổi đó bằng JSON cũ mà assertion vẫn pass.
- **Impact:** Có nguy cơ mất cập nhật khi chạy với writer hoạt động. Đối soát dump trong lượt này không phát hiện trường hợp như vậy.
- **Unknowns:** Chưa kiểm thử writer đồng thời; chưa xác nhận maintenance window hoặc cơ chế khóa/chống stale write khi đưa script vào quy trình vận hành.

### F6 — [P2] Scope schema theo tên khác scope dữ liệu theo ID; target local chưa được cưỡng chế

- **Observed:** SQL đổi schema dùng `nt.name`, trong khi migration Note dùng 5 UUID cố định. Trong local, 20 FieldDef thuộc 5 NoteType có dữ liệu được chuyển cùng Note; **50 FieldDef khác thuộc 15 NoteType không có Note riêng** cũng bị đổi kiểu. 59/70 FieldDef nằm trên NoteType được ghi nhận trong `note_type_installs`.
- **Evidence:** `scripts/migrations/migrate_db_to_arrays.py:326–371,390–424`; truy vấn census độc lập và so sánh 462 FieldDef trong dump.
- **Potential concern:** Bản cài từ marketplace chưa được phân tích như một scope riêng. Trên dataset khác, một NoteType cùng tên nhưng khác UUID có thể bị đổi schema mà Note của nó không được chuyển. `create_db_engine()` đọc `DB_HOST` từ environment và không kiểm tra localhost dù docstring nói local.
- **Impact:** Scope dễ vượt ngoài manifest đã review; lệnh `--apply` không tự bảo đảm chỉ ghi local như yêu cầu thử nghiệm hiện tại.
- **Unknowns:** Trong dump này, các NoteType ngoài 5 ID không có Note riêng. Cần thống nhất manifest theo ID, lineage và target DB trước lần chạy tiếp theo.

### F7 — [P2] Báo cáo nghiệm thu đang gộp số lần lệch với số Note và bỏ qua regression đã tái hiện

- **Observed:** `DATABASE_ARRAY_MIGRATION_RESULT.md:9` ghi `0 Regressions`; phần 3.3 gọi 165 lần lệch là 165 Note. Thực tế union Note ID trong telemetry là **113**. Báo cáo ghi 61 `Synonym_VI` có duplicate, nhưng scan theo field cho thấy **60 `Synonym_VI` + 1 `Synonym`**.
- **Evidence:** Báo cáo dòng 224–235; `migration_metrics.json`; scan bằng validator thực tế và reproduction F1/F2.
- **Potential concern:** 100% SQL được ghi thành công bị diễn giải thành 100% tính năng hoạt động đúng. Bộ test SQLite/frontend hiện pass không kiểm tra template DB đang dùng với nội dung đã migrate.
- **Impact:** Gate approve hiện không phản ánh rủi ro người dùng sẽ gặp khi học/chỉnh sửa hoặc publish.
- **Unknowns:** Gemini còn đang chỉnh artifact khi review; các số trong tài liệu này phản ánh snapshot đọc ngày 2026-10-11.

## Điều kiện cần kiểm chứng trước nghiệm thu

1. Template và hai renderer hiển thị đúng dữ liệu mới; mẫu F1 phải có 6 hàng sau render, và đường Mustache loop nếu chọn dùng phải thật sự lặp từng mục. Kiểm cả owner, clone, template/version đã pin và quick edit.
2. Round-trip xem → sửa → lưu giữ đủ mục lặp và thứ tự cặp. Thống nhất quy tắc giữa migration, conversion validator và normalizer; giải quyết 139 giá trị hiện không khớp quy tắc.
3. Ghi nhận backfill vào working-tree tracking và chứng minh publish/rebase thấy thay đổi, đồng thời giữ overlay và release lịch sử.
4. Có manifest theo ID, kiểm tra target local, preflight toàn bộ dữ liệu, thử lỗi giữa chunk và thử writer đồng thời hoặc xác nhận cách dừng writer.
5. Báo cáo tách tỷ lệ thực thi SQL, hợp lệ theo contract và hành vi UI. Ghi rõ 165 lần lệch thuộc 113 Note, 11 rỗng cách đọc và 24 rỗng nghĩa là dữ liệu cần đối soát, không tự sửa nghĩa/điền nội dung.

## Lệnh test đã chạy

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_field_array_conversion.py tests/test_array_field_type_migration.py --backend-only
.\.venv\Scripts\python.exe scripts/run_tests.py --file frontend/src/lib/arrayField.test.ts frontend/src/features/note-types/lib/arrayConversion.test.ts --frontend-only
```

Chạy lại đối soát dump (chỉ đọc DB) bằng artifact local:

```powershell
.\.venv\Scripts\python.exe .agents/reviews/array-migration-20261011/array_review_compare_dump_20261011.py
```
