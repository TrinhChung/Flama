# Lịch Xuất Bản Nội Dung 12 Tuần & Khung Đo Lường Hiệu Quả GSC KPI (Content Calendar & KPI Tracking Framework) — Flama.vn

> **Phiên bản**: 2.0 (Production-Ready)  
> **Cập nhật lần cuối**: 2026-10-20  
> **Phạm vi áp dụng**: Kế hoạch vận hành nội dung 12 tuần và cơ chế theo dõi Google Search Console cho toàn bộ 68 từ khóa chiến lược của Flama.vn  
> **Tài liệu tham chiếu**:  
> - `docs/seo/KEYWORD_RESEARCH_MATRIX.md` (Ma trận 68 từ khóa phân loại theo 5 cụm chủ đề, Volume, KD và Intent)  
> - `docs/seo/BRAND_ENTITY_SEO_STRATEGY.md` (Chiến lược định danh thực thể & Tam giác ngữ nghĩa Flama)  
> - `docs/seo/PILLAR_CLUSTER_ARCHITECTURE.md` (Kiến trúc phân cấp 5 Pillar & 33 Cluster)  
> - `docs/seo/ONPAGE_SEMANTIC_GUIDELINES.md` (Quy chuẩn On-Page & Schema JSON-LD)  

---

## 1. NGUYÊN TẮC BIÊN SOẠN HƯỚNG VỀ HỌC VIÊN & QUY CHUẨN LOẠI BỎ THUẬT NGỮ HÀN LÂM (ANTI-JARGON PROTOCOL)

### 1.1. Thực Trạng Tâm Lý & Hành Vi Tìm Kiếm Thực Tế Của Người Học Tiếng Nhật
Cộng đồng người học tiếng Nhật tại Việt Nam (hơn 800,000 người từ học sinh, sinh viên, người ôn thi JLPT, kỹ sư IT đến du học sinh và tu nghiệp sinh) có đặc thù tìm kiếm rất rõ ràng:
1. **Tìm kiếm xuất phát từ "Nỗi đau" (Pain-Point-Driven Searches)**: Người học không tìm kiếm các khái niệm khoa học hay kiến trúc phần mềm trừu tượng; họ tìm kiếm giải pháp cứu nguy cho các khó khăn thường ngày:
   - *"Học trước quên sau, từ vựng hôm nay học ngày mai quên sạch."*
   - *"Chữ Hán (Kanji) quá phức tạp, viết đi viết lại cả trăm lần vẫn không nhớ nét."*
   - *"Phần mềm Anki quá phức tạp, giao diện cổ lỗ sĩ, cài add-on liên tục bị lỗi, dùng 3 ngày là bỏ cuộc."*
   - *"Muốn nghe phát âm bản xứ tự nhiên khi học từ chứ không muốn nghe giọng chị Google Dịch khô cứng."*
2. **Ngôn ngữ tìm kiếm thực dụng, đời thường**: Người học gõ vào thanh tìm kiếm các cụm từ rất trực tiếp:  
   *"học từ vựng tiếng nhật nhớ lâu"*, *"cách nhớ kanji nhanh"*, *"app thay thế anki"*, *"tải bộ thẻ minna 50 bài"*, *"cách tra từ khi xem anime"*.
3. **Cảnh báo về sai lầm "Hàn Lâm Hóa Kỹ Thuật"**: Khi các kỹ sư hoặc chuyên gia công nghệ viết bài SEO, họ thường vô thức đưa các thuật ngữ nội bộ (*SM-2*, *FSRS algorithm*, *MySQL JSON array fields*, *optimistic concurrency lock*, *BFS depth-limit tree traversal*, *WebSocket loopback proxy 4790*) vào tiêu đề và nội dung bài viết. Hậu quả:
   - **Tỷ lệ thoát trang (Bounce Rate) tăng vọt**: Người học cảm thấy hoa mắt, nghĩ rằng công cụ quá khó dùng và bấm nút thoát trang trong vòng 5 giây đầu.
   - **Lệch pha Search Intent**: Google đánh giá bài viết không phục vụ người học phổ thông và hạ thứ hạng trang web.

---

### 1.2. Bảng Quy Chuẩn Chuyển Dịch "Thuật Ngữ Kỹ Thuật Sang Ngôn Ngữ Người Học" (Anti-Jargon Translation Matrix)

Để đảm bảo 100% nội dung SEO chạm đúng cảm xúc và giữ chân học viên, toàn bộ đội ngũ biên soạn nội dung bắt buộc phải áp dụng bảng chuyển dịch sau:

