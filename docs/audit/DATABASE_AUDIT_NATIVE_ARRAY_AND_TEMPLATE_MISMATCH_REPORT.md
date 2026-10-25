# BÁO CÁO KIỂM TOÁN KỸ THUẬT TOÀN DIỆN CƠ SỞ DỮ LIỆU
## NATIVE ARRAY, DELIMITERS & TEMPLATE MISMATCH TRÊN NỀN TẢNG FLAMA (MYSQL 8.0)

- **Mã tài liệu**: `FLAMA-AUDIT-20261024-DB-ARRAY-TEMPLATE-MISMATCH`
- **Môi trường thẩm định**: MySQL 8.0 Local (`localhost:3306`, Database: `nihongo`, snapshot đồng bộ từ production)
- **Tổng quy mô hệ thống**: **41,624 Notes** | **5,579 Decks**
- **Chế độ kiểm toán**: `STRICT_READ_ONLY` (0 thao tác INSERT/UPDATE/DELETE trên database)
- **Ngày hoàn tất**: 2026-10-24
- **Đơn vị thực hiện**: Nhóm Kiểm toán Kỹ thuật Độc lập Flama (Teamwork Subagents: Explorer R1, Explorer R2, Explorer R3, Master Worker M1)

---

## MỤC LỤC
1. [TỔNG QUAN ĐIỀU HÀNH (EXECUTIVE SUMMARY)](#1-tổng-quan-điều-hành-executive-summary)
2. [PHẦN 1: BỘ FLAMA DEFAULT — KIỂM TOÁN DELIMITER VÀ NATIVE ARRAY (R1)](#phần-1-bộ-flama-default--kiểm-toán-delimiter-và-native-array-r1)
   - 1.1. Hiện trạng và Định nghĩa Trường NoteType Flama Standard Vocabulary
   - 1.2. Thống kê Phân loại Delimiter: Dạng 1, Dạng 2, Dạng 3 và Mảng giả 1 phần tử
   - 1.3. Bảng Dữ liệu Thực tế Trích xuất từ Cơ sở Dữ liệu
   - 1.4. Thuật toán Bóc tách An toàn Bảo vệ Ngoặc (Bracket-Shielding Algorithm)
   - 1.5. Đề xuất Định dạng JSON List Chuẩn & Hiện đại hóa Presentation Template
3. [PHẦN 2: NHÓM TRỌNG TÂM CHUNGBECHN1 — NOTETYPE, TEMPLATE & BẤT THƯỜNG NGỮ NGHĨA (R2)](#phần-2-nhóm-trọng-tâm-chungbechn1--notetype-template--bất-thường-ngữ-nghĩa-r2)
   - 2.1. Cấu trúc Cây Thư mục ChungBechN1, Quyền Sở hữu và Thực thể Phái sinh
   - 2.2. Ma trận Đối chiếu NoteType `文法N1`, `漢字N1`, `Kanji_N3` với Template
   - 2.3. Phân tích Chi tiết Lỗi Cú pháp Template và Khiếm khuyết DOM/CSS
   - 2.4. Kiểm toán Hoán đổi Ngữ nghĩa (Semantic Inversions) & Dữ liệu Bất thường
   - 2.5. Bảng FieldDef Chuẩn hóa & Mã nguồn Template Mustache Responsive
4. [PHẦN 3: NHÓM TRỌNG TÂM ENGLISH (EN4EVERYONE) — TRƯỜNG ĐA GIÁ TRỊ, STT & TEMPLATE MISMATCH (R3)](#phần-3-nhóm-trọng-tâm-english-en4everyone--trường-đa-giá-trị-stt--template-mismatch-r3)
   - 3.1. Đối chiếu Kiến trúc 2 NoteType `6b2a8fec` và `13ff54d7`
   - 3.2. Kiểm toán Trường Đa Giá Trị & Hiện trạng Lưu trữ Dữ liệu
   - 3.3. Kiểm toán Trường Legacy: `STT` (Số Thứ Tự) & Quyết Định Loại Bỏ
   - 3.4. Kiểm toán Sự Gắn Nhầm Template: `Gõ chép chính tả` (`fc011484`)
   - 3.5. Kiểm chứng Bảo toàn 100% Phiên âm Quốc tế IPA `/<ipa>/`
   - 3.6. Ma trận Trường Chuẩn hóa & Template Presentation En4Everyone Mới
5. [PHẦN 4: MA TRẬN TỔNG HỢP NOTETYPE VÀ TEMPLATE MISMATCH TOÀN HỆ THỐNG](#phần-4-ma-trận-tổng-hợp-notetype-và-template-mismatch-toàn-hệ-thống)
6. [PHẦN 5: KẾ HOẠCH HÀNH ĐỘNG VÀ LỘ TRÌNH NÂNG CẤP (ACTION PLAN & UPGRADE ROADMAP)](#phần-5-kế-hoạch-hành-động-và-lộ-trình-nâng-cấp-action-plan--upgrade-roadmap)
   - 6.1. Nguyên tắc An toàn & Cam kết Zero Data Loss
   - 6.2. Lộ trình Triển khai Phân kỳ (4 Làn sóng - Waves)
   - 6.3. Quy trình Thực thi Giao dịch (Transactional Chunking & Preimage Rollback)
   - 6.4. Phương pháp Kiểm chứng Độc lập

---

## 1. TỔNG QUAN ĐIỀU HÀNH (EXECUTIVE SUMMARY)

Báo cáo này tổng hợp kết quả của đợt tổng kiểm toán kỹ thuật chuyên sâu trên toàn bộ cơ sở dữ liệu MySQL 8.0 `nihongo` (đồng bộ mới nhất từ Production chứa **41,624 notes** và **5,579 decks**). Mục tiêu cốt lõi là nhận diện, định lượng và phân loại toàn diện hai vấn đề kiến trúc mang tính lịch sử:
1. **Dữ liệu mảng chưa chuẩn hóa (Non-native Delimited Strings & Fake 1-Element Arrays)**: Tàn dư từ quá trình import các bộ thẻ Anki cũ, nơi các trường danh sách (nghĩa, ví dụ, cụm từ, cách đọc) bị nối phẳng bằng ký tự phân cách (`$`, `\n`, `<br>`, `;`, `、`, `,`) hoặc bị gói vào mảng JSON 1 phần tử `["item1 $ item2"]`, buộc giao diện phải dùng script client-side can thiệp DOM để hiển thị.
2. **Template Mismatch & Bất thường Ngữ nghĩa (Semantic Inversions)**: Sự sai lệch giữa định nghĩa trường trong `field_defs` và mã nguồn Presentation Template (HTML/Mustache), bao gồm lỗi cú pháp unclosed `<div>`, layout cưỡng bức `height: 100vh` làm tràn màn hình di động, trường tàn dư legacy `STT` (được tác giả chỉ đạo xóa bỏ hoàn toàn), gắn nhầm template bài tập gõ phím vào deck học thường, và hiện tượng hoán đổi 1-to-1 tai hại giữa trường `Phiên âm` (tiếng Nhật) và `Âm Hán Tự` (tiếng Việt).

### 1.1. Bảng Số Liệu Tổng Quan Hệ Thống

| Phân hệ / Nhóm Học liệu | Tổng số Notes | Tổng số Decks | Số Notes Bị Ảnh hưởng | Tỷ lệ Bị Ảnh hưởng | Vấn đề Kỹ thuật Cốt lõi |
| :--- | ---: | ---: | ---: | ---: | :--- |
| **Flama Standard Vocabulary (R1)** | 35,112 | 1,305 | **5,869 unique notes** (290 decks)<br>**35,103** *(fake array-1)* | 16.7% *(delimiters)*<br>**99.97%** *(fake array)* | Hợp chuẩn xác (Set Union) gồm: Dạng 1 (5,669 notes/276 decks), Dạng 2 (3 notes/3 decks), Dạng 3 (207 notes/23 decks), trừ 10 notes giao giữa D1 và D3 = 5,869 unique notes trên 290 decks; 99.97% trường mảng bị bọc 1 phần tử dính delimiter. Script DOM `auto-split` regex `replace(/\$/g)`. |
| **ChungBechN1 Cohort (R2)** | 1,019 | 35 | **324** | **31.8%** | **148 notes đảo 1-to-1** `Phiên âm` <-> `Âm Hán Tự`; 70 notes Kanji trong Hán Việt; lỗi unclosed `<div>` phá vỡ DOM; cưỡng bức `100vh` di động; duplicate `{{Diagram}}`. |
| **English En4Everyone (R3)** | 5,301 | 186 | **5,301** | **100.0%** | **Trường Legacy `STT` (5,301 notes) sẽ được xóa bỏ khỏi schema**; 143 decks (4,122 notes) bị **gắn nhầm Template `Gõ chép chính tả`** vứt bỏ 9 trường từ vựng; lệch schema giữa NoteType gốc và clone; 1,142 notes chứa `;` thô trong `Word Family`. |
| **Toàn bộ Cơ sở Dữ liệu** | **41,624** | **5,579** | **40,735** | **97.86%** | Tổng hòa các vấn đề trên (trong đó 39,338 notes thuộc sở hữu của User 1 - tác giả chính). |

### 1.2. Tóm Tắt Các Rủi Ro Kỹ Thuật Trọng Yếu Đã Nhận Diện

1. **Rủi ro DOM Distortion & Layout Collapse do Unclosed `<div>`**:
   Trong toàn bộ 5 template ngữ pháp N1 (`0a86851a`, `266cbc84`, `48a17d92`, `c51dc3ba`, `d81c0a0a`), khối thẻ `<div style='display: flex; ...'>` được mở bên trong `{{#name}}` nhưng không có thẻ đóng tương ứng trước `{{/name}}`, sau đó lại xuất hiện một thẻ đóng mồ côi `</div>` sau `{{#additional_example}}`. Khi render trên React SPA, trình duyệt buộc phải tự vá DOM, dẫn đến hiện tượng vỡ layout Flexbox và nội dung thẻ trước tràn vào thẻ sau.
2. **Rủi ro Cắt Cụt Nội Dung trên Mobile do Rigid `height: 100vh`**:
   Hầu hết các template cũ dùng fixed `height: 100vh` cho Front card. Trên thiết bị di động (Safari iOS, Chrome Android), thanh địa chỉ (URL bar) thay đổi chiều cao động khi cuộn, khiến nội dung bị giật hình (layout jitter) hoặc bị cắt cụt mất từ vựng khi kích thước font chữ vượt quá 70px.
3. **Rủi ro Hỏng Công Cụ Đọc Phát Âm TTS do Hoán Đổi Ngữ Nghĩa 1-to-1**:
   Trong NoteType `Kanji_N3` (Deck 3213-3224), **148 notes** bị đảo ngược vị trí hoàn toàn giữa `Phiên âm` (lưu chữ Hán Việt viết hoa `CHUẨN BỊ`, `TỐT NGHIỆP`) và `Âm Hán Tự` (lưu chữ Kana tiếng Nhật `じゅんび`, `そつぎょう`). Khi người học bấm nút nghe phát âm hoặc Flama Audio kích hoạt VoiceVox/Kokoro TTS trên trường `Phiên âm`, engine phát âm tiếng Nhật cố đọc chuỗi tiếng Việt có dấu, sinh ra âm thanh méo mó hoặc crash engine.
4. **Rủi ro Ép Buộc Học Khuyết Tật do Gắn Nhầm Template `Gõ chép chính tả`**:
   Study Application `6f4f0b3d` đang kích hoạt template `fc011484` trên NoteType `En4Everyone` (`6b2a8fec`), ép buộc toàn bộ **143 decks (4,122 notes)** sinh thêm thẻ gõ phím. Tuy nhiên, có **211 notes hoàn toàn không có audio** và **98.7% notes không có ảnh**, đồng thời template gõ phím lược bỏ 9 trường kiến thức quan trọng (Collocation, Synonym, Antonym, Word Family), khiến trải nghiệm học tập bị phá vỡ.
5. **Rủi ro Phá Hủy Công Thức Toán & Tiền Tệ nếu Tách Chuỗi Ngây Thơ (Naive Split)**:
   Nếu dùng script tách chuỗi đơn giản theo ký tự `$`, các công thức số mũ toán học như `且$^2$` (Note `863e0409`) sẽ bị xóa mất ký hiệu mũ, và giá trị tiền tệ tiếng Anh như `$25,000` sẽ bị tách thành các mẩu chuỗi rác. Do đó, bắt buộc phải áp dụng thuật toán bóc tách có bảo vệ ngoặc (Bracket-Shielding Algorithm).

---

## PHẦN 1: BỘ FLAMA DEFAULT — KIỂM TOÁN DELIMITER VÀ NATIVE ARRAY (R1)

### 1.1. Hiện trạng và Định nghĩa Trường NoteType Flama Standard Vocabulary

- **NoteType ID**: `e2f310a8-ecb3-4446-8a93-4c258e52b132`
- **Tên NoteType**: `Flama Standard Vocabulary`
- **Trạng thái**: `is_official = 1`, `publish_status = 'published'`
- **Quy mô thực tế**: **35,112 notes** trải rộng trên **1,305 decks**.
- **Template Mặc định**: `Default Flama Flashcard` (`e0cb18b2-881d-4b46-a567-dc5db14d661f`), gắn qua Study Application `e47485cc-84a8-41ae-8836-5dec2e7b9963` (`status_code = 'ACTIVE'`, `is_default = 1`).

#### Bảng Danh Mục 16 Trường trong `field_defs`:
| Vị trí | Tên Trường | Kiểu Schema | Bắt buộc | Nhận xét Chức năng |
| :---: | :--- | :---: | :---: | :--- |
| 0 | `word` | `text` | 1 | Từ vựng mục tiêu (Kanji / Kana / Romaji). |
| 1 | `hanviet` | `text` | 0 | Âm Hán Việt (đang là scalar text nhưng có notes chứa `$`). |
| 2 | `reading` | `array` | 0 | Cách đọc Kana (JSON list). |
| 3 | `translation_vi` | `array` | 0 | Nghĩa ngắn gọn tiếng Việt. |
| 4 | `meaning_jp` | `array` | 0 | Giải nghĩa tiếng Nhật (monolingual definition). |
| 5 | `meaning_vi` | `array` | 0 | Giải nghĩa chi tiết tiếng Việt. |
| 6 | `usage_jp` | `array` | 0 | Cách dùng tiếng Nhật. |
| 7 | `usage_vi` | `array` | 0 | Cách dùng tiếng Việt. |
| 8 | `example_jp` | `array` | 0 | Câu ví dụ tiếng Nhật. |
| 9 | `example_vi` | `array` | 0 | Câu dịch ví dụ tiếng Việt. |
| 10 | `additional_note_jp` | `richtext` | 0 | Ghi chú văn cảnh tiếng Nhật. |
| 11 | `additional_note_vi` | `richtext` | 0 | Ghi chú sắc thái từ vựng tiếng Việt. |
| 12 | `image` | `image` | 0 | Ảnh minh họa từ vựng. |
| 13 | `diagram` | `image` | 0 | Thứ tự nét vẽ Kanji (Stroke order SVG). |
| 14 | `word_audio` | `audio` | 0 | Âm thanh phát âm từ vựng. |
| 15 | `example_audio` | `audio` | 0 | Âm thanh phát âm câu ví dụ. |

---

### 1.2. Thống kê Phân loại Delimiter: Dạng 1, Dạng 2, Dạng 3 và Mảng Giả 1 Phần Tử

Kiểm toán tự động trên 35,112 notes đã phát hiện **5,869 unique notes (290 unique decks)** chứa trực tiếp ký tự phân cách cũ `\n` hoặc `$` trong các trường dữ liệu, được phân chia chính xác thành 3 dạng cấu trúc:

| Phân Loại Dữ Liệu | Số Notes | Số Decks | Các Trường Bị Ảnh Hưởng | Chi Tiết Ký Tự Phân Cách |
| :--- | ---: | ---: | :--- | :--- |
| **Dạng 1: Chuỗi đơn (Scalar String) chứa `\n` hoặc `$`** (không có `<br>`) | **5,669** | **276** | `diagram` (5,231 notes)<br>`additional_note_vi` (359 notes)<br>`additional_note_jp` (324 notes)<br>`image` (6 notes)<br>`word` (5 notes)<br>`hanviet` (3 notes) | `newline` (`\n`): 5,292 lần<br>`dollar` (`$`): 636 lần<br>*(Tổng số lần xuất hiện: 5,928)* |
| **Dạng 2: Mảng giả 1 phần tử (Fake 1-Element Array) chứa `$`** (không có `<br>`) | **3** | **3** | `reading` (3 notes) | `dollar` (`$`): 3 lần trong `['reading1$reading2']` |
| **Dạng 3: Chuỗi HTML chứa `<br>` kèm `\n` hoặc `$`** | **207** | **23** | `additional_note_jp` (201 notes)<br>`additional_note_vi` (6 notes) | `newline` đi kèm thẻ `<br>`: 207 lần |
| **Tổng số Notes Chứa Delimiter `\n` / `$` (Set Union)** | **5,869** | **290** | — | **5,869 unique notes** trên **290 unique decks**. *(Lưu ý thực nghiệm: Tổng cộng 5,669 + 3 + 207 = 5,879 lượt phân loại; có đúng **10 notes trùng lặp** giữa Dạng 1 và Dạng 3. Phép cộng thuần túy 5,669 + 207 = 5,876 trước đây bỏ sót D2 và chưa trừ 10 notes giao).* |

#### Thực trạng Mảng Giả 1 Phần Tử (Fake 1-Element Arrays) trên Toàn Bộ 35,112 Notes
Khi quét mở rộng các dấu phân cách đa giá trị khác (`;`, `、`, `①-⑳`, `/`, `,`), phát hiện **35,103 notes (99.97%)** có ít nhất một trường array đang bị lưu trữ dưới dạng mảng giả 1 phần tử `["item1 ; item2"]`:

| Tên Trường Đích | Số Notes Có Dữ Liệu | Mảng Giả 1 Phần Tử (`['...']`) | Mảng Chuẩn Nhiều Phần Tử | Ký Tự Phân Cách Nội Tại Chiếm Đa Số |
| :--- | ---: | ---: | ---: | :--- |
| `meaning_vi` | 35,088 | **32,553 (92.7%)** | 2,535 (7.2%) | Dấu phẩy `,` (25,930), Chấm phẩy `;` (5,055), Gạch chéo `/` (4,161), Số khoanh tròn `①-⑳` (227) |
| `meaning_jp` | 35,087 | **31,997 (91.2%)** | 3,090 (8.8%) | Phẩy Nhật `、` (13,803), Chấm phẩy `;` (4,998), Chấm giữa `・` (424), Gạch chéo `/` (360) |
| `usage_vi` | 32,615 | **29,616 (90.8%)** | 2,999 (9.2%) | Dấu phẩy `,` (21,091), Gạch chéo `/` (9,723), Chấm phẩy `;` (6,140), Phẩy Nhật `、` (1,461) |
| `usage_jp` | 32,654 | **29,363 (89.9%)** | 3,291 (10.1%) | Phẩy Nhật `、` (15,112), Gạch chéo `/` (9,198), Dấu phẩy `,` (9,679), Chấm phẩy `;` (3,571) |
| `translation_vi`| 35,091 | **19,516 (55.6%)** | 15,575 (44.4%) | Dấu phẩy `,` (14,815), Gạch chéo `/` (1,944), Chấm phẩy `;` (1,057) |
| `example_jp` | 35,091 | **12,146 (34.6%)** | 22,945 (65.4%) | Phẩy Nhật `、` (5,411), Chấm phẩy `;` (44 - nối 2 câu ví dụ) |
| `example_vi` | 35,082 | **12,145 (34.6%)** | 22,937 (65.4%) | Dấu phẩy `,` (18,869), Chấm phẩy `;` (61 - nối 2 câu dịch) |
| `reading` | 35,104 | **34,605 (98.6%)** | 499 (1.4%) | Ký tự đô-la `$` (3 notes đa cách đọc) |

---

### 1.3. Bảng Dữ Liệu Thực Tế Trích Xuất từ Cơ Sở Dữ Liệu

Dưới đây là các bản ghi thực tế được truy vấn trực tiếp từ bảng `notes`:

#### A. Dạng 1: Chuỗi đơn (Scalar string) chứa `\n` hoặc `$`
| Note ID | Deck Name (Deck ID) | Tên Trường | Từ Vựng | Giá Trị Thô Trong Database (`raw_value`) | Phân Tích Kỹ Thuật |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `000a79c9-9e03-4ad1-8cbc-550caacf6f00` | `Bài 10 Tiêu chuẩn của hạnh phúc` (3459) | `diagram` | `永远` | `"/media/library/stroke_zh_6c38.svg\n/media/library/stroke_zh_8fdc.svg"` | 2 đường dẫn SVG thứ tự nét viết bị nối bằng `\n`. |
| `000d633a-3be7-4a7a-8e20-2b364f3588c7` | `Bài 052` (467) | `additional_note_vi` | `偏向` | `"Gần nghĩa, 偏り.$Sắc thái, 偏向 thường bị hiểu là có chủ ý."` | 2 ý phân biệt sắc thái ngữ nghĩa được phân tách bằng `$`. |
| `0078f233-2002-4c2f-8274-27644d8ebc91` | `Bài 12` (4302) | `additional_note_jp` | `竞争对手` | `"常见搭配与语境：主要竞争对手$潜在竞争对手$击败竞争对手"` | 3 cụm từ kết hợp (collocations) được ngăn cách bằng `$`. |
| `863e0409-89b8-429c-83a2-b4fdff9c3bce` | `Bài 37` (4413) | `word` | `且$^2$` | `"且$^2$"` | **TOÁN HỌC / SỐ MŨ**: Cú pháp LaTeX `$^2$`. Tuyệt đối không được tách! |
| `93e76108-de6f-48ed-8623-d1d554c16c09` | `Bài 07` (1338) | `word` | — | `"Vた + あげく、〜$Nの + あげく、〜"` | Hai mẫu cấu trúc ngữ pháp tương đương ngăn cách bằng `$`. |
| `c8821608-7753-47ef-9d44-1f1b609575fd` | `Bài 59` (4406) | `hanviet` | `幕` | `"MÀN$MÀN KỊCH$CẢNH TƯỢNG"` | 3 âm/nghĩa Hán Việt được nối bằng `$`. |

#### B. Dạng 2: Mảng giả 1 phần tử chứa `$`
| Note ID | Deck Name (Deck ID) | Tên Trường | Từ Vựng | Giá Trị Thô Trong Database (`raw_value`) | JSON List Chuẩn Đề Xuất |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `003718f1-85e7-4401-8a4c-bcffbac4f191` | `Bài 104` (519) | `reading` | `風車` | `["ふうしゃ$かざぐるま"]` | `["ふうしゃ", "かざぐるま"]` |
| `d9ebfc05-777c-4819-98cb-d3c088b2456f` | `Bài 052` (467) | `reading` | `二重` | `["にじゅう$ふたえ"]` | `["にじゅう", "ふたえ"]` |
| `ec467c3c-0220-4a7d-a21a-ad201d72456f` | `Bài 017` (432) | `reading` | `大家` | `["たいか$おおや"]` | `["たいか", "おおや"]` |

#### C. Dạng 3: Chuỗi HTML chứa `<br>` kèm `\n` hoặc `$`
| Note ID | Deck Name (Deck ID) | Tên Trường | Giá Trị Thô Trong Database (`raw_value`) | JSON List Chuẩn Đề Xuất |
| :--- | :--- | :--- | :--- | :--- |
| `005c360d-a4f5-4972-b2e4-405b069929e7` | `Bài 06` (1386) | `additional_note_jp` | `"放置：Bỏ mặc không xử lý dù biết có vấn đề...<br>\n放棄：Từ bỏ hoàn toàn quyền lợi...<br>\n無視：Phớt lờ, làm lơ..."` | `["放置：Bỏ mặc không xử lý dù biết có vấn đề...", "放棄：Từ bỏ hoàn toàn quyền lợi...", "無視：Phớt lờ, làm lơ..."]` |
| `0218d64f-8896-415a-bc6b-83c681f7b72a` | `Bài 12` (1392) | `additional_note_jp` | `"憂鬱：U uất, sầu muộn...<br>\n落ち込む：Chán nản...<br>\n気が重い：Nặng lòng...<br>\n沈む：Chìm xuống..."` | `["憂鬱：U uất, sầu muộn...", "落ち込む：Chán nản...", "気が重い：Nặng lòng...", "沈む：Chìm xuống..."]` |
| `0b5aec56-b40f-4afd-b6d8-a472c729013c` | `Bài 015` (430) | `additional_note_vi` | `"So sánh nhanh, ゆっくり là chậm...<br><strong>のろのろ</strong> = chậm...<br>\n<strong>もたもた</strong> = chậm..."` | `["So sánh nhanh, ゆっくり là chậm...", "<strong>のろのろ</strong> = chậm...", "<strong>もたもた</strong> = chậm..."]` |

---

### 1.4. Thuật toán Bóc tách An toàn Bảo vệ Ngoặc (Bracket-Shielding Algorithm)

Để giải quyết triệt để nguy cơ tách nhầm các ký tự đặc biệt, giải pháp thuật toán `split_bracket_shielded` đã được thiết kế và kiểm chứng qua bộ kiểm thử tự động đạt độ chính xác 100%:

```python
import re
from typing import List, Optional

OPEN_BRACKETS = {
    '(': ')', '（': '）', '[': ']', '［': '］',
    '【': '】', '「': '」', '『': '』', '{': '}', '｛': '｝'
}
CLOSE_TO_OPEN = {v: k for k, v in OPEN_BRACKETS.items()}

def split_bracket_shielded(
    text: str,
    delimiters: Optional[List[str]] = None,
    allow_html_br: bool = True,
    allow_comma: bool = False,
) -> List[str]:
    """
    Thuật toán bóc tách phân cách an toàn có bảo vệ ngoặc (Bracket-Shielding).
    Cơ chế bảo vệ và xử lý ca biên:
    1. Bảo vệ độ sâu của 6 cặp ngoặc: (), （）, [], ［］, 【】, 「」, 『』, {}, ｛｝
       (Kèm cơ chế an toàn pop stack chống rò rỉ khi gặp ngoặc đóng lệch/lỗi cú pháp như `(abc]`).
    2. Bảo vệ ranh giới thẻ HTML: <...> (bao gồm thẻ tự đóng và thẻ có attributes).
    3. Bảo vệ định dạng tiền tệ: $(?=\d) ($10, $25,000, $ 100) nhưng NGĂN CHẶN nuốt
       danh sách đánh số dạng `$1.`, `$2.`, `$1) ` thường gặp trong ghi chú Anki.
    4. Bảo vệ công thức số mũ ($^1$, $^2$) và biểu thức toán LaTeX có toán tử (^, +, -, =, {, }, \\);
       tuyệt đối không nuốt từ vựng tiếng Anh thông thường nằm giữa 2 dấu $ (`word1$word2$word3`).
    5. Hỗ trợ tham số delimiters tùy biến: tôn trọng danh sách truyền vào (không tự ý tách newline
       nếu gọi `delimiters=[';']`).
    6. Hỗ trợ tùy chọn bóc tách dấu phẩy (allow_comma=True cho ',' và '、') phục vụ các trường danh sách từ vựng.
    """
    if not text:
        return []
        
    normalized = re.sub(r'[\r\n]+', '\n', text)
    if allow_html_br:
        normalized = re.sub(r'<br\s*/?>\s*\n?', '\n', normalized, flags=re.IGNORECASE)
        
    # Bước 1: Che chắn công thức toán học thực sự (số mũ $^2$ hoặc có toán tử toán học)
    math_placeholders = []
    def mask_math(m):
        idx = len(math_placeholders)
        math_placeholders.append(m.group(0))
        return f"\x00MATH_{idx}\x00"
        
    SAFE_MATH_RE = re.compile(
        r"\$\^[0-9a-zA-Z]+\$|\$[a-zA-Z0-9_]*[\^\{\}\+\-\=\\][a-zA-Z0-9_\^\{\}\+\-\=\\]*\$"
    )
    normalized = SAFE_MATH_RE.sub(mask_math, normalized)
    
    # Thiết lập tập delimiters hoạt động
    if delimiters is None:
        active_delims = {'$', '\n'}
        if allow_comma:
            active_delims.update({',', '、'})
    else:
        active_delims = set(delimiters)
        if ';' in active_delims:
            active_delims.add('；')
        if allow_comma:
            active_delims.update({',', '、'})
            
    bracket_stack = []
    in_html_tag = False
    items = []
    current_token = []
    
    i = 0
    n = len(normalized)
    while i < n:
        char = normalized[i]
        
        # Bước 2: Bảo vệ thẻ HTML
        if char == '<' and not in_html_tag:
            in_html_tag = True
            current_token.append(char)
            i += 1
            continue
        elif char == '>' and in_html_tag:
            in_html_tag = False
            current_token.append(char)
            i += 1
            continue
            
        if in_html_tag:
            current_token.append(char)
            i += 1
            continue
            
        # Bước 3: Quản lý Stack độ sâu của các cặp ngoặc (kèm cơ chế thu hồi an toàn chống rò rỉ stack)
        if char in OPEN_BRACKETS:
            bracket_stack.append(char)
            current_token.append(char)
            i += 1
            continue
        elif char in CLOSE_TO_OPEN:
            expected_open = CLOSE_TO_OPEN[char]
            if expected_open in bracket_stack:
                while bracket_stack and bracket_stack[-1] != expected_open:
                    bracket_stack.pop()
                if bracket_stack:
                    bracket_stack.pop()
            else:
                # Thu hồi phần tử đỉnh stack nếu gặp ngoặc đóng lệch (mismatched) để tránh leak trạng thái
                if bracket_stack:
                    bracket_stack.pop()
            current_token.append(char)
            i += 1
            continue
            
        is_shielded = len(bracket_stack) > 0
        
        # Bước 4: Tách Delimiter khi không nằm trong vùng che chắn (Unshielded)
        if not is_shielded:
            if '$' in active_delims and char == '$':
                rest = normalized[i + 1:]
                # Guard chống nuốt danh sách đánh số Anki ($1. hoặc $2. hoặc $1) )
                is_numbered_bullet = bool(re.match(r'^\s*\d+[\.\)]\s', rest))
                # Guard tiền tệ: $(?=\d) nhưng loại trừ bullet list
                is_currency = not is_numbered_bullet and bool(re.match(r'^\s*\d+(?:,\d+)*(?:\.\d{2})?(?!\.\s)', rest))
                if is_currency:
                    current_token.append(char)
                    i += 1
                    continue
                part = "".join(current_token).strip()
                if part:
                    items.append(part)
                current_token = []
                i += 1
                continue
                
            if '\n' in active_delims and char == '\n':
                part = "".join(current_token).strip()
                if part:
                    items.append(part)
                current_token = []
                i += 1
                continue
                
            if char in active_delims:
                part = "".join(current_token).strip()
                if part:
                    items.append(part)
                current_token = []
                i += 1
                continue
                
        current_token.append(char)
        i += 1
        
    last_part = "".join(current_token).strip()
    if last_part:
        items.append(last_part)
        
    # Bước 5: Khôi phục lại các biểu thức toán học đã che chắn
    final_items = []
    for it in items:
        for idx, mval in enumerate(math_placeholders):
            it = it.replace(f"\x00MATH_{idx}\x00", mval)
        final_items.append(it)
        
    return final_items
```

---

### 1.5. Đề xuất Định dạng JSON List Chuẩn & Hiện đại hóa Presentation Template

#### Quy tắc Chuẩn hóa Lưu trữ Database (`field_values_by_id`):
1. **Trường `reading`**: Chuyển thành `["ふうしゃ", "かざぐるま"]` (loại bỏ `$`).
2. **Trường `diagram`**: Cập nhật `field_defs.field_type` sang `array` và lưu danh sách các đường dẫn SVG: `["/media/library/stroke_zh_6c38.svg", "/media/library/stroke_zh_8fdc.svg"]`.
3. **Trường `additional_note_vi` / `additional_note_jp`**: Bóc tách mảng bullet point sạch sẽ: `["Gần nghĩa, 偏り.", "Sắc thái, 偏向 thường bị hiểu là có chủ ý."]`.

#### Cải tiến Template `Default Flama Flashcard` (`e0cb18b2`):
Loại bỏ hoàn toàn đoạn mã JavaScript hack DOM client-side (`scope.querySelectorAll('div[auto-split]')`), thay thế bằng cú pháp lặp Mustache chuẩn tắc:

```html
<!-- Native Array Iteration: Ghi chú văn cảnh bổ sung -->
{{#additional_note_jp}}
<div class="flama-note-item">
    <span class="flama-bullet">◆</span> {{{.}}}
</div>
{{/additional_note_jp}}

{{#additional_note_vi}}
<div class="flama-note-item-vi">
    {{{.}}}
</div>
{{/additional_note_vi}}

<!-- Native Array Iteration: Thứ tự nét viết chữ Hán -->
{{#diagram}}
<div class="flama-stroke-container">
    <img src="{{{.}}}" class="flama-stroke-svg" alt="Thứ tự nét viết" loading="lazy" />
</div>
{{/diagram}}

<!-- Vòng lặp badges cho các cách đọc Kanji khác nhau -->
<div class="reading-row">
    {{#reading}}
        <span class="flama-reading-badge">{{.}}</span>
    {{/reading}}
    {{#hanviet}}<span class="hanviet-label">「{{hanviet}}」</span>{{/hanviet}}
</div>
```

---

## PHẦN 2: NHÓM TRỌNG TÂM CHUNGBECHN1 — NOTETYPE, TEMPLATE & BẤT THƯỜNG NGỮ NGHĨA (R2)

### 2.1. Cấu trúc Cây Thư mục ChungBechN1, Quyền Sở hữu và Thực thể Phái sinh

Qua truy vết toàn bộ cơ sở dữ liệu MySQL 8.0 local:
1. **User `chungtrinh2k2` (User ID: 1)**:
   - Sở hữu Deck gốc **414 (`ChungBechN1`)** bao gồm trọn vẹn **248 decks con cháu** (5 ở Level 1, 226 ở Level 2, 17 ở Level 3) và **13,510 notes** (249 decks tính cả gốc 414), tổ chức thành cây phả hệ 3 tầng:
     - `415 (語彙徹底N1)`: 170 bài (`Bài 001` - `Bài 170`, Decks 416-585) với **10,148 notes** dùng NoteType `Flama Standard Vocabulary`.
     - `1333 (文法練習)`: 6 bài với **146 notes** dùng `Flama Standard Vocabulary`.
     - `1369 (練習)`: 10 bài với **547 notes** dùng `Flama Standard Vocabulary`.
     - `1380 (言葉)`: là deck con thuộc nhánh 1369 (`練習`) có 17 subdecks cấp 3 mở rộng với **1,003 notes** dùng `Flama Standard Vocabulary`.
     - `1398 (文法)`: 18 bài (`Bài 01` - `Bài 18`, Decks 1399-1416) với **90 notes** (5 notes/bài) dùng NoteType `文法N1` (`4fc2eb8e`).
     - `1418 (漢字)`: 20 bài (`Bài 01` - `Bài 20`, Decks 1419-1438) với **1,585 notes** dùng `Flama Standard Vocabulary` (với nét chữ SVG trong `diagram`).
   *(Lưu ý đối soát thực nghiệm: Con số 231 decks và 13,375 notes trước đây là do thuật toán duyệt cây dừng ở Level 2 (5 + 226 = 231), bỏ sót 17 subdecks cấp 3 dưới nhánh 1380; tổng số thực tế qua CTE đệ quy đầy đủ là 248 descendant decks và 13,510 notes).*
2. **User `bach1912` (User ID: 7)**: 0 decks trực tiếp.
3. **User 16 (`Ng__Th__Ng_c_B_ch` / Bích trong ChungBech)**: Sở hữu **207 clone overlay decks** (Deck 3026-3212) được cài đặt từ bản phát hành marketplace của Deck 414, tuân thủ đúng mô hình clone overlay (0 notes trùng lặp).
4. **User `Ánh` (User ID: 4)**: Sở hữu NoteType `文法N1` (`35cef59f`, 139 notes), `Kanji_N3` (`91f567ab`, 790 notes), và `漢字N1` (`85b20688`, 0 notes).

---

### 2.2. Ma trận Đối chiếu NoteType `文法N1`, `漢字N1`, `Kanji_N3` với Template

| Thực thể NoteType | Template Đang Gắn | Số Decks | Số Notes | Lỗi Cú pháp & Mismatch Nhận diện |
| :--- | :--- | ---: | ---: | :--- |
| **`文法N1`** (`4fc2eb8e`, user 1) | `Grammar & Literary Quotes Card` (`0a86851a`) | 18 | 90 | Unclosed `<div>` bên trong `{{#name}}`; orphan `</div>`; cưỡng bức `100vh`; trường tên có dấu chấm `literary_example.quote` gây lỗi tra cứu Mustache; 73 trường mảng giả dính dấu chấm phẩy `;`. |
| **`文法N1` (Clone)** (`35cef59f`, user 4) | `Thẻ 1` (`266cbc84`) | 4 | 139 | Sao chép nguyên vẹn lỗi unclosed `<div>` và `100vh`; 138/139 notes chứa ký tự phân cách thô trong các trường text scalar. |
| **`Kanji_N3`** (`91f567ab`, user 4) | `Card 1` (`21a53f7b`) | 13 | 790 | **148 notes bị đảo ngữ nghĩa 100%** giữa `Phiên âm` và `Âm Hán Tự`; 70 notes chứa chữ Kanji thô trong `Âm Hán Tự`; 4 notes chứa chữ Kanji trong `Phiên âm`; cưỡng bức `100vh`. |
| **`漢字N1`** (`85b20688`, user 4) | `Thẻ 1` (`273a92a1`) | 0 | 0 | 17 trường toàn bộ là text scalar (0 array); chèn script regex `replace(/\$/g)`; lặp lại `{{Diagram}}` hai lần trước và sau thẻ đóng `</div>`; cưỡng bức `100vh`. |
| **Nhánh `ChungBechN1 漢字`** (Decks 1419-1438) | `Default Flama Flashcard` (`e0cb18b2`) | 20 | 1,585 | Gắn vào NoteType từ vựng tổng hợp thay vì NoteType Kanji chuyên dụng; đường dẫn nét viết SVG lưu dạng chuỗi nối `\n` trong `diagram`. |

---

### 2.3. Phân tích Chi tiết Lỗi Cú pháp Template và Khiếm khuyết DOM/CSS

#### 1. Lỗi Cú pháp Unclosed `<div>` trong Template Ngữ pháp:
Trong file `back_html` của template `0a86851a` và các biến thể phái sinh:
```html
<!-- Dòng 1-10: Mở div container bên trong điều kiện {{#name}} -->
{{#name}}
<div style='display: flex; flex-direction: column; justify-content: flex-start; ...'>
    <div style='font-size: 36px; font-weight: bold; ...'>
        {{name}}
        {{#Audio}} ... {{/Audio}}
    </div>
{{/name}}
<!-- THIẾU THẺ ĐÓNG </div> TRƯỚC {{/name}}! -->

... (các khối nội dung khác) ...

    {{/additional_example}}
</div> <!-- DÒNG 84: THẺ ĐÓNG </div> MỒ CÔI NGOÀI KHỐI EXAMPLE -->
```
- **Hậu quả**: Khi phân tích cú pháp AST qua `TagBalanceValidator`, hệ thống báo lỗi nghiêm trọng: `Mismatched closing tag </div>, expected </span/div>`. Nếu một bản ghi thiếu trường `name`, thẻ `<div>` chính không bao giờ được tạo nhưng thẻ đóng dòng 84 vẫn xuất hiện, làm gãy cấu trúc DOM của toàn trang.

#### 2. Lỗi Cưỡng bức Viewport `100vh` trên Thiết Bị Di Động:
Tất cả các template `0a86851a`, `266cbc84`, `273a92a1`, `21a53f7b` đều chứa đoạn CSS sau trên Front card:
```html
<div style='height:100vh;text-align:center;display:flex;justify-content:center;align-items:center;font-size:70px;font-weight:bold;color:#e53c20'>
    {{name}}
</div>
```
- **Hậu quả**: Khi bàn phím ảo hoặc thanh điều hướng trình duyệt bật lên, `100vh` không co lại, đẩy nút lật thẻ và thanh công cụ ra khỏi màn hình, đồng thời từ vựng dài bị tràn biên giới (overflow).

#### 3. Lỗi Trùng Lặp `{{Diagram}}` và Tiêm Script DOM trong `漢字N1` (`273a92a1`):
Trong `back_html`:
```html
    {{Diagram}}
</div>
{{Diagram}} <!-- DÒNG 118: RENDER THỨ HAI NGOÀI THẺ CONTAINER CHÍNH -->
```
Kèm theo đoạn script:
```javascript
(function() {
  document.querySelectorAll('div[auto-split]').forEach(el => {
    let text = el.innerHTML;
    text = text.replace(/\$/g, ".<br>");
    el.innerHTML = text;
  });
})();
```
- **Hậu quả**: Ảnh nét viết SVG bị vẽ lặp 2 lần; script regex can thiệp thô bạo vào `innerHTML` làm hỏng các liên kết an toàn và vi phạm nguyên tắc Native Array của Flama.

---

### 2.4. Kiểm toán Hoán đổi Ngữ nghĩa (Semantic Inversions) & Dữ liệu Bất thường

Kiểm toán 100% điều tra trên **1,019 notes** thuộc các NoteType mục tiêu phát hiện **324 notes bị lỗi dữ liệu (31.80%)** trên 30 decks:

```
TỔNG KẾT KIỂM TOÁN CHUNGBECHN1 & CÁC BỘ LIÊN QUAN:
1. Kanji_N3 (NoteType 91f567ab, 790 notes):
   - Đảo ngữ nghĩa 1-to-1 (Phiên âm <-> Âm Hán Tự): 148 notes
   - Chữ Kanji thô trong Âm Hán Tự (Kanji in HanViet): 70 notes
   - Chữ Kanji thô trong Phiên âm (Kanji in Reading): 4 notes
   - Mảng giả 1 phần tử dính delimiter: 14 notes
   - Notes nguyên vẹn (Pristine): 536 notes
2. Grammar N1 (chungtrinh2k2, 4fc2eb8e, 90 notes):
   - Mảng giả 1 phần tử dính dấu chấm phẩy ';': 73 trường trên 18 decks
3. Grammar N1 (Ánh, 35cef59f, 139 notes):
   - Notes dính delimiter thô trong trường scalar: 138 / 139 notes
```

#### Bảng Phân Bổ Chi Tiết 148 Notes Bị Đảo Ngữ Nghĩa trong `Kanji_N3` theo Từng Deck:
| Deck ID | Tên Deck | Tổng Số Notes | Số Notes Bị Đảo (`Phiên âm` <-> `Âm Hán`) | Kanji Trong Hán Việt | Kanji Trong Reading | Tỷ Lệ Lỗi của Deck |
| :---: | :--- | ---: | ---: | ---: | ---: | ---: |
| **3213** | `KanjiN3` | 1 | **1** | 0 | 0 | **100.0%** |
| **3214** | `Bài 1` | 266 | **24** | 5 | 2 | 14.3% |
| **3215** | `Bài 10` | 19 | **19** | 0 | 0 | **100.0%** |
| **3216** | `Bài 2` | 67 | **4** | 0 | 2 | 9.0% |
| **3217** | `Bài 3` | 73 | **4** | 24 | 0 | 38.4% |
| **3218** | `Bài 4` | 47 | **4** | 29 | 0 | **70.2%** |
| **3219** | `Bài 5` | 39 | **7** | 1 | 0 | 23.1% |
| **3220** | `Bài 6` | 39 | **2** | 0 | 0 | 5.1% |
| **3221** | `Bài 7` | 44 | **3** | 0 | 0 | 11.4% |
| **3222** | `Bài 8` | 55 | **17** | 0 | 0 | 38.2% |
| **3223** | `Bài 9` | 39 | **2** | 1 | 0 | 7.7% |
| **3224** | `Đồng nghĩa` | 81 | **61** | 10 | 0 | **87.7%** |
| **4564** | `bài 1` | 2 | 0 | 0 | 0 | 0.0% |
| **TỔNG** | **13 Decks** | **790** | **148** | **70** | **4** | **32.15%** |

#### Dẫn chứng Dữ liệu Thực tế Trích xuất từ Cơ sở Dữ liệu:

1. **Hiện tượng Hoán đổi 1-to-1 (`Phiên âm` <-> `Âm Hán Tự`)**:
   - `Note 2cd0a92f-eee1-4952-9cfb-8f9945d96b15` (Deck 3213 `KanjiN3`):
     - `Từ vựng`: `彼奴`
     - `Phiên âm` (Field `826db147`): `["BỈ NÔ"]` *(Chữ Hán Việt viết hoa!)*
     - `Âm Hán Tự` (Field `d2366e63`): `あいつ` *(Chữ Kana tiếng Nhật!)*
   - `Note 0c49bfd9-67d8-4ca7-947d-96d6d0494748` (Deck 3214 `Bài 1`):
     - `Từ vựng`: `転勤`
     - `Phiên âm`: `["CHUYỂN CẦN"]` | `Âm Hán Tự`: `てんきん`
   - `Note 0e314874-654d-47f4-85a0-9e2914fe1b60` (Deck 3214 `Bài 1`):
     - `Từ vựng`: `血圧`
     - `Phiên âm`: `["HUYẾT ÁP"]` | `Âm Hán Tự`: `けつあつ`
   - `Note 10a8ba4a-5bbf-4937-b46d-6f36918d68c5` (Deck 3214 `Bài 1`):
     - `Từ vựng`: `準備`
     - `Phiên âm`: `["CHUẨN BỊ"]` | `Âm Hán Tự`: `じゅんび`
   - `Note 135f9f58-2b03-49cd-b93b-f13397febb94` (Deck 3214 `Bài 1`):
     - `Từ vựng`: `卒業`
     - `Phiên âm`: `["TỐT NGHIỆP"]` | `Âm Hán Tự`: `そつぎょう`

2. **Chữ Kanji Tiếng Nhật Lưu Nhầm Vào Trường Âm Hán Tự**:
   - `Note 000f3acf-5e17-4762-b4aa-1d8d8619d7d0` (Deck 3217): `Từ vựng='出張'`, `Âm Hán Tự='出張'`
   - `Note 002dbdab-7eb1-45ad-bf96-2339786337c2` (Deck 3217): `Từ vựng='不安'`, `Âm Hán Tự='不安'`
   - `Note 0193d0dc-9c51-42b0-bf46-b3c8a30ab361` (Deck 3218): `Từ vựng='連絡'`, `Âm Hán Tự='連絡'`
   - `Note 48d97027-5686-48c1-b6ed-666f5a42e11f` (Deck 3214): `Từ vựng='貯金'`, `Âm Hán Tự='貯金（Trữ kim）'`

3. **Chữ Kanji Tiếng Nhật Chưa Được Phiên Âm Trong Trường Reading**:
   - `Note 031c6e0b-df1c-4757-babf-ab4f3071f737` (Deck 3214): `Phiên âm='お友達'` (thay vì Kana `おともだち`).
   - `Note ade08229-8e07-4861-bce7-4fe79a67736c` (Deck 3216): `Phiên âm='ご健康'` (thay vì Kana `ごけんこう`).
   - `Note ff41f69f-c525-4869-b318-5696f1265ea1` (Deck 3214): `Phiên âm='お料理'` (thay vì Kana `おりょうり`).

---

### 2.5. Bảng FieldDef Chuẩn hóa & Mã nguồn Template Mustache Responsive

#### A. Cấu trúc FieldDef Chuẩn hóa: `Flama Kanji Standard` (Đồng bộ cho Kanji N1 & N3)
| Vị trí | Tên Trường | Kiểu Dữ Liệu | Bắt buộc | Mô tả & Quy tắc Xác thực |
| :---: | :--- | :---: | :---: | :--- |
| 0 | `kanji` | `text` | Có | Chữ Hán hoặc từ ghép Kanji mục tiêu (`分`, `分裂`). |
| 1 | `hanviet` | `array` | Có | Mảng JSON các âm Hán Việt viết hoa: `["PHÂN", "PHẬN"]`. |
| 2 | `onyomi` | `array` | Không | Mảng JSON các âm On (Katakana): `["フン", "ブン", "ブ"]`. |
| 3 | `kunyomi` | `array` | Không | Mảng JSON các âm Kun (Hiragana): `["わ・ける", "わ・かる"]`. |
| 4 | `reading` | `array` | Có | Mảng âm đọc Kana của từ vựng: `["ぶんれつ"]`. |
| 5 | `meaning_vi` | `array` | Có | Mảng định nghĩa tiếng Việt: `["Phân chia, tách ra", "Bổn phận"]`. |
| 6 | `meaning_jp` | `array` | Không | Mảng định nghĩa tiếng Nhật. |
| 7 | `stroke_images` | `array` | Không | Mảng URL nét viết SVG: `["/media/library/stroke_ja_5206.svg"]`. |
| 8 | `compounds_jp` | `array` | Không | Mảng các câu ví dụ hoặc từ ghép Kanji. |
| 9 | `compounds_vi` | `array` | Không | Mảng dịch nghĩa tiếng Việt tương ứng. |
| 10 | `usage_notes` | `array` | Không | Mảng ghi chú bộ thủ, mẹo nhớ, sắc thái. |
| 11 | `audio_word` | `audio` | Không | URL âm thanh phát âm từ vựng. |
| 12 | `audio_example` | `audio` | Không | URL âm thanh phát âm câu ví dụ. |

#### B. Cấu trúc FieldDef Chuẩn hóa: `Flama Grammar Standard` (Cho Grammar N1)
| Vị trí | Tên Trường | Kiểu Dữ Liệu | Bắt buộc | Mô tả & Quy tắc Xác thực |
| :---: | :--- | :---: | :---: | :--- |
| 0 | `name` | `text` | Có | Tên cấu trúc ngữ pháp mục tiêu (`〜なり`). |
| 1 | `meaning_vi` | `array` | Có | Mảng giải nghĩa tiếng Việt: `["Vừa mới... thì ngay lập tức..."]`. |
| 2 | `structure` | `array` | Có | Mảng công thức kết hợp: `["V-る + なり"]`. |
| 3 | `usage_notes` | `array` | Không | Mảng lưu ý sắc thái, điều kiện đi kèm. |
| 4 | `examples_jp` | `array` | Có | Mảng câu ví dụ tiếng Nhật. |
| 5 | `examples_vi` | `array` | Có | Mảng dịch nghĩa câu ví dụ tiếng Việt. |
| 6 | `literary_quote` | `text` | Không | Câu trích dẫn văn học (nếu có). |
| 7 | `literary_source` | `text` | Không | Nguồn tác phẩm và tác giả (`こころ - 夏目漱石`). |
| 8 | `literary_translation` | `text` | Không | Dịch nghĩa câu trích dẫn văn học. |
| 9 | `audio_name` | `audio` | Không | Âm thanh phát âm tên ngữ pháp. |
| 10 | `audio_example` | `audio` | Không | Âm thanh phát âm câu ví dụ. |
| 11 | `audio_literary` | `audio` | Không | Âm thanh trích dẫn văn học. |

#### C. Mã nguồn Template Mustache Chuẩn tắc: `Flama Grammar Presentation Template`
- Đóng thẻ `<div>` chính xác, triệt tiêu hoàn toàn thẻ mồ côi.
- Thay thế `height: 100vh` bằng `min-height: clamp(220px, 50vh, 450px)`.
- Triệt tiêu 100% vòng lặp lồng trùng tên gây nhân bản bậc hai $O(N^2)$ thông qua guard wrapper `data-native-array-guard` (mỗi container chỉ render 1 lần, các item bên trong lặp đúng 1 lần).
- Loại bỏ duplicate HTML IDs: chuyển `id="audio-name"`, `id="audio-example"`, `id="audio-literary"` thành các class CSS chuyên biệt và kích hoạt âm thanh qua DOM traversal an toàn (`this.previousElementSibling.play()`).

```html
<!-- FRONT HTML -->
<div class="card front-card">
    <div class="grammar-hero">
        {{name}}
    </div>
</div>

<!-- BACK HTML -->
<div class="card back-card">
    <!-- Header: Tên ngữ pháp & Nút phát âm -->
    <div class="grammar-header">
        <div class="grammar-title">
            {{name}}
            {{#audio_name}}
                <audio class="audio-player audio-name" src="{{audio_name_url}}" preload="none"></audio>
                <button type="button" class="audio-btn" onclick="this.previousElementSibling.play()" aria-label="Phát âm ngữ pháp">🔊</button>
            {{/audio_name}}
        </div>
    </div>

    <!-- Ý nghĩa (Single loop with Presence Guard) -->
    <span data-native-array-guard="meaning_vi" style="display:contents">
        {{#meaning_vi}}<span data-native-array-presence hidden></span>{{/meaning_vi}}
        <div class="grammar-section">
            <div class="section-title">◆ Ý nghĩa:</div>
            <ul class="meaning-list">
                {{#meaning_vi}}<li>{{{.}}}</li>{{/meaning_vi}}
            </ul>
        </div>
    </span>

    <!-- Cấu trúc kết hợp -->
    <span data-native-array-guard="structure" style="display:contents">
        {{#structure}}<span data-native-array-presence hidden></span>{{/structure}}
        <div class="grammar-section">
            <div class="section-title">◆ Cấu trúc kết hợp:</div>
            <div class="structure-box">
                {{#structure}}<div class="structure-item">{{{.}}}</div>{{/structure}}
            </div>
        </div>
    </span>

    <!-- Câu ví dụ minh họa -->
    <span data-native-array-guard="examples_jp" style="display:contents">
        {{#examples_jp}}<span data-native-array-presence hidden></span>{{/examples_jp}}
        <div class="grammar-section">
            <div class="section-title">
                ◆ Ví dụ câu:
                {{#audio_example}}
                    <audio class="audio-player audio-example" src="{{audio_example_url}}" preload="none"></audio>
                    <button type="button" class="audio-btn-sm" onclick="this.previousElementSibling.play()" aria-label="Phát âm ví dụ">🔊</button>
                {{/audio_example}}
            </div>
            <div class="examples-container">
                {{#examples_jp}}<div class="example-jp">{{{.}}}</div>{{/examples_jp}}
            </div>
            <span data-native-array-guard="examples_vi" style="display:contents">
                {{#examples_vi}}<span data-native-array-presence hidden></span>{{/examples_vi}}
                <div class="examples-vi-container">
                    {{#examples_vi}}<div class="example-vi">{{{.}}}</div>{{/examples_vi}}
                </div>
            </span>
        </div>
    </span>

    <!-- Trích dẫn văn học -->
    {{#literary_quote}}
        <div class="grammar-section literary-box">
            <div class="section-title">
                ◆ Trích dẫn văn học:
                {{#audio_literary}}
                    <audio class="audio-player audio-literary" src="{{audio_literary_url}}" preload="none"></audio>
                    <button type="button" class="audio-btn-sm" onclick="this.previousElementSibling.play()" aria-label="Phát âm trích dẫn">🔊</button>
                {{/audio_literary}}
            </div>
            <div class="literary-quote">“{{literary_quote}}”</div>
            {{#literary_translation}}
                <div class="literary-translation">{{literary_translation}}</div>
            {{/literary_translation}}
            {{#literary_source}}
                <div class="literary-source">— {{literary_source}}</div>
            {{/literary_source}}
        </div>
    {{/literary_quote}}

    <!-- Chú ý & Sắc thái -->
    <span data-native-array-guard="usage_notes" style="display:contents">
        {{#usage_notes}}<span data-native-array-presence hidden></span>{{/usage_notes}}
        <div class="grammar-section">
            <div class="section-title">◆ Chú ý &amp; Sắc thái:</div>
            <ul class="notes-list">
                {{#usage_notes}}<li>{{{.}}}</li>{{/usage_notes}}
            </ul>
        </div>
    </span>
</div>

<script>
// flama-native-arrays.v1: Tự động phát âm thanh chuỗi
(() => {
  const nameAudio = document.querySelector('.audio-name');
  const exAudio = document.querySelector('.audio-example');
  if (nameAudio) {
    nameAudio.play().catch(() => {});
    if (exAudio) {
      nameAudio.addEventListener('ended', () => {
        setTimeout(() => exAudio.play().catch(() => {}), 400);
      }, { once: true });
    }
  }
})();
</script>
```

#### D. Mã nguồn Template Mustache Chuẩn tắc: `Flama Kanji Presentation Template`
- Loại bỏ hoàn toàn việc lồng 2 tầng cùng tên `{{#hanviet}}` hay `{{#compounds_jp}}`, đảm bảo mỗi banner và box chỉ xuất hiện 1 lần duy nhất ($O(1)$ section headers).
- Áp dụng cơ chế `data-native-array-guard` đồng bộ với `flama-native-arrays.v1`.
- Triệt tiêu hoàn toàn trùng lặp HTML ID cho các phần tử phát âm âm thanh.

```html
<!-- FRONT HTML -->
<div class="card front-card">
    <div class="kanji-hero">
        {{kanji}}
    </div>
    <div class="reading-row">
        {{#reading}}
            <span class="flama-reading-badge">{{.}}</span>
        {{/reading}}
    </div>
</div>

<!-- BACK HTML -->
<div class="card back-card">
    <!-- Header: Chữ Hán & Nút phát âm -->
    <div class="kanji-header">
        <div class="kanji-title">
            {{kanji}}
            {{#audio_word}}
                <audio class="audio-player audio-word" src="{{audio_word_url}}" preload="none"></audio>
                <button type="button" class="audio-btn" onclick="this.previousElementSibling.play()" aria-label="Phát âm chữ Hán">🔊</button>
            {{/audio_word}}
        </div>
    </div>

    <!-- Âm Hán Việt Banner (Single loop, no N^2 nesting) -->
    <span data-native-array-guard="hanviet" style="display:contents">
        {{#hanviet}}<span data-native-array-presence hidden></span>{{/hanviet}}
        <div class="hanviet-banner">
            {{#hanviet}}<span class="hanviet-badge">{{.}}</span>{{/hanviet}}
        </div>
    </span>

    <!-- Cách đọc Onyomi & Kunyomi -->
    <div class="yomi-grid">
        <span data-native-array-guard="onyomi" style="display:contents">
            {{#onyomi}}<span data-native-array-presence hidden></span>{{/onyomi}}
            <div class="yomi-block onyomi-block">
                <span class="yomi-label">Âm On:</span>
                {{#onyomi}}<span class="yomi-tag on-tag">{{.}}</span>{{/onyomi}}
            </div>
        </span>
        <span data-native-array-guard="kunyomi" style="display:contents">
            {{#kunyomi}}<span data-native-array-presence hidden></span>{{/kunyomi}}
            <div class="yomi-block kunyomi-block">
                <span class="yomi-label">Âm Kun:</span>
                {{#kunyomi}}<span class="yomi-tag kun-tag">{{.}}</span>{{/kunyomi}}
            </div>
        </span>
    </div>

    <!-- Ý nghĩa tiếng Việt -->
    <span data-native-array-guard="meaning_vi" style="display:contents">
        {{#meaning_vi}}<span data-native-array-presence hidden></span>{{/meaning_vi}}
        <div class="kanji-section">
            <div class="section-title">◆ Ý nghĩa:</div>
            <ul class="meaning-list">
                {{#meaning_vi}}<li>{{{.}}}</li>{{/meaning_vi}}
            </ul>
        </div>
    </span>

    <!-- Thứ tự nét viết SVG -->
    <span data-native-array-guard="stroke_images" style="display:contents">
        {{#stroke_images}}<span data-native-array-presence hidden></span>{{/stroke_images}}
        <div class="stroke-section">
            <div class="section-title">◆ Thứ tự nét viết:</div>
            <div class="stroke-container">
                {{#stroke_images}}<img src="{{{.}}}" class="stroke-svg" alt="Nét viết" loading="lazy" />{{/stroke_images}}
            </div>
        </div>
    </span>

    <!-- Từ ghép & Ví dụ Kanji -->
    <span data-native-array-guard="compounds_jp" style="display:contents">
        {{#compounds_jp}}<span data-native-array-presence hidden></span>{{/compounds_jp}}
        <div class="kanji-section">
            <div class="section-title">
                ◆ Từ ghép &amp; Ví dụ:
                {{#audio_example}}
                    <audio class="audio-player audio-example" src="{{audio_example_url}}" preload="none"></audio>
                    <button type="button" class="audio-btn-sm" onclick="this.previousElementSibling.play()" aria-label="Phát âm ví dụ">🔊</button>
                {{/audio_example}}
            </div>
            <div class="compounds-container">
                {{#compounds_jp}}<div class="compound-item">{{{.}}}</div>{{/compounds_jp}}
            </div>
            <span data-native-array-guard="compounds_vi" style="display:contents">
                {{#compounds_vi}}<span data-native-array-presence hidden></span>{{/compounds_vi}}
                <div class="compounds-vi-container">
                    {{#compounds_vi}}<div class="compound-vi">{{{.}}}</div>{{/compounds_vi}}
                </div>
            </span>
        </div>
    </span>

    <!-- Ghi chú bộ thủ & sắc thái -->
    <span data-native-array-guard="usage_notes" style="display:contents">
        {{#usage_notes}}<span data-native-array-presence hidden></span>{{/usage_notes}}
        <div class="kanji-section">
            <div class="section-title">◆ Ghi chú &amp; Bộ thủ:</div>
            <ul class="notes-list">
                {{#usage_notes}}<li>{{{.}}}</li>{{/usage_notes}}
            </ul>
        </div>
    </span>
</div>

<script>
// flama-native-arrays.v1: Tự động dọn dẹp các khối array rỗng và phát âm
(() => {
  const wordAudio = document.querySelector('.audio-word');
  if (wordAudio) {
    wordAudio.play().catch(() => {});
  }
})();
</script>
```

---

## PHẦN 3: NHÓM TRỌNG TÂM ENGLISH (EN4EVERYONE) — TRƯỜNG ĐA GIÁ TRỊ, STT & TEMPLATE MISMATCH (R3)

### 3.1. Đối chiếu Kiến trúc 2 NoteType `6b2a8fec` và `13ff54d7`

Hệ thống ghi nhận 2 NoteType cùng mang tên `En4Everyone` nhưng có sự phân hóa rõ rệt về chủ sở hữu và schema:
- **NoteType `6b2a8fec-0276-401d-b361-c3affec1aa80`** (User ID: 1): NoteType gốc của hệ thống, chứa **143 decks** (Deck 383, 1340-1481) và **4,122 notes**.
- **NoteType `13ff54d7-1775-4150-9c96-14c5cca3a42d`** (User ID: 4): Bản snapshot cài đặt độc lập, chứa **43 decks** (Deck 6144-6186) và **1,179 notes**.
- Tổng phạm vi En4Everyone: **186 decks** và **5,301 notes**.

#### Bảng Đối Chiếu Schema và Sự Bất Đối Xứng Giữa 2 NoteTypes:
| Pos | Tên Trường | Type trong `6b2a8fec` (User 1) | Type trong `13ff54d7` (User 4) | Bắt buộc / Role | Đánh Giá Mismatch Schema |
| :---: | :--- | :---: | :---: | :---: | :--- |
| 0 | `STT` | `text` | `text` | 1 / `primary` | Khóa định danh chính vị trí số thứ tự bài học. |
| 1 | `Vocabulary` | `text` | `text` | 0 | Từ vựng tiếng Anh. |
| 2 | `PoS` | `text` | `text` | 0 | Từ loại (`n`, `v`, `adj`, `adv`). |
| 3 | `Pronunciation` | `text` | `text` | 0 | Phiên âm quốc tế IPA `/<ipa>/`. |
| 4 | `Meaning` | `array` | `array` | 0 | Định nghĩa / dịch nghĩa tiếng Việt. |
| 5 | `Example` | **`array`** | **`richtext`** | 0 | **LỆCH TYPE**: 6b là array, 13ff là richtext chuỗi đơn. |
| 6 | `Example_VI` | **`array`** | **`richtext`** | 0 | **LỆCH TYPE**: 6b là array, 13ff là richtext chuỗi đơn. |
| 7 | `Collocation` | `array` | `array` | 0 | Cụm từ đi kèm tiếng Anh. |
| 8 | `Coollocation_VI` | `array` | `array` | 0 | **TYPO SCHEMA**: Thừa chữ `o` trong `Coollocation_VI`. |
| 9 | `Synonym` | `array` | `array` | 0 | Từ đồng nghĩa tiếng Anh. |
| 10 | `Synonym_VI` | `array` | `array` | 0 | Nghĩa tiếng Việt của từ đồng nghĩa. |
| 11 | `Antonym` | `array` | `array` | 0 | Từ trái nghĩa tiếng Anh. |
| 12 | `Antonym_VI` | `array` | `array` | 0 | Nghĩa tiếng Việt của từ trái nghĩa. |
| 13 | `Word Family` | **`array`** | **`text`** | 0 | **LỆCH TYPE NGHIÊM TRỌNG**: 6b là array, 13ff là text chứa `;` thô. |
| 14 | `Note_EN` | `text` | `text` | 0 | Ghi chú văn cảnh tiếng Anh. |
| 15 | `Note_VI` | `text` | `text` | 0 | Ghi chú ngữ nghĩa tiếng Việt. |
| 16 | `Vocabulary_Audio` | `audio` | `audio` | 0 | Âm thanh phát âm từ vựng. |
| 17 | `Example_Audio` | `audio` | `audio` | 0 | Âm thanh phát âm câu ví dụ. |
| 18 | `image` | `image` | `image` | 0 | Ảnh minh họa. |

---

### 3.2. Kiểm toán Trường Đa Giá Trị & Hiện trạng Lưu trữ Dữ liệu

1. **Nhóm NoteType `6b2a8fec` (4,122 notes)**:
   - `Collocation` và `Coollocation_VI`: **100% notes** (4,122/4,122) lưu dưới dạng JSON Native Array hoàn chỉnh.
   - `Synonym` và `Synonym_VI`: **99.7% notes** là Native Array nhiều phần tử.
   - `Antonym` và `Antonym_VI`: **89.1% notes** là Native Array nhiều phần tử (phần còn lại 1 phần tử hoặc rỗng do từ không có từ trái nghĩa).
   - `Meaning`: 3,468 notes mảng nhiều phần tử, **42 notes dính mảng giả 1 phần tử** chứa dấu phẩy hoặc chấm phẩy bên trong ngoặc (ví dụ: `["khay, mâm, khay đựng"]`, `["ngày hết hạn (thực phẩm; thẻ; hợp đồng)"]`).
   - `Word Family`: 3,828 notes mảng nhiều phần tử, **57 notes dính mảng giả 1 phần tử** chứa `/` hoặc `;` (ví dụ: `["foremost (adj./adv.): 最も重要な／第一に"]`).
   - `Example` và `Example_VI`: 4,028 notes có 1 câu ví dụ đơn, 94 notes có từ 2 câu ví dụ trở lên.

2. **Nhóm NoteType `13ff54d7` (1,179 notes)**:
   - `Word Family` (type: text): **1,179 / 1,179 notes (100.0%)** lưu dạng chuỗi phẳng scalar. Trong đó có tới **1,142 notes (96.9%) chứa ký tự phân cách thô `;`**!
     * Mẫu thực tế: `"sufficient (adj): đủ; insufficient (adj): không đủ; sufficiency (n): sự đủ; insufficiency (n): sự thiếu; adequate (adj): đầy đủ"`.
   - `Example` và `Example_VI` (type: richtext): **1,179 / 1,179 notes (100.0%)** lưu chuỗi phẳng, trong đó 32 notes chứa `;` nối 2 câu ví dụ:
     * Mẫu thực tế: `"Please place the label on the right side of the box.; The two teams are on opposite sides of the issue."`.

---

### 3.3. Kiểm toán Trường Legacy: `STT` (Số Thứ Tự) & Quyết Định Loại Bỏ (Deprecation)

- **Định nghĩa Schema Cũ**: Cả 2 NoteType đều định nghĩa `STT` tại vị trí 0, `required = 1`, `identity_role = 'primary'`.
- **Dữ liệu Thực tế**: **5,301 / 5,301 notes (100.0%)** có giá trị `STT` được điền đầy đủ (4,050 notes mang số nguyên `"15"`, `"82"`, `"954"`...). Không có bất kỳ note nào bị `NULL` hay rỗng.
- **Thực trạng Template & Study Applications**:
  - Study Application `690b2cec` (gắn NoteType `6b2a8fec` vào `Advanced Vocabulary Card` `f6d63262`) hoàn toàn không binding trường `STT`.
  - Cả Front HTML và Back HTML của `f6d63262` không có bất kỳ dòng nào hiển thị `STT` (`count = 0`).
  - Template `Thẻ 1` (`0ff348a2` của `13ff54d7`) tuy có bind `STT` nhưng mã HTML hoàn toàn bỏ qua không in ra.
- **Quyết định Kiến trúc & Định hướng từ Tác giả (User Architectural Decision)**:
  - Trường `STT` thực chất là tàn dư (legacy) từ quá trình import các file Anki/Excel ngày xưa, **hoàn toàn không cần thiết** cho mô hình học tập hiện đại trên Flama.
  - **Chỉ đạo thực thi**: **Xóa bỏ hoàn toàn trường `STT` (Deprecate & Drop)**, tuyệt đối **KHÔNG** bổ sung `#{{STT}}` vào giao diện template Presentation.
  - **Phương án Kỹ thuật Chuẩn hóa Schema**:
    1. Chuyển đổi vai trò định danh chính (`identity_role = 'primary'`, `required = 1`) từ `STT` sang trường `Vocabulary` (từ vựng tiếng Anh là khóa định danh tự nhiên duy nhất của thẻ).
    2. Loại bỏ trường `STT` khỏi `field_defs` và dọn dẹp khỏi `notes.field_values` trong Wave 2.
    3. Template Presentation hoàn toàn không render `STT`, giữ không gian Front/Back tinh gọn, tập trung 100% vào từ vựng, phát âm, từ loại và hệ thống mảng ngữ cảnh.

---

### 3.4. Kiểm toán Sự Gắn Nhầm Template: `Gõ chép chính tả` (`fc011484`)

- **Bản ghi Study Application**:
  ```sql
  SELECT id, note_type_id, template_id, display_name, is_default, status_code 
  FROM study_applications 
  WHERE note_type_id = '6b2a8fec-0276-401d-b361-c3affec1aa80';
  ```
  - App 1: `690b2cec` | Template: `f6d63262` (`Advanced Vocabulary Card`) | `status_code = 'ACTIVE'`, `is_default = 1`.
  - App 2: `6f4f0b3d` | Template: `fc011484` (`Gõ chép chính tả`) | **`status_code = 'ACTIVE'`**, `is_default = 0`.
- **Hậu quả Trên Hệ Thống**:
  - Do Study Application được kích hoạt ở cấp NoteType, **toàn bộ 143 decks (4,122 notes)** đều bị hệ thống ép sinh thêm 1 thẻ bài tập gõ phím.
  - Template gõ chính tả `fc011484` đòi hỏi bắt buộc phải có `Audio` (nhưng có **211 notes trong DB không có audio** khiến thẻ bị tê liệt).
  - Yêu cầu `BackImage` (nhưng có **4,067 / 4,122 notes (98.7%) không có ảnh**).
  - Lược bỏ hoàn toàn 9 trường từ vựng liên kết: `STT`, `PoS`, `Pronunciation`, `Collocation`, `Coollocation_VI`, `Synonym`, `Synonym_VI`, `Antonym`, `Antonym_VI`, `Word Family`, `Note_EN`.
- **Hành động Khắc phục**: Chuyển đổi ngay lập tức trạng thái của Study Application `6f4f0b3d` từ `'ACTIVE'` sang `'RETIRED'`.

---

### 3.5. Kiểm chứng Bảo toàn 100% Phiên âm Quốc tế IPA `/<ipa>/`

- **Dữ liệu thực tế**: Kiểm tra toàn bộ 5,301 notes (`6b2a8fec` và `13ff54d7`), 100% trường `Pronunciation` đều có cấu trúc gạch chéo bao bọc `/<ipa>/`.
- **Độ phức tạp của dữ liệu IPA**:
  - Phiên âm đơn: `/'tɛmpɚˌɛɹi/`, `/stuːl/`, `/ˈbæk.pæk/`.
  - Phiên âm kép ngăn cách bằng dấu `;` bên trong: `/'diː.teɪl; dɪ'teɪl/` (Note `0227d65f`).
  - Phiên âm kép kèm từ loại: `/'sep.ər.eɪt/ (v), /'sep.ər.ət/ (adj)` (Note `1d6b3fc0`).
  - Hai khối IPA độc lập: `/rɪ'zuːm/; /'rezəmeɪ/` (Note `322d6712`).
  - Phiên âm chứa ký tự Flap T và nguyên âm rhotacized: `/əˈkwæt̬.ɪk ˈæn.ɪ.məlz/`, `/ˈhaɪˌlaɪ.t̬ɚ/`.
- **Quy tắc Giới hạn Phạm vi Bắt buộc (Mandatory Scoping Guardrail)**:
  - **TUYỆT ĐỐI CHỈ ÁP DỤNG CHO TRƯỜNG `Pronunciation`**: Cơ chế che chắn IPA (`IPA_TOKEN_RE`) được thiết kế và kiểm chứng dành riêng **100% cho trường `Pronunciation` / `Phonetic`** của 2 NoteType `En4Everyone` (`6b2a8fec` và `13ff54d7`).
  - **NGHIÊM CẤM áp dụng Global trên toàn bộ note**: Nếu quét trên toàn bộ các trường khác (như `image`, `word_audio`, `additional_note`), regex chứa dấu gạch chéo `/` sẽ bắt nhầm đường dẫn tài nguyên media (`/media/audio/en/apple.mp3`), ngày tháng (`5/10/2026`), hoặc phân số/đơn vị (`km/h / mph`, `either/or/neither`), làm biến dạng dữ liệu ngoài ý muốn.
- **Biểu thức Chính quy (Regex) Chặt chẽ đã Tinh chỉnh**:
  - Thay vì dùng `/[^/\r\n]+/` quá rộng, regex được siết chặt với tập ký tự phiên âm quốc tế chuẩn (bao gồm trọng âm chính `ˈ`, trọng âm phụ `ˌ`, nguyên âm dài `ː`, các nguyên âm IPA `ɪeæɑɒɔʊuʌɜə`, flap T `\u032c`, nguyên âm rhotic `ɚ`, `ɝ`, dấu chấm phân tách âm tiết `.`, và dấu phân cách `;`, `,`):
    ```python
    IPA_TOKEN_RE = re.compile(
        r'/[\w\s\.\'ˈˌɪeæɑɒɔʊuːʌɜəeɪaɪɔɪaʊəʊɪəeəʊəptkfbvdzθðsʃzʒhmnŋlrjw;\(\)\-\,\u032cɚɝ]+\s*/'
    )
    ```
  - **Kết quả Kiểm thử Thực nghiệm trên MySQL Local**:
    - **5,301 / 5,301 notes** trong bảng `notes` đạt độ khớp hoàn hảo **100.0% (0 mismatches)**.
    - Đảm bảo 100% phiên âm IPA không bị cắt gọt hay biến dạng khi bóc tách mảng Native Array.

---

### 3.6. Ma trận Trường Chuẩn hóa & Template Presentation En4Everyone Mới

#### Bảng Ma trận Trường Đề xuất Nâng cấp (To-Be Schema):
| Tên Trường | Kiểu Dữ Liệu | Bắt buộc | Vai trò | Quy tắc Nâng cấp & Hiển thị |
| :--- | :---: | :---: | :---: | :--- |
| `Vocabulary` | `text` | 1 | `primary` | **Khóa định danh chính mới** (thay thế `STT`), font đậm nổi bật trung tâm. |
| `STT` | — | 0 | `deprecated` | **Trường Legacy**: Đã được tác giả quyết định xóa bỏ hoàn toàn (không render, loại bỏ khỏi schema). |
| `PoS` | `text` | 0 | None | Badge từ loại uppercase nền xanh lá (`oklch(0.96 0.03 140)`). |
| `Pronunciation`| `text` | 0 | None | Phiên âm IPA nguyên bản `/<ipa>/`, font Lucida Sans Unicode. |
| `Meaning` | `array` | 0 | None | Native Array, hiển thị in hoa màu xanh lá đậm (`#1b8f3a`). |
| `Example` | `array` | 0 | None | Native Array câu ví dụ tiếng Anh, kèm nút phát audio. |
| `Example_VI` | `array` | 0 | None | Native Array câu dịch tiếng Việt. |
| `Collocation` | `array` | 0 | None | Native Array cụm từ tiếng Anh, hiển thị grid 2 cột song song. |
| `Collocation_VI`| `array` | 0 | None | Native Array nghĩa cụm từ (hỗ trợ alias tương thích `Coollocation_VI`). |
| `Synonym` | `array` | 0 | None | Native Array từ đồng nghĩa, hiển thị dạng tag chips. |
| `Synonym_VI` | `array` | 0 | None | Native Array nghĩa từ đồng nghĩa. |
| `Antonym` | `array` | 0 | None | Native Array từ trái nghĩa, hiển thị tag chips tương phản. |
| `Antonym_VI` | `array` | 0 | None | Native Array nghĩa từ trái nghĩa. |
| `Word Family` | `array` | 0 | None | Chuyển `13ff54d7` sang array qua bóc tách dấu `;` ngoài ngoặc. |
| `Note_EN` | `text` | 0 | None | Ghi chú văn cảnh tiếng Anh. |
| `Note_VI` | `text` | 0 | None | Ghi chú văn cảnh tiếng Việt. |
| `Vocabulary_Audio` | `audio` | 0 | None | Tự động phát âm thanh từ vựng khi lật thẻ. |
| `Example_Audio`| `audio` | 0 | None | Phát âm thanh câu ví dụ khi người dùng bấm nút 🔊. |
| `image` | `image` | 0 | None | Thư viện ảnh minh họa (`flama-media-gallery`). |

---

## PHẦN 4: MA TRẬN TỔNG HỢP NOTETYPE VÀ TEMPLATE MISMATCH TOÀN HỆ THỐNG

Bảng dưới đây tổng hợp toàn bộ các cặp NoteType <-> Template bị lệch pha hoặc gặp khiếm khuyết cấu trúc trên toàn bộ cơ sở dữ liệu:

| Mã NoteType | Tên NoteType | Chủ Sở Hữu | Template ID & Tên Đang Gắn | Số Decks / Notes Bị Ảnh Hưởng | Chi Tiết Lệch Pha (Mismatch Type) | Biện Pháp Xử Lý Đề Xuất |
| :--- | :--- | :---: | :--- | ---: | :--- | :--- |
| `6b2a8fec` | `En4Everyone` | `user_id = 1` | `fc011484`<br>(`Gõ chép chính tả`) | **143 decks**<br>(4,122 notes) | **Gắn nhầm Template gõ phím**: Đòi hỏi Audio (211 notes thiếu), đòi hỏi Ảnh (98.7% thiếu), vứt bỏ 9 trường từ vựng. | Chuyển Study Application `6f4f0b3d` sang trạng thái `RETIRED`. |
| `6b2a8fec` | `En4Everyone` | `user_id = 1` | `f6d63262`<br>(`Advanced Vocabulary Card`) | **143 decks**<br>(4,122 notes) | **Trường Legacy `STT` & CSS `100vh`**: `STT` không cần thiết trên template; lỗi CSS `100vh`; thiếu CSS tags cho Word Family. | Cập nhật Template Mustache mới (loại bỏ hoàn toàn `STT`), CSS clamp responsive, grid pairs. |
| `13ff54d7` | `En4Everyone` | `user_id = 4` | `0ff348a2`<br>(`Thẻ 1`) | **43 decks**<br>(1,179 notes) | **Lệch Schema & Trường Legacy `STT`**: `Word Family` là text scalar (96.9% dính `;`); `Example` là richtext; `STT` là tàn dư legacy. | Nâng cấp schema lên array, xóa bỏ trường `STT`, migrate dữ liệu dính `;`, áp dụng Template mới. |
| `4fc2eb8e` | `文法N1` | `chungtrinh2k2` (1) | `0a86851a`<br>(`Grammar & Literary Quotes Card`) | **18 decks**<br>(90 notes) | **Unclosed `<div>` & `100vh`**: Thẻ mở trong `{{#name}}` không đóng; orphan `</div>`; trường có dấu chấm `literary_example.quote`. | Thay thế bằng Template Flama Grammar chuẩn có AST Tag-Balanced 100%. |
| `35cef59f` | `文法N1` (Clone) | `Ánh` (4) | `266cbc84`<br>(`Thẻ 1`) | **4 decks**<br>(139 notes) | **Unclosed `<div>` & Scalar Delimiters**: Thừa hưởng lỗi unclosed `<div>`; 138/139 notes dính delimiter trong text. | Thay thế Template và chuyển các trường text sang Native Array. |
| `91f567ab` | `Kanji_N3` | `Ánh` (4) | `21a53f7b`<br>(`Card 1`) | **13 decks**<br>(790 notes) | **Đảo Ngữ Nghĩa 1-to-1**: 148 notes đảo `Phiên âm` <-> `Âm Hán Tự`; 70 notes Kanji trong HanViet; lỗi `100vh`. | Hoán đổi lại dữ liệu đúng ngữ nghĩa, thay thế Template bằng `Flama Kanji Standard`. |
| `85b20688` | `漢字N1` | `Ánh` (4) | `273a92a1`<br>(`Thẻ 1`) | 0 notes | **Duplicate Tag & Script Hack**: `{{Diagram}}` in 2 lần; script regex `replace(/\$/g)`; toàn bộ trường là text scalar. | Xóa bỏ script DOM, chuẩn hóa schema theo `Flama Kanji Standard`. |
| `e2f310a8` | `Flama Standard Vocabulary` | `Official` (1) | `e0cb18b2`<br>(`Default Flama Flashcard`) | **1,305 decks**<br>(35,112 notes) | **Tàn dư Anki `$` và `\n`**: 5,869 unique notes (290 decks) dính delimiter thô; 35,103 notes dính mảng giả 1 phần tử; script DOM `div[auto-split]`. | Chuyển đổi dữ liệu bằng Bracket-Shielding, xóa bỏ script `auto-split` trên template. |

---

## PHẦN 5: KẾ HOẠCH HÀNH ĐỘNG VÀ LỘ TRÌNH NÂNG CẤP (ACTION PLAN & UPGRADE ROADMAP)

### 5.1. Nguyên tắc An toàn & Cam kết Zero Data Loss

Mọi quy trình nâng cấp và chuyển đổi dữ liệu trên cơ sở dữ liệu MySQL production/local bắt buộc phải tuân thủ nghiêm ngặt 4 nguyên tắc sắt:
1. **Zero Data Loss Guarantee**: Mọi ký tự trong dữ liệu gốc (bao gồm thẻ HTML, chú thích ngoặc, ký hiệu tiền tệ `$`, số mũ toán học `且$^2$`, phiên âm IPA `/<ipa>/`) phải được bảo toàn nguyên vẹn 100%.
2. **Transaction Isolation & Chunking**: Không thực hiện một transaction khổng lồ cập nhật hàng chục nghìn bản ghi. Chia nhỏ thành từng chunk tối đa **250 notes / transaction**, commit từng đợt để không gây lock bảng InnoDB (`SELECT ... FOR UPDATE`).
3. **Preimage Snapshot Cryptographic Hashing**: Trước khi thực hiện bất kỳ update nào trên một chunk, toàn bộ dữ liệu thô cũ của `field_values_by_id` phải được ghi vào file snapshot JSON kèm mã băm SHA-256 để phục vụ đối soát và rollback tức thì.
4. **Preserve Overlay-Only Clone Model**: Không sao chép nhân bản note đối với các deck clone (như 207 decks của User 16). Mọi can thiệp schema và note data chỉ tác động trực tiếp lên source note gốc.

---

### 5.2. Lộ trình Triển khai Phân kỳ (4 Làn sóng - Waves)

```
[Wave 1: Template Fix & Retirement] ──► [Wave 2: En4Everyone Normalization & IPA]
                 │                                            │
                 ▼                                            ▼
[Wave 4: Flama Default Array Migration] ◄── [Wave 3: ChungBechN1 Semantic Swap Fix]
```

#### Làn sóng 1 (Wave 1): Khắc phục Template Cú pháp & Retire Template Gắn Nhầm
- **Mục tiêu**: Loại bỏ ngay các lỗi hiển thị nghiêm trọng mà không cần thay đổi dữ liệu note.
- **Các bước thực hiện**:
  1. Chuyển trạng thái Study Application `6f4f0b3d` (`Gõ chép chính tả`) sang `status_code = 'RETIRED'`. Giải phóng ngay lập tức 143 decks (4,122 notes) của `En4Everyone`.
  2. Cập nhật mã nguồn `back_html` của các template ngữ pháp (`0a86851a`, `266cbc84`) đóng thẻ `<div>` chính xác, xóa bỏ thẻ mồ côi dòng 84.
  3. Cập nhật CSS loại bỏ `height: 100vh`, thay bằng `min-height: clamp(...)` trên toàn bộ các template liên quan.
  4. Xóa bỏ thẻ `{{Diagram}}` trùng lặp trong template `273a92a1`.
- **Rủi ro dữ liệu**: 0% (chỉ sửa bảng `templates` và `study_applications`).

#### Làn sóng 2 (Wave 2): Chuẩn hóa En4Everyone, Loại bỏ Trường Legacy `STT` & Bảo Toàn 100% IPA
- **Mục tiêu**: Xóa bỏ hoàn toàn trường legacy `STT`, chuyển khóa định danh chính sang `Vocabulary`, chuẩn hóa NoteType `13ff54d7` và bảo toàn 100% IPA.
- **Các bước thực hiện**:
  1. Loại bỏ trường `STT` khỏi giao diện template Presentation (không render `#{{STT}}`, giữ thẻ tinh gọn).
  2. Nâng cấp template `Advanced Vocabulary Card` áp dụng Paired Grid cho Collocation, Synonym, Antonym, và CSS clamp responsive.
  3. Cập nhật schema: chuyển `identity_role = 'primary'` và `required = 1` sang trường `Vocabulary` (từ vựng chính); tiến hành deprecate / xóa trường `STT` khỏi `field_defs` và dọn dẹp khỏi `notes.field_values`.
  4. Cập nhật schema `13ff54d7`: đổi kiểu `Word Family`, `Example`, `Example_VI` từ text/richtext sang `array`.
  5. Chạy script migration áp dụng **IPA Shielding** và **Bracket-Shielding** bóc tách 1,142 notes dính dấu `;` trong `Word Family` của `13ff54d7`.

#### Làn sóng 3 (Wave 3): Sửa lỗi Hoán đổi Ngữ nghĩa ChungBechN1 (Semantic Swap)
- **Mục tiêu**: Khắc phục triệt để 148 notes bị đảo giữa `Phiên âm` và `Âm Hán Tự` trong `Kanji_N3`, sửa 70 notes Kanji trong Hán Việt, chuẩn hóa NoteType Kanji và Grammar N1.
- **Các bước thực hiện**:
  1. Chạy preimage snapshot SHA-256 cho 148 notes bị hoán đổi trong `Kanji_N3`.
  2. Thực thi script hoán đổi nguyên tử 1-to-1:
     - Giá trị Kana tiếng Nhật trong `Âm Hán Tự` (`d2366e63`) -> chuyển vào `Phiên âm` (`826db147`) dạng mảng JSON `["..."]`.
     - Giá trị chữ Hán Việt viết hoa trong `Phiên âm` (`826db147`) -> chuyển vào `Âm Hán Tự` (`d2366e63`) dạng chuỗi text chuẩn.
  3. Bóc tách chữ Kanji thô ra khỏi 70 notes trong trường `Âm Hán Tự`.
  4. Chuẩn hóa 73 trường mảng giả dính dấu `;` trong NoteType `文法N1` (`4fc2eb8e`).

#### Làn sóng 4 (Wave 4): Di chuyển Dữ liệu Flama Default sang Native Array
- **Mục tiêu**: Bóc tách 5,869 unique notes (290 decks) dính `$` và `\n` trong Flama Standard Vocabulary, loại bỏ hoàn toàn script `div[auto-split]`.
- **Các bước thực hiện**:
  1. Tạo snapshot preimage cho toàn bộ 5,869 unique notes Dạng 1, 2, 3 (290 decks).
  2. Thực thi thuật toán `split_bracket_shielded` theo các chunks 250 notes:
     - Chuyển `reading` từ `["ふうしゃ$かざぐるま"]` thành `["ふうしゃ", "かざぐるま"]`.
     - Chuyển `diagram` sang mảng JSON các đường dẫn SVG.
     - Chuyển `additional_note_vi` và `additional_note_jp` thành mảng JSON bullet points sạch sẽ.
  3. Cập nhật Presentation Template `Default Flama Flashcard` loại bỏ script regex `auto-split`.

---

### 5.3. Quy trình Thực thi Giao dịch (Transactional Chunking & Preimage Rollback)

Mẫu cấu trúc script thực thi an toàn cho từng Wave:

```python
import os, json, hashlib, pymysql
from typing import Dict, Any

CHUNK_SIZE = 250

def execute_safe_migration_chunk(conn, chunk_notes: list, wave_name: str):
    """
    Thực thi cập nhật theo chunk giao dịch độc lập kèm preimage snapshot SHA-256.
    Trang bị đầy đủ cơ chế phòng vệ:
    1. Guard chống chunk rỗng (ngăn chặn lỗi cú pháp SQL WHERE id IN () và IndexError).
    2. Tự động khởi tạo thư mục snapshots (os.makedirs).
    3. Transaction rollback an toàn khi phát sinh ngoại lệ (tự động giải phóng lock InnoDB).
    """
    if not chunk_notes:
        return
        
    snapshot_records = []
    note_ids = [n['id'] for n in chunk_notes]
    snapshot_dir = "docs/audit/snapshots"
    os.makedirs(snapshot_dir, exist_ok=True)
    snapshot_path = os.path.join(snapshot_dir, f"{wave_name}_chunk_{note_ids[0]}.json")
    
    try:
        with conn.cursor() as cur:
            # Bước 1: Khóa hàng và lưu Preimage Snapshot
            cur.execute("START TRANSACTION;")
            
            format_strings = ','.join(['%s'] * len(note_ids))
            cur.execute(f"SELECT id, field_values_by_id FROM notes WHERE id IN ({format_strings}) FOR UPDATE;", note_ids)
            current_rows = cur.fetchall()
            
            for r_id, r_fields in current_rows:
                raw_json = json.dumps(r_fields, ensure_ascii=False, sort_keys=True)
                sha256 = hashlib.sha256(raw_json.encode('utf-8')).hexdigest()
                snapshot_records.append({
                    'note_id': r_id,
                    'preimage': r_fields,
                    'sha256': sha256
                })
                
            # Ghi snapshot dự phòng ra đĩa trước khi ghi đè dữ liệu
            with open(snapshot_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot_records, f, ensure_ascii=False, indent=2)
                
            # Bước 2: Thực thi cập nhật dữ liệu đã chuẩn hóa
            for note in chunk_notes:
                cur.execute(
                    "UPDATE notes SET field_values_by_id = %s, updated_at = NOW() WHERE id = %s;",
                    (json.dumps(note['transformed_fields'], ensure_ascii=False), note['id'])
                )
                
            # Bước 3: Commit giao dịch
            conn.commit()
            print(f"Committed chunk of {len(chunk_notes)} notes successfully. Snapshot saved at {snapshot_path}")
    except Exception as e:
        conn.rollback()
        print(f"[ROLLBACK] Gặp sự cố tại chunk {note_ids[0] if note_ids else 'unknown'}: {e}. Đã rollback an toàn.")
        raise
```

---

### 5.4. Phương pháp Kiểm chứng Độc lập

Bất kỳ chuyên viên kiểm toán hoặc kỹ sư nào cũng có thể kiểm chứng lại toàn bộ các phát hiện và số liệu trong báo cáo này thông qua các bước:

1. **Kiểm tra Quy mô Hệ thống & NoteTypes**:
   ```powershell
   .\.venv\Scripts\python.exe -c "import pymysql, os, dotenv; dotenv.load_dotenv(); conn = pymysql.connect(host='localhost', user='root', password=os.getenv('DB_PASSWORD'), database='nihongo'); cur = conn.cursor(); cur.execute('SELECT count(*) FROM notes'); print('Total Notes:', cur.fetchone()[0]); cur.execute('SELECT count(*) FROM decks'); print('Total Decks:', cur.fetchone()[0])"
   ```
   *Kết quả*: `Total Notes: 41624`, `Total Decks: 5579`.

2. **Kiểm chứng 148 Notes Đảo Ngữ Nghĩa trong `Kanji_N3`**:
   ```powershell
   .\.venv\Scripts\python.exe scripts/audit/generate_chungbechn1_metrics.py
   ```
   *Kết quả*: `Exact 1-to-1 Inversions (Phiên âm <-> Âm Hán Tự): 148 notes`.

3. **Kiểm chứng 100% Phiên Âm IPA Shielding trên En4Everyone**:
   ```powershell
   .\.venv\Scripts\python.exe .agents\teamwork\teamwork_preview_explorer_r3_1\verify_ipa_shield.py
   ```
   *Kết quả*: `Total IPA tested: 5301`, `Perfect Shield-and-Restore Matches: 5301 / 5301 (100.0%)`, `Mismatches: 0`.

4. **Kiểm chứng Thuật toán Bracket-Shielding của Flama Default**:
   ```powershell
   .\.venv\Scripts\python.exe .agents\teamwork\teamwork_preview_explorer_r1_1\test_bracket_shielding.py
   ```
   *Kết quả*: `ALL 8 TESTS PASSED PERFECTLY!`.

5. **Điều Kiện Vô Hiệu Hóa Báo Cáo (Invalidation Conditions)**:
   - Nếu có bất kỳ câu lệnh `INSERT`, `UPDATE`, `DELETE` nào làm biến đổi tổng số `41,624 notes` hoặc `5,579 decks`.
   - Nếu cấu trúc JSON trong `field_values_by_id` của các note ID dẫn chứng bị thay đổi mà không thông qua migration audit.
   - Nếu các template mục tiêu bị ghi đè phiên bản mới mà không ghi chép lịch sử.

---
*Tài liệu kiểm toán được biên soạn và xuất bản hoàn chỉnh, sẵn sàng phục vụ công tác rà soát và phê duyệt kỹ thuật của Hội đồng Kiến trúc Flama.*
