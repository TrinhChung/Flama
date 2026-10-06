# GT-06 — Quản lý template trên trang loại thẻ (số note, mặc định, đổi tên, xóa, lỗi thân thiện)

- Owner: Gemini. Reviewer: Claude. Milestone: M1.
- Phụ thuộc: GT-02 (API `note_count`), GT-04 (entity), GT-05 (`TemplateCodeEditor`) đều `Accepted`.
- Loại: UI mới trong trang có sẵn. Phần UI cũ giữ nguyên class/DOM.

## 1. Bối cảnh

Sau GT-05, `NoteTypeDetailPage.tsx` render `<TemplateCodeEditor headerActions={...} footer={...} .../>`. `headerActions` hiện có: `NativeSelect` chọn template, nút "Mới" (`createTemplateMutation`), nút "Reset" (`resetTemplateMutation`).

Backend đã có (không sửa): `PATCH /api/note-types/<nt>/templates/<tid>` nhận `{ name }`; `DELETE /api/note-types/<nt>/templates/<tid>` trả `{ success: true }`, từ chối template mặc định (409 `VALIDATION_ERROR` "Cannot delete default template.") và template cuối cùng (409 `VALIDATION_ERROR` "A note type requires at least one template."); NoteType có release chia sẻ trả 409 `SHARED_SCHEMA_VERSIONING_REQUIRED` cho thao tác cấu trúc. Sau GT-01, `POST .../templates` không gửi `front_html/back_html` sẽ nhận nội dung mặc định theo field thật.

Entity (GT-04) có: `fetchNoteTypeTemplates`, `renameNoteTypeTemplate`, `deleteNoteTypeTemplate`, `cardTemplateQueryKeys`, kiểu `CardTemplateWithNoteCount`. `ApiError` (`@/shared/api/client`) có `code`, `message`.

## 2. Mục tiêu

1. Hiện cho template đang chọn: nhãn "Mặc định" (nếu `is_default`) và "N note".
2. Nút "Đổi tên" mở dialog đổi tên.
3. Nút "Xóa" với xác nhận; vô hiệu khi template là mặc định hoặc là template duy nhất.
4. Thông báo lỗi tiếng Việt theo mã lỗi cho mọi thao tác template của trang.
5. Tạo template mới chỉ gửi `{ name }` (bỏ `{{Word}}` cứng).

## 3. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/features/note-types/components/TemplateManagementBar.tsx` | Tạo mới: thanh thông tin + nút Đổi tên/Xóa + 2 dialog. |
| `frontend/src/features/note-types/components/TemplateManagementBar.test.tsx` | Tạo mới. |
| `frontend/src/features/note-types/lib/templateErrors.ts` | Tạo mới: `templateErrorMessage`. |
| `frontend/src/features/note-types/lib/templateErrors.test.ts` | Tạo mới. |
| `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx` | Thêm query `note_count`, render `TemplateManagementBar`, đổi body tạo mới, dùng `templateErrorMessage` trong 3 `onError` có sẵn. |
| `frontend/src/features/note-types/pages/__snapshots__/NoteTypeDetailPage.editor.test.tsx.snap` | Chỉ cập nhật nếu Claude đồng ý (xem §6). |

CẤM: `entities/**` (gồm `TemplateCodeEditor.tsx`), `NoteTypeLivePreview.tsx`, `components/ui/**`, `shared/ui/**`, backend.

## 4. Hợp đồng chính xác

### 4.1 `lib/templateErrors.ts`

```ts
import { ApiError } from '@/shared/api/client'

export function templateErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'SHARED_SCHEMA_VERSIONING_REQUIRED') {
      return 'Template này đang dùng trong bộ thẻ đã chia sẻ nên chưa thể thêm, xóa hoặc đặt lại. Bạn vẫn có thể sửa nội dung HTML/CSS.'
    }
    if (error.code === 'TEMPLATE_COMPILE_ERROR') {
      return `Template có lỗi cú pháp: ${error.message}`
    }
    if (error.message === 'Cannot delete default template.') {
      return 'Không thể xóa template mặc định.'
    }
    if (error.message === 'A note type requires at least one template.') {
      return 'Loại thẻ cần ít nhất một template.'
    }
    return error.message
  }
  if (error instanceof Error && error.message) return error.message
  return 'Đã có lỗi xảy ra. Vui lòng thử lại.'
}
```

### 4.2 `components/TemplateManagementBar.tsx`

