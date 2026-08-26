# Card Template Sandbox Renderer

## Threat Model

### Previous trust boundary
- `rendered_front_html` and `rendered_back_html` were injected into parent pages by:
  - `templates/vocabulary_study.html`
  - `templates/flashcards/study.html`
  - `templates/flashcards/note_type_detail.html`
  - `static/js/pages/shared_note_type_detail/main.js`
  - `static/js/pages/shared_deck_detail/main.js`
- User-authored template JS could therefore execute with the main app document, same-origin DOM access, session cookies, and any same-origin CSRF weaknesses.

### New trust boundary
- Untrusted card template HTML and JS execute only inside `iframe sandbox="allow-scripts"`.
- The iframe does not use `allow-same-origin`.
- Parent pages never re-execute template scripts in the main document.
- The only parent/child communication channel is a narrow `postMessage` bridge with:
  - instance id matching
  - `event.source === iframe.contentWindow`
  - strict action allowlisting
  - minimal payload validation

### What template JS can do
- Normal JavaScript logic on its own DOM.
- Read rendered DOM content and structured renderer context.
- Manipulate card-side elements.
- Register `FlamaCard.onReveal(...)`.
- Request height sync with `FlamaCard.notifyHeight()`.
- Request approved audio playback with `FlamaCard.playAudio(...)`.
- Use direct `<audio src="/media/proxy/...">` elements that survive sanitization.

### What template JS cannot do
- Access the parent DOM.
- Read app cookies or `localStorage`.
- Perform authenticated same-origin `fetch`/XHR with app privileges.
- Open forms, popups, or top-level navigation through sandbox privileges.
- Load arbitrary external scripts.
- Use arbitrary network endpoints because renderer CSP sets `connect-src 'none'`.

## Current Execution Map

### Execution points in React SPA
- Flashcard study: `frontend/src/features/study/renderer/` & `frontend/src/features/study/pages/`
- Note type template preview & editor: `frontend/src/features/note-types/`
- Shared deck preview: `frontend/src/features/marketplace/`
- Sandboxed iframe host asset: `static/js/card_renderer_host.js`

### Renderer data producers (Backend)
- Compiler & sanitizer: `app/services/flashcard_renderer.py`
- Canonical v1 flashcard API: `app/api/v1/flashcards/`
- Compatibility study routes: `app/routes/flashcards/study.py` and `app/routes/vocabulary.py`
- Content/session orchestration: `app/services/flashcard_content_service.py`, `app/services/study_service.py`, and `app/services/study_session_service.py`
- Media asset proxy: `/media/proxy/<asset_id>`

## Renderer Design

### Server-side contract
- `render_template_pair(...)` now returns:
  - `front_html`
  - `back_html`
  - `front_renderer_payload`
  - `back_renderer_payload`
- Each renderer payload includes:
  - rendered HTML
  - allowlisted media URLs
  - allowlisted audio URLs
  - allowlisted audio asset ids

### Sanitization model
- Richtext, markdown, and field content still use strict sanitization.
- Template-authored HTML uses a different sanitizer path:
  - inline `<script>` blocks are preserved only for sandbox rendering
  - external `src=` scripts are removed
  - inline event handlers are preserved only on final template HTML
  - media URLs remain restricted to `/media/proxy/<asset_id>`

### Parent host
- Implemented in `static/js/card_renderer_host.js`.
- Responsibilities:
  - generate a new renderer instance id for each iframe render
  - create `srcdoc` documents with strict CSP
  - set `sandbox="allow-scripts"`
  - validate renderer messages
  - clamp iframe height updates
  - allow only approved audio requests
  - refuse to translate sandbox-authored keyboard messages into parent-window events

### Renderer shell
- Built into the iframe `srcdoc`.
- Exposes:
  - `FlamaCard.playAudio(ref)`
  - `FlamaCard.notifyHeight()`
  - `FlamaCard.onReveal(callback)`
  - `FlamaCard.getConfig()`
  - `FlamaCard.getContext()`
- Also preserves legacy behavior by:
  - auto-applying `auto-split`
  - leaving direct local DOM/audio logic intact inside the iframe