| Thuật ngữ Kỹ thuật / Nội bộ (TUYỆT ĐỐI KHÔNG dùng làm trọng tâm) | Ngôn ngữ Tự nhiên của Người học (BẮT BUỘC ƯU TIÊN) | Lợi ích Cốt lõi Chuyển giao (Value Proposition) | Ví dụ Tiêu đề & Thông điệp Thay thế |
|---|---|---|---|
| **Thuật toán Spaced Repetition (SM-2, FSRS, Stability, Retrievability)** | **Phương pháp lặp lại đúng thời điểm vàng / Ôn tập ngắt quãng thông minh** | Không cần học nhồi nhét; hệ thống tự động tính ngày nhắc ôn từ vựng ngay trước thời điểm sắp quên, tiết kiệm 80% thời gian. | *Thay vì*: "Tối ưu thuật toán FSRS trên Flama"<br>➜ *Dùng*: **"Cách học 50 từ vựng tiếng Nhật mỗi ngày mà không bao giờ quên nhờ phương pháp lặp lại ngắt quãng"** |
| **Kiến trúc Clone Overlay / Overlay Delta / Inheritance** | **Tải bộ thẻ cộng đồng, thoải mái ghi chú riêng không sợ mất khi tác giả cập nhật** | Tải bộ thẻ của giáo viên về, thêm ví dụ của bản thân; khi tác giả sửa lỗi, ghi chú cá nhân và tiến độ học vẫn giữ nguyên 100%. | *Thay vì*: "Mô hình Clone Overlay độc quyền trong DB Flama"<br>➜ *Dùng*: **"Tải bộ thẻ tiếng Nhật về học: Tự do thêm ghi chú cá nhân mà không lo bị ghi đè khi cập nhật"** |
| **Change Request 3-Way Diff / Conflict Resolution** | **Đóng góp sửa lỗi sai chính tả / Báo lỗi bộ thẻ cho tác giả** | Phát hiện từ sai hoặc nghĩa chưa chuẩn, bấm 1 nút báo lỗi cho tác giả để cả cộng đồng cùng được học bản chuẩn xác nhất. | *Thay vì*: "Quy trình xử lý Change Request 3 chiều trên Marketplace"<br>➜ *Dùng*: **"Cùng nhau xây dựng bộ thẻ chuẩn: Cách báo lỗi sai chính tả chỉ bằng 1 cú nhấp chuột"** |
| **Flama Connect Bridge / WebSocket AnkiConnect / Loopback 4790** | **Tra từ 1-click / Bắn từ vựng vào bộ thẻ ngay khi xem phim, đọc báo** | Đọc báo tiếng Nhật hay xem phim Anime, rê chuột tra từ và bấm 1 nút là từ vựng, audio, câu ví dụ tự bay vào bộ thẻ học. | *Thay vì*: "Cấu hình Flama Connect Bridge cổng 4790 tương thích Yomitan"<br>➜ *Dùng*: **"Bí quyết xem Anime có phụ đề tiếng Nhật: Rê chuột tra từ và lưu flashcard siêu tốc trong 0.1 giây"** |
| **Local TTS / VoiceVox / Kokoro ONNX Runtime (.NET 8 Companion)** | **Giọng đọc bản xứ Tokyo tự nhiên / Phát âm Anime sống động miễn phí** | Không còn nghe giọng đọc 'chị Google' vô hồn; phát âm chuẩn ngữ điệu Tokyo giúp luyện phản xạ nghe nói như người Nhật. | *Thay vì*: "Triển khai VoiceVox ONNX và Kokoro TTS trên nền tảng .NET 8"<br>➜ *Dùng*: **"Cách tạo giọng đọc phát âm tiếng Nhật chuẩn Tokyo cực hay cho flashcard mà không tốn 1 xu"** |
| **Database Schema / JSON Array Field Values / Migration** | **Mẫu thẻ flashcard đầy đủ chữ Hán, Furigana, âm Hán Việt và âm thanh** | Thẻ học đẹp mắt, trực quan, hỗ trợ đầy đủ các trường thông tin quan trọng cho kỳ thi JLPT. | *Thay vì*: "Cấu trúc Schema hỗ trợ Native Array và Rich Text"<br>➜ *Dùng*: **"Mẫu flashcard tiếng Nhật chuẩn: Vừa có Kanji, cách đọc Furigana, âm Hán Việt và giọng đọc chuẩn"** |

---

## 2. PHÂN TÍCH CHUYÊN SÂU 5 NHÓM TỪ KHÓA HÀNH VI NGƯỜI HỌC THỰC TẾ

```
                             [ HÀNH VI TÌM KIẾM CỦA NGƯỜI HỌC ]
                                             │
          ┌───────────────────┬──────────────┴───────┬───────────────────┐
          ▼                   ▼                      ▼                   ▼
 1. Từ Vựng & Trí Nhớ    2. Thay Thế Anki      3. Bộ Thẻ JLPT      4. Immersion Phim      5. Phát Âm & Audio
 - Nỗi đau: Mau quên     - Nỗi đau: Khó dùng   - Nhu cầu: Tải học  - Nhu cầu: Đọc truyện   - Nỗi đau: Giọng đơ
 - Tìm: Mẹo nhớ lâu      - Tìm: Web mượt mà     ngay cho kịp thi     xem anime tra 1-click  - Tìm: Giọng Tokyo
```

### 2.1. Nhóm 1: Từ Vựng & Ghi Nhớ ("học từ vựng tiếng nhật nhớ lâu", "app học từ vựng tiếng nhật", "cách nhớ kanji nhanh", "phần mềm flashcard tiếng nhật")
- **Tâm lý & Nỗi đau**: Khi bắt đầu học tiếng Nhật, người học bị choáng ngợp bởi hàng nghìn chữ Hán và kho từ vựng khổng lồ. Cách học truyền thống (chép tay vào sổ, học vẹt theo danh sách) khiến từ vựng trôi sạch sau 1–2 tuần. Họ tìm kiếm một phương pháp khoa học đã được chứng minh hiệu quả.
- **Search Intent**:
  - `học từ vựng tiếng nhật nhớ lâu`: **Informational** (Cần phương pháp, lộ trình, bằng chứng khoa học về đường cong quên lãng Ebbinghaus).
  - `app học từ vựng tiếng nhật`: **Commercial / Transactional** (So sánh giữa Quizlet, Mazii, Anki, HeyJapan và Flama để chọn app chính).
  - `cách nhớ kanji nhanh`: **Informational** (Phương pháp học qua bộ thủ, câu chuyện liên tưởng kết hợp flashcard lặp lại ngắt quãng).
  - `phần mềm flashcard tiếng nhật`: **Transactional** (Muốn tìm công cụ hỗ trợ flashcard 2 mặt chuyên biệt cho tiếng Nhật có Furigana).
- **Chiến lược chuyển đổi của Flama**: Khẳng định "Học vẹt chép tay đã lỗi thời. Bí quyết nhớ vĩnh viễn là ôn tập vào thời điểm sắp quên." Định vị Flama là ứng dụng Flashcard tiếng Nhật thông minh nhất với giao diện Web hiện đại, tự động xếp lịch ôn tập hàng ngày theo 4 nút đánh giá (Lại, Khó, Tốt, Dễ).

### 2.2. Nhóm 2: Thay Thế & Tối Ưu Anki ("app thay thế anki", "cách dùng anki tiếng nhật", "web flashcard giống anki miễn phí")
- **Tâm lý & Nỗi đau**: Anki là tiêu chuẩn vàng thế giới về Spaced Repetition, nhưng rào cản quá lớn tại Việt Nam: giao diện phức tạp, cài add-on dễ xung đột, đồng bộ AnkiWeb hay lỗi, và app AnkiMobile trên iOS có giá lên đến 25 USD (~600.000 VNĐ). Người học khao khát một giải pháp có sức mạnh như Anki nhưng chạy mượt mà trên Web, miễn phí, giao diện đẹp mắt, mở điện thoại hay máy tính lên là học được ngay.
- **Search Intent**:
  - `app thay thế anki`: **Commercial Investigation / Transactional** (Tìm lựa chọn thay thế tốt hơn).
  - `cách dùng anki tiếng nhật`: **Informational** (Gặp khó khăn khi sử dụng Anki, tìm bài hướng dẫn gỡ rối).
  - `web flashcard giống anki miễn phí`: **Transactional** (Muốn học trên trình duyệt không cần cài đặt phần mềm).
