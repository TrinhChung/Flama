# P1-02 — External progress revision and conflict contract

> Phase: 1
>
> Priority: P1
>
> Status: IN PROGRESS — P1-02.1 and P1-02.2 completed; P1-02.3 implementation is next
>
> Dependency: P1-01
>
> Primary lane: Backend Connect / Import / Share
>
> Preparation status: P1-01 dependency is satisfied. P1-02.1 inventory and P1-02.2 conflict decisions closed on 2026-08-29; P1-02.3 is the next executable task.

## Mục tiêu

Định nghĩa và áp dụng revision/conflict semantics nhất quán cho các path có thể thay đổi current progress ngoài native Study: Anki snapshot, revlog import, Flama Connect, import/cutover và clone repair.

## Bối cảnh

Native Study dùng lock/revision contract rõ hơn các external mutation paths. Nếu các path ngoài Study cập nhật progress mà không tham gia cùng concurrency rule, offline session hoặc MCP/direct review có thể ghi đè state mới hơn.

## Phạm vi file cần trace

- `app/services/anki_sync_service.py`
- `app/services/anki_import_service.py`
- `app/services/flama_connect_service.py`
- `app/services/connect/`
- `app/services/share/cutover.py`
- `app/services/flashcards_share_service.py`
- `models/connect_*.py`
- progress/review repositories liên quan
- `tests/test_anki_import_api.py`
- `tests/test_flama_connect_mcp.py`
- clone/cutover tests liên quan

## Công việc chi tiết

1. Lập mutation inventory: path, input identity, lock, revision read/write, event provenance, commit owner.
2. Phân biệt rõ:
   - user interaction review;
   - external snapshot replacement;
   - external revlog event import;
   - clone/cutover repair;
   - idempotent no-op sync.
3. Chốt conflict matrix giữa:
   - native direct/MCP;
   - open offline/batch session;
   - Anki snapshot;
   - Anki revlog;
   - import/cutover/repair.
4. Mỗi mutation phải:
   - lock hoặc verify revision theo contract;
   - increment/preserve revision đúng quy tắc;
   - emit typed conflict thay vì last-write-wins ngầm;
   - ghi source/provenance chính xác;
   - không gọi native Action semantics nếu đây là state sync.
5. Giữ idempotency qua external IDs/content hashes hiện có.
6. Định nghĩa behavior khi history incomplete hoặc snapshot cũ hơn current state.
7. Test concurrent native review vs từng external path quan trọng.
8. Test logical overlay identity: source/local Card đều resolve đúng current progress subject hiện tại mà không mutate source content.

## P1-02.1 — Mutation inventory đã xác minh

### Quy ước authority dùng cho inventory

- Current progress subject là duy nhất theo `(user_id, effective_card_id)` trong `card_progress`; với clone logical overlay, `effective_card_id` có thể là source Card hoặc clone-added local Card theo resolver hiện hành.
- `ReviewEvent` là immutable history/projection, không phải current scheduler state authority.
- `revision` phải đại diện cho thay đổi có thể làm một open Study Session trở nên stale. Một write thay đổi queue/due/interval/ease/memory/suspend/bury/reps/lapses/last-review pointer nhưng không tham gia revision contract là mutation gap.
- Package/content hash và external ID là idempotency identity; chúng không thay thế row lock hoặc optimistic revision check.

### Bảng producer/mutator đầy đủ

