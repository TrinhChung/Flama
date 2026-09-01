# Đặc tả Kiến trúc Thông tin Hệ thống Hướng dẫn Người dùng (Flama Help Center & User Guide)

## 1. Mục tiêu & Định hướng Biên soạn

### 1.1. Mục tiêu Dự án
1. **Chuẩn hóa Trung tâm Trợ giúp (`/guide/*`)**: Xây dựng cổng thông tin tài liệu hướng dẫn toàn diện, có cấu trúc phân cấp khoa học và dễ tiếp cận cho người học ngôn ngữ ở mọi trình độ.
2. **Tinh giản Màn hình Nghiệp vụ**: Loại bỏ các tab hướng dẫn cài đặt và bảng biểu tài liệu dài dòng trên các màn hình chức năng (như trang Đồng bộ Anki, Cài đặt Yomitan, Cấu hình MCP Tokens, Quản lý Note Type). Thay thế bằng các nút điều hướng trợ giúp ngữ cảnh (`? Hướng dẫn`) và chẩn đoán sự cố (`⚠️ Khắc phục sự cố`).
3. **Tiếp cận Sư phạm — Trang trọng & Mạch lạc**: Tài liệu được biên soạn bằng văn phong sư phạm chuẩn mực, trang trọng, giải thích rõ ràng nguyên lý hoạt động và quy trình thao tác mà không làm người dùng hoang mang bởi các thuật ngữ công nghệ phức tạp.

---

### 1.2. Nguyên tắc Biên soạn Chuẩn mực

- **Chính xác về mặt Kỹ thuật — Trực quan cho Người dùng**:
  - Dịch vụ **Flama Connect** là dịch vụ cầu nối được tích hợp sẵn ở máy chủ backend của Flama. Người học chỉ cần tạo Token trên giao diện web và dán đường dẫn kết nối vào tiện ích Yomitan; người dùng **không cần tải về hay cài đặt bất kỳ phần mềm Flama Connect nào**.
  - Phần mềm máy tính duy nhất người dùng có thể tải về là **Flama Audio Desktop** (`FlamaAudio-Portable.exe` trên Windows) nếu có nhu cầu phát âm tiếng Nhật giọng bản xứ (VOICEVOX & Kokoro TTS) hoàn toàn ngoại tuyến không cần internet.
  - Cung cấp hướng dẫn quy trình từng bước rõ ràng (Step-by-Step), có bảng đối chiếu tham số, hình minh họa vị trí thao tác và mẹo học tập tối ưu.
- **Tiếp cận Khắc phục Sự cố theo Hiện tượng Thực tế**:
  - Các bài chẩn đoán sự cố được đặt tên theo đúng hiện tượng người học quan sát được trên màn hình.
  - Trình bày tuần tự: Hiện tượng nhận biết ➔ Nguyên nhân thường gặp ➔ Các bước kiểm tra nhanh ➔ Quy trình xử lý dứt điểm.

---

## 2. Cấu trúc Cây Thư mục & Hệ thống Định tuyến `/guide/*`

