# Gõ chép chính tả

Nhấn nghe và chép lại theo từng từ; mặt sau đọc bản dịch và ghi chú nếu có. Mẫu 2.0.0, ngày 2026-10-11. [Xem thử cả hai mặt thẻ](../typing-preview.html).

Chỉ cần ánh xạ **hai input đầu tiên** để dùng. Các input còn lại bổ sung thông tin ở mặt sau; để không ánh xạ nếu không cần.

| Input | Kiểu | Vai trò |
| --- | --- | --- |
| Audio | audio | Âm thanh cần nghe (cần ánh xạ). |
| Answer | array | Nội dung cần chép (cần ánh xạ). |
| Translation | richtext | Bản dịch · mặt sau (tùy chọn, trống tự ẩn). |
| Notes | richtext | Ghi chú · mặt sau (tùy chọn, trống tự ẩn). |
| BackImage | image | Ảnh minh họa · mặt sau (tùy chọn, trống tự ẩn). |

Mặt trước dành cho **nghe và gõ một đoạn dài**. Mỗi từ là một cụm gạch nhỏ: một gạch cho một ký tự, khoảng trắng giữa các từ giữ như trong câu. Đoạn văn dùng một nút cho mỗi từ, không tạo từng ô ký tự riêng. Nội dung dài cuộn trong khung có giới hạn chiều cao. Chỉ có **một ô nhập nhỏ** cho từ đang chọn.

Gõ đúng một từ thì từ đó hiện chữ ngay. Khi đang gõ dở, từ giữ dạng gạch; nhấn **Dấu cách**, **Enter** hoặc **Chốt từ** để chốt và tiếp tục. Từ đã chốt sai đổi thành các ký tự `x` màu đỏ. **Bấm vào từ đỏ** để đưa nội dung đã nhập vào ô gõ và sửa; khi sửa đúng, chuyển đến từ còn thiếu hoặc chưa đúng tiếp theo. Backspace trong ô trống quay lại từ trước. Có thể dán nhiều từ vào ô nhập. Nút **Làm lại** bắt đầu lại bài; nếu dán thừa từ, từ thừa vẫn hiện lỗi và có nút xóa riêng khi chọn nó.

**Mở ký tự** mở từng ký tự của từ đang chọn, đến hết từ. Gợi ý không tự điền ô nhập hoặc tính là đã gõ đúng. Dấu câu bên ngoài từ có sẵn trong đoạn, người học có thể gõ kèm hoặc bỏ qua; dấu tiếng Việt, dấu thanh pinyin, dấu nối và dấu nháy bên trong từ vẫn cần đúng. Từ viết hoa/thường được chấp nhận như nhau. Chữ Nhật/Trung không có khoảng trắng dùng `Intl.Segmenter` trong trình duyệt để tạo các đơn vị từ khi có hỗ trợ.

Mỗi mục trong array **Answer là một bản chép hoàn chỉnh**. Mẫu tự chọn bản chép phù hợp với các từ đã nhập; hoàn thành một bản chép là đủ, không ghép các từ của những bản chép khác nhau để tính đúng. Mặt sau là phần ôn lại: bản chép, bản dịch và thông tin tùy chọn; không hiển thị lại kết quả đúng/sai. Phần null, trống hoặc không ánh xạ tự ẩn. Thiếu Answer vẫn hiện thông báo, không làm hỏng thẻ.

## Ánh xạ tham khảo

- **Nghe câu**: Audio → Audio, Answer → Transcript, Translation → Translation, Notes → Notes.
- **Nghe từ · Flama Default**: Audio → word_audio, Answer → word, Translation → meaning_vi.

Input array nhận cả field text và array; mỗi dòng không trống là một đáp án/mục. Field array hiện lưu chuỗi văn bản, mỗi mục một dòng. Input richtext nhận field richtext; không ánh xạ field richtext vào Answer. Nếu transcript hiện ở field richtext, dùng thêm field text/array cho nội dung cần gõ. Tên field trong ví dụ cần đổi thành ID thật khi gọi API.

Template đọc các mục array từ ranh giới `<br>` đã được render sẵn; không dùng `.split()` hoặc tách lại dấu `;`, `$`, `/`, dấu phẩy. Kiểm tra đáp án, gợi ý và bố cục tùy chỉnh nằm hoàn toàn trong HTML/CSS/JS của template; không cần thay đổi backend.

Tiếng Nhật, Trung và Anh dùng chung bộ so sánh Unicode. NFC, chữ hoa/thường và khoảng trắng được chuẩn hóa. Dấu cách và Enter không chốt khi IME đang ghép ký tự. Âm thanh chỉ phát khi bấm nghe; có thể nghe lại, dừng hoặc phát nhiều clip nối tiếp.

Dán [front.html](front.html), [back.html](back.html), [style.css](style.css) vào template và dùng input_schema trong [prototype.json](prototype.json). Cấu trúc note_type là tham khảo; có thể gắn template vào note type hiện có. Media giữ đường dẫn proxy của Flama. CSS có light/dark, mobile và reduced motion. Mẫu đã được cài vào thư viện template cá nhân trong DB ngày 2026-10-11, nhóm **Luyện gõ**. ID template và phiên bản nằm trong database_installation của prototype.json.
