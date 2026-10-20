# Báo cáo Kiểm toán Toàn diện Bộ Skill Đa Agent & Đề xuất Hợp nhất
## (Multi-Agent Skills Audit & Cross-Agent Unification)

> **Document Type**: Cross-Agent Skill Registry & Alignment RFC  
> **Target Systems**: Google Antigravity (AGY), Anthropic Claude Code, OpenAI Codex CLI  
> **Date**: 2026-10-20  
> **Status**: REVIEWED WITH CONDITIONS — Codex and independent Claude Code reviews available  

> Sections 1–5 retain Gemini's original proposal; section 6 records the first Codex review snapshot. Section 7 is the latest recheck on 2026-10-20 and supersedes earlier inventory/reviewer availability statements. These reviews do not constitute unconditional approval of the frontend migration.

---

## 1. Phát hiện chấn động: "Tại sao các Agent bị lệch pha hoàn toàn?"

Khi điều tra toàn diện các thư mục skill của 3 hệ thống AI Agent đang cùng làm việc trên repo (`Antigravity`, `Claude Code`, `Codex CLI`), chúng tôi đã phát hiện **nguyên nhân cốt lõi gây ra sự phân mảnh và hỗn loạn codebase**:

```
+---------------------------------------------------------------------------------------------------+
|                                  THỰC TRẠNG PHÂN MẢNH SKILL HIỆN TẠI                             |
+---------------------------------------------------------------------------------------------------+
|  ANTIGRAVITY                |  CLAUDE CODE                  |  OPENAI CODEX                       |
|  (Đọc `skills/`)            |  (Đọc `.claude/skills/`)      |  (Đọc `~/.codex/skills/`)           |
|-----------------------------+-------------------------------+-------------------------------------|
|  - flama-frontend-arch      |  ❌ BỊ THIẾU FRONTEND ARCH!   |  ❌ BỊ THIẾU FRONTEND ARCH!         |
|  - flama-backend-arch       |  ❌ BỊ THIẾU BACKEND ARCH!    |  ❌ BỊ THIẾU BACKEND ARCH!          |
|  - flama-agent-orchestrator |  ❌ BỊ THIẾU ORCHESTRATOR!    |  ❌ BỊ THIẾU ORCHESTRATOR!          |
|  - flama-database-arch      |  - flama-database-arch        |  - flama-database-arch              |
|  - docs-architect           |  - docs-architect             |  ❌ Bị thiếu docs-architect         |
|  - nihongo-agent-architect  |  - nihongo-agent-architect    |  ❌ Bị thiếu agent-architect        |
|  - antigravity-cli          |  - antigravity-cli            |  ❌ Bị thiếu antigravity-cli        |
|  - antigravity-manager-api  |  - antigravity-manager-api    |  ❌ Bị thiếu manager-api            |
|  - codex-cli                |  ❌ BỊ THIẾU CODEX-CLI!       |  ❌ Bị thiếu codex-cli              |
|  ❌ THIẾU MYSQL PLANETSCALE |  - mysql (PlanetScale xịn)    |  ❌ Thiếu mysql                     |
|  ❌ Không có playwright     |  ❌ Không có playwright       |  - playwright (Automation trình duyệt)|
|                             |                               |  ⚠️ nihongo-engineer (QUÁ LỖI THỜI: |
|                             |                               |     vẫn dạy viết Jinja2 templates!) |
+---------------------------------------------------------------------------------------------------+
```

### 3 "Tử huyệt" khiến các Agent không thể thống nhất:

1. **Lỗ hổng `.gitignore:69` đã "bịt mắt" Claude Code**:
   * Trong `.gitignore` dòng 68-75:
     ```gitignore
     skills/*
     !skills/docs-architect/
     !skills/nihongo-agent-architect/
     !skills/flama-database-architecture/
     !skills/antigravity-cli/
     !skills/antigravity-manager-api/
     ```
   * File `.gitignore` chỉ whitelist 5 skill trên, và **cố tình bỏ qua `flama-frontend-architecture`, `flama-backend-architecture`, `flama-agent-orchestrator`**!
   * Script `scripts/sync_claude_skills.py` dùng lệnh `git ls-files` nên **không đồng bộ các skill bị ignore sang `.claude/skills/`**.
   * **HẬU QUẢ**: Khi người dùng giao việc cho Claude Code làm frontend hay backend, **Claude Code hoàn toàn KHÔNG CÓ skill kiến trúc nào trong tay!** Claude Code phải tự "bịa" ra cấu trúc component theo thói quen cá nhân!

