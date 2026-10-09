# Thiết kế lại luồng thiết lập Template và Note Type

Ngày: **2026-10-09** · Trạng thái: **Đã triển khai các luồng thiết lập trên React; kiểm chứng và giới hạn ở mục 16**.

## 1. Mục tiêu và quyết định đã chốt

Mở một Template là bắt đầu thiết kế giao diện thẻ: **mặt trước, mặt sau, CSS và xem trước**. Khai báo input được mở khi cần, không chiếm vùng làm việc chính.

Mở một Note Type là thiết lập **cấu trúc dữ liệu dùng cho các note trong deck**: khai báo field, chọn kiểu nhập liệu, rồi gắn các template. Chọn một template tại đây là thiết lập **field nào cấp dữ liệu cho input nào**.

Người dùng đã xác nhận: **một Template có một bộ input gồm nhiều trường**. Không giới hạn Template chỉ có một input đơn lẻ.

Các quyết định của bản thiết kế:

- Template Detail dùng một workspace editor và preview; chỉ có ba tab nội dung `Mặt trước`, `Mặt sau`, `CSS`.
- `Inputs` mở modal quản lý input theo bố cục danh sách và chi tiết một input.
- `Dữ liệu mẫu` mở panel riêng; các ô nhập mẫu không nằm thường trực trên preview.
- Note Type dùng hai tab chính: `Trường dữ liệu` và `Templates`; mặc định mở `Trường dữ liệu`.
- Chọn một template đã gắn mở trang mapping riêng, định danh bằng **application ID**.
- Sửa HTML/CSS của template thực hiện tại Template Detail. Note Type cung cấp đường dẫn `Sửa thiết kế` về đúng Template.
- Các tác vụ thông tin, lịch sử, phân phối, lưu trữ vẫn có đường truy cập rõ ràng qua menu và panel riêng.

Phạm vi lần này là thiết kế luồng và giao diện React. Giữ contract lưu trữ hiện có cho input, field và attachment; không đề xuất một mô hình database mới.

## 2. Những vấn đề ghi nhận trước triển khai

Đây là nhận xét từ code tại thời điểm viết đặc tả, trước khi thay giao diện; không phải kết quả đo màn hình production.

| Hiện trạng quan sát được | Nguồn | Tác động tới trải nghiệm |
|---|---|---|
| Tên, danh mục, mô tả và toàn bộ form `TemplateInputSchemaEditor` nằm trước editor | [TemplateDetailPage.tsx](../../../frontend/src/features/template-library/pages/TemplateDetailPage.tsx) | Vùng thiết kế bị đẩy xuống khi có nhiều input |
| Mỗi input mở sẵn key, label, type, checkbox và nút xóa | [TemplateInputSchemaEditor.tsx](../../../frontend/src/features/template-library/components/TemplateInputSchemaEditor.tsx) | Một bộ input tạo thành nhiều form lặp lại trên màn hình |
| Toàn bộ ô dữ liệu mẫu nằm trên preview | [TemplateDetailPage.tsx](../../../frontend/src/features/template-library/pages/TemplateDetailPage.tsx) | Người dùng tiếp tục phải đi qua form trước khi thấy thẻ |
| Note Type Detail có trình sửa HTML/CSS và selector template; phía dưới có thêm panel applications | [NoteTypeDetailPage.tsx](../../../frontend/src/features/note-types/pages/NoteTypeDetailPage.tsx) | Có hai cách tiếp cận template trên cùng màn hình, khó phân biệt thiết kế và sử dụng |
| Link tên template trong panel mở Template Detail; sửa mapping phải bấm nút riêng | [TemplateApplicationsPanel.tsx](../../../frontend/src/features/template-library/components/TemplateApplicationsPanel.tsx) | Bấm template ở Note Type chưa dẫn ngay tới việc cấu hình mapping |
| Field đã có trang riêng, với danh sách và form của field được chọn | [NoteTypeFieldsPage.tsx](../../../frontend/src/features/note-types/pages/NoteTypeFieldsPage.tsx) | Có thể kế thừa cấu trúc tốt này và đưa về một shell Note Type thống nhất |

Contract nền đã hỗ trợ template độc lập, `input_schema`, mapping theo field ID và nhiều lần gắn cùng template. Xem [contract library/attachments](../../architecture/template-library-attachments-contract-2026-10-07.md); các quy tắc dùng trong thiết kế này được kiểm tra lại tại [template_library_service.py](../../../app/services/template_library_service.py), [validator](../../../app/validators/template_library.py), [Template](../../../models/template.py), [FieldDef](../../../models/field_def.py) và [StudyApplication](../../../models/study_application.py).

## 3. Phân biệt Input, Field và Mapping

| Khái niệm | Trả lời câu hỏi | Thuộc về | Ví dụ |
|---|---|---|---|
| **Input của Template** | Thiết kế thẻ cần nhận những dữ liệu gì? | Template, qua `input_schema` | `Word`, `Meaning`, `Audio` |
| **Field của Note Type** | Một note có những trường nào và nhập dữ liệu theo kiểu gì? | Note Type, qua `FieldDef` | `Từ vựng`, `Nghĩa`, `Phát âm` |
| **Mapping** | Với lần dùng template này, field nào cấp dữ liệu cho từng input? | Application của Template trong Note Type | `Word ← Từ vựng`, `Audio ← Phát âm` |
| **Giá trị của note** | Nội dung thực tế của trường là gì? | Note | `猫`, `con mèo`, một tham chiếu âm thanh |
| **Dữ liệu mẫu** | Dùng nội dung tạm nào để kiểm tra thiết kế? | State xem trước trên giao diện | Mẫu chữ hoặc media minh họa; không ghi vào Note |

Ví dụ hoàn chỉnh:

```text
Template: Vocabulary Card
  Inputs: Word:text, Meaning:markdown, Audio:audio
  Mặt trước: hiển thị {{Word}}
  Mặt sau: hiển thị {{Word}}, {{Meaning}}, {{Audio}}
  CSS: quy định bố cục và cách trình bày thẻ

Note Type: Từ vựng Nhật
  Fields: Từ vựng:text, Nghĩa:markdown, Phát âm:audio, Ghi chú:markdown

Lần dùng Vocabulary Card trong Từ vựng Nhật
  Word    ← Từ vựng
  Meaning ← Nghĩa
  Audio   ← Phát âm
```

