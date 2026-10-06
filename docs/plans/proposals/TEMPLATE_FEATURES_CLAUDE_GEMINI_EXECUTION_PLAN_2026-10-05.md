# Kế hoạch triển khai tính năng Template sau decoupling: Claude điều phối, Gemini triển khai phần đơn giản

- Ngày lập: **2026-10-05**.
- Trạng thái: **Chờ người dùng duyệt.** Chưa giao việc cho Gemini và chưa sửa source. Các quyết định ở §4 cần người dùng xác nhận trước khi mở task phụ thuộc.
- Người điều phối/review: **Claude**. Người triển khai phần đơn giản: **Gemini** (`agy`, theo [worker orchestration](../../../skills/antigravity-cli/references/worker-orchestration.md)).
- Spec chi tiết từng task Gemini: [`docs/task/template-features/`](../../task/template-features/README.md). Mỗi file có sẵn prompt để dán cho Gemini.
- Căn cứ đã đối chiếu với code ở commit `faa3c7d`: [study-interaction-trigger-algorithm-plan](../../architecture/study-interaction-trigger-algorithm-plan.md) (§5, §9, §16), [P3-07 applied composition contract](../../architecture/applied-composition-binding-contract-2026-09-09.md), [P6 plan](../../task/decoupling/P6_EXECUTION_PLAN_2026-09-29.md) (D6-08, D6-09), issue [TrinhChung/Flama#137](https://github.com/TrinhChung/Flama/issues/137) và #138, [proposal TPL-01](DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md) (chỉ là tham khảo, chưa được duyệt).

## 1. Mục tiêu

Đợt decoupling (P0–P10) đã đưa progress về learner/Note và có application occurrence (`study_applications`, `cards.application_id`). Nhưng ba nhu cầu sản phẩm vẫn chưa có trên UI hoặc chưa có trong code:

| # | Tính năng người dùng cần | Kết quả mong muốn |
|---|---|---|
| F1 | **Template tách riêng** | Có thư viện "Mẫu thẻ" độc lập với loại thẻ (NoteType). Một mẫu dùng lại được cho nhiều loại thẻ qua ánh xạ input → field. |
| F2 | **Một deck có nhiều template, thấy rõ trên UI** | Từ dashboard thấy deck có những kiểu thẻ nào, mỗi kiểu bao nhiêu note. Trang loại thẻ quản lý đủ template: đổi tên, xóa, số note dùng, nhãn mặc định. Template mới không còn mặc định `{{Word}}`. |
| F3 | **Template có phiên bản; ai cũng sửa được template của deck mình đã clone** | Mỗi lần lưu tạo một phiên bản bất biến, xem lịch sử, so sánh, khôi phục. Người cài deck từ marketplace tạo bản riêng (copy-on-write) cho kiểu thẻ gốc mà không đổi deck của tác giả. Khi tác giả sửa, người cài thấy cảnh báo và chọn giữ bản riêng hoặc theo bản gốc. |

Ngoài phạm vi: bán/chia sẻ mẫu thẻ độc lập trên marketplace, Interaction/Algorithm mới (Phase 8), xóa `templates.note_type_id`, đổi renderer ABI hoặc study wire.

## 2. Hiện trạng đã đối chiếu với code

| Chủ đề | Bằng chứng trong code | Khoảng trống |
|---|---|---|
| Template gắn cứng NoteType | `models/template.py:11` (`note_type_id` NOT NULL, CASCADE). Composition chỉ có `definition_id = legacy-template:{id}` (`app/services/study_composition_service.py:150`). | Không có bảng definition/version độc lập, không có thư viện, không có API áp dụng mẫu với ánh xạ field. |
| Application occurrence | `models/study_application.py` (unique `template_id + occurrence_key`). `cards.application_id`, unique `(note_id, application_id)` (`models/card.py:16-34`). `stage_repeated_application` chỉ có storage/test, chưa có UI (`app/services/study_application_service.py:1-10`, D6-09). | Đủ để giữ nguyên Card/progress khi thêm định nghĩa tái sử dụng. Không cần đổi trong kế hoạch này. |
| Chọn kiểu thẻ khi học | Endpoint `GET /api/study/scopes/<scope>/<id>/compositions` (`app/routes/flashcards/study.py:793-837`). `StudyModeSelector` chỉ hiện khi có >1 composition (`frontend/src/features/study/pages/StudyPage.tsx:347`). | Dashboard không cho biết deck có những kiểu thẻ nào, mỗi kiểu bao nhiêu note. |
| Quản lý template của NoteType | `NoteTypeDetailPage.tsx` chỉ có chọn template, nút "Mới", "Reset", lưu nội dung. Tạo mới luôn gửi `{{Word}}` (`NoteTypeDetailPage.tsx:121-127`). Backend cũng mặc định `{{Word}}` khi tạo NoteType và khi tạo template (`app/services/flashcards_share_service.py:224-225,265-266`). | Chưa có đổi tên, xóa, số note, nhãn mặc định trên UI dù API `PATCH`/`DELETE` đã có (`app/api/v1/flashcards/note_types.py:178-205`). Template mới trên NoteType không có field `Word` hiển thị trống. |
| Render thẻ của deck đã cài | `build_effective_study_card` luôn dùng `card.template` (`app/services/study_artifact_service.py:118,147`). Thẻ gốc trỏ Template **sống** của tác giả. | Người cài không thể đổi giao diện thẻ gốc. |
| Bản sao NoteType khi cài | `clone_note_type_for_user` chép Template, không lưu lineage về Template nguồn (`app/services/share/note_types.py:499-547`). Bản sao chỉ áp dụng cho note người cài tự thêm. | Sửa bản sao không ảnh hưởng thẻ gốc, gây hiểu nhầm "đã sửa nhưng không thấy đổi". |
| Phiên bản template | Release chỉ có entity `note_field`, `field_def` (`app/services/release/base.py:39`). Guard `SHARED_SCHEMA_VERSIONING_REQUIRED` (`app/services/flashcard_content_service.py:1509-1551`); #138 cho tác giả hotfix nội dung tại chỗ, người cài thấy ngay. | Không có lịch sử, so sánh, khôi phục. Người cài không được pin phiên bản. |
| Đổi tên field | `update_field` đổi key trong Note JSON nhưng không sửa token trong template (`app/services/flashcard_content_service.py:536-640`). | Template viết theo tên field bị hỏng sau khi đổi tên. Binding theo `FieldDef.id` (F1) sẽ xử lý cho mẫu có binding. |
| Renderer | `render_template_pair`/`build_render_context` dùng Mustache theo tên field; không hỗ trợ `{{FrontSide}}` (`app/services/flashcard_renderer.py:942-1080`). | Template mặc định mới không dùng `{{FrontSide}}`. |
| Contract REST | `tests/test_api_v1_route_map.py` snapshot mọi route `api_v1.*` trong `tests/snapshots/api_v1_routes.json`. | Mỗi route mới phải cập nhật snapshot bằng `UPDATE_ROUTE_SNAPSHOT=1`. Route trong `app/routes/flashcards/*` không nằm trong snapshot. |

Kiểm tra môi trường lập kế hoạch: container cloud không có dependency Python/Node nên **chưa chạy test baseline**. Baseline được chạy ở bước CT-00 trên máy local trước khi mở task đầu tiên.

## 3. Thiết kế tổng thể

```text
              (mới) template_definitions ──< template_definition_versions (bất biến)
                     ▲                 ▲
     definition_id / │                 │ fork version
 definition_version_id│                 │
                     │                 │
NoteType ──< templates (applied, materialized) ──< study_applications ──< cards ──> notes
                     ▲
                     │ source_template_id (FK từ bảng fork tới Template nguồn của tác giả)
(mới) deck_install_template_forks (install_id, source_template_id) ──> fork version
```

Nguyên tắc chốt: **giữ hàng `templates` làm "template đã áp dụng" cho một NoteType**. Renderer, Card, StudyApplication, composition id, Anki `source_ord`, session freeze và guard release giữ nguyên. Định nghĩa tái sử dụng và phiên bản nằm ở hai bảng mới. Hàng `templates` chứa nội dung đã materialize từ một phiên bản. Bản riêng của người cài nằm ở bảng fork, được một resolver duy nhất chọn khi render thẻ gốc.

## 4. Quyết định thiết kế (đề xuất) và câu hỏi cần người dùng chốt

| ID | Đề xuất | Lý do / ràng buộc |
|---|---|---|
| D-T1 | Giữ `templates` (NoteType-scoped, materialized). Không bỏ `note_type_id`, không đổi `cards`/`study_applications`. | Khớp quyết định 2026-08-24: Template độc lập + application theo NoteType. Card ID/progress không đổi. Đây là phương án D trong investigation. |
| D-T2 | Thêm `template_definitions` và `template_definition_versions`. Version là snapshot đầy đủ (`front_html`, `back_html`, `shared_css`, `input_schema`, `content_hash`), chỉ được insert. | Lịch sử, khôi phục và pin cần nội dung bất biến. Không lưu delta để tránh lỗi tái dựng. |
| D-T3 | Backfill: mỗi Template hiện có nhận một definition + version 1. Lưu, reset hoặc khôi phục đều thêm version mới; khôi phục là chép nội dung cũ thành version mới. | Mọi người có lịch sử ngay. Không có thao tác xóa/sửa lịch sử. |
| D-T4 | Fork của người cài theo **(DeckInstall, Template nguồn)** trong `deck_install_template_forks`. Không có fork thì theo bản gốc như hiện nay. Lần lưu đầu tạo fork (copy-on-write). Fork không bao giờ sửa Template/Note/Card nguồn. Note người cài tự thêm vẫn dùng Template của NoteType bản sao. | Mọi đường render overlay đều có `clone_scope.install`. Field override của overlay theo install và giữ `FieldDef.id` nguồn, nên fork theo install khớp schema view. |
| D-T5 | Phiên học đang mở không đổi khi tác giả/người cài sửa template (artifact đã freeze). Phiên mới dùng nội dung hiệu lực mới. | Hợp đồng freeze P3-04/P4-00. Có test bắt buộc. |
| D-T6 | Mẫu trong thư viện khai báo input (tự trích từ token Mustache). Áp dụng vào NoteType lưu `input_bindings` dạng `input_key → field_def_id`, materialize bằng cách đổi token sang tên field hiện tại. Đổi tên field sẽ materialize lại các template có binding. | Không đổi renderer ABI hoặc study wire. Binding bền theo `FieldDef.id` đúng P3-07. |
| D-T7 | Pin phiên bản theo release cho tác giả (#137 đầy đủ, bỏ đường hotfix sống #138) làm **M5**, cần duyệt riêng. Trước M5, người cài chưa fork vẫn thấy hotfix của tác giả như hiện nay. Người đã fork được cách ly. | Release/rebase là vùng rủi ro cao. Cách này giao F3 cho người cài sớm mà không động vào release engine. |
| D-T8 | Không đổi renderer ABI (`flama-client-mustache.v2`), schema session, định dạng composition id. Artifact template của fork **giữ `id` = `template_id` nguồn**; chỉ `version` (digest gồm front/back/css) khác. | Restore phía client bắt buộc `template.id === card.template_id`, `template_key` có dạng `{id}:{version}`, `definition_id === legacy-template:{template_id}` và `binding.definition_version === template.version` (`frontend/src/features/study/session/sessionRestore.ts:599-690`). Đổi `id` sẽ làm mọi phiên dùng fork bị quarantine. |

Câu hỏi cần người dùng trả lời trước khi mở task phụ thuộc:

| ID | Câu hỏi | Đề xuất của Claude | Chặn task |
|---|---|---|---|
| Q1 | Fork theo từng deck đã cài (D-T4) hay theo người dùng + loại thẻ (dùng chung cho mọi deck cài từ cùng loại thẻ)? | Theo từng deck đã cài. | CT-05, GT-11 |
| Q2 | Thư viện "Mẫu thẻ" hiện **tất cả** template (kể cả template đang nằm trong loại thẻ, nhờ backfill) hay chỉ mẫu người dùng chủ động lưu? | Hiện tất cả, chia nhóm "Đang dùng trong loại thẻ" và "Mẫu độc lập". | CT-06, GT-12 |
| Q3 | Materialize lại template khi đổi tên field: bật cho mọi NoteType hay chỉ NoteType chưa có release chia sẻ? | Chỉ NoteType chưa có release chia sẻ ở M4. NoteType đã release chờ M5. | CT-06 |
| Q4 | Có duyệt M5 (#137: pin release cho tác giả, rebase giữ bản của tôi/theo upstream) ngay trong đợt này? | Chưa. Duyệt sau khi M3 chạy ổn trên production. | CT-07 |
| Q5 | Nhánh triển khai: mỗi milestone một nhánh `feat/template-mN-*` từ nhánh tích hợp hiện hành, hay dùng chung `refactor/frontend-fsd-renderer-boundary`? | Nhánh riêng theo milestone, worktree riêng cho từng worker. | Mọi task source |

## 5. Hợp đồng API (đóng băng trước khi Gemini làm UI)

Các hợp đồng dưới đây là **bản đề xuất**. Claude đóng băng chúng trong CT-01. Nếu ADR đổi hợp đồng, Claude sửa §5 và mọi spec Gemini liên quan **trước khi** giao task. Gemini không được tự suy diễn field ngoài bảng.

### 5.1 Contract B — số note theo kiểu thẻ của deck (M1, không đổi schema)

`GET /api/study/scopes/deck/<deck_id>/compositions?include_counts=1`

- Không có `include_counts` (hoặc giá trị khác `1`/`true`/`yes`): response **giữ nguyên từng byte** như hiện tại.
- Có `include_counts=1`: thêm đúng một key cấp cao nhất:

```json
{ "note_counts": { "<composition_id>": 12, "<composition_id_2>": 0 } }
```

Mỗi `composition_id` trong `compositions` đều có mặt trong `note_counts`. Giá trị là số `Note` khác nhau có Card thuộc composition đó trong phạm vi deck (gồm deck con và overlay). Không thêm field vào từng phần tử `compositions` vì `AppliedComposition.to_dict()` được freeze vào session.

### 5.2 Contract C — danh sách template kèm số note (M1)

`GET /api/note-types/<note_type_id>/templates` → mỗi item giữ mọi key hiện có của `serialize_template` và thêm:

```json
{ "note_count": 120 }
```

`note_count` = số `Note` khác nhau có Card trỏ template đó. Các endpoint khác trả template (`GET /api/note-types/<id>`, `PATCH`, …) **không** đổi.

### 5.3 Contract A — phiên bản template của chủ sở hữu (M2)

Base: `/api/note-types/<note_type_id>/templates/<template_id>`

| Method & path | Body | Response 2xx | Lỗi |
|---|---|---|---|
| `GET /versions` | — | `{"schema_version":"template-versions.v1","template_id","definition_id","current_version_id","items":[VersionSummary]}`; `items` sắp `version_no` giảm dần | 404 `FIELD_NOT_FOUND` (giữ mã hiện có của `_owned_note_type`/`_template`) |
| `GET /versions/<version_id>` | — | `VersionDetail` | 404 `TEMPLATE_VERSION_NOT_FOUND` |
| `POST /versions/<version_id>/restore` | `{"change_note"?: string}` | `TemplateWithVersion` | 404 `TEMPLATE_VERSION_NOT_FOUND`; 409 `SHARED_SCHEMA_VERSIONING_REQUIRED`; 400 `TEMPLATE_COMPILE_ERROR` |
| `PATCH ` (đã có) | thêm tùy chọn `change_note` | `TemplateWithVersion` | như hiện tại |

```ts
type VersionSummary = {
  id: string
  version_no: number            // 1, 2, 3...
  content_hash: string          // sha256 hex, 64 ký tự
  change_note: string           // '' nếu không có
  origin: 'backfill' | 'create' | 'edit' | 'reset' | 'restore' | 'apply' | 'fork'
  created_at: string            // ISO 8601 UTC
  created_by: { id: number; username: string } | null
  is_current: boolean
}
type VersionDetail = VersionSummary & { front_html: string; back_html: string; shared_css: string }
type TemplateWithVersion = TemplateItem & {          // TemplateItem = serialize_template hiện tại
  definition_id: string | null
  definition_version_id: string | null
  version_no: number | null
}
```

`serialize_template` thêm hai key nullable `definition_id`, `definition_version_id` (additive).

### 5.4 Contract D — bản riêng của người cài (M3)

Base: `/api/marketplace/installations/<install_id>/templates`. Chỉ chủ của `DeckInstall` được gọi. Install đã detach trả 409 `INSTALL_DETACHED`.

| Method & path | Body | Response 2xx |
|---|---|---|
| `GET ` | — | `{"schema_version":"install-templates.v1","install_id","local_deck_id","items":[InstallTemplateItem]}` |
| `GET /<source_template_id>` | — | `InstallTemplateDetail` |
| `PUT /<source_template_id>/fork` | `{"front_html","back_html","shared_css","change_note"?}` | `InstallTemplateDetail` (lần đầu tạo fork, sau đó thêm version) |
| `DELETE /<source_template_id>/fork` | — | `InstallTemplateDetail` với `state:"following"` |
| `POST /<source_template_id>/preview` | `{"front_html","back_html","shared_css"}` | `{"front_html","back_html","front_renderer_payload","back_renderer_payload"}` (cùng shape với preview NoteType) |
| `GET /<source_template_id>/versions` | — | như Contract A |
| `GET /<source_template_id>/versions/<version_id>` | — | `VersionDetail` |
| `POST /<source_template_id>/versions/<version_id>/restore` | `{"change_note"?}` | `InstallTemplateDetail` |

```ts
type InstallTemplateItem = {
  source_template_id: string
  name: string
  position: number
  is_default: boolean
  state: 'following' | 'forked'
  fork_id: string | null
  current_version_id: string | null      // null khi following
  upstream_changed_since_fork: boolean   // false khi following
  note_count: number
  composition_id: string                 // comp:install:{install_id}:source:notetype:{nt}:template:{tid}
}
type InstallTemplateDetail = InstallTemplateItem & {
  front_html: string; back_html: string; shared_css: string   // nội dung hiệu lực
  upstream: { front_html: string; back_html: string; shared_css: string; content_hash: string }
  field_defs: Array<{ id: string; name: string; field_type: string; position: number }>  // schema view của overlay
}
```

Mã lỗi: 404 `INSTALL_NOT_FOUND`, 404 `TEMPLATE_NOT_IN_INSTALL`, 409 `INSTALL_DETACHED`, 400 `TEMPLATE_COMPILE_ERROR`, 404 `TEMPLATE_VERSION_NOT_FOUND`. Envelope lỗi theo `app/api/common/responses.error_response`: `{"error","message","field"?,"details"?}`.

### 5.5 Contract E — thư viện mẫu thẻ (M4)

Base: `/api/card-templates`.

| Method & path | Body | Response 2xx |
|---|---|---|
| `GET ?q=&group=all|in_use|standalone` | — | `{"items":[LibraryItem]}` |
| `POST ` | `{"name","description"?,"category"?,"front_html","back_html","shared_css"?}` | 201 `LibraryDetail` |
| `GET /<definition_id>` | — | `LibraryDetail` |
| `PATCH /<definition_id>` | `{"name"?,"description"?,"category"?}` | `LibraryDetail` |
| `PUT /<definition_id>/content` | `{"front_html","back_html","shared_css","change_note"?}` | `LibraryDetail` (thêm version) |
| `POST /<definition_id>/preview` | `{"front_html","back_html","shared_css","sample_values"?: Record<string,string>}` | như preview NoteType |
| `GET /<definition_id>/versions`, `GET .../versions/<vid>`, `POST .../versions/<vid>/restore` | như Contract A | như Contract A |
| `POST /<definition_id>/apply` | `{"note_type_id","name"?,"input_bindings":{"<input_key>":"<field_def_id>"}}` | 201 `TemplateWithVersion` |
| `POST /<definition_id>/archive` | — | `LibraryDetail` (`archived: true`) |
| `POST /api/note-types/<nt>/templates/<tid>/sync-definition` | — | `TemplateWithVersion` (cập nhật lên version mới nhất) |

```ts
type InputSpec = { key: string; label: string; type: 'text' | 'richtext' | 'markdown' | 'image' | 'audio' | 'diagram'; required: boolean }
type LibraryItem = {
  id: string; name: string; description: string; category: string
  group: 'in_use' | 'standalone'; archived: boolean
  current_version_id: string; version_no: number
  input_keys: string[]; applied_count: number; updated_at: string
}
type LibraryDetail = LibraryItem & {
  current_version: VersionDetail & { input_schema: InputSpec[] }
  applications: Array<{ note_type_id: string; note_type_name: string; template_id: string; template_name: string; definition_version_id: string; is_outdated: boolean }>
}
```

Lỗi khi apply (theo bảng binding P3-07): 400 `INPUT_BINDING_INCOMPLETE` (`details.missing_keys`), 400 `INPUT_BINDING_STALE` (`details.field_def_ids`), 403 `INPUT_BINDING_OUT_OF_SCOPE`, 400 `INPUT_BINDING_AMBIGUOUS`, 400 `INPUT_BINDING_TYPE_MISMATCH`; 404 `TEMPLATE_DEFINITION_NOT_FOUND`; 409 `SHARED_SCHEMA_VERSIONING_REQUIRED` khi NoteType đích đã có release chia sẻ.

## 6. Nguyên tắc chia việc

Gemini nhận task khi **toàn bộ** điều kiện sau đúng:

1. Có hợp đồng/đầu ra cụ thể (chữ ký hàm, JSON, props, chuỗi UI) ghi sẵn trong spec.
2. Danh sách file được sửa ≤ 6 file, không chạm schema/migration, transaction, lock, study runtime, overlay resolver, release engine hoặc sanitizer.
3. Kiểm chứng được bằng test tự động mà spec mô tả từng assertion.
4. Sai sót không gây mất dữ liệu: có thể sửa bằng một lần review.

Claude giữ: ADR và hợp đồng, schema/migration/backfill (MySQL), service có transaction/fence, resolver hiệu lực cho mọi đường render, fork/pin, session freeze, thay đổi ở `useStudySession`, review toàn bộ diff và integration gate. Claude cũng chạy review đối kháng cho phần pure function của Gemini vì lỗi ở đó âm thầm làm hỏng template.

## 7. Danh sách task

Trạng thái: `Planned → Ready → In progress → Review → Accepted` hoặc `Needs revision`. Chỉ Claude đánh dấu `Accepted` sau khi đọc diff và tự chạy test.

### M0 — Chốt kế hoạch

| ID | Owner | Nội dung | Phụ thuộc |
|---|---|---|---|
| CT-00 | Claude | Nhận câu trả lời Q1–Q5, chạy baseline local (`--module flashcards,study,marketplace,decks --backend-only`, frontend `study,decks`), ghi kết quả vào README task. | Người dùng duyệt |
| CT-01 | Claude | ADR `docs/architecture/template-definition-version-fork-adr-2026-10-XX.md`: kiểm chứng D-T1..D-T8 trên code (ràng buộc restore ở D-T8 đã xác nhận; còn lại: các đường render ở CT-04, cutover vị trí trong `share/cutover.py`, guard release/#138, kiểu cột MySQL và index), đóng băng Contract A/D/E. | CT-00 |

### M1 — Hiển thị rõ "một deck nhiều template" (không đổi schema)

| ID | Owner | Nội dung | File chính | Phụ thuộc |
|---|---|---|---|---|
| GT-01 | Gemini | Nội dung mặc định của template mới theo field thật của NoteType. | `app/services/flashcards_share_service.py`, test mới | CT-00 |
| GT-02 | Gemini | Contract C: `note_count` cho `GET /api/note-types/<id>/templates`. | `app/services/flashcard_content_service.py` (`list_templates`), test mới | CT-00 |
| GT-03 | Gemini | Contract B: `include_counts=1` → `note_counts`. | `app/services/study_composition_service.py` (hàm mới), `app/routes/flashcards/study.py` (endpoint compositions), test | CT-00 |
| GT-04 | Gemini | Entity frontend `entities/card-template`: types + API + query keys cho Contract B/C. | `frontend/src/entities/card-template/**` | CT-00 |
| GT-05 | Gemini | Tách UI soạn template trong `NoteTypeDetailPage` thành `TemplateCodeEditor` ở tầng entity (chuyển nguyên DOM/class, không đổi giao diện; có snapshot DOM trước/sau). | `frontend/src/entities/card-template/ui/`, `NoteTypeDetailPage.tsx` | GT-04 |
| GT-06 | Gemini | Quản lý template: số note, nhãn mặc định, đổi tên, xóa, thông báo lỗi thân thiện; bỏ `{{Word}}` cứng khi tạo. | `NoteTypeDetailPage.tsx`, component mới | GT-02, GT-04, GT-05 |
| GT-07 | Gemini | Dashboard: mục menu "Kiểu thẻ" và dialog liệt kê kiểu thẻ + số note + liên kết sửa. | `frontend/src/features/dashboard/**` | GT-03, GT-04 |
| CT-08 | Claude | (Tùy chọn) `/study?deck_id=X&composition_id=Y` chọn sẵn kiểu thẻ trong `useStudySession`. | `useStudySession.ts` | GT-07 |
| CT-R1 | Claude | Review + integration gate M1. | — | GT-01..07 |

### M2 — Phiên bản template cho chủ sở hữu

| ID | Owner | Nội dung | Phụ thuộc |
|---|---|---|---|
| GT-08 | Gemini | Python pure: `template_tokens.py` (trích/đổi token Mustache) + `content_hash`. Chạy song song từ M0. | CT-00 |
| GT-09 | Gemini | TS pure: `lineDiff` + component `TemplateDiffView`. Chạy sớm ở đợt 1. | GT-05 (cùng `index.ts`) |
| CT-02 | Claude | Models + migration `000051` (2 bảng + cột mới trên `templates`), backfill idempotent, rehearsal MySQL, thứ tự deploy (migration trước code). | CT-01, GT-08 |
| CT-03 | Claude | `template_definition_service` + tích hợp create/update/reset/delete + Contract A + cập nhật route snapshot + test. | CT-02 |
| GT-15A | Gemini | Bổ sung test hợp đồng Contract A theo bảng trường hợp trong spec. | CT-03 |
| GT-10 | Gemini | UI lịch sử phiên bản trong `NoteTypeDetailPage` (xem, so sánh, khôi phục). | CT-03, GT-06, GT-09 |
| CT-R2 | Claude | Review + gate M2 (MySQL migration, session freeze, tốc độ lưu). | toàn bộ M2 |

### M3 — Người cài sửa template của deck đã clone

| ID | Owner | Nội dung | Phụ thuộc |
|---|---|---|---|
| CT-04 | Claude | Seam `resolve_effective_template(card, clone_scope)` và chuyển mọi đường render sang seam (chưa đổi hành vi, có test parity). Danh sách callsite tối thiểu: `study_artifact_service.build_effective_study_card`, `routes/flashcards/study.py` (preview/artifact), `browse_card_service`/`vocabulary_repository`/`vocabulary_presenter`, `mcp/study_tools`, `study_card_editor_service`. | CT-01 |
| CT-05 | Claude | Bảng `deck_install_template_forks`, service fork/save/reset/restore/preview, Contract D, cờ `upstream_changed_since_fork`, test owned + installed + local-added + phiên đang mở + không đổi nguồn. | CT-03, CT-04, Q1 |
| GT-15D | Gemini | Bổ sung test hợp đồng Contract D. | CT-05 |
| GT-11 | Gemini | Trang `/installed-decks/:installId/templates`: danh sách kiểu thẻ gốc, soạn bản riêng, xem trước, khôi phục bản gốc, lịch sử. Thêm liên kết từ dialog GT-07. | CT-05, GT-05, GT-07, GT-10 |
| CT-R3 | Claude | Review + gate M3 (browser smoke bằng profile riêng, nhiều tab, restore IndexedDB). | toàn bộ M3 |

### M4 — Thư viện mẫu thẻ độc lập

| ID | Owner | Nội dung | Phụ thuộc |
|---|---|---|---|
| CT-06 | Claude | Service + Contract E: tạo mẫu độc lập, apply với binding (dùng GT-08), sync lên version mới, materialize lại khi đổi tên field (Q3), archive. | CT-03, GT-08, Q2, Q3 |
| GT-15E | Gemini | Bổ sung test hợp đồng Contract E. | CT-06 |
| GT-12 | Gemini | Trang `/card-templates` (danh sách, lọc nhóm) và `/card-templates/:id` (sửa, xem trước, lịch sử). Menu sidebar "Mẫu thẻ". | CT-06, GT-05, GT-10 |
| GT-13 | Gemini | Wizard "Áp dụng vào loại thẻ" + `FieldMappingEditor`. | GT-12 |
| GT-14 | Gemini | Tài liệu người dùng: hướng dẫn kiểu thẻ, phiên bản, bản riêng, thư viện. | M3/M4 Accepted |
| CT-R4 | Claude | Review + gate M4. | toàn bộ M4 |

### M5 — Pin phiên bản theo release cho tác giả (#137), cần duyệt riêng (Q4)

| ID | Owner | Nội dung |
|---|---|---|
| CT-07 | Claude | Release ghi bản đồ `source_template_id → version_id`; install pin theo release; update/rebase có xung đột template `keep_mine`/`keep_upstream`; bỏ đường hotfix sống #138; tài liệu runbook. Không giao Gemini phần lõi. Sau khi có contract, Gemini có thể nhận UI xung đột template theo mẫu GT-11. |

### Chi tiết task của Claude

**CT-00 — Chốt và baseline.** Ghi câu trả lời Q1–Q5 vào README task. Chạy trên máy local (đã có `.venv`, `node_modules`): `scripts/run_tests.py --module flashcards,study,marketplace,decks,deck_collaboration --backend-only`, frontend `--module study,decks --frontend-only`, `npm run typecheck`, `npm run build:ci`, `tests.test_api_v1_route_map`. Lưu kết quả và HEAD vào nhật ký README. Tạo worktree cho các task `Ready`.

**CT-01 — ADR.** Đầu ra `docs/architecture/template-definition-version-fork-adr-2026-10-XX.md`, trạng thái Accepted khi người dùng đồng ý. Nội dung bắt buộc:

1. Bảng cột của `template_definitions` (id, owner_user_id, name, description, category, origin `note_type|standalone|fork`, archived_at, forked_from_version_id, current_version_id, created/updated), `template_definition_versions` (id, definition_id, version_no unique theo definition, front_html/back_html/shared_css cùng kiểu cột với `templates`, input_schema JSON, content_hash CHAR(64), origin, change_note, created_by_user_id, created_at) và cột mới trên `templates` (`definition_id`, `definition_version_id`, `input_bindings` JSON, tất cả nullable). FK/ON DELETE, index, kiểu MySQL.
2. Chọn seam ghi version: khuyến nghị listener `before_flush` cho `Template` (giống seam `StudyApplication` ở `models/study_application.py`), vì Template được ghi ở 9 file: `flashcard_content_service`, `flashcards_share_service`, `share/note_types`, `flashcard_legacy`, `flashcard_media_normalizer`, `mcp/note_type_tools`, `connect/actions`, `connect/import_session`, `study_note_template_service`. Origin truyền qua `session.info`.
3. Danh sách đường render thẻ của deck đã cài (callsite CT-04) và chứng minh bằng grep không sót.
4. Quan hệ với guard `SHARED_SCHEMA_VERSIONING_REQUIRED` và hotfix #138: hotfix vẫn tạo version cho tác giả; người cài `following` thấy ngay; người đã fork chỉ nhận cờ `upstream_changed_since_fork`.
5. Vòng đời: xóa Template nguồn → fork xóa theo (CASCADE), version của fork giữ; gỡ/detach install → fork xóa theo; cutover theo vị trí trong `share/cutover.py` không bị ảnh hưởng.
6. Thứ tự deploy: migration trước code (cột mới trên `templates` không được `db.create_all()` thêm); kiểm tra boot qua `wsgi.py`.
7. Đóng băng Contract A/D/E (sửa §5 nếu cần) và quy tắc tương thích kiểu cho GT-13.

**CT-02 — Schema + backfill.** Model mới trong `models/`, đăng ký ở `models/__init__.py`; migration `migrations/versions/2026MMDD_000051_add_template_definitions.py` (sau `20261003_000050_drop_retired_note_progress_tables.py`). Backfill idempotent theo lô 500 (Alembic data step hoặc lệnh CLI `flask template-definitions-backfill --apply`, chọn trong ADR): mỗi Template chưa có `definition_id` nhận definition `origin='note_type'` + version 1 `origin='backfill'`, `input_schema` tính bằng GT-08. Test: schema/model, backfill hai lần không tăng dòng, round-trip `rewrite_variable_names` identity trên toàn bộ template local, migration 50→51→50→51 trên MySQL 8. Không động tới `cards`, `study_applications`.

**CT-03 — Version service + Contract A.** `app/services/template_definition_service.py` (ensure_definition, append_version có chống trùng theo `content_hash`, list/get/restore). Nối seam đã chọn ở CT-01; route Contract A trong `app/api/v1/flashcards/note_types.py`; thêm 2 key vào `serialize_template`; cập nhật `tests/snapshots/api_v1_routes.json` bằng `UPDATE_ROUTE_SNAPSHOT=1`. Test lõi: mọi writer ở danh sách CT-01 tạo đúng một version khi đổi nội dung; Card ID và progress không đổi; restore không xóa version. Sau đó mở GT-15A, GT-10.

**CT-04 — Seam render hiệu lực.** Thêm `resolve_effective_template(card, clone_scope)` (đặt trong `study_artifact_service.py`) và chuyển các callsite: `build_effective_study_card` (dòng 118, 147), `app/routes/flashcards/study.py` (khoảng dòng 378, 481, 629, 679), `app/repositories/vocabulary_repository.py:1110`, `app/presenters/vocabulary_presenter.py:412`, `app/services/mcp/study_tools.py:281,357`, `app/services/study_card_editor_service.py:152`, và mọi chỗ CT-01 tìm thêm. Bước này **không đổi hành vi**: test parity so `template_version` và HTML render trước/sau trên fixture owned + overlay + local-added.

**CT-05 — Fork của người cài.** Bảng `deck_install_template_forks` (install_id FK CASCADE, source_template_id FK CASCADE, definition_id của người cài, current_version_id, base_upstream_hash, unique `(install_id, source_template_id)`), migration `000052`. Resolver: tra fork theo `clone_scope.install.id` một lần cho mỗi lần dựng phiên/trang (không N+1), trả đối tượng giống Template với `id` = template nguồn (D-T8). Route Contract D trong `app/api/v1/marketplace/installations.py`; preview dùng `build_clone_schema_view`. Test lõi: không đổi hàng của tác giả, người cài khác không ảnh hưởng, phiên đang mở giữ artifact, restore IndexedDB không quarantine, browse/MCP/preview trả cùng nội dung hiệu lực. Sau đó mở GT-15D, GT-11.

**CT-06 — Thư viện + Contract E.** Service tạo mẫu độc lập, apply (kiểm tra binding theo bảng P3-07, materialize bằng `rewrite_variable_names`, tạo Template qua đường tạo Card/NOTE expansion có sẵn của `flashcard_content_service.create_template`), `sync-definition`, archive; hook đổi tên field trong `update_field` theo Q3; blueprint mới `app/api/v1/flashcards/card_templates.py` đăng ký trong `flashcards_v1_bp`; route snapshot. Sau đó mở GT-15E, GT-12, GT-13.

**CT-07 — Pin release (#137), chỉ khi Q4 được duyệt.** Release ghi bản đồ `source_template_id → version_id`; install pin; update/rebase thêm đơn vị xung đột template `keep_mine`/`keep_upstream`; bỏ đường hotfix sống #138; runbook. Lập plan riêng trước khi code.

**CT-08 — Liên kết học theo kiểu thẻ (tùy chọn).** `/study?deck_id=X&composition_id=Y`: trong `useStudySession`, khi có nhiều composition và `Y` thuộc danh sách thì gọi `selectComposition(Y)` thay vì chờ người dùng chọn; `Y` không hợp lệ thì vẫn hiện selector. Test trong `useStudySession.test.tsx`.

**CT-R1..R4 — Review và gate milestone.** Theo §9, cộng browser smoke bằng profile riêng và cập nhật tài liệu kiến trúc liên quan (`study-interaction-trigger-algorithm-plan.md` §16, issue #137).

### Thứ tự chạy thực tế

```text
Đợt 0: CT-00, CT-01 (Claude)  ||  GT-01, GT-02, GT-08, GT-04 (Gemini, mỗi task một worktree)
Đợt 1: GT-03  ||  GT-05 → GT-09 → GT-06 → GT-07  ||  CT-02, CT-04 (Claude)
Đợt 2: CT-03 → GT-15A, GT-10
Đợt 3: CT-05 → GT-15D, GT-11
Đợt 4: CT-06 → GT-15E, GT-12 → GT-13 → GT-14
Đợt 5 (nếu duyệt Q4): CT-07
```

Không chạy song song hai task cùng sửa một file. Cặp phải tuần tự: GT-04 → GT-05 → GT-09 (cùng `entities/card-template/index.ts`); GT-05 → GT-06 → GT-10 (cùng `NoteTypeDetailPage.tsx`); GT-02/GT-01 trước CT-03 (cùng `flashcard_content_service.py`/`flashcards_share_service.py`); GT-03 trước CT-08.

## 8. Quy trình giao và review một task Gemini

1. **Claude chuẩn bị:** xác nhận phụ thuộc đã `Accepted`, đối chiếu lại số dòng/đoạn code mà spec trích (code có thể đã đổi), cập nhật spec nếu lệch. Ghi `git status` và HEAD vào README task.
2. **Giao:** dán phần "Prompt cho Gemini" trong file spec (đã có phần quy tắc chung). Gemini chạy trong worktree riêng, chế độ `accept-edits`, không commit.
3. **Gemini báo cáo** theo mẫu trong spec: file đã sửa, lệnh đã chạy kèm output thật, điểm chưa chắc chắn.
4. **Claude review** theo checklist:
   - `git diff --stat` chỉ chứa file trong whitelist; không có file ngoài phạm vi, không đổi format hàng loạt.
   - So từng dòng với hợp đồng: tên hàm, kiểu, JSON key, mã lỗi, chuỗi tiếng Việt.
   - Test có assertion về giá trị (không chỉ kiểm tra tồn tại); có case âm; không `skip`/`expectedFailure` mới; không sửa test cũ để cho qua.
   - Tự chạy lại lệnh kiểm tra của spec, cộng `git diff --check`, lint/typecheck cho frontend và route snapshot cho backend.
   - Đọc đối kháng: input rỗng, None, Unicode/tiếng Nhật, field tên có dấu chấm, deck overlay, quyền người khác, StrictMode/unmount, query invalidation.
   - UI: class/DOM của phần cũ giữ nguyên; trạng thái loading/empty/error; mobile 375px; dark mode.
5. **Kết quả:** `Accepted` (Claude có thể sửa nhỏ và ghi lại) hoặc `Needs revision` với danh sách lỗi cụ thể gửi lại Gemini trong cùng conversation. Sau hai lần `Needs revision` cho cùng lỗi, Claude tự sửa.

## 9. Tiêu chí nghiệm thu chung và lệnh kiểm tra

Lệnh (PowerShell, từ repo root, môi trường local đã xác minh trong kế hoạch FSD):

```powershell
& .\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module marketplace,decks,deck_collaboration --backend-only
& .\.venv\Scripts\python.exe -m unittest tests.test_api_v1_route_map
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- <đường dẫn test của task>
npm --prefix frontend run build:ci
git diff --check
```

| Milestone | Bằng chứng bắt buộc |
|---|---|
| M1 | Response compositions không có `include_counts` giống hệt trước (so JSON). Dashboard/NoteType chạy trên desktop + mobile; deck owned và deck đã cài. |
| M2 | Migration 50→51→50→51 trên MySQL 8 local; backfill chạy hai lần không tạo thêm dòng; lưu template tạo đúng một version; khôi phục không xóa version; Card ID/progress không đổi. |
| M3 | Fork không đổi bất kỳ hàng nào của tác giả (đếm/so hash `templates`, `notes`, `cards`); người cài khác không bị ảnh hưởng; phiên đang mở giữ artifact cũ; phiên mới dùng fork; xóa fork quay về bản gốc; browse/MCP/preview hiển thị cùng nội dung hiệu lực. |
| M4 | Apply với binding thiếu/stale/khác NoteType/sai kiểu bị từ chối đúng mã; đổi tên field cập nhật template có binding; template không binding giữ hành vi cũ. |

Browser/DevTools chỉ dùng profile riêng (ví dụ `C:\Users\chung\.gemini\chrome-profiles\flama-template-features`), không dùng profile cá nhân. Thiếu bằng chứng nào thì ghi "chưa kiểm tra", không ghi PASS.

## 10. Rủi ro và cách kiểm soát

| Rủi ro | Kiểm soát |
|---|---|
| Gemini bịa hàm/field không tồn tại | Spec trích nguyên đoạn code liên quan; quy tắc "thiếu symbol thì dừng và báo cáo"; review so contract từng dòng. |
| Đổi token Mustache sai làm hỏng template | GT-08 có bảng test bắt buộc; CT-R2 thêm fuzz/so sánh trước–sau trên toàn bộ template backfill (round-trip phải giữ nguyên byte khi mapping là identity). |
| Fork rò rỉ sang tác giả hoặc người cài khác | Fork chỉ đọc qua resolver; test đếm hàng nguồn trước/sau; review bắt buộc của Claude. |
| Đổi `AppliedComposition` làm vỡ session freeze | Contract B thêm key cấp cao nhất, không sửa dataclass; review chặn mọi diff ở `AppliedComposition`. |
| Code mới boot trước migration (cột mới trên `templates`) | CT-02 ghi rõ thứ tự deploy; kiểm tra boot thật qua `wsgi.py` theo AGENTS.md. |
| Xung đột với migration FSD đang chạy (G03 dashboard, G09 note-types) | Không chạy GT-05/06/07/10 khi G03/G09 đang `In progress`; code mới đặt trong slice mới (`entities/card-template`) và component mới, chỉ sửa tối thiểu file cũ. |
| Hiệu năng: đếm note theo composition | Một truy vấn group-by cho mọi composition; chỉ chạy khi `include_counts=1`; không chạy trong luồng mở phiên học. |
| Backfill tạo nhiều version rác | Mỗi lần lưu chỉ thêm version khi `content_hash` khác version hiện tại (CT-03). |

## 11. Bước tiếp theo sau khi người dùng duyệt

1. Người dùng trả lời Q1–Q5 (có thể chấp nhận toàn bộ đề xuất).
2. Claude chạy CT-00 và đánh dấu GT-01, GT-02, GT-04, GT-08 là `Ready` trong README task (GT-05 mở sau khi GT-04 `Accepted`).
3. Người dùng hoặc Claude (nếu chạy local có `agy`) giao lần lượt prompt của các task `Ready`; Claude review theo §8.
