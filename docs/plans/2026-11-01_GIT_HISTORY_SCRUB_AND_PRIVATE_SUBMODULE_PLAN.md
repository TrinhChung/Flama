# Kế Hoạch Kỹ Thuật: Loại Bỏ Biến Nhạy Cảm Trong Lịch Sử Git & Cô Lập Hạ Tầng Sang Private Submodule

- **Mã kế hoạch**: `PLAN-SEC-20261101-01`
- **Mục tiêu**:
  1. Rà soát, phân loại toàn bộ biến, bí mật và thông tin nhạy cảm đã bị ghi vào Git: phần cần thiết đưa vào Git Environment, phần không cần thiết loại bỏ triệt để.
  2. Thực hiện quy trình thanh lọc hoàn toàn lịch sử Git (Git History Scrubbing) bằng công cụ chuyên dụng.
  3. Xây dựng Private Git Submodule (`flama-infra`) để lưu trữ toàn bộ cấu hình server production (Nginx, Systemd, Deploy scripts, Network topology, Runbooks), tách biệt hoàn toàn khỏi repo public `Flama`.
- **Trạng thái**: Chờ duyệt & Sẵn sàng thực thi.
- **Ngày lập**: 2026-11-01

---

## 1. Bảng Phân Loại & Điều Chuyển Biến Nhạy Cảm (Variable Classification Matrix)

Toàn bộ các biến, bí mật, địa chỉ IP và cấu hình bị lộ được phân vào 2 nhóm rõ ràng:

### 1.1. NHÓM 1: CẦN THIẾT CHO HỆ THỐNG ➔ Chuyển 100% vào Git Env (GitHub Secrets & Variables)

Các giá trị này là bắt buộc để ứng dụng chạy và triển khai, nhưng **tuyệt đối không được xuất hiện dưới dạng chuỗi thô hay giá trị fallback trong mã nguồn hoặc file workflow**:

| Tên biến / Bí mật | Vị trí hiện tại (Bị lộ) | Phân loại mới | Nơi lưu trữ đích | Hành động chuẩn hóa |
| :--- | :--- | :--- | :--- | :--- |
| **`SSH_HOST`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret, không in log |
| **`SSH_PORT`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret (đổi port non-standard) |
| **`SSH_USER`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`SSH_PRIVATE_KEY`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret, dùng ed25519 |
| **`DB_PASSWORD`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`PAYOS_API_KEY`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`PAYOS_CHECKSUM_KEY`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`PAYOS_CLIENT_ID`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`GOOGLE_OAUTH_CLIENT_SECRET`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`GOOGLE_OAUTH_CLIENT_ID`** | Hardcoded trong `deploy.yml` | Variable | GitHub Environment (`Flama`) | **Xóa fallback hardcoded**, chỉ đọc từ `vars.GOOGLE_OAUTH_CLIENT_ID` |
| **`GOOGLE_OAUTH_REDIRECT_URI`** | Hardcoded trong `deploy.yml` | Variable | GitHub Environment (`Flama`) | **Xóa fallback hardcoded**, chỉ đọc từ `vars.GOOGLE_OAUTH_REDIRECT_URI` |
| **`EMAIL_FROM_ADDRESS`** | Hardcoded trong `deploy.yml` | Variable | GitHub Environment (`Flama`) | **Xóa email cá nhân**, chỉ đọc từ `vars.EMAIL_FROM_ADDRESS` |
| **`EMAIL_SMTP_USER`** | Hardcoded trong `deploy.yml` | Variable | GitHub Environment (`Flama`) | **Xóa email cá nhân**, chỉ đọc từ `vars.EMAIL_SMTP_USER` |
| **`EMAIL_SMTP_PASSWORD`** | Secret trong `deploy.yml` | Secret | GitHub Environment (`Flama`) | Giữ trong Secret |
| **`FLAMA_GATEWAY_SECRET`** *(MỚI)* | Đang hardcode chuỗi cũ | Secret | GitHub Environment (`Flama`) & Private Infra | **Sinh mới chuỗi 64 hex**, lưu vào GitHub Secret & Nginx Private |
| **`INFRA_DEPLOY_KEY`** *(MỚI)* | Chưa có | Secret | GitHub Environment (`Flama`) | SSH Deploy Key đọc repo Private Submodule |

