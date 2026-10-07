# GT-13 — Gắn mẫu dùng chung và ánh xạ input (v2)

- Owner: Gemini. Reviewer: Codex. Backend F2 đã có code/test; dependency còn lại là frontend.
- Contract: [E2/F2](../../architecture/template-library-attachments-contract-2026-10-07.md). GT-13A mở sau GT-12A Accepted; không dùng spec copy/apply-token rewrite của v1.
- Đọc AGENTS.md và skills/flama-frontend-architecture + impeccable; giữ Zero Visual Regression. Mỗi lượt chỉ whitelist phase được giao, không commit/push/stash/reset. Không sửa backend/scheduler/session runtime/media renderer/shared primitives.

## 1. Identity và quy tắc

Gắn = POST application cho NoteType, **giữ template_id của library**. Source không đổi token theo tên field. Input key trỏ FieldDef ID của NoteType đang chọn; nhiều inputs dùng một field hợp lệ. Text/richtext/markdown là ba kiểu riêng, chỉ exact type tương thích.

Required là khuyến nghị. Omitted/null/chuỗi rỗng = unbound, chỉ warning, nút Gắn vẫn được bấm. ID field không có trong NoteType hoặc sai kiểu là lỗi blocking; không coi field ID stale như input bỏ trống. API application warnings dùng INPUT_UNBOUND/INPUT_TYPE_MISMATCH, không dùng missing_required hoặc study runtime warning codes.

## 2. Phase và ownership

Mọi đường dẫn dưới frontend/src; path sau path đầu tiên trong ô dùng cùng prefix feature/entity.

| Phase | Dependency frontend | Whitelist |
|---|---|---|
| GT-13A mapping thuần | GT-12A Accepted | `entities/card-template/lib/fieldMapping.ts`, `lib/fieldMapping.test.ts`, `index.ts` (3 file) |
| GT-13B mapping UI/wizard | GT-13A Accepted | `features/template-library/components/FieldMappingEditor.tsx`, `components/FieldMappingEditor.test.tsx`, `components/ApplyTemplateWizard.tsx`, `components/ApplyTemplateWizard.test.tsx`, `index.ts` (5) |
| GT-13C nối library page | GT-12D và GT-13B Accepted | `features/template-library/pages/TemplateDetailPage.tsx`, `pages/TemplateDetailPage.test.tsx` (2) |
| GT-13D quản lý attachment trên NoteType | GT-13B Accepted, GT-12D Accepted cho link library | `features/template-library/components/TemplateApplicationsPanel.tsx`, `components/TemplateApplicationsPanel.test.tsx`, `index.ts`, `features/note-types/pages/NoteTypeDetailPage.tsx`, `features/note-types/pages/NoteTypeDetailPage.applications.test.tsx` (5) |

GT-12A đã thêm toàn bộ GET/POST/PATCH/DELETE application API; GT-13 không sửa lại entity API/type/key để tránh ownership trùng. GT-13D là phần list/sửa/gỡ của Contract F2; không thay management bar/editor cũ. Chỉ page NoteType được import public feature template-library để ghép panel.

## 3. GT-13A — pure mapping

Đây là symbol cần tạo/export ở phase, chưa có trong entity hiện tại:

```ts
export type MappingField = { id: string; name: string; field_type: string }
export type MappingInput = TemplateInputSpec
export type MappingIssue =
  | { kind: 'unbound'; key: string; required: boolean; blocking: false }
  | { kind: 'field_out_of_scope'; key: string; fieldId: string; blocking: true }
  | { kind: 'type_mismatch'; key: string; fieldId: string; blocking: true }
  | { kind: 'unknown_input'; key: string; blocking: true }

export function isTypeCompatible(inputType: string, fieldType: string): boolean
export function suggestBindings(inputs: MappingInput[], fields: MappingField[]): TemplateBindings
export function validateBindings(inputs: MappingInput[], fields: MappingField[], bindings: TemplateBindings): MappingIssue[]
```

