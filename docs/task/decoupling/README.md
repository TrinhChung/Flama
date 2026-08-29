# Phase 0–3 Decoupling Task Backlog

> Status: ACTIVE backlog; Phase 0 closed, next task P1-01.2
>
> Source of truth: `docs/architecture/study-interaction-trigger-algorithm-plan.md`
>
> Progress review: `docs/architecture/decoupling-progress-review-2026-08-29.md`
>
> Latest Phase 0 gate review/handoff: [`P0_PHASE_REVIEW_HANDOFF_2026-08-29.md`](./P0_PHASE_REVIEW_HANDOFF_2026-08-29.md) — **GO; P0-01 through P0-04 COMPLETED**.
>
> Next execution plan: [`PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md`](./PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md) — close P0-03 first, then P1-01 as the first runtime refactor.
>
> Reviewed detailed backlog: [`REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md`](./REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md) — 18 remaining parent tasks with execution slices, required outputs and gates.
>
> Scope boundary: chỉ đóng các phần còn thiếu của Phase 0–3. Không tạo model, migration, progress store hoặc physical Template/NoteType schema mới.

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

1. `CardProgress` tiếp tục là progress authority duy nhất trong Phase 0–3.
2. Không thêm hoặc sửa model/migration phục vụ Phase 4.
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

Historical dependency note: `P2-01` has been merged, but the current reviewed execution gate requires P0-03 to close before any remaining Phase 1–3 runtime change. After that gate, use the wave ordering in `REVIEWED_DETAILED_EXECUTION_BACKLOG_2026-08-29.md`; tasks touching the same files must remain sequential.

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
| P1-01 | [Canonical native review transaction](./P1-01_CANONICAL_REVIEW_TRANSACTION.md) | P0-04 | một command/core cho REST, MCP, batch; parity tests |
| P1-02 | [External progress revision/conflict contract](./P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md) | P1-01 | contract cho Anki/import/Connect/cutover conflicts |
| P1-03 | [ReviewEvent provenance and payload hardening](./P1-03_REVIEW_EVENT_PROVENANCE.md) | P1-01 | canonical native/external provenance, bounded payloads |
| P1-04 | [Algorithm executable and decoder retirement lifecycle](./P1-04_ALGORITHM_VERSION_RETIREMENT.md) | P1-01 | support matrix, fail-closed retention policy, tests |

### Phase 2 — Built-in Interaction and Trigger compatibility

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P2-01 | [Iframe `host_command` containment](./completed/P2-01_IFRAME_HOST_COMMAND_CONTAINMENT.md) | none | đóng progress side channel và forged-message tests |
| P2-02 | [Frontend session mutation mutex](./P2-02_FRONTEND_SESSION_MUTEX.md) | P2-01 | atomic operation guard và same-tick tests |
| P2-03 | [Restore validation and quarantine](./P2-03_RESTORE_VALIDATION_QUARANTINE.md) | P2-01 | strict validator, stable quarantine reasons, tests |
| P2-04 | [Semantic ReviewInteraction contract](./P2-04_SEMANTIC_INTERACTION_CONTRACT.md) | P2-01 | một semantic callback, raw rating confined to adapter |
| P2-05 | [Trusted keyboard UX and threat model](./P2-05_TRUSTED_KEYBOARD_UX.md) | P2-01 + P2-04 | threat model, safe implementation hoặc documented no-bridge |
| P2-06 | [Built-in Trigger Runtime design checkpoint](./P2-06_TRIGGER_RUNTIME_DESIGN.md) | P1-03 + P2-04 | approved responsibility/transaction/idempotency design |
| P2-07 | [Wire v3 and legacy v2 lease policy](./P2-07_WIRE_V3_LEGACY_V2_POLICY.md) | P1-04 + P2-03 + P2-06 | versioned contract plan/implementation và compatibility tests |

### Phase 3 — Composition/StudyMode compatibility responsibility

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| P3-01 | [Exactly-one composition session API](./P3-01_COMPOSITION_SESSION_API.md) | P1/P2 correctness + P3-05 + P3-07 | authorized single selection và compatibility fallback |
| P3-02 | [Clone-aware composition discovery and query-first filtering](./P3-02_CLONE_AWARE_COMPOSITION_QUERY.md) | P3-01 | một resolver cho owned/overlay/local-added contexts |
| P3-03 | [Pre-session StudyMode selection UI](./P3-03_PRE_SESSION_STUDYMODE_UI.md) | P3-01 + P3-05 | selector trước session và request mang selection |
| P3-04 | [Frozen composition restore and stale handling](./P3-04_COMPOSITION_FREEZE_RESTORE.md) | P3-01 + P3-03 | immutable snapshot, reload/recovery behavior |
| P3-05 | [Mixed-NoteType scope policy](./P3-05_MIXED_NOTETYPE_SCOPE_POLICY.md) | Phase 0 evidence | approved ADR và API/UI rule |
| P3-06 | [Real overlay-only composition exit gate](./P3-06_OVERLAY_COMPOSITION_EXIT_GATE.md) | P3-01..P3-05 + P3-07 | integration proof dùng `DeckInstall` thật, không clone giả |
| P3-07 | [Applied composition and binding contract](./P3-07_APPLIED_COMPOSITION_BINDING_CONTRACT.md) | Phase 0 evidence | approved responsibility/identity/lifecycle contract, no schema |

### Cross-phase integration

| ID | Task | Dependency | Output chính |
|---|---|---|---|
| INT-01 | [Phase 0–3 integration and closeout](./INT-01_PHASE_0_3_INTEGRATION.md) | toàn bộ task trên | combined verification, duplicate-boundary audit, tracker update |

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
python scripts/run_tests.py --changed
```

Với browser security/keyboard testing, bắt buộc dùng Chrome profile riêng theo `AGENTS.md`; không dùng profile cá nhân của người dùng.

## 7. Điều kiện mở Phase 4

Phase 4 chỉ được xem xét khi:

- mọi task P0–P3 và `INT-01` đạt acceptance gate;
- audit MySQL trả zero blocking anomaly hoặc mỗi anomaly có disposition được duyệt;
- composition logical overlay có proof thật;
- không còn progress-affecting untrusted iframe path;
- tracker canonical được cập nhật theo code/test evidence;
- có approval riêng cho schema/migration.
