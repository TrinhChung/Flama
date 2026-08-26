# Kế hoạch hậu-P0: tối ưu shared-deck install và hardening canary `2×4`

> Ngày: 2026-08-26  
> Trạng thái: IMPLEMENTED IN CODE — chờ migrate/backfill và canary soak trên MySQL/VPS  
> Phạm vi: marketplace shared deck, logical-overlay clone, market stats, preview samples,
> process-local security state, Gunicorn/MySQL/Redis deployment  
> Điều tra nền:
> [`SHARED_DECK_INSTALL_PERFORMANCE_INVESTIGATION_2026-08-25.md`](SHARED_DECK_INSTALL_PERFORMANCE_INVESTIGATION_2026-08-25.md)

## 0. Trạng thái triển khai 2026-08-26

Đã triển khai trong code:

- P0 fail-fast cho listing chưa có release, seed fail transaction nếu initial release lỗi;
- atomic install counters và qualified state trên từng Deck/NoteType install;
- clone tree batched có rollback flag `recursive`;
- canonical NoteType pointer trên read/install/checkout, mutation guard và publish backstop;
- preview samples reconstruct từ immutable release và cache theo release/schema version;
- Redis shared state cho login limiter, MCP limiter/preview consume-once; MCP lifetime quota dùng
  conditional atomic SQL;
- DB pool bounds, Redis/systemd/CI/deploy configuration và các CLI audit/reconcile/backfill.

Validation local: migration upgrade/downgrade smoke pass; cây 111 node dùng 5 `SELECT`; backend
suite có 631/633 pass trong lần full-run đầu, hai test còn lại là expectation infer-on-read cũ và đã
pass sau khi chuyển sang contract pointer bắt buộc. MySQL staging, production backfill, load matrix
và soak 48 giờ vẫn là gate vận hành bắt buộc; chưa được coi là hoàn tất chỉ từ validation local.

## 1. Quyết định tổng thể

Hai workstream được chạy sau khi P0 đạt gate, có thể triển khai song song nhưng phải
gặp nhau tại cùng một production-promotion gate:

1. **Workstream A — hậu-P0:** loại N+1 market stats, batch clone Deck tree, biến
   `source_note_type_id` thành write-time invariant và thay full-scan sample bằng cache
   gắn với release.
2. **Workstream B — canary `2×4`:** giữ nguyên `2 Gunicorn process × 4 gthread`, không
   tăng worker/thread/timeout; externalize state ảnh hưởng correctness/security trước
   khi coi multi-worker là topology lâu dài.

Các quyết định kiến trúc:

- giữ nguyên logical-overlay: install chỉ tạo learner Deck shells và
  `DeckCloneDeckMap`, không copy hoặc mutate source `Note`/`Card`;
- bản P0 dùng `COUNT(...)` cho `install_count` và `LIMIT 20` cho sample chỉ là
  containment; không phải trạng thái đích;
- `install_count` dùng atomic delta trong cùng transaction với install/uninstall;
- `active_usage_count` được dẫn xuất từ trạng thái qualified trên từng install, có
  reconciliation làm safety net;
- source NoteType được kiểm chứng khi tạo/publish/mutate, không infer bằng full scan
  trong GET/detail/install/checkout;
- sample là derived cache trên `DeckMarketplaceItem`, keyed bằng current release;
  không sửa metadata của `DeckRelease` đã publish;
- Redis + atomic server-side operation là shared backend cho rate limit và MCP preview;
  MySQL vẫn là source of truth cho lifetime quota của MCP token;
- nếu shared state gặp lỗi nghiêm trọng, rollback vận hành là `1×4`; không tiếp tục
  `2×4` với local-only security state rồi gọi đó là cấu hình ổn định.

## 2. Gate bắt buộc trước khi bắt đầu hậu-P0

P0 chỉ được coi là hoàn tất khi đồng thời thỏa mãn:

- learner install không còn gọi initial-release publisher;
- listing chưa có `current_release_id` fail-fast bằng stable error/HTTP 503 và tạo
  **zero** `deck_release_*`, `deck_installs`, Deck hoặc map rows;
- tất cả đường free, paid entitlement, retry và internal caller dùng cùng service guard;
- các listing visible cũ đã được bootstrap có kiểm soát hoặc cố ý ở trạng thái unready;
- seed/publish không thể commit listing visible thiếu release ngoài explicit preparing
  workflow;
- focused tests và MySQL 8 staging proof của P0 đều pass;
- production không còn worker timeout/restart bất thường từ request tạo release.