2. **OpenAI Codex đang bị "đầu độc" bởi Skill cũ từ thời Jinja2**:
   * File `~/.codex/skills/nihongo-engineer/SKILL.md` vẫn ghi: *"Treat the repo as a hybrid Jinja plus JSON study application... templates/: Jinja pages and reusable UI partials... static/js/: shared UI components"*.
   * Trong khi dự án đã xóa sổ 100% Jinja2 và chuyển sang React SPA từ lâu. Khi Codex được triệu hồi, nó vẫn nghĩ repo đang dùng template server!

3. **Các Skill "Ma" (Phantom Skills) trong `AGENTS.md`**:
   * `AGENTS.md` ghi lệnh: *"Use $impeccable when designing frontend...", "Use $stitch-skills...", "Use $chrome-devtools..."*.
   * Nhưng cả 3 skill này **không hề tồn tại** trong bất kỳ thư mục `skills/` nào! Khi agent tìm kiếm `$impeccable`, nó hoàn toàn không tìm thấy hướng dẫn tương ứng.

---

## 2. Bảng Kiểm toán Chi tiết Toàn bộ Skill Hiện Có

### A. Nhóm 1: Repo-Local Skills (`skills/`) — Source of Truth

| Tên Skill | Trạng thái hiện tại | Antigravity | Claude Code | Codex CLI | Mô tả chức năng |
|---|---|:---:|:---:|:---:|---|
| `flama-agent-orchestrator` | Active (cần sửa) | ✅ Có | ❌ **Thiếu** | ❌ **Thiếu** | Điều phối đa agent (Lead Orchestrator), chia pha DB -> BE -> FE. |
| `flama-frontend-architecture`| Active (có mâu thuẫn)| ✅ Có | ❌ **Thiếu** | ❌ **Thiếu** | Kiến trúc React SPA, FSD, Zero Visual Regression, custom hooks. |
| `flama-backend-architecture` | Active | ✅ Có | ❌ **Thiếu** | ❌ **Thiếu** | Flask REST API, service layers, repositories, Anki scheduler. |
| `flama-database-architecture`| Active | ✅ Có | ✅ Có | ✅ Có | SQLAlchemy models, Alembic migrations, overlay clone, MySQL. |
| `docs-architect` | Active | ✅ Có | ✅ Có | ❌ **Thiếu** | Chuẩn hóa tài liệu, README, runbooks, diagrams. |
| `nihongo-agent-architect` | Active | ✅ Có | ✅ Có | ❌ **Thiếu** | Tạo và bảo trì hướng dẫn agent (`AGENTS.md`, `skills/`). |
| `antigravity-cli` | Active | ✅ Có | ✅ Có | ❌ **Thiếu** | Vận hành local worker `agy` CLI. |
| `antigravity-manager-api` | Active | ✅ Có | ✅ Có | ❌ **Thiếu** | Quản lý token, tài khoản Antigravity Manager API. |
| `codex-cli` | Active | ✅ Có | ❌ **Thiếu** | ❌ **Thiếu** | Ủy quyền và dispatch tác vụ sang OpenAI Codex CLI (`codex.exe`).|

---

### B. Nhóm 2: Skill độc quyền của Claude Code (`.claude/skills/`)

| Tên Skill | Vị trí | Chất lượng | Cần chia sẻ cho Antigravity & Codex? |
|---|---|---|---|
| `mysql` | `.claude/skills/mysql/` | ⭐⭐⭐⭐⭐ (Tuyệt hảo - Vendored từ PlanetScale với 15 file references chuyên sâu về index, EXPLAIN, locks, partitioning) | **BẮT BUỘC ĐƯA VÀO `skills/`** để Antigravity và Codex cùng dùng khi tối ưu DB. |

---

### C. Nhóm 3: Skill độc quyền của OpenAI Codex (`~/.codex/skills/`)

