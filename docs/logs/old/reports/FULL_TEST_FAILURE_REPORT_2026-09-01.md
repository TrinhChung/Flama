# Báo cáo điều tra lỗi full test — 2026-09-01

## Phạm vi

- Lệnh ban đầu: `python scripts/run_tests.py --all`
- Backend: 103 test files, 917 test cases, thời gian `528.668s` theo `unittest` (`551.83s` theo runner).
- Frontend: runner chọn 37 test files nhưng Vitest không khởi động được.
- Tổng thời gian runner: `562.22s`.
- Không thay đổi application code trong quá trình điều tra.

## Kết quả tổng quan

| Khu vực | Kết quả | Phân loại sau điều tra |
| --- | --- | --- |
| Backend | 917 tests: 13 failures, 7 errors, 1 skipped | 1 snapshot lệch thật; 16 case do media root không được cách ly; 1 case phụ thuộc DNS; 1 case phụ thuộc DB khi kiểm tra CLI; 1 case rò state rate-limit giữa test |
| Frontend | Exit code 127 | `vitest: not found`; chưa có kết quả đúng/sai cho 37 test files |
| `tests/test_admin_fee_config.py` | 10/10 pass khi chạy riêng | Không phát hiện lỗi trong file đang mở ở IDE |

Kết luận ngắn: chưa có bằng chứng cho thấy 20 backend failures/errors là 20 lỗi nghiệp vụ độc lập. Có 1 lỗi contract snapshot chắc chắn và 4 nhóm vấn đề về cách ly test hoặc môi trường. Frontend chưa được kiểm tra vì dependency cục bộ chưa đầy đủ.

## 1. API route snapshot chưa cập nhật

### Triệu chứng

Test fail ổn định cả khi chạy riêng:

```text
tests.test_api_v1_route_map.ApiRouteMapTests.test_rule_and_method_contract_is_stable
Expected 229, got 230
Added: POST /api/browse/cards/batch-delete
```

### Nguyên nhân gốc

Route canonical mới đã được đăng ký tại `app/api/v1/learning/browse.py`, nhưng `tests/snapshots/api_v1_routes.json` vẫn chỉ chứa 229 route. Lịch sử Git cho thấy commit `06ddcdb` thêm route canonical nhưng không cập nhật snapshot.

### Đánh giá

- Loại: lỗi repository/test contract thật, tái hiện độc lập.
- Ưu tiên: cao vì luôn làm backend suite đỏ.
- Cách xử lý đề xuất: xác nhận route mới là chủ đích, sau đó chạy `python scripts/update_route_snapshot.py` và review diff snapshot trước khi commit.

## 2. Media upload root không được cách ly trong test

### Triệu chứng

16 case fail/error khi cố ghi vào đường dẫn kế thừa từ `.env`:

```text
/workspaces/flama_media_storage/...
OSError: [Errno 30] Read-only file system
```

Các test bị ảnh hưởng:

1. `tests.test_stroke_service.TestStrokeService.test_batch_generate_strokes_deck`
2. `tests.test_stroke_service.TestStrokeService.test_batch_generate_strokes_overwrite`
3. `tests.test_stroke_service.TestStrokeService.test_resolve_stroke_items_html`
4. `tests.test_stroke_service.TestStrokeService.test_resolve_stroke_items_raw`
5. `tests.test_stroke_service.TestStrokeService.test_resolve_stroke_items_urls`
6. `tests.test_api_strokes.TestApiStrokes.test_batch_generate_strokes_api`
7. `tests.test_api_strokes.TestApiStrokes.test_generate_strokes_api`
8. `tests.test_api_strokes.TestApiStrokes.test_generate_strokes_chinese_api`
9. `tests.test_flama_connect_mcp.FlamaConnectMcpTests.test_import_image_base64_and_search_and_get`
10. `tests.test_flama_connect_mcp.FlamaConnectMcpTests.test_import_image_deduplication_merges_tags`
11. `tests.test_flama_connect_mcp.FlamaConnectMcpTests.test_import_image_url_mocked`
12. `tests.test_flashcard_api_integration.FlashcardApiIntegrationTests.test_canonical_api_content_crud_and_media_contract`
13. `tests.test_flashcard_api_integration.FlashcardApiIntegrationTests.test_study_edit_card_accepts_audio_filename_reference`
14. `tests.test_flashcard_api_integration.FlashcardApiIntegrationTests.test_study_next_payload_allowlists_legacy_audio_button_media`
15. `tests.test_study_behavior_acceptance_baseline.StudyBehaviorAcceptanceBaselineTests.test_import_and_connect_provenance_via_real_entrypoint`
16. `tests.test_support_tickets.SupportTicketApiTests.test_create_and_manage_ticket_flow`

