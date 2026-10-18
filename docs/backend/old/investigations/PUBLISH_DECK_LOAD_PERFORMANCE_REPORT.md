# BÁO CÁO ĐIỀU TRA KỸ THUẬT VÀ PHƯƠNG ÁN TỐI ƯU HÓA HIỆU NĂNG TOÀN DIỆN
# Technical Root Cause Analysis & Optimization Architecture: GET /api/shared/decks/publish-options

| Thông tin | Chi tiết |
| :--- | :--- |
| **Mã điều tra** | PERF-INV-2026-001 |
| **Hệ thống** | Flama Learning Platform - Marketplace Deck Publishing |
| **Endpoint trọng điểm** | `GET /api/shared/decks/publish-options` |
| **Giao diện liên quan** | Đăng học liệu lên Chợ (`/marketplace/decks/publish`) |
| **Trạng thái** | Hoàn thành điều tra, Kiểm định phản biện (Adversarially Audited & Hardened) |
| **Phiên bản báo cáo** | 4.0 (Final Adversarially Audited & Hardened: Cụ thể hóa Dataclass Batch Context, Code nhánh Fallback Standalone, Chuẩn hóa Import Repository & Quy tắc Đếm thẻ Overlay) |
| **Ngày cập nhật** | 2026-10-08 |

---

## 1. Executive Summary (Tóm tắt điều hành)

### 1.1. Hiện tượng & Vấn đề (Problem Statement)
Khi người dùng truy cập màn hình **Đăng học liệu** (`/marketplace/decks/publish`), ứng dụng gửi yêu cầu HTTP tới endpoint `GET /api/shared/decks/publish-options` nhằm nạp danh sách toàn bộ các bộ thẻ (decks) do người dùng sở hữu cùng trạng thái hợp lệ để chia sẻ (publish eligibility).

Trên các tài khoản thực tế có số lượng bộ thẻ trung bình hoặc lớn (đặc biệt là người dùng đồng bộ từ Anki với hàng chục bộ thẻ phân cấp cha-con), endpoint này mất từ **3.5 giây đến hơn 15 giây** để phản hồi, đôi khi chạm ngưỡng timeout (HTTP 504 Gateway Timeout). Trong suốt khoảng thời gian này, giao diện người dùng bị khóa hoàn toàn trong trạng thái loading ("Đang tải danh sách bộ thẻ..."), gây nghẽn luồng trải nghiệm và cản trở việc đóng góp học liệu lên Marketplace.

### 1.2. Kết quả điều tra nguyên nhân gốc rễ (Root Cause Summary)
Quá trình điều tra chuyên sâu mã nguồn backend đã định vị chính xác **4 điểm nghẽn nghiêm trọng (Bottlenecks)** và **2 rủi ro kiến trúc / tương thích**:

1. **Lạm dụng module Quản lý Lịch học (`browse_card_service.build_browse_decks`) để đếm thẻ**:
   Giao diện đăng học liệu chỉ cần một thông tin duy nhất về số lượng thẻ là tổng số thẻ (`card_count`). Tuy nhiên, backend lại kích hoạt toàn bộ pipeline xây dựng cây thẻ học (`build_browse_decks`). Pipeline này kích hoạt hàng loạt phép tính toán nặng nề của bộ lập lịch học Anki (Scheduler runtime, timezone day boundaries, queue normalization: `new`, `learn`, `due`), khóa quyền học tập (`lock_study_authority_route`), quét toàn bộ bảng tiến độ học (`card_progress`), và tính toán lại hai lần (double recounting) khi tài khoản ở chế độ `NOTE authority mode`. Toàn bộ dữ liệu `new`, `learn`, `due` sau đó bị vứt bỏ hoàn toàn.
2. **Bùng nổ truy vấn $N+1$ lồng nhau trong vòng lặp kiểm tra tính hợp lệ (`get_deck_publish_eligibility`)**:
   Backend duyệt qua từng bộ thẻ $i \in \{1 \dots N\}$ của người dùng và thực hiện từ **6 đến 10 truy vấn SQL riêng rẽ** cho mỗi bộ thẻ để: suy diễn Note Type, kiểm tra Note Type cài từ Marketplace, kiểm tra template kích hoạt, và quét cây con.
3. **Truy vấn cây con dư thừa lặp đôi (Duplicate Subtree BFS Queries)**:
   Hàm duyệt cây con `collect_subtree_ids` bị gọi **2 lần cho cùng một bộ thẻ** trong cùng một vòng lặp (lần 1 trong `resolve_single_note_type_for_deck`, lần 2 trong kiểm tra `descendant_shared`). Cả hai lần đều thực thi thuật toán tìm kiếm theo chiều rộng (BFS) bắn trực tiếp các câu lệnh SQL `SELECT id FROM decks WHERE parent_id IN (...)` xuống cơ sở dữ liệu theo từng tầng sâu của cây.
4. **Bất đối xứng trong duyệt quan hệ phả hệ cha-con (Tree Hierarchy Asymmetry)**:
   Mặc dù toàn bộ các bộ thẻ thuộc quyền sở hữu của người dùng đã được tải sẵn vào bộ nhớ RAM (`deck_by_id`), backend chỉ duyệt in-memory khi kiểm tra bộ cha (`ancestor_shared`), nhưng lại liên tục bắn SQL BFS xuống database khi kiểm tra bộ con (`descendant_shared`).
5. **Rủi ro phân hóa kiến trúc song hành (Architectural Dual-Track Drift)**:
   Mã nguồn tồn tại song song hai cài đặt của nghiệp vụ publish: module nguyên khối `app/services/flashcards_share_service.py` (đang được route gọi qua shim `app/services/flashcards_share.py`) và module tái cấu trúc `app/services/share/publish.py`. Hai module này có sự sai khác về logic kiểm tra template kích hoạt (`_active_note_type_templates` kiểm tra `study_applications.status_code == 'ACTIVE'` vs `resolved_note_type.templates`), cần được đồng bộ hóa triệt để khi thực hiện tối ưu.
6. **Rủi ro phá vỡ chữ ký hàm công khai của `get_deck_publish_eligibility` (Public Contract Risk)**:
   Hàm này là public API được gọi từ nhiều vị trí ngoài route publish (như `create_shared_deck_item`, `app/services/mcp/marketplace_tools.py`, `app/routes/flashcards/import_export.py`). Việc chuyển sang cơ chế batch bắt buộc phải bảo toàn tính tương thích ngược khi gọi đơn lẻ (`context=None`), tránh gây lỗi đổ vỡ dây chuyền (`TypeError`).

### 1.3. Tác động & Kết quả sau tối ưu dự kiến (As-Is vs. To-Be)

| Chỉ số đánh giá | Hiện trạng (As-Is) | Sau tối ưu (To-Be) | Mức độ cải thiện |
| :--- | :--- | :--- | :--- |
| **Độ phức tạp truy vấn SQL** | $O(N \cdot H)$ ($H$: độ sâu cây) | **$O(1)$ (Hằng số)** | **Triệt tiêu hoàn toàn bùng nổ $N+1$** |
| **Số SQL Roundtrips (N = 10 decks)** | **74 câu lệnh** | **8 câu lệnh** | **Giảm 89.2% số truy vấn** |
| **Số SQL Roundtrips (N = 50 decks)** | **~416 câu lệnh** | **8 câu lệnh** | **Giảm 98.1% số truy vấn** |
| **Số SQL Roundtrips (N = 150 decks)** | **~1,517 câu lệnh** | **8 - 9 câu lệnh** | **Giảm 99.4% số truy vấn** |
| **Độ trễ phản hồi API (Latency)** | 3,500ms – 15,000ms+ | **30ms – 80ms** | **Nhanh hơn 50x – 150x** |
| **Tải CPU / Database IOPS** | Cực cao (quét toàn bộ `card_progress`) | Tối thiểu (chỉ quét thẻ theo `deck_id`) | **Bảo vệ tài nguyên server** |
| **An toàn chu trình cây (Cycles)** | Dễ treo vòng lặp nếu BFS không kiểm soát | **Kháng chu trình tuyệt đối với `seen: set[int]`** | **Ngăn ngừa 100% RecursionError** |

---

## 2. Root Cause Analysis (RCA - Phân tích nguyên nhân gốc rễ chi tiết)

### 2.1. Bản đồ luồng thực thi & Kiến trúc song hành (Execution Flow & Architecture Trace)
Luồng xử lý khi request `GET /api/shared/decks/publish-options` đến backend:

```
[Client: GET /api/shared/decks/publish-options]
   │
   ▼
[app/routes/flashcards/share.py: shared_deck_publish_options()] (L410-415)
   │
   ├─▶ Imports: `from app.services import flashcards_share`
   │            └─ points to `app/services/flashcards_share.py` (L7: shim importing flashcards_share_service)
   │
   ▼
[app/services/flashcards_share_service.py: build_deck_publish_options()] (L593-627) [ACTIVE RUNTIME]
   │  (Song hành với `app/services/share/publish.py: build_deck_publish_options()` L237-271)
   │
   ├──▶ 1. _deck_publish_context(user_id) (L465-492)
   │       ├─ Query 1: Deck.query.filter(owner_user_id == user_id, deleted_at.is_(None)) (L466-478)
   │       ├─ Query 2: DeckMarketplaceItem.query.filter(source_deck_id.in_(deck_ids)) (L484-489)
   │       ├─ Query 3: DeckInstall.query.filter_by(user_id == user_id) (_installed_local_deck_ids, L379)
   │       └─ Query 4: DeckCloneDeckMap.query.filter(deck_install_id.in_(install_ids)) (L392-395)
   │
   ├──▶ 2. browse_card_service.build_browse_decks(...) (L598-608) [ĐIỂM NGHẼN 1]
   │       ├─ lock_study_authority_route(...) (browse_card_service.py L175)
   │       ├─ vocabulary_ctrl.build_browse_deck_tree_payload(...) (vocabulary_repository.py L729)
   │       │   ├─ resolve_scheduler_runtime_settings(...) -> Query scheduler_configs (L764)
   │       │   ├─ Quét toàn bộ cards, notes, card_progress -> Query đếm lịch học nặng (L772-808)
   │       │   ├─ Quét logical_installs & clone maps nếu có (L821-850)
   │       │   └─ Duyệt cây xây dựng node payload và counts (L994-1030)
   │       └─ [Nếu NOTE authority mode] aggregate_deck_study_counts(...) quét lại toàn bộ canonical availability! (browse_card_service.py L187-238)
   │
   └──▶ 3. for deck_id, deck in deck_by_id.items(): (L610-626) [ĐIỂM NGHẼN 2, 3, 4]
           └─ get_deck_publish_eligibility(deck) (L495-590)
               ├─ resolve_single_note_type_for_deck(deck_id) (L523, L1095-1117)
               │   ├─ collect_subtree_ids(deck_id) -> BFS SQL loop vào bảng decks (L1100, deck_tree_query.py L194-213)
               │   ├─ get_note_type_ids_for_decks_notes(...) -> SQL query notes (L1101, flashcards_share_repository.py L456-468)
               │   ├─ db.session.get(NoteType, ...) -> SQL query note_types (L1112)
               │   └─ _active_note_type_templates(...) -> SQL join templates + study_applications (L1115, template_release_repository.py L139-147)
               ├─ is_installed_note_type_copy(...) -> SQL query note_type_installs (L527, L404-412)
               ├─ collect_subtree_ids(deck_id) LẦN 2 -> Lặp lại BFS SQL loop! (L544)
               └─ Ancestor walk (in-memory) (L565-584)
```

