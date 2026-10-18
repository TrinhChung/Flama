# Kết quả triển khai đối ứng legacy và hiệu năng — 10/10/2026

Đã triển khai tối ưu Marketplace, Template Library, Flama Connect, Statistics fallback, i18n, Audio polling và Publish options. Offline Study có reader tương thích và writer tách checkpoint đã kiểm chứng, nhưng **writer mới mặc định tắt** để rollout theo canary. Chưa bật Analytics summary rộng hoặc triển khai lên production.

Đây là kết quả tiếp nối [báo cáo rà soát](../architecture/LEGACY_PERFORMANCE_AUDIT_2026-10-10.md). Baseline audit được giữ nguyên. Runtime trước triển khai bắt đầu ở `6d03826`; các thay đổi đã được đưa vào working tree và một số commit của phiên làm việc. Artifacts ghi HEAD/source hashes tại từng phép đo; HEAD cuối `50d0883dfc074f6134ed75f64e9db721458a5089` không đại diện cho toàn bộ working tree. Xung đột merge nhánh Study quickstart `a954270ee3b28fcde91ac4b9b548c62b4fdb6633` đã được giải quyết và stage; merge chưa commit trong lượt xử lý này.

## 1. Thay đổi đã thực hiện

| ID audit | Đối ứng trong code | Trạng thái và giới hạn |
|---|---|---|
| L1 | List Marketplace metadata gọn, page 24, batch metadata/stats; lọc visibility/pricing và sort ở SQL; React dùng list mới | Hoàn tất đường list mới. Search/tag taxonomy còn xử lý tập candidate để giữ kết quả; API full cũ còn cho client tương thích |
| L2 | Identity projection, cache trong một request `canAddNotes`; dùng lại lookup cho duplicate/add/findNotes; clone đọc applied release + local overlay theo batch | Hoàn tất. Không hydrate toàn Note/Body cho kiểm tra trùng. Deck/model catalog resolution vẫn nạp một lần trong request |
| L3 | Tách immutable cards/content/template/policy/composition bundle khỏi checkpoint; cùng transaction với overrides, events/undo/pending batch | Reader hoàn tất, writer canary `VITE_STUDY_SPLIT_STORAGE_ENABLED=1`; default `0`. Chưa phải event journal append-only; validation và tìm overrides vẫn tuyến tính |
| L4 | Giữ raw/off theo gate Analytics hiện có | Chưa bật rộng: writer overhead chưa đạt tiêu chí của đợt Analytics trước |
| L5 | Lấy Deck IDs từ progress của learner trước, rỗng trả sớm; chỉ hydrate Deck khớp | Hoàn tất; giữ fallback owner-null/legacy progress và thứ tự cũ |
| A1 | Dynamic locale/namespace imports, boot common/shell; Suspense và preload chỗ gọi `i18n.t` trực tiếp | Hoàn tất; lỗi tải có màn retry, đổi ngôn ngữ thất bại giữ ngôn ngữ cũ; thử lại được khi mạng phục hồi |
| A2 | Template Library metadata DTO và paging; library/attach tải thêm 24 item; detail/full vẫn giữ source | Hoàn tất; template có schema trống cũ vẫn cần một lượt đọc HTML theo batch để suy luận input |
| A3, A4 | Raw count/Today-Future và Browse effective search/sort | Chưa đổi query: cần profiling MySQL đại diện và parity trước refactor |
| A5 | Polling install/launch/pairing có AbortSignal, không overlap; dừng khi unmount/đổi engine, giới hạn cả response voices rỗng | Hoàn tất polling; cloud synthesis đồng bộ cần task worker riêng |
| A6 | Gộp facts `(deck_id, note_type_id)` qua `LEFT JOIN Card`, giữ notes không có card; index cây iterative với summary giới hạn kích thước | Hoàn tất code và parity; mục tiêu latency tài khoản lớn chưa đạt ổn định |

Các đường overlay-only, scheduler/day boundary, sanitization/CSP/media proxy và wire cũ được giữ. Không thêm migration hoặc DDL index trong đợt này. Tài liệu `SYSTEM_ARCHITECTURE.md` đã sửa startup maintenance theo code: mặc định tắt ngoài testing, không coi cutover/schema repair là công việc luôn chạy ở mỗi lần boot.

