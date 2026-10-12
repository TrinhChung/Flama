# KẾ HOẠCH THIẾT KẾ MÀN HÌNH GIỚI THIỆU GIÁ TRỊ (VALUE PROPOSITION)
## CHO BẬC THẦY ĐỌC HIỂU (YOMITAN), CAO THỦ LUYỆN NGHE (ASBPLAYER) & KẾT NỐI AI (MCP)

> **Mục tiêu**: Đứng trên góc nhìn của một người dùng mới hoàn toàn không biết gì về kỹ thuật để trả lời hai câu hỏi lớn:
> 1. *Tại sao mình phải dùng công cụ này?*
> 2. *Kết hợp công cụ này với Flama sẽ mang lại lợi ích gì cho việc học của mình?*

---

## I. NGUYÊN TẮC THIẾT KẾ: BÀI TRỪ "UI AI", BẢO TOÀN THEME FLAMA

### 1. Tuyệt đối tránh xa "Kiểu UI AI" (Anti-AI Slop)
- ❌ **Không gradient tím-hồng vũ trụ (Cosmic/Neon Purple Gradient)**: Thường thấy ở các template AI giả tạo, gây cảm giác chói mắt và xa lạ với ứng dụng học tập.
- ❌ **Không lạm dụng icon phép thuật (Magic Wand, Wizard Hat, Sparkles bừa bãi)**: Công cụ học tập là phương pháp khoa học (Spaced Repetition, Immersion), không phải trò ảo thuật.
- ❌ **Không copywriting sáo rỗng vô hồn**: Tránh các câu chữ như *"Trải nghiệm tương lai của công nghệ AI đỉnh cao đột phá"*. Thay vào đó, dùng câu từ chân thực, ngắn gọn, chỉ thẳng vào việc học hàng ngày (đọc báo, xem anime, ôn từ vựng).
- ❌ **Không bong bóng chat giả tạo**: Tránh vẽ các khung chat AI hoạt hình không có chức năng thực tế.

### 2. Tuân thủ 100% Theme & Design System Flama
- ✅ **Bảng màu Flama Hỏa (Warm Flame Palette)**:
  - Tone chủ đạo: Warm Flame (`primary: oklch(0.635 0.215 35)`), cam ấm hổ phách (`amber-500`), cam lửa (`orange-500`).
  - Điểm xuyết chức năng chuẩn Flama: `emerald-500` (thành công / thẻ được lưu), `sky-500` (liên kết / hướng dẫn tra cứu), `rose-500` (nỗi đau / cảnh báo lỗi).
- ✅ **Typography**: Chuẩn font Geist (`@fontsource-variable/geist`), phân cấp rõ ràng:
  - Tiêu đề mục: `text-base sm:text-lg font-bold tracking-tight text-foreground`
  - Chú thích / Giải thích: `text-xs sm:text-sm text-muted-foreground leading-relaxed`
  - Nhãn trạng thái / Badge: `text-[11px] font-semibold px-2 py-0.5 rounded-md`
- ✅ **Cấu trúc Card & Primitives (Radix / Tailwind)**:
  - Nền: `bg-card` kết hợp viền tinh tế `border border-border/60` và đổ bóng nhẹ `shadow-2xs` hoặc `shadow-xs`.
  - Phù hợp hoàn hảo với cả **Light Mode** và **Dark Mode**.
- ✅ **Progressive Disclosure (Không làm phiền người dùng cũ)**:
  - Với người mới (chưa tạo token nào): Mở rộng toàn bộ để giải thích giá trị.
  - Có nút thu gọn/mở rộng ("Tìm hiểu cách hoạt động" / "Thu gọn") lưu trạng thái vào `localStorage` để người dùng chuyên nghiệp có thể thu gọn nhanh khi chỉ cần quản lý Token.

---

## II. CHI TIẾT NỘI DUNG & THIẾT KẾ TỪNG MÀN HÌNH

### 1. BẬC THẦY ĐỌC HIỂU (Yomitan) — `/settings/yomitan`

