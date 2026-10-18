# Kế hoạch triển khai Phase 4 — learner/Note progress shadow

> Status (2026-09-20): **Phase 4 and INT-02 complete for pre-release development**; P4-11 production exceptions remain explicit. No shadow read authority or production rollout has been approved.
>
> Planning date: 2026-09-10
>
> Current update (2026-09-20): P4-08/P4-09/P4-10 are committed on `develop` at `263b65e`; P4-10 locally reconciled 16,424 synthetic rows with zero unexplained differences. P4-11's local large-row-count and isolated VPS MySQL 8.0.46 small-cohort rehearsal are [accepted for pre-release development](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) only. The [INT-02 closeout](../../architecture/phase-4-int02-closeout-2026-09-20.md) passed full backend/frontend tests and a fresh disposable MySQL local probe. Production multi-user/overlay load, remaining fault matrix and operational limits are **deferred, not passed**; production shadow enablement remains gated. `CardProgress` remains authoritative and all Phase 4 flags default off. This update supersedes historical status lines below.
>
> Repository baseline: `develop` at `880ff1b` (`phase3`)
>
> Scope: generic learner/Note progress envelope, versioned Algorithm State, normalized availability projection, additive backfill and shadow reconciliation
>
> Authority boundary: `CardProgress` remains the only operational read/write authority for all of Phase 4

Tài liệu này là kế hoạch thực thi chi tiết cho phase tiếp theo. Mọi thay đổi model, migration, backfill hoặc mirror writer chỉ được bắt đầu sau khi các decision gate tương ứng được chốt. Phase 4 không chuyển quyền authority; cutover thuộc Phase 5.

Grounding: [Phase 4 entry investigation](../../architecture/phase-4-entry-investigation-2026-09-09.md), [canonical architecture plan](../../architecture/study-interaction-trigger-algorithm-plan.md), [Phase 3/INT-01 closeout](./completed/PHASE_3_AND_INT_01_CLOSEOUT_2026-09-09.md), và [P1-02 external conflict contract](./completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md).

## 1. Kết quả cần đạt

Phase 4 hoàn tất khi hệ thống có một derived mirror cho mỗi learner/Note hợp lệ, gồm generic envelope, exact Algorithm/state-schema identity, state payload đã validate, availability anchors có thể query, và contributor/provenance evidence. Mirror được backfill và cập nhật atomically cùng mọi authoritative mutation, nhưng mọi user-facing read và scheduler decision vẫn đọc `CardProgress`.

Kết quả bắt buộc:

1. Mọi `CardProgress` được phân loại `mirrored`, `quarantined` hoặc `unresolvable` với disposition có audit; không bỏ row/value.
2. Nhiều Cards của cùng learner/Note không được silent merge. Contributor identity, revision, raw state hash và event/source lineage phải được giữ.
3. Mapper giữ lossless raw state và tạo exact `legacy-anki` compatibility state riêng; không rebuild current state từ `ReviewEvent`.
4. Availability giữ đúng queue, due time/day, suspension, burial, timezone/day-boundary và learn-ahead semantics; không lưu `eligible_now` như fact vĩnh viễn.
5. Native REST/MCP, session commit, async worker, Anki snapshot/import, reset, clone cutover/rekey và delete lifecycle đều có explicit mirror/disposition behavior.
6. Backfill resumable, idempotent, keyset-bounded và không ghi đè mirror mới hơn.
7. SQLite behavior tests và disposable MySQL migration/concurrency/restart rehearsal đều pass.
8. Tắt flags đưa runtime về `CardProgress`-only ngay lập tức; additive data được giữ cho diagnosis.

## 2. Invariants

- `CardProgress` tiếp tục là source of truth trong Phase 4.
- Không có request/scheduler path nào dùng shadow để quyết định answer, due, order hoặc conflict.
- Mirror là derived output trong cùng transaction/savepoint với authoritative write; không tự commit.
- Expected fan-in divergence tạo audited quarantine và giữ authoritative write hợp lệ. Unexpected mirror DB/codec error làm rollback unit hiện tại khi mirror flag bật.
- Logical overlay giữ source/local Note identity và learner ownership; không copy hoặc mutate source Note/Card.
- `ReviewEvent` là fact/history, không phải nguồn đủ để reconstruct current state.
- Existing Card IDs, session wire v2/v3, composition IDs và exact Algorithm lifecycle tiếp tục tương thích.
- Không implement authority cutover, Algorithm switching, physical reusable Template/application storage, Card cascade removal hoặc 30-day purge trong Phase 4.
- Backfill không chạy từ `create_app()`, `db.create_all()` hoặc startup maintenance mặc định.

