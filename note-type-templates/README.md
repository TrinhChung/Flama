# Thư viện cấu trúc note type và template

Lưu các prototype để dùng lại khi tạo note type và template trong Flama. Mỗi mẫu có một thư mục riêng, chứa cấu trúc dữ liệu, mặt trước, mặt sau, CSS và hướng dẫn ánh xạ input.

| Mẫu | Nội dung |
| --- | --- |
| [Gõ cách đọc](typing-reading/README.md) | Nhìn từ, gõ kana / pinyin / phiên âm. Mặt sau xem nghĩa và ví dụ. |
| [Gõ nghĩa](typing-meaning/README.md) | Nhìn từ, gõ nghĩa. Mặt sau xem cách đọc và ví dụ. |
| [Gõ từ qua ảnh](typing-image/README.md) | Nhìn ảnh, gõ tên. Mặt sau xem nghĩa và cách đọc. |
| [Gõ chép chính tả](typing-dictation/README.md) | Nhấn nghe rồi chép lại. Mặt sau xem bản dịch và ghi chú. |
| [Gõ đáp án — prototype ban đầu](typing-answer/README.md) | Bản người dùng cung cấp, giữ nguyên để tham khảo. |
| [Flama Default](flama-default/README.md) | Backup từ DB: Flama Standard Vocabulary, 16 trường, template Default Flama Flashcard. |
| [Advanced Vocabulary Card](advanced-vocabulary-card/README.md) | Backup từ DB: En4Everyone, 19 trường, template từ vựng tiếng Anh. |
| [Grammar & Literary Quotes Card](grammar-literary-quotes-card/README.md) | Backup từ DB: 文法N1, 15 trường, template ngữ pháp và trích dẫn văn học. |

[Xem và thử cả mặt trước / mặt sau](typing-preview.html): chép chính tả, kanji → cách đọc, từ → nghĩa, ảnh → từ vựng, Hán tự → pinyin, cụm hai từ và nghe đoạn văn. Preview mở trực tiếp trong trình duyệt, có sẵn âm thanh và hình minh họa.

Bốn mẫu mới tách theo mục đích học. Mỗi mẫu chỉ cần ánh xạ hai input đầu tiên; các input còn lại dành cho thông tin tùy chọn ở mặt sau. Tiếng Nhật, Trung và Anh dùng chung template khi dữ liệu cùng kiểu. Không phải truyền toàn bộ input: phần null, trống hoặc không ánh xạ tự ẩn cùng tiêu đề.

Ô gõ tự thích ứng: đáp án ngắn dùng ô ký tự tách theo từ; đáp án dài dùng một khối gợi ý nhỏ và ô nhập nhiều dòng có giới hạn chiều cao. Chỉ cần gõ đúng một mục hoàn chỉnh trong array Answer là được. Mẫu nghe dùng chung cho từ, câu hoặc đoạn văn; phần xử lý nằm trong HTML/CSS/JS của template.

Chữ dùng input text, danh sách đáp án/nghĩa/cách đọc dùng array, ảnh dùng image và âm thanh dùng audio. Mặt trước báo đúng/sai; mặt sau là phần thông tin ôn tập, gồm đáp án hoặc bản chép và dữ liệu bổ sung được truyền vào. Các trường nghĩa, giải thích và ví dụ tham khảo ba template đã backup; không cần tạo đầy đủ trường của chúng để dùng mẫu gõ.

Các bản backup từ DB lưu HTML/CSS nguyên nội dung, nguồn và ID trong `prototype.json`, cùng SHA-256 để kiểm tra file. Bốn mẫu gõ mới được soạn trong thư viện và đã cài vào DB ngày 2026-10-11, nhóm **Luyện gõ**. Tìm trong trang `/card-templates`; ID template và phiên bản được ghi tại database_installation của từng prototype.json. `example_field_values` là dữ liệu minh họa để thử mẫu.

Khi thêm mẫu mới, tạo thư mục cùng cấp với `typing-answer/` và thêm liên kết vào bảng trên.
