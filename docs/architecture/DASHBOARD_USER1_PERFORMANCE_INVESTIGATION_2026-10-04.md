# Dashboard User 1: bottleneck hiện tại sau P10

> Ngày: 2026-10-04 (JST) | Điều tra production + review implementation local | Baseline production release `d747a5f5be6d3799a977b5efe73467072491a744`, MySQL 8.0.46, migration `20261003_000050`, `CONSOLIDATED_V1`.

Các số latency/browser dưới đây được đo trên **production trước bản sửa local**. Thay đổi đã review ở cuối báo cáo chưa deploy; chưa có số đo chứng minh speedup production của bản sửa đó.

## Kết quả chính

Đã tái hiện Dashboard tải khoảng **3,2–3,8 giây** bằng Chrome trên máy local truy cập production. Trạng thái cây đóng chỉ render **8 hàng** và mất **22–44 ms từ JSON hoàn tất đến DOM xuất hiện**. Chi phí lớn nằm ở luồng nối tiếp session → chunk Dashboard → API, preflight, SQL và truyền response. Khi mở hết cây, render/layout mới trở thành bottleneck rõ rệt: **1.527 hàng, 20.933 DOM elements**, long task **545 ms + 267 ms**.

Backend vẫn mất median **1,17 s** trong 5 lần đo bằng audit app trên VPS. Median thời gian SQL execute/fetch là **0,97 s**; riêng query đếm thẻ khoảng **0,73 s**, fallback NoteType **0,15 s**. CPU token/URL/asdict có thể giảm nhưng không giải thích phần lớn 3 giây.

Thử nghiệm SQL chỉ đọc của heatmap trả **cùng 30 ngày / 15.033 thẻ** trên snapshot User 1: gom SQL và giữ nguyên hai subject joins mất median **287 ms**, so với **448 ms** cho đường Python. Biến thể một join đạt **116 ms** trên snapshot này nhưng đã bị loại sau review: fixture có `live_note_id` và `logical_note_key` lệch nhau cho kết quả khác reader gốc. Bản sửa local giữ hai joins; parity trên MySQL local đã qua 108 trường hợp và 2 trường hợp DST, chưa thay thế số đo production sau deploy.

## Phương pháp và giới hạn

- SSH kiểm tra symlink release; audit dùng `create_audit_app()`, không import `wsgi`, không chạy startup maintenance/migration/seed/cutover.
- MySQL connection đặt `SET SESSION TRANSACTION READ ONLY`, xác minh `@@transaction_read_only=1`, giới hạn SELECT 10 giây và chặn DML/locking SELECT bằng SQLAlchemy listener. Không tạo/drop audit principal, không đổi cấu hình MySQL hoặc dữ liệu ứng dụng.
- 5 lượt Flask test-client/endpoint trên VPS, Dashboard và overview lần lượt; các stage được bọc bằng timer. cProfile là một lượt riêng, không gộp vào latency thông thường.
- SQL A/B: 3 lượt đổi thứ tự, so đầu ra trong snapshot chỉ đọc. Không flush cache, không gọi đây là cold-DB hoặc p95.
- Chrome dùng profile riêng `C:/Users/chung/.codex/chrome-profiles/dashboard-perf-20261004`, timezone `Asia/Tokyo`; cookie chẩn đoán chỉ trong bộ nhớ và profile riêng, không lưu vào artifact. Chặn request mutation trước khi mở Dashboard.
- Browser đo bằng CDP network, MutationObserver, frame tiếp theo và Long Tasks. DOM/next-frame là mốc hiển thị gần đúng, không phải đo physical paint hay React Profiler commit chính xác.
- Browser `Response.json()` duration bao gồm chờ body tải xong; không được gọi toàn bộ duration này là JSON.parse CPU. Resource Timing không có TAO trả kích thước 0, nên dùng CDP để đo transfer.
- Các nhóm đo có chủ ý chạy lần lượt. Vẫn có thể có traffic của người dùng khác. Collection tăng từ 39.283 lên 39.284 Card trong cửa sổ khảo sát; parity A/B được kiểm tra trong cùng snapshot, không so payload giữa hai thời điểm khác nhau.
- Số đo máy local/VPS này không phải trace của chính phiên 3 giây người dùng đã gặp. Không cộng median của các lượt khác nhau để dựng một phân rã giả chính xác.