```text
/guide                                             # Trung tâm Trợ giúp & Hướng dẫn Flama
│
├── /guide/getting-started                         # Hướng dẫn Bắt đầu Nhanh (Quy trình Onboarding)
├── /guide/core-concepts                           # Các Khái niệm Cốt lõi: Bộ thẻ, Ghi chú, Thẻ hiển thị & SRS
│
├── /guide/dashboard                               # [Chuyên mục] Bảng Điều Khiển & Quản Lý Bộ Thẻ
│   ├── /guide/dashboard/overview                  # Tổng quan Bảng điều khiển & Chu trình học tập mỗi ngày
│   ├── /guide/dashboard/deck-grouping             # Hướng dẫn gom nhóm Bộ thẻ phân cấp (Subdecks bằng dấu `::`)
│   ├── /guide/dashboard/deck-management           # Tạo mới, đổi tên, sắp xếp, ghim và thiết lập giới hạn học
│   └── /guide/dashboard/study-metrics             # Giải thích chỉ số: Thẻ mới, Đang học, Đến hạn, Chuỗi ngày học & Tỷ lệ nhớ
│
├── /guide/study                                   # [Chuyên mục] Phòng Học Flashcard & Thuật Toán Ôn Tập
│   ├── /guide/study/flashcard-flow                # Quy trình học Flashcard tiêu chuẩn & Nguyên tắc 4 mức đánh giá
│   ├── /guide/study/spaced-repetition             # Cơ chế Thuật toán Lặp lại Ngắt quãng (Spaced Repetition)
│   ├── /guide/study/shortcuts                     # Bảng tra cứu phím tắt bàn phím khi học và ôn tập
│   └── /guide/study/audio-and-furigana            # Tùy chỉnh phiên âm Furigana & Cấu hình phát âm tự động
│
├── /guide/browse                                  # [Chuyên mục] Quản Lý Thư Viện Thẻ & Tìm Kiếm Nâng Cao
│   ├── /guide/browse/search-syntax                # Cú pháp tìm kiếm và các bộ lọc từ vựng nâng cao
│   ├── /guide/browse/batch-actions                # Thao tác hàng loạt: Đổi bộ thẻ, gán nhãn, tạm dừng, đặt lại tiến độ
│   └── /guide/browse/card-lifecycle               # Quản lý vòng đời thẻ & Phương pháp xử lý thẻ khó nhớ (Leech)
│
├── /guide/note-types                              # [Chuyên mục] Loại Ghi Chú & Tùy Biến Giao Diện Thẻ
│   ├── /guide/note-types/concept                  # Kiến trúc 1 Ghi chú sinh Nhiều Thẻ học (1-to-Many)
│   ├── /guide/note-types/fields                   # Quản lý danh sách trường dữ liệu (Văn bản, Âm thanh, Hình ảnh)
│   ├── /guide/note-types/templates                # Tùy biến mẫu thẻ Front/Back bằng HTML, Mustache Tags & CSS
│   └── /guide/note-types/cloze-deletion           # Hướng dẫn tạo và sử dụng mẫu thẻ đục lỗ (Cloze Deletion)
│
├── /guide/marketplace                             # [Chuyên mục] Marketplace & Chia Sẻ Học Liệu
│   ├── /guide/marketplace/discovery               # Tìm kiếm và cài đặt Bộ thẻ chia sẻ từ cộng đồng
│   ├── /guide/marketplace/overlay-clone           # Cơ chế Clone Overlay: Tùy biến thẻ học an toàn khi cập nhật
│   ├── /guide/marketplace/change-requests         # Quy trình gửi Đề xuất chỉnh sửa học liệu cho tác giả
│   └── /guide/marketplace/creator-publishing      # Dành cho Tác giả: Xuất bản bộ thẻ & Quản lý bản phát hành
│
├── /guide/import-sync                             # [Chuyên mục] Nhập Dữ Liệu & Đồng Bộ Anki
│   ├── /guide/import-sync/csv-wizard              # Nhập từ vựng từ tệp CSV / TSV / Text qua Wizard 4 bước
│   └── /guide/import-sync/anki-connect-sync       # Đồng bộ trực tiếp từ phần mềm Anki Desktop qua AnkiConnect
│
├── /guide/integrations                            # [Chuyên mục] Tiện Ích Khai Thác & Trợ Lý AI
│   ├── /guide/integrations/yomitan                # Khai thác từ vựng 1-Click với tiện ích Yomitan trên trình duyệt
│   └── /guide/integrations/mcp-ai                 # Kết nối trợ lý AI (Claude, Cursor, Antigravity) qua giao thức MCP
│
├── /guide/audio                                   # [Chuyên mục] Hệ Thống Âm Thanh & Tổng Hợp Giọng Đọc (TTS)
│   ├── /guide/audio/flama-audio                   # Cài đặt và sử dụng ứng dụng Flama Audio Desktop (Ngoại tuyến 100%)
│   ├── /guide/audio/cloud-tts-keys                # Hướng dẫn đăng ký và cấu hình API Key dịch vụ giọng đọc đám mây
│   └── /guide/audio/batch-generation              # Công cụ tạo phát âm hàng loạt cho toàn bộ bộ thẻ
│
├── /guide/account-billing                         # [Chuyên mục] Tài Khoản, Bảo Mật & Thanh Toán
│   ├── /guide/account-billing/profile-security    # Quản lý hồ sơ, bảo mật tài khoản & quyền riêng tư
│   └── /guide/account-billing/wallet-payos        # Nạp số dư ví và thanh toán bài học qua PayOS VietQR
│
└── /guide/troubleshooting                         # [Chuyên mục] Trung Tâm Xử Lý Sự Cố (Troubleshooting Hub)
    ├── /guide/troubleshooting/dashboard-study     # Khắc phục sự cố hiển thị thẻ và số lượng ôn tập trên Dashboard
    ├── /guide/troubleshooting/import-csv          # Khắc phục lỗi định dạng cột và dấu phân cách khi nạp tệp CSV
    ├── /guide/troubleshooting/anki-sync           # Khắc phục lỗi kết nối với phần mềm Anki Desktop (AnkiConnect)
    ├── /guide/troubleshooting/yomitan             # Khắc phục lỗi kết nối và tạo thẻ từ tiện ích Yomitan
    ├── /guide/troubleshooting/flama-audio         # Khắc phục lỗi không phát âm thanh hoặc không kết nối Flama Audio
    └── /guide/troubleshooting/marketplace-updates # Xử lý xung đột khi đồng bộ bản cập nhật mới từ tác giả
```

