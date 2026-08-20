# Hướng Dẫn Toàn Diện Tạo Note Type & Thiết Kế Template Flashcard Trên Flama

> **Dành cho mọi người dùng**: Tài liệu này giải thích công nghệ đằng sau hệ thống thẻ Flashcard của Flama và cung cấp bộ **Prompt Mẫu (Master Prompt)** để bạn dùng AI (ChatGPT, Claude, Gemini...) thiết kế ra bất kỳ loại thẻ nào đúng 100% ý muốn mà không cần biết lập trình.

---

## 1. Hệ Thống Công Nghệ Của Flama Flashcard

Flama sử dụng kiến trúc thẻ hiện đại, bảo mật và tương thích cao với Anki:

| Thành phần | Công nghệ / Chuẩn | Ý nghĩa & Cách thức hoạt động |
| :--- | :--- | :--- |
| **Template Engine** | **Mustache** | Cú pháp đặt chỗ dữ liệu `{{Tên_Trường}}`. Tự động điền dữ liệu của từng từ vựng vào giao diện. |
| **Ngôn ngữ hiển thị** | **HTML5 & CSS3** | Cho phép tùy biến mọi giao diện: màu sắc, font chữ, bố cục dạng hàng/cột (Flexbox, Grid), đổ bóng, bo góc. |
| **Logic & Tương tác** | **JavaScript (ES6+)** | Chạy các hiệu ứng lật thẻ, hiển thị ẩn/hiện nội dung, tự động phát âm thanh tuần tự. |
| **Môi trường hiển thị** | **Iframe Sandbox** | Đảm bảo an toàn, cách ly phong cách CSS giữa thẻ và ứng dụng Flama, giúp thẻ co giãn mượt mà trên cả điện thoại và máy tính. |
| **Hệ thống Âm thanh** | **Media Proxy Bridge** | Quản lý phát file audio mp3/wav an toàn qua nút bấm hoặc script phát âm tự động. |

---

## 2. Các Loại Trường Dữ Liệu (Field Types) Được Hỗ Trợ

Khi tạo một Note Type, bạn có thể tạo nhiều trường dữ liệu với các kiểu sau:

1. **`text`** (Chữ thuần): Dùng cho từ vựng, kanji, nghĩa ngắn, phiên âm romaji, tên tác giả...
2. **`richtext`** (Văn bản có định dạng): Hỗ trợ bôi đậm, in nghiêng, đổi màu chữ, gạch chân, danh sách gạch đầu dòng.
3. **`markdown`** (Định dạng Markdown): Dùng cho văn bản dài, công thức, bảng biểu.
4. **`audio`** (Âm thanh): File phát âm từ vựng, ví dụ, trích dẫn.
5. **`image`** (Hình ảnh): Ảnh minh họa nghĩa, ảnh sơ đồ tư duy.
6. **`diagram`** (Biểu đồ): Biểu đồ hoặc hình vẽ cấu trúc.

---

## 3. Cú Pháp Mustache Cần Biết

* `{{Tên_Trường}}`: Hiển thị nội dung trường dữ liệu (tự động mã hóa an toàn).
* `{{{Tên_Trường}}}`: Hiển thị nội dung trường dạng HTML (dùng cho trường `richtext`).
* `{{#Tên_Trường}} ... {{/Tên_Trường}}`: **Điều kiện CÓ dữ liệu** (Nếu trường đó có chữ/audio thì mới hiển thị khối bên trong, nếu rỗng thì ẩn đi).
* `{{^Tên_Trường}} ... {{/Tên_Trường}}`: **Điều kiện KHÔNG có dữ liệu** (Hiển thị nội dung mặc định khi trường bị bỏ trống).

---

## 4. 4 Quy Tắc Vàng Khi Thiết Kế Template (Tránh Lỗi)

1. **Quy tắc đặt tên trường**:
   * Nên dùng chữ cái không dấu, viết thường và nối bằng dấu gạch dưới `_` (VD: `word`, `kanji`, `audio_word`, `vi_du_jp`, `vi_du_vi`).
   * Không đặt tên trường chứa khoảng trắng hoặc ký tự đặc biệt lạ.
