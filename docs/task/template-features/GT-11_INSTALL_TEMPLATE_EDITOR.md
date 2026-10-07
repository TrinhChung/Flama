# GT-11 — Trang sửa template cho deck đã cài (bản riêng copy-on-write)

- Owner: Gemini. Reviewer: Claude. Milestone: M3.
- Trạng thái: **Blocked** đến khi CT-05 (Contract D chạy thật) và GT-05, GT-07, GT-10 `Accepted`; người dùng đã trả lời Q1.
- Loại: trang mới + route + liên kết từ dialog "Kiểu thẻ".

## 0. Việc Claude làm trước khi mở task

- [ ] So Contract D thật với kế hoạch §5.4; sửa §3 nếu khác (đặc biệt `state`, `upstream_changed_since_fork`, `field_defs`, mã lỗi).
- [ ] Xác nhận API preview trả cùng shape với preview NoteType để dùng `NoteTypeLivePreview` không đổi.
- [ ] Cấp quyền sửa `frontend/src/App.tsx` cho đúng 2 thay đổi ở §3.5 (App.tsx thuộc vùng điều phối của kế hoạch FSD).
- [ ] Đổi trạng thái README thành `Ready`.

## 1. Bối cảnh

Người cài deck từ marketplace hiện không đổi được giao diện thẻ gốc: thẻ gốc luôn render bằng Template sống của tác giả (`app/services/study_artifact_service.py:118,147`). Sau CT-05, mỗi `(DeckInstall, Template nguồn)` có thể có một bản riêng: lần lưu đầu tạo fork; xóa fork thì quay về theo bản gốc. Phiên học đang mở không đổi; phiên mới dùng bản hiệu lực.

Dữ liệu đầu vào cho link: `DeckCardType` của dialog GT-07 có `context_kind === 'installed_source'`, `install_id`, `template_id` (= `source_template_id`).

## 2. File được sửa/tạo

| File | Được làm gì |
|---|---|
| `frontend/src/entities/card-template/model/types.ts` | Thêm `InstallTemplateItem`, `InstallTemplateDetail`, `InstallTemplatesResponse`, `TemplatePreviewResponse` theo §3.1. |
| `frontend/src/entities/card-template/api/cardTemplateApi.ts` + `queryKeys.ts` + `index.ts` + test | Thêm API §3.2. |
| `frontend/src/features/library/pages/InstallTemplatesPage.tsx` | Tạo mới. |
| `frontend/src/features/library/pages/InstallTemplatesPage.test.tsx` | Tạo mới. |
| `frontend/src/features/dashboard/components/DeckCardTypesDialog.tsx` (+ test) | Đổi nút disabled của `installed_source` thành link §3.4. |
| `frontend/src/App.tsx` | Chỉ thêm lazy import + 1 route §3.5. |

CẤM: `LibraryPages.tsx`, `NoteTypeDetailPage.tsx`, `TemplateCodeEditor.tsx` (chỉ import), `NoteTypeLivePreview.tsx` (chỉ import), backend, file khác.

## 3. Hợp đồng chính xác

### 3.1 Kiểu

Chép nguyên `InstallTemplateItem` và `InstallTemplateDetail` từ kế hoạch §5.4. Thêm:

```ts
export type InstallTemplatesResponse = { schema_version: 'install-templates.v1'; install_id: string; local_deck_id: number | null; items: InstallTemplateItem[] }
export type TemplatePreviewResponse = { front_html?: string; back_html?: string; front_renderer_payload?: unknown; back_renderer_payload?: unknown }
```

### 3.2 API (base `/api/marketplace/installations/${enc(installId)}/templates`)