## Những nhận định cần sửa trong phân tích ban đầu

| Nhận định | Kết quả kiểm chứng |
|---|---|
| 1.464 deck đều mount ngay | 1.464 là số deck chứa Notes. Có 1.527 deck hiển thị, 8 root; chỉ nhánh mở mới mount. |
| Heatmap chặn spinner toàn màn hình | `frontend/src/features/dashboard/pages/DashboardPage.tsx` chỉ chờ bootstrap/dashboard. Heatmap đã có Skeleton riêng. |
| Mỗi hàng mount toàn bộ menu items | Menu dùng Radix Portal, không `forceMount`; browser đếm **0 menu item DOM** khi menu đóng. |
| Backend vẫn join 8 bảng và kiểm contributor | Đây là đường trước P10 trong báo cáo 02/10. Reader hiện dùng subject consolidated; vector check trả 0. |
| Token 120–150 ms, URL 60–80 ms, asdict 50 ms | Median đo VPS hiện tại: **42 / 10 / 22 ms**. Lượt đầu có chi phí cao hơn, không đại diện mọi lượt. |
| `url_for` duyệt regex route cho mỗi deck | URL generation dùng rule theo endpoint; nhận định regex không mô tả đường build URL. |
| Truyền 727 KB JSON qua Internet | Audit JSON thô 727.689 B, gzip thử 77.026–77.058 B. CDP đo khoảng **78 KB encoded transfer**, encoding **zstd**. 715.091 B là kích thước `JSON.stringify` lại payload trong browser, không phải số byte thô đã truyền. |
| Trả root-only sẽ bỏ chi phí quét 39k thẻ | Root badge và summary vẫn cần đếm descendants. Cắt response không tự thay đổi count SQL. |
| Tối ưu trên đảm bảo <800 ms | Chưa có phép đo chứng minh. Riêng backend hiện đã hơn 1 giây. |

