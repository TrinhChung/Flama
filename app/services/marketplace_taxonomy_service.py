from __future__ import annotations

import logging
from typing import Any
from sqlalchemy.orm import Session
from app.repositories import marketplace_taxonomy_repository

logger = logging.getLogger(__name__)

# Static fallbacks / constants
DOMAIN_OPTIONS = (
    {"id": "language_learning", "label": "Ngôn ngữ"},
    {"id": "certification", "label": "Chứng chỉ"},
    {"id": "professional_skills", "label": "Kỹ năng nghề nghiệp"},
    {"id": "academic", "label": "Học thuật"},
    {"id": "other", "label": "Khác"},
)

SUBJECT_OPTIONS = (
    {"id": "japanese", "label": "Tiếng Nhật", "domain": "language_learning"},
    {"id": "english", "label": "Tiếng Anh", "domain": "language_learning"},
    {"id": "chinese", "label": "Tiếng Trung", "domain": "language_learning"},
    {"id": "korean", "label": "Tiếng Hàn", "domain": "language_learning"},
    {"id": "aws", "label": "AWS Cloud", "domain": "certification"},
    {"id": "azure", "label": "Microsoft Azure", "domain": "certification"},
    {"id": "other_certification", "label": "Chứng chỉ khác", "domain": "certification"},
    {"id": "it_coding", "label": "CNTT & Lập trình", "domain": "professional_skills"},
    {"id": "business", "label": "Kinh doanh & Quản lý", "domain": "professional_skills"},
    {"id": "thpt_qg", "label": "Luyện thi THPT Quốc Gia", "domain": "academic"},
    {"id": "medical", "label": "Y dược", "domain": "academic"},
    {"id": "law", "label": "Luật", "domain": "academic"},
    {"id": "science", "label": "Khoa học tự nhiên", "domain": "academic"},
    {"id": "other", "label": "Khác", "domain": "other"},
)

DIFFICULTY_OPTIONS = (
    {"id": "beginner", "label": "Sơ cấp"},
    {"id": "intermediate", "label": "Trung cấp"},
    {"id": "advanced", "label": "Nâng cao"},
)

AUDIENCE_OPTIONS = (
    {"id": "self_study", "label": "Tự học"},
    {"id": "exam_learner", "label": "Người học luyện thi"},
    {"id": "beginner_learner", "label": "Người mới bắt đầu"},
    {"id": "working_professional", "label": "Người đi làm"},
    {"id": "classroom_support", "label": "Hỗ trợ lớp học"},
)

LEARNING_GOAL_OPTIONS = (
    {"id": "vocabulary", "label": "Từ vựng"},
    {"id": "kanji", "label": "Kanji / Hán tự"},
    {"id": "grammar", "label": "Ngữ pháp"},
    {"id": "reading", "label": "Đọc hiểu"},
    {"id": "listening", "label": "Luyện nghe"},
    {"id": "speaking", "label": "Luyện nói"},
    {"id": "writing", "label": "Luyện viết"},
    {"id": "exam_prep", "label": "Luyện thi"},
    {"id": "daily_communication", "label": "Giao tiếp hằng ngày"},
    {"id": "drill", "label": "Ôn tập nhanh"},
    {"id": "concept_recall", "label": "Nhớ khái niệm"},
    {"id": "service_comparison", "label": "So sánh dịch vụ"},
    {"id": "scenario_practice", "label": "Luyện tình huống"},
    {"id": "architecture_review", "label": "Ôn kiến trúc"},
    {"id": "formula_mastery", "label": "Nắm vững công thức"},
    {"id": "problem_solving", "label": "Giải bài tập / Case study"},
    {"id": "code_implementation", "label": "Viết mã & Thực hành"},
)

TOPIC_OPTIONS = (
    {"id": "meaning_recall", "label": "Nhớ nghĩa"},
    {"id": "reading_recall", "label": "Nhớ cách đọc"},
    {"id": "sentence_patterns", "label": "Mẫu câu"},
    {"id": "audio_recognition", "label": "Nghe nhận diện"},
    {"id": "daily_life", "label": "Đời sống hằng ngày"},
    {"id": "conversation", "label": "Hội thoại"},
    {"id": "travel", "label": "Du lịch"},
    {"id": "business", "label": "Công việc"},
    {"id": "academic_english", "label": "Học thuật"},
    {"id": "business_english", "label": "Tiếng Anh công việc"},
    {"id": "hanzi", "label": "Hanzi / Hán tự"},
    {"id": "pinyin", "label": "Pinyin"},
    {"id": "furigana", "label": "Furigana"},
    {"id": "compute", "label": "Compute"},
    {"id": "storage", "label": "Storage"},
    {"id": "networking", "label": "Networking"},
    {"id": "iam", "label": "IAM"},
    {"id": "security", "label": "Security"},
    {"id": "databases", "label": "Databases"},
    {"id": "serverless", "label": "Serverless"},
    {"id": "monitoring", "label": "Monitoring"},
    {"id": "architecture_concepts", "label": "Khái niệm kiến trúc"},
    {"id": "code_syntax", "label": "Cú pháp & Snippets"},
    {"id": "algorithms_dsa", "label": "Cấu trúc dữ liệu & Thuật toán"},
    {"id": "frontend_web", "label": "Frontend & Web"},
    {"id": "backend_api", "label": "Backend & API"},
    {"id": "devops_cloud", "label": "DevOps & Cloud"},
    {"id": "math_formulas", "label": "Công thức Toán"},
    {"id": "physics_laws", "label": "Định luật Vật lý"},
    {"id": "chemistry_reactions", "label": "Phản ứng Hóa học"},
    {"id": "biology_genetics", "label": "Sinh học & Di truyền"},
    {"id": "history_events", "label": "Sự kiện Lịch sử"},
    {"id": "geography_facts", "label": "Địa lý"},
    {"id": "medical_terms", "label": "Thuật ngữ Y khoa"},
    {"id": "anatomy", "label": "Giải phẫu học"},
    {"id": "pharmacology", "label": "Dược lý & Thuốc"},
    {"id": "law_clauses", "label": "Điều luật & Pháp điển"},
    {"id": "legal_cases", "label": "Án lệ & Tố tụng"},
    {"id": "project_management", "label": "Quản trị dự án / Agile"},
    {"id": "finance_accounting", "label": "Tài chính & Kế toán"},
    {"id": "marketing_sales", "label": "Marketing & Bán hàng"},
)

FORMAT_FEATURE_OPTIONS = (
    {"id": "audio", "label": "Có audio"},
    {"id": "example_sentences", "label": "Có ví dụ"},
    {"id": "image_based", "label": "Học bằng hình"},
    {"id": "cloze", "label": "Cloze"},
    {"id": "exam_style", "label": "Dạng đề thi"},
    {"id": "quick_drill", "label": "Drill nhanh"},
    {"id": "preview_available", "label": "Có preview"},
    {"id": "shadowing", "label": "Shadowing"},
    {"id": "speaking_prompt", "label": "Speaking prompt"},
    {"id": "writing_prompt", "label": "Writing prompt"},
    {"id": "architecture_diagram", "label": "Có sơ đồ"},
    {"id": "stroke_support", "label": "Có nét viết"},
)

NOTE_TYPE_BEST_USED_FOR_OPTIONS = (
    {"id": "vocabulary", "label": "Học từ vựng"},
    {"id": "grammar_drill", "label": "Drill ngữ pháp"},
    {"id": "cloze_practice", "label": "Luyện cloze"},
    {"id": "listening_practice", "label": "Luyện nghe"},
    {"id": "image_recall", "label": "Nhớ bằng hình"},
    {"id": "concept_recall", "label": "Nhớ khái niệm"},
    {"id": "scenario_practice", "label": "Luyện tình huống"},
)

