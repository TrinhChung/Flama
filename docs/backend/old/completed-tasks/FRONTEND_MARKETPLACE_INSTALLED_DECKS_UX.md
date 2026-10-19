# Task Frontend — Đồng bộ UX Marketplace / Installed Decks và luồng Deck khóa học

> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-28  
> **Target branch:** `develop`  
> **Commit SHA:** `99e5ba5a`

## Mục tiêu

Chuẩn hóa trải nghiệm giữa màn Marketplace và màn Deck đã cài, giảm khác biệt về card/layout/filter, đồng thời làm rõ luồng phân phối deck bằng key cho lớp học/khóa học.

Các màn liên quan chính:

- `/marketplace/decks`
- `/installed-decks`
- `/marketplace/decks/:id`
- màn tạo/chỉnh sửa Marketplace Deck (`/marketplace/decks/publish`)
- màn quản lý key của creator (`DeckAccessKeysManager`)

---

## 1. Dùng chung mẫu Deck Card cho Marketplace và Installed Decks

Hiện card ở `/marketplace/decks` và `/installed-decks` đã được hợp nhất vào một component duy nhất.

### Đã thực hiện

- Component dùng chung: [`frontend/src/features/marketplace/components/DeckCard.tsx`](file:///d:/Project/nihongo/frontend/src/features/marketplace/components/DeckCard.tsx)
- Đảm bảo đồng bộ 100%:
  - Kích thước card & bo góc `rounded-2xl`
  - Spacing & padding
  - Typography & màu sắc thương hiệu
  - Category/taxonomy badge theo ngữ cảnh (`getCategoryBadgeStyle`)
  - Author avatar & tên người đóng góp
  - Description vắn tắt `line-clamp-2`
  - Metadata chính (rating, lượt tải, số từ/bài)
  - Hover state & responsive layout
- Phân nhánh action/footer theo prop `variant="marketplace" | "installed"`.

---

## 2. Bộ lọc cho `/installed-decks`

Màn `/installed-decks` đã được trang bị **Control Center** tìm kiếm và lọc tương đương `/marketplace/decks`.

### Đã hỗ trợ

- Search theo tên deck / mô tả / tác giả (hỗ trợ debounce & phím tắt toàn cục `/`)
- Quick Category Pills lướt ngang (Tất cả, Tiếng Nhật, Tiếng Anh, Tiếng Trung, Tiếng Hàn, Công nghệ & IT, v.v.)
- Lọc theo trạng thái tab:
  - Tất cả
  - Đang dùng (`using_now`)
  - Có bản mới (`update_available`)
- Bộ lọc taxonomy mở rộng:
  - Trạng thái deck (*Đang sử dụng, Đã cài, Deck của bạn, Có bản cập nhật, Có xung đột*)
  - Lĩnh vực (Domain)
  - Môn học (Subject)
  - Trình độ / Khung (Framework Level)
  - Độ khó (Difficulty)
- Active filter badges với thao tác gỡ nhanh từng bộ lọc hoặc "Xóa tất cả".

---

## 3. Nhóm các chủ đề lớn thành section/block (Curated Section Blocks)

Đã nghiên cứu và triển khai logic phân nhóm Section Blocks khi duyệt tổng thể:

- **Khi không lọc (`!isFiltered` và số lượng deck >= 5)**:
  - Tự động gom nhóm các chủ đề có từ 3 deck trở lên.
  - Render Section Header: Tiêu đề danh mục, Badge, số lượng deck, nút CTA **"Xem tất cả {Category} →"**.
  - Hiển thị 4 deck tiêu biểu trên mỗi section, các deck lẻ được đưa vào mục "Học liệu & Chủ đề khác".
- **Khi tìm kiếm hoặc lọc cụ thể (`isFiltered`)**:
  - Tự động chuyển về **Flat Result Grid** giúp người dùng quét và so sánh kết quả nhanh chóng.

---

## 4. Tinh chỉnh Chức năng Nhập Key (Redeem Key Flow)

- **Gỡ bỏ entry nhập key khỏi trang danh sách `/marketplace/decks`**: Loại bỏ button và modal nhập key không có ngữ cảnh ở header listing.
- **Đưa về đúng ngữ cảnh**:
  - Card deck khóa học trên catalog hiển thị nút **"Xem khóa học & Nhập mã"**.
  - Trang chi tiết `/marketplace/decks/:id` hiển thị nút **"Nhập mã kích hoạt khóa học"** nổi bật kèm **Course Notice Banner**.

---

## 5. Phân biệt rõ Deck lớp học / Deck khóa học

- **Huy hiệu nhận diện**: Badge `Mã khóa học` / `Khóa học` với tông màu tím sang trọng (`purple-500`), icon `KeyRound` & `GraduationCap`.
- **Course Notice Banner**:
  > Học liệu độc quyền dành cho Khóa học  
  > Bộ thẻ này được thiết kế và quản lý bởi giảng viên cho lớp học cụ thể. Học viên cần có **Mã kích hoạt (Access Key)** từ giảng viên hoặc trung tâm để mở khóa và học tập.

---

## 6. Cho creator thêm link và mô tả khóa học

Hỗ trợ đầy đủ các trường thông tin khóa học:
- Tên khóa học (`course_title`)
- Mô tả ngắn về khóa học (`course_description`)
- Link khóa học / trang đăng ký (`course_url` - mở an toàn với `rel="noopener noreferrer"`)
- Hướng dẫn học viên nhận mã (`course_instructions`)

---

## 7. Tích hợp cấu hình phân phối vào wizard đăng tải Deck

Cập nhật Step 4 (`PublishStep4Pricing.tsx`) trong [`MarketplacePublishDeckPage.tsx`](file:///d:/Project/nihongo/frontend/src/features/marketplace/pages/MarketplacePublishDeckPage.tsx):
- 3 lựa chọn trực quan:
  1. 🟢 **Miễn phí (Free)**: Chia sẻ tự do tới cộng đồng.
  2. 🔵 **Có phí (Paid)**: Bán có phí qua cổng payOS, cấu hình giảm giá cho sinh viên.
  3. 🟣 **Mã lớp học (Course / Access Keys)**: Kích hoạt bằng mã lớp học, kèm form nhập thông tin khóa học.

---

## 8. Quản lý key sau khi bật chế độ khóa học

Creator có thể truy cập trực tiếp trình quản lý mã `DeckAccessKeysManager` từ nút **"Mã lớp học (Keys)"** trên trang chi tiết [`SharedDeckDetailPage.tsx`](file:///d:/Project/nihongo/frontend/src/features/marketplace/pages/SharedDeckDetailPage.tsx) để:
- Tạo mã đơn lẻ hoặc sinh mã hàng loạt
- Thiết lập hạn dùng, số lượt kích hoạt
- Theo dõi danh sách học viên đã kích hoạt
- Thu hồi / cấp lại mã

---

## 9. Backend & Database Schema

- Cột mới trên `deck_marketplace_items`:
  - `distribution_mode` (VARCHAR 32)
  - `course_title` (VARCHAR 255)
  - `course_description` (TEXT)
  - `course_url` (VARCHAR 500)
  - `course_instructions` (TEXT)
- Startup schema compatibility migration trong `app/startup_schema.py`.
- Serialization và format giá trong `app/services/marketplace_query_service.py`.
- Payload handler trong `app/services/flashcards_share_service.py`.

---

## 10. Acceptance Criteria Checklist

- [x] `/marketplace/decks` và `/installed-decks` dùng cùng visual language cho Deck Card (`DeckCard.tsx`).
- [x] Phần khác nhau giữa hai màn chủ yếu là actions và state, không phải hai thiết kế card riêng biệt.
- [x] `/installed-decks` có search/filter tương đương Marketplace ở các tiêu chí phù hợp.
- [x] Khi catalog lớn, UI hỗ trợ chia deck theo section/category hợp lý dựa trên nghiên cứu marketplace/e-commerce.
- [x] Khi search/filter cụ thể, result vẫn dễ scan và không bị chia section quá mức.
- [x] Không còn khu vực nhập key ở Marketplace listing.
- [x] Input key chỉ xuất hiện tại detail của deck yêu cầu key.
- [x] Deck khóa học có badge/copy riêng, không bị hiểu nhầm với deck free/paid thông thường.
- [x] Creator có thể cấu hình distribution mode ngay trong luồng tạo/chỉnh sửa deck.
- [x] Khi chọn chế độ khóa học/key, creator có thể thêm mô tả và link khóa học.
- [x] Detail page hiển thị course info và CTA tham gia khóa học trước phần nhập key.
- [x] Creator vẫn có màn quản lý key chi tiết sau khi bật chế độ course/key.
- [x] Không làm mất các chức năng update, study, contribution hiện có của Installed Deck.
- [x] Responsive tốt trên mobile/tablet/desktop.
- [x] Có test cho component/shared behavior và các trạng thái distribution chính (`DeckCard.test.tsx`).

---

## Kết quả kiểm thử

- **Frontend Tests (Vitest)**: 37/37 test files, **189 / 189 tests passed** (100%).
- **Frontend Build**: `npm run build` hoàn thành trong **2.38s**.
- **Backend Tests (Python 3.12 unittest)**: 100% passed cho toàn bộ test suite liên quan.
