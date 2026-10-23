# Hợp đồng các task hiện đại hóa kiểm thử

Review 2026-10-23 (Asia/Tokyo), Codex. Tài liệu thay các prompt triển khai H1/H2/H3 trước đây.

Đọc cùng [kế hoạch hiện hành](TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md), [RFC](../architecture/TEST_ARCHITECTURE_RFC.md), [tracker](MULTI_AGENT_TASK_QUEUE.md). Kế hoạch/RFC quyết định kiến trúc/nghiệm thu; tracker ghi owner/tiến độ.

## Quyết định

- Chưa rollout FastTestHarness, shared app/schema, pytest-xdist hoặc nightly thay predeploy gate: chưa đủ MySQL/isolation evidence.
- Runner chuẩn là `scripts/run_tests.py` + unittest. PR B song song trong một runner không cần pytest/shared fixtures hoặc sửa business services.
- FIX-01 sửa mất độ phủ trước PR B; PR C đo từng probe. Giữ full master validation và MySQL/Redis/migration gates.
- Minutes và **Actions storage 0,5 GB** là hai ràng buộc đồng thời, có dự phòng tới cuối kỳ; cache có allowance riêng. Theo mục 11 kế hoạch: dự báo account-level usage, không upload build để giảm phút mà đầy storage, không giảm coverage để né quota.
- Bỏ chỉ tiêu chưa đo: 75,8%, toàn suite <3 phút/auth <5 giây, file/case count hard-code. Cần frozen revision, selected/executed IDs/outcomes, env và cold benchmark.

| Task | Trạng thái | Phạm vi hiện nay |
| --- | --- | --- |
| H1 | `PARKED` | Nghiên cứu lifecycle/isolation riêng, không thêm autouse hook vào suite |
| H2 | `PARKED` | Inventory Study/Decks, không enrol suite vào POC |
| H3 | `PARKED` | Inventory probes/cost/replacement gate, không dời coverage khỏi CI |
| FIX-01 | `REVIEW_REQUIRED` | Path selection/missing files/archive callers/guards theo ownership tracker |
| PR B | `LOCAL_VERIFIED`, `HOSTED_PENDING` | Đã merge Claude và bổ sung `11422541`; 156 tooling cases, 1 POSIX skip, strict manifest parity; CI vẫn jobs=1 |
| PR C | `LOCAL_VERIFIED`, `HOSTED_PENDING` | Tách step để đo đủ probe trên CI; chưa giảm gate hay bật probe song song |

<a id="task-h1"></a>

## TASK-H1: Thiết Kế `tests/conftest.py` & Tích Hợp `pytest-xdist`

Autouse pytest fixture không tự thay `unittest.TestCase.setUp()` đang gọi factory/DDL. StaticPool riêng process chỉ xử lý SQLite connection, không giải quyết globals/hooks/FK/committed writes. Đề xuất SQLite cho toàn suite và tắt FK/raw delete xung đột policy MySQL, có thể che lỗi toàn vẹn. Chỉ giữ `user_roles` không khôi phục seed/reference mutations, sequences, env/extensions.

Điều kiện mở lại:

1. Một owner, nhánh riêng, disposable MySQL/schema từng worker được xác minh. Không suy ra cleanup từ DB dev, không mở rộng SQLite integration.
2. Phân loại unit/integration theo hành vi; giữ setup/commit/FK/JSON/clone invariants và assertions.
3. Chứng minh restoration sau setup/teardown/cleanup failure, seed update/delete, committed writes, multi-app/caches/aliases/hooks. Cleanup lỗi làm run fail; khôi phục hooks/env trong `finally`.
4. Loaded/executed test-ID multisets và outcomes ngang baseline qua lặp/xáo trộn; giữ import/load_tests errors, skips/expected failures.
5. Cold runs không instrumentation, cùng revision/máy. Chọn latency target từ evidence, không giảm độ phủ để đạt target.

Nếu mở lại, chốt riêng scope harness/config/dependencies/lifecycle tests, không tự sở hữu toàn `tests/`.

<a id="task-h2"></a>

## TASK-H2: Refactor Test Fixtures & Savepoints cho Domain Study & Decks

Lệnh `run_tests.py --module study,decks` không kích hoạt POC; pass không chứng minh harness chạy. Scope cũ có services ở bảng tổng nhưng chỉ tests ở phần chi tiết. Không sửa business logic để hợp harness. Không áp kết luận savepoint SQLite cho MySQL; rollback cần chứng minh transaction ownership/nested commits. Raw SQL hoặc bỏ FK/events không mặc nhiên an toàn.

Điều kiện mở lại:

- H1 đủ lifecycle/isolation gates; inventory suite unit/integration/MySQL, exact IDs và assertion contracts.
- Owner trực tiếp và installed clone, source không mutate, deltas/revision/conflict, authority enrollment/committed writes.
- Timezone/day boundary, due/order, answer/undo/idempotency, suspended/empty/authorization.
- Field identity, native array/nested/legacy và media sanitization ở cases hiện có; gap phải có task cụ thể.
- IDs/outcomes ngang baseline sau rename mapping rõ; không tăng skip/nới assertions/đổi expected để pass.
- DDL/JSON/locking/concurrency kiểm chứng MySQL thật. Module hẹp trước; full suite tại integration gate đã lên kế hoạch.

Lần chỉnh tài liệu này không giao worker triển khai H2; ownership theo tracker.

<a id="task-h3"></a>

## TASK-H3: Thiết Kế Workflow `nightly.yml` Cho Heavy MySQL Probes

Không dời tất cả probe/migration replay theo số lượng/tên file. Chúng bảo vệ cả runtime/JSON/concurrency đang dùng; nightly sau deploy không thay predeploy gate đúng candidate revision.

Không thêm Redis vào job chỉ chạy MySQL khi không có dependency; giữ Redis contract hiện hành. Cron Actions dùng UTC: `0 2 * * *` là 11:00 JST, không phải 02:00 JST. Task lịch mới ghi timezone/tần suất/ngân sách.

Điều kiện mở lại:

1. Inventory command/params, invariant, source/migration dependency, trigger, owner, timing, DB target/helper/cleanup.
2. Replacement trước deploy đúng SHA cho case bị chuyển; `models/**`/`migrations/**` luôn đủ tầng MySQL.
3. Đo runner-minutes kể cả cron/setup/reruns; nightly thêm workload, không mặc định tiết kiệm.
4. Mỗi probe có disposable schema trước song song; filename glob không chứng minh isolation. Không chia sẻ DB `ci` cho probe reset/DDL.
5. Timing không đổi semantics, tuần tự baseline, giữ historical bootstrap/Alembic replay; domain owner review đổi gate theo kế hoạch.

Hiện không yêu cầu tạo `nightly.yml`; chỉ chốt scope workflow/script khi mở lại task.

## Checklist bàn giao

- HEAD/diff sở hữu/dependencies/owner acknowledgement; không hai phiên cùng ghi runner/workflow.
- Tách rename/correctness/tối ưu/POC. File untracked cần review và đưa đủ vào thay đổi có chủ đích; không stage việc người khác.
- Command, env không secrets, selected/loaded/executed manifests, outcomes/skip reasons/failure-path/timing. AST/file parity chỉ là kiểm tra cấu trúc.
- Không dùng test-only branch trong hook hoặc đổi assertion để tăng tốc. Worksheet dùng fake timers cho debounce production, có cancel/stale/error cases.
- Báo riêng local/hosted/MySQL/visual verification; không ghi hoàn thành khi chưa đủ evidence.
