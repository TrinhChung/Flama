# GT-07 — Dashboard: mục "Kiểu thẻ (template)" và dialog liệt kê kiểu thẻ của deck

- Owner: Gemini. Reviewer: Claude. Milestone: M1.
- Phụ thuộc: GT-03 (API `include_counts`) và GT-04 (entity) `Accepted`. Không chạy khi gói FSD G03 (dashboard) đang `In progress`.
- Loại: UI mới + nối vào menu deck có sẵn.

## 1. Bối cảnh

- Menu bánh răng của mỗi deck nằm trong `frontend/src/features/dashboard/components/DeckRow.tsx` (dòng ~216-287). Các mục gọi `onAction({ type, deck: node })`. Mục "Import thẻ" (dòng ~255-261) và "Xuất bài tập / Worksheet" (dòng ~263-269) là mẫu.
- `frontend/src/features/dashboard/types.ts:53`: `export type DeckAction = 'rename' | 'move' | 'reset' | 'delete' | 'worksheet'`.
- `DeckActionModal` trong `frontend/src/features/dashboard/components/DeckModals.tsx` (dòng ~220+) có nhánh sớm:

```tsx
  if (type === 'worksheet') {
    return (
      <LazyDeckWorksheetModal
        open
        onOpenChange={(open) => !open && onClose()}
        deckId={deck.id}
        deckName={deck.name}
      />
    )
  }
```

- Entity (GT-04): `fetchDeckCardTypes(deckId, signal)` → `DeckCardTypesResponse` (có `groups`, `compositions`, `note_counts`), `cardTemplateQueryKeys.deckCardTypes(deckId)`.
- Nhãn ngữ cảnh đang dùng trong `frontend/src/features/study/components/StudyModeSelector.tsx`: `installed_source` → "Thẻ gốc từ bộ đã cài", `installed_local` → "Thẻ riêng trong bộ đã cài", còn lại → "Thẻ trong bộ của bạn". Dùng lại **nguyên văn** (không import từ feature study).

## 2. Mục tiêu

Người dùng mở menu deck → "Kiểu thẻ (template)" → dialog liệt kê các kiểu thẻ (nhóm theo loại thẻ), số note mỗi kiểu, nhãn mặc định/ngữ cảnh, nút sửa giao diện và nút học.

## 3. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/features/dashboard/components/DeckCardTypesDialog.tsx` | Tạo mới. |
| `frontend/src/features/dashboard/components/DeckCardTypesDialog.test.tsx` | Tạo mới. |
| `frontend/src/features/dashboard/types.ts` | Chỉ thêm `'card-types'` vào union `DeckAction`. |
| `frontend/src/features/dashboard/components/DeckRow.tsx` | Thêm 1 `DropdownMenuItem` và import `Layers` từ `lucide-react` (gộp vào dòng `import { Printer } from 'lucide-react'`). |
| `frontend/src/features/dashboard/components/DeckModals.tsx` | Thêm 1 nhánh sớm `card-types` ngay sau nhánh `worksheet` + import component. |

CẤM: các file dashboard khác, `features/study/**`, `entities/**`, `components/ui/**`, backend.

## 4. Hợp đồng chính xác

### 4.1 `DeckCardTypesDialog.tsx`

```ts
export type DeckCardTypesDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId: number
  deckName: string
}
```

- Query: `useQuery({ queryKey: cardTemplateQueryKeys.deckCardTypes(deckId), queryFn: ({ signal }) => fetchDeckCardTypes(deckId, signal), enabled: open })`.
- Khung: `Dialog` (`open`, `onOpenChange`) → `DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg"` → `DialogHeader` gồm `DialogTitle` = `` `Kiểu thẻ của “${deckName}”` `` và `DialogDescription` = `Mỗi kiểu thẻ là một template hiển thị cùng dữ liệu note. Khi học, bạn chọn một kiểu cho cả phiên.`
- Trạng thái:
  - Đang tải: `<div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> Đang tải kiểu thẻ…</div>`.
  - Lỗi: `<Alert variant="destructive"><AlertCircle /><AlertDescription>{error.message}</AlertDescription></Alert>`.
  - Rỗng (`compositions.length === 0`): `<p className="py-6 text-sm text-muted-foreground">Deck này chưa có thẻ để học.</p>`.
- Danh sách: với mỗi `group` trong `data.groups` (giữ thứ tự server):

```tsx
<section key={group.note_type_id} className="space-y-2">
  <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
    <span className="flex size-7 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
      <Layers className="size-4" aria-hidden="true" />
    </span>
    <span>{group.note_type_name}</span>
  </div>
  <ul className="space-y-2">
    {group.compositions.map((item) => (
      <li key={item.composition_id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border/80 bg-background px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{item.template_name}</p>
          <p className="text-xs text-muted-foreground">{contextLabel(item.context_kind)}</p>
        </div>
        {item.is_default ? <Badge variant="secondary">Mặc định</Badge> : null}
        <Badge variant="outline">{`${data.note_counts[item.composition_id] ?? 0} note`}</Badge>
        {editAction(item)}
      </li>
    ))}
  </ul>
</section>
```

  Các section cách nhau bằng `<div className="space-y-5">` bao ngoài.
