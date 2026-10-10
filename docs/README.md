# Flama Documentation Index

Bản đồ tra cứu toàn bộ tài liệu kỹ thuật, kiến trúc, kế hoạch và hướng dẫn vận hành của dự án Flama.

---

## 🏛️ 1. Kiến Trúc Hệ Thống (`docs/architecture/`)

Tài liệu mô tả kiến trúc hiện hành và các tiêu chuẩn kỹ thuật đang áp dụng trong hệ thống:

| Tài liệu | Mô tả |
|---|---|
| [`SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md) | **Tổng quan kiến trúc toàn hệ thống** (React SPA, Flask REST API, Flama Connect, Flama Audio). |
| [`FLAMA_PAYMENT_ARCHITECTURE.md`](architecture/FLAMA_PAYMENT_ARCHITECTURE.md) | **Kiến trúc thanh toán payOS** (Orders, PaymentAttempts, Webhook, Entitlements). |
| [`CARD_TEMPLATE_SANDBOX_RENDERER.md`](architecture/CARD_TEMPLATE_SANDBOX_RENDERER.md) | **Cơ chế render iframe sandbox an toàn** cho custom card templates. |
| [`study-interaction-trigger-algorithm-plan.md`](architecture/study-interaction-trigger-algorithm-plan.md) | **Tracker canonical cho refactor Study/Interaction/Trigger/Algorithm/Progress**; Phase 0–4 và INT-01/INT-02 hoàn tất cho pre-release development; production enablement còn gate riêng. |
| [`phase-4-current-state-preflight-2026-09-10.md`](architecture/phase-4-current-state-preflight-2026-09-10.md) | P4-01 accepted audit/preflight; production head `20260913_000038`, zero drift và complete accounting. |
| [`phase-4-reconciliation-rollout-rehearsal-2026-09-20.md`](architecture/phase-4-reconciliation-rollout-rehearsal-2026-09-20.md) | P4-10 reconciliation, local large-cohort và VPS small-cohort rehearsal; representative rollout gate vẫn mở. |
| [`phase-4-p4-11-pre-release-closeout-2026-09-20.md`](architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) | P4-11 đóng có giới hạn để không chặn phát triển pre-release; production load/fault/limits được defer rõ tới P5-09, không coi là pass. |
| [`phase-4-int02-closeout-2026-09-20.md`](architecture/phase-4-int02-closeout-2026-09-20.md) | Biên bản đóng Phase 4/INT-02: full backend/frontend test, MySQL local re-probe, authority boundary và P5 handoff. |
| [`phase-5-authority-cutover-design-2026-09-20.md`](architecture/phase-5-authority-cutover-design-2026-09-20.md) | **Draft** cutover Phase 5: physical-schema slice đã chốt riêng; NOTE routing, wire và rollback còn gate. |
| [`phase-5-p5-05-session-v4-contract-2026-09-22.md`](architecture/phase-5-p5-05-session-v4-contract-2026-09-22.md) | Study Session v4, migration 43, direct REST/MCP NOTE writer và enrollment/rollback dry-run contract; async/lifecycle/read gates còn mở. |
| [`phase-5-p5-00-inventory-2026-09-21.md`](architecture/phase-5-p5-00-inventory-2026-09-21.md) | P5-00 snapshot và two-run production SELECT-only audit; Phase 4 preflight PASS, full audit WARN, NOTE authority chưa bật. |
| [`phase-5-p5-03-legacy-projection-contract-2026-09-21.md`](architecture/phase-5-p5-03-legacy-projection-contract-2026-09-21.md) | P5-03 inert lossless encoder/comparator, field inventory và MySQL 1:N/fault/lifecycle round-trip proof. |
| [`phase-5-p5-04-canonical-command-2026-09-21.md`](architecture/phase-5-p5-04-canonical-command-2026-09-21.md) | P5-04 first slice: LEGACY-only learner/enrollment fence across native direct/session/worker entrypoints; NOTE remains fail-closed. |
| [`phase-4-schema-drift-remediation-2026-09-13.md`](architecture/phase-4-schema-drift-remediation-2026-09-13.md) | P4-01A design record cho independent batch-table migration, model/default parity và safe schema convergence. |
| [`phase-4-progress-identity-fanin-revision-adr-2026-09-10.md`](architecture/phase-4-progress-identity-fanin-revision-adr-2026-09-10.md) | P4-02 accepted ADR cho learner/Note identity, fan-in, generation và lock order. |
| [`phase-4-algorithm-state-availability-adr-2026-09-12.md`](architecture/phase-4-algorithm-state-availability-adr-2026-09-12.md) | P4-03 accepted ADR cho exact Algorithm State/raw codecs và context-aware availability. |
| [`phase-4-history-provenance-lifecycle-adr-2026-09-12.md`](architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) | P4-04 accepted ADR cho history completeness, provenance, retention fence và reset/delete/rekey. |
| [`phase-4-logical-contract-joint-acceptance-2026-09-13.md`](architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md) | Joint acceptance record cho production P4-01 và logical contracts P4-02/P4-03/P4-04. |
| [`phase-4-physical-shadow-schema-adr-2026-09-13.md`](architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md) | P4-05 accepted physical design cho additive subject/state/contributor/availability/history/lifecycle/backfill schema. |
| [`phase-4-native-session-worker-mirror-verification-2026-09-13.md`](architecture/phase-4-native-session-worker-mirror-verification-2026-09-13.md) | P4-07 same-transaction native/session/worker mirror verification. |
| [`phase-4-external-lifecycle-mirror-verification-2026-09-14.md`](architecture/phase-4-external-lifecycle-mirror-verification-2026-09-14.md) | P4-08 external snapshot/import/reset/delete/rekey mirror verification. |
| [`phase-4-resumable-backfill-verification-2026-09-14.md`](architecture/phase-4-resumable-backfill-verification-2026-09-14.md) | P4-09 dry-run-first keyset backfill, crash/resume, disposition accounting and MySQL CAS evidence. |
| [`STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md`](architecture/STUDY_ALGORITHM_RETIREMENT_LIFECYCLE.md) | Lifecycle `active/deprecated/lease-only/retired`, retention gate và rollback cho exact Algorithm artifacts. |
| [`builtin-trigger-runtime-contract-2026-09-07.md`](architecture/builtin-trigger-runtime-contract-2026-09-07.md) | ADR cho exact-version dispatcher của bốn built-in review Triggers. |
| [`trusted-study-keyboard-boundary-2026-09-07.md`](architecture/trusted-study-keyboard-boundary-2026-09-07.md) | ADR no-bridge bảo vệ Study shortcuts khỏi iframe Template không tin cậy. |
| [`study-wire-v3-rollout-contract-2026-09-08.md`](architecture/study-wire-v3-rollout-contract-2026-09-08.md) | Wire v2/v3 pairing, capability negotiation, rollout, telemetry và rollback. |
| [`decoupling-progress-review-2026-08-29.md`](architecture/decoupling-progress-review-2026-08-29.md) | Review tiến độ theo code/test/migration và roadmap tiếp tục có exit gate, rollback, security containment, cùng phương án Phase 4. |
| [`production-architecture-verification-2026-08-24.md`](architecture/production-architecture-verification-2026-08-24.md) | Baseline production chỉ-đọc và lần kiểm tra bổ sung ngày 2026-08-27 cho các migration gate. |
| [`template-notetype-decoupling-investigation.md`](architecture/template-notetype-decoupling-investigation.md) | Điều tra boundary Template/NoteType/Field và các lựa chọn tái sử dụng Template. |
| [`TYPOGRAPHY_SYSTEM.md`](architecture/TYPOGRAPHY_SYSTEM.md) | **Hệ thống Design Tokens & Typography** của giao diện. |
| [`MCP_LIST_MY_DECKS.md`](architecture/MCP_LIST_MY_DECKS.md) | **Đặc tả giao thức MCP (Model Context Protocol)** endpoint `POST /api/mcp`. |
| [`REPEATCALL.md`](architecture/REPEATCALL.md) | **Nghiên cứu giải thuật Spaced Repetition** (Anki SM-2 vs FSRS). |

---

## 📋 2. Kế Hoạch & Migration (`docs/plans/`)

### ✅ Đã Hoàn Thành (`docs/plans/completed/`)

Các kế hoạch và migration kỹ thuật đã hoàn thành và đưa vào vận hành:

| Tài liệu | Mô tả |
|---|---|
| [`REST_API_MIGRATION_PLAN.md`](plans/completed/REST_API_MIGRATION_PLAN.md) | Kế hoạch và nhật ký chuyển đổi toàn diện sang REST API canonical & React SPA. |
| [`LEGACY_SCHEMA_MIGRATION_PLAN.md`](plans/completed/LEGACY_SCHEMA_MIGRATION_PLAN.md) | Kế hoạch loại bỏ hoàn toàn các bảng schema `vocabulary_*` cũ. |
| [`DECK_CHANGE_REQUEST_SIMPLE_PLAN.md`](plans/completed/DECK_CHANGE_REQUEST_SIMPLE_PLAN.md) | Kế hoạch triển khai hệ thống đóng góp & giải quyết xung đột Change Request. |
| [`FLAMA_AUDIO_MVP_IMPLEMENTATION_PLAN.md`](plans/completed/FLAMA_AUDIO_MVP_IMPLEMENTATION_PLAN.md) | Kế hoạch triển khai ứng dụng Flama Audio desktop (.NET 8 WPF). |
| [`MARKDOWN_FIELD_EDITOR_PLAN.md`](plans/completed/MARKDOWN_FIELD_EDITOR_PLAN.md) | Kế hoạch hỗ trợ trường Markdown và dán ảnh inline. |
| [`CLONE_CUTOVER_REPORT.md`](plans/completed/CLONE_CUTOVER_REPORT.md) | Báo cáo hoàn tất cutover mô hình shared deck sang logical overlay. |
| [`SCHEDULER_FIX_DOCUMENTATION.md`](plans/completed/SCHEDULER_FIX_DOCUMENTATION.md) | Tài liệu sửa lỗi và chuẩn hóa bộ lập lịch Anki Scheduler. |

### 💡 Đề Xuất & Chưa Triển Khai (`docs/plans/proposals/` & Lộ Trình)

Các đề xuất kỹ thuật và lộ trình nâng cấp kiến trúc đang triển khai:

| Tài liệu | Mô tả |
|---|---|
| [`ARCHITECTURE_HARDENING_ROADMAP.md`](plans/ARCHITECTURE_HARDENING_ROADMAP.md) | **Lộ trình củng cố kiến trúc Modular Monolith**: Vá quyền OAuth/MCP, Alembic schema ownership, CI MySQL 8, REST API boundaries. |
| [`Flama Connect nhiều phiên bản và asbplayer — #217`](plans/proposals/FLAMA_CONNECT_MULTI_VERSION_ASBPLAYER_PLAN_2026-10-10.md) | Pipeline v2–v6, MVP text/media đã có code và test local; rollout, quota toàn hệ thống và client qualification còn gate riêng. |
| [`DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md`](plans/proposals/DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md) | Bản thảo đề xuất tách Template độc lập khỏi Note Type. |
| [`TEMPLATE_NOTE_TYPE_SETUP_UX_DESIGN_2026-10-09.md`](plans/proposals/TEMPLATE_NOTE_TYPE_SETUP_UX_DESIGN_2026-10-09.md) | Thiết kế và kết quả triển khai UI/UX: Template tập trung mặt trước/mặt sau/CSS, input trong modal; Note Type khai báo field và mapping từng lần gắn template. Có kiểm chứng và giới hạn triển khai. |
| [`TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md`](plans/proposals/TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md) | Kế hoạch triển khai template tách riêng, nhiều kiểu thẻ/deck, phiên bản và bản riêng cho deck đã cài; chia task Claude/Gemini, spec ở [`task/template-features/`](task/template-features/README.md). Chờ duyệt. |
| [`Study Decoupling Task Backlog`](task/decoupling/README.md) | Tracker task Phase 0–4 và entry Phase 5; P4-11/INT-02 đã đóng cho phát triển, production gate vẫn mở. |
| [`P5 execution plan — 2026-09-20`](task/decoupling/P5_EXECUTION_PLAN_2026-09-20.md) | Kế hoạch P5-00..P5-10/INT-03, gate, test, production canary và rollback; schema foundation LEGACY-only đang triển khai. |
| [`P5 executive brief — 2026-09-21`](task/decoupling/P5_EXECUTIVE_BRIEF_2026-09-21.md) | Bản trình quản lý: mục tiêu, mốc, nguồn lực sơ bộ, production canary và hard stops. |
| [`P5-00 inventory — 2026-09-21`](architecture/phase-5-p5-00-inventory-2026-09-21.md) | Kiểm kê code/schema P5, production SELECT-only preflight còn mở. |
| [`P5 authority-fence ADR — 2026-09-21`](architecture/phase-5-authority-fence-adr-2026-09-21.md) | Quyết định hai bảng additive LEGACY-only; chưa cấp NOTE authority. |
| [`P1/P2 closeout — 2026-09-08`](task/decoupling/completed/P1_P2_EXECUTION_CLOSEOUT_2026-09-08.md) | Handoff hoàn tất 8 task P1/P2, test evidence, async containment, v3 rollout và rollback. |
| [`FLASHCARD_FOR_KIDS_PLAN.md`](plans/proposals/FLASHCARD_FOR_KIDS_PLAN.md) | Ý tưởng phát triển bộ flashcard chuyên biệt cho trẻ em. |
| [`LISTENING_TYPING_PHONETIC_CONFUSION_ANALYSIS_PLAN.md`](plans/proposals/LISTENING_TYPING_PHONETIC_CONFUSION_ANALYSIS_PLAN.md) | **Đề xuất phân tích & gợi ý âm nghe nhầm đa ngôn ngữ (P3 - Low Priority)**: Dựa trên lịch sử nhập từ và từ gốc trong chế độ Dictation để tìm ra ma trận âm người dùng hay nghe nhầm (Tiếng Nhật, Tiếng Anh, Tiếng Hàn, Tiếng Trung, Tiếng Việt...). |

---

## 📖 3. Hướng Dẫn Kỹ Thuật (`docs/guides/`)

Các hướng dẫn chi tiết về cấu hình, dữ liệu và mẫu thẻ trong Flama:

| Tài liệu | Mô tả |
|---|---|
| [`SEEDING_GUIDE.md`](guides/SEEDING_GUIDE.md) | **Cẩm nang Seeding & Dữ liệu mẫu toàn diện** (Quy trình Reseed, CLI commands, cấu trúc `static/seed_data/`, Admin UI). |
| [`NOTE_TYPE_TEMPLATE_GUIDE.md`](guides/NOTE_TYPE_TEMPLATE_GUIDE.md) | Hướng dẫn định dạng & cú pháp xây dựng Note Type và Card Template. |

---

## 🚀 4. Hướng Dẫn Vận Hành & Release (`docs/runbooks/`)

Các tài liệu hướng dẫn quy trình vận hành, phát hành và công cụ:

| Tài liệu | Mô tả |
|---|---|
| [`FLASHCARD_V2_RUNBOOK.md`](runbooks/FLASHCARD_V2_RUNBOOK.md) | Runbook vận hành hệ thống Flashcard V2, template syntax và schema baseline. |
| [`FLAMA_AUDIO_WINDOWS_RELEASE.md`](runbooks/FLAMA_AUDIO_WINDOWS_RELEASE.md) | Quy trình build, ký số Authenticode và phát hành `FlamaAudio-Portable.exe`. |
| [`FLAMA_CONNECT_ASBPLAYER.md`](runbooks/FLAMA_CONNECT_ASBPLAYER.md) | Bật adapter AnkiConnect v2–v6, cấu hình token/asbplayer, media cleanup, giới hạn hỗ trợ và evidence local. |
| [`CHUNGBECH_IMPORT_GUIDE.md`](runbooks/CHUNGBECH_IMPORT_GUIDE.md) | Hướng dẫn import file TSV Anki ChungBech. |

---

## 📜 5. Tài Liệu Lịch Sử & Đã Thay Thế (`docs/historical/`)

Các tài liệu đánh giá hoặc kế hoạch giai đoạn trước, được lưu trữ để tra cứu bối cảnh:

| Tài liệu | Mô tả |
|---|---|
| [`FLAMA_ARCHITECTURE_REVIEW.md`](historical/FLAMA_ARCHITECTURE_REVIEW.md) | Đánh giá kiến trúc ban đầu (2026-03-01). |
| [`FLAMA_POST_REFACTOR_REVIEW.md`](historical/FLAMA_POST_REFACTOR_REVIEW.md) | Đánh giá sau đợt refactor ban đầu. |
| [`FLAMA_REFACTOR_PLAN.md`](historical/FLAMA_REFACTOR_PLAN.md) | Kế hoạch refactor cấu trúc module ban đầu. |
| [`FLAMA_PAYMENT_DOMAIN_EXPANSION_PLAN.md`](historical/FLAMA_PAYMENT_DOMAIN_EXPANSION_PLAN.md) | Bản thiết kế thanh toán cũ (đã thay thế bởi payOS). |
| [`flashcard_system_design.md.resolved`](historical/flashcard_system_design.md.resolved) | Bản thiết kế hệ thống Flashcard ban đầu. |
| [`SECURITY_ASSESSMENT_2026-04-06.md`](historical/SECURITY_ASSESSMENT_2026-04-06.md) | Báo cáo đánh giá an toàn thông tin ngày 2026-04-06. |

---

## 🛠️ 6. Agent Skills & Quy Trình Làm Việc (`docs/skills/`)

Các quy chuẩn và kỹ năng dành cho các AI Coding Agent (Antigravity, Codex, Tri, San, v.v.):

| Tài liệu | Mô tả |
|---|---|
| [`DATABASE_ARCHITECTURE.md`](skills/DATABASE_ARCHITECTURE.md) | **Cẩm nang điều tra & tiến hóa kiến trúc CSDL Flama MySQL** (Entity Landscape, Checklist rà soát, Migration 5 pha zero-downtime). |
| [`BRANCH_STRATEGY.md`](skills/BRANCH_STRATEGY.md) | **Chiến lược phân nhánh Git cho Agent** (Quy tắc không làm bẩn master/develop, task isolation). |

---

## 🔍 7. Code Review (`docs/reviews/`)

Các báo cáo review code/tài liệu để tra cứu lại:

| Tài liệu | Mô tả |
|---|---|
| [`code-review-c2c5902-decoupling-docs-2026-08-25.md`](reviews/code-review-c2c5902-decoupling-docs-2026-08-25.md) | Review commit `c2c5902` (bộ tài liệu decoupling + skill database-architecture): 6 phát hiện + danh sách claim đã kiểm chứng. |
