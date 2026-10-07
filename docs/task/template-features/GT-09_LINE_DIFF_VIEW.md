# GT-09 — TypeScript: `diffLines` và component `TemplateDiffView`

- Owner: Gemini. Reviewer: Claude. Milestone: M2 (chạy song song từ đợt 1). Phụ thuộc: GT-05 `Accepted` (slice `entities/card-template` đã có; chạy sau GT-05 vì cùng sửa `index.ts`).
- Loại: hàm thuần + component trình bày, không gọi API.
- Người dùng: GT-10 (so sánh phiên bản), GT-11 (so bản riêng với bản gốc), GT-12.

## 1. Bối cảnh

Không có thư viện diff trong `frontend/package.json` và **không được thêm**. Cần so sánh theo dòng cho 3 phần của template: Front HTML, Back HTML, Shared CSS. TypeScript bật `verbatimModuleSyntax`, `erasableSyntaxOnly`, `noUnusedLocals`.

## 2. File được tạo/sửa

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/lib/lineDiff.ts` | Tạo mới. |
| `frontend/src/entities/card-template/lib/lineDiff.test.ts` | Tạo mới. |
| `frontend/src/entities/card-template/ui/TemplateDiffView.tsx` | Tạo mới. |
| `frontend/src/entities/card-template/ui/TemplateDiffView.test.tsx` | Tạo mới. |
| `frontend/src/entities/card-template/index.ts` | Chỉ thêm các dòng export ở §3.3. |

CẤM mọi file khác.

## 3. Hợp đồng chính xác

### 3.1 `lib/lineDiff.ts`

```ts
export type DiffLineKind = 'same' | 'added' | 'removed'
export type DiffLine = { kind: DiffLineKind; text: string; oldLine: number | null; newLine: number | null }

export function diffLines(oldText: string, newText: string, maxCells = 4_000_000): DiffLine[]
export function summarizeDiff(lines: DiffLine[]): { added: number; removed: number }
```

Thuật toán `diffLines` (bắt buộc đúng như sau để kết quả xác định):

1. Chuẩn hóa `\r\n` → `\n` ở cả hai chuỗi, rồi `split('\n')`. Chuỗi rỗng `''` là **0 dòng** (không phải 1 dòng rỗng).
2. `n`, `m` là số dòng. Nếu `n * m > maxCells`: trả toàn bộ dòng cũ dạng `removed` (theo thứ tự) rồi toàn bộ dòng mới dạng `added`.
3. Bảng LCS cho hậu tố: `L[i][j]` với `i` từ `n-1` về `0`, `j` từ `m-1` về `0`; `L[i][j] = a[i] === b[j] ? L[i+1][j+1] + 1 : max(L[i+1][j], L[i][j+1])`; hàng/cột `n`/`m` bằng 0. Dùng `Uint32Array` cho mỗi hàng.
4. Duyệt từ `i = 0, j = 0`: nếu `a[i] === b[j]` → `same` (`oldLine = i+1`, `newLine = j+1`), tăng cả hai; ngược lại nếu `L[i+1][j] >= L[i][j+1]` → `removed` (`oldLine = i+1`, `newLine = null`), tăng `i`; ngược lại → `added` (`oldLine = null`, `newLine = j+1`), tăng `j`. Hết vòng: dòng cũ còn lại → `removed`, rồi dòng mới còn lại → `added`.

`summarizeDiff` đếm số dòng `added` và `removed`.

### 3.2 `ui/TemplateDiffView.tsx`

```ts
export type TemplateSources = { front_html: string; back_html: string; shared_css: string }
export type TemplateDiffViewProps = {
  before: TemplateSources
  after: TemplateSources
  beforeLabel: string   // ví dụ 'Phiên bản 3'
  afterLabel: string    // ví dụ 'Hiện tại'
}
```

Render:

```tsx
<div className="space-y-4">
  <p className="text-xs text-muted-foreground">So sánh {beforeLabel} → {afterLabel}</p>
  {SECTIONS.map(({ key, label }) => <DiffSection key={key} label={label} lines={diffLines(before[key], after[key])} />)}
</div>
```

với `SECTIONS = [{ key: 'front_html', label: 'Front HTML' }, { key: 'back_html', label: 'Back HTML' }, { key: 'shared_css', label: 'Shared CSS' }] as const`.

`DiffSection` (cùng file, không export):

```tsx
<section className="rounded-xl border border-border/80 overflow-hidden">
  <header className="flex items-center justify-between bg-muted/40 px-3 py-1.5 text-xs font-semibold">
    <span>{label}</span>
    <span className="font-mono text-muted-foreground">+{added} −{removed}</span>
  </header>
  {added === 0 && removed === 0
    ? <p className="px-3 py-2 text-xs text-muted-foreground">Không có thay đổi</p>
    : <pre className="max-h-80 overflow-auto text-xs leading-5 font-mono">{lines.map(renderLine)}</pre>}
