# Kế hoạch phân trang và giảm tải khi mở Browse

> Cập nhật triển khai 2026-10-25: URL pagination, selected-deck scope, sidebar structure/summaries và compact clone reads đã thực hiện; xem [kết quả và kiểm chứng](BROWSE_OPTIMIZATION_IMPLEMENTATION_2026-10-25.md). Nội dung bên dưới giữ lại kế hoạch ban đầu.

Ngày: 2026-10-25 (Asia/Tokyo). Mốc khảo sát: HEAD `16e82f3b` và working tree hiện có. Đây là báo cáo hiện trạng và đề xuất triển khai; chưa sửa application code, chạy benchmark, kết nối DB, chạy tests hoặc thay đổi schema/index trong phiên này.

## 1. Kết luận và phạm vi

Browse hiện **đã phân trang tại backend**, không tải toàn bộ nội dung collection về React rồi mới chia trang. Ba tham số người dùng cần đã có ở API: `deck_id`, `page`, `per_page`. Phần cần bổ sung rõ nhất là đọc/ghi đủ ba tham số trên URL của màn hình, cùng việc giảm các tác vụ toàn collection còn chạy độc lập với trang danh sách.

Mục tiêu đề xuất:

- Mở trực tiếp `/browse?deck_id=123&page=3&per_page=50` và lấy đúng trang ngay ở request danh sách đầu tiên.
- Nội dung Note, release values, overrides và progress dùng để dựng rows chỉ được hydrate theo IDs của trang hoặc Note đang mở editor.
- Cây deck và counters không khiến việc xem một trang nhỏ phải chờ xử lý toàn collection.
- Giữ một dòng cho mỗi Note, gồm cả Note không có template; giữ quyền truy cập, release pin, overlay, native arrays, scheduling và giao diện hiện tại.
- Giữ API cũ cho các caller khác. Không cần thay schema hoặc thêm index cho kế hoạch ban đầu.

Không đặt mục tiêu “DB chỉ chạm đúng 50 records”: exact total, tìm kiếm và sort có thể cần xét cả tập phù hợp trong SQL. Phân biệt việc đó với đưa toàn bộ nội dung/IDs về Python hoặc browser.

## 2. Hiện trạng đã kiểm tra trong code

| Phần | Hành vi quan sát được | Bằng chứng |
|---|---|---|
| API đang dùng | React gọi `/api/browse/notes?view=rows`, không dùng Card list làm nguồn chính | [browseApi.ts](../../frontend/src/features/browse/api/browseApi.ts), [browse.py](../../app/api/v1/learning/browse.py) |
| Tham số danh sách | Gửi `deck_id`, `page`, `per_page`, `q`, `status`, `sort_by`, `sort_dir`; request nhận AbortSignal | [useBrowseData.ts](../../frontend/src/features/browse/hooks/useBrowseData.ts) |
| Phân trang thường | Đếm Notes; SELECT identity đã order với `paginate(..., count=False)`; hydrate nội dung sau khi lấy trang | [browse_note_service.py](../../app/services/browse_note_service.py), [browse_note_repository.py](../../app/repositories/browse_note_repository.py) |
| Search | Count và page dùng chung ranked CTE trong một statement; không kéo toàn bộ matching IDs về Python | `search_note_page()` trong [browse_note_repository.py](../../app/repositories/browse_note_repository.py) |
| Release clone | Chỉ hydrate checkpoint/release values và overrides cho Notes của trang; tránh tải live source JSON không cần thiết | `_hydrate_page()` và `_page_overlay_values()` trong hai file trên |
| Scope deck | Đã có fast path cho subtree hoàn toàn thuộc learner, gồm shell deck của install nếu thỏa điều kiện; mixed/foreign và nhánh khác dùng resolver hiện có | `selected_owned_decks()` trong repository, `_build_browse_query()` trong [browse_card_service.py](../../app/services/browse_card_service.py) |
| URL màn hình | Đọc `deck_id`, `note_id`/`card_id`; `page` luôn khởi tạo bằng 1, số dòng lấy từ localStorage hoặc mặc định 100 | [useBrowseState.ts](../../frontend/src/features/browse/hooks/useBrowseState.ts), [useBrowseFilters.ts](../../frontend/src/features/browse/hooks/useBrowseFilters.ts) |
| UI phân trang | Đã có chọn 20/50/100/200/500 dòng, số trang, đầu/cuối, trước/sau, nhảy trang; thay filter/sort/page size có reset trang | [BrowsePagination.tsx](../../frontend/src/features/browse/components/BrowsePagination.tsx), `useBrowseFilters.ts` |
| Dữ liệu cũ khi chờ | React Query dùng `keepPreviousData`; bảng nhận `isPlaceholderData` để đặt `aria-busy`; response cũ có thể còn hiển thị khi state trang mới đã đổi | `useBrowseData.ts`, [BrowseCardTable.tsx](../../frontend/src/features/browse/components/BrowseCardTable.tsx) |
| Chọn nhiều dòng | Giữ IDs được chọn xuyên trang; Ctrl/Cmd+A dùng rows của trang hiện tại | [useBrowseSelection.ts](../../frontend/src/features/browse/hooks/useBrowseSelection.ts) |
| Sidebar | Mount query độc lập; `/browse/decks?view=notes` dựng cây đầy đủ, metadata note types và aggregate counters toàn cây | `build_decks()` trong service, `deck_counts()` trong repository, [vocabulary_repository.py](../../app/repositories/vocabulary_repository.py) |
| Note types | Đã dùng `compact=1`, cache riêng; vẫn preload ngay khi mount | `browseApi.ts`, `useBrowseData.ts` |
| Editor | Chỉ fetch khi có active Note; dùng `view=editor` và detail key chung cho editor/tools | [useBrowseEditor.ts](../../frontend/src/features/browse/hooks/useBrowseEditor.ts), `browseApi.ts` |

