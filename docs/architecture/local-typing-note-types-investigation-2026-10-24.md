# Local typing NoteTypes: investigation

Date: 2026-10-24. Mode: INVESTIGATE. Target: local MySQL 8.0.40,
`localhost/nihongo`, owner resolved from En4Everyone's supplied ID.
Database inspection used direct SQLAlchemy connections with
`START TRANSACTION READ ONLY`; the Flask factory was not started.

## Scope and result

The account has 12 local NoteTypes, matching the user's list. The connected
Flama MCP returned a different dataset (6 NoteTypes, with different attachments
and note counts). Its earlier review must not be treated as a local inventory.

Five local NoteTypes named after typing interactions contain test data. They
are separate from the reusable Template definitions with similar names.
No application code, schema, or database data was changed by this investigation.

## Finding 1: real test NoteTypes explain the five extra typing entries

- **Observed:** all five NoteTypes have `created_at=2026-10-11 03:58:16`
  (raw database timestamp). Each has one ACTIVE StudyApplication and one deck
  referencing its schema. All 14 notes carry `test` and `typing` tags; each
  containing deck describes itself as a test for that template.
- **Evidence:** read-only joins of `note_types`, `field_defs`, `notes`, `decks`,
  `study_applications`, and `templates`; identities below match the user's IDs.
  The prototype also contains a reference `note_type` schema alongside the
  independent `template` and `input_schema`:
  [typing-reading/prototype.json](../../note-type-templates/typing-reading/prototype.json).
- **Potential concern:** test schemas named exactly like interactions make the
  NoteType list look as though a presentation mode needs its own content schema.
- **Impact:** removing these NoteTypes would affect 14 actual test notes and
  their deck references; they are not empty metadata rows.
- **Unknowns:** the exact historical script/operator that created this batch
  was not established. The test purpose is verified from deck descriptions and
  tags, rather than inferred from names alone.

| Local NoteType | ID | Fields | Notes | Deck |
| --- | --- | ---: | ---: | --- |
| Gõ cách đọc | `0b9a37e5-c8ff-427d-bc50-b3a2d2bb00c6` | 7 | 2 | 6856: 3. Luyện gõ - Gõ cách đọc (Reading) |
| Gõ chép chính tả | `bb5f70a3-b3e1-4e92-acca-19e4076ef7bb` | 5 | 6 | 6859: 6. Luyện gõ - Gõ chép chính tả (Dictation) |
| Gõ đáp án | `a3048e55-6fd9-40d0-ba18-e5d01f17ae94` | 2 | 2 | 6860: 7. Luyện gõ - Gõ đáp án JS (Basic Answer) |
| Gõ nghĩa | `f9912e3a-a270-4520-956e-c0f44752d3e3` | 8 | 2 | 6857: 4. Luyện gõ - Gõ nghĩa (Meaning) |
| Gõ từ qua ảnh | `9e80eb7b-4d91-449f-9336-973d8605db83` | 6 | 2 | 6858: 5. Luyện gõ - Gõ từ qua ảnh (Image) |

## Finding 2: creating a reusable Template does not create a NoteType

- **Observed:** `Template` is an independently owned definition;
  `StudyApplication` explicitly attaches it to an existing NoteType and maps
  template inputs to that schema's FieldDef IDs. Four typing definitions were
  created at `2026-10-11 01:36:53`, before their test NoteTypes. The basic answer
  definition was created with its test NoteType. On this local account these
  five definitions are attached only to their corresponding test NoteTypes.
- **Evidence:** [Template](../../models/template.py),
  [StudyApplication](../../models/study_application.py),
  [attachment migration](../../migrations/versions/20261007_000054_expand_template_attachments.py),
  `create_template()` and `attach_template()` in
  [template_library_service.py](../../app/services/template_library_service.py).
  The [typing instructions](../../note-type-templates/typing-reading/README.md)
  explicitly describe the NoteType schema as reference material and give input
  mappings for existing Japanese, English, and Chinese schemas.
- **Potential concern:** template `input_schema` describes required inputs;
  it must not be confused with a new set of persisted NoteType fields.
- **Impact:** the existing attachment mechanism can present the same content
  through different typing templates without creating another NoteType.
- **Unknowns:** availability in other environments is outside this local check.

## Finding 3: Sentence Card has a different purpose

- **Observed:** local `Sentence Card` has seven fields, one note, one ACTIVE
  `Sentence` template, and deck `Sentences` (6863). It is a sentence-mining schema.
- **Evidence:** [connect/mining_setup.py](../../app/services/connect/mining_setup.py)
  explicitly creates the NoteType with `Sentence`, `Word`, `Definition`, `Image`,
  `Audio`, `Source`, and `URL`, plus its template and deck.
- **Potential concern:** its name ends in Card, but it identifies content fields,
  unlike the five interaction names above.
- **Impact:** it should not be classified as another typing demo merely by name.
- **Unknowns:** this inspection did not establish whether its one note is still
  wanted by the user or inspect external clients using its model name.

## Validation and limits

- Verified IDs, creation times, local field/note/deck counts, tags and all ACTIVE
  attachments of the five typing definitions directly on local MySQL.
- Confirmed the NoteType API reads real NoteType rows via
  [flashcard_content_service.py](../../app/services/flashcard_content_service.py)
  and its summary repository; it does not fabricate NoteTypes from Templates.
- Counts are a point-in-time observation. No deletion/merge dependency audit,
  cleanup, migration, or application test run was performed.
