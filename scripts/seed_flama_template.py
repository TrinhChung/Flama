import os
import sys

# Thêm thư mục gốc vào đường dẫn để import models và app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db
from models.flashcard import FieldDef, NoteType, Template

FRONT_HTML = """<div style='height:100vh;text-align:center;display:flex;justify-content:center;align-items:center;font-size:70px;font-weight:bold;color:#e53c20'>
{{word}}
</div>"""

BACK_HTML = """<div style='
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

CSS = """.card {
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

def seed_template():
    app = create_app()
    with app.app_context():
        from models.user import User
        import os
        from dotenv import load_dotenv

        load_dotenv()
        admin_email = os.environ.get("ADMIN_EMAIL", "chungtrinh2k2@gmail.com")
        admin_user = os.environ.get("ADMIN_USER", "chungtrinh2k2")
        admin_password = os.environ.get("ADMIN_PASSWORD", "chungtrinh1904")

        user = User.query.filter_by(email=admin_email).first()
        if not user:
            user = User(
                email=admin_email,
                username=admin_user,
                is_admin=True,
            )
            user.set_password(admin_password)
            db.session.add(user)
            db.session.commit()
            print(f"Đã tạo admin user mới: {admin_email}")
        else:
            if not user.is_admin:
                user.is_admin = True
                db.session.commit()
                print(f"Đã cập nhật quyền admin cho user: {admin_email}")

        # Kiểm tra xem NoteType "Flama Standard Vocabulary" đã có chưa
        note_type = NoteType.query.filter_by(name="Flama Standard Vocabulary", user_id=user.id).first()
        if not note_type:
            note_type = NoteType(
                name="Flama Standard Vocabulary",
                id="default-flama-vocab-000000000000",  # Hardcoded UUID cho dễ ref
                user_id=user.id,
                description="Official default Japanese vocabulary note type by Flama.",
                primary_category="Japanese",
                tags=["official", "default", "japanese", "vocabulary"],
                preview_text="Word / Reading / Meaning / Example layout.",
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                is_official=True,
                publish_status="published",
            )
            db.session.add(note_type)
            db.session.commit()
            print("Đã khởi tạo NoteType: Flama Standard Vocabulary (published)")

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

        # Đảm bảo NoteType đã publish nếu chạy lại script
        if note_type.publish_status != "published":
            note_type.publish_status = "published"
            note_type.is_official = True
            note_type.primary_category = note_type.primary_category or "Japanese"
            note_type.tags = note_type.tags or ["official", "default", "japanese"]
            note_type.pricing_mode = note_type.pricing_mode or "free"
            note_type.price_cents = note_type.price_cents if note_type.price_cents is not None else 0
            db.session.commit()
            print("Đã publish NoteType lên marketplace.")
        print("MIGRATION COMPLETED SUCCESSFULY!")

if __name__ == "__main__":
    seed_template()
