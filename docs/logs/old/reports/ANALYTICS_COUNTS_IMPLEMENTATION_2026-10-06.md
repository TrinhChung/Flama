# Analytics counts: kết quả triển khai và chi phí tuyến tính còn lại

## Kết quả và phạm vi

Đã triển khai Phase A count lịch sử và Phase B snapshot trực tiếp theo deck; migrate MySQL local từ revision 50 lên 52, backfill/prewarm User 1 trên dump thật. Raw ReviewEvents của User 1 không đổi: trước/sau đều **118.579 events**, cùng tổng ID/checksum các trường tham gia tính toán. Chưa bật flag/job trên production.

Sáu bảng mới: `review_analytics_heads`, `review_analytics_generations`, `daily_review_counts`, `deck_count_content_revisions`, `deck_count_learner_revisions`, `deck_study_count_snapshots`. Count lịch sử commit cùng fact. Deck snapshot bị loại khi dependency/token/day/policy thay đổi. Raw vẫn là fallback/nguồn kiểm chứng; layout React giữ nguyên.

Phase B phục vụ **Dashboard và deck thuộc sở hữu learner, ngoài nhánh install/clone**. Đã publish **1.528 snapshot** cho User 1. Scope khác, overlay và Browse/admin-wide chưa chứng minh được vẫn raw. Note-type metadata vẫn đọc riêng, giữ oldest-Note precedence và Notes chưa có Card.

## Số đo User 1

MySQL 8.0.40 localhost; builder backend với đồng hồ cố định `2026-10-06T03:00:00Z`, timezone/policy hiện tại. Mỗi mode warm-up một lần, lấy median 7 lần. Chưa tính Flask JSON serialization, nén/mạng, DOM; đây không phải p95 production hoặc thời gian trình duyệt.

| Builder | Raw median | Summary median | Thay đổi |
|---|---:|---:|---:|
| Dashboard compact | 1.594,69 ms | 360,65 ms | giảm 77,4% |
| Overview | 737,21 ms | 399,75 ms | giảm 45,8% |
| Study time, `all` | 295,86 ms | 8,90 ms | giảm 97,0% |
| Today/future | 754,06 ms | 727,57 ms | chỉ giảm 3,5% |

**4/4 payload khớp hoàn toàn.** History summary không SELECT `review_events`; riêng snapshot hit không scan Cards. Dashboard User 1 còn một count raw cho scope chưa cache. Số query Dashboard tăng từ 8 lên 16 nhưng lượt đọc dependency nhỏ thay aggregation lớn.

Backfill đầu 500 events/chunk khoảng **7,99 giây**; prewarm lạnh 1.528 deck khoảng **2,59 giây**. Đây là job, không đưa vào GET. Hai generation được giữ trong thử nghiệm; tổng 5.572 daily rows không phải số ngày collection hay số row chỉ riêng generation active.

Profiling query riêng, không dùng làm median, xác định các phần còn nặng:

- Overview: future-due SQL khoảng 460 ms; hai daily-count SQL khoảng 4 ms/lượt.
- Today/future: đọc trạng thái theo Card khoảng 761 ms rồi decode/aggregate Python; history count không thay được nó.
- Dashboard cache: note-type fallback khoảng 150 ms; snapshot SELECT khoảng 36 ms; scope/ancestor/tree/payload vẫn tốn chi phí.

Đã bỏ authority lock khỏi `today-future`, dùng reader không khóa trong RR read-only transaction. Profiling cuối kiểm tra bốn summary builder không `FOR SHARE`/`FOR UPDATE`. Query timings dao động theo tải local; chúng dùng để xác định việc cần nghiên cứu tiếp.

## Chi phí ghi và correctness

Probe MySQL chạy **native LEGACY review thật** trên fixture riêng trong DB local: 2 warm-up + 10 mẫu/mode. Lượt cuối: median count tắt **27,76 ms**, bật cả hai **49,60 ms**: thêm **21,84 ms / 78,7%**. Các lượt trước thêm khoảng 11–12 ms; độ dao động local này cần canary đo lại. 24 facts khớp 24 counts, 2.400 ms duration, 24 passed; 12 commit ở giai đoạn bật writer tăng source revision sau backfill.

