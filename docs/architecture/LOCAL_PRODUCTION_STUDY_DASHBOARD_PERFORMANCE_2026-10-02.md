# Local / production: điều tra tốc độ dashboard và study Tettei N1

> Báo cáo lịch sử trước P10. SQL và số đo Dashboard hiện tại sau `CONSOLIDATED_V1` được kiểm chứng lại tại [điều tra User 1 ngày 04/10](DASHBOARD_USER1_PERFORMANCE_INVESTIGATION_2026-10-04.md).

> Ngày: 2026-10-02 (JST) | Mode: INVESTIGATE | Production: MySQL 8.0.46, release `438b2835bcf632b5eacec95e3ef9d7c19f272c44`
> Local: MySQL 8.0.40, DB `nihongo`, branch `refactor/fe-phase1-pilot-mcp-tokens`, HEAD `f1310b7`
> Phạm vi study được người dùng xác nhận: các deck Tettei N1.

## Kết quả chính

**Local hiện không đại diện cho đường chạy production.** Local ở migration 43, chưa có enrollment NOTE, các bảng canonical progress trống và các flag NOTE đều tắt. Production ở migration 47, 18/18 tài khoản NOTE, storage profile `PROJECTION_V1`, dữ liệu canonical đã backfill. Số thẻ và số deck của user 1 trên production cũng lớn hơn nhiều.

Dashboard production user 1 chậm chủ yếu ở SQL đọc NOTE trên toàn bộ bộ sưu tập. Đo cùng code, cùng dữ liệu, cùng VPS, đường đếm NOTE mất 2,47–3,10 s; đường đếm projection LEGACY mất 0,84–1,02 s, trả cùng số đếm trong mẫu này. Đây là phép đối chiếu chỉ đọc, không đổi enrollment và không phải đề xuất chuyển learner về LEGACY.

Study Tettei N1 có thêm chi phí mở phiên NOTE, dựng artifact và nhiều bước mạng liên tiếp. Bài 046 và 137 có 60 thẻ/bài; không phải deck hàng nghìn thẻ. Chưa có bằng chứng trong mẫu hiện tại cho timeout hàng chục giây của các bài này. Log thực tế cho bài 046 ngày 02/10 cho thấy lấy composition và mở phiên xong trong khoảng 2 giây theo độ phân giải giây của nginx; dashboard cùng phiên mất khoảng 4 giây từ preflight đến phản hồi.

## Cách đo và giới hạn

- SSH đọc release, env theo allowlist, thông số MySQL, `EXPLAIN`, processlist, `performance_schema`, log nginx và journal. Không xuất password, secret, cookie hoặc nội dung thẻ vào log/báo cáo.
- Profiling service dùng `create_audit_app()`, tắt toàn bộ startup maintenance; tự đăng ký blueprint chỉ để resolve URL. Kết nối MySQL đặt `SET SESSION TRANSACTION READ ONLY`, xác minh `@@transaction_read_only=1`, chặn DML và locking SELECT bằng SQLAlchemy listener. Transaction analytics rollback sau mỗi mẫu.
- GET qua HTTPS production dùng cookie chẩn đoán ký trong bộ nhớ, không lưu cookie/secret ra file. Chỉ gọi dashboard, compositions và health. Không tạo phiên study hay gửi review trên production.
- Benchmark session NOTE 60 và 500 thẻ chạy bằng script có sẵn trên hai database local ngẫu nhiên, được script tạo và xóa; DB ứng dụng `nihongo` không bị thay đổi.
- Mỗi endpoint/service chỉ đo hai lượt; đây không phải p95 hoặc đo dưới tải. Không gọi lượt đầu là cold cache vì không reset cache.
- Chưa đo trình duyệt của người dùng, IndexedDB, render UI, hay full POST session trên production. Profiling artifact và benchmark local không thay thế được số đo full POST đó.
- Các bảng `TABLE_ROWS`/kích thước lấy từ information_schema là ước lượng; các số thẻ theo user và Tettei được đếm bằng SELECT trực tiếp.

## Những khác biệt đã xác minh

