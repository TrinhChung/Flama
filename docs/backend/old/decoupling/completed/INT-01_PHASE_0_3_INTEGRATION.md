# INT-01 — Phase 0–3 integration and closeout

> Scope: Cross-phase integration
>
> Priority: P0 gate
>
> Status: COMPLETED — 2026-09-09
>
> Dependency: all P0–P3 tasks
>
> Primary lane: Integration / Architecture review

## Mục tiêu

Xác minh toàn bộ Phase 0–3 hoạt động cùng nhau, không tạo duplicate boundary, security regression, clone regression hoặc documentation drift; chỉ sau task này mới cập nhật phase completion status.

## Công việc chi tiết

1. Review toàn bộ diff theo file ownership của từng task; reject unrelated refactor/schema changes.
2. Re-run searches cho:
   - duplicate ReviewEvent builders;
   - duplicate policy serializers;
   - raw rating callbacks ngoài compatibility adapter;
   - progress-affecting iframe commands;
   - session open trước composition selection;
   - client-only composition filtering;
   - physical clone simulation tests;
   - secondary progress authority/model/migration.
3. Chạy integration flows:
   - direct REST review;
   - MCP review;
   - batch/offline commit + retry/idempotency;
   - restore/quarantine/undo/mutex;
   - parent/iframe keyboard security;
   - owned composition selection;
   - real overlay source/local-added selection;
   - Algorithm unavailable/old lease compatibility.
4. Chạy audit SQLite và approved MySQL verification evidence.
5. Xác minh all output/handoff documents tồn tại và links đúng.
6. Cập nhật canonical tracker từng Phase dựa trên code/test evidence.
7. Không mark complete nếu một task bị waived mà không có explicit decision.
8. Ghi remaining debt thành task ID mới; không giấu trong prose.

## Output đầu ra bắt buộc

- Integration review report.
- Combined test command/results table.
- Search/audit evidence cho duplicate/security/progress authority.
- Phase 0, 1, 2, 3 exit-gate checklist có pass/fail/evidence link.
- Updated canonical tracker và documentation index.
- Explicit Phase 4 go/no-go recommendation; không tự authorize schema.

## Acceptance criteria

- P2 security containment vẫn giữ sau mọi integration.
- REST/MCP/batch parity và external conflict contract pass.
- Frontend same-tick/restore/action tests pass.
- Composition selection thật sự precedes and controls session.
- Real logical overlay exit tests pass, source không mutate.
- Audit có MySQL-safe evidence và no blocking unknowns, hoặc status vẫn Partial.
- `CardProgress` vẫn là sole authority và migrations không đổi.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
python scripts/run_tests.py --changed
```

Full suite chỉ chạy nếu đây là CI/pre-release gate:

```text
python scripts/run_tests.py --all
```

## Rollback

Nếu integration phát hiện blocker, revert task gây regression hoặc tắt feature flag tương ứng và giữ phase `Partial`. Không sửa test/docs để hợp thức hóa behavior lỗi.

## Không làm trong task này

- Không implement Phase 4.
- Không tạo schema/migration.
- Không merge unrelated cleanup.
- Không mark completion dựa trên test count mà thiếu exit-gate evidence.

## Handoff — 2026-09-09

- Task ID: `INT-01`
- Primary outcome: Phase 0–3 integration gates are closed with exact composition selection, logical-overlay proof, frozen restore/commit validation, and unchanged progress authority.
- Files reviewed: all Phase 3 backend/frontend/test changes plus the Phase 0–2 compatibility boundaries and canonical tracker.
- Contract checks: no premature session open, no client-only composition authority, no physical clone proof, no secondary progress model, and no model/migration diff.
- MySQL evidence: reused the approved signed SELECT-only P0-03 bundle; no credentials, DDL, DML, startup maintenance, or fresh production write was used.
- Combined verification: focused Study backend/frontend, Decks/Flashcards backend, TypeScript typecheck, lint, mapping coverage, real overlay integration, and final full-suite execution.
- Rollback path: disable admission for new Phase 3 sessions while retaining additive/legacy readers and the overlay invariant tests; return tracker status to Partial if any gate regresses.
- Remaining debt: Phase 4 physical progress/state/application design remains deferred and requires separate schema/migration authorization.
- Phase 4 recommendation: architecture planning may proceed; physical schema or authority cutover is **not authorized** by this closeout.
