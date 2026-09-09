# Mixed-NoteType Study Scope Policy

> Status: Accepted and implemented
>
> Decision date: 2026-09-09
>
> Scope: Phase 3 compatibility runtime; no schema change

## Context and evidence

A Deck is an entry scope, not a universal NoteType or composition owner. The read-only production report from 2026-08-24 found one recursive Deck scope spanning two NoteTypes even though no individual Deck row was directly mixed. The authoritative SELECT-only P0-03 bundle from 2026-08-29 records 9 NoteTypes, including 7 with one Template and 2 with multiple Templates, plus 3 logical installs exposing 39 source Cards and zero recorded overlay ambiguity. That bundle does not contain a refreshed recursive mixed-scope category, so the earlier mixed-scope count is historical evidence rather than a current signed count.

Code inspection also showed that the old discovery path considered owned Notes and could advertise a deck-level Template without an eligible Card, while session opening applied the client filter only after the card limit. The React client opened a session before learner selection and offered an in-session “all” filter.

## Decision

The effective scope is resolved first. Every composition backed by at least one eligible Card is returned on one pre-session screen, grouped by NoteType. The grouping is presentational only: the learner selects exactly one composition, never a NoteType-wide or “all compositions” union.

The selected progress-subject set is the set of existing Cards returned by applying that one composition predicate to the authorized effective scope. Progress remains learner-specific `CardProgress` for those Cards; grouping and overlay presentation do not create a second subject identity.

Cardinality has one deterministic outcome:

| Eligible compositions | Outcome |
|---|---|
| 0 | Return `cardinality: zero`; show an empty/recoverable state; do not create a session. |
| 1 | Auto-resolve the sole option, but send its explicit `composition_id` when opening the session. |
| 2 or more | Return `cardinality: many`; wait for explicit learner selection; do not create a session beforehand. |

An old client that omits selection receives the same policy. Omission succeeds only when the effective scope contains exactly one eligible composition. An ambiguous omission fails with `COMPOSITION_SELECTION_REQUIRED`; the server does not silently choose the default, first item, first NoteType, or first Deck.

## API contract

`GET /api/study/scopes/{scope_type}/{scope_id}/compositions` returns `study-scope-compositions.v2`:

- `scope_type`, `scope_id`;
- `cardinality`: `zero`, `one`, or `many`;
- `default_composition_id`: the sole ID only when cardinality is `one`, otherwise `null`;
- `groups[]`: `note_type_id`, `note_type_name`, and exact `compositions[]`;
- a flat `compositions[]` compatibility list containing the same IDs.

Groups sort by normalized NoteType name and stable NoteType ID. Compositions sort by Template position and Template ID, with context and composition ID as deterministic tie-breakers. Names and sort positions never authorize a selection.

`POST /api/study/sessions` accepts canonical `composition_id`. Legacy `composition_ids` is accepted only as a one-element compatibility shape. Canonical and legacy fields together fail with `COMPOSITION_SELECTION_CONFLICT`; a legacy list with cardinality other than one fails with `COMPOSITION_CARDINALITY_INVALID`.

Selection errors are fail-closed:

- `INVALID_COMPOSITION_ID`: malformed identifier;
- `COMPOSITION_SELECTION_REQUIRED`: ambiguous omission;
- `COMPOSITION_STALE`: the referenced Template no longer exists;
- `COMPOSITION_OUT_OF_SCOPE`: a syntactically valid existing composition is not in the authorized effective scope;
- `NO_STUDY_CARDS`: no eligible Card exists for the scope or selection.

No session row is created for these outcomes.

## Overlay rule

Discovery and opening use the same `CloneDeckScope` and effective Card query. Installed source and learner-local contexts have installation-qualified identities:

```text
comp:install:{install_id}:source:notetype:{note_type_id}:template:{template_id}
comp:install:{install_id}:local:notetype:{note_type_id}:template:{template_id}
```

The qualifier prevents one physical source Card reused through different logical installs from being treated as one global application. It does not copy the source Note/Card or create another progress authority.

## Alternatives rejected

1. Select NoteType first, then composition: deterministic but adds a step without improving authorization or queue semantics.
2. Require a narrower Deck scope: avoids mixed scopes by restricting existing recursive-study behavior and makes valid child content unexpectedly unavailable.
3. Choose the default or first composition: order-dependent and unsafe for mixed NoteTypes, duplicate Template positions, old clients, and overlays.
4. Open all Cards and filter in React: creates a session whose durable queue differs from what the learner sees and biases the server-side limit.

## Consequences and rollback

The active Study screen keeps its existing layout. New UI exists only in the pre-session launch state. Once opened, the selected server queue is authoritative and the client cannot switch or apply an “all” filter inside that lease.

Rollback may disable admission to the new launch flow, but readers for already-issued frozen sessions and installation-qualified identities must remain until their compatibility window expires.

## Verification

- Backend selection, cardinality, stale/out-of-scope, empty-scope, and query-before-limit tests in `tests/test_study_session_api.py`.
- Deterministic mixed-NoteType discovery in `tests/test_study_composition_exit_gate.py` and `tests/test_study_composition_service.py`.
- Pre-open no-POST and exact-selection tests in `frontend/src/features/study/hooks/useStudySession.test.tsx`.
- Real publish/install overlay coverage in `tests/test_study_behavior_acceptance_baseline.py`.