### Bằng chứng xác nhận

Chạy lại bằng đúng `.venv` và đặt:

```bash
FLASHCARD_MEDIA_UPLOAD_ROOT=/tmp/flama-test-investigation.gq3EvA
```

Kết quả: 17 test chạy, gồm toàn bộ 16 case trên và test bổ sung trong module strokes, đều pass trong `11.432s`.

### Nguyên nhân gốc

Các test trên tạo app với `TESTING=True` và SQLite in-memory nhưng không truyền `FLASHCARD_MEDIA_UPLOAD_ROOT`. `app/settings.py` vì vậy resolve giá trị `.env_example`/`.env` là `../flama_media_storage`, nằm ngoài workspace và không bảo đảm có quyền ghi. Một số suite khác như `test_image_library.py` và `test_secure_image_pipeline.py` đã làm đúng bằng `TemporaryDirectory`.

### Đánh giá và đề xuất

- Loại: lỗi cách ly test/cấu hình môi trường, không phải lỗi logic media được chứng minh.
- Ưu tiên: cao vì gây 80% số backend failures/errors trong lần chạy này.
- Nên tạo helper/fixture dùng chung để mọi app test nhận media root tạm, hoặc để test runner cấp một root tạm riêng cho toàn tiến trình. Test không nên ghi vào media storage dùng chung của developer/runtime.

## 3. Rò state daily rate-limit giữa các test

### Triệu chứng

Fail trong full suite:

```text
tests.test_support_donation_payment_flow.SupportDonationPaymentFlowTests
  .test_saved_support_donation_webhook_marks_order_paid_and_records_entitlement
Expected 201, got 429
```

Test này pass khi chạy riêng; cả module `tests.test_support_donation_payment_flow` cũng pass 11/11.

### Nguyên nhân gốc

`app/services/daily_rate_limit_service.py` giữ `_LOCAL_DAILY_COUNTS` ở cấp module và bucket theo `user_id:date`. Nhiều test SQLite tạo lại database nên người dùng thường có `id=1`, nhưng bộ đếm Python vẫn sống xuyên suốt 917 tests. Route `/api/support-donation/checkout` thực tế được canonical `api_v1` blueprint xử lý, vì canonical routes được đăng ký trước legacy adapter, nên request này bị daily limiter kiểm tra.

Đã tái tạo chính xác bằng cách nạp trước 300 request cho `user_id=1`, sau đó chạy riêng test donation: test trả lại đúng lỗi `429 != 201`. Sau khi reset state, test chạy pass.

### Đánh giá và đề xuất

- Loại: test pollution/rò global state, có thể làm full suite flaky theo thứ tự chạy.
- Ưu tiên: cao.
- Cần reset `daily_rate_limit_service.reset_local_rate_limit_state()` giữa các test app, hoặc tắt daily rate limit theo mặc định cho `TESTING=True` và chỉ bật rõ trong `tests/test_daily_rate_limit.py`. Các test rate-limit chuyên biệt hiện đã reset state, nhưng các suite còn lại không được bảo vệ khỏi bucket tích lũy toàn tiến trình.

