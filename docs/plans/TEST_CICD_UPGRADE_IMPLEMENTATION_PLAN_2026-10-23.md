# Review kế hoạch nâng cấp CI/CD test và kế hoạch triển khai

- Ngày: 2026-10-23 (Asia/Tokyo)
- Cập nhật quyền thực hiện: người dùng đã yêu cầu commit các phần cần kiểm chứng và **push lên** trong phiên 2026-10-23. Các yêu cầu "không push" bên dưới là lịch sử trước chỉ dẫn này. Rollout CI song song vẫn cần nghiệm thu, mặc định jobs=1 không đổi.
- Review điều phối bổ sung: Codex, cùng hai reviewer read-only trong phiên được người dùng giao điều phối; xem mục 10. Review trên HEAD `57738edd` cộng diff đang có, không phải nghiệm thu thay các agent triển khai.
- Kế hoạch này và [RFC](../architecture/TEST_ARCHITECTURE_RFC.md) quyết định kiến trúc/nghiệm thu; [tracker](MULTI_AGENT_TASK_QUEUE.md) ghi ownership/trạng thái; [H1/H2/H3](TEST_MODERNIZATION_HARD_TASKS_FOR_CLAUDE_CODEX.md) đã được sửa thành `PARKED`. Báo cáo 13/10 và các số đo ở mục 2–4 là lịch sử; evidence mới ở mục 10–11. Mục 11 bổ sung yêu cầu người dùng cân bằng minutes với **Actions storage 0,5 GB**, không đổi một quota lấy việc cạn quota khác.
- Phạm vi review:
  - Gemini, báo cáo 2026-10-13: `docs/plans/TEST_ARCHITECTURE_AND_CICD_OPTIMIZATION_REPORT.md` (Tiered CI, D2, nightly, gate MySQL).
  - Gemini Teamwork 2026-10-22: POC `FastTestHarness` (`tests/test_harness_poc.py`) và bản nháp RFC.
  - Codex P0 ở snapshot review ban đầu (khi đó chưa commit, nhánh `fix/deploy-disconnect-cloudflare` của PR TrinhChung/Flama#239): `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, `tests/test_spa_artifact_contract.py`, `scripts/run_tests.py`, `docs/architecture/TEST_ARCHITECTURE_RFC.md`, các file POC.
- Trạng thái khi ghi nhận P0: mục 6.0 và 6.1 đã làm và commit local, khi đó chưa push/chưa chạy Actions. Đợt review điều phối này chưa xác minh push/hosted workflow runs; chỉ đọc API artifact/cache cho mục 11. Diff S2/S3 cần sửa trước nghiệm thu.
- Cập nhật 2026-10-23 sau review (Claude Code): PR B có hai bản chưa tích hợp; trạng thái từng gate và bằng chứng ở mục 6.2.1. PR C có số đo từng probe, inventory và phương án mới ở mục 6.3.1. Thứ tự tích hợp ở mục 8, điểm mở ở mục 9, quy trình nghiệm thu hosted có ngân sách ở mục 12, review của Gemini và cách xử lý ở mục 12.4. Code tương ứng là các commit local `987f6ead`, `6569ebc9`, `61fdb9ff`, `a1f08cda`, `72ce0f5c` trên nhánh `wip/test-speed`. Gemini đã review hai lượt (mục 12.4); lượt 2 kết luận đủ để triển khai. Người dùng yêu cầu chỉ commit local, không push.
  - 6.0: POC được park ở nhánh local `experiment/test-harness-poc` (bước 2, lựa chọn (a)). Theo yêu cầu của người dùng, P0 được commit thẳng lên nhánh `fix/deploy-disconnect-cloudflare` thay cho bước 3–4.
  - 6.1: đã xoá job `spa-contract`. Bằng chứng local nằm trong `docs/architecture/TEST_ARCHITECTURE_RFC.md`; phần nghiệm thu trên GitHub (bước 6) vẫn chờ.

### Checkpoint tích hợp theo yêu cầu người dùng (Codex, 2026-10-23)

Đã fetch và rà toàn bộ refs/worktree trước khi sửa, xác nhận bản PR B mới nhất của Claude là `wip/test-speed` tại `72ce0f5c`. Người dùng yêu cầu merge vào nhánh chung: đã fast-forward `fix/deploy-disconnect-cloudflare` từ `57738edd` lên commit đó, bảo toàn lịch sử Claude và ghép lại các thay đổi local. Không push. Dùng bản A của Claude; bản B của Antigravity được thay thế, không triển khai lại PR B từ đầu.

Đã bổ sung sau review: hủy worker cả lúc submit/consume, cleanup process tree với Windows Job Object và POSIX session, timeout áp dụng cả một file/jobs=1, launch gate chống late spawn, snapshot flags thống nhất. Log giữ head/tail tối đa 1 MiB/bin và tiếp tục drain pipe. Manifest JSON v1 atomic giới hạn 32 MiB, ghi loaded/started/finished/outcome/subtest/fixture với scope của case, giữ duplicate và skip reason chính xác, kiểm tra schema/count/completion, từ chối kết quả rỗng hoặc log giả. Hash theo từng category và skip diagnostics có giới hạn được in vào CI log, không upload artifact.

Bằng chứng local trên patch tích hợp: 8 file tooling (`test_modular_test_runner`, `test_parallel_backend_runner`, `test_unittest_manifest`, `test_ci_workflow`, `test_test_mapping_coverage`, `test_deploy_workflow`, `test_cloudflare_cache_rule`, `test_flama_audio_release_workflow`). Ba lượt jobs=1, jobs=2 seed 0 và jobs=2 seed 13 đều có **156 loaded/started/finished cases, 1 skip POSIX, 683 event**, SHA-256 `e1943e749675eaa86a165cfc72563ccb783b522a4f4cb85cfe66ee48496e0372`. Hai phép so multiset đều `only before: 0`, `only after: 0`. Hai seed thay đổi grouping thật ở 6 bin. Wall time local lần lượt 24,38 / 15,78 / 15,80 giây; đây là số đo tooling, không phải full-suite hay dự báo minutes CI. Evidence/log local ở `%LOCALAPPDATA%/Flama/test-coordinator/prb-evidence`.

S2 đã hoàn tác chuyển thư mục theo quyết định người dùng qua MSG-10: giữ đủ 22 test tại `tests/`, phục hồi import/path, không giảm gate. CI push/PR vẫn jobs=1 và có timeout; full-suite parity trên revision tích hợp, Linux lifecycle thực và hosted benchmark còn chờ, nên PR B là `LOCAL_VERIFIED` cho tooling và `HOSTED_PENDING` cho rollout. Không chạy ứng dụng, DB, migrations hoặc SQLite integration trong đợt PR B này. Wrapper yêu cầu suite có inventory cố định trước run; custom suite thêm case động trong `run()` sẽ báo lỗi qualification. Hash TSV lịch sử không so trực tiếp với schema JSON mới.

### Checkpoint CI sau push (Codex, 2026-10-23)

- Quyền push đã được người dùng cấp sau checkpoint local. Run `39939578562` pass backend 2.647 cases/9 skip, Redis và MySQL; frontend fail vì selector giữ đường dẫn test đã chuyển/xoá. `524e4a1c` sửa selection bằng full inventory hiện hành của đúng tầng khi diff chứa deleted test, giữ lỗi cho explicit missing file và stale catalog, không hạ coverage.
- Run `39943093986` pass frontend 190 suites (1.540 pass/4 skip), Redis và toàn bộ MySQL gates. Backend chạy đủ 2.663 cases nhưng 2 test workflow mới lỗi vì import `yaml` chưa được khai báo trong dependencies CI; local đã có PyYAML nên không lộ lỗi. `4ae8b3fc` bổ sung `requirements-test.txt`, backend install/cache và mapping full backend cho test dependency changes; giữ nguyên assertions của PR-C. 96 tooling tests pass ở cả venv hiện có lẫn venv Python 3.12 mới cài từ manifest; 17 workflow tests cũng pass trong môi trường chỉ có PyYAML.
- Run [`39945884728`](https://github.com/TrinhChung/Flama/actions/runs/39945884728) trên `4ae8b3fc` đã **SUCCESS**: backend full inventory 253 file/2.740 cases, 9 skip, worker 794,54s (job 13m40s); frontend 190 suites/1.540 pass/4 skip, lint/typecheck/build/SPA contract pass; MySQL/Redis pass. Test-dependency manifest kích hoạt full inventory backend, rộng hơn selection 244 file của run trước. Push/PR vẫn jobs=1; chưa nghiệm thu full-suite parity đa seed của PR B, không tự mở thêm benchmark hosted khi chưa xác minh headroom quota.
- Hai run dùng PR-C mới đều pass mọi migration/contract step: `39943093986` job 4m54s, sáu probe song song wall 225,6s; `39945884728` job 9m05s, wall 429,8s. Giữ cả hai số đo để phản ánh biến động hosted, không chỉ dùng lượt nhanh nhất làm forecast. Tmpfs 262 MiB/2 GiB và swap 0 ở cả hai lượt là số cuối job sau cleanup, không phải peak. PR-C chưa đóng resource gate bằng số này. Run mới có 0 artifact/0 byte; repo cache snapshot 5 cache/545.360.559 byte (≈520 MiB), thuộc budget riêng. Account-level minutes/storage forecast vẫn `UNVERIFIED` theo mục 11.
- Warning jsdom trong typing template đã xác định là callback `select` từ case trước chạy sau `window.close()`. Theo MSG-16, cần sửa cleanup/drain timer và assert không có jsdom errors ở batch frontend kế tiếp, giữ assertions hiện hành; chưa có bằng chứng đây là lỗi production/audio.
- GitHub API sau khi CI xanh ghi nhận tài khoản `TrinhChung` đã merge PR #239 lúc 20:39:07 JST vào `master`, merge commit `d385295b`. CI master [`39947576664`](https://github.com/TrinhChung/Flama/actions/runs/39947576664) tự chạy và đang in progress tại checkpoint này; chưa xác nhận deploy thành công. Codex không thực hiện thao tác merge PR.

## 1. Kết luận ngắn

1. Số đo lịch sử 30 ngày khoảng **1.045 phút tính phí**, thấp hơn giả định 2.940 phút của báo cáo Gemini. Điều này không chứng minh tài khoản còn đủ quota hiện tại: phải kiểm tra cả minutes và Actions storage **0,5 GB** đến cuối billing cycle theo mục 11; account billing chưa xác minh được.
2. Hai job `backend` và `mysql-contract` chiếm khoảng **72%** số phút. Đòn bẩy chính là làm hai job này nhanh hơn, không phải chuyển sang chạy chọn lọc trên master.
3. Kiến trúc phân tầng (ứng viên B: chạy chọn lọc trên master cộng nightly) **không đáng làm lúc này**. 20/22 lượt merge gần đây đều chạm backend, nên chạy chọn lọc tiết kiệm rất ít. Trong khi đó nightly ngày thường sẽ *tăng thêm* khoảng 660–800 phút mỗi tháng.
4. Phần CI của Codex P0 đúng và đã pass test. Nhưng nếu giữ job shim `spa-contract` thì gần như **không tiết kiệm được phút tính phí**, vì job nào cũng bị làm tròn lên 1 phút. Repo không có branch protection, nên nên xoá hẳn job này.
5. Phần harness của Codex P0 **không còn trong checkout**. Phiên Antigravity/Gemini `d8ea6482` đã ghi đè lúc 00:32–00:34 bằng bản nháp cũ, và phiên này vẫn đang chạy. Vì vậy RFC hiện mô tả một bản code không còn tồn tại. Đề xuất đóng băng (park) POC và để nó ngoài mọi PR CI.
6. *(Bổ sung 2026-10-23.)* Khoảng **700/839 s của `mysql-contract` là dựng và xoá schema 115 bảng cho từng test** trong sáu probe nặng, không phải phần kiểm contract (mục 6.3.1). Đây là job dài nhất, nên chỉ PR C rút ngắn được thời gian push; hướng đầu tiên là datadir trên tmpfs, không bỏ probe hay case nào.
7. *(Bổ sung 2026-10-23.)* PR B chạy song song trong cùng runner đã khớp từng test với bản tuần tự ở local: cùng 2.638 ID test, cùng 7 skip, 1,6–2,6 lần nhanh hơn tuỳ số worker (mục 6.2.1). Runner hosted chỉ có 2 vCPU nên kỳ vọng trên CI là tối đa khoảng 1,6 lần ở step `backend`, chưa đo. Mặc định CI vẫn một tiến trình cho tới khi đạt các run hosted ở mục 12.

## 2. Số đo thực tế (30 ngày đến 2026-10-23)

Nguồn: `gh run list` và `gh api .../runs/<id>/jobs`. Phút tính phí được ước lượng bằng `ceil(completed - started)` cho từng job, chỉ tính lần chạy cuối của mỗi run. Số liệu billing chính thức nằm ở Settings → Billing; API billing cần scope `user`.

| Hạng mục | Giá trị |
| --- | --- |
| Gói / quyền riêng tư | Private repo, GitHub Free. API branch protection và rulesets trả về 403 ("Upgrade to GitHub Pro"). |
| Lượt chạy CI | 57: 20 push (17 thành công, 3 lỗi) và 37 PR (23 thành công, 9 lỗi, 5 bị huỷ) |
| Phút tính phí ước tính | ≈1.045 (push ≈495, PR ≈550) |
| Thời gian push thành công | Trung vị ≈10,8 phút, dao động 7,5–19,1 phút |
| PR thành công | Trung vị ≈6 phút |

Phút tính phí theo job:

| Job | PR | Push | Tổng | Tỷ trọng |
| --- | ---: | ---: | ---: | ---: |
| `backend` | 221 | 199 | **420** | 40% |
| `mysql-contract` | 199 | 138 | **337** | 32% |
| `frontend` | 66 | 72 | 138 | 13% |
| `changes` | 37 | 20 | 57 | 5% |
| `spa-contract` | 21 | 20 | 41 | 4% |
| `redis-contract`, `deploy` | 6 | 46 | 52 | 5% |

Lượt push gần nhất (run `39775470111`): `mysql-contract` 839s, `backend` 604s, `frontend` 363s, `deploy` 81s, `spa-contract` 54s. Critical path hiện nay là **`mysql-contract`**, không phải `backend`. Trong `mysql-contract`, step "Qualify Field identity expansion and exact forecast buckets" (5 probe) mất 423s và "NOTE overlay and pristine materialization" mất 191s.

Thành phần các merge trên master gần đây (25 commit first-parent từ 2026-09-23): 22 merge có kích hoạt CI. Trong đó chỉ **2 merge thuần frontend** (#232, #223); còn lại đều chạm `app/`, `models/`, `migrations/` hoặc `scripts/`, và đa số chạm code liên quan DB.

## 3. Review báo cáo Gemini (2026-10-13)

### Điểm nên giữ

- Phương án D2: chạy SPA contract ngay trong job `frontend`, dùng lại bản build Vite, bật pip cache.
- Bác bỏ D1 (upload/download artifact), đúng với chính sách không dùng artifact storage.
- Đúng khi nói rằng matrix sharding nhiều runner làm tăng tổng phút tính phí do mỗi runner bị làm tròn lên.
- Đúng khi nói rằng không thể thay MySQL contract bằng SQLite.
- Đúng khi lưu ý: một khi các contract job trở thành có điều kiện thì cần điều kiện `deploy` chống "cascading skip".

### Điểm sai, lỗi thời hoặc thiếu

| # | Vấn đề | Bằng chứng | Hệ quả |
| --- | --- | --- | --- |
| G1 | Mô hình quota giả định 60 merge và 120 lượt chạy PR mỗi tháng, ra 2.940 phút | Thực tế 20 push, 37 PR, ≈1.045 phút | Bối cảnh "khủng hoảng" không đúng. Mục tiêu nên là tạo dư địa và tăng tốc. |
| G2 | Cho rằng `backend` là critical path, `mysql-contract` chỉ 5m50s | Thực tế `mysql-contract` mất 14 phút, do các probe field identity được thêm sau ngày 10/13 | Thứ tự ưu tiên sai |
| G3 | Biểu thức chống skip `!contains(needs.*.result, 'failure') && !contains(..., 'cancelled')` | Khi `if:` không chứa hàm trạng thái nào (`success()`, `always()`, `failure()`, `cancelled()`), GitHub tự ghép thêm `success()` | Cách sửa không có tác dụng: job `deploy` vẫn bị skip khi một job trong `needs` bị skip. Phải dùng `!cancelled() && !failure() && ...`. |
| G4 | Master chỉ chạy chọn lọc theo event diff | `build_ci_change_plan` chọn job theo `changed_files`; `files_since_deploy` chỉ ảnh hưởng `deploy` (`scripts/run_tests.py:1463-1480`) | Lỗ hổng: push A (backend) fail CI nên chưa deploy, rồi push B (frontend) được deploy cùng code của A mà backend và MySQL không chạy lại |
| G5 | Nightly ngày thường là "lưới an toàn" | 22 lượt × 30–37 phút ≈ 660–800 phút, lớn hơn toàn bộ chi phí push hiện nay (≈495) | Chi phí tăng chứ không giảm. Nightly chỉ hậu kiểm *sau* khi đã deploy. |
| G6 | Chạy chọn lọc trên master tiết kiệm ≈70% | Chỉ 2/22 merge là thuần frontend | Mức tiết kiệm thực tế chỉ khoảng 5–10%, trong khi độ phủ trước deploy giảm |
| G7 | Nói gate MySQL "chỉ có 7 repository", và `stats_today_future.py` chạy READ ONLY | `MYSQL_CONTRACT_SOURCE_PATTERNS` đã có khoảng 80 pattern. Chỉ 7 file dùng `analytics_read_transaction`/READ ONLY, và `stats_today_future.py` không nằm trong số đó. | Lý do mở rộng không chính xác. Mở rộng thành `app/repositories/**` sẽ bật MySQL gần như cho mọi thay đổi backend. |
| G8 | Bỏ qua phương án chạy song song *trong cùng một runner* | `run_backend_tests` chạy một tiến trình `python -m unittest` cho toàn bộ file (`scripts/run_tests.py:1575-1588`) | Đây là đòn bẩy lớn nhất cho 420 phút của `backend`, không tốn thêm runner, và còn tăng isolation |
| G9 | Mâu thuẫn nội tại | Báo cáo 10/13 bác bỏ shared app/DB fixture (ứng viên A); POC 10/22 của Gemini lại làm đúng loại harness đó | Cần một quyết định thống nhất (mục 5) |
| G10 | Chi tiết lỗi thời | Báo cáo ghi 235 file/2.436 test, hiện có 254 file `tests/test_*.py`. Core smoke chứa `test_spa_artifact_contract.py`, file này bị skip trong job backend vì không có `dist`. | Cần đo lại trước khi dùng bất kỳ số nào |

## 4. Review Codex P0

### 4.1 Phần CI: đúng, đã kiểm chứng

- `ci.yml`: job `frontend` thêm pip cache và cài `requirements.txt`, rồi chạy `tests.test_spa_artifact_contract` trên chính bản `build:ci` khi `spa_contract == 'true'`. Job `spa-contract` chỉ còn một step `echo`.
- `test_spa_artifact_contract.py`: tắt maintenance và kiểm tra kết nối khi khởi động. `Engine.connect` bị patch để fail nếu có kết nối DB; `tearDown` chỉ dispose engine. Không còn dùng SQLite nữa.
- Kiểm chứng local:
  - `ci.yml` parse được bằng YAML; thứ tự job và `needs` của `deploy` không đổi.
  - `run_tests.py --file tests/test_ci_workflow.py tests/test_deploy_workflow.py tests/test_modular_test_runner.py tests/test_test_mapping_coverage.py tests/test_poc_test_runner.py --backend-only`: **67 test pass**.
  - `FLAMA_REQUIRE_REAL_SPA_ARTIFACT=1` với `tests/test_spa_artifact_contract.py`, chạy trên `frontend/dist` build lúc 00:06: **2 test pass**.
  - Workflow chưa được kiểm chứng trên GitHub Actions thật.

### 4.2 Vấn đề

| # | Vấn đề | Đề xuất |
| --- | --- | --- |
| C1 | Shim `spa-contract` được giữ lại "cho branch protection", nhưng repo không có branch protection (403). Job chỉ có một lệnh `echo` vẫn tốn một runner và 1 phút tính phí, bằng đúng job cũ (avg 49s cũng là 1 phút). Job `frontend` lại dài thêm khoảng 20–30s. | Xoá job, bỏ nó khỏi `needs` của `deploy`, cập nhật test. Chỉ khi đó mới thật sự tiết kiệm (≈25–41 phút/tháng). |
| C2 | Harness gia cố của Codex (`scripts/poc_harness.py`) đã bị thay lúc 00:32 bằng shim re-export `tests/test_harness_poc.py` (bản nháp). `poc_test_runner.py` và `test_repeatability_benchmark.py` giờ import bản nháp. `test_adversarial_poc_harness.py` bị viết lại lúc 00:34 thành 8 test khớp với bản nháp. | Đóng băng (mục 5). Bản của Codex còn khôi phục được từ transcript `~/.codex/sessions/2026/10/22/rollout-2026-10-22T23-50-19-*.jsonl` (có `Add File: scripts/poc_harness.py` và các patch test). |
| C3 | Bản nháp hiện tại vẫn còn đủ các lỗi mà RFC liệt kê: nuốt exception (`except Exception: pass`, `logger.warning`), cleanup trong `tearDown`, giữ role theo code/tên hard-code, bật/tắt FK, singleton `_instance`, key config dùng `str(v)` và không tính đến env, `activate()` ghi `os.environ` mà không khôi phục, không có guard cho target DB | Không dùng cho rollout. Số liệu "48% nhanh hơn" không đáng tin. |
| C4 | RFC (`docs/architecture/TEST_ARCHITECTURE_RFC.md`) ghi "P0 hardening implemented", "80 tests passed", "107/107" cho code không còn tồn tại | Sửa trạng thái trong RFC trước khi commit, hoặc tách RFC khỏi PR CI |
| C5 | P0 chưa commit, lại nằm trên nhánh của PR TrinhChung/Flama#239 (nhánh `fix/deploy-disconnect-cloudflare`, đang mở, chậm 2 commit so với master) | Tách ra nhánh mới tạo từ `origin/master` và chỉ mang theo các file CI |
| C6 | `scripts/run_tests.py` map các file POC vào module `tooling` | Chỉ giữ nếu POC được commit; nếu không thì bỏ khỏi PR CI |

## 5. Quyết định đề xuất

| Hạng mục | Quyết định |
| --- | --- |
| D2: SPA contract trong `frontend` và xoá shim | **Làm ngay** (PR A) |
| Chạy backend song song trong cùng một runner | **Làm** (PR B), đo trước rồi mới bật |
| Rà soát và chia tầng các probe MySQL | **Làm** (PR C), cần chủ sở hữu ký duyệt từng probe |
| Chạy chọn lọc trên master (ứng viên B) | **Park**. Bật lại khi tỷ lệ merge thuần frontend ≥30% trong 30 ngày, hoặc quota vượt 75%. Khi đó phải theo thiết kế ở mục 6.4. |
| Nightly / weekly cron | **Không làm** chừng nào master còn chạy đầy đủ |
| Matrix sharding nhiều runner | **Không làm** |
| POC `FastTestHarness` / tái dùng schema | **Park** trên nhánh thử nghiệm riêng, không merge vào `tests/`. Chỉ xem xét lại khi đã qua các gate trong RFC (MySQL, isolation, đo khi chạy lạnh) và có một chủ sở hữu duy nhất. |
| Datadir MySQL trên tmpfs trong `mysql-contract` (bổ sung 2026-10-23) | **Đã làm local** (commit `902c0cd5`, cùng commit với dòng dưới, theo yêu cầu người dùng); giữ lại chỉ khi hai run hosted đạt (mục 6.3.1 (d), 12.3) |
| Chạy song song sáu probe tự tạo schema (bổ sung 2026-10-23) | **Đã làm local** (commit `902c0cd5`); probe concurrency và probe dùng schema `ci` giữ tuần tự (mục 6.3.1 (b)) |

## 6. Kế hoạch triển khai chi tiết

### 6.0 Ổn định checkout (tiên quyết)

1. Người dùng dừng phiên Antigravity `d8ea6482` hoặc giao rõ cho nó quyền sở hữu các file POC; hai agent không được cùng sửa một file.
2. Quyết định số phận POC: (a) chuyển sang nhánh `experiment/test-harness-poc` *(đề xuất)*, (b) khôi phục bản gia cố của Codex, hoặc (c) xoá.
3. Người dùng đã chọn làm PR A thẳng trên nhánh `fix/deploy-disconnect-cloudflare` (PR TrinhChung/Flama#239). Khi commit, chỉ đưa vào các file CI/docs của PR A; các file POC đã đóng băng không được đưa vào.
4. Cách làm thay thế cho các PR sau: dùng worktree riêng để không đụng checkout chính, nơi các agent khác đang sửa:

```powershell
git fetch origin master
git worktree add ..\nihongo-ci-p0 -b ci/spa-contract-in-frontend origin/master
git diff --output=..\p0-ci.patch -- .github/workflows/ci.yml tests/test_ci_workflow.py tests/test_spa_artifact_contract.py
git -C ..\nihongo-ci-p0 apply --3way ..\p0-ci.patch
```

Dùng `git diff --output` thay vì chuyển hướng `>` của PowerShell để tránh BOM/UTF-16.

### 6.1 PR A: SPA contract trong `frontend`, xoá shim (≈0,5 ngày)

File: `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, `tests/test_spa_artifact_contract.py`, `docs/ops/ARCHITECTURE.md` (dòng 386), `docs/architecture/TEST_ARCHITECTURE_RFC.md` nếu đi kèm.

1. Giữ nguyên các step Codex đã thêm vào `frontend` (pip cache, `Install SPA contract dependencies`, `Verify Flask serves the real Vite artifact`).
2. Xoá job `spa-contract`. Đổi `needs` của `deploy` thành `[changes, frontend, backend, redis-contract, mysql-contract]`. Giữ output `spa_contract` vì các step trong `frontend` vẫn dùng.
3. Cập nhật `tests/test_ci_workflow.py`:
   - `test_backend_is_independent_from_frontend_and_redis`: đổi điểm cắt từ `"\n  spa-contract:\n"` sang `"\n  redis-contract:\n"`.
   - `test_expensive_environment_contracts_are_explicit`: bỏ `assertIn("  spa-contract:\n")`; khẳng định step `tests.test_spa_artifact_contract` cùng `FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'` nằm trong khối `frontend`, và `"\n  spa-contract:\n"` không còn trong workflow.
   - Xoá `test_spa_required_check_tracks_the_frontend_contract_result`.
   - `test_production_deploy_is_called_only_after_master_validation`: cập nhật chuỗi `needs`.
   - Giữ `test_ci_uses_no_actions_artifact_storage` (đếm `npm ci` và `build:ci` đúng 1 lần).
4. Nếu đi kèm RFC thì sửa trạng thái thành "CI P0 implemented; harness parked", bỏ các dòng bằng chứng về harness.
5. Kiểm chứng local (cwd là worktree, dùng venv của checkout chính; để trống các biến `STUDY_*` theo `$flama-local-dev`):

```powershell
D:\Project\nihongo\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_ci_workflow.py tests/test_deploy_workflow.py tests/test_modular_test_runner.py tests/test_test_mapping_coverage.py --backend-only
```

   Việc test với artifact thật cần `frontend/dist` trong worktree; nếu không build được ở local thì để CI kiểm chứng.
6. Nghiệm thu trên GitHub:
   - Run của PR không còn job `spa-contract`.
   - Step "Verify Flask serves the real Vite artifact" pass, vì `ci.yml` nằm trong `SPA_CONTRACT_SOURCE_PATTERNS` nên step này chắc chắn chạy.
   - Job `frontend` chỉ dài thêm ≤30s.
   - Ở lần push master đầu tiên có thay đổi runtime, `deploy` vẫn chạy sau khi các job khác thành công.
7. Rollback: revert PR.

### 6.2 PR B: chạy backend song song trong cùng runner (≈1–2 ngày, đo trước)

Mục tiêu là giảm thời gian mà giữ nguyên khả năng phát hiện lỗi. Giảm 30–45% chỉ là giả thuyết; ước lượng 1–2 ngày không bao gồm sửa FIX-01 hoặc suite không an toàn khi song song. Khi viết các bước dưới đây runner chưa có `--jobs`; trạng thái triển khai hiện tại ở mục 6.2.1.

1. **Tiên quyết:** đóng FIX-01 ở tracker. Chốt revision/diff và manifest, tách POC/rename khỏi tối ưu. Đo backend step, whole job, critical path, CPU/RAM và môi trường; baseline tuần tự trước. Không so máy/commit hoặc case set khác nhau.
2. **Tương thích:** thêm `--jobs N|auto`, mặc định `1`; valid-input command/environment/result như hiện nay. Explicit file thiếu phải fail là sửa correctness riêng, không giữ lỗi cũ vì mục tiêu tương thích. Thay đổi docs hợp lệ chọn rỗng vẫn là no-op; import error, file bị mất hoặc suite được yêu cầu nhưng load rỗng ngoài ý muốn phải fail.
3. **Scheduling:** thử jobs 1 và 2 trước; `auto` có trần theo effective CPU, số file và RAM đo được, không tự lấy toàn logical CPUs. LPT theo file size chỉ là heuristic ban đầu, thay bằng timing khi đủ dữ liệu. Mỗi file đúng một nhóm; seed phải thực sự đổi grouping/order và được ghi lại.
4. **Cô lập:** mỗi nhóm là subprocess unittest riêng, media/temp/env riêng từ cùng parent snapshot; không mutate parent env. Giữ email/quota safeguards; đặt `UPDATE_SNAPSHOT=0`, `UPDATE_ROUTE_SNAPSHOT=0` trong correctness run, không chỉ xoá biến rồi để `.env` nạp lại. Supply study-default flags nhất quán theo skill local-dev; không vô hiệu hoá cấu hình mà test chủ đích cần. Audit fixed files, snapshots, ports, Redis, DB/schema và subprocess descendants trước dispatch. Không tạo SQLite integration mới; MySQL tests/probes cần target disposable riêng đã xác minh.
5. **Kết quả:** ghi selected-file manifest, loaded/executed test-ID **multisets**, outcomes, skip reasons, expected failures, unexpected successes, import/setup/cleanup errors và exit codes. Giữ semantics `load_tests`, inherited tests và duplicate cases hiện có. Sau rename, dùng bảng old-ID → new-ID; cùng tổng `Ran N` không đủ.
6. **Failure lifecycle:** bất kỳ worker lỗi/spawn lỗi/timeout/crash/interrupt đều làm parent fail. Chốt global failfast: ngừng dispatch, dừng/reap cây subprocess còn chạy, rồi cleanup temp; không chỉ giữ `-f` trong từng worker. Output có giới hạn hoặc spool riêng, giữ diagnostics và log từng nhóm, tránh deadlock/mất lỗi vì buffer lớn.
7. **Runner regression tests:** invalid jobs; partition đầy đủ/xác định; jobs=1 compatibility; nested selection; missing/mixed paths; media/env isolation; worker fail/crash/import/empty suite; timeout/interrupt/failfast cleanup; large output; ID/outcome parity. Dùng mock/temporary pure-unit fixtures cho tooling, không dựng DB integration SQLite mới.
8. **Nghiệm thu:** module hẹp và runner tests trước; sau đó ba paired full-suite runs trên cùng frozen revision/máy/env, jobs=1 đối chiếu bản song song với ba partition seeds. Giữ exact case/outcome parity, không tăng skip/nới assertion. Có bằng chứng Windows và Linux CI. Đây là full-suite regression gate; integration/DDL/dialect phải kiểm chứng MySQL riêng, không lấy legacy SQLite fixtures làm qualification. Không chạy full suite liên tục cho mỗi sửa nhỏ; lập ngân sách benchmark theo mục 11 trước khi chạy hosted.
9. **Bật CI sau correctness gates:** giữ full/changed selection hiện hành; chỉ tăng worker count. Nếu ba paired CI runs không chứng minh lợi ích hoặc vượt RAM, giữ jobs=1 và ghi số đo. Mức giảm ≥30% là mục tiêu performance, không phải lý do bỏ test. Rollback về jobs=1; báo riêng backend-step/job/deploy gains.

#### 6.2.1 Trạng thái và bằng chứng (cập nhật 2026-10-23, Claude Code)

Có hai bản `--jobs`, chưa bản nào được tích hợp. Coordinator chọn một bản trước khi rebase (tracker, MSG-03). Không ghi đè bản còn lại khi chưa có đồng ý của owner.

| Tiêu chí | Bản A: nhánh local `wip/test-speed`, commit `987f6ead` đến `a1f08cda` | Bản B: checkout chính, chưa commit (`worker_o17_prb_parallel`) |
| --- | --- | --- |
| Một nhóm file được tính pass khi | exit 0 **và** summary `OK` với `Ran > 0` | exit 0 (`scripts/run_tests.py:1873` ở checkout chính, đọc lúc 05:55) |
| `auto` | CPU khả dụng; trần theo RAM trống (768 MiB/worker); 2 khi không đọc được RAM | `min(cpu, 4, số file)` (dòng 1647) |
| Output | spool ra file, in lại theo khối 64 KiB | `proc.communicate()` không timeout, giữ trong RAM (dòng 1744) |
| Dừng worker | failfast ngừng dispatch và kill worker đang chạy (`taskkill /T` trên Windows, fallback kill); `--bin-timeout`; Ctrl+C/SIGTERM | failfast kill sibling; Ctrl+C |
| CI | push/PR giữ 1; `workflow_dispatch` có `backend_jobs`, `backend_partition_seed`, `validation_scope` và in hash manifest; job `backend` có `timeout-minutes: 30` | không đổi CI |
| Evidence full suite | bảng dưới | worker ghi 44/44 unit test; chưa có so sánh ID full suite |

Gate cho bản A, đánh số theo các bước ở trên:

| Bước | Trạng thái | Bằng chứng hoặc phần còn thiếu |
| --- | --- | --- |
| 1 Tiên quyết | Chưa đạt | FIX-01 còn hai candidate (checkout chính và worktree `nihongo-coordinator-fix01`). Bản A sẽ rebase sau khi chốt. Baseline tuần tự đã đo trên `57738edd`. |
| 2 Tương thích | Đạt local cho phần của PR B | `--jobs 1` sinh đúng lệnh cũ (`test_single_job_keeps_one_unittest_process_for_all_files`). Cho tới khi rebase lên FIX-01, nhánh này vẫn giữ hành vi cũ là lọc bỏ file thiếu rồi báo xanh; sửa đó thuộc FIX-01, và gate 2 chỉ đạt đủ sau khi rebase. |
| 3 Scheduling | Đạt local | Đã chạy jobs 1, 2 và 3. LPT theo kích thước file, ba nhóm mỗi worker (mỗi tiến trình mất 4–8 s import app). `--partition-seed N` (commit `61fdb9ff`) đổi trọng số tối đa 25% để thử cách chia khác với cùng số worker; seed được in trong log. |
| 4 Cô lập | Một phần | Mỗi nhóm có media/temp riêng, env lấy từ một snapshot, `UPDATE_SNAPSHOT=0`/`UPDATE_ROUTE_SNAPSHOT=0`. Đã rà: file SQLite chỉ nằm trong thư mục tạm của từng test; port chỉ có trong chuỗi URL, không bind; snapshot route chỉ ghi khi thiếu và nằm trong một file test; test Redis thật duy nhất skip khi thiếu `REDIS_URL`, các app test khác đặt `REDIS_URL=''`; máy local và job `backend` không có Redis. Giới hạn đã biết: trên Linux, timeout/failfast chỉ kill worker trực tiếp; tiến trình cháu (nếu một test tự spawn) có thể sống tới khi job kết thúc. Đây là đánh đổi có chủ ý: worker dùng chung process group với tiến trình cha để tín hiệu từ CI và Ctrl+C tới thẳng worker. Trên Windows dùng `taskkill /T`. |
| 5 Kết quả | Đạt local | `--manifest PATH` (commit `61fdb9ff`) ghi mỗi outcome một dòng `id, outcome, lý do skip` qua `scripts/unittest_manifest.py`. Wrapper này giữ nguyên tham số, output và exit code của `python -m unittest`, kể cả 5 khi không có test. Subtest lỗi, expected failure, unexpected success, lỗi import và lỗi fixture class/module đều có dòng riêng. File gộp được sắp xếp, giữ trùng lặp, in số dòng và SHA-256; nhóm không ghi manifest làm run fail. `scripts/compare_test_manifests.py` so manifest, hoặc log `-v`, theo multiset. |
| 6 Failure lifecycle | Đạt local | Test dùng subprocess thật: worker treo bị timeout dừng; failfast kill worker anh em đang sleep; worker không khởi động được làm run fail. |
| 7 Runner tests | Đạt local | 88 test tooling/workflow pass ở `a1f08cda` (runner, manifest wrapper và so sánh, probe runner có timeout, CI workflow, mapping coverage, deploy workflow). Job `backend` có `timeout-minutes: 30` và `--bin-timeout 1200`. |
| 8 Nghiệm thu | Windows đạt; Linux chưa | Ba run manifest trên cùng commit `61fdb9ff` (tuần tự, jobs 2 seed 1, jobs 3 seed 2) có cùng SHA-256 (bảng dưới). Linux cần run hosted (mục 12). Sau khi rebase lên FIX-01 phải lập lại baseline manifest tuần tự, vì S2 đổi ID test. |
| 9 Bật CI | Chưa | Push/PR vẫn `--jobs 1`. |

Bằng chứng full suite (Windows, 16 logical CPU, 15,4 GB RAM, có ứng dụng khác chạy song song; thời gian chỉ dùng để so sánh tương đối):

| Run | Revision | Jobs / số nhóm | Kết quả | Wall |
| --- | --- | --- | --- | ---: |
| Baseline tuần tự | `57738edd` | 1 | 251 file, 2.638 test, `OK (skipped=7)` | 1.561 s |
| Song song | candidate ngay trước `987f6ead` (chưa có các sửa lifecycle) | 2 / 6 | Cùng multiset 2.638 ID và 7 skip như baseline, thêm 16 test runner mới, 0 lỗi | 975 s |
| Song song | `6569ebc9` (gồm `987f6ead`) | auto = 3 (bị trần RAM) / 9 | Cùng multiset 2.638 ID và 7 skip như baseline, thêm 20 test runner mới, 0 lỗi | 590 s |
| Manifest, tuần tự | `61fdb9ff` | 1 / 1 | 2.666 dòng (2.659 ok, 7 skipped), SHA-256 `11faa70acd23…463` | 1.036 s |
| Manifest, song song | `61fdb9ff` | 2, seed 1 / 6 | Cùng SHA-256 | 532 s |
| Manifest, song song | `61fdb9ff` | 3, seed 2 / 9 | Cùng SHA-256 | 500 s |

Ba run manifest có cùng hash, nghĩa là cùng multiset (ID, outcome, lý do skip) trên ba cách chia nhóm. So log `-v` bằng `scripts/compare_test_manifests.py --verbose-logs` cũng cho kết quả giống hệt nhau cho hai run song song đầu so với baseline tuần tự (2.638 bản ghi).

Đỉnh working set một worker đo được trên full suite: 653 MB (các worker khác 438–566 MB). Máy local thường chỉ còn 1–2,5 GB RAM trống, nên `auto` trên máy này ra 1–3 worker, không phải 16.

### 6.3 PR C: rà soát và chia tầng `mysql-contract` (≈2–3 ngày, dùng `$mysql` + `$flama-database-architecture`)

Mục tiêu: nhóm 337 phút/tháng, đồng thời là critical path 14 phút.

1. Không đổi hành vi: tách các step nhiều probe (field identity: 5 probe; historical/deck count: 2 probe) thành mỗi step một probe để lấy thời gian. Giữ thứ tự, env và artifact/env-file chuẩn bị dùng chung; tách setup của historical/deck count khỏi hai command mà không làm mất anchor user hoặc env file. Cập nhật workflow contract và command-path checks.
2. Lập bảng rà soát và đưa vào RFC. Mỗi probe có các cột:
   - Probe và tham số
   - Migration hoặc phase mà nó bảo vệ
   - Thời gian chạy
   - Lần cuối code được bảo vệ thay đổi
   - Đây là qualification của một cutover đã hoàn tất, hay contract cần chạy với mọi thay đổi
   - Chủ sở hữu ký duyệt
    - DB target/helper, mutation/reset/cleanup, dùng chung state hoặc dependency vào probe trước
    - Invariant/test cases thay thế, trigger PR/master/migration và candidate revision được bảo vệ
3. Các phương án, mỗi phương án cần dữ liệu từ bước 2:
   - (a) Gate riêng các probe qualification của cutover đã xong (ví dụ field identity cutover, xác nhận production ngày 2026-10-11) theo pattern nguồn của chính chúng cộng `migrations/**`.
   - (b) Chạy song song các probe độc lập trên các database riêng (`ci_probe_<n>`) trong cùng service MySQL; đo mức tranh chấp CPU trên 2 vCPU.
   - (c) Chỉ giảm tham số tải khi tài liệu của probe cho phép.
4. Quy tắc cứng:
   - `bootstrap_historical_schema.py` + `flask db upgrade` luôn chạy khi `mysql-contract` chạy.
   - Thay đổi `migrations/**` hoặc `models/**` luôn chạy đủ tầng MySQL.
   - Không bỏ probe nào chỉ dựa trên tên file.
    - Không chạy probe song song trước khi chứng minh không chia sẻ/reset schema hoặc state. Đọc từng probe/helper; tên `probe_*_mysql.py` không chứng minh an toàn.
    - Không hạ tải hoặc đẩy nightly để đạt mục tiêu thời gian khi chưa chứng minh invariant/coverage tương đương. Ưu tiên tối ưu setup/query/đo timing mà giữ gate; benchmark tổng job gồm setup và contention.

#### 6.3.1 Số đo từng probe, inventory và phương án (cập nhật 2026-10-23, Claude Code)

Bước 1 (mỗi step một probe) đã có trong diff FIX-01 ở checkout chính, chưa commit. Số đo dưới đây lấy từ log job `mysql-contract` của run `39775470111` (trước khi tách step), cùng benchmark cục bộ.

**Finding chính.** Sáu probe nặng tốn gần như đúng 7,2 s cho mỗi test, bất kể test kiểm gì:

| Probe (tham số CI) | Test | Giây CI | Giây/test |
| --- | ---: | ---: | ---: |
| `probe_review_analytics_outbox_mysql.py` | 33 | 232 | 7,0 |
| `probe_p5_direct_replay_mysql.py --overlay-only` | 26 | 189 | 7,3 |
| `probe_forecast_snapshots_mysql.py` | 16 | 117 | 7,3 |
| `probe_field_value_consumers_mysql.py` | 9 | 65 | 7,2 |
| `probe_p7_session_retention_mysql.py` | 7 | 52 | 7,4 |
| `probe_p5_analytics_mysql.py` | 6 | 45 | 7,6 |

Nguyên nhân: các probe này chạy lại test fixture của suite SQLite trên một schema MySQL riêng. Mỗi test `create_all` rồi `drop_all` 115 bảng. Trên MySQL, mỗi `CREATE TABLE` là DDL atomic, ghi data dictionary, fsync và tạo file `.ibd`. Đo cục bộ trên mysqld 8.0.40 Windows: một `create_all` mất 17–19 s, một `drop_all` 4–5 s. Như vậy khoảng 700 trên 839 s của job là dựng và xoá schema, không phải phần kiểm contract. Ba run gần nhất có `mysql-contract` 839 s (`39775470111`, push master), 1.064 s (`39247544956`, push master) và 1.320 s (`39779317426`, PR), nên mọi so sánh cần ít nhất hai run mỗi bên.

**Inventory** (cột chủ sở hữu ký duyệt và "qualification hay contract" để domain owner điền):

| Probe | Schema đích và dọn dẹp | State dùng chung | Chạy song song |
| --- | --- | --- | --- |
| outbox, direct replay (chỉ với `--overlay-only` như lệnh CI hiện tại; chế độ đầy đủ chưa được rà để chạy song song), forecast, consumers, P5 analytics | Schema sinh ngẫu nhiên `flama_*_probe_<pid>_<hex>`; guard loopback, từ chối trùng `DB_NAME`; `DROP DATABASE` rồi kiểm lại | Không; mỗi probe ghi report riêng | Được (đã đọc code) |
| P7 retention | Như trên | `GET_LOCK` với key băm theo `DATABASE()`, nên mỗi schema có khoá riêng | Được |
| field identity, cutover | Schema sinh ngẫu nhiên | Không | Không cần (0,3 và 2,5 s) |
| retirement fresh chain, P9 connect fence | Schema sinh ngẫu nhiên | Chưa rà hết | Chưa đề xuất |
| P1-02 locking | Tạo bảng `p102_concurrency_probe_*` **trong schema `ci`** | Schema `ci` | Không |
| P5 write concurrency | Schema sinh ngẫu nhiên | Đo tranh chấp khoá; chia CPU với probe khác làm sai mục đích đo | Không, chạy riêng |
| historical review analytics, deck counts | Schema `ci` qua `output/analytics-counts-ci.env`, anchor user id 1 | Schema `ci` | Không |

**Phương án bổ sung cho bước 3**, đều giữ mọi probe và mọi test:

- **(d) Datadir MySQL trên tmpfs**: thêm `--tmpfs /var/lib/mysql` vào `options` của service. Engine, phiên bản, isolation, locking, JSON và DDL không đổi; chỉ bỏ chi phí fsync và tạo file, vốn là phần lớn của 7,2 s/test. Dữ liệu mất khi container dừng, điều này vô hại với CI. Chưa đo trên Linux; Windows không mô phỏng được tmpfs. Rủi ro cần xử lý trước hoặc đo ở run đầu:
  - *RAM*: binlog vẫn bật trên service (không truyền được cờ mysqld qua `services`) và lớn dần theo DDL của 97 test; cộng redo 100 MB và datadir ban đầu ≈200 MB, tất cả nằm trong RAM. Đặt trần `--tmpfs /var/lib/mysql:rw,size=2g`, để khi đầy thì mysqld báo lỗi ghi rõ ràng thay vì runner bị OOM; thêm một step cuối job in `SHOW BINARY LOGS` và dung lượng datadir để đo peak.
  - *`innodb_flush_method`*: image `mysql:8.0` mặc định `fsync` trên Linux nên tmpfs dùng được. Nếu đổi image sang 8.4 thì kiểm lại, vì tmpfs không hỗ trợ `O_DIRECT`.
  - *Cửa sổ thời gian khoá*: commit nhanh hơn có thể làm hẹp cửa sổ tranh chấp trong probe concurrency (P1-02, P5). Các probe này ép thứ tự bằng barrier chứ không bằng thời gian, nhưng vẫn so số đo chờ khoá (`snapshot_wait_ms` và tương tự) trong report trước và sau khi bật tmpfs.
  - *Gate*: mọi step của `mysql-contract` phải PASS, kể cả `bootstrap_historical_schema.py` và `flask db upgrade`, không chỉ các probe.
  - Thêm `timeout-minutes` cho job `mysql-contract` (run chậm nhất gần đây 22 phút) cùng lúc với thay đổi này.

  Thay đổi nhỏ, rollback bằng revert.
- **(b) như trên, có công cụ**: `scripts/run_mysql_probes.py` (commit `6569ebc9`, chưa nối vào `ci.yml`) chạy sáu probe được phép song song, 2 cùng lúc, giữ nguyên lệnh và env của từng probe, in bảng thời gian từng probe. Probe concurrency và probe dùng schema `ci` giữ step tuần tự riêng. Chạy cục bộ 2 probe cùng lúc: sáu probe PASS, wall giảm từ 2.191 s xuống 1.118 s (bảng dưới).
- **(e) Park: dùng lại schema trong một probe** (tạo một lần, reset giữa các test). Lợi nhất, gần 7 s/test, nhưng đổi lifecycle fixture, nên chịu cùng gate với H1 trong RFC (reset có kiểm chứng, AUTO_INCREMENT, FK, state sau commit).
  - *Đã làm 2026-10-25 (Claude Code), theo yêu cầu người dùng.* `reuse_generated_schema` trong `scripts/mysql_probe_db.py` thay `db.drop_all` của fixture **chỉ trong tiến trình probe và chỉ khi engine trỏ đúng schema sinh tạm**: xoá dòng của mọi bảng có dữ liệu (tắt FK check trong session), đặt lại `AUTO_INCREMENT` (fixture forecast gọi thẳng `user_id=1`), rồi chứng minh mọi bảng rỗng. Nếu hình dạng schema (bảng, cột, index, constraint, FK, CHECK) khác lần dựng đầu thì gọi `drop_all` thật để test sau dựng lại. Không sửa fixture SQLite, không đổi lệnh probe; bảy probe ghi `schema_reuse` (resets/rebuilds/tables_emptied) vào report. Step mới trong `mysql-contract` chạy `tests/test_mysql_probe_schema_reuse.py` trước các probe (xoá dòng và id quay về 1, DDL đổi thì dựng lại, engine khác giữ `drop_all` thật).
  - Đo cục bộ mysqld 8.0.40 cùng ngày: `create_all` 115 bảng 10,9–11,6 s, `drop_all` 2,2–2,5 s, reset 0,06–0,2 s. `probe_p5_analytics_mysql.py` 82,2 s → 27,7 s. Tám probe theo đúng lệnh CI đều PASS, mọi probe `rebuilds=0` (ba test migration trả schema về nguyên dạng); chạy lại bảy probe với thứ tự test đảo ngược cũng PASS. Số đo hosted ghi sau run CI đầu tiên.

Thứ tự đề xuất: (d) trước, đo hai run; sau đó (b) nếu `mysql-contract` vẫn là critical path; (a)/(c) chỉ sau khi owner ký bảng inventory.

**Trạng thái 2026-10-23 (Claude Code).** Người dùng yêu cầu làm luôn, nên (d) và (b) được nối vào `ci.yml` trong cùng commit local `902c0cd5`, trên nền commit tách step `dbc5b736`:

- Service có `--tmpfs /var/lib/mysql:rw,size=2g`. Job có `timeout-minutes: 40`, và một step cuối `if: always()` in `df`/`du` của datadir, tổng binlog và `free -m`.
- Sáu probe tự tạo schema chạy trong một step, `run_mysql_probes.py --jobs 2 --timeout 1500`, dài nhất trước, giữ nguyên lệnh và tham số. P1-02, P5 write concurrency, hai probe dùng schema `ci`, hai probe field identity nhanh, retirement chain, P9 fence và các focused test vẫn là step tuần tự riêng.
- `tests/test_ci_workflow.py` khoá các điểm trên: tmpfs có trần, job có timeout, step đo chạy cả khi job lỗi, đúng sáu probe trong step song song với lệnh không đổi, mỗi probe chạy đúng một lần, các probe phải tuần tự không nằm trong step song song. 121 test tooling/workflow pass.
- Đã chạy đúng step song song lấy từ `ci.yml` của commit `902c0cd5` (worktree sạch, chỉ đổi interpreter và `DB_PORT`) trên mysqld 8.0.40 dùng một lần, ghim 2 core, durability mặc định. Sáu probe PASS, exit 0, wall 1.221 s; tổng thời gian sáu probe 2.433 s (outbox 817, direct replay 662, forecast 393, consumers 225, P7 179, P5 analytics 157). Sau run không còn schema probe nào sót lại. Tmpfs không kiểm được trên Windows.
- Vì (d) và (b) vào cùng lúc, run hosted đầu tiên tách hiệu quả bằng bảng thời gian từng probe mà `run_mysql_probes.py` in ra. Ở local, thời gian từng probe gần như không đổi khi chạy song song, nên thời gian mỗi probe giảm so với run CI cũ (outbox 232 s, direct replay 189 s, forecast 117 s, consumers 65 s, P7 52 s, P5 analytics 45 s) là phần của tmpfs; khoảng cách giữa wall của step và tổng thời gian sáu probe là phần của chạy song song. Nếu run hosted lỗi vì tmpfs, revert riêng dòng `--tmpfs`; nếu lỗi vì chạy song song, đặt `--jobs 1`.

Benchmark cục bộ trên mysqld 8.0.40 dùng một lần, ghim 2 core cho cả mysqld lẫn probe, durability mặc định như image CI. Windows chậm khoảng 3 lần so với CI ở các probe này, nên chỉ so tương đối giữa hai cách chạy trên cùng máy:

| Probe | Tuần tự (s) | 2 probe một lúc (s) |
| --- | ---: | ---: |
| outbox | 759 | 766 |
| direct replay | 526 | 630 |
| forecast | 424 | 342 |
| consumers | 203 | 194 |
| P7 retention | 164 | 158 |
| P5 analytics | 115 | 141 |
| **Wall của sáu probe** | **2.191** | **1.118** |

Cả hai cách chạy, sáu probe đều PASS. Thời gian từng probe gần như không đổi khi chạy song song, tức probe bị giới hạn bởi DDL/I/O chứ không phải CPU; hai làn rút wall còn 51%. Suy ra cho CI (chưa đo): sáu probe tổng ≈700 s, chạy hai làn thì wall bị chặn dưới bởi probe dài nhất (outbox 232 s) và một nửa tổng (≈350 s), nên khoảng 350–400 s thay vì ≈700 s.

### 6.4 (Park) Validation theo tầng trên master

Chỉ làm khi đạt trigger ở mục 5. Thiết kế bắt buộc:

1. Phạm vi file khi push master = event range ∪ `DEPLOYED_RELEASE_SHA..HEAD`. Nếu không xác định được SHA đang chạy, hoặc diff lỗi, thì force chạy tất cả.
2. Nếu một tầng được chọn thì chạy *đầy đủ* tầng đó (`--all --backend-only`, `npm test`); tầng không đổi thì skip. Backend được chọn theo pattern rộng (mọi `*.py` ngoài `docs/`, `requirements.txt`, `migrations/**`, `models/**`), không theo mapping module.
3. Điều kiện của `deploy`:

```yaml
if: ${{ !cancelled() && !failure() && github.event_name == 'push' && github.ref == 'refs/heads/master' && needs.changes.outputs.deploy == 'true' }}
```

4. Test planner cần bao các tình huống:
   - Push frontend trong khi còn thay đổi backend chưa deploy: backend và MySQL vẫn chạy.
   - SHA không xác định: chạy tất cả.
   - Chỉ test hoặc docs: không deploy.
   - Push frontend trên release đã cập nhật: backend và MySQL skip, deploy vẫn chạy.

### 6.5 Vệ sinh quy trình (không tốn CI)

- 14/37 run PR bị lỗi hoặc bị huỷ. Chạy `python scripts/run_tests.py --changed` ở local trước khi push để giảm số run PR thất bại.
- Theo dõi quota hằng tháng tại Settings → Billing.

## 7. Ước tính tác động

Các con số dưới đây là ước tính và phải đo lại sau mỗi PR.

| Hạng mục | Hiện tại (phút/30 ngày) | Sau khi làm | Điều kiện |
| --- | ---: | --- | --- |
| `spa-contract` (PR A) | 41 | ≈0 (`frontend` +≈10) | Xoá shim |
| `backend` (PR B) | 420 | −125…−190 | Runner ≥2 vCPU, không có xung đột giữa các file |
| `mysql-contract` (PR C) | 337 | −0…−130 | Tuỳ kết quả rà soát và chủ sở hữu duyệt |
| Tổng | ≈1.045 | ≈700–870 | Thời gian push giảm theo critical path `mysql-contract` |

Cập nhật theo số đo 2026-10-23 (mục 6.2.1, 6.3.1); các dòng "chưa đo" không được dùng làm cam kết:

| Hạng mục | Đã đo | Chưa đo |
| --- | --- | --- |
| `backend` | Windows cùng revision: jobs 2 nhanh hơn 1,6 lần so với tuần tự (975 s so với 1.561 s), cùng multiset ID | Runner Linux 2 vCPU; step `backend` lịch sử 585–914 s, chênh lớn giữa các run |
| `mysql-contract` | ≈700/839 s là dựng/xoá schema theo từng test; sáu probe nặng độc lập về schema; chạy hai làn trên 2 core local giảm wall của sáu probe 1,96 lần, cả sáu PASS | Mức giảm của tmpfs (d) và song song (b) trên Linux (ước tính (b): còn 350–400 s cho sáu probe); RAM peak khi dùng tmpfs |
| Critical path push | Hiện là `mysql-contract` (839–1.320 s ở ba run gần nhất), dài hơn `backend` (585–914 s) | PR B giảm phút tính phí nhưng không rút ngắn thời gian push; chỉ PR C làm được việc đó |

## 8. Quyền sở hữu và thứ tự

- Thứ tự hiện hành: review/FIX-01 → manifest baseline → PR B; nghiệm thu hosted PR A khi có run. PR C inventory read-only có thể làm độc lập; sửa workflow chờ owner release file. Phần (a)/(b) PR C chỉ sau review bảng probe theo domain.
- Mỗi file chỉ có một agent ghi. Chủ sở hữu hiện tại xác nhận release `ci.yml`/`tests/test_ci_workflow.py` trước khi giao độc quyền cho FIX-01 hoặc PR C; trạng thái merge ghi riêng. PR B nhận runner/runner tests sau khi owner FIX-01/S2 bàn giao, không tự ghi đè diff đang có.
- POC vẫn `PARKED` dù file đã xuất hiện lại dạng untracked; không tự kích hoạt hoặc đưa mapping POC vào commit S2/PR B. Không xoá/reset file của phiên khác. Người nhận task xác nhận ownership/HEAD/diff; tracker không tự dispatch agent.
- Cập nhật 2026-10-23 (Claude Code). Hiện có hai candidate cho FIX-01 (diff chưa commit ở checkout chính của `worker_o17_fix01`, và worktree `nihongo-coordinator-fix01` của Codex) và hai candidate cho PR B (mục 6.2.1). Thứ tự tích hợp đề xuất, mỗi bước chỉ một người ghi file liên quan:
  1. Codex chọn hoặc gộp một bản FIX-01. Owner bản được chọn commit local; bản còn lại không được copy đè.
  2. Quyết định S2: giữ (khi đó phải theo FIX-01 về caller/mapping/path) hoặc hoàn tác. Hiện chưa có lợi ích thời gian nào từ S2, vì discovery vẫn quét đệ quy.
  3. Codex chọn một bản PR B. Bản được chọn rebase lên FIX-01; bản còn lại bỏ phần `--jobs` khỏi checkout chính sau khi owner của nó đồng ý. FIX-01 và PR B cùng sửa `.github/workflows/ci.yml`, `scripts/run_tests.py` và `tests/test_modular_test_runner.py`. Khi rebase phải giữ cả hai phía: từ FIX-01 là path retirement, step probe đã tách, kiểm tra file thiếu và nested selection; từ PR B là input dispatch, `validation_scope`, giới hạn thời gian, `--jobs`/`--manifest`. Sau đó chạy lại `tests/test_ci_workflow.py`, `tests/test_modular_test_runner.py`, `tests/test_test_mapping_coverage.py`, rồi lập baseline manifest tuần tự mới (gate 8).
  4. PR C bước 1 (tách step) đi cùng FIX-01 vì cùng sửa `ci.yml`. Phương án (d)/(b) của mục 6.3.1 vào sau, khi `ci.yml` không còn ai giữ.
  5. Nghiệm thu hosted theo mục 12, chỉ sau khi người dùng đồng ý push.

## 9. Quyết định đã ghi nhận và điểm mở

POC đã park và job `spa-contract` đã xoá trong P0; không yêu cầu chốt lại những việc đã ghi nhận. Người dùng đã giao Codex điều phối review và sửa kế hoạch. Đợt này không sửa app, runner hoặc CI của agent khác.

Owner triển khai FIX-01/PR B/PR C/S3 cần xác nhận file ownership và cung cấp evidence trước khi coordinator nghiệm thu. Không suy diễn việc agent đang hoạt động từ tên trong tracker hoặc danh sách process. Việc chuyển test/probe khỏi gate vẫn cần domain review với replacement cụ thể; chưa được phê duyệt từ một con số benchmark.

Điểm mở tại 2026-10-23 (bổ sung bởi Claude Code), theo thứ tự cần chốt:

| # | Quyết định | Ai chốt | Trạng thái |
| --- | --- | --- | --- |
| 1 | Chọn hoặc gộp bản FIX-01 (checkout chính hoặc `nihongo-coordinator-fix01`) và xử lý các review còn mở | Codex | Mở |
| 2 | Giữ hay hoàn tác S2; nếu giữ, mapping/caller/path phải theo FIX-01 | Người dùng | **Đã chốt 2026-10-23: giữ cả 22 file, không xoá; hoàn tác việc chuyển vào `tests/archive/`, đưa về đường dẫn cũ trong `tests/`.** Lý do: 22 file (202 test) chỉ chạy 51 s trên 1.561 s của suite; `test_note_stats_retirement.py` là fixture cho 2 test và 2 probe MySQL, `test_legacy_progress_retirement_audit.py` là fixture cho 1 test; 5 file chạy trong step CI của `mysql-contract`; khoảng 7 file bảo vệ hành vi đang chạy. Khi hoàn tác, bỏ cả các sửa của FIX-01 chỉ phục vụ đường dẫn archive (path CI, mapping, `parents[3]`, import trong test và probe), giữ các sửa chung (file thiếu thì fail, nested selection). Trước đó: Antigravity (MSG-08) đề nghị giữ ở archive, với lý do S2 ngăn discovery chạy lại test migration cũ. Kiểm tra ngày 2026-10-23 không thấy điều đó: `tests/archive/` và `tests/archive/legacy_migrations/` đều có `__init__.py`, nên `unittest discover -s tests` vẫn nạp 202 ID test trong archive (2.701 tổng), và `run_tests.py --all` (CI dùng) vẫn chọn đủ 22 file. Muốn S2 giảm workload thì phải loại archive khỏi selection một cách có chủ ý, mà theo mục 10.3 cần domain review và replacement cho các runtime regression trong đó |
| 3 | Chọn bản PR B (mục 6.2.1) | Codex | Mở |
| 4 | Cho push để chạy nghiệm thu hosted theo mục 12 (≈40 phút thêm) | Người dùng | Mở; hiện chỉ commit local |
| 5 | Giữ tmpfs và/hoặc probe song song sau khi đo hosted | Codex, domain owner ký bảng 6.3.1 | Chờ số đo |

## 10. Review điều phối: correctness, độ phủ, kiến trúc và triển khai

### 10.1 Phạm vi và bằng chứng

Snapshot review: HEAD `57738edd` cộng staged/unstaged/untracked changes trong checkout dùng chung. Code có thể tiếp tục đổi sau snapshot; các finding cần recheck khi owner bàn giao. Không gán lỗi cho một agent cụ thể chỉ từ tracker chưa xác nhận.

| Kiểm tra trong phiên review | Kết quả / giới hạn |
| --- | --- |
| CI/deploy/runner/mapping: `run_tests.py --file tests/test_ci_workflow.py tests/test_deploy_workflow.py tests/test_modular_test_runner.py tests/test_test_mapping_coverage.py --backend-only` qua venv | 57 tests pass; không chứng minh các gate đã chạy đủ case |
| Mock runner với explicit path đã mất | Trả `True`, không gọi subprocess; false-green path tái hiện không cần DB |
| Map một edit `tests/archive/legacy_migrations/test_retirement_fresh_migration_chain.py` | Cả modules/backend/frontend rỗng; thiếu targeted coverage tái hiện |
| AST so HEAD với 22 file rename | 202 declared test methods, thân method không đổi; không phải executed-case parity hoặc chứng minh fixtures đúng |
| `npm test -- --run src/features/worksheets/DeckWorksheetModal.test.tsx` | 22 pass; test phase 6,03s, tổng 13,76s một lượt; chưa có paired baseline |
| MySQL migration/probe/integration và hosted Actions | Không chạy trong review này; MySQL service tồn tại không đồng nghĩa đã nghiệm thu |
| UI/browser/visual parity | Chưa kiểm chứng; focused DOM tests không thay được visual review |

### 10.2 Findings và xử lý

| Mức | Finding có bằng chứng | Hệ quả / sửa cần thiết |
| --- | --- | --- |
| P1 | [CI](../../.github/workflows/ci.yml) retirement step còn 5 path cũ; [runner](../../scripts/run_tests.py) `run_backend_tests` lọc file không tồn tại | Step có thể xanh chỉ chạy frozen-template trong 6 suite yêu cầu. FIX-01 phải update mọi caller và fail với explicit file thiếu |
| P1 | `map_files_to_modules` chỉ nhận direct backend test bắt đầu `tests/test_` | Edit/nêu explicit nested archive path chọn rỗng. Sửa nested recognition, regression CLI + planner và CI command-path validity |
| P1 | [migration-chain test đã chuyển](../../tests/archive/legacy_migrations/test_retirement_fresh_migration_chain.py) còn `parents[1] / 'migrations'` | Nay trỏ `tests/archive/migrations` không tồn tại. Audit relative paths/imports/snapshots mọi rename; kiểm chứng chain trên MySQL |
| P1 | H1/H2 cũ yêu cầu áp SQLite/shared harness toàn suite dù RFC park; H3 dời toàn probe khỏi predeploy | Sai policy/thiếu isolation và replacement coverage. Sửa contracts/tracker, giữ gates hiện hành |
| P2 | Recursive discovery vẫn chạy archive; module lists cũng giữ 22 file | S2 chưa giảm workload. Không tự loại archive để tạo speedup; phân loại từng case theo runtime invariant |
| P2 | [Worksheet hook](../../frontend/src/features/worksheets/hooks/useWorksheetStudio.ts) dùng debounce 0 trong test, immediate branch thay timer 300 ms | 22 case xanh không kiểm tra production timing/cancel path. Dùng fake timers, giữ hook production, thêm race/cancel/error tests |
| P2 | Worksheet test gán global `IS_REACT_ACT_ENVIRONMENT` không khôi phục; `waitTick(0)` vẫn phụ thuộc scheduling | Restore globals/timers/mocks; flush/advance có kiểm soát thay real sleep |
| P2 | Runner diff trộn mapping POC tới file untracked với S2; PR B chưa có `--jobs` | Tách dependency/commit scopes; không ghi hoàn thành hoặc merge catalog thiếu file |
| P2 | Tổng `Ran N`, số assertion hoặc speed target được dùng thay chứng minh hành vi | Dùng manifest/outcome/invariant gates dưới đây; không có số coverage % đáng tin trong audit này |

### 10.3 Độ phủ và độ chính xác phải giữ

Ba lớp cần cùng đạt: **selection coverage** (case đúng được chọn), **behavior coverage** (assertion bảo vệ invariant đúng), **fidelity/isolation** (đúng engine/config/timing và không nhiễm state). Dời file giữ nguyên assertion chỉ chứng minh một phần cấu trúc; branch/line coverage cũng không thay thế các lớp này.

Manifest trước/sau phải ghi old full case ID → retained/re-homed ID, source symbols/invariant, fixture/engine/config, owner, trigger PR/domain/master/MySQL, outcome/skip reason và timing. Case bị đổi module chỉ chuẩn hoá bằng rename map cụ thể; giữ multisets để không che duplicate/lost cases. Không sửa expected values/nới assertion/tăng skip để hợp harness. Subtests và load/import/setup/cleanup failures phải hiện trong evidence.

| Nhóm | Invariants cần mapping và gap audit | Gate |
| --- | --- | --- |
| Runner/CI | Missing/mixed paths, nested edits, rename/deletion, unmapped source fallback, empty/load/import failure, worker failure/timeout/interrupt, exact IDs/outcomes, deploy gating | Pure tooling tests; PR selection scenarios và hosted workflow trên đúng revision |
| Study/Decks | Owner + installed clone/source immutability, overlay/authority/revision, answer/undo/idempotency, bounded query, due/order/timezone/day boundary | Module tests và MySQL cho JSON/locking/concurrency |
| Templates/fields/media | Atomic create/publish/auth/remap, field identity, nested/legacy arrays, CSP/proxy/sanitization | Retain runtime assertions kể cả đang ở archive; domain tests + MySQL khi cần dialect |
| Migration/schema | Historical bootstrap → Alembic head, data/constraints/FKs, archive/restore/fences, fresh chain | Đủ MySQL gate khi models/migrations đổi; SQLite DDL không phải qualification |
| Analytics/forecast | Clone dedup, timezone buckets, freshness/authority, SQL bounds | Retain current runtime suites; tách shared fixtures trước khi loại archive |
| Worksheet | 300 ms boundary/coalescing/latest payload, abort/unmount/leave studio, stale success/error/loading, API error và UI/payload assertions | Focused fake-timer tests + typecheck; visual review khi đổi UI/behavior |

Không tuyên bố mọi invariant trên đã có coverage. Đây là checklist để owner lập case-ID mapping, đánh dấu existing/missing và bổ sung test cụ thể trước khi thay gate. Ưu tiên failure/negative/boundary cases có thể phát hiện bug thực; không thêm test đếm dòng hoặc chỉ lặp implementation.

Các file chuyển archive chứa runtime regressions rõ ràng: derived-card scope (17 declared methods), note query (16), note stats (14), template origin (12), provenance (6), telemetry (3). Mixed suite attachment/distribution còn runtime contracts. Fixture archive đang được analytics/forecast import. Không phân loại chúng là obsolete chỉ vì tên migration/retirement.

### 10.4 Kết luận kiến trúc và mức tối ưu

PR A dùng chung build hợp lý và có local evidence; hosted savings chưa được đo ở phiên này. PR B process-level parallelism tách khỏi shared app/schema là hướng ít thay lifecycle hơn, nhưng chưa tối ưu được chứng minh trước isolation/parity/resource benchmarks. PR C timing/inventory trước gate changes đúng thứ tự; probe có reset/shared state không được chạy song song cùng DB.

H1/H2 và nightly thay immediate validation chưa có cơ sở rollout. Loại runtime regressions khỏi gate, chuyển file làm mất selection/caller, hoặc bypass timing production làm suy yếu chất lượng dù case count không đổi; rename đúng caller/selection/parity tự nó không giảm độ phủ. Kế hoạch sửa ưu tiên correctness/coverage trước performance, rồi tối ưu setup, worker count và probe cost bằng số đo. S2/S3 hiện `REVIEW_REQUIRED`; PR B `PLANNED`; không kết luận các agent đã triển khai đạt chỉ từ status cũ.

Cuối review còn thấy `frontend/vitest.config.ts` và `frontend/src/test/setup.ts` untracked từ phiên khác. Thay đổi test setup toàn frontend cần ownership, FSD placement phù hợp và kiểm chứng riêng; kết quả một file Worksheet ở trên không nghiệm thu mọi thay đổi config/setup mới.

## 11. Cân bằng minutes và Actions storage 0,5 GB

### 11.1 Hạn mức, nguồn và snapshot

Người dùng xác nhận trần cần bảo vệ là **Actions storage 0,5 GB**. Dùng đúng allowance/đơn vị trong Billing cho tài khoản, không suy ra headroom từ một repo. [GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) liệt kê Free có 2.000 minutes, 500 MB artifact storage chia sẻ với Packages; cache riêng 10 GB/repo. Storage tính theo GB-hours: xoá object giảm sử dụng về sau, không xoá phần đã tích luỹ. Đây là các hạn mức khác nhau, không cộng cache vào 0,5 GB hoặc coi cache hết là toàn CI chắc chắn dừng.

Snapshot API read-only 2026-10-23 của `TrinhChung/Flama`: artifacts endpoint trả **0 artifacts / 0 bytes**, cache usage trả **4 caches / 508.722.223 bytes** (≈485 MiB). Đây chỉ là current repo usage, không gồm artifact/Packages repo khác hoặc accrued account storage. Billing usage API trả 404, CLI báo thiếu scope `user`; chưa xác minh remaining minutes, GB-hours, Packages hoặc account budgets. Không refresh quyền hay thay settings trong phiên này. Connector GitHub không có endpoint tổng billing/cache phù hợp nên dùng CLI read-only cho snapshot này; không download hoặc xoá dữ liệu.

[Billing docs](https://docs.github.com/en/billing/concepts/product-billing/github-actions) nói workflow logs/job summaries không tính vào artifact allowance, nhưng [changelog 27/08](https://github.blog/changelog/2026-08-27-actions-retention-will-cover-checks-workflow-runs-and-statuses/) nói logs billable. Không dùng giả định log miễn phí để cân bằng quota: ghi nhận điểm chưa nhất quán, đối chiếu SKU/report thực tế. [Thông báo 01/10](https://github.blog/changelog/2026-10-01-actions-retention-now-covers-checks-runs-and-statuses/) xác nhận retention còn ảnh hưởng checks/runs/statuses; giảm retention có thể mất bằng chứng review, không chỉ tiết kiệm bytes.

### 11.2 Ngân sách vận hành đề xuất

Các ngưỡng dưới đây là policy bảo vệ đề xuất cho kế hoạch, không phải cấu hình GitHub đã được đổi. Mỗi PR tối ưu phải đạt **đồng thời** coverage/fidelity, minutes và storage; không lấy trung bình để quota này che quota kia.

| Tài nguyên | Mục tiêu dự báo / phần dự phòng | Cách kiểm tra |
| --- | --- | --- |
| Standard runner minutes toàn account | Routine forecast ≤75% allowance (1.500/2.000 nếu Free); ≥25% dành rerun/hotfix/migration/release | Current billing cycle, mọi repo, mọi attempt/cancelled run, loại runner; số 1.045 phút/30 ngày lịch sử không phải remaining allowance |
| Actions shared storage 0,5 GB | Current peak và forecast GB-hours ≤70% allowance tương ứng, chừa ≥30%; mức danh nghĩa current target khoảng 0,35 GB theo UI | Artifacts + Packages toàn account, object lifetime/retention, accrued storage và remaining hours; không chỉ kích thước zip/build |
| Cache riêng | Khởi điểm soft budget 1 GiB/repo, dưới included limit; chỉ tăng nếu đo được lợi ích và vẫn có headroom | Byte count, hit/miss, key cardinality, branch copies, cold fallback và restore/upload cost |

Forecast theo thời gian **còn lại của billing cycle**, dùng mức burn bảo thủ từ 7/30 ngày, số PR/merge dự kiến và các run benchmark/migration đã lên lịch; cộng retry/burst scenario trước so ngưỡng. Với storage, theo dõi cả current/peak và `accrued_GB_hours + integral(projected_live_GB * remaining_hours)`, so với allowance cùng đơn vị do Billing cung cấp. Object còn lưu qua tháng vẫn tiếp tục chiếm storage; tháng mới reset minutes/accrual, không tự xoá object. Thiếu billing telemetry thì ghi `UNVERIFIED`, không kết luận chắc chắn đủ đến cuối tháng.

### 11.3 Thay đổi tối ưu được chấp nhận

- Giữ **không Actions build-artifact transfer**: PR A dùng build tại cùng job; không upload Vite/dist/node_modules, DB dumps, screenshots/video hoặc full manifests mỗi run để đổi lấy vài phút. Báo cáo gọn có thể ở bounded job output; storage accounting của log vẫn cần xác minh như trên. Retention diagnostic nếu mở sau này phải có byte cap, số bản tối đa và expiry được review.
- Cache chỉ dependency store cần thiết (pip/npm) với OS/runtime/lockfile key; không thêm key theo SHA/run/time làm sinh bản mỗi commit, không cache secrets/env/DB/test-result làm test bỏ chạy. Cache miss/eviction phải vẫn chạy đủ test/build đúng revision; đo thêm cold-run minutes, không phụ thuộc cache để bảo toàn correctness.
- [GitHub cache policy](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching) có eviction; churn có thể làm minutes tăng lại. Không nâng paid cache limit, xoá hàng loạt artifact/cache, đổi billing/retention tự động chỉ từ review này. Inventory object/owner/lifetime trước cleanup; không xoá evidence release đang cần.
- Trước ba paired hosted benchmark runs của PR B, ước tính tổng phút (baseline + optimized + retry) và storage phát sinh; dùng local paired runs trước, gộp xác nhận trong run vốn cần thiết khi hợp lệ. Nếu vượt phần routine budget, lùi benchmark/cron/duplicate work; giữ các correctness/release gates và jobs=1. Không skip test cần thiết hoặc deploy revision chưa được validate để tiết kiệm quota.
- Cảnh báo khi current **hoặc forecast** chạm 70% minutes/storage, hoặc dự báo cạn trước cuối kỳ; ở 80% chỉ mở thêm workload không thiết yếu khi đã tính lại headroom. Không chờ mốc 90–100%. Cache theo soft cap riêng. Các mốc này cần được triển khai/đo ở task BUDGET-01, chưa có monitor tự động.
- Nghiệm thu tối ưu gồm cold/warm runs, same case/outcome manifests, total runner-minutes gồm reruns/setup, account-level storage forecast/peak/GB-hours, cache bytes/hit-rate và dự phòng hotfix. Nếu giảm minutes nhưng vượt Actions storage 0,5 GB, hoặc ngược lại, phương án không đạt.

## 12. Quy trình nghiệm thu hosted (kế hoạch trước push)

Các mốc và ước tính dưới đây được lập trước khi người dùng cho push. Kết quả Actions hiện hành ở checkpoint đầu tài liệu; PR B vẫn chưa chạy benchmark hosted nhiều seed theo quy trình này.

### 12.1 Chi phí tham chiếu

Run push master `39775470111`, làm tròn lên từng job: `changes` 1, `frontend` 7, `backend` 11, `mysql-contract` 14, `redis-contract` 1, `spa-contract` 1, `deploy` 2, tổng ≈37 phút tính phí. Một `workflow_dispatch` hiện chạy mọi validation job (planner coi mọi event không phải PR là `force_all`), không deploy: ≈35 phút. Ba cặp dispatch jobs 1/2 như vậy tốn ≈210 phút, khoảng 10% allowance 2.000 phút. Quá đắt so với mục 11.2.

### 12.2 Bổ sung cần có trước khi đo (thuộc PR B)

Trạng thái: cả bốn mục đã có trong commit local `61fdb9ff` trên nhánh `wip/test-speed`, với test tooling và workflow (85 test pass). Chưa chạy trên hosted.

1. **Manifest gọn trong log.** Job CI chạy backend không có `-v`, nên log hosted không có ID test để so. In toàn bộ `-v` vào log làm log lớn, mà mục 11.1 chưa chốt log có tính vào storage hay không. Đề xuất: runner nhận `--manifest PATH`, mỗi worker vẫn chạy `-v` nhưng output chỉ nằm trong spool; runner ghi file manifest (`ID<TAB>outcome<TAB>skip reason`, sắp xếp, giữ trùng lặp) và chỉ in ra log số dòng, số theo từng outcome và SHA-256 của manifest. Hai run khớp khi hash bằng nhau. Không upload artifact. Khi có `--manifest`, `--jobs 1` cũng chạy qua đường spool với một worker.
2. **`--partition-seed N`** để đổi cách chia nhóm khi giữ nguyên số worker (bước 3 và 8 của mục 6.2).
3. **Input `validation_scope` cho `workflow_dispatch`** (mặc định `all`): khi là `backend`, chỉ chạy `changes` và `backend`. Một dispatch đo khi đó tốn ≈12 phút thay vì ≈35. Push và PR không bị ảnh hưởng.
4. **Script so sánh manifest** commit vào `scripts/`, có test tooling, để mọi reviewer chạy lại được.

### 12.3 Trình tự và ngân sách

| Bước | Run | Ước tính phút | Gate |
| --- | --- | ---: | --- |
| PR A | Run PR thường đầu tiên sau push | 0 thêm | Mục 6.1 bước 6 |
| PR B, mốc | Sau khi rebase lên FIX-01, một dispatch `validation_scope=backend`, `backend_jobs=1` | ≈12 | Có manifest baseline hosted của commit đã tích hợp. So với manifest tuần tự local cùng commit bằng `scripts/compare_test_manifests.py`; khác biệt chỉ được chấp nhận khi giải thích được bằng nền tảng (ví dụ lý do skip theo hệ điều hành). Hash của mốc hosted là chuẩn cho ba lượt dưới |
| PR B, ba lượt đo | Cùng commit, ba dispatch `backend_jobs=2` với seed 1, 2, 3 | ≈27 (3 × ≈9) | Hash bằng mốc ở cả ba lượt; RAM runner không cạn; step `backend` ngắn hơn mốc. Vì step `backend` lịch sử dao động 585–914 s, so thêm với ≥2 run push master gần nhất (jobs 1, không tốn thêm phút) |
| Sau các lượt đo | Đọc kích thước log của các run vừa chạy bằng `gh api` (không tải log về) | 0 | Ghi tổng; nếu mục 11.1 chốt log tính vào storage thì cộng vào forecast |
| PR C (d) tmpfs và (b) song song, commit `902c0cd5` | Hai run có `mysql-contract` sau khi push (PR hoặc master đã cần chạy) | ≈0 thêm | Mọi step của `mysql-contract` PASS, kể cả bootstrap và `flask db upgrade`; job ngắn hơn ≥2 run trước đó (839–1.320 s); peak datadir/binlog trong step đo dưới trần 2g; số đo chờ khoá của P1-02/P5 không lệch bất thường; tách phần tmpfs và phần song song bằng bảng thời gian từng probe (mục 6.3.1) |

Tổng thêm ≈40 phút, khoảng 2% allowance (bản trước của kế hoạch tính ≈72 phút cho ba cặp xen kẽ; review Gemini chỉ ra parity theo hash chỉ cần một mốc, vì `--jobs 1` chỉ có một nhóm nên seed không đổi gì). Nếu forecast quota ở mục 11.2 đã chạm 70%, lùi các bước có phút thêm và giữ `--jobs 1`. Chỉ đổi mặc định `backend_jobs` cho push/PR sau khi cả ba lượt đạt.

### 12.4 Review của Gemini và cách xử lý (2026-10-23)

Gemini (`gemini-3.8-flash-high` qua `agy` CLI, chế độ `plan`, sandbox, chỉ đọc file) review các phần mới của kế hoạch và code nhánh `wip/test-speed` ở `61fdb9ff`. Phiên Antigravity IDE không trả lời ASK-01/ASK-02 trong tracker. Kết luận của reviewer: "Cần bổ sung". Mỗi finding được xử lý như sau:

| Finding | Xử lý |
| --- | --- |
| P1: `run_mysql_probes.py` không có timeout | Sửa: `--timeout`, probe quá hạn bị kill và fail (`a1f08cda`, có test) |
| P1: job `backend` không có `timeout-minutes`, worker treo có thể tốn tới 360 phút | Sửa: `timeout-minutes: 30` và `--bin-timeout 1200` (`a1f08cda`, có test workflow) |
| P1: binlog trên tmpfs có thể làm cạn RAM | Bổ sung vào 6.3.1 (d): trần `size=2g` và đo peak; không tắt được binlog qua `services` |
| P1: tmpfs không hỗ trợ `O_DIRECT` | Ghi rủi ro ở 6.3.1 (d): `mysql:8.0` mặc định `fsync` nên áp dụng được; kiểm lại nếu đổi sang 8.4 |
| P1: runner nhánh này vẫn lọc bỏ file thiếu | Làm rõ gate 2 ở 6.2.1: đây là phần của FIX-01 theo thiết kế, gate 2 chỉ đạt đủ sau khi rebase |
| P1: thiếu baseline manifest lại sau khi rebase lên FIX-01 | Bổ sung vào gate 8 và bước "PR B, mốc" ở 12.3 |
| P2: ngoại suy tốc độ Windows cho CI 2 vCPU | Sửa mục 1 điểm 7: kỳ vọng trên CI tối đa khoảng 1,6 lần, chưa đo |
| P2: hai run lịch sử thiếu run ID | Bổ sung `39247544956` và `39779317426` vào 6.3.1 |
| P2: `load_dotenv` trong P7/P5 analytics thiếu `override=False` | Không sửa: `python-dotenv` mặc định `override=False`, và CI truyền `DB_*` qua env nên giá trị env thắng |
| P2: direct replay chỉ an toàn với `--overlay-only` | Ghi rõ điều kiện trong inventory 6.3.1 |
| P2: tmpfs làm hẹp cửa sổ tranh chấp khoá | Ghi rủi ro và thêm so sánh số đo chờ khoá vào gate tmpfs ở 12.3 |
| P2: ngân sách 72 phút có thể giảm | Đổi 12.3: một mốc cộng ba lượt seed, ≈40 phút |
| P2: thiếu kiểm tra kích thước log sau benchmark | Thêm dòng kiểm tra log vào 12.3 |
| P2: Linux không kill tiến trình cháu | Ghi giới hạn ở gate 4: đánh đổi có chủ ý để tín hiệu CI và Ctrl+C tới thẳng worker; Windows dùng `taskkill /T` |
| P2: `--jobs` số cụ thể bỏ qua trần RAM | Giữ thiết kế (số cụ thể là quyết định của người gọi), thêm cảnh báo khi vượt ước tính RAM (`a1f08cda`, có test) |
| P2: gate tmpfs thiếu kiểm tra migration | Gate tmpfs ở 12.3 yêu cầu mọi step PASS, kể cả bootstrap và `flask db upgrade` |
| P3: cột bản B dựa trên `task.md` | Đã đối chiếu code ở checkout chính và ghi số dòng trong bảng 6.2.1 |
| P3: seed `0` có thể bị hiểu sai trong bash | Không sửa: `[ -n "$BACKEND_PARTITION_SEED" ]` coi `0` là giá trị hợp lệ, và runner nhận mọi số nguyên |

Lượt 2 (cùng model và chế độ, trên commit `a1f08cda`): reviewer xác nhận cả 18 dòng trên đã được xử lý đúng như ghi, và kết luận **"Đủ để triển khai"** theo thứ tự mục 8 khi các quyết định ở mục 9 được chốt. Ba điểm mới, đều đã xử lý:

| Finding lượt 2 | Xử lý |
| --- | --- |
| P2: FIX-01 và PR B cùng sửa `ci.yml`, rebase dễ mất cấu hình của một bên | Bổ sung chỉ dẫn hợp nhất và các test phải chạy lại vào mục 8 bước 3 |
| P3: `shlex.split` kiểu POSIX nuốt `\` trong đường dẫn Windows của `--probe` | Sửa: chuẩn hoá `\` thành `/` trước khi tách (`72ce0f5c`, có test) |
| P3: hash mốc hosted có thể khác hash local vì khác nền tảng | Sửa gate "PR B, mốc" ở 12.3: so bằng script, hash hosted là chuẩn cho các lượt hosted |

### 12.5 Kết quả nghiệm thu hosted PR B (2026-10-23, Claude Code)

Bốn lượt `workflow_dispatch` với `validation_scope=backend` chạy trên tag tạm `bench/prb-f140c0f8`, tức `f140c0f8` (master); tag đã xoá sau đo. Một lượt seed 1 chạy trùng do lỗi điều phối của script dispatch nên có thêm mẫu thứ hai. Tổng khoảng 54 phút tính tiền (job làm tròn), 0 artifact.

| Lượt | Run | Bước backend | Job | Kết quả |
| --- | --- | ---: | ---: | --- |
| Mốc `jobs=1` | [39949971329](https://github.com/TrinhChung/Flama/actions/runs/39949971329) | 944,3 s | 967 s | PASS 2.740 tests, 9 skip |
| `jobs=2` seed 1 | [39951999818](https://github.com/TrinhChung/Flama/actions/runs/39951999818) | 314,0 s | 334 s | **FAIL 1**: `test_parallel_backend_runner…test_exited_successful_root_cannot_leave_descendant_alive` |
| `jobs=2` seed 1 (lặp) | [39952110786](https://github.com/TrinhChung/Flama/actions/runs/39952110786) | 548,3 s | 566 s | PASS |
| `jobs=2` seed 2 | [39952779623](https://github.com/TrinhChung/Flama/actions/runs/39952779623) | 296,2 s | 312 s | PASS |
| `jobs=2` seed 3 | [39954752393](https://github.com/TrinhChung/Flama/actions/runs/39954752393) | 526,5 s | 547 s | PASS |

Parity: `[SELECTION]` (253 file) và các nhóm `loaded`/`started`/`finished` trùng hash ở mọi lượt; `outcome` và danh sách skip của ba lượt pass trùng mốc. Baseline tuần tự local (Windows, cùng commit) trùng tập case; khác biệt chỉ do nền tảng: Linux skip hai test Windows Job Object, Windows skip một test tín hiệu POSIX (test này tạo hai subtest trên Linux, nên 1.620 so với 1.618). Hash nhóm `subtest` khác ở mọi lượt dù cùng 1.620: sáu test đặt tham số subtest bằng `uuid4` hoặc PID sinh lúc chạy (`test_flama_connect`, `test_scalability_qualification`, `test_study_note_batch` ×2, `test_study_note_templates`, `test_study_template_application_sessions`), xác nhận bằng hai lượt local với `PYTHONHASHSEED` khác nhau. Không mất case, nhưng gate subtest theo hash hiện không thể đạt.

Thời gian: bước backend giảm 42–69% (296–548 s so với 944 s), dao động lớn giữa các lượt. Runner không in RAM nên gate tài nguyên chưa có số đo; không có worker bị kill hoặc timeout.

**Kết luận: chưa nghiệm thu, giữ `jobs=1`.** Ba việc cần làm trước lượt đo lại:

1. Runner: `_terminate_process_tree` trên POSIX gửi `killpg(SIGKILL)` rồi trả về ngay, không chờ group hết process sống như nhánh Windows (`ActiveProcesses == 0`). Lúc runner tải nặng, con cháu còn sống vài ms sau khi bin kết thúc; seed 1 bắt đúng khoảng này (1/4 lượt song song).
2. Thứ tự test: `tests.test_flama_connect` fail khi chạy riêng (`no such table: template_sync_jobs`, ví dụ `test_clone_checks_batch_pinned_release_and_overlay_without_source_live`). `create_connect_app()` không import `models.template_sync_job` (chỉ `create_app()` import ở `app/__init__.py:138`), nên `db.create_all()` thiếu bảng. Trong suite tuần tự file này pass nhờ module chạy trước đã gọi `create_app()`; một cách chia bin khác đã làm lộ lỗi ở lượt local `jobs=2`.
3. Manifest: so `subtest` theo `parent_id`, số lượng và outcome thay vì theo ID đầy đủ, hoặc đổi sáu test sang nhãn subtest ổn định. Không được bỏ nhóm này khỏi gate.

Sau ba sửa này, lặp lại 12.3 (một mốc, ba seed) và thêm đo RAM đỉnh của runner trong bước backend.

### 12.6 Sửa ba blocker PR B và kiểm chứng local (2026-10-23, Codex)

Bản sửa được rà soát để commit local theo yêu cầu owner; chưa push. Giữ nguyên bằng chứng hosted ở 12.5 và mặc định CI `jobs=1`.

- **Cleanup POSIX:** sau `killpg(SIGKILL)` và reap root, chờ process group không còn process sống trong `BACKEND_CLEANUP_TIMEOUT`. Linux đọc `/proc/*/stat`, bỏ qua zombie/dead (`Z`/`X`) vì runner không thể reap orphan do PID 1 sở hữu; group còn sống quá hạn làm bin fail. Không báo bin hoàn tất hoặc xoá media trước khi chờ xong. Có test root đã thoát nhưng con còn sống, group quá hạn, zombie/process khác group/process biến mất, và nhiều worker thật cùng để lại con.
- **Connect độc lập:** `_register_models()` đăng ký `TemplateSyncJob`. Đã tái hiện lỗi `no such table: template_sync_jobs` bằng cách chạy riêng `tests/test_flama_connect.py` trước sửa; sau sửa 35 cases pass trong worker riêng. Test mới import entry point `connect_wsgi.py` trong interpreter mới, chặn main factory và `db.create_all()`, kiểm tra metadata/healthz để không bị thứ tự import trong suite che lỗi. Kiểm chứng riêng trên MySQL local: cold `connect_wsgi.py`, `SELECT 1`, `SELECT id FROM template_sync_jobs LIMIT 0`, `/healthz` đều pass, không sửa schema/data.
- **Manifest:** đổi đúng sáu test ở 12.5 sang nhãn subtest cố định, giữ nguyên UUID/PID và payload trong dữ liệu test. Không đổi schema, comparator hoặc giảm độ chặt của hash; vẫn so đầy đủ ID, parent, số lần, outcome và skip reason.

Nhóm kiểm chứng gồm 10 file: `test_parallel_backend_runner`, `test_unittest_manifest`, `test_modular_test_runner`, `test_ci_workflow`, `test_test_mapping_coverage`, `test_flama_connect`, `test_scalability_qualification`, `test_study_note_batch`, `test_study_note_templates`, `test_study_template_application_sessions` (đều dưới `tests/`). Chạy bằng `scripts/run_tests.py --file ... --backend-only --bin-timeout 180 --manifest ...`, trung hoà bảy study rollout flags theo local-dev skill và dùng `PYTHONHASHSEED` khác nhau (`100`..`103`).

| Lượt local Windows | Backend wall | Kết quả |
| --- | ---: | --- |
| `jobs=1` | 64,19 s | 267 cases, 1 POSIX skip, 144 subtests |
| `jobs=2`, seed 1 | 40,25 s | PASS; comparator `RESULT: identical` |
| `jobs=2`, seed 2 | 42,50 s | PASS; comparator `RESULT: identical` |
| `jobs=2`, seed 3 | 39,06 s | PASS; comparator `RESULT: identical` |

Cả bốn manifest có SHA-256 `7099f12cbf1c3be999fce1a90f90d87f739e65b912110118c19794f32c562e50`; hash từng nhóm, gồm `subtest`, đều trùng. File bằng chứng local (không đưa vào commit): `.tmp/prb-fixes/{sequential,seed1,seed2,seed3}.json`. Lượt focused đầu tiên cũng pass 161 cases, 1 skip; `git diff --check` pass.

Rà soát trước commit: dựng detached worktree từ HEAD, áp dụng đúng patch staged (không có mapping watcher/POC hoặc file untracked của phiên khác), chạy lại nhóm 267 cases với `jobs=2`, seed 3, `PYTHONHASHSEED=104` và env kiểu CI không dùng `.env` local: PASS, 1 skip, 52,44 s. Manifest `.tmp/prb-fixes/commit-candidate.json` có cùng SHA-256 ở trên; comparator trả `RESULT: identical`.

**Giới hạn nghiệm thu:** đây là nhóm liên quan, chưa phải full inventory 2.740 cases. Host Windows không có Linux/WSL nên nhánh Linux được kiểm tra bằng test deterministic với fake `/proc`; lifecycle thực trên Linux, full-suite hosted parity và peak RAM vẫn chờ lượt benchmark theo 12.3. Không dispatch Actions thêm và chưa bật `jobs=2` mặc định.
