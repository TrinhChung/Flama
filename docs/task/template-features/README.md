# Template features: backend handoff và tracker

Cập nhật **2026-10-08**: Codex đã hoàn tất phần backend CT-04/05/06/07/08 còn thiếu và sửa các lỗi phát hiện khi audit. Gemini tiếp tục phần FE; chưa coi các màn hình mới hoặc browser gate là hoàn thành.

Contract đang chạy: [phiên bản A2](../../architecture/template-version-foundation-adr-2026-10-07.md), [library/attachment](../../architecture/template-library-attachments-contract-2026-10-07.md), [study preset/binding](../../architecture/template-study-bindings-contract-2026-10-07.md), [distribution](GT-11_INSTALL_TEMPLATE_EDITOR.md). Bằng chứng và giới hạn: [backend handoff](reviews/CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md). Kế hoạch giữ U1–U8: [execution plan](../../plans/proposals/TEMPLATE_FEATURES_CLAUDE_GEMINI_EXECUTION_PLAN_2026-10-05.md).

## 1. Tracker

| ID | Owner | Trạng thái hiện tại | Kết quả / công việc tiếp theo |
|---|---|---|---|
| CT-00/01 | Codex | Completed | U1–U8 giữ nguyên; A2 và contract thực tế đã đối chiếu code |
| GT-01..09 | Gemini + Codex review/fix | Completed (code) | Default, counts, editor/draft, dashboard, token/diff; không giao lại |
| CT-02/03 | Codex | Completed | Immutable history, ORM transaction hooks, backfill, A2; migration 53 |
| GT-10A / GT-15A | Gemini | Completed / verified | Entity A2 và test contract đã có; không giao lại |
| CT-04 | Codex | Completed | Effective resolver cho owned/install/local-added, pinned content và binding |
| CT-06 | Codex | Completed | Template độc lập, ACTIVE attachment theo FieldDef ID, library/preview/filter/usage; migration 54 |
| CT-07 | Codex | Completed | `release_core` dùng chung; deck parity; immutable template releases và deck pins; migration 55 |
| CT-05 | Codex | Completed | Một market copy/user/source, entitlement qua deck/NoteType, update/conflict/reset, chặn republish |
| CT-08 | Codex | Completed | Opt-in preparation, personal deck preset, transient validation, session freeze và quick-edit projection |
| GT-15D/E | Codex | Superseded / covered in v2 suites | D/E v1 bỏ; xem [coverage v2](GT-15_CONTRACT_TESTS.md), không giao test backend v1 cho Gemini |
| GT-16/17 | Codex review | Superseded inventory request | Báo cáo ứng viên cũ chưa được Accepted; audit code/test hiện tại trong handoff thay gate này |
| GT-10B | Gemini | Ready | History sheet, restore draft; [prompt](GT-10B.prompt.txt) |
| GT-12A | Gemini | Ready | Entity library/schema/attachment; [prompt](GT-12A.prompt.txt) |
| GT-12B/C/D/E | Gemini | Ready after listed FE dependencies | Library/create, input schema, TemplateDetailPage, route/sidebar; [spec](GT-12_TEMPLATE_LIBRARY_PAGES.md) |
| GT-13A/B/C/D | Gemini | Ready after listed FE dependencies | Shared binding UI, attach wizard, library compose, NoteType application management; [spec](GT-13_APPLY_WIZARD.md) |
| GT-11A/B/C | Gemini | Ready after listed FE dependencies | Distribution API, install entry, author/recipient controls; [spec](GT-11_INSTALL_TEMPLATE_EDITOR.md) |
| GT-18A/B/C/D | Gemini | Ready after listed FE dependencies | Preparation API/UI, remember controls, study integration; [spec](GT-18_STUDY_TEMPLATE_PREPARATION.md) |
| CT-R2 | Codex | Awaiting FE | Review new UI, mobile/dark/browser smoke after Gemini implements it |
| GT-14 | Gemini | Awaiting accepted FE | User guide uses actual UI names; [spec](GT-14_USER_DOCS.md) |

Thứ tự giao an toàn trên một workspace: **GT-12A → GT-10B → GT-12B/C/D/E → GT-13A/B/C/D → GT-11A/B/C → GT-18A/B/C/D**. Mỗi phase có prompt riêng và tối đa 5–6 file. Tuân thủ dependency cụ thể trong spec; không chạy hai phase cùng sửa entity/index/routes/page. Không cần chờ một backend task Planned cũ.

Archive ẩn library mặc định và chặn attachment mới, nhưng attachment đang ACTIVE tiếp tục dùng được. Retire attachment giữ Card/progress. HTML không bị rewrite theo tên field; binding dùng ID. Reset bản nhận áp dụng release đã đăng qua subscription, không xóa market copy hay lịch sử. Browser gate và tài liệu người dùng đợi FE thực tế.

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

- Workspace: `D:\Project\nihongo`; Python: `.\.venv\Scripts\python.exe`; frontend: `npm --prefix frontend ...`.
- Tiếp tục trên `refactor/frontend-fsd-renderer-boundary` (U8). Nền library/distribution/runtime hiện đã có trong lịch sử nhánh. Kiểm tra `git status` và nền thực tế trước khi giao; workspace có thay đổi của các task khác đang chạy.
- Làm từng phase theo whitelist. Nếu dùng worktree, đưa cả commit nền và diff bổ sung đã review sang trước; không checkout một HEAD cũ rồi giả định API đã có.
- Prompt `.prompt.txt` là đầu vào triển khai của đúng một phase. Không giao toàn bộ spec nhiều phase trong một lượt. Không tự khởi chạy worker ngoài phase được giao.
- Khi dùng `agy`, áp dụng `skills/antigravity-cli/references/worker-orchestration.md` và skill Manager hiện có; không lưu key trong repo.

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

| 2026-10-08 | Codex hoàn tất backend handoff CT-04/05/06/07/08, cập nhật contract/spec/prompt GT-10B/11/12/13/18 và modular module templates. FE mới vẫn chờ Gemini. |