| Hạng mục | Local | Production |
|---|---|---|
| Code | HEAD `f1310b7`, branch refactor frontend | Release `438b283`, PR #188 |
| Alembic | `20260921_000043` | `20261001_000047` |
| Enrollment NOTE | 0 dòng; user 1 dùng LEGACY | 18/18 tài khoản NOTE |
| Storage profile | Chưa có bảng migration 47 | `PROJECTION_V1`, epoch 1 |
| Wire v4 / new learner NOTE / note count / shadow write | Cả bốn `false` | Cả bốn `true` |
| Async batch | `false` | `false` |
| Canonical subject/state/contributor/availability | Trống | Khoảng 36–38 nghìn dòng mỗi bảng (ước lượng) |
| Thẻ sở hữu bởi user 1 | 22.041 | 39.282 |
| Deck chứa note của user 1 | 429 | 1.464 |
| CardProgress user 1 | 11.254 | 39.282 |
| ReviewEvent toàn DB | 61.842 | 129.469 |
| MySQL buffer pool | 128 MiB | 128 MiB |
| CPU / RAM máy | 16 logical CPU / khoảng 15,4 GiB | 2 vCPU / khoảng 7,8 GiB |
| API transport | Vite proxy cùng origin tới `127.0.0.1:4789` | `flama.stmtp.com` → HTTPS `be-flama.stmtp.com` → nginx → Gunicorn |

Hash nội dung `app/settings.py` và `app/services/dashboard_service.py` trùng giữa hai môi trường. Reader NOTE, aggregation, stats và session service có khác biệt code. Diff local so với release production chủ yếu bỏ hỗ trợ `CANONICAL_V1` và đổi xử lý commit replay; profile production vẫn là `PROJECTION_V1`, nên không thể quy toàn bộ độ chậm cho chênh lệch code này. Khác biệt đường thực thi LEGACY/NOTE là bằng chứng mạnh hơn.

## Đo service và API

### Service trên dữ liệu thật, SQL READ ONLY

| Mẫu | Lượt 1 | Lượt 2 | SQL/lượt |
|---|---:|---:|---:|
| Local user 1 dashboard | 0,847 s | 0,376 s | 10 |
| Production user 1 dashboard | 3,715 s | 2,582 s | 13 |
| Local user 1 overview | 0,504 s | 0,323 s | 7 |
| Production user 1 overview | 2,524 s | 2,172 s | 9 |
| Production user 4 dashboard (có overlay) | 1,347 s | 0,973 s | 17 |
| Production user 4 overview | 0,383 s | 0,201 s | 9 |

User 1 production, dashboard lượt 2: 2,312/2,582 s nằm trong SQL. Câu aggregation 8 bảng mất 1,352 s; kiểm tra vector contributor/live Card mất 0,672 s; xác định note type/deck mất 0,209 s. Overview lượt 2: 1,965/2,172 s nằm trong SQL; đọc canonical availability mất 1,250 s và kiểm vector mất 0,354 s.

### Đối chiếu đường đếm trên cùng dữ liệu production user 1

Chỉ gọi `aggregate_deck_study_counts()` với tham số đọc khác nhau, không đổi cấu hình hoặc dữ liệu. Cả hai trả total 39.282, new 24.036, learn 2.084, due 12.903 ở thời điểm đo.

| Đường đếm | Lượt 1 | Lượt 2 | Logical buffer reads lượt 2 | Physical reads lượt 2 |
|---|---:|---:|---:|---:|
| Projection LEGACY | 1,015 s | 0,841 s | 603.277 | 8.019 |
| NOTE + kiểm evidence | 3,096 s | 2,466 s | 1.948.764 | 20.738 |

Counters là delta global MySQL trong mỗi lượt, nên vẫn có thể chứa hoạt động của connection khác. Processlist lúc lấy mẫu không có truy vấn ứng dụng dài hoặc chờ khóa; VPS load average khoảng 0,16.

### API HTTPS từ máy local, kết nối TLS tái sử dụng

| API user 1 | OPTIONS lượt 1 / 2 | GET lượt 1 / 2 | JSON sau giải nén |
|---|---|---|---:|
| Tettei bài 046 compositions | 0,567 / 0,149 s | 0,614 / 0,249 s | 1.860 byte |
| Dashboard | 0,492 / 0,301 s | 4,308 / 3,344 s | 727.689 byte |
| Health | 0,296 / 0,102 s | 0,313 / 0,107 s | 16 byte |

Dashboard HTTP chậm 3,65–4,80 s khi cộng preflight trong hai mẫu. Nginx/Cloudflare có gzip trong phản hồi thực tế; không có bằng chứng JSON đang truyền hoàn toàn không nén. Service timing không bao gồm toàn bộ JSON serialization, nén và truyền tải; do các lượt khác nhau, không lấy chênh lệch HTTP/service làm số đo riêng chính xác của mạng.

## Findings

### F1 — Local chưa chạy đường NOTE của production

