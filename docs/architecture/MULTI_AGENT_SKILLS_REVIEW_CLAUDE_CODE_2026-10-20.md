# Claude Code review: đề xuất hợp nhất skill và FSD của Gemini

> **Loại tài liệu**: Review độc lập, kèm hàng đợi skill còn thiếu
> **Người review**: Claude Code (Opus 5.5)
> **Ngày**: 2026-10-20
> **Phạm vi**: `docs/architecture/MULTI_AGENT_SKILLS_AUDIT_AND_UNIFICATION.md`, `docs/architecture/FLAMA_FRONTEND_FSD_CONSOLIDATION_AND_AGENT_ALIGNMENT_PROPOSAL.md`, cùng bản triển khai Codex đang làm song song trong working tree
> **Trạng thái**: Đồng ý có điều kiện (xem mục 7)

Mọi số liệu dưới đây đều đo lại trực tiếp trên working tree ngày 2026-10-20. Trong lúc review, Codex đang sửa `.gitignore`, `AGENTS.md`, `scripts/sync_claude_skills.py`, các `skills/*` và docs. Vì vậy Claude Code không sửa chung các file đó. Phần đóng góp của Claude nằm ở file này và ở skill mới `skills/flama-local-dev/`.

---

## 1. Kết luận nhanh

- Gemini chẩn đoán đúng gốc vấn đề: 4 skill bị `.gitignore` che khỏi Claude Code, skill `nihongo-engineer` của Codex đã lỗi thời, có phantom skill trong `AGENTS.md`, skill frontend cũ cho phép code dùng chung nằm ở hai nơi, và chưa có guard tự động.
- Cách sửa Gemini đề xuất có vài lỗi nặng: diff `.gitignore` làm ngược ý định, nhận định sai về chỗ Antigravity và Codex đọc skill, đặt `ContextHelpButton` vào `widgets/` (đảo chiều tầng FSD), guard script sẽ đỏ ngay từ ngày đầu, và bỏ sót nguyên nhân gốc là alias trong `frontend/components.json`.
- Bản triển khai Codex đã sửa phần lớn các lỗi này (allowlist từng skill, mirror `.agents/skills/`, skill frontend/orchestrator/codex-cli trung lập với host, ratchet baseline, alias Shadcn). Mục 4 liệt kê các việc còn thiếu.
- Hiện vẫn còn 3 nhóm phantom skill chưa ai có: `impeccable`, họ `stitch-skills` và `chrome-devtools` (mục 5).

---

## 2. Kiểm chứng `MULTI_AGENT_SKILLS_AUDIT_AND_UNIFICATION.md`

