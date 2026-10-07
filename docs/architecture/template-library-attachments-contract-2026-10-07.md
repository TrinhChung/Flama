# Template library và attachment — Contract E2/F2

Ngày: 2026-10-07. Contract quan sát từ API hiện có, dùng cho GT-12/13. Reviewer: Codex. Backend không còn là dependency chặn hai task này; mỗi phase frontend vẫn cần review riêng.

Nguồn: `app/api/v1/flashcards/card_templates.py`, `app/services/template_library_service.py`, `app/repositories/template_library_repository.py`, `app/validators/template_library.py`, `app/services/flashcard_content_service.py::preview_raw_template` và `app/services/flashcard_renderer.py::render_template_pair`.

## 1. Identity và hành vi

- Library dùng ID thật của `Template`. Gắn vào NoteType tạo `StudyApplication`, giữ nguyên `template_id`; không copy source HTML, không đổi token, không tạo definition ID.
- Một template có nhiều attachment theo `(note_type_id, template_id, occurrence_key)`. Mặc định occurrence `compat`; dùng occurrence khác để gắn thêm lần nữa vào cùng NoteType.
- Sửa source ảnh hưởng mọi attachment đang dùng template đó. `PATCH` trả ID các attachment ACTIVE trong `affected_applications`; đây không phải snapshot phiên học.
- Binding dùng `FieldDef.id`, không dùng tên field. Đổi tên field không đổi mapping. Một field có thể phục vụ nhiều input.
- `required` là khuyến nghị. Input không gắn vẫn được lưu và render rỗng; thiếu input chỉ phát warning. Binding có target ngoài NoteType hoặc sai kiểu bị từ chối.
- Archive ẩn template khỏi library mặc định và chặn attachment mới; attachment đang dùng vẫn ACTIVE. `DELETE` attachment chuyển thành RETIRED, giữ Card/progress; POST lại cùng occurrence phục hồi cùng application ID.
- Market copy là template thuộc người nhận, dùng chung giữa các NoteType của họ. Library chỉ trả template thuộc user hiện tại, không phải catalogue marketplace. Không có đồng bộ definition riêng cho từng attachment.

## 2. DTO chính xác

Các kiểu TypeScript dưới đây là hợp đồng **cần thêm** trong GT-12A; chưa phải export sẵn trong frontend. Không dùng `CardTemplateItem` cũ thay cho DTO library.

```ts
export type TemplateInputType = 'text' | 'richtext' | 'markdown' | 'image' | 'audio' | 'diagram'
export type TemplateInputSpec = {
  key: string
  label: string
  type: TemplateInputType
  required: boolean
}
export type TemplateBindings = Record<string, string | null>
export type TemplateLibraryGroup = 'all' | 'mine' | 'market' | 'standalone' | 'in_use'
export type TemplateLibraryParams = {
  q?: string
  group?: TemplateLibraryGroup
  category?: string
  include_archived?: boolean
}
export type TemplateLibraryTemplate = {
  id: string
  owner_user_id: number | null
  name: string
  description: string
  primary_category: string | null
  origin: 'authored' | 'market_copy'
  source_template_id: string | null
  source_version_id: string | null
  current_version_id: string | null
  front_html: string
  back_html: string
  shared_css: string
  input_schema: TemplateInputSpec[]
  archived_at: string | null
  created_at: string | null
  updated_at: string | null
}
export type TemplateApplicationUsage = {
  id: string
  application_id: string
  note_type_id: string
  note_type_name: string
  occurrence_key: string
  display_name: string | null
  position: number
  is_default: boolean
}
export type TemplateLibraryItem = TemplateLibraryTemplate & {
  application_count: number
  note_type_count: number
}
export type TemplateLibraryDetail = TemplateLibraryItem & {
  applications: TemplateApplicationUsage[]
}
export type TemplateLibraryResponse = {
  schema_version: 'template-library.v2'
  items: TemplateLibraryItem[]
}
export type TemplateWriteBody = {
  name?: string
  description?: string
  primary_category?: string | null
  front_html?: string
  back_html?: string
  shared_css?: string
  input_schema?: TemplateInputSpec[]
  change_note?: string
  expected_current_version_id?: string | null
}
export type TemplateUpdateResponse = TemplateLibraryTemplate & {
  affected_applications: string[]
}
export type TemplatePreviewBody = {
  front_html?: string
  back_html?: string
  shared_css?: string
  input_schema?: TemplateInputSpec[]
  sample_values?: Record<string, string>
}
export type TemplateLibraryPreview = {
  front_html: string
  back_html: string
  front_renderer_payload: unknown
  back_renderer_payload: unknown
}
export type TemplateBindingWarning = {
  input_key: string
  code: 'INPUT_UNBOUND' | 'INPUT_TYPE_MISMATCH'
  required: boolean
}
export type TemplateApplication = {
  id: string
  application_id: string
  note_type_id: string
  template_id: string
  occurrence_key: string
  status_code: 'ACTIVE' | 'RETIRED'
  display_name: string | null
  position: number
  is_default: boolean
  input_bindings: TemplateBindings
  input_schema: TemplateInputSpec[]
  warnings: TemplateBindingWarning[]
  template: TemplateLibraryTemplate
}
export type TemplateApplicationsResponse = {
  schema_version: 'template-applications.v2'
  items: TemplateApplication[]
}
export type TemplateApplicationPatch = {
  input_bindings?: TemplateBindings
  display_name?: string | null
  position?: number
  is_default?: boolean
}
export type TemplateAttachmentBody = TemplateApplicationPatch & {
  template_id: string
  occurrence_key?: string
}
```

