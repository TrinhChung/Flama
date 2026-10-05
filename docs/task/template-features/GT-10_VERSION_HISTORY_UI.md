# GT-10 — UI lịch sử phiên bản template (xem, so sánh, khôi phục)

- Owner: Gemini. Reviewer: Claude. Milestone: M2.
- Trạng thái: **Blocked** đến khi CT-03 (Contract A chạy thật) và GT-06, GT-09 `Accepted`.
- Loại: entity API + feature UI tái sử dụng + nối vào trang loại thẻ.

## 0. Việc Claude làm trước khi mở task

- [ ] So Contract A thật (route, key JSON, mã lỗi) với kế hoạch §5.3; sửa §3 của file này nếu khác.
- [ ] Ghi tên query key và các file đã tồn tại sau GT-06 (đường dẫn, số dòng chèn nút).
- [ ] Đổi trạng thái README thành `Ready`.

## 1. Bối cảnh

Contract A (kế hoạch §5.3): `GET .../templates/<tid>/versions`, `GET .../versions/<vid>`, `POST .../versions/<vid>/restore`. Mỗi lần lưu template tạo version mới; khôi phục tạo version mới bằng nội dung cũ, không xóa gì.

Component này sẽ được dùng lại cho bản riêng của người cài (GT-11, Contract D) và thư viện (GT-12, Contract E), nên nhận một **adapter** thay vì gọi cứng URL.

Ranh giới FSD: chỉ **file page** (`*/pages/*.tsx`) được import `@/features/template-versions`, vì page là tầng ghép (các page này sẽ chuyển sang `src/pages/` trong gói FSD G09). Component/hook trong feature khác không được import nó.

## 2. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/model/types.ts` | Thêm kiểu §3.1 (không sửa kiểu cũ). |
| `frontend/src/entities/card-template/api/cardTemplateApi.ts` | Thêm 3 hàm §3.2. |
| `frontend/src/entities/card-template/api/queryKeys.ts` | Thêm 2 key §3.2. |
| `frontend/src/entities/card-template/index.ts` | Thêm export tương ứng. |
| `frontend/src/entities/card-template/api/cardTemplateApi.test.ts` | Thêm test cho 3 hàm mới. |
| `frontend/src/features/template-versions/model/types.ts` | Tạo mới: `TemplateVersionSource`. |
| `frontend/src/features/template-versions/ui/TemplateVersionHistorySheet.tsx` | Tạo mới. |
| `frontend/src/features/template-versions/ui/TemplateVersionHistorySheet.test.tsx` | Tạo mới. |
| `frontend/src/features/template-versions/index.ts` | Tạo mới (export component + type). |
| `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx` | Thêm nút "Lịch sử" trong `headerActions` (sau nút Reset) và render sheet. |

CẤM: `entities/card-template/ui/TemplateCodeEditor.tsx`, `TemplateManagementBar.tsx`, backend, file khác.

## 3. Hợp đồng chính xác

### 3.1 Kiểu (entity)

```ts
export type TemplateVersionOrigin = 'backfill' | 'create' | 'edit' | 'reset' | 'restore' | 'apply' | 'fork'
export type TemplateVersionSummary = {
  id: string
  version_no: number
  content_hash: string
  change_note: string
  origin: TemplateVersionOrigin
  created_at: string
  created_by: { id: number; username: string } | null
  is_current: boolean
}
export type TemplateVersionDetail = TemplateVersionSummary & { front_html: string; back_html: string; shared_css: string }
export type TemplateVersionList = {
  schema_version: 'template-versions.v1'
  template_id: string
  definition_id: string
  current_version_id: string
  items: TemplateVersionSummary[]
}
```

### 3.2 API + key (entity)

```ts
export function fetchTemplateVersions(noteTypeId: string, templateId: string, signal?: AbortSignal)
  // apiRequest<TemplateVersionList>(`/api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}/versions`, { signal })
export function fetchTemplateVersion(noteTypeId: string, templateId: string, versionId: string, signal?: AbortSignal)
  // apiRequest<TemplateVersionDetail>(`.../versions/${enc(versionId)}`, { signal })
export function restoreTemplateVersion(noteTypeId: string, templateId: string, versionId: string, changeNote?: string)
  // apiJson<CardTemplateItem>(`.../versions/${enc(versionId)}/restore`, 'POST', changeNote ? { change_note: changeNote } : {})

cardTemplateQueryKeys.templateVersions = (noteTypeId: string, templateId: string) =>
  ['card-template', 'versions', 'note-type', noteTypeId, templateId] as const
cardTemplateQueryKeys.templateVersion = (noteTypeId: string, templateId: string, versionId: string) =>
  ['card-template', 'versions', 'note-type', noteTypeId, templateId, versionId] as const
```

### 3.3 Adapter (`features/template-versions/model/types.ts`)

```ts
import type { TemplateVersionDetail, TemplateVersionList } from '@/entities/card-template'

export type TemplateVersionSource = {
  listKey: readonly unknown[]
  detailKey: (versionId: string) => readonly unknown[]
  list: (signal?: AbortSignal) => Promise<TemplateVersionList>
  get: (versionId: string, signal?: AbortSignal) => Promise<TemplateVersionDetail>
  restore: (versionId: string) => Promise<unknown>
}
```

### 3.4 `TemplateVersionHistorySheet`

```ts
export type TemplateVersionHistorySheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  source: TemplateVersionSource
  current: { front_html: string; back_html: string; shared_css: string }  // nội dung đang ở trình soạn
  onRestored: () => void                                                   // trang invalidate query
}
```