2. **Quy tắc đóng/mở thẻ HTML trong Mustache**:
   * Nếu mở thẻ `<div>` bên trong `{{#Tên_Trường}}` thì **bắt buộc** phải đóng `</div>` trước khi kết thúc `{{/Tên_Trường}}`.
3. **Quy tắc chiều cao (Tránh tràn khung)**:
   * Không dùng `height: 100vh` trong Front HTML. Thay vào đó dùng Flexbox căn giữa:
     `style="min-height: 200px; display: flex; align-items: center; justify-content: center;"`.
4. **Quy tắc nút Audio và Script an toàn**:
   * Luôn bọc nút audio trong điều kiện `{{#Tên_Audio}} ... {{/Tên_Audio}}` để nếu không có file nghe, nút loa sẽ tự ẩn đi.

---

## 5. Master Prompt: Dùng AI Để Tạo Note Type & Template Theo Ý Muốn

> 📋 **Cách dùng**: Sao chép toàn bộ nội dung trong khung bên dưới, điền yêu cầu của bạn vào mục **[YÊU CẦU CỦA TÔI]** ở cuối, rồi dán vào ChatGPT, Claude hoặc Gemini.

```text
Bạn là một chuyên gia thiết kế Flashcard học ngôn ngữ trên nền tảng Flama (sử dụng chuẩn Mustache Template, HTML5, CSS3 và JavaScript trong iframe sandbox).

Nhiệm vụ của bạn là dựa vào [YÊU CẦU CỦA TÔI], hãy thiết kế:
1. Danh sách các Trường dữ liệu (Field Definitions) cần tạo trong Note Type.
2. Mã Front HTML (Mặt trước).
3. Mã Back HTML (Mặt sau).
4. Mã Shared CSS (Định dạng kiểu dáng chung).

YÊU CẦU KỸ THUẬT BẮT BUỘC ĐỂ KHÔNG BỊ LỖI:
- Đặt tên trường dữ liệu theo chuẩn snake_case chữ thường (ví dụ: word, reading, meaning, audio_word, example_jp, example_vi).
- Sử dụng cú pháp Mustache {{Tên_Trường}} hoặc {{{Tên_Trường}}} (nếu là richtext).
- Mọi khối có điều kiện ẩn hiện bắt buộc dùng: {{#Tên_Trường}} ... {{/Tên_Trường}}.
- Đóng mở thẻ HTML chuẩn xác: Mọi thẻ HTML mở bên trong block Mustache {{#...}} PHẢI ĐƯỢC ĐÓNG trước {{/...}}.
- Khung thẻ mặt trước căn giữa bằng Flexbox (không dùng style height: 100vh).
- Các trường Audio phải tạo thẻ <audio id="..." src="{{Tên_Trường}}"></audio> và nút bấm loa 🔊 tương ứng.
- Nếu có script tự động phát âm tuần tự trong thẻ <script>, phải kiểm tra phần tử tồn tại trước khi phát (safePlay).
- Thiết kế giao diện hiện đại, tinh tế, font chữ rõ ràng, phân cấp thị giác đẹp mắt, hỗ trợ hiển thị đẹp trên cả mobile và desktop.

[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: (Ví dụ: Thẻ học Ngữ pháp JLPT N2 / Thẻ học Kanji N1 / Thẻ học từ vựng Y tế...)
- Các thông tin tôi muốn có trên thẻ:
  + Mặt trước: (Ví dụ: Mẫu ngữ pháp lớn màu đỏ nổi bật, nút nghe audio câu ví dụ tiêu biểu)
  + Mặt sau: (Ví dụ: Ý nghĩa, Cấu trúc ngữ pháp, Giải thích chi tiết, 2 ví dụ có câu dịch và audio, phần phân biệt với ngữ pháp tương đương)
- Phong cách giao diện: (Ví dụ: Tối giản, tông màu xanh dương đậm thanh lịch, font chữ Nhật Bản rõ nét)
```

---

## 6. Ví Dụ Prompt Thực Tế