## 4. Test CLI audit phụ thuộc MySQL ngoài mục tiêu kiểm tra

### Triệu chứng

```text
tests.test_study_architecture_audit_cli.StudyArchitectureAuditCLITests
  .test_audit_subprocess_command_surface_isolation
```

Test mong `flask --app wsgi:create_app --help` liệt kê `startup-maintenance`, nhưng output chỉ có ba command Flask mặc định.

### Nguyên nhân gốc

Khi import `wsgi.py`, module thực thi ngay `app = create_app()`. App mặc định bật `STARTUP_CHECK_DB_CONNECTIVITY=True` và cố kết nối MySQL tại `localhost`. MySQL không chạy trong môi trường kiểm tra, nên Flask không load được app và không thể liệt kê custom commands. Phần `wsgi_audit` vẫn hoạt động vì entrypoint audit tắt startup mutators.

### Bằng chứng xác nhận

Chạy lại test với:

```bash
STARTUP_CHECK_DB_CONNECTIVITY=0 STARTUP_RUN_MAINTENANCE=0
```

Kết quả: test pass.

### Đánh giá và đề xuất

- Loại: test subprocess phụ thuộc môi trường DB; không chứng minh CLI command bị mất trong app hợp lệ.
- Ưu tiên: trung bình.
- Test nên truyền env cô lập cho cả hai subprocess, tối thiểu tắt connectivity check hoặc dùng SQLite tạm. Mục tiêu test là command surface, không phải readiness của MySQL.

## 5. Test secure image phụ thuộc DNS thật

### Triệu chứng

```text
tests.test_secure_image_pipeline.SecureImagePipelineTests
  .test_public_url_ingestion_uses_temp_url_and_async_worker_replaces_it
socket.gaierror: Temporary failure in name resolution
```

### Nguyên nhân gốc

Test mock `app.services.image_worker_service.fetch_remote_image`, nhưng bước ingestion ban đầu vẫn gọi `_resolve_remote_target()` và `socket.getaddrinfo()` thật cho `images.unsplash.com` để kiểm tra SSRF. Vì vậy test được xem như unit/integration cô lập nhưng vẫn cần DNS.

### Bằng chứng xác nhận

Chạy lại riêng khi DNS hoạt động: 1/1 pass trong `1.072s`.

### Đánh giá và đề xuất

- Loại: phụ thuộc mạng không ổn định trong test.
- Ưu tiên: trung bình.
- Mock bước DNS/resolved target với IP public cố định, hoặc tách test SSRF resolution khỏi test queue/worker flow.

## 6. Frontend không chạy vì thiếu Vitest trong `node_modules`

### Triệu chứng

```text
> frontend@0.0.0 test
> vitest run ...
sh: 1: vitest: not found
```

### Bằng chứng

- `frontend/package.json` khai báo `vitest` trong `devDependencies`.
- `frontend/package-lock.json` có entry `node_modules/vitest`.
- `frontend/node_modules/vitest` và symlink `frontend/node_modules/.bin/vitest` không tồn tại.
- `npm ls vitest --depth=0` trả về `(empty)`.

### Đánh giá và đề xuất

- Loại: dependency install cục bộ thiếu hoặc stale; 37 frontend test files chưa hề được thực thi.
- Ưu tiên: cao vì hiện chưa thể kết luận frontend pass/fail.
- Khôi phục dependency bằng `npm ci --prefix frontend`, sau đó chạy `python scripts/run_tests.py --frontend-only --all` hoặc `npm --prefix frontend test -- --run`.

## 7. Cảnh báo không làm suite fail nhưng cần theo dõi

1. Nhiều `ResourceWarning` cho file chưa đóng, đặc biệt `frontend/dist/index.html`, fallback image và media asset tạm.
2. Nhiều `DeprecationWarning` từ `datetime.utcnow()`/`datetime.utcfromtimestamp()` trên Python 3.12.
3. Nhiều `LegacyAPIWarning` do SQLAlchemy `Query.get()`; nên chuyển dần sang `db.session.get()`.
4. Các log như `disk full`, Redis offline, payOS failure, SMTP/Resend failure và security threat phần lớn xuất hiện trong test nhánh lỗi có chủ đích; không tự động xem chúng là test failure nếu case vẫn pass.

