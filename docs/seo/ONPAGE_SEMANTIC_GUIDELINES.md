# Quy Chuẩn Tối Ưu On-Page & Neo Thực Thể Ngữ Nghĩa (On-Page & Semantic Entity Guidelines) — Flama.vn

> **Phiên bản**: 2.0 (Production-Ready)  
> **Cập nhật lần cuối**: 2026-10-20  
> **Phạm vi áp dụng**: Toàn bộ hệ thống URL công khai thuộc domain `https://flama.vn` (Trang chủ, Trang tính năng, Landing page so sánh, và Cẩm nang học tập `/guide/*`)  
> **Tài liệu tham chiếu**:  
> - `docs/seo/KEYWORD_RESEARCH_MATRIX.md` (Bộ 68 từ khóa chiến lược & Intent)  
> - `docs/seo/BRAND_ENTITY_SEO_STRATEGY.md` (Chiến lược định danh thực thể số & Tam giác ngữ nghĩa Flama)  
> - `docs/seo/PILLAR_CLUSTER_ARCHITECTURE.md` (Kiến trúc phân cấp 5 Pillar & 33 Cluster)  

---

## 1. TỔNG QUAN & NGUYÊN TẮC CỐT LÕI (CORE PRINCIPLES)

Trong kỷ nguyên tìm kiếm ngữ nghĩa hiện đại (Semantic Search, Google Knowledge Graph và AI Overviews / GEO), thuật toán Google không còn xếp hạng trang web đơn thuần dựa trên mật độ từ khóa (Keyword Density) mà đánh giá dựa trên:
1. **Định danh thực thể duy nhất (Entity Authority & Disambiguation)**: Phân biệt rõ rệt thực thể học tiếng Nhật `Flama (flama.vn)` với thương hiệu gia dụng Bồ Đào Nha, phông chữ typography hay từ vựng tiếng Tây Ban Nha.
2. **Độ gần ngữ cảnh của thực thể (Entity Proximity & Semantic Triangulation)**: Đánh giá mối quan hệ mật thiết giữa Flama và các khái niệm: *Spaced Repetition (SRS)*, *Yomitan*, *VoiceVox/Kokoro TTS*, *Anki Alternative*, và *JLPT N5–N1*.
3. **Dữ liệu có cấu trúc máy đọc (Structured Linked Data)**: Khai báo toàn bộ các node thực thể trong một đồ thị tri thức `@graph` liên kết mạch lạc, giúp bot tìm kiếm và AI Agents trích xuất thông tin chuẩn xác 100%.

---

## 2. CHECKLIST KỸ THUẬT TỐI ƯU ON-PAGE (TECHNICAL ON-PAGE CHECKLIST)

