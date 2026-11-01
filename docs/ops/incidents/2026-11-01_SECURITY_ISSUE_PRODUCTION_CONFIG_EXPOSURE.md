# [P0 SECURITY ISSUE] Rò rỉ Thông tin Hạ tầng & Cấu hình Production lên Public Git - Đề xuất Cô lập sang Private Git Submodule

- **Mã định danh**: `SEC-INCIDENT-20261101-01`
- **Mức độ nghiêm trọng**: **P0 - CRITICAL / KHẨN CẤP**
- **Trạng thái**: **ĐANG MỞ - YÊU CẦU XỬ LÝ NGAY LẬP TỨC**
- **Phạm vi ảnh hưởng**: Toàn bộ máy chủ production Flama (Hostinger Chung VPS, Oracle Cloud Tokyo, OV Gateway Malaysia, Go Media Service, WireGuard VPN Mesh)
- **Kho chứa bị lộ (Target Repository)**: `https://github.com/TrinhChung/Flama` (Trạng thái: **PUBLIC**)
- **Ngày ghi nhận**: 2026-11-01

---

## 1. Tóm tắt Sự cố (Executive Summary)

Kho chứa Git **Flama** (`TrinhChung/Flama`) hiện đang được thiết lập ở chế độ **Public**. Trong quá trình phát triển và triển khai tính năng Media Cutover và Deck Optimization gần đây, các thông tin nhạy cảm ở mức tối mật liên quan đến cấu hình hệ thống máy chủ, địa chỉ IP public, topology mạng riêng WireGuard, script vận hành root và đặc biệt là **Mã khóa bí mật dùng chung (Gateway Secret Header)** đã bị commit và đẩy (push) trực tiếp lên nhánh chính `origin/master`.

Việc phơi bày toàn bộ bản đồ hạ tầng và script triển khai trên một kho chứa công khai tạo ra nguy cơ bị rà quét tự động (automated crawlers), tấn công vượt mặt tầng bảo vệ Cloudflare (WAF Bypass), giả mạo định danh cổng giao tiếp nội bộ và xâm nhập trực tiếp vào máy chủ.

Báo cáo này được lập để ghi nhận chi tiết các bằng chứng rò rỉ, phân tích rủi ro an ninh, cung cấp quy trình cô lập khẩn cấp và đề xuất kiến trúc **Private Git Submodule** nhằm bóc tách hoàn toàn các tài nguyên nhạy cảm ra khỏi kho chứa công khai.

---

## 2. Bằng chứng Rò rỉ Dữ liệu Chi tiết (Forensic Audit Findings)

Qua rà soát kiểm tra mã nguồn và lịch sử Git, các thông tin bảo mật sau đây đã bị lộ công khai:

### 2.1. Lộ Địa chỉ IP Public Thực & Bản đồ Mạng Nội bộ (Network Topology)
Trong commit `0ee1a4097d1a0c8e0aadec7c5695c63f061943dc` (đã merge vào `origin/master`), file tài liệu kiến trúc và runbook vận hành chứa chính xác địa chỉ IP public và WireGuard của từng server:

| Máy chủ (Node) | IP Public bị lộ | IP WireGuard Mesh bị lộ | Vị trí & Vai trò | Nguồn file bị lộ trên Git |
| :--- | :--- | :--- | :--- | :--- |
| **Hostinger Chung VPS** | `192.0.2.151` | `wg-app-server` | Primary Backend API, MySQL, Redis, SSH Port | `docs/runbooks/FLAMA_MEDIA_MIGRATION_AND_CUTOVER_RUNBOOK_20261101.md` |
| **Oracle VPS (OV Gateway)** | `198.51.100.141` | `wg-gateway` | Nginx Edge Gateway, TLS Termination, Reverse Proxy | `docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md`, `FLAMA_INFRASTRUCTURE_PROPOSAL_...RFC.md` |
| **Worker 212 (Tokyo)** | `203.0.113.226` | `wg-worker212` | Flama Media Go Daemon (:4792), CAS File Storage (3.1GB) | `docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md`, `FLAMA_MEDIA_MIGRATION...RUNBOOK...md` |

