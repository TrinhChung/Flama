# Task: Pipeline & Chức năng Tạo Stroke Diagram (SVG) cho Kanji và Hanzi

> **Trạng thái**: Đã hoàn thành (COMPLETED)  
> **Ngày hoàn thành**: 2026-08-28  
> **Commit**: `f6a6585` (`feat(strokes): implement Kanji and Hanzi SVG stroke diagram pipeline`)

---

## 1. Mục tiêu và Định hướng Thiết kế

Bổ sung khả năng tạo và hiển thị **sơ đồ thứ tự nét (stroke-order diagram)** cho chữ Hán trong hệ thống thẻ học (Flashcard) của Flama, hỗ trợ toàn diện:

- **Tiếng Nhật (Kanji)**: Sử dụng bộ dữ liệu chuẩn hóa từ KanjiVG.
- **Tiếng Trung (Hanzi)**: Hỗ trợ cả Giản thể (Simplified - `zh-CN`) và Phồn thể (Traditional - `zh-TW`/`zh-HK`) từ Make Me a Hanzi / Hanzi Writer Data.

### Nguyên tắc cốt lõi

1. **Không render server-side dynamic lúc học (No Runtime Server-Side Rendering)**:
   - Dữ liệu SVG stroke được **tạo/chuẩn bị sẵn (Pre-generated / Pre-built Static SVG Datasets)** thành các file SVG tĩnh, an toàn, chuẩn hóa viewBox và đường nét.
   - Khi học thẻ (Study Session), hệ thống không tốn tài nguyên hay độ trễ để parse/render SVG dynamic trên server.
2. **Chức năng Sinh Stroke SVG theo Field (Field-based Stroke Generator Tool)**:
   - Người dùng (khi soạn Note hoặc xử lý hàng loạt trong Deck) chỉ cần chọn **Field nguồn** (ví dụ: `Expression`, `Word`, `Kanji`, `Hanzi`) và **Locale/Ngôn ngữ** (`ja`, `zh-CN`, `zh-TW`).
   - Hệ thống tự động trích xuất các chữ Hán, ánh xạ ra **danh sách link SVG** sẵn có (hoặc snippet HTML `<img>` chuẩn), rồi ghi vào **Field đích** (Target Field do user chọn, ví dụ `StrokeDiagram` hoặc `KanjiStrokes`).
3. **Người dùng tự do thiết lập Template (User-Controlled Card Template)**:
   - Người dùng toàn quyền nhúng field chứa link/SVG vào Card Template bằng cú pháp Mustache thông thường (ví dụ: `{{{StrokeDiagram}}}` hoặc `<img src="{{StrokeSvgUrl}}">`).
   - Không can thiệp hay sửa đổi core Card Sandbox Renderer / Mustache Engine; dễ dàng tùy biến CSS, grid, kích thước, dark/light mode theo ý muốn của creator.

---

## 2. Luồng Hoạt động Tổng thể (Workflow)

```mermaid
flowchart TD
    A[Pre-built Datasets<br/>KanjiVG + MakeMeAHanzi] --> B[Static SVG Storage<br/>/static/strokes/ja/* & zh/*]
    
    C[User trong Deck / Note Editor] --> D[Mở công cụ: Generate Stroke Diagrams]
    D --> E[Chọn Source Field: vd 'Expression']
    D --> F[Chọn Locale: 'ja' / 'zh-CN' / 'zh-TW']
    D --> G[Chọn Target Field: vd 'StrokeDiagram']
    
    E & F & G --> H[Backend CJK Extractor]
    H --> I[Trích xuất Kanji/Hanzi & Map ra Static SVG URLs]
    I --> J[Cập nhật dữ liệu vào Target Field của Note]
    
    J --> K[Card Template Editor]
    K --> L[User đặt {{{StrokeDiagram}}} vào Front/Back Template]
    L --> M[Study / Preview Thẻ: Hiển thị mượt mà 0ms overhead]
```

