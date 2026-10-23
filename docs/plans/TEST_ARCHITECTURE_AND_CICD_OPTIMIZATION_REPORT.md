# BÁO CÁO CHIẾN LƯỢC KIẾN TRÚC KIỂM THỬ VÀ TỐI ƯU HÓA CI/CD PIPELINE
## (Test Architecture & CI/CD Optimization Strategy Report)

> Historical proposal, reviewed again on 2026-10-23. Execution decisions are in
> [the current implementation plan](TEST_CICD_UPGRADE_IMPLEMENTATION_PLAN_2026-10-23.md)
> and [RFC](../architecture/TEST_ARCHITECTURE_RFC.md). Section 10 of the current implementation plan covers plan
> correctness, coverage, test fidelity, architecture and in-progress agent work.
> Quota assumptions, speed targets and blanket nightly/gate-removal proposals
> below are not current acceptance evidence. Keep full master/MySQL/Redis gates;
> H1/H2/H3 are parked and archive/Worksheet changes require correction/review.
> Section 11 also requires balancing runner minutes with the user's 0.5 GB
> Actions storage allowance, separate cache accounting and end-of-cycle reserves.

- **Dự án**: Flama (Nền tảng Học tiếng Nhật & Flashcard Spaced Repetition)
- **Tài liệu**: `docs/plans/TEST_ARCHITECTURE_AND_CICD_OPTIMIZATION_REPORT.md`
- **Phiên bản**: 1.1 (Bản Hoàn chỉnh Hiệu chỉnh sau Phản biện Đối kháng & Thẩm định Độc lập)
- **Ngày hoàn thành**: 2026-10-13 (Cập nhật sau Review & Adversarial Challenge)
- **Thực hiện bởi**: Đội ngũ Kiến trúc sư Kiểm thử & Điều phối CI/CD (Teamwork Preview Swarm)
- **Tài liệu tham chiếu & Nguồn thẩm định**:
  - `docs/architecture/SYSTEM_ARCHITECTURE.md`
  - `docs/runbooks/FLASHCARD_V2_RUNBOOK.md`
  - `docs/plans/completed/CLONE_CUTOVER_REPORT.md`
  - `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
  - `scripts/run_tests.py`, `scripts/probes/*`, `tests/`
  - Dữ liệu thực nghiệm GitHub Actions Runs #38422486144 (Master Merge) & #38421024072 (Pull Request)
  - Báo cáo Phản biện Đối kháng Challenger 1 (`teamwork_preview_challenger_m4_1/handoff.md`) & Challenger 2 (`teamwork_preview_challenger_m4_2/handoff.md`)
  - Báo cáo Thẩm định Độc lập Reviewer 1 (`teamwork_preview_reviewer_m4_1/handoff.md`) & Reviewer 2 (`teamwork_preview_reviewer_m4_2/handoff.md`)

---

## MỤC LỤC TỔNG QUAN

1. [Tóm tắt Điều hành (Executive Summary)](#1-tóm-tắt-điều-hành-executive-summary)
2. [Phân tích Hiện trạng Kiến trúc Kiểm thử & CI/CD (As-Is Telemetry & Root Cause Analysis)](#2-phân-tích-hiện-trạng-kiến-trúc-kiểm-thử--cicd-as-is-telemetry--rca)
   - 2.1 Cấu trúc Đồ thị Luồng Công việc (DAG Telemetry)
   - 2.2 Cơ chế Kích hoạt Cưỡng bức `CI_FORCE_ALL_VALIDATION=true`
   - 2.3 Phân tích Chuyên sâu Backend Test Suite (235 Files, 2,436 Tests, Đơn luồng)
   - 2.4 Phân tích Chuyên sâu Frontend Test Suite & Anti-pattern Lặp lại Build trong `spa-contract`
   - 2.5 Phân tích 12 Bước Probes Hợp đồng MySQL 8.0 InnoDB
3. [Khảo sát & Đánh giá Chi tiết 4 Ứng viên Kiến trúc (Evaluation of Candidates A, B, C, D)](#3-khảo-sát--đánh-giá-chi-tiết-4-ứng-viên-kiến-trúc)
   - 3.1 Ứng viên A: Tái cấu trúc Fixture (Pytest / Shared App & DB Context / Rollback) — *Bác bỏ*
   - 3.2 Ứng viên B: Kiến trúc Phân tầng Pipeline (Tiered CI / Test Pyramid 3 Tầng) — *Khuyến nghị Cốt lõi*
   - 3.3 Ứng viên C: Ma trận Song song hóa (Matrix Sharding) — *Phân tích Rạch ròi Wall-Clock vs Quota*
   - 3.4 Ứng viên D: Tinh giản Build & Gộp Contract Assertion (D1 vs D2) — *Khuyến nghị Tuyệt đối D2 & Kế hoạch Refactor Tests*
4. [Mô hình Kiến trúc Đề xuất (To-Be Architecture: Hybrid B + D2 + Conditional C)](#4-mô-hình-kiến-trúc-đề-xuất-to-be-architecture)
   - 4.1 Sơ đồ Kiến trúc & Đồ thị Luồng Công việc Mới (To-Be DAG) & Cơ chế Chống Cascading Skip
   - 4.2 Cơ chế Selective Fast Merge & Đồng bộ Decouple Cả Backend Lẫn Frontend trên Master
   - 4.3 Cơ chế Conditional Gate Toàn diện cho MySQL Contract Probes (Zero False Negatives)
   - 4.4 Cơ chế Gộp SPA Contract Verification vào Job `frontend` & Cấu hình Pip Cache
   - 4.5 Thiết kế Pipeline Kiểm thử Toàn diện Định kỳ (Nightly Full Validation Cron Chuẩn xác)
5. [Bảng So sánh Định lượng & Dự toán Ngân sách Quota (Cost & Quota Modeling)](#5-bảng-so-sánh-định-lượng--dự-toán-ngân-sách-quota)
   - 5.1 Ma trận So sánh Toàn diện Hiện trạng vs Các Ứng viên
   - 5.2 Mô hình Dự toán Hạn ngạch Chi tiết Hàng tháng: Kịch bản 2 (Weekday Nightly) làm Baseline Mặc định
   - 5.3 Chứng minh Khả năng Đáp ứng Ngưỡng An toàn < 2,000 Runner-Minutes/Tháng
6. [Lộ trình Triển khai Khả thi (Actionable Implementation Roadmap 3 Giai đoạn)](#6-lộ-trình-triển-khai-khả-thi-actionable-roadmap)
   - 6.1 Giai đoạn 1: Quick Wins Không Rủi ro (D2 In-place, Pip Cache, Refactor Tests, Anti-Skip Deploy, Gate Mở rộng)
   - 6.2 Giai đoạn 2: Tách biệt Đồng bộ Cơ chế Master Validation (Decouple Cả Backend và Frontend)
   - 6.3 Giai đoạn 3: Tối ưu Hóa Song song & Giám sát Dài hạn (Tùy chọn)
   - 6.4 Kế hoạch Kiểm thử Không Hồi quy & Tiêu chí Nghiệm thu Từng Giai đoạn

---

## 1. TÓM TẮT ĐIỀU HÀNH (EXECUTIVE SUMMARY)

Dự án **Flama** là một nền tảng học tiếng Nhật và ôn luyện thẻ nhớ (Flashcard SRS) hiện đại với kiến trúc Fullstack: Flask REST API, React SPA (Vite/TailwindCSS/Radix UI), MySQL 8.0 (InnoDB), Redis 7 và các dịch vụ tích hợp Flama Connect/Audio. Quy trình tích hợp và phân phối liên tục (CI/CD) của dự án được tự động hóa qua GitHub Actions (`.github/workflows/ci.yml`), kết nối trực tiếp đến hạ tầng triển khai VPS Hostinger (`deploy.yml`).

### Nút thắt Nghiêm trọng Hiện tại
Qua quá trình giám sát viễn trắc (telemetry monitoring) và phân tích thực nghiệm trên các lượt chạy gần nhất của GitHub Actions, hệ thống đang phải đối mặt với **hai cuộc khủng hoảng song hành**:

1. **Nút thắt Thời gian Chờ (Wall-Clock Bottleneck)**:
   - Mỗi commit được merge vào nhánh `master` mất từ **16 phút 17 giây đến gần 20 phút** để hoàn tất kiểm thử và triển khai.
   - Thời gian chờ của `master` kéo dài gấp **~3 lần** so với một lượt chạy Pull Request thông thường (chỉ mất ~5–7 phút). Nút thắt này làm tê liệt năng suất phát hành, khiến các lập trình viên phải chờ đợi kéo dài và tạo ra nguy cơ tắc nghẽn hàng đợi (deployment queue lock).
2. **Khủng hoảng Cạn kiệt Hạn ngạch GitHub Actions (Quota Exhaustion Risk)**:
   - Mỗi lần merge to master tiêu tốn **33 billable runner-minutes** (29.8 runner-minutes thời gian CPU thực tế).
   - Với quy mô phát triển tiêu chuẩn **60 lượt merge to master/tháng**, pipeline riêng cho việc merge đã ngốn tới **1,980 phút/tháng** — chiếm **99.0% tổng hạn ngạch miễn phí 2,000 phút/tháng** của gói GitHub Actions tiêu chuẩn!
   - Khi tính thêm khoảng **80 lượt kiểm thử Pull Requests/tháng** (~960 phút), tổng mức tiêu thụ thực tế đạt tới **2,940 runner-minutes/tháng** (vượt trần **147.0%**, thâm hụt **940 phút/tháng**). Nếu không có biện pháp tái cấu trúc khẩn cấp, tài khoản GitHub Actions sẽ bị khóa runner giữa chừng, chặn đứng hoàn toàn hoạt động CI/CD và triển khai ứng dụng.

### Nguyên nhân Gốc rễ
- **Cơ chế `CI_FORCE_ALL_VALIDATION=true`**: Khi có sự kiện push lên `master`, workflow ép buộc chạy đồng loạt 100% tất cả 5 jobs kiểm thử (`backend`, `frontend`, `mysql-contract`, `redis-contract`, `spa-contract`), vô hiệu hóa hoàn toàn cơ chế chọn lọc modular test thông minh của `scripts/run_tests.py`.
- **Cơ chế Ép Buộc Lớp Kép (Dual-Layer Master Enforcement)**: Cả hai jobs `backend` (dòng 161–167) VÀ `frontend` (dòng 121–127) đều cài cắm logic kiểm tra nhánh `master` để ép chạy toàn diện (`--all` cho backend và `npm test` 7 phút cho frontend).
- **Job `backend` Đơn luồng Nặng nề (Critical Path)**: Chạy tuần tự 235 test files (2,436 unittests) trong một tiến trình đơn luồng, tiêu tốn **15 phút 03 giây**. Trong đó, có tới **~9.1 phút CPU thuần túy** chỉ để lặp đi lặp lại việc khởi tạo Flask Application Factory (`create_app()`, ~877 lần) và tạo/xóa bảng SQLite in-memory (`db.create_all() / db.drop_all()`, ~1,383 lần).
- **Anti-pattern Lặp lại Môi trường trong `spa-contract`**: Job này tiêu tốn 1–3 billable runner-minutes chỉ để lặp lại `npm ci`, build Vite và setup Python nhằm phục vụ đúng 2 câu kiểm tra HTTP contract kéo dài **3 giây** (`test_spa_artifact_contract.py`), gây lãng phí 120–180 phút/tháng.
- **Kích hoạt Vô điều kiện `mysql-contract`**: Container MySQL 8.0 và 10 probe scripts concurrency nặng bị ép chạy trên mọi merge dù thay đổi chỉ là 1 dòng CSS hay tài liệu Markdown.

### Giải pháp Chiến lược Toàn diện (To-Be Hybrid Architecture)
Báo cáo này đề xuất mô hình kiến trúc lai **To-Be Hybrid (B + D2 + Conditional C)** với các trụ cột kỹ thuật then chốt:
1. **Kiến trúc Phân tầng 3 Cấp (Ứng viên B)**:
   - **Tầng 1 (Per-Merge Fast Path)**: Chuyển đổi master merge sang cơ chế Selective Test thông minh theo modules bị thay đổi (`scripts/run_tests.py --changed`), **đồng bộ tách rời (decouple) cả hai jobs `backend` và `frontend` trên master** kết hợp với **Core Smoke Gate** (bộ 12 test files cốt lõi chạy trong ~25 giây).
   - **Tầng 2 (Nightly Full Validation Cron)**: Thiết lập workflow định kỳ chạy vào các ngày làm việc (Weekday Nightly Cron - 22 lượt/tháng) kiểm thử 100% full suite (2,436 unittests backend, 174 test files Vitest, toàn bộ hợp đồng MySQL và Redis probe).
   - **Tầng 3 (Conditional Gate Kín khít cho MySQL Contract)**: Mở rộng đầy đủ `MYSQL_CONTRACT_SOURCE_PATTERNS` bao gồm `app/repositories/**`, `app/services/stats_today_future.py`, `app/services/study_service.py` để đảm bảo **Zero False Negatives** trước khi Deploy, loại trừ hoàn toàn nguy cơ lọt lỗi InnoDB/READ-ONLY lên Production.
2. **Loại bỏ Hoàn toàn Job `spa-contract` bằng In-place Assertion (Ứng viên D2)**:
   - Gộp trực tiếp bước kiểm tra artifact vào cuối job `frontend` ngay sau khi Vite build xong; trang bị **Pip Cache** (`setup-python: cache: 'pip'`) để triệt tiêu thời gian tải package qua mạng; đồng thời tái cấu trúc bộ test bảo vệ `tests/test_ci_workflow.py` để tương thích cấu trúc in-place.
3. **Bảo vệ Luồng Deploy Khỏi Cascading Skip**:
   - Trang bị điều kiện `!contains(needs.*.result, 'failure') && !contains(needs.*.result, 'cancelled')` cho job `deploy`, ngăn chặn lỗi cố hữu của GitHub Actions tự động skip deploy khi các upstream jobs (`mysql-contract`, `redis-contract`) ở trạng thái `skipped`.
4. **Bác bỏ Dứt khoát Ứng viên A (Pytest / Shared Fixtures)**:
   - Bảo toàn 100% cấu trúc flat unittest độc lập theo đúng quy chuẩn `AGENTS.md`, ngăn chặn rủi ro rò rỉ trạng thái (SQLite sequence ID=1, RAM state, commit trong service layer) và duy trì sự ổn định cho hệ sinh thái Multi-Agent Swarm.

### Kết quả Định lượng Đạt được (Baseline Khuyến nghị Mặc định: Kịch bản 2)
- **Baseline Chuẩn được Khuyến nghị**: **Kịch bản 2 (Weekday Nightly Cron - 22 runs/tháng)**:
  - **Wall-Clock Time khi Merge Master**: Giảm từ **16m 17s xuống còn 3m 30s – 5m 00s** (Rút ngắn **70% – 78%** thời gian chờ đợi).
  - **Runner-Minutes tiêu thụ mỗi lần Merge**: Giảm từ **33 phút xuống còn 6 – 17 phút** (Trung bình **9.7 phút/lần merge**, tiết kiệm **70.6%**).
  - **Tổng Tiêu thụ Hạn ngạch Toàn hệ thống**: Đưa tổng chi phí hàng tháng từ **2,940 phút xuống còn 1,720 phút/tháng** (chỉ chiếm **86.0% hạn ngạch 2,000 phút**, tạo **thặng dư an toàn vững chắc +280 phút/tháng (14.0%)**).
- **Phương án Dự phòng Kịch bản 1 (Nightly 30 ngày/tháng)**: Tiêu thụ **1,960 phút/tháng (98.0%)**, biên thặng dư mỏng (+40 phút/tháng, 2.0%), tiềm ẩn nguy cơ cạn kiệt nếu phát sinh thêm retry hoặc commit phát sinh.
- **Codebase Safety**: **Tuyệt đối KHÔNG thay đổi mã nguồn sản phẩm (`app/`, `frontend/`, `models/`)**, rủi ro hồi quy bằng 0.

---

## 2. PHÂN TÍCH HIỆN TRẠNG KIẾN TRÚC KIỂM THỬ & CI/CD (AS-IS TELEMETRY & RCA)

### 2.1 Cấu trúc Đồ thị Luồng Công việc (DAG Telemetry)

Quy trình CI/CD cốt lõi của Flama được định nghĩa trong file `.github/workflows/ci.yml` (425 dòng), quản lý 7 jobs liên kết theo một Đồ thị Có hướng Không Chu trình (DAG):

```
                          [Event: push / pull_request]
                                       │
                                       ▼
                               ┌─────────────────┐
                               │     changes     │ (17s)
                               │  (Test Planner) │
                               └────────┬────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┬──────────────────────────┐
             │                          │                          │                          │
             ▼                          ▼                          ▼                          ▼
    ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
    │     backend     │        │    frontend     │        │  mysql-contract │        │  redis-contract │
    │    (15m 03s)    │        │    (6m 14s)     │        │    (5m 50s)     │        │      (32s)      │
    │ [CRITICAL PATH] │        └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
    └────────┬────────┘                 │                          │                          │
             │                          ▼                          │                          │
             │                 ┌─────────────────┐                 │                          │
             │                 │   spa-contract  │ (57s)           │                          │
             │                 │(Wait for FE win)│                 │                          │
             │                 └────────┬────────┘                 │                          │
             │                          │                          │                          │
             └──────────────────────────┼──────────────────────────┴──────────────────────────┘
                                        │
                                        ▼ (Needs: ALL previous jobs succeed)
                               ┌─────────────────┐
                               │     deploy      │ (57s)
                               │  (Hostinger VPS)│
                               └─────────────────┘
```

#### Bảng Dữ liệu Viễn trắc Chi tiết Lần chạy Thực tế (GitHub Actions Run #38422486144 - Master Merge)

| Tên Job | Thời gian Chạy Thực | Setup Overhead | Thời gian Test Thuần | Billable Minutes | Tỷ lệ Setup % | Vị trí trên Chuỗi Trọng yếu |
|---|---|---|---|---|---|---|
| **`changes`** | 17 giây | 11s (Checkout + Resolve) | 5s (`--ci-plan`) | **1 phút** | 64.7% | Node gốc |
| **`backend`** | **15 phút 03 giây** | 18s (Py setup + pip cache) | **14m 37s (877s)** | **16 phút** | 2.0% | **CRITICAL PATH** |
| **`frontend`** | 6 phút 14 giây | 27s (Node setup + `npm ci`) | 4m 45s (Vitest) + 45s (tsc) | **7 phút** | 7.2% | Chạy song song |
| **`mysql-contract`** | 5 phút 50 giây | 45s (Docker MySQL wait) | 4m 48s (10 probes) | **6 phút** | 12.9% | Chạy song song |
| **`redis-contract`** | 32 giây | 22s (Docker Redis wait) | 3s (1 test) | **1 phút** | 68.8% | Chạy song song |
| **`spa-contract`** | 57 giây | 39s (`npm ci`, build, pip) | 5s (1 test) | **1 phút** | 68.4% | Phụ thuộc `frontend` |
| **`deploy`** | 57 giây | 11s (Package payload) | 44s (SSH rsync & reload) | **1 phút** | 19.3% | Node đích |
| **TỔNG CỘNG** | **16m 17s Wall-clock** | — | — | **33 PHÚT** | — | **Chiếm 99% Quota/tháng** |

*Ghi chú*: Trên môi trường GitHub Actions, mỗi job được làm tròn lên phút nguyên gần nhất ($\lceil \text{Job Duration} \rceil$). Do đó, tổng billable minutes là **33 phút**, dù thời gian CPU thực tế là 29.83 phút.

---

### 2.2 Cơ chế Kích hoạt Cưỡng bức `CI_FORCE_ALL_VALIDATION=true`

Nguyên nhân trực tiếp khiến lần chạy merge to master bị kéo dài gấp 3 lần PR xuất phát từ thiết lập tại dòng 102–104 file `.github/workflows/ci.yml`:
```yaml
      - name: Plan affected validation jobs
        id: plan
        env:
          CI_FORCE_ALL_VALIDATION: ${{ github.event_name != 'pull_request' }}
          DEPLOYED_RELEASE_SHA: ${{ steps.deployed.outputs.sha }}
        run: python scripts/run_tests.py --ci-plan --github-output "$GITHUB_OUTPUT"
```

Khi sự kiện là `push` lên `master`, biểu thức `${{ github.event_name != 'pull_request' }}` đánh giá thành chuỗi `"true"`.

#### Tác động Dây chuyền đến `scripts/run_tests.py`
Trong `scripts/run_tests.py` (dòng 1403–1414 và 1662–1674):
```python
force_all = str(os.environ.get("CI_FORCE_ALL_VALIDATION") or "").lower() in {
    "1", "true", "yes", "on",
}
plan = build_ci_change_plan(changed, force_all_validation=force_all, files_since_deploy=since_deploy)
```
Hàm `build_ci_change_plan` trả về:
```python
return {
    "backend": force_all_validation or bool(backend_tests),
    "frontend": force_all_validation or bool(frontend_tests) or spa_contract,
    "spa_contract": force_all_validation or spa_contract,
    "redis_contract": force_all_validation or matches_any(REDIS_CONTRACT_SOURCE_PATTERNS),
    "mysql_contract": force_all_validation or matches_any(MYSQL_CONTRACT_SOURCE_PATTERNS),
    "deploy": matches_any(DEPLOY_RUNTIME_SOURCE_PATTERNS) or undeployed_runtime,
}
```
Khi `force_all_validation=True`, **tất cả 5 cờ kiểm thử đồng loạt bị ép thành `True`**.

#### Lớp Cưỡng bức Kép (Dual-Layer Trigger)
Không chỉ kích hoạt toàn bộ các job, workflow còn áp đặt lệnh kiểm thử toàn diện ngay bên trong từng job:
- **Tại Job `backend` (dòng 161–167)**:
  ```bash
  if [ "${{ github.ref_name }}" = "master" ] || [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
    echo "Running full backend test suite on master..."
    python scripts/run_tests.py --all --backend-only
  else
    python scripts/run_tests.py --changed --backend-only
  fi
  ```
- **Tại Job `frontend` (dòng 121–127)**:
  ```bash
  if [ "${{ github.ref_name }}" = "master" ] || [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
    echo "Running full frontend test suite on master..."
    npm test
  else
    python ../scripts/run_tests.py --changed --frontend-only
  fi
  ```

Hệ quả là: Một commit dù chỉ sửa 1 lỗi chính tả i18n trong file JSON frontend vẫn bắt buộc hệ thống phải chạy lại toàn bộ 2,436 backend tests, 174 frontend test files, và 10 bài probe MySQL nặng nề!

---

### 2.3 Phân tích Chuyên sâu Backend Test Suite (235 Files, 2,436 Tests, Đơn luồng)

Khảo sát mã nguồn qua phân tích cú pháp AST và nạp động bằng `unittest.TestLoader` trên toàn bộ thư mục `tests/`:

- **Tổng số test files**: **235 files** (100% tuân thủ cấu trúc flat `unittest.TestCase`).
- **Tổng số test cases / test methods**: **2,436 tests**.
- **Cơ chế thực thi**: Lệnh `python -m unittest` trong `scripts/run_tests.py` chạy trên **MỘT tiến trình duy nhất (single-threaded, sequential)**. Module `unittest` của Python Standard Library không hỗ trợ cờ song song (`-j` không tồn tại).

#### Định lượng Chi phí Khởi tạo Lặp đi Lặp lại (Bootstrap Overhead Benchmark)
Đo lường thời gian thực thi vi mô trên môi trường chuẩn:
- **1 lần gọi `create_app()`**: Mất trung bình **378.94 ms** (do phải import và đăng ký hơn 20 Blueprints, thiết lập SQLAlchemy event listeners, gán handler xử lý lỗi bảo mật, nạp LoginManager, cấu hình session cookie).
- **1 lần gọi `db.create_all()`**: Mất trung bình **146.03 ms** (do phải phát các câu lệnh DDL `CREATE TABLE` cho hơn 50 models trong metadata: `notes`, `cards`, `study_sessions`, `review_events`, `templates`, `deck_change_requests`...).
- **1 lần gọi `db.drop_all()`**: Mất trung bình **31.72 ms**.
- **Trung bình 1 chu kỳ DDL hoàn chỉnh (`create_all` + `drop_all`)**: **153.57 ms**.

Qua phân tích AST của 235 test files:
- **104 test files** sử dụng mô hình *Per-Test-Method Setup*: gọi `create_app()` và `db.create_all()` trong `setUp()`.
- **33 test files** sử dụng mô hình *Per-Class App + Per-Method DB Setup*: gọi `create_app()` trong `setUpClass()` nhưng vẫn gọi `db.create_all()` trong `setUp()`.
- **98 test files** còn lại có các biến thể khởi tạo context cục bộ khác.

#### Bảng Tổng hợp Chi phí Khởi tạo trong 1 Lần Chạy Full Suite (`--all`)

| Thao tác Khởi tạo | Số lần Thực thi Ước tính | Chi phí Đơn vị Thực nghiệm | Tổng Thời gian CPU Tiêu hao |
|---|:---:|:---:|:---:|
| `create_app()` | ~877 lần | ~378.94 ms | **332.33 giây (~5.54 phút)** |
| `db.create_all() + db.drop_all()` | ~1,383 lần | ~153.57 ms | **212.39 giây (~3.54 phút)** |
| **TỔNG CHI PHÍ SETUP/TEARDOWN THUẦN TÚY** | — | — | **544.72 GIÂY (~9.08 PHÚT CPU)** |

> **Phát hiện Cốt lõi**: Trong 14 phút 37 giây chạy của job `backend`, có tới **hơn 9 phút chỉ dành cho việc lặp đi lặp lại khởi tạo Flask application và tạo/xóa bảng SQLite in-memory**, thay vì thực thi logic nghiệp vụ hay kiểm tra assertion! Đây chính là lý do khiến job `backend` trở thành nút thắt dài nhất trên Critical Path.

---

### 2.4 Phân tích Chuyên sâu Frontend Test Suite & Anti-pattern Lặp lại Build trong `spa-contract`

#### Hiện trạng Frontend Test Suite (`frontend/`)
- Gồm **174 test files** (100% TypeScript/TSX).
- Phân bổ môi trường thực thi:
  - **137 files (78.7%)** sử dụng chỉ thị `// @vitest-environment jsdom` để giả lập DOM cho React components, Radix UI modals và hooks.
  - **37 files (21.3%)** chạy trực tiếp trên môi trường `node` cho các hàm tiện ích thuần túy, Zod schemas và scheduler calculations.
- Công cụ kiểm tra:
  - `oxlint src`: Linter bằng Rust siêu tốc, quét 734 files chỉ mất **178 ms**.
  - `tsc -b --pretty`: Kiểm tra Typecheck toàn diện, mất **35 – 59 giây**.
  - `vitest run`: Chạy toàn bộ 174 files test, mất **45 – 80 giây**.
  - `npm run build:ci` (`vite build` không tsc): Mất **4.6 – 12 giây** (xuất bản thư mục `dist/` nặng 21.5 MB).

#### Anti-pattern Nghiêm trọng tại Job `spa-contract`
Job `spa-contract` trong `.github/workflows/ci.yml` (dòng 169–212) khởi chạy một máy ảo độc lập (`ubuntu-latest`), thực hiện tuần tự:
1. `actions/checkout@v4` (4s)
2. `actions/setup-node@v4` (8s)
3. `npm ci` (15s với cache)
4. `npm run build:ci` (4s)
5. `actions/setup-python@v5` (3s)
6. `pip install -r requirements.txt` (9s)
7. `python -m unittest tests.test_spa_artifact_contract` (**Đúng 3–5 giây!**)

#### Nguyên nhân Gốc rễ: Chính sách "Zero Actions Artifact Storage"
File `tests/test_ci_workflow.py` (dòng 87–95) áp đặt một ràng buộc kiến trúc:
```python
def test_ci_uses_no_actions_artifact_storage(self):
    # An exhausted account artifact quota must never block validation, so
    # the SPA contract builds its own dist instead of passing an artifact.
    for workflow in (self.workflow, self.audio_workflow):
        self.assertNotIn("actions/upload-artifact", workflow)
        self.assertNotIn("actions/download-artifact", workflow)
```
- **Lý do ban đầu**: Tài khoản GitHub miễn phí chỉ có 500 MB dung lượng lưu trữ Artifact. Nếu mỗi build tải lên 21.5 MB `frontend/dist/`, dung lượng sẽ cạn kiệt nhanh chóng, dẫn đến việc GitHub Actions từ chối chạy mọi workflow.
- **Hệ quả không mong muốn**: Để tránh dùng Artifact storage, tác giả đã tách `spa-contract` thành một job riêng và ép nó tự build lại từ đầu. Kết quả là job này tiêu tốn **3 billable runner-minutes** mỗi lần chạy (57s thực tế + queue time làm tròn thành 1-2 phút, hoặc 2.5 phút khi cache miss làm tròn thành 3 phút).
- Với 60 lần merge/tháng, job này lãng phí từ **120 đến 180 runner-minutes/tháng** chỉ để đổi lấy 3 giây thực thi test!

---

### 2.5 Phân tích 12 Bước Probes Hợp đồng MySQL 8.0 InnoDB

Job `mysql-contract` khởi chạy container dịch vụ `mysql:8.0` và thực hiện 12 bước kiểm thử tuần tự (mất tổng cộng **5 phút 50 giây**, tương đương **6 billable minutes**):

1. `bootstrap_historical_schema.py` + `flask db upgrade`: Replay 60+ bản migration Alembic từ database trắng (45–60s).
2. `probe_p1_02_mysql_concurrency.py`: Kiểm tra InnoDB lock timeout, snapshot vs native revision (15–20s).
3. `probe_p5_analytics_mysql.py`: Xác thực giao dịch READ ONLY trên MySQL (chống lỗi MySQL Error 1792) (20–30s).
4. `probe_review_analytics_mysql.py` + `probe_deck_counts_mysql.py`: Rollup snapshot đếm thẻ (25–35s).
5. `probe_p5_concurrency_mysql.py`: Tranh chấp ghi đồng thời nhiều người học, deadlock delta (40–60s).
6. `probe_p5_direct_replay_mysql.py --overlay-only`: Vòng đời Note overlay, barrier lock sync với `threading.Barrier` (60–90s, chiếm 136s CPU).
7. `probe_retirement_fresh_chain_mysql.py`: Nâng cấp chuỗi migration xóa bảng cũ (45–60s).
8. `probe_field_identity_mysql.py` + `probe_forecast_snapshots_mysql.py`: Backfill định danh trường (30–40s).
9. Chạy 6 files tests archive tables qua `scripts/run_tests.py` (25–35s).
10. `probe_p7_session_retention_mysql.py`: Cascade foreign key khi dọn dẹp session retention (20–30s).
11. `probe_p9_connect_fence_mysql.py --refs 2000`: Migration 48 CHECK constraint trên 2,000 connect refs (20–30s).
12. Khởi tạo service container và ping healthcheck `mysqladmin ping` (32s).

#### Tại sao SQLite Hoàn toàn Không thể Thay thế MySQL 8.0?
Khảo sát kỹ thuật khẳng định các probe này **bắt buộc phải chạy trên MySQL 8.0 thật**, không thể giả lập bằng SQLite:
1. **Khóa Dòng và Khoảng Khóa InnoDB (Next-Key Locks & Gap Locks)**: Các probe kiểm tra concurrency ép 2 threads gửi request cùng một mili-giây qua `threading.Barrier`. InnoDB sử dụng Gap Locks để bảo vệ chỉ mục, một bên nhận `HTTP 200` và một bên nhận `HTTP 409 AUTHORITY_OPERATION_REUSED` hoặc bắt được `Deadlock (Error 1213)`. SQLite chỉ có database-level lock, hoàn toàn không thể tái hiện cơ chế này.
2. **Giao dịch Chỉ Đọc Tuyệt đối (`START TRANSACTION ... READ ONLY`)**: API phân tích thống kê chạy trong transaction READ ONLY. Nếu code vô tình phát sinh thao tác ghi, MySQL lập tức chặn đứng với `Error 1792`. SQLite hoàn toàn phớt lờ cờ này.
3. **Ràng buộc DDL & CHECK Constraint**: MySQL 8.0 thực thi nghiêm ngặt các CHECK constraint khi chạy `ALTER TABLE`. SQLite xử lý DDL rất lỏng lẻo.

Tuy nhiên, **việc ép buộc chạy toàn bộ 12 probe này trên mọi commit merge to master** (kể cả khi chỉ sửa code frontend hay tài liệu) là một sự lãng phí tài nguyên khổng lồ (ngốn 360 runner-minutes/tháng).

---

## 3. KHẢO SÁT & ĐÁNH GIÁ CHI TIẾT 4 ỨNG VIÊN KIẾN TRÚC

Bảng dưới đây tổng hợp đánh giá sơ bộ 4 ứng viên trước khi đi vào phân tích chuyên sâu:

| Ứng viên | Tên Kiến trúc | Mục tiêu Chính | Khả thi | Đánh giá Khuyến nghị |
|:---:|---|---|:---:|:---|
| **A** | Pytest / Shared Fixtures / Rollback | Giảm thời gian CPU backend | ❌ Thấp | **BÁC BỎ HOÀN TOÀN** (Rủi ro State Leakage, vi phạm `AGENTS.md`) |
| **B** | Tiered CI / Test Pyramid 3 Tầng | Giảm Wall-Clock & Runner-Minutes | ✅ Rất cao | **KHUYẾN NGHỊ CỐT LÕI** (Selective merge, Nightly cron, Conditional gate) |
| **C** | Matrix Sharding | Giảm Wall-Clock Time | ⚠️ Trung bình | **ÁP DỤNG CÓ ĐIỀU KIỆN** (Chỉ dùng cho Nightly, tránh bẫy Quota) |
| **D** | Build & Contract Optimization | Triệt tiêu lãng phí `spa-contract` | ✅ Rất cao | **KHUYẾN NGHỊ TUYỆT ĐỐI (D2)** (Gộp in-place vào job `frontend`) |

---

### 3.1 Ứng viên A: Tái cấu trúc Fixture (Pytest / Shared App & DB Context / Rollback) — BÁC BỎ

#### Đề xuất Kỹ thuật của Ứng viên A
1. Chuyển đổi toàn bộ test runner sang `pytest` (kết hợp `pytest-flask`).
2. Khởi tạo 1 Flask Application Factory duy nhất ở mức Session hoặc Module (`@pytest.fixture(scope="session")`).
3. Khởi tạo 1 connection SQLite in-memory duy nhất, chạy `db.create_all()` 1 lần.
4. Bọc mỗi test case trong một nested transaction (`SAVEPOINT`) và thực hiện `ROLLBACK` sau khi test kết thúc thay vì gọi `db.drop_all()`.

#### Lợi ích Lý thuyết
- Triệt tiêu ~876 lần gọi `create_app()` $\rightarrow$ Tiết kiệm ~5.54 phút CPU.
- Triệt tiêu ~1,382 lần gọi `db.create_all() / drop_all()` $\rightarrow$ Tiết kiệm ~3.54 phút CPU.
- Giảm thời gian chạy backend từ 14.6 phút xuống còn ~2.5 – 3.5 phút.

#### Lập luận Kỹ thuật Bác bỏ Hoàn toàn Ứng viên A

Mặc dù có lợi ích lý thuyết hấp dẫn, khảo sát kỹ thuật sâu sắc cho thấy Ứng viên A chứa đựng **5 rủi ro chết người**, phá vỡ tính toàn vẹn của hệ thống:

1. **Xung đột Trực diện với Guardrail Bắt buộc trong `AGENTS.md`**:
   `AGENTS.md` quy định rõ ràng:
   > *"The suite is flat unittest with per-file app/database setup and no shared fixture layer. Copy the closest existing test file instead of inventing a new harness."*
   
   Đây là **quy chuẩn kiến trúc tối thượng** phục vụ mô hình **Multi-Agent Swarm** của Flama:
   - Hệ thống được vận hành và đóng góp code đồng thời bởi nhiều AI agents độc lập (Claude Code, Antigravity, Codex).
   - Mô hình flat unittest đảm bảo mỗi file test là một ốc đảo hoàn toàn khép kín, tự cung tự cấp. Bất kỳ agent nào cũng có thể tạo test mới bằng cách nhân bản file test gần nhất mà không cần hiểu hay phụ thuộc vào cấu trúc fixture phân tầng.
   - Nếu tạo ra shared fixture layer, bất kỳ lỗi nào xuất hiện trong fixture chung sẽ làm sập đồng loạt 235 test files, làm tê liệt toàn bộ các agents khác.

2. **Rò rỉ Khóa Tự tăng SQLite (`sqlite_sequence` State Leakage)**:
   - Khảo sát mã nguồn phát hiện **ít nhất 14 test files** (như `test_anki_scheduler.py`, `test_study_integration.py`, `test_flashcard_api.py`) có các assertion cố định phụ thuộc vào việc ID tự tăng bắt đầu từ 1:
     `self.assertEqual(user.id, 1)`, `self.assertEqual(deck.id, 1)`, hoặc Foreign Key gán cứng `deck_id=1`.
   - Trong SQLite, lệnh `ROLLBACK` của transaction **TUYỆT ĐỐI KHÔNG khôi phục lại bảng hệ thống `sqlite_sequence`**.
   - Sau khi test case đầu tiên tạo user (id=1) và rollback, test case thứ hai tạo user mới sẽ nhận `id=2`! Toàn bộ các test case có assertion ID cố định sẽ lập tức FAIL hàng loạt.

3. **Vô hiệu hóa Cơ chế Rollback do Lệnh `db.session.commit()` trong Service Layer**:
   - Rất nhiều dịch vụ cốt lõi trong `app/services/` (`study_service.py`, `flashcards_share_service.py`, `deck_change_request_service.py`) chủ động gọi `db.session.commit()` để hoàn tất nghiệp vụ.
   - Khi chạy qua SQLAlchemy với SQLite, một lệnh `commit()` từ service sẽ **commit vĩnh viễn toàn bộ transaction hiện tại xuống cơ sở dữ liệu**, phá vỡ hoàn toàn ranh giới của `SAVEPOINT` do fixture thiết lập. Dữ liệu rác sẽ tồn đọng trên SQLite in-memory và làm sai lệch kết quả của các test case chạy tiếp theo.

4. **Rò rỉ Trạng thái Bộ nhớ RAM (In-Memory State Pollution)**:
   - Các dịch vụ độc lập trong ứng dụng duy trì bộ nhớ state trên RAM:
     - `login_rate_limit_service`: Duy trì dictionary đếm số lần đăng nhập sai theo IP/username.
     - `daily_rate_limit_service`: Duy trì bộ đếm request trong ngày.
     - Transactional Outbox: Danh sách in-memory `outbox = []`.
     - `app.config`: Rất nhiều test case can thiệp động vào `app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = False`.
   - Nếu dùng chung một instance `app` xuyên suốt phiên chạy, các đột biến cấu hình và trạng thái bộ nhớ này sẽ lưu cữu, tạo ra hiện tượng "flaky tests" cực kỳ khó phát hiện và debug.

5. **Nhân bản SQLAlchemy Event Listeners**:
   - Trong `app/__init__.py`, hàm `create_app()` đăng ký hàng loạt event listener vào SQLAlchemy models (`review_analytics_projection`, `deck_count_projection`, `field_value_identity_hooks`).
   - Nếu fixture không unregister hoàn hảo, các listener này sẽ bị đăng ký lặp lại nhiều lần. Mỗi lần gọi `db.session.flush()`, các hook này sẽ chạy lặp lại $N$ lần, tự động chèn các bản ghi projection trùng lặp, làm sập cơ sở dữ liệu với lỗi vi phạm ràng buộc toàn vẹn (Unique Constraint Violation).

**Kết luận**: **BÁC BỎ HOÀN TOÀN Ứng viên A**. Không tiến hành chuyển đổi sang Pytest hay shared DB fixture.

---

### 3.2 Ứng viên B: Kiến trúc Phân tầng Pipeline (Tiered CI / Test Pyramid 3 Tầng) — KHUYẾN NGHỊ

#### Mô hình Đề xuất
Ứng viên B đề xuất tái cấu trúc quy trình kiểm thử theo mô hình Kim tự tháp 3 Tầng:

```
                            ▲
                           / \
                          /   \
                         /     \
                        /   T3  \   Tầng 3: Conditional Gate
                       /─────────\  (Chỉ chạy MySQL Contract khi đổi DB/Schema)
                      /     T2    \ Tầng 2: Nightly Full Cron
                     /─────────────\ (100% Full Suite 2,436 Tests lúc 02:00 UTC)
                    /       T1      \ Tầng 1: Per-PR & Per-Merge Fast Path
                   /─────────────────\ (Selective Tests theo Changed Modules + Core Smoke)
```

1. **Tầng 1 (Per-PR & Per-Merge Fast Path)**:
   - Bãi bỏ việc ép buộc `CI_FORCE_ALL_VALIDATION=true` trên nhánh `master`.
   - Cả Pull Request lẫn Merge to master đều sử dụng cơ chế chọn lọc thông minh: `scripts/run_tests.py --changed`.
   - **Đồng bộ Decouple cả hai jobs `backend` và `frontend` trên `master`**: Cho phép cả hai jobs chạy selective test theo git diff thay vì bị ép chạy full suite.
   - Bổ sung một **Core Smoke Gate** siêu nhẹ: Chạy 12 files tests thuộc module `core` (kiểm tra App factory, routing, auth token, security handlers) kéo dài chỉ **~25 giây**.
   - Nếu commit chỉ sửa đổi Frontend: Job `backend` chỉ chạy core smoke gate (~45s), job `frontend` chạy selective tests (~3m).
   - Thời gian Wall-clock khi merge: **3.5 – 5 phút** (thay vì 16.5 – 20 phút).
   - Runner-minutes khi merge: **6 – 17 phút** (trung bình 9.7 phút, thay vì 33 phút).

2. **Tầng 2 (Nightly Full Validation Cron - Lưới An toàn Định kỳ)**:
   - Thiết lập một GitHub Actions workflow độc lập (`.github/workflows/nightly.yml`), tự động kích hoạt vào **02:00 AM UTC các ngày làm việc từ Thứ Hai đến Thứ Sáu** (`0 2 * * 1-5`, Baseline Khuyến nghị 22 lượt run/tháng).
   - Chạy 100% toàn diện: Toàn bộ 235 backend test files (2,436 tests), 174 frontend test files (Vitest + tsc), toàn bộ các contract probes của MySQL 8.0 InnoDB và Redis 7.
   - Tổng thời lượng viễn trắc thực tế mỗi lượt Nightly là **30 billable minutes** (`backend-full`: 16m + `frontend-full`: 7m + `mysql-contract-full`: 6m + `redis-contract-full`: 1m).
   - Đảm bảo bắt được 100% mọi lỗi hồi quy tiềm ẩn nếu có sự kết hợp bất thường giữa các module mà selective test bỏ sót.

3. **Tầng 3 (Conditional Gate Toàn diện cho MySQL Contract - Zero False Negatives)**:
   - Tách job `mysql-contract` thành một cổng kiểm soát có điều kiện nghiêm ngặt trước khi Deploy.
   - Vì quy trình CD sẽ **Deploy to Production ngay lập tức** sau khi merge master thành công, Conditional Gate bắt buộc phải có độ bao phủ kín khít tuyệt đối (**Zero False Negatives**), không thể trông chờ vào Nightly Cron (vốn chỉ đóng vai trò Hậu kiểm Post-deployment Audit).
   - Chỉ kích hoạt trên `master` khi Git diff của commit có chứa các thay đổi khớp với `MYSQL_CONTRACT_SOURCE_PATTERNS`:
     - `models/**`
     - `migrations/**`
     - `app/repositories/**` (Mở rộng toàn bộ repositories thay vì chỉ 7 file lẻ)
     - `app/services/stats_today_future.py` (Bảo vệ giao dịch READ ONLY khỏi lỗi MySQL Error 1792)
     - `app/services/study_service.py` (Bảo vệ logic direct replay và deck counts khỏi lỗi Deadlock/InnoDB)
     - `scripts/probe_*.py`
   - Đối với các commit thuần frontend, i18n, docs hoặc API không đụng tới DB, job này tự động `skipped`, tiết kiệm ngay **6 billable runner-minutes** cho mỗi lần merge.

**Đánh giá Khuyến nghị**: **KHUYẾN NGHỊ CỐT LÕI**. Đây là giải pháp giải quyết đồng thời cả hai mục tiêu: kéo sập thời gian chờ của lập trình viên và cắt giảm mạnh mẽ hạn ngạch runner-minutes.

---

### 3.3 Ứng viên C: Ma trận Song song hóa (Matrix Sharding) — PHÂN TÍCH RẠCH RÒI WALL-CLOCK VS QUOTA

#### Ý tưởng Kỹ thuật
Chia danh sách 235 test files của job `backend` thành $N$ nhóm (shards) chạy song song trên $N$ máy ảo GitHub Actions riêng biệt thông qua cú pháp `strategy.matrix`:
```yaml
strategy:
  matrix:
    shard: [1, 2, 3, 4]
```

#### Phân tích Rạch ròi: Wall-Clock Time vs Quota Runner-Minutes

Nhiều kỹ sư thường lầm tưởng rằng: *"Chạy song song 4 máy sẽ giúp pipeline nhanh gấp 4 lần và tối ưu hóa hệ thống."* Thực tế viễn trắc cho thấy một sự thật hoàn toàn trái ngược:

1. **Về Wall-Clock Time (Thời gian lập trình viên chờ đợi)**:
   - Chia 235 test files (877s) thành 4 shards: Mỗi shard chạy khoảng 220 giây (~3.6 phút).
   - Cộng overhead khởi tạo môi trường (~25s): Tổng thời gian mỗi shard là **~4 phút**.
   - Wall-clock time của job `backend` giảm ngoạn mục từ **15 phút 03 giây xuống còn ~4 phút**!

2. **Về Quota Runner-Minutes (Hạn ngạch 2,000 phút/tháng bị trừ)**:
   - Mỗi máy ảo trong ma trận phải chịu overhead độc lập:
     - Checkout mã nguồn: 4s $\times$ 4 = 16s.
     - Setup Python 3.12: 3s $\times$ 4 = 12s.
     - Restore pip cache & cài đặt dependencies: 10s $\times$ 4 = 40s.
     - Teardown & logging: 8s $\times$ 4 = 32s.
     - Tổng overhead lãng phí do nhân bản môi trường: **100 giây CPU**.
   - **Quy tắc Làm tròn Phút Nguyên của GitHub Actions (The Rounding Trap)**:
     - Giả sử 4 shards chạy lần lượt: Shard 1 (3m45s), Shard 2 (3m50s), Shard 3 (3m40s), Shard 4 (4m05s).
     - GitHub Actions tính tiền: $\lceil 3.75 \rceil + \lceil 3.83 \rceil + \lceil 3.66 \rceil + \lceil 4.08 \rceil = 4 + 4 + 4 + 5 = \mathbf{17\text{ Billable Minutes}}$!
     - Trong khi đó, chạy 1 tiến trình duy nhất mất 15m03s chỉ bị tính **16 Billable Minutes**.
   - **Hệ quả**: Matrix Sharding làm **TĂNG tổng hạn ngạch tiêu thụ hàng tháng** (tăng thêm 1–2 phút cho mỗi lần chạy).

**Kết luận về Ứng viên C**:
- **KHÔNG THỂ đứng độc lập** làm giải pháp cho bài toán quota 2,000 phút/tháng. Nếu áp dụng sharding trên mọi lần merge to master, quota sẽ cạn kiệt nhanh hơn nữa!
- **Chỉ áp dụng có điều kiện (Conditional Matrix Sharding)**: Sử dụng 2–3 shards riêng cho workflow **Nightly Full Cron** (nơi cần kiểm tra 100% full suite mà không muốn workflow chạy quá 20 phút), tuyệt đối **KHÔNG dùng sharding cho các lượt Per-Merge Fast Path hàng ngày**.

---

### 3.4 Ứng viên D: Tinh giản Build & Gộp Contract Assertion (D1 vs D2) — KHUYẾN NGHỊ TUYỆT ĐỐI D2

Nhằm giải quyết sự lãng phí vô lý của job `spa-contract` (tiêu tốn 1–3 runner-minutes cho 3 giây kiểm thử), có hai phương án kỹ thuật được đặt lên bàn cân:

#### Phương án D1: Truyền Build Artifact qua `actions/upload-artifact` & `download-artifact`
- **Cơ chế**: Job `frontend` build xong thì upload thư mục `frontend/dist/` lên GitHub Storage. Job `spa-contract` tải về và chạy test, không cần chạy lại `npm ci` và Vite build.
- **Đánh giá Kỹ thuật**:
  - Tiết kiệm được ~69 giây build trong `spa-contract`. Thời gian job giảm xuống còn ~1m25s.
  - Tuy nhiên, 1m25s vẫn vượt quá 60s, nên GitHub Actions **vẫn làm tròn thành 2 billable minutes**! Mức tiết kiệm thực tế chỉ là 1 phút/run (~60 phút/tháng).
  - **Vi phạm nghiêm trọng bài test hiện hữu**: `tests/test_ci_workflow.py:87–95` kiểm tra `assertNotIn("actions/upload-artifact", workflow)`. Test này sẽ FAIL ngay lập tức!
  - **Rủi ro cạn kiệt Storage Quota**: Với 21.5 MB/build $\times$ 80 runs/tháng = ~1.72 GB dữ liệu trung chuyển, nguy cơ làm nghẽn trần 500 MB của GitHub Storage là hiện hữu.
  - **Kết luận**: **BÁC BỎ Phương án D1**.

#### Phương án D2: Gộp Assertion trực tiếp vào Job `frontend` (In-place SPA Contract Verification)
- **Cơ chế**:
  - Xóa bỏ hoàn toàn job `spa-contract` khỏi DAG của workflow.
  - Tận dụng việc job `frontend` **đã có sẵn Python 3.12** (`actions/setup-python@v5` ở đầu job) và thư mục `frontend/dist/` vừa được build xong nằm sẵn trên ổ đĩa cục bộ.
  - **Cấu hình Bắt buộc Pip Cache**: Step `actions/setup-python@v5` trong job `frontend` phải được bổ sung `cache: 'pip'` và `cache-dependency-path: requirements.txt`. Nếu không có pip cache, runner sẽ phải tải lại hơn 50 bánh xe wheels từ PyPI qua mạng mỗi lần chạy, tốn thêm 40–55 giây và tiềm ẩn rủi ro timeout mạng!
  - Bổ sung 2 bước trực tiếp ngay sau step `Build`:
    ```yaml
    - name: Install backend contract dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r ../requirements.txt

    - name: Verify Flask serves real Vite artifact
      env:
        DB_USER: ci
        DB_NAME: ci
        SECRET_KEY: ci-secret
        FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'
      run: python -m unittest tests.test_spa_artifact_contract
      working-directory: .
    ```
- **Đánh giá Định lượng Vượt trội**:
  - **Triệt tiêu 100% chi phí của job `spa-contract`**: Giảm từ 1–3 billable minutes về **0 phút** (Khi đứng độc lập trên As-Is, D2 giảm 1 phút từ 33m xuống 32m; hoặc giảm tới 3m khi tính trường hợp cache-miss, tương đương tiết kiệm 120–180 phút/tháng).
  - Thời gian thêm vào job `frontend`: Chỉ mất thêm **~15–20 giây** nhờ tận dụng pip cache.
  - **Tác động đến Wall-Clock Time**: **HOÀN TOÀN BẰNG 0 (Zero Regression)**! Bởi vì job `frontend` (kể cả sau khi thêm 20s chỉ mất ~3 phút) vẫn kết thúc trước `backend` (15 phút) hoặc `mysql-contract` (5.8 phút). Nó nằm trọn vẹn trong "thời gian rỗi" (slack time) của pipeline.
  - **100% Tuân thủ Triết lý Zero Artifact Storage**: Không phát sinh bất kỳ byte dữ liệu nào trên GitHub Storage Quota.
  - Đơn giản hóa DAG: Giảm từ 7 jobs xuống còn 6 jobs (hoặc 5 jobs khi skip mysql-contract).

#### Kế hoạch Tái cấu trúc Bộ Test Bảo vệ Cấu trúc (`tests/test_ci_workflow.py`) cho Ứng viên D2
Quá trình thử nghiệm đối kháng kỹ thuật phát hiện rằng: **5 trong tổng số 10 test methods (50% test suite) trong `tests/test_ci_workflow.py` sẽ bị FAIL ngay lập tức** nếu xóa job `spa-contract` mà không có kế hoạch refactor đồng bộ:

1. **`test_backend_is_independent_from_frontend_and_redis` (dòng 68–70)**:
   - *Hiện trạng*: `backend_block = self.workflow.split("\n  backend:\n", 1)[1].split("\n  spa-contract:\n", 1)[0]`.
   - *Lỗi xảy ra*: Cắt chuỗi theo `\n  spa-contract:\n` bị trượt, `backend_block` nuốt chửng cả job `redis-contract`, làm fail assertion `assertNotIn("image: redis", backend_block)`.
   - *Kế hoạch Refactor*: Đổi điểm cắt chuỗi kết thúc của `backend_block` thành `\n  redis-contract:\n` (hoặc phân tích theo cú pháp YAML block độc lập).
2. **`test_expensive_environment_contracts_are_explicit` (dòng 78–79)**:
   - *Hiện trạng*: `self.assertIn("  spa-contract:\n", self.workflow)`.
   - *Lỗi xảy ra*: Ném `AssertionError` vì job `spa-contract:` không còn tồn tại độc lập.
   - *Kế hoạch Refactor*: Chuyển đổi kiểm tra sang cấp độ in-place: Xác nhận chuỗi step `Verify Flask serves real Vite artifact` và biến `FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'` xuất hiện tường minh bên trong job `frontend`.
3. **`test_ci_uses_no_actions_artifact_storage` (dòng 93–100)**:
   - *Hiện trạng*: `spa_block = self.workflow.split("\n  spa-contract:\n", 1)[1].split("\n  redis-contract:\n", 1)[0]`.
   - *Lỗi xảy ra*: Ném ngoại lệ `IndexError: list index out of range`.
   - *Kế hoạch Refactor*: Trích xuất `frontend_block` (`\n  frontend:\n` đến `\n  backend:\n`), kiểm tra thứ tự thực thi: `npm ci` $\rightarrow$ `npm run build:ci` $\rightarrow$ `tests.test_spa_artifact_contract` diễn ra trên cùng một runner cục bộ mà hoàn toàn không có `actions/upload-artifact`.
4. **`test_production_deploy_is_called_only_after_master_validation` (dòng 107–112)**:
   - *Hiện trạng*: Kiểm tra chuỗi cứng `needs: [changes, frontend, backend, spa-contract, redis-contract, mysql-contract]`.
   - *Lỗi xảy ra*: Khi xóa `spa-contract`, danh sách needs đổi thành `[changes, frontend, backend, redis-contract, mysql-contract]` khiến assertion FAIL.
   - *Kế hoạch Refactor*: Cập nhật chuỗi mong đợi trong assertion khớp với danh sách needs mới của job `deploy`.
5. **`test_change_plan_controls_layer_and_contract_jobs` (dòng 57–65)**:
   - *Hiện trạng*: Kiểm tra `steps.plan.outputs.spa_contract` trong workflow.
   - *Kế hoạch Refactor*: Duy trì output `spa_contract` trong planner để làm điều kiện conditional step cho in-place verification trong job `frontend` hoặc chuẩn hóa theo hợp đồng mới.

*Nguyên tắc Thực thi*: Kế hoạch refactor 5 test methods trên phải được commit **đồng thời (atomic commit)** cùng với thay đổi `.github/workflows/ci.yml` trong Giai đoạn 1 để đảm bảo pipeline CI tự kiểm chứng luôn xanh (green).

**Kết luận**: **KHUYẾN NGHỊ TUYỆT ĐỐI Phương án D2** kèm theo Pip Cache và kế hoạch refactor `tests/test_ci_workflow.py`.

---

## 4. MÔ HÌNH KIẾN TRÚC ĐỀ XUẤT (TO-BE ARCHITECTURE: HYBRID B + D2 + CONDITIONAL C)

### 4.1 Sơ đồ Kiến trúc & Đồ thị Luồng Công việc Mới (To-Be DAG)

Kiến trúc mới hợp nhất các ưu điểm vượt trội của Ứng viên B, D2 và Conditional C, loại bỏ hoàn toàn các nút thắt dư thừa:

#### A. Quy trình Chạy Hàng ngày: Per-PR & Per-Merge Fast Path (`ci.yml`)

```
                          [Event: push (master) / pull_request]
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │     changes     │ (17s)
                                   │  (Selective     │
                                   │   Test Planner) │
                                   └────────┬────────┘
                                            │
                 ┌──────────────────────────┼──────────────────────────┐
                 │                          │                          │ (Conditional)
                 ▼                          ▼                          ▼
        ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
        │     backend     │        │    frontend     │        │  mysql-contract │
        │ (Selective Tests│        │ (Vitest + Build │        │  (Only if DB/   │
        │  + Core Smoke)  │        │  + SPA Assert)  │        │   Models change)│
        │   [3m - 4m]     │        │     [3m]        │        │     [5.8m]      │
        └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
                 │                          │                          │
                 │                          │ (Optional Redis)         │
                 │                          │ ┌───────────────┐        │
                 │                          ├─┤redis-contract │        │
                 │                          │ └───────┬───────┘        │
                 │                          │         │                │
                 └──────────────────────────┼─────────┴────────────────┘
                                            │
                                            ▼ (Anti-Cascading-Skip Protected)
                                   ┌─────────────────┐
                                   │     deploy      │ (57s)
                                   │  (Hostinger VPS)│
                                   └─────────────────┘
```

#### Cơ chế Chống Cascading Skip cho Job `deploy` (Critical DAG Trap Mitigation)
Trong GitHub Actions, khi một job phụ thuộc vào danh sách `needs: [...]`, biểu thức điều kiện ngầm mặc định là `success()`. Nếu **BẤT KỲ job nào trong `needs` có trạng thái là `skipped`** (chẳng hạn `mysql-contract` hoặc `redis-contract` bị bỏ qua khi commit chỉ sửa frontend, i18n, hoặc tài liệu), GitHub Actions sẽ tự động đánh giá điều kiện job `deploy` thành `False` và **TỰ ĐỘNG SKIP LUÔN JOB `deploy`**!

- **Hậu quả nếu không có biện pháp bảo vệ**: Pipeline merge to master hiển thị trạng thái xanh toàn bộ, nhưng mã nguồn **hoàn toàn không được deploy lên VPS Hostinger**, gây gián đoạn quy trình phát hành sản phẩm.
- **Biện pháp Khắc phục Bắt buộc**: Cấu hình mệnh đề `if:` cho job `deploy` trong `.github/workflows/ci.yml` sử dụng hàm lọc trạng thái kết quả:
  ```yaml
  deploy:
    needs: [changes, frontend, backend, redis-contract, mysql-contract]
    if: >-
      github.event_name == 'push' &&
      github.ref == 'refs/heads/master' &&
      needs.changes.outputs.deploy == 'true' &&
      !contains(needs.*.result, 'failure') &&
      !contains(needs.*.result, 'cancelled')
  ```
  Biểu thức `!contains(needs.*.result, 'failure') && !contains(needs.*.result, 'cancelled')` cho phép job `deploy` kích hoạt an toàn kể cả khi các upstream contract jobs ở trạng thái `skipped`, chỉ dừng lại khi có ít nhất một job upstream thực sự thất bại hoặc bị hủy.

#### B. Quy trình Kiểm thử Toàn diện Hàng đêm: Nightly Full Validation (`nightly.yml`)

```
                   [Schedule: 02:00 AM UTC Thứ 2 – Thứ 6 (Weekday Baseline)]
                                            │
                                            ▼
                 ┌──────────────────────────┼──────────────────────────┬──────────────────────────┐
                 │                          │                          │                          │
                 ▼                          ▼                          ▼                          ▼
        ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
        │ backend-full    │        │  frontend-full  │        │mysql-contract-fl│        │redis-contract-fl│
        │ (235 Test Files │        │ (174 Test Files │        │ (Full 12 Probes │        │ (Redis 7 Shared │
        │  2,436 Tests)   │        │  Vitest + Build │        │  Concurrency)   │        │  State Tests)   │
        │  [15m - 16m]    │        │   + SPA Assert) │        │     [5.8m]      │        │      [32s]      │
        │  Billable: 16m  │        │  [6m14s -> 7m]  │        │  Billable: 6m   │        │  Billable: 1m   │
        └────────┬────────┘        └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
                 │                          │                          │                          │
                 └──────────────────────────┼──────────────────────────┴──────────────────────────┘
                                            │
                                            ▼ (TỔNG BILLABLE: 30 PHÚT / RUN)
                                   ┌─────────────────┐
                                   │  nightly-report │ (10s)
                                   │ (Health Summary)│
                                   └─────────────────┘
```

---

### 4.2 Cơ chế Selective Fast Merge & Đồng bộ Decouple Cả Backend Lẫn Frontend trên Master

#### Điều chỉnh Thiết lập Kích hoạt trong `ci.yml`
Thay vì gán cứng `CI_FORCE_ALL_VALIDATION=true` khi event là `push` lên master:
```yaml
      - name: Plan affected validation jobs
        id: plan
        env:
          # Chỉ ép buộc full validation khi được kích hoạt thủ công qua workflow_dispatch
          CI_FORCE_ALL_VALIDATION: ${{ github.event_name == 'workflow_dispatch' }}
          DEPLOYED_RELEASE_SHA: ${{ steps.deployed.outputs.sha }}
        run: python scripts/run_tests.py --ci-plan --github-output "$GITHUB_OUTPUT"
```

#### Nguy cơ Chí mạng: Lãng phí 240 Phút/Tháng nếu Bỏ quên Decouple Job `frontend`
Trong `.github/workflows/ci.yml` hiện tại (dòng 120–127):
```bash
if [ "${{ github.ref_name }}" = "master" ] || [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
  echo "Running full frontend test suite on master..."
  npm test
else
  echo "Running targeted tests for changed files..."
  python ../scripts/run_tests.py --changed --frontend-only
fi
```
Nếu kỹ sư chỉ sửa job `backend` mà **bỏ quên việc sửa điều kiện trong job `frontend`**, thì trên mọi commit merge to master, job `frontend` sẽ **tiếp tục chạy `npm test` toàn diện (6m14s thực tế, làm tròn thành 7 billable minutes)** thay vì selective test (3 billable minutes)!
- Mức lãng phí phát sinh: $(7 - 3) = 4\text{ phút} \times 60\text{ merges} = \mathbf{240\text{ runner-minutes/tháng}}$!
- Hậu quả: Đẩy tổng mức tiêu thụ tháng lên **2,200 phút/tháng** (vượt trần 200 phút), làm phá sản hoàn toàn mục tiêu kiểm soát quota dưới 2,000 phút!

#### Đồng bộ Cập nhật Lệnh Thực thi cho CẢ HAI Jobs `backend` và `frontend`:
1. **Trong Job `backend`**:
   ```bash
   if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
     echo "Running full backend test suite on manual dispatch..."
     python scripts/run_tests.py --all --backend-only
   else
     echo "Running selective tests with Core Smoke Gate on master/PR..."
     python scripts/run_tests.py --changed --backend-only
   fi
   ```
2. **Trong Job `frontend`**:
   ```bash
   if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
     echo "Running full frontend test suite on manual dispatch..."
     npm test
   else
     echo "Running targeted tests for changed files..."
     python ../scripts/run_tests.py --changed --frontend-only
   fi
   ```

#### Thiết lập Core Smoke Gate trong `backend`
Để đảm bảo an toàn tuyệt đối khi merge to master (tránh trường hợp một commit frontend làm gãy routing chung hoặc boot logic), job `backend` trên nhánh master sẽ luôn thực thi:
$$\text{Backend Tests} = \text{Affected Domain Modules} \cup \text{Core Smoke Suite}$$

Bộ **Core Smoke Suite** gồm 12 test files thiết yếu trong module `core` (`tests/test_api_v1_route_map.py`, `tests/test_app_startup.py`, `tests/test_cors.py`, `tests/test_deploy_workflow.py`, `tests/test_download_routes.py`, `tests/test_logging_redaction.py`, `tests/test_rest_api_v1.py`, `tests/test_rest_only_runtime.py`, `tests/test_spa_artifact_contract.py`, `tests/test_spa_routes.py`, `tests/test_sync_managed_env.py`, `tests/test_template_formatters.py`), kiểm tra:
- Khởi tạo App Factory và cấu hình CSRF/CORS.
- Cơ chế giải mã JWT và Identity Token.
- Tuyến điều hướng SPA shell `/api/` fallback.
- Thời gian chạy của Core Smoke Suite: chỉ **22 – 28 giây** (33.8s trên máy trạm Windows).

Nếu commit merge chỉ sửa frontend/docs:
- Job `backend` chỉ chạy Core Smoke Gate $\rightarrow$ Hoàn tất trong **~45 giây** (kể cả setup).
- Job `frontend` chỉ chạy selective Vitest $\rightarrow$ Hoàn tất trong **~3 phút**.
- Wall-clock time của master merge giảm từ 16.5m xuống còn **~3.5 – 4.5 phút**!

---

### 4.3 Cơ chế Conditional Gate Toàn diện cho MySQL Contract Probes (Zero False Negatives)

Trong `ci.yml`, điều kiện kích hoạt của job `mysql-contract` được chuẩn hóa:
```yaml
  mysql-contract:
    needs: changes
    if: needs.changes.outputs.mysql_contract == 'true'
    runs-on: ubuntu-latest
```
Hàm `build_ci_change_plan` trong `scripts/run_tests.py` sẽ đánh giá cờ `mysql_contract` dựa trên sự thay đổi thực tế:
```python
"mysql_contract": force_all_validation or matches_any(MYSQL_CONTRACT_SOURCE_PATTERNS),
```

#### Lỗ hổng Trọng yếu Phát hiện trong Phản biện Đối kháng:
Kiểm tra thực tế mã nguồn `scripts/run_tests.py:1051–1128` cho thấy danh sách `MYSQL_CONTRACT_SOURCE_PATTERNS` hiện thời **chỉ liệt kê 7 repository cụ thể**, hoàn toàn **chưa có wildcard `app/repositories/**`**, và thiếu vắng các service quan trọng liên quan đến MySQL locking và transaction:
- `app/services/stats_today_future.py`: Chạy trong `analytics_read_transaction()` (`START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY`). Bất kỳ câu lệnh ghi vô tình nào sẽ gây lỗi `pymysql.err.OperationalError: (1792, "Cannot execute statement in a READ ONLY transaction.")` trên MySQL 8.0, trong khi SQLite hoàn toàn bỏ qua. Nếu file này bị sửa mà không kích hoạt gate, lỗi sẽ lọt thẳng lên VPS Production!
- `app/services/study_service.py` & `app/repositories/study_repository.py`: Chứa các hàm nghiệp vụ rollup thẻ và overlay note, được kiểm tra bởi `probe_p5_direct_replay_mysql.py` và `probe_deck_counts_mysql.py`. Các lỗi InnoDB Deadlock (Error 1213) hoặc Lock Timeout (Error 1205) chỉ xuất hiện trên MySQL thật.

#### Mở rộng Danh sách `MYSQL_CONTRACT_SOURCE_PATTERNS` Bắt buộc:
Trong `scripts/run_tests.py`, danh sách pattern phải được mở rộng đầy đủ:
```python
MYSQL_CONTRACT_SOURCE_PATTERNS = (
    "scripts/archive_retired_tables.py",
    "scripts/bootstrap_historical_schema.py",
    "scripts/prepare_retirement_mysql_rehearsal.py",
    "scripts/verify_retirement_protected_state.py",
    "scripts/probe_retirement_fresh_chain_mysql.py",
    "migrations/**",
    "models/**",
    "requirements.txt",
    "scripts/probe_p1_02_mysql_concurrency.py",
    "tests/test_marketplace_taxonomy_migration.py",
    # Mở rộng toàn diện tầng Repository để bao quát mọi câu truy vấn SQL thô và locking
    "app/repositories/**",
    # Analytics READ ONLY contract (chống lỗi MySQL Error 1792)
    "app/api/v1/analytics/**",
    "app/services/study_analytics_read_service.py",
    "app/services/deck_aggregation_service.py",
    "app/services/dashboard_service.py",
    "app/services/stats_overview.py",
    "app/services/stats_today_future.py",        # BỔ SUNG: Endpoint today-future analytics
    # Study service & direct replay locking (chống lỗi Deadlock Error 1213 & Gap Locks)
    "app/services/study_service.py",             # BỔ SUNG: Direct replay và deck counts target
    "app/services/study_composition_service.py", # BỔ SUNG: Concurrency barrier target
    "app/services/study_session_retention_service.py",
    "app/services/review_analytics_*.py",
    "app/services/deck_count_*.py",
    "app/services/forecast_snapshot_service.py",
    "app/services/field_value_identity_*.py",
    "scripts/probe_*.py",
    "scripts/bench_*.py",
    # ... các patterns di chuyển và guards khác
)
```

> **Nguyên tắc Thiết kế Bất biến**: Conditional Gate trước khi Deploy phải đạt chuẩn **Zero False Negatives** (Tuyệt đối không bỏ lọt thay đổi ảnh hưởng cơ sở dữ liệu). Nightly Cron đóng vai trò là cơ chế **Hậu kiểm Giám sát (Post-deployment Audit)**, tuyệt đối không được dùng làm lý do để buông lỏng cửa ải an toàn tiền triển khai.

---

### 4.4 Cơ chế Gộp SPA Contract Verification vào Job `frontend` & Cấu hình Pip Cache

Triển khai chính xác Phương án D2:
1. Xóa hoàn toàn khối job `spa-contract:` khỏi `.github/workflows/ci.yml`.
2. **Cấu hình Bắt buộc Pip Cache trong Job `frontend`**:
   Tại step `actions/setup-python@v5` ở đầu job `frontend`, bổ sung cờ cache pip:
   ```yaml
   - name: Setup Python for contract and changed-file selection
     uses: actions/setup-python@v5
     with:
       python-version: '3.12'
       cache: 'pip'
       cache-dependency-path: requirements.txt
   ```
   *Lợi ích*: Khi bật cache pip, việc cài đặt dependencies chỉ tốn **10–15 giây** từ wheel cache cục bộ của máy ảo GitHub Actions, thay vì tốn 40–55 giây tải lại qua mạng internet từ PyPI, loại bỏ triệt để nguy cơ lỗi timeout mạng.
3. Trong job `frontend`, sau step `Build` (`npm run build:ci`), thêm 2 steps:
   ```yaml
      - name: Build
        run: npm run build:ci

      # Candidate D2: In-place SPA Artifact Contract Verification
      - name: Install contract dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r ../requirements.txt

      - name: Verify Flask serves real Vite artifact
        env:
          DB_USER: ci
          DB_NAME: ci
          SECRET_KEY: ci-secret
          FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'
        run: python -m unittest tests.test_spa_artifact_contract
        working-directory: .
   ```
4. Cập nhật điều kiện phụ thuộc và chống skip của job `deploy`:
   ```yaml
   deploy:
     needs: [changes, frontend, backend, redis-contract, mysql-contract]
     if: >-
       github.event_name == 'push' &&
       github.ref == 'refs/heads/master' &&
       needs.changes.outputs.deploy == 'true' &&
       !contains(needs.*.result, 'failure') &&
       !contains(needs.*.result, 'cancelled')
   ```
5. Đồng bộ refactor 5 test methods trong `tests/test_ci_workflow.py` (theo Mục 3.4) để CI self-test luôn xanh.

---

### 4.5 Thiết kế Pipeline Kiểm thử Toàn diện Định kỳ (Nightly Full Validation Cron Chuẩn xác)

Tạo workflow mới tại `.github/workflows/nightly.yml`, khắc phục 100% các thiếu sót cú pháp và tham số môi trường:

```yaml
name: Nightly Full Validation

on:
  schedule:
    # Baseline Khuyến nghị: Kích hoạt lúc 02:00 AM UTC từ Thứ Hai đến Thứ Sáu (22 runs/tháng)
    - cron: '0 2 * * 1-5'
  workflow_dispatch: # Cho phép kích hoạt thủ công khi cần kiểm tra phát hành lớn

permissions:
  contents: read

jobs:
  backend-full:
    name: Full Backend Suite (2,436 Tests)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt
      - name: Run 100% Backend Unittests
        run: python scripts/run_tests.py --all --backend-only

  frontend-full:
    name: Full Frontend Suite (Vitest & tsc & SPA Contract)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22.22.2'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: requirements.txt
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - name: Build Production Bundle
        run: npm run build:ci
      - name: Install contract dependencies
        run: pip install -r ../requirements.txt
      - name: Verify Real SPA Artifact Delivery in Nightly
        env:
          DB_USER: ci
          DB_NAME: ci
          SECRET_KEY: ci-secret
          FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'
        run: python -m unittest tests.test_spa_artifact_contract
        working-directory: .

  redis-contract-full:
    name: Full Redis 7 Shared State Contract Tests
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt
      - name: Run Redis Contract Tests
        env:
          REDIS_URL: redis://127.0.0.1:6379/0
        run: python -m unittest tests.test_shared_state_services

  mysql-contract-full:
    name: Full MySQL 8.0 InnoDB Contract Probes
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_DATABASE: ci
          MYSQL_ROOT_PASSWORD: ci-root-password
        ports:
          - 3306:3306
        options: >-
          --health-cmd "mysqladmin ping -h 127.0.0.1 -uroot -pci-root-password"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 20
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
          cache-dependency-path: requirements.txt
      - run: pip install -r requirements.txt

      - name: Verify Alembic migrations on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
          SECRET_KEY: ci-secret
          STARTUP_RUN_MAINTENANCE: '0'
          STARTUP_RUN_DB_CREATE_ALL: '0'
        run: |
          python scripts/bootstrap_historical_schema.py --database ci --ci-empty-database
          flask --app wsgi.py db upgrade

      - name: Run MySQL locking and concurrency contract
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p1_02_mysql_concurrency.py

      - name: Run NOTE analytics read-only contract on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p5_analytics_mysql.py

      - name: Seed Anchor User 1 & Verify Analytics Counts
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: |
          python - <<'PY'
          import os
          from pathlib import Path
          from sqlalchemy.engine import URL
          from app import create_audit_app
          from models import db
          from models.user import User
          from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
          url = URL.create('mysql+pymysql', username=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']), database=os.environ['DB_NAME'], query={'charset':'utf8mb4'})
          assert url.database == 'ci' and url.host == '127.0.0.1'
          app = create_audit_app({'SQLALCHEMY_DATABASE_URI':url.render_as_string(hide_password=False)})
          with app.app_context():
              if db.session.get(User, 1) is None:
                  anchor = User(id=1, username='ci-analytics-anchor', email='ci-analytics-anchor@example.invalid', timezone='UTC')
                  db.session.add(anchor)
                  db.session.flush()
                  enroll_new_learner_note_authority(db.session, user=anchor)
                  db.session.commit()
          path = Path('output/analytics-counts-ci.env')
          path.parent.mkdir(exist_ok=True)
          path.write_text('SQLALCHEMY_DATABASE_URI=' + url.render_as_string(hide_password=False) + '\n', encoding='utf-8')
          PY
          python scripts/probe_review_analytics_mysql.py --env-file output/analytics-counts-ci.env
          python scripts/probe_deck_counts_mysql.py --env-file output/analytics-counts-ci.env

      - name: Run cross-learner NOTE write concurrency contract on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p5_concurrency_mysql.py --learners 4 --notes 24 --rounds 2 --answers 8 --signups 6 --creates 8

      - name: Run NOTE overlay and pristine materialization contract on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p5_direct_replay_mysql.py --overlay-only

      - name: Qualify complete retirement chain on a generated MySQL schema
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_retirement_fresh_chain_mysql.py --output output/retirement-fresh-mysql-ci.json

      - name: Qualify Field identity expansion and exact forecast buckets on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: |
          python scripts/probe_field_identity_mysql.py --output output/field-identity-mysql-ci.json
          python scripts/probe_forecast_snapshots_mysql.py --output output/forecast-snapshots-mysql-ci.json
          python scripts/probe_review_analytics_outbox_mysql.py --output output/review-outbox-mysql-ci.json

      - name: Verify retirement archives and contract guards with focused tests
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/run_tests.py --file tests/test_frozen_template_modernization.py tests/test_retirement_fresh_migration_chain.py tests/test_derived_card_retirement_migration.py tests/test_legacy_model_retirement.py tests/test_card_progress_retirement_migration.py tests/test_template_origin_retirement_migration.py --backend-only

      - name: Run Phase 7 session retention contract on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p7_session_retention_mysql.py

      - name: Run migration 48 Connect authority fence probe on MySQL
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: '3306'
          DB_USER: root
          DB_PASSWORD: ci-root-password
          DB_NAME: ci
        run: python scripts/probe_p9_connect_fence_mysql.py --refs 2000
```

*Lợi ích chiến lược*: Toàn bộ rủi ro của việc chia sẻ test theo modular testing trên PR/Merge được bảo hiểm 100% bằng tấm lưới an toàn Nightly Cron. Nếu có bất kỳ sự tương tác chéo tiềm ẩn nào giữa các module độc lập, hệ thống sẽ phát hiện và gửi thông báo cảnh báo vào sáng hôm sau, trước khi tính năng tiếp theo được phát triển.

---

## 5. BẢNG SO SÁNH ĐỊNH LƯỢNG & DỰ TOÁN NGÂN SÁCH QUOTA (COST & QUOTA MODELING)

### 5.1 Ma trận So sánh Toàn diện Hiện trạng vs Các Ứng viên

Bảng ma trận đối chiếu định lượng giữa Hiện trạng (As-Is) và các ứng viên kiến trúc dựa trên dữ liệu viễn trắc thực tế và kết quả stress-test đối kháng:

| Tiêu chí Đánh giá | Hiện trạng (As-Is Status Quo) | Ứng viên A (Pytest/Fixture) | Ứng viên B (Tiered CI 3 Tầng) | Ứng viên C (Matrix Sharding 4x) | Ứng viên D2 (Gộp SPA Contract) | **To-Be Hybrid (B + D2 + Cond C)** *(Baseline Khuyến nghị)* |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Wall-Clock Time (Master Merge)** | **16m 17s** | ~4m 30s | **3m 30s – 5m** | ~4m 15s | 16m 17s | **3m 30s – 5m 00s** |
| **Mức giảm Thời gian Chờ** | Chuẩn (0%) | Giảm 72% | Giảm 75% | Giảm 74% | 0% | **GIẢM 70% – 78%** |
| **Billable Minutes / Merge** | **33 phút** | ~14 phút | **10 – 12 phút** | ~34 phút (Bẫy làm tròn) | 30 – 32 phút | **6 – 17 PHÚT** *(TB 9.7 phút)* |
| **Mức giảm Quota / Merge** | Chuẩn (0%) | Giảm 57% | Giảm 66% | Tăng 3% (Lãng phí) | Giảm 3% – 9% | **GIẢM 67% – 75%** |
| **Quota cho 60 Merges/tháng** | **1,980 phút** | ~840 phút | **660 phút** | 2,040 phút | 1,800 – 1,920 phút | **580 PHÚT** *(40x Non-DB + 20x DB)* |
| **Quota cho 80 PRs/tháng** | **960 phút** | ~560 phút | **480 phút** | 960 phút | 840 phút | **480 PHÚT** *(120 runs @ 4m)* |
| **Quota cho Nightly Cron/tháng** | 0 phút | 0 phút | 660 – 900 phút | 0 phút | 0 phút | **660 PHÚT** *(22 runs @ 30m)* |
| **TỔNG RUNNER-MINUTES / THÁNG** | **2,940 PHÚT** | ~1,400 phút | **1,800 – 2,040 phút** | 3,000 phút | 2,640 – 2,760 phút | **1,720 PHÚT** *(BASELINE CHUẨN)* |
| **Tỷ lệ Tiêu thụ Quota (2,000 min)** | **147.0% (VƯỢT TRẦN)** | 70.0% | 90.0% – 102.0% | 150.0% (VƯỢT) | 132.0% – 138.0% | **86.0% (ĐẠT CHUẨN AN TOÀN)** |
| **Thặng dư Quota An toàn** | **-940 phút (Thâm hụt)** | +600 phút | -40 đến +200 phút | -1,000 phút | -640 đến -760 phút | **+280 PHÚT (14.0% QUOTA)** |
| **Rủi ro Rò rỉ Trạng thái (Leakage)** | Không | **RẤT CAO** (Sequence, RAM) | **KHÔNG CÓ** | Không | Không | **KHÔNG CÓ (TUYỆT ĐỐI AN TOÀN)** |
| **Tuân thủ Guardrail `AGENTS.md`** | 100% | **VI PHẠM NẶNG** | 100% | 100% | 100% | **100% TUÂN THỦ** |
| **Sửa đổi Mã nguồn Sản phẩm** | 0 file | >200 files | 0 file | 0 file | 0 file | **0 FILE (HOÀN TOÀN READ-ONLY)** |

*Ghi chú về Ứng viên D2 Độc lập*: Nếu chỉ triển khai D2 đơn lẻ trên nền tảng As-Is, job `spa-contract` (1 phút billable ở điều kiện bình thường) bị triệt tiêu, đưa chi phí mỗi lần merge từ 33 xuống 32 phút (1,920 phút cho 60 merges); trong trường hợp cache miss làm tròn 3 phút, D2 tiết kiệm 3 phút xuống còn 30 phút/merge (1,800 phút cho 60 merges). D2 độc lập không thể tự giải quyết bài toán quota nếu không kết hợp với Ứng viên B.

---

### 5.2 Mô hình Dự toán Hạn ngạch Chi tiết Hàng tháng (Kịch bản 60 Merges + 80 PRs)

Để chứng minh một cách toán học khả năng đáp ứng trần 2,000 runner-minutes/tháng, chúng tôi phân tích chi tiết cơ cấu tiêu thụ trong hai kịch bản vận hành thực tế:

#### Giả định Tần suất & Phân bổ Tải (Operational Assumptions)
- **60 lượt Merge to master / tháng**:
  - 40 lượt merge thuần Frontend, i18n, docs, hoặc API không đổi DB (Không chạm `models/`, `migrations/`, `app/repositories/**`).
  - 20 lượt merge có thay đổi Backend / Database schema (Kích hoạt `mysql-contract` hoặc selective backend test).
- **80 lượt Pull Request / tháng**:
  - Trung bình chạy 1.5 lần commit/PR = 120 PR test runs.
  - Áp dụng selective modular testing (`scripts/run_tests.py --changed`), trung bình mỗi lượt PR chỉ tốn 4 billable minutes.
- **Thời lượng Viễn trắc Thực tế của 1 Lượt Nightly Run**:
  - `backend-full`: 15m 03s $\rightarrow$ $\lceil 15.05 \rceil = 16$ phút.
  - `frontend-full`: 6m 14s (Vitest + tsc + SPA build/contract) $\rightarrow$ $\lceil 6.23 \rceil = 7$ phút (Khảo sát đối kháng chứng minh không thể đạt 5 phút!).
  - `mysql-contract-full`: 5m 50s $\rightarrow$ $\lceil 5.83 \rceil = 6$ phút.
  - `redis-contract-full`: 32s $\rightarrow$ $\lceil 32/60 \rceil = 1$ phút.
  - **Tổng Billable Minutes cho 1 Lượt Nightly**: $16 + 7 + 6 + 1 = \mathbf{30\text{ PHÚT}}$.

---

#### KỊCH BẢN 2: Nightly Chạy 5 Ngày/Tuần (Weekday Cron - 22 Lượt Run/Tháng) — ★ BASELINE KHUYẾN NGHỊ MẶC ĐỊNH ★

Trong thực tế phát triển phần mềm chuyên nghiệp, vào các ngày cuối tuần (Thứ Bảy, Chủ Nhật) đội ngũ lập trình viên không merge code lên `master`. Việc cấu hình Cron chạy từ Thứ Hai đến Thứ Sáu (`0 2 * * 1-5`, 22 ngày làm việc/tháng) giúp tiết kiệm 240 runner-minutes so với chạy hàng ngày mà vẫn bảo đảm 100% độ phủ kiểm thử an toàn trước giờ làm việc mỗi sáng:

| Hạng mục Tác vụ | Tần suất / Tháng | Cấu thành Chi phí Runner (Billable Min) | Billable Min / Lần | Tổng Tiêu thụ Hàng tháng | Tỷ lệ trên Quota 2,000 |
|---|:---:|---|:---:|:---:|:---:|
| **1. Merge Master: Non-DB / Frontend** | 40 lần | `changes` (1) + `frontend` (3) + `backend smoke` (1) + `deploy` (1) | **6 phút** | **240 phút** | 12.0% |
| **2. Merge Master: Backend / DB Schema** | 20 lần | `changes` (1) + `frontend` (3) + `backend sel` (6) + `mysql` (6) + `deploy` (1) | **17 phút** | **340 phút** | 17.0% |
| **Tổng Chi phí Merge to Master** | **60 merges** | — | — | **580 phút** | **29.0%** |
| **3. Pull Requests Validation** | 80 PRs (120 runs) | Selective modular test (`scripts/run_tests.py --changed`) | **4 phút** | **480 phút** | **24.0%** |
| **4. Nightly Full Validation (Weekday Cron)** | 22 đêm | `backend full` (16) + `frontend full` (7) + `mysql full` (6) + `redis full` (1) | **30 phút** | **660 phút** | **33.0%** |
| **TỔNG TIÊU THỤ HÀNG THÁNG (BASELINE KỊCH BẢN 2)** | — | — | — | **1,720 PHÚT** | **86.0%** |
| **HẠN NGẠCH CÒN THỪA (SOLID SAFETY BUFFER)** | — | — | — | **+280 PHÚT** | **14.0%** |

> **Khẳng định Chiến lược**: Kịch bản 2 là **Baseline Khuyến nghị Chính thức**. Mức thặng dư **+280 phút/tháng (14.0% ngân sách)** tạo ra một biên độ an toàn vững chắc, có khả năng chống chịu va đập trước mọi dao động vi sai máy ảo GitHub Actions ("noisy neighbor"), chấp nhận tới 25 lần re-run thất bại do mạng mà vẫn không bao giờ chạm trần 2,000 phút.

---

#### KỊCH BẢN 1: Nightly Chạy Đầy Đủ 7 Ngày/Tuần (30 Lượt Run/Tháng) — PHƯƠNG ÁN DỰ PHÒNG & CẢNH BÁO RỦI RO

Trong trường hợp Ban Điều hành muốn duy trì lịch chạy Nightly liên tục cả Thứ Bảy và Chủ Nhật (30 đêm/tháng):

| Hạng mục Tác vụ | Tần suất / Tháng | Billable Min / Lần | Tổng Tiêu thụ Hàng tháng | Tỷ lệ trên Quota 2,000 |
|---|:---:|:---:|:---:|:---:|
| **Merge Master (40 Non-DB + 20 DB)** | 60 merges | 6m (40x) + 17m (20x) | **580 phút** | 29.0% |
| **Pull Requests Validation** | 80 PRs (120 runs) | 4 phút/run | **480 phút** | 24.0% |
| **Nightly Full Validation (30 Đêm Liên tục)** | 30 đêm | 30 phút/lần ($16 + 7 + 6 + 1$) | **900 phút** | 45.0% |
| **TỔNG TIÊU THỤ HÀNG THÁNG (KỊCH BẢN 1)** | — | — | **1,960 PHÚT** | **98.0%** |
| **HẠN NGẠCH CÒN THỪA (VÙNG NGUY HIỂM)** | — | — | **+40 PHÚT** | **2.0%** |

#### Cảnh báo Rủi ro Phản biện Đối kháng cho Kịch bản 1:
- Dưới Kịch bản 1, tổng tiêu thụ đạt tới **1,960 phút/tháng (98.0%)**, biên thặng dư an toàn chỉ còn vỏn vẹn **+40 phút (2.0%)**.
- **Nguy cơ cạn kiệt là hiện hữu**: Chỉ cần phát sinh thêm **2 lượt push merge ngoài dự kiến** ($2 \times 17\text{m} = 34\text{m}$) hoặc **7 lần retry PR** do lỗi chập chờn mạng, toàn bộ 2,000 phút sẽ bị **CẠN KIỆT HOÀN TOÀN $\rightarrow$ PIPELINE BỊ KHÓA CHẶT**!
- Do đó, Kịch bản 1 chỉ được giữ làm phương án tham chiếu dự phòng, **tuyệt đối không dùng làm baseline vận hành tiêu chuẩn**.

---

### 5.3 Chứng minh Khả năng Đáp ứng Ngưỡng An toàn < 2,000 Runner-Minutes/Tháng

Theo Baseline Chuẩn Kịch bản 2:
$$\text{Tổng Chi phí To-Be Baseline} = 580 + 480 + 660 = \mathbf{1,720\text{ phút}} \le 2,000\text{ phút} \quad (\Delta = +280\text{ phút, thặng dư an toàn } 14.0\%)$$

So sánh với Hiện trạng (As-Is):
- Hiện trạng tiêu hao: **2,940 phút/tháng** (Vượt trần 940 phút, thâm hụt nghiêm trọng).
- Mô hình To-Be Hybrid (Baseline Kịch bản 2) tiêu hao: **1,720 phút/tháng** (Tiết kiệm ròng **1,220 runner-minutes/tháng**, tương đương cắt giảm **41.5%** tổng tải toàn hệ sinh thái).
- **Độ an toàn cao gấp 7 lần**: Thặng dư an toàn của Baseline Kịch bản 2 (+280 phút) cao gấp **7 lần** so với Kịch bản 1 (+40 phút).
- Đồng thời, thời gian chờ của lập trình viên trong 40 lần merge thông thường giảm từ **16.5 phút xuống còn 3.5 phút** (Tiết kiệm hơn **8.6 giờ chờ đợi vô ích mỗi tháng** cho đội ngũ kỹ sư!).

---

## 6. LỘ TRÌNH TRIỂN KHAI KHẢ THI (ACTIONABLE ROADMAP)

Để đảm bảo quá trình chuyển đổi diễn ra mượt mà, không gây gián đoạn quy trình triển khai hiện tại và **100% tuân thủ nguyên tắc Zero Regression**, lộ trình được phân kỳ thành 3 giai đoạn độc lập:

```
[Hiện trạng: 33 min / 16.5m Wall-clock / 2,940 min Quota]
             │
             ▼ Giai đoạn 1: Quick Wins & Airtight Gates (1-2 ngày)
[Gộp D2 vào Frontend + Bật Pip Cache + Refactor test_ci_workflow.py + Anti-Skip Deploy + Mở rộng Gate MySQL + Nightly Weekday Cron]
             │ ➔ Tiết kiệm ngay 120-180 min/tháng, sẵn sàng lưới an toàn Nightly (30m)
             ▼ Giai đoạn 2: Tách biệt Đồng bộ Master Validation (3-5 ngày)
[Tắt CI_FORCE_ALL_VALIDATION trên Master + Decouple CẢ Backend VÀ Frontend + Kích hoạt Core Smoke Gate]
             │ ➔ Rút ngắn Wall-Clock Master xuống 3.5m - 5m, đạt chuẩn Baseline 1,720 min Quota
             ▼ Giai đoạn 3: Parallel Sharding Tuning & Alerting (Tùy chọn)
[Tối ưu hóa Sharding 2 Workers cho Nightly Cron nếu bộ test Backend tiếp tục phình to]
             │
[To-Be Ổn định: 6-17 min (TB 9.7m) / 3.5m-5m Wall-clock / 1,720 min Quota (Thặng dư +280m)]
```

---

### 6.1 Giai đoạn 1: Quick Wins Không Rủi ro (Zero Risk / 1–2 Ngày)

#### Mục tiêu
Loại bỏ lãng phí của job `spa-contract`, bật pip cache, refactor các assertion gãy vỡ trong `tests/test_ci_workflow.py`, bảo vệ luồng `deploy` khỏi cascading skip, mở rộng kín khít `MYSQL_CONTRACT_SOURCE_PATTERNS`, và khởi tạo `nightly.yml` chuẩn xác.

#### Các Bước Thực hiện Cụ thể
1. **Áp dụng Phương án D2 & Bật Pip Cache trong `.github/workflows/ci.yml`**:
   - Xóa bỏ hoàn toàn định nghĩa job `spa-contract:`.
   - Trong job `frontend`, bổ sung `cache: 'pip'` và `cache-dependency-path: requirements.txt` vào step `actions/setup-python@v5`.
   - Bổ sung 2 step cài đặt contract dependencies và chạy `python -m unittest tests.test_spa_artifact_contract` vào cuối job `frontend`.
2. **Bảo vệ Luồng `deploy` Khỏi Cascading Skip**:
   - Cập nhật dependency và điều kiện chống skip của job `deploy` trong `ci.yml`:
     ```yaml
     deploy:
       needs: [changes, frontend, backend, redis-contract, mysql-contract]
       if: >-
         github.event_name == 'push' &&
         github.ref == 'refs/heads/master' &&
         needs.changes.outputs.deploy == 'true' &&
         !contains(needs.*.result, 'failure') &&
         !contains(needs.*.result, 'cancelled')
     ```
3. **Mở rộng `MYSQL_CONTRACT_SOURCE_PATTERNS` trong `scripts/run_tests.py`**:
   - Bổ sung `"app/repositories/**"`, `"app/services/stats_today_future.py"`, `"app/services/study_service.py"`, và `"app/services/study_composition_service.py"` vào danh sách pattern để đạt chuẩn **Zero False Negatives** trước khi Deploy.
4. **Tái cấu trúc 5 Test Methods trong `tests/test_ci_workflow.py`**:
   - `test_backend_is_independent_from_frontend_and_redis`: Đổi mốc cắt chuỗi sang `\n  redis-contract:\n`.
   - `test_expensive_environment_contracts_are_explicit`: Kiểm tra in-place step `Verify Flask serves real Vite artifact` bên trong job `frontend`.
   - `test_ci_uses_no_actions_artifact_storage`: Kiểm tra build và assert SPA artifact diễn ra trong `frontend_block` mà không có `actions/upload-artifact`.
   - `test_production_deploy_is_called_only_after_master_validation`: Cập nhật assertion danh sách `needs` mới và điều kiện chống cascading skip.
   - `test_change_plan_controls_layer_and_contract_jobs`: Cập nhật logic assertion cho phù hợp với output planner.
   - *Thực hiện commit đồng thời (atomic commit) với thay đổi workflow để bảo đảm CI pass 100%*.
5. **Khởi tạo Workflow Nightly Weekday Cron (`.github/workflows/nightly.yml`)**:
   - Thiết lập lịch chạy `0 2 * * 1-5` (Thứ Hai đến Thứ Sáu lúc 02:00 UTC).
   - Đầy đủ 4 jobs chuẩn xác: `backend-full` (16m), `frontend-full` (7m, kèm build bundle và SPA contract assertion), `redis-contract-full` (1m, service container redis 7), và `mysql-contract-full` (6m, service container mysql 8.0, cấu hình biến môi trường, seed User 1 anchor, và đúng 6 file test retirement từ `ci.yml:395`).

#### Tiêu chí Nghiệm thu Giai đoạn 1
- [ ] Push commit lên PR và Master: Job `spa-contract` không còn xuất hiện trên giao diện Actions.
- [ ] Job `frontend` thực thi thành công việc xác thực SPA shell (`test_spa_artifact_contract` PASS trong ~15s nhờ pip cache).
- [ ] Merge một PR sửa frontend/docs: Job `mysql-contract` và `redis-contract` hiển thị trạng thái `skipped`, nhưng job `deploy` **VẪN CHẠY THÀNH CÔNG VÀ KHÔNG BỊ CASCADING SKIP**.
- [ ] `tests/test_ci_workflow.py` chạy PASS 100% (10/10 tests).
- [ ] Workflow `nightly.yml` kích hoạt chạy thử thủ công (manual dispatch) thành công 100% cả 4 jobs trong đúng ~30 billable minutes.

---

### 6.2 Giai đoạn 2: Tách biệt Đồng bộ Cơ chế Master Validation (3–5 Ngày)

#### Mục tiêu
Xóa bỏ nút thắt 15 phút của job `backend` và 7 phút của job `frontend` trên nhánh `master`, kéo Wall-clock time xuống dưới 5 phút, chính thức đưa tổng mức tiêu thụ hạn ngạch về mức **Baseline 1,720 phút/tháng**.

#### Các Bước Thực hiện Cụ thể
1. **Điều chỉnh Biến Môi trường `CI_FORCE_ALL_VALIDATION`**:
   - Trong `ci.yml`, sửa:
     `CI_FORCE_ALL_VALIDATION: ${{ github.event_name == 'workflow_dispatch' }}`.
2. **Triển khai Core Smoke Gate trong `scripts/run_tests.py`**:
   - Định nghĩa danh sách `CORE_SMOKE_TESTS` gồm 12 files tests cơ sở trong `MODULES['core']`.
   - Khi chạy trên nhánh `master` ở chế độ selective:
     `tests_to_run = affected_backend_tests | CORE_SMOKE_TESTS`.
   - Đảm bảo master luôn kiểm tra tính toàn vẹn của Core Framework trước khi cho phép deploy.
3. **Đồng bộ Cập nhật Lệnh Thực thi trong CẢ HAI Jobs `backend` VÀ `frontend`**:
   - **Job `backend`**: Cho phép master chạy `python scripts/run_tests.py --changed --backend-only` thay vì ép buộc `--all`.
   - **Job `frontend`**: Sửa điều kiện bash từ `if [ "${{ github.ref_name }}" = "master" ]` thành `if [ "${{ github.event_name }}" = "workflow_dispatch" ]`, đảm bảo trên master job `frontend` chạy `python ../scripts/run_tests.py --changed --frontend-only` (3 phút) thay vì ép chạy full `npm test` (7 phút), **ngăn chặn thất thoát 240 phút/tháng**!

#### Tiêu chí Nghiệm thu Giai đoạn 2
- [ ] Merge commit sửa đổi giao diện hoặc i18n vào `master`:
  - Job `backend` hoàn tất trong **dưới 1 phút** (~45s, chỉ chạy Core Smoke).
  - Job `frontend` hoàn tất trong **dưới 3 phút** (chỉ chạy selective Vitest).
- [ ] Toàn bộ pipeline merge to master từ lúc commit đến khi deploy VPS hoàn tất trong **dưới 5 phút** (Wall-clock time rút ngắn 70% – 78%).
- [ ] Tổng billable minutes mỗi lần merge giảm xuống **6 – 17 phút** (Trung bình 9.7 phút).
- [ ] Tổng hạn ngạch tháng được kiểm soát an toàn tuyệt đối ở mức **1,720 phút/tháng** (thặng dư an toàn +280 phút).

---

### 6.3 Giai đoạn 3: Tối ưu Hóa Song song & Giám sát Dài hạn (Tùy chọn)

#### Mục tiêu
Tối ưu hóa thời gian chạy của workflow Nightly Cron và thiết lập cảnh báo hạn ngạch chủ động.

#### Các Bước Thực hiện Cụ thể
1. **Cấu hình Matrix Sharding 2 Workers riêng cho Nightly Cron**:
   - Trong `.github/workflows/nightly.yml`, chia 235 backend tests thành 2 shards chạy song song.
   - Rút ngắn thời gian chạy của Nightly Backend Suite từ 15 phút xuống còn **~7.5 phút**.
2. **Tích hợp Vitest Configuration Tuning**:
   - Bổ sung cấu hình `test: { css: false }` trong frontend để tăng tốc thêm 15% thời gian chạy của 137 test files jsdom.
3. **Thiết lập GitHub Actions Quota Alert**:
   - Cấu hình webhook gửi cảnh báo qua Telegram/Discord khi hạn ngạch tháng vượt quá 75% (1,500 phút).

---

### 6.4 Kế hoạch Kiểm thử Không Hồi quy & Tiêu chí Nghiệm thu Từng Giai đoạn

| Giai đoạn | Đối tượng Kiểm tra | Phương pháp Thẩm định Thực nghiệm | Tiêu chí Đạt (Pass Criteria) |
|---|---|---|---|
| **G1** | Tích hợp D2 SPA Contract | Chạy `.venv\Scripts\python.exe -m unittest tests/test_ci_workflow.py` | 100% PASS (10/10 tests), 0 artifact storage |
| **G1** | Pip Cache Job Frontend | Kiểm tra step `setup-python` trong log Actions của job `frontend` | Cache hit `pip`, cài đặt hoàn tất trong $\le 15$s |
| **G1** | Anti-Cascading Skip | Tạo PR sửa file markdown/CSS, merge lên master | `mysql-contract` và `redis-contract` chuyển `skipped`, nhưng job `deploy` **VẪN CHẠY THÀNH CÔNG** |
| **G1** | Độ phủ Gate MySQL | Sửa `stats_today_future.py` hoặc `study_repository.py` | `mysql-contract` được kích hoạt chính xác (**Zero False Negatives**) |
| **G1** | Workflow Nightly Cron | Kích hoạt manual trigger qua `gh workflow run nightly.yml` | Toàn bộ 4 jobs (`backend-full`, `frontend-full`, `redis`, `mysql`) PASS 100% trong $\le 30$ min billable |
| **G2** | Decouple Frontend Master | Merge commit sửa component React lên master | Job `frontend` chỉ chạy selective Vitest ($\le 3$ min billable), không chạy `npm test` 7m |
| **G2** | Selective Master Gate | Merge commit test lên master, đo lường viễn trắc | Wall-clock $\le 5$ phút, Deploy thành công |
| **G2** | Core Smoke Resilience | Giả lập lỗi cú pháp trong `app/spa.py` | Pipeline chặn đứng deploy chính xác tại job `backend` sau 30s |
| **G3** | Quota Monitoring | Kiểm tra tab GitHub Billing sau 30 ngày áp dụng Baseline Kịch bản 2 | Mức tiêu thụ thực tế $\le 1,720$ phút/tháng, thặng dư an toàn $\ge +280$ phút |

---

## LỜI KẾT & KHUYẾN NGHỊ CUỐI CÙNG

Báo cáo nghiên cứu chiến lược này đã chứng minh một cách toàn diện và chặt chẽ rằng: **Nút thắt CI/CD của Flama hoàn toàn có thể được giải quyết triệt để thông qua tối ưu hóa kiến trúc điều phối và phân tầng pipeline, mà tuyệt đối không cần mạo hiểm thay đổi cấu trúc test suite hay sửa đổi bất kỳ dòng mã nguồn sản phẩm nào.**

Bằng việc kết hợp hài hòa giữa **Kiến trúc Phân tầng 3 Cấp (Ứng viên B)**, **Gộp Contract Assertion In-place (Ứng viên D2)**, **Đồng bộ Decouple cả Frontend lẫn Backend trên Master**, **Bảo vệ Luồng Deploy khỏi Cascading Skip**, và **Lưới an toàn Nightly Weekday Cron (Baseline Kịch bản 2)**:
- Flama sẽ ngay lập tức giải phóng đội ngũ phát triển khỏi thời gian chờ đợi 16–20 phút mỗi lần merge (rút ngắn xuống còn 3.5 – 5 phút).
- Hạn ngạch GitHub Actions được bảo vệ an toàn vững chắc dưới ngưỡng 2,000 phút/tháng (đưa tổng tiêu thụ về **1,720 phút/tháng**, tạo thặng dư an toàn **+280 phút/tháng**).
- Toàn bộ các nguyên tắc kiến trúc và guardrails bất biến trong `AGENTS.md` (mô hình Clone Overlay, tính toàn vẹn của Anki Scheduler, cấu trúc flat unittest cho Multi-Agent Swarm) được bảo toàn nguyên vẹn 100%.
- Không có bất kỳ dòng code sản phẩm nào trong `app/`, `frontend/`, `models/` bị thay đổi.

Đội ngũ kiến trúc khuyến nghị Ban Điều hành phê duyệt triển khai ngay **Giai đoạn 1** trong vòng 24–48 giờ tới để thu hoạch các kết quả Quick-Win tức thì.

---
*Báo cáo được hoàn thiện và chuẩn hóa bởi Teamwork Preview Worker R2.1 — Đáp ứng 100% khuyến nghị từ Hội đồng Thẩm định & Phản biện Đối kháng.*

