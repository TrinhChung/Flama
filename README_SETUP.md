# Setup Guide

Tai lieu nay tap trung vao thiet lap moi truong va cac lenh chay du an, co bo sung huong dan cho Windows.

## Commands Hay Dung (Uu Tien)

### macOS / Linux / Git Bash

```bash
# 1) Reset + reseed DB
bash scripts/reseed_db.sh

# 2) Setup workspace/codespaces
bash scripts/setup_github_workspace.sh

# 3) Chay app web (Port 4789)
flask --app wsgi.py run --host=0.0.0.0 --port=4789

# 4) Chay Flama Connect service (Yomitan / Anki Connect protocol - Port 4790)
python connect_wsgi.py
# Hoac:
flask --app connect_wsgi.py run --host=0.0.0.0 --port=4790
```

### Windows PowerShell

```powershell
# 1) Kich hoat virtual environment
.\.venv\Scripts\Activate.ps1

# 2) Reset + reseed DB
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1

# 3) Chay app web (Port 4789)
flask --app wsgi.py run --host=0.0.0.0 --port=4789

# 4) Chay Flama Connect service (Yomitan / Anki Connect protocol - Port 4790)
python connect_wsgi.py
# Hoac:
flask --app connect_wsgi.py run --host=0.0.0.0 --port=4790
```

### Windows Command Prompt

```bat
REM 1) Reset + reseed DB
scripts\reseed_db.bat

REM 2) Chay app web (Port 4789)
flask --app wsgi.py run --host=0.0.0.0 --port=4789

REM 3) Chay Flama Connect service (Yomitan / Anki Connect protocol - Port 4790)
python connect_wsgi.py
REM Hoac:
flask --app connect_wsgi.py run --host=0.0.0.0 --port=4790
```

## Prerequisites

- Python 3.10+
- Docker + Docker Compose plugin (neu chay MySQL bang container)
- Tren Windows:
  - Dung PowerShell hoac Command Prompt cho cac lenh native cua Windows
  - Cai Git Bash hoac WSL neu muon chay cac script `.sh`

## Quick Start (GitHub Workspace / Codespaces)

Chay tu thu muc goc du an:

### macOS / Linux / Git Bash

```bash
bash scripts/setup_github_workspace.sh
```

### Windows

`setup_github_workspace.sh` hien chi co ban shell, vi vay tren Windows can chay bang Git Bash hoac WSL:

```powershell
bash scripts/setup_github_workspace.sh
```

Script se tu dong:

- Tao/cap nhat `.env`
- Chay MySQL bang Docker (`docker compose up -d db`)
- Tao database theo `DB_NAME` trong `.env` (neu chua co)
- Cai Python dependencies vao `.venv`

Override bien moi truong:

### macOS / Linux / Git Bash

```bash
DB_PASSWORD='strong-db-pass' DB_NAME='flama' bash scripts/setup_github_workspace.sh
```

### Windows PowerShell

```powershell
$env:DB_PASSWORD = "strong-db-pass"
$env:DB_NAME = "flama"
bash scripts/setup_github_workspace.sh
```

Sau khi setup xong, reseed toan bo DB:

### macOS / Linux / Git Bash

```bash
bash scripts/reseed_db.sh
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1
```

### Windows Command Prompt

```bat
scripts\reseed_db.bat
```

Lenh reseed tren macOS/Linux se chay:

```bash
flask --app wsgi.py db upgrade
flask --app wsgi.py dev-purge-data --yes
python scripts/seed_flama_template.py
flask --app wsgi.py user-role-seed
flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons
```

Luu y: tren Windows, `scripts/reseed_db.ps1` va `scripts/reseed_db.bat` dang dung luong native va hien tai khong goi `dev-purge-data --yes`.

## Quick Start (May moi, khong dung workspace script)

### macOS / Linux / Git Bash

```bash
# Local Python
bash scripts/setup_new_device.sh --mode local

# Docker app + DB
bash scripts/setup_new_device.sh --mode docker
```

### Windows

`setup_new_device.sh` la shell script, nen can chay bang Git Bash hoac WSL:

```powershell
# Local Python
bash scripts/setup_new_device.sh --mode local

# Docker app + DB
bash scripts/setup_new_device.sh --mode docker
```

## Manual Setup

### macOS / Linux

1. Tao virtualenv:

```bash
python -m venv .venv
```

2. Kich hoat virtualenv:

```bash
source .venv/bin/activate
```

3. Cai dependencies:

```bash
pip install -r requirements.txt
```

4. Tao file moi truong:

```bash
cp .env_example .env
```

5. Chinh `.env`:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `FLASHCARD_MEDIA_UPLOAD_ROOT` (khuyen nghi de ngoai repo, vi du `../flama_media_storage`)

6. Chay migration + seed:

```bash
bash scripts/reseed_db.sh
```

### Windows PowerShell

1. Tao virtualenv:

```powershell
python -m venv .venv
```

2. Kich hoat virtualenv:

```powershell
.\.venv\Scripts\Activate.ps1
```

Neu bi chan script execution:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

3. Cai dependencies:

```powershell
pip install -r requirements.txt
```

4. Tao file moi truong:

```powershell
Copy-Item .env_example .env
```

5. Chinh `.env`:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `FLASHCARD_MEDIA_UPLOAD_ROOT` (khuyen nghi de ngoai repo, vi du `../flama_media_storage`)

