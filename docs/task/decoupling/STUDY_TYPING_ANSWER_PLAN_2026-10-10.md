# Kế hoạch chế độ gõ đáp án — so sánh ở frontend

> **Trạng thái: đã hoàn thành (2026-10-10).** Đã triển khai xong toàn bộ work packages T-01..T-08 trên branch `refactor/frontend-fsd-renderer-boundary`.
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

Lý do lưu chuỗi thay vì mảng JSON: các đường đọc hiện có (renderer, tìm kiếm, Connect) coi giá trị field là chuỗi. Renderer server đã giữ xuống dòng cho field text (`app/services/flashcard_renderer.py:457-462, 984`), nên field `answers` hiển thị mỗi đáp án một dòng mà không cần sửa renderer. Client renderer (`frontend/src/entities/flashcard/lib/clientRenderer.ts`) cần kiểm tra cùng hành vi khi triển khai.

**Dấu vết trong DB:**

| | Thay đổi |
|---|---|
| Schema | Thêm giá trị `answers` (7 ký tự). Cột `field_type` của `field_defs` và `deck_clone_added_field_defs` là `varchar(8)`, không có CHECK constraint (đo trên MySQL local 2026-10-10, SQLAlchemy 2.0 Enum không native). **Không cần migration.** Phải đo lại trên production bằng principal SELECT-only trước khi deploy |
| Dữ liệu | Chỉ các field người dùng chủ động chuyển |
| Khi học | Không có gì mới. `review_events` vẫn là event rating bình thường |

**Ràng buộc:**

- Field chính (`identity_role = 'primary'`) giữ kiểu `text`, giống quy tắc clone hiện có (`app/services/flashcards_share_service.py:3402-3404`). Field chính vẫn dùng làm đáp án được theo §5.
- Field media (image, audio, diagram) không chuyển được.
- Đổi kiểu trong trình sửa NoteType (`EditFieldCard`) sang `answers` phải đi qua công cụ §4, không đổi kiểu trần. Nếu đổi trần, giá trị chưa tách sẽ bị coi là một đáp án.
- Nguồn ghi khác (Connect/Yomitan, MCP, import vào field đã là `answers`) được lưu như text, không bị từ chối, để không làm hỏng luồng mining. Frontend vẫn đọc theo §5; Note chưa sạch có thể chạy lại công cụ §4.

**Nơi phải nhận kiểu mới:**

- Backend đang có khoảng 8 bản sao danh sách kiểu field: `app/routes/flashcards/__init__.py:72`, `app/services/flashcard_content_service.py:55`, `app/services/flashcards_share_service.py:52`, `app/validators/template_library.py:6`, `app/validators/mcp.py:129`, `app/services/mcp_tool_registry.py:1131`, `app/services/mcp/note_type_tools.py:111`, `app/services/connect/import_session.py:163`, cùng hai Enum trong `models/field_def.py` và `models/deck_clone_added_field_def.py`. **Gom về một hằng số dùng chung trước** rồi mới thêm `answers`, để không vá rải rác.
- Frontend: `FIELD_TYPES` ở `frontend/src/features/note-types/hooks/useNoteTypeFields.ts:24`, các chỗ rẽ nhánh theo kiểu trong `features/browse`, `entities/card-template`, `features/template-library`, `features/study/components/StudyQuickEditFields.tsx`. Import Anki (`frontend/src/lib/ankiSyncEngine.ts:165`) xử lý field `answers` như `text`.

## 4. Công cụ chuyển field sang `answers` (D-T1)

**Luồng:**

1. Người dùng chọn NoteType và field. Field chính và field media không có trong danh sách.
2. Chọn một hoặc nhiều kiểu tách (bảng dưới).
3. **Xem trước mọi Note của NoteType**, không chỉ deck đang mở, vì kiểu field thuộc NoteType. Mỗi dòng hiện giá trị cũ và danh sách mới, kèm cảnh báo: kết quả rỗng, còn thẻ HTML, dòng quá dài, đáp án trùng đã gộp, không thấy dấu tách (giữ nguyên làm một đáp án). Người dùng sửa tay từng Note nếu cần.
4. **Tải file sao lưu** giá trị cũ (bắt buộc trước khi áp dụng). Bản sao nằm ở máy người dùng, không lưu trong DB.
5. **Áp dụng trong một request.** Server ghi nguyên tử: đổi kiểu field và ghi giá trị mới cho toàn bộ Note. Server từ chối nếu field hoặc Note đã đổi so với lúc xem trước (so `updated_at` hoặc hash). Server chỉ kiểm tra hình dạng (chuỗi, mỗi dòng không rỗng), không tách lại.
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

**Deck cài từ marketplace:** ghi vào overlay (`DeckCloneFieldDefOverride.properties.field_type` và override giá trị từng Note), không sửa Note nguồn. Sau khi chuyển, chỉnh sửa của tác giả trên field đó bị override của người học che, theo đúng hành vi overlay hiện có.

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