Source: `frontend/src/features/dashboard/components/DeckRow.tsx`, `frontend/src/features/dashboard/hooks/useDeckTreeExpanded.ts`, `frontend/src/components/ui/dropdown-menu.tsx`, `app/repositories/note_analytics_read_repository.py`. Radix mô tả `forceMount` tại [Dropdown Menu documentation](https://www.radix-ui.com/primitives/docs/components/dropdown-menu).

## Browser: đường tới cây deck

Cold ở đây là profile browser mới/cache HTTP trống, không phải DB cache trống. Các reload sau giữ profile và cookies, nhưng JS vẫn revalidate bằng 304.

| Trạng thái | Hàng mount | DOM elements | DOM hàng đầu / frame kế tiếp | JSON xong → hàng đầu | Long tasks liên quan |
|---|---:|---:|---:|---:|---|
| Mở mới, cây đóng | 8 | 1.076 | 3.804 / 3.805 s | 44 ms | 62 ms ở bootstrap, không có render deck dài |
| Reload cây đóng 1 | 8 | 1.076 | 3.442 / 3.447 s | 23 ms | Không có |
| Reload cây đóng 2 | 8 | 1.076 | 3.219 / 3.224 s | 22 ms | Không có |
| Mở ancestor Tettei `[414,415]` | 183 | 3.361 | 3.175 / 3.175 s | 100 ms | 98 + 65 ms |
| Mở toàn bộ nhánh | 1.527 | 20.933 | 3.451 / 3.451 s | 552 ms | 545 + 267 ms |

Timeline cùng một lượt cold, tính từ navigation:

| Mốc | Thời điểm |
|---|---:|
| Bắt đầu `/api/session` (browser request, gồm chờ preflight) | 0,417 s |
| OPTIONS session xong | 0,760 s |
| Session response xong | 1,166 s |
| Bắt đầu tải chunk Dashboard | 1,199 s |
| Bắt đầu Dashboard + overview (browser request) | 1,596–1,598 s |
| OPTIONS Dashboard xong | 1,882 s |
| Dashboard nhận header | 3,415 s |
| Dashboard body tải xong | 3,755 s |
| Dashboard JSON hoàn tất | 3,760 s |
| Hàng deck xuất hiện | 3,804 s |

CDP request start của GET có thể xảy ra trước OPTIONS vì bao gồm thời gian chờ CORS. Không cộng duration GET và OPTIONS lần nữa.

**Observed trên baseline:** Outlet bị giữ đến khi session xong tại `frontend/src/layouts/AppLayout.tsx:324` và `frontend/src/features/auth/components/RequireAuth.tsx:9`; sau đó mới tải lazy Dashboard tại `frontend/src/App.tsx`, rồi hook khởi chạy hai API tại `frontend/src/features/dashboard/hooks/useDashboardPage.tsx`. Bản sửa local đã thay preload và thời điểm chạy overview; waterfall ở trên vẫn thuộc release production cũ.

**Impact:** Backend smoke một endpoint không bao gồm session, tải route code, preflight và render. Browser mới/reload phải trả các chi phí này nối tiếp.

**Observed trên baseline:** `frontend/src/features/dashboard/components/DeckModals.tsx` eagerly import `DeckWorksheetModal` qua worksheet barrel. Production trace xác nhận request `WorksheetsPage` dù chưa mở Worksheet, khoảng **49 KB encoded**. Bundle local khác hash production nên số bundle local chỉ là tham khảo. Cold browser có khoảng **327 KB JS encoded**; reload vẫn revalidate 44 script requests bằng 304 (~20,6 KB encoded headers).

**Candidates:** Preload code Dashboard trong lúc session chạy; lazy-load Worksheet/action modal; bỏ `X-Timezone` không cần thiết khỏi GET session/dashboard hoặc chuyển timezone GET phù hợp sang query parameter. Giữ authorization gate và semantics timezone.

Ở baseline production, API client thêm `X-Timezone` cho mọi request và frontend/backend khác origin; CORS chưa đặt `Access-Control-Max-Age`. Cache preflight giúp lượt lặp; loại header không cần thiết có thể giúp cả lượt đầu. Max-age là cache kết quả preflight, không cache dữ liệu người dùng ([MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Max-Age)). Bản sửa local đã giới hạn header theo endpoint và thêm max-age vào OPTIONS, nhưng browser timing ở bảng trên vẫn là baseline.

### Quay lại Dashboard trong cùng SPA

Đây là navigation từ `/terms` về `/dashboard` khi React Query và chunk đã tồn tại trong cùng phiên browser, khác hard reload:

| Cache dữ liệu | Cây hiển thị / frame kế tiếp | Network trong cửa sổ đo | Kết quả |
|---|---:|---|---|
| Fresh | 42,6 / 43,5 ms | 0 request | 8 hàng lấy từ cache, không có long task |
| Stale | 40,6 / 41,2 ms | 2 GET + 2 OPTIONS | Cây cache xuất hiện trước; Dashboard JSON revalidate xong khoảng 2.491 ms sau navigation |

Stale cache không biến lượt quay lại thành spinner 3 giây: nội dung cũ xuất hiện ngay, rồi hai API làm mới phía sau. Cần đánh giá first usable deck và data-ready riêng; không áp số hard reload cho mọi lần mở Dashboard.

### HTTP: đồng thời so với Dashboard trước

Probe độc lập dùng HTTP/1.1 qua TLS, connection đã warm và giữ riêng cho từng endpoint. Mỗi mode có 3 mẫu, không đo session/chunk/render; GET timing không chứa OPTIONS của browser. Các profiler SQL khác được tạm dừng trong cửa sổ này. Browser có protocol/cache khác nên không xem bảng này là navigation benchmark.

| Mode | Dashboard GET median | Overview GET median | Cả hai hoàn tất, median |
|---|---:|---:|---:|
| Đo từng endpoint riêng | 1.552 ms | 1.151 ms | Không phải một lượt tải chung |
| Hai GET đồng thời | 1.747 ms | 1.257 ms | 1.749 ms |
| Dashboard xong rồi mới Overview | 1.640 ms | 1.131 ms | 2.765 ms |

OPTIONS đo riêng khoảng **109 ms** cho Dashboard và **107 ms** cho Overview. Concurrent Dashboard dài hơn mẫu isolated khoảng 195 ms (~13%); mẫu này không chứng minh nhận định tăng 30–50% vì tranh chấp DB. Serial giúp Dashboard sớm hơn concurrent khoảng 108 ms nhưng cả hai hoàn tất muộn hơn khoảng 1 giây. Bản sửa local ưu tiên cây deck trước và giữ heatmap Skeleton; cần đo lại trade-off này sau tối ưu SQL thay vì coi serial là luôn nhanh hơn.

### Payload và CPU browser

Các biến thể dưới đây cùng được tạo từ payload baseline trong browser bằng `JSON.stringify` và `CompressionStream('gzip')`; đây là phép so byte, không phải endpoint đã triển khai hay transfer zstd đo sau sửa:

| Biến thể | JSON UTF-8 | gzip thử |
|---|---:|---:|
| Đầy đủ | 715.091 B | 79.373 B |
| Bỏ token/parent metadata/href, **giữ move alias** | 321.235 B | 28.580 B |
| Bỏ cả move alias | 275.425 B | 16.000 B |
| Chỉ 8 root, có `has_children`, giữ alias | 1.710 B | 502 B |

30 vòng parse/map offline trên máy đo: `JSON.parse` median **0,9 ms**, p95 mẫu **1,6 ms**; `toDeckNode` tương đương median **0,2 ms**, p95 mẫu **1,2 ms**. Đây không phải p95 người dùng và chưa tính allocation/GC dài hạn. Nó xác nhận không nên gán toàn bộ thời gian `Response.json()` chờ body cho CPU parse.

## Backend: công việc còn đắt

| Stage | Median 5 lượt | Ghi chú |
|---|---:|---|
| Dashboard endpoint | 1.173 ms | Range 1.004–1.717 ms; gồm auth, payload, JSON, request overhead |
| Tổng SQL execute/fetch Dashboard | 971 ms | 14 statements, gồm transaction statement |
| Count SQL `cards → notes → subjects` | 730 ms | Trả 1.464 group; 4 `COUNT(DISTINCT ...)` |
| Fallback NoteType SQL | 152 ms | Trả 1.464 group; `GROUP BY deck_id, note_type_id` |
| Thu thập cây deck, toàn hàm | 111 ms | Admin User 1 load full ORM hai lần + query parents |
| Sinh signed token, toàn bộ 1.527 deck | 42 ms | Còn SHA/alias ngoài timer này |
| `url_for`, 1.527 lần | 10 ms | Backend href không được frontend dùng |
| `asdict`, toàn cây | 22 ms | 8 root calls bao gồm recursive serialization |
| Overview endpoint | 800 ms | Range 715–1.107 ms, 10 statements |
| Overview yearly review aggregate | 250 ms | Trả 260 ngày; không tải toàn bộ review event vào Python |
| Overview future-due map, toàn hàm | 497 ms | Query trả 15.246 rows; Python mapping sau đó |

Stage tổng chứa stage con, không cộng tất cả hàng trong bảng. SQL timer với PyMySQL buffered cursor bao gồm nhận/decode result của driver; chưa tách riêng CPU MySQL khỏi network/driver.

Count EXPLAIN dùng `ix_notes_user_id` (estimate 17.936 row), `uq_cards_note_application`, `uq_sp_subject_user_note`; có `Using filesort`. Fallback dùng owner index và `Using temporary`. Không có bằng chứng một index mới tự giải quyết toàn bộ chi phí. `EXPLAIN.rows` là estimate, không phải count đã đọc thực tế ([MySQL manual](https://dev.mysql.com/doc/refman/8.0/en/explain-output.html)). Buffer pool vẫn **128 MiB**; chưa A/B thay cấu hình lần này.

## SQL A/B: điều gì thực sự giảm được

| Thử nghiệm chỉ đọc | Baseline median | Candidate median | Parity và giới hạn |
|---|---:|---:|---|
| Future due: gom SQL, giữ hai subject joins | 448 ms | 287 ms | Cùng 30 ngày / 15.033 thẻ |
| Future due: gom SQL + một subject join | 448 ms | 116 ms | Cùng đầu ra User 1; **bị loại** do regression với logical/live identity drift |
| Cây admin: load full ORM một lần | 113 ms | 39 ms | Cùng ID/order/fields cây trong snapshot |
| Fallback chỉ deck thiếu explicit NoteType | 152 ms | 134 ms | Cùng NoteType cuối cùng Dashboard |
| Count từ Note scope với `EXISTS Card` | 557 ms | 503 ms | Cùng total/new/learn/due mỗi deck |

Số count SQL baseline 557 ms là đợt A/B khác, không thay median 730 ms của 5 endpoint samples.

**F1 — Overview lặp join và truyền quá nhiều rows**

- Observed: `learner_note_scope` join subject bằng `live_note_id`, `note_card_rows` join subject lần nữa bằng `logical_note_key`; `_canonical_future_due_day_counts` lấy mọi due row rồi map/filter theo năm trong Python.
- Evidence: `app/repositories/note_analytics_read_repository.py:85` và `:47`. 15.246 rows chỉ tạo 30 group thuộc khoảng ngày; 213 rows ngoài khoảng cuối năm. SQL grouping local hiện nằm ở `app/repositories/stats_query_repository.py`, service chọn SQL/fallback trong `app/services/stats_overview.py`.
- Impact: Grouping giảm row transfer trong A/B; implementation giữ lookup subject thứ hai để bảo toàn tập availability gốc.
- Correctness: Writer kiểm logical/live identity, nhưng schema không có constraint buộc hai cột bằng nhau. Fixture lệch logical key có current state qua live association nhưng không có availability qua logical key: reader gốc không đếm, một join lại đếm. User 1 snapshot có 0 mismatch/duplicate nên A/B của riêng User 1 không phát hiện regression này.
- Unknowns: Latency sau deploy trên dữ liệu thật, p95 và traffic đồng thời. Local parity đã kiểm invalid due day, queue khác review, suspended/buried, detached/drift, publisher-owned source Notes, nhiều sibling Card, năm nhuận/year-end và day boundaries; DST vẫn dùng Python.

**F2 — Cây admin đọc full deck hai lần**

- Observed: admin path load 1.527 ORM Deck, query 1.519 parent rows, rồi load lại 1.527 Deck. Candidate tận dụng parent IDs đã có và Python sort, chỉ query thêm ancestor thực sự thiếu.
- Evidence: `app/repositories/deck_tree_query.py:24`; A/B tree parity trên các fields Dashboard dùng.
- Impact: Giảm median khoảng 74 ms ở User 1, scope nhỏ hơn redesign lazy tree.
- Unknowns: Cần kiểm chứng external-owner ancestors, deleted decks, normal ownership và installed-clone path; không bỏ visibility rules.

**F3 — Fallback và note-grain không phải thắng lớn trên dataset này**

- Observed: 1.223/1.527 deck chưa có explicit NoteType; 1.160 deck trong số đó chứa Notes. Narrowing fallback vẫn scan theo `ix_notes_user_id` và dùng temporary table. Mọi Note User 1 trong snapshot có đúng một Card (39.284/39.284).
- Evidence: `_deck_note_types` và main aggregation tại `app/services/deck_aggregation_service.py`; EXPLAIN hai biến thể.
- Impact: Giảm khoảng 18/54 ms ở mẫu nhỏ; chưa đáng xếp trước cải thiện overview/startup/tree. Với multi-template, Note-grain có thể khác.
- Unknowns: p95, lượng nhiều-template, overlay duplicate mappings. Không dùng kết quả này để bỏ `DISTINCT` toàn cục.

**F4 — Move transport dư thừa**

- Observed: React PATCH move bằng numeric `deck_id`/`parent_id`; không dùng `move.token`, `parent_token`, `parent_alias` hay backend `href`. `move.alias` vẫn dùng trong menu Copy Move ID của admin.
- Evidence: `frontend/src/app/api.ts`, `frontend/src/features/dashboard/hooks/useDashboardPage.tsx`, `frontend/src/features/dashboard/hooks/useDeckTreeDragDrop.ts`, `frontend/src/features/dashboard/components/DeckRow.tsx`.
- Impact: Biến thể browser giữ alias giảm 715.091 → 321.235 B, gzip thử 79.373 → 28.580 B. Bỏ mọi move field cho số byte nhỏ hơn nhưng không giữ Copy Move ID, nên không dùng biến thể đó làm mục tiêu implementation.
- Compatibility: Bản sửa local dùng opt-in `compact=1`; default payload giữ signed token, parent metadata và legacy `href`. Compact giữ alias hiển thị ổn định bằng HMAC, không đổi authorization của numeric PATCH. Legacy POST vẫn parse signed token; helper/legacy support được giữ.

Root-only payload giả lập có số byte khác nhau theo serializer và trường giữ lại: audit 3.178 B (~860 B gzip), browser variant 1.710 B (502 B gzip). Cả hai là byte comparison, chưa phải endpoint hoàn chỉnh. Lazy tree còn cần `has_children`, loaded-state, khôi phục nhánh mở, ancestor paths, move target catalog/naming/cycle guard, quyền truy cập và correct subtree counts.

## Thay đổi local đã review, chưa deploy

- **Overview:** chuyển SQL grouping về repository, giữ hai subject joins và Card units. Fixed-offset zones dùng SQL; DST dùng Python. Due-day precedence, overdue folding và exclusive end date giữ nguyên.
- **Dashboard contract:** thêm compact opt-in cho React, giữ alias Copy Move ID; default request vẫn trả contract signed-token cũ. Compact bỏ recursive `asdict` cho các trường không trả và không sinh token/legacy URL hàng loạt.
- **Cây admin:** dùng một lần đọc full Deck; chỉ query thêm ancestor còn thiếu, giữ normal/installed visibility path.
- **Waterfall:** preload Dashboard chunk trong lúc bootstrap; Worksheet modal lazy-load theo action; chỉ bỏ timezone header ở endpoint không dùng nó hoặc truyền timezone qua query. OPTIONS có max-age cấu hình.
- **Scheduling:** gate của hook trì hoãn overview lúc initial/stale mount cho đến khi Dashboard fetch xong, heatmap giữ Skeleton riêng. Gate không hủy overview đang chạy; global invalidation hoặc refetch đã bắt đầu vẫn có thể tạo overlap. Đây không phải cơ chế khóa hai API. Không thêm full-page spinner và không coi lượt serial là giảm tổng thời gian của cả hai API.

Review đã sửa regression `href` của bản Gemini ban đầu và không trả token rỗng cho default API consumer. Chưa thực hiện virtualization, root/child lazy loading, index/cache mới hay thay buffer pool. Các số A/B/browser baseline không phải số đo của bundle/backend local này.

Đơn vị của heatmap vẫn là **Card**, đúng reader cũ: Note có hai sibling Card đến hạn đóng góp hai vào ngày đó. Deck badges có thể đếm **Note** khi `STUDY_NOTE_COUNT_ENABLED=true` cho NOTE learners (`app/services/dashboard_service.py:80`, `app/services/deck_aggregation_service.py:236`). Tối ưu này không đồng nhất hai đơn vị. User 1 có một Card mỗi Note trong snapshot nên số của riêng tài khoản này không thể phát hiện sự khác biệt; fixture multi-card kiểm chứng heatmap vẫn đếm từng Card.

Kiểm chứng phần stats đã hoàn tất:

- `python scripts/run_tests.py --file tests/test_stats_overview.py --backend-only`: **18 tests PASS**.
- `python scripts/probe_dashboard_due_counts_mysql.py`: MySQL local **8.0.40**, **108 SQL/Python parity cases + 2 DST fallback cases**, 0 mismatch. Probe dùng generated local schema, startup maintenance tắt, schema được drop trong `finally`; DB ứng dụng không bị sửa.
- Fixture bao gồm one/multi-card, no-card/pristine, publisher-owned source, learner khác, suspended/buried, detached/logical drift, review due-day ưu tiên due-at, queues khác review, boundary 0/4/23, year-end và leap day.

Kiểm chứng toàn bản sửa local:

- **48 backend tests PASS:** 18 stats, 28 integration/CORS/NOTE analytics, 2 note-count flag tests. Nhóm 28 chạy với `STUDY_NOTE_COUNT_ENABLED=false` vì fixture NOTE analytics cũ giả định Card units; hai tests tại `tests/test_study_note_level_counts.py` kiểm tra riêng cả `false` và `true`. Không đổi default flag để làm tests qua.
- **27 frontend tests PASS:** 21 transport/client/CreateDeckModal và 6 dashboard query/page tests. Typecheck, build và lint PASS; lint còn warning có sẵn, build còn warning chunk trên 500 KB.
- **WSGI smoke PASS:** dùng đúng entry point `wsgi.py` với SQLite in-memory cô lập; health/bootstrap hoạt động, `CORS_MAX_AGE=7200` chỉ xuất hiện ở OPTIONS.
- **Browser QA PASS trên production build local, API mock:** Chrome dùng profile riêng `dashboard-review-20261004` và đã đóng. Ban đầu một hàng, mở nhánh thành hai; Study dẫn đúng `/study?deck_id=42`; không tải Worksheet chunk trước khi mở. Khi delay chunk 2 giây, loading dialog hiển thị và hủy được bằng Esc; modal thật tải với field mapping, đóng được, 0 page error.
- Browser QA xác nhận session/dashboard/overview không gửi `X-Timezone`; overview vẫn có query `timezone=Asia/Tokyo`, còn worksheets/meta giữ header. Đây là kiểm tra transport/UI với mock, chưa đo latency backend hoặc speedup production.

Không suy diễn speedup production từ tests parity hoặc Browser QA local. Cần đo lại navigation và endpoint sau khi triển khai bản sửa được phê duyệt.

## Ưu tiên xác minh tiếp theo

1. **Giảm waterfall vào trang:** timezone header/preflight không cần thiết, preload Dashboard code, lazy Worksheet/action modal. Đo lại navigation đến first deck và thời gian `/session`; preserve auth gate và giao diện.
2. **Đo overview grouped SQL giữ hai joins:** giữ fallback DST/correctness. So dashboard-first với concurrent sau sửa SQL; Skeleton đã có nên đo scheduling thay vì quy lỗi cho spinner.
3. **Loại tree read lặp ở admin** và thu gọn response fields không dùng, giữ Copy Move ID/legacy contract.
4. **Count SQL chính:** tiếp tục A/B ở note-grain/aggregation shape. Hiện vẫn là phần lớn backend; biến thể thử được mới giảm nhỏ, chưa có căn cứ hứa endpoint <500 ms.
5. **Virtualization cho nhiều nhánh mở:** trace all-expanded xác nhận lợi ích; bảo toàn row height/layout/colors, keyboard, drag/drop và scroll. Không coi đây là nguyên nhân của cây đóng 8 root.
6. **Lazy-load root/children** nếu vẫn cần sau các bước trên. Scope và regression surface lớn hơn; không dùng nó thay việc tối ưu SQL counts.

Không đặt cam kết <800 ms trước khi đo lại đúng critical path sau sửa. Đặt riêng first usable deck, heatmap-ready, và all-expanded responsiveness; đánh giá hard reload và SPA revisit riêng.

## Kiểm chứng khi chuyển từ thử nghiệm sang implementation

- Dùng `python scripts/run_tests.py --list-modules` để chọn domain hẹp; backend parity ở `test_note_analytics_read.py`, `test_deck_aggregation_service.py`, `test_stats_overview.py`, `test_study_consolidated_progress.py`; frontend dashboard/modal/drag tests khi có thay đổi tương ứng.
- So full payload và per-deck counts trên cùng snapshot: direct-owned + installed clone, one/multi-template, pristine/no-state, suspended/buried, due-day/due-at precedence, timezone/day-boundary/DST, detached/deleted entities.
- Browser profile riêng, cùng build/data và 3 trạng thái: 8 root, Tettei, mở hết; kiểm tra Copy Move ID, move selector, expand restore và keyboard.
- Không chạy full suite. Phần điều tra production chỉ đọc; implementation và tests chạy local. Không deploy/restart/mutate production.

## Artifact

Tổng hợp số đo đã lưu tại [artifact JSON](artifacts/dashboard_user1_performance_20261004.json). Chỉ giữ timing/count/byte/environment tổng hợp; không chứa cookie, secret, response body, nội dung Note/Deck hay SQL parameters. Script/raw timing nằm ở `output/` (gitignored):

- `perf_dashboard_20261004.py`, `perf_dashboard_production_20261004.jsonl`.
- `perf_overview_ab_20261004.py`, `perf_overview_ab_20261004.jsonl`.
- `perf_dashboard_backend_ab_20261004.py`, `.jsonl`.
- `perf_http_dashboard_20261004.py`, output JSON tương ứng.
- `output/playwright/dashboard_user1_*_20261004.json`, collector scripts.
- `dashboard_due_counts_mysql_20261004.json`; probe tái chạy được ở `scripts/probe_dashboard_due_counts_mysql.py`.

Bối cảnh lịch sử: [điều tra 02/10 trước P10](LOCAL_PRODUCTION_STUDY_DASHBOARD_PERFORMANCE_2026-10-02.md), [P10-08 cutover](../task/decoupling/P10_08_CUTOVER_REPORT_2026-10-03.md), [P10 execution plan / P10-09](../task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md).
