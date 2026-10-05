# Review roadmap O(N) và phương án bảng count — 04/10/2026

**Kết luận: nên lên kế hoạch triển khai bảng tổng hợp lịch sử theo user/ngày.** Lợi ích đã có bằng chứng đọc; chi phí ghi, tính nhất quán và phạm vi tính toán cần kiểm chứng trước khi chuyển production. Bảng count trạng thái deck cũng đáng khảo sát, nhưng là read model khác, cần xử lý clock/due, scope và các thao tác thay đổi nội dung. Không dùng một bảng để thay cả hai.

Đây là review độc lập của tài liệu trong workspace `docs/plans/O_N_PERFORMANCE_INVESTIGATION_ROADMAP.md`, có tiêu đề **MASTER TECHNICAL REPORT & OPTIMIZATION ROADMAP: SYSTEMIC O(N) LINEAR PERFORMANCE BOTTLENECKS**. Giữ nguyên tài liệu đầu vào. Các SQL, schema và con số mục tiêu trong đó chưa đủ cơ sở để gọi là roadmap đã verified.

Trạng thái: **investigation + proof of concept**, chưa thêm bảng count vào schema ứng dụng, chưa đổi writer, chưa purge/archive dữ liệu hay deploy. Review runtime tại merge `e1ab03d` của PR [#210](https://github.com/TrinhChung/Flama/pull/210), cộng phần cleanup đang chuẩn bị trong nhánh `perf/post-decoupling-scaling-20261004`. Backend production lúc kiểm tra vẫn ở release `d747a5f`; baseline trước PR không phải kết quả sau triển khai.

## 1. Dữ liệu cũ có còn tham gia thuật toán không?

Nhận định đúng cho **bước trả lời thông thường**: scheduler dùng state hiện tại cùng policy/runtime; không cần quét toàn lịch sử của user để tính câu trả lời tiếp theo. Heatmap, thời gian học và streak là các consumer có thể thay phép gom lịch sử thô bằng summary.

Nhưng lịch sử không chỉ phục vụ hiển thị:

- [`study_algorithm_history_cut_service.py`](../../../app/services/study_algorithm_history_cut_service.py) đọc history facts và ReviewEvents của các sibling Cards để đóng băng evidence khi preflight chuyển thuật toán. Đây là chi phí theo lịch sử của Note trong một thao tác riêng, không phải mỗi rating.
- [`study_note_batch_service.py`](../../../app/services/study_note_batch_service.py) join ReviewEvent với command receipt để xác minh prefix/continuation của phiên. [`study_note_session_status_service.py`](../../../app/services/study_note_session_status_service.py) kiểm tra receipt của phiên đang mở; [`study_direct_note_replay_service.py`](../../../app/services/study_direct_note_replay_service.py) yêu cầu event/fact của request được replay còn tồn tại.
- [`anki_sync_service.py`](../../../app/services/anki_sync_service.py) giữ provenance/idempotency qua `ConnectReviewEventRef`. Ref đã imported được coi là đã xử lý khi `review_event_id` còn tồn tại, hoặc status là `ignored`.

**Bảng tổng hợp giảm đọc lặp cho analytics mà không đòi xóa các nguồn evidence trên.** Retention/archive cần thiết kế hợp đồng riêng nếu sau này dung lượng hoặc IO chứng minh nhu cầu.

## 2. Những gì đã đo và giới hạn của phép đo

### Production, chỉ đọc

Inventory lúc **22:22 JST, 04/10/2026**, dùng metadata và COUNT có index trong transaction READ ONLY; không khởi tạo Flask, không chạy DDL/DML. [Artifact](../../architecture/artifacts/count_rollup_production_inventory_20261004.json) có mốc giờ và cách đo.

| Hạng mục | Quan sát thực tế | Ý nghĩa |
|---|---|---|
| User 1, toàn lịch sử ReviewEvent | **118.359 events** | Trường hợp đủ lớn để tổng hợp có ích |
| User 1, năm học 2026 | **76.543 events** | Tokyo, boundary 04:00; range UTC `[2025-12-31 19:00, 2026-12-31 19:00)` |
| User có review | **6** | Chưa có số lượt đọc/ghi theo thời gian để tính break-even |
| Host/runtime | Ubuntu **22.04.5**, **2 vCPU**, khoảng **7,75 GiB RAM**; Gunicorn **2 workers × 4 threads, gthread**, systemd | Khác mô tả Ubuntu 24.04/Docker/4 GB/4 sync workers trong roadmap |
| MySQL | **8.0.46**, buffer pool **128 MiB** | Cần đo working set trước khi đề xuất tăng RAM/cache |
| ReviewEvent + receipts + history facts + audit logs | **240,70 MiB allocated data/index pages**, toàn DB | Không phải 600 MiB/100k reviews và không phải số byte đang nóng trong RAM |
| Receipts / history facts | Mỗi bảng khoảng **215 rows theo estimate** | Không thể giả định mọi imported/legacy review đã có một receipt và một fact |

Rows từ `information_schema.tables` là estimate; bytes là allocated pages, không phải logical row size hoặc RSS. COUNT User 1 là exact tại thời điểm đọc. **25,6 ms COUNT năm không phải latency query gom theo ngày**.

[Baseline production User 1](../../architecture/DASHBOARD_USER1_PERFORMANCE_INVESTIGATION_2026-10-04.md) ghi query history daily aggregate khoảng **250 ms**, query Dashboard counts khoảng **730 ms**. Đây là hai phép đọc khác nhau: daily rollup có thể giảm phần history của overview; không xóa 730 ms của count trạng thái deck. Không cộng các khoản này thành số giây giao diện chắc chắn sẽ tiết kiệm.

### Proof trên MySQL local

MySQL **8.0.40**, schema sinh ngẫu nhiên chỉ dành cho probe, 100.000 events giả lập trải trên 730 ngày, một user, năm 2026, Tokyo/04:00. Schema được drop trong `finally`; DB ứng dụng không bị sửa. Bảng nguồn tối giản và cache local khác production. Đo 5 lượt warm/case, bao gồm fetch vào client. [Artifact đầy đủ](../../architecture/artifacts/review_rollup_candidate_20261004.json).

| Tổng events nguồn | Events trong năm | Daily summary rows trong năm | Raw median | Summary median | Parity |
|---:|---:|---:|---:|---:|---|
| 4.000 | 1.826 | 365 | 7,79 ms | 3,32 ms | PASS |
| 40.000 | 19.927 | 365 | 76,23 ms | 3,31 ms | PASS |
| 100.000 | 49.997 | 365 | 193,64 ms | 4,50 ms | PASS |

Parity gồm số lượt review, tổng duration dương (NULL/âm → 0 trong aggregate) và counts rating good/easy của fixture. Duplicate/rollback chỉ là transaction sanity; **chưa chứng minh tích hợp writer hoặc concurrent idempotency**. Chưa đo write overhead, DST, đổi timezone/boundary, import lịch sử, scope theo deck hay crash của worker. EXPLAIN là estimate, không có counters actual rows examined/disk spill. Không suy ra production sẽ đọc summary trong 4,5 ms.

Để tránh so summary với raw query chưa được tối ưu, probe thứ hai kiểm tra thêm range index đang có và **covering index thử nghiệm** `(user_id, reviewed_at, duration_ms, rating)` trong schema disposable. [Artifact alternatives](../../architecture/artifacts/review_rollup_raw_alternatives_20261004.json):

| Tổng events | Raw optimizer chọn | Raw FORCE user/time index | Raw FORCE covering index | Summary |
|---:|---:|---:|---:|---:|
| 4.000 | 7,50 ms | 9,45 ms | 6,39 ms | 3,50 ms |
| 40.000 | 79,94 ms | 56,63 ms | 30,90 ms | 3,54 ms |
| 100.000 | 212,19 ms | 136,04 ms | 72,31 ms | 4,89 ms |

Forced covering có parity; index chỉ tạo/drop ở probe, chưa đo chi phí lưu/ghi của index đó. Các lượt local không cô lập tải máy nên latency minh họa, không là capacity test. Kết quả củng cố lợi ích summary ở dữ liệu lớn, đồng thời cho thấy **index có thể là phương án rẻ hơn về kiến trúc**; cần A/B index/cache/raw tại schema thực trước khi chốt rollout. FORCE INDEX chỉ dùng để so sánh, chưa đề xuất áp vào production.

## 3. Hai loại count cần phân biệt

| Read model | Nguồn đúng | Phép tính giảm | Chi phí còn lại |
|---|---|---|---|
| **Lịch sử theo ngày** | Các ReviewEvents đã accepted | History query `O(H_range)` → `O(A_range)`; collection/năm đọc tối đa 365/366 ngày | Ghi/thay đổi event; backfill; policy/timezone; streak dài có thể đọc nhiều năm |
| **Trạng thái hiện tại của deck** | Notes/Cards + Subject state + effective owned/installed scope | Count lặp `O(C_scope)` → đọc count theo `O(D_scope + B_due)` nếu read model đúng | Các thao tác đổi state/content; clock chuyển due; overlay; ancestor aggregation |
| **Chọn Card tiếp theo** | Availability + queue order + Card metadata | Giảm hydration và lọc candidate đúng scope | Count không cho biết Card nào đứng đầu; cần selection/index riêng |

`H`: history events; `A`: active days; `C`: Cards; `D`: decks; `B`: due buckets. Đây là số phần tử ở tầng ứng dụng/read model; B-tree lookup, join, sorting và IO có thêm chi phí. Không gọi mọi query có index hay mọi upsert là `O(1)`.

Heatmap có hai nguồn: **ngày đã học** lấy history và **ngày sẽ đến hạn** lấy state hiện tại. Summary lịch sử chỉ thay nguồn thứ nhất. Số "cards studied" hiện là số **ReviewEvent**, không phải unique Cards hoặc unique Notes; không đổi đơn vị khi tạo counter.

## 4. Thiết kế daily rollup đề xuất

Tên và schema dưới đây là candidate, chưa phải migration được chốt:

- Key logic: `(user_id, policy_version, scope_kind/scope_id, study_day)`. Policy version xác định timezone, day-boundary và quy tắc aggregate. Có thể thêm generation cho quá trình rebuild/publish.
- Các measures ban đầu: `total_review_events`, `total_positive_duration_ms`; thêm `passed_reviews`/review-kind counters nếu endpoint cần và semantic đã thống nhất. Không đặt `new_count/learn_count/review_count` mơ hồ rồi dùng lẫn với availability hiện tại.
- Có summary **collection riêng** và summary theo **deck snapshot của event**. Nếu dùng sentinel `scope_id=0`, không FK nó tới Deck; reader phải chọn đúng scope, tránh cộng collection vào deck totals. Event cũ có `deck_id=NULL` vẫn góp collection, không bịa attribution theo vị trí Card hiện nay.
- Query collection/năm đi thẳng qua collection rows, không SUM toàn bộ deck rows. Nếu đọc tất cả deck/ngày thì số rows vẫn có thể là `O(D_active × days)`.
- Giữ nguồn gốc, version, watermark và khả năng rebuild. Khi thiếu summary, policy mismatch hoặc drift thì fallback query gốc; không trả 0 để che lỗi.

### Ngày học và thay đổi timezone

[`stats_overview.py`](../../../app/services/stats_overview.py) và [`stats_query_repository.py`](../../../app/repositories/stats_query_repository.py) dùng timezone/boundary có hiệu lực **lúc query** để gom cả lịch sử. Gán `study_day` theo timezone lúc event được ghi rồi không đổi sẽ làm khác hợp đồng sau khi user đổi cài đặt.

Khởi đầu hợp lý: materialize một policy đang dùng của user, version hóa khi đổi setting; rebuild policy mới, publish generation hoàn chỉnh rồi mới phục vụ. Request dùng timezone khác hoặc đang rebuild fallback raw. Dùng các day-boundary helpers hiện có; không dùng fixed offset cho DST zones. Probe Tokyo fixed offset không thay thế tests DST.

### Cập nhật đồng bộ hay bất đồng bộ?

| Cách cập nhật | Lợi ích | Chi phí/cần chứng minh |
|---|---|---|
| **Cùng transaction với accepted ReviewEvent** | Đọc ngay sau trả lời thấy số mới; rollback atomic | Thêm upsert, user/day row thành điểm serialize giữa nhiều thiết bị và imports; đo p95 commit/lock waits |
| **Transactional outbox + worker gom batch** | Giảm thời gian giữ counter lock trong luồng trả lời; xử lý import theo batch | Có lag; cần dedup từng event, retries, watermark và fallback; outbox vẫn thêm write |
| **Rebuild dirty days theo job + cache có invalidation** | Ít thay writer lúc đầu; tiện backfill/shadow so sánh | Read freshness có giới hạn; chi phí `O(H)` chuyển sang job, không biến mất |

Khuyến nghị **shadow backfill + parity trước**, sau đó benchmark cập nhật đồng bộ được gom delta theo ngày trong từng batch. Chỉ chọn outbox nếu write contention/latency hoặc import throughput cho thấy cần; không thêm pipeline mới chỉ vì lý thuyết. MySQL upsert có khóa exclusive trên duplicate row, nên counter đúng transaction vẫn có thể là hotspot. [Tài liệu khóa InnoDB](https://dev.mysql.com/doc/refman/8.0/en/innodb-locks-set.html).

Idempotency phải bám **event thực sự mới được accepted**, không bám số lần nhận HTTP. Direct answer, offline commit/batch, worker, MCP, Anki/Connect và backfill đều phải nằm trong inventory writers. Duplicate, conflict, rollback hoặc ignored import không tăng counter. Sửa/xóa event hoặc đổi attribution cần delta bù hoặc đánh dấu dirty day. Không giả định một ORM listener bao phủ raw SQL/bulk jobs.

Worker không được checkpoint đơn giản bằng `MAX(auto_increment_id)`: transaction có ID nhỏ có thể commit sau ID lớn đã được xử lý. Dùng outbox được nhận/đánh dấu theo transaction, hoặc cơ chế overlap + dedup/checkpoint được chứng minh. Backfill đồng thời với live writes cũng cần snapshot/watermark/catch-up, tránh hụt hoặc đếm hai lần.

## 5. Count trạng thái deck: lợi ích lớn hơn nhưng khó hơn

Đây là candidate cho count query Dashboard khoảng 730 ms; chưa đủ bằng chứng để triển khai ngay. Direct counts nên tách theo learner, effective deck scope, authority mode và count unit. Card counts khác Note counts khi một Note có nhiều Templates; pristine Notes không state vẫn là NEW nếu có Card hợp lệ. Installed-source/local Cards và visibility giữ đúng overlay-only model.

Delta phải phủ: accepted answer, reset/suspend/bury/unbury, Note/Card tạo/xóa, Template thêm/xóa, di chuyển Note/deck, thay preset hoặc thuật toán, import, install/uninstall và cập nhật snapshot/overlay. Chỉ hook "answer" sẽ khiến Dashboard drift sau các thao tác còn lại.

**Due thay đổi khi đồng hồ chạy ngay cả lúc không có write.** Cần due-day buckets cho review, due-at cho learning, expiry của burial, `valid_until/next_due_change` hoặc day-roll/recompute đúng timezone. User đổi timezone/day-boundary cần invalidate/version. Bury/suspend và due-day precedence phải khớp query hiện tại. B_due trong trường hợp xấu có thể tăng theo số state khác nhau; không cam kết O(1).

Ưu tiên thử **revision + time-valid cache theo scope** và batch query đúng trước; nếu vẫn không đạt budget, thiết kế read model trực tiếp theo deck. Count ancestor có thể roll up trong cây `O(D)` khi đọc, hoặc cập nhật `O(depth)` lúc đổi; cân nhắc với tần suất move/clone. Chưa có lý do bắt buộc thêm closure table.

## 6. Các sửa đổi bắt buộc của MASTER roadmap

| Mức độ | Mục/nhận định | Phát hiện và điều chỉnh |
|---|---|---|
| **Chặn triển khai** | QW-4 purge receipt theo TTL 30 ngày | Receipt còn tham gia continuation/status/direct replay; chưa có hợp đồng hết hạn operation key/evidence. Không purge theo timestamp đơn lẻ |
| **Chặn triển khai** | INF-2 archive ReviewEvent rồi NULL FK | Inner join event→receipt và direct replay sẽ thiếu evidence. `ConnectReviewEventRef.review_event_id=NULL` có thể khiến lần sync sau import lại event. Phải có archive-aware replay/provenance hoặc tombstone contract trước |
| **Chặn SQL** | AR-3 CAST interval JSON sang DECIMAL | [`study_progress_shadow_codec.py`](../../../app/services/study_progress_shadow_codec.py) lưu `interval_days` dạng `f64:<16 hex>`. CAST không tính đúng load. Aggregation theo Subject còn làm sai Card weighting; không lọc 30 ngày vào phép load toàn scope |
| **Chặn parity** | AR-1 queue SQL / LIMIT 50 | `due_day IS NULL` không đồng nghĩa đã due khi `due_at` ở tương lai. Phải giữ strict/learn-ahead priority, review due-day precedence, burial, semantic-state distinction và ordering. Window bị lọc hết phải tiếp tục keyset, không trả complete giả; LIMIT không tự chứng minh query scan bounded |
| **Chặn scope** | QW-6 chỉ lọc Deck.owner_user_id | Accessible decks còn gồm deck có Notes của learner, ancestors, admin scope và installed overlays. Owner-only làm mất dữ liệu hợp lệ |
| **Sai mô hình chi phí** | RM-4 Dashboard `O(D×C)` | Backend dùng một grouped count, không chạy lại toàn Cards cho mỗi Deck. Tách `O(C)` scope/aggregation, `O(D)` rollup và chi phí DISTINCT/sort phụ thuộc plan; không chứng minh nhân D×C |
| **Cần sửa thiết kế** | AR-4 daily_rollups | Hướng tốt; bổ sung policy/generation, collection scope, event unit, late imports, writer coverage, drift/rebuild và duplicate semantics như phần 4 |
| **Cần sửa phạm vi** | Mỗi rating React gọi next/prefetch API | React v4 trả lời/lưu local và commit batch; REST direct-answer/MCP là path khác. Tối ưu queue có ích nhưng không quy toàn bộ chi phí đó cho mọi rating SPA |
| **Cần sửa dữ liệu** | 600 MiB/100k reviews, tất cả history đẩy hot pages khỏi buffer pool | Inventory chỉ khoảng 240,70 MiB của bốn bảng toàn DB; facts/receipts chưa tỷ lệ 1:1 trên lịch sử imported. InnoDB có scan resistance, `old_blocks_time=1000ms` đang bật; cần đo physical reads/miss, không suy từ kích thước bảng. [MySQL scan resistance](https://dev.mysql.com/doc/refman/8.0/en/innodb-performance-midpoint_insertion.html) |
| **Cần bỏ đảm bảo** | Index mới → hết filesort, 34 indexes → 34 page writes, flushes → fsync/IOPS cố định | Chưa đo physical counters. `Using filesort` có thể chạy trong RAM; compound index có thể hữu ích nhưng không bảo đảm hết GROUP BY sort. Đếm physical indexes bằng `COUNT(DISTINCT INDEX_NAME)`, không COUNT indexed columns. [MySQL ORDER BY](https://dev.mysql.com/doc/refman/8.0/en/order-by-optimization.html) |
| **Cần sửa byte/time** | 900 KB raw luôn mất 1,44 giây transfer | Baseline Dashboard raw 727 KB nhưng browser khoảng 78 KB compressed. Xác nhận encoding/wire bytes; không dùng raw payload làm network bytes |
| **Cần đổi trạng thái** | Mục tiêu <20/<50/<800 ms và "zero risk/verified" | Giữ làm budget acceptance có điều kiện, chưa phải kết quả. SQLite/local synthetic/build-size không chứng minh latency production, lock contention hay browser memory |

## 7. Roadmap theo bằng chứng và điều kiện chuyển bước

1. **Hoàn tất cleanup đã đo**: metadata opt-out, request-local artifact/runtime settings, Note membership maps, batched sibling reads, composition metadata, minimal queue refs, shared bootstrap/lazy assets. Báo cáo before/after và các vòng lặp còn lại trong [review cleanup](../../architecture/POST_DECOUPLING_PERFORMANCE_CLEANUP_REVIEW_2026-10-04.md). Đo Dashboard lại sau release chứa PR210/cleanup.
2. **Daily history rollup shadow**: schema/migration riêng; backfill có checkpoint, chạy raw + summary parity mà chưa đổi response; xử lý timezone/boundary, duplicate, import và rollback. Giữ ReviewEvent làm nguồn kiểm chứng.
3. **Đo read/write economics**: ghi số request history/ngày (R), accepted events/ngày (W), số upsert/batch, p50/p95 đọc/commit, lock waits/deadlocks, freshness và drift; so thêm raw query với candidate covering index và cache có invalidation. Savings xấp xỉ `R × (raw_read_cost − summary_read_cost) − W × extra_write_cost − rebuild/worker_cost`. Với User 1 đã có cơ sở cho khoản đọc; chưa có R/W để kết luận toàn hệ thống lời bao nhiêu CPU.
4. **Chuyển collection heatmap/today/history sang summary** khi parity, consistency và rollback đạt gate. Giữ fallback/version switch; tối ưu streak theo daily rows nhưng không cắt 30 ngày nếu API còn phải trả streak dài.
5. **Deck-state read model/queue selection** sau khi đo count query còn lại. Tách daily_load và due-window đúng codec/unit; thiết kế state counts với clock/invalidation. Đây là hạng mục riêng, không phụ thuộc xóa lịch sử.
6. **Retention/index/buffer pool** chỉ thay theo evidence và hợp đồng: load test/memory headroom, EXPLAIN actual, index consumer inventory, archive-aware correctness. Chưa có cơ sở triển khai purge receipt/archive facts của MASTER roadmap.

Gates tối thiểu của daily rollup: parity collection/deck/NULL-deck/multi-template; nhiều reviews cùng Card vẫn nhiều events; passed-ratings gồm cả `good/easy` và legacy `'3'/'4'` như query hiện tại; timezone/DST/boundary/year switch; duplicate/retry/rollback/concurrent commit; backdated imports; đổi attribution/xóa nếu được hỗ trợ; backfill/live race và worker crash; version mismatch/fallback; commit p95/lock budget do nhóm chốt sau baseline. Count cache/state model phải có thêm clock/bury/reset/overlay/template/move parity.

**Ưu tiên đề xuất:** triển khai thử daily history rollup có kiểm soát vì số đọc đã chứng minh lợi ích; khảo sát deck-state counters tiếp theo để xử lý phần count Dashboard. Giữ các mục archival và TTL receipt ngoài đợt tối ưu này cho tới khi có hợp đồng dữ liệu đầy đủ.

**Kế hoạch triển khai chi tiết ngày 05/10:** [Analytics count table design](../../architecture/ANALYTICS_COUNT_TABLE_DESIGN_2026-10-05.md) cụ thể hóa 3 bảng daily history, synchronous finalizer/SAVEPOINT, barrier backfill/verification/publish, 3 bảng deck snapshot/revision dự kiến, task theo PR, test matrix, acceptance gates và rollback. Đây vẫn là thiết kế đề xuất, chưa thêm schema hoặc triển khai runtime.
