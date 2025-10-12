# Nihongo Flask Auth Starter

Ứng dụng Flask mẫu với chức năng đăng nhập/đăng ký cơ bản và kết nối MySQL.

## Tính năng chính
- Flask cấu trúc theo mô hình `app + models` với SQLAlchemy.
- Thông tin cấu hình (bí mật, kết nối DB) được quản lý qua `.env` sử dụng `python-dotenv`.
- Đăng ký tài khoản, đăng nhập, đăng xuất với `Flask-Login` và mật khẩu được băm an toàn.
- Giao diện nền tảng Bootstrap 5, sẵn sàng mở rộng.

## Yêu cầu môi trường
- Python 3.10+
- MySQL Server (đã tạo sẵn một schema/database trống, ví dụ `nihongo`)

## Thiết lập nhanh
1. **(Tuỳ chọn) Tạo lại môi trường ảo**
   ```powershell
   python -m venv myenv
   ```

2. **Kích hoạt môi trường ảo**
   ```powershell
   .\myenv\Scripts\Activate.ps1
   ```

3. **Cài đặt thư viện**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Cấu hình `.env`**
   - Sửa các giá trị trong file `.env` cho phù hợp với môi trường của bạn:
     ```env
     FLASK_APP=app.py
     FLASK_ENV=development
     SECRET_KEY=thay-doi-thanh-chuoi-bi-mat
     DB_HOST=localhost
     DB_PORT=3306
     DB_USER=root
     DB_PASSWORD=mat-khau
     DB_NAME=nihongo
     ```
   - Chú ý: `DB_USER` và `DB_NAME` bắt buộc phải có. Nếu mật khẩu chứa ký tự đặc biệt, `app.py` sẽ tự động mã hoá giúp bạn.

5. **Khởi tạo database**
   - Đảm bảo MySQL đã chạy và bạn đã tạo sẵn database tên giống `DB_NAME`.
   - Lần chạy đầu tiên, ứng dụng sẽ tự `create_all` các bảng cần thiết (bảng `users`).

6. **Chạy ứng dụng**
   ```powershell
   flask run
   ```
   hoặc
   ```powershell
   python app.py
   ```
   Ứng dụng sẽ hoạt động tại `http://127.0.0.1:5000`.

## Cấu trúc thư mục chính
```
├── app.py                # Điểm vào chính của Flask app
├── models/
│   ├── __init__.py       # SQLAlchemy instance
│   └── user.py           # Định nghĩa model User
├── templates/            # Giao diện HTML (Flask Jinja2)
├── static/               # Nơi đặt file tĩnh (CSS/JS nếu cần)
├── requirements.txt      # Danh sách thư viện cần cài
├── .env                  # Thông tin cấu hình (không commit nội dung thật lên git)
└── myenv/                # Môi trường ảo Python
```

## Mở rộng
- Thêm xác thực email, quên mật khẩu, hoặc phân quyền vai trò.
- Tách các route thành Blueprint để dự án dễ bảo trì hơn.
- Tích hợp Alembic/Flask-Migrate để quản lý schema khi dự án lớn.

Chúc bạn học tập và phát triển dự án Nihongo thật hiệu quả! ✨