- **Chiến lược chuyển đổi của Flama**: Định vị Flama là "Anki thế hệ mới trên Web — Đầy đủ sức mạnh lặp lại ngắt quãng, nhập nguyên vẹn file `.apkg`, đồng bộ đám mây tức thì và hoàn toàn miễn phí trên mọi thiết bị." Nhấn mạnh tính năng nhập khẩu file Anki cũ chỉ trong 60 giây mà không mất tiến độ ôn tập.

### 2.3. Nhóm 3: Luyện Thi JLPT & Bộ Thẻ Sẵn Có ("tải bộ thẻ tiếng nhật n5 n4 n3", "từ vựng minna flashcard", "bộ thẻ kanji soumatome n2")
- **Tâm lý & Nỗi đau**: Kỳ thi năng lực tiếng Nhật (JLPT) diễn ra vào tháng 7 và tháng 12 hàng năm. Áp lực thời gian khiến người học không thể tự ngồi tạo hàng nghìn thẻ flashcard. Nhu cầu cấp thiết: cần tải ngay trọn bộ từ vựng chuẩn theo giáo trình Minna no Nihongo, Mimikara Oboeru, Soumatome hay Shinkanzen Master để bắt đầu ôn thi ngay lập tức.
- **Search Intent**:
  - `tải bộ thẻ tiếng nhật n5 n4 n3`: **Transactional** (Tìm link tải học liệu sẵn có).
  - `từ vựng minna flashcard`: **Transactional / Commercial** (Học theo giáo trình Minna no Nihongo phổ biến nhất).
  - `bộ thẻ kanji soumatome n2`: **Transactional** (Luyện thi cấp độ trung - cao cấp phục vụ đi làm, du học).
- **Chiến lược chuyển đổi của Flama**: Xây dựng Landing Page chuyên biệt cho từng bộ thẻ trên Kho Marketplace Flama.vn với nút "Thêm vào thư viện học ngay (1-Click)". Nêu bật ưu thế độc quyền Clone Overlay: tải bộ thẻ về học, tự do ghi chú thêm ví dụ của mình; khi tác giả cập nhật bản mới, ghi chú riêng và tiến độ học không bao giờ bị mất.

### 2.4. Nhóm 4: Khai Thác Từ Khi Xem Phim/Đọc Truyện ("cách tra từ khi xem anime", "cài yomitan tiếng nhật", "tiện ích tra từ trên youtube")
- **Tâm lý & Nỗi đau**: Người học theo phương pháp Đắm Chìm (Immersion Learning) gặp khó khăn khi xem Anime trên Netflix, xem video trên YouTube hay đọc Manga: gặp từ mới phải tạm dừng video, mở từ điển gõ tay tra từ, rồi copy paste vào flashcard. Quá trình này làm đứt gãy mạch cảm xúc xem phim. Họ muốn rê chuột vào phụ đề để tra nghĩa tức thì và bấm 1 phím tắt là tự động tạo thẻ flashcard có sẵn âm thanh và câu thoại trong phim.
- **Search Intent**:
  - `cách tra từ khi xem anime`: **Informational** (Tìm phương pháp học tiếng Nhật qua phim).
  - `cài yomitan tiếng nhật`: **Informational / Transactional** (Hướng dẫn cài tiện ích và từ điển).
  - `tiện ích tra từ trên youtube`: **Informational / Commercial** (Tìm công cụ hỗ trợ phụ đề song ngữ).
- **Chiến lược chuyển đổi của Flama**: Giới thiệu Flama Connect — cầu nối giúp Yomitan trên trình duyệt Chrome/Edge/Kiwi Browser bắn thẳng từ vựng sang Flama Web mà không cần cài Anki Desktop hay add-on AnkiConnect rườm rà. Cung cấp cẩm nang 55 Field Markers và bài hướng dẫn từng bước kết nối Yomitan với Flama.

### 2.5. Nhóm 5: Ngữ Điệu & Phát Âm Chuẩn Bản Xứ ("phát âm tiếng nhật chuẩn giọng tokyo", "cách tạo audio tiếng nhật tự nhiên")
- **Tâm lý & Nỗi đau**: Tiếng Nhật có trọng âm ngữ điệu (Pitch Accent). Người học sợ nói ngọng hoặc phát âm thô cứng như Google Dịch. Khi tạo flashcard, người học muốn có file âm thanh phát âm chuẩn bản xứ, nhưng Google TTS thì phát âm vô cảm, còn Cloud TTS cao cấp (OpenAI, ElevenLabs) thì chi phí API quá đắt đỏ nếu tạo âm thanh cho hàng ngàn thẻ.
- **Search Intent**:
  - `phát âm tiếng nhật chuẩn giọng tokyo`: **Informational** (Tìm hiểu về Pitch Accent và cách luyện phát âm chuẩn).
  - `cách tạo audio tiếng nhật tự nhiên`: **Informational / Transactional** (Tìm phần mềm tạo âm thanh hàng loạt cho flashcard).
- **Chiến lược chuyển đổi của Flama**: Giới thiệu ứng dụng Flama Audio Desktop: Tích hợp công nghệ VoiceVox và Kokoro TTS giọng bản xứ Tokyo sống động như nhân vật Anime, chạy ngoại tuyến trên máy tính, tạo âm thanh hàng loạt cho cả bộ thẻ hoàn toàn miễn phí.

---

## 3. LỊCH XUẤT BẢN NỘI DUNG CHI TIẾT 12 TUẦN (12-WEEK CONTENT CALENDAR)

Kế hoạch xuất bản bao gồm **24 bài viết tiêu chuẩn** (2 bài/tuần), phân bổ đều đặn theo 3 giai đoạn chiến lược, bảo đảm bao phủ trọn vẹn **100% (68/68 từ khóa chiến lược)**.

```
[ GIAI ĐOẠN 1: TUẦN 1 - 4 ] ──► [ GIAI ĐOẠN 2: TUẦN 5 - 8 ] ──► [ GIAI ĐOẠN 3: TUẦN 9 - 12 ]
  Quick-Wins & Brand Defense      Authority Building & SRS        High-Volume Commercial Scaling
  (Brand, Yomitan, TTS - KD <30)  (Spaced Repetition, Anki - KD 30-50) (Kho JLPT N5-N1 Decks - KD >50)
```

### 3.1. Bảng Kế Hoạch Xuất Bản 24 Bài Viết (Tuần 1 đến Tuần 12)

