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
CONNECT_ANKI_ALLOWED_ORIGINS=https://killergerbah.github.io
CONNECT_RATE_LIMIT_BACKEND=redis
```

`REDIS_URL` dùng cấu hình Redis hiện có. Backend `redis` trả 503 khi Redis lỗi; không tự hạ xuống limiter riêng từng worker. `local` dùng cho phát triển. MySQL connection của process Connect dùng `READ COMMITTED`, kết hợp khóa row User trước duplicate/quota checks. Web app có engine riêng.

Origin có trong request phải thuộc allowlist; `null` và `*` không được chấp nhận. Request không có Origin vẫn cần token, scope và rate budget. Đo Origin thực tế của extension rồi bổ sung chính xác nếu cần; không suy Origin từ tên client. Không bật `CONNECT_VERSIONED_PROTOCOL_ENABLED` trước khi inventory các caller v5/v6 đang đọc raw result.

Mẫu Nginx tại `deploy/flama-connect.nginx.conf.example` có route chuẩn, body cap riêng 6 MiB và JSON cho edge 413/429/502/504. Đồng bộ `connect_error_origin` trong Nginx với allowlist của app. Chạy `nginx -t` trên máy triển khai trước reload; mẫu này chưa được kiểm chứng qua Nginx thật trong phiên local.

## Cấu hình người dùng

1. Trong Settings quản lý token, chọn **asbplayer — chỉ văn bản** và tạo token.
2. Bấm **Chuẩn bị deck và model**. API này tạo/reuse `Sentences` và `Sentence Card` trong tài khoản, có active Template. Nếu schema trùng tên đã khác, API báo lỗi thay vì sửa dữ liệu người dùng.
3. Dán URL `/v1/anki-connect` vào AnkiConnect URL của asbplayer; dán token riêng vào API key.
4. Chọn export **Add**, deck `Sentences`, model `Sentence Card`. Map sentence → `Sentence`, word → `Word`, definition → `Definition`, source → `Source`, URL → `URL`. Word là tùy chọn; Sentence là primary required text.
5. Với text-only, để trống image/audio mappings. Tạo một câu thử và kiểm tra Note/Card trên Flama.

Preset `mining-text` chỉ có `deck:read`, `note-type:read`, `note:check`, `note:create`. Preset `mining-media` thêm `media:write`. Rotate giữ các scope đã cấp; API cũng nhận danh sách scope hợp lệ để tạo token custom. Token cũ vẫn dùng preset/quyền mặc định hiện có.

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
