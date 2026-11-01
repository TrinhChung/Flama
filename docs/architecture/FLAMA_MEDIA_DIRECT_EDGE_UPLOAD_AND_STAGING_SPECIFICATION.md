# Flama Media: Direct Edge Upload & Two-Phase Staging Architecture

> **Architecture Specification & Design Contract**  
> **Date**: 2026-11-01  
> **Status**: Approved for Implementation  
> **Subsystems**: `flama-media` (Worker 212 Go Daemon, Tokyo), `app` (Flask Monolith, Malaysia), `frontend` (React SPA)

---

## 1. Bối cảnh & Lý do Kiến trúc (Motivation)

### 1.1. Hiện trạng Hạ tầng Vật lý
- **VPS Chung (Chính)**: Đặt tại datacenter Hostinger (Malaysia / Singapore), chạy ứng dụng Flask REST Monolith và cơ sở dữ liệu MySQL 8.0.
- **Worker 212 & OV Gateway**: Đặt tại Oracle Cloud Tokyo (NRT), chạy `flama-media` daemon (Pure Go) chịu trách nhiệm lưu trữ ổ SSD `/data/flama/media` và phát media tốc độ cao qua `https://media.flama.vn`.
- Hai cụm server kết nối với nhau qua mạng riêng ảo WireGuard Mesh (`<wg-subnet>`) với RTT ~73ms.

### 1.2. Nhược điểm của luồng Upload truyền thống (Đi vòng qua VPS Chung)
Nếu Frontend gửi file trực tiếp lên VPS Chung rồi VPS Chung stream sang 212:
1. **Nhân đôi độ trễ (Double-Hop Latency)**: File nhị phân nặng phải di chuyển 2 chặng: `Client -> Malaysia -> Tokyo`. Một file audio hoặc ảnh 5–10MB sẽ mất hàng giây tải lên.
2. **Nghẽn tài nguyên VPS Chung**: VPS Chung phải đệm multipart form vào RAM/ổ đĩa tạm, tiêu tốn CPU xử lý I/O và băng thông của server chính.

### 1.3. Giải pháp: Kiến trúc Direct Edge Upload (Tải thẳng lên Tokyo)
Thay vì đi vòng, **Frontend sẽ gửi trực tiếp luồng nhị phân lên Tokyo (`media.flama.vn`)**, sau đó gửi metadata xác thực về **VPS Chung (Malaysia)**.

---

## 2. Nguyên tắc Phân định Trách nhiệm (Separation of Concerns)

| Thành phần | Địa điểm | Trách nhiệm duy nhất (Single Responsibility) |
| :--- | :--- | :--- |
| **VPS Chung** | Malaysia | **Kiểm soát nghiệp vụ & Phân quyền**: Xác thực phiên (Session), kiểm tra quyền sở hữu Thẻ/Deck/Ticket/Avatar, kiểm soát hạn ngạch Quota, quản lý ORM MySQL (`MediaAsset`, `Note`, `User`), quyết định lưu URL vào thẻ và gửi tín hiệu `commit`. |
| **Worker 212** | Tokyo | **Xử lý nhị phân nặng & Phục vụ tĩnh**: Nhận byte stream, khử độc EXIF/polyglot, kiểm tra Decompression Bomb / Zip Slip, lưu tạm vào `staging/`, chuyển sang CAS vĩnh viễn khi có tín hiệu `commit`, tự động dọn rác file mồ côi và phát media tĩnh qua CDN/OV Gateway. |

---

## 3. Quy trình 2 Request Song song (Two-Phase Direct Upload)

```text
               ┌─────────────────── (1) Upload File Nhị Phân ───────────────────┐
               │    POST https://media.flama.vn/media/upload                    │
               │    (Đến thẳng Tokyo qua OV Gateway - Pure Go siêu nhanh)       │
               ▼                                                                ▼
┌───────────────────────────────┐                             ┌─────────────────────────────────┐
│     CLIENT (REACT FRONTEND)   │                             │      MÁY CHỦ 212 (TOKYO)        │
│                               │                             │  - Khử độc EXIF, polyglot       │
│  - Giữ sẵn Media Ticket       │                             │  - Lưu vào thư mục staging/     │
│    (cấp lúc login, hạn 24h)   │                             │  - Trả về ngay:                 │
│                               │                             │    { asset_id, url }            │
└──────────────┬────────────────┘                             └────────────────┬────────────────┘
               │                                                               │
               │ (2) Gửi JSON nhẹ (~200 bytes)                                 │
               │     POST /api/notes/<id>/attach-media                         │
               ▼                                                               │
┌───────────────────────────────┐                                              │
│     VPS CHUNG (MALAYSIA)      │                                              │
│  - Kiểm tra quyền & Quota     │                                              │
│  - Lưu URL vào MySQL Note     │                                              │
│  - Gửi tín hiệu commit ────►──┼─── (3) POST /media/commit (WireGuard) ───────┘
│    nhẹ (~10 bytes)            │        Chuyển file từ staging/ sang CAS vĩnh viễn
└───────────────────────────────┘
```