### Ví dụ 1: Tạo Note Type Từ Vựng Tiếng Nhật Cao Cấp
* **Nhập vào mục [YÊU CẦU CỦA TÔI]**:
  ```text
  - Mục đích thẻ: Học từ vựng JLPT kèm âm Hán Việt và ví dụ đời sống.
  - Mặt trước: Từ vựng Kanji to ở giữa, nút loa phát âm từ vựng.
  - Mặt sau:
    + Hiển thị lại Kanji kèm Furigana và Âm Hán Việt.
    + Ý nghĩa tiếng Việt (chữ đậm màu xanh).
    + Câu ví dụ tiếng Nhật + Câu dịch tiếng Việt + Audio phát âm câu ví dụ.
    + Ghi chú / Từ đồng nghĩa (nếu có mới hiện).
    + Script tự động đọc: Đọc từ vựng trước, sau đó tự đọc câu ví dụ.
  - Phong cách: Sang trọng, bo góc tròn, màu sắc hiện đại.
  ```

### Ví dụ 2: Tạo Note Type Ngữ Pháp Đầy Đủ
* **Nhập vào mục [YÊU CẦU CỦA TÔI]**:
  ```text
  - Mục đích thẻ: Học Ngữ pháp N1 có trích dẫn văn học.
  - Mặt trước: Mẫu ngữ pháp màu đỏ nổi bật ở giữa.
  - Mặt sau:
    + Tiêu đề ngữ pháp + Audio đọc mẫu câu.
    + Ý nghĩa + Cấu trúc ngữ pháp (chữ màu xanh lá).
    + Ghi chú giải thích chi tiết.
    + Ví dụ hội thoại thông thường + dịch nghĩa.
    + Ví dụ trích dẫn văn học (Câu trích dẫn, Tác phẩm, Tác giả, Bản dịch) - chỉ hiện khi có dữ liệu.
    + Mục phân biệt / so sánh với mẫu câu gần nghĩa.
  ```

---

## 7. Các Bước Thao Tác Trên Giao Diện Flama

Sau khi AI đã sinh cho bạn 4 thành phần (Fields, Front HTML, Back HTML, Shared CSS), bạn chỉ cần làm theo 4 bước:

### Bước 1: Tạo Loại Thẻ (Note Type) Mới
1. Vào mục **Quản lý NoteTypes** (hoặc truy cập `/flashcards/note-types`).
2. Bấm nút **+ Tạo NoteType mới**.
3. Điền Tên loại thẻ (Ví dụ: *Ngữ pháp N1 Pro*) và bấm Tạo.

### Bước 2: Tạo Danh Sách Trường (Field Definitions)
1. Bấm nút **Quản lý Trường** (biểu tượng thanh trượt 🎚️).
2. Thêm lần lượt các trường theo bảng danh sách mà AI đã tạo (chọn đúng Tên trường và Loại trường như `text`, `richtext`, `audio`...).
3. Sắp xếp thứ tự các trường bằng cách kéo thả vị trí nếu muốn.

### Bước 3: Dán Mã Template
1. Bấm quay lại trang **Chi tiết Template** của NoteType.
2. Ở cột bên trái:
   * Chọn tab **Front HTML** $\rightarrow$ Dán mã Front HTML từ AI.
   * Chọn tab **Back HTML** $\rightarrow$ Dán mã Back HTML từ AI.
   * Chọn tab **Shared CSS** $\rightarrow$ Dán mã Shared CSS từ AI.
3. Bấm **Lưu Template**.

### Bước 4: Kiểm Tra Trực Tiếp Trên Live Preview
1. Nhìn sang cột bên phải **Xem Trước Trực Tiếp (Live Preview)**.
2. Bấm chuyển đổi giữa **Mặt trước** và **Mặt sau** để kiểm tra giao diện mô phỏng.
3. Thử bấm nút loa 🔊 và kiểm tra màu sắc, bố cục đã đúng ý chưa.
4. Xong! Bạn đã có thể bắt đầu tạo thẻ mới hoặc import file Excel/Anki theo Note Type vừa tạo.
