# REST API V1 Migration Plan

## 1. Mục tiêu

Hoàn tất quá trình chuyển frontend React sang REST API có version mà không làm thay đổi
nghiệp vụ hiện tại, không phá scheduler, media security, payment idempotency hoặc mô
hình shared-deck logical overlay.

Runtime chuẩn vẫn là:

- Local: `flask --app wsgi.py run --host=0.0.0.0 --port=4789`
- Production/Docker: `gunicorn --bind 0.0.0.0:4789 wsgi:app`

Migration này không bao gồm schema migration, scheduler rewrite hoặc API V2 redesign.

## 2. Kết quả audit ban đầu

Tại thời điểm lập kế hoạch:

- 221 Flask route-rule.
- 46 route-rule dưới `/api/v1`.
- 93 API route-rule chưa version hóa.
- 82 route page, file, redirect hoặc legacy.
- Các route Level/Topic/Lesson/Entry đã retired và không được khôi phục.

REST API và React hiện mới migrate một phần:

| Miền | Trạng thái ban đầu |
| --- | --- |
| Auth/session | Gần hoàn tất trên V1 |
| Dashboard/deck CRUD | Có V1 nhưng route còn ORM/transaction logic |
| Statistics | Có V1, production deep-link vẫn có thể vào Jinja |
| Browse | Có V1 alias nhưng gọi trực tiếp handler legacy |
| Study | React dùng `/api/study/*` legacy |
| Note type/note/template/media | React dùng `/api/*` legacy |
| Import | React dùng `/api/flashcards/import/*` legacy |
| Marketplace/change request | Chủ yếu dùng `/api/shared/*` và `/api/change-requests/*` |
| Orders/payment/support | Read API một phần trên V1; mutation còn legacy |
| Admin | Users/payment/TTS một phần trên V1; batch/payout còn legacy |
| Admin support/image/MCP token | Có backend V1 nhưng thiếu React consumer |

Các blocker đã xác định:

1. Support checkout bị gọi thành `/api/v1/support-donation/checkout` nhưng endpoint đó
   chưa tồn tại.
2. Admin batch role/status bị gọi thành `/api/v1/admin/api/users/...` nhưng endpoint đó
   chưa tồn tại.
3. VoiceVox preview và study media upload dùng `fetch` trực tiếp, không gửi CSRF.
4. Flask chưa phục vụ SPA shell nhất quán cho các React deep-link.
5. V1 browse gọi trực tiếp route handler trong `app/routes/vocabulary.py`.
6. `app/routes/rest_api.py` là god-file, đồng thời parse HTTP, query ORM, commit và
   serialize response.

## 3. Tiêu chí một chức năng đã migrate

Một chức năng chỉ được đánh dấu `V1_PRIMARY` khi đồng thời đạt:

1. Có endpoint canonical dưới `/api/v1`.
2. React và client nội bộ dùng endpoint V1.
3. Handler V1 không gọi handler route legacy.
4. V1 và legacy adapter gọi cùng application service.
5. API route không sở hữu query/persistence hoặc transaction phức tạp.
6. Auth, ownership, admin permission, validation, CSRF và rollback có test.
7. Deep-link React hoạt động khi refresh trong production.
8. Legacy endpoint không còn là implementation owner.

Trạng thái dùng trong inventory:

- `V1_PRIMARY`: endpoint V1 và consumer đã cut over.
- `V1_ALIAS`: có URL V1 nhưng còn phụ thuộc handler legacy.
- `LEGACY_ONLY`: chưa có endpoint V1.
- `EXEMPT_NON_REST`: protocol, webhook hoặc binary delivery không thuộc REST migration.
- `DEPRECATED`: compatibility endpoint đang chờ sunset.

## 4. Cấu trúc thư mục mục tiêu

```text
app/
  api/
    __init__.py
    common/
      errors.py
      pagination.py
      requests.py
      responses.py
      security.py

    v1/
      __init__.py

      identity/
        routes.py
        schemas.py
        presenters.py

      decks/
        routes.py
        schemas.py
        presenters.py

      analytics/
        routes.py
        schemas.py
        presenters.py

      learning/
        browse.py
        study.py
        schemas.py
        presenters.py

      flashcards/
        note_types.py
        notes.py
        media.py
        imports.py
        schemas.py
        presenters.py

      marketplace/
        catalog.py
        publishing.py
        installations.py
        reviews.py
        change_requests.py
        schemas.py
        presenters.py

      billing/
        orders.py
        support.py
        schemas.py
        presenters.py

      settings/
        tts.py
        mcp_tokens.py
        schemas.py
        presenters.py

      admin/
        users.py
        payments.py
        payouts.py
        tts.py
        support.py
        image_library.py
```

