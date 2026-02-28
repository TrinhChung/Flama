# Flama Refactor Planning

## 1. Baseline
- **Tài liệu review cũ đã kết luận những gì:** Hệ thống đang gặp vấn đề trầm trọng về phân bổ trách nhiệm (responsibilities) giữa các layer. Route làm luôn việc của Controller/Service/Repository, Controller lại chứa DB logic khổng lồ, Service phụ thuộc ngược lại Controller. Template thì phình to với hàng ngàn dòng code UI và state machine inline.
- **Kết luận nào vẫn còn đúng:** Tất cả các kết luận trong tài liệu baseline (`FLAMA_ARCHITECTURE_REVIEW.md`) đều đang phản ánh chính xác 100% tình trạng hiện tại của codebase. `app/routes/flashcards.py` vẫn là một god-file ~2854 dòng. `app/controllers/flashcards_share_controller.py` vẫn ngốn ~2065 dòng xử lý logic chia sẻ/clone deck phức tạp. `templates/dashboard.html` vẫn dài ~1759 dòng và gánh vác cả frontend routing/state. Layer direction ở `stats_overview.py` vẫn bị lộn ngược (vẫn đang import query từ `review_event_controller`).
- **Kết luận nào đã cũ hoặc cần cập nhật:** Không có kết luận nào sai hoàn toàn, toàn bộ baseline đáng tin cậy để lập kế hoạch.
- **Những thay đổi đáng chú ý của code hiện tại so với tài liệu cũ:** Codebase chưa được refactor theo tài liệu cũ, mọi vấn đề được nêu vẫn giữ nguyên trạng.

## 2. Những vấn đề còn tồn tại cần xử lý

- **Mức độ:** Critical
- **File liên quan:** `app/routes/flashcards.py`
- **Tình trạng hiện tại:** God-file (gần 3000 dòng), chứa hơn 130 functions (kể cả private helpers), ôm việc query DB, transaction, validation, và routing trong cùng một nơi.
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao cần xử lý:** Là file "nóng" nhất khi sửa code flashcard, dễ gây merge conflict và hồi quy (regression) lỗi nọ xọ lỗi kia. Test unit từng phần rất vất vả.
- **Hướng xử lý đề xuất:** Tách thành nhiều files `app/routes/flashcards/*.py` chuyên biệt theo module (vd: `note.py`, `deck.py`, `marketplace.py`). Phần DB chuyển sang service/repository.

- **Mức độ:** High
- **File liên quan:** `app/controllers/flashcards_share_controller.py`
- **Tình trạng hiện tại:** Domain monolith (hơn 2000 dòng), tự xử module sharing, clone scopes, permission checker, apply marketplace payloads.
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao cần xử lý bây giờ:** Core nghiệp vụ quá lớn lại dồn cục vào khái niệm "controller", vi phạm quy tắc Single Responsibility.
- **Hướng xử lý đề xuất:** Chẻ nhỏ thành các domain services chuyên sâu: `clone_service.py`, `marketplace_publication_service.py`, `deck_install_service.py`.

- **Mức độ:** High
- **File liên quan:** `app/routes/main.py` (cụ thể là hàm `dashboard()`)
- **Tình trạng hiện tại:** Route tự thực thi thuật toán duyệt cây Tree (DFS/BFS) để gom nhóm thẻ học, tính due count, learn count.
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao cần xử lý bây giờ:** Bất kỳ thay đổi logic đếm thẻ nào cũng đụng đến file main, biến file định tuyến thành business logic container.
- **Hướng xử lý đề xuất:** Tách logic tree traversal sang `app/services/dashboard_service.py`. Route chỉ nhận về `DashboardViewModel`.

- **Mức độ:** High
- **File liên quan:** `app/services/stats_overview.py`, `app/services/stats_today_future.py`
- **Tình trạng hiện tại:** Tầng Service đang import và gọi thuần các hàm query ở tầng Controller (Dependency Inversion lỗi).
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao cần xử lý bây giờ:** Layering bị lỗi ngược chiều gây hiểu lầm cho người mới vào team. 
- **Hướng xử lý đề xuất:** Đổi/Tách nhóm query trong controller thành `ReviewRepository` hoặc chuyển thẳng vào Service tùy quy mô.