---

### 2.2. Điểm nghẽn 1: Lạm dụng `build_browse_decks` để lấy `card_count`
- **Tập tin chính**: `app/services/flashcards_share_service.py` (Dòng 598–608, 623)
- **Tập tin liên quan**: 
  - `app/services/browse_card_service.py` (Dòng 168–281)
  - `app/repositories/vocabulary_repository.py` (Dòng 729–1030)
  - `app/services/deck_aggregation_service.py` (Dòng 146–220)

#### Dẫn chứng mã nguồn tại `build_deck_publish_options`:
```python
# app/services/flashcards_share_service.py
598:     browse_payload = browse_card_service.build_browse_decks(
599:         user_id=user_id,
600:         admin_mode=False,
601:         timezone_name="UTC",
602:     )
603:     browse_by_id = {
604:         int(row["id"]): row
605:         for row in browse_payload.get("decks", [])
606:         if row.get("id") is not None
607:     }
...
611:         browse_row = browse_by_id.get(deck_id, {})
612:         counts = browse_row.get("counts") if isinstance(browse_row.get("counts"), dict) else {}
...
623:                 "card_count": int((counts or {}).get("total") or 0),
```

#### Phân tích chi phí dư thừa:
Mục đích duy nhất của việc gọi `build_browse_decks` là lấy giá trị `counts.get("total")` tại dòng 623 để đưa vào trường `card_count`. Tuy nhiên, để trả về `browse_payload`, hệ thống phải thực hiện toàn bộ pipeline tính toán học tập phức tạp:

1. **Khóa bản ghi Study Authority Routing**:
   Hàm `lock_study_authority_route(db.session, learner_user_id=user_id)` (dòng 175 `browse_card_service.py`) thực thi truy vấn tới bảng `study_user_authority_routes` nhằm xác định chế độ học tập, áp đặt cơ chế khóa hàng (row-level lock) không cần thiết cho một màn hình chỉ xem danh sách.
2. **Khởi tạo thông số lịch học Anki (Scheduler Runtime Calculations)**:
   Hàm `resolve_scheduler_runtime_settings(user_id=user_id)` (dòng 764 `vocabulary_repository.py`) truy vấn bảng cấu hình `scheduler_configs` để lấy giờ chuyển ngày (`day_boundary_hour_local`), tính toán chỉ số ngày học `today_day_index` theo múi giờ UTC.
3. **Biểu thức SQL phức tạp và quét bảng `card_progress`**:
   `vocabulary_repository.py` (dòng 772–808) tạo câu truy vấn phức hợp:
   ```sql
   SELECT notes.deck_id,
          COUNT(cards.id) AS total,
          SUM(CASE WHEN (is_new) THEN 1 ELSE 0 END) AS new,
          SUM(CASE WHEN (is_learn) THEN 1 ELSE 0 END) AS learn,
          SUM(CASE WHEN (is_due_review) THEN 1 ELSE 0 END) AS due
   FROM cards
   JOIN notes ON cards.note_id = notes.id
   LEFT OUTER JOIN card_progress ON card_progress.card_id = cards.id AND card_progress.user_id = :user_id
   WHERE notes.deck_id IN (:scoped_ids) AND notes.user_id = :user_id
   GROUP BY notes.deck_id;
   ```
   Câu truy vấn này thực hiện phép quét lớn trên bảng `card_progress` (thường có hàng chục nghìn bản ghi đối với người dùng chăm học) kèm các phép so sánh thời gian phức tạp (`active_progress_expr`, `normalized_queue_expr`, `review_due_expr`).
4. **Tính toán lặp đôi trong NOTE Authority Mode (Double Recounting Penalty)**:
   Tại dòng 187–238 `browse_card_service.py`:
   ```python
   if authority_route.mode_code == "NOTE":
       ...
       direct_counts, _note_types = aggregate_deck_study_counts(
           db.session,
           learner_user_id=user_id,
           visible_deck_ids=sorted(deck_ids),
           ...
       )
   ```
   Trong Flama, hầu hết tài khoản người dùng hoạt động ở chế độ `NOTE mode`. Điều này kích hoạt hàm `aggregate_deck_study_counts` (tại `app/services/deck_aggregation_service.py`), đọc `storage_profile`, duyệt qua tất cả thẻ thông qua `note_reads.note_card_rows`, và thực hiện đếm lại từ đầu!
5. **Lãng phí hoàn toàn**:
   Toàn bộ các trường `new`, `learn`, `due` cùng các dữ liệu lịch học tính toán được **bị loại bỏ hoàn toàn** tại dòng 623 của `flashcards_share_service.py`.

---

### 2.3. Điểm nghẽn 2: Bùng nổ truy vấn $N+1$ trong `get_deck_publish_eligibility`
- **Tập tin chính**: `app/services/flashcards_share_service.py` (Dòng 495–590)
- **Tập tin liên quan**:
  - `app/services/flashcards_share_service.py` (Dòng 1095–1117: `resolve_single_note_type_for_deck`)
  - `app/repositories/flashcards_share_repository.py` (Dòng 456–468: `get_note_type_ids_for_decks_notes`)
  - `app/repositories/template_release_repository.py` (Dòng 139–147: `active_templates`)
  - `app/services/flashcards_share_service.py` (Dòng 404–412: `is_installed_note_type_copy`)
  - `app/services/flashcards_share_service.py` (Dòng 455–457: `_active_note_type_templates`)

Tại vòng lặp chính của `build_deck_publish_options`:
```python
609:     items = []
610:     for deck_id, deck in deck_by_id.items():
...
613:         eligibility = get_deck_publish_eligibility(
614:             user_id=user_id,
615:             deck=deck,
616:             context=context,
617:         )
```
Với mỗi bộ thẻ `deck`, hàm `get_deck_publish_eligibility` thực hiện chuỗi truy vấn sau:

#### Bước 2.1: Suy diễn Note Type (`resolve_single_note_type_for_deck`)
```python
# app/services/flashcards_share_service.py: dòng 1095-1117
1095: def resolve_single_note_type_for_deck(*, deck_id: int, owner_user_id: int | None = None):
1100:     deck_ids = collect_subtree_ids(deck_id)
1101:     note_type_ids = flashcards_share_repository.get_note_type_ids_for_decks_notes(
1102:         deck_ids, owner_user_id,
1103:     )
...
1111:     resolved_note_type_id = note_type_ids[0]
1112:     resolved_note_type = db.session.get(NoteType, resolved_note_type_id)
1115:     if not _active_note_type_templates(resolved_note_type.id):
```
- **Dòng 1100**: Gọi `collect_subtree_ids(deck_id)`. Hàm này thực hiện BFS bắn từ $1$ đến $H_i + 1$ câu lệnh SQL vào bảng `decks`.
- **Dòng 1101**: Gọi `get_note_type_ids_for_decks_notes`. Hàm này thực thi:
  ```sql
  SELECT DISTINCT notes.note_type_id 
  FROM notes 
  WHERE notes.deck_id IN (:deck_ids) AND notes.user_id = :owner_user_id;
  ```
  -> **1 câu lệnh SQL riêng biệt cho mỗi bộ thẻ**.
- **Dòng 1112**: `db.session.get(NoteType, ...)` -> Truy vấn bảng `note_types` nếu đối tượng chưa nằm trong SQLAlchemy Identity Map.
- **Dòng 1115**: Gọi `_active_note_type_templates` -> Chạy `active_templates` (`app/repositories/template_release_repository.py` dòng 139–147):
  ```sql
  SELECT DISTINCT templates.* 
  FROM templates 
  JOIN study_applications ON study_applications.template_id = templates.id 
  WHERE study_applications.note_type_id = :note_type_id 
    AND study_applications.status_code = 'ACTIVE' 
  ORDER BY templates.id;
  ```
  -> **1 câu lệnh SQL join phức tạp cho mỗi bộ thẻ**.

#### Bước 2.2: Kiểm tra Note Type từ Marketplace (`is_installed_note_type_copy`)
```python
# app/services/flashcards_share_service.py: dòng 527
527:     if inferred_note_type_id and is_installed_note_type_copy(inferred_note_type_id):
```
Hàm `is_installed_note_type_copy` (`app/services/flashcards_share_service.py` dòng 404–412) thực thi:
```sql
SELECT * FROM note_type_installs WHERE installed_note_type_id = :inferred_note_type_id LIMIT 1;
```
-> **1 câu lệnh SQL cho mỗi bộ thẻ**.

---

### 2.4. Điểm nghẽn 3: Truy vấn cây con dư thừa lặp đôi (Duplicate Subtree BFS Queries)
- **Tập tin chính**: `app/services/flashcards_share_service.py` (Dòng 523, 544)
- **Tập tin liên quan**: `app/repositories/deck_tree_query.py` (Dòng 194–213)

Quan sát sự lặp lại trong `get_deck_publish_eligibility`:
1. **Lần 1 tại dòng 523**: Gọi `resolve_single_note_type_for_deck(deck_id=deck_id)`. Bên trong hàm đó (dòng 1100), hệ thống gọi:
   ```python
   deck_ids = collect_subtree_ids(deck_id)
   ```
2. **Lần 2 tại dòng 544**: Ngay sau khi suy diễn Note Type xong, hàm tiến hành kiểm tra xem có bộ con nào đã được chia sẻ không (`descendant_shared`):
   ```python
   544:     descendant_ids = set(collect_subtree_ids(deck_id)) - {deck_id}
   ```