*Chi tiết trích đoạn lộ trong Git:*
> `docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md` (Dòng 33 & 42):
> ```text
> OV Gateway (Malaysia): Public IP: 198.51.100.141 | WG: wg-gateway
> Worker 212 (Tokyo):   Public IP: 203.0.113.226 | WG: wg-worker212
> ```

### 2.2. Lộ Shared Secret Token giữa Gateway và Media Service
Trong commit `0ee1a409`, cấu hình Nginx mẫu đã được đưa vào tài liệu kiến trúc, trong đó **ghi lộ nguyên văn token xác thực bí mật**:
- **Token bị lộ**: `"REDACTED_GATEWAY_SECRET"`
- **Vị trí**:
  - `docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md` (Dòng 81 & 195)
  - File cấu hình `deploy/media.flama.vn.nginx.conf` (Dòng 64 & 81):
    ```nginx
    proxy_set_header X-Flama-Gateway-Secret "REDACTED_GATEWAY_SECRET";
    ```
- **Hậu quả**: Bất kỳ kẻ tấn công nào cũng có thể gửi header `X-Flama-Gateway-Secret: REDACTED_GATEWAY_SECRET` kèm theo payload để tải file lên hoặc truy cập trực tiếp vào Go daemon tại Worker 212 nếu port 4792 bị mở hoặc bị can thiệp.

### 2.3. Lộ Script Quản trị Hệ thống & Quyền Root trong `deploy/`
Thư mục `deploy/` nằm trực tiếp trong root của repository chứa toàn bộ quy trình vận hành nhạy cảm:
1. `deploy/bootstrap_hostinger.sh`:
   - Lộ chi tiết các đường dẫn nhạy cảm: `/etc/flama/flama.env` (chmod 0640), user hệ thống `flama`, database user `flama`.
   - Lộ toàn bộ các biến môi trường cấu hình production (default template) và port chạy nội bộ.
2. `deploy/run_remote_deploy.sh`:
   - Lộ phương thức triển khai SSH remote và command execution qua `systemd-run --unit=...` với quyền thực thi cao nhất.
3. `deploy/activate_release.sh`:
   - Lộ quy trình switch symlink, khởi động workers và quản lý database migrations.
4. `deploy/flama.service`, `flama-connect.service`, `flama-review-analytics-worker.service`, ...:
   - Toàn bộ danh sách systemd service units, giới hạn tài nguyên, chu kỳ timer của các worker nền.
5. Đường dẫn SSL Private Key trên server:
   - Trong `deploy/media.flama.vn.nginx.conf` lộ đường dẫn chứng chỉ: `/etc/ssl/certs/flama.vn.crt` và `/etc/ssl/private/flama.vn.key`.

### 2.4. Lộ Thông tin Định danh & Workflow Deploy trong `.github/workflows/deploy.yml`
Trong workflow tự động hóa:
- Giá trị fallback của biến môi trường lộ email cá nhân quản trị viên:
  ```yaml
  EMAIL_FROM_ADDRESS: ${{ vars.EMAIL_FROM_ADDRESS || '<personal-email>' }}
  EMAIL_SMTP_USER: ${{ vars.EMAIL_SMTP_USER || '<personal-email>' }}
  GOOGLE_OAUTH_CLIENT_ID: ${{ vars.GOOGLE_OAUTH_CLIENT_ID || secrets.GOOGLE_OAUTH_CLIENT_ID || '992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com' }}
  GOOGLE_OAUTH_REDIRECT_URI: ${{ vars.GOOGLE_OAUTH_REDIRECT_URI || 'https://api.flama.vn/auth/google/callback' }}
  ```
- Danh sách tất cả các biến môi trường bí mật của Production (dù dùng GitHub Secrets nhưng attacker nắm được kiến trúc xác thực gồm SSH, PayOS, MySQL, Gmail SMTP, Redis).

---

