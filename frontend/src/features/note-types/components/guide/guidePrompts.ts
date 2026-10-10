export const MASTER_PROMPT = `Bạn là một chuyên gia thiết kế Flashcard học ngôn ngữ trên nền tảng Flama (sử dụng chuẩn Mustache Template, HTML5, CSS3 và JavaScript trong iframe sandbox).

Nhiệm vụ của bạn là dựa vào [YÊU CẦU CỦA TÔI], hãy thiết kế:
1. Danh sách các Trường dữ liệu (Field Definitions) cần tạo trong Note Type (gồm Tên trường và Loại trường: text / richtext / audio / image / markdown...).
2. Bộ input của Template (key, nhãn, kiểu dữ liệu) và bảng mapping field → input.
3. Mã Front HTML (Mặt trước).
4. Mã Back HTML (Mặt sau).
5. Mã Shared CSS (Định dạng kiểu dáng chung).

YÊU CẦU KỸ THUẬT BẮT BUỘC ĐỂ KHÔNG BỊ LỖI:
- Field thuộc Note Type; input thuộc Template. Tên field và input không cần giống nhau; mapping phải ghép cùng kiểu dữ liệu.
- Đặt key input theo chuẩn snake_case chữ thường (ví dụ: word, reading, meaning, audio_word, example_jp, example_vi).
- Sử dụng cú pháp Mustache {{InputKey}} hoặc {{{InputKey}}} (nếu là richtext).
- Mọi khối có điều kiện ẩn hiện bắt buộc dùng: {{#InputKey}} ... {{/InputKey}}.
- Đóng mở thẻ HTML chuẩn xác: Mọi thẻ HTML mở bên trong block Mustache {{#...}} PHẢI ĐƯỢC ĐÓNG trước {{/...}}.
- Khung thẻ mặt trước căn giữa bằng Flexbox (không dùng style height: 100vh).
- Các input Audio phải tạo thẻ <audio id="..." src="{{InputKey}}"></audio> và nút bấm loa 🔊 tương ứng.
- Nếu có script tự động phát âm tuần tự trong thẻ <script>, phải kiểm tra phần tử tồn tại trước khi phát (safePlay).
- Thiết kế giao diện hiện đại, tinh tế, font chữ rõ ràng, phân cấp thị giác đẹp mắt, hỗ trợ hiển thị đẹp trên cả mobile và desktop.

[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: (Ví dụ: Thẻ học Ngữ pháp JLPT N2 / Thẻ học Kanji N1 / Thẻ học từ vựng Y tế...)
- Các thông tin tôi muốn có trên thẻ:
  + Mặt trước: (Ví dụ: Mẫu ngữ pháp lớn màu đỏ nổi bật, nút nghe audio câu ví dụ tiêu biểu)
  + Mặt sau: (Ví dụ: Ý nghĩa, Cấu trúc ngữ pháp, Giải thích chi tiết, 2 ví dụ có câu dịch và audio, phần phân biệt với ngữ pháp tương đương)
- Phong cách giao diện: (Ví dụ: Tối giản, tông màu xanh dương đậm thanh lịch, font chữ Nhật Bản rõ nét)`

export const EXAMPLE_VOCAB_PROMPT = `[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: Học từ vựng JLPT kèm âm Hán Việt và ví dụ đời sống.
- Mặt trước: Từ vựng Kanji to ở giữa, nút loa phát âm từ vựng.
- Mặt sau:
  + Hiển thị lại Kanji kèm Furigana và Âm Hán Việt.
  + Ý nghĩa tiếng Việt (chữ đậm màu xanh).
  + Câu ví dụ tiếng Nhật + Câu dịch tiếng Việt + Audio phát âm câu ví dụ.
  + Ghi chú / Từ đồng nghĩa (nếu có mới hiện).
  + Script tự động đọc: Đọc từ vựng trước, sau đó tự đọc câu ví dụ.
- Phong cách: Sang trọng, bo góc tròn, màu sắc hiện đại.`

