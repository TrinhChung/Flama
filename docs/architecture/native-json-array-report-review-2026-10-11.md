# Review báo cáo Native JSON Array của Gemini

> **Trạng thái sau xử lý:** Local đã sửa 12 source HTML, 25 template DB và 68 note lệch cột. Production đã triển khai riêng qua PR #228, backfill 41.199 note, sửa 68 note và 9 template; đối soát 106 bảng/41.510 note pass, không đưa P11 vào release. Chi tiết backup/receipt/smoke nằm trong [runbook production](../runbooks/NATIVE_ARRAY_CLEANUP_20261011.md). Còn 113 note cần biên tập nội dung/bản dịch. Các finding bên dưới giữ bằng chứng của pha review trước khi sửa; SHA-256 là của báo cáo gốc trước phần đính chính.

> Ngày: 2026-10-11 (Asia/Tokyo) | Chế độ: INVESTIGATE
> Đối tượng: `docs/reports/ARRAY_MIGRATION_AUDIT_REPORT.md`, bản 1.0.0.
> HEAD khi kiểm tra: `ed83cb391fb55d1f52c70cf94cd40765856574b4`, cùng working diff native array chưa commit.
> SHA-256 báo cáo: `aa00bb1492026db90e11eab85c647d59f2bcb7e209df69cad4bacdf0d2da98a8`.

## Kết luận và phạm vi

**Số liệu chính của khảo sát local đúng; kế hoạch thực thi chưa đủ điều kiện nghiệm thu.** Có hướng sửa cột sai, các lỗi luyện gõ/section Mustache chưa được kế hoạch xử lý, đề xuất bỏ script còn ảnh hưởng field chưa chuyển đổi, và rollback không bảo vệ cập nhật mới.

Review đọc MySQL local bằng `SET TRANSACTION READ ONLY` và `START TRANSACTION WITH CONSISTENT SNAPSHOT`; render trên bộ nhớ, thực thi JavaScript template trong jsdom, và chạy các test SQLite/frontend riêng. Không khởi động `wsgi.py`, chạy migration, sửa mã ứng dụng hoặc ghi DB. Chưa kiểm tra production hiện tại, lịch sử binary log hay nguồn gốc các thay đổi của phiên khác.

| Kết quả đối soát local | Giá trị xác nhận |
|---|---:|
| Notes / NoteTypes / Templates | 41.533 / 36 / 35 |
| Slot thuộc FieldDef hiện khai báo array | 108.960 |
| Slot là JSON list, bao gồm list rỗng | 108.956 |
| List rỗng / key thiếu | 139 / 4 |
| Slot là string trong `notes.field_values` của các field array | 0 |
| Lệch Collocation / Synonym / Antonym | 1 / 64 / 100 |
| Note ID lệch ít nhất một cặp | 113 |
| Giá trị chuỗi trong checkpoint, ở các key tương ứng field hiện khai báo array | 70.818 |
| DeckInstall có release pin / tổng installs | 27 / 28 |
| Giá trị ví dụ chứa HTML: `example_jp` / `example_vi` | 79 / 83 |

Giữ list, thứ tự và item lặp là đúng contract. Cách render cả list thành chuỗi dấu phẩy khớp `String(array)` của mustache.js; template phải tự tạo layout. Không nên đổi renderer để tự chèn `<br>` hoặc tách dấu phẩy chỉ nhằm tương thích template cũ.

## Findings

### F1 — [P1] Kế hoạch sửa lệch cột đi ngược dữ liệu thực tế

- **Observed:** Mục 4.3 nói dữ liệu Antonym đang nằm trong Synonym_VI, Word Family trong Antonym và Note_EN trong Antonym_VI. Nhưng giai đoạn 4 yêu cầu `Antonym → Synonym_VI`, `Word Family → Antonym`, `Note_EN → Antonym_VI`, tức tiếp tục chuyển sai chiều.
- **Evidence:** Báo cáo dòng 649–655 và 778–781. Note `00653f96-b964-4a1f-8541-b832c5f976b1` (`calibrate`) có Synonym_VI = `["misalign", "distort"]`, Antonym = bốn mục `calibration/calibrated/calibrator/recalibrate`, Antonym_VI = câu ghi chú tiếng Anh; Word Family = câu ghi chú tiếng Việt, Note_EN rỗng. Mô phỏng đúng ba phép gán của báo cáo đưa word family vào Synonym_VI, ghi câu tiếng Việt vào Antonym và làm Antonym_VI rỗng.
- **Potential concern:** Phát hiện dữ liệu lệch là có thật nhưng chưa chứng minh được một phép hoán chuyển đồng nhất có thể phục hồi toàn bộ dữ liệu. Bản dịch synonym gốc có thể đã thiếu trước migration.
- **Impact:** Chạy patch như mô tả sẽ làm hỏng nội dung thêm; không thể coi đó là làm sạch 66 notes.
- **Unknowns:** Chưa đối soát file import gốc hoặc từng before/after của toàn bộ 66 notes. Review chỉ xác nhận một phản ví dụ đủ bác bỏ patch chung này.

