# Flama Security Assessment

Date: 2026-04-06  
Target: local instance at `http://127.0.0.1:4789`  
Assessment type: authenticated black-box + targeted code review  
Assessor context: local repository + local running app

## 1. Executive Summary

This assessment focused on the authenticated web surface of Flama, especially:

- authentication and session protection
- flashcard template preview and study rendering
- shared marketplace preview flows
- media upload validation and media serving
- bootstrap/seed credential handling

The review found that several previously reported issues have already been remediated in the current codebase, including missing CSRF protection on normal state-changing routes, login open redirect, hardcoded seed credentials, and missing login throttling.

However, the current build still contains one high-risk client-side code execution issue:

- stored XSS through flashcard template HTML/script handling in preview and study flows

Two additional security weaknesses remain relevant:

- CSRF protection currently accepts same-origin unsafe requests without a token, which weakens containment if any XSS exists
- SVG upload validation can be bypassed by moving dangerous content past the first 8 KB of the file

No credentials or sensitive password values are included in this document.

## 2. Scope and Methodology

### Scope

In scope:

- authenticated routes reachable from the local app
- flashcard note type/template CRUD and preview
- study rendering flow
- shared note type and shared deck preview flows
- note media upload endpoints
- support donation QR media serving path
- auth/bootstrap/security hardening added during the earlier remediation round

Out of scope:

- infrastructure outside the Flask app
- reverse proxy/CDN behavior
- third-party services
- production-only secrets and deployment posture

### Test Method

The assessment combined:

- dynamic probing with authenticated HTTP requests using an existing local admin/session account from `.env`
- crafted POST/PATCH payloads for HTML, markdown, and media upload cases
- route, validator, renderer, and frontend JavaScript review to confirm exploitability and impact

### Evidence Handling

- test artifacts were created only as short-lived local objects and then removed
- no secret values were written into the repository or this report
- claims below are marked either as:
  - `Observed dynamically`: confirmed against the running app
  - `Inferred from code`: strongly supported by code inspection but not fully re-enacted end-to-end in a browser session

## 3. Findings Summary

| ID | Severity | Status | Title |
| --- | --- | --- | --- |
| F-01 | High | Open | Stored XSS via flashcard template preview and study rendering |
| F-02 | Medium | Open | CSRF middleware allows unsafe same-origin requests without token |
| F-03 | Medium | Open | SVG upload validation bypass after 8 KB |
| F-04 | High | Remediated | Missing CSRF enforcement on state-changing routes |
| F-05 | Medium | Remediated | Open redirect through login `next` parameter |
| F-06 | Medium | Remediated | Hardcoded default credentials and weak bootstrap fallback |
| F-07 | Low-Medium | Remediated | Missing login brute-force throttling |

## 4. Detailed Findings

### F-01. Stored XSS via flashcard template preview and study rendering

Severity: High  
Status: Open

#### Description

Flama currently preserves inline `<script>` blocks inside flashcard template HTML in several preview and render flows. In the study UI, deferred inline scripts are later converted back into executable `<script>` nodes on the client.

This creates a stored XSS path for malicious template authors and can likely become cross-account XSS when shared/public templates or shared decks are previewed by other logged-in users.

#### Evidence

Observed dynamically:

1. A note type template was updated with:

```html
<div>{{Word}}</div><script>window.__fc_probe=1;document.body.setAttribute("data-probe","yes")</script>
```

2. `POST /api/note-types/<note_type_id>/templates/<template_id>/preview` returned the script block intact in `front_html`.

3. `GET /api/study/next?...` returned study payload content containing the deferred script marker and the raw JavaScript body.

Inferred from code:

- preview routes enable inline scripts:
  - `app/routes/flashcards/share.py`
  - `preview_template(...)` with `allow_inline_script=True`
  - `preview_shared_note_type_template(...)` with `allow_inline_script=True`
  - `preview_shared_deck_template(...)` with `allow_inline_script=True`
- renderer extracts and re-attaches inline scripts:
  - `app/services/flashcard_renderer.py`
- study client executes deferred scripts:
  - `templates/vocabulary_study.html`
- shared preview pages inject preview HTML into `iframe.srcdoc` while the iframe allows scripts:
  - `templates/flashcards/shared_note_type_detail.html`
  - `static/js/pages/shared_note_type_detail/main.js`
  - `templates/flashcards/shared_deck_detail.html`
  - `static/js/pages/shared_deck_detail.js`
  - local editor preview also behaves similarly in `templates/flashcards/note_type_detail.html`

#### Impact

Likely impact includes:

