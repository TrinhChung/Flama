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
- Study & preview endpoints: `app/api/flashcards/` & `app/api/learning/study.py`
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
  - `log_error`
- Host to renderer:
  - `reveal`

### Renderer CSP
- `default-src 'none'`
- `base-uri 'none'`
- `form-action 'none'`
- `frame-ancestors 'none'`
- `connect-src 'none'`
- `font-src 'none'`
- `frame-src 'none'`
- `img-src data: /media/proxy/`
- `media-src blob: /media/proxy/`
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

## Concrete Patch Plan

1. Preserve template JS in renderer output, but only for sandbox consumption.
2. Add renderer metadata so the host can validate audio requests.
3. Introduce a shared sandbox iframe host layer.
4. Replace direct parent-document injection in preview/study/shared flows.
5. Add regression tests for:
   - script-preserving render output
   - renderer payload metadata
   - study/preview payload contract
   - vocabulary study page iframe contract

## Affected Files

- `app/services/flashcard_renderer.py`
- `app/routes/flashcards/study.py`
- `app/services/study_card_editor_service.py`
- `app/repositories/vocabulary_repository.py`
- `app/presenters/vocabulary_presenter.py`
- `app/routes/vocabulary.py`
- `templates/flashcards/note_type_detail.html`
- `templates/flashcards/study.html`
- `templates/flashcards/shared_note_type_detail.html`
- `templates/flashcards/shared_deck_detail.html`
- `templates/vocabulary_study.html`
- `static/js/card_renderer_host.js`
- `static/js/pages/shared_note_type_detail/main.js`
- `static/js/pages/shared_deck_detail/main.js`
- `tests/test_flashcard_renderer.py`
- `tests/test_flashcard_api_integration.py`

## Remaining Limitations

- Passive media loads to approved `/media/proxy/...` URLs are still allowed inside the sandbox because that is required for card images/audio.
- `FlamaCard.playAudio(...)` is limited to approved proxy asset refs. It does not allow arbitrary URLs.
- Browser autoplay policy still applies. Host-triggered playback is best-effort and legacy local `<audio>` controls remain supported for compatibility.
- This patch does not rely on SVG validation as a renderer boundary. SVG hardening remains defense in depth only.