## 3. Entry findings và mức ảnh hưởng

| Finding | Evidence | Ảnh hưởng |
|---|---|---|
| Active frontend snapshot có thể bị rewrite khi Template được edit | `useStudySession.ts`, `sessionStore.ts`, Phase 3 binding ADR | **Resolved by P4-00:** authoring changes không mutate active/pending lease |
| Backend unknown `study-session-config.*` bị đọc như legacy | `study_session_config.py` pure decoder probe | **Resolved by P4-00:** chỉ exact wrapper hoặc validated legacy policy được nhận |
| `CardProgress.card_id` nullable; learner/Card là UQ hiện tại | model + audit | P4-01/P4-02 phải inventory NULL/orphan/fan-in trước backfill |
| Runtime `CardState` không chứa toàn bộ raw progress/provenance | `study_repository.py` + model | P4-06 phải dùng lossless source serializer riêng |
| Availability phụ thuộc clock/policy/timezone | study repository/scheduler config | P4-03 không được materialize timeless eligibility boolean |
| Audit fan-in chưa chứng minh pointer lineage tương đương | architecture audit query | P4-01/P4-02/P4-10 phải mở rộng accounting |
| App đăng ký `StudySessionBatch` nhưng baseline không có migration tương ứng | app factory/model/migration search | **Resolved by P4-01A:** production applied independent migration `20260913_000037`; refreshed contract check passes |
| Reset có thể xóa state rồi tạo lại revision thấp | deck progress reset | Backfill fence cần contributor identity/hash + subject generation, không chỉ `max(revision)` |

## 4. Quyết định đã chốt và không mở lại

- Một learner có một progress subject cho một logical Note, dùng chung giữa Templates/StudyModes.
- Mixed NoteType scope dùng grouped pre-session selector và exactly-one composition.
- Current external conflict contract của P1-02 vẫn giữ: modern snapshots dùng revision/hash, revlog là history-only, ambiguous legacy snapshot fail closed, reset invalidates affected sessions.
- Algorithm executable/decoder retirement theo P1-04; built-in Trigger/evaluator security theo Phase 2.
- Future Algorithm switch khởi tạo từ history có provenance/completeness, nhưng Phase 4 chưa thực thi switch.
- Detailed execution retention là 30 ngày theo product decision; Phase 4 chỉ chốt minimum scheduler-grade history cần giữ, chưa purge.

## 5. Quyết định Phase 4 phải chốt

### D4-1 — Progress identity, fan-in và revision

- Exact logical Note identity cho owned, installed-source và installed-local cases.
- Meaning của Note-level `revision`/`generation` khi authoritative revisions vẫn per Card.
- Contributor vector tối thiểu: sorted `(CardProgress.id, Card.id, revision, canonical raw-state hash, last_review_event_id)` và reset/rekey generation hoặc equivalent tombstone fence.
- Disposition cho single, equivalent state với distinct lineage, divergent, NULL subject, orphan, deleted/reset, imported ambiguous và unsupported state.
- Lock order: acquire a learner/Note coordination row or equivalent before contributor `CardProgress` locks; prove first-create and sibling-Card concurrency on MySQL.

### D4-2 — Algorithm State

- Proposed default for ADR review: active Algorithm identity belongs to the learner/Note mirror; user/deck/StudyMode supplies requested policy context but cannot silently switch it.
- Phase 4 only maps current compatibility scheduler to exact `legacy-anki/1.0.0` + `anki-card-state.v1`; labels such as `scheduler_mode=fsrs` are provenance, not executable identity proof.
- State JSON uses canonical serialization, exact decoder registry, bounded size, content hash and fail-closed unknown/corrupt handling.
- Raw CardProgress preservation and executable Algorithm State are separate materials.
- Future switch authorization/history initializer contract is documented for Phase 5 without enabling it.

### D4-3 — Availability projection

- Store stable query anchors such as lifecycle/status, normalized queue/bucket, due time/day and hidden flags.
- Evaluate current eligibility using frozen `now`, timezone, day boundary, learn-ahead and policy context at query/compare time.
- Preserve current order: relearning → learning → review → new; then due keys and Card compatibility tie-breakers while Card readers remain authoritative.
- Define no-progress, completed, suspended, buried-until-day and indefinite burial semantics.

### D4-4 — History and lifecycle