| ID | Path thực thi / entrypoint | Loại mutation và input identity | Lock hiện tại | Revision hiện tại | Idempotency / provenance | Transaction owner hiện tại | Kết luận P1-02.1 |
|---|---|---|---|---|---|---|---|
| N1 | `study_service.execute_native_review_command` qua REST và MCP | Native user review; subject `(user_id, effective_card_id)` | Lock `CardProgress` hiện có; flush bắt race tạo row đầu tiên | Mỗi accepted command tăng đúng `+1` | Native `ReviewEvent`; runtime metadata do canonical core P1-01 tạo | Command wrapper commit/rollback | **Reference contract**, không sửa trong P1-02 trừ adapter conflict dùng chung |
| N2 | `study_session_service.commit_study_session` | Offline/batch native review; session snapshot + `base_revision`, idempotency theo session/client event | Lease/session lock, bulk `CardProgress` lock, scope revalidation | Mỗi card trong một batch hợp lệ tăng đúng `+1`, kể cả có nhiều event | Unique session sequence/client event + commit receipt; native provenance | Session service sở hữu toàn transaction | **Reference conflict consumer**; mọi external state replacement phải làm session stale |
| E1 | `anki_sync_service.import_progress` → `_apply_progress_snapshot`, được gọi bởi progress sync package | External Anki scheduler snapshot; `(source_key, sourceCardId, snapshotHash)` | Lock source-card ref và lock progress hiện có; row chưa tồn tại chỉ dựa vào unique constraint | Applied snapshot tăng `+1`; same-hash tạo default row revision `0` nếu row bị thiếu; `due_unresolved` cũng có thể để lại default row `0` | `ConnectSourceCardRef.snapshot_hash` + `applied_local_revision`; package `(session, kind, sequence, sha256)` | REST/Connect upload endpoint commit; mỗi record dùng savepoint, package có thể `partial_failed` | **In scope P1-02.2–.4**. `force=true` bypass conflict; first-row race chưa typed; no-op/unresolved không được phép tạo authority row ngoài contract |
| E2 | `anki_sync_service.import_reviews` → `_import_review`, được gọi bởi reviews sync package | External Anki revlog history; durable ID `(user_id, source_key, sourceReviewId)` | Lock provenance ref và source-card ref; **không lock `CardProgress`** | Tạo/repair event không đổi revision; nhưng event mới hơn có sửa `last_reviewed_at` và `last_review_event_id` **không bump revision** | Payload hash; `ConnectReviewEventRef`; event gắn `anki` / `revlog-v1`; replay repair projection được hỗ trợ | Endpoint commit toàn package; savepoint atomic theo source card, package cho phép partial failure | **Mutation gap**. History import là append/repair, không được giả thành native action; phải chốt riêng rule cho derived current-progress pointer |
| E3 | `connect.import_cards` → `_migrate_cards_progress`; gọi trực tiếp bởi AnkiConnect `importCards` hoặc card package | Legacy card snapshot theo note content + template ordinal; không có progress snapshot ID riêng | Lock progress hiện có; mapping dựa trên sorted template position | Existing row được `+1`; row mới giữ revision `0`; older timestamp bỏ qua, **timestamp bằng nhau vẫn overwrite/bump** | Note `contentHash` và package hash chỉ bảo vệ một số transport; direct `importCards` replay có thể apply lại | `import_cards(commit=True)` tự commit; card package gọi `commit=False`, REST/Connect endpoint commit; savepoint theo card/note | **Mutation gap**. Cần typed applied/no-op/conflict result, provenance đúng `anki`, và cùng rule first-row/revision với E1 |
| R1 | Active clone cutover: `app.services.flashcards_share` shim → `flashcards_share_service._merge_card_progress_rows_for_cutover` | Repair/rekey local cloned-card progress sang logical source-card progress | Repository reads **không lock** local/target progress | Rekey giữ revision cũ; merge có thể overwrite target và `max(reps/lapses)` nhưng **không bump revision** | Không có mutation provenance/result per row; chọn row theo `updated_at` | CLI `clone-cutover-overlay` hoặc opt-in startup maintenance commit; helper có rollback nội bộ khi một install lỗi | **Mutation gap mức cao**. Cần lock deterministic, monotonic revision, per-install savepoint/result và không mutate source Notes/Cards |
| R1-DUP | `app/services/share/cutover.py` | Cùng repair logic như R1 | Cùng thiếu lock | Cùng thiếu revision rule | Không có | Hiện không có production callsite trực tiếp được tìm thấy | **Duplicate boundary**. Không sửa riêng rồi để active shim chạy implementation khác; consolidation thuộc P1-02/P1-03 boundary và P3 cleanup |
| D1 | `deck_management_service.reset_deck_progress` qua `POST /api/decks/<id>/progress-reset` | User-authorized destructive reset, gồm logical-overlay source cards | Bulk delete không lock rows/session | Xóa row nên mất revision; session có base `0` có thể không phân biệt “chưa từng học” với “đã reset” | Không có reset receipt/tombstone | Service tự commit | **Conflict-invalidating command**. P1-02.2 phải chọn cách đóng/invalidate open sessions mà không thêm schema |
| D2 | Deck/note/card delete và purge trong `deck_management_service`, legacy vocabulary delete, MCP note delete, seed replacement | Entity lifecycle/destructive maintenance; progress bị delete cùng card/note | Tùy command; không có revision contract chung | Không áp dụng sau khi Card bị xóa | Entity authorization/audit tùy path | Mỗi service/route/CLI hiện có | Inventory đầy đủ nhưng **không phải snapshot merge**. Acceptance là stale session không được tái tạo progress cho entity/scope đã mất |
| M1 | `startup_schema.ensure_backward_compatible_schema` và Alembic revision backfill | One-time schema compatibility/backfill (`NULL` defaults, `interval_days_raw`, initial revision) | Không dùng row-level concurrency contract | Alembic gán revision ban đầu `1` cho row đã review; compatibility patch không bump khi backfill derived/default fields | Migration revision / startup maintenance flag | Alembic hoặc startup maintenance transaction | **Ngoài online conflict matrix**; chỉ hợp lệ khi chạy migration/maintenance trước traffic. Audit app đã ép tắt mutating maintenance |

