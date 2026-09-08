# ADR: Study wire v3 dual-reader and rollout contract

> Date: 2026-09-08
>
> Status: Accepted for implementation
>
> Task: [P2-07](../task/decoupling/completed/P2-07_WIRE_V3_LEGACY_V2_POLICY.md)

## Decision

Study snapshot, commit and batch envelopes have independent version names:

| Pinned session | Synchronous commit | Async batch | New semantic identity |
|---|---|---|---|
| `study-session.v2` | `study-commit.v1` | `study-batch.v1` | optional as one complete legacy group |
| `study-session.v3` | `study-commit.v2` | `study-batch.v2` | required and exact |

The `StudySession.wire_schema_version` selected at open time is authoritative.
Commit and worker paths choose their decoder from that stored value; client
fields never select or upgrade the decoder. Unknown versions fail closed.

New-session negotiation is explicit. A capable client sends
`accepted_session_schema_versions` in preference order. The server issues v3
only when `STUDY_WIRE_V3_ENABLED` is true and the client advertises v3. An old
client that does not advertise capability receives v2. Turning the flag off
stops new v3 issuance but does not remove the v3 reader.

## Event contracts

Both versions retain UUID event identity, contiguous sequence, card membership,
policy identity, bounded duration and lease-bounded monotonic scheduler offset.

A v2 event may omit all of `action_key`, `trigger_key` and
`trigger_contract_version`; the compatibility decoder derives the canonical
built-in identity from the rating. If any member is present, all three must be
present and exact. V3-only fields in a v2 envelope are rejected instead of
being treated as an implicit upgrade.

A v3 event requires this exact identity:

```text
action_key
action_contract_version
trigger_key
trigger_contract_version
algorithm_key
algorithm_version
config_schema_version
config_hash
study_session_id
event_id
sequence
```

Action and Trigger form one discriminated four-action contract. Algorithm,
config, session and policy values must equal the server-pinned session/card
material. The built-in Trigger runtime verifies the exact Trigger version and
the Algorithm registry resolves the pinned executable for an existing lease or
accepted job. There is no fallback to a latest version.

## Rollout and rollback

1. Deploy server, worker and new client with v2/v3 readers while v3 issuance is
   disabled.
2. Verify cross-version tests and metadata-only active-session counts.
3. Enable `STUDY_WIRE_V3_ENABLED` for capable clients. Old clients continue to
   negotiate v2.
4. During rollback, disable new v3 issuance but deploy only a target that still
   contains the v3 reader and exact Algorithm/Trigger artifacts.
5. Retire v2 creation only after the latest v2 lease expiry, every accepted v2
   job's finite processing deadline, the seven-day rollback window and the
   additional 24-hour P1-04 safety margin have all passed.

The async admission flag is independently false by default. If async batches
are re-enabled, both batch decoders, owner-safe queue locking, a production
consumer, schema migration and durable receipt reconciliation are prerequisites.
A 202 response means accepted, never completed.

## Telemetry and privacy

The architecture audit reports counts grouped by stored session wire version,
status and pinned Algorithm version, plus oldest/latest expiry timestamps. It
may report accepted batch/job counts when the queue is enabled. It must not log
rating sequences, card content, rendered HTML or answer payloads.

Unsupported wire/Trigger/Algorithm events use typed error/quarantine families.
These counters are metadata only and must not include raw quarantined event
content.

## Compatibility matrix

| Scenario | Required result |
|---|---|
| Old client → dual-reader server | Receives v2; valid lease opens/restores/commits. |
| New client, flag off | Negotiates v2 without blind v3 retry. |
| New client, flag on | Receives v3 and sends `study-commit.v2` / `study-batch.v2`, paired with that session. |
| New client restores valid IndexedDB v2 | V2 decoder preserves IDs/sequences; no heuristic rewrite to v3. |
| Partial v2 semantic metadata | Reject/quarantine before hydration or mutation. |
| Missing/mismatched v3 identity | Reject/quarantine before Trigger dispatch. |
| Unknown wire/Trigger/Algorithm | Stable typed failure; no fallback. |
| Expired v2 lease | History remains inspectable; execution is refused. |
| Rollback with live v3 leases | Stop issuance, retain v3 reader and exact artifacts until drain gates pass. |

## No schema expansion

V3 uses the existing session, policy, composition and event material. This ADR
does not add learner/Note progress state or a database column. Any async batch
table migration remains a separate deployment prerequisite, not P2-07 scope.
