# Kế hoạch triển khai bảng count cho analytics và Dashboard

**Cập nhật 06/10/2026:** Phase A và Phase B Dashboard owned-deck đã được triển khai trên worktree riêng và kiểm chứng DB local. Xem [kết quả, gate còn thiếu và chi phí tuyến tính](../reports/ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md), [runbook](../runbooks/ANALYTICS_COUNTS_RUNBOOK.md). Phần thiết kế bên dưới giữ mốc 05/10; chưa bật production.

Ngày: **05/10/2026** · Trạng thái: **DESIGN / đề xuất triển khai**, chưa tạo bảng hoặc đổi runtime. Đối chiếu code tại `0d4c293`, nhánh `refactor/frontend-fsd-renderer-boundary`; các thay đổi khác đang có trong workspace không thuộc thiết kế này.

**Đề xuất triển khai hai read model riêng:** daily count của lịch sử ReviewEvent để giảm quét lịch sử; snapshot count trạng thái từng deck để giảm quét Cards lặp lại ở Dashboard. Đợt đầu thêm **3 bảng lịch sử**. Đợt tiếp theo dự kiến thêm **3 bảng count/revision của deck**, sau khi hoàn tất kiểm kê invalidation và xác minh scope. Giữ ReviewEvent, state, receipts và history facts làm nguồn gốc; bảng mới có thể rebuild.

Thiết kế này cụ thể hóa [review tính khả thi](../plans/proposals/ANALYTICS_ROLLUP_FEASIBILITY_REVIEW_2026-10-04.md), đồng thời thay các giả định chưa được chứng minh trong [MASTER O(N) roadmap](../plans/O_N_PERFORMANCE_INVESTIGATION_ROADMAP.md). Đây là kế hoạch để chia PR và kiểm tra trước rollout; các tên bảng, cờ cấu hình và lệnh CLI được đánh dấu là **đề xuất**, chưa tồn tại trong ứng dụng.

## 1. Vì sao cần làm, và phạm vi lợi ích

| Bằng chứng đã có | Ý nghĩa đối với kế hoạch | Giới hạn |
|---|---|---|
| Production ngày 04/10: User 1 có **118.359 ReviewEvents**, trong năm học 2026 có **76.543** | Lịch sử đủ lớn để daily aggregate có ích | Inventory cũ, không phải phép đo production mới ngày 05/10 |
| Baseline cũ: history daily aggregate khoảng **250 ms**; Dashboard count khoảng **730 ms** | Có hai query nặng độc lập cần hai giải pháp | Không cộng thành thời gian UI chắc chắn tiết kiệm được; cần đo lại release hiện tại |
| Local MySQL, 100k events: optimized covering-index raw khoảng **72,31 ms**, summary khoảng **4,89 ms** | Có cơ sở thử summary, kể cả khi so với raw đã tối ưu | Synthetic warm median; chưa đo write overhead hoặc latency production |

Nguồn: [production inventory](artifacts/count_rollup_production_inventory_20261004.json), [so sánh raw/index/summary](artifacts/review_rollup_raw_alternatives_20261004.json), [điều tra Dashboard](DASHBOARD_USER1_PERFORMANCE_INVESTIGATION_2026-10-04.md). Production lúc inventory: MySQL 8.0.46, 2 vCPU, khoảng 7,75 GiB RAM, buffer pool 128 MiB; không dùng cấu hình khác trong MASTER làm baseline.

Ký hiệu: `H` là số events; `A` là số ngày có review; `C` là Cards trong scope; `D` là decks; `S` là số ngày của streak; `W` là accepted events trong một transaction. Độ phức tạp dưới đây nói về lượng dữ liệu phải xử lý, chưa bao gồm B-tree, join, sort và IO.

| Consumer | Thay đổi dự kiến | Phần còn lại |
|---|---|---|
| Heatmap lịch sử collection/năm | `O(H_year)` → tối đa **365/366 daily rows** | Tạo series và response; phần heatmap future vẫn đọc state |
| Today lịch sử collection | Quét events trong ngày → đọc một daily row | Deck-subtree vẫn cần resolve membership hiện tại |
| Study-time theo deck/subtree | Raw events → direct attribution rows của mọi deck được chọn trong subtree | `O(D_scope + A_scope)`; gồm root/intermediate có events, không chỉ tree leaves |
| Streak | Events → collection active days | `O(A_lifetime)` lúc đầu; có thể đọc ngược đến gap `O(S)` sau parity |
| Dashboard deck counts | Lặp quét Cards → đọc snapshot khi hợp lệ | Cache miss/rebuild vẫn `O(C_dirty)`; cây và response vẫn `O(D)` |

## 2. Findings quyết định thiết kế

### F1 — Count lịch sử và count hiện tại có nguồn gốc khác nhau

- **Observed:** history query đếm mọi ReviewEvent; future due/daily load đọc progress hoặc Subject state hiện tại.
- **Evidence:** [stats_query_repository.py](../../app/repositories/stats_query_repository.py), [stats_today_future.py](../../app/services/stats_today_future.py), [deck_aggregation_service.py](../../app/services/deck_aggregation_service.py).
- **Concern / impact:** lấy daily history count thay due/new/learn hoặc load sẽ cho số sai dù query nhanh hơn.
- **Unknown:** tỷ lệ thời gian history/state trên release production mới; phải tách đo ở PR đầu.
- **Recommendation:** hai read model, hai rollout độc lập. Daily table không lưu queue counts hoặc interval load.

### F2 — Ngày học và attribution không bất biến tuyệt đối

- **Observed:** lịch sử được nhóm lại theo timezone/boundary có hiệu lực lúc query; deck purge đổi `ReviewEvent.deck_id` thành `NULL`.
- **Evidence:** [analytics routes](../../app/api/v1/analytics/routes.py), [stats_overview.py](../../app/services/stats_overview.py), [deck_management_service.py](../../app/services/deck_management_service.py).
- **Concern / impact:** `+1` vào ngày ghi event rồi giữ mãi sẽ sai khi đổi timezone; bucket deck cũ sẽ sai sau purge.
- **Unknown:** tần suất đổi policy/purge và chi phí rebuild của user lớn.
- **Recommendation:** versioned generation, policy fingerprint, mutator coverage; fallback raw trong thời gian rebuild chưa hợp lệ.

### F3 — Counter tạo thêm contention và yêu cầu backfill có barrier

- **Observed:** `lock_study_authority_route()` lấy User **FOR SHARE**, cho phép các Note khác nhau ghi đồng thời. ID được cấp không phải thứ tự commit.
- **Evidence:** [study_authority_repository.py](../../app/repositories/study_authority_repository.py), [review_event_repository.py](../../app/repositories/review_event_repository.py), [study_session_service.py](../../app/services/study_session_service.py).
- **Concern / impact:** `MAX(id)` không có barrier có thể bỏ sót transaction commit muộn; lấy counter lock giữa vòng review có thể đảo thứ tự khóa.
- **Unknown:** lock waits và p95 commit khi thêm shared daily row.
- **Recommendation:** admission/backfill bằng fresh User FOR UPDATE; projection finalizer chạy cuối outer transaction, sau các authority/content writes.

## 3. Lựa chọn phương án

