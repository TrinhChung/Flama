# Prototype: Gõ đáp án

Lưu ngày 2026-10-11, giữ nguyên HTML, JavaScript và CSS người dùng cung cấp.

| File | Nội dung |
| --- | --- |
| [prototype.json](prototype.json) | Cấu trúc note type, input của template, ánh xạ theo tên trường và dữ liệu ví dụ. |
| [front.html](front.html) | Mặt trước: câu hỏi, ô gõ, nút Kiểm tra, nút Gợi ý và script xử lý. |
| [back.html](back.html) | Mặt sau: câu hỏi và đáp án. |
| [style.css](style.css) | CSS dùng chung cho hai mặt. |

## Cấu trúc

| Trường / input | Kiểu | Nội dung |
| --- | --- | --- |
| `Prompt` | `text` | Câu hỏi hiển thị trên cả hai mặt. |
| `Answer` | `array` | Danh sách đáp án được chấp nhận; nhập mỗi đáp án trên một dòng. |

Ví dụ: `Prompt` = “食べる nghĩa là gì?”, `Answer` gồm hai dòng “ăn” và “ăn uống”. Gõ đúng một đáp án bất kỳ là hợp lệ. Template cũng có thể ánh xạ input `Answer` vào trường `text` có đáp án theo dòng; gợi ý luôn lấy đáp án đầu tiên.

## Dùng lại trong Flama

1. Tạo note type với hai trường trong `note_type.field_defs` của `prototype.json`.
2. Tạo template với hai input trong `template.input_schema`.
3. Dán nguyên nội dung `front.html` vào Mặt trước, `back.html` vào Mặt sau và `style.css` vào CSS dùng chung.
4. Gắn template vào note type và ánh xạ `Prompt` → trường `Prompt`, `Answer` → trường `Answer`.
5. Thêm note với câu hỏi và các đáp án; mở thẻ để gõ, kiểm tra hoặc xem gợi ý.

`prototype.json` là bản mô tả lưu trữ. `template.source_files` chỉ đường dẫn đến các file trong thư mục này; khi dựng payload API phải đọc nội dung file vào `front_html`, `back_html`, `shared_css`. `input_bindings_by_field_name` lưu tên dễ đọc; API gắn template dùng ID thật của từng FieldDef trong `input_bindings`.

## Hành vi của mẫu

- Nhấn Enter hoặc Kiểm tra để so đáp án sau khi chuẩn hóa NFC, gộp khoảng trắng và chuyển về chữ thường; dấu tiếng Việt vẫn phải đúng.
- Gợi ý mở từng ký tự của đáp án đầu tiên, dừng khi còn một ký tự chưa mở. Trả lời đúng sẽ hiện đầy đủ đáp án đầu tiên.
- Enter trong lúc đang ghép ký tự bằng IME chưa kích hoạt kiểm tra.
- Khi không có đáp án, phần ô gõ và các nút được ẩn.
- Script có nhánh tự tạo ô nhập nếu bộ lọc template của server cũ đã bỏ thẻ `input`.

Mẫu tự kiểm tra bằng JavaScript; người học vẫn lật thẻ và chọn mức đánh giá trong màn học của Flama.
