# P3-06 — Real overlay-only composition exit gate

> Phase: 3
>
> Priority: P0 gate
>
> Status: COMPLETED — 2026-09-09
>
> Dependency: P3-01 through P3-05 and P3-07
>
> Primary lane: Integration testing

## Mục tiêu

Thay physical-copy clone simulation bằng end-to-end proof dùng `DeckInstall` logical overlay thật và chứng minh mọi effective Card/application context resolve unambiguously.

## Bối cảnh

`tests/test_study_composition_exit_gate.py` hiện tạo thêm một physical Card để mô phỏng clone. Đây không phải mô hình production: ordinary installed deck dùng source Notes/Cards qua overlay, trong khi local-added Notes có local Cards/Templates.

## Phạm vi file dự kiến

- `tests/test_study_composition_exit_gate.py`
- `tests/test_study_session_api.py`
- clone/install fixtures gần nhất
- `frontend/src/features/study/pages/StudyPage.test.tsx`
- session restore tests
- docs tracker khi gate đạt

## Công việc chi tiết

1. Tạo source user/deck/NoteType/Templates/Notes/Cards.
2. Publish/install bằng service/model path thật để tạo `DeckInstall` logical overlay.
3. Assert install không copy ordinary source Notes/Cards.
4. Discover compositions từ installed local deck context.
5. Chọn composition và mở session; assert source Cards resolve đúng.
6. Thêm local-added Note/Card dùng installed-copy Template và assert cùng logical deck vẫn resolve đúng context.
7. Test local field/template override hoặc fork case hiện được support mà không mutate source.
8. Test unauthorized installer/source user cross-access.
9. Test multiple Templates, repeated/equivalent compatibility contexts và selected query limit.
10. Test frontend pre-open selection + reload frozen session.
11. Remove hoặc đổi tên mọi “clone simulation” không còn là proof.
12. Ghi Phase 3 evidence chỉ sau khi full exit matrix pass.

## Output đầu ra bắt buộc

- Real `DeckInstall` overlay integration fixture.
- Backend exit-gate tests cho source + local-added contexts.
- Frontend selection/restore integration tests.
- Assertions no physical source Card copy/no source mutation.
- Exit-gate evidence summary link từ canonical tracker.
- Handoff report.

## Acceptance criteria

- Không test nào dùng second physical source-card copy làm bằng chứng overlay.
- Discovery, authorization, session query, snapshot và restore cùng dùng một composition contract.
- Source and local-added Cards đều học được trong correct context.
- No source Note/Card mutation.
- Unauthorized/out-of-scope selection fail closed.
- Phase 3 exit gate wording khớp behavior thực tế.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
```

## Rollback

Tests phản ánh invariant production không được xóa để hợp thức hóa regression. Nếu implementation rollback, Phase 3 phải quay về `Partial`, không đổi expected test thành physical clone.

## Không làm trong task này

- Không thay clone model.
- Không seed production data.
- Không tạo Phase 4 progress tables.
- Không mark Phase 3 complete nếu chỉ một happy path pass.

## Handoff — 2026-09-09

- Task ID: `P3-06`
- Primary outcome: a real publish/install `DeckInstall` logical-overlay path proves source and local-added composition discovery/open behavior without physical source Card copies.
- Files changed: `tests/test_study_behavior_acceptance_baseline.py`, composition/session exit-gate tests, and frontend selection/restore tests.
- Contract verified: discovery, authorization, query, snapshot, restore, and commit use the same context-qualified selection contract.
- Assertions: ordinary source Notes/Cards are not copied or mutated; installed source and local-added Cards resolve through their respective effective contexts.
- Rollback path: if runtime is rolled back, keep this production-invariant test and return Phase 3 to Partial.
- Known limitations: no production data was seeded or mutated; MySQL evidence remains the signed read-only Phase 0 bundle.
- Follow-up task IDs: `INT-01` — completed.
