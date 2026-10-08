# GT-12 — Thư viện Mẫu thẻ, editor và shell (v2)

- Owner: Gemini. Reviewer: Codex. Contract: [E2/F2](../../architecture/template-library-attachments-contract-2026-10-07.md).
- Trạng thái 2026-10-08: **GT-12A/B/C/D/E Completed / verified**; xem [CT-R2](reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md). Các dependency và whitelist dưới là tiêu chí triển khai đã hoàn tất.
- Làm tuần tự, chỉ phase được giao, không commit/push/stash/reset. Không sửa backend/schema/session runtime hoặc file ngoài whitelist. Dùng nhánh U8 và giữ mọi diff của người khác.

## 1. Hành vi và ranh giới

Template là identity dùng chung. Library list trả source, input_schema và count; editor lưu PATCH cùng ID với expected head. Attachment giữ template ID và mapping theo FieldDef ID. Không có copy-on-apply, token rewrite, sync-definition hoặc trạng thái is_outdated của attachment.

Giữ nguyên UI NoteType/editor/sidebar/shell; trang mới dùng màu/gradient/primitives hiện có. Chỉ file `pages/*.tsx` được import NoteTypeLivePreview hoặc history feature để ghép UI. Component/hook template-library không import feature khác. Đọc AGENTS.md, `skills/flama-frontend-architecture/SKILL.md`, `skills/impeccable/SKILL.md` trước triển khai.

## 2. Phase và file ownership

Mỗi đường dẫn dưới `frontend/src/`. Không sửa shared primitives ngoài whitelist.

| Phase | Dependency frontend | Whitelist |
|---|---|---|
| GT-12A entity | Ready; nền GT-10A hiện có | `entities/card-template/model/types.ts`, `api/cardTemplateApi.ts`, `api/queryKeys.ts`, `index.ts`, `api/cardTemplateApi.test.ts` (5 file) |
| GT-12B list/create | GT-12A Accepted | `features/template-library/pages/TemplateLibraryPage.tsx`, `pages/TemplateLibraryPage.test.tsx`, `components/CreateTemplateDialog.tsx`, `components/CreateTemplateDialog.test.tsx`, `index.ts` (5) |
| GT-12C input schema editor | GT-12A Accepted; độc lập GT-12B | `features/template-library/components/TemplateInputSchemaEditor.tsx`, `components/TemplateInputSchemaEditor.test.tsx`, `lib/inputSchemaValidation.ts`, `lib/inputSchemaValidation.test.ts` (4) |
| GT-12D detail/draft/preview/history | GT-12A/B/C và **GT-10B Accepted** | `features/template-library/model/useTemplateLibraryEditor.ts`, `model/useTemplateLibraryEditor.test.tsx`, `pages/TemplateDetailPage.tsx`, `pages/TemplateDetailPage.test.tsx`, `index.ts` (5) |
| GT-12E shell | GT-12B/D Accepted | `App.tsx`, `components/app-sidebar.tsx`, `layouts/AppLayout.tsx`, `features/template-library/pages/TemplateLibraryShell.test.tsx` (4) |

Trong một ô whitelist, các path sau path đầy đủ đầu tiên cùng prefix feature/entity đó. GT-12C chưa sửa index; GT-12D import nội bộ input editor và export page qua feature index. Không giao hai worker sửa cùng entity/index/page.

## 3. GT-12A — entity contract

Thêm/export nguyên DTO Contract E2/F2 §2, giữ mọi export/test hiện có. Sửa `CardTemplateItem.note_type_id` thành `string | null`: standalone A2 restore thực tế có origin NoteType null. Bổ sung origin lịch sử `market_copy`/`update` nếu GT-10 chưa cập nhật; giữ origin cũ.

Hàm mới dưới đây là **output của phase**, chưa phải symbol có sẵn. Dùng apiRequest/apiJson từ `@/shared/api/client`, encodeURIComponent từng ID, truyền signal cho GET/preview.

| Hàm | Request / return |
|---|---|
| `fetchTemplateLibrary(params: TemplateLibraryParams = {}, signal?)` | GET `/api/card-templates`, TemplateLibraryResponse |
| `fetchLibraryTemplate(id, signal?)` | GET `/api/card-templates/{id}`, TemplateLibraryDetail |
| `createLibraryTemplate(body: TemplateWriteBody & {name:string})` | POST base, TemplateLibraryTemplate |
| `updateLibraryTemplate(id, body: TemplateWriteBody)` | PATCH `/{id}`, TemplateUpdateResponse |
| `previewLibraryTemplate(id, body: TemplatePreviewBody, signal?)` | POST `/{id}/preview`, TemplateLibraryPreview |
| `archiveLibraryTemplate(id, archived:boolean)` | PATCH `/{id}/archive` `{archived}`, TemplateLibraryTemplate |
| `duplicateLibraryTemplate(id, body: {name?:string} = {})` | POST `/{id}/duplicate`, TemplateLibraryTemplate |
| `fetchTemplateApplications(nt, includeRetired = false, signal?)` | GET `/api/note-types/{nt}/template-applications`, query include_retired=true chỉ khi true, TemplateApplicationsResponse |
| `attachLibraryTemplate(nt, body: TemplateAttachmentBody)` | POST application collection, TemplateApplication |
| `updateTemplateApplication(nt, aid, body: TemplateApplicationPatch)` | PATCH application detail, TemplateApplication |
| `retireTemplateApplication(nt, aid)` | DELETE application detail, không body, TemplateApplication |

