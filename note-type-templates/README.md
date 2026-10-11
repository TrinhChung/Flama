# Thư viện cấu trúc note type và template

Lưu các prototype để dùng lại khi tạo note type và template trong Flama. Mỗi mẫu có một thư mục riêng, chứa cấu trúc dữ liệu, mặt trước, mặt sau, CSS và hướng dẫn ánh xạ input.

| Mẫu | Nội dung |
| --- | --- |
| [Gõ đáp án](typing-answer/README.md) | Hai trường Prompt / Answer, kiểm tra đáp án và gợi ý từng ký tự bằng JavaScript. |
| [Flama Default](flama-default/README.md) | Backup từ DB: Flama Standard Vocabulary, 16 trường, template Default Flama Flashcard. |
| [Advanced Vocabulary Card](advanced-vocabulary-card/README.md) | Backup từ DB: En4Everyone, 19 trường, template từ vựng tiếng Anh. |
| [Grammar & Literary Quotes Card](grammar-literary-quotes-card/README.md) | Backup từ DB: 文法N1, 15 trường, template ngữ pháp và trích dẫn văn học. |

Các bản backup từ DB lưu HTML/CSS nguyên nội dung, nguồn và ID trong `prototype.json`, cùng SHA-256 để kiểm tra file. `example_field_values` là dữ liệu minh họa để thử mẫu.

Khi thêm mẫu mới, tạo thư mục cùng cấp với `typing-answer/` và thêm liên kết vào bảng trên.