### F2 — [P1] Kế hoạch Typing bỏ sót nguồn đáp án và chấm điểm ở mặt trước

- **Observed:** Giai đoạn 2 chỉ sửa phần hiển thị Meaning và inline separator. Các mặt trước vẫn dùng `{{Answer}}` và parser đọc ranh giới `<br>`, nên list nhiều đáp án trở thành một đáp án ghép bằng dấu phẩy.
- **Evidence:** Báo cáo dòng 763–765; `note-type-templates/typing-answer/front.html:9,32,64` và `typing-reading/front.html:22,47,64,167`. Với template DB và file nguồn, Answer = `["Tokyo", "Đông Kinh"]`: từng đáp án đều bị chấm sai, chuỗi `Tokyo,Đông Kinh` được chấm đúng. Answer = `["nǐ hǎo", "ni hao"]` có kết quả tương tự. Fixture thực thi không có lỗi JavaScript.
- **Potential concern:** Sửa mặt sau không khôi phục cách đọc accepted answers ở mặt trước. Typing-image/meaning/dictation cũng có cùng parser phụ thuộc BR.
- **Impact:** Học viên nhập một đáp án hợp lệ nhưng không vượt qua bài luyện gõ; hint/độ dài cũng theo chuỗi ghép.
- **Unknowns:** Đã thực thi hai họ Typing; ba họ còn lại mới được đối chiếu mã parser, chưa thực thi hết các nhánh tương tác.

### F3 — [P1] Section cũ dùng làm điều kiện trở thành vòng lặp nhân bản block

- **Observed:** Nhiều template dùng `{{#Collocation}}`, `{{#Meaning}}`, `{{#reading}}`, `{{#Answer}}` để bao một block có tên field bên trong. Khi giá trị thành list, section lặp block theo từng item; `{{Field}}` bên trong vẫn đọc cả list. Hướng thay riêng raw div bằng span ở giai đoạn 2 không xử lý section bao ngoài.
- **Evidence:** Báo cáo dòng 756–759; `note-type-templates/advanced-vocabulary-card/back.html:21,30`, `flama-default/back.html:22`, `typing-reading/back.html:8`. Template En4 DB với ba Collocation tạo ba `#coll-raw`, ba `#coll-pairs`, nhưng script chỉ dựng một hàng ở block đầu. Meaning hai item tạo hai block `.meaning-vi`, mỗi block chứa cả list.
- **Potential concern:** Đây là thay đổi ngữ nghĩa từ scalar truthiness sang iteration, tách biệt với lỗi regex không nhận dấu phẩy. Lồng thêm item-loop vào guard cũ có thể nhân số span theo tích số vòng lặp.
- **Impact:** Lặp tiêu đề/nội dung, trùng ID và chỉ render đúng một phần layout; thay parser đơn thuần chưa bảo đảm Zero Visual Regression.
- **Unknowns:** Chưa lập census vị trí guard của toàn bộ 35 template DB; đã chứng minh trên một template DB và xác nhận cùng cấu trúc trong file nguồn.

### F4 — [P1] Bỏ toàn bộ auto-split khi chỉ chuyển hai field làm hỏng các field còn lại

- **Observed:** Giai đoạn 3 chỉ chuyển `example_jp`/`example_vi` rồi yêu cầu bỏ script auto-split. Script này còn xử lý `meaning_jp`, `meaning_vi`, `usage_vi`, `additional_note_vi` vẫn giữ kiểu cũ.
- **Evidence:** Báo cáo dòng 771–776 và script families F5/F6/F12. File `note-type-templates/flama-default/back.html` còn các div auto-split cho giải thích, sử dụng và ghi chú. Local của NoteType User 1 có `$` trong 2.966 giá trị meaning_jp, 2.394 meaning_vi, 2.834 usage_vi và 317 additional_note_vi.
- **Potential concern:** Dependency của script được liệt kê ở phần khảo sát nhưng chưa được giữ trong kế hoạch bỏ script.
- **Impact:** Các field chưa chuyển sẽ hiển thị dấu `$` và mất ranh giới dòng; tổng trên là số giá trị field, không phải số note khác nhau.
- **Unknowns:** Chưa đo ảnh hưởng theo từng template tùy biến hoặc phân biệt `$` dùng làm delimiter với ký hiệu literal trong mỗi giá trị. Vì vậy không được chuyển tiếp toàn bộ field theo một regex chung để lấp khoảng trống này.

