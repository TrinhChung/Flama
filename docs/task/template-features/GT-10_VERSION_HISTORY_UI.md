# GT-10 — UI lịch sử phiên bản template (xem, so sánh, khôi phục)

- Owner: Gemini. Reviewer: Codex (tiếp nhận Claude). Milestone: M2.
- Trạng thái 2026-10-08: **GT-10A/B Completed / verified**; xem [CT-R2](reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md). Nội dung dưới là tiêu chí triển khai, không phải hàng đợi còn thiếu.
- Loại: entity API + feature UI tái sử dụng + nối vào trang loại thẻ.

## 0. Nền backend đã sẵn sàng

- Contract A2 chạy ở `app/api/v1/flashcards/card_templates.py`; schema `template-versions.v2`. Xem [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md).
- Entity có `cardTemplateQueryKeys.noteTypeTemplates(noteTypeId)`; page có `invalidateTemplates()` và detail key `['note-type-detail', noteTypeId]`. GT-06 draft fix đã có test.
- Không gọi API definitions/forks của v1. GT-11/12 đã có contract v2 theo code; library/market editor dùng cùng history adapter.
- History thực có thêm origin `market_copy` và `update`. GT-12A mở rộng entity union; GT-10B dùng bảng nhãn `Record<string,string>` và fallback origin gốc cho giá trị chưa biết, không sửa thêm entity ngoài whitelist.
- Chia hai lượt, mỗi lượt tối đa 6 file; không chạy GT-10A và GT-10B cùng lúc.

## 1. Bối cảnh

Contract A2: `GET /api/card-templates/<tid>/versions`, `GET .../versions/<vid>`, `POST .../versions/<vid>/restore`. Lưu nội dung thay đổi tạo version mới; rename/no-op không tạo; khôi phục tạo version mới bằng nội dung cũ, không xóa gì.

Component này sẽ được dùng lại cho bản riêng của người cài (GT-11, Contract D) và thư viện (GT-12, Contract E), nên nhận một **adapter** thay vì gọi cứng URL.

Ranh giới FSD: chỉ **file page** (`*/pages/*.tsx`) được import `@/features/template-versions`, vì page là tầng ghép (các page này sẽ chuyển sang `src/pages/` trong gói FSD G09). Component/hook trong feature khác không được import nó.

## 2. File được sửa/tạo theo phase

**GT-10A — entity contract (5 file, Ready)**:

- `frontend/src/entities/card-template/model/types.ts`: thêm kiểu §3.1; thêm `current_version_id?: string | null` vào CardTemplateItem để giữ fixture cũ.
- `frontend/src/entities/card-template/api/cardTemplateApi.ts`: thêm 3 hàm §3.2.
- `frontend/src/entities/card-template/api/queryKeys.ts`: thêm 2 key §3.2.
- `frontend/src/entities/card-template/index.ts`: export API và kiểu mới.
- `frontend/src/entities/card-template/api/cardTemplateApi.test.ts`: kiểm tra URL encode, signal, POST body và response cho 3 hàm; không đổi assertion cũ.

**GT-10B — history sheet + page (6 file, sau GT-10A review)**:

- `frontend/src/features/template-versions/model/types.ts`: adapter §3.3.
- `frontend/src/features/template-versions/ui/TemplateVersionHistorySheet.tsx`: UI §3.4.
- `frontend/src/features/template-versions/ui/TemplateVersionHistorySheet.test.tsx`: unit tests §4 và integration draft/restore tại page; có thể copy fixture từ page draft test, không sửa file fixture nguồn.
- `frontend/src/features/template-versions/index.ts`: public export.
- `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx`: nối nút và sheet §3.5; giữ fix draft của CT-03.
- `frontend/src/features/note-types/pages/__snapshots__/NoteTypeDetailPage.editor.test.tsx.snap`: chỉ cập nhật đúng nút Lịch sử được yêu cầu, báo cáo diff; không đổi editor DOM/class còn lại.

Không sửa editor, management bar, backend hoặc file ngoài phase. Không dùng `-u` cả suite; chỉ snapshot test page cụ thể sau khi kiểm tra diff.

## 3. Hợp đồng chính xác

### 3.1 Kiểu (entity)

```ts
export type TemplateVersionOrigin = 'backfill' | 'create' | 'edit' | 'reset' | 'restore' | 'apply' | 'fork'
export type TemplateVersionSummary = {
  id: string
  template_id: string
  version_no: number
  content_hash: string
  change_note: string
  origin: TemplateVersionOrigin
  created_at: string
  created_by: { id: number; username: string } | null
  is_current: boolean
}
export type TemplateVersionDetail = TemplateVersionSummary & { front_html: string; back_html: string; shared_css: string; input_schema: unknown[] }
export type TemplateVersionList = {
  schema_version: 'template-versions.v2'
  template_id: string
  current_version_id: string | null
  items: TemplateVersionSummary[]
}
```

### 3.2 API + key (entity)

```ts
export function fetchTemplateVersions(templateId: string, signal?: AbortSignal)
  // apiRequest<TemplateVersionList>(`/api/card-templates/${enc(templateId)}/versions`, { signal })
export function fetchTemplateVersion(templateId: string, versionId: string, signal?: AbortSignal)
  // apiRequest<TemplateVersionDetail>(`.../versions/${enc(versionId)}`, { signal })
export function restoreTemplateVersion(templateId: string, versionId: string, changeNote?: string)
  // apiJson<CardTemplateItem>(`.../versions/${enc(versionId)}/restore`, 'POST', changeNote ? { change_note: changeNote } : {})

cardTemplateQueryKeys.templateVersions = (templateId: string) =>
  ['card-template', 'versions', templateId] as const
cardTemplateQueryKeys.templateVersion = (templateId: string, versionId: string) =>
  ['card-template', 'versions', templateId, versionId] as const
```

