# Kế hoạch xử lý latency màn đăng học liệu — 2026-10-09

Trạng thái: đã đo baseline MySQL local và thử biến thể SQL chỉ đọc; chưa sửa implementation của endpoint. Phạm vi: `GET /api/shared/decks/publish-options`, hai service publish và repository liên quan.

## 1. Kết quả đo trên bản dump local

MySQL **8.0.40**, database `nihongo` trên `localhost:3306`, InnoDB buffer pool **128 MiB**. Toàn DB có **41.486 notes / 41.486 cards**. Đo HTTP thật qua loopback bằng WSGI server riêng chạy working copy hiện tại; cùng factory/config và blueprint của ứng dụng, nhưng bỏ startup maintenance. Chưa phải benchmark Gunicorn production hay UI browser.

Mỗi tài khoản có 3 request warm-up và 30 request đo. p95 dùng nearest rank. Lượt cuối:

| Tài khoản | Deck chưa xóa | Thẻ sở hữu | Độ sâu tối đa (số node) | HTTP median / p95 | Service median | SQL cursor median | SQL/request | Peak Python allocations của service |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.528 | 39.325 | 5 | **480,2 / 566,3 ms** | 460,1 ms | 413,2 ms | 8 | 3,99 MiB |
| 4 | 1.852 | 2.108 | 4 | **127,2 / 213,3 ms** | 106,9 ms | 68,3 ms | 9 | 3,44 MiB |
| 15 | 224 | 0 | 3 | **37,0 / 50,4 ms** | 19,9 ms | 13,0 ms | 7 | 0,42 MiB |

Lượt trước cho tài khoản 1 là 497,4 / 653,0 ms, tài khoản 4 là 137,5 / 238,1 ms. Có biến động CPU/GC/tải nền; không chọn một request nhanh nhất để làm baseline. JSON lưu lượt cuối và toàn bộ 30 samples/tài khoản.

- HTTP gồm authentication, service, JSON và truyền response local; SQL cursor gồm execution và fetch của PyMySQL. Các median đo riêng không phải các thành phần có thể cộng/trừ chính xác.
- `tracemalloc` chỉ bật trong lượt đo allocations riêng; không bật trong mẫu latency. Đây là Python allocations, không phải toàn bộ RSS của process.
- Mọi connection của benchmark dùng MySQL `TRANSACTION READ ONLY`; SQL ngoài `SELECT`/`SHOW`/`EXPLAIN` bị từ chối. Không login, tạo fixture, sửa schema hay ghi dữ liệu ứng dụng.
- Payload ổn định qua các mẫu; monolith và `share/publish.py` cho payload bằng nhau. Hash source xác nhận bốn file implementation không đổi trong lúc đo.
- Request đầu từng tài khoản được ghi riêng. Không gọi đó là cold-cache: benchmark không restart MySQL hoặc xóa buffer pool.

Artifacts:

- [Script đo và thử SQL](../../../scripts/bench_publish_options_mysql.py).
- [Baseline HTTP, samples, query profiles và EXPLAIN JSON](../../../output/publish_options_mysql_20261009.json).
- [Biến thể SQL, parity và EXPLAIN ANALYZE](../../../output/publish_options_sql_variants_20261009.json).

`output/` được gitignore; các artifact này có trên workspace local. Bản dump tương đương về dữ liệu không bảo đảm latency production giống local: CPU, buffer pool, mạng và concurrency còn khác. Mốc 30–80 ms trong [báo cáo Gemini](../../investigations/PUBLISH_DECK_LOAD_PERFORMANCE_REPORT.md) chưa đạt trên hai tài khoản lớn đã đo.

## 2. Hai vấn đề cần xử lý

### A. Quét notes hai lần là điểm nghẽn đang quan sát

- **Observed:** tài khoản 1 dành khoảng 413 ms median ở SQL cursor, so với service khoảng 460 ms. Hai query chính là `COUNT(cards.id) GROUP BY notes.deck_id` và `DISTINCT(notes.deck_id, notes.note_type_id)`.
- **Evidence:** query profile trong baseline; `batch_get_cards_count_by_deck_ids` và `batch_get_deck_note_types` ở `app/repositories/flashcards_share_repository.py`. `EXPLAIN ANALYZE` xác nhận đọc 39.325 notes; count lookup cards theo từng note. Các plan hiện dùng `ix_notes_user_id` và `ix_cards_note_id`.
- **Potential concern:** số SQL hằng số không làm chi phí quét dữ liệu hằng số. Cùng tập notes đang được đọc lại cho hai dữ liệu của một response.
- **Impact:** tài khoản nhiều notes vẫn khoảng nửa giây/request trên local dù N+1 đã được loại bỏ.
- **Unknowns:** tác động trên production và khi cạnh tranh buffer pool; chưa có phép đo chứng minh cần thêm index.

