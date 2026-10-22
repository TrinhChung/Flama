# Review kế hoạch nâng cấp CI/CD test và kế hoạch triển khai

- Ngày: 2026-10-23 (Asia/Tokyo)
- Phạm vi review:
  - Gemini, báo cáo 2026-10-13: `docs/plans/TEST_ARCHITECTURE_AND_CICD_OPTIMIZATION_REPORT.md` (Tiered CI, D2, nightly, gate MySQL).
  - Gemini Teamwork 2026-10-22: POC `FastTestHarness` (`tests/test_harness_poc.py`) và bản nháp RFC.
  - Codex P0 (chưa commit, đang nằm trên nhánh `fix/deploy-disconnect-cloudflare` của PR TrinhChung/Flama#239): `.github/workflows/ci.yml`, `tests/test_ci_workflow.py`, `tests/test_spa_artifact_contract.py`, `scripts/run_tests.py`, `docs/architecture/TEST_ARCHITECTURE_RFC.md`, các file POC.
- Trạng thái (2026-10-23): mục 6.0 và 6.1 đã làm và commit ở local, chưa push, chưa chạy trên GitHub Actions. Các mục còn lại vẫn là kế hoạch.
  - 6.0: POC được park ở nhánh local `experiment/test-harness-poc` (bước 2, lựa chọn (a)). Theo yêu cầu của người dùng, P0 được commit thẳng lên nhánh `fix/deploy-disconnect-cloudflare` thay cho bước 3–4.
  - 6.1: đã xoá job `spa-contract`. Bằng chứng local nằm trong `docs/architecture/TEST_ARCHITECTURE_RFC.md`; phần nghiệm thu trên GitHub (bước 6) vẫn chờ.

## 1. Kết luận ngắn

1. Không có khủng hoảng quota. Số đo thực tế trong 30 ngày là khoảng **1.045 phút tính phí**, không phải 2.940 phút như báo cáo Gemini giả định. Trần của gói Free cho repo private là 2.000 phút.
2. Hai job `backend` và `mysql-contract` chiếm khoảng **72%** số phút. Đòn bẩy chính là làm hai job này nhanh hơn, không phải chuyển sang chạy chọn lọc trên master.
3. Kiến trúc phân tầng (ứng viên B: chạy chọn lọc trên master cộng nightly) **không đáng làm lúc này**. 20/22 lượt merge gần đây đều chạm backend, nên chạy chọn lọc tiết kiệm rất ít. Trong khi đó nightly ngày thường sẽ *tăng thêm* khoảng 660–800 phút mỗi tháng.
4. Phần CI của Codex P0 đúng và đã pass test. Nhưng nếu giữ job shim `spa-contract` thì gần như **không tiết kiệm được phút tính phí**, vì job nào cũng bị làm tròn lên 1 phút. Repo không có branch protection, nên nên xoá hẳn job này.
5. Phần harness của Codex P0 **không còn trong checkout**. Phiên Antigravity/Gemini `d8ea6482` đã ghi đè lúc 00:32–00:34 bằng bản nháp cũ, và phiên này vẫn đang chạy. Vì vậy RFC hiện mô tả một bản code không còn tồn tại. Đề xuất đóng băng (park) POC và để nó ngoài mọi PR CI.

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

Mục tiêu: nhóm 420 phút/tháng. Kỳ vọng giảm 30–45% thời gian job `backend` *nếu* runner có 2 vCPU. Con số này cần đo thật.

1. Đo trước: thêm `nproc` và `free -m` vào job `backend` (hoặc chạy một lần qua `workflow_dispatch`). Ở local, chạy `--all --backend-only` với jobs=1 để lấy baseline.
2. `scripts/run_tests.py`:
   - Thêm `--jobs N|auto` (mặc định `1`, khi đó lệnh giữ nguyên như hiện nay).
   - Chia file theo LPT, dùng kích thước file làm trọng số; có thể thêm `--partition-seed` để xáo trộn.
   - Mỗi nhóm chạy một tiến trình `python -m unittest` riêng, với `TemporaryDirectory` media riêng và `build_backend_test_environment` riêng.
   - Đệm output và in theo từng nhóm; exit code bằng OR của các nhóm; giữ `-f` trong từng nhóm.
3. Test mới trong `tests/test_modular_test_runner.py`:
   - Phân hoạch xác định và đầy đủ (mỗi file đúng một lần).
   - Gộp exit code đúng.
   - `--jobs 1` sinh đúng lệnh hiện tại.
4. Tìm các file có thể đụng nhau: grep đường dẫn cố định (`output/`, `instance/`, sqlite file), port cố định, tên temp cố định. Sửa trong test, không né.
5. Kiểm chứng: chạy `--all --backend-only --jobs auto` 3 lần với 3 seed khác nhau. Tổng số "Ran N" phải bằng baseline và không có lỗi nào.
6. Bật trong CI: job `backend` dùng `--jobs auto`. Nghiệm thu: thời gian job `backend` giảm ≥30% trên 3 run liên tiếp và số test bằng nhau.

### 6.3 PR C: rà soát và chia tầng `mysql-contract` (≈2–3 ngày, dùng `$mysql` + `$flama-database-architecture`)

Mục tiêu: nhóm 337 phút/tháng, đồng thời là critical path 14 phút.

1. Không đổi hành vi: tách các step nhiều probe (field identity: 5 probe; historical/deck count: 2 probe) thành mỗi step một probe để lấy thời gian của từng probe. Cập nhật `test_ci_workflow.py` nếu nó kiểm tra tên step.
2. Lập bảng rà soát và đưa vào RFC. Mỗi probe có các cột:
   - Probe và tham số
   - Migration hoặc phase mà nó bảo vệ
   - Thời gian chạy
   - Lần cuối code được bảo vệ thay đổi
   - Đây là qualification của một cutover đã hoàn tất, hay contract cần chạy với mọi thay đổi
   - Chủ sở hữu ký duyệt
3. Các phương án, mỗi phương án cần dữ liệu từ bước 2:
   - (a) Gate riêng các probe qualification của cutover đã xong (ví dụ field identity cutover, xác nhận production ngày 2026-10-11) theo pattern nguồn của chính chúng cộng `migrations/**`.
   - (b) Chạy song song các probe độc lập trên các database riêng (`ci_probe_<n>`) trong cùng service MySQL; đo mức tranh chấp CPU trên 2 vCPU.
   - (c) Chỉ giảm tham số tải khi tài liệu của probe cho phép.
4. Quy tắc cứng:
   - `bootstrap_historical_schema.py` + `flask db upgrade` luôn chạy khi `mysql-contract` chạy.
   - Thay đổi `migrations/**` hoặc `models/**` luôn chạy đủ tầng MySQL.
   - Không bỏ probe nào chỉ dựa trên tên file.

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

## 8. Quyền sở hữu và thứ tự

- Thứ tự: 6.0 → PR A → PR B, có thể chạy song song với bước 1–2 của PR C. Phần (a)/(b) của PR C chỉ làm sau khi bảng rà soát được duyệt.
- Mỗi file chỉ có một agent ghi. PR A sở hữu `ci.yml` và `tests/test_ci_workflow.py`, nên PR C không được sửa `ci.yml` cho tới khi PR A merge. PR B sở hữu `scripts/run_tests.py` và `tests/test_modular_test_runner.py`.
- Các file POC (`scripts/poc_*.py`, `scripts/test_repeatability_benchmark.py`, `scripts/stress_test_poc_adversarial.py`, `tests/test_harness_poc.py`, `tests/test_adversarial_poc_harness.py`, `tests/test_poc_test_runner.py`) bị đóng băng cho tới khi có quyết định ở 6.0.

## 9. Quyết định cần người dùng chốt trước khi bắt đầu

1. Dừng phiên Gemini `d8ea6482` và chọn số phận POC (park / khôi phục bản Codex / xoá).
2. Đồng ý xoá job `spa-contract`.
3. Đồng ý park ứng viên B (chạy chọn lọc trên master + nightly).
4. Agent nào thực hiện PR A/B/C.
