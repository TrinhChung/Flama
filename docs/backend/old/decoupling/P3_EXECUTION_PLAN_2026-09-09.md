# Kế hoạch triển khai Phase 3 — 2026-09-09

> Status: COMPLETED — Phase 3 and INT-01 closed on 2026-09-09
>
> Baseline: branch `develop`, commit `bf3942a`; worktree sạch tại thời điểm lập kế hoạch
>
> Entry gate: Phase 0, Phase 1 và Phase 2 đã hoàn tất
>
> Scope boundary: P3-05, P3-07, P3-01 đến P3-06 và handoff sang INT-01; không tạo model, migration, progress store hoặc full-copy clone behavior

Tài liệu này là execution plan mới nhất cho Phase 3. Acceptance criteria trong từng task file vẫn là điều kiện bắt buộc; kế hoạch này chỉ chốt thứ tự, delivery slices, file ownership và gate giữa các task.

> Completion note: P3-05/P3-07 decisions were accepted, P3-01 through P3-04 runtime work was implemented, P3-06 passed with a real logical-overlay install path, and INT-01 closed the combined verification. See [Phase 3 and INT-01 closeout](./completed/PHASE_3_AND_INT_01_CLOSEOUT_2026-09-09.md).

## 1. Kết quả cần đạt

Phase 3 hoàn tất khi learner chọn đúng một StudyMode/applied composition trước khi mở session, backend xác thực selection trong effective owned/overlay scope, session freeze selection đó trong toàn lease, và real `DeckInstall` logical-overlay flow chứng minh source Cards cùng local-added Cards đều resolve không mơ hồ mà không copy hoặc mutate source data.

Các invariant giữ nguyên:

1. `CardProgress` tiếp tục là authority duy nhất trong Phase 3.
2. Existing `Template`/`Card` identity tiếp tục là compatibility authority.
3. Shared deck tiếp tục là `logical_overlay`; không tạo physical copies để đơn giản hóa composition query.
4. New session fail closed với selection stale, inaccessible, out-of-scope hoặc ambiguous.
5. Active session dùng frozen snapshot, không re-resolve latest definition khi reload.
6. Active Study screen giữ zero visual regression; UI mới chỉ nằm ở pre-session launch state.
7. Không có DDL/Alembic hoặc physical reusable-template/application schema trong Phase 3.

## 2. Ground truth và khoảng trống trước triển khai

| Evidence | Trạng thái tại baseline | Hệ quả đối với kế hoạch |
|---|---|---|
| P0–P2 closeout | Hoàn tất tại `bf3942a`; async batch admission và wire-v3 issuance vẫn flag-off mặc định | Phase 3 được phép bắt đầu nhưng không thay các contract đã đóng |
| Mixed scope production | Report read-only ngày 2026-08-24 ghi nhận một recursive Deck scope chứa hai NoteTypes | P3-05 là real product decision, không phải edge case giả định |
| Current signed P0-03 bundle | Bundle ngày 2026-08-29 có 9 NoteTypes, 7 single-template, 2 multi-template, 3 logical installs, 39 installed source cards và 0 overlay ambiguity; bundle không chứa category đếm mixed recursive scopes | P3-05.0 phải refresh/reconcile targeted SELECT-only evidence trước khi ADR chuyển `Accepted` |
| Composition discovery | `list_available_compositions_for_scope` chỉ tìm owned `Note` rows; empty owned deck fallback sang `Deck.note_type_id`; mixed NoteType order chưa explicit | Discovery chưa cùng effective-scope semantics với session query |
| Session open | Route nhận optional `composition_ids` list; service lấy tối đa session cards rồi mới lọc | Cardinality/authorization chưa chặt và selected queue có thể empty/biased |
| React launch | `useStudySession` mở session trước; `StudyPage`/engine dùng `compositionFilter` để lọc local; selector có lựa chọn “Tất cả” | UI hiện tại chưa phải learner-selection authority |
| Overlay resolver | Session query đã có `CloneDeckScope` và logical-overlay source/local-added query path | P3-02 phải tái sử dụng seam này cho discovery thay vì tạo resolver song song |
| Exit-gate test | `test_study_composition_exit_gate.py` dùng physical second Card để mô phỏng clone | P3-06 phải thay bằng publish/install `DeckInstall` thật |
| Current identity model | `Template` thuộc đúng một `NoteType`; `Card` unique theo `(note_id, template_id)`; `FieldDef.id` là stable field identity | P3-07 phải là logical contract, không được giả vờ repeated application đã có physical representation |

