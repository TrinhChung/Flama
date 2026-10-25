# Hướng Dẫn Toàn Diện Tạo Note Type & Thiết Kế Template Flashcard Trên Flama

> **Dành cho mọi người dùng**: Tài liệu này giải thích công nghệ đằng sau hệ thống thẻ Flashcard của Flama và cung cấp bộ **Prompt Mẫu (Master Prompt)** để bạn dùng AI (ChatGPT, Claude, Gemini...) thiết kế ra bất kỳ loại thẻ nào đúng 100% ý muốn mà không cần biết lập trình.

---

## 1. Hệ Thống Công Nghệ Của Flama Flashcard

Flama sử dụng kiến trúc thẻ hiện đại, bảo mật và tương thích cao với Anki:

| Thành phần | Công nghệ / Chuẩn | Ý nghĩa & Cách thức hoạt động |
| :--- | :--- | :--- |
| **Template Engine** | **Mustache** | Cú pháp đặt chỗ `{{InputKey}}`. Mapping tại Note Type cấp dữ liệu field cho input của Template. |
| **Ngôn ngữ hiển thị** | **HTML5 & CSS3** | Cho phép tùy biến mọi giao diện: màu sắc, font chữ, bố cục dạng hàng/cột (Flexbox, Grid), đổ bóng, bo góc. |
| **Logic & Tương tác** | **JavaScript (ES6+)** | Chạy các hiệu ứng lật thẻ, hiển thị ẩn/hiện nội dung, tự động phát âm thanh tuần tự. |
| **Môi trường hiển thị** | **Iframe Sandbox** | Đảm bảo an toàn, cách ly phong cách CSS giữa thẻ và ứng dụng Flama, giúp thẻ co giãn mượt mà trên cả điện thoại và máy tính. |
| **Hệ thống Âm thanh** | **Media Proxy Bridge** | Quản lý phát file audio mp3/wav an toàn qua nút bấm hoặc script phát âm tự động. |

---

## 2. Các Loại Trường Dữ Liệu (Field Types) Được Hỗ Trợ

Khi tạo một Note Type, bạn có thể tạo nhiều trường dữ liệu với các kiểu sau:

**Field** thuộc Note Type, xác định dữ liệu mỗi note lưu và kiểu nhập liệu. **Input** thuộc Template, xác định dữ liệu giao diện cần nhận. Một Template có một bộ input gồm nhiều trường. Tên field và input không cần giống nhau; mapping nối bằng ID field và key input.

1. **`text`** (Chữ thuần): Dùng cho từ vựng, kanji, nghĩa ngắn, phiên âm romaji, tên tác giả...
2. **`richtext`** (Văn bản có định dạng): Hỗ trợ bôi đậm, in nghiêng, đổi màu chữ, gạch chân, danh sách gạch đầu dòng.
3. **`markdown`** (Định dạng Markdown): Dùng cho văn bản dài, công thức, bảng biểu.
4. **`audio`** (Âm thanh): File phát âm từ vựng, ví dụ, trích dẫn.
5. **`image`** (Hình ảnh): Ảnh minh họa nghĩa, ảnh sơ đồ tư duy.
6. **`diagram`** (Biểu đồ): Biểu đồ hoặc hình vẽ cấu trúc.
7. **`array`** (Danh sách): JSON list gồm text hoặc list lồng. Dữ liệu cũ mỗi dòng một item vẫn đọc được; số hoặc object không phải item hợp lệ.

---

## 3. Cú Pháp Mustache Cần Biết

* `{{InputKey}}`: Hiển thị nội dung input (tự động mã hóa an toàn).
* `{{{InputKey}}}`: Hiển thị nội dung input dạng HTML (dùng cho input `richtext`).
* `{{#InputKey}} ... {{/InputKey}}`: **Điều kiện CÓ dữ liệu** (nếu input có dữ liệu thì hiển thị khối bên trong).
* `{{^InputKey}} ... {{/InputKey}}`: **Điều kiện KHÔNG có dữ liệu** (hiển thị nội dung mặc định khi input bị bỏ trống).
* `{{#options}}<span>{{.}}</span>{{/options}}`: lặp từng item của array. `{{options.0}}` lấy item đầu; `{{options}}` in toàn list thành chuỗi nối bằng dấu phẩy.
* `{{FrontSide}}`: mặt sau hiển thị phần HTML của mặt trước; không chạy lại script mặt trước trong phần được chèn này.

