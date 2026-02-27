# Legacy Schema Audit + Migration Plan

Ngay audit: 2026-02-26

## Muc tieu
- Chuyen hoan toan sang mo hinh `Deck -> NoteType -> Note -> Card`.
- Loai bo dinh nghia/schema cu de tranh nham lan trong code va DB.

## Ket qua audit

### 1) Legacy schema van ton tai va con duoc dung
- `vocabulary_entries`: [models/vocabulary_entry.py](/workspaces/Flama/models/vocabulary_entry.py:6)
- `vocabulary_levels/topics/lessons`: [models/vocabulary_structure.py](/workspaces/Flama/models/vocabulary_structure.py:8)
- `vocabulary_progress.entry_id` (bridge cu): [models/vocabulary_progress.py](/workspaces/Flama/models/vocabulary_progress.py:13)
- `legacy_migration_maps`: [models/flashcard.py](/workspaces/Flama/models/flashcard.py:214)
- `review_events.entry_id` (bridge cu): [models/flashcard.py](/workspaces/Flama/models/flashcard.py:408)

### 2) Code layer con phu thuoc legacy
- Vocabulary CRUD/grid/import theo lesson-entry:
  - [app/routes/vocabulary.py](/workspaces/Flama/app/routes/vocabulary.py:45)
  - [app/routes/vocabulary.py](/workspaces/Flama/app/routes/vocabulary.py:2122)
  - [app/routes/vocabulary.py](/workspaces/Flama/app/routes/vocabulary.py:2366)
  - [app/routes/vocabulary.py](/workspaces/Flama/app/routes/vocabulary.py:2552)
- Template grid hardcode field cu:
  - [templates/vocabulary_lesson.html](/workspaces/Flama/templates/vocabulary_lesson.html:113)
- Flashcards marketplace/shared preview van fallback `VocabularyEntry`:
  - [app/routes/flashcards.py](/workspaces/Flama/app/routes/flashcards.py:338)
  - [app/routes/flashcards.py](/workspaces/Flama/app/routes/flashcards.py:788)
  - [app/routes/flashcards.py](/workspaces/Flama/app/routes/flashcards.py:1136)
  - [app/routes/flashcards.py](/workspaces/Flama/app/routes/flashcards.py:1263)
  - [app/routes/flashcards.py](/workspaces/Flama/app/routes/flashcards.py:3597)
- Stats layer van join theo `entry_id`:
  - [app/services/stats_today_future.py](/workspaces/Flama/app/services/stats_today_future.py:133)
  - [app/services/stats_today_future.py](/workspaces/Flama/app/services/stats_today_future.py:224)
- CLI/seed van tao `VocabularyEntry` va legacy note type:
  - [app/cli.py](/workspaces/Flama/app/cli.py:22)
  - [app/cli.py](/workspaces/Flama/app/cli.py:194)
  - [app/cli.py](/workspaces/Flama/app/cli.py:505)
  - [app/services/flashcard_legacy.py](/workspaces/Flama/app/services/flashcard_legacy.py:7)
  - [scripts/seed_flama_template.py](/workspaces/Flama/scripts/seed_flama_template.py:255)

### 3) Migration system risk
- Khong co revision file trong `migrations/versions` (hien tai rong).
- App dang phu thuoc `db.create_all()` + patch schema runtime:
  - [app/__init__.py](/workspaces/Flama/app/__init__.py:114)
  - [app/__init__.py](/workspaces/Flama/app/__init__.py:143)

## Cleanup da lam trong dot nay
- Da xoa cac dinh nghia legacy khong con call-site trong `vocabulary.py`:
  - `_select_next_card(...)` (entry-based)
  - `_render_study_flashcard(...)` wrapper cu
  - route `POST /vocabulary/study/entry/<entry_id>/answer`
  - route `POST /vocabulary/study/card/<entry_id>/edit`

## Script audit du lieu
- Script moi: [scripts/audit_legacy_schema.py](/workspaces/Flama/scripts/audit_legacy_schema.py:1)
- Chay:
  - `python scripts/audit_legacy_schema.py`

## Ke hoach migrate de drop schema cu

### Phase A - Cat phu thuoc runtime vao legacy rows
1. Chuyen `stats_today_future` va cac metric deck usage sang `new_card_id -> Card -> Note` 100%.
2. Bo fallback `VocabularyEntry` trong shared deck preview/test samples.
3. Bo clone `VocabularyEntry` khi install deck; chi clone `Note/Card`.
4. Chuyen lesson/import UI sang dynamic NoteType fields (hoac retire `/vocabulary/lesson`).
5. Chuan hoa CLI seeding/import de tao `Note/Card` truc tiep.

### Phase B - Dong bo du lieu
1. Bao dam moi progress active dung `new_card_id` (khong con can `entry_id`).
2. Bao dam `ReviewEvent.card_id` la card id that (khong con `entry:*`).
3. Xac minh migration map hoac bo map neu da khong can trace.

### Phase C - Drop schema cu
1. Drop/bo ref:
   - `review_events.entry_id`
   - `vocabulary_progress.entry_id` + constraint `uq_vocabulary_progress_user_entry`
   - `legacy_migration_maps`
2. Drop bang legacy:
   - `vocabulary_entries`
   - `vocabulary_lessons`
   - `vocabulary_topics`
   - `vocabulary_levels`
3. Xoa model/file/service/test legacy lien quan.
4. Tao migration Alembic thuc su cho toan bo thay doi, khong phu thuoc patch runtime.

## Tieu chi go-live de drop
- `python scripts/audit_legacy_schema.py` cho ket qua:
  - `progress rows with entry_id = 0`
  - `review_events rows with entry_id = 0`
  - `legacy entries missing migration map = 0` (neu van giu map den truoc luc drop)
- Tat ca integration test quan trong pass sau khi bo fallback legacy.