| Tuần | Bài | Giai đoạn & Chủ đề | Search Intent | Tiêu Đề Bài Viết Chuẩn SEO (Target Title) | Từ Khóa Chính (Primary) | Từ Khóa Phụ & Ngữ Cảnh (Secondary / LSI) | Độ Dài Đề Xuất | Trang Đích (Target URL) & CTA |
|---|---|---|---|---|---|---|---|---|
| **W1** | **#01** | **GĐ 1: Brand Core** | Nav / Info | **Flama Là Gì? Nền Tảng Học Tiếng Nhật & SRS Flashcard Thông Minh Thế Hệ Mới** | `flama`, `flama vn` | `flama tiếng nhật`, `học tiếng nhật flama`, `app flama`, `flama web` | 2,800 – 3,200 từ (Pillar) | `https://flama.vn`<br>*CTA: Bắt đầu học miễn phí* |
| **W1** | **#02** | GĐ 1: Fast Onboarding | Transactional | **Hướng Dẫn 3 Phút Tạo Tài Khoản & Bắt Đầu Học Thẻ Flashcard Đầu Tiên Trên Flama** | `flama flashcard` | `quản lý bộ thẻ flashcard`, `app học từ vựng tiếng nhật` | 1,500 – 1,800 từ | `https://flama.vn/guide/getting-started/getting-started`<br>*CTA: Tạo bộ thẻ đầu tiên* |
| **W2** | **#03** | **GĐ 1: Yomitan Setup** | Info / Trans | **Hướng Dẫn Cài Đặt Tiện Ích Yomitan Tiếng Nhật & Khai Thác Từ Vựng 1-Click Siêu Tốc** | `yomitan tiếng nhật`, `cách dùng yomitan` | `mining từ vựng yomitan`, `cài từ điển cho yomitan`, `yomichan sang yomitan` | 2,800 – 3,200 từ (Pillar) | `https://flama.vn/guide/anki-import/yomitan-mining`<br>*CTA: Kết nối Yomitan với Flama* |
| **W2** | **#04** | GĐ 1: Yomitan Markers | Informational | **Bảng Tra Cứu Toàn Bộ 55 Field Markers Yomitan & Cách Tùy Biến Thẻ Học Chuẩn Đẹp** | `field markers yomitan` | `pitch accent yomitan flashcard`, `tạo card anki 1 click` | 2,000 – 2,500 từ | `https://flama.vn/guide/anki-import/yomitan-markers`<br>*CTA: Xem mẫu thẻ tối ưu* |
| **W3** | **#05** | **GĐ 1: VoiceVox Audio** | Info / Trans | **Phát Âm Tiếng Nhật Chuẩn Giọng Tokyo: Hướng Dẫn Cài Đặt VOICEVOX Miễn Phí** | `phát âm tiếng nhật voicevox`, `voicevox tiếng nhật miễn phí` | `tts tiếng nhật chuẩn ngữ điệu`, `phần mềm đọc từ vựng tiếng nhật offline` | 2,500 – 3,000 từ (Pillar) | `https://flama.vn/guide/audio/local-tts`<br>*CTA: Tải Flama Audio miễn phí* |
| **W3** | **#06** | GĐ 1: Desktop Companion | Transactional | **Hướng Dẫn Sử Dụng Flama Audio Desktop: Tự Động Tạo Âm Thanh Hàng Loạt Cho Flashcard** | `tạo âm thanh flashcard tiếng nhật`, `flama audio` | `tải flama audio portable`, `audio flashcard tiếng nhật` | 1,800 – 2,200 từ | `https://flama.vn/guide/flama-audio`<br>*CTA: Tải bản Portable .exe* |
| **W4** | **#07** | **GĐ 1: Anime Immersion** | Informational | **Cách Tra Từ & Lưu Flashcard Khi Xem Anime, Phim Nhật Trên Trình Duyệt Bằng Flama Connect** | `khai thác từ vựng tiếng nhật khi xem anime` | `flama connect`, `tiện ích yomitan đọc báo tiếng nhật`, `yomitan kết nối flama` | 2,200 – 2,500 từ | `https://flama.vn/guide/anki-import/yomitan-mining`<br>*CTA: Trải nghiệm Flama Connect* |
| **W4** | **#08** | GĐ 1: Mobile Immersion | Info / Trans | **Hướng Dẫn Dùng Yomitan Bắn Flashcard Sang Flama Trực Tiếp Trên Điện Thoại Android** | `yomitan trên điện thoại android` | `yomitan anki bridge`, `lỗi yomitan could not connect` | 1,800 – 2,000 từ | `https://flama.vn/guide/troubleshooting/yomitan`<br>*CTA: Cài đặt trên Kiwi Browser* |
| **W5** | **#09** | **GĐ 2: Spaced Repetition** | Informational | **Phương Pháp Học Từ Vựng Bằng Spaced Repetition (SRS): Bí Quyết Nhớ Lâu 2000 Từ Không Quên** | `học từ vựng srs`, `spaced repetition tiếng nhật` | `cách học từ vựng nhớ lâu bằng srs`, `phần mềm lặp lại ngắt quãng`, `flama srs` | 3,000 – 3,500 từ (Core Pillar) | `https://flama.vn/guide/study/spaced-repetition`<br>*CTA: Học bài đầu tiên* |
| **W5** | **#10** | GĐ 2: Anki Migration | Trans / Comm | **Cách Chuyển Bộ Thẻ Từ Anki Sang Flama Chỉ Trong 1 Phút Bằng File .APKG** | `chuyển anki sang flama`, `tải file anki tiếng nhật` | `đồng bộ anki không cần ankiweb`, `web học từ vựng lặp lại ngắt quãng` | 2,000 – 2,400 từ | `https://flama.vn/guide/anki-import/apkg-import`<br>*CTA: Nhập file .apkg ngay* |
| **W6** | **#11** | **GĐ 2: Anki Comparison** | Comm / Trans | **Top Ứng Dụng Thay Thế Anki Học Tiếng Nhật Tốt Nhất 2026: Tại Sao Nên Chọn Flama?** | `thay thế anki học tiếng nhật`, `app học từ vựng như anki` | `phần mềm flashcard tiếng nhật tốt nhất`, `flashcard tiếng nhật srs` | 2,800 – 3,200 từ (Comparison) | `https://flama.vn/so-sanh/flama-vs-anki`<br>*CTA: Dùng thử Flama Web* |
| **W6** | **#12** | GĐ 2: Beginner Workflow | Informational | **Hướng Dẫn Học Flashcard Tiếng Nhật Cho Người Mới Bắt Đầu Từ Con Số 0** | `anki tiếng nhật cho người mới` | `cách nhớ kanji nhanh`, `học từ vựng tiếng nhật nhớ lâu` | 2,200 – 2,600 từ | `https://flama.vn/guide/getting-started/getting-started`<br>*CTA: Bắt đầu lộ trình sơ cấp* |
| **W7** | **#13** | **GĐ 2: 4-Grade Flow** | Informational | **Cách Đánh Giá 4 Mức Độ Lại, Khó, Tốt, Dễ Để Ghi Nhớ Từ Vựng Vĩnh Viễn** | `cách học từ vựng nhớ lâu bằng srs` | `thuật toán fsrs anki`, `thẻ đục lỗ cloze deletion tiếng nhật` | 2,000 – 2,500 từ | `https://flama.vn/guide/study/flashcard-flow`<br>*CTA: Thử thuật toán Flama* |
| **W7** | **#14** | GĐ 2: Cloze Deletion | Info / Trans | **Cách Tạo Thẻ Đục Lỗ (Cloze Deletion) Ôn Luyện Ngữ Pháp Tiếng Nhật Nhớ Sâu** | `thẻ đục lỗ cloze deletion tiếng nhật` | `quản lý bộ thẻ flashcard`, `flama flashcard` | 1,800 – 2,200 từ | `https://flama.vn/guide/note-types/cloze-deletion`<br>*CTA: Tạo thẻ đục lỗ đầu tiên* |
| **W8** | **#15** | **GĐ 2: Kokoro AI Voice** | Info / Trans | **Kokoro TTS Tiếng Nhật: Mô Hình Giọng Đọc AI Nhẹ, Chuẩn Ngữ Điệu Tự Nhiên Nhất 2026** | `kokoro tts tiếng nhật`, `luyện nghe tiếng nhật tts` | `tích hợp voicevox vào flashcard`, `khóa api cloud tts openai elevenlabs` | 2,200 – 2,600 từ | `https://flama.vn/guide/audio/local-tts`<br>*CTA: Cấu hình Kokoro TTS* |
| **W8** | **#16** | GĐ 2: Audio Troubleshoot | Informational | **Khắc Phục Nhanh Lỗi Không Phát Được Âm Thanh Trên Flama Audio & Trình Duyệt** | `sửa lỗi flama audio không phát tiếng` | `audio flashcard tiếng nhật`, `flama audio` | 1,500 – 1,800 từ | `https://flama.vn/guide/troubleshooting/flama-audio`<br>*CTA: Kiểm tra kết nối audio* |
| **W9** | **#17** | **GĐ 3: Marketplace Hub** | Trans / Info | **Kho Bộ Thẻ Tiếng Nhật Flama Marketplace: Khám Phá & Tải Học Liệu Miễn Phí** | `flama marketplace`, `kho flashcard tiếng nhật cộng đồng` | `chia sẻ bộ thẻ tiếng nhật`, `bộ thẻ học tiếng nhật có audio` | 3,000 – 3,500 từ (Hub Pillar) | `https://flama.vn/guide/marketplace/discovery`<br>*CTA: Khám phá Marketplace* |
| **W9** | **#18** | GĐ 3: Clone Overlay | Info / Trans | **Cơ Chế Clone Overlay Của Flama: Tự Do Thêm Ghi Chú Riêng Mà Không Sợ Bị Ghi Đè** | `flama clone overlay` | `cách xuất bản bộ thẻ lên marketplace`, `đóng góp sửa lỗi bộ thẻ flashcard` | 2,200 – 2,500 từ | `https://flama.vn/guide/marketplace/overlay-clone`<br>*CTA: Trải nghiệm Clone Overlay* |
| **W10** | **#19** | **GĐ 3: JLPT N5-N4 Decks**| Transactional | **Tải Trọn Bộ Flashcard Tiếng Nhật N5 & N4 Chuẩn Minna No Nihongo 50 Bài Có Audio** | `bộ thẻ tiếng nhật n5`, `flashcard tiếng nhật n4` | `bộ thẻ minna no nihongo 50 bài`, `bộ thẻ học tiếng nhật có audio` | 3,000 – 3,500 từ (High-Intent Pillar) | `https://flama.vn/marketplace/jlpt-n5-minna`<br>*CTA: Cài đặt bộ thẻ N5-N4* |
| **W10** | **#20** | GĐ 3: Kanji 2136 Joyo | Transactional | **Trọn Bộ Thẻ 2136 Chữ Hán Thường Dùng (Joyo Kanji N5 - N1) Kèm Thứ Tự Nét & Hán Việt** | `flashcard kanji n5 n1` | `cách nhớ kanji nhanh`, `bộ thẻ học tiếng nhật có audio` | 2,500 – 3,000 từ | `https://flama.vn/marketplace/kanji-2136-joyo`<br>*CTA: Tải bộ thẻ Kanji 2136* |
| **W11** | **#21** | **GĐ 3: JLPT N3-N2 Prep** | Trans / Comm | **Bộ Từ Vựng JLPT N3 & N2 Mimikara Oboeru & Soumatome: Bí Quyết Đạt Điểm Cao** | `từ vựng jlpt n3 anki`, `lộ trình từ vựng jlpt n2` | `bộ thẻ từ vựng soumatome`, `bộ thẻ shinkanzen master` | 2,800 – 3,200 từ (High-Intent Pillar) | `https://flama.vn/marketplace/jlpt-n3-mimikara`<br>*CTA: Cài đặt bộ thẻ N3-N2* |
| **W11** | **#22** | GĐ 3: JLPT N1 Advanced | Transactional | **Bộ Flashcard Từ Vựng JLPT N1 Đỉnh Cao & Shinkanzen Master Dành Cho Kỹ Sư, Biên Dịch** | `bộ flashcard từ vựng n1`, `bộ thẻ shinkanzen master` | `lộ trình từ vựng jlpt n2`, `chia sẻ bộ thẻ tiếng nhật` | 2,200 – 2,600 từ | `https://flama.vn/marketplace/jlpt-n1-advanced`<br>*CTA: Tải bộ thẻ N1 nâng cao* |
| **W12** | **#23** | **GĐ 3: Creator Hub** | Info / Trans | **Hướng Dẫn Tác Giả Xuất Bản Bộ Thẻ & Cơ Chế Đóng Góp Sửa Lỗi Trên Flama Marketplace** | `cách xuất bản bộ thẻ lên marketplace`, `đóng góp sửa lỗi bộ thẻ flashcard` | `chia sẻ bộ thẻ tiếng nhật`, `flama marketplace` | 2,200 – 2,500 từ | `https://flama.vn/guide/marketplace/creator-publishing`<br>*CTA: Đăng bộ thẻ đầu tiên* |
| **W12** | **#24** | GĐ 3: Best Apps Review | Comm / Info | **Đánh Giá Top 5 Phần Mềm Flashcard Tiếng Nhật Tốt Nhất 2026 Cho Người Việt** | `phần mềm flashcard tiếng nhật tốt nhất` | `app học từ vựng như anki`, `thay thế anki học tiếng nhật` | 2,800 – 3,200 từ (Round-up) | `https://flama.vn`<br>*CTA: Trải nghiệm Flama ngay* |