- Khung: `Sheet` → `SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto"` → `SheetHeader` (`SheetTitle` = `Lịch sử phiên bản`, `SheetDescription` = `Mỗi lần lưu tạo một phiên bản. Khôi phục sẽ tạo phiên bản mới, không xóa lịch sử.`).
- Danh sách (`useQuery({ queryKey: source.listKey, queryFn: ({ signal }) => source.list(signal), enabled: open })`): mỗi item là `button` chọn version, hiện `Phiên bản {version_no}`, thời gian `new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(created_at))`, nhãn origin theo bảng, `change_note` nếu khác rỗng, badge `Hiện tại` nếu `is_current`, người tạo `created_by.username` nếu có.

| origin | Nhãn |
|---|---|
| backfill | Bản ghi ban đầu |
| create | Tạo mới |
| edit | Chỉnh sửa |
| reset | Đặt lại mặc định |
| restore | Khôi phục |
| apply | Áp dụng từ thư viện |
| fork | Tạo bản riêng |

- Chọn version → `useQuery({ queryKey: source.detailKey(id), queryFn: ({ signal }) => source.get(id, signal) })`; hiện `TemplateDiffView` (entity, GT-09) với `before` = version, `after` = `current`, `beforeLabel` = `Phiên bản {n}`, `afterLabel` = `Trình soạn hiện tại`.
- Nút `Khôi phục phiên bản này` (ẩn khi `is_current`) → `ConfirmDialog` (`@/shared/ui`) `title="Khôi phục phiên bản {n}?"`, `description="Nội dung chưa lưu trong trình soạn sẽ được thay bằng phiên bản này. Lịch sử cũ vẫn được giữ."`, `confirmText="Khôi phục"`. Xác nhận → `source.restore(id)` → `toast.success('Đã khôi phục phiên bản {n}.')`, `onRestored()`, invalidate `source.listKey`; lỗi → `toast.error('Không thể khôi phục', { description: error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.' })`. Không import `templateErrorMessage` từ `features/note-types` (feature không import feature khác).
- Trạng thái tải/lỗi/rỗng: `Đang tải lịch sử…`, message lỗi, `Chưa có phiên bản nào.`

### 3.5 Nối vào `NoteTypeDetailPage.tsx`

- State `const [historyOpen, setHistoryOpen] = useState(false)`.
- Nút trong `headerActions`, ngay sau nút Reset: `<Button size="sm" variant="outline" className="h-8 sm:h-9 px-2.5 text-xs font-semibold rounded-xl shrink-0 gap-1.5" onClick={() => setHistoryOpen(true)} disabled={!selectedTemplateId}><FontAwesomeIcon icon={faClockRotateLeft} className="text-xs" /> Lịch sử</Button>` (thêm `faClockRotateLeft` vào import `@fortawesome/free-solid-svg-icons`).
- Source dựng bằng `useMemo` từ `noteTypeId` + `selectedTemplateId` với các hàm entity §3.2.
- `onRestored` = `invalidateTemplates` (từ GT-06).
- Render `<TemplateVersionHistorySheet ... current={{ front_html: frontHtml, back_html: backHtml, shared_css: sharedCss }} />` cạnh `TemplateCodeEditor` (ngoài Card).

## 4. Test bắt buộc

`TemplateVersionHistorySheet.test.tsx` (jsdom; mock `source` bằng object `vi.fn()`; mock `sonner`):

| Test | Kỳ vọng |
|---|---|
| không gọi khi đóng | `open=false` → `source.list` không được gọi |
| danh sách | 3 version (3 current, 2, 1) → hiện "Phiên bản 3", badge "Hiện tại" ở v3, nhãn origin đúng bảng |
| chọn v1 | gọi `source.get('v1')`; hiện "So sánh Phiên bản 1 → Trình soạn hiện tại" |
| ẩn khôi phục ở bản hiện tại | chọn v3 → không có nút "Khôi phục phiên bản này" |
| khôi phục | chọn v2 → bấm → xác nhận → `source.restore('v2')` 1 lần, `onRestored` 1 lần, `toast.success('Đã khôi phục phiên bản 2.')` |
| lỗi khôi phục | reject `new Error('x')` → `toast.error('Không thể khôi phục', { description: 'x' })`, `onRestored` không gọi |
| rỗng | `items: []` → "Chưa có phiên bản nào." |

Snapshot `NoteTypeDetailPage.editor.test.tsx` phải giữ nguyên **trừ** khi nút "Lịch sử" làm đổi DOM header của Card: trường hợp này báo cáo diff snapshot, **không** chạy `-u`; Claude quyết định cập nhật.

## 5. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/template-versions src/features/note-types
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

## 6. Ghi chú review cho Claude

- Kiểm tra end-to-end với backend CT-03: lưu 2 lần → 3 version; khôi phục v1 → v4 có hash bằng v1.
- Restore khi trình soạn có thay đổi chưa lưu: sau `invalidateTemplates`, effect đồng bộ editor từ server phải ghi đè đúng như cảnh báo.

## 7. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-10. Đọc và làm đúng theo docs/task/template-features/GT-10_VERSION_HISTORY_UI.md (§1–§5; bỏ qua §0 và §6).
Đọc thêm: frontend/src/entities/card-template/** , frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx,
frontend/src/components/ui/sheet.tsx, frontend/src/shared/ui/ConfirmDialog.tsx.
Chuỗi tiếng Việt NGUYÊN VĂN. Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
