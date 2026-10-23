# Phase 8 và Phase 9 — điều kiện bắt đầu và bằng chứng hiện tại

> Phần Phase 9 dưới đây là ảnh chụp 2026-09-30. D9-02 đã thay quyết định giữ rollback D6-02 và Phase 9 đã tổng kết ở [INT-06](./P9_CLOSEOUT_2026-10-03.md). Phần Phase 8 vẫn hiện hành; cập nhật 2026-10-10: trắc nghiệm tạm hoãn (§2).

> Lập 2026-09-30, sau khi Phase 6 chạy trên production và Phase 7 sẵn sàng. Scope gốc: [canonical plan §15 Phase 8, Phase 9](../../../architecture/study-interaction-trigger-algorithm-plan.md#phase-8--add-new-interactions-algorithms-and-secondary-consumers). Ràng buộc của chủ sản phẩm: giữ hiệu năng, **không mất hoặc hỏng dữ liệu learner**.

## 1. Kết luận

Theo bằng chứng triển khai ghi nhận dưới đây, progress đã thuộc learner/Note (Phase 5, 18/18 learner ở NOTE), Card/Template là presentation/compatibility (Phase 6), chi tiết thực thi phiên có retention (Phase 7). Tuy nhiên NOTE runtime vẫn phụ thuộc projection cũ để kiểm tra tính toàn vẹn; cần tách phụ thuộc này trước khi ngừng ghi.

- **Phase 8** là thêm năng lực sản phẩm mới trên kiến trúc đã tách. Mỗi năng lực cần chủ sản phẩm chọn và định nghĩa hợp đồng; chưa có năng lực nào được chọn.
- **Phase 9** đã có [kế hoạch thực thi chi tiết](./P9_EXECUTION_PLAN_2026-09-30.md), cập nhật theo chỉ đạo chủ sản phẩm: **xác nhận full NOTE → backup/restore proof → cắt ghi song song, ghi đầy đủ dữ liệu mới vào NOTE → cắt giảm tài nguyên**. Khi lỗi, bổ sung chọn lọc từ backup vào NOTE và giữ dữ liệu mới; không đợi Phase 8 hoặc cửa sổ wire để cắt projection khi đủ gate. Quyết định bỏ ghi song song đã chốt; technical readiness và kết quả production chưa được xác nhận trong công việc lập kế hoạch.

## 2. Phase 8 — cần chủ sản phẩm chọn năng lực đầu tiên

Canonical plan: thêm từng năng lực một, ví dụ (a) đánh giá trắc nghiệm, (b) Algorithm không lặp lại (non-repetition), (c) consumer analytics/XP từ commit. Mỗi năng lực phải định nghĩa: input, schema Action, ánh xạ trigger, schema Algorithm State, hợp đồng availability, mức tin cậy, giữ phiên bản, hành vi migration. Code tùy ý của người dùng, chuỗi nhiều trigger và automation ngoài vẫn đóng.

**Trắc nghiệm tạm hoãn (chủ sản phẩm quyết định 2026-10-10).** Trắc nghiệm không được chọn làm năng lực P8 đầu tiên và không lập kế hoạch trong đợt này. Lý do:

- Mọi chế độ dùng chung một tiến độ learner/Note ([canonical plan §16.1](../../../architecture/study-interaction-trigger-algorithm-plan.md#161-resolved-product-decisions), quyết định 1). Trắc nghiệm chỉ đo khả năng *nhận ra* và có thể đoán trúng, còn scheduler tính khoảng ôn theo khả năng *tự nhớ lại*. Nếu ánh xạ "đúng" thành rating thường, khoảng ôn của Note sẽ dài quá mức cho mọi chế độ khác.
- Chưa có nguồn phương án nhiễu. Note có field tùy ý, deck tự tạo, import từ Anki hoặc clone overlay. Phương án lấy ngẫu nhiên trong deck quá dễ đoán, deck nhỏ không đủ phương án, và phương án phải được đóng băng trong snapshot phiên để server chấm lại.
- Phải có evaluator ở client, verifier ở server, golden vectors và màn đối soát ([canonical plan §6.3](../../../architecture/study-interaction-trigger-algorithm-plan.md#63-evaluation-placement)). Chi phí này lớn so với quy mô hiện tại, và repo chưa có bằng chứng người dùng cần.

Chỉ mở lại khi đủ cả bốn điều kiện:

1. Có quyết định ánh xạ outcome → Trigger cho chế độ nhận diện (ví dụ "đúng" chỉ tương đương trigger yếu, hoặc chỉ dùng ở bước làm quen thẻ mới), kèm cách kiểm chứng không làm dài khoảng ôn của chế độ khác.
2. Có hợp đồng nguồn phương án nhiễu: lấy từ field/deck/NoteType nào, số phương án tối thiểu, hành vi khi không đủ, cách đóng băng trong snapshot.
3. Interaction host đã tách khỏi `StudyPage` và có bề mặt nhập liệu tin cậy ngoài iframe.
4. Có tín hiệu nhu cầu từ người dùng.

Quiz luyện tập **không ghi tiến độ** nằm ngoài Phase 8, và vẫn theo ranh giới hiện tại: iframe Template không có quyền ghi tiến độ.

**Action/outcome tổng quát (mức 3, để dành).** Bỏ giả định bốn rating khỏi phần generic là nền cho mọi năng lực có input khác bốn rating. Kế hoạch, kiểm kê callsite và điều kiện kích hoạt: [P8_GENERIC_ACTION_OUTCOME_PLAN](./P8_GENERIC_ACTION_OUTCOME_PLAN_2026-10-10.md).

Việc cần chủ sản phẩm: chọn năng lực đầu tiên trong các lựa chọn còn lại và UX của nó. Sau khi chọn, lập `P8_EXECUTION_PLAN` theo mẫu P6 (quyết định, gate, work package, probe MySQL, runbook).

Điều kiện UI và chi phí UX của từng lựa chọn: [điều tra UI/UX trước Phase 8](./UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md) §4 (P8-UI-1..10) và §6 (quyết định D-U1..D-U6).

## 3. Phase 9 — cổng và bằng chứng

Lệnh `flask study-phase9-readiness [--window-days 30]` có body chỉ đọc, cho trạng thái từng cổng: `ready` (các phép đếm hiện có đạt), `waiting` (phép đếm chưa đạt), `decision` (cần quyết định sản phẩm). **Readiness v1 chưa phải bằng chứng đủ để cắt:** chưa đo actual readers/writers, restore/retry, accepted jobs và package versions; CLI cũng chưa nằm trong audit-only app. Phải bảo đảm bootstrap không chạy maintenance. P9-02 sẽ bổ sung coverage và các cổng thiếu; chi tiết [F9-04](../decoupling-phases/phase-9-contraction-investigation-2026-09-30.md#f9-04--readiness-v1-là-tín-hiệu-sơ-bộ-chưa-chứng-minh-hết-consumer-cũ).

Số liệu production 2026-09-30 (SELECT-only):

| Hạng mục canonical Phase 9 | Bằng chứng | Trạng thái |
|---|---|---|
| Ngừng ghi projection `card_progress` | 18/18 learner NOTE, 0 user chưa enroll; 40.668 dòng `card_progress` = 40.668 subject NOTE. Đây là snapshot lịch sử; chưa chứng minh mọi dữ liệu/luồng ghi NOTE đầy đủ | **Quyết định đã chốt; chờ bằng chứng kỹ thuật**: G9-FULL/G9-WRITE → G9-BACKUP → G9-CUT theo P9-03..06. Phục hồi bằng bổ sung backup, không giữ projection chỉ để rollback LEGACY. Readiness v1 vẫn báo `decision`/D6-02 cho gate này đến khi P9-02a cập nhật |
| Bỏ wire phiên cũ (v2/v3) | 363 phiên v2 trong 30 ngày (phiên cuối mở 29/09 00:51, trước R1); từ R1 chỉ có v4 theo lần ghi nhận này | **waiting**: 2026-10-29 chỉ là mốc dự kiến theo issuance; cần zero usage, valid lease/job và đủ telemetry theo P9-02/P9-08 |
| Bỏ ánh xạ ordinal Anki theo vị trí | 0 Card thiếu occurrence, 0 occurrence thiếu ordinal, 0 ref Connect mất Card | **ready** về dữ liệu; vẫn cần xác nhận không còn gói Connect/Yomitan cũ |
| Bỏ giả định 4 rating, lời gọi scheduler cũ, cột Algorithm cố định, renderer/manifest cũ, tương thích theo tên Template/Field | Việc code; mỗi mục cần inventory callsite như P6-00 | Chưa bắt đầu |
| Archive/purge dòng runtime hết hạn | Phase 7 (`study-session-retention`) | Xong ở mức membership phiên |

## 4. Thứ tự đề xuất

1. P9-00, P9-02a và P9-03..05c: kiểm toàn bộ learner, dữ liệu, reader/writer, worker, import/lifecycle và new-user default; tách NOTE khỏi projection gồm fence Connect/Anki và audit canonical thay thế; đóng đường vào LEGACY (signup làm ngay được). Enrollment count không đủ.
2. Write freeze ngắn, backup nhất quán cả legacy + NOTE, giữ identity mapping/T0/watermark; thử restore cách ly và thử bổ sung dữ liệu thiếu mà bảo toàn mọi ghi mới sau T0.
3. P9-06: xử lý work cũ, ngừng projection trên toàn hệ thống cùng lúc; xác nhận mọi transaction mới ghi đầy đủ state/history/receipt vào NOTE. Không chờ retention hoặc telemetry wire 30 ngày.
4. Sau đó P9-01/P9-07..10 cắt giảm runtime/code/storage theo mức giảm tài nguyên và gate từng nhóm. Wire/Connect có điều kiện retirement riêng.
5. Nếu lỗi, bổ sung chọn lọc từ backup theo manifest, revision và lifecycle; không restore dump cũ đè production. Chi tiết [P9 execution plan](./P9_EXECUTION_PLAN_2026-09-30.md).
