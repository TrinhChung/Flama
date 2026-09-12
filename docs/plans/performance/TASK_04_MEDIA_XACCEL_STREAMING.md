# Kế hoạch Tối ưu #04: Kích hoạt Nginx X-Accel-Redirect cho Media Proxy Streaming

> **Mã Task:** `PERF-MEDIA-04`  
> **Mức độ ưu tiên:** 🟡 P2 (Medium-High - Tối ưu tài nguyên mạng và giải phóng WSGI thread khi phát âm thanh/hình ảnh)  
> **Trạng thái:** DỰ THẢO CHỜ DUYỆT (PROPOSED)  
> **Phạm vi tác động:** Route Media Proxy ([`app/routes/flashcards/media.py`](file:///d:/Project/nihongo/app/routes/flashcards/media.py)), Nginx Production Configuration, App Settings  
> **Tài liệu tham chiếu:** [`app/routes/flashcards/media.py`](file:///d:/Project/nihongo/app/routes/flashcards/media.py#L180-L227), [`app/settings.py`](file:///d:/Project/nihongo/app/settings.py)

---

## 1. Vấn đề Kỹ thuật Cần Giải quyết

### 1.1 Hiện trạng mã nguồn
Mọi yêu cầu nghe phát âm audio, xem ảnh thẻ từ vựng hoặc xem nét chữ Kanji đều đi qua endpoint `/media/proxy/<asset_id>`.

Tại [`app/routes/flashcards/media.py`](file:///d:/Project/nihongo/app/routes/flashcards/media.py#L202-L216):
```python
if request.if_none_match.contains(asset.sha256):
    response = current_app.response_class(status=304)
elif current_app.config.get("MEDIA_PROXY_USE_XACCEL", False):
    # Production: Nginx serves the validated file while Gunicorn is freed.
    response = current_app.response_class()
    relative_url_path = Path(asset.storage_path).as_posix().lstrip("/")
    response.headers["X-Accel-Redirect"] = quote(
        f"/internal-media/{relative_url_path}",
        safe="/",
    )
    response.headers["Content-Type"] = asset.mime_type
else:
    # Development / test fallback: Flask streams the file.
    response = send_file(
        full_path, mimetype=asset.mime_type, conditional=True,
    )
```

### 1.2 Điểm nghẽn
1. **Flask/Python giữ socket truyền file tĩnh:** Khi `MEDIA_PROXY_USE_XACCEL` tắt hoặc chưa được cấu hình ở Nginx, Flask chạy fallback `send_file()`. Luồng Python (Gunicorn worker) phải trực tiếp đọc từng block dữ liệu nhị phân từ ổ đĩa và ghi vào TCP socket tới client.
2. **Khóa luồng trên mạng chậm:** Một file audio $\approx 100\text{KB}$ phát trên mạng 4G/Wifi mất khoảng $100\text{ms} - 300\text{ms}$ để truyền xong. Trong suốt thời gian này, luồng Gunicorn bị giữ cứng chỉ để đợi socket client nhận dữ liệu.
3. **Cạn kiệt worker pool:** Trong một buổi học, 10 học viên đồng thời lật thẻ và nghe âm thanh sẽ tạo ra $\approx 50 - 100$ media requests liên tục mỗi giây, chiếm toàn bộ 8 worker slots của Gunicorn, khiến các request API học tập khác bị xếp hàng chờ.

---

## 2. Giải pháp Kỹ thuật (Technical Mechanism)

Cấu hình Nginx `X-Accel-Redirect` (Cơ chế Internal Zero-Copy Streaming):

```text
TRƯỚC TỐI ƯU (Flask send_file):
Browser ──(HTTP GET /media/proxy/xyz)──► Nginx ──► Gunicorn/Flask
                                                      │ (Đọc file từ Disk)
                                                      │ (Stream từng byte qua socket)
Browser ◄───(Tải file kéo dài 200ms)───────────────────┘ (Worker bị block 200ms)

SAU TỐI ƯU (Nginx X-Accel-Redirect):
1. Browser ──(HTTP GET /media/proxy/xyz)──► Nginx ──► Gunicorn/Flask
2. Gunicorn kiểm tra quyền + Asset ID (< 1ms)
3. Gunicorn ──(Header X-Accel-Redirect: /internal-media/xyz.wav)──► Nginx
   ==> GUNICORN GIẢI PHÓNG WORKER NGAY TẠI ĐÂY (Tốn đúng 1ms)!
4. Nginx (C / epoll / sendfile kernel zero-copy) ──► Trực tiếp stream file cho Browser!
```

### Chi tiết cấu hình Nginx
Bổ sung một block `internal` vào file cấu hình Nginx production:
```nginx
# Cấu hình trong file virtual host Nginx (/etc/nginx/sites-available/flama)
location /internal-media/ {
    internal; # Nghiêm cấm client bên ngoài gọi trực tiếp
    alias /var/lib/flama/uploads/flashcard_media/; # Hoặc đường dẫn FLASHCARD_MEDIA_UPLOAD_ROOT
    
    # Tối ưu hóa bộ đệm và kernel zero-copy
    sendfile on;
    sendfile_max_chunk 512k;
    tcp_nopush on;
    tcp_nodelay on;
    
    # Cache phía trình duyệt
    expires 30d;
    add_header Cache-Control "public, max-age=2592000, immutable";
}
```

Và bật cờ trong file cấu hình ứng dụng (`.env`):
```ini
MEDIA_PROXY_USE_XACCEL=1
```

---

## 3. Tính toán Định lượng Cụ thể (Quantitative Impact)

* Giả sử một phiên ôn tập gồm 50 thẻ từ vựng (50 file phát âm audio $\approx 80\text{KB}$/file):

| Tiêu chí đo lường | Trước khi tối ưu (Flask `send_file`) | Sau khi tối ưu (Nginx `X-Accel-Redirect`) | Mức độ cải thiện |
|---|---|---|:---:|
| **Thời gian chiếm dụng luồng Python** | $50 \text{ file} \times 150\text{ms} = \mathbf{7.5\text{ giây}}$ | $50 \text{ file} \times 1\text{ms} = \mathbf{50\text{ms}}$ | **Giảm 99.3% thời gian giữ worker** |
| **Năng lực phục vụ media đồng thời** | $\approx 20 - 40$ requests/giây (bị trần bởi 8 Gunicorn threads) | $\mathbf{> 10.000}$ requests/giây (Nginx xử lý tầng kernel) | **Tăng tải hơn 250 lần** |
| **Mức tiêu thụ CPU/RAM của Gunicorn** | Cao (đọc ghi buffer nhị phân liên tục) | Gần như bằng 0 (chỉ trả Header) | **Tiết kiệm tối đa tài nguyên** |
| **Bảo mật và Phân quyền** | Có kiểm tra quyền trước khi gửi file | Vẫn giữ 100% kiểm tra quyền tại Flask | **An toàn tuyệt đối** |

---

## 4. Kế hoạch Triển khai (Checklist)

- [ ] **Config:** Xác nhận đường dẫn `FLASHCARD_MEDIA_UPLOAD_ROOT` tuyệt đối trên server production.
- [ ] **Nginx:** Cập nhật file cấu hình Nginx production bổ sung `location /internal-media/` với directive `internal;`.
- [ ] **Nginx:** Kiểm tra cú pháp cấu hình `nginx -t` và reload service `systemctl reload nginx`.
- [ ] **App Environment:** Thiết lập `MEDIA_PROXY_USE_XACCEL=1` trong `.env` của Gunicorn service.
- [ ] **Verification:** Dùng `curl -I https://flama.vn/media/proxy/<sample_asset_id>` để xác minh file tải về thành công và response không bị lộ Header `X-Accel-Redirect` ra ngoài.
