# BÁO CÁO KIỂM KÊ BASELINE VÀ BẢN ĐỒ MAPPING KIẾN TRÚC 6 TẦNG FSD (GÓI G00)
## Master Engineering Specification & Baseline Characterization for Flama React SPA Migration

- **Mã tài liệu**: `FLAMA-DOC-2026-FE-G00`
- **Phiên bản**: 1.0 (Chính thức)
- **Tác giả tổng hợp**: Worker 1 (`teamwork_preview_worker_g00_1`)
- **Nguồn khảo sát thực tế**:
  - Explorer 1: Báo cáo Kiểm kê Baseline Code và Lệnh Chất lượng Frontend (`teamwork_preview_explorer_g00_1`)
  - Explorer 2: Báo cáo và Catalog Kiến trúc 6 tầng FSD (`teamwork_preview_explorer_g00_2`)
  - Explorer 3: Báo cáo Runtime Contracts và Ranh giới Gate G01 (`teamwork_preview_explorer_g00_3`)
- **Tài liệu tham chiếu**:
  - `docs/plans/proposals/FLAMA_FRONTEND_CODEX_GEMINI_EXECUTION_PLAN_2026-10-04.md`
  - `docs/plans/proposals/FLAMA_FRONTEND_STRUCTURE_MIGRATION_PLAN_2026-10-03.md`
  - `skills/flama-frontend-architecture/SKILL.md`
  - `AGENTS.md`
- **Ngày phát hành**: 2026-10-04 (Asia/Tokyo)
- **Trạng thái**: Đã nghiệm thu khảo sát 100% Read-Only, sẵn sàng làm căn cứ kỹ thuật cho Codex và Gemini.

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
   - 4.4 Danh mục Client Storage & Hợp đồng Kênh Truyền thông Trình duyệt (LocalStorage, SessionStorage, IndexedDB, BroadcastChannel)
   - 4.5 Hợp đồng Web Worker, Đồng bộ Anki và Dịch vụ Đồng hành Ngoại vi
