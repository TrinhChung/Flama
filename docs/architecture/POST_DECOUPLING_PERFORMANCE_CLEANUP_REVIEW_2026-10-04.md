# Review hiệu năng sau decoupling — 04/10/2026

Decoupling đã bỏ phần lớn chi phí của storage trung gian. **Vẫn còn công việc thừa trên các luồng đang dùng**, nổi bật là query đếm Dashboard ở mức Card, Study khóa từng Note và dựng lại template, Browse tải dữ liệu hoặc metadata không cần thiết. Các mục Study/Browse dưới đây ảnh hưởng chính các màn hình đó; chúng không cùng tạo nên thời gian tải Dashboard khoảng 3 giây.

## Phạm vi và mức tin cậy

- Review source sau PR [#210](https://github.com/TrinhChung/Flama/pull/210): commit `4c1d87f`, cùng nội dung runtime với merge `e1ab03d`. PR đã merge lúc 18:54:53 JST ngày 04/10.
- Kiểm tra SSH chỉ đọc lúc **19:09 JST**: backend production `/opt/flama/current` vẫn trỏ release `d747a5f5be6d3799a977b5efe73467072491a744`. Không lấy số đo trước PR làm kết quả sau triển khai PR.
- Số Dashboard production dùng lại [baseline User 1](DASHBOARD_USER1_PERFORMANCE_INVESTIGATION_2026-10-04.md) và [artifact](artifacts/dashboard_user1_performance_20261004.json). Các probe mới chạy SQLite in-memory hoặc Node 22 với dữ liệu giả lập; không benchmark tải production và không suy ra số giây tiết kiệm trên VPS.
- Bundle được phân tích từ build local có entry `index-C-3oo8Vn.js`. Source map của các luồng được nêu khớp source hiện tại. Entry public lúc kiểm tra là `index-BdqD3jZ0.js`; kích thước local không phải số byte production truyền trong một navigation.
- Các phần điều tra bên dưới mô tả snapshot **trước cleanup**. Đợt triển khai sau review đã sửa runtime trong nhánh `perf/post-decoupling-scaling-20261004`; xem phần kết quả cuối tài liệu. Chưa deploy hay thay schema/cấu hình production. [Artifact baseline](artifacts/post_decoupling_performance_cleanup_20261004.json) giữ số liệu trước sửa.

## Các mục nên xử lý

P1: ưu tiên vì có chi phí lớn hoặc tăng theo quy mô. P2: chi phí đã xác nhận về cấu trúc, nhưng cần đo thêm tác động thực tế hoặc chỉ lớn ở điều kiện nhất định.

| Ưu tiên | Luồng | Phần còn lại | Bằng chứng | Hướng xử lý |
|---|---|---|---|---|
| P1 | Dashboard | Tiến độ đã ở Note nhưng scope vẫn expand Card rồi chạy 4 `COUNT(DISTINCT)` | Query count median **730 ms** trong baseline VPS User 1 | Thử Note scope/`EXISTS` cho NOTE mode, giữ phạm vi và đơn vị đếm |
| P1 | Study status/commit | Khóa Note và sibling Cards bằng hai query cho từng Note | Status fixture 500 Notes: **1.014 SELECT** cho response khoảng 430 B | Gom locking reads theo tập, giữ fence và lock order |
| P1 | Study commit replay | Mỗi event quét toàn session để cập nhật siblings cùng Note | 300 Notes/events: **90.600 lượt tra pin**, tăng theo N² | Lập map Note → memberships/identity một lần |
| P1 | Mở Study session | Dựng cùng template/policy cho từng Card rồi mới deduplicate response | 500 Cards dùng một template: build **500 lần**; thử memoization có parity trên fixture | Cache trong request theo effective template/policy inputs |
| P1 | Browse tree | Aggregator tính NoteType metadata nhưng caller bỏ kết quả | Probe xác nhận **1 query thừa**; cùng SQL shape trong baseline Dashboard khoảng **152 ms** | Cho caller chỉ lấy counts; Dashboard lấy fallback metadata khi cần |
| P1/P2 | Study-next, MCP counts | Tải toàn bộ Card/Note content để quyết định availability | Fixture không còn thẻ due vẫn tải **202 Cards + 201 Notes**, gồm **826 KB** nội dung giả lập | Đọc metadata tối thiểu; hydrate nội dung sau khi chọn Card |
| P2 | Browse/Study frontend | Worksheet vẫn tải trước khi mở; Browse còn kéo GuidePage qua barrel | Worksheet **44,5 KB gzip**, GuidePage **36,6 KB gzip** trong local static import graph | Lazy modal theo action; import Help component trực tiếp |
| P2 | Bootstrap | Cùng session endpoint có hai React Query cache keys | Shell `['frontend','bootstrap']`; Browse/AnkiSync `['bootstrap']` | Dùng shared hook/key, sửa các invalidation liên quan |
| P2 | Tải lại frontend | Hash assets vẫn buộc HTTP revalidation | Hai JS public trả `max-age=0, must-revalidate`; baseline browser reload có **44 JS 304** | Cache dài/immutable cho assets có hash; giữ HTML revalidation |
| P2 | Today/Future | Đọc mọi stateful Card về Python rồi mới lọc khoảng tương lai | Fixture 202 rows, chỉ **2 Cards** trong khoảng 30 ngày | Tách due-window khỏi `daily_load` toàn scope |
| P2 | Browse canonical reader | Đọc full Subject hai lần, project cùng Note theo từng Card | Fixture 24 SQL, **2 full Subject reads**, 202 projections/201 Notes | Thu hẹp classifier; validate/project một lần mỗi Note |
| P2 | Chọn composition trước học | Lấy sample Card và lazy Template/NoteType riêng từng composition | 1/5/20 Templates: **11/31/106 SELECT** | Batch sample Cards và eager-load metadata cần thiết |
| P1 nếu session lớn; P2 thông thường | Trả lời Study offline | Mỗi rating normalize và persist toàn session blob | Fixture v4 5.000 Cards: **7,5–12,1 MB** JSON-equivalent; normalize **22,7–35,6 ms** CPU local | Tách immutable artifacts và mutable state/event journal, giữ durability |

## Dashboard và Browse: SQL còn mang cách đọc cũ

### Scope Card và DISTINCT

[`deck_aggregation_service.py:157`](../../app/services/deck_aggregation_service.py#L157) dựng `cards JOIN notes`; dòng 236–245 chỉ đổi đơn vị đếm sang `note_id` khi flag NOTE count bật, vẫn dùng bốn DISTINCT aggregates. PR210 giảm tree/serialization/heatmap, chưa thay query count này.

Baseline VPS có count query median 729,672 ms, metadata query riêng 151,833 ms. A/B Note-grain/EXISTS trên cùng snapshot chỉ cho **556,545 → 502,565 ms, khoảng 9,7%**; không dùng 730 ms làm lượng thời gian có thể xóa hoàn toàn. Cần thêm EXPLAIN và parity trước khi chọn query mới. Note không có Card, multi-template, admin-wide/owned scope, overlay snapshot, burial và due boundary phải giữ đúng.

### Metadata không được dùng trong Browse tree

[`browse_card_service.py:207`](../../app/services/browse_card_service.py#L207) nhận `direct_counts, _note_types` nhưng không dùng `_note_types`. [`deck_aggregation_service.py:271`](../../app/services/deck_aggregation_service.py#L271) vẫn chạy `_deck_note_types()`, gồm `MIN(notes.created_at)` và GROUP BY cho visible decks. Probe tree xác nhận query này trong 17 SQL. Con số 152 ms là query cùng shape của Dashboard production, chưa phải latency đo riêng của Browse.

Đây là việc nhỏ có bằng chứng rõ: để caller yêu cầu metadata khi cần. Dashboard vẫn cần chọn loại Note cũ nhất cho deck thiếu `note_type_id` và giữ overlay precedence; không bỏ fallback toàn hệ thống.

### Browse canonical reader

[`study_authority_read_service.py:300`](../../app/services/study_authority_read_service.py#L300) gọi classifier ở [`study_note_pristine_service.py:58`](../../app/services/study_note_pristine_service.py#L58), đọc full Subject để phân loại. Reader lại lấy full Subject qua locking read ở [`study_session_authority_pin_service.py:185`](../../app/services/study_session_authority_pin_service.py#L185), rồi validate/project từng requested Card ở reader dòng 387.

Probe 201 stateful Notes/202 Cards: 24 SQL, hai lần full Subject SELECT và 202 projections. Chi phí lặp tăng khi một Note có nhiều Templates. Locking read với `populate_existing` có mục đích đảm bảo trạng thái hiện tại; hướng tối ưu là thu hẹp lần phân loại đầu hoặc tái dùng locked data, giữ kiểm tra integrity và fail-closed khi evidence lệch.

## Study: chi phí còn tăng theo toàn phiên/toàn deck

### Status và commit khóa từng Note

[`study_session_service.py:1921`](../../app/services/study_session_service.py#L1921) lặp các Note gọi `lock_study_authority_siblings()`. [`study_authority_repository.py:459`](../../app/repositories/study_authority_repository.py#L459) đọc khóa Note; dòng 469 đọc khóa sibling Cards. Status chạy lại kiểm tra này cho cả phiên; commit dùng cùng helper.

Probe status cho 10/100/500 Notes lần lượt **34/214/1.014 SELECT**, tức `2N + 14` trên fixture một deck, owned NOTE/v4 leases không có batches. Lượt 500 Notes mất khoảng **599 ms local SQLite**, SQL execute khoảng 32 ms; không đo tranh chấp khóa hoặc độ trễ MySQL. Query count thể hiện vấn đề ngay cả khi không có network DB.

Commit một event mỗi Note cũng đã đo: 10/100/300 Notes cho **59/419/1.219 SELECT**, tức `4N + 19` trong fixture. Thời gian local một lượt mỗi case khoảng 94/572/2.284 ms. Một nửa phần SELECT tăng tuyến tính đến từ sibling reads; receipt/history/snapshot checks và writes còn có nhiệm vụ đảm bảo tính đúng, không thể coi toàn bộ query là thừa.

Tối ưu bằng set-wise reads cần giữ User/enrollment fence, khóa Subject, complete sibling membership, current-read receipt và thứ tự khóa. Chưa triển khai hay chứng minh parity của thay đổi locking trên MySQL.

### Replay quét toàn phiên cho từng event

[`study_session_service.py:1762`](../../app/services/study_session_service.py#L1762) duyệt tất cả session Cards sau mỗi event để truyền trạng thái sang siblings cùng Note. Dòng 1992 cũng tìm identity bằng `next(...)` theo Note. Probe một event mỗi Note cho 10/100/300 Notes có **120/10.200/90.600 lượt tra pin**, tức `N² + 2N` trong fixture. Replay 300 events có instrumentation mất khoảng 98 ms local; đây không phải thời gian production.

Có thể lập Note → memberships và Note → identity maps một lần trong request. Cần giữ việc truyền trạng thái cho mọi sibling và kiểm tra replay hash/receipt; không thay bằng cập nhật riêng Card được trả lời.

### Dựng artifact rồi mới deduplicate

[`study_session_service.py:710`](../../app/services/study_session_service.py#L710) tạo policy mỗi Card; dòng 745 tạo template artifact, dòng 749 mới `setdefault()` để deduplicate response. Template sanitation/hash vẫn chạy cho mọi Card dùng cùng effective template. Bindings/composition cũng được dựng lại trong vòng lặp.

Fixture 500 Notes, một template và một deck: issuance giữ 25 SELECT, nhưng build template/policy 500 lần. Thử memoization trong scratch cho template và policy giữ nguyên artifact/state payload qua ba lượt, median mở phiên **655 → 300 ms local**; template preparation **500 lần/307 ms → 1 lần/0,69 ms**. Parity dùng thời điểm issuance cố định và bỏ các lease fields biến động `session_id`, `session_token`, `snapshot_hash`, `expires_at`; không phải so full response byte-identical. Đây là thử nghiệm trên fixture, chưa phải bản sửa hoặc mức cải thiện production. Cache cần theo effective definition/policy inputs và có phạm vi request; không cache chỉ theo tên template và làm lẫn overlay. Response 500 Cards vẫn khoảng 999 KB raw/99 KB gzip vì lease state cần được giữ.

Learner settings cũng được đọc lại khi resolve options cho nhiều deck: fixture 100 Notes/20 decks có 21 reads `user_scheduler_settings` và 64 SELECT, so với 25 SELECT khi cùng 100 Notes ở một deck. Có thể resolve runtime settings một lần rồi truyền vào bước resolve options theo deck.

Installed sessions còn query `DeckCloneAddedNote` cho từng Card ở [`study_session_service.py:1873`](../../app/services/study_session_service.py#L1873), dù issuance đã batch membership. Đây là path đã xác nhận từ code; chưa đo installed-session query count trong probe này. Giữ quyền sở hữu và overlay mapping khi gom membership lookup.

### Composition discovery còn N+1 riêng

`/api/study/scopes/deck/<id>/compositions` nhóm các Card hợp lệ tại [`study_composition_service.py:227`](../../app/services/study_composition_service.py#L227), nhưng dòng 274–279 lấy sample Card từng nhóm; lazy Template/NoteType và bước sort đọc tiếp metadata. Fixture một NoteType có 1/5/20 Templates trả đúng số compositions nhưng chạy **11/31/106 SELECT**, khoảng 12/30/65 ms local. Batch sample Cards hoặc dùng projection metadata cần thiết; giữ phân biệt composition của source/install/local.

Các duplication khác được xác nhận từ call chain, chưa đo riêng: batch admission decode lại prefix events (`study_note_batch_transport_service.py:166`), continued commit replay lại full prefix (`study_note_batch_service.py:268`), status đọc receipt set-wise rồi kiểm từng receipt lại (`study_note_session_status_service.py:147`). Cần đo sessions có nhiều batches trước khi đổi checkpoint/replay; fingerprint, idempotency và crash recovery phải được bảo toàn.

### Nội dung vẫn được tải trước khi chọn hàng đợi

[`app/routes/flashcards/study.py:236`](../../app/routes/flashcards/study.py#L236) lấy toàn bộ full Card + Note trước khi gọi availability reader nhẹ. [`mcp/study_tools.py:118`](../../app/services/mcp/study_tools.py#L118) làm tương tự; `get_deck_stats()` dòng 475/483 còn nạp tập Card rồi gọi due-count helper nạp lại.

Probe 201 Notes/202 Cards không có thẻ due vẫn materialize 826.106 byte `field_values` giả lập và toàn bộ entities để trả complete. Chuyển progress sang consolidated đã giảm JSON tiến độ; content JSON vẫn còn ở luồng quyết định queue. Cần metadata tối thiểu cho scope/order, rồi mới lấy nội dung Card được chọn. Giữ NOTE count, learning-waiting, deck options và overlay scope.

### Ghi offline vẫn theo toàn snapshot

[`useStudySession.ts:612`](../../frontend/src/features/study/hooks/useStudySession.ts#L612) await `saveStudySession(next)` cho rating. [`sessionStore.ts:410`](../../frontend/src/features/study/session/sessionStore.ts#L410) normalize toàn phiên và dòng 419 `store.put(normalized)` toàn snapshot, gồm nội dung/template, state, events và undo. Restore còn tìm Card tuyến tính cho từng event tại [`sessionRestore.ts:125`](../../frontend/src/features/study/session/sessionRestore.ts#L125).

Probe gọi chính hàm save từ emitted v4 chunk, 10 lượt mỗi case trên Node 22. Với 5.000 Cards, JSON-equivalent 7,5–12,1 MB; normalize median 22,7–35,6 ms. `structuredClone` đo riêng median 60,4–78,6 ms. Save dùng memory fallback do không có IndexedDB; **không cộng hai số thành thời gian browser**, chưa đo transaction IndexedDB. Phiên 100 Cards chỉ khoảng 1–2,5 ms normalize.

Hướng nâng cấp là giữ artifact bất biến riêng, ghi mutable state và event journal có durability từng rating. Cần browser trace và kiểm tra tab crash/reload/undo trước khi thay persistence; debounce đơn giản có thể làm mất câu trả lời chưa lưu.

## React/API và delivery còn chưa thống nhất

- **Worksheet:** [`BrowsePage.tsx:176`](../../frontend/src/features/browse/pages/BrowsePage.tsx#L176) và [`StudyCompletionCard.tsx:13`](../../frontend/src/features/study/components/StudyCompletionCard.tsx#L13) import eager; StudyPage import CompletionCard ngay khi mở phiên. Built Worksheet chunk 208.638 B raw/44.538 B gzip nằm trong static closure cả hai route. Dashboard source sau PR210 đã lazy modal; có thể áp dụng loading/cancel behavior đó cho hai caller còn lại.
- **Guide:** Browse import `ContextHelpButton` từ barrel ở dòng 177; barrel export cả GuidePage. Local graph kéo GuidePage 145.084 B raw/36.556 B gzip dù chỉ cần nút Help. Import component trực tiếp là ứng viên nhỏ, phải xác nhận lại emitted graph.
- **Bootstrap:** shared [`bootstrap.ts:5`](../../frontend/src/shared/api/bootstrap.ts#L5) dùng `['frontend','bootstrap']` và staleTime Infinity. [`useBrowseState.ts:107`](../../frontend/src/features/browse/hooks/useBrowseState.ts#L107), [`useAnkiSyncPage.ts:65`](../../frontend/src/features/import/hooks/useAnkiSyncPage.ts#L65) dùng `['bootstrap']`. Khi cache thứ hai trống, cùng endpoint session được gọi thêm; mutation/VerifyEmail invalidation chỉ nhắm key thứ hai còn để shell stale. Đây là vấn đề reachable từ code, chưa đo fresh-browser latency trong lần review này.
- **Cache assets:** HEAD public lúc 19:10 JST cho `index-BdqD3jZ0.js` và `button-a5mQ1ReM.js` trả `Cache-Control: public, max-age=0, must-revalidate`, có ETag. Baseline browser trước PR đã ghi nhận 44 JS responses 304 ở reload. Nên áp dụng immutable caching cho nội dung có hash tại frontend host, giữ HTML revalidation và rollout/rollback asset retention. [`app/spa.py:121`](../../app/spa.py#L121) cũng chưa đặt chính sách cache dài cho assets Flask tự serve, nhưng VPS release archive loại frontend: Flask asset path không được xem là nơi phục vụ frontend public hiện tại.

Local incremental import closure so với shell: Browse 749.297 B raw/201.280 B gzip; Study 462.134 B raw/127.400 B gzip. Đây là tổng các chunk, không phải lượng chắc chắn tải thêm khi người dùng đã có cache/shared chunks.

[Cloudflare Pages](https://developers.cloudflare.com/pages/configuration/serving-pages/) mô tả mặc định revalidation này và việc dùng cache dài cho assets có content hash; [cấu hình `_headers`](https://developers.cloudflare.com/pages/configuration/headers/) cho phép override headers của static responses. Cần đặt rule tại host phục vụ frontend thực tế, không chỉ thay Nginx backend.

## Today/Future: tối ưu phần đọc, giữ đúng phép tính load

[`stats_today_future.py:333`](../../app/services/stats_today_future.py#L333) lấy 7 scalar/Card trên toàn scope, gồm queue/due và state type/interval; sau đó mới bỏ suspended và lọc window bằng Python. Fixture 200 Cards due sau 400 ngày và 2 Cards trong window vẫn đưa 202 rows về ứng dụng để trả hai lượt review trong 30 ngày.

`daily_load` cố ý tính toàn scope, nên thêm WHERE range vào query hiện tại sẽ làm sai kết quả. Cần tách/gom due-window và load với parity riêng. `interval_days` trong state codec có dạng `f64:<16 hex>`; không thay decode bằng CAST decimal. Giữ Card units, due_day precedence, timezone và DST. Đây là bước tiếp theo sau việc bỏ N+1 đã hoàn thành, không phải lỗi N+1 cũ còn tồn tại.

## Phần đã dọn hoặc được giữ có chủ đích

- Migration `20261003_000050` đã drop năm bảng storage cũ; runtime NOTE chỉ hỗ trợ `CONSOLIDATED_V1`. NOTE Browse không còn aggregate `card_progress` rồi ghi đè bằng canonical counts. Không đề xuất làm lại các việc này.
- PR210 đã xử lý compact Dashboard, token theo compact contract, admin tree đọc lặp, grouped heatmap, selective timezone/preflight, preload và Worksheet của Dashboard. Chờ đo release đã triển khai trước khi đánh giá hiệu quả production.
- `card_progress`/LEGACY, wire v2/v3 và Anki ordinal compatibility còn reachable và nằm trong phạm vi đã quyết định giữ. `legacyEngine` vẫn là evaluator cho active `legacy-anki`; xóa theo tên file sẽ làm hỏng cả v4.
- `static/js/card_renderer_host.js` đang phục vụ sandbox renderer; source maps không nằm trong import closure thông thường. Không có bằng chứng chúng là JS chết gây nghẽn navigation.
- Startup maintenance đã **tắt mặc định ngoài TESTING** qua [`startup.py:42`](../../app/startup.py#L42). Nhận định mỗi Gunicorn worker luôn chạy create_all/seeds/cutover không còn đúng với source hiện tại.
- Retention đã triển khai: kiểm tra production lúc 19:09 JST cho timer `active`, `enabled`, approval file tồn tại. Đây là bằng chứng bật lịch, chưa phải bằng chứng mỗi lần job chạy thành công hoặc backlog đã hết.
- Còn models backfill/accounting, shadow WRITE/BACKFILL flags không có writer consumer runtime và một số envelope columns trong `StudyProgressSubject`. Shadow COMPARE flag vẫn được dùng bởi audit connection safety, ngoài HTTP hot path. Đây là backlog housekeeping/footprint chưa định lượng. `mirror_revision` vẫn cập nhật và nằm trong receipt; không drop các cột theo tên cũ hoặc coi việc xóa chúng sẽ làm Dashboard nhanh lên.

## Thứ tự triển khai đề nghị

1. Đo lại Dashboard với release chứa PR210; giữ baseline cùng User 1, network và trạng thái cây để phân biệt hiệu quả của bản đã merge.
2. Làm các thay đổi nhỏ: bỏ metadata query khi caller không cần, thống nhất bootstrap key, lazy Worksheet/direct Help import, cache hash assets. Kiểm tra query count, emitted graph và visual behavior.
3. Tách các PR Study: memoization artifact/runtime settings và maps cho replay; batch composition metadata; set-wise status/commit locks; đọc metadata tối thiểu trước chọn Card. Locking cần MySQL parity và concurrency checks, ngoài SQLite.
4. Sau đó xử lý Today/Future và canonical Browse reads; thay offline persistence khi có browser trace và durability tests.

Không có bằng chứng hiện tại để cam kết Dashboard dưới 800 ms, hoặc cộng các cải thiện của Study/Browse vào thời gian tải Dashboard.

## Kết quả cleanup đã triển khai trong nhánh

Các con số sau đo fixture/local build, không là kết quả VPS. [Artifact validation](artifacts/post_decoupling_cleanup_validation_20261004.json) giữ probe trước/sau, environment và giới hạn; production release chưa đổi.

| Luồng | Thay đổi | Trước → sau |
|---|---|---|
| Study status, 10/100/500 Notes | Gom complete sibling locks theo chunk 500 sau learner/session/Subject locks | **34/214/1.014 → 16/16/16 SELECT** trong fixture owned một deck; số rows vẫn theo phiên |
| Study commit, 10/100/300 events, một event/Note | Batched sibling reads, Note→membership/identity maps | **59/419/1.219 → 41/221/621 SELECT**; INSERT `3N+2`, UPDATE `N+1` vẫn giữ |
| Study replay, cùng fixture | Bỏ quét toàn session sau mỗi event | **120/10.200/90.600 → 30/300/900 pin lookups**; không bỏ sibling updates |
| Mở session, 500 Cards cùng template/options | Cache template artifact và policy theo effective inputs trong request | Build template/policy **500 → 1 lần**; content/state/version hashes/output vẫn theo Cards |
| Settings khi mở session 1/20 decks | Resolve runtime settings một lần và truyền vào options | **2/21 → 1 settings read**; tổng SELECT **25/64 → 22/42** |
| Composition catalog, 1/5/20 templates | Dùng grouped context + batch Template/NoteType và vị trí sort | Endpoint **11/31/106 → 9/9/9 SELECT**; direct discovery 20 templates có 2 SELECT, grouping thêm 1 |
| Browse tree | Caller counts-only bỏ metadata fallback | **17 → 16 SQL**, query `MIN(notes.created_at)` **1 → 0** |
| Dashboard | Fallback metadata chỉ cho deck thiếu NoteType | Giữ counts và oldest-owned/overlay precedence; chưa đo speedup production của subset |
| Browse canonical list, 201 Notes/202 Cards | Classifier chỉ đọc identity/presence; validate một lần/Note | Full Subject JSON reads **2 → 1**, projections **202 → 201**; tổng SQL vẫn 24 |
| Study-next complete, 201 Notes/202 Cards | Dùng refs `(id,note_id,created_at)`, hydrate khi đã chọn | **14 → 13 SQL**, full Card/Note entities **202/201 → 0/0**, content giả lập **826.106 → 0 B** |
| MCP counts/stats/queue | Counts dùng refs; queue lọc renderable IDs trước limit, hydrate selected Cards | Không hydrate content để trả counts/complete; vẫn scan scope/có các lượt đọc metadata riêng |
| React bootstrap | Shared hook/key và invalidation | Dashboard→Browse SPA trên browser fixture chỉ **1 session request** |
| Worksheet/Help | Shared lazy loader cho ba caller, Help import trực tiếp | Static gzip closure Browse **201.280 → 85.609 B**, Study **127.400 → 80.483 B**; shell không tính trong hai số này |
| Restore offline | Dựng Card map một lần, dùng lại cho events/final states | Lookup **O(E×C) → O(C+E)**; validators và toàn snapshot persistence được giữ |

Chỉ một phần SELECT tăng theo event đã được giảm: commit vẫn cần receipt/CAS/history reads và writes. Các lượt SQLite đơn lẻ 10/100/300 events không cho thấy tổng commit nhanh hơn đáng kể (khoảng 94/572/2.284 ms trước và 87/622/2.293 ms sau); không biến giảm query count thành tuyên bố speedup tổng thể. Mở phiên 500 Notes có median local khoảng 655→442 ms; status một lượt khoảng 599→107 ms. Đây là minh họa local, có tải test khác trên cùng máy.

Shared loader làm Dashboard closure tăng **687 B gzip**, shell tăng 139 B; đổi lại Browse/Study không kéo Worksheet trước action. `_headers` dùng immutable cho `/assets/*` (335 files build đều có hash, không có `public/assets`), HTML vẫn revalidate. Cần deploy lên host frontend thực tế để có tác dụng; không suy từ file local rằng headers public đã đổi.

MySQL **8.0.40, REPEATABLE READ**, generated schema riêng: owned fixture 10 Notes/2 Templates giữ đủ 20 sibling Cards khi phiên chỉ chọn 10; sibling SELECT **20→2**, vectors khớp. Overlay source Notes thuộc publisher cũng có parity. Probe hai connection cho thấy cập nhật Subject/Note/sibling chưa chọn và thêm sibling mới bị khóa khi transaction đang giữ vector, thành công sau release. Đây là kiểm tra cụ thể về current reads/locks, chưa phải load test nhiều phiên/deadlock distribution. Classifier scalar có parity 7 cases, gồm JSON null và các JSON scalar; các schema probe đã được drop.

Review phát hiện `IN(...)` có thể khiến MySQL scan/khóa cả Notes hoặc Cards ngoài lease. Bản cuối dùng bounded key relation (bound parameters), `STRAIGHT_JOIN`/PRIMARY point reads cho Notes và existing `ix_cards_note_id` range cho Cards; branch SQLite giữ IN. Probe cập nhật unrelated Note/Card không bị block, khớp helper cũ, đồng thời giữ khóa vector/gap cần thiết. Fixture **501 Notes/1.002 siblings** có 4 sibling SELECT; EXPLAIN SQL thật cho Note chunk500 `eq_ref/PRIMARY`, chunk1 `const/PRIMARY`, Card chunk500 `range/ix_cards_note_id`. Probe overlapping Subject helper cũng bị block theo hợp đồng. Không suy lock acquisition order nội bộ của engine từ `ORDER BY`.

Repro kiểm tra an toàn trong schema MySQL loopback sinh ngẫu nhiên: `python scripts/probe_study_session_scaling_mysql.py --output output/study_scaling_mysql_probe_20261004.json`. Script từ chối non-local/non-generated DB; source schema chỉ được đọc metadata collation. Production có index được dùng trong hint, đã xác minh qua information_schema chỉ đọc.

Regression tests mới kiểm tra chunk **501 Notes**, missing/detached/wrong learner/route, đủ siblings, source/local overlay và artifact đổi theo field schema; queue complete/waiting không tải content, selected render, multi-template count units và missing NoteType được skip trước limit. Frontend **43 focused tests**, lint/typecheck/build và isolated Chrome QA đã pass; lỗi chunk vẫn đóng được và không làm hỏng trang. Modular runner đã đăng ký repository/test mới để CI chọn đúng domain.

Backend modular run đã chạy **1.320 tests, 1 skip**, phát hiện ba failures: hai assertions Card-unit bị `.env` Note-count flag chi phối và một source mapping thiếu của probe Dashboard từ PR210. Fixture hiện pin Card units rõ ràng; mapping được bổ sung. Rerun đúng ba suites liên quan **30 tests PASS**, cộng các bộ Study 156, DB reads 57, queue 8 mới + 56 liên quan và composition 8 đều PASS (có overlap, không cộng thành tổng unique). Sau sửa fixture/mapping không chạy lại toàn bộ suite; final MySQL branch được probe và 14 scaling tests rerun. Không ghi full run ban đầu thành một full-suite PASS.

## Các chi phí tăng theo quy mô còn phải lên kế hoạch

`N`: Notes trong scope/phiên; `C`: Cards; `E`: events; `D`: decks; `T`: templates; `H`: historical events; `A`: active days; `S`: tổng sibling memberships được cập nhật cho các events; `B`: bytes nội dung. Các biểu thức là công việc ở tầng ứng dụng hoặc cardinality của read, không mô tả toàn bộ optimizer/IO.

| Luồng sau cleanup | Quy mô còn lại | Cần thiết / phần có thể tối ưu tiếp |
|---|---|---|
| Dashboard count | Read/aggregate theo **C_scope**, cây theo **D**; DISTINCT/sort có thêm cost | Đếm scope đúng là cần; repeated scan ứng viên cho state count cache/read model, hoặc Note-grain query có parity |
| Heatmap history / streak | Raw scan theo **H_range / H_total**, trả **A** ngày | Có thể đọc daily rollup; streak dài không được cắt 30 ngày để giảm cost |
| Heatmap future / Today-Future | State/Card scalar rows theo **C_stateful**, dù due-window nhỏ | Due-window có thể group/filter riêng; daily_load vẫn toàn scope và interval `f64` phải decode đúng |
| Study status | Rows/vector validation theo **N+C_siblings**; sibling query **2×ceil(N/500)** | Bỏ N+1 đã xong; kiểm complete lease vẫn cần, không gọi status O(1) vì fixture chỉ 16 queries |
| Study commit / batch continuation | Accepted event work **O(E)**, replay prefix còn theo accumulated events; propagate **S** | Receipt/fingerprint/history writes có chủ đích. Đo nhiều batches trước khi thiết kế checkpoint; không purge evidence để làm nhanh |
| Study issuance | **C** content/state/output, effective-template version hashing mỗi Card; build theo số effective templates/policies | Offline lease đầy đủ phải nhận Cards đã chọn. Cần browser/byte budget và giới hạn scope nếu phiên quá lớn |
| Queue next / MCP queue | Refs + availability scan **C**, sorting có thể **O(C log C)**; MCP còn đọc scope nhiều lần | Đã bỏ full content hydration; selection SQL/index/window đúng priority là phase riêng, không chỉ thêm LIMIT |
| Browse list | Full state validation theo unique **N**, render metadata theo **C** của page | Giữ fail-closed validation; pagination/projection phải đánh giá theo endpoint thực |
| Composition discovery | Group scan eligible Cards, metadata **T**, sort **O(T log T)**; queries theo chunk | N+1 đã bỏ; cache/revision chỉ cần nếu số templates/discovery frequency chứng minh lợi ích |
| Offline answer/save | Normalize/save **O(C+E+B)** mỗi rating; queue view scan **C**, candidate sort có thể **O(C log C)** | Map đã bỏ E×C; immutable artifacts + mutable journal cần durability/undo/crash tests, chưa thay storage |
| Chuyển thuật toán | History cut theo history của Note/sibling Cards | Là thao tác riêng cần evidence; counters analytics không thay lịch sử dùng cho initializer/audit |
| Import/rebuild summary | **O(H)** dữ liệu được import/rebuild | Batch/idempotency/checkpoint; chi phí tuyến tính nền cần đo, không thể gọi đã biến mất |

Session 5.000 Cards/50 events/fields 500 chars giữ **12.114.287 B** JSON-equivalent trước/sau. Normalize median local **35,634→27,930 ms**; 5.000 Cards không events không có cải thiện đáng kể. `structuredClone` còn khoảng 65 ms trong probe Node, không là browser IndexedDB latency. Bước tiếp theo phải đo transaction và main-thread trên browser trước khi thay mô hình lưu.

Phương án giảm các history scans bằng summary tables đã được điều tra riêng, gồm inventory production, A/B local với raw index alternatives, writer consistency và các lỗi của MASTER roadmap: [review bảng count](../plans/proposals/ANALYTICS_ROLLUP_FEASIBILITY_REVIEW_2026-10-04.md). Hướng đề nghị là daily history rollup shadow trước, deck-state counts sau; chưa có schema count mới trong bản cleanup này.