| Phương án | Lợi ích | Chi phí / giới hạn | Quyết định |
|---|---|---|---|
| Raw query + covering index | Thay đổi nhỏ; không cần projection lifecycle | Vẫn xử lý `H_range`; thêm index storage/write; lợi ích tùy plan | Đo A/B làm đối chứng trước cutover, không mặc định FORCE INDEX |
| Cache response hoặc rebuild dirty days | Triển khai nhanh cho lượt đọc lặp | Miss vẫn raw; TTL/invalidation; nhiều worker cần cache chung; dữ liệu có thể cũ | Có thể bổ trợ; không đủ thay contract read-after-commit |
| **Synchronous daily summary** | Exact sau commit; không cần một outbox row/event | Counter lock, thêm writes, tích hợp mọi transaction owner | **Chọn cho Phase A**, chỉ cutover khi đạt write budget |
| Transactional outbox + projector | Gom writes, có thể giảm thời gian counter lock trong review | Outbox/dedup/checkpoint thêm storage và writes; lag; phải fallback hoặc bù tail | Phương án dự phòng nếu synchronous không đạt budget; thiết kế riêng trước chuyển |

Không thêm bảng fact mới sao chép từng ReviewEvent trong Phase A. Không purge hoặc archive history để triển khai count. Raw events vẫn được dùng cho replay, receipt verification, algorithm history cut và Connect provenance như [review tính khả thi](../plans/proposals/ANALYTICS_ROLLUP_FEASIBILITY_REVIEW_2026-10-04.md) đã xác minh.

## 4. Phase A — Schema lịch sử: 3 bảng

### 4.1. `review_analytics_heads`: điều phối từng user

Một row/user; giữ pointer generation và lock cuối transaction. `source_revision` tăng một lần/outer transaction có thay đổi các cột được projection sử dụng; **không dùng nó hoặc MAX(id) riêng lẻ làm bằng chứng đã backfill**.

### 4.2. `review_analytics_generations`: policy và checkpoint

Một row/user/generation. Policy bất biến trong generation: timezone đã resolve, boundary hour, phiên bản quy tắc grouping/passed-rating và phiên bản quy tắc timezone. `policy_hash` là SHA-256 của các giá trị chuẩn hóa đó; không hash giờ hiện tại hoặc mọi release ứng dụng.

Mã trạng thái đề xuất: `0 BUILDING`, `1 READY`, `2 DIRTY`, `3 FAILED`, `4 RETIRED`. Có tối đa một active và một building generation được cập nhật live cho mỗi user. Request chỉ dùng generation **READY và khớp policy**.

Transitions: BUILDING → READY/DIRTY/FAILED; READY → DIRTY/RETIRED; DIRTY/FAILED → RETIRED. Rebuild tạo generation ID mới, không reset DIRTY/FAILED về BUILDING để tránh tái dùng verification evidence cũ. `applied_source_revision` là revision của live deltas đã được xử lý; với BUILDING nó không thay điều kiện cursor=H về baseline coverage.

### 4.3. `daily_review_counts`: measures theo ngày/scope

Một row cho `(user, generation, scope_kind, scope_id, study_day)`:

- `scope_kind=0, scope_id=0`: collection. Mọi event, kể cả `deck_id=NULL`, đóng góp vào đây.
- `scope_kind=1, scope_id=deck_id>0`: attribution theo `ReviewEvent.deck_id` đang lưu. Không suy ra deck bằng vị trí Card hiện tại.
- Chỉ ba measures: số events, tổng duration dương, số passed ratings. Không lưu minutes/hours/average/streak; giữ phép làm tròn ở mapper hiện tại.
- Không có FK từ scope tới Deck. Sentinel `0` không phải Deck; attribution phải được xử lý theo contract purge, không xóa collection history qua cascade.

DDL mục tiêu dưới đây để review; implementation phải chuyển thành model/Alembic và kiểm tra trên MySQL thực tế. `user_id INT` khớp kiểu signed hiện tại của `users.id`. Generation và revision dùng BIGINT UNSIGNED; measures dùng BIGINT signed, kèm CHECK không âm.

```sql
CREATE TABLE review_analytics_heads (
    user_id INT NOT NULL,
    next_generation BIGINT UNSIGNED NOT NULL DEFAULT 1,
    active_generation BIGINT UNSIGNED NULL,
    building_generation BIGINT UNSIGNED NULL,
    source_revision BIGINT UNSIGNED NOT NULL DEFAULT 0,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE review_analytics_generations (
    user_id INT NOT NULL,
    generation BIGINT UNSIGNED NOT NULL,
    policy_hash BINARY(32) NOT NULL,
    timezone_name VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    day_boundary_hour TINYINT UNSIGNED NOT NULL,
    grouping_version SMALLINT UNSIGNED NOT NULL,
    timezone_rules_version VARCHAR(64) NOT NULL,
    status TINYINT UNSIGNED NOT NULL,
    baseline_high_water_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
    backfill_cursor_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
    applied_source_revision BIGINT UNSIGNED NULL,
    verified_source_revision BIGINT UNSIGNED NULL,
    verification_contract_version SMALLINT UNSIGNED NULL,
    verified_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    published_at DATETIME(6) NULL,
    last_error_code VARCHAR(64) NULL,
    PRIMARY KEY (user_id, generation),
    FOREIGN KEY (user_id) REFERENCES review_analytics_heads(user_id)
        ON DELETE CASCADE,
    CHECK (day_boundary_hour <= 23),
    CHECK (status BETWEEN 0 AND 4),
    CHECK (backfill_cursor_id <= baseline_high_water_id)
) ENGINE=InnoDB;

CREATE TABLE daily_review_counts (
    user_id INT NOT NULL,
    generation BIGINT UNSIGNED NOT NULL,
    scope_kind TINYINT UNSIGNED NOT NULL,
    scope_id INT NOT NULL,
    study_day DATE NOT NULL,
    review_event_count BIGINT NOT NULL,
    positive_duration_ms BIGINT NOT NULL,
    passed_review_count BIGINT NOT NULL,
    PRIMARY KEY (user_id, generation, scope_kind, scope_id, study_day),
    FOREIGN KEY (user_id, generation)
        REFERENCES review_analytics_generations(user_id, generation)
        ON DELETE CASCADE,
    CHECK ((scope_kind = 0 AND scope_id = 0) OR
           (scope_kind = 1 AND scope_id > 0)),
    CHECK (review_event_count >= 0),
    CHECK (positive_duration_ms >= 0),
    CHECK (passed_review_count >= 0 AND
           passed_review_count <= review_event_count)
) ENGINE=InnoDB;
```

Không thêm FK vòng từ head pointer tới generation; service kiểm tra pointer luôn trỏ row của cùng user trước publish. Không cần secondary index trên daily table cho các reads ban đầu: PK hỗ trợ collection/date range và deck/date range. Nếu worker cần hàng đợi nhiều user, đánh giá index `(status,user_id,generation)` trên metadata; chưa tạo index riêng cho từng measure.

`study_day` phải dùng cùng business-day semantics với query gốc: ngày của local `reviewed_at` sau boundary shift. Không dùng ngày UTC, timestamp server lúc commit hoặc fixed UTC offset cho DST zones. Bản đầu chỉ materialize policy hiện tại của user; timezone request khác chưa có matching generation → raw. Thay timezone database/rules hoặc quy tắc passed-rating phải tăng phiên bản policy và rebuild.

