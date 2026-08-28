# Task Frontend — Đồng bộ UX Marketplace / Installed Decks và luồng Deck khóa học

## Mục tiêu

Chuẩn hóa trải nghiệm giữa màn Marketplace và màn Deck đã cài, giảm khác biệt về card/layout/filter, đồng thời làm rõ luồng phân phối deck bằng key cho lớp học/khóa học.

Các màn liên quan chính:

- `/marketplace/decks`
- `/installed-decks`
- `/marketplace/decks/:id`
- màn tạo/chỉnh sửa Marketplace Deck
- màn quản lý key của creator

---

## 1. Dùng chung mẫu Deck Card cho Marketplace và Installed Decks

Hiện card ở `/marketplace/decks` và `/installed-decks` có cấu trúc và styling khác nhau.

### Yêu cầu

- Tách deck card thành component dùng chung.
- Giữ cùng:
  - kích thước card
  - spacing
  - typography
  - category/taxonomy badge
  - author
  - description
  - metadata chính
  - hover state
  - responsive layout
- Chỉ thay đổi action/footer theo context.

### Marketplace card

Có thể hiển thị các action như:

- Xem chi tiết
- Cài đặt / tải deck
- Đã cài
- Mua / nhận quyền truy cập nếu deck có phí
- Trạng thái yêu cầu key nếu là deck lớp học

### Installed Deck card

Có thể hiển thị các action như:

- Học ngay
- Xem chi tiết
- Xem cập nhật
- Đóng góp chỉnh sửa
- Các trạng thái riêng của deck đã cài

Không duplicate hai bộ UI card riêng nếu khác biệt chỉ nằm ở actions/state.

---

## 2. Thêm bộ lọc cho `/installed-decks`

Màn `/installed-decks` cần có trải nghiệm tìm kiếm/lọc gần giống `/marketplace/decks`.

### Tối thiểu cần hỗ trợ

- Search theo tên deck
- Lọc theo lĩnh vực / domain
- Lọc theo subject
- Lọc theo framework / level nếu có
- Lọc theo difficulty
- Lọc theo category/topic
- Lọc theo trạng thái:
  - Đang sử dụng
  - Đã cài
  - Deck của tôi
  - Có bản cập nhật

Ưu tiên tái sử dụng filter component và taxonomy schema hiện có của Marketplace thay vì xây bộ lọc độc lập.

---

## 3. Nghiên cứu cách nhóm các chủ đề lớn thành section/block

Ở cả `/marketplace/decks` và `/installed-decks`, khi số lượng deck tăng nhiều, một grid phẳng duy nhất sẽ khó scan.

Cần nghiên cứu UX theo các nền tảng marketplace/e-commerce/content catalog lớn trước khi chốt giao diện.

### Hướng nghiên cứu

Tham khảo cách các nền tảng như:

- Amazon
- Udemy
- Coursera
- Steam
- App Store / Google Play
- các marketplace nội dung số khác

xử lý:

- category lớn
- collection
- featured section
- personalized section
- continue learning / recently used
- popular / newest
- group theo topic

### Mục tiêu UX

Nếu một chủ đề lớn có đủ nhiều deck, nên tách thành block/section rõ ràng, ví dụ:

```text
Tiếng Nhật
[deck] [deck] [deck] [deck]
Xem tất cả →

Tiếng Anh
[deck] [deck] [deck] [deck]
Xem tất cả →

Công nghệ & IT
[deck] [deck] [deck] [deck]
Xem tất cả →
```

Không bắt buộc dùng chính xác layout này. Cần nghiên cứu và chọn phương án phù hợp với Flama.

### Lưu ý

- Khi user đang search hoặc filter cụ thể, có thể chuyển về result grid/list thay vì chia section.
- Không nên chia section nếu mỗi section chỉ có 1–2 item.
- Cần xác định threshold hợp lý trước khi nhóm.
- Thiết kế phải responsive tốt trên mobile.

---

## 4. Di chuyển chức năng nhập key khỏi trang Marketplace listing

Hiện chức năng nhập mã kích hoạt/key không nên chiếm vị trí ở màn danh sách `/marketplace/decks`.

### Yêu cầu

- Bỏ entry nhập key khỏi trang Marketplace listing.
- Chỉ hiển thị phần nhập key trong trang chi tiết deck `/marketplace/decks/:id` khi deck yêu cầu key.
- User cần hiểu mình đang nhập key cho deck cụ thể nào trước khi redeem.

---

## 5. Phân biệt rõ Deck lớp học / Deck khóa học

Với deck được creator cấu hình phân phối bằng key, cần thể hiện đây không phải deck marketplace thông thường.

### UI ở card/detail

Deck loại này cần có badge/trạng thái rõ ràng, ví dụ:

- `Deck lớp học`
- `Yêu cầu mã khóa học`

Khi user mở deck, hiển thị thông báo dạng:

> Đây là bộ thẻ dành cho học viên của một lớp học/khóa học. Bạn cần tham gia khóa học và nhận mã truy cập từ giảng viên/nhà sáng tạo để tải bộ thẻ này.

Không dùng wording gây hiểu nhầm rằng user có thể mua hoặc tải trực tiếp từ Marketplace nếu creator không cho phép.

---

## 6. Cho creator thêm link và mô tả khóa học

Khi deck sử dụng key cho lớp học, creator có thể khai báo thêm thông tin khóa học.