- **Mức độ:** Medium
- **File liên quan:** `templates/dashboard.html`, `templates/flashcards/shared_deck_detail.html`
- **Tình trạng hiện tại:** Fat template, thẻ `<script>` dài hàng trăm dòng điều hướng state của UI FE, DOM manipulation thủ công nhúng thẳng cùng file HTML.
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao cần xử lý bây giờ:** Gây khó khăn cho việc bảo trì UI FE, không thể lint hay test frontend module độc lập. Độc lập HTML và JS cực dễ làm và mang lại lợi ích cao ngay.
- **Hướng xử lý đề xuất:** Chuyển inline Javascript thành các file module static (`static/js/pages/dashboard.js`).

- **Mức độ:** Low
- **File liên quan:** `app/routes/admin.py`, `app/routes/vocabulary.py`
- **Tình trạng hiện tại:** `admin.py` thao tác DB trực tiếp, phân quyền trực tiếp. `vocabulary.py` có hàm wrapper thừa thãi.
- **Tính chất:** Đã có trong Docs cũ.
- **Tại sao chưa nên xử lý ngay:** Rủi ro và blocker đối với product flow thấp. Không chạm tới thay đổi business logic lõi và luồng ôn tập của người dùng.
- **Hướng xử lý đề xuất:** Gom lại sau ở cuối phase refactor.

## 3. Danh sách ưu tiên refactor

| File / module | Vai trò hiện tại | Vấn đề chính | Loại xử lý cần làm | Độ khó | Rủi ro | Ưu tiên | Phase |
|---|---|---|---|---|---|---|---|
| `app/routes/main.py` (dashboard) | Route + Tree Builder | Nhúng Business/Algo vào route | Extract `dashboard_service` | Vừa | Vừa | High | 1 |
| Templates (`dashboard.html`, `shared_deck_detail.html`) | Template + JS App | Fat template, JS inline | Trích xuất JS ra static `*.js` | Thấp | Vừa | High | 1 |
| `app/routes/vocabulary.py` | Route + redundant wrapper | Dư thừa code trung gian | Xóa wrapper, gọi thẳng service | Thấp | Thấp | Low | 1 |
| `app/services/stats_overview.py` & controllers | Orchestrator + ngược layer | Service phụ thuộc Controller | Chuyển query sang Repository | Vừa | Thấp | Medium | 2 |
| `app/routes/admin.py` | Route + Persistence | Xử lý domain trong route | Đẩy vào `admin_service` | Thấp | Thấp | Low | 2 |
| `app/routes/flashcards.py` | Route + DB + Validation | God-file, ôm mọi thứ | Decomposition (Tách route files) | Cao | Cao | Critical | 3 |
| `flashcards_share_controller.py` | Domain Monolith | God-file, gộp nhiều core logic | Bounded Context Split | Cao | Cao | High | 3 |

## 4. Kế hoạch refactor theo phase

### Phase 1: Tháo gỡ các cản trở dễ xử lý (Low-hanging fruits)
- **Mục tiêu:** Giảm bớt các tệp UI phình to, giải phóng route `main` khỏi logic dashboard quá nặng, làm gọn `vocabulary` type route. Tăng cường testability ngay từ bề ngoài.
- **Các file / module xử lý:** 
  - `templates/dashboard.html`
  - `templates/flashcards/shared_deck_detail.html`
  - `app/routes/main.py`
  - `app/routes/vocabulary.py`
- **Vì sao nên làm trước:** Việc trích xuất JS không chạm tới DB nên an toàn. `main.dashboard` được tách ra sẽ tạo module mẫu đầu tiên hiển thị rõ ranh giới Route gọi Service.
- **Kết quả mong đợi:** JS nằm trên static file dễ lint. Route dashboard mỏng lại, chỉ còn `< 30 dòng`. Wrapper ảo ở `vocabulary` biến mất.
- **Rủi ro:** Vỡ UI nhè nhẹ nếu DOM selector bị sai lúc di chuyển script.
- **Điều kiện để merge:** FE vẫn hoạt động bình thường trên các trình duyệt, các modal dashboard mở lên và clone/move deck không bị kẹt.

### Phase 2: Nắn lại xương sống (Layer Dependencies)
- **Mục tiêu:** Cắt đứt các sự phụ thuộc sai chiều (Service gọi ngược lại Controller), tách lập nghiệp vụ đơn giản khỏi admin route.
- **Các file / module xử lý:**
  - `app/services/stats_overview.py` & `app/services/stats_today_future.py`
  - `app/controllers/review_event_controller.py`, `app/controllers/card_progress_controller.py`
  - `app/routes/admin.py`
