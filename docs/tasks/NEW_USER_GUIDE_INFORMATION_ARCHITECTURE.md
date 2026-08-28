# Task: Tách hệ thống hướng dẫn sử dụng cho người mới thành `/guide/*`

## Bối cảnh

Hiện tại một số màn hình chức năng đang chứa quá nhiều tab hoặc nội dung hướng dẫn trực tiếp, ví dụ:

- Đồng bộ Anki
- MCP
- Yomitan
- Các thiết lập tích hợp khác

Việc vừa đặt chức năng, vừa đặt hướng dẫn, vừa đặt nội dung xử lý sự cố trong cùng một màn hình làm UI trở nên rối, khó hiểu với người mới và làm các trang chức năng ngày càng phình to.

## Mục tiêu

Thiết kế lại hệ thống hướng dẫn theo hướng:

- Trang chức năng chỉ tập trung vào thao tác chính.
- Nội dung hướng dẫn chi tiết được tách thành các URL riêng dưới `/guide/*`.
- Mỗi chức năng có nút/link **Hướng dẫn sử dụng** dẫn đúng tới bài viết tương ứng.
- Mỗi chức năng có nút/link **Sự cố / Khắc phục sự cố** dẫn tới bài troubleshooting tương ứng.
- Tạo một khu vực hướng dẫn tổng thể cho người mới, có cấu trúc rõ ràng và dễ tìm kiếm.

## Định hướng URL

Ví dụ:

```text
/guide
/guide/getting-started
/guide/anki-sync
/guide/mcp
/guide/yomitan
/guide/flama-connect
/guide/audio

/guide/troubleshooting
/guide/troubleshooting/anki-sync
/guide/troubleshooting/mcp
/guide/troubleshooting/yomitan
/guide/troubleshooting/flama-connect
```

Tên route cụ thể có thể điều chỉnh khi triển khai nhưng cần giữ cấu trúc thống nhất.

## Phạm vi công việc

### 1. Tạo trung tâm hướng dẫn `/guide`

Trang `/guide` đóng vai trò là Help Center / User Guide của Flama.

Nên chia thành các nhóm lớn như:

- Bắt đầu sử dụng Flama
- Học và quản lý bộ thẻ
- Marketplace
- Đồng bộ và tích hợp
- Anki
- Yomitan
- MCP
- Flama Connect
- Audio / TTS
- Tài khoản và cài đặt
- Xử lý sự cố

Ưu tiên thiết kế cho người mới, không trình bày theo cấu trúc code hoặc module kỹ thuật nội bộ.

### 2. Tách nội dung hướng dẫn khỏi màn hình chức năng

Rà soát các màn hình hiện đang dùng nhiều tab chỉ để chứa hướng dẫn hoặc giải thích dài.

Ví dụ với Anki, MCP, Yomitan:

```text
Trước:
[Thiết lập] [Hướng dẫn] [Sự cố] [Thông tin...]

Sau:
Trang chức năng
- trạng thái
- cấu hình
- thao tác chính

[Hướng dẫn sử dụng]
[Sự cố?]
```

Nội dung dài chuyển sang `/guide/...`.

Không cần xóa hoàn toàn contextual help khỏi màn chức năng. Có thể giữ mô tả ngắn hoặc tooltip, nhưng không nên nhồi toàn bộ tài liệu hướng dẫn vào tab.

### 3. Gắn hướng dẫn theo ngữ cảnh

Ở từng màn hình chức năng, thêm action phù hợp:

```text
? Hướng dẫn sử dụng
```

Ví dụ:

- màn Anki Sync -> `/guide/anki-sync`
- màn MCP -> `/guide/mcp`
- màn Yomitan -> `/guide/yomitan`

Người dùng không cần tự quay về `/guide` rồi tìm lại bài viết.

### 4. Luồng xử lý sự cố

Ở các màn hình có khả năng phát sinh lỗi kết nối hoặc cấu hình, thêm action rõ ràng:

```text
Gặp sự cố?
Khắc phục sự cố
```

Ví dụ:

- Anki không kết nối -> `/guide/troubleshooting/anki-sync`
- MCP không kết nối -> `/guide/troubleshooting/mcp`
- Yomitan không gửi được từ -> `/guide/troubleshooting/yomitan`

