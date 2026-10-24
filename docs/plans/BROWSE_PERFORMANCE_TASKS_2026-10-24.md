# Các task nâng cấp hiệu năng Browse

Ngày: 2026-10-24. Căn cứ: [báo cáo điều tra](../architecture/BROWSE_PERFORMANCE_DATA_REVIEW_2026-10-24.md) và [evidence MySQL local](../architecture/BROWSE_PERFORMANCE_DATA_REVIEW_2026-10-24.evidence.json).

Cập nhật phạm vi: người dùng yêu cầu làm nợ kỹ thuật trước, tối ưu sau. Đã triển khai công cụ service baseline/MySQL contract của B00 và bản sửa ordering B08; kết quả kiểm chứng ghi tại [báo cáo pha nợ kỹ thuật](../architecture/BROWSE_TECH_DEBT_IMPLEMENTATION_2026-10-24.md). B01–B07 chưa triển khai. HTTP/load measurements của B00 dành cho pha tối ưu, không được coi đã đo trong lần này.

Các số đo là mẫu service local một lần/case, không phải HTTP production hoặc p95. Ngưỡng 5 giây là giới hạn do probe đặt. Phần “vì sao cách cũ như vậy” phân biệt hành vi/lịch sử đã kiểm chứng với lý do kỹ thuật suy luận từ code; không khẳng định động cơ của người viết nếu Git không ghi rõ.

## Danh sách để chọn phạm vi

| ID | Task | Mức ưu tiên | Căn cứ | Phụ thuộc | Mức thay đổi |
|---|---|---|---|---|---|
| B00 | Thiết lập baseline và bộ đối chiếu kết quả trên MySQL | Điều kiện kiểm chứng | Số query phẳng chưa phản ánh latency | Không | Đo/kiểm chứng, chưa đổi hành vi |
| B01 | Chỉ tải NoteType đủ dùng cho form Browse | P2, thay đổi nhỏ làm sớm | Full 66 query/247 KB; compact 3 query/17,5 KB ở mẫu A | Kiểm contract trong B00 | Frontend |
| B02 | Tối ưu đếm tổng và chọn một preview mỗi Note | P1, tác động chính | Count toàn collection vượt ngưỡng 5 giây | B00 | Backend/repository |
| B03 | Giảm SQL lặp khi search/sort deck clone | P1 | Count search dài 1,86 triệu ký tự | B00; thống nhất query contract với B02 | Backend/repository |
| B04 | Batch việc xác định deck/install được truy cập | P2 | Toàn scope clone có 53 statements tới count | B00 | Backend/repository |
| B05 | Giảm chi phí aggregate counters sidebar | P2 | Sidebar service khoảng 3,4–4,7 giây | B00; dùng scope đã xác minh của B04 | Backend; frontend nếu đổi contract |
| B06 | Đánh giá reader trạng thái học dành cho Browse | P2, có điều kiện | List dựng nhiều state hơn dữ liệu trả về | Đo phase trong B00 | Backend, rủi ro nhất quán cao |
| B07 | Thu gọn dữ liệu hydrate và response danh sách | P3, có điều kiện | DTO/ORM rộng hơn dữ liệu React đang dùng | Audit callers; đo sau B02/B03 | Backend + hợp đồng frontend |
| B08 | Kiểm chứng và sửa sort theo tên deck local | P2 về hành vi | ORDER BY source name, response dùng local name | Fixture B00; cùng contract B02/B03 | Backend |

B02/B03 ưu tiên về tác động. B01 có thể hoàn thành trước vì phạm vi nhỏ. B06/B07 chỉ triển khai sau khi chứng minh lợi ích; không mặc định bỏ lock/validation hoặc xóa trường API. B08 là sửa tính đúng, không được tính là cải thiện latency.

## B00 — Baseline và đối chiếu kết quả trên MySQL

**Vì sao cần:** Có thể giảm số JOIN/query nhưng lại tăng thời gian, sai total hoặc bỏ Note của clone. Các test query-bounds hiện có chủ yếu chứng minh số statement không tăng theo số dòng trên fixture; chưa đủ chứng minh plan/latency MySQL.