`Ghi chú` có thể tồn tại mà không được template này sử dụng. Một field có thể cấp dữ liệu cho nhiều input. Cùng một template có thể được gắn nhiều lần với các mapping khác nhau.

Note Type là cấu trúc dùng cho các note, không tạo một bộ field khác chỉ vì thêm template. Mapping cũng không tạo hoặc sao chép field. Kiểu mà Template yêu cầu là kiểu nhận dữ liệu; cách nhập và ý nghĩa dữ liệu thuộc Note Type.

## 4. Điều hướng và các màn hình

Các route ghi **đề xuất** dưới đây chưa tồn tại trong router hiện tại.

| Vị trí | Route | Nội dung mặc định |
|---|---|---|
| Thư viện Template | `/card-templates` — hiện có | Tìm, chọn, tạo template |
| Template Detail | `/card-templates/:id` — hiện có | Editor mặt trước/mặt sau/CSS và preview |
| Quản lý input | Modal tại Template Detail | Danh sách input, form của input đang chọn |
| Note Type Detail | `/flashcards/note-types/:id` — hiện có, đổi bố cục | Tab `Trường dữ liệu` |
| Field | `/flashcards/note-types/:id/fields` — hiện có | Cùng shell, tab `Trường dữ liệu`; tương thích link cũ |
| Templates của Note Type | `/flashcards/note-types/:id/templates` — **đề xuất** | Các lần gắn template và trạng thái mapping |
| Mapping một template | `/flashcards/note-types/:id/templates/:applicationId` — **đề xuất** | Field → input cho đúng lần gắn |

Các alias `/note-types/:id` và `/note-types/:id/fields` đang có trong [App.tsx](../../../frontend/src/App.tsx) tiếp tục hoạt động; có thể điều hướng về shell canonical. Back từ mapping trở lại tab `Templates`; Back từ Template được mở qua `Sửa thiết kế` trở lại đúng application bằng ngữ cảnh điều hướng nội bộ.

### Hai hành trình chính

**Người thiết kế template:** Thư viện → Tạo hoặc chọn Template → Thiết kế mặt trước/mặt sau/CSS → mở `Inputs` khi cần → kiểm tra preview → `Lưu thay đổi`.

**Người thiết lập dữ liệu:** Tạo hoặc chọn Note Type → khai báo field → tab `Templates` → `Gắn template` → chọn Template → mapping → lưu → trở lại danh sách.

Người có template sẵn có thể gắn trước khi khai báo đủ field và để các input chưa ánh xạ. Giao diện hiển thị trạng thái cần bổ sung, không áp đặt thứ tự thao tác cứng.

## 5. Template Detail — workspace thiết kế thẻ

### 5.1 Bố cục desktop

Wireframe mô tả vùng chức năng, không ấn định màu hoặc kích thước từng pixel:

```text
Templates / Vocabulary Card
Vocabulary Card                 Chưa lưu  [Lưu thay đổi] [...]

[Inputs · 3] [Đang dùng ở 2 Note Type]

┌──────────────────────────────────┬──────────────────────────────┐
│ Mặt trước | Mặt sau | CSS         │ Xem trước   [Dữ liệu mẫu]   │
│ [Chèn input ▾]                   │ [Mặt trước] [Mặt sau]       │
│                                  │                              │
│          VÙNG SOẠN THẢO           │         GIAO DIỆN THẺ        │
│                                  │                              │
│                                  │                              │
└──────────────────────────────────┴──────────────────────────────┘
```

- Dùng chiều ngang container hiện có; editor khoảng 55%, preview khoảng 45% trên màn hình rộng.
- Workspace xuất hiện ngay dưới header và toolbar gọn. Không có form thông tin, form input hay panel phân phối mở sẵn trước nó.
- `Mặt trước`, `Mặt sau`, `CSS` là các tab chính của editor, không bị trộn với cấu hình dữ liệu.
- Đổi tab editor sang mặt trước/mặt sau đồng bộ mặt đang xem trước. Tab CSS giữ mặt preview gần nhất; người dùng vẫn có nút lật mặt.
- `Chèn input` mở menu có tìm kiếm, tên input và token. Không bày toàn bộ input thành nhiều hàng chip.
- Chèn token tại con trỏ trong HTML. Trong CSS, không chèn token như biến nội dung; tắt hành động này hoặc thay bằng lời nhắc ngắn.
- Preview dùng renderer hiện có; lỗi compile hiển thị trong khu vực preview mà vẫn giữ editor và bản nháp.

### 5.2 Thứ tự ưu tiên hành động

| Mức độ | Hành động |
|---|---|
| Chính, luôn thấy | `Lưu thay đổi` |
| Liên quan trực tiếp thiết kế | `Inputs · n`, `Chèn input`, `Dữ liệu mẫu`, lật mặt preview |
| Truy cập khi cần | `Thông tin template`, `Gắn vào Note Type`, `Lịch sử phiên bản`, `Nơi đang sử dụng`, `Phân phối / cập nhật`, `Lưu trữ` trong menu `...` hoặc panel tương ứng |

Header hiển thị tên dạng văn bản. `Thông tin template` mở form tên, mô tả, danh mục; đóng form không làm mất vị trí hoặc nội dung editor.

`Đang dùng ở n Note Type` mở danh sách usage. Chọn một usage dẫn tới trang mapping bằng `application_id`; không đưa `occurrence_key` kỹ thuật thành nội dung nổi bật.

Template đã lưu trữ có nhãn rõ và hành động `Bỏ lưu trữ`. Tiếp tục giữ quyền sửa và hành vi archive hiện có; archive chặn việc gắn mới, không biến các application đang dùng thành đã gỡ.

### 5.3 Tạo Template mới

Modal tạo ban đầu chỉ cần tên; mô tả là tùy chọn. Tạo xong mở workspace. Có thể giữ mẫu khởi tạo `Front` và `Back` hiện có để người mới thấy ngay một thẻ hoạt động; đây là input minh họa có thể chỉnh trong modal, không phải giới hạn hai input.

Không bắt đi qua một wizard cấu hình dài trước khi được thiết kế thẻ. Template tĩnh không có input vẫn có thể được thiết kế.

## 6. Modal `Inputs` — quản lý bộ input gọn gàng

### 6.1 Bố cục