---

### 3.2. Bảng Đối Chiếu Kiểm Tra Bao Phủ Toàn Bộ 68 Từ Khóa (68/68 Coverage Audit)

Bảng dưới đây chứng minh 100% từ khóa chiến lược trong `KEYWORD_RESEARCH_MATRIX.md` được phân bổ chính xác vào 24 bài viết:

| Tuần xuất bản | Danh mục từ khóa được phân bổ trong tuần | Số từ khóa | % Tích lũy |
|---|---|---|---|
| **Tuần 1** | `flama`, `flama vn`, `flama tiếng nhật`, `học tiếng nhật flama`, `app flama`, `flama web`, `flama flashcard`, `quản lý bộ thẻ flashcard`, `app học từ vựng tiếng nhật` | 9 từ khóa | 13.2% |
| **Tuần 2** | `yomitan tiếng nhật`, `cách dùng yomitan`, `mining từ vựng yomitan`, `cài từ điển cho yomitan`, `yomichan sang yomitan`, `field markers yomitan`, `pitch accent yomitan flashcard`, `tạo card anki 1 click` | 8 từ khóa | 25.0% |
| **Tuần 3** | `phát âm tiếng nhật voicevox`, `voicevox tiếng nhật miễn phí`, `tts tiếng nhật chuẩn ngữ điệu`, `phần mềm đọc từ vựng tiếng nhật offline`, `tạo âm thanh flashcard tiếng nhật`, `flama audio`, `tải flama audio portable`, `audio flashcard tiếng nhật` | 8 từ khóa | 36.8% |
| **Tuần 4** | `khai thác từ vựng tiếng nhật khi xem anime`, `flama connect`, `tiện ích yomitan đọc báo tiếng nhật`, `yomitan kết nối flama`, `yomitan trên điện thoại android`, `yomitan anki bridge`, `lỗi yomitan could not connect` | 7 từ khóa | 47.1% |
| **Tuần 5** | `học từ vựng srs`, `spaced repetition tiếng nhật`, `cách học từ vựng nhớ lâu bằng srs`, `phần mềm lặp lại ngắt quãng`, `flama srs`, `chuyển anki sang flama`, `tải file anki tiếng nhật`, `đồng bộ anki không cần ankiweb`, `web học từ vựng lặp lại ngắt quãng` | 9 từ khóa | 60.3% |
| **Tuần 6** | `thay thế anki học tiếng nhật`, `app học từ vựng như anki`, `phần mềm flashcard tiếng nhật tốt nhất`, `flashcard tiếng nhật srs`, `anki tiếng nhật cho người mới`, `cách nhớ kanji nhanh`, `học từ vựng tiếng nhật nhớ lâu` | 7 từ khóa | 70.6% |
| **Tuần 7** | `thuật toán fsrs anki`, `thẻ đục lỗ cloze deletion tiếng nhật` | 2 từ khóa | 73.5% |
| **Tuần 8** | `kokoro tts tiếng nhật`, `luyện nghe tiếng nhật tts`, `tích hợp voicevox vào flashcard`, `khóa api cloud tts openai elevenlabs`, `sửa lỗi flama audio không phát tiếng` | 5 từ khóa | 80.9% |
| **Tuần 9** | `flama marketplace`, `kho flashcard tiếng nhật cộng đồng`, `chia sẻ bộ thẻ tiếng nhật`, `bộ thẻ học tiếng nhật có audio`, `flama clone overlay` | 5 từ khóa | 88.2% |
| **Tuần 10** | `bộ thẻ tiếng nhật n5`, `flashcard tiếng nhật n4`, `bộ thẻ minna no nihongo 50 bài`, `flashcard kanji n5 n1` | 4 từ khóa | 94.1% |
| **Tuần 11** | `từ vựng jlpt n3 anki`, `lộ trình từ vựng jlpt n2`, `bộ thẻ từ vựng soumatome`, `bộ flashcard từ vựng n1`, `bộ thẻ shinkanzen master` | 5 từ khóa | 100.0% |
| **Tuần 12** | `cách xuất bản bộ thẻ lên marketplace`, `đóng góp sửa lỗi bộ thẻ flashcard` (gia cố lại toàn bộ cụm) | 2 từ khóa | **100% (68/68)** |

