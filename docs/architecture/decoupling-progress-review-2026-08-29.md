# Decoupling progress review and continuation plan — 2026-08-29

> Status: evidence-backed architecture review and execution proposal. This document does not authorize a schema migration, production write, or source-of-truth cutover.
>
> Superseded current review: [`decoupling-progress-review-2026-08-30.md`](decoupling-progress-review-2026-08-30.md) contains the P1-02 pre-closeout findings and completion addendum; the final task evidence is in [`completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md`](../task/decoupling/completed/P1-02_EXTERNAL_PROGRESS_REVISION_CONTRACT.md).
>
> Next execution plan: [`docs/task/decoupling/PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md`](../task/decoupling/PHASE_0_3_NEXT_EXECUTION_PLAN_2026-08-29.md).
>
> Scope: Study/Interaction/Trigger/Algorithm/Progress, Template/NoteType/applied composition, renderer trust boundary, shared-deck overlay compatibility, and migration readiness.
>
> Execution backlog: [`docs/task/decoupling/`](../task/decoupling/README.md)

> Historical note: sections below preserve the original evidence snapshot at commit `b01fcfb`. The status table and backend-duplication finding are superseded by the current update above and the completed P1-01 handoff.

## 1. Kết luận điều hành

Kế hoạch decoupling chưa sẵn sàng để bắt đầu Phase 4 hoặc thay đổi schema. Trạng thái chính xác tại commit `b01fcfb` là:

- Phase 0–2 có compatibility slice hữu ích nhưng các exit gate vẫn chưa đạt.
- Phase 3 có scaffold ở backend và frontend, nhưng luồng chọn composition chưa chi phối việc mở session, chưa chứng minh đúng với logical overlay clone, và test được gọi là exit gate đang mô phỏng physical copy thay vì mô hình overlay-only thật.
- Phase 4–9 chưa bắt đầu. `CardProgress` vẫn là source of truth duy nhất; chưa có model/migration cho learner/Note progress, Algorithm State, reusable Template definition, applied binding, hoặc StudyMode bền vững.
- Test module Study hiện xanh, nhưng coverage chưa chạm các gate còn thiếu và do đó không phải bằng chứng rằng phase đã hoàn tất.
- Có một blocker bảo mật cần xử lý trước các wave khác: iframe renderer hiện có thể gửi `host_command` làm thay đổi progress. Các check `source`, `instanceId`, channel và schema không chứng minh đây là thao tác bàn phím thật của người dùng vì Template JavaScript chạy trong cùng iframe có thể tự tạo message hợp lệ.

Khuyến nghị: nâng việc vô hiệu hóa progress-affecting iframe bridge thành Wave 0, hoàn tất correctness waves 1–4, đóng Phase 3 bằng test overlay thật, chốt các Priority-0 ADR, sau đó mới thiết kế và triển khai Phase 4 theo Expand → Backfill → Mirror → Shadow read → Cutover → Contract.

## 2. Nguồn bằng chứng và baseline đã kiểm tra

Thứ tự tin cậy dùng trong review:

1. model, migration và constraint hiện có;
2. runtime call graph và frontend session flow;
3. test hiện có;
4. lịch sử commit;
5. tài liệu kiến trúc/proposal.

Các bằng chứng trọng yếu:

