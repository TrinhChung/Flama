# Review tiến độ tách Card / Template — 2026-10-11

> Mode: INVESTIGATE. Đối chiếu code tại `cdbd1cc5`, working tree sạch trước review. Chỉ thêm báo cáo; không sửa ứng dụng, schema hoặc dữ liệu thật. Bằng chứng production bên dưới là báo cáo cutover đã lưu, không phải kiểm tra VPS mới.

## Kết luận và tiến độ

Đã tách **tiến độ học** khỏi Card/Template và tách **quyền sở hữu Template** khỏi NoteType. Chưa bỏ entity/bảng `cards`, chưa bỏ `cards.template_id`, và chưa chuyển runtime sang học trực tiếp từ Note + template được chọn mà không cần Card đã materialize. Đây là ba mức hoàn thành khác nhau.

| Phần việc | Trạng thái đối chiếu | Bằng chứng |
|---|---|---|
| Một tiến độ cho learner × Note | Đã có trong code; cutover production được ghi nhận 03/10 | `models/study_progress_subject.py:34`, `:92`; [P10](../task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md), P10-08 |
| Gộp tiến độ NOTE và bỏ năm bảng trung gian | Đã có trong code; contraction production được ghi nhận 04/10 | `app/repositories/study_authority_repository.py:52`; migration 50; P10-09 |
| Template độc lập, gắn nhiều NoteType, binding theo FieldDef ID | Đã triển khai | `models/template.py`; `StudyApplication`; migrations 53–55; `tests/test_template_library.py` |
| Chọn template/binding trước phiên, ghi nhớ và freeze trong phiên | Đã triển khai trong phạm vi composition có sẵn | [GT-18](../task/template-features/GT-18_STUDY_TEMPLATE_PREPARATION.md); commit `cdbd1cc5` sửa lựa chọn ban đầu/ghi nhớ |
| Sửa các writer theo attachment ACTIVE | Đã commit phần CT-R3, vẫn còn đường MCP theo legacy | Commit `80418285`; [CT-R3](../task/template-features/reviews/CT-R3_ATTACHMENT_WRITER_PATHS_2026-10-09.md); finding F4 |
| Không tạo Card khi gắn template/tạo Note | Chưa triển khai | `app/services/template_library_service.py:351`; `app/repositories/template_library_repository.py:120` |
| Bỏ quan hệ Card → Template hoặc bỏ bảng `cards` | Chưa triển khai | `models/card.py:16`; session/Connect/Browse còn dùng Card |
| Bỏ `card_progress` và nhánh LEGACY | Được giữ riêng ngoài phạm vi P10 | P10 §P10-09; model vẫn đăng ký trong startup |

Không quy đổi thành phần trăm: tracker đang đóng phạm vi decoupling đã chốt, không phải một kế hoạch hoàn chỉnh để drop `cards`. Kế hoạch kiến trúc còn cho phép giữ Card như presentation/integration projection (`study-interaction-trigger-algorithm-plan.md:882`, `:903`).

## Nguồn dữ liệu và luồng hiện tại

| Dữ liệu | Nguồn có thẩm quyền / vai trò |
|---|---|
| Nội dung Note và schema field | `notes.field_values`, `field_defs` |
| Template và lịch sử | `templates`, `template_versions`; quyền sở hữu qua `owner_user_id` |
| Thành viên NoteType/template và ánh xạ | `study_applications`, trạng thái ACTIVE/RETIRED và `input_bindings` |
| Card | Presentation/compatibility row; FK tới Note, Template và application; chưa phải đối tượng render thuần tạm thời |
| Tiến độ NOTE | `study_progress_subjects`, unique `(learner_user_id, logical_note_key)`; state, availability và CAS trên cùng dòng |
| Tiến độ LEGACY | `card_progress`; vẫn có nhánh thực thi và frozen rows của learner NOTE |
| Phiên / provenance / lịch sử | Membership phiên còn FK tới Card; Connect còn con trỏ Card và snapshot Note; ReviewEvent/history giữ định danh lịch sử |

Luồng đọc/ghi đã quan sát: tạo Note hoặc gắn application → materialize Card cho occurrence ACTIVE → discovery composition từ Cards → resolve effective template và binding → freeze artifact trong session → trả lời cập nhật tiến độ learner × Note. Với deck cài đặt, vẫn phải giữ scope source/install/local và release pin; không copy source Notes/Cards để né phụ thuộc.

## Findings

### F1 — Blocker bỏ Card: schema và writer vẫn materialize theo template

