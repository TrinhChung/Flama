# ADR: Built-in Trigger Runtime contract

> Date: 2026-09-07
>
> Status: Accepted
>
> Task: [P2-06](../task/decoupling/completed/P2-06_TRIGGER_RUNTIME_DESIGN.md)

## Decision

Phase 2 uses a minimal, exact-version dispatcher for the four built-in review Triggers. It does not create a generic plugin or Template automation engine.

The existing `study_action_runtime.py` is the boundary. `dispatch_builtin_review_trigger` accepts an already resolved semantic Action, an exact Trigger key/version and an exact Algorithm key/version. It verifies the allowlisted Action/Trigger pair and invokes the exact Algorithm adapter. The function calculates a transition only. The application service or Study Session worker owns authorization, idempotency, progress/event persistence and commit/rollback.

The compatibility `execute_review_action` entrypoint remains while REST, MCP and v2 session callers use rating-shaped inputs. It resolves the rating to the same semantic Action and delegates to the dispatcher. Wire v3 will pass explicit Action/Trigger identities through strict validation before dispatch.

## Responsibility boundary

| Component | Responsibility |
|---|---|
| Interaction UI | Emit one allowlisted semantic Action. |
| Wire/adapter validator | Decode a supported envelope and verify its Action/Trigger fields against the pinned session. |
| Built-in Trigger Runtime | Authorize the exact Action/Trigger pairing and call the exact Algorithm adapter. |
| Algorithm adapter | Calculate previews/transitions without persistence. |
| Native application/session service | Verify user/card/scope/revision, apply progress/event/required effects and own the DB transaction. |
| Queue worker, when enabled | Transport/replay the same primary command under the same session/revision contract; it is not a secondary Trigger effect. |
| Post-commit consumers | Optional analytics/notification work with separate durable idempotency; deferred when that durability requires new storage. |

## Runtime contract

```text
BuiltInReviewTriggerCommand
  action:
    rating
    action_key = review.{rating}
    trigger_key = scheduler.review.{rating}
    trigger_contract_version = 1
  trigger:
    key
    version
  algorithm_key
  algorithm_version

dispatch result
  canonical action identity
  exact algorithm identity/state schema
  calculated next CardState
```

The supported Trigger inventory is introspectable and contains exactly four `(key, version)` pairs. There is no public handler name, callable reference, arbitrary payload or multi-trigger chain.

## Primary sequence

```text
trusted Interaction / compatibility adapter
  -> validate wire and pinned session identities
  -> authorize user, card, effective overlay scope and revision
  -> dispatch exact built-in Trigger
  -> exact Algorithm transition
  -> canonical native mutation core
       progress + ReviewEvent + required local effects
  -> outer service transaction commit
  -> optional post-commit handoff
```

HTTP and MCP direct review own one command transaction. Study Session synchronous commit owns the lease/idempotency/sequence transaction around multiple calls to the same mutation core. An async worker, if admitted, must provide equivalent checks and durable command idempotency before it is considered an active production path.

## Error and idempotency matrix

| Condition | Result | Mutation |
|---|---|---|
| Unknown Action | `StudyActionValidationError` | None |
| Unknown Trigger key/version | `TRIGGER_UNAVAILABLE` | None |
| Known Trigger paired with different Action | `TRIGGER_CONTRACT_MISMATCH` | None |
| Unknown Algorithm key/version | `StudyAlgorithmNotFoundError` / stable adapter error | None |
| Wire identity differs from pinned session | Wire/session typed contract error before dispatch | None |
| Duplicate primary command identity | Return/reconcile canonical existing result | No duplicate event/effect |
| Progress revision/scope changed | Typed conflict from transaction owner | Transaction rollback |
| Required effect fails | Primary transaction fails | Transaction rollback |
| Optional follow-up fails | Primary result remains committed; follow-up retries by its own ID | No second primary mutation |

## Alternatives

### Permanent rating-to-Algorithm adapter only

Rejected as the target boundary. It preserves behavior but cannot make Trigger identity/version a verified part of wire v3 or audit history.

### Generic Trigger registry/plugin engine

Rejected for Phase 2. Arbitrary handlers, user-defined payloads and chains introduce authorization, cycle, durability and schema requirements outside this phase.

### Minimal built-in exact-version dispatcher

Accepted. It makes the current four behaviors explicit and fail closed while preserving the existing scheduler and progress authority.

## Implement now and defer

Implemented now:

- exact four-Trigger inventory;
- typed Action, Trigger and Algorithm command;
- pure dispatcher;
- compatibility delegation from `execute_review_action`;
- mismatch/unavailable tests.

P2-07:

- discriminated Python/TypeScript wire v3 schemas;
- pinned session validation and dual v2/v3 readers;
- rollout/retirement telemetry and cross-deploy tests.

Deferred to Phase 3:

- StudyMode/applied-composition allowlists selecting a built-in Interaction/Trigger mapping.

Deferred to Phase 4 or later:

- durable secondary effect outbox;
- reusable or user-defined Trigger definitions/state;
- multiple chains, conditional automation or Template-provided execution.

## Rollback

The compatibility entrypoint can temporarily calculate through its previous direct adapter implementation while retaining the published Trigger IDs in stored events/wires. Do not reinterpret a published Trigger version or fall back to another Algorithm version. Wire v3 must not be enabled unless every supported consumer contains the exact dispatcher/artifacts required by its active leases.
