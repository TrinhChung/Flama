# Flama Post-Refactor Architecture Review [HISTORICAL AUDIT - RESOLVED]

> **Trạng thái:** TÀI LIỆU LỊCH SỬ - ĐÃ GIẢI QUYẾT (HISTORICAL / RESOLVED)  
> **Ghi chú:** Các vấn đề import, boundary và regression được chỉ ra trong đợt audit 2026-03-01 đã được xử lý triệt để trong các phase sau (Phase N1, N2, N3 và REST API Migration 2026-07/2026-08). Hệ thống hiện tại vận hành hoàn toàn trên React SPA + Flask REST API canonical.

**Baseline dùng để so sánh:** [`FLAMA_ARCHITECTURE_REVIEW.md`](../historical/FLAMA_ARCHITECTURE_REVIEW.md), [`FLAMA_REFACTOR_PLAN.md`](../historical/FLAMA_REFACTOR_PLAN.md)  
**Snapshot code được review:** working tree ngày **2026-03-01**  
**Nguyên tắc đánh giá:** bám code hiện tại, không đoán; có gì chưa đủ bằng chứng sẽ ghi rõ.

## 1. Executive Summary
- Kiến trúc đã tiến bộ rõ theo hướng tách lớp (đặc biệt ở stats query và tách route flashcards theo thư mục), nhưng đang ở trạng thái **half-migrated**: boundary sạch hơn ở vài khu vực, đồng thời phát sinh lỗi import/runtime critical.
- Đợt refactor vừa rồi thành công khoảng **mức trung bình**: đạt được nhiều bước nền tảng, nhưng hiện chưa ổn định để coi là “done” vì app chưa boot sạch trong trạng thái hiện tại.
- 5 kết luận quan trọng nhất:
  1. **Critical regression**: import graph đang vỡ (`app/__init__.py:128`, `app/cli.py:17`, `app/routes/flashcards/__init__.py:35`, `app/routes/flashcards/__init__.py:39`, `app/routes/flashcards/import_export.py:44`, `app/services/study_service.py:14`).
  2. **Dependency flow đã cải thiện nhưng chưa sạch**: còn service import ngược route helper (`app/services/note_type_service.py:9`, `app/services/flashcard_media_service.py:7`, `app/services/study_service.py:15`).
  3. **God-file cũ giảm nhưng god-file mới xuất hiện**: `app/services/flashcards_share_service.py` (~2312 lines), `app/routes/vocabulary.py` (~1246 lines), `static/js/components/browse_modal.js` (~1219 lines).
  4. **Template cleanup mới partial**: `dashboard` và `shared_deck_detail` sạch hơn, nhưng nhiều template vẫn fat với inline JS rất lớn.
  5. **Chưa thể chuyển phase refactor sâu** trước khi xử lý phase ổn định import/runtime + smoke test.

## 2. So sánh với baseline cũ

### Những vấn đề cũ đã xử lý xong
- **Done** — Tách god-file route flashcards theo module: đã có `app/routes/flashcards/__init__.py`, `app/routes/flashcards/share.py`, `app/routes/flashcards/study.py`, `app/routes/flashcards/import_export.py`, `app/routes/flashcards/note_type.py`, `app/routes/flashcards/media.py`.
- **Done** — Dashboard route mỏng hơn: `app/routes/main.py:60-71` gọi `build_dashboard_data` thay vì tự ôm toàn bộ traversal.
- **Done** — Stats service chuyển sang repository/query module: `app/services/stats_overview.py:9-15`, `app/services/stats_today_future.py:11-20`.
- **Done** — Một phần inline JS đã tách ra static modules:
  - `templates/dashboard.html:935` -> `static/js/pages/dashboard/*`
  - `templates/flashcards/shared_deck_detail.html:154` -> `static/js/pages/shared_deck_detail/*`

### Những vấn đề cũ mới xử lý một phần
- **Partial** — Dependency flow Route -> Service -> Repository: đã có repository mới, nhưng route vẫn query ORM trực tiếp nhiều chỗ, service vẫn phụ thuộc route helper.
- **Partial** — Naming chuẩn hóa controller -> repository: có `app/repositories/*`, nhưng naming/role chưa đồng bộ (docstring và import path còn dấu vết legacy).
- **Partial** — Template cleanup: mới dọn 2 trang, còn nhiều template giữ inline orchestration.