Không bắt đầu backfill/migration của kế hoạch này trong cùng deployment với P0. Cần ít
nhất một release P0 độc lập để rollback không kéo theo schema hoặc behavior hậu-P0.

## 3. Invariant không được phá vỡ

1. Source `Note.id`/`Card.id`, release pointer và learner `CardProgress` phải giữ nguyên.
2. Clone không được ghi vào source content; local edit tiếp tục đi qua overlay rows.
3. Mỗi source Deck node trong install có đúng một learner Deck node và một
   `DeckCloneDeckMap`.
4. Một visible listing có đúng một canonical `source_note_type_id`; release không được
   âm thầm bỏ qua Note có NoteType khác.
5. Published release là immutable. Cache preview có thể rebuild nhưng phải chỉ chứa dữ
   liệu được reconstruct tại `current_release_id`, không chứa owner working edits.
6. Counter/cache mới là derived data. Install/review/progress/release rows vẫn là source
   of truth và luôn phải có reconciliation path.
7. Mọi migration là additive trước, backfill idempotent theo batch, cutover bằng feature
   flag và không downgrade schema trong incident rollback.

## 4. Thứ tự triển khai đề xuất

| Thứ tự | Ticket/PR | Nội dung | Phụ thuộc | Cỡ việc |
|---:|---|---|---|---|
| 0 | `OBS-01` | Structured request/install timings, query-budget harness, MySQL fixture | P0 pass | M |
| 1 | `STATS-01` | Atomic install/rating fast path, bỏ full recompute khỏi request | `OBS-01` | M |
| 2 | `TREE-01` | Preload + batch clone Deck tree | `OBS-01` | M |
| 3 | `TYPE-01` | Strict NoteType contract ở mutation/publish boundary | P0, `OBS-01` | L |
| 4 | `DATA-01` | Expand migration cho active state và release-keyed sample cache | `STATS-01`, `TYPE-01` | M |
| 5 | `DATA-02` | Backfill, shadow compare, reconciliation CLI | `DATA-01` | L |
| 6 | `CUTOVER-01` | Qualified stats + release cache authoritative | `DATA-02` | M |
| 7 | `RATE-01` | Redis foundation + shadow rate limiter | P0, `OBS-01` | L |
| 8 | `RATE-02` | Login authoritative, MCP preview/quota hardening | `RATE-01` | L |
| 9 | `CANARY-01` | MySQL 8 load matrix, Redis fault test, production soak `2×4` | tất cả gate trên | L + 48h soak |
| 10 | `CONTRACT-01` | Xóa hot paths cũ sau 1–2 tuần không mismatch | successful soak | M |

`STATS-01`, `TREE-01`, `TYPE-01` và `RATE-01` có thể phát triển song song. Không gộp
chúng thành một PR lớn; mỗi PR phải có flag/rollback độc lập.

---

## 5. Workstream A — tối ưu sau P0

### A0. Baseline và observability

Thêm structured log tối thiểu cho install:

- release ID, request ID, normalized route, status, duration, worker PID;
- phase duration: readiness guard, NoteType resolution, NoteType clone, Deck tree clone,
  stats, audit và commit;
- source Deck node count, install-created/already-installed, không log content/user PII;
- SQL query-count harness bằng SQLAlchemy events trong test/benchmark.

Fixture chuẩn trên MySQL 8:

- 10.148 Notes, 16 fields, 171 Deck nodes;
- current published release sẵn có;
- lịch sử `H = 1`, `100`, `1.000` installs cho stats benchmark;
- tree shapes: 1 node, wide, deep, 171 và 1.000 nodes;
- cold-cache và warm-cache runs.

Baseline phải tách riêng: NoteType binding, tree clone, stats, detail sample và full
release-pinned install. Không dùng lại timing 105 giây của request từng tạo initial release
để đánh giá hậu-P0.

### A1. Market stats: bỏ N+1 và bảo toàn counter dưới concurrency

#### Hiện trạng cần thay

Các hot paths nằm tại:

- `app/services/flashcards_share_service.py`:
  `recompute_note_type_market_stats`, `recompute_deck_item_market_stats`,
  `ensure_note_type_install_for_user`, `install_shared_deck_item_for_user`, các
  `touch_*_install_usage` và `is_*_install_active`;
- `app/repositories/flashcards_share_repository.py`: load toàn bộ installs rồi count
  Note/reps theo từng installer;
- callers trong study, study-session, content/import, rating và deck deletion services.

