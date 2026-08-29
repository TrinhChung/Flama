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
>
> Preparation status: repository evidence and blocking questions collected on 2026-08-29; P0-03 evidence is now available for the decision review.

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

## Pre-decision evidence inventory — 2026-08-29

This inventory is preparation only. It must not be treated as the ADR decision or as production distribution evidence.

### Current executable behavior

| Surface | Current behavior | Contract risk to resolve |
|---|---|---|
| Scope composition endpoint | `list_available_compositions_for_scope` discovers distinct NoteTypes from owned Notes in a recursive deck scope, then emits one compatibility composition per Template. | Ordering between NoteTypes is not explicitly stable, and the owned-note filter does not represent logical-overlay source cards. |
| Empty owned deck | Falls back to `Deck.note_type_id` when the deck belongs to the user. | The fallback can advertise Templates even when the scope has no eligible cards. |
| Session open API | Accepts up to 100 non-empty `composition_ids`; absent/invalidly shaped input becomes no filter. | “Exactly one”, grouped multi-select, unknown IDs, duplicates and empty selection are not contractually defined. |
| Session snapshot | Builds the composition dictionary from cards actually included in the frozen snapshot. | This is more authoritative than the discovery endpoint for overlay cards, but the relationship between discovery and open is unstated. |
| React Study page | Opens the whole deck session, then `compositionFilter` filters the local session view; selector exposes “Tất cả”. | Selection currently changes the local view rather than proving that the server froze only the selected progress-subject set. |
| Compatibility identity | `comp:notetype:{note_type_id}:template:{template_id}`. | Stable for current rows, but source/local identity and future application occurrences are not encoded. |

### Confirmed test/repository evidence

- Existing session tests prove a self-contained composition dictionary and basic scope endpoint response, but do not cover recursive mixed-NoteType ordering/cardinality.
- Clone session tests prove source Card identity with local scheduler deck and no source Note mutation.
- Overlay cutover guarantees logical source Note/Card identity; learner installs do not own copied Note/Card trees.
- Current publishing helpers still reject some deck publication shapes whose notes use multiple NoteTypes, but recursive parent scope can still contain heterogeneous child decks; publication validation is not a valid global Study assumption.
- Production frequency and representative single/mixed/empty distributions remain unverified until P0-03 evidence is accepted.

### Questions the ADR must answer

1. Does one session authorize exactly one compatibility composition, one NoteType group, or an ordered set of compositions?
2. If “all” remains supported, what is the deterministic inter-NoteType queue/fairness rule?
3. Is the selected progress-subject set cards, notes, or logical source cards plus local-added cards, and how is it frozen?
4. What are the stable grouping and ordering keys when Template positions collide across NoteTypes?
5. For an installed overlay, does the API expose source NoteType identity, installed/local NoteType identity, or both with an explicit mapping?
6. How are locally added notes/cards combined with release-pinned source cards without mutating or shadowing source identity?
7. Must unknown, duplicate, empty and cross-scope composition IDs fail closed, and with which bounded error codes?
8. What does an old client that omits selection receive for a mixed scope: deterministic default, explicit conflict, or restricted single-NoteType session?
9. Should an empty scope return zero compositions, a configuration hint, or a non-selectable default composition?
10. Does switching the UI selector require opening a new server session, or may it filter an already frozen multi-composition session?

### Evidence required before decision

- P0-03 distribution counts for empty, single-NoteType and mixed recursive scopes, including overlay/local-added cases.
- Deterministic examples for owned parent/child decks, installed overlays and old-client requests.
- API cardinality/error matrix agreed with P3-01 and frozen-snapshot behavior agreed with P3-04.
- Frontend flow agreed with P3-03 without treating the current “Tất cả” control as approved product policy.

## Verification

- Review đối chiếu audit P0, `study_composition_service.py`, deck tree query và clone scope resolver.
- Nếu không có production authorization, dùng repo/test evidence và đánh dấu distribution là needs verification.

## Rollback

ADR có thể được supersede trước implementation. Sau rollout, behavior phải feature-flagged nếu cần đổi mà vẫn có active sessions.

## Không làm trong task này

- Không implement UI/backend ngoài prototype cần chứng minh contract.
- Không thêm Deck-owned StudyMode table.
- Không thay deck tree model.
