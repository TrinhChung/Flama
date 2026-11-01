# Flama System Architecture

## Tổng quan

Flama là hệ thống học flashcard, quản lý từ vựng và chia sẻ bộ thẻ được cấu trúc thành các runtime chuyên biệt:

1. **React SPA (`frontend/` - Port 4789)**: Sở hữu toàn bộ giao diện HTML, state management, client routing và tương tác người dùng.
2. **Flask REST Backend (`app/` via `wsgi.py` - Port 4789)**: Cung cấp REST API canonical dưới `/api`, quản lý session/CSRF, binary media proxy, CLI và database migrations/maintenance.
3. **Flama Connect Service (`connect_wsgi.py` - Port 4790)**: Dịch vụ tương thích giao thức Yomitan/AnkiConnect cho phép trích xuất từ vựng 1-click từ trình duyệt trực tiếp vào Flama.
4. **Flama Audio Companion (`flama-audio/` - Port 4791)**: Ứng dụng desktop Windows độc lập (.NET 8 WPF) cung cấp VoiceVox và Kokoro TTS engines nội bộ (offline, không phụ thuộc cloud API key).
5. **Flama Media Service (`flama-media/` - Port 4792)**: Microservice Go hiệu năng cao chuyên biệt xử lý, lưu trữ và phát Media (âm thanh `.mp3` & hình ảnh Flashcard) theo kiến trúc Zero-Trust & Hardened Security.

`wsgi.py` là entry point chính cho web app và REST API. Flask không còn cấu hình thư mục Jinja và không render server-side template nào.

## Luồng runtime & Hệ sinh thái dịch vụ

```mermaid
flowchart TD
    subgraph Client["Client Tier"]
        B[Browser / React SPA :4789]
        EXT[Browser Extension / Yomitan]
        FA_APP[Flama Audio Desktop App :4791]
    end

    subgraph Gateway["OV Gateway / Reverse Proxy (:443)"]
        NGINX[Nginx Gateway & Rate Limiter]
    end

    subgraph Backend["Flama Core Backend (:4789)"]
        API[Flask REST API /api]
        SPA_HOST[SPA Shell Host app/spa.py]
        SVC[Application Services]
        REPO[Repositories]
    end

    subgraph Connect["Flama Connect Service (:4790)"]
        CONN_API[AnkiConnect Compatible API]
        CONN_SVC[Flama Connect Service]
    end

    subgraph MediaWorker["Flama Media Service (:4792 - Worker Node 212)"]
        MEDIA_GO[Go Hardened Media Service]
        SAN[Image Sanitizer & Pure-Go Re-encoding]
        AUTH[HMAC Presigned Ticket Verifier]
        INCIDENT[Security Incident Reporter]
    end

    subgraph Storage["Persistence Tier"]
        DB[(MySQL Primary / Replicas)]
        FS[(Hardened Media Storage /data/flama/media)]
    end

    B -->|SPA assets & routes| NGINX
    NGINX -->|Frontend Shell| SPA_HOST
    NGINX -->|JSON API + CSRF| API
    NGINX -->|Signed Media Proxy /media/proxy/| MEDIA_GO
    NGINX -->|Signed Media Upload /media/upload| MEDIA_GO
    B -->|Local TTS Generation| FA_APP
    EXT -->|Mining JSON-RPC| CONN_API

    API --> SVC
    CONN_API --> CONN_SVC
    CONN_SVC --> REPO
    SVC --> REPO
    REPO --> DB

    MEDIA_GO --> AUTH
    MEDIA_GO --> SAN
    MEDIA_GO --> FS
    MEDIA_GO -->|Security Incident Callback| INCIDENT
    INCIDENT -->|Lock Malicious Account| API
```

### Navigation và HTML

