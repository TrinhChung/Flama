# Backup: Grammar & Literary Quotes Card

Bản chụp ngày 2026-10-11 từ DB của user 1: note type **文法N1**, template **Grammar & Literary Quotes Card**. HTML, JavaScript và CSS giữ nguyên nội dung DB.

| File | Nội dung |
| --- | --- |
| [prototype.json](prototype.json) | Metadata, cấu trúc trường, schema hiệu lực, ánh xạ theo tên, ID nguồn và SHA-256. |
| [front.html](front.html) | Mặt trước hiển thị name. |
| [back.html](back.html) | Nghĩa, cấu trúc, ghi chú, ví dụ, trích dẫn văn học, nguồn và âm thanh. |
| [style.css](style.css) | CSS dùng chung cho hai mặt. |

## Cấu trúc note type

Thứ tự trong bảng khớp `position` 0–14 trong DB. `name` bắt buộc và có `identity_role = primary`; các trường còn lại không bắt buộc.

| Trường | Kiểu |
| --- | --- |
| `name` | `text` |
| `meaning` | `richtext` |
| `structure` | `text` |
| `notes` | `text` |
| `additional_example` | `richtext` |
| `example_vi` | `richtext` |
| `literary_example.quote` | `richtext` |
| `literary_example.work` | `richtext` |
| `literary_example.author` | `richtext` |
| `literary_example.translation` | `richtext` |
| `Audio` | `audio` |
| `Example_Audio` | `audio` |
| `Literary_Audio` | `audio` |
| `note_jp` | `text` |
| `note_vi` | `text` |

Giữ nguyên cả dấu chấm và chữ hoa/thường trong tên trường khi tạo note và ánh xạ input. Các key `literary_example.*` là tên trường đầy đủ trong DB.

DB chưa khai báo input schema riêng (`null`, schema của phiên bản là `[]`). `template.input_schema` lưu 15 input được suy ra bằng `infer_input_schema` của ứng dụng, với `required = false`. Schema gốc được giữ trong `source`; quy tắc bắt buộc của note nằm trong `note_type.field_defs`.

## Dùng lại

1. Tạo note type với `note_type.field_defs`, giữ tên, kiểu, thứ tự và identity của `name`.
2. Tạo template với `template.input_schema` và nội dung ba file HTML/CSS.
3. Gắn template vào note type, ánh xạ theo `input_bindings_by_field_name` và đặt làm mẫu mặc định.

Khi dựng payload API, đọc các file trong `template.source_files` vào `front_html`, `back_html`, `shared_css`; thay tên trường trong ánh xạ bằng ID FieldDef của note type đích. ID và application trong `source` ghi lại bản DB được xuất. Dữ liệu ví dụ dùng để thử mẫu.
