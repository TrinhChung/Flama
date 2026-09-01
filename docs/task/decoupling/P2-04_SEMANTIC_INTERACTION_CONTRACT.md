# P2-04 — Semantic ReviewInteraction contract

> Phase: 2
>
> Priority: P1
>
> Status: TODO
>
> Dependency: P2-01
>
> Primary lane: Frontend Study UI

## Mục tiêu

Hoàn tất reusable four-button Interaction boundary: visual component chỉ emit một semantic `ReviewAction`; raw scheduler rating chỉ tồn tại trong compatibility adapter.

## Bối cảnh

`ReviewInteractionControls` hiện nhận đồng thời `onAnswer(rating)` và `onReviewAction(action)` và có thể gọi cả hai. `StudyBottomBar` vẫn public raw rating callback.

## Phạm vi file dự kiến

- `frontend/src/features/study/interactions/ReviewInteractionControls.tsx`
- `frontend/src/features/study/interactions/ReviewInteractionControls.test.tsx`
- `frontend/src/features/study/interactions/reviewInteraction.ts`
- `frontend/src/features/study/components/StudyBottomBar.tsx`
- `frontend/src/features/study/pages/StudyPage.tsx`
- integration tests tương ứng

## Công việc chi tiết

1. Audit mọi caller của ReviewInteraction controls/bottom bar.
2. Chọn một discriminated semantic callback type.
3. Remove `onAnswer` khỏi reusable visual component public API.
4. Confine Action → legacy rating mapping vào một named compatibility adapter.
5. Interval preview chỉ là display data, không phải action identity.
6. Một gesture chỉ emit đúng một semantic action.
7. Giữ reveal gating, disabled state, local undo và busy semantics.
8. Bảo toàn tuyệt đối:
   - button order;
   - labels;
   - colors/gradient;
   - spacing/size;
   - icons;
   - keyboard hints;
   - responsive layout.
9. Add component/integration tests cho exact action mapping và single emission.

## Output đầu ra bắt buộc

- Reusable component API chỉ có semantic action callback.
- Explicit compatibility rating adapter.
- Updated callers và tests.
- Zero-visual-regression evidence/snapshots hiện có.
- Handoff report.

## Acceptance criteria

- Không raw rating callback trong public Interaction component.
- Mỗi click/key action map đúng một lần tới compatibility rating.
- Alternate Interaction có thể dùng contract mà không import scheduler implementation.
- Existing visual/interaction tests xanh.
- Không CSS/layout change ngoài incidental type wiring.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

## Rollback

Adapter cho phép revert call sites mà không đổi backend/wire. Không giữ song song hai callbacks sau merge.

## Không làm trong task này

- Không redesign Study controls.
- Không sửa iframe shortcut.
- Không thêm new Interaction type.
- Không đổi scheduler algorithm.
