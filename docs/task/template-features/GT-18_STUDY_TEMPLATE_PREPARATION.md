# GT-18 — Chọn template và ánh xạ trước phiên học

- Owner: Gemini (React UI/API adapter/tests); Codex owns backend and frozen renderer contracts.
- Status 2026-10-08: **GT-18A/B/C/D Completed / verified**; local Chrome + Flask preparation/remember/session restore passed. See [CT-R2](reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md).
- Required contract: [template-study-bindings-contract-2026-10-07.md](../../architecture/template-study-bindings-contract-2026-10-07.md).
- Run phases A -> B -> C -> D sequentially. Coordinate with GT-12/13 for shared `entities/card-template/index.ts` and `api/queryKeys.ts` ownership; each phase edits at most six listed files.

## Product behavior

A new study session uses one composition for its whole lease. Before opening it, let the user pick a template occurrence and map its declared inputs to effective NoteType fields by stable IDs. Inputs may be left empty, including required inputs; show an advisory explanation rather than blocking start. Never rewrite a template's tokens or modify an attachment while saving a personal mapping.

Get available choices with `GET /api/study/scopes/deck/<id>/compositions?include_template_inputs=1&include_counts=1`, and personal preferences with `GET /api/decks/<id>/study-template-preset`. Use the returned `template_inputs` fields for installed sources; do not fetch raw publisher fields or guess IDs from labels. Select dropdown candidates of the same field type. Missing/disabled/type-changed saved targets display as empty with a warning.

The prep form starts from the selected composition's saved mapping if a mapping entry exists, including `{}`; otherwise use its attachment defaults. Normalize every declared input to a field ID or `null`. Keep selection and bindings local until the user starts. If remember is selected, PUT exactly one selected composition and its mapping plus `ask_before_study`; then POST the session with that explicit choice and map. If remember is off, POST only; existing saved preferences remain unchanged. A failed preference PUT keeps the form open with a retryable error. Do not silently claim the choice was remembered.

Show the prep panel for a new lease when `ask_before_study` is true, even for a singleton. If false and exactly one current saved choice exists, open it with the saved mapping. Zero/multiple/stale saved choices must return to current choices; no multi-template session. Zero available compositions preserve the existing empty state. Restored active/pending sessions retain their current restore/receipt/lease flow and bypass prep; never overwrite a frozen snapshot with newly fetched preference data.

When opening a rollover/retry for the same chosen flow, carry the explicitly chosen bindings through the existing lease-opening path. Include bindings in open-request deduplication identity so two different maps cannot share one opening promise. Keep scheduler/commit/batch/authority semantics unchanged.

New UI strings:

| Purpose | Exact text |
| --- | --- |
| Heading | Chuẩn bị phiên học |
| Template choice | Template cho phiên này |
| Input field section | Ánh xạ dữ liệu |
| Empty candidate | Để trống |
| Remember checkbox | Ghi nhớ cho bộ thẻ này |
| Prompt preference | Luôn hỏi trước khi học |
| Optional input explanation | Input chưa ánh xạ sẽ hiển thị rỗng. |
| Stale target warning | Trường đã lưu không còn phù hợp. Hãy chọn lại hoặc để trống. |
| Start action | Bắt đầu học |
| Retry | Thử lại |

Use existing primitives, brand classes, and Vietnamese styling conventions. Preserve existing study toolbar, renderer, bottom controls, dialogs, DOM/classes, ratings, and empty/conflict states. No scheduler details, IDs, hashes, ABI labels, or authority terms in product UI.

## Phase A — Entity contract/API adapters

Allowed files (five):

1. `frontend/src/entities/card-template/model/studyTemplateTypes.ts` (new).
2. `frontend/src/entities/card-template/api/studyTemplateApi.ts` (new).
3. `frontend/src/entities/card-template/api/studyTemplateApi.test.ts` (new).
4. `frontend/src/entities/card-template/api/queryKeys.ts`.
5. `frontend/src/entities/card-template/index.ts`.

Add typed input schema, source fields, per-composition preparation entry, preset GET/PUT DTOs. Adapters use `apiRequest`/`apiJson` from `@/shared/api/client`, never `@/app` or another feature. Expose `fetchStudyTemplateInputs(deckId, signal?)`, `fetchStudyTemplatePreset(deckId, signal?)`, and `saveStudyTemplatePreset(deckId, payload)`. Use exact canonical URLs and existing transport error behavior. Do not add negotiation/scheduler fields to preset DTOs.

Test flag encoding, optional signal, GET/PUT payload distinctions, complete map including `null`, stable IDs, errors, and preservation of old `fetchDeckCardTypes` behavior. Existing entity exports must remain available. Run the modular runner on the new test file and `npm run typecheck` in `frontend`.

Prompt: [GT-18A.prompt.txt](GT-18A.prompt.txt).

## Phase B — Shared input-binding editor

Allowed files (three):

