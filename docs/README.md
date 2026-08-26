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
| [`study-interaction-trigger-algorithm-plan.md`](architecture/study-interaction-trigger-algorithm-plan.md) | **Tracker canonical cho refactor Study/Interaction/Trigger/Algorithm/Progress**; Phase 0–2 đang triển khai một phần, Phase 3–9 chưa bắt đầu. |
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
| [`DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md`](plans/proposals/DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md) | Bản thảo đề xuất tách Template độc lập khỏi Note Type. |
| [`FLASHCARD_FOR_KIDS_PLAN.md`](plans/proposals/FLASHCARD_FOR_KIDS_PLAN.md) | Ý tưởng phát triển bộ flashcard chuyên biệt cho trẻ em. |

---

## 🚀 3. Hướng Dẫn Vận Hành & Release (`docs/runbooks/`)

Các tài liệu hướng dẫn quy trình vận hành, phát hành và công cụ:

| Tài liệu | Mô tả |
|---|---|
| [`FLASHCARD_V2_RUNBOOK.md`](runbooks/FLASHCARD_V2_RUNBOOK.md) | Runbook vận hành hệ thống Flashcard V2, template syntax và schema baseline. |
| [`FLAMA_AUDIO_WINDOWS_RELEASE.md`](runbooks/FLAMA_AUDIO_WINDOWS_RELEASE.md) | Quy trình build, ký số Authenticode và phát hành `FlamaAudio-Portable.exe`. |
| [`CHUNGBECH_IMPORT_GUIDE.md`](runbooks/CHUNGBECH_IMPORT_GUIDE.md) | Hướng dẫn import file TSV Anki ChungBech. |

---

## 📜 4. Tài Liệu Lịch Sử & Đã Thay Thế (`docs/historical/`)

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

## 🛠️ 5. Agent Skills & Quy Trình Làm Việc (`docs/skills/`)

Các quy chuẩn và kỹ năng dành cho các AI Coding Agent (Antigravity, Codex, Tri, San, v.v.):

| Tài liệu | Mô tả |
|---|---|
| [`DATABASE_ARCHITECTURE.md`](skills/DATABASE_ARCHITECTURE.md) | **Cẩm nang điều tra & tiến hóa kiến trúc CSDL Flama MySQL** (Entity Landscape, Checklist rà soát, Migration 5 pha zero-downtime). |
| [`BRANCH_STRATEGY.md`](skills/BRANCH_STRATEGY.md) | **Chiến lược phân nhánh Git cho Agent** (Quy tắc không làm bẩn master/develop, task isolation). |

---

## 🔍 6. Code Review (`docs/reviews/`)

Các báo cáo review code/tài liệu để tra cứu lại:

| Tài liệu | Mô tả |
|---|---|
| [`code-review-c2c5902-decoupling-docs-2026-08-25.md`](reviews/code-review-c2c5902-decoupling-docs-2026-08-25.md) | Review commit `c2c5902` (bộ tài liệu decoupling + skill database-architecture): 6 phát hiện + danh sách claim đã kiểm chứng. |

