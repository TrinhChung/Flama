# Flama System Architecture

## Tổng quan
Flama là ứng dụng Flask render phía server. `wsgi.py` gọi `create_app()` trong `app/__init__.py`, sau đó ứng dụng phục vụ request qua các blueprint, đi qua lớp service/repository/model và render lại bằng Jinja hoặc trả JSON.

## Sơ đồ tổng quát

```mermaid
flowchart TD
    U[Browser / User]
    W[wsgi.py]
    A[create_app()<br/>app/__init__.py]
    X[Extensions<br/>db, migrate, login_manager]
    B[Blueprints / Routes<br/>app/routes/*]
    V[Validators<br/>app/validators/*]
    S[Services<br/>app/services/*]
    R[Repositories<br/>app/repositories/*]
    M[Models<br/>models/*]
    D[(MySQL<br/>SQLite trong nhiều test)]
    T[Templates<br/>templates/ + templates/components/]
    J[Static Assets<br/>static/js + static/css + static/uploads]
    C[CLI Commands<br/>app/cli.py]

    U --> W --> A
    A --> X
    A --> B
    A --> C
    B --> V
    B --> S
    S --> R
    R --> M
    M --> D
    B --> T
    T --> J
    C --> S
```

## Thành phần chính

### 1. Entry point và bootstrap
- `wsgi.py` là entry point cho `flask run` và Gunicorn.
- `create_app()` nạp config từ biến môi trường, khởi tạo extension, đăng ký model, blueprint, CLI và chạy startup hooks như `db.create_all()`, schema compatibility, seed mặc định và clone cutover.

### 2. Web layer
- `app/routes/*` chứa các blueprint chính: `main`, `auth`, `admin`, `admin_payments`, `payments`, `user_orders`, `vocabulary`, `flashcards`, `mcp`.
- Layer này nhận HTTP request, gọi service/validator và trả về HTML hoặc JSON.

### 3. Business layer
- `app/services/*` giữ orchestration và nghiệp vụ chính.
- `app/validators/*` xử lý validate và normalize input.
- `app/repositories/*` gom truy vấn và thao tác dữ liệu để route không làm việc trực tiếp với ORM quá nhiều.

### 4. Data layer
- `models/*` là nơi khai báo SQLAlchemy models của toàn hệ thống.
- Runtime chính dùng MySQL; nhiều test chạy bằng SQLite in-memory.

### 5. Frontend layer
- Giao diện dùng Jinja server-rendered, với layout gốc ở `templates/base.html` và partial/component trong `templates/components/`.
- Hành vi phía client dùng vanilla JavaScript trong `static/js`; CSS component nằm trong `static/css/components/`.

### 6. Vận hành và môi trường
- Cấu hình đi theo biến môi trường, không có lớp `config.py` riêng.
- `docker-compose.yml` hiện chủ yếu cung cấp MySQL; app có thể chạy bằng `flask --app wsgi.py run` hoặc Gunicorn.

## Luồng request ngắn gọn
Một request đi từ browser vào `wsgi.py` -> Flask app -> blueprint/route -> validator/service -> repository/model -> database, rồi quay ngược ra route để render Jinja hoặc trả JSON cho client.
