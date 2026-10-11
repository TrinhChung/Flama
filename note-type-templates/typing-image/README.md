# Gõ từ qua ảnh

Nhìn hình, gõ tên; mặt sau xem nghĩa, cách đọc và nghe phát âm. Mẫu 1.2.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. `DefinitionHint` bổ sung gợi ý ở mặt trước; các input tùy chọn còn lại bổ sung thông tin ở mặt sau. Để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| PromptImage | image | Ảnh cần gọi tên (cần ánh xạ). |
| Answer | array | Từ cần gõ (cần ánh xạ). |
| Meaning | array | Nghĩa · mặt sau (tùy chọn, trống tự ẩn). |
| Reading | array | Cách đọc · mặt sau (tùy chọn, trống tự ẩn). |
| Audio | audio | Phát âm · chỉ ở mặt sau (tùy chọn, trống tự ẩn). |
| DefinitionHint | richtext | Giải thích bằng ngôn ngữ đích · gợi ý mở ở mặt trước (tùy chọn, trống tự ẩn). |

Mặt trước kiểm tra đáp án và mở gợi ý từng ô ký tự. Mặt sau là phần ôn lại: từ vựng và thông tin được truyền vào; không hiển thị lại kết quả đúng/sai. Bố cục mặt sau gọn: từ và đáp án ở đầu, thông tin chia bằng đường phân cách nhẹ; phần nghe lại và hình ảnh được thu gọn. Khối null, trống hoặc không ánh xạ tự ẩn, gồm cả tiêu đề của khối đó. Nếu chưa có Answer, ô gõ ẩn và báo thiếu đáp án.

Khi chưa nhớ từ, mở **Giải thích bằng ngôn ngữ đích** để đọc định nghĩa trong `DefinitionHint`, rồi dùng **Mở ký tự** nếu cần thêm gợi ý. Nội dung mặc định đóng, có thể đóng lại; lời giải thích dài cuộn trong khối nhỏ. Null, không ánh xạ, khoảng trắng hoặc richtext rỗng như `<p><br></p>` đều ẩn cả khối. Lời giải thích không tham gia kiểm tra đáp án; `Meaning` vẫn dành cho mặt sau.

Đáp án ngắn hiện ô ký tự tách theo từ: **con vịt** có hai nhóm, mỗi nhóm ba ô. Nếu bất kỳ đáp án nào dài hơn **32 ký tự** (không tính khoảng trắng) hoặc **6 từ**, mẫu tự dùng một khối gợi ý nhỏ và ô nhập nhiều dòng, cao tối đa 216 px. Ngưỡng và cách gợi ý có thể sửa trực tiếp trong JS/CSS của template.

Chỉ cần gõ đúng **một đáp án hoàn chỉnh** trong Answer là đúng; không cần nhập tất cả các nghĩa. Mỗi dòng/mục array là một đáp án hoàn chỉnh, nên bản chép đoạn văn đặt trong một mục. Khoảng trắng và xuống dòng khi gõ được chuẩn hóa. Ô ngắn dùng Enter để kiểm tra; ô dài dùng Enter để xuống dòng, **Ctrl/⌘ + Enter** hoặc nút **Kiểm tra** để gửi. Gợi ý đoạn dài mở tám ký tự mỗi lần, tối đa 48 ký tự đầu. Khi sai, ô dài giữ vị trí con trỏ để sửa nội dung.

## Ánh xạ tham khảo

- **Tiếng Anh · Advanced Vocabulary**: PromptImage → image, Answer → Vocabulary, Meaning → Meaning, Reading → Pronunciation, Audio → Vocabulary_Audio.
- **Tiếng Nhật · Flama Default**: PromptImage → image, Answer → word, Meaning → translation_vi, Reading → reading, Audio → word_audio, DefinitionHint → meaning_jp.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa; dấu tiếng Việt, dấu thanh pinyin và dấu câu vẫn cần đúng. Enter không gửi khi IME đang ghép ký tự. Gợi ý giữ lại ký tự cuối; khi đúng, hiển thị đáp án khớp với nội dung đã gõ.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.
