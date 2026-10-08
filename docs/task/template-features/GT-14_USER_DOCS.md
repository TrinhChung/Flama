# GT-14 — User guide after accepted template UI

- Status 2026-10-08: **Completed** by Codex after UI tests and isolated Chrome smoke; guide and `study/template-library-bindings` article match actual controls. See [CT-R2](reviews/CT-R2_TEMPLATE_UI_COMPLETION_2026-10-08.md).
- Ready after GT-10B/11/12/13/18 UI review and isolated-browser smoke. Do not document a button or screen before it exists.

## 1. Allowed files

| File | Change |
|---|---|
| `docs/guides/NOTE_TYPE_TEMPLATE_GUIDE.md` | Add sections for shared templates, version history, received copies, field bindings and preparation. Preserve existing content. |
| `frontend/src/features/guide/guideData.ts` | Add one article with slug `template-library-bindings` under the existing `study` group. Preserve other articles and follow existing types. |

## 2. Confirmed behavior to explain

1. One independent template can be attached to multiple owned NoteTypes, including the user's received market copy. Binding uses stable FieldDef IDs, so field rename does not require rewriting HTML.
2. Required/unbound inputs warn; unbound inputs render empty. One field can supply multiple compatible inputs. A target of another NoteType or wrong type is rejected.
3. Actual content/schema changes append immutable history; rename/no-op does not. Explicit restore creates a new version and keeps cards/progress.
4. A received template belongs to the user/source pair across installs. Editing it leaves the author and other learners untouched. Manual/auto update and conflict choices use the subscription. Reset receives the currently published release while retaining copy identity and history.
5. Author auto publish and receiver auto update default off. Published versions and existing sessions are frozen. The user can reuse an entitled paid-deck template in other owned NoteTypes, but cannot republish its marketplace lineage.
6. Archive hides a definition and prevents a new attachment; existing uses continue. Retire removes an occurrence from study discovery and retains cards/progress. Archiving does not prevent saving existing template content, and skips standalone auto publication.
7. Preparation selects one composition and maps fields for the next session. Remembering uses a separate explicit preference write. An already active/restored session continues with its frozen binding.
8. Standalone template marketplace catalog and list-of-fields inputs remain outside this release. Describe implemented UI only; copy exact accepted button/menu names from GT specs and the final screen.

## 3. Reviewer gate before assignment

Record the implemented routes, actual menu/button strings, accepted phase IDs and browser result in the assignment. The article slug/group are chosen above; no backend approval is needed. This gate remains open because the new UI has not yet been implemented by Gemini.

## 4. Verification

Use the narrow existing guide test files discovered with `rg --files frontend/src/features/guide`, followed by frontend typecheck/lint. If the slice has no tests, do not pass a directory to the modular runner (it can select a broader fallback). Check links and compare guide names with actual UI. Run `git diff --check` and report changed files and real command output. No dependency changes, commits or unrelated edits.