1. `frontend/src/entities/card-template/ui/TemplateInputBindingEditor.tsx` (new).
2. `frontend/src/entities/card-template/ui/TemplateInputBindingEditor.test.tsx` (new).
3. `frontend/src/entities/card-template/index.ts`.

Controlled editor props: `inputSchema`, `fieldDefs`, `value`, `onChange`, and optional `disabled`. Use phase A's entity types. Render each input's label/key, a same-type field dropdown by ID, and `Để trống` -> `null`. Show unbound required inputs and stale/type-mismatched targets as advisory. Never auto-bind by field name, mutate inputs, or block the start action. This shared editor can be reused by GT-13 attachment UI; personal save behavior remains a feature concern.

Test duplicate source labels with different IDs, renamed labels with same ID, stale target, mismatched type, required/unbound, clear-to-null, stable change payload, keyboard/select accessibility, disabled state, and input immutability. Run the modular runner on the new test file and typecheck.

Prompt: [GT-18B.prompt.txt](GT-18B.prompt.txt).

## Phase C — Study preparation hook and panel

Allowed files (four):

1. `frontend/src/features/study/hooks/useStudyTemplatePreparation.ts` (new).
2. `frontend/src/features/study/hooks/useStudyTemplatePreparation.test.tsx` (new).
3. `frontend/src/features/study/components/StudyTemplatePreparation.tsx` (new).
4. `frontend/src/features/study/components/StudyTemplatePreparation.test.tsx` (new).

Use phase A public entity API/types and phase B editor. Keep loading, choice, mapping, preference, save, and error logic in the hook; render it in the panel. Return/emit one immutable `{compositionId, inputBindings}` selection for phase D's session opener. Implement the product rules above without opening a lease yet. Preserve a user's input if a request fails or finishes after the selected deck changes; cancel/ignore stale fetches. Remember off skips PUT. Remember on saves one choice with the complete mapping and selected prompt preference. Prefill `{}` as empty, not as default fallback. Do not add a feature-to-feature import or duplicate backend validation logic that rejects advisory unbound inputs.

Test initial no-row preference, singleton/multiple choices, saved singleton, `{}` versus absent mapping, same-ID rename, overlay-added fields, stale/type-mismatched saved targets, save/retry errors, remember-off, and deck switch/cancel. Run both new suites via the modular runner and typecheck.

Prompt: [GT-18C.prompt.txt](GT-18C.prompt.txt).

## Phase D — Session/page integration

Allowed files (five):

1. `frontend/src/features/study/hooks/useStudySession.ts`.
2. `frontend/src/features/study/hooks/useStudySession.test.tsx`.
3. `frontend/src/features/study/pages/StudyPage.tsx`.
4. `frontend/src/features/study/pages/StudyPage.test.tsx`.
5. `frontend/src/features/study/api.ts`.

Integrate the preparation hook/panel into the existing no-active-lease branch. Keep `selectComposition(compositionId)` backward compatible while allowing an explicit field-ID map. `openSnapshot` sends `input_bindings` for a submitted prep selection and preserves all current accepted wire/batch/storage-profile negotiation fields. Its dedupe key covers the immutable submitted map. Use selected saved choice on `ask_before_study: false`, and carry transient bindings on next lease/retry for this flow. Do not modify the snapshot's binding projection, scheduler policy, composition identity, authority pins, or event payloads. A restored lease never goes through a fresh selection or preset PUT.

Tests must cover singleton prompt, multiple composition choice, saved auto-open, no-choice/zero stale cases, transient map sent with no PUT, remembered map saved before open, preference failure/retry, two binding maps not deduplicated together, restored/pending session bypass, rollover carrying mapping, stale lease/error behavior, and exact unchanged rating/commit wire. Keep all old tests enabled. Verify the existing study UI remains visually identical outside the new preparation branch.

Validation: modular runner with both integration suites, the phase A/B/C suites, and existing `contentPatchAdapter.test.ts`, `contentPatchAdapter.adversarial.test.ts`, `sessionRestore.test.ts`, `wireContract.test.ts`; then `npm run build`. Use a separate browser profile for any real browser check.

Prompt: [GT-18D.prompt.txt](GT-18D.prompt.txt).

## Common execution rules and reporting

Read `AGENTS.md`, `$flama-frontend-architecture`, and `$impeccable`. Each phase has the exact whitelist above; do not edit backend/models/migrations, renderer entity code, session restore/content patch/wire/scheduler files, build config, dependencies, or another phase. Do not commit/push, change the real DB, or use a personal browser profile. Run phases sequentially; read existing code and this contract before writing. If the API or an expected exported symbol differs, report the mismatch and leave dependent work pending rather than inventing a replacement API.

Run `.\.venv\Scripts\python.exe scripts/run_tests.py --file <exact frontend test paths> --frontend-only` from the repo root. For typecheck/build use `npm run typecheck` / `npm run build` in `frontend`. Report changed files, behavior, actual commands/results, the last 20 output lines, and remaining gaps. Mark a phase done only after its tests and typecheck pass; UI acceptance remains pending until phase D and visual verification complete.