Cùng một bộ thẻ `deck_id`, hàm `collect_subtree_ids(deck_id)` bị gọi **2 lần liên tiếp** trong cùng một iteration!

Xem xét mã nguồn của `collect_subtree_ids` trong `app/repositories/deck_tree_query.py`:
```python
194: def collect_subtree_ids(root_deck_id: int | None) -> list[int]:
195:     if root_deck_id is None:
196:         return []
197:     seen: set[int] = set()
198:     frontier: set[int] = {int(root_deck_id)}
199:     while frontier:
200:         current_ids = {deck_id for deck_id in frontier if deck_id not in seen}
201:         if not current_ids:
202:             break
203:         seen.update(current_ids)
204:         child_rows = (
205:             db.session.query(Deck.id)
206:             .filter(Deck.parent_id.in_(current_ids))
207:             .all()
208:         )
209:         frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}
210:     return sorted(seen)
```
Mỗi lần gọi `collect_subtree_ids(deck_id)`, hệ thống lặp vòng `while frontier` và bắn câu lệnh `SELECT id FROM decks WHERE parent_id IN (...)` xuống cơ sở dữ liệu cho từng cấp bậc của cây. Nếu cây có độ sâu $H_i$, hàm sẽ bắn $H_i + 1$ câu truy vấn.
Vì bị gọi 2 lần, số câu truy vấn cây con cho một bộ thẻ là:
$$2 \times (H_i + 1)$$
Với $N$ bộ thẻ, tổng số truy vấn chỉ riêng cho `collect_subtree_ids` là:
$$Q_{\text{subtree}} = \sum_{i=1}^N 2(H_i + 1)$$
Với $N = 50$ và trung bình $H_i = 1$, riêng thao tác này đã sinh ra **$50 \times 2 \times 2 = 200$ truy vấn SQL**!

---

### 2.5. Điểm nghẽn 4: Bất đối xứng trong duyệt quan hệ phả hệ cha-con
- **Tập tin chính**: `app/services/flashcards_share_service.py` (Dòng 465–492, 544–584)

Xem xét cách `_deck_publish_context` khởi tạo dữ liệu ban đầu:
```python
466:     owned_decks = (
467:         Deck.query.filter(
468:             Deck.owner_user_id == user_id,
469:             Deck.deleted_at.is_(None),
470:         )
...
478:         .all()
479:     )
480:     deck_by_id = {int(deck.id): deck for deck in owned_decks}
```
Tại dòng 480, **toàn bộ các bộ thẻ thuộc quyền sở hữu của người dùng đã nằm trong bộ nhớ RAM** tại biến `deck_by_id`. Mỗi đối tượng `Deck` đều chứa đầy đủ `id` và `parent_id`.

Tuy nhiên, trong `get_deck_publish_eligibility`:
- **Khi duyệt lên trên (Ancestor Check - dòng 565–584)**:
  Mã nguồn duyệt bằng vòng lặp `while parent_id is not None` và tra cứu `parent_deck = deck_by_id.get(current_parent_id)` hoàn toàn trong bộ nhớ RAM, **không tốn bất kỳ truy vấn SQL nào**.
- **Khi duyệt xuống dưới (Descendant Check - dòng 544)**:
  Mã nguồn lại gọi `collect_subtree_ids(deck_id)`, hoàn toàn bỏ qua dữ liệu cây đã có sẵn trong `deck_by_id`, và bắn hàng loạt câu lệnh SQL BFS xuống cơ sở dữ liệu!

Sự bất đối xứng này biến một thao tác tra cứu cây in-memory thuần túy thành hàng trăm truy vấn I/O mạng.

---

### 2.6. Điểm nghẽn 5: Kiến trúc song hành & Nguy cơ phân hóa mã nguồn (Architectural Dual-Track Drift)
- **Tập tin 1 (Monolith Shim)**: `app/services/flashcards_share_service.py` (Dòng 593–627)
- **Tập tin 2 (Modular Package)**: `app/services/share/publish.py` (Dòng 237–271)
- **Tập tin liên kết**: `app/routes/flashcards/share.py` (Dòng 13, 410–415)

#### Phát hiện kỹ thuật:
1. Endpoint `GET /api/shared/decks/publish-options` tại `app/routes/flashcards/share.py` thực hiện:
   ```python
   from app.services import flashcards_share
   ...
   return jsonify(flashcards_share.build_deck_publish_options(user_id=current_user.id))
   ```
2. Tập tin `app/services/flashcards_share.py` thực chất là một compat shim:
   ```python
   from app.services.flashcards_share_service import *
   ```
   Do đó, **tại thời điểm chạy thực tế (Runtime), Flask route đang thực thi hàm `build_deck_publish_options` bên trong `app/services/flashcards_share_service.py`**.
3. Tuy nhiên, repository đã có gói module mới tại `app/services/share/`, trong đó `app/services/share/publish.py` định nghĩa lại hàm `build_deck_publish_options` (dòng 237) và được re-export tại `app/services/share/__init__.py`.
4. **Sự sai khác logic nguy hiểm (Divergence Risk)**:
   - Trong `flashcards_share_service.py` (dòng 1115), hàm `resolve_single_note_type_for_deck` gọi `_active_note_type_templates(resolved_note_type.id)`, yêu cầu template phải gắn với study application có trạng thái `ACTIVE`.
   - Trong `app/services/share/helpers.py` (dòng 297), hàm `resolve_single_note_type_for_deck` chỉ kiểm tra `if not resolved_note_type.templates:`.
   
Nếu đội ngũ chỉ tối ưu một trong hai tập tin, hệ thống sẽ rơi vào tình trạng hành vi không nhất quán giữa API route và các tác vụ gọi qua package `app.services.share` (ví dụ như MCP Tools hoặc batch scripts). Do đó, kế hoạch tối ưu **bắt buộc phải đồng bộ hóa song song cả hai vị trí**.

---

### 2.7. Rủi ro phá vỡ chữ ký hàm công khai của `get_deck_publish_eligibility` (Public Contract Breaking Risk)
- **Tập tin chính**: `app/services/flashcards_share_service.py` (Dòng 495–590)
- **Tập tin đối ứng**: `app/services/share/publish.py` (Dòng 138–235)

#### Bối cảnh & Phát hiện kỹ thuật:
Hàm `get_deck_publish_eligibility` không phải là hàm private nội bộ của riêng `build_deck_publish_options`, mà là một **Public Service API** đang được trực tiếp import và gọi bởi ít nhất 4 vị trí độc lập trên toàn hệ thống:
1. `app/services/flashcards_share_service.py: create_shared_deck_item` (Dòng 644) – Khi người dùng bấm submit publish một bộ thẻ.
2. `app/services/share/publish.py: create_shared_deck_item` (Dòng 289) – Phiên bản modular tương ứng.
3. `app/services/mcp/marketplace_tools.py: get_deck_publish_options` (Dòng 215) – Tool AI Model Context Protocol (MCP) kiểm tra eligibility của một `deck_id` cụ thể.
4. `app/routes/flashcards/import_export.py: _share_deck_page_impl` (Dòng 175) – Handler chia sẻ bộ thẻ đơn lẻ.

Tất cả các vị trí trên đều gọi hàm với cú pháp kiểm tra một bộ thẻ đơn lẻ:
```python
eligibility = get_deck_publish_eligibility(
    user_id=user_id,
    deck=deck,
    allow_existing=...,
    # context KHÔNG được truyền vào (None)
)
```

#### Rủi ro khi refactor:
Nếu lập trình viên khi tối ưu hóa vội vàng thay đổi chữ ký của `get_deck_publish_eligibility` thành bắt buộc phải nhận vào các tham số batch (`subtree_ids_by_deck`, `batch_context`, ...), toàn bộ 4 vị trí trên sẽ lập tức sập với ngoại lệ `TypeError: missing required argument` hoặc `AttributeError`.

#### Giải pháp thiết kế bắt buộc:
Thiết kế cấu trúc dữ liệu gom nhóm và chữ ký mở rộng theo cơ chế **Backward-Compatible Hybrid Context**:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DeckPublishBatchContext:
    """Ngữ cảnh nạp dữ liệu hàng loạt phục vụ tra cứu O(1) in-memory cho eligibility."""
    subtree_ids_by_deck: dict[int, set[int]]       # Map deck_id -> tập hợp ID cây con (đã kháng chu trình)
    deck_to_note_types: dict[int, set[str]]        # Map deck_id -> tập hợp Note Type IDs
    marketplace_installed_nt_ids: set[str]        # Tập hợp các Note Type IDs cài từ Marketplace
    active_template_nt_ids: set[str]               # Tập hợp các Note Type IDs có Template ACTIVE
