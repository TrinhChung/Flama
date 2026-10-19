# Task: Backend pipeline xử lý ảnh an toàn, tối ưu và đồng bộ qua Redis

> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-28  
> **Target branch:** `develop`  
> **Commit:** `e86c7d1`

## Mục tiêu

Thiết kế và triển khai một **pipeline backend dùng chung cho toàn bộ ảnh được người dùng đưa vào Flama**, bất kể ảnh được thêm từ màn nào, ví dụ:

- avatar / ảnh đại diện
- ảnh trong Profile
- ảnh Deck / Shared Deck / Marketplace
- ảnh được thêm vào note/card
- Image Library
- ảnh lấy từ URL public trên Internet
- các tính năng upload ảnh mới trong tương lai

Không để từng màn tự xử lý ảnh theo logic riêng.

Pipeline cần giải quyết đồng thời các yêu cầu:

1. kiểm tra URL/file ảnh trước khi sử dụng;
2. kiểm tra rủi ro bảo mật và nội dung file giả mạo;
3. phát hiện trường hợp nghi ngờ tấn công và tạo cảnh báo cho Admin;
4. nếu ảnh public có thể dùng trực tiếp từ frontend thì cho phép dùng tạm URL đó để UX không phải chờ;
5. đồng thời đưa ảnh vào hàng đợi Redis để backend xử lý bất đồng bộ;
6. worker tải ảnh về, decode/re-encode, resize theo đúng mục đích sử dụng, tối ưu dung lượng và chuyển sang format phù hợp như WebP;
7. sau khi xử lý thành công, thay URL public bên ngoài bằng asset đã được Flama quản lý;
8. cập nhật Image Library để các ảnh được quản lý tập trung và có trạng thái xử lý rõ ràng.

## Nguyên tắc kiến trúc

Cần có **một Image Ingestion / Image Processing Service dùng chung**, thay vì để Profile, Marketplace, Deck Editor, Image Library... tự download/validate/resize ảnh.

Luồng tổng quát:

```text
User thêm ảnh
    ↓
Image Ingestion API / Service
    ↓
Validate input + security checks
    ↓
┌────────────────────────────────────────────┐
│ Nếu nguy hiểm / nghi ngờ tấn công          │
│ → reject                                   │
│ → ghi security event                       │
│ → tạo cảnh báo cho Admin                   │
└────────────────────────────────────────────┘
    ↓ safe
Nếu là public URL và frontend dùng trực tiếp được
    ↓
Tạm thời lưu external/public URL làm display URL
    ↓
Đồng thời tạo Redis processing job
    ↓
Worker download ảnh an toàn
    ↓
Decode → validate → strip metadata → resize
    ↓
Convert/optimize (ưu tiên WebP khi phù hợp)
    ↓
Upload vào storage do Flama quản lý
    ↓
Update Image Library / image asset record
    ↓
Atomic replace external URL → internal managed URL
```

## 1. Tất cả ảnh phải đi qua backend validation

Không được tin tưởng trực tiếp:

- file extension;
- MIME type do client gửi;
- `Content-Type` của server bên ngoài;
- URL chỉ vì kết thúc bằng `.jpg`, `.png`, `.webp`;
- ảnh lấy từ clipboard hoặc nguồn public.

Backend phải xác định file thực tế bằng nội dung/magic bytes và thử decode bằng thư viện xử lý ảnh phù hợp.

Cần reject tối thiểu các trường hợp:

- file không phải ảnh hợp lệ;
- MIME khai báo không khớp dữ liệu thực;
- file bị hỏng hoặc decoder không đọc được;
- file vượt giới hạn dung lượng;
- kích thước pixel quá lớn;
- số megapixel vượt ngưỡng;
- image/decompression bomb;
- format không được hỗ trợ;
- payload polyglot hoặc file có dữ liệu bất thường nếu thư viện/security scanner phát hiện;
- SVG chưa được sanitize hoặc không nằm trong policy cho phép.

