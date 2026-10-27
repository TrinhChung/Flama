# Review độ ổn định Edge TTS — 2026-10-27

Ngày review: **27/10/2026, Asia/Tokyo**; snapshot cuối xác minh khoảng **22:28 JST**. Phạm vi: working tree của Flama Audio, gồm module Edge TTS chưa commit, WPF host, local HTTP API và các caller React liên quan. HEAD nền: `ab9d5a76`. Có thay đổi từ phiên khác trong lúc review; các kết luận hiện còn tồn tại dưới đây đã đối chiếu lại với snapshot cuối.

## 1. Kết luận

**Có lỗi thực sự trong quản lý WebSocket và nhận kết quả; chưa đủ bằng chứng để quy toàn bộ hiện tượng cho bước tạo socket hoặc máy chủ Microsoft.** Các vấn đề ưu tiên cao nhất:

1. Đóng socket sớm, audio rỗng và audio chưa hoàn tất vẫn có thể được trả thành công.
2. `_connectLock` mới giải quyết connect trùng ở cold start, nhưng chưa bảo vệ toàn bộ lượt kết nối → cấu hình → tổng hợp → phục hồi.
3. Socket đã bị server đóng giữa hai lượt vẫn có thể được coi là đang mở; lượt sau nhận audio rỗng và không kích hoạt retry.
4. Không có deadline ở tầng engine cho connect, chờ audio, chờ khóa và close; caller WPF/Web cũng thiếu hủy tác vụ tổng hợp.
5. Test live có thể xanh dù WebSocket lỗi. **96 test đã chọn pass trên snapshot cuối**, nhưng chưa bao phủ các lỗi đã tái hiện.

Khuyến nghị: sửa tính đúng đắn của kết quả, quyền sở hữu socket và timeout trước; sau đó đo để quyết định chính sách reuse. Không có cơ sở từ review này để đổi endpoint, nâng version giả lập trình duyệt hoặc bỏ reuse trên mọi request.

## 2. Bằng chứng đã chạy

### 2.1. Kiểm thử có sẵn

Máy review: Windows, .NET SDK `8.0.419`, target engine `net8.0`.

Chạy lại cùng một filter sau các thay đổi đồng thời:

```powershell
dotnet test flama-audio/tests/Flama.Audio.Tests/Flama.Audio.Tests.csproj --no-restore --filter '(FullyQualifiedName~EdgeTtsDrmTests|FullyQualifiedName~EdgeTtsWebSocketTests|FullyQualifiedName~EdgeTtsVoiceCatalogTests|FullyQualifiedName~EdgeTtsEmpiricalChallengeTests|FullyQualifiedName~EdgeTtsEngineAdapterTests|FullyQualifiedName~EdgeTtsChallengerStressTests)&FullyQualifiedName!~Live&FullyQualifiedName!~ListVoicesAsync_Returns322Voices&FullyQualifiedName!~StartAsync_And_StopAsync_ExecuteWithoutError' --logger 'console;verbosity=minimal'
```

| Snapshot | Kết quả | Ý nghĩa |
|---|---|---|
| Snapshot cuối, có `_connectLock` và catalog disk-first | **96 pass, 0 fail** | Không bao gồm test synthesis live; một số test health vẫn gọi DNS |

Một bản catalog trung gian từng làm `GetVoicesAsync_DiskCache_LoadsSuccessfully` thất bại vì ưu tiên embedded hơn disk. Snapshot cuối đã sửa thứ tự này; không tính đó là lỗi hiện còn tồn tại.

Không sửa implementation hoặc test hiện có trong đợt review này. Không chạy ứng dụng Flask, migration hoặc thao tác DB.

### 2.2. Fault injection bằng WebSocket thật trên localhost

Dùng console harness tạm ngoài repo, tham chiếu trực tiếp project Edge TTS hiện có và Kestrel bind `127.0.0.1` trên cổng ngẫu nhiên. Các hàng dưới chạy qua **`EdgeWebSocketClient` thật**, không thay thế parser bằng bản sao trong test. Payload 8 byte là fixture cố ý, không phải MP3 hoàn chỉnh.