- Mọi GET giao diện được `app/spa.py` trả về `frontend/dist/index.html`.
- React Router xử lý deep-link, trang 404, auth guard và permission guard phía giao diện.
- Permission thật luôn được kiểm tra lại tại REST endpoint.
- `frontend/dist` được tạo trong frontend build stage của Dockerfile.
- Không còn thư mục `templates/`, Jinja filter, Jinja context processor hoặc HTML error page phía Flask.

### REST API

- Public namespace canonical là `/api`.
- Blueprint chính được đăng ký từ `app/api/`; package `app/api/v1/` là boundary nội bộ, không đưa version vào URL.
- JSON dùng `snake_case`; lỗi dùng envelope `error`, `message` và các trường tùy chọn như `field`, `details`.
- SPA dùng Flask-Login session, `credentials: same-origin` và CSRF token lấy từ `GET /api/session`.
- Các adapter cũ chỉ được bật trong `TESTING`; production trả `410 LEGACY_ENDPOINT_REMOVED` và yêu cầu dùng namespace `/api`.

### Ngoại lệ không phải JSON resource thông thường

- `/api/mcp`: MCP JSON-RPC protocol endpoint.
- PayOS webhook (`/api/payments/providers/payos/webhook`): callback có signature và idempotency riêng.
- `/media/*`, `/static/js/card_renderer_host.js`, download binary: static & media delivery.
- SPA shell và frontend assets.

## Các lớp backend

- `app/api/`: parse HTTP, schema validation, auth/permission guard và response mapping.
- `app/services/`: orchestration, transaction ownership và business rules.
- `app/repositories/`: query/persistence, không sở hữu response HTTP.
- `app/validators/`: validate và normalize request/business input.
- `models/`: SQLAlchemy models canonical (`Deck`, `NoteType`, `FieldDef`, `Template`, `Note`, `Card`, `DeckInstall`, `DeckChangeRequest`, `PaymentOrder`, ...).
- `app/routes/`: transition adapters, binary/proxy delivery và compatibility endpoints.

Đích kiến trúc cho mutation là:

```text
REST route -> application service (transaction owner) -> repository -> model
```

## Flama Media Service & Zero-Trust Architecture

`flama-media/` là microservice độc lập viết bằng Go, lắng nghe tại cổng **4792**, chịu trách nhiệm toàn bộ vòng đời của tệp media (upload, kiểm duyệt, tẩy uế, lưu trữ và streaming):

1. **Topology phân tầng Zero-Trust (OV Gateway -> Worker 212)**:
   - Dịch vụ chạy trên Worker Node (Máy 212), đóng cổng 4792 hoàn toàn với toàn bộ Internet thông qua Firewall (UFW).
   - Chỉ duy nhất Nginx trên OV Gateway (VPS Chính) được phép proxy traffic sang cổng 4792 và bắt buộc đính kèm header xác thực `X-Flama-Gateway-Secret`.
2. **HMAC Presigned Tickets**:
   - Mọi tác vụ upload đơn lẻ (`POST /media/upload`) hoặc upload gói nén (`POST /media/upload-zip`) đều phải có vé ký số HMAC SHA256 do Flama Backend cấp phát, có giới hạn thời gian sống (TTL) và gắn với định danh người dùng.
3. **Tẩy uế hình ảnh (Pure-Go Image Re-encoding)**:
   - Để triệt tiêu 100% rủi ro khai thác mã độc EXIF, Polyglot files (ảnh ngụy trang script PHP/JS), và Steganography: hệ thống giải mã toàn bộ pixel của ảnh trong bộ nhớ RAM và vẽ lại thành tệp ảnh mới thuần túy bằng Go trước khi lưu xuống đĩa.
4. **Chống Decompression Bomb (Zip Bomb / Pixel Flood)**:
   - Trước khi phân bổ RAM giải nén ảnh, kích thước ảnh được kiểm tra nghiêm ngặt: chiều dài/rộng tối đa <= 4096px, tổng số pixel <= 16.000.000px. Các file ZIP upload hàng loạt bị giới hạn kích thước giải nén và tỷ lệ nén tối đa.
