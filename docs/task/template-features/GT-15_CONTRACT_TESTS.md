# GT-15 — Bổ sung test hợp đồng cho Contract A, D, E (3 lượt: GT-15A, GT-15D, GT-15E)

- Owner: Gemini. Reviewer: Codex (tiếp nhận Claude). Milestone: M2/M3/M4.
- Trạng thái: **GT-15A Completed / verified**. Coverage D/E v2 đã được Codex bổ sung; không giao backend test v1 cho Gemini.
- Loại: **chỉ viết test** backend theo bảng trường hợp. Không sửa source.

## 0. Contract và fixture đã xác nhận (2026-10-07)

- Backend `app/services/template_version_service.py`, blueprint `app/api/v1/flashcards/card_templates.py`, [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md).
- A2 canonical: `/api/card-templates/<tid>/versions`; alias NoteType giữ tương thích. Schema `template-versions.v2`, không có definition_id. Detail có `input_schema`, list/restore current_version_id được mô tả trong ADR.
- Harness: copy setup/teardown và cách login từ `TemplateVersionsTests` trong `tests/test_template_versions.py`; **không subclass hoặc import TestCase đó**, tránh chạy lại test của Codex. SQLite in-memory, create_all/drop_all, REST tạo NoteType Kanji/Meaning, owner/other user và deck.
- Đã phủ A1–A6, A8–A11 bằng test Codex, không viết bản sao. A10 đã chốt: content restore giữ input_schema trả **200** theo #138; restore đổi input_schema của NoteType đã released trả **409 SHARED_SCHEMA_VERSIONING_REQUIRED**. Không áp quy tắc v1 chặn mọi restore.
- A7 và A12–A17 đã có trong `tests/test_template_versions_contract.py`. Giữ bảng dưới làm bằng chứng hợp đồng, không giao lại task Completed.

## 1. Quy tắc riêng

- Chỉ tạo file test mới ở §2. Không sửa source, không sửa test có sẵn.
- Nếu một case **fail** vì hành vi thật khác hợp đồng: giữ nguyên test, ghi rõ trong báo cáo mục "Sai lệch" (đây là phát hiện bug cho Claude), **không** sửa source và **không** đổi kỳ vọng.
- Mỗi test kiểm tra cả mã HTTP, `error` code và trạng thái DB liên quan (đếm hàng trước/sau).

## 2. Lượt GT-15A — Contract A (phiên bản template của chủ sở hữu)

File duy nhất được tạo: `tests/test_template_versions_contract.py`. Harness đã chốt ở §0. Các dòng A1–A11 là reference, chỉ A7 cần bổ sung; chạy case A12–A17 để mở rộng coverage.

| # | Tình huống | Kỳ vọng |
|---|---|---|
| A1 | Template mới tạo qua REST | `GET .../versions` có 1 item, `is_current = true`, `origin` thuộc `{'create','backfill'}` |
| A2 | `PATCH` đổi `front_html` hai lần | 3 version; `version_no` 3,2,1 theo thứ tự giảm; chỉ v3 `is_current` |
| A3 | `PATCH` với nội dung y hệt hiện tại | không tạo version mới |
| A4 | `PATCH` có `change_note: "sửa màu"` | version mới có `change_note == "sửa màu"` |
| A5 | `GET .../versions/<v1>` | đủ `front_html/back_html/shared_css` của lúc tạo |
| A6 | `POST .../versions/<v1>/restore` | 200; tạo version mới `origin == 'restore'`; nội dung template = v1; số version tăng 1; không version nào bị xóa |
| A7 | restore version không thuộc template này | 404 `TEMPLATE_VERSION_NOT_FOUND` |
| A8 | user khác gọi `GET .../versions` | 404 (không lộ tồn tại) |
| A9 | `content_hash` | bằng `template_content_hash(front, back, css)` của GT-08 |
| A10 | NoteType có release chia sẻ (dựng theo fixture Claude chỉ định) | restore trả 409 `SHARED_SCHEMA_VERSIONING_REQUIRED` nếu restore bị coi là thay đổi cấu trúc; nếu CT-03 coi restore là hotfix nội dung thì 200 — Claude ghi kỳ vọng đúng ở §0 |
| A11 | Card ID của template trước/sau restore | không đổi; số Card không đổi |