---

## 3. Đặc tả Nội dung Chi tiết Từng Chuyên mục

### Chuyên mục 1: Bắt đầu & Khái niệm Cốt lõi

#### 1.1. `/guide/getting-started` — Hướng dẫn Bắt đầu Nhanh (Onboarding)
- **Mục đích**: Giúp người học làm quen và hoàn thành buổi học Flashcard đầu tiên trong vòng 3 phút.
- **Quy trình thực hiện**:
  1. **Bước 1: Chọn hoặc tạo bài học đầu tiên**: Người học có thể tạo bộ thẻ mới bằng nút *Tạo bộ thẻ* trên Dashboard, hoặc vào *Marketplace* tải một bộ thẻ chuẩn trình độ JLPT (N5, N4...).
  2. **Bước 2: Thêm từ vựng đầu tiên**: Nhấn nút *Thêm thẻ* (biểu tượng dấu `+`), điền các trường thông tin: Chữ Hán (Kanji), Phiên âm (Hiragana), Nghĩa tiếng Việt và Ví dụ.
  3. **Bước 3: Thực hiện phiên học**: Nhấn nút **Học ngay** tại bộ thẻ. Quan sát câu hỏi mặt trước ➔ Nhấn phím `Space` để lật mở đáp án ➔ Nhấn các phím số `1`, `2`, `3`, `4` để đánh giá mức độ ghi nhớ.
  4. **Bước 4: Theo dõi tiến độ**: Xem kết quả hoàn thành buổi học trên thanh mục tiêu hàng ngày và chuỗi ngày học (`Streak`).

#### 1.2. `/guide/core-concepts` — Các Khái niệm Cốt lõi
- **Bộ thẻ (Deck)**: Thùng chứa dùng để phân loại học liệu theo cấp độ (N5-N1), giáo trình hoặc chủ đề.
- **Ghi chú dữ liệu (Note)**: Bản ghi chứa toàn bộ thông tin gốc của mục từ vựng hoặc điểm ngữ pháp.
- **Thẻ hiển thị (Card)**: Sản phẩm hiển thị trực quan được sinh ra từ Ghi chú để phục vụ việc ôn tập hai chiều.
- **Thuật toán Lặp lại Ngắt quãng (Spaced Repetition System - SRS)**: Cơ chế khoa học tự động tính toán thời điểm trí não sắp quên để lên lịch ôn tập, giúp chuyển hóa kiến thức thành trí nhớ dài hạn với thời gian học ít nhất.

---

### Chuyên mục 2: Bảng Điều Khiển & Quản Lý Bộ Thẻ (Dashboard & Decks)

#### 2.1. `/guide/dashboard/deck-grouping` — Gom nhóm Bộ thẻ Phân cấp (Cú pháp `::`)
- **Mục đích**: Hướng dẫn xây dựng cấu trúc cây thư mục phân cấp cho các bộ thẻ để quản lý khối lượng học liệu lớn một cách ngăn nắp, khoa học.
- **Quy ước đặt tên**:
  - Sử dụng ký hiệu hai dấu hai chấm liền nhau `::` để phân định cấp cha - con trong tên bộ thẻ.
  - *Ví dụ mẫu*: `Tiếng Nhật::N3::Từ vựng Soumatome::Tuần 1 Ngày 1`.
- **Cơ chế hoạt động của Cây Thư mục (Deck Tree)**:
  - Hệ thống tự động phân tích tiền tố tên và nhóm các bộ thẻ thành dạng cây thư mục có thể mở rộng hoặc thu gọn.
- **Cơ chế Ôn tập: Học Bộ thẻ Cha so với Học Bộ thẻ Con**:
  - **Khi nhấn nút Học tại Bộ thẻ Cha** (ví dụ `Tiếng Nhật::N3`): Hệ thống sẽ tự động tổng hợp toàn bộ các thẻ đến hạn ôn tập từ tất cả các bộ thẻ con cháu thuộc nhánh đó vào một phiên học duy nhất.
  - **Khi nhấn nút Học tại Bộ thẻ Con** (ví dụ `Tuần 1 Ngày 1`): Phiên học chỉ giới hạn chính xác trong phạm vi các thẻ của bài học con đó.
- **Cơ chế Đếm gộp Số lượng (Aggregated Counters)**:
  - Các con số thống kê *Thẻ mới / Đang học / Đến hạn* hiển thị tại hàng của bộ thẻ cha là tổng số lượng của chính nó cộng với tất cả các nhánh con cháu bên dưới.