- isTypeCompatible true chỉ khi hai string bằng nhau và nằm trong sáu type Contract; text↔markdown/richtext false.
- suggestBindings: từng input theo thứ tự schema, chọn field đầu tiên có name.trim().toLowerCase() bằng key.trim().toLowerCase() **và exact type**; thiếu → key:null. Cho phép cùng field ID phục vụ nhiều inputs. Không dùng label thay key, không map theo vị trí.
- validateBindings: theo thứ tự inputs, omitted/null/'' → unbound warning; ID lạ → field_out_of_scope blocking; type khác → type_mismatch blocking; sau đó các binding key ngoài schema theo thứ tự object → unknown_input blocking. Không duplicate_field issue. Không sửa input objects.

Tests: cả sáu exact types; unknown same strings vẫn false; text→markdown/richtext false; media mismatch; normalized name suggestion; wrong-type same-name không suggested; hai input Word/word dùng cùng field; missing required vẫn blocking=false; unknown ID required=false vẫn blocking; null/''; unknown input; issue ordering; immutability.

## 4. GT-13B — FieldMappingEditor

Props `{inputs:MappingInput[];fields:MappingField[];bindings:TemplateBindings;onChange:(next:TemplateBindings)=>void;issues:MappingIssue[];disabled?:boolean}`.

Mỗi hàng: key `{{key}}`, label, badge `Khuyến nghị` khi required; NativeSelect gồm `— Không dùng —` và fields `{name} · {field_type}`. Value select `bindings[key] ?? ''`; chọn empty → next[key]=null. Giữ options sai type visible nhưng disabled; mapping stale hiện lỗi, không im lặng đổi sang null.

Chuỗi diagnostics:

- Unbound optional: `Input này sẽ hiển thị rỗng.`
- Unbound recommended: `Input được khuyến nghị chưa ánh xạ; vẫn có thể sử dụng.`
- field_out_of_scope: `Trường không thuộc loại thẻ đã chọn.`
- type_mismatch: `Kiểu trường không phù hợp.`
- unknown_input: `Input không còn trong mẫu thẻ.`

Warnings dùng muted/amber, blocking dùng destructive; giữ label/select accessible. Change object mới, không mutate props. Tests select→mapping ID/null; recommended advisory; sai type disabled; stale target báo; repeated target hợp lệ; disabled không đổi.

## 5. GT-13B — ApplyTemplateWizard

Props `{open:boolean;onOpenChange:(open:boolean)=>void;template:TemplateLibraryDetail;initialNoteTypeId?:string}`. Dialog hai bước, dùng entity APIs GT-12A và mapping GT-13A. Không import NoteType feature, không import live preview/history.

1. `Chọn loại thẻ`: useQuery chỉ enabled khi open, apiRequest `/api/note-types` với AbortSignal; local DTO `{items:Array<{id:string;name:string;field_defs:Array<{id:string;name:string;field_type:string;position:number}>;is_marketplace_install:boolean}>}` từ API thật. Installed NoteType vẫn selectable, badge `Bản cài từ marketplace`. Loading/error/empty có thể retry; không đổi tên installed fields.
2. `Ánh xạ trường`: suggestBindings trên input_schema library + field_defs NoteType đã chọn. Ô `Tên hiển thị` mặc định template.name (đây là display_name attachment); ô `Mã lần gắn` mặc định compat (occurrence_key nonblank≤64). Mô tả `Mẫu dùng chung giữ nguyên nội dung; ánh xạ chỉ áp dụng cho loại thẻ này.`. Có thể bỏ trống mọi input. Nút `Gắn mẫu` disabled chỉ khi blocking issue, invalid occurrence/display_name, archived template hoặc request pending.

Thay NoteType reset mapping sang field IDs của NoteType mới; không gửi ID còn giữ từ lựa chọn cũ. Mở lại reset state lỗi/pending/step theo template hiện tại. Khi initialNoteTypeId có trong list có thể vào mapping thẳng; id không có thì giữ bước chọn, không tự fetch template source của user khác.

Submit:

```ts
attachLibraryTemplate(selectedNoteTypeId, {
  template_id: template.id,
  occurrence_key: occurrence.trim(),
  display_name: displayName,
  input_bindings: bindings, // null hợp lệ, không dùng tên field làm value
})
```

