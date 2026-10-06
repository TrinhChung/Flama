# GT-05 — Tách `TemplateCodeEditor` khỏi `NoteTypeDetailPage` (không đổi giao diện)

- Owner: Gemini. Reviewer: Claude. Milestone: M1. Phụ thuộc: GT-04 `Accepted` (slice `entities/card-template` đã có). Không chạy khi gói FSD G09 (note-types) đang `In progress`.
- Loại: refactor UI thuần, **Zero Visual Regression**. Bằng chứng bắt buộc: DOM snapshot trước = sau.

## 1. Bối cảnh

`frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx` (443 dòng, commit `faa3c7d`) chứa toàn bộ trình soạn template trong cột trái:

- Dòng 72: `const activeTextareaRef = useRef<HTMLTextAreaElement | null>(null)`.
- Dòng 197-222: hàm `insertPlaceholder(fieldName)` chèn `{{fieldName}}` tại con trỏ của textarea đang active; tab CSS thì nối `/* {{fieldName}} */` vào cuối.
- Dòng 277-419: `{/* Left Column: Template Editor */}` → `<div className="lg:col-span-6 flex flex-col">` → `<Card className="p-4 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl bg-card">` gồm: header (h3 "Trình Soạn Thảo Template" + khối `NativeSelect`/nút "Mới"/nút "Reset"), thanh chèn placeholder, `Tabs` 3 textarea (Front HTML / Back HTML / Shared CSS), footer có nút "Lưu Template".

Trang thư viện mẫu (GT-12) và trang bản riêng của người cài (GT-11) cần dùng lại đúng trình soạn này.

## 2. Mục tiêu

Chuyển phần `<Card>...</Card>` của cột trái thành component trình bày `TemplateCodeEditor` đặt ở tầng entity (`entities/card-template/ui/`) để các trang khác dùng lại mà không import chéo feature. Trang cũ render component đó với cùng dữ liệu. HTML render ra phải **giống hệt từng ký tự**.

## 3. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/ui/TemplateCodeEditor.tsx` | Tạo mới. Chỉ import từ `react`, `@/components/ui/*`. |
| `frontend/src/entities/card-template/ui/TemplateCodeEditor.test.tsx` | Tạo mới. |
| `frontend/src/entities/card-template/index.ts` | Chỉ thêm `export { TemplateCodeEditor } from './ui/TemplateCodeEditor'` và `export type { TemplateCodeEditorProps, TemplateEditorTab } from './ui/TemplateCodeEditor'`. |
| `frontend/src/features/note-types/pages/NoteTypeDetailPage.editor.test.tsx` | Tạo mới (test đặc tả DOM trước/sau). |
| `frontend/src/features/note-types/pages/__snapshots__/NoteTypeDetailPage.editor.test.tsx.snap` | Do Vitest sinh ra ở bước 1. |
| `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx` | Thay khối `<Card>` cột trái bằng `<TemplateCodeEditor .../>`; xóa `activeTextareaRef`, `insertPlaceholder` và import không còn dùng. Không đổi logic khác. |

CẤM: `NoteTypeLivePreview.tsx`, mọi file `components/ui/*`, `entities/flashcard/**`, file khác. Trang import component qua `@/entities/card-template`.

## 4. Thứ tự làm việc BẮT BUỘC

1. **Trước khi sửa source**, tạo `NoteTypeDetailPage.editor.test.tsx` (§5.1) và chạy `npm --prefix frontend run test -- src/features/note-types/pages/NoteTypeDetailPage.editor.test.tsx`. Vitest tạo file `.snap`. Ghi lại output vào báo cáo.
2. Tạo `TemplateCodeEditor.tsx` (§4.1), sửa `NoteTypeDetailPage.tsx` (§4.2).
3. Chạy lại test bước 1 **không** dùng `-u`. Test phải PASS với snapshot cũ. Nếu FAIL: sửa component cho tới khi DOM khớp; **cấm** cập nhật snapshot.
4. Tạo `TemplateCodeEditor.test.tsx` (§5.2) và chạy toàn bộ lệnh §6.

### 4.1 `entities/card-template/ui/TemplateCodeEditor.tsx`

```tsx
import { useRef, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export type TemplateEditorTab = 'front' | 'back' | 'css'

export type TemplateCodeEditorProps = {
  title?: string                         // mặc định 'Trình Soạn Thảo Template'
  headerActions?: ReactNode              // nội dung đặt trong div actions của header
  fields: Array<{ id: string; name: string }>
  activeTab: TemplateEditorTab
  onActiveTabChange: (tab: TemplateEditorTab) => void
  frontHtml: string
  backHtml: string
  sharedCss: string
  onFrontHtmlChange: (value: string) => void
  onBackHtmlChange: (value: string) => void
  onSharedCssChange: (value: string) => void
  footer?: ReactNode                     // nội dung đặt trong div footer
  readOnly?: boolean                     // mặc định false; true => textarea readOnly, ẩn nút placeholder
}
```

Yêu cầu:

- JSX bên trong là **bản chép nguyên văn** của dòng 279-418 hiện tại (Card, header, toolbar placeholder, Tabs, footer) với các thay thế: chuỗi tiêu đề → `{title}`; nội dung bên trong `<div className="flex items-center gap-1.5 sm:gap-2 w-full sm:w-auto overflow-x-auto pb-0.5">` → `{headerActions}`; nội dung bên trong `<div className="pt-3 flex justify-start border-t mt-3">` → `{footer}`; state → props.
- `activeTextareaRef` và `insertPlaceholder` chuyển vào component. Khi chèn ở tab front/back có textarea: `onXChange(value.slice(0, start) + placeholder + value.slice(end))` với `start = textarea.selectionStart || 0`, `end = textarea.selectionEnd || 0`; không có textarea: `onXChange(value + placeholder)`. Tab css: `onSharedCssChange(sharedCss + '/* ' + placeholder + ' */')` (chính xác như code cũ: `` `/* ${placeholder} */` ``).
- `readOnly === true`: thêm thuộc tính `readOnly` cho 3 textarea và không render các nút placeholder (giữ nguyên div bao ngoài và dòng "Chèn trường dữ liệu"). Với `readOnly` mặc định (false) DOM phải giống hệt cũ, **không** render thuộc tính `readonly`.
- Không thêm `data-*`, `aria-*`, class hay wrapper mới.

