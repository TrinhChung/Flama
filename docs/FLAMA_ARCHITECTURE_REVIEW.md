# Flama Architecture Review

## 1. Tổng quan hiện trạng

### Kiến trúc hiện tại đang được tổ chức ra sao
- Flama đang tổ chức theo hướng Flask Blueprint, với 5 route modules chính: `main`, `auth`, `admin`, `vocabulary`, `flashcards`.
- Nhóm `app/controllers` hiện đóng vai trò **hỗn hợp**: có file đóng vai trò domain helper/repository (query DB), có file đóng vai trò business logic, có file chỉ utility.
- Nhóm `app/services` cũng đang là **hỗn hợp**: một số file là business service đúng nghĩa (`anki_scheduler`, `flashcard_renderer`, `flashcard_import`), nhưng một số service lại phụ thuộc ngược vào controller query (`stats_overview`, `stats_today_future`).
- Nhóm templates có 2 dạng:
  - Dạng đúng vai trò view (các partial/component nhỏ, form components).
  - Dạng “fat template” chứa JS dài + logic điều phối API/state ngay trong file HTML (đặc biệt nhóm flashcards marketplace/share và dashboard/index).

### Các nhóm file chính theo phạm vi review

#### Route
- `app/routes/main.py`
- `app/routes/auth.py`
- `app/routes/admin.py`
- `app/routes/vocabulary.py`
- `app/routes/flashcards.py`

#### Controller
- `app/controllers/vocabulary_controller.py`
- `app/controllers/flashcards_share_controller.py`
- `app/controllers/flashcards_marketplace_controller.py`
- `app/controllers/flashcards_import_controller.py`
- `app/controllers/review_event_controller.py`
- `app/controllers/card_progress_controller.py`
- `app/controllers/study_controller.py`
- `app/controllers/deck_controller.py`
- `app/controllers/flashcards_note_controller.py`

#### Service
- `app/services/anki_scheduler.py`
- `app/services/flashcard_renderer.py`
- `app/services/flashcard_import.py`
- `app/services/stats_overview.py`
- `app/services/stats_today_future.py`
- `app/services/user_roles.py`
- `app/services/user_management_schema.py`

#### Template
- Trang tổng hợp lớn: `templates/index.html`, `templates/dashboard.html`, `templates/statistics.html`, `templates/vocabulary_browse.html`, `templates/vocabulary_study.html`
- Flashcards pages: `templates/flashcards/*.html` (nổi bật: `import.html`, `shared_deck_detail.html`, `shared_note_type_detail.html`, `note_type_fields.html`)
- Admin pages: `templates/admin/users.html`, `templates/admin/permission_assignment.html`
- Components: `templates/components/**/*.html`

### Nhận xét tổng quát
- **Điểm ổn:**
  - Đã có phân tách thư mục route/controller/service/template rõ theo tên thư mục.
  - Nhiều domain logic cốt lõi đã được tách khỏi route (scheduler, renderer, import pipeline, một phần marketplace/share).
- **Điểm lệch:**
  - Một số route vẫn quá dày và trực tiếp thao tác DB/business (`flashcards.py`, `main.py`, `admin.py`).
  - “Controller” và “Service” đang chồng vai trò (đặc biệt query/aggregation nằm ở controller nhưng service gọi ngược controller).
  - Một số template đang chứa logic UI-state + gọi API phức tạp ngay trong HTML, khó bảo trì/khó test.

---

## 2. Sơ đồ trách nhiệm hiện tại

### Trách nhiệm thực tế theo tầng

- **Route (thực tế):**
  - Vừa map URL + parse request/response.
  - Vừa thực hiện query DB trực tiếp và transaction (`db.session.add/commit/query`).
  - Vừa chứa helper/domain logic nội bộ (đặt prefix `_...`) với số lượng lớn, nhất là `app/routes/flashcards.py`.

- **Controller (thực tế):**
  - Không thuần “HTTP controller”.
  - Nhiều file controller thực chất là **domain + data access layer** (query ORM, serialize payload, validate business rule).
  - Có controller đóng vai trò tốt (ví dụ nhóm helper nhỏ), nhưng naming dễ gây kỳ vọng sai cho dev mới.

