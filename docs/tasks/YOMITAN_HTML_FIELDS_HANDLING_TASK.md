# Task: Xử lý và Chuẩn hóa Trường HTML từ Tiện ích Yomitan trong Flama Connect

## 1. Mục tiêu (Goal)

Đảm bảo trải nghiệm tra từ và tạo thẻ 1-click từ **Yomitan** (trên Chrome, Firefox, Kiwi Browser di động) hoạt động trơn tru 100%, giải quyết triệt để lỗi khi Yomitan gửi các đoạn HTML (`<ruby>`, `<ol>`, `<li>`, `<b>`, `<span>`, `<svg>`, v.v.) vào các trường của Flama NoteType.

Mục tiêu cụ thể:
1. **Không làm rớt request tạo thẻ từ Yomitan (`addNote` / `canAddNotes`)**: Khi người dùng map các Yomitan marker (như `{furigana}`, `{glossary}`, `{sentence}`) vào các trường có kiểu `text` hoặc `richtext`, hệ thống phải tự động chuẩn hóa thông minh thay vì ném lỗi `400 VALIDATION_ERROR: Field '...' must be plain text (HTML is not allowed)`.
2. **Duy trì tính toàn vẹn dữ liệu & bảo mật (XSS & Sanitization)**: Giữ lại định dạng HTML an toàn cho các trường rich text (`richtext`), đồng thời lọc/strip HTML hợp lý sang plain text sạch sẽ cho các trường văn bản thuần (`text`), bảo vệ thẻ trước script injection độc hại.
3. **Trải nghiệm hiển thị nhất quán trên toàn hệ sinh thái Flama**:
   - Bảng duyệt thẻ (Browse Table): Không hiển thị chuỗi thẻ HTML thô dạng `<ol><li>...</li></ol>` hay `<ruby>...` làm xấu và vỡ layout bảng.
   - Trình soạn thẻ (Card Editor): Hiển thị và hỗ trợ người dùng chỉnh sửa nội dung dễ nhìn.
   - Thẻ học (Study Cards): Render chuẩn thẻ `<ruby>`, danh sách giải nghĩa `<ol>/<ul>`, câu ví dụ in đậm `<b>`.
   - Tìm kiếm (Browse & Study Search): Tìm kiếm dựa trên nội dung chữ thực tế, không ăn nhầm vào tên thẻ hay thuộc tính HTML (`<span class="...">`).
   - Tổng hợp giọng đọc (TTS Engine - VoiceVox & Kokoro): Xử lý đúng cấu trúc Furigana `<ruby>漢字<rt>かんじ</rt></ruby>` để máy phát âm chuẩn tiếng Nhật, không bị đọc lẫn lộn cả chữ Hán lẫn Kana (`漢 かん 字 じ`).

---

## 2. Phân tích chi tiết hiện trạng & Nguyên nhân gốc (Current Problem Analysis)

### 2.1. Cách Yomitan gửi dữ liệu (Yomitan Export Behavior)
Trong hệ sinh thái Anki truyền thống, mọi trường (fields) trong Anki về bản chất đều là chuỗi HTML. Do đó, các marker mặc định của Yomitan xuất ra rất nhiều thẻ HTML:
- `{furigana}`: Xuất ra thẻ HTML Ruby, ví dụ: `<ruby>食<rt>た</rt></ruby>べる` hoặc `<ruby>日<rt>に</rt>本<rt>ほん</rt>語<rt>ご</rt></ruby>`.
- `{glossary}`, `{glossary-brief}`, `{single-glossary-...}`: Xuất ra danh sách có thứ tự/không thứ tự: `<ol><li><span>to eat; to consume</span></li></ol>`.
- `{sentence}`: Tự động in đậm từ vựng được tra trong ngữ cảnh câu: `昨日、りんごを<b>食べた</b>。`.
- `{sentence-furigana}`: Câu chứa các thẻ `<ruby>` và `<b>`.
- `{pitch-accents}`, `{pitch-accent-graphs}`: Chứa các thẻ `<span>` định kiểu hoặc thậm chí `<svg>` biểu đồ cao độ.

### 2.2. Cơ chế kiểm tra dữ liệu hiện tại của Flama (Root Cause)
Flama thiết kế hệ thống trường theo kiểu dữ liệu chặt chẽ (`FieldDef.field_type`: `text`, `richtext`, `markdown`, `image`, `audio`, `diagram`):
1. **Tại Flama Connect (`app/services/connect/actions.py`)**:
   Khi Yomitan gọi RPC `addNote`, hàm `_parse_note` tiếp nhận payload `fields` và thực hiện:
   ```python
   fields = normalize_anki_field_values(fields, tuple(note_type.field_defs))
   validated = validate_note_create_request(
       note_type=note_type,
       payload={"note_type_id": note_type.id, "deck_id": deck.id, "field_values": fields, "tags": tags},
       ...
   )
   ```
   *Lưu ý:* `normalize_anki_field_values` (`app/services/anki_content_normalizer.py`) hiện chỉ decode ký tự nháy đơn (`&apos;`, `&#39;`), hoàn toàn chưa có xử lý đối với thẻ HTML.

