# GT-04 — Entity frontend `card-template` (types, API, query keys) cho Contract B/C

- Owner: Gemini. Reviewer: Claude. Milestone: M1. Phụ thuộc: CT-00 (có thể chạy trước khi GT-02/GT-03 merge vì test mock API).
- Loại: TypeScript thuần, tạo slice mới, không sửa file cũ.

## 1. Bối cảnh

Migration FSD đang dùng tầng `entities/` (đã có `frontend/src/entities/flashcard/`). Entity **không được** import từ `@/app/*` hoặc `@/features/*`. Gọi HTTP bằng `apiRequest`/`apiJson` trong `@/shared/api/client` (chữ ký thật):

```ts
export async function apiRequest<T>(url: string, init: ApiRequestInit = {}): Promise<T>
export async function apiJson<T>(url: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown, init?: RequestInit)
```

URL truyền vào bắt đầu bằng `/api/...` (xem `frontend/src/features/worksheets/api.ts`). Lỗi HTTP được ném dưới dạng `ApiError` (`@/shared/api/client`) có `status`, `code`, `field`, `details`.

TypeScript bật `verbatimModuleSyntax` và `erasableSyntaxOnly`: import kiểu phải dùng `import type`, không dùng `enum`/`namespace`.

## 2. Mục tiêu

Tạo slice `frontend/src/entities/card-template/` chứa kiểu dữ liệu và hàm API cho Contract B và C (kế hoạch §5.1, §5.2). Các task sau (GT-06, GT-07, GT-10, GT-11, GT-12) sẽ mở rộng slice này.

## 3. File được tạo (không sửa file nào khác)

```text
frontend/src/entities/card-template/model/types.ts
frontend/src/entities/card-template/api/cardTemplateApi.ts
frontend/src/entities/card-template/api/queryKeys.ts
frontend/src/entities/card-template/api/cardTemplateApi.test.ts
frontend/src/entities/card-template/index.ts
```

## 4. Nội dung chính xác

### 4.1 `model/types.ts`

```ts
export type CardTemplateItem = {
  id: string
  note_type_id: string
  name: string
  front_html: string
  back_html: string
  shared_css: string
  position: number
  is_default: boolean
  updated_at: string | null
}

export type CardTemplateWithNoteCount = CardTemplateItem & { note_count: number }

export type NoteTypeTemplatesResponse = { items: CardTemplateWithNoteCount[] }

export type CardTypeContextKind = 'owned' | 'installed_source' | 'installed_local'

export type DeckCardType = {
  composition_id: string
  note_type_id: string
  note_type_name?: string
  template_id: string
  template_name: string
  is_default: boolean
  context_kind?: CardTypeContextKind
  install_id?: string | null
}

export type DeckCardTypeGroup = {
  note_type_id: string
  note_type_name: string
  compositions: DeckCardType[]
}

export type DeckCardTypesResponse = {
  schema_version: 'study-scope-compositions.v2'
  scope_type: 'deck'
  scope_id: string
  cardinality: 'zero' | 'one' | 'many'
  default_composition_id: string | null
  groups: DeckCardTypeGroup[]
  compositions: DeckCardType[]
  note_counts: Record<string, number>
}
```

Không thêm field nào ngoài danh sách trên.

### 4.2 `api/queryKeys.ts`

```ts
export const cardTemplateQueryKeys = {
  noteTypeTemplates: (noteTypeId: string) => ['card-template', 'note-type-templates', noteTypeId] as const,
  deckCardTypes: (deckId: number | string) => ['card-template', 'deck-card-types', String(deckId)] as const,
}
```

### 4.3 `api/cardTemplateApi.ts`