- Current state is backfilled from `CardProgress`, not reconstructed from `ReviewEvent`.
- Preserve per-contributor latest-event pointer and Connect external identities; do not manufacture one winner pointer for equivalent fan-in.
- Define minimum chronological/provenance/completeness material future history-based initializer requires after retention cleanup.
- Define mirror tombstone/detached behavior for reset, source/local Note delete, Template/Card delete and clone rekey. Authority cascade changes remain Phase 6.

## 6. Conceptual storage direction

P4-05 compared these alternatives before fixing DDL:

| Alternative | Strength | Cost/risk |
|---|---|---|
| A. One learner/Note row with state, availability and contributor JSON | fewer joins and simpler first migration | row bloat, weak contributor integrity, difficult lifecycle/history accounting |
| B. Lockable envelope + separate current Algorithm State, availability and contributor/disposition rows | explicit ownership, narrow hot rows, relational reconciliation and future state decoders | more tables/joins and more careful atomic writes |

Accepted direction is B. Exact names/DDL contracts are in the [P4-05 ADR](../../architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md):

- envelope: learner + logical Note, mirror status, monotonic generation, active Algorithm identity and last mutation provenance;
- current Algorithm State: exact key/version/schema, canonical JSON, size and hash;
- availability: normalized query anchors, no ephemeral `eligible_now` fact;
- contributors: every source CardProgress/Card identity, revision, raw state hash and event/source pointers;
- migration run/checkpoint/disposition: resumability, quarantine, counts, sample IDs and evidence digests.

P4-05 fixes foreign-key delete behavior, active-row uniqueness, JSON/column types, indexes and retention representation. No physical application/binding tables are required for the Phase 4 mirror.

## 7. Dependency graph

```text
P4-00 frozen-session correction ──────────────┐
P4-01 preflight ─> P4-01A schema remediation ─┼─> P4-02 progress/fan-in ADR
                                               ├─> P4-03 state/availability ADR
                                               └─> P4-04 history/lifecycle ADR
P4-01A production gate + P4-02 + P4-03 + P4-04 ─> P4-05 physical schema ADR
P4-05 ─> P4-06 additive migration + lossless mapper
P4-06 ─> P4-07 native/session/worker mirror
P4-07 ─> P4-08 external/reset/cutover/delete mirror
P4-08 ─> P4-09 resumable backfill while mirror is enabled
P4-09 ─> P4-10 shadow reconciliation
P4-10 ─> P4-11 MySQL rollout rehearsal
P4-11 ─> INT-02 Phase 4 integration/closeout
```

Production applied both P4-01A revisions. The refreshed two-run P4-01 bundle used an ephemeral `SELECT, SHOW VIEW` principal and confirms head `20260913_000038`, zero unexplained drift and no batch-table issue. P4-02/P4-03/P4-04 were [accepted jointly](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md), and P4-05 is accepted.

## 8. Task map