## 3. Thứ tự triển khai

```text
D0 shared evidence freeze
  -> P3-05 mixed-NoteType policy
  -> P3-07 applied composition/binding contract
  -> G3-D decision consistency gate
  -> P3-01 exactly-one session API
  -> P3-02 clone-aware query-first resolver
  -> P3-03 pre-session StudyMode UI
  -> P3-04 frozen composition restore
  -> P3-06 real overlay-only exit gate
  -> INT-01
```

P3-05 đi trước P3-07 vì P3-07 cần cardinality/selection policy để chốt application occurrence semantics. Hai task có thể dùng chung evidence inventory, nhưng không được phê duyệt độc lập nếu terminology, compatibility ID hoặc snapshot material còn mâu thuẫn.

P3-01 và P3-02 được review theo hai task riêng nhưng nên nằm trong cùng backend rollout gate: không bật frontend pre-session flow khi discovery và session query chưa dùng cùng effective-scope semantics.

## 4. Wave D — quyết định kiến trúc

### D0 — Shared evidence freeze

| Slice | Công việc | Output bắt buộc |
|---|---|---|
| D0.1 Data reconciliation | Đối chiếu report 2026-08-24 với signed bundle 2026-08-29; chạy targeted SELECT-only query nếu authorized environment khả dụng để đếm empty/single/mixed recursive scopes và owned/overlay/local-added cases | Redacted evidence table có timestamp/source; không credential, DDL hoặc DML |
| D0.2 Runtime map | Freeze call graph từ scope endpoint, `_build_study_scope_query`, `CloneDeckScope`, `open_study_session`, snapshot, restore và client-only filter | Một authority map chỉ rõ discovery/query/snapshot/UI owner hiện tại |
| D0.3 Scenario fixtures | Mô tả deterministic examples cho owned single/mixed tree, installed source overlay, local-added card, empty scope, stale ID và old client | Scenario matrix được P3-05 và P3-07 cùng tham chiếu |
| D0.4 Vocabulary | Chốt nghĩa logic của definition, version, input, application occurrence, effective composition và compatibility projection | Không dùng `Template`, `StudyMode` và composition như từ đồng nghĩa |

Gate D0: evidence production mới phải được gắn đúng mức tin cậy. Nếu không có authorized current MySQL read, ADR phải ghi rõ mixed-scope count là historical evidence và không được tuyên bố là current signed P0-03 fact.

### P3-05 — Mixed-NoteType scope policy

Hướng đề xuất để đưa vào ADR review:

- Một recursive scope trả các eligible compositions được group theo NoteType trên cùng pre-session screen.
- Learner vẫn chọn đúng một composition/application; group chỉ là presentation, không phải multi-select.
- Chỉ auto-resolve khi toàn effective scope có đúng một eligible composition.
- Khi có từ hai eligible compositions trở lên, kể cả trong một NoteType, client phải chờ explicit selection.
- Old client bỏ selection chỉ được tiếp tục khi có đúng một option; trường hợp ambiguous trả typed `COMPOSITION_SELECTION_REQUIRED`, không chọn default/first ngầm.
- Empty scope trả zero eligible options và recoverable empty/configuration state; không advertise Template không có eligible Card và không mở empty session giả.
- Group order dùng deterministic `(normalized NoteType name, note_type_id)`; composition order dùng `(Template.position, template_id)`. `template_id` là tie-break bắt buộc vì production từng có duplicate positions.
- Stable identity nằm ở ID fields; display name và sort order không tham gia authorization.

