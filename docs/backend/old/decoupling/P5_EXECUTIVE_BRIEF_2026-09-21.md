# Phase 5 — bản trình triển khai cho quản lý

> 2026-09-21 | Đề xuất thực thi, không phải thông báo production đã bật. Chi tiết kỹ thuật: [execution plan](./P5_EXECUTION_PLAN_2026-09-20.md), [data design](../../architecture/phase-5-authority-cutover-design-2026-09-20.md).

## Mục tiêu và quyết định

Đưa **trạng thái học tập về một learner/Note** làm nguồn dữ liệu chính. Deck quản lý tập hợp/ngữ cảnh học; NoteType quản lý cấu trúc nội dung; Template/Card quản lý cách hiển thị. Đổi Template hoặc thêm Card không được vô tình tạo một tiến độ học riêng cho cùng Note. Giai đoạn này vẫn giữ `CardProgress` và Card ID để tương thích/rollback; không đổi thuật toán ôn tập, không xóa dữ liệu cũ.

Chủ sản phẩm đã chọn **bật trên production hiện tại sau khi đạt gate an toàn**, dùng số người dùng hiện có làm canary rồi **giữ vận hành và giám sát**, không chờ một chỉ tiêu số lượng người dùng thật. Điều này loại bỏ “thiếu traffic thật” như một lý do trì hoãn, nhưng không bỏ qua kiểm thử tải tổng hợp, migration, rollback và go/no-go vận hành.

## Điểm xuất phát

- Phase 4/INT-02 đã đóng cho phát triển pre-release. `CardProgress` vẫn là authority duy nhất; production chưa chạy NOTE mode. P4-11 còn rủi ro tải/fault/giới hạn đã chuyển sang P5-09.
- P5 đã bắt đầu: [P5-00](../../architecture/phase-5-p5-00-inventory-2026-09-21.md) có snapshot và audit production SELECT-only hai lượt 2026-09-21: head 39, 16.764 progress rows thuộc 6 learners, drift 0, Phase 4 preflight PASS; full audit WARN với 7 nhóm session/event lịch sử, không có blocker. Principal tạm đã xóa và checksum bundle pass. Gunicorn flags Phase 4/v3/async đều unset; Redis study queue/DLQ đều 0 tại lúc đo. Phase 4 shadow rỗng nên **chưa có old/new parity**; browser offline chưa đo, đây chưa phải bằng chứng rollout.
- [Migration 40](../../architecture/phase-5-authority-fence-adr-2026-09-21.md) vẫn chỉ ở local, thêm hai bảng độc lập **chỉ cho LEGACY**, không thay đổi hành vi sản phẩm. SQLite 6 test, backend study 216 test và MySQL local 8.0.40 disposable migration/khóa hai connection probe đã qua; chưa deploy production.

## Lộ trình và điều kiện nghiệm thu

| Mốc | Phạm vi | Điều kiện ra mốc |
|---|---|---|
| A — khóa hợp đồng | P5-00/01: inventory toàn bộ writer/reader, production read-only preflight, CAS/lock/wire/rollback ADR | Không còn writer/reader hoặc luồng offline chưa được phân loại; quyết định dữ liệu không còn mơ hồ. |
| B — tương thích không mất dữ liệu | P5-02/03: schema LEGACY mặc định và bộ chuyển Note→tất cả Card | Mọi trạng thái NOTE được nhận đều round-trip lossless sang legacy; trạng thái không biểu diễn được bị từ chối. |
| C — ghi tập trung | P5-04/06: review trực tiếp, session/worker, Anki/Connect, reset/delete/clone cùng fence và transaction | Không split brain, không nhận session cũ qua epoch; một Action chỉ có một state/event/receipt; clone không sửa source. |
| D — đọc và client | P5-05/07/08: wire version mới, IndexedDB/retry, due/count/order/stats, history/Algorithm seam | Chạy hai mode trên synthetic cohort; v2/v3 lease được giữ đúng nghĩa cũ; mọi mismatch giải thích hoặc dừng. |
| E — rehearsal và tích hợp | P5-09/INT-03: MySQL 8.0.46 disposable đa người dùng/overlay, concurrent faults, backup/restore, full suite | Có ngưỡng abort, người trực, lệnh rollback đã tập dượt; G5-X/G5-P có bằng chứng. |
| F — production và vận hành | P5-10: deploy LEGACY default, enroll canary đủ điều kiện, theo dõi ít nhất hết lease 24h và pending-job horizon, mở rộng có kiểm soát | Diff không giải thích bằng 0, rollback proof còn hiệu lực, on-call/audit duy trì; G5-F mới đóng Phase 5. |

Ước lượng sơ bộ để bố trí nhân lực: **10–14 tuần lịch** với một backend/database owner tập trung, frontend hỗ trợ ở mốc D, QA và vận hành tham gia từ mốc C–F. Đây không phải cam kết ngày giao: sau P5-00/01 cần rebaseline theo fan-in/lease/traffic production và số writer gián tiếp thực tế. Mốc A–D có thể chồng lấn theo file ownership, nhưng không được bỏ qua thứ tự gate trước production.

## Rủi ro và quy tắc dừng

- Rủi ro chính: Card và Note cùng được ghi, session cũ được nhận sau chuyển mode, projection legacy mất một field/pointer, Anki snapshot đè Action, hoặc lifecycle clone/xóa làm mất progress. Mỗi loại có test 2-connection/fault và audit riêng trước canary.
- Dừng canary ngay khi có một accepted transition không project được, unexplained diff, stale session được nhận, event/receipt bị mất, source clone bị mutate, hoặc lỗi lock/retry vượt ngưỡng P5-09. Không chuyển về Card authority bằng một flag nếu projection chưa được chứng minh đầy đủ; khi đó giữ NOTE, sửa tiến tới/khôi phục theo runbook.
- Rollout **không** xóa bảng/card cũ và **không** tự động hợp nhất PR/deploy. Ít người dùng giúp giới hạn canary nhưng không chứng minh tải; tải/fault phải được tạo tổng hợp trên MySQL disposable cùng phiên bản/cấu hình production.

Quyết định quản lý cần theo dõi theo từng mốc là **tiếp tục cấp nguồn lực và xem bằng chứng gate**, không phải bật production ngay bằng migration 40. Chủ sản phẩm đã xác nhận mục tiêu production; thời điểm chuyển cohort phụ thuộc kết quả kỹ thuật G5-P và khả năng trực/rollback thực tế.
