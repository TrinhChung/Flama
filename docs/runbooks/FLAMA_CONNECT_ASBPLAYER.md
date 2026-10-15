# Flama Connect: AnkiConnect v2–v6 và asbplayer

Ngày kiểm chứng local: 2026-10-10. Code đã có trong repository; chưa deploy hoặc đổi cấu hình production.

## Endpoint và cách bật

| Route | Success v2–v4 | Success v5–v6 | Duplicate |
|---|---|---|---|
| `/v1/anki-connect` | Result trực tiếp | `{result, error: null}` | Create hoặc reject; không upsert |
| `/v1/flama-connect[/<token>]` mặc định | Result trực tiếp | Result trực tiếp | Giữ upsert cũ, cần `note:update` |

Error luôn là `{result: null, error: "..."}`. Route chuẩn mặc định version 4 nếu request không có `version`, nhận JSON qua `application/json`, `text/plain` hoặc không có Content-Type. `params: null` và version ngoài 2–6 bị từ chối.

Bật text trên môi trường canary đã kiểm tra Redis và proxy:

```dotenv
CONNECT_ANKI_ADAPTER_ENABLED=1
CONNECT_ANKI_MEDIA_ENABLED=0
CONNECT_VERSIONED_PROTOCOL_ENABLED=0
CONNECT_ANKI_ALLOWED_ORIGINS=https://killergerbah.github.io,https://asbplayer.dev
CONNECT_RATE_LIMIT_BACKEND=redis
```

`REDIS_URL` dùng cấu hình Redis hiện có. Backend `redis` trả 503 khi Redis lỗi; không tự hạ xuống limiter riêng từng worker. `local` dùng cho phát triển. MySQL connection của process Flama Connect dùng `READ COMMITTED`, kết hợp khóa row User trước duplicate/quota checks. Web app có engine riêng. Không bật `CONNECT_VERSIONED_PROTOCOL_ENABLED` trước khi inventory các caller v5/v6 đang đọc raw result.

### Chính sách kiểm soát Origin & CORS thông minh của Flama Connect

Endpoint `/v1/anki-connect` áp dụng cơ chế xác thực Origin phân tầng bảo đảm tính an toàn tối đa cho dữ liệu người dùng đồng thời mang lại trải nghiệm kết nối liền mạch không cần can thiệp thủ công:

1. **Browser Extensions (Tự động cấp phép theo Scheme)**:
   - Các tiện ích mở rộng trên Chromium (Chrome, Edge, Brave, Kiwi Browser) mang scheme `chrome-extension://<id>`.
   - Các tiện ích mở rộng trên Mozilla Firefox (Desktop & Android) mang scheme `moz-extension://<uuid>`. Do Firefox tạo UUID ngẫu nhiên riêng biệt cho từng hồ sơ (profile) người dùng nhằm chống fingerprinting, Flama Connect tự động công nhận toàn bộ request có scheme `chrome-extension://` hoặc `moz-extension://` mà không yêu cầu người dùng phải đo hay thêm ID thủ công vào biến môi trường.
2. **Web Domains (Kiểm soát nghiêm ngặt qua `CONNECT_ANKI_ALLOWED_ORIGINS`)**:
   - Các ứng dụng web chạy trên nền trình duyệt (như trình phát web asbplayer tại `https://killergerbah.github.io`, `https://asbplayer.dev`, hoặc domain cá nhân tự host) bắt buộc phải được khai báo tường minh trong `CONNECT_ANKI_ALLOWED_ORIGINS`.
   - Bất kỳ web origin nào (`http://`, `https://`) không có trong danh sách allowlist này sẽ bị từ chối với mã lỗi HTTP **403 Forbidden** và **tuyệt đối không nhận header `Access-Control-Allow-Origin`**, kích hoạt cơ chế Same-Origin Policy (SOP) của trình duyệt để ngăn chặn website độc hại đọc kết quả.
3. **Non-browser / Desktop Clients (cURL, Python, Desktop Scripts, Flama Audio)**:
   - Các request không gửi header `Origin` (hoặc gửi `Origin: null` từ công cụ cục bộ/file) được bỏ qua bước kiểm tra CORS và chuyển thẳng tới bộ xác thực API Key. Request thành công nếu API Key hợp lệ và có đủ quyền (scope).
4. **Header CORS chuẩn hóa**:
   - Đối với mọi Origin hợp lệ, phản hồi preflight `OPTIONS` (204 No Content) và phản hồi `POST` luôn đính kèm:
     - `Access-Control-Allow-Origin: <request_origin>`
     - `Vary: Origin` (bắt buộc để ngăn chặn proxy cache Nginx/Cloudflare chia sẻ nhầm cache giữa các origin)
     - `Access-Control-Allow-Methods: GET, POST, OPTIONS`
     - `Access-Control-Allow-Headers: Content-Type, Content-Encoding, Authorization, X-Flama-Connect-Key, X-Package-SHA256, MCP-Protocol-Version`
     - `Access-Control-Max-Age: 600` (cache preflight 10 phút)