- **Service (thực tế):**
  - Có business logic đúng nghĩa ở một số module.
  - Nhưng nhóm stats service lại phụ thuộc vào controller query -> tạo dependency direction chưa sạch.

- **Template (thực tế):**
  - Nhiều template render thuần HTML/Jinja đúng vai trò.
  - Một số template chứa script dài xử lý state, API orchestration, transform dữ liệu frontend-side nhiều bước.

### Trách nhiệm chồng chéo đang thấy rõ
- **Route ↔ Controller:** cùng xử lý validation/serialization/business rule trong cùng domain flashcards.
- **Controller ↔ Service:** controller chứa query/aggregation; service gọi controller như data source (inversion của tầng).
- **Route ↔ Service:** cùng chạm ORM trực tiếp (service chưa là điểm tập trung duy nhất cho nghiệp vụ).
- **Template ↔ Backend normalization:** nhiều trang phụ thuộc dữ liệu chưa được chuẩn hóa triệt để từ backend, dẫn tới JS xử lý nhiều ở template.

---

## 3. Các vấn đề phát hiện

### Vấn đề 1: `flashcards` route đang ôm quá nhiều trách nhiệm
- **Mức độ:** High
- **Khu vực ảnh hưởng:** Flashcards API + pages + marketplace/share/import
- **File liên quan:** `app/routes/flashcards.py`
- **Hiện trạng:** File route rất lớn (~2.8k lines, ~132 funcs), gồm cả routing, helper nghiệp vụ, validation, serialization, query DB, transaction.
- **Vì sao đây là vấn đề:** Route không còn là tầng mỏng; khó đọc flow, khó test unit theo chức năng nhỏ.
- **Rủi ro nếu giữ nguyên:** tăng regression khi sửa nhỏ; onboarding chậm; conflict merge cao.
- **Hướng chỉnh sửa đề xuất:** tách theo use-case module (`note_type`, `note`, `template`, `marketplace`, `install/share`, `import`), route giữ nhiệm vụ HTTP mapping + gọi service/controller coordinator.

### Vấn đề 2: `main.dashboard` chứa business/query tree + thống kê sâu
- **Mức độ:** High
- **Khu vực ảnh hưởng:** Dashboard load performance + maintainability
- **File liên quan:** `app/routes/main.py`
- **Hiện trạng:** Route xây dựng toàn bộ deck visibility, traversal cây deck, tính card counts, clone overlay counts, và build node tree.
- **Vì sao đây là vấn đề:** logic nghiệp vụ nằm trực tiếp trong endpoint làm route khó test và khó tái sử dụng cho API khác.
- **Rủi ro nếu giữ nguyên:** mỗi thay đổi rule đếm card/deck có thể làm vỡ dashboard; khó mở rộng thống kê.
- **Hướng chỉnh sửa đề xuất:** tách `dashboard_service` để gom query + aggregation; route chỉ nhận output view model.

### Vấn đề 3: Route admin tự quản lý business + persistence không qua service/controller domain
- **Mức độ:** Medium
- **Khu vực ảnh hưởng:** User/permission management
- **File liên quan:** `app/routes/admin.py`
- **Hiện trạng:** parse payload, query user, assign role, append audit log, commit transaction đều ở route.
- **Vì sao đây là vấn đề:** thiếu lớp nghiệp vụ trung gian; rule permission dễ trùng lặp nếu sau này mở API/admin CLI.
- **Rủi ro nếu giữ nguyên:** khó tái sử dụng và khó đảm bảo consistency policy.
- **Hướng chỉnh sửa đề xuất:** tạo `admin_user_service` + `admin_permission_service`, route giữ validation HTTP cơ bản + mapping response.

### Vấn đề 4: Layer direction chưa sạch (service phụ thuộc controller)
- **Mức độ:** High
- **Khu vực ảnh hưởng:** Stats domain
- **File liên quan:** `app/services/stats_overview.py`, `app/services/stats_today_future.py`, `app/controllers/review_event_controller.py`, `app/controllers/card_progress_controller.py`
- **Hiện trạng:** service gọi trực tiếp các hàm query trong controller.
- **Vì sao đây là vấn đề:** vi phạm chiều phụ thuộc kiến trúc thông thường (controller thường là tầng ngoài gọi service), làm naming gây nhiễu.
- **Rủi ro nếu giữ nguyên:** khó xác định boundary; test doubles/phân lớp lâu dài khó chuẩn hóa.
- **Hướng chỉnh sửa đề xuất:** đổi controller query thành `repository`/`query_service` rõ ràng hoặc chuyển toàn bộ query vào service stats.

