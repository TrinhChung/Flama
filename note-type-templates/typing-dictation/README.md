# Gõ chép chính tả

Nhấn nghe và chép lại theo từng từ; mặt sau đọc bản dịch và ghi chú nếu có. Mẫu 2.3.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Mặt sau dùng cùng vị trí nút nghe, kích thước thẻ và kiểu chữ đoạn văn như mặt trước. Bản dịch nằm ngay dưới bản chép; ghi chú và hình minh họa tiếp theo. Mặt sau tự phát đoạn nghe, rồi phát âm ví dụ nếu có; nút nghe lại vẫn ở cùng vị trí như mặt trước. Phần thông tin không truyền vào tự ẩn.

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. Các input còn lại bổ sung thông tin ở mặt sau; để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| Audio | audio | Âm thanh cần nghe (cần ánh xạ). |
| Answer | array | Nội dung cần chép (cần ánh xạ). |
| Translation | richtext | Bản dịch · mặt sau (tùy chọn, trống tự ẩn). |
| Notes | richtext | Ghi chú · mặt sau (tùy chọn, trống tự ẩn). |
| BackImage | image | Ảnh minh họa · mặt sau (tùy chọn, trống tự ẩn). |
| ExampleAudio | audio | Âm thanh của ví dụ · mặt sau (tùy chọn). |
| Usage | richtext | Cách sử dụng / lưu ý ngữ cảnh (tùy chọn). |
| UsageTranslation | richtext | Giải thích cách dùng bằng ngôn ngữ khác (tùy chọn, độc lập với Usage). |
| Example | richtext | Ví dụ bổ sung · mặt sau (tùy chọn). |
| ExampleTranslation | richtext | Bản dịch ví dụ · mặt sau (tùy chọn). |

Mặt trước dành cho **nghe và gõ một đoạn dài**. Mỗi từ là một cụm gạch nhỏ: một gạch cho một ký tự, khoảng trắng giữa các từ giữ như trong câu. Đoạn văn dùng một nút cho mỗi từ, không tạo từng ô ký tự riêng. Đoạn văn không có viền hay nền hộp, xuống dòng tự nhiên; đoạn rất dài cuộn trong vùng giới hạn chiều cao. Chỉ có **một ô nhập nhỏ** cho từ đang chọn.

Gõ đúng một từ thì từ đó hiện chữ và **tự chuyển sang từ tiếp theo**, không cần chốt từ. Chữ đang gõ dở đúng hướng vẫn là gạch; khi không còn khớp một từ có thể chấp nhận, từ chuyển thành `x` đỏ và ô gõ rung nhẹ một lần. Ô nhập giữ nội dung để sửa. **Bấm vào một từ** để chọn và gõ lại; sửa đúng tự chuyển đến từ chưa hoàn thành tiếp theo. **Enter** bỏ qua từ chưa biết để sửa sau; dấu cách ngay sau khi tự chuyển không bỏ qua từ. Backspace trong ô trống quay lại từ trước. Có thể dán nhiều từ, kể cả một đoạn hoàn chỉnh. **Làm lại** bắt đầu lại bài; từ dán thừa vẫn hiện lỗi và có nút xóa khi chọn nó.

**Mở ký tự** mở từng ký tự của từ đang chọn, đến hết từ. Gợi ý không tự điền ô nhập hoặc tính là đã gõ đúng. Dấu câu bên ngoài từ có sẵn trong đoạn, người học có thể gõ kèm hoặc bỏ qua; dấu tiếng Việt, dấu thanh pinyin, dấu nối và dấu nháy bên trong từ vẫn cần đúng. Từ viết hoa/thường được chấp nhận như nhau. Chữ Nhật/Trung không có khoảng trắng dùng `Intl.Segmenter` trong trình duyệt để tạo các đơn vị từ khi có hỗ trợ.

Mỗi mục trong array **Answer là một bản chép hoàn chỉnh**. Mẫu tự chọn bản chép phù hợp với các từ đã nhập; hoàn thành một bản chép là đủ, không ghép các từ của những bản chép khác nhau để tính đúng. Mặt sau là phần ôn lại: bản chép, bản dịch và thông tin tùy chọn; không hiển thị lại kết quả đúng/sai. Phần null, trống hoặc không ánh xạ tự ẩn. Thiếu Answer vẫn hiện thông báo, không làm hỏng thẻ.

## Ánh xạ tham khảo

- **Nghe câu**: Audio → Audio, Answer → Transcript, Translation → Translation, Notes → Notes.
- **Nghe từ · Flama Default**: Audio → word_audio, Answer → word, Translation → meaning_vi.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa. Không kiểm tra lỗi hay tự chuyển từ khi IME đang ghép ký tự; chỉ kiểm tra sau khi ghép xong. Mặt trước phát khi bấm ở mặt trước và tự phát ở mặt sau nghe. Mặt sau tự phát Audio rồi ExampleAudio; có thể nghe lại hoặc dừng bằng nút riêng.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.

## Dữ liệu thử

[test-data.json](test-data.json) lưu bốn mẫu đã thêm vào deck **6. Luyện gõ - Gõ chép chính tả (Dictation)**, ID 6859: ba bài tiếng Anh từ câu ngắn đến đoạn dài và một đoạn tiếng Nhật để thử IME. Mỗi note có âm thanh giọng máy khớp bản chép, bản dịch và ghi chú; âm thanh trong DB dùng media proxy của Flama. File này lưu nội dung mẫu và tên giọng, không chứa file âm thanh.

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

Audio là input cần thiết cho bài nghe. Không cần ánh xạ ExampleAudio, Usage,
UsageTranslation hoặc Notes nếu không dùng. Mỗi phần trống/null/không ánh xạ tự ẩn; bản dịch ví dụ và giải thích
cách dùng vẫn hiển thị độc lập khi phần ngôn ngữ đích không được truyền vào.

Với **Flama Default**, ánh xạ tùy chọn: Audio → word_audio, Example → example_jp,
ExampleTranslation → example_vi, ExampleAudio → example_audio, Usage → usage_jp,
UsageTranslation → usage_vi, Notes → additional_note_jp. Với **Advanced Vocabulary**,
Example → Example, ExampleTranslation → Example_VI, ExampleAudio → Example_Audio,
Audio → Vocabulary_Audio. Usage và Notes nhận richtext; tạo field richtext nếu
note type đang dùng chỉ có ghi chú dạng text. Tất cả phát âm dùng media được
Flama render sẵn; template không cần backend bổ sung xử lý hoặc phân tách dữ liệu.
