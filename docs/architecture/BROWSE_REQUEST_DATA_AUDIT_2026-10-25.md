# Browse: mỗi request lấy bao nhiêu dữ liệu, query chung hay riêng?

Ngày: 2026-10-25, Asia/Tokyo. Chế độ INVESTIGATE. Source: HEAD `16e82f3b` và working tree hiện có. Đã đo lại MySQL local; không sửa application code, schema, index hoặc dữ liệu.

## 1. Kết quả chính

**Sidebar, bảng từ và editor là các HTTP request riêng.** Mỗi request lại thực hiện nhiều SQL statements; request riêng không có nghĩa là chỉ đọc một bảng hoặc chỉ chạy một query.

- Sidebar trả toàn bộ deck được phép nhìn thấy, không phân trang deck. Nó không trả hoặc hydrate nội dung các Notes. Tuy vậy, nó vẫn đọc bảng `notes` để xác định metadata và aggregate counters của toàn scope.
- Bảng giữa trả tối đa `per_page` Note rows: mặc định 100, hoặc preference đã lưu; backend giới hạn 1–500. Nội dung được hydrate theo page IDs. SQL count/sort vẫn xét tập phù hợp lớn hơn trang.
- Editor gọi endpoint riêng cho đúng một Note khi người dùng chọn dòng hoặc mở bookmark Note. Không có active Note thì không có request detail.
- NoteType compact là một request metadata riêng, không tải các từ trong collection.

Hai tài khoản local được chọn để đo, không suy ra đây là phiên browser hiện đang đăng nhập của người dùng:

| Mẫu | Context dùng khi đo | Dữ liệu liên quan |
|---|---|---|
| A | `user_id=1`, admin theo role hiện có, `admin_mode=True` | 39.338 owned Notes, 1.534 owned live decks, 0 installs; list mặc định đo được total 39.338 |
| B | `user_id=20`, learner, `admin_mode=False` | 0 owned Notes, 290 owned live deck shells, 7 installs; list mặc định nhìn thấy total 14.835 |

Quan trọng: một số báo cáo cũ đo tài khoản 1 với `admin_mode=False`. Số SQL và nhánh scope của kết quả đó không được dùng thay cho context admin trong lần đo này.

## 2. Mỗi HTTP request đang lấy gì?

| Request | Từ/Notes trả về browser | Backend đọc gì? | Quan hệ với request khác |
|---|---:|---|---|
| `GET /api/browse/decks?view=notes` | **0 nội dung Note**; toàn bộ deck metadata + counters | Deck tree/scope, install maps, distinct deck/type metadata, progress integrity candidates, grouped counters trên Notes/progress | Request sidebar riêng; không chứa page items hoặc editor detail |
| `GET /api/browse/notes?view=rows&...&page=1&per_page=100` | **Tối đa 100 Note previews** | Scope/quyền; exact count; ordered page IDs; Note content hoặc release values cho page; schema, progress và overrides | Request list riêng; có đọc lại metadata deck cần cho scope |
| `GET /api/browse/notes/<id>?view=editor` | **1 Note**, full typed field values và schema | Một Note, field definitions, deck context, learner progress; clone thêm authorization/release/overrides | Request riêng khi có active Note; không trả lại sidebar hoặc cả trang list |
| `GET /api/note-types?compact=1` | **0 Notes**; metadata NoteTypes/fields | NoteTypes, installs và field definitions | Query riêng được preload khi mở Browse |

Mở Browse khi các query chưa có cache thường khởi động ba request dữ liệu độc lập: decks, list và compact NoteTypes. Nếu URL có active `note_id`/`card_id`, detail có thể được gọi thêm ngay. Bootstrap/session là request dùng chung khác, nằm ngoài số đo Browse này.

`useBrowseData()` khai báo ba query độc lập. `useBrowseEditor()` chỉ bật detail với `enabled: Boolean(activeCardId)`. Không có chuỗi frontend bắt buộc “đợi sidebar xong rồi mới gọi list”.

### Trong một request sidebar có query chung với từ không?