#### A. Thông điệp cốt lõi (Core Angle)
* **Định vị**: Biến mọi trang web, báo chí, truyện tranh bạn đọc thành mỏ khai thác từ vựng tự động.
* **Người mới tự hỏi**: *"Tôi lướt web gặp từ mới thì copy sang Google Dịch hoặc Mazii cũng được, sao phải cài cái này?"*

#### B. Khung so sánh trực quan (Before vs After)
| Tiêu chí | Cách học cũ (Không có Yomitan) | Khi kết hợp cùng Flama (Bậc thầy đọc hiểu) |
| :--- | :--- | :--- |
| **Thao tác tra từ** | Bôi đen từ ➔ Mở tab mới ➔ Dán vào Google Dịch ➔ Đứt mạch đọc, mất tập trung. | **Rê chuột 0.1 giây**: Khung giải nghĩa, Hiragana, âm Hán Việt hiện ra ngay trên mặt chữ. |
| **Tạo Flashcard** | Tự gõ từng chữ, chọn Kanji, chép nghĩa, tìm câu ví dụ. Mất 3–5 phút/thẻ. | **1 cú nhấp chuột (1-Click)**: Bấm icon `+`, thẻ tự động bay vào Flama đầy đủ nghĩa, ví dụ và audio. |
| **Hiệu quả duy trì** | Sau khi đọc xong quên sạch vì ngại làm thẻ thủ công. | **Học từ vựng thực tế**: Đọc đến đâu thẻ sinh ra đến đó, sẵn sàng cho thuật toán ôn tập Flama. |

#### C. Wireframe & Bố cục UI (Component: `YomitanValueIntro.tsx`)
```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 📖 BẬC THẦY ĐỌC HIỂU                                  [ 👁️ Thu gọn / Mở rộng ]         │
│ Tại sao bạn nên kết hợp công cụ này cùng Flama?                                        │
│                                                                                        │
│ ┌───────────────────────────────────────┐  ┌─────────────────────────────────────────┐ │
│ │ ❌ TRƯỚC ĐÂY (Tốn thời gian)          │  │ ⚡ KHI DÙNG VỚI FLAMA (Siêu tốc)         │ │
│ │ • Bôi đen, mở tab khác tra từ điển    │  │ • Rê chuột là thấy nghĩa trong 0.1s      │ │
│ │ • Gõ tay từng thẻ mất 3-5 phút        │  │ • Bấm dấu (+) 1-click bay thẳng Flama    │ │
│ │ • Đọc xong quên hết vì lười ghi chép   │  │ • Thuật toán SRS nhắc ôn đúng lúc quên  │ │
│ └───────────────────────────────────────┘  └─────────────────────────────────────────┘ │
│                                                                                        │
│ ── QUY TRÌNH 3 BƯỚC ĐƠN GIẢN ───────────────────────────────────────────────────────────│
│ [ 1. Đọc bài viết bất kỳ ] ➔ [ 2. Rê chuột tra từ tức thì ] ➔ [ 3. Bấm (+) lưu vào Flama ]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. CAO THỦ LUYỆN NGHE (asbplayer) — `/settings/asbplayer`

#### A. Thông điệp cốt lõi (Core Angle)
* **Định vị**: Bắt trọn câu thoại, âm thanh MP3 và biểu cảm nhân vật trực tiếp từ Phim ảnh & Anime.
* **Người mới tự hỏi**: *"Tôi luyện nghe thì cứ mở YouTube, Netflix lên xem là xong, cài thêm cái player này làm chi?"*

#### B. Khung so sánh trực quan (Before vs After)
| Tiêu chí | Xem phim thông thường | Khi kết hợp cùng Flama (Cao thủ luyện nghe) |
| :--- | :--- | :--- |
| **Phụ đề & Nghe** | Bật Vietsub thì mắt chỉ lo đọc chữ. Tắt Vietsub thì nghe không kịp, diễn viên nói quá nhanh. | **Chủ động bắt âm**: Phụ đề tiếng Nhật đồng bộ từng mili-giây, tua lặp từng câu thoại chuẩn xác. |
| **Lưu câu để học** | Thấy câu hay nhưng tắt phim là quên sạch, không lưu lại được giọng nói nhân vật. | **Cắt Audio MP3 tức thì**: Phím tắt chụp ảnh ngữ cảnh + cắt đúng file âm thanh câu thoại. |
| **Chất lượng thẻ** | Thẻ Flashcard thông thường chỉ có giọng máy đọc (TTS) đều đều, vô cảm. | **Giọng lồng tiếng thật**: Ôn tập bằng chính giọng diễn viên bản xứ, cảm nhận ngữ điệu và cảm xúc thật. |

#### C. Wireframe & Bố cục UI (Component: `AsbplayerValueIntro.tsx`)
```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎧 CAO THỦ LUYỆN NGHE                                 [ 👁️ Thu gọn / Mở rộng ]         │
│ Học từ vựng & ngữ điệu tự nhiên qua Phim ảnh, Anime và Video phụ đề                    │
│                                                                                        │
│ ┌───────────────────────────────────────┐  ┌─────────────────────────────────────────┐ │
│ │ ❌ XEM PHIM TRUYỀN THỐNG              │  │ 🎬 KHI KẾT HỢP CÙNG FLAMA               │ │
│ │ • Mắt mải đọc Vietsub, tai không nghe │  │ • Phụ đề tiếng Nhật đồng bộ từng câu     │ │
│ │ • Tua đi tua lại bị lệch nhịp, ức chế │  │ • Bấm 1 phím: Tự cắt MP3 + chụp ảnh gốc │ │
│ │ • Tắt video là âm thanh bay sạch      │  │ • Ôn lại với giọng diễn viên người thật │ │
│ └───────────────────────────────────────┘  └─────────────────────────────────────────┘ │
│                                                                                        │
│ ── QUY TRÌNH 3 BƯỚC ĐƠN GIẢN ───────────────────────────────────────────────────────────│
│ [ 1. Mở video có phụ đề ] ➔ [ 2. Bấm phím tắt cắt câu thoại ] ➔ [ 3. Tự động sinh thẻ Flama]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### 3. KẾT NỐI AI - MCP (Model Context Protocol) — `/settings/mcp-tokens`

