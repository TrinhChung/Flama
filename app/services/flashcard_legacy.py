"""Default note type seed helpers used by migration and API flows."""

from __future__ import annotations

from models.flashcard import FieldDef, NoteType, Template

LEGACY_NOTE_TYPE_NAME = "Flama Standard Vocabulary"

LEGACY_FIELD_DEFS = [
    ("word", "text", True),
    ("hanviet", "text", False),
    ("reading", "text", False),
    ("translation_vi", "text", False),
    ("meaning_jp", "richtext", False),
    ("meaning_vi", "richtext", False),
    ("usage_jp", "richtext", False),
    ("usage_vi", "richtext", False),
    ("example_jp", "richtext", False),
    ("example_vi", "richtext", False),
    ("additional_note_jp", "richtext", False),
    ("additional_note_vi", "richtext", False),
    ("image", "image", False),
    ("diagram", "image", False),
    ("word_audio", "audio", False),
    ("example_audio", "audio", False),
]

LEGACY_FRONT_TEMPLATE = """<div style='height:100vh;text-align:center;display:flex;justify-content:center;align-items:center;font-size:70px;font-weight:bold;color:#e53c20'>
{{word}}
</div>"""

LEGACY_BACK_TEMPLATE = r"""<div style='
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    text-align: start;
    padding-left: 20px;
    font-family: "Arial";
    font-size: 18px;'
>
    <!-- Hiển thị từ vựng -->
    <div style='
        font-family: "Arial";
        font-size: 36px;
        font-weight: bold;
        display: flex;
        align-items: center;
        color: #e53c20;
        padding-top: 20px;'
    >
        {{word}}
{{#word_audio}}
  <audio id="custom-audio" src="{{word_audio}}"></audio>
  <button onclick="document.getElementById('custom-audio').play()">🔊</button>
{{/word_audio}}
    </div>

    <!-- Hiển thị cách đọc -->
    {{#reading}}
    <div style='
        display: flex;
        font-weight: bold;
        font-family: "Arial";
        font-size: 20px;
        flex-direction: column;
        text-transform: uppercase;'
    >
        <div style='font-family: "Arial"; display: flex'>
            {{reading}} 「{{hanviet}}」
        </div>
        <div style='color: green; display: flex; padding-bottom: 10px' auto-split>
            {{translation_vi}}
        </div>
    </div>
    {{/reading}}

    <!-- Hiển thị giải thích -->
    {{#meaning_jp}}
    <div style='display: flex; padding-top: 20px; color: #3367d6' auto-split>
        ◆ {{meaning_jp}}
    </div>
    {{/meaning_jp}}

    {{#meaning_vi}}
    <div style='display: flex; padding-top: 10px' auto-split>
        {{meaning_vi}}
    </div>
    {{/meaning_vi}}

<!-- Ảnh minh hoạ stroke order -->
{{#image}}
<div class="kanji-stroke-images">
  {{image}}
</div>
{{/image}}

    <!-- Hiển thị cách sử dụng -->
    {{#usage_jp}}
    <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
        ◆ Cách sử dụng:
    </div>
    <div style='display: flex; flex-direction: column; padding-top: 10px;'>
        <div style="font-size: 20px;" auto-split>{{usage_jp}}</div>
        {{#usage_vi}}
        <div style="font-size: 16px; color: gray; margin-left: 10px;" auto-split>{{usage_vi}}</div>
        {{/usage_vi}}
    </div>
    {{/usage_jp}}

    <!-- Hiển thị ví dụ -->
    {{#example_jp}}
    <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
        ◆ Câu ví dụ:
    </div>
    <div style='display: flex; flex-direction: column; padding-top: 10px;'>
        <div style="font-size: 20px; display: flex; align-items: center;" auto-split>
            {{example_jp}}
{{#example_audio}}
  <audio id="example-audio" src="{{example_audio}}"></audio>
  <button onclick="document.getElementById('example-audio').play()">🔊</button>
{{/example_audio}}
        </div>
        {{#example_vi}}
        <div style="font-size: 16px; color: gray; margin-left: 10px;" auto-split>{{example_vi}}</div>
        {{/example_vi}}
    </div>
    {{/example_jp}}

    <!-- Hiển thị ghi chú -->
    {{#additional_note_jp}}
    <div style='display: flex; padding-top: 20px; font-family: "Arial";color: #3367d6'>
        ◆ Ghi chú:
    </div>
    <div style='display: flex; padding-top: 10px' auto-split>
        {{additional_note_jp}}
    </div>
    {{/additional_note_jp}}

    {{#additional_note_vi}}
    <div style='display: flex; padding-top: 10px;font-family: "Arial"; color: gray; font-size: 16px;' auto-split>
        {{additional_note_vi}}
    </div>
    {{/additional_note_vi}}

{{#diagram}}
<div class="kanji-stroke-images">
  {{diagram}}
</div>
{{/diagram}}
</div>

<!-- Script phát âm từ vựng và ví dụ -->
<script>
  (() => {
    const wordAudio = document.getElementById("custom-audio");
    const exampleAudio = document.getElementById("example-audio");

    if (wordAudio) {
      wordAudio.play().catch(err => {
        console.error("Không thể phát âm từ vựng:", err);
      });

      wordAudio.onended = () => {
        setTimeout(() => {
          if (exampleAudio) {
            exampleAudio.play().catch(err => {
              console.error("Không thể phát câu ví dụ:", err);
            });
          }
        }, 500);
      };
    }
  })();

(function() {
  const selectorList = [
    'div[auto-split]'
  ];

  selectorList.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
      let text = el.innerHTML;

      text = text
        .replace(/\$/g, "<br>");

      el.innerHTML = text;
    });
  });
})();
</script>"""

