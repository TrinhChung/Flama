# Browse — pha xử lý nợ kỹ thuật

Ngày: 2026-10-24. Pha đầu xử lý B00 (công cụ baseline/contract) và B08 (sort tên deck local). Theo yêu cầu tiếp theo, đã tách Browse frontend theo FSD và hoàn thành B01 compact NoteType. B02–B07 còn lại cho pha tiếp theo.

## Thay đổi đã thực hiện

### Browse frontend và B01

- Chuyển route composition sang `frontend/src/pages/browse/`; page phối hợp Browse, local audio, worksheet và guide qua public APIs. Helper audio dùng chung chuyển xuống `entities/audio`, giữ re-export ở đường dẫn cũ cho caller chưa migrate.
- `useBrowseState.ts` từ hơn 1.100 dòng còn 31 dòng điều phối; tách filters/data, selection, editor, batch actions, dialog state, TTS và TTS settings. Logic SVG dialog chuyển sang `useBrowseStrokeModal`.
- Browse dùng `api/browseApi.ts` và `api/strokeApi.ts` qua shared HTTP client; giữ URLs, CSRF/cookies, revision preconditions, native arrays và invalidation. GET queries truyền AbortSignal. Các helper field và stroke DTO dùng chung nằm ở entity với public entries không tải UI.
- `GET /api/note-types?compact=1` có cache key `['note-types', 'browse', 'compact']`, không ghi đè full response; invalidation theo prefix `['note-types']` vẫn cập nhật Browse. Giữ preload để form mở như trước.
- Kiểm chứng: **119 tests / 17 suites đạt** trong lượt focused Browse/page, bootstrap, array, audio và Study quick edit, trên cả worktree và checkout chính; gồm cache isolation/invalidation, compact transport, array create/edit, draft trong lúc save/refetch, revisions và selection xuyên trang. TypeScript, lint các thư mục thay đổi và Vite production build đạt. Modular runner đã cập nhật đường dẫn page và bổ sung API/hook/dialog suites.
- Chrome profile riêng, API fixtures giống nhau trước/sau: form create/edit ở 1440×1000 và 390×844 trùng ảnh hoàn toàn (0 pixel khác biệt cho cả 4 cặp). Browser xác nhận URL compact, không có page error. Artifacts local: `output/playwright/browse-fsd-b01/`; fonts của worktree dùng dependency junction được phục vụ từ Vite baseline để so sánh cùng font.
- Đo service đọc trên MySQL 8.0.40 bằng `benchmark_browse_mysql.py`, cùng tài khoản local, 1 warmup và 3 samples/case: 6 NoteType; full **60 SQL / 180.463 bytes**, compact **3 SQL / 16.349 bytes**. Payload mỗi case ổn định cả 3 samples. Artifacts local: `note-types-cases.json`, `note-types-mysql.json` trong thư mục trên. Đây không phải HTTP/load benchmark; không thay đổi backend/schema.

Các shim ở root helpers/audio vẫn phục vụ caller cũ. Hai import legacy từ Study vào Browse (detail DTO và SVG dialog) chưa migrate trong task Browse này; cần xử lý khi tách composition của Study, không coi toàn bộ frontend đã sạch FSD.

### B00: đưa phép đo khỏi script tạm

- Thêm [script baseline](../../scripts/benchmark_browse_mysql.py) nhận cases JSON, không gắn cứng tài khoản/deck trong code.
- Mỗi sample có app/request context và session riêng; tránh lỗi reuse ORM objects trong request cache giữa các lượt.
- Dùng audit factory, loopback MySQL và guard SQL ghi. Báo cáo giữ hash kết quả, metadata và phase timings; không ghi content/SQL parameters/credentials.
- Đo lặp và warmup tùy chọn; tách scope, count, page/hydrate, authority, release/override/format và serialization. EXPLAIN là chẩn đoán riêng, không cộng vào elapsed.
- So sánh toàn payload có thứ tự bằng hash, cùng case inputs và clock UTC. Cùng timeout hoặc error không được chứng nhận là tương đương.
- Thêm [suite MySQL contract](../../tests/test_browse_mysql_contract.py) và [tests công cụ](../../tests/test_browse_baseline_tool.py). MySQL tests dùng schema được tạo riêng, có guard cleanup; không mở rộng SQLite integration.

