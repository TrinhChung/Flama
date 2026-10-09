# Rà soát legacy và hiệu năng toàn ứng dụng — 10/10/2026

Các phần legacy có chi phí rõ nhất còn chạy là **API list Marketplace đang được React gọi, kiểm tra trùng của Flama Connect, fallback ownership của Statistics và cơ chế ghi nguyên phiên học offline**. Dashboard/Statistics còn có đường đọc raw mặc định dù summary/snapshot đã được triển khai. Không nên bắt đầu bằng xóa mọi file mang tên `legacy`: một số là thuật toán đang được hỗ trợ, decoder dữ liệu cũ hoặc facade không tạo thêm query.

## 1. Phạm vi và độ tin cậy

- Source: HEAD `8c3b8f03d8c4a68c202b0dbbb07367a4c5801874` và **working tree có thay đổi sẵn**. Báo cáo phản ánh code đang có trên máy, không chỉ commit HEAD. Không sửa application code hoặc các thay đổi sẵn của người dùng.
- Quét inventory 1.315 file code/config: `app/` 399, `models/` 104, `migrations/` 58, `frontend/src/` 713, `flama-audio/src/` 41. Inventory gồm test/locale, không có nghĩa đã đọc từng dòng của từng file. Truy vết sâu theo entry point, service, repository, model và caller React của các luồng chính.
- Đã kiểm tra web `wsgi.py -> create_app()`, Connect `connect_wsgi.py -> create_connect_app()`, React build, startup/config, auth/admin, dashboard/stats, browse/study, note/template/import, marketplace/overlay/releases/change requests, payments, media/TTS và audio companion.
- Đo mới: SQLite in-memory với dữ liệu giả lập; build Vite riêng ngoài `frontend/dist`; Node CPU/structured clone. Không mở database ứng dụng được cấu hình, không benchmark production, không chạy MySQL EXPLAIN hoặc Chrome/IndexedDB.
- Chỉ đọc một allowlist cờ không chứa bí mật trong `.env` local. Chưa biết flag, tỷ lệ learner LEGACY/NOTE, cache hit, lượng request hoặc revision schema production hiện tại.
- Mức tin cậy: **đã đo** = có probe hiện tại; **source** = reachable và có bằng chứng trong code, tác động thời gian cần đo; **có điều kiện** = phụ thuộc cấu hình/dữ liệu/caller.

Artifacts và probe tái chạy: [results.json](artifacts/legacy_perf_audit_20261010/results.json), [offline_results.json](artifacts/legacy_perf_audit_20261010/offline_results.json), [probe.py](artifacts/legacy_perf_audit_20261010/probe.py), [offline_probe.mjs](artifacts/legacy_perf_audit_20261010/offline_probe.mjs). JSON có thông tin môi trường, kích thước bundle, số query/entity và giới hạn phép đo. Các số byte JSON là JSON-equivalent, không phải bytes HTTP hoặc bytes vật lý của IndexedDB.

## 2. Danh sách ưu tiên

P1: chi phí rõ trên luồng sử dụng hoặc rủi ro tăng nhanh theo dữ liệu. P2: cần xử lý nhưng phạm vi hẹp hơn, hoặc cần profiling để chốt lợi ích. P3: dọn sau khi có đủ evidence retirement.