#### 2.2. `/guide/dashboard/overview` — Tổng quan Bảng Điều Khiển
- **Bố cục màn hình**:
  1. Khu vực tóm tắt chỉ số học tập trong ngày (Hôm nay cần ôn bao nhiêu thẻ, đã học được bao nhiêu).
  2. Cây danh mục bộ thẻ kèm số lượng thẻ chờ học theo từng danh mục.
  3. Thanh công cụ tác vụ nhanh: *Học ngay*, *Thêm thẻ*, *Duyệt thư viện*, *Nhập tệp*, *Marketplace*.
  4. Thanh tiến độ mục tiêu học tập hàng ngày và biểu tượng chuỗi ngày học (`Streak`).

#### 2.3. `/guide/dashboard/deck-management` — Quản trị & Thiết lập Bộ thẻ (Deck Settings)
- **Tạo mới, đổi tên và sắp xếp**: Hướng dẫn tạo bộ thẻ độc lập hoặc bộ thẻ phân cấp, đổi tên và di chuyển nhánh.
- **Ghim bộ thẻ (Pinned Decks)**: Ghim các bộ thẻ quan trọng lên đầu danh sách để ưu tiên truy cập.
- **Cấu hình Giới hạn Học tập (Deck Study Options)**:
  - `Số thẻ mới tối đa mỗi ngày (New Cards/Day)`: Giới hạn lượng từ mới nạp vào để tránh quá tải (khuyến nghị: 15 - 25 thẻ/ngày).
  - `Số lượt ôn tập tối đa mỗi ngày (Max Reviews/Day)`: Đặt trần số lượng thẻ ôn tập để phân bổ thời gian hợp lý.
- **Xóa bộ thẻ**: Phân biệt giữa xóa chỉ bộ thẻ (giữ lại thẻ chuyển về mặc định) và xóa toàn bộ thẻ bên trong.

#### 2.4. `/guide/dashboard/study-metrics` — Giải mã Các Chỉ số Thống kê
- **Ý nghĩa 3 nhóm màu sắc**:
  - **Màu xanh dương (New - Thẻ mới)**: Thẻ vừa tạo hoặc vừa nhập vào hệ thống, người học chưa từng học lần nào.
  - **Màu cam/đỏ (Learn - Đang học)**: Thẻ đang trong các bước ghi nhớ ban đầu hoặc vừa bị đánh giá sai (`Again`), đang chờ hoàn thành trong ngày.
  - **Màu xanh lá (Due - Đến hạn ôn tập)**: Thẻ đã vượt qua giai đoạn học ban đầu, hôm nay đến hạn lặp lại theo tính toán của thuật toán SRS.
- **Quy tắc Tính Chuỗi Ngày Học (`Streak`)**:
  - Chuỗi ngày học tăng thêm 1 khi người học hoàn thành ít nhất một phiên học trong ngày.
  - **Mốc chốt ngày mới (Day Boundary Cutoff)**: Hệ thống quy định mốc thời gian chuyển sang ngày mới là **4:00 sáng** (thay vì 00:00 đêm) để bảo toàn chuỗi ngày học cho những người học có thói quen học khuya.
- **Tỷ lệ Ghi nhớ (Retention Rate)**:
  - Tỷ lệ phần trăm số lần đánh giá thành công (`Good` / `Easy`) trên tổng số lượt ôn tập thẻ đến hạn (tối ưu: 85% - 90%).
- **Biểu đồ Dự báo Ôn tập (Review Forecast)**:
  - Thể hiện số lượng thẻ sẽ đến hạn ôn tập trong 7 ngày tới.

---

### Chuyên mục 3: Phòng Học Flashcard & Thuật Toán Ôn Tập

#### 3.1. `/guide/study/flashcard-flow` — Quy trình Học & Nguyên tắc Đánh giá
- **Chu trình 3 bước chuẩn mực**:
  1. **Bước 1: Quan sát mặt trước (Question)**: Tự gợi nhớ cách đọc, ngữ nghĩa và ví dụ trong tâm trí.
  2. **Bước 2: Lật thẻ (Show Answer)**: Nhấn phím `Space` hoặc `Enter` để kiểm tra kết quả mặt sau.
  3. **Bước 3: Tự đánh giá mức độ ghi nhớ theo 4 mức độ**:
     - **1 - Học lại (Again)**: Quên hoặc nhớ sai ➔ Thẻ xuất hiện lại sau vài phút trong cùng phiên học.
     - **2 - Khó (Hard)**: Nhớ đúng nhưng mất nhiều thời gian suy nghĩ ➔ Khoảng cách lặp lại tiếp theo tăng nhẹ.
     - **3 - Tốt (Good - Khuyến nghị mặc định)**: Nhớ chính xác với phản xạ chuẩn ➔ Khoảng cách lặp lại tăng theo hệ số chuẩn.
     - **4 - Dễ (Easy)**: Nhớ ngay lập tức không cần nỗ lực ➔ Khoảng cách lặp lại tăng nhảy vọt.

