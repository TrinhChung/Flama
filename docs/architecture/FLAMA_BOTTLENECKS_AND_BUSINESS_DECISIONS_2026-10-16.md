# Flama: điểm nghẽn và nghiệp vụ cần quyết định

Ngày rà soát: **16/10/2026, Asia/Tokyo**. Mục đích: quyết định phạm vi sản phẩm trong ngân sách thấp.

**Trạng thái: báo cáo điều tra và đề xuất, chưa phê duyệt cắt giảm tính năng.** Đợt rà soát chỉ thêm tài liệu và bằng chứng; không sửa ứng dụng, cấu hình, dữ liệu hay deployment.

## 1. Kết luận dành cho chủ sản phẩm

**Có cơ sở để tiếp tục Flama theo hướng miễn phí, tập trung vào flashcard động. Chưa có cơ sở để cam kết sức chứa người dùng hoặc chi phí vận hành khi mở rộng.** Repo có nhiều biện pháp bảo vệ dữ liệu và tối ưu đã triển khai. Điểm cần xử lý trước là sự lệch nhau giữa lời hứa sản phẩm, giới hạn sử dụng và chi phí của các luồng phụ.

Ưu tiên được chủ sản phẩm xác nhận trong cuộc trao đổi này:

1. Giai đoạn đầu cho người dùng sử dụng miễn phí các tính năng được cung cấp để thu hút người dùng.
2. Giữ lõi: thêm/sửa/xóa nội dung, các chế độ học, thuật toán ôn tập, quản lý bộ thẻ.
3. Đóng góp bộ thẻ và version có giá trị nhưng được phép xếp sau lõi nếu tài nguyên không đủ.
4. Những phần còn lại có thể cân nhắc hy sinh; **từng thay đổi làm giảm khả năng sử dụng phải báo cáo tác động và được phê duyệt**.

Năm quyết định nên giải quyết trước:

| Thứ tự | Vấn đề | Đề xuất để quyết định | Điều chưa được phép suy ra |
|---|---|---|---|
| 1 | Quota API có thể chặn CRUD; phạm vi áp dụng giữa các blueprint chưa đồng nhất | Chốt fair-use phù hợp với sử dụng miễn phí; ưu tiên bảo vệ thao tác lõi | Miễn phí không tự đồng nghĩa vô hạn tài nguyên; không suy ra mọi lượt học đều bị đếm quota |
| 2 | Auto-publish có thể kéo theo cập nhật mọi subscriber trong luồng ghi | Ưu tiên phát hành/cập nhật thủ công nếu cần giảm tải | Không xóa release/pin/overlay đang phục vụ bộ thẻ đã cài |
| 3 | Chưa có ngân sách dung lượng xuyên suốt các đường upload và dữ liệu lịch sử | Đo tăng trưởng, chốt chính sách; chưa xóa dữ liệu để giải phóng disk | Giới hạn 10 MiB/file hoặc 512 MiB ở Connect không phải quota tổng toàn hệ thống |
-> hiện khi dùng connect đang để 512 do chức năng này có thể upload cả video nhưng nên điều tra sau cũng được hiện tại cứ tạm thời để như vậy. 
| 4 | Phạm vi thuật toán và tiến độ giữa các chế độ dễ bị hiểu quá mức | Công bố chính xác thuật toán đang chạy và việc dùng chung tiến độ Note | Có trường FSRS hoặc test adapter không chứng minh FSRS hoàn chỉnh |
| 5 | Luồng admin thanh toán có sai lệch đã tái hiện | Trong chiến lược miễn phí, cân nhắc đóng nhận giao dịch mới; vẫn xử lý nghĩa vụ cũ nếu có | Tắt nút mua không giải quyết đơn đã trả tiền, entitlement và số dư tác giả |

**Khuyến nghị phân bổ công sức:** ổn định lõi và bảo toàn dữ liệu → đo tài nguyên thực → giảm tự động hóa/phạm vi phụ → chỉ đầu tư mở rộng khi có bằng chứng nhu cầu. Chưa có bằng chứng cần tách microservice hay thay database để giải quyết giai đoạn này.

## 2. Phạm vi và mức độ tin cậy

- Bắt đầu trên working tree tại base commit `033dd94af05e597e8de3a59bafe1355ae7e8d739`, có nhiều thay đổi chưa commit từ trước. Trong lúc rà soát, các thay đổi được một tiến trình khác commit thành `1eca44cbd83234ce5bb708770b0a24b946ddf773`; lần kiểm tra cuối và hash nguồn gắn với commit này. Đợt rà soát không chạy lệnh commit. Kết luận áp dụng cho snapshot trong workspace, **không mặc định là code đang chạy trên VPS**. Hash các file trọng yếu nằm trong [bằng chứng rà soát](artifacts/flama_decision_audit_20261016.json).
- Đã đối chiếu startup/deploy, CRUD/browse, study/scheduler, release/overlay/contribution, analytics, media/import/TTS, payment/wallet, onboarding và CI. Đây là rà soát có trọng điểm; không phải chứng nhận toàn bộ bảo mật hoặc toàn bộ tổ hợp tính năng.
- Đã chạy **121 test backend trong 13 file**, đều đạt; có thêm probe trên SQLite in-memory với dữ liệu giả. Không benchmark lại MySQL, không load-test production, không thực hiện giao dịch thật hoặc truy cập VPS.
- Không đọc/báo cáo thông tin đăng nhập hoặc nội dung học riêng. Số đo MySQL cũ dưới đây được ghi rõ là bằng chứng lịch sử trong repo.

Nhãn sử dụng:

| Nhãn | Nghĩa |
|---|---|
| **Tái hiện** | Đã thực thi tình huống cụ thể trong đợt rà soát này |
| **Code** | Đường thực thi hoặc giới hạn được xác nhận qua code; chưa định lượng tác động production |
| **Lịch sử local** | Số đo từ tài liệu/artifact trước đó; chưa chạy lại hôm nay |
| **Chưa biết** | Thiếu dữ liệu hoặc quyết định; không được trình bày thành lỗi/sự cố đã xảy ra |

Mức ưu tiên: **P0** cần giải quyết trước khi cho luồng liên quan hoạt động rộng; **P1** cần chốt cho giai đoạn thu hút người dùng; **P2** có thể trì hoãn có chủ đích. Mức ưu tiên phản ánh tác động trong định hướng đã xác nhận, không phải khẳng định đang có sự cố production.

