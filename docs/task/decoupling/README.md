# Study decoupling task backlog

> Status: Phase 0–3 and INT-01 are closed, including the P4-00 correction that reclosed the frozen-session gate on 2026-09-10. Phase 4 is active at P4-01/P4-01A: schema remediation is implemented and rehearsed on local MySQL, while production upgrade plus refreshed SELECT-only evidence and joint P4-02/P4-03/P4-04 acceptance remain open; schema/runtime mirror has not started.
>
> Source of truth: `docs/architecture/study-interaction-trigger-algorithm-plan.md`
>
> Latest P1/P2 closeout: [2026-09-08 execution closeout](./completed/P1_P2_EXECUTION_CLOSEOUT_2026-09-08.md) — 8 tasks completed; async admission and v3 issuance remain flag-off by default.
>
> Latest Phase 3 execution plan: [2026-09-09 Phase 3 plan](./P3_EXECUTION_PLAN_2026-09-09.md) — completed through INT-01.
>
> Latest Phase 3 closeout: [2026-09-09 Phase 3 and INT-01 closeout](./completed/PHASE_3_AND_INT_01_CLOSEOUT_2026-09-09.md) — historical delivery record; amended on 2026-09-10 to record the P4-00 correction and reclosed gate.
>
> Latest Phase 4 plan: [2026-09-10 Phase 4 execution plan](./P4_EXECUTION_PLAN_2026-09-10.md) — correction, decision, additive shadow schema, mirror, backfill, reconciliation, and rollout rehearsal through INT-02.
>
> Phase 4 entry evidence: [2026-09-09 investigation](../../architecture/phase-4-entry-investigation-2026-09-09.md) — includes the P4-00 frozen-session blocker and current writer/storage inventory.
>
> Phase 4 current-state preflight: [2026-09-10 P4-01 report, updated 2026-09-13](../../architecture/phase-4-current-state-preflight-2026-09-10.md) — deterministic production evidence is captured; [P4-01A](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md) implements the independent repairs through head `20260913_000038`, with production application and refreshed evidence still pending.

> Phase 4 identity/fan-in design: [2026-09-10 P4-02 provisional ADR](../../architecture/phase-4-progress-identity-fanin-revision-adr-2026-09-10.md) — learner/Note key, contributor vectors, generation/revision, lock order and typed dispositions are drafted; production distribution is incorporated, while the P4-01A production gate and joint P4-02/P4-03/P4-04 review remain open.
>
> Phase 4 state/availability design: [2026-09-12 P4-03 provisional ADR](../../architecture/phase-4-algorithm-state-availability-adr-2026-09-12.md) — exact compatibility identity, lossless raw/state codecs, typed failures, availability anchors and fixed-context Card-order comparison.
>
> Phase 4 history/lifecycle design: [2026-09-12 P4-04 provisional ADR](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) — provenance/completeness, retained scheduler facts, reset/delete/rekey fences and initializer handoff.
>
> Latest completed-task evidence review: [2026-08-30 review and P1-02 closeout](../../architecture/decoupling-progress-review-2026-08-30.md)
>
> Latest Phase 0 gate review/handoff: [`P0_PHASE_REVIEW_HANDOFF_2026-08-29.md`](./P0_PHASE_REVIEW_HANDOFF_2026-08-29.md) — **GO; P0-01 through P0-04 COMPLETED**.
>
> Historical cross-phase dependency plan: [`PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md`](./PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md) — retained as planning history for the delivered Phase 0–3 slice.
>
> Historical reviewed backlog: [`REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md`](./REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md) — superseded for active work by the Phase 4 execution plan.
>
> Scope boundary: Phase 4 chỉ bổ sung derived shadow storage và reconciliation. `CardProgress` vẫn là operational read/write authority; authority cutover thuộc Phase 5 và cần authorization riêng.

## 1. Mục tiêu

Thư mục này chia backlog decoupling còn lại thành các task nhỏ, có thể giao và review độc lập. Mỗi task phải mô tả rõ:

- phạm vi và file ownership;
- dependency;
- công việc chi tiết;
- output đầu ra bắt buộc;
- test/verification;
- acceptance gate;
- rollback và phần không được làm.

Không được đánh dấu một Phase hoàn thành chỉ vì test hiện có đang xanh. Task chỉ hoàn tất khi toàn bộ output và acceptance gate trong file task tương ứng được thỏa mãn.

## 2. Invariants chung