- **Observed:** `cards.template_id` NOT NULL, FK `templates.id` ON DELETE CASCADE. Card có thêm `application_id` nullable và unique `(note_id, application_id)`, không thay thế Template bằng render selection tạm. Gắn template vẫn bulk INSERT Card cho mỗi Note còn thiếu. Tạo Note/import dùng slot ACTIVE để tạo Card.
- **Evidence:** `models/card.py:16`, `:19`, `:36`; `models/template.py:46`; `app/services/template_library_service.py:351`, `:366`; `app/repositories/template_library_repository.py:107`, `:120`, `:127`, `:144`. Commit `a1a67ce4` ngày 11/10 tối ưu cách INSERT, không bỏ INSERT.
- **Potential concern:** Có thể hiểu nhầm việc độc lập hóa Template hoặc bulk INSERT nhanh hơn là đã bỏ phụ thuộc Card/Template.
- **Impact:** Mỗi application vẫn thêm presentation rows theo số Note; không thể drop cột/bảng khi writer này còn chạy.
- **Unknowns:** Chưa đo số Card/occurrence và thời gian attach trên production trong lần review này.

### F2 — Blocker runtime: chọn template/render/session vẫn bắt đầu từ Card

- **Observed:** Discovery composition lấy Card hợp lệ, group theo `Card.template_id` và `Card.application_id`; chọn composition lọc lại các Card đó. Effective template resolver bắt đầu ở `card.template`. Session open/status/commit cũng truy vấn Card.
- **Evidence:** `app/services/study_composition_service.py:259`, `:266`, `:275`, `:531`; `app/services/effective_template_service.py:64`; `app/services/study_artifact_service.py:122`, `:150`; `app/services/study_session_service.py:600`, `:622`, `:1142`, `:1901`.
- **Potential concern:** UI chọn template trước phiên đã hoàn thành nhưng lựa chọn vẫn giới hạn trong composition backed by Cards.
- **Impact:** Theo đường code này, template thư viện chưa có application/Card trong scope không tự trở thành lựa chọn học. Bỏ materialization mà giữ discovery hiện tại sẽ làm mất composition/thẻ học.
- **Unknowns:** Chưa có acceptance contract riêng cho học trực tiếp từ Note với template chưa materialize.

### F3 — Blocker lifecycle/compatibility: nhiều dữ liệu còn giữ Card identity

- **Observed:** `StudySessionCard.card_id` và `CardProgress.card_id` FK tới Card với CASCADE; Connect ref FK với SET NULL và giữ Note/ordinal. Browse xóa Card cuối sẽ xóa luôn Note. ReviewEvent/history vẫn ghi card/logical-card identity dù đã bổ sung Note attribution.
- **Evidence:** `models/study_session_card.py:18`; `models/card_progress.py:15`; `models/connect_source_card_ref.py:34`; `models/review_event.py:14`; `models/study_progress_history_fact.py:40`; `app/services/browse_card_service.py:1173`, `:1186`. Startup vẫn đăng ký `Card`/`CardProgress` (`app/__init__.py`) và có `db.create_all()` (`app/startup.py:51`).
- **Potential concern:** Xóa bảng/rows Card như một bước cleanup có thể tác động membership/pins đang lease, provenance và nội dung Note.
- **Impact:** Drop vật lý cần chứng minh mọi consumer đã chuyển hoặc có compatibility mapping và dữ liệu restore phù hợp. Đây chưa phải một migration chỉ đổi FK. Browse-delete hiện tại là hành vi content deletion, không phải công cụ loại presentation rows.
- **Unknowns:** Chưa kiểm kê live leases/client versions/FK thực tế trên VPS. Không kết luận cần xóa định danh card trong lịch sử; các fact có thể cần giữ lâu dài.

### F4 — P2 lỗi còn thực tế: MCP owner schema/list bỏ qua template từ attachment

- **Observed:** MCP list đếm `len(nt.templates)`; owner schema sort `nt.templates`; update còn lập current set theo legacy origin ở cả nhánh LEGACY và NOTE. REST đã đọc attachment. Reproducer SQLite cho NoteType có 2 ACTIVE applications: REST trả 2 templates, MCP schema/list chỉ trả 1 và thiếu template độc lập vừa gắn.
- **Evidence:** `app/services/mcp/note_type_tools.py:65`, `:99`, `:960`; `app/services/study_note_template_service.py:105`. Reproducer dùng fixture `tests/test_template_library.py`, `_attach()`, REST `GET /api/note-types/<id>`, gọi `get_note_type_schema` và `list_note_types` trực tiếp.
- **Potential concern:** Các giao diện nhìn thấy schema khác nhau; tracker Completed không bao phủ hết legacy consumers.
- **Impact:** MCP không thấy đủ template của NoteType và không có đường update attachment tương đương REST. Đây là khoảng trống chức năng có thể tái hiện, độc lập với việc có giữ bảng Card hay không.
- **Unknowns:** Việc mở rộng MCP update template dùng chung cần ngữ nghĩa đã chốt; chỉ xác nhận read mismatch trong lần review này, chưa sửa update behavior.