- **Observed:** Local chưa enroll và canonical tables trống; production đã enroll toàn bộ. Cùng hàm dashboard rẽ sang hai đường SQL khác nhau.
- **Evidence:** Alembic, SELECT enrollment/progress; `app/services/dashboard_service.py:67`, `app/services/deck_aggregation_service.py:181`, `app/services/stats_overview.py:413`.
- **Potential concern:** Test thủ công local nhanh không kiểm chứng hiệu năng NOTE với dữ liệu đã backfill.
- **Impact:** Kết quả local che khuất chi phí join và kiểm integrity ở production. Cùng dữ liệu/VPS, đường NOTE chậm gần 3 lần đường projection.
- **Unknowns:** Chưa có môi trường staging cùng schema/enrollment và phân phối dữ liệu production.

### F2 — Mỗi dashboard/overview kiểm tra toàn bộ bộ sưu tập NOTE

- **Observed:** Aggregation join Card, Note, subject, state, token, contributor, availability và projection. Sau đó có thêm kiểm tra số contributor so với live Card. Overview dựng scope bằng UNION stateful/projection và đọc từng row availability về Python.
- **Evidence:** `app/repositories/note_analytics_read_repository.py:62`, `:161`, `:194`; `app/services/deck_aggregation_service.py:230`; `app/services/stats_overview.py:172`. EXPLAIN production: join phần lớn dùng `ref`/`eq_ref`; vector check có `DEPENDENT SUBQUERY`; overview UNION có `Using temporary`.
- **Potential concern:** Số câu SQL hằng số vẫn có chi phí O(collection). Trong câu vector check, hai correlated COUNT chạy theo subject. Các bảng đã có index; chưa có bằng chứng một index bị thiếu là nguyên nhân chính.
- **Impact:** User 1 phải xử lý khoảng 39 nghìn thẻ và nhiều lookup mỗi lần mở dashboard. Hai endpoint dashboard/overview được frontend gọi cùng lượt, cùng chạm các bảng lớn.
- **Unknowns:** p95 khi dashboard và study mở đồng thời, nhu cầu giữ toàn bộ kiểm integrity trong mỗi GET. Tính nhất quán của NOTE vẫn phải được bảo toàn trong mọi tối ưu tiếp theo.

### F3 — Buffer pool production quá nhỏ so với tập dữ liệu đang đọc

- **Observed:** Pool 128 MiB; toàn DB khoảng 1.309 MiB; riêng notes 123 MiB, review_events 189 MiB, contributors 59 MiB, cards 43 MiB, projection 33 MiB, subject/state mỗi bảng 24 MiB. VPS có khoảng 5,6 GiB available tại lúc đo. NOTE aggregation lượt 2 làm khoảng 20.738 physical reads.
- **Evidence:** SHOW VARIABLES/STATUS, information_schema, `free -m`; delta cùng workload ở bảng đối chiếu.
- **Potential concern:** Dữ liệu và index cần cho lượt đếm lớn hơn pool; nhiều lookup không nằm trong cache InnoDB. Buffer pool cache dữ liệu/index theo [MySQL 8.0 documentation](https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool.html).
- **Impact:** Là yếu tố khuếch đại chi phí SQL đã đo, dù VPS không hết RAM và không quá tải CPU ở thời điểm lấy mẫu.
- **Unknowns:** Mức cải thiện khi tăng pool chưa được A/B; ngân sách RAM dài hạn của các dịch vụ cùng VPS. Chưa thay đổi cấu hình MySQL.

### F4 — Study Tettei có bước mạng nối tiếp và template bị xử lý lặp

- **Observed:** Tettei root `415` (`語彙徹底N1`) có 170 deck con, 10.148 note; bài 046 (`461`) và 137 (`552`) có 60 thẻ. Mở mới trên React lần lượt: bootstrap/lease → compositions GET → session POST → lưu IndexedDB → render. API client gửi `X-Timezone`; production khác origin nên có OPTIONS. `app/cors.py` không đặt `Access-Control-Max-Age` (browser chỉ còn cache preflight mặc định). Local qua Vite proxy cùng origin.
- **Evidence:** `frontend/src/features/study/hooks/useStudySession.ts:272`, `:373`, `:391`; `frontend/src/shared/api/client.ts:114`; `app/cors.py:36`; `frontend/vite.config.ts:16`; HTTPS timings và nginx OPTIONS thật.
- **Potential concern:** Các bước network không thể gộp thời gian bằng cách chạy đồng thời theo luồng hiện tại. Artifact builder xử lý/sanitize cùng template 60 lần rồi mới deduplicate bằng `setdefault`.
- **Impact:** Composition GET + OPTIONS mất 0,40–1,18 s trong hai mẫu, trước session POST. Read-only artifact profiling trên dữ liệu Tettei thật: nạp 60 thẻ 0,07–0,51 s; dựng template/content không bật profiler 0,44–0,48 s. Có đúng 1 template version trong mỗi bài nhưng gọi builder 60 lần; dựng một template khoảng 5–6 ms. cProfile cho thấy sanitizer HTML chiếm phần lớn thời gian template builder, nhưng số đo có profiler không được xem là latency thông thường.
- **Unknowns:** Full POST production, thời gian IndexedDB/browser render và lần chậm cụ thể người dùng gặp. Chưa xác định tỉ trọng I/O ghi pins/lease hoặc chờ writer trong lần đó.

