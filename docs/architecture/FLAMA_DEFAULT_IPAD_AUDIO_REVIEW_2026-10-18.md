# Flama Default: audio tự phát trên iPad

Ngày kiểm tra: 2026-10-18 (Asia/Tokyo). Phạm vi: đọc template qua Flama MCP, đọc renderer đang deploy qua SSH, đối chiếu code và chẩn đoán nhánh phát trong JSDOM. Không sửa dữ liệu hoặc code production.

**Cập nhật 2026-10-19:** Đã áp dụng bản sửa trên server theo yêu cầu người dùng; xem phần xác minh sau sửa bên dưới. Các quan sát ban đầu mô tả trạng thái trước bản sửa.

## Kết luận

Đã xác nhận khác biệt giữa Flama Default và template tiếng Anh: thuộc tính `controls` trên hai audio ẩn của Flama Default làm chúng **bỏ qua media bridge**, phát bằng phần tử native trong iframe. Template tiếng Anh `Advanced Vocabulary Card` không có `controls`, nên phát qua audio dùng chung ở trang host.

Đây là nguyên nhân có cơ sở mạnh cho triệu chứng người dùng xác nhận: **phải bấm loa ở mọi thẻ**. Khi thay nội dung iframe, phần tử native được tạo lại; tương tác trước đó không bảo đảm quyền autoplay cho phần tử mới. Chưa có log `NotAllowedError` trực tiếp hoặc thử nghiệm trên iPad thật để xác nhận hoàn toàn chính sách của phiên bản trình duyệt cụ thể.

## Bằng chứng từ server

- Release đang chạy: `/opt/flama/releases/c1dfa6e88bcac074649fec9579a6314674a9f51b`.
- Note type: `Flama Standard Vocabulary`, ID `e2f310a8-ecb3-4446-8a93-4c258e52b132`.
- Template mặc định: `Default Flama Flashcard`, ID `e0cb18b2-881d-4b46-a567-dc5db14d661f`; application `e47485cc-84a8-41ae-8836-5dec2e7b9963`.
- Template so sánh: `En4Everyone` → `Advanced Vocabulary Card`, ID `f6d63262-7ad8-4694-af0c-4bd8b0519c61`.
- SHA-256 renderer server và local sau chuẩn hóa newline đều là `c593ce458aa274322938a424e2c6b75ca5215d89f4b2ff232993ab438771d322`.

| Vị trí trong source template trên server | Flama Default | Advanced Vocabulary Card |
|---|---|---|
| Audio từ vựng | back HTML dòng 15: `<audio id="custom-audio" controls style="display: none" ...>` | back HTML dòng 8: `<audio id="word-audio" ...>` |
| Audio ví dụ | back HTML dòng 91–96: có `controls`, ẩn bằng CSS | back HTML dòng 66: không có `controls` |
| Tự phát | Gọi `.play()` khi script mặt sau chạy | Cũng gọi `.play()` khi script mặt sau chạy |
| Phát ví dụ | Sau `ended`, đợi 500 ms | Sau `ended`, đợi 500 ms |

`get_card` với một note thuộc deck 416 đã xác nhận HTML render trên server vẫn giữ cả hai thuộc tính `controls` và dùng URL `/media/proxy/...`. Khác biệt tồn tại ở payload đã render, không chỉ bản backup trong repo.

## Luồng renderer

Trong [card_renderer_host.js](../../static/js/card_renderer_host.js), dòng 575:

```javascript
if (tagName === 'audio' && !element.controls) {
    // Resolve approved media, then post('play_audio', ...)
}
return originalPlay.apply(element, arguments);
```

- `controls=true`: gọi native `HTMLMediaElement.play()` trong iframe.
- `controls=false`: media proxy được duyệt qua bridge, host gọi `getSharedAudioElement()` (dòng 234–260), dùng lại phần tử audio giữa các thẻ và nguồn phát.
- [CardRendererFrame.tsx](../../frontend/src/entities/flashcard/ui/CardRendererFrame.tsx) gọi `controller.render()` trong effect khi mặt/nội dung thẻ đổi. Controller gán `frameEl.srcdoc` ở dòng 1116, tạo document/phần tử audio mới.
- Flama Default chỉ `console.warn` khi lần autoplay đầu thất bại; bấm loa gọi `.play()` trực tiếp từ thao tác người dùng, nên có thể phát được.

