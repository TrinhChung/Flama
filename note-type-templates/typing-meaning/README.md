# Gõ nghĩa

Nhìn từ, gõ nghĩa; mặt sau xem cách đọc, giải thích và ví dụ. Mẫu 1.4.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Mặt sau giữ nguyên vị trí từ và cùng kích thước thẻ với mặt trước. Cách đọc ở ngay dưới từ nếu có; nghĩa và các cách diễn đạt khác tiếp theo, rồi đến giải thích và ví dụ kèm bản dịch. Phần thông tin không truyền vào tự ẩn.

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. `DefinitionHint` bổ sung gợi ý ở mặt trước; các input tùy chọn còn lại bổ sung thông tin ở mặt sau. Để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| PromptText | text | Từ / cụm từ (cần ánh xạ). |
| Answer | array | Một hoặc nhiều nghĩa được chấp nhận; gõ đúng một mục là đủ (cần ánh xạ). |
| Reading | array | Cách đọc · mặt sau (tùy chọn, trống tự ẩn). |
| Explanation | richtext | Giải thích · mặt sau (tùy chọn, trống tự ẩn). |
| Example | richtext | Ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| ExampleTranslation | richtext | Bản dịch ví dụ · mặt sau (tùy chọn, trống tự ẩn). |
| Audio | audio | Phát âm · tự phát ở mặt sau (tùy chọn, trống tự ẩn). |
| DefinitionHint | richtext | Giải thích bằng ngôn ngữ đích · gợi ý mở ở mặt trước (tùy chọn, trống tự ẩn). |
| ExampleAudio | audio | Âm thanh của ví dụ · mặt sau (tùy chọn). |
| Usage | richtext | Cách sử dụng / lưu ý ngữ cảnh (tùy chọn). |
| UsageTranslation | richtext | Giải thích cách dùng bằng ngôn ngữ khác (tùy chọn, độc lập với Usage). |
| Notes | richtext | Ghi chú bổ sung (tùy chọn). |

Mặt trước dùng **một ô input thông thường**, không hiện ô ký tự, số ký tự hoặc số từ. Các nghĩa có thể dài ngắn khác nhau mà không làm thay đổi kiểu ô nhập. Mặt sau là phần ôn lại: nghĩa và thông tin được truyền vào; không hiển thị lại kết quả đúng/sai. Khối null, trống hoặc không ánh xạ tự ẩn, gồm cả tiêu đề của khối đó. Nếu chưa có Answer, ô gõ ẩn và báo thiếu đáp án.

Khi chưa nhớ nghĩa, mở **Giải thích bằng ngôn ngữ đích** để đọc nội dung `DefinitionHint`. Ví dụ, từ tiếng Nhật có thể truyền lời giải thích tiếng Nhật, còn từ tiếng Anh truyền định nghĩa tiếng Anh. Gợi ý mặc định đóng, có thể đóng lại; nội dung dài cuộn trong khối nhỏ. Không có dữ liệu, kể cả richtext rỗng như `<p><br></p>`, thì cả khối tự ẩn. `Explanation` vẫn là thông tin mặt sau, độc lập với gợi ý này.

Nếu vẫn chưa nhớ, bấm **Mở ký tự** để mở từng ký tự đầu của **nghĩa đầu tiên** trong Answer, chẳng hạn `h…` rồi `họ…`. Gợi ý không hiển thị số ô trống hoặc tổng độ dài; mở được đến ký tự cuối cùng. Khi mở hết, dấu ba chấm biến mất và nút gợi ý tắt; nội dung dài cuộn trong khối có giới hạn chiều cao. Dù gợi ý lấy từ nghĩa đầu tiên, nhập đúng bất kỳ mục hoàn chỉnh nào trong Answer vẫn được chấp nhận. Ví dụ `học` và `học tập` là hai mục thay thế, không cần gõ cả hai. **Enter** hoặc **Kiểm tra** để gửi; khi sai giữ vị trí con trỏ để sửa.

## Ánh xạ tham khảo

- **Tiếng Nhật · Flama Default**: PromptText → word, Answer → translation_vi, Reading → reading, Explanation → meaning_vi, Example → example_jp, ExampleTranslation → example_vi, Audio → word_audio, DefinitionHint → meaning_jp.
- **Tiếng Anh · Advanced Vocabulary**: PromptText → Vocabulary, Answer → Meaning, Reading → Pronunciation, Example → Example, ExampleTranslation → Example_VI, Audio → Vocabulary_Audio.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa; dấu tiếng Việt, dấu thanh pinyin và dấu câu vẫn cần đúng. Enter không gửi khi IME đang ghép ký tự. Chỉ nội dung Answer tham gia so sánh; lời giải thích không phải đáp án.

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