### Call graph và transaction boundary đã chốt

```text
REST Anki import
  anki_imports route
    -> anki_import_service facade
      -> flama_connect_package_service
        -> anki_sync_service import_progress/import_reviews
    -> route COMMIT / ROLLBACK

Standalone Connect package endpoint
  app.connect endpoint
    -> flama_connect_package_service
      -> connect.import_cards(commit=False) OR anki_sync_service
    -> endpoint COMMIT / ROLLBACK

Direct AnkiConnect importCards
  app.connect protocol endpoint
    -> flama_connect_service facade -> connect.dispatcher
      -> connect.import_cards(commit=True)
    -> endpoint COMMIT lần nữa / ROLLBACK khi lỗi

Clone cutover đang chạy
  CLI hoặc opt-in startup maintenance
    -> app.services.flashcards_share compatibility shim
      -> flashcards_share_service (legacy monolith)
        -> _merge_card_progress_rows_for_cutover
    -> CLI/startup COMMIT
```

`import_progress` dùng savepoint theo record; `import_reviews` dùng savepoint theo source card; `import_cards` dùng savepoint theo note/card. Vì exception được chuyển thành per-item result, package thành công có thể commit các item hợp lệ và trả `partial_failed`. Đây là behavior hiện hữu phải được giữ khi thêm typed conflict.

### Search proof và negative inventory

Các search dưới đây xác nhận không còn online `CardProgress` state writer nào khác ngoài native core, hai Anki/Connect importer và hai bản cutover; những reference còn lại là query/serialization hoặc destructive entity lifecycle:

```text
rg -n "CardProgress\\(" app -g "*.py"
rg -n "\\.revision\\s*(\\+=|=)" app/services app/repositories -g "*.py"
rg -n "last_review_event_id\\s*=|last_reviewed_at\\s*=|interval_days\\s*=|due_at\\s*=|due_day\\s*=" app/services app/repositories -g "*.py"
rg -n "create_review_event_record\\(|record_review_event\\(" app -g "*.py"
rg -n "CardProgress\\.query.*delete" app -g "*.py"
```

Kết quả quan trọng:

- Online constructors chỉ nằm ở native direct, native batch, modern Anki snapshot và legacy `cardsProgress` import.
- `ReviewEvent` chỉ được tạo qua canonical native recorder hoặc `create_review_event_record` của Anki revlog.
- Browse, dashboard, stats, vocabulary repository và MCP study read paths không ghi progress.
- Không tìm thấy callsite production trực tiếp cho modular `app.services.share.cutover`; startup/CLI dùng compatibility shim trỏ vào monolith.

### Gap register chuyển sang P1-02.2

| Gap | Rủi ro quan sát được | Quyết định bắt buộc ở P1-02.2 |
|---|---|---|
| G1 — revlog pointer write không lock/revision | Native/session có thể không thấy history projection vừa thay đổi hoặc overwrite pointer | Pointer là derived-only hay progress mutation; lock/bump/no-op rule tương ứng |
| G2 — snapshot row mới revision `0` | Open session base `0` không nhận ra external snapshot đầu tiên | Initial material mutation revision phải là `1`; xử lý race bằng typed result |
| G3 — same-hash/due-unresolved tạo default row | Idempotent/no-op request vẫn tạo authority state | No-op phải không tạo row; unresolved phải rollback toàn record mutation |
| G4 — `force=true` không có contract rõ | Có thể overwrite newer native state có chủ ý nhưng không audit lý do | Scope/authorization, result code và session invalidation cho forced replacement |
| G5 — legacy timestamp tie/missing semantics | Replay có thể bump revision; snapshot thiếu timestamp có thể trở thành current state | Stable no-op hash/equality và explicit incomplete-history policy |
| G6 — legacy scheduler provenance | Imported snapshot dùng runtime scheduler mode và có thể bị hiểu là native | Lưu đúng external scheduler provenance mà không gọi native Action semantics |
| G7 — cutover merge không lock/revision | Concurrent review có thể mất state; stale session không bị phát hiện | Deterministic lock order, revision `max(local,target)+1` khi material merge/rekey, per-install atomicity |
| G8 — reset xóa revision | Session base `0` có thể hồi sinh progress sau reset | Invalidate/close affected sessions hoặc equivalent no-schema guard |
| G9 — active/duplicate cutover split | Patch có thể chỉ sửa dead modular file | Chọn canonical implementation và giữ shim thật sự delegate cùng code |

