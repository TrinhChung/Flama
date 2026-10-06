# GT-12 — Trang thư viện "Mẫu thẻ" (danh sách + chi tiết/sửa)

- Owner: Gemini. Reviewer: Claude. Milestone: M4.
- Trạng thái: **Blocked** đến khi CT-06 (Contract E chạy thật), GT-05, GT-10 `Accepted`, người dùng đã trả lời Q2.
- Loại: 2 trang mới, route, menu sidebar.

## 0. Việc Claude làm trước khi mở task

- [ ] So Contract E thật với kế hoạch §5.5; sửa §3 nếu khác (đặc biệt `group`, `input_schema`, `applications`, mã lỗi).
- [ ] Cấp quyền sửa `App.tsx`, `components/app-sidebar.tsx`, `layouts/AppLayout.tsx` cho đúng các dòng ở §3.4 (file thuộc vùng shell của kế hoạch FSD).
- [ ] Đổi trạng thái README thành `Ready`.

## 1. Bối cảnh

Sau CT-06, mỗi template là một `TemplateDefinition` có nhiều phiên bản. Định nghĩa có thể được áp dụng vào nhiều loại thẻ (mỗi lần áp dụng tạo một template của loại thẻ đó, pin vào một phiên bản). Mẫu độc lập là định nghĩa chưa áp dụng ở đâu.

## 2. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/model/types.ts`, `api/cardTemplateApi.ts`, `api/queryKeys.ts`, `index.ts`, test API | Thêm kiểu + API §3.1–§3.2. |
| `frontend/src/features/template-library/pages/TemplateLibraryPage.tsx` (+ `.test.tsx`) | Tạo mới: danh sách. |
| `frontend/src/features/template-library/pages/TemplateDefinitionPage.tsx` (+ `.test.tsx`) | Tạo mới: chi tiết/sửa. |
| `frontend/src/features/template-library/components/CreateTemplateDialog.tsx` (+ test) | Tạo mới. |
| `frontend/src/App.tsx`, `frontend/src/components/app-sidebar.tsx`, `frontend/src/layouts/AppLayout.tsx` | Chỉ các dòng ở §3.4. |

CẤM: file khác, backend.

## 3. Hợp đồng chính xác

### 3.1 Kiểu

Chép nguyên `InputSpec`, `LibraryItem`, `LibraryDetail` từ kế hoạch §5.5, đổi tên với tiền tố: `TemplateInputSpec`, `TemplateLibraryItem`, `TemplateLibraryDetail`.

### 3.2 API (base `/api/card-templates`)

| Hàm | Gọi |
|---|---|
| `fetchTemplateLibrary(params: { q?: string; group?: 'all' \| 'in_use' \| 'standalone' }, signal?)` | `apiRequest<{ items: TemplateLibraryItem[] }>` với query string chỉ chứa tham số khác rỗng; `group` mặc định không gửi |
| `fetchTemplateDefinition(id, signal?)` | `GET /api/card-templates/${enc(id)}` |
| `createTemplateDefinition(body: { name: string; description?: string; category?: string; front_html: string; back_html: string; shared_css?: string })` | `POST` base |
| `updateTemplateDefinitionMeta(id, body: { name?: string; description?: string; category?: string })` | `PATCH /${enc(id)}` |
| `saveTemplateDefinitionContent(id, body: { front_html: string; back_html: string; shared_css: string; change_note?: string })` | `PUT /${enc(id)}/content` |
| `previewTemplateDefinition(id, body: { front_html: string; back_html: string; shared_css: string; sample_values?: Record<string, string> })` | `POST /${enc(id)}/preview` → `TemplatePreviewResponse` |
| `archiveTemplateDefinition(id)` | `POST /${enc(id)}/archive` với body `{}` |
| `syncAppliedTemplate(noteTypeId, templateId)` | `POST /api/note-types/${enc(noteTypeId)}/templates/${enc(templateId)}/sync-definition` với body `{}` |
| `fetchDefinitionVersions(id, signal?)`, `fetchDefinitionVersion(id, vid, signal?)`, `restoreDefinitionVersion(id, vid)` | như Contract A dưới `/${enc(id)}/versions` |

Query keys: `library(params)` = `['card-template','library', params.q ?? '', params.group ?? 'all']`; `definition(id)` = `['card-template','definition',id]`; `definitionVersions(id)` = `['card-template','versions','definition',id]`; `definitionVersion(id, vid)` = `[...definitionVersions(id), vid]`.

### 3.3 Trang

**`TemplateLibraryPage`** (route `/card-templates`):

- `PageHeader title="Mẫu thẻ" description="Thư viện template dùng lại cho nhiều loại thẻ."`, action nút `Tạo mẫu mới` mở `CreateTemplateDialog`.
- Thanh lọc: `SearchInput` từ `@/shared/ui` (debounce 300 ms) + `FilterPillGroup` từ `@/shared/ui` với 3 lựa chọn `Tất cả` (`all`), `Đang dùng` (`in_use`), `Mẫu độc lập` (`standalone`). Đọc props thật của 2 component này trước khi dùng; nếu không khớp mô tả, dừng và báo cáo.
- Lưới thẻ (`grid gap-3 sm:grid-cols-2 lg:grid-cols-3`), mỗi thẻ là `Link` tới `/card-templates/:id` gồm: tên, mô tả (2 dòng, `line-clamp-2`), badge `Phiên bản {version_no}`, badge `Dùng ở {applied_count} loại thẻ` hoặc `Chưa dùng` khi `applied_count === 0`, danh sách `input_keys` dạng `{{key}}` (tối đa 4, phần còn lại `+N`).
- Rỗng: `Chưa có mẫu thẻ nào.`; lỗi: `PageError`; đang tải: `PageLoading label="Đang tải mẫu thẻ…"`.

