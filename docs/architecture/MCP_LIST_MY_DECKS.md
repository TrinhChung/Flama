# MCP `list_my_decks`

Endpoint MCP tối giản nằm tại `POST /api/mcp` và chỉ expose đúng 1 tool: `list_my_decks`.

## Auth

- Tool không nhận `user_id`.
- `tools/list` có thể gọi mà không cần đăng nhập, vì chỉ trả metadata của tool.
- Nếu request có `Authorization: Bearer <token>` thì backend xác thực bằng MCP access token ngắn hạn.
- Nếu không có Bearer token thì backend fallback về Flask session (`current_user`) như trước.
- Nếu Bearer token hiện diện nhưng sai, hết hạn, bị revoke, vượt request cap, hoặc thiếu scope thì request bị reject và không fallback về session.

## MCP Access Token

- User tạo token từ màn riêng `GET /settings/mcp-tokens` bằng nút `Generate MCP token`.
- Token chỉ hiển thị đúng một lần trong HTML response ngay sau khi tạo.
- Chỉ hash token được lưu trong DB, không lưu plaintext.
- Mặc định token có:
  - TTL: 10 phút
  - Request cap: 30
  - Scope: `deck:read`
- Màn `MCP Tokens` cũng hiển thị expiry, remaining requests, last used, và nút revoke.

## Supported MCP Methods

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

Protocol version hiện được server trả về: `2025-11-25`.

## Example Requests

### 1. Initialize

```http
POST /api/mcp
Content-Type: application/json
Authorization: Bearer <your-short-lived-mcp-token>

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "local-test",
      "version": "0.1.0"
    }
  }
}
```

### 2. List tools

```http
POST /api/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25

{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

### 3. Call `list_my_decks`

```http
POST /api/mcp
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25
Authorization: Bearer <your-short-lived-mcp-token>

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "list_my_decks",
    "arguments": {}
  }
}
```

## Example Response

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"decks\": [{\"deck_id\": 12, \"name\": \"JLPT N5\", \"description\": \"Core deck\", \"created_at\": \"2026-03-31T10:00:00\"}]}"
      }
    ],
    "structuredContent": {
      "decks": [
        {
          "deck_id": 12,
          "name": "JLPT N5",
          "description": "Core deck",
          "created_at": "2026-03-31T10:00:00"
        }
      ]
    }
  }
}
```

## Quick Local Test

1. Chạy app như bình thường, ví dụ qua Docker Compose hoặc `flask run`.
2. Đăng nhập để lấy session cookie:

```bash
curl -s -c /tmp/flama.cookies \
  -X POST http://localhost:4789/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "email=your-user@example.com&password=your-password" > /dev/null
```

3. Mở màn MCP token riêng:

```bash
curl -s -b /tmp/flama.cookies http://localhost:4789/settings/mcp-tokens > /tmp/flama-mcp-page.html
```

4. Tạo MCP token ngắn hạn từ route generate:

```bash
curl -s -b /tmp/flama.cookies \
  -X POST http://localhost:4789/settings/mcp-tokens/generate \
  > /tmp/flama-mcp-dashboard.html
```

5. Trích token plaintext vừa được render đúng một lần:

```bash
TOKEN=$(grep -o 'flama_mcp_[A-Za-z0-9_-]*' /tmp/flama-mcp-dashboard.html | head -n 1)
echo "$TOKEN"
```

6. Gọi `initialize` bằng Bearer token:

```bash
curl -s \
  -X POST http://localhost:4789/api/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"local-test","version":"0.1.0"}}}'
```

7. Gọi tool:

```bash
curl -s \
  -X POST http://localhost:4789/api/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_my_decks","arguments":{}}}'
```

8. Kiểm tra case bị chặn:

```bash
curl -s \
  -X POST http://localhost:4789/api/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_my_decks","arguments":{"user_id":999}}}'
```

Request trên phải bị reject vì tool không nhận `user_id`.