| ID | Task | Primary output | Gate |
|---|---|---|---|
| P4-00 | [Frozen session entry correction](./P4-00_FROZEN_SESSION_ENTRY_CORRECTION.md) | **COMPLETED** — immutable active artifacts, strict config/batch restore | Phase 3 freeze contract pass |
| P4-01 | [Current MySQL/schema/data/writer preflight](./P4-01_CURRENT_STATE_PREFLIGHT.md) | **COMPLETED / ACCEPTED** — signed read-only evidence + full accounting | no blocking unknown before physical design |
| P4-01A | [Independent schema drift remediation](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md) | **COMPLETED / PRODUCTION VERIFIED** — batch table + schema convergence | production head/drift/contract pass |
| P4-02 | [Learner/Note identity, fan-in and revision contract](./P4-02_PROGRESS_IDENTITY_FANIN_REVISION.md) | **COMPLETED / ACCEPTED** — identity/lock/disposition ADR | no silent merge |
| P4-03 | [Algorithm State and availability contract](./P4-03_ALGORITHM_STATE_AVAILABILITY.md) | **COMPLETED / ACCEPTED** — state/codec/query projection ADR | exact decoder + due/order parity definition |
| P4-04 | [History, provenance and lifecycle contract](./P4-04_HISTORY_PROVENANCE_LIFECYCLE.md) | **COMPLETED / ACCEPTED** — initializer-input and lifecycle ADR | every lineage/lifecycle case has disposition |
| P4-05 | [Physical shadow schema design](./P4-05_PHYSICAL_SHADOW_SCHEMA.md) | **COMPLETED / ACCEPTED** — exact MySQL schema and migration specification | alternatives/trade-offs/constraints approved |
| P4-06 | [Additive migration and lossless mapper](./P4-06_ADDITIVE_SCHEMA_AND_MAPPER.md) | **COMPLETED / MERGED**; models, Alembic `000039`, exact codecs, flags off | disposable MySQL round-trip + raw parity passed |
| P4-07 | [Native/session/worker transactional mirror](./P4-07_NATIVE_SESSION_MIRROR.md) | **IMPLEMENTED / LOCAL VERIFIED — COMMITTED ON DEVELOP (`bd96abc`)** | atomicity, locks, receipt/retry parity passed |
| P4-08 | [External and lifecycle transactional mirror](./P4-08_EXTERNAL_LIFECYCLE_MIRROR.md) | **IMPLEMENTED / LOCAL VERIFIED — UNCOMMITTED** | 755 backend tests + disposable MySQL savepoint/reset/delete/race passed |
| P4-09 | [Resumable backfill](./P4-09_RESUMABLE_BACKFILL.md) | **IMPLEMENTED / LOCAL VERIFIED — UNCOMMITTED**; dry-run-first CLI, keyset batches, checkpoints | SQLite fault/race coverage and disposable MySQL crash/resume/CAS pass |
| P4-10 | [Shadow comparison and audit](./P4-10_SHADOW_RECONCILIATION.md) | **LOCALLY COMPLETE / COMMITTED (`263b65e`)**; writer matrix, context-fixed parity and 16,424-row MySQL probe pass | production rollout proof is separate |
| P4-11 | [Disposable MySQL rollout rehearsal](./P4-11_MYSQL_ROLLOUT_REHEARSAL.md) | **CLOSED FOR PRE-RELEASE DEVELOPMENT** by [risk-scoped decision](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) | production-scale/fault/limits deferred to P5-09 before enablement |
| INT-02 | [Phase 4 integration and closeout](./INT-02_PHASE_4_INTEGRATION.md) | **COMPLETED FOR PRE-RELEASE DEVELOPMENT**; [exit report](../../architecture/phase-4-int02-closeout-2026-09-20.md) | Phase 4 development handoff complete; no authority cutover |

## 9. Implementation waves

### Wave 0 — Close entry integrity and evidence

P4-00 corrects the newly found frozen-session gaps. For new-contract active/pending leases, same-tab and cross-tab Template changes must not rewrite frozen Template keys, versions, sources or hashes. Content edit behavior must be explicit; recommended policy is “saved for the next session” for any material that can affect evaluation. Restore recomputes/validates binding material, preserves `composition_id` in durable batches, and fails closed for unknown versioned wrappers while accepting genuine legacy flat policy maps.

P4-00 completed on 2026-09-10 with the “saved for the next session” policy, strict frontend/backend validation, pending-batch composition checks and full Study module regressions. P4-01/P4-01A now have deterministic post-deploy production accounting at head `20260913_000038`; G4-0 is closed.

P4-01 extends the read-only architecture audit and runs it through `wsgi_audit.py`. Inventory includes actual Alembic head/FKs/defaults/indexes/collation/time precision, `study_session_batches` drift, NULL/orphans, all learner/Note fan-in, raw queue labels, FSRS-labelled provenance, event pointer/linkage, logical overlay mappings, active sessions/batches and every writer. Current production facts must be timestamped and redacted.

As of 2026-09-13, audit v4 has a grant-first MySQL safety check and a deterministic production bundle captured through an ephemeral SELECT-only principal. P4-01A's independent migrations are deployed, and production reports head `20260913_000038`, zero drift and no batch issue. See the [current-state preflight report](../../architecture/phase-4-current-state-preflight-2026-09-10.md), [schema remediation record](../../architecture/phase-4-schema-drift-remediation-2026-09-13.md) and [joint acceptance](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md).

Gate G4-0: P4-00 tests pass; P4-01 has deterministic accounting and an explicit disposition for every schema/data unknown. No Phase 4 DDL before this gate.

### Wave 1 — Accept the logical contracts

P4-02, P4-03 and P4-04 produce three linked ADRs. They may be drafted in parallel from the same evidence but are approved together. Terminology, identity, generation, source hash, state version, availability anchors and lifecycle status must match. Each ADR records at least two alternatives and MySQL/SQLAlchemy trade-offs.

