# Handoff điều phối kiểm thử — 2026-10-23 (Asia/Tokyo)

Owner review: Codex coordinator. Người dùng cho phép tiếp tục xử lý và kiểm tra định kỳ, trao đổi Gemini/Claude khi cần. Đây là handoff có thể đọc chung; không phải bằng chứng mọi phiên đã nhận hoặc xác nhận ownership.

## Ownership và việc đang diễn ra

- Main checkout có phiên Claude tên `Phase 0/1 nâng cấp test` đang busy theo `claude agents --json`; một phiên API review mới không xác thực được (OAuth expired). Không resume/interrupt hay đổi tài khoản của phiên đang chạy.
- Codex FIX-01 chỉ ghi trong `D:/Project/nihongo-coordinator-fix01`, gồm runner, runner tests, CI contracts/workflow và static migration-path guard. Main đã có thay đổi trùng mục tiêu từ phiên khác; không copy đè. Bản riêng đã pass 78 pure tooling tests; sau normalization cuối, 44 runner tests pass. Patch theo baseline ở `%LOCALAPPDATA%/Flama/test-coordinator/fix01-candidate.patch`; chờ owner main chọn delta còn thiếu, không copy nguyên runner.
- Worktree `D:/Project/nihongo-test-speed` có candidate PR B và bắt đầu thêm MySQL probe runner. Đây là implementation candidate, chưa được nghiệm thu/bật CI. Không nhận toàn bộ diff của worktree này để thay runner main.
- Local watcher: Codex worker chỉ sở hữu `scripts/watch_test_coordination.py`, `tests/test_watch_test_coordination.py`; coordinator tích hợp source mapping khi runner owner bàn giao. Scheduler/report ở local, không Actions.

## Gửi owner FIX-01 / Phase 0–1

Main đã sửa nested selection, explicit missing paths và CI archive callers. Cần review thêm:

1. `--file docs/README.md` hợp lệ trước đây là no-op, nay bị thêm lỗi no-suites. Phân biệt tài liệu/source hợp lệ không cần test với explicit test không tồn tại.
2. `--changed` đang lọc mọi selected missing paths sau mapping: catalog stale do source edit lại có thể mất test âm thầm. Chỉ resolve deletion/rename từ event diff; không bỏ missing suite sinh từ catalog.
3. Git status cần `--untracked-files=all`, nếu không nested new directory chỉ hiện tên thư mục, không chọn test mới.
4. Rename/deletion không có basename tương ứng: cần conservative fallback cho affected layer, không chọn rỗng. Nếu trùng basename ở nhiều nơi không chọn tuỳ tiện entry đầu tiên.
5. Frontend root thiếu khi có explicit selected tests phải fail; không trả success.
6. Migration-chain path hiện đã là `parents[3]` ở snapshot mới. Giữ static guard, kiểm chứng MySQL riêng; không lấy việc sửa path làm bằng chứng migration pass.

Worktree Codex có regression/candidate cho các điểm trên; tích hợp từng delta sau xác nhận ownership, không xoá các sửa live của owner main.

## Gửi owner PR B

Review read-only candidate ở `nihongo-test-speed` (base 57738edd, file còn đang đổi):

- P1: `BackendBinResult.passed` chỉ xét exit 0; missing summary/Ran 0/summary FAILED có thể xanh. Cần structured outcomes và fail khi không có execution hợp lệ.
- P1: workflow đã dùng `--jobs auto` trước FIX-01/parity/resource/paired-run/budget gates. Giữ jobs=1 trên hosted cho tới đủ evidence.
- P1: regex tổng Ran N không chứng minh exact loaded/executed-ID multisets, outcomes/skip reasons/subtests/fixture errors. Cần manifest baseline, seed và parity.
- P1: worker wait không timeout; SIGTERM/process-tree cleanup chưa đầy đủ khi leader exit hoặc taskkill lỗi. Thêm concurrent negative lifecycle tests.
- P2: snapshot flags cần `0`, env cùng parent snapshot; memory 768 MiB chưa có số đo trong RFC được dẫn, không tự dùng hết CPU khi không rõ RAM/cgroup. Log spool đọc toàn bộ lại vào RAM vẫn chưa bounded.
- Tách MySQL probe runner thành PR C riêng với inventory/schema ownership. Không ghi mọi backend suite là SQLite isolated hoặc dùng SQLite làm integration qualification.