### 4.2 Sửa `NoteTypeDetailPage.tsx`

Thay khối `<Card ...> ... </Card>` (dòng 279-418) bằng:

```tsx
<TemplateCodeEditor
  headerActions={<>{/* NativeSelect + nút Mới + nút Reset: chép nguyên văn từ dòng cũ */}</>}
  fields={fields}
  activeTab={activeTab}
  onActiveTabChange={setActiveTab}
  frontHtml={frontHtml}
  backHtml={backHtml}
  sharedCss={sharedCss}
  onFrontHtmlChange={setFrontHtml}
  onBackHtmlChange={setBackHtml}
  onSharedCssChange={setSharedCss}
  footer={/* nút Lưu Template: chép nguyên văn từ dòng cũ */}
/>
```

`<div className="lg:col-span-6 flex flex-col">` bao ngoài giữ nguyên trong trang. Import bằng `import { TemplateCodeEditor } from '@/entities/card-template'`. Xóa import `Card`, `Tabs*` khỏi trang nếu không còn dùng. Không đổi query/mutation/preview/useEffect.

## 5. Test bắt buộc

### 5.1 `NoteTypeDetailPage.editor.test.tsx` (đặc tả DOM)

```tsx
// @vitest-environment jsdom
```

- Dùng `createRoot` + `act` như `frontend/src/features/dashboard/components/DeckModals.test.tsx`; bọc `QueryClientProvider` (`new QueryClient({ defaultOptions: { queries: { retry: false } } })`) và `MemoryRouter initialEntries={['/note-types/nt-1']}` + `Routes`/`Route path="/note-types/:id"`.
- `vi.mock('@/app/api', ...)`: `appApi.get` trả `{ id: 'nt-1', name: 'Từ vựng', publish_status: 'private', field_defs: [{ id: 'f1', name: 'Kanji', field_type: 'text', position: 0 }, { id: 'f2', name: 'Meaning', field_type: 'text', position: 1 }], templates: [{ id: 't1', name: 'Card 1', front_html: '{{Kanji}}', back_html: '{{Meaning}}', shared_css: '.card{}' }] }`; `appApi.mutate` trả `{}`.
- `vi.mock('../components/NoteTypeLivePreview', () => ({ NoteTypeLivePreview: () => null }))` và `vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))`.
- Chờ dữ liệu (lặp `await act(async () => { await Promise.resolve() })` tối đa 10 lần đến khi thấy heading "Trình Soạn Thảo Template").
- Lấy `const card = heading.closest('[data-slot="card"]')`, `expect(card?.outerHTML).toMatchSnapshot()`.
- Bấm tab "Back HTML" rồi snapshot lần hai (`toMatchSnapshot('back-tab')`).

### 5.2 `entities/card-template/ui/TemplateCodeEditor.test.tsx`

| Test | Kỳ vọng |
|---|---|
| render tiêu đề mặc định | có text "Trình Soạn Thảo Template"; `title="X"` thì hiện "X" |
| slots | `headerActions` nằm trong div `.overflow-x-auto`; `footer` nằm trong div `.border-t` |
| gõ textarea front | `onFrontHtmlChange` được gọi với giá trị mới |
| chèn placeholder tại con trỏ | `frontHtml="ab"`, đặt `selectionStart=selectionEnd=1` trên textarea front, bấm nút `{{Kanji}}` → `onFrontHtmlChange('a{{Kanji}}b')` |
| chèn ở tab css | `activeTab='css'`, `sharedCss='.a{}'`, bấm `{{Kanji}}` → `onSharedCssChange('.a{}/* {{Kanji}} */')` |
| không có field | hiện "Chưa có trường nào" |
| readOnly | 3 textarea có thuộc tính `readonly`; không có nút `{{Kanji}}` |
| mặc định không readonly | không textarea nào có thuộc tính `readonly` |

Ghi chú jsdom: Radix Tabs chỉ render `TabsContent` đang active; để test tab css, truyền `activeTab='css'`.

## 6. Kiểm tra

```powershell
npm --prefix frontend run test -- src/features/note-types src/entities/card-template
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

Báo cáo phải có: output bước 1 (tạo snapshot), output bước 3 (pass không `-u`), và `git diff --stat`.

## 7. Ghi chú review cho Claude

- Chạy `NoteTypeDetailPage.editor.test.tsx` trên base commit (chỉ thêm file test + snap) để xác nhận snapshot sinh từ code cũ.
- So sánh từng class trong diff; chặn wrapper mới.
- Kiểm tra trực quan nhanh trang `/note-types/:id` desktop/mobile bằng profile Chrome riêng.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-05. Đọc và làm đúng theo docs/task/template-features/GT-05_EXTRACT_TEMPLATE_CODE_EDITOR.md
(§1–§6), đặc biệt THỨ TỰ ở §4: viết test snapshot và chạy TRƯỚC khi sửa source; sau refactor
chạy lại KHÔNG dùng -u. Đọc thêm: frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx,
frontend/src/features/dashboard/components/DeckModals.test.tsx (mẫu test), frontend/src/components/ui/tabs.tsx.
Chỉ sửa/tạo các file ở §3. Báo cáo theo mẫu README §3. Không commit.
```