SUBJECT_PACKS = {
    "japanese": {
        "frameworks": (
            {
                "id": "jlpt",
                "label": "JLPT",
                "levels": (
                    {"id": "n5", "label": "N5 (Sơ cấp 1)", "difficulty_band": "beginner"},
                    {"id": "n4", "label": "N4 (Sơ cấp 2)", "difficulty_band": "beginner"},
                    {"id": "n3", "label": "N3 (Trung cấp)", "difficulty_band": "intermediate"},
                    {"id": "n2", "label": "N2 (Trung cao cấp)", "difficulty_band": "advanced"},
                    {"id": "n1", "label": "N1 (Cao cấp)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "kanji",
                "label": "Kanji / Hán tự",
                "levels": (
                    {"id": "kanji_n5_n4", "label": "Kanji N5 - N4 (Cơ bản)", "difficulty_band": "beginner"},
                    {"id": "kanji_n3_n2", "label": "Kanji N3 - N2 (Trung cấp)", "difficulty_band": "intermediate"},
                    {"id": "kanji_n1_jouyou", "label": "Kanji N1 & 2136 chữ Thường dụng", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "bjt",
                "label": "BJT / Giao tiếp",
                "levels": (
                    {"id": "kaiwa_basic", "label": "Giao tiếp đời sống (Minna)", "difficulty_band": "beginner"},
                    {"id": "bjt_j3_j2", "label": "BJT J3 - J2 (Thương mại)", "difficulty_band": "intermediate"},
                    {"id": "bjt_j1_plus", "label": "BJT J1 - J1+ (Cao cấp)", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "kanji", "grammar", "reading", "listening", "speaking", "exam_prep"),
        "topics": ("meaning_recall", "reading_recall", "sentence_patterns", "audio_recognition", "daily_life", "conversation", "travel", "business", "furigana"),
        "features": ("audio", "example_sentences", "cloze", "preview_available", "shadowing"),
    },
    "english": {
        "frameworks": (
            {
                "id": "ielts",
                "label": "IELTS",
                "levels": (
                    {"id": "ielts_4_5", "label": "IELTS 4.0 - 5.0", "difficulty_band": "beginner"},
                    {"id": "ielts_5_5", "label": "IELTS 5.5 - 6.0", "difficulty_band": "intermediate"},
                    {"id": "ielts_6_5", "label": "IELTS 6.5 - 7.0", "difficulty_band": "intermediate"},
                    {"id": "ielts_7_plus", "label": "IELTS 7.5 - 8.0+", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "toeic",
                "label": "TOEIC",
                "levels": (
                    {"id": "toeic_450", "label": "TOEIC 250 - 450", "difficulty_band": "beginner"},
                    {"id": "toeic_600", "label": "TOEIC 500 - 650", "difficulty_band": "intermediate"},
                    {"id": "toeic_750", "label": "TOEIC 700 - 850", "difficulty_band": "intermediate"},
                    {"id": "toeic_900", "label": "TOEIC 900+", "difficulty_band": "advanced"},
                    {"id": "toeic_sw", "label": "TOEIC Speaking & Writing", "difficulty_band": "intermediate"},
                ),
            },
            {
                "id": "vstep",
                "label": "VSTEP (Bậc 3-5)",
                "levels": (
                    {"id": "vstep_b1", "label": "VSTEP B1 (Bậc 3)", "difficulty_band": "intermediate"},
                    {"id": "vstep_b2", "label": "VSTEP B2 (Bậc 4)", "difficulty_band": "intermediate"},
                    {"id": "vstep_c1", "label": "VSTEP C1 (Bậc 5)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "cefr",
                "label": "CEFR",
                "levels": (
                    {"id": "a1_a2", "label": "A1 - A2 (Cơ bản)", "difficulty_band": "beginner"},
                    {"id": "b1_b2", "label": "B1 - B2 (Độc lập)", "difficulty_band": "intermediate"},
                    {"id": "c1_c2", "label": "C1 - C2 (Thành thạo)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "toefl",
                "label": "TOEFL",
                "levels": (
                    {"id": "toefl_60", "label": "TOEFL iBT 40 - 60", "difficulty_band": "beginner"},
                    {"id": "toefl_80", "label": "TOEFL iBT 61 - 80", "difficulty_band": "intermediate"},
                    {"id": "toefl_100", "label": "TOEFL iBT 81 - 100+", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "thpt_qg",
                "label": "Luyện thi THPT QG / K12",
                "levels": (
                    {"id": "thpt_english", "label": "Luyện thi THPT QG Tiếng Anh", "difficulty_band": "intermediate"},
                    {"id": "cambridge_ket_pet", "label": "Cambridge KET / PET", "difficulty_band": "beginner"},
                    {"id": "sat_digital", "label": "SAT Digital", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "writing", "exam_prep", "daily_communication"),
        "topics": ("meaning_recall", "sentence_patterns", "audio_recognition", "conversation", "travel", "business_english", "academic_english"),
        "features": ("audio", "example_sentences", "cloze", "preview_available", "speaking_prompt", "writing_prompt", "exam_style"),
    },
    "korean": {
        "frameworks": (
            {
                "id": "topik",
                "label": "TOPIK",
                "levels": (
                    {"id": "topik_1", "label": "TOPIK 1 (Cấp 1 - Nhập môn)", "difficulty_band": "beginner"},
                    {"id": "topik_2", "label": "TOPIK 2 (Cấp 2 - Đời sống)", "difficulty_band": "beginner"},
                    {"id": "topik_3", "label": "TOPIK 3 (Cấp 3 - Xã hội)", "difficulty_band": "intermediate"},
                    {"id": "topik_4", "label": "TOPIK 4 (Cấp 4 - Tin tức/Công việc)", "difficulty_band": "intermediate"},
                    {"id": "topik_5", "label": "TOPIK 5 (Cấp 5 - Chuyên sâu)", "difficulty_band": "advanced"},
                    {"id": "topik_6", "label": "TOPIK 6 (Cấp 6 - Bản xứ)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "general_korean",
                "label": "Tiếng Hàn Tổng Hợp / Giao tiếp",
                "levels": (
                    {"id": "korean_beginner", "label": "Tiếng Hàn Sơ cấp 1 - 2", "difficulty_band": "beginner"},
                    {"id": "korean_intermediate", "label": "Tiếng Hàn Trung cấp 3 - 4", "difficulty_band": "intermediate"},
                    {"id": "korean_advanced", "label": "Tiếng Hàn Cao cấp 5 - 6", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "eps_topik",
                "label": "EPS-TOPIK (XKLĐ)",
                "levels": (
                    {"id": "eps_manufacturing", "label": "EPS-TOPIK Sản xuất chế tạo", "difficulty_band": "beginner"},
                    {"id": "eps_construction", "label": "EPS-TOPIK Xây dựng / Nông nghiệp", "difficulty_band": "beginner"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "daily_communication", "exam_prep"),
        "topics": ("meaning_recall", "reading_recall", "sentence_patterns", "audio_recognition", "conversation", "travel", "business"),
        "features": ("audio", "example_sentences", "preview_available", "cloze"),
    },
    "chinese": {
        "frameworks": (
            {
                "id": "hsk",
                "label": "HSK (Tiêu chuẩn)",
                "levels": (
                    {"id": "hsk1", "label": "HSK 1 (150 từ)", "difficulty_band": "beginner"},
                    {"id": "hsk2", "label": "HSK 2 (300 từ)", "difficulty_band": "beginner"},
                    {"id": "hsk3", "label": "HSK 3 (600 từ)", "difficulty_band": "intermediate"},
                    {"id": "hsk4", "label": "HSK 4 (1200 từ)", "difficulty_band": "intermediate"},
                    {"id": "hsk5", "label": "HSK 5 (2500 từ)", "difficulty_band": "advanced"},
                    {"id": "hsk6", "label": "HSK 6 (5000+ từ)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "hsk_3_0",
                "label": "HSK 3.0 (9 Cấp)",
                "levels": (
                    {"id": "hsk3_beginner", "label": "HSK 3.0 Sơ cấp (Cấp 1 - 3)", "difficulty_band": "beginner"},
                    {"id": "hsk3_intermediate", "label": "HSK 3.0 Trung cấp (Cấp 4 - 6)", "difficulty_band": "intermediate"},
                    {"id": "hsk3_advanced", "label": "HSK 3.0 Cao cấp (Cấp 7 - 9)", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "hskk",
                "label": "HSKK (Khẩu ngữ)",
                "levels": (
                    {"id": "hskk_primary", "label": "HSKK Sơ cấp", "difficulty_band": "beginner"},
                    {"id": "hskk_intermediate", "label": "HSKK Trung cấp", "difficulty_band": "intermediate"},
                    {"id": "hskk_advanced", "label": "HSKK Cao cấp", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "tocfl",
                "label": "TOCFL (Đài Loan / Phồn thể)",
                "levels": (
                    {"id": "tocfl_band_a", "label": "TOCFL Band A (A1 - A2)", "difficulty_band": "beginner"},
                    {"id": "tocfl_band_b", "label": "TOCFL Band B (B1 - B2)", "difficulty_band": "intermediate"},
                    {"id": "tocfl_band_c", "label": "TOCFL Band C (C1 - C2)", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "exam_prep"),
        "topics": ("hanzi", "pinyin", "meaning_recall", "reading_recall", "audio_recognition", "conversation", "travel", "business"),
        "features": ("audio", "example_sentences", "preview_available", "cloze", "stroke_support"),
    },
    "aws": {
        "frameworks": (
            {
                "id": "aws_certification",
                "label": "AWS Certification",
                "levels": (
                    {"id": "foundational", "label": "Cloud Practitioner (CCP)", "difficulty_band": "beginner"},
                    {"id": "associate", "label": "Associate (SAA / DVA / SOA)", "difficulty_band": "intermediate"},
                    {"id": "professional", "label": "Professional (SAP / DOP)", "difficulty_band": "advanced"},
                    {"id": "specialty", "label": "Specialty (Security / Data / ML)", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "service_comparison", "scenario_practice", "architecture_review", "exam_prep"),
        "topics": ("compute", "storage", "networking", "iam", "security", "databases", "serverless", "monitoring", "architecture_concepts"),
        "features": ("quick_drill", "exam_style", "preview_available", "architecture_diagram"),
    },
    "azure": {
        "frameworks": (
            {
                "id": "azure_certification",
                "label": "Microsoft Azure",
                "levels": (
                    {"id": "az_900", "label": "AZ-900 (Fundamentals)", "difficulty_band": "beginner"},
                    {"id": "az_104", "label": "AZ-104 (Administrator)", "difficulty_band": "intermediate"},
                    {"id": "az_204", "label": "AZ-204 (Developer)", "difficulty_band": "intermediate"},
                    {"id": "az_305", "label": "AZ-305 (Solutions Architect)", "difficulty_band": "advanced"},
                    {"id": "ai_dp_900", "label": "AI-900 / DP-900 (Data & AI)", "difficulty_band": "beginner"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "service_comparison", "scenario_practice", "exam_prep"),
        "topics": ("compute", "storage", "networking", "iam", "security", "databases", "serverless", "monitoring", "architecture_concepts"),
        "features": ("quick_drill", "exam_style", "preview_available", "architecture_diagram"),
    },
    "it_coding": {
        "frameworks": (
            {
                "id": "coding_stack",
                "label": "Lập trình & Kỹ năng CNTT",
                "levels": (
                    {"id": "frontend", "label": "Frontend (React, Vue, TS)", "difficulty_band": "intermediate"},
                    {"id": "backend", "label": "Backend (Node.js, Python, Java, Go)", "difficulty_band": "intermediate"},
                    {"id": "database", "label": "Database (SQL, MongoDB, Redis)", "difficulty_band": "intermediate"},
                    {"id": "devops", "label": "DevOps & Cloud (Docker, K8s, Linux)", "difficulty_band": "advanced"},
                    {"id": "ai_data", "label": "Data Science & AI / ML", "difficulty_band": "advanced"},
                    {"id": "dsa_leetcode", "label": "Thuật toán & LeetCode", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "scenario_practice", "drill", "exam_prep"),
        "topics": ("architecture_concepts", "databases", "serverless", "security", "business"),
        "features": ("example_sentences", "quick_drill", "preview_available"),
    },
    "thpt_qg": {
        "frameworks": (
            {
                "id": "thpt_exam",
                "label": "Môn thi THPT Quốc Gia",
                "levels": (
                    {"id": "thpt_math", "label": "Toán học THPT QG", "difficulty_band": "intermediate"},
                    {"id": "thpt_physics", "label": "Vật lý THPT QG", "difficulty_band": "intermediate"},
                    {"id": "thpt_chemistry", "label": "Hóa học THPT QG", "difficulty_band": "intermediate"},
                    {"id": "thpt_biology", "label": "Sinh học THPT QG", "difficulty_band": "intermediate"},
                    {"id": "thpt_history_geo", "label": "Lịch sử & Địa lý THPT QG", "difficulty_band": "intermediate"},
                    {"id": "thpt_civic", "label": "GDCD THPT QG", "difficulty_band": "intermediate"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "exam_prep", "drill"),
        "topics": ("meaning_recall", "academic_english"),
        "features": ("example_sentences", "quick_drill", "exam_style", "preview_available"),
    },
    "medical": {
        "frameworks": (
            {
                "id": "medical_field",
                "label": "Y Dược & Thuật ngữ",
                "levels": (
                    {"id": "med_terms", "label": "Thuật ngữ Y khoa tiếng Anh", "difficulty_band": "intermediate"},
                    {"id": "anatomy", "label": "Giải phẫu học (Anatomy)", "difficulty_band": "intermediate"},
                    {"id": "pharmacology", "label": "Dược lý học (Pharmacology)", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "concept_recall", "exam_prep", "drill"),
        "topics": ("meaning_recall", "academic_english"),
        "features": ("image_based", "example_sentences", "quick_drill", "preview_available"),
    },
    "law": {
        "frameworks": (
            {
                "id": "law_field",
                "label": "Chuyên ngành Luật",
                "levels": (
                    {"id": "civil_law", "label": "Luật Dân sự & Hôn nhân", "difficulty_band": "intermediate"},
                    {"id": "criminal_law", "label": "Luật Hình sự & Tố tụng", "difficulty_band": "intermediate"},
                    {"id": "business_law", "label": "Luật Doanh nghiệp & Đất đai", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "exam_prep", "scenario_practice"),
        "topics": ("meaning_recall", "sentence_patterns"),
        "features": ("example_sentences", "quick_drill", "preview_available"),
    },
    "business": {
        "frameworks": (
            {
                "id": "business_field",
                "label": "Kinh doanh & Chứng chỉ nghề",
                "levels": (
                    {"id": "pmp_agile", "label": "PMP / Scrum Master / Agile", "difficulty_band": "advanced"},
                    {"id": "cfa_acca", "label": "CFA / ACCA / Tài chính", "difficulty_band": "advanced"},
                    {"id": "digital_mkt", "label": "Digital Marketing & SEO", "difficulty_band": "intermediate"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "scenario_practice", "exam_prep"),
        "topics": ("business", "business_english", "conversation"),
        "features": ("example_sentences", "quick_drill", "preview_available"),
    },
    "other": {
        "frameworks": (),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "writing", "exam_prep", "concept_recall", "drill"),
        "topics": ("meaning_recall", "sentence_patterns", "audio_recognition", "architecture_concepts"),
        "features": ("example_sentences", "quick_drill", "preview_available"),
    },
}

LEGACY_SUBJECT_ALIASES = {
    "japanese": "japanese",
    "tieng_nhat": "japanese",
    "english": "english",
    "tieng_anh": "english",
    "chinese": "chinese",
    "tieng_trung": "chinese",
    "korean": "korean",
    "tieng_han": "korean",
    "aws": "aws",
    "azure": "azure",
    "other": "other",
    "khac": "other",
}

KEYWORD_TO_GOALS = {
    "vocabulary": "vocabulary",
    "tu vung": "vocabulary",
    "kanji": "kanji",
    "grammar": "grammar",
    "ngu phap": "grammar",
    "reading": "reading",
    "doc": "reading",
    "listening": "listening",
    "nghe": "listening",
    "speaking": "speaking",
    "noi": "speaking",
    "writing": "writing",
    "viet": "writing",
    "exam": "exam_prep",
    "jlpt": "exam_prep",
    "hsk": "exam_prep",
    "topik": "exam_prep",
    "toeic": "exam_prep",
    "ielts": "exam_prep",
    "vstep": "exam_prep",
    "toefl": "exam_prep",
    "aws": "exam_prep",
    "azure": "exam_prep",
    "thpt": "exam_prep",
    "scenario": "scenario_practice",
    "architecture": "architecture_review",
}

KEYWORD_TO_TOPICS = {
    "kanji": "kanji",
    "hanzi": "hanzi",
    "pinyin": "pinyin",
    "furigana": "furigana",
    "audio": "audio_recognition",
    "listening": "audio_recognition",
    "nghe": "audio_recognition",
    "daily": "daily_life",
    "travel": "travel",
    "business": "business",
    "conversation": "conversation",
    "compute": "compute",
    "storage": "storage",
    "network": "networking",
    "iam": "iam",
    "security": "security",
    "database": "databases",
    "serverless": "serverless",
    "monitor": "monitoring",
}

_DOMAIN_MAP = {row["id"]: row["label"] for row in DOMAIN_OPTIONS}
_SUBJECT_MAP = {row["id"]: row for row in SUBJECT_OPTIONS}
_DIFFICULTY_MAP = {row["id"]: row["label"] for row in DIFFICULTY_OPTIONS}
_AUDIENCE_MAP = {row["id"]: row["label"] for row in AUDIENCE_OPTIONS}
_GOAL_MAP = {row["id"]: row["label"] for row in LEARNING_GOAL_OPTIONS}
_TOPIC_MAP = {row["id"]: row["label"] for row in TOPIC_OPTIONS}
_FEATURE_MAP = {row["id"]: row["label"] for row in FORMAT_FEATURE_OPTIONS}
_BEST_USED_FOR_MAP = {row["id"]: row["label"] for row in NOTE_TYPE_BEST_USED_FOR_OPTIONS}

_SCHEMA_CACHE: dict[str, Any] = {}


def invalidate_taxonomy_cache() -> None:
    """Clear cached taxonomy schema to force DB re-query."""
    _SCHEMA_CACHE.clear()


def ensure_default_taxonomy_data(session: Session) -> None:
    """Seed initial taxonomy tables in database if empty."""
    from models.taxonomy import TaxonomyDomain

    existing = session.query(TaxonomyDomain).first()
    if existing:
        return

    logger.info("Seeding initial Taxonomy Metadata tables in database...")
    try:
        # 1. Domains
        for idx, dom in enumerate(DOMAIN_OPTIONS):
            marketplace_taxonomy_repository.create_domain(
                domain_id=dom["id"],
                label=dom["label"],
                sort_order=idx * 10,
            )

        # 2. Subjects
        for idx, sub in enumerate(SUBJECT_OPTIONS):
            marketplace_taxonomy_repository.create_subject(
                subject_id=sub["id"],
                domain_id=sub["domain"],
                label=sub["label"],
                sort_order=idx * 10,
            )

        # 3. Options
        for idx, opt in enumerate(DIFFICULTY_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="difficulty_band",
                label=opt["label"],
                sort_order=idx * 10,
            )
        for idx, opt in enumerate(AUDIENCE_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="audience",
                label=opt["label"],
                sort_order=idx * 10,
            )
        for idx, opt in enumerate(LEARNING_GOAL_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="learning_goal",
                label=opt["label"],
                sort_order=idx * 10,
            )
        for idx, opt in enumerate(TOPIC_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="primary_topic",
                label=opt["label"],
                sort_order=idx * 10,
            )
        for idx, opt in enumerate(FORMAT_FEATURE_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="format_feature",
                label=opt["label"],
                sort_order=idx * 10,
            )
        for idx, opt in enumerate(NOTE_TYPE_BEST_USED_FOR_OPTIONS):
            marketplace_taxonomy_repository.create_option(
                option_id=opt["id"],
                option_type="best_used_for",
                label=opt["label"],
                sort_order=idx * 10,
            )

        # 4. Subject Packs (Frameworks & Levels & Mappings)
        for subject_id, pack in SUBJECT_PACKS.items():
            frameworks = pack.get("frameworks", ())
            for f_idx, fw in enumerate(frameworks):
                marketplace_taxonomy_repository.create_framework(
                    framework_id=fw["id"],
                    subject_id=subject_id,
                    label=fw["label"],
                    sort_order=f_idx * 10,
                )
                for l_idx, lvl in enumerate(fw.get("levels", ())):
                    marketplace_taxonomy_repository.create_framework_level(
                        level_id=lvl["id"],
                        framework_id=fw["id"],
                        subject_id=subject_id,
                        label=lvl["label"],
                        difficulty_band=lvl.get("difficulty_band", "beginner"),
                        sort_order=l_idx * 10,
                    )
            # Subject mappings
            marketplace_taxonomy_repository.set_subject_option_maps(
                subject_id=subject_id,
                option_type="learning_goal",
                option_ids=list(pack.get("learning_goals", ())),
            )
            marketplace_taxonomy_repository.set_subject_option_maps(
                subject_id=subject_id,
                option_type="primary_topic",
                option_ids=list(pack.get("topics", ())),
            )
            marketplace_taxonomy_repository.set_subject_option_maps(
                subject_id=subject_id,
                option_type="format_feature",
                option_ids=list(pack.get("features", ())),
            )

        session.flush()
        logger.info("Successfully seeded Taxonomy Metadata database tables.")
    except Exception as e:
        logger.warning("Could not seed Taxonomy Metadata into DB: %s", e)


def empty_taxonomy_metadata() -> dict[str, Any]:
    return {
        "domain": None,
        "subject": None,
        "difficulty_band": None,
        "framework": None,
        "framework_level": None,
        "framework_track": None,
        "learning_goals": [],
        "primary_topics": [],
        "format_features": [],
        "audience": None,
        "best_used_for": None,
        "subcategory": None,
        "target_audience": None,
    }


def build_taxonomy_schema(*, content_type: str) -> dict[str, Any]:
    cache_key = f"schema_{content_type}"
    if cache_key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[cache_key]

    try:
        tree = marketplace_taxonomy_repository.get_full_taxonomy_tree(include_inactive=False)
        db_domains = tree["domains"]
        db_subjects = tree["subjects"]
        db_frameworks = tree["frameworks"]
        db_levels = tree["levels"]
        db_options = tree["options"]
        db_mappings = tree["mappings"]
    except Exception as e:
        logger.debug("Failed fetching taxonomy from DB, using fallback: %s", e)
        db_domains = []

    if db_domains:
        domains_list = [{"id": d.id, "label": d.label} for d in db_domains]
        subjects_list = [
            {"id": s.id, "label": s.label, "domain": s.domain_id} for s in db_subjects
        ]

        difficulty_bands = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "difficulty_band"
        ]
        audiences = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "audience"
        ]
        learning_goals = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "learning_goal"
        ]
        primary_topics = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "primary_topic"
        ]
        format_features = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "format_feature"
        ]
        best_used_for = [
            {"id": o.id, "label": o.label}
            for o in db_options
            if o.option_type == "best_used_for"
        ]

        # Group subject packs
        opt_lookup = {o.id: {"id": o.id, "label": o.label} for o in db_options}

        subject_packs = {}
        for sub in db_subjects:
            s_id = sub.id
            sub_frameworks = []
            for fw in [f for f in db_frameworks if f.subject_id == s_id]:
                fw_levels = [
                    {
                        "id": l.id,
                        "label": l.label,
                        "difficulty_band": l.difficulty_band,
                    }
                    for l in db_levels
                    if l.framework_id == fw.id
                ]
                sub_frameworks.append(
                    {
                        "id": fw.id,
                        "label": fw.label,
                        "levels": fw_levels,
                    }
                )

            s_goals = [
                opt_lookup[m.option_id]
                for m in db_mappings
                if m.subject_id == s_id and m.option_type == "learning_goal" and m.option_id in opt_lookup
            ]
            s_topics = [
                opt_lookup[m.option_id]
                for m in db_mappings
                if m.subject_id == s_id and m.option_type == "primary_topic" and m.option_id in opt_lookup
            ]
            s_features = [
                opt_lookup[m.option_id]
                for m in db_mappings
                if m.subject_id == s_id and m.option_type == "format_feature" and m.option_id in opt_lookup
            ]

            subject_packs[s_id] = {
                "frameworks": sub_frameworks,
                "learning_goals": s_goals,
                "primary_topics": s_topics,
                "format_features": s_features,
            }

        result = {
            "content_type": content_type,
            "domains": domains_list,
            "subjects": subjects_list,
            "difficulty_bands": difficulty_bands,
            "audiences": audiences,
            "learning_goals": learning_goals,
            "primary_topics": primary_topics,
            "format_features": format_features,
            "best_used_for": best_used_for if content_type == "note_type" else [],
            "subject_packs": subject_packs,
        }
    else:
        # Static Fallback
        result = {
            "content_type": content_type,
            "domains": list(DOMAIN_OPTIONS),
            "subjects": list(SUBJECT_OPTIONS),
            "difficulty_bands": list(DIFFICULTY_OPTIONS),
            "audiences": list(AUDIENCE_OPTIONS),
            "learning_goals": list(LEARNING_GOAL_OPTIONS),
            "primary_topics": list(TOPIC_OPTIONS),
            "format_features": list(FORMAT_FEATURE_OPTIONS),
            "best_used_for": list(NOTE_TYPE_BEST_USED_FOR_OPTIONS) if content_type == "note_type" else [],
            "subject_packs": {
                subject_id: {
                    "frameworks": [dict(framework) for framework in pack.get("frameworks", ())],
                    "learning_goals": [dict(_goal_option(goal_id)) for goal_id in pack.get("learning_goals", ()) if _goal_option(goal_id)],
                    "primary_topics": [dict(_topic_option(topic_id)) for topic_id in pack.get("topics", ()) if _topic_option(topic_id)],
                    "format_features": [dict(_feature_option(feature_id)) for feature_id in pack.get("features", ()) if _feature_option(feature_id)],
                }
                for subject_id, pack in SUBJECT_PACKS.items()
            },
        }

    _SCHEMA_CACHE[cache_key] = result
    return result


def normalize_taxonomy_payload(payload: dict[str, Any] | None, *, content_type: str) -> tuple[dict[str, Any], str | None]:
    normalized = empty_taxonomy_metadata()
    source = payload or {}

    schema = build_taxonomy_schema(content_type=content_type)
    allowed_subjects = {s["id"] for s in schema["subjects"]}
    allowed_domains = {d["id"] for d in schema["domains"]}
    allowed_difficulties = {d["id"] for d in schema["difficulty_bands"]}
    allowed_audiences = {a["id"] for a in schema["audiences"]}
    allowed_goals = {g["id"] for g in schema["learning_goals"]}
    allowed_topics = {t["id"] for t in schema["primary_topics"]}.union({"kanji"})
    allowed_features = {f["id"] for f in schema["format_features"]}
    allowed_best_used = {b["id"] for b in schema["best_used_for"]}

    subject_map = {s["id"]: s for s in schema["subjects"]}

    subject = _normalize_choice(_get_value(source, "taxonomy_subject", "subject"), allowed_subjects)
    domain = _normalize_choice(_get_value(source, "taxonomy_domain", "domain"), allowed_domains)
    difficulty_band = _normalize_choice(
        _get_value(source, "taxonomy_difficulty_band", "difficulty_band", "level_band"),
        allowed_difficulties,
    )
    audience = _normalize_choice(_get_value(source, "taxonomy_audience", "audience"), allowed_audiences)
    subcategory = _normalize_free_text(_get_value(source, "subcategory"), max_length=120)
    target_audience = _normalize_free_text(_get_value(source, "target_audience"), max_length=255)

    if subject:
        expected_domain = subject_map.get(subject, {}).get("domain")
        if domain and expected_domain and domain != expected_domain:
            return normalized, "subject does not match selected domain."
        domain = expected_domain or domain

    framework_ids = {framework["id"] for framework in _framework_options(subject)}
    framework = _normalize_choice(_get_value(source, "taxonomy_framework", "framework"), framework_ids)
    framework_level_ids = {level["id"] for level in _framework_level_options(subject, framework)}
    framework_level = _normalize_choice(_get_value(source, "taxonomy_framework_level", "framework_level"), framework_level_ids)
    framework_track_ids = {track["id"] for track in _framework_track_options(subject, framework)}
    framework_track = _normalize_choice(_get_value(source, "taxonomy_framework_track", "framework_track"), framework_track_ids)

    learning_goals = _normalize_multi_values(
        _get_multi_value(source, "taxonomy_learning_goals", "learning_goals"),
        allowed_goals,
        max_items=3,
    )
    primary_topics = _normalize_multi_values(
        _get_multi_value(source, "taxonomy_primary_topics", "primary_topics"),
        allowed_topics,
        max_items=5,
    )
    format_features = _normalize_multi_values(
        _get_multi_value(source, "taxonomy_format_features", "format_features"),
        allowed_features,
        max_items=4,
    )

    best_used_for = None
    if content_type == "note_type":
        best_used_for = _normalize_choice(
            _get_value(source, "taxonomy_best_used_for", "best_used_for"),
            allowed_best_used,
        )

    if framework_level and difficulty_band is None:
        difficulty_band = framework_level_to_difficulty(subject=subject, framework=framework, framework_level=framework_level)

    normalized.update(
        {
            "domain": domain,
            "subject": subject,
            "difficulty_band": difficulty_band,
            "framework": framework,
            "framework_level": framework_level,
            "framework_track": framework_track,
            "learning_goals": learning_goals,
            "primary_topics": primary_topics,
            "format_features": format_features,
            "audience": audience,
            "best_used_for": best_used_for,
            "subcategory": subcategory,
            "target_audience": target_audience,
        }
    )
    return normalized, None


def validate_required_taxonomy(metadata: dict[str, Any] | None, *, content_type: str) -> str | None:
    normalized, error = normalize_taxonomy_payload(metadata or {}, content_type=content_type)
    if error:
        return error
    if not normalized.get("domain"):
        return "taxonomy_domain is required for publish."
    if not normalized.get("subject"):
        return "taxonomy_subject is required for publish."
    if not normalized.get("difficulty_band"):
        return "taxonomy_difficulty_band is required for publish."
    if not (normalized.get("learning_goals") or []):
        return "At least one learning goal is required for publish."
    if not (normalized.get("primary_topics") or []):
        return "At least one primary topic is required for publish."
    return None


def get_item_taxonomy(item: Any, *, content_type: str) -> dict[str, Any]:
    raw = getattr(item, "taxonomy_metadata", None)
    normalized, _ = normalize_taxonomy_payload(raw if isinstance(raw, dict) else {}, content_type=content_type)
    if normalized.get("subject") and normalized.get("difficulty_band"):
        return normalized

    inferred = _infer_legacy_taxonomy(
        primary_category=getattr(item, "primary_category", None),
        tags=getattr(item, "tags", None),
        title=getattr(item, "title", None) or getattr(item, "name", None),
        description=getattr(item, "description", None),
        content_type=content_type,
    )
    merged = empty_taxonomy_metadata()
    for key, value in inferred.items():
        merged[key] = value
    for key, value in normalized.items():
        if isinstance(value, list):
            if value:
                merged[key] = value
        elif value:
            merged[key] = value
    return merged


def build_taxonomy_display(metadata: dict[str, Any] | None, *, content_type: str) -> dict[str, Any]:
    normalized, _ = normalize_taxonomy_payload(metadata or {}, content_type=content_type)
    domain = normalized.get("domain")
    subject = normalized.get("subject")
    difficulty_band = normalized.get("difficulty_band")
    framework = normalized.get("framework")
    framework_level = normalized.get("framework_level")
    framework_track = normalized.get("framework_track")
    learning_goals = normalized.get("learning_goals") or []
    primary_topics = normalized.get("primary_topics") or []
    format_features = normalized.get("format_features") or []
    audience = normalized.get("audience")
    best_used_for = normalized.get("best_used_for")
    subcategory = normalized.get("subcategory")
    target_audience = normalized.get("target_audience")

    chips: list[str] = []
    for value in (
        subject_label(subject),
        difficulty_label(difficulty_band),
        framework_level_label(subject=subject, framework=framework, framework_level=framework_level),
        framework_track_label(subject=subject, framework=framework, framework_track=framework_track),
    ):
        if value:
            chips.append(value)
    chips.extend(goal_labels(learning_goals)[:2])
    chips.extend(topic_labels(primary_topics)[:2])

    detail_tags: list[str] = []
    detail_tags.extend(filter(None, (subject_label(subject), difficulty_label(difficulty_band))))
    detail_tags.extend(goal_labels(learning_goals))
    detail_tags.extend(topic_labels(primary_topics))
    detail_tags.extend(feature_labels(format_features))
    if audience_label(audience):
        detail_tags.append(audience_label(audience))
    detail_tags.extend(filter(None, (subcategory, target_audience)))
    if content_type == "note_type" and best_used_for_label(best_used_for):
        detail_tags.append(best_used_for_label(best_used_for))

    return {
        "domain": domain,
        "domain_label": domain_label(domain),
        "subject": subject,
        "subject_label": subject_label(subject),
        "difficulty_band": difficulty_band,
        "difficulty_label": difficulty_label(difficulty_band),
        "framework": framework,
        "framework_label": framework_label(subject=subject, framework=framework),
        "framework_level": framework_level,
        "framework_level_label": framework_level_label(subject=subject, framework=framework, framework_level=framework_level),
        "framework_track": framework_track,
        "framework_track_label": framework_track_label(subject=subject, framework=framework, framework_track=framework_track),
        "learning_goals": learning_goals,
        "learning_goal_labels": goal_labels(learning_goals),
        "primary_topics": primary_topics,
        "primary_topic_labels": topic_labels(primary_topics),
        "format_features": format_features,
        "format_feature_labels": feature_labels(format_features),
        "audience": audience,
        "audience_label": audience_label(audience),
        "best_used_for": best_used_for,
        "best_used_for_label": best_used_for_label(best_used_for),
        "subcategory": subcategory,
        "target_audience": target_audience,
        "catalog_chips": _dedupe_list(chips),
        "catalog_tags": _dedupe_list(detail_tags),
    }


def build_searchable_taxonomy_text(metadata: dict[str, Any] | None, *, content_type: str) -> str:
    display = build_taxonomy_display(metadata, content_type=content_type)
    parts = [
        display.get("domain_label"),
        display.get("subject_label"),
        display.get("difficulty_label"),
        display.get("framework_label"),
        display.get("framework_level_label"),
        display.get("framework_track_label"),
        display.get("audience_label"),
        display.get("best_used_for_label"),
        display.get("subcategory"),
        display.get("target_audience"),
        " ".join(display.get("learning_goal_labels") or []),
        " ".join(display.get("primary_topic_labels") or []),
        " ".join(display.get("format_feature_labels") or []),
    ]
    return " ".join(part for part in parts if part).strip()


def merge_detail_tags(*, free_tags: list[str] | None, metadata: dict[str, Any] | None, content_type: str) -> list[str]:
    display = build_taxonomy_display(metadata or {}, content_type=content_type)
    return _dedupe_list((display.get("catalog_tags") or []) + list(free_tags or []))


def suggest_primary_category(metadata: dict[str, Any] | None) -> str | None:
    display = build_taxonomy_display(metadata or {}, content_type="deck_marketplace_item")
    return display.get("subject_label") or display.get("domain_label")


def domain_label(value: str | None) -> str | None:
    val = str(value or "").strip()
    if not val:
        return None
    try:
        dom = marketplace_taxonomy_repository.get_domain(val)
        if dom:
            return dom.label
    except Exception:
        pass
    return _DOMAIN_MAP.get(val)


def subject_label(value: str | None) -> str | None:
    val = str(value or "").strip()
    if not val:
        return None
    try:
        sub = marketplace_taxonomy_repository.get_subject(val)
        if sub:
            return sub.label
    except Exception:
        pass
    option = _SUBJECT_MAP.get(val)
    return option.get("label") if option else None


def difficulty_label(value: str | None) -> str | None:
    val = str(value or "").strip()
    if not val:
        return None
    if val in _DIFFICULTY_MAP:
        return _DIFFICULTY_MAP[val]
    try:
        opt = marketplace_taxonomy_repository.get_option(val)
        if opt:
            return opt.label
    except Exception:
        pass
    return None


def audience_label(value: str | None) -> str | None:
    val = str(value or "").strip()
    if not val:
        return None
    if val in _AUDIENCE_MAP:
        return _AUDIENCE_MAP[val]
    try:
        opt = marketplace_taxonomy_repository.get_option(val)
        if opt:
            return opt.label
    except Exception:
        pass
    return None


def goal_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    for item in values:
        lbl = _GOAL_MAP.get(item)
        if not lbl:
            try:
                opt = marketplace_taxonomy_repository.get_option(item)
                if opt:
                    lbl = opt.label
            except Exception:
                pass
        if lbl:
            labels.append(lbl)
    return labels


def topic_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    for item in values:
        lbl = _TOPIC_MAP.get(item)
        if not lbl and item == "kanji":
            lbl = "Kanji"
        if not lbl:
            try:
                opt = marketplace_taxonomy_repository.get_option(item)
                if opt:
                    lbl = opt.label
            except Exception:
                pass
        if lbl:
            labels.append(lbl)
    return labels


def feature_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    for item in values:
        lbl = _FEATURE_MAP.get(item)
        if not lbl:
            try:
                opt = marketplace_taxonomy_repository.get_option(item)
                if opt:
                    lbl = opt.label
            except Exception:
                pass
        if lbl:
            labels.append(lbl)
    return labels


def best_used_for_label(value: str | None) -> str | None:
    val = str(value or "").strip()
    if not val:
        return None
    if val in _BEST_USED_FOR_MAP:
        return _BEST_USED_FOR_MAP[val]
    try:
        opt = marketplace_taxonomy_repository.get_option(val)
        if opt:
            return opt.label
    except Exception:
        pass
    return None


def framework_level_to_difficulty(*, subject: str | None, framework: str | None, framework_level: str | None) -> str | None:
    if not subject or not framework or not framework_level:
        return None
    for level in _framework_level_options(subject, framework):
        if level["id"] == framework_level:
            return level.get("difficulty_band")
    try:
        lvl = marketplace_taxonomy_repository.get_framework_level(framework_level)
        if lvl:
            return lvl.difficulty_band
    except Exception:
        pass
    return None


def framework_label(*, subject: str | None, framework: str | None) -> str | None:
    if not subject or not framework:
        return None
    for option in _framework_options(subject):
        if option["id"] == framework:
            return option["label"]
    try:
        fw = marketplace_taxonomy_repository.get_framework(framework)
        if fw:
            return fw.label
    except Exception:
        pass
    return None


def framework_level_label(*, subject: str | None, framework: str | None, framework_level: str | None) -> str | None:
    if not subject or not framework or not framework_level:
        return None
    for option in _framework_level_options(subject, framework):
        if option["id"] == framework_level:
            return option["label"]
    try:
        lvl = marketplace_taxonomy_repository.get_framework_level(framework_level)
        if lvl:
            return lvl.label
    except Exception:
        pass
    return None


def framework_track_label(*, subject: str | None, framework: str | None, framework_track: str | None) -> str | None:
    if not subject or not framework or not framework_track:
        return None
    for option in _framework_track_options(subject, framework):
        if option["id"] == framework_track:
            return option["label"]
    return None


def _infer_legacy_taxonomy(
    *,
    primary_category: str | None,
    tags: list[str] | None,
    title: str | None,
    description: str | None,
    content_type: str,
) -> dict[str, Any]:
    normalized = empty_taxonomy_metadata()
    category_token = _slug(primary_category)
    if category_token in LEGACY_SUBJECT_ALIASES:
        normalized["subject"] = LEGACY_SUBJECT_ALIASES[category_token]
        normalized["domain"] = _SUBJECT_MAP.get(normalized["subject"], {}).get("domain")

    haystack = " ".join(
        str(part or "").strip().lower()
        for part in [title, description, " ".join(str(tag or "") for tag in tags or [])]
        if part
    )

    for level_token in ("n5", "n4", "n3", "n2", "n1"):
        if f" {level_token}" in f" {haystack} ":
            normalized["framework"] = "jlpt"
            normalized["framework_level"] = level_token
            normalized["subject"] = normalized.get("subject") or "japanese"
            break
    for level_token in ("hsk1", "hsk2", "hsk3", "hsk4", "hsk5", "hsk6"):
        if level_token in haystack:
            normalized["framework"] = "hsk"
            normalized["framework_level"] = level_token
            normalized["subject"] = normalized.get("subject") or "chinese"
            break
    for level_token in ("topik_1", "topik_2", "topik_3", "topik_4", "topik_5", "topik_6", "topik"):
        if level_token in haystack:
            normalized["framework"] = "topik"
            if level_token != "topik":
                normalized["framework_level"] = level_token
            normalized["subject"] = normalized.get("subject") or "korean"
            break
    for level_token in ("ielts", "toeic", "vstep"):
        if level_token in haystack:
            normalized["framework"] = level_token
            normalized["subject"] = normalized.get("subject") or "english"
            break

    if not normalized.get("domain") and normalized.get("subject"):
        normalized["domain"] = _SUBJECT_MAP.get(normalized["subject"], {}).get("domain")
    if not normalized.get("difficulty_band"):
        normalized["difficulty_band"] = framework_level_to_difficulty(
            subject=normalized.get("subject"),
            framework=normalized.get("framework"),
            framework_level=normalized.get("framework_level"),
        )
    if not normalized.get("difficulty_band"):
        if "beginner" in haystack or "so cap" in haystack:
            normalized["difficulty_band"] = "beginner"
        elif "intermediate" in haystack or "trung cap" in haystack:
            normalized["difficulty_band"] = "intermediate"
        elif "advanced" in haystack or "nang cao" in haystack:
            normalized["difficulty_band"] = "advanced"

    goals: list[str] = []
    topics: list[str] = []
    for keyword, goal in KEYWORD_TO_GOALS.items():
        if keyword in haystack and goal not in goals:
            goals.append(goal)
    for keyword, topic in KEYWORD_TO_TOPICS.items():
        if keyword in haystack and topic not in topics:
            topics.append(topic)
    normalized["learning_goals"] = goals[:3]
    normalized["primary_topics"] = topics[:5]
    if content_type == "note_type" and not normalized.get("best_used_for") and goals:
        normalized["best_used_for"] = goals[0]
    return normalized


def _framework_options(subject: str | None) -> list[dict[str, Any]]:
    if not subject:
        return []
    if subject in SUBJECT_PACKS and "frameworks" in SUBJECT_PACKS[subject]:
        return [dict(option) for option in SUBJECT_PACKS[subject]["frameworks"]]
    try:
        fws = marketplace_taxonomy_repository.list_frameworks(subject_id=subject)
        if fws:
            return [{"id": f.id, "label": f.label} for f in fws]
    except Exception:
        pass
    return []


def _framework_level_options(subject: str | None, framework: str | None) -> list[dict[str, Any]]:
    if not subject or not framework:
        return []
    for option in SUBJECT_PACKS.get(subject, {}).get("frameworks", ()):
        if option["id"] == framework:
            return [dict(level) for level in option.get("levels", ())]
    try:
        lvls = marketplace_taxonomy_repository.list_framework_levels(framework_id=framework)
        if lvls:
            return [{"id": l.id, "label": l.label, "difficulty_band": l.difficulty_band} for l in lvls]
    except Exception:
        pass
    return []


def _framework_track_options(subject: str | None, framework: str | None) -> list[dict[str, Any]]:
    if not subject or not framework:
        return []
    for option in SUBJECT_PACKS.get(subject, {}).get("frameworks", ()):
        if option["id"] == framework:
            return [dict(track) for track in option.get("tracks", ())]
    return []


def _goal_option(goal_id: str) -> dict[str, Any] | None:
    for option in LEARNING_GOAL_OPTIONS:
        if option["id"] == goal_id:
            return option
    return None


def _topic_option(topic_id: str) -> dict[str, Any] | None:
    if topic_id == "kanji":
        return {"id": "kanji", "label": "Kanji"}
    for option in TOPIC_OPTIONS:
        if option["id"] == topic_id:
            return option
    return None


def _feature_option(feature_id: str) -> dict[str, Any] | None:
    for option in FORMAT_FEATURE_OPTIONS:
        if option["id"] == feature_id:
            return option
    return None


def _get_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None


def _get_multi_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return []


def _normalize_choice(raw_value: Any, allowed: set[str]) -> str | None:
    token = _slug(raw_value)
    if not token:
        return None
    return token if token in allowed else None


def _normalize_free_text(raw_value: Any, *, max_length: int) -> str | None:
    text = str(raw_value or "").strip()
    return text[:max_length] or None


def _normalize_multi_values(raw_value: Any, allowed: set[str], *, max_items: int) -> list[str]:
    values: list[str] = []
    if isinstance(raw_value, (list, tuple, set)):
        iterable = list(raw_value)
    elif isinstance(raw_value, str):
        iterable = raw_value.split(",")
    elif raw_value is None:
        iterable = []
    else:
        iterable = [raw_value]

    seen: set[str] = set()
    for candidate in iterable:
        token = _slug(candidate)
        if not token or token not in allowed or token in seen:
            continue
        seen.add(token)
        values.append(token)
        if len(values) >= max_items:
            break
    return values


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text.replace("-", "_").replace(" ", "_")


def _dedupe_list(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _commit_and_invalidate() -> None:
    from models import db

    db.session.commit()
    invalidate_taxonomy_cache()


def create_domain(
    *,
    domain_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
):
    from models import db

    try:
        domain = marketplace_taxonomy_repository.create_domain(
            domain_id=domain_id,
            label=label,
            sort_order=sort_order,
            is_active=is_active,
        )
        _commit_and_invalidate()
        return domain
    except Exception:
        db.session.rollback()
        raise


def update_domain(
    *,
    domain_id: str,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
):
    from models import db

    domain = marketplace_taxonomy_repository.update_domain(
        domain_id=domain_id,
        label=label,
        sort_order=sort_order,
        is_active=is_active,
    )
    if not domain:
        return None
    try:
        _commit_and_invalidate()
        return domain
    except Exception:
        db.session.rollback()
        raise


def delete_domain(domain_id: str) -> bool:
    success = marketplace_taxonomy_repository.delete_domain(domain_id)
    if not success:
        return False
    _commit_and_invalidate()
    return True


def create_subject(
    *,
    subject_id: str,
    domain_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
):
    from models import db

    try:
        subject = marketplace_taxonomy_repository.create_subject(
            subject_id=subject_id,
            domain_id=domain_id,
            label=label,
            sort_order=sort_order,
            is_active=is_active,
        )
        _commit_and_invalidate()
        return subject
    except Exception:
        db.session.rollback()
        raise


def update_subject(
    *,
    subject_id: str,
    domain_id: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
):
    from models import db

    subject = marketplace_taxonomy_repository.update_subject(
        subject_id=subject_id,
        domain_id=domain_id,
        label=label,
        sort_order=sort_order,
        is_active=is_active,
    )
    if not subject:
        return None
    try:
        _commit_and_invalidate()
        return subject
    except Exception:
        db.session.rollback()
        raise


def delete_subject(subject_id: str) -> bool:
    success = marketplace_taxonomy_repository.delete_subject(subject_id)
    if not success:
        return False
    _commit_and_invalidate()
    return True


def create_framework(
    *,
    framework_id: str,
    subject_id: str,
    label: str,
    sort_order: int = 0,
    is_active: bool = True,
):
    from models import db

    try:
        framework = marketplace_taxonomy_repository.create_framework(
            framework_id=framework_id,
            subject_id=subject_id,
            label=label,
            sort_order=sort_order,
            is_active=is_active,
        )
        _commit_and_invalidate()
        return framework
    except Exception:
        db.session.rollback()
        raise


def update_framework(
    *,
    framework_id: str,
    subject_id: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
):
    from models import db

    framework = marketplace_taxonomy_repository.update_framework(
        framework_id=framework_id,
        subject_id=subject_id,
        label=label,
        sort_order=sort_order,
        is_active=is_active,
    )
    if not framework:
        return None
    try:
        _commit_and_invalidate()
        return framework
    except Exception:
        db.session.rollback()
        raise


def delete_framework(framework_id: str) -> bool:
    success = marketplace_taxonomy_repository.delete_framework(framework_id)
    if not success:
        return False
    _commit_and_invalidate()
    return True


def create_framework_level(
    *,
    level_id: str,
    framework_id: str,
    subject_id: str,
    label: str,
    difficulty_band: str = "beginner",
    sort_order: int = 0,
    is_active: bool = True,
):
    from models import db

    try:
        level = marketplace_taxonomy_repository.create_framework_level(
            level_id=level_id,
            framework_id=framework_id,
            subject_id=subject_id,
            label=label,
            difficulty_band=difficulty_band,
            sort_order=sort_order,
            is_active=is_active,
        )
        _commit_and_invalidate()
        return level
    except Exception:
        db.session.rollback()
        raise


def update_framework_level(
    *,
    level_id: str,
    label: str | None = None,
    difficulty_band: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
):
    from models import db

    level = marketplace_taxonomy_repository.update_framework_level(
        level_id=level_id,
        label=label,
        difficulty_band=difficulty_band,
        sort_order=sort_order,
        is_active=is_active,
    )
    if not level:
        return None
    try:
        _commit_and_invalidate()
        return level
    except Exception:
        db.session.rollback()
        raise


def delete_framework_level(level_id: str) -> bool:
    success = marketplace_taxonomy_repository.delete_framework_level(level_id)
    if not success:
        return False
    _commit_and_invalidate()
    return True


def create_option(
    *,
    option_id: str,
    option_type: str,
    label: str,
    sub_label: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
):
    from models import db

    try:
        opt = marketplace_taxonomy_repository.create_option(
            option_id=option_id,
            option_type=option_type,
            label=label,
            sub_label=sub_label,
            sort_order=sort_order,
            is_active=is_active,
        )
        _commit_and_invalidate()
        return opt
    except Exception:
        db.session.rollback()
        raise


def update_option(
    *,
    option_id: str,
    option_type: str | None = None,
    label: str | None = None,
    sub_label: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
):
    from models import db

    opt = marketplace_taxonomy_repository.update_option(
        option_id=option_id,
        option_type=option_type,
        label=label,
        sub_label=sub_label,
        sort_order=sort_order,
        is_active=is_active,
    )
    if not opt:
        return None
    try:
        _commit_and_invalidate()
        return opt
    except Exception:
        db.session.rollback()
        raise


def delete_option(option_id: str, *, option_type: str | None = None) -> bool:
    success = marketplace_taxonomy_repository.delete_option(
        option_id, option_type=option_type
    )
    if not success:
        return False
    _commit_and_invalidate()
    return True


def set_subject_option_maps(
    *,
    subject_id: str,
    option_type: str,
    option_ids: list[str],
) -> None:
    from models import db

    try:
        marketplace_taxonomy_repository.set_subject_option_maps(
            subject_id=subject_id,
            option_type=option_type,
            option_ids=option_ids,
        )
        _commit_and_invalidate()
    except Exception:
        db.session.rollback()
        raise


def reseed_default_taxonomy_data() -> None:
    from models import db

    try:
        ensure_default_taxonomy_data(db.session)
        _commit_and_invalidate()
    except Exception:
        db.session.rollback()
        raise

