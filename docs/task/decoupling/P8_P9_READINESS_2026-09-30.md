# Phase 8 và Phase 9 — điều kiện bắt đầu và bằng chứng hiện tại

> Lập 2026-09-30, sau khi Phase 6 chạy trên production và Phase 7 sẵn sàng. Scope gốc: [canonical plan §15 Phase 8, Phase 9](../../architecture/study-interaction-trigger-algorithm-plan.md#phase-8--add-new-interactions-algorithms-and-secondary-consumers). Ràng buộc của chủ sản phẩm: giữ hiệu năng, **không mất hoặc hỏng dữ liệu learner**.

## 1. Kết luận

Phần *tách* (decoupling) của kế hoạch đã xong: progress thuộc learner/Note (Phase 5, 18/18 learner ở NOTE), Card/Template chỉ còn là presentation/compatibility (Phase 6), chi tiết thực thi phiên có retention (Phase 7). Hai phase còn lại không phải việc code có thể làm ngay:

- **Phase 8** là thêm năng lực sản phẩm mới trên kiến trúc đã tách. Mỗi năng lực cần chủ sản phẩm chọn và định nghĩa hợp đồng; chưa có năng lực nào được chọn.
- **Phase 9** là xóa lưu trữ/code cũ. Canonical plan chỉ cho phép khi telemetry chứng minh không còn ai dùng, sau backup đã kiểm, chứng minh restore và **một phê duyệt migration riêng**. Hai cổng hiện chưa đạt (bảng §3).

## 2. Phase 8 — cần chủ sản phẩm chọn năng lực đầu tiên

Canonical plan: thêm từng năng lực một, ví dụ (a) đánh giá trắc nghiệm, (b) Algorithm không lặp lại (non-repetition), (c) consumer analytics/XP từ commit. Mỗi năng lực phải định nghĩa: input, schema Action, ánh xạ trigger, schema Algorithm State, hợp đồng availability, mức tin cậy, giữ phiên bản, hành vi migration. Code tùy ý của người dùng, chuỗi nhiều trigger và automation ngoài vẫn đóng.

Việc cần chủ sản phẩm: chọn năng lực đầu tiên và UX của nó. Sau khi chọn, lập `P8_EXECUTION_PLAN` theo mẫu P6 (quyết định, gate, work package, probe MySQL, runbook).

## 3. Phase 9 — cổng và bằng chứng

Lệnh đọc-only `flask study-phase9-readiness [--window-days 30]` (không ghi gì) cho trạng thái từng cổng: `ready` (không thấy dùng trong cửa sổ), `waiting` (còn dùng), `decision` (bị chặn bởi quyết định sản phẩm, không phải dữ liệu).

Số liệu production 2026-09-30 (SELECT-only):

| Hạng mục canonical Phase 9 | Bằng chứng | Trạng thái |
|---|---|---|
| Ngừng ghi projection `card_progress` | 18/18 learner NOTE, 0 user chưa enroll; 40.668 dòng `card_progress` = 40.668 subject NOTE. Projection này là đường rollback NOTE → LEGACY mà D6-02 giữ | **decision**: bỏ nó là bỏ rollback, cần chủ sản phẩm quyết |
| Bỏ wire phiên cũ (v2/v3) | 363 phiên v2 trong 30 ngày (phiên cuối mở 29/09 00:51, trước R1); từ R1 chỉ có v4 | **waiting**: sẵn sàng khi 30 ngày không có v2/v3 (sớm nhất 2026-10-29) |
| Bỏ ánh xạ ordinal Anki theo vị trí | 0 Card thiếu occurrence, 0 occurrence thiếu ordinal, 0 ref Connect mất Card | **ready** về dữ liệu; vẫn cần xác nhận không còn gói Connect/Yomitan cũ |
| Bỏ giả định 4 rating, lời gọi scheduler cũ, cột Algorithm cố định, renderer/manifest cũ, tương thích theo tên Template/Field | Việc code; mỗi mục cần inventory callsite như P6-00 | Chưa bắt đầu |
| Archive/purge dòng runtime hết hạn | Phase 7 (`study-session-retention`) | Xong ở mức membership phiên |

## 4. Thứ tự đề xuất

1. Chạy `study-phase9-readiness` hằng tuần (hoặc khi cần) và ghi kết quả vào tài liệu này.
2. Khi cổng wire đạt (≥ 2026-10-29): PR gỡ nhánh v2/v3 ở server + client (không đụng dữ liệu; phiên cũ đã kết thúc).
3. Chủ sản phẩm quyết định có giữ rollback NOTE → LEGACY hay không. Chỉ khi bỏ: backup đã kiểm → chứng minh restore trên DB tạm → phê duyệt migration riêng → ngừng ghi `card_progress` (giữ bảng, không xóa dữ liệu) → theo dõi → mới xét xóa bảng.
4. Mỗi bước Phase 9 là một PR riêng, có probe MySQL và runbook, không gộp.