1. `CardProgress` tiếp tục là progress authority duy nhất trong toàn bộ Phase 4.
2. Phase 4 chỉ được thêm schema/migration sau khi P4-00, P4-01 và các ADR P4-02..P4-05 đạt gate; không được đổi authority.
3. Shared deck giữ mô hình `logical_overlay`; không copy source Notes/Cards và không mutate source content.
4. REST, MCP và batch phải giữ tương thích API hiện có.
5. `study-session.v2` hợp lệ phải tiếp tục hoạt động trong lease compatibility window.
6. Algorithm resolution phải exact key/version và fail closed.
7. Template JavaScript không được trực tiếp gây reveal/answer/undo hoặc progress write.
8. UI refactor phải zero visual regression trừ khi task nói rõ có UI mới.
9. Audit production phải read-only và không được kích hoạt startup maintenance mutating path.
10. Mọi task phải dùng test runner theo module; không chạy full suite trừ integration gate/CI.

## 3. Thứ tự triển khai

```text
P2-01 security containment                         [global blocker]
        |
        +--> P0-01 --> P0-02 ------> P0-03
        +--> P0-04 -----------------> P0-03
        |
        +--> P0-04 --> P1-01 --> P1-03
        |       |
        |       +--> P1-02
        |       +--> P1-04
        |
        +--> P2-02
        +--> P2-03
        +--> P2-04 --> P2-05
                         |
                 P2-06 --> P2-07

P1/P2 correctness gates + P3-05/P3-07 decisions
        |
        +--> P3-01 --> P3-02
        |       |
        |       +--> P3-03 --> P3-04
        |
        +----------------------> P3-06

All tasks --> INT-01 integration and tracker closeout
```

Historical dependency note: `P2-01` and P0-03 gated the completed Phase 1/2 work; P3-05 and P3-07 then gated the completed Phase 3 runtime sequence. The diagram is retained to explain delivery order, not as an active queue.

Active Phase 4 dependency:

```text
P4-00 frozen-session correction ----+
                                     +--> P4-02/P4-03/P4-04 --> P4-05 --> P4-06
P4-01 current-state preflight --> P4-01A schema remediation ------------+
                                                                        v
P4-07 native/session mirror --> P4-08 external/lifecycle mirror
                                      |
                                      v
P4-09 resumable backfill --> P4-10 shadow reconciliation
                                      |
                                      v
P4-11 MySQL rollout rehearsal --> INT-02
```

P4-00 và phần repository-only của P4-01 có thể bắt đầu song song. Không chốt physical schema trước khi frozen-session gate, current MySQL evidence và các ADR P4-02..P4-05 cùng đạt.

## 4. Danh sách task

### Phase 0 — Freeze evidence and invariants

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P0-01 | [Audit command safety and machine-readable contract](./completed/P0-01_AUDIT_COMMAND_SAFETY.md) | P2-01 | entrypoint read-only, exit code, schema output, tests |
| P0-02 | [Audit coverage and disposition inventory](./completed/P0-02_AUDIT_COVERAGE_AND_DISPOSITION.md) | P0-01 | đầy đủ anomaly categories, counts/samples/dispositions |
| P0-03 | [MySQL baseline verification and drift snapshot](./completed/P0-03_MYSQL_BASELINE_VERIFICATION.md) | P0-02 + P0-04 + operator authorization | `COMPLETED`; current SELECT-only evidence bundle and Phase 0 GO verdict |
| P0-04 | [Behavior acceptance baseline](./completed/P0-04_BEHAVIOR_ACCEPTANCE_BASELINE.md) | P2-01 | characterization matrix cho clone/import/due/direct/MCP/batch/keyboard |

### Phase 1 — Runtime boundaries without storage change

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P1-01 | [Canonical native review transaction](./completed/P1-01_CANONICAL_REVIEW_TRANSACTION.md) | P0-04 | `COMPLETED`; one typed transition/mutation core for REST, MCP and batch |
| P1-02 | [External progress revision/conflict contract](./completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md) | P1-01 | `COMPLETED`; typed Anki/import/reset/cutover revision and conflict contract |
| P1-03 | [ReviewEvent provenance and payload hardening](./completed/P1-03_REVIEW_EVENT_PROVENANCE.md) | P1-01 | `COMPLETED`; canonical native/external provenance, bounded payloads |
| P1-04 | [Algorithm executable and decoder retirement lifecycle](./completed/P1-04_ALGORITHM_VERSION_RETIREMENT.md) | P1-01 | `COMPLETED`; support matrix, fail-closed retention policy, tests |