## Gửi owner Worksheet / S3

Giữ production debounce 300 ms; dùng fake timers trong test. Case cần có: không gọi trước hạn, coalesce/latest payload, cancel/unmount/leave studio, stale success/error/loading và lỗi request. Không nghiệm thu 22 case xanh khi hook dùng nhánh test-only 0 ms. Config/setup toàn frontend cần test/ownership riêng.

## Trao đổi thực tế

- Claude bounded read-only review đã thử: không có lượt inference, lỗi `OAuth session expired and could not be refreshed`; không ghi là Claude đã review.
- Gemini bounded read-only review qua agy trả exit 0 nhưng stdout rỗng và stderr báo print timeout 90s khi turn đang chạy. Không có review report hợp lệ; không ghi là đã review. Manager quota endpoint không truy cập được; không refresh/rotate account, không giao batch dài.
- Không có message được chèn vào các phiên IDE đang busy; file handoff này là mailbox dùng chung. Chỉ xác nhận received/reviewed khi có response thật.

## Quota và job kiểm tra

Theo kế hoạch mục 11: bảo vệ đồng thời minutes và Actions storage 0,5 GB đến cuối kỳ. Không upload artifact hoặc chạy Actions để poll. Windows Task `Flama-Test-Coordinator` đã đăng ký: poll 30 phút, IgnoreNew, execution cap 8 phút; chạy hidden bằng venv pythonw dưới tài khoản đang đăng nhập. Static run thật trả LastTaskResult=0. AI run thử thất bại vì configured CLI model `gpt-6.1-sol` không được ChatGPT account của CLI hỗ trợ; không tự đổi model/global config. Hiện action bỏ `--review` và chỉ poll tĩnh, chờ lựa chọn model của người dùng. Thiết kế AI khi được bật: tối đa 4 attempts/ngày JST, 12 file/lượt, giữ backlog, timeout/cooldown và bounded reports.


## Checkpoint lead sau khi các phiên tiếp tục sửa

- Main có PR B candidate khác `nihongo-test-speed`; CI main vẫn chạy jobs=1, không gán finding bật auto quá sớm của worktree kia cho main.
- Main PR B còn P1: `KeyboardInterrupt` handler nằm ngoài `with ThreadPoolExecutor`, nên executor có thể chờ worker treo trước khi handler được chạy; `communicate()` không timeout và chỉ kill/terminate PID trực tiếp. Cần sửa lifecycle trước qualification.
- Main worker pass chỉ theo exit code, không chứng minh case-ID/outcome parity. Speedup lấy tổng thời gian concurrent workers chia wall time không phải baseline tuần tự và không chứng minh tiết kiệm quota.
- Main đã khôi phục Worksheet debounce production 300 ms và thêm 8 hook cases. Lead chạy cả hook + modal: **30 tests pass**, 2 files, một lượt 14,24s tổng. Chưa có baseline/cold benchmark hoặc visual verification; không ghi speedup.
- Lead chạy CI/runner/mapping current main: **56 tests pass**. Watcher + mapping: **28 tests, 27 pass, 1 skip** vì Windows thiếu quyền symlink. Các số này là các lượt riêng, không cộng thành coverage toàn suite.
- Coordinator chỉ thêm module `test_coordination` để map script watcher sang focused test; giữ toàn bộ delta runner của owner main. Không stage/commit/push.

## Vận hành job local

