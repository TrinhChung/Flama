# Gõ cách đọc

Nhìn từ, gõ kana, pinyin hoặc phiên âm; mặt sau xem nghĩa và ví dụ. Mẫu 1.3.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Mặt sau giữ nguyên vị trí từ và cùng kích thước thẻ với mặt trước. Cách đọc nằm dưới từ; nghĩa ngay dưới cách đọc, tiếp đến giải thích và ví dụ kèm bản dịch. Phần thông tin không truyền vào tự ẩn.

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. Các input còn lại bổ sung thông tin ở mặt sau; để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| PromptText | text | Từ / cụm từ (cần ánh xạ). |
| Answer | array | Cách đọc cần gõ (cần ánh xạ). |
| Meaning | array | Nghĩa ngắn gọn · mặt sau (tùy chọn, trống tự ẩn). |
| Explanation | richtext | Giải thích nghĩa · mặt sau (tùy chọn, trống tự ẩn). |
| Example | richtext | Ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| ExampleTranslation | richtext | Bản dịch ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| Audio | audio | Phát âm · tự phát ở mặt sau (tùy chọn, trống tự ẩn). |
| ExampleAudio | audio | Âm thanh của ví dụ · mặt sau (tùy chọn). |
| Usage | richtext | Cách sử dụng / lưu ý ngữ cảnh (tùy chọn). |
| UsageTranslation | richtext | Giải thích cách dùng bằng ngôn ngữ khác (tùy chọn, độc lập với Usage). |
| Notes | richtext | Ghi chú bổ sung (tùy chọn). |

Mặt trước kiểm tra đáp án và mở gợi ý từng ô ký tự. Mặt sau là phần ôn lại: cách đọc và thông tin được truyền vào; không hiển thị lại kết quả đúng/sai. Bố cục mặt sau gọn: từ và đáp án ở đầu, thông tin chia bằng đường phân cách nhẹ; ví dụ và bản dịch nằm cùng một khối. Khối null, trống hoặc không ánh xạ tự ẩn, gồm cả tiêu đề của khối đó. Nếu chưa có Answer, ô gõ ẩn và báo thiếu đáp án.

Đáp án ngắn hiện ô ký tự tách theo từ: **con vịt** có hai nhóm, mỗi nhóm ba ô. Nếu bất kỳ đáp án nào dài hơn **32 ký tự** (không tính khoảng trắng) hoặc **6 từ**, mẫu tự dùng một khối gợi ý nhỏ và ô nhập nhiều dòng, cao tối đa 216 px. Ngưỡng và cách gợi ý có thể sửa trực tiếp trong JS/CSS của template. Mẫu nghe dùng được cho cả từ và đoạn văn.

Chỉ cần gõ đúng **một đáp án hoàn chỉnh** trong Answer là đúng; không cần nhập tất cả các nghĩa. Mỗi dòng/mục array là một đáp án hoàn chỉnh, nên bản chép đoạn văn đặt trong một mục. Khoảng trắng và xuống dòng khi gõ được chuẩn hóa. Ô ngắn dùng Enter để kiểm tra; ô dài dùng Enter để xuống dòng, **Ctrl/⌘ + Enter** hoặc nút **Kiểm tra** để gửi. Gợi ý đoạn dài mở tám ký tự mỗi lần cho đến hết đáp án; khối gợi ý giữ giới hạn chiều cao và cuộn nội dung bên trong. Khi sai, ô dài giữ vị trí con trỏ để sửa nội dung.

## Ánh xạ tham khảo

- **Tiếng Nhật · Flama Default**: PromptText → word, Answer → reading, Meaning → translation_vi, Explanation → meaning_vi, Example → example_jp, ExampleTranslation → example_vi, Audio → word_audio.
- **Tiếng Anh · Advanced Vocabulary**: PromptText → Vocabulary, Answer → Pronunciation, Meaning → Meaning, Example → Example, ExampleTranslation → Example_VI, Audio → Vocabulary_Audio.
- **Tiếng Trung**: PromptText → Hanzi, Answer → Pinyin, Meaning → Meaning.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa; dấu tiếng Việt, dấu thanh pinyin và dấu câu vẫn cần đúng. Enter không gửi khi IME đang ghép ký tự. Gợi ý mở được đến ký tự cuối cùng, sau đó nút gợi ý tắt; khi đúng, hiển thị đáp án khớp với nội dung đã gõ.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.

## Âm thanh và thông tin tùy chọn ở mặt sau

`Audio` giữ nguyên input cũ: âm từ đối với ba mẫu từ vựng, âm đoạn nghe đối với
chép chính tả. `ExampleAudio` là input mới cho âm ví dụ. Khi lật, template dùng
thứ tự của Flama Default: **Audio → nghỉ 500 ms → ExampleAudio**, một lần.
Nếu chỉ có ExampleAudio thì phát ví dụ ngay. Nếu một field có nhiều clip thì
phát hết các clip theo thứ tự trước khi chuyển sang field tiếp theo.

Nút loa nằm cạnh từ/đáp án và cạnh ví dụ; mẫu chép chính tả giữ nút nghe của mặt
trước. Bấm nghe lại chỉ phát field đã chọn và hủy phần tự phát đang chờ. Rời thẻ
hoặc ẩn trang sẽ dừng âm thanh. Nếu trình duyệt chặn tự phát, bấm nút nghe để
phát lại; thẻ vẫn hoạt động bình thường.

Không cần ánh xạ Audio, ExampleAudio, Usage, UsageTranslation hoặc Notes nếu
không dùng. Mỗi phần trống/null/không ánh xạ tự ẩn; bản dịch ví dụ và giải thích
cách dùng vẫn hiển thị độc lập khi phần ngôn ngữ đích không được truyền vào.

Với **Flama Default**, ánh xạ tùy chọn: Audio → word_audio, Example → example_jp,
ExampleTranslation → example_vi, ExampleAudio → example_audio, Usage → usage_jp,
UsageTranslation → usage_vi, Notes → additional_note_jp. Với **Advanced Vocabulary**,
Example → Example, ExampleTranslation → Example_VI, ExampleAudio → Example_Audio,
Audio → Vocabulary_Audio. Usage và Notes nhận richtext; tạo field richtext nếu
note type đang dùng chỉ có ghi chú dạng text. Tất cả phát âm dùng media được
Flama render sẵn; template không cần backend bổ sung xử lý hoặc phân tách dữ liệu.
