# Gõ cách đọc

Nhìn từ, gõ kana, pinyin hoặc phiên âm; mặt sau xem nghĩa và ví dụ. Mẫu 1.0.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. Các input còn lại bổ sung thông tin ở mặt sau; để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| PromptText | text | Từ / cụm từ (cần ánh xạ). |
| Answer | array | Cách đọc cần gõ (cần ánh xạ). |
| Meaning | array | Nghĩa ngắn gọn · mặt sau (tùy chọn, trống tự ẩn). |
| Explanation | richtext | Giải thích nghĩa · mặt sau (tùy chọn, trống tự ẩn). |
| Example | richtext | Ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| ExampleTranslation | richtext | Bản dịch ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| Audio | audio | Phát âm · chỉ ở mặt sau (tùy chọn, trống tự ẩn). |

Mặt trước kiểm tra đáp án và mở gợi ý từng ô ký tự. Mặt sau là phần ôn lại: cách đọc và thông tin được truyền vào; không hiển thị lại kết quả đúng/sai. Khối null, trống hoặc không ánh xạ tự ẩn, gồm cả tiêu đề của khối đó. Nếu chưa có Answer, ô gõ ẩn và báo thiếu đáp án.

## Ánh xạ tham khảo

- **Tiếng Nhật · Flama Default**: PromptText → word, Answer → reading, Meaning → translation_vi, Explanation → meaning_vi, Example → example_jp, ExampleTranslation → example_vi, Audio → word_audio.
- **Tiếng Anh · Advanced Vocabulary**: PromptText → Vocabulary, Answer → Pronunciation, Meaning → Meaning, Example → Example, ExampleTranslation → Example_VI, Audio → Vocabulary_Audio.
- **Tiếng Trung**: PromptText → Hanzi, Answer → Pinyin, Meaning → Meaning.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa; dấu tiếng Việt, dấu thanh pinyin và dấu câu vẫn cần đúng. Enter không gửi khi IME đang ghép ký tự. Gợi ý giữ lại ký tự cuối; khi đúng, hiển thị đáp án khớp với nội dung đã gõ.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.