### F5 — Coverage còn sót ở công cụ chuẩn hóa media

- **Observed:** Khi lọc theo user/deck, template media normalizer vẫn join/filter bằng `Template.note_type_id` và lấy field definitions từ origin NoteType. Standalone template hoặc market copy không có origin NoteType không nằm trong tập template được scan theo cách này.
- **Evidence:** `app/services/flashcard_media_normalizer.py:441`, `:444`, `:447`, `:449`; CT-R3 mục “Chưa làm”.
- **Potential concern:** Maintenance tooling chưa phản ánh ownership/attachment/schema độc lập.
- **Impact:** Công cụ không phủ đầy đủ template mới; chưa có bằng chứng đây là lỗi sanitizer/render runtime hoặc bypass media proxy.
- **Unknowns:** Chưa đo số template/token cần normalize thực tế; phát hiện này dựa trên code, không có reproducer media mới.

### F6 — P3 trạng thái tài liệu bị lỗi thời, dễ báo sai tiến độ

- **Observed:** Plan kiến trúc đầu file còn nói CardProgress là authority và Phase 6 chưa bắt đầu; các báo cáo P6/P9/P10 mới hơn ghi cutover hoàn tất. Tracker template còn nói CT-R3 “chưa commit”, trong khi commit `80418285` đã có trong lịch sử HEAD.
- **Evidence:** `docs/architecture/study-interaction-trigger-algorithm-plan.md:3`, `:43`, `:44`; `docs/task/template-features/README.md:3`, `:30`; `docs/task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md:127`, `:128`; git log.
- **Potential concern:** Đọc một tracker duy nhất có thể báo chưa làm việc đã deploy, hoặc báo hoàn tất việc drop Card vốn không nằm trong scope.
- **Impact:** Review này phân biệt code hiện tại, báo cáo production đã lưu và mục tiêu chưa triển khai; không dùng snapshot lịch sử làm trạng thái production mới.
- **Unknowns:** Chưa xác nhận release/schema/flags đang chạy trên VPS ngày 11/10.

## Kiểm tra trong lần review này

Chạy `.venv/Scripts/python.exe scripts/run_tests.py --file tests/test_template_library.py tests/test_template_attachment_writers.py tests/test_study_application_occurrence.py tests/test_study_consolidated_progress.py --backend-only`: **46 tests PASS**, 4 files, 17,27 s theo runner. Các cờ study async/wire/new-learner/note-count/shadow được ép `0` ở process test để tránh nhiễm `.env`; từng fixture NOTE/v4 bật contract cần kiểm tra. DB SQLite tạm, media root tạm do runner quản lý.

Reproducer F4: **exit 0**, assertions xác nhận mismatch hiện có:

```json
{"active_applications":2,"rest_template_count":2,"mcp_schema_template_count":1,"mcp_list_template_count":1,"attached_template_present_in_rest":true,"attached_template_present_in_mcp":false}
```

Test xanh xác nhận những hành vi đã được test, không chứng minh mọi consumer đã bỏ Card. Không chạy full suite, browser mới, migration hoặc data-changing probe trên DB thật.

## Phần còn phải xác minh trước khi đánh dấu “bỏ Card hoàn toàn”

1. Contract mục tiêu có yêu cầu bỏ entity Card thật hay chỉ giữ nó như presentation/integration projection. Scope đã đóng vẫn cho phép giữ projection.
2. Inventory đầy đủ các writer/reader còn dùng Card và Template origin; F1–F3 là các phụ thuộc đã xác nhận, không phải manifest consumers đầy đủ.
3. Tương thích session đang mở, receipt/replay cũ, Connect ordinal, Browse content deletion và installed source/local/release-pin scope.
4. Production release/schema/flags cùng live row/lease/client telemetry. Báo cáo cutover cũ không thay việc kiểm chứng này.

Đây là danh sách điều kiện còn thiếu và phát hiện review, không phải phê duyệt hay thiết kế migration drop bảng.