List và detail có count theo attachment **ACTIVE trên NoteType của user hiện tại**. Một NoteType gắn cùng template hai lần có `application_count=2`, `note_type_count=1`. Detail usage summary không chứa `input_bindings`, `status_code`, full template hay version number; muốn sửa binding, gọi API application của NoteType.

Không có `current_version`, `version_no`, `input_keys`, `applied_count`, `definition_id`, `definition_version_id`, `is_outdated` trong DTO library. Dùng `input_schema.map(input => input.key)` và Contract A2 nếu cần số phiên bản.

## 3. Endpoint E2

Mọi endpoint dưới `/api`, yêu cầu login; response thành công `Cache-Control: private, no-store`.

| Method/path | Body/query | Response |
|---|---|---|
| GET `/card-templates` | `q`, `group`, `category`, `include_archived=true` | `TemplateLibraryResponse` |
| POST `/card-templates` | `TemplateWriteBody & {name:string}` | 201 `TemplateLibraryTemplate` |
| GET `/card-templates/<id>` | — | `TemplateLibraryDetail` |
| PATCH `/card-templates/<id>` | `TemplateWriteBody` | `TemplateUpdateResponse` |
| POST `/card-templates/<id>/preview` | `TemplatePreviewBody`, `{}` hợp lệ | `TemplateLibraryPreview` |
| POST `/card-templates/<id>/duplicate` | `{name?:string}` | 201 `TemplateLibraryTemplate` |
| PATCH `/card-templates/<id>/archive` | `{archived:boolean}` | `TemplateLibraryTemplate` |

Group: `all` = toàn bộ library sở hữu; `mine` = origin khác market_copy; `market` = market_copy; `standalone` = không có usage ACTIVE của user; `in_use` = có usage ACTIVE. Filter có thể kết hợp `q/category/include_archived`. `q` tìm substring literal trong **name**, không tìm description; `%` và `_` là ký tự tìm kiếm thường. Không có pagination ở API này.

Save dùng PATCH cùng template ID và gửi `expected_current_version_id` lấy lúc nạp draft, kể cả null. Stale trả 409; không tự retry ghi bằng head mới. Rename/metadata không tạo content version khi source/schema không đổi. Thay HTML/CSS/schema tạo phiên bản; explicit restore luôn tạo phiên bản mới.

`name`: nonblank, ≤255; `primary_category`: string ≤120 hoặc null; `description/front_html/back_html/shared_css`: string. `change_note` theo Contract A2, tối đa 1.000 ký tự (null được chuẩn hóa thành chuỗi rỗng). Body ngoài whitelist bị 400.

Preview không lưu source/head/history và không nhận field_defs/binding/note_type_id. Khi thiếu một source key, dùng source đã lưu; khi thiếu input_schema, dùng effective schema đã lưu. `sample_values` chỉ chứa key trong schema; value string ≤100.000 ký tự, tổng ≤250.000; schema preview tối đa 100 inputs theo raw renderer. Giá trị rỗng `""` được giữ; input không có sample được renderer dựng dữ liệu mẫu. Frontend không tự sanitizer/render raw HTML.

Input schema là array có key unique, không rỗng/whitespace bao quanh; cấm `{ } # ^ / ! > & =` và newline; key `.`/`FrontSide` bị cấm. Label ≤255. Type có đúng sáu giá trị trong DTO. Khi create không gửi schema, server suy ra token; khi PATCH gửi schema, server giữ schema đó, không tự thêm token mới.

## 4. Endpoint F2 và binding

| Method/path | Body/query | Response |
|---|---|---|
| GET `/note-types/<nt>/template-applications` | `include_retired=true` tùy chọn | `TemplateApplicationsResponse` |
| POST `/note-types/<nt>/template-applications` | `TemplateAttachmentBody` | 201 `TemplateApplication` |
| PATCH `/note-types/<nt>/template-applications/<aid>` | `TemplateApplicationPatch` | `TemplateApplication` |
| DELETE `/note-types/<nt>/template-applications/<aid>` | Không body | `TemplateApplication` với RETIRED |