## 3. Đánh giá Mức độ Rủi ro (Threat Modeling & Impact Analysis)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MA TRẬN ĐÁNH GIÁ RỦI RO (P0)                          │
├───────────────────────┬──────────────────────────────┬──────────────────────┤
│ Nguy cơ (Threat)      │ Mức độ khả thi (Likelihood)  │ Hậu quả (Impact)     │
├───────────────────────┼──────────────────────────────┼──────────────────────┤
│ Bypass Cloudflare WAF │ RẤT CAO (Đã biết IP gốc)     │ CRITICAL (DDoS, scan)│
│ Giả mạo Gateway Token │ CAO (Token lộ nguyên văn)    │ HIGH (Upload rác/mã) │
│ Tấn công Brute-force  │ CAO (Đã biết port & user)    │ CRITICAL (Chiếm quyền│
│ Trinh sát Hạ tầng     │ HOÀN TOÀN (100% rõ ràng)     │ HIGH (Khai thác lỗ hổng)
└───────────────────────┴──────────────────────────────┴──────────────────────┘
```

1. **Bypass Cloudflare WAF để tấn công trực tiếp vào Máy chủ Gốc (Origin IP Exposure)**:
   - Bình thường `flama.vn` và `media.flama.vn` được bảo vệ phía sau proxy Cloudflare.
   - Nhưng khi IP `192.0.2.151`, `198.51.100.141`, và `203.0.113.226` bị công khai, kẻ tấn công có thể bỏ qua Cloudflare, gửi request trực tiếp đến IP gốc để vượt qua rate limiting, tấn công từ chối dịch vụ (DDoS) hoặc khai thác cổng dịch vụ chưa khóa kỹ.
2. **Nguy cơ Xâm nhập Trực tiếp từ Cổng Dịch vụ (Direct Service Exploitation)**:
   - Các cổng backend như `4789` (Flask), `4790` (Connect), `4792` (Flama Media Go daemon) hoặc SSH `22` có nguy cơ bị tấn công dò mật khẩu hoặc khai thác tràn bộ đệm nếu firewall UFW chưa drop toàn bộ public incoming traffic.
3. **Phơi bày Logic Vận hành và Điểm yếu Hệ thống**:
   - Hacker biết rõ cronjob, timer worker (`flama-analytics-counts.timer`, `flama-review-analytics-worker.timer`), quy trình migrate database và cách thức deploy qua SSH để canh thời điểm hệ thống khởi động lại nhằm tiến hành tấn công race-condition.

---

## 4. Biện pháp Khắc phục Khẩn cấp (Immediate Containment Actions)

Agent khuyến nghị thực hiện ngay lập tức các bước sau theo thứ tự ưu tiên:

### Bước 1: Thu hồi và Tạo mới Khóa Bí mật (Secret Rotation) - *Ưu tiên 1*
1. **Rotate ngay `X-Flama-Gateway-Secret`**:
   - Sinh chuỗi ngẫu nhiên mới 64 ký tự hex:
     ```bash
     openssl rand -hex 32
     ```
   - Cập nhật cấu hình Nginx trên OV Gateway (`198.51.100.141`) và file cấu hình / env của `flama-media` trên Worker 212 (`203.0.113.226`).
   - Khởi động lại dịch vụ `flama-media` và `nginx`.
2. **Kiểm tra và Cấu hình lại Tường lửa (Firewall Hardening)**:
   - Đảm bảo trên cả 3 server, tường lửa UFW / OCI Security List:
     - **Chỉ mở cổng 80, 443** cho các dải IP của Cloudflare (Cloudflare IP Ranges).
     - **Chặn tuyệt đối** truy cập trực tiếp từ Internet vào cổng `4789`, `4790`, `4792`, `3306`, `6379`.
     - Chỉ cho phép giao tiếp giữa các server thông qua mạng ảo WireGuard (`<wg-subnet>`).
     - Cổng SSH (22) nên đổi port hoặc giới hạn theo IP quản trị cố định.

### Bước 2: Tạm ẩn hoặc Làm sạch Lịch sử Git (Scrub Git History) - *Ưu tiên 2*
Vì repo đang ở chế độ Public, việc chỉ commit đè file mới (overwrite) **không xóa được dữ liệu cũ trong lịch sử commit**. Bất kỳ ai cũng có thể xem lại commit `0ee1a409` để lấy secret và IP.
- **Phương án A (Khuyến nghị ngắn hạn nhanh nhất)**:
  - Tạm thời chuyển repository `TrinhChung/Flama` sang **Private** trên GitHub Settings trong quá trình xử lý và dọn dẹp lịch sử.
- **Phương án B (Làm sạch lịch sử Git bằng `git-filter-repo`)**:
  - Dùng công cụ `git-filter-repo` để thay thế toàn bộ các chuỗi IP (`198.51.100.141`, `192.0.2.151`, `203.0.113.226`) và secret token `flama_gw_sec_...` thành chuỗi giả lập/dummy trong toàn bộ lịch sử commit.
  - Xóa bỏ file `deploy/media.flama.vn.nginx.conf` ra khỏi cây thư mục git.

---

## 5. Giải pháp Dài hạn Cốt lõi: Tách Cấu hình Deploy sang Private Git Submodule

Theo đúng định hướng chỉ đạo của người dùng: **Toàn bộ cấu hình máy chủ, script triển khai production, cấu hình Nginx thực tế và Systemd services phải được cô lập vào một Private Repository riêng biệt và liên kết với repo chính thông qua Git Submodule.**

### 5.1. Mô hình Kiến trúc Phân tách (Architecture Separation Model)

```
┌──────────────────────────────────────────────┐
│       Flama Main Repository (PUBLIC)         │
│       https://github.com/TrinhChung/Flama    │
├──────────────────────────────────────────────┤
│ ├── app/              (Flask Application)    │
│ ├── frontend/         (React 19 SPA)         │
│ ├── models/           (Database Schema)      │
│ ├── tests/            (Unit & In-Memory Test)│
│ ├── docs/             (Tài liệu mã nguồn mở) │
│ ├── deploy.example/   (MẪU config generic)   │
│ │   ├── flama.nginx.conf.example             │
│ │   └── flama.service.example                │
│ └── deploy/ ────────► [GIT SUBMODULE]        │
└──────────────────────────────┬───────────────┘
                               │
                               │ Trỏ tới Private Repo (SSH / Token)
                               ▼
┌──────────────────────────────────────────────┐
│   Flama Infra & Deploy Repo (PRIVATE)        │
│   https://github.com/TrinhChung/flama-infra  │
├──────────────────────────────────────────────┤
│ ├── nginx/            (Nginx configs thực tế)│
│ ├── systemd/          (Systemd service units)│
│ ├── scripts/          (deploy, activate, etc)│
│ ├── wireguard/        (Topology, IP mappings)│
│ ├── runbooks/         (Runbook vận hành nội) │
│ └── secrets.enc       (File mã hóa sops/ans) │
└──────────────────────────────────────────────┘
```

### 5.2. Lợi ích Cốt lõi của Private Submodule
1. **Bảo mật Tuyệt đối cho Public Repo**:
   - Người ngoài xem repo public `Flama` chỉ thấy một con trỏ submodule trỏ tới một Commit ID trên repo `flama-infra`.
   - Vì repo `flama-infra` là **Private**, người ngoài click vào sẽ nhận thông báo **404 Not Found** hoặc Không có quyền truy cập. Họ không xem được bất kỳ file Nginx, IP, hay script deploy nào.
2. **Dễ dàng Quản lý Phiên bản (Version Control Parity)**:
   - Mỗi commit trên repo code `Flama` có thể gắn liền với chính xác phiên bản script deploy tương ứng trong submodule.
3. **An toàn trong CI/CD (GitHub Actions)**:
   - Khi chạy workflow deploy trên GitHub Actions, chỉ cần cấu hình một **Deploy Key (Read-Only)** hoặc **Personal Access Token (PAT)** trong GitHub Secrets để GitHub Runner kéo (pull) submodule về tại thời điểm deploy.

### 5.3. Các Bước Kỹ thuật Triển khai Private Submodule

#### Bước 1: Khởi tạo Private Repository trên GitHub
1. Tạo một repository mới trên GitHub với tên: `flama-infra` (hoặc `flama-deploy-private`).
2. **Bắt buộc chọn chế độ: `Private`**.

#### Bước 2: Di chuyển Dữ liệu Deploy hiện tại vào Repo Private
1. Clone repo private về máy cục bộ.
2. Di chuyển toàn bộ nội dung trong thư mục `deploy/` hiện tại sang repo private.
3. Di chuyển các tài liệu runbook chứa IP thực tế (`docs/runbooks/FLAMA_MEDIA_MIGRATION_AND_CUTOVER_RUNBOOK_20261101.md`, v.v.) sang repo private.
4. Commit và push lên `flama-infra:main`.

#### Bước 3: Chuẩn hóa Thư mục Public trên Repo Flama
1. Trên repo `Flama` (public):
   - Xóa bỏ thư mục `deploy/` chứa file thực.
   - Thay thế bằng các template `.example` (chỉ chứa placeholder như `127.0.0.1`, `your-domain.com`, `GENERATED_SECRET_KEY`).
   - Thêm `deploy/media.flama.vn.nginx.conf` và các file cấu hình private vào `.gitignore`.

#### Bước 4: Nhúng Private Submodule vào Repo Flama
Chạy lệnh liên kết submodule:
```bash
# Đứng tại thư mục gốc của repo Flama
git submodule add git@github.com:TrinhChung/flama-infra.git deploy-infra
git commit -m "build(infra): isolate deployment configs and server topologies into private submodule"
```

#### Bước 5: Cấu hình GitHub Actions CI/CD với Private Submodule
Cập nhật file `.github/workflows/deploy.yml` để runner có quyền checkout private submodule:
```yaml
      - name: Checkout code with Private Submodule
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.INFRA_DEPLOY_SUBMODULE_TOKEN }}
          submodules: 'recursive'
