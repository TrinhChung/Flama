from __future__ import annotations

from typing import Any


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
    {"id": "aws", "label": "AWS", "domain": "certification"},
    {"id": "other_certification", "label": "Chứng chỉ khác", "domain": "certification"},
    {"id": "it_coding", "label": "CNTT & Lập trình", "domain": "professional_skills"},
    {"id": "business", "label": "Kinh doanh & Quản lý", "domain": "professional_skills"},
    {"id": "science", "label": "Khoa học tự nhiên", "domain": "academic"},
    {"id": "medical", "label": "Y dược", "domain": "academic"},
    {"id": "law", "label": "Luật", "domain": "academic"},
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
    {"id": "kanji", "label": "Kanji"},
    {"id": "grammar", "label": "Ngữ pháp"},
    {"id": "reading", "label": "Đọc"},
    {"id": "listening", "label": "Nghe"},
    {"id": "speaking", "label": "Nói"},
    {"id": "writing", "label": "Viết"},
    {"id": "exam_prep", "label": "Luyện thi"},
    {"id": "daily_communication", "label": "Giao tiếp hằng ngày"},
    {"id": "drill", "label": "Ôn tập nhanh"},
    {"id": "concept_recall", "label": "Nhớ khái niệm"},
    {"id": "service_comparison", "label": "So sánh dịch vụ"},
    {"id": "scenario_practice", "label": "Luyện tình huống"},
    {"id": "architecture_review", "label": "Ôn kiến trúc"},
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
    {"id": "hanzi", "label": "Hanzi"},
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
                    {"id": "n5", "label": "N5", "difficulty_band": "beginner"},
                    {"id": "n4", "label": "N4", "difficulty_band": "beginner"},
                    {"id": "n3", "label": "N3", "difficulty_band": "intermediate"},
                    {"id": "n2", "label": "N2", "difficulty_band": "advanced"},
                    {"id": "n1", "label": "N1", "difficulty_band": "advanced"},
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
                "id": "cefr",
                "label": "CEFR",
                "levels": (
                    {"id": "a1_a2", "label": "A1-A2", "difficulty_band": "beginner"},
                    {"id": "b1_b2", "label": "B1-B2", "difficulty_band": "intermediate"},
                    {"id": "c1_c2", "label": "C1-C2", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "toeic",
                "label": "TOEIC",
                "levels": (
                    {"id": "toeic_450", "label": "450+", "difficulty_band": "beginner"},
                    {"id": "toeic_600", "label": "600+", "difficulty_band": "intermediate"},
                    {"id": "toeic_750", "label": "750+", "difficulty_band": "intermediate"},
                    {"id": "toeic_900", "label": "900+", "difficulty_band": "advanced"},
                ),
            },
            {
                "id": "ielts",
                "label": "IELTS",
                "levels": (
                    {"id": "ielts_4_5", "label": "4.5+", "difficulty_band": "beginner"},
                    {"id": "ielts_5_5", "label": "5.5+", "difficulty_band": "intermediate"},
                    {"id": "ielts_6_5", "label": "6.5+", "difficulty_band": "intermediate"},
                    {"id": "ielts_7_plus", "label": "7.0+", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "writing", "exam_prep", "daily_communication"),
        "topics": ("meaning_recall", "sentence_patterns", "audio_recognition", "conversation", "travel", "business_english", "academic_english"),
        "features": ("audio", "example_sentences", "cloze", "preview_available", "speaking_prompt", "writing_prompt", "exam_style"),
    },
    "chinese": {
        "frameworks": (
            {
                "id": "hsk",
                "label": "HSK",
                "levels": (
                    {"id": "hsk1", "label": "HSK1", "difficulty_band": "beginner"},
                    {"id": "hsk2", "label": "HSK2", "difficulty_band": "beginner"},
                    {"id": "hsk3", "label": "HSK3", "difficulty_band": "intermediate"},
                    {"id": "hsk4", "label": "HSK4", "difficulty_band": "intermediate"},
                    {"id": "hsk5", "label": "HSK5", "difficulty_band": "advanced"},
                    {"id": "hsk6", "label": "HSK6", "difficulty_band": "advanced"},
                ),
            },
        ),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "exam_prep"),
        "topics": ("hanzi", "pinyin", "meaning_recall", "reading_recall", "audio_recognition", "conversation", "travel", "business"),
        "features": ("audio", "example_sentences", "preview_available", "cloze", "stroke_support"),
    },
    "korean": {
        "frameworks": (),
        "learning_goals": ("vocabulary", "grammar", "reading", "listening", "speaking", "daily_communication"),
        "topics": ("meaning_recall", "reading_recall", "sentence_patterns", "audio_recognition", "conversation", "travel", "business"),
        "features": ("audio", "example_sentences", "preview_available", "cloze"),
    },
    "aws": {
        "frameworks": (
            {
                "id": "aws_certification",
                "label": "AWS Certification",
                "levels": (
                    {"id": "foundational", "label": "Foundational", "difficulty_band": "beginner"},
                    {"id": "associate", "label": "Associate", "difficulty_band": "intermediate"},
                    {"id": "professional", "label": "Professional", "difficulty_band": "advanced"},
                    {"id": "specialty", "label": "Specialty", "difficulty_band": "advanced"},
                ),
                "tracks": (
                    {"id": "ccp", "label": "CCP"},
                    {"id": "saa", "label": "SAA"},
                    {"id": "dva", "label": "DVA"},
                    {"id": "soa", "label": "SOA"},
                    {"id": "sap", "label": "SAP"},
                    {"id": "security", "label": "Security"},
                    {"id": "data", "label": "Data"},
                    {"id": "ml", "label": "ML"},
                ),
            },
        ),
        "learning_goals": ("concept_recall", "service_comparison", "scenario_practice", "architecture_review", "exam_prep"),
        "topics": ("compute", "storage", "networking", "iam", "security", "databases", "serverless", "monitoring", "architecture_concepts"),
        "features": ("quick_drill", "exam_style", "preview_available", "architecture_diagram"),
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
    "toeic": "exam_prep",
    "ielts": "exam_prep",
    "aws": "exam_prep",
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
    return {
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


def normalize_taxonomy_payload(payload: dict[str, Any] | None, *, content_type: str) -> tuple[dict[str, Any], str | None]:
    normalized = empty_taxonomy_metadata()
    source = payload or {}

    subject = _normalize_choice(_get_value(source, "taxonomy_subject", "subject"), {row["id"] for row in SUBJECT_OPTIONS})
    domain = _normalize_choice(_get_value(source, "taxonomy_domain", "domain"), {row["id"] for row in DOMAIN_OPTIONS})
    difficulty_band = _normalize_choice(
        _get_value(source, "taxonomy_difficulty_band", "difficulty_band", "level_band"),
        {row["id"] for row in DIFFICULTY_OPTIONS},
    )
    audience = _normalize_choice(_get_value(source, "taxonomy_audience", "audience"), {row["id"] for row in AUDIENCE_OPTIONS})
    subcategory = _normalize_free_text(_get_value(source, "subcategory"), max_length=120)
    target_audience = _normalize_free_text(_get_value(source, "target_audience"), max_length=255)

    if subject:
        expected_domain = _SUBJECT_MAP.get(subject, {}).get("domain")
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
        {row["id"] for row in LEARNING_GOAL_OPTIONS},
        max_items=3,
    )
    primary_topics = _normalize_multi_values(
        _get_multi_value(source, "taxonomy_primary_topics", "primary_topics"),
        {row["id"] for row in TOPIC_OPTIONS}.union({"kanji"}),
        max_items=5,
    )
    format_features = _normalize_multi_values(
        _get_multi_value(source, "taxonomy_format_features", "format_features"),
        {row["id"] for row in FORMAT_FEATURE_OPTIONS},
        max_items=4,
    )

    best_used_for = None
    if content_type == "note_type":
        best_used_for = _normalize_choice(
            _get_value(source, "taxonomy_best_used_for", "best_used_for"),
            {row["id"] for row in NOTE_TYPE_BEST_USED_FOR_OPTIONS},
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
    return _DOMAIN_MAP.get(str(value or "").strip())


def subject_label(value: str | None) -> str | None:
    option = _SUBJECT_MAP.get(str(value or "").strip())
    return option.get("label") if option else None


def difficulty_label(value: str | None) -> str | None:
    return _DIFFICULTY_MAP.get(str(value or "").strip())


def audience_label(value: str | None) -> str | None:
    return _AUDIENCE_MAP.get(str(value or "").strip())


def goal_labels(values: list[str]) -> list[str]:
    return [_GOAL_MAP[item] for item in values if item in _GOAL_MAP]


def topic_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    for item in values:
        if item in _TOPIC_MAP:
            labels.append(_TOPIC_MAP[item])
        elif item == "kanji":
            labels.append("Kanji")
    return labels


def feature_labels(values: list[str]) -> list[str]:
    return [_FEATURE_MAP[item] for item in values if item in _FEATURE_MAP]


def best_used_for_label(value: str | None) -> str | None:
    return _BEST_USED_FOR_MAP.get(str(value or "").strip())


def framework_level_to_difficulty(*, subject: str | None, framework: str | None, framework_level: str | None) -> str | None:
    if not subject or not framework or not framework_level:
        return None
    for level in _framework_level_options(subject, framework):
        if level["id"] == framework_level:
            return level.get("difficulty_band")
    return None


def framework_label(*, subject: str | None, framework: str | None) -> str | None:
    if not subject or not framework:
        return None
    for option in _framework_options(subject):
        if option["id"] == framework:
            return option["label"]
    return None


def framework_level_label(*, subject: str | None, framework: str | None, framework_level: str | None) -> str | None:
    if not subject or not framework or not framework_level:
        return None
    for option in _framework_level_options(subject, framework):
        if option["id"] == framework_level:
            return option["label"]
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
    return [dict(option) for option in SUBJECT_PACKS.get(subject, {}).get("frameworks", ())]


def _framework_level_options(subject: str | None, framework: str | None) -> list[dict[str, Any]]:
    if not subject or not framework:
        return []
    for option in SUBJECT_PACKS.get(subject, {}).get("frameworks", ()):
        if option["id"] == framework:
            return [dict(level) for level in option.get("levels", ())]
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