- `models/template.py`: `Template.note_type_id` vẫn bắt buộc và cascade theo NoteType.
- `models/card.py`: Card vẫn là cặp `Note + Template`; uniqueness vẫn là `(note_id, template_id)`.
- `models/card_progress.py`: progress vẫn khóa theo `(user_id, card_id)` và chứa state scheduler dạng cố định.
- `models/study_session.py` và `models/study_session_card.py`: không có composition identity bền vững ở schema; composition chỉ nằm trong snapshot JSON.
- `migrations/`: không có migration decoupling Template/NoteType, Card/Progress, Algorithm State hoặc StudyMode.
- `app/services/study_algorithm_registry.py`: exact algorithm key/version registry và fail-closed đã có; hiện chỉ có `legacy-anki/1.0.0`.
- `app/services/study_action_runtime.py`: Action/Trigger hiện là compatibility metadata; chưa có Trigger dispatcher độc lập.
- `app/services/study_composition_service.py`: compatibility composition được suy ra từ Template hiện tại, chưa phải durable applied binding.
- `frontend/src/features/study/hooks/useStudySession.ts`: session được mở mà không gửi composition lựa chọn.
- `frontend/src/features/study/pages/StudyPage.tsx`: selector chỉ lọc queue của session đã được mở.
- `app/services/study_session_service.py`: batch path vẫn lặp lại event/side-effect/policy work thay vì hoàn toàn dùng một authoritative transaction command.
- `static/js/card_renderer_host.js`: `host_command` hiện đi từ iframe sang parent và được chuyển thành progress-affecting UI command.

Verification đã chạy ngày 2026-08-29:

```text
python scripts/run_tests.py --module study --backend-only
PASS — 11 files, 65 tests

python scripts/run_tests.py --module study --frontend-only
PASS — 19 files, 87 tests
```

Các suite xanh chỉ xác nhận regression matrix hiện tại. Chúng chưa có negative proof cho forged `host_command`, same-tick mutex, restore sequence integrity, hay composition trên DeckInstall overlay thật.

## 3. Ma trận tiến độ chính xác

| Track | Trạng thái | Đã có | Exit gate còn thiếu |
|---|---|---|---|
| Phase 0 — evidence/invariants | **Completed, GO** | safe audit contract, accepted SELECT-only MySQL bundle, behavior baseline and checksums | downstream warning owners only; no Phase 0 blocker |
| Phase 1 — runtime boundaries | **Partial; P1-01 completed** | one typed native transition/mutation core for REST/MCP/session, canonical policy/event builder, race/rollback tests | P1-02 external conflicts, P1-03 provenance hardening and P1-04 retirement lifecycle |
| Phase 2 — Interaction/Trigger compatibility | **Partial, có security blocker** | semantic action metadata, extracted controls, legacy restore normalization | raw rating callback vẫn rò ra UI; ref chưa là mutex; restore validation thiếu; iframe `host_command` forgeable; chưa có Trigger dispatcher thật |
| Phase 3 — StudyMode/composition | **Partial scaffold, exit gate thất bại** | compositions API, compatibility IDs, optional server filter, snapshot metadata, selector UI | chọn trước khi mở session; exactly-one authorization; query-first filtering; immutable selection; mixed NoteType rule; overlay-only clone proof |
| Phase 4 — learner/Note progress + Algorithm State | **Not started** | conceptual split trong architecture plan | Priority-0 ADR, additive schema, backfill, mirror, shadow comparison |
| Phase 5 — authority cutover | **Not started** | none | Phase 4 reconciliation sạch và lossless legacy projection trong rollback window |
| Phase 6 — remove Card/Template progress ownership | **Not started** | none | stable compatibility mapping cho Card/Anki/Connect/clone và learner/Note authority |
| Phase 7 — retention/aggregation | **Not started** | policy direction 30 ngày | durable aggregate/history summary, lease-safe purge, reconciliation |
| Phase 8 — new Interaction/Algorithm | **Not started** | none | runtime và storage authority ổn định, threat model được duyệt |
| Phase 9 — contract legacy storage | **Not started** | none | backup/restore proof, migration approval riêng, không còn reader/writer cũ |
| Physical Template–NoteType decoupling | **Not started** | investigation và product decisions | physical schema, version/application lifecycle, bindings, import/export/marketplace compatibility |

## 4. Các gap phải xử lý trước schema

### 4.1 Blocker — renderer có progress side channel không đáng tin cậy

Luồng hiện tại:

```text
Template JavaScript trong iframe
  -> postMessage(host_command + instance/channel)
  -> card_renderer_host parent listener
  -> flama:host-command
  -> StudyPage reveal / answer / undo
  -> session progress mutation
```

