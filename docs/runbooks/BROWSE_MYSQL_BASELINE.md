# Đo và đối chiếu Browse trên MySQL local

Công cụ: [benchmark_browse_mysql.py](../../scripts/benchmark_browse_mysql.py). Phục vụ task B00 trong [kế hoạch Browse](../plans/BROWSE_PERFORMANCE_TASKS_2026-10-24.md). Đây là phép đo service trong Python, không phải HTTP/browser benchmark.

## 1. Điều kiện chạy

- Chạy từ repository root bằng `.venv/Scripts/python.exe`, dùng cấu hình MySQL trong `.env` hiện có.
- Script chỉ chấp nhận MySQL loopback, không cho database bind phụ. Audit factory tắt startup maintenance; không tạo bảng, migrate hoặc seed trong database được cấu hình.
- Trong lúc gọi service, chặn SQL ghi và server-side output/lock functions. Locking SELECT của Browse vẫn chạy để giữ contract. Rollback sau mỗi sample; engine được dispose khi xong.
- Chọn thời điểm dữ liệu không bị sửa trong lúc so sánh. Dữ liệu thay đổi có thể làm digest khác dù code không đổi; khác digest cần điều tra, không tự kết luận regression.

## 2. Chuẩn bị cases JSON

Tạo file riêng, ví dụ `output/browse-cases.json`; thay `user_id` và `deck_id` bằng IDs hợp lệ trên database đang khảo sát:

```json
[
  {
    "name": "owned-selected",
    "operation": "cards",
    "user_id": 1,
    "admin_mode": false,
    "timezone": "Asia/Tokyo",
    "query": {"deck_id": 1438, "per_page": 20, "sort_by": "due"}
  },
  {
    "name": "sidebar",
    "operation": "decks",
    "user_id": 1,
    "timezone": "Asia/Tokyo"
  },
  {
    "name": "note-types-full",
    "operation": "note_types",
    "user_id": 1,
    "compact": false
  }
]
```

`cards` nhận các query keys: `deck_id`, `include_subdecks`, `all_templates`, `q`, `tag`, `status`, `sort_by`, `sort_dir`, `page`, `per_page`. Bỏ `deck_id` để đo toàn collection. `admin_mode` mặc định false; nó là context service được chọn cho phép đo, không phải kiểm chứng quyền HTTP của tài khoản.

Chọn riêng owned/release/snapshot và trường hợp ít/nhiều installs. Case file không tạo fixture và không bảo đảm data đang có đủ override hoặc historical pairs; dùng suite MySQL ở phần 5 để kiểm các nhánh đó.

## 3. Baseline và so sánh

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_browse_mysql.py --cases output/browse-cases.json --output output/browse-before.json --repeat 5 --warmup 1 --as-of 2026-10-24T00:00:00Z --explain
.\.venv\Scripts\python.exe scripts/benchmark_browse_mysql.py --cases output/browse-cases.json --output output/browse-after.json --compare output/browse-before.json --repeat 5 --warmup 1 --explain
```

`--compare` tự dùng lại clock của baseline nếu không truyền `--as-of`. Clock UTC có offset giúp giữ nhất quán due/day-boundary. Mỗi sample có Flask app/request context và session mới; không reuse ORM objects trong request cache từ sample trước.

Mặc định giới hạn một SQL statement 5.000 ms và lock wait 2 giây. Có thể chọn bằng `--max-statement-ms` và `--lock-wait-seconds`; giới hạn này chỉ áp dụng connection của process benchmark. Nó không phải timeout được triển khai cho ứng dụng.

Kết quả chứa:

- Hash của case inputs và toàn payload theo thứ tự; không xuất field values, Note IDs, SQL text, bound parameters hoặc credentials. Case name do người chạy đặt được giữ nguyên.
- Total/page/count trả về, bytes JSON chưa nén, số statement kể cả câu lỗi, locking statement count và thời gian DBAPI execute.
- Inclusive phase spans: scope, count, page/hydrate, authority, release values, overrides, format overlay, serialization; sidebar có deck aggregate. Các span có thể lồng nhau, không cộng chúng để suy ra tổng thời gian.
- Các SQL chậm nhất được mô tả bằng thời gian/độ dài/cờ count/window. `--explain` thêm plan summary, bỏ predicates/parameters; thời gian EXPLAIN không tính vào service latency. Số plan nodes không phải actual execution loops.
- Min/median và sample p95. Với ít samples, p95 thường là sample lớn nhất; không gọi đây là p95 production.

Exit code 0 chỉ khi mọi sample thành công, payload ổn định và comparison tương đương nếu có baseline. Hai lần cùng timeout/error không được coi là bằng chứng parity. Script không ghi đè case file hoặc baseline dùng để compare.

## 4. Diễn giải đúng kết quả

- Ít SQL hơn không tự chứng minh nhanh hơn. Tách count/page/authority trước khi chọn task tối ưu.
- `cursor_execute_ms` không bao trọn fetch/ORM/compile; phần chênh so với elapsed không được mặc định gọi là CPU Python.
- Digest bằng nhau chứng minh các case đã đo trả cùng payload, không thay thế coverage quyền truy cập, release history hoặc concurrency.
- B08 sửa ordering là thay đổi có chủ ý: digest của `sort_by=deck` có thể đổi so với baseline trước sửa. Dùng oracle tên local và pagination test, không ép equality với thứ tự sai cũ.
- Không thêm cache, bỏ lock, thay schema hoặc đổi API contract chỉ để làm số benchmark đẹp hơn.

## 5. Bộ kiểm chứng trên database dùng riêng cho test

```powershell
$previousBrowseMySQLFlag = $env:FLAMA_BROWSE_MYSQL_TESTS
try {
    $env:FLAMA_BROWSE_MYSQL_TESTS = '1'
    .\.venv\Scripts\python.exe scripts/run_tests.py --file tests/test_browse_mysql_contract.py tests/test_browse_baseline_tool.py --backend-only --verbose
} finally {
    $env:FLAMA_BROWSE_MYSQL_TESTS = $previousBrowseMySQLFlag
}
```

`test_browse_mysql_contract.py` mặc định skip để không tạo database khi chưa chọn chạy integration. Khi bật flag, mỗi test tạo một schema loopback có tên `flama_browse_contract_<pid>_<random>`, khớp collation của database cấu hình. Nó chỉ đọc default collation từ database cấu hình; fixtures và `create_all()` chỉ chạy trong schema vừa tạo. Cleanup chỉ DROP đúng schema được test tạo, có guard tên/target, kể cả khi test fail.

Suite tái sử dụng các query-bounds fixtures hiện có nhưng chạy trên MySQL; bổ sung local-name ASC/DESC/pagination, giữ source values, added/removed/renamed/disabled fields, nested arrays, nhiều applications, retired/historical missing pairs và baseline context/write guard. Các schema này kiểm ORM/query contract, không kiểm chuỗi Alembic migrations hoặc concurrent reviews.

Các task B01–B07 vẫn thuộc pha tối ưu tiếp theo. HTTP/load metrics và những phân bố dữ liệu lớn hơn cần bổ sung trong pha đó.