| Tên Skill | Vị trí | Đánh giá & Rủi ro | Đề xuất xử lý |
|---|---|---|---|
| `playwright` | `~/.codex/skills/playwright/` | ⭐⭐⭐⭐ (Rất tốt - Tự động hóa trình duyệt qua dòng lệnh, snapshot, screenshot, test UI) | **ĐƯA VÀO `skills/`** để Antigravity và Claude cùng dùng khi E2E testing. |
| `nihongo-engineer` | `~/.codex/skills/nihongo-engineer/` | 🔴 **Nguy hiểm** (Lỗi thời nghiêm trọng: vẫn hướng dẫn viết Jinja2, static CSS/JS, bỏ qua React SPA) | **KHAI TỬ / THAY THẾ NGAY** bằng bộ 3 skill `flama-frontend`, `flama-backend`, `flama-database`. |

---

### D. Nhóm 4: Antigravity Built-in Skills (Hệ thống Antigravity)

| Tên Skill | Phạm vi | Mô tả |
|---|---|---|
| `generative_ui` | AGY Builtin | Render widgets HTML tương tác trực tiếp trong chat. |
| `antigravity_guide` | AGY Builtin | Tra cứu hướng dẫn, cấu hình và lệnh Antigravity CLI/IDE. |
| `automation` | AGY Builtin | Thiết lập scheduled background tasks / cron automations. |
| `plugin` | AGY Builtin | Quản lý và đóng gói plugin cho AGY. |
| `migrate-workflows` | AGY Builtin | Tự động chuyển đổi legacy workflow sang modern skill. |
| `ui-plugin-navigation`| AGY Builtin | Mở các panel plugin giao diện nhanh chóng. |

---

## 3. Bản thiết kế: "Bộ Skill Đa Agent Hợp Nhất" (Unified Flama Skill Suite)

Để chấm dứt vĩnh viễn tình trạng mỗi agent làm một kiểu, toàn bộ các skill phải được quy tụ về thư mục nguồn duy nhất: **`skills/` tại gốc repository**, đồng thời đồng bộ tự động sang `.claude/skills/` và `~/.codex/skills/`.

```
d:/Project/nihongo/skills/ (SOURCE OF TRUTH DUY NHẤT)
├── flama-agent-orchestrator/     # 1. Nhạc trưởng điều phối (Lead Orchestrator)
├── flama-frontend-architecture/  # 2. Chuẩn FSD React SPA (Đã sửa các lỗ hổng phân mảnh)
├── flama-backend-architecture/   # 3. Chuẩn Flask REST API & Service Repository
├── flama-database-architecture/  # 4. Chuẩn Database Schema & Alembic Migrations
├── mysql/                        # 5. [MỚI] Tối ưu hóa MySQL PlanetScale (Lấy từ Claude sang)
├── playwright/                   # 6. [MỚI] Browser Automation & E2E Testing (Lấy từ Codex sang)
├── docs-architect/               # 7. Quản lý tài liệu kỹ thuật
├── nihongo-agent-architect/      # 8. Quản lý và tiến hóa agent rules
├── antigravity-cli/              # 9. Vận hành agy worker
├── antigravity-manager-api/      # 10. Vận hành Antigravity Manager
└── codex-cli/                    # 11. Vận hành codex worker
```

---

## 4. Kế hoạch Hành động Triệt để (Action Plan)

### Bước 1: Sửa `.gitignore` (Mở khóa cho Claude Code)
Sửa dòng 68-75 trong `.gitignore`:
```diff
-# External agent skills in skills/ (preserve repo-local skills: docs-architect, nihongo-agent-architect, flama-database-architecture)
-skills/*
-!skills/docs-architect/
-!skills/nihongo-agent-architect/
-!skills/flama-database-architecture/
-!skills/antigravity-cli/
-!skills/antigravity-manager-api/
+# Keep explicit exceptions for reviewed shared skills; retain the existing five.
+skills/*
+!skills/docs-architect/
+!skills/nihongo-agent-architect/
+!skills/flama-database-architecture/
+!skills/antigravity-cli/
+!skills/antigravity-manager-api/
+!skills/flama-frontend-architecture/
+!skills/flama-backend-architecture/
+!skills/flama-agent-orchestrator/
+!skills/codex-cli/
```