| ID | Ưu tiên | Luồng và phần còn lại | Kết quả / độ tin cậy |
|---|---|---|---|
| L1 | P1 | Marketplace React vẫn dùng list API cũ, đọc catalog rồi lọc, serialize definition từng item | 100 public + 500 private: 600 NoteType được nạp, 403 SELECT, ~1,85 MB JSON; **đã đo** |
| L2 | P1 | Connect duplicate/search quét full Notes bằng Python | 50 duplicate checks × 1.000 Notes: 50 SELECT, 50.000 lượt hydrate Note; **đã đo helper** |
| L3 | P1 khi phiên lớn | Offline Study ghi nguyên snapshot sau mỗi rating | NOTE/v4, 5.000 thẻ: ~11,48 MB JSON; normalize median ~27,5 ms Node; **đã đo CPU/clone**, chưa đo browser |
| L4 | P1 khi raw reads chiếm đa số | Summary/snapshot đã có nhưng raw là mặc định | Bốn cờ read/write chưa set trong `.env` local; defaults giữ raw/writes off; **source + cấu hình local**, production chưa xác minh |
| L5 | P2 | Statistics fallback cũ khi learner không có owned deck | Learner trống vẫn nạp 1.000 deck của người khác để trả 0 deck; **đã đo** |
| A1 | P2 | i18n còn gom cả hai ngôn ngữ/mọi namespace vào startup bundle | 52 locale sources; chunk ~134 KB gzip bằng phép nén của probe; **đã đo build** |
| A2 | P2 | Template Library list vẫn gửi toàn HTML/CSS | 100 templates với 16 KiB code/template: ~1,70 MB JSON, chỉ 3 SELECT; **đã đo**, vấn đề payload |
| A3 | P2 | Raw deck counts vẫn Card-grain/DISTINCT; Today/Future vẫn đọc toàn stateful scope | **source**, không có số latency mới của MySQL |
| A4 | P2 nếu sort/search chậm | Browse word/clone search có correlated JSON/release expressions | **source**, cần EXPLAIN trên dữ liệu đại diện |
| A5 | P2, P1 nếu cloud TTS dùng nhiều | Audio polling không dừng đúng khi trả voices rỗng; online TTS vẫn đồng bộ | **source**, cloud impact phụ thuộc usage |
| A6 | P2 | Publish options còn quét notes hai lần / subtree materialization | Kế hoạch MySQL ngày 09/10 đã tồn tại; **bằng chứng lịch sử**, chưa tái đo trong audit này |

`L` là seam/đường đọc tương thích cũ hoặc cơ chế giữ lại qua chuyển đổi. `A` là điểm nghẽn liên quan trên kiến trúc hiện tại; không gọi tất cả chúng là legacy model.

## 3. Các phát hiện cụ thể

### L1 — Marketplace vẫn nối UI mới với list implementation cũ