### Những vấn đề cũ vẫn còn nguyên
- **Unchanged** — `app/routes/vocabulary.py` vẫn là bottleneck lớn, còn query/transaction/permission/orchestration trộn.
- **Unchanged** — Trùng lặp deck visibility/tree traversal ở nhiều module (`dashboard_service`, `vocabulary_repository`, `flashcards_import_repository`, `deck_tree_query`, `flashcards_share_service`).
- **Unchanged** — Route layer còn chọc ORM sâu ở nhiều endpoint.

### Những vấn đề mới phát sinh sau refactor
- **New Regression (Critical)** — App boot lỗi import:
  - `app/__init__.py:128` và `app/cli.py:17` import `flashcards_share` từ `app.services`, nhưng `app/services/__init__.py` không export.
  - `app/routes/flashcards/__init__.py:35` và `app/routes/flashcards/__init__.py:39` còn import `app.controllers.*` dù thư mục đã xóa.
  - `app/routes/flashcards/import_export.py:44` còn import `app.services.deck_service` (không tồn tại).
  - `app/services/study_service.py:14` import `app.services.user_settings` (không tồn tại).
- **New Regression (High)** — Runtime variable chưa định nghĩa:
  - `app/routes/vocabulary.py:753` dùng `deck_obj` chưa định nghĩa.
  - `app/routes/flashcards/import_export.py:115` dùng `existing_item_was_found` chưa định nghĩa.
- **New Regression (High)** — Test import vỡ theo app import:
  - `python -m unittest tests.test_stats_overview -q` fail vì import error ở `app/cli.py`.

## 3. Đánh giá theo từng tầng

### 3.1 Route
**Đã cải thiện**
- `main.dashboard` đã mỏng hơn và có service boundary (`app/routes/main.py:60-71`).
- Route flashcards đã tách file theo domain.

**Vẫn còn vấn đề**
- Nhiều route vẫn query model trực tiếp (ví dụ `app/routes/vocabulary.py`, `app/routes/admin.py`, `app/routes/flashcards/share.py`, `app/routes/flashcards/note_type.py`).
- `vocabulary` còn rollback/commit ở route (`app/routes/vocabulary.py:661-663`, `app/routes/vocabulary.py:895`, `app/routes/vocabulary.py:963`, `app/routes/vocabulary.py:994`, `app/routes/vocabulary.py:1014`).
- Legacy import còn sót trong flashcards route package gây fail boot.

**File tiêu biểu**
- `app/routes/vocabulary.py`
- `app/routes/flashcards/__init__.py`
- `app/routes/main.py`
- `app/routes/admin.py`

**Nhận xét mức độ sạch boundary hiện tại**
- **Chưa sạch**; mức hiện tại là **partial migration**.

### 3.2 Application Service
**Đã cải thiện**
- Stats service sử dụng repository/query rõ hơn (`app/services/stats_overview.py`, `app/services/stats_today_future.py`).
- Một số transaction đã chuyển vào service (`app/services/admin_service.py`, `app/services/deck_management_service.py`).

**Vẫn còn vấn đề**
- Service import ngược route helper:
  - `app/services/note_type_service.py`
  - `app/services/flashcard_media_service.py`
  - `app/services/study_service.py`
- `app/services/flashcards_share_service.py` quá lớn, trộn nhiều bounded context.

**File tiêu biểu**
- `app/services/stats_overview.py`
- `app/services/stats_today_future.py`
- `app/services/study_service.py`
- `app/services/flashcards_share_service.py`

**Transaction boundary hiện tại có đúng chưa**
- **Chưa đúng hoàn toàn**: có cải thiện nhưng route vẫn còn commit/rollback trực tiếp ở `vocabulary`.

### 3.3 Repository / Query Layer / Legacy Controller
**Những file đã đúng vai trò hơn**
- `app/repositories/stats_query_repository.py`
- `app/repositories/review_event_repository.py`
- `app/repositories/card_progress_repository.py`
- `app/repositories/deck_tree_query.py` (đã bắt đầu gom tree query)

**Những file còn legacy naming hoặc legacy responsibility**
- `app/repositories/vocabulary_repository.py` vẫn ôm nhiều business/overlay orchestration.
- `app/repositories/flashcards_import_repository.py` còn import service (`from app.services import flashcards_share`) -> ngược chiều.