## 2. Kết quả đo có thể đối chiếu

### Fixture SQLite và build

Fixture list có 600 NoteTypes (100 public, 500 private), 100 templates với source khoảng 16 KiB/template; fixture Connect có 1.000 Notes. Số byte là JSON-equivalent, không phải HTTP transfer. Paging thay đổi số item trả về có chủ đích.

| Phép đo | Trước | Sau |
|---|---:|---:|
| Marketplace: full list cũ → compact page 24/100 | 403 SELECT; 600 NoteType; 1.854.201 B | 3 SELECT; 24 NoteType, không Template/FieldDef; 41.823 B |
| Template Library: full list → compact page 24/100 | 3 SELECT; 100 Template; 1.698.842 B | 5 SELECT; 24 Template; 12.964 B |
| Duplicate helper 50 checks, cùng group, cache một request | 50 SELECT; 50.000 lượt hydrate Note | 1 identity SELECT; 0 hydrate Note |
| Statistics: learner trống, 1.000 foreign Deck | 3 SELECT; 1.000 hydrate Deck | 2 SELECT; 0 hydrate Deck |
| Static JS entry closure, raw | 1.120.089 B | 696.709 B |
| Static JS entry closure, gzip từng file level 9 | 346.769 B | 216.121 B, giảm 37,7% |
| Locale JSON trong static entry closure | 52 | 0; 52 dynamic entries |

Actual dispatcher `canAddNotes` 50 item hiện dùng 7 SELECT và không hydrate Note; không có transport baseline cũ để tính phần trăm latency. Taxonomy lạnh của Marketplace có thêm 6 queries ngoài fixture 3 SELECT. Full compatibility list Marketplace vẫn có 402 SELECT/1,85 MB; Template Library full response giữ nguyên. Cải thiện list thuộc caller React dùng compact/paging, không áp dụng tự động cho mọi client cũ.

Build graph loại `testResources` khỏi production. Common/shell và dictionaries theo route tải động ngoài static entry closure; số giảm gzip không chứng minh mức cải thiện LCP hoặc tổng bytes của một phiên truy cập.

Evidence: [probe/results](../architecture/artifacts/legacy_perf_implementation_20261010/results.json), [build manifest summary](../architecture/artifacts/legacy_perf_implementation_20261010/build_results.json), [cách chạy và fixture](../architecture/artifacts/legacy_perf_implementation_20261010/README.md).

### Offline IndexedDB trên Chrome riêng

NOTE/v4, 1 KiB content/note, không answer events; mỗi case 3 warm-up + 7 checkpoints, chờ IndexedDB transaction hoàn tất. Writer mới chỉ bật trong Vite process thử nghiệm.

| Số cards | Checkpoint median trước | Checkpoint median sau | First save sau |
|---:|---:|---:|---:|
| 100 | 2,7 ms | 1,7 ms | 18,9 ms |
| 1.000 | 20,8 ms | 6,1 ms | 41,5 ms |
| 5.000 | 84,6 ms | 19,0 ms | 124,7 ms |

Checkpoint chưa có overrides/events khoảng 1,1 KiB so với toàn session 5.000 cards khoảng 11,48 MB. Bundle lớn vẫn ghi khi save đầu hoặc content patch; checkpoint tăng theo cards đã thay đổi/events/undo. Không khẳng định lợi ích tương tự cho first save, phiên đã trả lời hết hoặc production latency.

Đã kiểm tra upgrade inline DB2 → DB3, answer/undo/reload/resave, pending batch/commit identity, content patch, abort atomic cả artifact lẫn checkpoint, fallback memory mới hơn khi disk write lỗi, missing-artifact quarantine/removal, reader flag-off đọc DB3 và ghi inline, tab khác xóa artifact cache, NOTE/v4 siblings/pins/receipt. Artifact thiếu không âm thầm dựng phiên sai.

Evidence: [trước](../architecture/artifacts/legacy_perf_implementation_20261010/browser_persistence_before.json), [sau](../architecture/artifacts/legacy_perf_implementation_20261010/browser_persistence_after.json), [durability/rollback/cross-tab](../architecture/artifacts/legacy_perf_implementation_20261010/browser_durability_results.json). Các browser dùng isolated profiles, không can thiệp profile cá nhân.

### MySQL local, read-only