Preview dùng apiRequest với POST, JSON body, signal và JSON Content-Type như apiJson; giữ shared client CSRF, không tự fetch. Query URLSearchParams theo thứ tự q/group/category/include_archived; bỏ string rỗng/undefined và false; true gửi literal `true`. Không trim q. Params `{}` → URL base không trailing `?`.

Thêm key, giữ key cũ:

```ts
library: (p: TemplateLibraryParams = {}) =>
  ['card-template', 'library', p.q ?? '', p.group ?? 'all', p.category ?? '', p.include_archived ?? false] as const
libraryDetail: (id: string) => ['card-template', 'library-detail', id] as const
applications: (nt: string, includeRetired = false) =>
  ['card-template', 'applications', nt, includeRetired] as const
```

Tests API: từng method/body/response; encode ID có `/ ? #`; q tiếng Nhật/`%_` encode literal; false query bị bỏ; preview signal; DELETE không body; ApiError nguyên gốc; A2 assertions cũ còn pass.

## 4. GT-12B — list/create

Export named TemplateLibraryPage; route nối GT-12E. Dùng Page/PageHeader và PageState từ shared/components; SearchInput/FilterPillGroup từ shared/ui. SearchInput onChange nhận event; tự debounce 300ms, cleanup và giữ IME flow. FilterPillGroup single mode nhận options/value/onChange.

Chuỗi và layout:

- Header `Mẫu thẻ`; description `Thư viện template dùng lại cho nhiều loại thẻ.`; action `Tạo mẫu mới`.
- Filter `Tất cả` all, `Của tôi` mine, `Marketplace` market, `Mẫu độc lập` standalone, `Đang dùng` in_use.
- Loading `Đang tải mẫu thẻ…`; empty `Chưa có mẫu thẻ nào.`; PageError hiện message/retry.
- Grid `grid gap-3 sm:grid-cols-2 lg:grid-cols-3`, Link `/card-templates/{encoded id}`; tên/mô tả line-clamp-2; origin badge `Của tôi`/`Bản nhận`; `Dùng ở {note_type_count} loại thẻ` hoặc `Chưa dùng`; thêm `{application_count} lần gắn` khi count > note_type_count.
- Tokens từ input_schema, tối đa 4 `{{key}}`, còn lại `+N`. Không suy version number từ UUID.

Create dialog tên nonblank ≤255, mô tả string; khóa submit khi invalid/pending. Body:

```ts
{
  name: name.trim(), description,
  front_html: '{{Front}}', back_html: '{{Front}}<hr>{{Back}}', shared_css: '',
  input_schema: [
    { key: 'Front', label: 'Front', type: 'text', required: false },
    { key: 'Back', label: 'Back', type: 'text', required: false },
  ],
}
```

Success invalidate library prefix, toast `Đã tạo mẫu thẻ.`, navigate detail ID encoded. Lỗi giữ form/message; đóng/mở không điều hướng bằng success cũ. Tests: default fetch `{}`; cả 5 filters; debounce final q; loading/error/empty; 2 applications cùng NT→count 1 NT/2 lần gắn; 6 inputs→4/+2; whitespace name không submit; default body/navigation đúng; lỗi giữ input.

## 5. GT-12C — input schema editor thuần

```ts
type TemplateInputSchemaEditorProps = {
  value: TemplateInputSpec[]
  onChange: (value: TemplateInputSpec[]) => void
  disabled?: boolean
}
```

Dùng Input/Label/NativeSelect/Button. Mỗi hàng key/label/6 type/checkbox `Khuyến nghị ánh xạ`; action `Thêm input`/`Xóa input`; mô tả `Input chưa ánh xạ sẽ hiển thị rỗng.`. Không API, không rewrite HTML token khi đổi key. Inline validation theo Contract §3; cho nhập draft tạm invalid nhưng page chặn save. Input mới key/label Input{n} chưa dùng, text, required false. Change tạo array/object mới.

Export named validator `inputSchemaIssues(value): Array<{index:number;message:string}>` trong lib/inputSchemaValidation.ts để component/page dùng; không import feature khác. Tests: exact types; required chỉ là khuyến nghị; duplicate/reserved/whitespace key được báo; add/delete không mutate props; disabled giữ value.

## 6. GT-12D — detail/draft/preview/history

Chỉ giao sau GT-10B review; đọc public API thật `features/template-versions/index.ts`, không tạo fake dependency.