## Thứ tự xử lý đề xuất

1. Cài lại frontend dependencies và chạy đủ 37 frontend files để có baseline thật.
2. Cách ly `FLASHCARD_MEDIA_UPLOAD_ROOT` cho toàn bộ test app.
3. Reset/tách state daily rate-limit giữa các app test.
4. Xác nhận route batch-delete là chủ đích rồi cập nhật route snapshot.
5. Làm test CLI audit độc lập với MySQL.
6. Mock DNS trong secure image pipeline test.
7. Giảm dần ResourceWarning và các API deprecated.

## Lệnh kiểm chứng đã chạy

```bash
python scripts/run_tests.py --all

FLASHCARD_MEDIA_UPLOAD_ROOT=/tmp/flama-test-investigation.gq3EvA \
  .venv/bin/python -m unittest <17 media-related tests>

.venv/bin/python -m unittest -v \
  tests.test_api_v1_route_map.ApiRouteMapTests.test_rule_and_method_contract_is_stable \
  tests.test_study_architecture_audit_cli.StudyArchitectureAuditCLITests.test_audit_subprocess_command_surface_isolation \
  tests.test_support_donation_payment_flow.SupportDonationPaymentFlowTests.test_saved_support_donation_webhook_marks_order_paid_and_records_entitlement

.venv/bin/python -m unittest -v tests.test_support_donation_payment_flow

STARTUP_CHECK_DB_CONNECTIVITY=0 STARTUP_RUN_MAINTENANCE=0 \
  .venv/bin/python -m unittest -v \
  tests.test_study_architecture_audit_cli.StudyArchitectureAuditCLITests.test_audit_subprocess_command_surface_isolation

.venv/bin/python -m unittest -v \
  tests.test_secure_image_pipeline.SecureImagePipelineTests.test_public_url_ingestion_uses_temp_url_and_async_worker_replaces_it

.venv/bin/python -m unittest -v tests.test_admin_fee_config
npm ls vitest --depth=0
```

## Files chính đã đối chiếu

- `scripts/run_tests.py`
- `Dockerfile`, `docker-compose.yml`, `.env_example`
- `wsgi.py`, `wsgi_audit.py`
- `app/__init__.py`, `app/extensions.py`, `app/settings.py`, `app/startup.py`
- `app/routes/__init__.py`, `app/api/__init__.py`, `app/cli.py`
- `app/api/v1/__init__.py`
- `app/api/v1/learning/browse.py`
- `app/api/v1/billing/support.py`
- `app/services/daily_rate_limit_service.py`
- `app/services/remote_image_fetcher.py`
- Các test files được nêu trong từng nhóm trên
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/node_modules`
- `README.md`, `README_SETUP.md`, `docs/architecture/SYSTEM_ARCHITECTURE.md`

## Khoảng trống còn lại

- Chưa có kết quả frontend cho đến khi Vitest được cài đúng.
- Chưa chạy lại toàn bộ 917 backend tests với media root tạm và rate-limit được reset, vì yêu cầu hiện tại là điều tra và lập báo cáo, chưa sửa test harness.
- Chưa cập nhật route snapshot vì cần xác nhận thay đổi API là contract được chấp nhận, không nên tự động ghi nhận snapshot chỉ để làm test xanh.
- `docs/architecture/SYSTEM_ARCHITECTURE.md` vẫn mô tả các tác vụ schema/seed/cutover như hành vi startup chung, trong khi `app/settings.py` hiện gate chúng bằng các cờ `STARTUP_*` và mặc định không chạy maintenance ngoài `TESTING`. Nên chỉnh tài liệu kiến trúc ở một task riêng.
