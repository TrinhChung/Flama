# Flama SEO Strategic Documentation & Implementation Portal

> **Hệ thống Quản trị & Triển khai Chiến lược SEO Toàn diện cho Nền tảng Flama (https://flama.vn)**  
> **Cập nhật lần cuối**: 2026-10-20  
> **Trạng thái**: Production-Ready  
> **Mục tiêu cốt lõi**: Chiếm lĩnh Top 1 Google Search cho toàn bộ 68 từ khóa chiến lược, xác lập thực thể thương hiệu duy nhất trên Google Knowledge Graph, tối ưu hóa cho AI Search (GEO) và xây dựng hệ thống tăng trưởng hữu cơ bền vững.

---

## 1. MỤC LỤC TỔNG THỂ HỆ THỐNG TÀI LIỆU SEO (SEO DOCUMENTATION SUITE)

Hệ thống tài liệu SEO của Flama được thiết kế module hóa, phục vụ từ cấp độ hoạch định chiến lược đến quy chuẩn thực thi chi tiết cho lập trình viên và biên tập viên nội dung:

```
docs/seo/
├── README.md                             # [Bạn đang ở đây] Cổng điều hướng trung tâm
├── KEYWORD_RESEARCH_MATRIX.md           # Ma trận 68 từ khóa chiến lược (Volume, KD, Intent)
├── BRAND_ENTITY_SEO_STRATEGY.md         # Chiến lược định danh thực thể & Tam giác ngữ nghĩa
├── KEYWORD_ROLLOUT_PLAN.md              # Lộ trình triển khai 3 giai đoạn (Tuần 1–12)
├── PILLAR_CLUSTER_ARCHITECTURE.md       # Kiến trúc 5 Pillar, 33 Cluster & Sơ đồ liên kết nội bộ
├── ONPAGE_SEMANTIC_GUIDELINES.md        # Quy chuẩn On-Page, Schema JSON-LD & Wikidata
└── CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md# Lịch xuất bản 24 bài, Khung GSC KPI & 5 Playbooks
```

### Bảng Ma Trận Tra Cứu Nhanh (Navigation Hub)

| STT | Tài liệu | Nội dung trọng tâm | Nhóm đối tượng phục vụ | Trạng thái |
|---|---|---|---|---|
| **01** | [`KEYWORD_RESEARCH_MATRIX.md`](./KEYWORD_RESEARCH_MATRIX.md) | Phân tích 68 từ khóa theo 5 cụm: Brand, SRS/Anki, Yomitan, VoiceVox/TTS, JLPT Marketplace. Phân loại Volume, KD, Search Intent. | SEO Lead, Marketing, Product Owner | Hoàn thành |
| **02** | [`BRAND_ENTITY_SEO_STRATEGY.md`](./BRAND_ENTITY_SEO_STRATEGY.md) | Chiến lược định danh thực thể số `Flama (flama.vn)`, tách biệt khỏi đồ gia dụng Bồ Đào Nha và phông chữ; Mô hình tam giác ngữ nghĩa và liên kết `sameAs`. | SEO Lead, PR, Social Media | Hoàn thành |
| **03** | [`KEYWORD_ROLLOUT_PLAN.md`](./KEYWORD_ROLLOUT_PLAN.md) | Kế hoạch triển khai 3 giai đoạn: GĐ 1 Quick-Wins (Tuần 1-4), GĐ 2 Authority (Tuần 5-8), GĐ 3 Commercial Scaling (Tuần 9-12). | Content Manager, Project Manager | Hoàn thành |
| **04** | [`PILLAR_CLUSTER_ARCHITECTURE.md`](./PILLAR_CLUSTER_ARCHITECTURE.md) | Thiết kế 5 trang Pillar trung tâm và 33 bài viết vệ tinh (Satellite URLs); Quy tắc liên kết nội bộ 2 chiều và tỷ lệ vàng Anchor Text. | Content Creator, Web Architect | Hoàn thành |
| **05** | [`ONPAGE_SEMANTIC_GUIDELINES.md`](./ONPAGE_SEMANTIC_GUIDELINES.md) | Checklist On-Page (Title, Meta, URL, H1-H3), Quy tắc gần ngữ cảnh (≤ 15 từ), Wikidata Q-IDs, và các khối Schema.org JSON-LD (@graph). | Web Developer, QA Auditor, Copywriter | Hoàn thành |
| **06** | [`CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md`](./CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md) | Bảng chuyển dịch chống thuật ngữ hàn lâm (Anti-Jargon), Lịch xuất bản 24 bài viết chi tiết, Khung đo lường GSC 30-60-90 ngày và 5 Playbooks xử lý sự cố. | Content Creator, SEO Specialist | Hoàn thành |

---

## 2. TỔNG QUAN CHIẾN LƯỢC 68 TỪ KHÓA & TAM GIÁC NGỮ NGHĨA FLAMA

### 2.1. Phân Bổ 68 Từ Khóa Theo 5 Cụm Chủ Đề
Toàn bộ chiến dịch SEO Flama bao phủ 68 từ khóa chiến lược phản ánh đúng hành vi tìm kiếm tự nhiên của người học tiếng Nhật:
1. **Brand Cluster (12 từ khóa)**: Xác lập vị thế độc tôn của `flama`, `flama vn`, `flama tiếng nhật`, `app flama`, `flama flashcard`, bảo vệ thương hiệu trên SERP Top 1.
2. **Spaced Repetition & Anki Alternative (15 từ khóa)**: Giải quyết nhu cầu "học từ vựng nhớ lâu", "app thay thế Anki trên Web", "cách nhớ kanji nhanh".
3. **Yomitan & 1-Click Immersion Mining (14 từ khóa)**: Đáp ứng xu hướng khai thác từ vựng khi xem Anime, đọc báo tiếng Nhật với tiện ích Yomitan và Flama Connect.
4. **Local TTS VoiceVox & Kokoro (12 từ khóa)**: Giải quyết nỗi đau phát âm chuẩn bản xứ Tokyo ngoại tuyến miễn phí, tạo audio hàng loạt cho flashcard.
5. **Marketplace & Lộ Trình JLPT N5–N1 (15 từ khóa)**: Phục vụ nhu cầu tải trọn bộ flashcard Minna no Nihongo 50 bài, Soumatome, Joyo Kanji với cơ chế độc quyền Clone Overlay.

### 2.2. Mô Hình Tam Giác Ngữ Nghĩa Flama (The Flama Semantic Triangle)

```
                           [ THỰC THỂ ĐỈNH: FLAMA ]
                            (Canonical: flama.vn)
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

- **Quy tắc neo ngữ cảnh**: Trong 100 chữ đầu tiên của bài viết, từ khóa "Flama" bắt buộc phải xuất hiện trong khoảng cách không quá 15 từ so với ít nhất 2 thực thể con thuộc tam giác ngữ nghĩa.
- **Wikidata Mapping**:
  - `Flama` isA `Q166142` (Web application) & `Q340169` (Educational software)
  - `teaches`: `Q5287` (Japanese language), `Q82851` (Kanji)
  - `preparesFor`: `Q842398` (JLPT)
  - `usesTechnique`: `Q2300067` (Spaced repetition)
  - `alternativeTo`: `Q557098` (Anki)
  - `integratesWith`: `Q107604` (Speech synthesis - VoiceVox / Kokoro)

---

## 3. LỘ TRÌNH TRIỂN KHAI 3 GIAI ĐOẠN & MỤC TIÊU HIỆU SUẤT GSC

```
[ GIAI ĐOẠN 1: TUẦN 1 - 4 ] ──► [ GIAI ĐOẠN 2: TUẦN 5 - 8 ] ──► [ GIAI ĐOẠN 3: TUẦN 9 - 12 ]
  Quick-Wins & Brand Defense      Authority Building & SRS        High-Volume Commercial Scaling
  - 100% Brand keywords Top 1     - 15 Feature keywords Top 3-10  - 60%+ tổng từ khóa Top 10
  - Yomitan & TTS Niche Top 1-3   - Top Ứng dụng thay thế Anki    - Lộ trình JLPT N5-N1 Decks Top 3-10
  - Mục tiêu: 1,500 - 2,500 click - Mục tiêu: 5,000 - 8,000 click - Mục tiêu: 15,000 - 25,000 click
```

### Bảng Mục Tiêu Đo Lường 30 - 60 - 90 Ngày

| Chỉ số Đo Lường | Mốc 30 Ngày (Sau Tuần 4) | Mốc 60 Ngày (Sau Tuần 8) | Mốc 90 Ngày (Sau Tuần 12) |
|---|---|---|---|
| **Từ khóa Thương hiệu Top 1** | **100% (12/12 từ khóa)** | Duy trì Top 1 ổn định | Top 1 kèm Sitelinks & Search Box |
| **Từ khóa Ngách KD < 30** | 8 – 10 từ khóa Top 1–5 | 12 – 14 từ khóa Top 1–3 | 14/14 từ khóa Top 1–3 vững chắc |
| **Từ khóa Cốt lõi SRS & Anki** | Top 11–20 (Trang 2) | 8 – 10 từ khóa Top 3–10 | 12 – 15 từ khóa Top 1–5 |
| **Từ khóa Bộ thẻ JLPT** | Lập chỉ mục thành công, Top 30–50 | 5 – 7 từ khóa Top 10–20 | 10 – 12 từ khóa Top 3–10 |
| **Tổng Lượt Hiển Thị (Impressions)** | 15,000 – 25,000 lượt | 45,000 – 65,000 lượt | 120,000 – 160,000+ lượt |
| **Tổng Lượt Nhấp Chuột (Clicks)** | 1,500 – 2,500 clicks | 5,000 – 8,000 clicks | 15,000 – 25,000+ clicks |
| **Học Viên Đăng Ký Mới Từ Google** | > 200 học viên | > 800 học viên | > 2,000 học viên / tháng |

---

## 4. QUY CHUẨN KỸ THUẬT & MÁY ĐỌC (GEO & TECHNICAL SEO)

Flama áp dụng đầy đủ các tiêu chuẩn tìm kiếm trí tuệ nhân tạo (Generative Engine Optimization):
- **Chuẩn máy đọc `llms.txt`**: Cung cấp tệp tóm tắt cấu trúc ứng dụng và tài liệu tính năng tại root cho các AI Agents (Perplexity, ChatGPT, Claude).
- **Cấu hình `robots.txt`**: Mở quyền truy cập tối ưu cho các crawler AI hợp lệ (`GPTBot`, `PerplexityBot`, `ClaudeBot`, `Google-Extended`).
- **Sơ đồ dữ liệu có cấu trúc Schema.org JSON-LD**:
  - Gắn khối `@graph` hợp nhất: `Organization`, `WebSite`, `SoftwareApplication`, `Course`, `FAQPage`.
  - Gắn thẻ `HowTo` cho 3 luồng hướng dẫn cốt lõi: Yomitan Mining, VoiceVox Local TTS, và Chuyển đổi Anki .apkg.
  - Gắn `BreadcrumbList` 3 cấp độ cho toàn bộ các bài viết hướng dẫn `/guide/*`.

---

## 5. BẢO TRÌ & NGUYÊN TẮC VẬN HÀNH (OPERATIONAL GOVERNANCE)

1. **Nguyên tắc "Học viên là trung tâm" (Learner-First)**: Không đưa các thuật ngữ kỹ thuật nội bộ (SM-2, FSRS, database schema) vào tiêu đề hoặc làm thông điệp chính. Luôn chuyển hóa thành lợi ích trực tiếp cho người học tiếng Nhật.
2. **Quy tắc Kiểm duyệt On-Page 100%**: Mọi bài viết trước khi xuất bản phải tuân thủ nghiêm ngặt checklist trong [`ONPAGE_SEMANTIC_GUIDELINES.md`](./ONPAGE_SEMANTIC_GUIDELINES.md) (Title 50–60 ký tự, Meta 145–160 ký tự, đúng 1 thẻ H1, hình ảnh WebP có Alt text).
3. **Theo dõi GSC định kỳ thứ Hai hàng tuần**: Đánh giá chỉ số Click, Impression, CTR và kích hoạt các Playbook xử lý sự cố trong [`CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md`](./CONTENT_CALENDAR_AND_KPI_FRAMEWORK.md) ngay khi phát hiện lỗi lập chỉ mục hoặc chững thứ hạng.

---

*Cổng tài liệu SEO Flama.vn — Nền tảng tri thức phục vụ tăng trưởng bền vững.*