### F5 — N+1 lớn cũ của session open đã được sửa

- **Observed:** Code production đã có eager loading, cache deck/options theo request và bulk insert session cards. Benchmark local NOTE hiện tại: 60 thẻ 0,159–0,224 s, 500 thẻ 0,980–1,056 s, cả hai 43 SQL/lượt. Benchmark dùng template rất đơn giản, không phải dữ liệu Tettei.
- **Evidence:** `app/services/study_session_service.py:578`, `:606`, `:941`; `scripts/bench_p5_session_open_mysql.py`. Mẫu production Tettei bài 046 ngày 02/10: compositions GET/OPTIONS POST kết thúc 10:20:04 JST; POST 201 kết thúc 10:20:06 JST, body 384.687 byte. Dashboard sau đó: OPTIONS 10:20:24, GET 200 10:20:28 JST.
- **Potential concern:** Không được dùng báo cáo 29/09 (~8 SQL/thẻ) làm mô tả code hiện tại. Vẫn tải toàn bộ scope thay vì chỉ hàng đợi cần học, nhưng các bài Tettei được kiểm tra nhỏ hơn nhiều giới hạn 5.000 thẻ.
- **Impact:** Bằng chứng hiện tại phù hợp với chậm vài giây do nhiều lớp chi phí; chưa xác nhận sự cố timeout 60 giây tái diễn. Mẫu nginx không có request_time, khoảng cách OPTIONS/POST chỉ là timeline có độ phân giải giây.
- **Unknowns:** Backend p95 của session open và study browser waterfall khi xuất hiện sự cố.

## Hướng xử lý tiếp theo, chưa triển khai

1. Lập A/B tăng buffer pool production trong ngân sách RAM đã kiểm tra, đo lại chính các workload ở báo cáo. Mức 1–2 GiB là ứng viên để kiểm chứng, chưa phải giá trị đã chứng minh tối ưu. Đây là yếu tố vận hành có delta physical reads rõ nhất.
2. Tối ưu đường đếm NOTE và vector check theo tập dữ liệu, giữ nguyên integrity, ownership, timezone và overlay; đặc biệt correlated COUNT, scope UNION và việc hai endpoint lặp kiểm tra toàn collection. Kiểm chứng bằng EXPLAIN và số đo cùng dataset, không tắt NOTE để làm số đo đẹp hơn.
3. Study: tái sử dụng template artifact trong request theo template/schema hiệu lực, giữ sanitization; xem xét cache preflight có thời hạn và giảm bước discovery phải chờ trước POST. Cần benchmark đúng Tettei trước/sau.
4. Đưa local/staging về một fixture cách ly có schema 47, NOTE enrollment và dữ liệu tương đương; dùng profiler/browser với profile Chrome riêng, đo đầy đủ các bước study và dashboard. Không nâng cấp trực tiếp DB local hiện tại chỉ để phục vụ phép đo này.
5. Nếu lần người dùng gặp dài hàng chục giây, cần timestamp/deck/account và waterfall đúng lần đó; các mẫu hiện tại chưa đủ kết luận nguyên nhân cho độ trễ lớn như vậy. Nginx đang dùng access log mặc định, thiếu request_time/upstream_response_time.

## Trạng thái sau điều tra

- Chưa sửa app, migration, cấu hình hoặc dữ liệu production; không restart/deploy dịch vụ.
- Hai database benchmark local đã được xóa bởi `finally` của script. Không chạy full test suite vì không có thay đổi runtime.
- Script và output đo nằm trong `output/perf_*_20261002*` (gitignored). Báo cáo này là artifact được lưu trong repo.
- Sự cố bản sửa dashboard chưa deploy của 30/09 đã đóng ở release #173; production hiện chạy #188 và dùng analytics read-only. Không có căn cứ xem đó là nguyên nhân lần này.
