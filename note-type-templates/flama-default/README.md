# Backup: Flama Default

Bản chụp ngày 2026-10-11 của note type **Flama Standard Vocabulary** và template **Default Flama Flashcard**, đọc trực tiếp từ DB của user 1. ID note type, template, phiên bản hiện tại, các FieldDef và ánh xạ application được lưu trong `prototype.json`.

Mặt trước và CSS giữ nguyên bản DB. Mặt sau phiên bản 1.1 đọc trực tiếp xuống dòng của array cho cách đọc/nghĩa; vùng chữ dùng layout block để `<br>` không bị gom ngang bởi flex. `source.sha256` giữ checksum của bản DB gốc, `files_sha256` mô tả các file hiện tại.

Phiên bản 1.1.1 (2026-10-19) bỏ thuộc tính `controls` trên hai audio ẩn để `.play()` đi qua trình phát chung của Flama, giống template tiếng Anh. Bản sửa đã được lưu trên server ở template version 4; ID trong `source` vẫn ghi lại bản backup gốc. Nút loa và chuỗi phát từ vựng → ví dụ sau 500 ms được giữ nguyên. Trên iPad, tải lại trang và bắt đầu phiên học mới để nhận template đã sửa.

| File | Nội dung |
| --- | --- |
| [prototype.json](prototype.json) | Metadata note type, 16 trường, input schema, ánh xạ, dữ liệu ví dụ và SHA-256 của các file template. |
| [front.html](front.html) | Mặt trước hiển thị từ vựng. |
| [back.html](back.html) | Mặt sau hiển thị cách đọc, nghĩa, cách dùng, ví dụ, ghi chú, ảnh và âm thanh. |
| [style.css](style.css) | CSS của thẻ và ảnh minh họa, gồm các kích thước màn hình. |

## Cấu trúc note type

Thứ tự bên dưới khớp `position` 0–15 trong DB. Trường `word` bắt buộc và có `identity_role = primary`; các trường còn lại không bắt buộc.

| Trường | Kiểu |
| --- | --- |
| `word` | `text` |
| `hanviet` | `text` |
| `reading` | `array` |
| `translation_vi` | `array` |
| `meaning_jp` | `richtext` |
| `meaning_vi` | `richtext` |
| `usage_jp` | `richtext` |
| `usage_vi` | `richtext` |
| `example_jp` | `richtext` |
| `example_vi` | `richtext` |
| `additional_note_jp` | `richtext` |
| `additional_note_vi` | `richtext` |
| `image` | `image` |
| `diagram` | `image` |
| `word_audio` | `audio` |
| `example_audio` | `audio` |

Trường tên `diagram` có kiểu `image` theo DB. `reading` và `translation_vi` lưu chuỗi với một phần tử mỗi dòng. Danh sách JSON trong dữ liệu ví dụ là biểu diễn để đọc; khi nhập DB, nối bằng `\n`.

DB chưa khai báo input schema riêng (`null`, schema của phiên bản là `[]`). `template.input_schema` lưu schema hiệu lực được suy ra bằng `infer_input_schema` của ứng dụng: input ứng với field `array` được suy ra thành `text`, các input có `required = false`. Quy tắc bắt buộc của note vẫn nằm trong `note_type.field_defs`. Schema gốc được giữ trong `source`.

## Dùng lại trong Flama

1. Tạo note type với các trường trong `note_type.field_defs` của `prototype.json`, giữ thứ tự, kiểu dữ liệu và identity của `word`.
2. Tạo template với `template.input_schema`.
3. Dán `front.html` vào Mặt trước, `back.html` vào Mặt sau và `style.css` vào CSS dùng chung.
4. Gắn template vào note type, ánh xạ mỗi input tới trường cùng tên và đặt làm mẫu mặc định.

`prototype.json` là bản mô tả backup. Khi dựng payload API, đọc nội dung các file trong `template.source_files` vào `front_html`, `back_html`, `shared_css`, và thay tên trường trong `input_bindings_by_field_name` bằng ID thật của FieldDef thuộc note type đích. Các ID trong `source` ghi lại nguồn DB đã xuất; metadata như `is_official` và `publish_status` cũng lấy từ DB.

Mặt sau giữ script phát âm từ vựng rồi phát âm câu ví dụ sau 500 ms. Chỉ các trường văn xuôi chưa migrate còn dùng `$` trong vùng `auto-split`; không tách lại dấu câu của array. Các phần tử array không được bọc thêm thẻ block có margin/padding.