2. **Tại Validator (`app/validators/flashcard_input.py`)**:
   Hàm `clean_note_field_values` duyệt qua từng trường:
   - Nếu `field_type == "richtext"`: gọi `sanitize_rich_text(raw_value)`.
   - Nếu `field_type == "text"`: gọi `sanitize_plain_text(raw_value)`.
   Trong `sanitize_plain_text`:
   ```python
   if _HTML_TAG_RE.search(text):
       raise RequestValidationError(
           f"Field '{field_name}' must be plain text (HTML is not allowed).",
           field=field_name,
       )
   ```
   Biểu thức chính quy `_HTML_TAG_RE = re.compile(r"(?is)<\s*/?\s*[a-z!][^>]*>")` phát hiện bất kỳ tag HTML nào (kể cả `<b>`, `<ruby>`, `<ol>`, `<span>`) và **từ chối toàn bộ request với lỗi 400**.

3. **Xung đột với cấu hình mẫu thẻ mặc định**:
   - Mẫu thẻ chuẩn `Flama Standard Vocabulary` (`app/services/flashcard_legacy.py`):
     - `word`: kiểu `text`
     - `reading`: kiểu `text`
     - `translation_vi`: kiểu `text`
   - Ngay trong tài liệu hướng dẫn của Flama (`frontend/src/features/guide/guideData.ts`, dòng 727):
     - Trường 2 (Cách đọc): `{furigana}` -> Yomitan gửi `<ruby>...` vào trường `reading` (`text`) -> **LỖI!**
     - Trường 3 (Ý nghĩa): `{glossary}` -> Yomitan gửi `<ol><li>...` vào trường `translation_vi` (`text`) -> **LỖI!**
   - Hơn nữa, trường định danh duy nhất (`primary identity field`) trong Flama bắt buộc phải có kiểu `text` (`app/services/flashcard_content_service.py:320`). Người dùng thậm chí không thể tự chuyển trường này sang `richtext` được.

---

## 3. Các vấn đề dây chuyền khi xử lý HTML trong Flama (Secondary Issues)

Khi hỗ trợ dữ liệu HTML từ Yomitan, cần đồng bộ giải quyết 5 bài toán giao diện và chức năng liên quan:

### Vấn đề 1: Hiển thị trên bảng danh sách thẻ (Browse Table)
- **Vị trí**: `frontend/src/features/browse/components/BrowseCardTable.tsx` & `app/repositories/vocabulary_repository.py` (`note_display_triplet`).
- **Hiện tượng**: Bảng hiển thị `card.meaning` bằng text thô. Nếu chứa `<ol><li><span>to eat</span></li></ol>`, người dùng nhìn thấy toàn bộ mã nguồn HTML trên từng dòng bảng, gây rối mắt và làm vỡ độ cao hàng.
- **Giải pháp yêu cầu**: Backend hoặc Frontend helper phải strip HTML thành text tóm tắt ngắn gọn và đẹp mắt (ví dụ: `1. to eat; to consume`) khi hiển thị trên Table row.

### Vấn đề 2: Chỉnh sửa thẻ trong Browse Editor
- **Vị trí**: `frontend/src/features/browse/components/BrowseCardEditor.tsx`.
- **Hiện tượng**: Trường `meaning` hiển thị thẻ `<textarea>` chứa đầy mã HTML thô. Người dùng không quen thuộc với HTML sẽ rất khó chỉnh sửa. Khi lưu lại, nếu trường đó là `text`, validator sẽ chặn lại.
- **Giải pháp yêu cầu**: Hỗ trợ hiển thị trực quan hoặc cơ chế toggle giữa Text thuần và HTML format, hoặc hỗ trợ RichText Editor đơn giản.

### Vấn đề 3: Tìm kiếm thẻ (Search Query)
- **Vị trí**: `app/services/browse_card_service.py` (`list_browse_cards`).
- **Hiện tượng**: Tìm kiếm thực hiện qua `func.lower(db.cast(Note.field_values, db.Text)).like(keyword_like)`.
- **Hệ quả**: Nếu người dùng gõ tìm kiếm từ `span`, `class`, `div`, `ol`, hệ thống sẽ trả về hàng loạt thẻ chứa các tag HTML này thay vì từ vựng thực tế.