JSDOM chạy shell tạo từ chính renderer có checksum trùng server, với media native được stub để đếm nhánh gọi:

| Trường hợp | Số lần native play trong iframe | Số yêu cầu play gửi host |
|---|---:|---:|
| Audio có `controls`, ẩn bằng CSS | 1 | 0 |
| Cùng audio, bỏ `controls` | 0 | 1 |

Chẩn đoán này chứng minh lựa chọn nhánh của renderer; không mô phỏng chính sách autoplay thật của Safari.

## Hướng sửa nhỏ nhất

Bỏ `controls` ở cả `custom-audio` và `example-audio` của template Flama Default, giữ nút loa, URL proxy và thứ tự từ vựng → ví dụ sau 500 ms. Hai phần tử sẽ dùng media bridge giống template tiếng Anh. Không cần thay field dữ liệu hoặc nới sandbox.

Sau khi sửa cần thử trên iPad: bắt đầu phiên mới, lật đáp án, chuyển nhiều thẻ, nghe từ vựng rồi ví dụ, và bấm nghe lại. Nếu trình duyệt chặn lần phát đầu của cả phiên, cần xử lý mở quyền audio từ thao tác người dùng ở host; việc bỏ `controls` không phải cơ chế vượt chính sách trình duyệt.

## Nguồn chính sách trình duyệt

- [WebKit: New video policies for iOS](https://webkit.org/blog/6784/new-video-policies-for-ios/): giải thích yêu cầu thao tác người dùng cho media có tiếng và việc `.play()` phải được gọi từ sự kiện phù hợp.
- [WebKit: Auto-play policy changes for macOS](https://webkit.org/blog/7734/auto-play-policy-changes-for-macos/): hướng dẫn quyền autoplay theo từng phần tử và dùng lại phần tử cho chuỗi media. Đây là tài liệu macOS, dùng làm hướng dẫn thiết kế; không thay thế kiểm chứng phiên bản iPadOS thực tế.

## Đã sửa trên server — 2026-10-19

- Thời điểm: 00:06 Asia/Tokyo.
- Dùng `flashcard_content_service.update_template` của release đang chạy, qua luồng content hotfix có kiểm tra quyền tác giả, compile template, audit log và immutable version history.
- Khóa template và kiểm tra version/hash trước ghi để tránh ghi đè thay đổi mới.
- Version trước: 3, `503ebd9b-5719-4c3f-a17c-df994a5084d4`.
- Version sau: 4, `1944204d-587c-4c0b-a5dc-429529d1cac4`.
- Chỉ bỏ `controls` ở `custom-audio` và `example-audio`; checksum back HTML sau sửa: `19d2e25a7065792ad96610cb38d6eb4a827c494dda5c06a8068c2f52d705bfb2`.
- Xác minh front HTML, CSS, input schema, tên/owner template và toàn bộ attachment của template không thay đổi. Không có DML vào `notes`, `field_defs`, `study_progress_subjects` hoặc `study_applications` trong thao tác cập nhật.
- Đọc lại qua Flama MCP: hai audio đều không có `controls`; hai template còn lại của note type và field schema giữ nguyên.
- `get_card` sau cập nhật xác nhận HTML render của một thẻ thực tế có cả audio từ vựng và ví dụ với URL proxy, không còn `controls`.
- Đồng bộ `note-type-templates/flama-default/back.html`, cập nhật checksum và phiên bản backup 1.1.1.
- Vitest: `arrayTemplates.test.ts` và `CardRendererHost.test.ts` — 18 test pass.
- Cần tải lại trang và bắt đầu phiên học mới trên iPad để dùng template mới. Chưa xác minh trên thiết bị iPad thật.