| Server giả lập | Kết quả thực tế | Kỳ vọng |
|---|---|---|
| Gửi Close trước audio và trước `turn.end` | Trả thành công, **0 byte** | Lỗi lượt chưa hoàn tất |
| Gửi 8 byte audio rồi Close, thiếu `turn.end` | Trả thành công, **8 byte** | Không trả audio dở dang là kết quả hợp lệ |
| Chỉ gửi `turn.end`, không có audio | Trả thành công, **0 byte** | Lỗi không nhận được audio |
| Audio và `turn.end` mang request ID khác | Trả thành công, **8 byte** | Không nhận kết quả của lượt khác |
| Binary frame khai header length vượt dữ liệu, rồi `turn.end` | Bỏ qua frame lỗi, trả thành công **0 byte** | Lỗi protocol rõ ràng |
| Server im lặng sau khi nhận SSML | Chỉ dừng khi deadline **do harness cấp** hết hạn, khoảng **1.203 giây** | Engine tự giới hạn thời gian chờ |
| Lượt 1 gửi audio + `turn.end`, rồi server gửi Close; chờ 150 ms và gọi lượt 2 | Lượt 1: 8 byte; trước lượt 2 `IsConnected=true`; lượt 2 trả thành công **0 byte** | Nhận diện socket cũ, reset và phục hồi hoặc báo lỗi |

Kiểm tra adapter bằng các implementation kiểm soát lịch chạy của `IEdgeWebSocketClient`, tách biệt với các phép thử transport ở trên:

| Trường hợp | Quan sát |
|---|---|
| Hai lượt bắt đầu khi chưa kết nối, snapshot cuối | **1 lần connect**; `_connectLock` đã cải thiện trường hợp này |
| Lượt A đã connect nhưng đang chờ gửi config hoàn tất; bắt đầu B | B vào synthesis khi config chưa hoàn tất: **1 lần** |
| Client trả `byte[0]` | Adapter vẫn tạo `TtsResult` thành công |
| Voice/language có dấu nháy và text có `U+0001` | Attribute bổ sung lọt vào SSML; XML parser từ chối tài liệu |

Các phép thử adapter chứng minh thiếu ràng buộc ở tầng orchestration. Chúng không phải số đo xác suất race trên mạng Microsoft. Trước khi `_connectLock` được thêm, probe cold start từng ghi nhận 2 lần connect; không dùng kết quả cũ đó để mô tả snapshot cuối.

### 2.3. Gọi dịch vụ thật có deadline

Lượt đầu bắt đầu khoảng **22:19 JST**, với deadline ngoài 12 giây/request, dùng cùng adapter. Các phép thử live này diễn ra trước thay đổi `_connectLock`; transport/parser không đổi, nhưng chưa chạy lại live trên adapter snapshot cuối:

| Lượt | Voice | Kết quả | Thời gian |
|---|---|---|---|
| 1 | `ja-JP-NanamiNeural` | 15.696 byte | 1.212 ms |
| 2 | `vi-VN-HoaiMyNeural` | `WebSocketException`: remote đóng kết nối mà không hoàn tất close handshake | 6.161 ms |
| 3 | `ja-JP-NanamiNeural` | 11.808 byte | 1.056 ms |

Health ngay trước đó trả `ready`. Đây là một lỗi tổng hợp được quan sát trực tiếp; chưa xác định được nguyên nhân ở mạng, backend Microsoft hay trạng thái phiên từ mẫu này.

Đối chiếu bổ sung trên từng nhóm 3 lượt: reuse và config một lần/connection; reuse nhưng gửi lại config mỗi lượt; tạo adapter mới mỗi lượt. Cả **9 lượt tiếng Anh** và **9 lượt đổi Nhật → Việt → Nhật** đều có audio khác rỗng. Với nhóm tiếng Anh, reuse sau lượt đầu mất 216–241 ms; mở mới mỗi lượt mất 492–1.232 ms trong lần đo này. Các nhóm chạy tuần tự, mẫu nhỏ và chịu cache/mạng, nên không dùng làm benchmark hoặc tỷ lệ lỗi dài hạn.

Một lượt đối chiếu thử nghiệm ban đầu bị lỗi encoding của fixture đã bị loại khỏi kết luận về độ ổn định. Các số đo so sánh ở trên dùng fixture đã kiểm tra lại.

Voice-list HTTP trả 200 và 322 voices ở cả request tối giản và request thêm GEC v2/User-Agent/Cookie. Không tái hiện được lỗi 403 khi lấy catalog trong lần kiểm tra này.

## 3. Các vấn đề cần cải thiện

### P1-01 — Kết quả thành công không yêu cầu audio hoàn tất

