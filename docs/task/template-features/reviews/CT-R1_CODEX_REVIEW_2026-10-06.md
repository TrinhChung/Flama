# CT-R1 — Review code Gemini: GT-01..GT-09

- Ngày: 2026-10-06 (Asia/Tokyo). Reviewer: Codex, tiếp nhận vai trò review của Claude theo yêu cầu người dùng.
- Nhánh: `refactor/frontend-fsd-renderer-boundary`. HEAD: `965b565c73f61eb8c0742e030eee434a80cac5cb`.
- Commit được review: `9f9309d` (GT-01..04), `869a433` (GT-05..06), `6d997a9` (GT-07), `8c5ef24` (GT-08..09), đối chiếu code tại HEAD.
- Kết luận: **Needs revision** cho GT-01 và GT-06; chưa nghiệm thu lại gate M1. Những test đang có đều qua nhưng hai ca đối kháng dưới đây tái hiện lỗi.

## 1. [P1] GT-06: đổi tên template làm mất bản nháp HTML/CSS

- **Observed:** Người dùng sửa Front HTML nhưng chưa lưu, bấm **Đổi tên**, rồi **Lưu tên**. API rename thành công; textarea bị trả về nội dung đã lưu trước đó. Việc đổi tên không gửi bản nháp lên server nên nội dung vừa soạn bị mất.
- **Evidence:** `frontend/src/features/note-types/components/TemplateManagementBar.tsx:51` gọi `onRenamed()` sau rename. `frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx:101` invalidate detail query; `:119` đồng bộ lại cả Front HTML, Back HTML và CSS với dependency `selectedTemplate`. Rename làm object template thay đổi dù ID và nội dung server vẫn giữ nguyên. Prop `onRenamed={invalidateTemplates}` là phần được thêm trong GT-06.
- **Impact:** Thao tác metadata thông thường xóa nội dung người dùng đang soạn, không có cảnh báo hay cách phục hồi bản nháp trong trang.
- **Reproduction:** Test cấp trang dùng component thật, React Query thật và mock API; xác nhận bản nháp hiện trong textarea trước rename, PATCH chỉ gửi `{ name: 'Renamed' }`, detail được fetch lại, rồi kiểm tra bản nháp sau rename. Test FAIL ở assertion cuối:

```text
Expected: "<b>UNSAVED DRAFT</b>"
Received: "{{Kanji}}"
```

- **Cần sửa:** Giữ draft khi chỉ metadata của cùng template thay đổi. Việc đồng bộ sau chọn template khác, Save hoặc Reset vẫn phải hoạt động. Bổ sung test cấp trang cho Front HTML, Back HTML và CSS; test component riêng và snapshot DOM hiện có không phủ chuỗi thao tác này.
- **Unknowns:** Chưa kiểm tra trình duyệt thật; lỗi đã tái hiện trong jsdom bằng luồng mutation/refetch thực của trang.

Reproducer: [rename-draft.test.tsx](fixtures/rename-draft.test.tsx). File nằm ngoài frontend để không thêm một test đỏ vào bộ test sản phẩm. Chạy từ repo root:

```powershell
New-Item -ItemType Directory -Force -Path frontend/.review-template-code | Out-Null
Copy-Item -LiteralPath docs/task/template-features/reviews/fixtures/rename-draft.test.tsx -Destination frontend/.review-template-code/rename-draft.test.tsx
npm --prefix frontend run test -- .review-template-code/rename-draft.test.tsx
Remove-Item -LiteralPath frontend/.review-template-code/rename-draft.test.tsx
Remove-Item -LiteralPath frontend/.review-template-code
```

## 2. [P2] GT-01: tên field được nhận nhưng default template lỗi hoặc render rỗng

- **Observed:** `POST /api/note-types` nhận field `#Kanji` hoặc `!Word` và trả 201. Helper mới ghép tên field trực tiếp vào `{{...}}`. Mustache hiểu `#` là mở section, `!` là comment; chúng không còn là tham chiếu field.
- **Evidence:** `app/services/flashcards_share_service.py:174` và `:176` ghép raw field name vào token. `create_note_type` và `create_template` dùng kết quả làm nội dung mặc định. Probe chạy qua API create và preview thật trong SQLite:

| Field | HTTP create | Front mặc định | HTTP preview | Kết quả |
|---|---|---|---|---|
| `#Kanji` | 201 | `{{#Kanji}}` | 400 | `TEMPLATE_COMPILE_ERROR`: tag `Kanji` chưa đóng |
| `!Word` | 201 | `{{!Word}}` | 200 | `front_html == ''` dù sample data có giá trị |
| `A.B` (control) | 201 | `{{A.B}}` | 200 | `front_html == 'A.B'` |

