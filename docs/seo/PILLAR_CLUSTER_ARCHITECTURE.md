# Kiến Trúc Nội Dung Pillar - Cluster & Sơ Đồ Liên Kết Nội Bộ Toàn Diện (Pillar - Cluster Architecture & Internal Linking Blueprint) — Flama.vn

> **Tài liệu đặc tả kiến trúc phân cấp nội dung & điều hướng dòng chảy sức mạnh liên kết (Link Equity)**  
> **Dự án**: Flama (https://flama.vn) — Nền tảng học tiếng Nhật & ghi nhớ Spaced Repetition thông minh  
> **Phiên bản**: 2.0.0 (Production Architecture)  
> **Tác giả**: Flama SEO Strategy Team (teamwork_preview_worker_m1)  
> **Cấu trúc mạng lưới**: **5 Trang Trụ Cột (Pillar Pages) & 33 Trang Vệ Tinh (Satellite Cluster URLs)** ánh xạ 100% khớp nối với `PUBLIC_SITEMAP_CATALOG` (`app/services/seo_service.py`) và cấu trúc ứng dụng Web React SPA  
> **Cơ chế điều phối**: Mạng lưới liên kết 2 chiều (Vertical ⬌ Horizontal) & Chiến lược neo văn bản 4 tầng chống phạt thuật toán Google Penguin  

---

## MỤC LỤC
1. [TỔNG QUAN KIẾN TRÚC PILLAR - CLUSTER & TRIẾT LÝ THỰC THI](#1-tổng-quan-kiến-trúc-pillar---cluster--triết-lý-thực-thi)
2. [SƠ ĐỒ PHÂN CẤP TỔNG THỂ 5 CỤM CHỦ ĐỀ](#2-sơ-đồ-phân-cấp-tổng-thể-5-cụm-chủ-đề)
3. [MA TRẬN ĐỐI CHIẾU 5 TRANG TRỤ CỘT & 33 TRANG VỆ TINH](#3-ma-trận-đối-chiếu-5-trang-trụ-cột--33-trang-vệ-tinh)
4. [QUY TẮC ĐIỀU HƯỚNG LIÊN KẾT NỘI BỘ 2 CHIỀU (2-WAY INTERNAL LINKING RULES)](#4-quy-tắc-điều-hướng-liên-kết-nội-bộ-2-chiều-2-way-internal-linking-rules)
5. [CHIẾN LƯỢC ĐA DẠNG HÓA ANCHOR TEXT 4 TẦNG (4-TIER ANCHOR DIVERSIFICATION)](#5-chiến-lược-đa-dạng-hóa-anchor-text-4-tầng-4-tier-anchor-diversification)
6. [RANH GIỚI AN TOÀN CHỐNG SPAM & THUẬT TOÁN PENGUIN (ANTI-SPAM GUARDRAILS)](#6-ranh-giới-an-toàn-chống-spam--thuật-toán-penguin-anti-spam-guardrails)
7. [HƯỚNG DẪN BẢO TRÌ & QUY TRÌNH KIỂM TRA TÍNH TOÀN VẸN LIÊN KẾT](#7-hướng-dẫn-bảo-trì--quy-trình-kiểm-tra-tính-toàn-vẹn-liên-kết)

---

## 1. TỔNG QUAN KIẾN TRÚC PILLAR - CLUSTER & TRIẾT LÝ THỰC THI

### 1.1. Tại sao Flama cần mô hình Pillar - Cluster?
Trong kỷ nguyên của Semantic Search và thuật toán Google Helpful Content, việc viết các bài viết đơn lẻ rời rạc (Single Standalone Posts) không còn mang lại hiệu quả nâng hạng bền vững. Khi các bài viết phân tán, công cụ tìm kiếm khó nhận diện được chiều sâu chuyên môn (Topical Authority) của website và dòng sức mạnh liên kết (PageRank / Link Equity) bị rò rỉ, phân mảnh.

Mô hình **Pillar - Cluster (Trụ cột - Vệ tinh)** của Flama giải quyết triệt để vấn đề này:
1. **Thiết lập thẩm quyền chủ đề tuyệt đối (Topical Authority)**: Tổ chức nội dung thành 5 trung tâm chuyên môn sâu (Brand Entity, Spaced Repetition SRS, Yomitan Mining, Local TTS Audio, và Kho Thẻ JLPT).
2. **Tối ưu hóa hành trình người học (User Intent Journey)**: Dẫn dắt người học từ câu hỏi thông tin ban đầu (TOFU: *"Cách nhớ từ vựng lâu?"*), qua tìm hiểu giải pháp kỹ thuật (MOFU: *"So sánh Flama vs Anki"*, *"Cài Yomitan tra từ anime"*), đến hành động chuyển đổi học tập (BOFU: *"Tải bộ thẻ N5 Minna"*, *"Đăng ký học miễn phí"*).
3. **Phân phối Link Equity khoa học**: Trang chủ và các trang Pillar đóng vai trò là "hồ chứa sức mạnh", truyền PageRank xuống các bài vệ tinh thông qua liên kết ngữ cảnh, đồng thời nhận lại tín hiệu uy tín tích lũy từ các bài vệ tinh.

### 1.2. Triết lý phân bổ URL chuẩn hóa
- **Tính thống nhất (Canonical Consistency)**: Mọi URL đều sử dụng giao thức bảo mật `https://`, tên miền chuẩn `flama.vn`, không sử dụng trailing slash thừa, phân cách các từ bằng dấu gạch ngang `-`.
- **Ánh xạ 100% với Codebase thực tế**: Toàn bộ đường dẫn được đối chiếu chặt chẽ với danh mục `PUBLIC_SITEMAP_CATALOG` (định nghĩa trong `app/services/seo_service.py`), router của React SPA (`frontend/src/app/routes/`) và dữ liệu cẩm nang (`frontend/src/features/guide/guideData.ts`).
- **Không tạo trang rỗng (Zero Thin/Empty Pages)**: Mỗi URL vệ tinh đều giải quyết một khía cạnh nghiệp vụ cụ thể, có dung lượng tối thiểu từ 1,000 đến 2,500 từ và nhúng dữ liệu có cấu trúc Schema.org tương ứng.

---

## 2. SƠ ĐỒ PHÂN CẤP TỔNG THỂ 5 CỤM CHỦ ĐỀ

Toàn bộ hệ thống nội dung của Flama được cấu trúc theo mô hình mạng lưới 5 cụm chủ đề kết nối chặt chẽ:

```
                                  [ https://flama.vn ]
                       (PILLAR TỐI CAO: BRAND ENTITY & WEB APP SHELL)
                                           │
         ┌───────────────────┬─────────────┴─────────────┬────────────────────┐
         │                   │                           │                    │
         ▼                   ▼                           ▼                    ▼
   [ CỤM CHỦ ĐỀ 1 ]    [ CỤM CHỦ ĐỀ 2 ]            [ CỤM CHỦ ĐỀ 3 ]     [ CỤM CHỦ ĐỀ 4 ]
   SRS & THAY THẾ ANKI  YOMITAN 1-CLICK MINING      LOCAL TTS VOICEVOX   MARKETPLACE & JLPT
         │                   │                           │                    │
   Pillar Page:        Pillar Page:                Pillar Page:         Pillar Page:
   /guide/study/       /guide/anki-import/         /guide/audio/        /guide/marketplace/
   spaced-repetition   yomitan-mining              local-tts            discovery
         │                   │                           │                    │
   ┌─────┴─────┐       ┌─────┴─────┐               ┌─────┴─────┐        ┌─────┴─────┐
   │ Satellites│       │ Satellites│               │ Satellites│        │ Satellites│
   │ (11 URLs) │       │ (5 URLs)  │               │ (5 URLs)  │        │ (8 URLs)  │
   └───────────┘       └───────────┘               └───────────┘        └───────────┘
         │                   │                           │                    │
         └───────────────────┴─────────────┬─────────────┴────────────────────┘
                                           │
                                           ▼
                                 [ CỤM PHỤ TRỢ & VỆ TINH THƯƠNG HIỆU ]
                                 /guide (Guide Portal Hub)
                                 /support (Hỗ trợ học viên & FAQ)
                                 /community-guidelines & /marketplace-guidelines
```

---

## 3. MA TRẬN ĐỐI CHIẾU 5 TRANG TRỤ CỘT & 33 TRANG VỆ TINH

Dưới đây là ma trận chi tiết ánh xạ toàn bộ 5 Trang Trụ Cột và 33 Trang Vệ Tinh vào cấu trúc ứng dụng và mã nguồn `PUBLIC_SITEMAP_CATALOG`:

### 3.1. Cụm Chủ Đề 0: Thực Thể Thương Hiệu & Cổng Trung Tâm (Brand & Hubs)
*Pillar Tối Cao: `https://flama.vn` | Số lượng vệ tinh phụ trợ: 4 URLs*

| # | Phân Loại | Canonical URL | Ánh Xạ Trong `PUBLIC_SITEMAP_CATALOG` | Từ Khóa Trọng Tâm | Ý Định Tìm Kiếm | Vai Trò Kiến Trúc & Mục Tiêu Nội Dung |
|:---:|:---|:---|:---|:---|:---:|:---|
| **P0** | **Pillar Tối Cao** | `https://flama.vn` | `{"path": "/", "priority": "1.0"}` | `flama`, `flama vn`, `flama tiếng nhật`, `học tiếng nhật flama` | Navigational | Tiếp nhận toàn bộ Brand Traffic, phân phối Link Equity xuống 5 cụm, kích hoạt Sitelinks 6 nhánh. |
| S0.1 | Satellite Hub | `https://flama.vn/guide` | `{"path": "/guide", "priority": "0.9"}` | `cẩm nang flama`, `hướng dẫn flama` | Nav / Info | Cổng thông tin trung tâm (Hub Portal), điều hướng học viên vào tất cả các chuyên mục cẩm nang. |
| S0.2 | Satellite Hub | `https://flama.vn/support` | `{"path": "/support", "priority": "0.7"}` | `hỗ trợ flama`, `trợ giúp học tiếng nhật` | Nav / Info | Trang trung tâm trợ giúp người học, tổng hợp FAQ và kênh liên hệ kỹ thuật trực tiếp. |
| S0.3 | Satellite Legal | `https://flama.vn/community-guidelines` | `{"path": "/community-guidelines", "priority": "0.6"}` | `quy chuẩn cộng đồng flama` | Informational | Quy tắc thảo luận văn minh, chia sẻ kinh nghiệm học tập tiếng Nhật và đóng góp học liệu. |
| S0.4 | Satellite Legal | `https://flama.vn/marketplace-guidelines` | `{"path": "/marketplace-guidelines", "priority": "0.6"}` | `quy định marketplace flama` | Informational | Chính sách kiểm duyệt bản quyền, tiêu chuẩn nội dung bộ thẻ và cơ chế bảo vệ tác giả. |

---

### 3.2. Cụm Chủ Đề 1: Spaced Repetition (SRS) & Nâng Cấp Thay Thế Anki
*Pillar Page: `https://flama.vn/guide/study/spaced-repetition` | Số lượng vệ tinh: 11 URLs*

| # | Phân Loại | Canonical URL | Ánh Xạ Trong `PUBLIC_SITEMAP_CATALOG` | Từ Khóa Trọng Tâm | Ý Định Tìm Kiếm | Vai Trò Kiến Trúc & Mục Tiêu Nội Dung |
|:---:|:---|:---|:---|:---|:---:|:---|
| **P1** | **Pillar Page** | `https://flama.vn/guide/study/spaced-repetition` | `{"path": "/guide/study/spaced-repetition", "priority": "0.8"}` | `học từ vựng srs`, `spaced repetition tiếng nhật`, `thuật toán fsrs anki` | Informational | **Trụ cột Cụm 1**: Cẩm nang toàn diện về khoa học lặp lại ngắt quãng, đường cong quên lãng Ebbinghaus và thuật toán FSRS. |
| S1.1 | Satellite Comp | `https://flama.vn/so-sanh/flama-vs-anki` | Trang so sánh độc lập (Landing Page) | `thay thế anki học tiếng nhật`, `app học từ vựng như anki` | Trans / Comm | Bảng so sánh trực quan 12 tiêu chí giữa Flama Web SPA và Anki Desktop cổ điển. |
| S1.2 | Satellite Guide | `https://flama.vn/guide/study/flashcard-flow` | `{"path": "/guide/study/flashcard-flow", "priority": "0.8"}` | `cách học từ vựng nhớ lâu bằng srs` | Informational | Hướng dẫn thực hành: cách đánh giá 4 mức độ Again, Hard, Good, Easy để nhớ từ vĩnh viễn. |
| S1.3 | Satellite Guide | `https://flama.vn/guide/anki-import/apkg-import` | `{"path": "/guide/import-sync/csv-wizard", "priority": "0.8"}` (Import Hub) | `chuyển anki sang flama`, `nhập file apkg` | Transactional | Hướng dẫn từng bước nhập nguyên vẹn file thẻ `.apkg` từ Anki sang Flama trong 60 giây. |
| S1.4 | Satellite Guide | `https://flama.vn/guide/import-sync/anki-connect-sync` | `{"path": "/guide/import-sync/anki-connect-sync", "priority": "0.8"}` | `đồng bộ anki không cần ankiweb` | Info / Trans | Hướng dẫn đồng bộ dữ liệu đám mây tự động qua Flama Connect mà không lo nghẽn AnkiWeb. |
| S1.5 | Satellite Guide | `https://flama.vn/guide/import-sync/csv-wizard` | `{"path": "/guide/import-sync/csv-wizard", "priority": "0.8"}` | `tạo flashcard bằng excel`, `nhập từ vựng csv` | Transactional | Hướng dẫn nhập danh sách từ vựng hàng loạt từ file Excel/Google Sheets bằng CSV Wizard. |
| S1.6 | Satellite Guide | `https://flama.vn/guide/getting-started/getting-started` | `{"path": "/guide/getting-started/getting-started", "priority": "0.8"}` | `anki tiếng nhật cho người mới` | Informational | Cẩm nang nhập môn học Flashcard tiếng Nhật từ con số 0 cho người mới bắt đầu. |
| S1.7 | Satellite Guide | `https://flama.vn/guide/getting-started/core-concepts` | `{"path": "/guide/getting-started/core-concepts", "priority": "0.8"}` | `khái niệm flashcard anki flama` | Informational | Giải thích bản chất 4 khái niệm nền tảng: Bộ thẻ (Deck), Ghi chú (Note), Trường (Field), Thẻ (Card). |
| S1.8 | Satellite Guide | `https://flama.vn/guide/dashboard/deck-grouping` | `{"path": "/guide/dashboard/deck-grouping", "priority": "0.8"}` | `quản lý bộ thẻ flashcard` | Informational | Hướng dẫn tổ chức cây thư mục bộ thẻ phân cấp cha-con trực quan bằng dấu `::`. |
| S1.9 | Satellite Guide | `https://flama.vn/guide/dashboard/study-metrics` | `{"path": "/guide/dashboard/study-metrics", "priority": "0.8"}` | `thống kê học tập flashcard` | Informational | Hướng dẫn đọc biểu đồ tỷ lệ ghi nhớ, phân bố thẻ Due/Learn/New và bảo vệ chuỗi Streak. |
| S1.10| Satellite Guide | `https://flama.vn/guide/note-types/cloze-deletion` | `{"path": "/guide/note-types/cloze-deletion", "priority": "0.8"}` | `thẻ đục lỗ cloze deletion tiếng nhật` | Info / Trans | Hướng dẫn tạo và sử dụng mẫu thẻ đục lỗ để ôn tập mẫu câu ngữ pháp và ngữ cảnh. |
| S1.11| Satellite Guide | `https://flama.vn/guide/study/shortcuts` | `{"path": "/guide/study/shortcuts", "priority": "0.8"}` | `phím tắt học flashcard flama` | Informational | Bảng tổng hợp phím tắt bàn phím (Space, 1-2-3-4, R) giúp tăng tốc độ ôn bài lên gấp 3 lần. |

---

### 3.3. Cụm Chủ Đề 2: Tiện Ích Yomitan & Khai Thác Từ Vựng 1-Click (Mining)
*Pillar Page: `https://flama.vn/guide/anki-import/yomitan-mining` | Số lượng vệ tinh: 5 URLs*

| # | Phân Loại | Canonical URL | Ánh Xạ Trong `PUBLIC_SITEMAP_CATALOG` | Từ Khóa Trọng Tâm | Ý Định Tìm Kiếm | Vai Trò Kiến Trúc & Mục Tiêu Nội Dung |
|:---:|:---|:---|:---|:---|:---:|:---|
| **P2** | **Pillar Page** | `https://flama.vn/guide/anki-import/yomitan-mining` | `{"path": "/guide/integrations/yomitan", "priority": "0.8"}` (Alias chuẩn) | `yomitan tiếng nhật`, `cách dùng yomitan`, `mining từ vựng yomitan` | Informational | **Trụ cột Cụm 2**: Hướng dẫn toàn diện về cài đặt Yomitan, cấu hình Flama Connect và kỹ thuật khai thác từ khi đọc báo/xem phim. |
| S2.1 | Satellite Guide | `https://flama.vn/guide/anki-import/yomitan-markers` | `{"path": "/guide/integrations/yomitan-markers", "priority": "0.8"}` | `field markers yomitan`, `pitch accent yomitan flashcard` | Informational | Bảng tra cứu 55 Field Markers chi tiết (`{marker:expression}`, `{marker:audio}`, `{marker:pitch-accent}`). |
| S2.2 | Satellite Guide | `https://flama.vn/guide/integrations/yomitan` | `{"path": "/guide/integrations/yomitan", "priority": "0.8"}` | `yomitan kết nối flama`, `yomitan anki bridge` | Transactional | Hướng dẫn kỹ thuật thiết lập Anki Server URL trên Yomitan trỏ thẳng về máy chủ Flama Connect. |
| S2.3 | Satellite Tech | `https://flama.vn/guide/integrations/mcp-ai` | `{"path": "/guide/integrations/mcp-ai", "priority": "0.8"}` | `mcp ai tiếng nhật`, `model context protocol flama` | Informational | Hướng dẫn kết nối AI Agent (Claude, ChatGPT) tra cứu từ vựng và tài liệu học tập Flama qua giao thức MCP. |
| S2.4 | Satellite Tech | `https://flama.vn/guide/integrations/mcp-tools` | `{"path": "/guide/integrations/mcp-tools", "priority": "0.8"}` | `công cụ mcp tìm kiếm bộ thẻ` | Informational | Đặc tả các API Tools an toàn của Flama MCP Server (tra cứu deck công khai, preview mẫu thẻ). |
| S2.5 | Satellite Fix | `https://flama.vn/guide/troubleshooting/yomitan` | `{"path": "/guide/troubleshooting/yomitan", "priority": "0.8"}` | `lỗi yomitan could not connect` | Informational | Hướng dẫn chẩn đoán và khắc phục nhanh lỗi không kết nối được server, sai CORS Origin hoặc token hết hạn. |

---

### 3.4. Cụm Chủ Đề 3: Công Nghệ Phát Âm Bản Xứ Local TTS (VoiceVox & Kokoro)
*Pillar Page: `https://flama.vn/guide/audio/local-tts` | Số lượng vệ tinh: 5 URLs*

| # | Phân Loại | Canonical URL | Ánh Xạ Trong `PUBLIC_SITEMAP_CATALOG` | Từ Khóa Trọng Tâm | Ý Định Tìm Kiếm | Vai Trò Kiến Trúc & Mục Tiêu Nội Dung |
|:---:|:---|:---|:---|:---|:---:|:---|
| **P3** | **Pillar Page** | `https://flama.vn/guide/audio/local-tts` | `{"path": "/guide/audio/batch-generation", "priority": "0.8"}` (Pillar Hub) | `phát âm tiếng nhật voicevox`, `tts tiếng nhật chuẩn ngữ điệu` | Info / Trans | **Trụ cột Cụm 3**: Giới thiệu công nghệ giọng đọc bản xứ VoiceVox và Kokoro TTS, phân tích ngữ điệu Tokyo (Pitch accent). |
| S3.1 | Satellite Product| `https://flama.vn/guide/flama-audio` | `{"path": "/guide/flama-audio", "priority": "0.8"}` | `phần mềm đọc từ vựng tiếng nhật offline`, `tải flama audio portable` | Transactional | Trang giới thiệu và cung cấp link tải ứng dụng máy tính Flama Audio Portable (.NET 8) chạy cổng 4791. |
| S3.2 | Satellite Tool | `https://flama.vn/guide/audio/batch-generation` | `{"path": "/guide/audio/batch-generation", "priority": "0.8"}` | `tạo âm thanh flashcard tiếng nhật`, `tích hợp voicevox vào flashcard` | Transactional | Hướng dẫn sử dụng công cụ sinh âm thanh hàng loạt tự động gắn audio giọng đọc vào hàng ngàn thẻ. |
| S3.3 | Satellite Config| `https://flama.vn/guide/audio/cloud-tts-keys` | `{"path": "/guide/audio/cloud-tts-keys", "priority": "0.8"}` | `khóa api cloud tts openai elevenlabs` | Info / Trans | Hướng dẫn người dùng nâng cao cấu hình khóa API OpenAI / ElevenLabs cá nhân trong tài khoản. |
| S3.4 | Satellite Study | `https://flama.vn/guide/study/audio-and-furigana` | `{"path": "/guide/study/audio-and-furigana", "priority": "0.8"}` | `audio flashcard tiếng nhật`, `luyện nghe tiếng nhật tts` | Transactional | Hướng dẫn cấu hình tự động phát âm thanh khi lật thẻ và ẩn hiện Furigana hỗ trợ phản xạ nghe. |
| S3.5 | Satellite Fix | `https://flama.vn/guide/troubleshooting/flama-audio`| `{"path": "/support", "priority": "0.7"}` (Chuyên mục Audio) | `sửa lỗi flama audio không phát tiếng` | Informational | Hướng dẫn xử lý sự cố không nghe thấy tiếng: kiểm tra xung đột cổng 4791, tường lửa Windows và thiết bị phát. |

---

### 3.5. Cụm Chủ Đề 4: Kho Marketplace Học Liệu & Lộ Trình Luyện Thi JLPT N5 - N1
*Pillar Page: `https://flama.vn/guide/marketplace/discovery` | Số lượng vệ tinh: 8 URLs*

| # | Phân Loại | Canonical URL | Ánh Xạ Trong `PUBLIC_SITEMAP_CATALOG` | Từ Khóa Trọng Tâm | Ý Định Tìm Kiếm | Vai Trò Kiến Trúc & Mục Tiêu Nội Dung |
|:---:|:---|:---|:---|:---|:---:|:---|
| **P4** | **Pillar Page** | `https://flama.vn/guide/marketplace/discovery` | `{"path": "/guide/marketplace/discovery", "priority": "0.8"}` | `chia sẻ bộ thẻ tiếng nhật`, `kho flashcard tiếng nhật cộng đồng` | Info / Trans | **Trụ cột Cụm 4**: Trung tâm khám phá kho học liệu cộng đồng, phân loại theo cấp độ JLPT N5–N1 và chuyên ngành. |
| S4.1 | Satellite Deck | `https://flama.vn/marketplace/jlpt-n5-minna` | Chuyên mục Marketplace Deck | `bộ thẻ tiếng nhật n5`, `bộ thẻ minna no nihongo 50 bài` | Transactional | Trang đích bộ thẻ N5: 25 bài sơ cấp Minna no Nihongo, 1,000 từ vựng và 100 chữ Hán có audio. |
| S4.2 | Satellite Deck | `https://flama.vn/marketplace/jlpt-n4-complete` | Chuyên mục Marketplace Deck | `flashcard tiếng nhật n4` | Transactional | Trang đích bộ thẻ N4: 25 bài trung cấp Minna no Nihongo, 1,500 từ vựng và 180 chữ Hán. |
| S4.3 | Satellite Deck | `https://flama.vn/marketplace/jlpt-n3-mimikara` | Chuyên mục Marketplace Deck | `từ vựng jlpt n3 anki`, `bộ thẻ từ vựng soumatome` | Trans / Comm | Trang đích bộ thẻ N3 Mimikara Oboeru & Soumatome: 1,800 từ vựng kèm ví dụ giao tiếp thực tế. |
| S4.4 | Satellite Deck | `https://flama.vn/marketplace/jlpt-n2-roadmap` | Chuyên mục Marketplace Deck | `lộ trình từ vựng jlpt n2`, `bộ thẻ shinkanzen master` | Info / Trans | Cẩm nang lộ trình học 2,500 từ vựng N2 trong 90 ngày kết hợp bộ thẻ tải về từng tuần. |
| S4.5 | Satellite Deck | `https://flama.vn/marketplace/jlpt-n1-advanced` | Chuyên mục Marketplace Deck | `bộ flashcard từ vựng n1` | Transactional | Trang đích bộ thẻ N1 cao cấp: 3,000 từ vựng chuyên sâu thời sự, báo chí và công việc IT/kinh tế. |
| S4.6 | Satellite Deck | `https://flama.vn/marketplace/kanji-2136-joyo` | Chuyên mục Marketplace Deck | `flashcard kanji n5 n1` | Transactional | Trang đích bộ thẻ 2,136 chữ Hán thường dùng (Joyo Kanji) kèm thứ tự nét, âm On-Kun và Hán Việt. |
| S4.7 | Satellite Tech | `https://flama.vn/guide/marketplace/overlay-clone` | `{"path": "/guide/marketplace/overlay-clone", "priority": "0.8"}` | `flama clone overlay` | Nav / Info | Cẩm nang kiến trúc Clone Overlay: giải thích cơ chế bảo vệ ghi chú riêng của học viên khi tác giả update deck. |
| S4.8 | Satellite Guide| `https://flama.vn/guide/marketplace/change-requests`| `{"path": "/guide/marketplace/change-requests", "priority": "0.8"}`| `đóng góp sửa lỗi bộ thẻ flashcard` | Informational | Hướng dẫn cơ chế gửi đề xuất sửa lỗi (Change Request) để cùng tác giả hoàn thiện học liệu mở. |

*Tổng cộng: 5 Trang Trụ Cột (P0 – P4) + 33 Trang Vệ Tinh = **38 URL Canonical Chuẩn Mực**, tạo thành một thể thống nhất hoàn hảo với `PUBLIC_SITEMAP_CATALOG`.*

---

## 4. QUY TẮC ĐIỀU HƯỚNG LIÊN KẾT NỘI BỘ 2 CHIỀU (2-WAY INTERNAL LINKING RULES)

Để dòng chảy sức mạnh liên kết (Link Equity) lưu thông liên tục và người học có trải nghiệm đọc liền mạch, Flama thiết lập 3 quy chuẩn điều hướng bắt buộc:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               QUY CHUẨN LIÊN KẾT 2 CHIỀU (VERTICAL ⬌ HORIZONTAL)                │
├────────────────────────────────┬────────────────────────────────┬───────────────────────────────┤
│ 1. CHIỀU DỌC (VERTICAL)        │ 2. CHIỀU NGANG (HORIZONTAL)    │ 3. THƯỢNG TẦNG (UPWARD)       │
│ Pillar ⬌ Cluster Satellite     │ Cross-Cluster Bridges          │ Về Trang Chủ Thương Hiệu      │
├────────────────────────────────┼────────────────────────────────┼───────────────────────────────┤
│ • Pillar trỏ xuống Satellites  │ • Kết nối logic hành vi:       │ • Mọi trang đều có Breadcrumb │
│   qua hộp "Chủ đề chuyên sâu"  │   Immersion ⬌ Local TTS Audio  │   và Logo trỏ về Trang chủ    │
│ • Satellite trỏ ngược Pillar   │   Anki Import ⬌ Yomitan Bridge │ • Nút CTA cuối bài: "Tạo tài  │
│   ngay trong 150 chữ đầu tiên  │   Bộ thẻ JLPT ⬌ Thuật toán SRS │   khoản Flama học miễn phí"   │
│ • Giữ vững ngữ cảnh Breadcrumb │   Marketplace ⬌ Clone Overlay  │ • Truyền dồn Authority về     │
│   3 cấp độ chuẩn SEO           │ • Tăng thời gian On-Site (Dwell)│   Entity gốc: https://flama.vn │
└────────────────────────────────┴────────────────────────────────┴───────────────────────────────┘
```

### 4.1. Liên kết chiều dọc (Vertical Linking: Pillar ⬌ Satellite)
1. **Từ Trang Pillar xuống các Bài Vệ Tinh**:
   - Ở phần mở đầu hoặc giữa bài viết Pillar, bắt buộc phải có một khối **Mục Lục Chuyên Đề (Topic Breakout Index)** liệt kê liên kết đến từng bài vệ tinh chuyên sâu.
   - Mỗi liên kết đi kèm một câu mô tả ngắn gọn giúp người học lựa chọn đúng vấn đề cần đào sâu.
2. **Từ Bài Vệ Tinh ngược về Trang Pillar**:
   - **Quy tắc 150 chữ đầu tiên (Above-the-fold Context)**: Trong đoạn mở đầu (150 chữ đầu bài viết), bắt buộc phải có ít nhất 1 liên kết ngữ cảnh trỏ ngược về bài Pillar tương ứng.  
     *Ví dụ trong bài `/guide/study/flashcard-flow`*: "Để hiểu rõ cơ sở khoa học phía sau phương pháp học này, bạn có thể tham khảo [Cẩm nang thuật toán Spaced Repetition (SRS)](/guide/study/spaced-repetition)."
   - **Khối chân trang (Footer Reference)**: Ở cuối bài viết, khối "Tài liệu học tập liên quan" phải luôn đặt bài Pillar ở vị trí ưu tiên số 1.
3. **Thanh điều hướng phân cấp (Breadcrumbs 3 cấp)**:
   - Tất cả các trang vệ tinh đều hiển thị thanh Breadcrumb rõ ràng:  
     `Trang chủ > Cẩm nang học tập > [Tên Cụm Chủ Đề] > [Tiêu Đề Bài Viết]`.

### 4.2. Liên kết chiều ngang liên cụm (Horizontal Cross-Cluster Bridges)
Học tiếng Nhật là một quy trình tương hỗ giữa đọc, nghe, ghi nhớ và làm bài tập. Do đó, các bài viết thuộc các cụm khác nhau phải được kết nối tự nhiên theo các kịch bản sử dụng thực tế:

- **Cầu nối 1: Khai thác từ vựng (Yomitan) ⬌ Phát âm bản xứ (Local TTS)**:
  - Từ bài `/guide/anki-import/yomitan-mining`, đặt liên kết sang `/guide/audio/local-tts`.  
    *Mẫu ngữ cảnh*: "Sau khi khai thác từ vựng từ anime, bạn nên [tự động gắn phát âm VoiceVox chuẩn Tokyo](/guide/audio/local-tts) để luyện phản xạ nghe đồng thời."
- **Cầu nối 2: Chuyển đổi Anki (Migration) ⬌ Khai thác 1-click (Yomitan Bridge)**:
  - Từ bài `/guide/anki-import/apkg-import`, đặt liên kết sang `/guide/anki-import/yomitan-mining`.  
    *Mẫu ngữ cảnh*: "Sau khi đã nhập dữ liệu từ Anki cũ, hãy trải nghiệm [cách tạo thẻ 1-click qua tiện ích Yomitan](/guide/anki-import/yomitan-mining) mượt mà mà không cần cài đặt Anki Desktop."
- **Cầu nối 3: Tải bộ thẻ JLPT ⬌ Phương pháp chấm điểm (Study Flow)**:
  - Từ các trang tải bộ thẻ `/marketplace/jlpt-n5-minna` hay `/marketplace/jlpt-n4-complete`, đặt liên kết sang `/guide/study/flashcard-flow`.  
    *Mẫu ngữ cảnh*: "Để ghi nhớ trọn bộ từ vựng này nhanh nhất, hãy áp dụng [nguyên tắc chấm điểm 4 nút SRS](/guide/study/flashcard-flow) trong mỗi phiên học."
- **Cầu nối 4: Khám phá Marketplace ⬌ Kiến trúc bảo vệ Clone Overlay**:
  - Từ bài giới thiệu kho thẻ `/guide/marketplace/discovery`, đặt liên kết sang `/guide/marketplace/overlay-clone`.  
    *Mẫu ngữ cảnh*: "Bạn hoàn toàn có thể yên tâm tải bộ thẻ về ghi chú riêng nhờ [cơ chế Clone Overlay độc quyền của Flama](/guide/marketplace/overlay-clone) bảo vệ dữ liệu cá nhân."

### 4.3. Liên kết thượng tầng (Upward Linking to Brand Core)
- Mọi trang trong hệ thống đều có logo ở góc trên bên trái gắn liên kết trực tiếp về Trang chủ `https://flama.vn`.
- Mỗi bài viết kết thúc bằng một hộp kêu gọi hành động (Sticky CTA Card):  
  *"Bắt đầu chinh phục tiếng Nhật cùng Flama ngay hôm nay — Hoàn toàn miễn phí."* trỏ về form đăng ký tài khoản tại Trang chủ.

---

## 5. CHIẾN LƯỢC ĐA DẠNG HÓA ANCHOR TEXT 4 TẦNG (4-TIER ANCHOR DIVERSIFICATION)

Thuật toán Google Penguin và các bộ lọc chống thao túng liên kết sẽ phạt nặng những website lạm dụng quá đà Anchor Text khớp chính xác (Exact Match Spam). Flama áp dụng tỷ lệ phân bổ Anchor Text vàng chuẩn mực ngành:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       MA TRẬN PHÂN BỔ ANCHOR TEXT CHỐNG PHẠT GOOGLE PENGUIN                     │
├───────────────────────────────────┬──────────────┬──────────────────────────────────────────────┤
│ Tầng Anchor Text                  │ Tỷ Lệ Mục Tiêu│ Mục Đích & Vai Trò Trong Xếp Hạng            │
├───────────────────────────────────┼──────────────┼──────────────────────────────────────────────┤
│ 1. Partial Match (Khớp cụm từ)    │ 35% – 40%    │ Chiếm tỷ trọng cao nhất; giàu ngữ cảnh tự    │
│                                   │              │ nhiên, giúp Google hiểu sâu sắc ngữ nghĩa.    │
├───────────────────────────────────┼──────────────┼──────────────────────────────────────────────┤
│ 2. Branded (Thương hiệu & Biến thể)│ 20% – 25%    │ Củng cố định danh thực thể Flama trong       │
│                                   │              │ Knowledge Graph, gia tăng chỉ số Brand Trust. │
├───────────────────────────────────┼──────────────┼──────────────────────────────────────────────┤
│ 3. Exact Match (Khớp chính xác)   │ 15% – 20%    │ Tập trung trực tiếp vào trang đích chuyển đổi,│
│                                   │              │ thúc đẩy leo Top cho từ khóa mục tiêu.       │
├───────────────────────────────────┼──────────────┼──────────────────────────────────────────────┤
│ 4. LSI & Natural (Từ khóa liên đới)│ 15% – 20%    │ Đa dạng hóa hồ sơ liên kết; mô tả hành động  │
│                                   │              │ và lợi ích thực tế của người học tiếng Nhật.  │
└───────────────────────────────────┴──────────────┴──────────────────────────────────────────────┘
```

### 5.1. Bảng Danh Mục Mẫu Anchor Text Cho Từng Cụm Chủ Đề

| Cụm Chủ Đề | Tầng Anchor Text | Tỷ Lệ Đề Xuất | Mẫu Anchor Text Chuẩn Mực Trong Bài Viết | Trang Đích Nhắm Đến |
|:---|:---|:---:|:---|:---|
| **Cụm 1: SRS & Thay thế Anki** | Exact Match | 15% – 20% | • `học từ vựng srs`<br>• `thay thế anki học tiếng nhật`<br>• `thuật toán fsrs anki` | • `/guide/study/spaced-repetition`<br>• `/so-sanh/flama-vs-anki`<br>• `/guide/study/spaced-repetition` |
| | Partial Match | 35% – 40% | • `phương pháp học từ vựng SRS khoa học`<br>• `ứng dụng thay thế Anki tốt nhất trên web`<br>• `cách nhập file .apkg từ Anki vào Flama` | • `/guide/study/spaced-repetition`<br>• `/so-sanh/flama-vs-anki`<br>• `/guide/anki-import/apkg-import` |
| | Branded | 20% – 25% | • `Flama SRS`<br>• `Flama Spaced Repetition`<br>• `Nền tảng Flama Web` | • `/guide/study/spaced-repetition`<br>• `https://flama.vn`<br>• `https://flama.vn` |
| | LSI & Natural | 15% – 20% | • `cách nhớ từ vựng tiếng Nhật không bao giờ quên`<br>• `đường cong quên lãng Ebbinghaus`<br>• `cách chấm điểm Again Hard Good Easy` | • `/guide/study/spaced-repetition`<br>• `/guide/study/spaced-repetition`<br>• `/guide/study/flashcard-flow` |
| **Cụm 2: Yomitan & Mining** | Exact Match | 15% – 20% | • `yomitan tiếng nhật`<br>• `cách dùng yomitan`<br>• `tạo card anki 1 click` | • `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining` |
| | Partial Match | 35% – 40% | • `hướng dẫn cài đặt Yomitan tra từ anime`<br>• `tiện ích Yomitan khai thác từ vựng 1-click`<br>• `kết nối Yomitan với Flama Connect` | • `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining` |
| | Branded | 20% – 25% | • `Flama Connect`<br>• `Flama Yomitan Bridge`<br>• `Cầu nối Flama` | • `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining` |
| | LSI & Natural | 15% – 20% | • `khai thác từ vựng khi đọc báo NHK Easy`<br>• `tra từ tiếng Nhật siêu tốc 0.1s trên Chrome`<br>• `bảng tra cứu 55 Field Markers` | • `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-mining`<br>• `/guide/anki-import/yomitan-markers` |
| **Cụm 3: Local TTS Audio** | Exact Match | 15% – 20% | • `phát âm tiếng nhật voicevox`<br>• `voicevox tiếng nhật miễn phí`<br>• `tải flama audio portable` | • `/guide/audio/local-tts`<br>• `/guide/audio/local-tts`<br>• `/guide/flama-audio` |
| | Partial Match | 35% – 40% | • `giọng đọc VoiceVox chuẩn ngữ điệu Tokyo`<br>• `tạo âm thanh flashcard tiếng Nhật tự động`<br>• `trợ lý phát âm tiếng Nhật ngoại tuyến Flama Audio` | • `/guide/audio/local-tts`<br>• `/guide/audio/batch-generation`<br>• `/guide/flama-audio` |
| | Branded | 20% – 25% | • `Flama Audio`<br>• `Flama Audio Desktop`<br>• `Flama TTS Engine` | • `/guide/flama-audio`<br>• `/guide/flama-audio`<br>• `/guide/audio/local-tts` |
| | LSI & Natural | 15% – 20% | • `luyện nghe phản xạ tiếng Nhật mỗi ngày`<br>• `so sánh giọng đọc AI và Google Dịch`<br>• `khắc phục lỗi không phát tiếng` | • `/guide/audio/local-tts`<br>• `/guide/audio/local-tts`<br>• `/guide/troubleshooting/flama-audio` |
| **Cụm 4: Marketplace & JLPT**| Exact Match | 15% – 20% | • `bộ thẻ tiếng nhật n5`<br>• `flashcard tiếng nhật n4`<br>• `flashcard kanji n5 n1` | • `/marketplace/jlpt-n5-minna`<br>• `/marketplace/jlpt-n4-complete`<br>• `/marketplace/kanji-2136-joyo` |
| | Partial Match | 35% – 40% | • `tải bộ thẻ Minna no Nihongo 50 bài chuẩn`<br>• `lộ trình từ vựng JLPT N2 trong 90 ngày`<br>• `cộng đồng chia sẻ bộ thẻ tiếng Nhật Flama` | • `/marketplace/jlpt-n5-minna`<br>• `/marketplace/jlpt-n2-roadmap`<br>• `/guide/marketplace/discovery` |
| | Branded | 20% – 25% | • `Flama Marketplace`<br>• `Kho thẻ Flama`<br>• `Kiến trúc Flama Clone Overlay` | • `/guide/marketplace/discovery`<br>• `/guide/marketplace/discovery`<br>• `/guide/marketplace/overlay-clone` |
| | LSI & Natural | 15% – 20% | • `tải học liệu tiếng Nhật có sẵn âm thanh`<br>• `bộ từ vựng Mimikara Oboeru chuẩn đề thi`<br>• `cách đóng góp sửa lỗi thẻ flashcard` | • `/guide/marketplace/discovery`<br>• `/marketplace/jlpt-n3-mimikara`<br>• `/guide/marketplace/change-requests` |

---

## 6. RANH GIỚI AN TOÀN CHỐNG SPAM & THUẬT TOÁN PENGUIN (ANTI-SPAM GUARDRAILS)

Để đảm bảo mạng lưới liên kết nội bộ luôn lành mạnh, tối đa hóa sức mạnh truyền dẫn và tuyệt đối không kích hoạt các tín hiệu cảnh báo của Google Search Quality Raters:

### 6.1. Mật độ liên kết nội bộ (Link Density Guardrail)
- **Quy tắc khoảng cách từ ngữ**: Không đặt liên tiếp các liên kết nội bộ sát nhau. Khoảng cách tối thiểu giữa hai liên kết nội bộ là **120 – 150 chữ**.
- **Chỉ tiêu theo độ dài bài viết**:
  - Bài viết ngắn (1,000 – 1,200 từ): Chứa tối đa **6 – 8 internal links**.
  - Bài viết tiêu chuẩn (1,500 – 2,000 từ): Chứa từ **8 – 12 internal links**.
  - Bài viết Pillar dài (2,500 – 3,500 từ): Chứa từ **12 – 18 internal links**.

### 6.2. Triệt tiêu các hành vi liên kết rác (Prohibited Linking Patterns)
1. **Nghiêm cấm Anchor Text rỗng**: Tuyệt đối không sử dụng các từ ngữ vô nghĩa như: *"tại đây"*, *"bấm vào đây"*, *"xem thêm"*, *"link này"*, *"click here"*. Anchor text bắt buộc phải chứa danh từ hoặc cụm động từ mô tả chính xác nội dung của trang đích.
2. **Cấm liên kết tự thân lặp kín (Circular Self-Linking)**: Một trang tuyệt đối không được chèn liên kết trỏ về chính URL hiện tại của nó trong phần thân văn bản.
3. **Cấm chèn liên kết ép uổng (Forced Linking)**: Mọi liên kết phải hòa hợp tự nhiên vào mạch văn học tập. Không được cố tình nhồi nhét từ khóa vào những câu không liên quan.
4. **Không dùng `rel="nofollow"` cho liên kết nội bộ**: Tất cả các liên kết trong cùng tên miền `flama.vn` phải là liên kết tự nhiên `dofollow` để dòng chảy PageRank được luân chuyển thông suốt.

### 6.3. Chuẩn mực kỹ thuật URL (Technical Link Quality)
- Luôn sử dụng URL chuẩn tuyệt đối (hoặc tương đối đúng root): `https://flama.vn/guide/study/spaced-repetition`.
- Tuyệt đối không trỏ liên kết qua các URL chuyển hướng (Redirect Chains: 301 / 302).
- Không gắn các tham số tracking UTM nội bộ (`?utm_source=...`) trong liên kết nội bộ vì sẽ làm loãng ngân sách thu thập dữ liệu (Crawl Budget) của bot tìm kiếm.

---

## 7. HƯỚNG DẪN BẢO TRÌ & QUY TRÌNH KIỂM TRA TÍNH TOÀN VẸN LIÊN KẾT

### 7.1. Checklist kiểm tra trước khi xuất bản bất kỳ bài viết mới
Trước khi đưa một bài viết vệ tinh hoặc trang đích lên hệ thống, tác giả nội dung phải tự kiểm tra 6 tiêu chí kỹ thuật:
- [ ] Thẻ `<link rel="canonical">` của trang trỏ chính xác về URL chính thức.
- [ ] Trong 150 chữ đầu tiên có ít nhất 1 liên kết trỏ ngược về bài viết Pillar của cụm.
- [ ] Tỷ lệ Anchor Text trong bài viết tuân thủ đúng khung phân bổ 4 tầng (ưu tiên Partial Match 35–40%).
- [ ] Có ít nhất 1 liên kết ngang (Cross-Cluster Bridge) sang một cụm chủ đề bổ trợ liên quan.
- [ ] Có khối CTA cuối bài dẫn dắt người học vào trải nghiệm thực tế trên Flama Web.
- [ ] Không có liên kết nào bị lỗi 404 hoặc chuyển hướng 301.

### 7.2. Tần suất rà soát và kiểm toán định kỳ
- **Hàng tuần**: Sử dụng công cụ Google Search Console (mục "Trang liên kết nội bộ") để kiểm tra số lượng liên kết trỏ về các trang Pillar trọng điểm. Đảm bảo 5 trang Pillar luôn nằm trong Top 10 trang có nhiều liên kết nội bộ nhất toàn site.
- **Hàng tháng**: Chạy script kiểm thử tự động toàn bộ cây sitemap `PUBLIC_SITEMAP_CATALOG` để phát hiện và vá ngay các trang mồ côi (Orphan Pages nếu có).

---

*Tài liệu Kiến trúc Nội dung Pillar - Cluster & Sơ đồ Liên kết Nội bộ Flama được phê duyệt và lưu trữ chính thức tại `docs/seo/PILLAR_CLUSTER_ARCHITECTURE.md`.*
