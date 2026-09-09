# P3-02 — Clone-aware composition discovery and query-first filtering

> Phase: 3
>
> Priority: P0
>
> Status: COMPLETED — 2026-09-09
>
> Dependency: P3-01
>
> Primary lane: Backend Study / Share overlay

## Mục tiêu

Dùng cùng một clone-aware effective scope resolver cho composition discovery và session card query, áp dụng selection trong query trước limit để owned/overlay/local-added contexts nhất quán.

## Bối cảnh

- Installed shared deck có local Deck/NoteType/Template copies nhưng source Cards vẫn là logical overlay pointers.
- Composition service hiện có thể suy ra local copied Template IDs, trong khi session dùng source Card/Template IDs.
- Session hiện fetch tới limit rồi mới filter composition, gây empty/biased session.

## Phạm vi file dự kiến

- `app/services/study_composition_service.py`
- `app/services/study_session_service.py`
- clone scope resolver/repository hiện có
- `app/services/share/overlay.py`
- `app/services/share/install.py`
- `app/services/share/note_types.py`
- `tests/test_study_composition_service.py`
- `tests/test_study_session_api.py`

## Công việc chi tiết

1. Trace effective cards cho:
   - owned deck;
   - recursive owned deck;
   - installed overlay source Cards;
   - local-added Notes/Cards trong installed deck;
   - mixed source/local logical deck.
2. Chọn một resolver/query seam dùng chung cho discovery và session.
3. Compatibility composition identity phải resolve theo effective application context, không giả định một physical Card có một global clone composition.
4. Map source Template vs installed local Template presentation context rõ ràng theo contract P3-07.
5. Apply composition predicate trong database/effective scope query trước `MAX_SESSION_CARDS`.
6. Preserve due ordering, timezone/day boundary và suspension/burial filters hiện có; không hand-roll scheduler query.
7. Không copy source Notes/Cards để làm query dễ hơn.
8. Add tests cho limit fairness: eligible selected composition nằm sau các card của composition khác vẫn phải được lấy đúng.
9. Add tests cho source/local mixture và clone-local override context.

## Output đầu ra bắt buộc

- Shared clone-aware composition scope resolver/query seam.
- Query-first filtering implementation.
- Source/local/template/application identity mapping document ngắn.
- Tests cho owned, overlay source, local-added và mixed contexts.
- Query count/ordering regression evidence.
- Handoff report.

## Acceptance criteria

- Discovery options và session query dùng cùng effective scope semantics.
- Selected overlay composition trả đúng source Cards mà không dùng local Template ID sai.
- Limit áp dụng sau composition eligibility.
- No source mutation và no physical clone fallback.
- Due ordering/day-boundary behavior không đổi.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
```

## Rollback

Có thể route query về compatibility resolver cũ sau feature flag, nhưng giữ authorization P3-01. Không materialize copied Cards khi rollback.

## Không làm trong task này

- Không thay overlay install model.
- Không tạo applied binding table.
- Không rewrite scheduler/due logic.
- Không implement frontend flow.

## Handoff — 2026-09-09

- Task ID: `P3-02`
- Primary outcome: discovery and session authorization now derive from the same effective card query, including owned, installed-source overlay, and installed-local contexts.
- Files changed: `app/services/study_composition_service.py`, `app/services/study_session_service.py`, route wiring, and composition/session/overlay tests.
- Contract/API behavior changed: context-qualified installed composition IDs distinguish source and local applications; the composition predicate is applied before `MAX_SESSION_CARDS`.
- Tests added or updated: recursive mixed scope, overlay source/local discovery, out-of-scope rejection, query-limit fairness, and real install coverage.
- Rollback path: disable new-session admission; do not materialize or copy overlay Cards.
- Known limitations: due ordering remains owned by the existing study query/scheduler, and Phase 3 does not add a reusable definition store.
- Follow-up task IDs: `P3-03`, `P3-06`, `INT-01` — completed.