```

Chữ ký hàm `get_deck_publish_eligibility`:
```python
def get_deck_publish_eligibility(
    *,
    user_id: int,
    deck: Deck,
    allow_existing: bool = False,
    context: tuple[dict[int, Deck], set[int], dict[int, DeckMarketplaceItem]] | None = None,
    batch_context: DeckPublishBatchContext | None = None,
) -> dict[str, Any]:
```
- **Nhánh 1 (Fast-Path In-Memory)**: Khi được gọi từ vòng lặp tối ưu của `build_deck_publish_options`: truyền đầy đủ `batch_context` để tra cứu $O(1)$ in-memory, không phát sinh bất kỳ truy vấn SQL nào.
- **Nhánh 2 (Safe Standalone Fallback)**: Khi được gọi đơn lẻ từ các consumer bên ngoài (`batch_context is None`): hàm tự động fallback thực thi các hàm lazy resolve đơn lẻ truyền thống (`resolve_single_note_type_for_deck`, `is_installed_note_type_copy`, `collect_subtree_ids`), bảo đảm 100% không làm gãy vỡ hợp đồng gọi hàm hiện hữu của 4 consumer ngoại vi.

---

## 3. Quantitative Impact Modeling (Mô hình hóa định lượng tác động)

### 3.1. Mô hình toán học về số lượng truy vấn cơ sở dữ liệu
Đặt:
- $N$: Tổng số bộ thẻ (`decks`) người dùng sở hữu.
- $H$: Độ sâu trung bình của cây phân cấp bộ thẻ ($H = 0$ nếu phẳng, $H = 1$ nếu có 1 cấp con, $H \ge 2$ nếu nhiều tầng lồng nhau).
- $M$: Tổng số ghi chú (`notes`) người dùng sở hữu.
- $C$: Tổng số thẻ (`cards`) người dùng sở hữu.
- $P$: Tổng số bản ghi tiến độ học (`card_progress`) của người dùng.

#### Công thức Hiện trạng (As-Is):
$$Q_{\text{As-Is}} = Q_{\text{context}} + Q_{\text{browse}} + \sum_{i=1}^N \left[ 2(H_i + 1) + Q_{\text{nt\_query}} + Q_{\text{nt\_get}} + Q_{\text{tpl\_active}} + Q_{\text{nt\_inst}} \right]$$

Trong đó:
- $Q_{\text{context}} \approx 3 - 4$ truy vấn (Decks, Marketplace Items, Installs, Clone Maps).
- $Q_{\text{browse}} \approx 8 - 13$ truy vấn nặng (Route lock, Decks, Scheduler configs, Card progress scan quét $P$ bản ghi, NOTE mode aggregation đếm lại toàn bộ).
- Trong vòng lặp mỗi bộ thẻ ($N$ lần lặp):
  - Subtree BFS (2 lần gọi): $2(H_i + 1)$ truy vấn.
  - Distinct Note Types: 1 truy vấn.
  - NoteType entity fetch: 0 - 1 truy vấn (tùy thuộc session cache).
  - Active Templates join: 1 truy vấn.
  - Installed NoteType check: 1 truy vấn.
  - Tổng cộng mỗi bộ thẻ: $2H_i + 5$ đến $2H_i + 6$ truy vấn.

$$\implies Q_{\text{As-Is}} \approx 15 + N \times (2H + 5.5)$$

#### Công thức Sau tối ưu (To-Be):
$$Q_{\text{To-Be}} = Q_{\text{context}} + Q_{\text{batch\_counts}} + Q_{\text{batch\_note\_types}} + Q_{\text{batch\_templates}} + Q_{\text{batch\_installs}}$$
$$Q_{\text{To-Be}} \approx 4 + 1 + 1 + 1 + 1 = 8 \text{ truy vấn (Hằng số } O(1) \text{ đối với mọi } N!)$$

---

### 3.2. Bảng ma trận so sánh số lượng truy vấn theo quy mô dữ liệu

| Kịch bản người dùng | Quy mô dữ liệu | As-Is: Context + Browse | As-Is: Loop N decks | As-Is Tổng truy vấn (Roundtrips) | To-Be Tổng truy vấn (Optimized) | Tỷ lệ cắt giảm truy vấn |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kịch bản 1: User Mới / Cơ bản** | $N = 10$ decks<br>$H = 0$ (phẳng)<br>$M = 200$ notes<br>$C = 300$ cards | 14 queries | $10 \times 6 = 60$ queries | **74 queries** | **8 queries** | **- 89.2%** |
| **Kịch bản 2: User Tiêu chuẩn** | $N = 30$ decks<br>$H = 1$ (1 cấp con)<br>$M = 1,200$ notes<br>$C = 2,000$ cards | 15 queries | $30 \times 8 = 240$ queries | **255 queries** | **8 queries** | **- 96.9%** |
| **Kịch bản 3: User Tích cực / Giáo viên** | $N = 50$ decks<br>$H = 1$ (1 cấp con)<br>$M = 2,500$ notes<br>$C = 5,000$ cards | 16 queries | $50 \times 8 = 400$ queries | **416 queries** | **8 queries** | **- 98.1%** |
| **Kịch bản 4: Power User / Import Anki** | $N = 100$ decks<br>$H = 2$ (2 cấp con)<br>$M = 8,000$ notes<br>$C = 16,000$ cards | 16 queries | $100 \times 10 = 1,000$ queries | **1,016 queries** | **8 queries** | **- 99.2%** |
| **Kịch bản 5: Enterprise / Extreme** | $N = 150$ decks<br>$H = 2$ (2 cấp con)<br>$M = 15,000$ notes<br>$C = 30,000$ cards | 17 queries | $150 \times 10 = 1,500$ queries | **1,517 queries** | **8 - 9 queries** | **- 99.4%** |

---

### 3.3. Phân tích chi phí CPU, Memory và Độ trễ mạng (Latency Analysis)

#### 1. Network Roundtrip Time (RTT Latency):
Trong kiến trúc phân tán hoặc container hóa của Flama (Flask App kết nối qua TCP socket/mạng tới MySQL container), mỗi truy vấn SQL có độ trễ mạng tối thiểu từ $1.5\text{ms} - 3.5\text{ms}$.
- Với Kịch bản 3 ($N = 50$ decks, 416 queries):
  $$\text{Latency}_{\text{RTT}} = 416 \times 2.5\text{ms} \approx 1,040\text{ms} \quad (1.04 \text{ giây riêng cho độ trễ truyền gói tin!})$$
- Với Kịch bản 5 ($N = 150$ decks, 1,517 queries):
  $$\text{Latency}_{\text{RTT}} = 1,517 \times 2.5\text{ms} \approx 3,792\text{ms} \quad (3.79 \text{ giây riêng cho độ trễ truyền gói tin!})$$

#### 2. CPU Processing Overhead & ORM Deserialization:
- **Quét bảng `card_progress`**: Bảng này tích lũy toàn bộ lịch sử ôn tập. Việc thực hiện các phép toán `CASE WHEN` tính toán `review_due_expr` so khớp múi giờ khiến CPU của MySQL tăng vọt mỗi khi người dùng mở trang publish.
- **Hydration của SQLAlchemy**: Việc nạp và hủy hàng trăm đối tượng ORM (`NoteType`, `Template`, `Deck`) trong vòng lặp Python gây áp lực phân bổ bộ nhớ và kích hoạt Garbage Collection liên tục trên worker process của Gunicorn.

#### 3. Cạn kiệt Connection Pool & Rủi ro khóa đồng thời:
Hàm `lock_study_authority_route` gọi trong `build_browse_decks` giữ lock bản ghi routing của người dùng trong khi hàng trăm câu query phía sau đang thực thi tuần tự. Trong thời gian này, các request học thẻ song song của chính người dùng đó hoặc các worker khác sẽ bị chặn, dẫn đến nghẽn connection pool.

---

## 4. Database Query Waterfall (Biểu đồ dòng thác truy vấn SQL)

### 4.1. Waterfall Hiện trạng (As-Is - 416 Queries, ~3.55 giây)
Mô phỏng chi tiết trình tự thực thi truy vấn của request `GET /api/shared/decks/publish-options` đối với người dùng có **50 bộ thẻ** ($N = 50$, $H = 1$):

```
Thời gian (ms)
0ms    ├─ [Query 1] SELECT * FROM decks WHERE owner_user_id = 12 AND deleted_at IS NULL ... (3ms)
       ├─ [Query 2] SELECT * FROM deck_marketplace_items WHERE source_deck_id IN (...) (2ms)
       ├─ [Query 3] SELECT * FROM deck_installs WHERE user_id = 12 (2ms)
10ms   ├─ [Query 4] SELECT local_deck_id FROM deck_clone_deck_maps WHERE deck_install_id IN (...) (2ms)
       │
       ▼ [PHASE BROWSE DECKS - CỰC KỲ NẶNG]
20ms   ├─ [Query 5] SELECT * FROM study_user_authority_routes WHERE learner_user_id = 12 (3ms)
30ms   ├─ [Query 6] SELECT * FROM decks WHERE ... (collect_accessible_browse_decks) (3ms)
40ms   ├─ [Query 7] SELECT * FROM scheduler_configs WHERE user_id = 12 (2ms)
50ms   ├─ [Query 8] SELECT Note.deck_id, COUNT(Card.id), SUM(CASE...), SUM(CASE...) 
       │            FROM cards JOIN notes LEFT JOIN card_progress ... 
       │            [Quét 15,000 card_progress rows] (85ms)
140ms  ├─ [Query 9] SELECT Note.deck_id, Note.note_type_id FROM notes ... (4ms)
150ms  ├─ [Query 10] SELECT * FROM note_types WHERE id IN (...) (3ms)
160ms  ├─ [Query 11] SELECT * FROM scheduler_configs WHERE user_id = 12 [LẶP LẠI!] (2ms)
170ms  ├─ [Query 12] SELECT * FROM study_storage_profiles ... (2ms)
180ms  ├─ [Query 13] [NOTE Mode Recount] UNION ALL cards, overlay, notes ... (120ms)
       │
310ms  ▼ [PHASE FOR LOOP: 50 DECKS x 8 QUERIES = 400 QUERIES TUẦN TỰ]
       │
       ├─ [Deck 1]
       │   ├─ [Query 14] SELECT id FROM decks WHERE parent_id IN (101) [BFS level 1] (2ms)
       │   ├─ [Query 15] SELECT id FROM decks WHERE parent_id IN (105, 106) [BFS level 2] (2ms)
       │   ├─ [Query 16] SELECT DISTINCT note_type_id FROM notes WHERE deck_id IN (...) (3ms)
       │   ├─ [Query 17] SELECT * FROM note_types WHERE id = 'nt_1' (2ms)
       │   ├─ [Query 18] SELECT templates.* FROM templates JOIN study_applications ... (4ms)
       │   ├─ [Query 19] SELECT * FROM note_type_installs WHERE installed_note_type_id = 'nt_1' (2ms)
       │   ├─ [Query 20] SELECT id FROM decks WHERE parent_id IN (101) [BFS LẶP LẠI LẦN 2!] (2ms)
       │   └─ [Query 21] SELECT id FROM decks WHERE parent_id IN (105, 106) [BFS LẶP LẠI LẦN 2!] (2ms)
       │
       ├─ [Deck 2]
       │   ├─ [Queries 22 - 29] (8 queries tuần tự) (19ms)
       │
       ├─ [Deck 3 ... Deck 49]
       │   ├─ [Queries 30 - 405] (Tuần tự thực thi 8 queries cho mỗi bộ thẻ) (~3,000ms)
       │
       ├─ [Deck 50]
       │   ├─ [Queries 406 - 413] (8 queries cuối cùng) (18ms)
       │
