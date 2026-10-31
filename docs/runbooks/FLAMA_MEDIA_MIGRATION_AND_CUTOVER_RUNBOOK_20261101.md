# Runbook: Di chuyển Dữ liệu 3.1GB & Chuyển giao Hệ thống Flama Media

> **Operational Runbook & Migration Guide**  
> **Date**: 2026-11-01  
> **Author**: Antigravity Pair-Programming Agent  
> **Status**: Ready for Execution  
> **Environment**: Hostinger Chung VPS (`187.77.131.151` / `10.10.0.4`) ➔ Worker 212 (`132.145.115.226` / `10.10.0.6`)

---

## 1. Mục tiêu & Hiện trạng Dữ liệu (Pre-flight Audit)

- **Mục tiêu**: Di chuyển an toàn 100% dữ liệu media hiện tại từ ổ cứng VPS Chung sang Worker 212 (Tokyo), chuyển giao hoàn toàn quyền phục vụ media sang `media.flama.vn` (OV Gateway ➔ 212).
- **Nguyên tắc cốt lõi**: **Zero Broken Links** (Tuyệt đối không làm chết link audio hay ảnh trên bất kỳ thẻ flashcard nào của người dùng).
- **Dữ liệu thực tế tại VPS Chung**:
  - Đường dẫn nguồn: `/var/lib/flama/media/`
  - Dung lượng: **`3.1 GB`**
  - Số lượng bản ghi `media_assets`: ~25,000+ files.
  - Định dạng URL trong database (`notes.field_values_by_id`): `/media/proxy/<uuid>` (Ví dụ: `/media/proxy/160ad0b0-7fd5-4d33-af96-d50cb0cb9102`).

---

## 2. Chiến lược Định danh Kép (Dual-Addressing Strategy)

### Vì sao không thể chỉ copy file sang SHA-256?
- `flama-media` lưu file theo chuẩn CAS (SHA-256): `/data/flama/media/ab/cd/<sha256>.<ext>`.
- Nhưng các thẻ cũ trong database lại đang lưu đường dẫn theo UUID (`/media/proxy/<uuid>`).
- Nếu chỉ lưu theo SHA-256, toàn bộ thẻ cũ sẽ bị **404 Not Found**.

### Giải pháp: Liên kết kép CAS vật lý + Symlink UUID
1. File vật lý được lưu tại cây thư mục CAS SHA-256:
   ```text
   /data/flama/media/6c/7a/6c7a773bffa27a9d02f6c9921f7733c3c505a6d5ef10dde8a05f78e9339243d5.mp3
   ```
2. Tạo một Symlink theo UUID tương ứng trỏ vào file CAS:
   ```text
   /data/flama/media/16/0a/160ad0b0-7fd5-4d33-af96-d50cb0cb9102.mp3
   ──► ../../6c/7a/6c7a773bffa27a9d02f6c9921f7733c3c505a6d5ef10dde8a05f78e9339243d5.mp3
   ```
3. **Kết quả**:
   - Khi client gọi `/media/proxy/160ad0b0...` (UUID cũ): Worker 212 tìm thấy symlink và phát file bình thường.
   - Khi client upload mới gọi `/media/proxy/6c7a77...` (SHA256 mới): Worker 212 tìm thấy file CAS trực tiếp.
   - **100% thẻ cũ và mới đều hoạt động hoàn hảo, không cần chạy bất kỳ câu lệnh SQL UPDATE nào trên database!**

---

## 3. Các bước Thực hiện Chi tiết (Step-by-Step Execution)

### Bước 1: Đồng bộ dữ liệu khối 3.1GB sang Máy 212 qua WireGuard
Trên **VPS Chung** (`root@187.77.131.151`), chạy lệnh `rsync` truyền tải dữ liệu trực tiếp qua mạng WireGuard Mesh sang Máy 212:

