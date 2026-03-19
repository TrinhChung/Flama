# Markdown Field Editor Plan

## 0) Tinh trang trien khai (2026-03-05)

Da implement:

- Backend ho tro `field_type = markdown` (model enum, constants, validation, renderer, voice source text-only).
- Them endpoint `POST /api/notes/<note_id>/markdown-media` cho upload anh inline markdown (image-only, dedupe theo `sha256`, khong ghi de `field_values`).
- UI field manager bo sung option `markdown`.
- UI editor da render markdown bang `textarea` o:
  - `note_editor`
  - `note_edit`
  - `study edit modal`
  - `browse modal editor`
- Ho tro paste/drop image vao markdown o:
  - `note_edit`
  - `study edit modal`
  - `browse modal editor`
  Sau upload se chen syntax `![alt](/media/proxy/<asset_id>)`.
- Test da bo sung va pass:
  - renderer markdown
  - markdown inline upload endpoint

Gioi han hien tai:

- `note_editor` (tao note moi) da dung `textarea` cho markdown, nhung chua upload anh ngay luc paste vi note chua co `note_id` de luu asset.

## 1) Muc tieu

Bo sung `field_type = markdown` cho he thong flashcard theo cach:

- Tuong thich voi he thong hien tai (CRUD note type, note editor, browse, study edit, renderer).
- Ho tro thoi quen nguoi dung **dan anh truc tiep** vao editor markdown (paste/drop), khong bat buoc chen link thu cong.
- Giu an toan noi dung (sanitize), khong mo rong be mat XSS.

## 2) Hien trang sau khi dieu tra

### 2.1 Field type hien tai

He thong dang hard-code cac type:

- `text`
- `richtext`
- `image`
- `audio`
- `diagram`

Noi tap trung:

- `FIELD_TYPES` trong routes/services.
- Validation branch theo `field_type`.
- Renderer branch theo `field_type`.
- Dropdown chon type trong UI quan tri field.

### 2.2 Cac editor hien tai va khoang trong voi markdown

#### A. Note create page (`note_editor`)

- `richtext` dung `textarea`.
- Type khac (khong phai media) roi vao `input text`.
- Neu them `markdown` ma chua sua UI thi se thanh `input 1 dong` (sai UX).

#### B. Note edit page (`note_edit`)

- `richtext` dung `textarea`.
- Media co preview/upload rieng.
- Con lai dung `input text`.
- `markdown` se bi xem nhu text 1 dong neu khong bo sung nhanh.

#### C. Study edit modal (`vocabulary_study`)

- `richtext` dung `textarea`.
- Con lai dung `input text`.
- `markdown` cung se bi 1 dong.

#### D. Browse modal editor

- Non-media hien dang dung `textarea` nen khong bi vo UX nghiem trong.
- Tuy nhien chua co markdown toolbar/preview/paste image workflow.

### 2.3 Dan anh hien tai chua phu hop markdown

Endpoint upload media hien tai:

- Chi chap nhan field type media (`image/audio/diagram`).
- Sau upload se ghi de `note.field_values[field_name] = asset.id`.

Dieu nay khong phu hop markdown vi markdown can luu **chuoi noi dung** (co the chua nhieu hinh), khong phai 1 asset id duy nhat.

## 3) Nguyen tac thiet ke cho markdown

1. Markdown field luu **raw markdown** trong `note.field_values`.
2. Khi render card:
   - Markdown -> HTML.
   - HTML phai di qua sanitizer hien co truoc khi tra ve giao dien hoc.
3. Khong doi hanh vi cua `richtext`.
4. Paste/drop image vao markdown:
   - Upload file media.
   - Chen markdown image syntax tai vi tri con tro.
   - Khong thay doi model luu tru core (`field_values` van la JSON string values).

## 4) De xuat UX editor markdown

## 4.1 Muc toi thieu (P0)

- Tat ca noi co field input cho note phai render `markdown` bang `textarea` (khong dung `input text`).
- Them label/hint:
  - "Ho tro Markdown"
  - "Ctrl+V hoac keo-tha anh de chen nhanh"

## 4.2 Muc nang cao (P1)

- Editor markdown gom:
  - Toolbar nhe (bold, italic, link, code, list, quote, heading, image marker).
  - Tab `Write | Preview`.
- Layout:
  - Browse/study modal: tab mode (do khung hep).
  - Note edit page: co the tab mode, hoac split neu du rong.

## 4.3 Quy tac chen anh

Khi paste/drop co image file:

1. Upload anh len server.
2. Nhan `asset_id` + `url`.
3. Chen vao editor:

```md
![image-name](/media/proxy/<asset_id>)
```

Neu co selection text thi dung selection lam alt text.

## 5) API de ho tro paste/drop image trong markdown

## 5.1 Khong dung endpoint upload media cu cho markdown

Endpoint cu hop cho media-field mot gia tri duy nhat.

## 5.2 Them endpoint moi (de xuat)

`POST /api/notes/<note_id>/markdown-media`

Input:

- `field_name` (field markdown)
- `file` (image)

Xu ly:

- Validate:
  - note ton tai + ownership
  - field ton tai + `field_type == markdown`
  - mime/size/signature nhu upload media hien tai
- Luu `MediaAsset` (khong ghi de `note.field_values[field_name]`).
- Tra:

```json
{
  "asset_id": "...",
  "url": "/media/proxy/<asset_id>",
  "filename": "..."
}
```

## 6) Thay doi backend can co

1. Mo rong `FIELD_TYPES` va enum model de chap nhan `markdown`.
2. Validation:
   - Them branch `markdown` trong clean field values.
   - Them sanitize markdown text (gioi han do dai + normalize linebreak + reject payload xau co chu dich).
3. Renderer:
   - Them branch markdown trong render context.
   - Convert markdown -> HTML.
   - HTML output tiep tuc sanitize theo pipeline hien co.
4. VoiceVox source field:
   - Coi `markdown` la text-like.
   - Strip markdown -> plain text truoc khi synth.
5. Browse/presenter/repository:
   - Cac cho `text_only` bo sung `markdown`.

## 7) Thay doi frontend can co

1. Field manager:
   - Dropdown type bo sung `markdown`.
2. Note editor + note edit + study edit:
   - `markdown` dung textarea editor.
   - Bat su kien paste/drop.
3. Browse modal:
   - Ho tro markdown editor + paste/drop.
4. Utility JS dung chung:
   - `insertTextAtCursor`
   - `uploadMarkdownImage`
   - `bindMarkdownPasteDrop`
   - `renderMarkdownPreview` (client-side preview, output chi de xem nhanh).

## 8) Database va migration

Trang thai hien tai:

- Cac cot `field_type` dang la `VARCHAR(8)` va khong thay check constraint.
- Chuoi `markdown` dai 8 ky tu => co the luu ngay.

Ket luan:

- Khong bat buoc migration cho dot dau.
- Neu muon du phong dai han, co the nang len `VARCHAR(16)` sau.

## 9) Ke hoach trien khai de xuat

## Phase 1 (bat buoc, ship nhanh)

1. Bo sung `markdown` o backend type constants + validation + renderer.
2. Bo sung `markdown` vao dropdown type.
3. Sua 3 man hinh dang roi vao `input text` de dung `textarea`.
4. Cap nhat logic text-only + VoiceVox source.
5. Test unit/integration co ban cho markdown.

## Phase 2 (quan trong ve UX)

1. Them endpoint upload media cho markdown paste/drop.
2. Them paste/drop handler trong 4 editor.
3. Chen markdown image syntax tu dong.
4. Them hint UI va loading/error trang thai upload.

## Phase 3 (hoan thien)

1. Toolbar markdown.
2. Preview tab (client-side).
3. Tinh chinh autosize/shortcut.

## 10) Test checklist

### Backend

- Tao/sua field type markdown thanh cong.
- Create/update note voi markdown value.
- Renderer markdown khong cho script nguy hiem lot qua.
- Paste image endpoint:
  - success image
  - reject fake mime/signature
  - reject khi field khong phai markdown

### Frontend

- Markdown field hien textarea o 4 editor.
- Paste image chen dung syntax markdown va luu dung noi dung.
- Drop image cung hanh vi.
- Khong lam hong dirty tracking/save flow hien co.

## 11) Rui ro chinh va giai phap

1. Ghi de field markdown thanh asset id:
   - Tach endpoint markdown media, khong tai su dung commit logic media-field cu.
2. Lech render giua preview client va server:
   - Preview client chi de tham khao; output thuc te theo renderer server.
3. Phat sinh media rac (orphan assets):
   - Dot dau chap nhan; co the bo sung cleanup job theo note usage o phase tiep.

## 12) Definition of Done

- Co the tao field markdown, nhap noi dung markdown, render dung tren card.
- Paste/drop image vao markdown editor hoat dong tren cac man hinh chinh.
- Khong pha vo luong cu (`text`, `richtext`, `image`, `audio`, `diagram`).
- Test markdown + media paste duoc bo sung va pass.