- Script: [watch_test_coordination.py](../../scripts/watch_test_coordination.py), tests: [test_watch_test_coordination.py](../../tests/test_watch_test_coordination.py).
- Task name: `Flama-Test-Coordinator`. Cần máy bật và tài khoản Windows đăng nhập; không phải job cloud hay notification tự hiện trong chat.
- State: `%LOCALAPPDATA%/Flama/test-coordinator/state.json`; AI report nếu thành công: `report-*.md`, tối đa 10 bản ×128 KiB. Không đổi Actions storage hoặc upload artifact.
- Kiểm tra: `Get-ScheduledTaskInfo -TaskName 'Flama-Test-Coordinator'`; tạm dừng: `Disable-ScheduledTask -TaskName 'Flama-Test-Coordinator'`; bật lại: `Enable-ScheduledTask -TaskName 'Flama-Test-Coordinator'`.
- Poll thủ công không AI: `.venv/Scripts/python.exe scripts/watch_test_coordination.py --repo D:/Project/nihongo --inbox docs/plans/TEST_COORDINATION_HANDOFF_2026-10-23.md`.
- Còn mở: model CLI cho AI review; owner acknowledgement và tích hợp FIX-01; lifecycle/parity/resource evidence PR B; qualification MySQL/hosted; account-level quota telemetry. Static polling không đồng nghĩa đã có AI review/đã nhắn thành công cho IDE sessions.


### Bổ sung review main PR B tại checkpoint cuối

- Failfast có race: worker kiểm tra stop trước Popen rồi đăng ký sau; nếu sibling fail trước registration, worker khởi động muộn có thể thoát khỏi cả hai lượt terminate. Cần stop/register atomic và test có barrier, không chỉ assert overall False.
- Handler Ctrl+C ở ngoài executor context có thể không chạy tới vì executor đợi futures trước. Cần xử lý cancel ngay trong lifecycle executor, process-tree termination, timeout và bounded reap.
- Main vẫn chỉ xác nhận worker exit code, chưa có structured executed-ID/outcomes/skip parity; thiếu memory/affinity/output caps và explicit snapshot-update safeguards.
- Nhãn speedup tính cumulative thời gian workers / parallel wall time chỉ phản ánh overlap; không phải paired sequential speedup, không chứng minh giảm runner-minutes.
- Deletion không có same-basename replacement cần current-manifest fallback. Các finding FIX-01 cũ cần recheck trên diff owner mới nhất vì main liên tục thay đổi; không coi một snapshot là trạng thái cuối.

Code/CLI probe và scheduler:

- Installed Codex CLI 0.150.1 đăng nhập bằng ChatGPT; request tối thiểu không tools bị backend từ chối model configured `gpt-6.1-sol` với HTTP 400. Cache model catalog không chứng minh inference được account hỗ trợ.
- Không đổi model hoặc global config. Câu hỏi lựa chọn đã gửi người dùng vì skill codex-cli yêu cầu giữ configured model nếu chưa được chỉ định khác. Job hiện chạy static, LastTaskResult=0; AI attempt thất bại không được ghi là review thành công.

## Checkpoint PR B đã merge và commit local

Theo yêu cầu mới, Codex đã fetch/rà các nhánh để tránh trùng công việc, chọn bản Claude mới nhất và fast-forward nhánh chung lên `72ce0f5c`. Commit bổ sung `11422541` sửa lifecycle, launch race, timeout, structured manifest và giới hạn log. Ba lượt tooling jobs1/2 seed0/13 và lượt kiểm tra commit sạch đều có 156 cases, 1 skip POSIX, 683 event, hash `e1943e749675eaa86a165cfc72563ccb783b522a4f4cb85cfe66ee48496e0372`. So multiset strict không khác biệt. Không push; CI jobs1 cho đến khi đạt full-suite/Linux/hosted gates. S2 đã trả đủ 22 file về `tests/` theo MSG-10. Chi tiết ở checkpoint đầu kế hoạch và MSG-11..13 của tracker.