Mọi trang đích trong chiến dịch SEO của Flama bắt buộc phải vượt qua 6 tiêu chuẩn kỹ thuật On-Page trước khi xuất bản:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   ON-PAGE QUALITY GATEWAY (FLAMA.VN)                   │
├───────────────────┬────────────────────────────────────────────────────┤
│ 1. Thẻ Title      │ 50–60 ký tự, Chứa Brand + Primary Keyword          │
│ 2. Meta Desc      │ 145–160 ký tự, Hook hấp dẫn + CTA hành động        │
│ 3. URL Slug       │ Ngắn gọn, chuẩn kebab-case, chứa keyword không dấu │
│ 4. Phân cấp Head  │ Duy nhất 1 thẻ H1, H2-H3 logic, không nhảy cóc     │
│ 5. Hình ảnh/Media │ Định dạng WebP, Alt text giàu ngữ nghĩa, CLS = 0   │
│ 6. Canonical Tag  │ URL tuyệt đối HTTPS, tự tham chiếu, không trailing │
└───────────────────┴────────────────────────────────────────────────────┘
```

### 2.1. Quy Chuẩn Thẻ Tiêu Đề (`<title>`)
- **Độ dài hiển thị tối ưu**: 50 – 60 ký tự (tương đương 580 – 600 pixels trên màn hình máy tính). Không để tiêu đề bị cắt cụt bằng dấu ba chấm `...` trên Google SERP.
- **Vị trí từ khóa vàng**: Đặt Từ khóa chính (Primary Keyword) trong 30 ký tự đầu tiên của thẻ Title.
- **Ký tự phân cách thương hiệu**: Dùng dấu gạch đứng `|` hoặc dấu gạch ngang dài `—` để phân cách giữa tiêu đề bài viết và thương hiệu Flama.
- **Yếu tố thúc đẩy tỷ lệ nhấp chuột (CTR Boosters)**: Lồng ghép năm hiện tại (`2026`), con số cụ thể (`1-Click`, `60 Giây`, `50 Bài`, `2136 Từ`), hoặc tính từ chuyển đổi (`Miễn Phí`, `Chuẩn Tokyo`, `Nhớ Lâu`).
- **Cấu trúc chuẩn**:
  - *Trang chủ*: `Flama — Nền Tảng Học Tiếng Nhật & SRS Flashcard Thông Minh 2026` (59 ký tự)
  - *Trang Pillar*: `Phương Pháp Spaced Repetition (SRS) Tiếng Nhật | Flama Guide` (58 ký tự)
  - *Trang So sánh*: `Top Ứng Dụng Thay Thế Anki Học Tiếng Nhật Tốt Nhất 2026 | Flama` (60 ký tự)
  - *Trang Bộ thẻ*: `Bộ Thẻ Tiếng Nhật N5 Chuẩn Minna 50 Bài Có Audio | Flama` (55 ký tự)

### 2.2. Quy Chuẩn Thẻ Mô Tả (`<meta name="description">`)
- **Độ dài tối ưu**: 145 – 160 ký tự (tối đa 960 pixels trên Desktop, 680 pixels trên Mobile).
- **Cấu trúc 3 thành phần bắt buộc**:
  1. *Câu móc (Hook/Pain point)*: Nêu trực tiếp nỗi đau hoặc nhu cầu của người học (mau quên, khó dùng Anki, cần tra từ khi xem phim).
  2. *Giải pháp cốt lõi (Core Solution)*: Giới thiệu tính năng độc quyền của Flama (thuật toán lặp lại ngắt quãng, Yomitan 1-click, VoiceVox phát âm bản xứ).
  3. *Kêu gọi hành động (CTA)*: Thôi thúc người dùng nhấp chuột ngay ("Khám phá ngay", "Học miễn phí trên Web", "Tải bộ thẻ ngay").
- **Mẫu Meta Description chuẩn mực**:
  - *Trang chủ*:  
    `Học từ vựng tiếng Nhật nhớ lâu vĩnh viễn với Flama: Nền tảng Flashcard SRS thông minh, tra từ 1-click qua Yomitan, phát âm chuẩn Tokyo miễn phí. Bắt đầu ngay!` (158 ký tự)
  - *Trang Yomitan Mining*:  
    `Hướng dẫn cài đặt tiện ích Yomitan kết nối Flama Connect: Tra từ khi xem anime, đọc báo tiếng Nhật và lưu flashcard 1-click siêu tốc. Xem hướng dẫn chi tiết!` (157 ký tự)
  - *Trang Thay thế Anki*:  
    `Tìm kiếm app thay thế Anki học tiếng Nhật? Khám phá Flama: Giao diện web mượt mà, nhập file .apkg trong 60s, đồng bộ tức thì không cần AnkiWeb. Trải nghiệm ngay!` (159 ký tự)

### 2.3. Quy Chuẩn URL Slug & Thẻ Canonical (`<link rel="canonical">`)
- **Cấu trúc URL**: 100% chữ thường (lowercase), không dấu tiếng Việt, phân tách bằng dấu gạch ngang (`kebab-case`), không chứa ký tự đặc biệt, không đuôi file `.html`.
- **Ranh giới Canonical tuyệt đối**:
  - Mọi trang công khai phải khai báo thẻ canonical tuyệt đối: `<link rel="canonical" href="https://flama.vn/duong-dan-chuan" />`.
  - Không có dấu gạch chéo ở cuối (no trailing slash) đối với bài viết con.
  - **Xử lý URL đồng nghĩa (Alias Reconciliation)**:
    - Bài viết Yomitan Mining có 2 slug: `/guide/integrations/yomitan` và `/guide/anki-import/yomitan-mining`.
    - Quy định: URL chính thức chuẩn SEO là `https://flama.vn/guide/anki-import/yomitan-mining`. Nếu người dùng vào `/guide/integrations/yomitan`, hệ thống phải khai báo canonical trỏ về `/guide/anki-import/yomitan-mining` hoặc trả về mã chuyển hướng 301.

### 2.4. Phân Bổ Tiêu Đề Heading (H1, H2, H3 Hierarchy)
Quy tắc bất biến: **Chỉ duy nhất 1 thẻ `<h1>` trên mỗi URL**. Thẻ H1 phải chứa từ khóa chính của trang.
- **Cấp độ H1**: Xác lập thực thể và chủ đề duy nhất của trang.
- **Cấp độ H2**: Phân chia các khía cạnh chính của chủ đề, chứa các từ khóa phụ (Secondary Keywords) và từ khóa liên đới ngữ nghĩa (LSI).
- **Cấp độ H3**: Chia nhỏ các bước thực hành (Step-by-step), giải đáp thắc mắc con hoặc các câu hỏi trong khối FAQ.
- **Quy tắc cấm**: Tuyệt đối không nhảy cóc cấp độ (ví dụ: từ H1 nhảy thẳng xuống H3 bỏ qua H2), không dùng thẻ Heading cho các phần tử giao diện phụ như sidebar, footer copyright hoặc nút bấm.

---

## 3. TỐI ƯU HÓA THỰC THỂ THEO MÔ HÌNH TAM GIÁC NGỮ NGHĨA FLAMA (SEMANTIC TRIANGULATION)

### 3.1. Mô Hình Tam Giác Ngữ Nghĩa Flama (The Flama Semantic Triangle)

Để tách biệt Flama khỏi các thực thể toàn cầu trùng tên, mọi nội dung bài viết và trang đích đều phải được neo chắc chắn vào hệ thống 3 trục của **Tam Giác Ngữ Nghĩa Flama**:

```
                           [ THỰC THỂ ĐỈNH: FLAMA ]
                            (ID: https://flama.vn)
                                    /     \
                                   /       \
              Trục Thuật Toán & Phương Pháp \       Trục Công Cụ & Trải Nghiệm Học
                                  /           \
      [ Spaced Repetition (SRS) / Anki ] ────── [ Yomitan / VoiceVox & Kokoro TTS ]
                                  \           /
                                   \         /
                                Trục Học Liệu Thực Tế
                                     \     /
                          [ Lộ Trình JLPT N5 - N1 ]
                          (Minna, Soumatome, Joyo Kanji)
```

#### 5 Thực Thể Con Cốt Lõi (Core Child Entities)
1. **Spaced Repetition (SRS)**: Thuật toán lặp lại ngắt quãng, đường cong quên lãng Ebbinghaus, 4 nút đánh giá (Again, Hard, Good, Easy).
2. **Anki Alternative**: Tương thích file `.apkg`, đồng bộ đám mây tức thì không cần AnkiWeb, giao diện Web SPA hiện đại.
3. **Yomitan 1-Click Mining**: Tiện ích tra từ trên trình duyệt Chrome/Edge/Firefox, Flama Connect Bridge, 55 Field Markers.
4. **Local TTS (VoiceVox & Kokoro)**: Phát âm bản xứ Tokyo ngoại tuyến, ứng dụng máy tính Flama Audio (.NET 8), âm thanh chất lượng cao miễn phí.
5. **Kho Thẻ JLPT N5–N1 & Clone Overlay**: Giáo trình Minna no Nihongo, Soumatome, 2136 Joyo Kanji, cơ chế Clone Overlay bảo toàn ghi chú cá nhân.

---

### 3.2. Quy Tắc Đồng Xuất Hiện Ngữ Cảnh & Khoảng Cách Từ (Co-occurrence Proximity Rules)

Khoảng cách từ (Word Proximity Window) là tín hiệu hàng đầu để Google Knowledge Graph liên kết hai thực thể với nhau:

#### Quy tắc 1: Khoảng Cách Vàng 15 Từ Trong Đoạn Mở Đầu (Lead 15-Word Window)
Trong **100 từ đầu tiên** (đoạn mở đầu Lead Paragraph) của bất kỳ trang nào trên `flama.vn`, danh từ thương hiệu **"Flama"** bắt buộc phải xuất hiện cách không quá **15 từ** so với ít nhất **2 thực thể con** thuộc tam giác ngữ nghĩa.

```
[ Ví Dụ Chuẩn Vượt Qua Kiểm Duyệt ]
"Nền tảng học tiếng Nhật Flama ứng dụng thuật toán Spaced Repetition (SRS) 
 giúp bạn ghi nhớ từ vựng vĩnh viễn, kết hợp tiện ích Yomitan khai thác từ 1-click."
  ├── Từ "Flama" đến "Spaced Repetition (SRS)": 3 từ  ──► [ĐẠT: ≤ 15 từ]
  └── Từ "Spaced Repetition" đến "Yomitan":     9 từ  ──► [ĐẠT: ≤ 15 từ]
```

```
[ Ví Dụ Vi Phạm Cần Sửa Đổi ]
"Flama là một trang web rất hữu ích dành cho những ai đang muốn cải thiện khả năng ngôn ngữ 
 của mình một cách bài bản và nhanh chóng nhất trong năm nay thông qua hệ thống học thông minh 
 với công nghệ lặp lại ngắt quãng SRS..."
  └── Từ "Flama" đến "lặp lại ngắt quãng SRS": 32 từ  ──► [VI PHẠM: > 15 từ]
```

#### Quy tắc 2: Tần Suất Xuất Hiện Đồng Đều (Semantic Density)
Trong thân bài (Body content), mỗi 250 – 300 từ cần lồng ghép tự nhiên các cặp thực thể liên đới:
- Khi nói về *học từ vựng*, kết hợp với: *đường cong quên lãng*, *khoảng cách ôn tập*, *thẻ flashcard 2 mặt*.
- Khi nói về *Yomitan*, kết hợp với: *đọc báo NHK Easy*, *xem Anime có phụ đề*, *cầu nối Flama Connect*.
- Khi nói về *âm thanh phát âm*, kết hợp với: *ngữ điệu Tokyo (Pitch Accent)*, *giọng đọc VoiceVox*, *luyện nghe phản xạ Shadowing*.
- Khi nói về *tải bộ thẻ*, kết hợp với: *kiến trúc Clone Overlay*, *giáo trình Minna 50 bài*, *kỳ thi JLPT*.

---

### 3.3. Bảng Ánh Xạ Thực Thể Wikidata (Wikidata Entity Mapping)

Để chuẩn hóa ngữ nghĩa quốc tế cho Google Knowledge Graph và các mô hình AI Search (Perplexity, ChatGPT Search, Claude), Flama liên kết tường minh với các thực thể Wikidata chuẩn mực:

| Thực thể Flama | Quan hệ vị từ (Ontology Predicate) | Thực thể đích (Wikidata Entity) | Mã định danh Wikidata | Diễn giải ngữ nghĩa trên Knowledge Graph |
|---|---|---|---|---|
| **Flama** | `rdf:type` (isA) | Web application | [`Q166142`](https://www.wikidata.org/wiki/Q166142) | Ứng dụng nền tảng web hiện đại |
| **Flama** | `rdf:type` (isA) | Educational software | [`Q340169`](https://www.wikidata.org/wiki/Q340169) | Phần mềm giáo dục & đào tạo trực tuyến |
| **Flama** | `schema:teaches` | Japanese language | [`Q5287`](https://www.wikidata.org/wiki/Q5287) | Đào tạo và giảng dạy tiếng Nhật |
| **Flama** | `schema:teaches` | Kanji | [`Q82851`](https://www.wikidata.org/wiki/Q82851) | Chữ Hán tiếng Nhật (2136 chữ Joyo) |
| **Flama** | `schema:preparesFor` | JLPT (Japanese-Language Proficiency Test) | [`Q842398`](https://www.wikidata.org/wiki/Q842398) | Luyện thi chứng chỉ Năng lực Nhật ngữ N5–N1 |
| **Flama** | `schema:usesTechnique` | Spaced repetition | [`Q2300067`](https://www.wikidata.org/wiki/Q2300067) | Kỹ thuật ghi nhớ lặp lại ngắt quãng |
| **Flama** | `schema:alternativeTo`| Anki (software) | [`Q557098`](https://www.wikidata.org/wiki/Q557098) | Giải pháp hiện đại hóa thay thế phần mềm Anki |
| **Flama** | `schema:integratesWith`| Speech synthesis (TTS) | [`Q107604`](https://www.wikidata.org/wiki/Q107604) | Tích hợp tổng hợp giọng nói VoiceVox & Kokoro |

---

### 3.4. Định Danh Thực Thể Mạng Xã Hội Đồng Nhất (`sameAs`)

Tất cả các tài khoản mạng xã hội chính thức của Flama được khai báo đồng nhất qua thuộc tính `sameAs` trong Schema Organization để Google hợp nhất tín hiệu uy tín thương hiệu:
- **Kho lưu trữ mã nguồn**: `https://github.com/TrinhChung/Flama`
- **Trang cộng đồng Facebook**: `https://facebook.com/flama.vn`
- **Kênh thông tin X (Twitter)**: `https://x.com/flamavn`
- **Kênh video hướng dẫn YouTube**: `https://youtube.com/@flamavn`
- **Cộng đồng học tập Discord**: `https://discord.gg/flama`

---

## 4. ĐẶC TẢ CẤU TRÚC DỮ LIỆU SCHEMA.ORG JSON-LD (PRODUCTION TEMPLATES)

Toàn bộ các thực thể trên Flama được kết nối trong một khối `@graph` duy nhất, giúp bot tìm kiếm nhận diện toàn vẹn mạng lưới quan hệ giữa Doanh nghiệp, Trang web, Phần mềm, Khóa học, Hướng dẫn và Câu hỏi thường gặp.

### 4.1. Khối `@graph` Hợp Nhất Hoàn Chỉnh Cho Trang Chủ (`https://flama.vn`)

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://flama.vn/#organization",
      "name": "Flama",
      "alternateName": ["Flama Vietnam", "Flama Tiếng Nhật"],
      "legalName": "Flama Vietnam",
      "url": "https://flama.vn",
      "logo": {
        "@type": "ImageObject",
        "@id": "https://flama.vn/#logo",
        "url": "https://flama.vn/logo.png",
        "contentUrl": "https://flama.vn/logo.png",
        "caption": "Flama — Nền tảng học tiếng Nhật & SRS Flashcard",
        "width": 512,
        "height": 512
      },
      "image": {
        "@id": "https://flama.vn/#logo"
      },
      "sameAs": [
        "https://github.com/TrinhChung/Flama",
        "https://facebook.com/flama.vn",
        "https://x.com/flamavn",
        "https://youtube.com/@flamavn",
        "https://discord.gg/flama"
      ],
      "contactPoint": [
        {
          "@type": "ContactPoint",
          "contactType": "customer support",
          "url": "https://flama.vn/support",
          "availableLanguage": ["vi", "ja", "en"]
        }
      ],
      "description": "Flama là nền tảng học tiếng Nhật và ghi nhớ thông minh thế hệ mới, kết hợp thuật toán lặp lại ngắt quãng (SRS), khai thác từ vựng 1-click qua Yomitan bridge, phát âm chuẩn tự nhiên với Local TTS (VoiceVox & Kokoro), và cộng đồng chia sẻ bộ thẻ Flashcard."
    },
    {
      "@type": "WebSite",
      "@id": "https://flama.vn/#website",
      "url": "https://flama.vn",
      "name": "Flama",
      "description": "Nền tảng học tiếng Nhật & SRS Flashcard thông minh thế hệ mới",
      "publisher": {
        "@id": "https://flama.vn/#organization"
      },
      "inLanguage": "vi",
      "potentialAction": {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": "https://flama.vn/guide?q={search_term_string}"
        },
        "query-input": "required name=search_term_string"
      }
    },
    {
      "@type": ["SoftwareApplication", "EducationalApplication"],
      "@id": "https://flama.vn/#app",
      "name": "Flama",
      "alternateName": "Flama Flashcard App",
      "applicationCategory": "EducationalApplication",
      "operatingSystem": "Web, Windows, macOS, Linux, Android, iOS",
      "softwareVersion": "2.0.0",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "VND",
        "availability": "https://schema.org/InStock",
        "description": "Bắt đầu học miễn phí hoàn toàn không giới hạn số lượng thẻ"
      },
      "publisher": {
        "@id": "https://flama.vn/#organization"
      },
      "description": "Ứng dụng học từ vựng tiếng Nhật thông minh với thuật toán Spaced Repetition (SRS), tích hợp Yomitan 1-click mining, Local TTS VoiceVox & Kokoro phát âm tự nhiên miễn phí, và kho bộ thẻ JLPT N5 đến N1.",
      "featureList": [
        "Thuật toán lặp lại ngắt quãng Spaced Repetition (SRS) thông minh",
        "Tích hợp tiện ích Yomitan khai thác từ vựng 1-click trực tiếp từ anime manga báo chí",
        "Phát âm chuẩn ngữ điệu bản xứ Tokyo với Local TTS VoiceVox & Kokoro ngoại tuyến miễn phí",
        "Kho Marketplace chia sẻ bộ thẻ cộng đồng với kiến trúc Clone Overlay bảo vệ ghi chú cá nhân",
        "Đồng bộ hai chiều với Anki và nhập khẩu nguyên vẹn file .apkg không giới hạn"
      ],
      "screenshot": "https://flama.vn/screenshots/study-screen.png",
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.9",
        "ratingCount": "128",
        "bestRating": "5",
        "worstRating": "1"
      }
    },
    {
      "@type": "Course",
      "@id": "https://flama.vn/#course-jlpt-n5-n1",
      "name": "Lộ Trình Từ Vựng & Flashcard Tiếng Nhật Toàn Diện JLPT N5 - N1",
      "description": "Chương trình học từ vựng, chữ Hán và ngữ pháp tiếng Nhật có hệ thống từ sơ cấp N5 đến cao cấp N1 ứng dụng phương pháp Spaced Repetition (SRS).",
      "provider": {
        "@id": "https://flama.vn/#organization"
      },
      "inLanguage": "vi",
      "educationalLevel": "Beginner to Advanced (JLPT N5 - N1)",
      "teaches": [
        "2136 Chữ Hán Thường Dùng (Joyo Kanji)",
        "Từ vựng tiếng Nhật N5 - N4 chuẩn giáo trình Minna no Nihongo",
        "Từ vựng và ngữ pháp JLPT N3 - N2 giáo trình Soumatome & Mimikara Oboeru",
        "Từ vựng nâng cao JLPT N1 chuyên sâu cho công việc và dịch thuật"
      ],
      "hasCourseInstance": {
        "@type": "CourseInstance",
        "courseMode": "Online",
        "courseWorkload": "PT15M/D",
        "instructor": {
          "@type": "Organization",
          "name": "Đội ngũ Học thuật Flama Vietnam"
        }
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://flama.vn/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "Flama là gì và có điểm gì khác biệt so với các app học tiếng Nhật khác?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Flama là nền tảng học tiếng Nhật và flashcard thông minh kết hợp thuật toán Spaced Repetition (SRS) chuẩn khoa học, tiện ích Flama Connect giúp khai thác từ vựng 1-click qua Yomitan, phát âm bản xứ với Local TTS VoiceVox & Kokoro hoàn toàn miễn phí, và cơ chế Clone Overlay độc quyền bảo vệ ghi chú cá nhân."
          }
        },
        {
          "@type": "Question",
          "name": "Flama có thay thế được Anki không?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Có. Flama là giải pháp nâng cấp toàn diện cho Anki với giao diện web hiện đại, mượt mà trên mọi thiết bị, đồng bộ đám mây tức thì không cần AnkiWeb, hỗ trợ nhập khẩu nguyên vẹn tệp .apkg và kết nối Yomitan dễ dàng mà không bị lỗi cổng kết nối."
          }
        },
        {
          "@type": "Question",
          "name": "Làm thế nào để khai thác từ vựng (mining) 1-click từ Yomitan vào Flama?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Bạn chỉ cần dán URL endpoint Flama Connect trong tài khoản Flama vào phần thiết lập Anki Server của tiện ích Yomitan trên trình duyệt Chrome/Edge hoặc Kiwi Browser trên điện thoại. Khi đọc báo hoặc xem anime, bấm nút dấu cộng trên pop-up Yomitan là từ vựng lập tức được lưu vào bộ thẻ Flama."
          }
        },
        {
          "@type": "Question",
          "name": "Công nghệ phát âm Flama Audio hoạt động ra sao và có mất phí không?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Flama Audio là ứng dụng máy tính (.NET 8) chạy ngoại tuyến trên Windows, tích hợp sẵn mô hình VoiceVox và Kokoro TTS. Bạn có thể nghe phát âm chuẩn ngữ điệu Tokyo hoàn toàn miễn phí, không giới hạn số lượng từ và không tốn tiền mua API như các dịch vụ Cloud."
          }
        },
        {
          "@type": "Question",
          "name": "Cơ chế Clone Overlay của Flama là gì?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Clone Overlay là kiến trúc độc quyền của Flama tách biệt nội dung bộ thẻ gốc của tác giả và lớp ghi chú riêng của bạn. Khi tác giả cập nhật sửa lỗi từ vựng, các ghi chú cá nhân và tiến độ học tập của bạn vẫn được bảo toàn nguyên vẹn 100%."
          }
        },
        {
          "@type": "Question",
          "name": "Tôi có thể học Flama trên điện thoại di động được không?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Hoàn toàn được. Flama là ứng dụng Web SPA chuẩn Progressive Web App (PWA), hiển thị mượt mà trên mọi trình duyệt điện thoại iOS (Safari) và Android (Chrome). Bạn có thể thêm Flama ra màn hình chính để học như một ứng dụng độc lập."
          }
        },
        {
          "@type": "Question",
          "name": "Flama tính mốc chuyển ngày mới (Streak) vào mấy giờ?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Flama chốt mốc chuyển ngày mới vào lúc 4:00 sáng hàng ngày (thay vì 0:00 nửa đêm). Thiết kế này giúp các học viên học khuya sau 12h đêm không bao giờ bị đứt chuỗi ngày học liên tục (Streak)."
          }
        },
        {
          "@type": "Question",
          "name": "Làm sao để nhập bộ thẻ Anki cũ (.apkg) vào Flama?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Tại Bảng điều khiển Flama, bạn bấm nút 'Nhập file' và kéo thả tệp .apkg từ máy tính vào. Flama sẽ tự động phân tích cấu trúc trường dữ liệu, thẻ học và tiến độ ôn tập để bạn tiếp tục học ngay."
          }
        },
        {
          "@type": "Question",
          "name": "Kho bộ thẻ Marketplace của Flama có những giáo trình nào?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Marketplace của Flama cung cấp đầy đủ các bộ thẻ chuẩn giáo trình Minna no Nihongo (50 bài), Soumatome (N3, N2), Mimikara Oboeru, Shinkanzen Master, và bộ thẻ 2136 chữ Hán thường dùng (Joyo Kanji) có sẵn phát âm và ví dụ minh họa."
          }
        },
        {
          "@type": "Question",
          "name": "Tôi có thể tự tạo bộ thẻ và chia sẻ cho bạn bè trên Flama được không?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Có. Bạn có thể tự tạo bộ thẻ cá nhân, tùy biến mẫu thẻ (Note Type) và bấm 'Xuất bản lên Marketplace'. Bạn bè của bạn có thể tải về học và gửi đề xuất sửa lỗi (Change Request) để cùng bạn hoàn thiện bộ thẻ."
          }
        }
      ]
    }
  ]
}
```

---

### 4.2. Đặc Tả Chi Tiết 3 Mẫu `HowTo` Sản Xuất (Production Step-by-Step Schemas)

#### Mẫu HowTo 1: Khai Thác Từ Vựng 1-Click Từ Yomitan Sang Flama
*Áp dụng cho trang*: `https://flama.vn/guide/anki-import/yomitan-mining`

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "@id": "https://flama.vn/guide/anki-import/yomitan-mining#howto",
  "name": "Cách Cài Đặt Và Khai Thác Từ Vựng 1-Click Từ Yomitan Sang Flama",
  "description": "Hướng dẫn từng bước kết nối tiện ích tra từ Yomitan trên trình duyệt với Flama Connect để tạo thẻ Flashcard siêu tốc khi đọc báo hoặc xem anime.",
  "totalTime": "PT5M",
  "tool": [
    {
      "@type": "HowToTool",
      "name": "Trình duyệt web Google Chrome, Microsoft Edge hoặc Kiwi Browser"
    },
    {
      "@type": "HowToTool",
      "name": "Tiện ích mở rộng Yomitan (Chrome Web Store)"
    },
    {
      "@type": "HowToTool",
      "name": "Tài khoản Flama (https://flama.vn)"
    }
  ],
  "step": [
    {
      "@type": "HowToStep",
      "position": 1,
      "name": "Bước 1: Lấy URL kết nối Flama Connect",
      "text": "Đăng nhập vào Flama, truy cập Cài đặt > Yomitan Tokens để sao chép đường dẫn Server URL cá nhân của bạn.",
      "url": "https://flama.vn/guide/anki-import/yomitan-mining#step-1"
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "name": "Bước 2: Cài đặt tiện ích Yomitan trên trình duyệt",
      "text": "Truy cập Chrome Web Store, tìm kiếm 'Yomitan' và bấm 'Thêm vào Chrome'.",
      "url": "https://flama.vn/guide/anki-import/yomitan-mining#step-2"
    },
    {
      "@type": "HowToStep",
      "position": 3,
      "name": "Bước 3: Cấu hình Anki Server trong Yomitan",
      "text": "Mở Settings của Yomitan, tìm mục Anki, bật 'Enable Anki integration' và dán URL Server Flama Connect đã sao chép ở Bước 1.",
      "url": "https://flama.vn/guide/anki-import/yomitan-mining#step-3"
    },
    {
      "@type": "HowToStep",
      "position": 4,
      "name": "Bước 4: Ánh xạ trường dữ liệu (Field Markers)",
      "text": "Chọn Deck muốn lưu từ và gán các Field Markers tương ứng: {marker:expression} cho từ vựng, {marker:reading} cho cách đọc, {marker:glossary} cho định nghĩa.",
      "url": "https://flama.vn/guide/anki-import/yomitan-mining#step-4"
    },
    {
      "@type": "HowToStep",
      "position": 5,
      "name": "Bước 5: Bắt đầu khai thác từ vựng 1-click",
      "text": "Giữ phím Shift và di chuột qua từ vựng tiếng Nhật trên bất kỳ trang web nào, bấm biểu tượng dấu cộng (+) màu xanh để bắn từ vào Flama.",
      "url": "https://flama.vn/guide/anki-import/yomitan-mining#step-5"
    }
  ]
}
```

#### Mẫu HowTo 2: Cài Đặt Phát Âm VoiceVox Ngoại Tuyến Miễn Phí Với Flama Audio
*Áp dụng cho trang*: `https://flama.vn/guide/audio/local-tts` và `https://flama.vn/guide/flama-audio`

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "@id": "https://flama.vn/guide/audio/local-tts#howto",
  "name": "Cách Cài Đặt Phát Âm VoiceVox Ngoại Tuyến Miễn Phí Với Flama Audio",
  "description": "Hướng dẫn tải và kích hoạt trợ lý Flama Audio Portable trên Windows để nghe giọng đọc tiếng Nhật tự nhiên chuẩn ngữ điệu Tokyo.",
  "totalTime": "PT3M",
  "tool": [
    {
      "@type": "HowToTool",
      "name": "Máy tính hệ điều hành Windows 10 hoặc Windows 11"
    },
    {
      "@type": "HowToTool",
      "name": "Tệp FlamaAudio-Portable.exe (.NET 8)"
    }
  ],
  "step": [
    {
      "@type": "HowToStep",
      "position": 1,
      "name": "Bước 1: Tải Flama Audio Portable",
      "text": "Truy cập https://flama.vn/guide/flama-audio và tải tệp FlamaAudio-Portable.exe bản mới nhất.",
      "url": "https://flama.vn/guide/audio/local-tts#step-1"
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "name": "Bước 2: Khởi chạy ứng dụng",
      "text": "Mở tệp FlamaAudio-Portable.exe. Ứng dụng sẽ tự động khởi động dịch vụ âm thanh cục bộ trên cổng 4791.",
      "url": "https://flama.vn/guide/audio/local-tts#step-2"
    },
    {
      "@type": "HowToStep",
      "position": 3,
      "name": "Bước 3: Kiểm tra kết nối trên Flama Web",
      "text": "Mở Flama trên trình duyệt, biểu tượng âm thanh sẽ chuyển sang màu xanh lá báo hiệu 'Flama Audio: Đã kết nối'.",
      "url": "https://flama.vn/guide/audio/local-tts#step-3"
    },
    {
      "@type": "HowToStep",
      "position": 4,
      "name": "Bước 4: Trải nghiệm phát âm tự nhiên",
      "text": "Khi lật thẻ trong phòng học hoặc dùng tính năng Tạo âm thanh hàng loạt, Flama sẽ tự động phát âm giọng VoiceVox chuẩn bản xứ.",
      "url": "https://flama.vn/guide/audio/local-tts#step-4"
    }
  ]
}
```

#### Mẫu HowTo 3: Chuyển Bộ Thẻ Từ Anki Sang Flama Chỉ Trong 60 Giây
*Áp dụng cho trang*: `https://flama.vn/guide/anki-import/apkg-import`

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "@id": "https://flama.vn/guide/anki-import/apkg-import#howto",
  "name": "Cách Nhập File .apkg Từ Anki Sang Flama Chỉ Trong 60 Giây",
  "description": "Hướng dẫn nhập khẩu nguyên vẹn các bộ thẻ Anki bao gồm âm thanh, hình ảnh và tiến độ ôn tập sang nền tảng web Flama.",
  "totalTime": "PT2M",
  "step": [
    {
      "@type": "HowToStep",
      "position": 1,
      "name": "Bước 1: Xuất file .apkg từ Anki Desktop",
      "text": "Mở Anki Desktop, bấm vào bánh răng cạnh bộ thẻ cần chuyển, chọn Export và xuất dưới định dạng Anki Deck Package (.apkg) kèm file media.",
      "url": "https://flama.vn/guide/anki-import/apkg-import#step-1"
    },
    {
      "@type": "HowToStep",
      "position": 2,
      "name": "Bước 2: Mở trình nhập file của Flama",
      "text": "Đăng nhập Flama, chọn mục 'Nhập file' từ thanh tác vụ nhanh tại Bảng điều khiển.",
      "url": "https://flama.vn/guide/anki-import/apkg-import#step-2"
    },
    {
      "@type": "HowToStep",
      "position": 3,
      "name": "Bước 3: Tải file lên và xác nhận ánh xạ",
      "text": "Kéo thả tệp .apkg vào khung tải lên. Hệ thống tự động nhận diện mẫu thẻ và hiển thị số lượng thẻ hợp lệ.",
      "url": "https://flama.vn/guide/anki-import/apkg-import#step-3"
    },
    {
      "@type": "HowToStep",
      "position": 4,
      "name": "Bước 4: Hoàn tất và bắt đầu học",
      "text": "Bấm 'Bắt đầu nhập'. Sau vài giây, bộ thẻ xuất hiện trên Dashboard sẵn sàng cho bạn tiếp tục phiên học.",
      "url": "https://flama.vn/guide/anki-import/apkg-import#step-4"
    }
  ]
}
```

---

### 4.3. Đặc Tả Chi Tiết `BreadcrumbList` (Cấu Trúc Điều Hướng Chuẩn 3 Cấp)

Áp dụng cho mọi bài viết chi tiết trong Cẩm nang hướng dẫn `/guide/*`:

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "@id": "https://flama.vn/guide/anki-import/yomitan-mining#breadcrumb",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Trang chủ",
      "item": "https://flama.vn"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "Cẩm nang hướng dẫn",
      "item": "https://flama.vn/guide"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "Khai thác từ vựng Yomitan 1-Click",
      "item": "https://flama.vn/guide/anki-import/yomitan-mining"
    }
  ]
}
```

---

## 5. HƯỚNG DẪN NHÚNG SCHEMA TRONG KIẾN TRÚC FLASK & REACT SPA (CMS & DEV GUIDE)

### 5.1. Cơ Chế Bơm Schema SSR Trong Flask (`app/spa.py`)
Flama vận hành trên kiến trúc React SPA với Flask backend phục vụ shell HTML tại `app/spa.py`. Để đảm bảo Googlebot và các AI bot (GPTBot, PerplexityBot) đọc được Schema JSON-LD ngay trong lượt thu thập đầu tiên (không cần đợi JavaScript render):

1. **Khối Schema Toàn Cục (Global Graph)**: Được gắn cứng trực tiếp vào thẻ `<head>` của `frontend/index.html` (hoặc template Jinja shell rendered bởi `app/spa.py`).
2. **Khối Schema Động Cho Bài Viết Guide**: Khi người dùng hoặc bot truy cập các URL `/guide/*`, route backend trong `app/spa.py` (hoặc service SEO `app/services/seo_service.py`) đối chiếu slug bài viết từ `guideData.ts` và tiêm thẻ `<script type="application/ld+json">` tương ứng vào thẻ `<head>` trước khi trả về client.

### 5.2. Khai Báo Meta Tags Trong React SPA
Trên frontend React, sử dụng component quản lý metadata (`<Helmet>` hoặc cập nhật `document.title` và thẻ `<meta>` trong hook `useDocumentTitle`) để cập nhật trạng thái khi người dùng điều hướng client-side:

```typescript
// frontend/src/shared/lib/seo.ts
export function setPageSeoMetadata(title: string, description: string, canonicalUrl: string) {
  document.title = title;
  
  // Cập nhật Meta Description
  let metaDesc = document.querySelector('meta[name="description"]');
  if (!metaDesc) {
    metaDesc = document.createElement('meta');
    metaDesc.setAttribute('name', 'description');
    document.head.appendChild(metaDesc);
  }
  metaDesc.setAttribute('content', description);

  // Cập nhật Canonical Tag
  let canonical = document.querySelector('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement('link');
    canonical.setAttribute('rel', 'canonical');
    document.head.appendChild(canonical);
  }
  canonical.setAttribute('href', canonicalUrl);
}
```

---

## 6. QUY TRÌNH KIỂM DUYỆT CHẤT LƯỢNG (QA & VALIDATION CHECKLIST)

Trước khi nghiệm thu bất kỳ trang nào, QA Auditor phải kiểm tra theo bảng sau:

| Hạng mục kiểm tra | Công cụ xác thực | Tiêu chuẩn đạt chuẩn (Pass Criteria) |
|---|---|---|
| **Cú pháp JSON-LD** | [Schema.org Validator](https://validator.schema.org/) | 0 Error, 0 Warning. Tất cả các node `@id` liên kết thành công. |
| **Kết quả nhiều định dạng** | [Google Rich Results Test](https://search.google.com/test/rich-results) | Hợp lệ cho `SoftwareApplication`, `Course`, `FAQPage`, `HowTo`, `BreadcrumbList`. |
| **Điểm số Lighthouse SEO** | Chrome DevTools Lighthouse | Điểm SEO đạt **100/100**, kiểm tra đầy đủ Viewport, Title, Meta, Alt text, Font size. |
| **Kiểm tra độ dài ký tự** | Word Counter / SEO Checker | Title: 50–60 ký tự; Meta Desc: 145–160 ký tự. |
| **Khoảng cách từ ngữ nghĩa** | Kiểm tra thủ công đoạn mở đầu | Từ "Flama" cách các thực thể con không quá 15 từ. |
| **Canonical & URL** | Curl / Chrome Network tab | Mã HTTP 200, Canonical khớp chính xác URL hiển thị, không bị chuyển hướng vòng lặp. |

---

*Tài liệu được ban hành và phê chuẩn cho toàn bộ chiến dịch SEO Flama.vn — Mọi thay đổi cấu trúc URL hoặc Schema phải được cập nhật đồng bộ vào tài liệu này.*
