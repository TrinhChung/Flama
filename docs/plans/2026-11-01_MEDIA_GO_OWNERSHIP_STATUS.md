# Media chuyển sang Go — trạng thái và phân công (2026-11-01)

File này là bảng phối hợp cho mọi agent đang làm luồng media. Cập nhật khi xong hoặc nhận một mục.

## Nhánh dùng chung

| Repo | Nhánh | Ghi chú |
|---|---|---|
| Flama (app) | `feat/media-direct-upload-20261101` | Dựa trên PR #282 (`sec/redact-live-secrets-20261101`). Main checkout `D:/Project/nihongo` đang ở nhánh này. |
| flama-media (Go) | `feat/direct-upload-staging-20261101` | Submodule checkout `D:/Project/nihongo/flama-media` đang ở nhánh này. |

Quy tắc: commit thẳng lên hai nhánh này, không để WIP chưa commit qua đêm; trước khi sửa một file mà agent khác đang nhận, ghi vào bảng bên dưới. Bản sao WIP cũ của GPT nằm trong `git stash` của từng checkout ("backup: GPT ... WIP before switching to shared branch").

## Luồng đã chốt

- **VPS (Flask)**: quyền, quota, ticket HMAC, dòng DB; field chỉ lưu `/store/<id>`. Không giữ byte media.
- **212 (Go `flama-media`)**: mọi xử lý media (kiểm tra, làm sạch, resize, WebP, lưu theo id, tải URL, sinh SVG nét chữ).
- **OV (`media.flama.vn`, chỉ nginx)**: cổng đọc/ghi công khai, lưu file SVG nét chữ, nối 212 qua WireGuard.
- FE upload thẳng `https://media.flama.vn/media/upload` bằng ticket, nhận `stg_…`; khi lưu note Flask commit qua WireGuard và ghi `/store/<asset_id>`.
- FE ghép `/store/<id>` với `VITE_MEDIA_BASE_URL`; luồng đọc không qua Flask.
- Phát hiện file độc hại chỉ cảnh báo admin, không tự khoá tài khoản.

Mặc định đang dùng cho các điểm chưa chốt (đổi nếu chủ dự án quyết khác):
- id: staging `stg_…` rồi commit (file bỏ dở tự hết hạn).
- Nét chữ: OV không chạy Go; OV thiếu file thì lấy từ 212 và lưu lại (`proxy_store`).
- File riêng tư (avatar, đính kèm hỗ trợ, QR): tạm giữ trên VPS.

## Từng chức năng

| # | Chức năng | Trạng thái | Người nhận |
|---|---|---|---|
| 1 | Upload thẳng FE → 212 (staging, commit, preset + WebP, symlink id) | Go đã chạy trên 212 từ 2026-11-01 13:04 UTC; OV route `/media/staged/` (GET). App chờ merge PR #283 | Claude |
| 2 | Tải ảnh/trang từ URL qua Go (`POST /media/fetch-url`, chỉ qua WireGuard) | Go đã chạy trên 212; Flask `remote_image_fetcher` gọi worker, chờ PR #283 | Claude |
| 3 | SVG nét chữ: 212 sinh + lưu `/data/flama/strokes`, OV nginx `proxy_store` khi thiếu | Đã chạy trên 212 và OV; `FLAMA_STROKE_WORKER_ENABLED=1` trong env, có hiệu lực sau PR #283 | Claude |
| 4 | Báo sự cố chỉ tạo cảnh báo + audit, không khoá tài khoản | Code trong PR #283; `/api/v1/internal/` miễn CSRF | Claude |
| 5 | Dọn: bỏ timer sync, fallback nginx về app, route media/stroke Flask, Pillow, worksheet tự tải SVG từ GitHub trên VPS | Sau khi 1–3 chạy ổn trên prod | — |

## Việc sau khi PR #283 deploy

1. Thử upload ảnh và audio TTS trong một thẻ thật; kiểm tra field lưu `/store/<uuid>` và file có trên 212.
2. Bật báo sự cố trên 212: `SECURITY_CALLBACK_URL=http://wg-app-server:4789/api/internal/security/incident` (đường không có `/v1`), rồi restart `flama-media`. Chỉ làm sau khi bản chỉ-cảnh-báo đã chạy.
3. Merge TrinhChung/flama-media#1 để CI build lại đúng bản đang chạy (CI chỉ thay binary, không sửa `.env`).