**Có cần tách tiếp / rename tiếp không**
- **Có**: cần tách query thuần khỏi business clone overlay; chuẩn hóa repository chỉ làm data access/query.

### 3.4 Template + Static JS
**Template đã sạch hơn**
- `templates/dashboard.html` (module script)
- `templates/flashcards/shared_deck_detail.html` (module script)

**Template vẫn fat**
- `templates/flashcards/import.html`
- `templates/statistics.html`
- `templates/vocabulary_browse.html`
- `templates/flashcards/shared_note_type_detail.html`
- `templates/admin/users.html`
- `templates/admin/permission_assignment.html`

**JS module bắt đầu phình to**
- `static/js/components/browse_modal.js` (~1219 lines) đang là god-js mới.

**UI logic nên gom lại theo page/domain**
- Browse: tách `browse_modal.js` thành data/api/state/render/actions.
- Statistics/import/vocabulary_browse: chuyển inline JS sang `static/js/pages/*` theo domain page.

## 4. Các vấn đề còn tồn tại

### Vấn đề A
- Mức độ: **Critical**
- File / module liên quan: `app/__init__.py:128`, `app/cli.py:17`, `app/services/__init__.py`
- Hiện trạng sau refactor: import `flashcards_share` không hợp lệ làm fail boot.
- So với baseline cũ: **phát sinh mới**.
- Vì sao đây vẫn là vấn đề: app không khởi động được ổn định.
- Rủi ro nếu giữ nguyên: chặn toàn bộ test/regression pipeline.
- Hướng xử lý đề xuất: chuẩn hóa một entrypoint share module (shim hoặc import trực tiếp module đích), đảm bảo `from app import create_app` pass.

### Vấn đề B
- Mức độ: **Critical**
- File / module liên quan: `app/routes/flashcards/__init__.py:35`, `app/routes/flashcards/__init__.py:39`
- Hiện trạng sau refactor: còn import `app.controllers.*` trong khi thư mục đã xóa.
- So với baseline cũ: **phát sinh mới**.
- Vì sao đây vẫn là vấn đề: vỡ import graph ngay lúc load route.
- Rủi ro nếu giữ nguyên: runtime crash sớm.
- Hướng xử lý đề xuất: thay toàn bộ import legacy sang service/repository mới tương ứng.

### Vấn đề C
- Mức độ: **Critical**
- File / module liên quan: `app/routes/flashcards/import_export.py:44`, `app/services/study_service.py:14`
- Hiện trạng sau refactor: import module không tồn tại (`deck_service`, `user_settings`).
- So với baseline cũ: **phát sinh mới**.
- Vì sao đây vẫn là vấn đề: code path bất kỳ chạm vào sẽ fail runtime.
- Rủi ro nếu giữ nguyên: lỗi production theo endpoint.
- Hướng xử lý đề xuất: mapping về module mới (`deck_access_policy`/`stats_overview.update_user_timezone` hoặc module trung lập).

### Vấn đề D
- Mức độ: **High**
- File / module liên quan: `app/routes/vocabulary.py:753`, `app/routes/flashcards/import_export.py:115`
- Hiện trạng sau refactor: dùng biến chưa định nghĩa (`deck_obj`, `existing_item_was_found`).
- So với baseline cũ: **phát sinh mới**.
- Vì sao đây vẫn là vấn đề: gây lỗi runtime trực tiếp.
- Rủi ro nếu giữ nguyên: request fail 500 theo flow cụ thể.
- Hướng xử lý đề xuất: fix biến theo đúng context hiện tại + thêm test regression cho 2 flow.

### Vấn đề E
- Mức độ: **High**
- File / module liên quan: `app/routes/vocabulary.py`
- Hiện trạng sau refactor: route vẫn lớn, query + business + permission + transaction trộn.
- So với baseline cũ: **cải thiện ít**.
- Vì sao đây vẫn là vấn đề: bottleneck maintainability và hồi quy.
- Rủi ro nếu giữ nguyên: khó test, conflict merge cao.
- Hướng xử lý đề xuất: tách theo use-case modules + service facade, giảm ORM access trực tiếp từ route.