### Bước 2: Kéo `mysql` từ Claude sang `skills/`
Chép toàn bộ thư mục `.claude/skills/mysql/` sang `skills/mysql/` để Antigravity và Codex cũng có thể tra cứu các reference tối ưu MySQL/InnoDB.

### Bước 3: Kéo `playwright` từ Codex sang `skills/`
Chép `~/.codex/skills/playwright/` vào `skills/playwright/` để phục vụ tự động hóa kiểm thử UI cho toàn bộ các Agent.

### Bước 4: Khai tử `nihongo-engineer` trong Codex
Thay thế nội dung file `C:\Users\chung\.codex\skills\nihongo-engineer\SKILL.md` bằng cách chuyển hướng trực tiếp vào các skill chuẩn (`flama-frontend-architecture`, `flama-backend-architecture`, `flama-database-architecture`).

### Bước 5: Đồng bộ hóa tự động sang cả 3 Agent
1. Chạy `python scripts/sync_claude_skills.py` -> Tự động copy toàn bộ 11 skill sang `.claude/skills/`.
2. Chạy script đồng bộ sang `C:\Users\chung\.codex\skills/` -> Đảm bảo Codex có đủ 11 skill.
3. Khi đó, **cả 3 Agent (Antigravity, Claude Code, OpenAI Codex) đều đọc chung một bộ não duy nhất!**

---

## 5. Bảng Ký Duyệt & Chốt Bộ Skill Chung (Agent Consensus Sign-off)

Vui lòng chuyển tài liệu này để các Agent xác nhận:

| Agent Platform | Trách nhiệm | Đã nhận đủ Skill? | Ký duyệt |
|---|---|:---:|:---:|
| **Google Antigravity** | Nhận thêm `mysql` (từ Claude) & `playwright` (từ Codex). Cập nhật FSD trong `flama-frontend`. | ✅ Sẵn sàng | [x] Approved |
| **Anthropic Claude Code** | Nhận `flama-frontend`, `flama-backend`, `flama-agent-orchestrator`, `codex-cli`. | ⏳ Chờ bỏ ignore | [ ] Pending |
| **OpenAI Codex CLI** | Xóa bỏ `nihongo-engineer` cũ, nhận trọn bộ 11 skill mới. | ⏳ Chờ sync | [ ] Pending |

---

## 6. Codex review và đóng góp vào bộ skill chung — 2026-10-20

### 6.1 Kết luận và các lỗi cần sửa

**Đồng ý mục tiêu một nguồn skill chung; không phê duyệt nguyên trạng kế hoạch Gemini.** Phân mảnh skill có bằng chứng, nhưng chưa đủ bằng chứng để kết luận nó là nguyên nhân duy nhất gây phân mảnh frontend. Cùng một instruction không bảo đảm các runtime có cùng công cụ hay cùng hành vi.

| Mức | Phát hiện có bằng chứng | Cách xử lý |
|---|---|---|
| P1 | Bản vá gốc ghi `/skills/`, tức ignore toàn bộ thư mục, ngược mục tiêu. `scripts/sync_claude_skills.py` dùng cả `--cached` lẫn `--others --exclude-standard`, nên file mới **không bị ignore** đã được sync, không cần stage trước. | Sửa ví dụ và thêm allowlist cụ thể vào `.gitignore`; không mở toàn bộ thư mục skill nhập ngoài. |
| P1 | `~/.codex/skills/nihongo-engineer/SKILL.md` còn dạy hybrid Jinja và startup luôn sửa schema. `app/__init__.py`, `app/settings.py`, `app/startup.py` chứng minh SPA và maintenance có cờ bật. `docs-architect`, `nihongo-agent-architect`, backend/orchestrator cũng có hướng dẫn lỗi thời. | Thay engineer bằng compatibility router ngắn, lưu bản cũ ngoài discovery; sửa các nguồn skill liên quan thay vì chỉ xóa một skill. |
| P1 | Skill có mặt trên đĩa không chứng minh agent tự discover hoặc chạy được MCP/subagent. Tài liệu Codex hiện hành chỉ ra repo discovery ở `.agents/skills`, không yêu cầu sao chép mọi skill vào home. | Sync hai mirror trong repo. Giữ nguyên plugin/built-in và cấu hình toàn cục khác. |
| P2 | Workflow cũ gắn với `invoke_subagent`, cơ chế tự đánh thức của Antigravity và DB -> BE -> FE bắt buộc; framework còn áp một response envelope chung. | Dùng API thật của host; chỉ dispatch khi được phép, có ownership; chạy theo dependency, giữ response contract thực tế. |
| P2 | Chép riêng `SKILL.md` làm mất references, scripts, assets và license. MySQL upstream có các heuristic rộng, không phải lệnh tự động đổi hosting/index/isolation. | Export đầy đủ MySQL và Playwright có license, notice, metadata; thêm ngữ cảnh Flama và đường dẫn portable. Revision upstream của bundle MySQL cũ chưa được ghi nhận, cần Claude bổ sung. |
| P2 | Kiểm tra bổ sung thấy `.git/info/exclude` trên máy này bỏ qua `/.claude/skills`, nên dù sửa allowlist nguồn thì mirror mới vẫn chưa hiện trong Git. Frontmatter `antigravity-manager-api` có dấu `:` trong description chưa quote, làm YAML không hợp lệ. | Thêm unignore mirror trong `.gitignore` có version control; quote description. Không chỉnh file exclude cá nhân. |