---

## 4. KHUNG ĐO LƯỜNG GOOGLE SEARCH CONSOLE (GSC KPI FRAMEWORK)

### 4.1. Bộ Chỉ Số Đánh Giá Cốt Lõi (Core Metrics)
1. **Tổng lượt hiển thị (Total Impressions)**: Đo lường mức độ bao phủ của thương hiệu Flama và các trang tính năng trên Google SERP.
2. **Tổng lượt nhấp chuột (Total Clicks)**: Số lượng học viên thực tế truy cập vào `https://flama.vn`.
3. **Tỷ lệ nhấp chuột trung bình (Average CTR)**:
   - Từ khóa Thương hiệu: **CTR mục tiêu > 75%**
   - Từ khóa Tính năng & Cẩm nang hướng dẫn: **CTR mục tiêu 6% – 12%**
   - Từ khóa Bộ thẻ JLPT & Thay thế Anki: **CTR mục tiêu 8% – 15%**
4. **Vị trí xếp hạng trung bình (Average Position)**: Theo dõi lộ trình tăng hạng của từng cụm từ khóa qua các mốc thời gian.
5. **Tỷ lệ lập chỉ mục thành công (Index Coverage Ratio)**: 100% URL trong sitemap được Googlebot index hợp lệ, không có lỗi loại trừ.

---

### 4.2. Mục Tiêu Hiệu Suất Theo Mốc 30 - 60 - 90 Ngày (Quantitative Performance Targets)