`event.source`, instance ID và channel chỉ xác định đúng iframe/session, không chứng minh thao tác người dùng. Vì bootstrap identity có mặt trong cùng iframe realm, Template code có thể tạo message trực tiếp. Đây là regression so với ranh giới được ghi trong `CARD_TEMPLATE_SANDBOX_RENDERER.md`.

Biện pháp containment an toàn là loại bỏ mọi progress-affecting `host_command`. Shortcut có thể tạm không hoạt động khi focus nằm trong iframe; đây là trade-off phù hợp hơn việc giữ một write side channel giả mạo được. Thiết kế khôi phục shortcut phải có threat model riêng và không dựa vào một nonce bị lộ cho untrusted realm.

### 4.2 Resolved by P1-01 — canonical native transaction boundary

P1-01 replaced the duplicated batch writer with `execute_native_review_transition` and `apply_native_review_mutation` in `study_service.py`. REST/MCP keep their direct transaction wrapper; batch keeps lease/idempotency/bulk locks and one outer transaction while delegating policy identity, transition execution, progress application, `ReviewEvent` construction and required side effects.

Closure evidence: fixed-time REST/MCP/session parity, canonical-core delegation, batch idempotency, stale conflicts, typed first-progress races and rollback after progress/event/note-side-effect mutation all pass. External snapshot/revlog/import writers remain intentionally separate and are the next P1-02/P1-03 scope.

### 4.3 Frontend operation guard chưa phải mutex

`operationRef` hiện được dùng như marker nhưng các đường answer/undo/restore/commit không atomically test-and-acquire trước `await`. Hai event cùng tick vẫn có thể cùng đi vào mutation path.

### 4.4 Restore validation chưa fail-closed đầy đủ

Validator hiện chưa bắt buộc:

- event ID đúng UUID;
- ID không trùng;
- sequence bắt đầu tại 1 và liên tục;
- offset đơn điệu và nằm trong lease bound;
- card/session association đầy đủ;
- mọi action/trigger identity hợp lệ theo version.

### 4.5 Composition chưa phải input authoritative của session

Backend nhận `composition_ids` tùy chọn và lọc sau khi đã lấy giới hạn card. Frontend không gửi lựa chọn đó khi mở session. Vì thế selector hiện chỉ thay đổi view cục bộ, không thay đổi session contract.

Với installed shared deck, composition service có thể suy ra local copied Template trong khi logical overlay session dùng source Cards/source Template IDs. Test `test_study_composition_exit_gate.py` tạo một Card copy thứ hai để “mô phỏng clone”, nên không chứng minh invariant overlay-only. Test logical overlay thật trong `test_study_session_api.py` lại chưa kiểm tra discovery/selection composition.

### 4.6 Audit chưa đạt migration grade

CLI hiện in JSON nhưng không trả exit code theo verdict, chưa có bounded sample IDs, thiếu MySQL verification, và việc khởi tạo Flask app vẫn có startup maintenance side effects. Không nên chạy command hiện tại trên production chỉ vì service function tự mô tả là read-only.

## 5. Invariants bắt buộc giữ nguyên

1. Shared deck tiếp tục overlay-only; không tạo lại full-copy clone flow và không mutate source Note trong clone edit.
2. Một learner/Note có đúng một progress authority dùng chung cho mọi Template, Interaction và applied composition.
3. Template edit, detach, unpublish hoặc delete không được cascade xóa progress.
4. Reusable Template khai báo abstract input; applied NoteType-scoped application mới bind tới stable `FieldDef` identity. Field name chỉ là label/legacy syntax.
5. Cùng một Template có thể được apply nhiều lần vào một NoteType với application/config identity khác nhau.
6. Installed definition được pin theo version; edit tạo private fork theo copy-on-write.
7. StudyMode được chọn trước khi mở session và bị freeze cho toàn bộ lease.
8. Algorithm key/version/state-schema/config hash được resolve chính xác và fail closed.
9. Chỉ một transaction owner được quyền mutate progress, ghi authoritative event, idempotency receipt và required side effects.
10. Untrusted renderer không được trực tiếp chọn action/rating hoặc phát lệnh thay đổi progress.
11. Trong migration, legacy `CardProgress` là authority cho tới cutover gate; mirror mới chỉ là derived projection trong cùng transaction.
12. Không contract/drop legacy storage trước backup restore proof, reconciliation production và approval riêng.