- **Vì sao nằm ở phase 2:** Phải nắn thẳng layer rules trước khi đụng vào các "boss" bự (như flashcards), để sau đó mọi tệp tách ra có sẵn format layer để tham chiếu.
- **Kết quả mong đợi:** Các Controller xử lý truy vấn trở thành Repository/QueryModule độc lập.
- **Rủi ro:** Sai sót số liệu thống kê.
- **Điều kiện để merge:** Các chỉ số stats (overview, today, tomorrow) trả về y chang như trước. Bắt buộc viết snapshot assertion (hoặc manual view test kỹ) cho API response stats.

### Phase 3: Công phá God-Files (Deep Decomposition)
- **Mục tiêu:** Cắt nhỏ `flashcards.py` (3000 dòng) và `flashcards_share_controller.py` (2000 dòng) về đúngBounded Context riêng.
- **Các file / module xử lý:**
  - `app/routes/flashcards.py`
  - `app/controllers/flashcards_share_controller.py`
- **Vì sao phải để sau:** Rủi ro vỡ luồng cốt lõi cao nhất, dễ conflict với branch feature nhất, cần các phase trước chuẩn bị hạ tầng rõ ràng để có bến đỗ an toàn khi code được cắt ra.
- **Kết quả mong đợi:** Folders cấu trúc tốt: `routes/flashcards/note_routes.py`, `services/flashcards/deck_clone_service.py` v.v. Không còn file nào mạn phép quá 500 dòng logic gộp.
- **Rủi ro:** Mất route, tham số truyền lệch, bể transaction session DB do không còn chung 1 scope function.
- **Điều kiện để merge:** Full regression tests (Cả bộ test API phải pass hoặc manual test trên nhiều account, user sharing quyền public/private).

## 5. Refactor strategy cho từng loại vấn đề

### 5.1 Route quá dày
- **Nên tách theo nguyên tắc nào:** Chia theo Feature/Entity. VD flashcard chia ra: Note, NoteType, Deck, Share, Import.
- **Dấu hiệu nào cho thấy route cần tách:** File vượt 500 dòng, khai báo chung nhiều endpoint không cùng use-case, import trực tiếp ORM models `db.session.query`.
- **Cách ưu tiên thứ tự tách:** Tách router HTTP ra trước `app/routes/flashcards/`, giữ hàm helper nội bộ trong file logic mới. Cắt những phần ít dùng trước (như Import/Marketplace share) để test độ mượt, sau đó mới cắt thẻ học cốt lõi (Note, Study).

### 5.2 Controller / Service lẫn vai trò
- **Khi nào nên rename:** Khi controller thực chất chỉ query Data không hứng HTTP request trực tiếp -> Rename thành `Repository` hoặc `QueryService`.
- **Khi nào nên tách file:** Khi file ôm cả 2 quá trình (VD Share Controller vừa xử lý rating, vừa xử lý logic install clone deck).
- **Khi nào chỉ cần chuẩn hóa boundary trước:** Khi hàm đang gọi lộn xộn, ta chuyển toàn bộ query hàm đấy sang Repository thuần túy để đảo chiều Import (DIP).

### 5.3 Template quá nặng
- **Khi nào phải tách JS ra static module:** Ngay khi block `<script>` vượt 50 dòng hoặc chứa event listener/ fetch API DOM manipulation.
- **Những template nào cần xử lý trước:** `dashboard.html` và `shared_deck_detail.html` (rất rườm rà).
- **Cách giảm coupling giữa HTML và logic UI:** Sử dụng `data-*` attributes ở HTML để truyền ID/Context; JS bắt event qua class/id và hook vào `data-*`. Không nhúng `{{ jinja }}` lung tung sâu bên dưới thân JS function. Truyền config xuống window namespace 1 lần duy nhất ở đầu.

### 5.4 Duplicate logic / access rule / query logic
- **Logic nào nên gom vào đâu:** Rule "Deck này ai có quyền xem" đẩy về `DeckAccessPolicyService`. Chứ không để kiểm tra if-else rời rạc ở route import/share.
- **Chỗ nào cần shared service hoặc query module:** Quét toàn bộ cây nhị phân/ BFS cho Deck Hierarchy (tổ tiên trực tiếp) cần 1 `DeckTreeQueryModule`.
- **Cách tránh copy rule giữa nhiều tầng:** Mọi thay đổi về state DB phải gọi đi qua duy nhất 1 application service có nhiệm vụ định tuyến transaction DB, các tầng khác cấm trực tiếp commit.