6. Chay migration + seed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1
```

### Windows Command Prompt

1. Tao virtualenv:

```bat
python -m venv .venv
```

2. Kich hoat virtualenv:

```bat
.\.venv\Scripts\activate.bat
```

3. Cai dependencies:

```bat
pip install -r requirements.txt
```

4. Tao file moi truong:

```bat
copy .env_example .env
```

5. Chinh `.env`, sau do reseed:

```bat
scripts\reseed_db.bat
```

## Payment Setup (payOS only)

Payment direction hien tai cua FLAMA la payOS-first. Neu can bat thanh toan marketplace, dung cac bien sau trong `.env`:

- `PAYMENTS_ENABLED=1`
- `PAYMENTS_PROVIDER=payos`
- `PAYMENTS_PAID_INSTALL_REQUIRED=1` neu marketplace item phai thanh toan truoc khi cap quyen
- `PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED=1` neu muon webhook payOS tu dong confirm va grant quyen
- `PAYMENTS_ORDER_EXPIRY_SECONDS=1800` hoac gia tri phu hop voi chinh sach het han
- `PAYOS_CLIENT_ID`
- `PAYOS_API_KEY`
- `PAYOS_CHECKSUM_KEY`

Luu y:

- Gia tri mac dinh trong `.env_example` da theo huong payOS-first.
- `PAYMENTS_V1_ENABLED` chi con ton tai de tuong thich nguoc trong code. Khong dung bien nay cho setup moi.
- Khong them lai bien moi truong payment deprecated vao `.env`, setup guide, hay tai lieu van hanh.
- Webhook canonical hien tai la `POST /api/payments/providers/payos/webhook`.

Tai lieu payment canonical:

- `docs/architecture/FLAMA_PAYMENT_ARCHITECTURE.md`
- `docs/architecture/SYSTEM_ARCHITECTURE.md`

## Core Commands

### Chung

```bash
# Chay migration
flask --app wsgi.py db upgrade

# Chay app web (Port 4789)
flask --app wsgi.py run --host=0.0.0.0 --port=4789

# Chay Flama Connect service (Yomitan / Anki Connect protocol - Port 4790)
python connect_wsgi.py
```

### Reseed DB

```bash
# macOS / Linux / Git Bash
bash scripts/reseed_db.sh
```

```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\reseed_db.ps1
```

```bat
REM Windows Command Prompt
scripts\reseed_db.bat
```

### Seed Vocabulary Data

`vocab-seed` doc duoc du lieu tu `static/seed_data` va tao deck tree theo folder/file:

- Folder -> deck node
- File `.csv` / `.tsv` / `.txt` -> leaf deck
- Reseed full DB mac dinh se chay: `flask --app wsgi.py vocab-seed --path "static/seed_data" --replace-lessons`

Neu muon seed rieng mot nhom du lieu, co the chay truc tiep:

```bash
flask --app wsgi.py vocab-seed --path "static/seed_data/ChungBech" --replace-lessons
```

```powershell
flask --app wsgi.py vocab-seed --path "static/seed_data/ChungBech" --replace-lessons
```

```bat
flask --app wsgi.py vocab-seed --path "static/seed_data/ChungBech" --replace-lessons
```

### Legacy TXT Seed (ChungBech)

Flow seed hien tai da ho tro file `.txt` kieu Anki export co preamble nhu:

```text
#separator:tab
#html:true
#tags column:16
```

File mau hien dat tai `static/seed_data/ChungBech/ChungBechN1__言葉__Bài 01.txt`.

Khi seed file `.txt` legacy nay, he thong tai su dung parser import delimited hien co va map sang note type `Flama Standard Vocabulary` theo thu tu cot:

```text
1 Deck
2 Word
3 Reading
4 Translation_VI
5 Meaning_JP
6 Meaning_VI
7 Usage_JP
8 Usage_VI
9 Example_JP
10 Example_VI
11 Additional_Note_JP
12 Additional_Note_VI
13 image
14 Word_Audio
15 Example_Audio
16 tags (bo qua trong vocab-seed)
```

Luu y:

- Bo du lieu ChungBech khong co `hanviet`, nen field `hanviet` duoc seed la `null`.
- File `.txt` legacy nay khong co `diagram`, nen field `diagram` duoc seed la `null`.
- Bat ky truong nao khong co du lieu trong file cung duoc seed la `null`.
- `#tags column` duoc dung de parser doc dung format, nhung cot tags khong duoc ghi vao field values cua note.
- De them full data sau nay, chi can dat them file/folder cung format vao `static/seed_data/ChungBech/` roi chay lai `vocab-seed --replace-lessons`.

## Luu y media/audio

- Mac dinh media (bao gom audio VoiceVox) duoc luu ngoai repo tai `../flama_media_storage` de tranh lam nang git workspace.
- Co the doi bang bien moi truong `FLASHCARD_MEDIA_UPLOAD_ROOT`.

## CSV Import (UI)

1. Dang nhap vao he thong.
2. Truy cập `http://127.0.0.1:4789/import` hoặc dùng mục **Import** trong React app.
3. Bam **Nhap CSV** va dan du lieu voi header:

```text
Deck,Word,hanviet,Reading,Translation_VI,Meaning_JP,Meaning_VI,Usage_JP,Usage_VI,Example_JP,Example_VI,Additional_Note_JP,Additional_Note_VI,image,Diagram,Word_Audio,Example_Audio
```

4. Cot bat buoc: `Deck`, `Word`.