### Vấn đề F
- Mức độ: **High**
- File / module liên quan: `app/services/note_type_service.py`, `app/services/flashcard_media_service.py`, `app/services/study_service.py`
- Hiện trạng sau refactor: service import ngược route helper.
- So với baseline cũ: **chưa đạt mục tiêu dependency flow**.
- Vì sao đây vẫn là vấn đề: vi phạm chiều phụ thuộc, khó mock/test.
- Rủi ro nếu giữ nguyên: coupling cao, refactor chồng chéo.
- Hướng xử lý đề xuất: tách helper dùng chung khỏi route package sang module trung lập.

### Vấn đề G
- Mức độ: **High**
- File / module liên quan: `app/services/flashcards_share_service.py`
- Hiện trạng sau refactor: god-service mới (~2312 lines), trộn publish/install/clone/rating/cutover/query.
- So với baseline cũ: **đổi vị trí monolith**, chưa giảm độ phức tạp tổng.
- Vì sao đây vẫn là vấn đề: thay đổi nhỏ cũng chạm nhiều luồng.
- Rủi ro nếu giữ nguyên: regression dây chuyền.
- Hướng xử lý đề xuất: tách bounded context và chuẩn hóa facade API.

### Vấn đề H
- Mức độ: **Medium**
- File / module liên quan: `app/services/dashboard_service.py`, `app/repositories/vocabulary_repository.py`, `app/repositories/flashcards_import_repository.py`, `app/repositories/deck_tree_query.py`
- Hiện trạng sau refactor: lặp logic tree traversal/visibility scope.
- So với baseline cũ: **có cải thiện nhẹ** nhưng vẫn trùng lặp.
- Vì sao đây vẫn là vấn đề: thay rule access phải sửa nhiều nơi.
- Rủi ro nếu giữ nguyên: lệch rule giữa dashboard/browse/import.
- Hướng xử lý đề xuất: gom về 1 deck scope resolver/repository dùng chung.

### Vấn đề I
- Mức độ: **Medium**
- File / module liên quan: `templates/flashcards/import.html`, `templates/statistics.html`, `templates/vocabulary_browse.html`, `static/js/components/browse_modal.js`
- Hiện trạng sau refactor: tách một số trang nhưng vẫn còn fat template/god-js.
- So với baseline cũ: **cải thiện một phần**.
- Vì sao đây vẫn là vấn đề: khó test/lint/module hóa frontend.
- Rủi ro nếu giữ nguyên: bug UI khó khoanh vùng.
- Hướng xử lý đề xuất: chuẩn hóa page modules và chia nhỏ browse modal theo trách nhiệm.

### Vấn đề J
- Mức độ: **Low**
- File / module liên quan: `app/repositories/vocabulary_repository.py:1`, `app/services/marketplace_query_service.py:1`
- Hiện trạng sau refactor: naming/docstring còn dùng “controller” trong lớp repository/service.
- So với baseline cũ: **có cải thiện file location nhưng naming chưa sạch**.
- Vì sao đây vẫn là vấn đề: tăng cognitive load cho team.
- Rủi ro nếu giữ nguyên: pattern mới dễ lệch.
- Hướng xử lý đề xuất: rename/docstring cleanup sau khi ổn định runtime.

## 5. Những việc refactor vừa rồi làm tốt
- Tách route flashcards theo module domain là đúng hướng, giảm rủi ro so với 1 file monolith cũ.
- Dashboard route đã mỏng hơn và bắt đầu dùng service orchestration (`app/routes/main.py:60-71`).
- Stats layer đã có repository/query tách rõ hơn, giúp khả năng test unit theo data-query tốt hơn.
- Hai template lớn đã chuyển qua static module JS (`dashboard`, `shared_deck_detail`), giảm inline script.
- Bỏ thư mục `app/controllers` là bước đúng để chuẩn hóa package structure (dù còn import legacy cần dọn).

## 6. Những chỗ refactor chưa tới nơi
- Tách file nhưng chưa tách trách nhiệm triệt để: `vocabulary.py` và `flashcards_share_service.py`.
- Đổi vị trí module nhưng boundary vẫn bẩn: service vẫn gọi helper trong route package.
- Đổi tên controller -> repository ở một số khu vực nhưng repository còn ôm business/serialization không thuần query.
- Tách JS khỏi template ở một số page nhưng chưa làm đồng bộ; `browse_modal.js` phình thành god-js mới.
- Có dấu hiệu rename/migrate cơ học chưa hoàn tất: import path cũ còn sót làm vỡ runtime.