Ưu tiên chỉ hỗ trợ một tập format raster rõ ràng như JPEG, PNG, WebP, GIF nếu thực sự cần.

Nếu không có nhu cầu nghiệp vụ rõ ràng cho SVG thì nên **không nhận SVG do user upload**, vì SVG có thể chứa script, external reference hoặc các thành phần active content.

## 2. Kiểm tra mã độc / file nguy hiểm

Cần nghiên cứu và triển khai lớp kiểm tra bảo mật phù hợp với hạ tầng Flama.

Không chỉ dựa vào tên file.

Tối thiểu cần có:

- magic byte / file signature validation;
- image decoder validation;
- giới hạn file size và pixel count;
- re-encode ảnh sang format sạch do server tạo ra;
- loại bỏ metadata không cần thiết;
- loại bỏ embedded payload không còn tồn tại sau bước decode/re-encode.

Nghiên cứu bổ sung antivirus/malware scanner như ClamAV hoặc giải pháp tương đương nếu phù hợp với hạ tầng hiện tại.

Không bắt buộc chọn ClamAV nếu có giải pháp tốt hơn, nhưng task phải đánh giá rõ:

- chi phí CPU/RAM;
- latency;
- cách deploy;
- false positive;
- phạm vi file scanner thực sự bảo vệ được.

Việc **decode rồi re-encode server-side** cần được coi là lớp bảo vệ chính đối với asset ảnh cuối cùng, thay vì giữ nguyên byte gốc của user và phục vụ trực tiếp.

## 3. Bảo vệ khi nhận ảnh từ URL public

Đây là phần bắt buộc vì backend sẽ chủ động download URL do user cung cấp.

Phải chống SSRF.

Không được cho worker tùy ý request mọi URL.

Cần kiểm tra tối thiểu:

- chỉ cho phép `http` / `https` theo policy;
- reject schema khác như `file://`, `ftp://`, `data:` nếu không có use case rõ ràng;
- reject localhost;
- reject loopback IP;
- reject private/internal network ranges;
- reject link-local / metadata service IP;
- kiểm tra DNS resolution;
- kiểm tra lại destination sau redirect;
- giới hạn số redirect;
- timeout kết nối và download;
- giới hạn response size;
- không download vô hạn nếu server không khai báo Content-Length;
- không forward credential/cookie/token nội bộ của Flama đến host bên ngoài.

Cần xem xét DNS rebinding và các trường hợp hostname ban đầu hợp lệ nhưng resolve/redirect về private IP.

## 4. Dùng tạm public URL để giảm thời gian chờ

Đối với ảnh được nhập bằng URL public:

- backend kiểm tra URL hợp lệ;
- kiểm tra ảnh tồn tại và thực sự là image;
- kiểm tra frontend có thể render/hotlink ảnh đó hay không;
- nếu frontend có thể sử dụng trực tiếp thì cho phép dùng tạm public URL làm `display_url`;
- đồng thời vẫn phải enqueue Redis job để đưa ảnh về storage của Flama.

### Lưu ý về CORS

Không thiết kế logic theo kiểu đơn giản:

> Có CORS = dùng được, không có CORS = không dùng được.

Với thẻ `<img>`, ảnh từ domain khác thường vẫn có thể hiển thị dù server không cấp CORS. CORS trở thành vấn đề khi frontend cần đọc pixel, canvas hoặc thực hiện request theo cách yêu cầu CORS.

Vì vậy cần định nghĩa một bước kiểm tra **frontend usability / hotlink availability** phù hợp với use case thực tế.

Có thể xem xét:

- URL trả về status hợp lệ;
- Content-Type/image signature hợp lệ;
- ảnh có thể truy cập public không cần cookie/auth;
- host có chặn hotlink hay không;
- frontend hiện tại cần chỉ render `<img>` hay còn thao tác canvas/crop phía client.

