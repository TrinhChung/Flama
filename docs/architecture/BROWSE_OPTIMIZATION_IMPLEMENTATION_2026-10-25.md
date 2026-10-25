# Browse: triển khai scope và tải sidebar theo nhu cầu

Ngày: 2026-10-25, Asia/Tokyo. Đã triển khai trong checkout local; không thay schema/index, không sửa dữ liệu collection hoặc deploy production.

## Thay đổi đã thực hiện

- **Selected deck:** admin đọc đúng subtree có quyền, không dựng lại toàn bộ 1.534 deck trong mẫu khảo sát. Nhánh learner giữ mixed visibility, ancestor rules và phạm vi install cũ.
- **Sidebar:** React gọi `GET /api/browse/decks?view=notes&structure_only=1` để lấy cây nhẹ trước. Counters và mixed-note-type metadata lấy riêng qua `GET /api/browse/decks/summaries?deck_ids=...`, tối đa 50 IDs/request, tối đa hai batch đồng thời ở client. Chỉ gửi selected deck và các nodes đang render theo trạng thái mở cây/tìm kiếm; không yêu cầu toàn bộ descendants đang đóng.
- **Summary scope:** backend đếm một lần trên hợp các subtree được yêu cầu, rồi roll up và chỉ trả các node được yêu cầu. Giữ nested-install precedence, persisted-map NoteType metadata, legacy missing-map fallback và fail-closed integrity. Mỗi ID được kiểm quyền; batch có ID không có quyền trả 404, không trả kết quả một phần.
- **Cache:** structure và từng summary có key riêng dưới `['browse', 'decks']`, nên invalidation cũ vẫn cập nhật cả hai. Chuyển trang không tải lại sidebar. Hủy một consumer không làm hủy batch còn consumer khác; hủy tất cả thì hủy request chung.
- **Editor clone:** compact GET không tải live source field JSON cho release-pinned Notes. Owned/snapshot fallback tải các cột values cùng `content_revision` trong một query; full detail, admin và mutation contracts giữ nguyên.
- **Pagination URL:** đọc `deck_id`, `page`, `per_page` ngay từ request đầu; Back/Forward khôi phục state; đổi deck/filter/sort/page size reset page atomically; search debounce dùng history replace; giữ Note/Card bookmark params.
- **Loading correctness:** chỉ giữ placeholder khi đổi trang trong cùng scope. Footer dùng page/page size của dữ liệu đang hiển thị; navigation tạm inert trong lúc chuyển trang. Đổi deck/filter không giữ rows của scope trước. Tạo Note và các công cụ phụ thuộc schema/count chờ summary đúng deck.
- **FSD:** logic cây/sidebar và scroll table ở hooks của Browse; API loader ở slice. Không thêm cross-feature import hoặc module mới trong root legacy helpers. Những primitive imports cũ vẫn được dùng; không di chuyển hệ primitive xuyên các feature trong task này.

API `/browse/decks?view=notes` đầy đủ và các Card/detail legacy vẫn giữ contract mặc định. Summary không trả lại `path`; client giữ path từ structure payload.

## Số đo kiểm chứng

MySQL local 8.0.40. Một lượt warmup có instrumentation và ba samples nhẹ hơn/case; cùng clock và dữ liệu. Mẫu A là admin user 1, mẫu B là learner user 20 có 7 installs. Chỉ đo service Python + SQL + serialization; không phải HTTP/load/browser latency.

Baseline chạy trong subprocess riêng bằng source của ba module backend trước thay đổi (`16e82f3b`, cùng blob tại `0b723b1f`); không đổi checkout. Các dependency khác dùng working tree hiện tại ở cả hai phía. Có các công việc/test ngoài task chạy cùng máy, nên latency chỉ là số đo tham khảo; bytes, query shape và payload parity là bằng chứng trực tiếp hơn.