### 3.3 Adapter (`features/template-versions/model/types.ts`)

```ts
import type { CardTemplateItem, TemplateVersionDetail, TemplateVersionList } from '@/entities/card-template'

export type TemplateVersionSource = {
  listKey: readonly unknown[]
  detailKey: (versionId: string) => readonly unknown[]
  list: (signal?: AbortSignal) => Promise<TemplateVersionList>
  get: (versionId: string, signal?: AbortSignal) => Promise<TemplateVersionDetail>
  restore: (versionId: string) => Promise<CardTemplateItem>
}
```

### 3.4 `TemplateVersionHistorySheet`

```ts
export type TemplateVersionHistorySheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  source: TemplateVersionSource
  current: { front_html: string; back_html: string; shared_css: string }  // nội dung đang ở trình soạn
  onRestored: (template: CardTemplateItem) => void  // áp dụng nguồn trả về, rồi invalidate
}
```

- Khung: `Sheet` → `SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto"` → `SheetHeader` (`SheetTitle` = `Lịch sử phiên bản`, `SheetDescription` = `Mỗi lần lưu thay đổi nội dung tạo một phiên bản. Khôi phục sẽ tạo phiên bản mới, không xóa lịch sử.`).
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
| market_copy | Bản nhận marketplace |
| update | Cập nhật từ tác giả |

- Chọn version → `useQuery({ queryKey: source.detailKey(id), queryFn: ({ signal }) => source.get(id, signal) })`; hiện `TemplateDiffView` (entity, GT-09) với `before` = version, `after` = `current`, `beforeLabel` = `Phiên bản {n}`, `afterLabel` = `Trình soạn hiện tại`.
- Nút `Khôi phục phiên bản này` (ẩn khi `is_current`) → `ConfirmDialog` (`@/shared/ui`) `title="Khôi phục phiên bản {n}?"`, `description="Nội dung chưa lưu trong trình soạn sẽ được thay bằng phiên bản này. Lịch sử cũ vẫn được giữ."`, `confirmText="Khôi phục"`. Xác nhận → `source.restore(id)` → `toast.success('Đã khôi phục phiên bản {n}.')`, `onRestored(restoredTemplate)`, invalidate `source.listKey`; lỗi → `toast.error('Không thể khôi phục', { description: error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.' })`. Không import `templateErrorMessage` từ `features/note-types` (feature không import feature khác).
- Trạng thái tải/lỗi/rỗng: `Đang tải lịch sử…`, message lỗi, `Chưa có phiên bản nào.`

### 3.5 Nối vào `NoteTypeDetailPage.tsx`

- State `const [historyOpen, setHistoryOpen] = useState(false)`.
- Nút trong `headerActions`, ngay sau nút Reset: `<Button size="sm" variant="outline" className="h-8 sm:h-9 px-2.5 text-xs font-semibold rounded-xl shrink-0 gap-1.5" onClick={() => setHistoryOpen(true)} disabled={!selectedTemplateId}><FontAwesomeIcon icon={faClockRotateLeft} className="text-xs" /> Lịch sử</Button>` (thêm `faClockRotateLeft` vào import `@fortawesome/free-solid-svg-icons`).
- Source dựng bằng `useMemo` từ `selectedTemplateId` với các hàm entity §3.2. Chỉ mount sheet khi có template được chọn; key component theo template ID để không giữ selection của template trước.
- `onRestored(restoredTemplate)` phải gán trực tiếp `frontHtml/backHtml/sharedCss` từ response khi response.id vẫn là template đang chọn, cập nhật cache detail/list tương ứng rồi gọi `invalidateTemplates()`. Chỉ invalidate không đủ: GT-06 giữ draft khi nguồn server không đổi, nên restore bản có nguồn giống server cũng phải thay draft. Chặn đổi template khi restore pending hoặc bỏ qua response đã cũ; không ghi vào draft của template khác.
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

GT-10B được cập nhật snapshot page cho đúng nút "Lịch sử" trong whitelist; báo cáo diff. Snapshot của TemplateCodeEditor và class/DOM cũ phải giữ nguyên. Thêm test restore thay draft ngay cả khi response sources giống server, restore lỗi giữ draft và đổi template không áp response cũ. Detail query chỉ enabled khi sheet mở và đã chọn version; loading/error rõ ràng, không so sánh bằng dữ liệu cũ của selection trước.

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
- Restore khi có draft: response phải thay draft ngay, kể cả nguồn version khôi phục giống nguồn đang cache; lỗi giữ draft. Đổi template/đóng sheet phải không hiển thị dữ liệu cũ.

## 7. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-10<PHASE A hoặc B>. Chỉ làm đúng file của phase đã giao, dừng sau báo cáo. Đọc và làm đúng theo docs/task/template-features/GT-10_VERSION_HISTORY_UI.md (§1–§5; bỏ qua §0 và §6).
Đọc thêm: frontend/src/entities/card-template/** , frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx,
frontend/src/components/ui/sheet.tsx, frontend/src/shared/ui/ConfirmDialog.tsx.
Chuỗi tiếng Việt NGUYÊN VĂN. Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
