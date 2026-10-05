# BÁO CÁO KIỂM KÊ BASELINE VÀ BẢN ĐỒ MAPPING KIẾN TRÚC 6 TẦNG FSD (GÓI G00)
## Master Engineering Specification & Baseline Characterization for Flama React SPA Migration

- **Mã tài liệu**: `FLAMA-DOC-2026-FE-G00`
- **Phiên bản**: 2.0 (Cập nhật nghiệm thu Gate C00)
- **Tác giả tổng hợp**: Worker G00 Updater (`worker_g00_updater`) & Worker 1 (`teamwork_preview_worker_g00_1`)
- **Nguồn khảo sát thực tế**:
  - Explorer 1: Báo cáo Kỹ thuật Toàn diện Khảo sát Codebase & Gỡ bỏ 8 Findings Codex (`explorer_survey_1`)
  - Codex Review Report: `docs/task/frontend-migration/G00_CODEX_REVIEW_2026-10-04.md`
  - Codex Renderer Review: `docs/task/frontend-migration/FLASHCARD_EXTRACTION_CODEX_REVIEW_2026-10-05.md`
  - Explorer 1, 2, 3: Báo cáo Baseline, Catalog FSD và Runtime Contracts ban đầu
- **Tài liệu tham chiếu**:
  - `docs/plans/proposals/FLAMA_FRONTEND_CODEX_GEMINI_EXECUTION_PLAN_2026-10-04.md`
  - `docs/plans/proposals/FLAMA_FRONTEND_STRUCTURE_MIGRATION_PLAN_2026-10-03.md`
  - `skills/flama-frontend-architecture/SKILL.md`
  - `AGENTS.md`
- **Ngày phát hành ban đầu**: 2026-10-04 (Asia/Tokyo)
- **Ngày cập nhật hoàn tất**: 2026-10-05 (Asia/Tokyo)
- **Trạng thái**: **Updated for Gate C00 Acceptance** (Đã cập nhật toàn diện giải quyết dứt điểm 8 findings R1–R8 từ Codex Review `G00_CODEX_REVIEW_2026-10-04.md`; sẵn sàng để Codex thẩm định lại và phê duyệt chính thức mở Gate C00).

---

## MỤC LỤC TỔNG QUAN