</section>
```

Mỗi dòng: `<div key={index} data-kind={line.kind} className={CLASS[line.kind]}><span className="inline-block w-4 select-none">{MARK[line.kind]}</span>{line.text}</div>` với

```ts
const MARK = { same: ' ', added: '+', removed: '-' }
const CLASS = {
  same: 'px-3 text-muted-foreground',
  added: 'px-3 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  removed: 'px-3 bg-rose-500/10 text-rose-700 dark:text-rose-300',
}
```

`text` render dưới dạng chữ (JSX text node), **không** dùng `dangerouslySetInnerHTML` (nội dung là HTML của template, phải hiện nguyên mã).

### 3.3 Thêm vào `index.ts`

```ts
export { diffLines, summarizeDiff } from './lib/lineDiff'
export type { DiffLine, DiffLineKind } from './lib/lineDiff'
export { TemplateDiffView } from './ui/TemplateDiffView'
export type { TemplateDiffViewProps, TemplateSources } from './ui/TemplateDiffView'
```

## 4. Test bắt buộc

### 4.1 `lineDiff.test.ts`

Ký hiệu kỳ vọng `kind[0]:text:oldLine:newLine`, `-` là `null`. Mọi kỳ vọng đã được Claude chạy kiểm chứng.

| `diffLines(old, new[, maxCells])` | Kỳ vọng |
|---|---|
| `('a\nb\nc', 'a\nb\nc')` | `s:a:1:1 \| s:b:2:2 \| s:c:3:3` |
| `('a\nb\nc', 'a\nx\nc')` | `s:a:1:1 \| r:b:2:- \| a:x:-:2 \| s:c:3:3` |
| `('', 'x\ny')` | `a:x:-:1 \| a:y:-:2` |
| `('x\ny', '')` | `r:x:1:- \| r:y:2:-` |
| `('', '')` | `[]` |
| `('a\r\nb', 'a\nb')` | `s:a:1:1 \| s:b:2:2` |
| `('a\nb', 'a\nb\n')` | `s:a:1:1 \| s:b:2:2 \| a::-:3` |
| `('a\nb\nc\nd', 'b\nc\ne')` | `r:a:1:- \| s:b:2:1 \| s:c:3:2 \| r:d:4:- \| a:e:-:3` |
| `('a\nb', 'c\nd', 3)` | `r:a:1:- \| r:b:2:- \| a:c:-:1 \| a:d:-:2` (vượt `maxCells`) |

`summarizeDiff` của case `('a\nb\nc\nd', 'b\nc\ne')` = `{ added: 1, removed: 2 }`.

### 4.2 `TemplateDiffView.test.tsx` (jsdom, `createRoot` + `act`)

| Test | Kỳ vọng |
|---|---|
| nhãn | có text `So sánh Phiên bản 1 → Hiện tại` |
| không đổi | before = after → 3 lần "Không có thay đổi", không có `pre` |
| front đổi | before.front `'{{Word}}'`, after.front `'{{Kanji}}'` → section Front HTML có `+1 −1`; có phần tử `[data-kind="removed"]` chứa text `{{Word}}` và `[data-kind="added"]` chứa `{{Kanji}}` |
| không chèn HTML | after.front `'<b>x</b>'` → không có phần tử `<b>` trong DOM; text `<b>x</b>` hiển thị nguyên văn |

## 5. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template
npm --prefix frontend run typecheck
npm --prefix frontend run lint
git diff --check
git status --short
```

## 6. Ghi chú review cho Claude

- Kiểm tra hiệu năng với template 2.000 dòng mỗi bên (4.000.000 ô, ~16 MB `Uint32Array`) chấp nhận được; nếu không, hạ `maxCells` mặc định.

## 7. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-09. Đọc và làm đúng theo docs/task/template-features/GT-09_LINE_DIFF_VIEW.md (§1–§5).
Thuật toán diff phải đúng từng bước ở §3.1; kỳ vọng ở §4.1 dùng nguyên văn, nếu lệch thì sửa cài đặt.
Không thêm thư viện. Đọc thêm: frontend/src/entities/card-template/index.ts, frontend/src/entities/flashcard/ui/CardDisplay.test.tsx (mẫu test jsdom).
Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