**Vì sao trước đây làm như vậy:** Tests query-bounds phục vụ đúng việc ngăn N+1 và giữ deck visibility sau thay đổi 20/10. Đây là coverage có ích. Việc dùng số query như chỉ báo hiệu năng tổng thể sẽ vượt quá điều các test đó chứng minh.

**Bây giờ phần nào không đủ/không cần:** Không bỏ test cũ. Cần bổ sung bằng chứng thời gian và kết quả trên workload lớn; không cần chạy toàn bộ test suite cho mọi thử nghiệm query.

**Làm gì:** Chuẩn hóa probe SELECT-only và fixtures MySQL local/disposable cho owned, release clone, snapshot, override/add/remove/rename field, pristine/stateful, multi-template/cutover/retired. Ghi riêng count, page, authority, overlay, serialization và HTTP; đo lặp với điều kiện cache được ghi rõ. So sánh ordered Note/presentation IDs, total/pages, preview values, statuses và lỗi giữa baseline/candidate.

**Điểm yếu/đánh đổi:** Tốn công tạo fixture đúng; cache, máy local và dữ liệu không đồng đều làm lệch số đo. Không tự động áp dụng SLO từ local sang production. Fixture sai có thể làm hai implementation cùng “pass” nhưng đều sai.

**Hoàn thành khi:** Có case matrix, baseline và cách chạy lại; có fixture override vì DB local khảo sát có 0 note-field override. Tests correctness và benchmark được phân biệt, không đặt assertion latency dễ dao động vào unit tests.

Phạm vi: `tests/test_browse_query_bounds.py`, các test Browse/NOTE hiện có, probe khảo sát và MySQL fixture theo quy trình local-dev. Không chạy lại seed/migration trên DB phát triển dùng chung chỉ để tạo benchmark.

## B01 — Tải NoteType gọn và đúng lúc

**Vì sao cần:** Browse gọi `/note-types` full ngay khi mount, lấy template HTML/CSS, marketplace/taxonomy mà form tạo Note không đọc. Mẫu A: full 66 statements/247.402 bytes; compact 3 statements/17.523 bytes, cùng 6 note types.

**Vì sao trước đây làm như vậy:** Code dùng endpoint đầy đủ và query key chung `['note-types']`. Suy luận kỹ thuật: reuse dữ liệu của màn quản lý và có sẵn schema ngay khi người dùng mở form giúp giảm code/độ trễ tương tác lúc tạo Note. Không có bằng chứng cần HTML/CSS template cho Browse form hiện tại.

**Bây giờ phần nào không cần:** Riêng Browse form chỉ đọc ID, tên và `field_defs`; backend đã có `compact=1`. Endpoint full vẫn cần cho caller khác. Có thể trì hoãn request tới lúc mở create nếu trải nghiệm chấp nhận được; không bắt buộc phải lazy để dùng compact.

**Làm gì:** Dùng compact với query key riêng theo response shape; giữ field definitions. Cân nhắc enable khi create hoặc prefetch theo tương tác mở form. Kiểm tra loading/error và chọn note type tự động. Migrate các frontend file được chạm theo FSD, dùng client của slice/shared; không kéo theo toàn bộ feature rewrite.

**Điểm yếu/đánh đổi:** Lazy load làm lần mở form đầu phải chờ. Cache riêng có thể thêm một request nếu màn khác đã có full data. Đổi shape dưới query key cũ làm caller khác nhận thiếu dữ liệu. `summary=1` không mặc nhiên thay compact vì form còn cần fields.

**Hoàn thành khi:** Form tạo Note đủ fields/array types; màn khác không bị cache shape sai; payload và query count được đo lại. Giao diện và hành vi tạo Note giữ nguyên; chạy focused Vitest/typecheck cho phần chạm.

Phạm vi: `frontend/src/features/browse/hooks/useBrowseState.ts`, API/public entry của slice và focused tests. Endpoint compact hiện có ở `app/api/v1/flashcards/note_types.py`, service `app/services/flashcard_content_service.py`.

## B02 — Count theo Note và chọn preview hiệu quả hơn

**Vì sao cần:** Toàn collection phải count xong mới lấy trang. Mẫu A/B chạm ngưỡng 5 giây ở count dù yêu cầu 100 hay 500 dòng. Đây là nút thắt trực tiếp của trang đầu.