**Storage:** số daily rows một generation là `A_collection + SUM(A_deck)`, không mặc định `D × 366`; tối đa hai contributions/event rồi gộp trùng key. Trường hợp history phân tán vào nhiều deck/ngày, cardinality vẫn có thể gần `O(H)`. Trong rebuild có thể tồn tại hai bản. Đo allocated data/index pages, rows và buffer-pool reads trên staging; chưa có con số MiB đã kiểm chứng cho schema này.

## 5. Phase A — Cách cập nhật cùng transaction

### 5.1. Tách capture khỏi ghi counter

[create_review_event_record()](../../app/repositories/review_event_repository.py) là điểm hội tụ tạo event, nhưng hiện chỉ `session.add()` và không sở hữu commit. Không thêm commit tại repository, không gọi tăng counter trong frontend, và không tăng lại cho replay trả event cũ.

Thiết kế đề xuất:

1. Factory/raw flush capture **event thực sự mới**, ID và các giá trị `user_id, reviewed_at, deck_id, duration_ms, rating` vào buffer của đúng SQLAlchemy transaction/session. Chỉ capture sau khi uniqueness/flush thành công; không suy ra acceptance từ HTTP retry hoặc upsert affected-row count.
2. Buffer phân biệt root và nested SAVEPOINT. Rollback nested loại contributions của nested đó **và mọi descendants**, kể cả child đã release; parent contributions vẫn giữ. Không pop frame chỉ vì `after_transaction_end` chạy, vì nó xảy ra cho cả commit và rollback. Giữ các released child frames tới root end; `after_soft_rollback(previous_transaction)` loại đúng nhánh. `begin_nested()` flush pending parent work trước SAVEPOINT, nên work đó thuộc parent. Outer end/retry xóa buffer; mechanism root-only hiện có không đủ cho yêu cầu này.
3. Sau tất cả authority/content writes, transaction owner gọi `flush_review_analytics_deltas(session)` **một lần trước outer commit**. Flush raw đang pending, giữ User shared fence, rồi khóa head của các user theo thứ tự tăng dần.
4. Đọc generation metadata bằng current/locking read sau head lock, tính ngày theo policy từng generation, gom vector contribution theo key, cập nhật active READY và building đủ điều kiện. Tăng `source_revision` một lần; READY và BUILDING generation đã xử lý live delta nhận cùng `applied_source_revision`. Nếu có DIRTY marker, invalidate generation và evidence; không đánh dấu nó đã đồng bộ.
5. Commit state + raw event + receipts/history + daily counters cùng nhau. Counter failure làm rollback toàn outer command; rollback reader flag không thay nguyên tắc atomic này.

Thứ tự khóa phải là **User fence → session/Subject/Card/content locks → analytics heads → daily keys**. Không lấy head ngay ở review đầu tiên rồi tiếp tục khóa Note thứ hai: hai batch có thể tạo vòng chờ. Không khóa lại authority sau projection finalizer; guard phải phát hiện pending analytics writes khi owner định commit mà chưa finalize.

Native/MCP/session đã có deadlock retry ở các wrapper; purge và Anki package cần bounded **whole-transaction** retry hoặc rollback + retry response rõ ràng. Không retry riêng counter UPSERT hay chỉ một statement sau lock timeout. Anki package còn ghi files trước DB commit: kiểm tra stable replay/cleanup của files trước áp generic retry wrapper. Khi một command có cả Phase A và Phase B, phải quy định chung thứ tự giữa các loại revision/head/bucket locks, không ghép hai finalizers có thứ tự tùy caller.