Hướng dẫn và commands: [Browse MySQL baseline](../runbooks/BROWSE_MYSQL_BASELINE.md).

### B08: sort theo tên deck hiển thị trước pagination

Lỗi đã tái hiện trên MySQL ở cả release clone và snapshot clone: SQL sort theo source name làm ASC trả `Z local root` trước `A local child`, DESC trả ngược kỳ vọng.

Đổi sang biểu thức effective deck name trong [browse repository](../../app/repositories/browse_card_repository.py), dùng mapping source/local đã được service xác định. Tên local được bind làm SQL values; giữ nguyên join deck hiện có. Sort này được áp trước LIMIT/OFFSET. Owned Notes vẫn dùng tên deck của chính Note, kể cả khi deck cũng là source của install. Giữ `Card.updated_at DESC` và `Card.id ASC` làm tie-break hiện có.

Không đổi count, visibility, đại diện một Note, word/due sort, API response shape, clone values, transaction/locks hay schema. Không thay đổi React UI và không tuyên bố cải thiện latency từ bản sửa ordering.

## Bằng chứng và kiểm chứng

- Trước sửa: 8 case MySQL chạy; bốn subcases ASC/DESC trên release/snapshot clone fail đúng thứ tự tên local. Các case query bounds/scope hiện có pass.
- Sau sửa: **18 tests pass** (13 MySQL contract + 5 tool tests), không skip; modular runner hoàn tất trong khoảng 263 giây. Bao gồm schema deltas/arrays, retired/historical pairs và context/write guard. Raw-driver write guard được kiểm độc lập với guard của ORM.
- Script baseline chạy trên MySQL 8.0.40, migration `20261020_000071`: hai selected-deck cases owned/clone, mỗi case ba measured samples; lượt đầu thêm một warmup. Hai lần chạy đều ổn định payload; comparison trả `equivalent=true`. Đây là kiểm tra công cụ, không phải benchmark cải thiện ứng dụng.
- Các artifacts local của lần kiểm chứng công cụ: `.tmp/browse_tech_debt_cases.json`, `.tmp/browse_tech_debt_baseline.json`, `.tmp/browse_tech_debt_compare.json`. Không dùng chúng làm fixture portable có IDs cố định; JSON input phải chọn lại theo database.
- Final suite và manifest: command trong runbook; manifest local `.tmp/browse_tech_debt_test_manifest.json` xác nhận `complete=true`, `success=true`, `tests_run=18`. [Evidence đã rút gọn](BROWSE_TECH_DEBT_IMPLEMENTATION_2026-10-24.evidence.json) giữ kết quả CLI và tóm tắt manifest.

## Giới hạn

- B00 đã có nền tảng service baseline và MySQL correctness matrix. HTTP/load, concurrent review, p95 production và các phân bố release/override lớn hơn vẫn cần thực hiện khi bước sang tối ưu.
- MySQL tests tạo schema từ ORM metadata để kiểm query/runtime contract; không thay thế rehearsal Alembic migration chain.
- Sort dùng cùng quy tắc mapping đầu tiên đang được Browse dùng khi nhiều installs trỏ cùng source. Pha này không thay đổi quy tắc chọn install/dedup của toàn collection.
- Bản điều tra đã sửa diễn giải `status=all`: current list predicate lọc suspended nhưng chưa truyền `today_day_index` để áp nhánh buried. Không sửa scheduling/burial semantics trong pha này.

## Công việc để lại cho pha tối ưu

B02 count/preview; B03 clone search expressions; B04 scope batching; B05 sidebar aggregate/cache; B06 authority reader; B07 hydrate/DTO. B01 đã dùng compact; lazy load là tùy chọn chưa áp dụng. Dùng baseline/contract để đánh giá các thay đổi tiếp theo.