**Vì sao trước đây làm như vậy:** Browse đi qua Card/presentation để dùng chung visibility, membership và bộ lọc trạng thái. Thay đổi 14/10 chuyển UI sang một dòng mỗi Note. Query hiện ranking trên tập visible để không bỏ Note khi application default không visible. Cách này ưu tiên tái sử dụng điều kiện đúng.

**Bây giờ phần nào không cần:** Khi chỉ đếm Notes, không cần xác định toàn bộ nội dung/metadata của presentation đại diện nếu có thể chứng minh tồn tại ít nhất một presentation hợp lệ bằng cùng predicates. Khi lấy page vẫn cần chọn đúng preview. Chưa chứng minh có thể bỏ ranking trong mọi trường hợp.

**Làm gì:** Tách contract “Note có ít nhất một presentation visible” khỏi “chọn preview nào”; thử count Note identity và chọn ID trước, hydrate sau. So sánh plan và tổng chi phí với cách hiện tại. Giữ exact total, filters, stable tie-break và diagnostic `all_templates`. Không chốt DDL/index mới trước khi đo query candidate trên MySQL.

**Điểm yếu/đánh đổi:** Tách count/page dễ làm lệch predicates và đơn vị đếm. Chọn default application toàn NoteType có thể bỏ Note lịch sử chỉ còn application khác. Hai query có thể thấy trạng thái khác nhau nếu đổi transaction semantics. Query mới nhiều nhánh hơn có thể khó bảo trì hoặc planner xử lý tệ hơn ở clone.

**Hoàn thành khi:** Ordered IDs/total/pages/preview và lỗi giữ đúng qua matrix B00; toàn scope không còn bị ngắt ở count với giới hạn probe trên workload tương đương. Ghi riêng cải thiện count và page; không coi bật `all_templates` hoặc bỏ total là bản sửa.

Phạm vi: `app/repositories/browse_card_repository.py`, `app/services/browse_card_service.py`, tests Browse/NOTE visibility. Giữ HTTP parsing ở route và query ở repository khi chạm code.

## B03 — Giảm biểu thức lặp của search/sort clone

**Vì sao cần:** Search toàn collection mẫu B dựng SQL count dài 1.862.434 ký tự. Một deck 118 Notes, search không có kết quả vẫn mất khoảng 1,51 giây. Số Note trả về ít không đồng nghĩa ít việc phải tính.

**Vì sao trước đây làm như vậy:** Clone không copy source Notes. Nội dung phải khôi phục đúng applied release rồi áp local overrides, kể cả field thêm/xóa/đổi tên. Đặt effective-value search/sort trong SQL trước pagination giúp total và các trang đúng; lọc sau LIMIT sẽ sai.

**Bây giờ phần nào không cần:** Vẫn cần release/override resolution. Có thể không cần lặp riêng checkpoint, operation/value và cùng scope expression nhiều lần cho mỗi field trong count/ranking/page. Đây là ứng viên giảm lặp, chưa phải bằng chứng có thể xóa các bảng release.

**Làm gì:** So sánh cách resolve effective fields có thể reuse trong một query với correlated expressions hiện tại; kiểm khả năng tách owned/installed branches. Dùng chung semantic contract với B02 và template/schema runtime. Đo SQL length, compile/client time nếu tách được, execute/fetch và latency tổng. Chưa mặc định thêm search cache/materialized table.

**Điểm yếu/đánh đổi:** Gom bằng derived table/CTE có thể materialize tập lớn và chậm hơn. JOIN sai cardinality làm nhân dòng. Reuse kết quả sai install/release/overlay revision gây lẫn dữ liệu. Tạo search index/cache mới sẽ thêm storage, đồng bộ và invalidation; chưa nằm trong phạm vi triển khai mặc định.

**Hoàn thành khi:** Search/sort tìm theo đúng giá trị learner nhìn thấy, gồm nested arrays và field deltas; total/thứ tự không đổi; chi phí được cải thiện trên cả no-match và nhiều-match, một/nhiều installs, lịch sử release dài. Không dùng source live thay pinned content và không lọc sau pagination.