### F1 — URL chưa biểu diễn đủ vị trí Browse

- **Observed:** API hỗ trợ đủ pagination nhưng URL chưa khởi tạo `page`/`per_page`; thay lựa chọn deck trong sidebar cũng chưa đồng bộ thành một query state URL thống nhất.
- **Evidence:** `useBrowseState()`, `useBrowseFilters()`, callback chọn deck trong `BrowseDeckSidebar.tsx`.
- **Potential concern:** Refresh, chia sẻ link hoặc Back/Forward không khôi phục đầy đủ trang đang xem.
- **Impact:** Người dùng truyền trang/số dòng trên URL vẫn mở theo state mặc định hiện tại.
- **Unknowns:** Chưa kiểm browser/network của phiên đang chạy; nhận định dựa trên source.

### F2 — Chi phí sidebar không bị giới hạn bởi page size

- **Observed:** Sidebar gọi service riêng, không nhận selected deck/page; `deck_counts()` gọi `guard_scope()` rồi aggregate theo toàn bộ context deck. Tree còn đọc distinct deck/note-type metadata.
- **Evidence:** `build_decks()`, `deck_counts()`, `build_browse_deck_tree_payload()`. `guard_scope()` đọc các progress rows có dấu hiệu lỗi của learner trước khi đối chiếu scope, không phải hydrate mọi Note.
- **Potential concern:** Giảm `per_page` không giảm được công việc này; tải sidebar nhẹ hơn cần thay đường đọc backend, không chỉ dời thời điểm gọi query ở React.
- **Impact:** Vẫn có hoạt động xét collection khi danh sách chỉ cần một trang nhỏ.
- **Unknowns:** Chưa có số đo mới về tỷ trọng sidebar so với list/HTTP/render tại mốc khảo sát.

### F3 — Exact count/search/sort vẫn có chi phí theo filtered scope

- **Observed:** List đã giới hạn hydration theo page; count thường xét tập phù hợp, search dùng ranking/aggregate; sort có thể cần đọc nhiều rows trước page boundary.
- **Evidence:** `count_notes()`, `note_page()`, `search_note_page()`, `order_notes()`.
- **Potential concern:** Chỉ thêm pagination params hoặc giảm số dòng chưa chắc giảm phần SQL chiếm nhiều thời gian nhất.
- **Impact:** Cần đo count, lựa chọn trang và hydration riêng để quyết định tối ưu tiếp.
- **Unknowns:** Chưa chạy lại EXPLAIN, latency, write/concurrency hay các trang sâu trong phiên này.

