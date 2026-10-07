# Template features: task Gemini và tracker

Kế hoạch tổng: [TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md](../../plans/proposals/TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md). Contract A2 v2 đã chạy trong [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md); các contract library/market copy/attachment còn phác thảo. Spec GT-10/15A đã được đối chiếu với backend thật.

## 1. Tracker

| ID | Tiêu đề | Owner | Trạng thái | Phụ thuộc | Spec |
|---|---|---|---|---|---|
| CT-00 | U1–U8 và baseline phần phiên bản | Codex | Completed | người dùng đã chốt | kế hoạch §7 |
| CT-01 | ADR-T1 + A2; ADR attachment/release tiếp sau | Codex | A2 frozen | CT-00 | [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md) |
| GT-01 | Default template theo field thật | Gemini / Codex fix | Accepted (code) | CT-00 | [GT-01](GT-01_DEFAULT_TEMPLATE_CONTENT.md) |
| GT-02 | note_count template | Gemini | Completed / reviewed | CT-00 | [GT-02](GT-02_TEMPLATE_NOTE_COUNT.md) |
| GT-03 | include_counts compositions | Gemini | Completed / reviewed | CT-00 | [GT-03](GT-03_COMPOSITION_NOTE_COUNTS.md) |
| GT-04 | Entity card-template | Gemini | Completed / reviewed | CT-00 | [GT-04](GT-04_CARD_TEMPLATE_ENTITY.md) |
| GT-05 | Tách TemplateCodeEditor | Gemini | Completed / reviewed | GT-04 | [GT-05](GT-05_EXTRACT_TEMPLATE_CODE_EDITOR.md) |
| GT-06 | Quản lý template, giữ draft khi rename | Gemini / Codex fix | Accepted (code) | GT-02/04/05 | [GT-06](GT-06_TEMPLATE_MANAGEMENT_UI.md) |
| GT-07 | Dialog Kiểu thẻ dashboard | Gemini | Completed / reviewed | GT-03/04 | [GT-07](GT-07_DECK_CARD_TYPES_DIALOG.md) |
| GT-08 | Mustache tokens/hash Python | Gemini | Completed / reviewed | CT-00 | [GT-08](GT-08_TEMPLATE_TOKENS_PURE.md) |
| GT-09 | lineDiff/TemplateDiffView | Gemini | Completed / reviewed | GT-05 | [GT-09](GT-09_LINE_DIFF_VIEW.md) |
| CT-02 | Schema expand + migration 53 + backfill MySQL | Codex | Accepted (code) | CT-01, GT-08 | [báo cáo](reviews/CT-02_CT-03_CODEX_IMPLEMENTATION_2026-10-07.md) |
| CT-03 | Transactional version service + A2 + CLI | Codex | Accepted (code) | CT-02 | [báo cáo](reviews/CT-02_CT-03_CODEX_IMPLEMENTATION_2026-10-07.md) |
| GT-15A | Test A2 bổ sung A7/A12–A17 | Gemini | Completed / verified | CT-03 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-10A | Entity API/types/query keys A2 (5 file) | Gemini | Completed / verified | CT-03 | [GT-10](GT-10_VERSION_HISTORY_UI.md) |
| GT-10B | Sheet lịch sử và nối page (6 file) | Gemini | **Ready** | GT-10A, GT-06, GT-09 | [GT-10](GT-10_VERSION_HISTORY_UI.md) |
| CT-R2 | Review UI/contract + browser gate M2 | Codex | Planned | GT-10B, GT-15A | kế hoạch §7 |
| CT-04 | Resolver render tương thích | Codex | Planned | CT-01 | kế hoạch §7 |
| CT-06 | Attachment/binding theo ID + template độc lập + library | Codex | Planned | CT-04 | kế hoạch §7 |
| CT-07 | Release core + #137 theo U7 | Codex | Planned (đã được yêu cầu) | gate parity deck | kế hoạch §7 |
| CT-05 | Market copy cấp người dùng/source | Codex | Blocked | CT-06, CT-07 | kế hoạch §7 |
| GT-15D | Test market copy v2 | Gemini | Blocked; spec v1 chưa dùng | CT-05 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-11 | Editor bản nhận | Gemini | Blocked; cần spec v2 | CT-05 | [GT-11](GT-11_INSTALL_TEMPLATE_EDITOR.md) |
| GT-15E | Test library/attachment v2 | Gemini | Blocked; spec v1 chưa dùng | CT-06 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-12 | Library UI | Gemini | Blocked; cần spec v2 | CT-06 | [GT-12](GT-12_TEMPLATE_LIBRARY_PAGES.md) |
| GT-13 | Wizard attachment/bindings | Gemini | Blocked; cần spec v2 | GT-12 | [GT-13](GT-13_APPLY_WIZARD.md) |
| GT-14 | Hướng dẫn tính năng đã nghiệm thu | Gemini | Blocked | milestone tương ứng | [GT-14](GT-14_USER_DOCS.md) |
| GT-16/17 | Inventory template/release | Gemini | Candidate reports, chưa Accepted | review quote/source | [GT-16](GT-16_TEMPLATE_USAGE_INVENTORY.md), [GT-17](GT-17_RELEASE_CODE_INVENTORY.md) |

