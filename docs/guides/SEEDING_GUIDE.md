# Hướng Dẫn Chi Tiết Về Seeding & Dữ Liệu Mẫu (Flama Seeding Guide)

Tài liệu này cung cấp hướng dẫn toàn diện về cơ chế seeding (khởi tạo dữ liệu mẫu), các lệnh CLI, cấu trúc thư mục học liệu và quy trình nạp dữ liệu vào cơ sở dữ liệu của dự án Flama.

---

## 📑 Mục Lục
1. [Tổng Quan Về Kiến Trúc Seeding](#1-tổng-quan-về-kiến-trúc-seeding)
2. [Các Kịch Bản Reseed Nhanh (One-Click Scripts)](#2-các-kịch-bản-reseed-nhanh-one-click-scripts)
3. [Chi Tiết Các Lệnh CLI Seeding](#3-chi-tiết-các-lệnh-cli-seeding)
4. [Cấu Trúc Thư Mục Dữ Liệu Mẫu (`static/seed_data/`)](#4-cấu-trúc-thư-mục-dữ-liệu-mẫu-staticseed_data)
5. [Quy Chuẩn Định Dạng File Seed (CSV / TSV / TXT)](#5-quy-chuẩn-định-dạng-file-seed-csv--tsv--txt)
6. [Quản Lý & Nạp Dữ Liệu Qua Giao Diện Admin](#6-quản-lý--nạp-dữ-liệu-qua-giao-diện-admin)
7. [Khắc Phục Sự Cố & Câu Hỏi Thường Gặp (FAQs)](#7-khắc-phục-sự-cố--câu-hỏi-thường-gặp-faqs)

---

## 1. Tổng Quan Về Kiến Trúc Seeding

Hệ thống Seeding của Flama được thiết kế theo các nguyên tắc:
- **Idempotent (Không nhân bản dữ liệu)**: Các lệnh seed kiểm tra sự tồn tại của bản ghi trước khi tạo mới hoặc cập nhật, đảm bảo có thể chạy lại nhiều lần mà không sinh lỗi trùng lặp.
- **Thứ tự phụ thuộc dữ liệu chuẩn xác**:
  $$\text{Migrations} \rightarrow \text{Note Types / Templates} \rightarrow \text{User Roles} \rightarrow \text{TTS Providers} \rightarrow \text{Taxonomy & Metadata} \rightarrow \text{Vocabulary Decks & Notes}$$
- **Tách biệt dữ liệu Dev và Production**: Hỗ trợ lệnh purge có kiểm soát để làm sạch dữ liệu kiểm thử mà không ảnh hưởng đến dữ liệu production.

---

## 2. Các Kịch Bản Reseed Nhanh (One-Click Scripts)

Để reset và nạp lại toàn bộ dữ liệu mẫu một cách tự động, sử dụng các script tương ứng với hệ điều hành:

### macOS / Linux / Git Bash
```bash
bash scripts/reseed_db.sh
```
*Luồng thực thi:*
1. `flask --app wsgi.py db upgrade` (Chạy toàn bộ migration Alembic)
2. `flask --app wsgi.py dev-purge-data --yes` (Làm sạch dữ liệu phát triển)
3. `python scripts/seed_flama_template.py` (Tạo các mẫu thẻ Note Type cơ bản)
4. `flask --app wsgi.py user-role-seed` (Khởi tạo các vai trò người dùng)
5. `flask --app wsgi.py taxonomy-seed` (Khởi tạo cây phân loại và metadata)
6. `flask --app wsgi.py vocab-seed --path static/seed_data --replace-lessons` (Nạp toàn bộ bộ thẻ từ vựng)

### Windows PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1
```

### Windows Command Prompt (CMD)
```bat
scripts\reseed_db.bat
```

---

## 3. Chi Tiết Các Lệnh CLI Seeding

Tất cả các lệnh CLI đều được gọi thông qua Flask CLI (`flask --app wsgi.py <command>`):

### 3.1. Seeding Phân Loại & Metadata (Taxonomy)
Khởi tạo và kiểm tra 6 bảng taxonomy trong cơ sở dữ liệu: `taxonomy_domains`, `taxonomy_subjects`, `taxonomy_frameworks`, `taxonomy_framework_levels`, `taxonomy_options`, `taxonomy_subject_option_maps`.

```bash
# Nạp dữ liệu taxonomy mặc định
flask --app wsgi.py taxonomy-seed

# Kiểm tra tính toàn vẹn của dữ liệu taxonomy hiện có
flask --app wsgi.py taxonomy-verify
```

### 3.2. Seeding Mẫu Thẻ (Note Types & Templates)
Tạo mẫu thẻ mặc định `Flama Standard Vocabulary` cùng các trường chuẩn (*Word, Reading, Hanviet, Translation_VI, Meaning_JP, Meaning_VI, Usage_JP, Example_JP, Audio, Image...*) và card layout HTML/CSS.

```bash
python scripts/seed_flama_template.py
```

### 3.3. Seeding Vai Trò Người Dùng (User Roles)
Khởi tạo các role hệ thống: `admin`, `moderator`, `member` cùng bộ quyền hạn chi tiết.

```bash
flask --app wsgi.py user-role-seed
```

### 3.4. Seeding Nhà Cung Cấp Giọng Đọc (TTS Providers)
Khởi tạo cấu hình cho Flama Audio desktop TTS (VoiceVox, Kokoro, Edge TTS...).

```bash
flask --app wsgi.py tts-provider-seed
```

### 3.5. Seeding Bộ Thẻ & Từ Vựng (Vocabulary Decks & Notes)
Đọc cấu trúc file/thư mục từ `static/seed_data/` để tạo cây bộ thẻ (Deck Tree) và các Note flashcard tương ứng.

```bash
# Nạp toàn bộ dữ liệu mẫu trong static/seed_data
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons

# Nạp riêng một thư mục cụ thể (ví dụ: bộ ChungBech)
flask --app wsgi.py vocab-seed --path "static/seed_data/ChungBech" --replace-lessons

# Bỏ qua các file đã nạp (không ghi đè)
flask --app wsgi.py vocab-seed --path "static/seed_data"
```

### 3.6. Xóa Trắng Dữ Liệu Phát Triển (Dev Purge)
Xóa toàn bộ các note, card, deck và install do người dùng tạo (dùng khi muốn đưa database về trạng thái xuất xưởng sạch sẽ).

```bash
# Yêu cầu cờ --yes để xác nhận thao tác phá hủy
flask --app wsgi.py dev-purge-data --yes
```

### 3.7. Khởi Tạo OAuth Client
Đăng ký OAuth client dùng cho tích hợp bên thứ ba (như ChatGPT GPTs hoặc Extension).

```bash
flask --app wsgi.py seed-oauth-client --client-id "chatgpt_flama" --client-name "ChatGPT"
```

---

## 4. Cấu Trúc Thư Mục Dữ Liệu Mẫu (`static/seed_data/`)

Hệ thống seed ánh xạ trực tiếp cấu trúc thư mục thành cây danh mục bộ thẻ (Deck Tree):

```text
static/seed_data/
├── MinnaNoNihongo/                      # -> Tạo Deck cha "MinnaNoNihongo"
│   ├── Bai_01.csv                       # -> Tạo Deck con "Bai 01" chứa các từ vựng bài 1
│   ├── Bai_02.csv                       # -> Tạo Deck con "Bai 02"
│   └── ...
├── Soumatome_N2/                        # -> Tạo Deck cha "Soumatome N2"
│   ├── TuVung_Tuan1.tsv                 # -> Tạo Deck con "TuVung Tuan1"
│   └── ...
└── ChungBech/                           # -> Bộ dữ liệu Anki TSV/TXT ChungBech
    ├── ChungBechN1__言葉__Bài 01.txt   # -> Deck "ChungBechN1 :: 言葉 :: Bài 01"
    └── ...
```

---

## 5. Quy Chuẩn Định Dạng File Seed (CSV / TSV / TXT)

### 5.1. Định dạng CSV Chuẩn Flama
File CSV mã hóa UTF-8 (hoặc UTF-8 with BOM) với dòng tiêu đề:

```csv
Deck,Word,hanviet,Reading,Translation_VI,Meaning_JP,Meaning_VI,Usage_JP,Usage_VI,Example_JP,Example_VI,Additional_Note_JP,Additional_Note_VI,image,Diagram,Word_Audio,Example_Audio
N5::Bài 1,わたし,TƯ,watashi,tôi,,,,,,わたしはアンです。,,,,,,
N5::Bài 1,あなた,,anata,bạn,,,,,,,,,,,,
```

### 5.2. Định dạng TXT Anki Export (ChungBech Legacy)
Hỗ trợ file xuất trực tiếp từ Anki có phần header thiết lập:

```text
#separator:tab
#html:true
#tags column:16
1. Deck Name	2. Word	3. Reading	4. Translation_VI	5. Meaning_JP	6. Meaning_VI	7. Usage_JP	8. Usage_VI	9. Example_JP	10. Example_VI	11. Additional_Note_JP	12. Additional_Note_VI	13. Image	14. Word_Audio	15. Example_Audio	16. Tags
```

---

## 6. Quản Lý & Nạp Dữ Liệu Qua Giao Diện Admin

Ngoài việc chạy CLI qua dòng lệnh, người quản trị có thể trực tiếp quản lý và kích hoạt seed lại từ trình duyệt:

1. Đăng nhập với tài khoản Admin.
2. Điều hướng tới menu **Quản trị hệ thống** $\rightarrow$ **Phân loại & Metadata** (URL: `http://127.0.0.1:4789/admin/taxonomy`).
3. Các thao tác trực quan:
   - **Nút "Nạp dữ liệu mẫu" (Reseed Defaults)**: Đồng bộ lại danh mục Lĩnh vực, Môn học, Khung thi và Metadata chuẩn vào database mà không cần mở terminal.
   - **Quản lý Lĩnh vực (Domains)**: Thêm/Sửa/Xóa Lĩnh vực học tập.
   - **Quản lý Môn học (Subjects)**: Gắn môn học vào Lĩnh vực, phân thứ tự hiển thị.
   - **Khung chứng chỉ & Cấp độ**: Thiết lập các kỳ thi (JLPT, IELTS, HSK, AWS...) và từng cấp độ (N5, 7.0, SAA...).
   - **Metadata Options**: Thêm mới hoặc chỉnh sửa các mục tiêu học tập, tính năng thẻ flashcard.
   - **Ánh xạ Môn học**: Tích chọn nhanh các chủ đề/mục tiêu áp dụng riêng cho từng môn học.

---

## 7. Khắc Phục Sự Cố & Câu Hỏi Thường Gặp (FAQs)

### Q1: Gặp lỗi `IntegrityError: Duplicate entry` khi chạy seed?
**Giải pháp**: Sử dụng cờ `--replace-lessons` với lệnh `vocab-seed` hoặc chạy `dev-purge-data --yes` trước khi seed để làm sạch dữ liệu cũ.

### Q2: Thiếu trường `hanviet` hoặc `diagram` khi nạp từ file Anki TXT?
**Giải thích**: File Anki cũ không có các trường này. Hệ thống sẽ tự động gán giá trị `null` và hiển thị an toàn trên giao diện mà không làm gãy format thẻ.

### Q3: File CSV có chứa tiếng Nhật/tiếng Việt bị lỗi hiển thị ký tự (mojibake)?
**Giải pháp**: Đảm bảo lưu file với encoding **UTF-8** hoặc **UTF-8 with BOM** trước khi đưa vào thư mục `static/seed_data/`.

### Q4: Thay đổi đường dẫn lưu trữ file âm thanh/hình ảnh khi seed?
**Giải pháp**: Cấu hình biến môi trường `FLASHCARD_MEDIA_UPLOAD_ROOT` trong file `.env` (khuyến nghị trỏ ra ngoài thư mục repo, ví dụ `../flama_media_storage`).