Đã thử 6 query shapes trên tài khoản 1, 2 warm-up + 15 samples/biến thể, đổi thứ tự mỗi vòng để giảm lệch do cache:

| Query shape | Median | Kết quả so với baseline |
|---|---:|---|
| Đếm thẻ hiện tại | 225,0 ms | Baseline |
| Note Type hiện tại | 119,3 ms | Baseline |
| Gộp theo `(deck_id, note_type_id)`, giữ `IN(deck_ids)` | **259,2 ms** | Counts và tập Note Type bằng baseline |
| Gộp nhưng thêm `JOIN decks` để lọc scope | 305,4 ms | Bằng baseline; chậm hơn phương án giữ `IN` |
| Count riêng với `JOIN decks` | 266,7 ms | Bằng baseline |
| Note Type riêng với `JOIN decks` | 163,7 ms | Bằng baseline |

259,2 ms so với tổng median 344,3 ms của hai query riêng tương ứng khoảng 25% giảm chi phí query, chưa phải mức cải thiện HTTP đã triển khai.

### B. Index cây lưu mọi tập descendant làm bộ nhớ tăng bậc hai

- **Observed:** `build_deck_publish_options` chạy BFS cho từng deck rồi giữ tất cả `subtree_ids_by_deck`; sau đó còn duyệt các tập đó để sum counts, merge Note Type và tìm descendant shared.
- **Evidence:** `app/services/flashcards_share_service.py:657` và `app/services/share/publish.py:301`. Probe pure Python của review trước đạt 128,7 MiB allocations với chuỗi 2.000 deck, đã mock DB.
- **Potential concern:** cây dạng chuỗi giữ `D(D+1)/2` ID entries. Chống cycle chỉ bảo đảm kết thúc, không bảo đảm bộ nhớ tuyến tính.
- **Impact:** có thể nghẽn CPU/RAM khi cây sâu; benchmark SQL count với 50 deck hai tầng không bắt được.
- **Unknowns:** chưa gặp cây sâu trong bản dump này. Tài khoản 1/4 chỉ có khoảng 6.759/6.797 subtree entries và depth 5/4; đây là hardening cần làm, không phải nguyên nhân chính của latency thực tế vừa đo.

## 3. Các bước triển khai

### Bước 1 — Gộp đọc counts và Note Type, chưa thêm index

Thêm một repository helper trả `direct_card_counts` và `deck_to_note_types` bằng một query:

```sql
SELECT n.deck_id, n.note_type_id, COUNT(c.id)
FROM notes AS n
LEFT JOIN cards AS c ON c.note_id = n.id
WHERE n.user_id = :user_id AND n.deck_id IN (:visible_owned_deck_ids)
GROUP BY n.deck_id, n.note_type_id;
```

SQL trên biểu diễn shape; dùng SQLAlchemy bind parameters cho danh sách IDs, không ghép giá trị vào chuỗi SQL.

- `LEFT JOIN` giữ Note Type của notes chưa có Card; không dùng `COUNT(notes.id)` hoặc giả định một note chỉ có một card.
- Cộng count qua các Note Type để lấy count trực tiếp của deck; giữ Note Type kể cả row có count 0.
- Giữ filter user và tập deck của context hiện tại; không mở rộng sang nguồn overlay hoặc deck đã xóa.
- Hai service dùng helper mới. Giữ các helper cũ nếu còn caller; tránh refactor các flow install/import/template đang được sửa ở working tree.
- Đo lại cả tài khoản 4 và 15: biến thể mới chỉ mới được đối chiếu SQL trực tiếp trên tài khoản 1.

### Bước 2 — Đổi index cây sang summary có kích thước tuyến tính

Đặt thuật toán pure Python dùng chung trong `app/services/deck_publish_index.py`, không phụ thuộc request/session. Hai service publish gọi cùng helper để tránh drift.

Mỗi deck chỉ cần summary:

1. Tổng card count của scope reachable, mỗi deck đóng góp một lần.
2. Trạng thái Note Type `EMPTY`, `SINGLE(id)` hoặc `MIXED`; không sao chép toàn bộ tập Note Type lên từng ancestor.
3. Deck shared có ID nhỏ nhất trong descendants, để giữ nguyên cách chọn lý do chặn.
4. Ancestor shared gần nhất theo thứ tự duyệt parent, không chọn theo ID nhỏ nhất.

Xử lý bằng post-order **iterative**, tổng hợp từ dưới lên và memo từ trên xuống. Không BFS cho mỗi root, không giữ descendant sets, không recursion phụ thuộc độ sâu.

