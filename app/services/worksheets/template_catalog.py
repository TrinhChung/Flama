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


def calculate_optimal_rows_per_page(
    template_id: str,
    orientation: str = "portrait",
    margin: str = "compact",
    extra_blank_rows: int = 0,
    box_size: int = 36,
) -> int:
    """Calculate the exact number of items/rows per page to fill 100% of an A4 sheet."""
    is_landscape = str(orientation).lower() == "landscape"
    box_size = max(10, min(int(box_size or 36), 120))
    extra_blanks = max(0, min(int(extra_blank_rows or 0), 10))

    if template_id in {"kanji_stroke", "kanji_compact"}:
        usable_height = 580 if is_landscape else 900
        item_height = (box_size + 16) + min(3, extra_blanks) * (box_size + 6)
        optimal_rows = max(1, min(24, int(usable_height // item_height)))
        return optimal_rows

    elif template_id == "vocab_writing":
        usable_height = 580 if is_landscape else 900
        row_height = 36 + min(3, extra_blanks) * 30
        return max(1, min(30, int(usable_height // row_height)))

    elif template_id == "vocab_recall":
        return 12 if is_landscape else 18

    elif template_id == "sentence_writing":
        usable_height = 660 if is_landscape else 940
        lines_cnt = max(1, min(10, extra_blanks if extra_blanks > 0 else 3))
        row_h = 42 + lines_cnt * 24
        return max(1, min(10, int(usable_height // row_h)))

    elif template_id == "grammar_practice":
        usable_height = 660 if is_landscape else 940
        lines_cnt = max(1, min(10, extra_blanks if extra_blanks > 0 else 3))
        row_h = 50 + lines_cnt * 24
        return max(1, min(8, int(usable_height // row_h)))

    elif template_id == "genkouyoushi":
        return 20 if not is_landscape else 14

    return 6 if is_landscape else 8


# 1. Kanji Stroke Practice Template
KANJI_STROKE_TEMPLATE = WorksheetTemplate(
    id="kanji_stroke",
    name_vi="Luyện viết Kanji chuẩn (Stroke Practice)",
    name_en="Kanji Stroke Order Practice",
    description_vi="Mẫu luyện viết chữ Hán tiêu chuẩn với chữ mẫu to, sơ đồ thứ tự từng nét, các ô mờ để đồ chữ (trace) và dải ô lưới luyện viết liền mạch tiết kiệm giấy.",
    description_en="Standard Japanese Kanji practice sheet with large reference character, stroke order diagrams, faint tracing boxes, and continuous guided writing grid.",
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
        "practice_count": 6,    # Number of blank practice boxes
        "show_stroke_diagram": True,
        "reference_char_color": "#e11d48",
        "stroke_color_mode": "monochrome",  # 'monochrome' | 'multicolor' | 'same_as_reference'
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 8,
        "auto_fit_page": True,
        "box_size": 36,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",   # 'compact' | 'standard' | 'wide'
        "locale": "ja",         # 'ja' | 'zh' | 'zh-hant'
    },
)

# 2. Kanji Compact Practice Template
KANJI_COMPACT_TEMPLATE = WorksheetTemplate(
    id="kanji_compact",
    name_vi="Luyện viết Kanji nhiều dòng (Compact Practice)",
    name_en="Kanji Compact Multi-row Practice",
    description_vi="Mẫu thu gọn tối đa chứa nhiều chữ Hán trên 1 trang A4, sơ đồ nét tinh gọn kèm nhiều ô luyện viết liền kề (thích hợp ôn tập tốc hành, siêu tiết kiệm giấy photo).",
    description_en="Compact multi-character layout per page with mini stroke order diagrams and high-density writing squares.",
    category="kanji",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=10,
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
        "practice_count": 8,
        "show_stroke_diagram": True,
        "reference_char_color": "#e11d48",
        "stroke_color_mode": "monochrome",  # 'monochrome' | 'multicolor' | 'same_as_reference'
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 10,
        "auto_fit_page": True,
        "box_size": 30,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
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
    description_vi="Bảng từ vựng chia cột: Từ gốc, Cách đọc, Nghĩa và dải ô kẻ liền mạch để viết lại từ nhiều lần.",
    description_en="Structured table with word, reading, meaning columns and handwriting practice space.",
    category="vocabulary",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=16,
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
        "practice_boxes_count": 6,
        "show_reading": True,
        "show_meaning": True,
        "rows_per_page": 16,
        "auto_fit_page": True,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
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
    default_rows_per_page=18,
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
        "rows_per_page": 18,
        "auto_fit_page": True,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
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
    default_rows_per_page=22,
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
        "rows_per_page": 22,
        "auto_fit_page": True,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
        "watermark_enabled": True,
        "watermark_text": "flama.app",
        "watermark_opacity": 0.04,
    },
)

# 6. Sentence Writing & Translation Template
SENTENCE_WRITING_TEMPLATE = WorksheetTemplate(
    id="sentence_writing",
    name_vi="Mẫu câu & Dịch câu / Đoạn văn (Sentence Practice)",
    name_en="Sentence Writing & Translation Worksheet",
    description_vi="Mẫu câu mẫu từ thẻ, bên dưới có các dòng kẻ tự do để học sinh tự dịch, chép lại hoặc viết thành đoạn văn (tuỳ chỉnh số dòng kẻ).",
    description_en="Sample sentence practice sheet with custom writing lines below for translation or paragraph writing.",
    category="sentence",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=6,
    field_slots=(
        FieldSlot(
            key="sentence",
            label_vi="Trường câu mẫu / Ví dụ (Sample Sentence)",
            label_en="Sample Sentence Field",
            required=True,
            description_vi="Trường chứa câu mẫu hoặc ví dụ cần luyện tập.",
            suggested_names=("Example", "Sentence", "Expression", "Word", "Front"),
        ),
        FieldSlot(
            key="reading",
            label_vi="Trường cách đọc / Phiên âm câu mẫu (Furigana / Romaji)",
            label_en="Reading / Furigana Field",
            required=False,
            description_vi="Hiển thị cách đọc phụ âm phía trên hoặc bên dưới câu mẫu.",
            suggested_names=("Example_Reading", "ExampleReading", "Reading", "Furigana"),
        ),
        FieldSlot(
            key="meaning",
            label_vi="Trường ý nghĩa / Bản dịch câu mẫu",
            label_en="Meaning / Translation Field",
            required=False,
            description_vi="Hiển thị bản dịch câu mẫu hoặc ẩn đi để học sinh tự dịch.",
            suggested_names=("Example_Meaning", "ExampleMeaning", "Meaning", "Definition", "Vietnamese", "Back"),
        ),
    ),
    default_options={
        "writing_lines_count": 3,
        "writing_line_style": "dashed",
        "show_sample_sentence": True,
        "show_sample_reading": True,
        "show_sample_meaning": True,
        "auto_fit_page": True,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
        "watermark_enabled": True,
        "watermark_text": "flama.app",
        "watermark_opacity": 0.04,
    },
)

# 7. Grammar Practice & Custom Prompts Template
GRAMMAR_PRACTICE_TEMPLATE = WorksheetTemplate(
    id="grammar_practice",
    name_vi="Ngữ pháp & Đặt câu theo đề bài (Grammar Practice)",
    name_en="Grammar Practice & Custom Prompts Worksheet",
    description_vi="Hiển thị cấu trúc ngữ pháp/từ vựng mục tiêu, đi kèm đề bài/yêu cầu bài tập tuỳ chỉnh của giáo viên và dòng kẻ để học sinh làm bài.",
    description_en="Grammar pattern & vocab worksheet with customizable exercise instructions/prompts and ruled answer lines.",
    category="grammar",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=5,
    field_slots=(
        FieldSlot(
            key="grammar_point",
            label_vi="Trường cấu trúc ngữ pháp / Điểm ngữ pháp mục tiêu",
            label_en="Grammar Point Field",
            required=True,
            description_vi="Trường chứa điểm ngữ pháp hoặc từ vựng trọng tâm.",
            suggested_names=("Expression", "Grammar", "Pattern", "Word", "Front"),
        ),
        FieldSlot(
            key="meaning_usage",
            label_vi="Trường ý nghĩa / Cách dùng / Giải thích",
            label_en="Meaning / Usage Field",
            required=False,
            description_vi="Hiển thị giải thích ý nghĩa hoặc cấu trúc kết nối của ngữ pháp.",
            suggested_names=("Meaning", "Usage", "Explanation", "Definition", "Vietnamese"),
        ),
        FieldSlot(
            key="example",
            label_vi="Trường câu ví dụ minh hoạ",
            label_en="Example Sentence Field",
            required=False,
            description_vi="Ví dụ minh hoạ ngữ pháp làm gợi ý cho học sinh.",
            suggested_names=("Example", "Sentence", "Sample"),
        ),
    ),
    default_options={
        "exercise_prompt": "Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:",
        "writing_lines_count": 3,
        "writing_line_style": "dashed",
        "show_explanation": True,
        "show_example_hint": True,
        "auto_fit_page": True,
        "extra_blank_rows": 0,
        "fill_blank_rows": True,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
        "watermark_enabled": True,
        "watermark_text": "flama.app",
        "watermark_opacity": 0.04,
    },
)

# 8. Genkouyoushi / Chinese Essay Writing Paper Template (400-grid / 200-grid / Blank practice)
GENKOUYOUSHI_TEMPLATE = WorksheetTemplate(
    id="genkouyoushi",
    name_vi="Giấy luyện viết văn (Genkō Yōshi / 作文纸 400 ô)",
    name_en="Manuscript Paper (Genkō Yōshi / 400-Grid Essay)",
    description_vi="Giấy kẻ ô luyện viết văn chuẩn Nhật & Trung (400 ô / 200 ô) với các hàng ô vuông kèm dải đệm ghi chú và khung thông tin học sinh, hỗ trợ tạo trang trắng hoặc điền văn bản mẫu.",
    description_en="Standard Japanese Genkō Yōshi and Chinese manuscript essay paper (400/200 squares) with student header and horizontal spacer bands, ideal for blank handwriting practice worksheets or reference text tracing.",
    category="essay",
    supported_orientations=("portrait", "landscape"),
    default_orientation="portrait",
    default_rows_per_page=20,
    field_slots=(
        FieldSlot(
            key="custom_text",
            label_vi="Đoạn văn bản / Câu mẫu cần chép (Nếu có)",
            label_en="Reference Text / Sentences (Optional)",
            required=False,
            description_vi="Nhập đoạn văn bản để điền vào từng ô vuông (hoặc để trống nếu in trang trắng luyện viết).",
            suggested_names=("Sentence", "Example", "Expression", "Text", "Content"),
        ),
    ),
    default_options={
        "grid_columns": 20,
        "grid_rows": 20,
        "box_style": "square",  # 'square' (plain) | 'cross' (+) | 'diagonal' (*)
        "grid_color": "#475569",  # Charcoal grey (photocopy safe)
        "has_spacer_band": True,
        "spacer_height": 10,
        "content_mode": "blank",  # 'blank' | 'text' | 'trace'
        "custom_text": "",
        "header_student_style": "chinese",  # 'chinese' (班级/姓名/学号/分数) | 'vietnamese' | 'japanese' | 'none'
        "title_placement": "none",  # 'none' (all boxes blank) | 'header' | 'first_row'
        "footer_date_format": "chinese",  # 'chinese' (年 月 日) | 'vietnamese' | 'none'
        "footer_brand_label": "Flama (400格)",
        "essay_page_count": 1,
        "paper_size": "a4",
        "orientation": "portrait",
        "margin": "compact",
        "watermark_enabled": True,
        "watermark_text": "flama.app",
        "watermark_opacity": 0.035,
    },
)

TEMPLATE_CATALOG: dict[str, WorksheetTemplate] = {
    KANJI_STROKE_TEMPLATE.id: KANJI_STROKE_TEMPLATE,
    KANJI_COMPACT_TEMPLATE.id: KANJI_COMPACT_TEMPLATE,
    VOCAB_WRITING_TEMPLATE.id: VOCAB_WRITING_TEMPLATE,
    VOCAB_RECALL_TEMPLATE.id: VOCAB_RECALL_TEMPLATE,
    DECK_TABLE_TEMPLATE.id: DECK_TABLE_TEMPLATE,
    SENTENCE_WRITING_TEMPLATE.id: SENTENCE_WRITING_TEMPLATE,
    GRAMMAR_PRACTICE_TEMPLATE.id: GRAMMAR_PRACTICE_TEMPLATE,
    GENKOUYOUSHI_TEMPLATE.id: GENKOUYOUSHI_TEMPLATE,
}


def get_template(template_id: str) -> WorksheetTemplate | None:
    """Get worksheet template by ID."""
    return TEMPLATE_CATALOG.get(str(template_id or "").strip())


def list_templates() -> list[dict[str, Any]]:
    """List all available worksheet templates serialized as dictionaries."""
    return [tpl.to_dict() for tpl in TEMPLATE_CATALOG.values()]
