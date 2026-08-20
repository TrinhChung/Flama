export const CATEGORY_PRESETS = [
  { id: 'General', label: 'Tổng hợp', sub: 'Thường thức, đố vui, tổng hợp' },
  { id: 'Japanese', label: 'Tiếng Nhật', sub: 'JLPT, Kanji, Kaiwa, Từ vựng' },
  { id: 'English', label: 'Tiếng Anh', sub: 'IELTS, TOEIC, TOEFL, VSTEP, Giao tiếp' },
  { id: 'Chinese', label: 'Tiếng Trung', sub: 'HSK, HSKK, TOCFL, Chữ Hán' },
  { id: 'Korean', label: 'Tiếng Hàn', sub: 'TOPIK, EPS-TOPIK, Từ vựng, Giao tiếp' },
  { id: 'IT', label: 'Công nghệ & IT', sub: 'Lập trình, Web, DevOps, AI, LeetCode' },
  { id: 'Certification', label: 'Chứng chỉ', sub: 'AWS, Azure, PMP, CFA, Thi công chức' },
  { id: 'Academic', label: 'Học thuật & Thi cử', sub: 'THPT Quốc Gia, Y Dược, Luật' },
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
  { id: 'academic', label: 'Học thuật & Thi cử' },
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
    { id: 'aws', label: 'AWS Cloud' },
    { id: 'azure', label: 'Microsoft Azure' },
    { id: 'other_certification', label: 'Chứng chỉ khác' },
  ],
  professional_skills: [
    { id: 'it_coding', label: 'CNTT & Lập trình' },
    { id: 'business', label: 'Kinh doanh & Quản lý' },
  ],
  academic: [
    { id: 'thpt_qg', label: 'Luyện thi THPT Quốc Gia' },
    { id: 'medical', label: 'Y dược' },
    { id: 'law', label: 'Luật' },
    { id: 'science', label: 'Khoa học tự nhiên' },
  ],
  other: [
    { id: 'other', label: 'Chủ đề khác' },
  ],
}

export type FrameworkLevelOption = {
  id: string
  label: string
  difficulty_band: 'beginner' | 'intermediate' | 'advanced'
  suggestedTags?: string[]
}

export type FrameworkOption = {
  id: string
  label: string
  levels: FrameworkLevelOption[]
}