- self-XSS for the template author in local editor preview
- stored XSS when the template is rendered in study mode
- probable cross-account XSS if another logged-in user previews or studies a shared template/deck carrying malicious template HTML
- authenticated JavaScript execution inside the victim session

Because the app is session-based and many APIs are same-origin, this issue can likely be chained into account actions, content modification, and data access within the victim account.

#### Recommended Fix

Recommended priority: immediate.

Suggested remediation:

- disable inline script support in template rendering by default
- remove `allow_inline_script=True` from preview and study render paths unless there is a narrowly justified trusted-only use case
- remove client-side re-execution of deferred scripts from the study UI
- if preview iframes must remain, avoid `allow-scripts` for untrusted template content
- validate or reject `<script>` in template HTML at create/update time for normal users

#### Affected Code

- `app/routes/flashcards/share.py`
- `app/services/flashcard_renderer.py`
- `templates/vocabulary_study.html`
- `templates/flashcards/shared_note_type_detail.html`
- `static/js/pages/shared_note_type_detail/main.js`
- `templates/flashcards/shared_deck_detail.html`
- `static/js/pages/shared_deck_detail.js`
- `templates/flashcards/note_type_detail.html`

### F-02. CSRF middleware allows unsafe same-origin requests without token

Severity: Medium  
Status: Open

#### Description

The current CSRF middleware accepts an unsafe request if:

- it is same-origin according to `Origin` or `Referer`, even when no CSRF token is supplied

This design prevents some cross-site attacks, but it also weakens containment. If any XSS is present, the attacker does not need to read or submit a CSRF token at all.

#### Evidence

Observed dynamically:

- earlier in the remediation round, normal cross-site style POSTs without token were blocked correctly on routes such as `/vocabulary/decks/create`

Inferred from code:

- `app/csrf.py` returns success for unsafe same-origin requests without requiring a token

#### Impact

On its own, this is mainly a defense-in-depth weakness rather than a standalone exploit. Combined with F-01, it materially lowers the barrier for account-impacting malicious JavaScript.

#### Recommended Fix

- require a real CSRF token for all session-authenticated unsafe methods
- keep same-origin checks as an additional signal, not as a token substitute
- if some endpoints truly need tokenless behavior, exempt them explicitly and narrowly

#### Affected Code

- `app/csrf.py`

### F-03. SVG upload validation bypass after 8 KB

Severity: Medium  
Status: Open

#### Description

The SVG safety check only inspects the first 8,192 bytes of the uploaded file. A malicious SVG can therefore hide `<script>` or other dangerous constructs beyond that window and still be classified as a safe SVG.

#### Evidence

Observed dynamically:

1. A padded SVG payload was uploaded to `/api/notes/<note_id>/media`.
2. The SVG began with a normal `<svg ...>` header.
3. More than 9 KB of spaces were inserted before the `<script>` element.
4. The server accepted the upload and returned `201`.

Normal unsafe SVGs without padding were rejected, which confirms the bypass is specifically related to the limited scan window.

#### Current Mitigations

The normal note media proxy currently adds:

- `X-Content-Type-Options: nosniff`
- `Content-Security-Policy: default-src 'none'; sandbox`

That reduces exploitability for `/media/proxy/<asset_id>` itself.

However, this is still a validator bypass and should be fixed at the validation layer. It also creates risk if the same upload validation logic is reused for a route that serves SVG without the same CSP hardening.

One relevant code path is the public support-donation QR route, which serves uploaded images inline and currently only sets `nosniff`.

#### Impact

Current confirmed impact:

- upload filter bypass for SVG safety validation

Potential future impact:

- XSS or active content execution if the stored SVG is ever served through a less restricted route
- unsafe admin/content workflows if trusted viewers open the uploaded SVG in a context without strict CSP

#### Recommended Fix

- parse and inspect the full SVG document, not just the first 8 KB
- or disallow SVG entirely for untrusted uploads
- ensure every route serving uploaded SVG sets strict CSP or forces download
- review reuse of `validate_media_upload_request(...)` in non-note upload flows

#### Affected Code

- `app/validators/flashcard_input.py`
- `app/routes/flashcards/media.py`
- `app/routes/main.py`
- `app/services/support_donation_service.py`

### F-04. Missing CSRF enforcement on state-changing routes

Severity: High  
Status: Remediated

#### Previous Issue

Earlier in the assessment, state-changing requests such as deck creation accepted POSTs without CSRF token validation, and logout was reachable through `GET`.

#### Remediation Status

The current build includes:

- app-wide CSRF middleware
- client-side token propagation for form/fetch flows
- POST-based logout

#### Retest Result

Observed dynamically:

- POST to `/vocabulary/decks/create` without a valid CSRF token now returns `400`
- GET `/logout` no longer acts as a state-changing logout endpoint

### F-05. Open redirect through login `next` parameter

Severity: Medium  
Status: Remediated

#### Previous Issue

The login flow previously redirected directly to the user-controlled `next` parameter and accepted external destinations.

#### Remediation Status

The login redirect now resolves `next` through a safe local redirect helper.

#### Retest Result

Observed dynamically:

- `POST /login?next=https://example.com/phish` now redirects to `/dashboard` instead of the external host

### F-06. Hardcoded default credentials and weak bootstrap fallback

Severity: Medium  
Status: Remediated

#### Previous Issue

Seed/bootstrap logic previously contained hardcoded credentials and weak defaults that remained usable on the local instance.

#### Remediation Status

The current codebase now:

- removes hardcoded admin/test credentials from the repo
- requires environment-provided bootstrap credentials
- disables the legacy QA account on the local assessment instance
- rotates the local admin password to an environment-managed value

#### Retest Result

Observed dynamically and by code review:

- hardcoded credential strings used earlier in the assessment are no longer present in the repository
- bootstrap credential resolution is environment-only

### F-07. Missing login brute-force throttling

Severity: Low-Medium  
Status: Remediated

#### Previous Issue

Login attempts were previously accepted without throttling or temporary lockout.

#### Remediation Status

An in-memory login rate limiter has been added.

#### Retest Result

Observed dynamically earlier in the remediation round:

- repeated failed login attempts now trigger lockout behavior instead of unlimited retries

Residual note:

- the current limiter is in-memory only and should move to Redis or another shared backend if the app is deployed with multiple instances

## 5. Attack Paths Tested

### Input/POST Payload Tests

The following payload classes were tested against active routes:

- deck names containing HTML and event handlers
- richtext fields with `onerror`, `javascript:` URLs, inline SVG, and CSS URL payloads
- markdown fields with raw HTML, `javascript:` links, and data-URI image payloads
- template HTML with inline `<script>`

### Upload Tests

The following file classes were tested:

- ordinary unsafe SVG
- safe SVG
- fake PNG
- PNG with appended script content
- filename traversal attempts such as `../../evil.png`
- padded SVG with dangerous content beyond 8 KB

### Results

Successful protections observed:

- deck names are escaped in rendered pages
- richtext and markdown field payloads were sanitized correctly in the tested cases
- obvious unsafe SVG uploads were rejected
- fake PNG uploads were rejected
- filename traversal attempts were normalized safely
- `/media/proxy/<asset_id>` adds restrictive CSP and `nosniff`

Remaining exploitable surface:

- template script handling
- SVG validator scan-window bypass

## 6. Verification Performed

### Dynamic Verification

Confirmed on the running local app:

- template preview preserves inline `<script>`
- study payload includes deferred inline scripts
- padded malicious SVG is accepted by upload validation
- sanitized field-value attacks in richtext/markdown did not execute in the tested paths
- CSRF protections added earlier are active on standard state-changing routes
- login open redirect has been closed

### Automated Verification

Targeted regression checks were executed:

```bash
python -m unittest tests.test_auth_security tests.test_bootstrap_admin_credentials tests.test_app_startup
```

Result:

- `Ran 13 tests in 3.474s`
- `OK`

## 7. Risk Prioritization

Recommended remediation order:

1. Fix F-01 immediately by removing untrusted inline script support from template preview/study/shared preview flows.
2. Tighten F-02 so unsafe session requests require a CSRF token even when same-origin.
3. Fix F-03 by replacing partial SVG sniffing with full-document validation or by disallowing SVG for untrusted uploads.
4. Keep the earlier auth/bootstrap remediations under regression test coverage.

## 8. Limitations

- This assessment was performed against a local authenticated instance, not a production deployment.
- Shared-preview cross-account impact for F-01 is strongly supported by code review and page structure, but was not fully demonstrated with two separate browser users in this round.
- Infrastructure-layer controls such as reverse proxy headers, WAF, or CDN transformations were not evaluated.

## 9. Conclusion

The current Flama build is materially better than the earlier baseline because the most obvious auth/session weaknesses have already been addressed. That said, the template rendering pipeline still treats untrusted user-authored HTML as executable content, which is the most important remaining security issue in the app today.

If this issue is fixed cleanly and the CSRF/SVG follow-up items are completed, the overall security posture of the tested web surface will improve significantly.