> [!IMPORTANT]
> **Nguyên tắc "Fail-Fast No-Fallback"**:  
> Trong file `.github/workflows/deploy.yml`, loại bỏ hoàn toàn các toán tử fallback như:  
> `EMAIL_SMTP_USER: ${{ vars.EMAIL_SMTP_USER || 'chungtrinh2k2@gmail.com' }}`  
> Chuyển thành:  
> `EMAIL_SMTP_USER: ${{ vars.EMAIL_SMTP_USER }}`  
> Nếu thiếu biến trong GitHub Environment, runner phải dừng ngay lập tức (`exit 1`) thay vì âm thầm dùng giá trị fallback nhạy cảm đã hardcode.

---

### 1.2. NHÓM 2: KHÔNG CẦN THIẾT / RÁC / NGUY HIỂM ➔ Loại Bỏ & Tiêu Hủy Triệt Để

Các thông tin này hoàn toàn không có lý do tồn tại trên public repository và phải bị loại bỏ vĩnh viễn:

1. **Chuỗi Secret Token Cũ**:
   - Giá trị: `"flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4"`
   - *Hành động*: Hủy bỏ (Revoke) trên toàn bộ server production; xóa sạch khỏi tài liệu `FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md`.
2. **Địa Chỉ IP Public Thật Của Cả 3 Server**:
   - `187.77.131.151` (Hostinger VPS)
   - `161.33.193.141` (Oracle OV Gateway)
   - `132.145.115.226` (Worker 212 Tokyo)
   - *Hành động*: Xóa khỏi toàn bộ tài liệu public. Nếu tài liệu kiến trúc cần minh họa sơ đồ mạng, **bắt buộc thay bằng dải IP tài liệu chuẩn RFC 5737**:
     - `198.51.100.10` (Ví dụ cho Gateway)
     - `203.0.113.20` (Ví dụ cho Worker 212)
     - `192.0.2.30` (Ví dụ cho App Server)
3. **Địa Chỉ IP Mạng Ảo WireGuard Nội Bộ**:
   - `10.10.0.4`, `10.10.0.5`, `10.10.0.6`
   - *Hành động*: Đưa tài liệu cấu hình mạng này sang **Private Submodule**, tài liệu public chỉ dùng tên định danh trừu tượng (`wg-gateway`, `wg-worker212`).
4. **File Cấu Hình Nginx Chứa SSL Private Key Path & Secret Thật**:
   - File `deploy/media.flama.vn.nginx.conf`
   - *Hành động*: Di chuyển vĩnh viễn sang Private Submodule; thêm vào `.gitignore` của repo public.

---

## 2. Quy Trình Kỹ Thuật: Làm Sạch Lịch Sử Git (Git History Scrubbing)

Vì Git lưu trữ dữ liệu theo mô hình Directed Acyclic Graph (DAG) bất biến, việc tạo một commit mới để xóa file **không giải quyết được vấn đề** vì người ngoài vẫn có thể checkout commit cũ (`0ee1a409`). Cần phải viết lại lịch sử commit của nhánh `master`.

### 2.1. Công cụ Khuyến nghị: `git-filter-repo`
`git-filter-repo` là công cụ Python được Git Core chính thức khuyến nghị (nhanh gấp 10-50 lần `git filter-branch` và an toàn hơn BFG Repo Cleaner).

### 2.2. Quy trình 4 Bước Thực Hiện

#### Bước 1: Sao lưu An toàn (Pre-flight Backup)
Trước khi thao tác viết lại lịch sử, tạo một bản sao lưu (mirror clone) tách biệt:
```bash
git clone --mirror https://github.com/TrinhChung/Flama.git Flama-backup.git
```

#### Bước 2: Tạo File Định Nghĩa Thay Thế Chuỗi (`sanitize_expressions.txt`)
Tạo một file text định nghĩa các chuỗi nhạy cảm cần tự động tìm và thay thế trên toàn bộ cây commit:
```text
# Thay thế Gateway Secret bị lộ thành chuỗi placeholder
flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4==>[REDACTED_GATEWAY_SECRET]

# Thay thế các IP thật thành IP chuẩn RFC 5737
161.33.193.141==>198.51.100.141
132.145.115.226==>203.0.113.226
187.77.131.151==>192.0.2.151

# Thay thế email cá nhân trong workflow
chungtrinh2k2@gmail.com==>noreply@flama.vn

# Thay thế Google OAuth Client ID hardcoded
992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com==>[REDACTED_OAUTH_CLIENT_ID]
```