P0 `deck_item.install_count = DeckInstall.query...count()` đã bounded hơn full stats,
nhưng vẫn tăng theo lịch sử và có thể lost-update khi hai transaction cùng count rồi ghi
giá trị cũ.

#### Trạng thái đích

Tách bốn trách nhiệm đang bị gộp trong `recompute_*`:

1. **Install count:** atomic `+1/-N` trên parent row, chỉ sau khi unique install insert
   thực sự mới được tạo và trong cùng transaction.
2. **Rating:** create/update review chỉ chạy một aggregate `AVG/COUNT` trên review table;
   không load installs hoặc activity.
3. **Per-install activity:** evaluate đúng install bị event tác động và persist kết quả.
4. **Reconciliation:** CLI/timer tính lại derived state/counters theo batch từ source
   tables và sửa drift.

Schema expand trên cả `deck_installs` và `note_type_installs`:

- `market_active BOOLEAN NULL` — `NULL` nghĩa là chưa evaluate, khác `FALSE`;
- `market_active_evaluated_at DATETIME NULL`;
- `market_active_policy_version SMALLINT NULL`;
- index candidate `(deck_item_id, market_active)` và
  `(source_note_type_id, market_active)`;
- index `(user_id, installed_note_type_id)` để resolve đúng cả source và installed-copy
  NoteType identity.

Chỉ tạo composite index sau `EXPLAIN ANALYZE` trên MySQL. Migration expand không đặt
`NOT NULL` ngay; contract migration mới chuyển `market_active` sang
`NOT NULL DEFAULT 0` sau backfill/cutover ổn định.

#### Transaction và concurrency contract

Install mới:

1. unique constraint `(deck_item_id, user_id)` hoặc
   `(source_note_type_id, user_id)` quyết định created/already-installed;
2. tạo install và clone data;
3. atomic update `install_count = install_count + 1` trên đúng parent;
4. commit một lần; rollback/deadlock rollback cả install và delta;
5. retry bắt duplicate trả existing install và không increment lần hai.

Uninstall/purge phải group số rows theo parent **trước** bulk delete rồi atomic decrement
trong cùng transaction. Không dựa vào ORM delete event vì code hiện có bulk delete paths
bỏ qua event hooks. Dùng `GREATEST(install_count - :delta, 0)` và để reconciliation phát
hiện mọi mismatch thay vì che source-of-truth lỗi.

Active transition:

1. lock một install row cần evaluate;
2. tính predicate bằng bounded queries của đúng user/install;
3. nếu state đổi, cập nhật install rồi atomic `active_usage_count +/- 1` trên parent;
4. luôn lock theo thứ tự `install row → parent row` để giảm deadlock;
5. timer hằng ngày xử lý điều kiện elapsed-days và reconcile drift.

NoteType có hai identity: logical-overlay study dùng source Card/Note identity, còn
standalone installed NoteType/local content dùng `installed_note_type_id`. Resolver và
evaluator phải nhận context rõ ràng và cover cả hai; không đổi mù lookup từ source sang
installed hoặc ngược lại.

Trước backfill phải chốt một policy version duy nhất. Code hiện có cả `5 notes / 1 rep /
7 days` và `3 / 3 / 3`. Khuyến nghị ban đầu là NoteType `3/3/3`, Deck `3 reps`, vì đây
là default/constants đang dùng rộng hơn; nhưng đây là explicit product/engineering
decision gate, không được âm thầm chọn trong migration.

#### Reconciliation

Thêm CLI dạng:

```text
flask market-stats-reconcile --kind all --limit 10000
flask market-stats-reconcile --kind all --limit 10000 --apply
```

- keyset paginate, commit mỗi 100–500 rows;
- rerunnable/idempotent, lưu cursor/counters trong log;
- batched/grouped aggregate là oracle cho backfill, không chạy trong request;
- kiểm tra ba invariant:
  `install_count = COUNT(installs)`,
  `active_usage_count = COUNT(market_active=1)`,
  rating cache = aggregate review table.

#### Test và acceptance

- 20 distinct users install đồng thời: counter chính xác;
- hai request cùng user/item: đúng một install và một increment;
- injected deadlock/rollback: không orphan Deck/map và không lệch counter;
- Deck install dùng chung NoteTypeInstall: NoteType chỉ increment một lần;
- uninstall, delete local Deck, reset và admin purge decrement đúng;
- rating create/update không gọi install/activity scan;
- active transition cover direct study, study session, note create/import/delete và
  elapsed-days timer;
- deliberately corrupt counter rồi reconcile: sửa đúng, chạy lần hai là no-op;
- query count của install không đổi khi `H` tăng từ 1 lên 1.000.