```
*(Trong đó `INFRA_DEPLOY_SUBMODULE_TOKEN` là GitHub Fine-grained PAT hoặc Deploy Key có quyền đọc repo `flama-infra`).*

---

## 6. Kế hoạch Hành động Cụ thể (Action Plan & Checklist)

- [ ] **Khẩn cấp (Trong vòng 1 giờ tới)**:
  - [ ] Rotate `X-Flama-Gateway-Secret` trên cả OV Gateway (`198.51.100.141`) và Worker 212 (`203.0.113.226`).
  - [ ] Xóa bỏ/tách file untracked `deploy/media.flama.vn.nginx.conf` khỏi workspace công khai hoặc bổ sung vào `.gitignore`.
  - [ ] Tạm thời cân nhắc đặt repo `Flama` sang Private trên GitHub nếu cần chặn bot scanner trong lúc dọn dẹp.
- [ ] **Làm sạch Tài liệu & Mã nguồn (Trong 24 giờ tới)**:
  - [ ] Rà soát lại tất cả các file docs trong `docs/architecture/` và `docs/runbooks/`: thay thế toàn bộ địa chỉ IP thực (`198.51.100.141`, `192.0.2.151`, `203.0.113.226`) bằng địa chỉ giả lập/RFC 5737 (ví dụ: `203.0.113.10`, `198.51.100.5`).
  - [ ] Rà soát `.github/workflows/deploy.yml`: loại bỏ email cá nhân và client id hardcode trong fallback.
  - [ ] Chạy công cụ thanh lọc lịch sử Git để xóa vĩnh viễn token đã commit.
- [ ] **Triển khai Kiến trúc Mới (Private Submodule)**:
  - [ ] Khởi tạo repo `flama-infra` (Private).
  - [ ] Chuyển giao toàn bộ scripts deploy và file service sang `flama-infra`.
  - [ ] Cấu hình Submodule liên kết và cập nhật workflow deploy GitHub Actions.
  - [ ] Cài đặt công cụ `gitleaks` hoặc pre-commit hook để ngăn chặn bất kỳ lập trình viên hoặc agent nào vô tình commit file chứa secret/IP trong tương lai.

---

*Tài liệu này được lập theo chuẩn báo cáo sự cố an ninh thông tin (P0 Incident Report) để người dùng và đội ngũ kỹ thuật có căn cứ xử lý khẩn cấp và tái cấu trúc hệ thống một cách an toàn.*
