"""Legacy note type seed helpers used by migration and API flows."""

from __future__ import annotations

from models.flashcard import FieldDef, NoteType, Template

LEGACY_NOTE_TYPE_NAME = "Legacy Japanese"

LEGACY_FIELD_DEFS = [
    ("Word", "text", True),
    ("hanviet", "text", False),
    ("Reading", "text", False),
    ("Translation_VI", "text", False),
    ("Meaning_JP", "richtext", False),
    ("Meaning_VI", "richtext", False),
    ("Usage_JP", "richtext", False),
    ("Usage_VI", "richtext", False),
    ("Example_JP", "richtext", False),
    ("Example_VI", "richtext", False),
    ("Additional_Note_JP", "richtext", False),
    ("Additional_Note_VI", "richtext", False),
    ("image", "image", False),
    ("Diagram", "diagram", False),
    ("Word_Audio", "audio", False),
    ("Example_Audio", "audio", False),
]

LEGACY_FRONT_TEMPLATE = """<div class="legacy-front">{{Word}}</div>"""

LEGACY_BACK_TEMPLATE = """
<div class="legacy-back">
  <div class="word-line">{{Word}}</div>
  {{#Reading}}<div class="reading-line">{{Reading}} {{#hanviet}}「{{hanviet}}」{{/hanviet}}</div>{{/Reading}}
  {{#Translation_VI}}<div class="translation-line">{{Translation_VI}}</div>{{/Translation_VI}}
  {{#Meaning_JP}}<div class="meaning-jp">{{{Meaning_JP}}}</div>{{/Meaning_JP}}
  {{#Meaning_VI}}<div class="meaning-vi">{{{Meaning_VI}}}</div>{{/Meaning_VI}}
  {{#Usage_JP}}<div class="usage-jp">{{{Usage_JP}}}</div>{{/Usage_JP}}
  {{#Usage_VI}}<div class="usage-vi">{{{Usage_VI}}}</div>{{/Usage_VI}}
  {{#Example_JP}}<div class="example-jp">{{{Example_JP}}}</div>{{/Example_JP}}
  {{#Example_VI}}<div class="example-vi">{{{Example_VI}}}</div>{{/Example_VI}}
  {{#Additional_Note_JP}}<div class="note-jp">{{{Additional_Note_JP}}}</div>{{/Additional_Note_JP}}
  {{#Additional_Note_VI}}<div class="note-vi">{{{Additional_Note_VI}}}</div>{{/Additional_Note_VI}}
  {{#image}}<div class="image">{{{image}}}</div>{{/image}}
  {{#Diagram}}<div class="diagram">{{{Diagram}}}</div>{{/Diagram}}
  {{#Word_Audio}}<div class="word-audio">{{{Word_Audio}}}</div>{{/Word_Audio}}
  {{#Example_Audio}}<div class="example-audio">{{{Example_Audio}}}</div>{{/Example_Audio}}
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


def ensure_legacy_note_type(db_session, user_id: int) -> tuple[NoteType, Template]:
    note_type = (
        db_session.query(NoteType)
        .filter(NoteType.user_id == user_id, NoteType.name == LEGACY_NOTE_TYPE_NAME)
        .first()
    )
    if note_type is None:
        note_type = NoteType(user_id=user_id, name=LEGACY_NOTE_TYPE_NAME)
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
            name="Legacy",
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