### Bước 1: Request 1 (Tải nhị phân lên Tokyo)
- **Endpoint**: `POST https://media.flama.vn/media/upload`
- **Header**: `Authorization: Bearer <media_ticket>` (ticket HMAC 24h đã được cấp sẵn lúc đăng nhập).
- **Xử lý trên 212**:
  - Xác thực chữ ký số HMAC của ticket (`ticket.UserID`, `ticket.MaxBytes`).
  - Kiểm tra Decompression Bomb, Zip-Slip, SVG Exploit.
  - Re-encode giải mã pixel ảnh (Pure Go) để xóa 100% EXIF/GPS/metadata độc hại.
  - Lưu file tạm thời vào thư mục Staging: `/data/flama/media/staging/<sha256>.<ext>`.
- **Phản hồi**:
  ```json
  {
    "asset_id": "01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb",
    "url": "/media/proxy/01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb",
    "sha256": "01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb",
    "size_bytes": 74,
    "content_type": "image/png"
  }
  ```
- **Preview tức thì**: Hàm `FindById` trên 212 hỗ trợ tìm kiếm cả trong `staging/` lẫn CAS vĩnh viễn, nên thẻ preview trên màn hình học tập của Frontend hiển thị ảnh/audio **ngay lập tức** không có độ trễ.

### Bước 2: Request 2 (Xác nhận quyền & Gắn thẻ tại Malaysia)
- **Endpoint**: `POST /api/notes/<note_id>/attach-media` (hoặc `/profile/avatar`, `/tickets/attach-media`)
- **Payload (JSON siêu nhẹ ~200B)**:
  ```json
  {
    "field_name": "Audio",
    "asset_id": "01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb",
    "url": "/media/proxy/01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb",
    "sha256": "01b58ddb2f86a768f91751b62f25395417f6cf526191a4aefc1ebe4f8beacdcb"
  }
  ```
- **Xử lý trên VPS Chung**:
  1. Kiểm tra xác thực (`current_user.is_authenticated`).
  2. Kiểm tra quyền sở hữu Note / Deck (`note.user_id == current_user.id`).
  3. Kiểm tra hạn ngạch upload/ngày của tài khoản.
  4. Tạo bản ghi `MediaAsset` trong MySQL và cập nhật `notes.field_values_by_id`.
  5. **Gửi tín hiệu Commit nội bộ qua WireGuard**:
     - `POST http://wg-worker212:4792/media/commit`
     - Header: `X-Internal-Secret: <GATEWAY_SECRET>`
     - Body: `{"asset_id": "01b58ddb..."}`
  6. 212 chuyển file từ `/data/flama/media/staging/` sang cây CAS vĩnh viễn `/data/flama/media/ab/cd/<sha256>.<ext>`.
  7. Commit transaction MySQL và trả về `200 OK`.

---

## 4. Cơ chế Staging TTL & Tự động dọn rác (Auto-Cleanup Worker)

### 4.1. Kịch bản hủy / mồ côi (Orphan File)
Nếu người dùng upload file lên 212 xong nhưng:
- Đóng tab trình duyệt.
- Bấm "Hủy" (Cancel) không lưu thẻ.
- Bị VPS Chung từ chối vì không có quyền sửa hoặc hết quota.

### 4.2. Cơ chế dọn rác tự động trên Worker 212
- File vẫn nằm ở `/data/flama/media/staging/<sha256>.<ext>` và chưa bao giờ được commit.
- Trong `flama-media`, một **Background Goroutine** chạy ngầm định kỳ mỗi **30 phút**:
  ```go
  func (s *DiskStorage) StartCleanupWorker(interval time.Duration, maxAge time.Duration) {
      ticker := time.NewTicker(interval)
      go func() {
          for range ticker.C {
              s.cleanupStaleStaged(maxAge)
          }
      }()
  }
  ```
- Mọi file trong `staging/` có thời gian sửa đổi (`ModTime`) vượt quá **2 giờ** sẽ bị xóa vĩnh viễn khỏi ổ đĩa.
- **Kết quả**: Ổ cứng 212 sạch 100%, không bị rác hay phình dung lượng.

---

## 5. Cấp phát Media Upload Ticket không tốn thêm Round-trip

Để Frontend không phải xin vé trước mỗi lần bấm upload:
1. Khi đăng nhập (`/api/session`), VPS Chung sinh sẵn `media_upload_ticket` bằng khóa bí mật HMAC `MEDIA_SHARED_SECRET`.
2. Thời hạn vé: **24 giờ**.
3. Frontend lưu ticket vào `sessionStorage` (hoặc Zustand store).
4. Khi upload, Frontend lấy ticket từ cache gửi thẳng sang `https://media.flama.vn`. Chỉ khi vé hết hạn (hoặc 401), Frontend mới xin vé mới từ `/api/v1/media/ticket`.

---

## 6. Lợi ích Đạt được

1. **Tốc độ Upload (UX) tăng gấp 3 lần**:
   - Loại bỏ hoàn toàn chặng bay đôi `Client -> Malaysia -> Tokyo`.
   - File nhị phân đi thẳng vào cổng Tokyo (`media.flama.vn`) với tốc độ thuần Go.
2. **VPS Chung tải nhẹ 100% về Media**:
   - Không còn phải đệm dữ liệu lớn, không còn chạy Pillow làm nóng CPU.
   - VPS Chung chỉ nhận JSON siêu nhẹ vài trăm bytes để kiểm tra quyền và ghi database.
3. **Bảo mật tuyệt đối**:
   - Nếu client cố tình upload file độc hại, 212 bắt quả tang và bắn webhook về VPS Chung qua WireGuard để khóa tài khoản tự động (Lớp bảo vệ đã kích hoạt).
   - Nếu người dùng không hoàn tất, file tự động bay màu sau 2 giờ.