### A2. Batch clone Deck tree

#### Thiết kế

Thay recursion trong `clone_deck_subtree()` bằng pipeline:

1. preload source tree breadth-first; số SELECT tăng theo tree depth, không theo node;
2. build adjacency map trong memory, sort siblings bằng `(position, id)`;
3. validate root tồn tại, owner/provenance hợp lệ, không duplicate/cycle/missing parent;
4. query learner root max position đúng một lần, scoped theo learner;
5. gán dense child position trong memory, giữ nguyên visual sibling order;
6. tạo Deck objects theo level, flush một lần mỗi level để lấy MySQL AUTO_INCREMENT IDs;
7. tạo `DeckCloneDeckMap` theo chunk sau khi IDs có sẵn;
8. set `install.local_deck_id` và commit trong transaction hiện có.

Không suy đoán IDs là một dải AUTO_INCREMENT liên tục: concurrent MySQL inserts và
`innodb_autoinc_lock_mode` làm giả định đó không an toàn. Không bỏ learner Deck shells vì
việc đó phá API/tree UI và overlay contract.

Feature flag:

```text
SHARED_DECK_TREE_CLONE_MODE=recursive|batched
```

#### Test và acceptance

- topology, name, description, NoteType mapping và sibling order giống behavior cũ;
- đúng `N` learner Decks và `N` maps; learner Note/Card delta bằng 0;
- invalid/cyclic/missing source rollback toàn bộ;
- duplicate concurrent request không để orphan shells/maps;
- source tree SELECT `<= depth + 2`, sibling MAX query đúng một lần;
- tree 171–213 nodes có dưới khoảng 30 SELECTs; total statements còn lại chủ yếu là
  required Deck/map inserts;
- tăng Notes từ 100 lên 10k không làm tree-clone phase tăng quá 10–15%;
- target component p95 dưới 1 giây trên staging 2 vCPU, threshold cuối freeze theo
  baseline MySQL 8.

### A3. Source NoteType: inference thành write-time contract

#### Contract

`DeckMarketplaceItem.source_note_type_id` là canonical pointer và phải:

- tồn tại, thuộc source owner và không phải installed-copy lineage;
- có ít nhất một Template;
- không đổi sau listing creation;
- khớp mọi Note thuộc source subtree.

Install/detail/checkout chỉ kiểm tra pointer + owner/provenance/template bằng O(1) lookups;
không gọi `resolve_single_note_type_for_deck()` hoặc commit repair từ GET.

Mọi mutation boundary tạo/move/import/sync Note phải tìm các listing phủ Deck đó bằng
ancestor lookup và reject NoteType khác pointer, tối thiểu tại:

- Content API và Browse;
- package/import API;
- MCP tools;
- Flama Connect và note sync;
- deck move/new child flows có thể đưa Note vào source subtree.

Publish chạy defense-in-depth anti-mismatch query trước khi tạo bất kỳ release row nào:

```text
EXISTS Note trong source subtree
WHERE owner != expected owner OR note_type_id != source_note_type_id
```

Nếu mismatch, trả stable 409 như `DECK_SOURCE_NOTETYPE_MISMATCH` và zero release writes.
Điều này bắt buộc vì release repository hiện lọc theo pointer; nếu chỉ trust pointer,
mixed descendant Notes có thể bị bỏ khỏi release một cách im lặng.

Legacy CLI/audit:

- 0 NoteTypes: report unready/private, không tự đoán;
- đúng 1: bind pointer trong apply mode;
- hơn 1: quarantine/report conflict, không tự sửa content;
- dry-run mặc định, keyset/batch và audit đầy đủ.

Candidate index `(user_id, deck_id, note_type_id)` chỉ thêm sau MySQL
`EXPLAIN ANALYZE`; install/read path không được giữ scan rồi dùng index để che kiến trúc.

Feature flag:

```text
DECK_SOURCE_NOTETYPE_GUARD_MODE=shadow|strict
```

Shadow ghi mismatch nhưng không thay response; strict chỉ bật sau audit/backfill sạch.

#### Test và acceptance

- listing có pointer: install/detail/checkout không phát sinh distinct/full Note scan;
- mixed NoteType ở hai child Deck khác nhau bị chặn trên mọi mutation surface;
- hand-inserted mismatch bị publish backstop bắt và không tạo release;
- GET/detail không commit source repair;
- legacy 0/1/>1 cases đúng contract;
- direct-source owner và installed clone flows đều giữ behavior hợp lệ.