3,550ms ──▶ TRẢ VỀ JSON CHO CLIENT (Tổng thời gian ~3.55 giây)
```

---

### 4.2. Waterfall Sau tối ưu (To-Be - 8 Queries Hằng số, ~42ms)
Sau khi áp dụng kiến trúc gom truy vấn hàng loạt (Batching) và xử lý cây an toàn trong bộ nhớ:

```
Thời gian (ms)
0ms    ├─ [Query 1] SELECT * FROM decks WHERE owner_user_id = 12 AND deleted_at IS NULL ... (3ms)
4ms    ├─ [Query 2] SELECT * FROM deck_marketplace_items WHERE source_deck_id IN (...) (2ms)
7ms    ├─ [Query 3] SELECT * FROM deck_installs WHERE user_id = 12 (2ms)
10ms   ├─ [Query 4] SELECT local_deck_id FROM deck_clone_deck_maps WHERE deck_install_id IN (...) (2ms)
       │
13ms   ├─ [Query 5 - BATCH COUNTS] SELECT Note.deck_id, COUNT(Card.id) FROM cards 
       │                           JOIN notes ON Card.note_id = Note.id 
       │                           WHERE Note.user_id = 12 AND Note.deck_id IN (...) 
       │                           GROUP BY Note.deck_id; (5ms)
       │
19ms   ├─ [Query 6 - BATCH NOTE TYPES] SELECT Note.deck_id, Note.note_type_id FROM notes 
       │                               WHERE Note.user_id = 12 AND Note.deck_id IN (...) 
       │                               GROUP BY Note.deck_id, Note.note_type_id; (4ms)
       │
24ms   ├─ [Query 7 - BATCH MARKETPLACE NT] SELECT installed_note_type_id FROM note_type_installs 
       │                                   WHERE installed_note_type_id IN (:used_nt_ids); (2ms)
       │
27ms   ├─ [Query 8 - BATCH ACTIVE TPL] SELECT DISTINCT study_applications.note_type_id 
       │                               FROM study_applications 
       │                               JOIN templates ON study_applications.template_id = templates.id 
       │                               WHERE study_applications.note_type_id IN (:used_nt_ids) 
       │                                 AND study_applications.status_code = 'ACTIVE'; (3ms)
       │
31ms   ▼ [IN-MEMORY PROCESSING - THUẦN TÚY TRONG RAM]
       │  ├─ Xây dựng children_by_parent index: 0.05ms
       │  ├─ Tính toán subtree_ids cho từng bộ thẻ kèm chống chu trình (seen set): 0.15ms
       │  ├─ Post-order roll-up card_count: 0.08ms
       │  ├─ Tra cứu Note Type provenance & Active Templates qua in-memory sets: 0.05ms
       │  └─ Ancestor walk & Descendant check trên in-memory sets: 0.12ms
       │
33ms   ──▶ TRẢ VỀ JSON CHO CLIENT (Tổng thời gian ~35ms – 45ms, CẮT GIẢM 99% THỜI GIAN)
```

---

### 4.3. Bảng đối chiếu Lược đồ CSDL, Khóa ngoại & Chỉ mục (Database Schema & Index Alignment Matrix)

Để bảo đảm các câu lệnh SQL đề xuất thực thi ở độ phức tạp $O(1)$ mà không kích hoạt Full Table Scan (quét toàn bảng) trên MySQL InnoDB, toàn bộ bảng, cột, khóa ngoại và chỉ mục (Indexes) đã được đối chiếu chi tiết trực tiếp từ các file mô hình ORM:

| Bảng CSDL (`__tablename__`) | Model ORM tương ứng | Cột sử dụng trong tối ưu | Khóa ngoại (Foreign Keys) | Chỉ mục hiện hữu (Indexes) | Đánh giá Tối ưu & Kế hoạch Thực thi SQL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`decks`** | `models/deck.py: Deck` | `id`<br>`owner_user_id`<br>`parent_id`<br>`name`<br>`deleted_at` | `owner_user_id -> users.id`<br>`parent_id -> decks.id` | - `ix_decks_owner_user_id`<br>- `ix_decks_parent_id`<br>- `ix_decks_deleted_at` | **Tối ưu 100%**: Query lọc theo `owner_user_id` và `deleted_at IS NULL` khớp index `ix_decks_owner_user_id`. Truy vấn cây cha-con được chuyển hoàn toàn vào RAM. |
| **`deck_marketplace_items`** | `models/deck_marketplace_item.py: DeckMarketplaceItem` | `id`<br>`source_deck_id`<br>`publish_status` | `source_deck_id -> decks.id` | - `uq_deck_marketplace_items_source_deck` (Unique Index)<br>- `ix_deck_marketplace_items_source_deck_id` | **Tối ưu 100%**: Filter `source_deck_id.in_(deck_ids)` tận dụng Unique Index B-Tree, tra cứu tức thời. |
| **`deck_installs`** | `models/deck_install.py: DeckInstall` | `id`<br>`user_id`<br>`local_deck_id` | `user_id -> users.id`<br>`local_deck_id -> decks.id` | - `ix_deck_installs_user_id`<br>- `ix_deck_installs_local_deck_id` | **Tối ưu 100%**: Filter `user_id = :uid` sử dụng index `ix_deck_installs_user_id`. |
| **`deck_clone_deck_maps`** | `models/deck_clone_deck_map.py: DeckCloneDeckMap` | `deck_install_id`<br>`local_deck_id` | `deck_install_id -> deck_installs.id`<br>`local_deck_id -> decks.id` | - `ix_deck_clone_deck_maps_deck_install_id`<br>- `ix_deck_clone_deck_maps_local_deck_id`<br>- `uq_clone_map_local_deck` | **Tối ưu 100%**: Filter `deck_install_id.in_(install_ids)` sử dụng B-tree index, không sinh scan. |
| **`notes`** & **`cards`** | `models/note.py: Note`<br>`models/card.py: Card` | `Note.id`<br>`Note.user_id`<br>`Note.deck_id`<br>`Note.note_type_id`<br>`Card.id`<br>`Card.note_id` | `Note.user_id -> users.id`<br>`Note.deck_id -> decks.id`<br>`Note.note_type_id -> note_types.id`<br>`Card.note_id -> notes.id` | - `ix_notes_user_id`<br>- `ix_notes_deck_id`<br>- `ix_notes_note_type_id`<br>- `ix_cards_note_id` | **Tối ưu 100%**: Câu lệnh batch counts `JOIN Note ON Card.note_id = Note.id WHERE Note.user_id = :uid AND Note.deck_id IN (...)` sử dụng `ix_notes_user_id`/`ix_notes_deck_id` ở bảng `notes` và `ix_cards_note_id` ở bảng `cards`. |
| **`note_type_installs`** | `models/note_type_install.py: NoteTypeInstall` | `installed_note_type_id` | `installed_note_type_id -> note_types.id` | - `ix_note_type_installs_installed_note_type_id`<br>- `ix_note_type_installs_user_installed` | **Tối ưu 100%**: Filter `installed_note_type_id.in_(...)` tra cứu theo index B-tree. |
| **`study_applications`** & **`templates`** | `models/study_application.py: StudyApplication`<br>`models/template.py: Template` | `StudyApplication.note_type_id`<br>`StudyApplication.template_id`<br>`StudyApplication.status_code`<br>`Template.id` | `StudyApplication.note_type_id -> note_types.id`<br>`StudyApplication.template_id -> templates.id` | - `uq_study_applications_note_type_template_occurrence`<br>- `ix_study_applications_note_type_ord`<br>- Primary Key `templates.id` | **Tối ưu 100%**: `uq_study_applications_note_type_template_occurrence` có cột dẫn đầu là `note_type_id`. Khi filter `note_type_id.in_(...)` và join `Template.id`, MySQL duyệt index range scan cực nhanh. |

---

## 5. Architectural & Query Optimization Proposals (Đề xuất giải pháp tối ưu hóa toàn diện & Kháng lỗi)

Kiến trúc tối ưu hóa được thiết kế dựa trên 4 trụ cột công nghệ, bảo đảm **100% tuân thủ mô hình clone overlay của Flama, bảo toàn hợp đồng API với React SPA, và kháng hoàn toàn các lỗi suy thoái dữ liệu**:

```
┌────────────────────────────────────────────────────────────────────────┐
│               KIẾN TRÚC TỐI ƯU HÓA GET /publish-options                 │
└────────────────────────────────────────────────────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌──────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ 1. LIGHTWEIGHT BATCH CARD COUNTER    │   │ 2. CYCLE-SAFE IN-MEMORY TREE INDEX  │
│ - Bỏ 100% build_browse_decks         │   │ - children_by_parent hash map       │
│ - 1 SQL: GROUP BY Note.deck_id       │   │ - Kháng chu trình với seen set      │
│ - Roll-up card_count trong RAM       │   │ - Tái sử dụng subtree_ids cho mọi xử│
└──────────────────────────────────────┘   │   lý con cháu                       │
           │                               └─────────────────────────────────────┘
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌──────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ 3. BATCH NOTE TYPE PROVENANCE CHECK  │   │ 4. SUBTREE-BASED CONFLICT ENGINE    │
│ - 1 SQL: Note types theo deck_id     │   │ - Kiểm tra descendant_shared từ RAM │
│ - 1 SQL: Marketplace installed NTs   │   │ - Ancestor walk an toàn với seen    │
│ - 1 SQL: Active template status      │   │ - Không phân hóa giữa 2 services    │
└──────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

### Đề xuất 1: Thay thế `build_browse_decks` bằng Lightweight Batch Card Counter

#### Cơ chế hoạt động:
Giao diện đăng học liệu chỉ hiển thị duy nhất thông số `card_count`. Ta thay thế toàn bộ pipeline nặng nề của `browse_card_service.build_browse_decks` bằng đúng **1 câu lệnh SQL duy nhất** tổng hợp số thẻ do người dùng sở hữu:

```python
# app/repositories/flashcards_share_repository.py
def batch_get_cards_count_by_deck_ids(
    *,
    user_id: int,
    deck_ids: list[int],
) -> dict[int, int]:
    if not deck_ids:
        return {}
    rows = (
        db.session.query(
            Note.deck_id,
            db.func.count(Card.id),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(deck_ids),
        )
        .group_by(Note.deck_id)
        .all()
    )
    return {int(row[0]): int(row[1] or 0) for row in rows if row and row[0] is not None}
```

#### Cộng dồn phân cấp (Roll-up) an toàn trong bộ nhớ:
Với cấu trúc cây phân cấp, số lượng thẻ hiển thị của bộ thẻ cha phải bao gồm số thẻ của chính nó cộng với số thẻ của tất cả các bộ con cháu.
Thay vì dùng hàm đệ quy không kiểm soát dễ gặp `RecursionError` khi cây bị lỗi chu trình, ta tính tổng dựa trên tập hợp `subtree_ids` đã được bảo vệ kháng chu trình:

```python
direct_card_count = batch_get_cards_count_by_deck_ids(user_id=user_id, deck_ids=deck_ids)

# Tính card_count cộng dồn từ tập subtree_ids đã nạp an toàn
total_cards_by_deck: dict[int, int] = {}
for d_id in deck_ids:
    sub_ids = subtree_ids_by_deck.get(d_id, {d_id})
    total_cards_by_deck[d_id] = sum(direct_card_count.get(cid, 0) for cid in sub_ids)
```
- **Ưu điểm**: Giảm từ 13+ truy vấn nặng và việc quét hàng vạn dòng `card_progress` xuống đúng 1 truy vấn `GROUP BY` có index (`Note.user_id`, `Note.deck_id`).
- **Thời gian thực thi**: Giảm từ ~300ms xuống **~3ms**.

---

### Đề xuất 2: Chỉ mục cây trong RAM & Cơ chế kháng chu trình dữ liệu (Cycle-Safe In-Memory Tree Index)

#### Bối cảnh rủi ro & Ca biên:
Nếu người dùng gặp sự cố đồng bộ từ Anki client của bên thứ ba, cơ sở dữ liệu có thể xuất hiện:
- Chu trình khép kín: Bộ thẻ A có `parent_id = B`, Bộ thẻ B có `parent_id = A`.
- Tự tham chiếu (Self-loop): Bộ thẻ A có `parent_id = A`.
- Tham chiếu mồ côi (Orphan parent): `parent_id` trỏ tới một ID không còn tồn tại hoặc không thuộc `owned_decks`.

Nếu dùng đệ quy DFS thông thường, ứng dụng sẽ bị treo hoặc văng ngoại lệ `RecursionError: maximum recursion depth exceeded`, làm sập toàn bộ request.

#### Giải pháp BFS an toàn với tập `seen: set[int]`:
Trong `_deck_publish_context`, `owned_decks` đã có sẵn. Ta xây dựng index quan hệ cha-con và tính toán cây con thuần túy trong RAM:

```python
children_by_parent: dict[int, list[int]] = defaultdict(list)
for deck in owned_decks:
    if deck.parent_id is not None and int(deck.parent_id) != int(deck.id): # Ngắt self-loop
        children_by_parent[int(deck.parent_id)].append(int(deck.id))

def compute_safe_subtree_ids(root_id: int) -> set[int]:
    """BFS in-memory duyệt cây con với cơ chế chống chu trình tuyệt đối."""
    subtree: set[int] = {root_id}
    queue: list[int] = [root_id]
    while queue:
        curr = queue.pop(0)
        for child_id in children_by_parent.get(curr, []):
            if child_id not in subtree:
                subtree.add(child_id)
                queue.append(child_id)
    return subtree

# Tiền tính toán một lần duy nhất cho toàn bộ decks trong RAM:
subtree_ids_by_deck: dict[int, set[int]] = {
    int(deck.id): compute_safe_subtree_ids(int(deck.id))
    for deck in owned_decks
}
```

Tập `subtree_ids_by_deck` này được tái sử dụng xuyên suốt cho cả 3 tác vụ:
1. Tính cộng dồn `card_count`.
2. Gom Note Types trong cây con để suy diễn Note Type.
3. Lấy tập hợp `descendant_ids = subtree_ids_by_deck[d_id] - {d_id}` để kiểm tra xung đột chia sẻ.

-> **0 câu lệnh SQL cho việc duyệt cây con, thời gian tính toán < 0.2ms cho toàn bộ 150 bộ thẻ!**

---

### Đề xuất 3: Gom truy vấn Note Type Provenance & Active Templates (Batching)

Thay vì trong mỗi lần lặp lại truy vấn database để tìm Note Type và kiểm tra Marketplace, ta thực thi 3 truy vấn hàng loạt trước vòng lặp:

```python
# 1. BATCH QUERY: Lấy Note Types được sử dụng bởi các bộ thẻ của người dùng
# SQL: SELECT Note.deck_id, Note.note_type_id FROM notes WHERE Note.user_id = :uid AND Note.deck_id IN (...)
deck_to_note_types: dict[int, set[str]] = (
    flashcards_share_repository.batch_get_deck_note_types(user_id=user_id, deck_ids=deck_ids)
)

# Thu thập tất cả các Note Type IDs đang xuất hiện
all_used_nt_ids: set[str] = {
    nt_id for nt_set in deck_to_note_types.values() for nt_id in nt_set
}

# 2. BATCH QUERY: Kiểm tra các Note Type nào là bản copy cài từ Marketplace
# SQL: SELECT installed_note_type_id FROM note_type_installs WHERE installed_note_type_id IN (...)
marketplace_installed_nt_ids: set[str] = (
    flashcards_share_repository.batch_get_installed_note_type_ids(all_used_nt_ids)
    if all_used_nt_ids else set()
)

# 3. BATCH QUERY: Kiểm tra các Note Type nào có Active Templates (kết hợp Template join để bảo đảm toàn vẹn)
# SQL: SELECT DISTINCT study_applications.note_type_id FROM study_applications 
#      JOIN templates ON study_applications.template_id = templates.id 
#      WHERE study_applications.note_type_id IN (...) AND study_applications.status_code = 'ACTIVE'
active_template_nt_ids: set[str] = (
    flashcards_share_repository.batch_get_active_template_note_type_ids(all_used_nt_ids)
    if all_used_nt_ids else set()
)
```

#### Chi tiết cài đặt tại `app/repositories/flashcards_share_repository.py`:
```python
from collections import defaultdict
from models import db
from models.flashcard import Note, Card
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.template import Template

def batch_get_deck_note_types(
    *,
    user_id: int,
    deck_ids: list[int],
) -> dict[int, set[str]]:
    if not deck_ids:
        return {}
    rows = (
        db.session.query(Note.deck_id, Note.note_type_id)
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(deck_ids),
        )
        .distinct()
        .all()
    )
    result: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        if row and row[0] is not None and row[1]:
            result[int(row[0])].add(str(row[1]))
    return dict(result)


def batch_get_installed_note_type_ids(note_type_ids: set[str]) -> set[str]:
    if not note_type_ids:
        return set()
    rows = (
        db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter(NoteTypeInstall.installed_note_type_id.in_(list(note_type_ids)))
        .all()
    )
    return {str(row[0]) for row in rows if row and row[0]}


def batch_get_active_template_note_type_ids(note_type_ids: set[str]) -> set[str]:
    if not note_type_ids:
        return set()
    rows = (
        db.session.query(StudyApplication.note_type_id)
        .join(Template, StudyApplication.template_id == Template.id)
        .filter(
            StudyApplication.note_type_id.in_(list(note_type_ids)),
            StudyApplication.status_code == "ACTIVE",
        )
        .distinct()
        .all()
    )
    return {str(row[0]) for row in rows if row and row[0]}
```

#### Suy diễn Note Type trong RAM cho từng bộ thẻ:
Với mỗi bộ thẻ `deck_id`, Note Types của toàn bộ cây con được lấy bằng phép hợp tập hợp:
```python
sub_ids = subtree_ids_by_deck[deck_id]
subtree_nt_ids = {nt for sid in sub_ids for nt in deck_to_note_types.get(sid, set())}

inferred_note_type_id = None
if len(subtree_nt_ids) == 1:
    candidate_nt_id = next(iter(subtree_nt_ids))
    # Khớp 100% logic với flashcards_share_service.py: Yêu cầu template phải ACTIVE
    if candidate_nt_id in active_template_nt_ids:
        inferred_note_type_id = candidate_nt_id
```

Kiểm tra Note Type từ Marketplace trong vòng lặp trở thành:
```python
if inferred_note_type_id and (inferred_note_type_id in marketplace_installed_nt_ids):
    # Trả về block_code = "marketplace_note_type"
```
-> **Thao tác kiểm tra Note Type đạt độ phức tạp $O(1)$ in-memory lookup!**

#### Toàn văn cài đặt Tương thích ngược của `get_deck_publish_eligibility` (Hybrid Context Implementation):
Bảo toàn 100% tính tương thích ngược cho cả lời gọi batch từ `build_deck_publish_options` và lời gọi đơn lẻ từ các consumer bên ngoài:

