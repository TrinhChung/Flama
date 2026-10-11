# Backup: Advanced Vocabulary Card

Bản chụp ngày 2026-10-11 từ DB của user 1: note type **En4Everyone**, template **Advanced Vocabulary Card**. HTML, JavaScript và CSS giữ nguyên nội dung DB.

| File | Nội dung |
| --- | --- |
| [prototype.json](prototype.json) | Metadata, cấu trúc trường, schema hiệu lực, ánh xạ theo tên, ID nguồn và SHA-256. |
| [front.html](front.html) | Mặt trước hiển thị Vocabulary. |
| [back.html](back.html) | Từ loại, phát âm, nghĩa, ví dụ, collocation, synonym, antonym, word family, ghi chú và media. |
| [style.css](style.css) | CSS của hai mặt và bố cục các cặp nội dung. |

## Cấu trúc note type

Thứ tự trong bảng khớp `position` 0–18 trong DB. `STT` bắt buộc và có `identity_role = primary`; các trường còn lại không bắt buộc.

| Trường | Kiểu |
| --- | --- |
| `STT` | `text` |
| `Vocabulary` | `text` |
| `PoS` | `text` |
| `Pronunciation` | `text` |
| `Meaning` | `array` |
| `Example` | `richtext` |
| `Example_VI` | `richtext` |
| `Collocation` | `array` |
| `Coollocation_VI` | `array` |
| `Synonym` | `array` |
| `Synonym_VI` | `array` |
| `Antonym` | `array` |
| `Antonym_VI` | `array` |
| `Word Family` | `text` |
| `Note_EN` | `text` |
| `Note_VI` | `text` |
| `Vocabulary_Audio` | `audio` |
| `Example_Audio` | `audio` |
| `image` | `image` |

Giữ nguyên tên `Coollocation_VI` và `Word Family` như DB. Template dùng 18 input; `STT` là trường định danh của note và không được tham chiếu trên thẻ.

DB chưa khai báo input schema riêng (`null`, schema của phiên bản là `[]`). `template.input_schema` được suy ra bằng `infer_input_schema` của ứng dụng; các field `array` tạo input kiểu `text`, `required = false`. Schema gốc được giữ trong `source`. Các ví dụ trong `example_field_values` dùng danh sách JSON cho field `array`.

## Dùng lại

1. Tạo note type với `note_type.field_defs`, giữ tên, kiểu, thứ tự và identity của `STT`.
2. Tạo template với `template.input_schema` và nội dung ba file HTML/CSS.
3. Gắn template vào note type, ánh xạ theo `input_bindings_by_field_name` và đặt làm mẫu mặc định.

Khi dựng payload API, đọc các file trong `template.source_files` vào `front_html`, `back_html`, `shared_css`; thay tên trường trong ánh xạ bằng ID FieldDef của note type đích. ID và application trong `source` ghi lại bản DB được xuất. Dữ liệu ví dụ dùng để thử mẫu.