Các báo cáo ngày 24/10 có phần đã được triển khai tiếp. Không dùng số count timeout của Card path cũ để mô tả Note path hiện tại. Tham khảo bản cập nhật 25/10 trong [review query/overfetch](BROWSE_QUERY_OVERFETCH_REVIEW_2026-10-24.md) và [báo cáo triển khai](BROWSE_TECH_DEBT_IMPLEMENTATION_2026-10-24.md); số đo trong đó là bằng chứng lịch sử, không phải lần benchmark mới của báo cáo này.

## 3. Hợp đồng đề xuất

### URL màn hình và request

```text
/browse?deck_id=123&page=3&per_page=50

GET /api/browse/notes?view=rows&deck_id=123&page=3&per_page=50
```

Giữ tên đang dùng là `deck_id` và `per_page`, tránh thêm một bộ alias `deck`/`page_size` có cùng ý nghĩa. “Số trang” trong request là trang muốn xem, còn `pages` trong response là tổng số trang.

| Tham số | Quy tắc đề xuất |
|---|---|
| `deck_id` | ID deck local được phép truy cập; bỏ trống là xem toàn collection có quyền, vẫn phân trang |
| `page` | Đánh số từ 1; thiếu thì 1; giữ normalization hiện có về tối thiểu 1 |
| `per_page` | Từ 1 đến 500 theo giới hạn API hiện có; URL hợp lệ được ưu tiên hơn preference local; thiếu cả hai thì giữ mặc định 100 |
| `include_subdecks` | Tiếp tục giữ mặc định 1 của backend; 0 khi muốn chỉ deck đó. Không tự thay nghĩa chọn deck hiện tại |
| `q`, `status`, `sort_by`, `sort_dir`, `tag` | Giữ các bộ lọc/sort đã được API hỗ trợ; filter và order chạy trước pagination |

Đồng bộ quy tắc URL/API cho số nguyên, giá trị ngoài khoảng và đầu vào sai kiểu; không tự thay error contract API trong một refactor frontend. API hiện trả 400 khi không parse được page/per_page hoặc deck_id, và 404 khi deck không thuộc scope truy cập. URL không hợp lệ được chuẩn hóa trước request, không âm thầm biến một deck bị cấm thành yêu cầu toàn collection.

Ví dụ cấu trúc response minh họa, không phải dữ liệu đo:

```jsonc
{
  "items": [/* tối đa 50 Note rows theo DTO hiện có */],
  "page": 3,
  "per_page": 50,
  "total": 2403,
  "pages": 49,
  "has_next": true
}
```

Trong ví dụ có dữ liệu thật, `items` chứa tối đa 50 Note rows. Mỗi row giữ `note_id`, deck, preview và trạng thái theo DTO hiện tại. Backend đã trả `per_page`; cần bổ sung trường này vào type response frontend để client biết số dòng thực tế đã được chuẩn hóa.

Không suy ra `total` bằng số items của trang, và không thay `total` danh sách bằng counters sidebar: hai đường đọc hiện có quy tắc active/burial khác nhau.

### Trang vượt phạm vi

Giữ response hiện có: items rỗng nhưng total/pages đúng. Client chuyển về trang hợp lệ cuối cùng, cập nhật URL rồi fetch trang đó. Collection rỗng dùng page 1 và pages 0. Không clamp về trang cuối trong lúc response vẫn chỉ là placeholder của query cũ.

## 4. Triển khai theo từng bước

### Bước 0 — Chốt baseline đúng Note path

- Dùng `scripts/benchmark_browse_mysql.py` với operations `notes`, `note_decks`, `note_types`; không đo nhầm legacy `cards`/`decks`.
- Cases: selected owned deck, selected installed deck, toàn collection, include/exclude subdecks, keyword có/không kết quả, due/word/deck sort, trang đầu/giữa/cuối, page size 20/50/100/500.
- Đo service/SQL riêng với HTTP/network/render. Ghi count, chọn page, hydrate, authority, release/overlay, response bytes và rows/columns đọc từ DB.
- Dùng cùng dataset, clock và parameters khi so sánh. Đo warmup và lặp; không lấy một sample hay hai timeout làm bằng chứng tương đương/nhanh hơn.
- Chỉ đọc MySQL local với audit factory và guard của benchmark. Không đổi schema, thêm index hoặc chạy migration cho baseline.

