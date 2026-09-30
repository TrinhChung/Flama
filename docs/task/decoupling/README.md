# Study decoupling task backlog

> **Status (2026-09-30): Phase 5, Phase 6, Phase 7 chạy trên production.** P5-11 NOTE hardening deploy qua PR #173 (`6472e42`). Phase 6 (application occurrence, Note attribution, đếm theo Note) deploy qua PR #174 (`3e7fa3a`): backfill 128.650 event, dấu vân tay dữ liệu learner không đổi, audit 18/18 PASS, `STUDY_NOTE_COUNT_ENABLED=1` ([runbook P6](../../runbooks/P6_APPLICATION_OCCURRENCE_RUNBOOK.md)). Phase 7 retention membership phiên deploy qua PR #175 (`1e14106`), lần chạy đầu dọn 15.072 dòng membership, dữ liệu learner không đổi ([plan](./P7_EXECUTION_PLAN_2026-09-30.md), [runbook](../../runbooks/P7_SESSION_RETENTION_RUNBOOK.md)). Phase 8 chờ chủ sản phẩm chọn năng lực; Phase 9 chờ cửa sổ telemetry và phê duyệt riêng ([P8/P9 readiness](./P8_P9_READINESS_2026-09-30.md)).
>
> **Phase 6 preparation (2026-09-29):** [P6 execution plan](./P6_EXECUTION_PLAN_2026-09-29.md) records the code baseline (what Phase 5 already delivers for NOTE learners), nine owner decisions D6-01..D6-09, gates and work packages P6-00..P6-10/INT-04. No Phase 6 code, migration or flag exists. Phase 6 code stays on `phase6/*` branches until R0 (PR #168) is deployed; production enablement additionally needs every active learner on NOTE (new gate P5-T).
>
> **Status (2026-09-29): Phase 5 code scope is complete for R0.** Owned + logical-overlay NOTE authority (pristine reads, first-state materialization), multi-learner content topology, Connect card package, admin-wide readers and the requested Algorithm switch writer are implemented; INT-03 passes locally (1,648 backend tests with one unrelated pre-existing Flama Audio workflow failure, 507 frontend tests, production build, MySQL 8.0.40 probe matrix including 65 direct-replay/overlay/switch scenarios). Remaining Phase 5 steps are operational and need the product owner: deploy R0 (LEGACY default), then the manual NOTE canary R1 per the [runbook](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md). Nothing is committed, pushed or enabled in production by this work. Details: [P5 plan](./P5_EXECUTION_PLAN_2026-09-20.md) §2 and §5.
>
> Status (2026-09-28): Phase 0–4 and INT-01/INT-02 are closed **for pre-release development**. Phase 5 has synchronous NOTE support and readiness-gated async admission/worker/status; no production cohort or flags were changed. [Checkpoint](../../architecture/phase-5-p5-05-session-v4-contract-2026-09-22.md) records browser online/offline/reopen, rollover and empty-final recovery. The normal-rating FLOAT failure is fixed with a negotiated/frozen NOTE write-storage profile (4,107 MySQL scalar samples). **Direct REST/MCP retry now restores the original receipt**, including after later answers or a lost COMMIT acknowledgment; MySQL-specific JSON preview precision is preserved as hash-bound text. Corrected local MySQL concurrency/retry scenarios pass; the checkpoint records the exact qualification scope. Broader numeric/browser qualification, Linux deploy rehearsal, remaining P5 writer/reader/switch code and release/canary gates remain open. [Release-first plan](./P5_EXECUTION_PLAN_2026-09-20.md): finish the **full Phase 5 code scope** before R0 ships with LEGACY default; R1 is the NOTE canary. Only extended migration-data/load rehearsal is deferred.
>
> Source of truth: `docs/architecture/study-interaction-trigger-algorithm-plan.md`

Latest checkpoint (2026-09-28): Phase 5 now includes durable NOTE batch transport/worker recovery, numeric storage negotiation, exact direct REST/MCP replay, multi-learner template topology, and atomic NoteType/deck/content deletion. Shared-release template versioning, overlay enrollment/study and clone rekey remain fail-closed; P5-07/08/09/10 and the production canary remain open. Qualification includes the previously recorded **783 backend tests / 65 files**, **15 direct/numeric MySQL scenarios**, the later deck/NoteType lifecycle matrices, **268 frontend tests / 28 files**, and a production frontend build. This snapshot is committed locally on `develop`; it has not been pushed or enabled in production.
>
> Current update (2026-09-20): Phase 4 implementation through P4-10 is committed on `develop` at `263b65e`; P4-10 locally reconciled 16,424 synthetic rows with zero unexplained differences. The [P4-11 pre-release decision](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md) accepted local large-row-count and isolated VPS MySQL 8.0.46 small-cohort evidence **only as a development dependency**. The [INT-02 closeout](../../architecture/phase-4-int02-closeout-2026-09-20.md) passed fresh full tests (1,267 backend, 2 skipped; 437 frontend) and a 1,002-row disposable MySQL re-probe. **Phase 4 is closed for pre-release development.** Representative multi-user/overlay load, remaining fault matrix and operational limits are deferred to P5-09 before production enablement, not passed. Shadow flags default off and product authority remains `CardProgress`. This update supersedes historical status lines below.
>
> Latest P1/P2 closeout: [2026-09-08 execution closeout](./completed/P1_P2_EXECUTION_CLOSEOUT_2026-09-08.md) — 8 tasks completed; async admission and v3 issuance remain flag-off by default.
>
> Latest Phase 3 execution plan: [2026-09-09 Phase 3 plan](./P3_EXECUTION_PLAN_2026-09-09.md) — completed through INT-01.
>
> Latest Phase 3 closeout: [2026-09-09 Phase 3 and INT-01 closeout](./completed/PHASE_3_AND_INT_01_CLOSEOUT_2026-09-09.md) — historical delivery record; amended on 2026-09-10 to record the P4-00 correction and reclosed gate.
>
> Latest Phase 4 plan: [2026-09-10 Phase 4 execution plan](./P4_EXECUTION_PLAN_2026-09-10.md) — correction, decision, additive shadow schema, mirror, backfill, reconciliation, and rollout rehearsal through INT-02.
>
> Phase 5 update (2026-09-25): [execution plan](./P5_EXECUTION_PLAN_2026-09-20.md), [P5-00 inventory](../../architecture/phase-5-p5-00-inventory-2026-09-21.md), [physical-schema ADR](../../architecture/phase-5-authority-fence-adr-2026-09-21.md) and [projection contract](../../architecture/phase-5-p5-03-legacy-projection-contract-2026-09-21.md). Migrations 40–43 are present; migrations 44–45 and current Phase 5 changes remain uncommitted/release-unverified. Local MySQL 8.0.40 proves LEGACY batch duplicate serialization, uncertain-commit receipt handling and separate-process recovery with durable retries; NOTE/v4 async and continuous consumer remain open. Product priority is full code correctness and an early R0 release, followed by R1 canary. Full restore/large-load matrix no longer blocks R0/R1; full code paths, integration tests and MySQL NOTE rollback rehearsal still do.
>
> Phase 4 entry evidence: [2026-09-09 investigation](../../architecture/phase-4-entry-investigation-2026-09-09.md) — includes the P4-00 frozen-session blocker and current writer/storage inventory.
>
> Phase 4 current-state preflight: [2026-09-10 P4-01 report, accepted 2026-09-13](../../architecture/phase-4-current-state-preflight-2026-09-10.md) — deterministic production evidence confirms head `20260913_000038`, zero drift and complete accounting after [P4-01A](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md).

> Phase 4 identity/fan-in design: [2026-09-10 P4-02 accepted ADR](../../architecture/phase-4-progress-identity-fanin-revision-adr-2026-09-10.md) — learner/Note key, contributor vectors, generation/revision, subject-before-contributor lock order and typed dispositions.
>
> Phase 4 state/availability design: [2026-09-12 P4-03 accepted ADR](../../architecture/phase-4-algorithm-state-availability-adr-2026-09-12.md) — exact compatibility identity, lossless raw/state codecs, typed failures, availability anchors and fixed-context Card-order comparison.
>
> Phase 4 history/lifecycle design: [2026-09-12 P4-04 accepted ADR](../../architecture/phase-4-history-provenance-lifecycle-adr-2026-09-12.md) — provenance/completeness, retained scheduler facts, reset/delete/rekey fences and initializer handoff.
>
> Phase 4 joint acceptance and physical design: [2026-09-13 joint review](../../architecture/phase-4-logical-contract-joint-acceptance-2026-09-13.md) and [P4-05 accepted schema ADR](../../architecture/phase-4-physical-shadow-schema-adr-2026-09-13.md).
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

P5-06 continuation (2026-09-28): admin NoteType **and deck** purges now coordinate multiple NOTE/LEGACY learners atomically, tombstone canonical state, cancel affected sessions and preserve review/history rows. Deck purge still fails closed for a NOTE learner's installed clone node, uncovered NOTE progress and cardless canonical state. Content-delete/market-counter suites pass 20 tests, Decks + Flashcards + Marketplace pass 41 files, the content-delete MySQL probe passes 10/10 and the full authority-schema MySQL probe passes on 8.0.40 with cleanup confirmed. Shared-template/overlay/import/rekey and later P5 gates remain open.

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
| P4-01 | [Current-state preflight](./P4-01_CURRENT_STATE_PREFLIGHT.md) | none | **COMPLETED / ACCEPTED** — deterministic production refresh; head `000038`, zero drift and complete accounting |
| P4-01A | [Independent schema drift remediation](./P4-01A_SCHEMA_DRIFT_REMEDIATION.md) | P4-01 evidence | **COMPLETED / PRODUCTION VERIFIED** — migrations applied; batch contract and model/migration parity pass |
| P4-02 | [Progress identity, fan-in, revision and locking ADR](./P4-02_PROGRESS_IDENTITY_FANIN_REVISION.md) | P4-00 + P4-01 | **COMPLETED / ACCEPTED** — learner/Note identity, no-winner fan-in, generation/fence and lock matrix |
| P4-03 | [Algorithm State and availability ADR](./P4-03_ALGORITHM_STATE_AVAILABILITY.md) | P4-00 + P4-01 | **COMPLETED / ACCEPTED** — exact compatibility state/raw codecs and fixed-context per-Card availability |
| P4-04 | [History, provenance and lifecycle ADR](./P4-04_HISTORY_PROVENANCE_LIFECYCLE.md) | P4-01 | **COMPLETED / ACCEPTED** — completeness/provenance, retained facts and reset/delete/rekey fence |
| P4-05 | [Physical shadow schema design](./P4-05_PHYSICAL_SHADOW_SCHEMA.md) | P4-01A production gate + P4-02 + P4-03 + P4-04 | **COMPLETED / ACCEPTED** — exact additive tables, constraints, indexes, first-create locking and rollback design |
| P4-06 | [Additive schema and lossless mapper](./P4-06_ADDITIVE_SCHEMA_AND_MAPPER.md) | P4-05 | **COMPLETED / MERGED**; models, Alembic `000039`, strict codec/mapper, MySQL rehearsal passed |
| P4-07 | [Native and session mirror](./P4-07_NATIVE_SESSION_MIRROR.md) | P4-06 | **IMPLEMENTED / LOCAL VERIFIED — COMMITTED ON DEVELOP (`bd96abc`)**; same-transaction REST/MCP/session/worker mirror |
| P4-08 | [External and lifecycle mirror](./P4-08_EXTERNAL_LIFECYCLE_MIRROR.md) | P4-07 | **IMPLEMENTED / COMMITTED ON DEVELOP (`263b65e`)**; import/sync/reset/cutover/delete coverage with explicit dispositions |
| P4-09 | [Resumable backfill](./P4-09_RESUMABLE_BACKFILL.md) | P4-08 | **IMPLEMENTED / COMMITTED ON DEVELOP (`263b65e`)**; fenced, idempotent, restartable backfill and quarantine |
| P4-10 | [Shadow reconciliation](./P4-10_SHADOW_RECONCILIATION.md) | P4-09 | **LOCALLY COMPLETE / COMMITTED ON DEVELOP (`263b65e`)**; writer matrix, fixed-context parity and 16,424-row MySQL probe pass |
| P4-11 | [MySQL rollout rehearsal](./P4-11_MYSQL_ROLLOUT_REHEARSAL.md) | P4-10 | **CLOSED FOR PRE-RELEASE DEVELOPMENT** by [risk-scoped decision](../../architecture/phase-4-p4-11-pre-release-closeout-2026-09-20.md); representative traffic/fault/limits deferred to P5-09 before production enablement |

### Phase 5 — Authority cutover (code hoàn tất cho R0, chưa bật NOTE)

[Detailed P5-00..P5-10/INT-03 task sequence](./P5_EXECUTION_PLAN_2026-09-20.md). [INT-02 is closed](../../architecture/phase-4-int02-closeout-2026-09-20.md). The complete Phase 5 writer/reader/wire/history code matrix is implemented and INT-03 passes locally; R0 deploys with LEGACY default, R1 is the manually enrolled NOTE canary ([runbook](../../runbooks/P5_NOTE_AUTHORITY_RUNBOOK.md)). R2 contains expanded migration/data/load proof and async enablement only.

| ID | Trạng thái hiện tại | Bằng chứng / phần còn lại |
|---|---|---|
| P5-00..P5-03 | **DONE (code)** | Inventory production 2026-09-21, learner-row fence, projection encoder; additive migrations 40–45 verified 39→45 + flags-off boot on MySQL 8.0.40. Production head/backup refresh is an R0 step. |
| P5-04..P5-07 | **DONE (code)** | Sync + async v4, owned + logical-overlay NOTE with pristine/first-state, Connect snapshot/revlog/card package, multi-learner delete/template topology, admin purge, all readers incl. overlay/admin-wide with NOTE↔LEGACY equality tests. |
| P5-08 | **DONE (code)** | Requested Algorithm switch writer with synthetic registered target; typed refusals; forward-only rollback; no production initializer/route. |
| P5-09 / INT-03 | **DONE (local)** | 1,648 backend tests (1 unrelated pre-existing Flama Audio workflow failure), 507 frontend tests, build, MySQL probe matrix (65 direct-replay/overlay/switch scenarios + authority schema + batch + numeric). |
| P5-10 | **R1 DONE 2026-09-29** | R0 released; R1 moved 18/18 learners to NOTE, audit 18/18 PASS, new accounts start in NOTE ([P5 plan](./P5_EXECUTION_PLAN_2026-09-20.md) header). Async stays off. |
| P5-11 | **DONE 2026-09-30** — [NOTE production hardening](./P5-11_NOTE_PRODUCTION_HARDENING.md) | Deadlock khác learner, retry, session open O(scope), N+1 `/api/study/next`, cổng deploy so với release đang chạy; deploy PR #173 (`6472e42`), audit 18/18 PASS. |

### Phase 6 — Remove Card/Template from progress ownership (DONE trên production 2026-09-30)

[P6 execution plan](./P6_EXECUTION_PLAN_2026-09-29.md), [runbook](../../runbooks/P6_APPLICATION_OCCURRENCE_RUNBOOK.md).

| ID | Trạng thái hiện tại | Ghi chú |
|---|---|---|
| P6-00..P6-09 | **DONE** | Inventory, D6 chốt (D6-05 = B), migration 46, seam `before_flush`, đếm theo Note, lifecycle, ordinal Anki theo occurrence, `review_events.note_id`, áp dụng lặp, probe + bench MySQL |
| INT-04 | **DONE** | Backend `--all` 164 file, probe P5 + P6, bench migration quy mô production với release cũ ghi song song |
| P6-10 | **DONE** | PR #174 deploy, backfill, dấu vân tay không đổi, audit 18/18, bật `STUDY_NOTE_COUNT_ENABLED` |
| 6B | **CHƯA BẮT ĐẦU** | Versioning Template shared deck (#137) |

### Phase 7 — Retention chi tiết phiên (DONE trên production 2026-09-30)

PR #175 deploy `1e14106`; lần chạy đầu xóa 15.072 dòng membership của 160 phiên > 30 ngày, dấu vân tay dữ liệu learner không đổi ([runbook §2](../../runbooks/P7_SESSION_RETENTION_RUNBOOK.md)).

[P7 plan](./P7_EXECUTION_PLAN_2026-09-30.md), [runbook](../../runbooks/P7_SESSION_RETENTION_RUNBOOK.md). `flask study-session-retention` (dry-run mặc định): đóng phiên `open` quá hạn thành `expired` (commit muộn vẫn `410 SESSION_EXPIRED`), xóa membership phiên kết thúc > 30 ngày theo lô; không xóa event/history/progress/session/receipt.

### Phase 8 / Phase 9

[Điều kiện và bằng chứng](./P8_P9_READINESS_2026-09-30.md). `flask study-phase9-readiness` đo các cổng (đọc-only). Không bước Phase 9 nào xóa dữ liệu khi chưa có backup đã kiểm, chứng minh restore và phê duyệt riêng.

### Cross-phase integration

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| INT-01 | [Phase 0–3 integration and closeout](./completed/INT-01_PHASE_0_3_INTEGRATION.md) | toàn bộ task trên | `COMPLETED`; combined verification, duplicate-boundary audit, tracker update |
| INT-02 | [Phase 4 integration and exit gate](./INT-02_PHASE_4_INTEGRATION.md) | P4-00..P4-11 | **COMPLETED FOR PRE-RELEASE DEVELOPMENT**; [closeout](../../architecture/phase-4-int02-closeout-2026-09-20.md), full tests and zero unexplained local audit; production enablement not approved |
| INT-03 | [Phase 5 release integration gate](./P5_EXECUTION_PLAN_2026-09-20.md) | P5-00..P5-09 after INT-02 | **PASS LOCALLY (2026-09-29)**; see [P5 plan §2 G5-X](./P5_EXECUTION_PLAN_2026-09-20.md). Final production closeout follows P5-10. |

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