```
        [ MỐC 30 NGÀY ] ──────────────► [ MỐC 60 NGÀY ] ──────────────► [ MỐC 90 NGÀY ]
   (Quick-Wins & Brand Defense)    (Authority Building & SRS)    (High-Volume Commercial Scaling)
   - 100% Brand Top 1              - 15 Feature keywords Top 3-10 - 60%+ tổng từ khóa Top 10
   - 100% Sitemap Indexed         - Google Sitelinks kích hoạt   - 15,000+ Clicks/tháng
   - 1,500 - 2,500 Clicks/tháng   - 5,000 - 8,000 Clicks/tháng   - > 2,000 Đăng ký mới/tháng
```

| Chỉ số Đo Lường (KPI Metric) | Mốc 30 Ngày (Sau Tuần 4) | Mốc 60 Ngày (Sau Tuần 8) | Mốc 90 Ngày (Sau Tuần 12) |
|---|---|---|---|
| **Từ khóa Thương hiệu Top 1 (Brand)** | **100% (12/12 từ khóa)** đạt Top 1 tuyệt đối | Duy trì Top 1 ổn định | Top 1 kèm đầy đủ 6 Sitelinks & Search Box |
| **Từ khóa Ngách KD < 30 (Yomitan & TTS)** | 8 – 10 từ khóa lọt Top 1–5 | 12 – 14 từ khóa lọt Top 1–3 | 14/14 từ khóa duy trì Top 1–3 vững chắc |
| **Từ khóa Cốt lõi SRS & Anki (KD 30–50)** | Xuất hiện trang 2 (Top 11–20) | 8 – 10 từ khóa lọt Top 3–10 | 12 – 15 từ khóa lọt Top 1–5 |
| **Từ khóa Bộ thẻ JLPT N5–N1 (KD > 50)** | Lập chỉ mục thành công, Top 30–50 | 5 – 7 từ khóa lọt Top 10–20 | 10 – 12 từ khóa lọt Top 3–10 |
| **Tổng Lượt Hiển Thị Hàng Tháng (Impressions)** | 15,000 – 25,000 lượt | 45,000 – 65,000 lượt | 120,000 – 160,000+ lượt |
| **Tổng Lượt Nhấp Chuột Hàng Tháng (Clicks)** | 1,500 – 2,500 clicks | 5,000 – 8,000 clicks | 15,000 – 25,000+ clicks |
| **Tỷ Lệ Lập Chỉ Mục (Index Coverage Ratio)** | 100% (38/38 URLs sitemap) | 100% (Toàn bộ 16 bài viết mới) | 100% (Toàn bộ 24 bài viết + Landing) |
| **Tài Khoản Đăng Ký Mới Từ Organic Search** | > 200 học viên mới | > 800 học viên mới | > 2,000 học viên mới / tháng |

---

## 5. QUY TRÌNH XỬ LÝ SỰ CỐ GSC & THỨ HẠNG (5 TROUBLESHOOTING PLAYBOOKS)

Khi theo dõi hiệu quả trên Google Search Console, nếu phát hiện bất kỳ dấu hiệu bất thường nào, đội ngũ kỹ thuật và nội dung phải kích hoạt ngay quy trình xử lý chuẩn hóa sau:

```
                            [ PHÁT HIỆN SỰ CỐ TRÊN GSC ]
                                         │
        ┌──────────────────┬─────────────┴───────────┬──────────────────┐
        ▼                  ▼                         ▼                  ▼
1. Đã phát hiện      2. Đã thu thập            3. Chững thứ hạng    4. Ăn thịt từ khóa
(Discovered not      (Crawled not              (Stagnant Rank       (Keyword Cannibalization)
   indexed)             indexed)                 Page 2-3)
```

### Playbook 1: URL Bị Báo "Đã phát hiện - hiện chưa được lập chỉ mục" (Discovered – currently not indexed)
- **Dấu hiệu**: URL xuất hiện trong báo cáo Lập chỉ mục của GSC nhưng trạng thái là màu xám, không có dữ liệu hiển thị trên Google.
- **Nguyên nhân gốc rễ**: Googlebot đã tìm thấy liên kết qua Sitemap hoặc liên kết nội bộ, nhưng máy chủ Google đang quá tải hoặc đánh giá ngân sách thu thập (Crawl Budget) của domain chưa đủ để ưu tiên nạp nội dung.
- **Quy trình xử lý 4 bước**:
  1. *Kiểm tra liên kết nội bộ (Internal Link Audit)*: Đảm bảo URL này có ít nhất 2–3 liên kết ngữ cảnh trỏ từ Trang chủ hoặc trang Pillar `/guide` với Anchor text rõ ràng.
  2. *Kiểm tra XML Sitemap*: Xác nhận URL có trong `sitemap.xml`, mã phản hồi HTTP là `200 OK`, và thẻ `<lastmod>` phản ánh đúng thời gian gần nhất.
  3. *Chạy Kiểm tra URL trực tiếp (URL Inspection)*: Mở GSC, dán URL vào thanh tìm kiếm, bấm "Test Live URL" để xem ảnh chụp màn hình DOM và bấm nút **"Request Indexing"**.
  4. *Kích hoạt Google Indexing API*: Với các bài viết quan trọng trong chiến dịch, chạy script gọi Google Indexing API qua tài khoản Google Cloud Service Account để kích hoạt bot thu thập trong vòng 2–6 giờ.

---

### Playbook 2: URL Bị Báo "Đã thu thập dữ liệu - hiện chưa được lập chỉ mục" (Crawled – currently not indexed)
- **Dấu hiệu**: Googlebot đã tải mã nguồn của trang nhưng thuật toán từ chối đưa trang vào chỉ mục tìm kiếm.
- **Nguyên nhân gốc rễ**: Nội dung bị thuật toán đánh giá là **nội dung mỏng (Thin Content)**, trùng lặp quá nhiều đoạn văn mẫu (boilerplate) từ các bài khác, hoặc thiếu thông tin giá trị so với các trang sẵn có trên Google.
- **Quy trình xử lý 4 bước**:
  1. *Đánh giá chất lượng và độ dài*: Nếu bài viết dưới 1,500 từ, bổ sung ngay các bảng so sánh thực tế, hình ảnh chụp màn hình từ ứng dụng Flama, và các mẹo thực hành độc quyền.
  2. *Viết lại phần mở đầu & kết luận*: Đảm bảo 100 từ đầu tiên không sao chép nguyên văn từ bài viết khác, lồng ghép ngữ cảnh cá nhân hóa và giải quyết trực tiếp câu hỏi của người học.
  3. *Bổ sung Schema Markup*: Gắn thêm cấu trúc dữ liệu `HowTo` hoặc `FAQPage` để cung cấp tín hiệu máy đọc rõ ràng về cấu trúc nội dung.
  4. *Cập nhật ngày sửa đổi & gửi lại*: Cập nhật trường `<lastmod>` trong sitemap và gửi lại yêu cầu lập chỉ mục trên GSC.