### Dữ liệu cần hỗ trợ

- Tên khóa học / lớp học nếu cần
- Mô tả ngắn về khóa học
- Link khóa học / trang đăng ký / landing page

### Hiển thị ở Deck Detail

Nếu deck là deck lớp học:

- hiển thị mô tả khóa học
- hiển thị link khóa học
- CTA phù hợp, ví dụ:
  - `Xem khóa học`
  - `Tham gia khóa học để nhận key`
- sau đó mới hiển thị khu vực nhập key

Link phải mở an toàn và không làm user hiểu rằng Flama tự xác nhận việc mua/đăng ký ở website ngoài.

---

## 7. Đưa cấu hình Key Distribution vào cùng luồng tạo/chỉnh sửa Deck

Hiện quản lý key đang tách khỏi luồng cấu hình listing.

Cần đưa lựa chọn **phương thức phân phối deck** vào wizard tạo/chỉnh sửa Marketplace Deck, cùng khu vực với `Miễn phí / Trả phí`.

### Đề xuất mô hình phân phối

Không chỉ dùng boolean `has_key` đơn lẻ. UI nên thể hiện rõ các mode, ví dụ:

1. `Miễn phí`
2. `Trả phí`
3. `Dành cho khóa học / Yêu cầu key`

Tên cuối cùng cần thống nhất theo UX copy của Flama.

### Khi chọn `Dành cho khóa học / Yêu cầu key`

Hiển thị thêm các field:

- Course/Class name
- Course description
- Course URL
- Hướng dẫn nhận key nếu cần

Sau khi lưu/xuất bản, creator có thể quản lý/tạo key cho deck đó.

Không bắt creator đi sang một màn hoàn toàn khác chỉ để bật chế độ phân phối bằng key.

---

## 8. Quản lý key sau khi đã bật chế độ khóa học

`DeckAccessKeysManager` vẫn có thể là nơi quản lý chi tiết key sau khi deck đã được cấu hình là deck lớp học.

### Chức năng giữ lại

- tạo key
- revoke/reactivate
- giới hạn số lượt dùng
- thời hạn kích hoạt
- thời gian truy cập
- xem danh sách redemption
- copy key
- copy share link

Nhưng entry point cần hợp lý hơn:

```text
Create/Edit Deck
→ Distribution = Course/Key
→ Save
→ Manage course access keys
```

---

## 9. Data/API dependency cần kiểm tra

Đây là task frontend/UX nhưng cần kiểm tra API hiện tại có đủ dữ liệu hay không.

Có thể cần bổ sung contract cho Marketplace Deck:

```text
distribution_mode
course_title
course_description
course_url
requires_access_key
```

Tên field chỉ là gợi ý, không bắt buộc dùng nguyên dạng.

Không nhét các dữ liệu khóa học vào `description` hoặc `taxonomy_metadata` nếu về mặt domain chúng là thuộc tính riêng của listing/distribution.

Cần đảm bảo API list/detail trả đủ thông tin để frontend không phải gọi N+1 request chỉ để render card/section.

---

## 10. Component architecture

Ưu tiên refactor theo hướng reusable:

```text
DeckCard
├─ DeckCardHeader
├─ DeckCardMetadata
├─ DeckCardDescription
└─ DeckCardActions
   ├─ MarketplaceActions
   └─ InstalledDeckActions
```

Filter cũng nên tái sử dụng:

```text
DeckCatalogFilters
├─ search
├─ taxonomy
├─ difficulty
├─ category/topic
└─ context-specific filters
```

Không bắt buộc đúng cấu trúc component trên, nhưng implementation cần tránh duplicate logic giữa hai màn.

---

## Acceptance Criteria

- `/marketplace/decks` và `/installed-decks` dùng cùng visual language cho Deck Card.
- Phần khác nhau giữa hai màn chủ yếu là actions và state, không phải hai thiết kế card riêng biệt.
- `/installed-decks` có search/filter tương đương Marketplace ở các tiêu chí phù hợp.
- Khi catalog lớn, UI hỗ trợ chia deck theo section/category hợp lý dựa trên nghiên cứu marketplace/e-commerce.
- Khi search/filter cụ thể, result vẫn dễ scan và không bị chia section quá mức.
- Không còn khu vực nhập key ở Marketplace listing.
- Input key chỉ xuất hiện tại detail của deck yêu cầu key.
- Deck khóa học có badge/copy riêng, không bị hiểu nhầm với deck free/paid thông thường.
- Creator có thể cấu hình distribution mode ngay trong luồng tạo/chỉnh sửa deck.
- Khi chọn chế độ khóa học/key, creator có thể thêm mô tả và link khóa học.
- Detail page hiển thị course info và CTA tham gia khóa học trước phần nhập key.
- Creator vẫn có màn quản lý key chi tiết sau khi bật chế độ course/key.
- Không làm mất các chức năng update, study, contribution hiện có của Installed Deck.
- Responsive tốt trên mobile/tablet/desktop.
- Có test cho component/shared behavior và các trạng thái distribution chính.

---

## Out of scope ban đầu

- Xây hệ thống LMS hoàn chỉnh trong Flama.
- Thanh toán khóa học bên ngoài Flama.
- Tự động xác minh user đã mua khóa học ở website bên ngoài.
- Affiliate tracking.
- Recommendation engine phức tạp.

Task này tập trung vào **catalog UX, card consistency, filtering và course/key distribution UX**.