As of 2026-09-13, [P4-02](../../architecture/phase-4-progress-identity-fanin-revision-adr-2026-09-10.md) accepts `(learner_user_id, Note.id)` identity, explicit contributor accounting, no-winner fan-in, separate subject generation/mirror revision, lifecycle fencing and the global lock/race matrix.

As of 2026-09-13, [P4-03](../../architecture/phase-4-algorithm-state-availability-adr-2026-09-12.md) and [P4-04](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) are accepted. The refreshed production evidence and [joint cross-review](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md) close G4-D. [P4-05](../../architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md) closes the physical-design gate, and [P4-06](../../architecture/phase-4-additive-schema-mapper-verification-2026-09-13.md) is implemented and locally verified. P4-07 is next after user review/commit.

Gate G4-D: all three ADRs are `Accepted`; every current `CardProgress` column maps to raw preservation, generic envelope, Algorithm State, availability or lineage; every current writer/lifecycle path has a planned outcome; no open decision is deferred into DDL code.

### Wave 2 — Expand storage and implement pure mapping

P4-05 selects the physical design and specifies exact tables, types, FKs, uniqueness, indexes, delete rules and state-size limits. P4-06 implements only additive models/migration and pure codecs. Feature flags default off and no startup backfill exists.

Mapper requirements:

- canonical raw snapshot includes every `CardProgress` column without scheduler defaulting;
- exact compatibility mapper validates raw values and derives state/availability;
- unknown queue/state/version becomes typed quarantine, not implicit `new`;
- timestamps/floats/NULLs hash identically across SQLite test vectors and MySQL rehearsal;
- a round trip proves raw preservation; independent golden vectors prove expected state/availability.

Gate G4-E: migration upgrade/downgrade on disposable databases passes, pre-Phase4 schema upgrades without `db.create_all()`, models match migration, and flags-off app boot/read/write behavior is unchanged.

### Wave 3 — Mirror every mutation atomically

P4-07 introduces one no-commit learner/Note mirror coordinator. The transaction owner determines affected subjects, acquires locks in the approved order, performs existing CardProgress/history mutations, flushes final event pointers, then finalizes mirror once per learner/Note.

P4-08 covers external/lifecycle paths while preserving their existing units:

- modern Anki snapshot: mirror only `applied`, never duplicate/conflict/no-op;
- card package/import: mirror inside the current per-note savepoint;
- revlog: history/provenance accounting only, no current-state rewrite;
- reset: cancel sessions, delete CardProgress, advance tombstone/generation atomically;
- clone cutover/rekey: preserve old→new contributor lineage;
- Note/Card/Template/deck deletes and seed/import reconciliation: explicit detach/quarantine/rebuild behavior, including bulk deletes.

Gate G4-W: fault injection proves unexpected mirror failure rolls back the existing atomic unit; expected divergence quarantines only the mirror; first-create/sibling writes use deterministic locks; session receipts and worker delivery remain idempotent.

### Wave 4 — Backfill while mirrors protect new writes

P4-09 ships a separate CLI/service. Default is dry-run. Recommended initial limits are 250 source progress rows or 100 learner/Note subjects per transaction, then adjusted only from MySQL rehearsal evidence. Keyset cursor uses stable source identity, never offset pagination.

For each batch:

1. read contributor candidates and build canonical vector/hash;
2. acquire subject coordination and contributor locks;
3. re-read and verify identity/revision/hash/generation;
4. upsert trusted mirror or audited quarantine;
5. write disposition counts and checkpoint in the same transaction;
6. release and continue from durable keyset cursor.

Gate G4-B: kill/restart, repeated run, concurrent review/import/reset/delete/rekey, second Card creation and stale checkpoint cases produce the same final accounting; stale backfill never overwrites a newer mirror.

### Wave 5 — Compare without serving shadow data

P4-10 adds read-only comparison for:

- total source-row and contributor accounting;
- raw column/hash/pointer/external provenance parity;
- single/equivalent/divergent/unresolvable disposition stability;
- exact state decoder results and sampled scheduler transitions;
- fixed-context due counts, queue buckets/order, suspension and burial;
- UTC and Asia/Tokyo day boundaries, learning time/day and learn-ahead;
- owned, mixed-template, real installed-source and installed-local cases;
- direct REST, MCP, session, worker, external snapshot/import, reset and lifecycle mutations.

One Note mirror must not deduplicate current Card queue multiplicity during comparison. Comparator projects back to contributor Cards until Phase 6 changes addressing.

Gate G4-S: all source rows and references are accounted for, zero unexplained difference remains, every accepted tolerance is named and measured, and no shadow result is used in a product response.