Không dùng Handlebars `{{#each options}}`, partials, đổi delimiter hoặc `{{@index}}`. Không có helper `{{index}}`: để đánh số đáp án, dùng thứ tự DOM `index + 1` trong script. Chuỗi được escape; rich text/Markdown được renderer chuẩn bị và sanitize trước khi chèn HTML.

`shared_css` là CSS tĩnh, không nội suy Mustache. Token trong HTML và inline `<style>` được render; script của template được tách trước Mustache, vì vậy token trong `<script>` giữ nguyên. Script lấy dữ liệu qua `FlamaCard.getContext().fieldValues`, tránh đưa raw text vào mã JavaScript. Script chạy khi dựng nội dung mới; dùng `FlamaCard.onReveal(callback)` nếu cần xử lý khi mặt thẻ được mở lại. Lật lại mặt thẻ không thay candidate giữ DOM và lựa chọn hiện tại.

---

## 4. 4 Quy Tắc Vàng Khi Thiết Kế Template (Tránh Lỗi)

1. **Quy tắc đặt key input**:
   * Nên dùng chữ cái không dấu, viết thường và nối bằng dấu gạch dưới `_` (VD: `word`, `kanji`, `audio_word`, `vi_du_jp`, `vi_du_vi`).
   * Không đặt key input chứa khoảng trắng hoặc ký tự đặc biệt lạ. Nhãn hiển thị và tên field có thể dùng tiếng Việt.
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
2. Bộ input của Template (key, nhãn, kiểu) và bảng mapping field → input.
3. Mã Front HTML (Mặt trước).
4. Mã Back HTML (Mặt sau).
5. Mã Shared CSS (Định dạng kiểu dáng chung).