---

### Playbook 3: Từ Khóa Bị Chững Thứ Hạng Ở "Trang 2-3" (Stagnant Rankings - Positions 11 to 30)
- **Dấu hiệu**: Bài viết đã được lập chỉ mục, có hiển thị nhưng vị trí trung bình kẹt cứng ở mức 12–25 suốt 3–4 tuần không vào được Top 10.
- **Nguyên nhân gốc rễ**: Trang web đã đạt tiêu chuẩn cơ bản nhưng thiếu "Lực đẩy thẩm quyền (Authority Boost)" hoặc "Trải nghiệm tương tác người dùng (Engagement Signals)" để vượt qua các trang tin tức lớn hoặc đối thủ lâu năm.
- **Quy trình tối ưu 5 bước**:
  1. *Tối ưu hóa Thẻ Tiêu Đề để tăng CTR*: Thêm các yếu tố kích thích nhấp chuột: năm hiện tại `2026`, từ ngữ chỉ tốc độ (`1 Phút`, `Cực Nhanh`), hoặc lợi ích vượt trội (`Miễn Phí`, `Chuẩn Tokyo`). Tăng CTR từ 2% lên 5% là tín hiệu mạnh giúp Google tự động đẩy hạng bài viết.
  2. *Lấp đầy khoảng trống nội dung (Content Gap Analysis)*: Đối chiếu với 3 bài viết đang đứng Top 1–3, bổ sung các phần mà họ có nhưng Flama chưa đề cập (ví dụ: bảng phím tắt, video hướng dẫn ngắn, giải đáp thắc mắc chi tiết).
  3. *Tối ưu độ gần thực thể (Semantic Proximity)*: Rà soát đoạn mở đầu và thân bài, lồng ghép các thực thể theo Tam giác ngữ nghĩa Flama trong khoảng cách ≤ 15 từ.
  4. *Bơm sức mạnh liên kết nội bộ (Internal Link Push)*: Đặt thêm 3–4 internal links từ Trang chủ và các bài viết có lượng truy cập cao nhất trỏ về trang đang bị kẹt, sử dụng Anchor text khớp chính xác hoặc khớp cụm từ tự nhiên.
  5. *Đánh giá lại sau 14 ngày*: Theo dõi biểu đồ Performance trên GSC; khi thứ hạng dịch chuyển vào Top 10, tiếp tục duy trì và củng cố liên kết.

---

### Playbook 4: Hiện Tượng Tự Cạnh Tranh Từ Khóa (Keyword Cannibalization)
- **Dấu hiệu**: Trong báo cáo GSC, một từ khóa chính hiển thị xen kẽ lúc thì URL Trang chủ, lúc thì URL bài viết Guide; thứ hạng trồi sụt thất thường và không trang nào lọt được vào Top 5.
- **Nguyên nhân gốc rễ**: Có từ 2 trang trở lên trên `flama.vn` cùng nhắm vào một từ khóa chính, khiến Google bối rối không biết chọn trang nào làm đại diện chính thức.
- **Quy trình xử lý 3 bước**:
  1. *Xác định URL chủ lực duy nhất*: Dựa trên Search Intent để chọn URL đích chuẩn xác nhất (ví dụ: từ khóa thương mại `thay thế anki học tiếng nhật` trỏ về trang so sánh `/so-sanh/flama-vs-anki`; từ khóa thông tin `phương pháp srs` trỏ về `/guide/study/spaced-repetition`).
  2. *Điều chỉnh toàn bộ Anchor Text nội bộ*: Sửa lại tất cả các liên kết nội bộ trong toàn site, chỉ trỏ từ khóa đó về duy nhất URL chủ lực đã chọn. Trang phụ phải đặt một liên kết trỏ về trang chính với câu dẫn: *"Để tìm hiểu so sánh toàn diện, hãy xem tại..."*.
  3. *Gộp nội dung hoặc khai báo Canonical*: Nếu hai bài viết có nội dung quá tương đồng, tiến hành sáp nhập nội dung bài yếu vào bài mạnh và thiết lập lệnh chuyển hướng 301 hoặc gắn thẻ `<link rel="canonical">` trỏ về URL chính.

---

### Playbook 5: Lỗi Soft 404 & Điều Hướng Sai Trong React SPA (SPA Routing Redirections)
- **Dấu hiệu**: Googlebot báo lỗi "Soft 404" hoặc "Trang bị chuyển hướng" cho hàng loạt URL trong chuyên mục cẩm nang `/guide/*`.
- **Nguyên nhân gốc rễ**: Trong kiến trúc Single Page Application (React SPA), nếu một route tài liệu gặp lỗi tải dữ liệu hoặc người dùng chưa đăng nhập mà bị component Auth chuyển hướng nhầm về `/login`, Googlebot sẽ nhận diện toàn bộ các trang tài liệu là trang rỗng hoặc trang 404 giả tạo.
- **Quy trình xử lý 3 bước**:
  1. *Bảo vệ danh mục Sitemap công khai*: Chỉ cho phép các URL công khai (Public Routes) nằm trong `sitemap.xml`. Tuyệt đối không để lọt các route cá nhân yêu cầu đăng nhập (`/study`, `/browse`, `/dashboard`).
  2. *Đảm bảo phản hồi HTTP 200 tại tầng máy chủ Flask*: Cấu hình `app/spa.py` để mọi route công khai `/guide/*` luôn trả về mã trạng thái HTTP 200 kèm theo đầy đủ thẻ meta Title, Description và khối Schema JSON-LD trong mã HTML gốc ban đầu.
  3. *Xử lý mã lỗi HTTP 404 chuẩn mực*: Khi người dùng hoặc bot truy cập vào một URL không tồn tại, máy chủ Flask phải phản hồi đúng mã trạng thái `HTTP 404 Not Found` thay vì trả về mã 200 kèm trang trắng phía client.

---

*Tài liệu vận hành nội dung được ban hành cho Đội ngũ Marketing & Kỹ thuật Flama.vn — Bắt buộc tuân thủ lịch xuất bản và báo cáo chỉ số GSC định kỳ hàng tuần.*