Vì vậy chế độ gõ làm được bằng một component riêng trong `features/study`, không cần chờ tách toàn bộ Interaction host và không cần API mới. Khi triển khai cần kiểm tra hai điểm: host biết input `answers` gắn với field nào bằng cách nào (binding trong snapshot phiên), và với deck đã cài thì `field_values` có phải là giá trị sau overlay không.

**Gợi ý khác (sau, D-T2):** ví dụ mở ký tự đầu để người học thấy là katakana.

## 7. Work package

| ID | Nội dung | Phụ thuộc | Trạng thái | Kết quả |
|---|---|---|---|---|
| T-01 | Hàm `typing-compare.v1` (§5) và hàm tính ô, mở gợi ý ở frontend, kèm bộ test (NFC, hoa thường, khoảng trắng, U+3000, IME, dấu tiếng Việt, kana, grapheme) | — | Hoàn thành | Đã hoàn thành (`typingAnswer.ts`) |
| T-02 | Validator Template: nhận input kiểu `answers`, cho gắn với field `text`, thêm khóa `show_length`/`hints`; sửa tương ứng ở `frontend/src/features/template-library/lib/inputSchemaValidation.ts` | — | Hoàn thành | Đã hoàn thành (`template_library.py`, `inputSchemaValidation.ts`) |
| T-03 | Component ô gõ ở host theo §6: Enter, Đúng/Sai, gõ lại, ô ẩn, gợi ý, bỏ qua, kết quả ở mặt sau | T-01, T-02 | Hoàn thành | Đã hoàn thành (`StudyTypingAnswerPanel.tsx`, `StudyPage.tsx`) |
| T-04 | Template mẫu "Gõ đáp án" | T-02 | Hoàn thành | Đã hoàn thành (`CreateTemplateDialog.tsx`) |
| T-05 | Gom danh sách kiểu field về một hằng số (backend, frontend) | — | Hoàn thành | Đã hoàn thành (`models/field_types.py`) |
| T-06 | Thêm kiểu field `answers`: validator, MCP, Connect, overlay, `FIELD_TYPES` frontend, ô nhập chip, kiểm hiển thị cả hai renderer; chặn đổi kiểu trần; đo cột production | T-05 | Hoàn thành | Đã hoàn thành |
| T-07 | Endpoint áp dụng và hoàn tác chuyển đổi nguyên tử (NoteType sở hữu và overlay), có điều kiện tiên quyết | T-06 | Hoàn thành | Đã hoàn thành (`field_answers_conversion_service.py`) |
| T-08 | Công cụ chuyển đổi ở frontend: kiểu tách, xem trước, sửa tay, file sao lưu (§4) | T-07 | Hoàn thành | Đã hoàn thành (`FieldAnswersConversionDialog.tsx`) |

T-01..T-08 đã được triển khai và kiểm thử toàn diện trên backend và frontend.

## 8. Câu hỏi còn mở

1. Chuyển đổi NoteType có nhiều Note (§4). Đề xuất: màn xem trước hiện tóm tắt (tổng số Note, số tách được, số có cảnh báo) và chỉ liệt kê Note có cảnh báo, có phân trang; vẫn xem được toàn bộ theo trang. Áp dụng một lần cho cả NoteType trong một giao dịch, để không có trạng thái nửa chuyển nửa không. Không giới hạn số Note ở quy mô hiện tại; NoteType rất lớn mới cần chia đợt, khi đó phải thiết kế thêm.

## 9. Kiểm chứng

- `python scripts/run_tests.py --module flashcards,study` cho T-00..T-02; test overlay cho cả deck sở hữu và deck đã cài (theo `AGENTS.md`).
- Bộ test frontend của T-04 chạy cùng `npm run test:changed`.
- Luồng trình duyệt dùng profile Chrome riêng theo `AGENTS.md`.

## 10. Handoff

```text
Task ID: STUDY-TYPING-ANSWER
Primary outcome: kế hoạch chế độ gõ so sánh ở frontend; luồng Đúng/Sai/gõ lại/gợi ý/bỏ qua ở host; kiểu field answers; công cụ chuyển đổi bằng regex định sẵn; luật typing-compare.v1; quyết định D-T1..D-T8
Files changed: docs/task/decoupling/STUDY_TYPING_ANSWER_PLAN_2026-10-10.md (mới); liên kết trong README.md và P8_GENERIC_ACTION_OUTCOME_PLAN_2026-10-10.md
Runtime change: none
Tests added or updated: none (kế hoạch)
Known limitations: độ dài cột field_type mới đo trên MySQL local; chưa kiểm cách host đọc binding của input answers trong snapshot phiên, field_values sau overlay của deck đã cài, và hành vi xuống dòng của client renderer
```