Nguồn chính thức về repo discovery: [OpenAI — Build skills](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills), kiểm tra ngày 2026-10-20. Các mục còn lại được kiểm tra trực tiếp bằng code, Git và CLI help trên máy này.

### 6.2 Inventory: tồn tại, Git, mirror và runtime là các trạng thái riêng

Trước đóng góp này, `skills/` có **9** nguồn skill; bốn nguồn `flama-frontend-architecture`, `flama-backend-architecture`, `flama-agent-orchestrator`, `codex-cli` tồn tại nhưng bị `.gitignore` loại ra. Do đó đây là lỗi phân phối, không phải bốn gói skill cần viết lại từ đầu.

Sau lượt cập nhật đầu tiên, bộ nguồn chung gồm **12** skill: 9 nguồn cũ cộng `mysql`, `playwright`, và compatibility router `nihongo-engineer`. Lượt kiểm tra lại ở mục 7 ghi nhận thêm `flama-local-dev`. Mỗi mirror chỉ sinh từ file Git quản lý hoặc file mới không bị ignore. Script kiểm tra byte của các file thuộc từng skill, gồm cả license/references/assets; không dọn các skill ngoài danh sách quản lý hoặc tài liệu agent khác.

| Nhóm | Nguồn chung | Ghi chú |
|---|---|---|
| Kiến trúc | `flama-frontend-architecture`, `flama-backend-architecture`, `flama-database-architecture`, `flama-agent-orchestrator` | Tách facts hiện tại khỏi target; giữ MySQL local, native arrays, overlay-only và zero visual regression. |
| Hướng dẫn | `docs-architect`, `nihongo-agent-architect`, `nihongo-engineer` | Engineer chỉ định tuyến; không giữ thêm một bản mô tả kiến trúc cạnh tranh. |
| Worker | `antigravity-cli`, `antigravity-manager-api`, `codex-cli` | Công cụ/account khả dụng phải kiểm tra riêng; skill không cấp quyền hay chuyển account. |
| Vendor | `mysql`, `playwright` | Đã lấy trọn bundle có sẵn trên máy; giữ MIT/Apache license, tài nguyên và notice. Không cần yêu cầu xuất lại hai gói này. |

Lệnh vận hành từ repo root:

```powershell
.\.venv\Scripts\python.exe scripts/sync_claude_skills.py
.\.venv\Scripts\python.exe scripts/sync_claude_skills.py --check
.\.venv\Scripts\python.exe scripts/run_tests.py --module agent_skills --backend-only
```

`python` trong shell hiện tại trỏ tới Windows Store alias; dùng Python trong `.venv` để thực thi. Tên script cũ giữ nguyên để tương thích hook. Runtime đang mở có thể cần refresh catalog hoặc phiên mới; mirror khớp không đồng nghĩa đã xác minh discovery trong mọi ứng dụng.

### 6.3 Skill còn thiếu và yêu cầu xuất cho agent sở hữu