- **Impact:** Luồng tạo tự động ghi một template không sử dụng được, hoặc hiện thẻ trống, dù người dùng không tự viết mã template.
- **Cần sửa:** Chốt cách xử lý tên field mang cú pháp Mustache trước khi ghép token. Field được chấp nhận phải sinh nội dung render được; nếu hạn chế tên thì báo lỗi rõ trước khi commit. Kiểm tra cả create NoteType và create thêm Template, giữ nguyên các case tên Unicode/dấu cách/dấu chấm và payload template explicit đã có. Không tự đổi sanitizer hoặc mở rộng whitelist của Gemini.
- **Unknowns:** Chưa xác minh có field mang tên này trong DB thật; API hiện tại cho phép và probe tái hiện bằng dữ liệu hợp lệ.

Reproducer: [default-field-names.py](fixtures/default-field-names.py). Chạy:

```powershell
& ./.venv/Scripts/python.exe docs/task/template-features/reviews/fixtures/default-field-names.py
```

Probe chỉ in hành vi; exit 0 nghĩa là probe chạy xong, không phải hai case lỗi đã được sửa.

## 3. Phần đã đối chiếu

- GT-02/03: aggregation đếm distinct Note, dùng scope query hiện hành, tách source/local theo clone scope; counts chỉ thêm khi bật `include_counts`. Test quyền truy cập, deck con, overlay, zero count và query count hiện có qua.
- GT-04: API methods, escaping ID, response types và query keys phù hợp Contract B/C tại thời điểm review.
- GT-05: đọc diff extraction và chạy test editor/snapshot. Chưa có browser QA để kết luận đầy đủ Zero Visual Regression.
- GT-07: nối menu/modal, grouping, loading/error/empty, labels và hành động owned/installed phù hợp spec. Link sửa dùng route alias tồn tại trong `App.tsx`.
- GT-08: parser giữ khoảng trắng/sigil, đổi đồng thời, media suffix precedence, delimiter error và golden content hash khớp spec; không phát hiện lỗi logic cụ thể trong phạm vi đã kiểm tra. Chưa chạy round-trip trên template trong DB thật của bước backfill.
- GT-09: LCS, tie-breaking, fallback lớn, CRLF và hiển thị HTML dưới dạng text khớp spec. Component chưa được sử dụng trong UI lịch sử phiên bản vì GT-10 chưa triển khai.

Hai lỗi đều liên quan chỉ dẫn đã có trong spec GT-01/GT-06. Cần sửa cả tiêu chí giao task; đây không phải bằng chứng Gemini tự ý làm khác hợp đồng.

## 4. Kiểm thử reviewer tự chạy

Môi trường: `.venv` Python 3.12.6, dependencies frontend sẵn có. Chạy trên working tree hiện tại; các thay đổi chưa commit ở MCP/stats/kế hoạch đã có trước lượt review và được giữ nguyên.

| Lệnh | Kết quả |
|---|---|
| `python scripts/run_tests.py --module flashcards --backend-only` (bằng Python `.venv`) | PASS, 24 file, 318 test |
| `python scripts/run_tests.py --file tests/test_template_default_content.py tests/test_template_note_count.py tests/test_composition_note_counts.py tests/test_adversarial_template_features.py tests/test_template_tokens.py --backend-only` | PASS, 5 file, 61 test |
| `python scripts/run_tests.py --file tests/test_study_composition_service.py tests/test_study_session_install_usage.py tests/test_api_v1_route_map.py --backend-only` | PASS, 3 file, 13 test |
| `npm --prefix frontend run test -- src/entities/card-template src/features/note-types src/features/dashboard` | PASS, 15 file, 165 test |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run lint` | PASS, có warning; không ghi lint sạch tuyệt đối |
| `npm --prefix frontend run build:ci` | PASS, có warning chunk > 500 kB |
| `git diff --check` | PASS sau cập nhật tracker và tài liệu review |
| Reproducer rename cấp trang | FAIL như mục 1, xác nhận lỗi |
| Probe create/preview field names | Xác nhận hai lỗi mục 2 |

Không chạy full suite, không truy cập DB thật, không thay đổi application code trong lượt review. Browser smoke desktop/mobile/dark mode và MySQL QA chưa chạy; chưa đủ bằng chứng để đánh dấu integration gate Accepted.

## 5. Trạng thái bàn giao

- Tracker đổi GT-01 và GT-06 thành `Needs revision`; các task khác giữ trạng thái hiện có.
- GT-16/GT-17: tại lúc review chỉ có candidate `.txt`, chưa có Markdown report theo spec. Chưa review hay nghiệm thu hai task inventory này.
- Kế hoạch đang được sửa ở working tree: phần đầu nói v2/template độc lập nhưng phần task phía sau còn model và migration của v1. Cần đồng bộ kế hoạch/spec trước khi mở GT-10 trở đi; reviewer giữ nguyên phần sửa đang có của người dùng.
- Khi nhận bản sửa, chạy lại reproducer, các test gần nhất và gate liên quan; chỉ đóng hai finding khi kiểm chứng được hành vi đã sửa.