### Vấn đề 5: Wrapper pass-through quá nhiều ở route `vocabulary`
- **Mức độ:** Medium
- **Khu vực ảnh hưởng:** Readability, traceability
- **File liên quan:** `app/routes/vocabulary.py`, `app/controllers/vocabulary_controller.py`
- **Hiện trạng:** nhiều hàm `_x()` ở route chỉ forward sang controller tương ứng.
- **Vì sao đây là vấn đề:** tăng độ dài file, khó theo dõi call chain, không tăng giá trị.
- **Rủi ro nếu giữ nguyên:** dev dễ sửa nhầm điểm; duplication bề mặt API nội bộ.
- **Hướng chỉnh sửa đề xuất:** route gọi trực tiếp controller/service public API; loại wrapper không thêm logic.

### Vấn đề 6: Template “fat” chứa JS điều phối logic nghiệp vụ UI quá dày
- **Mức độ:** High
- **Khu vực ảnh hưởng:** Frontend maintainability/testability
- **File liên quan:** `templates/flashcards/shared_deck_detail.html`, `templates/flashcards/shared_note_type_detail.html`, `templates/flashcards/import.html`, `templates/dashboard.html`, `templates/index.html`
- **Hiện trạng:** nhiều script inline dài (request API, transform data, state machine UI, render logic condition).
- **Vì sao đây là vấn đề:** HTML template không còn thuần render; khó lint/test module JS; khó tái sử dụng.
- **Rủi ro nếu giữ nguyên:** bug UI khó khoanh vùng; merge conflict cao; khó tách frontend layer sau này.
- **Hướng chỉnh sửa đề xuất:** chuyển JS sang `static/js/modules/*` theo page-domain; template chỉ bind data/bootstrap config nhỏ.

### Vấn đề 7: Trùng lặp logic visibility/access deck giữa nhiều nơi
- **Mức độ:** Medium
- **Khu vực ảnh hưởng:** dashboard, browse, import, share/install flows
- **File liên quan:** `app/routes/main.py`, `app/controllers/flashcards_import_controller.py`, `app/controllers/vocabulary_controller.py`, `app/controllers/flashcards_share_controller.py`
- **Hiện trạng:** cùng pattern lấy installed roots -> BFS/collect subtree -> query deck list xuất hiện nhiều module.
- **Vì sao đây là vấn đề:** rule access thay đổi sẽ cần sửa nhiều nơi.
- **Rủi ro nếu giữ nguyên:** bug không đồng nhất quyền nhìn thấy deck.
- **Hướng chỉnh sửa đề xuất:** gom thành `deck_access_service` / `deck_scope_resolver` dùng chung.

### Vấn đề 8: Nhiều file tên gọi chưa phản ánh đúng vai trò
- **Mức độ:** Low
- **Khu vực ảnh hưởng:** khả năng hiểu hệ thống
- **File liên quan:** `app/controllers/*` (đặc biệt review/card_progress/vocabulary/share controllers)
- **Hiện trạng:** nhiều controller thực tế làm query/repository/business utility hơn là controller HTTP.
- **Vì sao đây là vấn đề:** naming mismatch tạo cognitive load.
- **Rủi ro nếu giữ nguyên:** code mới tiếp tục đi lệch pattern.
- **Hướng chỉnh sửa đề xuất:** chuẩn hóa naming theo chức năng thật (`*_repository.py`, `*_domain_service.py`, `*_serializer.py`).

### Vấn đề 9: Có route gọi model/DB quá sâu (đúng tiêu chí cần cảnh báo)
- **Mức độ:** High
- **Khu vực ảnh hưởng:** Route layer toàn cục
- **File liên quan:** `app/routes/flashcards.py`, `app/routes/main.py`, `app/routes/admin.py`, `app/routes/auth.py`, `app/routes/vocabulary.py`
- **Hiện trạng:** route import model trực tiếp và tự `.query`, `db.session`, transaction.
- **Vì sao đây là vấn đề:** làm route khó giữ role mỏng.
- **Rủi ro nếu giữ nguyên:** route trở thành business hub; test integration nặng mới bao phủ được.
- **Hướng chỉnh sửa đề xuất:** route chỉ gọi service façade, DB access tập trung ở repository/service.