TemplateDetailPage đọc route id, query libraryDetail(id), DTO phẳng. Hook useTemplateLibraryEditor quản lý draft HTML/CSS/input_schema/name/description/primary_category, baseline expected head và sample_values của đúng ID. Background refetch không đè dirty draft. Đổi route reset selection/draft/sample/preview; response cũ không ghi vào route mới.

Header `Quay lại` `/card-templates`, `Lịch sử`, `Lưu trữ`/`Bỏ lưu trữ`; nút `Áp dụng vào loại thẻ` disabled với title `Chờ wizard ánh xạ` đến GT-13C. TemplateCodeEditor dùng fields `{id:key,name:key}` từ draft schema và đúng props hiện có. Ghép input editor, metadata và string sample inputs. `Lưu thay đổi` gửi source/schema/metadata cùng expected_current_version_id **từ baseline draft**, không lấy head refetch khi dirty.

Success áp response source/head trực tiếp, refresh detail/usage, invalidate `['card-template']` và NoteType detail của usages, toast `Đã lưu mẫu thẻ.`. 409 stale giữ draft, message `Mẫu thẻ đã thay đổi. Hãy tải lại trước khi lưu.`; action `Tải lại` ConfirmDialog khi dirty. Không tự retry PATCH bằng head mới.

Preview debounce 500ms; abort khi draft đổi/route đổi/unmount; chỉ latest response được áp. Body đầy đủ front_html/back_html/shared_css/input_schema/sample_values. Giữ sample `''`, bỏ key sample đã xóa. **Page** import NoteTypeLivePreview từ `@/features/note-types/components/NoteTypeLivePreview`; props cardId `library-preview:{id}`, frontPayload/backPayload từ front_renderer_payload/back_renderer_payload, HTML response, fieldDefs `{id:\`f_${index}\`,name:key,field_type:type,position:index}` khớp raw preview renderer. Hook/component khác không import preview feature; không tự render HTML chưa sanitize.

Block `Đang dùng ở`: link `/note-types/{nt}`, NoteType name, display_name hoặc template.name, occurrence_key; message `Thay đổi mẫu này áp dụng cho mọi loại thẻ đang gắn.` và count. Không trạng thái outdated/sync mỗi attachment.

Archive ConfirmDialog title `Lưu trữ mẫu thẻ này?`, description `Mẫu sẽ ẩn khỏi thư viện. Các loại thẻ đang dùng không bị ảnh hưởng.`; PATCH `{archived:true}`; unarchive `{archived:false}`; invalidate, không xóa Card/application.

History adapter A2 từ GT-10B dùng template ID và API existing fetchTemplateVersions/fetchTemplateVersion/restoreTemplateVersion. `onRestored` **gán trực tiếp response HTML/back/CSS/head**, kể cả source giống server cache, sau đó GET detail lấy input_schema/metadata. Khóa editor/save trong lúc restore/refetch schema. Response route cũ bị bỏ qua. Không dựng giả note_type_id để ép library DTO sang CardTemplateItem.

Tests hook/page: refetch giữ dirty; đổi route bỏ response cũ; PATCH baseline head; stale giữ draft; success head mới; required unbound không chặn save; preview debounce/abort/latest; sample `''`; usage không sync; archive exact method/body; restore thay dirty draft **khi response source giống server**, GET detail cập nhật schema/head; restore lỗi giữ draft; route switch không nhận nguồn cũ.

## 7. GT-12E — shell

- App.tsx: named lazy imports public exports TemplateLibraryPage/TemplateDetailPage; routes card-templates/card-templates/:id dùng deferred và auth layout như NoteType, giữ route cũ.
- app-sidebar.tsx: sau Loại thẻ trong library thêm `{title:'Mẫu thẻ',url:'/card-templates',icon:Layers}`, bổ sung lucide import; giữ class/layout/item cũ.
- AppLayout.tsx: thêm `'/card-templates':'Mẫu thẻ'` vào pageTitles, giữ breadcrumb logic.
- Smoke test mới: list/detail routes dùng named exports đúng; navigation item URL đúng; NoteType route cũ còn hoạt động. Dùng router/provider pattern hiện có; không sửa App chỉ để export private router phục vụ test. Reviewer kiểm shell diff.

Reviewer browser gate desktop/mobile375px/light/dark: list→create→detail→history→archive. Chrome riêng profile theo AGENTS.md. Không ghi browser PASS nếu chưa chạy.

## 8. Validation và giao task

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/template-library
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

GT-12D/E thêm `npm --prefix frontend run test -- src/features/template-versions src/features/note-types`. Báo output thật/whitelist diff/dependency chưa có/việc chưa kiểm browser. Không update snapshot hàng loạt.

Giao đúng một prompt: GT-12A.prompt.txt, GT-12B.prompt.txt, GT-12C.prompt.txt, GT-12D.prompt.txt hoặc GT-12E.prompt.txt. Không giao toàn spec một lượt.