## 7. Danh sách ưu tiên refactor tiếp theo

| File / module | Vai trò hiện tại | Vấn đề còn lại | Loại xử lý cần làm | Độ khó | Rủi ro | Mức ưu tiên | Đề xuất phase tiếp theo |
|---|---|---|---|---|---|---|---|
| `app/__init__.py` + `app/cli.py` + `app/services/__init__.py` | App bootstrap / CLI wiring | import `flashcards_share` vỡ | compatibility shim hoặc chuẩn hóa import target | Low | High | P0 | N1 |
| `app/routes/flashcards/__init__.py` | flashcards route root | import legacy `app.controllers.*` | thay import sang service/repository mới | Medium | High | P0 | N1 |
| `app/routes/flashcards/import_export.py` | import/export routes | import `deck_service` không tồn tại + biến undefined | fix module path + fix runtime variable | Medium | High | P0 | N1 |
| `app/services/study_service.py` | study application service | import `user_settings` không tồn tại + route helper coupling | fix import + tách helper trung lập | Medium | High | P0 | N1/N2 |
| `app/routes/vocabulary.py` | browse/study/deck routes | god-route + commit/rollback ở route + bug undefined var | sửa regression trước, sau đó modularize | High | High | P0 | N1/N2 |
| `app/presenters/` | presenter package | thiếu `__init__.py` | chuẩn hóa package boundary | Low | Medium | P1 | N1 |
| `app/services/note_type_service.py` | note-type service | import ngược route helper | tách helper sang domain util | Medium | Medium | P1 | N2 |
| `app/services/flashcard_media_service.py` | media service | import ngược route helper | tách audit/helper trung lập | Medium | Medium | P1 | N2 |
| `app/repositories/flashcards_import_repository.py` | import repository | repository import service | tách validator/policy module, giữ repo thuần query | Medium | Medium | P1 | N2 |
| `app/services/flashcards_share_service.py` | share domain service | god-service mới | chia bounded context + facade ổn định | High | High | P2 | N3 |
| `static/js/components/browse_modal.js` | shared browse modal logic | god-js mới | chia module state/api/render/action | High | Medium | P2 | N3 |
| `templates/flashcards/import.html` + `templates/statistics.html` + `templates/vocabulary_browse.html` | page templates | inline JS lớn | chuyển sang page JS modules | Medium | Medium | P2 | N3 |

## 8. Kế hoạch refactor tiếp theo

### Phase N1
- **Mục tiêu:** ổn định runtime/import trước, bảo đảm app boot được và smoke test cơ bản chạy.
- **Phạm vi:** `app/__init__.py`, `app/cli.py`, `app/routes/flashcards/__init__.py`, `app/routes/flashcards/import_export.py`, `app/services/study_service.py`, `app/routes/vocabulary.py`, `app/presenters/`.
- **File bị ảnh hưởng:** như phạm vi trên.
- **Vì sao nên làm trước:** đang có lỗi critical chặn boot/test; nếu không xử lý trước thì mọi refactor tiếp theo đều rủi ro mù.
- **Definition of Done:**
  - `from app import create_app` pass.
  - `python -m unittest tests.test_stats_overview -q` không fail vì import graph.
  - Không còn import module legacy đã xóa (`app.controllers`, `app.services.deck_service`, `app.services.user_settings`).
  - Không còn các biến undefined đã nêu.
- **Rủi ro cần lưu ý:** shim compatibility có thể tạo technical debt; phải gắn kế hoạch remove trong N2.

### Phase N2
- **Mục tiêu:** làm sạch dependency flow và transaction boundary.
- **Phạm vi:** `app/routes/vocabulary.py`, `app/routes/flashcards/*.py`, `app/services/note_type_service.py`, `app/services/flashcard_media_service.py`, `app/services/study_service.py`, `app/repositories/flashcards_import_repository.py`, `app/repositories/vocabulary_repository.py`.
- **File bị ảnh hưởng:** các route/service/repository chính ở trên.
- **Vì sao để sau:** cần nền import/runtime ổn định trước để tránh refactor chồng lỗi.
- **Definition of Done:**
  - Service không import route helper.
  - Repository không import service.
  - Route không còn `db.session.commit` trực tiếp.
  - `vocabulary.py` giảm đáng kể logic query/orchestration trực tiếp.