### Vấn đề 10: Một số nhận định cần thêm bằng chứng trước khi kết luận sâu
- **Mức độ:** Low
- **Khu vực ảnh hưởng:** hiệu năng/query tuning, kiến trúc FE bundling
- **File liên quan:** toàn hệ thống
- **Hiện trạng:** chưa benchmark hiệu năng và chưa có test coverage map chính thức trong phạm vi review này.
- **Vì sao đây là vấn đề:** thiếu số liệu định lượng để ưu tiên kỹ thuật tối ưu sâu.
- **Rủi ro nếu giữ nguyên:** có thể ưu tiên sai nếu refactor lớn mà không đo trước/sau.
- **Hướng chỉnh sửa đề xuất:** bổ sung baseline metrics (response time endpoint lớn, query count, template payload size) trước phase refactor lớn.

---

## 4. Đánh giá theo từng tầng

### 4.1 Route

**Những điểm làm đúng**
- Có phân tách blueprint theo domain rõ (`main`, `auth`, `admin`, `vocabulary`, `flashcards`).
- Một số endpoint stats trong `main.py` đã gọi service (`build_stats_overview`, `build_today_future_stats`) thay vì tự xử lý sâu.

**Những điểm làm sai vai trò**
- Nhiều route tự làm query/transaction/domain rule (đặc biệt `flashcards.py`, `main.py`, `admin.py`).
- `vocabulary.py` có nhiều wrapper trung gian không cần thiết làm route dài.

**File tiêu biểu cần chỉnh**
- `app/routes/flashcards.py`
- `app/routes/main.py`
- `app/routes/admin.py`
- `app/routes/vocabulary.py`

### 4.2 Controller

**Những điểm làm đúng**
- Một số controller gom được domain helper tái sử dụng tốt (`study_controller`, một phần `deck_controller`).
- Có các function serialize/normalize giúp giảm trùng code ở route.

**Những điểm làm sai vai trò**
- Naming “controller” nhưng phần lớn không phải HTTP controller; chứa query/data access/business rules.
- Có controller rất lớn (`flashcards_share_controller.py`) trở thành “mini service + mini repository + serializer” trong cùng file.

**File tiêu biểu cần chỉnh**
- `app/controllers/flashcards_share_controller.py`
- `app/controllers/vocabulary_controller.py`
- `app/controllers/review_event_controller.py`
- `app/controllers/card_progress_controller.py`

### 4.3 Service

**Những điểm làm đúng**
- `anki_scheduler`, `flashcard_renderer`, `flashcard_import` thể hiện business capability tương đối tách biệt.
- Service stats đóng vai trò orchestrator tương đối rõ theo use-case.

**Những điểm làm sai vai trò**
- Service stats phụ thuộc controller query -> tầng service chưa độc lập dữ liệu.
- Biên giữa service và controller chưa thống nhất: cùng domain nhưng chia responsibilities không nhất quán.

**File tiêu biểu cần chỉnh**
- `app/services/stats_overview.py`
- `app/services/stats_today_future.py`
- nhóm controller query liên quan stats để đổi tên/tái cấu trúc

### 4.4 Template

**Những điểm làm đúng**
- Có component hóa template (buttons/forms/navbar/footer/modals) khá tốt.
- Nhiều page vẫn chủ yếu render data từ backend.

**Những điểm làm sai vai trò**
- Nhiều trang chứa JS inline dài và logic điều phối API/state ở trong template.
- Một số page chứa cả markup + style + script lớn trong cùng file, coupling cao.

**File tiêu biểu cần chỉnh**
- `templates/flashcards/shared_deck_detail.html`
- `templates/flashcards/shared_note_type_detail.html`
- `templates/flashcards/import.html`
- `templates/dashboard.html`
- `templates/index.html`

---

## 5. Danh sách file cần ưu tiên chỉnh sửa