Nếu không thể dùng trực tiếp thì không được gắn URL hỏng vào UI; cần dùng trạng thái `processing`/placeholder cho đến khi worker xử lý xong.

## 5. Image Library là nguồn quản lý asset tập trung

Khi một ảnh được user thêm vào hệ thống, cần nghiên cứu việc tạo một image asset record dùng chung thay vì mỗi domain lưu một URL rời rạc.

Một hướng dữ liệu tham khảo:

```text
ImageAsset
- id
- owner_user_id
- source_type            upload | external_url | generated | ...
- source_url             nullable
- display_url            URL hiện frontend đang dùng
- managed_url            URL asset nội bộ sau xử lý
- original_content_type
- output_content_type
- original_width
- original_height
- output_width
- output_height
- original_size_bytes
- output_size_bytes
- usage_type              avatar | deck_cover | note_image | marketplace | ...
- processing_status       pending | processing | ready | failed | rejected
- security_status         pending | safe | suspicious | blocked
- security_reason         nullable
- created_at
- processed_at
```

Tên field/model không bắt buộc giống trên. Cần kiểm tra schema hiện tại trước khi quyết định.

Image Library cần có khả năng biết:

- ảnh nào đang dùng external URL tạm thời;
- ảnh nào đang pending;
- ảnh nào đã được download và tối ưu;
- ảnh nào failed;
- ảnh nào bị security block;
- ảnh nội bộ nào đang được tham chiếu bởi các feature khác.

## 6. Redis queue cho xử lý bất đồng bộ

Sau khi ảnh vượt qua bước kiểm tra ban đầu, backend tạo một job vào Redis queue.

Không block request của user chỉ để resize/convert một ảnh nếu không cần thiết.

Job cần chứa hoặc tham chiếu tối thiểu:

- image asset id;
- source URL/storage key;
- usage type;
- target preset;
- user/request context cần thiết cho audit;
- retry metadata.

Worker cần hỗ trợ:

- idempotency;
- retry có giới hạn;
- exponential backoff nếu phù hợp;
- dead-letter/failed state;
- tránh xử lý trùng cùng một asset;
- timeout;
- structured logging;
- metric cho queue depth / processing time / failure rate.

Không để retry vô hạn với URL chết hoặc file độc hại.

## 7. Resize theo đúng mục đích sử dụng

Không dùng một kích thước ảnh duy nhất cho mọi màn.

Cần nghiên cứu các image preset theo `usage_type`.

Ví dụ:

### Avatar

Avatar của Profile không cần giữ ảnh 4000x4000.

Có thể nghiên cứu các size như:

- 128x128
- 256x256
- 512x512 tối đa nếu cần retina/high-density

Cần cân nhắc crop vuông hoặc giữ aspect ratio tùy UX của Profile.

### Deck / Marketplace cover

Cần preset phù hợp tỷ lệ card/detail page.

Có thể cần nhiều derivative nếu cùng ảnh được hiển thị ở:

- card nhỏ;
- detail page;
- mobile.

### Note/Card image

Không resize quá nhỏ làm mất nội dung học tập.

Cần giới hạn max width/height hợp lý nhưng giữ đủ chất lượng cho Kanji, diagram, screenshot hoặc tài liệu học.

### Image Library

Có thể lưu:

- optimized original hợp lý;
- thumbnail;
- các derivative cần thiết.

Không tạo quá nhiều variant nếu sản phẩm chưa cần, tránh tăng storage complexity.

## 8. Chuyển format và tối ưu dung lượng

Sau khi decode ảnh:

- resize nếu cần;
- auto-orient theo EXIF trước khi strip metadata;
- remove metadata không cần thiết;
- encode lại;
- tối ưu chất lượng/dung lượng.

Ưu tiên WebP cho ảnh raster nếu browser/storage hiện tại hỗ trợ tốt.