```text
Inputs của Vocabulary Card                               [Đóng]
Khai báo dữ liệu mà thiết kế thẻ cần nhận.

┌──────────────────────┬────────────────────────────────────────┐
│ [Tìm input...]       │ Input đang chọn: Word                  │
│ Word        Văn bản  │ Tên hiển thị   [Từ vựng             ]  │
│ Meaning     Markdown│ Kiểu dữ liệu   [Văn bản            ▾]  │
│ Audio       Âm thanh│ [ ] Khuyến nghị ánh xạ                  │
│                      │                                        │
│ [+ Thêm input]       │ Nâng cao ▾  Mã input: Word             │
│                      │ Token: {{Word}}         [Sao chép]     │
│                      │ Dùng ở: Mặt trước, Mặt sau              │
│                      │                               [Xóa]    │
└──────────────────────┴────────────────────────────────────────┘
                                     [Hủy] [Áp dụng vào bản nháp]
```

Desktop: modal rộng khoảng 880–960px, tối đa 85dvh, danh sách trái khoảng 240–280px. Chỉ form của input được chọn được mở. Danh sách có tìm kiếm khi nhiều input; không tạo một form đầy đủ cho mỗi dòng.

Mobile: cùng chức năng trong dialog toàn màn hình. Bắt đầu bằng danh sách; chọn input chuyển sang chi tiết với nút quay lại trong dialog. Không đặt hai cột chật trên màn hình 375px.

### 6.2 Thuộc tính của input

| Thuộc tính | Cách hiển thị | Quy tắc |
|---|---|---|
| `label` | `Tên hiển thị` | Tên dễ đọc; nếu trống, hiển thị bằng key; đổi tên không đổi token |
| `key` | `Mã input` trong `Nâng cao`, kèm token chỉ đọc | Mã dùng trong HTML và mapping; unique trong template |
| `type` | `Kiểu dữ liệu` | Sáu kiểu hiện có; đây là kiểu Template nhận, không phải cấu hình editor nhập note |
| `required` | `Khuyến nghị ánh xạ` | Giữ ý nghĩa advisory hiện có; không gọi là “bắt buộc” |

Input không có cấu hình field định danh, nơi lưu dữ liệu note, nhãn form nhập note hay các thiết lập editor chi tiết. Những nội dung đó thuộc Note Type.

Khi thêm, tạo dòng draft mới và chọn ngay dòng đó. Cho phép sửa mã trước khi lưu lần đầu; có mã gợi ý hợp lệ, không ép người dùng nhập thêm một label trùng lặp. Không tự phiên âm hoặc tạo key không hợp lệ từ tên tiếng Việt.

### 6.3 Đổi mã, đổi kiểu và xóa

- **Đổi label:** được làm trực tiếp; HTML và mapping giữ nguyên.
- **Đổi key đã lưu:** trong đợt triển khai đầu, hiển thị key chỉ đọc. Không cung cấp một thao tác rename có vẻ đơn giản nhưng âm thầm làm mất mapping. Muốn thay contract thì thêm input mới, cập nhật HTML và ánh xạ lại có chủ đích. Rename an toàn đồng bộ HTML/bindings là tính năng riêng sau này.
- **Đổi type:** hiển thị lưu ý nếu template đang được sử dụng: các mapping không cùng kiểu sẽ cần chọn lại. Không tự chuyển dữ liệu field hoặc sửa các application khác.
- **Xóa input:** cho thấy token còn được dùng trên mặt nào. Nếu còn tham chiếu, yêu cầu người dùng sửa HTML trước khi áp dụng việc xóa; không tự rewrite chuỗi HTML bằng replace toàn cục. Nếu đã được sử dụng ở Note Type, nêu số nơi dùng; mapping cũ có key dư cần được làm sạch khi cấu hình application.
- Cách xác định token đang dùng phải dựa trên parser/cú pháp hiện có, kể cả conditional, filter và token media phái sinh; không dùng regex tự chế làm nguồn xác thực cuối cùng.
- Token người dùng gõ trong HTML nhưng chưa khai báo được hiển thị như một chẩn đoán có hành động `Khai báo input`. Không tự tạo một field của Note Type, không ghi đè schema đã khai báo.

Các kiểm tra tham chiếu này là yêu cầu UX mới, phải được hiện thực và kiểm thử; không coi là tính năng đã có. Backend renderer vẫn quyết định tính hợp lệ cuối cùng.

### 6.4 Bản nháp và lưu

Modal có một bản nháp riêng lấy từ draft của workspace lúc mở:

1. Sửa danh sách hoặc thuộc tính chỉ thay đổi draft của modal.
2. `Hủy` bỏ các thay đổi từ lần mở modal; giữ nguyên HTML/CSS trong workspace.
3. `Áp dụng vào bản nháp` kiểm tra schema, cập nhật draft chung, đóng modal và cập nhật menu chèn input/preview.
4. Chỉ `Lưu thay đổi` ở workspace gửi HTML, CSS, schema và metadata đã sửa lên server cùng nhau.

Sau khi áp dụng, hiển thị trạng thái `Chưa lưu` rõ ràng. Không dùng nhãn `Lưu input` cho một hành động chưa ghi server. Đóng bằng Escape hoặc click ngoài khi modal có thay đổi phải cho lựa chọn giữ sửa hoặc bỏ thay đổi; sau khi đóng trả focus về nút `Inputs`.

## 7. Dữ liệu mẫu và xem trước

`Dữ liệu mẫu` là một panel phụ mở theo yêu cầu. Không mở đồng thời panel này và modal Inputs. Khi đóng, toàn bộ không gian preview được trả về cho thẻ.

- Các ô nhập mẫu nhóm theo input; chỉ dùng tên hiển thị một lần, token ở phần phụ khi cần đối chiếu.
- Mẫu chữ dùng giá trị string; Markdown và richtext có vùng nhập đủ rộng thay vì một hàng ngắn cho mọi kiểu.
- Ảnh và âm thanh ưu tiên mẫu hệ thống an toàn hiện có. Chưa đưa upload media hoặc TTS vào bước thiết kế template này.
- `Dùng mẫu mặc định` xóa override cục bộ. Không biến dữ liệu mẫu thành giá trị mặc định của field.
- Sample chỉ phục vụ preview, không tham gia dirty state lưu template và không tạo phiên bản nội dung.
- Input chưa có sample để renderer cấp mẫu; sample `""` là lựa chọn hiển thị rỗng, không bị thay bằng mẫu tự động.
- Giữ debounce và cơ chế loại bỏ response cũ. Thay route, schema hoặc mặt preview không được để response của draft trước ghi đè kết quả mới.