## 6. Roadmap thực thi đề xuất

Ước lượng dưới đây là engineering effort tương đối, không bao gồm thời gian chờ quan sát production hoặc duyệt ADR.

### Wave 0 — Security containment (P0, 1–2 engineer-days)

Mục tiêu: đóng ngay write side channel từ iframe.

Tasks:

1. Xóa/disable child `host_command` emission và parent translation sang `flama:host-command`.
2. Gỡ progress handler tương ứng trong `StudyPage`; giữ shortcut ở trusted parent document.
3. Thêm test chủ động forge `host_command`, legacy `keydown_event`, action/rating tùy ý và assert không reveal/answer/undo.
4. Cập nhật renderer security contract và cache revision nếu cần.
5. Browser-test bằng profile Chrome cô lập; bao phủ input/textarea/contenteditable/IME/repeat.

Exit gate:

- Template script không thể làm thay đổi progress qua `postMessage`.
- Shortcut ngoài iframe và UI hiện tại không visual regress.
- Việc shortcut không hoạt động khi focus trong iframe được ghi rõ là giới hạn tạm thời.

Rollback: không tự động bật lại bridge cũ. Chỉ khôi phục shortcut-in-iframe sau một threat model và security test được duyệt.

### Wave 1 — Correctness của compatibility runtime (5–8 engineer-days, ba nhánh chạy song song)

#### A. Canonical backend review command

- Trace direct REST, MCP, batch và import/sync entry points.
- Tách một transaction command/core duy nhất sở hữu lock, validation, transition, progress write, authoritative event, required side effects và idempotency result.
- Batch chỉ thích nghi transport/lease input; không tự dựng event hoặc scheduler identity.
- Hợp nhất policy/config serializer.
- Typed contract cho concurrent first progress creation và stale revision.

Gate: direct/MCP/batch tạo cùng canonical transition metadata; batch atomicity và retry semantics không đổi; duplicated authoritative builder search về zero.

#### B. Frontend session mutex

- Dùng synchronous test-and-acquire hoặc serialized queue trước mọi async mutation.
- Answer, undo, restore, retry và commit dùng cùng exclusion rule.
- Release guard trong success, handled error, abort và unmount.
- Test `submit+submit`, `submit+undo`, `restore+submit`, `commit+submit` trong cùng tick.

Gate: tại mọi thời điểm chỉ một mutating operation có ownership; test phải fail trên implementation cũ.

#### C. Restore validation/quarantine

- Validate UUID, uniqueness, contiguous sequence, card/session membership, supported contract identity và bounded monotonic offset.
- Quarantine với stable reason; không tự sửa history mơ hồ.
- Giữ normalization cho legacy v2 hợp lệ.

Gate: malformed rows không vào live state hoặc commit payload; valid current/legacy restore vẫn hoạt động.

Wave 1 integration gate: chạy Study backend/frontend, MCP và changed-file suites; không có schema change.

### Wave 2 — Semantic Interaction boundary và trusted input (3–5 engineer-days)

1. `ReviewInteractionControls` chỉ emit một semantic `ReviewAction` callback.
2. Raw numeric/rating mapping chỉ tồn tại trong compatibility adapter; `StudyBottomBar` không còn public raw scheduler callback.
3. Bảo toàn 100% button order, labels, color, spacing, icon, disabled state và keyboard hints.
4. Thiết kế shortcut-in-iframe như một security subproject. Baseline được phép là “không hỗ trợ khi iframe focused”. Bất kỳ bridge mới nào cũng phải chứng minh untrusted Template không thể forge intent.