### Bước 1 — Một query state thống nhất với URL

- Đưa parsing/normalization vào model/helper của slice Browse và một hook điều phối URL; khởi tạo đủ deck/page/per_page ngay lần render đầu, không mount ở collection rồi effect mới chọn deck.
- Dùng URL làm nguồn vị trí Browse; ưu tiên URL, sau đó preference số dòng, sau đó mặc định.
- Thay deck/search/status/sort/page size sẽ cập nhật state và page=1 cùng một lần, tránh request trung gian mang deck mới nhưng trang cũ.
- Đổi page cập nhật URL; Back/Forward khôi phục được query state. Search debounce dùng replace để tránh một history entry cho mỗi lần gõ; thao tác điều hướng chủ động có thể tạo entry.
- Giữ `note_id`/`card_id` bookmark và các query params khác cần thiết; không ghi đè toàn bộ search string.
- Giữ query key đầy đủ và AbortSignal hiện có. Không thêm vòng fetch nối tất cả trang hoặc prefetch toàn collection.
- Khi giữ rows cũ trong lúc tải, footer và thao tác chọn dòng phải gắn với response đang hiển thị; không ghi trang 3 cho rows của trang 2. Khi đổi deck/filter, không cho thao tác batch vô tình chạy trên placeholder của scope cũ. Giữ draft editor và selection xuyên trang theo contract hiện tại.

### Bước 2 — Giữ SQL pagination và khóa giới hạn hydration

- Giữ đường Note-first hiện có; không viết lại thành Card/Template query hoặc Python slicing.
- Dùng cùng scoped/filter relation cho count và page; order có tie-break hiện có `Note.updated_at DESC, Note.id ASC` sau sort chính.
- Không thay `search_note_page()` bằng count/search riêng hai lần: CTE hiện đã dùng chung kết quả.
- Tải Note payload, schema, progress reads, release values và overrides chỉ cho page IDs. Detail vẫn query riêng khi chọn một Note.
- Với selected deck, kiểm tra fast path hiện có bằng query capture. Chỉ mở rộng/batch resolver nếu thấy nhánh thực sự vẫn đọc deck/install không liên quan; giữ mixed visibility, ancestors và install precedence.
- Page number cần nhảy trực tiếp nên giữ cách chọn trang theo số; trang thường dùng LIMIT/OFFSET, search đang dùng ranked page window. Trang sâu vẫn có thể tốn chi phí. Chỉ đánh giá cursor ở bước sau nếu workload cho phép đổi UX, vì cursor không trực tiếp thay thế việc nhảy tới trang bất kỳ.
- `updated_at`/due có thể thay đổi khi import, edit hoặc study đồng thời: kết quả giữa hai request là dữ liệu hiện thời. Không hứa một snapshot cố định xuyên mọi trang; muốn bảo đảm đó sẽ là phạm vi riêng.

### Bước 3 — Sidebar tải cấu trúc trước, thống kê theo nhu cầu

Đây là phần bổ sung thực sự giúp tránh công việc toàn collection khi mục tiêu chỉ là xem một deck nhỏ.