SQLAlchemy `before_commit` chạy cho cả root và SAVEPOINT; không dùng hook chung thiếu phân biệt để flush sớm. `after_commit` quá muộn để cập nhật cùng transaction. Có thể dùng flush hooks để capture và root-commit hook để **kiểm tra** coverage, còn explicit finalizer thuộc transaction owner. Bulk SQL cần capture/invalidation riêng, không dựa vào ORM hooks để bắt mọi UPDATE. [SQLAlchemy session events](https://docs.sqlalchemy.org/en/20/orm/session_events.html).

### 5.2. Writer inventory phải tích hợp trước khi bật reader

| Luồng | Điểm tạo / transaction owner cần sửa | Quy tắc |
|---|---|---|
| Native direct, LEGACY | [study_service.py](../../app/services/study_service.py), `_record_native_review_transition`, `execute_native_review_command` | State/event cùng transaction; CardProgress locks trước finalizer |
| Native direct / MCP, NOTE | [study_authority_command_service.py](../../app/services/study_authority_command_service.py), outer owner trong study service | Receipt replay không tạo delta; state/history/receipt/event atomic |
| SPA offline/session batch | [study_session_service.py](../../app/services/study_session_service.py), `commit_study_session` | Chỉ accepted server events; skip prefix/replay không tăng lại |
| Worker | [study_worker_service.py](../../app/services/study_worker_service.py) và canonical batch owner | Đảm bảo mỗi outer commit được finalize; không finalize trùng giữa caller/callee |
| Connect/Anki revlog import | [anki_sync_service.py](../../app/services/anki_sync_service.py), [flama_connect_package_service.py](../../app/services/flama_connect_package_service.py), [Anki import API](../../app/api/v1/flashcards/anki_imports.py) | SAVEPOINT rollback/release đúng; source ref dedup là acceptance authority |
| Compatibility wrapper / explicit Session | [stats_overview.py](../../app/services/stats_overview.py), `record_review_event` | Chưa thấy live caller; giữ signature, yêu cầu learner fence/finalizer nếu được dùng |
| Deck purge | [deck_management_service.py](../../app/services/deck_management_service.py) | Fences các learner bị ảnh hưởng theo thứ tự; xử lý invalidation trong cùng transaction rewrite |

Imported `ease=0` hiện chỉ tạo provenance, không phải event. Matching source identity/hash không tăng lại. Repair thiếu ReviewEvent mà tạo một event mới đóng góp đúng một lần. Content/progress import không có event không được tự tăng history count.

Một event mới đóng góp vector `(1, max(duration_ms or 0,0), is_passed)` vào collection và, nếu có deck, vào deck row. `is_passed` giữ đúng semantics backend hiện tại cho `good/easy/'3'/'4'`, bao gồm behavior normalization/collation được oracle tests khóa lại; không tự thêm mode/review-kind exclusion.

Gom batch theo key trước khi ghi: 1.000 events cùng ngày/cùng deck không cần 2.000 upserts. Giữ đủ event IDs để áp eligibility của building generation. Trong thời gian rebuild, có thể cần cập nhật cả hai generation với hai policy khác nhau. Positive vector dùng atomic upsert. Nếu bổ sung signed correction ở phiên bản sau thì dùng UPDATE trên row đã có, không INSERT âm rồi trông chờ CHECK cho qua; v1 chọn DIRTY cho correction. [MySQL upsert](https://dev.mysql.com/doc/refman/8.0/en/insert-on-duplicate.html).

### 5.3. Mutation matrix và phương án purge của bản đầu

| Thay đổi | History daily count phải làm gì? |
|---|---|
| Review accepted/backdated import | Cộng theo `reviewed_at` thật, kể cả ngày cũ/năm cũ |
| Note move / Card delete / suspension / reset progress | Không sửa history attribution hoặc measures nếu ReviewEvent không đổi |
| Deck tree move | Không sửa daily direct-deck rows; reader resolve lại subtree hiện tại |
| Deck purge, historical deck_id → NULL | Collection totals giữ nguyên nhưng deck projection cần sửa/invalidate |
| NoteType purge, note_type_id → NULL | Không đổi Phase A vì không có NoteType dimension |
| Attribution job chỉ fill note_id | Không đổi Phase A; không tự thêm Note dimension vào schema này |
| User delete | Cascade head/generation/daily cùng user; không cần aggregate sang user khác |
| Future correction/hard-delete projected raw fields | Phải thêm signed delta hoặc DIRTY coverage trước cho phép writer đó chạy |

**Bản đầu dùng invalidation an toàn cho bulk deck purge:** trong cùng outer transaction rewrite events, khóa heads của affected learners, tăng revision và đánh dấu active/building generations **DIRTY**. Không phục vụ một phần generation đó. Worker restart bằng generation mới; trong thời gian này reads fallback raw. Không hydrate toàn bộ history vào Python chỉ để trừ từng event.

Trade-off rõ ràng: collection cũng fallback tạm thời dù totals không đổi; rebuild là `O(H_user)` sau purge. Nếu đo thấy purge thường xuyên, PR tiếp theo có thể tách collection/deck readiness hoặc cập nhật deck buckets theo grouped negative contributions. Phương án tối ưu đó cần chứng minh fences chống concurrent insert/mutation và điều kiện baseline/tail; không đưa vào bản đầu chỉ để tránh một fallback hiếm.

## 6. Phase A — Backfill không mất hoặc đếm hai lần event

### 6.1. Điều kiện tiên quyết

Mọi live writer tạo event phải lấy User shared fence **trước khi cấp ID/flush event**, giữ tới outer commit, và finalize projection. Mọi mutator của projected columns tuân thủ cùng admission hoặc atomically invalidate. Deploy writers đầy đủ trước; reader vẫn raw. Compatibility/raw SQL/CLI không tuân thủ phải được chặn hoặc bổ sung coverage trước bắt đầu backfill.

Factory và các private staging/import helpers hiện không tự chứng minh fence; enforcement thuộc outer writer contract, không đợi tới finalizer mới acquire User lock. Note-id attribution job và startup compatibility SQL hiện không đều có fence, nhưng các cột chúng đổi không thuộc projection v1. Thêm Note/mode/scheduler dimensions sau này buộc kiểm kê lại các đường đó.

Existing shared learner fence không serialize writers. Bởi vậy **không** lấy `MAX(id)` rồi tự giả định mọi ID nhỏ hơn đã commit. Dùng exclusive lock trên cùng User row để drain compliant writers, trong một **Session/transaction mới**, không nâng cấp shared lock đang giữ. Các locking reads và consistent snapshot có semantics khác nhau; backfill phải tạo snapshot nguồn sau admission, không dùng snapshot cũ của request. [MySQL locking reads](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking-reads.html), [consistent reads](https://dev.mysql.com/doc/refman/8.0/en/innodb-consistent-read.html).

### 6.2. Protocol admission, chunks và publish

```text
ADMIT (fresh transaction)
  User(user_id) FOR UPDATE             # drain shared-fence writers
  analytics head FOR UPDATE
  create BUILDING generation with immutable target policy
  H = MAX(committed ReviewEvent.id WHERE user_id = U), or 0
  cursor = 0; applied_source_revision=head.source_revision; set building pointer
  commit

COPY ONE CHUNK (fresh transaction)
  User(U) FOR UPDATE, then head FOR UPDATE
  validate generation still BUILDING / same target policy
  read next N current rows WHERE user_id=U AND cursor < id <= H ORDER BY id
  aggregate their current fields into building generation
  advance cursor through processed IDs in the same transaction
  if no baseline rows remain, set cursor=H (ID gaps/deletions are normal)
  commit

LIVE WRITER (User shared fence held; finalizer last)
  new IDs > H -> add to BUILDING immediately, regardless of reviewed_at
  projected old-row correction/delete/bulk rewrite -> DIRTY + invalidate evidence
  signed correction of copied/uncopied baseline rows is deferred beyond v1

PUBLISH (fresh transaction)
  User(U) FOR UPDATE, then head FOR UPDATE
  require same BUILDING pointer/policy/H, cursor=H, verified evidence
  require applied_source_revision=head.source_revision
  only INSERT + certified atomic delta may have advanced since verification
  any unsupported projected mutation makes generation DIRTY; do not publish
  mark generation READY; set applied_source_revision=current source_revision
  swap active pointer atomically, clear building pointer
  commit
```

`H` chỉ an toàn vì admission đã drain toàn bộ writer của user trước lấy high-water và writer sau đó chỉ cấp IDs mới. ID là global nên có gaps của user khác; chunks chọn theo user+id, không lặp qua từng integer ID. Cursor và counters commit chung: crash trước commit làm cả hai rollback; retry sau commit không copy lại chunk.

Worker không lock Subject/Card sau khi giữ analytics head. User-exclusive barrier vốn sẽ chờ writer finish và tạm chặn review mới; giảm chunk nếu lock time vượt budget. Khởi đầu thử **N=500**, điều chỉnh theo latency; **mục tiêu** giữ critical section khoảng ≤100 ms, không mặc định số rows luôn đạt mục tiêu trên production. Một worker generation/user; không chạy nhiều chunks cùng user song song. Pause/resume tại checkpoint không làm READY một generation thiếu dữ liệu.

**Verification cụ thể, không giữ User-exclusive trong phép quét `O(H)`:**

1. Sau cursor=H, mở fresh **READ ONLY consistent RR snapshot**. Trong snapshot này đọc building pointer, generation/policy/cursor và source revision `r0`, rồi so raw grouped rows với daily rows theo toàn bộ `(scope,day)` và ba measures. Hai nguồn cùng snapshot, live transaction commit cả raw và summary nên không xuất hiện nửa commit. So cả missing/excess buckets; không chỉ so tổng count.
2. Đóng transaction read; gắn evidence `verified_source_revision=r0, verification_contract_version=1, verified_at` và publish trong cùng fresh User-exclusive + head transaction ngắn. Contract version 1 nghĩa là exact **all-history/all-scopes** count/duration/passed parity, gồm backdated/future timestamps và NULL-deck collection. Evidence gắn với immutable `(user,generation,policy,H)` và complete cursor; không chỉ một tổng hoặc digest. Policy thay đổi, revision coverage không đủ hoặc generation DIRTY/restarted → bỏ evidence, giữ raw serving.
3. Publish yêu cầu generation `applied_source_revision = head.source_revision`, `verified_source_revision <= head.source_revision`, cùng pointer/H/cursor/policy và BUILDING status. Source revision có thể lớn hơn `r0` **chỉ khi** mọi thay đổi sau verification là event insertion qua finalizer đã certified: cộng cùng vector vào raw projection và summary giữ invariant parity. Bulk/projected correction của bản đầu luôn DIRTY và xóa evidence, nên không được vượt guard. Không coi `r0` là một MAX-ID watermark hoặc tự bỏ qua unknown writer.
4. Nếu sau này hỗ trợ signed historical correction mà không DIRTY, phải chứng minh cùng invariant bằng tests và có coverage version tương ứng, hoặc yêu cầu verify lại. Không đưa kiểu mutation mới vào trong canary như một đường ghi không kiểm kê.

Full verification vẫn `O(H)` và giữ MVCC snapshot lâu; theo dõi query time/undo retention, rate-limit từng user và không chạy trong GET. Kết quả grouped có thể nhiều deck-day rows, nên stream/merge hoặc digest từng bucket **kèm so exact** để không hydrate events vào Python. Log revision, policy, row counts và mismatch keys cho audit. Snapshot verification tránh pause review kéo dài; critical-section budget chỉ áp admission/chunks/publish, không được lấy thời gian verify để gọi là job `O(1)`.

Có thể dọn RETIRED generations theo batch sau rollout để tránh FK cascade lớn. Không drop ReviewEvents hoặc receipts; không dùng raw-history TTL như bước backfill.

## 7. Phase A — Chuyển reader, giữ API và UI contract

Implement façade ở [stats_query_repository.py](../../app/repositories/stats_query_repository.py); service/route vẫn nhận shape hiện tại. Proposed repository/service riêng quản lý projection để không trộn writer vào read helper. Giữ [analytics_read_transaction](../../app/services/study_analytics_read_service.py) READ ONLY: **GET không rebuild, upsert hay ghi repair vào DB**. Worker/CLI prewarm; fallback được log ngoài transaction read, không yêu cầu ghi job trong GET.

| Read hiện tại | Summary query | Điều kiện |
|---|---|---|
| `query_daily_review_aggregates` | Collection rows trong năm, ordered day | Matching READY policy; tối đa 366 rows cho năm |
| `query_today_review_summary` | Collection day hoặc SUM direct-deck rows trong ngày | Resolve current accessible subtree, gồm root/intermediate; empty scope trả contract cũ |
| `query_user_daily_study_time` | Daily collection hoặc SUM direct-deck rows theo ngày | Gồm mọi deck được chọn trong subtree; preserve zero-day filling và rounding |
| `query_active_review_days` | Collection rows `review_event_count>0` tới today | Streak không giới hạn 30 ngày hoặc một năm |

Ví dụ collection history query:

```sql
SELECT study_day, review_event_count, positive_duration_ms, passed_review_count
FROM daily_review_counts
WHERE user_id = :user_id AND generation = :generation
  AND scope_kind = 0 AND scope_id = 0
  AND study_day >= :start_day AND study_day < :end_day
ORDER BY study_day;
```

Reader resolve head/generation và daily rows trong **cùng snapshot** để không thấy pointer mới với dữ liệu cũ. Missing row là zero **chỉ khi toàn generation READY/đúng policy và được bảo đảm hoàn chỉnh**. Head/generation thiếu, DIRTY, schema/policy mismatch hoặc disabled → query raw; không coi metadata thiếu là lịch sử rỗng.

Các contract phải giữ:

- “Cards studied” hiện là số **ReviewEvents**, không unique Cards/Notes. Một Card review nhiều lần vẫn nhiều events.
- Overview heatmap luôn collection; selected year không đổi giá trị today và streak có thể qua nhiều năm.
- `today-future.totals.total_reviews` là tổng **future due series**, không lấy history event count thay vào.
- Study-time `range=all` hiện là trailing 365 ngày; `history_range` trong today-future chưa đổi phép tính. Giữ hành vi trong rollout; thay contract là việc riêng.
- Study-time summary hiện cộng daily minutes đã round; không tự đổi sang round tổng milliseconds vì sẽ lệch response.
- Admin breakdown theo UTC window/mode/scheduler/rating, future due và interval-weighted daily load còn dùng raw/state; daily business-day table không thay chính xác các phép đó.

Frontend không đổi layout. Sau Study receipt đã invalidate dashboard/statistics/stats; bổ sung thiếu `['stats']` sau Anki Sync trong [AnkiSyncTab.tsx](../../frontend/src/features/import/components/AnkiSyncTab.tsx). Audit query keys timezone/boundary và invalidate khi policy đổi: backend exact không sửa được frontend đang giữ cached response cũ. Local offline answers chỉ vào analytics sau server acceptance.

## 8. Phase B — Count trạng thái deck: 3 bảng dự kiến

Daily history table **không giải quyết** query Dashboard count Cards. Phase B bắt đầu bằng **snapshot direct-deck counts có invalidation**, chưa dùng delta `+1/-1` cho toàn bộ scheduler. Rebuild affected deck theo aggregator gốc rồi lưu result; tree rollup vẫn làm theo hierarchy hiện tại.

### 8.1. Contract phải tách trước khi thiết kế cache

| Consumer | Quy tắc hiện tại | Phase B ban đầu |
|---|---|---|
| Dashboard LEGACY/NOTE | Review due-day ưu tiên; due_at fallback trước cutoff ngày tiếp theo; learn gồm mọi active learn/relearning | Snapshot hợp lệ trong study day, có invalidation writes |
| NOTE Browse | Dùng deck aggregator; CARD/NOTE unit theo flag | Snapshot contract riêng, dùng cùng day semantics |
| LEGACY Browse | due_at so với **now**; queue normalization/NEW và admin boundary khác Dashboard | Giữ raw trước; muốn cache phải thiết kế expiry subday/contract riêng |
| Admin Dashboard vs Browse | Dashboard chỉ count learner Notes trong visible scope; Browse có admin-any Notes | Không chia sẻ snapshot chỉ vì cùng deck ID |

Nguồn: [deck_aggregation_service.py](../../app/services/deck_aggregation_service.py), [vocabulary_repository.py](../../app/repositories/vocabulary_repository.py), [study_repository.py](../../app/repositories/study_repository.py).

Card không có progress là pristine NEW; Note không có Card không đóng góp count. Total count vẫn bao gồm scope membership trong khi new/learn/due loại suspended/buried. NOTE mode có DISTINCT Note hoặc DISTINCT Card; không tính số Note rồi dùng cho mọi unit. Buried-until, day cutoff và authority/storage profile phải giữ behavior gốc. Cache không được thêm/bỏ mode/profile errors; hiện analytics vector violation helpers trả 0, nên không mô tả cache hit như đã kiểm tra integrity từng Note nếu code gốc chưa làm việc đó.

**Scope gate:** aggregator overlay hiện dùng timestamp cutoff, trong khi release-aware clone query dùng `DeckReleaseEntityMembership` cho applied release. Aggregator không fallback source subtree khi thiếu mappings; owned local branch không yêu cầu `DeckCloneAddedNote` như Study clone scope. Creation cutoff cũng không đóng băng current `Note.deck_id` hoặc Card existence. Không cache sai rồi gọi là đã sửa scope. Trước cutover overlay, thêm parity fixture install release + source publish/move/delete/template change; quyết định sửa aggregator trong PR riêng nếu lệch contract study/release. Chưa giải quyết gate thì overlay counts tiếp tục raw.

### 8.2. Schema logic dự kiến

| Bảng đề xuất | PK | Columns chính | Mục đích |
|---|---|---|---|
| `deck_count_content_revisions` | `physical_deck_id` | `revision BIGINT`, `updated_at` | Token membership/content ảnh hưởng count của physical source/local deck |
| `deck_count_learner_revisions` | `(user_id,effective_deck_id)` | `revision BIGINT`, `updated_at` | Token state của learner tại mọi local deck có liên quan |
| `deck_study_count_snapshots` | `(user_id,effective_deck_id,contract_code,unit_code)` | `total,new,learn,due BIGINT`; `study_day DATE`, `valid_until_utc DATETIME(6)`, `policy_hash BINARY(32)`, `dependency_hash BINARY(32)`, `computed_at` | Direct counts đã materialize; không chứa ancestor totals |

FK user/local physical deck có thể CASCADE vì đây là state cache không phải lịch sử. Revisions thiếu được chuẩn hóa token 0 chỉ khi writer coverage đã bảo đảm chưa có mutation bị bỏ qua. Tokens phải tăng đơn điệu, không reset/reuse để tránh ABA; maintenance/reseed cần invalidate bằng projection version. Các code contract/unit là hữu hạn, có CHECK và mapping rõ; không dùng một scope hash bất kỳ để tạo vô hạn biến thể mỗi request.

`dependency_hash` đại diện sorted vector: learner revision, local/source content revisions, authority mode/epoch/storage profile, count unit, visibility contract, actual install/mapping set + source owner/cutoff, overlay revision, applied-release/snapshot identity và policy. Stamp còn có **count-contract/projection version và timezone-rules version**; đổi semantics phải invalidate ngay cả không có content/state write, không bump cho mọi app release. Tập dependencies lấy theo scope đã kiểm chứng, query batch cho tất cả deck; tránh một SELECT/deck. Không dựa vào `Deck.updated_at` vì Note/Card writes không luôn bump nó.

### 8.3. Invalidation coverage

| Writer/change | Token cần bump / hết hạn |
|---|---|
| Rating/state edit/reset/suspend/bury/unbury, authority repair | Learner revision của **mọi effective local deck** chứa Note/Card bị đổi |
| NOTE shared Subject state | Áp cho các sibling Cards và mọi mapping của **learner đó**, không chỉ deck của ReviewEvent |
| Note/Card create/delete/move; Template thêm/xóa Card | Physical content revision của deck bị ảnh hưởng; move gồm old+new deck |
| Source edit thay membership của overlay | Source content token; snapshot subscriber tự mismatch khi đọc, không đồng bộ bump toàn bộ installers |
| Install/rebase/uninstall/mapping change | Install identity/revision + dependencies của local scope |
| Day boundary / burial expiry / timezone settings | Study day + policy + `valid_until_utc`; hết hạn ngay cả không có writes |
| Deck parent move | Tree rollup/scope cache invalidation; direct counts không tự đổi nếu membership giữ nguyên |

Source content token tránh thêm **O(number_of_installers)** writes cho mỗi source mutation. Ngược lại, learner có nhiều mappings của cùng Note vẫn có chi phí `O(affected_mappings)` để bump đúng state token; cần đo và báo cáo. Không dùng biến process-local làm invalidation chung cho nhiều Gunicorn workers.

Tập token cần bump được gom transaction-local rồi ghi cuối transaction, như Phase A, theo thứ tự khóa thống nhất. Không bump do thay HTML/CSS/media thuần túy nếu membership/count unchanged, trừ khi chưa chứng minh được an toàn thì invalidation dư được chấp nhận.

Task B1 phải nối hooks vào các owner thực tế: consolidated progress/lifecycle mirror, scheduler/algorithm switch, LEGACY progress import, Note/Card/Template CRUD, CSV chunk commits, Connect nested imports và install/rebase/change-request merge. Không chỉ nối ReviewEvent factory: progress import/reset/repair có thể đổi count mà không tạo event. Capture old deck/owner/mapping context trước move/delete; map chỉ dựa vào sau mutation sẽ bỏ old bucket. Dedicated Browse suspend/bury route chưa được tìm thấy trong code hiện tại; state changes này đi qua review/scheduler/import, không invent một API hook không tồn tại.

| Coverage B1 | Files/owners cần nối hooks |
|---|---|
| NOTE state | [consolidated progress](../../app/services/study_consolidated_progress_service.py), [lifecycle mirror](../../app/services/study_progress_lifecycle_mirror_service.py), [authority commands](../../app/services/study_authority_command_service.py), [algorithm switch](../../app/services/study_algorithm_switch_service.py) |
| LEGACY / external progress | [study repository](../../app/repositories/study_repository.py), [Anki sync](../../app/services/anki_sync_service.py), [Connect import cards](../../app/services/connect/import_cards.py) |
| Note/Card/template/application | [content CRUD](../../app/services/flashcard_content_service.py), [Browse mutations](../../app/services/browse_card_service.py), [MCP note tools](../../app/services/mcp/note_tools.py), [note templates](../../app/services/study_note_template_service.py), [applications](../../app/services/study_application_service.py) |
| Import chunks / savepoints | [flashcard import](../../app/services/flashcard_import.py), [Connect actions](../../app/services/connect/actions.py), Connect import/reconcile owners ở trên |
| Install/source/topology/policy | [install](../../app/services/share/install.py), [overlay](../../app/services/share/overlay.py), [rebase](../../app/services/deck_install_rebase_service.py), [merge](../../app/services/change_request/merge.py), [deck management](../../app/services/deck_management_service.py), [profile](../../app/services/profile_service.py), scheduler settings và maintenance writers |

### 8.4. Read, rebuild và publish snapshot

1. Dashboard GET trong READ ONLY transaction đọc dependencies + snapshot theo batch. Dùng snapshot khi contract/policy/dependency hash/study-day/expiry đều match; giữ authority mode/profile behavior. Browse hiện có learner shared fence và chưa có fresh nonlocking read boundary như Dashboard; task B0 phải chọn boundary cụ thể phù hợp caller, không gọi nó là READ ONLY snapshot hiện có. Không ghi cache trong bất kỳ GET path nào.
2. Với missing/dirty deck, gọi aggregator gốc cho **tập dirty decks**; cached deck giữ counts. Không chuyển GET thành transaction writer. Worker prewarm learner đang hoạt động và các keys writer vừa làm dirty.
3. Worker compute với consistent snapshot và vector `v0`; kết thúc transaction read. Bản đầu publish theo **optimistic token validation** trong fresh transaction: đọc current dependencies bằng **nonlocking READ COMMITTED SELECT**, kiểm tra policy/day/expiry và `v_current=v0`, rồi upsert snapshot với **hash/stamps của captured v0**. Token đã đổi thì bỏ result và retry có giới hạn. Không stamp result cũ bằng vector mới.
4. Source/state có thể đổi sau compare và trước snapshot commit: reader vẫn kiểm tra captured stamps với current dependencies trong coherent snapshot, nên result cũ trở thành miss/raw fallback; publisher không clear hoặc advance revision của domain. Không cần khóa canonical Subject/install để gọi cache là clean. Hai worker cùng key có thể ghi đè cache mới bằng result cũ gây miss; dedup/debounce giảm việc đó, không thay freshness invariant. Không gọi compare hai lần trong cùng RR snapshot rồi cho là chống race. Nếu thêm locking publish sau này, validate chung lock order và không lấy canonical locks sau revision locks.
5. Rebuild lỗi authority/scope không được trả count 0 hoặc dùng snapshot cũ; giữ error/fallback behavior gốc. Expired snapshot không thay thế exact count trên Dashboard.

Snapshot hữu ích nhất khi nhiều reads chia sẻ một generation state. Nếu mọi lần về Dashboard đều có state/content thay đổi làm toàn bộ scope dirty, cache hit thấp và lợi ích ít. Vì vậy gate Phase B phải đo **dirty deck count, hit ratio, chi phí dependency reads, rebuild fanout và p95 count query**; không mặc định đã xóa `O(C)`.

**Discovery/scheduling:** worker định kỳ enumerate direct scopes của learner active để prewarm cold keys; writer có thể phát advisory dirty notification sau commit, dedup theo `(user,effective_deck,contract,unit)`, debounce khoảng 0,5–2 giây và giới hạn concurrency. GET miss chỉ có thể gửi advisory signal ngoài read transaction, không ghi admission row; mất signal không làm count sai vì reader vẫn kiểm tra token và fallback raw. Periodic active-scope token checks bao phủ source mutation không fanout subscriber keys và notifications bị mất. Đo số raw miss + worker recompute trùng nhau; không prewarm Cartesian `users × decks`, không coi advisory queue là nguồn freshness authority.

## 9. Chia PR, thứ tự triển khai và định nghĩa hoàn thành

Effort dưới đây là ước lượng ban đầu cho một engineer, có thể song song review/test; không phải lịch cam kết. Chỉ sửa documentation trong lần chuẩn bị kế hoạch này.

| PR | Công việc cụ thể | Điều kiện hoàn thành | Ước lượng |
|---|---|---|---|
| **A0 — baseline/contracts** | Đo lại history vs state count; kiểm kê commit/mutators; A/B raw/index/cache; fixtures timezone/scope/rounding | Có baseline đọc/ghi và danh sách writer coverage; không đổi response | 1–2 ngày |
| **A1 — schema/policy** | Model 3 bảng, Alembic additive, policy resolver, metadata repository, flags off; migration tests | MySQL upgrade + app boot; FK/CHECK/parity SQLite hỗ trợ; chưa phục vụ summary | 1–2 ngày |
| **A2 — transactional writers** | Buffer SAVEPOINT-aware + finalizer; tích hợp mọi owner; purge invalidation; root-commit guard | New event/replay/rollback/import/concurrency đúng; không đảo lock order | 2–4 ngày |
| **A3 — backfill/reconcile** | CLI/worker admission/chunks/checkpoint/publish, dry-run/status/resume; DIRTY restart | Race tests + crash/retry + exact grouped parity; bounded barrier đã đo | 2–3 ngày |
| **A4 — shadow reader** | Summary façade; sampled raw oracle; metrics/fallback; FE import/policy invalidation | API JSON parity; chosen index/rows và write budget đạt gate | 1–2 ngày |
| **A5 — canary/cutover** | Allowlist User 1 rồi eligible users; rollback drill; cleanup retired generations | Stable canary, drift 0, read/write gates; raw fallback vẫn hoạt động | 1 ngày + observation window |
| **B0 — state-cache design gate** | Contracts admin/LEGACY/NOTE; overlay release parity; full invalidation inventory | Chốt phạm vi supported và dependency token đầy đủ | 1–2 ngày |
| **B1–B3 — deck snapshots** | 3 bảng/revision hooks; batch reads/rebuild; race-safe publish; canary theo contract | Exact clock/scope parity, hit ratio và latency có lợi | 4–8 ngày sau B0 |

Ưu tiên A0–A5 vì proof đã có; B0 có thể điều tra song song. Không chờ Phase B mới dùng history count. Nếu A2 không đạt write budget, dừng reader cutover và so lại index/cache/outbox; không đẩy counter contention sang người học chỉ để Dashboard nhanh hơn.

Code mới dự kiến: `models/review_analytics.py`, `app/repositories/review_analytics_repository.py`, `app/services/review_analytics_projection_service.py`, `app/services/review_analytics_backfill_service.py`; đăng ký CLI tại [app/cli.py](../../app/cli.py). Tên này là task destinations, chưa phải files có sẵn. Đưa chúng vào test-module mapping trong [scripts/run_tests.py](../../scripts/run_tests.py).

Cờ đề xuất: `REVIEW_ANALYTICS_WRITE_ENABLED`, `REVIEW_ANALYTICS_READ_MODE=raw|shadow|summary`, read allowlist; deck snapshots có flags riêng. Ngày đầu `raw`, schema deployed, writer coverage bật nhưng reader chưa bật. Shadow raw oracle phải sample/rate-limit ngoài hot path: chạy full raw+summary cho mọi request sẽ tăng tải và làm phép đo thiếu công bằng. Mỗi comparison dùng **cùng fresh READ ONLY RR snapshot và captured now/policy/scope**; hai requests riêng hoặc rollover giữa queries có thể tạo false drift.

## 10. Test matrix bắt buộc

Mở rộng các suites [stats overview](../../tests/test_stats_overview.py), [today/future](../../tests/test_stats_today_future.py), [study-time](../../tests/test_stats_study_time.py), [note analytics](../../tests/test_note_analytics_read.py), [study session](../../tests/test_study_session_api.py), [note batch](../../tests/test_study_note_batch.py); thêm tests projection/backfill MySQL thực. SQLite không chứng minh locking/isolation/CONVERT_TZ.

| Nhóm | Cases và oracle |
|---|---|
| Measures / dimensions | NULL/âm/0/dương duration, passed legacy strings, nhiều events cùng Card, multi-template, NULL deck; so grouped measures exact |
| Consumer contract | Collection/leaf/ancestor, empty scope, năm khác, streak qua năm, zero-day series, daily rounding và full JSON |
| Temporal policy | UTC/Tokyo/Ho Chi Minh, DST spring/fall, boundary 04:00, leap day/year rollover; đổi timezone/header/query/boundary và timezone-rules version |
| Idempotency / atomicity | Same operation ID/hash, prefix replay, imported unchanged/ignored/repair, nested SAVEPOINT rollback, outer rollback, retry, projection failure |
| Concurrent writers | Hai thiết bị cùng ngày, hai Notes khác nhau, batch khóa Notes thứ tự khác; no counter-head/authority inversion |
| Backfill race | Allocate nhỏ nhưng commit muộn trước barrier; insert sau H; backdated reviewed_at; gaps; chunk crash trước/sau commit; policy/purge giữa copy/verify/publish |
| Historical mutations | Note move khác deck tree move; purge trước/sau cursor; NULL rewrite; unsupported raw mutation bị guard/invalidation |
| Phase B scope/clock | Owned vs installed, release/timestamp scope, admin contracts, CARD/NOTE units, pristine/suspend/bury expiry/reset, move/template regeneration, midnight không có writes |
| Phase B publish | Writer commit giữa compare/publish; worker cũ overwrite snapshot mới; source/mapping đổi giữa compute/publish; multi-worker; retry không trả stale/zero |

Load matrix: history **4k/40k/100k/1M**; active days **7/365/1.095**; deck breadth **1/50/1.500**; single review/batches **1/50/1.000**; warm và cold runs trên MySQL staging tách biệt. “Cold” không flush shared production cache. Đo collection-year và lifetime streak riêng.

Chạy modular tests khi implementation có code: `.venv\Scripts\python.exe scripts/run_tests.py --module analytics,study,decks --backend-only`, bổ sung module importer tương ứng sau kiểm tra `--list-modules`; FE chạy narrow tests cho query invalidation. Xác minh real `wsgi.py` entry point và Alembic trên DB staging vì startup có schema/setup side effects; không dùng import Flask production để chạy một phép đo read-only.

## 11. Acceptance gates và số liệu phải báo cáo

Các con số sau là **budget đề xuất, chưa là kết quả đo**; A0 ghi baseline rồi nhóm chốt budget trước canary.

| Gate | Tiêu chí |
|---|---|
| Correctness | **0 drift** count/duration/passed theo ngày/scope; full response parity; read-after-accepted-commit exact; pending/offline chưa commit không hiện |
| History read | Eligible collection-year p95 **≤50 ms**, xử lý ≤366 daily rows; có lợi rõ so với optimized raw cho large users |
| Write overhead | Added commit p95 **≤5 ms và ≤10%** baseline, không có deadlock mới không được xử lý; báo cáo cả import/batch |
| Backfill interference | Critical-section target **≤100 ms**/chunk; pause/resume đúng; raw fallback trong build; đo impact p95 review khi job chạy |
| Snapshot deck | Supported-contract parity; count-cache path target p95 **≤50 ms**; cache hit/rebuild rate chứng minh lợi ích, không gọi cả Dashboard ≤50 ms |
| Rollback | Disable summary reads trả raw ngay; thử rollback flags khi đang backfill/ghi; không sửa mất nguồn raw |

Metrics/logs: read source và fallback reason, policy/generation, query p50/p95, actual rows examined/returned, summary rows, raw-oracle drift, accepted write p50/p95, upserts/transaction, lock waits/deadlocks/retries, backfill cursor/rows/sec/barrier time, dirty/rebuild lag, snapshot hit ratio/affected mappings, allocated data/index pages và physical reads.

Tính lợi ích theo traffic thực: `R × (raw read cost − summary read cost) − W × added write cost − rebuild cost`. Báo cáo CPU/IO nếu đo được, không lấy wall-clock của query làm CPU chính xác. Chi phí observation shadow ghi riêng, không trộn với latency serving summary-only.

## 12. Migration, rollout và rollback

1. **Expand:** tạo bảng mới bằng Alembic, không ALTER/drop nguồn gốc. Kiểm tra startup/metadata registration có `db.create_all` hay schema repair bật ở profile nào; không để mỗi Gunicorn worker tự backfill lúc boot. Rehearse metadata lock/upgrade/downgrade ở staging MySQL.
2. **Cover writers:** deploy A2 tới mọi web/worker/CLI writer, readers raw. Không rolling-canary writer coverage một phần rồi backfill user đang được old writer phục vụ. Drain/restart old workers trước admission.
3. **Backfill:** từng user, ưu tiên User 1; flags reader off. Resume generation theo checkpoint; error/policy mismatch → DIRTY/FAILED, không READY. Giới hạn concurrency theo DB budget.
4. **Shadow:** sampled parity, covering-index/cache comparison, migration/rollback drill. Đề xuất observation ít nhất 48 giờ với traffic thực và ít nhất một import/batch + boundary rollover; DST phải có fixture, không chờ production DST.
5. **Canary:** bật summary read User 1 trước, theo dõi accepted-write và endpoint p95; mở rộng khi gates đạt. Phase B canary riêng, không chồng hai thay đổi để rồi không xác định nguồn regression.
6. **Contract:** dọn RETIRED generations theo batch sau thời gian quan sát; chỉ gỡ duplicate reader logic khi fallback thay thế đã có chiến lược vận hành. ReviewEvents/facts/receipts vẫn giữ.

**Rollback chính:** chuyển read mode về raw trước; giữ synchronous writers nếu chúng đang an toàn. Nếu phải tắt writer vì lỗi/lock contention, tắt summary readers trước, invalidate generations bị ảnh hưởng và yêu cầu rebuild trước bật lại. Không tắt writers rồi bật lại readers dùng READY cũ như chưa có gap. Downgrade/drop bảng chỉ sau khi không còn code đọc/ghi; rollout không cần drop bảng để khôi phục phục vụ raw.

GET không tự chữa schema. Freshness/fallback info đi vào telemetry, giữ API/UI payload hiện tại. Drift phải có alert + reader raw fallback, không “fix” bằng cách đổi dashboard total cho khớp một phía.

## 13. Những phần tăng tuyến tính vẫn cần kế hoạch riêng

| Chi phí còn lại | Scale | Vì sao bảng count chưa giải quyết | Việc tiếp theo |
|---|---|---|---|
| Daily history backfill/rebuild | `O(H_user)` | Phải đọc nguồn một lần/generation; policy change/purge có thể làm lại | Bounded chunks, đo frequency và verification cost |
| Scoped daily rows | `O(A_deck_scope + D_scope)` | Collection row không trả được mọi subtree | Báo cáo cardinality thực; không materialize mọi ancestor mặc định |
| Streak dài | `O(A_lifetime)` hoặc `O(S)` | Ngày liên tục vẫn phải kiểm tra | Reverse daily iteration có parity, không cắt lịch sử tùy ý |
| State future due + daily load | `O(C_state_scope)` ở các paths hiện tại | Có clock và interval weighting **theo Card** | Thiết kế state/due buckets riêng; codec `f64:<hex>` không CAST decimal trực tiếp |
| Dirty deck rebuild | `O(C_dirty)` | Snapshot chuyển quét sang miss/job, không bỏ phép tính | Measure dirty-key locality; cân nhắc delta counters sau writer coverage |
| NOTE shared mapping invalidation | `O(affected_mappings)` | Một state phục vụ nhiều effective local scopes | Đo fanout; source-global token chỉ tránh fanout installers cho content |
| Deck tree/ancestor rollup/JSON | `O(D)` | Counts sẵn nhưng vẫn tạo cây và payload | Lazy children/pagination/virtualization theo browser profile riêng |
| NoteType metadata/fallback | Theo Notes trong scope | Dashboard fallback có thể đọc Notes không có Card; Browse type list không suy được từ count rows | Đo và cache/index metadata riêng, giữ visibility/type semantics |
| Queue selection / hydration | Theo candidates và scope | Count không chỉ ra Card tiếp theo | Keyset/index/order optimization với strict/learn-ahead parity |
| Offline session snapshot/persist | `O(C + events + bytes)` | Local state/event serialization là chi phí khác | Indexed persistence/chunking; đo frontend main thread |
| History cut, receipt/provenance verification | Theo Note/session history | Nguồn evidence vẫn cần tồn tại | Tối ưu query theo consumer; retention là contract riêng |

**Quyết định đề xuất:** bắt đầu A0–A3 để có schema và synchronous writer/backfill có thể review, sau đó chỉ chuyển reader khi A4 chứng minh correctness lẫn write economics. Phase B xử lý phần count Dashboard bằng read model riêng, bắt đầu ở các contract đã rõ; phạm vi overlay/LEGACY Browse giữ raw cho đến khi các gate tương ứng đạt.