YÊU CẦU KỸ THUẬT BẮT BUỘC ĐỂ KHÔNG BỊ LỖI:
- Đặt key input theo chuẩn snake_case chữ thường (ví dụ: word, reading, meaning, audio_word, example_jp, example_vi).
- Dùng cùng kiểu dữ liệu cho input và field được mapping; không đổi text thành markdown hoặc richtext ngầm.
- Sử dụng cú pháp Mustache {{InputKey}} hoặc {{{InputKey}}} (nếu là richtext).
- Mọi khối có điều kiện ẩn hiện bắt buộc dùng: {{#InputKey}} ... {{/InputKey}}.
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

Sau khi AI sinh danh sách field, bộ input, mapping và mã giao diện, thực hiện các bước sau:

### Bước 1: Tạo Loại Thẻ (Note Type) Mới
1. Vào mục **Quản lý NoteTypes** (hoặc truy cập `/flashcards/note-types`).
2. Bấm nút **+ Tạo NoteType mới**.
3. Điền Tên loại thẻ (Ví dụ: *Ngữ pháp N1 Pro*) và bấm Tạo.

### Bước 2: Tạo Danh Sách Trường (Field Definitions)
1. Mở Note Type: tab **Trường dữ liệu** hiển thị mặc định.
2. Chọn **Thêm trường**, khai báo tên, kiểu, bắt buộc và định danh chính khi phù hợp, rồi lưu. Danh sách ở trái; cấu hình một field ở phải.
3. Thử editor mẫu theo kiểu field. Ảnh/audio có thể chọn tệp cục bộ để xem thử; dữ liệu mẫu không được lưu vào note và tệp thử không được upload.
4. Sắp xếp thứ tự bằng kéo thả hoặc nút lên/xuống. Khi chuyển field/tab còn thay đổi chưa lưu, chọn lưu, bỏ thay đổi hoặc ở lại.

### Bước 3: Thiết Kế Template
1. Mở **Thư viện giao diện thẻ** (`/card-templates`) và tạo hoặc chọn Template.
2. Bấm **Inputs** để khai báo bộ input trong hộp thoại riêng. Chọn từng input để sửa nhãn và kiểu; key nằm ở **Nâng cao**. Key đã lưu được giữ cố định.
3. Bấm **Áp dụng vào bản nháp**. Nút này chưa ghi lên máy chủ; **Hủy** bỏ các chỉnh sửa riêng trong hộp thoại.
4. Dán mã vào ba tab **Mặt trước**, **Mặt sau**, **CSS**. Dùng **Chèn input** để chọn token trong hai tab HTML.
5. Bấm **Lưu thay đổi** để lưu thiết kế và bộ input.

### Bước 4: Kiểm Tra Trực Tiếp Trên Live Preview
1. Nhìn sang cột bên phải **Xem Trước Trực Tiếp (Live Preview)**.
2. Bấm chuyển đổi giữa **Mặt trước** và **Mặt sau** để kiểm tra giao diện mô phỏng.
3. Thử bấm nút loa 🔊 và kiểm tra màu sắc, bố cục đã đúng ý chưa.
4. Mở **Dữ liệu mẫu** để thay giá trị thử. Các giá trị này chỉ dùng xem trước.

Mỗi input có mẫu đúng kiểu để sửa ngay: text, rich text trực quan (có HTML nâng cao), Markdown, danh sách array và media. Array có thể thêm/xóa/đổi thứ tự item; JSON nâng cao giữ được list lồng và báo dữ liệu sai mà không gửi bản sai sang preview. Ảnh, audio và diagram có mẫu hệ thống; có thể thay URL media hợp lệ để thử nguồn khác. Có thể khôi phục từng mẫu, tất cả mẫu hoặc đặt giá trị rỗng. Sample chỉ nằm trong bộ nhớ của phiên editor: đóng/mở bảng vẫn giữ, tải lại trang sẽ reset; sample không đánh dấu template/mapping chưa lưu và không đi vào DB hay lịch sử phiên bản. Trang mapping có cùng editor mẫu, dùng đúng kiểu của field được gắn.

### Bước 5: Gắn Template Và Mapping
1. Tại Note Type, mở tab **Templates** → **Gắn template**.
2. Chọn thiết kế, ghép các input với field cùng kiểu và xác nhận gắn.
3. Bấm một template trong danh sách để mở trang mapping riêng. Sửa tên lần gắn, mapping, xem trước rồi **Lưu mapping**.
4. **Sửa thiết kế** dẫn đến Template Detail; đường quay lại giữ đúng lần gắn đang cấu hình. Sau khi lưu, bạn có thể tạo note hoặc import dữ liệu theo Note Type.

## 8. Thư viện Mẫu thẻ và ánh xạ dữ liệu

Vào **Thư viện giao diện thẻ** (`/card-templates`), chọn **Tạo mẫu mới**, nhập tên rồi tạo. Trang chi tiết tập trung editor và preview; **Inputs**, **Dữ liệu mẫu**, thông tin và lịch sử mở riêng khi cần. Bấm **Lưu thay đổi** để lưu cùng mẫu hiện tại.

Input là tên đặt chỗ trong HTML, ví dụ `{{term}}`; field là trường dữ liệu của loại thẻ. Hai tên không cần giống nhau. Bấm **Áp dụng vào loại thẻ**, chọn loại thẻ, bấm **Tiếp tục**, ánh xạ từng input rồi xác nhận **Gắn mẫu**. Chỉ input và field cùng kiểu được ghép; `text`, `richtext` và `markdown` là ba kiểu khác nhau. Nhiều input có thể dùng cùng một field.

Ánh xạ lưu theo ID trường: đổi tên field không yêu cầu sửa HTML. **Khuyến nghị ánh xạ** chỉ là lời nhắc; input chưa ánh xạ vẫn được lưu và hiển thị rỗng. Trường của loại thẻ khác hoặc sai kiểu không được chấp nhận.

Một mẫu có thể dùng chung cho nhiều loại thẻ. Mục **Đang dùng ở** dẫn đến từng lần gắn; sửa nội dung mẫu ảnh hưởng tất cả những nơi đó. Tab **Templates** tại Note Type có mapping riêng cho từng hàng cùng menu đặt mặc định, gỡ và gắn lại. Gỡ giữ thẻ và tiến độ. Để dùng cùng thiết kế nhiều lần, chọn tạo lần gắn khác trong hộp thoại; hệ thống tạo mã nội bộ.

**Lưu trữ** ẩn mẫu khỏi thư viện mặc định và chặn lần gắn mới; các nơi đang dùng vẫn hoạt động. Bật **Hiện mẫu lưu trữ** trong thư viện để tìm lại, rồi **Bỏ lưu trữ** nếu muốn gắn thêm. Lưu trữ không khóa việc sửa nội dung hiện có và không tự phát hành mẫu độc lập.

## 9. Lịch sử và khôi phục

Mở menu trang Template → **Lịch sử**. Chọn phiên bản để so sánh với nội dung đang soạn; **Khôi phục phiên bản này → Khôi phục** thay bản nháp bằng nội dung cũ và tạo phiên bản mới. Lịch sử trước đó, thẻ và tiến độ được giữ lại. Đổi nội dung hoặc schema tạo phiên bản; chỉ đổi tên hoặc lưu nội dung không đổi thì không tạo thêm phiên bản.

Nếu có người hoặc tab khác vừa sửa mẫu, lưu có thể báo mẫu đã thay đổi. Giữ lại nội dung cần thiết trước khi chọn **Tải lại**; hệ thống không tự ghi đè bằng bản nháp cũ.

## 10. Bản nhận marketplace và phát hành

Ở menu bộ thẻ đã cài, mở **Kiểu thẻ → Sửa giao diện** để đến **Mẫu thẻ đã nhận**, rồi chọn bản nhận cần sửa. Bản nhận cũng xuất hiện dưới bộ lọc **Marketplace** trong thư viện. Mỗi tài khoản chỉ có một bản nhận cho một mẫu nguồn, dùng chung qua các bộ thẻ đã cài và loại thẻ của bạn. Sửa bản nhận không thay mẫu của tác giả hoặc của người học khác.

Khi có bản mới, chọn **Xem cập nhật**. Nếu có xung đột, chọn **Giữ bản của tôi** hoặc **Lấy bản của tác giả** cho từng phần rồi **Áp dụng cập nhật**. **Dùng lại bản đã nhận** thay nội dung riêng bằng bản phát hành đang áp dụng, giữ nguyên bản nhận và lịch sử; thao tác này không lấy bản nháp chưa đăng của tác giả. Các thao tác thay nguồn sẽ thay cả nội dung chưa lưu trong trình soạn.

Tác giả có **Tự động đăng bản mới** và **Đăng bản mới nhất**; bản nhận có **Tự động kế thừa**. Cả hai tùy chọn tự động mặc định tắt. Phát hành dùng nội dung đã lưu. Bạn có thể dùng mẫu đã nhận hợp lệ từ bộ thẻ trả phí trong các loại thẻ của mình, nhưng không thể phát hành lại nguồn marketplace đó thành mẫu của tác giả mới. Màn hình hiện tại không cung cấp chợ mua bán mẫu độc lập.

## 11. Chuẩn bị phiên học

Trước một phiên mới, **Chuẩn bị phiên học** cho phép chọn một **Template cho phiên này** và **Ánh xạ dữ liệu**. Chọn **Để trống** nếu không dùng input; kể cả input được khuyến nghị cũng không chặn **Bắt đầu học**. Trường đã lưu không còn phù hợp sẽ được bỏ trống kèm lời nhắc để bạn chọn lại.

**Ghi nhớ cho bộ thẻ này** lưu riêng lựa chọn và ánh xạ cá nhân. Khi bật, bạn có thể tắt **Luôn hỏi trước khi học** để dùng lại một lựa chọn hợp lệ cho phiên sau. Nếu không ghi nhớ, lựa chọn chỉ áp dụng cho phiên này và không đổi cài đặt đã lưu. Lỗi lưu tùy chọn giữ form để **Thử lại**.

Phiên đang học hoặc được khôi phục tiếp tục dùng nội dung và ánh xạ đã chốt khi mở phiên, kể cả mẫu hoặc tùy chọn cá nhân thay đổi sau đó. Ánh xạ cá nhân không sửa ánh xạ dùng chung của loại thẻ. Input dạng danh sách field chưa thuộc phiên bản này.

## 12. Preview và kiểm chứng qua MCP

Chat đọc `get_flama_documentation(topic="template-authoring")` để lấy contract và `topic="quiz-template"` để lấy recipe trắc nghiệm đã dùng trong bộ test browser. Hai topic cũng có qua `flama://docs/template-authoring` và `flama://docs/quiz-template`.

`preview_note_type_template` chỉ đọc, nhận raw candidate với `input_schema`, `front_html`, `back_html`, `shared_css`, `sample_values`; hoặc `note_type_id` của mình cùng `application_id` xác định đúng lần gắn và mapping. Trong trường hợp gắn sẵn, sample được key theo tên field nguồn. V1 chưa đọc note thật hoặc preview trong installed/pinned context: dùng raw candidate với sample rõ ràng. `template_id` đơn lẻ không đủ chọn occurrence.

Kết quả có candidate hash, ABI, diagnostics và artifact cùng đường render client của Study. Các trạng thái `study_browser=not_run`, `interaction=not_run` cho biết server chưa thao tác browser. `preview_note_type_update` vẫn là phân tích tác động và token xác nhận; analyzer cũng kiểm tra candidate trước khi ghi. Preview không thay thế token hay confirmation của mutation.

Khi host hỗ trợ MCP Apps và deployment bật UI, người dùng có thể mở Front/Back, chọn đáp án, xem lỗi sandbox rồi bấm **Send report to chat**. Báo cáo chứa candidate hash, mặt thẻ, lỗi và ghi chú người dùng. GPT nhận báo cáo qua bridge; không tự đọc DOM hoặc tự click. Nếu host chỉ hỗ trợ cập nhật context, gửi tin nhắn tiếp trong chat để yêu cầu review. Không có browser runner theo từng cuộc chat trong v1.

Recipe quiz dùng `options` và `correct_answers` là list phẳng, đáp án là vị trí chuỗi bắt đầu từ 1, ví dụ `["1", "3"]`. Preview với `profile="quiz"` kiểm tra rỗng, trùng, ngoài khoảng và kiểu item. Khi chọn đúng N mục, recipe hiện đúng/sai; thay lựa chọn sẽ tính lại, chọn thiếu/thừa thì chưa chấm. Back hiển thị đáp án và explanation hoặc nội dung dự phòng. Đổi thứ tự options phải cập nhật vị trí đáp án; validation không biết ý nghĩa câu trả lời. Logic này không đổi điểm scheduler.

### Build, kiểm thử và bật inline UI

Chạy từ repo trên Windows:

```powershell
cd frontend
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe scripts/build_template_browser_fixtures.py
cd frontend
npx playwright install chromium
npm run test:template-browser
```

Build tạo SPA và `frontend/dist-mcp/index.html` tự chứa mã app, CSS, renderer host. Docker đóng gói cả hai; CI chạy browser fixtures bằng compiler chuẩn. Browser profile của Playwright tách biệt profile cá nhân. Report ở `output/template-browser/report.json`, evidence theo candidate/ABI/viewport và ảnh/trace khi thất bại.

`MCP_TEMPLATE_PREVIEW_UI_ENABLED=false` mặc định giữ text/structured preview. Sau khi kiểm tra host thật cho phép nested `srcdoc` sandbox và CSP tương ứng, đặt `true`, cấu hình `PUBLIC_APP_URL` trỏ đúng web origin phục vụ media rồi restart Flask/Connect. Với VPS deploy qua GitHub, đặt flag trong Variables của Environment Flama để managed env giữ giá trị qua các lần deploy. Docker và VPS release đều mang theo `frontend/dist-mcp/index.html`; VPS chỉ build resource này trên runner. Registry chỉ advertise UI khi flag bật và bundle tồn tại. Resource không chứa dữ liệu người dùng hay credential.

Khi SPA và backend khác origin, đặt `MCP_TEMPLATE_PREVIEW_MEDIA_BASE_URL` thành origin backend phục vụ `/media`, ví dụ `https://api.flama.vn`; `PUBLIC_APP_URL` tiếp tục trỏ tới SPA cho các luồng web/email. VPS managed env có cấu hình origin media riêng này.

Host simulator không chứng minh ChatGPT host đã chạy được inline UI. Media riêng tư qua cookie trong host khác origin cũng cần kiểm tra riêng. Có thể tắt flag để rollback advertisement mà giữ tool preview và luồng ghi hiện hành.