| Nhận định của Gemini | Kết quả kiểm chứng | Đánh giá |
|---|---|---|
| `flama-frontend/backend/agent-orchestrator` và `codex-cli` bị ignore nên Claude không có | `git status --ignored` trả về `!! skills/codex-cli/`, `!! skills/flama-*/`. `sync_claude_skills.py` dùng `git ls-files --exclude-standard` nên không mirror các skill này | **Đúng** |
| Sửa `.gitignore` thành `/skills/` | Pattern `/skills/` **ignore toàn bộ thư mục**. 5 skill đã track vẫn còn (vì là file cached), nhưng 4 skill thiếu vẫn bị ignore, mọi skill mới sau này cũng vậy, và mất luôn cơ chế giữ skill ngoài ở chế độ private | **Sai, làm ngược ý định**. Codex đã thay bằng allowlist từng skill |
| Antigravity đọc `skills/` | Theo docs builtin của AGY (`~/.gemini/antigravity/builtin/skills/agy-customizations/docs/skills.md`, `json_configs.md`), AGY nhận skill từ customization root `.agents/skills/<name>/` hoặc từ manifest `.agents/skills.json`. AGY "có" skill trong `skills/` chỉ vì `AGENTS.md` trích dẫn đường dẫn | **Không đúng**. Mirror `.agents/skills/` mà Codex tạo cũng phục vụ luôn AGY |
| Codex chỉ đọc `~/.codex/skills/` | Binary `codex-cli 0.150.1` có chuỗi `.agents/skills` (quét skill trong repo). `~/.codex/skills/` hiện có `nihongo-engineer`, `playwright` và symlink `flama-database-architecture` | **Thiếu**. Chưa xác minh ở runtime (mục 4) |
| `nihongo-engineer` (Codex) vẫn dạy Jinja | File 13,6 KB, ngày 2026-03-19, vẫn có câu "hybrid Jinja plus JSON" | **Đúng** |
| Phantom `$impeccable`, `$stitch-skills`, `$chrome-devtools` | Đã tìm trong repo, các mirror, `~/.codex`, `~/.claude`, `~/.gemini` (sâu 8 cấp), `AppData`: không có `SKILL.md` nào. Chỉ có cấu hình MCP `stitch`, `StitchMCP`, `chrome-devtools` trong `~/.gemini/antigravity*/mcp/` | **Đúng**. Vẫn còn ở `AGENTS.md:120-122` |
| Đưa `mysql` vào `skills/` | Hợp lý. Codex đã chép, giữ `LICENSE` (MIT) và thêm mục "Flama integration" vào đầu `SKILL.md` | **Đồng ý** |
| Đưa `playwright` vào `skills/` | Có `LICENSE.txt` (Apache-2.0) và `NOTICE.txt`. Wrapper gọi `npx --yes --package @playwright/cli` **không pin version** và là file `.sh` | **Đồng ý có điều kiện**: pin version (mục 4) |
| Bước 4–5: chép hàng loạt vào `~/.codex/skills/` | Bản chép global sẽ drift, và ghi đè thư mục user-global của agent khác | **Không nên**. Codex chọn mirror trong repo, đúng hướng |
| `Status: APPROVED FOR CROSS-AGENT DISTRIBUTION`, AGY tự ký | Claude và Codex còn `Pending` | **Sai quy trình**: chỉ nên ghi `PROPOSED` cho tới khi đủ chữ ký |

**Những điểm Gemini bỏ sót** (Codex đã sửa trong working tree):

- Description của skill `nihongo-agent-architect` (đã track, Claude đang dùng) vẫn ghi "Jinja plus vanilla JS frontend".
- Skill backend trỏ sai `app/api/identity/` (thực tế là `app/api/v1/identity/`), mô tả `app/routes/vocabulary.py` là "large legacy" (thực tế còn 117 dòng), và không nhắc facade `app/services/share/`.
- Skill `codex-cli` hardcode đường dẫn cài đặt, ví dụ nào cũng dùng `--dangerously-bypass-approvals-and-sandbox`, và có tên model chưa xác minh.
- `AGENTS.md` ghi config nằm trong `app/__init__.py`, trong khi thực tế đã chuyển sang `app/settings.py` và `app/startup.py`.

---

## 3. Kiểm chứng `FLAMA_FRONTEND_FSD_CONSOLIDATION_AND_AGENT_ALIGNMENT_PROPOSAL.md`

### 3.1 Số liệu

| Chỉ số | Gemini | Đo lại | Ghi chú |
|---|---:|---:|---|
| File TS/TSX trong `frontend/src` | 811 | 811 | Khớp |
| File import `components/ui` | 318 | 319 (315 không tính test) | Khớp |
| File import `shared/ui` | 20 | 20 | Khớp |
| File import `app/api.ts` | 93 | **70** (59 không tính test) | Gemini **thổi phồng khoảng 30%** |
| Import chéo feature | 54 | 54 câu lệnh trong 41 file (50/37 không tính test) | Khớp. Tập trung ở: settings→onboarding 12, settings→guide 6, settings→mcp 5. Tổng cộng 14 import đi vào `guide` |
| `window.confirm` | 13 | 13 | Khớp |
| Shim "chết" | 5 | Sai một phần | `features/study/components/CardDisplay.tsx` **vẫn được** `StudyCardRendererFrame.tsx` import. `features/browse/components/MediaFieldPreview.tsx` chỉ còn test của chính nó. `features/settings/components/mcp/hooks/useMcpTokens.ts` không còn ai import |
| File lớn (> 800 dòng) | 12 | 17 file không phải test | 3 trong số đó là dữ liệu tĩnh (`guideData.ts`, `legalDocumentsData*.ts`), không nên áp quy tắc "< 400 dòng" |
| Page nằm trong `features/*/pages` | "hơn 30" | **64 file** | Khối lượng di chuyển lớn gấp đôi ước tính |
| Slice thiếu `index.ts` | (không đo) | **18/26** | Vì thế quy tắc "import qua public API" chưa thể áp dụng |