```python
def get_deck_publish_eligibility(
    *,
    user_id: int,
    deck: Deck,
    allow_existing: bool = False,
    context: tuple[dict[int, Deck], set[int], dict[int, DeckMarketplaceItem]] | None = None,
    batch_context: DeckPublishBatchContext | None = None,
) -> dict[str, Any]:
    if deck.deleted_at is not None or deck.owner_user_id != user_id:
        return {
            "is_selectable": False,
            "block_code": "not_owned",
            "block_reason": "Chỉ có thể chia sẻ bộ thẻ do bạn tự tạo hoặc đồng bộ từ Anki.",
            "shared_item_id": None,
        }

    deck_by_id, installed_scope_ids, shared_by_source = context or _deck_publish_context(
        user_id=user_id
    )
    deck_id = int(deck.id)

    if deck_id in installed_scope_ids:
        return {
            "is_selectable": False,
            "block_code": "marketplace_clone",
            "block_reason": "Bộ thẻ được cài từ Marketplace không thể chia sẻ lại.",
            "shared_item_id": None,
        }

    # =========================================================================
    # NHÁNH 1: BATCH IN-MEMORY RESOLUTION (O(1) RAM - không sinh SQL)
    # =========================================================================
    if batch_context is not None:
        sub_ids = batch_context.subtree_ids_by_deck.get(deck_id, {deck_id})
        subtree_nt_ids = {
            nt for sid in sub_ids for nt in batch_context.deck_to_note_types.get(sid, set())
        }
        inferred_note_type_id = None
        if len(subtree_nt_ids) == 1:
            candidate_nt_id = next(iter(subtree_nt_ids))
            if candidate_nt_id in batch_context.active_template_nt_ids:
                inferred_note_type_id = candidate_nt_id

        if inferred_note_type_id and (inferred_note_type_id in batch_context.marketplace_installed_nt_ids):
            return {
                "is_selectable": False,
                "block_code": "marketplace_note_type",
                "block_reason": "Bộ thẻ dùng Note Type cài từ Marketplace nên không thể chia sẻ lại.",
                "shared_item_id": None,
            }
        descendant_ids = sub_ids - {deck_id}

    # =========================================================================
    # NHÁNH 2: STANDALONE FALLBACK RESOLUTION (Bảo toàn 100% hợp đồng gọi đơn lẻ)
    # =========================================================================
    else:
        inferred_note_type_id, _ = resolve_single_note_type_for_deck(
            deck_id=deck_id,
            owner_user_id=user_id,
        )
        if inferred_note_type_id and is_installed_note_type_copy(inferred_note_type_id):
            return {
                "is_selectable": False,
                "block_code": "marketplace_note_type",
                "block_reason": "Bộ thẻ dùng Note Type cài từ Marketplace nên không thể chia sẻ lại.",
                "shared_item_id": None,
            }
        descendant_ids = set(collect_subtree_ids(deck_id)) - {deck_id}

    existing_item = shared_by_source.get(deck_id)
    if existing_item is not None and not allow_existing:
        return {
            "is_selectable": False,
            "block_code": "already_shared",
            "block_reason": "Bộ thẻ này đã được chia sẻ và không thể chia sẻ lại.",
            "shared_item_id": existing_item.id,
        }

    descendant_items = [
        (d_id, shared_by_source[d_id])
        for d_id in sorted(descendant_ids)
        if d_id in shared_by_source
    ]
    if descendant_items:
        descendant_id, descendant_item = descendant_items[0]
        descendant_deck = deck_by_id.get(descendant_id)
        descendant_name = (
            descendant_deck.name if descendant_deck is not None else str(descendant_id)
        )
        return {
            "is_selectable": False,
            "block_code": "descendant_shared",
            "block_reason": f"Không thể chia sẻ bộ cha vì bộ con '{descendant_name}' đã được chia sẻ.",
            "shared_item_id": descendant_item.id,
        }

    seen: set[int] = set()
    parent_id = deck.parent_id
    while parent_id is not None and int(parent_id) not in seen:
        current_parent_id = int(parent_id)
        seen.add(current_parent_id)
        parent_item = shared_by_source.get(current_parent_id)
        if parent_item is not None:
            parent_deck = deck_by_id.get(current_parent_id)
            parent_name = parent_deck.name if parent_deck is not None else str(current_parent_id)
            return {
                "is_selectable": False,
                "block_code": "ancestor_shared",
                "block_reason": f"Không thể chia sẻ bộ con vì bộ cha '{parent_name}' đã được chia sẻ.",
                "shared_item_id": parent_item.id,
            }
        parent_deck = deck_by_id.get(current_parent_id)
        if parent_deck is None:
            break
        parent_id = parent_deck.parent_id

    return {
        "is_selectable": True,
        "block_code": None,
        "block_reason": None,
        "shared_item_id": existing_item.id if existing_item is not None else None,
    }
```

---

### Đề xuất 4: Xử lý xung đột phả hệ (Hierarchy Conflict Verification) & Ca biên Phức hợp

#### 1. Kiểm tra bộ con đã chia sẻ (`descendant_shared`):
Với `subtree_ids_by_deck` đã có sẵn trong RAM:
```python
descendant_ids = subtree_ids_by_deck[deck_id] - {deck_id}
descendant_items = [
    (d_id, shared_by_source[d_id])
    for d_id in sorted(descendant_ids)
    if d_id in shared_by_source
]
if descendant_items:
    descendant_id, descendant_item = descendant_items[0]
    descendant_deck = deck_by_id.get(descendant_id)
    descendant_name = descendant_deck.name if descendant_deck else str(descendant_id)
    return {
        "is_selectable": False,
        "block_code": "descendant_shared",
        "block_reason": f"Không thể chia sẻ bộ cha vì bộ con '{descendant_name}' đã được chia sẻ.",
        "shared_item_id": descendant_item.id,
    }
```

#### 2. Kiểm tra bộ cha đã chia sẻ (`ancestor_shared`):
Duyệt ngược từ con lên cha trong RAM với `seen: set[int]` để bảo vệ trước chu trình cha-con:
```python
seen_ancestors: set[int] = set()
parent_id = deck.parent_id
while parent_id is not None and int(parent_id) not in seen_ancestors:
    curr_parent_id = int(parent_id)
    seen_ancestors.add(curr_parent_id)
    parent_item = shared_by_source.get(curr_parent_id)
    if parent_item is not None:
        parent_deck = deck_by_id.get(curr_parent_id)
        parent_name = parent_deck.name if parent_deck else str(curr_parent_id)
        return {
            "is_selectable": False,
            "block_code": "ancestor_shared",
            "block_reason": f"Không thể chia sẻ bộ con vì bộ cha '{parent_name}' đã được chia sẻ.",
            "shared_item_id": parent_item.id,
        }
    parent_deck = deck_by_id.get(curr_parent_id)
    if parent_deck is None:
        break
    parent_id = parent_deck.parent_id
```

---

### 5.5. Phân tích & Kiểm chứng các Ca biên Phức hợp (Edge Cases Matrix)

| Tình huống biên | Hành vi Hiện tại (As-Is) | Hành vi Đề xuất (To-Be) | Đánh giá Tính nhất quán & An toàn |
| :--- | :--- | :--- | :--- |
| **1. Cây có bộ con rỗng xen kẽ** (Folder decks 0 cards ở giữa) | - `card_count` cộng dồn thẻ các nhánh con bên dưới.<br>- Nếu toàn bộ cây con không có thẻ nào: `card_count = 0`, `inferred_note_type = None`, `is_selectable = True` (chặn khi bấm nút Publish). | - Post-order roll-up cộng chính xác số thẻ các bộ con.<br>- Nếu không có thẻ: `card_count = 0`, `is_selectable = True`. | **Đồng nhất 100%**. Giao diện React hiển thị đúng trạng thái rỗng và không sinh lỗi `KeyError`. |
| **2. Cây lai ghép** (Bộ thẻ tự tạo chứa bộ thẻ cài từ Marketplace hoặc ngược lại) | - Bộ thẻ cài nằm trong `installed_scope_ids` bị chặn `marketplace_clone`.<br>- Bộ thẻ con tạo dưới bộ cài dùng Note Type Marketplace bị chặn `marketplace_note_type`.<br>- `build_browse_decks` quét thêm thẻ overlay qua `DeckInstall`/`DeckCloneDeckMap`. | - `installed_scope_ids` vẫn chặn `marketplace_clone`.<br>- Batch provenance check phát hiện Note Type nằm trong `marketplace_installed_nt_ids` và chặn `marketplace_note_type`.<br>- `batch_get_cards_count_by_deck_ids` đếm chuẩn xác thẻ thuộc quyền sở hữu (`Note.user_id == user_id`). Bộ cài trả về `card_count = 0`, Frontend ẩn badge số thẻ tự nhiên (`card_count > 0`) và gắn badge khóa "Từ Marketplace". *(Ghi chú kiến trúc: Nếu sản phẩm yêu cầu hiển thị số thẻ của bộ cài, có thể bổ sung 1 query gom nhóm phụ trên `DeckInstall` mà không phá vỡ độ phức tạp $O(1)$).* | **Bảo toàn 100% mô hình Overlay-only**. Không cho phép re-publish nội dung có nguồn gốc Marketplace. |
| **3. Cây bị chu trình khép kín** ($A \to B \to A$ do lỗi Anki sync) | - Duyệt ancestor có `seen: set[int]`.<br>- Nhưng `collect_subtree_ids` bắn SQL liên tục vào DB. | - `compute_safe_subtree_ids` dùng `seen: set[int]` ngắt chu trình ngay tại RAM.<br>- Ngăn chặn hoàn toàn `RecursionError`. | **Kháng lỗi vượt trội**. Hệ thống không bị crash HTTP 500 khi gặp dữ liệu Anki đồng bộ lỗi. |
| **4. Bộ thẻ có nhiều Note Types khác nhau trong các bộ con** | - `len(note_type_ids) > 1` $\to$ không suy diễn được Note Type duy nhất $\to$ `is_selectable = True` ở options, chặn khi publish. | - `len(subtree_nt_ids) > 1` $\to$ `inferred_note_type_id = None`. | **Đồng nhất 100%**. Giữ nguyên hợp đồng kiểm tra tính hợp lệ. |

---

### 5.6. Đối chiếu Hợp đồng Giao diện Frontend (Frontend SPA Contract & Component Alignment)

Giao diện SPA tại `frontend/src/features/marketplace/` tiêu thụ trực tiếp kết quả từ `GET /api/shared/decks/publish-options`. Để bảo đảm nguyên tắc **Zero Visual & Behavioral Regression**, giải pháp tối ưu đã được kiểm chứng đối sánh 100% với các định nghĩa và component frontend:

#### 1. Đối chiếu Kiểu dữ liệu TypeScript (`publishApi.ts`):
Hợp đồng dữ liệu `PublishDeckOption` quy định 8 trường thuộc tính bắt buộc:
```typescript
export type PublishDeckOption = {
  id: number
  name: string
  parent_id: number | null
  card_count: number
  is_selectable: boolean
  block_code: 'marketplace_clone' | 'marketplace_note_type' | 'already_shared' | 'ancestor_shared' | 'descendant_shared' | 'not_owned' | null
  block_reason: string | null
  shared_item_id: string | null
}
```
Backend sau tối ưu bảo toàn chính xác tên, kiểu và ngữ nghĩa của tất cả 8 trường này.

#### 2. Đối chiếu Component cây phân cấp (`PublishDeckTree.tsx`):
- **Cấu trúc cây (`buildPublishDeckTree`)**:
  Frontend chuyển đổi mảng phẳng `decks: PublishDeckOption[]` thành cấu trúc cây lồng nhau (`children: PublishDeckTreeNode[]`) dựa trên `deck.parent_id`. Trường hợp bộ cha bị xóa hoặc không thuộc quyền sở hữu (`parent == null`), node tự động trở thành root của cây mà không làm sập giao diện.
- **Sắp xếp hiển thị**:
  Cây được sắp xếp tự động theo tên bộ thẻ với bảng mã tiếng Việt (`localeCompare(..., 'vi')`), độc lập với thứ tự trả về của SQL.
- **Huy hiệu Số lượng thẻ (`card_count`)**:
  Render badge thẻ khi `card_count > 0`. Đối với các thư mục rỗng (`card_count === 0`), badge được ẩn tự nhiên.