```ts
export type TemplateManagementBarProps = {
  noteTypeId: string
  template: { id: string; name: string; is_default: boolean } | null
  noteCount: number | null        // null = đang tải hoặc lỗi
  templateCount: number           // tổng số template của NoteType
  onRenamed: () => void           // trang invalidate query
  onDeleted: (deletedTemplateId: string) => void  // trang chọn template khác + invalidate
}
```

Render (khi `template === null` trả `null`):

```tsx
<div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
  {template.is_default ? <Badge variant="secondary">Mặc định</Badge> : null}
  <Badge variant="outline">{noteCount === null ? '… note' : `${noteCount} note`}</Badge>
  <div className="ml-auto flex items-center gap-1.5">
    <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs font-semibold rounded-lg gap-1.5" onClick={openRename}>
      <Pencil className="size-3.5" aria-hidden="true" /> Đổi tên
    </Button>
    <Button size="sm" variant="ghost" className="h-7 px-2.5 text-xs font-semibold text-destructive hover:bg-destructive/10 rounded-lg gap-1.5"
      onClick={openDelete} disabled={deleteDisabled} title={deleteDisabledReason ?? undefined}>
      <Trash2 className="size-3.5" aria-hidden="true" /> Xóa
    </Button>
  </div>
</div>
```

- Icon `Pencil`, `Trash2` từ `lucide-react`. `Badge` từ `@/components/ui/badge`, `Button` từ `@/components/ui/button`.
- `deleteDisabled = template.is_default || templateCount <= 1`. `deleteDisabledReason`: `'Không thể xóa template mặc định.'` hoặc `'Loại thẻ cần ít nhất một template.'` (ưu tiên lý do mặc định).
- Dialog đổi tên: dùng `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` (`@/components/ui/dialog`), `Input`, `Label`. Tiêu đề `Đổi tên template`. Label `Tên template`. Input khởi tạo bằng tên hiện tại. Nút `Hủy` (variant outline) và `Lưu tên`. Validate: `value.trim()` rỗng → hiện dưới input `Tên template không được để trống.` và không gọi API; dài hơn 255 ký tự → `Tên template tối đa 255 ký tự.`; bằng tên cũ → đóng dialog không gọi API. Hợp lệ → `renameNoteTypeTemplate(noteTypeId, template.id, value.trim())`; thành công → `toast.success('Đã đổi tên template.')`, đóng dialog, `onRenamed()`; lỗi → `toast.error('Không thể đổi tên template', { description: templateErrorMessage(error) })`, giữ dialog mở. Nút `Lưu tên` disabled khi đang gửi.
- Dialog xóa: `ConfirmDialog` từ `@/shared/ui`, `variant="destructive"`, `title={\`Xóa template “${template.name}”?\`}`, `description="Thẻ của template này sẽ bị xóa. Tiến độ học của từng note vẫn được giữ."`, `confirmText="Xóa template"`, `isLoading` khi đang gửi. Body (`children`): `<p className="text-sm text-muted-foreground">{noteCount ?? 0} note đang có thẻ dùng template này.</p>`. Xác nhận → `deleteNoteTypeTemplate`; thành công → `toast.success('Đã xóa template.')`, đóng, `onDeleted(template.id)`; lỗi → `toast.error('Không thể xóa template', { description: templateErrorMessage(error) })`.
- Dùng `useMutation` của `@tanstack/react-query`; component không tự invalidate query.

### 4.3 Sửa `NoteTypeDetailPage.tsx`

1. Thêm query:

```ts
const templatesWithCountsQuery = useQuery({
  queryKey: cardTemplateQueryKeys.noteTypeTemplates(noteTypeId ?? ''),
  queryFn: ({ signal }) => fetchNoteTypeTemplates(noteTypeId as string, signal),
  enabled: Boolean(noteTypeId),
})
const selectedNoteCount =
  templatesWithCountsQuery.data?.items.find((item) => item.id === selectedTemplate?.id)?.note_count ?? null
```