| Hàm | Gọi |
|---|---|
| `fetchInstallTemplates(installId, signal?)` | `apiRequest<InstallTemplatesResponse>(base, { signal })` |
| `fetchInstallTemplate(installId, sourceTemplateId, signal?)` | `apiRequest<InstallTemplateDetail>(\`${base}/${enc(sid)}\`, { signal })` |
| `saveInstallTemplateFork(installId, sid, body: { front_html: string; back_html: string; shared_css: string; change_note?: string })` | `apiJson<InstallTemplateDetail>(\`${base}/${enc(sid)}/fork\`, 'PUT', body)` |
| `deleteInstallTemplateFork(installId, sid)` | `apiJson<InstallTemplateDetail>(\`${base}/${enc(sid)}/fork\`, 'DELETE')` |
| `previewInstallTemplate(installId, sid, body: { front_html; back_html; shared_css })` | `apiJson<TemplatePreviewResponse>(\`${base}/${enc(sid)}/preview\`, 'POST', body)` |
| `fetchInstallTemplateVersions(installId, sid, signal?)` | `apiRequest<TemplateVersionList>(\`${base}/${enc(sid)}/versions\`, { signal })` |
| `fetchInstallTemplateVersion(installId, sid, vid, signal?)` | `apiRequest<TemplateVersionDetail>(\`${base}/${enc(sid)}/versions/${enc(vid)}\`, { signal })` |
| `restoreInstallTemplateVersion(installId, sid, vid)` | `apiJson<InstallTemplateDetail>(\`${base}/${enc(sid)}/versions/${enc(vid)}/restore\`, 'POST', {})` |

Query keys: `installTemplates(installId)` = `['card-template','install',installId]`; `installTemplate(installId, sid)` = `['card-template','install',installId,sid]`; `installTemplateVersions(installId, sid)` = `['card-template','versions','install',installId,sid]`; `installTemplateVersion(installId, sid, vid)` = `[...installTemplateVersions(installId, sid), vid]`.

### 3.3 Trang `InstallTemplatesPage`

- Route param `installId`; query string `template` chọn `source_template_id` ban đầu (không có → item đầu tiên).
- Bố cục: giống `NoteTypeDetailPage` (`Page` + `PageHeader` + lưới `grid gap-5 lg:grid-cols-12`), cột trái `lg:col-span-6`: danh sách kiểu thẻ + `TemplateCodeEditor`; cột phải `lg:col-span-6`: `NoteTypeLivePreview` (props như trang loại thẻ; `scope="install_template_preview"`, `scopeId={installId}`, `fieldDefs={detail.field_defs}`).
- `PageHeader`: `title="Giao diện thẻ của deck đã cài"`, `description="Tùy chỉnh template cho riêng bạn. Deck của tác giả không thay đổi."`, action: nút `Quay lại` → `/installed-decks`.
- Danh sách kiểu thẻ: `NativeSelect` trong `headerActions` của `TemplateCodeEditor` (giống trang loại thẻ), mỗi option `{name}{state === 'forked' ? ' (bản riêng)' : ''}`.
- Khối trạng thái (ngay trên `TemplateCodeEditor`, ngoài Card):
  - `following`: `Alert` mặc định với `AlertDescription`: `Bạn đang dùng template gốc của tác giả. Khi lưu, Flama tạo bản riêng chỉ áp dụng cho deck này.`
  - `forked`: `Badge variant="secondary"` `Bản riêng` + nút `So với bản gốc` (mở Dialog chứa `TemplateDiffView before=detail.upstream after=nội dung trình soạn beforeLabel="Bản gốc" afterLabel="Bản của bạn"`) + nút `Lịch sử` (mở `TemplateVersionHistorySheet` với source dựng từ API §3.2) + nút destructive `Dùng lại bản gốc`.
  - `forked` và `upstream_changed_since_fork`: thêm `Alert` (variant mặc định, icon `AlertCircle`): `Tác giả đã cập nhật template gốc sau khi bạn tạo bản riêng.` với nút `Xem khác biệt` (mở dialog so sánh như trên).
- `Dùng lại bản gốc` → `ConfirmDialog variant="destructive"` `title="Bỏ bản riêng và dùng template gốc?"` `description="Phiên học mới sẽ dùng template của tác giả. Lịch sử bản riêng vẫn được giữ."` `confirmText="Dùng bản gốc"` → `deleteInstallTemplateFork` → `toast.success('Đã chuyển về template gốc.')`.
- Footer của editor: nút `Lưu bản riêng` (`following`) hoặc `Lưu` (`forked`) → `saveInstallTemplateFork` → `toast.success(state === 'following' ? 'Đã tạo bản riêng.' : 'Đã lưu bản riêng.')`.
- Preview: debounce 500 ms như `NoteTypeDetailPage` (sao chép logic `useEffect` + `setTimeout` + cờ `cancelled`) gọi `previewInstallTemplate`.
- Đồng bộ trình soạn từ `detail.front_html/back_html/shared_css` khi đổi template hoặc sau khi lưu/khôi phục/xóa fork (giống effect của trang loại thẻ).
- Mọi mutation thành công invalidate `installTemplates(installId)`, `installTemplate(installId, sid)` và `installTemplateVersions(installId, sid)`. Thêm invalidate `['card-template','deck-card-types']` (prefix) để dialog GT-07 cập nhật.
- Lỗi: `toast.error(<tiêu đề>, { description: error instanceof Error ? error.message : 'Đã có lỗi xảy ra. Vui lòng thử lại.' })`. Lỗi tải trang: `PageError`. Đang tải: `PageLoading label="Đang tải template của deck…"`.