### Bridge protocol
- Renderer to host:
  - `renderer_ready`
  - `resize_request`
  - `play_audio`
  - `pause_audio`
  - `log_error`
- Host to renderer:
  - `reveal`
  - `patch_content`
  - `audio_result`
  - `audio_event`

There is deliberately no generic `keydown_event` or progress-changing Action in this bridge. The 2026-08-27 study-runtime slice removed the former keyboard relay because Template code could synthesize the same message as a real key press. Study shortcuts continue to be owned by the React study host while focus is in the parent document. A replacement for shortcuts while focus is inside the iframe must use a reviewed trusted-gesture/capability design; it must not restore raw `KeyboardEvent` redispatch.

### Renderer CSP
- `default-src 'none'`
- `base-uri <configured media origin>`
- `form-action 'none'`
- `frame-ancestors 'none'`
- `connect-src 'none'`
- `font-src 'none'`
- `frame-src 'none'`
- `img-src <exact approved media proxy URLs>`
- `media-src <exact approved media proxy URLs>`
- `navigate-to 'none'`
- `object-src 'none'`
- `script-src 'unsafe-inline'`
- `style-src 'unsafe-inline'`
- `worker-src 'none'`
- `manifest-src 'none'`

## Security Tradeoffs

### Why scripts are preserved
- Product requires real JavaScript support for card templates.
- The security boundary is isolation plus bridge validation, not script stripping.

### Why direct `<audio>` is still allowed
- Existing card templates already use local audio elements and `element.play()`.
- Audio/media URLs remain constrained to `/media/proxy/...`.
- `FlamaCard.playAudio(...)` adds a safer allowlisted host path without breaking legacy cards.

### Why same-origin is not granted
- `allow-same-origin` would collapse the isolation boundary.
- Without it, template JS loses parent DOM access and authenticated same-origin fetch privileges.

## Implementation status

1. [x] Preserve Template JS in renderer output, but only for sandbox consumption.
2. [x] Add renderer metadata so the host can validate audio requests.
3. [x] Introduce a shared sandbox iframe host layer.
4. [x] Use the shared renderer from React study, preview, and marketplace flows.
5. [x] Remove the forgeable sandbox-to-parent keyboard relay.
6. [ ] Design a trusted keyboard-command path for iframe focus without granting Template code a progress capability.
7. [ ] Expand browser-level regression coverage for:
   - script-preserving render output
   - renderer payload metadata
   - study/preview payload contract
   - parent-focus and iframe-focus shortcut behavior
   - rejection of sandbox-authored progress Actions

## Affected Files

- `app/services/flashcard_renderer.py`
- `app/routes/flashcards/study.py`
- `app/services/study_card_editor_service.py`
- `app/routes/vocabulary.py`
- `frontend/src/features/study/components/CardRendererFrame.tsx`
- `frontend/src/features/study/components/CardDisplay.tsx`
- `frontend/src/features/study/renderer/clientRenderer.ts`
- `frontend/src/features/note-types/components/NoteTypeLivePreview.tsx`
- `frontend/src/features/marketplace/pages/SharedNoteTypeDetailPage.tsx`
- `frontend/src/features/marketplace/pages/SharedDeckDetailPage.tsx`
- `static/js/card_renderer_host.js`
- `tests/test_flashcard_renderer.py`
- `tests/test_rest_only_runtime.py`
- `frontend/src/features/study/components/CardRendererHost.test.ts`
- `frontend/src/features/study/components/CardRendererFrame.test.tsx`

## Remaining Limitations

- Passive media loads to approved `/media/proxy/...` URLs are still allowed inside the sandbox because that is required for card images/audio.
- `FlamaCard.playAudio(...)` is limited to approved proxy asset refs. It does not allow arbitrary URLs.
- Browser autoplay policy still applies. Host-triggered playback is best-effort and legacy local `<audio>` controls remain supported for compatibility.
- This patch does not rely on SVG validation as a renderer boundary. SVG hardening remains defense in depth only.
- Keyboard shortcuts are not forwarded while focus is inside the sandbox. This is the accepted secure interim behavior, not the final Phase 2 UX.
