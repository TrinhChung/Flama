# Kế hoạch chế độ gõ đáp án — so sánh ở frontend

> **Trạng thái (2026-10-10): T-01..T-08 đã triển khai cho NoteType người dùng sở hữu**, trên nhánh `refactor/frontend-fsd-renderer-boundary`, chưa push: `24d879f5` và `f0f90946` (T-01..T-03, commit gộp cùng việc khác), `851c1302` (T-04), `3e51c94b` (T-05), `8c914a85` (T-06), `94849c42` (T-07), `d93b40b2` (T-08). R-01 (kiểm tra trên trình duyệt với dữ liệu thật) xong, các lỗi tìm được sửa ở `d763043e`. Còn lại: nạp code vào Flask local (R-03), kiểm tra production trước deploy (R-04); chuyển đổi cho deck đã cài để dành (R-02). Xem [§10](#10-việc-còn-lại-sau-triển-khai).
>
> **Đổi hướng 2026-10-10:** ô gõ do Flama vẽ đã được comment lại. Gõ đáp án nay viết trong HTML/JS của chính template; kiểu field `answers` và công cụ chuyển đổi vẫn giữ. Xem [§12](#12-đổi-hướng-2026-10-10-tạm-cất-ô-gõ-của-flama-template-tự-viết-htmljs).
>
> Khác với [mức 3](./P8_GENERIC_ACTION_OUTCOME_PLAN_2026-10-10.md): server không chấm, contract bốn rating giữ nguyên. Mức 3 chỉ cần khi muốn kết quả gõ tự ghi tiến độ mà người học không xác nhận.

## 1. Mục tiêu và nguyên tắc

Người học gõ đáp án, nhấn Enter, frontend so với danh sách đáp án của Note và báo Đúng hoặc Sai.

- **Server không chấm** và không lưu gì về lượt gõ. Tiến độ vẫn ghi bằng bốn rating sau khi người học xác nhận.
- **Dữ liệu đáp án phải sạch và có quy tắc** trước khi dùng: field kiểu mới `answers`, mỗi dòng một đáp án.
- **Không thêm bảng, không thêm cột.** Chỉ thêm một giá trị `field_type`.
- So sánh dựa đúng vào dữ liệu người dùng nhập, không đoán nghĩa.

## 2. Quyết định đã chốt (chủ sản phẩm, 2026-10-10)

| ID | Nội dung |
|---|---|
| D-T1 | Có công cụ để người dùng chọn field muốn chuyển sang kiểu `answers`; Flama cung cấp sẵn các kiểu tách bằng regex (§4) |
| D-T2 | Không coi katakana = hiragana. Người dùng tự nhập đáp án nên so đúng như nhập. Chức năng gợi ý (ví dụ mở ký tự đầu để thấy là katakana) bổ sung sau |
| D-T3 | Tiếng Việt so sánh có dấu; thiếu dấu là sai vì nghĩa thay đổi. Chỉ so với danh sách đáp án của người dùng |
| D-T4 | Chưa xử lý xuất sang Anki; hiện không có dự định |
| D-T5 | Import Anki giữ nguyên như hiện tại (field text). Muốn dùng chế độ gõ thì chuyển field bằng công cụ D-T1 |
| D-T6 | So sánh không phân biệt chữ hoa và chữ thường |
| D-T7 | Input `answers` của Template gắn được với field `answers` hoặc `text` |
| D-T8 | Không tự gửi rating. Đúng → lật sang mặt sau và báo Đúng. Sai → báo Sai, người học gõ lại. Có gợi ý mở dần ký tự trên các ô ẩn kiểu ô mật khẩu (Template cấu hình). Khó quá thì bỏ qua, lật thẳng mặt sau để đọc. Người học tự chọn rating |

## 3. Kiểu field `answers`

**Định dạng lưu:** chuỗi, **mỗi dòng một đáp án**. Không có HTML, không có dòng rỗng, không trùng. Frontend chuẩn hóa ngay khi lưu; ô nhập dạng chip, mỗi chip một đáp án.

Lý do lưu chuỗi thay vì mảng JSON: các đường đọc hiện có (renderer, tìm kiếm, Connect) coi giá trị field là chuỗi. Renderer server đã giữ xuống dòng cho field text (`app/services/flashcard_renderer.py:457-462, 984`), nên field `answers` hiển thị mỗi đáp án một dòng mà không cần sửa renderer. Client renderer (`frontend/src/entities/flashcard/lib/clientRenderer.ts`) dùng `render_context` do server dựng sẵn, nên hiển thị giống hệt (đã kiểm khi triển khai).

**Dấu vết trong DB:**

| | Thay đổi |
|---|---|
| Schema | Thêm giá trị `answers` (7 ký tự). Cột `field_type` của `field_defs` và `deck_clone_added_field_defs` là `varchar(8)`, không có CHECK constraint (đo trên MySQL local 2026-10-10, SQLAlchemy 2.0 Enum không native). **Không cần migration.** Phải đo lại trên production bằng principal SELECT-only trước khi deploy ([R-04](#r-04--kiểm-tra-production-trước-deploy)) |
| Dữ liệu | Chỉ các field người dùng chủ động chuyển |
| Khi học | Không có gì mới. `review_events` vẫn là event rating bình thường |

**Ràng buộc:**

- Field chính (`identity_role = 'primary'`) giữ kiểu `text`, giống quy tắc clone hiện có (`app/services/flashcards_share_service.py:3402-3404`). Field chính vẫn dùng làm đáp án được theo §5.
- Field media (image, audio, diagram) không chuyển được.
- Đổi kiểu trong trình sửa NoteType (`EditFieldCard`) sang `answers` phải đi qua công cụ §4, không đổi kiểu trần. Nếu đổi trần, giá trị chưa tách sẽ bị coi là một đáp án.
- Nguồn ghi khác (Connect/Yomitan, MCP, import vào field đã là `answers`) được lưu như text, không bị từ chối, để không làm hỏng luồng mining. Frontend vẫn đọc theo §5; Note chưa sạch có thể chạy lại công cụ §4.

**Nơi phải nhận kiểu mới:**

- Backend đang có khoảng 8 bản sao danh sách kiểu field: `app/routes/flashcards/__init__.py:72`, `app/services/flashcard_content_service.py:55`, `app/services/flashcards_share_service.py:52`, `app/validators/template_library.py:6`, `app/validators/mcp.py:129`, `app/services/mcp_tool_registry.py:1131`, `app/services/mcp/note_type_tools.py:111`, `app/services/connect/import_session.py:163`, cùng hai Enum trong `models/field_def.py` và `models/deck_clone_added_field_def.py`. **Gom về một hằng số dùng chung trước** rồi mới thêm `answers`, để không vá rải rác. *Đã làm ở T-05:* hằng số nằm ở `models/field_types.py`. Danh sách của Connect (kiểu field client bên ngoài được khai báo) và `app/services/share/constants.py` (chỉ nhánh cutover clone cũ dùng) cố ý giữ nguyên.
- Frontend: `FIELD_TYPES` ở `frontend/src/features/note-types/hooks/useNoteTypeFields.ts:24`, các chỗ rẽ nhánh theo kiểu trong `features/browse`, `entities/card-template`, `features/template-library`, `features/study/components/StudyQuickEditFields.tsx`. Import Anki (`frontend/src/lib/ankiSyncEngine.ts:165`) xử lý field `answers` như `text`.

## 4. Công cụ chuyển field sang `answers` (D-T1)

**Luồng:**

1. Người dùng chọn NoteType và field. Field chính và field media không có trong danh sách.
2. Chọn một hoặc nhiều kiểu tách (bảng dưới).
3. **Xem trước mọi Note của NoteType**, không chỉ deck đang mở, vì kiểu field thuộc NoteType. Mỗi dòng hiện giá trị cũ và danh sách mới, kèm cảnh báo: kết quả rỗng, còn thẻ HTML, dòng quá dài, đáp án trùng đã gộp, không thấy dấu tách (giữ nguyên làm một đáp án). Người dùng sửa tay từng Note nếu cần.
4. **Tải file sao lưu** giá trị cũ (bắt buộc trước khi áp dụng). Bản sao nằm ở máy người dùng, không lưu trong DB.
5. **Áp dụng trong một request.** Server ghi nguyên tử: đổi kiểu field và ghi giá trị mới cho toàn bộ Note. Server từ chối (409 `NOTES_CHANGED`) nếu kiểu field, tập Note hoặc giá trị hiện tại của bất kỳ Note nào khác lúc xem trước. Server chỉ kiểm tra hình dạng (chuỗi, mỗi dòng không rỗng, không trùng, không HTML), không tách lại.
6. **Hoàn tác** bằng file sao lưu, qua cùng endpoint theo chiều ngược: kiểu `text` và giá trị cũ.

**Kiểu tách Flama cung cấp (regex định nghĩa sẵn):**

| Kiểu | Tách theo | Lưu ý |
|---|---|---|
| Dấu phẩy | `,` `，` | Không dùng nếu nghĩa có chứa dấu phẩy |
| Dấu chấm phẩy | `;` `；` | |
| Dấu phẩy tiếng Nhật | `、` | |
| Gạch chéo | `/` `／` | |
| Xuống dòng | xuống dòng, `<br>` | Thường gặp ở dữ liệu import từ Anki |
| Đánh số | `1.` `2)` `①` … | Bỏ phần số, giữ nội dung |
| Dấu chấm giữa | `・` | **Tắt mặc định**: tên katakana ghép (ジョン・スミス) dùng dấu này |

Sau khi tách: bỏ khoảng trắng đầu cuối từng phần tử, bỏ phần tử rỗng, gộp trùng (giữ thứ tự), bỏ thẻ HTML còn sót (có cảnh báo). Regex do người dùng tự viết không có ở bản đầu; nếu thêm thì phải chạy trong Web Worker, có giới hạn thời gian và độ dài.

**Deck cài từ marketplace: chưa hỗ trợ ở bản này.** Công cụ chỉ áp dụng cho NoteType người dùng sở hữu, và chỉ đọc, ghi Note của chính chủ NoteType. Note mà người khác thêm vào bản cài của họ không bị lộ và không bị sửa. Với deck đã cài, chế độ gõ vẫn dùng được với field `text` (D-T7). Muốn có nhiều đáp án thì tác giả chuyển field ở deck nguồn rồi phát hành release. Kế hoạch overlay để dành ở [R-02](#r-02--chuyển-đổi-cho-deck-cài-từ-marketplace-để-dành).

**Deck do người dùng phát hành:** thay đổi đi theo release kế tiếp như mọi thay đổi field khác; khi triển khai cần kiểm tra pipeline release mang theo đổi kiểu field.

## 5. Luật so sánh ở frontend (`typing-compare.v1`)

**Lấy danh sách đáp án** từ field được gắn: lấy văn bản hiển thị (`<br>` là xuống dòng, bỏ các thẻ khác, giải mã entity), rồi **mỗi dòng là một đáp án**. Field `answers` bảo đảm dữ liệu đã sạch. Field `text` dùng được khi mỗi dòng đã là một đáp án, thường là field chính chỉ có một dòng.

**Chuẩn hóa cả câu gõ và đáp án**, chỉ với các khác biệt không đổi nghĩa:

- Unicode NFC: cùng một chữ có dấu có thể được mã hóa theo hai cách tùy bộ gõ hoặc nguồn dữ liệu. Không chuẩn hóa thì hai chuỗi trông giống hệt vẫn bị chấm khác nhau.
- Bỏ khoảng trắng đầu cuối, gộp khoảng trắng liên tiếp, kể cả khoảng trắng toàn độ rộng (U+3000) của IME tiếng Nhật.
- Không phân biệt chữ hoa và chữ thường (D-T6); bàn phím điện thoại hay tự viết hoa chữ đầu.

**Không chuẩn hóa:** dấu tiếng Việt (D-T3), katakana/hiragana (D-T2), kanji/kana, độ rộng ký tự, dấu câu.

**Kết quả:** Đúng khi trùng ít nhất một đáp án; ngược lại là Sai. Cách hiển thị và gõ lại theo §6.

**Ô nhập:** tắt `autocapitalize`, `autocorrect`, `spellcheck`, `autocomplete`. Bỏ qua Enter khi IME đang chuyển đổi (`isComposing`), nếu không người học vừa chọn kanji là bài đã bị gửi.

**Note không có đáp án** (field rỗng): ẩn ô gõ, quay về lật thẻ và tự chấm.

Kết quả so sánh không gửi lên server và không được lưu.

## 6. Luồng học và gắn vào chế độ

**Khai báo trong Template:**

- Template khai báo một input kiểu `answers` trong `input_schema`, tối đa một input kiểu này mỗi Template (một Interaction chính, [canonical plan §6.4](../../architecture/study-interaction-trigger-algorithm-plan.md#64-one-primary-interaction)).
- Input này gắn được với field `answers` hoặc `text` (D-T7), nhờ đó gõ được field chính mà không phải chuyển kiểu. Cần nới kiểm tra "kiểu input = kiểu field" ở `app/validators/template_library.py:81, 92` cho đúng cặp này.
- Cấu hình chế độ gõ nằm ngay trong input đó: `show_length` (hiện số ký tự cần gõ bằng các ô ẩn, như ô mật khẩu) và `hints` (cho mở gợi ý). `input_schema` đã là cột JSON trên `templates` và `template_versions`, nên không cần migration; chỉ thêm khóa vào danh sách cho phép của validator (`app/validators/template_library.py:32`).

**Luồng (D-T8):**

1. Mặt trước: host hiện ô gõ và tự focus vào đó. Nếu `show_length` bật, hiện các ô ẩn theo độ dài đáp án chuẩn.
2. Nhấn Enter:
   - **Đúng:** host lật sang mặt sau và hiện "Đúng".
   - **Sai:** hiện "Sai", giữ nguyên chữ đã gõ để người học sửa, **không hiện đáp án**. Gõ lại bao nhiêu lần cũng được.
3. **Gợi ý** (nếu bật): mỗi lần bấm mở thêm một ký tự trên các ô, từ trái sang phải, tối đa đến khi còn một ký tự.
4. **Bỏ qua:** lật thẳng sang mặt sau để đọc thông tin, hiện "Đã bỏ qua".
5. Mặt sau hiện kết quả (đúng ngay lần đầu, đúng sau N lần thử, đã dùng K gợi ý, hoặc đã bỏ qua) cùng các đáp án. Người học **tự chọn** một trong bốn nút như hiện nay. Không tự gửi rating, không tô sẵn nút.

**Quy tắc chi tiết:**

- Đáp án chuẩn để tính số ô và mở gợi ý là **dòng đầu tiên** của field; các dòng khác vẫn được chấp nhận khi so sánh.
- Đếm ký tự theo grapheme (`Intl.Segmenter`), để mỗi chữ có dấu hay mỗi chữ Nhật là một ô. Khoảng trắng trong đáp án hiện sẵn thành khoảng trống, không tính là ô.
- Ô gõ do host vẽ, nằm ngoài iframe. Khi focus ở ô gõ thì phím tắt học (Space, 1–4) không chạy ([ADR phím tắt tin cậy](../../architecture/trusted-study-keyboard-boundary-2026-09-07.md)).
- Sau khi lật, Enter ở mặt sau nghĩa là "Tốt" (theo ADR). Phím Enter vừa dùng để gửi đáp án không được tính luôn là "Tốt": bỏ qua phím lặp (`event.repeat`) và chỉ nhận một lần nhấn mới.
- Nút "Bỏ qua" dùng lại hành động "Hiện đáp án" sẵn có. Phím tắt cho nút này chốt khi làm giao diện, không được trùng phím dùng để gõ.
- Thông báo Đúng/Sai đọc được bằng trình đọc màn hình (`aria-live`).
- Note không có đáp án: không hiện ô gõ, học như lật thẻ thường.

**Vì sao làm ở host chứ không trong Template:** Template không lật thẻ được và không gửi lệnh nào cho host (ADR phím tắt tin cậy), nên không làm được "đúng thì tự lật". Host đã có sẵn những thứ cần dùng:

- trạng thái lật và `onReveal` (`frontend/src/features/study/components/StudyBottomBar.tsx:13, 21`);
- giá trị field của Note trong artifact phiên (`StudyContentArtifact.field_values`, `frontend/src/features/study/types.ts:84-93`).

Vì vậy chế độ gõ làm được bằng một component riêng trong `features/study`, không cần chờ tách toàn bộ Interaction host và không cần API mới. Hai điểm cần kiểm khi triển khai đều đã rõ:

- Binding projection đặt giá trị field được gắn vào `content.field_values[<key của input>]` (`app/services/template_binding_service.py`). Artifact Template mang thêm `typing_input` (`study-typing-input.v1`: key, `show_length`, `hints`) khi Template có input `answers`. Template khác giữ nguyên artifact và version.
- Với deck đã cài, `build_effective_study_card` áp override overlay trước binding projection, nên đáp án là giá trị sau overlay.

**Gợi ý khác (sau, D-T2):** ví dụ mở ký tự đầu để người học thấy là katakana.

## 7. Work package

| ID | Nội dung | Phụ thuộc | Trạng thái | Kết quả |
|---|---|---|---|---|
| T-01 | Hàm `typing-compare.v1` (§5) và hàm tính ô, mở gợi ý ở frontend, kèm bộ test (NFC, hoa thường, khoảng trắng, U+3000, IME, dấu tiếng Việt, kana, grapheme) | — | Hoàn thành | Đã hoàn thành (`typingAnswer.ts`) |
| T-02 | Validator Template: nhận input kiểu `answers`, cho gắn với field `text`, thêm khóa `show_length`/`hints`; sửa tương ứng ở `frontend/src/features/template-library/lib/inputSchemaValidation.ts` | — | Hoàn thành | Đã hoàn thành (`template_library.py`, `inputSchemaValidation.ts`) |
| T-03 | Component ô gõ ở host theo §6: Enter, Đúng/Sai, gõ lại, ô ẩn, gợi ý, bỏ qua, kết quả ở mặt sau | T-01, T-02 | Hoàn thành | Đã hoàn thành (`StudyTypingAnswerPanel.tsx`, `StudyPage.tsx`) |
| T-04 | Template mẫu "Gõ đáp án" | T-02 | Hoàn thành | Đã hoàn thành (`CreateTemplateDialog.tsx`) |
| T-05 | Gom danh sách kiểu field về một hằng số (backend, frontend) | — | Hoàn thành | Đã hoàn thành (`models/field_types.py`) |
| T-06 | Thêm kiểu field `answers`: validator, MCP, overlay, `FIELD_TYPES` frontend, ô nhập (textarea "mỗi dòng một đáp án", chuẩn hóa khi lưu), kiểm hiển thị cả hai renderer; chặn đổi kiểu trần | T-05 | Hoàn thành | `models/field_types.py`, `flashcard_content_service.py` (409 `FIELD_TYPE_REQUIRES_CONVERSION`), `src/lib/answersField.ts`. Đo cột production chuyển sang [R-04](#r-04--kiểm-tra-production-trước-deploy) |
| T-07 | Endpoint xem trước và áp dụng/hoàn tác chuyển đổi nguyên tử cho NoteType sở hữu, có điều kiện tiên quyết | T-06 | Hoàn thành (chỉ NoteType sở hữu) | `field_answers_conversion_service.py`, `validators/field_answers_conversion.py`. Overlay chuyển sang [R-02](#r-02--chuyển-đổi-cho-deck-cài-từ-marketplace-để-dành) |
| T-08 | Công cụ chuyển đổi ở frontend: kiểu tách, xem trước, sửa tay, file sao lưu (§4) | T-07 | Hoàn thành | Đã hoàn thành (`FieldAnswersConversionDialog.tsx`) |

T-01..T-08 đã có test backend và frontend (§9). Chế độ gõ và công cụ chuyển đổi đã kiểm trên trình duyệt, gồm cả dữ liệu thật trên MySQL local (R-01).

## 8. Câu hỏi đã chốt

1. NoteType có nhiều Note (chủ sản phẩm đồng ý 2026-10-10, đã làm ở T-08): màn xem trước hiện tóm tắt (tổng số Note, số cần xem, số không đổi) và chỉ liệt kê Note có cảnh báo, có phân trang; vẫn xem được toàn bộ theo trang. Áp dụng một lần cho cả NoteType trong một giao dịch. Không giới hạn số Note ở quy mô hiện tại; validator nhận tối đa 20.000 Note mỗi lần. NoteType lớn hơn mới cần chia đợt, khi đó phải thiết kế thêm.

   *Đo trên DB local (R-01):* có một NoteType 35.108 Note (đã phát hành), vượt giới hạn. Đọc xem trước mất 3,4 giây, trả 3,6 MB; request áp dụng sẽ khoảng 7 MB, vẫn dưới `client_max_body_size 20m` của nginx production. Thời gian ghi 35k Note trong một giao dịch chưa đo. Giao diện hiện báo ngay "vượt giới hạn" và khóa nút áp dụng. Muốn nâng giới hạn hoặc chia đợt thì đo thời gian ghi trên một bản sao lớn trước.

Không còn câu hỏi mở cho phạm vi NoteType sở hữu.

## 9. Kiểm chứng

Đã chạy khi triển khai (2026-10-10):

- Backend: `python scripts/run_tests.py --module templates,flashcards,browse,connect_mcp,marketplace --backend-only` đạt 69 file. Test mới: `tests/test_study_typing_template.py` (validator, binding, artifact `typing_input`, kiểu `answers`, chặn đổi kiểu trần) và `tests/test_field_answers_conversion.py` (chỉ Note của chủ, nguyên tử, 409, giá trị sạch, field chính/media, rename đang chạy, khôi phục qua sanitizer, quyền).
- Frontend: vitest cho `features/study` (360), `features/note-types` (95), `features/template-library` (96), `src/lib`; `tsc -b` và `oxlint` sạch.
- Trình duyệt: chế độ gõ chạy trên một instance riêng (SQLite tạm, Flask 4799, Vite 5183): gõ sai báo "Chưa đúng" và giữ thẻ, mở gợi ý, gõ đúng tự lật và hiện "Đúng · lần thử thứ 2 · đã mở 1 gợi ý".
- R-01 (2026-10-10) trên DB MySQL local với dữ liệu thật: xem kết quả ở [R-01](#r-01--kiểm-tra-công-cụ-chuyển-đổi-trên-trình-duyệt-và-mobile).

## 10. Việc còn lại sau triển khai

R-01 đã xong. Tiếp theo: R-03 rồi R-04. R-02 để dành, chỉ mở khi đủ điều kiện.

| ID | Việc | Ai làm | Chặn deploy? |
|---|---|---|---|
| R-01 | Kiểm tra công cụ chuyển đổi trên trình duyệt và giao diện mobile | Claude — **xong 2026-10-10** | Có (đã đạt) |
| R-02 | Chuyển đổi cho deck cài từ marketplace (overlay) | Để dành | Không |
| R-03 | Nạp code mới vào Flask local (cổng 4789) | Chủ dự án (server chạy trong terminal của bạn) | Không |
| R-04 | Kiểm tra production trước deploy, rồi deploy và smoke test | Claude (SELECT-only), chủ dự án duyệt merge | Là bước deploy |

### R-01 — Kiểm tra công cụ chuyển đổi trên trình duyệt và mobile

**Trạng thái:** xong 2026-10-10. Ba lỗi tìm được sửa ở `d763043e`, có test.

**Môi trường đã dùng.** Kế hoạch ban đầu dùng SQLite tạm. Chủ dự án yêu cầu chạy trên MySQL local vì có dữ liệu thật đầy đủ, nên dữ liệu thật được bảo vệ như sau:

- Tạo tài khoản thử riêng `r01-local-tester`. Chép hai NoteType thật chưa phát hành của một người dùng local vào tài khoản này qua API thường: Kanji_N3 (724 Note) và En4Everyone (1.179 Note). Note nguồn chỉ được đọc. Field media để trống vì asset thuộc chủ cũ.
- Dùng Flask riêng ở cổng 4799, trỏ vào MySQL local (`STARTUP_RUN_MAINTENANCE=0`, cờ `STUDY_*` để trống), và Vite riêng ở cổng 5183. Server 4789/5173 của chủ dự án không bị đụng.
- Chụp giá trị của bốn field sẽ thử trước khi bắt đầu, rồi so lại sau khi khôi phục: không có khác biệt.

**Kết quả desktop:**

| # | Kịch bản | Kết quả |
|---|---|---|
| 1 | Field chính và field ảnh không có nút. Field có thay đổi chưa lưu thì nút bị khóa. | Đạt |
| 2 | Xem trước field "Nghĩa" của Kanji_N3: 724 Note, 35 cần xem, 578 không đổi. Lọc, phân trang (37 trang ở "Tất cả"), đổi kiểu tách (bật dấu phẩy Nhật thì còn 562 không đổi), sửa tay rồi "Bỏ sửa" đều chạy. | Đạt sau khi sửa lỗi 1 (trước khi sửa: 3 cần xem, 572 không đổi) |
| 3 | Nút Áp dụng bị khóa cho đến khi tải sao lưu. File đúng `flama-answers-backup.v1`, giá trị khớp DB. | Đạt |
| 4 | Áp dụng (lần chạy trước khi sửa lỗi 1): 152 Note đổi, giá trị sạch, có AuditLog `field.convert_answers`. Browse hiện textarea có gợi ý; lưu từ Browse chuẩn hóa mỗi đáp án một dòng. | Đạt |
| 5 | Học chế độ gõ với thẻ 最低: gõ "Ít nhất" (dòng thứ hai, viết hoa) được chấm Đúng. | Đạt |
| 6 | Sửa một Note ở tab khác rồi áp dụng: báo lỗi 409 và hiện nút "Tải lại xem trước". Tải lại thì phải tải sao lưu lần nữa, rồi áp dụng được. Thử trên field "Synonym_VI" của En4Everyone: 1.179 Note, 22 cần xem, trong đó 20 trùng đáp án. | Đạt sau khi sửa lỗi 2 |
| 7 | Khôi phục từ file sao lưu: tóm tắt đúng, kiểu và giá trị cũ trở lại. File của field khác và file hỏng bị từ chối. | Đạt |
| 8 | Field `richtext` "Example_VI": 65 cần xem vì có HTML. Chuyển rồi khôi phục về `richtext`, giá trị như cũ. | Đạt |

**Lỗi tìm được và đã sửa (`d763043e`):**

1. Dấu phẩy trong ngoặc bị tách. Ví dụ "Số tờ, số tấm (giấy, ảnh, vé)" bị cắt thành bốn đáp án. Nay không tách bên trong `() （） [] ［］ 【】 「」 『』 {} ｛｝`, và gắn cờ "Có phần trong ngoặc, người học phải gõ cả phần này" để người dùng xem lại.
2. Lỗi từ server (409 và các mã khác) hiện nguyên câu tiếng Anh trên giao diện tiếng Việt. Nay frontend dịch theo mã lỗi; mã lạ thì hiện kèm thông báo gốc.
3. NoteType vượt 20.000 Note chỉ bị từ chối sau khi đã tải sao lưu và bấm áp dụng. Nay hộp thoại báo ngay và khóa nút áp dụng (số đo ở §8).

**Kết quả mobile** (375×812, xong đã trả pane về desktop):

- Trình sửa field và hộp thoại vừa khung: không cuộn ngang; hộp thoại cuộn được và luôn thấy hai nút ở chân.
- Màn học: ô gõ nằm trên thanh dưới, không chồng lên nhau, không cuộn ngang. Gợi ý, Bỏ qua và mặt sau chỉ mới kiểm ở desktop.
- Ghi nhận, chưa sửa: với đáp án dài (field `text` nhiều chữ), dãy ô ẩn xuống thành ba hàng. Vẫn dùng được; có thể làm gọn sau nếu cần.
- Chưa kiểm bàn phím ảo trên máy thật (pane không giả lập được).

**Chế độ tối:** chưa kiểm được. App hiện không có chỗ nào bật lớp `.dark`, nên người dùng cũng không vào được chế độ tối. Nếu sau này thêm chế độ tối, renderer phải truyền theme vào iframe của Template.

**Dọn dẹp:** đã dừng Flask 4799 và Vite 5183, xóa `frontend/node_modules/.claude-verify` và các DB SQLite tạm. Dữ liệu thử vẫn còn trong MySQL local: tài khoản `r01-local-tester`, hai NoteType "(R-01 sandbox)", các deck "R-01 sandbox", khoảng 1.900 Note cùng thẻ và AuditLog của chúng. Có thể xóa khi không cần nữa.

### R-02 — Chuyển đổi cho deck cài từ marketplace (để dành)

**Hiện trạng:** công cụ chỉ dành cho NoteType sở hữu (`_owned_field` lọc theo `user_id`). Deck đã cài vẫn học chế độ gõ với field `text` (D-T7). Cách khuyến nghị hiện tại là tác giả chuyển field ở deck nguồn rồi phát hành release.

**Lý do chưa làm:**

1. Frontend chưa có giao diện nào sửa schema overlay: không chỗ nào gọi `updated_defs` hay `added_defs`, nên phải làm một điểm vào mới.
2. Override giá trị từng Note làm người học tách khỏi các chỉnh sửa sau này của tác giả trên field đó.
3. `upsert_clone_overlay` xử lý từng mục với nhiều truy vấn, nên hàng nghìn Note sẽ chậm.
4. Có ba loại Note phải xử lý khác nhau: Note nguồn trong phạm vi install (ghi override), Note người học tự thêm (Note thật của họ nhưng dùng NoteType của tác giả), và field chính không được đổi kiểu trong clone.

**Điều kiện mở lại:** có người học cần gõ nhiều đáp án trên deck marketplace mà tác giả không chuyển, hoặc tác giả có nhiều người cài yêu cầu.

**Phác thảo khi mở lại:**

- Điểm vào ở trang deck đã cài: "Chuyển field sang Đáp án gõ (chỉ cho bạn)".
- Endpoint theo `deck_install_id`:
  - GET trả giá trị hiệu lực (sau overlay) của Note nguồn trong phạm vi và của Note người học tự thêm.
  - POST ghi trong một giao dịch: `DeckCloneFieldDefOverride.properties.field_type = 'answers'`, override giá trị Note nguồn qua một đường ghi theo lô mới (giữ đủ kiểm tra phạm vi của `upsert_clone_overlay` nhưng gom truy vấn), cập nhật thẳng Note người học tự thêm, rồi tăng `overlay_revision`.
- Khôi phục: xóa các override do lần chuyển tạo ra, vì Note nguồn trở lại nội dung tác giả mà không cần file sao lưu. Note người học tự thêm vẫn cần sao lưu.
- Phải đọc trước khi làm: `docs/plans/completed/CLONE_CUTOVER_REPORT.md` và hành vi rebase khi tác giả phát hành release mới (`app/services/deck_install_rebase_service.py`).
- Test cả deck sở hữu lẫn deck đã cài, install theo release lẫn không theo release (`AGENTS.md`).

**Ước lượng:** một đợt riêng (đường ghi overlay theo lô, giao diện mới, test), ngoài ngân sách hiện tại.

### R-03 — Nạp code mới vào Flask local

1. Trong terminal đang chạy `flask --app wsgi.py run --host=0.0.0.0 --port=4789`, dừng server (Ctrl+C) rồi chạy lại đúng lệnh đó từ thư mục repo. Không có migration; khởi động chạy như thường.
2. Vite 5173 đã tự nạp frontend mới; chỉ backend cần khởi động lại. Phiên học đang mở giữ artifact cũ, phải mở phiên mới mới thấy ô gõ.
3. Kiểm nhanh:
   - tạo được field mới kiểu "Đáp án gõ";
   - mở công cụ chuyển đổi trên một field `text` thì thấy bản xem trước (GET `/api/note-types/<id>/fields/<field_id>/answers-conversion` trả 200);
   - học bằng Template có input `answers` thì ô gõ hiện.

Lưu ý: dùng thử công cụ chuyển đổi trên MySQL local sẽ sửa dữ liệu Note thật. Hãy tải bản sao lưu trước khi áp dụng.

### R-04 — Kiểm tra production trước deploy

**1. Đo cấu trúc cột** (đọc-only, principal SELECT-only theo quy trình hiện có: `/etc/flama/phase9-audit.env` qua một `--defaults-extra-file` tạm, xóa ngay sau khi dùng):

```sql
SELECT TABLE_NAME, COLUMN_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME = 'field_type'
  AND TABLE_NAME IN ('field_defs', 'deck_clone_added_field_defs');

SELECT tc.TABLE_NAME, cc.CONSTRAINT_NAME, cc.CHECK_CLAUSE
FROM information_schema.TABLE_CONSTRAINTS tc
JOIN information_schema.CHECK_CONSTRAINTS cc
  ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
WHERE tc.TABLE_SCHEMA = DATABASE()
  AND tc.TABLE_NAME IN ('field_defs', 'deck_clone_added_field_defs');

SELECT field_type, COUNT(*) FROM field_defs GROUP BY field_type;
```

- **Kỳ vọng:** cột tối thiểu `varchar(8)` và không có CHECK constraint giới hạn giá trị. Production đã có giá trị 8 ký tự (`richtext`, `markdown`), nên `answers` (7 ký tự) chắc chắn vừa độ dài; điểm cần kiểm thật sự là CHECK.
- **Nếu có CHECK:** dừng deploy, viết migration Alembic nới hoặc bỏ constraint, kèm backup và probe MySQL theo quy trình các phase trước.
- Ghi kết quả vào §3 thay cho dòng "phải đo lại".

**2. Đường deploy:**

- Các commit của chế độ gõ nằm trên `refactor/frontend-fsd-renderer-boundary` cùng nhiều việc khác (refactor FSD, Connect multi-version…). Deploy nghĩa là merge cả nhánh, nên phải xem CI và review cho toàn nhánh.
- Muốn ship riêng chế độ gõ thì phải tách sang nhánh khác. Việc này khó, vì T-01..T-03 nằm trong commit gộp của phiên khác (`24d879f5`, `f0f90946`).
- Không có migration, nhưng theo quy trình vẫn backup trước khi merge thay đổi runtime.
- Frontend (Cloudflare Pages) có thể lên trước backend vài phút. Trong khoảng đó công cụ chuyển đổi báo lỗi 404, và template có `<input>` mất ô nhập cho tới khi backend mới lên. Chấp nhận được theo thỏa thuận đã có.

**3. Smoke test sau deploy** (SSH, đọc-only, cộng một tài khoản thử):

- GET endpoint chuyển đổi trả 200 cho NoteType sở hữu và 404 cho người khác;
- artifact của một template có `<input>` vẫn giữ ô nhập (§12);
- tạo được field `answers`.

**Xong khi:** kết quả SQL đã ghi; deploy và smoke test đạt.

## 11. Handoff

```text
Task ID: STUDY-TYPING-ANSWER
Primary outcome: chế độ gõ so sánh ở frontend (Đúng/Sai/gõ lại/gợi ý/bỏ qua ở host, typing-compare.v1); kiểu field answers; công cụ chuyển đổi có xem trước, sao lưu, khôi phục cho NoteType sở hữu; quyết định D-T1..D-T8
Commits: 24d879f5, f0f90946 (T-01..T-03, gộp cùng việc khác), 851c1302, 3e51c94b, 8c914a85, 94849c42, d93b40b2 — nhánh refactor/frontend-fsd-renderer-boundary, chưa push
Runtime change: có — field_type answers; input answers; GET/POST /api/note-types/<id>/fields/<field_id>/answers-conversion; template HTML giữ <input>/<label>. Ô gõ của host và typing_input đã cất (§12)
Migration: không (cột field_type varchar(8), không CHECK — local; production đo ở R-04)
Tests added or updated: tests/test_study_typing_template.py, tests/test_field_answers_conversion.py; vitest typingAnswer, StudyTypingAnswerPanel, answersField, answersConversion, FieldAnswersConversionDialog và các test bị ảnh hưởng
Known limitations: deck đã cài chưa chuyển đổi được (R-02); Flask local cần khởi động lại (R-03); production chưa đo cột (R-04); {{FrontSide}} chưa được hỗ trợ
```

## 12. Đổi hướng (2026-10-10): tạm cất ô gõ của Flama, template tự viết HTML/JS

**Quyết định của chủ sản phẩm:** chưa làm phức tạp. Mẫu không chia thành "lật" hay "gõ". Phần gõ đáp án nằm hoàn toàn trong mã mặt trước và mặt sau của thẻ: người viết template tự đặt ô nhập, tự so đáp án và tự làm gợi ý bằng HTML/CSS/JS. Flama và backend không tham gia. Sau này muốn kết quả gõ ghi vào tiến độ thì thêm trigger ([mức 3](./P8_GENERIC_ACTION_OUTCOME_PLAN_2026-10-10.md)).

**Đã comment lại** (đánh dấu `Parked 2026-10-10`; bỏ comment là dùng lại):

| Phần | Vị trí |
|---|---|
| Ô gõ của Flama trên màn học | `frontend/src/features/study/pages/StudyPage.tsx` |
| `typing_input` trong artifact Template | `app/services/study_artifact_service.py` (`template_version`, `build_template_artifact`) |
| Lựa chọn "Lật thẻ cơ bản / Gõ đáp án" khi tạo mẫu | `frontend/src/features/template-library/components/CreateTemplateDialog.tsx` |
| Ô cấu hình "Chế độ gõ" (hiện số ký tự, gợi ý) | `frontend/src/features/template-library/components/TemplateInputSchemaEditor.tsx` |
| Luật "mỗi mẫu một input `answers`", lưu tùy chọn `typing` | `app/validators/template_library.py`, `frontend/src/features/template-library/lib/inputSchemaValidation.ts` |

Code của ô gõ (`StudyTypingAnswerPanel.tsx`, `typing/typingAnswer.ts`, `typing/useTypingAnswer.ts`) và test của chúng vẫn giữ nguyên. Test của hành vi đã cất được đánh dấu skip, kèm cùng ghi chú.

**Giữ nguyên:**

- Kiểu field `answers` (mỗi dòng một đáp án) và công cụ chuyển đổi (§4).
- Kiểu input `answers`, gắn được field `answers` hoặc `text`. Nay một mẫu có thể có nhiều input `answers`.
- Key `typing` lưu từ trước vẫn được nhận, nhưng bị bỏ khi lưu lại.

**Thay đổi để template tự viết ô nhập.** Bộ lọc HTML của template nay giữ thẻ `<input>` và `<label>`: server dùng `TEMPLATE_HTML_TAGS` trong `app/services/flashcard_renderer.py`, client dùng `ALLOWED_TAGS` trong `frontend/src/entities/flashcard/lib/clientRenderer.ts`. Trước đây hai thẻ này bị xóa, nên template chỉ tạo được ô nhập bằng JS.

- Nội dung field vẫn dùng danh sách chặt cũ (`sanitize_html_fragment`).
- Không thêm năng lực mới: script của template vốn tạo được các thẻ này, và iframe sandbox chặn gửi form (`form-action 'none'`) cũng như mạng (`connect-src 'none'`).

**Mẫu tham khảo.** Ở DB local đã có hai bản: "Gõ đáp án (thử)" của user 1, gắn vào deck "Thử chế độ gõ" (`Prompt` = Từ vựng, `Answer` = Nghĩa); và "Điền đáp án (JS)" của tài khoản thử.

- Mặt trước có câu hỏi, ô nhập, nút Kiểm tra, nút Gợi ý, và đáp án nằm trong một `div hidden`.
- Script đọc đáp án theo dòng (mỗi `<br>` là một dòng). Trước khi so, cả hai bên được chuẩn hóa NFC, gộp khoảng trắng và đổi về chữ thường. Khớp một dòng bất kỳ là Đúng. Dấu tiếng Việt phải đúng (D-T3); không phân biệt hoa thường (D-T6).
- Gợi ý là dãy chấm theo đáp án đầu tiên. Mỗi lần bấm mở thêm một ký tự, dừng khi còn một ký tự.
- Mặt sau lặp lại `{{Prompt}}` vì Flama chưa hỗ trợ `{{FrontSide}}` (đã đề xuất sửa ở một phiên riêng).

Mặt trước:

```html
<div class="cz-prompt">{{Prompt}}</div>
<div class="cz-box">
  <input id="cz-input" type="text" placeholder="Gõ đáp án rồi nhấn Enter" autocomplete="off" autocapitalize="off" spellcheck="false">
  <button type="button" id="cz-check">Kiểm tra</button>
  <button type="button" id="cz-hint">Gợi ý</button>
</div>
<div id="cz-mask" class="cz-mask"></div>
<div id="cz-result" class="cz-result"></div>
<div id="cz-answers" hidden>{{Answer}}</div>
<script>
(function () {
  var input = document.getElementById('cz-input');
  var result = document.getElementById('cz-result');
  var mask = document.getElementById('cz-mask');

  // Each line of the field is one accepted answer; a plain string is one line.
  function readAnswers(el) {
    var lines = [''];
    el.childNodes.forEach(function (node) {
      if (node.nodeName === 'BR') lines.push('');
      else lines[lines.length - 1] += node.textContent;
    });
    return lines.map(function (line) { return line.trim(); }).filter(Boolean);
  }
  // Same text = same after NFC, collapsed spaces and lower case.
  function norm(text) {
    return text.normalize('NFC').replace(/[\s\u3000]+/g, ' ').trim().toLowerCase();
  }

  var answers = readAnswers(document.getElementById('cz-answers'));
  var first = Array.from((answers[0] || '').normalize('NFC'));
  var shown = 0;

  // Hint slots follow the first answer: one dot per character, opened left to right.
  function drawMask() {
    mask.textContent = first.map(function (ch, i) {
      return i < shown || ch === ' ' ? ch : '•';
    }).join('');
  }

  function check() {
    var typed = norm(input.value);
    if (!typed) return;
    var ok = false;
    for (var i = 0; i < answers.length; i++) {
      if (norm(answers[i]) === typed) { ok = true; break; }
    }
    result.textContent = ok ? 'Đúng' : 'Sai, thử lại';
    result.className = 'cz-result ' + (ok ? 'cz-ok' : 'cz-bad');
    if (ok) { shown = first.length; drawMask(); } else { input.select(); }
  }

  input.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    check();
  });
  document.getElementById('cz-check').addEventListener('click', check);
  document.getElementById('cz-hint').addEventListener('click', function () {
    if (shown < first.length - 1) shown += 1;
    drawMask();
    input.focus();
  });

  if (!answers.length) {
    document.querySelector('.cz-box').hidden = true;
  }
  drawMask();
  input.focus();
})();
</script>
```

Mặt sau:

```html
<div class="cz-prompt">{{Prompt}}</div>
<hr>
<div class="cz-answer">{{Answer}}</div>
```

CSS dùng chung:

```css
.cz-prompt { font-size: 1.8em; font-weight: 600; text-align: center; margin: 12px 0; }
.cz-box { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.cz-box input { font-size: 1.1em; padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 10px; min-width: 220px; }
.cz-box button { font-size: 0.95em; padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 10px; background: #fff; cursor: pointer; }
.cz-mask { text-align: center; letter-spacing: 0.3em; font-size: 1.2em; margin-top: 12px; color: #71717a; }
.cz-result { text-align: center; margin-top: 8px; font-weight: 600; min-height: 1.4em; }
.cz-ok { color: #15803d; }
.cz-bad { color: #b91c1c; }
.cz-answer { font-size: 1.3em; text-align: center; }
```

**Giới hạn đã biết** (do iframe sandbox, đúng theo ADR bàn phím tin cậy):

- Khi con trỏ đang ở trong ô nhập, phím tắt của màn học (Space lật thẻ, 1–4 chấm điểm) không chạy, vì phím gõ trong iframe không lên tới trang. Muốn lật thì bấm "Hiện đáp án", hoặc bấm ra ngoài thẻ rồi nhấn Space.
- Template không lật thẻ hay chấm điểm được; người học vẫn tự chọn rating.
- Chữ đã gõ không mang sang mặt sau, vì mặt sau là một tài liệu iframe khác và không có bộ nhớ chung.
- Lệnh `input.focus()` lúc mở thẻ có thể bị trình duyệt chặn trong iframe khác origin; khi đó người học bấm vào ô.

**Kiểm chứng (2026-10-10):**

- Backend: `python scripts/run_tests.py --module templates,flashcards,study --backend-only` đạt 102 file. `tests/test_study_typing_template.py`: 10 đạt, 3 skip.
- Frontend: vitest cho `entities/flashcard`, `features/template-library`, `features/study`: 537 đạt, 4 skip. `tsc -b` và `oxlint` sạch.
- Trình duyệt (Flask 4799 và Vite 5183 tạm, tài khoản thử, MySQL local): iframe của màn học giữ `<input>` và script. Chạy chính tài liệu iframe đó trong một khung thử:
  - một đáp án ("mới"): gõ "  MỚI " được Đúng, "moi" bị Sai;
  - nhiều đáp án: dòng hai "Ít nhất" được Đúng, "it nhat" bị Sai, "sự   tồi tệ" được Đúng;
  - gợi ý: "••• •••••" thành "tố• •••••" sau hai lần bấm, dừng ở "tối thiể•";
  - field đáp án rỗng thì ô nhập bị ẩn; mặt sau hiện đáp án.
- Chưa kiểm bằng mắt (pane trình duyệt đang ẩn nên không chụp được) và chưa gõ thật bằng bàn phím trong iframe.

**Cách mở lại ô gõ của Flama:** bỏ comment các chỗ trong bảng trên, khôi phục `useMemo` trong `StudyPage.tsx`, rồi bỏ skip các test.
