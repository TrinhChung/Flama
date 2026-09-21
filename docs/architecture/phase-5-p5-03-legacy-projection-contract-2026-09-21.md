# P5-03 — lossless legacy projection encoder and comparison

> Date: 2026-09-21 | Mode: IMPLEMENTED / INERT | Status: **CORE COMPLETE**. The pure encoder/comparator and disposable-MySQL persistence proof are complete. They are not connected to a request path, do not authorize NOTE enrollment, and do not change production reads or writes.

## Invariants before implementation

1. One learner/Note authority transition must update every active sibling `CardProgress` in the same transaction. A missing, duplicate or unexpected sibling is a hard failure.
2. A candidate legacy row must match the exact registered Algorithm State, its semantic availability anchors, **and** an independent expected raw digest for that Card. State or semantic equality alone cannot prove lossless rollback.
3. Card identity, Card-specific event pointer, revision and timestamps stay distinct even when two Cards share one Note state. A historical raw value cannot be silently normalized away at enrollment or during reversible write-through.
4. Unknown Algorithm/state codec, nonfinite/unmappable value, and unprojectable Note transition fail closed. No `CardProgress` update or NOTE mode switch is permitted by this slice.

## Observed lossiness and alternatives

### Algorithm State is not an inverse of raw CardProgress

- **Observed:** `app/services/study_progress_shadow_mapper.py::map_card_progress` maps `queue="learn"` to `"learning"` and normalizes signed zero for Algorithm State. Its state payload omits Card ID, progress ID/revision, `last_review_event_id`, raw interval representation, burial anchors, leech timestamp, and row timestamps. The semantic hash includes some availability anchors but not the omitted raw metadata. `app/services/study_progress_shadow_codec.py` separately serializes **every** `CardProgress` column into typed, bounded canonical raw bytes.
- **Evidence:** `models/card_progress.py`, `RAW_CARD_PROGRESS_FIELDS`, `serialize_raw_card_progress`, `map_card_progress`, `tests/test_study_progress_shadow_codec.py` golden vectors.
- **Potential concern:** a reverse encoder based only on `StudyProgressState.state_payload` could produce rows that look equivalent to the scheduler yet differ in legacy fields needed for rollback, audit and Connect revision/hash checks.
- **Impact:** irreversible accepted NOTE transitions or a false-positive reconciliation before switching back to Card authority.
- **Unknowns resolved here:** every transition receives a hash-verified per-Card baseline; a newly allocated compatibility row uses the same contract. Active-sibling resolution, overlay/rekey identity, transaction locking and mutation ownership remain deliberately outside this pure layer and are owned by P5-04/P5-06.
- **Alternatives Considered:** (A) rebuild every legacy field from Algorithm State only; (B) keep per-Card raw baseline/metadata and explicitly encode changed fields for every transition; (C) accept lossy NOTE-only state with forward-repair rollback.
- **Trade-offs:** A is small but mathematically non-invertible for current data; B adds write amplification and per-sibling evidence but supports the required reversible window; C cannot offer the currently promised Card rollback.
- **Recommendation:** B. Reject any transition until its exact encoder and independent expected raw vector exist. Defer C to a separately approved forward-only phase.
- **Migration Implications:** no additional DDL is required by P5-03. The encoder consumes the exact Phase 4 raw document as its baseline; P5-04 must refresh compatibility evidence in the same transaction rather than silently overload `StudyProgressState` JSON.

## Implemented, non-serving encoder and oracle

`app/services/study_authority_projection_comparator.py::compare_note_legacy_projection` accepts an exact registered Algorithm identity/payload plus its persisted size/hash, learner identity, expected semantic hash, an independently built expected raw SHA-256 **for each active Card**, and the complete candidate sibling vector. It checks:

- exact decoder availability, stored payload size/hash, and learner identity;
- missing, unexpected or duplicate sibling Cards;
- each Card's mapped Algorithm State against the Note state;
- each Card's semantic availability hash;
- the entire raw `CardProgress` column inventory through its canonical digest.

