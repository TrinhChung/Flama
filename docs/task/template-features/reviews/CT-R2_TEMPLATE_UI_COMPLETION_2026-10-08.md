# CT-R2: Template UI completion — 2026-10-08

The remaining accepted template tasks are implemented in the workspace on `refactor/frontend-fsd-renderer-boundary`. GT-12A from Gemini was reviewed and reused; GT-10B, GT-12B/C/D/E, GT-13A/B/C/D, GT-11A/B/C, GT-18A/B/C/D and GT-14 are now complete. Codex has not committed or pushed these UI changes. Concurrent SEO/favicon changes are outside this report.

This report supersedes the frontend-pending handoff in [CT-04/08](CT-04_CT-08_BACKEND_HANDOFF_2026-10-08.md). The [tracker](../README.md) and current library/study contracts remain the entry points. Standalone template marketplace catalog N5 and list-of-fields input N6 remain outside accepted scope.

## Completed behavior

| Task | Result |
|---|---|
| GT-10B | Shared history sheet for the NoteType editor and library; version details, source diff, stale-head handling and explicit restore that replaces the draft |
| GT-12A | Reviewed existing library types/API/keys against the actual contract; retained A2 history API coverage |
| GT-12B/C/D/E | Search/group/category library, creation, input schema validation, draft editor with debounced safe preview, ACTIVE usage, archive/unarchive, protected routes and sidebar |
| GT-13A/B/C/D | Stable FieldDef ID suggestions and type checks, advisory unbound inputs, attachment wizard, NoteType mapping edits, retire and reactivate without replacing the application |
| GT-11A/B/C | Distribution entity API, installed-deck template entry, author publication controls, recipient subscription/update/diff/conflict choices and reset to the applied published release |
| GT-18A/B/C/D | Preparation and preset API, optional remembered choices, preference write before lease opening, transient binding submission, restored-session bypass and rollover mapping retention |
| GT-14 | Repository guide sections 8–11 and in-app article `/guide/study/template-library-bindings` match the final UI |

The new features live in `features/template-library`, `features/template-versions`, `features/template-distribution`, study preparation components/hooks and `entities/card-template`. App routes, sidebar, NoteType/Study pages and installed-deck entry compose their public exports. Existing renderer, scheduler, lease wire contracts and source-note overlay semantics were preserved.

## Defects fixed during implementation and review

- **Next submitted the attachment form in Chrome.** React reused the button when the next step changed it from `button` to `submit`; the same native activation could send a POST immediately. The wizard now prevents the initial activation and uses separate keyed buttons. A native cancelable-click regression and real-browser request counting verify zero POSTs for Next and one for Attach.
- **Restore could retain a dirty draft or apply an obsolete response.** Explicit restore/source replacement now updates editor state directly, reloads full schema/metadata, locks editing until replacement finishes and checks template identity/generation. Background refetches continue to preserve unrelated dirty edits and their original expected head.
- **Subscription toggles could erase unsaved edits without changing source.** Draft replacement now occurs only when the returned local version changed. Tests cover disabling inheritance and unchanged versions.
- **Legacy install listing could hide usable received templates.** The legacy notice coexists with returned items; only an empty result uses the empty state.
- **Archived templates had no route back from the default library.** The “Hiện mẫu lưu trữ” filter exposes archived entries so their detail page can unarchive them. The default query still excludes them.
- **Legal input keys could resolve inherited object properties.** Sample values and mapping checks use own-property semantics, including `__proto__`, `constructor` and `toString`.
- **An unstyled preview was hard to read in dark mode.** The library preview uses a white canvas beneath the sandboxed card, matching its default black text. Template HTML/CSS and existing preview/renderer behavior were not rewritten. Chrome verifies the sample text inside the iframe in dark mode.
- **Preparation displayed an internal deck ID as its title.** The page passes the resolved deck name to the new preparation view.

Focused coverage also checks API encoding/signals, stale-write conflicts, missing/foreign/type-mismatched binding targets, duplicate-submit guards, schema/sample cleanup, opt-in persistence failures, restored leases and frozen content-patch compatibility.

## Validation

Commands use `.\.venv\Scripts\python.exe` on Windows. Logs and browser artifacts are under ignored `output/playwright/`; they are local evidence rather than checked-in test fixtures.

| Check | Result |
|---|---|
| `scripts/run_tests.py --module templates --backend-only` | PASS: 197 tests, 17 files |
| `$env:VITEST_MAX_WORKERS = '2'; scripts/run_tests.py --module templates --frontend-only` | PASS: 437 tests, 35 files; 55.47s |
| Final library filter, StudyPage and DeckCardTypesDialog focused run | PASS: 49 tests, 3 files |
| Modular runner/catalog tests | PASS: 27 tests, 2 files |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run lint` | PASS, zero errors; existing warnings in other modules remain |
| `npm --prefix frontend run build:ci` | PASS, production bundle rebuilt after the preview adjustment |
| Chrome functional flows against actual Flask APIs | PASS: create/save/publish/history/restore/attach/archive/unarchive, recipient conflict/update/reset, preparation/remember/session restore |
| Chrome application management | PASS: clear binding, retire/reactivate the same application ID, unchanged template source/head |
| Chrome layout/theme matrix | PASS: 28 checks, 7 screens × desktop/mobile × light/dark; no horizontal overflow |
| Chrome preview sample | PASS: supplied sample rendered inside the iframe; readable canvas in dark mode |
| Documentation links/encoding and `git diff --check` | PASS: 10 UTF-8 documents, 34 local links; no whitespace errors |

The layout matrix covers library, detail, history, wizard, recipient distribution, NoteType applications and study preparation at 1440×1000 and 375×812. The guide route was opened and its article heading verified. The NoteType editor's existing DOM/classes were checked against the baseline with generated Radix IDs normalized; focused editor/draft regression tests remain enabled.

The default high-parallelism final frontend run hit the existing five-second timeout in the architecture AST scan; its focused rerun passed. The first overloaded run also timed out the new shell test, producing cascading act/navigation errors; the subsequent module run passed that shell test. The final entire template module passed with the process-local `VITEST_MAX_WORKERS=2` setting. Neither assertions nor timeouts were relaxed, and no permanent runner configuration changed.

## Environment and limits

Chrome used a separate profile at `%LOCALAPPDATA%/Temp/flama-template-review-chrome`. Functional writes targeted a disposable SQLite database through a temporary Flask app on `127.0.0.1:4798`; the normal local app/database and personal Chrome profile were not used. The review browser session and temporary server were closed after validation. MySQL migration/runtime evidence belongs to the earlier linked backend report; this UI completion did not rerun or change schema migrations.

Existing renderer CSP console diagnostics about meta `frame-ancestors` and `navigate-to` remain; the CSP was not weakened. The local `impeccable` skill named by repository guidance was unavailable, so the UI reused the existing primitives and received the browser checks above. This is local acceptance, with no production deployment or external PR comment.
