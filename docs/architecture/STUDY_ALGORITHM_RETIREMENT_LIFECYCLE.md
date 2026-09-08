# Study Algorithm executable and decoder retirement lifecycle

> Decision status: accepted for the P1-04 registry contract
>
> Runtime scope: Phase 0–3 compatibility; no schema or migration
>
> Current production identity: `legacy-anki/1.0.0`

## Decision

Every Algorithm is addressed by exact `(algorithm_key, algorithm_version)`.
Server and client registries publish lifecycle state and retained artifacts for
that exact identity. Resolution never chooses another version.

The four states are:

| State | New session | Existing unexpired lease | Accepted job | Historical inspection |
|---|---:|---:|---:|---:|
| `active` | yes; may be the default | yes | yes | when the history decoder is retained |
| `deprecated` | yes when explicitly pinned; must not become a new default | yes | yes | when the history decoder is retained |
| `lease-only` | no | yes | yes, if admitted before the issuance cutoff | when the history decoder is retained |
| `retired` | no | no | no | independent of executable support |

`deprecated` is a warning/drain stage. The actual issuance cutoff is the
source-controlled transition to `lease-only`. This keeps the registry
decision deterministic and avoids depending on application-server clocks.

Backend callers use `AlgorithmResolutionPurpose.NEW_SESSION`,
`EXISTING_LEASE`, or `ACCEPTED_JOB`. Frontend callers use the matching
string purpose. Unknown, disallowed and retired identities all fail with the
stable `ALGORITHM_UNAVAILABLE` family and include a diagnostic reason. The
reason is observability metadata, not a signal to retry with a newer version.

## Versioned artifact inventory

| Artifact | Current exact identity/schema | Runtime owner | Required through |
|---|---|---|---|
| Server executable | `legacy-anki/1.0.0` | `study_algorithm_registry.py` wrapping `anki_scheduler.py` | latest admitted lease/job plus safety gate |
| Client evaluator and previews | `legacy-anki/1.0.0` | `scheduler/algorithmRegistry.ts` and `legacyEngine.ts` | latest restorable unexpired lease |
| Card state decoder | `anki-card-state.v1` | backend `deserialize_card_state`; frontend persisted-session validation | latest admitted lease/job plus safety gate |
| Scheduler config decoder | `scheduler-config.v1` | backend `deserialize_deck_options`; frontend Algorithm contract validation | latest admitted lease/job plus safety gate |
| Session wire decoder | `study-session.v2` | backend session service; frontend `sessionRestore.ts` | the separately approved v2 compatibility window |
| Action/Trigger decoder | `review.*`, `scheduler.review.*`, contract `1` | backend action runtime; frontend interaction/restore adapters | latest lease using the contract; historical fields remain inspectable |
| Golden behavior vectors | `study-algorithm-golden-vectors.v1` for `legacy-anki/1.0.0` | Python and Vitest golden suites | permanently while the version is executable; preserve after retirement as evidence |
| Historical event fields | stored Algorithm/version plus provenance | `ReviewEvent` readers and audit | data retention policy; does not require executable replay |

The registry capability flags say whether state, config, event-history and
interaction decoders are retained. They do not replace the decoder's own schema
validation. Session wire support remains a separate P2-07 concern because one
wire version can carry more than one Algorithm version.

## Retention gate

The server lease TTL is currently 24 hours. An executable can move from
`lease-only` to `retired` only after all of these times have passed:

1. the maximum `expires_at` of every lease issued before the cutoff;
2. the processing deadline of every job accepted before the cutoff;
3. the end of the deployment rollback window;
4. an additional 24-hour safety margin after the latest of the first three.

The deployment rollback window for this runbook is seven calendar days from
the deploy that stops new issuance. If the async worker has no finite,
queryable processing deadline, retirement is blocked. A queue length of zero
alone is not evidence that all accepted jobs are resolved.

Browser IndexedDB records can outlive a server lease. They must be measured
before retirement to estimate recovery impact, but an expired local record does
not extend the executable replay promise. A valid unexpired local lease still
does. P2-03 owns quarantine behavior; P2-07 owns the legacy-v2 compatibility
window.

The 30-day session/detail retention clock serves support, audit and later
aggregation. It does not require an Algorithm executable or client evaluator to
remain runnable for 30 days. Historical readers use stored outcome/provenance
fields and retained event decoders without replaying the transition.

## Retirement procedure

1. Add the new exact version beside the old one on Python and TypeScript. Add
   new golden fixtures; never edit the old version's vectors.
2. Deploy both executables and verify server/client support introspection agrees.
3. Make only an `active` identity the default for newly opened sessions.
4. Mark the old identity `deprecated` for one full deploy cycle and monitor
   new-session issuance, restores, commits and accepted jobs by identity.
5. Mark it `lease-only`; record the issuance-cutoff timestamp, latest lease
   expiry, latest accepted-job processing deadline and rollback deadline.
6. After the retention gate, register it as `retired`, remove its executable
   and evaluator, and retain only explicitly declared decoders/evidence.
7. Verify new-session, restore, commit, delayed-job and history-read behavior.
   Store counts/timestamps with the task handoff.

The current default is checked as new-session eligible during Python module
initialization. A `lease-only` or `retired` default therefore fails startup
instead of silently issuing unusable sessions.

## Rollback

Restore the exact Python adapter, TypeScript evaluator and decoder artifacts
under the same key/version. Restore the prior lifecycle entry and redeploy both
sides. Do not rewrite persisted session, event, state-schema or config-schema
identities. A rollback to code that lacks a newly issued version is unsafe until
all leases/jobs for that version have drained.

## Integration wiring

The P1-04 boundaries are wired as follows:

- session creation resolves the default with `new-session` before reading or
  writing session state;
- open-session status (the server restore check) and synchronous commit resolve
  the pinned identity with `existing-lease`;
- the worker resolves the pinned identity with `accepted-job` before decoding
  or applying events and sends unavailable work to the DLQ;
- frontend snapshot validation resolves with `existing-lease`; P2-03 maps the
  stable unavailable family to quarantine;
- the architecture audit consumes lifecycle introspection and uses
  `existing_lease_allowed` to distinguish a valid `lease-only` session from
  a retired or unknown active session.

An actual future version retirement must attach deployment evidence for last
issuance, lease expiry, accepted-job deadline and rollback deadline. That
evidence is version-rollout data; `legacy-anki/1.0.0` remains active.