### Case bổ sung giao Gemini

| # | Tình huống | Kỳ vọng |
|---|---|---|
| A7 | Tạo hai template cùng owner, lấy version của B rồi GET/restore qua URL A | 404 `TEMPLATE_VERSION_NOT_FOUND`; nguồn/head/count của cả hai giữ nguyên |
| A12 | Logout rồi gọi 3 canonical endpoint | 401 `AUTHENTICATION_REQUIRED`, không thêm version |
| A13 | PATCH CSS có note 1000 ký tự; note 1001 ký tự hoặc object | hợp lệ 200 và note đúng; sai 400 `VALIDATION_ERROR`, field `change_note`, không đổi nguồn/head/count |
| A14 | PATCH đổi CSS rồi POST reset template riêng | reset 200, version cuối origin `reset`, created_by đúng owner, nguồn đúng LEGACY_* trong renderer; Card ID/count không đổi |
| A15 | Body restore JSON hỏng hoặc array/null; body không có dữ liệu | body hỏng/array/null 400 `VALIDATION_ERROR`, không đổi DB; body trống hợp lệ và append restore |
| A16 | Tạo raw SQL template chưa có history, invoke CLI với/không --apply | dry run giữ pointer null và count 0; --apply tạo 1 backfill, nguồn/updated_at giữ nguyên; --apply lần hai không thêm |
| A17 | GET canonical và alias NoteType | schema v2, cùng head/ID/version, Cache-Control `private, no-store`; alias sai NoteType trả 404 `TEMPLATE_NOT_FOUND` |

A14 cần tạo Note/Card bằng REST giống test restore của Codex; không chỉ so count bằng 0. A16 dùng app.test_cli_runner và raw Core insert như fixture unversioned của Codex; không chạy CLI vào DB thật.

## 3. D/E v2 coverage completed by Codex

The old per-install fork, token rewrite, sync-definition and required-input blocking cases are superseded by U1/U2/U6 and the implemented contracts. Do not create the v1 test files or adjust source to satisfy them.

| Area | Existing focused suites and assertions |
|---|---|
| Owner/auth/history/restore/rollback | `test_template_versions.py`, `test_template_versions_contract.py`, `test_template_versions_migration.py` |
| Library/group/usage/preview/ownership | `test_template_library.py`, `test_template_library_fe_contract.py`: standalone and ACTIVE shared use, distinct NoteTypes, note counts scoped to NoteType, draft preview without writes, foreign data hidden |
| Attachment/retirement/binding | `test_template_binding_service.py`, `test_template_attachment_migration.py`: stable FieldDef IDs, strict type/foreign field validation, empty inputs advisory, retained cards/progress |
| Receipt/update/publish restrictions | `test_template_release_service.py`: canonical user/source copy, paid entitlement, immutable snapshot, stale/idempotency fences, update conflict/reset, auto defaults, received-source republish prohibition, archived edits |
| Deck release presentation parity | `test_template_deck_release.py`: old/new pins, template/binding-only working state, no raw code in deck atoms, independent-session atomic publish/rollback, legacy fallback and rebase preservation |
| Preset/effective overlay/session freeze | `test_study_template_presets.py`, `test_study_template_application_sessions.py`, `test_effective_template_service.py`: clone schema, transient override validation, opt-in preparation parity and frozen artifacts |
| Client runtime compatibility | content-patch/restore/quick-edit focused tests under `frontend/src/features/study/` |
| Schema distribution | `test_template_distribution_migration.py`, disposable MySQL rehearsal tools |

Coverage here describes the actual v2 invariants, not a claim that obsolete v1 cases ran. Remaining Gemini work is FE behavior tests in GT-10B/11/12/13/18. Additional backend bugs found by those tests return to Codex for repair.

## 4. Verification

```powershell
& .\.venv\Scripts\python.exe scripts/run_tests.py --module templates --backend-only
& .\.venv\Scripts\python.exe scripts/run_tests.py --module templates --frontend-only
git diff --check
```

There is no pending GT-15D/E Gemini backend prompt. See [backend handoff](reviews/CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md) for executed commands and limits.
