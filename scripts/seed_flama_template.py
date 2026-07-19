import os
import sys
import csv
import json
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn để import models và app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app
from models import db
from models.flashcard import FieldDef, NoteType, Template, Note, Card
from models.deck import Deck
from models.card_progress import CardProgress
from app.services.flashcard_legacy import ensure_quiz_note_type
from app.utils.bootstrap_admin import (
    MissingBootstrapAdminCredentials,
    resolve_bootstrap_admin_credentials,
)

FRONT_HTML = """<div class="front-word">{{word}}</div>"""

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

CSS = """html,
body,
.card {
    margin: 0;
    padding: 0;
    height: 100%;
}
body {
    box-sizing: border-box;
}
.front-word {
    box-sizing: border-box;
    width: 100%;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    font-family: arial;
    font-size: clamp(48px, 9vw, 70px);
    font-weight: bold;
    line-height: 1.1;
    text-align: center;
    color: #e53c20;
    overflow-wrap: anywhere;
    word-break: break-word;
}
.card {
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

QUIZ_DUMP_ROOT = Path(__file__).resolve().parent.parent / "static" / "deck_dumps" / "trac_nghiem_markdown"
QUIZ_DUMP_MANIFEST = "deck_manifest.json"
QUIZ_DUMP_REQUIRED_COLUMNS = (
    "question",
    "answer_1",
    "answer_2",
    "answer_3",
    "answer_4",
    "correct_answer",
)


def _next_root_deck_position() -> int:
    max_pos = db.session.query(db.func.max(Deck.position)).filter(Deck.parent_id.is_(None)).scalar()
    return (max_pos or 0) + 1


def _normalize_correct_answer(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip()
    if candidate in {"1", "2", "3", "4"}:
        return candidate
    try:
        parsed = int(candidate)
    except (TypeError, ValueError):
        return "1"
    return str(parsed) if 1 <= parsed <= 4 else "1"


def _seed_quiz_dump_for_user(*, user_id: int, note_type_id: str, template_id: str) -> tuple[Deck | None, int]:
    manifest_path = QUIZ_DUMP_ROOT / QUIZ_DUMP_MANIFEST
    if not manifest_path.exists():
        print(f"Không tìm thấy quiz dump manifest: {manifest_path}. Bỏ qua seed deck Trắc nghiệm.")
        return None, 0

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Manifest quiz dump không hợp lệ: {manifest_path}.")
        return None, 0

    deck_name = str(manifest.get("deck_name") or "Trac Nghiem Co Ban").strip() or "Trac Nghiem Co Ban"
    dump_file_name = str(manifest.get("file") or "trac_nghiem_markdown.tsv").strip() or "trac_nghiem_markdown.tsv"
    dump_file = QUIZ_DUMP_ROOT / dump_file_name
    if not dump_file.exists():
        print(f"Không tìm thấy quiz dump file: {dump_file}.")
        return None, 0

    with dump_file.open("r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile, delimiter="\t")
        if not reader.fieldnames:
            print(f"Quiz dump thiếu header: {dump_file}.")
            return None, 0

        normalized = {name.strip().lower(): name for name in reader.fieldnames if name}
        missing = [column for column in QUIZ_DUMP_REQUIRED_COLUMNS if column not in normalized]
        if missing:
            print(f"Quiz dump thiếu cột bắt buộc: {', '.join(missing)}")
            return None, 0

        rows: list[dict[str, str]] = []
        for raw in reader:
            if not raw:
                continue
            question = str(raw.get(normalized["question"]) or "").strip()
            if not question:
                continue
            rows.append(
                {
                    "question": question,
                    "answer_1": str(raw.get(normalized["answer_1"]) or "").strip(),
                    "answer_2": str(raw.get(normalized["answer_2"]) or "").strip(),
                    "answer_3": str(raw.get(normalized["answer_3"]) or "").strip(),
                    "answer_4": str(raw.get(normalized["answer_4"]) or "").strip(),
                    "correct_answer": _normalize_correct_answer(raw.get(normalized["correct_answer"])),
                }
            )

    if not rows:
        print(f"Quiz dump không có dòng hợp lệ: {dump_file}.")
        return None, 0

    deck = (
        Deck.query.filter(
            Deck.parent_id.is_(None),
            Deck.owner_user_id == user_id,
            Deck.name == deck_name,
        )
        .order_by(Deck.id.asc())
        .first()
    )
    if deck is None:
        deck = Deck(
            parent_id=None,
            owner_user_id=user_id,
            note_type_id=note_type_id,
            name=deck_name,
            description=f"Seeded quiz dump from {dump_file.name}",
            position=_next_root_deck_position(),
        )
        db.session.add(deck)
        db.session.flush()
    elif not deck.note_type_id:
        deck.note_type_id = note_type_id

    existing_notes = (
        Note.query.filter(
            Note.user_id == user_id,
            Note.note_type_id == note_type_id,
            Note.deck_id == deck.id,
        )
        .all()
    )
    existing_note_ids = [note.id for note in existing_notes]
    if existing_note_ids:
        existing_card_ids = [
            row[0]
            for row in db.session.query(Card.id).filter(Card.note_id.in_(existing_note_ids)).all()
            if row and row[0]
        ]
        if existing_card_ids:
            CardProgress.query.filter(CardProgress.card_id.in_(existing_card_ids)).delete(synchronize_session=False)
        Card.query.filter(Card.note_id.in_(existing_note_ids)).delete(synchronize_session=False)
        Note.query.filter(Note.id.in_(existing_note_ids)).delete(synchronize_session=False)

    notes: list[Note] = []
    for row in rows:
        notes.append(
            Note(
                note_type_id=note_type_id,
                user_id=user_id,
                deck_id=deck.id,
                field_values={
                    "question": row["question"],
                    "answer_1": row["answer_1"],
                    "answer_2": row["answer_2"],
                    "answer_3": row["answer_3"],
                    "answer_4": row["answer_4"],
                    "correct_answer": row["correct_answer"],
                },
                tags=["quiz", "seeded"],
            )
        )
    db.session.add_all(notes)
    db.session.flush()

    db.session.add_all([Card(note_id=note.id, template_id=template_id) for note in notes])
    db.session.flush()
    return deck, len(notes)

def seed_template():
    app = create_app()
    with app.app_context():
        from models.user import User
        import os
        from dotenv import load_dotenv

        load_dotenv()
        try:
            credentials = resolve_bootstrap_admin_credentials(require_password=True)
        except MissingBootstrapAdminCredentials as exc:
            raise RuntimeError(
                "scripts/seed_flama_template.py yêu cầu ADMIN_EMAIL, ADMIN_USERNAME và ADMIN_PASSWORD trong .env."
            ) from exc
        admin_email = credentials.email
        admin_user = credentials.username
        admin_password = credentials.password

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

        if str(os.environ.get("SEED_TEST_USER", "")).strip().lower() in {"1", "true", "yes", "on"}:
            test_email = str(os.environ.get("TEST_USER_EMAIL") or "").strip()
            test_username = (
                str(os.environ.get("TEST_USER_USERNAME") or "").strip()
                or (test_email.split("@", 1)[0] if test_email and "@" in test_email else "")
            )
            test_password = str(os.environ.get("TEST_USER_PASSWORD") or "").strip()
            missing_fields = [
                field_name
                for field_name, value in (
                    ("TEST_USER_EMAIL", test_email),
                    ("TEST_USER_USERNAME", test_username),
                    ("TEST_USER_PASSWORD", test_password),
                )
                if not value
            ]
            if missing_fields:
                raise RuntimeError(
                    "SEED_TEST_USER=1 yêu cầu cấu hình đầy đủ: "
                    + ", ".join(missing_fields)
                    + "."
                )

            test_user = User.query.filter_by(email=test_email).first()
            if not test_user:
                test_user = User(
                    email=test_email,
                    username=test_username,
                    is_admin=False,
                )
                test_user.set_password(test_password)
                db.session.add(test_user)
                db.session.commit()
                print(f"Đã tạo test user: {test_email}")
            else:
                print(f"Test user đã tồn tại: {test_email}")

        # Kiểm tra xem NoteType "Flama Standard Vocabulary" đã có chưa
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
            ("example_audio", "audio", False),
        ]

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

        existing_fields = {
            field.name: field
            for field in FieldDef.query.filter_by(note_type_id=note_type.id).all()
        }
        created_fields = 0
        updated_fields = 0

        for i, (name, f_type, required) in enumerate(fields):
            field_def = existing_fields.get(name)
            if not field_def:
                db.session.add(
                    FieldDef(
                        note_type_id=note_type.id,
                        name=name,
                        field_type=f_type,
                        position=i,
                        required=required
                    )
                )
                created_fields += 1
                continue

            changed = False
            if field_def.field_type != f_type:
                field_def.field_type = f_type
                changed = True
            if bool(field_def.required) != bool(required):
                field_def.required = required
                changed = True
            if int(field_def.position or 0) != i:
                field_def.position = i
                changed = True
            if changed:
                updated_fields += 1

        db.session.commit()
        print(
            f"Đã đồng bộ field defs. created={created_fields}, "
            f"updated={updated_fields}, expected_total={len(fields)}"
        )

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

        quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, user.id)
        quiz_deck, quiz_note_count = _seed_quiz_dump_for_user(
            user_id=user.id,
            note_type_id=quiz_note_type.id,
            template_id=quiz_template.id,
        )
        db.session.commit()
        print(
            f"Đã seed NoteType Trắc nghiệm: note_type_id={quiz_note_type.id}, "
            f"template_id={quiz_template.id}"
        )
        if quiz_deck is not None:
            print(
                f"Đã seed deck Trắc nghiệm: deck_id={quiz_deck.id}, "
                f"name={quiz_deck.name}, notes={quiz_note_count}"
            )
        print("MIGRATION COMPLETED SUCCESSFULY!")

if __name__ == "__main__":
    seed_template()
