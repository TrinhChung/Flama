# Browse — pha xử lý nợ kỹ thuật

Ngày: 2026-10-24. Phạm vi được chọn theo yêu cầu làm nợ kỹ thuật trước, tối ưu hiệu năng sau: B00 (công cụ baseline/contract) và B08 (sort tên deck local). B01–B07 được giữ cho pha tiếp theo.

## Thay đổi đã thực hiện

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

B01 compact/lazy NoteType; B02 count/preview; B03 clone search expressions; B04 scope batching; B05 sidebar aggregate/cache; B06 authority reader; B07 hydrate/DTO. Dùng baseline/contract mới để đánh giá các thay đổi này, không tự gộp vào bản sửa nợ kỹ thuật.