- Bổ sung chế độ cấu trúc nhẹ cho deck API; đề xuất `GET /api/browse/decks?view=notes&structure_only=1`. Cờ này **chưa có** trong code hiện tại.
- Chế độ nhẹ chỉ trả identity/name/path/parent cần dựng cây và picker; bỏ việc aggregate progress/counters và distinct NoteType distribution. Không chỉ thêm flag ở React trong khi backend vẫn gọi `build_decks()` đầy đủ.
- Bổ sung batch summaries có giới hạn, ví dụ `GET /api/browse/decks/summaries?deck_ids=123,124`. Endpoint này **chưa có**. Chỉ tính counters và mixed-note-type metadata cho selected deck cùng các nodes đang cần hiển thị; scope summary của một node vẫn phải gồm subtree theo contract hiện tại. Giới hạn số IDs mỗi request, kiểm quyền từng ID và gom truy vấn, tránh một request/query cho mỗi dòng sidebar.
- Giữ full response mặc định của API cũ để không làm hỏng các caller chưa chuyển đổi. Structure response không được dùng như full summary trong cache/types.
- `selectedDeck` phục vụ tools phải được ghép với summary đầy đủ. Trong lúc chưa có, giữ loading state và khóa công cụ phụ thuộc mixed-note-type/count thay vì giả định thiếu counts nghĩa là 0 hoặc thiếu type metadata nghĩa là single type.
- Giữ bố cục, kích thước badges và trạng thái đã tải như cũ; request bảng không chờ summary. Các count hiển thị khi chưa tải dùng trạng thái chờ phù hợp.
- Nếu cần mọi badge, tải batch ở nền theo các nodes hiển thị. Nếu người dùng mở toàn cây thì cuối cùng vẫn có thể cần counters toàn cây; kế hoạch thay chi phí ban đầu bằng tải theo nhu cầu, không tuyên bố xóa mọi aggregate.
- Dùng cache phía client có key rõ ràng cho structure/summaries; invalidation theo edit/create/delete/move/import/rebase và các thay đổi progress/day boundary hiện ảnh hưởng counters. Không thêm persistent cache hoặc bỏ integrity guards trong đợt này.
- Cây cấu trúc vẫn có thể là O(số deck). Lazy children/server-side deck search là bước riêng nếu đo thấy payload cây tiếp tục lớn; không cần để hoàn thành pagination nội dung.

### Bước 4 — Metadata phụ và hoàn thiện UX

- NoteType compact đã dùng đúng. Chỉ cân nhắc lazy query khi bật form tạo Note nếu baseline còn cho thấy lợi ích; kiểm lại logic chọn default type và loading của form. Không coi đây là thay đổi đã bắt buộc.
- Xóa dòng cuối trang: invalidate list, lấy total mới, về trang cuối hợp lệ. Tạo/sửa Note: giữ detail/draft, refresh đúng query keys theo hành vi hiện tại.
- Ctrl/Cmd+A và checkbox đầu bảng chỉ chọn trang đang hiển thị. Giữ IDs được người dùng chọn xuyên trang mà không tải toàn collection. Không thêm “chọn mọi kết quả” bằng cách fetch tất cả IDs.
- Các công cụ xử lý cả deck chỉ chạy khi người dùng yêu cầu thao tác đó; mở Browse/chuyển trang không được khởi động việc tải nội dung cả deck cho audio/SVG/worksheet.
- Khi chạm file frontend, tuân theo FSD trong phạm vi thay đổi: hooks/model/api thuộc Browse; page ráp các workflows qua public API; không thêm cross-feature import, root helpers hoặc legacy `app/api.ts` calls. Kiểm callers trước khi di chuyển/xóa shim. Giữ style, spacing, fonts, gradient và layout hiện có.

## 5. File dự kiến liên quan

| Vùng | Phạm vi dự kiến |
|---|---|
| `features/browse/hooks/useBrowseFilters.ts`, `useBrowseState.ts` | Đồng bộ URL/query state và tránh init request sai scope |
| `features/browse/hooks/useBrowseData.ts` | Query keys, rows/metadata độc lập, response normalization và loading |
| `features/browse/api/browseApi.ts`, `types.ts`, `api/browseQueryKeys.ts` | Khai báo contract pagination/structure/summary; tách cache identities |
| Browse sidebar/table/pagination và `pages/browse` | Nối state, range hiển thị, metadata loading; chỉ sửa markup khi cần cho trạng thái mới |
| `app/api/v1/learning/browse.py` | Parse chế độ cấu trúc/summary và response mapping, giữ auth/error conventions |
| `app/validators/` | Validation các flags/IDs mới, giới hạn batch và quy tắc tham số thống nhất |
| `app/services/browse_note_service.py` | Điều phối structure/summary, không đưa DB query vào route |
| `app/repositories/browse_note_repository.py`, deck query helpers liên quan | Scope/batch summary reads, không hydrate nội dung ngoài trang |
| `tests/test_browse_notes_mysql.py`, `test_browse_search_mysql.py`, focused Vitest suites | Contract, pagination, permissions, SQL bounds, URL và UX regressions |

Không mặc định sửa `models/`, migrations, scheduler, authority locking hay share cutover. Không mở lại các tối ưu đã hoàn thành chỉ để đổi tên/cấu trúc code.

## 6. Tiêu chí nghiệm thu và kiểm chứng