### Output bàn giao P1-02.1

```text
Task ID: P1-02.1
Primary outcome: Complete inventory of current-progress/history producers, locks, revisions, idempotency and transaction owners.
Runtime change: none
Evidence files: service, repository, model, route, startup, CLI and focused tests named in the tables above.
Files changed: this task document and decoupling trackers only.
Contract/API behavior changed: none.
Tests added or updated: none; investigation only.
Verification: Markdown relative-link check and git diff check.
Rollback path: revert the documentation-only commit.
Known limitations: conflict/priority decisions are intentionally deferred to P1-02.2; no MySQL write probe was executed.
Follow-up task IDs: P1-02.2, P1-02.3, P1-02.4, P1-03, P3 cleanup for share-service duplication.
```

## P1-02.2 — Conflict/priority matrix đã chốt

### Rule set bắt buộc

1. **Material progress write** là thay đổi scheduler/current-state field của `CardProgress`. Writer phải lock row hiện có và tăng revision đúng một lần; row mới bắt đầu ở revision `1` sau material write.
2. **Idempotent/no-op** không tạo `CardProgress`, không tăng revision và không tạo duplicate event.
3. **Native direct/MCP** tiếp tục dùng canonical transaction P1-01. Nếu external snapshot commit trước, native command đọc state mới dưới lock; nếu native commit trước, external optimistic check trả conflict.
4. **Open batch session** không bị writer bên ngoài sửa trực tiếp. Mọi material external write tăng revision để commit session trả `CARD_PROGRESS_CONFLICT` theo `base_revision` đã freeze.
5. **Modern Anki snapshot** dùng hai optimistic token độc lập:
   - `applied_local_revision` phát hiện native/local write kể từ snapshot Anki cuối;
   - optional `baseSnapshotHash` phát hiện hai external snapshots đến sai thứ tự. First-party sync phải gửi hash server trả từ note-status; client cũ thiếu field vẫn được nhận trong compatibility window nhưng result phải ghi `legacy_unversioned=true`.
6. `force=true` chỉ là explicit authenticated resync override. Nó được phép vượt local/base conflict nhưng vẫn lock, tăng revision và trả code `FORCED_PROGRESS_APPLIED`; không được gọi native Action semantics.
7. **Anki revlog** chỉ append/repair immutable history và provenance. Nó không sửa `CardProgress.last_reviewed_at`/`last_review_event_id`, không tăng revision; current state do snapshot/native writer sở hữu.
8. **Legacy `cardsProgress`** không có durable snapshot token nên dùng fail-closed timestamp rule:
   - incoming mới hơn: apply và tăng revision;
   - incoming cũ hơn hoặc identical: no-op;
   - timestamp bằng nhau nhưng state khác, hoặc không đủ timestamp để order một existing material row: typed conflict;
   - row mới materialized ở revision `1` và gắn scheduler provenance `anki`.
9. **Clone cutover** là maintenance repair: lock local/source rows theo thứ tự ổn định; rekey/merge đặt revision thành `max(local, source) + 1`; mỗi install dùng savepoint khi non-strict; active compatibility shim phải delegate modular cutover.
10. **Explicit progress reset** hủy mọi open Study Session chứa card bị reset trước khi bulk-delete progress. Entity deletion tiếp tục dựa vào card/scope revalidation và không được tái tạo progress cho Card đã mất.

### Priority matrix