**Vị trí:** [EdgeWebSocketClient.cs](../../../flama-audio/src/Flama.Audio.Engine.EdgeTts/Network/EdgeWebSocketClient.cs), dòng 118–171; [EdgeTtsEngineAdapter.cs](../../../flama-audio/src/Flama.Audio.Engine.EdgeTts/EdgeTtsEngineAdapter.cs), dòng 154–182.

Nhánh Close chỉ `break`; sau vòng lặp luôn log “completed” và trả buffer. Không kiểm tra `turnEnded`, số byte hoặc lỗi trong response. Adapter không có hàng rào thứ hai cho output rỗng. Retry chỉ chạy khi có exception, nên các lỗi đã tái hiện này đi thẳng thành kết quả thành công. Local API sau đó có thể trả HTTP 200 với audio rỗng/dở dang.

**Cải thiện:** chỉ thành công khi đã nhận tín hiệu kết thúc đúng lượt và có audio. Close trước kết thúc phải thành lỗi riêng, bỏ buffer của attempt đó và invalidate socket. Phân biệt no-audio, incomplete-turn, protocol-error; không dùng ngưỡng byte cố định để kết luận audio đầy đủ. Có thể thêm kiểm tra giải mã MP3 trong kiểm thử, nhưng header MP3 hợp lệ không chứng minh cả câu đã được đọc.

### P1-02 — Quyền sở hữu connection chưa bao trùm toàn bộ transaction

**Vị trí:** adapter dòng 155–174, 185–230; client dòng 26–65, 67–95; [App.xaml.cs](../../../flama-audio/src/Flama.Audio.App/App.xaml.cs), dòng 75–78.

Adapter là singleton. Bản mới có `_connectLock` và kiểm tra lại trạng thái trong khóa, đã tránh connect trùng ở cold start được thử. Tuy nhiên, fast path `if (_client.IsConnected) return` nằm trước khóa. Khi lượt A đang giữ `_connectLock` để gửi config, socket đã Open; lượt B bỏ qua khóa và gửi SSML. Probe snapshot cuối vẫn tái hiện **1 lượt synthesis trước config hoàn tất**.

Khóa này cũng không bao trùm synthesis và retry. Một request đã quyết định phục hồi vẫn có thể đợi khóa ở client trong khi request khác sử dụng connection; sau đó `ConnectAsync` thay socket vì method này luôn dispose `_ws` cũ. Chưa có generation/ownership để bảo đảm recovery chỉ tác động đúng phiên lỗi.

Client đã serialize các thao tác của mình; không kết luận rằng có hai `ReceiveAsync` chạy đồng thời trong implementation hiện tại. Lỗ hổng nằm ở sự xen kẽ giữa các thao tác và quá trình phục hồi. Ngoài ra `Dispose()` không dùng cùng cơ chế đồng bộ.

**Cải thiện:** một chủ sở hữu cho mỗi socket. Với thiết kế hiện tại, dùng gate ở adapter cho toàn bộ ensure-connect/config/synthesis/reset/retry, kèm deadline cho thời gian chờ gate. Chỉ publish trạng thái “configured” sau khi config hoàn tất. Nếu cần nhiều request thực sự song song, dùng pool nhỏ có giới hạn, mỗi connection xử lý một lượt; không chỉ tăng worker phía caller.

### P1-03 — `IsConnected` không chứng minh socket còn dùng được

**Vị trí:** client dòng 19, 118–168; adapter dòng 185–187.

`IsConnected` chỉ đọc `ClientWebSocket.State == Open`. Không có receive đang chờ giữa các lượt để quan sát Close. Fault injection đã chứng minh server đóng sau lượt 1 nhưng trước lượt 2 client vẫn báo connected; lượt 2 trả 0 byte. Trường hợp này không vào nhánh reconnect vì thiếu exception của P1-01.

**Cải thiện:** xử lý Close/no-audio/incomplete-turn như lỗi phiên; reset và dispose socket cũ trước reconnect. Có chính sách tuổi/idle của connection và kiểm tra phục hồi sau sleep/resume, đổi mạng. TTL không thay thế kiểm tra kết quả.

.NET 8 có keep-alive mặc định dạng unsolicited PONG; cơ chế này không bảo đảm phát hiện peer mất phản hồi nhanh. `KeepAliveTimeout` với PING/PONG là khả năng được thêm từ .NET 9, nên không đưa thẳng cấu hình đó vào target `net8.0`. [Tài liệu Microsoft](https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/websockets).