LEGACY_SHARED_CSS = """.card {
    font-family: arial;
    font-size: 20px;
    text-align: center;
    color: black;
    background-color: white;
}
.kanji-stroke-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-start;
  align-items: flex-start;
  margin-top: 15px;
  line-height: 0;
}

/* Desktop: ảnh cao 180px, width auto giữ tỉ lệ */
.kanji-stroke-images > img {
  height: 180px;
  width: auto;
  object-fit: contain;
  border-radius: 6px;
  display: block;
  margin: 0 5px 10px 0; /* khoảng cách ảnh */
  flex: none;           /* không chiếm % chiều ngang */
}

/* Điện thoại: 2 ảnh 1 dòng, mỗi ảnh 48% chiều ngang, chiều cao theo % màn hình */
@media (max-width: 480px) {
  .kanji-stroke-images > img {
    flex: 0 0 48%;       /* 2 ảnh 1 dòng */
    height: 38vw;        /* chiều cao theo % màn hình */
    width: auto;         /* width tự động */
    margin: 0;
  }
}

/* Điện thoại nhỏ hơn: 1 ảnh 1 dòng */
@media (max-width: 320px) {
  .kanji-stroke-images > img {
    flex: 0 0 100%;      /* 1 ảnh 1 dòng */
    height: 68vw;        /* chiều cao theo % màn hình */
    width: auto;
  }
}"""

QUIZ_NOTE_TYPE_NAME = "Tr\u1eafc nghi\u1ec7m"

QUIZ_FIELD_DEFS = [
    ("question", "markdown", True),
    ("answer_1", "markdown", True),
    ("answer_2", "markdown", True),
    ("answer_3", "markdown", True),
    ("answer_4", "markdown", True),
    # Store 1|2|3|4 as the correct option index.
    ("correct_answer", "text", True),
]

QUIZ_FRONT_TEMPLATE = """
<div class="quiz-front">
  <div class="quiz-question">{{{question}}}</div>
  <ol class="quiz-options">
    <li>{{{answer_1}}}</li>
    <li>{{{answer_2}}}</li>
    <li>{{{answer_3}}}</li>
    <li>{{{answer_4}}}</li>
  </ol>
</div>
"""

QUIZ_BACK_TEMPLATE = """
<div class="quiz-back">
  <div class="quiz-question">{{{question}}}</div>
  <ol class="quiz-options">
    <li>1. {{{answer_1}}}</li>
    <li>2. {{{answer_2}}}</li>
    <li>3. {{{answer_3}}}</li>
    <li>4. {{{answer_4}}}</li>
  </ol>
  <div class="quiz-correct">Dap an dung: {{correct_answer}}</div>
</div>
"""

QUIZ_SHARED_CSS = """
.quiz-front, .quiz-back {
  font-family: Arial, sans-serif;
  font-size: 20px;
  line-height: 1.5;
}
.quiz-question {
  font-size: 28px;
  font-weight: 700;
  color: #e53c20;
  margin-bottom: 0.85rem;
}
.quiz-options {
  margin: 0;
  padding-left: 1.2rem;
}
.quiz-options li {
  margin: 0.25rem 0;
}
.quiz-correct {
  margin-top: 1rem;
  font-weight: 700;
  color: #198754;
}
"""


