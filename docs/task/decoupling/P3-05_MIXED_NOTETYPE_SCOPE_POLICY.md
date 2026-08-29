# P3-05 — Mixed-NoteType scope policy

> Phase: 3
>
> Priority: P0 decision
>
> Status: TODO
>
> Dependency: Phase 0 evidence
>
> Primary lane: Product architecture / Backend + Frontend contract

## Mục tiêu

Chốt behavior khi recursive Deck scope chứa nhiều NoteType trước khi selector/API mới được triển khai rộng.

## Bối cảnh

Deck chỉ là entry scope/default hint, không phải universal composition owner. Production baseline từng ghi nhận ít nhất một recursive scope có hai NoteTypes; không được giả định mọi deck đồng nhất.

## Công việc chi tiết

1. Dùng P0 audit để xác nhận data distribution và representative cases.
2. So sánh tối thiểu ba lựa chọn:
   - group compositions theo NoteType trong một màn;
   - chọn NoteType trước, rồi chọn StudyMode;
   - hạn chế session còn một NoteType và yêu cầu user chọn scope.
3. Đánh giá từng lựa chọn theo:
   - UX/number of clicks;
   - queue semantics và fairness;
   - API identity/cardinality;
   - clone overlay source/local mixture;
   - restore/session freeze;
   - old-client fallback.
4. Chốt default behavior cho single NoteType và empty/mixed cases.
5. Định nghĩa API response grouping/order và stable IDs.
6. Định nghĩa frontend states và error/retry flow.
7. Ghi decision trong ADR và update P3-01/P3-03 contract nếu cần.

## Output đầu ra bắt buộc

- ADR có evidence, alternatives, trade-offs và quyết định chính thức.
- API composition grouping/cardinality contract.
- Frontend interaction flow/wireframe mức logic, không cần redesign visual.
- Compatibility/default rules.
- Acceptance examples cho owned và installed overlay decks.

## Acceptance criteria

- Không assumption “một Deck = một NoteType” còn ẩn trong contract.
- Quyết định xác định rõ selected progress subject set và composition eligibility.
- Logical overlay/local-added cases được xét.
- Old-client fallback không tạo ambiguous mixed session.
- Không cần schema/migration.

## Verification

- Review đối chiếu audit P0, `study_composition_service.py`, deck tree query và clone scope resolver.
- Nếu không có production authorization, dùng repo/test evidence và đánh dấu distribution là needs verification.

## Rollback

ADR có thể được supersede trước implementation. Sau rollout, behavior phải feature-flagged nếu cần đổi mà vẫn có active sessions.

## Không làm trong task này

- Không implement UI/backend ngoài prototype cần chứng minh contract.
- Không thêm Deck-owned StudyMode table.
- Không thay deck tree model.