### P1-04 — Chưa có deadline và đường hủy xuyên suốt

**Vị trí:** client dòng 28, 58, 95, 126, 179–199; [MainWindow.xaml.cs](../../../flama-audio/src/Flama.Audio.App/MainWindow.xaml.cs), dòng 583; [flamaAudioClient.ts](../../../frontend/src/lib/flamaAudioClient.ts), dòng 105–129; [ApiEndpoints.cs](../../../flama-audio/src/Flama.Audio.Api/ApiEndpoints.cs), dòng 190.

Engine chỉ sử dụng cancellation token do caller cấp, không đặt deadline của riêng mình. WPF gọi synthesis với token mặc định. Web `synthesize()` không nhận `AbortSignal` và không đặt timeout. API chuyển `RequestAborted`, nhưng đây là tín hiệu client ngắt request, không phải giới hạn thời gian tổng hợp.

Một lượt đang chờ nhận audio giữ semaphore; các lượt sau và `CloseAsync` cũng phải chờ. Đường đóng kết nối không có giới hạn riêng hoặc bước abort cuối cùng. Vì vậy lỗi mạng có thể biểu hiện thành nút thử giọng/queue chờ kéo dài, dù UI thread không bị block trực tiếp.

**Cải thiện:** linked token với connect timeout, thời gian chờ dữ liệu, deadline toàn request gồm chờ gate và retry; close timeout ngắn rồi abort/dispose. Phân biệt caller cancel với timeout nội bộ. UI cần hủy synthesis khi người dùng hủy/đóng phiên; task chờ gate phải hủy được mà không phá connection của lượt đang chạy.

### P1-05 — Test live có thể che lỗi kết nối

**Vị trí:** [EdgeTtsIntegrationTests.cs](../../../flama-audio/tests/Flama.Audio.Tests/EdgeTtsIntegrationTests.cs), dòng 16–17, 24–27, 50–53, 125–128; [EdgeTtsChallengerStressTests.cs](../../../flama-audio/tests/Flama.Audio.Tests/EdgeTtsChallengerStressTests.cs), các nhánh `catch (IsNetworkException)`; [EdgeTtsWebSocketTests.cs](../../../flama-audio/tests/Flama.Audio.Tests/EdgeTtsWebSocketTests.cs), dòng 54–78.

Nhiều test live bắt WebSocket/timeout/network exception rồi kết thúc bình thường, không đánh dấu skipped/failed. Test Việt Nam trong integration lại không dùng cùng guard, nên chính sách còn không nhất quán. Test binary parser đang sao chép phép cắt byte trong thân test, không gọi parser thật. Mock concurrency không mô phỏng việc Connect dispose connection cũ, nên vẫn có thể xanh khi tầng orchestration bị race.

**Cải thiện:** test deterministic qua transport thật với local fake server cho các lỗi ở mục 2.2; tách test live opt-in. Live đã bật thì connection failure phải fail; môi trường thiếu prerequisite phải skip rõ ràng. Thêm assert số connect, thứ tự config/SSML và không trả audio rỗng. Cả CI và release workflow hiện gọi `dotnet test` toàn solution, nên cần tránh test live không kiểm soát làm nhiễu gate phát hành.

### P2-01 — Parser chưa ràng buộc request ID và protocol response

**Vị trí:** client dòng 132–161.

Nhận diện `Path` bằng `Contains`, không parse header thành key/value và không so `X-RequestId`. Binary sai độ dài bị bỏ qua; response lỗi hoặc path bất thường không được phân loại. Đã tái hiện nhận dữ liệu của ID khác.

**Cải thiện:** parse header chính xác, kiểm tra framing, path, content type và ID khi protocol cung cấp ID; parse response lỗi. Khi lệch phiên hoặc framing sai, loại connection thay vì tiếp tục nhận mù. Hạn chế kích thước message và tổng audio buffer để tránh một response bất thường giữ RAM quá lâu.

### P2-02 — Retry chưa có phân loại lỗi và chẩn đoán handshake

**Vị trí:** adapter dòng 160–173, 201–230; client dòng 44–59, 179–199; [EdgeTtsDrm.cs](../../../flama-audio/src/Flama.Audio.Engine.EdgeTts/Cryptography/EdgeTtsDrm.cs), dòng 15–27, 355–373.