Không gửi note_type_id/name/source HTML/definition_id/version ID trong body. POST 409 APPLICATION_EXISTS: hiện `Lần gắn này đã tồn tại. Chọn mã lần gắn khác hoặc sửa ánh xạ hiện có.`; không auto duplicate template hoặc tự đổi occurrence. Có thể dùng mã khác để tạo occurrence thứ hai. RETIRED cùng occurrence được backend khôi phục cùng ID.

Success response template_id phải là library ID, toast `Đã gắn mẫu vào loại thẻ.` với action `Mở loại thẻ` navigate `/note-types/{encoded id}`, đóng dialog, invalidate `['card-template']`, `['note-type-detail',nt]` và `['note-types']`. Lỗi hiện Alert/message server, giữ mapping/step; ApiError.field đánh dấu input nếu đúng key. Không dùng details.missing_keys/INPUT_BINDING_INCOMPLETE không tồn tại.

Tests wizard: bước1→2; initial selection; installed selectable; gợi ý exact type; recommended unbound vẫn submit; hai inputs một field vẫn submit; sai type/stale target blocking; đổi NoteType không giữ ID cũ; correct method/path/body; success template identity; duplicate conflict giữ mapping; server compile/scope errors; close/reopen và pending response không tác động template khác.

## 6. GT-13C — bật library action

TemplateDetailPage import ApplyTemplateWizard qua `@/features/template-library` public index hoặc nội bộ cùng feature. Nút `Áp dụng vào loại thẻ` mở wizard, không disabled placeholder nữa; archive vẫn disabled với giải thích `Bỏ lưu trữ để gắn mẫu.`. Detail usages/count refetch sau attach; không tạo application frontend cache từ dữ liệu suy diễn.

Tests: click mở với đúng template detail; archive không mở; attach success count 2 usages cùng NoteType vẫn note_type_count=1; ID template không đổi; hook preview/history vẫn giữ; existing GT12D tests còn pass.

## 7. GT-13D — NoteType application management

Panel props `{noteTypeId:string}`; public export TemplateApplicationsPanel. Page NoteType thêm panel dưới khu editor/preview hiện có; không sửa class/DOM/layout/callback editor và management bar cũ. Tests mới giữ draft khi application query refetch.

Panel query fetchTemplateApplications(nt,true); hiện `Mẫu đã gắn`, template.name (link library canonical id), display_name, occurrence, ACTIVE/RETIRED. Edit ACTIVE mở dialog FieldMappingEditor, fields từ apiRequest GET `/api/note-types/{nt}` (response có field_defs; không suy is_marketplace_install từ detail). PATCH {input_bindings,display_name} vào application ID, không sửa template source. Recommended missing warning không chặn save. Server issue giữ dialog/mapping.

`Gỡ mẫu` ConfirmDialog title `Gỡ mẫu khỏi loại thẻ?`, description `Mẫu sẽ ngừng xuất hiện khi học. Tiến độ đã học được giữ lại.` → retireTemplateApplication(nt,aid), nhận RETIRED. `Gắn lại` POST cùng template_id/occurrence_key/input_bindings/display_name/position/is_default của row, backend phục hồi cùng ID. Không DELETE template hoặc Card, không tạo tiến độ mới.

Không import ApplyTemplateWizard từ feature khác vào component; các component cùng template-library được import nội bộ. Action quản lý không gọi client học/session endpoints. Invalidate card-template prefix/NoteType detail sau mutation; không ghi đè editor draft từ query refetch.

Tests: active/retired; mapped FieldDef ID exact; PATCH application giữ template identity/source; required unbound save; DELETE returns RETIRED, progress text; reattach POST cùng occurrence và giữ application ID; scope errors; page editor draft không mất khi panel refresh; NoteType existing snapshots giữ UI cũ (reviewer kiểm phần thêm riêng).

## 8. Validation/giao task

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/template-library
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

GT-13C thêm test features/template-versions và GT-13D thêm `npm --prefix frontend run test -- src/features/note-types`. Báo output thật/whitelist diff/việc chưa kiểm browser. Không update snapshots hàng loạt. Reviewer browser smoke dark/light/mobile375px với owner và market-copy của user, dùng Chrome profile riêng.

Prompt files: GT-13A.prompt.txt, GT-13B.prompt.txt, GT-13C.prompt.txt, GT-13D.prompt.txt. Mỗi lượt chỉ một phase; không mở phase khi frontend dependency chưa review.
