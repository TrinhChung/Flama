---
name: Flama
description: "Hệ thống thiết kế giao diện học tập flashcard tinh gọn, tươi sáng và tràn đầy động lực"
colors:
  primary: "oklch(0.635 0.215 35)"
  primary-dark: "oklch(0.70 0.21 40)"
  neutral-bg: "oklch(1 0 0)"
  neutral-fg: "oklch(0.19 0.02 50)"
  neutral-muted: "oklch(0.96 0.015 65)"
  neutral-border: "oklch(0.9 0.025 60)"
  accent-warm: "oklch(0.94 0.04 55)"
  destructive: "oklch(0.577 0.245 27.325)"
  chart-emerald: "oklch(0.62 0.15 155)"
  chart-amber: "oklch(0.72 0.16 70)"
  chart-sky: "oklch(0.58 0.16 250)"
  chart-berry: "oklch(0.66 0.18 305)"
typography:
  display:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "oklch(0.58 0.22 35)"
  button-secondary:
    backgroundColor: "{colors.accent-warm}"
    textColor: "{colors.neutral-fg}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  card-surface:
    backgroundColor: "{colors.neutral-bg}"
    rounded: "{rounded.lg}"
    padding: "20px"
---

# Design System: Flama

## Overview

**Creative North Star: "The Focused Ember - Ngọn lửa tập trung và ấm áp"**

Flama mang đến không gian học tập tỉnh táo, tràn đầy năng lượng nhưng tuyệt đối không gây xao nhãng. Thiết kế tôn vinh nhịp điệu học ngắt quãng hàng ngày bằng sự kết hợp giữa gam màu cam lửa ấm áp làm điểm nhấn hành động, nền giấy sáng sạch sẽ, và kiểu chữ kỹ thuật hiện đại dễ quét.

Giao diện cự tuyệt các khuôn mẫu SaaS nhàm chán (như màu tím gradient nhân tạo, các khối card lồng card vô tận, hay hiệu ứng bóng đổ mờ mịt). Mỗi bề mặt được kiến tạo để phục vụ trực tiếp một tác vụ: gợi nhớ từ vựng, quản lý bộ thẻ, và nhìn nhận tiến bộ một cách trung thực, rõ ràng.

**Key Characteristics:**
- **Rõ ràng & Tỉnh táo:** Độ tương phản cao, phân cấp thị giác mạch lạc, loại bỏ mọi trang trí dư thừa.
- **Ấm áp có chủ đích:** Sắc cam Flama (`oklch(0.635 0.215 35)`) chỉ xuất hiện ở các điểm kích hoạt hành động quan trọng (CTA, nút lật thẻ, streak thành tích).
- **Phản hồi xúc giác & Chuyển động nhẹ:** Micro-interactions êm ái, thẻ 3D lật mượt mà không giật nảy.

---

## Colors

Bảng màu dựa trên không gian màu OKLCH hiện đại, với sự phân cấp rành mạch giữa màu hành động, màu nền ấm áp và màu trạng thái học tập.

### Primary
- **Flama Ember Orange** (`oklch(0.635 0.215 35)` / Dark: `oklch(0.70 0.21 40)`): Màu đại diện thương hiệu và hành động chính. Dùng cho nút CTA, trạng thái active, thanh tiến độ học và điểm nhấn thành tích.

### Secondary & Accent
- **Warm Sandstone** (`oklch(0.95 0.03 65)` / Dark: `oklch(0.269 0 0)`): Nền phụ cho các khu vực hỗ trợ, badge phụ và ô tìm kiếm.
- **Amber Glow** (`oklch(0.94 0.04 55)` / Dark: `oklch(0.269 0 0)`): Màu nhấn phụ cho trạng thái hover, thẻ đang chọn hoặc cảnh báo nhẹ.

### Neutral
- **Clean Canvas White** (`oklch(1 0 0)` / Dark: `oklch(0.145 0 0)`): Nền chính của ứng dụng và bề mặt thẻ.
- **Deep Charcoal Text** (`oklch(0.19 0.02 50)` / Dark: `oklch(0.985 0 0)`): Màu chữ chính, có độ ấm nhẹ thay vì màu đen thuần thô ráp.
- **Muted Stone** (`oklch(0.5 0.025 45)` / Dark: `oklch(0.708 0 0)`): Màu chữ phụ, caption, và nhãn không quan trọng.
- **Subtle Surface Border** (`oklch(0.9 0.025 60)` / Dark: `oklch(1 0 0 / 10%)`): Viền phân cách siêu nhẹ, thanh lịch.