Nguyên tắc:

- `app/api/**` chỉ parse request, gọi service và map HTTP response.
- Business orchestration và transaction owner nằm trong `app/services/`.
- Query/persistence nằm trong `app/repositories/`.
- Sanitization và validation nghiệp vụ tiếp tục nằm trong `app/validators/`.
- `schemas.py` chỉ parse/coerce contract HTTP.
- `presenters.py` chỉ serialize, không query và không commit.
- Không tạo service/repository thứ hai bên trong `app/api`.
- `app/routes/` tiếp tục giữ Jinja, SPA shell, binary delivery, provider callbacks và
  legacy adapters trong thời gian chuyển tiếp.

Luồng chuyển tiếp:

```text
Legacy route ---\
                 +--> Application service --> Repository
REST V1 --------/
```

Không redirect mutation legacy sang V1 và không để route gọi route.

## 5. Contract V1

### 5.1 Versioning và naming

- Dùng path versioning `/api/v1`.
- URL dùng plural noun và kebab-case.
- JSON tiếp tục dùng snake_case.
- Không đổi path/status/payload V1 hiện tại chỉ để REST thuần hơn.
- Action endpoint như `progress-reset`, study answer hoặc preview được giữ trong V1
  nếu đổi tên làm tăng rủi ro; redesign dành cho V2.
- Pagination dùng `page`, `per_page`; search dùng `q`.

### 5.2 Error response