Có thể nghiên cứu AVIF cho phase sau nhưng không bắt buộc nếu làm tăng CPU/complexity.

Cần có policy riêng cho:

- ảnh có transparency;
- animated GIF nếu Flama hỗ trợ animation;
- screenshot/text image cần chất lượng cao;
- ảnh thông thường/photo.

Không convert mù quáng khiến ảnh chữ bị mờ hoặc mất transparency.

## 9. Thay external URL bằng managed URL sau xử lý

Trong thời gian chờ worker:

```text
display_url = external public URL
processing_status = pending/processing
```

Sau khi worker xử lý thành công:

```text
managed_url = Flama storage/CDN URL
display_url = managed_url
processing_status = ready
```

Việc thay thế phải atomic ở mức phù hợp để frontend không rơi vào trạng thái URL nửa cũ nửa mới.

Các entity đang dùng ảnh nên tham chiếu `ImageAsset`/asset id nếu kiến trúc cho phép, thay vì copy raw URL vào nhiều bảng rồi phải update từng nơi.

Nếu hiện tại schema đang lưu URL trực tiếp ở nhiều model, cần nghiên cứu migration strategy theo phase.

Không bắt buộc refactor toàn bộ schema trong một lần nếu rủi ro lớn, nhưng kiến trúc mới phải tránh tiếp tục mở rộng technical debt.

## 10. Xử lý khi external URL thay đổi hoặc chết

Lợi ích của việc đưa ảnh về storage của Flama là không phụ thuộc lâu dài vào host bên ngoài.

Sau khi managed asset đã sẵn sàng:

- frontend không còn phụ thuộc source URL;
- source website xóa ảnh không làm Flama mất ảnh;
- host bên ngoài thay policy/hotlink không ảnh hưởng asset đã migrate;
- giảm request đến website bên thứ ba.

Có thể giữ `source_url` phục vụ audit/provenance nếu phù hợp, nhưng không dùng nó làm runtime URL sau khi asset nội bộ đã sẵn sàng.

## 11. Security alert cho Admin

Nếu phát hiện trường hợp nghi ngờ tấn công, cần tạo event/cảnh báo ở **màn Cảnh báo của Admin**.

Các case cần xem xét cảnh báo:

- user upload file giả ảnh;
- malware scanner phát hiện threat;
- image bomb / kích thước bất thường;
- SSRF attempt đến localhost/private IP/metadata endpoint;
- URL redirect cố tình sang private/internal address;
- nhiều request ảnh độc hại liên tiếp từ cùng user;
- pattern thử nhiều file bị block trong thời gian ngắn;
- format/payload đáng ngờ.

Alert cần có dữ liệu đủ để Admin điều tra nhưng không hiển thị/chạy trực tiếp payload nguy hiểm.

Ví dụ metadata:

- user id;
- request id;
- source type;
- source hostname hoặc sanitized URL;
- detection type;
- reason;
- timestamp;
- related ImageAsset id;
- mức severity;
- số lần vi phạm gần đây nếu có.

Không lưu secret/token/query parameter nhạy cảm vào log hoặc Admin UI nếu URL có chứa chúng.

Cần liên kết với hệ thống Admin Alert hiện tại nếu đã có; không tạo một hệ thống cảnh báo thứ hai nếu không cần thiết.

## 12. Trạng thái lỗi và UX contract với frontend

Backend cần trả trạng thái đủ rõ để frontend xử lý thống nhất.

Ví dụ:

```text
READY_EXTERNAL_TEMP
PROCESSING
READY_MANAGED
FAILED
REJECTED_SECURITY
```

Tên enum không bắt buộc như trên.

Frontend cần biết được:

- có URL dùng ngay hay không;
- đang xử lý hay đã hoàn thành;
- khi nào nên hiện placeholder;
- ảnh bị reject vì input không hợp lệ hay vì security policy;
- có cần retry/re-upload hay không.