2. Hàm `invalidateTemplates` gọi `queryClient.invalidateQueries` cho `['note-type-detail', noteTypeId]` **và** `cardTemplateQueryKeys.noteTypeTemplates(noteTypeId ?? '')`. Dùng nó trong `onSuccess` của save/create/reset (thay các lời gọi invalidate cũ chỉ khi đó là lời gọi duy nhất; giữ nguyên toast và setState khác).
3. `createTemplateMutation` body đổi thành `{ name: \`Card ${templates.length + 1}\` }`.
4. Trong 3 `onError` có sẵn, đổi `description: error.message` thành `description: templateErrorMessage(error)`; giữ nguyên tiêu đề toast.
5. Thêm `is_default?: boolean` vào type `TemplateItem` cục bộ của trang (không đổi field khác). Không thêm prop cho `TemplateCodeEditor`. Render `TemplateManagementBar` ngay **trên** `<TemplateCodeEditor />`, bên trong `<div className="lg:col-span-6 flex flex-col">`:

```tsx
<TemplateManagementBar
  noteTypeId={noteTypeId ?? ''}
  template={
    selectedTemplate
      ? { id: selectedTemplate.id, name: selectedTemplate.name, is_default: Boolean(selectedTemplate.is_default) }
      : null
  }
  noteCount={selectedNoteCount}
  templateCount={templates.length}
  onRenamed={invalidateTemplates}
  onDeleted={(deletedId) => {
    // Chọn ngay template còn lại; không để selectedTemplateId trỏ template đã xóa.
    setSelectedTemplateId(templates.find((item) => item.id !== deletedId)?.id ?? null)
    invalidateTemplates()
  }}
/>
```

## 5. Test bắt buộc

`TemplateManagementBar.test.tsx` (jsdom, `createRoot` + `act`, `QueryClientProvider`; `vi.mock('@/entities/card-template', ...)` cho `renameNoteTypeTemplate`, `deleteNoteTypeTemplate`; `vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))`):

| Test | Kỳ vọng |
|---|---|
| hiện nhãn | `is_default=true`, `noteCount=12` → có "Mặc định" và "12 note"; `noteCount=null` → "… note" |
| xóa bị khóa khi mặc định | nút "Xóa" `disabled`, `title="Không thể xóa template mặc định."` |
| xóa bị khóa khi chỉ 1 template | `is_default=false`, `templateCount=1` → disabled, title "Loại thẻ cần ít nhất một template." |
| đổi tên rỗng | nhập "   " → hiện "Tên template không được để trống.", API không được gọi |
| đổi tên trùng tên cũ | dialog đóng, API không được gọi |
| đổi tên thành công | gọi `renameNoteTypeTemplate('nt-1','t-2','Nghe')`, `toast.success('Đã đổi tên template.')`, `onRenamed` gọi 1 lần |
| đổi tên lỗi | mock reject `new ApiError('x', 409, 'SHARED_SCHEMA_VERSIONING_REQUIRED')` → `toast.error` với description đúng chuỗi §4.1; dialog vẫn mở |
| xóa thành công | xác nhận → `deleteNoteTypeTemplate('nt-1','t-2')`, `onDeleted` gọi đúng 1 lần với `'t-2'` |

`templateErrors.test.ts`: mỗi nhánh của §4.1 một case (5 nhánh `ApiError` + `Error` thường + giá trị không phải Error).

## 6. Kiểm tra

```powershell
npm --prefix frontend run test -- src/features/note-types
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

Snapshot `NoteTypeDetailPage.editor.test.tsx` chụp Card của editor; `TemplateManagementBar` nằm **ngoài** Card nên snapshot phải giữ nguyên. Nếu test đó fail, **không** chạy `-u`: báo cáo diff snapshot để Claude quyết định.

## 7. Ghi chú review cho Claude

- Kiểm tra mobile 375px: thanh mới không tràn ngang; dark mode đọc được.
- Xóa template trên NoteType có note thật: kiểm tra số note trước/sau và tiến độ NOTE giữ nguyên (bằng test backend có sẵn của `delete_template`).
- Đảm bảo `noteTypeId` rỗng không gọi API.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-06. Đọc và làm đúng theo docs/task/template-features/GT-06_TEMPLATE_MANAGEMENT_UI.md (§1–§6).
Đọc thêm: frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx,
frontend/src/entities/card-template/ui/TemplateCodeEditor.tsx (chỉ đọc),
frontend/src/entities/card-template/index.ts, frontend/src/shared/ui/ConfirmDialog.tsx,
frontend/src/components/ui/dialog.tsx, frontend/src/shared/api/client.ts (ApiError).
Chuỗi tiếng Việt dùng NGUYÊN VĂN trong spec. Chỉ sửa/tạo file ở §3. Báo cáo theo README §3. Không commit.
```
