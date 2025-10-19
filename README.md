# Nihongo Flask Auth Starter

Lightweight Flask + MySQL starter project that focuses on user registration, login, and logout using Flask-Login.

## Core Features
- Flask application factory pattern with SQLAlchemy models.
- Environment-based configuration via `.env` and `python-dotenv`.
- Secure password hashing and session management handled by Flask-Login.
- Vocabulary management: duyệt danh sách bài chia tự động mỗi 60 từ, nhập liệu hàng loạt qua CSV và chỉnh sửa nhanh nhãn `deck` cho từng mục từ.
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
4. Configure `.env` with your local settings:
   ```env
   FLASK_APP=wsgi.py
   FLASK_ENV=development
   SECRET_KEY=replace-me-with-a-secret-value
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your-password
   DB_NAME=nihongo
   ```
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
8. (Optional) Mở từng bài để hiệu chỉnh nhãn `Deck`:
   - Danh sách bài được chia tự động, mỗi bài hiển thị tối đa 60 từ theo thứ tự nhập.
   - Cột `Deck` có ô nhập cho phép cập nhật nhanh, kèm gợi ý `N1練習::Từ {số thứ tự}`.
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