Không expose thông tin security quá chi tiết cho attacker. User-facing message chỉ cần đủ để người dùng hợp lệ hiểu cách sửa input.

## 13. Storage và cache

Cần kiểm tra storage hiện tại của Flama và chọn nơi lưu managed image phù hợp.

Cần nghiên cứu:

- object storage/local storage hiện tại;
- CDN nếu có;
- cache headers;
- immutable/versioned URL;
- cleanup asset không còn được sử dụng;
- duplicate image/deduplication nếu có lợi;
- backup/retention.

Nếu replace ảnh avatar hoặc cover, ưu tiên URL version/hash mới để tránh browser/CDN giữ cache cũ.

## 14. Không làm toàn bộ security scan trong frontend

Frontend có thể kiểm tra sơ bộ để UX tốt hơn, ví dụ:

- extension;
- preview;
- client-side file size.

Nhưng toàn bộ validation quan trọng phải chạy lại ở backend.

Không coi client-side validation là security boundary.

## 15. Technical investigation trước khi code

Trước khi triển khai cần kiểm tra code hiện tại và ghi rõ:

- Image Library hiện đang lưu dữ liệu như thế nào;
- các API upload/import image hiện tại;
- Profile/avatar hiện có hay chưa;
- Deck/Shared Deck/Marketplace đang lưu ảnh bằng field nào;
- note/card image đang lưu URL/file theo cách nào;
- Redis hiện được dùng cho job gì;
- project đang dùng queue framework nào, nếu có;
- worker/deployment model hiện tại;
- storage hiện tại;
- Admin Alert hiện tại;
- logging/audit hiện tại.

Sau investigation cần quyết định:

- service dùng chung nằm ở module nào;
- API contract;
- model/schema cần thêm;
- migration cần thiết;
- queue/job implementation;
- storage adapter;
- security scanner;
- image processing library;
- preset theo từng usage type.

## 16. Phân kỳ đề xuất

### Phase 1 - Core security + ingestion

- unified backend entry point;
- upload/public URL validation;
- magic byte/decode check;
- size/pixel limits;
- SSRF protection;
- security event + Admin Alert;
- ImageAsset/process status.

### Phase 2 - Async processing

- Redis job;
- worker download;
- resize presets;
- metadata stripping;
- WebP optimization;
- managed storage;
- atomic URL replacement.

### Phase 3 - Migrate các feature

Chuyển lần lượt:

- Profile/avatar;
- Image Library;
- Deck/Marketplace;
- note/card image;
- các màn còn lại.

Không cần big-bang migration nếu ảnh hưởng quá nhiều feature.

## Deliverables

- Thiết kế Image Ingestion / Processing architecture dùng chung.
- Danh sách tất cả flow hiện tại có thể thêm ảnh.
- Security validation policy.
- SSRF protection cho external URL.
- ImageAsset/state model hoặc giải pháp tương đương.
- Redis queue + worker processing.
- Resize preset theo usage type.
- WebP/optimized output.
- Metadata stripping/re-encode.
- Managed storage integration.
- External URL temporary display flow.
- Atomic replace sang managed URL.
- Image Library integration.
- Admin Security Alert integration.
- Logging/metrics/retry/failure handling.
- Migration plan cho các feature đang lưu image URL trực tiếp.
- Unit/integration/security tests cho các flow chính.

## Acceptance criteria

