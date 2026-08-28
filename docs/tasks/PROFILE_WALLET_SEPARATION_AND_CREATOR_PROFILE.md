# Task: Tách trang cá nhân và ví, thiết kế lại Profile theo hướng creator/contributor

## Mục tiêu

Tách chức năng **Ví** khỏi **Trang cá nhân** để giảm độ rối của UI và làm rõ trách nhiệm của từng màn.

Đồng thời nghiên cứu và thiết kế lại **Trang cá nhân / Profile** theo hướng một hồ sơ người dùng có giá trị trong hệ sinh thái Flama, đặc biệt với người tạo Deck, người đóng góp nội dung và người có hoạt động cộng đồng.

## Phạm vi chính

### 1. Tách màn Ví ra khỏi Trang cá nhân

Hiện tại các thông tin tài khoản cá nhân và ví đang bị đặt quá gần nhau hoặc cùng một khu vực, khiến màn hình khó mở rộng khi thêm nhiều thông tin profile.

Cần tách thành hai route độc lập, ví dụ:

- `/profile` hoặc `/profile/:username`
- `/wallet`

Không bắt buộc giữ chính xác route trên nếu kiến trúc routing hiện tại có quy ước khác, nhưng cần đảm bảo Profile và Wallet là hai màn chức năng độc lập.

#### Wallet

Màn Wallet tập trung riêng vào các nội dung tài chính, ví dụ:

- số dư
- lịch sử giao dịch
- doanh thu từ Deck
- thanh toán / rút tiền nếu có
- các khoản pending
- thông tin liên quan đến marketplace payment

Không để các thành phần này chen vào trang Profile.

### 2. Thiết kế lại Trang cá nhân

Trang cá nhân không chỉ là màn chỉnh sửa username/email mà cần trở thành hồ sơ đại diện cho một người dùng Flama.

Cần nghiên cứu cấu trúc profile của các nền tảng có creator/community system như GitHub, Udemy, Coursera, Medium, Gumroad, Notion Marketplace, Figma Community hoặc các marketplace tương tự để tìm cấu trúc phù hợp với Flama.

Không copy nguyên thiết kế của nền tảng khác; cần chọn các pattern phù hợp với sản phẩm học tập và marketplace của Flama.

### 3. Ảnh đại diện

Cho phép người dùng upload và thay đổi ảnh đại diện.

Cần nghiên cứu và xác định:

- crop/resize ảnh
- giới hạn dung lượng
- định dạng file hỗ trợ
- fallback avatar
- xử lý ảnh lỗi
- cache/version ảnh
- quyền riêng tư nếu cần

UX cần đơn giản, không biến việc đổi avatar thành một flow phức tạp.

### 4. Giới thiệu bản thân

Cho phép người dùng viết một đoạn giới thiệu ngắn về bản thân.

Ví dụ nội dung có thể gồm:

- đang học hoặc giảng dạy lĩnh vực nào
- trình độ/ngôn ngữ quan tâm
- kinh nghiệm
- mục tiêu học tập
- thông tin về lớp học hoặc dự án nội dung

Cần nghiên cứu giới hạn độ dài phù hợp và cách hiển thị sao cho profile vẫn gọn.

### 5. Các liên kết liên quan

Cho phép người dùng thêm một số link bên ngoài có kiểm soát, ví dụ:

- website cá nhân
- GitHub
- YouTube
- Facebook
- X/Twitter
- LinkedIn
- trang khóa học
- các nền tảng khác phù hợp

Cần có validation URL và thiết kế để tránh biến profile thành khu vực spam link.

Có thể nghiên cứu mô hình:

- danh sách link với type + URL
- giới hạn số lượng link
- icon theo platform
- custom label khi cần

### 6. Thành tích và hoạt động trên Flama

Profile cần thể hiện được đóng góp thực tế của người dùng trong hệ sinh thái Flama.

Cần nghiên cứu các loại dữ liệu và chỉ số nên hiển thị, tối thiểu xem xét:

#### Deck đã tạo

- các Deck đang publish
- số Deck đã tạo
- tổng lượt cài đặt/tải
- tổng số người sử dụng nếu có
- Deck nổi bật

#### Đóng góp vào Deck khác

Hiển thị các dự án/Deck mà user đã đóng góp.

Có thể bao gồm:

- số contribution đã gửi
- số contribution được chấp nhận/merge
- Deck đã tham gia đóng góp
- loại đóng góp nếu dữ liệu hiện tại hỗ trợ

Không hiển thị các metric không có ý nghĩa hoặc dễ bị game hóa nếu chưa có dữ liệu đáng tin cậy.

#### Đánh giá / uy tín

Nghiên cứu cách hiển thị các thông tin như:

- rating trung bình của các Deck do user tạo
- tổng số lượt đánh giá nhận được
- số review
- số lượt cài đặt
- số contribution được chấp nhận