Trong lần đầu, không hứa preview note thật, upload media hay đồng bộ mẫu giữa các thiết bị. Preview ở workspace giúp kiểm tra thiết kế độc lập với deck.

## 8. Note Type — nơi khai báo field dữ liệu

### 8.1 Shell và tab `Trường dữ liệu`

```text
Note Types / Từ vựng Nhật
Từ vựng Nhật                                              [...]
Cấu trúc dữ liệu cho các note của bạn.

[Trường dữ liệu · 4] [Templates · 2]

┌────────────────────────┬─────────────────────────────────────┐
│ Trường dữ liệu         │ Từ vựng                             │
│ Từ vựng       Văn bản  │ Tên trường   [Từ vựng             ] │
│ Nghĩa         Markdown │ Kiểu dữ liệu [Văn bản            ▾] │
│ Phát âm       Âm thanh │ [x] Bắt buộc nhập                    │
│ Ghi chú       Markdown │ [x] Trường định danh chính           │
│                        │                                     │
│ [+ Thêm trường]        │ Cách nhập liệu                      │
│                        │ ┌─────────────────────────────────┐ │
│                        │ │ Xem thử ô nhập và dữ liệu mẫu   │ │
│                        │ └─────────────────────────────────┘ │
│                        │                                     │
│                        │ Dùng bởi: Vocabulary Card, Reverse  │
│                        │ [Xóa trường]          [Lưu trường]  │
└────────────────────────┴─────────────────────────────────────┘
```

Kế thừa cách chọn một field để sửa từ trang Fields hiện tại, đưa vào shell có hai tab. Đây là trang làm việc lâu dài cho field nên dùng page, không nhồi toàn bộ cấu hình vào modal.

- Danh sách cho biết tên, kiểu, trạng thái định danh; có tìm kiếm khi nhiều trường.
- Sắp thứ tự bằng kéo thả và nút lên/xuống hỗ trợ bàn phím/mobile, kế thừa flow hiện có.
- Mỗi lần chỉ hiển thị form của field được chọn. `Thêm trường` mở form trong cột chi tiết.
- `Bắt buộc nhập` là thuộc tính field, khác với `Khuyến nghị ánh xạ` của input.
- Trường định danh chính giữ quy tắc hiện có: kiểu `text`, required, không cho xóa khi đang là định danh.
- `Cách nhập liệu` là preview của editor dùng khi tạo/sửa note, không phải preview mặt trước/mặt sau của card.
- Giá trị gõ thử tại đây là state cục bộ, không ghi vào note và không được mô tả là default của field.

Trên mobile, chọn một field mở phần chi tiết trong cùng page với nút về danh sách. Nút lưu nằm cuối form, không cần cuộn qua danh sách của tất cả field.

### 8.2 Chi tiết sáu kiểu dữ liệu

Sáu kiểu dưới đây đã tồn tại trong `FieldDef`. Phần xem thử editor là yêu cầu giao diện của thiết kế mới; không mặc định mọi editor hiện tại đã đáp ứng đầy đủ.

| Kiểu | Tên trên UI | Xem thử cách nhập | Gợi ý ngắn cho người dùng |
|---|---|---|---|
| `text` | Văn bản | Ô nhập văn bản thuần; xem mẫu một dòng hoặc nhiều dòng theo editor hiện hành | Dùng cho từ, cách đọc hoặc nội dung không cần định dạng |
| `richtext` | Văn bản có định dạng | Editor với các thao tác định dạng mà editor note hiện có hỗ trợ, kèm preview | Dùng khi muốn nhập nội dung có định dạng trực tiếp |
| `markdown` | Markdown | Vùng nhập Markdown và chuyển sang xem kết quả | Dùng cho giải thích, ví dụ và nội dung định dạng bằng cú pháp |
| `image` | Hình ảnh | Trạng thái chọn/thay ảnh, thumbnail mẫu và trạng thái rỗng | Field lưu tham chiếu media theo cơ chế hiện có |
| `audio` | Âm thanh | Trạng thái chọn/thay audio, phát thử mẫu và trạng thái rỗng | Field lưu tham chiếu audio; cấu hình tạo TTS vẫn thuộc luồng Audio |
| `diagram` | Sơ đồ | Editor và preview tương thích định dạng diagram hiện có | Giữ codec/renderer hiện có; không tự định nghĩa thêm định dạng lưu |

Mỗi kiểu có ví dụ và empty state đúng loại. Không dùng cùng một `Input` text ngắn để đại diện cho toàn bộ sáu kiểu.

Các thuộc tính persisted của field trong đợt đầu vẫn là `name`, `field_type`, `required`, `identity_role`, `position`. Các cấu hình như placeholder riêng, help text, toolbar tùy biến, giới hạn ký tự, MIME riêng, nhiều file hay default value **chưa có trong model/API field hiện hành**; không hiển thị như cài đặt có thể lưu. Nếu cần mở rộng sau này, phải có đặc tả persistence riêng.

### 8.3 Rename, đổi kiểu và xóa field

- Rename đi qua flow field hiện có; mapping tiếp tục dùng field ID, không sửa token Template theo tên field mới.
- Đổi kiểu hiển thị nơi đang mapping tới field; mapping khác kiểu phải được đánh dấu cần sửa. Không tự chuyển đổi text/richtext/markdown cho nhau.
- Xóa field phải giữ hành vi kiểm tra, cảnh báo và ràng buộc backend hiện có. Không tự chuyển binding sang field khác cùng tên.
- Danh sách `Dùng bởi` được tính từ application bindings đã đọc, không từ việc tìm tên field trong HTML.
- Lưu một field, reorder hoặc chuyển tab đều phải làm mới các query field/application liên quan; giữ draft chưa lưu khi query refetch.

Thông tin số note bị ảnh hưởng chỉ hiển thị nếu API cung cấp dữ liệu đúng phạm vi. Không suy ra số liệu từ field count hoặc template count.

## 9. Tab `Templates` trong Note Type

### 9.1 Danh sách các lần gắn

```text
Từ vựng Nhật
[Trường dữ liệu · 4] [Templates · 2]

Templates                                         [+ Gắn template]

┌────────────────────────────────────────────────────────────────┐
│ Vocabulary Card                         Đã ánh xạ 3/3 inputs    │
│ Thiết kế: Vocabulary Card               [Thiết lập mapping →]  │
│                                                         [...]  │
├────────────────────────────────────────────────────────────────┤
│ Reverse Vocabulary                      Cần ánh xạ · 1 input   │
│ Thiết kế: Vocabulary Card               [Thiết lập mapping →]  │
│                                                         [...]  │
└────────────────────────────────────────────────────────────────┘
                                             [Xem template đã gỡ]
```