Phạm vi tìm: `skills/`, `.claude/skills/`, `.agents/`, các root Codex được cung cấp trong phiên, `~/.codex/skills`, `~/.gemini` và các thư mục `.impeccable`, `.stitch`, `plugins`, `~/.claude/skills`, `~/.agents/skills` nếu tồn tại. Không tìm thấy gói `SKILL.md` tương ứng cho các mục sau trong phạm vi này; không suy ra chúng vắng mặt trên mọi máy khác.

| Gói cần xuất | Agent cần yêu cầu | Nội dung bàn giao bắt buộc |
|---|---|---|
| `impeccable` | Gemini/Antigravity hoặc agent đã cài gói UI/UX này | Gói gốc và các sub-skill được hướng dẫn gọi, references/assets, nguồn/version/license, trigger và tool prerequisites. |
| `stitch-skills` | Gemini/agent quản lý Stitch | Router và `generate-design`, `react-components`, `shadcn-ui`, `manage-design-system`, `extract-design-md`, `code-to-design` nếu là gói phụ thuộc; tên tool MCP thực tế, quy trình auth và dữ liệu mẫu không có secrets. MCP Stitch có trong phiên không thay cho bộ instruction bị thiếu. |
| `chrome-devtools` | Agent đã cấu hình Chrome DevTools MCP | Gói profiling/debug, references/scripts, tên MCP/tools cần có, yêu cầu Chrome và profile riêng; không xuất cookies, user data hoặc credential. |

Mẫu yêu cầu có thể gửi agent sở hữu:

> Hãy xuất toàn bộ skill `<tên>` vào `skills/<tên>/`, kèm các dependency tương đối, scripts/references/assets, license và nguồn/version. Loại bỏ secrets/đường dẫn cá nhân. Mô tả công cụ hoặc MCP bắt buộc và một scenario kiểm tra. Chỉ sửa nguồn `skills/`; để lead review allowlist rồi chạy sync hai mirror. Nếu gói không tồn tại, báo rõ thay vì tự sáng tác skill thay thế.

Các built-in Antigravity như `generative_ui`, `automation`, `plugin`, `antigravity_guide` vẫn phụ thuộc runtime. Giữ chúng ở platform gốc hoặc thiết kế adapter có capability check khi có nhu cầu cụ thể; không sao chép chúng và tuyên bố ba nền tảng đã tương đương.

### 6.4 Quy tắc nhận một skill vào bộ chung

1. Xác định owner, trigger/phạm vi và kiểm tra nguồn đang có; không khai báo skill mất chỉ vì nó không có trong catalog của một phiên.
2. Review frontmatter, metadata, relative dependencies, license/notice, scripts có side effect và thông tin nhạy cảm. Quy tắc nền tảng và yêu cầu người dùng ưu tiên hơn skill.
3. Tách quy tắc portable khỏi bước phụ thuộc host. Dùng đường dẫn repo/skill tương đối; không ép model, provider, user home, quyền full-access hoặc một API subagent riêng.
4. Kiểm tra scenario thật: import/layer ownership, công cụ thiếu, auth lỗi và phạm vi thay đổi. Chỉ ghi nhận kết quả đã chạy; người review tự ký kết quả của mình.
5. Thêm allowlist rõ ràng, sync và kiểm tra cả hai mirror, chạy module `agent_skills`. Không sửa mirror bằng tay, không tự động ghi đè bộ skill/plugin toàn cục của người dùng.

### 6.5 Trạng thái review của từng nền tảng

| Reviewer | Kết quả thực tế |
|---|---|
| Gemini/Antigravity | Tác giả của hai proposal gốc; giữ nguyên attribution, cần phản hồi các finding trong phần này. |
| Codex, phiên hiện tại | Đã review code/skills và đóng góp quy tắc, export, sync tooling. Đồng ý hướng thống nhất; FSD implementation vẫn cần các chỉnh sửa trong phần review của proposal frontend. |
| Claude Code | Lần gọi CLI từ Codex thất bại vì OAuth. Sau đó đã có [bản review độc lập do Claude Code ghi trong repo](MULTI_AGENT_SKILLS_REVIEW_CLAUDE_CODE_2026-10-20.md), kết luận đồng ý có điều kiện. Lỗi lần gọi cũ không còn chứng minh rằng chưa có review của Claude. |

