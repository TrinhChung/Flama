export const CATEGORY_PRESETS = [
  { id: 'General', label: 'Tổng hợp', sub: 'Thường thức, đố vui, tổng hợp' },
  { id: 'Japanese', label: 'Tiếng Nhật', sub: 'JLPT, Kanji, Kaiwa, Từ vựng' },
  { id: 'English', label: 'Tiếng Anh', sub: 'IELTS, TOEIC, TOEFL, Giao tiếp' },
  { id: 'Chinese', label: 'Tiếng Trung', sub: 'HSK, Chữ Hán, Giao tiếp' },
  { id: 'Korean', label: 'Tiếng Hàn', sub: 'TOPIK, Từ vựng, Ngữ pháp' },
  { id: 'IT', label: 'Công nghệ & IT', sub: 'Lập trình, Web, Mobile, DevOps' },
  { id: 'Certification', label: 'Chứng chỉ', sub: 'AWS, PMP, GMAT, Thi công chức' },
  { id: 'Academic', label: 'Học thuật', sub: 'Y dược, Toán, Lý, Hóa, Luật' },
  { id: 'Custom', label: 'Tùy chỉnh', sub: 'Nhập tên danh mục riêng' },
]

export const NOTE_TYPE_CATEGORY_PRESETS = [
  { id: 'Templates', label: 'Mẫu chuẩn', sub: 'Mẫu cơ bản, Anki mặc định' },
  { id: 'Vocabulary', label: 'Từ vựng', sub: 'Song ngữ, Kanji, Phiên âm, Audio' },
  { id: 'Cloze', label: 'Cloze Deletion', sub: 'Thẻ đục lỗ, điền từ vào chỗ trống' },
  { id: 'IT', label: 'Code & IT', sub: 'Lập trình, Snippets, Cú pháp' },
  { id: 'Grammar', label: 'Ngữ pháp', sub: 'Ví dụ, Cấu trúc, Giải thích' },
  { id: 'QA', label: 'Hỏi đáp (Q&A)', sub: 'Câu hỏi ngắn, Đố vui' },
  { id: 'Custom', label: 'Tùy chỉnh', sub: 'Nhập tên danh mục riêng' },
]

export const TAXONOMY_DOMAINS = [
  { id: 'language_learning', label: 'Ngôn ngữ (Language Learning)' },
  { id: 'certification', label: 'Chứng chỉ (Certification)' },
  { id: 'professional_skills', label: 'Kỹ năng nghề nghiệp' },
  { id: 'academic', label: 'Học thuật' },
  { id: 'other', label: 'Khác' },
]

export const TAXONOMY_SUBJECTS: Record<string, Array<{ id: string; label: string }>> = {
  language_learning: [
    { id: 'japanese', label: 'Tiếng Nhật' },
    { id: 'english', label: 'Tiếng Anh' },
    { id: 'chinese', label: 'Tiếng Trung' },
    { id: 'korean', label: 'Tiếng Hàn' },
  ],
  certification: [
    { id: 'aws', label: 'AWS Certification' },
    { id: 'other_certification', label: 'Chứng chỉ khác' },
  ],
  professional_skills: [
    { id: 'it_coding', label: 'CNTT & Lập trình' },
    { id: 'business', label: 'Kinh doanh & Quản lý' },
  ],
  academic: [
    { id: 'science', label: 'Khoa học tự nhiên' },
    { id: 'medical', label: 'Y dược' },
    { id: 'law', label: 'Luật' },
  ],
  other: [
    { id: 'other', label: 'Chủ đề khác' },
  ],
}

export const TAXONOMY_DIFFICULTIES = [
  { id: 'beginner', label: 'Sơ cấp (Beginner)' },
  { id: 'intermediate', label: 'Trung cấp (Intermediate)' },
  { id: 'advanced', label: 'Nâng cao (Advanced)' },
]

export const TAXONOMY_LEARNING_GOALS = [
  { id: 'vocabulary', label: 'Từ vựng' },
  { id: 'kanji', label: 'Kanji' },
  { id: 'grammar', label: 'Ngữ pháp' },
  { id: 'reading', label: 'Luyện đọc' },
  { id: 'listening', label: 'Luyện nghe' },
  { id: 'speaking', label: 'Luyện nói' },
  { id: 'writing', label: 'Luyện viết' },
  { id: 'exam_prep', label: 'Luyện thi' },
  { id: 'daily_communication', label: 'Giao tiếp hàng ngày' },
  { id: 'drill', label: 'Ôn tập nhanh' },
]

export const TAXONOMY_TOPICS = [
  { id: 'meaning_recall', label: 'Nhớ nghĩa' },
  { id: 'reading_recall', label: 'Nhớ cách đọc' },
  { id: 'sentence_patterns', label: 'Mẫu câu' },
  { id: 'audio_recognition', label: 'Nghe nhận diện' },
  { id: 'daily_life', label: 'Đời sống hàng ngày' },
  { id: 'conversation', label: 'Hội thoại' },
  { id: 'travel', label: 'Du lịch' },
  { id: 'business', label: 'Công việc' },
  { id: 'kanji', label: 'Kanji' },
]