1. Mở URL deck/page/per_page: request list đầu tiên đúng cả ba giá trị; không có request collection trung gian và không có chuỗi tải mọi trang.
2. Collection có N Notes, P dòng/trang: response tối đa P rows; ORM/overlay/progress hydration giới hạn page IDs. Không kết luận DB scan là O(P) chỉ vì hydrate bị giới hạn.
3. Hợp các trang trên dữ liệu đứng yên cho đúng toàn bộ Notes phù hợp, không lặp/mất dòng; trường hợp một Note có nhiều applications vẫn là một dòng, Note không template vẫn có mặt.
4. Filter/sort áp dụng trước phân trang, giữ thứ tự ổn định; search giữ literal wildcard và native arrays; trang không kết quả/ngoài phạm vi có metadata đúng.
5. Owned, release clone, legacy snapshot, source/local deck khác tên, nested subdecks, admin/learner và deck không có quyền đều giữ đúng contract. Không lộ live author values, không ghi vào source khi edit clone.
6. URL Back/Forward/refresh hoạt động; đổi filters/page size reset trang atomically; stale/cancelled response không ghi đè scope mới; placeholder/footer/selection không mô tả nhầm trang.
7. Xóa hết trang cuối tự về trang hợp lệ; giữ draft editor và lựa chọn xuyên trang. Điều khiển desktop/mobile và keyboard giữ hành vi.
8. Khi dùng structure mode, query capture chứng minh không aggregate counters/NoteType distribution toàn collection. Summary chỉ dùng scope được yêu cầu, không N+1; API full cũ vẫn hoạt động.
9. Kiểm chứng MySQL local bằng suite hiện có với `FLAMA_BROWSE_MYSQL_TESTS=1`; không dùng SQLite để thay thế integration. Frontend chạy focused Vitest, typecheck và so giao diện desktop/mobile trong Chrome profile riêng. Đọc `skills/flama-local-dev/SKILL.md` trước khi thực thi.
10. So sánh baseline đúng cùng workload; báo riêng list, sidebar và total time tới khi có trang dùng được. Mục tiêu giảm tải phải được chứng minh bằng rows/bytes/query scope và số đo, không chỉ số request hoặc page size.

Lệnh kiểm chứng dự kiến dùng `.venv/Scripts/python.exe scripts/run_tests.py --file ... --backend-only` cho các MySQL files liên quan, và `npm test -- <focused suites>`/`npm run typecheck` trong `frontend`. Danh sách `--file` cần gồm `test_browse_notes_mysql.py`, `test_browse_search_mysql.py`, cùng compatibility/tool suites khi đường đọc tương ứng thay đổi. Không chạy toàn suite chỉ cho một thay đổi pagination.

## 7. Giới hạn, rủi ro và cách triển khai

- Chưa có số đo mới, nên không hứa số ms hoặc hệ số tăng tốc. Exact count, sort, clone search và deep pages vẫn có thể chiếm chi phí đáng kể.
- Thay Sidebar sang tải summary theo nhu cầu phải giữ quyền và mixed-type checks của tools. Đây là hạng mục vừa, không phải chỉ một flag frontend.
- Không thay nghĩa `status=all`, due/burial hoặc day boundary trong task pagination; dùng helpers hiện có. Không bỏ fail-closed validation hoặc locks để giảm latency.
- Không thêm index trong kế hoạch này. Nếu baseline về sau cho thấy cần index, phải có EXPLAIN, phương án không thêm index, tác động ghi/storage/import/sync/study, rủi ro DDL/rollback và sự đồng ý rõ ràng riêng trước khi tạo, kể cả local.
- Triển khai backend modes mới trước, giữ mặc định cũ; sau đó chuyển frontend. Có thể quay client về endpoint full cũ nếu summary path có regression, không cần rollback dữ liệu/schema.
- Phân tách review thành: (1) URL + pagination contract, (2) sidebar structure/summary, (3) tối ưu SQL bổ sung nếu baseline chỉ ra vấn đề. Sau mỗi phần có focused correctness checks; không gộp thành rewrite toàn Browse.

Trạng thái cuối báo cáo: chỉ tạo tài liệu kế hoạch này. Việc triển khai ứng dụng và đo kiểm nằm ở bước tiếp theo khi người dùng yêu cầu thực hiện.