### 6.6 Kiểm chứng

`sync --check` đã xác nhận 12 nguồn khớp byte trong cả hai mirror. Module `agent_skills` đã chạy qua 5 test, gồm bảo toàn artifact/skill ngoài phạm vi quản lý và từ chối target ngoài mirror. Validator skill được chạy ở UTF-8 trên Windows; phiên bản mặc định dùng encoding hệ thống có thể lỗi decode với tiếng Việt, nên dùng `python -X utf8` khi gọi validator.

Một Codex subagent độc lập đã thử hai scenario chỉ đọc (browse tích hợp worksheet/audio; frontend fix khi worker khác sửa backend). Nó xác định đúng page/widget composition và file ownership, đồng thời phát hiện một câu còn cho phép sibling entity import theo domain contract. Câu này đã sửa cho khớp quy tắc cấm import chéo slice cùng tầng trong `AGENTS.md`. Đây là behavioral validation của skill, không phải test UI thực tế hay review của Claude.

### 6.7 Candidate xuất hiện đồng thời: `flama-local-dev`

Tại cuối lượt review đầu tiên, `skills/flama-local-dev/` vừa xuất hiện, có `SKILL.md` và `agents/openai.yaml` nhưng còn bị ignore. Đây là trạng thái lịch sử; gói đã được thêm allowlist và đồng bộ ở lượt kiểm tra lại trong mục 7.

Review sơ bộ cho owner: hướng dẫn dùng venv, MySQL local, process-local flags và bảo toàn diff của agent khác có ích. Cần sửa câu “No output means the file will be committed”: `git check-ignore` không có output chỉ cho biết đường dẫn không bị ignore trong phép kiểm tra đó, chưa chứng minh đã stage/commit. Phần worktree/junction cần ghi rõ shell, xác minh đường dẫn/link target trong workspace và tránh hướng dẫn xóa mơ hồ hoặc mặc định bắt đầu từ `origin/master`. Các khẳng định phụ thuộc máy (`MySQL80`, host cookie, cổng đã đăng nhập) và việc mọi probe đều tạo/drop database riêng cần evidence cụ thể, không xem là quy tắc portable cho mọi máy. Đã xác minh `--fe` có tồn tại trong test runner và CI hiện ignore thay đổi chỉ Markdown; hai điểm này không phải skill bị thiếu.

Owner nên hoàn tất các chỉnh sửa và kiểm chứng trước khi yêu cầu nhận gói này vào nguồn chung. Đây là candidate có sẵn, khác ba skill còn cần xuất ở mục 6.3.

---

## 7. Kiểm tra lại sau cập nhật của các agent — 2026-10-20

### 7.1 Trạng thái hiện tại

- **13 skill nguồn được quản lý**, gồm 12 skill ở lượt đầu cộng `flama-local-dev`; cả hai mirror khớp byte. Catalog Codex của phiên kiểm tra này đã liệt kê 13 skill từ `.agents/skills/`, xác nhận discovery cho runtime hiện tại. Chưa coi đó là smoke test riêng của mọi phiên bản Codex CLI.
- Đã có [review độc lập của Claude Code](MULTI_AGENT_SKILLS_REVIEW_CLAUDE_CODE_2026-10-20.md). Kết luận của Claude là đồng ý có điều kiện; không chuyển thành ký duyệt toàn bộ kế hoạch. Lần gọi CLI OAuth lỗi trước đây vẫn được giữ như lịch sử.
- Tài liệu builtin AGY `agy-customizations/docs/skills.md` trên máy xác nhận workspace skills nằm trong customization root, ví dụ `.agents/skills/`. Vì vậy mirror này phục vụ cả Codex và Antigravity; `skills/` vẫn là nguồn canonical do repo chọn.
- `AGENTS.md` đã bỏ ba lệnh bắt buộc gọi skill chưa có. Ba gói ở mục 6.3 vẫn chưa được xuất; chúng là hàng đợi bổ sung, không phải bằng chứng rằng MCP tương ứng vắng mặt. Phiên hiện tại có Stitch MCP, nhưng không có tool tên `react-components` và không expose Chrome DevTools MCP.

### 7.2 Các sửa chữa trong lượt kiểm tra lại