**Có truy cập cùng bảng `notes`, nhưng không SELECT toàn bộ nội dung từ.** Trace của mẫu A cho thấy:

1. SELECT 1.534 Deck rows: identity, parent, owner, name, description và metadata.
2. SELECT DISTINCT `(notes.deck_id, notes.note_type_id)`: trả 1.469 cặp metadata.
3. SELECT tên các NoteTypes liên quan.
4. Query integrity candidates của learner.
5. Aggregate `COUNT/SUM ... GROUP BY deck_id` trên Notes và progress: trả 1.469 dòng counters.

Tổng request A có 9 SQL statements, còn lại là authority/settings context. Không statement nào trả cột Note content JSON hoặc release checkpoint content. Một dòng counter có thể đại diện cho rất nhiều Notes; 1.469 grouped rows không có nghĩa là chỉ có 1.469 từ được DB xét.

Mẫu B còn phải resolve 7 installs, source/local deck mapping và release membership; request có 58 SQL statements, nhưng vẫn trả **0 Note content rows**. Aggregate trả 278 deck-counter rows rồi roll up vào 290 deck entries của response.

### Nội dung trong bảng và editor có được tải chung không?

**HTTP riêng, có một phần dữ liệu được đọc lại.** Với trang 100 Notes:

- Mẫu A: lấy 100 Note content JSON từ DB, dùng chúng để dựng các cột preview; browser chỉ nhận DTO preview/tags/status/deck, không nhận full field values của cả 100 Notes.
- Mẫu B: lấy metadata của 100 source Notes, không lấy live source field JSON cho list; lấy đúng 100 checkpoint content rows để dựng nội dung release đã cài.
- Khi bấm một dòng: editor tải lại Note đó cùng toàn bộ fields. Đây là một Note đã xuất hiện trong page, không phải thêm một từ mới trong collection.
- Hai editor samples đều có 16 field definitions và 16 field values. Editor response hiện có `row`, `note`, `fields`, `can_upload_media`; không có `media_assets`, template HTML/CSS hoặc file media trong đường đọc đã đo.
- Riêng editor clone B: query `load_note_reference()` tải một live Note row có JSON; sau đó đọc thêm một checkpoint của **cùng Note** để dựng pinned content. Đây là một phần đọc dư ở editor; không phải tải hai từ khác nhau hoặc toàn source collection. List clone đã tránh live JSON, detail loader chưa tránh phần đó.

## 3. Số đo từng request trên MySQL local

MySQL **8.0.40**, migration head **`20261024_000073`**. Mỗi case có một lượt khảo sát cấu trúc làm warmup, sau đó ba lượt đo nhẹ hơn; bảng dùng median của ba lượt sau. Mỗi lượt có app/request context và session mới. Tất cả 16 cases trả cùng payload hash qua bốn lượt của từng case.

KB bên dưới là 1.000 bytes. JSON là serialize UTF-8 theo cùng một cách, chưa nén; không phải HTTP transferred size. Thời gian là service + serialization trong Python, có SQL, không gồm HTTP/auth/JS/render browser.

| Request/case | Kết quả trả về | SQL/request | JSON chưa nén | Median service |
|---|---|---:|---:|---:|
| A sidebar | 1.534 decks, 0 Notes | 9 | 597,1 KB | 609,3 ms |
| A collection, 20/trang | 20/39.338 Notes | 27 | 4,7 KB | 609,6 ms |
| A collection, 100/trang | 100/39.338 Notes | 34 | 22,9 KB | 760,6 ms |
| A collection, 500/trang | 500/39.338 Notes | 39 | 114,5 KB | 1.033,1 ms |
| A selected deck, 20/trang | 20/118 Notes | 18 | 4,3 KB | 143,8 ms |
| A selected deck, 100/trang | 100/118 Notes | 18 | 21,0 KB | 125,1 ms |
| A editor | 1 Note / 16 fields | 16 | 2,9 KB | 23,3 ms |
| A compact NoteTypes | 6 types, 0 Notes | 3 | 16,2 KB | 10,1 ms |
| B sidebar | 290 decks, 0 Notes | 58 | 113,6 KB | 410,5 ms |
| B collection, 20/trang | 20/14.835 Notes | 88 | 4,5 KB | 904,6 ms |
| B collection, 100/trang | 100/14.835 Notes | 96 | 21,8 KB | 1.005,5 ms |
| B collection, 500/trang | 500/14.835 Notes | 104 | 103,6 KB | 1.402,7 ms |
| B selected deck, 20/trang | 20/118 Notes | 33 | 4,0 KB | 98,1 ms |
| B selected deck, 100/trang | 100/118 Notes | 33 | 19,7 KB | 144,8 ms |
| B editor | 1 Note / 16 fields | 35 | 2,9 KB | 73,3 ms |
| B compact NoteTypes | 3 types, 0 Notes | 3 | 10,1 KB | 9,1 ms |

