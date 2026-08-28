"""Worksheet template catalog and schema definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldSlot:
    key: str
    label_vi: str
    label_en: str
    required: bool = True
    description_vi: str = ""
    suggested_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorksheetTemplate:
    id: str
    name_vi: str
    name_en: str
    description_vi: str
    description_en: str
    category: str  # 'kanji' | 'vocabulary' | 'table'
    supported_orientations: tuple[str, ...] = ("portrait", "landscape")
    default_orientation: str = "portrait"
    default_rows_per_page: int = 5
    field_slots: tuple[FieldSlot, ...] = field(default_factory=tuple)
    default_options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


# 1. Kanji Stroke Practice Template
KANJI_STROKE_TEMPLATE = WorksheetTemplate(
    id="kanji_stroke",
    name_vi="Luyện viết Kanji chuẩn (Stroke Practice)",
    name_en="Kanji Stroke Order Practice",
    description_vi="Mẫu luyện viết chữ Hán tiêu chuẩn với chữ mẫu to, sơ đồ thứ tự từng nét, các ô mờ để đồ chữ (trace) và các ô trống kẻ lưới hướng dẫn.",
    description_en="Standard Japanese Kanji practice sheet with large reference character, stroke order diagrams, faint tracing boxes, and guided writing grid.",
    category="kanji",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=5,
    field_slots=(
        FieldSlot(
            key="kanji",
            label_vi="Trường Kanji / Từ chứa chữ Hán",
            label_en="Kanji / Expression Field",
            required=True,
            description_vi="Hệ thống sẽ tự động trích xuất các chữ Hán (Kanji/Hanzi) từ trường này.",
            suggested_names=("Expression", "Kanji", "Word", "Vocab", "Hanzi", "Front"),
        ),
        FieldSlot(
            key="reading",
            label_vi="Trường cách đọc (Furigana / Kana / Pinyin)",
            label_en="Reading Field",
            required=False,
            description_vi="Hiển thị cách đọc bên dưới chữ Hán.",
            suggested_names=("Reading", "Furigana", "Kana", "Pinyin", "Pronunciation"),
        ),
        FieldSlot(
            key="meaning",
            label_vi="Trường ý nghĩa (Hán Việt / Tiếng Việt / Nghĩa)",
            label_en="Meaning Field",
            required=False,
            description_vi="Hiển thị nghĩa hoặc âm Hán Việt.",
            suggested_names=("Meaning", "Definition", "HanViet", "Vietnamese", "Back"),
        ),
    ),
    default_options={
        "grid_style": "cross",  # 'cross' (+) | 'diagonal' (*) | 'square' (box)
        "trace_count": 2,       # Number of faint tracing boxes
        "practice_count": 5,    # Number of blank practice boxes
        "show_stroke_diagram": True,
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 5,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "standard",   # 'compact' | 'standard' | 'wide'
        "locale": "ja",         # 'ja' | 'zh' | 'zh-hant'
    },
)

# 2. Kanji Compact Practice Template
KANJI_COMPACT_TEMPLATE = WorksheetTemplate(
    id="kanji_compact",
    name_vi="Luyện viết Kanji nhiều dòng (Compact Practice)",
    name_en="Kanji Compact Multi-row Practice",
    description_vi="Mẫu thu gọn chứa nhiều chữ Hán trên 1 trang A4, sơ đồ nét tinh gọn kèm nhiều ô luyện viết liên tiếp (thích hợp ôn tập tốc hành).",
    description_en="Compact multi-character layout per page with mini stroke order diagrams and high-density writing squares.",
    category="kanji",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=8,
    field_slots=(
        FieldSlot(
            key="kanji",
            label_vi="Trường Kanji / Từ chứa chữ Hán",
            label_en="Kanji / Expression Field",
            required=True,
            description_vi="Hệ thống sẽ trích xuất chữ Hán từ trường này.",
            suggested_names=("Expression", "Kanji", "Word", "Vocab", "Hanzi"),
        ),
        FieldSlot(
            key="reading",
            label_vi="Trường cách đọc",
            label_en="Reading Field",
            required=False,
            suggested_names=("Reading", "Furigana", "Kana"),
        ),
        FieldSlot(
            key="meaning",
            label_vi="Trường ý nghĩa",
            label_en="Meaning Field",
            required=False,
            suggested_names=("Meaning", "Definition", "HanViet"),
        ),
    ),
    default_options={
        "grid_style": "cross",
        "trace_count": 1,
        "practice_count": 7,
        "show_stroke_diagram": True,
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 8,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
        "locale": "ja",
    },
)

# 3. Vocabulary Writing Practice Template
VOCAB_WRITING_TEMPLATE = WorksheetTemplate(
    id="vocab_writing",
    name_vi="Luyện viết từ vựng (Vocabulary Writing Table)",
    name_en="Vocabulary Writing Practice Table",
    description_vi="Bảng từ vựng chia cột: Từ gốc, Cách đọc, Nghĩa và các ô/dòng kẻ trống để viết lại từ nhiều lần.",
    description_en="Structured table with word, reading, meaning columns and handwriting practice space.",
    category="vocabulary",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=12,
    field_slots=(
        FieldSlot(
            key="word",
            label_vi="Trường từ vựng (Word / Expression)",
            label_en="Word Field",
            required=True,
            suggested_names=("Expression", "Word", "Vocab", "Front"),
        ),
        FieldSlot(
            key="reading",
            label_vi="Trường cách đọc (Reading / Kana)",
            label_en="Reading Field",
            required=False,
            suggested_names=("Reading", "Furigana", "Kana"),
        ),
        FieldSlot(
            key="meaning",
            label_vi="Trường ý nghĩa (Meaning / Definition)",
            label_en="Meaning Field",
            required=False,
            suggested_names=("Meaning", "Definition", "Vietnamese", "Back"),
        ),
    ),
    default_options={
        "practice_type": "boxes",  # 'boxes' | 'lines' | 'grid'
        "practice_boxes_count": 5,
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 12,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "standard",
    },
)

# 4. Recall & Cloze Worksheet Template
VOCAB_RECALL_TEMPLATE = WorksheetTemplate(
    id="vocab_recall",
    name_vi="Bài tập kiểm tra trí nhớ (Recall & Cloze Worksheet)",
    name_en="Recall & Cloze Practice Worksheet",
    description_vi="Hiển thị đề bài bằng cách đọc / ý nghĩa và ẩn từ gốc, để trống ô kẻ cho người học tự nhớ lại và viết từ vào.",
    description_en="Prompt sheet showing reading and meaning while hiding the target word for active recall handwriting tests.",
    category="vocabulary",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=14,
    field_slots=(
        FieldSlot(
            key="word",
            label_vi="Trường từ mục tiêu cần nhớ (Target Word - Sẽ ẩn đi)",
            label_en="Target Word Field (Hidden)",
            required=True,
            suggested_names=("Expression", "Word", "Vocab", "Kanji"),
        ),
        FieldSlot(
            key="prompt_reading",
            label_vi="Trường gợi ý cách đọc (Reading Prompt)",
            label_en="Reading Prompt Field",
            required=False,
            suggested_names=("Reading", "Furigana", "Kana"),
        ),
        FieldSlot(
            key="prompt_meaning",
            label_vi="Trường gợi ý ý nghĩa (Meaning Prompt)",
            label_en="Meaning Prompt Field",
            required=True,
            suggested_names=("Meaning", "Definition", "Vietnamese", "Back"),
        ),
    ),
    default_options={
        "show_reading_hint": True,
        "show_word_length_hint": False,
        "rows_per_page": 14,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "standard",
    },
)

# 5. Generic Deck Table Template
DECK_TABLE_TEMPLATE = WorksheetTemplate(
    id="deck_table",
    name_vi="Bảng dữ liệu bộ thẻ tuỳ biến (Generic Deck Table)",
    name_en="Generic Deck Table Worksheet",
    description_vi="Mẫu bảng đa năng cho phép chọn tự do các trường trong bộ thẻ làm cột hiển thị, kèm tuỳ chọn cột luyện viết trống.",
    description_en="Customizable table worksheet where you can pick any fields as visible columns with an optional blank practice column.",
    category="table",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=15,
    field_slots=(
        FieldSlot(
            key="custom_columns",
            label_vi="Danh sách các cột muốn hiển thị",
            label_en="Visible Columns",
            required=True,
            description_vi="Chọn 1 hoặc nhiều trường trong Note Type để tạo các cột.",
        ),
    ),
    default_options={
        "include_practice_column": True,
        "practice_column_label": "Ghi chú / Luyện viết",
        "rows_per_page": 15,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "standard",
    },
)

TEMPLATE_CATALOG: dict[str, WorksheetTemplate] = {
    KANJI_STROKE_TEMPLATE.id: KANJI_STROKE_TEMPLATE,
    KANJI_COMPACT_TEMPLATE.id: KANJI_COMPACT_TEMPLATE,
    VOCAB_WRITING_TEMPLATE.id: VOCAB_WRITING_TEMPLATE,
    VOCAB_RECALL_TEMPLATE.id: VOCAB_RECALL_TEMPLATE,
    DECK_TABLE_TEMPLATE.id: DECK_TABLE_TEMPLATE,
}


def get_template(template_id: str) -> WorksheetTemplate | None:
    """Get worksheet template by ID."""
    return TEMPLATE_CATALOG.get(str(template_id or "").strip())


def list_templates() -> list[dict[str, Any]]:
    """List all available worksheet templates serialized as dictionaries."""
    return [tpl.to_dict() for tpl in TEMPLATE_CATALOG.values()]