```bash
# Tạo thư mục nhận tạm thời trên Máy 212
ssh -o StrictHostKeyChecking=no ubuntu@10.10.0.6 "mkdir -p /data/flama/media_legacy_source"

# Đồng bộ toàn bộ 3.1GB sang Máy 212 (băng thông WireGuard ~50-100MB/s mất khoảng 1-2 phút)
rsync -avz --progress /var/lib/flama/media/ ubuntu@10.10.0.6:/data/flama/media_legacy_source/
```

### Bước 2: Chạy Script xây dựng cấu trúc CAS & Symlink
Trên **VPS Chung**, chạy script di chuyển đã chuẩn bị sẵn để tạo cây thư mục CAS và symlink tự động từ cơ sở dữ liệu:

```bash
cd /opt/flama/current
/opt/flama/venv/bin/python scripts/migrate_media_to_worker212.py
```

*Script sẽ duyệt qua toàn bộ bản ghi `MediaAsset` trong MySQL, đặt file vào đúng vị trí `/data/flama/media/{sha[0:2]}/{sha[2:4]}/{sha}.{ext}` và tạo symlink theo `{uuid[0:2]}/{uuid[2:4]}/{uuid}.{ext}`.*

### Bước 3: Kiểm thử Khói (Smoke Test) URL Media Cũ
Chọn một `asset_id` cũ từ database và kiểm tra xem `media.flama.vn` có phát được không:

```bash
# Thử nghiệm với file audio thực tế
curl -I https://media.flama.vn/media/proxy/160ad0b0-7fd5-4d33-af96-d50cb0cb9102

# Kết quả kỳ vọng:
# HTTP/1.1 200 OK
# Content-Type: audio/mpeg
# X-Content-Type-Options: nosniff
```

### Bước 4: Kích hoạt Chế độ Staging & Commit trên `flama-media`
1. Đảm bảo `flama-media` trên 212 chạy phiên bản có hỗ trợ endpoint `POST /media/commit` và background auto-cleanup worker.
2. Kiểm tra log của `flama-media.service` trên 212:
   ```bash
   journalctl -u flama-media -n 20 --no-pager
   ```

### Bước 5: Chuyển hướng Traffic Media cũ trên Nginx VPS Chung
Trên **VPS Chung**, cấu hình Nginx trong `/etc/nginx/sites-available/api.flama.vn`:
Chuyển `location ^~ /media/proxy/` từ trỏ vào Gunicorn sang proxy thẳng sang 212 (hoặc 301 chuyển hướng sang `media.flama.vn`):

```nginx
location ^~ /media/proxy/ {
    # Proxy trực tiếp sang Worker 212 qua WireGuard, giải phóng hoàn toàn Gunicorn
    proxy_pass http://10.10.0.6:4792;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Flama-Gateway-Secret "flama_gw_sec_e4b2a0f8c6d4e2a0b8c6d4e2a0b8c6d4";

    expires 30d;
    add_header Cache-Control "public, no-transform";
}
```
Reload Nginx:
```bash
nginx -t && systemctl reload nginx
```

---

## 4. Kế hoạch Dự phòng & Rollback (Disaster Recovery)

Nếu xảy ra bất kỳ sự cố nào trong quá trình chuyển giao:
1. **Dữ liệu gốc trên VPS Chung (`/var/lib/flama/media/`) được giữ nguyên 100%**, không bị xóa hay sửa đổi.
2. Nếu 212 gặp trục trặc mạng:
   Chỉ cần khôi phục lại cấu hình Nginx cũ trên VPS Chung trỏ về Gunicorn local (`proxy_pass http://127.0.0.1:4789`).
   ```bash
   cp /etc/nginx/sites-available/api.flama.vn.bak /etc/nginx/sites-available/api.flama.vn
   systemctl reload nginx
   ```
   Hệ thống ngay lập tức trở về trạng thái hoạt động ban đầu mà không mất mát dữ liệu.