Các bài troubleshooting nên ưu tiên flow theo triệu chứng:

```text
Không kết nối được
Không thấy dữ liệu
Bị timeout
Sai quyền truy cập
Port bị chiếm
Extension chưa kết nối
```

Không nên bắt người dùng hiểu nguyên nhân kỹ thuật trước rồi mới tìm được hướng dẫn.

### 5. Chuẩn hóa cấu trúc bài hướng dẫn

Mỗi bài hướng dẫn nên có cấu trúc tương đối thống nhất:

```text
1. Chức năng này dùng để làm gì
2. Khi nào nên sử dụng
3. Điều kiện trước khi bắt đầu
4. Các bước thiết lập
5. Cách kiểm tra đã hoạt động
6. Các lỗi thường gặp
7. Link tới troubleshooting chi tiết
8. Nội dung liên quan
```

Bài troubleshooting có thể dùng cấu trúc:

```text
Triệu chứng
Nguyên nhân thường gặp
Cách kiểm tra
Cách xử lý
Nếu vẫn không được
```

### 6. Hướng dẫn cho người mới

Cần có flow onboarding tổng thể, ví dụ:

```text
/guide/getting-started
```

Nội dung nên dẫn người mới qua các bước chính:

```text
Tạo tài khoản
-> cài / tạo deck
-> học flashcard
-> cài thêm deck từ Marketplace
-> tùy chọn kết nối Anki / Yomitan / MCP
```

Không đưa các tính năng kỹ thuật nâng cao như MCP, API, Connect lên quá sớm trong flow cơ bản.

## Yêu cầu UX

- Trang chức năng phải đơn giản hơn sau khi tách guide.
- Guide và troubleshooting phải mở được bằng URL trực tiếp.
- URL phải có thể bookmark/share.
- Có breadcrumb trong khu vực `/guide`.
- Có navigation giữa các bài liên quan.
- Có CTA quay lại chức năng đang được hướng dẫn nếu phù hợp.
- Responsive tốt trên mobile.
- Không tạo thêm hàng loạt tab mới trong màn hình chức năng.

## Cần nghiên cứu trước khi triển khai

Nghiên cứu cách tổ chức Help Center / Docs của các sản phẩm SaaS phổ biến, đặc biệt cách họ kết hợp:

- in-app contextual help
- documentation riêng
- troubleshooting
- onboarding cho người mới
- search trong help center

Mục tiêu không phải copy giao diện mà chọn một information architecture phù hợp với Flama.

## Gợi ý kiến trúc component

Có thể nghiên cứu tách thành các component dùng chung:

```text
GuideLayout
GuideSidebar
GuideBreadcrumb
GuideArticle
GuideCard
ContextHelpButton
TroubleshootingButton
RelatedGuides
```

Không bắt buộc đúng tên trên; ưu tiên tái sử dụng và tránh hard-code layout riêng cho từng bài.

## Acceptance Criteria

- Có route `/guide` làm trang trung tâm hướng dẫn.
- Có route hướng dẫn riêng cho ít nhất Anki Sync, MCP và Yomitan.
- Có route troubleshooting riêng cho các chức năng trên.
- Các màn hình tương ứng có link/nút dẫn trực tiếp tới guide đúng ngữ cảnh.
- Các màn hình có vấn đề kết nối/cấu hình có nút **Sự cố / Khắc phục sự cố**.
- Các tab chỉ chứa nội dung hướng dẫn dài được loại bỏ hoặc giảm đáng kể khỏi UI chính.
- Có ít nhất một bài `/guide/getting-started` dành cho người mới.
- Kiến trúc guide có thể mở rộng cho Marketplace, Audio, Flama Connect và các tính năng khác sau này.
- Không làm thay đổi logic nghiệp vụ chính của các chức năng khi thực hiện refactor UI này.

## Ghi chú

Task này tập trung vào **information architecture + frontend UX + documentation UX**. Trước khi code cần rà soát các màn hình đang có tab hướng dẫn để xác định phần nào nên giữ inline, phần nào nên chuyển hoàn toàn sang `/guide/*`.
