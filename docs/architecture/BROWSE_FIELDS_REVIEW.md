# Browse fields: review and implementation plan

Date: 2026-10-13. Scope: React Browse field editing, native arrays, and the shared Study content update path.

## Observed data contract

`FieldDef` defines each field's name, order, type and required flag. `Note.field_values` is the authoritative JSON object; its keys are field names. Cards refer to the Note, so changing one card's fields changes its sibling cards' content.

Evidence: `models/field_def.py`, `models/note.py`, `models/card.py`, `models/field_types.py`, and `app/validators/flashcard_input.py`.

Array fields store lists of plain text or nested lists. Legacy values can be newline strings. Backend writes accept either a native list or lines; a JSON-looking **string** remains literal text. The Code editor must therefore parse JSON before sending the API payload. Nested lists retain their structure; Mustache receives the stored list directly.

Owned Browse edits go through `app/api/v1/learning/browse.py` → `app/services/browse_card_service.py` → note validation/persistence. Installed shared decks use release content plus `DeckCloneNoteFieldOverride`; learner edits must only create local deltas. This review requires no schema migration or production data rewrite.

## Findings and fixes

| Priority | Observed problem and evidence | Impact | Implemented fix |
| --- | --- | --- | --- |
| P1 | `ArrayFieldInput` converted values through flat display items when changing modes. | A nested list could become text or a flat list; merely viewing Code marked the note dirty. | Separate presentation from the draft value. Mode switches never emit changes. Nested lists and multiline items use Code. |
| P1 | Invalid Code content only displayed a warning; Browse save still normalized it as lines. | Broken JSON could be saved as unintended text items. | Validate text/list JSON recursively and block Save and Ctrl+Enter until corrected. |
| P1 | Browse DTOs and Study update contracts used `Record<string, string>`. Create coerced values with `String(value)`. | Runtime list values could be flattened despite native JSON storage. | Use `Record<string, unknown>` at content boundaries; convert only display text. Parse Code into native lists for create/update. |
| P1 | Save success used current form state and current card selection to update Study. | Server sanitization could be missed; selecting another card while saving could update the wrong session content. | Capture the submitted card and draft. Apply the committed API response to that card; preserve newer local edits. |
| P2 | Every detail query update repopulated the editor. | Background refresh discarded unsaved fields. | Hydrate new cards and pristine editors; retain dirty drafts on refresh. |
| P2 | Edit sent the complete field object. | Unchanged clone fields became unnecessary overrides; unrelated obsolete keys could fail validation. | PATCH only changed field values; untouched lists remain unchanged. |
| P2 | Multiline selection relied on field name/value heuristics. | Short richtext/markdown fields opened in a single-line input. | Respect the declared richtext/markdown type in create and edit. |
| P2 | Creation could use fallback field definitions when the selected note type was absent. | Field definitions could disagree with the submitted note type ID. | Require the exact selected type and loaded fields before enabling creation. |

The shared Study quick editor also serializes arrays and blocks invalid Code drafts, so Browse's editor changes remain compatible there. Stroke text extraction uses `fieldValueEditorText()` rather than comma-stringifying arrays.

## Execution plan

1. **Completed:** trace the stored field contract, owned writes, clone overlays and Study synchronization.
2. **Completed:** separate array presentation from storage and serialize native list payloads.
3. **Completed:** add validation, partial field updates, type-aware multiline inputs, draft preservation and committed-response synchronization.
4. **Completed:** regression tests for create/edit/revert, invalid JSON, nested arrays, background refresh and card selection during an in-flight save; API tests for owned notes and clone delta isolation; frontend build and browser layout checks.

Validation results:

- `tests/test_flashcard_api_integration.py`: 89 tests passed, including native nested array Browse writes and clone-only overrides.
- `tests/test_field_array_conversion.py`: 12 tests passed, including legacy lines, nested lists and repeated array items.
- Focused frontend suites passed for array utilities/input, Browse state/forms/page, stroke modal, Study quick edit, content patch adapter and persisted sessions.
- `npm run build` passed (TypeScript and Vite). `npm run lint` passed with existing warnings outside this change.
- Chrome screenshots reviewed at 1440×1000 and 390×844; invalid Code disables Save and mode switching, and Revert restores the nested list. Screenshots: `output/playwright/browse-fields-desktop.png` and `output/playwright/browse-fields-mobile.png`.

## Verification boundaries

Backend integration tests use SQLite. They verify list persistence, compatibility and clone isolation, not production MySQL data distribution. No MySQL DDL or query changes are included in this field fix.

Browser checks use an isolated Chrome profile and mock API responses. Existing local database data is not used for visual verification. Existing Browse query/retirement changes in the working tree are preserved.

Broader follow-ups outside this fix: optimistic conflict detection between multiple editors, explicit handling of obsolete field definitions, and decomposition of the large Browse state hook. These should be separate changes with their own behavior and visual checks.