### Semantic Status
- **Success / Mastered** (`oklch(0.62 0.15 155)`): Thẻ đã nhớ, hoàn thành phiên học.
- **Learning / Due Soon** (`oklch(0.72 0.16 70)`): Thẻ đang học, thẻ sắp đến hạn ôn.
- **Destructive / Reset** (`oklch(0.577 0.245 27.325)`): Xóa thẻ, cảnh báo nguy hiểm, quên từ.

### Named Rules
**The 10% Ember Rule.** Màu cam Primary chỉ chiếm tối đa 10% diện tích màn hình để giữ trọn vẹn sức mạnh thị giác của lời kêu gọi hành động.
**The No Gray On Color Rule.** Không bao giờ dùng chữ xám mờ trên nền màu ấm. Luôn dùng tông màu đậm cùng sắc độ hoặc chữ đen/trắng tương phản rõ ràng.

---

## Typography

Sử dụng kiểu chữ biến thiên **Geist Variable** với độ tinh chỉnh kerning và tracking tối ưu cho việc đọc từ vựng tiếng Nhật lẫn tiếng Việt/tiếng Anh.

- **Display Font:** Geist Variable (sans-serif)
- **Body Font:** Geist Variable (sans-serif)
- **Japanese Content Font:** `'Geist Variable', 'Noto Sans JP', 'Hiragino Sans', sans-serif`

### Hierarchy
- **Display** (Bold 700, 2.25rem / 36px, line-height 1.2, tracking -0.02em): Tiêu đề hero, thống kê thành tích lớn.
- **Headline** (SemiBold 600, 1.75rem / 28px, line-height 1.25, tracking -0.015em): Tiêu đề trang chính, tên bộ thẻ lớn.
- **Title** (SemiBold 600, 1.25rem / 20px, line-height 1.3, tracking -0.01em): Tiêu đề nhóm thẻ, modal header, card heading.
- **Body** (Regular 400, 0.9375rem / 15px, line-height 1.5): Nội dung giải nghĩa từ, đoạn văn, hướng dẫn.
- **Label** (Medium 500, 0.8125rem / 13px, tracking 0.01em): Nhãn nút, badge, thông tin phụ, tab navigation.

### Named Rules
**The Tabular Numerics Rule.** Toàn bộ số liệu thống kê (streak, số thẻ đến hạn, heatmap, thời gian đếm ngược) bắt buộc kích hoạt `font-variant-numeric: tabular-nums` để tránh nhảy layout khi cập nhật.
**The Solid Text Rule.** Không áp dụng hiệu ứng `bg-clip-text` hoặc gradient trên chữ đọc; chữ viết luôn mang màu đơn sắc rõ nét.

---

## Layout

Hệ thống lưới linh hoạt tối ưu hóa cho 3 dạng màn hình chính:
- **Mobile (< 640px):** Giao diện 1 cột toàn màn hình, thanh điều hướng đáy (Bottom Nav / Drawer) dễ với tới bằng ngón cái, touch target tối thiểu 44px.
- **Tablet (640px - 1024px):** Layout 2 cột, thanh Sidebar có thể thu gọn.
- **Desktop (> 1024px):** Sidebar cố định bên trái (256px), khu vực nội dung trung tâm căn giữa với max-width 1280px.

**Rhythm & Spacing Scale:**
- Base đơn vị: 4px (`xs: 4px`, `sm: 8px`, `md: 16px`, `lg: 24px`, `xl: 32px`, `2xl: 48px`).
- Khoảng cách giữa các khối nội dung lớn: `gap-6` (24px) đến `gap-8` (32px).
- Khoảng cách padding trong thẻ (Card): 16px (mobile) hoặc 20px - 24px (desktop).

---

## Elevation & Depth

Triết lý **Flat-By-Default**: Bề mặt giao diện phẳng ở trạng thái tĩnh. Độ sâu thị giác được tạo nên bởi các lớp viền tinh tế (`border-border`) và tương phản nền, thay vì bóng đổ nặng nề.