Gate: một user gesture tạo đúng một semantic action; renderer không thể chọn arbitrary action/rating; zero visual regression.

### Wave 3 — Đóng Phase 3 thật sự, chưa đổi schema (5–8 engineer-days)

Backend:

1. Dùng một clone-aware scope resolver cho cả composition discovery và session card query.
2. Compatibility composition phải được suy ra từ actual effective card/application context, không suy ra riêng từ local installed NoteType rồi lọc source Card bằng local Template ID.
3. API session nhận một `composition_id` canonical; validate owned/accessible/in-scope. Tạm hỗ trợ old client bằng explicit default dưới feature flag, không nhận danh sách mơ hồ.
4. Áp dụng composition trong DB query trước `MAX_SESSION_CARDS`, không fetch rồi filter.
5. Freeze selected composition + effective version/config metadata trong snapshot; không cho live definition đổi semantics của session đang mở.
6. Quyết định và test rule cho recursive deck có nhiều NoteType.

Frontend:

1. Gọi compositions endpoint trước khi mở session.
2. Với một option, dùng explicit default; nhiều option thì chờ learner chọn; zero option thì hiện recoverable empty state.
3. Gửi selection vào open-session request.
4. Restore session dùng frozen composition, không prompt hoặc lọc lại theo current definition.

Required tests:

- owned deck;
- owned recursive deck;
- real `DeckInstall` logical overlay với source Cards;
- local-added Note trong installed deck;
- unauthorized/out-of-scope/stale composition;
- query-limit fairness;
- one/multiple/empty options;
- active-session restore.

Gate: xóa physical-copy “clone simulation” khỏi exit proof; direct và overlay-only paths đều chứng minh cùng contract.

### Wave 4 — Migration evidence và ReviewEvent hardening (4–6 engineer-days)

Audit:

- chạy read-only bằng construction, không thông qua mutating startup maintenance;
- deterministic/bounded output, counts + sampled IDs, không log answer content;
- explicit pass/warn/block exit codes;
- SQLite tests và MySQL execution evidence;
- inventory progress fan-in, orphan/NULL, revision, open lease, event provenance, clone/source/local identity và algorithm labels.

ReviewEvent:

- một contract nhất quán cho new native writes: effective algorithm/version/config hash, semantic action/trigger, source path, session/request/idempotency/order identity;
- legacy gaps được classify, không bịa provenance;
- schema column mới, nếu cần cho query, phải là một additive migration riêng và không được gộp với progress cutover.

Gate: operator có thể dùng audit để quyết định migration go/no-go và nhận exit status tự động.

### Wave 5 — ADR checkpoint trước Phase 4 (documentation only, 3–5 engineer-days)

Phải chốt tối thiểu:

1. normalized availability projection và selection policy;
2. active Algorithm ownership và quyền switch;
3. Algorithm State schema validation, size limit, decoder/migration, corruption recovery;
4. incomplete/imported history fallback;
5. compact history còn lại sau retention 30 ngày;
6. mixed-NoteType deck selection;
7. executable/state decoder retirement;
8. primary/follow-up transaction and idempotency semantics;
9. native/MCP/Anki snapshot/revlog/offline conflict priority;
10. allowed Template input types và renderer trust tiers.

Gate: ADR được duyệt và không còn Priority-0 decision ảnh hưởng physical state design.

## 7. Phương án physical design để duyệt ở Wave 5

Tên entity dưới đây là provisional; đây là responsibility proposal, chưa phải SQL được duyệt.

### 7.1 Progress/Algorithm State