- Bấm tên, vùng link chính hoặc `Thiết lập mapping` đều mở trang mapping của application đó.
- Tên dòng ưu tiên `display_name`, tên thiết kế gốc ở dòng phụ; hai application dùng chung một Template vẫn phân biệt được.
- Không có editor HTML/CSS trên tab này. Hành động `Sửa thiết kế` nằm trong menu dòng hoặc trên trang mapping.
- Các thao tác đổi tên lần dùng, đặt mặc định, gỡ và gắn lại giữ contract application hiện có. Chỉ đưa thao tác lên UI khi có flow mutation đúng tương ứng.
- Số input đã map tính trên schema hiện tại và target còn hợp lệ, không tính đơn thuần số key của `input_bindings`.
- Các application RETIRED nằm trong phần `Đã gỡ` đóng mặc định; `Gắn lại` dùng lại đúng application/occurrence.

Trạng thái chính: `Đã ánh xạ x/y inputs`, `Còn n input để trống`, hoặc `Cần sửa mapping`. Mapping được khuyến nghị nhưng chưa có target có thể dùng màu chú ý; input tùy chọn để trống dùng thông báo trung tính. Không gọi mọi application ACTIVE là “sẵn sàng” nếu binding đã stale.

### 9.2 Gắn Template

`Gắn template` mở bộ chọn trong thư viện của người dùng: tìm theo tên, xem tên/nhóm/số input, chọn template rồi sang bước mapping trong cùng dialog. Note Type đã biết từ ngữ cảnh nên không hỏi chọn lại Note Type.

- Tái sử dụng API và quy tắc của `ApplyTemplateWizard`; không tạo một cơ chế copy HTML khác.
- Gợi ý mapping khi **key trùng tên field và cùng type**, như helper hiện có; người dùng thấy và sửa được trước khi lưu.
- Có thể để trống input và lưu. Không tự tạo field chỉ vì không có target cùng tên.
- Nếu một template đã gắn, mặc định cung cấp `Mở lần dùng hiện có`; người dùng chủ động chọn `Gắn thêm lần nữa` để tạo occurrence khác.
- `occurrence_key` là chi tiết kỹ thuật, tạo mã hợp lệ và unique khi thêm lần dùng; người dùng đặt `Tên lần dùng` để phân biệt.
- Archive không xuất hiện như lựa chọn gắn mới. Xử lý `APPLICATION_EXISTS` bằng thông báo và link tới lần dùng có sẵn, không âm thầm tạo duplicate.

`Gắn và lưu mapping` là một POST atomic cho application mới. Thành công điều hướng tới trang mapping của ID server trả về. Hủy dialog chưa submit không để lại application rỗng.

## 10. Trang mapping — field cấp dữ liệu cho input

### 10.1 Bố cục

```text
Từ vựng Nhật / Templates / Vocabulary Card
Thiết lập mapping                      [Sửa thiết kế ↗] [Lưu mapping]
Chọn trường dữ liệu cấp nội dung cho từng input của template.

┌───────────────────────────────────────┬─────────────────────────┐
│ Input của template    Trường dữ liệu  │ Xem trước               │
│                                       │ Dữ liệu minh họa        │
│ Từ hiển thị · text                    │ [Mặt trước] [Mặt sau]   │
│ {{Word}}      ← [Từ vựng          ▾]   │                         │
│                                       │       GIAO DIỆN THẺ      │
│ Nghĩa · markdown                      │                         │
│ {{Meaning}}   ← [Nghĩa             ▾] │                         │
│                                       │                         │
│ Âm thanh · audio                      │                         │
│ {{Audio}}     ← [Phát âm           ▾] │                         │
└───────────────────────────────────────┴─────────────────────────┘
```

UI đặt input làm hàng vì cần kiểm tra mọi đầu vào mà template nhận; mũi tên thể hiện dữ liệu đi từ field sang input. Dùng tên dễ đọc làm chính, token/kiểu làm phụ; không mở các form label/key/type tại đây.

Tên lần dùng có thể sửa trong phần thông tin gọn. Template input chỉ đọc ở trang này. `Sửa thiết kế` mở đúng `template_id`; trang mapping giữ đúng `applicationId` để quay lại.

### 10.2 Quy tắc chọn field

- Combo box hiển thị field thuộc đúng Note Type, có tìm kiếm theo tên.
- Ưu tiên các target cùng kiểu; field khác kiểu được ẩn hoặc disabled trong nhóm có giải thích `Khác kiểu dữ liệu`.
- `text`, `richtext`, `markdown` là ba kiểu khác nhau theo validator hiện có; không coi chúng là tương thích ngầm.
- Mỗi input có lựa chọn `Để trống`. Input chưa map render rỗng, kể cả khi được khuyến nghị.
- Một field có thể dùng cho nhiều input; không loại khỏi danh sách sau khi đã được chọn ở hàng khác.
- Mapping lưu bằng field ID. Đổi label/key của input không được suy đoán thành đổi tên field.
- Field đã xóa hoặc sai phạm vi hiển thị giá trị stale và lời nhắc chọn lại; không âm thầm xóa để tạo cảm giác mapping hợp lệ.
- Binding có key không còn trong schema xuất hiện trong mục `Mapping cũ cần xử lý`, có thao tác xóa binding dư trước khi lưu.
- Field thiếu có đường dẫn `Quản lý trường dữ liệu` tới tab Fields. Trong đợt đầu không mở modal tạo field lồng trong mapping.

`Lưu mapping` bị chặn khi binding sai kiểu, ngoài scope hoặc chứa key input không tồn tại. Unbound là warning, không chặn lưu. Thông báo server gắn đúng hàng nếu có `field`; draft được giữ khi request thất bại.

### 10.3 Preview mapping không cần ghi trước

Preview hiển thị nhãn **Dữ liệu minh họa**. Không phải nội dung một note thật và không tạo card/application để thử.

Có thể dùng endpoint library preview hiện có:

1. Dùng schema và source đã lưu của Template được gắn.
2. Giữ mẫu nhập thử của field trong state cục bộ, keyed theo `FieldDef.id`.
3. Chuyển giá trị mẫu field đã chọn thành `sample_values[input_key]`.
4. Input unbound hoặc binding không hợp lệ gửi string rỗng `""`; không omit để tránh renderer tự dựng mẫu cho một input thực tế đang trống.
5. Với input đã map nhưng chưa có mẫu tùy chỉnh, có thể dùng mẫu renderer hiện có. Media dùng mẫu hệ thống, chưa tải media riêng của note.
6. Gửi `POST /api/card-templates/:templateId/preview`, chỉ dùng các thuộc tính endpoint này chấp nhận; không gửi `note_type_id`, `input_bindings` hoặc `field_defs`.

Như vậy thay dropdown mapping cập nhật preview mà không PATCH server. Chỉ backend compile/render; client chỉ chuyển mẫu và dựng controls, không render HTML template vào DOM trực tiếp.

Preview với note thật, bao gồm media riêng và overlay, là phần mở rộng cần contract backend riêng. Không gắn chức năng này vào endpoint preview hiện có bằng payload tự phát.

### 10.4 Rời trang và cạnh tranh cập nhật

Trang mapping có draft riêng theo application ID. Chuyển sang application khác hoặc rời trang khi dirty cần lựa chọn lưu, bỏ thay đổi hoặc ở lại. Link `Quản lý trường dữ liệu` và `Sửa thiết kế` cũng tuân theo quy tắc này.

Khi refetch phát hiện schema/field thay đổi, giữ lựa chọn draft và chạy validation lại. Nếu template thay đổi type/key, hiển thị hàng cần sửa; không lấy binding cũ áp vào schema mới một cách âm thầm.

API PATCH application hiện tại chưa có optimistic revision trong payload. Đợt UI đầu không được hứa giải quyết ghi đồng thời giữa hai tab; đọc lại dữ liệu/validate trước khi lưu chỉ giảm sai lệch, không loại trừ race. Nếu cần bảo đảm chống ghi đè mapping đồng thời, thiết kế bổ sung revision riêng ở backend.

## 11. Quy tắc lưu, phiên bản và ảnh hưởng dùng chung

| Thao tác | Ghi gì | Phạm vi ảnh hưởng |
|---|---|---|
| Áp dụng input modal | Draft frontend | Workspace đang mở |
| Lưu thiết kế Template | HTML trước/sau, CSS, input schema và metadata draft | Template và các nơi đang dùng source đó, theo contract hiện có |
| Nhập dữ liệu mẫu | State preview | Không đổi dữ liệu note, mapping hoặc content version |
| Lưu field | FieldDef qua API field hiện có | Cấu trúc dữ liệu Note Type, các note và mapping liên quan theo service hiện hành |
| Lưu mapping | `input_bindings` và thuộc tính application thực sự đã sửa | Đúng application đang chọn |
| Gỡ Template khỏi Note Type | RETIRED application | Giữ lịch sử học và dữ liệu theo hành vi retire hiện có |

Template save tiếp tục gửi `expected_current_version_id` lấy từ baseline, kể cả null. Khi gặp `TEMPLATE_VERSION_STALE`, giữ draft, thông báo có thay đổi mới và cho xem/tải bản server có chủ đích; không tự retry bằng head mới.

Trước khi lưu thay đổi source/schema của template đang được sử dụng, hiển thị thông tin gọn: `Thay đổi thiết kế sẽ áp dụng cho n lần dùng trong m Note Type của bạn.` Số liệu lấy từ usage đã đọc; không nói mọi phiên học đang mở sẽ lập tức đổi vì session freeze là contract riêng.

Metadata rename không mặc định tạo content version; thay HTML/CSS/schema đi qua version service hiện có. Restore phải thay source và nạp lại detail/schema theo đúng contract, có xử lý draft chưa lưu.

Các panel phân phối/cập nhật khi thay source cũng phải bảo vệ draft giống restore. Đưa panel vào menu không làm mất quy tắc entitlement, update/conflict/reset hoặc hạn chế sao chép lại market copy.

Installed Note Type và deck overlay tiếp tục đi qua quyền và API hiện có. Giao diện không sửa source note của tác giả hay tạo full-copy clone để đơn giản hóa mapping.

## 12. Phong cách thị giác, responsive và accessibility

Đây là redesign chủ đích của hai luồng này; có thể đổi cách chia vùng và thứ tự nội dung. Tiếp tục dùng màu thương hiệu, typography, radius và token của [index.css](../../../frontend/src/index.css), cùng primitives đang có. Không mở rộng redesign sang các màn học, browse hoặc audio.

- Nền workspace trung tính, một cấp card cho editor và preview; tránh card lồng card cho từng input trên màn chính.
- Một hành động primary cho mỗi ngữ cảnh: `Lưu thay đổi`, `Lưu trường` hoặc `Lưu mapping`.
- Tên trang khoảng 24–28px, tiêu đề vùng 16–18px, form 14px, thông tin phụ 12px; dùng scale hiện có để thống nhất.
- Toolbar gọn, cách vùng lớn khoảng 16–24px; input/modal dùng spacing 12–16px. Nút quan trọng có vùng chạm đủ lớn trên mobile.
- Status có cả chữ và màu; dùng màu cảnh báo theo ý nghĩa, không biến input optional chưa map thành lỗi đỏ.
- Desktop từ breakpoint `lg` đặt editor/preview cạnh nhau. Mobile dùng tab `Soạn thảo` / `Xem trước` cho workspace; bên trong `Soạn thảo` vẫn có mặt trước/mặt sau/CSS.
- Header và các nút không gây cuộn ngang ở 375px. Modal không có cuộn trang nền; footer và nút đóng luôn truy cập được.
- Note Type Fields trên tablet/desktop dùng danh sách và chi tiết; mapping trên mobile xếp form trước, preview ở tab phụ hoặc bên dưới.
- Dùng Dialog/Tabs/Select/Button của hệ thống; focus trap, tên truy cập được, trả focus đúng nút mở và trạng thái loading có thông báo.
- Các hành động icon có tên accessible. Lỗi gắn `aria-describedby`; reorder có nút thay thế kéo thả.
- Escape đóng panel khi không có thay đổi cần xử lý; khi đang submit, giữ quy tắc khóa thao tác nhất quán.
- Kiểm tra light/dark. CSS thẻ của người dùng vẫn thuộc sandbox, không làm thay đổi giao diện cấu hình bên ngoài.

## 13. Ánh xạ triển khai vào code hiện có