### Phase 2 — Built-in Interaction and Trigger compatibility

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P2-01 | [Iframe `host_command` containment](./completed/P2-01_IFRAME_HOST_COMMAND_CONTAINMENT.md) | none | đóng progress side channel và forged-message tests |
| P2-02 | [Frontend session mutation mutex](./completed/P2-02_FRONTEND_SESSION_MUTEX.md) | P2-01 | `COMPLETED`; owner-token guard và same-tick tests |
| P2-03 | [Restore validation and quarantine](./completed/P2-03_RESTORE_VALIDATION_QUARANTINE.md) | P2-01 | `COMPLETED`; strict validator, bounded quarantine và recovery |
| P2-04 | [Semantic ReviewInteraction contract](./completed/P2-04_SEMANTIC_INTERACTION_CONTRACT.md) | P2-01 | `COMPLETED`; một semantic callback, raw rating confined to adapter |
| P2-05 | [Trusted keyboard UX and threat model](./completed/P2-05_TRUSTED_KEYBOARD_UX.md) | P2-01 + P2-04 | `COMPLETED`; accepted no-bridge ADR và browser evidence |
| P2-06 | [Built-in Trigger Runtime design checkpoint](./completed/P2-06_TRIGGER_RUNTIME_DESIGN.md) | P1-03 + P2-04 | `COMPLETED`; accepted exact built-in dispatcher contract |
| P2-07 | [Wire v3 and legacy v2 lease policy](./completed/P2-07_WIRE_V3_LEGACY_V2_POLICY.md) | P1-04 + P2-03 + P2-06 | `COMPLETED`; dual reader, negotiation và compatibility tests |

### Phase 3 — Composition/StudyMode compatibility responsibility

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P3-01 | [Exactly-one composition session API](./completed/P3-01_COMPOSITION_SESSION_API.md) | P1/P2 correctness + P3-05 + P3-07 | `COMPLETED`; authorized single selection và compatibility fallback |
| P3-02 | [Clone-aware composition discovery and query-first filtering](./completed/P3-02_CLONE_AWARE_COMPOSITION_QUERY.md) | P3-01 | `COMPLETED`; một resolver cho owned/overlay/local-added contexts |
| P3-03 | [Pre-session StudyMode selection UI](./completed/P3-03_PRE_SESSION_STUDYMODE_UI.md) | P3-01 + P3-05 | `COMPLETED`; selector trước session và request mang selection |
| P3-04 | [Frozen composition restore and stale handling](./completed/P3-04_COMPOSITION_FREEZE_RESTORE.md) | P3-01 + P3-03 | delivery completed; correctness gate reclosed by P4-00 |
| P3-05 | [Mixed-NoteType scope policy](./completed/P3-05_MIXED_NOTETYPE_SCOPE_POLICY.md) | Phase 0 evidence | `COMPLETED`; accepted ADR và API/UI rule |
| P3-06 | [Real overlay-only composition exit gate](./completed/P3-06_OVERLAY_COMPOSITION_EXIT_GATE.md) | P3-01..P3-05 + P3-07 | `COMPLETED`; integration proof dùng `DeckInstall` thật, không clone giả |
| P3-07 | [Applied composition and binding contract](./completed/P3-07_APPLIED_COMPOSITION_BINDING_CONTRACT.md) | Phase 0 evidence | `COMPLETED`; accepted responsibility/identity/lifecycle contract, no schema |

Post-closeout note: P3-01..P3-07 vẫn là lịch sử delivery đã hoàn tất. Acceptance claim “active lease dùng immutable artifact” từng được mở lại bởi entry review và đã được [P4-00](./P4-00_FROZEN_SESSION_ENTRY_CORRECTION.md) đóng lại bằng same-tab/cross-tab regression proof, strict restore/config validation và durable-batch composition checks.

