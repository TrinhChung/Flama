# P6-00 — Card/Template ownership inventory and risk reproduction

> 2026-09-30. Code baseline: `phase5/p5-11-note-hardening` (PR #173). Production counts from a SELECT-only query on 2026-09-30.

## 1. Production shape

| Measure | Value |
|---|---|
| Templates / NoteTypes | 24 / 24 (no NoteType has two Templates) |
| Notes / Cards | 40,257 / 40,257 (no Note has two Cards) |
| ReviewEvents (detached from a live Card) | 129,245 (595) |
| Connect card refs | 15,965 |
| Learners by authority | 18 NOTE, 0 LEGACY |
| Deck installs | 17, all `logical_overlay` |

Consequence: Note-level counting (D6-04) and occurrence backfill change no number seen today.

## 2. Card creation (14 call sites, 11 files)

| # | Path | Where |
|---|---|---|
| 1 | REST note create | `flashcard_content_service._create_cards` |
| 2 | Yomitan/AnkiConnect add | `connect/actions.add_note` |
| 3–4 | Connect import reconcile (LEGACY / NOTE) | `connect/import_cards._reconcile_note_cards`, `_reconcile_note_authority_cards` |
| 5 | CSV import | `flashcard_import` |
| 6–7 | Template add (share paths) | `flashcards_share_service.create_template`, `share/note_types.create_template` |
| 8 | Note sync | `note_sync_service.execute_sync_notes` |
| 9 | MCP note create | `mcp/note_tools.create_note` |
| 10–11 | MCP NoteType update | `mcp/note_type_tools.update_note_type` |
| 12 | NOTE sibling expansion | `study_note_template_service` |
| 13–14 | Seed CLI | `seeding_service` |

**Seam (P6-05):** instead of editing each site, a `before_flush` hook in `models/study_application.py` gives every new Template its compatibility occurrence and binds every new Card without an explicit occurrence to it. A caller applying a Template twice sets `Card.application` itself. The hook covers future call sites too.

## 3. Card/Template deletion

| Path | Operation | Learner data |
|---|---|---|
| `flashcard_content_service.delete_template` | bulk-delete the Template's Cards, delete Template | NOTE state kept (partial sibling removal, P5) |
| `study_note_template_service` | delete Template after sibling state copy | NOTE state kept |
| `mcp/note_type_tools.update_note_type` | bulk-delete Cards of a removed Template | NOTE state kept |
| `connect/import_cards` | delete Cards absent from the package | reconcile |
| `deck_management_service` | deck purge | lifecycle-coordinated (P5-06) |
| `seeding_service` | reseed | operator tool, refuses NOTE learners |

## 4. Foreign keys to cards/templates (after migration 46)

| Column | On delete | Disposition |
|---|---|---|
| `cards.template_id` | CASCADE | unchanged |
| `cards.application_id` | CASCADE (new) | occurrence removed with its Template |
| `card_progress.card_id` | CASCADE | compatibility projection only; NOTE state lives on the subject |
| `study_session_cards.card_id` | CASCADE | unchanged; affected sessions are cancelled by the P5 content-delete flow |
| `connect_source_card_refs.card_id` | **SET NULL** (was CASCADE) | ref, ordinal and sync cursors survive on `note_id` (D6-05 B) |
| `study_progress_contributors.live_card_id` | SET NULL | unchanged |
| `review_events.card_id` | text, no FK | `note_id` snapshot added (D6-07) |

## 5. Readers by Template or per Card

- Composition: `study_composition_service` filters `Card.template_id`; compatibility composition IDs are unchanged for `compat` occurrences.
- Counts per Card → per Note behind `STUDY_NOTE_COUNT_ENABLED`: `deck_aggregation_service` (dashboard), `browse_card_service.build_browse_deck_tree`, `study_authority_read_service.summarize_study_authority_queue` (`/api/study/next`, MCP).
- Anki ordinal: `anki_sync_service._card_for_ord` maps through `application.source_ord`; the positional fallback remains only for Notes without bound ordinals.

## 6. Risk reproduction (now regression tests)

| Risk (P6 plan §3.4) | Test | Result |
|---|---|---|
| Template reorder or removal remaps an Anki `ord` to another sibling | `test_anki_ordinal_follows_the_occurrence_not_the_template_position` | reorder keeps the mapping; removed ordinal is refused |
| Card removal cascades the Connect ref and its cursors | `probe_p6_application_schema_mysql.py` (`connect_ref_survives_card_delete`) | ref kept with `card_id` NULL and its `note_id` |
| A two-Template Note counts twice | `tests/test_study_note_level_counts.py` | counts once with the flag on |