def ensure_legacy_note_type(db_session, user_id: int) -> tuple[NoteType, Template]:
    note_type = (
        db_session.query(NoteType)
        .filter(NoteType.user_id == user_id, NoteType.name == LEGACY_NOTE_TYPE_NAME)
        .first()
    )
    if note_type is None:
        note_type = NoteType(
            user_id=user_id,
            name=LEGACY_NOTE_TYPE_NAME,
            description="Official default Japanese vocabulary note type by Flama.",
            primary_category="Japanese",
            tags=["official", "default", "japanese", "vocabulary"],
            preview_text="Word / Reading / Meaning / Example layout.",
            pricing_mode="free",
            price_amount_minor=0,
            version="1.0.0",
            is_official=True,
            publish_status="published",
        )
        db_session.add(note_type)
        db_session.flush()

    existing_fields = {field.name: field for field in note_type.field_defs}
    has_identity_field = any(
        field.identity_role == "primary" for field in existing_fields.values()
    )
    for position, (name, field_type, required) in enumerate(LEGACY_FIELD_DEFS):
        field = existing_fields.get(name)
        if field is None:
            identity_role = "primary" if name == "word" and not has_identity_field else None
            field = FieldDef(
                note_type_id=note_type.id,
                name=name,
                field_type=field_type,
                required=required,
                position=position,
                identity_role=identity_role,
            )
            db_session.add(field)
            has_identity_field = has_identity_field or identity_role == "primary"
        else:
            field.field_type = field_type
            field.required = required
            field.position = position
            if name == "word" and not has_identity_field:
                field.identity_role = "primary"
                has_identity_field = True

    template = (
        db_session.query(Template)
        .filter(Template.note_type_id == note_type.id)
        .order_by(Template.position.asc(), Template.created_at.asc())
        .first()
    )
    if template is None:
        template = Template(
            note_type_id=note_type.id,
            name="Default Flama Flashcard",
            front_html=LEGACY_FRONT_TEMPLATE.strip(),
            back_html=LEGACY_BACK_TEMPLATE.strip(),
            shared_css=LEGACY_SHARED_CSS.strip(),
            position=0,
            is_default=True,
        )
        db_session.add(template)
    else:
        template.front_html = LEGACY_FRONT_TEMPLATE.strip()
        template.back_html = LEGACY_BACK_TEMPLATE.strip()
        template.shared_css = LEGACY_SHARED_CSS.strip()
        template.is_default = True

    db_session.flush()
    return note_type, template


def ensure_quiz_note_type(db_session, user_id: int) -> tuple[NoteType, Template]:
    note_type = (
        db_session.query(NoteType)
        .filter(NoteType.user_id == user_id, NoteType.name == QUIZ_NOTE_TYPE_NAME)
        .first()
    )
    if note_type is None:
        note_type = NoteType(
            user_id=user_id,
            name=QUIZ_NOTE_TYPE_NAME,
            description="Seeded multiple-choice note type.",
            primary_category="General",
            tags=["official", "default", "quiz", "multiple-choice"],
            preview_text="Question (markdown) + 4 answers (markdown) + correct answer index (1-4).",
            pricing_mode="free",
            price_amount_minor=0,
            version="1.0.0",
            is_official=True,
            publish_status="published",
        )
        db_session.add(note_type)
        db_session.flush()

    existing_fields = {field.name: field for field in note_type.field_defs}
    for position, (name, field_type, required) in enumerate(QUIZ_FIELD_DEFS):
        field = existing_fields.get(name)
        if field is None:
            field = FieldDef(
                note_type_id=note_type.id,
                name=name,
                field_type=field_type,
                required=required,
                position=position,
            )
            db_session.add(field)
        else:
            field.field_type = field_type
            field.required = required
            field.position = position

    template = (
        db_session.query(Template)
        .filter(Template.note_type_id == note_type.id)
        .order_by(Template.position.asc(), Template.created_at.asc())
        .first()
    )
    if template is None:
        template = Template(
            note_type_id=note_type.id,
            name="Default Quiz Flashcard",
            front_html=QUIZ_FRONT_TEMPLATE.strip(),
            back_html=QUIZ_BACK_TEMPLATE.strip(),
            shared_css=QUIZ_SHARED_CSS.strip(),
            position=0,
            is_default=True,
        )
        db_session.add(template)
    else:
        if not template.front_html:
            template.front_html = QUIZ_FRONT_TEMPLATE.strip()
        if not template.back_html:
            template.back_html = QUIZ_BACK_TEMPLATE.strip()
        if not template.shared_css:
            template.shared_css = QUIZ_SHARED_CSS.strip()
        template.is_default = True

    db_session.flush()
    return note_type, template