| Writer A | Writer B / trạng thái hiện hữu | Kết quả đã chốt |
|---|---|---|
| Native direct/MCP | Native direct/MCP | Row lock serialize; command sau tính từ state đã commit của command trước |
| Native direct/MCP | Open batch session | Native tăng revision; batch cũ fail `CARD_PROGRESS_CONFLICT` |
| Native direct/MCP | Modern snapshot | Snapshot chỉ apply nếu `applied_local_revision` còn khớp, nếu không trả `LOCAL_PROGRESS_CHANGED`; `force` là explicit override |
| Native direct/MCP | Legacy `cardsProgress` | Lock serialize; external chỉ thay nếu timestamp chứng minh mới hơn, ambiguous/equal-different trả conflict |
| Open batch session | Bất kỳ material snapshot/cutover write | External write tăng revision; batch cũ fail, không merge hai scheduler states |
| Modern snapshot | Modern snapshot cùng hash | `PROGRESS_UNCHANGED`; không row/event/revision side effect |
| Modern snapshot | Modern snapshot khác hash | Source-ref lock serialize; `baseSnapshotHash` mismatch trả `SOURCE_SNAPSHOT_CHANGED`; matching base được apply |
| Modern snapshot | Anki revlog | Snapshot sở hữu current state; revlog chỉ append history/provenance |
| Anki revlog | Native review | Hai immutable events cùng tồn tại theo provenance; revlog không overwrite native current state |
| Clone cutover | Existing local + source progress | Merge theo existing `updated_at` rule, giữ max counters, revision `max + 1`; local progress row bị xóa trong cùng savepoint |
| Progress reset | Open batch session | Session chuyển `cancelled`, commit trả `SESSION_NOT_OPEN`; progress rows sau đó bị xóa |
| Entity delete | Open batch session | Card/scope revalidation trả conflict; không recreate missing Card/progress |

### Typed result contract

| Code | State tương thích | Ý nghĩa |
|---|---|---|
| `PROGRESS_APPLIED` | `applied` | Snapshot material đã commit candidate state và bump revision |
| `FORCED_PROGRESS_APPLIED` | `applied` | Explicit resync override đã apply và bump revision |
| `PROGRESS_UNCHANGED` | `unchanged` | Hash/state giống nhau; zero progress side effect |
| `PROGRESS_STALE` | `stale` | Legacy snapshot cũ hơn state hiện tại; no-op |
| `LOCAL_PROGRESS_CHANGED` | `local_conflict` | Native/local revision lệch snapshot base |
| `SOURCE_SNAPSHOT_CHANGED` | `source_conflict` | External base hash không còn là current hash |
| `AMBIGUOUS_PROGRESS_ORDER` | `conflict` | Legacy timestamp thiếu/bằng nhau nhưng payload khác nên không thể order an toàn |
| `CONCURRENT_PROGRESS_WRITE` | `conflict` | Race tạo first progress row/unique key |
| `ANKI_DUE_UNRESOLVED` | `due_unresolved` | Không map được source day; toàn progress mutation của record là no-op |

### Compatibility decision

- Không đổi URL, HTTP method, package envelope hoặc field hiện có.
- `baseSnapshotHash`, `serverSnapshotHash`, `code`, `legacy_unversioned` và legacy `progressResults` là additive.
- First-party React sync gửi base hash ngay trong P1-02.3. Client cũ vẫn chạy nhưng server đánh dấu result unversioned; hard-require base hash chỉ được xem xét trong P2-07 wire-version policy.
- Không thêm model/migration/tombstone trong Phase 1.

### Output bàn giao P1-02.2

```text
Task ID: P1-02.2
Primary outcome: Approved pairwise priority, revision, idempotency and typed-result contract for all inventoried writers.
Runtime change: none
Contract/API behavior changed: additive fields/codes approved for implementation; no endpoint removal or required-field break.
Verification: every G1–G9 inventory gap has an explicit rule above.
Rollback path: revert the documentation-only decision commit before P1-02.3 lands.
Known limitations: legacy clients without baseSnapshotHash remain compatibility-unversioned until the P2-07 wire decision.
Follow-up task IDs: P1-02.3, P1-02.4, P1-03, P2-07.
```

## Output đầu ra bắt buộc

- Mutation inventory table đầy đủ.
- Approved conflict/priority matrix.
- Code áp dụng revision semantics cho in-scope paths.
- Typed conflict/result codes và tests.
- Provenance mapping native vs snapshot vs revlog vs repair.
- Remaining unknowns cho production data/history completeness.

## Acceptance criteria

- Không external path nào silently overwrite một newer committed state.
- Idempotent replay không increment revision hoặc tạo duplicate event ngoài contract.
- Open session conflict được phát hiện theo frozen base revision.
- Source/local clone identity không bị collapse sai và source Notes/Cards không bị mutate.
- Không giả nhãn imported snapshot thành native Algorithm execution.

## Verification

```text
python scripts/run_tests.py --module study --backend-only
python scripts/run_tests.py --module connect_mcp --backend-only
python scripts/run_tests.py --module decks,flashcards --backend-only
```

## Rollback

Không đổi schema. Có thể feature-flag conflict enforcement theo external path nếu cần rollout, nhưng không được quay lại silent last-write-wins sau khi task được đóng.

## Không làm trong task này

- Không thiết kế learner/Note progress.
- Không reconstruct state từ deleted import staging.
- Không thay đổi clone model thành physical copy.
- Không triển khai Algorithm switching.