| Lựa chọn | Ưu điểm | Rủi ro | Kết luận |
|---|---|---|---|
| A. Đổi trực tiếp `CardProgress.card_id` thành `note_id` và thêm JSON state | ít table mới | destructive, khó rollback, fan-in collision khó quarantine, legacy query/cascade bị đổi cùng lúc | Không khuyến nghị |
| B. Một learner/Note envelope chứa cả query projection và algorithm JSON | triển khai đơn giản hơn; một row/subject | generic lifecycle và opaque state vẫn chung lifecycle; khó version/validate/switch độc lập | Chỉ cân nhắc nếu state contract rất nhỏ |
| C. **Additive learner/Note envelope + active versioned Algorithm State + normalized availability projection** | đúng responsibility, query hiệu quả, shadow/mirror/cutover rõ, algorithm state opaque nhưng validated | thêm join và transaction invariant | **Khuyến nghị** |

Candidate responsibility:

- `LearnerNoteProgress`: unique `(learner_user_id, note_id)`, lifecycle/control status, concurrency revision, active algorithm/state-schema identity, last authoritative mutation reference.
- `LearnerNoteAvailability`: query-efficient projection cho eligible/blocked/completed, next eligibility và selection priority/bucket; có thể cùng physical row với envelope nếu benchmark chứng minh tốt, nhưng vẫn là derived responsibility.
- `LearnerNoteAlgorithmState`: đúng một active state cho progress, algorithm key/version/state-schema, validated opaque payload, state hash/provenance.
- Compatibility mapping giữ Card ID, Anki external card ID, source/local clone context và active v2 session addressability.

### 7.2 Reusable Template và applied composition

| Lựa chọn | Ưu điểm | Rủi ro | Kết luận |
|---|---|---|---|
| A. Nới `Template.note_type_id` thành nullable và dùng chính row hiện tại làm global definition/application | ít entity | một row vẫn trộn definition, binding, application, ordinal/default; repeated application mơ hồ; cascade/authorization blast radius lớn | Không khuyến nghị |
| B. Independent definition bind trực tiếp đến FieldDef IDs | rename-safe trong một schema | không portable qua NoteType; mỗi binding set thực chất đã là application ẩn | Không khuyến nghị cho reuse mục tiêu |
| C. **Versioned reusable definition + abstract inputs + NoteType-scoped application + stable bindings** | đúng product decisions, portable, repeated application rõ, pin/fork/version rõ | lifecycle và migration phức tạp hơn | **Khuyến nghị** |

Candidate responsibility:

- reusable Template definition và immutable version;
- abstract input declarations thuộc version;
- NoteType-scoped StudyMode/application identity, cho phép cùng definition được apply nhiều lần;
- binding rows từ abstract input đến stable FieldDef identity, ban đầu chỉ direct binding;
- install/source/version lineage và copy-on-write fork metadata;
- legacy `Template` tiếp tục làm compatibility presentation/Card mapping trong migration window.

Không bật delete/detach semantics mới cho legacy Template cho tới khi progress authority đã rời Card và toàn bộ Card/Anki/Connect/clone mapping đã được chứng minh.

## 8. Migration runbook sau khi ADR được duyệt

### Stage A — Expand

- Additive tables/columns/indexes only; không drop/rename/re-purpose legacy columns.
- Feature flags mặc định off.
- Constraints mới ban đầu cho phép backfill theo batch nhưng không cho tạo hai authority.
- Upgrade/downgrade được test trên MySQL copy; app version cũ vẫn chạy được.

### Stage B — Inventory và quarantine plan

- Chạy migration-grade audit bằng read-only DB principal và startup-maintenance-disabled entry point.
- Group mọi `CardProgress` theo `(user_id, Card.note_id)`.
- Mỗi fan-in group divergent phải vào quarantine/report; không chọn winner tự động.
- Preserve raw values và provenance; không reconstruct current state từ `ReviewEvent`.

### Stage C — Idempotent backfill

- Batch theo stable primary-key cursor, commit nhỏ, restart-safe.
- Insert learner/Note envelope + state + projection bằng deterministic mapping.
- Ghi mapping/disposition cho từng legacy row.
- Metrics: scanned, created, matched, quarantined, invalid, elapsed, high-water mark.

### Stage D — Same-transaction mirror