Không suy ra quy luật “20 dòng luôn nhanh hơn 100”: mẫu A selected-20 chậm hơn selected-100 trong lượt đo này, chủ yếu dao động phase scope. Ba timing samples sau warmup không phải phân bố tải production.

## 4. DB trả về backend bao nhiêu dữ liệu?

Đây là lượng giá trị DBAPI buffered rows trả về Python trong một sample có instrumentation, không phải số rows MySQL scan/examine. Metadata/progress có thể đọc lại, nên tổng rows không phải số từ duy nhất.

| Case | Tổng rows DB trả về qua mọi SQL | Giá trị DB → Python ước lượng | Note live content rows | Checkpoint content rows |
|---|---:|---:|---:|---:|
| A sidebar | 4.480 | 179,9 KB | **0** | **0** |
| A collection 100 | 1.975 | 340,7 KB | 100 | 0 |
| A selected 20 | 1.655 | 151,8 KB | 20 | 0 |
| A editor | 44 | 5,1 KB | 1 | 0 |
| B sidebar | 1.754 | 117,6 KB | **0** | **0** |
| B collection 100 | 3.384 | 463,5 KB | 0 | 100 |
| B selected 20 | 248 | 48,4 KB | 0 | 20 |
| B editor | 182 | 18,8 KB | 1 | 1 |

Estimate bytes cộng độ dài UTF-8 của giá trị cell, không gồm MySQL protocol overhead. Instrumentation không fetch thêm hoặc thay đổi rows; đọc buffered PyMySQL `_rows`. Tổng bytes gồm metadata/schema/state, không chỉ content JSON. Không dùng tỷ lệ DB bytes/JSON bytes làm tỷ lệ CPU hoặc tốc độ.

## 5. Cách tách hiện tại ảnh hưởng hiệu năng ra sao?

### F1 — Request độc lập cho phép cache và tải từng phần

- **Observed:** Đổi page/filter/sort/page size thay key của list; không thay key sidebar hoặc compact NoteTypes. Chọn Note đổi detail key; có thể dùng lại cache riêng của Note đó.
- **Evidence:** [useBrowseData.ts](../../frontend/src/features/browse/hooks/useBrowseData.ts), [useBrowseEditor.ts](../../frontend/src/features/browse/hooks/useBrowseEditor.ts), [main.tsx](../../frontend/src/main.tsx).
- **Potential concern:** Cold open vẫn có ba request và mỗi request tạo lại context riêng; số request ít hơn chưa tự động giảm DB work.
- **Impact:** Chuyển trang thông thường không phải tải lại 597 KB/114 KB sidebar. Code có staleTime 30 giây và tắt refetch khi focus; metadata có thể refetch khi remount/stale/invalidate.
- **Unknowns:** Chưa đo cold HTTP, frontend cache hit rate, request concurrency hoặc network waterfall.

### F2 — Sidebar ít nội dung nhưng aggregate trên tập rộng

