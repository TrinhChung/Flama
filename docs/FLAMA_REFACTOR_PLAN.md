# Flama Refactor Planning

## 1. Baseline
- **Kết luận baseline vẫn còn đúng:** Các vấn đề nêu trong `FLAMA_ARCHITECTURE_REVIEW.md` vẫn phản ánh đúng hiện trạng: `app/routes/flashcards.py` là god-file, `app/controllers/flashcards_share_controller.py` là domain monolith, `templates/dashboard.html` quá nặng, và layer stats còn phụ thuộc ngược về controller query.
- **Mục tiêu của kế hoạch này:** Đây là **architecture refactor plan**, không phải feature redesign. Mọi phase ưu tiên tách lớp, giảm coupling, và giữ behavior hiện tại ổn định.
- **Nguyên tắc xuyên suốt:** Ưu tiên PR nhỏ theo phase, tránh “đại phẫu” một lần.

## 2. Scope và nguyên tắc không đổi behavior

### 2.1 In-scope
- Tách route quá dày thành route mỏng + application service.
- Tách query khỏi controller cũ để service không phụ thuộc ngược.
- Tách inline JS khỏi template sang static page modules.
- Gom logic access policy và tree query dùng chung.

### 2.2 Out-of-scope (chưa làm ngay)
- Refactor `anki_scheduler.py`.
- Chuyển frontend sang SPA (React/Vue).
- Tối ưu performance sâu (N+1, query micro-optimization) trước khi xong boundary tách lớp.

### 2.3 Non-behavior-change rules
- Không đổi API contract nếu không có issue riêng được phê duyệt.
- Không đổi semantics permission/access hiện tại nếu không có issue riêng.
- Không đổi hành vi HTML/UX hiện tại ngoài các thay đổi kỹ thuật bắt buộc để tách code.

## 3. Kiến trúc đích và rule bắt buộc

### 3.1 Dependency flow chuẩn
**Route ➔ Application Service ➔ Repository / Query Module**

- Service không import ngược lại controller legacy.
- Nếu còn file tên `_controller.py` do lịch sử, xem là **legacy naming**; đích cuối là tách thành repository/query module rõ nghĩa.

### 3.2 Transaction boundary
- `db.session.commit()` chỉ được gọi ở **application service** (hoặc orchestration entrypoint đã được team quy ước rõ).
- Route không tự commit.
- Repository/query module không tự commit (trừ ngoại lệ được review và ghi chú rõ).

### 3.3 Rule cho route/template
- Route không truy cập ORM trực tiếp, trừ lookup nhỏ đã được review và chấp thuận rõ ràng.
- Template chỉ render dữ liệu đã chuẩn hóa; không chứa business rule hoặc UI orchestration phức tạp.

## 4. Danh sách ưu tiên

| File / module | Vấn đề chính | Hướng xử lý | Ưu tiên | Phase |
|---|---|---|---|---|
| `templates/dashboard.html` | Inline JS quá lớn | Tách sang `static/js/pages/dashboard.js` | High | 1 |
| `templates/flashcards/shared_deck_detail.html` | Inline JS + DOM orchestration | Tách sang `static/js/pages/shared_deck_detail.js` | High | 1 |
| `app/routes/main.py` (`dashboard`) | Route chứa tree traversal + counting | Trích xuất `dashboard_service` + view model | High | 1 |
| `app/routes/vocabulary.py` | Wrapper dư thừa | Dọn wrapper, đi thẳng service | Medium | 1 |
| `app/services/stats_overview.py`, `stats_today_future.py` | Service phụ thuộc controller query | Tách query module/repository độc lập | High | 2 |
| `app/controllers/review_event_controller.py`, `card_progress_controller.py` | Sai vai trò naming/boundary | Tách query trước, rename vật lý sau | High | 2 |
| `app/routes/admin.py` | Domain logic nằm trong route | Đẩy qua `admin_service` | Medium | 2 |
| `app/routes/flashcards.py` | God-file route | Tách router theo domain (3A) | Critical | 3A |
| `app/controllers/flashcards_share_controller.py` | God-file domain | Tách bounded context (3B) | Critical | 3B |
| Access policy + tree query dùng chung | Rule lặp rải rác | Gom `DeckAccessPolicyService` + `DeckTreeQueryModule` (3C) | High | 3C |

