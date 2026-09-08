# ADR: Trusted keyboard boundary for Study renderer

> Date: 2026-09-07
>
> Status: Accepted
>
> Decision owner: Study frontend/security
>
> Task: [P2-05](../task/decoupling/completed/P2-05_TRUSTED_KEYBOARD_UX.md)

## Context

Card Template HTML and JavaScript run in an opaque-origin iframe with `sandbox="allow-scripts"`. Template code can synthesize DOM events and `postMessage` payloads inside that realm. The parent React Study page owns reveal, ReviewAction, undo and progress mutation.

The renderer bridge accepts presentation/media operations. It deliberately has no `keydown_event`, `host_command`, raw rating or semantic ReviewAction message. Instance ID and `event.source` bind a message to the current iframe, but they do not prove a physical user gesture because code in that iframe can send the same message.

## Decision

Study shortcuts are handled only by the trusted parent document. When focus is inside the untrusted renderer iframe, review/reveal/undo shortcuts are unavailable. We do not add an iframe-to-parent keyboard bridge in Phase 2.

The parent maps a trusted key event to one semantic `ReviewAction`. The reusable controls use the same semantic callback. The session boundary converts that action to the current four-rating scheduler adapter. Local mutation ownership prevents repeated/same-tick events from appending the same action twice.

This limitation is intentional product behavior. Users can click/tap the parent controls after leaving iframe focus. Supporting shortcuts inside rich Template content would require a browser-enforced realm that Template code cannot execute in; no such separate trusted input surface exists in the current renderer.

## Threat model

| Threat | Boundary/result |
|---|---|
| Template sends `host_command`, `keydown_event`, rating or ReviewAction | Renderer host does not dispatch these actions; no progress capability is exposed. |
| Template reuses instance ID or sends from the correct `contentWindow` | Identity proves frame origin only, not user intent; message remains rejected. |
| Template claims `isTrusted` or sends a nonce from bootstrap/DOM | Child-controlled claims/secrets are not accepted as trust proof. |
| Template synthesizes keyboard events | Events remain in the sandbox realm and are never redispatched into the parent. |
| Template monkey-patches its own event APIs | It gains no parent action channel. |
| Parent focus is in input/textarea/select/contenteditable or IME composition | Parent shortcut handler ignores the event. |
| Key repeat or same-tick duplicate reaches a mutation callback | Frontend session owner-token guard permits at most one mutation owner. |
| Unrelated window/channel/instance sends a renderer message | Host message validation rejects it before handling allowlisted media actions. |

## Alternatives

### Expose a nonce or iframe capability

Rejected. Any value visible to Template JavaScript authorizes synthesized messages as readily as physical input.

### Trust `event.source`, instance ID or child-supplied `isTrusted`

Rejected. These identify the active iframe/message shape, not the provenance of a user gesture.

### Relay raw keyboard/rating/action messages

Rejected. This restores a direct progress-affecting capability to untrusted Template code.

### Separate browser-enforced trusted overlay inside the renderer area

Deferred. A parent-owned overlay could be evaluated as a future UI design, but it must remain outside the iframe realm and preserve accessibility, focus and Template interaction behavior. It is not required to close Phase 2.

## Acceptance matrix

| Case | Expected behavior |
|---|---|
| Parent body focus, Space/Enter | Reveal, or semantic Good action after reveal. |
| Parent body focus, 1–4 | Exactly one matching semantic action after reveal. |
| Parent input/textarea/select/contenteditable | No Study shortcut. |
| Parent IME composition | No Study shortcut. |
| Parent repeated keydown | Mutation mutex rejects overlapping action; no duplicate event. |
| Renderer iframe focus | No parent Study shortcut bridge. |
| Forged renderer `keydown_event`/`host_command` | No parent event/action/progress write. |
| Unrelated window/channel/instance | No parent action and no unauthorized media operation. |

Evidence is provided by `StudyPage` keyboard tests, `CardRendererHost` forged-message tests and the P2-02 same-tick mutation matrix. Real-browser verification must use an isolated profile as required by `AGENTS.md`.

## Real-browser verification — 2026-09-07

Playwright CLI ran the bounded keyboard harness in the named isolated session
`flama-p205`; it did not attach to the user's normal Chrome profile. The local
harness is retained under ignored test output at
`output/playwright/p2-05-keyboard-harness.html`, with a screenshot at
`.playwright-cli/page-2026-09-07T12-30-11-930Z.png`.

Observed results:

- parent button focused, key `3`: parent keydown count changed from `0` to `1`;
- iframe control focused, key `3`: parent count remained `1`, while the iframe
  recorded its own trusted key event;
- forged renderer `host_command`: parent keydown and host-command counters both
  remained `0` after reload;
- console contained only the harness's expected CSP-meta warnings and a missing
  favicon; no application/runtime exception occurred.

The focused automated matrix also covers parent editable targets, IME
composition, repeated keydown and the host's rejection of forged
`host_command`/`keydown_event` messages.

## Consequences and rollback

The security boundary stays small and auditable. Keyboard parity is lower while focus remains inside Template content. No wire, storage, renderer sandbox or CSS change is required.

Rollback of any future keyboard experiment returns to this no-bridge behavior. It must never restore the former sandbox-authored `host_command` path.