Các lựa chọn “NoteType trước rồi StudyMode” và “buộc user thu hẹp Deck scope” vẫn phải được ADR ghi cùng trade-off. Hướng grouped-one-screen chỉ được chuyển thành `Accepted` sau khi scenario matrix chứng minh không làm mơ hồ queue semantics, overlay/local-added mapping và restore.

Deliverables:

1. `docs/architecture/mixed-notetype-study-scope-policy-2026-09-09.md`.
2. API response cardinality/grouping/order contract và empty/error matrix.
3. Pre-session state flow ở mức logic, không redesign active Study UI.
4. Owned/overlay/old-client acceptance examples.
5. Update P3-05 task handoff; runtime change ghi `none`.

Gate P3-05:

- Không còn assumption “Deck = một NoteType”.
- Mọi zero/one/many case có một deterministic outcome.
- Mixed scope không mở session trước selection.
- Old client không tạo ambiguous mixed session.
- Decision không yêu cầu schema.

### P3-07 — Applied composition và binding contract

Delivery slices:

| Slice | Công việc | Output bắt buộc |
|---|---|---|
| P3-07.1 Responsibility | Ghi current/future owner cho Note, NoteType, Template, Card, progress, definition, application và binding | Responsibility table phân biệt runtime fact với target contract |
| P3-07.2 Identity/cardinality | Định nghĩa logical IDs cho reusable definition, immutable version, application occurrence, input và effective compatibility composition | Repeated application biểu diễn được mà không tạo progress mới hoặc duplicate current Card |
| P3-07.3 Binding | Phase-3 minimum là direct required/optional input binding tới stable `FieldDef.id`; field name chỉ là legacy authoring/compile input | Validation/error matrix cho missing, wrong NoteType, deleted field, duplicate cardinality, incompatible type và unresolved name |
| P3-07.4 Lifecycle | Chốt create/apply/pin/fork/edit/unpublish/detach/delete cho author, installer và private fork | Active/historical session cùng progress không bị mô tả như bị xóa theo Template lifecycle |
| P3-07.5 Compatibility | Map current Template row thành một compatibility application; mô tả source/local overlay, import ordinal, Anki/Connect và no-card-regeneration rules | Compatibility projection rules; không claim unsupported release/template guarantee |
| P3-07.6 Freeze contract | Liệt kê exact effective material P3-04 phải freeze trong existing JSON snapshot | Versioned snapshot fields/fingerprints và fail-closed availability rules |
| P3-07.7 Deferral | Tách table layout, FK/index, backfill, retention và physical migration sang Phase 4+ | Explicit deferred-question register |

Deliverable chính: `docs/architecture/applied-composition-binding-contract-2026-09-09.md` ở trạng thái `Proposed`, sau review mới chuyển `Accepted`.

Gate P3-07:

- Compatibility ID hiện tại `comp:notetype:{note_type_id}:template:{template_id}` vẫn hợp lệ cho legacy Template application.
- Target contract có occurrence identity riêng cho repeated application nhưng Phase 3 không giả lập nó bằng duplicate Card.
- Binding identity dựa trên `FieldDef.id`, không dựa vào mutable field name.
- Installed definition pin version; edit tạo private fork theo copy-on-write contract.
- Active session freeze đủ identity/version/material để không re-resolve latest.
- Không có model/migration diff.

### G3-D — Decision consistency gate

P3-01 chỉ được mở khi:

1. P3-05 và P3-07 đều `Accepted`.
2. Cùng một exactly-one rule, terminology và compatibility ID grammar xuất hiện trong cả hai ADR.
3. P3-01 error matrix không còn câu hỏi product mở.
4. P3-03 launch states và P3-04 snapshot fields có thể triển khai từ contract mà không phát minh thêm policy.
5. P3-06 scenario matrix có owned source, installed source overlay và local-added contexts.

## 5. Wave B — backend selection authority