| File | Vai trò hiện tại | Vấn đề | Vai trò nên có | Mức ưu tiên | Gợi ý hành động |
|---|---|---|---|---|---|
| `app/routes/flashcards.py` | Route + business + DB + serializer + helper | God-file, chồng trách nhiệm | Route mỏng theo module domain | P0 | Tách thành nhiều route module + gọi service/controller nhỏ |
| `app/routes/main.py` | Route + dashboard aggregation | Business/query nặng trong endpoint | Route gọi `dashboard_service` | P0 | Tạo service trả `DashboardViewModel` |
| `app/routes/admin.py` | Route + admin domain logic + transaction | Rule phân quyền khó tái sử dụng | Route mỏng + admin services | P1 | Tách `admin_user_service`, `admin_permission_service` |
| `app/controllers/flashcards_share_controller.py` | Domain monolith cho share/marketplace/clone | File lớn, trộn query + rule + mapping | Domain services + repositories tách nhỏ | P0 | Chia theo bounded context: publish/install/clone/rating |
| `app/controllers/vocabulary_controller.py` | Data shaping + query helpers | Chưa rõ là service hay repository | Chia thành `vocabulary_query_service` + `presenter` | P1 | Tách function theo read-model vs rule |
| `app/services/stats_overview.py` | Stats orchestrator | phụ thuộc controller query | Service + repository dependency rõ | P1 | Đổi controller query -> repository interface/module |
| `app/services/stats_today_future.py` | Stats orchestrator | phụ thuộc controller query | Service thuần nghiệp vụ | P1 | Đồng bộ kiến trúc với `stats_overview` |
| `templates/flashcards/shared_deck_detail.html` | View + inline style + JS app logic | Fat template, khó test | View + static JS module | P0 | Trích script sang `static/js/pages/shared_deck_detail.js` |
| `templates/flashcards/import.html` | View + JS flow import dài | Logic FE khó bảo trì | View + module JS riêng | P1 | Trích state machine/import actions ra JS module |
| `templates/dashboard.html` | View + macro + modal + script lớn | Coupling UI cao | View thuần + component + JS module | P1 | Tách modal/components và handler JS riêng |

---

## 6. Kiến trúc mục tiêu sau chỉnh sửa

### Mô tả kiến trúc mong muốn
- **Route layer:** chỉ parse request, auth/permission HTTP-level, gọi service facade, map response/render.
- **Application service layer:** điều phối use-case, transaction boundary, gọi domain service/repository.
- **Domain service layer:** business rules thuần, không phụ thuộc Flask request context.
- **Repository/query layer:** ORM query tập trung, trả entity hoặc read-model rõ ràng.
- **Presenter/serializer layer:** chuẩn hóa dữ liệu trả API/template.
- **Template layer:** hiển thị + binding config nhẹ; JS logic đặt ở `static/js` module theo trang.

### Nguyên tắc phân vai route/controller/service/template
- Route không query DB trực tiếp (trừ health/simple read cực nhỏ đã được team chấp thuận).
- Controller (nếu giữ tên) phải định nghĩa rõ: hoặc là HTTP-controller, hoặc rename thành service/repository tương ứng.
- Service là nơi duy nhất chứa nghiệp vụ cốt lõi và orchestration use-case.
- Template không chứa business rule; chỉ render dữ liệu đã chuẩn hóa.
- JS business/state phức tạp không để inline trong template.

### Quy tắc để tránh tái diễn lỗi phân tầng
1. Mỗi endpoint mới phải chỉ rõ use-case service owner trước khi viết code.
2. Cấm merge route > 300-400 dòng nếu không có lý do đặc biệt + review architecture.
3. Query ORM phải nằm ở repository/query module, không phát tán.
4. Chuẩn hóa naming theo vai trò thật (`route`, `service`, `repository`, `presenter`).
5. Với template, script inline chỉ cho hành vi rất nhỏ; còn lại phải tách file JS.

---

## 7. Kế hoạch chỉnh sửa theo giai đoạn

### Phase 1: ít rủi ro, hiệu quả cao
- **Mục tiêu:** giảm nhanh độ phình route/template, tăng readability.
- **Phạm vi:**
  - Loại wrapper pass-through ở `vocabulary.py`.
  - Trích JS inline lớn khỏi template ưu tiên cao (`shared_deck_detail`, `dashboard`).
  - Chuẩn hóa naming/docstring cho module controller/service hiện có.