Không nên gom tất cả thành một điểm reputation duy nhất nếu chưa có mô hình rõ ràng.

Trước tiên ưu tiên hiển thị các số liệu gốc và dễ hiểu.

### 7. Thành tích / badge

Nghiên cứu khả năng có các badge hoặc milestone trên Flama, ví dụ:

- Creator
- Contributor
- Deck có X lượt cài đặt
- Deck được đánh giá cao
- đóng góp cho nhiều Deck
- early creator

Phần này là **research trước**, không bắt buộc triển khai badge system ngay nếu backend chưa hỗ trợ.

Cần tránh badge mang tính trang trí nhưng không phản ánh thành tích thật.

### 8. Public Profile và Edit Profile

Nghiên cứu tách hai trạng thái:

- **Public profile**: người khác xem
- **Edit profile**: chủ tài khoản chỉnh sửa

Ví dụ route có thể là:

- `/profile/:username`
- `/settings/profile`

hoặc một cấu trúc khác phù hợp với routing hiện tại.

Không nên để toàn bộ form chỉnh sửa xuất hiện trực tiếp trên public profile.

### 9. Liên kết Profile với Marketplace

Từ các khu vực như:

- Deck card
- Deck detail
- review
- contribution

khi nhấn vào tên/avatar tác giả hoặc contributor, cần có khả năng đi đến profile tương ứng.

Profile trở thành nơi trả lời câu hỏi:

> Người này là ai, đã tạo gì trên Flama, đã đóng góp những gì và nội dung của họ có uy tín như thế nào?

### 10. Nghiên cứu Information Architecture

Trước khi triển khai cần nghiên cứu cách chia các khối trên Profile.

Một hướng tham khảo:

1. Header
   - avatar
   - display name
   - username
   - bio
   - links

2. Summary metrics
   - Deck đã tạo
   - lượt cài đặt
   - rating/reviews
   - contributions

3. Created Decks

4. Contributions

5. Activity / Achievements nếu có giá trị

Không bắt buộc dùng cấu trúc này. Cần nghiên cứu để tránh biến profile thành dashboard quá nhiều số liệu.

## UX requirements

- Mobile responsive.
- Profile public phải dễ đọc, không giống trang Settings.
- Wallet phải tách biệt rõ về navigation và visual hierarchy.
- Không đưa thông tin tài chính lên public profile.
- Không làm Profile thành nơi chứa mọi setting của tài khoản.
- Các metric phải có ý nghĩa và có nguồn dữ liệu rõ ràng.
- Với metric chưa có backend support, ghi rõ dependency thay vì fake dữ liệu ở frontend.

## Technical investigation

Trước khi code cần kiểm tra:

- model/profile hiện tại
- API user/account hiện tại
- nơi đang lưu avatar nếu đã có
- quan hệ giữa user và DeckMarketplaceItem
- contribution/change request data
- rating/review data
- wallet/payment data
- các route/profile/settings hiện tại

Sau đó xác định rõ phần nào:

- chỉ cần frontend refactor
- cần API mới
- cần schema/model mới
- cần migration

## Deliverables

- Đề xuất Information Architecture cho Profile và Wallet.
- Đề xuất route mới.
- Tách Wallet khỏi Profile.
- Public Profile.
- Edit Profile.
- Upload avatar.
- Bio và external links.
- Hiển thị Deck đã tạo.
- Hiển thị contribution phù hợp với dữ liệu hiện có.
- Hiển thị rating/review/marketplace metrics phù hợp.
- Research badge/achievement/reputation system và ghi rõ phần nào nên làm ngay, phần nào để phase sau.
- Responsive desktop/mobile.
- Tests cho các flow chính.

## Acceptance criteria

- Profile và Wallet không còn là cùng một màn chức năng.
- Người dùng có thể cập nhật avatar và bio.
- Người dùng có thể thêm các link được hỗ trợ.
- Public profile thể hiện được danh tính và đóng góp của user trên Flama.
- Có khu vực hiển thị các Deck do user tạo.
- Có thiết kế cho contribution history hoặc contribution summary.
- Có các marketplace metrics có ý nghĩa như rating/review/install khi dữ liệu hỗ trợ.
- Không hiển thị thông tin Wallet/tài chính trên public profile.
- Các tác giả/creator trong Marketplace có thể liên kết đến profile tương ứng.
- Profile hoạt động tốt trên mobile và desktop.
- Các metric hoặc achievement chưa có backend support phải được xác định rõ là dependency, không mock như dữ liệu production.

## Ghi chú triển khai

Task này yêu cầu **research UX/product trước khi chốt UI cuối cùng**. Không triển khai bằng cách chỉ lấy màn profile hiện tại rồi thêm nhiều tab mới, vì mục tiêu chính là giảm độ rối và tạo Information Architecture rõ ràng cho user identity, creator identity và financial features.