#### Bước 3: Chạy Lệnh Thanh Lọc Lịch Sử
Chạy lệnh thanh lọc để vừa thay thế chuỗi, vừa loại bỏ các file cấu hình private ra khỏi toàn bộ lịch sử:
```bash
# 1. Thay thế chuỗi nhạy cảm trong toàn bộ commit
git-filter-repo --replace-text sanitize_expressions.txt --force

# 2. Xóa triệt để file nhạy cảm nếu đã từng bị add vào git
git-filter-repo --path deploy/media.flama.vn.nginx.conf --invert-paths --force
```

#### Bước 4: Đồng Bộ Lên Remote (Force Push Có Kiểm Soát)
Sau khi kiểm tra lịch sử cục bộ đã sạch hoàn toàn:
```bash
# Thêm lại remote vì git-filter-repo tự động gỡ remote để phòng ngừa sai sót
git remote add origin https://github.com/TrinhChung/Flama.git

# Đẩy lịch sử đã làm sạch lên GitHub (Bắt buộc cần quyền Admin trên repo)
git push origin --force --all
git push origin --force --tags
```

---

## 3. Kiến Trúc Private Git Submodule Cho Cấu Hình Hạ Tầng (Infra Submodule)

### 3.1. Sơ đồ Kiến trúc Cô lập (Decoupled Infrastructure Topology)

```
========================= GITHUB =========================

  [PUBLIC REPO] TrinhChung/Flama
  ├── app/                  (Flask Backend)
  ├── frontend/             (React 19 SPA)
  ├── models/               (SQLAlchemy ORM)
  ├── deploy.example/       (Mẫu cấu hình tham khảo generic)
  │   ├── flama.nginx.conf.example
  │   └── flama.service.example
  │
  └── deploy/ ────────────► [SUBMODULE POINTER: commit hash]
                                   │
                                   │ Xác thực bằng SSH Deploy Key
                                   ▼
  [PRIVATE REPO] TrinhChung/flama-infra  <--- CHỈ OWNER & CI TRUY CẬP
  ├── nginx/
  │   ├── flama.nginx.conf
  │   ├── media.flama.vn.nginx.conf
  │   └── connect.flama.vn.nginx.conf
  ├── systemd/
  │   ├── flama.service
  │   ├── flama-connect.service
  │   └── *.timer
  ├── scripts/
  │   ├── bootstrap_hostinger.sh
  │   ├── activate_release.sh
  │   ├── run_remote_deploy.sh
  │   └── sync_managed_env.py
  ├── wireguard/
  │   └── (configs, IP maps, topology thật)
  └── runbooks/
      └── (tài liệu vận hành chứa IP & hướng dẫn khẩn cấp)
```

### 3.2. Cấu Trúc File & Thư Mục Cụ Thể

1. **Trên Public Repo `Flama`**:
   - Thư mục `deploy/` cũ được chuyển đổi thành Git Submodule.
   - Bổ sung thư mục `deploy.example/`:
     - Chứa các file template `.example` sạch sẽ, dùng `127.0.0.1`, `example.com`, `CHANGE_ME_SECRET`.
     - Phục vụ cho lập trình viên mã nguồn mở muốn chạy thử ứng dụng trên môi trường cá nhân mà không cần truy cập infra production của Flama.
   - Thêm vào `.gitignore`:
     ```gitignore
     # Ngăn chặn vô tình commit file cấu hình production trực tiếp
     *.nginx.conf
     !*.nginx.conf.example
     *.service
     !*.service.example
     deploy/local/
     ```

2. **Trên Private Repo `flama-infra`**:
   - Đặt chế độ repository: **Private**.
   - Phân quyền: Chỉ cho phép tài khoản của Owner và GitHub Actions Bot.
   - Quản lý tập trung mọi thay đổi liên quan đến Nginx, Systemd, WireGuard mesh, và scripts triển khai VPS.