- Mọi flow mới thêm ảnh vào Flama phải đi qua backend image pipeline dùng chung.
- Backend không tin extension/MIME do client hoặc remote server khai báo mà không kiểm tra nội dung thực tế.
- File không phải ảnh hoặc ảnh nguy hiểm/bất thường bị reject.
- External URL được bảo vệ khỏi SSRF và redirect sang private/internal network.
- Các trường hợp nghi ngờ tấn công tạo được cảnh báo trong hệ thống Admin Alert.
- Public image URL hợp lệ có thể được dùng tạm nếu frontend thực sự render được.
- Việc dùng tạm URL public không làm bỏ qua Redis processing job.
- Worker có thể download, decode, resize và optimize ảnh theo usage type.
- Avatar không lưu/phục vụ ảnh kích thước gốc quá lớn khi không cần thiết.
- Output được chuyển sang format nhẹ phù hợp, ưu tiên WebP khi không làm mất đặc tính cần thiết của ảnh.
- Metadata không cần thiết được loại bỏ khỏi managed asset.
- Sau khi xử lý thành công, frontend chuyển sang dùng URL asset do Flama quản lý thay vì URL Internet ban đầu.
- Job có retry có giới hạn, idempotency và trạng thái failed rõ ràng.
- Image Library thể hiện được trạng thái external/pending/ready/failed/rejected.
- Có tests cho file giả ảnh, image bomb, oversized file, invalid URL, SSRF/private IP, redirect SSRF, timeout, URL chết, worker retry và successful URL replacement.

## Out of scope / không làm trong task này nếu chưa cần

- AI moderation nội dung hình ảnh NSFW/copyright nếu chưa có requirement riêng;
- hệ thống CDN phức tạp nếu storage hiện tại chưa cần;
- AVIF bắt buộc;
- tự động nhận diện bản quyền ảnh;
- giữ nguyên file upload gốc để public trực tiếp.

Các nội dung trên có thể được tách thành task riêng sau khi pipeline ảnh cơ bản đã ổn định.

---

## Implementation Summary (2026-08-28)

### 1. Database & Migration
- **`models/image_asset.py`**: Model `ImageAsset` theo dõi toàn bộ thuộc tính và trạng thái xử lý ảnh.
- **`models/admin_security_alert.py`**: Model `AdminSecurityAlert` ghi nhận các sự kiện bảo mật (SSRF, Decompression Bomb, Disguised File, Unsafe SVG).
- **`migrations/versions/20260831_000028_add_image_assets_and_security_alerts.py`**: Linear migration cho DB schema.

### 2. Services & Architecture
- **`app/services/image_security_service.py`**: Kiểm tra signature/magic bytes, phát hiện decompression bomb, polyglot header, ghi nhận threat alert.
- **`app/services/image_processor.py`**: Auto-orient EXIF, resize theo preset (`avatar`, `deck_cover`, `note_image`, `image_library`, `thumbnail`), bảo toàn alpha channel, strip metadata và convert sang WebP.
- **`app/services/image_queue_service.py`**: Quản trị hàng đợi Redis (`flama:images:queue`) với fallback in-memory.
- **`app/services/image_worker_service.py`**: Worker download an toàn (Anti-SSRF & DNS pinning), validate, optimize WebP và thay thế atomic `display_url = managed_url` (`/media/asset/<id>`).
- **`app/services/image_ingestion_service.py`**: Entrypoint thống nhất cho toàn bộ hệ thống Flama (hỗ trợ temporary display URL cho public images).

### 3. API, Routes & CLI
- **`app/api/v1/images.py`**: `POST /api/v1/images/ingest` & `GET /api/v1/images/<asset_id>/status`.
- **`app/api/v1/admin/security_alerts.py`**: `GET /api/v1/admin/security-alerts` & `PATCH /api/v1/admin/security-alerts/<alert_id>`.
- **`app/routes/media_asset_routes.py`**: `GET /media/asset/<asset_id>` phục vụ WebP kèm CSP sandbox, nosniff, immutable cache.
- **`app/cli.py`**: CLI command `flask images process-queue` & `flask images clear-queue`.

### 4. Verification Results
- **`tests/test_secure_image_pipeline.py`**: 14/14 tests Passed (`OK`).
- **Regression tests (`test_image*.py`, `test_remote_image_fetcher.py`)**: 34/34 tests Passed (`OK`).

