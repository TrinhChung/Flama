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
from models.flashcard import Note, Card
from models.deck import Deck
from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
    ensure_legacy_note_type,
    ensure_quiz_note_type,
)
from app.services import study_progress_lifecycle_mirror_service
from app.repositories.study_authority_repository import lock_study_authority_route
from app.utils.bootstrap_admin import (
    MissingBootstrapAdminCredentials,
    resolve_bootstrap_admin_credentials,
)

FRONT_HTML = LEGACY_FRONT_TEMPLATE
BACK_HTML = LEGACY_BACK_TEMPLATE
CSS = LEGACY_SHARED_CSS

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
    # This helper replaces whole Note/Card sets; callers must retain the
    # learner fence until the transaction containing its writes is committed.
    lock_study_authority_route(db.session, learner_user_id=int(user_id))
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
            lifecycle_plan = study_progress_lifecycle_mirror_service.prepare_lifecycle_mirror(
                db.session,
                removed_card_ids=existing_card_ids,
                deleted_note_ids=existing_note_ids,
            )
        else:
            lifecycle_plan = study_progress_lifecycle_mirror_service.prepare_lifecycle_mirror(
                db.session,
                removed_card_ids=(),
                deleted_note_ids=existing_note_ids,
            )
        study_progress_lifecycle_mirror_service.finalize_lifecycle_mirror(
            lifecycle_plan,
            transition_code="TOMBSTONED_SUBJECT_DELETED",
            source_path="seed.flama_template_replace",
            operation_key=f"seed-flama-template-replace:{deck.id}:{dump_file.name}",
        )
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
            db.session.flush()
            from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
            enroll_new_learner_note_authority(db.session, user=user)
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
                db.session.flush()
                from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
                enroll_new_learner_note_authority(db.session, user=test_user)
                db.session.commit()
                print(f"Đã tạo test user: {test_email}")
            else:
                print(f"Test user đã tồn tại: {test_email}")

        # Keep one learner fence across NoteType updates and quiz Note/Card
        # replacement. The earlier admin-account commits do not touch content.
        lock_study_authority_route(db.session, learner_user_id=int(user.id))
        note_type, template = ensure_legacy_note_type(db.session, user.id)
        quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, user.id)
        quiz_deck, quiz_note_count = _seed_quiz_dump_for_user(
            user_id=user.id,
            note_type_id=quiz_note_type.id,
            template_id=quiz_template.id,
        )
        db.session.commit()
        print(
            "Đã đồng bộ Flama Standard Vocabulary từ canonical seed: "
            f"note_type_id={note_type.id}, template_id={template.id}"
        )
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