#### 3.2. `/guide/study/spaced-repetition` — Cơ chế Thuật toán Lặp lại Ngắt quãng
- Vòng đời của thẻ: `Học ban đầu (Learning)` ➔ `Tốt nghiệp (Graduated)` ➔ `Ôn tập định kỳ (Review)`.
- Hệ số Độ khó (Ease Factor) tự động điều chỉnh theo từng phản xạ đánh giá của người học.

#### 3.3. `/guide/study/shortcuts` — Bảng Tra cứu Phím tắt Bàn phím
| Phím tắt | Tác vụ thực hiện | Chi tiết hoạt động |
| :--- | :--- | :--- |
| `Space` / `Enter` | **Lật thẻ (Show Answer)** | Lật mở mặt sau của thẻ học |
| `1` | **Học lại (Again)** | Đánh giá chưa thuộc, lặp lại trong phiên |
| `2` | **Khó (Hard)** | Đánh giá mức độ khó |
| `3` | **Tốt (Good)** | Đánh giá mức độ đạt yêu cầu chuẩn |
| `4` | **Dễ (Easy)** | Đánh giá mức độ ghi nhớ xuất sắc |
| `R` / `F5` | **Phát lại âm thanh (Replay Audio)** | Phát lại file âm thanh giọng đọc mẫu |
| `Z` / `Ctrl + Z` | **Hoàn tác (Undo Review)** | Hủy bỏ lượt chấm điểm vừa rồi để đánh giá lại |
| `F` | **Ẩn/Hiện Furigana** | Bật hoặc tắt phiên âm Hiragana trên chữ Hán |
| `E` | **Sửa nhanh thẻ (Quick Edit)** | Mở cửa sổ chỉnh sửa trực tiếp nội dung thẻ đang học |
| `*` / `-` | **Gắn cờ ưu tiên (Flag)** | Đánh dấu thẻ để lọc lại trong trình duyệt thẻ |

---

### Chuyên mục 4: Duyệt Thẻ & Quản Lý Thư Viện (Browse)

#### 4.1. `/guide/browse/search-syntax` — Cú pháp Tìm kiếm & Bộ lọc Nâng cao
- **Tìm kiếm toàn văn**: Tìm kiếm từ khóa xuất hiện trong bất kỳ trường dữ liệu nào.
- **Lọc theo Bộ thẻ**: `deck:"Tiếng Nhật::N3"` hoặc `deck:current`.
- **Lọc theo Thẻ nhãn (Tags)**: `tag:kanji`, `tag:jlpt_n2`, `-tag:tam_dung`.
- **Lọc theo Trạng thái học tập**: `is:new`, `is:learn`, `is:due`, `is:suspended`.
- **Lọc theo Cờ đánh dấu**: `flag:1` (Cờ đỏ), `flag:2` (Cờ cam)...

#### 4.2. `/guide/browse/batch-actions` — Thao tác Hàng loạt (Batch Operations)
- Đổi bộ thẻ hàng loạt (Change Deck).
- Gắn / Gỡ nhãn hàng loạt (Add / Remove Tags).
- Tạm dừng / Hủy tạm dừng (Suspend / Unsuspend).
- Đặt lại tiến độ học (Reset Progress).
- Xóa hàng loạt an toàn (Batch Delete).

#### 4.3. `/guide/browse/card-lifecycle` — Quản lý Thẻ Khó nhớ (Leech Management)
- Tự động nhận diện và gắn nhãn `leech` cho thẻ bị đánh giá `Again` trên 8 lần để người học kịp thời bổ sung câu ví dụ hoặc hình ảnh liên tưởng.

---

### Chuyên mục 5: Loại Ghi Chú & Mẫu Thẻ (Note Types & Templates)

#### 5.1. `/guide/note-types/concept` — Kiến trúc 1 Ghi chú tạo Nhiều Thẻ (1-to-Many)
- Người học chỉ cần nhập thông tin một lần vào Ghi chú (Kanji, Hiragana, Nghĩa, Âm thanh). Hệ thống tự động sinh ra Thẻ Nhận diện (Kanji ➔ Nghĩa) và Thẻ Tái hiện (Nghĩa ➔ Kanji) với tiến độ ôn tập hoàn toàn độc lập.

#### 5.2. `/guide/note-types/templates` — Tùy biến Mẫu thẻ HTML & CSS
- Sử dụng Mustache tags `{{Field}}`, thẻ điều kiện `{{#Field}}...{{/Field}}`, `{{FrontSide}}` và tùy biến CSS Dark/Light mode.