Codex tiếp nhận cả implementation và review của Claude theo yêu cầu người dùng ngày 2026-10-07. [Review CT-R1](reviews/CT-R1_CODEX_REVIEW_2026-10-06.md) được giữ làm bằng chứng lỗi; hai blocker đã sửa bằng code/test. Accepted (code) không đồng nghĩa đã deploy hay đã chạy browser gate toàn M1/M2.

Gemini bắt đầu **GT-10A** hoặc **GT-15A**; hai task không cùng sửa file. Prompt đầy đủ: [GT-10A](GT-10A.prompt.txt), [GT-15A](GT-15A.prompt.txt). Sau review GT-10A mới giao GT-10B. Nền CT-02/03 hiện là diff trong workspace, chưa commit; không tạo worktree từ HEAD rồi mặc định nền đã có. Chạy tuần tự theo whitelist trên workspace này hoặc chuyển đúng diff nền đã review sang checkout riêng.


## 2. Quy tắc chung cho Gemini (dán vào đầu mọi prompt)

Mọi spec đã nhúng khối dưới đây trong phần "Prompt cho Gemini". Không rút gọn khi giao.

```text
QUY TẮC BẮT BUỘC (Flama, template features)
1. Repo: D:\Project\nihongo (workspace/worktree Codex chỉ định). Đọc AGENTS.md trước.
2. Chỉ sửa/tạo đúng các file trong mục "File được sửa". Mọi file khác là CẤM sửa,
   kể cả để "dọn dẹp", đổi format, sửa import hoặc sửa test khác.
3. KHÔNG bịa: nếu một hàm, file, prop, field JSON, route, fixture mà spec nhắc tới
   không tồn tại hoặc khác chữ ký ghi trong spec -> DỪNG phần phụ thuộc, ghi vào
   báo cáo mục "Sai lệch so với spec". Không tự tạo thay thế.
4. Không thêm dependency (pip/npm). Không đổi package.json, requirements.txt,
   lockfile, cấu hình build/lint/test, CI, scripts/run_tests.py.
5. Không chạm models/, migrations/, app/__init__.py, renderer
   (app/services/flashcard_renderer.py, frontend/src/entities/flashcard/**),
   study runtime (frontend/src/features/study/hooks|session|scheduler/**),
   trừ khi spec liệt kê rõ.
6. Giữ nguyên 100% class Tailwind, DOM và chuỗi tiếng Việt của phần UI cũ.
   Chuỗi UI mới dùng đúng nguyên văn trong spec.
7. Không xóa, skip, expectedFailure hoặc nới lỏng test. Không sửa test cũ để qua.
8. Không commit, push, reset, stash, checkout nhánh khác, xóa file ngoài phạm vi.
   Không chạy lệnh ghi vào DB thật, không mở profile Chrome cá nhân.
9. Chạy đúng các lệnh trong mục "Kiểm tra". Dán 20 dòng cuối output THẬT của
   từng lệnh. Không được ghi PASS nếu chưa chạy hoặc lệnh lỗi.
10. Khi xong, trả lời theo "Mẫu báo cáo" rồi dừng. Không tự làm task tiếp theo.
11. Ranh giới import: entities/** không import @/app/* hay @/features/*; feature không
    import feature khác. Ngoại lệ duy nhất: file trong */pages/*.tsx được import
    component public mà spec nêu tên (tầng ghép tạm thời trước khi chuyển sang src/pages).
```

## 3. Mẫu báo cáo Gemini