### P3-01 — Exactly-one composition session API

1. Thêm canonical request field `composition_id`; parse/validate ở API boundary.
2. Tạo typed resolved-selection object; session service không nhận raw arbitrary list.
3. Validate identity, scope membership và user access trước khi tạo session.
4. Legacy `composition_ids` chỉ có compatibility handling được ADR cho phép; nhiều/blank/unknown IDs fail closed.
5. Chuẩn hóa error codes tối thiểu cho required, malformed, inaccessible/out-of-scope, stale và no-eligible cases.
6. Giữ response fields v2/v3 hiện có; chưa đổi frontend launch trong task này.

Gate: không session row/snapshot nào được tạo khi selection invalid; omitted selection chỉ thành công trong unambiguous fallback đã duyệt.

### P3-02 — Clone-aware discovery và query-first filtering

1. Trích một effective-scope resolver dùng cùng `CloneDeckScope`/overlay query semantics cho discovery và session.
2. Resolve source Template versus installed/local presentation context theo P3-07.
3. Áp selected composition predicate trước `MAX_SESSION_CARDS`; sau đó giữ nguyên scheduler ordering, timezone/day-boundary và suspended/buried filters.
4. Trả cùng eligible identity set từ discovery và session authorization.
5. Test selected eligible cards nằm sau nhiều cards của composition khác để bắt regression filter-after-limit.

Gate chung P3-01/P3-02: owned, recursive mixed, installed source overlay và local-added paths đều authorize/query bằng một semantics; không source mutation và không physical-copy fallback.

## 6. Wave F — frontend launch và session durability

### P3-03 — Pre-session StudyMode UI

Launch state machine bắt buộc:

```text
discover -> zero / one / many
zero     -> empty or recoverable error; no open request
one      -> resolve explicit ID -> open once
many     -> wait for learner selection -> open once
open     -> active Study UI
```

Frontend thêm discovery API/types, chuyển selector ra trước session, gửi `composition_id`, loại client-only filter khỏi authority và giữ nguyên layout/control của active session. Retry phải đi qua mutex/open-request dedupe hiện có để không tạo duplicate session.

Gate: test chứng minh không có POST `/api/study/sessions` trước resolution/selection; zero/one/many, load/error/retry và stale selection đều có coverage; active screen đạt zero visual regression.

### P3-04 — Frozen composition restore

1. Freeze selected effective composition và P3-07 material trong existing versioned snapshot JSON.
2. Mọi card trong session phải reference selection tương thích; contradictory composition fail closed.
3. Reload dùng frozen snapshot, không gọi discovery để đổi lựa chọn.
4. Commit/retry từ chối client selection khác frozen selection.
5. Live definition edit/delete/unpublish sau open không đổi active lease nếu exact frozen executable/material còn support; thiếu material trả typed terminal/recoverable error.
6. Giữ dual-reader behavior cho supported legacy v2/v3 snapshots; không rewrite active snapshot khi rollback.

Gate: definition drift, reload, stale UI, unavailable version và legacy session cases đều có backend/frontend tests; không migration.

## 7. Wave G — real overlay exit gate

P3-06 thay toàn bộ clone simulation bằng fixture publish/install thật:

1. Tạo source owner, recursive deck, NoteTypes, Templates, Notes và Cards.
2. Publish/install qua production service để có `DeckInstall(clone_mode="logical_overlay")` và deck maps.
3. Assert ordinary source Notes/Cards không bị copy.
4. Discover, select và open session từ installed local scope; assert source Cards có correct effective composition.
5. Thêm local-added Note/Card và verify cùng logical deck resolve đúng local context.
6. Verify source/local field override/fork case đang được support, unauthorized access, mixed scope, query-limit fairness, reload và frozen selection.
7. Assert source Note/Card không đổi trước/sau flow.

Chỉ sau khi matrix này pass mới update canonical tracker thành Phase 3 complete và chuyển P3 task files vào `completed/`.

## 8. File ownership và collision rule