Snapshot mới đã gọi `ReconnectAsync` khi retry, đi tới `ConnectAsync` để thay socket, thay vì chỉ trông chờ `IsConnected` đổi sau Close. Tuy vậy, vẫn chỉ retry một lần ngay lập tức cho `WebSocketException`, `InvalidOperationException`, `IOException`. Các lỗi khác nhau đều bị gọi là disconnected socket; không có HTTP handshake status/headers để phân biệt 403, 429 hoặc lỗi upstream. Có setter clock skew nhưng production không gọi nó. Bước Close trước reconnect vẫn có thể chờ mà không có deadline nội bộ.

**Cải thiện:** thu handshake status, server Date, close status, phase và attempt; reset phiên rõ ràng trước retry. Retry có giới hạn và delay có jitter cho lỗi tạm thời, dùng cùng tổng deadline. Không retry input sai hoặc cancellation của caller. Với 403, chỉ thử hiệu chỉnh đồng hồ khi có Date đáng tin cậy và offset hợp lý; 403 không mặc nhiên đồng nghĩa lệch giờ. Upstream cũng có xử lý offset từ response Date. [Mã DRM upstream](https://raw.githubusercontent.com/rany2/edge-tts/master/src/edge_tts/drm.py).

### P2-03 — Health và log chưa phản ánh khả năng tổng hợp

**Vị trí:** adapter dòng 36–37, 41–84; App dòng 73–77; WPF dòng 920–941.

Health chỉ resolve DNS rồi cache 30 giây. Nó không kiểm tra TLS, upgrade, xác thực protocol hoặc audio. UI hiển thị “Sẵn sàng” dựa trên tín hiệu này. Adapter tạo client và catalog bằng `new` không truyền logger; DI hiện chỉ cấp logger cho adapter. Log connect/frame/close quan trọng vì thế không tự xuất hiện trong app như khi inject logger thủ công ở harness.

**Cải thiện:** tách app reachable/network reachable/upstream synthesis status; ghi lần tổng hợp thành công gần nhất và lỗi gần nhất. Inject logger/client/catalog qua DI. Log có correlation ID, connection generation, attempt, queue wait, connect time, time-to-first-audio, total time, byte count, close/HTTP code. Không log toàn văn SSML hoặc toàn bộ URL chứa token/cookie.

### P2-04 — Catalog đọc nhanh nhưng chưa có cơ chế refresh remote thông thường

**Vị trí:** [EdgeTtsVoiceCatalog.cs](../../../flama-audio/src/Flama.Audio.Engine.EdgeTts/Services/EdgeTtsVoiceCatalog.cs), dòng 75–114; adapter dòng 92–106.

Snapshot cuối có fast path: `forceRefresh=false` thì đọc disk trước, sau đó embedded và trả ngay nếu hợp lệ. Thứ tự disk/embedded đã được sửa và test đọc disk pass. Tuy nhiên, cả Start/List của adapter đều truyền false, không có refresh nền hoặc TTL; khi có cache hợp lệ thì remote không được gọi để tìm thay đổi mới. Các test “network timeout fallback” có thể trả embedded ngay mà không chạm handler HTTP; tên test khi đó không còn chứng minh hành vi timeout.

**Cải thiện:** giữ fast path, làm mới nền theo TTL/single-flight và giữ fallback embedded. Cho test kiểm soát nguồn cache, assert HTTP/disk thực sự được truy cập. Remote path hiện chưa gửi GEC v2 như [voice-list upstream](https://raw.githubusercontent.com/rany2/edge-tts/master/src/edge_tts/voices.py); ghi nhận khoảng trống tương thích này, nhưng chưa thể gọi là nguyên nhân lỗi hiện tại vì probe thực tế vẫn trả 200.

### P2-05 — Input và hợp đồng output có thể tạo lỗi giống lỗi socket

**Vị trí:** adapter dòng 111–141; [TtsModels.cs](../../../flama-audio/src/Flama.Audio.Core/Models/TtsModels.cs), dòng 7–22; API dòng 191.

Text được escape XML nhưng control character không hợp lệ vẫn còn; `voiceId` và `language` được nội suy trực tiếp vào attribute. Chưa validate voice, locale và khoảng hữu hạn cho prosody. Không giới hạn/chia text theo byte trong engine; toàn bộ SSML được gửi một message. Input lớn hoặc SSML sai có thể dẫn đến lỗi upstream và bị nhìn nhầm thành sự cố mạng.

Engine luôn trả MP3 dù request có `OutputFormat` mặc định `wav`; API luôn đặt tên file `.wav`. WPF đã có nhánh phát MP3, nhưng hợp đồng download/upload còn không đồng nhất.

**Cải thiện:** xây XML bằng API an toàn, validate voice/locale/prosody, xử lý control character, giới hạn byte và chia đoạn an toàn với Unicode/XML entities. Upstream đang chia text thành các đoạn 4.096 byte; đây là lựa chọn tham khảo, không phải giới hạn server đã được review này đo xác nhận. [Communicate upstream](https://raw.githubusercontent.com/rany2/edge-tts/master/src/edge_tts/communicate.py). Trả MIME/extension đúng định dạng; nếu không hỗ trợ output được yêu cầu thì báo lỗi contract rõ ràng.

## 4. Thứ tự triển khai đề xuất

| Đợt | Phạm vi | Điều kiện hoàn thành |
|---|---|---|
| 1 | P1-01, P1-02, P1-03 và test deterministic | Không có success với 0 byte/thiếu turn.end; một connection không bị hai lượt giành quyền; cold start chỉ connect theo số slot cho phép; phát hiện stale socket |
| 2 | P1-04, P2-02, P2-03 | Không có request chờ vô hạn ở tầng ứng dụng; cancel/timeout giải phóng slot; retry có deadline và reset thật; có log xác định phase lỗi |
| 3 | P1-05, P2-01, P2-04, P2-05 | Test lỗi thực sự kiểm tra production path; catalog test pass và refresh được; ID/protocol/input/output đúng contract |
| 4 | Đo chính sách reuse/pool | So sánh request thành công có audio đầy đủ, p50/p95 latency, time-to-first-audio, số connect/retry/close/timeout; thay đổi một yếu tố mỗi lần |

Ma trận xác minh tiếp theo nên gồm: một caller và nhiều caller; cold start/reconnect; idle 30/60/120 giây; đổi voice/locale; sleep/resume và mất mạng có kiểm soát; server Close sau audio một phần; server không gửi `turn.end`; cancellation khi đang chờ gate và khi đang nhận audio; văn bản dài nhiều byte và control characters. Không cần bắn stress tải lớn lên dịch vụ thật để kiểm tra parser hoặc khóa.

## 5. Giới hạn và các điểm chưa nên kết luận

- Module Edge TTS đang có trong WPF và được đăng ký ở local API. React hiện chỉ cho chọn `voicevox | kokoro` trong audio rule/type; **chưa có flow chọn Edge TTS hoàn chỉnh trên Web**. Rủi ro concurrent Edge hiện áp dụng cho nhiều HTTP caller hoặc HTTP cùng WPF; không giả định queue Web đang sử dụng Edge.
- Endpoint, User-Agent version và `Sec-MS-GEC-Version=2-143.0.3650.75` hiện khớp [constants upstream](https://raw.githubusercontent.com/rany2/edge-tts/master/src/edge_tts/constants.py) được kiểm tra ngày review. Không báo thiếu token v2 hoặc version cũ chỉ dựa vào số phiên bản.
- Chưa đo reliability dài hạn, idle thực trên mạng Microsoft, proxy/VPN, DNS failure có kiểm soát, handshake 403/429 hoặc memory khi văn bản rất lớn. Chưa xác nhận audio live bằng nghe/giải mã toàn file; số đo live ở đây là số byte và outcome của request.
- Có chỉnh sửa adapter và catalog từ phiên khác trong lúc review. Snapshot cuối có `_connectLock`, clean reconnect và fast path disk-first; các probe localhost được chạy lại, bộ 96 test đã chọn pass. Các hash dưới đây xác định phạm vi review nếu code tiếp tục thay đổi.

| File core | SHA-256 của snapshot review |
|---|---|
| `EdgeTtsEngineAdapter.cs` | `AFE94E7AF1A99ED2C60FEEE4C21EF3B426D92BC7CCC7049FF53978B043D34CA9` |
| `Network/EdgeWebSocketClient.cs` | `6E8795042259D99A0EA45D7F8532EAA90DD1AE1769391EE0A31741A09B83327E` |
| `Cryptography/EdgeTtsDrm.cs` | `3F318975DE23F788E0AF5457B47201E282371FDDB6E3BD4DAA1CCFF670D1D9F1` |
| `Services/EdgeTtsVoiceCatalog.cs` | `F2D03F853CE46F66CD1DE647FF57F2DBD1ED8015AC25FF6EACA183544237E452` |