- **Observed:** Sidebar không hydrate từ, nhưng vẫn tính counters toàn scope. Median phase counters A khoảng 466,4 ms, B khoảng 256,7 ms; phase scope/query B khoảng 133,6 ms.
- **Evidence:** Query trace và phase timings trong [evidence](BROWSE_REQUEST_DATA_AUDIT_2026-10-25.evidence.json); `build_decks()` và `deck_counts()`.
- **Potential concern:** Page size của list không tác động đến request sidebar.
- **Impact:** Chọn 20 từ cho bảng giữa vẫn có thể đồng thời trả 1.534 decks và chạy thống kê toàn scope nếu sidebar cần fetch.
- **Unknowns:** Chưa đo rows examined/EXPLAIN ANALYZE hoặc tải đồng thời với review. Các phase timings có thể lồng nhau, không cộng các median để suy ra tổng.

### F3 — Metadata deck được đọc lại giữa các request

- **Observed:** A sidebar đọc 1.534 Deck rows. A collection và cả A selected deck lại đọc 1.534 Deck rows để dựng scope; query đó trả khoảng 107,7 KB giá trị DB. Nhánh selected-subtree fast path chỉ bật khi `not admin_mode`. B selected deck không đọc lại toàn 290 deck shells; scope trực tiếp rất nhỏ.
- **Evidence:** `_build_browse_query()` trong [browse_card_service.py](../../app/services/browse_card_service.py), `selected_owned_decks()` trong [repository](../../app/repositories/browse_note_repository.py); A selected-20 trace có 1.534 Deck rows và 20 Note content rows.
- **Potential concern:** Sidebar trả đủ cây cho browser không có nghĩa list backend được dùng lại cây đó. Request-local caches không dùng chung qua hai HTTP requests.
- **Impact:** A selected-20 trả chỉ 4,3 KB JSON nhưng DB → Python khoảng 151,8 KB; 107,7 KB đến từ deck scope. Dữ liệu dư chủ yếu là metadata, không phải hàng chục nghìn từ.
- **Unknowns:** Chưa thử thay đổi/admin fast path hoặc cache xuyên request; không tuyên bố đã loại phần đọc lặp.

### F4 — Trả ít từ vẫn còn chi phí count/order toàn collection

- **Observed:** A collection-100: median count khoảng 208,6 ms, page/content khoảng 325,0 ms. B collection-100: count khoảng 190,5 ms, page/content khoảng 395,0 ms, release-values khoảng 159,2 ms. Selected deck 118 Notes có count chỉ khoảng 2–4 ms.
- **Evidence:** `count_notes()`, `note_page()`, `_hydrate_page()`, `_page_overlay_values()` và evidence timings.
- **Potential concern:** Giảm số dòng chỉ giảm hydration/format/response theo trang; count và chọn trang có chi phí nền.
- **Impact:** B collection 20/trang vẫn khoảng 905 ms dù chỉ trả 4,5 KB. B selected deck 20/trang khoảng 98 ms trên workload khác nhỏ hơn. Không gọi đây là speedup tương đương vì scope đầu vào khác nhau.
- **Unknowns:** Chưa benchmark search, word sort, deep pages hoặc concurrent writes trong đợt này. Các case dùng sort/status mặc định và trang 1.

### F5 — Editor tách riêng giới hạn full fields, vẫn có đọc lặp

- **Observed:** Full fields chỉ trả cho một active Note; list trước đó đã đọc nội dung để dựng preview. Editor B còn đọc cả một live Note JSON và một pinned checkpoint của cùng Note.
- **Evidence:** `load_note()`, `authorized_note()`, `_editor_detail()`; B editor trace có một SELECT Note full row và một checkpoint content row.
- **Potential concern:** Một phần content/schema/progress của Note được đọc lại khi chọn dòng; clone detail loader đọc live JSON không dùng để dựng pinned fields.
- **Impact:** Mức tải có giới hạn: editor A/B khoảng 2,9 KB, 23/73 ms trong mẫu đo. Đưa full detail vào toàn bộ list sẽ nhân lượng full fields theo page size; chưa có A/B benchmark cho phương án đó.
- **Unknowns:** Chưa đo Notes có field/media JSON lớn hoặc người dùng click liên tục; số field 16 chỉ là hai Notes được chọn.

## 6. Nếu gộp request thì có nhanh hơn không?