```ts
import { apiJson, apiRequest } from '@/shared/api/client'
import type { CardTemplateItem, DeckCardTypesResponse, NoteTypeTemplatesResponse } from '../model/types'

const enc = encodeURIComponent

export function fetchNoteTypeTemplates(noteTypeId: string, signal?: AbortSignal) {
  return apiRequest<NoteTypeTemplatesResponse>(`/api/note-types/${enc(noteTypeId)}/templates`, { signal })
}

export function fetchDeckCardTypes(deckId: number | string, signal?: AbortSignal) {
  return apiRequest<DeckCardTypesResponse>(
    `/api/study/scopes/deck/${enc(String(deckId))}/compositions?include_counts=1`,
    { signal },
  )
}

export function createNoteTypeTemplate(noteTypeId: string, body: { name?: string; front_html?: string; back_html?: string; shared_css?: string }) {
  return apiJson<CardTemplateItem>(`/api/note-types/${enc(noteTypeId)}/templates`, 'POST', body)
}

export function renameNoteTypeTemplate(noteTypeId: string, templateId: string, name: string) {
  return apiJson<CardTemplateItem>(`/api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}`, 'PATCH', { name })
}

export function deleteNoteTypeTemplate(noteTypeId: string, templateId: string) {
  return apiJson<{ success: boolean }>(`/api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}`, 'DELETE')
}
```

Giữ đúng tên hàm, URL, method, body. `renameNoteTypeTemplate` **chỉ** gửi `{ name }` (backend coi payload chỉ có `name` là thay đổi nội dung được phép cho template đã release, xem `ALLOWED_TEMPLATE_HOTFIX_FIELDS`).

### 4.4 `index.ts`

```ts
export type {
  CardTemplateItem,
  CardTemplateWithNoteCount,
  NoteTypeTemplatesResponse,
  CardTypeContextKind,
  DeckCardType,
  DeckCardTypeGroup,
  DeckCardTypesResponse,
} from './model/types'
export {
  fetchNoteTypeTemplates,
  fetchDeckCardTypes,
  createNoteTypeTemplate,
  renameNoteTypeTemplate,
  deleteNoteTypeTemplate,
} from './api/cardTemplateApi'
export { cardTemplateQueryKeys } from './api/queryKeys'
```

Không dùng `export *`.

## 5. Test bắt buộc (`api/cardTemplateApi.test.ts`)

Mock theo mẫu `frontend/src/features/deck-collaboration/api.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
const { apiRequest, apiJson } = vi.hoisted(() => ({ apiRequest: vi.fn(), apiJson: vi.fn() }))
vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson }))
import { ... } from '../index'
```

| Test | Kỳ vọng |
|---|---|
| fetchNoteTypeTemplates | gọi `apiRequest('/api/note-types/nt%2F1/templates', { signal: undefined })` với id `nt/1`; trả đúng object mock |
| fetchDeckCardTypes | gọi `apiRequest('/api/study/scopes/deck/42/compositions?include_counts=1', { signal: undefined })` với `42` (number) |
| createNoteTypeTemplate | `apiJson('/api/note-types/nt1/templates', 'POST', { name: 'Card 2' })` |
| renameNoteTypeTemplate | `apiJson('/api/note-types/nt1/templates/t1', 'PATCH', { name: 'Mới' })` và body không có key khác |
| deleteNoteTypeTemplate | `apiJson('/api/note-types/nt1/templates/t1', 'DELETE')` (đúng 2 tham số) |
| queryKeys | `deckCardTypes(42)` bằng `['card-template','deck-card-types','42']`; `noteTypeTemplates('a')` bằng `['card-template','note-type-templates','a']` |

## 6. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template
npm --prefix frontend run typecheck
npm --prefix frontend run lint
git diff --check
git status --short
```

`git status --short` chỉ có 5 file mới ở §3.

## 7. Ghi chú review cho Claude

- Không import `@/app/api` hoặc `@/features/*` trong entity.
- Kiểm tra lại URL so với route thật sau khi GT-02/GT-03 merge.

## 8. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-04. Đọc và làm đúng theo docs/task/template-features/GT-04_CARD_TEMPLATE_ENTITY.md
(§1–§6). Đọc thêm: frontend/src/shared/api/client.ts (chỉ đọc), frontend/src/features/worksheets/api.ts,
frontend/src/features/deck-collaboration/api.test.ts (mẫu mock), frontend/src/entities/flashcard/index.ts (mẫu export).
Chỉ tạo đúng 5 file ở §3 với nội dung ở §4. Chạy lệnh ở §6, báo cáo theo mẫu README §3. Không commit.
```
