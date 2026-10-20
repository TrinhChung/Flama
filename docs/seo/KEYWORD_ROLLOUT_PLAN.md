# Kế Hoạch Triển Khai Toàn Diện 68 Từ Khóa Chiến Lược SEO Flama (3-Phase Keyword Rollout Plan)

> **Tài liệu chiến lược & lộ trình thực thi SEO cấp cao**  
> **Dự án**: Flama (https://flama.vn) — Nền tảng học tiếng Nhật & ghi nhớ Spaced Repetition thông minh  
> **Phiên bản**: 2.0.0 (Production Roadmap)  
> **Tác giả**: Flama SEO Strategy Team (teamwork_preview_worker_m1)  
> **Phạm vi kiểm kê**: **100% (68/68 từ khóa chiến lược)**, phân bổ chính xác theo 3 giai đoạn (Phase 1: 38 từ khóa, Phase 2: 15 từ khóa, Phase 3: 15 từ khóa)  
> **Tổng lượng tìm kiếm khai thác**: **46,350 lượt tìm kiếm/tháng (ước tính danh mục tài liệu) / 46,550 lượt tìm kiếm/tháng (tổng số học chính xác của 68 từ khóa)**  
> **Tài liệu tham chiếu & căn cứ**:
> - `docs/seo/KEYWORD_RESEARCH_MATRIX.md` (Ma trận gốc 68 từ khóa)
> - `docs/seo/BRAND_ENTITY_SEO_STRATEGY.md` (Chiến lược định danh thực thể & tam giác ngữ nghĩa)
> - `app/services/seo_service.py` (`PUBLIC_SITEMAP_CATALOG` 38 URL chuẩn hóa)
> - `.agents/teamwork/ORIGINAL_REQUEST.md` (Chỉ đạo người dùng về ngôn ngữ tự nhiên của người học)

---

## MỤC LỤC
1. [TỔNG QUAN CHIẾN LƯỢC & NGUYÊN TẮC ĐIỀU HÀNH](#1-tổng-quan-chiến-lược--nguyên-tắc-điều-hành)
2. [LỘ TRÌNH 3 GIAI ĐOẠN TỔNG THỂ (3-PHASE STRATEGIC ROADMAP)](#2-lộ-trình-3-giai-đoạn-tổng-thể-3-phase-strategic-roadmap)
3. [BẢNG DANH MỤC TOÀN BỘ 68 TỪ KHÓA CHIẾN LƯỢC (FULL 68-KEYWORD MASTER CATALOG)](#3-bảng-danh-mục-toàn-bộ-68-từ-khóa-chiến-lược-full-68-keyword-master-catalog)
4. [CHI TIẾT THỰC THI GIAI ĐOẠN 1: QUICK-WINS & BRAND DEFENSE (TUẦN 1–4)](#4-chi-tiết-thực-thi-giai-đoạn-1-quick-wins--brand-defense-tuần-14)
5. [CHI TIẾT THỰC THI GIAI ĐOẠN 2: AUTHORITY BUILDING & CORE FEATURES (TUẦN 5–8)](#5-chi-tiết-thực-thi-giai-đoạn-2-authority-building--core-features-tuần-58)
6. [CHI TIẾT THỰC THI GIAI ĐOẠN 3: HIGH-VOLUME COMMERCIAL SCALING (TUẦN 9–12)](#6-chi-tiết-thực-thi-giai-đoạn-3-high-volume-commercial-scaling-tuần-912)
7. [MA TRẬN PHÂN TÍCH GIAO THOA & BIỆN PHÁP TRIỆT TIÊU ĂN THỊT TỪ KHÓA (CANNIBALIZATION MITIGATION)](#7-ma-trận-phân-tích-giao-thoa--biện-pháp-triệt-tiêu-ăn-thịt-từ-khóa-cannibalization-mitigation)
8. [CHUYỂN NGỮ TRUY VẤN TỰ NHIÊN CỦA HỌC VIÊN TIẾNG NHẬT (ANTI-JARGON MAPPING)](#8-chuyển-ngữ-truy-vấn-tự-nhiên-của-học-viên-tiếng-nhật-anti-jargon-mapping)
9. [KHUNG THEO DÕI TIẾN ĐỘ & CHỈ TIẾU KPI THEO TỪNG GIAI ĐOẠN](#9-khung-theo-dõi-tiến-độ--chỉ-tiếu-kpi-theo-từng-giai-đoạn)

---

## 1. TỔNG QUAN CHIẾN LƯỢC & NGUYÊN TẮC ĐIỀU HÀNH

### 1.1. Bối cảnh cạnh tranh & Nhu cầu thực tế
Thị trường đào tạo tiếng Nhật tại Việt Nam có hơn 800,000 học viên thường trực, bao gồm thí sinh luyện thi JLPT N5–N1, sinh viên chuyên ngành tiếng Nhật, kỹ sư IT cầu nối (BrSE), tu nghiệp sinh tại Nhật Bản và cộng đồng người hâm mộ Anime/Manga thực hành phương pháp Immersion.

Tuy nhiên, người học đang đối mặt với các rào cản nghiêm trọng:
- **Anki Desktop truyền thống**: Giao diện cũ kỹ, khó cấu hình, dễ lỗi đồng bộ, phụ thuộc vào add-on phức tạp và máy chủ AnkiWeb chậm.
- **Tiện ích Yomitan tra từ**: Cực kỳ mạnh mẽ cho Immersion nhưng người dùng thường không biết cách kết nối với Anki hoặc phải mở song song phần mềm nặng nề.
- **Giọng đọc máy tính**: Google Dịch hay các bộ phát âm mặc định thường đơ cứng, đọc sai ngữ điệu chuẩn Tokyo hoặc sai âm đọc Kanji (Onyomi vs Kunyomi).
- **Chia sẻ bộ thẻ**: Các tệp `.apkg` trôi nổi trên mạng dễ bị trùng lặp, lỗi định dạng và mất sạch ghi chú riêng khi người dùng tải bản cập nhật mới.

Flama (https://flama.vn) giải quyết triệt để các rào cản này bằng kiến trúc Web SPA hiện đại, Spaced Repetition (SRS) thông minh, cầu nối Flama Connect 1-click không cần cài Anki Desktop, trợ lý Flama Audio (VoiceVox & Kokoro) giọng đọc anime bản xứ ngoại tuyến, cùng kiến trúc Clone Overlay độc quyền.

### 1.2. Mục tiêu chiến lược của kế hoạch 68 từ khóa
1. **Phòng thủ & Chiếm lĩnh thực thể Brand Search**: Đạt Top 1 tuyệt đối cho 12 từ khóa thương hiệu, kích hoạt Google Knowledge Panel và Sitelinks 6 nhánh, loại bỏ hoàn toàn nguy cơ nhầm lẫn với các thực thể trùng tên quốc tế (`flama.pt`, typography).
2. **Khai thác thị trường ngách đại dương xanh (Quick-Wins)**: Chiếm lĩnh Top 1–3 ngay trong 30 ngày đầu tiên cho 26 từ khóa ngách thuộc cụm Yomitan Mining và Local TTS VoiceVox (KD < 30), nơi đối thủ cạnh tranh hầu như chưa tối ưu SEO.
3. **Định vị Flama là giải pháp thay thế Anki hàng đầu (Authority Building)**: Thâm nhập Top 3–5 trong tháng thứ 2 cho cụm 15 từ khóa Spaced Repetition và Anki Alternative (KD 30–50), chuyển đổi người dùng gặp khó khăn trên Anki sang Flama Web.
4. **Đón đầu đỉnh sóng mùa thi JLPT (Commercial Scaling)**: Tấn công Top 5–10 trong tháng thứ 3 cho cụm 15 từ khóa khối lượng tìm kiếm cao (KD > 50) về bộ thẻ JLPT N5–N1, Minna no Nihongo 50 bài, Soumatome và Joyo Kanji.

---

## 2. LỘ TRÌNH 3 GIAI ĐOẠN TỔNG THỂ (3-PHASE STRATEGIC ROADMAP)

Kế hoạch triển khai được phân kỳ theo nguyên tắc **"Bảo vệ thực thể trước, khai thác ngách dễ, xây dựng thẩm quyền domain (Link Equity), rồi tấn công từ khóa thương mại lớn"**:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TIẾN TRÌNH TRIỂN KHAI 12 TUẦN                                   │
├──────────────────────────────┬──────────────────────────────────┬───────────────────────────────┤
│ GIAI ĐOẠN 1 (Tuần 1 – 4)      │ GIAI ĐOẠN 2 (Tuần 5 – 8)         │ GIAI ĐOẠN 3 (Tuần 9 – 12)     │
│ Quick-Wins & Brand Defense   │ Authority & Core Features        │ High-Volume Commercial Scale  │
├──────────────────────────────┼──────────────────────────────────┼───────────────────────────────┤
│ • 12 Từ khóa Brand           │ • 15 Từ khóa Feature 1 (SRS)     │ • 15 Từ khóa Feature 4 (JLPT) │
│ • 14 Từ khóa Yomitan Mining  │ • So sánh Flama vs Anki          │ • Lộ trình bộ thẻ N5 đến N1   │
│ • 12 Từ khóa Local TTS       │ • Phân tích FSRS vs SM-2         │ • Giáo trình Minna, Soumatome │
│ • Target: Top 1 Brand,       │ • Hướng dẫn nhập file .apkg      │ • Đón đầu cao điểm thi JLPT   │
│   Top 1–3 Niche Yomitan/TTS  │ • Target: Top 3–5 SRS / Anki Alts│ • Target: Top 3–5 N5/N4,      │
│                              │                                  │   Top 5–10 N3/N2/N1           │
├──────────────────────────────┼──────────────────────────────────┼───────────────────────────────┤
│ Quy mô: 38 Từ khóa           │ Quy mô: 15 Từ khóa               │ Quy mô: 15 Từ khóa            │
│ Volume: 21,300 visits/tháng  │ Volume: 13,800 visits/tháng      │ Volume: 11,250 visits/tháng   │
│ Tỷ trọng Volume: 45.95%      │ Tỷ trọng Volume: 29.77%          │ Tỷ trọng Volume: 24.27%       │
└──────────────────────────────┴──────────────────────────────────┴───────────────────────────────┘
```

### Bảng So Sánh Các Chỉ Số Giữa 3 Giai Đoạn

| Tiêu chí phân tích | Giai Đoạn 1 (Tuần 1–4) | Giai Đoạn 2 (Tuần 5–8) | Giai Đoạn 3 (Tuần 9–12) | Toàn bộ 12 tuần |
|:---|:---:|:---:|:---:|:---:|
| **Trọng tâm chủ đề** | Brand, Yomitan, Local TTS | Spaced Repetition, Thay thế Anki | Kho Marketplace, Bộ thẻ JLPT | Cả 5 Cụm Chủ Đề |
| **Dải Index Từ Khóa** | #1 – #12, #28 – #53 | #13 – #27 | #54 – #68 | #1 – #68 |
| **Tổng số lượng từ khóa** | **38 từ khóa** | **15 từ khóa** | **15 từ khóa** | **68 từ khóa** |
| **Tổng lượng tìm kiếm (Volume)** | **21,300/tháng** (thực tế: 21,600) | **13,800/tháng** (thực tế: 13,700) | **11,250/tháng** (thực tế: 11,250) | **46,350/tháng** (thực tế: 46,550) |
| **Khoảng độ khó (KD Range)** | KD 10 – 30 (Rất thấp đến thấp) | KD 20 – 50 (Thấp đến trung bình) | KD 25 – 65 (Trung bình đến cao) | Toàn dải KD 10 – 65 |
| **Mục tiêu thứ hạng SERP** | Top 1 Brand, Top 1–3 Niche | Top 3–5 SRS & Anki Alternatives | Top 3–5 Sơ cấp, Top 5–10 Trung/Cao cấp | 85%+ từ khóa vào Top 5 |
| **Tỷ lệ nhấp CTR mục tiêu** | > 75% Brand, 25–35% Niche | 15–25% Trang so sánh/cẩm nang | 10–20% Tải bộ thẻ & Marketplace | Tăng trưởng lũy tích |
| **Trang đích chính** | Homepage, Yomitan Pillar, TTS Hub | SRS Pillar, So sánh Anki, Import Guide | Marketplace Discovery, JLPT Landing | Toàn bộ Content Hub |

---

## 3. BẢNG DANH MỤC TOÀN BỘ 68 TỪ KHÓA CHIẾN LƯỢC (FULL 68-KEYWORD MASTER CATALOG)

Dưới đây là bảng dữ liệu chi tiết của toàn bộ **68 từ khóa chiến lược** được chuẩn hóa theo mã định danh (#1 đến #68), phân định rõ Intent, Volume, Độ khó thực tế, Giai đoạn phân bổ, Trang đích chuẩn hóa theo `PUBLIC_SITEMAP_CATALOG`, và giải pháp triệt tiêu hiện tượng ăn thịt từ khóa (Cannibalization Mitigation):

| # | Từ Khóa Chiến Lược | Cụm Chủ Đề | Ý Định Tìm Kiếm | Vol/Tháng | Độ Khó (KD Tag / Est.) | Giai Đoạn | Trang Đích Mục Tiêu (Target URL) | Tiêu Đề Bài Viết / Trang Đích Đề Xuất | Giải Pháp Chống Ăn Thịt Từ Khóa (Cannibalization Mitigation) |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---|:---|:---|
| **I** | **BRAND CLUSTER** | | | **8,450** | | **Phase 1** | | | |
| 1 | `flama` | Brand | Navigational | 2,400 | Low (KD <15) | Phase 1 | `https://flama.vn` | Flama — Nền Tảng Học Tiếng Nhật & SRS Flashcard Thông Minh | Trang chủ độc quyền định danh thực thể. Nhúng Schema Organization & WebSite. |
| 2 | `flama vn` | Brand | Navigational | 1,200 | Low (KD <15) | Phase 1 | `https://flama.vn` | Flama.vn — Nền Tảng Ghi Nhớ Ngoại Ngữ & Spaced Repetition | Tối ưu hóa tên miền ccTLD `.vn` và Geo-targeting Việt Nam trong thẻ Meta. |
| 3 | `flama tiếng nhật` | Brand | Nav / Info | 1,000 | Low (KD <15) | Phase 1 | `https://flama.vn` | Flama Tiếng Nhật — Học Từ Vựng, Kanji & Luyện Thi JLPT N5-N1 | Gắn đỉnh 2 tam giác ngữ nghĩa (`Tiếng Nhật`). Định hướng người học tìm kiếm tổng quan. |
| 4 | `học tiếng nhật flama` | Brand | Nav / Trans | 850 | Low (KD <20) | Phase 1 | `https://flama.vn` | Học Tiếng Nhật Cùng Flama: Ghi Nhớ Đỉnh Cao Với SRS | Trang chủ với CTA đăng ký trực tiếp "Học Ngay Miễn Phí", phân biệt với trang thông tin. |
| 5 | `app flama` | Brand | Nav / Trans | 700 | Low (KD <20) | Phase 1 | `https://flama.vn` | Ứng Dụng Học Flashcard Flama: Học Mọi Lúc Mọi Nơi | Nhấn mạnh tính năng Web App PWA không cần cài đặt từ App Store/CH Play. |
| 6 | `flama flashcard` | Brand | Navigational | 650 | Low (KD <20) | Phase 1 | `https://flama.vn` | Flama Flashcard: Tạo Thẻ Học Trong 30 Giây Với SRS | Nhấn mạnh tính năng tạo thẻ và học tập tức thì trên trang chủ; tránh nhầm với `#26`. |
| 7 | `flama srs` | Brand | Nav / Info | 450 | Low (KD <20) | Phase 1 | `https://flama.vn/guide/study/spaced-repetition` | Thuật Toán Lặp Lại Ngắt Quãng SRS Của Flama Hoạt Động Ra Sao? | Điều hướng thẳng vào bài hướng dẫn thuật toán SRS, liên kết ngược về Trang chủ. |
| 8 | `flama web` | Brand | Navigational | 400 | Low (KD <15) | Phase 1 | `https://flama.vn` | Flama Web: Trải Nghiệm Học Flashcard Trên Trình Duyệt | Tối ưu đoạn giới thiệu Web SPA, đăng nhập tức thì không rào cản nền tảng. |
| 9 | `flama connect` | Brand | Nav / Trans | 350 | Low (KD <20) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Flama Connect: Cầu Nối Khai Thác Từ Vựng 1-Click Không Cần Anki | Tối ưu hóa anchor text thương hiệu trỏ vào Pillar Yomitan; tránh nhầm với `#34`. |
| 10 | `flama audio` | Brand | Nav / Trans | 250 | Low (KD <20) | Phase 1 | `https://flama.vn/guide/flama-audio` | Tải Flama Audio Desktop: Giọng Đọc VoiceVox & Kokoro Miễn Phí | Dành riêng cho trang tải ứng dụng máy tính .NET 8; phân biệt với bài lý thuyết `#42`. |
| 11 | `flama marketplace` | Brand | Navigational | 120 | Low (KD <15) | Phase 1 | `https://flama.vn/guide/marketplace/discovery` | Kho Bộ Thẻ Flama Marketplace: Khám Phá & Tải Học Liệu Cộng Đồng | Trang hướng dẫn và khám phá chợ thẻ cộng đồng; phân biệt với từng deck lẻ. |
| 12 | `flama clone overlay` | Brand | Nav / Info | 80 | Low (KD <15) | Phase 1 | `https://flama.vn/guide/marketplace/overlay-clone` | Kiến Trúc Clone Overlay Của Flama: Tùy Biến Thẻ Không Lo Mất Ghi Chú | Bài viết kỹ thuật chuyên sâu bảo vệ bản quyền và dữ liệu ghi chú của người học. |
| **II** | **FEATURE 1: SRS & THAY THẾ ANKI** | | | **13,800** | | **Phase 2** | | | |
| 13 | `học từ vựng srs` | Feature 1: SRS | Informational | 1,900 | Med (KD ~45) | Phase 2 | `https://flama.vn/guide/study/spaced-repetition` | Phương Pháp Học Từ Vựng Bằng Spaced Repetition (SRS) Chuẩn Khoa Học | Trang Pillar chính của Cụm 1. Giải thích đường cong quên lãng Ebbinghaus. |
| 14 | `flashcard tiếng nhật srs` | Feature 1: SRS | Transactional | 1,500 | Med (KD ~42) | Phase 2 | `https://flama.vn` | Flashcard Tiếng Nhật SRS: Ghi Nhớ 2000 Kanji Không Bao Giờ Quên | Section chuyên biệt trên trang chủ có demo lật thẻ tương tác trực tiếp. |
| 15 | `thay thế anki học tiếng nhật` | Feature 1: SRS | Trans / Comm | 1,400 | Med (KD ~48) | Phase 2 | `https://flama.vn/so-sanh/flama-vs-anki` | Top Ứng Dụng Thay Thế Anki Học Tiếng Nhật Tốt Nhất 2026: Tại Sao Chọn Flama? | Landing page so sánh chi tiết dạng bảng: Web SPA vs Anki Desktop. |
| 16 | `spaced repetition tiếng nhật` | Feature 1: SRS | Informational | 1,200 | Low (KD ~28) | Phase 2 | `https://flama.vn/guide/study/spaced-repetition` | Spaced Repetition Trong Tiếng Nhật: Bí Quyết Đạt 90% Tỷ Lệ Ghi Nhớ | Phần H2 trọng tâm trong Pillar SRS, hướng dẫn áp dụng cho Kanji và Từ vựng. |
| 17 | `phần mềm lặp lại ngắt quãng` | Feature 1: SRS | Info / Trans | 1,100 | Med (KD ~40) | Phase 2 | `https://flama.vn` | Top Phần Mềm Lặp Lại Ngắt Quãng Đỉnh Nhất Hiện Nay | Tổng hợp giải pháp EdTech, định vị Flama dẫn đầu phân khúc học tiếng Nhật. |
| 18 | `anki tiếng nhật cho người mới` | Feature 1: SRS | Informational | 950 | Med (KD ~38) | Phase 2 | `https://flama.vn/guide/getting-started/getting-started` | Hướng Dẫn Học Flashcard Tiếng Nhật Cho Người Mới Bắt Đầu Từ A Đến Z | Hướng dẫn nhập môn học flashcard, giới thiệu lộ trình học từ N5 cho người mới. |
| 19 | `web học từ vựng lặp lại ngắt quãng` | Feature 1: SRS | Transactional | 900 | Low (KD ~25) | Phase 2 | `https://flama.vn` | Web Học Từ Vựng Lặp Lại Ngắt Quãng Miễn Phí, Đồng Bộ Tức Thì | Giải pháp nền tảng web không cần cài phần mềm; CTA vào phòng học tức thì. |
| 20 | `app học từ vựng như anki` | Feature 1: SRS | Transactional | 850 | Med (KD ~36) | Phase 2 | `https://flama.vn/so-sanh/flama-vs-anki` | Tìm Kiếm App Học Từ Vựng Giống Anki Nhưng Giao Diện Đẹp, Dễ Dùng? | Tối ưu H2 trong trang so sánh, giải quyết nỗi đau giao diện phức tạp của Anki. |
| 21 | `cách học từ vựng nhớ lâu bằng srs` | Feature 1: SRS | Informational | 800 | Low (KD ~22) | Phase 2 | `https://flama.vn/guide/study/flashcard-flow` | Cách Đánh Giá 4 Mức Độ Again, Hard, Good, Easy Để Thuộc Bài Vĩnh Viễn | Hướng dẫn thực hành: cách chọn nút chấm điểm chuẩn xác trong phiên học. |
| 22 | `chuyển anki sang flama` | Feature 1: SRS | Transactional | 650 | Low (KD ~18) | Phase 2 | `https://flama.vn/guide/anki-import/apkg-import` | Cách Nhập File .apkg Từ Anki Sang Flama Chỉ Trong 1 Phút | Hướng dẫn kỹ thuật import file `.apkg`; phân biệt với đồng bộ `#25` và tài nguyên `#66`. |
| 23 | `phần mềm flashcard tiếng nhật tốt nhất` | Feature 1: SRS | Comm / Trans | 600 | High (KD ~65) | Phase 2 | `https://flama.vn` | Đánh Giá Top 5 Phần Mềm Flashcard Tiếng Nhật Tốt Nhất Cho Người Việt | Bài đánh giá khách quan các công cụ Flashcard, đặt Flama làm lựa chọn tối ưu. |
| 24 | `thuật toán fsrs anki` | Feature 1: SRS | Informational | 550 | Low (KD ~24) | Phase 2 | `https://flama.vn/guide/study/spaced-repetition` | So Sánh Thuật Toán FSRS Và SM-2: Tại Sao Flama Tối Ưu Thời Gian Học? | Section chuyên sâu giải thích công thức FSRS giúp giảm 30% số thẻ ôn mỗi ngày. |
| 25 | `đồng bộ anki không cần ankiweb` | Feature 1: SRS | Info / Trans | 500 | Low (KD ~20) | Phase 2 | `https://flama.vn/guide/import-sync/anki-connect-sync` | Đồng Bộ Anki Trực Tiếp Lên Đám Mây Mượt Mà Với Flama Connect | Giải pháp đồng bộ hóa đám mây không lo nghẽn AnkiWeb; phân biệt với `#22`. |
| 26 | `quản lý bộ thẻ flashcard` | Feature 1: SRS | Informational | 450 | Low (KD ~22) | Phase 2 | `https://flama.vn/guide/dashboard/deck-grouping` | Cách Gom Nhóm Bộ Thẻ Cây Phân Cấp Bằng Dấu :: Đơn Giản Nhất | Hướng dẫn sắp xếp cây thư mục bộ thẻ cha-con trên Dashboard Flama. |
| 27 | `thẻ đục lỗ cloze deletion tiếng nhật` | Feature 1: SRS | Info / Trans | 350 | Low (KD ~20) | Phase 2 | `https://flama.vn/guide/note-types/cloze-deletion` | Cách Tạo Thẻ Đục Lỗ Cloze Deletion Học Ngữ Pháp Tiếng Nhật Hiệu Quả | Hướng dẫn định dạng mẫu thẻ đục lỗ `{{c1::từ vựng}}` để ôn tập ngữ cảnh. |
| **III** | **FEATURE 2: YOMITAN & 1-CLICK MINING** | | | **7,650** | | **Phase 1** | | | |
| 28 | `yomitan tiếng nhật` | Feature 2: Yomitan | Informational | 1,800 | Med (KD ~35) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Yomitan Tiếng Nhật: Tiện Ích Tra Từ Và Tạo Thẻ Flashcard Tốc Độ Cao | Trang Pillar chính của Cụm 2. Tổng quan từ cài đặt đến khai thác từ vựng. |
| 29 | `cách dùng yomitan` | Feature 2: Yomitan | Informational | 1,200 | Low (KD ~20) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Hướng Dẫn Cài Đặt & Sử Dụng Tiện Ích Yomitan Chi Tiết Nhất | Step-by-step HowTo hướng dẫn người mới cài tiện ích từ Chrome Web Store. |
| 30 | `mining từ vựng yomitan` | Feature 2: Yomitan | Info / Trans | 950 | Low (KD ~22) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Nghệ Thuật Mining Từ Vựng Bằng Yomitan: Đọc Đến Đâu Thuộc Đến Đó | Phương pháp khai thác từ thực tế trong quá trình đọc tài liệu và lướt web. |
| 31 | `yomitan kết nối flama` | Feature 2: Yomitan | Transactional | 650 | Low (KD ~15) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Kết Nối Tiện Ích Yomitan Với Flama Connect Không Cần Cài Anki Desktop | Hướng dẫn dán URL endpoint và API token của Flama vào cài đặt Yomitan. |
| 32 | `tiện ích yomitan đọc báo tiếng nhật` | Feature 2: Yomitan | Informational | 600 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Đọc Báo Tiếng Nhật NHK Easy & Tra Từ Siêu Tốc 0.1s Cùng Yomitan | Hướng dẫn ứng dụng thực tế tra từ trên trang tin tức NHK News Web Easy. |
| 33 | `tạo card anki 1 click` | Feature 2: Yomitan | Transactional | 550 | Med (KD ~32) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Tạo Flashcard 1-Click Tự Động Điền Kanji, Nghĩa, Audio Và Câu Ví Dụ | Giới thiệu cơ chế tự động điền các trường dữ liệu khi bấm nút dấu cộng. |
| 34 | `yomitan anki bridge` | Feature 2: Yomitan | Info / Trans | 450 | Low (KD ~20) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Flama Connect Bridge: Giải Pháp Thay Thế Hoàn Hảo Cho AnkiConnect | Bài viết giải thích cơ chế tương thích giao thức AnkiConnect trên đám mây. |
| 35 | `khai thác từ vựng tiếng nhật khi xem anime` | Feature 2: Yomitan | Informational | 400 | Low (KD ~25) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Cách Khai Thác Từ Vựng (Mining) Trực Tiếp Khi Xem Anime Có Phụ Đề Nhật | Hướng dẫn kết hợp Yomitan với asbplayer và phụ đề song ngữ để học từ tự nhiên. |
| 36 | `field markers yomitan` | Feature 2: Yomitan | Informational | 350 | Low (KD ~15) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-markers` | Bảng Tra Cứu Toàn Bộ 55 Field Markers Yomitan & Flama Chuẩn Xác | Trang cẩm nang kỹ thuật tra cứu 55 markers (`{marker:expression}`, `{marker:audio}`). |
| 37 | `yomitan trên điện thoại android` | Feature 2: Yomitan | Info / Trans | 300 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Cách Dùng Yomitan Bắn Thẻ Sang Flama Trên Kiwi Browser Điện Thoại | Hướng dẫn cài extension trên trình duyệt Kiwi Browser để học cơ động. |
| 38 | `cài từ điển cho yomitan` | Feature 2: Yomitan | Informational | 250 | Low (KD ~16) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Tổng Hợp Bộ Từ Điển Nhật - Việt, Nhật - Nhật Hay Nhất Cho Yomitan | Danh mục tải các bộ từ điển JMdict, KANJIDIC, từ điển Nhật - Việt tương thích. |
| 39 | `yomichan sang yomitan` | Feature 2: Yomitan | Informational | 200 | Low (KD ~12) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-mining` | Yomichan Đã Ngừng Cập Nhật: Hướng Dẫn Chuyển Sang Yomitan Ngay Hôm Nay | Hướng dẫn chuyển đổi cài đặt từ Yomichan cũ sang Yomitan đang được duy trì. |
| 40 | `pitch accent yomitan flashcard` | Feature 2: Yomitan | Informational | 150 | Low (KD ~14) | Phase 1 | `https://flama.vn/guide/anki-import/yomitan-markers` | Cách Tự Động Chèn Biểu Đồ Trọng Âm Pitch Accent Vào Thẻ Học Bằng Yomitan | Hướng dẫn cấu hình hiển thị biểu đồ ngữ điệu cao-thấp trong thẻ học. |
| 41 | `lỗi yomitan could not connect` | Feature 2: Yomitan | Informational | 100 | Low (KD ~15) | Phase 1 | `https://flama.vn/guide/troubleshooting/yomitan` | Khắc Phục Lỗi 'Could Not Connect to Anki/Flama Server' Trên Yomitan | Trang xử lý sự cố kỹ thuật riêng biệt; giải quyết lỗi CORS và sai URL server. |
| **IV** | **FEATURE 3: LOCAL TTS VOICEVOX & KOKORO** | | | **5,200** | | **Phase 1** | | | |
| 42 | `phát âm tiếng nhật voicevox` | Feature 3: TTS | Info / Trans | 1,100 | Low (KD ~22) | Phase 1 | `https://flama.vn/guide/audio/local-tts` | Phát Âm Tiếng Nhật Bằng VOICEVOX: Giọng Đọc Bản Xứ Tự Nhiên Miễn Phí | Trang Pillar chính của Cụm 3. Giới thiệu công nghệ VoiceVox và chất giọng bản xứ. |
| 43 | `luyện nghe tiếng nhật tts` | Feature 3: TTS | Informational | 900 | Med (KD ~36) | Phase 1 | `https://flama.vn/guide/audio/local-tts` | Luyện Nghe Phản Xạ Tiếng Nhật Hàng Ngày Với Trí Tuệ Nhân Tạo Text-To-Speech | Phương pháp nghe Shadowing và luyện phản xạ âm thanh khi ôn flashcard. |
| 44 | `voicevox tiếng nhật miễn phí` | Feature 3: TTS | Transactional | 750 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/audio/local-tts` | Cài Đặt VOICEVOX Miễn Phí Cho Windows: Hàng Trăm Giọng Anime Độc Đáo | Hướng dẫn cài đặt trọn gói miễn phí không cần đăng ký tài khoản đám mây. |
| 45 | `kokoro tts tiếng nhật` | Feature 3: TTS | Info / Trans | 600 | Low (KD ~16) | Phase 1 | `https://flama.vn/guide/audio/local-tts` | Kokoro TTS Tiếng Nhật: Mô Hình Giọng Đọc AI Nhẹ, Chuẩn Ngữ Điệu 2026 | Giới thiệu mô hình Kokoro 82M siêu nhẹ chạy mượt mà ngay trên CPU máy tính. |
| 46 | `tạo âm thanh flashcard tiếng nhật` | Feature 3: TTS | Transactional | 500 | Low (KD ~20) | Phase 1 | `https://flama.vn/guide/audio/batch-generation` | Công Cụ Tạo Âm Thanh Hàng Loạt Cho Hàng Ngàn Thẻ Flashcard Chỉ Trong 1 Phút | Giới thiệu công cụ Batch Audio Generator; phân biệt với bài học tập `#51`. |
| 47 | `tts tiếng nhật chuẩn ngữ điệu` | Feature 3: TTS | Informational | 450 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/audio/local-tts` | Tại Sao VoiceVox & Kokoro Phát Âm Tiếng Nhật Chuẩn Hơn Google Dịch? | Bài phân tích so sánh chất lượng ngữ điệu Tokyo (Pitch accent) với Google Dịch. |
| 48 | `phần mềm đọc từ vựng tiếng nhật offline` | Feature 3: TTS | Transactional | 350 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/flama-audio` | Flama Audio Companion: Trợ Lý Phát Âm Tiếng Nhật Ngoại Tuyến Không Cần Mạng | Giới thiệu ứng dụng máy tính Flama Audio chạy ngầm trên cổng mạng nội bộ 4791. |
| 49 | `tải flama audio portable` | Feature 3: TTS | Transactional | 200 | Low (KD <15) | Phase 1 | `https://flama.vn/guide/flama-audio` | Tải FlamaAudio-Portable.exe (.NET 8): Giải Pháp Phát Âm Cục Bộ Cổng 4791 | Trang cung cấp link tải trực tiếp file `.exe` portable không cần cài đặt rườm rà. |
| 50 | `tích hợp voicevox vào flashcard` | Feature 3: TTS | Transactional | 150 | Low (KD ~16) | Phase 1 | `https://flama.vn/guide/audio/batch-generation` | Cách Gắn Tự Động Giọng Đọc VoiceVox Vào Bộ Thẻ Tiếng Nhật Trên Flama | Hướng dẫn chọn voice model (Zundamon, Shikishiba...) và gắn vào trường âm thanh. |
| 51 | `audio flashcard tiếng nhật` | Feature 3: TTS | Transactional | 100 | Low (KD ~18) | Phase 1 | `https://flama.vn/guide/study/audio-and-furigana` | Cách Kết Hợp Furigana Và Tự Động Phát Âm Khi Lật Thẻ Flashcard | Hướng dẫn thiết lập tự động phát âm thanh trong phòng học; phân biệt với `#46`. |
| 52 | `khóa api cloud tts openai elevenlabs` | Feature 3: TTS | Info / Trans | 60 | Low (KD <15) | Phase 1 | `https://flama.vn/guide/audio/cloud-tts-keys` | Hướng Dẫn Cấu Hình API Key OpenAI & ElevenLabs Cho Giọng Đọc Cao Cấp | Hướng dẫn người dùng tự nhập khóa API đám mây cá nhân nếu có nhu cầu cao cấp. |
| 53 | `sửa lỗi flama audio không phát tiếng` | Feature 3: TTS | Informational | 40 | Low (KD <15) | Phase 1 | `https://flama.vn/guide/troubleshooting/flama-audio` | Khắc Phục Nhanh Sự Cố Không Nghe Thấy Âm Thanh Trên Flama Audio | Trang xử lý sự cố riêng biệt: kiểm tra cổng 4791, quyền firewall và thiết bị phát. |
| **V** | **FEATURE 4: KHO MARKETPLACE & JLPT** | | | **11,250** | | **Phase 3** | | | |
| 54 | `bộ thẻ tiếng nhật n5` | Feature 4: JLPT | Transactional | 2,100 | Med (KD ~48) | Phase 3 | `https://flama.vn/marketplace/jlpt-n5-minna` | Tải Bộ Thẻ Flashcard Tiếng Nhật N5 Chuẩn Giáo Trình Minna No Nihongo | Trang đích bộ thẻ N5: 25 bài Minna, 1000 từ vựng và 100 chữ Hán kèm audio. |
| 55 | `flashcard tiếng nhật n4` | Feature 4: JLPT | Transactional | 1,600 | Med (KD ~46) | Phase 3 | `https://flama.vn/marketplace/jlpt-n4-complete` | Bộ Flashcard Tiếng Nhật N4 Đầy Đủ Từ Vựng, Kanji Và Ngữ Pháp Có Audio | Trang đích bộ thẻ N4: 25 bài Minna trung cấp, 1500 từ vựng và 180 chữ Hán. |
| 56 | `từ vựng jlpt n3 anki` | Feature 4: JLPT | Trans / Comm | 1,400 | Med (KD ~45) | Phase 3 | `https://flama.vn/marketplace/jlpt-n3-mimikara` | Bộ Từ Vựng JLPT N3 Mimikara Oboeru & Soumatome: Học Ngay Trên Flama | Bộ thẻ N3 Mimikara Oboeru chuẩn thi, nhập vào tài khoản Flama với 1 click. |
| 57 | `lộ trình từ vựng jlpt n2` | Feature 4: JLPT | Info / Trans | 1,200 | High (KD ~62) | Phase 3 | `https://flama.vn/marketplace/jlpt-n2-roadmap` | Lộ Trình Nằm Lòng 2500 Từ Vựng JLPT N2 Trong 90 Ngày Với Spaced Repetition | Cẩm nang lộ trình học kèm liên kết cài đặt bộ thẻ N2 phân đoạn theo tuần. |
| 58 | `bộ flashcard từ vựng n1` | Feature 4: JLPT | Transactional | 950 | High (KD ~60) | Phase 3 | `https://flama.vn/marketplace/jlpt-n1-advanced` | Bộ Flashcard Từ Vựng JLPT N1 Đỉnh Cao Cho Kỹ Sư Và Dịch Thuật Viên | Bộ thẻ chuyên sâu 3000 từ vựng N1 kèm ví dụ thời sự báo chí và chính trị. |
| 59 | `chia sẻ bộ thẻ tiếng nhật` | Feature 4: JLPT | Info / Trans | 800 | Low (KD ~26) | Phase 3 | `https://flama.vn/guide/marketplace/discovery` | Cộng Đồng Chia Sẻ Bộ Thẻ Tiếng Nhật Đóng Góp Mở Trên Flama Marketplace | Trang Pillar chính của Cụm 4. Giới thiệu mô hình chia sẻ học liệu cộng đồng. |
| 60 | `kho flashcard tiếng nhật cộng đồng` | Feature 4: JLPT | Transactional | 750 | Low (KD ~25) | Phase 3 | `https://flama.vn/guide/marketplace/discovery` | Khám Phá Hàng Trăm Bộ Thẻ Tiếng Nhật Do Cộng Đồng Biên Soạn Miễn Phí | Khám phá kho tài nguyên phân loại theo cấp độ N5–N1, chuyên ngành IT, du lịch. |
| 61 | `bộ thẻ học tiếng nhật có audio` | Feature 4: JLPT | Transactional | 650 | Med (KD ~42) | Phase 3 | `https://flama.vn/guide/marketplace/discovery` | Tuyển Tập Các Bộ Thẻ Tiếng Nhật Có Sẵn Phát Âm Giọng Đọc Bản Xứ Chuẩn | Bộ lọc danh mục Marketplace cho các bộ thẻ đã nhúng sẵn âm thanh chuẩn. |
| 62 | `flashcard kanji n5 n1` | Feature 4: JLPT | Transactional | 550 | Med (KD ~45) | Phase 3 | `https://flama.vn/marketplace/kanji-2136-joyo` | Bộ Thẻ 2136 Chữ Hán Thường Dùng (Joyo Kanji) Kèm Thứ Tự Nét Và Âm Hán Việt | Trang đích chuyên sâu về chữ Hán: bộ thủ, thứ tự nét, âm On, âm Kun và nghĩa Hán Việt. |
| 63 | `bộ thẻ minna no nihongo 50 bài` | Feature 4: JLPT | Transactional | 450 | Med (KD ~44) | Phase 3 | `https://flama.vn/marketplace/jlpt-n5-minna` | Trọn Bộ Flashcard Minna No Nihongo 50 Bài Bản Chuẩn Kèm Ví Dụ & Audio | Tối ưu hóa từ khóa giáo trình quốc dân Minna no Nihongo trong landing N5. |
| 64 | `cách xuất bản bộ thẻ lên marketplace` | Feature 4: JLPT | Informational | 300 | Low (KD ~18) | Phase 3 | `https://flama.vn/guide/marketplace/creator-publishing` | Hướng Dẫn Tác Giả Xuất Bản Bộ Thẻ & Quản Lý Bản Phát Hành Trên Flama | Hướng dẫn tác giả đóng gói học liệu, định giá hoặc chia sẻ miễn phí. |
| 65 | `đóng góp sửa lỗi bộ thẻ flashcard` | Feature 4: JLPT | Informational | 200 | Low (KD ~16) | Phase 3 | `https://flama.vn/guide/marketplace/change-requests` | Cơ Chế Gửi Đề Xuất Sửa Lỗi (Change Request) Cải Thiện Bộ Thẻ Cộng Đồng | Hướng dẫn người học gửi yêu cầu sửa lỗi chính tả/nghĩa trực tiếp cho tác giả. |
| 66 | `tải file anki tiếng nhật` | Feature 4: JLPT | Transactional | 150 | Med (KD ~35) | Phase 3 | `https://flama.vn/guide/anki-import/apkg-import` | Tổng Hợp File Deck Anki Tiếng Nhật Và Hướng Dẫn Mở Bằng Flama Web | Hướng dẫn tìm kiếm và mở trực tiếp các file Anki mẫu trên Flama Web. |
| 67 | `bộ thẻ từ vựng soumatome` | Feature 4: JLPT | Transactional | 100 | Low (KD ~22) | Phase 3 | `https://flama.vn/marketplace/soumatome-decks` | Bộ Flashcard Giáo Trình Nihongo Soumatome N3-N2 Tối Ưu Học Ôn Thi | Trang đích bộ thẻ giáo trình Soumatome (Từ vựng, Ngữ pháp, Hán tự) cấp tốc. |
| 68 | `bộ thẻ shinkanzen master` | Feature 4: JLPT | Transactional | 50 | Low (KD ~20) | Phase 3 | `https://flama.vn/marketplace/shinkanzen-master` | Bộ Thẻ Shinkanzen Master N2-N1: Bí Quyết Chinh Phục Điểm Tuyệt Đối JLPT | Bộ thẻ luyện thi điểm cao Shinkanzen Master bám sát cấu trúc đề thi thật. |

---

## 4. CHI TIẾT THỰC THI GIAI ĐOẠN 1: QUICK-WINS & BRAND DEFENSE (TUẦN 1–4)

### 4.1. Mục tiêu chiến dịch & Chỉ số đo lường
- **Quy mô danh mục**: **38 từ khóa** (#1 – #12, #28 – #53).
- **Tổng lượng tìm kiếm tiềm năng**: **21,300 lượt tìm kiếm/tháng** (chiếm 45.95% toàn bộ ma trận).
- **Mục tiêu xếp hạng (Rank Targets)**:
  - **Top 1 tuyệt đối** cho toàn bộ 12 từ khóa thương hiệu Flama trong vòng 14 ngày đầu tiên.
  - **Top 1–3 SERP** cho 26 từ khóa ngách thuộc Cụm Yomitan Mining và Local TTS VoiceVox trong 30 ngày.
- **Kích hoạt Rich Snippets**:
  - Google Knowledge Panel chính thức cho thực thể thương hiệu `Flama`.
  - Google Sitelinks (6 nhánh điều hướng chính) và Sitelinks Search Box nhờ Schema.org `@graph` tại trang chủ.

### 4.2. Chiến thuật triển khai theo từng tuần

#### Tuần 1: Khóa chặt thực thể thương hiệu & Thiết lập hạ tầng On-Page
- Xuất bản và xác thực khối Schema.org JSON-LD `@graph` hợp nhất tại trang chủ `https://flama.vn`: bao gồm `Organization`, `WebSite`, `SoftwareApplication` và `FAQPage`.
- Đăng ký và liên kết chéo các hồ sơ số chính thức (`sameAs`): GitHub repo (`TrinhChung/Flama`), Fanpage Facebook, X/Twitter, Kênh YouTube và Discord.
- Tối ưu hóa thẻ `<title>` và `<meta name="description">` của Trang chủ chứa đầy đủ 3 đỉnh của Tam giác ngữ nghĩa: `Flama — Nền Tảng Học Tiếng Nhật & SRS Flashcard Thông Minh Thế Hệ Mới`.
- Gửi yêu cầu lập chỉ mục qua Google Search Console URL Inspection API.

#### Tuần 2: Xuất bản Cẩm nang Yomitan Pillar & Flama Connect Bridge
- Xuất bản bài viết Trụ cột (Pillar Page): `/guide/anki-import/yomitan-mining` (*Yomitan Tiếng Nhật: Tiện Ích Tra Từ Và Tạo Thẻ Flashcard Tốc Độ Cao*).
- Nhúng khối Schema `HowTo` 5 bước chi tiết: từ cài tiện ích trên Chrome Web Store, lấy endpoint Flama Connect, đến thao tác giữ Shift tra từ 1-click.
- Xuất bản trang tra cứu kỹ thuật: `/guide/anki-import/yomitan-markers` tổng hợp đầy đủ 55 Field Markers.
- Thiết lập liên kết nội bộ 2 chiều giữa Trang chủ và Pillar Yomitan với Anchor Text: `tiện ích Yomitan tiếng Nhật`, `khai thác từ vựng 1-click`.

#### Tuần 3: Đột phá thị trường ngách Local TTS & Ra mắt Flama Audio
- Xuất bản bài viết Trụ cột: `/guide/audio/local-tts` (*Phát Âm Tiếng Nhật Bằng VOICEVOX: Giọng Đọc Bản Xứ Tự Nhiên Miễn Phí*).
- Xuất bản trang tải trợ lý máy tính: `/guide/flama-audio` cung cấp file tải `FlamaAudio-Portable.exe (.NET 8)` chạy cổng nội bộ 4791.
- Xuất bản bài viết công cụ: `/guide/audio/batch-generation` hướng dẫn tạo âm thanh hàng loạt cho cả bộ thẻ trong 1 phút.
- Đặt các khối so sánh âm thanh trực quan (VoiceVox vs Google Dịch) để giữ chân người dùng (Dwell Time > 3 phút).

#### Tuần 4: Hoàn thiện các bài vệ tinh & Xử lý sự cố kỹ thuật
- Xuất bản 2 bài xử lý lỗi thường gặp để đón đầu truy vấn người dùng:
  - `/guide/troubleshooting/yomitan` (*Khắc Phục Lỗi "Could Not Connect to Anki/Flama Server" Trên Yomitan*).
  - `/guide/troubleshooting/flama-audio` (*Khắc Phục Nhanh Sự Cố Không Nghe Thấy Âm Thanh Trên Flama Audio*).
- Tối ưu hóa các bài ngách đọc báo NHK và xem Anime có phụ đề Nhật bằng tiện ích mở rộng.
- Rà soát thứ hạng tuần đầu trên Google Search Console: xác nhận 100% 38 từ khóa đã được lập chỉ mục (Indexed).

---

## 5. CHI TIẾT THỰC THI GIAI ĐOẠN 2: AUTHORITY BUILDING & CORE FEATURES (TUẦN 5–8)

### 5.1. Mục tiêu chiến dịch & Chỉ số đo lường
- **Quy mô danh mục**: **15 từ khóa** (#13 – #27).
- **Tổng lượng tìm kiếm tiềm năng**: **13,800 lượt tìm kiếm/tháng** (chiếm 29.77% toàn bộ ma trận).
- **Mục tiêu xếp hạng (Rank Targets)**:
  - Đưa cụm từ khóa học thuật Spaced Repetition (`học từ vựng srs`, `spaced repetition tiếng nhật`) vào **Top 3–5**.
  - Đưa từ khóa thương mại cạnh tranh trực diện với Anki (`thay thế anki học tiếng nhật`, `app học từ vựng như anki`) vào **Top 3**.
  - Tỷ lệ chuyển đổi học thử (Signup Conversion Rate) đạt **> 8%** từ người dùng truy cập trang so sánh.

### 5.2. Chiến thuật triển khai theo từng tuần

#### Tuần 5: Xuất bản Trang Trụ Cột Spaced Repetition (SRS) Toàn Diện
- Hoàn thiện bài Pillar học thuật: `/guide/study/spaced-repetition` (*Phương Pháp Học Từ Vựng Bằng Spaced Repetition (SRS) Chuẩn Khoa Học*).
- Độ dài đề xuất: 2,500 – 3,000 từ. Minh họa đồ thị đường cong quên lãng Ebbinghaus, phân tích chuyên sâu thuật toán FSRS (Free Spaced Repetition Scheduler) và cách nó giúp học viên ghi nhớ 2,000 từ vựng chỉ với 15 phút học mỗi ngày.
- Nhúng video ngắn hoặc ảnh GIF động minh họa 4 nút chấm điểm: *Again (1), Hard (2), Good (3), Easy (4)*.

#### Tuần 6: Tấn công từ khóa so sánh & Giải pháp thay thế Anki
- Xuất bản Landing Page chuyển đổi cao: `/so-sanh/flama-vs-anki` (*Top Ứng Dụng Thay Thế Anki Học Tiếng Nhật Tốt Nhất 2026: Tại Sao Chọn Flama?*).
- Xây dựng bảng so sánh 12 tiêu chí sống còn:
  1. Giao diện: Web SPA hiện đại, responsive điện thoại vs Giao diện cổ điển thập niên 2000 của Anki.
  2. Đồng bộ đám mây: Tự động qua Flama Cloud vs Cấu hình AnkiWeb dễ nghẽn mạng.
  3. Khai thác từ vựng (Mining): Flama Connect tích hợp sẵn vs Bắt buộc cài add-on AnkiConnect và mở Anki 24/7.
  4. Phát âm tiếng Nhật: Tích hợp sẵn VoiceVox anime chuẩn Tokyo vs Cài add-on AwesomeTTS rắc rối hoặc trả phí.
  5. Kho học liệu cộng đồng: Marketplace với Clone Overlay giữ ghi chú riêng vs File .apkg chia sẻ thủ công.
  6. Chi phí: Miễn phí hoàn toàn trên Web & Mobile vs AnkiMobile thu phí $24.99 trên iOS.
- Đặt nút kêu gọi hành động (CTA) nổi bật: "Dùng thử Flama Web ngay — Không cần cài đặt, không cần thẻ tín dụng".

#### Tuần 7: Mở rộng cẩm nang thao tác và nhập khẩu dữ liệu
- Xuất bản hướng dẫn di chuyển tài nguyên: `/guide/anki-import/apkg-import` (*Cách Nhập File .apkg Từ Anki Sang Flama Chỉ Trong 1 Phút*).
- Xuất bản bài viết đồng bộ: `/guide/import-sync/anki-connect-sync` (*Đồng Bộ Thẻ Anki Lên Đám Mây Mượt Mà Với Flama Connect*).
- Hướng dẫn nhập môn cho người mới: `/guide/getting-started/getting-started` (*Hướng Dẫn Học Flashcard Tiếng Nhật Cho Người Mới Bắt Đầu Từ A Đến Z*).

#### Tuần 8: Tối ưu tính năng thẻ nâng cao & Gom nhóm bộ thẻ
- Xuất bản bài viết: `/guide/note-types/cloze-deletion` hướng dẫn tạo thẻ đục lỗ học cấu trúc ngữ pháp.
- Xuất bản bài viết: `/guide/dashboard/deck-grouping` hướng dẫn phân cấp thư mục bộ thẻ cha-con bằng cú pháp `::`.
- Rà soát mạng lưới liên kết nội bộ: đảm bảo tất cả bài viết Giai đoạn 2 đều trỏ ngược về Pillar SRS và Trang chủ với các anchor text phong phú.

---

## 6. CHI TIẾT THỰC THI GIAI ĐOẠN 3: HIGH-VOLUME COMMERCIAL SCALING (TUẦN 9–12)

### 6.1. Mục tiêu chiến dịch & Chỉ số đo lường
- **Quy mô danh mục**: **15 từ khóa** (#54 – #68).
- **Tổng lượng tìm kiếm tiềm năng**: **11,250 lượt tìm kiếm/tháng** (chiếm 24.27% toàn bộ ma trận).
- **Mục tiêu xếp hạng (Rank Targets)**:
  - **Top 3–5** cho các từ khóa bộ thẻ cơ bản N5, N4 và Minna no Nihongo 50 bài.
  - **Top 5–10** cho các từ khóa cạnh tranh cao cấp N3, N2, N1 và 2136 Joyo Kanji.
- **Mục tiêu thương mại**:
  - Thu hút lượt tải bộ thẻ Marketplace tăng trưởng 200% trước mỗi kỳ thi JLPT (Tháng 7 và Tháng 12).
  - Tăng tỷ lệ người dùng tham gia đóng góp học liệu và xuất bản bộ thẻ lên Marketplace.

### 6.2. Chiến thuật triển khai theo từng tuần

#### Tuần 9: Ra mắt Trang Trụ Cột Marketplace & Bộ Thẻ Sơ Cấp N5 - N4
- Xuất bản bài Pillar Cụm 4: `/guide/marketplace/discovery` (*Cộng Đồng Chia Sẻ Bộ Thẻ Tiếng Nhật Đóng Góp Mở Trên Flama Marketplace*).
- Ra mắt 2 Landing Page bộ thẻ chuẩn giáo trình:
  - `/marketplace/jlpt-n5-minna` (*Tải Bộ Thẻ Flashcard Tiếng Nhật N5 Chuẩn Giáo Trình Minna No Nihongo 50 Bài*).
  - `/marketplace/jlpt-n4-complete` (*Bộ Flashcard Tiếng Nhật N4 Đầy Đủ Từ Vựng, Kanji Và Ngữ Pháp Có Audio*).
- Nhúng Schema `Course` cho từng bộ thẻ giáo trình, khai báo rõ ràng số lượng thẻ, thời lượng học ước tính và kiến thức giảng dạy.

#### Tuần 10: Triển khai Lộ trình Trung cấp JLPT N3 - N2
- Xuất bản Landing Page bộ thẻ: `/marketplace/jlpt-n3-mimikara` (*Bộ Từ Vựng JLPT N3 Mimikara Oboeru & Soumatome*).
- Xuất bản bài viết Lộ trình chiến lược: `/marketplace/jlpt-n2-roadmap` (*Lộ Trình Nằm Lòng 2500 Từ Vựng JLPT N2 Trong 90 Ngày Với Spaced Repetition*).
- Chia nhỏ lộ trình học thành 12 chặng tuần, mỗi chặng gắn nút tải trực tiếp 200 từ vựng vào tài khoản Flama của người học.

#### Tuần 11: Chinh phục Cao cấp JLPT N1 & Bộ Thẻ 2136 Joyo Kanji
- Xuất bản Landing Page bộ thẻ cao cấp: `/marketplace/jlpt-n1-advanced` (*Bộ Flashcard Từ Vựng JLPT N1 Đỉnh Cao Cho Kỹ Sư Và Dịch Thuật Viên*).
- Xuất bản Landing Page chữ Hán toàn diện: `/marketplace/kanji-2136-joyo` (*Bộ Thẻ 2136 Chữ Hán Thường Dùng Kèm Thứ Tự Nét Và Âm Hán Việt*).
- Bổ sung các bộ thẻ giáo trình luyện thi nổi tiếng: `/marketplace/soumatome-decks` và `/marketplace/shinkanzen-master`.

#### Tuần 12: Đòn bẩy công nghệ độc quyền (Clone Overlay & Change Request)
- Xuất bản bài cẩm nang chuyên sâu: `/guide/marketplace/overlay-clone` (*Kiến Trúc Clone Overlay Của Flama: Tùy Biến Thẻ Không Lo Mất Ghi Chú*).
- Xuất bản bài cẩm nang đóng góp cộng đồng: `/guide/marketplace/change-requests` (*Cơ Chế Gửi Đề Xuất Sửa Lỗi Cải Thiện Bộ Thẻ Cộng Đồng*).
- Xuất bản bài hướng dẫn người sáng tạo: `/guide/marketplace/creator-publishing` (*Hướng Dẫn Tác Giả Xuất Bản Bộ Thẻ & Quản Lý Bản Phát Hành Trên Flama*).
- Hoàn tất đợt tổng kiểm kê liên kết nội bộ toàn trang, xác nhận không có trang mồ côi (Zero Orphan Pages).

---

## 7. MA TRẬN PHÂN TÍCH GIAO THOA & BIỆN PHÁP TRIỆT TIÊU ĂN THỊT TỪ KHÓA (CANNIBALIZATION MITIGATION)

Hiện tượng **Tự ăn thịt từ khóa (Keyword Cannibalization)** xảy ra khi nhiều trang trong cùng một website cùng nhắm đến một từ khóa hoặc các biến thể ngữ nghĩa quá giống nhau, dẫn đến việc Google không xác định được trang nào là đại diện chính thức và làm tụt hạng cả hai.

Dưới đây là 4 nhóm giao thoa ngữ nghĩa chính trong danh mục 68 từ khóa và cơ chế phân định rạch ròi:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                       4 NHÓM GIAO THOA NGỮ NGHĨA & CƠ CHẾ TRIỆT TIÊU CANNIBALIZATION           │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────────────┤
│ Nhóm Giao Thoa           │ Các Từ Khóa Liên Quan       │ Cơ Chế Phân Định Rạch Ròi             │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────────────┤
│ 1. Nhóm Nhập/Tải Anki    │ #22, #25, #66               │ #22: Migration (Nhập .apkg của mình)  │
│                          │                             │ #25: Sync Cloud (Đồng bộ AnkiConnect) │
│                          │                             │ #66: Resource Hub (Tải file Anki mẫu) │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────────────┤
│ 2. Nhóm Tạo Thẻ & Yomitan│ #6, #26, #31, #33           │ #6: Brand Flashcard Tổng quan         │
│                          │                             │ #26: Quản lý Thư mục Cây phân cấp ::  │
│                          │                             │ #31: Hướng dẫn kết nối Token Server   │
│                          │                             │ #33: Kỹ thuật 1-Click Mining pop-up   │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────────────┤
│ 3. Nhóm Audio & Phát Âm  │ #46, #51, #61               │ #46: Batch Audio Generator (Kỹ thuật) │
│                          │                             │ #51: Audio phòng học & Furigana       │
│                          │                             │ #61: Bộ lọc Deck Marketplace có Audio │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────────────┤
│ 4. Nhóm Flama Connect    │ #9, #34, #41                │ #9: Thương hiệu Flama Connect (Pillar)│
│                          │                             │ #34: AnkiConnect Bridge (Kỹ thuật)    │
│                          │                             │ #41: Khắc phục mã lỗi CORS / Network  │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────────────┘
```

### 7.1. Nhóm 1: Nhập/Tải File Anki (#22, #25, #66)
- **#22 (`chuyển anki sang flama` - Vol 650)**: Nhắm vào ý định **Chuyển đổi nền tảng (Platform Migration)**. Người dùng đang dùng Anki Desktop, có sẵn file `.apkg` và muốn chuyển dữ liệu sang Flama. Trang đích: `/guide/anki-import/apkg-import`. Tiêu đề H1: *"Cách Nhập File .apkg Từ Anki Sang Flama Chỉ Trong 1 Phút"*.
- **#25 (`đồng bộ anki không cần ankiweb` - Vol 500)**: Nhắm vào ý định **Khắc phục sự cố đồng bộ đám mây (Cloud Syncing)**. Người dùng không muốn dùng tài khoản AnkiWeb do bị chặn hoặc chậm. Trang đích: `/guide/import-sync/anki-connect-sync`. Tiêu đề H1: *"Đồng Bộ Thẻ Anki Lên Đám Mây Tự Động Không Cần AnkiWeb"*.
- **#66 (`tải file anki tiếng nhật` - Vol 150)**: Nhắm vào ý định **Tìm kiếm tài nguyên học liệu (Resource Gathering)**. Người dùng chưa có thẻ, đang tìm link tải file Anki mẫu trên mạng. Trang đích điều hướng về kho tài nguyên hoặc Marketplace. Tiêu đề H1: *"Tổng Hợp File Deck Anki Tiếng Nhật N5-N1 Chuẩn & Cách Mở Bằng Flama Web"*.

### 7.2. Nhóm 2: Tạo Thẻ Flashcard & Kết Nối Yomitan (#6, #26, #31, #33)
- **#6 (`flama flashcard` - Vol 650)**: Ý định điều hướng thương hiệu (Brand Navigational) trỏ về Trang chủ `https://flama.vn`.
- **#26 (`quản lý bộ thẻ flashcard` - Vol 450)**: Tập trung vào tính năng tổ chức dữ liệu: cách tạo thư mục con, gom nhóm bộ thẻ bằng cú pháp dấu hai chấm đôi `::` trên Dashboard. Trang đích: `/guide/dashboard/deck-grouping`.
- **#31 (`yomitan kết nối flama` - Vol 650)**: Hướng dẫn cấu hình API token và server endpoint trên giao diện Settings của Yomitan. Trang đích: `/guide/anki-import/yomitan-mining`.
- **#33 (`tạo card anki 1 click` - Vol 550)**: Hướng dẫn trải nghiệm người dùng khi lướt web: rê chuột, bấm dấu cộng và tự động điền các trường Kanji, âm đọc Furigana, nghĩa và audio.

### 7.3. Nhóm 3: Audio Phát Âm Flashcard (#46, #51, #61)
- **#46 (`tạo âm thanh flashcard tiếng nhật` - Vol 500)**: Bài viết về **Công cụ kỹ thuật (Tooling)**: Sử dụng tính năng Batch Audio Generator trong Flama để sinh file âm thanh hàng loạt cho 1,000 thẻ chỉ với 1 cú click. Trang đích: `/guide/audio/batch-generation`.
- **#51 (`audio flashcard tiếng nhật` - Vol 100)**: Bài viết về **Trải nghiệm phòng học (Study UX)**: Cách bật chế độ tự động phát âm khi lật thẻ, hiển thị Furigana đi kèm để ôn tập phản xạ nghe. Trang đích: `/guide/study/audio-and-furigana`.
- **#61 (`bộ thẻ học tiếng nhật có audio` - Vol 650)**: Ý định **Tìm kiếm học liệu thương mại (Marketplace Discovery)**: Người dùng muốn tìm các bộ thẻ làm sẵn đã có âm thanh giọng bản xứ để tải về học ngay. Trang đích: `/guide/marketplace/discovery`.

### 7.4. Nhóm 4: Flama Connect & Yomitan Bridge (#9, #34, #41)
- **#9 (`flama connect` - Vol 350)**: Tên thương hiệu dịch vụ, trỏ về bài Pillar Yomitan Mining với vai trò là Brand Anchor Text.
- **#34 (`yomitan anki bridge` - Vol 450)**: Bài viết giải thích kiến trúc kỹ thuật: Cách Flama Connect giả lập giao thức AnkiConnect trên môi trường đám mây an toàn.
- **#41 (`lỗi yomitan could not connect` - Vol 100)**: Tách riêng hoàn toàn sang trang khắc phục sự cố `/guide/troubleshooting/yomitan` để xử lý các mã lỗi CORS, sai cổng mạng hoặc token hết hạn mà không làm loãng nội dung bài Pillar chính.

---

## 8. CHUYỂN NGỮ TRUY VẤN TỰ NHIÊN CỦA HỌC VIÊN TIẾNG NHẬT (ANTI-JARGON MAPPING)

Tuân thủ nghiêm ngặt chỉ thị bổ sung từ người dùng tại `.agents/teamwork/ORIGINAL_REQUEST.md`:
> *"Cần tập trung cao độ vào các từ khóa thực tế mà người dùng cuối (end-user, học viên tiếng Nhật) tìm kiếm hàng ngày bằng ngôn ngữ tự nhiên. Tránh sa đà vào các thuật ngữ kỹ thuật/nội bộ quá hàn lâm (ví dụ: SM-2, FSRS backend logic, DB schema) khi xây dựng kế hoạch và dàn ý nội dung."*

Dưới đây là bảng chuyển ngữ toàn diện từ **Thuật ngữ kỹ thuật/hàn lâm nội bộ** sang **Từ khóa & Truy vấn thực tế của học viên**:

| # | Khái Niệm / Logic Kỹ Thuật Nội Bộ | Thuật Ngữ Hàn Lâm Cần Tránh Trên SERP | Cụm Tìm Kiếm Tự Nhiên Của Học Viên (Target Keyword) | Nỗi Đau & Nhu Cầu Thực Tế Của Người Học Tiếng Nhật |
|:---:|:---|:---|:---|:---|
| 1 | **Thuật toán Spaced Repetition (SRS)** | `SM-2 decay matrix`, `FSRS parameter weights`, `retrievability formula` | `học từ vựng srs`, `cách học từ vựng nhớ lâu bằng srs`, `app học từ vựng như anki` | Học sinh học trước quên sau, tốn hàng giờ chép từ nhưng vài tuần sau quên sạch. Muốn có phương pháp khoa học để thuộc từ vĩnh viễn và không bị ngợp bài ôn tập. |
| 2 | **Giao thức Flama Connect Bridge** | `AnkiConnect HTTP RPC proxy`, `CORS Origin regex allowlist`, `UUID token mapping` | `cách dùng yomitan`, `tạo card anki 1 click`, `yomitan kết nối flama` | Người học đọc báo NHK hay xem anime muốn bấm vào từ là tự động tạo thẻ học có đầy đủ nghĩa và audio, không muốn mở Anki Desktop hay cấu hình cổng mạng phức tạp. |
| 3 | **Local TTS Audio Desktop Companion** | `WPF .NET 8 host`, `Named pipe IPC port 4791`, `Kokoro ONNX runtime` | `phát âm tiếng nhật voicevox`, `voicevox tiếng nhật miễn phí`, `tts tiếng nhật chuẩn ngữ điệu` | Giọng đọc Google Dịch quá đơ cứng, đọc sai âm Kanji và ngữ điệu Tokyo; Cloud TTS (OpenAI/ElevenLabs) thì quá đắt. Người học cần giọng anime tự nhiên, chuẩn bản xứ và miễn phí. |
| 4 | **Mô hình Clone Overlay** | `Relational clone overlay deltas`, `JSON field_values AST diff`, `immutable source notes` | `bộ thẻ tiếng nhật n5`, `bộ thẻ minna no nihongo 50 bài`, `chia sẻ bộ thẻ tiếng nhật` | Học viên tải bộ thẻ Minna/Soumatome về muốn tự ghi chú thêm mẹo nhớ riêng, nhưng sợ tác giả cập nhật bản mới thì toàn bộ ghi chú của mình bị đè mất sạch. |
| 5 | **Phương pháp Immersion Learning** | `HTML5 audio proxy streaming`, `Subtitle parser timeline sync`, `Manga OCR capture` | `khai thác từ vựng tiếng nhật khi xem anime`, `tiện ích yomitan đọc báo tiếng nhật` | Người học chán ngấy các ví dụ sách giáo khoa gượng gạo, muốn học từ vựng thực tế trong phim ảnh, truyện tranh và tin tức đời sống hàng ngày của người Nhật. |
| 6 | **Cơ chế Phản hồi Change Request** | `Bidirectional pull request model`, `Three-way merge resolver`, `ChangeRequest inbox` | `đóng góp sửa lỗi bộ thẻ flashcard`, `cách xuất bản bộ thẻ lên marketplace` | Người học phát hiện bộ thẻ cộng đồng bị gõ sai chính tả hoặc sai nghĩa, muốn báo cho tác giả sửa ngay để cả cộng đồng cùng được học bản chuẩn xác nhất. |

---

## 9. KHUNG THEO DÕI TIẾN ĐỘ & CHỈ TIẾU KPI THEO TỪNG GIAI ĐOẠN

### 9.1. Khung Mục Tiêu Xếp Hạng SERP Tích Lũy 30 – 60 – 90 Ngày

| Mốc Thời Gian | % Từ Khóa Vào Top 10 | % Từ Khóa Vào Top 5 | % Từ Khóa Đạt Top 1–3 | Tổng Traffic Tìm Kiếm Tự Nhiên Ước Tính |
|:---:|:---:|:---:|:---:|:---:|
| **Sau 30 Ngày (Hết Giai đoạn 1)** | **55%** (38/68 từ khóa) | **40%** (27/68 từ khóa) | **25%** (Toàn bộ Brand + Niche TTS/Yomitan) | 4,500 – 6,500 visits/tháng |
| **Sau 60 Ngày (Hết Giai đoạn 2)** | **75%** (51/68 từ khóa) | **60%** (41/68 từ khóa) | **45%** (Thêm các từ khóa SRS & So sánh Anki) | 12,000 – 16,000 visits/tháng |
| **Sau 90 Ngày (Hết Giai đoạn 3)** | **90%** (61/68 từ khóa) | **80%** (54/68 từ khóa) | **65%** (Bao phủ cả các bộ thẻ JLPT N5–N1) | 25,000 – 35,000 visits/tháng |

### 9.2. Kế Hoạch Ứng Phó Khi Từ Khóa Bị Chững Hạng Hoặc Lỗi Index
1. **Trường hợp từ khóa không được lập chỉ mục sau 7 ngày**:
   - Kiểm tra `robots.txt` và HTTP Response header xem có thẻ `noindex` vô tình bị bật hay không.
   - Bổ sung ít nhất 3 liên kết nội bộ ngữ cảnh từ Trang chủ và các trang Pillar có chỉ số PageRank cao nhất trỏ về trang đó.
   - Dùng Google Search Console URL Inspection gửi yêu cầu lập chỉ mục lại kèm cập nhật ngày `lastmod` trong `sitemap.xml`.
2. **Trường hợp từ khóa bị chững ở vị trí Top 11–20 (Trang 2)**:
   - Bổ sung thêm 1 khối FAQ chuyên sâu gồm 3 câu hỏi thực tế của người học giải quyết triệt để Search Intent.
   - Thêm video hoặc hình ảnh minh họa có gắn thẻ `alt` giàu ngữ nghĩa để tăng Dwell Time.
   - Bổ sung anchor text từ khóa chính từ 2 bài viết vệ tinh có liên quan cùng cụm.
3. **Trường hợp phát hiện hiện tượng ăn thịt từ khóa (Cannibalization)**:
   - Đối chiếu với Ma trận Mục 7, điều chỉnh lại thẻ H1 và Title của trang thứ yếu để phân hóa rõ ràng ý định tìm kiếm.
   - Thiết lập liên kết một chiều từ trang thứ yếu trỏ về trang chính thức với Exact Match Anchor Text để truyền toàn bộ Link Equity.

---

*Kế hoạch triển khai toàn diện bộ 68 từ khóa SEO Flama được phê duyệt và lưu trữ chính thức tại `docs/seo/KEYWORD_ROLLOUT_PLAN.md`.*