- **Huy hiệu Khóa & Nhãn trạng thái (`blockLabel`)**:
  Tất cả 6 mã lỗi chặn (`block_code`) được map chính xác với nhãn giao diện và icon ổ khóa (`LockKeyhole`):
  - `marketplace_clone`: "Từ Marketplace" (Khóa chọn, vô hiệu hóa click)
  - `marketplace_note_type`: "Dùng Note Type Marketplace" (Khóa chọn)
  - `already_shared`: "Đã chia sẻ" (Khóa chọn)
  - `ancestor_shared`: "Bộ cha đã chia sẻ" (Khóa chọn)
  - `descendant_shared`: "Bộ con đã chia sẻ" (Khóa chọn)
  - `not_owned`: "Không thuộc sở hữu" (Khóa chọn)
- **Hỗ trợ tìm kiếm (`filteredDeckIds`)**:
  Tìm kiếm theo tên bộ thẻ và lý do chặn (`block_reason`), tự động mở rộng toàn bộ nhánh cha liên quan.

#### 3. Bổ khuyết khoảng trống kiểm thử Backend (Test Coverage Gap):
Kiểm tra test suites hiện hữu cho thấy mã lỗi `descendant_shared` đã có unit test trên frontend (`PublishDeckTree.test.tsx`), nhưng **chưa từng có integration test nào ở tầng Backend** trong `tests/`. Do đó, kế hoạch kiểm thử ở Giai đoạn 3 bắt buộc phải bổ sung ca kiểm thử backend này.

---

## 6. Implementation Roadmap (Lộ trình triển khai tối ưu hóa & Kế hoạch kiểm thử)

Kế hoạch triển khai được phân chia thành 3 giai đoạn chặt chẽ, bảo đảm không gây gián đoạn hệ thống và duy trì nguyên tắc Zero Regression:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   LỘ TRÌNH TRIỂN KHAI TỐI ƯU HÓA                       │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 1: BỔ SUNG BATCH REPOSITORY METHODS & UNIT TESTS             │
│ Tập tin: app/repositories/flashcards_share_repository.py               │
│ - batch_get_cards_count_by_deck_ids(user_id, deck_ids)                 │
│ - batch_get_deck_note_types(user_id, deck_ids)                         │
│ - batch_get_installed_note_type_ids(note_type_ids)                     │
│ - batch_get_active_template_note_type_ids(note_type_ids)               │
│ - Viết Unit test trong tests/test_flashcards_share_repository.py       │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 2: REFACTOR SERVICE LAYER & ĐỒNG BỘ KIẾN TRÚC SONG HÀNH      │
│ Tập tin:                                                               │
│ 1. app/services/flashcards_share_service.py (Active runtime)           │
│ 2. app/services/share/publish.py (Modular package target)              │
│ - Loại bỏ 100% lời gọi browse_card_service.build_browse_decks          │
│ - Triển khai in-memory tree index & cycle-safe subtree collector       │
│ - Tích hợp batch note type provenance và active template checking      │
│ - Bảo toàn chữ ký tương thích ngược của get_deck_publish_eligibility   │
│ - Bảo đảm 100% tính đồng nhất về hợp đồng JSON payload                 │
└────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 3: KIỂM THỬ HỒI QUY TOÀN DIỆN & QUERY COUNT BENCHMARK        │
│ - Chạy test suites hiện hữu (Flashcards, Marketplace, Study)           │
│ - Bổ sung integration test cho descendant_shared ở Backend             │
│ - Xây dựng bài kiểm thử tự động đếm câu truy vấn (Query Counter Test): │
│   Khẳng định số query <= 9 với tài khoản có 50+ bộ thẻ                │
│ - Đo lường độ trễ phản hồi qua curl/Postman trên môi trường staging    │
└────────────────────────────────────────────────────────────────────────┘
```

### Chi tiết các bước thực hiện:

#### Bước 1: Bổ sung 4 phương thức truy vấn Batch tại Repository
Tập tin: `app/repositories/flashcards_share_repository.py`
1. `batch_get_cards_count_by_deck_ids(user_id: int, deck_ids: list[int]) -> dict[int, int]`
2. `batch_get_deck_note_types(user_id: int, deck_ids: list[int]) -> dict[int, set[str]]`
3. `batch_get_installed_note_type_ids(note_type_ids: set[str]) -> set[str]`
4. `batch_get_active_template_note_type_ids(note_type_ids: set[str]) -> set[str]`

#### Bước 2: Tái cấu trúc logic Service & Đồng bộ song song
Tập tin: `app/services/flashcards_share_service.py` và `app/services/share/publish.py`
- Thay thế hoàn toàn phần đếm thẻ trong `build_deck_publish_options`: nạp `direct_counts` qua hàm batch, sau đó roll-up in-memory.
- Gom dữ liệu Note Types và kiểm tra điều kiện xuất bản trong `get_deck_publish_eligibility` bằng các tập hợp in-memory.
- Hỗ trợ cả hai chế độ gọi: truyền `batch_context` (chạy $O(1)$) hoặc gọi đơn lẻ (`batch_context=None`, fallback an toàn).
- Giữ nguyên vẹn 100% cấu trúc JSON:
  ```json
  {
    "items": [
      {
        "id": 101,
        "name": "JLPT N5 Vocabulary",
        "parent_id": null,
        "card_count": 120,
        "is_selectable": true,
        "block_code": null,
        "block_reason": null,
        "shared_item_id": null
      }
    ]
  }
  ```

#### Bước 3: Kiểm thử hồi quy, Bổ sung ca biên Backend và Khẳng định số lượng truy vấn
1. **Bài test kiểm tra chặn bộ cha khi bộ con đã chia sẻ (`descendant_shared`)**:
   Bổ sung test case vào `tests/test_flashcard_api_integration.py`:
   ```python
   def test_shared_deck_publish_options_blocks_parent_when_child_is_shared(self):
       with self.app.app_context():
           parent_deck = Deck(name="Root Parent Deck", owner_user_id=self.user_id)
           db.session.add(parent_deck)
           db.session.flush()
           child_deck = Deck(name="Active Child Deck", owner_user_id=self.user_id, parent_id=parent_deck.id)
           db.session.add(child_deck)
           db.session.flush()
           shared_child = DeckMarketplaceItem(
               owner_user_id=self.user_id,
               source_deck_id=child_deck.id,
               title="Child Shared Listing",
               publish_status="published",
           )
           db.session.add(shared_child)
           db.session.commit()
           parent_deck_id = parent_deck.id

       response = self.client.get("/api/shared/decks/publish-options")
       self.assertEqual(response.status_code, 200)
       options = {row["id"]: row for row in response.get_json()["items"]}
       self.assertFalse(options[parent_deck_id]["is_selectable"])
       self.assertEqual(options[parent_deck_id]["block_code"], "descendant_shared")
       self.assertIn("Active Child Deck", options[parent_deck_id]["block_reason"])
   ```

2. **Bài test đo đếm câu lệnh SQL (Query Count Benchmark Assertion)**:
   Xây dựng integration test sử dụng SQLAlchemy event listener `before_cursor_execute`:
   ```python
   def test_publish_options_query_count_benchmark(self):
       # Tạo cây 50 bộ thẻ phân cấp 2 tầng
       queries = []
       def record_query(conn, cursor, statement, parameters, context, executemany):
           queries.append(statement)

       from sqlalchemy import event
       event.listen(db.engine, "before_cursor_execute", record_query)
       try:
           response = self.client.get("/api/shared/decks/publish-options")
           self.assertEqual(response.status_code, 200)
           # Khẳng định số lượng query là hằng số O(1), không vượt quá 9 câu lệnh
           self.assertLessEqual(len(queries), 9)
       finally:
           event.remove(db.engine, "before_cursor_execute", record_query)
   ```

---

## 7. Verification Record & Shallow Verification Disclosures

### 7.1. Hồ sơ kiểm thử thực tế (Deep Verification Record)
Đã chạy kiểm thử trực tiếp trên môi trường máy ảo dự án (`.venv` Python 3.12.6, Vitest v4.1.10):

1. **Flashcards Backend Module & Frontend Tests**:
   - Lệnh thực thi: `.\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards`
   - Kết quả: **24 test suites backend (318 tests) PASS 100%** (107.89s).
   - Frontend: **2 suites (9 tests) PASS 100%** (3.69s).
2. **Marketplace Backend Module & Frontend Tests**:
   - Lệnh thực thi: `.\.venv\Scripts\python.exe scripts/run_tests.py --module marketplace`
   - Kết quả: **6 test suites backend (34 tests) PASS 100%** (15.93s).
   - Frontend: **3 suites (8 tests) PASS 100%** bao gồm `PublishDeckTree.test.tsx` (3.46s).

### 7.2. Minh bạch về các khía cạnh chưa kiểm thử thực tế (Shallow Verification Disclosures)
- **Mô hình hóa RTT & IOPS trên Production**: Các con số độ trễ 1.5ms – 3.5ms và mức suy giảm IOPS được tính toán dựa trên mô hình lý thuyết mạng TCP cục bộ giữa ứng dụng và máy chủ MySQL. Hệ thống chưa được đo lường trực tiếp qua công cụ APM (Application Performance Monitoring) như New Relic hay Datadog trên môi trường production có tải truy cập đồng thời cao.
- **Dữ liệu lớn trên MySQL thực tế**: Các bài kiểm thử hiện tại chạy trên cơ sở dữ liệu test SQLite in-memory / MySQL dev với hàng trăm bộ thẻ. Việc kiểm thử hiệu năng đối với cơ sở dữ liệu có hàng trăm nghìn dòng `card_progress` cần được thực hiện trong giai đoạn Staging Verification của Phase 3.

---

## 8. Kết luận (Conclusion)

Báo cáo điều tra kỹ thuật đã làm sáng tỏ toàn diện cơ chế gây trễ nghiêm trọng tại màn hình Đăng học liệu: sự kết hợp tai hại giữa việc lạm dụng module tính lịch học (`build_browse_decks`) và bùng nổ truy vấn $N+1$ đệ quy nhiều tầng trong vòng lặp kiểm tra tính hợp lệ.

Bằng việc chuyển đổi từ mô hình truy vấn phân tán $O(N \cdot H)$ sang mô hình nạp dữ liệu hàng loạt kết hợp xử lý đồ thị cây an toàn trong bộ nhớ RAM $O(1)$, số lượng truy vấn cơ sở dữ liệu sẽ giảm hơn **98%** (từ 416+ câu lệnh xuống 8 câu lệnh), đưa độ trễ từ **nhiều giây xuống dưới 50 milliseconds**, bảo vệ 100% mô hình Overlay của Flama và mang lại trải nghiệm mượt mà tức thì cho người dùng.