- **File bị ảnh hưởng:**
  - `app/routes/vocabulary.py`
  - `templates/flashcards/shared_deck_detail.html`, `templates/dashboard.html`
  - `static/js/pages/*` (mới)
  - docs guideline nội bộ
- **Kết quả mong đợi:** call-chain ngắn hơn, template sạch hơn, dễ review code.
- **Rủi ro cần lưu ý:** mismatch selector/event khi tách JS; cần smoke test UI theo page.

### Phase 2: chỉnh sửa trung bình
- **Mục tiêu:** làm sạch dependency direction và gom query logic.
- **Phạm vi:**
  - Refactor stats: service không gọi controller.
  - Tạo query/repository module cho review/card_progress/deck access.
  - Tách admin domain logic khỏi route.
- **File bị ảnh hưởng:**
  - `app/services/stats_overview.py`, `app/services/stats_today_future.py`
  - `app/controllers/review_event_controller.py`, `app/controllers/card_progress_controller.py`
  - `app/routes/admin.py`
  - các module repository mới
- **Kết quả mong đợi:** dependency rõ, dễ unit-test service bằng fake repository.
- **Rủi ro cần lưu ý:** regression query logic thống kê; cần snapshot test payload stats.

### Phase 3: chỉnh sửa lớn / đụng nhiều file
- **Mục tiêu:** giải thể god-files và tái cấu trúc theo bounded contexts.
- **Phạm vi:**
  - Tách `app/routes/flashcards.py` thành nhiều module route theo use-case.
  - Tách `flashcards_share_controller.py` thành nhiều service/repository/presenter file.
  - Tạo `dashboard_service` cho `main.dashboard`.
- **File bị ảnh hưởng:**
  - `app/routes/flashcards.py`, `app/routes/main.py`
  - `app/controllers/flashcards_share_controller.py`
  - service/repository mới cho flashcards/share/dashboard
- **Kết quả mong đợi:** cấu trúc mở rộng tốt, giảm coupling, giảm chi phí thay đổi tính năng mới.
- **Rủi ro cần lưu ý:** refactor lớn dễ phá API behavior; bắt buộc có regression suite + migration plan theo PR nhỏ tuần tự.

---

## 8. Đề xuất coding guideline cho team

1. Route không chứa business logic và không thao tác ORM trực tiếp.
2. Controller chỉ điều phối HTTP (nếu dùng khái niệm controller kiểu web MVC).
3. Service là nơi tập trung nghiệp vụ và transaction boundary.
4. Query DB phải đi qua repository/query-service chuyên trách.
5. Template chỉ render; không xử lý rule nghiệp vụ.
6. Dữ liệu render template phải được backend chuẩn hóa trước.
7. Không duplicate business rule giữa route/controller/service/template.
8. Mọi file >500 dòng cần có kế hoạch tách module.
9. Hàm utility dùng chung phải nằm module dùng chung (không copy/paste giữa route files).
10. Khi thêm feature mới, bắt buộc cập nhật sơ đồ responsibility trong docs kiến trúc.

---

## 9. Kết luận

### 5 điểm quan trọng nhất
1. `app/routes/flashcards.py` là điểm nghẽn kiến trúc lớn nhất, cần ưu tiên tách.
2. `main.dashboard` và `admin` routes đang mang quá nhiều domain logic.
3. Biên controller/service đang chồng chéo; đặc biệt stats service phụ thuộc ngược controller.
4. Nhiều template đang là “fat template”, cần tách JS để giảm coupling UI.
5. Có trùng lặp logic deck access/visibility ở nhiều module, cần gom về một nơi.

### Thứ tự ưu tiên nên làm trước
1. **P0:** giảm độ phình route/template (flashcards route decomposition plan + tách JS inline nặng).
2. **P1:** làm sạch dependency stats và tách admin domain service.
3. **P2:** chuẩn hóa naming và hoàn tất tách repository/service theo domain.
4. **P3:** hoàn thiện guideline + checklist review kiến trúc để ngăn tái phát.
