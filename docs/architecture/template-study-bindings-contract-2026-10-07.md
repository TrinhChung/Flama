# Template study preparation contract — 2026-10-07

Status: backend preparation/preset/session runtime implemented; Gemini frontend phases remain unimplemented. This contract follows U1/U3/U6 and uses the existing canonical `/api` routes registered through `wsgi.py -> create_app()`. It does not introduce scheduler policy or queue changes.

## Preparation data

`GET /api/study/scopes/deck/<deck_id>/compositions?include_template_inputs=1` retains `study-scope-compositions.v2`, `groups`, `compositions`, `cardinality`, and `default_composition_id`. With this opt-in flag it adds `template_inputs`, keyed by the exact opaque `composition_id` returned in `compositions`:

```json
{
  "template_inputs": {
    "comp:notetype:<note-type-id>:template:<template-id>": {
      "input_schema": [{"key": "term", "label": "Word", "type": "text", "required": true}],
      "field_defs": [{"id": "<field-id>", "name": "Expression", "field_type": "text", "required": false, "position": 0}],
      "input_bindings": {"term": "<field-id>"},
      "warnings": []
    }
  }
}
```

`include_template_inputs` accepts trimmed/case-insensitive `1`, `true`, or `yes`. Without it, no `template_inputs` property is returned. Existing `include_counts=1` may be combined with this flag; counts remain distinct note counts per composition. Zero-card scopes return an empty dictionary.

The preparation data contains schema and attachment defaults, never note values or scheduler state. Owned and locally added notes use their NoteType's fields. Installed source compositions use the install's effective field schema, including added fields, renamed fields, disabled-field removal, and effective field types. Template sources use the same immutable release pins/canonical user copy as session issuance. Source/template/NoteType/application metadata is loaded in batches. A field ID is meaningful only within that composition's effective field list.

`warnings` are advisory `{input_key, code, required}` items: `INPUT_UNBOUND` or `INPUT_TYPE_MISMATCH`. A required input is a recommendation; it can remain unbound and render empty. API input keys stay unchanged when users rename fields or templates.

## Personal preset

`GET /api/decks/<deck_id>/study-template-preset` returns:

```json
{
  "schema_version": "study-template-preset.v2",
  "deck_id": 12,
  "selected_compositions": ["<composition-id>"],
  "input_bindings": {"<composition-id>": {"term": "<field-id>", "answer": null}},
  "ask_before_study": false,
  "stale_compositions": []
}
```

A missing row returns `selected_compositions: []`, `input_bindings: {}`, `ask_before_study: true`, `stale_compositions: []`. The row belongs to the signed-in user and local deck; it does not edit the shared attachment or publisher's template.

`PUT` to the same route replaces all three preference fields. Only `selected_compositions`, `input_bindings`, and `ask_before_study` are allowed. Omitted fields default to `[]`, `{}`, and `true`; this is not a PATCH. `selected_compositions` must be a unique string array of currently available composition IDs. Each binding-map key must be one of those selected compositions. Each input target must be `null`, `""` (normalized to `null`), or a stable field ID from the effective field schema; field and input types must match. Missing keys remain unbound. An empty map does not merge attachment defaults.

The endpoint accepts zero/multiple selections for compatibility, but the study frontend saves exactly one choice for a session. It must not interpret multiple saved choices as a request to mix templates in one session.

## Session opening and preference resolution

`POST /api/study/sessions` accepts the existing session negotiation fields plus an optional top-level `input_bindings` map for its single selected composition:

```json
{
  "scope": "deck",
  "scope_id": "12",
  "composition_id": "<composition-id>",
  "input_bindings": {"term": "<field-id>", "answer": null},
  "accepted_session_schema_versions": ["study-session.v4", "study-session.v3", "study-session.v2"],
  "accepted_batch_schema_versions": ["study-batch.v3"],
  "accepted_note_storage_profiles": ["note-mysql-float-text.v1"]
}
```

Success is HTTP 201 with the existing negotiated snapshot. Session authority/version/worker gates still apply. The request does not contain `remember` or change a scheduler preset. Remembering requires a separate explicit preset PUT. A transient override is validated even when no preset is saved and never modifies attachment bindings.

Choice resolution:

| Request/preset | Server behavior |
| --- | --- |
| Explicit `composition_id` | Uses that current composition; ignores saved choice and `ask_before_study` for selection. |
| Omitted choice, saved singleton, `ask_before_study: false` | Uses saved choice if still available; otherwise 409 `COMPOSITION_STALE`. |
| Omitted choice, no row / zero or multiple saved choices / `ask_before_study: true` | Uses the existing scope cardinality rule: zero -> 404 `NO_STUDY_CARDS`; one -> auto-select; many -> 409 `COMPOSITION_SELECTION_REQUIRED`. |

`ask_before_study` is a frontend prompting preference, not a server prohibition on opening the unambiguous singleton. The frontend should show preparation before a new session when this preference is true, including a deck with one composition. An already stored/restored active session uses its frozen material and bypasses preparation.

Binding resolution: explicit non-null map replaces all attachment defaults; `{}` means all declared inputs are empty. Omitted/`null` override uses the selected composition's saved personal map, if one exists; otherwise attachment defaults apply. A selected composition's saved map is used even when `ask_before_study` is true. An explicit form submission should send a complete map, using `null` for intentionally unbound inputs, so old saved targets cannot become a fallback.

## Errors and ownership

Responses use `{error, message}` with optional `field`/`details`; session-open template validation currently returns no `field` property. Authentication and existing CSRF checks apply. Deck preferences require a deck owned by this user or an install accessible to this user.

| HTTP | Code | Meaning |
| --- | --- | --- |
| 404 | `DECK_NOT_FOUND` | Preset deck absent or not accessible; another user's preset is never returned. |
| 400 | `VALIDATION_ERROR` | Unsupported preset properties, invalid list/boolean/map shape, or malformed input schema. |
| 400 | `INPUT_NOT_FOUND` | Binding key is not a declared input. |
| 400 | `FIELD_OUT_OF_SCOPE` | Target missing/disabled, belongs to another NoteType, or target is not a field ID string. |
| 400 | `INPUT_TYPE_MISMATCH` | Target's effective field type differs from the input type. |
| 403 | `COMPOSITION_OUT_OF_SCOPE` | Choice or saved preference is outside the current effective deck. |
| 400 | `INVALID_COMPOSITION_ID` | Explicit choice has an unsupported identity format. |
| 409 | `COMPOSITION_STALE` | Saved singleton unavailable, or explicit choice refers to a removed template. |
| 409 | `COMPOSITION_SELECTION_REQUIRED` | Scope has several choices and no applicable singleton selection. |
| 404 | `NO_STUDY_CARDS` | Scope has no available cards. |

If a previously saved target field was removed or changed type, session opening rejects that stale personal override with the same binding validation code. Reload preparation, clear/fix the affected target, and save/send the corrected map; do not substitute a field by name. Attachment defaults with unbound or removed targets render empty with advisory warnings.

## Frozen render metadata

`study-template.v1` optionally adds `binding_projection` only when aliases are needed:

```json
{
  "binding_projection": {
    "schema_version": "template-input-bindings.v1",
    "input_bindings": {"term": "<source-field-id>", "answer": null},
    "field_defs": [{"id": "<source-field-id>", "name": "Expression", "field_type": "text", "required": false, "position": 0}],
    "fingerprint": "sha256-<64 lowercase hex characters>"
  }
}
```

These field definitions snapshot the original effective source fields; the artifact's existing `field_defs` remain the projected renderer fields. Stale attachment targets are `null` in projection metadata. `fingerprint` hashes this projection object without its fingerprint property using the existing canonical JSON digest. Template version hashes include the projection metadata. Identity-bound and legacy artifacts omit the property and preserve their old shape and hashes.

Frontend session restore accepts old artifacts and checks optional projection schema, field IDs, declared inputs, and fingerprint. Content patches use the frozen ID/name map to update bound aliases and media helpers; unbound inputs/helpers stay empty. Template edits, source binding edits, or later preset writes cannot replace an existing session's template/field map. This metadata belongs to the programmer-facing contract; do not surface it in product UI. Wire schemas, composition identity, scheduler policy hashes, authority pins, rating actions, and queue algorithms retain their existing behavior.

## Validation and remaining frontend work

Focused coverage lives in `tests/test_study_template_presets.py`, `tests/test_study_template_application_sessions.py`, `tests/test_template_binding_service.py`, and the study session content-patch/restore tests. Gemini implementation phases and acceptance checks are in [GT-18](../task/template-features/GT-18_STUDY_TEMPLATE_PREPARATION.md). These APIs do not imply that the preparation screen, remember controls, or frontend integration are implemented.
