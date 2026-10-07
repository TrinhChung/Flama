# GT-15 — Bổ sung test hợp đồng cho Contract A, D, E (3 lượt: GT-15A, GT-15D, GT-15E)

- Owner: Gemini. Reviewer: Codex (tiếp nhận Claude). Milestone: M2/M3/M4.
- Trạng thái: **GT-15A Ready (A2 v2)**. GT-15D/GT-15E vẫn Blocked; các bảng D/E phía dưới là v1 lịch sử, chưa dùng làm contract cho v2.
- Loại: **chỉ viết test** backend theo bảng trường hợp. Không sửa source.

## 0. Contract và fixture đã xác nhận (2026-10-07)

- Backend `app/services/template_version_service.py`, blueprint `app/api/v1/flashcards/card_templates.py`, [ADR-T1](../../architecture/template-version-foundation-adr-2026-10-07.md).
- A2 canonical: `/api/card-templates/<tid>/versions`; alias NoteType giữ tương thích. Schema `template-versions.v2`, không có definition_id. Detail có `input_schema`, list/restore current_version_id được mô tả trong ADR.
- Harness: copy setup/teardown và cách login từ `TemplateVersionsTests` trong `tests/test_template_versions.py`; **không subclass hoặc import TestCase đó**, tránh chạy lại test của Codex. SQLite in-memory, create_all/drop_all, REST tạo NoteType Kanji/Meaning, owner/other user và deck.
- Đã phủ A1–A6, A8–A11 bằng test Codex, không viết bản sao. A10 đã chốt: content restore giữ input_schema trả **200** theo #138; restore đổi input_schema của NoteType đã released trả **409 SHARED_SCHEMA_VERSIONING_REQUIRED**. Không áp quy tắc v1 chặn mọi restore.
- A7 dùng version thực của template khác cùng owner còn cần bổ sung. Các case A12–A17 dưới đây là việc Gemini được giao. D/E phải được cập nhật sau market-copy/attachment/release backend, không triển khai dựa trên fork theo install hoặc rewrite token v1.

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

## 3. Lượt GT-15D — Contract D (bản riêng của người cài)

File: `tests/test_install_template_forks_contract.py`. Harness overlay: theo Claude chỉ định (mặc định mẫu `_install_overlay` trong `tests/test_study_session_install_usage.py`).

| # | Tình huống | Kỳ vọng |
|---|---|---|
| D1 | `GET .../templates` khi chưa fork | mọi item `state == 'following'`, `fork_id is None`, `upstream_changed_since_fork is False` |
| D2 | `PUT .../<sid>/fork` lần đầu | 200, `state == 'forked'`; **mọi** hàng `templates`, `notes`, `cards` của tác giả giữ nguyên (so hash trước/sau) |
| D3 | `PUT` lần hai | thêm 1 version, `fork_id` không đổi |
| D4 | người cài khác (user C) cài cùng deck | `GET` của C vẫn `following`, nội dung = bản gốc |
| D5 | tác giả sửa nội dung template (hotfix #138) sau khi B fork | `GET` của B: `upstream_changed_since_fork is True`, nội dung hiệu lực vẫn là fork |
| D6 | `DELETE .../<sid>/fork` | `state == 'following'`; nội dung = bản gốc hiện tại; version của fork vẫn đọc được qua lịch sử nếu Claude chốt như vậy ở §0 |
| D7 | user không sở hữu install gọi bất kỳ route | 404 `INSTALL_NOT_FOUND` |
| D8 | `sid` không thuộc NoteType nguồn của install | 404 `TEMPLATE_NOT_IN_INSTALL` |
| D9 | nội dung Mustache lỗi | 400 `TEMPLATE_COMPILE_ERROR`, không tạo version |
| D10 | mở phiên học trước khi fork, fork, rồi lấy lại snapshot phiên | artifact template của phiên cũ giữ nguyên (`version` cũ); phiên mới: mọi artifact template vẫn có `id` = `template_id` nguồn, `version` khác phiên cũ, `front_source` chứa nội dung fork |
| D11 | Card ID/`study_applications` trước/sau fork | không đổi |

## 4. Lượt GT-15E — Contract E (thư viện)

File: `tests/test_template_library_contract.py`.

| # | Tình huống | Kỳ vọng |
|---|---|---|
| E1 | `POST /api/card-templates` | 201; `input_keys` = token trong front/back theo thứ tự xuất hiện |
| E2 | `GET ?group=standalone` | chỉ định nghĩa `applied_count == 0` |
| E3 | apply đủ binding | 201; template mới thuộc NoteType đích; `front_html` đã đổi token sang tên field; Card được tạo cho mọi note của NoteType |
| E4 | apply thiếu input bắt buộc | 400 `INPUT_BINDING_INCOMPLETE`, `details.missing_keys` đúng; không tạo template/Card |
| E5 | binding trỏ field đã xóa | 400 `INPUT_BINDING_STALE` |
| E6 | binding trỏ field của NoteType khác | 403 `INPUT_BINDING_OUT_OF_SCOPE` |
| E7 | sai kiểu (`image` → field `text`) | 400 `INPUT_BINDING_TYPE_MISMATCH` |
| E8 | NoteType đích của user khác | 404 |
| E9 | sửa nội dung định nghĩa sau khi apply | template đã apply **không** đổi; `applications[*].is_outdated == true` |
| E10 | `sync-definition` | template cập nhật nội dung version mới; Card ID không đổi |
| E11 | đổi tên field được bind (Q3) | template có binding đổi token theo tên mới; template không binding giữ nguyên |
| E12 | `archive` | không còn trong `GET` mặc định; template đã apply vẫn hoạt động |

## 5. Kiểm tra (mỗi lượt)

```powershell
& .\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_template_versions_contract.py tests/test_template_versions.py tests/test_template_versions_migration.py tests/test_template_note_count.py --backend-only
# Với D/E: chỉ chạy khi đã được mở task, thay --file bằng file test của lượt đó.
git diff --check
git status --short
```

## 6. Prompt cho Gemini (thay `<LƯỢT>` bằng A, D hoặc E)

```text
<dán nguyên khối QUY TẮC BẮT BUỘC trong docs/task/template-features/README.md §2>

Task GT-15<LƯỢT>. Đọc docs/task/template-features/GT-15_CONTRACT_TESTS.md §1 và đúng mục của lượt <LƯỢT>
(§2 cho A, §3 cho D, §4 cho E), cùng phần §0 Claude đã điền. Chỉ tạo file test của lượt đó.
Không sửa source hay test có sẵn. Test fail do hành vi khác hợp đồng: giữ nguyên test và báo cáo ở mục
"Sai lệch". Chạy lệnh §5, báo cáo theo README §3. Không commit.
```