### Vấn đề 4: Đọc phát âm TTS (VoiceVox & Kokoro)
- **Vị trí**: `frontend/src/features/audio/services/ttsTextNormalizer.ts` & `app/services/browse_voicevox_service.py`.
- **Hiện tượng**: Hàm `cleanTextForTts` hiện dùng `text.replace(/<[^>]*>/g, ' ')`. Khi gặp `<ruby>食<rt>た</rt></ruby>べる`, việc xóa tag thô thiển biến chuỗi thành `食 た べる`, khiến engine đọc cả Hán tự lẫn Hiragana rời rạc ("Shoku ta beru" thay vì "taberu").
- **Giải pháp yêu cầu**: Cần xử lý riêng thẻ Ruby:
  - Nếu lấy cách đọc (Reading): lấy nội dung bên trong `<rt>...</rt>`, bỏ phần chữ Hán chân ruby.
  - Nếu lấy biểu thức Hán tự (Expression): lấy chữ Hán, bỏ phần `<rt>...</rt>`.

### Vấn đề 5: Render thẻ học (Study Card Renderer)
- **Vị trí**: `app/services/flashcard_renderer.py` & `frontend/src/features/study/renderer/clientRenderer.ts`.
- **Hiện tượng**: Mustache mặc định escape HTML với dấu `{{field}}`. Flama có hàm `_upgrade_html_field_double_brace_tokens` nhưng chỉ nâng cấp các trường đã khai báo là `richtext`/`markdown`. Nếu trường được nhập HTML nhưng là kiểu `text`, Mustache sẽ render ra text `&lt;ol&gt;...`.
- **Giải pháp yêu cầu**: Cần cơ chế thống nhất để trường chứa HTML hợp lệ luôn được hiển thị đúng định dạng trên thẻ học.

---

## 4. Giải pháp kỹ thuật đề xuất (Proposed Technical Solutions)

### Giải pháp 1: Tầng chuẩn hóa thông minh tại Flama Connect (Smart Ingest Normalizer)
Can thiệp ngay tại cổng tiếp nhận của Flama Connect (`app/services/anki_content_normalizer.py` hoặc `actions.py`):
1. **Phân loại hành vi theo `field_type`**:
   - **Đối với trường `text` (Text Field)**:
     - Nếu nhận được chuỗi HTML từ Yomitan, tự động **chuyển đổi HTML sang Plain Text sạch (HTML-to-Plain)**:
       - Thẻ ngắt dòng `<br>`, `<p>`, `<div>`, `<li>`: chuyển thành ký tự xuống dòng `\n` hoặc dấu chấm phân cách `1. `, `2. `.
       - Thẻ Ruby `<ruby>漢字<rt>かんじ</rt></ruby>`:
         - Nếu trường là `reading`: ưu tiên trích xuất phần Kana trong `<rt>` -> `かんじ`.
         - Nếu trường là `word`/`expression`: trích xuất phần Hán tự chân ruby -> `漢字` (hoặc định dạng Anki bracket `漢字[かんじ]` nếu cấu hình cho phép).
       - Thẻ in đậm/nghiêng `<b>`, `<strong>`, `<i>`: giữ lại text bên trong, bỏ tag.
       - Thẻ rác `<span>`, `<small>`: giữ text bên trong, bỏ tag.
     - Sau khi chuyển đổi, trường hoàn toàn là plain text và vượt qua validation `sanitize_plain_text` an toàn mà không làm mất nội dung người dùng vừa tra.
   - **Đối với trường `richtext` (RichText Field)**:
     - Cho phép giữ lại các thẻ HTML cấu trúc (`<ol>`, `<ul>`, `<li>`, `<b>`, `<i>`, `<ruby>`, `<rt>`, `<rp>`, `<br>`).
     - Đi qua bộ lọc `bleach.clean` với `ALLOWED_HTML_TAGS` để đảm bảo không bị dính XSS hay style rác độc hại.

### Giải pháp 2: Chuẩn hóa hiển thị Browse Table & Tóm tắt tệp thẻ
- Thêm hàm trích xuất tóm tắt text (Plain summary stripper) tại `app/repositories/vocabulary_repository.py` trong `note_display_triplet`:
  - Loại bỏ các tag HTML khi tạo `word`, `reading`, `meaning` phục vụ bảng Browse Table.
  - Xử lý `<ruby>` thành dạng đọc gọn gàng, biến `<ol><li>...</li></ol>` thành danh sách đánh số dạng text `1. Nghĩa một; 2. Nghĩa hai`.