5. **Chống Path Traversal**:
   - Tên file lưu trữ vật lý được chuẩn hóa sang định dạng UUIDv4 ngẫu nhiên và phân mảnh thư mục hai cấp: `/data/flama/media/ab/cd/<uuid>.<ext>`.
6. **Cơ chế phản ứng bảo mật (Security Incident Callback)**:
   - Khi phát hiện request giả mạo chữ ký, decompression bomb hoặc cố tình tiêm mã độc, service lập tức kích hoạt webhook gọi ngược về Flama Core (`/api/v1/internal/security/incident`) để ghi nhận log an ninh và tự động khóa tài khoản vi phạm.

## Flashcard Renderer & Sandbox

`render_template_pair()` trong `app/services/flashcard_renderer.py` biên dịch cú pháp card `{{Field}}`, `{{{Field}}}`, conditionals và media proxy an toàn. Output được React render trong `iframe sandbox="allow-scripts"` thông qua `static/js/card_renderer_host.js` với CSP chặt chẽ (`connect-src 'none'`), bảo vệ người dùng trước các mã script không an toàn từ template chia sẻ.

## Shared Deck Collaboration & Change Requests

1. **Logical Overlay Installation**: Người dùng cài đặt shared deck không bị copy toàn bộ `Note/Card`. Hệ thống tạo `DeckInstall` và ánh xạ qua `DeckCloneDeckMap`.
2. **Local Customization**: Chỉnh sửa của người học lưu độc lập trong các bảng `DeckClone*` (`DeckCloneNoteFieldOverride`, v.v.) mà không làm thay đổi source deck của tác giả.
3. **Deck Change Request**: Người cài đặt có thể tạo Change Request (`models/deck_change_request.py`) gửi các cải tiến về cho tác giả. Hệ thống hỗ trợ phát hiện xung đột (`has_conflict`), cho phép tác giả duyệt/hợp nhất (`merged`) hoặc từ chối (`rejected`) một cách an toàn.

## Study Session & Undo System

- Quá trình học tập được quản lý bởi `StudySession` (`models/study_session.py`, `models/study_session_card.py`, `models/study_session_commit.py`).
- Hỗ trợ **Undo/Revert**: Người học có thể hoàn tác ngay lượt đánh giá thẻ vừa thực hiện; scheduler khôi phục lại trạng thái card interval/ease/state chính xác trước đó.

## Startup và dữ liệu

`create_app()` khởi tạo extension, đăng ký model/blueprint/CLI và gọi `run_startup_maintenance()` trong `app/startup.py`. Ngoài testing, `STARTUP_RUN_MAINTENANCE` mặc định tắt; schema được quản lý bằng Alembic. Kiểm tra kết nối DB là bước riêng (`STARTUP_CHECK_DB_CONNECTIVITY`).

Khi bật maintenance, các cờ con điều khiển `db.create_all()`, sửa schema tương thích, seed roles/taxonomy/TTS và clone cutover. TTS seed và clone cutover mặc định tắt; không xem chúng là chi phí bắt buộc mỗi lần boot. Xác minh effective config của process trước khi đánh giá startup hoặc chạy maintenance.

## Chạy và kiểm tra

- **Web & API (Local)**: `flask --app wsgi.py run --host=0.0.0.0 --port=4789`
- **Flama Connect Service**: `python connect_wsgi.py` (Port 4790)
- **Flama Audio Companion**: Chạy `flama-audio/publish/release/FlamaAudio-Portable.exe` hoặc debug WPF app (Port 4791)
- **Flama Media Service**: `cd flama-media && go run ./cmd/server` (Port 4792) hoặc `cd flama-media && docker compose up -d`
- **Production Server**: `gunicorn --bind 0.0.0.0:4789 wsgi:app`
- **Frontend Check**: `cd frontend && npm run check`
- **Focused Tests**: `python scripts/run_tests.py --changed` hoặc `--module study,marketplace`; dùng `--all` cho CI/pre-release.