| Phần | Trước | Sau | Diễn giải |
|---|---:|---:|---|
| Admin selected deck, 20 Notes: DB values trả về Python | 151.769 B | **44.128 B** | Giảm khoảng 71%; bỏ metadata toàn cây, vẫn trả cùng 20 rows |
| Cùng case: median service | 169,6 ms | **78,6 ms** | Payload hash giữ nguyên; số SQL 18 → 19 vì hai truy vấn subtree nhỏ thay một truy vấn collection rộng |
| A sidebar JSON ban đầu | 597.091 B | **205.927 B** | Structure-only, counters/type summaries tải riêng |
| A sidebar SQL ban đầu | 9 | **1** | Không chạy aggregate counters hoặc distinct NoteType distribution trong structure path |
| B sidebar JSON ban đầu | 113.595 B | **29.925 B** | Structure-only, không resolve/đếm mọi install ngay trong request cấu trúc |
| B sidebar SQL ban đầu | 58 | **4** | Scope cây vẫn cần owned/install/ancestor metadata |
| Clone editor: live Note content rows | 1 | **0** | Giữ một checkpoint content row của đúng Note và cùng response |
| Clone editor: DB values | 18.829 B | **17.883 B** | Giảm nhỏ ở một Note; không xem đây là thay đổi chính về latency |

Request structure mới có median A **73,8 ms**, B **32,9 ms**. Summary cho một deck mẫu 118 Notes có JSON A **363 B**, B **406 B**; median tương ứng **190,6/67,5 ms**. Summary vẫn giữ integrity và aggregate; không suy ra nó chỉ chạm đúng số Notes được trả ở list.

Sáu case có cùng response contract trước/sau đều giữ payload hash: selected list, editor, full sidebar ở cả A và B. B selected-list và full-sidebar có dao động thời gian dù số query/bytes không đổi; không ghi nhận đó là speedup do logic Browse này.

**Giới hạn:** tải root counters vẫn cần tổng hợp descendants, nên hợp các root đang render có thể phủ cả collection. Thay đổi làm cấu trúc/list tải độc lập, trả ít metadata hơn và giới hạn các lần đọc tiếp theo; không xóa mọi aggregate toàn collection. Exact count, sort, search và deep-page cost của list vẫn còn. Việc defer compact GET tạo thêm một grouped value query cho owned non-admin hoặc snapshot fallback; admin/full detail không chịu query thêm đó.

## Kiểm chứng

- MySQL: **29 distinct cases đạt** — 11 Note Browse hiện có, 10 scope/editor mới, 8 structure/summary/input mới. Hai assertion ở test editor được sửa để so compact contract thay vì full-only `updated_at`; ba lỗi fixture ở lượt đầu summary đã được sửa. Các case lỗi đều chạy lại thành công; không bỏ qua bằng cách skip.
- Frontend: focused Browse/page/bootstrap suites, typecheck, lint phần Browse và production Vite build. Kết quả lượt focused cuối được lưu trong evidence.
- API route snapshot khớp **304 routes**, có endpoint summaries mới. Kiểm tra bằng audit app không chạy startup maintenance hoặc SQLite integration.
- Browser: Chrome profile riêng `flama-browse-opt-20261025`, API fixtures thống nhất, before source snapshot và after checkout. Form create/edit ở **1440×1000** và **390×844**: **0 pixel khác biệt trong cả bốn cặp**, đã xem ảnh thực tế. Đây là visual verification với fixtures; MySQL correctness được kiểm riêng.
- Entry point thật: Flask `wsgi.py` chạy MySQL local với startup maintenance tắt; `/api/health` trả 200; hai đường deck mới trả 401 khi chưa đăng nhập. HTTP contract có đăng nhập/validation/quyền được kiểm trên schema MySQL riêng trong suite.

[Evidence số đo](BROWSE_OPTIMIZATION_IMPLEMENTATION_2026-10-25.evidence.json). Artifacts browser local: `output/playwright/browse-optimization-20261025/`; manifests MySQL local: `.tmp/browse-deck-summary-tests-final.json`, `.tmp/browse-scope-optimization-manifest.json`, `.tmp/browse-scope-editor-rerun-manifest.json`. Benchmark driver local: `.tmp/browse_optimization_benchmark.py`. Các file scratch không phải runtime dependencies.

Đã bổ sung các source/tests mới vào module `browse` của `scripts/run_tests.py`, giữ các thay đổi đã có của phiên khác. Không sửa hoặc hoàn tác các thay đổi đồng thời ngoài task ở models, stats/aggregation/share repositories và tài liệu khác. Không commit trong phiên này.
