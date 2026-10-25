# Kế hoạch bổ sung khả năng thiết kế và kiểm chứng Card Template qua MCP

Ngày: 2026-10-25 (Asia/Tokyo). Trạng thái: **đề xuất để review, chưa triển khai**.

Nguồn yêu cầu: [#248 — interactive quiz authoring gaps](https://github.com/TrinhChung/Flama/issues/248), kết hợp [#116 — MCP App template preview](https://github.com/TrinhChung/Flama/issues/116). Đối chiếu source tại checkout có HEAD `d4da3c7d`; kết quả dưới đây là đọc mã, chưa phải kết quả chạy trình duyệt hoặc kiểm thử production.

## 1. Mục tiêu và quyết định đề xuất

Cho phép chat biết chính xác template đã được kiểm tra tới đâu: kiểm tra dữ liệu, render phía server, render bằng client Study, hay đã thử tương tác trên trình duyệt. Chỉ ghi hoặc đọc lại thành công qua MCP chưa đủ để kết luận trải nghiệm Study đúng.

Ưu tiên hoàn thiện luồng authoring chung: **contract + diagnostics → preview artifact theo Study → kiểm thử tương tác → UI trong chat**. Bộ trắc nghiệm là bộ dữ liệu kiểm chứng đầu tiên. Chưa có bằng chứng yêu cầu thay toàn bộ renderer hoặc bắt buộc xây một quiz engine riêng.

Phạm vi đầu không cần bảng, cột hay index mới. Giữ native JSON arrays và cơ chế mapping input → field theo application hiện tại. Việc preview không ghi note, template, version, application, tiến độ hay review.

Yêu cầu bổ sung của người dùng: editor web phải có **dữ liệu mẫu theo đúng kiểu, sửa trực quan được và cập nhật live preview**, thay vì chỉ cho nhập chuỗi. Sample là dữ liệu thử tạm của phiên chỉnh sửa, không cần lưu DB. Phần này thuộc trải nghiệm tạo template của người dùng và làm được độc lập với MCP App.

## 2. Hiện có gì, còn thiếu gì

| Thành phần | Đã xác nhận trong source | Cần bổ sung |
|---|---|---|
| MCP mutation preview | `preview_note_type_update()` phân tích field/template, ảnh hưởng dữ liệu và cấp token. `validation_errors` được khởi tạo rỗng, không có bước render trong hàm | Công bố đúng phạm vi kiểm tra; chạy phân tích template và trả diagnostic có cấu trúc |
| Web preview | Có preview cho Template Library, template gắn NoteType và raw draft; dùng `render_template_pair()` | Adapter cho MCP; kiểm tra độ khớp với đường render Study hiện tại |
| Study artifacts | `study_artifact_service.py` tạo template/content artifacts, có ABI, version, field mapping và script provenance | Xây artifact cho candidate chưa lưu bằng các hàm chuẩn bị hiện có; tránh mô phỏng version lưu DB |
| Client renderer | `entities/flashcard/lib/clientRenderer.ts` dùng mustache.js, sanitize markup rồi nối script đã được server tách riêng | Dùng chính đường này trong preview/harness; public entry gọn cho phần render nếu cần |
| HTML/CSS/script | HTML server qua Chevron; `shared_css` chỉ sanitize. Script ở client được tách khỏi nguồn HTML trước Mustache và gắn lại sau | Contract rõ cho từng context; fixture đối chiếu script có token và thời điểm script chạy |
| Sandbox | `CardRendererFrame` dùng `sandbox="allow-scripts"`; host hiện có ready, reveal, media bridge và log lỗi | Hook diagnostics từ host lên UI, timeout, giới hạn số/độ dài lỗi |
| Lỗi runtime | Sandbox đã gửi `error` và `unhandledrejection` thành `log_error`; host ghi `console.warn` | Hiển thị lỗi theo candidate/card/side; cung cấp bằng chứng cho kiểm thử |
| UI preview tái sử dụng | Có `CardPreviewPanel`, `CardDisplay`, `CardRendererFrame` ở entity flashcard | MCP App entry và adapter dữ liệu. Không dựa vào tên `NoteTypeLivePreview` cũ trong #116 |
| MCP resources | `resources/list/read` hiện phục vụ tài liệu `flama://docs/...` | Registry cho resource UI cụ thể, giữ các resource tài liệu đang hoạt động |
| MCP metadata | `McpToolDefinition` có schema, annotation, handler nhưng chưa serialize `_meta` | Metadata `_meta.ui.resourceUri`, output schema cho tool mới, read-only hint chuẩn |
| Đóng gói | Chưa thấy MCP App entry/build hoặc dependency `@modelcontextprotocol/ext-apps` trong frontend | Build HTML độc lập, host bridge SDK được khóa phiên bản và kiểm tra tương thích |
| Tài liệu | Guide có Mustache cơ bản nhưng danh sách kiểu field chưa có `array`; chưa giải thích loop/index/CSS/script đầy đủ | Cập nhật guide và resource tài liệu để chat đọc trực tiếp qua MCP |
| Sample editor | `SampleValuesSheet` nhận `Record<string, string>`; text/array dùng Input, richtext/markdown dùng Textarea, media chỉ có hint và nút để trống. Transport đã parse JSON array hợp lệ thành list | Editor đúng kiểu, sample mặc định nhìn thấy/sửa được, array native, media thử và lifecycle trong bộ nhớ |

Các điểm đọc chính:

- [MCP NoteType tools](../../app/services/mcp/note_type_tools.py), [registry](../../app/services/mcp_tool_registry.py), [resources routing](../../app/connect/mcp.py).
- [Web preview service](../../app/services/template_library_service.py), [raw/application preview](../../app/services/flashcard_content_service.py), [preview value validator](../../app/validators/template_preview.py).
- [Renderer](../../app/services/flashcard_renderer.py), [Study artifacts](../../app/services/study_artifact_service.py), [binding projection](../../app/services/template_binding_service.py).
- [Client renderer](../../frontend/src/entities/flashcard/lib/clientRenderer.ts), [preview panel](../../frontend/src/entities/flashcard/ui/CardPreviewPanel.tsx), [sandbox host](../../static/js/card_renderer_host.js).

## 3. Phân biệt kết luận và việc cần tái hiện

**Đã có bằng chứng source:** preview mutation chưa render; CSS không nội suy; server và client đi qua hai đường render khác nhau; lỗi runtime đã tới host nhưng chỉ ra console; chưa có UI resource/tool preview trong MCP hiện tại.

**Được ghi nhận trong #248, cần fixture tái hiện:** `{{#each options}}` không hoạt động; `{{@index}}` trống; `{{index}}` trả biểu diễn method Python; Study thiếu hướng dẫn số đáp án/feedback trong các lần sửa đầu.

**Chưa xác định nguyên nhân cụ thể:** JavaScript ban đầu không hoạt động vì lỗi code, nội suy token trong script, lifecycle front/back, mapping, bản artifact đang dùng hay nguyên nhân khác. Việc client tách script trước Mustache là điểm cần so sánh, chưa phải kết luận nguyên nhân của ca production. Không suy ra CSP phải được nới.

Hai quyết định dữ liệu cần giữ rõ:

- Generic `array` nhận text/safe rich-text và list lồng. `[1,3]` bị từ chối là contract hiện tại; không đổi generic array thành object/number array để xử lý riêng bộ trắc nghiệm.
- `correct_answers = ["1","3"]`, vị trí bắt đầu từ 1 là quy ước của bộ trắc nghiệm, không phải quy tắc cho mọi array trong Flama.

## 4. Các hạng mục triển khai và điều kiện hoàn thành

### T01 — Tái hiện và chốt bảng hành vi (P0)

Chuẩn bị fixture tổng hợp từ cấu trúc case #248, không lấy nội dung câu hỏi thật làm fixture mặc định. Đọc dữ liệu thật chỉ khi cần bằng chứng cụ thể và có scope truy cập phù hợp.

Chạy cùng một candidate qua server preview, artifact/client renderer và sandbox Study. Ghi nhận markup, lỗi, hành vi nhìn thấy và source hash. So sánh theo kết quả DOM/hành vi có ý nghĩa; không yêu cầu toàn bộ HTML giống từng byte.

Bao phủ sections, inverted sections, `{{.}}`, indexed access, phần tử rỗng/list lồng, token trong HTML/inline style/shared CSS/script, FrontSide và reveal. Kiểm tra script khởi tạo ở lần mở, đổi thẻ, đổi mặt và cập nhật candidate.

**Đầu ra:** bảng supported/unsupported/divergent, minimal reproduction cho mỗi khác biệt, nguyên nhân đã chứng minh hoặc trạng thái chưa tái hiện. Đây là đầu vào bắt buộc trước khi đổi semantics renderer.

### T02 — Contract và diagnostics chung (P0)

Thêm analyzer dùng chung cho preview và candidate template mutation. Đặt ở service, tách khỏi HTTP/MCP handler; tái sử dụng `template_tokens.py` và parser thực tế. Không dùng regex đơn lẻ như một compiler thứ hai.

Mỗi diagnostic có `code`, `severity`, `stage`, `source_part`, `message`, `hint`; bổ sung token/line/column khi có vị trí đáng tin cậy. Các stage tối thiểu: input, binding, template, server_render. Không gắn stage browser/runtime khi chưa chạy browser.

Các nhóm kiểm tra:

- Unsupported constructs như Handlebars-style `#each`, metadata `@index` chưa hỗ trợ; token sai hoặc section không khớp.
- Input không khai báo, binding thiếu/sai kiểu; phân biệt trường optional và mapping thực sự không hợp lệ.
- Mustache trong `shared_css`: cảnh báo context không được nội suy.
- Token trong script: mô tả hành vi đã xác minh ở T01; cảnh báo khác biệt với client Study thay vì tự chèn raw dữ liệu vào JavaScript.
- Lookup không được trả Python method/internal representation. Tái hiện trước, rồi sửa giới hạn lookup tại ranh giới renderer bằng cách vẫn bảo toàn list và sections.

Giữ `preview_note_type_update` là impact preview. Thêm kết quả validation theo stage mà không làm mất các key/token cũ. Dùng cùng analyzer tại bước ghi để template sai rõ ràng không lọt qua chỉ vì bỏ qua preview. Không cấm hàng loạt template cũ bằng luật mới trước khi có kiểm tra tương thích; warning và error phải có chính sách riêng.

**Đầu ra:** chat nhận lý do và cách sửa cụ thể; danh sách lỗi rỗng không còn ngầm được hiểu là tương tác đã chạy thành công.

### T03 — Một MCP tool preview chỉ đọc (P0)

Thêm `preview_note_type_template`, dùng cùng dịch vụ preview với editor. Giữ một tool mới trong v1; kiểm thử browser là harness riêng ở T05, chưa hứa thêm `test_card_template` chạy browser trên server.

Contract đầu vào đề xuất:

- Target là application đã gắn vào NoteType, hoặc raw candidate có `input_schema`/field definitions rõ ràng.
- Có thể ghi đè candidate `front_html`, `back_html`, `shared_css` trong bộ nhớ.
- Dữ liệu thử lấy từ `sample_values` hoặc một note có quyền đọc; hai nguồn phải được phân biệt rõ. Thiếu dữ liệu không được âm thầm thay bằng dữ liệu mẫu rồi báo pass.
- Nếu một template gắn nhiều lần, bắt buộc xác định `application_id` để chọn đúng binding/occurrence; không tự chọn application đầu tiên theo `template_id`.
- Dùng scope đọc phù hợp, kiểm tra quyền resource; không tin `user_id` gửi trong args. Preview từ installed context phải tôn trọng effective/pinned presentation và quyền đọc hiện hành.

Đầu ra gồm diagnostics, các stage đã kiểm tra, candidate hash, ABI/version của renderer, dữ liệu artifact để dựng client preview và thông tin nguồn mẫu. Có thể giữ HTML server như dữ liệu chẩn đoán, nhưng không gọi đó là kết quả browser Study.

REST preview hiện có cũng nhận artifact theo cách bổ sung tương thích; editor, MCP App và harness dùng `renderCardSide()` trên artifact trước khi đưa vào sandbox. Giữ các field HTML/payload cũ cho caller chưa chuyển đổi. Trích helper chuẩn bị candidate/projection khi cần, không tạo Note/Template/version trong DB để giả lập preview. Đây là thay đổi giúp preview dùng đúng đường client của Study, không chỉ dùng chung iframe.

Ví dụ trạng thái trả về, **chỉ là đề xuất contract mới**:

```json
{
  "schema_version": "template-preview.v1",
  "candidate_hash": "sha256:...",
  "renderer_abi": "flama-client-mustache.v2",
  "checks": {
    "input": "passed",
    "binding": "passed",
    "template": "passed",
    "server_render": "passed",
    "study_browser": "not_run",
    "interaction": "not_run"
  },
  "diagnostics": [],
  "preview": {
    "template_artifact": {},
    "content_artifact": {}
  }
}
```

Artifact thực tế phải tuân thủ schema hiện có, không dùng hai object rỗng như ví dụ tối giản. Có schema version riêng cho envelope preview; candidate hash không giả làm immutable version đã lưu. Hạn chế kích thước template/sample theo validator hiện tại và thời gian xử lý; cache phải phân biệt owner, nguồn dữ liệu, candidate, binding và ABI.

**Đầu ra:** chat preview được candidate trước khi lưu; text fallback cho biết chính xác stage đã pass và stage chưa chạy.

### T04 — Đưa diagnostics runtime lên preview (P0)

Nối `log_error` hiện có thành callback/diagnostic UI tại renderer entity. Bổ sung timeout khi frame không ready và lỗi tải renderer host. Giữ kiểm tra `event.source`, channel và instance ID; gắn candidate/card/side vào thông tin do host quản lý.

Lỗi hoặc nội dung do template gửi là dữ liệu không tin cậy, không được quyết định quyền, điều hướng hay hành động ghi. Giới hạn số bản ghi, độ dài, loại payload và tần suất; hiển thị dạng text. Cần phân biệt lỗi tải host, compile/render, lỗi script và trường hợp không thu thập được lỗi.

**Đầu ra:** lỗi script có thể nhìn thấy trong preview và được browser runner thu thập. Không tuyên bố đã thu đủ mọi `console.*` nếu chỉ có error/rejection.

**Đường trả kết quả cho GPT:** diagnostics xuất hiện trong UI không tự trở thành dữ liệu model nhìn thấy. Khi triển khai MCP App ở T06, thêm nút gửi báo cáo gồm candidate hash, mặt thẻ, thao tác đã thử, lỗi và kết quả quan sát về ngữ cảnh chat qua bridge host hỗ trợ. MCP Apps có `ui/update-model-context`; yêu cầu GPT phản hồi tiếp dùng cơ chế message/follow-up của host theo tương tác người dùng. Cập nhật context không được coi là đã tự khởi chạy một vòng sửa mới. Nội dung lỗi/quan sát là dữ liệu không tin cậy, không phải instruction cho model.

Luồng v1 là GPT tạo candidate → người dùng thao tác preview → gửi báo cáo → GPT đọc báo cáo và đề xuất bản sửa. GPT không tự đọc DOM/console hoặc tự click iframe chỉ vì preview có mặt trong chat. Test browser ở T05 là bằng chứng dev/CI; để GPT tự gọi kiểm thử trong từng cuộc chat cần thêm tool nối tới browser runner local/server, trả report qua tool result. Khả năng đó vẫn là phạm vi mở rộng có chi phí vận hành riêng, không phải tính năng đã có của UI preview.

### T05 — Kiểm thử tương tác bằng browser thật (P0)

Thêm fixture/harness dùng đúng artifact/client renderer và `CardRendererFrame` của Study. Test runner dùng Playwright hoặc browser runner hiện hữu sau khi xác minh cài đặt; chưa có wiring riêng cho case này trong source đã kiểm tra. Không coi optional dependency trong lockfile là runner đã sẵn sàng.

Runner thao tác DOM trong iframe qua công cụ browser, không cần thêm quyền truy cập DOM vào parent hoặc đổi sandbox. Thử template tổng quát với các bước và assertion cấu hình trong test; không đưa tên field `options` vào renderer chung.

Report gồm candidate hash, renderer ABI, viewport, từng thao tác/assertion, lỗi runtime và artifact screenshot khi thất bại. Chỉ đánh pass khi runner thật sự quan sát được kết quả; dữ liệu tự khai báo của template không đủ chứng minh pass.

**Đầu ra:** bộ fixture trắc nghiệm single/multi-select có bằng chứng chọn sai, chọn đúng, đổi lựa chọn, reveal và explanation. Có ít nhất một smoke test đi qua trang Study thật, không chỉ trang harness.

### T06 — MCP App UI và đóng gói (P1, theo #116)

Bổ sung `_meta` tùy chọn vào `McpToolDefinition`; tool mới dùng `_meta.ui.resourceUri` và `annotations.readOnlyHint = true`. Registry hiện dùng key `readOnly` ở nhiều tool: xác nhận client compatibility và tách việc chuẩn hóa toàn bộ tool thành thay đổi riêng nếu cần; không coi `readOnly` là tên field chuẩn MCP.

Thêm resource `ui://flama/template-preview/v1.html`, MIME `text/html;profile=mcp-app`. Resource registry chỉ đọc artifact đã build theo URI allowlist; không ánh xạ URI thành đường dẫn tùy ý. `resources/list/read` tiếp tục phục vụ tài liệu hiện có. HTML UI dùng chung là static, không nhúng dữ liệu note hoặc credential theo user vào bundle được cache.

UI v1 có front/back, sample/template context, lỗi và trạng thái kiểm chứng. Dùng `CardPreviewPanel`/`CardRendererFrame` qua public API; không nhập feature template-library hoặc study ngang tầng. Mọi script trong card vẫn chạy ở inner sandbox, không render HTML template trực tiếp vào outer app.

Phân bổ FSD dự kiến:

- Entry bootstrap: `frontend/src/app/mcp-template-preview/`.
- Composition: `frontend/src/pages/mcp-template-preview/`.
- Bridge/data lifecycle: `frontend/src/features/template-preview/`, có hooks và public API.
- UI/renderer domain dùng chung: `frontend/src/entities/flashcard/`.
- Build độc lập: `frontend/vite.mcp.config.ts`, script build và artifact được đóng gói cùng Flask/Connect.

`CardRendererFrame` hiện tải `/static/js/card_renderer_host.js`. Cần đóng gói cùng một implementation vào MCP App hoặc trích module dùng chung với wrapper tương thích cho web. Không chép thành renderer thứ hai. Các legacy imports chạm tới phải migrate đúng FSD, scope theo caller thực tế và giữ nguyên giao diện web.

Xác minh host thật có MCP Apps và cho phép nested sandbox/frame/CSP cần thiết trước khi cam kết inline preview. Host không hỗ trợ vẫn nhận kết quả text/structured diagnostics; việc fallback không được ghi thành inline-UI pass. SDK/bundler được khóa phiên bản sau khi kiểm tra Vite/React hiện có; không tạo thêm Node MCP server.

**Đầu ra:** thử thành công tool → resource → app → inner sandbox trong host mục tiêu; asset build thiếu phải báo trạng thái rõ và còn dùng được preview dữ liệu. Tách kết quả host simulator với kết quả host thật.

### T07 — Tài liệu để chat tự khám phá (P1)

Cập nhật [guide hiện có](../guides/NOTE_TYPE_TEMPLATE_GUIDE.md): array native/legacy đọc, sections + `{{.}}`, inverted sections, indexed access đã được kiểm chứng, escaping, FrontSide, HTML/CSS/script context, lifecycle và API script thực sự được hỗ trợ.

Thêm topic vào `FLAMA_DOCUMENTATION_TOPICS`, ví dụ `template-authoring` và `quiz-template`, để dùng qua `get_flama_documentation` và `flama://docs/...`; tránh thêm một tool tài liệu nếu tool hiện có đáp ứng. Resource phải có phiên bản/ngày và ví dụ được kiểm thử để hạn chế lệch với guide.

Xuất bản một recipe trắc nghiệm đã chạy browser: `question`, `options[]`, `correct_answers[]`, `explanation`. Định nghĩa rõ câu trả lời là vị trí chuỗi bắt đầu từ 1; báo lỗi đáp án trùng hoặc ngoài khoảng, không chấm khi số lựa chọn chưa đủ và quy định có được đổi lựa chọn sau chấm hay không.

Tạm dùng hành vi: đúng N lựa chọn thì hiện feedback; đổi lựa chọn sẽ tính lại; reveal hiển thị đáp án và explanation/fallback. Đây là hành vi recipe đề xuất, không đổi scheduler rating. Đảo thứ tự options phải cập nhật vị trí đáp án cùng lúc; kiểm tra range không phát hiện được mọi sai lệch ngữ nghĩa.

Validate quy tắc quiz trong recipe/fixture hoặc profile preview opt-in rõ ràng; không áp lên mọi NoteType có array. Chưa cần đổi editor array chung thành quiz editor.

**Đầu ra:** chat lấy được syntax/recipe bằng MCP; examples không cần đoán index helper hay nội suy biến vào JavaScript.

### T08 — Tích hợp, tương thích và rollout (P1)

Sau T01–T07, thử workflow hoàn chỉnh trên fixture local: đọc schema → tạo candidate → preview → kiểm tra browser → impact preview → áp dụng vào fixture → mở Study → đọc lại. Giữ token/confirmation, stale protection và ownership của mutation hiện có.

Report phải gắn candidate đã kiểm tra với candidate thực sự áp dụng. Hash trong kết quả preview không tự trở thành token authorization hay ràng buộc mutation. Nếu cần server cưỡng chế candidate-bound apply, lập thay đổi riêng cho token contract và compatibility; không tuyên bố cơ chế cũ đã làm điều đó.

Build CI tạo MCP UI artifact và container/package mang theo artifact; không báo hoàn thành chỉ vì frontend build ở máy dev. Chạy fixture non-media trước, tiếp theo media proxy/auth trong host thật. Chỉ bật metadata UI sau khi artifact và host integration sẵn sàng. Có thể rollback UI advertisement độc lập, tiếp tục dùng preview dữ liệu và tools cũ.

**Đầu ra:** evidence cho editor, MCP text-only, MCP Apps-capable host, Study và smoke ownership/pinned presentation hiện có.

### T09 — Quyết định có cần primitive quiz riêng (P2, có điều kiện)

Chỉ làm sau khi recipe và harness hoạt động. So sánh lượng script cần viết, khả năng tiếp cận, mobile/keyboard và chi phí bảo trì. Nếu vẫn cần primitive, thiết kế opt-in, có contract/version và giữ tùy biến style. Không thêm bảng, quiz type bắt buộc hay thay đổi array chung trước quyết định này.

### T10 — Dữ liệu mẫu theo kiểu, sửa trực quan, không lưu DB (P0)

Trạng thái triển khai 2026-10-25: đã có typed sample editor cho 7 kiểu, array native/list lồng, rich text trực quan/HTML, reset, lifecycle tạm và mẫu media có nội dung thật. Đã kiểm tra editor/mapping trên browser + MySQL local, typecheck và production build. Media tùy chỉnh hiện đổi qua URL; chọn tệp local trong card sandbox và preset nhóm quiz bên dưới vẫn là phần đề xuất tiếp theo, chưa triển khai. Các hạng mục MCP khác trong tài liệu chưa được coi là hoàn thành bởi thay đổi T10 này.

Áp dụng trong Template Detail và trang mapping NoteType → Template. Tạo input mới hoặc đổi kiểu sẽ có mẫu thích hợp được hiển thị thành giá trị thật để sửa; không chỉ đặt placeholder hoặc in tên input thay dữ liệu. Dùng một bộ sinh mẫu dùng chung, không suy đoán/chuyển đổi kiểu từ tên input. Template chưa có input hiển thị trạng thái hướng dẫn khai báo input.

| Kiểu | Mẫu mặc định và thao tác đề xuất |
|---|---|
| `text` | Nội dung ngắn có nghĩa, sửa bằng ô text |
| `richtext` | Mẫu có chữ đậm/nghiêng/danh sách; có thao tác định dạng và xem kết quả, source HTML ở chế độ nâng cao |
| `markdown` | Mẫu heading/list/emphasis, sửa source và xem kết quả render |
| `array` | List thực gồm các item text; sửa từng item, thêm/xóa/sắp xếp bằng UI. Chế độ nâng cao xử lý JSON/list lồng và báo lỗi ngay tại editor |
| `image` | Mẫu ảnh hệ thống hiển thị sẵn; có thể thay bằng ảnh thử cục bộ hoặc media URL hợp lệ cho preview |
| `audio` | Mẫu audio phát thử; có thể chọn tệp thử cục bộ hoặc media URL hợp lệ |
| `diagram` | Mẫu diagram được hỗ trợ hiện hành, xem và thay nguồn media phù hợp; không tự bổ sung một ngôn ngữ diagram khác |

Hành vi chung:

- Sửa sample cập nhật live preview qua debounce/cancellation đang có; response cũ không được thay kết quả mới.
- Có reset từng input, reset toàn bộ và đặt giá trị rỗng để thử điều kiện Mustache. Rỗng phải phân biệt với chưa có override; `[]`, `[""]` và chuỗi rỗng không bị gộp tùy tiện.
- Đóng/mở bảng sample giữ dữ liệu trong phiên editor. Refresh/rời phiên trở về mẫu mặc định; sample không ảnh hưởng dirty state hoặc yêu cầu lưu template.
- Thêm input giữ nguyên sample của input khác. Đổi nhãn giữ sample; đổi kiểu tạo lại sample của input đó theo quy tắc rõ ràng. Xóa input loại sample tương ứng. Mapping dùng ID field làm nguồn, input key làm đích, đúng kiểu của field nguồn.
- Có thể thêm preset nhóm cho recipe trắc nghiệm: `options` là list lựa chọn, `correct_answers` là list vị trí chuỗi, `explanation` là nội dung có thể sửa. Đây là thao tác người dùng chọn rõ ràng, không áp ngầm quy tắc quiz lên mọi array.

Contract và ranh giới lưu trữ:

- Text/richtext/markdown/media reference vẫn là string đúng contract; array hợp lệ là JSON list text/list lồng. Không bắt người dùng gõ JSON để làm các thao tác array thông thường. Draft JSON chưa hợp lệ được giữ riêng để sửa, không bị âm thầm gửi như chuỗi hợp lệ.
- State sample tách khỏi template draft và payload save. Chỉ gửi sample trong request preview khi cần render phía server; server validate/sanitize nhưng không ghi sample vào DB hoặc lịch sử version.
- Tệp local và object URL chỉ tồn tại trong trình duyệt, thu hồi khi thay/reset/unmount; không upload hoặc tạo `MediaAsset`. Không gửi File/blob URL vào API server rồi coi như media đã lưu.
- Để hiển thị tệp local trong card sandbox cần adapter media tạm có scope theo phiên/candidate. Kiểm tra CSP và media bridge thực tế; không nới allowlist media toàn cục để hợp thức hóa một URL tạm. Mẫu hệ thống hiện có vẫn là fallback rõ ràng khi host không hỗ trợ local preview.
- Dữ liệu sample người dùng sửa không tự trở thành dữ liệu GPT nhìn thấy. Gửi sample/báo cáo về chat là thao tác/bridge riêng ở T04/T06, khi có chức năng đó.

Tái sử dụng và file dự kiến:

- Nâng `entities/card-template/ui/SampleValuesSheet.tsx`, types, `lib/previewSamples.ts` và public API. Trích state/side effects thành hook phù hợp, không đặt vào UI component.
- `entities/flashcard` đã có array/media/field editors. `features/note-types/components/fields/FieldEditorPreview.tsx` đã có mẫu theo kiểu và chọn media local nhưng chưa phải public entity dùng chung; nếu cần tái sử dụng, trích phần độc lập xuống entity phù hợp thay vì import ngang feature.
- Cập nhật `useTemplateLibraryEditor`, `useTemplateMappingDraft` và các caller của sample sheet theo cùng contract. Kiểm tra FSD/on-touch và bảo toàn layout/màu sắc ngoài phần sample được nâng cấp.
- Preview API hiện nhận string/list; chỉ mở rộng adapter cần thiết, không cần migration hoặc field DB cho sample. T03 dùng lại contract sample này để web và MCP tránh xử lý array khác nhau.

Kiểm chứng: mở editor có mẫu đúng kiểu; sửa sample thấy kết quả ở cả hai mặt; array vẫn là list qua request; JSON sai được báo; reset/rỗng đúng semantics; save không chứa sample; đóng/mở giữ sample và refresh reset; đổi input/mapping không làm sample lẫn nhau; media local cleanup và không upload; layout responsive và API preview không ghi note/template/version.

**Đầu ra:** người dùng tạo và thử template bằng dữ liệu thực tế theo từng kiểu ngay trong editor, không phải chuẩn bị note thật hoặc lưu sample vào DB.

## 5. Trình tự và ranh giới công việc

| Đợt | Hạng mục | Phụ thuộc | Người review đánh giá được gì |
|---|---|---|---|
| A | T01 + T02; T10 là phần UI có thể làm độc lập | Fixture, bảng contract và editor mẫu | Nguyên nhân đã chứng minh, diagnostics và sample sửa trực quan được |
| B | T03 + T04 + T05 | A | Preview dữ liệu đúng đường Study và bằng chứng tương tác thật |
| C | T06 + T07 | B; docs có thể hoàn thiện từ A | Inline UI dùng được trên host; chat khám phá được hướng dẫn |
| D | T08 | B + C | Workflow hoàn chỉnh, build/deploy và rollback |
| E | T09 nếu cần | Kết quả D | Có đủ lý do xây primitive quiz hay giữ recipe |

Quyền sở hữu thay đổi theo module: backend quản lý candidate validation/projection/artifacts và MCP dispatch; frontend quản lý renderer diagnostics/preview UI/bridge; tests quản lý browser assertions; docs mô tả contract đã chứng minh. Đây là phân chia trách nhiệm triển khai, không phải yêu cầu khởi chạy subagent trong lần lập kế hoạch này.

## 6. Ma trận kiểm chứng bắt buộc khi triển khai

| Nhóm | Ca kiểm tra |
|---|---|
| Template syntax | Sections/inverted/dot; unknown token; `#each`, `@index`; thiếu đóng section; lookup method/internal; dotted field names và indexed access |
| Array | List text, list lồng, legacy newline, phần tử rỗng; numeric/object bị từ chối đúng contract; không biến list thành repr Python |
| Sample editor | Đúng editor cho 7 kiểu; array giữ list; sửa/reset/rỗng; input/type/mapping thay đổi; không dirty/save/version; media local không upload và được cleanup |
| Context | HTML, inline style, shared CSS và script; dữ liệu chứa quote, `</script>` và markup nguy hiểm không trở thành script được tin cậy |
| Binding | Field/input khác tên; thiếu optional/required; nhiều application của cùng template; version/pinned context và sai quyền |
| Runtime | Script chạy ban đầu, đổi thẻ, flip/reveal, đổi candidate; ready timeout; exception/rejection; lỗi cũ không gắn vào candidate mới |
| Quiz | 1/2/3 đáp án đúng, 2/4/6 lựa chọn; thiếu/thừa lựa chọn; đúng/sai; duplicate/out-of-range; sửa lựa chọn; thiếu explanation |
| Accessibility | Click/touch, Tab/Space/Enter theo control, focus khi flip; mobile 390px và desktop 1280px; hướng dẫn/feedback nhìn thấy được |
| MCP protocol | Metadata/output schema; read-only; no resource mutation; tài liệu và UI resource cùng tồn tại; URI lạ bị từ chối; host không có Apps |
| Security | Giữ inner iframe không `allow-same-origin`; dữ liệu field không cấp script provenance; message sai source/instance bị bỏ; diagnostic flood bị giới hạn |
| Build/rollout | Single artifact không phụ thuộc Vite dev server; renderer host có trong bundle; resource MIME/CSP; asset bị thiếu; rollback UI riêng |

Tái sử dụng suite gần nhất: `test_mcp_note_type_capabilities.py`, `test_flashcard_renderer.py`, `test_study_artifact_service.py`, `test_template_library.py` và tests entity flashcard. Bổ sung tập regression có ý nghĩa cho các hành vi trên; không nhân bản toàn bộ suite vào harness mới.

Khi bắt đầu chạy: đọc `skills/flama-local-dev/SKILL.md`; dùng venv, module runner và MySQL local cho integration. Có thể tái sử dụng pattern fixture MySQL/browser ở `scripts/probe_template_pin_isolation_mysql.py` sau khi kiểm tra guard và cleanup; không dùng case #248 làm dữ liệu bị sửa. Không mở rộng SQLite integration. Không dùng Chrome profile cá nhân.

Chạy test hẹp theo file thay đổi trước, sau đó các module `connect_mcp`, `flashcards`, `study` liên quan qua `scripts/run_tests.py`; frontend chạy focused Vitest và typecheck. Đăng ký browser regression mới vào test matrix/CI có thật. Khi tests dùng cùng một DB ngoài, giữ `--jobs 1`. Không ghi các lệnh này là đã pass trong lần lập kế hoạch.

## 7. Checklist nghiệm thu tổng thể

- [ ] Chat đọc được hướng dẫn template/array/script trực tiếp qua MCP.
- [ ] Người dùng có sample theo kiểu, sửa trực quan và thấy live preview; sample chỉ thuộc phiên editor và không lưu DB.
- [ ] Candidate sai nhận diagnostic có mã và vị trí/context hữu ích trước khi áp dụng.
- [ ] Preview chỉ đọc dùng artifact/client render tương ứng với Study, không giả định HTML Python đủ chứng minh tương tác.
- [ ] Trạng thái `passed`, `failed`, `not_run`, `unsupported` được phân biệt; không có browser run thì không có interaction pass.
- [ ] Các fixture 1/2/3 đáp án thực sự hiển thị số cần chọn, feedback và back/explanation trong browser.
- [ ] Có runtime error nhìn thấy được, correlation đúng candidate và giới hạn dữ liệu lỗi.
- [ ] Inline preview được xác minh trên host mục tiêu; text fallback vẫn có ích khi host không hỗ trợ.
- [ ] Mapping/occurrence, pinned presentation, IDs, notes và tiến độ không bị preview thay đổi.
- [ ] Editor và Study hiện tại qua regression/visual checks; artifact UI có trong package triển khai.
- [ ] Report nêu bằng chứng, giới hạn và phần còn chưa tái hiện; đóng #248 theo kết quả thực tế thay vì kết quả mutation/readback.

## 8. Phần cần thêm ngay và phần để sau

**Cần thêm để giải quyết vấn đề hiện tại:** một analyzer/diagnostic contract; một adapter/dịch vụ preview candidate theo Study; một MCP tool preview; callback lỗi runtime; bộ fixture và runner browser; một MCP UI resource/entry/build; dữ liệu mẫu theo kiểu sửa trực quan trong web editor; tài liệu syntax và recipe qua MCP; CI/package wiring và bằng chứng host thật.

**Tái sử dụng:** artifact preparation, binding projection, validators, sandbox host, preview panel, response helpers và mutation token hiện có. Có thể cần trích helper để chia sẻ đường chạy, nhưng không tạo compiler hoặc sandbox khác.

**Để sau khi có bằng chứng:** `@index` như extension renderer, nội suy trong shared CSS, JavaScript data API mới, editor riêng cho quiz, tool chạy browser từ xa, candidate-bound mutation token, hoặc native quiz component. Mỗi phần là quyết định semantics/compatibility riêng; không phải điều kiện mặc định cho v1.

## 9. Tài liệu giao thức đối chiếu

- [MCP Apps specification — draft](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx): liên kết tool/resource, MIME UI, text fallback và CSP nested frames. Phải khóa SDK/spec compatibility khi triển khai; draft có thể đổi.
- [MCP ToolAnnotations schema](https://modelcontextprotocol.io/specification/2025-06-18/schema#toolannotations): tên chuẩn `readOnlyHint`; annotation là hint, quyền truy cập vẫn do server kiểm tra.
- [MCP Apps SDK documentation](https://apps.extensions.modelcontextprotocol.io/): SDK và bridge cho UI host. Khả năng của host mục tiêu vẫn cần kiểm tra thực tế.

Lần lập kế hoạch này chỉ đọc issue/source và bổ sung tài liệu. Chưa chạy tests, browser, MCP candidate preview hay thay đổi application/data.