1. [PHẦN 1: GIT STATUS / CHECKPOINT VÀ CÁC THAY ĐỔI CẦN BẢO VỆ](#phần-1-git-status--checkpoint-và-các-thay-đổi-cần-bảo-vệ)
   - 1.1 Thông tin Nhánh và HEAD Commit Checkpoint
   - 1.2 Snapshot Chi tiết Thay đổi của Agent P10 (Backend/Database)
   - 1.3 Xác nhận Trạng thái Cách ly Tuyệt đối của Thư mục Frontend
   - 1.4 Kỷ luật An toàn Git Bất biến
2. [PHẦN 2: BẢNG KIỂM KÊ 22 FEATURE, THƯ MỤC DÙNG CHUNG, FILE QUÁ KHỔ VÀ PHỤ THUỘC CHÉO](#phần-2-bảng-kiểm-kê-22-feature-thư-mục-dùng-chung-file-quá-khổ-và-phụ-thuộc-chéo)
   - 2.1 Tổng quan Định lượng Toàn bộ Codebase
   - 2.2 Bảng Kiểm kê Chi tiết 22 Thư mục Feature (`frontend/src/features/`)
   - 2.3 Bảng Kiểm kê Các Thư mục Dùng chung Ngoài Features
   - 2.4 Phân tích Chi tiết 17 Tệp Quá khổ (> 1.000 Dòng)
   - 2.5 Phụ thuộc Chéo giữa các Feature, Vòng lặp Hai chiều và 5 Type SCCs
   - 2.6 Vi phạm Phân tầng Kiến trúc (Layer Boundary Inversions)
3. [PHẦN 3: BẢNG MAPPING SOURCE -> TARGET 6 TẦNG FSD CHI TIẾT](#phần-3-bảng-mapping-source---target-6-tầng-fsd-chi-tiết)
   - 3.1 Khung Kiến trúc 6 Tầng Chuẩn FSD và Quy tắc Đơn hướng
   - 3.2 Bảng Phân bổ Định lượng 414 Tệp theo 6 Tầng Target
   - 3.3 Ma trận Chuyển đổi Chi tiết 22 Feature và Thành phần Chung
   - 3.4 Chiến lược Tháo gỡ 5 Điểm nghẽn Kiến trúc và Vòng lặp Trọng yếu
   - 3.5 Đặc tả Mã nguồn Public API Export (`index.ts`)
4. [PHẦN 4: DANH MỤC RUNTIME CONTRACTS BẮT BUỘC BẢO TOÀN](#phần-4-danh-mục-runtime-contracts-bắt-buộc-bảo-toàn)
   - 4.1 Bảng Phân cấp Định tuyến (Routes), Parameters và Query Strings
   - 4.2 Cơ chế Kiểm soát Quyền (Access Guards & Availability Redirect)
   - 4.3 Ma trận TanStack Query Keys, Cache Identity và Phân tích Dual Bootstrap
   - 4.4 Danh mục Client Storage & Hợp đồng Kênh Truyền thông Trình duyệt (LocalStorage, SessionStorage, IndexedDB, BroadcastChannel, Cookie)
   - 4.5 Hợp đồng Web Worker, Đồng bộ Anki và Dịch vụ Đồng hành Ngoại vi
5. [PHẦN 5: HIỆN TRẠNG TEST BASELINE VÀ KHOẢNG TRỐNG KIỂM THỬ (TEST GAPS)](#phần-5-hiện-trạng-test-baseline-và-khoảng-trống-kiểm-thử-test-gaps)
   - 5.1 Kết quả Thực thi Bộ Lệnh Chất lượng Baseline
   - 5.2 Phân loại và Đánh giá 37 Cảnh báo Linter Hiện hữu
   - 5.3 Định danh Khoảng trống Kiểm thử (Test Gaps) trên 9 Feature Chưa có Test
   - 5.4 Yêu cầu Bộ Kiểm thử Đặc tả Hành vi & Tiêu chuẩn Visual Chống Hồi quy
6. [PHẦN 6: ĐỀ XUẤT PHẠM VI CHI TIẾT CHO GÓI G01 (SHARED PRIMITIVES & UTILITIES)](#phần-6-đề-xuất-phạm-vi-chi-tiết-cho-gói-g01-shared-primitives--utilities)
   - 6.1 Mục tiêu và Ranh giới Kỹ thuật Gói G01 (Phân tách G01.a và G01.b)
   - 6.2 Danh sách Tệp Được phép Chỉnh sửa / Tạo mới (Whitelist G01.a & G01.b)
   - 6.3 Danh sách Tệp và Thư mục Nghiêm cấm Chạm vào (Gate G01 Blacklist)
   - 6.4 Ranh giới Caller Scope và Cơ chế Re-export Shim Bắt buộc (Zero Caller Regression)
   - 6.5 Tiêu chí Nghiệm thu Khắt khe cho Gate G01 (Acceptance Criteria)

---

## PHẦN 1: GIT STATUS / CHECKPOINT VÀ CÁC THAY ĐỔI CẦN BẢO VỆ

### 1.1 Thông tin Nhánh và HEAD Commit Checkpoint
Toàn bộ khảo sát và lập kế hoạch di chuyển kiến trúc frontend Flama SPA được thực hiện và đối chiếu qua các mốc checkpoint:

#### A. Mốc Lịch sử Ban đầu (P10 Baseline - 2026-10-04):
- **Tên nhánh**: `phase10/contraction-drop`
- **HEAD Commit SHA ban đầu**: `8ea41587fdd613272e9edd0dc675277950e5cee6`
- **Hoàn tất P10**: Commit `5b21b1b` (*"feat(phase10): drop the five retired NOTE progress tables (P10-09 PR-B)"*). Toàn bộ 5 tệp staged và 13 tệp unstaged của Agent P10 đã được sáp nhập an toàn vào nhánh.

#### B. Mốc Checkpoint Hiện hành (Frontend FSD Refactor Baseline - 2026-10-05):
- **Tên nhánh hiện tại**: `refactor/frontend-fsd-renderer-boundary`
- **HEAD Commit SHA hiện tại**: `faa3c7d` (*"refactor"*)
- **Tiến độ đã đạt được**: Đã bóc tách thành công gói C02 (`entities/flashcard` và `app/studyContentSync.ts`, 69 tests pass) theo đúng báo cáo `FLASHCARD_EXTRACTION_CODEX_REVIEW_2026-10-05.md`.
- **Hiện trạng working tree**: Thư mục backend, database models, migrations và toàn bộ `frontend/src/` hoàn toàn sạch sẽ (0 modified, 0 staged, 0 untracked source files).
- **Cảnh báo ranh giới (Caveat theo R8)**: Việc working tree hiện tại đang sạch sẽ **KHÔNG đồng nghĩa** với việc rủi ro xung đột được triệt tiêu 100%. Trước khi bắt đầu bất kỳ gói công việc nào (C01, G01.a, G01.b...), agent thực thi bắt buộc phải kiểm tra lại checkpoint SHA và đối chiếu file locks độc quyền.

### 1.2 Snapshot Chi tiết Thay đổi của Agent P10 (Backend/Database)
Tại thời điểm bắt đầu Gói G00, working tree đang ghi nhận chính xác các thay đổi sau thuộc sở hữu độc quyền của Agent P10:

#### A. Staged Changes (5 files xóa bảng cũ - P10 drop retired tables):
```text
deleted:    models/study_authority_subject_token.py
deleted:    models/study_progress_availability.py
deleted:    models/study_progress_contributor.py
deleted:    models/study_progress_lineage_ref.py
deleted:    models/study_progress_state.py
(5 files changed, 424 deletions)
```

#### B. Unstaged Modifications (13 files thay đổi mã nguồn backend, migration và test):
```text
.github/workflows/ci.yml                                             |  9 ++++++
app/__init__.py                                                      |  5 ---
docs/task/decoupling/P10_EXECUTION_PLAN_2026-10-03.md               |  2 +-
migrations/versions/20260913_000039_add_study_progress_shadow_schema.py | 11 ++++---
migrations/versions/20260921_000040_add_study_authority_fence.py     |  3 +-
models/study_progress_history_fact.py                                |  8 ++---
models/study_progress_subject.py                                     | 12 -------
scripts/bench_p9_profile_migration_mysql.py                          |  4 +++
scripts/run_tests.py                                                 |  7 ++++
tests/test_stats_overview.py                                         | 11 -------
tests/test_study_authority_schema.py                                 |  9 ++++--
tests/test_study_note_write_gap_locks.py                             |  5 +--
tests/test_study_storage_profile.py                                  | 37 +++-------------------
(13 files changed, 44 insertions(+), 79 deletions(-))
```

#### C. Untracked Files (7 files tài liệu, migration mới và script probe):
```text
docs/architecture/LOCAL_DECOUPLING_MIGRATION_2026-10-03.md
docs/plans/proposals/FLAMA_FRONTEND_CODEX_GEMINI_EXECUTION_PLAN_2026-10-04.md
docs/plans/proposals/FLAMA_FRONTEND_STRUCTURE_MIGRATION_PLAN_2026-10-03.md
docs/runbooks/P10_09_RETIRED_TABLES_DROP_RUNBOOK.md
migrations/versions/20261003_000050_drop_retired_note_progress_tables.py
scripts/probe_p10_drop_mysql.py
tests/test_study_retired_tables_migration.py
```

### 1.3 Xác nhận Trạng thái Cách ly Tuyệt đối của Thư mục Frontend
- **Kết quả đối chiếu working tree**: Không có bất kỳ tệp nào nằm trong `frontend/` xuất hiện trong danh sách staged, unstaged modified hay untracked của git status (ngoại trừ các bundle tạm sinh trong `frontend/dist/` do chạy lệnh `npm run build` kiểm tra chất lượng).
- **Trạng thái working tree của `frontend/src/`**: **100% SẠCH SẼ (CLEAN & UNTOUCHED)**.

### 1.4 Kỷ luật An toàn Git Bất biến
Trong suốt quá trình thực thi Gói G00 và toàn bộ các gói tiếp theo của chiến dịch tái cấu trúc frontend:
1. **TUYỆT ĐỐI KHÔNG tự ý `git checkout` chuyển nhánh**: Giữ vững vị trí làm việc tại nhánh hiện tại để không gây xung đột working tree với Agent P10.
2. **TUYỆT ĐỐI KHÔNG chạm vào các thay đổi của Agent P10**: Không revert, không restore, không stash, không checkout đè lên các file backend, models, migrations hoặc test backend.
3. **TUYỆT ĐỐI KHÔNG chạy các lệnh đột biến git**: Không chạy `git commit`, `git add`, `git reset`, `git restore` hay `git push`. Không commit bất kỳ tệp nào cho đến khi toàn bộ kế hoạch kiểm thử và nghiệm thu được phê duyệt chính thức.
4. **Phạm vi tác động của Gói G00**: Duy nhất tạo mới và cập nhật tệp tài liệu `docs/task/frontend-migration/G00_BASELINE_AND_MAPPING.md`. Tuyệt đối không chỉnh sửa source code hoặc file cấu hình nào trong repo.

---

## PHẦN 2: BẢNG KIỂM KÊ 22 FEATURE, THƯ MỤC DÙNG CHUNG, FILE QUÁ KHỔ VÀ PHỤ THUỘC CHÉO

### 2.1 Tổng quan Định lượng Toàn bộ Codebase
Khảo sát quét mã tĩnh bằng AST Parser trên toàn bộ thư mục `frontend/src/` xác lập số liệu baseline chính thức:
- **Tổng số tệp TypeScript / TSX**: **413 tệp**
  - **Tệp Source TS/TSX**: **331 tệp** (Tổng: **96.154 dòng code - LOC**)
  - **Tệp Test TS/TSX**: **82 tệp** (Tổng: **20.763 dòng code - LOC**)
  *(Quy chuẩn phân loại test: Có đuôi `.test.ts`, `.test.tsx`, `.spec.ts`, `.spec.tsx` hoặc nằm trong thư mục `__tests__`)*
- **Tổng dung lượng dòng code TS/TSX**: **116.917 LOC**
- **Số lượng miền chức năng (Features)**: **22 thư mục**

### 2.2 Bảng Kiểm kê Chi tiết 22 Thư mục Feature (`frontend/src/features/`)

| STT | Feature Domain | Source Files | Source LOC | Test Files | Test LOC | Total TS/TSX | Mục đích Nghiệp vụ Cốt lõi |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | `admin` | 22 | 9.231 | 1 | 783 | 23 | Quản trị toàn sàn: người dùng, phân quyền, cấu hình phí creator, quản lý đơn hàng PayOS, thư viện ảnh, quản lý MCP tokens, vé hỗ trợ và quản trị taxonomy JLPT/chủ đề. |
| 2 | `audio` | 16 | 4.824 | 3 | 338 | 19 | Hệ thống tạo và đồng bộ âm thanh TTS từ Flama Audio Desktop (.NET 8 VoiceVox/Kokoro), hàng đợi sinh âm thanh, quét audio thiếu và chuẩn hóa text tiếng Nhật. |
| 3 | `auth` | 12 | 1.540 | 0 | 0 | 12 | Xác thực người dùng: Đăng nhập, đăng ký, quên/đặt lại mật khẩu, xác thực email, access guards (`RequireAuth`, `RequireCreator`). |
| 4 | `browse` | 14 | 5.257 | 9 | 1.214 | 23 | Không gian tra cứu và quản lý flashcard: Bảng dữ liệu thẻ, lọc/tìm kiếm đa tiêu chí, gán tag, di chuyển deck, sửa thẻ inline, Kanji stroke modal và preview media. |
| 5 | `dashboard` | 12 | 1.723 | 4 | 683 | 16 | Bảng điều khiển trang chủ học tập: Cây thư mục deck kéo thả, số lượng thẻ due/learn/new, heatmap học tập theo năm, modal thao tác deck (tạo/đổi tên/xóa/xuất). |
| 6 | `deck-collaboration` | 9 | 3.892 | 4 | 789 | 13 | Cộng tác phát triển bộ thẻ: Không gian giải quyết xung đột 3-way merge diff, gửi đề xuất thay đổi (Deck Change Request), hòm thư duyệt và release builder. |
| 7 | `guide` | 13 | 3.749 | 0 | 0 | 13 | Trung tâm tài liệu và hướng dẫn học tập: Kho dữ liệu markdown in-memory, hướng dẫn tương tác MCP/Yomitan, nút trợ giúp ngữ cảnh (`ContextHelpButton`). |
| 8 | `import` | 17 | 5.243 | 2 | 200 | 19 | Nhập liệu học tập: Kết nối đồng bộ AnkiConnect Yomitan bridge, wizard nhập file CSV/TSV/APKG, ánh xạ trường (field mapping) và cây chọn deck. |
| 9 | `library` | 1 | 941 | 0 | 0 | 1 | Thư viện cá nhân: Quản lý danh sách các bộ thẻ đã cài đặt từ Marketplace, kiểm tra và cập nhật các bản phát hành mới. |
| 10 | `marketplace` | 20 | 9.464 | 4 | 468 | 24 | Chợ chia sẻ bộ thẻ & note type: Catalog danh mục, chi tiết deck, preview mẫu thẻ sandbox, thanh toán PayOS, quản lý license key và wizard xuất bản sàn. |
| 11 | `mcp` | 9 | 1.733 | 3 | 1.844 | 12 | Quản lý token Model Context Protocol (AI Integration): Tạo/sửa token, gán scope presets (read, write, tools), thu hồi/xóa vĩnh viễn, modal hiển thị secret key. |
| 12 | `note-types` | 8 | 2.662 | 0 | 0 | 8 | Quản lý cấu trúc mẫu thẻ (Note Type): Thiết lập danh sách trường dữ liệu, trình soạn thảo template Front/Back (HTML/CSS), live preview thẻ trong sandbox. |
| 13 | `oauth` | 2 | 422 | 0 | 0 | 2 | Giao diện cấp quyền ủy quyền OAuth2 Consent cho ứng dụng bên thứ ba truy cập tài khoản Flama. |
| 14 | `onboarding` | 7 | 1.577 | 1 | 301 | 8 | Quy trình chào mừng người dùng mới: Thiết lập mục tiêu học tập (JLPT, số thẻ/ngày), Spotlight Tour hướng dẫn trên giao diện dashboard. |
| 15 | `orders` | 1 | 280 | 0 | 0 | 1 | Lịch sử đơn hàng, biên lai giao dịch và trạng thái thanh toán PayOS của người dùng. |
| 16 | `profile` | 13 | 2.291 | 1 | 171 | 14 | Hồ sơ người dùng: Thay đổi avatar, thông tin cá nhân, xác minh email, thống kê huy hiệu đạt được, đóng góp và học liệu đã xuất bản. |
| 17 | `settings` | 10 | 3.260 | 3 | 1.239 | 13 | Cài đặt ứng dụng: Thiết lập mục tiêu học tập, quản lý token MCP, token Yomitan mining, quản lý client app OAuth. |
| 18 | `statistics` | 5 | 887 | 0 | 0 | 5 | Báo cáo thống kê chuyên sâu: Biểu đồ thẻ đến hạn tương lai (Future Due), thời gian học thực tế theo ngày/tháng, phân tích tỷ lệ duy trì trí nhớ. |
| 19 | `study` | 37 | 11.555 | 27 | 7.866 | 64 | Runtime học tập cốt lõi (Spaced Repetition System): Động cơ SM-2 scheduler, lật thẻ hai mặt mounted, chấm điểm, quản lý phiên học bền vững trên IndexedDB, undo stack, batch commit. |
| 20 | `support` | 5 | 2.767 | 0 | 0 | 5 | Trung tâm hỗ trợ: Gửi yêu cầu/phản hồi đóng góp, theo dõi tiến độ xử lý vé hỗ trợ, trang hướng dẫn cài đặt TTS local và API key. |
| 21 | `wallet` | 6 | 475 | 0 | 0 | 6 | Ví thu nhập creator: Theo dõi số dư bán deck/note type, yêu cầu rút tiền về tài khoản ngân hàng, lịch sử giao dịch ví. |
| 22 | `worksheets` | 13 | 8.017 | 3 | 1.511 | 16 | Studio tạo phiếu bài tập in ấn PDF: Mẫu tập viết Kanji, Genkouyoushi, ô kẻ lưới, từ vựng, câu ví dụ; tùy biến lề/khoảng cách/font và live preview in trực tiếp. |
| **CỘNG** | **22 Features** | **252** | **81.790** | **65** | **19.009** | **317** | **Chiếm 85,1% tổng số dòng code nguồn của toàn bộ SPA.** |

### 2.3 Bảng Kiểm kê Các Thư mục Dùng chung Ngoài Features

| STT | Vị trí / Thư mục | Source Files | Source LOC | Test Files | Test LOC | Total TS/TSX | Mục đích & Chi tiết Thành phần |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | `app/` | 1 | 465 | 0 | 0 | 1 | `app/api.ts`: API Gateway kế thừa tập trung (chứa các hàm gọi axios/fetch bọc quanh REST endpoints, phụ thuộc ngược vào domain types). |
| 2 | `components/` | 36 | 4.104 | 1 | 126 | 37 | Chứa các shell layout component (`app-sidebar.tsx`, `site-footer.tsx`, `site-mascot.tsx`, `nav-main.tsx`, `nav-user.tsx`) và toàn bộ 30 primitives shadcn UI tại `components/ui/`. |
| 3 | `lib/` | 10 | 2.137 | 4 | 425 | 14 | Thư viện cầu nối & tiện ích cốt lõi: Client AnkiConnect, IndexedDB sync adapter, web worker đồng bộ (`sync.worker.ts`), client Flama Audio, nén ảnh client-side, HTML sanitizer. |
| 4 | `shared/` | 21 | 3.682 | 10 | 1.777 | 31 | Thành phần dùng chung đa tầng: `shared/api` (bootstrap, client, backendAvailability), `shared/components`, `shared/types`, và 8 UI primitives tại `shared/ui`. |
| 5 | `pages/` | 4 | 1.752 | 2 | 1.028 | 6 | Các trang độc lập / hệ thống: `LandingPage.tsx`, `NotFoundPage.tsx`, `MaintenancePage.tsx`, `StaticPages.tsx` (Điều khoản sử dụng, chính sách quyền riêng tư). |
| 6 | `layouts/` | 1 | 463 | 0 | 0 | 1 | `AppLayout.tsx`: Khung giao diện chính bao bọc toàn bộ SPA (Header, Sidebar, breadcrumb, theme toggle, mascot, feedback dialog). |
| 7 | `hooks/` | 1 | 19 | 0 | 0 | 1 | `use-mobile.ts`: Hook phát hiện breakpoint màn hình di động dùng chung cho thanh bên. |
| 8 | `config/` | 1 | 55 | 0 | 0 | 1 | `env.ts`: Quản lý biến môi trường runtime và resolve URL backend, Yomitan bridge, MCP server. |
| 9 | `data/` | 1 | 1.000 | 0 | 0 | 1 | `legalDocumentsData.ts`: Dữ liệu văn bản pháp lý tĩnh (Điều khoản dịch vụ, chính sách quyền riêng tư, quy định hoàn tiền, thỏa thuận tác giả). |
| 10 | Root `frontend/src/` | 3 | 687 | 0 | 0 | 3 | Điểm khởi đầu ứng dụng: `App.tsx` (Router chính), `main.tsx` (Bootstrapper React 19), `vite-env.d.ts` (Khai báo types Vite client). |
| **CỘNG** | **Ngoài Features** | **79** | **14.364** | **17** | **1.754** | **96** | **Chứa toàn bộ hạ tầng layout, primitives dùng chung, adapter mạng và router.** |

### 2.4 Phân tích Chi tiết 17 Tệp Quá khổ (> 1.000 Dòng)
Toàn bộ codebase có đúng **17 tệp** có độ dài từ 1.000 dòng code trở lên (gồm **14 tệp source code** và **3 tệp test suite**). Đây là các trọng điểm kỹ thuật cần được phân rã hoặc bảo vệ ranh giới nghiêm ngặt:

| STT | Đường dẫn Tệp | Loại | LOC | Phân loại Kiến trúc | Lý do Quá khổ & Cấu trúc Nội tại |
|:---:|:---|:---:|:---:|:---|:---|
| 1 | `features/worksheets/components/DeckWorksheetModal.tsx` | SRC | **4.387** | Monolithic Modal UI | Gộp toàn bộ wizard 4 bước, canvas studio thiết kế trang in, tùy biến lề/khoảng cách/font, live preview PDF, logic in ấn, lưu preset localStorage. Chứa **22 `useState`** hooks trong 1 component. |
| 2 | `features/worksheets/components/WorksheetPageRenderer.tsx` | SRC | **1.718** | Monolithic Print Renderer | Renderer chung cho 6 mẫu in khác nhau (Kanji compact, Genkouyoushi, Grid, Sentence...). Nhúng trực tiếp cả logic phân tích cú pháp SVG Stroke order (`_parseStaticKanjiSvgClient`). |
| 3 | `features/study/hooks/useStudySession.test.tsx` | TEST | **1.529** | Integration Test Suite | Test suite bao quát toàn diện vòng đời phiên học SRS: lease handling, restore snapshot từ IndexedDB, rating SM-2, undo stack, auto-advance, commit retry batch. |
| 4 | `features/study/hooks/useStudySession.ts` | SRC | **1.463** | Complex Controller Hook | Controller điều phối phiên học SRS: **12 `useState`, 10 `useEffect`, 15 `useCallback`**. Xử lý commit receipt, lease fence, rollback, undo stack, timer đếm giờ, auto TTS, note batching. |
| 5 | `features/marketplace/pages/SharedDeckDetailPage.tsx` | SRC | **1.435** | Monolithic Route Page | Trang chi tiết Marketplace trộn lẫn: Hiển thị thông tin deck, review/đánh giá, mua qua PayOS, cài đặt bản clone overlay, xem trước flashcard bằng `CardDisplay`, lịch sử cập nhật. (4 queries, 6 mutations). |
| 6 | `features/admin/pages/AdminTaxonomyPage.tsx` | SRC | **1.399** | Monolithic Route Page | Quản trị cây phân loại: Danh mục cha, danh mục con, tags, cấp độ JLPT, bộ icon, sắp xếp thứ tự. Chứa **46 `useState`** và **13 `useMutation`** trong một component duy nhất. |
| 7 | `features/admin/pages/AdminPaymentsPage.tsx` | SRC | **1.394** | Monolithic Route Page | Bảng theo dõi giao dịch PayOS, tra cứu đơn hàng, bộ lọc trạng thái, xử lý hoàn tiền, audit log, copy webhook payload. (18 `useState`, 6 `useQuery`). |
| 8 | `features/worksheets/DeckWorksheetModal.test.tsx` | TEST | **1.354** | Integration Test Suite | Test tích hợp modal worksheet: Giả lập wizard chuyển bước, thay đổi mapping trường từ vựng, cập nhật preview in ấn. |
| 9 | `features/settings/components/McpOAuthTab.tsx` | SRC | **1.159** | Monolithic Tab Component | Tab cấu hình OAuth Client app cho MCP: Tạo client mới, quản lý scope ủy quyền, sinh client secret, quản lý redirect URIs, danh sách ứng dụng đã cấp quyền. |
| 10 | `features/marketplace/pages/MarketplacePublishNoteTypePage.tsx` | SRC | **1.157** | Monolithic Route Page | Wizard xuất bản Note Type: Định nghĩa cấu trúc trường, ánh xạ template HTML/CSS, preview trực tiếp, xác thực form, đặt giá bán và metadata. (21 `useState`). |
| 11 | `features/guide/guideData.ts` | SRC | **1.157** | Static Data Repository | Kho dữ liệu tĩnh chứa toàn bộ nội dung markdown của các bài hướng dẫn Flama cùng tiện ích tìm kiếm, phân loại danh mục in-memory. |
| 12 | `features/marketplace/pages/MarketplacePages.tsx` | SRC | **1.151** | Combined Page Module | Chứa cả `SharedDecksPage` và `SharedNoteTypesPage`, thanh lọc theo thể loại/cấp độ, sort, search bar, skeleton grid, pagination. |
| 13 | `features/admin/pages/AdminFeesPage.tsx` | SRC | **1.100** | Monolithic Route Page | Quản lý chính sách phí nền tảng: Tỷ lệ hoa hồng theo role creator, lịch sử trả tiền payout, bảng tra cứu yêu cầu rút tiền. (13 `useState`, 4 `useMutation`). |
| 14 | `features/audio/hooks/useLocalAudioEngine.ts` | SRC | **1.079** | Complex Controller Hook | Engine tạo giọng đọc cục bộ qua Flama Audio: **23 `useState`, 12 `useEffect`, 7 `useCallback`**. Điều khiển ghép nối token, quét danh sách giọng Kokoro/VoiceVox, xử lý batching, lưu âm thanh vào thẻ. |
| 15 | `features/browse/hooks/useBrowseState.ts` | SRC | **1.052** | Complex Controller Hook | Hook trung tâm của Browse: **49 `useState`**, 9 `useQuery`, 6 `useMutation`. Khai báo cả DTO, xử lý chọn đa thẻ, tìm kiếm full-text, di chuyển deck, gắn nhãn tag, đồng bộ session. |
| 16 | `features/settings/components/__tests__/McpTokensBaseline.characterization.test.tsx` | TEST | **1.020** | Test Suite | Test hồi quy đặc tả hành vi chi tiết cho màn hình quản lý token MCP. |
| 17 | `data/legalDocumentsData.ts` | SRC | **1.000** | Static Data Repository | Kho văn bản pháp lý đầy đủ gồm: Điều khoản dịch vụ, Chính sách quyền riêng tư, Quy định hoàn tiền, Thỏa thuận tác giả. |

### 2.5 Phụ thuộc Chéo giữa các Feature, Vòng lặp Hai chiều và 5 Type SCCs

#### A. Số liệu Thống kê Phụ thuộc Chéo
- **Tổng số lệnh `import` xuyên ranh giới feature**: **45 lệnh** (41 lệnh runtime và 4 lệnh type-only).
- **Số cặp feature có liên kết qua lại**: **28 cặp**.

#### B. Các Vòng lặp Cấp Feature (Feature-Level Cycles)
Phân tích đồ thị có hướng (Directed Graph) giữa các feature phát hiện các chu trình liên kết ngang:
1. **Vòng lặp Hai chiều Trực tiếp `study` $\longleftrightarrow$ `browse`**:
   - `features/browse/hooks/useBrowseState.ts` gọi trực tiếp `updateCardFieldValuesInSessions` từ `@/features/study/session/sessionStore`.
   - Ngược lại, `features/study/components/StudyQuickEditDialog.tsx` gọi `MediaFieldPreview`, `BrowseStrokeModal` và type `CardDetailResponse` từ `@/features/browse/...`.
2. **Vòng lặp Hai chiều Trực tiếp `mcp` $\longleftrightarrow$ `settings`**:
   - `features/mcp/types.ts` re-export các scopes/policy từ `@/features/settings/hooks/useMcpTokenCRUD`.
   - Trong khi đó, `features/settings/components/McpTokensTab.tsx` và `features/settings/hooks/useMcpTokenCRUD.ts` gọi `McpTokensManager` và `useMcpTokens` từ `@/features/mcp/...`.
3. **Vòng lặp Chuỗi 5 Feature**:
   `audio` $\longrightarrow$ `import` $\longrightarrow$ `note-types` $\longrightarrow$ `study` $\longrightarrow$ `browse` $\longrightarrow$ `audio`:
   - `audio` import `DeckSelectionTreeView` từ `import`.
   - `import` import `NoteTypeLivePreview` từ `note-types`.
   - `note-types` import `CardDisplay` và `updateTemplateInSessions` từ `study`.
   - `study` import `MediaFieldPreview` từ `browse`.
   - `browse` import `loadStoredLocalAudioSettings` và `cleanTextForTts` từ `audio`.
4. **Vòng lặp Chuỗi Worksheets**:
   `worksheets` $\longrightarrow$ `import` $\longrightarrow$ `note-types` $\longrightarrow$ `study` $\longrightarrow$ `browse` $\longrightarrow$ `worksheets`:
   - `worksheets/components/WorksheetDeckSelectStep.tsx` import `DeckSelectionTreeView` từ `@/features/import/...`.
   - `browse/pages/BrowsePage.tsx` import `DeckWorksheetModal` từ `@/features/worksheets`.

#### C. Phân tích Vòng lặp Cấp Tệp (File-Level SCCs) bằng Thuật toán Tarjan
- **Khi tính cả Type Imports: Có đúng 5 nhóm vòng phụ thuộc tệp (SCCs)**:
  1. `features/auth/api.ts` $\longleftrightarrow$ `app/api.ts` (Kích thước: 2 tệp)
  2. `features/settings/hooks/useMcpTokenCRUD.ts` $\longleftrightarrow$ `features/mcp/types.ts` $\longleftrightarrow$ `features/mcp/hooks/useMcpTokens.ts` (Kích thước: 3 tệp)
  3. `features/study/scheduler/types.ts` $\longleftrightarrow$ `features/study/types.ts` (Kích thước: 2 tệp)
  4. `features/study/session/sessionRestore.ts` $\longleftrightarrow$ `features/study/session/sessionStore.ts` (Kích thước: 2 tệp)
  5. `features/import/utils/mapping.ts` $\longleftrightarrow$ `features/import/hooks/useFileImportWizard.ts` (Kích thước: 2 tệp)
- **Khi loại trừ import `type` tường minh: Có đúng 0 nhóm vòng phụ thuộc runtime (SCC = 0)**.
  - *Kết luận*: Module evaluation lúc runtime của Vite không bị deadlock, nhưng cấu trúc type definitions bị lồng ghép chặt chẽ, đòi hỏi phải bóc tách DTO xuống tầng `entities`.

### 2.6 Vi phạm Phân tầng Kiến trúc (Layer Boundary Inversions)
Khảo sát và rà soát của Codex phát hiện 6 điểm vi phạm nguyên tắc kiến trúc đơn hướng FSD cần được khắc phục dứt điểm:
1. **Tầng dùng chung (`shared`) phụ thuộc tầng ứng dụng (`app`)**:
   - `shared/api/bootstrap.ts` (dòng 2) gọi `import { appApi } from '../../app/api'`.
   - Trong khi đó, `app/api.ts` lại import DTO từ `features/auth`, `features/dashboard`, `features/statistics`.
   - *Hệ quả*: Tầng thấp nhất (`shared`) vô tình kéo theo toàn bộ ứng dụng và các domain feature, phá vỡ tính độc lập của các package.
2. **Tầng dùng chung (`shared`) phụ thuộc trạng thái phiên (`session bootstrap`)**:
   - `shared/components/Brand.tsx` (dòng 3, 20) gọi `useBootstrap()` từ `@/shared/api/bootstrap` để sinh destination URL `/dashboard` hoặc `/`.
   - *Hệ quả*: Một presentation component dùng chung lại phụ thuộc vào query cache phiên của ứng dụng.
3. **Tầng tiện ích (`lib`) phụ thuộc tầng nghiệp vụ (`features`)**:
   - `lib/ankiSyncEngine.ts` (dòng 8–9) gọi `import { ankiImportApi } from '@/features/import/api'`.
   - `lib/flamaAudioClient.ts` (dòng 1–7) gọi `import type { EnginePackageState... } from '@/features/audio/types'`.
4. **Tầng tiện ích (`utils`) phụ thuộc components và DTO nghiệp vụ**:
   - `features/worksheets/utils/printEngine.tsx` (dòng 4–5) import trực tiếp `WorksheetPageRenderer` và worksheet DTOs.
   - *Hệ quả*: Không thể chuyển nguyên khối `printEngine.tsx` xuống `shared/lib/print` vì sẽ tạo thêm phụ thuộc ngược `shared` $\to$ `features/worksheets`.
5. **Thành phần Entity/Model phụ thuộc tầng App và Feature**:
   - `features/marketplace/hooks/useTaxonomySchema.ts` (dòng 2, 65) gọi `appApi` từ `@/app/api` và fallback constants từ `features/marketplace/utils/publishTaxonomyConstants`.
   - *Hệ quả*: Không thể chuyển file này trực tiếp vào `entities/marketplace-item` nếu chưa bóc tách API query và constants độc lập.
6. **Feature phụ thuộc Widget (Inversion across Upper Layers)**:
   - `features/settings/components/McpTokensTab.tsx` import component quản lý `<McpTokensManager />`. Nếu `McpTokensManager` được đặt ở `widgets/`, thì feature `settings` đang vi phạm FSD khi import từ tầng widget. Việc composition phải thuộc về tầng `pages`.

---

## PHẦN 3: BẢNG MAPPING SOURCE -> TARGET 6 TẦNG FSD CHI TIẾT

### 3.1 Khung Kiến trúc 6 Tầng Chuẩn FSD và Ma trận Phụ thuộc Đơn hướng
Hệ thống frontend mới chuẩn hóa theo 6 tầng Feature-Sliced Design (FSD):

```
frontend/src/
  ├── app/          [Tier 1 / Level 6] Khởi tạo ứng dụng, routing root, providers, styles toàn cục
  ├── pages/        [Tier 2 / Level 5] Các màn hình tương ứng với route của react-router
  ├── widgets/      [Tier 3 / Level 4] Các khối giao diện phức hợp ghép từ nhiều feature và entity
  ├── features/     [Tier 4 / Level 3] Các luồng hành vi tương tác và nghiệp vụ của người dùng
  ├── entities/     [Tier 5 / Level 2] Thực thể dữ liệu nghiệp vụ, DTO, schema và UI card nguyên tử
  └── shared/       [Tier 6 / Level 1] Primitives UI dùng chung, HTTP client, tiện ích và cấu hình
```

#### Quy tắc Đơn hướng Sắt đá (Unidirectional Dependency Rule):
Hệ thống tuân thủ nghiêm ngặt nguyên tắc phụ thuộc một chiều từ trên xuống dưới theo chuỗi:
$$\text{app (Tier 1)} \longrightarrow \text{pages (Tier 2)} \longrightarrow \text{widgets (Tier 3)} \longrightarrow \text{features (Tier 4)} \longrightarrow \text{entities (Tier 5)} \longrightarrow \text{shared (Tier 6)}$$

1. **Chiều phụ thuộc**: Một tầng chỉ được phép import từ các tầng nằm sâu hơn bên dưới trong chuỗi phân cấp (nghĩa là với chỉ số Tier $T \in \{1..6\}$, module tại Tier $T_A$ chỉ được phép import từ Tier $T_B$ khi $T_B > T_A$; hoặc xét theo độ cao kiến trúc Level $L \in \{6..1\}$, tầng có Level $L$ chỉ được import từ các tầng có Level $< L$):
   - `app` (Tier 1) $\longrightarrow$ có thể import `pages` (2), `widgets` (3), `features` (4), `entities` (5), `shared` (6).
   - `pages` (Tier 2) $\longrightarrow$ có thể import `widgets` (3), `features` (4), `entities` (5), `shared` (6).
   - `widgets` (Tier 3) $\longrightarrow$ có thể import `features` (4), `entities` (5), `shared` (6).
   - `features` (Tier 4) $\longrightarrow$ có thể import `entities` (5), `shared` (6). **Feature TUYỆT ĐỐI KHÔNG import Feature khác và KHÔNG import Widget.**
   - `entities` (Tier 5) $\longrightarrow$ có thể import `shared` (6). **Entity TUYỆT ĐỐI KHÔNG import Entity khác hoặc Feature/Widget/Page/App.**
   - `shared` (Tier 6) $\longrightarrow$ **TUYỆT ĐỐI KHÔNG import bất kỳ tầng nào bên trên nó.**

#### Ma trận Phụ thuộc Hợp lệ (Architectural Dependency Matrix):

| Source Layer (Gọi) \ Target Layer (Được gọi) | `app` (1) | `pages` (2) | `widgets` (3) | `features` (4) | `entities` (5) | `shared` (6) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **`app` (Tier 1 / Level 6)** | 🔷 Nội bộ | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép |
| **`pages` (Tier 2 / Level 5)** | ❌ CẤM | 🔷 Nội bộ | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép |
| **`widgets` (Tier 3 / Level 4)** | ❌ CẤM | ❌ CẤM | 🔷 Nội bộ | ✅ Cho phép | ✅ Cho phép | ✅ Cho phép |
| **`features` (Tier 4 / Level 3)** | ❌ CẤM | ❌ CẤM | ❌ CẤM (R3) | ❌ CẤM (cross) | ✅ Cho phép | ✅ Cho phép |
| **`entities` (Tier 5 / Level 2)** | ❌ CẤM | ❌ CẤM | ❌ CẤM | ❌ CẤM | ❌ CẤM (cross) | ✅ Cho phép |
| **`shared` (Tier 6 / Level 1)** | ❌ CẤM (R2) | ❌ CẤM | ❌ CẤM | ❌ CẤM | ❌ CẤM | 🔷 Nội bộ |

2. **Rào chắn Public API (`index.ts`) & Lazy Boundary**:
   - Mọi slice trong `widgets/`, `features/`, `entities/` bắt buộc phải có `index.ts` để công khai interface.
   - Các module bên ngoài CHỈ ĐƯỢC PHÉP import qua root slice (ví dụ: `@/entities/flashcard`, `@/features/study`), **nghiêm cấm** import sâu vào file nội bộ (trừ khi có adapter headless được cấu hình tại tầng `app`).
   - Các file trong cùng một slice phải dùng relative path (`./ui/...`, `./model/...`) và không được import qua `index.ts` của chính mình để tránh circular evaluation.
   - **Quy tắc Lazy Boundary cho `shared`**: Không bắt buộc phải có một public root barrel chung gom toàn bộ mọi primitive tại `src/shared/index.ts` nếu việc này làm mất ranh giới lazy-loading và làm phình to bundle ban đầu; thay vào đó, các sub-path exports phải rõ ràng và tường minh (`@/shared/ui`, `@/shared/api/client`, `@/shared/lib/utils`).

---

### 3.2 Bảng Phân bổ Định lượng và Catalog Bóc tách Đa Đích (1-to-Many Extraction)

Bảng phân bổ dưới đây phản ánh cấu trúc chuyển đổi sang 6 tầng FSD, đồng thời hỗ trợ đầy đủ các module cần bóc tách đa đích (1-to-many extractions) thay vì ép buộc ánh xạ 1-to-1 máy móc:

| FSD Tier | Thư mục Đích | Số lượng Tệp (Dự kiến Đích) | Thành phần Cốt lõi bên trong |
|---|---|---:|---|
| **Tier 1: app** | `src/app/` | **7** | `App.tsx`, `main.tsx`, `index.css`, `studyContentSync.ts`, `RequireAuth`, `RequireCreator`, `vite-env.d.ts` |
| **Tier 2: pages** | `src/pages/` | **71** | 48 route pages trên toàn bộ các feature domains + các trang static/legal/404 |
| **Tier 3: widgets** | `src/widgets/` | **22** | `app-shell`, `worksheet-studio` (Wizard Shell), `mcp-token-manager`, `collaboration-diff`, `dashboard-workspace`, `browse-workspace`, `study-workspace`, `admin-analytics` |
| **Tier 4: features** | `src/features/` | **240+** | Các luồng tương tác và controllers: `auth`, `browse` (tách 3 controllers), `study`, `worksheets` (tách step views & print utils), `deck-management`, `note-editor`, `anki-sync`, `audio`, `marketplace-publish`, `deck-install`, `onboarding` |
| **Tier 5: entities** | `src/entities/` | **25+** | Thực thể nghiệp vụ:<br>- `entities/flashcard`: **15 tệp (8 src + 7 test)** — *Đã hoàn tất bóc tách ngày 2026-10-05 (Gói C02)*.<br>- `entities/deck`: 3 tệp (`DeckSelectionTreeView`, `StudyHeatmap`).<br>- `entities/marketplace-item`: 3 tệp (`DeckCard`, decoupled taxonomy schema).<br>- `entities/mcp-token`: 1 tệp (`scopes`, `types`).<br>- `entities/session`: DTOs phiên và headless session bootstrap.<br>- `entities/media`: `noteMedia.ts`.<br>- **Planned Extractions**: `support-ticket` (tách từ `admin`/`support` ở G10/G12), `order` (tách từ `orders`), `wallet` (tách từ `wallet`), `user` (tách từ `profile`). |
| **Tier 6: shared** | `src/shared/` | **70+** | 8 Flama UI primitives + 30 Shadcn UI primitives (`shared/ui/shadcn/`), HTTP transport client (`client.ts`), `utils.ts`, `imageCompression.ts`, `useMobile.ts`, `BrandView` (presentation thuần). |

#### Catalog Bóc tách Đa Đích cho các Tệp Monolith Trọng yếu:

| Tệp Nguồn Hiện tại | Kích thước | Các Phần Đích Sau Khi Bóc Tách (1-to-Many Mapping) | Trách nhiệm Phân công |
|:---|:---:|:---|:---:|
| `features/worksheets/components/DeckWorksheetModal.tsx` | 4.387 LOC | 1. `widgets/worksheet-studio/DeckWorksheetModal.tsx` (Wizard Modal Shell < 300 LOC)<br>2. `features/worksheets/components/steps/WorksheetDeckSelectStep.tsx` (< 250 LOC)<br>3. `features/worksheets/components/steps/WorksheetTemplateStep.tsx` (< 300 LOC)<br>4. `features/worksheets/components/steps/WorksheetConfigStep.tsx` (< 300 LOC)<br>5. `features/worksheets/components/steps/WorksheetPreviewStep.tsx` (< 300 LOC)<br>6. `features/worksheets/hooks/useWorksheetStudioState.ts` (Wizard Controller Hook) | Gemini (UI/Steps)<br>Codex (State/Geometry) |
| `features/worksheets/components/WorksheetPageRenderer.tsx` & `printEngine.tsx` | 1.718 + 144 LOC | 1. `features/worksheets/components/renderers/` (Tách riêng 6 renderers mẫu in)<br>2. `features/worksheets/utils/printEngine.tsx` (**GIỮ NGUYÊN tại worksheets utils**, không hạ xuống shared)<br>3. `shared/lib/print/printCssHelpers.ts` (Chỉ chứa CSS page-break và helpers in ấn trung lập) | Codex (Print Math & Geometry) |
| `features/browse/hooks/useBrowseState.ts` | 1.052 LOC | 1. `features/browse/hooks/useBrowseFilters.ts` (Bộ lọc tìm kiếm, sort, sortDir & URL sync)<br>2. `features/browse/hooks/useBrowseSelection.ts` (Chọn đa thẻ, bulk tag, bulk move)<br>3. `features/browse/hooks/useBrowseNoteEditor.ts` (Modal chỉnh sửa thẻ & card detail cache) | Codex (State Orchestration) |
| `features/admin/pages/AdminTicketsPage.tsx` & `features/support/pages/FeedbackPage.tsx` | ~1.400 LOC | 1. `pages/admin/AdminTicketsPage.tsx` & `pages/support/FeedbackPage.tsx` (Route Views)<br>2. `entities/support-ticket/` (`TicketItem`, `TicketStatusBadge`, `types.ts`) — **Owner: G10/G12 (Admin/Support)**, KHÔNG gán cho worksheets | Gemini (UI Badge)<br>Codex (Ticket Schema) |
| `shared/components/Brand.tsx` | 66 LOC | 1. `shared/components/Brand.tsx` $\to$ `BrandView` (Presentation thuần túy nhận `homeHref`, `size`, `compact` qua props, KHÔNG gọi `useBootstrap`)<br>2. `components/Brand.tsx` hoặc `widgets/app-shell/` $\to$ Wrapper kết nối `useBootstrap()` và truyền `destination` | Gemini (UI Decoupling) |
| `features/marketplace/hooks/useTaxonomySchema.ts` | 118 LOC | 1. `shared/api/taxonomy.ts` (Endpoint query độc lập)<br>2. `entities/marketplace-item/model/taxonomyConstants.ts` (Fallbacks)<br>3. `entities/marketplace-item/model/useTaxonomySchema.ts` (Hook độc lập không import `app/api`) | Codex (API Extraction) |

### 3.3 Ma trận Chuyển đổi Chi tiết 22 Feature và Thành phần Chung

| Feature Hiện tại | Vị trí Đích (6 Tầng FSD) | Public Exports (`index.ts`) | Chiến lược Điều phối Phân công (Codex / Gemini) |
|---|---|---|---|
| **`admin`** | - `pages/admin/` (12 pages)<br>- `widgets/admin-analytics/`<br>- `features/admin-management/`<br>- `entities/support-ticket/` | `AdminAnalyticsWidget`, `AdminUsersManager`, `AdminTaxonomyManager` | - Gemini: Tách các page và controller UI cục bộ.<br>- Codex: Quản lý quyền, xử lý dòng tiền PayOS, ticket/token contracts. `entities/support-ticket` thuộc owner Admin/Support (G10/G12). |
| **`audio`** | - `pages/audio/`<br>- `features/audio/`<br>- `entities/media/`<br>- `shared/lib/japanese/` | `LocalAudioDialog`, `useDeckAudioQueue`, `cleanTextForTts` | - Gemini: Tách UI dialogs và rule cards.<br>- Codex: Giữ desktop companion client (port 4791), queue storage, cancel token. Gọi cập nhật thẻ qua `@/entities/flashcard/model/cardContentUpdates`, KHÔNG import `features/study`. |
| **`auth`** | - `pages/auth/` (5 pages)<br>- `app/router/guards/`<br>- `features/auth/`<br>- `entities/session/` | `AuthCard`, `useLoginForm`, `useRegisterForm`, `RequireAuth`, `RequireCreator` | - Gemini: Chuyển forms và auth views.<br>- Codex: Session bootstrap DTO, auth state, cookie/CSRF handling. |
| **`browse`** | - `pages/browse/`<br>- `widgets/browse-workspace/`<br>- `features/browse/`<br>- `features/note-editor/`<br>- `entities/flashcard/` | `BrowseWorkspace`, `useBrowseFilters`, `MediaFieldPreview`, `BrowseStrokeModal` | - Gemini: Chuyển toolbar, table, split sidebar, pagination UI.<br>- Codex: Phân rã 1.052 LOC `useBrowseState` thành 3 controllers chuyên trách. Cập nhật thẻ qua `@/entities/flashcard/model/cardContentUpdates`, KHÔNG import `features/study`. |
| **`dashboard`** | - `pages/dashboard/`<br>- `widgets/dashboard-workspace/`<br>- `features/deck-management/`<br>- `entities/deck/` | `DashboardWorkspace`, `DeckModals`, `StudyHeatmap`, `DeckTree` | - Gemini: Thực hiện pilot chuyển đổi UI và kéo thả deck tree.<br>- Codex: Chốt query contract và mutation invalidations. |
| **`deck-collaboration`** | - `pages/deck-collaboration/` (5 pages)<br>- `widgets/collaboration-diff/`<br>- `features/deck-collaboration/`<br>- `entities/deck/` | `DiffWorkspace`, `ChangeRequestStatusBadge`, `useDeckCollaboration` | - Gemini: Chuyển trang và diff layout.<br>- Codex: Quản lý thuật toán 3-way rebase, conflict resolution và overlay clone. |
| **`guide`** | - `pages/guide/`<br>- `widgets/guide-explorer/`<br>- `features/guide/`<br>- `shared/lib/guide/` | `ContextHelpButton`, `GuideArticleRenderer`, `McpToolsExplorer` | - Gemini: Chuyển toàn bộ views và static markdown data.<br>- Codex: Chuẩn hóa public export `ContextHelpButton` cho 8 caller features. |
| **`import`** | - `pages/import/`<br>- `features/import/`<br>- `features/anki-sync/`<br>- `entities/deck/` | `DeckSelectionTreeView`, `FileImportWizard`, `AnkiSyncTab` | - Gemini: Chuyển wizard import CSV/TSV và UI sync.<br>- Codex: Giữ AnkiConnect client, sync worker (`sync.worker.ts`), IndexedDB. |
| **`library`** | - `pages/library/`<br>- `features/deck-install/`<br>- `entities/marketplace-item/` | `InstalledDecksPage`, `useInstalledDecks` | - Gemini: Chuyển trang thư viện.<br>- Codex: Quản lý logic cập nhật phiên bản phát hành và overlay clone cutover. |
| **`marketplace`** | - `pages/marketplace/` (6 pages)<br>- `widgets/marketplace-catalog/`<br>- `features/marketplace-publish/`<br>- `features/deck-install/`<br>- `entities/marketplace-item/` | `DeckCard`, `MarketplaceCatalog`, `RedeemDeckKeyModal` | - Gemini: Chuyển catalog, detail page, publish wizard steps UI.<br>- Codex: Quản lý pricing, payment redirection; tách `useTaxonomySchema` khỏi `app/api`. |
| **`mcp`** | - `widgets/mcp-token-manager/`<br>- `features/mcp/`<br>- `entities/mcp-token/` | `McpTokensManager`, `useMcpTokens`, `ALL_MCP_SCOPES`, `McpPolicy` | - Gemini: Chuyển widget manager và modal UI.<br>- Codex: Thống nhất scopes/policy entity. Widget được ghép tại `pages`, `features/settings` KHÔNG import widget. |
| **`note-types`** | - `pages/note-types/` (4 pages)<br>- `features/note-type-editor/`<br>- `entities/flashcard/` | `NoteTypeLivePreview`, `NoteTypeEditor`, `NoteTypeAiGuideModal` | - Gemini: Chuyển editor UI và template cards.<br>- Codex: Quản lý template authoring (không mutate active study lease) và tiêu thụ `entities/flashcard`. |
| **`oauth`** | - `pages/oauth/`<br>- `features/oauth-consent/` | `OAuthConsentPage`, `useOAuthConsent` | - Gemini: Chuyển trang và UI consent card.<br>- Codex: Quản lý security redirect, code challenge và authorization code. |
| **`onboarding`** | - `features/onboarding/`<br>- `entities/user/` | `OnboardingModal`, `DashboardSpotlightTour`, `useOnboarding` | - Gemini: Chuyển modal và spotlight tour, giữ nguyên localStorage keys.<br>- Codex: Xác nhận schema mục tiêu học tập. |
| **`orders`** | - `pages/orders/`<br>- `entities/order/` | `OrdersPage`, `OrderReceiptCard` | - Gemini: Chuyển UI bảng đơn hàng.<br>- Codex: Quản lý PayOS webhook verification status. |
| **`profile`** | - `pages/profile/`<br>- `features/account/`<br>- `entities/user/` | `ProfileHeroCard`, `ProfileEditDialog`, `AvatarUploadModal` | - Gemini: Chuyển các modal chỉnh sửa thông tin và avatar.<br>- Codex: Quản lý xác thực sinh viên, avatar upload và session update. |
| **`settings`** | - `pages/settings/` (3 pages)<br>- `features/account/`<br>- `features/yomitan-connect/` | `StudyGoalsForm`, `YomitanTokensTab` | - Gemini: Chuyển settings views. Nhúng `<McpTokensManager mode="user" />` tại Page level (`McpTokensPage.tsx`), không import widget vào tab component.<br>- Codex: Quản lý OAuth client CRUD và session invalidation. |
| **`statistics`** | - `pages/statistics/`<br>- `widgets/statistics-overview/`<br>- `entities/deck/api/` | `StatisticsOverviewWidget`, `UserStudyTimeChart`, `FutureDueChart` | - Gemini: Chuyển charts và trang thống kê.<br>- Codex: Quản lý timezone offset và query filter contract. |
| **`study`** | - `pages/study/`<br>- `widgets/study-workspace/`<br>- `features/study/`<br>- `entities/flashcard/` | `StudyWorkspace`, `CardDisplay`, `CardRendererFrame` | - Gemini: Chuyển header toolbar, bottom bar, completion card UI.<br>- Codex: Giữ độc quyền 1.463 LOC `useStudySession`, SM-2 engine, IndexedDB durability. Đã tách `entities/flashcard` (C02). |
| **`support`** | - `pages/support/` (5 pages)<br>- `features/support/`<br>- `entities/support-ticket/` | `SupportFeedbackDialog`, `TicketStatusBadge`, `TicketItem` | - Gemini: Chuyển form gửi phản hồi và các trang guide.<br>- Codex: Quản lý support donation PayOS bridge; `entities/support-ticket` thuộc owner G10/G12. |
| **`wallet`** | - `pages/wallet/`<br>- `features/wallet/`<br>- `entities/wallet/` | `WalletSummaryCard`, `WalletTransactionsTable` | - Gemini: Chuyển trang và bảng giao dịch.<br>- Codex: Quản lý payout request validation và ledger balance. |
| **`worksheets`** | - `pages/worksheets/`<br>- `widgets/worksheet-studio/`<br>- `features/worksheets/` | `DeckWorksheetModal`, `WorksheetPageRenderer`, `printEngine` | - Gemini: Phân rã 4.387 LOC modal theo từng wizard step.<br>- Codex: Giữ layout math geometry, SVG parser; `printEngine.tsx` giữ trong `features/worksheets/utils/`, không hạ xuống shared. |

### 3.4 Chiến lược Tháo gỡ 5 Điểm nghẽn Kiến trúc và Vòng lặp Trọng yếu

#### 1. Tháo gỡ Vòng lặp `mcp` $\longleftrightarrow$ `settings` & Tuân thủ Phân tầng:
- **Thực trạng**: `features/mcp/types.ts` import scope từ `features/settings/hooks/useMcpTokenCRUD.ts`; ngược lại `settings` import hook và manager từ `mcp`. Đồng thời, việc `McpTokensTab.tsx` import widget vi phạm FSD (Feature không được import Widget).
- **Giải pháp dứt điểm**:
  1. Trích xuất toàn bộ kiểu dữ liệu, `ALL_MCP_SCOPES`, `SCOPE_CATEGORIES`, `SCOPE_PRESETS` và `McpPolicy` xuống `src/entities/mcp-token/model/scopes.ts` và `types.ts`.
  2. Gom cụm `<McpTokensManager />` vào `src/widgets/mcp-token-manager/`.
  3. Cả `features/admin/pages/AdminMcpTokensPage.tsx` và trang người dùng `src/pages/settings/McpTokensPage.tsx` thực hiện việc composition tại **tầng Pages**, nhúng `<McpTokensManager mode="admin" />` hoặc `<McpTokensManager mode="user" />`. Component tab `McpTokensTab.tsx` chỉ đóng vai trò trình bày hoặc controller mà **KHÔNG import widget**. Triệt tiêu 100% vòng lặp và vi phạm phân tầng.

#### 2. Tháo gỡ Phụ thuộc Ngược `shared/api/bootstrap.ts` $\longrightarrow$ `app/api.ts` & Chuẩn hóa Wire Contract:
- **Thực trạng**: `shared/api/bootstrap.ts` gọi `appApi` từ `app/api.ts`; trong khi `app/api.ts` lại import DTO từ `features/auth`, `features/dashboard`, `features/statistics`. Bản dự thảo cũ của G00 từng đề xuất sai endpoint `apiJson('/api/bootstrap')` (gây lỗi typecheck và đứt gãy luồng khởi tạo).
- **Giải pháp dứt điểm (Chuẩn hóa Wire Contract & Decoupling)**:
  1. **Đúng Wire Endpoint**: Endpoint backend thực tế trên wire là `GET ${API_BASE_URL}/session` với `{ includeTimezone: false }`.
  2. **Đúng Transport Method**: `shared/api/client.ts` cung cấp `apiRequest<T>` cho các request đọc (GET), trong khi `apiJson<T>` chỉ phục vụ các mutations có method (`POST | PUT | PATCH | DELETE`) và body. Do đó, hàm session fetcher gọi:
     ```typescript
     const payload = await apiRequest<SessionResponse>(`${API_BASE_URL}/session`, { includeTimezone: false })
     ```
  3. **Bảo toàn Response Mapping (`toBootstrap`)**: Payload raw `SessionResponse` (`authenticated`, `user`, `csrf_token`) bắt buộc phải được chuyển đổi qua hàm `toBootstrap(payload)` để tạo đối tượng `FrontendBootstrap`:
     - Tự động thiết lập token: `setCsrfToken(payload.csrf_token)`.
     - Kiểm tra quyền quản trị: `isAdmin = Boolean(payload.user?.is_admin)`.
     - Bổ sung cấu trúc liên kết điều hướng `links` (các admin links chỉ được gán khi `isAdmin === true`, ngược lại là `null`).
     - Gán giá trị mặc định: `api_version: 'v1'`, `messages: []`, `support_contact_email: ''`.
  4. **Thống nhất Query Key**: Toàn bộ ứng dụng sử dụng duy nhất hằng số:
     ```typescript
     export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const
     ```
  5. **Loại bỏ Hoàn toàn Reverse Import**: Chuyển hàm fetch session độc lập này vào `src/entities/session/api/bootstrap.ts` hoặc trích xuất vào module transport độc lập. `shared/api/bootstrap.ts` tiêu thụ hàm này mà tuyệt đối **KHÔNG import `app/api.ts`**. `app/api.ts` chỉ đóng vai trò facade tương thích ngược tạm thời.

#### 3. Tháo gỡ Mutation Xuyên Thấu vào Study Persistence & Khóa chặt Bất biến Template (Template Immutability in Active Lease):
- **Thực trạng**: 
  Các tính năng chỉnh sửa dữ liệu (`browse` khi sửa trường thẻ inline, `audio` khi sinh giọng đọc gắn URL media, `note-types` khi sửa CSS/HTML template) từng gọi trực tiếp hàm nội bộ `updateCardFieldValuesInSessions` và `updateTemplateInSessions` sâu bên trong `@/features/study/session/sessionStore.ts`.
- **Phân định Rạch ròi giữa Card-Content Patch và Template Authoring**:
  Rà soát của Codex (`G00_CODEX_REVIEW_2026-10-04.md`, R1) đã xác định rõ:
  1. **Cập nhật Dữ liệu Thẻ Động (Dynamic Card-Content Updates - Hỗ trợ Realtime)**:
     - Khi người dùng sửa giá trị trường từ vựng (ví dụ: sửa nghĩa, kanji) hoặc gắn file audio TTS mới, dữ liệu này cần được cập nhật vào tất cả các phiên học dở dang để người dùng thấy nội dung mới nhất.
     - Cơ chế này được thực hiện qua **Headless Port độc lập** tại `src/entities/flashcard/model/cardContentUpdates.ts`:
       ```typescript
       // src/entities/flashcard/model/cardContentUpdates.ts
       import type { CardMediaArtifact } from './types'

       export interface CardContentUpdate {
         cardId: string
         noteId?: string | null
         fieldValues: Record<string, string>
         media?: CardMediaArtifact[]
       }

       type CardContentUpdater = (update: CardContentUpdate) => Promise<void>
       let contentUpdater: CardContentUpdater | undefined

       export function configureCardContentUpdater(updater: CardContentUpdater): () => void {
         const previous = contentUpdater
         contentUpdater = updater
         return () => {
           if (contentUpdater === updater) contentUpdater = previous
         }
       }

       export async function updateCardFieldValues(update: CardContentUpdate): Promise<void> {
         if (!contentUpdater) throw new Error('Card content persistence is not configured')
         await contentUpdater(update)
       }
       ```
     - Ráp nối tại Tầng Ứng dụng (`src/app/studyContentSync.ts`):
       ```typescript
       // src/app/studyContentSync.ts
       import { configureCardContentUpdater } from '@/entities/flashcard/model/cardContentUpdates'

       configureCardContentUpdater(async ({ cardId, fieldValues, noteId, media }) => {
         const { updateCardFieldValuesInSessions } = await import('@/features/study/contentUpdates')
         await updateCardFieldValuesInSessions(cardId, fieldValues, { noteId, media })
       })
       ```
     - **Nguyên lý Headless**: Hoạt động trực tiếp trên IndexedDB `flama-study` (store `sessions`) và memory fallback; không đòi hỏi `StudyPage` phải mount. Nếu có `StudyPage` đang mở ở tab khác, phát sự kiện `CARD_UPDATED` qua `BroadcastChannel('flama_study_sync_channel')` để cập nhật RAM state.
  2. **Bất biến Mẫu Thẻ trong Phiên Học Đang Mở (Template Immutability in Active Lease Epoch)**:
     - **TUYỆT ĐỐI KHÔNG** cập nhật cấu trúc template (`templates[templateKey]`) vào snapshot của phiên học đang mở!
     - Mã nguồn hiện tại cố ý khóa chặt hành vi này:
       - `sessionStore.ts`, hàm `updateTemplateInSessions` (dòng 616): **là no-op**.
       - `useStudySession.ts`, hàm `updateTemplateContent` (dòng 1243): **cũng là no-op**.
       - `sessionStore.test.ts` (dòng 127): **test khóa chặt hành vi**: content được patch nhưng template giữ nguyên vẹn sau khi tác giả sửa mẫu thẻ.
     - **Lý do bảo vệ kiến trúc**: Snapshot của một phiên học đang hoạt động (active lease) bắt buộc phải bất biến về mặt template để bảo vệ tính toàn vẹn của mã băm snapshot (`snapshot_hash`), tránh crash/reload iframe sandbox ngoài ý muốn và bảo đảm khả năng hoàn tác (deterministic undo stack).
     - Thay đổi về template trong NoteType Editor chỉ có hiệu lực khi người dùng **mở một phiên học mới** (khi snapshot mới được khởi tạo từ backend/cache).
  3. **Caller Integration**: `browse` và `audio` chỉ cần import `updateCardFieldValues` từ `@/entities/flashcard/model/cardContentUpdates`, hoàn toàn loại bỏ việc import vào `features/study`.

#### 4. Bóc tách Iframe Sandbox Flashcard Renderer (`CardDisplay` & `CardRendererFrame`):
- **Thực trạng**: `marketplace` và `note-types` từng import `CardDisplay` từ `features/study/components/CardDisplay`.
- **Hiện trạng Đã Nghiệm thu (Gói C02 - 2026-10-05)**:
  1. Codex đã hoàn tất xuất sắc việc trích xuất `CardDisplay.tsx`, `CardRendererFrame.tsx` và `clientRenderer.ts` sang `src/entities/flashcard/` (8 src files + 7 test files, 69 tests pass).
  2. Bảo toàn nguyên vẹn cơ chế iframe sandbox, CSP headers, postMessage channel hai chiều, và cơ chế giữ mounted cả hai mặt Front/Back thẻ.
  3. Cả `study`, `marketplace`, `note-types` hiện đều tiêu thụ qua public API của `@/entities/flashcard`.

#### 5. Bóc tách Cây Chọn Bộ Thẻ Dùng Chung (`DeckSelectionTreeView`):
- **Thực trạng**: `audio` và `worksheets` import `DeckSelectionTreeView` từ `features/import/components/DeckSelectionTreeView`.
- **Giải pháp dứt điểm**:
  1. Di chuyển `DeckSelectionTreeView.tsx` và test suite đi kèm sang `src/entities/deck/ui/DeckSelectionTreeView.tsx`.
  2. Di chuyển kiểu dữ liệu `DeckOption` sang `src/entities/deck/model/types.ts`.
  3. Các caller (`import`, `audio`, `worksheets`) import từ `@/entities/deck`.

### 3.5 Đặc tả Mã nguồn Public API Export (`index.ts`)

#### A. `src/entities/flashcard/index.ts` (Hiện trạng Nghiệm thu C02 & Planned Contracts)
```typescript
/**
 * Public UI & DTO entry for Flashcard Entity (Tier 5)
 * Bóc tách hoàn tất tại Gói C02 (2026-10-05) - 69 tests pass.
 */
export { CardRendererFrame } from './ui/CardRendererFrame'
export { CardDisplay } from './ui/CardDisplay'
export { MediaFieldPreview, resolveDisplayUrl } from './ui/MediaFieldPreview'
export type { MediaFieldPreviewProps } from './ui/MediaFieldPreview'
export type {
  CardRendererFrameProps,
  CardDisplayProps,
  CardRendererSlots,
  CardRendererSlotContext,
  SlotRenderer,
  FieldDef,
  CardMediaArtifact,
  CardRenderTemplate,
  CardRenderContent,
  CardRenderPayload,
  RendererSidePayload,
} from './model/types'

// Headless renderer functions export từ lib (Renderer hiện hữu export renderStudySide):
export { renderStudySide } from './lib/clientRenderer'

// [Planned API]: renderCardHtml (Dự kiến chuẩn hóa ở C04 bởi Codex phục vụ in ấn/export tĩnh)
```

#### B. `src/entities/deck/index.ts`
```typescript
// Public API for Deck Entity (Tier 5)
export { DeckSelectionTreeView } from './ui/DeckSelectionTreeView'
export type { DeckOption, DeckSelectionTreeViewProps } from './ui/DeckSelectionTreeView'
export { StudyHeatmap } from './ui/StudyHeatmap'
export type {
  DeckNode,
  DeckOverview,
  CreateDeckForm,
  RenameDeckForm,
  MoveDeckForm,
} from './model/types'
export { buildDeckTree, flattenDeckTree, sanitizeDeckName } from './lib/deckTreeUtils'
```

#### C. `src/entities/mcp-token/index.ts`
```typescript
// Public API for MCP Token Entity (Tier 5)
export type {
  McpToken,
  McpMode,
  McpTokenStatus,
  CreateTokenPayload,
  UpdateTokenPayload,
  RotateTokenPayload,
  IssuedTokenResult,
  McpScopeItem,
  McpScopeCategory,
  McpPolicy,
} from './model/types'
export {
  ALL_MCP_SCOPES,
  SCOPE_CATEGORIES,
  SCOPE_PRESETS,
} from './model/scopes'
```

#### D. `src/entities/support-ticket/index.ts`
> **Ghi chú phân loại & Sở hữu (Owner Correction theo R6)**: Slice `entities/support-ticket` là một **Planned Extraction** thuộc gói triển khai **G10 / G12 (Admin & Support)** theo phân công của Codex, **TUYỆT ĐỐI KHÔNG** thuộc về các gói worksheets (C05/G05). Kiểu `TicketItem` sẽ được di dời từ `features/admin/pages/AdminTicketsPage.tsx` sang đây, và `TicketStatusBadge` sẽ được tạo mới như một component hiển thị trạng thái chuẩn hóa thay thế cho các badge rời rạc hiện nay.

```typescript
// Public API for Support Ticket Entity (Tier 5 - Owner: G10/G12 Admin & Support)
export type {
  TicketItem,
  TicketPriority,
  TicketStatus,
  TicketComment,
  CreateTicketPayload,
} from './model/types'
export { TicketStatusBadge } from './ui/TicketStatusBadge'
```

#### E. `src/widgets/mcp-token-manager/index.ts`
```typescript
// Public API for MCP Token Manager Widget (Tier 3)
export { McpTokensManager } from './ui/McpTokensManager'
export type { McpTokensManagerProps } from './ui/McpTokensManager'
```

#### F. `src/widgets/worksheet-studio/index.ts`
```typescript
// Public API for Worksheet Studio Widget (Tier 3)
export { DeckWorksheetModal } from './ui/DeckWorksheetModal'
export type { DeckWorksheetModalProps } from './ui/DeckWorksheetModal'
```

---

## PHẦN 4: DANH MỤC RUNTIME CONTRACTS BẮT BUỘC BẢO TOÀN

### 4.1 Bảng Phân cấp Định tuyến (Routes), Parameters và Query Strings
Định tuyến của Flama được khai báo tập trung tại `frontend/src/App.tsx` (dòng 328–632). Toàn bộ kiến trúc gồm đúng **95 khai báo route** (bao quát đầy đủ 95 path/index entries), được phân định nghiêm ngặt thành hai nhóm:
1. **Các tuyến đường hiển thị component trực tiếp (Canonical & Direct Component Routes)**: Gồm chính xác **77 tuyến đường** (59 tuyến đường canonical chuẩn và 18 aliases hiển thị component trực tiếp).
2. **Các tuyến đường chuyển hướng phía client (`<Navigate replace />` Redirect Routes)**: Gồm đúng **18 tuyến đường** bảo tồn tương thích ngược các URL lịch sử, bookmark cũ của người dùng và các shortcut URL ngắn.

Mọi hoạt động tái cấu trúc thư mục (FSD Migration) bắt buộc phải bảo toàn 100% các route paths, parameters và dynamic query strings dưới đây.

#### 4.1.A Bảng 77 Tuyến đường Trực tiếp & Chuẩn (Canonical & Direct Component Routes)

| Đường dẫn Tuyến đường (Route Path) | Component Tương ứng | Chế độ Tải | Access Guard | Phân loại | Params / Query Strings Bắt buộc Bảo toàn |
|---|---|---|---|:---:|---|
| `/maintenance` | `MaintenancePage` | Eager | Public | Canonical | Đọc `flama:maintenance:return-path` từ `sessionStorage` để khôi phục URL |
| `/oauth/consent` | `OAuthConsentPage` | Lazy | Public | Canonical | Query: `client_id`, `redirect_uri`, `scope`, `state`, `code_challenge`, `code_challenge_method`, `response_type` (mặc định `'code'`) |
| `/` | `LandingPage` | Eager | Public | Canonical | Trang chủ công cộng giới thiệu nền tảng |
| `/login` | `LoginPage` | Lazy | Public | Canonical | Query: `next` (URL điều hướng quay lại sau đăng nhập) |
| `/register` | `RegisterPage` | Lazy | Public | Canonical | Form đăng ký tài khoản người dùng mới |
| `/forgot-password` | `ForgotPasswordPage` | Lazy | Public | Canonical | Form yêu cầu gửi email khôi phục mật khẩu |
| `/reset-password` | `ResetPasswordPage` | Lazy | Public | Canonical | Query: `token` (xác thực token khôi phục) |
| `/verify-email` | `VerifyEmailPage` | Lazy | Public | Canonical | Query: `token` (xác thực email người dùng) |
| `/support` | `SupportPage` | Lazy | Public | Canonical | Query: `payment_order_id`, `order_id`, `support_provider_order_code`, `orderCode`, `order_code` (kích hoạt kiểm tra trạng thái ủng hộ PayOS) |
| `/payments/result` | `PaymentResultPage` | Lazy | Public | Canonical | Query: `payment_order_id`, `order_id`, `id`, `support_provider_order_code`, `orderCode`, `order_code`, `support_checkout_mode` |
| `/payments/marketplace-result` | `PaymentResultPage` | Lazy | Public | Direct Alias | Cùng component và query params như `/payments/result` (dành cho giao dịch mua học liệu) |
| `/support-donation/result` | `PaymentResultPage` | Lazy | Public | Direct Alias | Cùng component và query params như `/payments/result` (dành cho kết quả ủng hộ) |
| `/guide` | `GuidePage` | Lazy | Public | Canonical | Trung tâm hướng dẫn người dùng Flama |
| `/guide/:categorySlug` | `GuidePage` | Lazy | Public | Canonical | Param: `:categorySlug` (danh mục hướng dẫn) |
| `/guide/:categorySlug/:articleSlug` | `GuidePage` | Lazy | Public | Canonical | Params: `:categorySlug`, `:articleSlug` (bài viết cụ thể) |
| `/guide/flama-audio` | `FlamaAudioGuidePage` | Lazy | Public | Canonical | Hướng dẫn cài đặt và thiết lập Flama Audio Desktop (.NET 8 WPF) |
| `/terms` | `TermsPage` | Lazy | Public | Canonical | Điều khoản sử dụng dịch vụ |
| `/privacy` | `PrivacyPage` | Lazy | Public | Canonical | Chính sách bảo mật thông tin |
| `/cookies` | `CookiesPage` | Lazy | Public | Canonical | Chính sách sử dụng cookie |
| `/marketplace-guidelines` | `MarketplaceGuidelinesPage` | Lazy | Public | Canonical | Quy định chia sẻ và kinh doanh học liệu |
| `/community-guidelines` | `CommunityGuidelinesPage` | Lazy | Public | Canonical | Bộ quy tắc ứng xử cộng đồng |
| `/dashboard` | `DashboardPage` | Lazy | `<RequireAuth />` | Canonical | Không gian tổng quan học tập, due cards, cây thư mục bộ thẻ |
| `/statistics` | `StatisticsPage` | Lazy | `<RequireAuth />` | Canonical | Query: `deck_id` (lọc theo deck), `scope` (`'collection'` \| `'deck'`) |
| `/browse` | `BrowsePage` | Lazy | `<RequireAuth />` | Canonical | Query: `deck_id` (chọn deck), `card_id` (mở trực tiếp thẻ cụ thể) |
| `/study` | `StudyPage` | Lazy | `<RequireAuth />` | Canonical | Query: `deck_id` (chọn bộ thẻ bắt đầu phiên học SRS) |
| `/note-types` | `NoteTypeManagerPage` | Lazy | `<RequireAuth />` | Canonical | Quản lý danh sách mẫu thẻ cá nhân và hệ thống |
| `/flashcards/note-types` | `NoteTypeManagerPage` | Lazy | `<RequireAuth />` | Direct Alias | URL tương thích ngược hiển thị trực tiếp danh sách mẫu thẻ |
| `/note-types/guide` | `NoteTypeGuidePage` | Lazy | `<RequireAuth />` | Canonical | Cẩm nang và tài liệu thiết kế mẫu thẻ Anki/Flama |
| `/flashcards/note-types/guide` | `NoteTypeGuidePage` | Lazy | `<RequireAuth />` | Direct Alias | URL tương thích ngược hiển thị trực tiếp cẩm nang mẫu thẻ |
| `/note-types/:id` | `NoteTypeDetailPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:id` (Note Type ID) |
| `/flashcards/note-types/:id` | `NoteTypeDetailPage` | Lazy | `<RequireAuth />` | Direct Alias | Param: `:id` (URL tương thích ngược hiển thị chi tiết mẫu thẻ) |
| `/note-types/:id/fields` | `NoteTypeFieldsPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:id` (Note Type ID - Quản lý cấu trúc trường dữ liệu) |
| `/flashcards/note-types/:id/fields` | `NoteTypeFieldsPage` | Lazy | `<RequireAuth />` | Direct Alias | Param: `:id` (URL tương thích ngược quản lý cấu trúc trường) |
| `/installed-decks` | `InstalledDecksPage` | Lazy | `<RequireAuth />` | Canonical | Quản lý các bộ thẻ đã tải/cài đặt từ Marketplace |
| `/installed-decks/:installId/updates/:releaseId` | `InstalledDeckUpdatePage` | Lazy | `<RequireAuth />` | Canonical | Params: `:installId`, `:releaseId` (Giao diện 3-way merge giải quyết xung đột khi update deck) |
| `/flashcards/shared-decks/:deckItemId/change-request` | `DeckChangeRequestPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:deckItemId` (Giao diện gửi đề xuất sửa đổi bộ thẻ đã cài) |
| `/flashcards/change-requests/incoming` | `ChangeRequestInboxPage` | Lazy | `<RequireAuth />` | Canonical | Query: `deck_item_id` (Hộp thư duyệt đề xuất sửa đổi của tác giả) |
| `/flashcards/change-requests/:requestId` | `ChangeRequestDetailPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:requestId` (Chi tiết và diff phê duyệt đề xuất sửa đổi) |
| `/worksheets` | `WorksheetsPage` | Lazy | `<RequireAuth />` | Canonical | Query: `deckId` \| `deck_id` (Deck ID), `deckName` \| `deck_name` (Tiêu đề deck) |
| `/audio/generate` | `DeckAudioGeneratorPage` | Lazy | `<RequireAuth />` | Canonical | Studio quét và tạo audio hàng loạt (VoiceVox / Kokoro TTS) |
| `/flashcards/sync` | `AnkiSyncPage` | Lazy | `<RequireAuth />` | Canonical | Cầu nối Yomitan / AnkiConnect đồng bộ 1-click |
| `/sync` | `AnkiSyncPage` | Lazy | `<RequireAuth />` | Direct Alias | URL ngắn truy cập trực tiếp trang đồng bộ Anki |
| `/flashcards/import` | `FileImportPage` | Lazy | `<RequireAuth />` | Canonical | Trình nhập file CSV/TSV/APKG. Query: `deck_id` (deck đích) |
| `/import` | `FileImportPage` | Lazy | `<RequireAuth />` | Direct Alias | URL ngắn truy cập trực tiếp wizard nhập file |
| `/creator/decks/:itemId/releases/new` | `ReleaseBuilderPage` | Lazy | `<RequireCreator />` | Canonical | Param: `:itemId` (Creator đóng gói và xuất bản release mới) |
| `/settings/goals` | `StudyGoalsPage` | Lazy | `<RequireAuth />` | Canonical | Thiết lập mục tiêu học tập hàng ngày (thẻ mới, ôn tập) |
| `/settings/mcp-tokens` | `McpTokensPage` | Lazy | `<RequireAuth />` | Canonical | Quản lý API Access Token cho Claude Desktop / Cursor AI |
| `/settings/yomitan` | `YomitanTokensPage` | Lazy | `<RequireAuth />` | Canonical | Quản lý token xác thực tiện ích Yomitan mining |
| `/feedback` | `FeedbackPage` | Lazy | `<RequireAuth />` | Canonical | Query: `tab` (`'my-tickets'` \| `'create'`) |
| `/tickets` | `FeedbackPage` | Lazy | `<RequireAuth />` | Direct Alias | Query: `tab` (URL ngắn truy cập trung tâm vé hỗ trợ) |
| `/support/feedback` | `FeedbackPage` | Lazy | `<RequireAuth />` | Direct Alias | Query: `tab` (URL phân cấp truy cập phản hồi hỗ trợ) |
| `/tickets/:id` | `UserTicketDetailPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:id` (Chi tiết vé hỗ trợ và trao đổi của người dùng) |
| `/marketplace/decks` | `SharedDecksPage` | Lazy | `<RequireAuth />` | Canonical | Chợ chia sẻ và giao dịch bộ thẻ |
| `/marketplace/decks/publish` | `MarketplacePublishDeckPage` | Lazy | `<RequireAuth />` | Canonical | Query: `deck_id`, `edit` (`'1'`) |
| `/marketplace/decks/:id` | `SharedDeckDetailPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:id`. Query: `code`, `key` (Mã kích hoạt / License Key) |
| `/flashcards/shared-decks/:id` | `SharedDeckDetailPage` | Lazy | `<RequireAuth />` | Direct Alias | Param: `:id` (URL tương thích ngược xem chi tiết shared deck) |
| `/marketplace/note-types` | `SharedNoteTypesPage` | Lazy | `<RequireAuth />` | Canonical | Chợ chia sẻ mẫu thẻ |
| `/marketplace/note-types/publish` | `MarketplacePublishNoteTypePage` | Lazy | `<RequireAuth />` | Canonical | Query: `id`, `edit` (`'1'`) |
| `/marketplace/note-types/:id` | `SharedNoteTypeDetailPage` | Lazy | `<RequireAuth />` | Canonical | Param: `:id` (ID mẫu thẻ trên marketplace) |
| `/flashcards/shared-note-types/:id` | `SharedNoteTypeDetailPage` | Lazy | `<RequireAuth />` | Direct Alias | Param: `:id` (URL tương thích ngược xem chi tiết shared note type) |
| `/orders` | `OrdersPage` | Lazy | `<RequireAuth />` | Canonical | Lịch sử đơn hàng mua học liệu qua PayOS |
| `/profile` | `ProfilePage` | Lazy | `<RequireAuth />` | Canonical | Trang cá nhân của người dùng hiện tại |
| `/profile/:username` | `ProfilePage` | Lazy | `<RequireAuth />` | Canonical | Param optional: `:username` (Trang cá nhân công khai của tác giả) |
| `/wallet` | `WalletPage` | Lazy | `<RequireAuth />` | Canonical | Quản lý số dư, lịch sử giao dịch và rút tiền của creator |
| `/admin/analytics` | `AdminAnalyticsPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Dashboard phân tích KPI tài chính, tăng trưởng và gắn kết |
| `/admin/users` | `AdminUsersPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý người dùng, trạng thái kích hoạt và phân quyền |
| `/admin/payments` | `AdminPaymentsPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Bảng kiểm soát giao dịch, đơn hàng PayOS và xử lý hoàn tiền |
| `/admin/fees` | `AdminFeesPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý biểu phí hoa hồng sàn và chính sách chiết khấu |
| `/admin/tts` | `AdminTtsPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý và cấu hình VoiceVox / TTS providers hệ thống |
| `/admin/image-library` | `AdminImageLibraryPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý kho hình ảnh hệ thống dùng chung |
| `/admin/permissions` | `AdminPermissionsPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý phân quyền đặc biệt. Query: `selected_ids` |
| `/admin/mcp-tokens` | `AdminMcpTokensPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Giám sát toàn bộ API token MCP cấp cho AI trên hệ thống |
| `/admin/support` | `AdminSupportConfigPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Cấu hình tài khoản ngân hàng, mã QR và thông tin ủng hộ |
| `/admin/tickets` | `AdminTicketsPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Hộp thư quản trị tiếp nhận và giải quyết vé hỗ trợ người dùng |
| `/admin/tickets/:id` | `AdminTicketDetailPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Param: `:id` (Xử lý chi tiết vé hỗ trợ cụ thể) |
| `/admin/taxonomy` | `AdminTaxonomyPage` | Lazy | `<RequireAuth />` (Server Role Enforced) | Canonical | Quản lý cây danh mục, cấp độ JLPT, môn học, mappings |
| `*` | `NotFoundPage` | Eager | Public | Catch-all | Trang 404 cho mọi URL không khớp với bất kỳ tuyến đường nào |

#### 4.1.B Bảng 18 Tuyến đường Chuyển hướng Phía Client (`<Navigate replace />` Redirect Routes)

Bảng dưới đây kiểm kê chính xác 18 tuyến đường sử dụng component `<Navigate to="..." replace />` trong `App.tsx`. Khi người dùng truy cập các URL này, React Router sẽ tự động thay thế entry trong trình duyệt và điều hướng tức thời về URL chuẩn tương ứng mà không làm gãy history stack:

| STT | Tuyến đường Nguồn (Source Path) | Tuyến đường Đích Chuẩn (Target Canonical URL) | Vị trí Khai báo (`App.tsx`) | Flag Điều hướng | Mục đích & Nguồn gốc Lịch sử |
|:---:|---|---|:---:|:---:|---|
| 1 | `auth/verify-email` | `/verify-email` | Dòng 347–349 | `replace: true` | URL xác thực email từ các template email phiên bản cũ |
| 2 | `support-donation` | `/support` | Dòng 353–355 | `replace: true` | Trang ủng hộ cũ được hợp nhất vào Trung tâm Hỗ trợ & Quyên góp |
| 3 | `help` | `/guide` | Dòng 371 | `replace: true` | Shortcut URL trợ giúp người dùng phổ biến |
| 4 | `guides` | `/guide` | Dòng 372 | `replace: true` | URL dạng số nhiều hướng về thư viện hướng dẫn |
| 5 | `guide/tts-key` | `/guide/audio/cloud-tts-keys` | Dòng 373 | `replace: true` | URL bookmark hướng dẫn cấu hình khóa API TTS |
| 6 | `guides/tts-key` | `/guide/audio/cloud-tts-keys` | Dòng 375–377 | `replace: true` | Biến thể dạng số nhiều của hướng dẫn cấu hình TTS key |
| 7 | `help/tts-key` | `/guide/audio/cloud-tts-keys` | Dòng 379–381 | `replace: true` | Biến thể tiền tố `help/` của hướng dẫn cấu hình TTS key |
| 8 | `guides/flama-audio` | `/guide/flama-audio` | Dòng 384–386 | `replace: true` | Biến thể dạng số nhiều hướng dẫn Flama Audio Desktop |
| 9 | `help/flama-audio` | `/guide/flama-audio` | Dòng 388–390 | `replace: true` | Biến thể tiền tố `help/` hướng dẫn Flama Audio Desktop |
| 10 | `vocabulary/browse` | `/browse` | Dòng 409–411 | `replace: true` | URL tra cứu từ vựng từ hệ thống Flask/Jinja server-rendered cũ |
| 11 | `flashcards/study` | `/study` | Dòng 414–416 | `replace: true` | URL học thẻ SRS từ phiên bản Flashcards V1 |
| 12 | `flashcards/installed-decks` | `/installed-decks` | Dòng 455–457 | `replace: true` | URL quản lý bộ thẻ đã cài đặt từ phiên bản Flashcards V1 |
| 13 | `audio` | `/audio/generate` | Dòng 480 | `replace: true` | Shortcut URL ngắn trỏ vào Studio sinh âm thanh TTS |
| 14 | `flashcards/audio` | `/audio/generate` | Dòng 483–485 | `replace: true` | URL sinh âm thanh thẻ từ phiên bản Flashcards V1 |
| 15 | `goals` | `/settings/goals` | Dòng 516–518 | `replace: true` | Shortcut URL ngắn trỏ vào Cài đặt mục tiêu học tập |
| 16 | `mcp-tokens` | `/settings/mcp-tokens` | Dòng 544–546 | `replace: true` | Shortcut URL ngắn trỏ vào Cài đặt MCP Access Tokens cho AI |
| 17 | `admin` | `/admin/analytics` | Dòng 583 | `replace: true` | URL gốc quản trị tự động chuyển vào dashboard phân tích mặc định |
| 18 | `home` | `/dashboard` | Dòng 628 | `replace: true` | URL bookmark `/home` truyền thống trỏ về `/dashboard` người dùng |

*Ghi chú đặc biệt*: Các tuyến đường như `flashcards/note-types`, `flashcards/note-types/guide`, `flashcards/note-types/:id`, `flashcards/shared-decks/:id`, `/sync`, `/import`, `/tickets`, `/support/feedback` **KHÔNG PHẢI** là redirect routes mà là **Direct Component Aliases** (hiển thị component trực tiếp tại URL đó như đã quy định tại Bảng 4.1.A).

### 4.2 Cơ chế Kiểm soát Quyền (Access Guards & Availability Redirect)
1. **`RequireAuth` (`features/auth/components/RequireAuth.tsx`)**:
   - Kiểm tra dữ liệu phiên qua `useBootstrap()`.
   - Nếu chưa đăng nhập: Lưu URL hiện tại `next = ${location.pathname}${location.search}` và chuyển hướng sang `/login?next=...` với flag `replace: true`.
2. **`RequireCreator` (`features/auth/components/RequireCreator.tsx`)**:
   - Kiểm tra quyền: `data?.user?.is_admin || data?.user?.role?.code === 'creator'`.
   - Nếu không đủ quyền: Tự động điều hướng về `/dashboard` với flag `replace: true`.
3. **Phân quyền Quản trị Admin (`/admin/*`) (Làm rõ theo R8)**:
   - Giao diện Client: Tuyến đường `/admin/*` trên router client hiện tại được bảo vệ bởi `<RequireAuth />` để đảm bảo đã đăng nhập. Menu điều hướng Admin chỉ render khi `user?.is_admin === true`.
   - Tầng API Backend Enforcement: Toàn bộ quyền truy cập dữ liệu và thao tác quản trị được kiểm soát và cưỡng chế bởi Flask backend (`@admin_required` / `@login_required`); nếu tài khoản không có quyền admin, backend trả về HTTP 403 Forbidden. Quá trình refactor cấu trúc tuyệt đối **KHÔNG tự ý bổ sung thêm guard client-side** ngoài baseline hiện có.
4. **Backend Availability Guard (`shared/api/backendAvailability.ts`)**:
   - Tự động bắt các mã lỗi HTTP Gateway: 502, 503, 504, 521, 522, 523, 524.
   - Lưu URL vào `sessionStorage` (`flama:maintenance:return-path`) và chuyển hướng sang `/maintenance`. Khi backend hoạt động trở lại, tự động phục hồi người dùng về đúng trang đang thao tác dở.

### 4.3 Ma trận TanStack Query Keys, Cache Identity và Phân tích Dual Bootstrap

#### A. Trọng điểm Phân kỳ Cache Bootstrap và Hợp đồng Wire Thực tế (R2 Resolution):
- **Chuẩn hóa Query Key**: Hằng số query key chuẩn duy nhất trong toàn hệ thống được định nghĩa tại `shared/api/bootstrap.ts`:
  ```typescript
  export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const
  ```
- **Hiện trạng 7 file gọi hardcoded `['bootstrap']`**: Cả 7 file (`useBrowseState.ts`, `useAnkiSyncPage.ts`, `AnkiSyncTab.tsx`, `AvatarUploadModal.tsx`, `EmailVerificationDialog.tsx`, `ProfileEditDialog.tsx`, `VerifyEmailPage.tsx`) cần được đồng bộ sử dụng hằng số `bootstrapQueryKey`.
- **Hợp đồng Wire & Transport Thực tế**:
  - Endpoint backend thực tế: `GET ${API_BASE_URL}/session` với tham số `{ includeTimezone: false }`.
  - Phương thức gọi: `apiRequest<SessionResponse>` từ `shared/api/client.ts` (`apiJson` chỉ dùng cho mutations).
  - Quy trình Response Mapping: Payload raw `SessionResponse` được biến đổi qua `toBootstrap(payload)` để tạo `FrontendBootstrap`:
    - Gọi `setCsrfToken(payload.csrf_token)`.
    - Kiểm tra `isAdmin = Boolean(payload.user?.is_admin)`.
    - Gán `links` (chỉ mở admin links khi `isAdmin === true`).
    - Khởi tạo `messages: []`, `support_contact_email: ''`, `api_version: 'v1'`.

#### B. Ma trận Toàn bộ TanStack Query Keys Theo 16 Miền Chức năng (Đầy đủ 100%):

Toàn bộ 413 tệp mã nguồn frontend tiêu thụ hơn 75 biểu thức `queryKey`. Bảng dưới đây phân loại chính xác theo 16 miền nghiệp vụ:

| Miền Nghiệp vụ (Domain) | Cấu trúc Query Key | Tệp / Hook Tiêu thụ | Mục đích Dữ liệu & Cache Policy |
|---|---|---|---|
| **1. Bootstrap** | `['frontend', 'bootstrap']` | `useBootstrap()`, `MaintenancePage` | Thông tin phiên người dùng, feature flags, system config (Canonical) |
| | `['bootstrap']` | `useBrowseState`, `ProfileEditDialog`... (7 files) | Phiên bản hardcoded legacy (cần thống nhất về `bootstrapQueryKey` ở C01) |
| **2. Dashboard** | `['frontend', 'dashboard']` / `['dashboard']` | `DashboardPage`, `useDashboardPage` | Tổng quan số thẻ cần ôn, due cards, cây bộ thẻ học tập |
| | `['frontend', 'dashboard', 'overview', year]` | `DashboardPage` | Bản đồ nhiệt (Activity Heatmap) học tập theo năm |
| **3. Statistics** | `['frontend', 'statistics', 'config']` | `StatisticsPage` | Cấu hình hiển thị thống kê và deck selector |
| | `['frontend', 'statistics', 'overview', year]` | `StatisticsPage` | Báo cáo tổng quan số lượng thẻ học trong năm |
| | `['stats', 'today-future', filters]` | `useStatistics` | Dự báo khối lượng ôn tập SRS theo ngày (Forecast chart) |
| | `['stats', 'study-time', filters]` | `useStatistics` | Biểu đồ phân bổ thời gian học tập và tốc độ phản xạ |
| **4. Browse & Vocab** | `['browse', 'decks']` | `useBrowseState` | Danh sách cây bộ thẻ phục vụ bộ lọc tìm kiếm |
| | `['browse', 'cards', query, deckId, status, sortBy, sortDir, page, perPage]` | `useBrowseState` | Danh sách thẻ tìm kiếm với đầy đủ tham số phân trang, bộ lọc và chiều sắp xếp (`sortBy`, `sortDir`) (R5 Parity) |
| | `['browse', 'card-detail', activeCardId]` | `useBrowseState`, `StudyQuickEditDialog` | Chi tiết nội dung trường, tags, và metadata của 1 thẻ |
| | `['browse', 'card-detail-sample', sampleCardId]` | `useBrowseState` | Dữ liệu thẻ mẫu xem trước |
| | `['voicevox-profile']` | `useBrowseState` | Cấu hình endpoint và profile kết nối VoiceVox TTS |
| | `['voicevox-voices', ttsApiKey]` | `useBrowseState` | Danh sách giọng đọc khả dụng từ VoiceVox engine |
| | `['browse', 'stroke-modal-card-detail', targetCardId]` | `BrowseStrokeModal` | Nội dung Kanji của thẻ để dựng nét viết |
| | `['stroke-preview', sampleText, locale, maxChars]` | `BrowseStrokeModal` | Dữ liệu SVG render động thứ tự nét viết Kanji |
| | `['stroke-estimate', ...]` | `BrowseStrokeModal` | Ước tính thời gian và chi phí sinh animation nét vẽ |
| **5. Study Session** | `['study', 'template', abi, templateId, version]` | `queries.ts`, `useStudySession` | CSS/HTML artifact cache của Template mẫu thẻ (StaleTime: vô hạn) |
| | `['study', 'content', abi, cardId, templateId, contentId, version]` | `queries.ts`, `useStudySession` | Nội dung trường và thẻ đã biên dịch sang HTML an toàn |
| **6. Note Types** | `['note-types']` | `NoteTypeManagerPage`, `useBrowseState` | Danh sách toàn bộ Note Types của người dùng và hệ thống |
| | `['note-type-detail', noteTypeId]` | `NoteTypeDetailPage`, `NoteTypeFieldsPage` | Thông tin chi tiết mẫu thẻ, CSS, và danh sách template mặt trước/sau |
| | `['note-type-fields', noteTypeId]` | `NoteTypeFieldsPage` | Danh sách định nghĩa các trường dữ liệu và thứ tự hiển thị |
| **7. Marketplace** | `['marketplace', mode, query, category, domain, subject, level, diff, pricing, sort, page, perPage]` | `SharedDecksPage`, `SharedNoteTypesPage` (`MarketplacePages.tsx`) | Danh mục học liệu chia sẻ (dùng chung cho cả `mode='decks'` và `mode='note_types'` với 11 tham số lọc/phân trang) (R5 Parity) |
| | `['shared-deck-detail', id]` | `SharedDeckDetailPage` | Chi tiết bộ thẻ marketplace, thông tin tác giả, giá bán |
| | `['shared-deck-preview', id, templateId, sampleNoteId]` | `SharedDeckDetailPage` | Thẻ mẫu xem trước trong bộ thẻ đang xem |
| | `['shared-note-type-detail', id]` | `SharedNoteTypeDetailPage` | Chi tiết mẫu thẻ chia sẻ |
| | `['shared-note-type-preview', id, selectedTemplateId]` | `SharedNoteTypeDetailPage` | Xem trước giao diện mẫu thẻ chia sẻ |
| | `['my-decks-for-publish']` | `MarketplacePublishDeckPage` | Danh sách bộ thẻ cá nhân đủ điều kiện đăng lên chợ |
| | `['my-note-types-for-publish']` | `MarketplacePublishNoteTypePage` | Danh sách mẫu thẻ cá nhân đủ điều kiện đăng lên chợ |
| | `['deck-access-keys', deckItemId]` | `DeckAccessKeysManager` | Quản lý mã kích hoạt (license keys) của tác giả bộ thẻ |
| | `['deck-key-redemptions', deckItemId, page]` | `DeckAccessKeysManager` | Lịch sử người mua kích hoạt license keys |
| | `['shared-deck-auto-publish', id]` | `SharedDeckDetailPage` | Trạng thái bật/tắt tự động xuất bản phiên bản mới |
| | `['payment-result', paymentOrderId, supportProviderOrderCode, isAnon]` | `PaymentResultPage` | Đối soát và kiểm tra trạng thái thanh toán PayOS |
| | `['taxonomy-schema', contentType]` | `MarketplacePages` | Schema cây danh mục phục vụ wizard đăng bài |
| **8. Support & Tickets** | `['user', 'my-tickets']` | `FeedbackPage`, `UserTicketDetailPage` | Danh sách các vé hỗ trợ do người dùng hiện tại gửi |
| | `['user', 'ticket-detail', id]` | `UserTicketDetailPage` | Lịch sử tin nhắn trao đổi và phản hồi của vé hỗ trợ |
| | `['support-donation-status', paymentOrderId, supportOrderCode]` | `SupportPage` | Polling trạng thái thanh toán ủng hộ PayOS (chu kỳ 4s) |
| | `['support-donation']` | `SupportPage` | Cấu hình các gói ủng hộ, tài khoản ngân hàng và mã QR |
| | `['support-modal-status', modalOrderCode, modalOrderId]` | `SupportPage` | Trạng thái giao dịch ủng hộ qua popup modal |
| **9. Orders** | `['orders']` | `OrdersPage` | Lịch sử các đơn hàng mua học liệu PayOS của người dùng |
| | `['order-detail', selectedOrderId]` | `OrdersPage` | Chi tiết hóa đơn, mã thanh toán PayOS, học liệu đã mua |
| **10. Wallet** | `['wallet-summary']` | `WalletPage` | Số dư khả dụng, số dư chờ duyệt, tổng doanh thu tác giả |
| | `['wallet-transactions', page, filterType]` | `WalletTransactionsTable` | Lịch sử biến động số dư và lệnh rút tiền |
| **11. Profile** | `['profile']` | `ProfilePage`, `ProfileEditDialog`... | Thông tin cá nhân riêng tư, cài đặt bảo mật và thông báo |
| | `['public-profile', username]` | `ProfilePage` | Hồ sơ công khai của tác giả (bio, danh sách bộ thẻ đã tạo) |
| **12. OAuth & Apps** | `['oauth-consent-info', clientId, scope, redirectUri]` | `OAuthConsentPage` | Thông tin bên thứ ba và quyền yêu cầu trong màn hình ủy quyền |
| | `['oauth-endpoints-info']` | `useMcpOAuth` | Các URL endpoint OAuth của hệ thống Flama |
| | `['oauth-clients']` | `useMcpOAuth` | Danh sách các ứng dụng OAuth do người dùng đăng ký |
| | `['oauth-connected-apps']` | `useMcpOAuth` | Danh sách các ứng dụng bên thứ ba người dùng đã cấp quyền |
| **13. Onboarding** | `['onboarding-recommended-decks', targetSubject, frameworkLevel]` | `useOnboarding` | Danh sách bộ thẻ đề xuất dựa trên trình độ JLPT/môn học chọn lúc đầu |
| **14. Collaboration** | `['deck-releases', itemId]` | `ReleaseBuilderPage` | Lịch sử các phiên bản release của bộ thẻ |
| | `['deck-release-preview', itemId, filters]` | `ReleaseBuilderPage` | Bản xem trước thay đổi trước khi đóng gói release mới |
| | `['installed-deck-updates', installId]` | `InstalledDeckUpdatePage` | Kiểm tra cập nhật mới của bộ thẻ đã cài |
| | `['installed-deck-update-diff', installId, releaseId, filters]` | `InstalledDeckUpdatePage` | 3-way merge diff giữa phiên bản hiện tại và release mới |
| | `['installed-update-conflicts', rebaseId]` | `InstalledDeckUpdatePage` | Danh sách xung đột cần người dùng giải quyết thủ công |
| | `['deck-change-request', requestId, filters]` | `ChangeRequestDetailPage` | Chi tiết và diff của một đề xuất sửa đổi bộ thẻ |
| | `['incoming-deck-change-requests', deckItemId]` | `ChangeRequestInboxPage` | Hộp thư tiếp nhận các đề xuất sửa đổi từ cộng đồng |
| | `['active-deck-change-request', deckItemId, filters]` | `DeckChangeRequestPage` | Đề xuất sửa đổi đang soạn dở của người dùng |
| | `['local-deck-changes', deckItemId, filters]` | `DeckChangeRequestPage` | Các thay đổi cục bộ trên bộ thẻ đã cài đặt so với gốc |
| **15. MCP Tokens** | `['mcp', 'tokens', mode, search, status, page, userId]` | `McpTokensPage` | Danh sách API token cá nhân kết nối Claude / Cursor AI |
| | `['admin-mcp-summary']` | `AdminMcpTokensPage` | Thống kê số lượng token và mức độ sử dụng MCP toàn sàn |
| | `['admin-mcp-users', userSearch, userFilter, userPage]` | `AdminMcpTokensPage` | Danh sách người dùng đang sở hữu token MCP hệ thống |
| **16. Admin Domain** | `['admin', 'analytics', 'overview' \| 'growth' \| 'study-time' \| 'content-growth', params]` | `analyticsApi.ts` | Báo cáo phân tích KPI, tăng trưởng người dùng, nội dung |
| | `['admin', 'analytics', 'retention-cohorts', weeks]` | `analyticsApi.ts` | Báo cáo tỷ lệ giữ chân người dùng (Cohort retention) |
| | `['admin', 'users', search, status, page, perPage]` | `AdminUsersPage` | Quản lý danh sách người dùng và khóa/mở tài khoản |
| | `['admin', 'permissions-users']` | `AdminPermissionsPage` | Danh sách người dùng có quyền quản trị đặc biệt |
| | `['admin', 'payments-dashboard']` | `AdminPaymentsPage` | Tổng quan doanh thu PayOS, số giao dịch thành công |
| | `['admin', 'payments-orders', search, status, sort, page]` | `AdminPaymentsPage` | Danh sách đơn hàng thanh toán chi tiết |
| | `['admin', 'payments-order-detail', selectedOrderId]` | `AdminPaymentsPage` | Chi tiết một đơn hàng cụ thể |
| | `['admin', 'payments-transactions', search, status, sort, page]` | `AdminPaymentsPage` | Sổ cái dòng tiền và giao dịch thanh toán |
| | `['admin', 'payments-tx-detail', selectedTxId]` | `AdminPaymentsPage` | Chi tiết giao dịch thanh toán cụ thể |
| | `['admin', 'fees-overview']` | `AdminFeesPage` | Cấu hình mức phí hoa hồng sàn và doanh thu creator |
| | `['admin', 'tts-providers']` | `AdminTtsPage` | Cấu hình bật/tắt các dịch vụ TTS hệ thống |
| | `['admin', 'image-library', search, status, page, perPage]` | `AdminImageLibraryPage` | Quản lý kho hình ảnh hệ thống dùng chung |
| | `['admin', 'support-config']` | `AdminSupportConfigPage` | Cấu hình cổng ủng hộ, tài khoản PayOS và mã QR sàn |
| | `['admin', 'tickets', status, category, priority, search]` | `AdminTicketsPage` | Hộp thư điều phối và giải quyết khiếu nại người dùng |
| | `['admin', 'ticket-detail', id]` | `AdminTicketDetailPage` | Chi tiết vé hỗ trợ phía admin và trao đổi nội bộ |
| | `['admin-taxonomy-domains']` | `AdminTaxonomyPage` | Danh sách các miền tri thức (Domains) |
| | `['admin-taxonomy-subjects']` | `AdminTaxonomyPage` | Danh sách các môn học (Subjects: Japanese, English...) |
| | `['admin-taxonomy-frameworks']` | `AdminTaxonomyPage` | Danh sách các khung đánh giá (JLPT, CEFR...) |
| | `['admin-taxonomy-levels']` | `AdminTaxonomyPage` | Danh sách các cấp độ đánh giá (N5, N4, N3, N2, N1...) |
| | `['admin-taxonomy-options']` | `AdminTaxonomyPage` | Danh sách các thẻ phân loại và tùy chọn danh mục |
| | `['admin-taxonomy-mappings', subjectId, optionType]` | `AdminTaxonomyPage` | Bảng ánh xạ giữa môn học và các tùy chọn phân loại |
| **Shared Helper** | `['browse-decks-tree']` | `WorksheetDeckSelectStep`, `useDeckAudioScanner` | Cây thư mục bộ thẻ nạp dùng chung cho Worksheets và Audio Studio |

#### C. Quy tắc Invalidation Liên Miền (Cross-Domain Mutation Invalidation):

1. **Kết thúc lượt học (Study Session Commit)**:
   - Kích hoạt tại `useStudySession.ts` khi hoàn thành phiên học.
   - Invalidate đồng thời 3 keys: `['frontend', 'dashboard']`, `['frontend', 'statistics']`, `['stats']`.
2. **Cài đặt bộ thẻ Marketplace (Install Deck)**:
   - Kích hoạt khi người dùng tải hoặc mua thành công bộ thẻ.
   - Invalidate đồng thời 4 keys: `['shared-deck-detail', id]`, `['marketplace']`, `['installed-decks']`, `['dashboard']`.
3. **Hoàn thành luồng Onboarding ban đầu**:
   - Kích hoạt tại `useOnboarding.ts` khi người dùng hoàn tất chọn môn học và cài đặt bộ thẻ gợi ý.
   - Invalidate đồng thời 3 keys: `['dashboard']`, `['installed-decks']`, `['marketplace']`.
4. **Cập nhật Hồ sơ cá nhân & Avatar**:
   - Kích hoạt tại `ProfileEditDialog` và `AvatarUploadModal`.
   - Invalidate đồng thời: `['profile']`, `['public-profile']`, và `['bootstrap']`.
5. **Thao tác Mẫu thẻ (Note Types Mutations)**:
   - Thêm/sửa trường dữ liệu hoặc mẫu hiển thị: Invalidate `['note-types']`, `['note-type-detail', noteTypeId]`, và `['note-type-fields', noteTypeId]`.
6. **Xử lý Đề xuất Sửa đổi (Deck Change Request Resolution)**:
   - Khi tác giả chấp thuận đề xuất: Invalidate `['active-deck-change-request', deckItemId]`, `['incoming-deck-change-requests']`, và `['deck-release-preview', deckItemId]`.
7. **Xử lý Vé Hỗ trợ (Support Ticket Actions)**:
   - Tạo vé mới hoặc phản hồi: Invalidate `['user', 'my-tickets']`, `['user', 'ticket-detail', id]` (phía user) hoặc `['admin', 'tickets']`, `['admin', 'ticket-detail', id]` (phía admin).
8. **Thao tác Quản trị Hệ thống (Admin Mutations)**:
   - Sửa quyền hạn / khóa người dùng: Invalidate `['admin', 'users']`, `['admin', 'permissions-users']`.
   - Đổi phí sàn: Invalidate `['admin', 'fees-overview']`.
   - Bật/tắt TTS engine: Invalidate `['admin', 'tts-providers']`.
   - Cập nhật ảnh kho: Invalidate `['admin', 'image-library']`.
9. **Optimistic Pre-seeding (Deck Update Rebase)**:
   - Khi chuẩn bị cập nhật bản release mới, hệ thống gọi `queryClient.setQueryData(['installed-update-conflicts', result.rebase_id], ...)` để inject dữ liệu conflict vào cache trước, chống hiện tượng giật màn hình.

### 4.4 Danh mục Client Storage & Hợp đồng Kênh Truyền thông Trình duyệt (LocalStorage, SessionStorage, IndexedDB, BroadcastChannel)

Nhằm đảm bảo trải nghiệm người dùng không bị gián đoạn và trạng thái dữ liệu cục bộ được bảo toàn tuyệt đối 100% khi tái cấu trúc FSD, toàn bộ các khóa lưu trữ và định danh kênh truyền thông dưới đây là **hợp đồng bất biến (immutable contracts)**. Nghiêm cấm mọi hành vi đổi tên, xóa bỏ hoặc thay đổi kiểu dữ liệu của các khóa này trong suốt quá trình di chuyển.

#### A. Danh mục Toàn bộ 24 LocalStorage Keys (Bắt buộc giữ nguyên tên key và kiểu dữ liệu):

| STT | Tên LocalStorage Key | Hằng Số Khai Báo & File Nguồn | Miền Nghiệp Vụ / Kiểu Dữ Liệu | Mục Đích Sử Dụng & Hợp Đồng Bắt Buộc |
|:---:|:---|:---|:---|:---|
| 1 | `flama_audio_pairing_token` | `TOKEN_STORAGE_KEY`<br>`lib/flamaAudioClient.ts:10` | Audio / String | Token xác thực máy trạm với Flama Audio Desktop companion (port 4791). |
| 2 | `flama_local_audio_settings_v1` | `LOCAL_AUDIO_STORAGE_KEY`<br>`features/audio/services/localAudioStorage.ts:51` | Audio / JSON Object (`LocalAudioSettings`) | Cấu hình kết nối TTS cục bộ (VoiceVox & Kokoro: voiceId, speed, pitch, volume, field mapping theo Note Type). |
| 3 | `flama_deck_audio_studio_settings_v1` | `DECK_AUDIO_STUDIO_STORAGE_KEY`<br>`features/audio/services/deckAudioSettingsStorage.ts:23` | Audio / JSON Object (`DeckAudioStudioSettings`) | Cấu hình Deck Audio Studio tạo audio hàng loạt (mode, defaultEngine, defaultVoice, volume, speed). |
| 4 | `flama_deck_audio_queue_v1` | `AUDIO_QUEUE_STORAGE_KEY`<br>`features/audio/services/audioQueueStorage.ts:3` | Audio / JSON Array (`AudioDeckJob[]`) | Lưu danh sách hàng đợi và tiến trình tạo audio ngầm của bộ thẻ khi người dùng chuyển trang hoặc reload. |
| 5 | `flama_deck_audio_concurrency_v1` | `AUDIO_CONCURRENCY_KEY`<br>`features/audio/services/audioQueueStorage.ts:4` | Audio / String Integer (`"1"` đến `"5"`) | Giới hạn số luồng worker sinh audio đồng thời (mặc định 3). |
| 6 | `flama_voicevox_api_key` | Literal Key<br>`features/browse/hooks/useBrowseState.ts:212` | Audio & Browse / String | API Key dịch vụ VoiceVox được người dùng lưu cục bộ. |
| 7 | `flama_voicevox_tts_settings_v1` | `BROWSE_TTS_STORAGE_KEY`<br>`features/browse/services/ttsSettingsStorage.ts:31` | Browse / JSON Object (`BrowseTtsSettings`) | Cấu hình giọng đọc TTS VoiceVox trong không gian tra cứu từ vựng Browse. |
| 8 | `flama_browse_per_page` | Literal Key<br>`features/browse/hooks/useBrowseState.ts:127` | Browse / String Integer (`"20"`, `"50"`, `"100"`, `"200"`, `"500"`) | Số lượng thẻ hiển thị trên mỗi trang trong danh sách Browse. |
| 9 | `flama:browse:editor-width` | Literal Key<br>`features/browse/components/BrowseCardEditor.tsx:17`<br>(và `shared/ui/SplitPane.tsx:43`) | Browse / String Float (px) | Kích thước độ rộng (pixel width) của panel soạn thảo thẻ inline bên phải trong màn hình Browse. |
| 10 | `flama_browse_stroke_settings_v1` | `STROKE_STORAGE_KEY`<br>`features/browse/services/strokeStorage.ts:11` | Browse / JSON Object (`StrokeSettings`) | Cài đặt thứ tự nét vẽ Kanji (locale `'ja'`, `'zh-CN'`, `'zh-TW'`, cờ overwrite). |
| 11 | `flama_dashboard_expanded_deck_ids` | `DASHBOARD_EXPANDED_DECKS_STORAGE_KEY`<br>`features/dashboard/hooks/useDeckTreeExpanded.ts:4` | Dashboard / JSON Array (`number[]`) | Danh sách ID các thư mục bộ thẻ đang được mở rộng (expanded) trên cây thư mục Dashboard. |
| 12 | `flama_dashboard_spotlight_tour_v1` | `DASHBOARD_TOUR_STORAGE_KEY`<br>`features/onboarding/constants.ts:11` | Dashboard / String (`"true"`) | Đánh dấu người dùng đã hoàn thành hướng dẫn Spotlight Tour trên trang Dashboard. |
| 13 | `flama_installed_decks_spotlight_tour_v1` | `DECKS_STORAGE_KEY`<br>`features/library/pages/LibraryPages.tsx:39` | Library / String (`"true"`) | Đánh dấu đã xem hướng dẫn tại trang quản lý bộ thẻ đã cài đặt (Installed Decks). |
| 14 | `flama_marketplace_spotlight_tour_v1` | `MARKET_STORAGE_KEY`<br>`features/marketplace/pages/MarketplacePages.tsx:43` | Marketplace / String (`"true"`) | Đánh dấu đã xem hướng dẫn Spotlight Tour của Marketplace. |
| 15 | `flama_notetype_spotlight_tour_v1` | `TOUR_STORAGE_KEY`<br>`features/note-types/pages/NoteTypeManagerPage.tsx:44` | Note Types / String (`"true"`) | Đánh dấu đã xem hướng dẫn tại trang Quản lý Loại Thẻ (Note Type Manager). |
| 16 | `flama_notetype_tour_completed_v1` | `STORAGE_KEY`<br>`features/note-types/components/NoteTypeTourGuide.tsx:13` | Note Types / String (`"true"`) | Đánh dấu đã hoàn thành toàn bộ các bước trong modal hướng dẫn Note Type. |
| 17 | `flama_guide_spotlight_tour_v1` | `GUIDE_STORAGE_KEY`<br>`features/note-types/pages/NoteTypeGuidePage.tsx:24` | Guide / String (`"true"`) | Đánh dấu đã xem hướng dẫn tại Trung tâm Hướng dẫn (Guide Center). |
| 18 | `flama_user_onboarding_preferences_v1` | `ONBOARDING_STORAGE_KEY`<br>`features/onboarding/constants.ts:9` | Onboarding / JSON Object (`OnboardingPreferences`) | Tùy chọn cá nhân hóa mục tiêu học tập hoàn thành trong Onboarding wizard. |
| 19 | `flama_onboarding_completed_v1` | `ONBOARDING_COMPLETED_KEY`<br>`features/onboarding/constants.ts:10` | Onboarding / String (`"true"`) | Cờ xác nhận người dùng đã hoàn thành tiến trình Onboarding ban đầu. |
| 20 | `flama_import_warn_non_empty_deck` | Literal Key<br>`features/import/hooks/useFileImportWizard.ts:142` | Import / String (`"true"` / `"false"`) | Cờ ghi nhớ cảnh báo khi người dùng import dữ liệu vào một bộ thẻ đã có sẵn thẻ. |
| 21 | `anki_nt_map_${modelName}` | Template Literal Key<br>`features/import/components/AnkiSyncTab.tsx:215` | Import / JSON Object (`Record<string, string>`) | Ánh xạ trường dữ liệu giữa Model Anki cục bộ và Note Type tương ứng trên Flama. |
| 22 | `flama_worksheet_preset_notetype_${noteTypeId}` | `STORAGE_PREFIX`<br>`features/worksheets/utils/worksheetStorage.ts:11` | Worksheets / JSON Object (`WorksheetPreset`) | Cấu hình preset in bài tập A4 (field mapping, layout, font, khổ giấy) theo từng Note Type. |
| 23 | `flama-study-lease-epoch:${scopeKey}` | `LEASE_EPOCH_PREFIX`<br>`features/study/session/studySessionLease.ts:1` | Study / String Integer (epoch counter) | Số nguyên epoch tăng dần quản lý quyền điều khiển phiên học SRS đa tab độc quyền. |
| 24 | `[dynamic storageKey]` | Dynamic Prop<br>`shared/ui/SplitPane.tsx:43` | UI Primitive / String Float (px) | Kích thước chia đôi màn hình kéo giãn (px) theo prop `storageKey` truyền vào component `SplitPane`. |

#### B. SessionStorage & Cookie Contracts:
1. **SessionStorage: `flama:maintenance:return-path`**:
   - File quản lý: `frontend/src/pages/MaintenancePage.tsx`.
   - Mục đích: Lưu URL người dùng đang truy cập trước khi server gặp sự cố kết nối hoặc bảo trì (502/503) để tự động phục hồi điều hướng khi hệ thống hoạt động trở lại.
2. **Cookie: `sidebar_state` (R8 Cookie Contract)**:
   - File quản lý: `frontend/src/components/ui/sidebar.tsx` (`useSidebar()`, `SidebarProvider`).
   - Định dạng: `document.cookie = 'sidebar_state=true|false; path=/; max-age=604800'` (`SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7` — 7 ngày).
   - Mục đích: Lưu trữ trạng thái thu gọn (`collapsed`) hoặc mở rộng (`expanded`) của thanh điều hướng chính `app-sidebar` trên trình duyệt, giữ nguyên trạng thái UI khi tải lại trang hoặc điều hướng giữa các màn hình. Khi G01 chuyển primitive này sang `shared/ui/shadcn/sidebar.tsx`, hợp đồng cookie này bắt buộc phải được bảo toàn 100%.

#### C. Danh mục Cơ sở Dữ liệu IndexedDB:
1. **`FlamaAnkiSyncDB_v2` (Version 1)**:
   - File quản lý: `frontend/src/lib/ankiIndexedDB.ts`.
   - Object Stores:
     - `'profiles'` (`keyPath: 'id'`): Lưu cấu hình `AnkiSyncProfile`.
     - `'noteStates'` (`keyPath: 'key'`): Lưu trạng thái đồng bộ từng thẻ Anki (`AnkiNoteSyncState`).
     - `'mediaStates'` (`keyPath: 'key'`): Lưu trạng thái đồng bộ file âm thanh/hình ảnh (`AnkiMediaSyncState`).
2. **`flama-study` (Version 2)**:
   - File quản lý: `frontend/src/features/study/session/sessionStore.ts`.
   - Object Stores:
     - `'sessions'` (`keyPath: 'scope_key'`): Lưu trạng thái phiên học đang hoạt động (`PersistedStudySession`), snapshot và danh sách events chưa commit.
     - `'session-quarantine'` (`keyPath: 'scope_key'`): Lưu trữ phiên học bị lỗi để cách ly kiểm tra.
   - Cơ chế Fallback: Khi trình duyệt chặn IndexedDB (chế độ ẩn danh Incognito), tự động chuyển sang lưu tạm trên RAM memory maps (`memoryFallback`, `memoryQuarantine`).

#### D. Hợp đồng Kênh Truyền thông Trình duyệt Đa Tab (BroadcastChannel Contracts):
Hệ thống sử dụng đúng 2 kênh `BroadcastChannel` chuẩn hóa để đồng bộ dữ liệu theo thời gian thực giữa các tab mà không cần tải lại trang:

1. **Kênh Đồng bộ Nội dung Học: `'flama_study_sync_channel'` (Tên cố định)**:
   - File gửi (Senders): `entities/flashcard/model/cardContentUpdates.ts` (qua app binding `studyContentSync.ts`) và `features/study/contentUpdates.ts` (khi sửa trường thẻ).
   - File nhận (Receivers): `frontend/src/features/study/hooks/useStudySession.ts` (lắng nghe để cập nhật session state trong RAM nếu có phiên học đang mở).
   - Hợp đồng Payload Thực tế (R5 Wire Parity):
     ```typescript
     // Sự kiện cập nhật trường thẻ (CARD_UPDATED):
     {
       type: 'CARD_UPDATED',
       cardId: string, // ID chuỗi ký tự theo chuẩn Wire và sessionStore (R5 Parity)
       noteId?: string | null,
       fieldValues: Record<string, string>,
       media?: StudyMediaArtifact[] // Mảng đối tượng artifact, không phải Record thô (R5 Parity)
     }
     ```
   - **Làm rõ về Template Immutability (R1 Resolution)**:
     - Trong active session lease, cấu trúc template là **bất biến**. Hàm `updateTemplateInSessions` trong `sessionStore.ts:616` và `updateTemplateContent` trong `useStudySession.ts:1243` **hoàn toàn là no-op** (được khóa chặt bởi `sessionStore.test.ts:127`).
     - Do đó, sender hiện tại **cố ý không phát sự kiện `TEMPLATE_UPDATED`** để tránh mutate snapshot dở dang; mọi listener tương thích ngược cũ (nếu còn) không được coi là bằng chứng rằng active session cho phép patch template. Template mới chỉ có hiệu lực khi mở phiên học mới.
   - Quy tắc an toàn: Mọi thao tác gửi/nhận kênh đều phải bọc trong khối `try { ... } catch {}` để đảm bảo hệ thống không bị crash trên các trình duyệt cũ hoặc webview hạn chế API.

2. **Kênh Nhượng quyền Phiên học: `'flama-study-handoff:v1:${scopeKey}'` (Tên động theo Scope Key)**:
   - Hằng số tiền tố: `export const HANDOFF_CHANNEL_PREFIX = 'flama-study-handoff:v1:'` (`features/study/hooks/useStudySessionLease.ts:11`).
   - Định dạng tên kênh: `${HANDOFF_CHANNEL_PREFIX}${currentScopeKey}` (Ví dụ: `flama-study-handoff:v1:deck:15`).
   - File quản lý: `frontend/src/features/study/hooks/useStudySessionLease.ts`.
   - Mục đích: Phối hợp cùng Web Locks API (`navigator.locks`) và LocalStorage epoch key để chuyển giao quyền học SRS độc quyền khi người dùng mở cùng một bộ thẻ trên tab khác.
   - Hợp đồng Payload (`HandoffMessage`):
     ```typescript
     export type HandoffMessage = {
       type: 'handoff-accepted' | 'handoff-rejected' | 'handoff-request' | 'handoff-forced'
       requester_id: string
       epoch?: number
     }
     ```
   - Hợp đồng Thời gian chờ (Timeouts): `HANDOFF_RESPONSE_TIMEOUT_MS = 8_000` (8 giây), `HANDOFF_COMPLETION_TIMEOUT_MS = 30_000` (30 giây).

### 4.5 Hợp đồng Web Worker, Đồng bộ Anki và Dịch vụ Đồng hành Ngoại vi
1. **Thuật toán SM-2 Scheduler trên Client**:
   - Định danh bất biến:
     ```typescript
     export const LEGACY_ANKI_ALGORITHM = Object.freeze({
       key: 'legacy-anki',
       version: '1.0.0',
       stateSchemaVersion: 'anki-card-state.v1',
       configSchemaVersion: 'scheduler-config.v1',
     })
     ```
   - Chạy đồng bộ trong React Session Orchestrator để xếp lịch lặp lại ngắt quãng (`Again`, `Hard`, `Good`, `Easy`), tính interval và ghi nhận sự kiện vào IndexedDB trước khi batch commit lên backend.
2. **Web Worker Đồng bộ Anki Desktop (`sync.worker.ts`)**:
   - File: `frontend/src/lib/sync.worker.ts`.
   - Khởi tạo tại `AnkiSyncTab.tsx` qua `new Worker(new URL('../../../lib/sync.worker.ts', import.meta.url), { type: 'module' })`.
   - Giao thức tin nhắn:
     - Main $\to$ Worker: `{ type: 'START_SYNC', payload: { deckName, modelName, fieldMapping, syncMode, flamaUserId, csrfToken, options } }`
     - Worker $\to$ Main: `{ type: 'PROGRESS', payload: ... }`, `{ type: 'COMPLETED', payload: ... }`, `{ type: 'ERROR', payload: { message } }`.
   - Worker không truy cập được LocalStorage; toàn bộ `anki_nt_map_*` phải được Main Thread đọc và inject vào `options` trước khi gửi message.
3. **Flama Connect Service (Cổng 4790 - Yomitan Bridge & MCP Server)**:
   - `http://127.0.0.1:4790/v1/flama-connect/${token}`: Tương thích 100% giao thức JSON-RPC của AnkiConnect (`version`, `deckNames`, `modelNames`, `addNote`, `canAddNotes`) phục vụ 1-click word mining từ Yomitan.
   - `http://127.0.0.1:4790/v1/mcp/${token}`: Cung cấp SSE transport cho các AI Clients (Claude Desktop, Cursor).
4. **Flama Audio Desktop Companion (Cổng 4791 - Local VoiceVox & Kokoro TTS)**:
   - URL: `http://127.0.0.1:4791` (xác thực qua Bearer Token `flama_audio_pairing_token`).
   - Endpoints: `GET /health`, `POST /v1/pairing/start`, `GET /v1/pairing/:pairingId`, `GET /v1/engines`, `GET /v1/voices`, `POST /v1/tts` (nhận `TtsRequest`, trả về binary WAV Blob).

---

## PHẦN 5: HIỆN TRẠNG TEST BASELINE VÀ KHOẢNG TRỐNG KIỂM THỬ (TEST GAPS)

### 5.1 Kết quả Thực thi Bộ Lệnh Chất lượng Baseline
Tất cả 4 lệnh kiểm tra chất lượng cốt lõi đã được chạy kiểm chứng thực tế trên repo:

| Lệnh Kiểm tra | Công cụ & Môi trường | Exit Code | Kết quả | Chi tiết Thực tế Ghi nhận |
|:---|:---|:---:|:---:|:---|
| `npm --prefix frontend run lint` | Oxlint linter trên 413 tệp | **0** | **PASS** | Hoàn thành trong 53ms. Ghi nhận **37 cảnh báo (warnings), 0 lỗi (errors)**. |
| `npm --prefix frontend run typecheck` | TypeScript compiler (`tsc -b --pretty`) | **0** | **PASS** | Hoàn thành với **0 lỗi kiểu dữ liệu**. Hệ thống type hoàn toàn hợp lệ. |
| `npm --prefix frontend run build` | Full production build (`tsc -b && vite build`) | **0** | **PASS** | Đóng gói thành công trong 2.90s. Sinh 69 bundles trong `dist/assets/`. Cảnh báo kích thước chunk > 500 kB tại `dist/assets/index-JGBZd6Je.js` (513.20 kB). |
| `.venv\Scripts\python.exe scripts/run_tests.py --list-modules` | Python modular test runner | **0** | **PASS** | Định danh **20 domain modules**, liên kết 213 test files backend và **50 test files frontend**. |

### 5.2 Phân loại và Đánh giá 37 Cảnh báo Linter Hiện hữu
37 cảnh báo hiện có được phân bổ chính xác theo 4 nhóm quy tắc sau:
1. `react(only-export-components)` (**25 cảnh báo**): Xuất component kèm theo constants hoặc hàm tiện ích trong cùng một file TSX (ảnh hưởng nhẹ đến Vite Fast Refresh HMR khi phát triển).
2. `react-hooks(exhaustive-deps)` (**6 cảnh báo**): Thiếu dependencies trong `useEffect` / `useCallback` (nổi bật nhất tại `DeckWorksheetModal.tsx` và `useStudySession.ts`).
3. `oxc(only-used-in-recursion)` (**5 cảnh báo**): Các hàm helper đệ quy cục bộ.
4. `eslint(no-useless-escape)` (**1 cảnh báo**): Ký tự escape dư thừa trong biểu thức chính quy regex.

*Nguyên tắc bảo vệ*: Quá trình refactor không được làm tăng thêm bất kỳ cảnh báo mới nào, đồng thời từng bước giải quyết các cảnh báo về Fast Refresh khi phân rã components.

### 5.3 Định danh Khoảng trống Kiểm thử (Test Gaps) trên 9 Feature Chưa có Test
Khảo sát phát hiện có đúng **9 feature hoàn toàn chưa có tệp kiểm thử tự động nào** (0 test files, 0 test LOC):

| STT | Feature Thiếu Test | Số tệp Source | LOC Source | Đánh giá Mức độ Rủi ro Khi Refactor |
|:---:|:---|:---:|:---:|:---|
| 1 | `auth` | 12 | 1.540 | **Cao**: Rủi ro mất session, lỗi điều hướng `next` parameter hoặc hỏng form đăng ký/đăng nhập. |
| 2 | `guide` | 13 | 3.749 | **Trung bình**: Chủ yếu là hiển thị markdown tĩnh và điều hướng tài liệu; rủi ro nằm ở `ContextHelpButton`. |
| 3 | `library` | 1 | 941 | **Cao**: Rủi ro hỏng luồng kiểm tra phiên bản cập nhật và trigger update cho deck đã cài từ Marketplace. |
| 4 | `note-types` | 8 | 2.662 | **Rất cao**: Trình soạn thảo template HTML/CSS thẻ; rủi ro hỏng live preview hoặc mất trường dữ liệu. |
| 5 | `oauth` | 2 | 422 | **Trung bình**: Giao diện cấp quyền ủy quyền OAuth2 consent. |
| 6 | `orders` | 1 | 280 | **Thấp**: Bảng hiển thị lịch sử đơn hàng PayOS. |
| 7 | `statistics` | 5 | 887 | **Trung bình**: Biểu đồ hiển thị thống kê thẻ due tương lai và thời gian học. |
| 8 | `support` | 5 | 2.767 | **Trung bình**: Form gửi ticket và hướng dẫn cài đặt TTS. |
| 9 | `wallet` | 6 | 475 | **Trung bình**: Bảng hiển thị số dư thu nhập và yêu cầu rút tiền của creator. |

### 5.4 Yêu cầu Bộ Kiểm thử Đặc tả Hành vi & Tiêu chuẩn Visual Chống Hồi quy (R7 Resolution)
1. **Thừa nhận Khoảng trống Kiểm thử Trực quan Hiện hữu (Visual Test Gaps)**:
   - Khảo sát xác nhận hiện trạng repo **hoàn toàn chưa có bộ kiểm thử visual snapshot tự động** cho 344 source files.
   - Các phương pháp kiểm tra cấu trúc DOM đơn thuần (DOM Snapshot) hoặc đo kích thước bounding box **KHÔNG ĐỦ** để chứng minh giữ nguyên 100% token màu OKLCH, dải gradient thương hiệu, font chữ, đổ bóng (box-shadow) và trạng thái hiển thị của các Radix UI portals/popovers.
2. **Quy trình Kiểm thử Trực quan Chống Hồi quy (Zero Visual Regression Protocol)**:
   - Đối với các gói di chuyển UI (G01, G05, v.v.): Bắt buộc phải thực hiện đối chiếu ảnh chụp màn hình (screenshot comparison) trước và sau khi refactor trên cùng fixture dữ liệu mẫu, kích thước viewport chuẩn (Desktop 1440x900, Mobile 375x667), cùng trạng thái animation.
   - **Môi trường Trình duyệt Cách ly (Isolated Chrome Profile)**: Mọi thao tác kiểm tra trình duyệt hoặc chạy Chrome DevTools MCP **BẮT BUỘC** phải sử dụng profile độc lập cô lập tại đường dẫn:
     `C:\Users\chung\.gemini\chrome-profiles\flama-devtools`
   - **RÀNG BUỘC SỐNG CÒN**: Tuyệt đối **KHÔNG ĐƯỢC PHÉP** mở, can thiệp hoặc truy cập vào profile Chrome cá nhân mặc định của người dùng nhằm bảo vệ dữ liệu cá nhân và tránh xung đột cookie/session.
3. **Chính sách Kiểm thử Thực tế Theo Ranh giới Kỹ thuật (Realistic Seam-Based Test Policy)**:
   - Phù hợp với test policy tinh gọn của repository: **KHÔNG bắt buộc** phải tốn tài nguyên viết characterization test suites đồ sộ cho toàn bộ 9 feature tĩnh/ít thay đổi khi chỉ thực hiện các thao tác di chuyển file thuần túy (pure 1-to-1 file moves) có shim bảo vệ.
   - Thay vào đó, tập trung nguồn lực kiểm thử tự động và characterization tests vào các **mối nối kỹ thuật trọng yếu (critical architectural seams)** có sự thay đổi về trách nhiệm, luồng dữ liệu hoặc vòng đời (như phân rã monolith `useBrowseState`, bóc tách `DeckWorksheetModal` / `printEngine`, hoặc đóng băng hợp đồng phiên học `useStudySession`).

---

## PHẦN 6: ĐỀ XUẤT PHẠM VI CHI TIẾT CHO GÓI G01 (SHARED PRIMITIVES & UTILITIES)

### 6.1 Mục tiêu và Ranh giới Kỹ thuật Gói G01 (Phân tách G01.a và G01.b theo R4)
- **Tên gói**: Gói G01 — Shared Primitives & Utilities Consolidation.
- **Agent chịu trách nhiệm thực thi**: Gemini (`agy` worker).
- **Mục tiêu**: Chuẩn hóa toàn bộ 8 Flama UI Primitives, 30 Shadcn Radix UI components và các tiện ích trung lập không mang nghiệp vụ vào tầng `src/shared/`.
- **Phân kỳ Thực thi Hai Giai đoạn An toàn (Phased Sub-packages)**:
  - **Gói G01.a (Neutral Utilities Consolidation)**: Gom cụm các tiện ích trung lập độc lập (`shared/lib/utils.ts`, `shared/lib/hooks/useMobile.ts`, `shared/lib/imageCompression.ts`) kèm thiết lập re-export shims tại vị trí cũ.
  - **Gói G01.b (Shadcn Primitives & Tooling Configuration)**: Gom cụm chính xác 30 Shadcn UI primitives về thư mục chuẩn duy nhất `src/shared/ui/shadcn/`, sửa đổi internal imports, thiết lập 30 re-export shims tại `src/components/ui/`, và đồng bộ cấu hình generator tại `frontend/components.json`.
- **Ràng buộc an toàn số 1**: Tạo lớp **Re-export Shim** tương thích ngược tại các vị trí cũ để 344 file mã nguồn và test callers hiện có tiếp tục compile bình thường, không gây ra diff hàng loạt làm đứt gãy working tree.

### 6.2 Danh sách Tệp Được phép Chỉnh sửa / Tạo mới (Whitelist G01.a & G01.b)
Gemini được cấp quyền rõ ràng để tạo mới, di chuyển và hiệu chỉnh các tệp nằm trong Whitelist sau:

#### A. Gói G01.a — Tiện ích Trung lập Dùng chung (`frontend/src/shared/lib/` & Shims):
1. `frontend/src/shared/lib/utils.ts` (Tạo mới: Tiện ích gộp class `cn`).
2. `frontend/src/lib/utils.ts` (Cấp quyền sửa thành Shim: `export * from '@/shared/lib/utils'`).
3. `frontend/src/shared/lib/hooks/useMobile.ts` (Tạo mới: Hook phát hiện màn hình di động `useIsMobile`).
4. `frontend/src/hooks/use-mobile.ts` (Cấp quyền sửa thành Shim: `export * from '@/shared/lib/hooks/useMobile'`).
5. `frontend/src/shared/lib/imageCompression.ts` & `imageCompression.test.ts` (Tạo mới / di chuyển: Nén ảnh client-side).
6. `frontend/src/lib/imageCompression.ts` (Cấp quyền sửa thành Shim: `export * from '@/shared/lib/imageCompression'`).
*(LƯU Ý R4: Giữ nguyên `frontend/src/lib/ankiHtmlSanitizer.ts` tại `lib/`, KHÔNG đưa vào G01; quyền xử lý thuộc về Codex trong gói C06.a).*

#### B. Gói G01.b — 30 Shadcn UI Primitives (`frontend/src/shared/ui/shadcn/` & Shims):
- **Thư mục Đích Chuẩn (Canonical Destination)**: `frontend/src/shared/ui/shadcn/<primitive>.tsx` (đúng 30 tệp, KHÔNG ghi nước đôi):
  `alert.tsx`, `avatar.tsx`, `badge.tsx`, `breadcrumb.tsx`, `button.tsx`, `card.tsx`, `chart.tsx`, `checkbox.tsx`, `collapsible.tsx`, `dialog.tsx`, `drawer.tsx`, `dropdown-menu.tsx`, `field.tsx`, `input.tsx`, `label.tsx`, `native-select.tsx`, `pagination.tsx`, `progress.tsx`, `scroll-area.tsx`, `select.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `skeleton.tsx`, `sonner.tsx`, `switch.tsx`, `table.tsx`, `tabs.tsx`, `textarea.tsx`, `tooltip.tsx`.
- **30 Tệp Shim Tương thích Ngược Cũ**: Cấp quyền rõ ràng cho Gemini sửa 30 tệp tại `frontend/src/components/ui/<primitive>.tsx` thành re-export shim:
  ```typescript
  export * from '@/shared/ui/shadcn/<primitive>'
  ```
- **Cập nhật Cấu hình Công cụ Sinh mã (Generator Tooling)**: Cấp quyền sửa tệp `frontend/components.json` để đồng bộ aliases:
  ```json
  "aliases": {
    "components": "@/components",
    "utils": "@/shared/lib/utils",
    "ui": "@/shared/ui/shadcn",
    "lib": "@/shared/lib",
    "hooks": "@/shared/lib/hooks"
  }
  ```

#### C. 8 Flama UI Primitives Chuẩn hóa (`frontend/src/shared/ui/`):
1. `SearchInput.tsx` & `SearchInput.test.tsx` (Bảo toàn cờ `isComposing` Japanese IME, badge phím tắt, loading spinner).
2. `ConfirmDialog.tsx` & `ConfirmDialog.test.tsx` (Bảo toàn Radix dialog accessibility, async loading spinner).
3. `StatusPill.tsx` & `StatusPill.test.tsx` (Bảo toàn 8 trạng thái CVA và token màu OKLCH).
4. `CodeSnippetBox.tsx` & `CodeSnippetBox.test.tsx` (Bảo toàn copy clipboard animation tích xanh, dark mode).
5. `FilterPillGroup.tsx` & `FilterPillGroup.test.tsx` (Bảo toàn horizontal scroll và keyboard navigation).
6. `ImageUploadDropzone.tsx` & `ImageUploadDropzone.test.tsx` (Bảo toàn dán ảnh clipboard `Ctrl+V` và nén ảnh).
7. `SplitPane.tsx` & `SplitPane.test.tsx` (Bảo toàn draggable handle và lưu vị trí vào LocalStorage).
8. `CardFieldsForm.tsx` & `CardFieldsForm.test.tsx` (Giữ nguyên tại đây như một shim cho đến khi Codex C02 tách Flashcard Entity).
9. `index.ts` & `index.test.ts` (Public API exports của `shared/ui`).

*(LƯU Ý R4: Các component dùng chung có nghiệp vụ/session như `Brand.tsx`, domain DTOs và shell layout KHÔNG nằm trong whitelist G01 mà do owner tương ứng xử lý).*

### 6.3 Danh sách Tệp và Thư mục Nghiêm cấm Chạm vào (Gate G01 Blacklist)

Mục tiêu duy nhất của Gói G01 là **chuẩn hóa và cô lập Shared Primitives / Utilities vào `src/shared/` và thiết lập các Re-export Shims tại vị trí cũ**. Gói G01 **TUYỆT ĐỐI KHÔNG REFACTOR CALLERS**. Mọi chỉnh sửa nằm ngoài Whitelist (Mục 6.2) sẽ ngay lập tức bị từ chối nghiệm thu:

1. **Toàn bộ các Thư mục Feature Nghiệp vụ (`frontend/src/features/**`)**:
   - Cấm tuyệt đối chỉnh sửa bất kỳ tệp nào trong `frontend/src/features/**` (bao gồm `admin`, `audio`, `auth`, `browse`, `dashboard`, `deck-collaboration`, `guide`, `import`, `library`, `marketplace`, `mcp`, `note-types`, `oauth`, `onboarding`, `orders`, `profile`, `settings`, `statistics`, `study`, `support`, `wallet`, `worksheets`).
   - Mọi feature components và hooks tiếp tục import từ đường dẫn cũ (`@/components/ui/...`, `@/lib/utils`...); các import này được đáp ứng trọn vẹn qua các shim mà không thay đổi bất kỳ ký tự nào trong `features/**`.
2. **Toàn bộ Tầng Pages & Views (`frontend/src/pages/**`)**:
   - Cấm sửa đổi các tệp `frontend/src/pages/**` (`StaticPages.tsx`, `MaintenancePage.tsx`...).
3. **Tầng App Root, Router & Entry Points (Thẩm quyền Codex C01, C03)**:
   - Cấm sửa đổi `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/app/**`, `frontend/index.html`.
4. **Tầng Network Transport & Session (Thẩm quyền Codex C01)**:
   - Cấm sửa đổi `frontend/src/shared/api/client.ts`, `bootstrap.ts`, `backendAvailability.ts`, `config/env.ts`.
5. **Toàn bộ Core Runtime, Storage, Anki Worker & Audio Client (Thẩm quyền Codex C02, C06, C08)**:
   - Cấm tuyệt đối sửa đổi `frontend/src/lib/anki*` (bao gồm `ankiHtmlSanitizer.ts`, `ankiIndexedDB.ts`, `ankiSyncEngine.ts`), `frontend/src/lib/sync.worker.ts`, `frontend/src/lib/flamaAudioClient.ts`.
6. **Tầng App Shell Layouts & Navigation (Thẩm quyền Gói G02 / C03)**:
   - Cấm sửa đổi `frontend/src/layouts/**` (`AppLayout.tsx`).
   - Cấm sửa đổi các layout components: `frontend/src/components/app-sidebar.tsx`, `site-footer.tsx`, `nav-main.tsx`, `nav-user.tsx`, `site-mascot.tsx`, `feedback-dialog.tsx`.
   *(Ngoại lệ duy nhất tại `components/`: 30 file shims trong `components/ui/*.tsx` đã được cấp quyền trong Whitelist).*
7. **Tệp Cấu hình Xây dựng Frontend (Build & Tooling Configuration)**:
   - Cấm can thiệp hoặc sửa đổi:
     - `frontend/package.json`, `frontend/package-lock.json`
     - `frontend/vite.config.ts`
     - `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`
     - `frontend/tailwind.config.js`, `frontend/postcss.config.js`
   *(Ngoại lệ duy nhất về tooling: `frontend/components.json` được cấp quyền cập nhật aliases theo Whitelist).*
8. **Dịch vụ Đồng hành Ngoại vi & Backend Python**:
   - Cấm chạm vào `connect_wsgi.py`, `flama-audio/**`, `scripts/**`, `tests/**`, `app/**`, `models/**`, `migrations/**`, `wsgi.py`.
9. **Kỷ luật Git Bất biến**:
   - TUYỆT ĐỐI KHÔNG tự ý `git checkout` chuyển nhánh.
   - TUYỆT ĐỐI KHÔNG chạy `git commit`, `git add`, `git reset`, `git restore`, `git stash`, hay `git push`.

### 6.4 Ranh giới Caller Scope và Cơ chế Re-export Shim Bắt buộc (Zero Caller Regression)

Để đảm bảo **không một file nào trong số các file source và test callers bị lỗi import hay đứt gãy kiểm thử** khi di chuyển primitives sang `src/shared/`, Gate G01 **bắt buộc phải duy trì lớp Re-export Shim tương thích ngược hoàn toàn tại các vị trí cũ**:

#### 1. Re-export Shims cho 30 Shadcn UI Primitives (`components/ui/*.tsx`):
Tại vị trí cũ `frontend/src/components/ui/<component>.tsx`, giữ nguyên file và tạo shim re-export tường minh:
```typescript
// Ví dụ: frontend/src/components/ui/button.tsx
export * from '@/shared/ui/shadcn/button'

// Ví dụ: frontend/src/components/ui/dialog.tsx
export * from '@/shared/ui/shadcn/dialog'
```
*Áp dụng đồng bộ cho toàn bộ 30 tệp UI*: `alert.tsx`, `avatar.tsx`, `badge.tsx`, `breadcrumb.tsx`, `button.tsx`, `card.tsx`, `chart.tsx`, `checkbox.tsx`, `collapsible.tsx`, `dialog.tsx`, `drawer.tsx`, `dropdown-menu.tsx`, `field.tsx`, `input.tsx`, `label.tsx`, `native-select.tsx`, `pagination.tsx`, `progress.tsx`, `scroll-area.tsx`, `select.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `skeleton.tsx`, `sonner.tsx`, `switch.tsx`, `table.tsx`, `tabs.tsx`, `textarea.tsx`, `tooltip.tsx`.
*Owner thu hồi shim*: Các shim này sẽ được duy trì cho đến khi các gói di chuyển feature tương ứng (G03–G09) hoàn tất việc chuyển đổi import trực tiếp sang `@/shared/ui/shadcn` hoặc `@/shared/ui`.

#### 2. Re-export Shim cho Tiện ích Lớp Gộp `cn` (`lib/utils.ts`):
Tại vị trí cũ `frontend/src/lib/utils.ts`, thiết lập shim trỏ sang `shared/lib/utils`:
```typescript
// frontend/src/lib/utils.ts
export * from '@/shared/lib/utils'
```
*Bảo vệ*: Hơn 150 callers trong `features/**` và `pages/**` đang gọi `import { cn } from '@/lib/utils'` tiếp tục compile bình thường.

#### 3. Re-export Shim cho Tiện ích Nén Ảnh Client-side (`lib/imageCompression.ts`):
Tại vị trí cũ `frontend/src/lib/imageCompression.ts`, thiết lập shim trỏ sang `shared/lib/imageCompression`:
```typescript
// frontend/src/lib/imageCompression.ts
export * from '@/shared/lib/imageCompression'
```
*Bảo vệ*: Các callers trong `shared/ui/ImageUploadDropzone.tsx`, `features/browse/MediaFieldPreview.tsx`, `features/support/FeedbackPage.tsx`.

#### 4. Re-export Shim cho Hook Nhận diện Màn hình Di động (`hooks/use-mobile.ts`):
Tại vị trí cũ `frontend/src/hooks/use-mobile.ts`, thiết lập shim trỏ sang `shared/lib/hooks/useMobile`:
```typescript
// frontend/src/hooks/use-mobile.ts
export * from '@/shared/lib/hooks/useMobile'
```
*Bảo vệ*: Callers trong `components/ui/sidebar.tsx` và `components/app-sidebar.tsx`.

### 6.5 Tiêu chí Nghiệm thu Khắt khe cho Gate G01 (Acceptance Criteria)
Gate G01 chỉ được đóng và nghiệm thu chuyển sang các gói tiếp theo khi vượt qua toàn bộ 7 tiêu chí:
1. **Typecheck Latch**: `npm --prefix frontend run typecheck` vượt qua với **0 lỗi (exit code 0)**.
2. **Lint Latch**: `npm --prefix frontend run lint` không phát sinh thêm bất kỳ lỗi hoặc cảnh báo mới nào.
3. **Build Latch**: `npm --prefix frontend run build:ci` đóng gói bundle thành công với exit code 0.
4. **Test Suite Latch**:
   - `npm --prefix frontend test -- shared/ui` đạt **100% pass (43/43 tests passed)**.
   - `npm --prefix frontend test -- imageCompression` đạt **100% pass**.
5. **Zero Visual Regression**: Đối chiếu ảnh chụp màn hình bằng Chrome profile cô lập (`C:\Users\chung\.gemini\chrome-profiles\flama-devtools`), giữ nguyên 100% styling CVA, token màu OKLCH, padding, border-radius, font-size và box-shadow.
6. **Zero Runtime Regression**: Cờ `isComposing` Japanese IME của `SearchInput`, cookie contract `sidebar_state` của `sidebar.tsx`, LocalStorage sync của `SplitPane` và Radix accessibility của `ConfirmDialog` hoạt động chuẩn mực.
7. **Bảo tồn Working Tree Git**: Không có commit mới trên working branch; toàn bộ working tree được bảo toàn nguyên vẹn.

---
*Tài liệu Master Specification G00 được hoàn thành và xác thực độc quyền bởi Worker G00 Updater (`worker_g00_updater`) tại mốc bàn giao Gate C00.*