### A4. Bỏ full-scan sample bằng release-keyed derived cache

#### Schema và cache contract

Expand `deck_marketplace_items` bằng:

- `preview_samples_release_id VARCHAR(36) NULL`;
- named FK tới `deck_releases.id`, `ON DELETE SET NULL`, dùng migration mechanics giống
  vòng FK `current_release_id`;
- `preview_samples_schema_version SMALLINT NULL`;
- `preview_samples_json JSON NULL`.

Cache chỉ hợp lệ khi:

```text
preview_samples_release_id == current_release_id
AND preview_samples_schema_version == 1
```

Payload là tối đa năm ordered objects:

```json
{"note_id": "...", "word": "...", "reading": "...", "meaning": "..."}
```

Áp per-string và total-byte cap trước khi persist. JSON phù hợp ở đây vì payload nhỏ,
ordered, không query theo element và hoàn toàn rebuildable. Không lưu vào `DeckRelease`:
backfill như vậy sẽ mutate metadata của một release đã publish.

#### Write/read behavior

- initial publish lấy candidates từ working state đã materialize;
- subsequent publish reuse cached IDs còn active, reserialize giá trị tại target release,
  rồi refill vacancy bằng bounded/keyset query;
- publish swap `current_release_id` và cache release ID/payload trong cùng transaction;
- detail đọc cache O(1), không shuffle và không query live source Notes;
- template-preview POST chỉ nhận sample ID thuộc cache và reconstruct field values tại
  current release;
- unpublished owner edit không được làm đổi detail/sample cho đến lần publish tiếp theo.

Backfill listing hiện có theo item ID batches, chọn membership đang active tại current
release và reconstruct historical field values qua release service. Không đọc
`Note.field_values` live và không sửa release rows.

Rollout modes:

```text
MARKETPLACE_SAMPLE_MODE=bounded_live|shadow_cache|release_cache
```

- expand: P0 `LIMIT 20` là bounded fallback và ghi cache mismatch metric;
- shadow: trả fallback nhưng build/compare cache;
- cutover: cache miss/mismatch trả `[]` hoặc preparing state và enqueue/reconcile;
  tuyệt đối không quay lại full scan;
- contract: xóa random shuffle/full live-scan path.

#### Test và acceptance

- repeated GET giữ nguyên sample IDs/order qua worker restart;
- unpublished edit không leak, publish mới đổi cache atomically;
- cached Note bị remove được refill đúng;
- 100/10k/50k Notes có detail query count và rows examined gần như không đổi;
- cache miss/mismatch không load toàn bộ Notes;
- detail p95 `<=250 ms` trên staging hoặc cải thiện ít nhất 80% so với 10k baseline;
- response tối đa 5 samples và luôn trong byte budget.

### A5. Migration lifecycle chung

1. **Expand:** thêm nullable columns/FKs/indexes; old code bỏ qua; deploy feature flags ở
   mode cũ/shadow.
2. **Backfill:** CLI keyset batches 100–500, commit từng batch, rerunnable; không chạy
   trong Alembic hoặc startup.
3. **Dual-read/validate:** shadow compare active state, counters và sample cache; dashboard
   mismatch/drift.
4. **Cutover:** event-qualified stats, strict NoteType guard, batched tree và release
   cache authoritative.
5. **Contract:** sau tối thiểu 1–2 tuần không mismatch, đặt defaults/NOT NULL phù hợp và
   xóa GET repair/full recompute/live sample scan. Giữ reconciliation CLI.

MySQL notes:

- additive nullable columns trên MySQL 8.0.46 có thể dùng instant DDL nhưng phải kiểm tra
  SQL Alembic sinh ra, không giả định;
- composite-index build vẫn scan table/I/O, triển khai low-traffic và theo dõi replica/
  redo/lock nếu có;
- atomic parent delta tạo short row lock và serialize burst trên cùng item; transaction
  phải ngắn, không giữ lock trong tree clone hay network call;
- migration phải pass cả MySQL 8 upgrade/downgrade smoke và SQLite tests, nhưng incident
  rollback chỉ đổi app flag/release, không chạy downgrade.

---

## 6. Workstream B — hardening canary `2×4`

### B0. Freeze topology và audit mutable state

Giữ nguyên:

```text
workers=2
threads=4
worker_class=gthread
timeout=120
```

Không tăng timeout để che request unbounded. `Nice=5`/`CPUWeight=100` chỉ là priority,
không phải CPU/RAM limit.

Các state đã audit:

| State | Hiện trạng | Quyết định |
|---|---|---|
| Login attempts/lockouts | module-level dict, mỗi worker một quota | hard blocker; Redis authoritative |
| MCP short-window limiter | module-level deque, mặc định disabled | externalize trước khi bật |
| MCP preview token | process-local, validate/consume không atomic | hard blocker; Redis TTL + atomic claim |
| MCP lifetime quota | ORM read-modify-write `used_requests` | hard blocker; conditional atomic MySQL update |
| Connect limiter | process-local nhưng Connect hiện 1 worker | không scale Connect trước shared backend |
| Renderer template cache | bounded 512 + lock | chấp nhận process-local |
| Renderer preview cache | unbounded, get/set không lock | bound + TTL/LRU + lock trước soak dài |
| Flask session/CSRF | signed cookie + shared `SECRET_KEY` | multi-worker safe |
| DB/idempotency rows | shared MySQL + unique constraints | multi-worker safe theo transaction contract |

`LOGIN_RATE_LIMIT_*` hiện chỉ dùng hardcoded defaults trong settings; phải đọc env thật
trước shadow/cutover.

### B1. Shared-state architecture

Tạo hai abstraction tách biệt:

- `RateLimitStore`: `local`, `shadow_redis`, `redis`;
- `McpPreviewStore`: `local`, `redis`.

Không ghép chúng thành một interface vì failure semantics khác nhau.

Redis foundation cần:

- pinned Redis client dependency trong `requirements.txt`;
- config URL/ACL, short connect/socket timeout, versioned key prefix, HMAC salt;
- dedicated namespace và TTL cho mọi key;
- verify production Redis ownership, bind/ACL, `maxmemory`, eviction policy và service
  unit trước khi dùng; việc Redis đang chạy trên VPS chưa phải operational contract;
- dùng Redis server time trong atomic script, không dùng clock riêng của worker;
- không đưa raw email/IP/token vào keys/log/metric labels; bucket identity dùng HMAC;
- `evicted_keys=0`; rate-limit/preview data là ephemeral nên Redis restart có thể buộc
  preview lại, không cần biến nó thành durable business database.

Thuật toán:

- login failure/lockout: small ZSET sliding windows + lockout TTL, atomic server-side;
- MCP/Connect high-volume bucket: chọn bounded token-bucket/GCRA hoặc fixed counter
  trước khi enable; không lưu mặc định 100.000 timestamp/token/phút;
- success semantics ở cutover đầu giữ parity để giảm risk. Việc success đang xóa cả IP
  và email bucket là security-hardening ticket riêng; sau parity cutover nên đổi thành
  chỉ clear account bucket, không reset IP abuse history.

Nginx `limit_req` có thể là lớp coarse IP bên ngoài password hashing, nhưng không thay
thế email/token/action-aware Redis authority.

### B2. Failure semantics

- **Login:** mirror local limiter liên tục làm degraded fallback. Redis timeout dùng
  local conservative policy + critical alert; không fail-open hoàn toàn và cũng không
  làm toàn bộ login outage.
- **MCP bearer limiter khi enabled:** Redis lỗi trả 503
  `RATE_LIMIT_BACKEND_UNAVAILABLE`, không giả thành 429.
- **MCP preview:** Redis lỗi fail-closed 503; không fallback local dưới multi-worker.
- **Connect:** giữ coarse Nginx IP layer; Redis chịu token/user/action buckets trước khi
  tăng Connect workers.
- Redis calls dùng timeout ngắn và circuit breaker; không retry dài trong request.

### B3. MCP correctness đi kèm

Preview record TTL 600 giây. Execute dùng atomic compare-and-delete/claim:

1. so user, action, resource ID và resource version;
2. sai owner/action không consume;
3. đúng thì delete/claim trước mutation, nên hai execute đồng thời chỉ một request thắng;
4. nếu mutation sau claim thất bại, client preview lại — an toàn hơn reuse token có trạng
   thái không chắc chắn.

Lifetime quota giữ MySQL làm source of truth và dùng một conditional update:

```sql
UPDATE mcp_access_tokens
SET used_requests = used_requests + 1,
    last_used_at = :now
WHERE id = :id
  AND revoked = 0
  AND (expires_at IS NULL OR expires_at > :now)
  AND used_requests < max_requests;
```

Chỉ `rowcount=1` mới cho request tiếp tục. Cách này tránh lost update giữa workers và
không cần schema migration.

### B4. Repo/deployment changes cần có

Các vùng dự kiến thay đổi:

- `app/services/login_rate_limit_service.py`;
- `app/services/mcp_access_token_service.py` và MCP token repository;
- `app/services/mcp_preview_service.py`;
- `app/connect/__init__.py`;
- `app/settings.py`, `.env_example`, `requirements.txt`;
- `deploy/sync_managed_env.py`, `deploy/bootstrap_hostinger.sh`;
- `deploy/flama.service`, `deploy/flama-connect.service`;
- `.github/workflows/ci.yml` và `.github/workflows/deploy.yml`.

Systemd dùng `Wants/After=redis-server.service`; không dùng Redis như silent implicit
dependency. Deployment preflight phải PING/auth Redis khi backend authoritative.
`/api/health` chỉ đang kiểm tra `SELECT 1`; authoritative health cần kiểm tra dependency
mode tương ứng và release fingerprint.

`TimeoutStopSec=30` ngắn hơn Gunicorn timeout 120. Trước promotion cần drain/reload
strategy hoặc tăng stop grace đủ để deploy không cưỡng bức kill request đang chạy.

### B5. Shadow và cutover

#### Expand/shadow

```text
RATE_LIMIT_BACKEND=shadow_redis
MCP_PREVIEW_BACKEND=local
```

- local quyết định response;
- check/failure/success mirror sang Redis;
- log decision mismatch, Redis latency/error, fallback/circuit events, key count/memory
  và eviction;
- shadow ít nhất dài hơn lockout window, khuyến nghị 24 giờ + synthetic cross-worker
  traffic;
- `Redis deny / local allow` là expected evidence của process-local bug, không phải lý do
  giữ local.

MCP preview chuyển sang Redis authoritative ngay sau integration test riêng; restart làm
preview cũ mất hiệu lực chỉ yêu cầu người dùng preview lại.

#### Cutover

```text
RATE_LIMIT_BACKEND=redis
MCP_PREVIEW_BACKEND=redis
```

- login Redis authoritative, local mirror chỉ làm degraded fallback;
- MCP limiter chỉ bật sau khi threshold/burst được quyết định và load-test;
- main + Connect dùng cùng policy/namespace khi Connect migration hoàn tất;
- vẫn giữ Gunicorn `2×4`, không tăng topology.

### B6. SQLAlchemy connection budget

Hiện engine chỉ set `pool_pre_ping`/`pool_recycle`; QueuePool defaults tạo configured cap
lý thuyết khoảng 30 connections cho hai web workers, thêm 15 cho Connect và transient
CLI pools. Actual web concurrency thấp hơn vì chỉ có tám threads, nhưng capacity chưa
được quản trị rõ.

Công thức gate:

```text
web_workers × (web_pool_size + web_overflow)
+ connect_workers × (connect_pool_size + connect_overflow)
+ concurrent deploy/CLI jobs
+ operational reserve
<= 70% × MySQL max_connections
```

Candidate để benchmark, chưa hardcode trước khi đọc production:

- web: `pool_size=4`, `max_overflow=1`, `pool_timeout=5–10s`;
- Connect: `pool_size=1–2`, `max_overflow=1`;
- giữ `pool_pre_ping=true`, `pool_recycle=1800`.

Main và Connect đang cùng dùng `build_app_config`; cần service-specific override hoặc
systemd env riêng. Gate: zero pool timeout/`Too many connections`, peak connections dưới
70% `max_connections`, `Threads_running` không vượt vCPU lâu dài và không có lock wait
trên 1 giây trong normal scenario.

### B7. Test bắt buộc

- unit parity: window boundary, lockout TTL, email/IP normalization, success reset;
- Redis integration thật trong CI, không chỉ fake;
- nhiều OS processes cùng Redis: global threshold chính xác;
- raw PII không xuất hiện trong Redis keys/logs;
- Redis outage: login local fallback, MCP/preview 503 đúng contract;
- preview create ở worker A, consume ở B; second consume fail; wrong owner/action không
  consume; stale version fail;
- parallel MCP lifetime quota không lost update/vượt max;
- `X-Forwarded-For` spoof không bypass trusted proxy policy;
- renderer preview-cache memory soak;
- focused suites: auth security, MCP access/OAuth regression, Connect auth và managed
  environment sync.

### B8. Load-test matrix cho canary

Staging phải dùng MySQL 8, Redis và resource limit tương đương VPS `2 vCPU / 8 GB`, chạy
đúng service command `2×4`.