export const TAXONOMY_FRAMEWORKS: Record<string, FrameworkOption[]> = {
  japanese: [
    {
      id: 'jlpt',
      label: 'JLPT',
      levels: [
        { id: 'n5', label: 'N5 (Sơ cấp 1)', difficulty_band: 'beginner', suggestedTags: ['jlpt', 'n5', 'tieng_nhat'] },
        { id: 'n4', label: 'N4 (Sơ cấp 2)', difficulty_band: 'beginner', suggestedTags: ['jlpt', 'n4', 'tieng_nhat'] },
        { id: 'n3', label: 'N3 (Trung cấp)', difficulty_band: 'intermediate', suggestedTags: ['jlpt', 'n3', 'tieng_nhat'] },
        { id: 'n2', label: 'N2 (Trung cao cấp)', difficulty_band: 'advanced', suggestedTags: ['jlpt', 'n2', 'tieng_nhat'] },
        { id: 'n1', label: 'N1 (Cao cấp)', difficulty_band: 'advanced', suggestedTags: ['jlpt', 'n1', 'tieng_nhat'] },
      ],
    },
    {
      id: 'kanji',
      label: 'Kanji / Hán tự',
      levels: [
        { id: 'kanji_n5_n4', label: 'Kanji N5 - N4 (Cơ bản)', difficulty_band: 'beginner', suggestedTags: ['kanji', 'n5_n4'] },
        { id: 'kanji_n3_n2', label: 'Kanji N3 - N2 (Trung cấp)', difficulty_band: 'intermediate', suggestedTags: ['kanji', 'n3_n2'] },
        { id: 'kanji_n1_jouyou', label: 'Kanji N1 & 2136 chữ Thường dụng', difficulty_band: 'advanced', suggestedTags: ['kanji', 'jouyou', 'n1'] },
      ],
    },
    {
      id: 'bjt',
      label: 'BJT / Giao tiếp',
      levels: [
        { id: 'kaiwa_basic', label: 'Giao tiếp đời sống (Minna)', difficulty_band: 'beginner', suggestedTags: ['kaiwa', 'giao_tiep'] },
        { id: 'bjt_j3_j2', label: 'BJT J3 - J2 (Thương mại)', difficulty_band: 'intermediate', suggestedTags: ['bjt', 'tieng_nhat_thuong_mai'] },
        { id: 'bjt_j1_plus', label: 'BJT J1 - J1+ (Cao cấp)', difficulty_band: 'advanced', suggestedTags: ['bjt', 'cao_cap'] },
      ],
    },
  ],
  english: [
    {
      id: 'ielts',
      label: 'IELTS',
      levels: [
        { id: 'ielts_4_5', label: 'IELTS 4.0 - 5.0', difficulty_band: 'beginner', suggestedTags: ['ielts', 'ielts_foundation'] },
        { id: 'ielts_5_5', label: 'IELTS 5.5 - 6.0', difficulty_band: 'intermediate', suggestedTags: ['ielts', 'ielts_5_5'] },
        { id: 'ielts_6_5', label: 'IELTS 6.5 - 7.0', difficulty_band: 'intermediate', suggestedTags: ['ielts', 'ielts_6_5'] },
        { id: 'ielts_7_plus', label: 'IELTS 7.5 - 8.0+', difficulty_band: 'advanced', suggestedTags: ['ielts', 'ielts_advanced'] },
      ],
    },
    {
      id: 'toeic',
      label: 'TOEIC',
      levels: [
        { id: 'toeic_450', label: 'TOEIC 250 - 450', difficulty_band: 'beginner', suggestedTags: ['toeic', 'toeic_450'] },
        { id: 'toeic_600', label: 'TOEIC 500 - 650', difficulty_band: 'intermediate', suggestedTags: ['toeic', 'toeic_600'] },
        { id: 'toeic_750', label: 'TOEIC 700 - 850', difficulty_band: 'intermediate', suggestedTags: ['toeic', 'toeic_750'] },
        { id: 'toeic_900', label: 'TOEIC 900+', difficulty_band: 'advanced', suggestedTags: ['toeic', 'toeic_900'] },
        { id: 'toeic_sw', label: 'TOEIC Speaking & Writing', difficulty_band: 'intermediate', suggestedTags: ['toeic', 'speaking_writing'] },
      ],
    },
    {
      id: 'vstep',
      label: 'VSTEP (Bậc 3-5)',
      levels: [
        { id: 'vstep_b1', label: 'VSTEP B1 (Bậc 3)', difficulty_band: 'intermediate', suggestedTags: ['vstep', 'vstep_b1'] },
        { id: 'vstep_b2', label: 'VSTEP B2 (Bậc 4)', difficulty_band: 'intermediate', suggestedTags: ['vstep', 'vstep_b2'] },
        { id: 'vstep_c1', label: 'VSTEP C1 (Bậc 5)', difficulty_band: 'advanced', suggestedTags: ['vstep', 'vstep_c1'] },
      ],
    },
    {
      id: 'cefr',
      label: 'CEFR (Châu Âu)',
      levels: [
        { id: 'a1_a2', label: 'A1 - A2 (Cơ bản)', difficulty_band: 'beginner', suggestedTags: ['cefr', 'a1_a2'] },
        { id: 'b1_b2', label: 'B1 - B2 (Độc lập)', difficulty_band: 'intermediate', suggestedTags: ['cefr', 'b1_b2'] },
        { id: 'c1_c2', label: 'C1 - C2 (Thành thạo)', difficulty_band: 'advanced', suggestedTags: ['cefr', 'c1_c2'] },
      ],
    },
    {
      id: 'toefl',
      label: 'TOEFL',
      levels: [
        { id: 'toefl_60', label: 'TOEFL iBT 40 - 60', difficulty_band: 'beginner', suggestedTags: ['toefl', 'toefl_ibt'] },
        { id: 'toefl_80', label: 'TOEFL iBT 61 - 80', difficulty_band: 'intermediate', suggestedTags: ['toefl', 'toefl_ibt'] },
        { id: 'toefl_100', label: 'TOEFL iBT 81 - 100+', difficulty_band: 'advanced', suggestedTags: ['toefl', 'toefl_ibt'] },
      ],
    },
    {
      id: 'thpt_qg',
      label: 'THPT QG / K12',
      levels: [
        { id: 'thpt_english', label: 'Luyện thi THPT QG Tiếng Anh', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'tieng_anh'] },
        { id: 'cambridge_ket_pet', label: 'Cambridge KET / PET', difficulty_band: 'beginner', suggestedTags: ['cambridge', 'ket_pet'] },
        { id: 'sat_digital', label: 'SAT Digital', difficulty_band: 'advanced', suggestedTags: ['sat', 'sat_digital'] },
      ],
    },
  ],
  korean: [
    {
      id: 'topik',
      label: 'TOPIK',
      levels: [
        { id: 'topik_1', label: 'TOPIK 1 (Cấp 1 - Nhập môn)', difficulty_band: 'beginner', suggestedTags: ['topik', 'topik_1', 'tieng_han'] },
        { id: 'topik_2', label: 'TOPIK 2 (Cấp 2 - Đời sống)', difficulty_band: 'beginner', suggestedTags: ['topik', 'topik_2', 'tieng_han'] },
        { id: 'topik_3', label: 'TOPIK 3 (Cấp 3 - Xã hội)', difficulty_band: 'intermediate', suggestedTags: ['topik', 'topik_3', 'tieng_han'] },
        { id: 'topik_4', label: 'TOPIK 4 (Cấp 4 - Tin tức/Công việc)', difficulty_band: 'intermediate', suggestedTags: ['topik', 'topik_4', 'tieng_han'] },
        { id: 'topik_5', label: 'TOPIK 5 (Cấp 5 - Chuyên sâu)', difficulty_band: 'advanced', suggestedTags: ['topik', 'topik_5', 'tieng_han'] },
        { id: 'topik_6', label: 'TOPIK 6 (Cấp 6 - Bản xứ)', difficulty_band: 'advanced', suggestedTags: ['topik', 'topik_6', 'tieng_han'] },
      ],
    },
    {
      id: 'general_korean',
      label: 'Tiếng Hàn Tổng Hợp',
      levels: [
        { id: 'korean_beginner', label: 'Tiếng Hàn Sơ cấp 1 - 2', difficulty_band: 'beginner', suggestedTags: ['tieng_han_tong_hop', 'so_cap'] },
        { id: 'korean_intermediate', label: 'Tiếng Hàn Trung cấp 3 - 4', difficulty_band: 'intermediate', suggestedTags: ['tieng_han_tong_hop', 'trung_cap'] },
        { id: 'korean_advanced', label: 'Tiếng Hàn Cao cấp 5 - 6', difficulty_band: 'advanced', suggestedTags: ['tieng_han_tong_hop', 'cao_cap'] },
      ],
    },
    {
      id: 'eps_topik',
      label: 'EPS-TOPIK (XKLĐ)',
      levels: [
        { id: 'eps_manufacturing', label: 'EPS-TOPIK Sản xuất chế tạo', difficulty_band: 'beginner', suggestedTags: ['eps_topik', 'xkld_han'] },
        { id: 'eps_construction', label: 'EPS-TOPIK Xây dựng / Nông nghiệp', difficulty_band: 'beginner', suggestedTags: ['eps_topik', 'nong_nghiep'] },
      ],
    },
  ],
  chinese: [
    {
      id: 'hsk',
      label: 'HSK (Tiêu chuẩn)',
      levels: [
        { id: 'hsk1', label: 'HSK 1 (150 từ)', difficulty_band: 'beginner', suggestedTags: ['hsk', 'hsk1', 'tieng_trung'] },
        { id: 'hsk2', label: 'HSK 2 (300 từ)', difficulty_band: 'beginner', suggestedTags: ['hsk', 'hsk2', 'tieng_trung'] },
        { id: 'hsk3', label: 'HSK 3 (600 từ)', difficulty_band: 'intermediate', suggestedTags: ['hsk', 'hsk3', 'tieng_trung'] },
        { id: 'hsk4', label: 'HSK 4 (1200 từ)', difficulty_band: 'intermediate', suggestedTags: ['hsk', 'hsk4', 'tieng_trung'] },
        { id: 'hsk5', label: 'HSK 5 (2500 từ)', difficulty_band: 'advanced', suggestedTags: ['hsk', 'hsk5', 'tieng_trung'] },
        { id: 'hsk6', label: 'HSK 6 (5000+ từ)', difficulty_band: 'advanced', suggestedTags: ['hsk', 'hsk6', 'tieng_trung'] },
      ],
    },
    {
      id: 'hsk_3_0',
      label: 'HSK 3.0 (9 Cấp)',
      levels: [
        { id: 'hsk3_beginner', label: 'HSK 3.0 Sơ cấp (Cấp 1 - 3)', difficulty_band: 'beginner', suggestedTags: ['hsk3_0', 'so_cap'] },
        { id: 'hsk3_intermediate', label: 'HSK 3.0 Trung cấp (Cấp 4 - 6)', difficulty_band: 'intermediate', suggestedTags: ['hsk3_0', 'trung_cap'] },
        { id: 'hsk3_advanced', label: 'HSK 3.0 Cao cấp (Cấp 7 - 9)', difficulty_band: 'advanced', suggestedTags: ['hsk3_0', 'cao_cap'] },
      ],
    },
    {
      id: 'hskk',
      label: 'HSKK (Khẩu ngữ)',
      levels: [
        { id: 'hskk_primary', label: 'HSKK Sơ cấp', difficulty_band: 'beginner', suggestedTags: ['hskk', 'khau_ngu'] },
        { id: 'hskk_intermediate', label: 'HSKK Trung cấp', difficulty_band: 'intermediate', suggestedTags: ['hskk', 'khau_ngu'] },
        { id: 'hskk_advanced', label: 'HSKK Cao cấp', difficulty_band: 'advanced', suggestedTags: ['hskk', 'khau_ngu'] },
      ],
    },
    {
      id: 'tocfl',
      label: 'TOCFL (Đài Loan / Phồn thể)',
      levels: [
        { id: 'tocfl_band_a', label: 'TOCFL Band A (A1 - A2)', difficulty_band: 'beginner', suggestedTags: ['tocfl', 'phon_the'] },
        { id: 'tocfl_band_b', label: 'TOCFL Band B (B1 - B2)', difficulty_band: 'intermediate', suggestedTags: ['tocfl', 'phon_the'] },
        { id: 'tocfl_band_c', label: 'TOCFL Band C (C1 - C2)', difficulty_band: 'advanced', suggestedTags: ['tocfl', 'phon_the'] },
      ],
    },
  ],
  aws: [
    {
      id: 'aws_certification',
      label: 'AWS Certification',
      levels: [
        { id: 'foundational', label: 'Cloud Practitioner (CCP)', difficulty_band: 'beginner', suggestedTags: ['aws', 'ccp', 'cloud'] },
        { id: 'associate', label: 'Associate (SAA / DVA / SOA)', difficulty_band: 'intermediate', suggestedTags: ['aws', 'saa', 'associate'] },
        { id: 'professional', label: 'Professional (SAP / DOP)', difficulty_band: 'advanced', suggestedTags: ['aws', 'sap', 'professional'] },
        { id: 'specialty', label: 'Specialty (Security / Data / ML)', difficulty_band: 'advanced', suggestedTags: ['aws', 'specialty'] },
      ],
    },
  ],
  azure: [
    {
      id: 'azure_certification',
      label: 'Microsoft Azure',
      levels: [
        { id: 'az_900', label: 'AZ-900 (Fundamentals)', difficulty_band: 'beginner', suggestedTags: ['azure', 'az900', 'cloud'] },
        { id: 'az_104', label: 'AZ-104 (Administrator)', difficulty_band: 'intermediate', suggestedTags: ['azure', 'az104'] },
        { id: 'az_204', label: 'AZ-204 (Developer)', difficulty_band: 'intermediate', suggestedTags: ['azure', 'az204'] },
        { id: 'az_305', label: 'AZ-305 (Solutions Architect)', difficulty_band: 'advanced', suggestedTags: ['azure', 'az305'] },
        { id: 'ai_dp_900', label: 'AI-900 / DP-900 (Data & AI)', difficulty_band: 'beginner', suggestedTags: ['azure', 'ai900', 'dp900'] },
      ],
    },
  ],
  it_coding: [
    {
      id: 'coding_stack',
      label: 'Lập trình & Kỹ năng CNTT',
      levels: [
        { id: 'frontend', label: 'Frontend (React, Vue, TS)', difficulty_band: 'intermediate', suggestedTags: ['frontend', 'react', 'javascript'] },
        { id: 'backend', label: 'Backend (Node.js, Python, Java, Go)', difficulty_band: 'intermediate', suggestedTags: ['backend', 'python', 'nodejs'] },
        { id: 'database', label: 'Database (SQL, MongoDB, Redis)', difficulty_band: 'intermediate', suggestedTags: ['database', 'sql', 'nosql'] },
        { id: 'devops', label: 'DevOps & Cloud (Docker, K8s, Linux)', difficulty_band: 'advanced', suggestedTags: ['devops', 'docker', 'kubernetes'] },
        { id: 'ai_data', label: 'Data Science & AI / ML', difficulty_band: 'advanced', suggestedTags: ['ai', 'machine_learning', 'data_science'] },
        { id: 'dsa_leetcode', label: 'Thuật toán & LeetCode', difficulty_band: 'advanced', suggestedTags: ['dsa', 'leetcode', 'algorithms'] },
      ],
    },
  ],
  thpt_qg: [
    {
      id: 'thpt_exam',
      label: 'Môn thi THPT Quốc Gia',
      levels: [
        { id: 'thpt_math', label: 'Toán học THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'toan_hoc'] },
        { id: 'thpt_physics', label: 'Vật lý THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'vat_ly'] },
        { id: 'thpt_chemistry', label: 'Hóa học THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'hoa_hoc'] },
        { id: 'thpt_biology', label: 'Sinh học THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'sinh_hoc'] },
        { id: 'thpt_history_geo', label: 'Lịch sử & Địa lý THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'lich_su', 'dia_ly'] },
        { id: 'thpt_civic', label: 'GDCD THPT QG', difficulty_band: 'intermediate', suggestedTags: ['thpt_qg', 'gdcd'] },
      ],
    },
  ],
  medical: [
    {
      id: 'medical_field',
      label: 'Y Dược & Thuật ngữ',
      levels: [
        { id: 'med_terms', label: 'Thuật ngữ Y khoa tiếng Anh', difficulty_band: 'intermediate', suggestedTags: ['y_khoa', 'medical_english'] },
        { id: 'anatomy', label: 'Giải phẫu học (Anatomy)', difficulty_band: 'intermediate', suggestedTags: ['giai_phau', 'anatomy'] },
        { id: 'pharmacology', label: 'Dược lý học (Pharmacology)', difficulty_band: 'advanced', suggestedTags: ['duoc_ly', 'pharmacology'] },
      ],
    },
  ],
  law: [
    {
      id: 'law_field',
      label: 'Chuyên ngành Luật',
      levels: [
        { id: 'civil_law', label: 'Luật Dân sự & Hôn nhân', difficulty_band: 'intermediate', suggestedTags: ['luat_dan_su'] },
        { id: 'criminal_law', label: 'Luật Hình sự & Tố tụng', difficulty_band: 'intermediate', suggestedTags: ['luat_hinh_su'] },
        { id: 'business_law', label: 'Luật Doanh nghiệp & Đất đai', difficulty_band: 'advanced', suggestedTags: ['luat_doanh_nghiep'] },
      ],
    },
  ],
  business: [
    {
      id: 'business_field',
      label: 'Kinh doanh & Chứng chỉ nghề',
      levels: [
        { id: 'pmp_agile', label: 'PMP / Scrum Master / Agile', difficulty_band: 'advanced', suggestedTags: ['pmp', 'scrum', 'agile'] },
        { id: 'cfa_acca', label: 'CFA / ACCA / Tài chính', difficulty_band: 'advanced', suggestedTags: ['cfa', 'acca', 'tai_chinh'] },
        { id: 'digital_mkt', label: 'Digital Marketing & SEO', difficulty_band: 'intermediate', suggestedTags: ['marketing', 'seo'] },
      ],
    },
  ],
}

export const TAXONOMY_DIFFICULTIES = [
  { id: 'beginner', label: 'Sơ cấp (Beginner)' },
  { id: 'intermediate', label: 'Trung cấp (Intermediate)' },
  { id: 'advanced', label: 'Nâng cao (Advanced)' },
]

export const TAXONOMY_LEARNING_GOALS = [
  { id: 'vocabulary', label: 'Từ vựng' },
  { id: 'kanji', label: 'Kanji / Hán tự' },
  { id: 'grammar', label: 'Ngữ pháp' },
  { id: 'reading', label: 'Đọc hiểu' },
  { id: 'listening', label: 'Luyện nghe' },
  { id: 'speaking', label: 'Luyện nói' },
  { id: 'writing', label: 'Luyện viết' },
  { id: 'exam_prep', label: 'Luyện thi' },
  { id: 'daily_communication', label: 'Giao tiếp hàng ngày' },
  { id: 'drill', label: 'Ôn tập nhanh' },
  { id: 'concept_recall', label: 'Nhớ khái niệm' },
  { id: 'service_comparison', label: 'So sánh dịch vụ' },
  { id: 'scenario_practice', label: 'Luyện tình huống' },
  { id: 'architecture_review', label: 'Ôn kiến trúc' },
  { id: 'formula_mastery', label: 'Nắm vững công thức' },
  { id: 'problem_solving', label: 'Giải bài tập / Case study' },
  { id: 'code_implementation', label: 'Viết mã & Thực hành' },
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
  { id: 'academic_english', label: 'Học thuật' },
  { id: 'business_english', label: 'Tiếng Anh công việc' },
  { id: 'hanzi', label: 'Hanzi / Hán tự' },
  { id: 'pinyin', label: 'Pinyin' },
  { id: 'furigana', label: 'Furigana' },
  { id: 'compute', label: 'Compute' },
  { id: 'storage', label: 'Storage' },
  { id: 'networking', label: 'Networking' },
  { id: 'iam', label: 'IAM' },
  { id: 'security', label: 'Security' },
  { id: 'databases', label: 'Databases' },
  { id: 'serverless', label: 'Serverless' },
  { id: 'monitoring', label: 'Monitoring' },
  { id: 'architecture_concepts', label: 'Khái niệm kiến trúc' },
  { id: 'code_syntax', label: 'Cú pháp & Snippets' },
  { id: 'algorithms_dsa', label: 'Cấu trúc dữ liệu & Thuật toán' },
  { id: 'frontend_web', label: 'Frontend & Web' },
  { id: 'backend_api', label: 'Backend & API' },
  { id: 'devops_cloud', label: 'DevOps & Cloud' },
  { id: 'math_formulas', label: 'Công thức Toán' },
  { id: 'physics_laws', label: 'Định luật Vật lý' },
  { id: 'chemistry_reactions', label: 'Phản ứng Hóa học' },
  { id: 'biology_genetics', label: 'Sinh học & Di truyền' },
  { id: 'history_events', label: 'Sự kiện Lịch sử' },
  { id: 'geography_facts', label: 'Địa lý' },
  { id: 'medical_terms', label: 'Thuật ngữ Y khoa' },
  { id: 'anatomy', label: 'Giải phẫu học' },
  { id: 'pharmacology', label: 'Dược lý & Thuốc' },
  { id: 'law_clauses', label: 'Điều luật & Pháp điển' },
  { id: 'legal_cases', label: 'Án lệ & Tố tụng' },
  { id: 'project_management', label: 'Quản trị dự án / Agile' },
  { id: 'finance_accounting', label: 'Tài chính & Kế toán' },
  { id: 'marketing_sales', label: 'Marketing & Bán hàng' },
]

export type TopicItem = {
  id: string
  label: string
  sub?: string
}

export type LearningGoalItem = {
  id: string
  label: string
  sub?: string
}

export const TAXONOMY_SUBJECT_TOPICS: Record<string, TopicItem[]> = {
  // --- Ngôn ngữ (Language Learning) ---
  japanese: [
    { id: 'meaning_recall', label: 'Nhớ nghĩa từ vựng', sub: 'Flashcard từ vựng song ngữ' },
    { id: 'reading_recall', label: 'Cách đọc Onyomi / Kunyomi', sub: 'Âm Hán & âm thuần Nhật' },
    { id: 'furigana', label: 'Kanji & Furigana', sub: 'Mặt chữ Hán tự & phiên âm' },
    { id: 'sentence_patterns', label: 'Mẫu câu & Ngữ pháp', sub: 'Bunpou JLPT theo cấp' },
    { id: 'conversation', label: 'Hội thoại & Kaiwa', sub: 'Giao tiếp tình huống thực tế' },
    { id: 'audio_recognition', label: 'Luyện nghe Choukai', sub: 'Nhận diện âm thanh & phản xạ' },
    { id: 'daily_life', label: 'Đời sống & Văn hóa Nhật', sub: 'Sinh hoạt & phong tục' },
    { id: 'business', label: 'Kính ngữ Keigo & Tiếng Nhật công sở', sub: 'Thương mại BJT & email' },
    { id: 'travel', label: 'Du lịch & Hỏi đường', sub: 'Giao tiếp du lịch nhanh' },
  ],
  english: [
    { id: 'meaning_recall', label: 'Từ vựng cốt lõi (Oxford 3000/5000)', sub: 'Định nghĩa & ví dụ thực tế' },
    { id: 'sentence_patterns', label: 'Ngữ pháp & Cấu trúc câu', sub: 'Grammar in Use & mệnh đề' },
    { id: 'academic_english', label: 'Tiếng Anh học thuật & IELTS', sub: 'Collocations, Task 1 & Task 2' },
    { id: 'business_english', label: 'Tiếng Anh công việc & TOEIC', sub: 'Email, đàm phán & phỏng vấn' },
    { id: 'audio_recognition', label: 'Phát âm IPA & Luyện nghe', sub: 'Phonics, nối âm & phản xạ' },
    { id: 'conversation', label: 'Hội thoại & Giao tiếp tự nhiên', sub: 'Daily Communication & Idioms' },
    { id: 'travel', label: 'Tiếng Anh du lịch & Sân bay', sub: 'Tình huống du lịch nước ngoài' },
  ],
  chinese: [
    { id: 'hanzi', label: 'Hán tự & Thứ tự nét', sub: 'Chữ Hán giản thể & phồn thể' },
    { id: 'pinyin', label: 'Pinyin & Thanh điệu', sub: 'Bảng phiên âm chuẩn Bắc Kinh' },
    { id: 'meaning_recall', label: 'Từ vựng HSK / TOCFL', sub: 'Nghĩa Hán Việt & Thuần Việt' },
    { id: 'sentence_patterns', label: 'Ngữ pháp & Mẫu câu tiếng Trung', sub: 'Cấu trúc câu, liên từ, phó từ' },
    { id: 'audio_recognition', label: 'Luyện nghe nhận âm', sub: 'Phân biệt thanh điệu 1, 2, 3, 4' },
    { id: 'conversation', label: 'Khẩu ngữ & Giao tiếp (HSKK)', sub: 'Hội thoại đời sống thực tế' },
    { id: 'business', label: 'Tiếng Trung thương mại & Đàm phán', sub: 'Giao thương & văn phòng' },
  ],
  korean: [
    { id: 'meaning_recall', label: 'Từ vựng TOPIK I & II', sub: 'Từ vựng theo chủ đề đời sống' },
    { id: 'reading_recall', label: 'Bảng chữ cái Hangul & Phát âm', sub: 'Quy tắc biến âm & nối âm' },
    { id: 'sentence_patterns', label: 'Đuôi câu & Ngữ pháp TOPIK', sub: 'Cấu trúc kính ngữ & liên kết câu' },
    { id: 'audio_recognition', label: 'Luyện nghe tiếng Hàn', sub: 'Nghe hội thoại theo cấp độ' },
    { id: 'conversation', label: 'Hội thoại & Giao tiếp đời sống', sub: 'Giao tiếp hàng ngày, K-Drama' },
    { id: 'business', label: 'Tiếng Hàn văn phòng & XKLĐ (EPS)', sub: 'Từ vựng chuyên ngành & nhà xưởng' },
  ],

  // --- Chứng chỉ Điện toán đám mây & Quốc tế (Certification) ---
  aws: [
    { id: 'compute', label: 'Compute (EC2, Lambda, ECS, EKS)', sub: 'Điện toán máy chủ & Serverless' },
    { id: 'storage', label: 'Storage (S3, EBS, EFS)', sub: 'Lưu trữ đối tượng, block & file' },
    { id: 'databases', label: 'Databases (RDS, DynamoDB, Aurora)', sub: 'CSDL SQL quan hệ & NoSQL' },
    { id: 'networking', label: 'Networking (VPC, CloudFront, Route53)', sub: 'Mạng riêng ảo, CDN & định tuyến' },
    { id: 'iam', label: 'Identity & Access (IAM, Cognito)', sub: 'Phân quyền, vai trò & định danh' },
    { id: 'security', label: 'Security & KMS Encryption', sub: 'Bảo mật dữ liệu & quản lý khóa' },
    { id: 'serverless', label: 'Serverless (EventBridge, SQS, SNS)', sub: 'Kiến trúc bất đồng bộ hướng sự kiện' },
    { id: 'monitoring', label: 'Monitoring (CloudWatch, X-Ray)', sub: 'Giám sát, log & truy vết lỗi' },
    { id: 'architecture_concepts', label: 'AWS Well-Architected Framework', sub: 'Kiến trúc tối ưu chi phí & sẵn sàng cao' },
  ],
  azure: [
    { id: 'compute', label: 'Azure Compute (VMs, App Services, Functions)', sub: 'Dịch vụ điện toán đám mây' },
    { id: 'storage', label: 'Azure Storage (Blob, Disk, Files)', sub: 'Lưu trữ đám mây Microsoft' },
    { id: 'databases', label: 'Azure SQL & Cosmos DB', sub: 'Cơ sở dữ liệu đám mây đa mô hình' },
    { id: 'networking', label: 'Virtual Networks & Load Balancer', sub: 'Mạng riêng ảo & cân bằng tải' },
    { id: 'iam', label: 'Microsoft Entra ID (Azure AD)', sub: 'Xác thực & Quản lý danh tính người dùng' },
    { id: 'security', label: 'Microsoft Defender for Cloud & Sentinel', sub: 'Trung tâm cảnh báo an ninh' },
    { id: 'serverless', label: 'Serverless (Logic Apps, Event Grid)', sub: 'Tự động hóa luồng nghiệp vụ' },
    { id: 'monitoring', label: 'Azure Monitor & Log Analytics', sub: 'Giám sát hiệu năng & phân tích log' },
    { id: 'architecture_concepts', label: 'Cloud Adoption Framework (CAF)', sub: 'Khung triển khai kiến trúc chuẩn' },
  ],
  other_certification: [
    { id: 'architecture_concepts', label: 'Kiến trúc & Khái niệm cốt lõi', sub: 'Lý thuyết chuẩn quốc tế' },
    { id: 'security', label: 'Bảo mật, Rủi ro & Tuân thủ', sub: 'Security & Compliance' },
    { id: 'databases', label: 'Cơ sở dữ liệu & Quản trị hệ thống', sub: 'Database Administration' },
    { id: 'project_management', label: 'Quy trình chuẩn & Quản trị', sub: 'Standard Frameworks' },
    { id: 'meaning_recall', label: 'Thuật ngữ & Cheat sheet', sub: 'Tra cứu nhanh định nghĩa' },
  ],

  // --- Kỹ năng nghề nghiệp (Professional Skills) ---
  it_coding: [
    { id: 'code_syntax', label: 'Cú pháp ngôn ngữ & Code Snippets', sub: 'Python, TypeScript, JS, Go, Java, C#' },
    { id: 'algorithms_dsa', label: 'Cấu trúc dữ liệu & Thuật toán', sub: 'LeetCode, Big-O, Đệ quy, DP' },
    { id: 'frontend_web', label: 'Frontend & UI Frameworks', sub: 'React, Next.js, Vue, Tailwind, DOM' },
    { id: 'backend_api', label: 'Backend & RESTful / GraphQL API', sub: 'Node.js, Flask, Spring Boot, Microservices' },
    { id: 'databases', label: 'Database Design & SQL Queries', sub: 'Indexing, Joins, Transactions, ORM' },
    { id: 'devops_cloud', label: 'DevOps, Docker, K8s & Linux', sub: 'Container, CI/CD pipeline, Terminal' },
    { id: 'architecture_concepts', label: 'Design Patterns & Clean Code', sub: 'SOLID, Clean Architecture, Refactoring' },
    { id: 'security', label: 'Web Security & OWASP Top 10', sub: 'JWT, CORS, XSS, CSRF, Injection' },
  ],
  business: [
    { id: 'project_management', label: 'Quản trị dự án & Agile / Scrum', sub: 'PMP, Sprint Planning, Jira, Kanban' },
    { id: 'finance_accounting', label: 'Tài chính, Kế toán & Đầu tư', sub: 'CFA, ACCA, Báo cáo tài chính, Dòng tiền' },
    { id: 'marketing_sales', label: 'Digital Marketing, SEO & Phễu bán hàng', sub: 'Performance Ads, Content Strategy, CRO' },
    { id: 'business', label: 'Quản trị doanh nghiệp & Đàm phán', sub: 'Chiến lược kinh doanh, Vận hành, KPI' },
    { id: 'conversation', label: 'Kỹ năng giao tiếp & Thuyết trình', sub: 'Pitching, Trình bày ý tưởng, Storytelling' },
  ],

  // --- Học thuật & Thi cử (Academic) ---
  thpt_qg: [
    { id: 'math_formulas', label: 'Công thức Toán học trọng tâm', sub: 'Hàm số, Tích phân, Hình học Oxyz, Tổ hợp' },
    { id: 'physics_laws', label: 'Định luật & Hiện tượng Vật lý', sub: 'Dao động cơ, Sóng, Điện xoay chiều, Hạt nhân' },
    { id: 'chemistry_reactions', label: 'Phương trình & Chuỗi phản ứng Hóa học', sub: 'Este, Lipit, Peptit, Kim loại, Vô cơ' },
    { id: 'biology_genetics', label: 'Sinh học tế bào & Quy luật Di truyền', sub: 'Cơ chế di truyền, Đột biến, Sinh thái' },
    { id: 'history_events', label: 'Mốc sự kiện Lịch sử VN & Thế giới', sub: 'Niên đại, Ý nghĩa lịch sử & Chiến dịch' },
    { id: 'geography_facts', label: 'Địa lý tự nhiên & Vùng kinh tế', sub: 'Khai thác Atlat, Khí hậu, Ngành kinh tế' },
    { id: 'academic_english', label: 'Ngữ pháp & Đọc hiểu tiếng Anh THPT', sub: 'Cấu trúc câu & Cụm từ hay gặp trong đề thi' },
  ],
  medical: [
    { id: 'medical_terms', label: 'Thuật ngữ Y khoa tiếng Anh', sub: 'Gốc từ, Tiền tố, Hậu tố Y học quốc tế' },
    { id: 'anatomy', label: 'Giải phẫu học (Anatomy)', sub: 'Hệ cơ quan, Xương, Mạch máu, Dây thần kinh' },
    { id: 'pharmacology', label: 'Dược lý học & Cơ chế tác dụng của thuốc', sub: 'Dược động học, Chỉ định, Tác dụng phụ' },
    { id: 'meaning_recall', label: 'Bệnh học & Triệu chứng lâm sàng', sub: 'Chẩn đoán phân biệt & Cơ chế bệnh sinh' },
    { id: 'concept_recall', label: 'Sinh lý học & Miễn dịch học', sub: 'Cơ chế cân bằng nội môi & Đáp ứng miễn dịch' },
  ],
  law: [
    { id: 'law_clauses', label: 'Điều luật & Bộ luật trọng tâm', sub: 'Bộ luật Dân sự, Hình sự, Đất đai, Lao động' },
    { id: 'legal_cases', label: 'Án lệ & Quy trình Tố tụng', sub: 'Thủ tục Tố tụng Dân sự & Tố tụng Hình sự' },
    { id: 'business', label: 'Luật Doanh nghiệp & Hợp đồng thương mại', sub: 'Thành lập công ty, Giải quyết tranh chấp' },
    { id: 'meaning_recall', label: 'Thuật ngữ Pháp lý & Khái niệm Luật học', sub: 'Định nghĩa văn bản quy phạm pháp luật' },
  ],
  science: [
    { id: 'math_formulas', label: 'Toán cao cấp, Đại số & Xác suất thống kê', sub: 'Ma trận, Không gian Vector, Tích phân mặt' },
    { id: 'physics_laws', label: 'Vật lý đại cương & Cơ học lượng tử', sub: 'Cơ học, Nhiệt động lực học, Quang học' },
    { id: 'chemistry_reactions', label: 'Hóa học đại cương & Hóa lý', sub: 'Nhiệt hóa học, Động hóa học, Điện hóa' },
    { id: 'architecture_concepts', label: 'Mô hình khoa học & Lý thuyết thực nghiệm', sub: 'Phương pháp luận nghiên cứu' },
  ],

  // --- Khác (Other) ---
  other: [
    { id: 'meaning_recall', label: 'Nhớ nghĩa & Khái niệm tổng quát', sub: 'Flashcard 2 mặt định nghĩa' },
    { id: 'daily_life', label: 'Thường thức đời sống & Đố vui', sub: 'Kiến thức xã hội tổng hợp' },
    { id: 'conversation', label: 'Hội thoại & Giao tiếp', sub: 'Kỹ năng giao tiếp ứng xử' },
    { id: 'travel', label: 'Du lịch, Địa lý & Văn hóa', sub: 'Khám phá thế giới' },
    { id: 'business', label: 'Kỹ năng công việc & Năng suất', sub: 'Workplace Skills' },
  ],
}

export const TAXONOMY_SUBJECT_LEARNING_GOALS: Record<string, LearningGoalItem[]> = {
  // Languages
  japanese: [
    { id: 'vocabulary', label: 'Từ vựng (Tango)', sub: 'Nghĩa & phát âm âm On/Kun' },
    { id: 'kanji', label: 'Kanji / Hán tự', sub: 'Nét viết & bộ thủ' },
    { id: 'grammar', label: 'Ngữ pháp (Bunpou)', sub: 'Mẫu câu & liên kết ngữ pháp' },
    { id: 'reading', label: 'Đọc hiểu (Dokkai)', sub: 'Đoạn văn ngắn, trung, trường cú' },
    { id: 'listening', label: 'Luyện nghe (Choukai)', sub: 'Phản xạ audio tự nhiên' },
    { id: 'speaking', label: 'Luyện nói & Kaiwa', sub: 'Phản xạ giao tiếp thực tế' },
    { id: 'exam_prep', label: 'Luyện thi JLPT / NAT-TEST', sub: 'Từ N5 đến N1' },
    { id: 'daily_communication', label: 'Giao tiếp hàng ngày', sub: 'Đời sống Nhật Bản' },
  ],
  english: [
    { id: 'vocabulary', label: 'Từ vựng (Vocabulary)', sub: 'Định nghĩa, IPA & Collocation' },
    { id: 'grammar', label: 'Ngữ pháp (Grammar)', sub: 'Thì, mệnh đề quan hệ, câu điều kiện' },
    { id: 'reading', label: 'Đọc hiểu (Reading)', sub: 'Kỹ năng Skimming & Scanning' },
    { id: 'listening', label: 'Luyện nghe (Listening)', sub: 'Bắt từ khóa, Shadowing' },
    { id: 'speaking', label: 'Luyện nói (Speaking)', sub: 'Lưu loát & Phát âm Phonics' },
    { id: 'writing', label: 'Luyện viết (Writing)', sub: 'Essay, Task 1, Task 2' },
    { id: 'exam_prep', label: 'Luyện thi IELTS / TOEIC / VSTEP', sub: 'Chiến thuật giải đề thi' },
    { id: 'daily_communication', label: 'Giao tiếp công sở & đời sống', sub: 'Hội thoại tự tin' },
  ],
  chinese: [
    { id: 'vocabulary', label: 'Từ vựng (Từ mới HSK)', sub: 'Âm Pinyin & Giải nghĩa' },
    { id: 'kanji', label: 'Chữ Hán (Hanzi)', sub: 'Bộ thủ & Thứ tự nét viết' },
    { id: 'grammar', label: 'Ngữ pháp tiếng Trung', sub: 'Bổ ngữ kết quả, lượng từ, phó từ' },
    { id: 'reading', label: 'Đọc hiểu tiếng Trung', sub: 'Đọc đoạn văn không có pinyin' },
    { id: 'listening', label: 'Luyện nghe (Tingli)', sub: 'Nhận diện thanh điệu & từ vựng' },
    { id: 'speaking', label: 'Khẩu ngữ (Kouyu)', sub: 'Phản xạ giao tiếp HSKK' },
    { id: 'exam_prep', label: 'Luyện thi HSK / HSKK / TOCFL', sub: 'Cấp độ 1 đến Cấp 9' },
  ],
  korean: [
    { id: 'vocabulary', label: 'Từ vựng tiếng Hàn', sub: 'Từ vựng theo chủ đề đời sống' },
    { id: 'grammar', label: 'Ngữ pháp & Đuôi câu', sub: 'Đuôi kính ngữ, liên từ' },
    { id: 'reading', label: 'Đọc hiểu TOPIK', sub: 'Đọc bài báo & đoạn văn ngắn' },
    { id: 'listening', label: 'Luyện nghe tiếng Hàn', sub: 'Nghe hội thoại audio' },
    { id: 'speaking', label: 'Luyện nói tiếng Hàn', sub: 'Giao tiếp thực tế hàng ngày' },
    { id: 'exam_prep', label: 'Luyện thi TOPIK / EPS-TOPIK', sub: 'TOPIK I & II' },
  ],

  // Cloud & Tech
  aws: [
    { id: 'concept_recall', label: 'Nhớ khái niệm dịch vụ AWS', sub: 'Đặc tính, giới hạn & use cases' },
    { id: 'service_comparison', label: 'So sánh dịch vụ', sub: 'Khi nào chọn dịch vụ phù hợp' },
    { id: 'scenario_practice', label: 'Luyện câu hỏi tình huống', sub: 'Dạng đề thi chứng chỉ thực tế' },
    { id: 'architecture_review', label: 'Ôn kiến trúc hệ thống', sub: 'AWS Well-Architected Framework' },
    { id: 'exam_prep', label: 'Luyện thi chứng chỉ AWS', sub: 'CCP, SAA, SAP, DVA, Security...' },
    { id: 'drill', label: 'Ôn tập nhanh Flashcard', sub: 'Lặp lại ngắt quãng Spaced Repetition' },
  ],
  azure: [
    { id: 'concept_recall', label: 'Nhớ khái niệm dịch vụ Azure', sub: 'Resource groups, VMs, Blob, Entra' },
    { id: 'service_comparison', label: 'So sánh giải pháp Microsoft', sub: 'Lựa chọn SKU & kiến trúc phù hợp' },
    { id: 'scenario_practice', label: 'Luyện câu hỏi tình huống thi', sub: 'Case studies thực tế' },
    { id: 'architecture_review', label: 'Ôn kiến trúc Cloud Adoption', sub: 'Security, Governance & Scale' },
    { id: 'exam_prep', label: 'Luyện thi chứng chỉ Azure', sub: 'AZ-900, AZ-104, AZ-204, AZ-305...' },
    { id: 'drill', label: 'Ôn tập nhanh Flashcard', sub: 'Drill thuật ngữ nhanh' },
  ],
  other_certification: [
    { id: 'concept_recall', label: 'Nhớ khái niệm chuyên môn', sub: 'Lý thuyết & Khung chuẩn quốc tế' },
    { id: 'scenario_practice', label: 'Luyện câu hỏi tình huống', sub: 'Bài tập thực tế dạng đề' },
    { id: 'exam_prep', label: 'Luyện thi chứng chỉ quốc tế', sub: 'Đề mẫu & Bí quyết thi đạt điểm cao' },
    { id: 'drill', label: 'Ôn tập nhanh tốc độ cao', sub: 'Flashcard lặp lại' },
  ],

  // IT & Coding
  it_coding: [
    { id: 'code_implementation', label: 'Viết mã & Cú pháp thực hành', sub: 'Cú pháp ngôn ngữ & Frameworks' },
    { id: 'concept_recall', label: 'Nhớ khái niệm & Nguyên lý thiết kế', sub: 'OOP, Functional, SOLID, Clean Code' },
    { id: 'problem_solving', label: 'Giải thuật toán / LeetCode', sub: 'Tư duy logic & Giải thuật' },
    { id: 'scenario_practice', label: 'Luyện tình huống kỹ thuật', sub: 'System Design & Debugging' },
    { id: 'drill', label: 'Drill nhanh phím tắt & API', sub: 'Ghi nhớ hàm thư viện' },
    { id: 'exam_prep', label: 'Luyện phỏng vấn lập trình viên', sub: 'Technical Interview questions' },
  ],
  business: [
    { id: 'concept_recall', label: 'Nhớ mô hình & Khái niệm kinh doanh', sub: 'KPI, ROI, OKR, SWOT, P&L' },
    { id: 'problem_solving', label: 'Giải bài tập & Case study quản trị', sub: 'Phân tích tình huống kinh doanh' },
    { id: 'scenario_practice', label: 'Luyện tình huống đàm phán & quản trị', sub: 'Xử lý khủng hoảng & ra quyết định' },
    { id: 'exam_prep', label: 'Luyện thi chứng chỉ PMP / CFA / ACCA', sub: 'Đề thi chuẩn quốc tế' },
    { id: 'daily_communication', label: 'Giao tiếp & Thuyết trình doanh nghiệp', sub: 'Kỹ năng lãnh đạo' },
  ],

  // Academic
  thpt_qg: [
    { id: 'formula_mastery', label: 'Nắm vững công thức cốt lõi', sub: 'Toán, Lý, Hóa, Sinh' },
    { id: 'concept_recall', label: 'Nhớ lý thuyết & Mốc sự kiện', sub: 'Lịch sử, Địa lý, GDCD' },
    { id: 'problem_solving', label: 'Giải bài tập & Dạng đề thi', sub: 'Phương pháp giải trắc nghiệm nhanh' },
    { id: 'exam_prep', label: 'Luyện thi THPT Quốc Gia', sub: 'Mục tiêu điểm số 8+ đến 9+' },
    { id: 'drill', label: 'Drill nhanh phản xạ trắc nghiệm', sub: 'Luyện đề bấm giờ' },
  ],
  medical: [
    { id: 'vocabulary', label: 'Thuật ngữ Y khoa chuyên ngành', sub: 'Gốc từ & Tên quốc tế' },
    { id: 'concept_recall', label: 'Nhớ cơ chế sinh lý & bệnh sinh', sub: 'Nguyên nhân & Triệu chứng bệnh' },
    { id: 'scenario_practice', label: 'Luyện ca lâm sàng & Chẩn đoán', sub: 'Tình huống bệnh án thực tế' },
    { id: 'exam_prep', label: 'Luyện thi Y Dược & Nội trú', sub: 'Câu hỏi chuyên ngành y khoa' },
    { id: 'drill', label: 'Drill nhanh tên thuốc & Liều lượng', sub: 'Dược lý học thực hành' },
  ],
  law: [
    { id: 'concept_recall', label: 'Nhớ điều luật & Khái niệm pháp lý', sub: 'Quy định pháp luật hiện hành' },
    { id: 'scenario_practice', label: 'Phân tích án lệ & Tình huống tranh chấp', sub: 'Áp dụng luật thực tế' },
    { id: 'problem_solving', label: 'Tư vấn & Soạn thảo pháp lý', sub: 'Hợp đồng & Văn bản pháp quy' },
    { id: 'exam_prep', label: 'Luyện thi Luật sư / Công chức', sub: 'Nghiệp vụ pháp lý chuyên sâu' },
    { id: 'drill', label: 'Ôn tập nhanh điều khoản luật', sub: 'Tra cứu & Ghi nhớ' },
  ],
  science: [
    { id: 'formula_mastery', label: 'Nắm vững công thức & Định lý', sub: 'Toán cao cấp, Vật lý, Hóa học' },
    { id: 'concept_recall', label: 'Nhớ mô hình lý thuyết', sub: 'Nguyên lý khoa học tự nhiên' },
    { id: 'problem_solving', label: 'Giải bài toán chứng minh & Định lượng', sub: 'Tư duy toán học & thực nghiệm' },
    { id: 'exam_prep', label: 'Luyện thi học phần đại học / Olympic', sub: 'Nâng cao trình độ' },
  ],

  // Fallback
  other: [
    { id: 'concept_recall', label: 'Nhớ khái niệm cốt lõi', sub: 'Kiến thức nền tảng' },
    { id: 'vocabulary', label: 'Thuật ngữ & Từ vựng', sub: 'Nghĩa và cách áp dụng' },
    { id: 'scenario_practice', label: 'Luyện tình huống thực tế', sub: 'Kỹ năng thực hành' },
    { id: 'daily_communication', label: 'Giao tiếp hàng ngày', sub: 'Ứng xử & Xã hội' },
    { id: 'drill', label: 'Ôn tập nhanh ngắt quãng', sub: 'Flashcard Spaced Repetition' },
    { id: 'exam_prep', label: 'Luyện thi & Đánh giá năng lực', sub: 'Kiểm tra kiến thức' },
  ],
}

/**
 * Returns the relevant primary topics for a selected subject (or domain fallback).
 */
export function getTopicsForSubject(subjectId: string, domainId?: string): TopicItem[] {
  if (TAXONOMY_SUBJECT_TOPICS[subjectId]) {
    return TAXONOMY_SUBJECT_TOPICS[subjectId]
  }
  if (domainId && TAXONOMY_SUBJECT_TOPICS[domainId]) {
    return TAXONOMY_SUBJECT_TOPICS[domainId]
  }
  return TAXONOMY_SUBJECT_TOPICS.other
}

/**
 * Returns the relevant learning goals for a selected subject (or domain fallback).
 */
export function getGoalsForSubject(subjectId: string, domainId?: string): LearningGoalItem[] {
  if (TAXONOMY_SUBJECT_LEARNING_GOALS[subjectId]) {
    return TAXONOMY_SUBJECT_LEARNING_GOALS[subjectId]
  }
  if (domainId && TAXONOMY_SUBJECT_LEARNING_GOALS[domainId]) {
    return TAXONOMY_SUBJECT_LEARNING_GOALS[domainId]
  }
  return TAXONOMY_SUBJECT_LEARNING_GOALS.other
}

/**
 * Returns sensible default learning goal IDs when switching subjects.
 */
export function getDefaultGoalsForSubject(subjectId: string): string[] {
  const goals = getGoalsForSubject(subjectId)
  if (goals.length === 0) return ['vocabulary']
  // Pick first 1 or 2 goals as default
  return goals.slice(0, Math.min(2, goals.length)).map((g) => g.id)
}

/**
 * Returns sensible default primary topic IDs when switching subjects.
 */
export function getDefaultTopicsForSubject(subjectId: string): string[] {
  const topics = getTopicsForSubject(subjectId)
  if (topics.length === 0) return ['meaning_recall']
  // Pick first topic as default
  return [topics[0].id]
}