### 13.1 Các nơi tái sử dụng

| Nơi hiện có | Hướng sử dụng |
|---|---|
| `features/template-library/pages/TemplateDetailPage.tsx` | Chuyển về workspace; bỏ form schema/sample/metadata mở thường trực |
| `features/template-library/model/useTemplateLibraryEditor.ts` | Giữ owner của draft/source/schema/save/preview; bổ sung điều phối modal draft |
| `features/template-library/components/TemplateInputSchemaEditor.tsx` | Đổi thành danh sách + chi tiết một input trong modal |
| `entities/card-template/ui/TemplateCodeEditor.tsx` | Giữ front/back/css; đổi toolbar chèn token sang menu, không lấy field Note Type làm token Template |
| `features/note-types/pages/NoteTypeDetailPage.tsx` | Shell Fields/Templates, bỏ editor thiết kế lặp tại đây |
| `features/note-types/pages/NoteTypeFieldsPage.tsx` và `hooks/useNoteTypeFields.ts` | Kế thừa field CRUD/reorder; tích hợp shell và draft guard |
| `features/template-library/components/TemplateApplicationsPanel.tsx` | Danh sách occurrences; tên/link chính mở mapping, action thiết kế tách riêng |
| `features/template-library/components/ApplyTemplateWizard.tsx` | Giữ attach flow, bỏ bước chọn Note Type khi đã có context |
| `features/template-library/components/FieldMappingEditor.tsx` và `lib/fieldMapping.ts` | Giữ exact type validation và ID binding; điều chỉnh presentation theo bảng mapping |
| `features/template-versions/ui/TemplateVersionHistorySheet.tsx` | Giữ history/restore; truy cập qua menu Template |
| `features/template-distribution/` | Giữ phân phối/cập nhật; panel mở khi cần |
| `src/App.tsx` | Thêm route tab Templates/mapping, giữ aliases và deep-link cũ |

Các tên component/hook dưới đây là **đề xuất**, không phải export đã tồn tại:

- `TemplateInputsDialog`, `TemplateSampleDataPanel`: UI phụ của Template workspace.
- `NoteTypeSetupShell`, `NoteTypeTemplatesPage`, `NoteTypeTemplateMappingPage`: composition cấp page.
- `useTemplateMappingDraft`: quản lý draft theo application, lỗi, submit và preview minh họa.
- `FieldEditorPreview`: xem thử cách nhập dữ liệu cho từng field type.

Tách API/state khỏi UI. Shared mapping controls và helper có thể đặt trong `entities/card-template` nếu được dùng bởi nhiều feature; khi chuyển, thay import và giữ test hành vi. Không để hook hoặc component sâu của note-types import ngược feature template-library. Trong giai đoạn chuyển tiếp, page composition có thể dùng public export như ranh giới hiện có.

`NoteTypeLivePreview` hiện nằm trong feature note-types. Nếu cần tái sử dụng sâu hơn, tách wrapper preview dùng chung về entity phù hợp dựa trên sandbox renderer; không copy renderer hay đưa study session logic vào workspace.

Không gọi `create_app()` hoặc entry point có startup mutation chỉ để kiểm tra tài liệu hoặc dựng mockup. Đợt tài liệu này không thay application code, model hay migration.

### 13.2 API hiện có đủ cho phạm vi đầu

Tất cả path sau có prefix `/api`:

| Chức năng | Endpoint hiện có |
|---|---|
| Đọc/lưu Template | `GET`, `PATCH /card-templates/:id` |
| Preview source hoặc sample | `POST /card-templates/:id/preview` |
| Danh sách lần gắn | `GET /note-types/:id/template-applications` |
| Gắn và mapping ban đầu | `POST /note-types/:id/template-applications` |
| Lưu mapping lần gắn | `PATCH /note-types/:id/template-applications/:applicationId` |
| Gỡ lần gắn | `DELETE /note-types/:id/template-applications/:applicationId` |
| Đọc/tạo field | `GET`, `POST /note-types/:id/fields` |
| Sửa/xóa field | `PATCH`, `DELETE /note-types/:id/fields/:fieldId` |

Library detail có usage summary; mapping phải lấy từ applications API, không dựng từ summary hoặc legacy `Template.note_type_id`. Không có API GET một application riêng trong contract hiện tại: route mapping lấy danh sách theo Note Type rồi chọn đúng application ID; ID không thuộc danh sách phải báo không tìm thấy.

Nếu một phần UI cần thông tin chưa có trong response, tính từ dữ liệu đã có khi đúng nghĩa hoặc ghi nhận phần mở rộng contract trước. Không thêm thuộc tính payload chỉ để giao diện trông đầy đủ.

## 14. Thứ tự triển khai đề xuất

| Bước | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| 1 | Template workspace, modal Inputs, panel sample, metadata/menu | Editor và preview xuất hiện ngay; modal cancel/apply/save rõ ràng |
| 2 | Note Type shell và Fields | Hai tab thống nhất, field CRUD/reorder/identity giữ hành vi; xem thử editor đúng kiểu |
| 3 | Danh sách Templates và route mapping | Bấm mỗi application mở đúng mapping; không còn editor thiết kế trùng trên Note Type |
| 4 | Gắn mới, gắn thêm lần nữa, gỡ/gắn lại và đường quay về | Mọi thao tác dùng đúng application ID, giữ occurrence và lịch sử |
| 5 | Cập nhật hướng dẫn/tour/i18n và kiểm tra UI | Hướng dẫn phản ánh flow mới; light/dark, desktop/mobile và deep-link hoạt động |

Đây là thứ tự triển khai đã áp dụng. Những phần backend tách Template/Note Type đã hoàn tất được giữ theo [tracker template-features](../../task/template-features/README.md).

Các phần mở rộng ngoài đợt đầu: tùy biến persisted editor cho field, preview note thật/overlay, rename key có migration bindings, bảo đảm chống ghi đè mapping đồng thời. Chúng không chặn việc cải thiện bố cục và luồng chính này.

## 15. Tiêu chí nghiệm thu và kiểm chứng khi triển khai

### Trải nghiệm chính

