# Task: Pipeline & Chức năng Tạo Stroke Diagram (SVG) cho Kanji và Hanzi

## 1. Mục tiêu và Định hướng Thiết kế

Bổ sung khả năng tạo và hiển thị **sơ đồ thứ tự nét (stroke-order diagram)** cho chữ Hán trong hệ thống thẻ học (Flashcard) của Flama, hỗ trợ toàn diện:

- **Tiếng Nhật (Kanji)**: Sử dụng bộ dữ liệu chuẩn hóa từ KanjiVG.
- **Tiếng Trung (Hanzi)**: Hỗ trợ cả Giản thể (Simplified - `zh-CN`) và Phồn thể (Traditional - `zh-TW`/`zh-HK`) từ Make Me a Hanzi / Hanzi Writer Data.

### Nguyên tắc cốt lõi mới

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
- **License**: CC BY-SA 3.0 (ghi nhận attribution trong trang Licenses/About).
- **Lưu trữ tĩnh**: Các file SVG được build sẵn theo mã Unicode Hex:
  - Đường dẫn: `/static/strokes/ja/{unicode_hex}.svg` (ví dụ: `勉` -> `/static/strokes/ja/52c9.svg`).

### 3.2. Chinese Hanzi (Make Me a Hanzi / Hanzi Writer Data)
- **Nguồn**: [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) & [hanzi-writer-data](https://github.com/chanind/hanzi-writer-data).
- **Đặc điểm**: Hỗ trợ hơn 9,000 chữ Giản thể (`zh-CN`) và Phồn thể (`zh-TW` / `zh-HK`), dữ liệu đường nét chuẩn nét viết tiếng Trung.
- **License**: Arphic Public License / MIT.
- **Lưu trữ tĩnh**:
  - Giản thể / Chung: `/static/strokes/zh/{unicode_hex}.svg` (ví dụ: `学` -> `/static/strokes/zh/5b66.svg`).
  - Biến thể Phồn thể (nếu có khác biệt): `/static/strokes/zh-hant/{unicode_hex}.svg` hoặc cùng tra cứu trong bộ Chinese dataset.

### 3.3. Quy trình Pre-generate SVG Dataset (CLI Seed / Build Tool)
- Cung cấp CLI script để build/tối ưu toàn bộ SVG 1 lần khi triển khai hoặc cập nhật:
  ```bash
  flask strokes build-dataset --locale ja --source ./data/kanjivg
  flask strokes build-dataset --locale zh --source ./data/makemeahanzi
  ```
- **Chuẩn hóa SVG khi build**:
  - Loại bỏ các tag không an toàn (không `<script>`, không `onload`, không `foreignObject`).
  - Chuẩn hóa `viewBox="0 0 109 109"`, `fill="none"`, `stroke="currentColor"` hoặc stroke styling rõ ràng.
  - Tối ưu dung lượng SVG (SVGO hoặc strip metadata thừa).

---

## 4. Bộ Trích Xuất Ký Tự CJK (Extractor & Locale Resolver)

Tạo service dùng chung `app/services/strokes/cjk_extractor.py`:

```python
class CjkExtractor:
    @staticmethod
    def extract_characters(text: str, deduplicate: bool = True, max_limit: int = 15) -> list[str]:
        """
        Trích xuất danh sách các ký tự CJK (Kanji / Hanzi) từ chuỗi text/HTML.
        - Strip HTML tags (không scan nhầm thuộc tính/class).
        - Bỏ qua Hiragana (0x3040-0x309F), Katakana (0x30A0-0x30FF).
        - Bỏ qua Pinyin, Bopomofo, Latin, số, dấu câu.
        - Giữ lại CJK Unified Ideographs (0x4E00-0x9FFF, Extension A-F, Compatibility).
        - deduplicate=True: Loại bỏ ký tự lặp lại trong cùng 1 từ/câu.
        - max_limit: Giới hạn tối đa số ký tự để tránh card quá tải.
        """
```

### Quy tắc phân định Locale
- **Không tự đoán mò** giữa tiếng Nhật và tiếng Trung chỉ dựa trên ký tự (vì nhiều chữ như `直`, `骨`, `令` có quy tắc nét viết khác nhau giữa Nhật và Trung).
- Locale được truyền rõ ràng từ tùy chọn người dùng:
  - `ja`: Tiếng Nhật
  - `zh-CN`: Tiếng Trung Giản thể
  - `zh-TW`: Tiếng Trung Phồn thể

---

## 5. Chức năng Sinh Stroke Kanji/Hanzi (Stroke Generator Feature)

### 5.1. Vị trí & Trải nghiệm Người Dùng (UI/UX)

#### A. Trong Trình Soạn Thảo Note (Note Editor / Create & Edit Card)
- Cạnh các text field hoặc trong thanh công cụ Note Form có nút **"Generate Stroke SVGs" (Sinh sơ đồ nét)**.
- Modal hoặc Popover cho phép chọn:
  - **Source Field**: Chọn field chứa từ vựng (ví dụ `Expression`, `Word`).
  - **Language / Locale**: `Tiếng Nhật (Kanji)` / `Tiếng Trung (Giản thể)` / `Tiếng Trung (Phồn thể)`.
  - **Target Field**: Chọn field để lưu (ví dụ `StrokeDiagram`, `Kanji_Stroke`, hoặc tạo field mới).
  - **Output Format**:
    1. *HTML Embed* (Mặc định): Tạo các thẻ `<img src="/static/strokes/ja/52c9.svg" alt="勉" class="stroke-svg" />` bọc trong wrapper div.
    2. *URL List / JSON*: Mảng link URL SVG (phù hợp nếu template dùng script/mustache loop).
- Bấm **"Apply"**: Backend trả về nội dung và tự động điền vào Target Field.

#### B. Trong Danh Sách Thẻ / Deck Actions (Batch Generation)
- Trong màn hình Deck Detail hoặc Browse / Cards List:
  - Chọn nhiều Note (hoặc toàn bộ Deck).
  - Chọn Batch Action: **"Generate Kanji/Hanzi Stroke Diagrams"**.
  - Form cấu hình:
    - **Source Field**: `Expression`
    - **Target Field**: `StrokeDiagram`
    - **Locale**: `ja`
    - **Overwrite existing**: Có ghi đè nếu field đích đã có dữ liệu hay không.
  - Hệ thống chạy batch cập nhật hàng loạt các Note trong deck.

---

## 6. Thiết kế API Backend

### 6.1. Endpoint Resolve Stroke URLs cho 1 chuỗi text (Preview & Single Note)
- **Route**: `POST /api/strokes/generate`
- **Request Body**:
  ```json
  {
    "text": "日本語を勉強する",
    "locale": "ja",
    "format": "html", // "html" | "urls" | "raw"
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
- **Route**: `POST /api/decks/<deck_id>/strokes/batch-generate`
- **Request Body**:
  ```json
  {
    "note_ids": [101, 102, 103], // hoặc rỗng để áp dụng cả deck
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

Sau khi link/HTML SVG đã được lưu vào Note Field, người dùng tự do thiết lập Card Template trong giao diện **Card Template Editor**:

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
Người dùng có thể thêm CSS tùy ý vào Card Style:
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
   - Browser chỉ load ảnh nội bộ từ cùng origin (`/static/strokes/...`), không cần fetch CDN ngoài, không cần mở rộng Content Security Policy (`connect-src` hay `img-src` bên ngoài).
2. **Sanitization triệt để**:
   - Bộ pre-built SVG được quét sạch hoàn toàn các thẻ thực thi (`<script>`, inline JS, event handlers `onload`, `onclick`).
   - Chỉ giữ lại vector paths, stroke numbers và svg structure thuần túy.

---

## 9. Giấy Phép Dữ Liệu (Licensing & Attribution)

- **KanjiVG**: License [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- **Make Me a Hanzi**: License [Arphic Public License](https://www.freedesktop.org/wiki/Arphic_Public_License/).
- **Hanzi Writer Data**: License [MIT](https://github.com/chanind/hanzi-writer-data).
- **Thực thi**:
  - Ghi nhận attribution rõ ràng trong trang About / Open Source Software Licenses của Flama (`/settings/licenses` hoặc footer).
  - Đảm bảo tuân thủ điều khoản chia sẻ và ghi công của tác giả nguồn dữ liệu.

---

## 10. Kế Hoạch Triển Khai (Phased Roadmap)

### Phase 1: Chuẩn bị Dataset tĩnh & Bộ trích xuất CJK
- [ ] Tải và build bộ SVG tĩnh cho Kanji Nhật (KanjiVG) vào `static/strokes/ja/`.
- [ ] Tải và build bộ SVG tĩnh cho Hanzi Trung (Make Me a Hanzi / Hanzi Writer Data) vào `static/strokes/zh/`.
- [ ] Viết module `cjk_extractor.py` (trích xuất ký tự Hán, lọc bỏ kana/pinyin/latin/html).
- [ ] Viết CLI seed command `flask strokes build-dataset` để tự động hóa việc đồng bộ dataset.

### Phase 2: Backend API & Service
- [ ] Xây dựng `StrokeService` để map ký tự sang URL SVG tĩnh theo locale (`ja`, `zh-CN`, `zh-TW`).
- [ ] Tạo endpoint `POST /api/strokes/generate` (tạo stroke snippet cho single text/preview).
- [ ] Tạo endpoint `POST /api/decks/<deck_id>/strokes/batch-generate` (batch generation cho deck/notes).

### Phase 3: Frontend UI Generator & Template Support
- [ ] Thêm nút/công cụ "Generate Stroke Diagrams" trong Note Editor modal.
- [ ] Thêm Batch Action "Sinh sơ đồ nét Kanji/Hanzi" trong Deck Browse / Card Management.
- [ ] Cung cấp các Card Template mẫu có sẵn trường `{{{StrokeDiagram}}}` và CSS mẫu để người dùng áp dụng nhanh.

---

## 11. Tiêu Chuẩn Nghiệm Thu (Acceptance Criteria)

- [ ] Bộ file SVG tĩnh của Tiếng Nhật và Tiếng Trung được tổ chức ngăn nắp trong `static/strokes/` và truy cập được qua URL local.
- [ ] Hệ thống trích xuất chính xác chữ Hán từ chuỗi input (ví dụ: `勉強する` -> `勉`, `強`; `学习中文` -> `学`, `习`, `中`, `文`).
- [ ] Chức năng Sinh Stroke trả về đúng danh sách link SVG hoặc đoạn mã HTML `<img>` theo locale được chọn.
- [ ] Khi thực hiện Batch Generate trên Deck, các Note được cập nhật chính xác nội dung vào Target Field đã chỉ định.
- [ ] Người dùng có thể đặt `{{{StrokeDiagram}}}` vào Card Template và xem trước (Preview) cũng như học (Study) hiển thị mượt mà mà không có bất kỳ độ trễ render nào trên server.
- [ ] Không có lỗ hổng XSS hay script độc hại trong các file SVG pre-built.