#### 5.3. `/guide/note-types/cloze-deletion` — Mẫu Thẻ Đục Lỗ (Điền vào chỗ trống)
- Cú pháp `{{c1::từ cần ẩn}}` hoặc `{{c1::từ cần ẩn::gợi ý}}` để ôn tập ngữ pháp và mẫu câu giao tiếp. Phím tắt: `Ctrl + Shift + C`.

---

### Chuyên mục 6: Marketplace & Mô Hình Clone Overlay Độc Quyền

#### 6.1. `/guide/marketplace/discovery` — Tìm kiếm & Cài đặt Bộ thẻ Chia sẻ
- Khám phá kho học liệu phong phú từ cộng đồng, lọc theo cấp độ JLPT và giáo trình chuẩn, cài đặt 1-click vào tài khoản.

#### 6.2. `/guide/marketplace/overlay-clone` — Cơ chế Clone Overlay Bảo toàn Ghi chú Cá nhân
- Phân tách dữ liệu thành **Lớp nguồn của Tác giả** và **Lớp phủ cá nhân của Người học**. Người học tự do thêm ví dụ và ghi chú riêng; khi tác giả cập nhật bản mới, hệ thống tự động hợp nhất mà **bảo toàn 100% các ghi chú cá nhân và tiến trình học tập của người học**.

#### 6.3. `/guide/marketplace/change-requests` — Đóng góp Sửa lỗi Học liệu (Change Requests)
- Người học gửi đề xuất sửa lỗi cho tác giả. Tác giả xem bảng đối chiếu 3 chiều trực quan (**3-Way Visual Diff**) và duyệt hợp nhất vào bộ thẻ gốc trong 1 thao tác.

#### 6.4. `/guide/marketplace/creator-publishing` — Dành cho Tác giả: Xuất bản & Quản lý Bản phát hành
- Quy trình xuất bản bộ thẻ, sử dụng công cụ **Release Builder** để tạo phiên bản phát hành mới (`v1.1.0`) kèm Changelog.

---

### Chuyên mục 7: Nhập Dữ Liệu & Đồng Bộ Anki (Import & Sync)

#### 7.1. `/guide/import-sync/csv-wizard` — Nhập Thẻ từ Tệp CSV / TSV qua Wizard 4 Bước
- **Giao diện thực hiện**: Trang `/import` (File Import Wizard).
- **Quy trình 4 bước nạp dữ liệu an toàn**:
  1. **Bước 1: Chọn Bộ thẻ & Loại ghi chú đích**: Xác định bộ thẻ tiếp nhận và Loại ghi chú (`Note Type`) tương ứng với cấu trúc dữ liệu.
  2. **Bước 2: Tải tệp & Phân tích cú pháp (Parse)**: Kéo thả tệp dữ liệu (`.csv`, `.tsv`, `.txt`). Lựa chọn ký tự phân cách cột (Dấu phẩy, Dấu chấm phẩy, Dấu Tab).
  3. **Bước 3: Ánh xạ Cột & Chế độ Ghi đè**: Ghép nối từng cột trong bảng tính với trường dữ liệu của Flama, thiết lập hành vi khi gặp thẻ trùng lặp (Bỏ qua / Cập nhật / Thêm mới).
  4. **Bước 4: Kiểm tra Ước lượng & Thực thi**: Xem trước số lượng ghi chú hợp lệ và bấm hoàn tất để nạp thẻ vào hệ thống.

#### 7.2. `/guide/import-sync/anki-connect-sync` — Đồng Bộ Trực Tiếp từ Anki Desktop qua AnkiConnect
- **Giao diện thực hiện**: Trang `/sync`.
- **Nguyên lý hoạt động**: Trình duyệt kết nối trực tiếp đến cổng `8765` của tiện ích AnkiConnect đang chạy trên phần mềm Anki Desktop ở máy tính cá nhân.
- **Tính năng đồng bộ**: Kéo toàn bộ danh mục Bộ thẻ (Deck Tree), Loại ghi chú (Note Types), Thẻ học kèm toàn bộ tệp âm thanh và hình ảnh từ Anki Desktop sang Flama.

---

### Chuyên mục 8: Tiện Ích Khai Thác & Trợ Lý AI