Mẫu Nginx tại `deploy/flama-connect.nginx.conf.example` có route chuẩn, body cap riêng 6 MiB và JSON cho edge 413/429/502/504. Cấu hình map `$http_origin $connect_error_origin` trong Nginx hỗ trợ regex cho extension schemes:
```nginx
map $http_origin $connect_error_origin {
    default "";
    "~^chrome-extension://" $http_origin;
    "~^moz-extension://"    $http_origin;
    "https://killergerbah.github.io" $http_origin;
    "https://asbplayer.dev"          $http_origin;
}
```
Việc này bảo đảm khi Nginx ngắt sớm do rate limit hoặc body quá lớn, client tiện ích Yomitan/asbplayer vẫn nhận được mã lỗi kèm header CORS hợp lệ thay vì lỗi network timeout. Chạy `nginx -t` trên máy triển khai trước reload.

## Cấu hình người dùng

### 1. Tích hợp Tiện ích Yomitan (Chrome, Edge, Brave, Firefox, Kiwi)
1. Truy cập giao diện Flama: **Cài đặt ➔ Yomitan** (`/settings/yomitan`), tạo token mới với preset `mining-text` (hoặc `mining-media`).
2. Mở Cài đặt của tiện ích **Yomitan** trên trình duyệt ➔ Cuộn đến mục **Anki / Integration**:
   - Bật **Enable Anki integration** (kích hoạt kết nối).
   - **AnkiConnect Server URL**: Nhập `https://connect.flama.vn/v1/anki-connect` (hoặc `http://127.0.0.1:4790/v1/anki-connect` ở môi trường dev).
   - **API Key**: Dán mã token vừa tạo trên Flama.
   - Bấm **Test connection**: Yomitan sẽ kết nối thành công và tải về danh sách Decks, Note Types của bạn từ Flama.
3. Cấu hình ánh xạ thẻ trong mục **Configure card templates...** để gán các marker (`{expression}`, `{reading}`, `{glossary}`, `{audio}`) vào các trường của Note Type trên Flama.

### 2. Tích hợp asbplayer (Web Player & Browser Extension)
1. Truy cập giao diện Flama: **Cài đặt ➔ asbplayer** (`/settings/asbplayer`):
   - Chọn preset **asbplayer — chỉ văn bản** (`mining-text`) hoặc **asbplayer — đa phương tiện** (`mining-media`).
   - Bấm nút **Chuẩn bị deck và model**: Hệ thống Flama tự động khởi tạo bộ thẻ `Sentences` và loại thẻ `Sentence Card` chuẩn hóa nếu chưa có.
   - Sao chép đường dẫn Flama Connect (`/v1/anki-connect`) và mã API Key.
2. Trong cài đặt **asbplayer** (trên web player `https://killergerbah.github.io` hoặc tiện ích extension):
   - **AnkiConnect URL**: Dán `https://connect.flama.vn/v1/anki-connect`.
   - **API Key**: Dán token riêng của bạn.
   - Chọn chế độ export **Add**, Deck `Sentences`, Model `Sentence Card`.
   - Ánh xạ 7 trường chuẩn:
     - `Sentence` ➔ `Sentence` (bắt buộc, chứa phụ đề thoại).
     - `Word` ➔ `Word` (từ vựng tra cứu).
     - `Definition` ➔ `Definition` (giải nghĩa từ).
     - `Image` ➔ `Image` (ảnh chụp khoảnh khắc video, yêu cầu token `mining-media`).
     - `Audio` ➔ `Audio` (file mp3 âm thanh cắt từ video, yêu cầu token `mining-media`).
     - `Source` ➔ `Source` (tên video/phim).
     - `URL` ➔ `URL` (link phát video).
3. Thử khai thác phụ đề bằng phím tắt `Ctrl + Shift + X` trên asbplayer và kiểm tra Note/Card xuất hiện ngay lập tức trong Flama.

Preset `mining-text` bao gồm các scope: `deck:read`, `note-type:read`, `note:check`, `note:create`. Preset `mining-media` bổ sung thêm scope `media:write`. Rotate token luôn bảo toàn các scope đã cấp; API cũng nhận danh sách scope hợp lệ để tạo token custom. Token cũ vẫn dùng preset/quyền mặc định hiện có.

## Media

Code hỗ trợ object hoặc array `note.audio`/`note.picture` với `filename`, `data` base64, `fields`, và `storeMediaFile` bằng base64. Chỉ nhận MP3/JPEG/PNG, kiểm signature qua validator hiện có, kiểm owner/expiry và kiểu FieldDef. Không tải URL/path; video, overwrite `deleteExisting=true` và nhiều media trong một field bị từ chối.