POST defaults: occurrence_key `compat`, position 0, is_default false, input_bindings `{}`, display_name null. `occurrence_key`: nonblank ≤64; `position`: integer ≥0, không boolean; `is_default`: boolean; `display_name`: null/string ≤255. PATCH không được đổi template_id/occurrence_key/status_code.

| Input type | Chỉ nhận field type |
|---|---|
| text | text |
| richtext | richtext |
| markdown | markdown |
| image | image |
| audio | audio |
| diagram | diagram |

Binding omitted key, null và `""` đều unbound; server chuẩn hóa `""` thành null. Không có constraint một field chỉ dùng cho một input. Input không biết → `INPUT_NOT_FOUND`; ID không thuộc field_defs NoteType đó → `FIELD_OUT_OF_SCOPE`; sai kiểu → `INPUT_TYPE_MISMATCH`. Kiểu text/richtext/markdown không hoán đổi cho nhau.

Warnings trong application DTO: mọi input unbound có `INPUT_UNBOUND`, kể cả required false; mapping stale/sai kiểu đã tồn tại có warning. `required` không chặn POST/PATCH hoặc nút xác nhận. Render/session diagnostics là contract riêng; không đổi tên code warning của application thành code study.

GET `/api/note-types` hiện trả `{items:[...]}` có `id/name/field_defs/is_marketplace_install`. FieldDefs có `id/name/field_type/position` và metadata khác. Dùng field ID từ NoteType được chọn, không đưa source field ID của tác giả sang NoteType của người nhận. Loại thẻ đã cài có thể được chọn; không có trường `is_marketplace_install` trong response GET detail NoteType hiện tại.

## 5. Error surface

Response lỗi: `{error:string,message:string,field?:string,details?:unknown}`. Frontend đọc `ApiError.code/status/field` từ `@/shared/api/client`; không suy diễn `details.missing_keys`.

| Code | HTTP | Ý nghĩa |
|---|---|---|
| VALIDATION_ERROR | 400 | Body/query/schema/value không hợp lệ |
| TEMPLATE_COMPILE_ERROR | 400 | Source template không compile được |
| INPUT_NOT_FOUND | 400 | Binding/sample có input key không có trong schema |
| FIELD_OUT_OF_SCOPE | 400 | Field không có trong NoteType được chọn |
| INPUT_TYPE_MISMATCH | 400 | Binding sai exact type |
| TEMPLATE_NOT_FOUND | 404 | Template không tồn tại hoặc user không sở hữu |
| NOTE_TYPE_NOT_FOUND | 404 | NoteType không tồn tại hoặc không thuộc user |
| APPLICATION_NOT_FOUND | 404 | Application không thuộc NoteType đó hoặc không tìm thấy |
| TEMPLATE_VERSION_STALE | 409 | Expected head khác current head |
| TEMPLATE_ARCHIVED | 409 | Gắn template đã archive |
| APPLICATION_EXISTS | 409 | Occurrence ACTIVE đã tồn tại |
| APPLICATION_RETIRED | 409 | PATCH vào occurrence RETIRED |
| MARKET_TEMPLATE_REPUBLISH_FORBIDDEN | 403 | Duplicate market copy thành authored bị chặn |

Expansion/card topology có thể trả lỗi ContentApiError từ nền NOTE. Hiện message server và giữ draft/mapping; không giả lập thành công hoặc tự tạo card trên client.

## 6. Frontend boundary và dependency

- Entity contract ở `entities/card-template`; UI library ở feature mới. Chỉ file page được ghép `NoteTypeLivePreview` từ feature note-types và `TemplateVersionHistorySheet` từ GT-10B.
- Reusable input editor/mapping editor và hooks không import feature note-types, template-versions, scheduler hoặc session runtime.
- GT-10B chưa có component trong workspace tại thời điểm viết. GT-12A/B/C không phụ thuộc nó; phase detail/history GT-12D chỉ mở sau GT-10B được review. Đây là dependency frontend.
- A2 restore trả serializer `CardTemplateItem` cũ, `note_type_id` có thể null cho standalone và không trả input_schema. GT-12A sửa kiểu nullability, giữ existing fields. Sau restore, gán trực tiếp HTML/CSS response rồi GET library detail để lấy schema/head. Không dựng giả NoteType ID hoặc ép DTO library thành CardTemplateItem.
- Shell/route wiring là phase riêng; giữ DOM/class/gradient/padding/layout hiện hữu. Không thêm navigation route trỏ tới file page chưa tồn tại.
