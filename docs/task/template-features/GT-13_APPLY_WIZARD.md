# GT-13 — Wizard "Áp dụng vào loại thẻ" và `FieldMappingEditor`

- Owner: Gemini. Reviewer: Claude. Milestone: M4.
- Trạng thái: **Blocked** đến khi GT-12 `Accepted` và CT-06 xác nhận mã lỗi apply.
- Loại: dialog nhiều bước + component ánh xạ thuần.

## 0. Việc Claude làm trước khi mở task

- [ ] Xác nhận body/response/mã lỗi `POST /api/card-templates/<id>/apply` (kế hoạch §5.5) và quy tắc tương thích kiểu field ↔ input do CT-06 chốt; điền bảng §3.2.
- [ ] Đổi trạng thái README thành `Ready`.

## 1. Bối cảnh

Áp dụng một mẫu vào loại thẻ = tạo một template mới của loại thẻ đó, với `input_bindings` ánh xạ từng input của mẫu (`key`) sang một field (`field_def_id`) của loại thẻ. Backend từ chối khi thiếu input bắt buộc, field không tồn tại/khác loại thẻ, một input gắn nhiều field, hoặc sai kiểu (bảng binding P3-07).

## 2. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/lib/fieldMapping.ts` (+ `.test.ts`) | Tạo mới: hàm thuần §3.1. |
| `frontend/src/entities/card-template/api/cardTemplateApi.ts`, `index.ts`, test API | Thêm `applyTemplateDefinition`. |
| `frontend/src/features/template-library/components/FieldMappingEditor.tsx` (+ test) | Tạo mới. |
| `frontend/src/features/template-library/components/ApplyTemplateWizard.tsx` (+ test) | Tạo mới. |
| `frontend/src/features/template-library/pages/TemplateDefinitionPage.tsx` | Bật nút "Áp dụng vào loại thẻ" mở wizard. |

## 3. Hợp đồng chính xác

### 3.1 `lib/fieldMapping.ts`

```ts
export type MappingField = { id: string; name: string; field_type: string }
export type MappingInput = { key: string; label: string; type: string; required: boolean }
export type MappingIssue =
  | { kind: 'missing_required'; key: string }
  | { kind: 'type_mismatch'; key: string; fieldId: string }
  | { kind: 'duplicate_field'; fieldId: string; keys: string[] }

export function suggestBindings(inputs: MappingInput[], fields: MappingField[]): Record<string, string>
export function validateBindings(inputs: MappingInput[], fields: MappingField[], bindings: Record<string, string>): MappingIssue[]
export function isTypeCompatible(inputType: string, fieldType: string): boolean
```

- `suggestBindings`: với mỗi input, chọn field có `name.trim().toLowerCase() === key.trim().toLowerCase()`; không có thì bỏ qua. Không gán một field cho hai input (input đứng trước thắng).
- `isTypeCompatible` theo bảng §3.2 (Claude điền ở §0; mặc định: trùng kiểu thì `true`; `text` ↔ `richtext` ↔ `markdown` `true`; media (`image`, `audio`, `diagram`) chỉ khớp đúng kiểu đó).
- `validateBindings` trả issue theo thứ tự: `missing_required` theo thứ tự `inputs`, rồi `type_mismatch` theo thứ tự `inputs`, rồi `duplicate_field` theo thứ tự xuất hiện field đầu tiên. Binding trỏ id không có trong `fields` coi như thiếu (nếu input bắt buộc) hoặc bỏ qua (nếu không bắt buộc).

### 3.2 Bảng tương thích (Claude xác nhận ở §0)

| Input \ Field | text | richtext | markdown | image | audio | diagram |
|---|---|---|---|---|---|---|
| text | ✓ | ✓ | ✓ | | | |
| richtext | ✓ | ✓ | ✓ | | | |
| markdown | ✓ | ✓ | ✓ | | | |
| image | | | | ✓ | | |
| audio | | | | | ✓ | |
| diagram | | | | | | ✓ |

### 3.3 API

`applyTemplateDefinition(id, body: { note_type_id: string; name?: string; input_bindings: Record<string, string> })` → `apiJson<CardTemplateItem & { definition_id: string | null; definition_version_id: string | null; version_no: number | null }>(\`/api/card-templates/${enc(id)}/apply\`, 'POST', body)`.

### 3.4 `FieldMappingEditor`

Props: `{ inputs: MappingInput[]; fields: MappingField[]; bindings: Record<string,string>; onChange: (next: Record<string,string>) => void; issues: MappingIssue[] }`. Mỗi input một hàng: trái `{{key}}` (font-mono) + label + `Bắt buộc` (badge) nếu required; phải `NativeSelect` gồm option rỗng `— Không dùng —` và mọi field (`{name} · {field_type}`). Hàng có issue hiện chữ đỏ: `Thiếu trường cho input bắt buộc.` / `Kiểu trường không phù hợp.` / `Trường này đang được dùng cho input khác.`

### 3.5 `ApplyTemplateWizard`

Dialog 2 bước, props `{ open; onOpenChange; definition: TemplateLibraryDetail }`:

1. `Chọn loại thẻ`: danh sách loại thẻ từ `GET /api/note-types` (dùng `apiRequest<{ items: Array<{ id: string; name: string; field_defs?: MappingField[]; is_marketplace_install?: boolean }> }>('/api/note-types')` trong file wizard, không thêm vào entity). Loại thẻ `is_marketplace_install === true` vẫn hiện, kèm nhãn `Bản cài từ marketplace`.
2. `Ánh xạ trường`: `FieldMappingEditor` khởi tạo bằng `suggestBindings`; ô `Tên template` mặc định `definition.name`. Nút `Áp dụng` disabled khi `validateBindings` trả issue `missing_required`/`type_mismatch`/`duplicate_field` nào. Gửi `input_bindings` chỉ gồm key có giá trị khác rỗng.

Thành công → `toast.success('Đã áp dụng mẫu vào loại thẻ.', { action: { label: 'Mở loại thẻ', onClick: () => navigate(\`/note-types/${note_type_id}\`) } })`, đóng dialog, invalidate `definition(id)` và `noteTypeTemplates(note_type_id)`. Lỗi từ server: hiện `Alert` trong dialog với message server; `INPUT_BINDING_INCOMPLETE` thì đánh dấu các `details.missing_keys` trên editor.

## 4. Test bắt buộc

- `fieldMapping.test.ts`: suggest không phân biệt hoa thường; không gán trùng field; thiếu bắt buộc; sai kiểu `image`→`text`; `text`→`markdown` hợp lệ; trùng field; binding trỏ id lạ; thứ tự issue.
- `FieldMappingEditor.test.tsx`: đổi select gọi `onChange` với object mới (không mutate cũ); hiện đúng chuỗi lỗi.
- `ApplyTemplateWizard.test.tsx`: bước 1 → 2; gợi ý tự động; nút Áp dụng disabled khi thiếu; gửi đúng body; lỗi server hiện `Alert`.

## 5. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/template-library
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

## 6. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-13. Đọc và làm đúng theo docs/task/template-features/GT-13_APPLY_WIZARD.md (§1–§5; bỏ qua §0).
Đọc thêm: frontend/src/entities/card-template/index.ts, frontend/src/features/template-library/**,
frontend/src/components/ui/native-select.tsx, frontend/src/components/ui/dialog.tsx.
Chuỗi tiếng Việt NGUYÊN VĂN. Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