Connect: 128 Notes × 3 fields, 384 so sánh identity projection với full JSON sau normalization đều khớp. Phép đo giới hạn này kiểm MySQL JSON type/Unicode/whitespace parity, không là load test Connect. [Evidence](../architecture/artifacts/legacy_perf_implementation_20261010/connect_mysql_projection_results.json).

Publish options: cùng local dump, 3 warm-up + 30 warm HTTP samples mỗi tài khoản. Bảng dùng lượt AFTER cuối có hash đầy đủ của helper mới; exact JSON SHA-256 giữ nguyên trước/sau và giữa hai service.

| User fixture | Median trước → sau | p95 trước → sau | SQL/request trước → sau |
|---:|---:|---:|---:|
| 1, 1.528 decks / 39.325 cards | 518,0 → 430,9 ms | 638,2 → 626,0 ms | 8 → 7 |
| 4 | 150,8 → 107,9 ms | 250,8 → 202,4 ms | 9 → 8 |
| 15 | 24,4 → 25,3 ms | 35,0 → 41,0 ms | 7 → 6 |

Một lượt AFTER trước đó của User 1 đạt 390,1 / 515,1 ms; lượt cuối vẫn vượt mục tiêu 400 / 550 ms trong [kế hoạch Publish](../plans/performance/PUBLISH_OPTIONS_MYSQL_OPTIMIZATION_PLAN_2026-10-09.md). Không đánh dấu gate latency này pass. User 15 không cải thiện thời gian dù bớt query.

Stress index cây: chain 2.000 → 4.000 nodes dùng khoảng 0,66 → 1,32 MiB allocations, tỷ lệ 2,01×; cycle cũng tuyến tính và không cộng trùng. A/B query cuối giữ `IN(deck_ids)`: median query gộp 278,2 ms, so với hai query riêng 239,2 và 125,4 ms; thêm JOIN scope chậm hơn. Đây là query timing riêng, không cộng median thành latency HTTP.

Evidence: [MySQL summary và provenance](../architecture/artifacts/legacy_perf_implementation_20261010/publish_mysql_summary.json). Không ghi data/DDL hoặc bật startup maintenance khi benchmark.

## 3. Kiểm chứng và xử lý merge Study

- Backend: 212 tests trên 14 files liên quan Connect, Marketplace, Template Library, Deck tree, Stats, Publish/share và Flashcard API đã pass trong đợt triển khai.
- Sau xử lý merge: 431 frontend tests trên 47 files thuộc Study, Audio, Template Library list/attach, Marketplace list, i18n/language switch và Audio client đã pass; thêm 5 tests Publish trên 2 files đã pass.
- `npm run build -- --outDir D:/Project/nihongo-legacy-implementation-final-build --manifest` pass, gồm TypeScript và production bundle. Build dùng flag mặc định writer-off; writer-on đã kiểm bằng browser/probe riêng.
- Diff check và lint phạm vi sửa được kiểm; không chạy full suite, không lấy test pass làm bằng chứng production performance.
- Bốn xung đột Study đã stage: giữ `discardSession` cùng `applyTemplateBindings`, đưa counts/setup vào picker hiện tại và giữ màu/background/padding của picker. Component preparation cũ không còn caller đã được bỏ; test chuyển sang dialog mới để kiểm explicit-null, cancel/reopen, reset-default, saving lock và template không có input. Học một chạm và discard đều có test qua.

Không có kiểm tra pixel toàn app hoặc benchmark desktop TTS thực. Những thay đổi CSS của luồng mới từ nhánh Study được giữ theo chức năng mới; không tuyên bố đã có toàn bộ visual snapshots.

Lệnh frontend đã chạy sau merge, từ `frontend/`:

```powershell
npm run test -- src/features/study src/features/audio src/features/template-library/pages/TemplateLibraryPage.test.tsx src/features/template-library/components/AttachTemplateDialog.test.tsx src/features/marketplace/pages/MarketplacePages.test.tsx src/shared/config/i18n src/shared/ui/LanguageSwitcher.test.tsx src/lib/flamaAudioClient.test.ts
npm run test -- src/features/marketplace/components/PublishDeckTree.test.tsx src/features/marketplace/components/PublishNoteTypeSelector.test.tsx
```