### Giải pháp 3: Nâng cấp chuẩn hóa TTS Text Normalizer
- Cập nhật cả ở Backend (`browse_voicevox_service.py`) và Frontend (`ttsTextNormalizer.ts`):
  - Phân tích cú pháp thẻ `<ruby>` trước khi strip toàn bộ HTML:
  ```typescript
  // Trích xuất reading kana cho TTS tiếng Nhật
  function stripRubyForReading(html: string): string {
    return html.replace(/<ruby>(?:(?!<rt>).)*<rt>([^<]+)<\/rt><\/ruby>/gi, '$1')
  }
  ```

### Giải pháp 4: Cập nhật tài liệu & Template mẫu
- Rà soát lại tài liệu `frontend/src/features/guide/guideData.ts` và `YomitanMarkersExplorer.tsx` để hướng dẫn người dùng map chính xác marker:
  - Nếu trường là `text`: khuyên dùng `{furigana-plain}` hoặc `{glossary-plain}`.
  - Nếu người dùng muốn giữ format đẹp: khuyên dùng NoteType có các trường `richtext` tương ứng.

---

## 5. Danh sách file tác động (Impact Scope)

| Thành phần | Đường dẫn file | Trách nhiệm |
| --- | --- | --- |
| **Flama Connect Normalizer** | `app/services/anki_content_normalizer.py` | Bổ sung logic parse/clean Yomitan HTML sang plain text cho các trường `text`. |
| **Flama Connect Actions** | `app/services/connect/actions.py` | Áp dụng smart normalizer trước khi validate note payload. |
| **Input Validator** | `app/validators/flashcard_input.py` | Đảm bảo thông điệp lỗi rõ ràng và cung cấp tùy chọn auto-strip an toàn. |
| **Browse Table Summary** | `app/repositories/vocabulary_repository.py` | Strip HTML cho 3 trường tóm tắt (`word`, `reading`, `meaning`) trong Browse Table. |
| **Browse Card Editor** | `frontend/src/features/browse/components/BrowseCardEditor.tsx` | Hiển thị editor thân thiện cho các trường có chứa HTML/RichText. |
| **Browse Card Table** | `frontend/src/features/browse/components/BrowseCardTable.tsx` | Đảm bảo UI cell không bị vỡ hoặc lộ tag thô. |
| **Audio TTS Normalizer** | `frontend/src/features/audio/services/ttsTextNormalizer.ts` | Xử lý bóc tách thẻ `<ruby>` chuẩn xác trước khi gửi engine TTS. |
| **Backend VoiceVox Service** | `app/services/browse_voicevox_service.py` | Đồng bộ logic trích xuất text cho VoiceVox backend. |
| **Guide & Documentation** | `frontend/src/features/guide/guideData.ts` & `YomitanMarkersExplorer.tsx` | Cập nhật hướng dẫn khuyến nghị marker phù hợp với loại trường. |
| **Tests** | `tests/test_flama_connect.py`, `tests/test_anki_content_normalizer.py` | Bổ sung test cases bao phủ toàn diện các trường hợp Yomitan HTML. |

---

## 6. Kế hoạch triển khai (Implementation Phases)

### Giai đoạn 1: Điều tra & Xây dựng Smart Normalizer tại Backend (Backend Core)
- Viết unit test tái hiện lỗi hiện tại: Gửi note chứa `{furigana}`, `{glossary}`, `{sentence}` vào Flama Connect với các trường `text` và `richtext`.
- Cập nhật `anki_content_normalizer.py`:
  - Hàm `html_to_plain_text(value, field_role)`: Chuyển đổi an toàn từ HTML sang văn bản thuần, bóc tách thẻ `<ruby>` thông minh.
  - Tích hợp vào `normalize_anki_field_values` để tự động dọn dẹp các trường kiểu `text`.

### Giai đoạn 2: Chuẩn hóa hiển thị Browse & UI
- Cập nhật `note_display_triplet` trong `vocabulary_repository.py` để làm sạch HTML cho các cột trên Browse Table.
- Kiểm tra Browse Table trong React để xác nhận 100% không còn thẻ `<ol>`, `<li>`, `<span>` thô.

### Giai đoạn 3: Tối ưu TTS Audio & Ruby Rendering
- Nâng cấp `cleanTextForTts` trong `ttsTextNormalizer.ts` và `browse_voicevox_service.py`.
- Viết test case đảm bảo cụm từ `<ruby>漢字<rt>かんじ</rt></ruby>` được chuyển thành âm đọc đúng chuẩn cho VoiceVox/Kokoro.

### Giai đoạn 4: Hướng dẫn người dùng & Hoàn thiện kiểm thử
- Bổ sung ghi chú giải thích rõ ràng trong `YomitanInteractiveGuide.tsx` và `YomitanMarkersExplorer.tsx`.
- Chạy toàn bộ test suite `connect_mcp`, `study`, `browse` đảm bảo không phát sinh hồi quy (Zero Regression).