Phạm vi: `clone_effective_field_text_expression()` trong browse repository, clone projections trong browse service; đối chiếu `app/services/share/overlay.py` và `app/services/deck_release_service.py`.

## B04 — Batch deck/install scope

**Vì sao cần:** Mỗi request list vẫn xây toàn scope accessible của learner trước khi xử lý deck đã chọn. Luồng nhiều installs đọc ancestors/subtree/map/release lặp theo install; mẫu B có 53 statements trước khi count hoàn thành.

**Vì sao trước đây làm như vậy:** Resolver từng deck dùng lại được cho browse/detail/edit; giữ quyền truy cập, local/source mapping và xử lý fallback tập trung. Thay đổi 20/10 đã bỏ tải mọi deck toàn hệ thống, nhưng vẫn cần xây scope riêng của learner.

**Bây giờ phần nào không cần:** Không cần đọc lại cùng ancestor, subtree, map hoặc release metadata nhiều lần trong một request khi đã có tập đủ dùng. Không được bỏ ownership, note-holding decks, deleted-deck rules hoặc install fallback vì chúng vẫn là contract hiện tại.

**Làm gì:** Tải installs/maps theo batch, dùng lại cây/request-scoped data và giảm query traversal trùng. Giữ resolver đơn lẻ cho caller khác nếu cần, nhưng cho phép list cung cấp context đã tải. Tối ưu selected-deck path chỉ khi scope equivalence được chứng minh.

**Điểm yếu/đánh đổi:** Tải batch quá rộng làm tốn RAM và IN-list lớn; context tạo stale hoặc dùng sai learner sẽ thành lỗi quyền truy cập. Thu hẹp scope quá sớm có thể mất ancestors/Note-holding decks hoặc fallback legacy. Shared cache xuyên request có rủi ro khác và chưa thuộc task này.

**Hoàn thành khi:** So sánh visible IDs/order với contract cũ trên owned/foreign ancestor/deleted nodes/installed subtree; query traversal trùng giảm khi số installs/depth tăng. Không yêu cầu số query luôn hằng số vì depth/chunking còn hợp lệ.

Phạm vi: `app/repositories/vocabulary_repository.py`, `app/repositories/deck_tree_query.py`, share scope resolver/repository và Browse service. Tránh broad rewrite `app/services/share/`.

## B05 — Giảm chi phí counters của sidebar

**Vì sao cần:** Sidebar phải aggregate toàn cây; hai mẫu mất khoảng 3,43 và 4,72 giây. Bảng danh sách nhanh hơn chưa bảo đảm người dùng có sidebar sẵn để chọn deck.

**Vì sao trước đây làm như vậy:** Tính trực tiếp từ canonical availability giữ counts đúng sau học, sửa/cài deck và đổi ngày học; chưa cần quản lý cache invalidation. Các node cha phải cộng subtree, đồng thời sidebar phục vụ mixed-note-type/batch actions.

**Bây giờ phần nào không cần:** Counters vẫn cần. Có thể giảm tính lặp hoặc query shape không hiệu quả; chưa có bằng chứng “không cần tính trực tiếp nữa”. Cache chỉ là bước có điều kiện sau khi đo và xác định freshness contract.

**Làm gì:** Tách thời gian scope/aggregate/integrity/build-tree/serialize; tối ưu aggregate trên scope đã xác minh. Giữ counters và metadata hiện có ở bước đầu. Chỉ mở bước cache nếu query optimization chưa đủ và đã có invalidation cho review, content/schema/install/overlay/deck changes, timezone và day boundary.

**Điểm yếu/đánh đổi:** Cache làm số đếm cũ sau review hoặc sang ngày mới; invalidate quá rộng làm mất lợi ích. Tách metadata/counters thành hai request thêm loading states và có thể lệch snapshot. Không reuse cache dashboard chỉ vì cùng có total/new/learn/due: Browse có visibility contract riêng.

**Hoàn thành khi:** Counters và mixed-type metadata đúng ở root/subdeck, owned/clone, suspended/buried/pristine, Note-count/presentation-count modes; có số đo aggregate trước/sau. Nếu chọn cache, phải chứng minh invalidation/freshness và error contract trước khi coi task xong.