5. [PHẦN 5: HIỆN TRẠNG TEST BASELINE VÀ KHOẢNG TRỐNG KIỂM THỬ (TEST GAPS)](#phần-5-hiện-trạng-test-baseline-và-khoảng-trống-kiểm-thử-test-gaps)
   - 5.1 Kết quả Thực thi Bộ Lệnh Chất lượng Baseline
   - 5.2 Phân loại và Đánh giá 37 Cảnh báo Linter Hiện hữu
   - 5.3 Định danh Khoảng trống Kiểm thử (Test Gaps) trên 9 Feature Chưa có Test
   - 5.4 Yêu cầu Bộ Kiểm thử Đặc tả Hành vi (Characterization Suites)
6. [PHẦN 6: ĐỀ XUẤT PHẠM VI CHI TIẾT CHO GÓI G01 (SHARED PRIMITIVES & UTILITIES)](#phần-6-đề-xuất-phạm-vi-chi-tiết-cho-gói-g01-shared-primitives--utilities)
   - 6.1 Mục tiêu và Ranh giới Kỹ thuật Gói G01
   - 6.2 Danh sách Tệp Được phép Chỉnh sửa / Tạo mới (Whitelist)
   - 6.3 Danh sách Tệp và Thư mục Nghiêm cấm Chạm vào (Gate G01 Blacklist)
   - 6.4 Ranh giới Caller Scope và Cơ chế Re-export Shim Bắt buộc (Zero Caller Regression)
   - 6.5 Tiêu chí Nghiệm thu Khắt khe cho Gate G01 (Acceptance Criteria)

---

## PHẦN 1: GIT STATUS / CHECKPOINT VÀ CÁC THAY ĐỔI CẦN BẢO VỆ

### 1.1 Thông tin Nhánh và HEAD Commit Checkpoint
Toàn bộ khảo sát và lập kế hoạch di chuyển kiến trúc frontend Flama SPA được thực hiện trực tiếp trên workspace hiện tại:
- **Tên nhánh hiện tại**: `phase10/contraction-drop`
- **HEAD Commit SHA ban đầu**: `8ea41587fdd613272e9edd0dc675277950e5cee6`
- **Nhiệm vụ song song trên repo khi bắt đầu G00**: Agent Backend Decoupling Phase 10 (P10) thực hiện việc loại bỏ các bảng tiến trình học tập cũ đã nghỉ hưu (retired note progress tables) và hoàn thiện lớp bảo vệ dữ liệu MySQL.

> **CẬP NHẬT CHECKPOINT P10 (2026-10-04 00:23 JST)**:
> Agent P10 đã hoàn tất xuất sắc toàn bộ nhiệm vụ và đã commit an toàn vào nhánh `phase10/contraction-drop` tại **SHA `5b21b1b`** (*"feat(phase10): drop the five retired NOTE progress tables (P10-09 PR-B)"*).
> Toàn bộ 5 tệp staged, 13 tệp unstaged và các migration backend mô tả tại Mục 1.2 đã được sáp nhập vĩnh viễn vào lịch sử git của nhánh.
> **Hiện trạng working tree**: Thư mục backend, database models, migrations và toàn bộ `frontend/src/` hoàn toàn sạch sẽ (0 modified, 0 staged, 0 untracked source files). Nguy cơ xung đột working tree với P10 chính thức triệt tiêu 100%.

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
| 2 | `components/` | 36 | 4.104 | 1 | 126 | 37 | Chứa các shell layout component (`app-sidebar.tsx`, `site-footer.tsx`, `site-mascot.tsx`, `nav-main.tsx`, `nav-user.tsx`) và toàn bộ 29 primitives shadcn UI tại `components/ui/`. |
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
Khảo sát phát hiện 2 điểm vi phạm nguyên tắc kiến trúc đơn hướng nghiêm trọng:
1. **Tầng dùng chung (`shared`) phụ thuộc tầng ứng dụng (`app`)**:
   - `shared/api/bootstrap.ts` (dòng 2) gọi `import { appApi } from '../../app/api'`.
   - Trong khi đó, `app/api.ts` lại import DTO từ `features/auth`, `features/dashboard`, `features/statistics`.
   - *Hệ quả*: Tầng thấp nhất (`shared`) vô tình kéo theo toàn bộ ứng dụng và các domain feature, phá vỡ tính độc lập của các package.
2. **Tầng tiện ích (`lib`) phụ thuộc tầng nghiệp vụ (`features`)**:
   - `lib/ankiSyncEngine.ts` (dòng 8–9) gọi `import { ankiImportApi } from '@/features/import/api'`.
   - `lib/flamaAudioClient.ts` (dòng 1–7) gọi `import type { EnginePackageState... } from '@/features/audio/types'`.

---

## PHẦN 3: BẢNG MAPPING SOURCE -> TARGET 6 TẦNG FSD CHI TIẾT

### 3.1 Khung Kiến trúc 6 Tầng Chuẩn FSD và Quy tắc Đơn hướng
Hệ thống frontend mới chuẩn hóa theo 6 tầng Feature-Sliced Design (FSD):

```
frontend/src/
  ├── app/          [Tier 1] Khởi tạo ứng dụng, routing root, providers, styles toàn cục
  ├── pages/        [Tier 2] Các màn hình tương ứng với route của react-router
  ├── widgets/      [Tier 3] Các khối giao diện phức hợp ghép từ nhiều feature và entity
  ├── features/     [Tier 4] Các luồng hành vi tương tác và nghiệp vụ của người dùng
  ├── entities/     [Tier 5] Thực thể dữ liệu nghiệp vụ, DTO, schema và UI card nguyên tử
  └── shared/       [Tier 6] Primitives UI dùng chung, HTTP client, tiện ích và cấu hình
```

#### Quy tắc Đơn hướng Sắt đá ($N \to < N$):
1. **Chiều phụ thuộc**: Một tầng $N$ chỉ được phép import từ các tầng $< N$ (các tầng thấp hơn nó).
   - `pages` (2) $\to$ `widgets` (3), `features` (4), `entities` (5), `shared` (6).
   - `widgets` (3) $\to$ `features` (4), `entities` (5), `shared` (6).
   - `features` (4) $\to$ `entities` (5), `shared` (6). **Feature TUYỆT ĐỐI KHÔNG import Feature khác.**
   - `entities` (5) $\to$ `shared` (6). **Entity TUYỆT ĐỐI KHÔNG import Entity khác hoặc Feature.**
   - `shared` (6) **TUYỆT ĐỐI KHÔNG import bất kỳ tầng nào bên trên nó.**
2. **Rào chắn Public API (`index.ts`)**:
   - Mọi slice trong `widgets/`, `features/`, `entities/`, `shared/` bắt buộc phải có `index.ts`.
   - Các module bên ngoài CHỈ ĐƯỢC PHÉP import qua root slice (ví dụ: `@/entities/deck`, `@/features/study`), **nghiêm cấm** import sâu vào file nội bộ (như `@/features/study/session/sessionStore`).
   - Các file trong cùng một slice phải dùng đường dẫn tương đối (`./ui/...`, `./model/...`) và không được import qua `index.ts` của chính mình để tránh circular evaluation.

---

### 3.2 Bảng Phân bổ Định lượng 414 Tệp theo 6 Tầng Target

| FSD Tier | Thư mục Đích | Số lượng Tệp | Thành phần Cốt lõi bên trong |
|---|---|---:|---|
| **Tier 1: app** | `src/app/` | **6** | `App.tsx`, `main.tsx`, `index.css`, `RequireAuth`, `RequireCreator`, `vite-env.d.ts` |
| **Tier 2: pages** | `src/pages/` | **71** | 48 route pages trên toàn bộ 22 feature domains + các trang static/legal/404 |
| **Tier 3: widgets** | `src/widgets/` | **20** | `app-shell`, `worksheet-studio`, `mcp-token-manager`, `collaboration-diff`, `dashboard-workspace`, `browse-workspace`, `study-workspace`, `admin-analytics` |
| **Tier 4: features** | `src/features/` | **234** | Các luồng tương tác: `auth`, `browse`, `study`, `deck-management`, `note-editor`, `anki-sync`, `audio`, `marketplace-publish`, `deck-install`, `onboarding` |
| **Tier 5: entities** | `src/entities/` | **18** | **18 tệp mã nguồn hiện hữu chuyển đổi 1-to-1** (xem bảng chi tiết bên dưới).<br>*(Ghi chú: Các slice `support-ticket`, `order`, `wallet`, `user` là các **Planned Extractions** dự kiến bóc tách trong các gói C04–C07 / G03–G06)* |
| **Tier 6: shared** | `src/shared/` | **65** | 8 Flama UI primitives + 30 Shadcn UI primitives, HTTP client, `utils`, `imageCompression`, `env` |
| **TỔNG CỘNG** | `frontend/src/` | **414** | **Bao quát chính xác 100% toàn bộ cây thư mục nguồn frontend (331 source + 83 non-source/test/style).** |

#### Danh mục Chi tiết 18 Tệp Vật lý Hiện hữu Ánh xạ vào Tier 5 (`entities`):
Để đảm bảo tính nhất quán tuyệt đối giữa số liệu thống kê AST (414 tệp) và phân loại kiến trúc, danh mục 18 tệp nguồn hiện có được định tuyến trực tiếp vào 6 slices của Tier 5 như sau:

| Entity Slice Đích | Số tệp | Danh sách Tệp Nguồn Hiện tại trong Codebase |
|:---|:---:|:---|
| **`entities/flashcard`** | **9** | - `features/browse/components/MediaFieldPreview.tsx`<br>- `features/browse/components/MediaFieldPreview.test.tsx`<br>- `features/study/components/CardDisplay.tsx`<br>- `features/study/components/CardDisplay.test.tsx`<br>- `features/study/components/CardRendererFrame.tsx`<br>- `features/study/components/CardRendererFrame.test.tsx`<br>- `features/study/components/CardRendererHost.test.ts`<br>- `features/study/renderer/clientRenderer.ts`<br>- `features/study/renderer/clientRenderer.test.ts` |
| **`entities/deck`** | **3** | - `features/import/components/DeckSelectionTreeView.tsx`<br>- `features/import/components/DeckSelectionTreeView.test.tsx`<br>- `shared/components/StudyHeatmap.tsx` |
| **`entities/marketplace-item`** | **3** | - `features/marketplace/components/DeckCard.tsx`<br>- `features/marketplace/components/DeckCard.test.tsx`<br>- `features/marketplace/hooks/useTaxonomySchema.ts` |
| **`entities/mcp-token`** | **1** | - `features/mcp/types.ts` |
| **`entities/session`** | **1** | - `shared/api/bootstrap.ts` |
| **`entities/media`** | **1** | - `shared/api/noteMedia.ts` |
| **TỔNG CỘNG TIER 5** | **18** | **Đúng 18 tệp vật lý hiện hữu (11 source files + 7 test files). Khớp 100% với catalog mapping.** |

> **LÀM RÕ VỀ CÁC ENTITY SLICE DỰ KIẾN (PLANNED EXTRACTIONS)**:
> Các miền thực thể `support-ticket`, `order`, `wallet`, `user` được nêu trong thiết kế đích của FSD hiện **chưa có tệp vật lý độc lập** trong 414 tệp hiện tại. Các kiểu dữ liệu và thành phần UI của chúng hiện đang nằm phân tán bên trong các trang hoặc tính năng nguyên khối (ví dụ: `TicketItem` nằm trong `AdminTicketsPage.tsx`, các DTO đơn hàng nằm trong `OrdersPage.tsx`, DTO ví nằm trong `WalletPage.tsx`).
> Các slice này sẽ được tạo mới qua quy trình bóc tách (extraction) trong các gói triển khai tương ứng của Codex và Gemini (C04–C07 / G03–G06). Ví dụ: `TicketStatusBadge` (nêu tại Mục 3.5.D) là một UI primitive mới sẽ được trích xuất từ logic trạng thái vé hỗ trợ trong gói bóc tách admin/support.

### 3.3 Ma trận Chuyển đổi Chi tiết 22 Feature và Thành phần Chung

| Feature Hiện tại | Vị trí Đích (6 Tầng FSD) | Public Exports (`index.ts`) | Chiến lược Điều phối Phân công (Codex / Gemini) |
|---|---|---|---|
| **`admin`** | - `pages/admin/` (12 pages)<br>- `widgets/admin-analytics/`<br>- `features/admin-management/`<br>- `entities/support-ticket/` | `AdminAnalyticsWidget`, `AdminUsersManager`, `AdminTaxonomyManager` | - Gemini: Tách các page và controller UI cục bộ.<br>- Codex: Quản lý quyền, xử lý dòng tiền PayOS, ticket/token contracts. |
| **`audio`** | - `pages/audio/`<br>- `features/audio/`<br>- `entities/media/`<br>- `shared/lib/japanese/` | `LocalAudioDialog`, `useDeckAudioQueue`, `cleanTextForTts` | - Gemini: Tách UI dialogs và rule cards.<br>- Codex: Giữ desktop companion client (port 4791), queue storage, cancel token. |
| **`auth`** | - `pages/auth/` (5 pages)<br>- `app/router/guards/`<br>- `features/auth/`<br>- `entities/session/` | `AuthCard`, `useLoginForm`, `useRegisterForm`, `RequireAuth`, `RequireCreator` | - Gemini: Chuyển forms và auth views.<br>- Codex: Session bootstrap DTO, auth state, cookie/CSRF handling. |
| **`browse`** | - `pages/browse/`<br>- `widgets/browse-workspace/`<br>- `features/browse/`<br>- `features/note-editor/`<br>- `entities/flashcard/` | `BrowseWorkspace`, `useBrowseFilters`, `MediaFieldPreview`, `BrowseStrokeModal` | - Gemini: Chuyển toolbar, table, split sidebar, pagination UI.<br>- Codex: Phân rã 1.052 LOC `useBrowseState`, quản lý cache/selection/mutations. |
| **`dashboard`** | - `pages/dashboard/`<br>- `widgets/dashboard-workspace/`<br>- `features/deck-management/`<br>- `entities/deck/` | `DashboardWorkspace`, `DeckModals`, `StudyHeatmap`, `DeckTree` | - Gemini: Thực hiện pilot chuyển đổi UI và kéo thả deck tree.<br>- Codex: Chốt query contract và mutation invalidations. |
| **`deck-collaboration`** | - `pages/deck-collaboration/` (5 pages)<br>- `widgets/collaboration-diff/`<br>- `features/deck-collaboration/`<br>- `entities/deck/` | `DiffWorkspace`, `ChangeRequestStatusBadge`, `useDeckCollaboration` | - Gemini: Chuyển trang và diff layout.<br>- Codex: Quản lý thuật toán 3-way rebase, conflict resolution và overlay clone. |
| **`guide`** | - `pages/guide/`<br>- `widgets/guide-explorer/`<br>- `features/guide/`<br>- `shared/lib/guide/` | `ContextHelpButton`, `GuideArticleRenderer`, `McpToolsExplorer` | - Gemini: Chuyển toàn bộ views và static markdown data.<br>- Codex: Chuẩn hóa public export `ContextHelpButton` cho 8 caller features. |
| **`import`** | - `pages/import/`<br>- `features/import/`<br>- `features/anki-sync/`<br>- `entities/deck/` | `DeckSelectionTreeView`, `FileImportWizard`, `AnkiSyncTab` | - Gemini: Chuyển wizard import CSV/TSV và UI sync.<br>- Codex: Giữ AnkiConnect client, sync worker (`sync.worker.ts`), IndexedDB. |
| **`library`** | - `pages/library/`<br>- `features/deck-install/`<br>- `entities/marketplace-item/` | `InstalledDecksPage`, `useInstalledDecks` | - Gemini: Chuyển trang thư viện.<br>- Codex: Quản lý logic cập nhật phiên bản phát hành và overlay clone cutover. |
| **`marketplace`** | - `pages/marketplace/` (6 pages)<br>- `widgets/marketplace-catalog/`<br>- `features/marketplace-publish/`<br>- `features/deck-install/`<br>- `entities/marketplace-item/` | `DeckCard`, `MarketplaceCatalog`, `RedeemDeckKeyModal` | - Gemini: Chuyển catalog, detail page, publish wizard steps UI.<br>- Codex: Quản lý pricing, payment redirection, preview contract. |
| **`mcp`** | - `widgets/mcp-token-manager/`<br>- `features/mcp-access/`<br>- `entities/mcp-token/` | `McpTokensManager`, `useMcpTokens`, `ALL_MCP_SCOPES`, `McpPolicy` | - Gemini: Chuyển widget manager và modal UI.<br>- Codex: Thống nhất scopes/policy entity, xóa bỏ circular dependency với settings. |
| **`note-types`** | - `pages/note-types/` (4 pages)<br>- `features/note-type-editor/`<br>- `entities/flashcard/` | `NoteTypeLivePreview`, `NoteTypeEditor`, `NoteTypeAiGuideModal` | - Gemini: Chuyển editor UI và template cards.<br>- Codex: Quản lý template patch adapter và sandbox renderer contract. |
| **`oauth`** | - `pages/oauth/`<br>- `features/oauth-consent/` | `OAuthConsentPage`, `useOAuthConsent` | - Gemini: Chuyển trang và UI consent card.<br>- Codex: Quản lý security redirect, code challenge và authorization code. |
| **`onboarding`** | - `features/onboarding/`<br>- `entities/user/` | `OnboardingModal`, `DashboardSpotlightTour`, `useOnboarding` | - Gemini: Chuyển modal và spotlight tour, giữ nguyên localStorage keys.<br>- Codex: Xác nhận schema mục tiêu học tập. |
| **`orders`** | - `pages/orders/`<br>- `entities/order/` | `OrdersPage`, `OrderReceiptCard` | - Gemini: Chuyển UI bảng đơn hàng.<br>- Codex: Quản lý PayOS webhook verification status. |
| **`profile`** | - `pages/profile/`<br>- `features/account/`<br>- `entities/user/` | `ProfileHeroCard`, `ProfileEditDialog`, `AvatarUploadModal` | - Gemini: Chuyển các modal chỉnh sửa thông tin và avatar.<br>- Codex: Quản lý xác thực sinh viên, avatar upload và session update. |
| **`settings`** | - `pages/settings/` (3 pages)<br>- `features/account/`<br>- `features/yomitan-connect/`<br>- `widgets/mcp-token-manager/` | `StudyGoalsForm`, `YomitanTokensTab` | - Gemini: Chuyển settings views, nhúng `<McpTokensManager mode="user" />`.<br>- Codex: Quản lý OAuth client CRUD và session invalidation. |
| **`statistics`** | - `pages/statistics/`<br>- `widgets/statistics-overview/`<br>- `entities/deck/api/` | `StatisticsOverviewWidget`, `UserStudyTimeChart`, `FutureDueChart` | - Gemini: Chuyển charts và trang thống kê.<br>- Codex: Quản lý timezone offset và query filter contract. |
| **`study`** | - `pages/study/`<br>- `widgets/study-workspace/`<br>- `features/study/`<br>- `entities/flashcard/` | `StudyWorkspace`, `patchStudyCardContent`, `CardDisplay` | - Gemini: Chuyển header toolbar, bottom bar, completion card UI.<br>- Codex: Giữ độc quyền 1.463 LOC `useStudySession`, SM-2 engine, IndexedDB durability. |
| **`support`** | - `pages/support/` (5 pages)<br>- `features/support/`<br>- `entities/support-ticket/` | `SupportFeedbackDialog`, `TicketStatusBadge`, `TicketItem` | - Gemini: Chuyển form gửi phản hồi và các trang guide.<br>- Codex: Quản lý support donation PayOS bridge và ticket status schema. |
| **`wallet`** | - `pages/wallet/`<br>- `features/wallet/`<br>- `entities/wallet/` | `WalletSummaryCard`, `WalletTransactionsTable` | - Gemini: Chuyển trang và bảng giao dịch.<br>- Codex: Quản lý payout request validation và ledger balance. |
| **`worksheets`** | - `pages/worksheets/`<br>- `widgets/worksheet-studio/`<br>- `features/worksheets/`<br>- `shared/lib/print/` | `DeckWorksheetModal`, `WorksheetPageRenderer`, `printEngine` | - Gemini: Phân rã 4.387 LOC modal theo từng wizard step.<br>- Codex: Giữ layout math geometry, SVG stroke parser, print stylesheet. |

### 3.4 Chiến lược Tháo gỡ 5 Điểm nghẽn Kiến trúc và Vòng lặp Trọng yếu

#### 1. Tháo gỡ Vòng lặp `mcp` $\longleftrightarrow$ `settings`:
- **Thực trạng**: `features/mcp/types.ts` import scope từ `features/settings/hooks/useMcpTokenCRUD.ts`; ngược lại `settings` import hook và manager từ `mcp`.
- **Giải pháp dứt điểm**:
  1. Trích xuất toàn bộ kiểu dữ liệu, `ALL_MCP_SCOPES`, `SCOPE_CATEGORIES`, `SCOPE_PRESETS` và `McpPolicy` xuống `src/entities/mcp-token/model/scopes.ts` và `types.ts`.
  2. Gom cụm `<McpTokensManager />` vào `src/widgets/mcp-token-manager/`.
  3. Cả `features/admin/pages/AdminMcpTokensPage.tsx` và `features/settings/components/McpTokensTab.tsx` đều chỉ import `<McpTokensManager />` từ `@/widgets/mcp-token-manager`. Triệt tiêu 100% vòng lặp.

#### 2. Tháo gỡ Phụ thuộc Ngược `shared/api/bootstrap.ts` $\longrightarrow$ `app/api.ts`:
- **Thực trạng**: `shared/api/bootstrap.ts` gọi `appApi` từ `app/api.ts`; trong khi `app/api.ts` lại import DTO từ `features/auth`, `features/dashboard`, `features/statistics`.
- **Giải pháp dứt điểm**:
  1. Chuyển hàm fetch session bootstrap sang `src/entities/session/api/bootstrap.ts`.
  2. `entities/session/api/bootstrap.ts` gọi trực tiếp HTTP client trung lập `shared/api/client.ts` (`apiJson('/api/bootstrap')`).
  3. Chuyển các endpoint domain khác về đúng `entities/deck/api`, `features/auth/api`. Giữ `app/api.ts` như một facade re-export tạm thời trong quá trình chuyển đổi.

#### 3. Tháo gỡ Mutation Xuyên Thấu vào Study Persistence (`audio`, `browse`, `note-types`):
- **Thực trạng**: 
  Các tính năng chỉnh sửa dữ liệu (`browse` khi sửa trường thẻ inline, `audio` khi sinh giọng đọc gắn URL media, `note-types` khi sửa CSS/HTML template) đang gọi trực tiếp hàm nội bộ `updateCardFieldValuesInSessions` và `updateTemplateInSessions` sâu bên trong `@/features/study/session/sessionStore.ts`.
  Điều này vi phạm nghiêm trọng nguyên tắc đóng gói module FSD (Feature-to-Feature deep import) và tạo ra phụ thuộc xoắn ốc giữa các feature.
- **Ràng buộc Kỹ thuật Cốt lõi (Tránh Lỗ hổng React Lifecycle)**:
  Adapter đồng bộ thẻ **TUYỆT ĐỐI KHÔNG** được thiết kế dưới dạng React listener hay callback đăng ký khi component mount (như `StudyPage` mount). Khi người dùng đang ở `/browse` hoặc `/audio/generate`, `StudyPage` hoàn toàn không mount; mọi cơ chế dựa trên React listener sẽ dẫn đến no-op âm thầm (silent failure) và làm phân rã dữ liệu phiên học trên IndexedDB.
- **Giải pháp dứt điểm: Headless Persistent Content Patch Adapter (`studyContentPatchAdapter`)**:
  1. `features/study` tạo adapter lưu trữ độc lập tại `src/features/study/model/studyContentPatchAdapter.ts` và export công khai tại `src/features/study/index.ts`.
  2. Adapter là **hàm headless thuần túy**, chạy bất đồng bộ trực tiếp xuống IndexedDB `flama-study` (object store `sessions`) mà không đòi hỏi bất kỳ React component nào phải hiển thị.
  3. Cung cấp chữ ký hàm chuẩn hóa:
     ```typescript
     // src/features/study/model/studyContentPatchAdapter.ts
     import {
       openStudyDatabase,
       loadStudySession,
       saveStudySession,
       memoryFallback,
       STORE_SESSIONS,
     } from '../session/sessionStore'
     import { patchRenderContext } from '../renderer/renderContext'
     import { canonicalDigest } from '../renderer/canonicalDigest'
     import type { StudyMediaArtifact, StudyFieldDef } from '../types'

     export interface PatchCardOptions {
       noteId?: string | null
       media?: StudyMediaArtifact[]
     }

     export interface PatchTemplateOptions {
       fieldDefs?: StudyFieldDef[]
       css?: string
       templates?: Record<string, { qfmt: string; afmt: string }>
     }

     /**
      * Cập nhật giá trị trường và media vào tất cả các phiên học dở dang.
      * Hoạt động HEADLESS trực tiếp trên IndexedDB, không phụ thuộc vào React lifecycle.
      */
     export async function patchStudyCardContent(
       cardId: string,
       newFieldValues: Record<string, string>,
       options?: PatchCardOptions
     ): Promise<void> {
       try {
         const keys = await getActiveSessionScopeKeys()
         for (const key of keys) {
           const session = await loadStudySession(key)
           if (!session) continue

           let isDirty = false
           const snapshot = session.snapshot

           for (const card of snapshot.cards) {
             if (card.card_id === cardId || (options?.noteId && card.note_id === options.noteId)) {
               const contentKey = card.content_key
               const existingContent = snapshot.contents[contentKey]
               if (!existingContent) continue

               const combinedMedia = options?.media && options.media.length > 0
                 ? [...options.media]
                 : [...(existingContent.media || [])]

               // Tự động phân tích các URL media proxy mới trong giá trị trường
               extractAndMergeProxyMedia(newFieldValues, combinedMedia)

               const mergedFieldValues = { ...existingContent.field_values, ...newFieldValues }
               const nextRenderContext = patchRenderContext(
                 existingContent.render_context || {},
                 newFieldValues,
                 snapshot.templates[card.template_key]?.field_defs,
                 combinedMedia
               )
               const nextVersion = canonicalDigest({
                 schema_version: 'study-content.v1',
                 renderer_abi: existingContent.renderer_abi,
                 note_id: existingContent.note_id,
                 field_values: mergedFieldValues,
                 media: combinedMedia,
               })
               const newContentKey = `${existingContent.id}:${nextVersion}`

               snapshot.contents[newContentKey] = {
                 ...existingContent,
                 version: nextVersion,
                 field_values: mergedFieldValues,
                 render_context: nextRenderContext,
                 media: combinedMedia,
               }
               card.content_key = newContentKey
               isDirty = true
             }
           }

           if (isDirty) {
             await saveStudySession(session)
           }
         }

         // Phát thông báo đồng bộ realtime (nếu có StudyPage đang mở ở tab khác hoặc background)
         broadcastStudySyncEvent('CARD_UPDATED', { cardId, noteId: options?.noteId || null, fieldValues: newFieldValues })
       } catch (error) {
         console.warn('[studyContentPatchAdapter] Failed to patch active sessions in IndexedDB:', error)
       }
     }

     /**
      * Cập nhật template cấu trúc thẻ vào các phiên học dở dang.
      */
     export async function patchStudyTemplateContent(
       templateKey: string,
       patch: PatchTemplateOptions
     ): Promise<void> {
       // Quét IndexedDB và cập nhật snapshot.templates[templateKey], sau đó broadcast TEMPLATE_UPDATED
     }
     ```
  4. **Cơ chế hoạt động kép (Dual Persistence & Live Broadcast)**:
     - **Trường hợp `StudyPage` KHÔNG mở**: Dữ liệu phiên học được ghi ngay lập tức vào IndexedDB. Khi người dùng mở trang học, hook `useStudySession` đọc snapshot mới nhất từ IndexedDB, đảm bảo 100% tính nhất quán.
     - **Trường hợp `StudyPage` ĐANG mở** (chạy nền hoặc tab khác): Kênh `BroadcastChannel('flama_study_sync_channel')` và `CustomEvent('flama_study_card_updated')` kích hoạt callback trong `useStudySession`, cập nhật in-memory state ngay tại chỗ mà không cần reload trang.
  5. **Caller Integration**: Các module `browse`, `audio`, `note-types` chỉ cần gọi:
     ```typescript
     import { patchStudyCardContent } from '@/features/study'
     // Hoặc import { patchStudySessionCards } from '@/entities/session' (theo lộ trình bóc tách Tier 5)
     ```
     Ranh giới nội bộ của `sessionStore` được bảo vệ an toàn tuyệt đối, triệt tiêu vi phạm FSD.

#### 4. Bóc tách Iframe Sandbox Flashcard Renderer (`CardDisplay`):
- **Thực trạng**: `marketplace` và `note-types` import `CardDisplay` từ `features/study/components/CardDisplay`.
- **Giải pháp dứt điểm**:
  1. Di chuyển `CardDisplay.tsx`, `CardRendererFrame.tsx` và `clientRenderer.ts` sang `src/entities/flashcard/ui/` và `src/entities/flashcard/lib/`.
  2. Bảo toàn nguyên vẹn cơ chế iframe sandbox, CSP headers, postMessage channel và invariant luôn render cả 2 mặt thẻ đồng thời (`question` và `answer`).
  3. Cả `study`, `marketplace`, `note-types` đều import `<CardDisplay />` từ `@/entities/flashcard`.

#### 5. Bóc tách Cây Chọn Bộ Thẻ Dùng Chung (`DeckSelectionTreeView`):
- **Thực trạng**: `audio` và `worksheets` import `DeckSelectionTreeView` từ `features/import/components/DeckSelectionTreeView`.
- **Giải pháp dứt điểm**:
  1. Di chuyển `DeckSelectionTreeView.tsx` và test suite đi kèm sang `src/entities/deck/ui/DeckSelectionTreeView.tsx`.
  2. Di chuyển kiểu dữ liệu `DeckOption` sang `src/entities/deck/model/types.ts`.
  3. Các caller (`import`, `audio`, `worksheets`) import từ `@/entities/deck`.

### 3.5 Đặc tả Mã nguồn Public API Export (`index.ts`)

#### A. `src/entities/flashcard/index.ts`
```typescript
// Public API for Flashcard Entity (Tier 5)
export { CardDisplay } from './ui/CardDisplay'
export type { CardDisplayProps } from './ui/CardDisplay'
export { MediaFieldPreview } from './ui/MediaFieldPreview'
export type { MediaFieldPreviewProps } from './ui/MediaFieldPreview'
export type {
  Note,
  Card,
  NoteType,
  NoteField,
  CardTemplate,
  RenderedCardSide,
} from './model/types'
export { renderCardHtml } from './lib/clientRenderer'
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
> **Ghi chú phân loại**: Slice `entities/support-ticket` là một **Planned Extraction** thuộc gói triển khai tiếp theo (Codex C05 / Gemini G05). Kiểu `TicketItem` sẽ được di dời từ `features/admin/pages/AdminTicketsPage.tsx` sang đây, và `TicketStatusBadge` sẽ được tạo mới như một component hiển thị trạng thái chuẩn hóa thay thế cho các badge rời rạc hiện nay.

```typescript
// Public API for Support Ticket Entity (Tier 5)
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
Định tuyến của Flama được khai báo tập trung tại `frontend/src/App.tsx` (dòng 328–632). Toàn bộ kiến trúc gồm 95 khai báo route, được phân định nghiêm ngặt thành hai nhóm:
1. **Các tuyến đường hiển thị component trực tiếp (Canonical & Direct Component Routes)**: Gồm 52 tuyến đường chuẩn và alias hiển thị trang.
2. **Các tuyến đường chuyển hướng phía client (`<Navigate replace />` Redirect Routes)**: Gồm đúng 18 tuyến đường bảo tồn tương thích ngược các URL lịch sử, bookmark cũ của người dùng và các shortcut URL ngắn.

Mọi hoạt động tái cấu trúc thư mục (FSD Migration) bắt buộc phải bảo toàn 100% các route paths, parameters và dynamic query strings dưới đây.

#### 4.1.A Bảng Tuyến đường Trực tiếp & Chuẩn (Canonical & Direct Component Routes)

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
| `/admin/analytics` | `AdminAnalyticsPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Dashboard phân tích KPI tài chính, tăng trưởng và gắn kết |
| `/admin/users` | `AdminUsersPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý người dùng, trạng thái kích hoạt và phân quyền |
| `/admin/payments` | `AdminPaymentsPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Bảng kiểm soát giao dịch, đơn hàng PayOS và xử lý hoàn tiền |
| `/admin/fees` | `AdminFeesPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý biểu phí hoa hồng sàn và chính sách chiết khấu |
| `/admin/tts` | `AdminTtsPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý và cấu hình VoiceVox / TTS providers hệ thống |
| `/admin/image-library` | `AdminImageLibraryPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý kho hình ảnh hệ thống dùng chung |
| `/admin/permissions` | `AdminPermissionsPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý phân quyền đặc biệt. Query: `selected_ids` |
| `/admin/mcp-tokens` | `AdminMcpTokensPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Giám sát toàn bộ API token MCP cấp cho AI trên hệ thống |
| `/admin/support` | `AdminSupportConfigPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Cấu hình tài khoản ngân hàng, mã QR và thông tin ủng hộ |
| `/admin/tickets` | `AdminTicketsPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Hộp thư quản trị tiếp nhận và giải quyết vé hỗ trợ người dùng |
| `/admin/tickets/:id` | `AdminTicketDetailPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Param: `:id` (Xử lý chi tiết vé hỗ trợ cụ thể) |
| `/admin/taxonomy` | `AdminTaxonomyPage` | Lazy | `<RequireAuth />` + Admin | Canonical | Quản lý cây danh mục, cấp độ JLPT, môn học, mappings |
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
3. **Phân quyền Quản trị Admin (`/admin/*`)**:
   - Giao diện client: Menu Admin chỉ render khi `user?.is_admin === true`.
   - Tầng API: Mọi endpoint dưới `/api/admin/` kiểm tra role tại backend Flask; nếu vi phạm trả về HTTP 403 Forbidden.
4. **Backend Availability Guard (`shared/api/backendAvailability.ts`)**:
   - Tự động bắt các mã lỗi HTTP Gateway: 502, 503, 504, 521, 522, 523, 524.
   - Lưu URL vào `sessionStorage` (`flama:maintenance:return-path`) và chuyển hướng sang `/maintenance`. Khi backend hoạt động trở lại, tự động phục hồi người dùng về đúng trang đang thao tác dở.

### 4.3 Ma trận TanStack Query Keys, Cache Identity và Phân tích Dual Bootstrap

#### A. Trọng điểm Phân kỳ Cache Bootstrap Cần Thống nhất:
- Trong `shared/api/bootstrap.ts`, hằng số query key chuẩn được định nghĩa là:
  ```typescript
  export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const
  ```
- Tuy nhiên, khảo sát mã nguồn thực tế phát hiện có đúng 7 tệp đang tự tay gọi chuỗi hardcoded `['bootstrap']`:
  1. `features/browse/hooks/useBrowseState.ts` (dòng 108, 622, 706)
  2. `features/import/hooks/useAnkiSyncPage.ts`
  3. `features/import/components/AnkiSyncTab.tsx`
  4. `features/profile/components/AvatarUploadModal.tsx` (dòng 54, 70)
  5. `features/profile/components/EmailVerificationDialog.tsx` (dòng 73, 99)
  6. `features/profile/components/ProfileEditDialog.tsx` (dòng 127)
  7. `features/auth/pages/VerifyEmailPage.tsx`
- **Hành động bảo vệ ranh giới**: Hai query keys này đang tồn tại song song như hai entry cache độc lập trong runtime. Codex sẽ thống nhất hằng số này trong gói C01/C02. Trong gói G01, Gemini tuyệt đối không tự ý đổi chuỗi query key để tránh làm hỏng các test cases hiện có.

#### B. Ma trận Toàn bộ TanStack Query Keys Theo 16 Miền Chức năng (Đầy đủ 100%):

Toàn bộ 413 tệp mã nguồn frontend tiêu thụ hơn 75 biểu thức `queryKey`. Bảng dưới đây phân loại chính xác theo 16 miền nghiệp vụ:

| Miền Nghiệp vụ (Domain) | Cấu trúc Query Key | Tệp / Hook Tiêu thụ | Mục đích Dữ liệu & Cache Policy |
|---|---|---|---|
| **1. Bootstrap** | `['frontend', 'bootstrap']` | `useBootstrap()`, `MaintenancePage` | Thông tin phiên người dùng, feature flags, system config (Canonical) |
| | `['bootstrap']` | `useBrowseState`, `ProfileEditDialog`... (7 files) | Phiên bản hardcoded legacy (cần thống nhất ở C01/C02) |
| **2. Dashboard** | `['frontend', 'dashboard']` / `['dashboard']` | `DashboardPage`, `useDashboardPage` | Tổng quan số thẻ cần ôn, due cards, cây bộ thẻ học tập |
| | `['frontend', 'dashboard', 'overview', year]` | `DashboardPage` | Bản đồ nhiệt (Activity Heatmap) học tập theo năm |
| **3. Statistics** | `['frontend', 'statistics', 'config']` | `StatisticsPage` | Cấu hình hiển thị thống kê và deck selector |
| | `['frontend', 'statistics', 'overview', year]` | `StatisticsPage` | Báo cáo tổng quan số lượng thẻ học trong năm |
| | `['stats', 'today-future', filters]` | `useStatistics` | Dự báo khối lượng ôn tập SRS theo ngày (Forecast chart) |
| | `['stats', 'study-time', filters]` | `useStatistics` | Biểu đồ phân bổ thời gian học tập và tốc độ phản xạ |
| **4. Browse & Vocab** | `['browse', 'decks']` | `useBrowseState` | Danh sách cây bộ thẻ phục vụ bộ lọc tìm kiếm |
| | `['browse', 'cards', query, deckId, status, sort, page, perPage]` | `useBrowseState` | Danh sách thẻ tìm kiếm với đầy đủ tham số phân trang và bộ lọc |
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
| **7. Marketplace** | `['marketplace', mode, query, category, domain, subject, level, diff, pricing, sort]` | `SharedDecksPage` | Danh mục học liệu chia sẻ với 10 tham số lọc nâng cao |
| | `['shared-deck-detail', id]` | `SharedDeckDetailPage` | Chi tiết bộ thẻ marketplace, thông tin tác giả, giá bán |
| | `['shared-deck-preview', id, templateId, sampleNoteId]` | `SharedDeckDetailPage` | Thẻ mẫu xem trước trong bộ thẻ đang xem |
| | `['shared-note-types', query, sort, page]` | `SharedNoteTypesPage` | Danh mục mẫu thẻ được chia sẻ công khai |
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

#### B. SessionStorage Keys:
- **`flama:maintenance:return-path`**:
  - File quản lý: `frontend/src/pages/MaintenancePage.tsx`.
  - Mục đích: Lưu URL người dùng đang truy cập trước khi server gặp sự cố kết nối hoặc bảo trì (502/503) để tự động phục hồi điều hướng khi hệ thống hoạt động trở lại.

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
   - File gửi (Senders): `frontend/src/features/study/session/sessionStore.ts` (khi sửa trường thẻ hoặc cập nhật giao diện mẫu thẻ).
   - File nhận (Receivers): `frontend/src/features/study/hooks/useStudySession.ts` (lắng nghe để cập nhật session state trong RAM).
   - Hợp đồng Payload:
     ```typescript
     // Sự kiện cập nhật trường thẻ:
     {
       type: 'CARD_UPDATED',
       cardId: number,
       noteId: number | null,
       fieldValues: Record<string, string>,
       media?: Record<string, string>
     }

     // Sự kiện cập nhật mẫu template thẻ:
     {
       type: 'TEMPLATE_UPDATED',
       templateId: number,
       updated: UpdatedTemplatePayload
     }
     ```
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

### 5.4 Yêu cầu Bộ Kiểm thử Đặc tả Hành vi (Characterization Suites)
Trước khi bất kỳ agent nào bắt tay vào chỉnh sửa mã nguồn của 9 feature trên trong các gói tương ứng (từ G03 trở đi):
1. Bắt buộc phải viết **Characterization Tests** để khóa chặt hành vi hiện tại trước khi chạm vào mã nguồn sản xuất (tương tự quy chuẩn đã thực hiện mẫu mực tại `AdminMcpTokensBaseline.characterization.test.tsx` và `McpTokensBaseline.characterization.test.tsx`).
2. Kiểm thử chụp ảnh DOM (DOM Snapshot) hoặc bounding box đối với các màn hình trực quan phức tạp để đảm bảo Zero Visual Regression.

---

## PHẦN 6: ĐỀ XUẤT PHẠM VI CHI TIẾT CHO GÓI G01 (SHARED PRIMITIVES & UTILITIES)

### 6.1 Mục tiêu và Ranh giới Kỹ thuật Gói G01
- **Tên gói**: Gói G01 — Shared Primitives & Utilities Consolidation.
- **Agent chịu trách nhiệm thực thi**: Gemini (`agy` worker).
- **Mục tiêu**: Chuẩn hóa toàn bộ 8 Flama UI Primitives, 30 Shadcn Radix UI components và các tiện ích trung lập không mang nghiệp vụ vào tầng `src/shared/`.
- **Ràng buộc an toàn số 1**: Tạo lớp **Re-export Shim** tương thích ngược tại các vị trí cũ để 331 file mã nguồn hiện có tiếp tục compile bình thường, không gây ra diff hàng loạt làm đứt gãy working tree.

### 6.2 Danh sách Tệp Được phép Chỉnh sửa / Tạo mới (Whitelist)
Gemini chỉ được phép tạo mới, di chuyển và hiệu chỉnh các tệp nằm trong Whitelist sau:

#### A. 8 Flama UI Primitives (`frontend/src/shared/ui/`):
1. `SearchInput.tsx` & `SearchInput.test.tsx` (Bảo toàn cờ `isComposing` chống giật IME tiếng Nhật, badge phím tắt, loading spinner).
2. `ConfirmDialog.tsx` & `ConfirmDialog.test.tsx` (Bảo toàn Radix dialog accessibility, async loading spinner).
3. `StatusPill.tsx` & `StatusPill.test.tsx` (Bảo toàn 8 trạng thái CVA và token màu OKLCH).
4. `CodeSnippetBox.tsx` & `CodeSnippetBox.test.tsx` (Bảo toàn copy clipboard animation tích xanh, dark mode).
5. `FilterPillGroup.tsx` & `FilterPillGroup.test.tsx` (Bảo toàn horizontal scroll và keyboard navigation).
6. `ImageUploadDropzone.tsx` & `ImageUploadDropzone.test.tsx` (Bảo toàn dán ảnh clipboard `Ctrl+V` và nén ảnh).
7. `SplitPane.tsx` & `SplitPane.test.tsx` (Bảo toàn draggable handle và lưu vị trí vào LocalStorage).
8. `CardFieldsForm.tsx` & `CardFieldsForm.test.tsx` (Giữ nguyên tại đây như một shim cho đến khi Codex C02 tách Flashcard Entity).
9. `index.ts` & `index.test.ts` (Public API exports của `shared/ui`).

#### B. 30 Shadcn UI Primitives (`frontend/src/shared/ui/shadcn/` hoặc `components/ui/`):
- `alert.tsx`, `avatar.tsx`, `badge.tsx`, `breadcrumb.tsx`, `button.tsx`, `card.tsx`, `chart.tsx`, `checkbox.tsx`, `collapsible.tsx`, `dialog.tsx`, `drawer.tsx`, `dropdown-menu.tsx`, `field.tsx`, `input.tsx`, `label.tsx`, `native-select.tsx`, `pagination.tsx`, `progress.tsx`, `scroll-area.tsx`, `select.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `skeleton.tsx`, `sonner.tsx`, `switch.tsx`, `table.tsx`, `tabs.tsx`, `textarea.tsx`, `tooltip.tsx`.

#### C. Tiện ích Trung lập Dùng chung (`frontend/src/shared/lib/`):
1. `frontend/src/shared/lib/utils.ts`: Tiện ích gộp class `cn` (kế thừa từ `lib/utils.ts`).
2. `frontend/src/shared/lib/imageCompression.ts` & `imageCompression.test.ts`: Nén ảnh client-side qua Canvas.
3. `frontend/src/shared/lib/ankiHtmlSanitizer.ts` & `ankiHtmlSanitizer.test.ts`: Làm sạch HTML thẻ từ vựng trung lập.
4. `frontend/src/shared/lib/hooks/useMobile.ts`: Hook phát hiện màn hình di động (kế thừa từ `hooks/use-mobile.ts`).

#### D. Thành phần Giao diện Chung Hiện có (`frontend/src/shared/components/` & `shared/types/`):
1. `frontend/src/shared/components/Brand.tsx`
2. `frontend/src/shared/components/Icons.tsx`
3. `frontend/src/shared/components/Page.tsx`
4. `frontend/src/shared/components/PageState.tsx`
5. `frontend/src/shared/components/SpotlightTour.tsx`
6. `frontend/src/shared/types/api.ts` & `heatmap.ts`

### 6.3 Danh sách Tệp và Thư mục Nghiêm cấm Chạm vào (Gate G01 Blacklist)

Mục tiêu duy nhất của Gói G01 là **chuẩn hóa và cô lập Shared Primitives / Utilities vào `src/shared/` và thiết lập các Re-export Shims tại vị trí cũ**. Gói G01 **TUYỆT ĐỐI KHÔNG REFACTOR CALLERS**. Bất kỳ hành vi chỉnh sửa nào nằm ngoài Whitelist (Mục 6.2) sẽ ngay lập tức bị từ chối nghiệm thu:

1. **Toàn bộ 22 Thư mục Feature Nghiệp vụ (`frontend/src/features/**`)**:
   - Cấm tuyệt đối chỉnh sửa bất kỳ tệp nào trong `frontend/src/features/**` (bao gồm `admin`, `analytics`, `audio`, `auth`, `browse`, `dashboard`, `deck-collaboration`, `guide`, `import`, `landing`, `library`, `marketplace`, `mcp`, `note-types`, `notifications`, `oauth`, `onboarding`, `settings`, `statistics`, `study`, `support`, `worksheets`).
   - Tất cả các feature components và hooks tiếp tục import từ đường dẫn cũ (`@/components/ui/...`, `@/lib/utils`, `@/lib/imageCompression`...). Các import này sẽ được giải quyết trơn tru thông qua lớp Re-export Shim tại Mục 6.4 mà không làm thay đổi dù chỉ một ký tự trong `features/**`.
2. **Toàn bộ Tầng Pages & Views (`frontend/src/pages/**`)**:
   - Cấm sửa đổi các tệp `frontend/src/pages/**` (`StaticPages.tsx`, `MaintenancePage.tsx`...).
3. **Tầng App Root, Router & Entry Points (Thẩm quyền Codex C01, C03)**:
   - Cấm sửa đổi `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/app/**`, `frontend/index.html`.
4. **Tầng Network Transport & Session (Thẩm quyền Codex C01)**:
   - Cấm sửa đổi `frontend/src/shared/api/client.ts`, `bootstrap.ts`, `backendAvailability.ts`, `config/env.ts`.
5. **Toàn bộ Core Runtime, Storage, Anki Worker & Audio Client (Thẩm quyền Codex C02, C06, C08)**:
   - Cấm sửa đổi `frontend/src/lib/anki*`, `frontend/src/lib/sync.worker.ts`, `frontend/src/lib/flamaAudioClient.ts`.
6. **Tầng App Shell Layouts & Navigation (Thẩm quyền Gói G02 / C03)**:
   - Cấm sửa đổi `frontend/src/layouts/**` (`AppLayout.tsx`).
   - Cấm sửa đổi các layout components: `frontend/src/components/app-sidebar.tsx`, `site-footer.tsx`, `nav-main.tsx`, `nav-user.tsx`, `site-mascot.tsx`, `feedback-dialog.tsx`.
7. **Tệp Cấu hình Xây dựng Frontend (Build & Tooling Configuration)**:
   - Cấm tuyệt đối can thiệp hoặc sửa đổi:
     - `frontend/package.json`, `frontend/package-lock.json` (Không cài thêm hoặc gỡ bỏ dependencies).
     - `frontend/vite.config.ts` (Không sửa cấu hình bundler).
     - `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json` (Không sửa path alias hay compiler options).
     - `frontend/tailwind.config.js`, `frontend/postcss.config.js` (Không sửa cấu hình CSS pipeline).
8. **Dịch vụ Đồng hành Ngoại vi (Companion Services) & Scripts / Tests Backend**:
   - Cấm chạm vào `connect_wsgi.py` (Flama Connect bridge Yomitan cổng 4790).
   - Cấm chạm vào `flama-audio/**` (Bộ desktop audio engine .NET 8 WPF cổng 4791).
   - Cấm chạm vào `scripts/**` (Toàn bộ các test runner và migration scripts).
   - Cấm chạm vào `tests/**` (Toàn bộ test suites của backend Python).
9. **Mã nguồn Backend Flask & Database Persistence**:
   - Cấm chạm vào `app/**`, `models/**`, `migrations/**`, `wsgi.py`.
10. **Kỷ luật Git Trạng thái & Working Tree**:
    - TUYỆT ĐỐI KHÔNG tự ý `git checkout` chuyển nhánh.
    - TUYỆT ĐỐI KHÔNG chạy `git commit`, `git add`, `git reset`, `git restore`, `git stash`, hay `git push`.
    - Bảo toàn 100% commit SHA `5b21b1b` của Agent P10 và trạng thái sạch sẽ của working tree.

---

### 6.4 Ranh giới Caller Scope và Cơ chế Re-export Shim Bắt buộc (Zero Caller Regression)

Để đảm bảo **không một file nào trong số 331 file source và test callers bị lỗi import hay đứt gãy kiểm thử** khi di chuyển primitives sang `src/shared/`, Gate G01 **bắt buộc phải thiết lập 5 nhóm Re-export Shim tương thích ngược hoàn toàn tại các vị trí cũ**:

#### 1. Re-export Shims cho 30 Shadcn UI Primitives (`components/ui/*.tsx`):
Tại vị trí cũ `frontend/src/components/ui/<component>.tsx`, giữ nguyên file và tạo shim re-export toàn bộ sang vị trí mới:
```typescript
// Ví dụ: frontend/src/components/ui/button.tsx
export * from '@/shared/ui/shadcn/button'

// Ví dụ: frontend/src/components/ui/dialog.tsx
export * from '@/shared/ui/shadcn/dialog'
```
*Áp dụng đồng bộ cho toàn bộ 30 tệp UI*: `alert.tsx`, `avatar.tsx`, `badge.tsx`, `breadcrumb.tsx`, `button.tsx`, `card.tsx`, `chart.tsx`, `checkbox.tsx`, `collapsible.tsx`, `dialog.tsx`, `drawer.tsx`, `dropdown-menu.tsx`, `field.tsx`, `input.tsx`, `label.tsx`, `native-select.tsx`, `pagination.tsx`, `progress.tsx`, `scroll-area.tsx`, `select.tsx`, `separator.tsx`, `sheet.tsx`, `sidebar.tsx`, `skeleton.tsx`, `sonner.tsx`, `switch.tsx`, `table.tsx`, `tabs.tsx`, `textarea.tsx`, `tooltip.tsx`.

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
*Bảo vệ*:
- `frontend/src/shared/ui/ImageUploadDropzone.tsx:6`: `import { compressImage } from "@/lib/imageCompression"`
- `frontend/src/features/browse/components/MediaFieldPreview.tsx:19`: `import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from '@/lib/imageCompression'`
- `frontend/src/features/support/pages/FeedbackPage.tsx:44`: `import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from '@/lib/imageCompression'`
- `frontend/src/features/browse/components/MediaFieldPreview.test.tsx:172`: Dynamic import `const imageCompression = await import('@/lib/imageCompression')`.

#### 4. Re-export Shim cho Bộ Làm sạch HTML Thẻ Từ vựng (`lib/ankiHtmlSanitizer.ts`):
Tại vị trí cũ `frontend/src/lib/ankiHtmlSanitizer.ts`, thiết lập shim trỏ sang `shared/lib/ankiHtmlSanitizer`:
```typescript
// frontend/src/lib/ankiHtmlSanitizer.ts
export * from '@/shared/lib/ankiHtmlSanitizer'
```
*Bảo vệ*:
- `frontend/src/lib/ankiSyncEngine.ts:28`: `import { ... } from '@/lib/ankiHtmlSanitizer'`
- `frontend/src/features/import/components/AnkiSyncTab.tsx:26`: `import { sanitizeAnkiHtml } from '@/lib/ankiHtmlSanitizer'`

#### 5. Re-export Shim cho Hook Nhận diện Màn hình Di động (`hooks/use-mobile.ts`):
Tại vị trí cũ `frontend/src/hooks/use-mobile.ts`, thiết lập shim trỏ sang `shared/lib/hooks/useMobile`:
```typescript
// frontend/src/hooks/use-mobile.ts
export * from '@/shared/lib/hooks/useMobile'
```
*Bảo vệ*:
- `frontend/src/components/ui/sidebar.tsx:5`: `import { useIsMobile } from "@/hooks/use-mobile"`

#### 6. Bảo vệ Tính Toàn vẹn và Vị trí Tạm thời của `CardFieldsForm.tsx`:
Tiếp tục export `CardFieldsForm` qua `frontend/src/shared/ui/index.ts`. Component này đóng vai trò là shim chuyển tiếp tạm thời tại tầng UI Primitives cho đến khi Codex thực hiện bóc tách thực thể Flashcard tại Gói C02.

### 6.5 Tiêu chí Nghiệm thu Khắt khe cho Gate G01 (Acceptance Criteria)
Gate G01 chỉ được đóng và nghiệm thu chuyển sang G02 khi vượt qua toàn bộ 7 tiêu chí:
1. **Typecheck Latch**: `npm --prefix frontend run typecheck` vượt qua với **0 lỗi (exit code 0)**.
2. **Lint Latch**: `npm --prefix frontend run lint` không phát sinh thêm bất kỳ lỗi hoặc cảnh báo mới nào.
3. **Build Latch**: `npm --prefix frontend run build` đóng gói bundle thành công với exit code 0.
4. **Test Suite Latch**:
   - `npm --prefix frontend test -- shared/ui` đạt **100% pass (43/43 tests passed)**.
   - `npm --prefix frontend test -- imageCompression ankiHtmlSanitizer` đạt **100% pass (10/10 tests passed)**.
5. **Zero Visual Regression**: Giữ nguyên 100% styling CVA, token màu OKLCH, padding, border-radius, font-size và box-shadow.
6. **Zero Runtime Regression**: Cờ `isComposing` Japanese IME của `SearchInput`, LocalStorage sync của `SplitPane` và Radix accessibility của `ConfirmDialog` hoạt động chuẩn mực.
7. **Bảo tồn Working Tree Git**: Working tree trên nhánh `phase10/contraction-drop` không có commit mới; toàn bộ thay đổi của Agent P10 được bảo toàn nguyên vẹn 100%.

---
*Tài liệu Master Specification G00 được hoàn thành và xác thực độc quyền bởi Worker 1 (`teamwork_preview_worker_g00_1`) tại mốc bàn giao Package G00.*