### 3.3. Tích Hợp Vào CI/CD (GitHub Actions Workflow)

Để workflow `deploy.yml` có thể checkout repo public `Flama` đồng thời kéo được Private Submodule `deploy/` mà không để lộ token:

1. **Tạo Deploy Key trên Repo Private `flama-infra`**:
   - Tạo cặp khóa SSH ed25519: `ssh-keygen -t ed25519 -C "github-actions-flama-deploy"`
   - Thêm Public Key vào `flama-infra` -> **Settings -> Deploy keys** (Chỉ cần quyền Read-only).
   - Thêm Private Key vào `Flama` (Repo chính) -> **Settings -> Environments -> Flama -> Secrets** với tên: `INFRA_SUBMODULE_SSH_KEY`.

2. **Cập nhật Step Checkout trong `.github/workflows/deploy.yml`**:
   ```yaml
   jobs:
     deploy:
       runs-on: ubuntu-latest
       environment: Flama
       steps:
         - name: Configure SSH Agent for Private Submodule
           uses: webfactory/ssh-agent@v0.9.0
           with:
             ssh-private-key: ${{ secrets.INFRA_SUBMODULE_SSH_KEY }}

         - name: Checkout code with Submodule
           uses: actions/checkout@v4
           with:
             submodules: 'recursive'
             fetch-depth: 1
   ```

Khi đó:
- Runner có đầy đủ script trong `deploy/` để thực hiện triển khai lên Hostinger VPS.
- Người dùng ngoài duyệt web xem mã nguồn `Flama` trên GitHub chỉ nhìn thấy icon submodule trỏ tới `flama-infra` kèm commit hash, khi click vào sẽ nhận thông báo **404 Repository not found**.

---

## 4. Kế Hoạch Triển Khai Từng Giai Đoạn (Execution Roadmap)

```
[ Giai đoạn 1: Khẩn Cấp ] (Thực hiện ngay)
  ├─ 1. Rotate Secret: Tạo mới X-Flama-Gateway-Secret trên server OV và Worker 212.
  ├─ 2. Audit Firewall: Khóa UFW port 4789, 4790, 4792, chỉ cho phép WireGuard.
  └─ 3. Chuyển repo Flama tạm thời sang Private trên GitHub (để chặn scanner).
         │
         ▼
[ Giai đoạn 2: Tạo Private Submodule ]
  ├─ 1. Tạo repo private `TrinhChung/flama-infra`.
  ├─ 2. Sao chép toàn bộ thư mục `deploy/` và các runbook chứa IP sang repo mới.
  ├─ 3. Thiết lập SSH Deploy Key giữa `Flama` và `flama-infra`.
  └─ 4. Nhúng submodule vào repo chính: `git submodule add ... deploy`.
         │
         ▼
[ Giai đoạn 3: Chuẩn Hóa Git Env & Workflow ]
  ├─ 1. Cập nhật `deploy.yml`: Xóa bỏ toàn bộ fallback chứa email cá nhân, Client ID.
  ├─ 2. Đưa toàn bộ biến vào GitHub Environment Secrets & Variables của `Flama`.
  └─ 3. Tạo thư mục `deploy.example/` trên repo public.
         │
         ▼
[ Giai đoạn 4: Thanh Lọc Lịch Sử Git ]
  ├─ 1. Chạy `git-filter-repo` với danh sách chuỗi cần thay thế.
  ├─ 2. Kiểm tra commit diff sau khi lọc.
  ├─ 3. Force push lịch sử sạch lên GitHub.
  └─ 4. Chuyển repo `Flama` trở lại chế độ Public (hoặc giữ Private theo ý muốn).
         │
         ▼
[ Giai đoạn 5: Phòng Ngừa Tái Diễn (Hardening) ]
  ├─ 1. Cài đặt pre-commit hook với `gitleaks` trên máy local.
  └─ 2. Bổ sung step `gitleaks-action` vào workflow CI để tự động chặn PR vi phạm.
```

---

*Kế hoạch này được lập chi tiết để làm kim chỉ nam thực hiện từng bước an toàn, đảm bảo zero-downtime cho hệ thống production Flama và bảo mật tuyệt đối cho toàn bộ hạ tầng.*