## 3. Các nguồn dữ liệu chuẩn cần bảo vệ

| Dữ liệu | Nguồn chuẩn hiện tại | Ý nghĩa khi cân nhắc cắt giảm |
|---|---|---|
| Nội dung Note | `Note.field_values_by_id`, codec `field-id.v1`; tên field được chiếu ra ở boundary | Không chuyển list thành chuỗi, không quay lại lưu theo tên field để giảm công việc |
| Field identity | Field definitions và ledger identity/retirement | Ledger có vai trò đọc đúng nội dung; không coi là cache có thể xóa |
| Card | Presentation dẫn xuất từ Note × StudyApplication; alias lưu ID lịch sử | Không đánh giá số dòng bảng `cards` theo kiến trúc cũ; không cần materialize lại Card |
| Tiến độ học | `StudyProgressSubject` theo learner/logical Note, profile `CONSOLIDATED_V1` | Một presentation/mode mới không mặc định có tiến độ riêng |
| Lịch sử và chống ghi lặp | Review events, history/lifecycle facts, command receipts, session/batch contracts | Không xóa như cache chỉ vì bảng lớn |
| Bộ thẻ đã cài | Release đã áp dụng + template pins + overlay cá nhân + lineage nguồn | Hoãn cập nhật mới vẫn phải giữ khả năng học ở release đang dùng |
| Counts/forecast/history summary | Snapshot, daily buckets, generations và outbox xử lý projection | Là dữ liệu dẫn xuất; có thể trì hoãn hiển thị nếu có thông báo và hợp đồng rõ |
| Giao dịch | Order/attempt/webhook, entitlement và ledger số dư | Trạng thái hiển thị không thay thế việc đối soát hoặc chuyển tiền |

Nguồn: [Note](../../models/note.py), [Field ledger](../../models/field_value_identity_definition.py), [Card dẫn xuất](../../models/card.py), [application](../../models/study_application.py), [progress subject](../../models/study_progress_subject.py), [review event](../../models/review_event.py), [install](../../models/deck_install.py), [analytics](../../models/review_analytics.py), [payment order](../../models/payment_order.py), [ledger](../../models/user_balance_transaction.py).

## 4. Điểm nghẽn và rủi ro có bằng chứng

### F01 — Quota request hiện có thể cắt ngang tính năng lõi