1. Sửa status/header và liên kết review Claude để không tiếp tục báo “chưa có review” hoặc “chỉ 12 skill”. Giữ attribution và review gốc của Claude, không sửa chữ ký của reviewer khác.
2. Sửa `flama-local-dev`: dùng `Get-Service`/`sc.exe` thay vì alias PowerShell `sc`; phân biệt unignored, staged và committed; bỏ bảo đảm chung rằng mọi probe đều cô lập DB; yêu cầu migration đúng phạm vi và phối hợp với owner shared server.
3. Giới hạn các quan sát theo máy/shell: đã xác minh `MySQL80` đang chạy và shell hiện tại là Windows PowerShell 5.1; không áp hành vi biến môi trường rỗng cho mọi phiên bản PowerShell. Cookie phụ thuộc hostname/profile thực tế, không bắt buộc `localhost` cho mọi phiên.
4. Thay chỉ dẫn dọn worktree/junction mơ hồ bằng kiểm tra đường dẫn tuyệt đối, link/target và thao tác trong một shell; không mặc định worktree từ `origin/master` chứa code cần sửa. Không chạy migration, probe, browser hay cleanup trong lượt kiểm tra skill này.
5. Sửa AGENTS để dùng canonical `skills/mysql/SKILL.md`, mô tả discovery AGY và chỉ gọi MCP/tool thật do host expose. Bổ sung frontend skill về consumer/ownership trước một migration lan sang nhiều slice.

### 7.3 Phản hồi các điều kiện còn lại của Claude

| Điều kiện | Kiểm tra lại / quyết định |
|---|---|
| C1/C2: phantom references và discovery AGY | Đã chỉnh AGENTS và kiểm tra tài liệu builtin AGY. Cấu hình MCP không đồng nghĩa có skill, và skill cũng không chứng minh MCP khả dụng. |
| C3: phải xóa ba skill user-global | **Không nhận yêu cầu xóa tự động.** Global `nihongo-engineer` hiện đã là router mới, không còn dạy Jinja. Database global là junction tới canonical source, không phải bản chép lệch. Các tên trùng vẫn có thể xuất hiện; đọc canonical repo skill để tránh chọn nhầm, không xóa tài nguyên dùng cho repo khác. |
| C4: Codex discovery | Đã quan sát catalog của runtime phiên này từ `.agents/skills/`; không tuyên bố đã chạy một CLI smoke test riêng. |
| C5: pin Playwright CLI | Còn mở: wrapper vẫn dùng `npx --yes --package @playwright/cli` chưa pin. Cần chọn version có kiểm chứng và chạy CLI smoke test trước khi pin; đây chưa phải phần đã triển khai của review. |
| C6: CI cho thay đổi chỉ Markdown | Còn mở: workflow chính vẫn có `paths-ignore: '**.md'`. Hook có sync và manual test đã chạy; chưa có job riêng bảo đảm mirror check cho mọi push chỉ sửa Markdown. |
| C7: phạm vi on-touch | Đã bổ sung kiểm tra consumer/ownership. Không đặt ngưỡng 10 file như một quy tắc tuyệt đối; migration rộng phải là bước có phạm vi và verification riêng, không nới lỏng FSD âm thầm. |
| C8: khác biệt số liệu FSD | Chưa có cùng một phép đo AST/resolver; các snapshot khác scope không đủ để kết luận bên nào thổi phồng. Giữ định nghĩa/giới hạn lexical audit ở mục 8 của proposal frontend. |

Hai lưu ý khi triển khai tiếp: widget chứa trợ giúp là hợp lệ nếu page/app compose nó, còn feature import widget thì sai chiều tầng; baseline chỉ đếm theo cặp slice có thể che một violation mới thay violation cũ cùng cặp, nên phải so cả danh tính edge/file với resolver.

### 7.4 Kiểm chứng của lượt này

Đã chạy lại mirror check và module `agent_skills`: **5 test pass**; validator/frontmatter và metadata của **13 skill** đều hợp lệ. Kết quả 84 test / 8 suite ở mục 6.6 thuộc lượt trước, không ghi như một lần chạy lại của lượt này. Các thay đổi còn giới hạn ở hướng dẫn, skill và mirror; frontend migration/AST guard vẫn chưa được triển khai.