#### 8.1. `/guide/integrations/yomitan` — Khai thác Từ vựng 1-Click với Tiện ích Yomitan
- **Nguyên lý hoạt động**: Dịch vụ **Flama Connect** đã được thiết lập sẵn trong nền tảng máy chủ Flama. Người học **không cần cài đặt phần mềm cầu nối trung gian nào**.
- **Quy trình 3 bước**:
  1. Vào `/settings/yomitan` trên Flama để tạo Token và sao chép đường dẫn kết nối (**Server URL**).
  2. Mở Cài đặt của tiện ích Yomitan trên trình duyệt ➔ Mục **Integration / Connect** ➔ Bật kích hoạt và dán đường dẫn **Server URL**.
  3. Cấu hình ánh xạ các trường dữ liệu (`{expression}`, `{reading}`, `{glossary}`, `{audio}`).
- Khi đọc báo tiếng Nhật trên web, chỉ cần rê chuột tra từ và bấm dấu **`+`**, từ vựng sẽ tự động được tạo thành Flashcard trong Flama kèm phát âm và câu ví dụ.

#### 8.2. `/guide/integrations/mcp-ai` — Kết nối Trợ lý AI qua Model Context Protocol (MCP)
- Tạo mã MCP Token tại `/settings/mcp-tokens` để kết nối với các công cụ AI (Claude Desktop, Cursor, Antigravity) để AI tự động phân tích bộ thẻ và tạo câu ví dụ mẫu theo yêu cầu.

---

### Chuyên mục 9: Hệ Thống Âm Thanh & Tổng Hợp Giọng Đọc (Audio & TTS)

#### 9.1. `/guide/audio/flama-audio` — Ứng dụng Flama Audio Desktop (Phát âm Ngoại tuyến 100%)
- Ứng dụng độc lập `FlamaAudio-Portable.exe` (.NET 8 WPF) dành cho Windows, cung cấp giọng đọc bản xứ VOICEVOX và Kokoro TTS chạy trực tiếp trên máy cục bộ (cổng `4791`), hoàn toàn miễn phí và không cần mạng internet.
- Ghép nối an toàn với web app qua cơ chế Private Network Access (PNA).

#### 9.2. `/guide/audio/cloud-tts-keys` — Cấu hình Khóa API Giọng đọc Đám mây
- Hướng dẫn cấu hình API Key cho các dịch vụ: VoiceVox API (miễn phí), OpenAI TTS, ElevenLabs, Google Speech (được mã hóa chuẩn AES-256 trên máy chủ).

#### 9.3. `/guide/audio/batch-generation` — Công cụ Tạo Phát âm Hàng loạt
- Quét tự động toàn bộ bộ thẻ và tạo âm thanh hàng loạt cho hàng nghìn từ vựng cùng lúc tại trang `/audio/generate`.

---

### Chuyên mục 10: Tài Khoản, Ví & Thanh Toán

#### 10.1. `/guide/account-billing/profile-security` — Quản trị Hồ sơ & Bảo mật
- Quản trị thông tin cá nhân, bảo mật mật khẩu và quyền riêng tư của chuỗi ngày học `Streak`.

#### 10.2. `/guide/account-billing/wallet-payos` — Nạp Ví & Thanh toán qua PayOS VietQR
- Nạp số dư ví Flama Wallet tự động 24/7 bằng quét mã VietQR ngân hàng qua cổng PayOS để mua các bộ thẻ bản quyền từ giảng viên trên Marketplace.

---

## 4. Bản Đồ Ánh Xạ Nút Trợ Giúp Ngữ Cảnh Trên Giao Diện

| Màn hình Chức năng | URL | Nút Hướng dẫn Sử dụng (`? Guide`) | Nút Khắc phục Sự cố (`⚠️ Troubleshooting`) |
| :--- | :--- | :--- | :--- |
| **Bảng điều khiển** | `/dashboard` | `/guide/dashboard/overview` & `/guide/dashboard/deck-grouping` | `/guide/troubleshooting/dashboard-study` |
| **Thống kê** | `/statistics` | `/guide/dashboard/study-metrics` | `/guide/troubleshooting/dashboard-study` |
| **Phòng học Flashcard** | `/study` | `/guide/study/flashcard-flow` & `/guide/study/shortcuts` | `/guide/troubleshooting/dashboard-study` |
| **Duyệt thư viện thẻ** | `/browse` | `/guide/browse/search-syntax` & `/guide/browse/batch-actions` | `/guide/troubleshooting/dashboard-study` |
| **Quản lý Note Types** | `/note-types` | `/guide/note-types/concept` & `/guide/note-types/templates` | `/guide/troubleshooting/import-csv` |
| **Thẻ đã cài đặt** | `/installed-decks` | `/guide/marketplace/overlay-clone` | `/guide/troubleshooting/marketplace-updates` |
| **Marketplace** | `/marketplace/decks`| `/guide/marketplace/discovery` | `/guide/troubleshooting/marketplace-updates` |
| **Nhập tệp CSV** | `/import` | `/guide/import-sync/csv-wizard` | `/guide/troubleshooting/import-csv` |
| **Đồng bộ Anki Desktop** | `/sync` | `/guide/import-sync/anki-connect-sync` | `/guide/troubleshooting/anki-sync` |
| **Cài đặt Yomitan** | `/settings/yomitan` | `/guide/integrations/yomitan` | `/guide/troubleshooting/yomitan` |
| **Cài đặt MCP Tokens** | `/settings/mcp-tokens`| `/guide/integrations/mcp-ai` | `/guide/troubleshooting/mcp` |
| **Tạo âm thanh hàng loạt**| `/audio/generate` | `/guide/audio/batch-generation` & `/guide/audio/flama-audio` | `/guide/troubleshooting/flama-audio` |
| **Ví & Thanh toán** | `/wallet` | `/guide/account-billing/wallet-payos` | `/guide/troubleshooting/dashboard-study` |