Sau khi qualification media đạt yêu cầu, bật `CONNECT_ANKI_MEDIA_ENABLED=1`, tạo token media, map image → `Image`, audio → `Audio`, chọn MP3 trong asbplayer. Media được materialize thành asset thuộc Note và field chứa `/media/proxy/<asset_id>`. Note/Card/ref/asset dùng chung transaction; rollback có file compensation. File mới nằm trong `connect_mined`, staging dùng `connect_pending`.

| Giới hạn mặc định của adapter chuẩn | Giá trị |
|---|---|
| JSON body | 6 MiB |
| File decoded | 2 MiB |
| Tổng media một Note | 4 MiB |
| Pending | 20 files, 16 MiB, TTL 30 phút |
| Connect storage admission | 512 MiB |

Storage admission tính MediaAsset đã commit, Connect pending và import media; canonical Connect writes được serialize theo tài khoản. **Đây chưa phải quota toàn hệ thống:** REST/MCP/import upload khác chưa cùng reserve dưới khóa này, nên chúng có thể thay đổi usage đồng thời. Giữ media rollout tắt cho tới khi gate tất cả writer/quota được giải quyết hoặc phạm vi quota và ngân sách canary được chốt rõ.

Cài timer/service `deploy/flama-connect-media-cleanup.*` theo đường dẫn triển khai thực tế. Command thủ công:

```powershell
.venv\Scripts\python.exe -m flask --app connect_wsgi:app cleanup-connect-media
```

Cleanup xóa expired pending và file không còn row trong các directory Connect quản lý, chỉ với tên storage do server sinh và tuổi trên 2 TTL. File đã commit còn asset được giữ; directory khác không bị quét để xóa. Timer mẫu chạy mỗi 5 phút. Điều chỉnh media root và quyền ghi cho process Connect/cleanup/web app cùng storage.

## Actions và giới hạn hỗ trợ

Registry dùng chung nằm ở `app/services/connect/registry.py`; parser/encoder ở `app/connect/protocol.py`, HTTP pipeline ở `request_pipeline.py`. Writer dùng chung, facade cũ vẫn được giữ. Thêm version mới cần qualification và thay contract tương ứng, không sao chép backend theo client.

Actions: `version`, `apiReflect`, `deckNames`, `modelNames`, `modelFieldNames`, `canAddNotes`, `canAddNotesWithErrorDetail`, `findNotes`, `multi`, `addNote`, và `storeMediaFile` khi media bật. `findNotes` chỉ hỗ trợ hai clause quoted deck + primary field. `multi` tối đa 10 read actions, kiểm từng scope/key/version; inner request thiếu version dùng 4, không kế thừa outer version. Chi phí rate tính số action con.

Duplicate chuẩn hỗ trợ collection cùng model và một deck, dùng normalization identity hiện có. `checkChildren=true`, `checkAllModels=true`, `deck-root` bị từ chối. Note mới dùng UUID; numeric RPC ID là `ConnectNoteRef.id` do database cấp. Existing Notes/refs không bị rekey.

`requestPermission`, create model/deck qua RPC, updateLast, notesInfo/updateNoteFields/addTags, GUI và Anki SRS chưa được hỗ trợ. asbplayer web app có thể fallback từ requestPermission sang version. Endpoint legacy/import và MCP giữ contract hiện có.

## Bằng chứng và gate còn mở

- Module backend Connect/MCP: 328 tests pass; kiểm tra bổ sung suite protocol sau thay đổi cuối: 21 tests pass, gồm clone addition không sửa source, scope, staged ownership, expiry, rollback và crash-file cleanup.
- Module frontend Connect: 22 tests pass. Typecheck, production build và lint pass (lint có warnings sẵn ngoài phần thay đổi).
- Probe `scripts/probe_connect_protocol_mysql.py`: MySQL 8.0.40, hai app instances/hai deck, numeric IDs không collision, collection duplicate chỉ một insert, pending và storage admission giữ cap khi 8 requests đồng thời. Database probe đã được xóa.
- `connect_wsgi.py` smoke: health OK, standard route disabled 404, legacy OPTIONS 204, không đăng ký main `/api`.
- Component preview trên Chrome profile riêng: desktop 1280px, mobile 390px, URL/key riêng và không tràn ngang. Đây là kiểm tra component với fixture, chưa phải flow người dùng thật trên toàn SPA.
- Redis local không phản hồi; đã test nhánh fail-closed 503, chưa có evidence thực thi Lua trên Redis thật.
- Chưa có qualification stock asbplayer extension + web app trên video thật, render/play media thật qua production proxy, hoặc oracle Anki cho toàn bộ duplicate semantics. Các request fixtures dựa trên upstream SHA được pin trong kế hoạch #217; không đại diện cho release tương lai chưa phát hành.

Rollback admission bằng tắt hai cờ adapter/media, giữ các Notes/refs/assets đã tạo. Cờ wire cutover legacy và retirement là gate riêng; không xóa dữ liệu để rollback.