Backend có thể kiểm lại theo phạm vi bằng `.venv/Scripts/python.exe scripts/run_tests.py --file <test-files> --backend-only`; không cần chạy `--all` cho lượt review này.

## 4. Kế hoạch rollout và rollback

| Bước | Triển khai | Điều kiện mở rộng / rollback |
|---|---|---|
| 1. Backend list/Connect/Stats/Publish | Deploy API trước; compact/paging là contract opt-in, full/detail còn giữ | Đối chiếu owned và installed release/overlay, filters/sort/pages, payload parity; quan sát SQL/request và p95. Revert optimization code nếu sai; không cần rollback data/schema |
| 2. React list/i18n/audio + offline reader | Build/deploy với `VITE_STUDY_SPLIT_STORAGE_ENABLED=0`, giữ assets các build còn đang có tab hoạt động | Kiểm VI/EN, lỗi dictionary/network, retry load-more, dialog, empty-voices và cancel. Hoàn tất bước reader tương thích trước khi bật split writer |
| 3. Offline writer canary | Build flag `1` cho môi trường/cohort riêng sau khi các tab dùng bundle DB2 cũ đã được đóng/cập nhật | Theo dõi durable-save failures, quarantine, restore/undo/commit parity và storage quota; benchmark thêm phiên nhiều events và 1/4/8 tabs. Mở rộng khi không mất answer/commit identity và chi phí checkpoint không tăng bất thường |
| 4. Rollback offline | Deploy **reader mới tương thích**, rebuild flag `0`; reader hydrate DB3 rồi ghi inline và dọn bundle trong transaction | Không rollback sang binary DB2 trước thay đổi sau khi DB đã upgrade lên 3. Không xóa IndexedDB để rollback; bản cũ không đọc được DB3 |
| 5. Analytics riêng | Inventory effective env/ready generations → giảm writer overhead → backfill → sampled shadow → summary allowlist | Chưa bật writer/read summary rộng: [gate hiện tại](ANALYTICS_COUNTS_IMPLEMENTATION_2026-10-06.md) là ≤5 ms / ≤10% write overhead, đợt trước còn vượt. Drift thì reader về raw, giữ dữ liệu và authority hiện tại |

Các biến Vite là build-time; đổi env sau khi build không đổi bundle đang phục vụ. File `.env.example`/`.env.production.example` ghi default và rollback; không thay `.env` thực tế hoặc cờ production trong đợt này.

## 5. Việc còn lại theo ưu tiên

1. **P1 rollout evidence:** canary offline với phiên dài có events/content patches; đo Marketplace/Connect/Stats p50/p95 dưới tải staging, error/quarantine rate và SQL/request. Phép đo local ở trên đủ để review implementation, chưa đủ kết luận SLO production.
2. **P1 Analytics gate:** tối ưu history finalizer/writer round trips và đo NOTE/concurrent writers; sau đó shadow/parity trước summary. Không bật flag để che chi phí ghi chưa đạt.
3. **P2 Publish latency:** A/B xen kẽ trên cùng dump cho User 1; thử covering index chỉ trên schema benchmark riêng với EXPLAIN ANALYZE, write-cost và parity trước migration.
4. **P2 Connect/Marketplace scaling:** giảm catalog resolution một lần của Connect; push candidate search/tag xuống SQL khi chứng minh được semantics, theo dõi client còn dùng full list trước retirement.
5. **P2 A3/A4:** Note-grain raw counts, Today/Future tách due window khỏi daily-load aggregation; Browse effective release/overlay trước filter/order/page. Cần timezone/DST, multi-template, retired-template và clone parity.
6. **P2 cloud Audio:** durable job/status, concurrency và cancellation cho synthesis; dùng lại [kế hoạch async](../plans/performance/TASK_01_VOICEVOX_ASYNC_PIPELINE.md), không ép người dùng bỏ cloud feature.
7. **P3 retirement:** thu telemetry ít nhất 30 ngày cho LEGACY learner/wire/full-list consumers theo kế hoạch audit rồi mới bỏ decoder/model/facade. Không drop `CardProgress`, wire v2/v3 hoặc thuật toán `legacy-anki` chỉ vì tên gọi.

Các bước trên là việc tiếp theo có gate rõ ràng. Không có deployment/push, migration phá hủy hoặc chuyển authority scheduler trong kết quả hiện tại.