### Shadow Vocabulary
- **Resting Surface:** Không có shadow (`box-shadow: none`). Phân tách bằng viền mỏng 1px `border-border`.
- **Card Hover:** `box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.05)` kết hợp nâng nhẹ `translateY(-1px)`.
- **Floating Overlay / Modal:** `box-shadow: 0 16px 48px -8px rgba(0, 0, 0, 0.12)` tạo cảm giác nổi rõ ràng phía trên backdrop làm mờ nhẹ.
- **3D Card Flip:** Hiệu ứng chiều sâu `perspective(1000px)` với `transform-style: preserve-3d` cho trải nghiệm lật thẻ học.

### Named Rules
**The Ghost Border Rule.** Mọi thẻ và container đều có viền 1px mỏng để giữ vững cấu trúc hình học ở cả chế độ Light và Dark.

---

## Shapes

- **Bo góc chuẩn:**
  - Nút bấm, Ô nhập liệu (Inputs), Badges: `rounded-md` (8px).
  - Khối chứa (Cards, Modals, Panels): `rounded-lg` (10px) hoặc `rounded-xl` (14px).
  - Tags trạng thái, Avatar: `rounded-full` (9999px).
- **Cấm:** Không sử dụng bo góc bất đối xứng ngẫu nhiên hoặc bo góc quá gắt (0px góc vuông nhọn) làm mất đi vẻ thân thiện của sản phẩm.

---

## Components

### Buttons
- **Primary:** Nền `colors.primary`, chữ trắng, bo góc `rounded-md`, padding `8px 16px`. Hover: màu cam đậm hơn, chuyển động màu 150ms.
- **Secondary:** Nền `colors.accent-warm`, chữ `colors.neutral-fg`, không viền. Hover: nền ấm hơn.
- **Outline / Ghost:** Nền trong suốt, viền 1px mỏng `border-border`. Hover: nền `colors.neutral-muted`.

### Cards & Containers
- Nền trắng `colors.neutral-bg`, viền mỏng 1px, padding 20px, bo góc 10px.
- Tuyệt đối không bọc một thẻ Card bên trong một thẻ Card khác trừ khi là danh sách con có nền phân tách rõ ràng.

### Inputs & Selects
- Chiều cao chuẩn 40px, viền 1px `colors.neutral-border`, nền sáng.
- Focus: viền chuyển màu `colors.primary` kèm vòng sáng ring `ring-2 ring-primary/20`.

### Flashcard Study Surface (Signature Component)
- Tỷ lệ hiển thị tối ưu cho Kanji, Hiragana và nghĩa từ vựng.
- Lật thẻ 3D tức thì khi ấn phím Space/Enter hoặc click chuột, hiển thị rõ ràng 4 mức độ đánh giá: *Again (Quên)*, *Hard (Khó)*, *Good (Được)*, *Easy (Dễ)* với màu sắc phân định trực quan.

### Study Heatmap (Signature Component)
- Lưới hoạt động 52 tuần x 7 ngày với 5 cấp độ màu cam từ nhạt đến đậm dần theo số lượng thẻ ôn tập, có tooltip chi tiết khi hover.

---

## Do's and Don'ts

### Do:
- **Do** giữ cho giao diện học tập sạch sẽ, tập trung tối đa vào nội dung chữ tiếng Nhật và thao tác ôn luyện.
- **Do** dùng màu cam `oklch(0.635 0.215 35)` làm màu hành động chính trên toàn bộ ứng dụng.
- **Do** hỗ trợ phím tắt (`Space`, `1`, `2`, `3`, `4`, `Ctrl+Z`) cho tất cả các thao tác học và duyệt từ.
- **Do** hiển thị thông báo trạng thái rõ ràng (Empty states, Skeleton loading, Error messages hữu ích).

### Don't:
- **Don't** dùng các gradient tím/chàm (`from-purple-500`, `from-indigo-500`) đặc trưng của AI generic.
- **Don't** dùng text gradient (`bg-clip-text`) trên các tiêu đề hoặc số liệu.
- **Don't** tạo viền màu dày ở một cạnh của card (`border-l-4`) làm giao diện bị thô.
- **Don't** dùng chữ xám mờ trên nền màu (`text-gray-600` trên `bg-orange-50`).
- **Don't** lồng nhiều lớp card với nhau (`Card` bên trong `CardContent` của `Card` cha).