#### A. Thông điệp cốt lõi (Core Angle)
* **Định vị**: Biến ChatGPT / Claude thành gia sư cá nhân hóa am hiểu tường tận kho kiến thức Flama của bạn.
* **Người mới tự hỏi**: *"Tôi mở tab chat với ChatGPT bình thường là đủ rồi, sao phải kết nối MCP làm gì cho phức tạp?"*

#### B. Khung so sánh trực quan (Before vs After)
| Tiêu chí | Chat AI thông thường ở tab khác | Khi kết nối trực tiếp với Flama (MCP) |
| :--- | :--- | :--- |
| **Lưu kiến thức** | AI trả lời rất hay nhưng trôi mất trong đoạn chat, phải copy từng dòng sang Flama. | **Tạo thẻ qua câu lệnh**: Nhắn *"Tạo 10 thẻ chủ đề du lịch Tokyo"*, AI tự chèn thẳng vào Flama. |
| **Độ cá nhân hóa** | AI không biết bạn đã học bài nào, cho bài tập chung chung, quá dễ hoặc quá khó. | **Gia sư hiểu bạn**: AI đọc được danh sách thẻ hôm nay bạn học để biên soạn đoạn hội thoại sát trình độ. |
| **Phân tích ngữ cảnh** | Phải gõ giải thích lại ngữ cảnh rất dài dòng. | **Truy vấn tức thì**: AI phân tích trực tiếp từ vựng dựa trên đúng bộ thẻ bạn đang sở hữu. |