### F5 — [P1] Chuyển ví dụ richtext sang array chưa giải quyết contract text thuần

- **Observed:** Báo cáo yêu cầu đổi hai field richtext sang array và dùng `{{{.}}}` để hiển thị. Native array chỉ chấp nhận item text thuần; validator từ chối item chứa HTML. Hai field ví dụ có HTML thật, không thuộc nhóm array sạch đã được thống kê trước đó.
- **Evidence:** Báo cáo dòng 338–345, 771–776; `models/field_types.py:7`, `app/validators/flashcard_input.py:271,415`, `app/validators/field_array_conversion.py:92`. Scan local xác nhận 79 giá trị example_jp và 83 example_vi chứa HTML. `clean_array_fields({"example_jp": ["<b>example</b>"]}, ...)` trả lỗi `must be plain text (HTML is not allowed)`.
- **Potential concern:** Giữ HTML bằng SQL trực tiếp sẽ tạo dữ liệu không hợp lệ khi sửa/lưu qua API; bỏ HTML làm mất định dạng. Triple-brace trong template không mở rộng contract của array.
- **Impact:** Migration có thể bị validator chặn hoặc tạo regression khi học/chỉnh sửa; chưa có cơ sở hứa bảo toàn hiển thị.
- **Unknowns:** Chưa kiểm tra từng fragment HTML hay xác định giá trị nào được chủ sở hữu cho phép hạ xuống text thuần. 162 là số giá trị field, không khẳng định 162 notes riêng biệt.

### F6 — [P1] Rollback vừa không chạy được vừa có thể ghi đè chỉnh sửa mới

- **Observed:** SQL khôi phục template dùng `t.styling`, nhưng cột đúng là `shared_css`. SQL khôi phục notes ghi lại toàn bộ JSON của mọi row từ backup, không kiểm tra giá trị sau migration, phạm vi target hoặc writer đang hoạt động. `READ_ONLY_SAFETY_MODE` được đề cập nhưng không có consumer trong app/scripts/deploy.
- **Evidence:** Báo cáo dòng 713 và 798–822; `models/template.py:39`, cùng `SHOW COLUMNS FROM templates` của local xác nhận không có styling. `scripts/migrations/array_cutover.py:217–268` và runbook hiện có thể hiện kiểm tra hash/row lock, giữ writer dừng và restore được kiểm soát; kế hoạch mới không có các gate này.
- **Potential concern:** Một lệnh rollback bị lỗi có thể để hệ thống giữa các bước phục hồi. Một lệnh rollback chạy được có thể xóa mọi thay đổi người dùng tạo sau snapshot, kể cả field ngoài phạm vi array.
- **Impact:** Quy trình phục hồi không đạt cam kết an toàn dữ liệu hoặc trạng thái đồng bộ schema/content/template.
- **Unknowns:** Chưa thực thi SQL rollback hoặc migration; không có bằng chứng thử lỗi giữa các bước. Snapshot ba bảng không chứng minh khôi phục được toàn bộ history/release state.

### F7 — [P1] Kế hoạch chưa bao phủ release-pinned content và lịch sử template

- **Observed:** Census native array chỉ đọc Notes đang làm việc. Checkpoint còn 70.818 giá trị string tại các key tương ứng field hiện là array; 27/28 installs có release pin. Mẫu DOM spans đề xuất nhận list mới, nhưng với legacy `one\ntwo` chỉ tạo một span có text `onetwo`; với `one; two` cũng chỉ tạo một item. Kế hoạch không xác định cách kiểm tra clone/version pin, ghi dirty atoms, hoặc tạo version cho template updates/restores.
- **Evidence:** Báo cáo mục 1.2, 2.4 và 5.1–5.2; `models/deck_release_note_checkpoint.py`, `app/services/study_artifact_service.py:142`, `app/services/effective_template_service.py:70`, `app/services/template_version_service.py:1,59,89`, `app/services/field_array_conversion_service.py:170–176`. Repo có journal và template-history handling, raw SQL rollback trong báo cáo bypass ORM hooks.
- **Potential concern:** Owner working content, published release content và learner overlays là các nguồn khác nhau. Đổi working Notes/Templates không tự sửa release đã pin; rewrite history để đồng bộ lại vi phạm immutable-release contract. Statement “100%” đúng cho phạm vi Notes local đã scan, không chứng minh toàn bộ effective study content đã native.
- **Impact:** Template mới có thể đọc sai giá trị legacy khi được dùng với snapshot cũ; nội dung đã đổi có thể không xuất hiện trong release delta nếu writer không đánh dấu journal; rollback template có thể lệch current history head.
- **Unknowns:** Chưa dựng end-to-end cho từng install/rebase; checkpoint count có thể gồm nhiều phiên bản của cùng note, không phải số note/slot duy nhất đang được tất cả learner đọc. Chưa có migration script mới để kiểm tra writer có gọi journal hay không.

