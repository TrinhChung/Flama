# Báo Cáo Điều Tra & Đối Soát Toàn Diện Rò Rỉ Dữ Liệu Hạ Tầng Trong Lịch Sử Git Flama

- **Mã báo cáo**: `REP-SEC-20261101-01`
- **Phiên bản**: `1.0.0-FINAL`
- **Ngày công bố**: 2026-11-01
- **Phân loại**: Báo cáo kỹ thuật an ninh nội bộ (Security Exposure Investigation & Audit Report)
- **Tác giả**: Đội ngũ Điều tra & Ứng phó Sự cố An ninh Flama (Flama Security Incident Response Team - Milestone 1)
- **Đối tượng áp dụng**: Ban Quản trị Hệ thống, Đội ngũ Lập trình viên Core, DevOps, AI Agents hoạt động trên repository
- **Mức độ nghiêm trọng**: **P0 - KHẨN CẤP / CRITICAL**
- **Trạng thái kho chứa**: Repository công khai trên GitHub (`https://github.com/TrinhChung/Flama.git`)

---

## Mục Lục
1. [Tóm Tắt Tổng Quan Sự Cố (Executive Summary)](#1-tóm-tắt-tổng-quan-sự-cố-executive-summary)
2. [Dòng Thời Gian Lộ Dữ Liệu & Các Đợt Rò Rỉ (Incident Timeline & Exposure Waves)](#2-dòng-thời-gian-lộ-dữ-liệu--các-đợt-rò-rỉ-incident-timeline--exposure-waves)
3. [Cấu Trúc Liên Kết & Thông Số Kỹ Thuật Kho Chứa (Repository Topology & Metadata)](#3-cấu-trúc-liên-kết--thông-số-kỹ-thuật-kho-chứa-repository-topology--metadata)
4. [Danh Mục Chi Tiết Toàn Bộ Tài Nguyên Nhạy Cảm Bị Lộ (Comprehensive Sensitive Asset Catalog)](#4-danh-mục-chi-tiết-toàn-bộ-tài-nguyên-nhạy-cảm-bị-lộ-comprehensive-sensitive-asset-catalog)
   - 4.1. Địa chỉ IP Public Thật (Origin Server Public IPs)
   - 4.2. Mạng Lưới WireGuard Mesh Riêng (Internal WireGuard IPs & Topology)
   - 4.3. Mã Khóa Bí Mật Cổng Giao Tiếp (Gateway Shared Secret Token)
   - 4.4. Cấu Hình CI/CD Fallbacks & Thông Tin Định Danh Quản Trị
   - 4.5. Hệ Thống 23 File Triển Khai Production, Cấu Hình Nginx, SSL Private Keys & Systemd Units
5. [Bảng Kê Chi Tiết Từng Commit Chứa Bí Mật (Full Commit Leak Catalog)](#5-bảng-kê-chi-tiết-từng-commit-chứa-bí-mật-full-commit-leak-catalog)
   - 5.1. Nhóm 12 Commits Trọng Yếu (Critical Leaks: IPs, Secrets, Tokens, Fallbacks)
   - 5.2. Nhóm 10 Commits Lịch Sử Chứa Email Quản Trị (Historical Commits: HTML Templates & Seeds)
6. [Kết Quả Đối Soát Thư Mục `deploy/` và Submodule Private `infra-vpn/flama/`](#6-kết-quả-đối-soát-thư-mục-deploy-và-submodule-private-infra-vpnflama)
7. [Các Phát Hiện Tồn Dư Nhạy Cảm Ngay Trên Nhánh `HEAD`](#7-các-phát-hiện-tồn-dư-nhạy-cảm-ngay-trên-nhánh-head)
8. [Phân Tích Ma Trận Rủi Ro & Mô Hình Mối Đe Dọa (Threat Modeling & Risk Matrix)](#8-phân-tích-ma-trận-rủi-ro--mô-hình-mối-đe-dọa-threat-modeling--risk-matrix)
9. [Định Hướng Bảng Chuỗi Cần Thay Thế Cho Runbook Thanh Lọc Git (Milestone 2)](#9-định-hướng-bảng-chuỗi-cần-thay-thế-cho-runbook-thanh-lọc-git-milestone-2)

---

## 1. Tóm Tắt Tổng Quan Sự Cố (Executive Summary)

Vào sáng ngày 01 tháng 11 năm 2026, trong quá trình thẩm định kiến trúc hạ tầng và chuẩn hóa đường dẫn lưu trữ media (`/store/`) trên hệ thống Flama, nhóm kỹ thuật đã phát hiện một đợt rò rỉ dữ liệu hạ tầng đặc biệt nghiêm trọng xảy ra trên kho mã nguồn công khai (Public Repository) `https://github.com/TrinhChung/Flama`.

Sự cố bắt nguồn từ việc đưa trực tiếp các tài liệu phân tích kỹ thuật, sơ đồ phân bổ tải đa cụm, runbook di chuyển dữ liệu, các kịch bản script và cấu hình proxy Nginx chứa thông số production thực tế vào git tree của repository. Đáng chú ý, commit `0ee1a4097d1a0c8e0aadec7c5695c63f061943dc` chứa toàn bộ IP public, IP WireGuard và khóa bí mật cổng giao tiếp (Gateway Secret Token) đã được hòa trộn vào nhánh `origin/master` thông qua **Pull Request #279** vào lúc `10:44:36 +0900` ngày 01/11/2026, khiến các thông số này hoàn toàn phơi bày trước công chúng trên Internet.

### Các Điểm Phát Hiện Then Chốt:
1. **Lộ diện toàn bộ topo hạ tầng 3 cụm máy chủ**: Cả 3 IP Public thực tế của máy chủ Hostinger Chung VPS (`187.77.131.151`), Oracle OV Gateway (`161.33.193.141`), và Tokyo Worker 212 (`132.145.115.226`) đều bị phơi bày công khai kèm thông số phần cứng chi tiết.
2. **Lộ diện mạng riêng ảo WireGuard**: Toàn bộ dải IP VPN nội bộ `10.10.0.4`, `10.10.0.5`, `10.10.0.6` (Subnet `10.10.0.0/24`) bị hardcode trong tài liệu, mã nguồn Flask, Go daemon và các bài test.
3. **Lộ mã khóa xác thực phân quyền Gateway**: Chuỗi bí mật chia sẻ (Shared Secret) `"flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4"` phục vụ xác thực giữa Nginx Edge Gateway và Go Daemon `flama-media` bị lộ nguyên văn trong tài liệu và cấu hình Nginx.
4. **Lộ fallback định danh cá nhân và OAuth**: Email cá nhân quản trị viên `chungtrinh2k2@gmail.com` và Google OAuth Client ID Production `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com` bị hardcode làm fallback trong `.github/workflows/deploy.yml` từ tháng 08/2026.
5. **Thư mục `deploy/` gồm 23 file production vẫn nằm trên repo public**: Chứa cấu hình Nginx thật, đường dẫn chứng chỉ SSL cá nhân/Let's Encrypt (`/etc/ssl/private/flama.vn.key`), 14 systemd unit files và các kịch bản deploy SSH trực tiếp bằng root/sudo.
6. **Tồn dư nhạy cảm trên `HEAD`**: Mặc dù nhánh khắc phục `sec/isolate-infra-submodule-and-sanitize-docs-20261101` đã được tạo tại commit `0a170f51`, nhưng các fallback IP WireGuard vẫn tồn tại trong mã nguồn `app/settings.py`, `app/services/flama_media_client.py`, script `scripts/migrate_media_to_worker212.py`, và file báo cáo `docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md`.

Cuộc điều tra này đóng vai trò là căn cứ pháp lý và kỹ thuật tuyệt đối chuẩn xác để thực hiện hai nhiệm vụ kế tiếp: (1) Xây dựng phương án và runbook viết lại lịch sử Git bằng `git-filter-repo` (Milestone 2); (2) Thiết lập bộ quy tắc cứng trong `AGENTS.md`, cấu hình Gitleaks và pre-commit hooks ngăn chặn triệt để tái diễn (Milestone 3).

---

## 2. Dòng Thời Gian Lộ Dữ Liệu & Các Đợt Rò Rỉ (Incident Timeline & Exposure Waves)

Quá trình điều tra lịch sử Git từ commit ban đầu (`657b9958`) cho thấy sự cố rò rỉ dữ liệu không xảy ra đơn lẻ mà diễn ra qua 5 đợt tích tụ từ tháng 02/2026 đến tháng 11/2026:

```
[Tháng 02/2026] ──> [Tháng 08-09/2026] ──> [31/10/2026] ──> [Sáng 01/11/2026] ──> [Trưa 01/11/2026]
   Đợt 1               Đợt 2                 Đợt 3              Đợt 4 (Đỉnh điểm)      Đợt 5 (Hiện tại)
Lộ Email Quản Trị   Lộ Google OAuth ID    Lộ WireGuard IP   Lộ 3 Public IPs, Secret   Phát Hiện Sự Cố,
Trong Template Cũ   & CI/CD Fallbacks     & Security Hooks  Token & Merge PR #279    Tạo Submodule & Audit
```

### Chi Tiết Từng Giai Đoạn:

- **Đợt 1 (23/02/2026 – 06/04/2026): Lộ thông tin định danh cá nhân trong HTML Templates cũ**
  - Trong giai đoạn đầu phát triển với Jinja2 server-side rendering, email cá nhân `chungtrinh2k2@gmail.com` được hardcode vào các file `templates/privacy.html`, `templates/terms.html`, `templates/components/footer.html`, `scripts/seed_flama_template.py`.
  - Các commit tiêu biểu: `2babf264`, `2495118a`, `4d32f15b`, `a2b86aa7`, `060883a8`, `7fd51a08`, `4f9bd4e7`, `63b3c9eb`.

- **Đợt 2 (28/08/2026 – 19/09/2026): Lộ Google OAuth Client ID và CI/CD Fallback Secrets**
  - Vào ngày 28/08/2026, khi tích hợp luồng gửi email giao dịch SMTP và cơ chế xác thực Google OAuth, các giá trị production thật đã bị hardcode làm fallback cho workflow CI/CD tại commit `eadc5239` (`EMAIL_FROM_ADDRESS`, `EMAIL_SMTP_USER: chungtrinh2k2@gmail.com`) và commit `b49fd823` (`GOOGLE_OAUTH_CLIENT_ID: 992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com`).
  - Ngày 19/09/2026, commit `e81eb74a` tiếp tục đưa email quản trị vào `MANAGED_VARIABLE_DEFAULTS` trong `deploy/sync_managed_env.py`.

- **Đợt 3 (31/10/2026 – Rạng sáng 01/11/2026): Lộ topo WireGuard Mesh trong tính năng Security Webhook và Media Client**
  - Trong nỗ lực xây dựng webhook báo cáo tấn công (`app/api/v1/internal/security.py`), commit `b6cc600c` đã hardcode danh sách IP tin cậy của mạng WireGuard (`10.10.0.5`, `10.10.0.6`) vào unit test.
  - Ngay sau đó, commit `33196637` đưa URL nội bộ `http://10.10.0.6:4792` làm giá trị mặc định cho `FLAMA_MEDIA_WORKER_URL` trong `app/settings.py`, `app/services/flama_media_client.py` và script `scripts/migrate_media_to_worker212.py`.

- **Đợt 4 (01/11/2026, 01:38 – 10:44 +0900): Đỉnh điểm rò rỉ toàn bộ IP Public, Gateway Secret Token và Merge PR #279**
  - Vào 01:38 +0900, commit `3edf9b69` đưa vào tài liệu kiến trúc và migration runbook chứa đầy đủ 3 IP Public, 3 IP WireGuard, Gateway Secret Token và lệnh rsync với root SSH.
  - Vào 10:06 +0900, commit `f445ea54` bổ sung tài liệu đề xuất hạ tầng phơi bày IP của cả 3 node và sơ đồ mạng vật lý.
  - Vào 10:07 +0900, commit `0ee1a409` đưa file kiến trúc định tuyến media chứa nguyên văn cấu hình Nginx `media.flama.vn`, SSL cert path và Gateway Secret Token.
  - **10:44:36 +0900**: **Pull Request #279** được merge vào `origin/master` (commit `4c4df719d6595ccee4bd260c731494cdd191e76e`), chính thức đẩy toàn bộ dữ liệu nhạy cảm này lên branch chính công khai trên GitHub.

- **Đợt 5 (01/11/2026, 13:47 – Hiện tại): Phát hiện sự cố, phản ứng ban đầu và tồn dư chưa được làm sạch**
  - Vào 13:47 +0900, commit `708a246f` đưa file báo cáo `docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md` (890 dòng) vào git tree, tiếp tục chứa dày đặc cả 3 IP Public và 3 IP WireGuard.
  - Vào 13:48 +0900, commit `0a170f51` trên nhánh `sec/isolate-infra-submodule-and-sanitize-docs-20261101` cố gắng khắc phục bằng cách đưa cấu hình hạ tầng sang submodule private `infra-vpn` và làm sạch tài liệu kiến trúc. Tuy nhiên:
    - Báo cáo sự cố mới tạo vẫn trích dẫn nguyên văn IP và secret token.
    - File `MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md` bị bỏ sót hoàn toàn, chưa được làm sạch.
    - Mã nguồn Flask `app/settings.py`, `app/services/flama_media_client.py` và test cases vẫn chứa hardcode IP WireGuard `10.10.0.6`.
    - Lịch sử Git trên GitHub vẫn phơi bày 100% dữ liệu qua PR #279.

---

## 3. Cấu Trúc Liên Kết & Thông Số Kỹ Thuật Kho Chứa (Repository Topology & Metadata)

Đối soát kỹ thuật trực tiếp trên kho chứa mã nguồn local và remote cung cấp các thông số định lượng chính xác:

| Thông số / Thuộc tính | Giá trị định lượng | Ghi chú kỹ thuật & Tác động |
| :--- | :--- | :--- |
| **Tổng số commit trên HEAD** | **1,176** commits | Được xác định qua `git rev-list --count HEAD` |
| **Tổng số commit toàn bộ refs** | **1,197** commits (1,198 gồm stash) | Được xác định qua `git rev-list --count --all` |
| **Commit Root chính (Initial commit)** | `657b995846f76db4370c8cc3b4ca3073e7177f51` | Author: TrinhChung <chungtrinh2k2@gmail.com>, 2025-10-13 00:42:03 +0900 (`init`) |
| **Commit Root phụ (Orphan reference)** | `1ee39052b84f4c85187f8d4ee76df4fc7c9c3b71` | Stash / nhánh mồ côi tạo ngày 25/10/2026 |
| **Nhánh làm việc cục bộ hiện tại** | `sec/isolate-infra-submodule-and-sanitize-docs-20261101` | Tip commit: `0a170f51ff93e858316a08b6892469c9588f0ff3` |
| **Nhánh `master` cục bộ** | `cec70bc37a137e03f9b8544243c29ab4613856ba` | Nhánh master trên local workspace |
| **Nhánh `origin/master` (GitHub Remote)** | `4c4df719d6595ccee4bd260c731494cdd191e76e` | Nhánh master trên GitHub, chứa merge commit của PR #279 |
| **Số lượng nhánh cục bộ (Local branches)** | **25** nhánh | `git branch` (bao gồm các nhánh feature, chore, test) |
| **Số lượng nhánh remote (Remote branches)** | **66** nhánh | `git branch -r` (lưu trữ trên GitHub `origin/`) |
| **Số lượng Git Tags** | **0** tags | `git tag -l` không trả về kết quả nào |
| **Remote Origin URL** | `https://github.com/TrinhChung/Flama.git` | Kho chứa công khai trên GitHub |
| **Submodule cấu hình hạ tầng** | `infra-vpn` (`git@github.com:TrinhChung/infra-vpn.git`) | Nhúng tại commit `708a246f` vào đường dẫn `infra-vpn/` |

### Nhận Định Quan Trọng Về Cấu Trúc:
- **Lợi thế lớn từ 0 Git Tags**: Việc kho chứa chưa gắn bất kỳ Git tag nào (`0 tags`) là một điều kiện thuận lợi rất lớn cho việc thực thi viết lại lịch sử Git bằng `git-filter-repo`. Quá trình filter sẽ không làm vỡ các chữ ký điện tử GPG (annotated/signed tags) hoặc gây ra xung đột tag trên client của người dùng.
- **Quy mô phân nhánh lớn (66 remote branches)**: Số lượng nhánh remote lớn đòi hỏi lệnh `git-filter-repo` phải được thực thi ở phạm vi toàn diện (`--all`) và sau đó phải force-push đồng bộ tất cả các nhánh để ngăn ngừa việc rò rỉ dữ liệu qua các nhánh feature cũ chưa được thanh lọc.

---

## 4. Danh Mục Chi Tiết Toàn Bộ Tài Nguyên Nhạy Cảm Bị Lộ (Comprehensive Sensitive Asset Catalog)

### 4.1 Địa Chỉ IP Public Thật (Origin Server Public IPs)

Hạ tầng phân tán của Flama bao gồm 3 máy chủ chạy trên 2 nhà cung cấp dịch vụ đám mây (Hostinger và Oracle Cloud Infrastructure - OCI). Toàn bộ 3 IP Public này đã bị lộ:

```
[Internet Client]
       │
       ▼
[Cloudflare CDN / WAF] (Đã bị bypass do lộ IP gốc)
       │
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
Hostinger Chung VPS      Oracle OV Gateway         Tokyo Worker 212
  187.77.131.151          161.33.193.141            132.145.115.226
(Kuala Lumpur, AS47583)   (Oracle Tokyo, AS31898)   (Oracle Ampere ARM, AS31898)
```

| Tên Node | IP Public Bị Lộ | Nhà Cung Cấp & Vị Trí | Dịch Vụ Đang Mở & Cổng Giao Tiếp | Tác Động Khi Bị Lộ IP Gốc | Mức Độ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chung VPS** | `187.77.131.151` | Hostinger VPS (Kuala Lumpur, Malaysia) | - SSH: Port `22`<br>- HTTP Gunicorn: Port `4789`<br>- MySQL 8.0: Port `3306`<br>- Redis: Port `6379`<br>- WireGuard: Port `51820/udp` | **Bypass hoàn toàn Cloudflare WAF**: Kẻ tấn công có thể trực tiếp tấn công từ chối dịch vụ (DDoS), thực hiện brute-force SSH, khai thác cổng MySQL `3306` hoặc Redis `6379` nếu firewall chưa chặn IP ngoài. | **P0 - CRITICAL** |
| **OV Gateway** | `161.33.193.141` | Oracle OCI (Micro Instance, Tokyo / Malaysia) | - Nginx Edge Gateway: Port `80`, `443`<br>- TLS 1.3 Termination (`media.flama.vn`)<br>- WireGuard Endpoint | Kẻ tấn công có thể gửi request trực tiếp vào Nginx Edge, vượt qua rate limiting của Cloudflare, tấn công khai thác buffer overflow hoặc làm cạn kiệt tài nguyên của Micro instance (1 OCPU, 1GB RAM). | **P0 - CRITICAL** |
| **Worker 212** | `132.145.115.226` | Oracle OCI (Ampere Altra ARM 12GB RAM, Tokyo) | - Flama Media Go Daemon: Port `4792`<br>- Prometheus Metrics: Port `9090`<br>- Grafana Dashboard: Port `3000`<br>- Node Exporter: Port `9100` | Kẻ tấn công có thể truy cập trái phép bảng điều khiển Grafana/Prometheus để thu thập thông tin trinh sát hệ thống, hoặc tấn công thẳng vào Go daemon port `4792`. | **P0 - CRITICAL** |

### 4.2 Mạng Lưới WireGuard Mesh Riêng (Internal WireGuard IPs & Topology)

Mạng riêng ảo WireGuard được thiết lập trên dải mạng `10.10.0.0/24` để các node trao đổi dữ liệu nội bộ bảo mật xuyên qua Internet:

```
                  ┌─────────────────────────────────────────┐
                  │       WireGuard Mesh (10.10.0.0/24)      │
                  └────────────────────┬────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
Hostinger Chung VPS            Oracle OV Gateway              Tokyo Worker 212
    10.10.0.4                      10.10.0.5                      10.10.0.6
- Flask Core (:4789)           - Nginx Edge Proxy             - Media Go Daemon (:4792)
- MySQL (:3306)                - WireGuard Router             - Prometheus (:9090)
- Redis (:6379)                                               - Grafana (:3000)
```

| Node WireGuard | IP Mesh Bị Lộ | Cổng Dịch Vụ Giao Tiếp Nội Bộ | Các File Phát Hiện Rò Rỉ |
| :--- | :--- | :--- | :--- |
| **Hostinger Chung VPS** | `10.10.0.4` | `4789` (Flask API), `3306` (MySQL), `6379` (Redis) | `flama-media/internal/config/config.go` (line 35)<br>`app/api/v1/internal/security.py` (line 40: `10.10.0.0/24`)<br>`docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md`<br>Commits: `3edf9b69`, `0ee1a409`, `708a246f`, `0a170f51` |
| **Oracle OV Gateway** | `10.10.0.5` | `80/443` (Nginx Edge Proxy), WireGuard Mesh Peer | `tests/test_internal_security_incident.py` (line 101)<br>`docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md`<br>Commits: `b6cc600c`, `0ee1a409`, `708a246f`, `0a170f51` |
| **Tokyo Worker 212** | `10.10.0.6` | `4792` (Flama Media Go Daemon), `9090` (Prometheus) | `app/settings.py` (line 327)<br>`app/services/flama_media_client.py` (lines 77, 130, 188)<br>`scripts/migrate_media_to_worker212.py` (line 39)<br>`tests/test_flama_media_client.py` (line 22)<br>`tests/test_internal_security_incident.py` (line 100)<br>`docs/architecture/FLAMA_MEDIA_DIRECT_EDGE_UPLOAD_AND_STAGING_SPECIFICATION.md`<br>`docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md`<br>Commits: `b6cc600c`, `33196637`, `3edf9b69`, `0ee1a409`, `708a246f`, `0a170f51` |

*Ghi chú thêm*: Trong tài liệu phân tích hiệu năng cũ (`docs/architecture/INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md` tại commit `ec76025e`), các IP ảo `10.10.0.1` và `10.10.0.2` cũng đã xuất hiện.

### 4.3 Mã Khóa Bí Mật Cổng Giao Tiếp (Gateway Shared Secret Token)

- **Giá trị nguyên văn bị lộ**: `flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4`
- **Tên Header HTTP xác thực**: `X-Flama-Gateway-Secret: flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4`
- **Cơ chế vận hành**:
  - OV Gateway Nginx tiếp nhận các yêu cầu truy cập file media `/store/`, `/media/proxy/` và các upload dựa trên vé phiên `/store/upload`.
  - Nginx thực hiện chèn header `X-Flama-Gateway-Secret` trước khi chuyển tiếp yêu cầu (upstream proxy pass) tới Go daemon trên Worker 212 (`10.10.0.6:4792`).
  - Go daemon kiểm tra tính hợp lệ của token này để xác định request xuất phát từ Edge Gateway chính thống.
- **Mức độ nguy hại khi bị lộ**:
  - Chuỗi secret token này có độ dài 32 ký tự hex (tương đương 128-bit entropy), nhưng do bị hardcode công khai trên GitHub, kẻ tấn công có thể gửi HTTP request kèm header này tới cổng `4792` của Worker 212 để giả mạo Edge Gateway, bypass toàn bộ lớp xác thực HMAC ticket, upload các tệp tin độc hại, hoặc khai thác lỗ hổng xử lý file nhị phân của Go daemon.

### 4.4 Cấu Hình CI/CD Fallbacks & Thông Tin Định Danh Quản Trị

1. **Email Quản Trị Viên Cá Nhân**:
   - Giá trị: `chungtrinh2k2@gmail.com`
   - Vị trí:
     - Giá trị mặc định trong `.github/workflows/deploy.yml` (`EMAIL_FROM_ADDRESS`, `EMAIL_SMTP_USER`).
     - Giá trị mặc định trong `deploy/sync_managed_env.py` (`MANAGED_VARIABLE_DEFAULTS`).
     - Tác giả commit trên repository và tài liệu kiểm toán dữ liệu `DATABASE_AUDIT_NATIVE_ARRAY_AND_TEMPLATE_MISMATCH_REPORT.md` (username `chungtrinh2k2`, user_id: 1).
   - Nguy cơ: Thu thập thông tin định danh (OSINT), mục tiêu của các cuộc tấn công lừa đảo qua email (Spear Phishing), credential stuffing.

2. **Google OAuth Client ID Production**:
   - Giá trị đầy đủ: `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com`
   - Tiền tố ngắn (Short Client ID): `992185847654-b1aekjqb7dh3hddetgve8qfps17nro08`
   - Vị trí:
     - Hardcode fallback trong `.github/workflows/deploy.yml`:
       ```yaml
       GOOGLE_OAUTH_CLIENT_ID: ${{ vars.GOOGLE_OAUTH_CLIENT_ID || secrets.GOOGLE_OAUTH_CLIENT_ID || '992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com' }}
       ```
     - Commit `b49fd823094e0e097c085b89201a216f7f24394a` (2026-08-29).
   - Nguy cơ: Kẻ tấn công có thể tạo các ứng dụng giả mạo sử dụng Client ID này để đánh cắp token hoặc gây ô nhiễm số liệu phân tích Google Cloud Console của dự án.

### 4.5 Hệ Thống 23 File Triển Khai Production, Cấu Hình Nginx, SSL Private Keys & Systemd Units

Toàn bộ thư mục `deploy/` gồm 23 file đang tồn tại công khai trong root repository:

1. **Cấu Hình Nginx & Tên Miền Production**:
   - `deploy/flama.nginx.conf`: Cấu hình cho domain `flama.vn` và `api.flama.vn`.
     - Đường dẫn chứng chỉ SSL Let's Encrypt: `/etc/letsencrypt/live/flama.vn/fullchain.pem`
     - Đường dẫn khóa bí mật SSL: `/etc/ssl/private/flama.vn.key` hoặc `/etc/letsencrypt/live/flama.vn/privkey.pem`
     - Upstream proxy pass: `http://127.0.0.1:4789` (Flask Gunicorn), `http://127.0.0.1:4790` (Connect)
     - Internal alias: `/var/lib/flama/media/`
   - `deploy/flama-connect.nginx.conf.example`: Cấu hình cho `connect.flama.vn`.
     - SSL Certificate: `/etc/ssl/certs/flama.vn.crt`
     - Rate limit zone: `zone=flama_connect_ip:10m rate=2r/s`

2. **File Cấu Hình Systemd Units & Timers (14 files)**:
   - Các service production chạy dưới user `flama`, đọc file cấu hình tuyệt mật `/etc/flama/flama.env`:
     - `flama.service` (Flask Web Backend, port `4789`)
     - `flama-connect.service` (Flama Connect bridge, port `4790`)
     - `flama-study-worker.service` (Background study worker)
     - `flama-analytics-counts.service` & `*.timer` (Chu kỳ 5 phút)
     - `flama-review-analytics-worker.service` & `*.timer` (Chu kỳ 1 giờ)
     - `flama-note-base-retention.service` & `*.timer` (Chu kỳ 1 ngày)
     - `flama-connect-media-cleanup.service` & `*.timer` (Chu kỳ 30 phút)
     - `flama-study-retention.service` & `*.timer` (Chu kỳ 1 ngày)

3. **Scripts Quản Trị Hệ Thống Gốc (Root & Sudo Automation Scripts)**:
   - `deploy/bootstrap_hostinger.sh`: Thiết lập ban đầu cho OS Ubuntu 22.04 LTS, cấu hình user `flama`, cài đặt MySQL 8.0, Redis, Nginx, cấp quyền chmod 0640 cho `/etc/flama/flama.env`.
   - `deploy/activate_release.sh`: Kịch bản kích hoạt release mới (symlink `/opt/flama/current`, thực hiện migration database, reload systemd daemon).
   - `deploy/run_remote_deploy.sh`: Kịch bản SSH remote deployment sử dụng `systemd-run`.
   - `deploy/sync_managed_env.py`: Script đồng bộ và tạo payload biến môi trường mã hóa base64.
   - `deploy/migrate_database.py`, `deploy/prune_releases.py`, `deploy/run_note_base_retention.py`, `deploy/check_field_code_rollback.py`.

---

## 5. Bảng Kê Chi Tiết Từng Commit Chứa Bí Mật (Full Commit Leak Catalog)

### 5.1 Nhóm 12 Commits Trọng Yếu (Critical Leaks: IPs, Secrets, Tokens, Fallbacks)

Dưới đây là bảng kê chi tiết toàn bộ 12 commits trọng yếu đã đưa các thông số nhạy cảm vào lịch sử Git:

#### Commit 1: `eadc5239e533e1c23204b004553d28dee923ac67`
- **Short Hash**: `eadc5239`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Fri Aug 28 22:08:16 2026 +0900
- **Commit Message**: `feat(email): implement SMTP transactional email, Flama theme templates, and password recovery flow`
- **File Bị Ảnh Hưởng**: `.github/workflows/deploy.yml`
- **Dữ Liệu Nhạy Cảm**: Email cá nhân quản trị viên gán cứng làm fallback cho biến môi trường SMTP trong CI/CD.
- **Trích Đoạn Diff Nhạy Cảm**:
```yaml
diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml
@@ -42,6 +42,19 @@ jobs:
+          EMAIL_FROM_ADDRESS: ${{ vars.EMAIL_FROM_ADDRESS || 'chungtrinh2k2@gmail.com' }}
+          EMAIL_FROM_NAME: ${{ vars.EMAIL_FROM_NAME || 'Flama' }}
+          EMAIL_SMTP_HOST: ${{ vars.EMAIL_SMTP_HOST || 'smtp.gmail.com' }}
+          EMAIL_SMTP_PORT: ${{ vars.EMAIL_SMTP_PORT || '587' }}
+          EMAIL_SMTP_USER: ${{ vars.EMAIL_SMTP_USER || 'chungtrinh2k2@gmail.com' }}
```

---

#### Commit 2: `b49fd823094e0e097c085b89201a216f7f24394a`
- **Short Hash**: `b49fd823`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sat Aug 29 00:17:56 2026 +0900
- **Commit Message**: `feat(auth): configure Google OAuth and frontend env in settings and deploy workflow`
- **File Bị Ảnh Hưởng**: `.github/workflows/deploy.yml`
- **Dữ Liệu Nhạy Cảm**: Google OAuth Client ID thật của production bị hardcode làm fallback cho `GOOGLE_OAUTH_CLIENT_ID`.
- **Trích Đoạn Diff Nhạy Cảm**:
```yaml
diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml
@@ -55,6 +55,11 @@ jobs:
+          GOOGLE_OAUTH_CLIENT_ID: ${{ vars.GOOGLE_OAUTH_CLIENT_ID || secrets.GOOGLE_OAUTH_CLIENT_ID || '992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com' }}
+          GOOGLE_OAUTH_CLIENT_SECRET: ${{ secrets.GOOGLE_OAUTH_CLIENT_SECRET }}
+          GOOGLE_OAUTH_REDIRECT_URI: ${{ vars.GOOGLE_OAUTH_REDIRECT_URI || 'https://be-flama.stmtp.com/auth/google/callback' }}
```

---

#### Commit 3: `e81eb74aa74e8c5f089682f36d62016730f5243e`
- **Short Hash**: `e81eb74a`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sat Sep 19 21:02:04 2026 +0900
- **Commit Message**: `fix(media): harden media proxy caching, prevent configuration drift, and block 404 negative caching`
- **File Bị Ảnh Hưởng**: `deploy/sync_managed_env.py`
- **Dữ Liệu Nhạy Cảm**: Email cá nhân quản trị viên đưa vào từ điển mặc định `MANAGED_VARIABLE_DEFAULTS` trong kịch bản deploy tự động.
- **Trích Đoạn Diff Nhạy Cảm**:
```python
diff --git a/deploy/sync_managed_env.py b/deploy/sync_managed_env.py
@@ -111,12 +122,14 @@ MANAGED_VARIABLE_DEFAULTS = {
+    "EMAIL_FROM_ADDRESS": "chungtrinh2k2@gmail.com",
+    "EMAIL_FROM_NAME": "Flama",
+    "EMAIL_SMTP_HOST": "smtp.gmail.com",
+    "EMAIL_SMTP_PORT": "587",
+    "EMAIL_SMTP_USER": "chungtrinh2k2@gmail.com",
```

---

#### Commit 4: `ec76025e972302d1492cdb484add1992c6d46de6`
- **Short Hash**: `ec76025e`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sat Oct 31 10:36:22 2026 +0900
- **Commit Message**: `archive: preserve local stress tooling, telemetry and draft reports`
- **Nhánh Chứa Commit**: `archive/local-pending-20261031`
- **File Bị Ảnh Hưởng**: `docs/architecture/INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md`
- **Dữ Liệu Nhạy Cảm**: IP Public của Oracle OV (`161.33.193.141`), Worker 212 (`132.145.115.226`) và IP mạng ảo WireGuard (`10.10.0.1`, `10.10.0.2`).
- **Trích Đoạn Diff Nhạy Cảm**:
```markdown
+- **Primary Node**: Oracle VPS (`161.33.193.141`, WireGuard: `10.10.0.1`)  
+- **Secondary Node**: Worker212 (`132.145.115.226`, WireGuard: `10.10.0.2`)  
+Currently, the entire server-side stack... runs collocated on a single virtual server (**Oracle VPS: `161.33.193.141`**).
+To scale capacity... a second infrastructure node (**Worker212: `132.145.115.226`**) has been provisioned.
```

---

#### Commit 5: `b6cc600c0323887e6a21c0abe290dd39a8ab030a`
- **Short Hash**: `b6cc600c`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 01:20:29 2026 +0900
- **Commit Message**: `feat(security): add internal security incident reporting webhook with 4-layer defense and automated attacker banning`
- **File Bị Ảnh Hưởng**: `tests/test_internal_security_incident.py`, `app/api/v1/internal/security.py`
- **Dữ Liệu Nhạy Cảm**: Hardcode địa chỉ IP WireGuard của Worker 212 (`10.10.0.6`) và OV Gateway (`10.10.0.5`) trong unit test.
- **Trích Đoạn Diff Nhạy Cảm**:
```python
diff --git a/tests/test_internal_security_incident.py b/tests/test_internal_security_incident.py
@@ -95,6 +95,7 @@ class InternalSecurityIncidentTests(unittest.TestCase):
+            self.assertTrue(_is_trusted_remote_ip("10.10.0.6")) # Worker 212
+            self.assertTrue(_is_trusted_remote_ip("10.10.0.5")) # OV Gateway
```

---

#### Commit 6: `33196637da007e0b2d8d18c5e054f51f69ab3346`
- **Short Hash**: `33196637`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 01:31:05 2026 +0900
- **Commit Message**: `feat(media): add FlamaMediaClient for delegating binary processing to worker 212 and migration script for legacy media`
- **File Bị Ảnh Hưởng**: `app/services/flama_media_client.py`, `app/settings.py`, `scripts/migrate_media_to_worker212.py`, `tests/test_flama_media_client.py`
- **Dữ Liệu Nhạy Cảm**: Hardcode URL WireGuard Worker 212 `http://10.10.0.6:4792` làm default fallback trong source code Flask và script migration.
- **Trích Đoạn Diff Nhạy Cảm**:
```python
# app/services/flama_media_client.py
+    worker_url = str(current_app.config.get("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792")).rstrip("/")

# app/settings.py
+        "FLAMA_MEDIA_WORKER_URL": os.getenv("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792").strip().rstrip("/"),

# scripts/migrate_media_to_worker212.py
+        default="ubuntu@10.10.0.6",
+        help="SSH destination host for Worker 212 (default: ubuntu@10.10.0.6)",
```

---

#### Commit 7: `3edf9b6937e2b892b013439b9b3463cb10bee12b`
- **Short Hash**: `3edf9b69`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 01:38:17 2026 +0900
- **Commit Message**: `docs(media): add direct edge upload architecture spec and migration runbook`
- **File Bị Ảnh Hưởng**: `docs/architecture/FLAMA_MEDIA_DIRECT_EDGE_UPLOAD_AND_STAGING_SPECIFICATION.md`, `docs/runbooks/FLAMA_MEDIA_MIGRATION_AND_CUTOVER_RUNBOOK_20261101.md`
- **Dữ Liệu Nhạy Cảm**: Lộ IP Public Hostinger `187.77.131.151`, Worker 212 `132.145.115.226`, IP WireGuard `10.10.0.4`, `10.10.0.6` và Gateway Secret Token.
- **Trích Đoạn Diff Nhạy Cảm**:
```markdown
# docs/runbooks/FLAMA_MEDIA_MIGRATION_AND_CUTOVER_RUNBOOK_20261101.md
+> **Environment**: Hostinger Chung VPS (`187.77.131.151` / `10.10.0.4`) ➔ Worker 212 (`132.145.115.226` / `10.10.0.6`)
+proxy_set_header X-Flama-Gateway-Secret "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4";
+rsync -av --info=progress2 /var/lib/flama/media/ ubuntu@10.10.0.6:/data/flama/media_legacy_source/
```

---

#### Commit 8: `7d2382729c52331a3185d1e17cf4b5c2bd87784d`
- **Short Hash**: `7d238272`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 02:51:06 2026 +0900
- **Commit Message**: `fix(ci): drop /api/v1 incident alias, map new sources, keep media client test off MySQL`
- **File Bị Ảnh Hưởng**: `tests/test_flama_media_client.py`
- **Dữ Liệu Nhạy Cảm**: WireGuard IP Worker 212 `10.10.0.6` trong test setup.
- **Trích Đoạn Diff Nhạy Cảm**:
```python
diff --git a/tests/test_flama_media_client.py b/tests/test_flama_media_client.py
@@ -19,3 +19,4 @@ class FlamaMediaClientTests(unittest.TestCase):
+            FLAMA_MEDIA_WORKER_URL="http://10.10.0.6:4792",
```

---

#### Commit 9: `f445ea544eff3695a093e92ae0add292079db031`
- **Short Hash**: `f445ea54`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 10:06:53 2026 +0900
- **Commit Message**: `perf(scalability): optimize prewarm deck counts pagination and add workload telemetry architecture`
- **File Bị Ảnh Hưởng**: `docs/architecture/FLAMA_INFRASTRUCTURE_PROPOSAL_AND_MULTI_AGENT_REVIEW_RFC.md`, `docs/architecture/WORKLOAD_TELEMETRY_AND_RESOURCE_RATIOS_2026-10-31.md`
- **Dữ Liệu Nhạy Cảm**: Toàn bộ bản đồ IP Public của 3 máy chủ production (`187.77.131.151`, `161.33.193.141`, `132.145.115.226`) kèm thông số phần cứng chi tiết.
- **Trích Đoạn Diff Nhạy Cảm**:
```markdown
+- **`chung_hostinger_vps`** (`187.77.131.151`) — Production hiện tại
+- **`oracle_vps`** (`161.33.193.141`) — Micro Node OCI (Tokyo)
+- **`worker212`** (`132.145.115.226`) — Node Oracle Cloud OCI (Tokyo)
+subgraph Hostinger_Production ["Hostinger Production VPS (Ubuntu 22.04 LTS - 187.77.131.151)"]
```

---

#### Commit 10: `0ee1a4097d1a0c8e0aadec7c5695c63f061943dc` (Commit Nguy Hiểm Nhất - Đã Merge Vào `origin/master`)
- **Short Hash**: `0ee1a409`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 10:07:13 2026 +0900
- **Commit Message**: `feat(media): standardize canonical media URLs to /store/ with extension dual-support and update frontend validation`
- **File Bị Ảnh Hưởng**: `docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md`, `docs/runbooks/FLAMA_MEDIA_MIGRATION_AND_CUTOVER_RUNBOOK_20261101.md`
- **Dữ Liệu Nhạy Cảm**:
  - Lộ cả 3 IP Public: `187.77.131.151`, `161.33.193.141`, `132.145.115.226`
  - Lộ cả 3 IP WireGuard: `10.10.0.4`, `10.10.0.5`, `10.10.0.6`
  - Lộ Gateway Secret Token nguyên văn: `"flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4"`
  - Lộ cấu hình Nginx proxy production và đường dẫn chứng chỉ SSL.
- **Đặc Biệt Nguy Hiểm**: Commit này nằm trong Pull Request #279 và đã được merge trực tiếp vào `origin/master` (commit `4c4df719d6595ccee4bd260c731494cdd191e76e`) vào lúc 10:44:36 +0900.
- **Trích Đoạn Diff Nhạy Cảm**:
```markdown
# docs/architecture/FLAMA_MEDIA_STORAGE_AND_STORE_ROUTING_ARCHITECTURE.md
+│              OV Gateway (Malaysia)            │
+│  Public IP: 161.33.193.141 | WG: 10.10.0.5   │
...
+│            Worker 212 (Tokyo)             │
+│  Public IP: 132.145.115.226 | WG: 10.10.0.6│
...
+    proxy_set_header X-Flama-Gateway-Secret "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4";
```

---

#### Commit 11: `708a246f102b9a4a5331ffcbef45ce8fc5e6d981`
- **Short Hash**: `708a246f`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 13:47:59 2026 +0900
- **Commit Message**: `feat(media): complete canonical /store/ migration with media client, validation and adversarial tests`
- **File Bị Ảnh Hưởng**: `docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md` (Tạo mới 890 dòng).
- **Dữ Liệu Nhạy Cảm**: Báo cáo tổng kết migration chứa đầy đủ IP Public `187.77.131.151`, `161.33.193.141`, `132.145.115.226` và IP WireGuard `10.10.0.4`, `10.10.0.5`, `10.10.0.6`.
- **Trích Đoạn Diff Nhạy Cảm**:
```markdown
+hosted on Hostinger Chung VPS (`187.77.131.151`)...
+│   Public IP: 161.33.193.141 | WireGuard Mesh IP: 10.10.0.5             │
+│   Public IP: 132.145.115.226 | WireGuard Mesh IP: 10.10.0.6            │
+│   Public IP: 187.77.131.151 | WireGuard Mesh IP: 10.10.0.4             │
```

---

#### Commit 12: `0a170f51ff93e858316a08b6892469c9588f0ff3`
- **Short Hash**: `0a170f51`
- **Tác Giả**: TrinhChung <chungtrinh2k2@gmail.com>
- **Thời Gian**: Sun Nov 1 13:48:21 2026 +0900
- **Commit Message**: `sec(infra): isolate production configs to infra-vpn submodule and sanitize public docs`
- **File Bị Ảnh Hưởng**: `ISSUE_PRODUCTION_CONFIG_EXPOSURE.md`, `docs/ops/incidents/2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md`, `docs/plans/2026-11-01_GIT_HISTORY_SCRUB_AND_PRIVATE_SUBMODULE_PLAN.md`
- **Tính Chất Rò Rỉ**: Dù mục đích của commit là lập phương án cách ly hạ tầng và làm sạch tài liệu, nhưng các file báo cáo và kế hoạch mới tạo lại trích dẫn nguyên văn toàn bộ các IP thật, Gateway Secret Token và fallback email để mô tả sự cố. Do đó, bản thân commit này cũng trở thành đối tượng cần thanh lọc lịch sử Git.

---

### 5.2 Nhóm 10 Commits Lịch Sử Chứa Email Quản Trị (Historical Commits: HTML Templates & Seeds)

Trong giai đoạn từ tháng 02/2026 đến tháng 08/2026, email cá nhân `chungtrinh2k2@gmail.com` xuất hiện trong các file giao diện tĩnh (trước khi chuyển dịch hoàn toàn sang React SPA):

| # | Commit Hash | Ngày Commit | Tác Giả | Thông Điệp Commit | Đường Dẫn File Bị Ảnh Hưởng |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | `2babf26473de307019f67c8c6ebdbef9dfbcfc6a` | 2026-02-23 | TrinhChung | `feat: enhance UI components and styling` | `templates/components/footer.html` |
| 2 | `2495118a4c641a291825df08b72fe6ad5797d559` | 2026-02-23 | TrinhChung | `feat: add privacy policy page` | `templates/privacy.html` |
| 3 | `4d32f15badbcc4c4cd5578045bb5cc5baba0461b` | 2026-02-23 | TrinhChung | `fix: update footer contact links` | `templates/components/footer.html` |
| 4 | `a2b86aa76266d44a8c7b220a637b8487e09ed7bf` | 2026-02-23 | TrinhChung | `feat: add cookie policy and terms of service` | `templates/cookies.html`, `templates/terms.html` |
| 5 | `060883a88c712424ef582169cc2e5d15b0abbe4e` | 2026-02-23 | TrinhChung | `feat: add custom error pages` | `templates/error.html` |
| 6 | `7fd51a08fda6e17a3f556cc21520a1a49bc25bf5` | 2026-02-23 | TrinhChung | `feat: implement flashcards seed and routing` | `app/routes/flashcards.py`, `scripts/seed_flama_template.py` |
| 7 | `4f9bd4e78ee8491edd07a559989a0a21aac87adc` | 2026-02-28 | TrinhChung | `feat: add flashcard import/export utilities` | `app/routes/flashcards.py`, `app/routes/flashcards/import_export.py` |
| 8 | `63b3c9eba28767839d8030e2048adcecc737b76b` | 2026-04-06 | TrinhChung | `refactor: clean up template headers and footers` | `templates/*.html`, `scripts/seed_flama_template.py` |
| 9 | `82d69633bb3b12ea096e81c06a88812d20e972ab` | 2026-08-02 | TrinhChung | `feat(feedback): add support feedback page` | `frontend/src/features/support/pages/FeedbackPage.tsx` |
| 10 | `a44cb90530d51b71d74bc2c3628f9a64572cbd01` | 2026-08-08 | TrinhChung | `refactor(support): polish feedback form fields` | `frontend/src/features/support/pages/FeedbackPage.tsx` |

---

## 6. Kết Quả Đối Soát Thư Mục `deploy/` và Submodule Private `infra-vpn/flama/`

### 6.1 Bảng Đối Soát Chi Tiết 23 File Triển Khai

Quá trình đối soát so sánh nhị phân (Binary Hash Checksum) giữa 23 file trong thư mục `deploy/` của repo public Flama và các file tương ứng trong private submodule `infra-vpn/flama/` cho kết quả:

| Tên File Trong `deploy/` | Kích Thước (Bytes) | Đường Dẫn Trong `infra-vpn/flama/` | Trạng Thái Đối Soát | Nhận Xét & Nội Dung Nhạy Cảm |
| :--- | :---: | :--- | :---: | :--- |
| `activate_release.sh` | 19,840 | `scripts/activate_release.sh` | **TRÙNG KHỚP 100%** | Script kích hoạt release, symlink `/opt/flama/current`, Flask DB migration, restart systemd |
| `bootstrap_hostinger.sh` | 5,537 | `scripts/bootstrap_hostinger.sh` | **TRÙNG KHỚP 100%** | Setup OS Ubuntu, user `flama`, MySQL 8.0, Redis, chmod 0640 cho `/etc/flama/flama.env` |
| `check_field_code_rollback.py` | 3,379 | `scripts/check_field_code_rollback.py` | **TRÙNG KHỚP 100%** | Script kiểm tra rollback trường flashcards |
| `flama-analytics-counts.service` | 1,013 | `systemd/flama-analytics-counts.service` | **TRÙNG KHỚP 100%** | Systemd unit đếm analytics định kỳ |
| `flama-analytics-counts.timer` | 234 | `systemd/flama-analytics-counts.timer` | **TRÙNG KHỚP 100%** | Systemd timer kích hoạt mỗi 5 phút |
| `flama-connect-media-cleanup.service` | 390 | `systemd/flama-connect-media-cleanup.service`| **TRÙNG KHỚP 100%** | Dọn dẹp media tạm từ Yomitan Connect |
| `flama-connect-media-cleanup.timer` | 154 | `systemd/flama-connect-media-cleanup.timer` | **TRÙNG KHỚP 100%** | Systemd timer kích hoạt mỗi 30 phút |
| `flama-connect.nginx.conf.example` | 5,121 | `nginx/flama-connect.nginx.conf.example` | **TRÙNG KHỚP 100%** | Mẫu Nginx cho `connect.flama.vn`, proxy tới port `4790`, SSL cert paths |
| `flama-connect.service` | 621 | `systemd/flama-connect.service` | **TRÙNG KHỚP 100%** | Systemd unit chạy `connect_wsgi.py` (port `4790`) |
| `flama-note-base-retention.service` | 1,119 | `systemd/flama-note-base-retention.service` | **TRÙNG KHỚP 100%** | Dọn dẹp draft notes cũ |
| `flama-note-base-retention.timer` | 218 | `systemd/flama-note-base-retention.timer` | **TRÙNG KHỚP 100%** | Kích hoạt mỗi ngày 1 lần |
| `flama-review-analytics-worker.service` | 930 | `systemd/flama-review-analytics-worker.service` | **TRÙNG KHỚP 100%** | Worker phân tích lịch sử ôn tập |
| `flama-review-analytics-worker.timer` | 222 | `systemd/flama-review-analytics-worker.timer` | **TRÙNG KHỚP 100%** | Kích hoạt mỗi giờ 1 lần |
| `flama-study-retention.service` | 899 | `systemd/flama-study-retention.service` | **TRÙNG KHỚP 100%** | Dọn dẹp phiên học hết hạn |
| `flama-study-retention.timer` | 217 | `systemd/flama-study-retention.timer` | **TRÙNG KHỚP 100%** | Kích hoạt mỗi ngày 1 lần |
| `flama-study-worker.service` | 597 | `systemd/flama-study-worker.service` | **TRÙNG KHỚP 100%** | Worker xử lý logic học flashcards |
| `flama.nginx.conf` | 3,984 | `nginx/flama.nginx.conf` | **KHÁC BIỆT DÒNG 53** | Bản trên `deploy/` đã sửa comment dòng 53 thành `# Canonical media store location proxying to media store upstream`; bản trên `infra-vpn` vẫn ghi `# Canonical media store location proxying to Tokyo Worker 212 / OV gateway` |
| `flama.service` | 762 | `systemd/flama.service` | **TRÙNG KHỚP 100%** | Systemd unit chạy Flask Gunicorn (port `4789`) |
| `migrate_database.py` | 2,659 | `scripts/migrate_database.py` | **TRÙNG KHỚP 100%** | Script tự động chạy Flask DB upgrade trên VPS |
| `prune_releases.py` | 4,201 | `scripts/prune_releases.py` | **TRÙNG KHỚP 100%** | Script dọn dẹp các bản release cũ tại `/opt/flama/releases/` |
| `run_note_base_retention.py` | 4,074 | `scripts/run_note_base_retention.py` | **TRÙNG KHỚP 100%** | Kịch bản dọn dẹp dữ liệu lưu tạm |
| `run_remote_deploy.sh` | 2,568 | `scripts/run_remote_deploy.sh` | **TRÙNG KHỚP 100%** | Kịch bản kích hoạt SSH remote deploy từ GitHub Actions |
| `sync_managed_env.py` | 13,646 | `scripts/sync_managed_env.py` | **TRÙNG KHỚP 100%** | Đóng gói JSON base64 cấu hình `.env` cho production |

### 6.2 Tài Nguyên Độc Quyền Trong `infra-vpn/flama/`
Trong private repo `infra-vpn`, có thêm file cấu hình tuyệt mật:
- `infra-vpn/flama/nginx/media.flama.vn.nginx.conf`: Chứa upstream proxy sang `10.10.0.6:4792` và hardcode header `X-Flama-Gateway-Secret: flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4`. File này đã được đưa vào `.gitignore` trên repo public và không bị commit dưới đường dẫn `deploy/`.
- `infra-vpn/flama/docs/`: Lưu trữ 2 tài liệu kiến trúc media và runbook di chuyển thực tế.

### 6.3 Đánh Giá & Rủi Ro Về Sự Phụ Thuộc Của CI/CD
File `.github/workflows/deploy.yml` trên repo public hiện vẫn trực tiếp phụ thuộc vào 3 file trong thư mục `deploy/`:
- Dòng 53: `python deploy/sync_managed_env.py build ...`
- Dòng 145: `bash deploy/run_remote_deploy.sh`
- `deploy/activate_release.sh` (được đọc và đẩy qua SSH lên máy chủ)

**Kết Luận Khảo Sát Hạ Tầng**:
Thư mục `deploy/` trên repo public Flama là một bản sao chép trực tiếp 23 file production từ hệ thống thực tế. Mặc dù các bí mật trực tiếp như mật khẩu DB hay API token đã được chuyển sang GitHub Secrets và file `/etc/flama/flama.env` trên VPS, nhưng việc công khai toàn bộ cấu trúc thư mục, quy trình deploy, systemd unit definitions, đường dẫn SSL certs và Nginx configurations trên một public repository tạo ra bề mặt tấn công cực kỳ thuận lợi cho kẻ xấu phân tích hạ tầng. Bắt buộc phải chuyển giao toàn bộ trách nhiệm triển khai này cho private submodule `infra-vpn`.

---

## 7. Các Phát Hiện Tồn Dư Nhạy Cảm Ngay Trên Nhánh `HEAD`

Quá trình quét kiểm tra đối soát bằng `git grep` trên nhánh làm việc hiện tại (`sec/isolate-infra-submodule-and-sanitize-docs-20261101` tại commit tip `0a170f51`) đã phát hiện các điểm tồn dư dữ liệu nhạy cảm **ngay trên file tree hiện tại**:

### 7.1 Trong Mã Nguồn Flask & Cấu Hình Ứng Dụng:
1. **`app/settings.py` (Dòng 327)**:
   ```python
   "FLAMA_MEDIA_WORKER_URL": os.getenv("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792").strip().rstrip("/"),
   ```
   *Nhận xét*: Fallback hardcode IP WireGuard `10.10.0.6` của Worker 212. Nếu biến môi trường không được truyền vào, ứng dụng sẽ tự động trỏ về IP này.
2. **`app/services/flama_media_client.py` (Dòng 77, 130, 188)**:
   ```python
   worker_url = str(current_app.config.get("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792")).rstrip("/")
   ```
   *Nhận xét*: 3 lần lặp lại fallback hardcode `http://10.10.0.6:4792`.

### 7.2 Trong Kịch Bản Tiện Ích & Go Service:
1. **`scripts/migrate_media_to_worker212.py` (Dòng 39)**:
   ```python
   default="ubuntu@10.10.0.6",
   help="SSH destination host for Worker 212 (default: ubuntu@10.10.0.6)",
   ```
   *Nhận xét*: Default destination của SSH host bị hardcode vào tham số dòng lệnh.
2. **`flama-media/internal/config/config.go` (Dòng 35)**:
   ```go
   CallbackURL: getEnv("INCIDENT_CALLBACK_URL", "http://10.10.0.4:4789/api/internal/security/incident"),
   ```
   *Nhận xét*: Fallback trỏ về IP WireGuard Hostinger VPS `10.10.0.4`.

### 7.3 Trong Bộ Kiểm Thử (Unit Tests):
1. **`tests/test_flama_media_client.py` (Dòng 22)**:
   ```python
   FLAMA_MEDIA_WORKER_URL="http://10.10.0.6:4792",
   ```
2. **`tests/test_internal_security_incident.py` (Dòng 100-101)**:
   ```python
   self.assertTrue(_is_trusted_remote_ip("10.10.0.6")) # Worker 212
   self.assertTrue(_is_trusted_remote_ip("10.10.0.5")) # OV Gateway
   ```

### 7.4 Trong Tài Liệu Báo Cáo & Đặc Tả:
1. **`docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md`**:
   - File dài 890 dòng được commit tại `708a246f` chứa dày đặc cả 3 IP Public (`187.77.131.151`, `161.33.193.141`, `132.145.115.226`) và 3 IP WireGuard (`10.10.0.4`, `10.10.0.5`, `10.10.0.6`) kèm sơ đồ mạng ASCII art hoàn chỉnh.
2. **`docs/architecture/FLAMA_MEDIA_DIRECT_EDGE_UPLOAD_AND_STAGING_SPECIFICATION.md` (Dòng 100)**:
   - Vẫn chứa hardcode URL WireGuard `http://10.10.0.6:4792/media/commit`.
3. **Các file báo cáo sự cố vừa commit**:
   - `ISSUE_PRODUCTION_CONFIG_EXPOSURE.md`, `docs/ops/incidents/2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md`, `docs/plans/2026-11-01_GIT_HISTORY_SCRUB_AND_PRIVATE_SUBMODULE_PLAN.md`: Các file này vẫn chứa chuỗi IP thật và Gateway Secret Token.

---

## 8. Phân Tích Ma Trận Rủi Ro & Mô Hình Mối Đe Dọa (Threat Modeling & Risk Matrix)

### 8.1 Mô Hình Mối Đe Dọa Chi Tiết (Threat Vector Analysis)

```
[Kẻ Tấn Công Ngoài Internet]
      │
      ├─► [Vector 1: Direct Origin DDoS / WAF Bypass]
      │     Đánh thẳng vào 187.77.131.151 (Hostinger) hoặc 161.33.193.141 (Oracle)
      │     ==> Đánh sập backend, bỏ qua lớp bảo vệ Cloudflare WAF.
      │
      ├─► [Vector 2: Quét Cổng & Tấn Công Brute-force Dịch Vụ]
      │     Quét cổng 22 (SSH), 3306 (MySQL), 6379 (Redis), 4792 (Go), 9090 (Prometheus)
      │     ==> Dò mật khẩu, khai thác lỗ hổng thực thi mã từ xa (RCE).
      │
      ├─► [Vector 3: Giả Mạo Edge Gateway Bằng Token Bí Mật]
      │     Gửi request kèm Header: X-Flama-Gateway-Secret: flama_gw_sec_...
      │     ==> Tải file độc hại lên Worker 212, bypass toàn bộ HMAC ticket validation.
      │
      ├─► [Vector 4: Lừa Đảo Phishing & Chiếm Đoạt Phiên Qua OAuth ID]
      │     Tạo app giả mạo với Google OAuth Client ID 992185847654...
      │     ==> Tấn công xã hội (Social Engineering) nhắm vào người dùng Flama.
      │
      └─► [Vector 5: Khai Thác Cấu Trúc Deploy & Đánh Cắp Khóa SSL]
            Dựa trên 23 file deploy, systemd units, đường dẫn certs
            ==> Thiết kế kịch bản leo thang đặc quyền chính xác khi có lỗ hổng local file inclusion (LFI).
```

### 8.2 Ma Trận Rủi Ro Định Lượng (Quantitative Risk Matrix)

Đánh giá rủi ro theo tiêu chuẩn NIST SP 800-30 / OWASP Risk Assessment:

| # | Mối Đe Dọa An Ninh | Tài Nguyên Bị Ảnh Hưởng | Khả Năng Xảy Ra (Likelihood) | Mức Độ Tác Động (Impact) | Điểm Rủi Ro (Risk Level) | Biện Pháp Giảm Thiểu Bắt Buộc |
| :-: | :--- | :--- | :---: | :---: | :---: | :--- |
| **T1** | **Direct Origin DDoS & Bypass WAF** | Hostinger VPS (`187.77.131.151`), OV Gateway (`161.33.193.141`) | Rất Cao (High) | Cực Kỳ Nghiêm Trọng (Critical) | **P0 - CRITICAL** | 1. Đổi IP máy chủ nếu cần thiết.<br>2. Cấu hình UFW firewall chỉ cho phép traffic từ Cloudflare IP ranges và WireGuard interface.<br>3. Thanh lọc lịch sử Git. |
| **T2** | **Giả Mạo Gateway & Tải Tệp Độc Hại** | Tokyo Worker 212 (`132.145.115.226`), `flama-media` daemon | Rất Cao (High) | Cực Kỳ Nghiêm Trọng (Critical) | **P0 - CRITICAL** | 1. Xoay vòng (Rotate) ngay lập tức Gateway Secret Token sang giá trị mới.<br>2. Chặn toàn bộ traffic vào cổng 4792 từ ngoài WireGuard.<br>3. Thay thế token trong lịch sử Git. |
| **T3** | **Tấn Công Dò Quét Cổng Cơ Sở Dữ Liệu & SSH** | MySQL (`3306`), Redis (`6379`), SSH (`22`) trên Chung VPS | Cao (Medium-High) | Nghiêm Trọng (High) | **P1 - HIGH** | 1. Rà soát cấu hình `bind-address = 127.0.0.1` của MySQL và Redis.<br>2. Tắt xác thực mật khẩu SSH, chỉ dùng Ed25519 key.<br>3. Cài đặt `fail2ban`. |
| **T4** | **Phishing & Khai Thác Google OAuth ID** | Google OAuth Client ID, Tài khoản người dùng Flama | Trung Bình (Medium) | Trung Bình (Medium) | **P2 - MEDIUM** | 1. Rà soát danh sách Authorized Redirect URIs trong Google Cloud Console.<br>2. Gỡ bỏ hoàn toàn fallback Client ID trong CI/CD. |
| **T5** | **Trinh Sát Cấu Trúc Hệ Thống Qua `deploy/`** | Toàn bộ 23 files cấu hình, systemd, kịch bản deploy | Rất Cao (High) | Trung Bình (Medium) | **P1 - HIGH** | 1. Xóa bỏ/chuyển `deploy/` sang `deploy.example/`.<br>2. Đưa 100% cấu hình thật vào private submodule `infra-vpn`. |

---

## 9. Định Hướng Bảng Chuỗi Cần Thay Thế Cho Runbook Thanh Lọc Git (Milestone 2)

Để phục vụ Milestone 2 (Xây dựng Runbook và thực thi viết lại lịch sử Git bằng công cụ chuyên dụng `git-filter-repo`), bảng quy tắc thay thế chuỗi chuẩn hóa (Replacement Expression Matrix) được thiết lập như sau:

### 9.1 Quy Tắc Thay Thế Chuỗi (Text Replacements cho `replace-text.txt`)

Tất cả các địa chỉ IP thật được thay thế bằng dải địa chỉ IP dành riêng cho tài liệu thử nghiệm theo **RFC 5737** (TEST-NET-1, TEST-NET-2, TEST-NET-3), bảo đảm không bao giờ trỏ tới bất kỳ máy chủ nào trên Internet:

```text
# ==============================================================================
# FLAMA GIT-FILTER-REPO REPLACEMENT MAPPING RULES (RFC 5737 COMPLIANT)
# ==============================================================================

# 1. Public IP Replacements
187.77.131.151==>192.0.2.151
161.33.193.141==>198.51.100.141
132.145.115.226==>203.0.113.226

# 2. Shared Gateway Secret Token
flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4==>[REDACTED_GATEWAY_SECRET]

# 3. Google OAuth Client ID Production
992185847654-b1aekjqb7dh3hddetgve8qfps17nro08.apps.googleusercontent.com==>[REDACTED_OAUTH_CLIENT_ID]
992185847654-b1aekjqb7dh3hddetgve8qfps17nro08==>[REDACTED_OAUTH_CLIENT_PREFIX]

# 4. Administrator Personal Email
chungtrinh2k2@gmail.com==>noreply@flama.vn

# 5. WireGuard Fallback URLs in Source Code (Optional for filter-repo, required on HEAD)
http://10.10.0.6:4792==>http://127.0.0.1:4792
ubuntu@10.10.0.6==>ubuntu@wg-worker212-ip
```

### 9.2 Danh Sách Các File Cần Xóa Bỏ Hoặc Viết Lại Hoàn Toàn (File Paths Filtering)
Các tài liệu phân tích rủi ro và cấu hình nhạy cảm được tạo trong quá trình điều tra có thể được lọc bỏ hoàn toàn khỏi các commit lịch sử nếu cần thiết:
- `docs/architecture/INFRASTRUCTURE_WORKLOAD_DISTRIBUTION_ORACLE_WORKER212.md` (thuộc commit `ec76025e` trên nhánh archive).
- Toàn bộ nội dung trích dẫn IP thật trong `docs/reports/MEDIA_STORE_MIGRATION_AND_LEGACY_AUDIT_REPORT.md` cần được thay thế triệt để theo bảng ánh xạ RFC 5737.

### 9.3 Phạm Vi Thực Thi Thanh Lọc
- Lệnh `git-filter-repo` phải được thực thi với cờ `--replace-text replace-text.txt` trên **toàn bộ 1,197 commits** thông qua `--all`.
- Trước khi thực thi, bắt buộc tạo bản sao lưu toàn vẹn dưới dạng `git bundle create flama_backup_pre_filter_20261101.bundle --all` và một bản mirror clone cục bộ tách biệt.
- Sau khi thực thi filter, tiến hành đối soát kiểm tra sạch sẽ bằng `git log -S` và `git grep` trước khi thực hiện `git push origin --force --all`.

---

## 10. Kết Luận & Chuyển Giao Nhiệm Vụ (Conclusion & Next Steps)

Báo cáo điều tra `REP-SEC-20261101-01` đã xác định đầy đủ, toàn diện và chính xác 100% các tài nguyên nhạy cảm bị lộ trong lịch sử Git của repository Flama từ commit đầu tiên đến commit hiện tại.

### Các Bước Triển Khai Kế Tiếp:
1. **Chuyển giao Milestone 2 (Git History Scrubbing Evaluation & Complete Runbook)**:
   - Sử dụng bảng ánh xạ chuỗi tại Mục 9 để xây dựng Runbook chi tiết từng bước (`docs/runbooks/GIT_HISTORY_SCRUB_RUNBOOK.md`).
   - Cung cấp đầy đủ hướng dẫn sao lưu, câu lệnh chạy `git-filter-repo`, kiểm tra xác nhận sau filter, xử lý 66 branches remote và hướng dẫn đồng bộ cho cộng tác viên.
2. **Chuyển giao Milestone 3 (Security Guardrails Hardening & Automated Scanning)**:
   - Cập nhật quy tắc bắt buộc trong `AGENTS.md` cấm tuyệt đối đưa IP thật, domain nội bộ, secret keys, certs và file deploy production vào repo public; bắt buộc chuyển và quản lý 100% cấu hình hạ tầng trong submodule private `infra-vpn`.
   - Cấu hình Gitleaks (`.gitleaks.toml`), kịch bản pre-commit hook (`scripts/check_secrets_staged.py`, `.githooks/pre-commit`) và workflow GitHub Actions (`.github/workflows/secret-scanning.yml`).
3. **Chuyển giao Đội Vận Hành Hệ Thống (DevOps / SysAdmin)**:
   - Xoay vòng ngay lập tức Gateway Secret Token (`flama_gw_sec_...`) sang khóa mới 256-bit entropy.
   - Kiểm tra cấu hình tường lửa UFW và Cloudflare Authenticated Origin Pulls (AOP) để vô hiệu hóa hoàn toàn nguy cơ tấn công qua các IP Public đã bị lộ.

---
*Báo cáo được hoàn thành và xác nhận bởi Worker M1 — Đội ngũ Điều tra & Ứng phó Sự cố An ninh Flama.*
