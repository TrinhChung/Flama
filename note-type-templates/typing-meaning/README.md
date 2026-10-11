# Gõ nghĩa

Nhìn từ, gõ nghĩa; mặt sau xem cách đọc, giải thích và ví dụ. Mẫu 1.2.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. `DefinitionHint` bổ sung gợi ý ở mặt trước; các input tùy chọn còn lại bổ sung thông tin ở mặt sau. Để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| PromptText | text | Từ / cụm từ (cần ánh xạ). |
| Answer | array | Một hoặc nhiều nghĩa được chấp nhận; gõ đúng một mục là đủ (cần ánh xạ). |
| Reading | array | Cách đọc · mặt sau (tùy chọn, trống tự ẩn). |
| Explanation | richtext | Giải thích · mặt sau (tùy chọn, trống tự ẩn). |
| Example | richtext | Ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| ExampleTranslation | richtext | Bản dịch ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| Audio | audio | Phát âm · chỉ ở mặt sau (tùy chọn, trống tự ẩn). |
| DefinitionHint | richtext | Giải thích bằng ngôn ngữ đích · gợi ý mở ở mặt trước (tùy chọn, trống tự ẩn). |

Mặt trước dùng **một ô input thông thường**, không hiện ô ký tự, số ký tự hoặc số từ. Các nghĩa có thể dài ngắn khác nhau mà không làm thay đổi kiểu ô nhập. Mặt sau là phần ôn lại: nghĩa và thông tin được truyền vào; không hiển thị lại kết quả đúng/sai. Khối null, trống hoặc không ánh xạ tự ẩn, gồm cả tiêu đề của khối đó. Nếu chưa có Answer, ô gõ ẩn và báo thiếu đáp án.

Khi chưa nhớ nghĩa, mở **Giải thích bằng ngôn ngữ đích** để đọc nội dung `DefinitionHint`. Ví dụ, từ tiếng Nhật có thể truyền lời giải thích tiếng Nhật, còn từ tiếng Anh truyền định nghĩa tiếng Anh. Gợi ý mặc định đóng, có thể đóng lại; nội dung dài cuộn trong khối nhỏ. Không có dữ liệu, kể cả richtext rỗng như `<p><br></p>`, thì cả khối tự ẩn. `Explanation` vẫn là thông tin mặt sau, độc lập với gợi ý này.

Nếu vẫn chưa nhớ, bấm **Mở ký tự** để mở từng ký tự đầu của **nghĩa đầu tiên** trong Answer, chẳng hạn `h…` rồi `họ…`. Gợi ý không hiển thị số ô trống hoặc tổng độ dài; tối đa 48 ký tự đầu và giữ ký tự cuối chưa mở. Dù gợi ý lấy từ nghĩa đầu tiên, nhập đúng bất kỳ mục hoàn chỉnh nào trong Answer vẫn được chấp nhận. Ví dụ `học` và `học tập` là hai mục thay thế, không cần gõ cả hai. **Enter** hoặc **Kiểm tra** để gửi; khi sai giữ vị trí con trỏ để sửa.

## Ánh xạ tham khảo

- **Tiếng Nhật · Flama Default**: PromptText → word, Answer → translation_vi, Reading → reading, Explanation → meaning_vi, Example → example_jp, ExampleTranslation → example_vi, Audio → word_audio, DefinitionHint → meaning_jp.
- **Tiếng Anh · Advanced Vocabulary**: PromptText → Vocabulary, Answer → Meaning, Reading → Pronunciation, Example → Example, ExampleTranslation → Example_VI, Audio → Vocabulary_Audio.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa; dấu tiếng Việt, dấu thanh pinyin và dấu câu vẫn cần đúng. Enter không gửi khi IME đang ghép ký tự. Chỉ nội dung Answer tham gia so sánh; lời giải thích không phải đáp án.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.