### F8 — [P2] Validation queries chưa kiểm tra đúng identity và các trạng thái rỗng

- **Observed:** Query 2/3 nhóm bằng tên NoteType + tên field, gộp En4Everyone User 1 và User 4 dù bảng thống kê tách theo owner. Empty predicate và so sánh pair lengths cũng không xử lý JSON null/SQL missing nhất quán.
- **Evidence:** Báo cáo dòng 843–856, 866–872 và Query 4/5. MySQL thực tế: `JSON_LENGTH(JSON null)=1`, `JSON null IS NULL=0`, `JSON_LENGTH(missing)=NULL`, `JSON_LENGTH("")=1`; phép `!= NULL` không trả true.
- **Potential concern:** Query không phát hiện mismatch khi một bên thiếu key; JSON null/empty string bị bỏ sót trong empty_count. Query gom tên không phát hiện một owner/schema sai mà owner khác vẫn đúng.
- **Impact:** Validation gate có false negatives khi gặp đúng các trạng thái rỗng/legacy mà báo cáo nói cần hỗ trợ.
- **Unknowns:** Census Notes hiện có 139 empty lists và bốn missing keys, không có array slot string. Null/empty-string defect được xác nhận bằng fixture SQL, chưa phải một sai số đã chứng minh trong census hiện tại.

## Các điểm khác cần chỉnh trong báo cáo

- Claim giữ nguyên layout chưa có render/screenshot evidence. Báo cáo dòng 218 ghi grid gap `6px 16px`, trong khi `note-type-templates/advanced-vocabulary-card/style.css:190` đặt row-gap 3px. Mẫu reading-list/reading-tag chưa kèm CSS tương ứng; không nên coi sample là thay thế hoàn chỉnh có bảo toàn style.
- `preserveDuplicates: true` không phải option của `splitToArray()` hiện tại. `normalizeArrayValue()` đã giữ item lặp; cần gọi đúng API và kiểm tra thứ tự/cardinality, không dựa vào một flag chưa tồn tại.
- Không có artifact binary-log/commit-isolation đính kèm để review độc lập các chứng nhận “0 mutations” hoặc nguồn gốc 42 file. Không suy ra các chứng nhận đó sai; chỉ chưa được xác nhận trong lượt review này. Không chạy quy trình stash khi phiên khác còn chỉnh cùng working tree.

## Validation và điều kiện nghiệm thu còn thiếu

67 backend tests được chạy: 64 pass, ba test của host typing mode đã parked được skip. 45 frontend tests pass. Các test này kiểm tra utility/renderer/contract, không thay thế việc thực thi template DB hiện hữu với nhiều item. Hai repro Typing và một repro En4 ở trên vẫn xác nhận regression.

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_flashcard_renderer.py tests/test_field_array_conversion.py tests/test_study_typing_template.py --backend-only
.\.venv\Scripts\python.exe scripts/run_tests.py --file frontend/src/entities/flashcard/lib/clientRenderer.test.ts frontend/src/lib/arrayField.test.ts frontend/src/features/note-types/lib/arrayConversion.test.ts --frontend-only
```

Script và kết quả review local nằm trong thư mục ignored `output/native-json-array-report-review/`:

```powershell
.\.venv\Scripts\python.exe output/native-json-array-report-review/review_probe.py
node output/native-json-array-report-review/review_dom.mjs
```

`evidence.json` chứa census, các phản ví dụ và hash báo cáo; `fixture.json`/`dom-results.json` chứa template render và kết quả tương tác. Đây là artifact local, không phải dữ liệu public hoặc release payload.

Trước nghiệm thu cần bằng chứng: từng accepted answer hoạt động ở mặt trước; mỗi section có đúng một tiêu đề/container; list mới và string legacy đều giữ item boundary trong owner/clone/template-pinned flows; field chưa chuyển vẫn giữ delimiter behavior; không đưa richtext vào array text thuần; patch dữ liệu có before/after từng note đã xác minh; apply/restore giữ writer gate, stale-value checks, journal và lịch sử. Chưa thực hiện thay đổi nào để giải quyết các finding trong lượt review này.