### 3.4 Dialog GT-07

Thay nút disabled của `installed_source` bằng:

```tsx
<Button asChild size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg">
  <Link to={`/installed-decks/${encodeURIComponent(item.install_id ?? '')}/templates?template=${encodeURIComponent(item.template_id)}`}>Sửa giao diện</Link>
</Button>
```

Nếu `install_id` rỗng/null: giữ nút disabled cũ. Cập nhật test GT-07 tương ứng (chỉ test của case này).

### 3.5 `App.tsx`

Thêm lazy import cạnh `InstalledDecksPage`:

```tsx
const InstallTemplatesPage = lazy(() =>
  import('./features/library/pages/InstallTemplatesPage').then((module) => ({
    default: module.InstallTemplatesPage,
  })),
)
```

và route ngay sau `{ path: 'installed-decks', element: deferred(<InstalledDecksPage />) }`:

```tsx
          {
            path: 'installed-decks/:installId/templates',
            element: deferred(<InstallTemplatesPage />),
          },
```

## 4. Test bắt buộc (`InstallTemplatesPage.test.tsx`)

Mock entity API; `MemoryRouter initialEntries={['/installed-decks/i1/templates?template=t2']}` + `Route path="/installed-decks/:installId/templates"`; mock `NoteTypeLivePreview` và `AmbientBackground` thành `() => null`.

| Test | Kỳ vọng |
|---|---|
| chọn theo query | `template=t2` → gọi `fetchInstallTemplate('i1','t2')` |
| following | hiện chuỗi following; nút "Lưu bản riêng" |
| lưu tạo fork | sửa front → bấm "Lưu bản riêng" → `saveInstallTemplateFork('i1','t2',{front_html, back_html, shared_css})`; `toast.success('Đã tạo bản riêng.')` |
| forked | detail `state:'forked'` → badge "Bản riêng", nút "Lưu", "So với bản gốc", "Lịch sử", "Dùng lại bản gốc" |
| upstream đổi | `upstream_changed_since_fork: true` → chuỗi cảnh báo và nút "Xem khác biệt" |
| bỏ fork | xác nhận → `deleteInstallTemplateFork('i1','t2')`; `toast.success('Đã chuyển về template gốc.')` |
| lỗi lưu | reject `new Error('Bad')` → `toast.error` có description `'Bad'` |

## 5. Kiểm tra

```powershell
npm --prefix frontend run test -- src/entities/card-template src/features/library src/features/dashboard
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build:ci
git diff --check
git status --short
```

## 6. Ghi chú review cho Claude

- Smoke thật với profile Chrome riêng: tài khoản A xuất bản deck, B cài → B tạo bản riêng → học phiên mới thấy giao diện mới; A và C không đổi; phiên B đang mở trước khi lưu vẫn giữ giao diện cũ.
- Kiểm tra trên mobile: editor + preview xếp dọc như trang loại thẻ.

## 7. Prompt cho Gemini

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-11. Đọc và làm đúng theo docs/task/template-features/GT-11_INSTALL_TEMPLATE_EDITOR.md (§1–§5; bỏ qua §0 và §6).
Đọc thêm: frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx (mẫu bố cục, preview, đồng bộ editor),
frontend/src/entities/card-template/ui/TemplateCodeEditor.tsx (import qua @/entities/card-template),
frontend/src/features/note-types/components/NoteTypeLivePreview.tsx (chỉ import; ngoại lệ ghép ở tầng page),
frontend/src/features/template-versions/index.ts, frontend/src/entities/card-template/index.ts,
frontend/src/features/dashboard/components/DeckCardTypesDialog.tsx, frontend/src/App.tsx (chỉ 2 chỗ ở §3.5).
Chuỗi tiếng Việt NGUYÊN VĂN. Chỉ sửa/tạo file ở §2. Báo cáo theo README §3. Không commit.
```