### 3.2 Những điểm đúng

Skill frontend cũ hợp thức hóa việc để code dùng chung ở cả `components/` lẫn `shared/`. Skill thiếu tầng `entities/`. Page nằm trong feature tạo mâu thuẫn với quy tắc cấm import chéo. Cần dọn shim. Cần guard tự động.

### 3.3 Những điểm sai hoặc rủi ro

1. **Bỏ sót nguyên nhân gốc**: trong `frontend/components.json`, alias đang là `ui: @/components/ui`, `utils: @/lib/utils`, `hooks: @/hooks`. `npx shadcn add` sẽ tiếp tục sinh file ở root. Nếu cấm root mà không đổi alias, agent nào làm đúng theo tool cũng sẽ vi phạm rule.
2. **`ContextHelpButton` đặt vào `widgets/` là đảo tầng**: `widgets` nằm trên `features`, nên feature không được import widget. 14 import vào `guide` sẽ biến thành vi phạm mới. Cách sửa đúng: page ráp nối rồi truyền nút trợ giúp qua slot hoặc children, hoặc tách phần dữ liệu guide khỏi UI guide.
3. **Mâu thuẫn nội tại trong `AGENTS.md`** mà Gemini không phát hiện: quy tắc 2 ("import từ ngoài vào slice phải qua `@/features/<slice>`") có thể hiểu là cho phép import chéo qua barrel, trong khi quy tắc 3 cấm import chéo. Đã có 10/14 import vào `guide` đi qua barrel. Codex đã chốt: "Public API không hợp thức hóa import chéo feature".
4. **Guard `exit(1)` sẽ đỏ ngay ngày đầu** vì đang có 54 vi phạm. Cần baseline ratchet (xem R2).
5. **Phase 2 codemod 319 file** là blast radius rất lớn, xung đột với các agent đang sửa song song. Việc này không được làm theo kiểu "migrate khi chạm file" (xem R1).
6. **Gộp 4 slice `template-*`**: vòng import là có thật (template-library ↔ template-versions, template-library → distribution/marketplace, template-marketplace → marketplace), nhưng gộp slice là cách sửa đắt nhất. Nên tách phần dùng chung xuống `entities/card-template` trước, phù hợp với ràng buộc ngân sách hiện tại.
7. **`entities/user` chứa "auth state"**: các hiệu ứng auth thuộc `features/auth` hoặc `app`. Entity chỉ nên giữ type và UI hiển thị.
8. **Giao Database Architect review "DTO frontend khớp schema MySQL"** là sai đối tượng: DTO phải khớp contract của API, không phải cột ORM.
9. **"Zero Dead Shim, xóa ngay" dựa trên grep tên file**: dễ xóa nhầm file đang được lazy/dynamic import, router, test hoặc generator dùng. Ví dụ ở bảng 3.1 cho thấy chính danh sách shim của Gemini đã có file còn caller.

---

## 4. Review bản triển khai của Codex (working tree, 2026-10-20 ~22:00)

**Điểm tốt**: allowlist từng skill, mirror `skills/` sang `.claude/skills/` và `.agents/skills/` kèm kiểm tra target an toàn, `nihongo-engineer` chỉ còn là router mỏng. Skill FE đã có chiều phụ thuộc tầng, quy tắc barrel không hợp thức hóa import chéo, alias Shadcn, ratchet baseline và kiểm tra đầy đủ caller trước khi xóa shim. Skill orchestrator và codex-cli đã trung lập với host, dùng quyền tối thiểu và không ký thay agent khác. Sau khi Codex chạy sync, catalog của Claude Code đã thấy đủ `codex-cli`, `flama-*`, `mysql`, `playwright` và `nihongo-engineer`.

**Còn thiếu (đề xuất cho Codex hoặc người tích hợp)**:

| # | Vấn đề | Đề xuất |
|---|---|---|
| C1 | `AGENTS.md:120-122` vẫn trỏ tới phantom skill | Xóa, hoặc ghi rõ "host-provided (Antigravity), prerequisite: Stitch/Chrome DevTools MCP". Thêm test R4 |
| C2 | `AGENTS.md` mô tả `.agents/skills/` là mirror "cho Claude Code và Codex" | Thêm Antigravity, vì AGY cũng đọc customization root `.agents/skills/` |
| C3 | `~/.codex/skills/` còn bản `nihongo-engineer` cũ (dạy Jinja), symlink `flama-database-architecture` và `playwright`, **trùng tên** với mirror trong repo | Người dùng (hoặc Codex nếu được cho phép rõ ràng) xóa 3 mục user-level này, sau khi xác minh C4 |
| C4 | Chưa xác minh ở runtime rằng Codex 0.150.1 có quét `.agents/skills/` | Mở Codex trong repo, liệt kê skill, xác nhận thấy `flama-frontend-architecture` từ mirror |
| C5 | Wrapper Playwright không pin version, tự cài qua `npx --yes` | Pin version cụ thể của `@playwright/cli`. Ghi chú rằng `.sh` cần Git Bash trên Windows |
| C6 | CI có `paths-ignore: '**.md'`, nên thay đổi chỉ đụng `SKILL.md` không chạy CI và không chạy `test_claude_skills_sync.py` | Thêm job nhỏ chạy `sync_claude_skills.py --check` cho `skills/**`, hoặc ghi rõ chỉ dựa vào pre-commit hook |
| C7 | Skill FE chưa giới hạn blast radius của "migrate khi chạm file" | Áp quy tắc R1 |
| C8 | Số liệu sai trong đề xuất FSD của Gemini (bảng 3.1) | Cập nhật vào doc gốc trước khi dùng để lập kế hoạch |

---

## 5. Hàng đợi skill còn thiếu (để yêu cầu agent khác xuất)

| Skill | Được nhắc ở | Đã tìm ở | Agent có khả năng sở hữu | Cần xuất gì | Nếu không ai có |
|---|---|---|---|---|---|
| `impeccable` | `AGENTS.md:120` | `skills/`, `.claude/skills/`, `.agents/`, `~/.codex/skills/`, `~/.claude/skills/`, `~/.gemini/**`, `AppData` | Antigravity (repo có `.impeccable/` trong `.gitignore`, nghĩa là từng cài) | `SKILL.md`, references, license, và mô tả nó đọc/ghi `.impeccable/` như thế nào | Xóa dòng này, dùng `$flama-frontend-architecture` |
| `stitch-skills` (`generate-design`, `react-components`, `shadcn-ui`, `manage-design-system`, `extract-design-md`, `code-to-design`) | `AGENTS.md:121` | Như trên. Chỉ có cấu hình MCP `stitch`/`StitchMCP` của AGY | Antigravity | Các `SKILL.md`, cùng điều kiện tiên quyết là Stitch MCP và đăng nhập Google | Đánh dấu "chỉ có trên AGY". Claude và Codex không dùng được nếu chưa cấu hình MCP |
| `chrome-devtools` | `AGENTS.md:122` | Như trên. Chỉ có cấu hình MCP của AGY | Antigravity | `SKILL.md` mỏng: cách khởi động MCP với profile riêng (`--user-data-dir`), những gì được đo | Claude Code dùng browser pane tích hợp hoặc Claude in Chrome. Có thể viết skill repo mỏng sau |
| Built-in của Codex (`imagegen`, `openai-docs`, `review-agent`, `skill-creator`, `skill-installer`) và của AGY (`generative_ui`, `automation`, ...) | Doc của Gemini | `~/.codex/skills/.system`, builtin AGY | Host | **Không xuất**: đây là năng lực gắn với từng host, không mang sang host khác được | — |

**Gợi ý cách yêu cầu Antigravity**: "Xuất `impeccable`, các skill Stitch và `chrome-devtools` nếu bạn có `SKILL.md` thật. Gửi kèm license, references và điều kiện MCP. Nếu chỉ có MCP server mà không có skill, hãy báo lại để xóa tham chiếu khỏi `AGENTS.md`."

---

## 6. Đóng góp của Claude Code

### 6.1 Skill mới `skills/flama-local-dev/`

Kiến thức vận hành local trước đây chỉ nằm trong memory riêng của Claude, các agent khác không có. Tất cả các điểm dưới đây đã được kiểm chứng lại ngày 2026-10-20:

