# P4-03 — Versioned Algorithm State and availability contract

> Phase: 4
>
> Priority: P0 decision
>
> Status: TODO
>
> Dependency: P4-00 and P4-01; consistency with P4-02/P4-04
>
> Primary lane: Scheduler / Data architecture

## Mục tiêu

Chốt exact versioned state và query projection cho current compatibility scheduler mà không cho generic domain code đọc arbitrary JSON.

## Công việc

1. Map every `CardProgress` field into raw preservation, generic envelope, Algorithm State, availability or provenance.
2. Define exact Algorithm key/version/state schema; `scheduler_mode` remains label/provenance unless registry identity proves executable.
3. Define canonical JSON, size limit, hash, validation, unknown version, corruption recovery and decoder retirement requirements.
4. Compare state-in-envelope versus separate 1:1 current state row.
5. Define normalized availability anchors and query contract; never store current-time eligibility as permanent fact.
6. Freeze queue normalization, due day/time precedence, suspension, burial, learn-ahead, timezone/day-boundary and no-progress semantics.
7. Preserve Card-compatible multiplicity/order in Phase 4 comparison even though mirror identity is learner/Note.
8. Define fixed-context cross-language golden vectors and sampled transition comparison.
9. Document future Algorithm switch request/authorization inputs; do not enable switching.

## Output

- Accepted Algorithm State/availability ADR.
- Field mapping matrix and exact error codes.
- Decoder/size/retirement contract.
- SQL query projection and ordering specification.
- Golden-vector specification.

## Acceptance

- Raw data can round-trip without scheduler defaults, clock reads or transition replay.
- Exact decoder fails closed for unsupported state; labels do not select an executable.
- Availability reproduces current due/count/order behavior at a fixed context.
- Query-critical fields are relational/indexable; arbitrary state remains opaque to generic queries.
- No shadow read becomes operational authority.

## Verification

Architecture cross-review against scheduler registry, repository SQL, session policy snapshots and P1-04 lifecycle. Runtime change: none.

## Rollback

ADR can be superseded before P4-05; issued schema/state versions remain readable under the accepted retirement contract.
