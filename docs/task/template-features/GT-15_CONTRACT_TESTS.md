# GT-15 — Bổ sung test hợp đồng cho Contract A, D, E (3 lượt: GT-15A, GT-15D, GT-15E)

- Owner: Gemini. Reviewer: Claude. Milestone: M2/M3/M4.
- Trạng thái: **Blocked**. GT-15A mở sau CT-03; GT-15D sau CT-05; GT-15E sau CT-06.
- Loại: **chỉ viết test** backend theo bảng trường hợp. Không sửa source.

## 0. Việc Claude làm trước mỗi lượt

- [ ] Ghi tên file test Claude đã viết trong CT-03/05/06 và helper fixture có sẵn (tên lớp, hàm `_make_*`, cách đăng nhập) vào §2 của lượt tương ứng.
- [ ] Đánh dấu những dòng trong bảng mà Claude đã phủ (Gemini bỏ qua dòng đó).
- [ ] Đổi trạng thái README của lượt thành `Ready`.

## 1. Quy tắc riêng

- Chỉ tạo file test mới ở §2. Không sửa source, không sửa test có sẵn.
- Nếu một case **fail** vì hành vi thật khác hợp đồng: giữ nguyên test, ghi rõ trong báo cáo mục "Sai lệch" (đây là phát hiện bug cho Claude), **không** sửa source và **không** đổi kỳ vọng.
- Mỗi test kiểm tra cả mã HTTP, `error` code và trạng thái DB liên quan (đếm hàng trước/sau).

## 2. Lượt GT-15A — Contract A (phiên bản template của chủ sở hữu)

File: `tests/test_template_versions_contract.py`. Harness: theo chỉ định của Claude ở §0 (mặc định sao chép `FlashcardApiIntegrationTests`).

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
& .\.venv\Scripts\python.exe -m unittest tests.<file_lượt> -v
& .\.venv\Scripts\python.exe scripts/run_tests.py --module flashcards,marketplace --backend-only
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