- Legacy `CardProgress` vẫn authoritative.
- Canonical command ghi legacy rồi derive mirror mới trong cùng transaction.
- Import, Connect, MCP, direct và batch đều phải đi qua revision/conflict semantics tương đương.
- Không cho API/worker nào ghi riêng new store.

### Stage E — Shadow read và reconciliation

- Reader vẫn trả legacy result nhưng tính new result song song.
- So sánh state hash, due time/day, ordering bucket, suspension/burial, revision và source/local Note identity.
- Gate là zero unexplained mismatch; tolerance chỉ cho representation difference đã được tài liệu hóa.

### Stage F — Guarded cutover

- Cutover reader trước theo cohort/internal flag, sau đó writer authority.
- Giữ lossless legacy write-through projection trong rollback window.
- Đo active v2 leases và giữ executable/version decoder tối thiểu qua max lease 24 giờ + safety margin đã duyệt.

### Stage G — Template/application expansion và cutover

- Materialize definition/version/application/binding additively.
- Backfill mỗi legacy Template thành một compatibility application không đổi rendered output hay Card IDs.
- Shadow render/manifest/import/export/clone resolution.
- Chỉ route authoring và new session composition sang entity mới sau parity gate.

### Stage H — Contract

- Chỉ chạy sau approval riêng, verified backup, restore rehearsal và production reconciliation.
- Remove cascade/progress ownership, name-based binding và obsolete columns theo nhiều migration nhỏ.
- Incident rollback sau khi có new-only state là forward repair hoặc backup restore; không reverse-migrate phá dữ liệu.

## 9. Verification matrix bắt buộc

| Boundary | Bằng chứng cần có |
|---|---|
| Renderer security | forged message negative tests + real-browser focus/IME/editable tests bằng isolated profile |
| Direct/MCP/batch | event/state/side-effect parity, idempotent retry, atomic rollback, concurrent first insert |
| Frontend session | same-tick mutex, undo, restore, commit, IndexedDB quarantine, unmount/abort cleanup |
| Composition | pre-open selection, authorization, immutable snapshot, query-limit fairness, mixed NoteType |
| Clone | source overlay Card, local-added Card, installed NoteType/template copy, no source mutation |
| Import/Connect/Anki | external-card mapping, ordinal compatibility, snapshot/revlog conflict and provenance |
| Database | SQLite unit tests, MySQL constraints/query plan, upgrade/downgrade, restartable backfill |
| Reconciliation | zero unexplained state/projection mismatch, full disposition accounting |
| Rollback | flag-off before cutover, legacy read proof during mirror, backup restore rehearsal before contract |
| UI | zero visual regression for Study controls and launch flow |

Suggested focused commands during implementation:

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module study --frontend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
python scripts/run_tests.py --changed
```

Full suite chỉ chạy ở final integration/CI gate.

## 10. Ticket order đề xuất

```text
SEC-0 iframe containment
  -> COR-1 backend command
  -> COR-2 frontend mutex       (COR-1/2/3 có thể chạy song song)
  -> COR-3 restore validation
  -> INT-1 semantic controls
  -> INT-2 trusted keyboard design
  -> CMP-1 backend composition
  -> CMP-2 pre-session selection
  -> AUD-1 migration-grade audit
  -> EVT-1 event provenance
  -> ADR-1..10 Priority-0 decisions
  -> MIG-EXPAND
  -> MIG-BACKFILL
  -> MIG-MIRROR
  -> MIG-SHADOW
  -> MIG-CUTOVER
  -> TEMPLATE-EXPAND/CUTOVER
  -> RETENTION
  -> CONTRACT (approval riêng)
```

Không bắt đầu `MIG-EXPAND` chỉ vì compatibility tests xanh. Điều kiện bắt đầu là Wave 0–4 đạt gate, Phase 3 có overlay proof thật, audit chạy được trên MySQL an toàn, và toàn bộ Priority-0 ADR đã được duyệt.
