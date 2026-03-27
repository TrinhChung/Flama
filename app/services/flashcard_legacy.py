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

LEGACY_FRONT_TEMPLATE = """<div class="legacy-front">{{word}}</div>"""

LEGACY_BACK_TEMPLATE = """
<div class="legacy-back">
  <div class="word-line">{{word}}</div>
  {{#reading}}<div class="reading-line">{{reading}} {{#hanviet}}「{{hanviet}}」{{/hanviet}}</div>{{/reading}}
  {{#translation_vi}}<div class="translation-line">{{translation_vi}}</div>{{/translation_vi}}
  {{#meaning_jp}}<div class="meaning-jp">{{{meaning_jp}}}</div>{{/meaning_jp}}
  {{#meaning_vi}}<div class="meaning-vi">{{{meaning_vi}}}</div>{{/meaning_vi}}
  {{#usage_jp}}<div class="usage-jp">{{{usage_jp}}}</div>{{/usage_jp}}
  {{#usage_vi}}<div class="usage-vi">{{{usage_vi}}}</div>{{/usage_vi}}
  {{#example_jp}}<div class="example-jp">{{{example_jp}}}</div>{{/example_jp}}
  {{#example_vi}}<div class="example-vi">{{{example_vi}}}</div>{{/example_vi}}
  {{#additional_note_jp}}<div class="note-jp">{{{additional_note_jp}}}</div>{{/additional_note_jp}}
  {{#additional_note_vi}}<div class="note-vi">{{{additional_note_vi}}}</div>{{/additional_note_vi}}
  {{#image}}<div class="image">{{{image}}}</div>{{/image}}
  {{#diagram}}<div class="diagram">{{{diagram}}}</div>{{/diagram}}
  {{#word_audio}}<div class="word-audio">{{{word_audio}}}</div>{{/word_audio}}
  {{#example_audio}}<div class="example-audio">{{{example_audio}}}</div>{{/example_audio}}
</div>
"""

LEGACY_SHARED_CSS = """
.legacy-front { font-size: 52px; text-align: center; color: #e53c20; font-weight: 700; padding: 1rem; }
.legacy-back { font-family: Arial, sans-serif; font-size: 18px; line-height: 1.6; }
.legacy-back .word-line { font-size: 36px; color: #e53c20; font-weight: 700; }
.legacy-back .reading-line { color: #0f5132; font-weight: 700; }
.legacy-back .translation-line { color: #198754; margin-bottom: 0.5rem; }
.legacy-back .meaning-jp, .legacy-back .usage-jp, .legacy-back .example-jp, .legacy-back .note-jp { color: #3367d6; margin-top: 0.5rem; }
.legacy-back .meaning-vi, .legacy-back .usage-vi, .legacy-back .example-vi, .legacy-back .note-vi { color: #495057; margin-top: 0.3rem; }
.legacy-back img { max-width: 100%; height: auto; }
"""

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
    for position, (name, field_type, required) in enumerate(LEGACY_FIELD_DEFS):
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
            name="Default Flama Flashcard",
            front_html=LEGACY_FRONT_TEMPLATE.strip(),
            back_html=LEGACY_BACK_TEMPLATE.strip(),
            shared_css=LEGACY_SHARED_CSS.strip(),
            position=0,
            is_default=True,
        )
        db_session.add(template)
    else:
        if not template.front_html:
            template.front_html = LEGACY_FRONT_TEMPLATE.strip()
        if not template.back_html:
            template.back_html = LEGACY_BACK_TEMPLATE.strip()
        if not template.shared_css:
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