- `contextLabel(kind)`: `'installed_source'` → `Thẻ gốc từ bộ đã cài`; `'installed_local'` → `Thẻ riêng trong bộ đã cài`; còn lại → `Thẻ trong bộ của bạn`.
- `editAction(item)`:
  - `context_kind` là `undefined`, `'owned'` hoặc `'installed_local'`: `<Button asChild size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg"><Link to={\`/note-types/${encodeURIComponent(item.note_type_id)}\`}>Sửa giao diện</Link></Button>`.
  - `'installed_source'`: `<Button size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg" disabled title="Sắp có: tạo bản riêng cho thẻ gốc của bộ đã cài.">Sửa giao diện</Button>` (GT-11 sẽ đổi thành link).
- Footer: `DialogFooter` có `<Button variant="outline" onClick={() => onOpenChange(false)}>Đóng</Button>` và `<Button asChild><Link to={\`/study?deck_id=${deckId}\`}>Học deck này</Link></Button>` (chỉ render nút học khi `compositions.length > 0`).
- Import: `Link` từ `react-router-dom`; `AlertCircle`, `Layers`, `LoaderCircle` từ `lucide-react`; `Alert`, `AlertDescription` từ `@/components/ui/alert`; `Badge`; `Button`; Dialog parts từ `@/components/ui/dialog`; entity từ `@/entities/card-template`.

### 4.2 Nối vào menu

`DeckRow.tsx`: chèn **ngay sau** mục "Import thẻ" và **trước** mục "Xuất bài tập / Worksheet":

```tsx
                <DropdownMenuItem
                  className="cursor-pointer text-sm py-2 px-2.5 font-medium flex items-center gap-2"
                  onSelect={() => onAction({ type: 'card-types', deck: node })}
                >
                  <Layers className="size-4 text-orange-600" />
                  <span>Kiểu thẻ (template)</span>
                </DropdownMenuItem>
```

`DeckModals.tsx`: ngay sau nhánh `if (type === 'worksheet') { ... }` thêm:

```tsx
  if (type === 'card-types') {
    return (
      <DeckCardTypesDialog
        open
        onOpenChange={(open) => !open && onClose()}
        deckId={deck.id}
        deckName={deck.name}
      />
    )
  }
```

## 5. Test bắt buộc (`DeckCardTypesDialog.test.tsx`)

Mẫu harness: `frontend/src/features/dashboard/components/DeckModals.test.tsx` (`// @vitest-environment jsdom`, `createRoot`, `act`, `QueryClientProvider`). Thêm `MemoryRouter`. Mock `@/entities/card-template`: giữ `cardTemplateQueryKeys` thật bằng `vi.importActual`, chỉ mock `fetchDeckCardTypes`.

Fixture: 2 group: NoteType "Từ vựng" có `T1` (owned, default, 12 note) và `T2` (owned, 0 note — không có key trong `note_counts`); NoteType "Bộ cài" có `T3` (`installed_source`, `install_id: 'i1'`, 30 note) và `T4` (`installed_local`, 2 note).

| Test | Kỳ vọng |
|---|---|
| tải và hiện nhóm | thấy "Từ vựng", "Bộ cài", 4 dòng theo đúng thứ tự fixture |
| số note | "12 note", "0 note" (T2 thiếu key), "30 note", "2 note" |
| nhãn | T1 có "Mặc định"; T3 có "Thẻ gốc từ bộ đã cài"; T4 có "Thẻ riêng trong bộ đã cài"; T1 có "Thẻ trong bộ của bạn" |
| sửa giao diện | link của T1 có `href="/note-types/<nt_id>"`; nút của T3 `disabled` và có `title` đúng chuỗi |
| nút học | link "Học deck này" có `href="/study?deck_id=42"` |
| rỗng | `compositions: []` → "Deck này chưa có thẻ để học." và không có link học |
| lỗi | mock reject `new Error('Mất kết nối')` → thấy "Mất kết nối" |
| không gọi khi đóng | `open=false` → `fetchDeckCardTypes` không được gọi |

Thêm 1 test trong file mới (không sửa test cũ): render `DeckActionModal` với `selection={{ type: 'card-types', deck }}` → dialog có tiêu đề `Kiểu thẻ của “<tên deck>”`. Lấy `DashboardPayload`/`DeckNode` fixture theo mẫu `DeckModals.test.tsx`.

## 6. Kiểm tra

```powershell
npm --prefix frontend run test -- src/features/dashboard
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

## 7. Ghi chú review cho Claude

- Kiểm tra trên deck đã cài thật: `context_kind` và `install_id` có trong payload.
- Mobile 375px: dòng wrap, không tràn; dark mode.
- Không prefetch khi menu chưa mở.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-07. Đọc và làm đúng theo docs/task/template-features/GT-07_DECK_CARD_TYPES_DIALOG.md (§1–§6).
Đọc thêm: frontend/src/features/dashboard/components/DeckRow.tsx, DeckModals.tsx, DeckModals.test.tsx,
frontend/src/features/dashboard/types.ts, frontend/src/entities/card-template/index.ts,
frontend/src/features/study/components/StudyModeSelector.tsx (chỉ để xem nhãn, KHÔNG import).
Chuỗi tiếng Việt dùng NGUYÊN VĂN. Chỉ sửa/tạo file ở §3. Báo cáo theo README §3. Không commit.
```
