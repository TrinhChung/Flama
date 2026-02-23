# Nihongo Flask Auth Starter

Lightweight Flask + MySQL starter project that focuses on user registration, login, and logout using Flask-Login.

## Core Features
- Flask application factory pattern with SQLAlchemy models.
- Environment-based configuration via `.env` and `python-dotenv`.
- Secure password hashing and session management handled by Flask-Login.
- Vocabulary management: duyệt danh sách bài chia tự động mỗi 60 từ, nhập liệu hàng loạt qua CSV và chỉnh sửa nhanh mọi trường dữ liệu ngay trong bảng.
- Giao diện bài học hỗ trợ kéo giãn cột và tự lưu kích thước cho từng tài khoản.
- Bootstrap 5 templates for a quick, responsive UI.

## Requirements
- Python 3.10+
- MySQL server with an empty schema (default name `nihongo`).
- Python dependencies listed in `requirements.txt` (includes `cryptography` for MySQL caching_sha2 auth and `Flask-Migrate` for database migrations).

## Quick Setup
1. (Optional) Create a virtual environment:
   ```powershell
   python -m venv myenv
   ```
2. Activate the environment:
   ```powershell
   .\myenv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```powershell
   cp .env_example .env
   ```
   Edit `.env` with your local database credentials and settings.
5. Ensure the MySQL database defined by `DB_NAME` exists.
6. (Optional) Initialize migrations:
   ```powershell
   flask db init
   flask db migrate -m "Initial tables"
   flask db upgrade
   ```
7. (Optional) Nhập dữ liệu từ vựng bằng CSV:
   - Đăng nhập, truy cập `http://127.0.0.1:5000/vocabulary`.
   - Bấm **Nhập CSV**, dán nội dung với tiêu đề:
     ```
     Deck,Word,hanviet,Reading,Translation_VI,Meaning_JP,Meaning_VI,Usage_JP,Usage_VI,Example_JP,Example_VI,Additional_Note_JP,Additional_Note_VI,image,Diagram,Word_Audio,Example_Audio
     ```
   - Các cột bắt buộc: `Deck`, `Word`.
8. (Optional) Mở từng bài để hiệu chỉnh dữ liệu inline:
   - Tất cả từ vựng hiển thị trên một bảng; header tự cập nhật bài hiện tại dựa trên vị trí cuộn (mỗi 60 từ là một bài).
   - Double click vào bất kỳ ô nào để phóng to, chỉnh sửa và nhấn `Enter`/`blur` để lưu (Shift+Enter giữ xuống dòng với các ô đa dòng).
   - Phía cuối bảng có sẵn các hàng trống: double click vào từng ô để soạn thảo trước khi thêm dữ liệu mới.
   - Có thể kéo chiều rộng tiêu đề cột; hệ thống sẽ ghi nhớ kích thước cho lần truy cập sau.
9. Run the application:
   ```powershell
   flask run
   ```
   or
   ```powershell
   python wsgi.py
   ```

The server listens on `http://127.0.0.1:5000`.

## Seed Vocabulary from `static/seed_data`
- Command:
  ```powershell
  flask vocab-seed
  ```
- Default behavior:
  - Tạo/duy trì level tên `Seed Data`.
  - Mỗi folder con trong `static/seed_data` -> 1 `topic`.
  - Mỗi file `.tsv`/`.csv` trong folder -> 1 `lesson` (dùng tên file bỏ phần mở rộng).
  - Các dòng hợp lệ (`deck`, `word`) sẽ được import thành vocabulary entries.
- Tùy chọn:
  ```powershell
  flask vocab-seed --level "JLPT N1 Seed"
  flask vocab-seed --path "static/seed_data" --replace-lessons
  ```
  - `--replace-lessons`: Nếu lesson cùng tên đã tồn tại trong topic, xóa lesson cũ và nạp lại từ file.

## Project Structure
```
wsgi.py                 # Flask entry point
app/
├── __init__.py         # Application factory and configuration
├── extensions.py       # Shared Flask extensions (LoginManager)
├── routes/
│   ├── __init__.py     # Blueprint registration
│   ├── auth.py         # Authentication routes
│   ├── main.py         # Landing page and dashboard
│   └── vocabulary.py   # Vocabulary lessons, CSV import, deck editing
models/
├── __init__.py         # SQLAlchemy instance
├── user.py             # User model definition
└── vocabulary_entry.py # Vocabulary table schema
templates/              # Jinja2 templates
static/                 # Static assets
requirements.txt        # Python dependencies
.env                    # Environment configuration (never commit real secrets)
myenv/                  # Optional local virtual environment
```

## Next Ideas
- Add email confirmation or password reset flows.
- Introduce role-based access control for different user types.
- Expand migration scripts with seed data or additional tables as features grow.

## Flashcard V2 (Anki-like)
- New NoteType/FieldDef/Template/Note/Card/Media model is available.
- Management UI:
  - `/flashcards/note-types`
  - `/flashcards/note-types/<note_type_id>`
  - `/flashcards/notes/new`
  - `/flashcards/study`
- API root:
  - `/api/note-types`
  - `/api/notes`
  - `/api/study`
- Migration + rollback runbook:
  - `docs/FLASHCARD_V2_RUNBOOK.md`

### Assumptions recorded for review
- Legacy data does not contain user ownership on `vocabulary_entries`; migration maps to one target user.
- Backward-compatible transition is preserved via `USE_NEW_CARD_MODEL=false` default.
- Field rename uses job-tracking record but executes synchronously in current version.