Phạm vi: `build_browse_deck_tree()` trong browse service, `app/services/deck_aggregation_service.py`, note analytics scope/read repositories; frontend chỉ khi thật sự đổi response/loading contract.

## B06 — Đánh giá reader trạng thái học chuyên cho Browse

**Vì sao cần:** List đọc/khóa/decode full authority state và dựng state-version rồi chỉ lấy queue/due. Các page có state đã đo có 8 locking SELECT. Đây là chi phí có thể giảm, chưa được chứng minh là bottleneck chính.

**Vì sao trước đây làm như vậy:** Reuse Study reader bảo đảm enrollment/profile, pristine classification, state hash và availability parity; lock giữ thứ tự và tính nhất quán với writer. Đây là mục đích đang còn giá trị, không phải validation lỗi thời.

**Bây giờ phần nào không cần:** Browse không dùng artifact/state-version cho việc cấp phiên học. Có thể tránh dựng output chỉ Study cần. **Chưa thể kết luận full validation hoặc lock không còn cần.** Nếu bỏ chúng làm yếu contract, đó là thay đổi sản phẩm/consistency riêng cần quyết định.

**Làm gì:** Trước hết đo riêng authority phase và concurrent Browse/review. Thử reader/projection nhỏ hơn chỉ khi giữ page integrity, hash/state parity, fail-closed errors và consistency đã chốt. Không âm thầm đổi GET sang non-locking chỉ vì số query thấp hơn.

**Điểm yếu/đánh đổi:** Non-locking snapshot có thể khác current write state; chỉ đọc queue/due có thể che state hỏng. Reader riêng dễ lệch logic với Study và làm tăng maintenance. Nếu vẫn phải decode/project đầy đủ để giữ contract thì phần tiết kiệm có thể nhỏ.

**Hoàn thành khi:** Có quyết định dựa trên measurement: triển khai reader có equivalence hoặc ghi nhận không đáng tách. Nếu triển khai, kiểm concurrent review, pristine/stateful, malformed/diverged state và 409 parity. Không tính case count timeout vào lợi ích authority vì timeout xảy ra trước phase này.

Phạm vi: browse service, `app/services/study_authority_read_service.py`, authority repository và focused state/parity tests. Không làm thay đổi rộng reader dùng chung của Study chỉ để phục vụ Browse.

## B07 — Thu gọn hydrate và response list

**Vì sao cần:** Query tải Note entity rộng; pinned clone vẫn nhận live source JSON dù formatter không dùng để hiển thị. Serializer còn trả template/card-type và các thuộc tính React Browse không đọc.

**Vì sao trước đây làm như vậy:** Card browser có contract giàu thông tin và ORM entity thuận tiện cho formatter, quyền truy cập và các caller khác. List/detail dùng nhiều thành phần chung. Suy luận kỹ thuật: reuse giảm logic riêng nhưng không tự bảo đảm projection tối thiểu.

**Bây giờ phần nào không cần:** Editor đã có detail request riêng. Có thể giảm các cột/output chỉ phục vụ detail hoặc client khác, sau khi audit. Chỉ vì bảng có ba cột preview không có nghĩa chỉ cần lấy đúng ba field names: thứ tự/fallback/schema tùy biến vẫn cần.

**Làm gì:** Audit API callers, alias/legacy endpoints và tests; xác định list DTO cần giữ. Thử hydrate metadata/preview theo page IDs, tránh source working JSON ở pinned clone nếu không còn caller runtime cần. Nếu xóa response fields, phải có compatibility decision; bước đầu có thể tối ưu ORM mà giữ wire shape.

**Điểm yếu/đánh đổi:** Deferred columns dễ sinh N+1 nếu formatter chạm lại. Cắt DTO có thể làm client ngoài React hỏng. Cache/precomputed preview tạo thêm invalidation khi values/schema/order/overlay đổi. Giảm vài string response không giải quyết count nhiều giây.

**Hoàn thành khi:** Có consumer inventory và số bytes/ORM work tiết kiệm đo được; không thêm per-row reads; custom fields, extras và native nested arrays giữ nguyên. Nếu lợi ích thấp thì hoãn, không ép thay contract để hoàn thành task.