Với cycle/self-loop, nhận diện và gom component của đồ thị parent bằng thuật toán iterative trước khi roll-up. Không cộng trùng deck trong component; lưu hai shared deck IDs nhỏ nhất để loại trừ chính deck đang xét. Nearest-ancestor lookup phải loại chính deck khi đi vòng cycle, như `seen = {deck_id}` hiện tại. Mục tiêu CPU/RAM `O(D + K)`, với K là số cặp `(deck_id, note_type_id)` đầu vào.

Giữ chữ ký và nhánh standalone của `get_deck_publish_eligibility`. Giữ thứ tự ưu tiên: `not_owned` → `marketplace_clone` → `marketplace_note_type` → `already_shared` → `descendant_shared` → `ancestor_shared`. Bảo toàn `allow_existing=True`, `block_reason`, `shared_item_id`, parent IDs, item order và JSON. Deck rỗng/mixed Note Type vẫn theo hành vi options hiện tại; validation khi đăng không đổi.

### Bước 3 — Kiểm chứng và đóng task

- So sánh exact JSON và SHA-256 trước/sau trên cả ba tài khoản dump, cả hai service.
- Test repository: notes không có Card, nhiều Card/note, nhiều Note Type/deck, deck rỗng, user khác và deck đã xóa.
- Test cây: chain, wide tree, shared ancestor/descendant, chọn descendant ID nhỏ nhất, cycle/self-loop có và không có listing, `allow_existing`, dangling/cross-user parent. Đối chiếu oracle của implementation hiện tại trên fixture nhỏ.
- Giữ test SQL count 50 deck, thêm fixture 1.000+ deck. SQL/request không tăng theo số deck; phép gộp giảm một query trên scope không rỗng.
- Stress pure helper với 1.000/2.000/4.000 node, dạng chain và cycle. Tách latency và allocations; không dùng timing assertion dễ flaky trong CI. Kiểm tra mỗi node có bounded summary và không còn materialize mọi descendants.
- Chạy module flashcards/marketplace liên quan, không full suite. Chạy lại benchmark MySQL và frontend PublishDeckTree tests sau implementation.
- Nếu SQL vẫn chiếm phần lớn sau hai bước này, mở task riêng để thử covering index trên schema benchmark tách biệt. Chỉ chốt migration sau khi có before/after `EXPLAIN ANALYZE` và latency; không thêm index trên dump trong task lập kế hoạch này.

## 4. Tiêu chí nghiệm thu đề xuất

Đo trên cùng local dump/máy, 3 warm-up + 30 samples; nếu dao động lớn, chạy xen kẽ before/after và báo cả hai lượt.

- Tài khoản 1: warm HTTP median **≤400 ms**, p95 **≤550 ms**; đây là mục tiêu, chưa phải kết quả đã đạt.
- Tài khoản 4: median **≤150 ms**, p95 **≤250 ms**; tài khoản 15: **≤40 / 60 ms**.
- Payload giữ nguyên, 100% parity hai implementation; không ghi DB hoặc gọi scheduler/count tiến độ trong endpoint.
- SQL/request không N+1, tối đa 10 trên fixtures đã xét; gộp query giảm một roundtrip so với baseline tương ứng.
- Pure helper với chain 2.000 node: peak allocations **≤20 MiB**; tăng lên 4.000 node không vượt **2,5×**. Cycle không treo và counts không nhân đôi.

## 5. Lệnh tái đo và kiểm tra

```powershell
# HTTP/MySQL baseline hoặc kết quả sau sửa; không đụng app ở cổng 4789
.\.venv\Scripts\python.exe scripts/bench_publish_options_mysql.py --users 4 1 15 --warmups 3 --repetitions 30 --output output/publish_options_mysql_after.json

# Đối chiếu 6 query shapes, giữ dữ liệu nguyên vẹn
.\.venv\Scripts\python.exe scripts/bench_publish_options_mysql.py --users 1 --sql-variants-only --repetitions 15 --output output/publish_options_sql_variants_after.json

# Test nghiệp vụ sau implementation
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_flashcard_api_integration.py tests/test_flashcards_share_repository.py --backend-only
.\.venv\Scripts\python.exe scripts/run_tests.py --module marketplace --frontend-only
```

Các benchmark fail nếu env trỏ ra ngoài MySQL loopback. Baseline có hash source/payload để reviewer đối chiếu cùng version và cùng dữ liệu. Không reset cache server; không dùng số đo warm để khẳng định latency dưới tải production.

Triển khai thành hai thay đổi nhỏ: gộp query, rồi thay index cây kèm tests. Nếu cần rollback, revert phần optimization tương ứng và rerun parity; không có schema/data migration trong hai bước này.