- [x] Template Detail mở ra thấy ngay editor và preview; không có danh sách form input hoặc sample mở sẵn phía trên.
- [x] Template có 20 inputs vẫn giữ cùng chiều cao toolbar; danh sách dài nằm trong modal/menu có tìm kiếm.
- [x] Modal chỉ sửa một input tại một thời điểm; hủy không làm mất HTML/CSS; áp dụng chỉ làm dirty draft; global save mới ghi server.
- [x] Note Type có hai tab rõ ràng; field được gọi là `Trường dữ liệu`, template schema được gọi là `Inputs`.
- [x] Sáu kiểu field có xem thử/giải thích đúng loại; không trình bày cấu hình chưa persist như đã hỗ trợ.
- [x] Bấm template trong Note Type mở mapping của application đó. `Sửa thiết kế` đi tới Template Detail và có đường quay lại đúng context.
- [x] Hai applications dùng chung Template có tên, mapping và route riêng; sửa mapping A không đổi B.
- [x] Chọn field thay đổi preview minh họa trước khi lưu; unbound thực sự hiển thị rỗng.

### Hành vi cần giữ

- [x] Field rename giữ target ID; không rewrite token theo tên field; exact type validation giữ nguyên.
- [x] Input khuyến nghị chưa map không chặn lưu; target ngoài scope/sai kiểu/key dư phải xử lý đúng.
- [x] Refetch hoặc response preview cũ không ghi đè draft mới; đổi route reset đúng state.
- [x] Template stale save giữ draft và không tự retry; restore/update source xử lý dirty state trước.
- [x] Gỡ rồi gắn lại giữ application và lịch sử theo backend; archive không vô hiệu attachment ACTIVE.
- [x] Market copy và installed Note Type giữ quyền/backend contract; không sửa note nguồn hoặc tạo clone full copy.
- [x] Media và custom HTML/CSS tiếp tục render qua sanitizer, proxy và iframe sandbox hiện có.
- [x] History, share và hướng dẫn truy cập được qua vị trí mới. Distribution/update/reset: xem giới hạn sẵn có ở mục 16.

### Kiểm tra phù hợp

Khi triển khai, ưu tiên test hành vi draft/modal, route theo application ID, mapping/preview và error handling. Snapshot editor cũ thay bằng kiểm chứng mục tiêu redesign rõ ràng; không đơn thuần xóa/nới test để đổi giao diện.

Lệnh kiểm tra theo module đã có trong repo:

```powershell
python scripts/run_tests.py --module templates --frontend-only
```

Nếu sửa field API/service hoặc hành vi application, chạy thêm các backend module liên quan, bắt đầu từ phạm vi hẹp:

```powershell
python scripts/run_tests.py --module templates --backend-only
python scripts/run_tests.py --module flashcards --backend-only
```

Kiểm tra trình duyệt ở desktop và mobile 375px, light/dark, bàn phím, dialog dài và deep-link trực tiếp tới mapping. Khi chạy Chrome phải dùng profile riêng theo AGENTS.md.

## 16. Kết quả triển khai ngày 2026-10-09

### Giao diện và luồng đã hoàn thành

- Template Detail mở editor/preview ngay đầu trang. Ba tab Mặt trước/Mặt sau/CSS; menu chèn input có tìm kiếm; mobile chuyển Soạn thảo/Xem trước.
- Modal Inputs hiển thị danh sách và cấu hình một input. Hủy giữ nguyên draft chính; Áp dụng chỉ cập nhật draft. Key đã persist chỉ đọc; xóa input bị chặn khi HTML còn tham chiếu hoặc Mustache chưa parse được.
- Thông tin, dữ liệu mẫu, nơi dùng và lịch sử mở riêng. Link từ mapping sang thiết kế và quay lại giữ application ID.
- Note Type mặc định mở Fields, với cấu hình từng field, định danh chính, tìm kiếm và đổi thứ tự. Xem thử sáu kiểu dữ liệu; ảnh/audio chọn tệp cục bộ và dọn object URL; richtext/Markdown qua backend preview và sandbox.
- Tab Templates có danh sách lần gắn, mapping count, mặc định, gỡ/gắn lại và hộp thoại chọn thiết kế. Dùng cùng thiết kế thêm lần nữa tạo occurrence key nội bộ.
- Trang mapping định danh bằng application ID, có tên lần dùng, tìm field, kiểm tra cùng kiểu, sửa binding dư/lỗi và preview từ draft. Đổi tên field giữ binding theo ID; input chưa map được gửi mẫu rỗng.
- Guard bảo vệ draft khi đổi field, tab, route hoặc tải lại. Có lựa chọn lưu/bỏ/ở lại; lưu lỗi giữ draft và chặn chuyển trang. Refetch không ghi đè draft đang sửa.
- Cập nhật bản dịch en/vi, hướng dẫn thao tác và Master Prompt để phân biệt field với input.

### Kiểm chứng

- Module frontend `templates`: 451 test trong 35 file pass; ba test bổ sung cho guard và các test tích hợp bị ảnh hưởng tiếp tục pass sau chỉnh sửa cuối.
- `npm run typecheck`, production build và oxlint các file thuộc phạm vi thay đổi pass.
- Chrome dùng profile riêng, frontend Vite thật và renderer sandbox thật; API được mock bằng dữ liệu tổng hợp. Đã xem Template với 20 inputs, modal, Fields sáu kiểu, Templates có hai lần gắn cùng thiết kế, mapping, guard lưu trước khi mở thiết kế và quay lại đúng context.
- Desktop 1440px và mobile 375px không có tràn ngang ở các màn kiểm tra; kiểm tra style dark qua class `.dark`. Ảnh chụp QA nằm trong `output/playwright/` (artifact cục bộ).
- Console chỉ ghi cảnh báo CSP sẵn có của renderer (`frame-ancestors` trong meta, `navigate-to` chưa được Chrome hỗ trợ); không ghi nhận exception ứng dụng trong các luồng kiểm tra.

### Giới hạn và trạng thái sẵn có

- `features/template-distribution/index.ts` hiện là stub trả `null`, đã có trước redesign. Không thêm nút mở panel rỗng; phát hành/cập nhật/reset distribution cần feature riêng hoạt động trước khi đưa vào menu. Contract/backend liên quan không bị đổi.
- Editor mẫu của field minh họa kiểu nhập liệu; không persist bộ cấu hình editor mới hay upload tệp mẫu. Mapping dùng dữ liệu minh họa; preview note thật và media riêng chưa có contract trong đợt này.
- Không thay models, migrations, API hay startup; không kiểm thử ghi dữ liệu trên database production. PATCH mapping vẫn không có optimistic revision; đọc lại trước khi lưu không bảo đảm chống ghi đồng thời giữa hai tab.