**`CreateTemplateDialog`**: trường `Tên mẫu` (bắt buộc, ≤255), `Mô tả` (tùy chọn). Tạo với `front_html: '{{Front}}'`, `back_html: '{{Front}}<hr>{{Back}}'`, `shared_css: ''`. Thành công → điều hướng `/card-templates/{id}`, `toast.success('Đã tạo mẫu thẻ.')`.

**`TemplateDefinitionPage`** (route `/card-templates/:id`):

- Bố cục như `NoteTypeDetailPage`: cột trái `TemplateCodeEditor` (từ `@/entities/card-template`) với `fields` = `current_version.input_schema.map((s) => ({ id: s.key, name: s.key }))`; cột phải `NoteTypeLivePreview` (ngoại lệ ghép ở tầng page) với payload từ `previewTemplateDefinition` (debounce 500 ms), `fieldDefs` dựng từ `input_schema` (`{ id: key, name: key, field_type: type, position: index }`).
- `PageHeader`: `title` = tên mẫu; nút `Quay lại` → `/card-templates`; nút `Lịch sử` mở `TemplateVersionHistorySheet` (source từ API version của định nghĩa); nút `Lưu trữ` (ConfirmDialog `title="Lưu trữ mẫu thẻ này?"` `description="Mẫu sẽ ẩn khỏi thư viện. Các loại thẻ đang dùng không bị ảnh hưởng."`).
- Footer editor: nút `Lưu phiên bản mới` → `saveTemplateDefinitionContent` → `toast.success('Đã lưu phiên bản mới.')`.
- Khối "Đang dùng ở" (dưới editor): bảng `applications` gồm loại thẻ (link `/note-types/:note_type_id`), tên template, trạng thái `Mới nhất` hoặc `Có phiên bản mới` (`is_outdated`), nút `Cập nhật` (chỉ khi `is_outdated`) → `syncAppliedTemplate` → `toast.success('Đã cập nhật template của loại thẻ.')`. Nút `Áp dụng vào loại thẻ` để trống `onClick` mở wizard **của GT-13**: trong GT-12 render nút với `disabled` và `title="Sắp có"`.
- Sửa metadata: nút `Đổi tên` mở dialog giống GT-06 (tên ≤255, không rỗng) gọi `updateTemplateDefinitionMeta`.

### 3.4 Shell

- `App.tsx`: 2 lazy import theo mẫu `NoteTypeDetailPage` và 2 route ngay sau route `note-types/:id/fields`: `{ path: 'card-templates', element: deferred(<TemplateLibraryPage />) }`, `{ path: 'card-templates/:id', element: deferred(<TemplateDefinitionPage />) }`.
- `components/app-sidebar.tsx`: trong mảng `library`, ngay sau `{ title: 'Loại thẻ', ... }` thêm `{ title: 'Mẫu thẻ', url: '/card-templates', icon: Layers },` và thêm `Layers` vào import `lucide-react` có sẵn của file.
- `layouts/AppLayout.tsx`: trong `pageTitles`, ngay sau `'/note-types': 'Loại thẻ',` thêm `'/card-templates': 'Mẫu thẻ',`.

## 4. Test bắt buộc

| File | Test |
|---|---|
| `TemplateLibraryPage.test.tsx` | gọi `fetchTemplateLibrary({})` lần đầu; chọn "Mẫu độc lập" → gọi với `group: 'standalone'`; hiện "Chưa dùng" khi `applied_count = 0`; `input_keys` 6 phần tử → hiện 4 + "+2"; rỗng → "Chưa có mẫu thẻ nào." |
| `CreateTemplateDialog.test.tsx` | tên rỗng không gọi API; tạo thành công gọi đúng body mặc định và điều hướng `/card-templates/d1` |
| `TemplateDefinitionPage.test.tsx` | placeholder là input keys; lưu gọi `saveTemplateDefinitionContent('d1', {...})`; ứng dụng `is_outdated` có nút "Cập nhật" gọi `syncAppliedTemplate('nt1','t1')`; nút "Áp dụng vào loại thẻ" disabled |
| test API entity | URL/method/body của từng hàm §3.2 (kiểu test GT-04) |

## 5. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/template-library
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

## 6. Ghi chú review cho Claude

- Q2: nếu người dùng chọn "chỉ mẫu chủ động lưu", bỏ bộ lọc `in_use` trước khi giao.
- Kiểm tra sidebar mobile và breadcrumb/tiêu đề trang.

## 7. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-12. Đọc và làm đúng theo docs/task/template-features/GT-12_TEMPLATE_LIBRARY_PAGES.md (§1–§5; bỏ qua §0 và §6).
Đọc thêm: frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx (mẫu bố cục), frontend/src/entities/card-template/index.ts,
frontend/src/features/template-versions/index.ts, frontend/src/shared/ui/index.ts, SearchInput.tsx, FilterPillGroup.tsx,
frontend/src/App.tsx, frontend/src/components/app-sidebar.tsx, frontend/src/layouts/AppLayout.tsx (chỉ các dòng ở §3.4).
Chuỗi tiếng Việt NGUYÊN VĂN. Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