## 5. Kế hoạch theo phase

### Phase 1 — Ổn định nền tảng dễ triển khai
1. Tách JS khỏi `dashboard.html`.
2. Tách JS khỏi `shared_deck_detail.html`.
3. Tách `main.dashboard()` sang `dashboard_service`.
4. Dọn wrapper ở `vocabulary.py`.

**Definition of Done (Phase 1)**
- Không còn inline `<script>` dài > 30 dòng trong 2 template mục tiêu.
- Event handler chính nằm trong `static/js/pages/*`.
- Không còn Jinja logic cắm sâu trong JS function.
- `main.dashboard()` không còn BFS/DFS/business counting trực tiếp.
- Service trả về view model rõ ràng, HTML render không đổi.
- Query count không tăng bất thường so với trước refactor.
- Smoke test các action chính (modal/action flows) pass.

### Phase 2 — Nắn lại layer và dependency
5. Tách query khỏi `review_event_controller.py` / `card_progress_controller.py` thành query module/repository mới.
6. Chuyển `stats_overview.py` và `stats_today_future.py` sang dùng module query mới.
7. Tách admin domain logic khỏi route.

**Quyết định rename (Phase 2)**
- Ưu tiên chiến lược ít rủi ro: **tách boundary trước, rename vật lý file sau**.
- Chỉ rename `_controller.py` ➔ `_repository.py` khi import graph đã ổn định và dễ review.

**Definition of Done (Phase 2)**
- Không còn service nào import query từ controller legacy.
- Payload stats JSON trước/sau tương đương (snapshot/compare).
- Không phát sinh transaction commit ngoài application service.

### Phase 3A — Tách route flashcards theo domain
8. Tách `app/routes/flashcards.py` thành các module domain route, giữ behavior cũ.

**Definition of Done (Phase 3A)**
- Route tree rõ ràng theo domain (note/deck/review/share/import...).
- Không đổi API contract và permission semantics.
- Regression test route chính pass.

### Phase 3B — Tách share controller theo bounded context
9. Tách `flashcards_share_controller.py` thành các module clone/install/publish/rating.

**Definition of Done (Phase 3B)**
- Mỗi module có trách nhiệm đơn nhất.
- Flow clone/install/publish giữ nguyên behavior.
- Không còn file domain monolith > 500 dòng cho một use-case trộn lẫn.

### Phase 3C — Gom rule dùng chung
10. Gom rule access và tree query dùng chung: `DeckAccessPolicyService`, `DeckTreeQueryModule`.

**Definition of Done (Phase 3C)**
- Không còn copy rule access ở nhiều route/service.
- Các luồng gọi đúng dependency flow chuẩn.

## 6. Test strategy theo phase

- **Phase 1:** UI smoke test cho dashboard và shared deck detail (DOM events, modal/action flows).
- **Phase 2:** Snapshot/compare payload stats JSON (overview/today/future), kiểm tra không lệch số liệu.
- **Phase 3:** Regression theo use-case chính:
  - create/edit note
  - review/study
  - share public/private
  - install/clone deck
  - import flow

## 7. Guideline áp dụng ngay cho team

- PR nhỏ theo domain/phase; không tạo PR “Big Architecture Refactor”.
- Mỗi PR phải ghi rõ:
  - boundary nào được tách,
  - behavior nào được giữ nguyên,
  - rủi ro và checklist test tương ứng phase.
- Nếu cần ngoại lệ với rule (ORM trong route, commit ngoài service...), phải có note review và lý do cụ thể trong PR.

## 8. Kết luận hành động

**Làm ngay (theo thứ tự):**
1. Phase 1 đầy đủ (dashboard template, shared deck detail template, dashboard service, vocabulary cleanup).
2. Phase 2 đầy đủ (stats dependency + admin boundary).
3. Phase 3 theo nhịp 3A ➔ 3B ➔ 3C, không gộp một PR.

**Tiêu chí thành công cuối kỳ:**
- Dependency flow nhất quán: Route ➔ Application Service ➔ Repository/Query Module.
- Không còn phụ thuộc ngược từ service sang controller legacy.
- God-file được chia nhỏ theo domain với rủi ro hồi quy được kiểm soát bằng test strategy theo phase.