| Scenario | Tải |
|---|---|
| Baseline | 4 users chạy session/dashboard/stats/marketplace/browse trong 15 phút |
| Large install | 10 release-pinned N1 installs tuần tự bằng fresh users |
| Mixed | 1 large install + 4 users thường trong 15 phút |
| Same item | 2 users install cùng item đồng thời, lặp 10 vòng |
| Duplicate | 2 request đồng thời cùng user/item; chỉ một install |
| Saturation | 8 installs đồng thời × 3 vòng, staging only |
| Unready | 8 installs listing thiếu release; tất cả fail-fast, zero writes |
| Detail | 4 users gọi detail trước/sau install, 100/10k/50k fixture |
| Limiter | fresh TCP connections đi qua cả hai PIDs, threshold vẫn global |
| Redis fault | dừng Redis staging 60 giây rồi phục hồi |
| Soak | mixed ordinary traffic tối thiểu 60 phút |

Sau shared-state cutover, benchmark `1×4`, `2×1`, `2×2`, `2×4`; không thử hơn hai
workers trên VPS hai vCPU. Chọn topology nhỏ nhất đạt gate, không mặc định threads nhiều
hơn là nhanh hơn cho Python CPU-bound work.

### B9. Promotion/rollback gates

Containment rollback ngay nếu có một trong các điều kiện:

- worker timeout, unexpected replacement, SIGKILL/OOM;
- 5xx trên 1% trong 5 phút;
- ordinary p99 trên 2 lần baseline trong 10 phút;
- CPU trên 90% liên tục 60 giây, normalized load/vCPU trên 1 trong 3 phút hoặc I/O wait
  trên 15% trong 60 giây;
- pool timeout/MySQL connection exhaustion;
- limiter cho phép vượt global threshold.

Chỉ promote `2×4` thành topology lâu dài sau ít nhất 48 giờ authoritative soak và đạt:

- zero worker timeout/restart/OOM;
- 5xx dưới 0,5%;
- ordinary p95 không tăng quá 20% so baseline, p95 dưới 1 giây, p99 dưới 2 giây;
- release-pinned N1 full install p95 dưới 5 giây, p99 dưới 10 giây;
- unversioned install p95 dưới 300 ms và zero writes;
- mixed-load CPU p95 dưới 75%, không có >90% sustained; I/O wait p95 dưới 10%;
- RSS không tăng đơn điệu, host luôn còn ít nhất 25% memory;
- Redis steady-state fallback/error/eviction bằng 0, local Redis p99 dưới 10 ms;
- login/MCP thresholds và preview consume-once đúng 100% qua hai workers;
- MySQL usage dưới 70%, pool timeout bằng 0;
- Nginx/firewall/proxy trust path đã được xác minh.

Rollback:

1. lỗi riêng install: bật kill switch trả 503 trước;
2. lỗi feature hậu-P0: `qualified→shadow`, `batched→recursive`, `strict→shadow`,
   `release_cache→bounded_live`; không bật lại full stats/sample scan trong CPU incident;
3. Redis/shared-state lỗi nghiêm trọng: login degraded-local và đổi topology về `1×4`;
   MCP/preview vẫn fail-closed;
4. app regression: restore previous release symlink + systemd unit;
5. không Alembic downgrade, không xóa immutable release/checkpoints và chạy reconcile sau
   rollback.

## 7. Definition of done chung

Hai workstream chỉ hoàn tất khi:

- P0 guard vẫn pass toàn bộ negative/zero-write tests;
- install latency/query count không tăng theo Note count hoặc install history;
- clone tree giữ 100% overlay/pointer behavior;
- NoteType mismatch không thể đi qua supported mutation paths và publish backstop;
- detail không scan live source collection, không leak unpublished edits;
- stats/sample backfills chạy idempotent trên MySQL 8 và có zero mismatch sau reconcile;
- process-local security/correctness state đã externalize hoặc được chứng minh cache-only;
- `2×4` hoàn thành load matrix + 48 giờ soak, đạt toàn bộ promotion gate;
- rollback được diễn tập bằng feature flags và previous-release workflow.

## 8. Các decision gate còn phải chốt trước implementation

1. Canonical NoteType active policy: đề xuất `3 notes / 3 reps / 3 days`, Deck `3 reps`.
2. Redis ownership: dedicated instance/ACL/namespace, memory/eviction và alert ownership.
3. Login success reset policy: parity trước, sau đó không clear IP abuse bucket.
4. MCP short-window threshold/burst thực tế; giữ disabled cho đến khi benchmark xong.
5. Product response khi preview cache chưa sẵn: `[]` hay explicit preparing state.
6. MySQL composite indexes cuối cùng chỉ được chọn sau production-shaped
   `EXPLAIN ANALYZE`.