- Python trong `.venv` (`python` trên PATH là stub của Store), service `MySQL80`, và lệnh `flask db upgrade` trước khi restart server dùng chung.
- Bảy cờ `STUDY_*` trong `.env` rò vào unittest (do `load_dotenv()` không override) làm khoảng 12 test study fail ở local. Đã xác minh: trong PowerShell `$env:X=''` **xóa** biến, nên `.env` lại ghi đè vào; phải chạy từ Bash với `env X= ...`.
- Allowlist cho `/migrations/*` và `skills/*`: file mới bị bỏ khỏi commit mà không báo gì, nên phải kiểm tra bằng `git check-ignore -v`.
- CI bỏ qua thay đổi chỉ gồm Markdown (`**.md`).
- `.claude/launch.json` (4789/5173/5184), cookie theo host (dùng `localhost`, không dùng `127.0.0.1`), worktree hotfix với junction `node_modules` (phải `rmdir` junction trước khi xóa worktree), và cách tạo tài khoản test dùng một lần.
- Làm việc trong checkout dùng chung: sự cố Codex reset file ngày 2026-10-19, nguyên tắc ghi file mới trước rồi mới chuyển import, và không sửa cùng lúc file mà agent khác đang viết.

Chưa đưa vào: runbook vận hành production (SSH, backup, principal SELECT-only). Phần này nhạy cảm, cần người dùng quyết có đưa vào repo không (nếu có thì không ghi host hay secret).

**Để kích hoạt** (chờ Codex xong `.gitignore`): thêm `!skills/flama-local-dev/`, chạy `python scripts/sync_claude_skills.py`, rồi chạy `--check`. Thêm một dòng `$flama-local-dev` vào mục Agent Files của `AGENTS.md`.

### 6.2 Quy tắc bổ sung đề xuất

- **R1. Giới hạn blast radius của "migrate khi chạm file"**: nếu việc di chuyển một module làm thay đổi import ở hơn khoảng 10 file, hoặc ở hơn một slice khác, thì không làm theo kiểu "khi chạm file". Tách thành PR riêng chạy codemod, báo trước, làm lúc không có agent nào đang sửa frontend, và cập nhật alias trong `components.json` cùng PR.
- **R2. Guard ranh giới là test Vitest có baseline**: đặt baseline JSON đếm import theo cặp (slice nguồn → slice đích), fail khi xuất hiện cặp mới hoặc số đếm tăng, và baseline chỉ được giảm. Chạy trong `npm test` để mọi agent đều gặp. `npm run check` hiện chỉ gồm lint và build.
- **R3. Feature không import widget**: khi feature cần UI của feature khác, để page ráp nối và truyền vào qua slot hoặc children. Chỉ hạ xuống `entities/` hoặc `shared/` khi phần đó thật sự không mang workflow.
- **R4. Không có phantom skill**: mỗi `$name` trong `AGENTS.md` phải tồn tại ở `skills/<name>/SKILL.md`, hoặc nằm trong danh sách "host-provided" ghi rõ host và điều kiện tiên quyết. Thêm test nhỏ parse `AGENTS.md` để kiểm tra.
- **R5. Chữ ký review**: mỗi agent chỉ ký phần của mình. Doc chỉ được chuyển `APPROVED` khi đủ chữ ký thật.

---

## 7. Ký duyệt của Claude Code

| Hạng mục | Quyết định |
|---|---|
| Hợp nhất skill về `skills/` + mirror `.claude/skills/`, `.agents/skills/` | **Đồng ý** (theo hướng của Codex, không theo diff `/skills/` của Gemini) |
| Đưa `mysql`, `playwright` vào `skills/` | **Đồng ý**. `playwright` cần pin version (C5) |
| Khai tử `nihongo-engineer` cũ | **Đồng ý**. Phải xóa luôn bản user-level (C3) |
| Kiến trúc FSD đích (`shared`, `entities`, page ra khỏi feature) | **Đồng ý về hướng**. Không đồng ý đặt `ContextHelpButton` vào `widgets` và không đồng ý guard `exit(1)` khi chưa có baseline |
| Lộ trình 4 phase | **Đồng ý có điều kiện**: Phase 2 chạy như một PR codemod riêng (R1). Phase 4 tách entity trước, chưa gộp slice |
| Ký thay agent khác | Không. Mục này chỉ thể hiện ý kiến của Claude Code |
