# Setup Guide

Tài liệu này tập trung vào thiết lập môi trường và các lệnh chạy dự án.

## Commands Hay Dung (Uu Tien)

```bash
# 1) Reset + reseed DB
bash scripts/reseed_db.sh

# 2) Setup workspace/codespaces
bash scripts/setup_github_workspace.sh

# 3) Chay app
flask --app wsgi.py run --host=0.0.0.0 --port=4789
```

## Prerequisites
- Python 3.10+
- Docker + Docker Compose plugin (nếu chạy MySQL bằng container)

## Quick Start (GitHub Workspace / Codespaces)

Chạy từ thư mục gốc dự án:

```bash
bash scripts/setup_github_workspace.sh
```

Script sẽ tự động:
- Tạo/cập nhật `.env`
- Chạy MySQL bằng Docker (`docker compose up -d db`)
- Tạo database theo `DB_NAME` trong `.env` (nếu chưa có)
- Cài Python dependencies vào `.venv`

Override biến môi trường (khuyến nghị):

```bash
DB_PASSWORD='strong-db-pass' DB_NAME='flama' bash scripts/setup_github_workspace.sh
```

Sau khi setup xong, reseed toàn bộ DB bằng 1 lệnh:

```bash
bash scripts/reseed_db.sh
```

Script này sẽ chạy tuần tự:

```bash
flask --app wsgi.py db upgrade
flask --app wsgi.py dev-purge-data --yes
python scripts/seed_flama_template.py
flask --app wsgi.py user-role-seed
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons
```

## Quick Start (Máy mới, không dùng workspace script)

```bash
# Local Python
bash scripts/setup_new_device.sh --mode local

# Docker app + DB
bash scripts/setup_new_device.sh --mode docker
```

## Manual Setup (Local, khi không dùng script)

1. Tạo virtualenv:
```bash
python -m venv .venv
```

2. Kích hoạt virtualenv:
```bash
source .venv/bin/activate
```

3. Cài dependencies:
```bash
pip install -r requirements.txt
```

4. Tạo file môi trường:
```bash
cp .env_example .env
```

5. Chỉnh `.env`:
- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `FLASHCARD_MEDIA_UPLOAD_ROOT` (khuyến nghị để ngoài repo, ví dụ `../flama_media_storage`)

6. Chạy migration + seed:
```bash
bash scripts/reseed_db.sh
```

7. Chạy ứng dụng theo lệnh ở mục `Core Commands`.

## Core Commands (không trùng lặp)

```bash
# Chạy migration
flask --app wsgi.py db upgrade

# Chạy app
flask --app wsgi.py run --host=0.0.0.0 --port=4789

# Reseed full DB (đã bao gồm purge + seed)
bash scripts/reseed_db.sh
```

## Lưu ý media/audio

- Mặc định media (bao gồm audio VoiceVox) được lưu ngoài repo tại `../flama_media_storage` để tránh làm nặng git workspace.
- Có thể đổi bằng biến môi trường `FLASHCARD_MEDIA_UPLOAD_ROOT`.

Các lệnh seed lẻ vẫn còn dùng được, nhưng thường không cần chạy riêng nếu đã dùng `scripts/reseed_db.sh`.

## CSV Import (UI)

1. Đăng nhập vào hệ thống.
2. Truy cập `http://127.0.0.1:4789/vocabulary`.
3. Bấm **Nhập CSV** và dán dữ liệu với header:

```text
Deck,Word,hanviet,Reading,Translation_VI,Meaning_JP,Meaning_VI,Usage_JP,Usage_VI,Example_JP,Example_VI,Additional_Note_JP,Additional_Note_VI,image,Diagram,Word_Audio,Example_Audio
```

4. Cột bắt buộc: `Deck`, `Word`.