| Task | Primary files | Collision rule |
|---|---|---|
| P3-05 | New architecture ADR, P3-05 task handoff, tracker links | Docs-only; không sửa runtime |
| P3-07 | New architecture contract, P3-07 task handoff, tracker links | Docs-only; không tạo schema proposal trá hình |
| P3-01 | `app/routes/flashcards/study.py`, `app/services/study_session_service.py`, validators, session/composition tests | Merge trước P3-02; giữ API parsing trong route/validator |
| P3-02 | `app/services/study_composition_service.py`, overlay resolver/repository seam, session/composition tests | Không broad-rewrite share service; reuse current overlay module |
| P3-03 | `frontend/src/features/study/api.ts`, types, `useStudySession.ts`, `StudyPage.tsx`, selector/tests | Chỉ bắt đầu sau backend contract ổn định |
| P3-04 | session service/snapshot + frontend restore/store/hook/tests | Thực hiện sau P3-03; giữ v2/v3 readers |
| P3-06 | integration fixtures/tests và tracker/handoff | Không sửa expected behavior để hợp thức hóa physical clone |

Mọi thay đổi cùng `study_session_service.py`, `useStudySession.ts` hoặc restore/store files phải merge tuần tự theo task; không trộn handoff khiến reviewer không xác định được acceptance gate nào tạo behavior.

## 9. Verification matrix

| Mốc | Lệnh tối thiểu |
|---|---|
| P3-05/P3-07 docs | link/path check, decision cross-review, `git diff --check` |
| P3-01/P3-02 backend | `.venv\Scripts\python.exe scripts/run_tests.py --module study --backend-only` |
| P3-02 overlay regression | `.venv\Scripts\python.exe scripts/run_tests.py --module decks,flashcards --backend-only` |
| P3-03 frontend | `npm --prefix frontend run test:changed`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint` |
| P3-04 cross-language restore | Study backend + Study frontend modules |
| P3-06 exit gate | Study backend, Study frontend và Decks/Flashcards backend |
| Task handoff | `.venv\Scripts\python.exe scripts/run_tests.py --changed`, `git diff --check` |
| INT-01/pre-release | `python scripts/run_tests.py --all` chỉ tại final integration gate |

Nếu dùng browser để kiểm chứng pre-session UX, bắt buộc dùng isolated Chrome profile theo `AGENTS.md`; không dùng profile cá nhân mặc định.

## 10. Stop conditions và rollback

STOP và quay lại decision gate nếu:

- current mixed-scope evidence không thể xác định mức tin cậy;
- discovery và session không thể dùng cùng overlay-aware identity mà không copy/mutate source;
- repeated application cần physical Card/progress duplication;
- một task cần DDL, new FK hoặc progress authority change;
- active session chỉ restore được bằng cách resolve latest live Template;
- ambiguous old-client request vẫn cần chọn “first/default” ngầm.

Rollback Phase 3 phải tắt admission của flow mới nhưng giữ readers cho mọi snapshot/wire version đã phát hành. Không xóa frozen artifacts, session history, overlay maps hoặc compatibility IDs. Nếu P3-06 fail sau rollout candidate, tracker phải giữ Phase 3 ở trạng thái `Partial`.

## 11. Completed handoff

Chuỗi phụ thuộc đã hoàn tất theo thứ tự P3-05 → P3-07 → P3-01/P3-02 → P3-03/P3-04 → P3-06 → INT-01. Phase 4 chưa được triển khai và vẫn cần phê duyệt riêng cho mọi model, migration hoặc thay đổi progress authority.

Handoff format đã dùng cho P3-05:

```text
Task ID: P3-05
Primary outcome:
Evidence sources and confidence:
Decision and rejected alternatives:
API grouping/cardinality/default/error contract:
Frontend launch-state contract:
Owned/overlay/old-client examples:
Runtime change: none
Verification performed:
Rollback/supersession path:
Follow-up task IDs: P3-07, P3-01, P3-03
```