export const EXAMPLE_GRAMMAR_PROMPT = `[YÊU CẦU CỦA TÔI]:
- Mục đích thẻ: Học Ngữ pháp JLPT N1 nâng cao.
- Mặt trước: Mẫu ngữ pháp màu đỏ nổi bật ở giữa.
- Mặt sau:
  + Tiêu đề ngữ pháp + Nút Audio đọc mẫu câu.
  + Ý nghĩa tiếng Việt + Cấu trúc ngữ pháp (màu xanh lá).
  + Ghi chú / Giải thích chi tiết.
  + Ví dụ hội thoại thông thường + dịch nghĩa.
  + Ví dụ trích dẫn văn học (Câu trích dẫn, Tác phẩm, Tác giả, Bản dịch) - chỉ hiện khi có dữ liệu.
  + Mục phân biệt / so sánh với mẫu câu gần nghĩa.
- Phong cách: Rõ ràng, dễ đọc, tương phản tốt.`

export const MASTER_PROMPT_EN = `You are an expert language flashcard designer on the Flama platform (using Mustache Template, HTML5, CSS3, and JavaScript in an iframe sandbox).

Your task is to design based on [MY REQUIREMENTS]:
1. A list of Field Definitions to create in the Note Type (Field Name and Field Type: text / richtext / audio / image / markdown...).
2. The Template input schema (key, label, type) and a field → input mapping table.
3. Front HTML code.
4. Back HTML code.
5. Shared CSS code.

MANDATORY TECHNICAL REQUIREMENTS TO PREVENT ERRORS:
- Fields belong to the Note Type; inputs belong to the Template. Their names may differ, but mapped types must match exactly.
- Name input keys using lowercase snake_case (e.g. word, reading, meaning, audio_word, example_jp, example_vi).
- Use Mustache syntax {{InputKey}} or {{{InputKey}}} (if richtext).
- All conditional visibility blocks must use: {{#InputKey}} ... {{/InputKey}}.
- Precise HTML tag pairing: Any HTML tag opened inside {{#...}} MUST BE CLOSED before {{/...}}.
- Center the front card with Flexbox (do not use style height: 100vh).
- Audio inputs must generate an <audio id="..." src="{{InputKey}}"></audio> tag and a matching speaker button 🔊.
- If sequential audio playback scripts exist inside <script>, ensure element existence before playing (safePlay).
- Clean, modern, responsive design with clear typography, supporting both mobile and desktop.

[MY REQUIREMENTS]:
- Card purpose: (e.g., JLPT N2 Grammar Cards / N1 Kanji Cards / Medical Vocabulary...)
- Information to include:
  + Front: (e.g., Large red grammar point, audio button for sample sentence)
  + Back: (e.g., Meaning, Grammar structure, Detailed explanation, 2 examples with translation and audio, comparison with similar grammar)
- Visual style: (e.g., Minimalist, elegant dark blue theme, clean Japanese fonts)`

export const EXAMPLE_VOCAB_PROMPT_EN = `[MY REQUIREMENTS]:
- Card purpose: JLPT vocabulary with reading and real-life examples.
- Front: Large Kanji word in center, audio pronunciation button.
- Back:
  + Re-display Kanji with Furigana.
  + Meaning (bold blue text).
  + Japanese example sentence + translation + Example sentence audio.
  + Notes / Synonyms (only show if present).
  + Auto-play script: Play vocabulary first, then automatically play example sentence.
- Style: Elegant, rounded corners, modern color scheme.`

export const EXAMPLE_GRAMMAR_PROMPT_EN = `[MY REQUIREMENTS]:
- Card purpose: Advanced JLPT N1 Grammar.
- Front: Red prominent grammar pattern in center.
- Back:
  + Grammar title + Audio button for pattern sentence.
  + Meaning + Grammar structure (green text).
  + Detailed notes & explanation.
  + Standard conversational example + translation.
  + Literary quotation example (Quote, Work, Author, Translation) - only show if present.
  + Comparison section with similar grammar patterns.
- Style: Clean, readable, strong contrast.`

export function getMasterPrompt(lang?: string): string {
  return lang === 'en' ? MASTER_PROMPT_EN : MASTER_PROMPT
}

export function getExampleVocabPrompt(lang?: string): string {
  return lang === 'en' ? EXAMPLE_VOCAB_PROMPT_EN : EXAMPLE_VOCAB_PROMPT
}

export function getExampleGrammarPrompt(lang?: string): string {
  return lang === 'en' ? EXAMPLE_GRAMMAR_PROMPT_EN : EXAMPLE_GRAMMAR_PROMPT
}