`app/services/study_authority_projection_encoder.py::encode_note_state_to_legacy_cards` now builds that independent vector. It verifies each baseline raw size/hash, learner/Card identity and expected revision; decodes only a registered exact Algorithm State; encodes every active sibling; serializes all 27 `CardProgress` columns; and runs the comparator before returning. It owns no SQL and cannot select authority.

Two explicit sibling dispositions cover both mutation and lifecycle cases:

- `APPLY_NOTE_STATE` projects the target state and compatibility metadata, then advances that Card's revision once.
- `PRESERVE_MATCHING_STATE` retains the baseline bytes and revision exactly, but only if the row already maps to the same Note state and semantic anchors. This permits a new sibling to be materialized without spuriously advancing existing siblings.

The caller must resolve the complete active sibling set under the learner/subject fence. It must allocate and flush a default compatibility shell before encoding a newly created Card, because the raw contract includes the database-generated progress ID. Deletion removes the no-longer-active Card/row from the set. Overlay/rekey identity resolution and import orchestration remain P5-06 responsibilities; they cannot be inferred safely inside a Card row serializer.

## Complete field inventory

| Source | `CardProgress` fields / evidence |
|---|---|
| Preserved immutable baseline | `id`, `user_id`, `card_id`, `created_at` |
| Exact decoded Note Algorithm State | `queue`, `step_index`, `due_at`, `due_day`, `interval_days_raw`, `is_suspended`, `review_kind`, `scheduler_mode`, `ease_factor`, `memory_stability`, `memory_difficulty`, `suspension_reason`, `reps`, `lapses`, `last_reviewed_at` |
| Explicit Action/lifecycle compatibility metadata | rounded integer `interval_days`, `is_buried`, `buried_until_day`, `last_leech_at`, `last_leech_lapses`, `updated_at` |
| Explicit per-sibling command metadata | `last_review_event_id` |
| Derived from locked baseline | `revision = expected_base_revision + 1` for apply; unchanged for preserve |
| Separate presentation input | `Card.created_at` for availability ordering; it is intentionally not confused with `CardProgress.created_at` |

## MySQL representability boundary

The local schema probe confirmed that all four legacy floating columns are MySQL `FLOAT` and the projected datetime columns are `DATETIME(0)`. Therefore arbitrary f64 values and microseconds cannot round-trip losslessly. The encoder rejects them with `UNPROJECTABLE_LEGACY_FLOAT` or `UNPROJECTABLE_LEGACY_TIMESTAMP`; it never silently rounds an already-authoritative Note state. P5-04 must produce a legacy-representable state before committing Note authority.

The disposable MySQL 8.0.40 probe now proves:

- exact 1:2 Note→Card persistence after reload;
- full transaction rollback when failure occurs after only the first sibling update;
- preserve-existing/materialize-new behavior for a third sibling, followed by delete cascade;
- exact all-sibling reset projection;
- explicit dirty marking for `updated_at`, preventing SQLAlchemy's `onupdate` clock from replacing an equal projection timestamp on a newly flushed shell.

Eight encoder tests plus six comparator tests cover golden canonical JSON/SHA-256, baseline tamper/stale revision/wrong learner, missing/duplicate/unknown sibling input, unsupported decoder, leech metadata mismatch, 1:N apply/preserve behavior and MySQL representability rejection.

## Expand → compare → cutover → contract

1. **Expand — complete:** retain the Phase 4 exact raw codec and classify every field. No NOTE mode.
2. **Compare — complete for the projection layer:** pure encoder, independent golden vector, 1:N/new/delete/reset MySQL fixtures and fault rollback pass. Overlay/import/rekey *resolution* remains in P5-06 and must feed this same closed contract.
3. **Cutover — not started:** P5-04 must persist the proposed vector, Note token, event/fact/receipt and refreshed evidence in one transaction under the learner/subject fence; fail the Action if any sibling or exact stored value diverges.
4. **Contract:** do not remove legacy rows/raw codec/decoder until the rollback window and a separate post-Phase-5 decision end.

Current gate: **P5-03 core is complete and remains inert**. This permits P5-04 implementation; it does not satisfy G5-W, enable NOTE mode, or prove overlay/import/rekey routing before P5-06.
