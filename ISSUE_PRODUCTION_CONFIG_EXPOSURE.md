# [P0 ISSUE] Khẩn cấp: Rò rỉ Cấu hình Server Production trên Public Git & Kế hoạch Cô lập sang Private Submodule

> **Mã sự cố**: `SEC-INCIDENT-20261101-01`  
> **Mức độ nghiêm trọng**: **P0 - CRITICAL / KHẨN CẤP**  
> **Repository bị ảnh hưởng**: `https://github.com/TrinhChung/Flama` (Hiện trạng: **PUBLIC**)  
> **Tài liệu sự cố chi tiết**: [2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md](docs/ops/incidents/2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md)

---

## 1. Mô tả Vấn đề (Issue Description)

Repository `Flama` trên GitHub hiện đang ở chế độ **Public**, nhưng trong quá trình phát triển và triển khai gần đây, nhiều thông tin nhạy cảm ở cấp độ máy chủ production và hạ tầng mạng đã bị commit và đẩy (push) trực tiếp lên nhánh `master`:

1. **Lộ Địa chỉ IP Public thật và Topology mạng nội bộ WireGuard**:
   - `192.0.2.151` (Hostinger Chung VPS - Primary Backend & DB) - WireGuard `wg-app-server`
   - `198.51.100.141` (Oracle VPS - OV Gateway Nginx) - WireGuard `wg-gateway`
   - `203.0.113.226` (Worker 212 Tokyo - Flama Media Go Daemon) - WireGuard `wg-worker212`
   *(Đã bị commit trực tiếp trong `docs/architecture/` và `docs/runbooks/` tại commit `0ee1a409`)*.
2. **Lộ Chuỗi Khóa Bí Mật Xác thực Cổng (Gateway Secret Token)**:
   - Secret token: `"REDACTED_GATEWAY_SECRET"`
   - Bị commit công khai trong tài liệu kiến trúc dòng 81 & 195, đồng thời nằm trong file Nginx config `deploy/media.flama.vn.nginx.conf`.
3. **Phơi bày Thư mục `deploy/` chứa Scripts Vận hành Production**:
   - Toàn bộ scripts quản trị: `bootstrap_hostinger.sh`, `activate_release.sh`, `run_remote_deploy.sh`, `sync_managed_env.py`.
   - Các file systemd unit services và cấu hình Nginx chi tiết kèm đường dẫn private key SSL.
4. **Lộ Email cá nhân và OAuth Client ID trong Workflow**:
   - Trong `.github/workflows/deploy.yml` chứa email cá nhân quản trị viên và Google OAuth Client ID trong giá trị fallback.

---

## 2. Nguy cơ An ninh Trực tiếp (Security Risks)

- **Bypass Cloudflare WAF**: Kẻ tấn công biết chính xác IP gốc của các server (`192.0.2.151`, `198.51.100.141`, `203.0.113.226`), có thể bypass hoàn toàn lớp bảo vệ Cloudflare để tấn công DDoS trực tiếp hoặc scan cổng dịch vụ.
- **Giả mạo Cổng Gateway**: Token `REDACTED_GATEWAY_SECRET` bị lộ cho phép kẻ xấu giả mạo Edge Gateway gửi request trực tiếp vào Go daemon tại Worker 212.
- **Tấn công Dò quét Dịch vụ**: Cổng backend 4789, 4790, 4792 và SSH có thể bị tấn công brute-force.

---

## 3. Các Hành động Cần xử lý Ngay (Emergency Checklist)

- [ ] **Rotate Secret ngay lập tức**: Sinh token mới cho `X-Flama-Gateway-Secret` trên OV Gateway và Worker 212 Go daemon.
- [ ] **Khóa Tường lửa (Firewall Hardening)**: Kiểm tra UFW/OCI Security List đảm bảo chỉ mở cổng 80/443 cho IP Cloudflare; chặn toàn bộ truy cập public vào cổng 4789, 4790, 4792, 3306, 6379.
- [ ] **Tạm thời chuyển Repo sang Private (Khuyến nghị)**: Đổi repo GitHub sang Private trong quá trình dọn dẹp để ngăn chặn bot crawler/scanners quét secret.
- [ ] **Thanh lọc Lịch sử Git (Scrub Git History)**: Dùng `git-filter-repo` để xóa vĩnh viễn IP thực và secret token khỏi các commit cũ trên GitHub.

---

## 4. Giải pháp Kiến trúc: Cô lập sang Private Git Submodule

Để mã nguồn ứng dụng (Frontend, Backend, Database Models) vẫn có thể mở (Open/Public) mà **không làm lộ bất kỳ thông tin hạ tầng nào**:

### Mô hình tách biệt:
1. **Public Repo `TrinhChung/Flama`**:
   - Chỉ giữ mã nguồn sản phẩm, tài liệu mở (với IP giả lập RFC 5737 như `203.0.113.1`), file cấu hình generic `.example`.
   - Xóa bỏ thư mục `deploy/` thực tế khỏi repo public.
2. **Private Repo `TrinhChung/flama-infra` (hoặc `flama-deploy`)**:
   - Khởi tạo repo riêng ở chế độ **Private**.
   - Chuyển toàn bộ scripts deploy (`activate_release.sh`, `bootstrap_hostinger.sh`), systemd units, Nginx production configs, và runbook chứa IP thực tế sang repo này.
3. **Liên kết qua Git Submodule**:
   - Nhúng `flama-infra` vào repo chính dưới dạng submodule private (ví dụ: `deploy/` hoặc `infra/`).
   - Người ngoài xem repo public sẽ chỉ thấy submodule trỏ đến private repo và nhận 404 nếu không có quyền truy cập.
4. **CI/CD GitHub Actions**:
   - Thiết lập Deploy Key hoặc GitHub PAT trong Secrets (`INFRA_DEPLOY_SUBMODULE_TOKEN`) để workflow `deploy.yml` tự động checkout submodule private an toàn trong môi trường runner kín.

---

*Chi tiết đầy đủ về bằng chứng kiểm tra, phân tích mối đe dọa và hướng dẫn kỹ thuật từng bước có tại:*  
[`docs/ops/incidents/2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md`](docs/ops/incidents/2026-11-01_SECURITY_ISSUE_PRODUCTION_CONFIG_EXPOSURE.md)