```text
## Báo cáo <ID>
### File đã sửa/tạo
- <path>: <tóm tắt 1 dòng>
### Lệnh đã chạy
- <lệnh>: PASS/FAIL
  <20 dòng cuối output thật>
### Sai lệch so với spec
- <không có> | <mô tả: spec nói X, code thật là Y, tôi đã dừng/đã làm Z>
### Điểm chưa chắc chắn cần reviewer xem
- ...
### Việc còn lại
- ...
```

## 4. Môi trường và cách chạy

- Repo local: `D:\Project\nihongo`; Python: `.\.venv\Scripts\python.exe`; frontend: `npm --prefix frontend ...`.
- Nhánh người dùng đã chốt là `refactor/frontend-fsd-renderer-boundary` (U8). Khi dùng worktree, Codex đưa đúng diff nền CT-02/03 sang trước; HEAD hiện tại chưa chứa nền. Có thể làm tuần tự trên workspace với whitelist khi tránh xung đột file.
- Lệnh giao (theo `skills/antigravity-cli/references/worker-orchestration.md`):

```powershell
$taskPrompt = Get-Content -Raw docs\task\template-features\GT-01_DEFAULT_TEMPLATE_CONTENT.prompt.txt
agy --print $taskPrompt --model gemini-3.7-flash-high --effort high --mode accept-edits --output-format text
```

  File `.prompt.txt` là phần "Prompt cho Gemini" của spec, Claude tách ra khi đánh dấu task `Ready` (để không gửi nhầm phần ghi chú review dành cho Claude).
- Kiểm tra quota trước task dài theo `$antigravity-manager-api`; xoay tài khoản chỉ theo quy tắc trong worker-orchestration.

## 5. Nhật ký

| Ngày | Sự kiện |
|---|---|
| 2026-10-05 | Claude lập kế hoạch và spec GT-01..GT-15. Chưa giao task, chưa chạy baseline (container lập kế hoạch không có dependency). |
| 2026-10-05 | Gemini / teamwork_preview hoàn thành và kiểm thử toàn diện Milestone M1 (GT-01..GT-04). Pass 100% test suites (30 unit tests, 15 adversarial tests, 52 Vitest, typecheck, lint, 24 flashcard backend suites). |
| 2026-10-06 | Gemini / teamwork_preview hoàn thành GT-05 và GT-06 (tách TemplateCodeEditor không đổi DOM snapshot, TemplateManagementBar, localized errors). Pass 87 frontend tests, typecheck 0 lỗi, lint 0 lỗi, build:ci exit code 0. |
| 2026-10-06 | Gemini / teamwork_preview hoàn thành GT-07 (Dashboard DeckCardTypesDialog và tích hợp menu deck). Victory Auditor phê duyệt VICTORY CONFIRMED. Pass 24/24 dialog tests, 58/58 dashboard tests, typecheck 0 lỗi, lint 0 lỗi, build:ci clean. |
| 2026-10-06 | Gemini / teamwork_preview hoàn thành GT-08 và GT-09 (Python Mustache tokens & hash; TS lineDiff LCS & TemplateDiffView). Victory Auditor phê duyệt VICTORY CONFIRMED. Pass 20 Python tests, golden hash khớp, 81/81 card-template tests, typecheck 0 lỗi, lint 0 lỗi, build:ci clean. |
| 2026-10-06 | Codex tiếp nhận review của Claude: review GT-01..GT-09 tại HEAD `965b565`; 392 test backend và 165 test frontend đang có qua, typecheck/lint/build qua. Reproducer bổ sung xác nhận 2 lỗi; GT-01 và GT-06 → Needs revision. Xem [CT-R1 review](reviews/CT-R1_CODEX_REVIEW_2026-10-06.md). |
| 2026-10-07 | Người dùng giao Codex phần code Claude. Hoàn thành CT-02/03 expand + A2 v2; MySQL 8.0.40 rehearsal/concurrency và cleanup qua, main wsgi + standalone Connect boot qua; sửa GT-01/06. GT-10A và GT-15A Ready, GT-10B sau review entity. Xem [báo cáo](reviews/CT-02_CT-03_CODEX_IMPLEMENTATION_2026-10-07.md). |
| 2026-10-07 | Gemini / teamwork_preview hoàn thành và kiểm thử toàn diện GT-10A (Frontend entity API/types/keys/tests) và GT-15A (Backend contract tests A7, A12–A17). Victory Auditor phê duyệt VICTORY CONFIRMED. Pass 93/93 card-template tests, 45/45 backend modular tests, typecheck 0 lỗi, lint 0 lỗi, build:ci clean. GT-10B chuyển sang Ready. |