- **Quan sát — Tái hiện/Code:** Guard của blueprint `api_v1` dưới `/api` đếm cả GET và mutation của người đã đăng nhập, trừ một số đường ngoại lệ. Regular mặc định 300 request/ngày; Creator 2.000; Enterprise 10.000; Admin được bỏ qua. Tuy nhiên, các endpoint Study session nằm ở blueprint `flashcards` riêng, không đi qua guard này. Test thường tự tắt quota trừ khi bật rõ.
- **Bằng chứng:** [API guard](../../app/api/v1/__init__.py#L43), [quota service](../../app/services/daily_rate_limit_service.py#L105), [defaults](../../app/settings.py#L305), [Study route](../../app/routes/flashcards/study.py#L773). Probe đặt quota = 2: hai lần GET note types trả `200`, POST tạo note type tiếp theo trả `429 RATE_LIMIT_EXCEEDED`. Probe bổ sung khi quota đã hết vẫn đi tới validation của endpoint mở Study session (`400`, không có rate-limit header); không coi payload sai đó là phiên học thành công.
- **Nguy cơ:** Hoạt động xem/tải dữ liệu thuộc blueprint mới và dùng MCP có thể tiêu cùng ngân sách với CRUD. Số request không tương đương số thẻ học; không thể lấy quota này làm giới hạn toàn bộ tài nguyên Study. Local fallback khi Redis lỗi làm giới hạn phụ thuộc process.
- **Tác động:** Người dùng miễn phí có thể không tạo/sửa nội dung tiếp được dù không làm thao tác đắt tiền, trong khi một số luồng nặng không chịu cùng guard. Đây là xung đột sản phẩm và coverage, không chỉ vấn đề tăng tốc SQL. Không kết luận mọi lượt học/commit bị tính hoặc chặn bởi quota này.
- **Chưa biết:** Effective quota production, số request trung bình của một phiên học thực tế, lượng request lặp do refetch/polling.
- **Ưu tiên:** P0 trước mở rộng sử dụng lõi. Cần phê duyệt chính sách fair-use mới; không tự bỏ các biện pháp chống lạm dụng/login throttling.

### F02 — Auto-publish và auto-update gắn chi phí cộng đồng vào luồng ghi

- **Quan sát — Code:** Khi bật auto-publish, sửa field/nội dung/presentation có thể kích hoạt publish ngay trong transaction của writer. Publish gọi `process_subscriber_auto_updates()`: lấy toàn bộ install bật auto-update rồi tuần tự prepare/apply từng install. Không thấy giới hạn số subscriber hoặc time budget trong hàm này. Hai cờ đều mặc định tắt.
- **Bằng chứng:** [writer trigger](../../app/services/deck_working_tree_service.py#L235), [presentation commit hook](../../app/services/deck_working_tree_service.py#L84), [auto-publish](../../app/services/deck_auto_publish_service.py#L116), [subscriber loop](../../app/services/deck_install_rebase_service.py#L1142), [default](../../models/deck_marketplace_item.py#L130).
- **Nguy cơ:** Một thao tác sửa của tác giả phát sinh công việc tỷ lệ với số người bật tự cập nhật và độ phức tạp overlay. Chi phí không còn chỉ phụ thuộc một Note vừa sửa. Việc bắt exception/ghi lỗi không tạo ra hàng đợi nền hay giới hạn tải.
- **Tác động:** Có thể kéo dài transaction, giữ connection/lock và tăng độ trễ CRUD khi bộ thẻ phổ biến. Chưa chứng minh đây đang là request chậm trên production.
- **Chưa biết:** Số cờ đang bật, subscriber/deck, độ trễ prepare/apply, lock waits và lỗi thực tế.
- **Ưu tiên:** P1 có điều kiện. Đây là ứng viên cắt tự động hóa trước khi cắt chế độ học: giữ phát hành cơ bản và cài miễn phí, cân nhắc cập nhật thủ công.
được nếu vậy có thể tạm thời ẩn đi để tối ưu sau hiện tại chỉ có dugnf thủ công. 

### F03 — Thống kê đã được tối ưu nhưng đường chậm vẫn tồn tại

- **Quan sát — Code/Lịch sử local:** Đã có summary/outbox/count/forecast workers. Cấu hình mặc định đọc `raw`, writer tắt. Trong summary mode, snapshot không hợp lệ có thể quay về raw; nhóm người dùng bật strict readiness nhận trạng thái đang cập nhật thay vì raw. Forecast prewarm hiện quét dữ liệu của scope để dựng lại bucket.
- **Bằng chứng:** [settings](../../app/settings.py#L151), [forecast resolver/build](../../app/services/forecast_snapshot_service.py#L49), [raw fallback](../../app/services/stats_today_future.py#L392), [strict readiness](../../app/services/analytics_summary_readiness.py), [prewarm unit](../../deploy/flama-analytics-counts.service).
- **Số đo lịch sử:** Báo cáo local ở fixture head64 ghi overview p95 **1.955,53 → 77,35 ms**, today/future **2.420,15 → 64,26 ms**, dashboard 1.537 deck **1.668,78 → 374,98 ms**. Đây không phải đo lại ở working tree hôm nay hoặc production. [Nguồn và giới hạn](DATABASE_PROGRESS_SCALABILITY_IMPLEMENTATION_2026-10-14.md#L76).
- **Nguy cơ:** Mỗi review thay dependency stamp; cache hit rate khi người dùng đang học có thể khác fixture đứng yên. Prewarm có danh sách người dùng/caps chưa chứng minh tự bao phủ toàn bộ người mới đăng ký. Budget 4.096 bucket không giới hạn tổng dữ liệu phải đọc để dựng scope.
- **Tác động:** Dashboard/forecast nặng có thể tranh tài nguyên với học; summary không tự bảo đảm mọi request đều nhẹ.
- **Chưa biết:** Cờ và cohort production, cache hit/miss, thời gian rebuild, số user được phục vụ đúng hạn, CPU/I/O lúc học liên tục.
- **Ưu tiên:** P1. Có thể đề xuất giảm lịch sử/forecast nâng cao hoặc hiển thị pending, nhưng cần giữ due/queue phục vụ học đúng. Chỉ thu ngắn biểu đồ ở UI chưa chắc giảm được truy vấn phía server.

### F04 — Retention còn thiếu ở một số dữ liệu tăng theo thời gian

- **Quan sát — Code/Lịch sử local:** Outbox xử lý xong đặt `applied_at` nhưng giữ payload; generation cũ chuyển `RETIRED`; forecast cùng scope được ghi đè nhưng scope cũ chưa có eviction tổng thể. Session retention đã có nhưng không dọn toàn bộ lịch sử, receipts hoặc Field archive.
- **Bằng chứng:** [outbox worker](../../app/services/review_analytics_outbox_service.py#L195), [backfill](../../app/services/review_analytics_backfill_service.py), [forecast persistence](../../app/repositories/forecast_snapshot_repository.py), [session retention runbook](../runbooks/P7_SESSION_RETENTION_RUNBOOK.md), [review dung lượng ngày 15/10](CACHE_STORAGE_GROWTH_REVIEW_2026-10-15.md).
- **Số đo lịch sử:** Báo cáo local ngày 15/10 ghi Field archive **75.468 object, DATA_LENGTH khoảng 1,28 GiB**; các bảng summary/cache/outbox được nêu khi đó có **0 hàng**. Không sử dụng số này như số đo production hoặc tổng dung lượng hiện tại.
- **Nguy cơ:** Disk, index, backup và thời gian restore tăng dù queue pending đã về 0. Số bảng nhiều không đồng nghĩa cache lớn; archive lịch sử local mới là phần đã có số đo đáng kể.
- **Tác động:** Chi phí dài hạn, hết disk hoặc restore lâu. Cleanup sai có thể mất khả năng replay, undo hoặc đọc dữ liệu lịch sử.
- **Chưa biết:** Tăng trưởng byte/ngày, horizon retry/undo, lịch giữ archive, vị trí backup và restore toàn ứng dụng trên production hiện tại.
- **Ưu tiên:** P1 về đo/chốt policy. Mọi xóa/di chuyển dữ liệu lịch sử cần đề án riêng và phê duyệt; báo cáo không cấp phép cleanup.

### F05 — Giới hạn media chưa thành ngân sách lưu trữ chung

- **Quan sát — Code:** Upload thông thường có validation và giới hạn mỗi file (mặc định 10 MiB). Connect có admission cap mặc định 512 MiB, tính cả một số media đã có, nhưng code ghi rõ các writer upload khác chưa reserve dưới cùng khóa và đây không phải quota toàn cục. Image library có giới hạn riêng 5 MiB/file.
- **Bằng chứng:** [upload](../../app/services/flashcard_media_api_service.py#L92), [Connect quota](../../app/services/connect/mining_media.py#L67), [media staging](../../app/services/media_staging_service.py), [limits](../../app/settings.py#L202), [Nginx media delivery](../../deploy/flama.nginx.conf).
- **Nguy cơ:** Người dùng đi qua nhiều đường upload/import/TTS có thể làm tăng tổng disk dù từng request hợp lệ. X-Accel-Redirect đã giúp delivery, không giới hạn tổng storage hoặc băng thông.
- **Tác động:** Chi phí disk/backup/egress có thể tăng nhanh trong dịch vụ miễn phí có ảnh/audio. Miễn phí cho người dùng không làm chi phí TTS bên thứ ba hoặc thiết bị người dùng bằng 0.
- **Chưa biết:** Tổng media bytes, duplicate/orphan ratio, file lớn theo loại, egress thực tế, hóa đơn và cấu hình storage production.
- **Ưu tiên:** P1. Cần một policy tài nguyên minh bạch xuyên các writer trước khi quảng bá lưu trữ không giới hạn. Giới hạn mới phải có phương án cho dữ liệu đã tồn tại.

### F06 — Import và bulk TTS có thể chiếm tài nguyên của web request

- **Quan sát — Code:** Import parse đọc file vào bộ nhớ; execute gọi service và commit trong request. Bulk VoiceVox xử lý vòng lặp và gọi dịch vụ synthesis đồng bộ, có cache trong lượt chạy và timeout. Hạ tầng systemd mẫu chạy web 2 worker × 4 thread; Connect 1 worker. Có Study worker riêng, không có nghĩa import/TTS cũng đi qua worker đó.
- **Bằng chứng:** [import routes](../../app/api/v1/flashcards/imports.py#L34), [execute](../../app/services/flashcard_import_api_service.py#L176), [bulk VoiceVox](../../app/services/browse_voicevox_service.py), [synthesis timeout](../../app/services/tts_provider_service.py#L1283), [web unit](../../deploy/flama.service#L13), [Connect unit](../../deploy/flama-connect.service#L14).
- **Nguy cơ:** Các lượt bulk đồng thời giữ slot, memory và connection; timeout từng call không phải tổng time budget của cả batch. Chunk size xử lý không tự biến HTTP request thành background job.
- **Tác động:** Có thể làm chậm thao tác lõi trên VPS nhỏ. Không có benchmark để tuyên bố số batch bao nhiêu sẽ làm nghẽn.
- **Chưa biết:** Kích thước file/batch thực, đồng thời, peak RSS, pool wait, latency của provider.
- **Ưu tiên:** P1 cho admission của import; P2 cho mở rộng bulk TTS. Cân nhắc giới hạn batch hoặc giữ TTS local/tự cung cấp key trước khi đầu tư hạ tầng hàng đợi mới. Phát audio đã có và chế độ nghe vẫn thuộc lõi cần giữ.

### F07 — Admin đổi trạng thái thanh toán chưa tương đương xử lý nghiệp vụ đầy đủ

- **Quan sát — Tái hiện:** Trên fixture in-memory, PATCH trạng thái đơn đã paid sang `refunded` trả `200`, đơn thành `refunded`, `grant_status` vẫn `completed`, entitlement vẫn `active`, **không thêm AuditLog**. Yêu cầu `failed` được chấp nhận trong danh sách trạng thái nhưng thiếu nhánh xử lý: trả `200` và đơn vẫn `paid`.
- **Bằng chứng:** [route đang được gọi từ UI](../../app/api/v1/admin/payments.py#L91), [status service](../../app/services/payment/orders.py#L299), [probe](artifacts/flama_decision_audit_20261016.json). Nhánh refund này không gọi provider để chuyển tiền và không hạch toán đảo số dư. Có thể vận hành hoàn tiền thủ công bên ngoài, nhưng chưa thấy precondition/bằng chứng bắt buộc trong thao tác này.
- **Nguy cơ:** Admin tưởng đã hoàn tiền hoặc cập nhật thành công dù side effects chưa xảy ra. Luồng này dùng package `payment/orders.py`, trong khi checkout/webhook/sync còn dùng `payment_service.py`; đúng ở một đường không chứng minh mọi đường nhất quán.
- **Tác động:** Sai đối soát, quyền lợi và báo cáo. Không kết luận đã có tiền thực thất thoát hoặc quyền học phải luôn bị thu hồi khi refund; chính sách đó cần được quyết định.
- **Chưa biết:** Có giao dịch thật đang mở không, quy trình refund ngoài hệ thống, tổng entitlement/số dư đã phát sinh và cờ payments production.
- **Ưu tiên:** P0 **nếu đang vận hành thanh toán**. Trong hướng miễn phí có thể đề nghị tạm dừng nhận giao dịch mới. Việc này không miễn trách nhiệm xử lý giao dịch và số dư cũ.

### F08 — Ví tác giả có ledger nhưng chưa có cam kết rút tiền hoàn chỉnh

- **Quan sát — Code:** Wallet ghi doanh thu sau xác nhận và có unique key chống trùng theo order item/user/type. API summary trả `payout_enabled=False`. Admin có payout-batch service gọi payOS, nhưng luồng này không thể được coi ngay là quy trình quyết toán ví tác giả.
- **Bằng chứng:** [wallet credit](../../app/services/wallet_service.py#L56), [payout disabled](../../app/services/wallet_service.py#L158), [ledger constraint](../../models/user_balance_transaction.py), [wallet repository](../../app/repositories/wallet_repository.py), [admin payout](../../app/services/payout_service.py).
- **Nguy cơ:** Credit đang đọc balance rồi ghi balance mới; repository lấy seller không dùng `FOR UPDATE`. Unique chống cùng order item không tự bảo vệ hai đơn khác nhau cộng tiền cho cùng tác giả. Đây là **rủi ro concurrency từ code, chưa tái hiện trên MySQL**. Chưa thấy wallet reversal trong nhánh refund ở F07.
- **Tác động:** Có thể lệch ledger/balance; kỳ vọng số dư có thể rút không khớp khả năng thực tế. Chưa khẳng định lỗi đã xảy ra.
- **Chưa biết:** Chính sách fee chốt tại thời điểm nào, refund/chargeback, lịch/ngưỡng quyết toán, người chịu phí, đối soát payout và mức độ dùng thực tế.
- **Ưu tiên:** P2 trong chiến lược miễn phí; P0 trước mở thanh toán/chi trả rộng. Nên cân nhắc hoãn thương mại hóa hơn là vừa thu tiền vừa để nghĩa vụ này chưa rõ.

### F09 — Vận hành cần chốt downtime, trạng thái worker và mức phục hồi

- **Quan sát — Code:** `create_app()` đã tách settings/startup; maintenance mặc định tắt ngoài testing. Deploy hiện dừng HTTP/Connect/Study/projection units trước migration rồi khởi động lại. Health kiểm DB và Redis nếu bắt buộc, không chứng minh toàn bộ Study/analytics worker đã xử lý đúng hạn. Study có readiness riêng khi nhận session/batch.
- **Bằng chứng:** [factory](../../app/__init__.py#L32), [startup flags](../../app/settings.py#L410), [deployment](../../.github/workflows/deploy.yml#L457), [health](../../app/api/v1/health.py), [study readiness](../../app/services/study_worker_readiness_service.py), [rollout/restore giới hạn](../runbooks/DATABASE_PROGRESS_SCALABILITY_ROLLOUT.md#L99).
- **Nguy cơ:** Deploy gây cửa sổ gián đoạn; health `200` không đủ mô tả khả năng lưu học. Sau schema contraction, rollback code đơn thuần có thể bị từ chối để tránh ghi sai codec. Repo có runbook và bằng chứng restore từng đợt; chưa kiểm tra lịch backup/khôi phục đầy đủ đang vận hành hôm nay.
- **Tác động:** Với đội vận hành nhỏ, thời gian sửa sự cố và phục hồi có thể quan trọng hơn tiết kiệm vài ms request.
- **Chưa biết:** Downtime đo được, lịch maintenance được chấp nhận, backup off-host, thời gian phục hồi (RTO), mức mất dữ liệu tối đa chấp nhận (RPO), queue lag và người phụ trách cảnh báo.
- **Ưu tiên:** P1. Chốt cam kết vận hành đơn giản, có thể đo được; chưa có cơ sở yêu cầu HA/đa máy tốn kém. Không báo cáo sai rằng mọi lần boot hiện đều tự migrate/seed/cutover.

### F10 — CI còn chạy rộng trên master, chi phí phát hành chưa được chứng minh đã tối ưu

- **Quan sát — Code:** Workflow vẫn force validation khi không phải PR; backend và frontend có nhánh chạy toàn bộ trên master; còn job SPA contract riêng. Báo cáo tối ưu CI trong repo là kế hoạch, không phải bằng chứng toàn bộ thay đổi đã được áp dụng.
- **Bằng chứng:** [workflow](../../.github/workflows/ci.yml#L77), [full backend branch](../../.github/workflows/ci.yml#L162), [test planner](../../scripts/run_tests.py#L1305), [báo cáo CI trước đó](../plans/TEST_ARCHITECTURE_AND_CICD_OPTIMIZATION_REPORT.md).
- **Nguy cơ:** Tốn runner time và kéo dài vòng phát hành, nhất là thay đổi nhỏ không liên quan runtime. Số phút/quota/hạn mức tài khoản trong báo cáo cũ chưa được xác minh lại, không sử dụng làm hóa đơn hay capacity hiện tại.
- **Tác động:** Chi phí phát triển và tốc độ sửa lỗi; chưa chứng minh ảnh hưởng trực tiếp tới độ trễ học.
- **Chưa biết:** Thời gian/job và billable minutes gần đây, quyền lợi tài khoản, số retry, tỷ lệ lỗi bắt được bởi từng gate.
- **Ưu tiên:** P2. Có thể giảm lặp setup/build, kiểm thử chọn lọc và kiểm thử đầy đủ định kỳ; không đổi thành bỏ kiểm tra integrity, migration hoặc scheduler.

## 5. Nghiệp vụ còn chưa rõ hoặc dễ hiểu khác với code

Phân biệt **code đã quy định rõ nhưng sản phẩm cần công bố** với **thiếu cơ chế thực hiện**. Các hàng dưới không tự phủ nhận quyết định kiến trúc trước đây.

| ID | Hiện trạng đã xác minh | Điều cần chốt/công bố | Phương án ít chi phí để duyệt |
|---|---|---|---|
| N01 | Registry production khởi tạo `legacy-anki 1.0.0`. Resolver đặt `fsrsNextStates=None`; ngay cả cấu hình mode `fsrs` cũng không đi vào nhánh FSRS khi thiếu next states. Có codec nhận states, chưa thấy bộ tính FSRS hoàn chỉnh trong đường tạo policy thông thường | Thuật toán đang cung cấp là gì? Có cam kết FSRS thực sự hay chỉ nền mở rộng? | Giữ scheduler đang chạy; sửa mô tả quá mức, chưa phát triển thuật toán mới nếu không phải ưu tiên được duyệt |
| N02 | Nhiều StudyApplication/presentation cùng Note dùng chung tiến độ learner/Note | Học nhận mặt, gõ và nghe của cùng Note chia sẻ tiến độ có đúng kỳ vọng? Counts đang nói Note, presentation hay lượt trả lời? | Công bố đơn vị và dùng chung tiến độ hiện có; không hứa tiến độ độc lập cho mỗi mode |
| N03 | Xóa riêng một presentation của Note có nhiều presentation bị `CARD_PARTIAL_DELETE_UNSUPPORTED`. Có API xóa Note, tác động tất cả presentation; gỡ Template/application có phạm vi khác | Nút “xóa thẻ”, “xóa note”, “gỡ chế độ khỏi note type”, “xóa deck”, “reset tiến độ” phải nói rõ phạm vi | Giữ invariant hiện tại; làm rõ xác nhận và thông báo lỗi. Không đổi sang xóa từng Card như mô hình cũ |
| N04 | Nội dung đã phát hành có guard: Note tags/deck move, đổi tên NoteType, hard delete; thêm Template qua Content API vẫn có guard. Đồng thời đã có template publication/pins và hotfix content-only; không thể nói “toàn bộ template chưa version hóa” | Ai được sửa phần nào, qua giao diện/API nào, thay đổi ảnh hưởng bản đã cài lúc nào? | Công bố ma trận owned/installed/released; hoãn mở rộng mutation khó. Không gỡ guard để đạt lời hứa CRUD tuyệt đối |
| N05 | Host typing đã được cất theo đổi hướng 10/10; input/đúng-sai có thể nằm trong HTML/JS của Template. Người học vẫn rating ở host; typing không mặc định thành kết quả scheduler | “Chế độ học” là UI trong Template hay tính năng chuẩn có tự chấm, thống kê độ chính xác, lưu số lần thử? | Giữ chế độ động bằng Template và rating hiện có; ghi rõ giới hạn. Không âm thầm khôi phục host typing hoặc cắt chế độ nghe/gõ |
| N06 | Miễn phí là hướng mới được xác nhận. Code vẫn hỗ trợ paid/course key, fee, wallet và role quotas; `.env_example` payments tắt không chứng minh production tắt | Miễn phí gồm các bộ thẻ nào? Tác giả còn được gắn paid/key không? Có dữ liệu/giao dịch cũ cần chuyển tiếp? | Chỉ cung cấp catalog miễn phí trong giai đoạn này sau khi kiểm kê nghĩa vụ cũ; không tự sửa giá/quyền của mọi listing |
| N07 | Preferences `dailyNewCards`/`preferredStudyTime` được lưu localStorage với key chung; Save không cập nhật scheduler backend. Các consumer tìm được chủ yếu là onboarding/settings/summary | “Mục tiêu học” là mong muốn hiển thị hay thật sự giới hạn thẻ mới/nhắc giờ? Có đồng bộ theo tài khoản/thiết bị không? | Công bố là mục tiêu cục bộ, hoặc ẩn lời hứa điều khiển scheduler/nhắc giờ; chưa xây hệ thống reminder |
| N08 | Đóng góp/version có sẵn, overlay bảo vệ source, review/merge có conflict handling; preview có phân trang nhưng một số đường dựng toàn bộ diff trước khi cắt trang | Trong giai đoạn đầu cam kết xử lý đóng góp nhanh đến đâu? Nếu tắt cập nhật tự động, người dùng nhận sửa lỗi bằng cách nào? | Giữ chia sẻ/cài miễn phí; contribution thủ công hoặc giới hạn phạm vi có thông báo. Không coi page size = budget tổng tính toán |
| N09 | Có support tickets; tài liệu community/profile-reporting mô tả yêu cầu, chưa tìm được luồng report profile chuyên biệt trong phần API/UI đã rà | Ai xử lý nội dung vi phạm/bản quyền, trong bao lâu, có cần mở profile cộng đồng đầy đủ ngay không? | Kênh ticket và admin xử lý thủ công trước; hoãn hệ thống moderation nâng cao. Chưa cam kết SLA chưa có người vận hành |
| N10 | TTL/expiry, checkpoint, history/receipt/archives có mục đích khác nhau | Lưu gì, bao lâu; user được xóa/reset cái gì; restore và retry cần bao nhiêu lịch sử? | Chốt policy trước cleanup; không gom tất cả thành “cache hết hạn thì xóa” |

Nguồn bổ sung:

- N01: [registry](../../app/services/study_algorithm_registry.py#L503), [resolver](../../app/services/scheduler_config_service.py#L154), [FSRS branch condition](../../app/services/anki_scheduler.py#L691), [probe](artifacts/flama_decision_audit_20261016.json). Đây là kết luận về đường cấu hình thông thường, không phủ nhận các hook/test với FSRS next states được cấp sẵn. Một số default text trong [InstalledDecksPage](../../frontend/src/features/library/pages/InstalledDecksPage.tsx#L300) và [progress guarantee](../../frontend/src/features/deck-collaboration/components/update/LearningProgressGuarantee.tsx) nhắc FSRS; cần kiểm cả bản dịch đang hiển thị khi sửa thông điệp.
- N02–N03: [application semantics](../../models/study_application.py#L1), [subject unique key](../../models/study_progress_subject.py), [whole-note deletion guard/API](../../app/services/browse_card_service.py#L1151).
- N04: [template guard và ngoại lệ](../../app/services/flashcard_content_service.py#L1466), [Note mutation guards](../../app/services/browse_card_service.py#L1450), [template release/pin tests](../../tests/test_template_deck_release.py). Test này chứng minh pipeline template pins tồn tại, không thay cho ma trận tất cả API mutation.
- N05: [StudyPage](../../frontend/src/features/study/pages/StudyPage.tsx#L20), [đổi hướng typing, §12](../task/decoupling/STUDY_TYPING_ANSWER_PLAN_2026-10-10.md#L318). Giới hạn đã được ghi nhận trước đợt này, không trình bày thành lỗi mới phát hiện.
- N07: [local preferences](../../frontend/src/features/onboarding/hooks/useOnboarding.ts#L19), [Save goals](../../frontend/src/features/settings/hooks/useStudyGoals.ts#L46).
- N08: [release preview](../../app/services/deck_release_service.py#L1358), [local contribution preview](../../app/services/change_request/preview.py#L374).
- N09: [ticket API](../../app/api/v1/tickets.py), [task community reporting](../tasks/COMMUNITY_STANDARDS_PROFILE_REPORTING.md). Không kết luận hệ thống hoàn toàn không có hỗ trợ hoặc moderation chỉ vì chưa có report profile riêng.

## 6. Các phương án giảm phạm vi để phê duyệt

**Tất cả phương án C01–C09 bên dưới đang CHƯA PHÊ DUYỆT.** Hướng miễn phí/lõi ở §1 đã được xác nhận; đó không phải phê duyệt bất kỳ thao tác tắt hoặc xóa cụ thể nào. “Lợi ích” là hướng giảm chi phí dự kiến, chưa phải số tiền đã đo.

| ID | Đề xuất | Người dùng mất/đổi gì | Phần bắt buộc giữ | Lợi ích dự kiến và điều kiện mở lại |
|---|---|---|---|---|
| C01 | Điều chỉnh quota để bảo vệ CRUD/học; giới hạn mạnh hơn ở thao tác đắt tiền | Có thể gặp giới hạn import/media/bulk được công bố thay vì hết quota vì xem/học | Login/abuse protection, an toàn commit, quota được giải thích và đo | Khớp chiến lược miễn phí; chốt con số sau đo phiên học, không tự chọn 300/2.000 làm chuẩn mới |
| C02 | Giữ auto-publish/auto-update tắt cho đối tượng mới; nếu cần, chuyển đối tượng đã bật sang thủ công sau thông báo | Không tự nhận cập nhật tức thời | Học bộ thẻ đã cài, release/pins/overlay, phát hành/cài miễn phí cơ bản, cập nhật thủ công | Giảm fan-out trong transaction; mở lại sau đo theo subscriber và có budget xử lý |
| C03 | Xếp contribution nâng cao, diff/rebase lớn sau lõi; thí điểm nhóm nhỏ hoặc xử lý thủ công | Chờ duyệt/cập nhật lâu hơn; phạm vi đóng góp có giới hạn | Dữ liệu đóng góp đã gửi, local edits, source ownership, đường báo lỗi nội dung | Giảm chi phí phát triển/hỗ trợ; không khẳng định chỉ ẩn UI là giảm tải. Mở rộng theo usage và chi phí mỗi đợt merge |
| C04 | Giảm phạm vi forecast/lịch sử nâng cao và tần suất refresh khi thiếu tài nguyên | Chưa có một số biểu đồ hoặc thấy trạng thái đang cập nhật | Due/queue phục vụ học đúng, progress/history chuẩn, thống kê cơ bản đã chốt | Giảm scan/rebuild nếu thay đổi cả đường server; mở lại khi cache hit, lag và budget đạt ngưỡng được duyệt |
| C05 | Hoãn marketplace thương mại: mua bán, wallet UI, rút tiền và phát khóa truy cập khóa học mới | Không mở bán/thu nhập/rút tiền mới trong giai đoạn này | Catalog/cài miễn phí, nghĩa vụ thanh toán/số dư đã có, audit/đối soát | Giảm nghĩa vụ vận hành và phạm vi sửa lỗi; mở lại sau quyết định chính sách và kiểm chứng tiền/quyền/ledger |
| C06 | Giới hạn bulk TTS, crawl ảnh và công cụ phụ tốn tài nguyên; ưu tiên audio sẵn có/local/BYOK nếu phù hợp | Ít tự động tạo nội dung hàng loạt hơn; có thể cần tự chuẩn bị audio | Nghe audio và các mode học; upload hợp lệ trong ngân sách đã công bố | Giảm provider/slot/storage; mở lại khi đo được chi phí từng thao tác. Local desktop vẫn có chi phí bảo trì và giới hạn thiết bị |
| C07 | Hoãn reminder, đồng bộ goals và moderation/reporting nâng cao | Không hứa nhắc giờ/giới hạn thẻ mới theo goals; hỗ trợ qua ticket | Auth, quản lý nội dung cá nhân, kênh hỗ trợ và khả năng admin xử lý vi phạm | Giảm scope phát triển; không loại bỏ xử lý báo cáo cần thiết khi catalog công khai |
| C08 | Áp dụng retention riêng cho dữ liệu dẫn xuất sau thiết kế/restore proof | Có thể giảm khả năng xem lịch sử phụ hoặc rollback lâu ngày, tùy policy | Nội dung/progress, receipts trong horizon, release còn được tham chiếu, dữ liệu nghĩa vụ | Giảm disk/backup. Chưa được xóa archive/history; phải duyệt loại dữ liệu, tuổi, exception và khả năng restore cụ thể |
| C09 | Tối ưu CI theo thay đổi và full validation định kỳ | Một số lỗi liên miền có thể phát hiện ở đợt full thay vì mọi merge nếu chọn gate thiếu | Smoke lõi, scheduler/integrity tests và MySQL contracts đúng phạm vi | Giảm runner time; chỉ duyệt sau ma trận gate và số đo. Không gọi việc bỏ test là “rủi ro bằng 0” |

Các biện pháp **không đề xuất hy sinh trong báo cáo này**: tính đúng lịch ôn, commit/idempotency, quyền sở hữu source/overlay, sanitization và media proxy, dữ liệu Note/list, nội dung đã cài còn cần đọc, kiểm chứng migration và khả năng phục hồi dữ liệu.

## 7. Những phần đã làm tốt, không nên tính lại thành nợ cần xây mới

- Startup đã được tách và có cờ maintenance; migration không còn mặc định chạy trên mọi lần boot.
- Card đã dẫn xuất theo application; Field live storage đã dùng ID. Các đề xuất tối ưu dựa trên full-copy clone, materialize Card mới hoặc rename toàn bộ JSON theo tên không mô tả đúng working tree hiện tại.
- Overlay-only, immutable releases, template pins, conflict handling và progress concurrency là nền bảo vệ đã có. Hoãn version nâng cao không có nghĩa bỏ nền đọc dữ liệu đó.
- Study có lưu phiên, receipts, retry/replay và worker readiness; không có cơ sở kết luận chỉ cần refresh là mọi tiến độ mất. Phạm vi durability thực tế trên thiết bị/trình duyệt và khi worker lỗi vẫn cần đo riêng.
- Analytics có projection/outbox và bằng chứng MySQL local; không cần đề xuất xây lại từ đầu. Phần thiếu là qualification vận hành, coverage, budget và retention.
- Import/media có validation, size limits, chống đường dẫn nguy hiểm; thiếu quota xuyên writer không đồng nghĩa upload hiện hoàn toàn không được bảo vệ.
- Payment có signature, idempotency và tests fulfillment. Lỗi admin status không chứng minh toàn bộ thanh toán hỏng; ngược lại, test webhook đạt không chứng nhận refund/admin adjustments đúng.

## 8. Dữ liệu còn thiếu để quyết định ngân sách và giới hạn

Không thể quy số dòng code hoặc số bảng thành chi phí. Cần một bảng đo tối thiểu thay vì mua thêm hạ tầng theo cảm giác:

| Cần biết | Thu thập ở đâu | Quyết định được mở khóa |
|---|---|---|
| Ngân sách tối đa/tháng, hóa đơn VPS/storage/backup/egress/email/TTS/CI | Chủ sản phẩm + hóa đơn/cấu hình đã che secret | Chốt trần chi phí và biên dự phòng |
| DAU, số người học đồng thời, notes/decks/active modes mỗi user | Logs/metrics tổng hợp, không thu nội dung học | Quy mô thực cần phục vụ; không dùng số tài khoản đăng ký thay concurrency |
| Request/phiên, tỷ lệ 429, endpoint tốn nhất | Access logs, cohort tài khoản miễn phí | C01 và giới hạn công bằng |
| p50/p95/p99 mở phiên, sửa Note, nhận commit; tỷ lệ lỗi/retry | Đo đường lõi với mẫu đại diện | SLO học và admission trước khi mở rộng |
| CPU/RAM/I/O, DB pool waits/connections, slow queries/locks | Host + MySQL monitoring | Tối ưu query/giảm scope hay thực sự cần nâng máy |
| Study queue lag và thời gian từ accepted đến receipt | DB jobs/worker telemetry | Có đang lưu học đúng hạn; health 200 chưa đủ |
| Projection lag, hit/miss, raw fallback, prewarm coverage | Counts/history/forecast workers/readers | C04 và chi phí summary thực |
| Subscriber bật auto, diff size, publish/rebase latency | Release/install telemetry | C02–C03 và ngưỡng cho version |
| Media/history/outbox/archive data+index bytes và tăng/ngày | DB metadata + filesystem + delivery logs | C05/C06/C08 và quota storage |
| Đơn tiền thật, entitlement, ledger balance, payout chưa đối soát | Read-only audit tiền/quyền | Có thể hoãn thương mại hóa an toàn đến đâu |
| Backup gần nhất, restore toàn DB+media và thời gian hoàn thành | Operator và rehearsal cô lập | RPO/RTO và quyền dọn dữ liệu |

Một công thức để lập ngân sách, **không phải dự báo đã đo**:

`Tăng dữ liệu/ngày ≈ bytes sự kiện + bytes outbox còn giữ + media mới + release/overlay mới − cleanup đã kiểm chứng.`

`Chi phí/tháng = hạ tầng cố định + storage/backup + egress + dịch vụ trả phí + CI + công vận hành.`

Tắt tính năng có thể giảm công phát triển/hỗ trợ nhiều hơn giảm hóa đơn VPS cố định. Chưa đo thì không ghi phần trăm tiết kiệm hoặc hứa chịu được 1.000/10.000 user.

## 9. Thứ tự xử lý được đề nghị

Đây là thứ tự ra quyết định, không phải lịch triển khai đã được chấp thuận:

1. **Chốt lời hứa lõi:** free-use/fair-use, scheduler đang có, dùng chung progress giữa modes và phạm vi CRUD của nội dung đã phát hành. Rà lỗi quota và thông điệp sản phẩm trước chiến dịch thu hút người dùng.
2. **Kiểm kê vận hành chỉ đọc:** effective config, workload, tài nguyên, dữ liệu tiền/quyền, backup. Không tự chạy migration/backfill/cleanup.
3. **Duyệt từng C01–C09:** chốt đối tượng mới/cũ, thông báo, phần phải giữ và điều kiện mở lại. Ưu tiên giảm tự động hóa/version/thương mại hóa trước khi giảm chế độ học.
4. **Thực hiện theo hạng mục đã duyệt:** giới hạn/admission, flags ở cả backend/frontend nếu cần; kiểm owned và installed-clone, session đang chạy, quyền đọc release cũ và dữ liệu đang chờ xử lý.
5. **Đo lại:** chứng minh giảm tài nguyên/chi phí; nếu thao tác lõi vẫn chậm thì xử lý đúng hot path đã đo. Không tiếp tục cắt tính năng chỉ vì chưa tìm ra nguyên nhân.

Mẫu phê duyệt tối thiểu cho mỗi thay đổi:

| Trường | Nội dung phải điền |
|---|---|
| ID/quyết định | Cxx; giữ / giảm / hoãn / từ chối |
| Người duyệt, ngày hiệu lực | Chủ sản phẩm; thời điểm và cohort áp dụng |
| Người dùng bị ảnh hưởng | Người mới, đang dùng, người đóng góp, tác giả, người đã thanh toán nếu có |
| Hành vi sau thay đổi | Nói rõ điều gì còn làm được, điều gì không, thông báo và đường hỗ trợ |
| Dữ liệu/nghĩa vụ giữ lại | Release/pin/overlay/progress/ticket/order/ledger cần bảo toàn |
| Tiêu chí nghiệm thu | Đúng dữ liệu; thao tác lõi; số đo tài nguyên/chi phí; không chỉ “build pass” |
| Khôi phục/mở lại | Cách bật lại, điều kiện, có cần migration không, có backlog phải xử lý không |

## 10. Kiểm chứng và giới hạn nghiệm thu

### Thực hiện trong lần rà soát này

| Hạng mục | Kết quả |
|---|---|
| `scripts/run_tests.py --module payment --backend-only` | **46 test / 7 file PASS**, test time 32,914 s; runner 38,71 s |
| `scripts/run_tests.py --file tests/test_daily_rate_limit.py tests/test_study_algorithm_registry.py tests/test_study_algorithm_golden_vectors.py tests/test_study_content_delete.py tests/test_study_note_overlay.py tests/test_study_batch_queue.py --backend-only` | **75 test / 6 file PASS**, test time 32,549 s; runner 38,45 s |
| Admin refund probe | HTTP 200; refunded + active entitlement + completed grant; audit delta 0 |
| Admin failed-status probe | HTTP 200; requested failed, persisted paid |
| Quota probe hợp lệ | GET 200, GET 200, POST create 429 với quota 2 |
| Quota blueprint boundary | Khi quota CRUD đã hết, Study session endpoint vẫn tới validation (400); thuộc blueprint khác, không có rate-limit header |
| FSRS resolver/registry inspection | Cấu hình fsrs nhưng next states absent, uses-FSRS branch false; registry có legacy-anki 1.0.0 |

Lệnh thực tế dùng `.venv/Scripts/python.exe -X utf8` vì `python` trên PATH trỏ tới Windows Store alias. Probe dùng fixture `PaymentManagementViewTests`, SQLite in-memory, tài khoản giả, teardown sau khi chạy. Lượt quota ban đầu dùng một route trả 405 nên không dùng làm bằng chứng; artifact giữ kết quả đó riêng, cùng lượt đã sửa route hợp lệ. Tests có warning deprecation và log fault-injection; chúng không phải sự cố production quan sát được.

**121 test đạt không chứng minh không có lỗi:** các probe admin ở trên tìm được case ngoài những assertion hiện có. Không sửa test hoặc application để làm kết quả đẹp hơn. Không chạy lại full suite, frontend build/UI/browser hoặc MySQL concurrency/throughput; không dùng kết quả cũ thay chứng nhận những phần đó.

### Các giới hạn của quyết định hiện tại

- Không xác nhận production đã deploy mọi thay đổi trong working tree, bật summary, tắt payments hay bật auto-update.
- Không có số đo resource/cost/capacity hôm nay; không gắn nhãn “đang quá tải” cho một đường chỉ mới thấy nguy cơ trong code.
- Không tự duyệt xóa lịch sử, đổi schema, reset progress, gỡ guards, chuyển giá listing, đóng thanh toán hoặc tắt version/contribution.
- Những phần được đề nghị giảm có thể khôi phục chỉ khi giữ đúng dữ liệu và hợp đồng liên quan; cắt UI đơn thuần không bảo đảm giảm backend workload.

Tài liệu này dùng để chốt phạm vi và ủy quyền công việc tiếp theo. Trạng thái phê duyệt từng phương án hiện vẫn là **chưa phê duyệt**.