---

## 5. Ma trận Chẩn đoán Sự cố theo Hiện tượng (Troubleshooting Matrix)

| Hiện tượng quan sát được | Nguyên nhân phổ biến | Quy trình xử lý dứt điểm |
| :--- | :--- | :--- |
| **Số lượng thẻ cần học hôm nay không hiển thị hoặc bị thiếu** | Do cài đặt giới hạn số lượng thẻ mỗi ngày (`Max Reviews/Day`) hoặc chưa qua mốc cắt ngày mới (4:00 sáng). | Vào phần *Cài đặt Bộ thẻ (Deck Settings)* ➔ Tăng giới hạn số thẻ mới hoặc số thẻ ôn tập mỗi ngày. |
| **Không nghe được âm thanh phát âm tiếng Nhật** | Ứng dụng Flama Audio Desktop chưa được khởi chạy trên máy tính. | Khởi chạy tệp `FlamaAudio-Portable.exe` và kiểm tra trạng thái kết nối tại `/guide/flama-audio`. |
| **Tiện ích Yomitan báo lỗi không thêm được từ vựng** | Đường dẫn Server URL hoặc Token kết nối bị sai/thu hồi. | Kiểm tra và sao chép lại Server URL tại `/settings/yomitan`, dán lại vào mục Integration của tiện ích Yomitan. |
| **Đồng bộ Anki Desktop (`/sync`) báo lỗi không kết nối được** | Phần mềm Anki Desktop chưa mở hoặc chưa cài đặt tiện ích AnkiConnect trên cổng 8765. | Khởi động phần mềm Anki Desktop, kiểm tra add-on AnkiConnect và đảm bảo cấu hình CORS cho phép kết nối. |
| **Tệp CSV tải lên bị dồn dữ liệu vào 1 cột duy nhất** | Lựa chọn sai ký tự phân cách trong bảng tính ở Bước 2. | Chọn lại ký tự phân cách là dấu Chấm phẩy (`;`) hoặc dấu Tab (`\t`) khi tải tệp tại trang `/import`. |
| **Lỡ tay bấm nhầm mức đánh giá trong khi học** | Người học muốn hoàn tác thao tác vừa thực hiện. | Nhấn ngay phím `Ctrl + Z` hoặc phím `Z` trên bàn phím để phục hồi lại thẻ vừa học. |
| **Bộ thẻ chia sẻ thông báo có bản cập nhật mới** | Tác giả phát hành bản sửa lỗi hoặc bổ sung nội dung mới. | Nhấn nút *Cập nhật* tại trang `/installed-decks`. Toàn bộ ghi chú riêng của bạn sẽ được bảo toàn tuyệt đối. |

---

## 6. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

- [x] Toàn bộ tài liệu được biên soạn bằng văn phong trang trọng, chuẩn mực, rõ ràng và mạch lạc.
- [x] Phản ánh chính xác 100% kiến trúc kỹ thuật của hệ thống: Flama Connect là dịch vụ máy chủ tích hợp sẵn, Flama Audio Desktop là ứng dụng phát âm ngoại tuyến tùy chọn.
- [x] Bao quát toàn diện 100% tính năng hiện có của Flama (Dashboard, Subdecks `::`, SRS Study, Browse, Note Types, Clone Overlay, Change Requests, Releases, Yomitan, AnkiSync, MCP, Flama Audio, PayOS Wallet, Troubleshooting).
- [x] Có bảng ánh xạ nút trợ giúp ngữ cảnh cho toàn bộ các màn hình chức năng trên React frontend.
- [x] Ma trận chẩn đoán sự cố theo hiện tượng rõ ràng, hỗ trợ người học tự xử lý vấn đề trong thời gian ngắn.
- [x] Kiến trúc định tuyến `/guide/*` phân tầng chuẩn xác, sẵn sàng cho việc triển khai giao diện Help Center.