- **Rủi ro cần lưu ý:** thay đổi call-chain có thể làm lệch semantics permission/clone overlay nếu không snapshot compare.

### Phase N3
- **Mục tiêu:** xử lý god-file mới và hoàn thiện UI module hóa.
- **Phạm vi:** `app/services/flashcards_share_service.py`, `static/js/components/browse_modal.js`, nhóm fat templates còn lại.
- **File bị ảnh hưởng:** service share, browse modal JS, template import/statistics/vocabulary_browse/shared-note-type/admin.
- **Vì sao chưa nên làm ngay:** phạm vi lớn, đụng business quan trọng; nên làm sau khi N1/N2 đã giảm rủi ro hồi quy.
- **Definition of Done:**
  - `flashcards_share_service.py` tách theo bounded context rõ (publish/install/clone/rating/cutover).
  - `browse_modal.js` chia module state/api/render/actions.
  - Inline JS lớn trong template được thay bằng page modules.
- **Rủi ro cần lưu ý:** regression cao ở clone install, preview template, browse edit flow.

## 9. Test strategy cho vòng refactor tiếp theo
- Cần bảo vệ các use-case:
  - app boot + blueprint registration + CLI import
  - dashboard render + stats APIs
  - browse cards/detail/update/delete
  - shared deck detail/install/rate/preview
  - import parse/estimate/execute
- Cần snapshot/compare:
  - `/api/stats/overview`
  - `/api/stats/today-future`
  - browse card detail/update payload
  - shared deck detail/template preview payload
- Cần smoke test màn:
  - `/dashboard`
  - `/vocabulary/browse`
  - `/flashcards/shared-decks/<id>`
  - `/flashcards/import`
- Khu vực có nguy cơ hồi quy cao nhất:
  - clone overlay flow
  - deck scope/tree traversal
  - permission checks
  - template rendering/preview
- Lưu ý bằng chứng:
  - Hiện chưa có benchmark perf chi tiết; đánh giá perf sâu vẫn là **chưa đủ bằng chứng**.

## 10. Guideline cập nhật cho team
- Rule tiếp tục giữ nguyên:
  - Route mỏng: chỉ HTTP mapping + validation + gọi service.
  - Service là orchestration + transaction boundary chính.
  - Repository/query module không commit transaction.
- Rule cần bổ sung:
  1. Mọi PR migrate phải chạy checklist import graph (`from app import create_app`, unittest smoke tối thiểu).
  2. Cấm import path legacy đã deprecate; thêm grep guard trong CI.
  3. Cấm service import `app.routes.*`.
  4. Cấm repository import `app.services.*`.
  5. Mọi rename module phải có mapping table old->new trong PR note.
- Anti-pattern cấm tái diễn:
  - “chia file cơ học” nhưng giữ nguyên responsibility trộn.
  - để lại alias/import cũ làm app boot fail.
  - dồn toàn bộ logic mới vào 1 service/js file lớn.

## 11. Kết luận hành động
- 5 việc nên làm tiếp ngay:
  1. Sửa toàn bộ import regression chặn boot.
  2. Sửa 2 lỗi runtime undefined variable.
  3. Tạo/chuẩn hóa compatibility interface cho share domain import.
  4. Bổ sung package init cho presenter + dọn import legacy path.
  5. Chạy smoke unittest tối thiểu để khóa trạng thái ổn định N1.
- 5 việc chưa nên làm tiếp:
  1. Tách sâu `flashcards_share_service.py` ngay khi app chưa boot sạch.
  2. Refactor lớn UI browse modal trước khi khóa regression backend.
  3. Tối ưu performance sâu khi chưa có baseline metrics.
  4. Đổi API contract/payload khi chưa có issue riêng.
  5. Rename hàng loạt file khi import graph chưa ổn định.
- Thứ tự thực hiện đề xuất: **N1 -> N2 -> N3**.
- Tiêu chí đánh giá vòng refactor tiếp theo thành công:
  - app boot ổn định, smoke test pass.
  - dependency flow không còn reverse import.
  - route commit trực tiếp bị loại bỏ.
  - các god-file chính giảm độ phình theo mục tiêu phase.