Đã bỏ hai lookup scope dư khi Card/Note có sẵn trong Session, không lazy-load hay duyệt cả identity map. Overhead vẫn vượt gate đề xuất **5 ms / 10%**. Read ROI tốt nhưng **write economics chưa đạt gate** để tự rollout rộng. Cần đo NOTE/concurrent writers trên canary và giảm round trip history finalizer. Mặc định vẫn raw/off; không đánh dấu gate này pass.

Khóa theo thứ tự User/domain → tất cả history heads theo user → generation/bucket → deck token theo key. Snapshot token ghi ở outer commit sau mọi domain flush. SAVEPOINT giữ ancestry đến root; rollback cha loại cả delta/token của child đã release. Replay/trùng/import-card thất bại không cộng count.

Coverage: schema/DDL, migration idempotence trên MySQL thật, writer đồng thời, ID thấp chưa commit trước admission, chunk crash/retry/live tail, purge DIRTY, timezone/DST/boundary, subtree root/intermediate, NOTE/CARD units, overlay fallback, hai publication race, HTTP học/session/worker/MCP/Anki và GET không DML. CI thêm hai probe MySQL. JSON evidence ở [analytics-counts-2026-10-06](analytics-counts-2026-10-06/).

Kết quả kiểm tra: **176 analytics backend tests**, **32 startup/modular-runner/deck tests**, **27 history MySQL checks** và **15 deck MySQL checks** pass. Frontend: 17 import-related + 3 profile tests, typecheck và focused lint pass. Entry point `wsgi.py` boot thành công với startup maintenance tắt trên local dump. Các test SQLite bổ sung không thay thế probe MySQL local thật.

## Các hàm/luồng còn tăng theo dữ liệu

| Phần | Chi phí | Việc cần làm tiếp |
|---|---|---|
| `_canonical_future_due_day_counts` và state due queries | `O(C_state_scope)` | Ưu tiên cao; nghiên cứu due/day buckets với interval codec/timezone đúng. Không dùng review history total thay future total. |
| `_consolidated_due_rows_and_load` + due Python aggregation | `O(C_state_scope)` | Nút khoảng 761 ms còn nguyên; tách due count khỏi weighted load và nghiên cứu SQL grouping/buckets. |
| `_deck_note_types` | theo Notes của fallback scope | Khoảng 150 ms; cache/index metadata riêng, giữ oldest-Note và Notes chưa Card. |
| Cold/dirty `aggregate_deck_study_counts` | `O(C_dirty)` | Raw fallback/recompute chỉ deck mất hiệu lực; overlay còn raw. Worker skip mọi key hợp lệ. |
| Eligibility/dependency hash | `O(D + A)` khi có đủ cây | Đã thay duyệt tổ tiên `O(D × depth)` bằng memoization; cây sâu 1.500 cấp dùng 3 SELECT. Truy vấn chỉ lá sâu vẫn cần batch tổ tiên thiếu. |
| Tree/sort/alias/payload | ít nhất `O(D)` + sort sibling | Count không giảm số deck/payload. Lazy children/pagination cần browser profile/contract riêng. |
| Daily reader/streak | theo ngày/daily rows của scope | Heatmap collection theo năm chặn ở 365/366 ngày; lifetime streak/subtree vẫn tăng theo scope/ngày. |
| Backfill/oracle/reconcile | `O(H_user)` | Chuyển khỏi request; timezone/purge/recovery cần rebuild. Đo chunk fence p95, lên retention RETIRED rows. |
| Capture/import/delete | `O(changed objects)` + distinct-key upserts | Không scan mọi learner Card khi học. Bulk chưa biết scope tăng global epoch O(1) nhưng làm nhiều cache lạnh. |
| Queue hydration/session/offline persistence | theo candidates/events/bytes | Count không chọn Card kế tiếp hoặc giảm snapshot/offline serialization; roadmap riêng. |

Worker hiện dùng allowlist cấu hình, tối đa 100 learner/lượt; chưa tự khám phá active users. Timer mẫu chưa cài production. Tắt/bật writer không chứng minh coverage liên tục; Direct Connection/DB/binary cũ bỏ qua hooks. Sau gap: history cần `--restart` có verification, deck cần bump global epoch rồi prewarm. [Runbook](../runbooks/ANALYTICS_COUNTS_RUNBOOK.md) ghi thứ tự cụ thể. Không reset token/xóa raw history.