Phạm vi: `browse_page_load_options()`, list serializer trong vocabulary repository, Browse DTO/client callers. Không di chuyển full editor/media payload vào list.

## B08 — Sort theo tên deck mà learner nhìn thấy

**Vì sao cần:** Code ORDER BY tên source deck, sau pagination mới remap row sang tên local deck. Nếu hai tên khác nhau, thứ tự có thể không khớp tên response. Hiện là finding từ code, chưa có fixture tái hiện trong lần khảo sát.

**Vì sao trước đây làm như vậy:** Query nền dùng source Note/deck để đọc clone không copy dữ liệu; local mapping được áp lúc dựng response. Sort SQL vẫn giữ biểu thức theo source identity. Đây là nguyên nhân suy ra từ luồng code.

**Bây giờ phần nào không cần:** Vẫn cần source identity cho release/membership. Riêng yêu cầu sort theo deck hiển thị không nên phụ thuộc source name nếu API cam kết tên local. Trước khi sửa phải khóa kỳ vọng này bằng fixture.

**Làm gì:** Tái hiện bằng source/local names trái thứ tự, nhiều installs và page boundary. Nếu API kỳ vọng sort theo local name, dùng effective deck identity/name nhất quán trước ORDER BY và pagination; giữ tie-break ổn định.

**Điểm yếu/đánh đổi:** Một source có thể được thấy qua nhiều installs; mapping không đơn trị cần quyết định cùng scope contract. JOIN/CASE thêm có thể làm sort nặng hơn. Đổi ordering làm page membership khác baseline nên cần expected-correct oracle, không chỉ equality với cách cũ.

**Hoàn thành khi:** Có reproducer; đúng ASC/DESC và page boundaries với effective names, không nhân đôi/mất Note. Đo lại sort để biết chi phí. Nếu fixture không xác nhận lỗi trong contract thực tế, đóng bằng giải thích thay vì sửa giả định.

Phạm vi: nhánh `sort_by=deck` trong browse service/repository; clone mapping và focused API/query tests.

## Ranh giới chung khi triển khai

- Giữ overlay-only, pinned release, quyền owner/install, canonical field identity và native JSON arrays. Không bỏ các bảng alias/cutover hay quay về full-copy clone.
- Giữ default một dòng/Note, diagnostic all-templates, nullable due anchors và timezone/day-boundary helpers. Không đổi `status=all` hoặc đơn vị sidebar count như tác dụng phụ của tối ưu.
- Code frontend chạm tới phải theo FSD, public API của slice, slice/shared client và bảo toàn màu/layout/loading/error/draft behavior. Refactor chỉ trong phạm vi task.
- Dùng focused tests qua modular runner theo local-dev; kiểm query/JSON/concurrency trên MySQL. SQLite memory hiện có không thay thế benchmark/integration MySQL. Không chạy full suite mặc định.
- Schema/index/cache model mới chưa nằm trong kế hoạch triển khai đã chốt. Nếu query experiments chỉ ra cần DDL hoặc thay đổi freshness/consistency, trình phương án và trade-offs riêng trước khi mở rộng task.
- Mỗi task phải có diff, correctness evidence và số đo tương ứng; không báo “nhanh hơn” chỉ từ ít query/ít dòng code. Không yêu cầu mọi task phải tạo thay đổi nếu phép đo hoặc parity không ủng hộ.

## Trình tự thực hiện đề xuất

1. B00: khóa baseline và contract.
2. B01: thay đổi nhỏ độc lập; B02 là ưu tiên điều tra/tối ưu chính.
3. B03: dùng contract query đã thống nhất; B08 kiểm ordering trong quá trình này.
4. B04 rồi B05: giảm scope work và chi phí sidebar, chưa bật cache theo mặc định.
5. B06/B07: chỉ đi tiếp khi phase metrics cho thấy có lợi ích đáng kể.

Các phần mô tả B01–B07 vẫn là kế hoạch cho pha tối ưu tiếp theo. B00/B08 theo trạng thái cập nhật đầu tài liệu. Chưa ấn định SLA và chưa suy diễn các số local thành cam kết production.