**Observed.** [`MarketplacePages.tsx:251`](../../frontend/src/features/marketplace/pages/MarketplacePages.tsx#L251) chọn `/api/shared/decks` hoặc `/api/shared/note-types`; query tại dòng 278 gọi endpoint này. Đây là caller hiện tại, không phải route bỏ không. Trang map toàn bộ kết quả thành card grid, chưa phân trang server.

**Evidence.** [`marketplace_note_type_service.py:178`](../../app/services/marketplace_note_type_service.py#L178) gọi `NoteType.query...all()` trước lọc visibility/search. Dòng 208 serialize từng NoteType với definition. [`marketplace_query_service.py:66`](../../app/services/marketplace_query_service.py#L66) đọc applications/templates theo từng item. List decks tại [`share.py:375`](../../app/routes/flashcards/share.py#L375) cũng đọc toàn `DeckMarketplaceItem` rồi lọc; stats đã batch nên không quy kết mọi phần của deck list là N+1.

Probe dùng 600 NoteType, 100 published, 500 private, mỗi public item có một template với 16 KiB source:

| Trường hợp | SELECT | ORM nạp | Kết quả | JSON-equivalent |
|---|---:|---|---:|---:|
| List cũ, search không khớp | 8 | 600 NoteType | 0 | 13 B |
| List cũ, không filter | 403 | 600 NoteType, 100 Template, 100 StudyApplication | 100 | 1.854.201 B |
| Hub compact hiện có, không filter | 7 | 100 NoteType | 100 | 226.563 B |

**Impact.** Query tăng theo item, tải cả những hàng không dùng, trả template code vào màn chỉ cần metadata. Dataset càng lớn càng tăng CPU, DB roundtrip, response và DOM. Hub compact cũng chưa phân trang nên không phải giải pháp scaling cuối cùng.

**Đối ứng.** Trước hết tạo list DTO gọn và batch metadata trong service; dùng filter/visibility ở SQL cho điều kiện tương đương; giữ definition ở detail/preview. Kế tiếp bổ sung pagination với sort ổn định và cập nhật caller React. Không đổi route sang hub một cách máy móc: response shape, sorting, saved/installed/owned status và bộ lọc khác nhau.

**Unknowns.** Tỷ lệ private/public và template sizes thật; domain/subject metadata có thể tạo thêm taxonomy reads ngoài fixture. Chưa chứng minh API MySQL p95 hoặc số KB tiết kiệm trên mạng.

### L2 — Connect còn kiểm tra identity theo toàn deck

**Observed.** [`connect/actions.py:274`](../../app/services/connect/actions.py#L274) tải tất cả owned Notes của target deck rồi normalize identity bằng Python. `check_note()` và `add_note()` dùng helper này; duplicate existing note lại được tìm trong [`resolvers.py:263`](../../app/services/connect/resolvers.py#L263). [`dispatcher.py:158`](../../app/services/connect/dispatcher.py#L158) lặp `check_note` cho từng phần tử `canAddNotes`; giới hạn request là 50 Notes.

**Evidence.** `_is_duplicate` được đo trên deck 1.000 Notes, mỗi Note có Body 4 KiB. Một check không khớp nạp 1.000 Notes; 50 checks nạp **50.000 lượt Note**, 50 SELECT, khoảng 1,71 s local SQLite trong một lượt đo. Đây là thời gian helper, chưa gồm parse/auth/HTTP và không phải production percentile.

`find_notes()` dòng 459 cũng quét toàn deck. Installed-clone branch còn gọi effective override/release reader cho từng source Note; request cache không làm distinct Notes thành một batch.

**Impact.** Một lần mining trả chi phí theo kích thước collection; batch checks tăng theo `B × N`. Toàn `field_values` được nạp dù chỉ cần identity.

**Đối ứng.** Gom duplicate checks theo `(learner, deck, NoteType, identity field)` trong request; đọc projection identity thay full JSON; tái dùng kết quả cho add/update. Trước khi chọn index/hash/SQL normalization, giữ đúng trim/case/Unicode normalization hiện tại. So sánh phương án projection trong request với lookup chuẩn hóa được lưu/backfill; chỉ chốt schema khi có workload và parity. Clone phải tra identity ở **applied release + overlay**, không source live.

### L3 — Offline persistence vẫn ghi toàn snapshot

**Observed.** [`useStudySession.ts:627`](../../frontend/src/features/study/hooks/useStudySession.ts#L627) await `saveStudySession(next)` mỗi rating. [`sessionStore.ts:410`](../../frontend/src/features/study/session/sessionStore.ts#L410) normalize whole session rồi `store.put(normalized)` ở dòng 419. Snapshot bao gồm immutable content/templates/policies cùng state/events/undo. Đường này được giữ cho cả wire v2/v3/v4.

**Evidence.** Fixture NOTE/v4 ban đầu, không events, Body 1 KiB mỗi Note, được normalizer hiện tại chấp nhận:

| Số thẻ | JSON-equivalent | Normalize median Node | Structured clone median Node |
|---:|---:|---:|---:|
| 100 | 231.141 B | 0,69 ms | 1,70 ms |
| 1.000 | 2.296.641 B | 4,20 ms | 13,89 ms |
| 5.000 | 11.484.641 B | 27,52 ms | 73,03 ms |

7 lượt đo sau 3 warm-up; không cộng hai số median để gọi đó là latency rating. Fixture tối thiểu không có frozen composition contract hoặc events; phiên thật có nhiều validation hơn. `structuredClone` chỉ minh họa chi phí sao chép, chưa đo serialization/transaction của IndexedDB.

**Đối ứng.** Profiling browser trước, rồi tách immutable artifacts khỏi mutable session checkpoint/event journal. Một answer ghi event + state delta trong cùng durable transaction; hydrate đủ snapshot khi restore; giữ undo, pending commits, content patch và quarantine. Không debounce toàn bộ persistence mà làm mất câu trả lời khi đóng tab/offline. Read cũ và dữ liệu cũ phải tồn tại trong thời gian chuyển đổi.

`buildSessionView()` còn quét cards theo mỗi tick, nhưng probe 5.000 thẻ chỉ ~0,96 ms Node trong fixture này; ưu tiên persistence trước, không xem timer này là lỗi P1 đã đo.

### L4 — Optimizations đã có nhưng default vẫn đọc raw

**Observed.** [`settings.py:151`](../../app/settings.py#L151) mặc định `REVIEW_ANALYTICS_WRITE_ENABLED=False`, `REVIEW_ANALYTICS_READ_MODE=raw`; dòng 156 tương tự cho deck count. Bốn cờ này chưa được set trong `.env` local đã đọc. Đây là trạng thái file local, không chứng minh production dùng raw và không thay thế kiểm effective env của process.

**Evidence.** [`review_analytics_read_repository.py:96`](../../app/repositories/review_analytics_read_repository.py#L96) có summary/shadow nhưng quay lại raw khi writes off, allowlist/policy/generation chưa đủ hoặc interval không khớp ngày. Shadow có sample chạy cả hai reader và vẫn trả raw. [`deck_count_snapshot_service.py:123`](../../app/services/deck_count_snapshot_service.py#L123) chỉ dùng counts khi writes enabled, read mode summary và dependency/policy/revision/expiry hợp lệ; cache stale/miss dùng raw. Cache này giới hạn owned eligible scope, không áp dụng máy móc cho overlays/admin-wide.

**Impact.** Chuyển progress sang NOTE không tự bỏ quét `ReviewEvent`/raw state counts. Có table và writer code không đồng nghĩa runtime đang hưởng lợi. Raw fallback là bảo vệ tính đúng, cần giảm frequency sau validation thay vì xóa fallback ngay.

**Đối ứng.** Inventory effective flags, ready generations, hit/miss/fallback reason và prewarm timer. Backfill/verify bằng workflow hiện có; rollout write -> sampled shadow -> summary allowlist -> mở rộng khi parity đạt. Deck snapshots rollout riêng. Revert reader về raw nếu drift; giữ writer/finalizer cần thiết và dữ liệu, không chuyển NOTE về LEGACY để rollback.

### L5 — Fallback stats nạp toàn bảng deck khi owned scope trống

**Observed.** [`deck_tree_query.py:164`](../../app/repositories/deck_tree_query.py#L164) giữ fallback cho dữ liệu chưa có `owner_user_id`: tải toàn bộ non-deleted Deck, tìm deck IDs qua `CardProgress`, rồi lọc Python. Caller là config Statistics trong [`stats_today_future.py:152`](../../app/services/stats_today_future.py#L152).

**Evidence.** Learner không có owned deck/progress, trong DB có 1.000 foreign Deck: **3 SELECT, 1.000 Deck hydrate, trả 0 Deck**. Trigger là owned query rỗng, không chỉ dữ liệu owner-null legacy. Chi phí phụ thuộc tổng deck của app thay vì scope learner.

**Đối ứng.** Lấy candidate IDs trước; rỗng thì trả sớm; chỉ query matching Deck ở SQL. Giữ semantics/admin cases trong PR nhỏ này. Sau đó audit owner-null rows và NOTE learner usage để quyết định backfill/retire đường `CardProgress`; không xóa progress/history để làm gate sạch.

### A1 — Startup i18n vẫn monolithic

[`main.tsx:3`](../../frontend/src/main.tsx#L3) import i18n; [`i18n/index.ts:6`](../../frontend/src/shared/config/i18n/index.ts#L6) import tĩnh 26 namespaces cho mỗi ngôn ngữ Việt/Anh. Build có **52 locale JSON sources trong static entry closure**.

Probe gzip level 9: i18n chunk 431.258 B raw / 134.353 B gzip; toàn static JS entry closure 1.120.089 B raw / 346.769 B gzip, chưa gồm CSS/font. Đây là tổng nén từng file trong build local, không là transferred bytes hoặc LCP browser. Khoảng 39% gzip của closure nằm ở chunk i18n.

**Đối ứng.** Giữ common/shell và fallback cần thiết cho locale đang dùng; load namespace còn lại theo route, locale khác khi chọn. Có loading/preload để không nháy translation key; giữ hình thức UI. Kiểm build graph và hai ngôn ngữ, không chỉ sửa import mà tưởng đã giảm tải.

### A2 — Template Library list trả source đầy đủ

[`template_library_service.py:83`](../../app/services/template_library_service.py#L83) lấy toàn library; serializer dòng 64 luôn gửi `front_html`, `back_html`, `shared_css` và schema. Repository đã eager/batch usages, nên đây **không phải N+1 đã xác nhận**.

100 templates, mỗi template ~16 KiB source: **3 SELECT, 100 Template/100 NoteType hydrate, ~1,70 MB JSON**. UI list thường chỉ cần title/usage/updated metadata.

**Đối ứng.** Metadata DTO + paging cho list; lấy source qua detail khi mở editor/preview. Audit caller để giữ flows dùng nguồn source hiện tại. Binding initialization/input-schema inference cho old templates là bước tương thích riêng, chỉ retire sau backfill và parity.

### A3 — Đơn vị state mới, query shape vẫn quét Card scope

[`deck_aggregation_service.py:183`](../../app/services/deck_aggregation_service.py#L183) dựng scope từ Cards JOIN Notes; dòng 256 chỉ đổi unit sang Note nếu flag count bật, rồi bốn `COUNT(DISTINCT ...)`. Snapshot giảm tần suất raw count cho eligible hits, nhưng cold/dirty/overlay/admin và Browse counts vẫn đi qua raw shape.

[`stats_today_future.py:309`](../../app/services/stats_today_future.py#L309) đọc toàn consolidated Card rows về Python để tính due rows và daily load; window filter diễn ra sau. Đây là scan set-wise, không là N+1 per-Note cũ.

**Đối ứng.** A/B Note-grain scope/EXISTS với MySQL EXPLAIN và multi-template/retired-template/clone/count-unit parity. Today/Future tách due-window aggregation khỏi `daily_load` toàn scope. Không thêm WHERE range vào toàn query cũ làm sai daily load; giữ due_day precedence, timezone/day boundary/DST và decode interval chính xác.

### A4 — Browse search/sort còn correlated expressions

[`browse_card_repository.py:50`](../../app/repositories/browse_card_repository.py#L50) chọn field Word bằng correlated scalar subquery; [`clone_effective_field_text_expression():126`](../../app/repositories/browse_card_repository.py#L126) kết hợp checkpoint/change/overlay qua các expressions theo Note. Khi tìm/sort nhiều Note trước pagination, query có thể tốn dù response chỉ một page.

**Đối ứng.** Capture SQL cho owned/installed, EXPLAIN trên 1k/10k/40k Notes và release history khác nhau. So sánh batch effective projection và indexed read model, gồm chi phí invalidation/backfill. Chỉ đổi sau khi giữ đúng **applied release + local overlay trước filter/order/page**. Chưa có bằng chứng trong audit này để cam kết tốc độ hoặc thêm một index cụ thể.

### A5 — Audio giữ cloud request đồng bộ và polling thiếu lifecycle

Online VoiceVox vẫn reachable qua [`learning/browse.py:251`](../../app/api/v1/learning/browse.py#L251) và [`browse_voicevox_service.py:184`](../../app/services/browse_voicevox_service.py#L184). Service generate gọi synthesis lần lượt cho các text khác nhau, dù có request-local audio cache. [`tts_provider_service.py:1314`](../../app/services/tts_provider_service.py#L1314) gọi `urlopen` đồng bộ với timeout cấu hình clamp 2–25 s. Adapter mặc định có URL `deprecatedapis.tts.quest`; tên URL không chứng minh dịch vụ upstream đã ngừng hoạt động.

Local companion đã có, nhưng [`useLocalAudioEngine.ts:620`](../../frontend/src/features/audio/hooks/useLocalAudioEngine.ts#L620) và dòng 655 tạo interval khi install/launch. Giới hạn số lượt chỉ kiểm trong `catch`; response `[]` thành công cứ poll tiếp. Các timer này không đăng ký cleanup khi unmount. Pairing có attempt bound nhưng cũng cần cleanup/abort và tránh interval async chồng request. Đây là path issue có điều kiện, chưa đo leak browser.

**Đối ứng.** PR nhỏ thống nhất cancellable polling, max attempts kể cả voices rỗng, dừng khi unmount/challenge đổi và không overlap. Cloud synthesis tách thành durable job/status với giới hạn concurrency; giữ cloud feature cho người đang dùng thay vì ép toàn bộ sang companion. Worker/job contract riêng cho audio, không dùng worker Study legacy để giải quyết I/O này.

### A6 — Publish options đã có kế hoạch đo, cần nối vào rollout

[Kế hoạch 09/10](../plans/performance/PUBLISH_OPTIONS_MYSQL_OPTIMIZATION_PLAN_2026-10-09.md) đã đo MySQL local, chỉ ra `batch_get_cards_count_by_deck_ids` và `batch_get_deck_note_types` quét cùng tập Notes hai lần; subtree representation tăng bộ nhớ với cây sâu. Code các helper vẫn hiện diện. Giữ task riêng, tái chạy [`bench_publish_options_mysql.py`](../../scripts/bench_publish_options_mysql.py) trên cùng snapshot trước implementation. Các số ~480 ms trong tài liệu đó là baseline cũ của MySQL local, không phải kết quả đo mới ngày 10/10 hay latency production.

## 4. Phần đã xử lý hoặc nên giữ

| Phần từng được gọi legacy | Trạng thái xác minh trong source hiện tại | Quyết định |
|---|---|---|
| Startup `create_all`, schema repair, seed, clone cutover | Maintenance gate mặc định false ngoài testing; `app/startup.py:42` trả sớm khi off | Không báo là chi phí luôn chạy. Xác minh override deploy; cập nhật docs sai |
| Full-copy clone mới | New install dùng overlay/release; cutover còn cho dữ liệu cũ | Giữ overlay-only; cutover không đưa lại vào request thường |
| Level/Topic/Lesson/Entry, Jinja UI | Routes retired trả 410; frontend là React, Flask template folder None | Chỉ maintenance/import overhead; không có chứng cứ là nguồn chậm request |
| NOTE storage trung gian cũ | `20261003_000050` có drop 5 bảng, runtime NOTE hỗ trợ consolidated | Không dùng số 18k queries/22 s của audit 29/09 để mô tả code hiện tại |
| Study sibling locking / replay scan quadratic | Có `lock_study_authority_siblings_many` và Note→siblings map | Không báo lại N+1/quadratic đã sửa |
| Study artifact/policy build mỗi Card | Có caches theo effective input trong request | Giữ cache key/invariants; không gọi mọi hashing là thừa |
| Composition discovery / Browse metadata / pristine reader | Batch discovery; counts-only Browse; classifier nhẹ và validate theo Note | Không lặp lại các phát hiện trước cleanup 04/10 |
| Worksheet / Guide eager load, bootstrap cache keys | Lazy Worksheet loader và shared bootstrap đã có; emitted Browse/Study closure không chứa actual Worksheet modal/GuidePage | Không báo lại chỉ vì barrel/export vẫn tồn tại |
| Offline restore O(events×cards) | Có cardsById map | Vấn đề còn lại là whole-snapshot save, không old lookup đã sửa |
| Hash asset cache | `frontend/public/_headers` có immutable `/assets/*` | Hosting thực tế chưa xác minh; không cam kết public cache đã đổi |
| Media streaming | Có X-Accel path, Flask fallback cho dev/test | Kiểm deployment flag/header trước tối ưu; giữ proxy/CSP/sanitization |
| `legacyEngine.ts`, `legacy-anki/1.0.0` | Thuật toán default active trong registry, có parity/golden fixtures | Không thay scheduler vì tên có legacy |
| `CardProgress`, wire v2/v3, ordinal fallback | LEGACY learners / lease / import / history readers vẫn có consumer | Retirement qua telemetry/gate; không drop hoặc switch authority tùy tiện |
| `flashcards_share_service`, Connect/marketplace facade, SQLAlchemy `Query.get` warnings | Facades chủ yếu re-export; deprecated API không tự chứng minh slowdown | P3 cleanup theo consumer inventory, ưu tiên query/payload thực tế |

`AGENTS.md`, `SYSTEM_ARCHITECTURE.md`, `FLASHCARD_V2_RUNBOOK.md`, `CLONE_CUTOVER_REPORT.md` còn mô tả startup cutover tự chạy; skill `nihongo-engineer` còn phần hybrid Jinja. Đây là tài liệu lệch code, cần cập nhật trong PR docs riêng.

Các vùng khác: auth/admin user lists đã có pagination; payment order queries đã paginate/selectinload, chưa có bằng chứng để gắn chúng với legacy bottleneck P1. Release/change-request có cursor/bounded diff; không nên rewrite các service này để dọn facade. Import CSV có chunk buffer và batch card slots, không còn mẫu lookup slots mỗi row ở đoạn đã kiểm; dirty tracking/cross-domain writers vẫn cần test khi tối ưu. Audio engine C# được rà source, chưa benchmark inference/download/native memory. Không kết luận các domain này đã tối ưu hết.

## 5. Kế hoạch triển khai đối ứng

### Giai đoạn 0 — Baseline và deployment inventory, khoảng 1–2 ngày công

1. Chốt commit + working-tree scope của triển khai; đọc effective env, schema revision, process topology, timer/worker status bằng workflow read-only. Tách local, staging và production trong artifacts.
2. Ghi p50/p95, SQL/request, rows examined/hydrated, payload raw/gzip, worker RSS, count cache/summary hit và fallback reasons cho Marketplace, Connect, Dashboard, Stats và session issuance/commit.
3. Dataset đại diện: 100/1k/5k/40k Notes; 1/5 templates mỗi Note; owned và installed; owner-null legacy; 50 duplicate checks; locale VI/EN; review history 10k/100k. Test 1/4/8 concurrent learners trên môi trường riêng.
4. Cập nhật docs startup/runtime đã lệch. Không lấy toàn suite pass hoặc build pass làm bằng chứng latency.

Nghiệm thu: benchmark tái chạy được, source/data/config có provenance; bảng baseline từng endpoint. **Chưa cần migration phá hủy hoặc đổi scheduler.**

### Giai đoạn 1 — Loại công việc thừa rõ ràng, khoảng 3–5 ngày công

| PR | Phụ trách | Thay đổi | Tiêu chí nghiệm thu đề xuất | Rollback |
|---|---|---|---|---|
| 1. Marketplace list | Backend + Frontend | Compact list DTO, batch metadata, visibility/search SQL theo parity; server paging và cập nhật React | Fixture L1 không tải 500 private; không gửi template source; query cho một page không tuyến tính theo item; mục tiêu ≤15 SELECT/page trên fixture đơn giản | Reader/DTO switch về cũ; giữ detail/preview contract |
| 2. Connect duplicate | Backend | Request-scoped batch identity reads, dùng lại duplicate result; tối ưu findNotes | B=50 cùng group chỉ một identity scan hoặc bounded lookup; không hydrate full Body; trim/case/Unicode/clone parity | Giữ helper cũ sau flag trong rollout; dữ liệu chưa đổi |
| 3. Stats fallback | Backend | Candidate IDs trước, return empty sớm, query matching Deck | Learner trống không hydrate foreign Deck; old owner-null/admin cases giữ kết quả | Revert code, không migration |
| 4. Audio polling | Frontend | Abort/cleanup, max attempts cả empty success, tránh overlapping polls | Fake timer test voices=[] hết hạn; unmount/challenge đổi không còn request; UI giữ nguyên | Revert hook/controller |

Đưa contract gọn cho Marketplace trước paging để dễ review. Không thay đổi toàn bộ service sharing hoặc giao diện thẻ trong cùng PR.

### Giai đoạn 2 — Hưởng lợi từ summary và giảm tải frontend, khoảng 3–5 ngày công

| PR | Phụ trách | Thay đổi | Gate |
|---|---|---|---|
| 5. Analytics rollout | Backend + vận hành DB | Backfill/verify history generations; write/shadow/summary allowlist; deck snapshots/prewarm riêng | Coverage đầy đủ cho writers, parity trên timezone/day boundary; theo dõi fallback reason và invalidation; rollback reader raw luôn hoạt động |
| 6. Frontend delivery | Frontend | Lazy locale namespaces và metadata-only/paged Template Library | Entry closure không mang 52 locales; locale switch/fallback không lộ key; list không gửi HTML/CSS; visual regression = 0 |
| 7. Publish options | Backend | Thực hiện kế hoạch 09/10: gộp scans, cải thiện subtree representation | Reuse benchmark/targets/parity đã mô tả trong kế hoạch; không thêm index nếu thiếu EXPLAIN/benefit |

Mục tiêu latency chỉ chốt sau baseline. Không có bằng chứng để hứa Dashboard dưới một con số cố định, hoặc cộng lợi ích Marketplace/Study vào Dashboard.

### Giai đoạn 3 — Thay cơ chế tốn chi phí theo toàn dữ liệu, khoảng 5–10 ngày công

1. **Offline persistence:** đo browser trace/IndexedDB trước; schema storage mở rộng -> dual reader -> journal/checkpoint -> canary -> ngừng writer cũ sau restore proof. Tests mất mạng, crash giữa transaction, reload/multi-tab, quota error, pending batch/commit retry, undo, content patch và quarantine. Giữ answers bền vững; không erase IndexedDB để tránh migration.
2. **Raw count/Today-Future/Browse:** A/B SQL từng endpoint, không gom thành rewrite. Chỉ chọn Note-grain aggregation/index/read model khi có count/filter/order parity và MySQL evidence. Nếu dùng derived storage, giữ source-of-truth + versioned invalidation/backfill; triển khai expand/backfill/cutover trước contract.
3. **Cloud audio:** nếu usage/worker occupancy cho thấy đáng làm, chuyển I/O thành audio job có idempotency, progress/cancel và concurrency bound. Kiểm authorization/media writes/timeout/retry trong worker. Không thay chức năng cloud bằng local companion ngầm.

Rollback: reader/backend flag hoặc old storage reader theo từng PR; giữ schema mở rộng/backfill đã tạo nếu cần rollback ứng dụng. Không downgrade NOTE learner sang LEGACY, không xóa review facts/receipts để rollback perf.

### Giai đoạn 4 — Retire compatibility theo evidence, thời gian phụ thuộc usage

Theo [P9 retirement telemetry runbook](../runbooks/P9_RETIREMENT_TELEMETRY_RUNBOOK.md), kiểm coverage liên tục tối thiểu 30 ngày cho wire/session/worker/ordinal; zero log không tự chứng minh zero consumer. Inventory REST aliases và third-party Connect/import clients riêng. Old-model owner-null/application binding data cần backfill/parity trước retire.

Chỉ contract/drop khi consumer gate, backup/restore và pending-work proof đã đạt. Thuật toán `legacy-anki` đang active không thuộc danh sách tự động xóa. Những PR facade/import/doc cleanup làm cuối, không dùng làm thành tích giảm latency.

Ước lượng trên là ngày công cho các thay đổi có scope rõ, không phải lịch cam kết; retirement không thể rút xuống số ngày công vì phụ thuộc cửa sổ quan sát. Ưu tiên thực tế: **Marketplace -> Connect -> Stats fallback/polling -> summary rollout -> frontend delivery -> offline persistence/SQL sâu -> retirement**.

## 6. Kiểm tra và tái chạy

Đã chạy build Vite current tree thành công và hai suite qua modular runner:

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_marketplace_query_service.py tests/test_stats_today_future.py --backend-only
```

Kết quả: **2 suite pass**. Các warnings `datetime.utcnow`/SQLAlchemy `Query.get` xuất hiện; chúng không được quy đổi thành giảm hiệu năng khi chưa có đo lường. Không chạy toàn test suite hoặc typecheck trong audit này; `build:ci` là Vite-only, không đồng nghĩa TypeScript check pass.

Tái chạy measurements với build output riêng:

```powershell
Push-Location frontend
npm run build:ci -- --outDir D:/Project/nihongo-audit-20261010-build --manifest
Pop-Location
.\.venv\Scripts\python.exe docs/architecture/artifacts/legacy_perf_audit_20261010/probe.py --build D:/Project/nihongo-audit-20261010-build --output docs/architecture/artifacts/legacy_perf_audit_20261010/results.json
node docs/architecture/artifacts/legacy_perf_audit_20261010/offline_probe.mjs
```

Python probe assert database là `sqlite:///:memory:` trước tạo fixtures. Node probe không listen HTTP hoặc mở IndexedDB. Khi triển khai, dùng `scripts/run_tests.py --module marketplace`, `--module connect_mcp`, `--module analytics`, `--module study`, `--module audio` phù hợp từng PR; kiểm module matrix tại `--list-modules`. Locking/query/schema changes cần thêm MySQL checks; offline/browser tests cần profile Chrome riêng theo AGENTS.md.

Phần còn cần xác minh: production effective flags/release/schema, summary/cache hit rate, LEGACY enrollment/old client usage, MySQL plans/concurrency và browser long tasks/IndexedDB. Những phần này là gate của triển khai, không phải kết quả đã đạt của báo cáo.