V1 giữ envelope tương thích với client hiện tại:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Deck name is required.",
  "field": "name",
  "details": [],
  "request_id": "optional"
}
```

`details` và `request_id` là optional. Không chuyển sang nested error object trong V1.

### 5.3 Auth và CSRF

- First-party SPA tiếp tục dùng Flask-Login session.
- Client dùng `credentials: same-origin`.
- Unsafe method gửi CSRF token lấy từ `/api/v1/session`.
- Không bật CORS rộng.
- Admin guard và JSON 401/403 dùng common API helper.
- Bearer authentication chỉ được exempt CSRF cho endpoint/protocol thực sự dùng Bearer.

### 5.4 Ngoại lệ không migrate vào REST V1

- `/api/mcp`: MCP JSON-RPC.
- PayOS webhook: external provider callback có signature/idempotency contract riêng.
- `/media/*`, QR image, asset/download route: binary delivery.
- Static asset và SPA shell.

## 6. Transaction ownership

Đích đến:

```text
API route --> application service (transaction owner) --> repository
```

- API route mới không gọi `commit()` hoặc `rollback()`.
- Repository không commit.
- Mỗi mutation use case có một transaction owner.
- Payment webhook có thể có durable multi-step commit nếu được ghi rõ.
- Media/file mutation phải có compensation khi DB commit thất bại.
- Marketplace install phải giữ deadlock retry và logical overlay behavior.

## 7. Kế hoạch triển khai

### Phase 0 - Contract freeze và blocker

- Lập inventory endpoint/consumer/service/permission/transaction/test.
- Thêm target V1 cho support checkout và admin batch.
- Chuẩn hóa frontend URL builder.
- Thêm client helper cho JSON, FormData và binary response có CSRF.
- Thống nhất SPA shell/deep-link.
- Sửa các link React trỏ sai route hoặc quay lại Jinja ngoài chủ đích.

Acceptance:

- Không còn lỗi 404/CSRF do migration wiring.
- React deep-link canonical refresh đúng SPA.
- API contract hiện có không bị thay đổi ngoài endpoint mới.

### Phase 1 - Chia REST god-file

- Tạo `app/api/common` và `app/api/v1`.
- Chia `rest_api.py` và `admin_rest_api.py` theo bounded context.
- Giữ nguyên URL, status code và payload.
- Đăng ký qua parent V1 blueprint.

Acceptance:

- URL map V1 không mất endpoint.
- Existing V1 tests giữ nguyên expected contract.
- Startup qua `wsgi.py` load thành công.

### Phase 2 - Tách V1 khỏi legacy route

- Tách browse use cases khỏi `vocabulary.py`.
- V1 và vocabulary legacy cùng gọi service.
- Chuyển deck/auth/admin/MCP token mutation khỏi API route vào service.
- Tách presenter/serializer khỏi route.

Acceptance:

- Không có `from app.routes...` trong `app/api/**`.
- API route không query ORM/commit trực tiếp.
- Browse payload V1 không đổi.

### Phase 3 - Content management

Thứ tự:

1. Note type, field, template.
2. Note và card.
3. Media upload/delete.
4. Flashcard import parse/estimate/execute.

Acceptance từng slice:

- React chỉ dùng `/api/v1`.
- Legacy và V1 gọi cùng service.
- Sanitization, CSP và media proxy không đổi.
- File cleanup và rollback được test.

### Phase 4 - Learning runtime

- Hoàn thiện Browse parity.
- Migrate Study next/answer/edit.
- Migrate TTS user profile, validation, voices và VoiceVox.

Acceptance:

- Scheduler/timezone/day-boundary behavior không đổi.
- Direct-owner và installed-overlay cases đều pass.
- Study counts, ordering và renderer contract không đổi.

### Phase 5 - Marketplace, billing và admin

- Marketplace catalog/save/publish/install/rate.
- Change-request requester/inbox/detail/approve/reject.
- Payment order/cancel và support checkout.
- Admin batch roles/status, payouts và payment details.
- React screen cho admin support, image library, MCP tokens và full TTS CRUD.

Acceptance:

- Install không copy hoặc mutate source Note/Card.
- Overlay chỉ ghi đúng các bảng `DeckClone*`.
- Payment idempotency, webhook signature và audit semantics không đổi.

### Phase 6 - Consumer cutover và deprecation

- React không còn gọi JSON API chưa version hóa ngoài allowlist.
- Thêm legacy usage logging.
- Thêm `Deprecation`, `Sunset` và successor `Link` header.
- Chỉ sunset sau ít nhất một chu kỳ release không còn consumer.
- Xóa legacy trong PR/release riêng.

## 8. Test strategy

Giữ test suite dạng flat `unittest`:

```text
tests/
  test_api_v1_auth.py
  test_api_v1_decks.py
  test_api_v1_analytics.py
  test_api_v1_browse.py
  test_api_v1_study.py
  test_api_v1_flashcards.py
  test_api_v1_marketplace.py
  test_api_v1_billing.py
  test_api_v1_admin.py
  test_api_v1_errors.py
  test_api_v1_csrf.py
  test_api_v1_legacy_parity.py
  test_spa_routes.py
```

Tối thiểu phải kiểm tra:

- Anonymous/authenticated/admin/owner/installed-clone permission.
- CSRF missing/wrong/correct token.
- JSON 401/403/404/405.
- Error envelope.
- Rollback không để lại dữ liệu dở dang.
- Legacy/V1 parity trên cùng dữ liệu.
- React deep-link trả SPA shell.
- Overlay-only behavior.
- SQLite focused tests và MySQL smoke cho query/transaction rủi ro.

## 9. Guardrails

- Không khôi phục Level/Topic/Lesson/Entry.
- Không reintroduce full-copy clone.
- Không mutate source notes trong installed clone flows.
- Không hand-roll scheduler/day boundary trong route.
- Không bypass media sanitizer, CSP hoặc `/media/proxy`.
- Không đổi PayOS webhook contract trong REST migration.
- Không gộp REST migration với schema migration.
- Không xóa Jinja/API legacy trước khi parity và usage đạt điều kiện sunset.

## 10. Theo dõi tiến độ

| Phase | Trạng thái |
| --- | --- |
| Phase 0 - Contract freeze và blocker | Completed |
| Phase 1 - Chia REST god-file | Completed |
| Phase 2 - Tách V1 khỏi legacy route | Completed |
| Phase 3 - Content management | Completed |
| Phase 4 - Learning runtime | Planned |
| Phase 5 - Marketplace, billing và admin | Planned |
| Phase 6 - Consumer cutover và deprecation | Planned |

## 11. Implementation log

### 2026-07-28 - Phase 0 hoàn tất

- Đã tạo parent blueprint `app/api/v1` và common response/security helper.
- Đã thêm canonical endpoint:
  - `POST /api/v1/support-donation/checkout`
  - `POST /api/v1/admin/users/status/batch`
  - `POST /api/v1/admin/users/roles/batch`
- Legacy và V1 support checkout đã dùng chung `support_checkout_service`; không thay
  đổi PayOS webhook.
- Admin batch React đã trỏ đúng V1.
- JSON, `FormData` và binary request của React đã đi qua HTTP client tự gắn CSRF.
- Vite đã proxy `/static` để study renderer hoạt động trong development.
- Canonical React deep-link đã có SPA route cho browse, study, import, installed deck,
  marketplace, support và admin TTS.
- Các page canonical statistics, orders, admin users và admin payments đã cut over
  sang SPA shell.
- Docker image đã có frontend build stage để production luôn chứa `frontend/dist`
  khi build từ clean checkout.

### 2026-07-28 - Phase 1 và Phase 2 hoàn tất

- Đã chuyển admin TTS, support config và image library khỏi
  `app/routes/admin_rest_api.py` sang:
  - `app/api/v1/admin/tts.py`
  - `app/api/v1/admin/support.py`
  - `app/api/v1/admin/image_library.py`
- Đã chuyển user/admin payment/order/MCP-token resource vào bounded-context module
  dưới `app/api/v1`.
- Đã chuyển identity/session, deck, dashboard/statistics và installed-deck resource
  sang các module:
  - `app/api/v1/identity/routes.py`
  - `app/api/v1/decks/routes.py`
  - `app/api/v1/analytics/routes.py`
  - `app/api/v1/marketplace/installations.py`
- `app/routes/rest_api.py` và `app/routes/admin_rest_api.py` hiện chỉ còn
  compatibility import; application đăng ký V1 duy nhất qua `app/api/v1`.
- MCP-token mutation đã chuyển transaction ownership từ API route vào service.
- Identity/session, deck mutation và admin user mutation đã chuyển ORM query,
  transaction ownership và rollback sang:
  - `app/services/identity_api_service.py`
  - `app/services/deck_api_service.py`
  - `app/services/admin_user_api_service.py`
- Browse deck/card/note và logical-clone overlay đã chuyển sang
  `app/services/browse_card_service.py`; VoiceVox preview/precheck/generate đã chuyển
  sang `app/services/browse_voicevox_service.py`.
- `app/api/v1/learning/browse.py` hiện là V1 primary route, không còn import hoặc
  gọi handler trong `app/routes/vocabulary.py`. Legacy Browse chỉ còn HTTP adapter
  gọi cùng service.
- Không còn `from app.routes...`, ORM query hoặc `db.session` transaction trực tiếp
  trong `app/api/**`; model import còn lại chỉ là type/presenter của deck.
- V1 URL map hiện có 49 rule; 46 contract cũ được giữ và có thêm 3 endpoint blocker.
- `tests/test_api_v1_route_map.py` khóa snapshot method/path để phát hiện mất hoặc
  trùng V1 route trong các phase sau.

### 2026-07-28 - Phase 3 hoàn tất

- Đã thêm 28 canonical endpoint cho note type, field, template, note, media và
  flashcard import dưới `app/api/v1/flashcards/`; V1 URL map hiện có 77 rule.
- HTTP parsing/response mapping nằm trong các module `note_types.py`, `notes.py`,
  `media.py` và `imports.py`; query, orchestration và transaction ownership nằm
  trong:
  - `app/services/flashcard_content_service.py`
  - `app/services/flashcard_media_api_service.py`
  - `app/services/flashcard_import_api_service.py`
- Legacy flashcard endpoint và V1 endpoint gọi cùng application service để giữ
  behavior parity trong thời gian cutover.
- React note-type manager/detail/fields, Library note-type list và Import page đã
  chuyển sang `/api/v1`; không còn gọi `/api/note-types` hoặc
  `/api/flashcards/import`.
- Media upload tiếp tục dùng validator chữ ký/kích thước, đường dẫn lưu trữ an toàn
  và `/media/proxy/<asset_id>`; không thay đổi renderer/CSP contract.
- Media service có compensating cleanup: rollback DB và xóa file vừa ghi nếu commit
  thất bại. Test xác nhận không còn `MediaAsset` hoặc file rác sau lỗi.
- Đã thêm V1 CRUD/media/import integration test, legacy/V1 parity test và mở rộng
  route-map snapshot lên 77 rule.

### Verification đã chạy

- `python -m compileall -q app`
- `npm run check`
- Focused backend suites cho REST V1, admin REST, admin roles, support checkout,
  MCP token, SPA routing, deck settings và statistics; 86 test đã pass trong lần
  verification Phase 1.
- Phase 2: 46 focused regression test đã pass cho REST V1, route-map snapshot,
  Browse logical-overlay/deck settings, admin user roles và auth security.
- Browse VoiceVox precheck có parity test giữa legacy và V1 adapter.
- Phase 3: 106 focused regression test đã pass cho REST V1, flashcard
  CRUD/import/media security, deck settings và route-map snapshot. Frontend
  lint/type-check/build đã pass; chỉ còn warning lint/chunk-size đã tồn tại.

### Công việc còn lại trước khi migration hoàn tất

- Thêm V1 và cut over React cho study/TTS learning runtime.
- Thêm V1 và cut over marketplace/change-request/payment mutations và phần admin
  còn lại.
- Chạy một release cycle với legacy usage logging trước khi thêm sunset header và
  xóa endpoint cũ.