### Wave 6 — MySQL rehearsal and integration closeout

Original release-grade P4-11 scope: disposable MySQL 8 matching production version, `sql_mode`, charset/collation and representative volume, plus migration-only upgrade, flags-off Gunicorn/`wsgi.py` restart, indexes/EXPLAIN, bounded backfill, two-connection races, first insert, duplicate key, deadlock retry, savepoint rollback, worker retry, backup/restore, flag disable and forward rollback. The [pre-release closeout](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) accepts a measured subset as the development dependency and moves the unproven production-load/fault/limit work to P5-09 before any production enablement.

INT-02 runs modular suites first, then full suite as the pre-release gate. It updates the canonical tracker only when all outputs and evidence links exist.

Phase 4 completion does not enable Note progress as authority. Phase 5 receives a go/no-go recommendation and a list of remaining quarantines/limitations; it requires separate authorization.

## 10. Feature flags and rollout states

Exact names are finalized in P4-05. Recommended semantics:

| State | Schema | Mirror writes | Backfill | Compare | Product reads |
|---|---|---|---|---|---|
| R0 baseline | absent | off | off | off | `CardProgress` |
| R1 expanded | present | off | off | off | `CardProgress` |
| R2 mirror pilot | present | selected internal cohort/on | off | diagnostic | `CardProgress` |
| R3 protected backfill | present | on | dry-run then apply | on | `CardProgress` |
| R4 reconciled Phase 4 | present | on | complete/resumable | full audit green | `CardProgress` |

Flags default off in every environment. Do not couple them to async batch admission, wire-v3 issuance or startup maintenance flags. Turning mirror off is the immediate runtime rollback; do not downgrade schema during an incident.

## 11. Verification matrix

| Slice | Minimum verification |
|---|---|
| P4-00 | Study backend/frontend restore, cross-tab edit, pending batch and wire compatibility tests |
| P4-01 | audit service/CLI tests; deterministic double-run; approved SELECT-only MySQL evidence |
| P4-02..P4-05 | ADR cross-review, model/migration inventory, link check, `git diff --check` |
| P4-06 | database + study backend modules; migration upgrade/downgrade; codec golden vectors |
| P4-07 | study + connect_mcp backend; frontend restore compatibility; concurrency/fault injection |
| P4-08 | connect_mcp, decks, flashcards, seed and study backend modules |
| P4-09 | backfill unit/integration, crash/resume/idempotency and two-connection MySQL races |
| P4-10 | audit + study/analytics query parity; fixed clock/timezone vectors; real overlay fixtures |
| P4-11 | disposable MySQL migration/load/restart/rollback report with commands, timing and EXPLAIN |
| INT-02 | `python scripts/run_tests.py --changed`, then `--all`; frontend typecheck/lint; docs links |

Browser profiling is not a Phase 4 requirement unless P4-00 changes visible Study behavior. If needed, use an isolated Chrome profile per `AGENTS.md`.

## 12. Stop conditions

Stop before the next gate when any of these occurs:

- frozen session material can still change after open;
- current MySQL schema/data distribution is unknown at physical approval time;
- one current progress row/value/reference has no disposition;
- fan-in requires choosing a winner without an accepted rule;
- mapper requires scheduler replay or current-time defaults to preserve raw state;
- lock order cannot prevent sibling-Card/deadlock races;
- mirror needs an independent commit or can fail while an authoritative write still commits;
- backfill cannot fence reset/delete/rekey or concurrent new CardProgress;
- shadow mismatch is unexplained, hidden by tolerance or normalized away;
- implementation requires product reads from mirror or authority cutover.

## 13. Rollback

At any Phase 4 runtime stage, disable mirror writes and shadow comparisons, then continue all product behavior from `CardProgress`. Keep additive rows, run/checkpoints and quarantines for diagnosis. Backfill is idempotent and may resume only after the cause is fixed. Migration downgrade is exercised on disposable databases for correctness but is not the incident rollback path. No destructive cleanup occurs in Phase 4.

## 14. Handoff format

Every task closes with:

```text
Task ID:
Primary outcome:
Baseline/evidence used:
Files changed:
Contract or schema behavior:
Writer/read/lifecycle paths covered:
Tests and commands:
Results and measured limits:
Data accounting/quarantine:
Rollback path:
Known limitations:
Follow-up task IDs:
```

Decision tasks replace `Files changed` with decision artifacts and record `Runtime change: none`.
