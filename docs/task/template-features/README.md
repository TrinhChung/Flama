# Template features: task Gemini và tracker

Kế hoạch tổng: [TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md](../../plans/proposals/TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md). Hợp đồng API nằm ở §5 của kế hoạch tổng; spec dưới đây chỉ trích phần cần cho từng task.

## 1. Tracker

| ID | Tiêu đề | Owner | Trạng thái | Phụ thuộc | Spec |
|---|---|---|---|---|---|
| CT-00 | Chốt Q1–Q5, chạy baseline | Claude | Planned | người dùng duyệt | kế hoạch §7 |
| CT-01 | ADR definition/version/fork, đóng băng Contract A/D/E | Claude | Planned | CT-00 | kế hoạch §7 |
| GT-01 | Nội dung mặc định template theo field thật | Gemini | Completed | CT-00 | [GT-01](GT-01_DEFAULT_TEMPLATE_CONTENT.md) |
| GT-02 | `note_count` trong danh sách template | Gemini | Completed | CT-00 | [GT-02](GT-02_TEMPLATE_NOTE_COUNT.md) |
| GT-03 | `include_counts` cho compositions | Gemini | Completed | CT-00 | [GT-03](GT-03_COMPOSITION_NOTE_COUNTS.md) |
| GT-04 | Entity `card-template` (frontend) | Gemini | Completed | CT-00 | [GT-04](GT-04_CARD_TEMPLATE_ENTITY.md) |
| GT-05 | Tách `TemplateCodeEditor` (không đổi giao diện) | Gemini | Completed | GT-04 | [GT-05](GT-05_EXTRACT_TEMPLATE_CODE_EDITOR.md) |
| GT-06 | Quản lý template trên trang loại thẻ | Gemini | Completed | GT-02, GT-04, GT-05 | [GT-06](GT-06_TEMPLATE_MANAGEMENT_UI.md) |
| GT-07 | Dialog "Kiểu thẻ" trên dashboard | Gemini | Completed | GT-03, GT-04 | [GT-07](GT-07_DECK_CARD_TYPES_DIALOG.md) |
| GT-08 | Python: token Mustache + content hash | Gemini | Completed | CT-00 | [GT-08](GT-08_TEMPLATE_TOKENS_PURE.md) |
| GT-09 | TS: `lineDiff` + `TemplateDiffView` | Gemini | Completed | GT-05 | [GT-09](GT-09_LINE_DIFF_VIEW.md) |
| CT-02 | Schema + migration 51 + backfill | Claude | Planned | CT-01, GT-08 | kế hoạch §7 |
| CT-03 | Version service + Contract A | Claude | Planned | CT-02 | kế hoạch §7 |
| GT-15A | Test hợp đồng Contract A | Gemini | Blocked | CT-03 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-10 | UI lịch sử phiên bản | Gemini | Blocked | CT-03, GT-06, GT-09 | [GT-10](GT-10_VERSION_HISTORY_UI.md) |
| CT-04 | Seam `resolve_effective_template` | Claude | Planned | CT-01 | kế hoạch §7 |
| CT-05 | Fork của người cài + Contract D | Claude | Blocked | CT-03, CT-04, Q1 | kế hoạch §7 |
| GT-15D | Test hợp đồng Contract D | Gemini | Blocked | CT-05 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-11 | Trang sửa template deck đã cài | Gemini | Blocked | CT-05, GT-05, GT-07, GT-10 | [GT-11](GT-11_INSTALL_TEMPLATE_EDITOR.md) |
| CT-06 | Thư viện mẫu thẻ + Contract E | Claude | Blocked | CT-03, GT-08, Q2, Q3 | kế hoạch §7 |
| GT-15E | Test hợp đồng Contract E | Gemini | Blocked | CT-06 | [GT-15](GT-15_CONTRACT_TESTS.md) |
| GT-12 | Trang thư viện mẫu thẻ | Gemini | Blocked | CT-06, GT-05, GT-10 | [GT-12](GT-12_TEMPLATE_LIBRARY_PAGES.md) |
| GT-13 | Wizard áp dụng + `FieldMappingEditor` | Gemini | Blocked | GT-12 | [GT-13](GT-13_APPLY_WIZARD.md) |
| GT-14 | Tài liệu người dùng | Gemini | Blocked | M3, M4 Accepted | [GT-14](GT-14_USER_DOCS.md) |
| CT-07 | Pin release cho tác giả (#137) | Claude | Chờ Q4 | M3 production | kế hoạch §7 |

Mỗi lần đổi trạng thái, Claude ghi thêm một dòng vào §5 (nhật ký).

## 2. Quy tắc chung cho Gemini (dán vào đầu mọi prompt)

Mọi spec đã nhúng khối dưới đây trong phần "Prompt cho Gemini". Không rút gọn khi giao.

```text
QUY TẮC BẮT BUỘC (Flama, template features)
1. Repo: D:\Project\nihongo (worktree Claude chỉ định). Đọc AGENTS.md trước.
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
### Điểm chưa chắc chắn cần Claude xem
- ...
### Việc còn lại
- ...
```

## 4. Môi trường và cách chạy

- Repo local: `D:\Project\nihongo`; Python: `.\.venv\Scripts\python.exe`; frontend: `npm --prefix frontend ...`.
- Mỗi task Gemini chạy trong worktree riêng do Claude tạo, ví dụ `git worktree add ..\nihongo-gt01 -b feat/template-m1-gt01 <base>`; nhánh cuối cùng do người dùng chốt (Q5).
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