Chưa có endpoint gộp được triển khai hoặc benchmark trong báo cáo này. Có thể đánh giá trade-off từ cấu trúc đã quan sát:

| Phương án | Lợi ích có thể có | Chi phí/giới hạn |
|---|---|---|
| Tách sidebar/list/editor như hiện tại | Cache riêng; chuyển trang không tải lại cây; detail chỉ lấy khi cần; list và sidebar có thể tải độc lập | Cold open có nhiều HTTP requests; context/scope có phần đọc lặp |
| Gộp sidebar + list khi mở lần đầu | Có thể giảm một HTTP round trip và dùng lại metadata trong cùng request nếu thiết kế dùng chung context | Nếu chờ trả chung response, list phải chờ sidebar; vẫn phải aggregate counters; gửi lại sidebar ở mỗi page sẽ tăng bytes |
| Gộp full detail vào mọi row của list | Chọn dòng có sẵn dữ liệu editor | Tải full fields của cả trang dù chỉ sửa một Note; tăng bytes/parse/memory, cần xử lý freshness/revision |

Gộp JSON đơn thuần không bảo đảm giảm các SQL statements hiện có. Cần thay cách dùng lại scope/context mới giảm được phần query trùng. Ngược lại, chỉ tách HTTP cũng không bảo đảm hai nhánh không đọc cùng metadata.

Tổng số học của ba response khi cold open, chưa có active Note và page size 100:

- A: **46 SQL** và khoảng **636,2 KB JSON**, sidebar chiếm khoảng **94%** bytes.
- B: **157 SQL** và khoảng **145,5 KB JSON**, sidebar chiếm khoảng **78%** bytes.

Đây là tổng công việc/bytes của ba service calls đã đo riêng, không phải số request HTTP quan sát trong browser hoặc thời gian mở màn. Không cộng các service medians để báo latency màn hình: request có thể chạy chồng thời gian, cạnh tranh DB/worker và có cache. Editor click thêm 16/35 SQL trong hai samples nếu chưa có detail cache phù hợp.

## 7. Phương pháp, kiểm chứng và giới hạn

- Công cụ khảo sát phiên này: `.tmp/browse_request_audit_20261025.py`; kết quả đã lọc nội dung: [evidence JSON](BROWSE_REQUEST_DATA_AUDIT_2026-10-25.evidence.json).
- Dùng `create_audit_app()` đã kiểm code: tắt startup maintenance/cutover/schema repair và không đăng ký route runtime có side effects. Chỉ cho phép MySQL loopback, một DB bind. Guard chặn SQL ngoài SELECT/read CTE; chỉ SET giới hạn statement/lock wait trước khi gọi service. Giữ locking SELECT của implementation, rollback sau mỗi lượt.
- Không chạy create_all, migration, seed, restore, thêm index hoặc đổi dữ liệu. Không chạy correctness suite vì không sửa application code; 16 benchmark cases đều hoàn tất, payload ổn định.
- Các timing samples bỏ bước tính bytes từng DB cell; structural sample có instrumentation riêng. Phép đo dùng DB buffers đã warm, không giả lập browser cache hay cold MySQL.
- Browse clock được freeze trong service/repository như benchmark hiện có; helpers không patch riêng vẫn có thể dùng real time. Các payload hashes ổn định trong toàn bộ lượt đo.
- Không đo HTTP/auth/session overhead, JS/render, transferred gzip bytes, p95/load, concurrency/lock waits hoặc số rows MySQL thực sự examine. Không khẳng định tài khoản browser hiện tại của người dùng là A hoặc B.
- Các source chính: [browse API client](../../frontend/src/features/browse/api/browseApi.ts), [Browse routes](../../app/api/v1/learning/browse.py), [Note service](../../app/services/browse_note_service.py), [Note repository](../../app/repositories/browse_note_repository.py), [vocabulary repository](../../app/repositories/vocabulary_repository.py).

Tài liệu này bổ sung số đo hiện trạng cho [kế hoạch phân trang](BROWSE_PAGINATION_PLAN_2026-10-25.md); chưa thực hiện các thay đổi được đề xuất trong kế hoạch đó.
