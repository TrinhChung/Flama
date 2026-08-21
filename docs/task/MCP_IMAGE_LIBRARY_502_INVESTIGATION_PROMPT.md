# Prompt — Điều tra lỗi MCP Image Library 502

Hãy điều tra và sửa lỗi hiện tại của các MCP tool liên quan đến **Flama Image Library** trên branch `develop`.

## Bối cảnh hiện tại

Flama đã có sẵn hệ thống Image Library và MCP đã expose các tool liên quan. Không xây media system mới, không thay đổi thiết kế Image Library nếu chưa chứng minh đó là nguyên nhân lỗi.

Các tool hiện đã xuất hiện qua MCP:

- `search_images`
- `get_image`
- `import_image`

Scope liên quan hiện dùng hệ thống scope media hiện có của Flama:

- `media:read` cho đọc/tìm kiếm ảnh;
- `media:write` cho import/upload/quản lý ảnh.

### Lịch sử lỗi quan sát được

Ban đầu khi gọi MCP Image Library, `search_images` trả:

```text
403
MCP_SCOPE_FORBIDDEN
MCP token does not grant the required scope.
```

Sau thay đổi về scope/auth, lỗi `403 MCP_SCOPE_FORBIDDEN` không còn xuất hiện.

Trạng thái hiện tại khi gọi thật qua MCP:

```text
search_images(limit=5)
→ 502
→ Upstream or external service errors
```

Và khi gọi `get_image` với một key không tồn tại để kiểm tra đường request:

```text
get_image(...)
→ 502
→ Upstream or external service errors
```

`import_image` chưa được dùng để test production vì read path còn đang lỗi; không tạo dữ liệu rác chỉ để kiểm tra write path trước khi hiểu nguyên nhân.

Tóm tắt trạng thái hiện tại:

```text
MCP tool discovery      ✅
Tool schema             ✅
Scope/auth              có vẻ ✅ — 403 cũ đã biến mất
MCP backend execution   ❌ — trả 502
Root cause              ❓ chưa xác định
```

**Không được kết luận sẵn rằng lỗi nằm ở DB, storage, CDN, OAuth hay external fetcher. Phải trace và thu bằng chứng.**

## Mục tiêu

Xác định chính xác nơi phát sinh lỗi 502 trong đường gọi MCP Image Library, sửa root cause với thay đổi nhỏ nhất có thể, và bổ sung test regression để lỗi tương tự không quay lại.

## Luồng cần trace

Bắt đầu từ request MCP và trace xuyên suốt đường thực thi thực tế trong code hiện tại, tối thiểu gồm:

```text
MCP client
  ↓
Flama Connect / MCP endpoint
  ↓
MCP tool registry
  ↓
mcp_tool_service
  ↓
Image Library service / repository / model
  ↓
DB / storage / CDN / remote dependency nếu thực sự được gọi
```

Không được bỏ qua lớp error mapping. Cần xác định **exception gốc nào đang bị chuyển thành 502** và lớp nào thực hiện việc chuyển đó.

## Task điều tra

### 1. Reproduce lỗi có kiểm soát

Reproduce ít nhất:

```text
search_images(limit=5)
```

và ghi lại:

- HTTP/MCP response cuối cùng;
- server traceback đầy đủ;
- exception type;
- exception message;
- layer/file/function nơi exception bắt đầu;
- layer chuyển exception thành `502`.

Nếu local không reproduce được nhưng production/staging reproduce được, phải ghi rõ khác biệt môi trường liên quan.

### 2. Kiểm tra scope/auth nhưng không dừng ở đó

Xác nhận token hiện tại thực sự có quyền cần thiết và tool đang yêu cầu đúng scope:

- `search_images` / `get_image` → read scope phù hợp;
- `import_image` → write scope phù hợp.

Vì lỗi hiện đã chuyển từ `403` sang `502`, không được coi scope là root cause nếu không có bằng chứng mới.

### 3. So sánh MCP path với REST/admin Image Library path

Kiểm tra cùng operation qua API/service hiện có ngoài MCP nếu có thể.

Mục tiêu phân biệt:

```text
Image Library core lỗi
```

hay:

```text
chỉ MCP adapter / serialization / error mapping lỗi
```

Nếu REST/admin path hoạt động nhưng MCP lỗi, tập trung vào adapter MCP thay vì sửa core Image Library.

### 4. Kiểm tra `search_images`

Trace đầy đủ:

- argument validation;
- default `limit` / `offset`;
- keyword/tag/status filter;
- repository/database query;
- model serialization;
- generated image URL hoặc metadata;
- MCP output wrapping/schema.

Test tối thiểu:

```text
search_images(limit=5)
search_images(query=<known keyword>, limit=5)
search_images(tag=<known tag>, limit=5)
```

Một thư viện rỗng phải trả danh sách rỗng hợp lệ, không được trả 502.

### 5. Kiểm tra `get_image`

Test cả hai case:

```text
get_image(<existing image>)
get_image(<non-existing image>)
```

Case không tồn tại phải trả lỗi domain/not-found có cấu trúc phù hợp, không được biến thành generic upstream 502.

Kiểm tra lookup bằng `image_key` và `asset_id` nếu implementation hỗ trợ cả hai.

### 6. Kiểm tra DB/schema

Xác nhận schema/migration của shared image assets trên môi trường lỗi đã được apply đầy đủ.

Kiểm tra tối thiểu:

- table tồn tại;
- column/index cần thiết tồn tại;
- model khớp migration;
- không có query dựa vào column chưa deploy;
- DB session/transaction không bị đóng hoặc dùng sai runtime.

Nếu schema không phải nguyên nhân, ghi rõ bằng chứng loại trừ.

### 7. Kiểm tra storage/CDN/external dependency

Chỉ điều tra các dependency này nếu read path thực sự chạm tới chúng.

Xác nhận:

- URL generation có cần config/env nào không;
- missing CDN/base URL có gây exception không;
- metadata read có vô tình yêu cầu file/storage existence không;
- remote image fetcher có bị gọi trong `search_images` hoặc `get_image` dù không cần thiết không.

`search_images` đọc metadata local không nên phụ thuộc vào một remote website bất kỳ.

### 8. Kiểm tra MCP serialization/output contract

Kiểm tra object trả về từ service trước khi wrap và payload MCP cuối cùng.

Tìm các lỗi kiểu:

- object SQLAlchemy chưa serialize;
- datetime/UUID/binary không JSON serializable;
- key output không khớp output schema;
- `None` ở field schema không cho phép;
- URL/object type không đúng;
- exception từ `_wrap_tool_result` hoặc MCP transport.

### 9. Chỉ test `import_image` sau khi read path ổn định

Sau khi `search_images` và `get_image` hoạt động ổn định, mới test `import_image` bằng một fixture hoặc ảnh test kiểm soát được.

Test:

```text
import_image
  ↓
get_image
  ↓
search_images
```

Xác nhận:

- ảnh được tạo đúng trong shared Image Library;
- SHA-256 deduplication hoạt động nếu implementation hiện có hỗ trợ;
- tags/description được lưu và tìm lại được;
- không tạo duplicate ngoài ý muốn;
- error từ URL invalid/unsupported content được map đúng, không thành generic 502 nếu đó là lỗi input/domain.

Dọn dữ liệu test sau khi hoàn thành nếu test chạy vào môi trường dùng dữ liệu thật.

## Yêu cầu về fix

Sau khi xác định root cause:

1. sửa đúng layer gây lỗi;
2. không bypass scope/auth;
3. không đổi toàn bộ Image Library architecture chỉ để chữa một lỗi adapter;
4. không swallow exception thành success giả;
5. giữ error response có ý nghĩa: validation/auth/not-found/domain/upstream phải phân biệt được;
6. bổ sung regression tests cho root cause thực tế.

## Test regression bắt buộc

Ít nhất phải có coverage cho:

```text
search_images — empty result
search_images — result có dữ liệu
get_image — existing image
get_image — missing image
scope thiếu → 403/forbidden đúng nghĩa
service/domain error → không bị map sai thành upstream 502
```

Nếu fix liên quan serialization/config/storage thì thêm test trực tiếp cho case đó.

Sau khi read path xanh, thêm test `import_image` phù hợp nếu root cause hoặc thay đổi code có ảnh hưởng write path.

## Kết quả cuối cùng phải báo cáo

Không kết thúc bằng câu chung chung như "fixed MCP image issue".

Phải ghi rõ:

```text
Primary root cause:
Contributing cause(s):
Why it returned 502:
Why the previous 403 disappeared:
Files changed:
Tests added/updated:
Commands/tests run:
Result:
Remaining risks:
```

Nếu chưa tìm được root cause, không đoán. Ghi rõ trace đã đi tới đâu, bằng chứng đã có, giả thuyết nào đã bị loại trừ và bước điều tra tiếp theo.

## Branch / commit rule

- Bắt đầu từ `develop` mới nhất.
- Không commit trực tiếp vào `master`.
- Nếu cần sửa code, tạo branch riêng từ `develop` theo convention hiện có của repo.
- Chỉ merge về `develop` khi test liên quan xanh và root cause đã được chứng minh.