---

## 3. Nguồn Dữ liệu & Quản lý Pre-built Static SVG

### 3.1. Japanese Kanji (KanjiVG)
- **Nguồn**: [KanjiVG](https://github.com/KanjiVG/kanjivg) (tagaini.net).
- **Đặc điểm**: SVG vector chất lượng cao, chia từng stroke theo path thứ tự chuẩn Nhật, kèm stroke numbers.
- **License**: CC BY-SA 3.0.
- **Lưu trữ tĩnh**: Các file SVG được build sẵn theo mã Unicode Hex:
  - Đường dẫn: `/static/strokes/ja/{unicode_hex}.svg` (ví dụ: `勉` -> `/static/strokes/ja/52c9.svg` hoặc `052c9.svg`).

### 3.2. Chinese Hanzi (Make Me a Hanzi / Hanzi Writer Data)
- **Nguồn**: [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) & [hanzi-writer-data](https://github.com/chanind/hanzi-writer-data).
- **Đặc điểm**: Hỗ trợ hơn 9,000 chữ Giản thể (`zh-CN`) và Phồn thể (`zh-TW` / `zh-HK`), dữ liệu đường nét chuẩn nét viết tiếng Trung.
- **License**: Arphic Public License / MIT.
- **Lưu trữ tĩnh**:
  - Giản thể / Chung: `/static/strokes/zh/{unicode_hex}.svg` (ví dụ: `学` -> `/static/strokes/zh/5b66.svg`).
  - Biến thể Phồn thể: `/static/strokes/zh-hant/{unicode_hex}.svg`.

### 3.3. Quy trình Pre-generate SVG Dataset (CLI Seed / Build Tool)
- Cung cấp CLI script trong `app/cli.py` (`flask strokes`):
  ```bash
  flask strokes build-dataset --locale ja --source ./data/kanjivg
  flask strokes build-dataset --locale zh --source ./data/makemeahanzi
  flask strokes seed-starter
  flask strokes status
  ```
- **Chuẩn hóa SVG khi build**:
  - Loại bỏ các tag không an toàn (không `<script>`, không `onload`, không `foreignObject`).
  - Chuẩn hóa `viewBox="0 0 109 109"`, `fill="none"`, `stroke="currentColor"` hoặc stroke styling rõ ràng.
  - Tối ưu dung lượng SVG.

---

## 4. Bộ Trích Xuất Ký Tự CJK (`app/services/strokes/cjk_extractor.py`)

```python
class CjkExtractor:
    @staticmethod
    def extract_characters(text: str, deduplicate: bool = True, max_limit: int = 15) -> list[str]:
        """
        Trích xuất danh sách các ký tự CJK (Kanji / Hanzi) từ chuỗi text/HTML.
        - Strip HTML tags (không scan nhầm thuộc tính/class).
        - Bỏ qua Hiragana (0x3040-0x309F), Katakana (0x30A0-0x30FF).
        - Bỏ qua Pinyin, Bopomofo, Latin, số, dấu câu.
        - Giữ lại CJK Unified Ideographs (0x4E00-0x9FFF, Extension A-I, Compatibility).
        - deduplicate=True: Loại bỏ ký tự lặp lại trong cùng 1 từ/câu.
        - max_limit: Giới hạn tối đa số ký tự để tránh card quá tải.
        """
```

### Quy tắc phân định Locale
- `ja`: Tiếng Nhật
- `zh-CN` / `zh`: Tiếng Trung Giản thể / Chung
- `zh-TW` / `zh-hant`: Tiếng Trung Phồn thể

---

## 5. Chức năng Sinh Stroke Kanji/Hanzi (Stroke Generator Feature)

### 5.1. Vị trí & Trải nghiệm Người Dùng (UI/UX)
- **Modal Tạo Nét (`BrowseStrokeModal.tsx`)**:
  - **Live SVG Preview**: Hiển thị trực quan chữ Hán được trích xuất, thumbnail SVG, mã Hex, badge trạng thái có/chưa có SVG.
  - **Source Field**: Chọn field chứa từ vựng (ví dụ `Expression`, `Word`).
  - **Language / Locale**: `Tiếng Nhật (Kanji)` / `Tiếng Trung (Giản thể)` / `Tiếng Trung (Phồn thể)`.
  - **Target Field**: Chọn field để lưu (ví dụ `StrokeDiagram`).
  - **Output Format**: *HTML Embed* (Mặc định) hoặc *URL List*.
  - **Overwrite existing**: Tùy chọn ghi đè nếu trường đã có dữ liệu.
- **Tích hợp vị trí**:
  - Trong thanh công cụ Browse Toolbar: nút "Tạo nét SVG" và dropdown menu hàng loạt.
  - Trong Card Editor Header: nút "Tạo nét".

---

## 6. Thiết kế API Backend (`app/api/v1/strokes/routes.py`)

### 6.1. Endpoint Resolve Stroke URLs cho 1 chuỗi text (Preview & Single Note)
- **Route**: `POST /api/strokes/generate`
- **Request Body**:
  ```json
  {
    "text": "日本語を勉強する",
    "locale": "ja",
    "format": "html",
    "deduplicate": true,
    "max_characters": 15
  }
  ```
- **Response**:
  ```json
  {
    "characters": ["日", "本", "語", "勉", "強"],
    "items": [
      { "char": "日", "hex": "65e5", "url": "/static/strokes/ja/65e5.svg", "available": true },
      { "char": "本", "hex": "672c", "url": "/static/strokes/ja/672c.svg", "available": true },
      { "char": "語", "hex": "8a9e", "url": "/static/strokes/ja/8a9e.svg", "available": true },
      { "char": "勉", "hex": "52c9", "url": "/static/strokes/ja/52c9.svg", "available": true },
      { "char": "強", "hex": "5f37", "url": "/static/strokes/ja/5f37.svg", "available": true }
    ],
    "output": "<div class=\"flama-stroke-diagram\"><img src=\"/static/strokes/ja/65e5.svg\" alt=\"日\" title=\"日\" /><img src=\"/static/strokes/ja/672c.svg\" alt=\"本\" title=\"本\" /><img src=\"/static/strokes/ja/8a9e.svg\" alt=\"語\" title=\"語\" /><img src=\"/static/strokes/ja/52c9.svg\" alt=\"勉\" title=\"勉\" /><img src=\"/static/strokes/ja/5f37.svg\" alt=\"強\" title=\"強\" /></div>"
  }
  ```

### 6.2. Endpoint Batch Generate cho Deck / Note List
- **Route**: `POST /api/strokes/batch-generate` và `POST /api/decks/<deck_id>/strokes/batch-generate`
- **Request Body**:
  ```json
  {
    "note_ids": ["uuid-1", "uuid-2"],
    "source_field": "Expression",
    "target_field": "StrokeDiagram",
    "locale": "ja",
    "format": "html",
    "overwrite": false
  }
  ```
- **Response**:
  ```json
  {
    "total_processed": 150,
    "updated": 142,
    "skipped": 8,
    "missing_characters": []
  }
  ```

---

## 7. Thiết Lập Template Phía Người Dùng (Template Customization)

### 7.1. Dùng Field HTML trực tiếp
Trong Back Template:
```html
<div class="card-back">
  <div class="reading">{{Reading}}</div>
  <div class="meaning">{{Meaning}}</div>
  
  {{#StrokeDiagram}}
  <div class="stroke-section">
    <div class="stroke-title">Thứ tự nét:</div>
    <div class="stroke-container">
      {{{StrokeDiagram}}}
    </div>
  </div>
  {{/StrokeDiagram}}
</div>
```

### 7.2. Tùy biến CSS trong Template Style
```css
.flama-stroke-diagram {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}

.flama-stroke-diagram img {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 4px;
}

/* Dark mode support */
.dark .flama-stroke-diagram img {
  background-color: #1e293b;
  border-color: #334155;
  filter: invert(0.9) hue-rotate(180deg);
}
```

---

## 8. Bảo Mật & Tương Thích CSP (Security & Sandbox)

1. **Static Files Serving**:
   - Tất cả SVG được lưu trữ trong thư mục static của Flama (`static/strokes/ja/`, `static/strokes/zh/`).
   - Browser chỉ load ảnh nội bộ từ cùng origin (`/static/strokes/...`), không cần fetch CDN ngoài.
2. **Sanitization triệt để**:
   - Backend `flashcard_renderer.py` và frontend `clientRenderer.ts` đã whitelist an toàn mẫu URL `/static/strokes/<locale>/<hex>.svg` cùng các thuộc tính `title`, `loading`.

---

## 9. Giấy Phép Dữ Liệu (Licensing & Attribution)

- **KanjiVG**: License [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- **Make Me a Hanzi**: License [Arphic Public License](https://www.freedesktop.org/wiki/Arphic_Public_License/).
- **Hanzi Writer Data**: License [MIT](https://github.com/chanind/hanzi-writer-data).

---

## 10. Kế Hoạch Triển Khai (Phased Roadmap)

### Phase 1: Chuẩn bị Dataset tĩnh & Bộ trích xuất CJK
- [x] Tải và build bộ SVG tĩnh cho Kanji Nhật (KanjiVG) vào `static/strokes/ja/`.
- [x] Tải và build bộ SVG tĩnh cho Hanzi Trung (Make Me a Hanzi / Hanzi Writer Data) vào `static/strokes/zh/`.
- [x] Viết module `cjk_extractor.py` (trích xuất ký tự Hán, lọc bỏ kana/pinyin/latin/html).
- [x] Viết CLI seed command `flask strokes build-dataset` để tự động hóa việc đồng bộ dataset.

### Phase 2: Backend API & Service
- [x] Xây dựng `StrokeService` để map ký tự sang URL SVG tĩnh theo locale (`ja`, `zh-CN`, `zh-TW`).
- [x] Tạo endpoint `POST /api/strokes/generate` (tạo stroke snippet cho single text/preview).
- [x] Tạo endpoint `POST /api/decks/<deck_id>/strokes/batch-generate` (batch generation cho deck/notes).

### Phase 3: Frontend UI Generator & Template Support
- [x] Thêm nút/công cụ "Generate Stroke Diagrams" trong Note Editor modal.
- [x] Thêm Batch Action "Sinh sơ đồ nét Kanji/Hanzi" trong Deck Browse / Card Management.
- [x] Cung cấp các Card Template mẫu có sẵn trường `{{{StrokeDiagram}}}` và CSS mẫu để người dùng áp dụng nhanh (`NoteTypeAiGuideModal.tsx`).

---

## 11. Tiêu Chuẩn Nghiệm Thu (Acceptance Criteria)

- [x] Bộ file SVG tĩnh của Tiếng Nhật và Tiếng Trung được tổ chức ngăn nắp trong `static/strokes/` và truy cập được qua URL local.
- [x] Hệ thống trích xuất chính xác chữ Hán từ chuỗi input (ví dụ: `勉強する` -> `勉`, `強`; `学习中文` -> `学`, `习`, `中`, `文`).
- [x] Chức năng Sinh Stroke trả về đúng danh sách link SVG hoặc đoạn mã HTML `<img>` theo locale được chọn.
- [x] Khi thực hiện Batch Generate trên Deck, các Note được cập nhật chính xác nội dung vào Target Field đã chỉ định.
- [x] Người dùng có thể đặt `{{{StrokeDiagram}}}` vào Card Template và xem trước (Preview) cũng như học (Study) hiển thị mượt mà mà không có bất kỳ độ trễ render nào trên server.
- [x] Không có lỗ hổng XSS hay script độc hại trong các file SVG pre-built.