### Phase 4 — Derived learner/Note progress shadow

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P4-00 | [Frozen-session entry correction](./P4-00_FROZEN_SESSION_ENTRY_CORRECTION.md) | none | **COMPLETED** — chặn live Template/Note propagation, strict wrapper/binding/batch validation và regression proof |
| P4-01 | [Current-state preflight](./P4-01_CURRENT_STATE_PREFLIGHT.md) | none | **IN PROGRESS** — deterministic production baseline captured; repository/local remediation passed; production refresh blocks acceptance |
| P4-01A | [Independent schema drift remediation](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md) | P4-01 evidence | **LOCAL GATE PASSED / PRODUCTION PENDING** — independent batch-table migration, model/default parity, safe marketplace convergence and zero-drift local MySQL rehearsal |
| P4-02 | [Progress identity, fan-in, revision and locking ADR](./P4-02_PROGRESS_IDENTITY_FANIN_REVISION.md) | P4-00 + P4-01 | **IN PROGRESS / PROVISIONAL** — learner/Note key, explicit contributors, no-winner fan-in, generation/fence and lock matrix drafted; production distribution captured, schema/joint gates open |
| P4-03 | [Algorithm State and availability ADR](./P4-03_ALGORITHM_STATE_AVAILABILITY.md) | P4-00 + P4-01 | **IN PROGRESS / PROVISIONAL** — exact compatibility state/raw codecs, typed failures and fixed-context per-Card availability contract drafted |
| P4-04 | [History, provenance and lifecycle ADR](./P4-04_HISTORY_PROVENANCE_LIFECYCLE.md) | P4-01 | **IN PROGRESS / PROVISIONAL** — completeness/provenance, retained scheduler facts and reset/delete/rekey fence contract drafted |
| P4-05 | [Physical shadow schema design](./P4-05_PHYSICAL_SHADOW_SCHEMA.md) | P4-01A production gate + P4-02 + P4-03 + P4-04 | MySQL-ready additive model, constraints, indexes and migration/rollback design |
| P4-06 | [Additive schema and lossless mapper](./P4-06_ADDITIVE_SCHEMA_AND_MAPPER.md) | P4-05 | models, Alembic migration, strict codec and authoritative-state mapper |
| P4-07 | [Native and session mirror](./P4-07_NATIVE_SESSION_MIRROR.md) | P4-06 | same-transaction mirror for REST, MCP, direct and batch writers |
| P4-08 | [External and lifecycle mirror](./P4-08_EXTERNAL_LIFECYCLE_MIRROR.md) | P4-07 | import/sync/reset/cutover/delete coverage with explicit dispositions |
| P4-09 | [Resumable backfill](./P4-09_RESUMABLE_BACKFILL.md) | P4-08 | fenced, idempotent, restartable backfill and quarantine |
| P4-10 | [Shadow reconciliation](./P4-10_SHADOW_RECONCILIATION.md) | P4-09 | state, due, queue, provenance and writer-coverage comparison report |
| P4-11 | [MySQL rollout rehearsal](./P4-11_MYSQL_ROLLOUT_REHEARSAL.md) | P4-10 | staging/rehearsal evidence, rollback drill and production runbook |

### Cross-phase integration

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| INT-01 | [Phase 0–3 integration and closeout](./completed/INT-01_PHASE_0_3_INTEGRATION.md) | toàn bộ task trên | `COMPLETED`; combined verification, duplicate-boundary audit, tracker update |
| INT-02 | [Phase 4 integration and exit gate](./INT-02_PHASE_4_INTEGRATION.md) | P4-00..P4-11 | full verification, zero unexplained diff, rollback proof và Phase 5 handoff only |

## 5. Output bàn giao bắt buộc cho mọi task

Mỗi task khi hoàn thành phải ghi trong PR/handoff:

```text
Task ID:
Primary outcome:
Files changed:
Contract/API behavior changed:
Tests added or updated:
Commands run:
Test results:
Rollback path:
Known limitations:
Follow-up task IDs:
```

Nếu task là investigation/ADR, thay `Files changed` bằng danh sách tài liệu/evidence và ghi rõ `Runtime change: none`.

## 6. Test commands chuẩn

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
python scripts/run_tests.py --module database,cli,analytics --backend-only
python scripts/run_tests.py --changed
```

Chỉ chạy `python scripts/run_tests.py --all` tại INT-02/CI hoặc pre-release gate; từng task dùng ma trận hẹp ghi trong task file.

Với browser security/keyboard testing, bắt buộc dùng Chrome profile riêng theo `AGENTS.md`; không dùng profile cá nhân của người dùng.

## 7. Phase 4 entry và exit

P4-00 đã hoàn tất; entry hiện tại cho phép investigation/preflight read-only của P4-01. Additive model/migration bắt đầu ở P4-06 chỉ khi:

- P4-00 đã chứng minh active session không bị live Template/Note edit thay artifact/binding;
- P4-01 current MySQL SELECT-only evidence đã được capture và mọi schema/data gap có disposition được duyệt;
- P4-02..P4-05 được duyệt và không còn quyết định ngầm trong migration;
- schema change được user authorize trong một implementation turn riêng.

Phase 4 chỉ hoàn tất ở INT-02 khi mọi writer/lifecycle path đã tham gia mirror, backfill có thể resume, zero row/value bị bỏ mà không có disposition, và zero reconciliation difference chưa giải thích. Hoàn tất Phase 4 **không** tự động cho phép Phase 5 đọc/ghi từ shadow; authority cutover phải có kế hoạch và authorization riêng.
