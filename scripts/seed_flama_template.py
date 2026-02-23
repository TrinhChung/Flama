import os
import sys

# Thêm thư mục gốc vào đường dẫn để import models và app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db
from models.flashcard import FieldDef, NoteType, Template

FRONT_HTML = """<div class="card-front-body">
  <div class="card-front-word">{{ word }}</div>
</div>
<!-- Footer -->
<div class="card-front-footer">
  <small class="card-hint">Click to reveal answer</small>
</div>"""

BACK_HTML = """<div style='display: flex; flex-direction: column; justify-content: flex-start; text-align: start; padding-left: 20px; font-family: "Arial"; font-size: 18px;'>
  <div style='font-family: "Arial"; font-size: 36px; font-weight: bold; display: flex; align-items: center; color: #e53c20; padding-top: 20px;'>
    {{ word }}
    {% if word_audio %}
    <audio id="custom-audio" src="{{ word_audio }}"></audio>
    <button onclick="document.getElementById('custom-audio').play()">🔊</button>
    {% endif %}
  </div>

  {% if reading %}
  <div style='display: flex; font-weight: bold; font-family: "Arial"; font-size: 20px; flex-direction: column; text-transform: uppercase;'>
    <div style='font-family: "Arial"; display: flex'>
      {{ reading }} 「{{ hanviet or '' }}」
    </div>
    <div style='color: green; display: flex; padding-bottom: 10px' auto-split>
      {{ translation_vi or '' }}
    </div>
  </div>
  {% endif %}

  {% if meaning_jp %}
  <div style='display: flex; padding-top: 20px; color: #3367d6' auto-split>
    ◆ {{ meaning_jp }}
  </div>
  {% endif %}

  {% if meaning_vi %}
  <div style='display: flex; padding-top: 10px' auto-split>
    {{ meaning_vi }}
  </div>
  {% endif %}

  {% if image %}
  <div class="kanji-stroke-images">
    {{ image|safe }}
  </div>
  {% endif %}

  {% if usage_jp %}
  <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
    ◆ Cách sử dụng:
  </div>
  <div style='display: flex; flex-direction: column; padding-top: 10px;'>
    <div style="font-size: 20px;" auto-split>{{ usage_jp }}</div>
    {% if usage_vi %}
    <div style="font-size: 16px; color: gray; margin-left: 10px;" auto-split>{{ usage_vi }}</div>
    {% endif %}
  </div>
  {% endif %}

  {% if example_jp %}
  <div style='display: flex; padding-top: 20px; color: #3367d6; font-weight: bold;'>
    ◆ Câu ví dụ:
  </div>
  <div style='display: flex; flex-direction: column; padding-top: 10px;'>
    <div style="font-size: 20px; display: flex; align-items: center;" auto-split>
      {{ example_jp }}
      {% if example_audio %}
      <audio id="example-audio" src="{{ example_audio }}"></audio>
      <button onclick="document.getElementById('example-audio').play()">🔊</button>
      {% endif %}
    </div>
    {% if example_vi %}
    <div style="font-size: 16px; color: gray; margin-left: 10px;" auto-split>{{ example_vi }}</div>
    {% endif %}
  </div>
  {% endif %}

  {% if additional_note_jp %}
  <div style='display: flex; padding-top: 20px; font-family: "Arial";color: #3367d6'>
    ◆ Ghi chú:
  </div>
  <div style='display: flex; padding-top: 10px' auto-split>
    {{ additional_note_jp }}
  </div>
  {% endif %}

  {% if additional_note_vi %}
  <div style='display: flex; padding-top: 10px;font-family: "Arial"; color: gray; font-size: 16px;' auto-split>
    {{ additional_note_vi }}
  </div>
  {% endif %}

  {% if diagram %}
  <div>{{ diagram|safe }}</div>
  {% endif %}
</div>"""

CSS = """/* Tuỳ chọn CSS nếu cần bổ sung cho thẻ review */
.kanji-stroke-images img {
    max-width: 100%;
}
"""

def seed_template():
    app = create_app()
    with app.app_context():
        from models.user import User
        user = User.query.first()
        if not user:
            print("Lỗi: Không tìm thấy User nào trong DB để gán chủ sở hữu cho NoteType.")
            return

        # Kiểm tra xem NoteType "Flama Standard Vocabulary" đã có chưa
        note_type = NoteType.query.filter_by(name="Flama Standard Vocabulary", user_id=user.id).first()
        if not note_type:
            note_type = NoteType(
                name="Flama Standard Vocabulary",
                id="default-flama-vocab-000000000000",  # Hardcoded UUID cho dễ ref
                user_id=user.id
            )
            db.session.add(note_type)
            db.session.commit()
            print("Đã khởi tạo NoteType: Flama Standard Vocabulary")

            # Tạo list các trường động (Khớp với columns của VocabularyEntry)
            fields = [
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
                ("example_audio", "audio", False)
            ]

            for i, (name, f_type, required) in enumerate(fields):
                field_def = FieldDef(
                    note_type_id=note_type.id,
                    name=name,
                    field_type=f_type,
                    position=i,
                    required=required
                )
                db.session.add(field_def)
            
            db.session.commit()
            print(f"Đã seed {len(fields)} fields cho NoteType.")

        # Cập nhật hoặc tạo mới Template
        template_name = "Default Flama Flashcard"
        template = Template.query.filter_by(note_type_id=note_type.id, name=template_name).first()
        if not template:
            template = Template(
                id="default-template-000000000000",
                note_type_id=note_type.id,
                name=template_name,
                front_html=FRONT_HTML,
                back_html=BACK_HTML,
                shared_css=CSS,
                is_default=True,
                position=0
            )
            db.session.add(template)
            print(f"Đã tạo Template: {template_name}")
        else:
            template.front_html = FRONT_HTML
            template.back_html = BACK_HTML
            template.shared_css = CSS
            print(f"Đã nạp lại nội dung HTML mới nhất vào Template hiện có: {template_name}")
            
        db.session.commit()
        print("MIGRATION COMPLETED SUCCESSFULY!")

if __name__ == "__main__":
    seed_template()