## 6. Những việc không nên làm ngay
- **Refactor `anki_scheduler.py`:** Tuy code Scheduler phức tạp nhưng đã ổn định và không bị trộn lẫn với route. Đụng vào rủi ro cực kì cao (làm hỏng flashcard due time toàn hệ thống). CHƯA LÀM.
- **Đập đi viết lại cơ chế Frontend (áp dụng React/Vue vào Template):** Mất quá nhiều nguồn lực dev rẽ nhánh, phải làm từ đầu. Hãy duy trì kiến trúc Jinja2 kết hợp Static JS Modules. CHƯA LÀM.
- **Tối ưu câu queries (N+1 query nhấp nháy):** Ở mức review kiến trúc phân tầng, việc optimize số lần chọc DB tuy đúng nhưng chưa phải trọng tâm. Phân tách layer xong rồi đo đạc Profiler sau đó mới tối ưu. CHƯA LÀM trừ khi thấy rõ mồn một.

## 7. Guideline áp dụng ngay cho team

- **Route KHÔNG CHƠI VỚI ORM:** Tuyệt đối không query `db.session` trong tệp `app/routes`. Ngoại lệ duy nhất là lệnh lookup cơ bản quá nhỏ được team lead duyệt.
- **Template LÀ HIỂN THỊ, KHÔNG LÀ NÃO BỘ:** Không viết tính toán if-else logic nghiệp vụ vào Template. Script nằm đúng folder `/static/js`.
- **Dòng chảy Dependency:** Route ➔ Service ➔ Repository/Controller. Dịch vụ (Service) cấm tuyệt đối quay đầu import và xài lại Controller.
- **Tên đúng với bản chất:** Nếu file đuôi `_controller.py` nhưng chỉ chứa query, bắt tay đổi tên thành `_repository.py` ngay không chần chừ.
- **Luôn Refactor Trong PR Nhỏ:** Không ai được tạo một PR 3000 dòng tên là "Big Architecture Refactor". Cắt nhỏ theo Phase/Domain (Ví dụ "Refactor: trích xuất JS khỏi Dashboard").

## 8. Kết luận hành động

**5 Việc Nên Làm Ngay:**
1. Trích xuất JS khỏi `templates/dashboard.html` ra file static.
2. Trích xuất JS khỏi `templates/flashcards/shared_deck_detail.html`.
3. Tách tính toán Tree cho `dashboard()` vào `DashboardService`.
4. Dọn dẹp wrapper cồng kềnh trong `vocabulary.py`.
5. Tạo `ReviewRepository` để gỡ phụ thuộc ngược cho `stats_overview.py`.

**5 Việc Chưa Nên Làm Ngay (Hoặc Rủi Ro Quá Cao Cần Cẩn Thận):**
1. Chia tách lập tức `app/routes/flashcards.py`. (Sẽ làm ở Phase 3).
2. Tách God-controller `flashcards_share_controller.py`. (Sẽ làm ở Phase 3).
3. Đổi cấu trúc frontend sang SPA/Lib mới (React/Vue).
4. Code lại logic lõi bên trong `anki_scheduler.py`.
5. Refactor tối ưu Performance (Query ORM/ N+1) khi chưa có file riêng lẻ nào rõ ràng.

**Thứ Tự Thực Hiện Đề Xuất:**
- Bắt đầu với các PR dành riêng cho **Phase 1** (UI/Templates, Main/Vocabulary Routes).
- Triển khai **Phase 2** nắn lại Layer & Stats.
- Đóng chốt bằng việc chẻ nhỏ các module cốt lõi **Phase 3** (Flashcards).

**Tiêu Chí Đánh Giá Thành Công:**
- Code size của các group routes phải nhỏ đi thấy rõ (bình quân mỗi tệp route không quá 500 dòng).
- Template không còn logic nghiệp vụ API dài ở Frontend.
- Không còn bất cứ Dependency Inversion (gọi ngược Controller) nào trong các tệp Service hiện tại. Test coverage và feature không bị hồi quy.