#### C. Wireframe & Bố cục UI (Component: `McpValueIntro.tsx`)
```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🤖 GIA SƯ AI RIÊNG CHO FLAMA (MCP)                    [ 👁️ Thu gọn / Mở rộng ]         │
│ Kết nối ChatGPT & Claude trực tiếp với tài khoản học tập của bạn                       │
│                                                                                        │
│ ┌───────────────────────────────────────┐  ┌─────────────────────────────────────────┐ │
│ │ ❌ CHAT AI THỦ CÔNG                   │  │ ⚡ KHI KẾT NỐI VỚI FLAMA                │ │
│ │ • Kiến thức kẹt lại trong tab chat    │  │ • Tạo hàng chục thẻ chỉ bằng 1 câu lệnh │ │
│ │ • Phải copy-paste thủ công từng từ    │  │ • AI biết bạn đang học gì để giao bài tập│ │
│ │ • AI không biết trình độ thực tế      │  │ • Tự động tra cứu và bổ trợ lỗ hổng thẻ │ │
│ └───────────────────────────────────────┘  └─────────────────────────────────────────┘ │
│                                                                                        │
│ ── QUY TRÌNH KẾT NỐI 1 LẦN DUY NHẤT ───────────────────────────────────────────────────│
│ [ 1. Đăng nhập ChatGPT ] ➔ [ 2. Cho phép kết nối Flama ] ➔ [ 3. Ra lệnh trực tiếp cho AI ] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## III. KẾ HOẠCH TỔ CHỨC MÃ NGUỒN (CODEBASE ARCHITECTURE)

### 1. Cấu trúc Component Mới (FSD Layer: `frontend/src/features/settings/components/`)
* `yomitan/YomitanValueIntro.tsx`: Card giới thiệu giá trị cho Bậc thầy đọc hiểu.
* `asbplayer/AsbplayerValueIntro.tsx`: Card giới thiệu giá trị cho Cao thủ luyện nghe.
* `mcp/McpValueIntro.tsx`: Card giới thiệu giá trị cho Kết nối AI (MCP).

### 2. Cấu trúc Thư mục & Tệp tin chỉnh sửa:
```text
frontend/src/
├── features/settings/
│   ├── components/
│   │   ├── yomitan/
│   │   │   └── YomitanValueIntro.tsx       <-- Tạo mới
│   │   ├── asbplayer/
│   │   │   └── AsbplayerValueIntro.tsx     <-- Tạo mới
│   │   ├── mcp/
│   │   │   └── McpValueIntro.tsx           <-- Tạo mới
│   │   └── __tests__/
│   │       └── value_intro.test.tsx        <-- Test suite kiểm tra render & parity
│   └── pages/
│       ├── YomitanTokensPage.tsx           <-- Tích hợp YomitanValueIntro
│       ├── AsbplayerTokensPage.tsx         <-- Tích hợp AsbplayerValueIntro
│       └── McpTokensPage.tsx               <-- Tích hợp McpValueIntro
└── shared/config/i18n/locales/
    ├── vi/
    │   ├── settings.json                   <-- Thêm i18n keys cho Yomitan & Asbplayer
    │   └── mcp.json                        <-- Thêm i18n keys cho MCP
    └── en/
        ├── settings.json                   <-- Thêm bản dịch tiếng Anh đối ứng
        └── mcp.json                        <-- Thêm bản dịch tiếng Anh đối ứng
```

---

## IV. TEST MATRIX & ZERO VISUAL REGRESSION

1. **Parity Tests**: Chạy kiểm tra 100% khớp khóa giữa tiếng Việt và tiếng Anh (`vi` vs `en`) trong `settings.json` và `mcp.json`.
2. **Responsive Design**: Đảm bảo trên màn hình hẹp (mobile 360px):
   - Grid 2 cột (Before vs After) chuyển thành 1 cột xếp chồng (stacked), không bị tràn ngang.
   - Các icon và badge căn giữa gọn gàng, text dễ đọc, khoảng cách padding tối ưu `p-3 sm:p-4`.
3. **Persisted State**: Trạng thái đóng/mở (thu gọn) được ghi nhớ trong `localStorage` bằng key riêng (`flama_intro_yomitan_collapsed`, `flama_intro_asbplayer_collapsed`, `flama_intro_mcp_collapsed`), không làm phiền người dùng quen thuộc.
